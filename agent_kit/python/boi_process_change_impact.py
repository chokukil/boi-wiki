"""Find process answer revalidation candidates from immutable Wiki reads.

No field name, process name or question text determines semantic relevance.
Uncertain additions are reviewed; discovery never rewrites an answer or receipt.
"""
import asyncio
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref,semantic_digest


def source_answer_impact(packet, *, old_source, new_source, source_dependency=None):
    from .boi_process_answer_v2 import answer_evidence_groups
    old={f['field_locator']:f for f in old_source['fields']}
    new={f['field_locator']:f for f in new_source['fields']}
    changed={p for p in set(old)|set(new) if p not in old or p not in new or
        any(old[p].get(k)!=new[p].get(k) for k in ('content_digest','field_state','value_kind','text'))}
    revision=old_source['source']['digest'];direct=[];uncertain=[];unaffected=[]
    for answer in packet['answer']['answers']:
        citations=[c for _,statements in answer_evidence_groups(answer) for s in statements for c in s['citations']]
        cited=any(b['source_revision_digest']==revision for c in citations for b in c['source_bindings'])
        scope=any(c['kind']=='source_scope' and c['source_revision_digest']==revision for c in citations)
        hit=any(b['source_revision_digest']==revision and b['field_locator'] in changed
            for c in citations for b in c['source_bindings'])
        if not changed:unaffected.append(answer['question_id'])
        elif hit or scope:direct.append(answer['question_id'])
        elif cited or source_dependency is not False:uncertain.append(answer['question_id'])
        else:unaffected.append(answer['question_id'])
    return {'contract_version':'boi/process-source-answer-impact@2','operation':'source_revision_change',
        'changed_fields':sorted(changed),'added_fields':sorted(set(new)-set(old)),
        'removed_fields':sorted(set(old)-set(new)),
        'affected_question_ids':direct,'review_candidate_question_ids':uncertain,
        'candidate_question_ids':direct+uncertain,'unaffected_question_ids':unaffected,
        'old_source_revision':revision,'new_source_revision':new_source['source']['digest'],
        'method':'exact citations plus complete stored source/dependency scope; uncertainty requires relevance review',
        'semantic_equivalence_proven':False,'regeneration_started':False}


async def discover_answer_impacts(client, *, namespace, old_source=None, new_source=None,
        changed_definition_revisions=()):
    """Read catalog heads and exact dependency closure through the common MCP.

    This is read-only discovery. A fresh caller needs no latest_requests memory.
    Missing/denied dependencies cannot justify excluding a result.
    """
    if (old_source is None)!=(new_source is None):raise ValueError('PROCESS_IMPACT_BOTH_SOURCE_REVISIONS_REQUIRED')
    changed={semantic_digest(r) for r in changed_definition_revisions}
    cache={};results=[];excluded=[]
    async def read(revision):
        key=semantic_digest(revision)
        if key not in cache:cache[key]=await client.read_asset(revision)
        return cache[key]
    catalog=await client.catalog_assets(namespace=namespace,kind='pack')
    for head in catalog['items']:
        asset=await read(head['revision']);packet=json.loads(asset['asset']['content_json'])
        if packet.get('contract_version') not in ('boi/process-user-result@1','boi/process-user-result@2','boi/process-user-result@3'):
            continue
        queue=[asset['revision']];visited=set();sources=set();closure_errors=[]
        while queue:
            revision=queue.pop();key=semantic_digest(revision)
            if key in visited:continue
            visited.add(key)
            try:node=await read(revision)
            except Exception as exc:
                closure_errors.append({'revision':revision,'error_type':type(exc).__name__});continue
            sources.update(s['digest'] for s in node['sources'])
            queue.extend(d['revision'] for d in node['asset']['dependencies'])
        definition_hit=bool(visited & changed)
        impact=None
        if old_source is not None:
            depends=old_source['source']['digest'] in sources
            impact=source_answer_impact(packet,old_source=old_source,new_source=new_source,
                source_dependency=None if closure_errors else depends)
        ids=[a['question_id'] for a in packet['answer']['answers']]
        candidates=set(impact['candidate_question_ids'] if impact else ())
        if definition_hit or closure_errors:candidates.update(ids)
        item={'answer_revision':asset['revision'],'logical_id':asset['logical_id'],
            'questions':packet['questions'],'candidate_question_ids':[i for i in ids if i in candidates],
            'source_impact':impact,'changed_definition_dependency':definition_hit,
            'closure_complete':not closure_errors,'closure_errors':closure_errors,
            'reading_receipt':asset['definition_reading_ref'],
            'operation':'source_or_definition_change','review_contract_revalidation':False}
        (results if candidates else excluded).append(item)
    return {'contract_version':'boi/process-stored-answer-impact@1','candidates':results,'excluded':excluded,
        'catalog_snapshot_digest':catalog['snapshot_digest'],'discovery':'actual_mcp_catalog_and_exact_revision_dependencies',
        'regeneration_started':False,'semantic_relevance':'requires_review_for_uncertain_candidates',
        'whole_plan_qualified':False}


