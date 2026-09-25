"""Partition source-review observations without inventing candidate judgments.

Only shape, identities, quotation binding and review self-consistency are checked.
A malformed reviewer judgment is pending review, not a false source claim.
"""
import copy
from collections import Counter
from .boi_process_claim_review import (ProcessSourceReview,SourceNodeJudgment,SourceFieldCoverage,
    assessment_targets,check_source_review,dependent_nodes,coverage_pointers)


def native_review_input_dependencies(request, dependencies):
    """Declare every exact input already admitted by review preparation."""
    result=copy.deepcopy(dependencies)
    for revision in request['input_revisions']:
        if not any(d['revision']==revision for d in result):
            result.append({'revision':copy.deepcopy(revision),'role':'review_input',
                'reason':'Exact retained source-review input, including prior definitions used for closure comparison.',
                'stages':['review','plan','explain'],'required':True})
    return result


async def repair_native_review_dependencies(client, *, review_revision, output_dir):
    """Repair only missing declared inputs; preserve the completed observation.

    A changed body is a new pack revision. Unknown publications require explicit
    reconciliation; this function never reruns a model or rewrites its opinion.
    """
    import json
    from pathlib import Path
    from boi_api.app.governed_runtime.native_observation import NativeObservation
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    def save(name,value):
        path=root/name
        if path.exists():
            if json.loads(path.read_text())!=value:raise ValueError('NATIVE_REVIEW_REPAIR_INPUT_CHANGED')
        else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    stored=await client.read_asset(review_revision);save('original.json',stored)
    observation=NativeObservation.model_validate_json(stored['asset']['content_json'])
    request=observation.request.model_dump(mode='json')
    dependencies=native_review_input_dependencies(request,stored['asset'].get('dependencies',[]))
    if dependencies==stored['asset'].get('dependencies',[]):
        return {'revision':review_revision,'new_revision_created':False,'new_model_calls':0}
    if (root/'saved.json').exists():
        saved=json.loads((root/'saved.json').read_text())
    else:
        if (root/'proposal.json').exists():raise ValueError('NATIVE_REVIEW_PUBLICATION_RECONCILIATION_REQUIRED')
        proposal={**{k:stored[k] for k in ('logical_id','namespace','title','description')},
            'kind':'pack','content_json':stored['asset']['content_json'],'sources':stored['sources'],
            'definition_reading_ref':request['knowledge_reading_ref'],'dependencies':dependencies,
            'previous_revision':review_revision,
            'evidence_spans':[{'ref':e['ref'],'revision_digest':e['revision_digest']}
                for e in stored['asset'].get('evidence',[])],
            'conflicts_with':stored['asset'].get('conflicts_with',[]),
            'supersedes':stored['asset'].get('supersedes',[])}
        save('proposal.json',proposal)
        saved=await client.propose_asset(proposal,idempotency_key='native-review-input-repair:'+semantic_digest(proposal))
        save('saved.json',saved)
    current=await client.read_asset(saved['revision']);save('readback.json',current)
    if current['asset']['content_json']!=stored['asset']['content_json'] or current['asset']['dependencies']!=dependencies:
        raise ValueError('NATIVE_REVIEW_REPAIR_READBACK_CHANGED')
    return {'revision':saved['revision'],'previous_revision':review_revision,'new_model_calls':0,
        'observation_unchanged':True,'semantic_review_repeated':False}


