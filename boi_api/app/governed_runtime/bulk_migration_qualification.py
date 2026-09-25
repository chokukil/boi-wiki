"""Derive qualification from the persisted run's exact required stage closure."""
from .bulk_migration import _digest, BulkMigrationPolicyError, stage_receipt_contract_valid
from .bulk_migration_execution import (
    P0_B3_PIPELINE_V2, SEMANTIC_METADATA_PIPELINE_V1, NORTH_STAR_ETCH_PIPELINE_V1,
    INTAKE_CHECKPOINT_PIPELINE_V1,
)


def profile_candidate_payload(profile, payload, domain_digests):
    if profile not in {'data-mapping','query'}:
        raise BulkMigrationPolicyError('DERIVED_PROFILE_KIND_INVALID')
    body={'candidate_contract_version':'boi/derived-profile-candidate@1',
        'candidate_profile':profile,'profile_payload':payload,
        'domain_dependency_candidate_digests':sorted(domain_digests),
        'status':'PROVISIONAL','authority':'candidate_only'}
    return {**body,'candidate_digest':_digest(body)}


def semantic_candidate_closure(run, manifest, repository):
    """Read exact derived records, not shard wrappers or a discovery listing.

    Used by qualification, review and the existing Workbench. Historical
    manifests retain their prior contract; 0.3 source execution binds children.
    """
    if not manifest.get('metadata_execution'):
        return {'records':[], 'record_refs':[], 'closure_digest':_digest([])}
    if not hasattr(repository,'store'):
        raise BulkMigrationPolicyError('SEMANTIC_CANDIDATE_STORE_REQUIRED')
    records=[];refs=[];seen=set();source_refs={item['artifact_ref'] for item in manifest['source_artifacts']}
    for shard in sorted(run.shards,key=lambda s:s.shard_id):
        stage_ref=shard.stage_receipt_refs.get('domain-ontology-draft')
        if not stage_ref:continue  # incomplete stages are independently withheld
        receipt=repository.get_stage_receipt(stage_ref) or {}
        body={k:v for k,v in receipt.items() if k not in {'updated_at','stage_receipt_digest'}}
        if (_digest(body)!=stage_ref or receipt.get('employee_id')!=run.principal
            or receipt.get('run_id')!=run.run_id or receipt.get('shard_id')!=shard.shard_id
            or receipt.get('attempt_digest')!=shard.last_attempt_digest):
            raise BulkMigrationPolicyError('SEMANTIC_CANDIDATE_STAGE_DRIFT')
        output=receipt.get('output') or {}
        proposed=output.get('domain_candidates') or []
        references=output.get('candidate_record_refs') or []
        if len(references)!=len(proposed) or len(proposed)>manifest['max_objects_per_shard']:
            raise BulkMigrationPolicyError('SEMANTIC_DERIVED_CLOSURE_INCOMPLETE')
        if receipt.get('status')=='pass' and (not proposed
            or output.get('derived_candidate_count')!=len(proposed)
            or output.get('derived_candidate_limit')!=manifest['max_objects_per_shard']):
            raise BulkMigrationPolicyError('SEMANTIC_DERIVED_COUNT_CONTRACT_INVALID')
        for reference, candidate in zip(references,proposed):
            record=repository.store.get('bulk_migration_candidates',reference)
            actual={k:v for k,v in (record or {}).items() if k!='updated_at'}
            expected={**candidate,'employee_id':run.principal,'run_id':run.run_id,
                'shard_id':shard.shard_id,'state':'semantically_drafted','active_transition':False}
            if (actual!=expected or _digest(actual)!=reference
                or candidate.get('candidate_digest')!=_digest({k:v for k,v in candidate.items() if k!='candidate_digest'})
                or candidate.get('source_record',{}).get('artifact_ref') not in source_refs
                or reference in seen):
                raise BulkMigrationPolicyError('SEMANTIC_DERIVED_CANDIDATE_DRIFT')
            seen.add(reference);refs.append(reference);records.append(actual)
        domain_digests=sorted(candidate['candidate_digest'] for candidate in proposed)
        total=len(proposed)
        for stage,profile,field in (('physical-mapping-verify','data-mapping','mapping_candidates'),
                                    ('query-contract-author','query','query_candidates')):
            stage_ref=shard.stage_receipt_refs.get(stage)
            receipt=repository.get_stage_receipt(stage_ref) if stage_ref else None
            output=(receipt or {}).get('output') or {}
            # Historical stage outputs had no derived profile envelope. Their
            # original Domain-only evidence remains historical, not rewritten.
            version=output.get('derived_profile_contract_version')
            if version is None:continue
            body={k:v for k,v in receipt.items() if k not in {'updated_at','stage_receipt_digest'}}
            if (version!='boi/derived-profile-candidate@1' or _digest(body)!=stage_ref
                or receipt.get('employee_id')!=run.principal or receipt.get('run_id')!=run.run_id
                or receipt.get('shard_id')!=shard.shard_id or receipt.get('skill_id')!=stage
                or receipt.get('attempt_digest')!=shard.last_attempt_digest):
                raise BulkMigrationPolicyError('SEMANTIC_CANDIDATE_STAGE_DRIFT')
            payloads=output.get(field) or []
            references=output.get('candidate_record_refs') or []
            total+=len(payloads)
            if (len(references)!=len(payloads) or total>manifest['max_objects_per_shard']
                or output.get('derived_candidate_count')!=len(payloads)
                or output.get('derived_candidate_total')!=total
                or output.get('derived_candidate_limit')!=manifest['max_objects_per_shard']):
                raise BulkMigrationPolicyError('SEMANTIC_DERIVED_COUNT_CONTRACT_INVALID')
            for reference,payload in zip(references,payloads):
                candidate=profile_candidate_payload(profile,payload,domain_digests)
                expected={**candidate,'employee_id':run.principal,'run_id':run.run_id,
                    'shard_id':shard.shard_id,'state':'semantically_drafted','active_transition':False}
                record=repository.store.get('bulk_migration_candidates',reference)
                actual={k:v for k,v in (record or {}).items() if k!='updated_at'}
                if actual!=expected or _digest(actual)!=reference or reference in seen:
                    raise BulkMigrationPolicyError('SEMANTIC_DERIVED_CANDIDATE_DRIFT')
                seen.add(reference);refs.append(reference);records.append(actual)
    return {'records':records,'record_refs':refs,'closure_digest':_digest(refs)}


