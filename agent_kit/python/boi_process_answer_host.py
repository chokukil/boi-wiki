"""Native proposal adapter around the existing process answer service.

Wiki owns every asset, reading, model task and receipt. The native client writes
an untrusted answer; a separate existing worker reviews it. No domain routing,
client-specific meaning, source extraction or new workflow engine lives here.
"""
import copy,json
import uuid
from pathlib import Path
from typing import Literal, Annotated
from pydantic import Field, TypeAdapter
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessQuotation

from .boi_mcp_server import BoiLocalMCPServer
from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef, semantic_digest
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref
from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
from .boi_process_intake import read_stored_intake, source_readings
from .boi_process_user_result import (SourceExplanation, normalize_process_questions,
    intake_evidence, answer_dependencies, source_explanation_prompt, explain_intake, source_explanation_generation_schema)
from .boi_process_response_review import RESPONSE_REVIEW_VERSION
from .boi_process_answer_layout import AnswerLayout,rejected_layout,proposal_layout_errors
from .boi_process_answer_v2 import RequestFacet,RecommendationStatement,answer_evidence_groups,statement_evidence_error

CONTRACT='boi/native-process-answer-request@1'
_UNSPECIFIED_LENGTH=object()


def pre_review_binding_error(proposal):
    """Structural failures only; never a semantic judgment or review retry."""
    layout_error=rejected_layout(proposal)
    if layout_error:return layout_error
    value=SourceExplanation.model_validate(proposal)
    for answer in value.answers:
        if answer.request_plan is not None:
            for facet in answer.request_plan.facets:
                if facet.aspect != 'presentation' and not facet.citations and not facet.unresolved_reason:
                    return 'ANSWER_PLAN_MEANING_OR_UNRESOLVED_REQUIRED'
    return None


def plan_correction_preserves_answer(previous,proposed):
    def without_plan(value):
        value=copy.deepcopy(value)
        for answer in value['answers']:answer.pop('request_plan',None)
        return value
    return without_plan(previous)==without_plan(proposed)


def proposal_correction_key(proposal_id, content):
    """Preserve existing keys; bound long identities without changing content."""
    key=proposal_id+':correction:'+semantic_digest(content)
    return key if len(key)<=240 else 'proposal-correction:'+semantic_digest([proposal_id,content])


def source_schema_revalidation_allowed(packet,binding):
    """Only completed failures addressed by newer reference/type constraints."""
    from .boi_process_response_review import RESPONSE_ASSESSMENT_SCHEMA_VERSION
    report=packet.get('response_review',{});attempts=report.get('attempts',[])
    mode=binding.get('assessment_reference_schema',{}).get('mode')
    diagnostic=binding.get('check',{}).get('diagnostic')
    addressed=(mode=='unbounded_identifiers' and diagnostic=='ANSWER_EVAL_UNKNOWN_EVIDENCE') or (
        mode=='exact_inventory_enum' and diagnostic in ('ANSWER_EVAL_SOURCE_RUNTIME_CONFUSION','ANSWER_EVAL_RUNTIME_SOURCE_CONFUSION'))
    return (binding.get('status')=='bound'
        and addressed
        and binding.get('assessment_reference_schema',{}).get('origin')=='admitted_model_work_input'
        and binding.get('check',{}).get('review_failure')=='invalid_assessment'
        and report.get('external_execution_state')=='known'
        and report.get('assessment_schema_version')!=RESPONSE_ASSESSMENT_SCHEMA_VERSION
        and bool(attempts) and attempts[-1]['provider'].get('status')=='completed')


from .boi_process_quality_resume import quality_contract_revalidation_allowed, quality_isolation_revalidation_allowed


class ProcessQuestionInput(FrozenContract):
    """Caller-supplied question text, distinct from attached source revisions."""
    contract_version: Literal['boi/process-question-input@1']='boi/process-question-input@1'
    question:Ref


class ProcessQuestionInputV2(ProcessQuestionInput):
    """Exact requested constraint; explicit null means no body length cap."""
    contract_version: Literal['boi/process-question-input@2']='boi/process-question-input@2'
    max_body_characters: int | None = Field(ge=1,le=10000,strict=True)
    response_request: Ref | None = Field(default=None,exclude_if=lambda v:v is None)
    previous_answer_revision: RevisionRef | None = Field(default=None,exclude_if=lambda v:v is None)


QUESTION_INPUT=TypeAdapter(Annotated[ProcessQuestionInput|ProcessQuestionInputV2,Field(discriminator='contract_version')])


def input_questions(data):
    questions=normalize_process_questions(data.question)
    if isinstance(data,ProcessQuestionInputV2):
        constraints=data.model_dump(mode='json',exclude={'contract_version','question'})
        questions=normalize_process_questions([{**q,**constraints} for q in questions])
    return questions


Index = Annotated[int, Field(strict=True, ge=0)]

class ReadingSourceQuote(FrozenContract):
    kind: Literal['source_quote'] = 'source_quote'
    source_index: Index
    quotation: ProcessQuotation

class ReadingSourceScope(FrozenContract):
    kind: Literal['source_scope'] = 'source_scope'
    source_index: Index
    reason: Ref

class ReadingMeaning(FrozenContract):
    kind: Literal['meaning'] = 'meaning'
    asset_index: Index
    target_pointer: Ref

class ReadingFact(FrozenContract):
    kind: Literal['source_reported_fact','interpretation']
    text: Ref
    citations: tuple[Annotated[ReadingSourceQuote | ReadingMeaning | ReadingSourceScope, Field(discriminator='kind')], ...] = Field(min_length=1,
        description='Use positive source/meaning citations for facts. Add source_scope when the same interpretation also depends on examining the complete supplied source. Scope does not prove absence or replace positive evidence.')

class ReadingGap(FrozenContract):
    kind: Literal['evidence_gap'] = 'evidence_gap'
    text: Ref
    citations: tuple[Annotated[ReadingSourceScope | ReadingSourceQuote | ReadingMeaning,Field(discriminator='kind')], ...] = Field(min_length=1,
        description='Include complete source_scope for the gap. If the same explanation states supported facts, also cite their source or meaning evidence.')

