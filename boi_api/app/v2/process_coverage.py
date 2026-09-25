"""Wiki-authorized reading of saved source-first coverage and actual receipts."""
import json
from ..governed_runtime.semantic_binding_contract import RevisionRef,semantic_digest
from ..governed_runtime.source_envelope import ArtifactEnvelope
from ..governed_runtime.domain_work_contract import DomainToolEvidenceRequest


def read_process_coverage(intake,principal,request):
    from .domain_intake import DomainAssetReadRequest
    from .process_review_binding import read_sources
    from agent_kit.python.boi_process_categories import read_category_contract,validate_category_semantics
    from agent_kit.python.boi_process_source_coverage import (INVENTORY_CONTRACT,ALIGNMENT_CONTRACT,
        SourceMeaningInventory,SourceMeaningAlignment,inventory_material,inventory_prompt,alignment_material,
        alignment_prompt,check_inventory,observe_alignment,check_observation_binding,check_source_reference_roles,
        REPAIRED_ALIGNMENT_CONTRACT,RepairedSourceMeaningAlignment,repaired_alignment_material,repaired_alignment_prompt,check_repaired_alignment)
    def asset(ref):return intake.read_asset(principal,DomainAssetReadRequest(revision=ref,lane='provisional'))
    stored=intake.read_asset(principal,request);aligned=json.loads(stored['asset']['content_json'])
    repaired=aligned.get('contract_version')==REPAIRED_ALIGNMENT_CONTRACT
    if aligned.get('contract_version') not in (ALIGNMENT_CONTRACT,REPAIRED_ALIGNMENT_CONTRACT):raise ValueError('PROCESS_COVERAGE_CONTRACT_REQUIRED')
    refs=aligned['input_revisions']
    if len(refs)!=(4 if repaired else 3):raise ValueError('PROCESS_COVERAGE_INPUT_SCOPE_REQUIRED')
    candidate=asset(refs[0]);inventory=asset(refs[1]);content=json.loads(candidate['asset']['content_json']);inventoried=json.loads(inventory['asset']['content_json'])
    if inventoried.get('contract_version')!=INVENTORY_CONTRACT or stored['sources']!=candidate['sources'] or inventory['sources']!=candidate['sources']:
        raise ValueError('PROCESS_COVERAGE_SOURCE_OR_INVENTORY_MISMATCH')
    auth,work=intake._work(principal);sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    def reading(ref):return work.contexts.validate_reading(authorization=auth,revision=RevisionRef.model_validate(ref),sources=sources,require_current=False).model_dump(mode='json')
    original_context=reading(candidate['definition_reading_ref']);category=read_category_contract(original_context);profile=category['profile_revision']
    if profile!=refs[2] or (repaired and refs[3]!=content['harness_revision']):raise ValueError('PROCESS_COVERAGE_PROFILE_MISMATCH')
    inventory_refs=inventoried['input_revisions']
    if len(inventory_refs)!=1:raise ValueError('PROCESS_COVERAGE_INVENTORY_PROFILE_REQUIRED')
    inventory_profile=asset(inventory_refs[0]);profile_content=json.loads(inventory_profile['asset']['content_json'])
    semantics=validate_category_semantics(profile_content['category_semantics'])
    inventory_category={'profile_revision':inventory_refs[0],'profile_content_digest':inventory_profile['asset']['content_digest'],
        'contract':semantics,'contract_digest':semantic_digest(semantics),'source_fidelity':'not_evaluated','historical_categories_reinterpreted':False}
    evidence=next(s for s in read_sources(intake,principal,sources) if s['source']['digest']==content['draft']['source_revision_digest'])
    first=inventory_material(evidence,inventory_category);icheck=check_inventory(inventoried['raw_observation'],evidence)
    second=alignment_material(icheck['inventory'],content['draft'],evidence,category)
    check=None if repaired else observe_alignment(aligned['raw_observation'],icheck['inventory'],content['draft'])
    second_prompt=alignment_prompt(second);second_schema=SourceMeaningAlignment.model_json_schema();second_contract=ALIGNMENT_CONTRACT
    if repaired:
        changed=content['repair_history']['delta']['changed_nodes']
        if aligned['changed_node_pointers']!=changed:raise ValueError('PROCESS_COVERAGE_CHANGED_NODE_SCOPE_MISMATCH')
        second=repaired_alignment_material(icheck['inventory'],content['draft'],evidence,category,changed)
        check=check_repaired_alignment(aligned['raw_observation'],icheck['inventory'],content['draft'],evidence,changed)
        second_prompt=repaired_alignment_prompt(second);second_schema=RepairedSourceMeaningAlignment.model_json_schema();second_contract=REPAIRED_ALIGNMENT_CONTRACT
    receipts=[]
    for record,phase,material,prompt,schema,contract,expected_refs,checked in (
        (inventory,inventoried,first,inventory_prompt(first),SourceMeaningInventory.model_json_schema(),INVENTORY_CONTRACT,inventory_refs,icheck),
        (stored,aligned,second,second_prompt,second_schema,second_contract,refs,check)):
        ctx=reading(phase['reading_ref']);available=[a['revision'] for a in ctx['assets']]
        if record['definition_reading_ref']!=phase['reading_ref'] or any(r not in available for r in expected_refs):
            raise ValueError('PROCESS_COVERAGE_ACKNOWLEDGED_INPUT_MISSING')
        if phase['material_digest']!=semantic_digest(material) or phase['check']!=checked:
            raise ValueError('PROCESS_COVERAGE_STORED_CHECK_MISMATCH')
        ref=phase['provider']['wiki_execution_ref'];ex=work.read_evidence(authorization=auth,request=DomainToolEvidenceRequest(execution_ref=ref))
        task=ex['execution']['signed_execution']['body']['invocation']['task_revision']['ref'];package=work._package(auth,task,require_current=False)
        binding=check_observation_binding(ex,package,ref,prompt=prompt,schema=schema,contract=contract,input_revisions=expected_refs,
            reading_ref=phase['reading_ref'],sources=candidate['sources'],value=phase['raw_observation'],allow_json_member_order=True)
        receipts.append({'asset_revision':record['revision'],**binding})
    # Recomputed with a separately versioned reference checker. Neither the
    # persisted @1 check nor its actual execution/receipt is replaced.
    repair_check=check if repaired else None
    if repaired:check=check['coverage']
    reference_roles=check_source_reference_roles(
        {k:aligned['raw_observation'][k] for k in ('alignments','limitations')},
        icheck['inventory'],content['draft'],evidence,version='boi/source-alignment-reference-roles@2')
    fields={f['field_locator']:f for f in evidence['fields']};failures=[]
    record_labels={f'/records/{index}':next(t['label'] for t in record['terms'] if t['term_id']==record['process_ref'])
        for index,record in enumerate(content['draft']['records'])}
    for index,item in enumerate(check['failures']):
        source_fields=[]
        for q in item['unit']['evidence']:
            field=fields[q['field_locator']]
            if any(f['field_locator']==q['field_locator'] for f in source_fields):continue
            source_fields.append({'source_revision':evidence['source'],'field_locator':q['field_locator'],
                'field_span_ref':field['span_ref'],'field_content_digest':field['content_digest'],'quoted_anchor':q['quote'],
                'full_field_context':field['text'],'citation_scope':'quoted anchor plus complete read field; source fidelity remains model opinion'})
        names=[]
        for component in item['components']:
            parent='/'.join(component['node_pointer'].split('/')[:3]);name=record_labels.get(parent)
            if name and name not in names:names.append(name)
        failure_path=f'/check/coverage/failures/{index}' if repaired else f'/check/failures/{index}'
        failures.append({**item,'process_names':names,'stored_location':{'asset_revision':stored['revision'],'content_json_pointer':failure_path},'source_fields':source_fields})
    result={'contract_version':'boi/process-coverage-view@3','origin':'wiki_authorized_coverage_read','reference_binding':'bound',
        'alignment_revision':stored['revision'],'inventory_revision':inventory['revision'],'candidate_revision':candidate['revision'],
        'candidate_draft_digest':semantic_digest(content['draft']),
        'authority':stored['asset']['authority'],'status':'PROVISIONAL','assessment_complete':check['assessment_complete'],
        'unit_count':len(icheck['inventory']['units']),'valid_unit_count':len(check['alignments']),
        'failure_count':len(failures),'failures':failures,'pending_count':len(check['pending_unit_ids']),
        'pending_unit_ids':check['pending_unit_ids'],'protocol_failures':check['protocol_failures'],
        'pending_scope':'historical_observation_contract; see current_reference_check for current reference roles only',
        'current_reference_check':reference_roles,
        'receipts':receipts,'ui_url':'/domain-coverage/'+stored['revision']['revision_digest'].split(':')[1],
        'source_fidelity':'model_opinion_only','scientific_correctness':'not_evaluated',
        'canonical_projection_eligible':False,'new_model_runs':0,'new_receipts':0,'whole_plan_qualified':False}
    from agent_kit.python.boi_process_stored_repair import coverage_repair_scope
    result['repair_scope']=coverage_repair_scope(result,coverage_revision=stored['revision'],candidate_revision=candidate['revision'],
        draft=content['draft'],evidence=evidence)
    if repaired:
        result['repair_review']={k:repair_check[k] for k in ('assessment_complete','model_assessment_accepts_repair',
            'changed_node_judgments','changed_node_failures','changed_node_protocol_failures','pending_changed_nodes')}
        result['repair_review']['source_inventory_profile_revision']=inventory_refs[0]
        result['repair_review']['current_review_profile_revision']=profile
    return result


