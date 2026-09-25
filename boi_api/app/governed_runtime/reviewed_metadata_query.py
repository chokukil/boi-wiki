"""Explicit logical query preparation over current reviewed metadata candidates.

Uses existing candidate, review, preview and freeze stores. It neither executes
SQL nor installs definitions into an active Release.
"""
from dataclasses import dataclass, replace
from typing import Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, Ref, Digest
from .bulk_migration import BulkMigrationPolicyError, _digest
from .bulk_migration_qualification import semantic_candidate_closure
from .bulk_migration_review import semantic_candidate_preview_body, recorded_interpretation_review
from .metadata_mapping_profile import (
    DeclaredMetadataMappingInputsV3,
    DeclaredMetadataMappingInputsV4,
    parse_declared_metadata_mapping_inputs,
)
from .multi_result_query_gateway import (
    ReviewedQueryAuthority, MultiResultSetPlan, MultiResultProjection,
    create_multi_result_logical_plan, validate_multi_result_plan_authority,
)


class ReviewedObjectQueryIntent(FrozenContract):
    contract_version: Literal['boi/reviewed-object-query-intent@1']
    root_object_ref: Ref
    property_refs: tuple[Ref,...] = Field(min_length=1,max_length=100)
    order_property_refs: tuple[Ref,...] = Field(min_length=1,max_length=100)
    maximum_rows: int = Field(ge=1,le=1000)

    @model_validator(mode='after')
    def explicit_projection(self):
        if (len(set(self.property_refs))!=len(self.property_refs)
            or len(set(self.order_property_refs))!=len(self.order_property_refs)
            or not set(self.order_property_refs)<=set(self.property_refs)):
            raise ValueError('REVIEWED_QUERY_PROJECTION_OR_ORDER_INVALID')
        return self


class ReviewedQueryPrepareRequest(FrozenContract):
    shard_id: Ref
    preview_digest: Digest
    intent: ReviewedObjectQueryIntent


class ReviewedQueryExecuteRequest(FrozenContract):
    preparation_receipt_digest: Digest
    idempotency_key: str = Field(min_length=1,max_length=256)


class ReviewedQueryReadRequest(FrozenContract):
    preparation_receipt_digest: Digest
    artifact_ref: Ref


class ReviewedQueryPageRequest(ReviewedQueryReadRequest):
    answer_artifact_semantic_digest: Digest
    result_set_id: Ref
    cursor: str = Field(min_length=1,max_length=4000)


class ReviewedQuestionInterpretRequest(FrozenContract):
    shard_id: Ref
    preview_digest: Digest
    question: str = Field(min_length=1,max_length=8192)


@dataclass(frozen=True)
class ReviewedQueryScope:
    """Current authorized inputs, read before any untrusted question inference."""

    run: object
    shard: object
    manifest: dict
    domain: list[dict]
    inputs: DeclaredMetadataMappingInputsV3 | DeclaredMetadataMappingInputsV4
    audit: dict
    review: dict
    index: dict


