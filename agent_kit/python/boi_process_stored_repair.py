"""Bounded repair of an admitted stored process candidate over Wiki MCP.

No source extraction or evaluation inputs. Reading identity is persisted before
inference, so restart replays the same Wiki model task instead of renewing its
budget. Unknown model outcomes remain unknown in the existing work service.
"""
import asyncio,base64,copy,json
from pathlib import Path

from .boi_mcp_stage import run_mcp_stage
from .boi_process_intake import source_readings,read_stored_review_check,intake_review_status
from .boi_process_claim_review import (ProcessIntakeRepair,apply_intake_repair,process_context_view,
    source_review_selection,SOURCE_REVIEW_INSTRUCTIONS_VERSION,definition_reuse_review_prompt)
from .boi_process_review_observation import review_source_candidate,observe_source_review
from .boi_process_response_review import response_context_view
from .boi_process_reuse_evaluation import verified_reuse_material,ProcessReuseAssessment,check_reuse_assessment
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.ledger import record_digest
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from boi_api.app.governed_runtime.source_envelope import byte_digest

REPAIR_CONTRACT='boi/stored-process-partial-repair@1'


async def read_coverage_repair_scope(client,*,coverage_revision,candidate_revision,draft,evidence):
    """Read Wiki-bound operational diagnoses, never evaluator expectations.

    This is preparation only: it grants no attempts, changes no asset and
    does not interpret a reviewer's proposed source unit as an answer key.
    """
    view=await client.call('boi_process_coverage_read',{'revision':coverage_revision})
    return coverage_repair_scope(view,coverage_revision=coverage_revision,candidate_revision=candidate_revision,
        draft=draft,evidence=evidence)


def coverage_repair_scope(view,*,coverage_revision,candidate_revision,draft,evidence):
    """Pure projection used after Wiki's authorized observation validation."""
    from .boi_process_source_coverage import semantic_components
    if (view.get('origin')!='wiki_authorized_coverage_read' or view.get('reference_binding')!='bound'
            or view.get('alignment_revision')!=coverage_revision or view.get('candidate_revision')!=candidate_revision):
        raise ValueError('STORED_REPAIR_COVERAGE_BINDING_MISMATCH')
    if (view.get('candidate_draft_digest')!=semantic_digest(draft)
            or evidence['source']['digest']!=draft['source_revision_digest']):
        raise ValueError('STORED_REPAIR_COVERAGE_DRAFT_OR_SOURCE_MISMATCH')
    components={c['pointer']:c for c in semantic_components(draft)}
    replaceable={f'/records/{ri}/{kind}/{index}' for ri,record in enumerate(draft['records'])
        for kind in ('terms','assertions') for index,_ in enumerate(record[kind])}
    fields={f['field_locator']:f for f in evidence['fields']}
    diagnoses=[];deferred=[];nodes=set();allowed=set()
    for item in view['failures']:
        # An unsupported inventory interpretation is not a candidate error.
        if item['unit']['kind']!='domain_meaning' or item['status'] not in ('partial','omitted','conflicting'):
            deferred.append({'unit_id':item['unit_id'],'reason':'Inventory interpretation or context classification requires review, not candidate repair.'})
            continue
        selected=item['components']
        if any(components.get(c['pointer'])!=c for c in selected):
            raise ValueError('STORED_REPAIR_COVERAGE_COMPONENT_CHANGED')
        bound_fields={f['field_locator']:f for f in item['source_fields']}
        quotes=item['unit']['evidence']
        if not quotes or set(bound_fields)!={q['field_locator'] for q in quotes}:
            raise ValueError('STORED_REPAIR_COVERAGE_SOURCE_SCOPE_MISMATCH')
        for locator,read in bound_fields.items():
            original=fields.get(locator)
            if (original is None or read['source_revision']!=evidence['source']
                    or read['full_field_context']!=original['text'] or read['field_span_ref']!=original['span_ref']
                    or read['field_content_digest']!=original['content_digest']):
                raise ValueError('STORED_REPAIR_COVERAGE_SOURCE_CHANGED')
        pointers=sorted({c['node_pointer'] for c in selected if c['node_pointer'] in replaceable})
        nodes.update(pointers);allowed.update(bound_fields)
        diagnoses.append({'unit_id':item['unit_id'],'status':item['status'],'source_interpretation':item['unit'],
            'reason':item['reason'],'missing_meaning':item['missing_meaning'],
            'target_node_pointers':pointers,'context_component_pointers':[c['pointer'] for c in selected if c['node_pointer'] not in replaceable],
            'evidence':quotes,'stored_location':item['stored_location']})
    return {'contract_version':'boi/stored-process-coverage-repair-scope@1',
        'coverage_revision':coverage_revision,'candidate_revision':candidate_revision,
        'inventory_revision':view['inventory_revision'],'diagnoses':diagnoses,
        'failed_claim_pointers':sorted(nodes),'allowed_addition_fields':sorted(allowed),
        'deferred_inventory_diagnoses':deferred,'historical_pending_unit_ids':view['pending_unit_ids'],
        'current_reference_check':{k:view.get('current_reference_check',{}).get(k)
            for k in ('contract_version','pending_unit_ids','reference_check_complete')},
        'source_fidelity':'model_opinion_only','scientific_correctness':'not_evaluated',
        'new_model_runs':0,'new_receipts':0,'repair_budget_granted':False}