async def review_native_candidate(client, *, candidate_revision, principal_id, policy_digest,
        output_dir, model_settings=None, target_pointers=None, timeout_seconds=180,
        prior_review_revision=None):
    """Reuse the product's source-review preparation, observation and binding.

    The caller selects existing knowledge, not an answer or expected verdict.
    This performs one independent native source comparison and keeps per-node
    limits. It cannot approve a final answer, science or equipment execution.
    Completed observations resume; unknown model/publication outcomes stop.
    """
    import asyncio,json
    from pathlib import Path
    from .boi_structured_provider import run_structured,reconcile_completed_codex_output,strict_output_schema,audit_codex_events
    from boi_api.app.governed_runtime.native_observation import NativeObservation
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    def read(name):return json.loads((root/name).read_text())
    def preserve(name,value):
        path=root/name
        if path.exists():
            if read(name)!=value:raise ValueError('NATIVE_REVIEW_RETAINED_INPUT_CHANGED')
        else:
            with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    preserve('selection.json',{'candidate_revision':candidate_revision,'target_pointers':target_pointers,
        'principal_id':principal_id,'policy_digest':policy_digest,'model_settings':model_settings,
        'timeout_seconds':timeout_seconds,
        **({'prior_review_revision':prior_review_revision} if prior_review_revision is not None else {})})
    candidate=await client.read_asset(candidate_revision)
    if candidate['asset']['kind']!='definition':raise ValueError('NATIVE_REVIEW_DEFINITION_REQUIRED')
    if not (root/'candidate.json').exists():preserve('candidate.json',candidate)
    previous=read('candidate.json')
    if candidate['revision']!=previous['revision'] or candidate['asset']!=previous['asset'] or candidate['sources']!=previous['sources']:
        raise ValueError('NATIVE_REVIEW_CANDIDATE_CHANGED')
    if (root/'saved.json').exists():
        saved=read('saved.json');current=await client.read_asset(saved['revision'])
        if current['asset']['content_json']!=read('proposal.json')['content_json']:
            raise ValueError('NATIVE_REVIEW_STORED_OBSERVATION_CHANGED')
        observation=NativeObservation.model_validate_json(current['asset']['content_json'])
        if native_review_input_dependencies(observation.request.model_dump(mode='json'),current['asset'].get('dependencies',[]))!=current['asset'].get('dependencies',[]):
            repaired=await repair_native_review_dependencies(client,review_revision=saved['revision'],output_dir=root/'dependency-repair')
            saved={**saved,'revision':repaired['revision']}
        binding=await client.call('boi_process_review_binding',{
            'candidate_revision':candidate_revision,'review_revision':saved['revision']})
        return {'candidate_revision':candidate_revision,'review_revision':saved['revision'],
            'binding':binding,'new_model_calls':0,'reused_observation':True}
    if (root/'proposal.json').exists():
        raise ValueError('NATIVE_REVIEW_PUBLICATION_RECONCILIATION_REQUIRED')
    if (root/'reading.json').exists():
        reading=read('reading.json')
        await client.restore_task_knowledge(reading['reading_ref'],candidate['sources'],
            principal_id=principal_id,policy_digest=policy_digest)
    else:
        roots=[{'revision':candidate_revision,'role':'reviewed_definition',
            'reason':'Compare selected stored meanings with their original record and correction dependencies.',
            'stages':['review','plan','explain'],'required':True}]
        if prior_review_revision is not None:
            roots.append({'revision':prior_review_revision,'role':'prior_source_review',
                'reason':'Retain prior judgments only where the current source and meaning dependency closure is unchanged.',
                'stages':['review','plan','explain'],'required':True})
        reading=await client.read_task_knowledge({'sources':candidate['sources'],'namespace':candidate['namespace'],
            'purpose':'intake','definition_reading':'selected_dependencies','roots':roots},
            principal_id=principal_id,policy_digest=policy_digest)
        preserve('reading.json',reading)
    prepared=await client.prepare_process_review(candidate_revision,knowledge_reading_ref=reading['reading_ref'],
        target_pointers=target_pointers,
        **({'prior_review_revision':prior_review_revision} if prior_review_revision is not None else {}))
    preserve('prepared.json',prepared)
    if not prepared['scope']['target_pointers'] and not prepared['scope']['field_locators']:
        # No reviewer is needed to repeat unchanged judgments. A preparation is
        # not a new observation or an execution/answer authority for this revision.
        result={'candidate_revision':candidate_revision,'prior_review_revision':prior_review_revision,
            'status':'unchanged_review_scope_prepared','new_model_calls':0,
            'carry_forward_nodes':prepared['selection']['carry_forward_nodes'],
            'new_review_revision':None,'execution_authority_granted':False}
        preserve('outcome.json',result)
        return result
    request=prepared['request'];schema=json.loads(request['output_schema_json']);stage=root/'provider'
    reused=stage.exists()
    if reused:
        value,run=reconcile_completed_codex_output(stage)
        if (stage/'prompt.txt').read_text()!=request['prompt'] or json.loads((stage/'schema.json').read_text())!=strict_output_schema(schema):
            raise ValueError('NATIVE_REVIEW_COMPLETED_INPUT_CHANGED')
    else:
        value,run=await asyncio.to_thread(run_structured,provider='codex',prompt=request['prompt'],schema=schema,
            output_dir=stage,timeout_seconds=timeout_seconds,knowledge_reading_ref=request['knowledge_reading_ref'],
            input_revisions=request['input_revisions'],model_settings=model_settings)
    events=[json.loads(line) for line in (stage/'stdout.txt').read_text().splitlines() if line.strip()]
    audit=audit_codex_events(events)
    sessions=[event['thread_id'] for event in events if event.get('type')=='thread.started']
    if audit['status']!='completed' or audit['unexpected_tool_use'] or len(sessions)!=1:
        raise ValueError('NATIVE_REVIEW_PROVIDER_NOT_COMPLETED')
    raw=(stage/'output.json').read_text()
    if json.loads(raw)!=value:raise ValueError('NATIVE_REVIEW_PROVIDER_OUTPUT_CHANGED')
    observation=NativeObservation(agent_session_ref='codex:'+sessions[0],request=request,value_json=raw)
    preserve('observation.json',observation.model_dump(mode='json'))
    proposal={'logical_id':candidate['logical_id']+':source-node-review:'+semantic_digest(prepared['scope']),
        'namespace':candidate['namespace'],'kind':'pack','title':candidate['title']+' 원문 대조',
        'description':'선택한 기존 의미와 원문 근거의 대조. 답변·과학적 진실·장비 실행의 승인이 아니다.',
        'content_json':observation.model_dump_json(),'sources':candidate['sources'],
        'definition_reading_ref':reading['reading_ref'],'dependencies':[{'revision':candidate_revision,
            'role':'reviewed_definition','reason':'Exact meanings and original evidence under review.',
            'stages':['review','plan','explain'],'required':True}],'previous_revision':None}
    if prior_review_revision is not None:
        proposal['dependencies'].append({'revision':prior_review_revision,'role':'prior_source_review',
            'reason':'Exact prior judgments and limitations carried through unchanged dependency closures.',
            'stages':['review','plan','explain'],'required':True})
    proposal['dependencies']=native_review_input_dependencies(request,proposal['dependencies'])
    preserve('proposal.json',proposal)
    saved=await client.propose_asset(proposal,idempotency_key='native-source-node-review:'+semantic_digest(observation))
    preserve('saved.json',saved)
    current=await client.read_asset(saved['revision']);preserve('readback.json',current)
    if current['asset']['content_json']!=proposal['content_json']:raise ValueError('NATIVE_REVIEW_STORED_OBSERVATION_CHANGED')
    binding=await client.call('boi_process_review_binding',{'candidate_revision':candidate_revision,'review_revision':saved['revision']})
    preserve('binding.json',binding)
    result={'candidate_revision':candidate_revision,'review_revision':saved['revision'],'binding':binding,
        'new_model_calls':0 if reused else 1,'reused_observation':reused,'model_seconds':run['elapsed_seconds']}
    preserve('outcome.json',result)
    return result


