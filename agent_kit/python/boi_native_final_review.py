"""Record completed independent reviews through existing native Wiki contracts.

No inference, answer rewriting, execution attestation or canonical promotion.
Callers retain the original provider files and use current protected bindings.
"""
import copy
import json
from pathlib import Path

from boi_api.app.governed_runtime.native_observation import NativeObservation
from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.v2.process_citation_display import process_semantic_basis
from .boi_final_source_review import check_final_review,final_review_prompt,final_review_schema
from .boi_structured_provider import strict_output_schema


def load_completed_final_review(directory):
    root=Path(directory)
    material=json.loads((root/'material.json').read_text())
    provider=json.loads((root/'provider.json').read_text())
    if provider.get('status')!='completed':raise ValueError('NATIVE_FINAL_REVIEW_NOT_COMPLETED')
    prompt=(root/'provider/prompt.txt').read_text()
    schema=(root/'provider/schema.json').read_text()
    output=(root/'provider/output.json').read_text()
    for key,value in [('prompt_digest',prompt),('schema_digest',schema),('output_digest',output)]:
        if provider.get(key)!=byte_digest(value.encode()):
            raise ValueError('NATIVE_FINAL_REVIEW_PROVIDER_BYTES_CHANGED')
    if prompt!=final_review_prompt(material):raise ValueError('NATIVE_FINAL_REVIEW_PROMPT_CHANGED')
    if semantic_digest(json.loads(schema))!=semantic_digest(strict_output_schema(final_review_schema(material,segmented=True))):
        raise ValueError('NATIVE_FINAL_REVIEW_SCHEMA_CHANGED')
    events=[json.loads(line) for line in (root/'provider/stdout.txt').read_text().splitlines() if line.strip()]
    sessions={e['thread_id'] for e in events if e.get('type')=='thread.started'}
    if len(sessions)!=1:raise ValueError('NATIVE_FINAL_REVIEW_SESSION_AMBIGUOUS')
    assessment=json.loads(output)
    return {'material':material,'assessment':assessment,'check':check_final_review(assessment,material=material),
        'prompt':prompt,'schema_json':schema,'output_json':output,'session_ref':'codex:'+next(iter(sessions))}


def composition_review_inputs(binding,material):
    if binding.get('contract_version')!='boi/native-answer-composition@1' or 'bound_answer' not in binding:
        raise ValueError('NATIVE_FINAL_REVIEW_PROTECTED_BINDING_REQUIRED')
    if binding['question']!=material['user_request'] or process_semantic_basis({'answer':binding['bound_answer']})!=material['semantic_basis']:
        raise ValueError('NATIVE_FINAL_REVIEW_COMPOSITION_SCOPE_CHANGED')
    request=binding['composition_request']
    reviews=[request['definition_review_revision'],*request.get('additional_definition_review_revisions',[])]
    mappings=binding.get('meaning_review_bindings',[])
    candidates={semantic_digest(x['review_revision']):x['candidate_revision'] for x in mappings}
    if not candidates and len(reviews)==1:
        selected={semantic_digest(n['asset_revision']):n['asset_revision'] for n in material['semantic_basis']['nodes']}
        if len(selected)==1:candidates[semantic_digest(reviews[0])]=next(iter(selected.values()))
    if set(candidates)!={semantic_digest(r) for r in reviews}:
        raise ValueError('NATIVE_FINAL_REVIEW_EXACT_INPUTS_UNRESOLVED')
    return [*reviews,*[candidates[semantic_digest(r)] for r in reviews]]


def reviewed_claim_citations(review):
    """Bind only supported claim segments to the original evidence they used."""
    check=check_final_review(review['assessment'],material=review['material'])
    if not check['assessment_complete'] or not check['model_accepts_final']:
        raise ValueError('NATIVE_FINAL_REVIEW_NOT_ACCEPTED')
    segments={s['unit_id']:s for s in check['claim_segments']}
    evidence={e['evidence_id']:e for e in review['material']['evidence']}
    citations=[]
    for unit in review['assessment']['units']:
        if unit['purpose']!='domain_claim' or unit['relation']!='supported':continue
        segment=segments[unit['unit_id']]
        for ref in unit['evidence_ids']:
            original=evidence.get(ref)
            if original is None or not original.get('text'):continue
            ranges=[]
            if unit.get('citation_support')=='full':
                for group in review['material'].get('citations',[]):
                    if group.get('number') not in unit.get('citation_numbers',[]):continue
                    if group.get('source')!=original['source']:continue
                    for quote in group.get('quotes',[]):
                        b=quote.get('binding',{});start=b.get('quote_start');end=b.get('quote_end')
                        if (b.get('span_ref')==original['field']['span_ref']
                                and quote.get('field_locator')==original['field']['field_locator']
                                and type(start) is int and type(end) is int
                                and 0<=start<end<=len(original['text'])
                                and original['text'][start:end]==quote.get('text')
                                and semantic_digest(quote['text'])==quote.get('quote_digest')):
                            ranges.append((start,end))
            # No guessed excerpt or semantic truncation. Unscoped/older reviews
            # retain their original full-field support and the existing display.
            for start,end in ranges or [(0,len(original['text']))]:
                citation={'body_start':segment['start'],'body_end':segment['end'],
                    'source_digest':original['source']['digest'],'span_ref':original['field']['span_ref'],
                    'quote_start':start,'quote_end':end}
                if citation not in citations:citations.append(citation)
    return citations


