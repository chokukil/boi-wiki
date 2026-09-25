"""MCP integration for workbook preservation followed by Profile preparation.

The portable Profile runtime remains transport-free. This module joins it to
the repository MCP client without pulling that client into the shipped local
contract archive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from .boi_profile_intake_host import (
    prepare_profile_intake, resume_profile_workflow, run_prepared_profile_workflow)
from .boi_workbook_intake import intake_workbook


def _write_private_json(target, value, conflict_code):
    encoded=json.dumps(value,ensure_ascii=False,indent=2)
    if target.exists():
        if json.loads(target.read_text())!=value:raise ValueError(conflict_code)
        return
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as handle:
        handle.write(encoded);handle.flush();os.fsync(handle.fileno())


def _persist_workflow_result(*, output, intake_receipt_digest, result,
                             source_scope=None, lineage=None):
    session=result.get('session')
    if not isinstance(session,dict):
        raise ValueError('PROFILE_WORKBOOK_RESULT_SESSION_REQUIRED')
    state={'contract_version':'boi/profile-workflow-state@1',
        'intake_receipt_digest':intake_receipt_digest,'workflow_status':result['status'],
        'session':session,'accepted_reviews':result.get('accepted_reviews') or {},
        'trace':result.get('trace') or (),
        'source_scope':source_scope,
        **({'lineage':lineage} if lineage is not None else {}),
        'publication_authority_granted':False,'semantic_truth_proven':False}
    state['state_digest']=semantic_digest(state)
    state_target=output/'profile-workflow-state.json'
    _write_private_json(state_target,state,'PROFILE_WORKBOOK_STATE_CONFLICT')
    receipt={'contract_version':'boi/profile-workbook-request-result@1',
        'intake_receipt_digest':intake_receipt_digest,
        'workflow_state_digest':state['state_digest'],
        'workflow_status':result['status'],'question_executed':result.get('question_executed',False),
        'publication_authority_granted':False,'semantic_truth_proven':False}
    receipt['result_digest']=semantic_digest(receipt)
    target=output/'profile-request-result.json'
    _write_private_json(target,receipt,'PROFILE_WORKBOOK_REQUEST_RESULT_CONFLICT')
    return receipt,state


def _read_workflow_state(path):
    state=json.loads(Path(path).read_text(encoding='utf-8'))
    digest=state.pop('state_digest',None)
    if (state.get('contract_version')!='boi/profile-workflow-state@1'
            or semantic_digest(state)!=digest):
        raise ValueError('PROFILE_WORKBOOK_STATE_CHANGED')
    return state,digest


def _write_receipt(*, output, outcome, material, preparation, source_scope):
    receipt={'contract_version':'boi/profile-workbook-session-receipt@1',
        'source_scope':source_scope,'source_inventory_digest':preparation['source_inventory_digest'],
        'source_snapshot_digest':preparation['source_snapshot_digest'],
        'profile_catalog_digest':preparation['profile_catalog_digest'],
        'profile_admission_digest':material['admission'].get('admission_digest')
            or material['admission'].get('catalog_digest'),
        'profile_catalog_scope_status':material['profile_catalog_scope_status'],
        'routing_status':'awaiting_model_observation','release_authority_granted':False,
        'semantic_truth_proven':False}
    receipt['receipt_digest']=semantic_digest(receipt)
    target=output/'profile-session-receipt.json'
    _write_private_json(target,receipt,'PROFILE_WORKBOOK_SESSION_RECEIPT_CONFLICT')
    return {'outcome':outcome,'preparation':preparation,'receipt':receipt}


async def intake_workbook_profile_session(client, *, path, namespace, output_dir,
                                          domain=None, maximum_selected=12):
    """Preserve a workbook and bind current MCP Profile policy in one session."""
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    outcome=await intake_workbook(client,path=path,namespace=namespace,output_dir=output)
    records=json.loads((output/'source-records.json').read_text())
    material=await client.profile_intake_material(domain=domain)
    source_scope={'artifact_ref':outcome['source']['artifact_ref'],
        'source_revision_digest':outcome['source']['digest'],
        'source_index_revision':outcome['source_index_revision'],'file_name':outcome['file_name'],
        'record_count':outcome['record_count'],'field_count':outcome['field_count']}
    preparation=prepare_profile_intake(preserved_workbook_records=records,
        profile_material=material,source_scope=source_scope,maximum_selected=maximum_selected)
    return _write_receipt(output=output,outcome=outcome,material=material,
        preparation=preparation,source_scope=source_scope)


async def resume_workbook_profile_session(client, *, intake_dir, output_dir,
                                          domain=None, source_path=None,
                                          maximum_selected=12):
    """Reuse an exact prior MCP workbook intake without recapturing its bytes."""
    intake=Path(intake_dir); output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    outcome=json.loads((intake/'outcome.json').read_text())
    source=json.loads((intake/'source.json').read_text())
    records=json.loads((intake/'source-records.json').read_text())
    if (outcome.get('source_preserved') is not True or outcome.get('source')!=source
            or outcome.get('record_count')!=len(records)):
        raise ValueError('PROFILE_WORKBOOK_PRIOR_INTAKE_INVALID')
    if source_path is not None:
        from boi_api.app.governed_runtime.source_envelope import byte_digest
        raw=Path(source_path).read_bytes()
        if byte_digest(raw)!=source.get('digest') or Path(source_path).name!=outcome.get('file_name'):
            raise ValueError('PROFILE_WORKBOOK_PRIOR_SOURCE_MISMATCH')
    source_index_revision=outcome.get('source_index_revision')
    if source_index_revision is None and (intake/'index-saved.json').exists():
        source_index_revision=json.loads((intake/'index-saved.json').read_text()).get('revision')
    inventory_revisions=outcome.get('assets') or ()
    if source_index_revision is None and (not isinstance(inventory_revisions,list)
            or not inventory_revisions or any(not isinstance(item,dict) for item in inventory_revisions)):
        raise ValueError('PROFILE_WORKBOOK_PRIOR_INDEX_REQUIRED')
    material=await client.profile_intake_material(domain=domain)
    source_scope={'artifact_ref':source['artifact_ref'],'source_revision_digest':source['digest'],
        **({'source_index_revision':source_index_revision} if source_index_revision else
           {'source_inventory_revisions':inventory_revisions}),
        'file_name':outcome['file_name'],'record_count':outcome['record_count'],
        'field_count':outcome['field_count'],'prior_intake_reused':True}
    preparation=prepare_profile_intake(preserved_workbook_records=records,
        profile_material=material,source_scope=source_scope,maximum_selected=maximum_selected)
    return _write_receipt(output=output,outcome=outcome,material=material,
        preparation=preparation,source_scope=source_scope)


async def run_workbook_profile_request(client, *, path, namespace, output_dir,
                                       observer, question=None, source_name=None,
                                       reviewer=None, accepted_reviews=None,
                                       domain=None, maximum_selected=12):
    """Preserve an XLSX and run its bounded Profile path in one MCP-bound call.

    Model observation and human/source-owner review remain separate callbacks.
    If review is unavailable the result is ``review_required`` and no question is
    executed. This function never publishes or grants semantic authority.
    """
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    bound=await intake_workbook_profile_session(client,path=path,namespace=namespace,
        output_dir=output_dir,domain=domain,maximum_selected=maximum_selected)
    result=await run_prepared_profile_workflow(preparation=bound['preparation'],
        observer=observer,question=question,source_name=source_name,reviewer=reviewer,
        accepted_reviews=accepted_reviews)
    receipt,state=_persist_workflow_result(output=output,
        intake_receipt_digest=bound['receipt']['receipt_digest'],result=result,
        source_scope=bound['receipt']['source_scope'])
    return {'outcome':bound['outcome'],'receipt':receipt,'state':state,'workflow':result}


async def resume_workbook_profile_request(*, state_path, output_dir, observer,
                                          question=None, source_name=None, reviewer=None):
    """Continue a persisted Profile session without recapture or earlier model calls."""
    state,digest=_read_workflow_state(state_path)
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    result=await resume_profile_workflow(session=state['session'],observer=observer,
        question=question,source_name=source_name,reviewer=reviewer,
        accepted_reviews=state.get('accepted_reviews'),prior_trace=state.get('trace') or ())
    receipt,new_state=_persist_workflow_result(output=output,
        intake_receipt_digest=state['intake_receipt_digest'],result=result,
        source_scope=state.get('source_scope'),lineage=state.get('lineage'))
    return {'receipt':receipt,'state':new_state,'workflow':result,
        'source_recaptured':False,'prior_state_digest':digest}


async def revise_workbook_profile_request(client, *, previous_state_path, correction,
                                          path, namespace, output_dir, observer,
                                          question=None, source_name=None, reviewer=None,
                                          domain=None, maximum_selected=12):
    """Capture changed source bytes and create a linked Profile workflow revision."""
    state,previous_digest=_read_workflow_state(previous_state_path)
    expected={'contract_version','previous_state_digest','previous_source_revision_digest',
        'source_owner_ref','reason'}
    if (not isinstance(correction,dict) or set(correction)!=expected
            or correction.get('contract_version')!='boi/profile-source-correction@1'):
        raise ValueError('PROFILE_SOURCE_CORRECTION_CONTRACT_INVALID')
    scope=state.get('source_scope')
    if not isinstance(scope,dict) or not isinstance(scope.get('source_revision_digest'),str):
        raise ValueError('PROFILE_SOURCE_CORRECTION_PRIOR_SCOPE_REQUIRED')
    if (correction.get('previous_state_digest')!=previous_digest
            or correction.get('previous_source_revision_digest')!=scope['source_revision_digest']):
        raise ValueError('PROFILE_SOURCE_CORRECTION_BASE_MISMATCH')
    if not all(isinstance(correction.get(key),str) and correction[key].strip()
               for key in ('source_owner_ref','reason')):
        raise ValueError('PROFILE_SOURCE_CORRECTION_JUSTIFICATION_REQUIRED')
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    bound=await intake_workbook_profile_session(client,path=path,namespace=namespace,
        output_dir=output,domain=domain,maximum_selected=maximum_selected)
    after_scope=bound['receipt']['source_scope']
    after_digest=after_scope.get('source_revision_digest')
    if after_digest==scope['source_revision_digest']:
        raise ValueError('PROFILE_SOURCE_CORRECTION_UNCHANGED')
    result=await run_prepared_profile_workflow(preparation=bound['preparation'],
        observer=observer,question=question,source_name=source_name,reviewer=reviewer)
    lineage={'contract_version':'boi/profile-source-correction-lineage@1',
        'previous_state_digest':previous_digest,
        'before_source_revision_digest':scope['source_revision_digest'],
        'after_source_revision_digest':after_digest,
        'source_owner_ref':correction['source_owner_ref'],'reason':correction['reason'],
        'correction_digest':semantic_digest(correction),'original_state_preserved':True}
    receipt,new_state=_persist_workflow_result(output=output,
        intake_receipt_digest=bound['receipt']['receipt_digest'],result=result,
        source_scope=after_scope,lineage=lineage)
    return {'outcome':bound['outcome'],'receipt':receipt,'state':new_state,
        'workflow':result,'source_recaptured':True,'prior_state_digest':previous_digest,
        'lineage':lineage}