def observe_source_review(raw,*,draft,evidence,selection,previous_review=None,
        reference_contract_version='boi/source-coverage-references@1',review_scope='complete_candidate',
        native_targets=None,native_closures=None):
    if review_scope not in ('complete_candidate','selected_nodes'):
        raise ValueError('SOURCE_REVIEW_SCOPE_INVALID')
    original_raw=copy.deepcopy(raw)
    # Native definitions keep their own schema. The caller supplies the exact
    # current resolver catalog, never a model's claimed dependency graph.
    native=native_targets is not None
    if native and (review_scope!='selected_nodes' or native_closures is None):
        raise ValueError('SOURCE_REVIEW_NATIVE_SELECTED_CLOSURES_REQUIRED')
    all_nodes={t['target_pointer'] for t in (native_targets if native else assessment_targets(draft,include_all_terms=True))}
    if native and (set(native_closures)!=all_nodes or any(not set(v)<=all_nodes for v in native_closures.values())):
        raise ValueError('SOURCE_REVIEW_NATIVE_CLOSURE_INVENTORY_MISMATCH')
    all_fields={f['field_locator']:f['text'] for f in evidence['fields']}
    selected_nodes={t['target_pointer'] for t in selection['targets']};selected_fields=set(selection['fields'])
    issues=[];pending_nodes=set();pending_fields=set();claims=[];fields=[]
    unreviewed_nodes=set();unreviewed_fields=set()
    def issue(code,*,pointer=None,field=None,reason=None):
        issues.append({'kind':'review_protocol_error','reason_code':code,'target_pointer':pointer,
            'field_locator':field,'reason':reason or code})
        if pointer in all_nodes:pending_nodes.add(pointer)
        if field in all_fields:pending_fields.add(field)
    if not isinstance(raw,dict):raw={};issue('SOURCE_REVIEW_OBJECT_REQUIRED')
    known_contract=raw.get('contract_version','boi/process-operational-source-review@1')=='boi/process-operational-source-review@1'
    try:
        envelope=ProcessSourceReview.model_validate({**raw,'claims':[],'fields':[]})
        limitations=list(envelope.limitations)
    except ValueError as exc:
        limitations=[];issue('SOURCE_REVIEW_ENVELOPE_INVALID',reason=str(exc))
    def entries(key,identity,selected,carried):
        items=raw.get(key)
        if not isinstance(items,(list,tuple)):
            issue('SOURCE_REVIEW_'+key.upper()+'_ARRAY_REQUIRED');items=[]
        grouped={}
        for item in items:
            ref=item.get(identity) if isinstance(item,dict) else None
            if not isinstance(ref,str) or ref not in selected:
                issue('SOURCE_REVIEW_UNEXPECTED_'+key.upper()+'_TARGET');continue
            grouped.setdefault(ref,[]).append(item)
        for ref in sorted(selected):
            values=grouped.get(ref,[])
            kwargs={'pointer':ref} if key=='claims' else {'field':ref}
            if len(values)!=1:issue('SOURCE_REVIEW_MISSING_OR_DUPLICATE_'+key.upper(),**kwargs)
            elif not known_contract:issue('SOURCE_REVIEW_UNKNOWN_CONTRACT',**kwargs)
            else:yield values[0]
        for item in (previous_review or {}).get(key,[]):
            if item.get(identity) in carried:yield item
    def quote_binding(judgment):
        for quote in judgment.evidence:
            text=all_fields.get(quote.field_locator,'');offset=-1
            for _ in range(quote.occurrence+1):
                offset=text.find(quote.quote,offset+1)
                if offset<0:raise ValueError('SOURCE_REVIEW_QUOTE_NOT_IN_EXACT_FIELD')
    for raw_claim in entries('claims','target_pointer',selected_nodes,set(selection['carry_forward_nodes'])):
        ptr=raw_claim.get('target_pointer')
        try:claim=SourceNodeJudgment.model_validate(raw_claim);quote_binding(claim)
        except ValueError as exc:issue('SOURCE_REVIEW_NODE_JUDGMENT_INVALID',pointer=ptr,reason=str(exc))
        else:claims.append(claim.model_dump(mode='json'))
    known={c['target_pointer']:c for c in claims}
    for ptr in all_nodes-set(known)-pending_nodes:
        if review_scope=='selected_nodes' and ptr not in selected_nodes|set(selection['carry_forward_nodes']):
            pending_nodes.add(ptr);unreviewed_nodes.add(ptr)
        else:issue('SOURCE_REVIEW_NODE_JUDGMENT_MISSING',pointer=ptr)
    for raw_field in entries('fields','field_locator',selected_fields,set(selection['carry_forward_fields'])):
        loc=raw_field.get('field_locator')
        try:
            field=SourceFieldCoverage.model_validate(raw_field)
            if not set(field.target_pointers)<=coverage_pointers(draft,all_nodes,field,reference_contract_version):raise ValueError('SOURCE_REVIEW_UNKNOWN_COVERAGE_NODE')
            if field.status in ('partial','omitted') and not field.missing_meaning:
                raise ValueError('SOURCE_REVIEW_MISSING_MEANING_REQUIRED')
            if field.status=='represented' and (not field.target_pointers or any(p not in known or known[p]['label']!='supported' for p in field.target_pointers)):
                raise ValueError('SOURCE_REVIEW_COVERAGE_AWAITS_SUPPORTED_NODE_JUDGMENTS')
        except ValueError as exc:issue('SOURCE_REVIEW_FIELD_JUDGMENT_INVALID',field=loc,reason=str(exc))
        else:fields.append(field.model_dump(mode='json'))
    for loc in set(all_fields)-{f['field_locator'] for f in fields}-pending_fields:
        if review_scope=='selected_nodes' and loc not in selected_fields|set(selection['carry_forward_fields']):
            pending_fields.add(loc);unreviewed_fields.add(loc)
        else:issue('SOURCE_REVIEW_FIELD_JUDGMENT_MISSING',field=loc)
    valid={'contract_version':'boi/process-operational-source-review@1','claims':claims,'fields':fields,'limitations':limitations}
    semantic_failures=[{'target_pointer':c['target_pointer'],'failure_kind':c['failure_kind'],'reason':c['reason'],
        'evidence':c['evidence'],'origin':'model_source_judgment'} for c in claims if c['label']!='supported']
    semantic_failures += [{'target_pointer':'field:'+f['field_locator'],'field_locator':f['field_locator'],'failure_kind':'omission',
        'reason':f['missing_meaning'],'evidence':[],'origin':'model_source_judgment'} for f in fields if f['status'] in ('partial','omitted')]
    failed=[c['target_pointer'] for c in claims if c['label']!='supported']
    if native:
        affected=set([*failed,*pending_nodes])
        while True:
            expanded=affected|{p for p,deps in native_closures.items() if affected.intersection(deps)}
            if expanded==affected:break
            affected=expanded
        quarantined=sorted(affected)
    else:quarantined=dependent_nodes(draft,[*failed,*pending_nodes])
    if not native and not issues and not unreviewed_nodes and not unreviewed_fields:
        check=check_source_review(valid,draft=draft,evidence=evidence,reference_contract_version=reference_contract_version)
    else:
        check={'contract_version':'boi/process-source-review-check@2','assessment_complete':False,
            'claim_counts':dict(Counter(c['label'] for c in claims)),'field_counts':dict(Counter(f['status'] for f in fields)),
            'failures':semantic_failures,'failed_claim_pointers':failed,'quarantined_node_pointers':quarantined,
            'model_assessment_accepts_source_fidelity':False,'deterministic_entailment_proven':False,
            'scientific_correctness':'not_evaluated','whole_plan_qualified':False}
    check.update(review_protocol_failures=issues,pending_review_node_pointers=sorted(pending_nodes),
        reference_contract_version=reference_contract_version,
        pending_review_field_locators=sorted(pending_fields),
        usable_node_pointers=sorted(p for p,c in known.items() if c['label']=='supported' and p not in quarantined),
        observation_partition_version='boi/process-source-review-observation@1')
    if review_scope=='selected_nodes':
        check.update(review_scope=review_scope,selected_assessment_complete=not issues,
            intentionally_unreviewed_node_pointers=sorted(unreviewed_nodes),
            intentionally_unreviewed_field_locators=sorted(unreviewed_fields))
    return {'raw_assessment':original_raw,'validated_assessment':valid,'check':check}