class ReadingRecommendation(RecommendationStatement):
    citations: tuple[Annotated[ReadingSourceScope | ReadingSourceQuote | ReadingMeaning,Field(discriminator='kind')], ...] = Field(min_length=1)


ReadingStatement = Annotated[ReadingFact | ReadingGap | ReadingRecommendation, Field(discriminator='kind')]

class ReadingRequestFacet(RequestFacet):
    citations: tuple[Annotated[ReadingMeaning|ReadingSourceQuote|ReadingSourceScope,Field(discriminator='kind')],...]=()

class ReadingRequestPlan(FrozenContract):
    facets: tuple[ReadingRequestFacet,...]=Field(min_length=1)

class ReadingAnswer(FrozenContract):
    question_index: Index
    sentences: tuple[ReadingStatement, ...] = Field(min_length=1)
    limitations: tuple[ReadingStatement, ...] = ()
    layout: AnswerLayout | None = Field(default=None,exclude_if=lambda v:v is None)
    request_plan: ReadingRequestPlan | None = Field(default=None,exclude_if=lambda v:v is None,
        description='Map actual request facets to source/meaning evidence and the answer statements that address them. Preserve unresolved interpretation explicitly. This candidate plan is not a truth judgment.')

class ReadingExplanation(FrozenContract):
    contract_version: Literal['boi/reading-scoped-explanation@1'] = 'boi/reading-scoped-explanation@1'
    answers: tuple[ReadingAnswer, ...] = Field(min_length=1)


def reading_citation_catalog(request,reading):
    """Indices belong only to this immutable request/authorized reading."""
    data=json.loads(request['asset']['content_json'])
    return {'request_revision':request['revision'],'reading_ref':request['definition_reading_ref'],
        'questions':[{'question_index':i,**q} for i,q in enumerate(data['questions'])],
        'sources':[{'source_index':i,**source} for i,source in enumerate(request['sources'])],
        'assets':[{'asset_index':i,**{k:asset[k] for k in ('revision','kind','authority')}}
            for i,asset in enumerate(reading['context']['assets'])]}


def reading_proposal_schema(catalog):
    schema=ReadingExplanation.model_json_schema()
    # New generation supplies a plan in the same inference. Historical stored
    # proposals without a plan remain readable but gain no inferred plan.
    answer_schema=schema['$defs']['ReadingAnswer']
    answer_schema['properties']['request_plan']={'$ref':'#/$defs/ReadingRequestPlan'}
    schema['$defs']['ReadingRequestPlan']['description']=ReadingAnswer.model_fields['request_plan'].description
    answer_schema['required'].append('request_plan')
    domains={'ReadingMeaning':('asset_index',[a['asset_index'] for a in catalog['assets'] if a['kind']=='definition']),
        'ReadingSourceQuote':('source_index',[s['source_index'] for s in catalog['sources']]),
        'ReadingSourceScope':('source_index',[s['source_index'] for s in catalog['sources']]),
        'ReadingAnswer':('question_index',[q['question_index'] for q in catalog['questions']])}
    for name,(field,values) in domains.items():
        if values:schema['$defs'][name]['properties'][field]['enum']=values
    return schema


def selected_candidate_index(request,catalog):
    selected=json.loads(request['asset']['content_json'])['intake']['asset_revision']
    return next((a['asset_index'] for a in catalog['assets'] if a['revision']==selected),None)


def reading_reference_errors(raw,catalog):
    errors=[]
    def check(pointer,index,allowed,code):
        if index not in allowed:errors.append({'pointer':pointer,'reason_code':code,'allowed_indices':allowed})
    for ai,answer in enumerate(raw['answers']):
        check(f'/answers/{ai}/question_index',answer['question_index'],list(range(len(catalog['questions']))),'PROCESS_READING_CITATION_INDEX_OUT_OF_RANGE')
        for part,statements in answer_evidence_groups(answer):
            for si,statement in enumerate(statements):
                if part in ('sentences','limitations'):
                    error=statement_evidence_error(statement['kind'],{c['kind'] for c in statement['citations']})
                    if error:errors.append({'pointer':f'/answers/{ai}/{part}/{si}','reason_code':error,
                        'correctable_fields':['kind','citations']})
                for ci,citation in enumerate(statement['citations']):
                    key='asset_index' if citation['kind']=='meaning' else 'source_index'
                    allowed=([a['asset_index'] for a in catalog['assets'] if a['kind']=='definition'] if key=='asset_index' else list(range(len(catalog['sources']))))
                    check(f'/answers/{ai}/{part}/{si}/citations/{ci}/{key}',citation[key],allowed,
                        'PROCESS_READING_MEANING_DEFINITION_REQUIRED' if key=='asset_index' else 'PROCESS_READING_CITATION_INDEX_OUT_OF_RANGE')
    return errors


def reading_evidence_correction_preserves_content(previous,proposed,errors):
    """Permit only identified evidence type/reference fields, preserving prose."""
    def strip(value):
        value=copy.deepcopy(value)
        for error in errors:
            if 'correctable_fields' not in error:continue
            item=value
            for part in error['pointer'].strip('/').split('/'):
                item=item[int(part)] if isinstance(item,list) else item[part]
            for field in error['correctable_fields']:item.pop(field,None)
        return value
    try:return strip(previous)==strip(proposed)
    except (KeyError,IndexError,TypeError,ValueError):return False