def repair_context_view(context,proposal,candidate_revision,*,version=3,active_harness=None):
    """Keep repair meaning once; retain exact Wiki refs for execution diagnostics.

    The caller still reads/acknowledges every full revision and verifies the
    original execution. This only changes the model input presentation.
    """
    view=response_context_view(context)
    for asset in view['assets']:
        content=asset['read_projection']
        if asset['revision']==candidate_revision and content.get('draft')==proposal['draft']:
            content['draft']={'same_json_as':'/proposal/draft',
                'value_digest':semantic_digest(proposal['draft'])}
        check=content.get('operative_review_check')
        if check is not None:
            # These are execution/binding diagnostics, not claim judgments,
            # applicability, conditions, exceptions or original quotations.
            omitted=[key for key in ('quotation_bindings','provider_run') if key in check]
            content['operative_review_check']={k:v for k,v in check.items() if k not in omitted}
            content['execution_diagnostics_in_exact_revision']=['/check/'+k for k in omitted]
        asset['projection_digest']=semantic_digest(content)
    if version not in (2,3,4):raise ValueError('REPAIR_PRESENTATION_VERSION_UNSUPPORTED')
    if version==4:
        active_skills=[s['requirement']['revision'] for s in context['selections']
            if s['parent']==active_harness and s['requirement']['role']=='skill' and s['status']=='selected']
        if active_harness is None or not active_skills:raise ValueError('REPAIR_ACTIVE_SKILL_REQUIRED')
        for asset in view['assets']:
            if asset['kind']=='skill' and asset['revision'] not in active_skills:
                asset['read_projection']={'historical_skill_revision':asset['revision'],
                    'current_operation_uses_skills':active_skills,
                    'scope':'Prior procedure remains in its exact revision; the current repair follows the selected harness skill. Domain definitions and source conditions remain here.'}
            elif asset['kind']=='tool':
                asset['read_projection']={'execution_contract_in_exact_revision':asset['revision'],
                    'scope':'Host executes these registered tools. This request only asks for a typed repair; full domain definitions, current skill and original source fields remain in this material.'}
            asset['projection_digest']=semantic_digest(asset['read_projection'])
    if version in (3,4):
        seen={}
        for index,asset in enumerate(view['assets']):
            value=asset['read_projection'];digest=semantic_digest(value)
            if digest in seen:
                previous=seen[digest]
                if view['assets'][previous]['read_projection']!=value:raise ValueError('REPAIR_PROJECTION_DIGEST_COLLISION')
                asset['read_projection']={'same_json_as':f'/context/assets/{previous}/read_projection','value_digest':digest}
                asset['projection_digest']=semantic_digest(asset['read_projection'])
            else:seen[digest]=index
    view['contract_version']=f'boi/process-repair-read-presentation@{version}'
    return view


async def read_repair_binding_inputs(client,invocation):
    """Read admitted input bytes, not a fresh projection response envelope."""
    material={}
    for artifact in invocation['inputs']:
        value=await client.call('boi_tool_execution',{'action':'input','request':{
            'invocation_id':invocation['invocation_id'],'name':artifact['name']}})
        raw=base64.b64decode(value['content_b64'],validate=True)
        if (value['invocation_id']!=invocation['invocation_id'] or value['input']!=artifact
                or byte_digest(raw)!=artifact['content_digest']):
            raise ValueError('STORED_REPAIR_INPUT_BINDING_MISMATCH')
        material[artifact['name']]=json.loads(raw)
    return material


def verify_stored_process_draft(proposal, stored_draft, *, admitted_inputs=None):
    """A reuse binder may add derived references to an otherwise unchanged draft.

    Never erase those fields or accept arbitrary differences: replay the
    existing deterministic binder on the exact admitted inputs when needed.
    The original empty-reference proposal remains the next repair's base.
    """
    raw=ProcessKnowledgeDraft.model_validate(proposal['draft']).model_dump(mode='json')
    if raw==stored_draft:return
    if admitted_inputs is None or admitted_inputs['draft']!=proposal:
        raise ValueError('STORED_PROCESS_REPAIR_PROPOSAL_CHANGED')
    from .boi_process_reuse import bind_process_reuse
    projected=bind_process_reuse(proposal,evidence=admitted_inputs['evidence'],
        context=admitted_inputs['context'],sources=admitted_inputs['sources'])
    if projected['draft']!=stored_draft:
        raise ValueError('STORED_PROCESS_REPAIR_PROPOSAL_CHANGED')