def read_reviewed_query_scope(repository, *, principal, run_id, shard_id, preview_digest, runtime_check, quality_check):
    run=repository.get(run_id)
    if not run or run.principal!=principal or run.control_state in {'cancelled','paused','initializing'}:
        raise BulkMigrationPolicyError('REVIEWED_QUERY_RUN_UNAVAILABLE')
    shard=next((s for s in run.shards if s.shard_id==shard_id),None)
    if not shard or shard.state not in {'completed','failed'}:
        raise BulkMigrationPolicyError('REVIEWED_QUERY_SHARD_UNAVAILABLE')
    manifest=repository.manifest_payload(run)
    preview=repository.store.get('bulk_migration_candidate_previews','preview:'+run_id)
    body=semantic_candidate_preview_body(repository,run)
    if (not preview or preview.get('employee_id')!=principal or preview.get('preview_digest')!=preview_digest
        or _digest(body)!=preview_digest):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_PREVIEW_STALE')
    def stage(name):
        value=repository.get_stage_receipt(shard.stage_receipt_refs.get(name,'')) or {}
        if value.get('status')!='pass':raise BulkMigrationPolicyError('REVIEWED_QUERY_REQUIRED_STAGE_NOT_PASS')
        return value['output']
    match=stage('existing-concept-match');mapping=stage('physical-mapping-verify')
    refs=match.get('interpretation_receipt_refs') or []
    if len(refs)!=1:raise BulkMigrationPolicyError('REVIEWED_QUERY_EXACT_REVIEW_REFERENCE_REQUIRED')
    review=repository.store.get('bulk_migration_approvals',refs[0]) or {}
    original=review.get('closure') or {}
    recorded=recorded_interpretation_review(repository,principal=principal,run_id=run_id,shard_id=shard_id,
        preview_digest=original.get('preview_digest',''))
    if (not recorded or recorded!=review or review.get('disposition')!='accept_interpretation'
        or review.get('receipt_digest') not in match.get('interpretation_receipt_digests',[])):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_REVIEW_STALE')
    plan_id='interpretation_'+review['plan_digest'].removeprefix('sha256:')
    confirmation=repository.store.get('plans',plan_id) or {}
    if (confirmation.get('status')!='confirmed' or confirmation.get('employee_id')!=principal
        or confirmation.get('confirmation_result',{}).get('interpretation_receipt',{}).get('receipt_digest')!=review['receipt_digest']):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_REVIEW_STALE')
    children=semantic_candidate_closure(replace(run,shards=(shard,)),manifest,repository)
    domain=[item for item in children['records'] if 'candidate_profile' not in item]
    if (original['manifest_digest']!=run.manifest_digest
        or original['domain_candidate_digests']!=[item['candidate_digest'] for item in domain]
        or original['runtime_closure']!=runtime_check(manifest,domain)):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_SOURCE_CLOSURE_STALE')
    inputs=parse_declared_metadata_mapping_inputs(mapping['declared_mapping_inputs'])
    audit=mapping.get('quality_audit_receipt') or {}
    if (not isinstance(inputs,(DeclaredMetadataMappingInputsV3,DeclaredMetadataMappingInputsV4))
        or inputs.semantic_authority_scope!='reviewed_provisional'
        or inputs.interpretation_receipt_digests!=(review['receipt_digest'],)
        or inputs.domain_candidate_closure_digest!=_digest(sorted(item['candidate_digest'] for item in domain))
        or audit.get('status')!='pass' or audit.get('mapping_input_digest')!=_digest(inputs.model_dump(mode='json'))
        or audit.get('manifest_digest')!=run.manifest_digest
        or audit.get('receipt_digest')!=_digest({k:v for k,v in audit.items() if k!='receipt_digest'})):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_MAPPING_OR_QUALITY_STALE')
    if quality_check(inputs,manifest,audit)!=audit:
        raise BulkMigrationPolicyError('REVIEWED_QUERY_CURRENT_QUALITY_CHANGED')
    index=repository.store.get('bulk_migration_concept_indexes','definition-index:'+manifest['metadata_execution']['definition_closure_digest']) or {}
    if index.get('employee_id')!=principal or index.get('digest')!=manifest['active_concept_index_digest']:
        raise BulkMigrationPolicyError('REVIEWED_QUERY_EXISTING_DEFINITIONS_STALE')
    return ReviewedQueryScope(run,shard,manifest,domain,inputs,audit,review,index)