def resolve_reading_explanation(proposal,*,request,reading):
    """Expand typed references only; never infer claims or repair quotations."""
    raw=ReadingExplanation.model_validate(proposal).model_dump(mode='json')
    catalog=reading_citation_catalog(request,reading);mappings=[]
    def selected(items,index):
        if index>=len(items):raise ValueError('PROCESS_READING_CITATION_INDEX_OUT_OF_RANGE')
        return items[index]
    answers=[]
    for ai,answer in enumerate(raw['answers']):
        question=selected(catalog['questions'],answer['question_index'])
        item={'question_id':question['id'],'sentences':[],'limitations':[]}
        if 'layout' in answer:item['layout']=answer['layout']
        if answer.get('request_plan'):item['request_plan']={'facets':[]}
        groups=[(part,answer[part],item[part]) for part in ('sentences','limitations')]
        if answer.get('request_plan'):
            groups.append(('request_plan/facets',answer['request_plan']['facets'],item['request_plan']['facets']))
        for part,statements,destination in groups:
            for si,statement in enumerate(statements):
                converted={k:v for k,v in statement.items() if k!='citations'};citations=[]
                for ci,citation in enumerate(statement['citations']):
                    if citation['kind']=='meaning':
                        asset=selected(catalog['assets'],citation['asset_index'])
                        if asset['kind']!='definition':raise ValueError('PROCESS_READING_MEANING_DEFINITION_REQUIRED')
                        resolved={'kind':'meaning','asset_revision':asset['revision'],'target_pointer':citation['target_pointer']}
                    else:
                        source=selected(catalog['sources'],citation['source_index'])
                        resolved={k:v for k,v in citation.items() if k!='source_index'}
                        resolved['source_revision_digest']=source['digest']
                    citations.append(resolved)
                    mappings.append({'pointer':f'/answers/{ai}/{part}/{si}/citations/{ci}',
                        'submitted':citation,'resolved':resolved})
                converted['citations']=citations;destination.append(converted)
        answers.append(item)
    expanded=SourceExplanation(context_digest=reading['context']['context_digest'],answers=answers).model_dump(mode='json')
    return expanded,{'contract_version':'boi/reading-reference-expansion@1','native_proposal':raw,
        'request_revision':request['revision'],'reading_ref':request['definition_reading_ref'],
        'catalog_digest':semantic_digest(catalog),'resolved_proposal_digest':semantic_digest(expanded),
        'reference_mappings':mappings,'semantic_text_changed':False}


async def register_question_input(client,*,namespace,question,attached_sources,max_body_characters=_UNSPECIFIED_LENGTH,
        response_request=None,previous_answer_revision=None):
    """Capture entry-point input before model work in the existing Wiki store.

    The pack is caller-supplied input, not verified human intent or domain truth.
    Repeating the same question/source selection restores the immutable input.
    """
    data=(ProcessQuestionInput(question=question) if max_body_characters is _UNSPECIFIED_LENGTH and response_request is None and previous_answer_revision is None
        else ProcessQuestionInputV2(question=question,max_body_characters=None if max_body_characters is _UNSPECIFIED_LENGTH else max_body_characters,
            response_request=response_request,previous_answer_revision=previous_answer_revision)).model_dump(mode='json')
    identity='question-input:'+semantic_digest({'content':data,'sources':source_manifest_digest(attached_sources)})
    return await client.propose_asset({'namespace':namespace,'logical_id':identity,'kind':'pack',
        'title':'질문과 선택 원문','description':'Caller-supplied question text with separate exact source references; no meaning verdict.',
        'sources':attached_sources,'content_json':json.dumps(data,ensure_ascii=False)},idempotency_key=identity)


def agent_result_view(view,*,base_url=None):
    """Deliver reviewed prose and source passages before linked operational detail.

    Full citation graphs and history remain readable in the exact authorized
    Wiki result revision. This projection does not change the stored answer.
    """
    value=copy.deepcopy(view)
    if base_url and value.get('ui_url'):
        from boi_api.app.v2.process_citation_display import citation_text
        value['product_url']=base_url.rstrip('/')+value['ui_url']
        original=citation_text(value['citation_display'])
        if not value['readable_text'].startswith(original):raise ValueError('PROCESS_AGENT_DELIVERY_TEXT_CHANGED')
        value['readable_text']=citation_text(value['citation_display'],source_url=value['product_url'])+value['readable_text'][len(original):]
        value['delivery_link_scope']='Actual authenticated product route and exact source-quote anchors; access follows the existing Wiki identity and ACL.'
    # Full graphs/history remain in the exact authorized result revision. Sending
    # them repeatedly beside readable_text can truncate the actual MCP delivery.
    packet=value['packet']
    from boi_api.app.v2.process_citation_display import process_semantic_basis
    value['semantic_basis']=process_semantic_basis(packet)
    value['packet']={k:packet[k] for k in ('contract_version','wiki_metadata','questions','whole_plan_qualified') if k in packet}
    if 'answer' in packet:value['packet']['answer_digest']=semantic_digest(packet['answer'])
    for entry in value.get('citation_display',{}).get('sources',[]):
        if entry.get('citation_references'):
            entry.pop('citation_reference',None)
            for reference in entry['citation_references']:
                reference['citation']={k:v for k,v in reference['citation'].items() if k!='graph_evidence'}
                reference['full_citation_in_answer_revision']=value['stored_answer_revision']
    value['receipts']=[{k:r[k] for k in ('asset_revision','reading_ref','newly_issued') if k in r}
        for r in value.get('receipts',[])]
    value['presentation_scope']={'omitted':'Repeated answer graphs and full review/history/receipt payloads; read the exact stored result revision for these records.',
        'full_record_revision':value['stored_answer_revision'],'conditions_citations_sources_history_preserved':True}
    # Put the shared human-readable delivery before long audit records. Keep
    # every source/condition/reference in the same result, without duplicating
    # the already server-rendered delivery text.
    front={k:value.pop(k) for k in ('readable_text','delivery_state','citation_display') if k in value}
    return {**front,**value}


