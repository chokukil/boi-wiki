"""Small external CLI provider adapter for isolated typed semantic stages.

This is inference, not a tool execution receipt or the complete MCP agent host.
No retries, model fallback, fixture answers, or Wiki internal agent execution.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from boi_api.app.governed_runtime.source_envelope import byte_digest
from agent_kit.python.boi_pi_provider import (
    PI_PROVIDER, PI_MODEL, PI_THINKING_LEVEL, parse_pi_events, pi_dispatch_prompt,
    prepare_pi_agent_dir)


def strict_output_schema(schema):
    """Require optional fields explicitly (nullable fields retain their union)."""
    result = copy.deepcopy(schema)
    def walk(node):
        if isinstance(node, dict):
            node.pop('default', None)
            # Pydantic tagged unions are disjoint through their literal tags.
            # Preserve those branch constraints using the provider-supported
            # anyOf form, without the OpenAPI discriminator annotation.
            if 'discriminator' in node and 'oneOf' in node:
                node['anyOf']=node.pop('oneOf')
                node.pop('discriminator')
            if node.get('type') == 'object':
                node['required'] = list(node.get('properties', {}))
                node['additionalProperties'] = False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(result)
    return result


def audit_codex_events(events):
    """Separate runtime diagnostics from tool activity, retaining both as evidence."""
    items=[event['item'] for event in events if 'item' in event]
    unexpected=any(i.get('type') not in ('agent_message','reasoning','error') for i in items)
    lifecycle=[e.get('type') for e in events if e.get('type') in ('turn.started','turn.completed','turn.failed','error')]
    completed=bool(lifecycle) and lifecycle[-1]=='turn.completed'
    failed=any(e.get('type')=='turn.failed' for e in events)
    return {'observed_item_types':sorted({i.get('type','unknown') for i in items}),
        'diagnostics':[i.get('message') for i in items if i.get('type')=='error']+
            [e.get('message',e.get('error')) for e in events if e.get('type')=='error'],
        'recovered_transport_errors':sum(e.get('type')=='error' for e in events) if completed and not failed else 0,
        'unexpected_tool_use':unexpected,
        'status':'unexpected_tool_use' if unexpected else 'incomplete_turn' if failed or not completed else 'completed'}


def _run_codex_process(command, *, cwd, stdout, stderr, input, timeout_seconds):
    """Use the native host's isolated process-group boundary for CLI wrappers.

    A wrapper exiting does not establish that its native child has exited. On
    timeout signal the group even after the wrapper exits, then reap our child.
    Descendants that leave the group and remote inference remain unobserved.
    """
    process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,
        start_new_session=True)
    timed_out=False;signals=[]
    def signal_group(sig):
        try:os.killpg(process.pid,sig)
        except ProcessLookupError:return
        signals.append(sig.name)
    try:
        process.communicate(input=input,timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out=True
        signal_group(signal.SIGTERM)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:pass
        # The direct wrapper may already be reaped while a descendant ignores
        # TERM. Do not make group cleanup conditional on process.wait timing out.
        signal_group(signal.SIGKILL)
        process.wait()
    finally:
        if process.stdin is not None and not process.stdin.closed:process.stdin.close()
    try:
        os.killpg(process.pid,0)
        group_present=True
    except ProcessLookupError:group_present=False
    return {'status':'timed_out' if timed_out else 'completed' if process.returncode==0 else 'failed',
        'returncode':process.returncode,'local_process':{
            'lifecycle_version':'boi/codex-process-group@1',
            'state':'terminated','scope':'direct_child_waited_process_group_observed',
            'pid':process.pid,'process_group_id':process.pid,'termination_signals':signals,
            'reason':'timeout_group_signaled_and_child_waited' if timed_out else 'exited_and_waited',
            # Presence can include zombies pending reaping by their owner. No
            # claim of group-wide disappearance or remote cancellation follows.
            'process_group_present_after_wait':group_present,
            'remote_completion':'not_established_by_local_process_exit'}}


def run_structured(*, provider='codex', prompt, schema, output_dir, timeout_seconds=900, knowledge_reading_ref=None, input_revisions=None, model_settings=None):
    if model_settings is not None:
        if (provider!='codex' or not isinstance(model_settings,dict)
                or set(model_settings)!={'model','reasoning_effort'}
                or any(not isinstance(v,str) or not v.strip() for v in model_settings.values())):
            raise ValueError('STRUCTURED_PROVIDER_MODEL_SETTINGS_INVALID')
        model_settings=copy.deepcopy(model_settings)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    schema = strict_output_schema(schema)
    schema_path = output / 'schema.json'
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2))
    if provider in ('codex','claude') and os.environ.get('BOI_ALLOW_CLOUD_MODEL_WORK') != '1':
        (output/'prompt.txt').write_text(prompt)
        (output/'run.json').write_text(json.dumps({'provider':provider,'status':'cloud_deferred',
            'returncode':None,'new_session':False,'new_model_dispatch':False,
            'prompt_digest':byte_digest(prompt.encode()),'schema_digest':byte_digest(schema_path.read_bytes())},indent=2))
        raise ValueError('STRUCTURED_PROVIDER_CLOUD_DEFERRED')
    executable = shutil.which(provider)
    if not executable or provider not in ('codex', 'claude', 'pi'):
        raise ValueError('STRUCTURED_PROVIDER_UNAVAILABLE')
    # prompt.txt/prompt_digest remain the ORIGINAL admitted prompt (replayed by
    # McpModelWorker.deliver). For Pi the appended-schema dispatched bytes are
    # journaled separately as wire-prompt.txt / wire_prompt_digest.
    pinned = None
    wire_prompt = None
    if provider == 'pi':
        source_dir = os.environ.get('PI_CODING_AGENT_DIR') or str(Path.home() / '.pi' / 'agent')
        pinned = prepare_pi_agent_dir(source_dir, output / 'pi-agent-dir')
        wire_prompt = pi_dispatch_prompt(prompt, schema)
    (output / 'prompt.txt').write_text(prompt)
    if provider == 'pi':
        (output / 'wire-prompt.txt').write_text(wire_prompt)
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout.strip()
    started = time.time()
    child_env = None
    if provider == 'pi':
        # Isolated agent dir holds only the copied local model definition;
        # offline startup, fresh ephemeral session, no tools, no discovery.
        child_env = {**os.environ, 'PI_CODING_AGENT_DIR': str(output / 'pi-agent-dir'),
                     'PI_OFFLINE': '1', 'PI_SKIP_VERSION_CHECK': '1'}
    # A fresh empty work directory keeps repository instructions and evaluation
    # artifacts out of discovery. No model-side tools are needed for this stage.
    with tempfile.TemporaryDirectory(prefix='boi-semantic-provider-') as temporary:
        if provider == 'codex':
            command = [executable, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '--json', '--output-schema', str(schema_path),
                '--output-last-message', str(output / 'output.json'), '-C', temporary,
                '-c', 'features.shell_tool=false', '-c', 'features.unified_exec=false',
                '-c', 'features.multi_agent=false', '-c', 'features.memories=false',
                '-c', 'features.plugins=false',
                '-c', 'web_search="disabled"', '-c', 'apps._default.enabled=false',
                '-c', 'project_doc_max_bytes=0', '-']
            if model_settings is not None:
                command[-1:-1]=['--model',model_settings['model'],'-c',
                    'model_reasoning_effort='+json.dumps(model_settings['reasoning_effort'])]
        elif provider == 'pi':
            # The prompt travels on stdin (never argv): Korean review-material
            # prompts far exceed the kernel per-argument limit.
            command = [executable, '--print', '--mode', 'json', '--offline', '--no-session', '--no-tools',
                '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-themes',
                '--no-context-files', '--no-approve', '--thinking', PI_THINKING_LEVEL,
                '--provider', PI_PROVIDER, '--model', PI_MODEL]
        else:
            command = [executable, '-p', '--output-format', 'json', '--json-schema', json.dumps(schema),
                '--no-session-persistence', '--tools', '', '--strict-mcp-config',
                '--mcp-config', '{"mcpServers":{}}', '--permission-mode', 'dontAsk', '--safe-mode']
        status, returncode, local_process = 'completed', None, None
        with (output/'stdout.txt').open('wb') as stdout, (output/'stderr.txt').open('wb') as stderr:
            try:
                if provider=='codex':
                    execution=_run_codex_process(command,cwd=temporary,stdout=stdout,stderr=stderr,
                        timeout_seconds=timeout_seconds,input=prompt.encode())
                    status,returncode,local_process=execution['status'],execution['returncode'],execution['local_process']
                else:
                    child = subprocess.run(command, cwd=temporary,
                        stdout=stdout, stderr=stderr, timeout=timeout_seconds,
                        input=(wire_prompt if provider == 'pi' else prompt).encode(),
                        **({'env': child_env} if provider == 'pi' else {}))
                    returncode = child.returncode
                    if returncode != 0:status = 'failed'
            except subprocess.TimeoutExpired:
                status = 'timed_out'
    # Other providers retain their historical direct-child lifecycle. New Codex
    # calls record the process-group observation without rewriting old records.
    meta = {'provider':provider, 'cli_version':version, 'status':status, 'returncode':returncode,
        'local_process':local_process or {'state':'terminated','scope':'direct_child_only',
            'reason':'timeout_killed_and_waited' if status=='timed_out' else 'exited_and_waited',
            'remote_completion':'not_established_by_local_process_exit'},
        **({'knowledge_reading_ref':knowledge_reading_ref} if knowledge_reading_ref else {}),
        **({'input_revisions':input_revisions} if input_revisions is not None else {}),
        'started_at_unix':started, 'elapsed_seconds':time.time()-started,
        'prompt_digest':byte_digest(prompt.encode()), 'schema_digest':byte_digest(schema_path.read_bytes()),
        'new_session':True, 'tool_execution_receipt':False, 'mcp_e2e':False,
        'model_selection':'provider_default', 'tool_policy':'no_tools_requested_shell_web_apps_disabled'}
    if model_settings is not None:
        meta.update(model_selection='explicit_cli_configuration',model_settings=model_settings,
            model_settings_digest=byte_digest(json.dumps(model_settings,sort_keys=True).encode()),
            backend_model_snapshot='not_attested')
    if provider == 'codex':
        meta['execution_isolation_version'] = 'boi/codex-no-plugins@1'
    if provider == 'pi':
        # Truthful local identity and isolation provenance. The CLI flags
        # constrain discovery and tooling only; they provide no OS sandbox.
        meta.update({'model':pinned['model'], 'model_provider':pinned['provider'],
            'model_base_url':pinned['base_url'], 'model_max_tokens':pinned['max_tokens'],
            'model_context_window':pinned['context_window'], 'agent_dir_isolated':True,
            'os_sandbox':False, 'thinking_level':PI_THINKING_LEVEL,
            'offline':True, 'skip_version_check':True,
            'wire_prompt_digest':byte_digest(wire_prompt.encode()),
            'isolation_provenance':'ephemeral_session_isolated_agent_dir_tools_and_discovery_disabled'})
        meta['model_selection'] = 'pinned_local_model'
        meta['tool_policy'] = 'all_tools_disabled'
    codex_audit=None
    if provider == 'codex':
        events=[];malformed=0
        for line in (output/'stdout.txt').read_text(errors='replace').splitlines():
            if not line.strip():continue
            try:
                event=json.loads(line)
                if not isinstance(event,dict):raise ValueError('event object required')
                events.append(event)
            except ValueError:malformed+=1
        codex_audit=audit_codex_events(events)
        meta['event_stream']={**codex_audit,'malformed_line_count':malformed,
            'stdout_digest':byte_digest((output/'stdout.txt').read_bytes()),
            'stderr_digest':byte_digest((output/'stderr.txt').read_bytes()),
            'stdout_bytes':(output/'stdout.txt').stat().st_size,
            'stderr_bytes':(output/'stderr.txt').stat().st_size}
        # Process termination remains authoritative: a partial event stream or
        # even a completed turn event must never upgrade a timed-out process.
        if malformed:codex_audit={**codex_audit,'status':'invalid_event_stream'}
    if status == 'completed':
        if provider == 'claude':
            wire = json.loads((output/'stdout.txt').read_text())
            if wire.get('is_error') or 'structured_output' not in wire:
                meta['status'] = 'missing_structured_output'
            else:
                (output/'output.json').write_text(json.dumps(wire['structured_output'], ensure_ascii=False, indent=2))
        elif provider == 'pi':
            # Model output is untrusted: require exactly one valid JSON object
            # conforming to the supplied schema from the real event stream.
            try:
                value = parse_pi_events((output/'stdout.txt').read_text(), schema)
            except ValueError as exc:
                meta['status'] = str(exc).removeprefix('STRUCTURED_PROVIDER_').lower()
            else:
                (output/'output.json').write_text(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            meta.update(codex_audit)
        if (output/'output.json').is_file():
            meta['output_digest'] = byte_digest((output/'output.json').read_bytes())
        elif meta['status'] == 'completed':meta['status'] = 'missing_structured_output'
    (output/'run.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    if meta['status'] != 'completed':
        raise ValueError('STRUCTURED_PROVIDER_' + meta['status'].upper())
    return json.loads((output/'output.json').read_text()), meta


def reconcile_completed_codex_output(output_dir):
    """Read-only reconciliation of a terminal CLI stream misclassified historically."""
    from jsonschema import validate
    root=Path(output_dir);old=json.loads((root/'run.json').read_text())
    if old.get('provider')!='codex' or old.get('returncode')!=0 or old.get('status') not in ('completed','incomplete_turn'):
        raise ValueError('CODEX_RECONCILIATION_NOT_TERMINAL_SUCCESS')
    raw=(root/'stdout.txt').read_bytes()
    if byte_digest(raw)!=old.get('event_stream',{}).get('stdout_digest'):
        raise ValueError('CODEX_RECONCILIATION_STREAM_CHANGED')
    events=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    audit=audit_codex_events(events)
    if audit['status']!='completed':raise ValueError('CODEX_RECONCILIATION_NOT_COMPLETED')
    for filename,key in [('prompt.txt','prompt_digest'),('schema.json','schema_digest'),('output.json','output_digest')]:
        if byte_digest((root/filename).read_bytes())!=old.get(key):
            raise ValueError('CODEX_RECONCILIATION_ARTIFACT_CHANGED')
    value=json.loads((root/'output.json').read_text())
    messages=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    if not messages or json.loads(messages[-1])!=value:raise ValueError('CODEX_RECONCILIATION_OUTPUT_CHANGED')
    validate(value,json.loads((root/'schema.json').read_text()))
    return value,{**old,'status':'completed','terminal_reconciliation':{'prior_status':old['status'],
        'prior_run_digest':byte_digest((root/'run.json').read_bytes()),'event_audit':audit,'new_model_calls':0}}