def prepare_reviewed_query(repository, *, principal, run_id, shard_id, preview_digest, intent, runtime_check, quality_check):
    intent=ReviewedObjectQueryIntent.model_validate(intent)
    scope=read_reviewed_query_scope(repository,principal=principal,run_id=run_id,shard_id=shard_id,
        preview_digest=preview_digest,runtime_check=runtime_check,quality_check=quality_check)
    run,shard,manifest,domain=scope.run,scope.shard,scope.manifest,scope.domain
    inputs,audit,review,index=scope.inputs,scope.audit,scope.review,scope.index
    from .semantic_qualifier import compile_reviewed_qualifiers,validate_candidate_qualifier_provenance
    subject_facets_required='boi/source-subject-facets@1' in manifest.get('profile_revisions',[])
    version=3 if subject_facets_required else 2
    try:
        filters,parameter_specs,parameters,filter_mappings,qualifier_resolution=compile_reviewed_qualifiers(
            domain=domain,index=index,inputs=inputs,root_object_ref=intent.root_object_ref,
            property_refs=intent.property_refs)
        used={item['ref'] for item in qualifier_resolution['definition_revisions']}
        source_stage=repository.get_stage_receipt(shard.stage_receipt_refs.get('domain-ontology-draft','')) or {}
        subject_context=validate_candidate_qualifier_provenance([c for c in domain if (c.get('logical_definition') or {}).get('id') in used],
            source_stage.get('output') or {},subject_facets_required=subject_facets_required)
    except ValueError as error:
        import re
        code=str(error)
        raise BulkMigrationPolicyError(code if re.fullmatch(r'REVIEWED_QUERY_QUALIFIER_[A-Z_]+',code)
            else 'REVIEWED_QUERY_QUALIFIER_UNRESOLVED') from None
    # Preserve full definitions, conditions, exceptions and field evidence in the
    # plan input. Do not replace these with names or retrieval rankings.
    context={'contract_version':f'boi/reviewed-query-context@{version}','manifest_digest':run.manifest_digest,
        'preview_digest':preview_digest,'shard_id':shard_id,'domain_candidates':domain,
        'existing_definition_index':{k:v for k,v in index.items() if k!='updated_at'},
        'qualifier_resolution':qualifier_resolution,
        **({'source_subject_facets':subject_context} if subject_facets_required else {}),
        'declared_mapping_inputs':inputs.model_dump(mode='json'),'quality_audit_receipt':audit,
        'interpretation_receipt':{k:v for k,v in review.items() if k!='updated_at'}}
    context_digest=_digest(context)
    frozen={'contract_version':f'boi/reviewed-query-input-freeze@{version}','principal':principal,
        'run_id':run_id,'shard_id':shard_id,'manifest_digest':run.manifest_digest,'preview_digest':preview_digest,
        'semantic_context_digest':context_digest,'intent':intent.model_dump(mode='json'),'intent_digest':_digest(intent.model_dump(mode='json'))}
    freeze={**frozen,'receipt_digest':_digest(frozen)}
    authority=ReviewedQueryAuthority(contract_version='boi/reviewed-query-authority@1',principal=principal,
        purpose=manifest['purpose'],manifest_digest=run.manifest_digest,preview_digest=preview_digest,
        interpretation_receipt_digest=review['receipt_digest'],semantic_context_digest=context_digest,
        mapping_input_digest=_digest(inputs.model_dump(mode='json')),intent_digest=frozen['intent_digest'],freeze_receipt_digest=freeze['receipt_digest'])
    obj=next((o for o in inputs.objects if o.object_ref==intent.root_object_ref),None)
    props={p.logical_property_ref:p for p in inputs.properties}
    if not obj or any(ref not in props or props[ref].owner_ref!=obj.object_ref for ref in intent.property_refs):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_LOGICAL_PROPERTY_NOT_BOUND')
    physical={p.physical.mapping_ref:p for p in inputs.properties}
    keys=tuple(physical[ref].logical_property_ref for ref in obj.logical_key_mapping_refs)
    if not set(keys)<=set(intent.order_property_refs):
        raise BulkMigrationPolicyError('REVIEWED_QUERY_EXACT_GRAIN_ORDER_REQUIRED')
    selected=tuple(props[ref].physical for ref in intent.property_refs)
    available_mappings=tuple({p.mapping_ref:p for p in (*selected,*filter_mappings)}.values())
    result_set=MultiResultSetPlan(result_set_id='result:reviewed',role='ROOT',object_ref=obj.object_ref,
        source_id=inputs.source_id,table=selected[0].table,
        projections=tuple(MultiResultProjection(mapping_ref=props[ref].physical.mapping_ref,
            column=props[ref].physical.column,output_name=ref) for ref in intent.property_refs),
        exact_grain=keys,filters=filters,parent_link=None,ordering=intent.order_property_refs,
        completeness_policy='BOUNDED',result_row_limit=intent.maximum_rows)
    plan=create_multi_result_logical_plan(shape_solver_outcome_digest=_digest(intent.model_dump(mode='json')),
        profile_contract_binding_digest=context_digest,active_release_digest=None,
        domain_profile_digest=inputs.domain_candidate_closure_digest,mapping_profile_digest=_digest(inputs.model_dump(mode='json')),
        query_profile_digest=frozen['intent_digest'],schema_digest=inputs.schema_snapshot_digest,
        result_sets=(result_set,),parameter_specs=parameter_specs,quality_receipt_digests=(),candidate_authority=authority)
    validation=validate_multi_result_plan_authority(plan,physical_mappings=available_mappings,selected_relationship_ids=())
    if validation.status!='PASS':raise BulkMigrationPolicyError('REVIEWED_QUERY_PLAN_AUTHORITY_INVALID')
    result={'contract_version':f'boi/reviewed-query-preparation@{version}','employee_id':principal,'run_id':run_id,
        'shard_id':shard_id,'semantic_context':context,'input_freeze':freeze,
        'logical_plan':plan.model_dump(mode='json'),'validation_receipt':validation.model_dump(mode='json'),
        'physical_mappings':[item.model_dump(mode='json') for item in available_mappings],
        'parameters':parameters,'result_status':'PROVISIONAL','execution_status':'not_run',
        'production_changed':False,'active_transition':False}
    return {**result,'receipt_digest':_digest(result)}