def pinned_relation_definition_index(index, manifest, principal, *, active_snapshot=None):
    """Read the run's owner and lookup-bound definition snapshot for review."""
    from .semantic_binding_contract import ConceptLookupClosure, semantic_digest
    from .semantic_profile_loader import LoadedProfileEntry

    closure=(manifest.get('metadata_execution') or {}).get('definition_closure_digest')
    expected_ref='definition-index:'+str(closure)
    raw_lookup=index.get('lookup')
    try:
        lookup=ConceptLookupClosure.model_validate(raw_lookup)
        items=[LoadedProfileEntry.model_validate(item) for item in index.get('items',())]
    except (TypeError,ValueError) as error:
        raise BulkMigrationPolicyError('RELATION_DEFINITION_INDEX_INVALID') from error
    if (not closure or index.get('employee_id')!=principal
        or index.get('index_ref')!=expected_ref
        or semantic_digest(lookup)!=closure
        or index.get('digest')!=manifest.get('active_concept_index_digest')
        or lookup.index_revision_digest!=index.get('digest')
        or lookup.principal_id!=principal
        or lookup.policy_digest!=manifest.get('acl_policy_digest')
        or lookup.status!='complete'
        or lookup.concept_revision_digests!=tuple(item.revision_digest for item in items)
        or len({item.entry_id for item in items})!=len(items)
        or any(item.category!='domain' for item in items)):
        raise BulkMigrationPolicyError('RELATION_DEFINITION_INDEX_STALE')
    content_verified=(active_snapshot is not None
        and active_snapshot.lookup==lookup
        and tuple(active_snapshot.entries)==tuple(items))
    return {item.entry_id:item.model_dump(mode='json') for item in items},lookup,content_verified


