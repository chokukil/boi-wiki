"""Provider-neutral external stage driver over the existing Wiki MCP contract.

The caller supplies an external executor, not an arbitrary receipt. Wiki owns
admission/completion. This driver does not infer meaning or choose an SOP.
"""
from __future__ import annotations

import base64
import asyncio
import json
import os
from pathlib import Path

from boi_api.app.governed_runtime.domain_work_contract import DomainHarnessContract,DomainToolReport
from boi_api.app.governed_runtime.tool_execution_contract import ToolInvocation, SignedToolExecution
from boi_api.app.governed_runtime.source_envelope import byte_digest


def retain_stage_result(directory, invocation, result):
    """Persist the executor's exact submission before network I/O, no signing.

    Local evidence can contain source content. The host chooses its private
    directory; this is not a Wiki asset, completion receipt or retry grant.
    """
    if result.receipt.body.invocation != invocation:
        raise ValueError('MCP_STAGE_RESULT_INVOCATION_MISMATCH')
    if result.receipt.body.output_content_digest != byte_digest(result.output_bytes):
        raise ValueError('MCP_STAGE_RESULT_OUTPUT_MISMATCH')
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/(byte_digest(invocation.invocation_id.encode()).split(':')[1]+'.json')
    submission={'receipt':result.receipt.model_dump(mode='json'),
        'output_b64':base64.b64encode(result.output_bytes).decode()}
    raw=json.dumps({'contract_version':'boi/stage-submission-journal@1','submission':submission},
        ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    # A partial write is retained and rejects recovery; it never invites another
    # execution. Identical writes may observe an existing complete journal.
    try:
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        descriptor=os.open(directory,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    except FileExistsError:
        if path.read_bytes()!=raw: raise ValueError('MCP_STAGE_JOURNAL_CONFLICT') from None
    return path


async def redeliver_stage_result(client, path):
    """Explicit exact-result delivery, never execution, renewal or re-signing.

    Wiki verifies current ACL, invocation, lease, trust and signature. A missing
    or corrupt journal cannot recover a lost result; no fallback is provided.
    """
    value=json.loads(Path(path).read_text())
    if set(value)!={'contract_version','submission'} or value['contract_version']!='boi/stage-submission-journal@1':
        raise ValueError('MCP_STAGE_JOURNAL_INVALID')
    submission=value['submission']
    if set(submission)!={'receipt','output_b64'}:raise ValueError('MCP_STAGE_JOURNAL_INVALID')
    receipt=SignedToolExecution.model_validate(submission['receipt'])
    output=base64.b64decode(submission['output_b64'],validate=True)
    if byte_digest(output)!=receipt.body.output_content_digest:raise ValueError('MCP_STAGE_JOURNAL_OUTPUT_MISMATCH')
    current=await client.call('boi_tool_execution',{'action':'read','request':{'invocation_id':receipt.body.invocation.invocation_id}})
    if current['invocation']!=receipt.body.invocation.model_dump(mode='json'):
        raise ValueError('MCP_STAGE_JOURNAL_INVOCATION_MISMATCH')
    return await client.call('boi_tool_execution',{'action':'submit','request':submission})


async def submit_stage_result(client,invocation,result,*,journal_dir=None,clock_recovery_seconds=3):
    """One bounded redelivery only for an explicit server clock rejection.

    A transport/unknown error or any other reason never enters this branch.
    Current authority is checked again after real elapsed time, with the exact
    saved signature. Neither clock nor signed timestamp is changed.
    """
    if not 0 <= clock_recovery_seconds <= 5:raise ValueError('MCP_STAGE_CLOCK_WAIT_BOUND_INVALID')
    path=retain_stage_result(journal_dir,invocation,result) if journal_dir is not None else None
    try:
        return await client.call('boi_tool_execution',{'action':'submit','request':{
            'receipt':result.receipt.model_dump(mode='json'),'output_b64':base64.b64encode(result.output_bytes).decode()}})
    except ValueError as exc:
        if str(exc)!='TOOL_EXECUTION_FINISHED_IN_FUTURE' or path is None:raise
        note=path.with_suffix('.clock-recovery.json')
        with note.open('x') as stream:
            json.dump({'reason_code':str(exc),'wait_seconds':clock_recovery_seconds,
                'same_signed_submission':True,'new_execution':False,'maximum_redeliveries':1},stream)
        await asyncio.sleep(clock_recovery_seconds)
        return await redeliver_stage_result(client,path)


async def read_completed_stage(client, package):
    """Reconstruct recorded outputs after restart; never dispatch or mint receipts."""
    if package['status']!='completed':raise ValueError('MCP_STAGE_NOT_COMPLETED')
    executions=[]
    for tool in package['domain_execution_contract']['stage']['tools']:
        slot=await client.call('boi_tool_execution',{'action':'lookup','request':{
            'task_package_id':package['task_package_id'],'tool_revision':tool['tool_revision']}})
        if slot['state']!='receipt_recorded':raise ValueError('MCP_STAGE_COMPLETED_EVIDENCE_UNAVAILABLE')
        evidence=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':slot['execution_ref']}})
        body=evidence['execution']['signed_execution']['body']
        if (evidence['execution_ref']!=slot['execution_ref'] or body['outcome']!='completed'
                or body['invocation']['task_revision']['ref']!=package['task_package_id']
                or body['invocation']['tool']['revision']!=tool['tool_revision']):
            raise ValueError('MCP_STAGE_COMPLETED_EVIDENCE_MISMATCH')
        report=DomainToolReport.model_validate_json(evidence['output_json'])
        if not all(any(c.check_id==r['check_id'] and c.status in r['accepted_statuses'] for c in report.checks)
                for r in tool['checks']):raise ValueError('MCP_STAGE_COMPLETED_CHECKS_MISMATCH')
        executions.append({'admission':{'execution_ref':slot['execution_ref'],'historical_projection':True},
            'output':json.loads(evidence['output_json'])})
    return {'status':'already_completed','package':package,'executions':executions,
        'new_execution':False,'new_receipt_created':False}


async def run_mcp_stage(client, *, reading, harness_revision, stage_id, sources, inputs,
                        execute, idempotency_key, request_revision=None, execution_journal_dir=None):
    harness=next(a for a in reading['context']['assets'] if a['revision']==harness_revision and a['kind']=='harness')
    contract=DomainHarnessContract.model_validate_json(harness['content_json'])
    stage=next(s for s in contract.stages if s.stage_id==stage_id)
    package=await client.call('boi_domain_work',{'action':'start','request':{
        'harness_revision':harness_revision,'stage_id':stage_id,'sources':sources,
        'reading_ref':reading['reading_ref'],'inputs':inputs,'idempotency_key':idempotency_key,
        **({'request_revision':request_revision} if request_revision is not None else {})}})
    if package['status']=='completed':
        # A retry observes the already recorded completion, not another tool run.
        return await read_completed_stage(client,package)
    if package.get('replayed'):
        # A completed task can be restored exactly. A prior incomplete task
        # cannot be treated as permission to repeat its external execution.
        # Single-attempt workers have their own slot reconciliation path.
        slots=[await client.call('boi_tool_execution',{'action':'lookup','request':{
            'task_package_id':package['task_package_id'],'tool_revision':tool.tool_revision.model_dump(mode='json')}})
            for tool in stage.tools]
        return {'status':'previous_attempt_incomplete','package':package,'executions':[],
            'tool_states':slots,'new_execution':False,'new_receipt_created':False}
    task=package['task_package_id']
    claimed=await client.call('boi_task_claim',{'task_package_id':task,'expected_revision':package['revision'],
        'idempotency_key':idempotency_key+':claim','lease_seconds':900})
    binding={'task_package_id':task,'expected_revision':claimed['revision'],'lease_id':claimed['lease']['lease_id']}
    executions=[]
    for index,tool in enumerate(stage.tools):
        prepared=await client.call('boi_tool_execution',{'action':'prepare','request':{
            **binding,'tool_revision':tool.tool_revision.model_dump(mode='json'),
            'idempotency_key':idempotency_key+':tool:'+str(index)}})
        invocation=ToolInvocation.model_validate(prepared['invocation'])
        material={}
        for artifact in invocation.inputs:
            value=await client.call('boi_tool_execution',{'action':'input','request':{
                'invocation_id':invocation.invocation_id,'name':artifact.name}})
            raw=base64.b64decode(value['content_b64'],validate=True)
            if value['invocation_id']!=invocation.invocation_id or value['input']!=artifact.model_dump(mode='json') or byte_digest(raw)!=artifact.content_digest:
                raise ValueError('MCP_STAGE_INPUT_BINDING_MISMATCH')
            material[artifact.name]=raw
        result=await execute(invocation,material)
        admitted=await submit_stage_result(client,invocation,result,journal_dir=execution_journal_dir)
        executions.append({'admission':admitted,'output':json.loads(result.output_bytes)})
        report=DomainToolReport.model_validate_json(result.output_bytes) if result.receipt.body.outcome=='completed' else None
        accepted=report is not None and all(any(c.check_id==required.check_id and c.status in required.accepted_statuses
            for c in report.checks) for required in tool.checks)
        if not accepted:
            released=await client.call('boi_task_release',{**binding,
                'reason':'Required external stage checks did not pass; evidence retained for revision.'})
            return {'status':'needs_revision','package':released,'executions':executions}
    completed=await client.call('boi_domain_work',{'action':'complete','request':{**binding,
        'execution_refs':[e['admission']['execution_ref'] for e in executions],
        'summary':'The declared external stage checks completed; domain meaning and canonical qualification remain separate.',
        'idempotency_key':idempotency_key+':complete'}})
    return {'status':'completed','package':completed,'executions':executions,'new_execution':True,'new_receipt_created':True}