class ProcessAnswerHost:
    def __init__(self,client,*,runtime,infer_for,output_dir):
        self.client=client;self.runtime=runtime;self.infer_for=infer_for
        self.output_dir=Path(output_dir)

    async def read_question_input(self,revision):
        asset=await self.client.read_asset(revision)
        if asset['asset']['kind']!='pack':raise ValueError('PROCESS_QUESTION_INPUT_KIND_INVALID')
        data=QUESTION_INPUT.validate_json(asset['asset']['content_json'])
        return asset,data

    async def prepare_selected_definition(self,*,candidate_revision,question,**constraints):
        """Resolve identity from an exact selected definition; never select by name."""
        candidate=await self.client.read_asset(candidate_revision)
        if candidate['asset']['kind']!='definition':
            raise ValueError('PROCESS_QUESTION_CANDIDATE_BINDING_MISMATCH')
        return await self.prepare(namespace=candidate['namespace'],logical_id=candidate['logical_id'],
            question=question,selected_candidate_revision=candidate_revision,**constraints)

    async def prepare_from_input(self,*,question_input_revision,candidate_revision):
        asset,data=await self.read_question_input(question_input_revision)
        candidate=await self.client.read_asset(candidate_revision)
        if candidate['asset']['kind']!='definition' or candidate['namespace']!=asset['namespace']:
            raise ValueError('PROCESS_QUESTION_CANDIDATE_BINDING_MISMATCH')
        if not {semantic_digest(s) for s in asset['sources']} <= {semantic_digest(s) for s in candidate['sources']}:
            # This is a fixable selection error before any answer/model work,
            # not missing evidence or authority to silently switch candidates.
            return {'status':'needs_candidate_selection','reason_code':'PROCESS_QUESTION_ATTACHED_SOURCE_OUTSIDE_MEANING',
                'user_request_fulfilled':False,'new_model_dispatch':False,'namespace':asset['namespace'],
                'question_input_revision':question_input_revision,'question':data.question,
                'attached_sources':asset['sources'],'selected_candidate_revision':candidate_revision,
                'selected_candidate_sources':candidate['sources'],
                'next_action':'Read the current catalog candidates and their source references. Select a candidate covering the exact attached source revisions and retry preparation. A matching label or related definition alone is insufficient; do not discard attached sources or rewrite the question.',
                'whole_plan_qualified':False}
        return await self.prepare(namespace=asset['namespace'],logical_id=candidate['logical_id'],question=data.question,
            question_input_revision=question_input_revision,selected_candidate_revision=candidate_revision)

    async def prepare(self,*,namespace,logical_id,question,question_input_revision=None,max_body_characters=_UNSPECIFIED_LENGTH,
            response_request=None,previous_answer_revision=None,selected_candidate_revision=None):
        explicit_length=max_body_characters is not _UNSPECIFIED_LENGTH
        questions=normalize_process_questions([{'id':'question:'+semantic_digest(question),'question':question,
            'response_request':response_request,'previous_answer_revision':previous_answer_revision}])
        if explicit_length:
            questions=normalize_process_questions([{**q,'max_body_characters':max_body_characters} for q in questions])
        intake=await read_stored_intake(self.client,namespace=namespace,logical_id=logical_id)
        if selected_candidate_revision is not None and (intake is None or intake['asset_revision']!=selected_candidate_revision):
            raise ValueError('PROCESS_QUESTION_CANDIDATE_NOT_CURRENT')
        if intake is None:raise ValueError('PROCESS_ANSWER_INTAKE_NOT_FOUND')
        asset,review,material,binding=await intake_evidence(self.client,intake)
        requirements=answer_dependencies(asset,review)
        if question_input_revision is not None:
            input_asset,input_data=await self.read_question_input(question_input_revision)
            if input_asset['namespace']!=namespace or input_data.question!=question:
                raise ValueError('PROCESS_QUESTION_INPUT_BINDING_MISMATCH')
            pinned_questions=input_questions(input_data)
            if (explicit_length or response_request is not None or previous_answer_revision is not None) and questions!=pinned_questions:
                raise ValueError('PROCESS_QUESTION_INPUT_CONSTRAINT_MISMATCH')
            questions=pinned_questions
            if not {semantic_digest(s) for s in input_asset['sources']} <= {semantic_digest(s) for s in asset['sources']}:
                raise ValueError('PROCESS_QUESTION_ATTACHED_SOURCE_OUTSIDE_MEANING')
            requirements=[*requirements,{'revision':question_input_revision,'role':'user_question_input',
                'reason':'Read exact caller question and selected original source revisions separately.','stages':['explain','review']}]
        previous=questions[0].get('previous_answer_revision')
        if previous:
            prior_answer=await self.client.read_asset(previous)
            prior_packet=json.loads(prior_answer['asset']['content_json'])
            if prior_answer['namespace']!=namespace or not prior_packet.get('answer') or prior_answer['sources']!=asset['sources']:
                raise ValueError('PROCESS_FOLLOWUP_ANSWER_CONTEXT_MISMATCH')
            requirements.append({'revision':previous,'role':'prior_user_answer',
                'reason':'Prior wording for the latest user follow-up; not source evidence.','stages':['explain','review']})
        review_ref=review['revision'] if review else None
        identity=asset['logical_id']+':answers:'+semantic_digest({
            'asset':asset['revision'],'review':review_ref,'questions':questions})
        packs=(await self.client.catalog_assets(namespace=namespace,kind='pack'))['items']
        existing=next((p for p in packs if p['logical_id']==identity),None)
        if existing:return await self.result(existing['revision'],reused=True)
        request_id=identity+':native-request'
        prior=next((p for p in packs if p['logical_id']==request_id),None)
        if prior:
            request=await self.client.read_asset(prior['revision'])
            data=json.loads(request['asset']['content_json'])
            if data['contract_version']!=CONTRACT or data['review_contract']!=RESPONSE_REVIEW_VERSION:
                raise ValueError('PROCESS_NATIVE_REVIEW_CONTRACT_CHANGED')
            if data['questions']!=questions:
                raise ValueError('PROCESS_NATIVE_PREPARED_QUESTION_CHANGED')
            reading=await self.restore(request['definition_reading_ref'],asset['sources'])
        else:
            reading=await self.client.read_task_knowledge({'namespace':namespace,'sources':asset['sources'],
                'purpose':'Native answer from stored process knowledge','roots':requirements,
                'tool_use':'provenance_only'},principal_id=self.runtime['principal'].employee_id,
                policy_digest=self.runtime['authorization'].policy_digest)
            data={'contract_version':CONTRACT,'intake':intake,'questions':questions,'answer_identity':identity,
                'logical_id':logical_id,'namespace':namespace,'review_contract':RESPONSE_REVIEW_VERSION,
                'max_proposals':1,'max_review_calls':2,'max_repairs':0,
                'review_stages':['source_and_citations','explanation_quality']}
            if question_input_revision is not None:data['question_input_revision']=question_input_revision
            saved=await self.client.propose_asset({'namespace':namespace,'logical_id':request_id,'kind':'pack',
                'title':'새 질문의 고정 입력','description':'Native answer input and one-proposal boundary; no verdict.',
                'sources':asset['sources'],'content_json':json.dumps(data,ensure_ascii=False),
                'dependencies':requirements,'definition_reading_ref':reading['reading_ref']},
                idempotency_key=request_id)
            request=await self.client.read_asset(saved['revision'])
        sources=await source_readings(self.client,asset['sources'])
        from .boi_process_answer_v2 import meaning_citation_targets
        meaning_targets=meaning_citation_targets(context=reading['context'],sources=sources,
            asset_revision=asset['revision'])
        from boi_api.app.v2.process_citation_display import process_meaning_catalog
        citation_catalog=reading_citation_catalog(request,reading)
        candidate_index=selected_candidate_index(request,citation_catalog)
        result={'status':'proposal_required','request_revision':request['revision'],
            'reading_ref':reading['reading_ref'],'candidate_revision':asset['revision'],'review_revision':review_ref,
            'proposal_schema':source_explanation_generation_schema(),
            'preferred_submit_tool':'boi_process_answer_submit_reading',
            'reading_proposal_schema':reading_proposal_schema(citation_catalog),
            'reading_citation_catalog':citation_catalog,
            'selected_candidate_asset_index':candidate_index,
            **process_meaning_catalog([{'asset_index':candidate_index,**target} for target in meaning_targets]),
            'operational_input':source_explanation_prompt(asset=asset,review_revision=review_ref,
                review_check=binding.get('check',{}),review_material=material,reading=reading,sources=sources,questions=questions),
            'max_proposals':1,'independent_review_required':True,'new_model_runs':0,
            'user_request_fulfilled':False,'authority':'candidate','scientific_correctness':'not_evaluated'}
        if question_input_revision is not None:result['question_input_revision']=question_input_revision
        saved_reading=next((p for p in packs if p['logical_id']==request['logical_id']+':reading-proposal'),None)
        if saved_reading:
            original=await self.client.read_asset(saved_reading['revision']);raw=json.loads(original['asset']['content_json'])
            if raw['request_revision']!=request['revision']:raise ValueError('PROCESS_SAVED_PROPOSAL_REQUEST_MISMATCH')
            result.update(stored_reading_proposal=raw['proposal'],reading_proposal_revision=original['revision'])
            result['remaining_pre_review_corrections']=max(0,2-raw['pre_review_correction_count'])
            current_errors=reading_reference_errors(raw['proposal'],citation_catalog)
            if current_errors:
                result.update(status='reading_reference_correction_required',reference_errors=current_errors,
                    remaining_pre_review_corrections=max(0,2-raw['pre_review_correction_count']),
                    continuation='Correct the reported reference indices or statement evidence kind/citations using this exact catalog/schema. Preserve the answer text and source conditions. Do not regenerate an answer or call repair_saved; independent review has not started. Submit the corrected draft on this same request as a new proposal revision.')
        stored=next((p for p in packs if p['logical_id']==request['logical_id']+':proposal'),None)
        if stored:
            previous=await self.client.read_asset(stored['revision']);value=json.loads(previous['asset']['content_json'])
            if value['request_revision']!=request['revision']:raise ValueError('PROCESS_SAVED_PROPOSAL_REQUEST_MISMATCH')
            if value.get('reference_expansion'):result['stored_reading_proposal']=value['reference_expansion']['native_proposal']
            result.update(stored_proposal_revision=previous['revision'],stored_proposal=value['proposal'],
                continuation='Resubmit the exact stored proposal. No new proposal or extra model budget is authorized.')
            error=pre_review_binding_error(value['proposal'])
            if error:
                result.update(stored_proposal_binding_error=error,layout_errors=proposal_layout_errors(value['proposal']),
                    remaining_pre_review_corrections=min(result.get('remaining_pre_review_corrections',2),max(0,2-value.get('pre_review_correction_count',0))),
                    continuation='The saved draft failed deterministic reference/plan/layout binding before any independent review. If request-plan evidence is missing, bind its facets to the original evidence or explicitly retain unresolved meaning; preserve all answer text, statement citations and layout. Correct the draft on this same request; do not call repair_saved (there is no reviewed answer yet). Each table cell displays a whole cited statement. Split cell content into separate statements, use each pointer once, and preserve source meaning. The corrected draft is a new proposal revision and still requires independent review.')
        return result

    async def restore(self,reading_ref,sources):
        return await self.client.restore_task_knowledge(reading_ref,sources,
            principal_id=self.runtime['principal'].employee_id,policy_digest=self.runtime['authorization'].policy_digest)

    async def submit_reading(self,*,request_revision,proposal):
        request=await self.client.read_asset(request_revision)
        data=json.loads(request['asset']['content_json'])
        if data.get('contract_version')!=CONTRACT:raise ValueError('PROCESS_NATIVE_REQUEST_CONTRACT_REQUIRED')
        reading=await self.restore(request['definition_reading_ref'],request['sources'])
        raw=ReadingExplanation.model_validate(proposal).model_dump(mode='json')
        catalog=reading_citation_catalog(request,reading);errors=reading_reference_errors(raw,catalog)
        identity=request['logical_id']+':reading-proposal';packs=(await self.client.catalog_assets(namespace=request['namespace'],kind='pack'))['items']
        previous=next((p for p in packs if p['logical_id']==identity),None);count=0;prior=None
        if previous:
            prior=await self.client.read_asset(previous['revision']);old=json.loads(prior['asset']['content_json'])
            if old['request_revision']!=request_revision:raise ValueError('PROCESS_SAVED_PROPOSAL_REQUEST_MISMATCH')
            count=old['pre_review_correction_count']
            old_errors=reading_reference_errors(old['proposal'],catalog)
            if old['proposal']!=raw:
                if (any('correctable_fields' in e for e in old_errors)
                        and not reading_evidence_correction_preserves_content(old['proposal'],raw,old_errors)):
                    raise ValueError('PROCESS_NATIVE_PROPOSAL_CHANGED')
                layout_error=False
                if not old_errors:
                    expanded_old,_=resolve_reading_explanation(old['proposal'],request=request,reading=reading)
                    layout_error=bool(pre_review_binding_error(expanded_old))
                    if (pre_review_binding_error(expanded_old)=='ANSWER_PLAN_MEANING_OR_UNRESOLVED_REQUIRED'
                            and not plan_correction_preserves_answer(old['proposal'],raw)):
                        raise ValueError('PROCESS_NATIVE_PROPOSAL_CHANGED')
                if count>=2 or not (old_errors or layout_error) or any(p['logical_id']==data['answer_identity'] for p in packs):
                    raise ValueError('PROCESS_NATIVE_PROPOSAL_CHANGED')
                count+=1
            else:prior=None
        if previous is None or prior is not None:
            content={'request_revision':request_revision,'proposal':raw,'reference_errors':errors,
                'pre_review_correction_count':count,'independent_review_started':False}
            if prior is not None:content['corrected_reading_proposal_revision']=prior['revision']
            stored=await self.client.propose_asset({'namespace':request['namespace'],'logical_id':identity,'kind':'pack',
                'title':'에이전트의 읽기 참조 초안','description':'Unreviewed draft and deterministic reference failures; no semantic verdict.',
                'sources':request['sources'],'content_json':json.dumps(content,ensure_ascii=False),
                'dependencies':[{'revision':request_revision,'role':'native_answer_request','reason':'Exact request/reading before reference expansion.','stages':['explain','review']}],
                'definition_reading_ref':request['definition_reading_ref'],**({'previous_revision':prior['revision']} if prior else {})},
                idempotency_key=proposal_correction_key(identity,content))
            revision=stored['revision']
        else:revision=previous['revision']
        if errors:
            return {'status':'reading_reference_correction_required','user_request_fulfilled':False,'new_model_dispatch':False,
                'request_revision':request_revision,'reading_proposal_revision':revision,'stored_reading_proposal':raw,
                'reference_errors':errors,'reading_citation_catalog':catalog,'reading_proposal_schema':reading_proposal_schema(catalog),
                'selected_candidate_asset_index':selected_candidate_index(request,catalog),
                'remaining_pre_review_corrections':max(0,2-count),
                'next_action':'Correct only the reported reference or evidence type fields using the exact catalog. A scope-only interpretation may need an evidence_gap classification or actual positive evidence; choose by its meaning, never invent citations. Preserve text and conditions; resubmit this same request. No independent review has run and no answer exists for repair_saved.',
                'whole_plan_qualified':False}
        expanded,origin=resolve_reading_explanation(raw,request=request,reading=reading)
        origin['reading_proposal_revision']=revision
        return await self.submit(request_revision=request_revision,proposal=expanded,reference_expansion=origin)

    async def submit(self,*,request_revision,proposal,reference_expansion=None):
        request=await self.client.read_asset(request_revision);data=json.loads(request['asset']['content_json'])
        if data['contract_version']!=CONTRACT or data['review_contract']!=RESPONSE_REVIEW_VERSION:
            raise ValueError('PROCESS_NATIVE_REVIEW_CONTRACT_CHANGED')
        if data.get('question_input_revision'):
            user_input,question=await self.read_question_input(data['question_input_revision'])
            expected=input_questions(question)
            # Historical requests remain readable, but an implicit old limit is
            # not current input authority. Prepare from the exact question input
            # again when its stored request constraints no longer match.
            if user_input['namespace']!=data['namespace'] or expected!=data['questions']:
                raise ValueError('PROCESS_QUESTION_INPUT_BINDING_MISMATCH')
        # Resolve current Wiki state again. Never silently answer with an old
        # meaning/review simply because this client retained a prepared handle.
        current=await read_stored_intake(self.client,namespace=data['namespace'],logical_id=data['logical_id'])
        if current is None or any(current.get(k)!=data['intake'].get(k) for k in ('asset_revision','review_revision')):
            raise ValueError('PROCESS_NATIVE_PREPARED_INPUT_CHANGED')
        reading=await self.restore(request['definition_reading_ref'],request['sources'])
        proposal=SourceExplanation.model_validate(proposal).model_dump(mode='json')
        if proposal['context_digest']!=reading['context']['context_digest']:
            raise ValueError('PROCESS_PREPARED_ANSWER_CONTEXT_MISMATCH')
        # The same immutable logical publication/idempotency key admits one
        # exact native proposal. A changed retry cannot buy a new model review.
        proposal_id=request['logical_id']+':proposal'
        content={'request_revision':request_revision,'proposal':proposal}
        if reference_expansion is not None:content['reference_expansion']=reference_expansion
        packs=(await self.client.catalog_assets(namespace=request['namespace'],kind='pack'))['items']
        prior=next((p for p in packs if p['logical_id']==proposal_id),None)
        corrected=False
        if prior:
            old=await self.client.read_asset(prior['revision']);previous=json.loads(old['asset']['content_json'])
            if (previous['request_revision']!=request_revision or previous['proposal']!=proposal
                    or (reference_expansion is not None and previous.get('reference_expansion')!=reference_expansion)):
                if (previous['request_revision']!=request_revision or not pre_review_binding_error(previous['proposal'])
                        or (pre_review_binding_error(previous['proposal'])=='ANSWER_PLAN_MEANING_OR_UNRESOLVED_REQUIRED'
                            and not plan_correction_preserves_answer(previous['proposal'],proposal))
                        or previous.get('pre_review_correction_count',0)>=2
                        or any(p['logical_id']==data['answer_identity'] for p in packs)):
                    raise ValueError('PROCESS_NATIVE_PROPOSAL_CHANGED')
                corrected=True
                content.update(pre_review_correction_count=previous.get('pre_review_correction_count',0)+1,
                    corrected_proposal_revision=old['revision'],prior_binding_error=pre_review_binding_error(previous['proposal']))
        if not prior or corrected:
            await self.client.propose_asset({'namespace':request['namespace'],'logical_id':proposal_id,'kind':'pack',
                'title':'에이전트의 미검토 답변 초안','description':'Untrusted native proposal retained before review; any reading reference expansion is recorded.',
                'sources':request['sources'],'content_json':json.dumps(content,ensure_ascii=False),
                'dependencies':[{'revision':request_revision,'role':'native_answer_request','reason':'Exact request and reading.',
                    'stages':['explain','review']}],'definition_reading_ref':request['definition_reading_ref'],
                **({'previous_revision':old['revision']} if corrected else {})},
                idempotency_key=proposal_correction_key(proposal_id,content) if corrected else proposal_id)
        refs=[v for v in (current['asset_revision'],current.get('review_revision')) if v]
        outcome=await explain_intake(self.client,runtime=self.runtime,intake=current,namespace=data['namespace'],
            questions=data['questions'],output_dir=self.output_dir/uuid.uuid4().hex,
            infer=self.infer_for(RESPONSE_REVIEW_VERSION,refs),proposed_answer=proposal,max_attempts=1,max_response_repairs=0,
            prepared_reading_ref=request['definition_reading_ref'])
        if not outcome.get('asset_revision'):
            return {'status':'unresolved','user_request_fulfilled':False,'outcome':outcome,
                'native_proposal_saved':True,'whole_plan_qualified':False,
                **({'pre_review_correction_required':pre_review_binding_error(proposal),
                    'layout_errors':proposal_layout_errors(proposal),
                    'needed_action':'Prepare this same request to read its saved draft and correction allowance. No answer revision exists for repair_saved.'} if pre_review_binding_error(proposal) else {})}
        return await self.result(outcome['asset_revision'],reused=outcome.get('new_model_run') is False)

    async def repair_saved_answer(self,*,failure_revision):
        """Repair an explicitly selected stored failure, never restart extraction.

        This is a separate user-requested correction of an immutable failure.
        One repair under an unchanged repair contract. A completed invalid patch
        from an older contract may be rebound after its cause is fixed, without
        generating another patch; its exact failure and execution remain recorded.
        """
        from .boi_process_user_result import revalidate_answer
        from .boi_process_response_review import RESPONSE_REPAIR_PRESENTATION_VERSION
        original=await self.client.read_asset(failure_revision)
        cursor=original;seen=set()
        while True:
            if cursor['revision']['ref'] in seen:raise ValueError('PROCESS_REPAIR_HISTORY_CYCLE')
            seen.add(cursor['revision']['ref']);packet=json.loads(cursor['asset']['content_json'])
            report=packet.get('response_review',{});repairs=[a['repair'] for a in report.get('attempts',[]) if a.get('repair')]
            if repairs:
                if (report.get('repair_presentation_contract_version')==RESPONSE_REPAIR_PRESENTATION_VERSION
                        or any(r.get('status')!='invalid_repair' or r.get('provider',{}).get('status')!='completed' for r in repairs)):
                    raise ValueError('PROCESS_SAVED_ANSWER_REPAIR_LIMIT_EXHAUSTED')
                prior_view=await self.client.call('boi_process_result',{'revision':cursor['revision']})
                if not prior_view['answer_review_binding'].get('terminal_repair',{}).get('verified_invalid_patch'):
                    raise ValueError('PROCESS_SAVED_REPAIR_KNOWN_INVALID_PATCH_REQUIRED')
            if not cursor.get('previous_revision'):break
            cursor=await self.client.read_asset(cursor['previous_revision'])
            if cursor['logical_id']!=original['logical_id']:raise ValueError('PROCESS_REPAIR_HISTORY_IDENTITY_CHANGED')
        view=await self.client.call('boi_process_result',{'revision':failure_revision})
        binding=view['answer_review_binding']
        original_packet=json.loads(original['asset']['content_json'])
        quality_only=quality_contract_revalidation_allowed(original_packet,binding)
        review_only=quality_only or source_schema_revalidation_allowed(original_packet,binding)
        if not review_only and (binding.get('status')!='bound' or not binding.get('check',{}).get('assessment_complete') or binding.get('model_assessment_accepts_answers')):
            raise ValueError('PROCESS_SAVED_REPAIR_CONFIRMED_FAILURE_REQUIRED')
        refs=[d['revision'] for d in original['asset']['dependencies'] if d['role'] in
            ('requested_process_meaning','requested_source_note','review')]+[failure_revision]
        execution_events=[];infer=self.infer_for(RESPONSE_REVIEW_VERSION,refs)
        def observed_infer(**kwargs):
            value,run=infer(**kwargs)
            execution_events.append({k:run.get(k) for k in ('wiki_execution_ref','new_model_dispatch','observation_replayed','status')})
            return value,run
        outcome=await revalidate_answer(self.client,runtime=self.runtime,answer_revision=failure_revision,
            repair_from_revision=None if review_only else failure_revision,output_dir=self.output_dir/uuid.uuid4().hex,
            infer=observed_infer,max_repairs=0 if review_only else 1,quality_only=quality_only)
        result=await self.result(outcome['asset_revision'],reused=outcome.get('new_model_run') is False)
        return {**result,'operation':'revalidate_explanation_quality' if quality_only else ('revalidate_completed_assessor_failure' if review_only else 'repair_recorded_answer_failure'),'original_failure_revision':failure_revision,
            'answer_wording_regenerated':False if review_only else None,
            'max_repairs_under_unchanged_contract':1,'original_generation_budget_reopened':False,
            'correction_execution':{'publication_status':outcome['status'],'worker_observations':execution_events,
                'new_model_dispatches':sum(e['new_model_dispatch'] is True for e in execution_events)
                    if all(isinstance(e['new_model_dispatch'],bool) for e in execution_events) else None,
                'scope':'This correction call only. Nested result/binding new_model_runs=0 describes readback, not preceding correction work.'}}


    async def result(self,revision,*,reused):
        view=await self.client.call('boi_process_result',{'revision':revision})
        fulfilled=view['user_request_fulfilled']
        return {'status':'stored_answer' if fulfilled else 'partial_stored_answer',
            'user_request_fulfilled':fulfilled,'answer_revision':revision,'reused_saved_answer':reused,
            'result':agent_result_view(view,base_url=self.runtime.get('api_url')),'scientific_correctness':'not_evaluated','whole_plan_qualified':False}