def relation_mapping_dependencies(children, *, definition_index=None):
    """Project cross-shard RelationType key dependencies from verified children.

    This is a review aid, not a RelationshipContract or a quality/approval
    receipt. The caller must obtain ``children`` through semantic_candidate_closure.
    """
    records=children['records']
    refs=children['record_refs']
    if len(records)!=len(refs) or _digest(refs)!=children['closure_digest']:
        raise BulkMigrationPolicyError('RELATION_DEPENDENCY_CHILD_CLOSURE_INVALID')
    by_property={}
    for record,record_ref in zip(records,refs):
        if record.get('candidate_profile')!='data-mapping':
            continue
        payload=record.get('profile_payload') or {}
        if not isinstance(payload,dict):
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_MAPPING_PAYLOAD_INVALID')
        physical=payload.get('physical') or {}
        if not isinstance(physical,dict):
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_MAPPING_PAYLOAD_INVALID')
        logical_ref=payload.get('logical_property_ref')
        if (not isinstance(logical_ref,str) or not logical_ref
            or not isinstance(physical.get('mapping_ref'),str) or not physical['mapping_ref']):
            continue
        raw_evidence=payload.get('evidence_span_refs')
        evidence=(list(raw_evidence) if isinstance(raw_evidence,(list,tuple))
            and all(isinstance(item,str) and item for item in raw_evidence) else [])
        by_property.setdefault(logical_ref,[]).append({
            'logical_property_ref':logical_ref,
            'owner_ref':payload.get('owner_ref'),
            'mapping_ref':physical['mapping_ref'],
            'physical_revision_digest':physical.get('revision_digest'),
            'source_id':physical.get('source_id'),
            'table':physical.get('table'),'column':physical.get('column'),
            'evidence_span_refs':evidence,
            'shard_id':record.get('shard_id'),
            'candidate_record_ref':record_ref,
        })
    dependencies=[]
    definitions,lookup,content_verified=(definition_index if definition_index is not None
        else ({},None,False))
    for record,record_ref in zip(records,refs):
        if 'candidate_profile' in record:
            continue
        logical=record.get('logical_definition') or {}
        if not isinstance(logical,dict):
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_LOGICAL_PAYLOAD_INVALID')
        proposed=record.get('proposed_concept') or {}
        if not isinstance(proposed,dict):
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_PROPOSED_CONCEPT_INVALID')
        if logical and proposed:
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_DEFINITION_ORIGIN_AMBIGUOUS')
        existing=None
        if not logical and proposed.get('ref'):
            existing=definitions.get(proposed['ref'])
            if existing and existing['payload'].get('kind')=='RelationType':
                logical=existing['payload']
        if logical.get('kind')!='RelationType':
            continue
        raw_left=logical.get('left_property_refs')
        raw_right=logical.get('right_property_refs')
        left=tuple(raw_left) if isinstance(raw_left,(list,tuple)) and all(
            isinstance(item,str) for item in raw_left) else ()
        right=tuple(raw_right) if isinstance(raw_right,(list,tuple)) and all(
            isinstance(item,str) for item in raw_right) else ()
        reasons=[]
        if existing:
            if (existing['revision_digest']!=proposed.get('revision_digest')
                or existing['entry_id']!=logical.get('id') or lookup is None
                or record.get('semantic_validation_status') not in {'not_run','VALIDATED'}):
                reasons.append('RELATION_EXISTING_DEFINITION_UNVERIFIED')
            if not content_verified:
                reasons.append('RELATION_EXISTING_DEFINITION_CONTENT_UNVERIFIED')
        elif (record.get('logical_contract_status')!='draft_valid'
              or record.get('logical_definition_digest')!=_digest(logical)
              or not record.get('logical_evidence_uses')):
            reasons.append('RELATION_LOGICAL_DRAFT_UNVERIFIED')
        if (not logical.get('id') or not logical.get('left_endpoint_ref')
            or not logical.get('right_endpoint_ref') or not left or len(left)!=len(right)
            or len(set(left))!=len(left) or len(set(right))!=len(right)):
            reasons.append('RELATION_LOGICAL_KEY_CONTRACT_INVALID')
        sides={}
        for side,keys,owner in (
            ('left',left,logical.get('left_endpoint_ref')),
            ('right',right,logical.get('right_endpoint_ref')),
        ):
            selected=[]
            for key in keys:
                matches=by_property.get(key,())
                if not matches:
                    reasons.append('RELATION_MAPPING_PROPERTY_MISSING')
                elif len(matches)!=1:
                    reasons.append('RELATION_MAPPING_PROPERTY_AMBIGUOUS')
                elif matches[0]['owner_ref']!=owner:
                    reasons.append('RELATION_MAPPING_PROPERTY_OWNER_MISMATCH')
                elif not all(matches[0].get(field) for field in (
                    'physical_revision_digest','source_id','table','column','shard_id')):
                    reasons.append('RELATION_MAPPING_PHYSICAL_CLOSURE_INCOMPLETE')
                else:
                    selected.append(matches[0])
            sides[side]=selected
        sources={item['source_id'] for side in sides.values() for item in side}
        if len(sources)>1:
            reasons.append('RELATION_MAPPING_CROSS_SOURCE')
        source=record.get('source_record') or {}
        if not isinstance(source,dict):
            raise BulkMigrationPolicyError('RELATION_DEPENDENCY_SOURCE_PAYLOAD_INVALID')
        if existing and lookup.namespace!=source.get('namespace'):
            reasons.append('RELATION_EXISTING_DEFINITION_NAMESPACE_MISMATCH')
        evidence_refs=sorted({item['span_ref'] for item in
            record.get('field_evidence') or () if isinstance(item,dict)
            and isinstance(item.get('span_ref'),str) and item['span_ref']})
        if (not (existing or record.get('logical_definition_digest')) or not source.get('artifact_ref')
            or not source.get('source_revision_digest') or not source.get('snapshot_digest')
            or not evidence_refs or any(not item['evidence_span_refs']
                for side in sides.values() for item in side)):
            reasons.append('RELATION_SOURCE_EVIDENCE_INCOMPLETE')
        body={
            'contract_version':'boi/run-relation-mapping-dependency@1',
            'relation_ref':logical.get('id'),
            'relation_candidate_digest':record.get('candidate_digest'),
            'relation_candidate_record_ref':record_ref,
            'logical_definition_digest':_digest(logical) if existing else record.get('logical_definition_digest'),
            'definition_origin':'active_index_reuse' if existing else 'new_candidate',
            'definition_revision_digest':existing['revision_digest'] if existing else None,
            'definition_index_digest':lookup.index_revision_digest if existing else None,
            'source_artifact_ref':source.get('artifact_ref'),
            'source_revision_digest':source.get('source_revision_digest'),
            'source_snapshot_digest':source.get('snapshot_digest'),
            'relation_evidence_span_refs':evidence_refs,
            'left_endpoint_ref':logical.get('left_endpoint_ref'),
            'right_endpoint_ref':logical.get('right_endpoint_ref'),
            'left_logical_key_refs':list(left),'right_logical_key_refs':list(right),
            'left_key_mappings':sides['left'],'right_key_mappings':sides['right'],
            'run_candidate_closure_digest':children['closure_digest'],
            'status':'candidate_mapping_closed' if not reasons else 'mapping_incomplete',
            'reason_codes':list(dict.fromkeys(reasons)),
            'execution_policy_status':'not_authored',
            'relationship_quality_status':'not_run',
            'authority':'candidate_only',
            'production_changed':False,'active_transition':False,
        }
        dependencies.append({**body,'dependency_digest':_digest(body)})
    return sorted(dependencies,key=lambda item:(str(item['relation_ref']),item['relation_candidate_record_ref']))


