"""Source-only explanation with Wiki-owned state outside model-authored prose."""
import asyncio,copy,json
from pathlib import Path
from typing import Annotated,Literal
from pydantic import Field
from .boi_process_answer_layout import AnswerLayout

from agent_kit.python.boi_process_answer_v2 import SourceStatement,GapStatement,RequestPlan,bind_process_answers_v2
from agent_kit.python.boi_process_intake import source_readings
from agent_kit.python.boi_process_result_view import render_process_result
from agent_kit.python.boi_process_claim_review import process_context_view,check_answer_review_dependencies
from agent_kit.python.boi_process_response_review import review_response,response_proposal,RESPONSE_REVIEW_VERSION,response_context_view,response_prompt_context
from agent_kit.python.boi_process_change_impact import source_answer_impact
from boi_api.app.governed_runtime.semantic_binding_contract import Digest,FrozenContract,Ref,RevisionRef,semantic_digest


class SourceAnswer(FrozenContract):
    question_id: Ref
    sentences: tuple[Annotated[SourceStatement|GapStatement,Field(discriminator='kind')],...] = Field(min_length=1)
    limitations: tuple[Annotated[SourceStatement|GapStatement,Field(discriminator='kind')],...] = ()
    layout: AnswerLayout | None = Field(default=None,exclude_if=lambda v:v is None)
    request_plan: RequestPlan | None = Field(default=None,exclude_if=lambda v:v is None)


class SourceExplanation(FrozenContract):
    contract_version: Literal['boi/source-explanation-proposal@1']='boi/source-explanation-proposal@1'
    context_digest: Digest
    answers: tuple[SourceAnswer,...] = Field(min_length=1)


def source_explanation_generation_schema():
    """Fresh answers must plan request meaning; historical records stay readable."""
    schema=SourceExplanation.model_json_schema()
    answer=schema['$defs']['SourceAnswer']
    answer['properties']['request_plan']={'$ref':'#/$defs/RequestPlan'}
    answer['required']=[*answer.get('required',[]),'request_plan']
    return schema


class ProcessUserQuestion(FrozenContract):
    id: Ref
    question: Ref
    max_body_characters: int | None = Field(default=None,ge=1,le=10000,strict=True)
    response_request: Ref | None = Field(default=None,exclude_if=lambda v:v is None)
    previous_answer_revision: RevisionRef | None = Field(default=None,exclude_if=lambda v:v is None)


def normalize_process_questions(questions):
    """User text needs no internal ID; exact text gives stable request identity."""
    if isinstance(questions,str):questions=[questions]
    if not isinstance(questions,(list,tuple)) or not questions:
        raise ValueError('PROCESS_QUESTIONS_REQUIRED')
    result=[]
    for value in questions:
        if isinstance(value,str):value={'id':'question:'+semantic_digest(value),'question':value}
        result.append(ProcessUserQuestion.model_validate(value).model_dump(mode='json'))
    if len({q['id'] for q in result})!=len(result):raise ValueError('PROCESS_QUESTION_ID_DUPLICATE')
    return result


class ProcessSourceNote(FrozenContract):
    """Stored original sources that have no admitted extracted meaning yet."""
    contract_version: Literal['boi/process-source-note@1']='boi/process-source-note@1'
    reading_mode: Literal['original_source_only']='original_source_only'
    extraction_status: Literal['not_performed']='not_performed'


def review_asset_binding_errors(asset,review,material):
    """Structural linkage only; execution admission needs separate resolution."""
    errors=[]
    if review is None:return ['review_missing']
    content=json.loads(review['asset']['content_json'])
    if not isinstance(content,dict) or not isinstance(content.get('check'),dict):
        return ['review_content_or_check_not_an_object']
    if content!=material:errors.append('review_material_not_stored_content')
    reviewed=(content.get('input_revisions') or [None])[0] if content.get('contract_version')=='boi/process-source-meaning-alignment@2' else content.get('check',{}).get('candidate_revision')
    if reviewed!=asset['revision']:errors.append('review_candidate_revision_mismatch')
    if not any(d['revision']==asset['revision'] for d in review['asset'].get('dependencies',[])):
        errors.append('review_candidate_dependency_missing')
    if not set(s['digest'] for s in asset['sources'])<=set(s['digest'] for s in review['sources']):
        errors.append('review_source_revisions_incomplete')
    return errors


async def intake_evidence(client, intake):
    asset=await client.read_asset(intake['asset_revision'])
    if intake.get('review_revision'):
        review=await client.read_asset(intake['review_revision'])
        material=json.loads(review['asset']['content_json'])
        errors=review_asset_binding_errors(asset,review,material)
        if errors:material={'check':{},'review_binding':{'status':'unconfirmed','reason_codes':errors},
            'meaning_citations_allowed':False}
    else:
        # An unreviewed typed candidate can still provide original sources;
        # none of its meaning citations becomes reviewed by this fallback.
        content=json.loads(asset['asset']['content_json'])
        if content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
            from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
            ProcessKnowledgeDraft.model_validate(content.get('draft'))
        else:ProcessSourceNote.model_validate(content)
        review=None
        material={'status':'no_extracted_meaning_to_review','check':{'failed_use_pointers':[]},
            'meaning_citations_allowed':False,'semantic_support_proven':False}
    binding=await client.call('boi_process_review_binding',{'candidate_revision':asset['revision'],
        'review_revision':review['revision'] if review else None})
    return asset,review,material,binding


