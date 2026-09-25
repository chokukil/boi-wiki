"""Assemble a run-wide relation quality input from verified shard children.

This is candidate-only. It neither reviews an interpretation nor approves a
relationship policy; the caller must verify the run, preview, source and grant.
"""

from .bulk_migration import BulkMigrationPolicyError, _digest
from .cardinality_query_shape import RelationshipContract
from .semantic_binding_contract import FrozenContract, Digest
from .metadata_mapping_profile import (
    DeclaredMetadataMappingInputsV2, DeclaredMetadataMappingInputsV4,
    DeclaredObjectMapping, DeclaredPropertyMappingV2, DeclaredPropertyMappingV3,
    derive_metadata_object_set_shapes,
)
from .bulk_migration import AgentV2StoreBulkMigrationRepository


class RunRelationQualityPreviewRequest(FrozenContract):
    expected_preview_digest: Digest
    relation_dependency_digest: Digest
    relationship_contract: RelationshipContract


def _domain_definitions(children, definition_index):
    definitions={}
    active,_,content_verified=definition_index
    if content_verified:
        for entry in active.values():
            definitions[entry['entry_id']]=entry['payload']
    for record in children['records']:
        if 'candidate_profile' in record:
            continue
        logical=record.get('logical_definition') or {}
        if not logical:
            continue
        if (record.get('logical_contract_status')!='draft_valid'
            or record.get('logical_definition_digest')!=_digest(logical)
            or not record.get('logical_evidence_uses')):
            continue
        identifier=logical.get('id')
        if not identifier or identifier in definitions:
            raise BulkMigrationPolicyError('RUN_RELATION_DOMAIN_IDENTITY_AMBIGUOUS')
        definitions[identifier]=logical
    return definitions


