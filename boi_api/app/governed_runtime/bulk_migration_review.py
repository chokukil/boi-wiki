"""Shared evidence-bound candidate review; never a Release or activation service."""
from .bulk_migration import AgentV2StoreBulkMigrationRepository, BulkMigrationPolicyError, _digest
from .bulk_migration_qualification import select_current_receipt, semantic_candidate_closure
from .bulk_migration_transaction import MigrationWriteSet
from typing import Literal
from .semantic_binding_contract import FrozenContract, Ref, Digest


class SemanticInterpretationRequest(FrozenContract):
    """One snapshot-bound atomic shard, not a list of caller-selected objects."""
    review_mode: Literal['semantic_interpretation']
    run_id: Ref
    shard_id: Ref
    expected_preview_digest: Digest
    disposition: Literal['accept_interpretation', 'reject_interpretation', 'request_changes']


def interpretation_review_key(principal, run_id, shard_id, preview_digest):
    return 'interpretation-current:' + _digest([principal,run_id,shard_id,preview_digest])


def recorded_interpretation_review(repository, *, principal, run_id, shard_id, preview_digest):
    """Display the recorded review of this exact preview; grants no runtime authority."""
    key=interpretation_review_key(principal,run_id,shard_id,preview_digest)
    current=repository.store.get('bulk_migration_approvals',key)
    if current is None:
        return None
    receipt=repository.store.get('bulk_migration_approvals',current.get('receipt_ref',''))
    body={k:v for k,v in (receipt or {}).items() if k not in {'updated_at','receipt_digest','employee_id','ui_url'}}
    closure=body.get('closure') or {}
    if (not receipt or current.get('employee_id')!=principal or receipt.get('employee_id')!=principal
        or body.get('principal')!=principal or body.get('contract_version')!='boi/semantic-interpretation-receipt@1'
        or _digest(body)!=receipt.get('receipt_digest') or current.get('receipt_digest')!=receipt.get('receipt_digest')
        or current.get('plan_digest')!=body.get('plan_digest')
        or (closure.get('run_id'),closure.get('shard_id'),closure.get('preview_digest'))!=(run_id,shard_id,preview_digest)):
        raise BulkMigrationPolicyError('INTERPRETATION_RECORDED_REVIEW_DRIFT')
    return receipt


def _interpretation_context(repository, principal, request, runtime_check):
    run = repository.get(request.run_id)
    if not run or run.principal != principal:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_ACCESS_DENIED')
    shard = next((item for item in run.shards if item.shard_id == request.shard_id), None)
    if (shard is None or shard.state not in {'completed', 'failed'}
        or shard.stage_states.get('domain-ontology-draft') != 'pass'
        or run.control_state == 'cancelled'
        or run.candidate_state in {'approved', 'release_proposed'}):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_SHARD_NOT_AVAILABLE')
    manifest = repository.manifest_payload(run)
    if _digest(manifest) != run.manifest_digest or not manifest.get('metadata_execution'):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_MANIFEST_INVALID')
    project = repository.store.get('bulk_migration_projects', run.project_id)
    if not project or project.get('employee_id') != principal:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_ACCESS_DENIED')
    preview = repository.store.get('bulk_migration_candidate_previews', 'preview:' + run.run_id)
    body = {k:v for k,v in (preview or {}).items() if k not in {'updated_at','employee_id','preview_id','preview_digest'}}
    if (not preview or preview.get('employee_id') != principal
        or preview.get('preview_digest') != request.expected_preview_digest
        or _digest(body) != request.expected_preview_digest
        or preview.get('manifest_digest') != run.manifest_digest
        or preview.get('stage_receipt_refs', {}).get(shard.shard_id) != dict(shard.stage_receipt_refs)):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_PREVIEW_STALE')
    # Review is bounded to this shard. Other shards are not implicitly reviewed.
    from dataclasses import replace
    selected_run = replace(run, shards=(shard,))
    children = semantic_candidate_closure(selected_run, manifest, repository)
    domain = [item for item in children['records'] if 'candidate_profile' not in item]
    if not domain or len(domain) > 100:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_CANDIDATE_BOUND')
    if not set(children['record_refs']) <= set(preview.get('derived_candidate_refs', [])):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_CHILD_CLOSURE_STALE')
    if request.disposition == 'accept_interpretation':
        from .domain_profile_v04 import validate_domain_profile_entry
        for item in domain:
            logical = item.get('logical_definition')
            if (not logical or item.get('logical_contract_status') != 'draft_valid'
                or item.get('logical_definition_digest') != _digest(logical)
                or not item.get('logical_evidence_uses')):
                raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_LOGICAL_CONTRACT_REQUIRED')
            validate_domain_profile_entry(logical)
    runtime = runtime_check(manifest, domain)
    return run, {
        'run_id': run.run_id, 'run_digest': run.semantic_digest,
        'manifest_digest': run.manifest_digest, 'shard_id': shard.shard_id,
        'preview_digest': request.expected_preview_digest,
        'candidate_record_refs': children['record_refs'],
        'candidate_closure_digest': children['closure_digest'],
        'domain_candidate_digests': [item['candidate_digest'] for item in domain],
        'field_support_digest': _digest([item.get('logical_evidence_uses', []) for item in domain]),
        'runtime_closure': runtime,
    }