async def record_independent_final_review(client,*,directory,composition_ref,namespace,logical_id,title,
        principal_id,policy_digest,output_dir):
    """Preserve one actual opinion, and an accepted delivery only if qualified.

    Stable proposal keys allow reconciliation without another model execution.
    Product reads reauthorize the current dependencies and original source.
    """
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False)
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    review=load_completed_final_review(directory)
    binding=await client.call('boi_native_answer',{'composition_ref':composition_ref,'view':'binding'})
    save('binding.json',binding)
    refs=composition_review_inputs(binding,review['material'])
    sources=[]
    for item in review['material']['evidence']:
        if item['source'] not in sources:sources.append(item['source'])
    dependencies=[{'revision':ref,'role':'review_input','reason':'Exact original final-review input',
        'stages':['review','explain'],'required':True} for ref in refs]
    reading=await client.read_task_knowledge({'sources':sources,'namespace':namespace,'definition_reading':'selected_dependencies',
        'tool_use':'provenance_only',
        'purpose':'Preserve the completed independent final review and its exact original inputs.',
        'roots':dependencies,'stages':['review','explain']},principal_id=principal_id,policy_digest=policy_digest)
    save('review-reading.json',reading)
    observation=NativeObservation(agent_session_ref=review['session_ref'],request={
        'prompt':review['prompt'],'output_schema_json':review['schema_json'],
        'source_manifest_digest':source_manifest_digest(sources),'input_revisions':refs,
        'knowledge_reading_ref':reading['reading_ref'],'review_contract_version':'boi/final-source-review@1'},
        value_json=review['output_json'])
    draft={'logical_id':logical_id+':review','namespace':namespace,'kind':'pack','title':title+' · 독립 원문 검토',
        'description':'Preserved actual final-review output; execution is unattested and no scientific or canonical approval is granted.',
        'content_json':observation.model_dump_json(),'sources':sources,'definition_reading_ref':reading['reading_ref'],'dependencies':dependencies}
    save('review-draft.json',draft)
    saved=await client.propose_asset(draft,idempotency_key=logical_id+':review')
    save('review-saved.json',saved)
    if not review['check']['assessment_complete'] or not review['check']['model_accepts_final']:
        return {'status':'review_recorded_needs_revision','review_revision':saved['revision'],'delivery_created':False}
    citations=reviewed_claim_citations(review)
    request=binding['composition_request'];reviews=[request['definition_review_revision'],*request.get('additional_definition_review_revisions',[])]
    dependencies=[{'revision':ref,'role':'reviewed_answer_input','reason':'Preserved final review and exact definition authority',
        'stages':['review','explain'],'required':True} for ref in [saved['revision'],*reviews]]
    reading=await client.read_task_knowledge({'sources':sources,'namespace':namespace,'definition_reading':'selected_dependencies',
        'tool_use':'provenance_only','purpose':'Read the independently reviewed final answer and original evidence.',
        'roots':dependencies,'stages':['review','explain']},principal_id=principal_id,policy_digest=policy_digest)
    save('delivery-reading.json',reading)
    content={'contract_version':'boi/native-source-answer-delivery@2','review_revision':saved['revision'],
        'definition_review_revision':reviews[0],'additional_definition_review_revisions':reviews[1:],
        'review_material':copy.deepcopy(review['material']),'citations':citations,
        'composition_ref':binding['composition_ref'],
        'execution_refs':[request['execution_ref']] if request.get('execution_ref') else []}
    draft={'logical_id':logical_id+':delivery','namespace':namespace,'kind':'pack','title':title,
        'description':'Actual final message with independent source review; no regenerated answer or live equipment claim.',
        'content_json':json.dumps(content,ensure_ascii=False),'sources':sources,'definition_reading_ref':reading['reading_ref'],'dependencies':dependencies}
    save('delivery-draft.json',draft)
    delivery=await client.propose_asset(draft,idempotency_key=logical_id+':delivery')
    save('delivery-saved.json',delivery)
    return {'status':'recorded_provisional_reviewed_delivery','review_revision':saved['revision'],
        'delivery_revision':delivery['revision'],'delivery_created':True,'execution_attested':False}
