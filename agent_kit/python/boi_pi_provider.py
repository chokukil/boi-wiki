"""Local Pi CLI plumbing for isolated structured observations.

The installed Pi CLI is invoked offline with a fresh ephemeral session, all
tools disabled, and automatic context/skills/extensions/prompt-template/theme
discovery disabled. It runs against an isolated PI_CODING_AGENT_DIR holding
only the copied local ninfer-local model definition and minimal settings;
auth and other providers are never copied. Model output is untrusted: exactly
one JSON object conforming to the supplied schema is accepted. Nothing here
performs OS sandboxing; the flags only constrain discovery and tooling.
"""
from __future__ import annotations

import copy
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import validate

PI_CLI = 'pi'
PI_PROVIDER = 'ninfer-local'
PI_MODEL = 'qwen3.8-27b'
# Recorded reasoning setting for this structured stage: high-quality local
# inference by default, never weakened, and always journaled in run.json.
PI_THINKING_LEVEL = 'xhigh'

_TOOL_EVENTS = {'tool_execution_start', 'tool_execution_update', 'tool_execution_end'}
_ERROR_EVENTS = {'auto_retry_start', 'extension_error'}


def pi_dispatch_prompt(prompt, schema):
    """Exact prompt dispatched to the Pi CLI: original prompt plus schema directive."""
    directive = ('Return exactly one JSON object and nothing else: no prose, no markdown fences, '
                 'no commentary before or after it. Every property listed in the schema is required '
                 'and no additional properties are allowed.\nSchema:\n'
                 + json.dumps(schema, ensure_ascii=False, indent=2))
    return prompt + '\n\n' + directive