def prepare_interpretation_review(repository, *, principal, request, runtime_check):
    """An Attention review plan, never final migration approval or execution."""
    request = SemanticInterpretationRequest.model_validate(request)
    buffer = MigrationWriteSet(repository.store)
    writer = AgentV2StoreBulkMigrationRepository(buffer)
    run, closure = _interpretation_context(writer, principal, request, runtime_check)
    body = {'contract_version':'boi/semantic-interpretation-plan@1', 'principal':principal,
        'request':request.model_dump(mode='json'), 'closure':closure,
        'authority':'meaning_interpretation_only', 'status':'PENDING_USER_CONFIRMATION',
        'final_migration_approved':False, 'production_changed':False, 'active_transition':False}
    digest = _digest(body)
    value = {**body, 'plan_digest':digest, 'employee_id':principal, 'ui_url':run.ui_url}
    key = 'interpretation-plan:' + digest
    prior = buffer.get('bulk_migration_approvals', key)
    if prior and {k:v for k,v in prior.items() if k != 'updated_at'} != value:
        raise BulkMigrationPolicyError('INTERPRETATION_PLAN_INTEGRITY_FAILURE')
    if not prior:
        buffer.put('bulk_migration_approvals', key, value)
    fences = tuple(key for key,value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_CLOSURE_CONFLICT')
    return value


def _reviewed_sibling_dependencies(repository, *, principal, run, shard, manifest,
                                   runtime_check):
    """Supply only still-current, separately reviewed sibling definitions.

    A target shard's review never reviews another shard. A prior sibling can
    satisfy a logical reference only after its own reviewed match stage passed;
    source, plan, receipt and immutable stage are checked again on this retry.
    """
    from dataclasses import replace
    dependencies=[]
    for sibling in run.shards:
        if sibling.shard_id==shard.shard_id or sibling.state not in {'completed','failed'}:
            continue
        match_ref=sibling.stage_receipt_refs.get('existing-concept-match')
        if not match_ref or sibling.stage_states.get('existing-concept-match')!='pass':
            continue
        match=repository.get_stage_receipt(match_ref) or {}
        body={key:value for key,value in match.items()
            if key not in {'updated_at','stage_receipt_digest'}}
        output=match.get('output') or {}
        if (match.get('stage_receipt_digest')!=match_ref or _digest(body)!=match_ref
            or match.get('employee_id')!=principal or match.get('run_id')!=run.run_id
            or match.get('shard_id')!=sibling.shard_id
            or match.get('skill_id')!='existing-concept-match'
            or match.get('attempt_digest')!=sibling.last_attempt_digest
            or match.get('output_digest')!=_digest(output)):
            raise BulkMigrationPolicyError('REVIEWED_DEPENDENCY_MATCH_STAGE_STALE')
        matches=output.get('match_candidates') or ()
        if not matches or any(item.get('decision')!='reviewed_new_definition'
            or item.get('reviewed_contract_satisfied') is not True for item in matches):
            continue
        refs=output.get('interpretation_receipt_refs') or ()
        own_digests={item.get('interpretation_receipt_digest') for item in matches}
        receipts=[(ref,repository.store.get('bulk_migration_approvals',ref) or {})
            for ref in refs]
        own=[(ref,item) for ref,item in receipts
            if item.get('receipt_digest') in own_digests]
        if (len(own_digests)!=1 or len(own)!=1
            or set(output.get('interpretation_receipt_digests') or ())!=set(
                item.get('receipt_digest') for _,item in receipts)):
            raise BulkMigrationPolicyError('REVIEWED_DEPENDENCY_RECEIPT_MISSING')
        own_ref,receipt=own[0]
        scope=receipt.get('closure') or {}
        recorded=recorded_interpretation_review(repository,principal=principal,
            run_id=run.run_id,shard_id=sibling.shard_id,
            preview_digest=scope.get('preview_digest',''))
        plan=repository.store.get('plans',
            'interpretation_'+str(receipt.get('plan_digest','')).removeprefix('sha256:')) or {}
        sibling_closure=semantic_candidate_closure(
            replace(run,shards=(sibling,)),manifest,repository)
        domain=[item for item in sibling_closure['records'] if 'candidate_profile' not in item]
        domain_refs=[ref for ref,item in zip(sibling_closure['record_refs'],
            sibling_closure['records']) if 'candidate_profile' not in item]
        if (recorded!=receipt or receipt.get('disposition')!='accept_interpretation'
            or receipt.get('principal')!=principal or scope.get('manifest_digest')!=run.manifest_digest
            or scope.get('candidate_record_refs')!=domain_refs
            or scope.get('domain_candidate_digests')!=[item['candidate_digest'] for item in domain]
            or scope.get('field_support_digest')!=_digest([
                item.get('logical_evidence_uses',[]) for item in domain])
            or scope.get('runtime_closure')!=runtime_check(manifest,domain)
            or plan.get('status')!='confirmed' or plan.get('employee_id')!=principal
            or (plan.get('confirmation_result') or {}).get('interpretation_receipt',{}).get('receipt_digest')
                !=receipt.get('receipt_digest')
            or sorted(item.get('candidate_digest') for item in matches)!=sorted(
                item['candidate_digest'] for item in domain)
            or any(item.get('interpretation_receipt_digest')!=receipt.get('receipt_digest')
                for item in matches)):
            raise BulkMigrationPolicyError('REVIEWED_DEPENDENCY_CLOSURE_STALE')
        dependencies.extend({**{key:value for key,value in item.items()
            if key not in {'employee_id','run_id','shard_id','state','active_transition','updated_at'}},
            'review_receipt_digest':receipt['receipt_digest'],
            'review_receipt_ref':own_ref}
            for item in domain)
    return dependencies


def resolve_reviewed_shard(repository, *, principal, run, shard, runtime_check):
    """Forward opt-in: immutable reviewed meaning may be reused on exact retry.

    No active-definition snapshot is extended here. Historical run/control state
    remains in the review receipt; current source, definitions and candidates
    must match it independently before an exploratory consumer can use them.
    """
    manifest=repository.manifest_payload(run)
    if manifest.get('metadata_execution',{}).get('reviewed_definition_policy')!='boi/reviewed-definitions@1':
        return None
    if shard.state!='queued' or shard.retry_count!=1:
        return None
    preview=repository.store.get('bulk_migration_candidate_previews','preview:'+run.run_id)
    if not preview:
        return None
    receipt=recorded_interpretation_review(repository,principal=principal,run_id=run.run_id,
        shard_id=shard.shard_id,preview_digest=preview.get('preview_digest',''))
    if receipt is None:
        return None
    if receipt['disposition']!='accept_interpretation':
        raise BulkMigrationPolicyError('REVIEWED_DEFINITION_NOT_ACCEPTED')
    if run.principal!=principal or run.control_state=='cancelled':
        raise BulkMigrationPolicyError('REVIEWED_DEFINITION_ACCESS_DENIED')
    plan=repository.store.get('plans','interpretation_'+receipt['plan_digest'].removeprefix('sha256:')) or {}
    if (plan.get('status')!='confirmed' or plan.get('employee_id')!=principal
        or plan.get('confirmation_result',{}).get('interpretation_receipt',{}).get('receipt_digest')!=receipt['receipt_digest']):
        raise BulkMigrationPolicyError('REVIEWED_DEFINITION_CONFIRMATION_STALE')
    body={k:v for k,v in preview.items() if k not in {'updated_at','employee_id','preview_id','preview_digest'}}
    if (_digest(body)!=preview['preview_digest'] or preview.get('employee_id')!=principal
        or preview.get('manifest_digest')!=run.manifest_digest
        or preview.get('stage_receipt_refs',{}).get(shard.shard_id)!=dict(shard.stage_receipt_refs)):
        raise BulkMigrationPolicyError('REVIEWED_DEFINITION_PREVIEW_STALE')
    from dataclasses import replace
    closure=semantic_candidate_closure(replace(run,shards=(shard,)),manifest,repository)
    domain=[item for item in closure['records'] if 'candidate_profile' not in item]
    expected=receipt['closure']
    if (expected['manifest_digest']!=run.manifest_digest
        or expected['candidate_record_refs']!=closure['record_refs']
        or expected['candidate_closure_digest']!=closure['closure_digest']
        or expected['domain_candidate_digests']!=[item['candidate_digest'] for item in domain]
        or expected['field_support_digest']!=_digest([item.get('logical_evidence_uses',[]) for item in domain])
        or expected['runtime_closure']!=runtime_check(manifest,domain)):
        raise BulkMigrationPolicyError('REVIEWED_DEFINITION_SOURCE_CLOSURE_STALE')
    retained={}
    stage_ref=shard.stage_receipt_refs.get('domain-ontology-draft')
    if stage_ref:
        stage=repository.get_stage_receipt(stage_ref) or {}
        unsigned={k:v for k,v in stage.items() if k not in {'updated_at','stage_receipt_digest'}}
        if (_digest(unsigned)!=stage_ref or stage.get('stage_receipt_digest')!=stage_ref
            or stage.get('employee_id')!=principal or stage.get('run_id')!=run.run_id
            or stage.get('shard_id')!=shard.shard_id or stage.get('skill_id')!='domain-ontology-draft'
            or stage.get('output_digest')!=_digest(stage.get('output'))):
            raise BulkMigrationPolicyError('REVIEWED_DEFINITION_SOURCE_STAGE_STALE')
        if 'source_meaning_results' in (stage.get('output') or {}):
            retained={'source_stage_receipt_ref':stage_ref,
                'source_meaning_results':stage['output']['source_meaning_results']}
    dependencies=_reviewed_sibling_dependencies(repository,principal=principal,run=run,
        shard=shard,manifest=manifest,runtime_check=runtime_check)
    return {'contract_version':'boi/reviewed-shard-input@3' if dependencies
        else 'boi/reviewed-shard-input@2' if retained else 'boi/reviewed-shard-input@1','receipt':receipt,
        'retry_checkpoint_digest':shard.last_checkpoint_digest,
        **retained,
        **({'dependency_candidates':dependencies} if dependencies else {}),
        'candidates':[{key:value for key,value in item.items()
            if key not in {'employee_id','run_id','shard_id','state','active_transition','updated_at'}} for item in domain]}


def confirm_interpretation_review(repository, *, principal, plan_digest, reason, runtime_check, confirmation_plan):
    """Write exact human review evidence without altering candidates or run state.

    The shared plan projection and receipt commit together. Its exact current
    state fences cancellation/revision races, including on response replay.
    """
    if not reason.strip():
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_REASON_REQUIRED')
    buffer = MigrationWriteSet(repository.store)
    writer = AgentV2StoreBulkMigrationRepository(buffer)
    projection_id = 'interpretation_' + plan_digest.removeprefix('sha256:')
    projection = buffer.get('plans', projection_id)
    if (not projection or projection != confirmation_plan
        or projection.get('employee_id') != principal
        or projection.get('status') not in {'draft', 'confirmed'}
        or projection.get('domain_operation') != 'ontology.migration.interpretation-review'
        or projection.get('domain_payload', {}).get('interpretation_plan_digest') != plan_digest):
        raise BulkMigrationPolicyError('INTERPRETATION_CONFIRMATION_PLAN_STALE')
    plan = buffer.get('bulk_migration_approvals', 'interpretation-plan:' + plan_digest)
    if not plan or plan.get('employee_id') != principal or plan.get('principal') != principal:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_ACCESS_DENIED')
    body = {k:v for k,v in plan.items() if k not in {'updated_at','plan_digest','employee_id','ui_url'}}
    if _digest(body) != plan_digest or body.get('contract_version') != 'boi/semantic-interpretation-plan@1':
        raise BulkMigrationPolicyError('INTERPRETATION_PLAN_INTEGRITY_FAILURE')
    request = SemanticInterpretationRequest.model_validate(plan['request'])
    run, closure = _interpretation_context(writer, principal, request, runtime_check)
    if closure != plan['closure']:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_CLOSURE_STALE')
    receipt_key = 'interpretation-receipt:' + plan_digest
    current_key=interpretation_review_key(principal,run.run_id,request.shard_id,request.expected_preview_digest)
    current=recorded_interpretation_review(writer,principal=principal,run_id=run.run_id,
        shard_id=request.shard_id,preview_digest=request.expected_preview_digest)
    if current and current['plan_digest']!=plan_digest:
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_ALREADY_RECORDED')
    prior = buffer.get('bulk_migration_approvals', receipt_key)
    receipt_body = {'contract_version':'boi/semantic-interpretation-receipt@1',
        'principal':principal, 'plan_digest':plan_digest, 'closure':closure,
        'disposition':request.disposition, 'authority':'meaning_interpretation_only',
        'reason_digest':_digest(reason.strip()), 'status':'RECORDED',
        'semantic_truth_verified':False, 'mapping_qualified':False,
        'final_migration_approved':False, 'production_changed':False, 'active_transition':False}
    if prior:
        saved_body = {k:v for k,v in prior.items() if k not in {'updated_at','receipt_digest','employee_id','ui_url'}}
        # The first human reason is immutable; an idempotent retry need not echo it.
        receipt_body['reason_digest'] = saved_body.get('reason_digest')
        if saved_body != receipt_body or _digest(saved_body) != prior.get('receipt_digest'):
            raise BulkMigrationPolicyError('INTERPRETATION_RECEIPT_INTEGRITY_FAILURE')
        result = {k:v for k,v in prior.items() if k != 'updated_at'}
    else:
        result = {**receipt_body, 'receipt_digest':_digest(receipt_body),
            'employee_id':principal, 'ui_url':run.ui_url}
        buffer.put('bulk_migration_approvals', receipt_key, result)
    buffer.put('bulk_migration_approvals',current_key,{
        'contract_version':'boi/semantic-interpretation-current@1','employee_id':principal,
        'plan_digest':plan_digest,'receipt_ref':receipt_key,'receipt_digest':result['receipt_digest']})
    response = {'status':'confirmed', 'plan_id':projection_id,
        'ui_url':result['ui_url'], 'run_id':result['closure']['run_id'],
        'interpretation_receipt':result, 'production_changed':False, 'active_transition':False}
    buffer.put('plans', projection_id, {**projection, 'status':'confirmed',
        'confirmation_result':response, 'production_changed':False})
    fences = tuple(key for key,value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('INTERPRETATION_REVIEW_CLOSURE_CONFLICT')
    return response


def semantic_candidate_preview_body(repository, run):
    """Derive the view from exact children/stages, never from its own hash."""
    manifest=repository.manifest_payload(run)
    children=semantic_candidate_closure(run,manifest,repository)
    from .bulk_migration_qualification import required_stage_evidence
    _,_,_,_,stages,_=required_stage_evidence(run,manifest,repository)
    matches=[];mappings=[];queries=[];mapping_checks=[];object_quality=[];quality_audits=[];value_quality=[]
    for shard in run.shards:
        def exact_stage(stage):
            ref=shard.stage_receipt_refs.get(stage)
            if not ref:return None
            receipt=repository.get_stage_receipt(ref)
            if not receipt:raise BulkMigrationPolicyError('SEMANTIC_PREVIEW_STAGE_PAYLOAD_MISMATCH')
            body={k:v for k,v in receipt.items() if k not in {'updated_at','stage_receipt_digest'}}
            if (_digest(body)!=ref or receipt.get('employee_id')!=run.principal
                or receipt.get('run_id')!=run.run_id or receipt.get('shard_id')!=shard.shard_id
                or receipt.get('skill_id')!=stage or receipt.get('attempt_digest')!=shard.last_attempt_digest
                or (receipt.get('output') is not None and receipt.get('output_digest')!=_digest(receipt['output']))):
                raise BulkMigrationPolicyError('SEMANTIC_PREVIEW_STAGE_PAYLOAD_MISMATCH')
            return receipt
        receipt=exact_stage('existing-concept-match')
        matches.extend(((receipt or {}).get('output') or {}).get('match_candidates',[]))
        for stage,target,field in (('physical-mapping-verify',mappings,'mapping_candidates'),
                                   ('query-contract-author',queries,'query_candidates')):
            receipt=exact_stage(stage)
            output=(receipt or {}).get('output') or {}
            target.extend(output.get(field,[]))
            if stage=='physical-mapping-verify':
                mapping_checks.extend(output.get('mapping_checks',[]))
                object_quality.extend(output.get('object_key_quality_receipts',[]))
                value_quality.extend(output.get('value_type_quality_receipts',[]))
                if output.get('quality_audit_receipt'):quality_audits.append(output['quality_audit_receipt'])
    domain_records=[r for r in children['records'] if 'candidate_profile' not in r]
    candidates=[{**record,'candidate_id':record['candidate_digest'],
        'kind':record['semantics']['kind'],'name':record['semantics']['definition']}
        for record in domain_records]
    body={'preview_contract_version':'boi/semantic-candidate-preview@1','run_id':run.run_id,
        'manifest_digest':run.manifest_digest,'pipeline_contract_id':manifest['pipeline_contract_id'],
        'stage_digests':stages,'stage_receipt_refs':{s.shard_id:dict(s.stage_receipt_refs) for s in run.shards},
        'derived_candidate_refs':children['record_refs'],'derived_candidate_snapshot_digest':children['closure_digest'],
        'domain_candidates':candidates,'existing_matches':matches,
        'domain_profile_digest':_digest([record['candidate_digest'] for record in domain_records]),
        'profile_validation_status':'not_run','source_artifacts':manifest['source_artifacts'],
        'metadata_execution':manifest['metadata_execution'],'status':'PROVISIONAL',
        'production_changed':False,'active_transition':False}
    if mappings or queries or mapping_checks:
        body.update(preview_contract_version='boi/semantic-candidate-preview@2',
            mapping_candidates=mappings,query_candidates=queries,mapping_checks=mapping_checks,
            mapping_candidate_digest=_digest(mappings),query_candidate_digest=_digest(queries))
    if quality_audits:
        body.update(object_key_quality_receipts=object_quality,quality_audit_receipts=quality_audits,
            quality_audit_closure_digest=_digest(quality_audits))
    if value_quality:
        body['value_type_quality_receipts']=value_quality
    return body


def persist_semantic_candidate_preview(repository, run):
    """Current shared Workbench proposal view; not review approval or Release."""
    buffer=MigrationWriteSet(repository.store)
    writer=AgentV2StoreBulkMigrationRepository(buffer)
    if writer.get(run.run_id)!=run:
        raise BulkMigrationPolicyError('PREVIEW_RUN_REVISION_CONFLICT')
    body=semantic_candidate_preview_body(writer,run)
    key='preview:'+run.run_id
    value={**body,'employee_id':run.principal,'preview_id':key,'preview_digest':_digest(body)}
    previous=buffer.get('bulk_migration_candidate_previews',key)
    if previous:
        if {k:v for k,v in previous.items() if k!='updated_at'}==value:
            return value
        buffer.put('bulk_migration_candidate_previews','history:'+previous['preview_digest'],
            {k:v for k,v in previous.items() if k!='updated_at'})
    buffer.put('bulk_migration_candidate_previews',key,value)
    fences=tuple(key for key,value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('PREVIEW_CLOSURE_REVISION_CONFLICT')
    return value


def review_context(repository,run):
    if run.control_state!='completed' or any(s.state!='completed' for s in run.shards):
        raise BulkMigrationPolicyError('REVIEW_RUN_NOT_COMPLETE')
    if not hasattr(repository, 'store'):
        raise BulkMigrationPolicyError('REVIEW_PERSISTENT_REPOSITORY_REQUIRED')
    manifest=repository.manifest_payload(run)
    store=repository.store
    project = store.get('bulk_migration_projects', run.project_id)
    if not project or project.get('employee_id') != run.principal:
        raise BulkMigrationPolicyError('REVIEW_PROJECT_ACCESS_DENIED')
    receipts=store.list('bulk_migration_receipts',employee_id=run.principal,limit=1000000)
    qualified=select_current_receipt(run,manifest,repository,receipts)
    if qualified.get('status')!='pass':
        raise BulkMigrationPolicyError('REVIEW_QUALIFICATION_REQUIRED')
    preview=store.get('bulk_migration_candidate_previews','preview:'+run.run_id)
    if not preview or preview.get('employee_id')!=run.principal:
        raise BulkMigrationPolicyError('REVIEW_PERSISTED_PREVIEW_REQUIRED')
    body={k:v for k,v in preview.items() if k not in {'updated_at','preview_id','preview_digest','employee_id'}}
    if (preview.get('preview_digest')!=_digest(body) or preview.get('run_id')!=run.run_id
        or preview.get('manifest_digest')!=run.manifest_digest
        or preview.get('pipeline_contract_id')!=manifest.get('pipeline_contract_id')
        or preview.get('stage_digests')!=qualified.get('stage_digests')):
        raise BulkMigrationPolicyError('REVIEW_PREVIEW_CLOSURE_STALE')
    candidates=[]
    for ref in run.candidate_refs:
        record=store.get('bulk_migration_candidates',ref)
        if not record or record.get('employee_id')!=run.principal or record.get('run_id')!=run.run_id:
            raise BulkMigrationPolicyError('REVIEW_CANDIDATE_CLOSURE_INVALID')
        candidates.append({k:v for k,v in record.items() if k not in {'updated_at','state'}})
    closure={'manifest_digest':run.manifest_digest,'before_hashes':manifest.get('before_hashes') or {},
        'preview_digest':preview['preview_digest'],'qualification_receipt_digest':qualified['receipt_digest'],
        'candidate_snapshot_digest':_digest(candidates),
        'execution_closure_digest':_digest({'input_digest':run.input_digest,'output_digest':run.output_digest,
            'stage_receipt_refs':{s.shard_id:dict(s.stage_receipt_refs) for s in run.shards},
            'service_stage_receipt_refs':run.service_stage_receipt_refs,'attention_refs':run.attention_refs})}
    if manifest.get('metadata_execution'):
        children=semantic_candidate_closure(run,manifest,repository)
        closure['derived_candidate_snapshot_digest']=children['closure_digest']
        if body!=semantic_candidate_preview_body(repository,run):
            raise BulkMigrationPolicyError('SEMANTIC_PREVIEW_STAGE_PAYLOAD_MISMATCH')
    return closure


def persist_review(repository, expected, updated, supplied):
    buffer = MigrationWriteSet(repository.store)
    writer = AgentV2StoreBulkMigrationRepository(buffer)
    if writer.get(expected.run_id) != expected:
        raise BulkMigrationPolicyError('REVIEW_RUN_REVISION_CONFLICT')
    closure = review_context(writer, expected)
    if supplied.get('candidate_digest') is not None:
        candidate = buffer.get('bulk_migration_candidates', expected.candidate_refs[0])
        if candidate.get('candidate_digest') != supplied['candidate_digest']:
            raise BulkMigrationPolicyError('STALE_APPROVAL:CANDIDATE_DIGEST')
    for key in ('manifest_digest', 'before_hashes', 'preview_digest'):
        if supplied[key] != closure[key]:
            raise BulkMigrationPolicyError('STALE_APPROVAL:' + key.upper())
    if (supplied.get('qualification_receipt_digest') is not None and
        supplied['qualification_receipt_digest'] != closure['qualification_receipt_digest']):
        raise BulkMigrationPolicyError('STALE_APPROVAL:QUALIFICATION_RECEIPT')
    # list() is discovery only; freeze the exact selected persisted receipt.
    receipt_key = closure['qualification_receipt_digest']
    stored_receipt = buffer.get('bulk_migration_receipts', receipt_key)
    if not stored_receipt or stored_receipt.get('receipt_digest') != receipt_key:
        raise BulkMigrationPolicyError('REVIEW_QUALIFICATION_REQUIRED')
    # Re-select with the snapshotted receipt so a discovery/read race cannot pass.
    current = select_current_receipt(expected, writer.manifest_payload(expected), writer, [stored_receipt])
    if current.get('status') != 'pass':
        raise BulkMigrationPolicyError('REVIEW_QUALIFICATION_REQUIRED')
    body = {'review_version': 'boi/bulk-review-approval@0.2.0',
            'run_id': expected.run_id, 'principal': expected.principal,
            **closure, 'candidate_state': 'approved',
            'production_changed': False, 'active_transition': False}
    approval = {**body, 'receipt_digest': _digest(body)}
    previous = writer.get_approval(expected.run_id)
    if previous and previous.get('receipt_digest') == approval['receipt_digest']:
        preserved = {k: v for k, v in previous.items() if k not in {'updated_at', 'employee_id'}}
        if preserved != approval or expected.candidate_state != 'approved':
            raise BulkMigrationPolicyError('REVIEW_APPROVAL_INTEGRITY_FAILURE')
        return approval
    if previous:
        historical = {k: v for k, v in previous.items() if k != 'updated_at'}
        history_id = 'history:' + _digest(historical)
        if not buffer.get('bulk_migration_approvals', history_id):
            buffer.put('bulk_migration_approvals', history_id, historical)
    writer.save_approval(updated, approval)
    buffer.put('bulk_migration_approvals', 'receipt:' + approval['receipt_digest'],
               {**approval, 'employee_id': expected.principal})
    writer.put(updated)
    fences = tuple(key for key, value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('REVIEW_CLOSURE_REVISION_CONFLICT')
    return approval


def current_approval(repository, run):
    approval = repository.get_approval(run.run_id)
    if not approval:
        raise BulkMigrationPolicyError('APPROVAL_NOT_FOUND')
    if (approval.get('employee_id') != run.principal or approval.get('principal') != run.principal
        or approval.get('run_id') != run.run_id):
        raise BulkMigrationPolicyError('APPROVAL_OWNER_MISMATCH')
    if run.candidate_state not in {'approved', 'release_proposed'}:
        raise BulkMigrationPolicyError('STALE_APPROVAL:CANDIDATE_STATE')
    closure = review_context(repository, run)
    body = {k:v for k,v in approval.items() if k not in {'updated_at','employee_id','receipt_digest'}}
    if (approval.get('review_version') != 'boi/bulk-review-approval@0.2.0'
        or _digest(body) != approval.get('receipt_digest')
        or any(approval.get(key) != value for key,value in closure.items())):
        raise BulkMigrationPolicyError('STALE_APPROVAL:EVIDENCE_CLOSURE')
    return approval


def persist_proposal(repository, expected, updated, approval_receipt_digest, preview_digest):
    """Record a proposal and its run state together; no production manifest."""
    buffer = MigrationWriteSet(repository.store)
    writer = AgentV2StoreBulkMigrationRepository(buffer)
    if writer.get(expected.run_id) != expected:
        raise BulkMigrationPolicyError('REVIEW_RUN_REVISION_CONFLICT')
    approval = current_approval(writer, expected)
    if (approval.get('receipt_digest') != approval_receipt_digest or
        approval.get('preview_digest') != preview_digest):
        raise BulkMigrationPolicyError('STALE_APPROVAL')
    # Freeze the qualification selected by list/discovery as an exact record.
    receipt = buffer.get('bulk_migration_receipts', approval['qualification_receipt_digest'])
    selected = select_current_receipt(expected, writer.manifest_payload(expected), writer, [receipt or {}])
    if selected.get('status') != 'pass':
        raise BulkMigrationPolicyError('REVIEW_QUALIFICATION_REQUIRED')
    candidate = buffer.get('bulk_migration_candidates', expected.candidate_refs[0])
    body = {'proposal_version':'boi/bulk-migration-release-proposal@0.2.0',
        'run_id':expected.run_id, 'manifest_digest':expected.manifest_digest,
        'candidate_digest':candidate['candidate_digest'],
        'candidate_snapshot_digest':approval['candidate_snapshot_digest'],
        'preview_digest':preview_digest,'approval_receipt_digest':approval_receipt_digest,
        'qualification_receipt_digest':approval['qualification_receipt_digest'],
        'status':'RELEASE_PROPOSAL','production_release_manifest_created':False,
        'promotion_performed':False,'production_changed':False,'active_transition':False}
    digest = _digest(body)
    value = {**body,'proposal_digest':digest,'receipt_digest':digest,'employee_id':expected.principal}
    old = buffer.get('bulk_migration_release_proposals', digest)
    if old:
        if {k:v for k,v in old.items() if k!='updated_at'} != value:
            raise BulkMigrationPolicyError('REVIEW_PROPOSAL_INTEGRITY_FAILURE')
        if expected.candidate_state != 'release_proposed':
            raise BulkMigrationPolicyError('REVIEW_PROPOSAL_RUN_STATE_DRIFT')
        return value
    buffer.put('bulk_migration_release_proposals',digest,value)
    writer.put(updated)
    fences = tuple(key for key,value in buffer.before.items() if value is not None)
    if not repository.store.atomic_compare_and_write(buffer.writes(fences=fences)):
        raise BulkMigrationPolicyError('REVIEW_CLOSURE_REVISION_CONFLICT')
    return value