def answer_dependencies(asset, review):
    values=[(asset['revision'],'requested_process_meaning' if review else 'requested_source_note')]
    if review:values.append((review['revision'],'review'))
    return [{'revision':ref,'role':role,'reason':'Requested source/meaning and its actual review when present.',
        'stages':['explain','review']} for ref,role in values]


def check_answer_evidence(answer, *, asset, review, material, binding=None):
    if review is None and any(c['kind']=='meaning' for a in answer['answers']
            for loc in ('sentences','limitations') for s in a[loc] for c in s['citations']):
        raise ValueError('PROCESS_SOURCE_NOTE_REQUIRES_DIRECT_SOURCE_CITATIONS')
    # A caller-authored stored check cannot qualify its own execution linkage.
    # Public reads recompute this binding in Wiki; agent paths obtain it via MCP.
    valid=(binding is not None and binding.get('status') in ('bound','partially_bound')
        and binding.get('candidate_revision')==asset['revision']
        and binding.get('review_revision')==(review['revision'] if review else None)
        and not review_asset_binding_errors(asset,review,material))
    checked=check_answer_review_dependencies(answer,asset_revision=asset['revision'],
        asset_content=json.loads(asset['asset']['content_json']),review_check=binding.get('check',{}) if valid else {})
    return {**checked,'review_execution_binding':binding.get('review_execution_binding','unconfirmed') if valid else 'unconfirmed',
        'binding_reason_codes':binding.get('reason_codes',[]) if binding else ['wiki_execution_binding_not_resolved']}


def affected_answer_questions(packet,*,old_source,new_source):
    """Compatibility entrypoint; no citation overlap does not prove no impact."""
    return source_answer_impact(packet,old_source=old_source,new_source=new_source)


def project_answer_evidence(answer, *, asset, review, material, binding):
    """A read projection withholds affected statements, never edits old assets.

    No semantic repair or citation conversion takes place. Each retained
    statement keeps its entire original citation set and original pointer.
    """
    projected=copy.deepcopy(answer);withheld=[]
    for ai,item in enumerate(projected['answers']):
        for location in ('sentences','limitations'):
            retained=[]
            for si,statement in enumerate(item[location]):
                single={'answers':[{'sentences':[statement],'limitations':[]}]}
                try:check_answer_evidence(single,asset=asset,review=review,material=material,binding=binding)
                except ValueError as exc:
                    if not str(exc).startswith(('PROCESS_ANSWER_QUARANTINED_DEPENDENCY:',
                            'PROCESS_SOURCE_NOTE_REQUIRES_DIRECT_SOURCE_CITATIONS')):raise
                    withheld.append({'target_pointer':f'/answers/{ai}/{location}/{si}',
                        'reason_code':'meaning_review_link_or_dependency_unresolved',
                        'needed_evidence':'An admitted review of this exact candidate node and its dependency scope.'})
                else:retained.append(statement)
            item[location]=retained
        item['body']=' '.join(s['text'] for s in item['sentences'])
        item['body_characters']=len(item['body'])
        if any(w.get('answer_index')==ai or w.get('target_pointer','').startswith(f'/answers/{ai}/') for w in withheld):
            item.pop('layout',None)
            if item.get('request_plan'):
                item.pop('request_plan')
                withheld.append({'target_pointer':f'/answers/{ai}/request_plan',
                    'reason_code':'request_plan_statement_projection_changed',
                    'needed_evidence':'Rebind the preserved original plan to the changed statement projection.'})
        elif item.get('request_plan'):
            try:check_answer_evidence({'answers':[{'sentences':[],'limitations':[],
                'request_plan':item['request_plan']}]},asset=asset,review=review,material=material,binding=binding)
            except ValueError as exc:
                if not str(exc).startswith(('PROCESS_ANSWER_QUARANTINED_DEPENDENCY:',
                        'PROCESS_SOURCE_NOTE_REQUIRES_DIRECT_SOURCE_CITATIONS')):raise
                item.pop('request_plan')
                withheld.append({'target_pointer':f'/answers/{ai}/request_plan',
                    'reason_code':'request_plan_meaning_dependency_unresolved',
                    'needed_evidence':'An admitted review of the plan meaning and dependency scope.'})
    return projected,withheld