def _is_loopback(base_url):
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or ''
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or not host or parsed.username is not None or parsed.password is not None:
        return False
    if host in ('localhost', '::1'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def prepare_pi_agent_dir(source_dir, isolated_dir):
    """Copy ONLY the pinned local provider and the selected model into an
    isolated 0700 agent dir with 0600 config files.

    Reads the configured local definition at runtime, pins the local
    provider/model, and validates the loopback endpoint before dispatch.
    Raises before any subprocess dispatch when the definition is absent or
    its endpoint is not loopback. Never copies auth, other providers, or
    other models; the input config and global auth are left untouched.
    Both the provider baseUrl and any selected-model baseUrl override must
    be loopback.
    """
    source = Path(source_dir) / 'models.json'
    try:
        catalog = json.loads(source.read_text())
        provider = catalog['providers'][PI_PROVIDER]
        model = next(item for item in provider['models'] if item.get('id') == PI_MODEL)
    except (OSError, KeyError, TypeError, ValueError, StopIteration):
        raise ValueError('STRUCTURED_PROVIDER_LOCAL_MODEL_UNAVAILABLE') from None
    provider_url = provider.get('baseUrl')
    if not isinstance(provider_url, str) or not _is_loopback(provider_url):
        raise ValueError('STRUCTURED_PROVIDER_LOCAL_MODEL_NOT_LOOPBACK')
    model_url = model.get('baseUrl')
    if model_url is not None and (not isinstance(model_url, str) or not _is_loopback(model_url)):
        raise ValueError('STRUCTURED_PROVIDER_LOCAL_MODEL_NOT_LOOPBACK')
    base_url = model_url if isinstance(model_url, str) else provider_url
    isolated = Path(isolated_dir)
    isolated.mkdir(parents=True, exist_ok=False)
    isolated.chmod(0o700)
    # Pin ONLY the selected model inside the copied provider; the local input
    # config (including its local credential) is preserved verbatim.
    pinned_provider = copy.deepcopy(provider)
    pinned_provider['models'] = [copy.deepcopy(model)]
    models_out = isolated / 'models.json'
    models_out.write_text(json.dumps(
        {'providers': {PI_PROVIDER: pinned_provider}}, ensure_ascii=False, indent=2))
    models_out.chmod(0o600)
    settings_out = isolated / 'settings.json'
    settings_out.write_text(json.dumps({
        'retry': {'enabled': False, 'provider': {'maxRetries': 0}},
        'defaultProjectTrust': 'never', 'quietStartup': True,
        'compaction': {'enabled': True,
                       'reserveTokens': max(1, int(model.get('contextWindow', 128000)) // 10),
                       'keepRecentTokens': 20000}}, ensure_ascii=False, indent=2))
    settings_out.chmod(0o600)
    return {'provider': PI_PROVIDER, 'model': PI_MODEL, 'base_url': base_url,
            'api': model.get('api', provider.get('api')), 'max_tokens': model.get('maxTokens', 16384),
            'context_window': model.get('contextWindow', 128000)}


def _single_json_object(text):
    """Exactly one JSON object: raw text, or one fenced block spanning all of it."""
    candidate = text.strip()
    if candidate.startswith('```'):
        body = candidate[3:]
        if body[:4].lower() == 'json':
            body = body[4:]
        body = body.lstrip()
        if not body.endswith('```'):
            raise ValueError('STRUCTURED_PROVIDER_MALFORMED_OUTPUT')
        candidate = body[:-3].rstrip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        raise ValueError('STRUCTURED_PROVIDER_MALFORMED_OUTPUT') from None
    if not isinstance(value, dict):
        raise ValueError('STRUCTURED_PROVIDER_MALFORMED_OUTPUT')
    return value


def parse_pi_events(stdout_text, schema):
    """Validate the real Pi JSON event stream and extract the single answer.

    Rejects malformed streams, any tool use, provider errors, truncation,
    malformed JSON, and schema violations. The raw stream is the caller's
    journal; this function only decides accept/reject and returns the value.
    """
    # Strict JSONL: records are framed by literal LF only. U+2028/U+2029 are
    # legal inside raw JSON strings, so splitlines() must not be used.
    events = []
    for line in stdout_text.split('\n'):
        if line == '':
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError('STRUCTURED_PROVIDER_MALFORMED_EVENT_STREAM') from None
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            raise ValueError('STRUCTURED_PROVIDER_MALFORMED_EVENT_STREAM')
        events.append(event)
    if not events or events[0].get('type') != 'session':
        raise ValueError('STRUCTURED_PROVIDER_MALFORMED_EVENT_STREAM')
    for event in events:
        if event['type'] in _TOOL_EVENTS:
            raise ValueError('STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE')
        if event['type'] in _ERROR_EVENTS:
            raise ValueError('STRUCTURED_PROVIDER_PROVIDER_ERROR')
        if event['type'] == 'message_update':
            delta = event.get('assistantMessageEvent')
            if isinstance(delta, dict) and str(delta.get('type', '')).startswith('toolcall'):
                raise ValueError('STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE')
    messages = [event['message'] for event in events
                if event['type'] == 'message_end' and isinstance(event.get('message'), dict)
                and event['message'].get('role') == 'assistant']
    if not messages:
        raise ValueError('STRUCTURED_PROVIDER_MISSING_STRUCTURED_OUTPUT')
    if len(messages) != 1:
        # A fresh single-turn observation with tools disabled yields exactly
        # one assistant message; anything else is not the expected shape.
        raise ValueError('STRUCTURED_PROVIDER_MALFORMED_EVENT_STREAM')
    message = messages[0]
    blocks = [block for block in message.get('content', []) if isinstance(block, dict)]
    if any(block.get('type') == 'toolCall' for block in blocks):
        raise ValueError('STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE')
    stop = message.get('stopReason')
    if stop == 'toolUse':
        raise ValueError('STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE')
    if stop in ('error', 'aborted'):
        raise ValueError('STRUCTURED_PROVIDER_PROVIDER_ERROR')
    if stop == 'length':
        raise ValueError('STRUCTURED_PROVIDER_TRUNCATED_OUTPUT')
    if stop != 'stop':
        raise ValueError('STRUCTURED_PROVIDER_MISSING_STRUCTURED_OUTPUT')
    text = ''.join(block.get('text', '') for block in blocks if block.get('type') == 'text')
    value = _single_json_object(text)
    try:
        validate(value, schema)
    except Exception:
        raise ValueError('STRUCTURED_PROVIDER_SCHEMA_MISMATCH') from None
    return value