def assemble_run_relation_quality_inputs(*, children, dependency, definition_index,
                                         relationship, manifest, source_snapshot_digest):
    """Bind explicit policy to exact RelationType and all endpoint key shards."""
    if (len(children.get('records',()))!=len(children.get('record_refs',()))
        or _digest(children.get('record_refs',()))!=children.get('closure_digest')
        or dependency.get('run_candidate_closure_digest')!=children.get('closure_digest')
        or dependency.get('dependency_digest')!=_digest({k:v for k,v in dependency.items()
            if k!='dependency_digest'})
        or dependency.get('status')!='candidate_mapping_closed'
        or dependency.get('authority')!='candidate_only'):
        raise BulkMigrationPolicyError('RUN_RELATION_DEPENDENCY_NOT_CLOSED')
    relation=RelationshipContract.model_validate(relationship)
    if (relation.contract_id!=dependency.get('relation_ref')
        or relation.left_endpoint_ref!=dependency.get('left_endpoint_ref')
        or relation.right_endpoint_ref!=dependency.get('right_endpoint_ref')
        or relation.schema_snapshot_digest!=manifest.get('schema_snapshot_digest')
        or tuple(relation.physical_keys.left_mapping_refs)!=tuple(
            item['mapping_ref'] for item in dependency['left_key_mappings'])
        or tuple(relation.physical_keys.right_mapping_refs)!=tuple(
            item['mapping_ref'] for item in dependency['right_key_mappings'])):
        raise BulkMigrationPolicyError('RUN_RELATION_POLICY_DEPENDENCY_MISMATCH')
    definitions=_domain_definitions(children,definition_index)
    logical=definitions.get(relation.contract_id)
    if not logical or logical.get('kind')!='RelationType':
        raise BulkMigrationPolicyError('RUN_RELATION_LOGICAL_DEFINITION_UNAVAILABLE')
    if (logical.get('cardinality')!=relation.cardinality
        or logical.get('semantic_name')!=relation.semantic_name
        or logical.get('left_endpoint_ref')!=relation.left_endpoint_ref
        or logical.get('right_endpoint_ref')!=relation.right_endpoint_ref
        or logical.get('relationship_identity_ref')!=relation.relationship_identity_ref):
        raise BulkMigrationPolicyError('RUN_RELATION_LOGICAL_POLICY_CONTRADICTION')
    required={}
    for side,owner in (('left',relation.left_endpoint_ref),
                       ('right',relation.right_endpoint_ref)):
        definition=definitions.get(owner)
        if not definition or definition.get('kind')!='ObjectType':
            raise BulkMigrationPolicyError('RUN_RELATION_OBJECT_DEFINITION_UNAVAILABLE')
        grain=tuple(definition.get('logical_grain') or ())
        if not grain:
            raise BulkMigrationPolicyError('RUN_RELATION_OBJECT_GRAIN_MAPPING_INCOMPLETE')
        required[owner]=(grain,set(grain)|set(dependency[side+'_logical_key_refs']))
    required_refs=set().union(*(refs for _,refs in required.values()))
    key_mapping_refs={item['mapping_ref'] for side in ('left','right')
        for item in dependency[side+'_key_mappings']}
    by_property={}
    by_mapping={}
    for record in children['records']:
        if record.get('candidate_profile')!='data-mapping':
            continue
        payload=record.get('profile_payload') or {}
        if (payload.get('logical_property_ref') not in required_refs
            and (payload.get('physical') or {}).get('mapping_ref') not in key_mapping_refs):
            continue
        model=(DeclaredPropertyMappingV3 if
            (payload.get('physical') or {}).get('temporal_encoding') is not None
            else DeclaredPropertyMappingV2)
        try:
            prop=model.model_validate(payload)
        except ValueError as error:
            raise BulkMigrationPolicyError('RUN_RELATION_PROPERTY_MAPPING_INVALID') from error
        if (prop.logical_property_ref in by_property
            or prop.physical.mapping_ref in by_mapping):
            raise BulkMigrationPolicyError('RUN_RELATION_PROPERTY_MAPPING_AMBIGUOUS')
        by_property[prop.logical_property_ref]=prop
        by_mapping[prop.physical.mapping_ref]=prop
    for record in children['records']:
        if record.get('candidate_profile')!='data-mapping':
            continue
        payload=record.get('profile_payload') or {}
        if (payload.get('logical_property_ref') not in required_refs
            and (payload.get('physical') or {}).get('mapping_ref') in by_mapping):
            raise BulkMigrationPolicyError('RUN_RELATION_PROPERTY_MAPPING_AMBIGUOUS')
    objects=[];selected=[]
    for owner in (relation.left_endpoint_ref,relation.right_endpoint_ref):
        grain,required_properties=required[owner]
        props=sorted((item for item in by_mapping.values() if item.owner_ref==owner
            and item.logical_property_ref in required_properties),
            key=lambda item:item.physical.mapping_ref)
        if (any(ref not in by_property or by_property[ref].owner_ref!=owner
            for ref in required_properties) or not props):
            raise BulkMigrationPolicyError('RUN_RELATION_OBJECT_GRAIN_MAPPING_INCOMPLETE')
        selected.extend(props)
        objects.append(DeclaredObjectMapping(object_ref=owner,
            property_mapping_refs=tuple(item.physical.mapping_ref for item in props),
            logical_key_mapping_refs=tuple(by_property[ref].physical.mapping_ref for ref in grain),
            evidence_span_refs=tuple(sorted({span for item in props for span in item.evidence_span_refs}))))
    if (len({item.physical.source_id for item in selected})!=1
        or not all(item.physical.source_id==dependency['left_key_mappings'][0]['source_id']
            for item in selected)):
        raise BulkMigrationPolicyError('RUN_RELATION_MAPPING_SOURCE_MISMATCH')
    for side,mappings in (('left',dependency['left_key_mappings']),
                          ('right',dependency['right_key_mappings'])):
        for logical_ref,mapping in zip(dependency[side+'_logical_key_refs'],mappings):
            prop=by_property.get(logical_ref)
            if (prop is None or prop.physical.mapping_ref!=mapping['mapping_ref']
                or prop.physical.revision_digest!=mapping['physical_revision_digest']
                or prop.physical.table!=mapping['table'] or prop.physical.column!=mapping['column']):
                raise BulkMigrationPolicyError('RUN_RELATION_KEY_MAPPING_REVISION_MISMATCH')
    shapes=derive_metadata_object_set_shapes(object_mappings=[{
        'object_ref':obj.object_ref,
        'logical_key_mapping_refs':tuple(by_mapping[ref].logical_property_ref
            for ref in obj.logical_key_mapping_refs),
    } for obj in objects],maximum_rows=1000)
    forward=any(item.physical.temporal_encoding is not None for item in selected)
    model=DeclaredMetadataMappingInputsV4 if forward else DeclaredMetadataMappingInputsV2
    try:
        return model(contract_version='boi/declared-metadata-mapping-input@4' if forward
            else 'boi/declared-metadata-mapping-input@2',
            source_id=selected[0].physical.source_id,
            source_snapshot_digest=source_snapshot_digest,
            catalog_snapshot_digest=manifest['catalog_snapshot_digest'],
            schema_snapshot_digest=manifest['schema_snapshot_digest'],
            policy_digest=manifest['acl_policy_digest'],
            domain_candidate_closure_digest=_digest(sorted(record['candidate_digest']
                for record in children['records'] if 'candidate_profile' not in record)),
            authorized_evidence_span_refs=tuple(sorted({span for item in selected
                for span in item.evidence_span_refs})),
            objects=tuple(objects),properties=tuple(selected),
            relationships=(relation,),result_shapes=shapes)
    except ValueError as error:
        raise BulkMigrationPolicyError('RUN_RELATION_MAPPING_CONTRACT_INVALID') from error