async def recheck_stored_source_review(client,*,candidate_revision,review_revision,output_dir):
    """Apply a versioned reference checker to authenticated unchanged observations."""
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    checked,binding=await read_stored_review_check(client,candidate_revision=candidate_revision,review_revision=review_revision)
    if binding['status']!='bound':raise ValueError('STORED_REVIEW_RECHECK_ADMITTED_LINK_REQUIRED')
    candidate=await client.read_asset(candidate_revision);review=await client.read_asset(review_revision)
    content=json.loads(review['asset']['content_json']);draft=json.loads(candidate['asset']['content_json'])['draft']
    sources=await source_readings(client,candidate['sources']);evidence=next(s for s in sources if s['source']['digest']==draft['source_revision_digest'])
    record=copy.deepcopy(content['source_observation']);prior=None
    reference_version='boi/source-coverage-references@2'
    save('pre-run-reference-contract.json',{'prior_review_revision':review_revision,'candidate_revision':candidate_revision,
        'reference_contract_version':reference_version,'input_observation_digest':semantic_digest(record),
        'purpose':'Permit real limitation pointers for non-domain context only. Never treat them as process support.',
        'expected_contrasts':['real limitation/non_domain accepted','unknown limitation rejected','limitation/represented rejected'],
        'new_model_calls':0,'source_or_candidate_change':False})
    for attempt in record['attempts']:
        observation=observe_source_review(attempt['observation']['raw_assessment'],draft=draft,evidence=evidence,
            selection=attempt['selection'],previous_review=prior,reference_contract_version=reference_version)
        attempt['observation']=observation;prior=observation['validated_assessment']
    record.update(**observation,reference_contract_version=reference_version)
    source_check={**content['check']['source_review'],**observation['check']}
    content.update(source_assessment=observation['validated_assessment'],source_observation=record,
        check={**content['check'],'source_review':source_check},
        mechanical_revalidation={'prior_review_revision':review_revision,'reference_contract_version':reference_version,
            'source_candidate_and_model_observations_unchanged':True,'new_model_calls':0})
    saved=await client.propose_asset({'namespace':review['namespace'],'logical_id':review['logical_id'],'title':review['title'],
        'description':'Versioned mechanical reference recheck of unchanged admitted model observations.',
        'kind':'pack','sources':review['sources'],'content_json':json.dumps(content,ensure_ascii=False),
        'dependencies':review['asset']['dependencies'],'previous_revision':review_revision,
        'definition_reading_ref':review['definition_reading_ref']},idempotency_key='source-reference-recheck:'+semantic_digest([review_revision,reference_version]))
    new_check,new_binding=await read_stored_review_check(client,candidate_revision=candidate_revision,review_revision=saved['revision'])
    result={'asset_revision':candidate_revision,'review_revision':saved['revision'],'sources':candidate['sources'],
        'primary_source':evidence['source'],'intake_review_status':intake_review_status(new_check,candidate_revision=candidate_revision),
        'review_binding':new_binding,'prior_review_revision':review_revision,'new_model_calls':0,
        'candidate_preserved':await client.read_asset(candidate_revision)==candidate,
        'prior_review_preserved':await client.read_asset(review_revision)==review,'whole_plan_qualified':False}
    save('original-review.json',review);save('review.json',await client.read_asset(saved['revision']));save('intake.json',result)
    return result


def draft_pointer_patch(raw):
    """Resolve root-qualified draft locations to the existing draft API.

    Only retained-location pointer roots are normalized. No node value, source
    quotation, failure or model judgment changes; retain the raw observation.
    """
    value=copy.deepcopy(raw);changes=[]
    for i,retraction in enumerate(value.get('retractions',[])):
        for j,pointer in enumerate(retraction.get('retained_locations',[])):
            if pointer.startswith('/draft/'):
                normalized=pointer[len('/draft'):]
                retraction['retained_locations'][j]=normalized
                changes.append({'patch_pointer':f'/retractions/{i}/retained_locations/{j}',
                    'original':pointer,'draft_relative':normalized,'operation':'same_document_root_resolution'})
    return value,changes


def patch_material_reuse_identity(material):
    """Only execution addresses may differ when carrying a completed patch.

    Source fields, failed nodes, proposal and prior judgments stay exact.
    Definition/review identities stay exact; profile/skill content stays exact.
    Harness namespace and registered tool addresses are host execution binding.
    """
    value=copy.deepcopy(material);value.pop('context_digest')
    context=value['context'];context.pop('context_digest');selections=context.pop('selections')
    identities=[];by_revision={}
    for asset in context.pop('assets'):
        kind=asset['kind']
        if kind=='tool':identity={'kind':kind,'authority':asset['authority'],'execution_address_only':True}
        elif kind=='harness':
            contract=copy.deepcopy(asset['read_projection']);contract.pop('namespace',None)
            for stage in contract.get('stages',[]):
                for tool in stage['tools']:tool.pop('tool_revision',None)
            identity={'kind':kind,'authority':asset['authority'],'contract':contract}
        elif kind in ('skill','profile'):
            identity={k:asset[k] for k in ('kind','authority','original_content_digest')}
        else:
            identity={k:asset[k] for k in ('kind','authority','revision','original_content_digest')}
        identities.append(json.dumps(identity,ensure_ascii=False,sort_keys=True))
        by_revision[semantic_digest(asset['revision'])]=semantic_digest(identity)
    context['semantic_asset_identities']=sorted(set(identities))
    normalized=[]
    for selection in selections:
        item=copy.deepcopy(selection)
        ref=item['requirement']['revision'];item['requirement']['revision']=by_revision.get(semantic_digest(ref),ref)
        if item['parent'] is not None:item['parent']=by_revision.get(semantic_digest(item['parent']),item['parent'])
        normalized.append(json.dumps(item,ensure_ascii=False,sort_keys=True))
    context['semantic_selections']=sorted(set(normalized))
    return value


