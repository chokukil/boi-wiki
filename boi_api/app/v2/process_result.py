"""Authorized view of an existing process answer, using Wiki evidence services.

Reading does not run an agent, issue a new review receipt, or qualify a source.
Stored packet prose/metadata cannot provide runtime authority. Original answer
bindings are recomputed from the exact historical reading and original fields.
"""
import copy,json

from ..governed_runtime.semantic_binding_contract import RevisionRef
from ..governed_runtime.source_envelope import ArtifactEnvelope,byte_digest


def process_node_changes(previous,current):
    """Compare stable typed IDs, without inferring semantic equivalence."""
    def nodes(draft):
        return {(r['process_ref'],kind,n['term_id' if kind=='terms' else 'assertion_id']):
            (f'/records/{ri}/{kind}/{i}',n) for ri,r in enumerate(draft.get('records',[]))
            for kind in ('terms','assertions') for i,n in enumerate(r[kind])}
    old,new=nodes(previous),nodes(current);changes=[]
    for key in sorted(set(old)|set(new)):
        before,after=old.get(key),new.get(key)
        if before==after:continue
        changes.append({'node_id':key[2],'kind':key[1],
            'operation':'added' if before is None else 'retracted' if after is None else 'changed' if before[1]!=after[1] else 'pointer_moved',
            'previous_pointer':before[0] if before else None,'current_pointer':after[0] if after else None,
            'previous_value':before[1] if before else None,'current_value':after[1] if after else None})
    return changes


def review_binding_display(binding):
    """Keep native authorship/reference checks distinct from execution evidence."""
    status=binding['status']
    labels={'bound':'확인됨','partially_bound':'일부 확인됨','unconfirmed':'미확인'}
    if binding.get('native_observation_provenance') and status in ('bound','partially_bound'):
        return ('native_observation_'+status+'_execution_unattested',
            'native 검토 기록·참조 '+labels[status]+' / 실행 미증명')
    return status,labels.get(status,status)


