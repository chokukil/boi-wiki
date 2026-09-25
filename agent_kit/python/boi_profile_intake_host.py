"""External-agent host for MCP-sourced Profile intake and later NL queries.

The host never accepts a caller-authored Profile catalog. Its ``profile_material``
must be the direct result of ``BoiDomainMcpClient.profile_intake_material`` and its
workbook records must come from the verified source projection. Model callbacks
only propose bounded observations and query plans.
"""
from __future__ import annotations

from copy import deepcopy
import inspect

from pydantic import BaseModel, ConfigDict, Field

from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration
from .boi_profile_intake_router import (
    adjudicate_profile_candidates, adjudicate_profile_route,
    profile_candidate_prompt, routing_prompt, workbook_profile_records,
    workbook_source_features)
from .boi_profile_record_query import (
    ProfileQueryPlan, ProfileRecordLayoutReview, ProfileRouteReview,
    adjudicate_profile_record_layout, execute_profile_query,
    profile_query_prompt, profile_query_recovery_prompt, profile_record_layout_prompt, project_profile_records,
    route_profile_declaration)
from .boi_ontology_query_host import run_published_user_request


class ProfileAuthoringIdentity(BaseModel):
    """Explicit record identity for the typed authoring bridge.

    ``source_scope_ref`` is deliberately opaque.  Equal labels never merge two
    identities; callers must reuse the same ``object_id`` to express reuse.
    """
    model_config = ConfigDict(extra='forbid', frozen=True)
    object_id: str = Field(min_length=1, max_length=512)
    object_type_id: str = Field(min_length=1, max_length=512)
    source_scope_ref: str = Field(min_length=1, max_length=2048)
    display_label: str = Field(min_length=1, max_length=2048)