def required_stage_evidence(run, manifest, repository):
    if _digest(manifest) != run.manifest_digest:
        raise BulkMigrationPolicyError('MIGRATION_MANIFEST_DRIFT')
    contracts = {item.contract_id:item for item in (
        P0_B3_PIPELINE_V2, SEMANTIC_METADATA_PIPELINE_V1, NORTH_STAR_ETCH_PIPELINE_V1,
        INTAKE_CHECKPOINT_PIPELINE_V1)}
    contract_id = str(manifest.get('pipeline_contract_id') or '')
    contract = contracts.get(contract_id)
    # Historical custom pipelines retain their declared closure, not an empty
    # caller-provided override. Unknown new contracts cannot qualify.
    required = contract.required_stage_ids if contract else tuple(manifest.get('requested_skill_stages') or ())
    optional = contract.optional_stage_ids if contract else ()
    checks = []
    if manifest.get('metadata_execution'):
        try:
            children=semantic_candidate_closure(run,manifest,repository)
            checks.append({'check_id':'derived-candidate-closure','status':'pass',
                'evidence_digest':children['closure_digest']})
        except BulkMigrationPolicyError as error:
            checks.append({'check_id':'derived-candidate-closure','status':'fail','reason_code':str(error)})
    if not contract and contract_id != 'boi/legacy-bulk-pipeline@0.1.0':
        checks.append({'check_id':'pipeline-contract', 'status':'fail',
                       'reason_code':'REQUIRED_PIPELINE_CONTRACT_UNKNOWN'})
    if not required:
        checks.append({'check_id':'pipeline-contract', 'status':'fail',
                       'reason_code':'REQUIRED_STAGE_CONTRACT_EMPTY'})
    stage_digests = {}
    missing = []
    base_current = True
    if run.service_stage_receipt_refs:
        for shard in run.shards:
            for stage in manifest.get('requested_skill_stages') or ():
                ref = shard.stage_receipt_refs.get(stage)
                receipt = repository.get_stage_receipt(ref) if ref else None
                body = {k:v for k,v in (receipt or {}).items() if k not in {'updated_at','stage_receipt_digest'}}
                if (not receipt or receipt.get('stage_receipt_digest') != ref or _digest(body) != ref
                    or receipt.get('status') != 'pass' or shard.stage_states.get(stage) != 'pass'
                    or receipt.get('run_id') != run.run_id or receipt.get('shard_id') != shard.shard_id
                    or receipt.get('employee_id') != run.principal or receipt.get('skill_id') != stage
                    or receipt.get('attempt_digest') != shard.last_attempt_digest):
                    base_current = False
    for stage in required:
        evidence = []
        statuses = []
        outputs = []
        service_ref = run.service_stage_receipt_refs.get(stage)
        if service_ref:
            receipt = repository.get_service_stage_receipt(service_ref) or {}
            body = {k:v for k,v in receipt.items() if k not in {'updated_at','stage_receipt_digest'}}
            valid = (base_current and receipt.get('stage_receipt_digest') == service_ref == _digest(body)
                and receipt.get('contract_version') == 'boi/service-stage-receipt@0.2.0'
                and receipt.get('run_id') == run.run_id and receipt.get('employee_id') == run.principal
                and receipt.get('manifest_digest') == run.manifest_digest
                and receipt.get('pipeline_contract_id') == contract_id and receipt.get('stage_id') == stage
                and receipt.get('status') == 'pass' and receipt.get('executor_code_digest')
                and receipt.get('base_stage_receipt_refs') == {s.shard_id:dict(s.stage_receipt_refs) for s in run.shards}
                and receipt.get('output_digest') == receipt.get('evidence_digest') == _digest(receipt.get('output'))
                and not receipt.get('production_changed') and not receipt.get('active_transition'))
            statuses.append('pass' if valid else 'fail')
            if valid:
                evidence.append(service_ref)
                outputs.append({'run_id':run.run_id,'output_digest':receipt['output_digest']})
        for shard in (() if service_ref else sorted(run.shards, key=lambda item:item.shard_id)):
            ref = shard.stage_receipt_refs.get(stage)
            receipt = repository.get_stage_receipt(ref) if ref else None
            if not receipt:
                statuses.append('not_run')
                continue
            body = {key:value for key,value in receipt.items() if key not in {'updated_at','stage_receipt_digest'}}
            valid = (
                receipt.get('stage_receipt_digest') == ref == _digest(body)
                and stage_receipt_contract_valid(receipt)
                and receipt.get('run_id') == run.run_id
                and receipt.get('shard_id') == shard.shard_id
                and receipt.get('employee_id') == run.principal
                and receipt.get('skill_id') == stage
                and receipt.get('attempt_digest') == shard.last_attempt_digest
                and receipt.get('status') == shard.stage_states.get(stage)
                and not receipt.get('production_changed') and not receipt.get('active_transition'))
            if not valid:
                statuses.append('fail')
                continue
            evidence.append(ref)
            status = str(receipt.get('status') or 'not_run')
            if status == 'pass' and any(
                not receipt.get(key) for key in ('input_digest','output_digest','evidence_digest')):
                status = 'not_run'
            statuses.append(status)
            outputs.append({'shard_id':shard.shard_id,'output_digest':receipt.get('output_digest')})
        status = next((value for value in ('fail','blocked','partial','flag','not_run','skip')
                       if value in statuses), 'pass' if statuses and all(value=='pass' for value in statuses) else 'not_run')
        closure = {'manifest_digest':run.manifest_digest, 'pipeline_contract_id':contract_id,
                   'profile_revisions':manifest.get('profile_revisions'),
                   'schema_snapshot_digest':manifest.get('schema_snapshot_digest'),
                   'catalog_snapshot_digest':manifest.get('catalog_snapshot_digest'),
                   'acl_policy_digest':manifest.get('acl_policy_digest'),
                   'evaluator_code_digests':manifest.get('evaluator_code_digests'),
                   'stage_id':stage, 'stage_receipt_refs':evidence, 'status':status}
        checks.append({'check_id':'required-stage:'+stage,'stage_id':stage,'status':status,
                       'reason_code':'EXACT_STAGE_CLOSURE' if status=='pass' else 'REQUIRED_STAGE_CLOSURE_INCOMPLETE',
                       'evidence_digest':_digest(closure)})
        if status != 'pass':
            missing.append(stage)
        elif len(outputs) == 1:
            stage_digests[stage] = outputs[0]['output_digest']
        else:
            stage_digests[stage] = _digest(outputs)
    if run.control_state != 'completed' or run.attention_refs:
        checks.append({'check_id':'run-ready','status':'partial',
                       'reason_code':'RUN_NOT_COMPLETE_OR_ATTENTION_PRESENT',
                       'evidence_digest':_digest({'run_digest':run.semantic_digest,'attention_refs':run.attention_refs})})
    return contract_id, tuple(required), tuple(optional), tuple(missing), stage_digests, checks