def source_explanation_prompt(*,asset,review_revision,review_check,review_material,reading,sources,questions):
    """One operational contract shared by native proposals and structured workers."""
    context=response_prompt_context(reading['context'],projection_root='/context')
    previous=[]
    for question in questions:
        ref=question.get('previous_answer_revision')
        if ref:
            prior=next((a for a in reading['context']['assets'] if a['revision']==ref),None)
            if prior is None:raise ValueError('PROCESS_FOLLOWUP_PRIOR_ANSWER_NOT_READ')
            content=json.loads(prior['content_json'])
            previous.append({'revision':ref,'proposal':response_proposal(content['answer']),
                'role':'Earlier wording to improve, not original source evidence or a review verdict.'})
    return ('새 세션의 사용자 질문에 저장한 공정 지식을 활용해 답하라. 원문과 근거를 모두 읽고 답할 수 있는 부분을 '
        '불필요하게 거절하지 마라. requested_asset을 우선 사용하고 과거 revision은 현재 조건과 구분하라. '
        '검토에서 해결되지 않은 use는 그 관계를 확정한 것으로 사용하지 마라. 원문 직접 근거로 답할 수 있는 부분은 '
        '계속 사용하고, source_review에서 격리된 candidate node와 그 의존 graph를 meaning citation으로 사용하지 마라. '
        '계속 답하되 과학적 진위로 승격하지 마라. 조건/부정/예외를 보존하고 문장별 원문 또는 meaning citation을 '
        '연결하라. 한 문장에 위치·순서·이유·조건을 함께 쓴다면 각각을 지지하는 구절을 그 문장에 모두 연결하라. '
        '다른 문장의 인용이나 제목 필드로 현재 문장의 조건/인과를 대신하지 마라. '
        '확인된 차이와 확인할 수 없는 동일성·수치·조건을 한 결론에 묶어 모호하게 만들지 말고 각각 설명하라. '
        '문장의 직접 근거에 필요한 구절만 선택하고, 자료의 제목·전체 본문·provenance 값을 한꺼번에 '
        '인용해 근거 부족을 메우려 하지 마라. 자료 확인 범위는 공정 주장의 긍정 근거와 구별하라. '
        '근거 부재 주장은 evidence_gap과 완전한 source_scope를 사용하라. Wiki 상태·권한·승인·검증 완료·'
        '자료 식별 provenance는 UI가 실제 metadata로 표시하므로 본문이나 limitation에서 그런 runtime 상태를 서술하지 마라. '
        '단, 원문이 명시한 적용 대상·사용 한계가 답에 영향을 주면 그 조건은 근거와 함께 본문에서 설명하라. '
        '원문이 보고한 사실과 해석/원문 범위에서의 근거 부족만 자연스러운 한국어로 설명하라. 내부 field key를 나열하지 '
        '마라. 질문에 직접 답하는 결론부터 쓰고 필요한 이유·조건을 연결해 설명하라. 최신 response_request의 깊이·형식을 '
        '반영하라. layout으로 문단·목록·비교표를 선택할 수 있다. /sentences/i 또는 /limitations/i를 정확히 한 번씩 '
        '배치하고, 표의 셀마다 표시할 내용을 별도의 짧은 statement로 작성해 각 주장의 인용을 보존하라. '
        '하나의 긴 문장을 여러 셀에서 재사용해 부분 추출하려 하지 마라. 표 제목은 열의 역할만 기술하라. 표를 요구하지 않은 '
        '질문까지 고정 형식으로 만들지 마라. 구성과 열 제목도 독립 검토 대상이며 최종 전달에서 설명을 추가하지 않는다. '
        '정보를 포함한 것만으로 설명이 명료한 것은 아니다. 각 질문 요구에 답했는지, 필요한 이유·조건이 충분한지, '
        '정보 순서와 구성이 이해를 돕는지, 반복·장황한 셀·모호한 표현이 핵심을 가리지 않는지 각각 확인하라. '
        '긴 설명은 표 아래 적절한 문단에서 풀고, 공통 한계는 중복을 줄이되 주장별 조건을 보존하라. '
        '명시된 max_body_characters가 있을 때만 지켜라. 외부 지식·도구·평가 정답은 없다.\n'+
        ('max_body_characters가 null이면 별도의 본문 글자 수 제한을 요청하지 않은 질문이다.\n' if any(q.get('max_body_characters') is None for q in questions) else '')+json.dumps({
            'requested_asset':asset['revision'],'context':context,'original_sources':sources,
            **({'previous_answer_wording':previous} if previous else {}),
            'review':{'review_revision':review_revision,'check':review_check,
                'definition_use_assessment':review_material.get('assessment'),
                'raw_source_review_attempts':'Preserved in the exact Wiki review revision; operative failures and quarantine are in check.'},
            'questions':questions},ensure_ascii=False,separators=(',',':')))