def read_process_result(intake, principal, request):
    from .domain_intake import DomainAssetReadRequest
    from .process_review_binding import ProcessReviewBindingRequest,read_recorded_sources
    from agent_kit.python.boi_process_answer_v2 import bind_process_answers_v2
    from agent_kit.python.boi_process_response_review import response_proposal
    from agent_kit.python.boi_process_user_result import project_answer_evidence

    stored=intake.read_asset(principal,request)
    packet=json.loads(stored['asset']['content_json'])
    if packet.get('contract_version') not in ('boi/process-user-result@2','boi/process-user-result@3'):
        raise ValueError('PROCESS_RESULT_CONTRACT_REQUIRED')
    authorization,work=intake._work(principal)
    sources=[ArtifactEnvelope.model_validate(s) for s in stored['sources']]
    reading=RevisionRef.model_validate(stored['definition_reading_ref'])
    context=work.contexts.validate_reading(authorization=authorization,revision=reading,sources=sources,require_current=False)
    def asset(ref):
        return intake.read_asset(principal,DomainAssetReadRequest(revision=ref,lane='provisional'))
    dependencies=stored['asset']['dependencies']
    meanings=[d['revision'] for d in dependencies if d['role'] in ('requested_process_meaning','requested_source_note')]
    reviews=[d['revision'] for d in dependencies if d['role']=='review']
    # Revalidated answers retain the same explicit meaning/review dependencies.
    if len(meanings)!=1 or len(reviews)>1:
        raise ValueError('PROCESS_RESULT_DEPENDENCY_BINDING_REQUIRED')
    meaning=asset(meanings[0]);review=asset(reviews[0]) if reviews else None
    if packet['wiki_metadata'].get('asset_revision')!=meaning['revision'] or packet['wiki_metadata'].get('review_revision')!=(review['revision'] if review else None):
        raise ValueError('PROCESS_RESULT_REVIEW_BINDING_MISMATCH')
    material=json.loads(review['asset']['content_json']) if review else {'check':{'failed_use_pointers':[]}}
    projections=read_recorded_sources(intake,principal,sources,packet['answer'])
    proposal=response_proposal(packet['answer']);proposal['contract_version']='boi/process-answer-draft@2'
    rebound=bind_process_answers_v2(proposal,context=context.model_dump(mode='json'),sources=projections,questions=packet['questions'])
    if rebound!=packet['answer']:
        raise ValueError('PROCESS_RESULT_STORED_BINDING_MISMATCH')
    from .process_answer_review_binding import answer_review_binding
    answer_link=answer_review_binding(work,authorization,stored,packet,context.model_dump(mode='json'),projections,read_asset=asset)
    linkage=intake.read_process_review_binding(principal,ProcessReviewBindingRequest(
        candidate_revision=meaning['revision'],review_revision=review['revision'] if review else None))
    visible,withheld=project_answer_evidence(rebound,asset=meaning,review=review,material=material,binding=linkage)
    operative_check=linkage.get('check',{})
    # Authority and qualification state come from the authenticated Wiki asset
    # and immutable reading, not packet['wiki_metadata'] authored by a caller.
    packet=copy.deepcopy(packet)
    packet.update(answer=visible,review_binding=linkage,withheld_statements=withheld,
        view_is_partial=bool(withheld),historical_asset_preserved=True)
    packet['wiki_metadata']={'origin':'wiki_authorized_result_read','answer_revision':stored['revision'],
        'asset_revision':meaning['revision'],'review_revision':review['revision'] if review else None,
        'authority':meaning['asset']['authority'],'display_status':stored['status'],
        'context_digest':context.context_digest,
        **{k:getattr(context,k) for k in ('source_fidelity','domain_verdict','task_readiness','dependency_completeness')},
        'qualification_scope':'original acknowledged reading; no new evaluation on view',
        'canonical_projection_eligible':False}
    packet['source_review_failures']=operative_check.get('source_review',{}).get('failures',[])
    packet['source_review_protocol_failures']=operative_check.get('source_review',{}).get('review_protocol_failures',[])
    packet['unresolved_use_pointers']=operative_check.get('failed_use_pointers',[])
    receipts=[]
    for item in (stored,meaning,review):
        if item and item.get('definition_reading_ref'):
            ref=RevisionRef.model_validate(item['definition_reading_ref'])
            work.contexts.validate_reading(authorization=authorization,revision=ref,
                sources=[ArtifactEnvelope.model_validate(s) for s in item['sources']],require_current=False)
            receipts.append({'asset_revision':item['revision'],'reading_ref':ref.model_dump(mode='json'),
                'receipt':work.ledger.read(ref.ref).payload,'newly_issued':False})
    history=[];previous=stored['previous_revision'];seen=set();history_status='complete'
    while previous and len(history)<20:
        if previous['ref'] in seen:
            history_status='unavailable';break
        seen.add(previous['ref'])
        try:old=asset(previous)
        except (ValueError,KeyError):
            # Optional history failure does not hide the authorized current
            # answer. Do not expose inaccessible titles, source data or errors.
            history_status='unavailable';break
        history.append({'revision':old['revision'],'title':old['title'],'reading_ref':old['definition_reading_ref'],
            'ui_url':'/domain-results/'+old['revision']['revision_digest'].split(':')[1]})
        previous=old['previous_revision']
    meaning_history=[];meaning_history_status='complete';current=meaning;seen=set()
    while current.get('previous_revision') and len(meaning_history)<20:
        ref=current['previous_revision']
        if ref['ref'] in seen:meaning_history_status='unavailable';break
        seen.add(ref['ref'])
        try:
            prior=asset(ref);current_content=json.loads(current['asset']['content_json']);prior_content=json.loads(prior['asset']['content_json'])
            if prior['logical_id']!=current['logical_id']:raise ValueError('PROCESS_HISTORY_IDENTITY_CHANGED')
            item={'previous_revision':prior['revision'],'current_revision':current['revision'],
                'changes':process_node_changes(prior_content.get('draft',{}),current_content.get('draft',{})),
                'source_revision_changed':prior_content.get('draft',{}).get('source_revision_digest')!=current_content.get('draft',{}).get('source_revision_digest'),
                'basis':'Stored typed ID/value comparison; no new semantic evaluation.',
                'previous_reading_ref':prior['definition_reading_ref'],'prior_review_status':'not_linked'}
            old_notes=prior_content.get('draft',{}).get('limitations',[])
            item['unchanged_candidate_notes']=[{'pointer':f'/limitations/{i}','text':note,
                'authority':'candidate_note_unverified'} for i,note in enumerate(current_content.get('draft',{}).get('limitations',[]))
                if i<len(old_notes) and old_notes[i]==note]
            repair=current_content.get('repair_history',{})
            if repair.get('original_candidate')==prior['revision'] and repair.get('original_review'):
                old_review=asset(repair['original_review'])
                old_binding=intake.read_process_review_binding(principal,ProcessReviewBindingRequest(
                    candidate_revision=prior['revision'],review_revision=old_review['revision']))
                item.update(prior_review_revision=old_review['revision'],prior_review_status=old_binding['status'],
                    prior_review_failures=old_binding.get('check',{}).get('source_review',{}).get('failures',[]),
                    prior_review_is_historical_model_opinion=True)
            meaning_history.append(item);current=prior
        except (ValueError,KeyError,TypeError):
            meaning_history_status='unavailable';break
    if current.get('previous_revision') and len(meaning_history)>=20:meaning_history_status='more_available'
    from .process_citation_display import citation_display,citation_text
    display=citation_display(packet,projections)
    response_status=packet.get('response_review',{}).get('status')
    fulfilled=(answer_link.get('status')=='bound' and answer_link.get('model_assessment_accepts_answers') is True
        and response_status=='accepted_by_model_review' and not withheld)
    candidate_execution_status,candidate_binding_text=review_binding_display(linkage)
    answer_execution_status,answer_binding_text=review_binding_display(answer_link)
    delivery_state={'origin':'wiki_authorized_result_read','authority':stored['asset']['authority'],
        'display_status':'PROVISIONAL','answer_request_fulfilled':fulfilled,
        'candidate_review_execution_binding':candidate_execution_status,
        'answer_review_execution_binding':answer_execution_status,
        'stored_answer_model_opinion':response_status,'source_fidelity':context.source_fidelity,
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}
    authority_label={'candidate':'후보 자산','legacy_unbound':'근거 미연결 과거 자산'}.get(stored['asset']['authority'],stored['asset']['authority'])
    status_text=('Wiki 상태 · '+authority_label+' / '+stored['status']+'\n'
        '공정 후보 검토의 실행 연결: '+candidate_binding_text+'\n'
        '이 답변 검토의 실행 연결: '+answer_binding_text+'\n'
        '저장된 답변 모델 의견: '+str(response_status)+' (실행 연결과 별개)\n'
        '이 답변 요청 상태: '+('저장 답변 제공' if fulfilled else '부분 제공 · 미완료')+'\n'
        '과학적 진위: 미검증. 전체 계획 완료: 아님.')
    delivery_notes=[]
    if answer_link.get('status')=='bound':
        for failure in answer_link.get('check',{}).get('failures',[]):
            pointer=failure.get('target_pointer','')
            target=next((s for ai,a in enumerate(rebound['answers']) for part in ('sentences','limitations')
                for si,s in enumerate(a[part]) if pointer==f'/answers/{ai}/{part}/{si}'),None)
            if target:
                label='인용 보완 필요' if failure['failure_kind']=='incomplete_citation' else '원문 근거 확인 필요'
                delivery_notes.append(label+': “'+target['text']+'”')
        delivery_notes.extend('설명 보완 필요: '+r['reason'] for r in answer_link.get('check',{}).get('quality_failures',[]))
        delivery_notes.extend('아직 충분히 답하지 못한 부분: '+r['reason'] for r in answer_link.get('check',{}).get('unanswered_requests',[]))
    if not fulfilled and not delivery_notes:delivery_notes.append('답변 검토가 아직 끝나지 않아 일부 설명은 확인이 필요합니다.')
    followup_history=[]
    for question in packet['questions']:
        previous=question.get('previous_answer_revision')
        if previous and any(a.revision.model_dump(mode='json')==previous for a in context.assets):
            prior=asset(previous)
            followup_history.append({'revision':prior['revision'],
                'ui_url':'/domain-results/'+prior['revision']['revision_digest'].split(':',1)[1]})
    return {'contract_version':'boi/process-result-view@1','packet':packet,'sources':projections,
        'followup_history':followup_history,
        'citation_display':display,'readable_text':citation_text(display)+'\n\n잠정 자료에 근거한 설명입니다. 과학적 진위는 별도로 검증하지 않았습니다.'+
            ('\n'+'\n'.join(delivery_notes) if delivery_notes else ''),
        'delivery_notes':delivery_notes,
        'operational_details_text':status_text,
        'delivery_state':delivery_state,'user_request_fulfilled':fulfilled,
        'answer_review_binding':answer_link,
        'meaning_history':meaning_history,'meaning_history_status':meaning_history_status,
        'receipt_scope':{'ui_url_is_receipt':False,'reading_receipts':'receipts[].reading_ref',
            'asset_and_review_revisions_are_receipts':False,'new_receipts_issued':False},
        'stored_answer_revision':stored['revision'],'history':history,'history_next_revision':previous,
        'history_status':history_status if history_status!='complete' or previous is None else 'more_available',
        'receipts':receipts,'ui_url':'/domain-results/'+stored['revision']['revision_digest'].split(':')[1],
        'authority':stored['asset']['authority'],'status':'PROVISIONAL','reference_binding':'recomputed_equal',
        'review_binding':linkage,
        'model_review_record':'Stored model opinion; review execution linkage checked separately, source entailment and scientific truth not proven.',
        'canonical_projection_eligible':False,'new_model_runs':0,'new_review_receipts':0}