def process_answer_tool_result(response, *, source_base_url=None):
    """Compact finished MCP answers; leave preparation and repair inputs intact."""
    if 'reading_proposal_schema' in response:
        # Native tools accept reading-scoped references. Offering the expanded
        # compatibility schema alongside it produces mixed, invalid arguments.
        response={k:v for k,v in response.items() if k!='proposal_schema'}
    result = response.get('result')
    if not isinstance(result, dict) or 'citation_display' not in result:
        return response
    from boi_api.app.v2.process_citation_display import process_answer_delivery
    delivery = process_answer_delivery(result, source_base_url=source_base_url)
    return {'result': delivery, **{k:v for k,v in response.items() if k != 'result'}}


def build_process_answer_mcp(host):
    mcp=BoiLocalMCPServer('boi-process-answer')

    def deliver(response):
        return process_answer_tool_result(response, source_base_url=host.runtime.get('api_url'))

    @mcp.tool()
    async def boi_process_question_prepare(question_input_revision:RevisionRef,candidate_revision:RevisionRef)->dict:
        """Prepare or reuse an answer from the exact Wiki-pinned question and selected original sources. Read the question input and candidate source references before selecting a current definition from catalog. needs_candidate_selection means no answer/model work started: use its exact source references to correct the choice; do not drop attachments or treat a related older definition as the requested material. Input @2 pins max_body_characters (null means no cap), response_request (latest depth/format/improvement request) and optional previous_answer_revision. Never inherit a historical length limit. Reuse wording only for the same current requirements; sources/definitions can be reused for new answers. Deliver result.readable_text with its reviewed structure, numbered sources and exact quotation links; use result.details for original excerpts and operational records. Do not rewrite or add unreviewed explanations. Resume an existing exact request/proposal unchanged unless the returned pre-review reference, evidence-type, plan or layout diagnostic explicitly permits a corrected draft revision."""
        return deliver(await host.prepare_from_input(question_input_revision=question_input_revision.model_dump(mode='json'),candidate_revision=candidate_revision.model_dump(mode='json')))

    @mcp.tool()
    async def boi_process_answer_prepare(question:str,namespace:str|None=None,logical_id:str|None=None,
            candidate_revision:RevisionRef|None=None,
            max_body_characters:Annotated[int,Field(ge=1,le=10000,strict=True)]|None=None,
            response_request:str|None=None,previous_answer_revision:RevisionRef|None=None)->dict:
        """Ask a new question using a stored process meaning chosen from Wiki catalog. Supply candidate_revision from the selected definition, or legacy namespace and logical_id, never both. Reads the current revision, review, original fields and answer contract. If an answer exists, returns it without model work. Otherwise read operational_input, reading_citation_catalog and reading_proposal_schema, then use boi_process_answer_submit_reading for one typed untrusted proposal; no guessed definitions or authority."""
        constraint={} if max_body_characters is None else {'max_body_characters':max_body_characters}
        if candidate_revision is not None:
            if namespace is not None or logical_id is not None:
                raise ValueError('PROCESS_QUESTION_SELECTION_AMBIGUOUS')
            return deliver(await host.prepare_selected_definition(candidate_revision=candidate_revision.model_dump(mode='json'),
                question=question,response_request=response_request,
                previous_answer_revision=previous_answer_revision.model_dump(mode='json') if previous_answer_revision else None,**constraint))
        if not namespace or not logical_id:
            raise ValueError('PROCESS_QUESTION_SELECTION_REQUIRED')
        return deliver(await host.prepare(namespace=namespace,logical_id=logical_id,question=question,
            response_request=response_request,previous_answer_revision=previous_answer_revision.model_dump(mode='json') if previous_answer_revision else None,**constraint))

    @mcp.tool()
    async def boi_process_answer_repair_saved(failure_revision:RevisionRef)->dict:
        """Correct the selected stored partial answer within the user-authorized work from its real recorded valid failure. First read the saved result and exact source/definition/review contracts. Reuses that assessment, allows one targeted patch followed by separate source/citation and explanation-quality reviews through existing Wiki work services. A mandatory quality failure permits restructuring only the affected question. Follow the user's authorized repair scope; ordinary authorized answer work does not require a new confirmation. No new extraction or answer regeneration. Same original failure revision replays its saved correction. An admitted completed patch rejected by an older repair contract can be rebound after its cause is fixed, without regenerating the patch. Current-contract failures, unknown work and exhausted semantic corrections cannot renew their budget. A Wiki-bound, completed reference-selection or evidence-domain assessment failure from its older schema can be revalidated under the corrected schema without rewriting the answer; current-schema failures and unknown executions cannot use this recovery. An explicitly selected answer with a confirmed source assessment can refresh an older explanation-quality contract without another source review or answer generation. Ordinary exact request readback still reuses the stored result. Returns the result, prior failure revision and actual receipts; acceptance remains Wiki-bound and PROVISIONAL."""
        return deliver(await host.repair_saved_answer(failure_revision=failure_revision.model_dump(mode='json')))

    @mcp.tool()
    async def boi_process_answer_submit_reading(request_revision:RevisionRef,proposal:ReadingExplanation)->dict:
        """Preferred for a NEW answer after question_prepare/answer_prepare. Read its reading_proposal_schema and reading_citation_catalog. Meaning asset_index must select a definition; the contextual schema lists those indices, and selected_candidate_asset_index identifies the already selected candidate without reindexing other assets. Select question/source indices only from this exact request. Write faithful text and exact quotations or meaning node pointers. Wiki-restored reading records the original draft, invalid references and expansion. No independent review runs for reading_reference_correction_required: correct only its reported reference or evidence-type fields in the stored draft on the SAME request, preserve text/conditions and resubmit. Do not call repair_saved before an answer exists. Only one bindable proposal proceeds to independent review. Reuse stored_reading_proposal unchanged except for the explicitly returned reference/layout correction allowance. Never copy or invent revision hashes."""
        return deliver(await host.submit_reading(request_revision=request_revision.model_dump(mode='json'),proposal=proposal.model_dump(mode='json')))

    @mcp.tool()
    async def boi_process_answer_submit(request_revision:RevisionRef,proposal:SourceExplanation)->dict:
        """Compatibility submission for a fully expanded or previously stored exact proposal. Prefer answer_submit_reading for a new native answer. Copy exact context digest/question IDs and follow source/meaning citation schema. Existing deterministic citation checks and separate source/citation and explanation-quality reviews precede Wiki answer storage. If the returned result has an actionable mandatory failure, use repair_saved within the authorized budget before delivering; preserve the first answer. Unknown or invalid assessments need reconciliation, not blind resubmission. Identical retry restores stored work; a valid proposal cannot be replaced. A saved draft rejected for malformed layout before review may be corrected on the same request within its reported allowance, preserving its prior revision. Read returned result, unresolved parts, conditions, history and actual receipts."""
        return deliver(await host.submit(request_revision=request_revision.model_dump(mode='json'),proposal=proposal.model_dump(mode='json')))

    return mcp