def relation_quality_current_key(principal, run_id, relation_ref):
    return 'run-relation-quality-current:' + _digest([principal,run_id,relation_ref])


def persist_run_relation_quality_receipt(repository, *, run, manifest, children,
                                         dependency, preview_digest, catalog, index, response):
    """Preserve a protected diagnostic with exact candidate read fences."""
    from .bulk_migration_qualification import semantic_candidate_closure
    from .bulk_migration_transaction import MigrationWriteSet
    buffer=MigrationWriteSet(repository.store)
    writer=AgentV2StoreBulkMigrationRepository(buffer)
    if writer.get(run.run_id)!=run or writer.manifest_payload(run)!=manifest:
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_RUN_STALE')
    preview=buffer.get('bulk_migration_candidate_previews','preview:'+run.run_id) or {}
    preview_body={k:v for k,v in preview.items() if k not in {
        'updated_at','employee_id','preview_id','preview_digest'}}
    if (preview.get('employee_id')!=run.principal
        or preview.get('preview_digest')!=preview_digest
        or _digest(preview_body)!=preview_digest):
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_PREVIEW_STALE')
    current_children=semantic_candidate_closure(run,manifest,writer)
    if (current_children['record_refs']!=children['record_refs']
        or current_children['records']!=children['records']
        or current_children['closure_digest']!=children['closure_digest']):
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_CANDIDATE_STALE')
    current_catalog=buffer.get('bulk_migration_catalog_snapshots',manifest['catalog_snapshot_ref'])
    index_ref='definition-index:'+manifest['metadata_execution']['definition_closure_digest']
    current_index=buffer.get('bulk_migration_concept_indexes',index_ref)
    if current_catalog!=catalog or current_index!=index:
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_SOURCE_STALE')
    audit=response.get('quality_audit_receipt') or {}
    try:
        relationship=RelationshipContract.model_validate(response.get('relationship_contract'))
    except ValueError as error:
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_BODY_INVALID') from error
    if (response.get('contract_version')!='boi/run-relation-quality-preview@1'
        or response.get('run_id')!=run.run_id
        or response.get('run_semantic_digest')!=run.semantic_digest
        or response.get('manifest_digest')!=run.manifest_digest
        or response.get('preview_digest')!=preview_digest
        or response.get('run_candidate_closure_digest')!=children['closure_digest']
        or response.get('relation_dependency_digest')!=dependency['dependency_digest']
        or relationship.contract_id!=dependency['relation_ref']
        or response.get('relationship_contract_digest')!=relationship.contract_digest
        or audit.get('contract_version')!='boi/metadata-quality-audit@4'
        or audit.get('manifest_digest')!=run.manifest_digest
        or audit.get('principal')!=run.principal
        or audit.get('purpose')!=manifest['purpose']
        or audit.get('mapping_input_digest')!=response.get('mapping_input_digest')
        or audit.get('receipt_digest')!=_digest({k:v for k,v in audit.items()
            if k!='receipt_digest'})
        or response.get('authority')!='candidate_only'
        or response.get('semantic_authority_approved') is not False
        or response.get('query_execution_status')!='not_run'
        or response.get('production_changed') is not False
        or response.get('active_transition') is not False):
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_BODY_INVALID')
    receipt_digest=_digest(response)
    receipt={**response,'receipt_digest':receipt_digest,'employee_id':run.principal}
    key='run-relation-quality:'+receipt_digest
    prior=buffer.get('bulk_migration_candidate_previews',key)
    if prior and {k:v for k,v in prior.items() if k!='updated_at'}!=receipt:
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_CONFLICT')
    buffer.put('bulk_migration_candidate_previews',key,receipt)
    current_key=relation_quality_current_key(run.principal,run.run_id,dependency['relation_ref'])
    buffer.put('bulk_migration_candidate_previews',current_key,{
        'contract_version':'boi/run-relation-quality-current@1',
        'employee_id':run.principal,'run_id':run.run_id,
        'relation_ref':dependency['relation_ref'],'receipt_ref':key,
        'receipt_digest':receipt_digest,'preview_digest':preview_digest,
        'run_candidate_closure_digest':children['closure_digest'],
        'relation_dependency_digest':dependency['dependency_digest'],
        'run_semantic_digest':run.semantic_digest,
        'production_changed':False,'active_transition':False})
    fences=tuple(key for key,value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('RUN_RELATION_RECEIPT_CONCURRENT_REVISION')
    return receipt


def recorded_run_relation_quality(repository, *, run, preview_digest, children,
                                  dependency):
    """Read a historical measurement only when its candidate closure still fits."""
    key=relation_quality_current_key(run.principal,run.run_id,dependency['relation_ref'])
    pointer=repository.store.get('bulk_migration_candidate_previews',key)
    if pointer is None:
        return None
    receipt=repository.store.get('bulk_migration_candidate_previews',pointer.get('receipt_ref',''))
    body={k:v for k,v in (receipt or {}).items() if k not in {'updated_at','employee_id','receipt_digest'}}
    audit=body.get('quality_audit_receipt') or {}
    try:
        relationship=RelationshipContract.model_validate(body.get('relationship_contract'))
    except ValueError as error:
        raise BulkMigrationPolicyError('RUN_RELATION_RECORDED_RECEIPT_DRIFT') from error
    if (not receipt or pointer.get('employee_id')!=run.principal
        or receipt.get('employee_id')!=run.principal
        or receipt.get('receipt_digest')!=_digest(body)
        or pointer.get('receipt_ref')!='run-relation-quality:'+receipt['receipt_digest']
        or pointer.get('receipt_digest')!=receipt['receipt_digest']
        or audit.get('receipt_digest')!=_digest({k:v for k,v in audit.items()
            if k!='receipt_digest'})
        or body.get('relationship_contract_digest')!=relationship.contract_digest
        or body.get('run_id')!=run.run_id
        or body.get('run_semantic_digest')!=run.semantic_digest
        or body.get('manifest_digest')!=run.manifest_digest
        or body.get('preview_digest')!=preview_digest
        or body.get('run_candidate_closure_digest')!=children['closure_digest']
        or body.get('relation_dependency_digest')!=dependency['dependency_digest']
        or any(pointer.get(field)!=body.get(field) for field in (
            'preview_digest','run_candidate_closure_digest','relation_dependency_digest',
            'run_semantic_digest'))):
        raise BulkMigrationPolicyError('RUN_RELATION_RECORDED_RECEIPT_DRIFT')
    return receipt
