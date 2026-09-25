"""External process intake using stored Wiki contracts, review and bounded revision.

This is a process harness consumer, not a second Wiki authority or SOP scheduler.
Operational review receives no evaluation oracle or question-specific answers.
"""
import asyncio,copy,json
from pathlib import Path

from pydantic import Field,model_validator,ValidationError

from agent_kit.python.boi_mcp_stage import run_mcp_stage
from agent_kit.python.boi_process_review_observation import review_source_candidate
from agent_kit.python.boi_process_scope import definition_inventory_with_scope,scope_facet_inventory
from agent_kit.python.boi_process_reuse_evaluation import ProcessReuseAssessment,verified_reuse_material,check_reuse_assessment
from agent_kit.python.boi_structured_provider import run_structured
from agent_kit.python.boi_bound_inference import infer_with_bound_metadata
from agent_kit.python.boi_process_claim_review import (ProcessSourceReview,ProcessIntakeRepair,
    process_context_view,reuse_review_view,source_review_material,source_review_selection,merge_source_review,
    check_source_review,apply_intake_repair,source_review_prompt,definition_reuse_review_prompt,SOURCE_REVIEW_INSTRUCTIONS_VERSION)
from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessReuseProposalV2,ProcessDefinitionUseV2
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Digest,Ref,semantic_digest
from boi_api.app.governed_runtime.ledger import record_digest


class UseReplacement(FrozenContract):
    use_pointer: Ref
    replacement: ProcessDefinitionUseV2


class DefinitionUseRepair(FrozenContract):
    context_digest: Digest
    base_proposal_digest: Digest
    replacements: tuple[UseReplacement,...] = Field(min_length=1)

    @model_validator(mode='after')
    def unique(self):
        if len({r.use_pointer for r in self.replacements})!=len(self.replacements):
            raise ValueError('PROCESS_REPAIR_DUPLICATE_TARGET')
        return self


def apply_use_repair(proposal,repair,*,allowed_targets,context_digest):
    repair=DefinitionUseRepair.model_validate(repair)
    if repair.base_proposal_digest!=semantic_digest(proposal) or repair.context_digest!=context_digest:
        raise ValueError('PROCESS_REPAIR_BASE_OR_CONTEXT_MISMATCH')
    targets={f'/definition_uses/{i}':i for i,_ in enumerate(proposal['definition_uses'])}
    result=copy.deepcopy(proposal)
    for replacement in repair.replacements:
        if replacement.use_pointer not in allowed_targets or replacement.use_pointer not in targets:
            raise ValueError('PROCESS_REPAIR_UNRELATED_TARGET')
        index=targets[replacement.use_pointer]
        if replacement.replacement.term_pointer!=proposal['definition_uses'][index]['term_pointer']:
            raise ValueError('PROCESS_REPAIR_LOCAL_SUBJECT_CHANGED')
        result['definition_uses'][index]=replacement.replacement.model_dump(mode='json')
    # The caller binds the exact context read by the repair model before checks.
    # Source assertions and quotations are unchanged by a definition-use repair.
    result['context_digest']=context_digest;result['draft']['extraction_context_digest']=context_digest
    return ProcessReuseProposalV2.model_validate(result).model_dump(mode='json')