def select_current_receipt(run, manifest, repository, receipts):
    """One shared selector for UI, MCP and service continuation; history retained."""
    contract, required, _, missing, digests, checks = required_stage_evidence(run, manifest, repository)
    matches = []
    for receipt in receipts:
        if (receipt.get('run_id') != run.run_id or receipt.get('employee_id') != run.principal
            or receipt.get('pipeline_contract_id') != contract
            or receipt.get('receipt_version') != 'boi/bulk-migration-receipt@0.2.0'):
            continue
        body = {k:v for k,v in receipt.items() if k not in {'updated_at','receipt_digest','run_id','employee_id'}}
        if _digest(body) != receipt.get('receipt_digest'):
            continue
        if (tuple(receipt.get('required_stage_ids') or ()) != required
            or tuple(receipt.get('missing_required_stage_ids') or ()) != missing
            or receipt.get('stage_digests') != digests
            or receipt.get('attention_digest') != _digest(run.attention_refs)):
            continue
        actual_required = [item for item in checks if item.get('stage_id') in required]
        recorded_required = [item for item in receipt.get('checks',()) if item.get('stage_id') in required]
        if actual_required != recorded_required:
            continue
        if manifest.get('metadata_execution'):
            if ([item for item in checks if item.get('check_id')=='derived-candidate-closure'] !=
                [item for item in receipt.get('checks',()) if item.get('check_id')=='derived-candidate-closure']):
                continue
        if receipt.get('run_digest') != run.semantic_digest:
            # Review/proposal state may change, not the qualified execution closure.
            if run.candidate_state not in {'approval_ready','approved','release_proposed'} or receipt.get('status')!='pass':
                continue
        matches.append(receipt)
    return matches[0] if len(matches)==1 else {}