async def explain_intake(client,*,runtime,intake,namespace,questions,output_dir,infer,provider='codex',max_attempts=2,
        proposed_answer=None,max_response_repairs=1,prepared_reading_ref=None):
    questions=normalize_process_questions(questions)
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    asset,review,review_material,review_binding=await intake_evidence(client,intake)
    review_check=review_binding.get('check',{})
    review_revision=review['revision'] if review else None
    sources=await source_readings(client,asset['sources'])
    answer_identity=asset['logical_id']+':answers:'+semantic_digest({'asset':asset['revision'],'review':review_revision,'questions':questions})
    existing=next((a for a in (await client.catalog_assets(namespace=namespace,kind='pack'))['items'] if a['logical_id']==answer_identity),None)
    previous_answer_revision=None
    if existing is not None:
        saved=await client.read_asset(existing['revision']);packet=json.loads(saved['asset']['content_json'])
        if packet['wiki_metadata']['asset_revision']!=asset['revision'] or packet['wiki_metadata']['review_revision']!=review_revision:
            raise ValueError('PROCESS_ANSWER_REPLAY_BINDING_MISMATCH')
        supplied_changed=(proposed_answer is not None and
            packet.get('input_provenance',{}).get('proposal_digest')!=semantic_digest(proposed_answer))
        if supplied_changed:
            previous_answer_revision=saved['revision']
        else:
            visible,withheld=project_answer_evidence(packet['answer'],asset=asset,review=review,material=review_material,binding=review_binding)
            packet={**packet,'answer':visible,'withheld_statements':withheld,'review_binding':review_binding,
                'view_is_partial':bool(withheld),'historical_asset_preserved':True}
            save('result.json',packet);save('answer-asset.json',saved)
            render_process_result(packet,root/'result.html',questions=questions,sources=sources)
            return {'status':'partial_replay' if withheld else 'replayed','asset_revision':saved['revision'],'packet_path':str(root/'result.json'),
                'withheld_statement_count':len(withheld),
                'view_path':str(root/'result.html'),'new_model_run':False,
                'answer_review_status':packet.get('response_review',{}).get('status','not_reviewed_under_current_contract'),
                'whole_plan_qualified':False}
    roots=answer_dependencies(asset,review)
    if prepared_reading_ref is not None:
        reading=await client.restore_task_knowledge(prepared_reading_ref,asset['sources'],
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
        read_refs=[a['revision'] for a in reading['context']['assets']]
        if any(d['revision'] not in read_refs for d in roots):
            raise ValueError('PROCESS_PREPARED_ANSWER_DEPENDENCY_NOT_READ')
        if proposed_answer is not None and proposed_answer.get('context_digest')!=reading['context']['context_digest']:
            raise ValueError('PROCESS_PREPARED_ANSWER_CONTEXT_MISMATCH')
    else:
        reading=await client.read_task_knowledge({'sources':asset['sources'],'namespace':namespace,'purpose':'Answer new questions from stored process intake','roots':roots,'tool_use':'provenance_only'},
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    save('reading.json',reading);save('sources.json',sources);save('asset.json',asset);save('review.json',review)
    prompt=source_explanation_prompt(asset=asset,review_revision=review_revision,review_check=review_check,
        review_material=review_material,reading=reading,sources=sources,questions=questions)
    attempts=[];feedback=None;bound=None
    for attempt in range(max_attempts):
        if proposed_answer is not None:
            # An explicitly supplied answer is an untrusted candidate, not a
            # freshly generated answer or previously admitted Wiki context.
            proposal={**proposed_answer,'context_digest':reading['context']['context_digest']}
            run={'status':'supplied_untrusted_answer','new_model_run':False,
                'original_proposal_digest':semantic_digest(proposed_answer)}
            save('supplied-proposal.json',proposed_answer)
        else:
            try:
                proposal,run=await asyncio.to_thread(infer,provider=provider,prompt=prompt+('\nBINDING_DIAGNOSTIC\n'+json.dumps(feedback,ensure_ascii=False) if feedback else ''),
                    schema=source_explanation_generation_schema(),output_dir=root/f'provider-{attempt}',
                    knowledge_reading_ref=reading['reading_ref'])
            except ValueError as exc:
                # Adapter outcome codes, not source-text or semantic matching.
                # Preserve available intake/readings and stop; neither an exit
                # nor an infrastructure failure is an answer or evidence gap.
                code=str(exc)
                known={'STRUCTURED_PROVIDER_FAILED','STRUCTURED_PROVIDER_TIMED_OUT',
                    'STRUCTURED_PROVIDER_MISSING_STRUCTURED_OUTPUT','STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE'}
                if code not in known:raise
                unknown=code=='STRUCTURED_PROVIDER_TIMED_OUT'
                attempts.append({'attempt':attempt,'status':'external_generation_failed','reason_code':code})
                result={'status':'external_generation_result_unknown' if unknown else 'answer_generation_failed',
                    'attempts':attempts,'failure_origin':'external_provider','reason_code':code,
                    'external_outcome':'unknown' if unknown else 'recorded_provider_failure',
                    'intake_asset_revision':asset['revision'],'review_revision':review['revision'] if review else None,
                    'reading_ref':reading['reading_ref'],'answer_asset_saved':False,'user_request_fulfilled':False,
                    'automatic_retry_performed':False,'whole_plan_qualified':False}
                save('attempts.json',attempts);save('report.json',result)
                return result
        try:
            value=SourceExplanation.model_validate(proposal).model_dump(mode='json')
            # Historical answer@2 is a read projection for its established
            # quotation binder; runtime prose is absent from the writer schema.
            value['contract_version']='boi/process-answer-draft@2'
            bound=bind_process_answers_v2(value,context=reading['context'],sources=sources,questions=questions)
            quarantine_check=check_answer_evidence(bound,asset=asset,review=review,material=review_material,binding=review_binding)
        except ValueError as exc:
            bound=None
            feedback={'proposal':proposal,'diagnostic':str(exc)}
            attempts.append({'status':'needs_revision','provider':run,'diagnostic':str(exc)})
            if proposed_answer is not None:break
        else:
            attempts.append({'status':'bound','provider':run});break
    save('attempts.json',attempts)
    if bound is None:return {'status':'answer_binding_unresolved','attempts':attempts}
    context=reading['context']
    save('initial-bound-answer.json',bound)
    def validate_repair(proposal):
        value=SourceExplanation.model_validate(proposal).model_dump(mode='json')
        value['contract_version']='boi/process-answer-draft@2'
        repaired=bind_process_answers_v2(value,context=context,sources=sources,questions=questions)
        check_answer_evidence(repaired,asset=asset,review=review,material=review_material,binding=review_binding)
        return repaired
    bound,response_review=await review_response(bound=bound,context=context,sources=sources,questions=questions,
        output_dir=root/'response-review',infer=infer,validate_repair=validate_repair,provider=provider,max_repairs=max_response_repairs,
        reading_ref=reading['reading_ref'])
    packet={'contract_version':'boi/process-user-result@2','answer':bound,'response_review':response_review,
        'input_provenance':{'kind':'supplied_untrusted_answer','proposal_digest':semantic_digest(proposed_answer),
            'proposal':proposed_answer,'new_answer_generation':False} if proposed_answer is not None else
            {'kind':'external_model_answer','new_answer_generation':True},
        'questions':questions,'review_dependency_check':quarantine_check,
        'wiki_metadata':{'origin':'actual_mcp_readings','context_digest':context['context_digest'],
            'asset_revision':asset['revision'],'authority':asset['asset']['authority'],
            **{k:context[k] for k in ('source_fidelity','domain_verdict','task_readiness','dependency_completeness','display_status')},
            'review_revision':review_revision,'evidence_mode':'reviewed_candidate' if review else 'original_source_only'},
        'unresolved_use_pointers':review_check.get('failed_use_pointers',[]),
        'review_binding':review_binding,
        'source_review_failures':review_check.get('source_review',{}).get('failures',[]),
        'source_review_protocol_failures':review_check.get('source_review',{}).get('review_protocol_failures',[]),
        'whole_plan_qualified':False}
    saved=await client.propose_asset({'logical_id':answer_identity,
        'namespace':namespace,'title':'새 질문과 공정 설명 근거','description':'저장된 후보/검토를 새 세션에서 읽고 원문 근거와 연결한 답변.',
        'kind':'pack','sources':asset['sources'],'content_json':json.dumps(packet,ensure_ascii=False),
        'definition_reading_ref':reading['reading_ref'],'dependencies':roots,
        **({'previous_revision':previous_answer_revision} if previous_answer_revision else {})},
        idempotency_key=('process-answer-proposal:'+semantic_digest([answer_identity,previous_answer_revision,proposed_answer])
            if previous_answer_revision else answer_identity))
    save('result.json',packet);save('answer-asset.json',saved)
    render_process_result(packet,root/'result.html',questions=questions,sources=sources)
    return {'status':'recorded','asset_revision':saved['revision'],'packet_path':str(root/'result.json'),
        'view_path':str(root/'result.html'),'answer_review_status':response_review['status'],'whole_plan_qualified':False}


def completed_source_review_value(native,*,prompt,schema,reading_ref,sources,input_revisions,version):
    """Input-bound replay of an authenticated observation, never a new verdict."""
    from boi_api.app.governed_runtime.native_observation import NativeObservation
    from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
    from .boi_structured_provider import strict_output_schema
    from jsonschema import Draft202012Validator,ValidationError
    native=NativeObservation.model_validate(native).model_dump(mode='json');data=native['request']
    expected_schema=strict_output_schema(schema)
    if (data['prompt']!=prompt or json.loads(data['output_schema_json'])!=expected_schema
            or data['knowledge_reading_ref']!=reading_ref
            or data['source_manifest_digest']!=source_manifest_digest(sources)
            or data['input_revisions']!=input_revisions or data['review_contract_version']!=version):
        raise ValueError('PROCESS_COMPLETED_SOURCE_INPUT_MISMATCH')
    value=json.loads(native['value_json'])
    try:Draft202012Validator(expected_schema).validate(value)
    except ValidationError as exc:raise ValueError('PROCESS_COMPLETED_SOURCE_OUTPUT_INVALID') from exc
    return value


async def revalidate_answer(client,*,runtime,answer_revision,output_dir,infer,provider='codex',max_repairs=1,
        repair_from_revision=None,quality_only=False,completed_source_observation_revision=None):
    """Explicitly review one saved answer under the current review contract.

    Same base revision/contract/budget identifies the operation. Sequential
    duplicates replay the recorded revision without another model call. The
    Wiki publication CAS prevents two revisions from overwriting the same head;
    external dispatch protection depends on the supplied provider adapter.
    """
    if not 0<=max_repairs<=2:raise ValueError('PROCESS_RESPONSE_REPAIR_BUDGET_REQUIRED')
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    original=await client.read_asset(answer_revision)
    packet=json.loads(original['asset']['content_json'])
    if packet.get('contract_version') not in ('boi/process-user-result@1','boi/process-user-result@2','boi/process-user-result@3'):
        raise ValueError('PROCESS_REVALIDATE_SAVED_ANSWER_REQUIRED')
    request={'base_answer_revision':answer_revision,'review_contract_version':RESPONSE_REVIEW_VERSION,
        'max_repairs':max_repairs,'purpose':'explicit_saved_answer_revalidation'}
    stored_failure=None
    completed_source=None
    if completed_source_observation_revision is not None:
        if quality_only or repair_from_revision is not None or max_repairs!=0:
            raise ValueError('PROCESS_COMPLETED_SOURCE_REPLAY_SCOPE')
        observed=await client.read_asset(completed_source_observation_revision)
        if observed['asset']['kind']!='pack' or observed['sources']!=original['sources']:
            raise ValueError('PROCESS_COMPLETED_SOURCE_RECORD_MISMATCH')
        completed_source=json.loads(observed['asset']['content_json'])
        request['completed_source_observation_revision']=completed_source_observation_revision
    if quality_only:
        from .boi_process_explanation_quality import QUALITY_VERSION,QUALITY_PRESENTATION_VERSION
        if repair_from_revision is not None or max_repairs!=0:raise ValueError('PROCESS_QUALITY_REFRESH_SCOPE')
        prior=await client.call('boi_process_result',{'revision':answer_revision})
        binding=prior['answer_review_binding'];old=packet.get('response_review',{});attempt=old.get('attempts',[{}])[-1]
        from .boi_process_quality_resume import quality_contract_revalidation_allowed, quality_isolation_revalidation_allowed
        if not quality_contract_revalidation_allowed(packet,binding):
            raise ValueError('PROCESS_QUALITY_REFRESH_CONFIRMED_SOURCE_REQUIRED')
        if quality_isolation_revalidation_allowed(packet,binding):
            request['execution_isolation_version']='boi/codex-no-plugins@1'
        stored_failure={'assessment':attempt['review'],'source_answer_revision':answer_revision,
            'prior_provider':attempt['provider'],'quality_review':attempt['quality_review'],'refresh_quality':True}
        request.update(purpose='explicit_explanation_quality_revalidation',quality_contract_version=QUALITY_VERSION,quality_presentation_version=QUALITY_PRESENTATION_VERSION)
    if repair_from_revision is not None:
        if max_repairs<1:raise ValueError('PROCESS_STORED_FAILURE_REPAIR_BUDGET_REQUIRED')
        failure=original;seen=set()
        while failure['revision']!=repair_from_revision:
            if failure['revision']['ref'] in seen or not failure.get('previous_revision'):
                raise ValueError('PROCESS_STORED_FAILURE_NOT_IN_ANSWER_HISTORY')
            seen.add(failure['revision']['ref']);failure=await client.read_asset(failure['previous_revision'])
            if failure['logical_id']!=original['logical_id']:raise ValueError('PROCESS_STORED_FAILURE_IDENTITY_CHANGED')
        failure_packet=json.loads(failure['asset']['content_json']);old_review=failure_packet.get('response_review',{})
        if (old_review.get('review_contract_version')!=RESPONSE_REVIEW_VERSION
                or old_review.get('external_execution_state')=='unknown' or not old_review.get('attempts')):
            raise ValueError('PROCESS_STORED_FAILURE_REVIEW_CONTRACT_REQUIRED')
        attempt=old_review['attempts'][-1]
        if (not attempt.get('review') or not attempt.get('check',{}).get('assessment_complete')
                or attempt['check'].get('model_assessment_accepts_answers')):
            raise ValueError('PROCESS_STORED_REPAIR_VALID_FAILURE_REQUIRED')
        if (failure['sources']!=original['sources'] or failure_packet['questions']!=packet['questions']
                or any(failure_packet['wiki_metadata'].get(k)!=packet['wiki_metadata'].get(k)
                    for k in ('asset_revision','review_revision'))
                or response_proposal(attempt['answer'])['answers']!=response_proposal(packet['answer'])['answers']):
            raise ValueError('PROCESS_STORED_FAILURE_INPUTS_CHANGED')
        stored_failure={'assessment':attempt['review'],'source_answer_revision':failure['revision'],
            'prior_provider':attempt['provider'],'quality_review':attempt['quality_review']}
        prior_patch=attempt.get('repair')
        if prior_patch and prior_patch.get('status')=='invalid_repair':
            from agent_kit.python.boi_process_response_review import RESPONSE_REPAIR_PRESENTATION_VERSION
            if old_review.get('repair_presentation_contract_version')==RESPONSE_REPAIR_PRESENTATION_VERSION:
                raise ValueError('PROCESS_REPAIR_UNCHANGED_INVALID_PATCH')
            stored_failure['reusable_invalid_patch']={**prior_patch,'base_proposal':response_proposal(attempt['answer'])}
        save('stored-failure.json',failure)
        request.update(purpose='repair_recorded_answer_failures',repair_from_revision=repair_from_revision,
            repair_operation_version='boi/process-stored-failure-repair@1')
    request_digest=semantic_digest(request)
    head=next((a for a in (await client.catalog_assets(namespace=original['namespace'],kind='pack'))['items']
        if a['logical_id']==original['logical_id']),None)
    if head is None:raise ValueError('PROCESS_REVALIDATE_ANSWER_HEAD_MISSING')
    current=await client.read_asset(head['revision']);seen=set()
    # Inspect only this answer's immutable revision chain, not other answers.
    while True:
        if current['revision']['ref'] in seen:raise ValueError('PROCESS_REVALIDATE_HISTORY_CYCLE')
        seen.add(current['revision']['ref'])
        content=json.loads(current['asset']['content_json'])
        if content.get('revalidation',{}).get('request_digest')==request_digest:
            meaning,review,material,binding=await intake_evidence(client,content['wiki_metadata'])
            visible,withheld=project_answer_evidence(content['answer'],asset=meaning,review=review,material=material,binding=binding)
            content={**content,'answer':visible,'withheld_statements':withheld,'review_binding':binding,
                'view_is_partial':bool(withheld),'historical_asset_preserved':True}
            save('result.json',content);save('answer-asset.json',current)
            return {'status':'partial_replay' if withheld else 'replayed','asset_revision':current['revision'],'new_model_run':False,
                'withheld_statement_count':len(withheld),
                'answer_review_status':content['response_review']['status'],'whole_plan_qualified':False}
        if current['revision']==answer_revision:break
        if not current.get('previous_revision'):raise ValueError('PROCESS_REVALIDATE_BASE_NOT_IN_HISTORY')
        current=await client.read_asset(current['previous_revision'])
        if current['logical_id']!=original['logical_id']:raise ValueError('PROCESS_REVALIDATE_HISTORY_IDENTITY_CHANGED')
    if head['revision']!=answer_revision:raise ValueError('PROCESS_REVALIDATE_ANSWER_CHANGED')
    if packet.get('response_review',{}).get('external_execution_state')=='unknown':
        save('result.json',packet);save('answer-asset.json',original)
        return {'status':'external_review_result_unknown','asset_revision':original['revision'],
            'answer_review_status':'unresolved_answer_review','new_model_run':False,
            'needed_action':'Reconcile the recorded external execution before dispatching another review.',
            'whole_plan_qualified':False}
    metadata=packet['wiki_metadata']
    meaning,review,review_material,review_binding=await intake_evidence(client,metadata)
    sources=await source_readings(client,original['sources'])
    roots=[{'revision':answer_revision,'role':'prior_answer','reason':'Revalidate this exact saved answer.',
        'stages':['explain','review']},*answer_dependencies(meaning,review)]
    if completed_source is not None:
        # Retain the original reading identity, not a relabelled new model input.
        roots=original['asset']['dependencies']
        historical=await client.restore_task_knowledge(original['definition_reading_ref'],original['sources'],
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
        # Historical restore alone never authorizes new quality work. Recheck
        # current admission with the original roots/purpose before replay.
        reading=await client.read_task_knowledge({'sources':original['sources'],'namespace':original['namespace'],
            'purpose':historical['context']['purpose'],'roots':roots,'tool_use':'provenance_only'},
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
        # Receipts identify deliveries and may change even for identical inputs.
        # Preserve the observed review's identity only after exact current-context
        # equivalence; never relabel its evidence with the fresh receipt.
        if reading['context']!=historical['context']:
            raise ValueError('PROCESS_COMPLETED_SOURCE_READING_CHANGED')
        save('current-admission-reading.json',reading)
        reading=historical
    else:
        reading=await client.read_task_knowledge({'sources':original['sources'],'namespace':original['namespace'],
            'purpose':'Explicit saved-answer revalidation','roots':roots,'tool_use':'provenance_only'},
            principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    context=reading['context'];questions=packet['questions']
    save('prior-answer.json',original);save('request.json',request);save('reading.json',reading);save('sources.json',sources)
    def validate(proposal):
        value=SourceExplanation.model_validate(proposal).model_dump(mode='json')
        value['contract_version']='boi/process-answer-draft@2'
        bound=bind_process_answers_v2(value,context=context,sources=sources,questions=questions)
        check_answer_evidence(bound,asset=meaning,review=review,material=review_material,binding=review_binding)
        return bound
    proposal=response_proposal(packet['answer']);proposal['context_digest']=context['context_digest']
    before=validate(proposal)
    # Exact source/definition/review roots must reach the model-work package,
    # not merely the prose prompt and acknowledged reading receipt.
    if completed_source is not None:
        from .boi_process_response_review import response_material,response_review_selection,response_review_prompt,response_review_schema
        replay_material=response_material(answers=before,context=context,sources=sources,questions=questions)
        replay_selection=response_review_selection(replay_material)
        completed_source_review_value(completed_source,prompt=response_review_prompt(replay_material,replay_selection,context),
            schema=response_review_schema(selection=replay_selection,material=replay_material),reading_ref=reading['reading_ref'],
            sources=original['sources'],input_revisions=[d['revision'] for d in roots if d['role'] in
                ('requested_process_meaning','requested_source_note','review','prior_answer')],version=RESPONSE_REVIEW_VERSION)
    replayed_source=False
    def infer_revalidation(**kwargs):
        nonlocal replayed_source
        if completed_source is not None:
            refs=[d['revision'] for d in roots if d['role'] in ('requested_process_meaning','requested_source_note','review','prior_answer')]
            if not replayed_source:
                value=completed_source_review_value(completed_source,prompt=kwargs['prompt'],schema=kwargs['schema'],
                    reading_ref=reading['reading_ref'],sources=original['sources'],input_revisions=refs,version=RESPONSE_REVIEW_VERSION)
                replayed_source=True
                return value,{'status':'completed','native_observation_revision':completed_source_observation_revision,
                    'new_model_dispatch':False,'observation_replayed':True}
            return infer(**kwargs,input_revisions=refs)
        return infer(**kwargs,input_revisions=[r['revision'] for r in roots[1:]]+[answer_revision])
    bound,response_review=await review_response(bound=before,context=context,sources=sources,questions=questions,
        output_dir=root/'response-review',infer=infer_revalidation,validate_repair=validate,provider=provider,max_repairs=max_repairs,
        reading_ref=reading['reading_ref'],stored_failure=stored_failure)
    from agent_kit.python.boi_process_response_review import unchanged_answer_disagreement
    disagreement=unchanged_answer_disagreement(packet,bound,response_review)
    if disagreement:
        response_review={**response_review,'status':'unresolved_answer_review','assessment_disagreement':disagreement,
            'needed_action':'Review the conflicting judgments or repair the recorded failure with the same exact evidence.'}
        save('assessment-disagreement.json',disagreement)
    new_metadata={'origin':'actual_mcp_readings','context_digest':context['context_digest'],
        'asset_revision':meaning['revision'],'review_revision':review['revision'] if review else None,
        'evidence_mode':'reviewed_candidate' if review else 'original_source_only','authority':meaning['asset']['authority'],
        **{k:context[k] for k in ('source_fidelity','domain_verdict','task_readiness','dependency_completeness','display_status')}}
    result={**packet,'contract_version':'boi/process-user-result@3','answer':bound,'response_review':response_review,
        'wiki_metadata':new_metadata,'review_binding':review_binding,
        'review_dependency_check':check_answer_evidence(bound,asset=meaning,review=review,material=review_material,binding=review_binding),
        'revalidation':{**request,'request_digest':request_digest,
            'prior_reading_receipt':original['definition_reading_ref'],'new_reading_receipt':reading['reading_ref'],
            'original_answer_digest':semantic_digest(packet['answer']),'rebound_answer_digest':semantic_digest(before),
            'semantic_truth_proven':False,'new_answer_generation':False},'whole_plan_qualified':False}
    saved=await client.propose_asset({'logical_id':original['logical_id'],'namespace':original['namespace'],
        'title':original['title'],'description':'Previously saved answer revalidated with bounded source-only repair; prior revisions preserved.',
        'kind':'pack','sources':original['sources'],'content_json':json.dumps(result,ensure_ascii=False),
        'definition_reading_ref':reading['reading_ref'],'dependencies':roots,'previous_revision':answer_revision},
        idempotency_key='process-answer-revalidation:'+request_digest)
    save('result.json',result);save('answer-asset.json',saved)
    render_process_result(result,root/'result.html',sources=sources)
    return {'status':'recorded','asset_revision':saved['revision'],'previous_revision':answer_revision,
        'answer_review_status':response_review['status'],'view_path':str(root/'result.html'),
        'whole_plan_qualified':False}


def render_result(packet,path):
    """Compatibility view when only the historical packet is available."""
    render_process_result(packet,path)