def structural_use_failures(proposal,inventory):
    """Locate repairable use errors by typed validation and exact inventory sets.

    No semantic selection is inferred. Invalid source meaning must be handled
    separately; it cannot authorize rewriting the draft in a use repair.
    """
    try:draft=ProcessKnowledgeDraft.model_validate(proposal['draft'])
    except (ValueError,KeyError,TypeError):return []
    known={semantic_digest(n['node_ref']):n for n in inventory}
    failures=[]
    for i,use in enumerate(proposal.get('definition_uses',[])):
        if not isinstance(use,dict):continue
        errors=[];local=None;definition=known.get(semantic_digest(use.get('definition_node')))
        try:ProcessDefinitionUseV2.model_validate(use)
        except ValidationError as exc:
            errors.extend({'path':list(e['loc']),'message':e['msg']} for e in exc.errors())
        try:local=scope_facet_inventory(draft,use.get('term_pointer'))
        except ValueError as exc:errors.append({'message':str(exc)})
        if definition is None:errors.append({'message':'PROCESS_REUSE_DEFINITION_NODE_NOT_IN_READ_INVENTORY'})
        scopes={'local':local,'definition':definition['scope_inventory'] if definition else None}
        for side,scope in scopes.items():
            if scope is None:continue
            for dimension in ('applicability','conditions','exceptions'):
                expected={f['target_pointer'] for f in scope['facets'] if f['dimension']==dimension}
                actual=[f.get('target_pointer') for c in use.get('scope_assessments',[]) if isinstance(c,dict)
                    and c.get('dimension')==dimension for f in c.get(side,[]) if isinstance(f,dict)]
                if set(actual)!=expected or len(actual)!=len(set(actual)):
                    errors.append({'message':'PROCESS_REUSE_SCOPE_FACET_ACCOUNTING_INCOMPLETE','side':side,
                        'dimension':dimension,'missing':sorted(expected-set(actual)),
                        'extra':sorted(str(p) for p in set(actual)-expected)})
        if errors:failures.append({'use_pointer':f'/definition_uses/{i}','errors':errors,'scope_inventories':scopes})
    return failures


async def source_readings(client,sources):
    result=[]
    for source in sources:
        manifest=await client.project(source)
        fields=[]
        for field in manifest['fields']:
            page=await client.read_complete_field(source,field)
            fields.append({**field,'text':page['text']})
        result.append({'source':source,'manifest':manifest,'fields':fields})
    return result


async def assess_definition_uses(material,*,infer,**kwargs):
    """An empty verified comparison inventory contains no semantic judgment."""
    if not material['targets']:
        return ProcessReuseAssessment(uses=(),limitations=(
            'No proposed definition uses. Source fidelity is reviewed separately.',)).model_dump(mode='json'),{
                'status':'not_required_no_proposed_uses','new_model_dispatch':False}
    return await asyncio.to_thread(infer,prompt=definition_reuse_review_prompt(material),
        schema=ProcessReuseAssessment.model_json_schema(),**kwargs)


def intake_review_status(check, *, candidate_revision):
    """Project the exact stored review, independent of execution/replay status."""
    if check.get('candidate_revision')!=candidate_revision:
        raise ValueError('PROCESS_INTAKE_REVIEW_CANDIDATE_MISMATCH')
    source=check.get('source_review',{})
    accepted=all(value is True for value in (check.get('assessment_complete'),
        check.get('model_assessment_accepts_definition_uses'),source.get('assessment_complete'),
        source.get('model_assessment_accepts_source_fidelity')))
    return 'accepted_by_model_review' if accepted else 'unresolved_intake_review'


async def read_stored_review_check(client,*,candidate_revision,review_revision):
    binding=await client.call('boi_process_review_binding',{'candidate_revision':candidate_revision,'review_revision':review_revision})
    check=binding.get('check',{'candidate_revision':candidate_revision,'assessment_complete':False,
        'model_assessment_accepts_definition_uses':False,'failed_use_pointers':[]})
    return check,binding


async def read_stored_intake(client,*,namespace,logical_id):
    """Resolve a current intake and its exact review from Wiki, not host memory."""
    entry=next((a for a in (await client.catalog_assets(namespace=namespace,kind='definition'))['items']
        if a['logical_id']==logical_id),None)
    if entry is None:return None
    asset=await client.read_asset(entry['revision']);content=json.loads(asset['asset']['content_json'])
    review_id=logical_id+':review:'+asset['revision']['revision_digest']
    review=next((a for a in (await client.catalog_assets(namespace=namespace,kind='pack'))['items']
        if a['logical_id']==review_id),None)
    result={'asset_revision':asset['revision'],'primary_source':content.get('intake_request',{}).get('primary_source'),
        'sources':asset['sources'],'review_revision':review['revision'] if review else None,'revisions':[],
        'status':'stored_without_review','intake_review_status':'unresolved_intake_review',
        'source_fidelity':'not_evaluated','whole_plan_qualified':False,'new_work_started':False}
    if review:
        item=await client.read_asset(review['revision'])
        check,binding=await read_stored_review_check(client,candidate_revision=asset['revision'],review_revision=review['revision'])
        result['review_binding']=binding
        result.update(status='replayed',intake_review_status=intake_review_status(check,candidate_revision=asset['revision']),
            source_review=check.get('source_review',{}),unresolved_use_pointers=check['failed_use_pointers'])
    return result