def read_repaired_review_binding(intake,principal,candidate,review,*,_trail=()):
    """Expose verified changed-node opinions without concealing context issues."""
    from .domain_intake import DomainAssetReadRequest
    from .process_review_binding import read_process_review_binding,ProcessReviewBindingRequest
    from agent_kit.python.boi_process_fidelity import assessment_targets
    from agent_kit.python.boi_process_claim_review import dependent_nodes
    if candidate['revision']['ref'] in _trail or len(_trail)>=16:raise ValueError('review_history_cycle_or_limit')
    view=read_process_coverage(intake,principal,DomainAssetReadRequest(revision=review['revision'],lane='provisional'))
    if view['candidate_revision']!=candidate['revision']:raise ValueError('review_candidate_revision_mismatch')
    content=json.loads(candidate['asset']['content_json']);history=content['repair_history']
    old_candidate=intake.read_asset(principal,DomainAssetReadRequest(revision=history['original_candidate'],lane='provisional'))
    if candidate['previous_revision']!=old_candidate['revision'] or candidate['sources']!=old_candidate['sources']:
        raise ValueError('review_repair_parent_or_source_mismatch')
    previous=read_process_review_binding(intake,principal,ProcessReviewBindingRequest(candidate_revision=old_candidate['revision'],
        review_revision=history['original_review']),_trail=(*_trail,candidate['revision']['ref']))
    if previous['status']!='bound':raise ValueError('review_previous_observation_unbound')
    old=json.loads(old_candidate['asset']['content_json'])
    old_nodes={t['target_pointer']:t['value'] for t in assessment_targets(old['draft'],include_all_terms=True)}
    new_nodes={t['target_pointer']:t['value'] for t in assessment_targets(content['draft'],include_all_terms=True)}
    mapping=history['delta']['node_pointer_map'];same={new for prior,new in mapping.items()
        if prior in old_nodes and new in new_nodes and old_nodes[prior]==new_nodes[new]}
    declared=set(history['delta']['changed_nodes'])
    if not set(new_nodes)-same<=declared:raise ValueError('review_changed_node_not_assessed')
    rr=view['repair_review'];judgments=rr['changed_node_judgments']
    usable={new for prior,new in mapping.items() if prior in previous['usable_node_pointers'] and new in same and new not in declared}
    usable.update(j['target_pointer'] for j in judgments if j['label']=='supported')
    # A supported node opinion cannot erase a separate source-meaning gap.
    domain_gaps={c['node_pointer'] for f in view['failures'] if f['unit']['kind']=='domain_meaning'
        for c in f['components']}
    usable-=domain_gaps
    blocked=dependent_nodes(content['draft'],set(new_nodes)-usable);usable-=set(blocked)
    uses_unchanged=content.get('definition_uses',[])==old.get('definition_uses',[])
    complete=rr['assessment_complete'] and uses_unchanged
    failures=[{'target_pointer':j['target_pointer'],'failure_kind':j['failure_kind'],'reason':j['reason'],'evidence':j['evidence'],
        'origin':'model_changed_node_judgment'} for j in rr['changed_node_failures']]
    failures += [{'target_pointer':'field:'+q['field_locator'],'field_locator':q['field_locator'],
        'failure_kind':'omission','reason':f['missing_meaning'],'evidence':f['unit']['evidence'],
        'origin':'model_source_coverage','unit_kind':f['unit']['kind']} for f in view['failures'] for q in f['unit']['evidence']]
    source={'assessment_complete':rr['assessment_complete'],'model_assessment_accepts_source_fidelity':rr['model_assessment_accepts_repair'],
        'usable_node_pointers':sorted(usable),'quarantined_node_pointers':blocked,'failures':failures,
        'failed_claim_pointers':[j['target_pointer'] for j in rr['changed_node_failures']],
        'review_protocol_failures':rr['changed_node_protocol_failures']+view['protocol_failures'],
        'pending_review_node_pointers':rr['pending_changed_nodes'],'pending_review_field_locators':[],
        'source_context_pending_unit_ids':view['current_reference_check']['pending_unit_ids'],
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}
    priorcheck=previous['check']
    check={'candidate_revision':candidate['revision'],'assessment_complete':complete,
        'model_assessment_accepts_definition_uses':uses_unchanged and priorcheck.get('model_assessment_accepts_definition_uses',False),
        'failed_use_pointers':priorcheck.get('failed_use_pointers',[]) if uses_unchanged else [f'/definition_uses/{i}' for i in range(len(content.get('definition_uses',[])))],
        'source_review':source}
    return {'contract_version':'boi/process-review-binding@1','candidate_revision':candidate['revision'],'review_revision':review['revision'],
        'status':'bound','reason_codes':[],'usable_node_pointers':sorted(usable),'quarantined_node_pointers':blocked,
        'check':check,'source_review':source,'execution_refs':[r['execution_ref'] for r in view['receipts']],
        'review_contract_version':'boi/process-source-meaning-alignment@2','review_execution_binding':'admitted_output_and_exact_structured_inputs',
        'historical_reading':True,'authority':'wiki_reference_check','source_fidelity':'model_opinion_only','scientific_correctness':'not_evaluated',
        'new_model_runs':0,'new_review_receipts':0,'canonical_projection_eligible':False,'whole_plan_qualified':False}