async def restore_completed_intake_patch(client,*,execution_ref,prompt,material,refs,contract,sources):
    """Read a completed Wiki observation, never retry a provider or forge output."""
    from .boi_process_source_coverage import check_observation_binding
    ex=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':execution_ref}})
    body=ex['execution']['signed_execution']['body']
    task=await client.call('boi_tasks',{'task_package_id':body['invocation']['task_revision']['ref']})
    if task['status']!='completed':raise ValueError('STORED_PATCH_COMPLETED_TASK_REQUIRED')
    data=json.loads(next(i['content_json'] for i in task['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='request'))
    result=json.loads(ex['output_json'])['result'];original=json.loads(result['value_json'])
    linked=check_observation_binding(ex,task,execution_ref,prompt=data['prompt'],schema=ProcessIntakeRepair.model_json_schema(),
        contract=contract,input_revisions=data['input_revisions'],reading_ref=data['knowledge_reading_ref'],sources=sources,value=original)
    old_header,old_json=data['prompt'].rsplit('\n',1);new_header,_=prompt.rsplit('\n',1)
    old_material=json.loads(old_json)
    old_refs=data['input_revisions']
    if (old_header!=new_header or len(old_refs)!=len(refs) or old_refs[:2]+old_refs[3:]!=refs[:2]+refs[3:]
            or patch_material_reuse_identity(old_material)!=patch_material_reuse_identity(material)
            or original['context_digest']!=old_material['context_digest']
            or original['base_proposal_digest']!=material['base_proposal_digest']):
        raise ValueError('STORED_PATCH_SEMANTIC_INPUT_CHANGED')
    rebound=copy.deepcopy(original);rebound['context_digest']=material['context_digest']
    proof={'contract_version':'boi/stored-patch-execution-context-rebind@1','original_patch':original,
        'original_observation_link':linked,'original_material':old_material,
        'original_context_digest':original['context_digest'],'new_context_digest':material['context_digest'],
        'changed_patch_fields':['/context_digest'] if rebound!=original else [],
        'semantic_material_digest':semantic_digest(patch_material_reuse_identity(material)),
        'source_or_semantic_node_changed':False,'new_model_dispatch':False,
        'independent_candidate_review_still_required':True}
    run={**result['provider_run'],'wiki_execution_ref':execution_ref,'observation_replayed':True,
        'new_model_dispatch':False,'wiki_task_status':task['status'],'declared_stage_completed':True,
        'execution_context_rebind':{k:v for k,v in proof.items() if k not in ('original_patch','original_material')}}
    return rebound,run,proof


async def repair_stored_process(client,*,runtime,candidate_revision,review_revision,installed,
        request_id,work_namespace,output_dir,infer_for,provider='codex',max_review_corrections=0,coverage_revision=None,defer_review=False,
        completed_patch_execution=None):
    if max_review_corrections not in (0,1):raise ValueError('PROCESS_REVIEW_CORRECTION_BUDGET_INVALID')
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    candidate=await client.read_asset(candidate_revision);review=await client.read_asset(review_revision)
    content=json.loads(candidate['asset']['content_json']);old_review=json.loads(review['asset']['content_json'])
    check,binding=await read_stored_review_check(client,candidate_revision=candidate_revision,review_revision=review_revision)
    save('original-candidate.json',candidate);save('original-review.json',review);save('original-binding.json',binding)
    if binding['status']!='bound':raise ValueError('STORED_PROCESS_REPAIR_REVIEW_LINK_REQUIRED')
    if coverage_revision is None and intake_review_status(check,candidate_revision=candidate_revision)=='accepted_by_model_review':
        raise ValueError('STORED_PROCESS_REPAIR_NO_RECORDED_FAILURE')
    sources=await source_readings(client,candidate['sources'])
    evidence=next(s for s in sources if s['source']['digest']==content['draft']['source_revision_digest'])
    save('sources.json',sources)
    coverage=None
    if coverage_revision is not None:
        coverage=await read_coverage_repair_scope(client,coverage_revision=coverage_revision,candidate_revision=candidate_revision,draft=content['draft'],evidence=evidence)
        save('coverage-repair-scope.json',coverage)
        if not coverage['diagnoses']:raise ValueError('STORED_PROCESS_REPAIR_NO_COVERAGE_FAILURE')
    repair_contract='boi/stored-process-partial-repair@2' if coverage is not None else REPAIR_CONTRACT
    # Recover exact original proposal from the admitted binding execution, not
    # from reconstructed prose or a local recovery file.
    executed=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':content['execution_refs'][0]}})
    body=executed['execution']['signed_execution']['body'];bound=json.loads(executed['output_json'])['result']
    if body['outcome']!='completed' or any(content.get(k)!=v for k,v in bound.items()):
        raise ValueError('STORED_PROCESS_REPAIR_CANDIDATE_EXECUTION_MISMATCH')
    package=await client.call('boi_tasks',{'task_package_id':body['invocation']['task_revision']['ref']})
    contract=package['domain_execution_contract']
    proposal=json.loads(next(i['content_json'] for i in contract['inputs'] if i['kind']=='proposal' and i['name']=='draft'))
    save('original-execution.json',executed);save('original-task.json',package);save('original-proposal.json',proposal)
    admitted=None
    if ProcessKnowledgeDraft.model_validate(proposal['draft']).model_dump(mode='json')!=content['draft']:
        admitted=await read_repair_binding_inputs(client,body['invocation'])
        save('original-admitted-inputs.json',admitted)
    verify_stored_process_draft(proposal,content['draft'],admitted_inputs=admitted)
    refs=[candidate_revision,review_revision,installed['harness']]
    requirement={'revision':installed['harness'],'role':'harness','reason':'Read the currently installed repair/binding contract.',
        'stages':['extract','reuse','review','explain']}
    original_roots=[requirement,{'revision':candidate_revision,'role':'repair_candidate','reason':'Exact stored candidate to repair.','stages':['review']},
        {'revision':review_revision,'role':'stored_failure','reason':'Original recorded failures; reviewer judgments may be wrong.','stages':['review']}]
    if coverage is not None:
        refs.append(coverage_revision)
        original_roots.append({'revision':coverage_revision,'role':'stored_coverage_diagnosis','reason':'Read source-first operational diagnoses, which may be mistaken.','stages':['review']})
    async def durable_reading(phase,roots,context_namespace=None):
        identity=request_id+':reading:'+phase
        data={'contract_version':repair_contract,'candidate_revision':candidate_revision,'review_revision':review_revision,
            'harness_revision':installed['harness'],'roots':roots,'sources':candidate['sources'],
            'repair_schema_digest':semantic_digest(ProcessIntakeRepair.model_json_schema()),
            'review_contract':SOURCE_REVIEW_INSTRUCTIONS_VERSION,'max_patch_calls':1,'max_review_corrections':max_review_corrections}
        if coverage is not None:data['coverage_revision']=coverage_revision;data['coverage_scope_digest']=semantic_digest(coverage)
        if defer_review:data['review_completion']='deferred_for_independent_coverage_review'
        if context_namespace is not None:data['context_namespace']=context_namespace
        found=next((a for a in (await client.catalog_assets(namespace=work_namespace,kind='pack'))['items'] if a['logical_id']==identity),None)
        if found:
            stored=await client.read_asset(found['revision']);value=json.loads(stored['asset']['content_json'])
            if value['request']!=data:raise ValueError('STORED_PROCESS_REPAIR_REQUEST_CHANGED')
            return await client.restore_task_knowledge(value['reading_ref'],candidate['sources'],
                principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
        reading=await client.read_task_knowledge({'sources':candidate['sources'],'namespace':context_namespace or candidate['namespace'],
            'purpose':identity,'roots':roots,'tool_use':'selected_stage'},principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
        await client.propose_asset({'namespace':work_namespace,'logical_id':identity,'kind':'pack','title':'제한 수정의 고정 입력',
            'description':'Exact acknowledged input and attempt budget. No semantic verdict.','sources':candidate['sources'],
            'content_json':json.dumps({'request':data,'reading_ref':reading['reading_ref']},ensure_ascii=False),
            'definition_reading_ref':reading['reading_ref']},idempotency_key=identity)
        return reading
    reading=await durable_reading('patch',original_roots);save('patch-reading.json',reading)
    failures=check['source_review'];allowed={q['field_locator'] for f in failures['failures'] for q in f.get('evidence',[])}
    allowed.update(f['field_locator'] for f in failures['failures'] if f.get('field_locator'))
    failed_claims=set(failures['failed_claim_pointers'])
    if coverage is not None:
        failed_claims.update(coverage['failed_claim_pointers']);allowed.update(coverage['allowed_addition_fields'])
    material={'base_proposal_digest':semantic_digest(proposal),'context_digest':reading['context']['context_digest'],
        'proposal':proposal,'source_failures':failures['failures'],'failed_claims':failures['failed_claim_pointers'],
        'failed_uses':check['failed_use_pointers'],'use_assessment':old_review.get('assessment'),
        'allowed_addition_fields':sorted(allowed),'context':repair_context_view(reading['context'],proposal,candidate_revision,version=4,active_harness=installed['harness']),
        'original_sources':[{'source':s['source'],'fields':[{k:f[k] for k in ('field_locator','text','span_ref','content_digest')}
            for f in s['fields']]} for s in sources]}
    if not check['failed_use_pointers'] and check.get('model_assessment_accepts_definition_uses'):
        material['use_assessment']={'prior_review_revision':review_revision,'no_recorded_definition_use_failures':True,
            'scope':'Preserve unchanged definition uses. The complete prior accepted judgments remain in the exact read review; current source fields, definitions and proposed uses remain in this input. Changed dependencies will be independently reviewed.'}
    if coverage is not None:
        material['coverage_diagnoses']=coverage;material['failed_claims']=sorted(failed_claims)
        # Complete original field text and binding identifiers occur once.
        # The full manifest envelopes remain in sources.json and admitted reads.
        material['original_sources']=[{'source':s['source'],'fields':[
            {k:f[k] for k in ('field_locator','text','span_ref','content_digest')} for f in s['fields']]} for s in sources]
        active_skills=[s['requirement']['revision'] for s in reading['context']['selections']
            if s['parent']==installed['harness'] and s['requirement']['role']=='skill' and s['status']=='selected']
        for asset in material['context']['assets']:
            if asset['revision']==coverage_revision:
                asset['read_projection']={'same_json_as':'/coverage_diagnoses','value_digest':semantic_digest(coverage)}
                asset['projection_digest']=semantic_digest(asset['read_projection'])
            elif asset['revision']==coverage['inventory_revision']:
                from .boi_process_source_coverage import SourceMeaningUnit
                raw_units=asset['read_projection']['raw_observation']['units']
                units={u['unit_id']:SourceMeaningUnit.model_validate(u).model_dump(mode='json') for u in raw_units}
                selected=[]
                for i,diagnosis in enumerate(coverage['diagnoses']):
                    unit=diagnosis['source_interpretation']
                    if units.get(unit['unit_id'])!=unit:raise ValueError('STORED_REPAIR_INVENTORY_DIAGNOSIS_DRIFT')
                    selected.append({'value_reference':f'/coverage_diagnoses/diagnoses/{i}/source_interpretation','value_digest':semantic_digest(unit)})
                asset['read_projection']={'operative_source_units':selected,'full_inventory_preserved_in_revision':asset['revision'],
                    'scope':'Only diagnosed units required for this partial repair; unselected source units remain in the exact read inventory.'}
                asset['projection_digest']=semantic_digest(asset['read_projection'])
            elif asset['kind']=='skill' and asset['revision'] not in active_skills:
                asset['read_projection']={'historical_skill_revision':asset['revision'],
                    'current_operation_uses_skills':active_skills,
                    'scope':'Prior execution procedure retained in its exact revision; current repair follows the selected harness skill. Domain definitions and source conditions are not omitted.'}
                asset['projection_digest']=semantic_digest(asset['read_projection'])
    prompt=('Read only the original sources, read Wiki contracts/definitions, candidate and recorded review. Reviewers can be wrong. '
        'Return a minimal typed repair of failed nodes/uses and necessary dependent references, preserving all unaffected meaning. '
        'Do not re-extract. No answer key or desired patch is provided. Preserve IDs. You may retract an erroneous assertion '
        'with exact source evidence, reason and pointers to unchanged locations where information remains retained. '
        'Do not invent a process subject for document information or elevate source statements to Wiki authority. '
        'Fix affected references explicitly; scope pointers use original draft positions and are remapped mechanically. '
        'Unresolvable failures need reasons and missing evidence in unresolved. Replacement/addition/retraction choices remain yours. '
        'Copy base_proposal_digest and context_digest exactly.\n'+json.dumps(material,ensure_ascii=False,separators=(',',':')))
    save('patch-material.json',material);(root/'patch-prompt.txt').write_text(prompt)
    if completed_patch_execution is None:
        patch,model=await asyncio.to_thread(infer_for(repair_contract,refs),provider=provider,prompt=prompt,
            schema=ProcessIntakeRepair.model_json_schema(),output_dir=root/'patch',knowledge_reading_ref=reading['reading_ref'],input_revisions=refs)
    else:
        patch,model,proof=await restore_completed_intake_patch(client,execution_ref=completed_patch_execution,
            prompt=prompt,material=material,refs=refs,contract=repair_contract,sources=candidate['sources'])
        save('completed-patch-reuse-proof.json',proof)
    save('patch-provider.json',model);save('patch.json',patch)
    patch,normalizations=draft_pointer_patch(patch)
    save('patch-pointer-normalization.json',normalizations);save('applied-patch.json',patch)
    repaired,delta=apply_intake_repair(proposal,patch,failed_claims=failed_claims,
        failed_uses=set(check['failed_use_pointers']),allowed_fields=allowed,context_digest=reading['context']['context_digest'],source_evidence=evidence)
    save('delta.json',delta);save('repaired-proposal.json',repaired)
    # The repair observation reads the stored business namespace. Execution
    # must use the selected harness's declared namespace. Preserve that full
    # definition inventory as explicit roots when the two namespaces differ.
    harness=json.loads(next(a['content_json'] for a in reading['context']['assets'] if a['revision']==installed['harness']))
    if harness['namespace']!=candidate['namespace']:
        definition_roots=[{'revision':a['revision'],'role':'read_definition','reason':'Carry the exact repair-reading definition inventory.',
            'stages':['reuse','review']} for a in reading['context']['assets'] if a['kind']=='definition']
        next_reading=await durable_reading('binding',original_roots+definition_roots,context_namespace=harness['namespace'])
        old_digest=repaired['context_digest'];new_digest=next_reading['context']['context_digest']
        repaired=copy.deepcopy(repaired);repaired['context_digest']=new_digest;repaired['draft']['extraction_context_digest']=new_digest
        save('binding-context-rebind.json',{'original_context_digest':old_digest,'binding_context_digest':new_digest,
            'changed_fields':['/context_digest','/draft/extraction_context_digest'],
            'new_model_dispatch':False,'source_or_semantic_node_changed':False,
            'reason':'Use declared harness namespace while retaining exact read definitions and source.'})
        reading=next_reading
    save('binding-reading.json',reading);save('binding-proposal.json',repaired)
    inputs=[{'kind':'proposal','name':'draft','content_json':json.dumps(repaired,ensure_ascii=False)},
        {'kind':'source_projection','name':'evidence','source':evidence['source'],'manifest_revision':{
            'ref':evidence['manifest']['manifest_ref'],'revision_digest':record_digest(evidence['manifest']['manifest_ref'])}},
        {'kind':'source_projection_bundle','name':'sources','projections':[{'source':s['source'],'manifest_revision':{
            'ref':s['manifest']['manifest_ref'],'revision_digest':record_digest(s['manifest']['manifest_ref'])}} for s in sources]}]
    stage=await run_mcp_stage(client,reading=reading,harness_revision=installed['harness'],stage_id='reuse',
        sources=candidate['sources'],inputs=inputs,execute=installed['execute'],idempotency_key=request_id+':bind',
        execution_journal_dir=root/'binding-executions')
    save('binding-stage.json',stage)
    if stage['status'] not in ('completed','already_completed'):
        return {'status':'binding_unresolved','stage':stage,'whole_plan_qualified':False}
    output=stage['executions'][0]['output']['result']
    content={**output,'execution_refs':[e['admission']['execution_ref'] for e in stage['executions']],
        'harness_revision':installed['harness'],'repair_history':{'original_candidate':candidate_revision,'original_review':review_revision,
            'patch_provider':model,'delta':delta,'request_id':request_id,'new_source_extraction':False,
            'patch_pointer_normalization':normalizations,
            'patch_observation_context_digest':model.get('execution_context_rebind',{}).get('original_context_digest',patch['context_digest']),
            'binding_context_digest':reading['context']['context_digest']}}
    if coverage is not None:content['repair_history']['coverage_diagnosis']=coverage
    dependencies=[requirement,*[{'revision':r,'role':'compared_definition','reason':'Exact compared definition.',
        'stages':['reuse','review','explain']} for r in output['definition_comparison_revisions']]]
    if coverage is not None:
        dependencies.append({'revision':coverage_revision,'role':'repair_diagnosis','reason':'Exact original source-first diagnosis.','stages':['review','explain']})
    saved=await client.propose_asset({'namespace':candidate['namespace'],'logical_id':candidate['logical_id'],
        'title':candidate['title'],'description':'Stored failure repaired as a new provisional revision; inspect review and history.',
        'kind':'definition','sources':candidate['sources'],'content_json':json.dumps(content,ensure_ascii=False),
        'previous_revision':candidate_revision,'dependencies':dependencies,'definition_reading_ref':reading['reading_ref']},
        idempotency_key=request_id+':candidate')
    save('candidate.json',await client.read_asset(saved['revision']))
    review_roots=[requirement,{'revision':saved['revision'],'role':'reviewed_candidate','reason':'Review this exact repaired candidate.',
        'stages':['review','explain']}]
    review_reading=await durable_reading('review',review_roots);save('review-reading.json',review_reading)
    if defer_review:
        result={'asset_revision':saved['revision'],'review_reading_ref':review_reading['reading_ref'],'status':'stored_pending_independent_review',
            'intake_review_status':'unresolved_intake_review','user_request_fulfilled':False,'whole_plan_qualified':False}
        save('report.json',result);return result
    return await review_stored_process_repair(client,runtime=runtime,candidate_revision=saved['revision'],
        review_reading_ref=review_reading['reading_ref'],request_id=request_id,output_dir=root/'review-completion',
        infer_for=infer_for,provider=provider,max_review_corrections=max_review_corrections)


async def review_stored_process_repair(client,*,runtime,candidate_revision,review_reading_ref,request_id,
        output_dir,infer_for,provider='codex',max_review_corrections=0):
    """Resume from actual stored repaired candidate; no binding or patch replay."""
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=False)
    def save(name,value):(root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    current=await client.read_asset(candidate_revision);content=json.loads(current['asset']['content_json'])
    history=content['repair_history'];candidate_revision=history['original_candidate'];review_revision=history['original_review']
    candidate=await client.read_asset(candidate_revision);review=await client.read_asset(review_revision)
    if current['previous_revision']!=candidate_revision or current['sources']!=candidate['sources']:
        raise ValueError('STORED_REPAIR_HISTORY_MISMATCH')
    old_review=json.loads(review['asset']['content_json']);delta=history['delta'];saved={'revision':current['revision']}
    installed={'harness':content['harness_revision']}
    sources=await source_readings(client,current['sources'])
    evidence=next(s for s in sources if s['source']['digest']==content['draft']['source_revision_digest'])
    async def restore(ref):return await client.restore_task_knowledge(ref,current['sources'],
        principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    reading=await restore(current['definition_reading_ref']);review_reading=await restore(review_reading_ref)
    if current['revision'] not in [a['revision'] for a in review_reading['context']['assets']]:
        raise ValueError('STORED_REPAIR_REVIEW_CANDIDATE_NOT_READ')
    executed=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':content['execution_refs'][0]}})
    body=executed['execution']['signed_execution']['body'];output=json.loads(executed['output_json'])['result']
    if body['outcome']!='completed' or any(content.get(k)!=v for k,v in output.items()):
        raise ValueError('STORED_REPAIR_ADMITTED_OUTPUT_MISMATCH')
    package=await client.call('boi_tasks',{'task_package_id':body['invocation']['task_revision']['ref']})
    repaired=json.loads(next(i['content_json'] for i in package['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='draft'))
    admitted_inputs=await read_repair_binding_inputs(client,body['invocation'])
    if admitted_inputs['draft']!=repaired or admitted_inputs['context']!=reading['context']:
        raise ValueError('STORED_REPAIR_INPUT_CONTEXT_MISMATCH')
    proposal={'draft':json.loads(candidate['asset']['content_json'])['draft']}
    review_roots=[{'revision':installed['harness'],'role':'harness','reason':'Exact bound contract.','stages':['review','explain']},
        {'revision':current['revision'],'role':'reviewed_candidate','reason':'Exact repaired candidate.','stages':['review','explain']}]
    save('candidate.json',current);save('original-review.json',review);save('binding-reading.json',reading)
    save('review-reading.json',review_reading);save('admitted-binding.json',executed)
    selection=source_review_selection(output['draft'],evidence,previous_draft=proposal['draft'],previous_review=old_review['source_assessment'])
    # New harness/profile/skill means old judgments are not reusable across
    # contracts. Selection already covers record applicability closure here.
    original_reading=await client.restore_task_knowledge(candidate['definition_reading_ref'],candidate['sources'],
        principal_id=runtime['principal'].employee_id,policy_digest=runtime['authorization'].policy_digest)
    relevant=lambda ctx:[a for a in ctx['assets'] if a['kind'] in ('definition','harness','profile','skill')]
    if (relevant(original_reading['context'])!=relevant(reading['context'])
            or old_review.get('source_observation',{}).get('review_instructions_version')!=SOURCE_REVIEW_INSTRUCTIONS_VERSION):
        selection=source_review_selection(output['draft'],evidence)
    review_refs=[saved['revision'],installed['harness']]
    observation=await review_source_candidate(draft=output['draft'],evidence=evidence,context=reading['context'],
        knowledge_reading_ref=review_reading['reading_ref'],input_revisions=review_refs,
        infer=infer_for(SOURCE_REVIEW_INSTRUCTIONS_VERSION,review_refs),provider=provider,output_dir=root/'source-review',
        selection=selection,previous_review=old_review['source_assessment'],max_corrections=max_review_corrections)
    source_check=observation['check'];source_check['prior_review_revision']=review_revision
    assessed=None;reuse={'assessment_complete':True,'model_assessment_accepts_definition_uses':True,
        'failed_use_pointers':[],'reuse_status':'no_proposed_uses_to_review'}
    if output['definition_uses']:
        reuse_material=verified_reuse_material(proposal=admitted_inputs['draft'],bound=output,
            evidence=admitted_inputs['evidence'],context=admitted_inputs['context'],sources=admitted_inputs['sources'])
        assessed,reuse_model=await asyncio.to_thread(infer_for('boi/process-definition-use-review@1',review_refs),provider=provider,
            prompt=definition_reuse_review_prompt(reuse_material),schema=ProcessReuseAssessment.model_json_schema(),
            output_dir=root/'reuse-review',knowledge_reading_ref=review_reading['reading_ref'],input_revisions=review_refs)
        reuse=check_reuse_assessment(assessed,material=reuse_material)
        reuse.update(provider_run=reuse_model,failed_use_pointers=[u['use_pointer'] for u in assessed['uses'] if any(j['label']!='supported' for j in u['judgments'])])
    current_check={**reuse,'candidate_revision':saved['revision'],'source_review':source_check,
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}
    reviewed=await client.propose_asset({'namespace':candidate['namespace'],
        'logical_id':candidate['logical_id']+':review:'+saved['revision']['revision_digest'],'kind':'pack',
        'title':'수정된 공정 후보의 원문 검토','description':'Source fidelity model opinion, not scientific truth.',
        'sources':candidate['sources'],'dependencies':review_roots,'definition_reading_ref':review_reading['reading_ref'],
        'content_json':json.dumps({'source_assessment':observation['validated_assessment'],'source_observation':observation,
            'assessment':assessed,'check':current_check},ensure_ascii=False)},idempotency_key=request_id+':review')
    save('review.json',await client.read_asset(reviewed['revision']))
    checked,current_binding=await read_stored_review_check(client,candidate_revision=saved['revision'],review_revision=reviewed['revision'])
    status=intake_review_status(checked,candidate_revision=saved['revision'])
    result={'asset_revision':saved['revision'],'review_revision':reviewed['revision'],'sources':candidate['sources'],
        'primary_source':evidence['source'],'intake_review_status':status,'review_binding':current_binding,
        'status':'recorded_with_model_review' if status=='accepted_by_model_review' else 'recorded_with_unresolved_review',
        'original_candidate_preserved':await client.read_asset(candidate_revision)==candidate,
        'original_review_preserved':await client.read_asset(review_revision)==review,'delta':delta,
        'new_source_extraction':False,'host_driven_mcp_plus_model':True,'native_agent_flow_completed':False,'whole_plan_qualified':False}
    save('report.json',result);return result