CHANGE_REVIEW_VERSION='boi/process-answer-change-review@2'


class ChangeFinding(FrozenContract):
    question_id:Ref
    impact:Literal['affected','unrelated','uncertain']
    reason:Ref
    evidence_ids:tuple[Ref,...]=Field(min_length=1)
    affected_statement_pointers:tuple[Ref,...]=()
    needed_evidence:tuple[Ref,...]=()


class ChangeAssessment(FrozenContract):
    findings:tuple[ChangeFinding,...]
    limitations:tuple[Ref,...]=Field(min_length=1)


def check_change_assessment(value,*,question_ids,statement_pointers,evidence_catalog,required_evidence_sides):
    assessment=ChangeAssessment.model_validate(value).model_dump(mode='json')
    found=[f['question_id'] for f in assessment['findings']]
    if len(found)!=len(set(found)) or set(found)!=set(question_ids):
        raise ValueError('PROCESS_CHANGE_REVIEW_QUESTION_SET_MISMATCH')
    catalog={e['evidence_id']:e for e in evidence_catalog}
    for finding in assessment['findings']:
        if not set(finding['evidence_ids'])<=catalog.keys():raise ValueError('PROCESS_CHANGE_REVIEW_UNKNOWN_EVIDENCE')
        if not set(finding['affected_statement_pointers'])<=set(statement_pointers[finding['question_id']]):
            raise ValueError('PROCESS_CHANGE_REVIEW_UNKNOWN_STATEMENT')
        if finding['impact']=='uncertain' and not finding['needed_evidence']:
            raise ValueError('PROCESS_CHANGE_REVIEW_UNCERTAINTY_REASON_REQUIRED')
        if finding['impact']=='unrelated' and finding['affected_statement_pointers']:
            raise ValueError('PROCESS_CHANGE_REVIEW_UNRELATED_HAS_AFFECTED_STATEMENTS')
        if finding['impact']!='uncertain' and any(not set(side)&set(finding['evidence_ids']) for side in required_evidence_sides):
            raise ValueError('PROCESS_CHANGE_REVIEW_BOTH_CHANGE_SIDES_REQUIRED')
    return {'assessment_complete':True,'model_judgment':assessment,
        'affected_question_ids':[f['question_id'] for f in assessment['findings'] if f['impact']=='affected'],
        'unrelated_question_ids':[f['question_id'] for f in assessment['findings'] if f['impact']=='unrelated'],
        'uncertain_question_ids':[f['question_id'] for f in assessment['findings'] if f['impact']=='uncertain'],
        'semantic_relevance_proven':False,'scientific_correctness':'not_evaluated'}