async def intake_process(client,*,runtime,raw,media_type,namespace,logical_id,request_id,installed,output_dir,
                         provider='codex',infer=run_structured,max_binding_attempts=3,max_semantic_repairs=1,max_review_corrections=1,
                         max_review_targets_per_call=8):
    if not 1<=max_binding_attempts<=3 or not 0<=max_semantic_repairs<=2 or not 0<=max_review_corrections<=1:
        raise ValueError('PROCESS_INTAKE_REPAIR_BUDGET_INVALID')
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    source=await client.capture(raw,media_type=media_type,role='corporate_metadata',idempotency_key='intake:'+request_id)
    fingerprint=semantic_digest({'source':source,'logical_id':logical_id,'harness':installed['harness']})
    catalog=await client.catalog_assets(namespace=namespace,kind='definition')
    previous=None;sources={source['artifact_ref']:source}
    for entry in catalog['items']:
        item=await client.read_asset(entry['revision'])
        for ref in item['sources']:sources[ref['artifact_ref']]=ref
        if entry['logical_id']==logical_id:
            previous=item
            payload=json.loads(item['asset']['content_json'])
            # Completed review records distinguish a finished request from a
            # candidate left awaiting review after an interrupted execution.
            if payload.get('intake_request',{}).get('fingerprint')==fingerprint:
                reviews=await client.catalog_assets(namespace=namespace,kind='pack')
                review_id=logical_id+':review:'+item['revision']['revision_digest']
                existing=next((r for r in reviews['items'] if r['logical_id']==review_id),None)
                if existing is not None:
                    reviewed=await client.read_asset(existing['revision'])
                    check,binding=await read_stored_review_check(client,candidate_revision=item['revision'],review_revision=reviewed['revision'])
                    report={'status':'replayed','asset_revision':item['revision'],'review_revision':reviewed['revision'],
                        'intake_review_status':intake_review_status(check,candidate_revision=item['revision']),
                        'primary_source':source,'sources':item['sources'],'revisions':[],
                        'unresolved_use_pointers':check['failed_use_pointers'],
                        'quarantined_node_pointers':check.get('source_review',{}).get('quarantined_node_pointers',[]),
                        'source_review':check.get('source_review',{}),'scientific_correctness':'not_evaluated',
                        'request_fingerprint':fingerprint,'new_work_started':False,'new_asset_created':False,'review_binding':binding,
                        'source_fidelity':'not_evaluated','whole_plan_qualified':False}
                    save('report.json',report);return report
    sources=list(sources.values());read_sources=await source_readings(client,sources)
    evidence=next(s for s in read_sources if s['source']==source)
    save('sources.json',read_sources);save('primary-source.json',source)
    requirement={'revision':installed['harness'],'role':'harness','reason':'Process intake and scoped definition binding.',
        'stages':['extract','reuse','review','explain']}
    async def read_context(purpose,extra_roots=()):
        return await client.read_task_knowledge({'sources':sources,'namespace':namespace,'purpose':purpose,'roots':[requirement,*extra_roots]},
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    reading=await read_context('Process source intake with existing definitions')
    inventory=definition_inventory_with_scope(reading['context'])
    save('reading-0.json',reading);save('definition-inventory.json',inventory)
    prompt=('자료를 적재해 달라는 요청을 처리하라. 아래 Wiki의 공정 profile/harness/skill 계약과 기존 정의를 모두 읽고 '
        'PRIMARY_SOURCE만 새 공정 지식으로 추출하라. 다른 sources는 기존 정의의 근거이며 새 자료처럼 다시 추출하지 마라. '
        '원문의 명칭 관계, 조건, 부정, 예외, 적용 범위를 보존하고 관련 기존 정의는 exact node로 비교/재사용하라. '
        'scope_assessments에서는 선택한 양쪽 process record의 모든 typed qualifier 및 applicability assertion을 '
        'dimension별로 한 번씩 applies/not_applicable/unresolved로 기록하라. 원문에 한정된 scope와 용어 자체의 scope를 '
        '구분하되 연결된 조건을 설명에서 인정하면서 구조상 없는 것으로 처리하지 마라. 전체 record inventory가 자동으로 '
        '모든 용어에 적용되는 것은 아니다. local target pointer는 새 draft의 실제 qualifier 위치와 일치해야 한다. '
        '정의가 다르거나 범위를 확정하지 못하면 comparison_only로 기록하고 무관한 정상 claim은 보존하라. '
        '최종 JSON은 proposal@2이며 draft의 구형 reused_definition fields는 비운다. 외부 지식·도구·평가 정답은 사용하지 않는다. '
        '출력 상한은 실행 설정을 따른다. 내부 추론에서 같은 판단을 반복하지 말고 필요한 의미와 근거를 최종 JSON에 보존하라. '
        '최종 JSON 전체를 내부 추론 안에서 미리 작성하거나 여러 번 반복 검토하지 마라. '
        '요구된 단일 JSON 객체는 본문에 정확히 한 번만, 빠짐없이 끝까지 출력하라. '
        '그 JSON은 반드시 문법적으로 유효해야 하며, 배열은 ]로만, 객체는 }로만 닫고, '
        '문자열 값 안에 이중 인용부호가 들어갈 때는 \\"으로 이스케이프하라. '
        '\nPRIMARY_SOURCE\n'+json.dumps(evidence,ensure_ascii=False)+'\nWIKI_CONTEXT\n'+json.dumps(process_context_view(reading['context']),ensure_ascii=False)+
        '\nORIGINAL_SOURCES_FOR_DEFINITIONS\n'+json.dumps([s for s in read_sources if s['source']!=source],ensure_ascii=False)+
        '\nSTORED_DEFINITION_NODE_AND_SCOPE_INVENTORY\n'+json.dumps(inventory,ensure_ascii=False))
    outcomes=[];proposal=None;feedback=None;all_inputs={}
    async def execute(invocation,inputs):
        all_inputs.clear();all_inputs.update({k:json.loads(v) for k,v in inputs.items()})
        return await installed['execute'](invocation,inputs)
    async def bind(value,current_reading,key):
        inputs=[{'kind':'proposal','name':'draft','content_json':json.dumps(value,ensure_ascii=False)},
            {'kind':'source_projection','name':'evidence','source':source,'manifest_revision':{
                'ref':evidence['manifest']['manifest_ref'],'revision_digest':record_digest(evidence['manifest']['manifest_ref'])}},
            {'kind':'source_projection_bundle','name':'sources','projections':[{'source':s['source'],'manifest_revision':{
                'ref':s['manifest']['manifest_ref'],'revision_digest':record_digest(s['manifest']['manifest_ref'])}} for s in read_sources]}]
        return await run_mcp_stage(client,reading=current_reading,harness_revision=installed['harness'],stage_id='reuse',
            sources=sources,inputs=inputs,execute=execute,idempotency_key=key,execution_journal_dir=root/'binding-executions')
    for attempt in range(max_binding_attempts):
        if attempt==0:
            proposal,run=await asyncio.to_thread(infer_with_bound_metadata,infer=infer,
                bindings={'/context_digest':reading['context']['context_digest'],
                    '/draft/extraction_context_digest':reading['context']['context_digest'],
                    '/draft/source_revision_digest':source['digest']},
                provider=provider,knowledge_reading_ref=reading['reading_ref'],prompt=prompt,
                schema=ProcessReuseProposalV2.model_json_schema(),output_dir=root/f'extract-{attempt}')
        else:
            failures=structural_use_failures(proposal,inventory)
            save(f'structural-failures-{attempt}.json',failures)
            if not failures:
                outcomes.append({'attempt':attempt,'kind':'binding_repair','status':'not_repairable_by_definition_use_patch',
                    'reason':'No exact failed use can be isolated. Preserve the draft and diagnostics for a separate source/node repair.'})
                break
            patch_prompt=(prompt+'\nRepair only the definition_uses listed in STRUCTURAL_REPAIR. Return a DefinitionUseRepair, '
                'not a new draft. Preserve source terms/assertions and unaffected comparisons. The supplied scope inventories '
                'enumerate exact pointers; choose dispositions by reading meaning and evidence, never drop a required facet. '
                'Base and context digests are bound by the caller. Do not change semantic relations merely to pass a validator.\nSTRUCTURAL_REPAIR\n'+
                json.dumps({'base_proposal_digest':semantic_digest(proposal),'context_digest':reading['context']['context_digest'],
                    'proposal':proposal,'failed_uses':failures,'previous_diagnostics':feedback},ensure_ascii=False))
            patch,run=await asyncio.to_thread(infer_with_bound_metadata,infer=infer,
                bindings={'/context_digest':reading['context']['context_digest'],'/base_proposal_digest':semantic_digest(proposal)},
                provider=provider,knowledge_reading_ref=reading['reading_ref'],prompt=patch_prompt,
                schema=DefinitionUseRepair.model_json_schema(),output_dir=root/f'structural-repair-{attempt}')
            try:
                proposal=apply_use_repair(proposal,patch,allowed_targets={f['use_pointer'] for f in failures},
                    context_digest=reading['context']['context_digest'])
            except ValueError as exc:
                feedback={'repair_diagnostic':str(exc)};save(f'structural-repair-check-{attempt}.json',feedback)
                outcomes.append({'attempt':attempt,'kind':'binding_repair','status':'invalid_patch','provider':run,'diagnostic':str(exc)})
                continue
            save(f'structurally-repaired-proposal-{attempt}.json',proposal)
        result=await bind(proposal,reading,request_id+':bind:'+str(attempt));save(f'binding-{attempt}.json',result)
        outcomes.append({'attempt':attempt,'kind':'initial_binding' if attempt==0 else 'binding_repair','status':result['status'],'provider':run})
        if result['status']=='completed':break
        feedback={'proposal':proposal,'reports':[e['output'] for e in result['executions']]}
    if result['status']!='completed':
        report={'status':'binding_unresolved','attempts':outcomes,'source':source,'reason':'Typed/evidence contract failure; not missing business knowledge.',
            'whole_plan_qualified':False};save('report.json',report);return report
    revisions=[];review=None;prior_source_review=None;prior_reviewed_draft=None
    for revision_attempt in range(max_semantic_repairs+1):
        output=result['executions'][0]['output']['result']
        execution_refs=[e['admission']['execution_ref'] for e in result['executions']]
        material=verified_reuse_material(proposal=all_inputs['draft'],bound=output,evidence=all_inputs['evidence'],
            context=all_inputs['context'],sources=all_inputs['sources'])
        content={**output,'execution_refs':execution_refs,'harness_revision':installed['harness'],
            'intake_request':{'fingerprint':fingerprint,'primary_source':source,'repair_attempt':revision_attempt}}
        spans={b['span_ref'] for b in output['bindings']}
        for use in output['definition_uses']:
            for n in use['definition_evidence']:spans.update(b['span_ref'] for b in n['source_bindings'])
            for c in use['resolved_scope']['comparisons']:
                for side in ('local','definition'):
                    for facet in c[side]:
                        for n in facet['graph_evidence']:spans.update(b['span_ref'] for b in n['source_bindings'])
        dependencies=[requirement]+[{'revision':ref,'role':'compared_definition','reason':'Exact previous definition compared.',
            'stages':['extract','reuse','review','explain']} for ref in output['definition_comparison_revisions']]
        saved=await client.propose_asset({'logical_id':logical_id,'namespace':namespace,'title':'공정 자료 적재 결과',
            'description':'원문·정의·scope를 연결한 후보이며 별도 검토 기록을 확인해야 한다.','kind':'definition','sources':sources,
            'content_json':json.dumps(content,ensure_ascii=False),'dependencies':dependencies,
            'evidence_spans':[{'ref':s,'revision_digest':record_digest(s)} for s in sorted(spans)],
            'definition_reading_ref':reading['reading_ref'],'previous_revision':previous['revision'] if previous else None},
            idempotency_key=request_id+':candidate:'+str(revision_attempt))
        save(f'candidate-{revision_attempt}.json',saved);save(f'bound-{revision_attempt}.json',content)
        save(f'inputs-{revision_attempt}.json',all_inputs)
        candidate_reading=await read_context('Read exact stored candidate for semantic review',
            ({'revision':saved['revision'],'role':'reviewed_candidate','reason':'Review this stored candidate revision.',
                'stages':['review']},))
        save(f'candidate-reading-{revision_attempt}.json',candidate_reading)
        selection=source_review_selection(output['draft'],evidence,previous_draft=prior_reviewed_draft,previous_review=prior_source_review)
        source_observation=await review_source_candidate(draft=output['draft'],evidence=evidence,context=all_inputs['context'],
            knowledge_reading_ref=candidate_reading['reading_ref'],input_revisions=[saved['revision'],installed['harness']],
            infer=infer,provider=provider,output_dir=root/f'source-review-observation-{revision_attempt}',
            selection=selection,previous_review=prior_source_review,max_corrections=max_review_corrections,
            max_targets_per_call=max_review_targets_per_call)
        source_assessed=source_observation['validated_assessment'];source_check=source_observation['check']
        source_model=source_check['provider_run']
        source_check.update(provider_run=source_model,review_instructions_version=SOURCE_REVIEW_INSTRUCTIONS_VERSION,
            category_contract_binding=output.get('category_contract_binding'),carry_forward_nodes=selection['carry_forward_nodes'],
            carry_forward_fields=selection['carry_forward_fields'],prior_review_revision=revisions[-1]['review'] if revisions else None)
        save(f'source-review-check-{revision_attempt}.json',source_check)
        assessed,model=await assess_definition_uses(material,infer=infer,provider=provider,
            knowledge_reading_ref=candidate_reading['reading_ref'],input_revisions=[saved['revision'],installed['harness']],
            output_dir=root/f'review-{revision_attempt}')
        try:review=check_reuse_assessment(assessed,material=material)
        except ValueError as exc:
            review={'assessment_complete':False,'diagnostic':str(exc),'model_assessment_accepts_definition_uses':False}
        failed=[u['use_pointer'] for u in assessed.get('uses',[]) if any(j['label']!='supported' for j in u['judgments'])]
        if review.get('assessment_complete') and not material['targets']:
            review.update(model_assessment_accepts_definition_uses=True,reuse_status='no_proposed_uses_to_review')
        review.update(candidate_revision=saved['revision'],provider_run=model,failed_use_pointers=failed,
            source_review=source_check,scope='Source terms/assertions and field coverage; definition relations/scopes. Answer usefulness is separate.',
            source_fidelity='not_evaluated',scientific_correctness='not_evaluated',whole_plan_qualified=False)
        save(f'review-check-{revision_attempt}.json',review)
        review_reading=await read_context('Record process definition review')
        review_asset=await client.propose_asset({'logical_id':logical_id+':review:'+saved['revision']['revision_digest'],
            'namespace':namespace,'title':'공정 정의 연결 검토','description':'외부 모델 검토와 기계적 근거/대상 검사. 전문가 판정 아님.',
            'kind':'pack','sources':sources,'content_json':json.dumps({'assessment':assessed,'source_assessment':source_assessed,'source_observation':source_observation,'check':review},ensure_ascii=False),
            'definition_reading_ref':review_reading['reading_ref'],'dependencies':[{'revision':saved['revision'],'role':'reviewed_candidate',
                'reason':'This review concerns this exact candidate revision.','stages':['review','explain']}]},
            idempotency_key=request_id+':review:'+str(revision_attempt))
        revisions.append({'candidate':saved['revision'],'review':review_asset['revision'],'failed_uses':failed,
            'failed_claims':source_check['failed_claim_pointers'],'execution_refs':execution_refs,
            'review_complete':review['assessment_complete'] and source_check['assessment_complete']})
        if (not failed and source_check.get('model_assessment_accepts_source_fidelity')) or not revisions[-1]['review_complete'] or revision_attempt==max_semantic_repairs:break
        reading=await read_context('Repair reported process source and definition-use failures',
            ({'revision':saved['revision'],'role':'repair_candidate','reason':'Exact failed candidate.', 'stages':['review']},
             {'revision':review_asset['revision'],'role':'stored_failure','reason':'Exact recorded review failure.', 'stages':['review']}))
        allowed_fields={q['field_locator'] for f in source_check['failures'] for q in f.get('evidence',[])}
        allowed_fields.update(f['field_locator'] for f in source_check['failures'] if f.get('field_locator'))
        repair_prompt=('아래 원문/읽은 Wiki 정의와 검토 실패를 읽고 지적된 claim node와 definition use만 수정하라. '
            '정답표는 없고 검토 모델도 틀릴 수 있다. 이유와 원문을 재검토하고 해결할 근거가 없으면 '
            'unresolved에 필요한 증거와 이유를 적고 해당 use는 comparison_only로 격리하라. 정상적인 node는 '
            '재작성하지 마라. 잘못된 주장을 교체할 수 없으면 원문 근거·이유·보존된 정보 위치를 적어 retractions로 철회할 수 있다. 관련 참조는 명시적으로 수정하고 scope pointer는 수정 전 위치를 사용하라. nodes는 실패한 term/assertion의 ID를 유지하며 교체한다. 필요한 누락/주어 보완만 '
            'allowed_addition_fields 근거로 같은 record에 terms/assertions를 추가할 수 있다. node가 바뀐 record의 '
            'use는 새 scope inventory에 맞춰 함께 갱신할 수 있다. not_applicable은 용어의 뜻을 제한하지 않는다는 '
            '뜻이지 전체 기록의 행위 조건을 지우는 것이 아니다. 용어 뜻이 같고 행위 맥락만 다른 경우를 구분하라. '
            'base_proposal_digest와 현재 context_digest는 호출자가 결합한다. typed patch의 의미 내용만 반환하라.\n'+json.dumps({
                'base_proposal_digest':semantic_digest(proposal),'proposal':proposal,'failed_uses':failed,
                'failed_claims':source_check['failed_claim_pointers'],'source_failures':source_check['failures'],
                'allowed_addition_fields':sorted(allowed_fields),'use_assessment':assessed,
                'context':process_context_view(reading['context']),'original_sources':read_sources},ensure_ascii=False))
        patch,model=await asyncio.to_thread(infer_with_bound_metadata,infer=infer,
            bindings={'/context_digest':reading['context']['context_digest'],'/base_proposal_digest':semantic_digest(proposal)},
            provider=provider,knowledge_reading_ref=reading['reading_ref'],
            input_revisions=[saved['revision'],review_asset['revision'],installed['harness']],prompt=repair_prompt,
            schema=ProcessIntakeRepair.model_json_schema(),output_dir=root/f'repair-{revision_attempt}')
        try:
            changed,delta=apply_intake_repair(proposal,patch,failed_claims=set(source_check['failed_claim_pointers']),
                failed_uses=set(failed),allowed_fields=allowed_fields,context_digest=reading['context']['context_digest'],source_evidence=evidence)
        except ValueError as exc:
            outcomes.append({'kind':'semantic_repair','status':'invalid_patch','diagnostic':str(exc),'provider':model});break
        save(f'repair-delta-{revision_attempt}.json',delta)
        outcomes.append({'kind':'semantic_repair','status':'proposed','provider':model,'delta':delta})
        if not delta['changed_nodes'] and not delta['changed_use_pointers']:break
        prior_source_review=source_assessed;prior_reviewed_draft=output['draft'];proposal=changed
        previous=saved
        result=await bind(proposal,reading,request_id+':repair:'+str(revision_attempt))
        save(f'repair-binding-{revision_attempt}.json',result)
        if result['status']!='completed':break
    report={'status':'recorded_with_unresolved_review' if not (review.get('model_assessment_accepts_definition_uses') and source_check.get('model_assessment_accepts_source_fidelity')) else 'recorded_with_model_review',
        'intake_review_status':intake_review_status(review,candidate_revision=saved['revision']),
        'asset_revision':saved['revision'],'review_revision':review_asset['revision'],'revisions':revisions,'attempts':outcomes,
        'primary_source':source,'sources':sources,'unresolved_use_pointers':review['failed_use_pointers'],
        'quarantined_node_pointers':source_check['quarantined_node_pointers'],'source_review':source_check,
        'source_fidelity':'not_evaluated','scientific_correctness':'not_evaluated','whole_plan_qualified':False,
        'definition_review_only':False,'request_fingerprint':fingerprint}
    verified,binding=await read_stored_review_check(client,candidate_revision=saved['revision'],review_revision=review_asset['revision'])
    report['review_binding']=binding
    report['intake_review_status']=intake_review_status(verified,candidate_revision=saved['revision'])
    report['status']=('recorded_with_model_review' if report['intake_review_status']=='accepted_by_model_review'
        else 'recorded_with_unresolved_review')
    save('report.json',report);return report