def review_correction_selection(observation,*,draft,evidence,previous_selection):
    """Revisit invalid judgments and waiting coverage, not their candidate values."""
    check=observation['check'];nodes=set(check['pending_review_node_pointers']);fields=set(check['pending_review_field_locators'])
    if check['review_protocol_failures'] and not nodes and not fields:
        # An envelope/unknown-target error cannot always be assigned to a node.
        nodes={t['target_pointer'] for t in previous_selection['targets']};fields=set(previous_selection['fields'])
    all_targets=assessment_targets(draft,include_all_terms=True)
    return {'targets':[t for t in all_targets if t['target_pointer'] in nodes],
        'fields':[f['field_locator'] for f in evidence['fields'] if f['field_locator'] in fields],
        'carry_forward_nodes':[c['target_pointer'] for c in observation['validated_assessment']['claims'] if c['target_pointer'] not in nodes],
        'carry_forward_fields':[f['field_locator'] for f in observation['validated_assessment']['fields'] if f['field_locator'] not in fields]}


async def _infer_review_batches(*,material,infer,provider,root,attempt,knowledge_reading_ref,
        input_revisions,max_targets_per_call):
    """Limit output targets, retaining the complete input and exact raw batches.

    Coverage follows node review so it can use all collected judgments. This
    never invents missing judgments or retries a failed provider dispatch.
    """
    import asyncio,json
    from .boi_process_claim_review import source_review_prompt
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    targets=material['targets'];fields=material['field_locators_to_assess']
    if len(targets)<=max_targets_per_call and len(fields)<=max_targets_per_call:
        return await asyncio.to_thread(infer,provider=provider,prompt=source_review_prompt(material),
            schema=ProcessSourceReview.model_json_schema(),output_dir=root/f'provider-{attempt}',
            knowledge_reading_ref=knowledge_reading_ref,input_revisions=input_revisions)
    groups=[(targets[i:i+max_targets_per_call],[]) for i in range(0,len(targets),max_targets_per_call)]
    groups.extend(([],fields[i:i+max_targets_per_call]) for i in range(0,len(fields),max_targets_per_call))
    merged={'contract_version':'boi/process-operational-source-review@1','claims':[],'fields':[],'limitations':[]}
    journal={'contract_version':'boi/source-review-batches@1','material_digest':semantic_digest(material),
        'knowledge_reading_ref':knowledge_reading_ref,'input_revisions':input_revisions,
        'max_targets_per_call':max_targets_per_call,'status':'running','batches':[]}
    path=root/f'provider-{attempt}-batches.json'
    def save():path.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n')
    save()
    for index,(nodes,locators) in enumerate(groups):
        batch=copy.deepcopy(material)
        batch.update(targets=nodes,field_locators_to_assess=locators)
        if locators:
            batch['carried_node_judgments']+=copy.deepcopy(merged['claims'])
        (root/f'material-{attempt}-batch-{index}.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
        schema=ProcessSourceReview.model_json_schema()
        schema['properties']['claims']['maxItems']=len(nodes)
        schema['properties']['fields']['maxItems']=len(locators)
        try:
            raw,run=await asyncio.to_thread(infer,provider=provider,prompt=source_review_prompt(batch),
                schema=schema,output_dir=root/f'provider-{attempt}-batch-{index}',
                knowledge_reading_ref=knowledge_reading_ref,input_revisions=input_revisions)
            row={'index':index,'target_pointers':[n['target_pointer'] for n in nodes],
                'field_locators':locators,'provider':run,'raw_assessment':raw}
            journal['batches'].append(row);save()
            # Missing/invalid judgments remain pending in observe_source_review;
            # a batch cannot substitute targets belonging to another group.
            if (any(c.get('target_pointer') not in row['target_pointers'] for c in raw.get('claims',[]))
                or any(f.get('field_locator') not in locators for f in raw.get('fields',[]))
                or raw.get('contract_version',merged['contract_version'])!=merged['contract_version']):
                raise ValueError('SOURCE_REVIEW_BATCH_TARGET_OR_CONTRACT_MISMATCH')
            for key in ('claims','fields','limitations'):merged[key].extend(raw.get(key,[]))
        except Exception as exc:
            journal.update(status='failed',failed_batch=index,error_type=type(exc).__name__,error=str(exc))
            save();raise
    journal['status']='completed';save()
    return merged,{'status':'completed','method':'bounded_source_review','batch_journal':str(path),
        'batch_contract_version':'boi/source-review-batches@1','max_targets_per_call':max_targets_per_call,
        'batches':[{k:b[k] for k in ('index','provider','target_pointers','field_locators')} for b in journal['batches']]}


async def review_source_candidate(*,draft,evidence,context,knowledge_reading_ref,input_revisions,
        infer,provider,output_dir,selection,previous_review=None,max_corrections=1,stored_observation=None,
        reference_contract_version='boi/source-coverage-references@2',max_targets_per_call=8):
    """Review or correct a caller-read stored observation; never edit the candidate.

    The MCP caller must bind stored_observation to the exact candidate and record
    its provenance. A stored observation is carried history, not a new model run.
    """
    import asyncio,json
    from pathlib import Path
    from .boi_process_claim_review import source_review_material,source_review_prompt,SOURCE_REVIEW_INSTRUCTIONS_VERSION
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    if not 0<=max_corrections<=1:raise ValueError('SOURCE_REVIEW_CORRECTION_BUDGET_INVALID')
    if not 1<=max_targets_per_call<=16:raise ValueError('SOURCE_REVIEW_BATCH_LIMIT_INVALID')
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    attempts=[];base_digest=semantic_digest(draft);prior=previous_review
    if stored_observation is not None:
        if stored_observation['candidate_revision']!=input_revisions[0] or stored_observation['draft_digest']!=base_digest:
            raise ValueError('STORED_SOURCE_REVIEW_CANDIDATE_MISMATCH')
    for attempt in range(max_corrections+1):
        material=source_review_material(draft,evidence,context)
        pointers={t['target_pointer'] for t in selection['targets']}
        material.update(all_current_nodes_for_field_coverage=material['targets'],
            targets=[t for t in material['targets'] if t['target_pointer'] in pointers],
            carried_node_judgments=[c for c in (prior or {}).get('claims',[]) if c['target_pointer'] in selection['carry_forward_nodes']],
            field_locators_to_assess=selection['fields'])
        if attempt:
            material['previous_review_protocol_errors']=observation['check']['review_protocol_failures']
            material['correction_scope']='Correct only invalid review judgments/coverage. Candidate is unchanged; reread original evidence and contract. Do not convert a label merely to satisfy validation.'
        save(f'material-{attempt}.json',material)
        if attempt==0 and stored_observation is not None:
            raw=stored_observation['raw_assessment'];run={'status':'carried_stored_observation','new_model_dispatch':False,
                'observation_revision':stored_observation['observation_revision'],'synthetic_mutation':stored_observation.get('synthetic_mutation',False)}
        elif selection['targets'] or selection['fields']:
            raw,run=await _infer_review_batches(material=material,infer=infer,provider=provider,root=root,
                attempt=attempt,knowledge_reading_ref=knowledge_reading_ref,input_revisions=input_revisions,
                max_targets_per_call=max_targets_per_call)
        else:
            raw={'claims':[],'fields':[],'limitations':['Unchanged judgments carried from exact prior candidate review.']}
            run={'status':'reused_unchanged_review','new_model_dispatch':False}
        observation=observe_source_review(raw,draft=draft,evidence=evidence,selection=selection,previous_review=prior,
            reference_contract_version=reference_contract_version)
        attempts.append({'selection':selection,'provider':run,'observation':observation,'candidate_draft_digest':base_digest})
        save(f'attempt-{attempt}.json',attempts[-1])
        if not observation['check']['review_protocol_failures'] or attempt==max_corrections:break
        selection=review_correction_selection(observation,draft=draft,evidence=evidence,previous_selection=selection)
        prior=observation['validated_assessment']
    result={**observation,'attempts':attempts,'review_instructions_version':SOURCE_REVIEW_INSTRUCTIONS_VERSION,
        'reference_contract_version':reference_contract_version,
        'candidate_draft_digest':base_digest,'candidate_modified':False,'max_review_corrections':max_corrections}
    result['check'].update(review_instructions_version=SOURCE_REVIEW_INSTRUCTIONS_VERSION,
        provider_run=attempts[-1]['provider'],review_protocol_correction_count=len(attempts)-1,
        candidate_modified_by_review_correction=False)
    save('report.json',result);return result