async def review_stored_answer_change(client,*,runtime,candidate,output_dir,infer,provider='codex',
        source_change=None,definition_changes=()):
    """One source-grounded relevance review; no regeneration or answer keys.

    Each change explicitly identifies old/new immutable inputs. Persist both
    the provisional judgment and a new Wiki reading receipt. Failed assessment
    integrity keeps all selected questions uncertain rather than excluding them.
    """
    from agent_kit.python.boi_process_intake import source_readings
    from agent_kit.python.boi_process_response_review import response_context_view
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    if not source_change and not definition_changes:raise ValueError('PROCESS_EXACT_CHANGE_REQUIRED')
    original=await client.read_asset(candidate['answer_revision'])
    packet=json.loads(original['asset']['content_json'])
    ids=candidate['candidate_question_ids']
    available={q['id'] for q in packet['questions']}
    if not ids or len(ids)!=len(set(ids)) or not set(ids)<=available:
        raise ValueError('PROCESS_CHANGE_CANDIDATE_QUESTIONS_INVALID')
    operation={'review_version':CHANGE_REVIEW_VERSION,'answer_revision':original['revision'],
        'question_ids':ids,'source_change':source_change,'definition_changes':list(definition_changes),
        'purpose':'source_or_definition_change_relevance'}
    identity='process-answer-change:'+semantic_digest(operation)
    prior=next((a for a in (await client.catalog_assets(namespace=original['namespace'],kind='pack'))['items']
        if a['logical_id']==identity),None)
    if prior:
        saved=await client.read_asset(prior['revision']);content=json.loads(saved['asset']['content_json'])
        save('result.json',content);save('review-asset.json',saved)
        return {'status':'replayed','asset_revision':saved['revision'],'reading_ref':saved['definition_reading_ref'],
            'check':content['check'],'new_model_run':False,'whole_plan_qualified':False}
    roots=[{'revision':original['revision'],'role':'prior_answer','reason':'Review this exact stored answer against the explicit changes.',
        'stages':['review','explain']}]
    sources={s['digest']:s for s in original['sources']}
    if source_change:
        for side in ('old','new'):sources[source_change[side]['digest']]=source_change[side]
    for change in definition_changes:
        for side in ('old','new'):
            asset=await client.read_asset(change[side]);sources.update({s['digest']:s for s in asset['sources']})
            if asset['asset']['kind']!='definition':raise ValueError('PROCESS_CHANGE_DEFINITION_KIND_REQUIRED')
            # The old revision is already an immutable dependency of the
            # stored answer. An explicit root means CURRENT in the existing
            # Wiki contract and would incorrectly demand that old == new head.
            # Keep only the new definition as a current root; old ACL/content
            # checks still run through the prior answer's exact closure.
            if side=='new':roots.append({'revision':asset['revision'],'role':'new_definition',
                'reason':'Current revision of the changed definition.','stages':['review','explain']})
    reading=await client.read_task_knowledge({'namespace':original['namespace'],'sources':list(sources.values()),'tool_use':'provenance_only',
        'purpose':'Review stored answer relevance to exact source or definition changes','roots':roots},
        principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    originals=await source_readings(client,list(sources.values()))
    for change in definition_changes:
        if not any(a['revision']==change['old'] for a in reading['context']['assets']):
            raise ValueError('PROCESS_CHANGE_OLD_DEFINITION_NOT_IN_ANSWER_DEPENDENCIES')
    catalog=[{'evidence_id':'field:'+semantic_digest([s['source']['digest'],f['field_locator']]),
        'kind':'source_field','source_revision_digest':s['source']['digest'],**f}
        for s in originals for f in s['fields']]
    for change in definition_changes:
        for side in ('old','new'):
            revision=change[side];entry=next(a for a in reading['context']['assets'] if a['revision']==revision)
            item={'evidence_id':'definition:'+semantic_digest(revision),'kind':'definition_revision',
                'asset_revision':revision,'side':side,'content_digest':entry['content_digest'],
                'meaning_location':'read_definitions_and_contracts.assets entry with this exact revision'}
            if not any(e['evidence_id']==item['evidence_id'] for e in catalog):catalog.append(item)
    required=[]
    if source_change:
        required.extend([[e['evidence_id'] for e in catalog if e.get('source_revision_digest')==source_change[side]['digest']]
            for side in ('old','new')])
    required.extend([['definition:'+semantic_digest(change[side])] for change in definition_changes for side in ('old','new')])
    pointers={a['question_id']:[f'/answers/{ai}/{loc}/{si}' for loc in ('sentences','limitations')
        for si,_ in enumerate(a[loc])] for ai,a in enumerate(packet['answer']['answers'])}
    material={'operation':operation,'prior_answer':packet['answer'],'questions':[q for q in packet['questions'] if q['id'] in ids],
        'evidence_catalog':catalog,'read_definitions_and_contracts':response_context_view(reading['context']),
        'candidate_discovery':candidate,'statement_pointers':{i:pointers[i] for i in ids},
        'required_evidence_sides':required,'requirements_origin':'original user questions and explicit old/new changes only'}
    save('operation.json',operation);save('reading.json',reading);save('sources.json',originals);save('material.json',material)
    schema=ChangeAssessment.model_json_schema()
    schema['properties']['findings'].update(minItems=len(ids),maxItems=len(ids))
    schema['$defs']['ChangeFinding']['properties']['question_id']['enum']=ids
    prompt=('Compare each selected stored answer/question with the exact old and new source/definition revisions. '
        'Decide whether the change can affect that answer meaning, conditions, negation, exceptions or scope. '
        'A newly added exception may change an answer even when no old citation mentions its field. '
        'Deleted conditions can widen applicability. Exact citation overlap is a discovery hint, not semantic proof. '
        'Conversely, a presentation-only or other unrelated change does not require a new answer. '
        'Read the full old/new content and definitions; do not classify from field names, process names or question patterns. '
        'Use affected for a necessary update/revalidation, unrelated only when the read evidence establishes irrelevance, '
        'and uncertain with the missing evidence when it cannot be resolved. Cite supplied evidence IDs from BOTH sides '
        'of each explicit change for a resolved finding. Map affected statements using only the supplied pointers. '
        'Preserve historical statements as historical evidence; do not rewrite them or treat old assessments as current. '
        'No answer key, desired outcome, external knowledge or scientific truth claim. Explain in Korean.\n')
    # The work identity must bind the authorized read and both exact definition
    # revisions. Historical definitions remain dependencies, not current roots.
    input_revisions=[]
    for revision in [r['revision'] for r in roots]+[c[side] for c in definition_changes for side in ('old','new')]:
        if revision not in input_revisions:input_revisions.append(revision)
    try:
        value,run=await asyncio.to_thread(infer,provider=provider,prompt=prompt+json.dumps(material,ensure_ascii=False),
            schema=schema,output_dir=root/'provider',knowledge_reading_ref=reading['reading_ref'],
            input_revisions=input_revisions)
    except ValueError as exc:
        from agent_kit.python.boi_process_response_review import recorded_provider_failure
        run=recorded_provider_failure(root/'provider',exc);value=None
    try:check=check_change_assessment(value,question_ids=ids,statement_pointers=pointers,
        evidence_catalog=catalog,required_evidence_sides=required)
    except ValueError as exc:
        check={'assessment_complete':False,'diagnostic':str(exc),'affected_question_ids':[],
            'unrelated_question_ids':[],'uncertain_question_ids':ids,'semantic_relevance_proven':False,
            'scientific_correctness':'not_evaluated'}
    result={'contract_version':CHANGE_REVIEW_VERSION,'operation':operation,'assessment':value,'check':check,'provider':run,
        'material_digest':semantic_digest(material),'reading_ref':reading['reading_ref'],
        'answer_regenerated':False,'whole_plan_qualified':False}
    # A storage failure must not lose a completed external observation or
    # silently cause another model dispatch on a later recovery.
    save('pending-publication.json',result)
    saved=await client.propose_asset({'namespace':original['namespace'],'logical_id':identity,'kind':'pack',
        'title':'원문·정의 변경의 답변 영향 검토','description':'Exact stored answer and changed evidence; provisional model relevance assessment.',
        'sources':list(sources.values()),'content_json':json.dumps(result,ensure_ascii=False),
        'definition_reading_ref':reading['reading_ref'],'dependencies':roots},idempotency_key=identity)
    save('result.json',result);save('review-asset.json',saved)
    return {'status':'recorded','asset_revision':saved['revision'],'reading_ref':reading['reading_ref'],
        'check':check,'new_model_run':run.get('new_model_dispatch',True),'whole_plan_qualified':False}


async def resume_change_review_publication(client, *, runtime, previous_dir, output_dir):
    """Publish a known completed observation after re-reading identical input.

    This is storage recovery, not a new semantic evaluation. Unknown/timed-out
    external outcomes cannot enter this path. Old receipts remain immutable;
    a fresh receipt admits publication and both readings are recorded.
    """
    from agent_kit.python.boi_process_intake import source_readings
    from boi_api.app.governed_runtime.source_envelope import byte_digest
    previous=Path(previous_dir);root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def read(name):return json.loads((previous/name).read_text())
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    operation=read('operation.json');material=read('material.json');old_reading=read('reading.json')
    run=read('provider/run.json');value=read('provider/output.json');schema=read('provider/schema.json')
    if (run.get('status')!='completed' or run.get('returncode')!=0 or run.get('unexpected_tool_use') is not False):
        raise ValueError('PROCESS_CHANGE_KNOWN_COMPLETED_PROVIDER_REQUIRED')
    for name,key in (('output.json','output_digest'),('prompt.txt','prompt_digest'),('schema.json','schema_digest')):
        if byte_digest((previous/'provider'/name).read_bytes())!=run.get(key):
            raise ValueError('PROCESS_CHANGE_PROVIDER_ARTIFACT_DRIFT')
    if json.loads((previous/'provider/prompt.txt').read_text().split('\n',1)[1])!=material or material['operation']!=operation:
        raise ValueError('PROCESS_CHANGE_ORIGINAL_MODEL_INPUT_DRIFT')
    from jsonschema import validate
    validate(value,schema)
    original=await client.read_asset(operation['answer_revision'])
    identity='process-answer-change:'+semantic_digest(operation)
    prior=next((a for a in (await client.catalog_assets(namespace=original['namespace'],kind='pack'))['items']
        if a['logical_id']==identity),None)
    if prior:
        saved=await client.read_asset(prior['revision']);content=json.loads(saved['asset']['content_json'])
        save('review-asset.json',saved)
        return {'status':'replayed','asset_revision':saved['revision'],'reading_ref':saved['definition_reading_ref'],
            'check':content['check'],'new_model_run':False,'whole_plan_qualified':False}
    before_sources=read('sources.json');sources=[s['source'] for s in before_sources]
    # Current namespace definitions are inserted by Wiki. Preserve every
    # explicit root and its exact historical dependency closure.
    roots=[s['requirement'] for s in old_reading['context']['selections'] if s['parent'] is None
        and s['requirement']['role']!='existing_definition']
    reading=await client.read_task_knowledge({'namespace':original['namespace'],'sources':sources,
        'purpose':old_reading['context']['purpose'],'roots':roots,'tool_use':'provenance_only'},
        principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    current_sources=await source_readings(client,sources)
    if reading['context']!=old_reading['context'] or current_sources!=before_sources:
        raise ValueError('PROCESS_CHANGE_PUBLICATION_REQUIRES_IDENTICAL_MODEL_EVIDENCE')
    check=check_change_assessment(value,question_ids=operation['question_ids'],
        statement_pointers=material['statement_pointers'],evidence_catalog=material['evidence_catalog'],
        required_evidence_sides=material['required_evidence_sides'])
    recovery={'operation':'publish_known_completed_observation','new_model_runs':0,
        'original_model_reading_ref':old_reading['reading_ref'],'publication_reading_ref':reading['reading_ref'],
        'identical_context_and_source_projections':True,'provider_run_digest':semantic_digest(run),
        'material_digest':semantic_digest(material),'previous_dir':str(previous)}
    result={'contract_version':operation['review_version'],'operation':operation,'assessment':value,'check':check,'provider':run,
        'material_digest':semantic_digest(material),'reading_ref':reading['reading_ref'],'publication_recovery':recovery,
        'answer_regenerated':False,'whole_plan_qualified':False}
    save('before-publication.json',recovery);save('reading.json',reading);save('pending-publication.json',result)
    saved=await client.propose_asset({'namespace':original['namespace'],'logical_id':identity,'kind':'pack',
        'title':'원문·정의 변경의 답변 영향 검토','description':'Exact stored answer and changed evidence; provisional model relevance assessment.',
        'sources':sources,'content_json':json.dumps(result,ensure_ascii=False),
        'definition_reading_ref':reading['reading_ref'],'dependencies':roots},idempotency_key=identity)
    save('result.json',result);save('review-asset.json',await client.read_asset(saved['revision']))
    return {'status':'recorded','asset_revision':saved['revision'],'reading_ref':reading['reading_ref'],
        'check':check,'new_model_run':False,'whole_plan_qualified':False}