class ProfileRelationCandidate(BaseModel):
    """One source-bound assertion ready for ``boi_local_knowledge_draft``."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1, max_length=512)
    subject_object_id: str = Field(min_length=1, max_length=512)
    predicate_id: str = Field(min_length=1, max_length=512)
    value: dict
    statement: str = Field(min_length=1, max_length=10000)
    assertion_kind: str = Field(min_length=1, max_length=128)
    polarity: str = Field(min_length=1, max_length=128)
    modality: str = Field(min_length=1, max_length=128)
    conditions: tuple[dict, ...] = ()
    exceptions: tuple[dict, ...] = ()
    applicability: tuple[dict, ...] = ()
    valid_time: dict
    depends_on: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    evidence: tuple[dict, ...] = Field(min_length=1)


def prepare_profile_relation_authoring(*, session, records, relation_candidates,
                                       profile_correction=None, existing_records=None):
    """Bind a routed Profile to exact typed-authoring assertion inputs.

    The bridge makes no semantic or publication decision.  It checks local
    subject/predicate/object types, preserves caller-declared source scopes and
    appends the checked relations to complete record payloads consumed by
    ``boi_local_knowledge_draft.assemble``.  Existing server identities still
    require that assembler's exact revision declaration and the server's
    current-identity verification.
    """
    value,session_digest=_checked_session(session)
    route=value['route']
    if route.get('route_digest')!=semantic_digest({k:v for k,v in route.items() if k!='route_digest'}):
        raise ValueError('PROFILE_RELATION_ROUTE_CHANGED')
    profiles={item['revision']['ref']:item for item in value['available_profiles']}
    selected_ref=route.get('selected_profile_revision')
    selected=profiles.get((selected_ref or {}).get('ref'))
    if selected_ref is not None and (selected is None or selected['revision']!=selected_ref):
        raise ValueError('PROFILE_RELATION_BASE_UNAVAILABLE')
    if route['branch']=='reuse':
        if selected is None or profile_correction is not None:
            raise ValueError('PROFILE_RELATION_REUSE_BASIS_INVALID')
        profile=selected['declaration']
        profile_fields={'profile':deepcopy(profile),'existing_profile_revision':deepcopy(selected_ref)}
    elif route['branch']=='extend':
        if selected is None or route.get('proposed_profile') is None or not isinstance(profile_correction,dict):
            raise ValueError('PROFILE_RELATION_EXTENSION_BASIS_REQUIRED')
        profile=route['proposed_profile']
        profile_fields={'profile':deepcopy(profile),'profile_base_revision':deepcopy(selected_ref),
            'profile_correction':deepcopy(profile_correction)}
    else:
        if route.get('proposed_profile') is None or profile_correction is not None:
            raise ValueError('PROFILE_RELATION_NEW_BASIS_INVALID')
        profile=route['proposed_profile']
        profile_fields={'profile':deepcopy(profile)}

    declaration=KnowledgeProfileDeclaration.model_validate(profile)
    components={item.id:item for item in declaration.components}
    record_values=deepcopy(records)
    if not isinstance(record_values,list) or not record_values:
        raise ValueError('PROFILE_RELATION_RECORDS_REQUIRED')
    identity_values=[]
    for record in record_values:
        if not isinstance(record,dict) or not isinstance(record.get('assertions'),list):
            raise ValueError('PROFILE_RELATION_RECORD_INVALID')
        identity_values.append(ProfileAuthoringIdentity.model_validate({
            'object_id':record.get('object_id'),'object_type_id':record.get('object_type_id'),
            'source_scope_ref':record.get('source_record_locator'),'display_label':record.get('title')}))
    identity_map={item.object_id:item for item in identity_values}
    if len(identity_map)!=len(identity_values):
        raise ValueError('PROFILE_RELATION_IDENTITY_DUPLICATE')
    object_types={item.id for item in declaration.components if item.kind=='object_type'}
    if any(item.object_type_id not in object_types for item in identity_values):
        raise ValueError('PROFILE_RELATION_IDENTITY_TYPE_UNAVAILABLE')

    records_by_id={record['object_id']:record for record in record_values}
    assertions={item.object_id:[] for item in identity_values}
    target_ids=set()
    for raw in relation_candidates:
        candidate=ProfileRelationCandidate.model_validate(raw)
        subject=identity_map.get(candidate.subject_object_id)
        predicate=components.get(candidate.predicate_id)
        if subject is None:
            raise ValueError('PROFILE_RELATION_SUBJECT_UNAVAILABLE')
        if predicate is None or predicate.kind!='predicate':
            raise ValueError('PROFILE_RELATION_PREDICATE_UNAVAILABLE')
        if predicate.subject_type.component_id!=subject.object_type_id:
            raise ValueError('PROFILE_RELATION_SUBJECT_TYPE_MISMATCH')
        authored=candidate.model_dump(mode='json',exclude={'subject_object_id'})
        authored['predicate_id']=candidate.predicate_id
        if candidate.value.get('kind')=='object':
            if set(candidate.value)!={'kind','target_object_id'} or predicate.target_type is None:
                raise ValueError('PROFILE_RELATION_OBJECT_TARGET_REQUIRED')
            target=identity_map.get(candidate.value['target_object_id'])
            if target is None:
                raise ValueError('PROFILE_RELATION_TARGET_UNAVAILABLE')
            if predicate.target_type.component_id!=target.object_type_id:
                raise ValueError('PROFILE_RELATION_TARGET_TYPE_MISMATCH')
            target_ids.add(target.object_id)
        elif candidate.value.get('kind')!=predicate.value_kind:
            raise ValueError('PROFILE_RELATION_VALUE_TYPE_MISMATCH')
        for group in (candidate.conditions,candidate.exceptions,candidate.applicability):
            for clause in group:
                if not isinstance(clause,dict) or not isinstance(clause.get('evidence'),list) \
                        or not clause['evidence']:
                    raise ValueError('PROFILE_RELATION_QUALIFIER_EVIDENCE_REQUIRED')
                for atom in clause.get('atoms',[]):
                    if (not isinstance(atom,dict) or 'subject_ref' in atom
                            or not isinstance(atom.get('subject_object_id'),str)):
                        raise ValueError('PROFILE_RELATION_QUALIFIER_SUBJECT_REQUIRED')
                    atom_subject=identity_map.get(atom['subject_object_id'])
                    atom_predicate=components.get(atom.get('predicate_id'))
                    if atom_subject is None:
                        raise ValueError('PROFILE_RELATION_QUALIFIER_SUBJECT_UNAVAILABLE')
                    if atom_predicate is None or atom_predicate.kind!='predicate':
                        raise ValueError('PROFILE_RELATION_QUALIFIER_PREDICATE_UNAVAILABLE')
                    if atom_predicate.subject_type.component_id!=atom_subject.object_type_id:
                        raise ValueError('PROFILE_RELATION_QUALIFIER_SUBJECT_TYPE_MISMATCH')
                    atom_value=atom.get('value') or {}
                    if atom_value.get('kind')!=atom_predicate.value_kind:
                        raise ValueError('PROFILE_RELATION_QUALIFIER_VALUE_TYPE_MISMATCH')
        assertions[subject.object_id].append(authored)
    if not any(assertions.values()):
        raise ValueError('PROFILE_RELATION_ASSERTIONS_REQUIRED')
    for object_id,values in assertions.items():
        records_by_id[object_id]['assertions'].extend(values)
    if any(not records_by_id[object_id]['assertions'] for object_id in target_ids):
        raise ValueError('PROFILE_RELATION_NEW_TARGET_REQUIRES_AUTHORED_MEANING')

    result={'contract_version':'boi/profile-relation-authoring-preparation@1',
        'session_digest':session_digest,'source_snapshot_digest':value['source_snapshot_digest'],
        'route_digest':route['route_digest'],
        'authoring_spec_fields':{**profile_fields,
            'records':record_values,
            **({'existing_records':deepcopy(existing_records)} if existing_records is not None else {})},
        'relation_target_object_ids':sorted(target_ids),
        'publication_authority_granted':False,'semantic_truth_proven':False}
    result['preparation_digest']=semantic_digest(result)
    return result


def prepare_profile_intake(*, profile_material, source_scope, preserved_workbook_records=None,
                           preserved_source_records=None, domain_guidance=None, maximum_selected=12):
    """Prepare a complete source/Profile comparison without asking for IDs or mappings."""
    if (preserved_workbook_records is None) == (preserved_source_records is None):
        raise ValueError('PROFILE_INTAKE_EXACT_SOURCE_INVENTORY_REQUIRED')
    preserved_workbook_records = (preserved_source_records if preserved_source_records is not None
                                 else preserved_workbook_records)
    if (profile_material.get('profile_catalog_scope_status')!='complete'
            or not isinstance(profile_material.get('profiles'),list)
            or not profile_material['profiles']):
        raise ValueError('PROFILE_INTAKE_MCP_PROFILE_SCOPE_INCOMPLETE')
    admission=profile_material.get('admission') or {}
    if admission.get('semantic_identity_decided') is not False \
            or admission.get('release_authority_granted') is not False:
        raise ValueError('PROFILE_INTAKE_MCP_ADMISSION_BOUNDARY_INVALID')
    features=[item.model_dump(mode='json') for item in
              workbook_source_features(preserved_workbook_records)]
    records=workbook_profile_records(preserved_workbook_records)
    profiles=deepcopy(profile_material['profiles'])
    packet={'contract_version':'boi/profile-intake-preparation@1',
        'source_scope':deepcopy(source_scope),'source_inventory_digest':semantic_digest(preserved_workbook_records),
        'source_snapshot_digest':semantic_digest(records),'features':features,'records':records,
        'available_profiles':profiles,'profile_catalog_digest':semantic_digest(profiles),
        'profile_admission':deepcopy(admission),'maximum_selected':maximum_selected,
        'domain_guidance':deepcopy(domain_guidance),
        'release_authority_granted':False,'semantic_truth_proven':False}
    packet['preparation_digest']=semantic_digest(packet)
    packet['candidate_prompt']=profile_candidate_prompt(features=features,
        available_profiles=profiles,source_scope=source_scope,
        domain_guidance=domain_guidance,maximum_selected=maximum_selected)
    return packet


def _checked_preparation(preparation):
    value=deepcopy(preparation); prompt=value.pop('candidate_prompt',None)
    digest=value.pop('preparation_digest',None)
    if not isinstance(prompt,str) or semantic_digest(value)!=digest:
        raise ValueError('PROFILE_INTAKE_PREPARATION_CHANGED')
    return value,digest


def select_profile_candidates(*, preparation, observation):
    value,digest=_checked_preparation(preparation)
    selected,receipt=adjudicate_profile_candidates(
        available_profiles=value['available_profiles'],observation=observation,
        maximum_selected=value['maximum_selected'])
    selected=[item.model_dump(mode='json') for item in selected]
    stage={'contract_version':'boi/profile-intake-candidate-stage@1',
        'preparation_digest':digest,'source_snapshot_digest':value['source_snapshot_digest'],
        'features':value['features'],'records':value['records'],
        'source_scope':value['source_scope'],'selected_profiles':selected,
        'selection_receipt':receipt,'domain_guidance':value['domain_guidance'],
        'release_authority_granted':False}
    stage['stage_digest']=semantic_digest(stage)
    stage['routing_prompt']=routing_prompt(features=value['features'],available_profiles=selected,
        source_scope=value['source_scope'],domain_guidance=value['domain_guidance'])
    return stage


def _checked_stage(stage):
    value=deepcopy(stage);prompt=value.pop('routing_prompt',None);digest=value.pop('stage_digest',None)
    if not isinstance(prompt,str) or semantic_digest(value)!=digest:
        raise ValueError('PROFILE_INTAKE_CANDIDATE_STAGE_CHANGED')
    return value,digest


def complete_profile_route(*, candidate_stage, observation):
    value,stage_digest=_checked_stage(candidate_stage)
    route=adjudicate_profile_route(features=value['features'],
        available_profiles=value['selected_profiles'],observation=observation)
    session={'contract_version':'boi/profile-intake-session@1','stage_digest':stage_digest,
        'source_snapshot_digest':value['source_snapshot_digest'],'features':value['features'],
        'records':value['records'],'available_profiles':value['selected_profiles'],
        'route':route,'release_authority_granted':False}
    session['session_digest']=semantic_digest(session)
    return session


def prepare_profile_layout(*, session):
    value,digest=_checked_session(session)
    packet={'contract_version':'boi/profile-layout-preparation@1','session_digest':digest,
        'source_snapshot_digest':value['source_snapshot_digest'],'features':value['features'],
        'records':value['records'],'route':value['route'],
        'available_profiles':value['available_profiles'],'release_authority_granted':False}
    packet['preparation_digest']=semantic_digest(packet)
    packet['layout_prompt']=profile_record_layout_prompt(records=value['records'],
        features=value['features'],route=value['route'])
    return packet


def complete_profile_layout(*, preparation, observation):
    value=deepcopy(preparation);prompt=value.pop('layout_prompt',None)
    digest=value.pop('preparation_digest',None)
    if not isinstance(prompt,str) or semantic_digest(value)!=digest:
        raise ValueError('PROFILE_LAYOUT_PREPARATION_CHANGED')
    layout=adjudicate_profile_record_layout(records=value['records'],features=value['features'],
        route=value['route'],observation=observation)
    return {'contract_version':'boi/profile-layout-session@1','session_digest':value['session_digest'],
        'source_snapshot_digest':value['source_snapshot_digest'],'features':value['features'],
        'records':value['records'],'route':value['route'],
        'available_profiles':value['available_profiles'],'layout':layout,
        'release_authority_granted':False,
        'layout_session_digest':semantic_digest({'session_digest':value['session_digest'],
            'layout_digest':layout['layout_digest']})}


def _checked_session(session):
    value=deepcopy(session);digest=value.pop('session_digest',None)
    if semantic_digest(value)!=digest:raise ValueError('PROFILE_INTAKE_SESSION_CHANGED')
    return value,digest


def prepare_profile_question(*, session, question, review=None, layout_review=None):
    if session.get('contract_version')=='boi/profile-layout-session@1':
        value=deepcopy(session); digest=value.pop('layout_session_digest',None)
        expected=semantic_digest({'session_digest':value['session_digest'],
            'layout_digest':value['layout']['layout_digest']})
        if expected!=digest:raise ValueError('PROFILE_LAYOUT_SESSION_CHANGED')
    else:
        value,digest=_checked_session(session)
    profile=route_profile_declaration(route=value['route'],
        available_profiles=value['available_profiles'])
    projection=project_profile_records(records=value['records'],features=value['features'],
        route=value['route'],source_snapshot_digest=value['source_snapshot_digest'],review=review,
        layout=value.get('layout'),layout_review=layout_review)
    packet={'contract_version':'boi/profile-question-preparation@1','session_digest':digest,
        'question':question,'profile':profile,'projection':projection,
        'planner_saw_source_records':False,'release_authority_granted':False}
    packet['preparation_digest']=semantic_digest(packet)
    packet['query_prompt']=profile_query_prompt(question=question,profile=profile,
        queryable_component_ids=projection.get('queryable_component_ids'))
    return packet


def execute_profile_question(*, preparation, plan):
    value=deepcopy(preparation);prompt=value.pop('query_prompt',None);digest=value.pop('preparation_digest',None)
    if not isinstance(prompt,str) or semantic_digest(value)!=digest:
        raise ValueError('PROFILE_QUESTION_PREPARATION_CHANGED')
    checked=ProfileQueryPlan.model_validate(plan).model_dump(mode='json')
    result=execute_profile_query(projection=value['projection'],profile=value['profile'],plan=checked)
    output={'contract_version':'boi/profile-question-execution@1','session_digest':value['session_digest'],
        'question':value['question'],'plan':checked,'result':result,
        'planner_saw_source_records':False,'publication_authority_granted':False}
    output['execution_digest']=semantic_digest(output)
    return output


def prepare_profile_question_recovery(*, preparation, execution):
    value=deepcopy(preparation);value.pop('query_prompt',None)
    digest=value.pop('preparation_digest',None)
    if semantic_digest(value)!=digest:
        raise ValueError('PROFILE_QUESTION_PREPARATION_CHANGED')
    checked=deepcopy(execution);execution_digest=checked.pop('execution_digest',None)
    if semantic_digest(checked)!=execution_digest:
        raise ValueError('PROFILE_QUESTION_EXECUTION_CHANGED')
    if (checked.get('session_digest')!=value['session_digest']
            or checked.get('question')!=value['question']):
        raise ValueError('PROFILE_QUESTION_EXECUTION_MISMATCH')
    row_count=checked.get('result',{}).get('row_count')
    prompt=profile_query_recovery_prompt(question=value['question'],profile=value['profile'],
        queryable_component_ids=value['projection'].get('queryable_component_ids'),
        failed_plan=checked['plan'],row_count=row_count)
    output={'contract_version':'boi/profile-question-recovery@1',
        'preparation_digest':digest,'execution_digest':execution_digest,
        'row_count':row_count,'records_exposed':False,'recovery_prompt':prompt}
    output['recovery_digest']=semantic_digest(output)
    return output


def render_profile_question(*, preparation, execution, source_name):
    """Render exact projected values without exposing host/Profile terminology."""
    value=deepcopy(preparation);value.pop('query_prompt',None)
    digest=value.pop('preparation_digest',None)
    if semantic_digest(value)!=digest:
        raise ValueError('PROFILE_QUESTION_PREPARATION_CHANGED')
    checked_execution=deepcopy(execution)
    execution_digest=checked_execution.pop('execution_digest',None)
    if semantic_digest(checked_execution)!=execution_digest:
        raise ValueError('PROFILE_QUESTION_EXECUTION_CHANGED')
    if (checked_execution.get('session_digest')!=value['session_digest']
            or checked_execution.get('question')!=value['question']):
        raise ValueError('PROFILE_QUESTION_EXECUTION_MISMATCH')
    labels={item['id']:item.get('label') or item['id']
        for item in value['profile'].get('components') or () if isinstance(item,dict) and item.get('id')}
    rows=checked_execution.get('result',{}).get('rows') or []
    if not rows:
        return {'contract_version':'boi/profile-question-display@1',
            'answer':'관련 원문 항목을 찾지 못했습니다.','displayed_rows':[],
            'answer_delivered':True,'unique_top_candidate':False,'source_values_exact':True}
    top_score=(rows[0].get('retrieval') or {}).get('score')
    selected=[row for row in rows if (row.get('retrieval') or {}).get('score')==top_score]
    blocks=[]
    for row in selected:
        lines=[]
        for component,value_item in row.get('values',{}).items():
            shown=(str(value_item) if value_item not in (None,'')
                   else '원문에 값이 기록되어 있지 않습니다.')
            lines.append('- %s: %s'%(labels.get(component,component),shown))
        locator=row.get('source_record_locator')
        if locator is not None:lines.append('- 출처: %s · %s'%(source_name,locator))
        blocks.append('\n'.join(lines))
    if len(selected)==1:
        opening='질문과 가장 관련성이 높은 원문 항목입니다.'
    else:
        opening=('질문만으로 하나를 확정하기 어려워, 관련성이 같은 원문 항목 '
                 '%d개를 함께 보여드립니다.'%len(selected))
    answer=opening+'\n\n'+'\n\n'.join(blocks)+\
        '\n\n설명과 값은 표시한 원문 행에서 그대로 확인했습니다.'
    return {'contract_version':'boi/profile-question-display@1','answer':answer,
        'displayed_rows':[{'record_index':row.get('record_index'),
            'source_record_locator':row.get('source_record_locator'),
            'values':deepcopy(row.get('values') or {})} for row in selected],
        'answer_delivered':True,'unique_top_candidate':len(selected)==1,
        'source_values_exact':True,'semantic_match_verified':False}


def _profile_publication_revision(value):
    if not isinstance(value,dict) or set(value)!={'ref','revision_digest'}:
        raise ValueError('PROFILE_PUBLICATION_RECEIPT_REVISION_INVALID')
    digest=value.get('revision_digest')
    if (not isinstance(digest,str) or len(digest)!=71 or not digest.startswith('sha256:')
            or value.get('ref')!='KnowledgeRevision:'+digest):
        raise ValueError('PROFILE_PUBLICATION_RECEIPT_REVISION_INVALID')
    return deepcopy(value)


def adapt_profile_publication_receipt(*, workflow_result, relation_preparation,
                                      bundle_status, validation_receipt, publish_receipt,
                                      expected_manifest_digest, expected_recipient):
    """Verify one committed server publication against its exact authoring workflow.

    No caller-authored current, approval, or authority flag is accepted.  The
    binding is reconstructed from the server's bundle status, mechanical
    validation and publication receipt, then tied back to the immutable Profile
    session and relation-authoring preparation.
    """
    if not isinstance(workflow_result,dict) or workflow_result.get('contract_version') \
            != 'boi/profile-workflow-result@1':
        raise ValueError('PROFILE_PUBLISHED_BRIDGE_WORKFLOW_REQUIRED')
    session=workflow_result.get('session')
    if not isinstance(session,dict):raise ValueError('PROFILE_PUBLISHED_BRIDGE_SESSION_REQUIRED')
    prepared_session_digest=session.get('layout_session_digest') or session.get('session_digest')
    source_snapshot_digest=session.get('source_snapshot_digest')
    preparation=deepcopy(relation_preparation)
    if not isinstance(preparation,dict) or preparation.get('contract_version') \
            != 'boi/profile-relation-authoring-preparation@1':
        raise ValueError('PROFILE_PUBLICATION_PREPARATION_INVALID')
    preparation_digest=preparation.pop('preparation_digest',None)
    if (preparation_digest!=semantic_digest(preparation)
            or preparation.get('session_digest')!=session.get('session_digest')
            or preparation.get('source_snapshot_digest')!=source_snapshot_digest):
        raise ValueError('PROFILE_PUBLICATION_PREPARATION_MISMATCH')
    if (not isinstance(expected_manifest_digest,str) or len(expected_manifest_digest)!=71
            or not expected_manifest_digest.startswith('sha256:')):
        raise ValueError('PROFILE_PUBLICATION_MANIFEST_DIGEST_INVALID')
    if (not isinstance(expected_recipient,dict) or set(expected_recipient)!={'actor','auth_source'}
            or not all(isinstance(expected_recipient.get(key),str) and expected_recipient[key]
                       for key in ('actor','auth_source'))):
        raise ValueError('PROFILE_PUBLICATION_RECIPIENT_INVALID')
    if not all(isinstance(item,dict) for item in (bundle_status,validation_receipt,publish_receipt)):
        raise ValueError('PROFILE_PUBLICATION_SERVER_RECEIPTS_REQUIRED')
    bundle_ref=bundle_status.get('bundle_ref')
    manifest=bundle_status.get('manifest')
    progress=bundle_status.get('publication_progress')
    if (not isinstance(bundle_ref,str) or not bundle_ref.startswith('local-bundle:sha256:')
            or bundle_status.get('manifest_digest')!=expected_manifest_digest
            or bundle_status.get('state')!='published'
            or bundle_status.get('publication_committed') is not True
            or bundle_status.get('basis_current') is not True
            or not isinstance(manifest,dict) or not isinstance(progress,dict)):
        raise ValueError('PROFILE_PUBLICATION_STATUS_MISMATCH')
    units=progress.get('units')
    if (not isinstance(units,list) or len(units)!=1 or progress.get('publication_committed') is not True
            or units[0].get('state')!='published'):
        raise ValueError('PROFILE_PUBLICATION_UNIT_CLOSURE_MISMATCH')
    unit_id=units[0].get('unit_id');publication_digest=units[0].get('publication_digest')
    if (not isinstance(unit_id,str) or not unit_id.startswith('publication-unit:sha256:')
            or not isinstance(publication_digest,str) or len(publication_digest)!=71
            or not publication_digest.startswith('sha256:')):
        raise ValueError('PROFILE_PUBLICATION_UNIT_CLOSURE_MISMATCH')
    confirmation=bundle_status.get('confirmation_context') or {}
    publish_confirmation=publish_receipt.get('confirmation_context') or {}
    if (any(confirmation.get(key)!=expected_recipient[key] for key in expected_recipient)
            or any(publish_confirmation.get(key)!=expected_recipient[key] for key in expected_recipient)):
        raise ValueError('PROFILE_PUBLICATION_RECIPIENT_MISMATCH')
    if (validation_receipt.get('bundle_ref')!=bundle_ref
            or publish_receipt.get('bundle_ref')!=bundle_ref
            or publish_receipt.get('unit_id')!=unit_id
            or publish_receipt.get('publication_digest')!=publication_digest
            or publish_receipt.get('state')!='published'
            or publish_receipt.get('publication_committed') is not True):
        raise ValueError('PROFILE_PUBLICATION_SERVER_RECEIPT_MISMATCH')
    receipt=publish_receipt.get('receipt') or {}
    if (receipt.get('operation_id')!=publication_digest
            or receipt.get('manifest_digest')!=publication_digest
            or receipt.get('application_store_durable') is not True):
        raise ValueError('PROFILE_PUBLICATION_COMMIT_PROOF_MISMATCH')

    changes=manifest.get('changes')
    if not isinstance(changes,list) or not changes:
        raise ValueError('PROFILE_PUBLICATION_OBJECT_CLOSURE_MISMATCH')
    change_by_id={item.get('object_id'):item for item in changes if isinstance(item,dict)}
    if len(change_by_id)!=len(changes) or None in change_by_id:
        raise ValueError('PROFILE_PUBLICATION_OBJECT_CLOSURE_MISMATCH')
    validation_items=validation_receipt.get('items')
    if not isinstance(validation_items,list):
        raise ValueError('PROFILE_PUBLICATION_REVISION_CLOSURE_MISMATCH')
    validated={}
    for item in validation_items:
        if not isinstance(item,dict) or item.get('state')!='completed':
            raise ValueError('PROFILE_PUBLICATION_REVISION_CLOSURE_MISMATCH')
        target=((item.get('report') or {}).get('target_revision'))
        validated[item.get('object_id')]=_profile_publication_revision(target)
    published=publish_receipt.get('published_items')
    if (set(validated)!=set(change_by_id) or not isinstance(published,list)
            or len(published)!=len(change_by_id)):
        raise ValueError('PROFILE_PUBLICATION_REVISION_CLOSURE_MISMATCH')
    published_by_id={item.get('object_id'):item for item in published if isinstance(item,dict)}
    if set(published_by_id)!=set(change_by_id):
        raise ValueError('PROFILE_PUBLICATION_OBJECT_CLOSURE_MISMATCH')
    checked_items=[]
    for object_id,change in change_by_id.items():
        item=published_by_id[object_id]
        revision=_profile_publication_revision(item.get('revision'))
        expected_stable='domain-asset-head:'+semantic_digest([
            expected_recipient['actor'],change.get('namespace'),change.get('logical_id')])
        if revision!=validated[object_id] or item.get('stable_id')!=expected_stable:
            raise ValueError('PROFILE_PUBLICATION_REVISION_CLOSURE_MISMATCH')
        checked_items.append({'object_id':object_id,'stable_id':expected_stable,'revision':revision})

    query_object_ids=preparation.get('relation_target_object_ids')
    if (not isinstance(query_object_ids,list) or not query_object_ids
            or not all(isinstance(item,str) and item for item in query_object_ids)
            or len(set(query_object_ids))!=len(query_object_ids)
            or not set(query_object_ids)<=set(published_by_id)):
        raise ValueError('PROFILE_PUBLICATION_QUERY_REVISION_CLOSURE_MISMATCH')
    query_revisions=[published_by_id[object_id]['revision'] for object_id in query_object_ids]
    binding={'contract_version':'boi/profile-server-publication-binding@1',
        'prepared_session_digest':prepared_session_digest,
        'source_snapshot_digest':source_snapshot_digest,
        'preparation_digest':preparation_digest,'bundle_ref':bundle_ref,
        'manifest_digest':expected_manifest_digest,'unit_id':unit_id,
        'publication_digest':publication_digest,'recipient':deepcopy(expected_recipient),
        'published_items':sorted(checked_items,key=lambda item:item['object_id']),
        'query_revisions':deepcopy(query_revisions)}
    binding['server_receipt_digest']=semantic_digest({
        'bundle_status':bundle_status,'validation_receipt':validation_receipt,
        'publish_receipt':publish_receipt,'binding':binding})
    return binding


def _published_readback_revisions(journal, published_items):
    """Count only current published documents returned for the exact server identity."""
    published_by_revision={}
    for item in published_items:
        published_by_revision.setdefault(item['revision']['revision_digest'],set()).add(item['stable_id'])
    discovered=set()
    for entry in journal:
        if not isinstance(entry,dict) or entry.get('tool')!='boi_knowledge_read' \
                or entry.get('error') is not None:
            continue
        arguments=entry.get('arguments') or {}
        readback=entry.get('result')
        if not isinstance(arguments,dict) or not isinstance(readback,dict):
            continue
        revision=arguments.get('revision')
        if not isinstance(revision,dict) or revision!=readback.get('revision'):
            continue
        digest=revision.get('revision_digest')
        if (readback.get('stable_id') in published_by_revision.get(digest,set())
                and readback.get('publication_state')=='published'
                and readback.get('is_current_revision') is True):
            discovered.add(digest)
    return discovered


def bridge_profile_workflow_to_published_question(*, workflow_result, publication_binding=None,
                                                  question, host_arguments=None):
    """Use the common published entrypoint only for an exact server-published revision.

    Intake and semantic review do not grant publication authority. The caller must
    supply a server-owned binding to the exact prepared session and source snapshot.
    """
    if not isinstance(workflow_result,dict) or workflow_result.get('contract_version') \
            != 'boi/profile-workflow-result@1':
        raise ValueError('PROFILE_PUBLISHED_BRIDGE_WORKFLOW_REQUIRED')
    if not isinstance(question,str) or not question.strip():
        raise ValueError('PROFILE_PUBLISHED_BRIDGE_QUESTION_REQUIRED')
    session=workflow_result.get('session')
    if not isinstance(session,dict):raise ValueError('PROFILE_PUBLISHED_BRIDGE_SESSION_REQUIRED')
    readiness={'source_preserved':True,
        'review_required':workflow_result.get('status') in ('review_required','review_rejected'),
        'explanation_ready':workflow_result.get('status') in ('ready_for_question','answer_ready'),
        'calculation_ready':False}
    if publication_binding is None:
        return {'contract_version':'boi/profile-published-bridge@1',
            'status':'review_required' if readiness['review_required'] else 'publication_required',
            'readiness':readiness,'published_question_executed':False,
            'publication_authority_granted':False,'workflow_session_preserved':True}
    expected={'contract_version','relation_preparation','bundle_status','validation_receipt',
        'publish_receipt','expected_manifest_digest','expected_recipient'}
    if not isinstance(publication_binding,dict) or set(publication_binding)!=expected \
            or publication_binding.get('contract_version')!='boi/profile-server-publication-evidence@1':
        raise ValueError('PROFILE_PUBLICATION_BINDING_INVALID')
    binding=adapt_profile_publication_receipt(workflow_result=workflow_result,
        relation_preparation=publication_binding['relation_preparation'],
        bundle_status=publication_binding['bundle_status'],
        validation_receipt=publication_binding['validation_receipt'],
        publish_receipt=publication_binding['publish_receipt'],
        expected_manifest_digest=publication_binding['expected_manifest_digest'],
        expected_recipient=publication_binding['expected_recipient'])
    prepared_digest=session.get('layout_session_digest') or session.get('session_digest')
    revisions=binding['query_revisions']
    if (binding.get('prepared_session_digest')!=prepared_digest
            or binding.get('source_snapshot_digest')!=session.get('source_snapshot_digest')):
        raise ValueError('PROFILE_PUBLICATION_BINDING_MISMATCH')
    arguments=deepcopy(host_arguments or {})
    result=run_published_user_request(question,request_context={
        'channel':'profile_intake_bridge','server_receipt_digest':binding['server_receipt_digest'],
        'published_revisions':deepcopy(revisions)},**arguments)
    journal=((result.get('raw') or {}).get('journal') or []) if isinstance(result,dict) else []
    discovered_revisions=_published_readback_revisions(journal,binding['published_items'])
    discovered=all(revision['revision_digest'] in discovered_revisions for revision in revisions)
    if not discovered:
        return {'contract_version':'boi/profile-published-bridge@1',
            'status':'published_revision_not_discovered','readiness':readiness,
            'published_question_executed':True,'published_revision_discovered':False,
            'publication_authority_granted':False,
            'server_publication_receipt_verified':True,'result':result}
    return {'contract_version':'boi/profile-published-bridge@1',
        'status':'answer_ready' if result.get('final_delivery_observed') else 'answer_incomplete',
        'readiness':{**readiness,'explanation_ready':True},
        'published_question_executed':True,'published_revision_discovered':True,
        'publication_authority_granted':False,
        'server_publication_receipt_verified':True,'result':result}


async def _workflow_call(callback, *, stage, payload, allow_none=False):
    """Call one external model/reviewer without prescribing its transport."""
    if callback is None:
        return None
    value=callback(stage=stage, **payload)
    if inspect.isawaitable(value):
        value=await value
    if allow_none and value is None:
        return None
    if not isinstance(value,dict):
        raise ValueError('PROFILE_WORKFLOW_CALLBACK_OBJECT_REQUIRED')
    return value


def _review_requirements(*, session):
    route=session['route']; layout=session['layout']
    required=[]
    if route.get('status')=='requires_semantic_review':
        required.append({'stage':'route_review','contract_version':'boi/profile-route-review@1',
            'route_digest':route['route_digest'],
            'source_snapshot_digest':session['source_snapshot_digest'],
            'review_subject':deepcopy(route)})
    if layout.get('requires_review'):
        required.append({'stage':'layout_review','contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':layout['layout_digest'],
            'source_snapshot_digest':session['source_snapshot_digest'],
            'review_subject':deepcopy(layout)})
    return required


async def run_profile_workflow(*, preserved_workbook_records, profile_material,
                               source_scope, observer, question=None, source_name=None,
                               reviewer=None, accepted_reviews=None,
                               domain_guidance=None, maximum_selected=12):
    """Run the source→Profile→question path while preserving explicit review gates.

    ``observer`` receives only each bounded prompt and returns its JSON object. It
    never receives the workflow state or query records. ``reviewer`` is distinct:
    it receives the exact proposed route/layout and may accept or reject it. When
    no reviewer is connected, the workflow returns a resumable review request
    instead of inventing approval. Publication remains a separate server action.
    """
    preparation=prepare_profile_intake(preserved_workbook_records=preserved_workbook_records,
        profile_material=profile_material,source_scope=source_scope,
        domain_guidance=domain_guidance,maximum_selected=maximum_selected)
    return await run_prepared_profile_workflow(preparation=preparation,observer=observer,
        question=question,source_name=source_name,reviewer=reviewer,
        accepted_reviews=accepted_reviews)


async def run_prepared_profile_workflow(*, preparation, observer, question=None,
                                        source_name=None, reviewer=None, accepted_reviews=None):
    """Advance one exact MCP-bound preparation through all available stages."""
    if not callable(observer):
        raise ValueError('PROFILE_WORKFLOW_OBSERVER_REQUIRED')
    if question is not None and (not isinstance(question,str) or not question.strip()
                                 or not isinstance(source_name,str) or not source_name.strip()):
        raise ValueError('PROFILE_WORKFLOW_QUESTION_SOURCE_REQUIRED')
    trace=[]

    async def observe(stage,prompt):
        value=await _workflow_call(observer,stage=stage,payload={'prompt':prompt})
        trace.append({'stage':stage,'prompt_digest':semantic_digest(prompt),
            'observation_digest':semantic_digest(value),'records_exposed':stage=='record_layout'})
        return value

    candidate=select_profile_candidates(preparation=preparation,
        observation=await observe('profile_candidates',preparation['candidate_prompt']))
    session=complete_profile_route(candidate_stage=candidate,
        observation=await observe('profile_route',candidate['routing_prompt']))
    layout_preparation=prepare_profile_layout(session=session)
    layout_session=complete_profile_layout(preparation=layout_preparation,
        observation=await observe('record_layout',layout_preparation['layout_prompt']))
    return await resume_profile_workflow(session=layout_session,observer=observer,
        question=question,source_name=source_name,reviewer=reviewer,
        accepted_reviews=accepted_reviews,prior_trace=trace)


def _validate_bound_review(*, stage, request, value):
    model=ProfileRouteReview if stage=='route_review' else ProfileRecordLayoutReview
    checked=model.model_validate(value).model_dump(mode='json')
    expected_digest=request['route_digest'] if stage=='route_review' else request['layout_digest']
    actual_digest=checked['route_digest'] if stage=='route_review' else checked['layout_digest']
    if (checked['decision']!='accepted' or actual_digest!=expected_digest
            or checked['source_snapshot_digest']!=request['source_snapshot_digest']):
        raise ValueError('PROFILE_WORKFLOW_ACCEPTED_REVIEW_BINDING_REQUIRED')
    return checked


async def resume_profile_workflow(*, session, observer=None, question=None,
                                  source_name=None, reviewer=None, accepted_reviews=None,
                                  prior_trace=()):
    """Resume an exact review-pending layout session without rerunning intake."""
    if session.get('contract_version')!='boi/profile-layout-session@1':
        raise ValueError('PROFILE_WORKFLOW_LAYOUT_SESSION_REQUIRED')
    checked=deepcopy(session); layout_digest=checked.pop('layout_session_digest',None)
    if layout_digest!=semantic_digest({'session_digest':checked.get('session_digest'),
            'layout_digest':checked.get('layout',{}).get('layout_digest')}):
        raise ValueError('PROFILE_LAYOUT_SESSION_CHANGED')
    if question is not None and (not isinstance(question,str) or not question.strip()
                                 or not isinstance(source_name,str) or not source_name.strip()):
        raise ValueError('PROFILE_WORKFLOW_QUESTION_SOURCE_REQUIRED')
    trace=list(deepcopy(prior_trace))

    async def observe(stage,prompt):
        if not callable(observer):
            raise ValueError('PROFILE_WORKFLOW_OBSERVER_REQUIRED')
        value=await _workflow_call(observer,stage=stage,payload={'prompt':prompt})
        trace.append({'stage':stage,'prompt_digest':semantic_digest(prompt),
            'observation_digest':semantic_digest(value),'records_exposed':False})
        return value

    supplied_reviews=deepcopy(accepted_reviews or {})
    if not isinstance(supplied_reviews,dict) or set(supplied_reviews)-{'route_review','layout_review'}:
        raise ValueError('PROFILE_WORKFLOW_ACCEPTED_REVIEWS_INVALID')
    reviews={}
    pending=[]
    for request in _review_requirements(session=session):
        stage=request['stage']
        if stage in supplied_reviews:
            value=_validate_bound_review(stage=stage,request=request,value=supplied_reviews[stage])
            trace.append({'stage':stage,'request_digest':semantic_digest(request),
                'review_digest':semantic_digest(value),'records_exposed':False,'reused':True})
            reviews[stage]=value
            continue
        value=await _workflow_call(reviewer,stage=stage,payload={'request':request},allow_none=True)
        if value is None:
            pending.append(request)
            continue
        if value.get('decision')=='accepted':
            value=_validate_bound_review(stage=stage,request=request,value=value)
        trace.append({'stage':request['stage'],
            'request_digest':semantic_digest(request), 'review_digest':semantic_digest(value),
            'records_exposed':True})
        if value.get('decision')!='accepted':
            return {'contract_version':'boi/profile-workflow-result@1','status':'review_rejected',
                'session':session,'review':value,'trace':trace,
                'publication_authority_granted':False,'semantic_truth_proven':False}
        reviews[request['stage']]=value
    if pending:
        return {'contract_version':'boi/profile-workflow-result@1','status':'review_required',
            'session':session,'required_reviews':pending,'accepted_reviews':reviews,'trace':trace,
            'question_executed':False,'publication_authority_granted':False,
            'semantic_truth_proven':False}
    if question is None:
        return {'contract_version':'boi/profile-workflow-result@1','status':'ready_for_question',
            'session':session,'accepted_reviews':reviews,'trace':trace,
            'question_executed':False,'publication_authority_granted':False,
            'semantic_truth_proven':False}

    query=prepare_profile_question(session=session,question=question,
        review=reviews.get('route_review'),layout_review=reviews.get('layout_review'))
    execution=execute_profile_question(preparation=query,
        plan=await observe('query_plan',query['query_prompt']))
    recovered=False
    if execution['result']['row_count']==0:
        recovery=prepare_profile_question_recovery(preparation=query,execution=execution)
        execution=execute_profile_question(preparation=query,
            plan=await observe('query_recovery',recovery['recovery_prompt']))
        recovered=True
    display=render_profile_question(preparation=query,execution=execution,source_name=source_name)
    return {'contract_version':'boi/profile-workflow-result@1','status':'answer_ready',
        'session_digest':session['layout_session_digest'],'session':session,
        'answer':display,'execution':execution,'accepted_reviews':reviews,
        'trace':trace,'recovery_used':recovered,'question_executed':True,
        'publication_authority_granted':False,'semantic_truth_proven':False}


def correct_profile_layout(*, session, correction):
    """Create a source-bound layout revision; never mutate or recapture the source."""
    if session.get('contract_version')!='boi/profile-layout-session@1':
        raise ValueError('PROFILE_WORKFLOW_LAYOUT_SESSION_REQUIRED')
    expected={'contract_version','previous_layout_session_digest','source_snapshot_digest',
        'reviewer_ref','reason','replacement_observation'}
    if not isinstance(correction,dict) or set(correction)!=expected \
            or correction.get('contract_version')!='boi/profile-layout-correction@1':
        raise ValueError('PROFILE_LAYOUT_CORRECTION_CONTRACT_INVALID')
    if (correction.get('previous_layout_session_digest')!=session.get('layout_session_digest')
            or correction.get('source_snapshot_digest')!=session.get('source_snapshot_digest')):
        raise ValueError('PROFILE_LAYOUT_CORRECTION_BASE_MISMATCH')
    if not all(isinstance(correction.get(key),str) and correction[key].strip()
               for key in ('reviewer_ref','reason')):
        raise ValueError('PROFILE_LAYOUT_CORRECTION_JUSTIFICATION_REQUIRED')
    checked=deepcopy(session);old_digest=checked.pop('layout_session_digest',None)
    if old_digest!=semantic_digest({'session_digest':checked.get('session_digest'),
            'layout_digest':checked.get('layout',{}).get('layout_digest')}):
        raise ValueError('PROFILE_LAYOUT_SESSION_CHANGED')
    layout=adjudicate_profile_record_layout(records=checked['records'],features=checked['features'],
        route=checked['route'],observation=correction['replacement_observation'])
    layout.pop('layout_digest')
    layout['correction']={
        'contract_version':'boi/profile-layout-correction@1',
        'previous_layout_session_digest':old_digest,
        'source_snapshot_digest':checked['source_snapshot_digest'],
        'reviewer_ref':correction['reviewer_ref'],'reason':correction['reason'],
        'correction_digest':semantic_digest(correction)}
    layout['layout_digest']=semantic_digest(layout)
    output={**checked,'layout':layout}
    output['layout_session_digest']=semantic_digest({'session_digest':output['session_digest'],
        'layout_digest':layout['layout_digest']})
    return output
