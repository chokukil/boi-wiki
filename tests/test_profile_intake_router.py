from copy import deepcopy
import json

import pytest

from agent_kit.python.boi_profile_intake_router import (
    available_profile_catalog_from_package_admissions,
    available_profiles_from_package_admissions,
    adjudicate_profile_candidates, adjudicate_profile_route,
    domain_admitted_profile_candidates,
    normalize_empty_profile_extension, normalize_new_profile_structure, normalize_profile_extension_delta,
    normalize_redundant_profile_extension,
    profile_candidate_prompt, routing_prompt,
    validate_or_repair_routing_observation,
    workbook_profile_records, workbook_source_features)


REV_A={'ref':'KnowledgeRevision:sha256:'+'a'*64,'revision_digest':'sha256:'+'a'*64}
REV_B={'ref':'KnowledgeRevision:sha256:'+'b'*64,'revision_digest':'sha256:'+'b'*64}


def profile(profile_id='process', extra=()):
    return {'contract_version':'boi/knowledge-profile@1','profile_id':profile_id,
        'schema_ref':profile_id+'@1','label':profile_id,'description':'test profile',
        'components':[{'kind':'object_type','id':'record','label':'Record','description':'record',
            'metadata_constraints':[]},
            {'kind':'predicate','id':'name','label':'Name','description':'name',
             'subject_type':{'component_id':'record'},'value_kind':'text','target_type':None,
             'role':'name','quantity_semantics':'not_applicable','value_semantics':'not_applicable',
             'cardinality':'one','allowed_operators':['eq']},*extra]}


def features(include_gap=False):
    result=[{'feature_id':'f-name','label':'공정','value_kinds':['text'],
        'evidence_refs':['cell:A1'],'required_for_reuse':True}]
    if include_gap:
        result.append({'feature_id':'f-purpose','label':'목적','value_kinds':['text'],
            'evidence_refs':['cell:B1'],'required_for_reuse':True})
    return result


def available(revision=REV_A):
    return {'revision':revision,'declaration':profile(),'allowed_domains':['process'],'package_ids':['process-pack']}


def disposition(feature_id, mode, component=None, evidence='cell:A1'):
    return {'feature_id':feature_id,'disposition':mode,'component_id':component,
        'evidence_refs':[evidence],'reason':'source-grounded routing observation'}


def test_reuse_requires_complete_mapped_source_coverage():
    result=adjudicate_profile_route(features=features(),available_profiles=[available()],observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]})
    assert result['status']=='ready_for_domain_authoring'
    assert result['coverage']=={'total':1,'mapped':1,'unresolved':0,'evidence_context':0,
        'outside_scope':0,'complete':True}
    assert result['release_authority_granted'] is False


def test_reuse_cannot_hide_required_gap():
    with pytest.raises(ValueError,match='REUSE_REQUIRED_FEATURE_UNCOVERED'):
        adjudicate_profile_route(features=features(True),available_profiles=[available()],observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'process',
            'selected_profile_revision':REV_A,'feature_dispositions':[
                disposition('f-name','mapped','name'),disposition('f-purpose','unresolved',evidence='cell:B1')],
            'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]})


def test_extension_preserves_base_and_adds_component_for_gap():
    added={'kind':'predicate','id':'purpose','label':'Purpose','description':'purpose',
        'subject_type':{'component_id':'record'},'value_kind':'text','target_type':None,'role':'purpose',
        'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'many',
        'allowed_operators':['eq']}
    extended=profile(extra=(added,));extended['schema_ref']='process@2'
    result=adjudicate_profile_route(features=features(True),available_profiles=[available()],observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[
            disposition('f-name','mapped','name'),disposition('f-purpose','unresolved',evidence='cell:B1')],
        'rejected_profiles':[],'proposed_profile':extended,'confidence':'high','ambiguity_notes':[]})
    assert result['status']=='requires_semantic_review'
    assert result['coverage']['unresolved']==1


def test_extension_delta_is_materialized_against_exact_pinned_base():
    added={'kind':'predicate','id':'purpose','label':'Purpose','description':'purpose',
        'subject_type':{'component_id':'record'},'value_kind':'text','target_type':None,'role':'purpose',
        'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'many',
        'allowed_operators':['eq']}
    result=adjudicate_profile_route(features=features(True),available_profiles=[available()],observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[
            disposition('f-name','mapped','name'),disposition('f-purpose','unresolved',evidence='cell:B1')],
        'rejected_profiles':[],'proposed_profile':{
            'contract_version':'boi/profile-extension-delta@1',
            'base_profile_revision':REV_A,'additive_components':[added]},
        'confidence':'high','ambiguity_notes':[]})
    assert result['branch']=='extend'
    assert result['extension_delta']['additive_components'][0]['id']=='purpose'
    assert {item['id'] for item in result['proposed_profile']['components']}=={'record','name','purpose'}
    assert result['canonical_projection_eligible'] is False

    mapped=adjudicate_profile_route(features=features(True),available_profiles=[available()],observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[
            disposition('f-name','mapped','name'),disposition('f-purpose','mapped','purpose',evidence='cell:B1')],
        'rejected_profiles':[],'proposed_profile':{
            'contract_version':'boi/profile-extension-delta@1',
            'base_profile_revision':REV_A,'additive_components':[added]},
        'confidence':'high','ambiguity_notes':[]})
    assert mapped['coverage']['unresolved']==0
    assert mapped['status']=='requires_semantic_review'

    common={**available(),'can_anchor_extension':False}
    with pytest.raises(ValueError,match='EXTENSION_ANCHOR_NOT_ALLOWED'):
        adjudicate_profile_route(features=features(True),available_profiles=[common],observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
            'selected_profile_revision':REV_A,'feature_dispositions':[
                disposition('f-name','mapped','name'),
                disposition('f-purpose','mapped','purpose',evidence='cell:B1')],
            'rejected_profiles':[],'proposed_profile':{
                'contract_version':'boi/profile-extension-delta@1',
                'base_profile_revision':REV_A,'additive_components':[added]},
            'confidence':'high','ambiguity_notes':[]})


def test_extension_delta_normalizes_structure_to_conservative_unknowns_only():
    raw={'branch':'extend','proposed_profile':{'base_profile_revision':REV_A,
        'additive_components':[{'kind':'predicate','id':'interval','label':'Interval',
            'description':'source value','subject_type':'record','value_kind':'decimal',
            'role':'source','cardinality':'one','allowed_operators':['eq']}]}}
    normalized,journal=normalize_profile_extension_delta(raw)
    proposal=normalized['proposed_profile']
    assert proposal['contract_version']=='boi/profile-extension-delta@1'
    component=proposal['additive_components'][0]
    assert component['subject_type']=={'component_id':'record'}
    assert component['quantity_semantics']=='unknown'
    assert component['value_semantics']=='unknown'
    assert journal['semantic_claims_added'] is False


def test_new_profile_normalization_does_not_turn_text_into_numeric_semantics():
    raw={'branch':'new','proposed_profile':{'profile_id':'maintenance','schema_ref':'candidate@1',
        'label':'Maintenance','description':'candidate','components':[
            {'kind':'object_type','id':'ticket','label':'Ticket','description':'ticket'},
            {'kind':'predicate','id':'status','label':'Status','description':'status',
             'subject_type':{'component_id':'ticket'},'value_kind':'text','role':'status',
             'quantity_semantics':'not_applicable','value_semantics':'absolute',
             'cardinality':'one','allowed_operators':['eq']} ]}}
    normalized,journal=normalize_new_profile_structure(raw)
    predicate=normalized['proposed_profile']['components'][1]
    assert predicate['quantity_semantics']=='not_applicable'
    assert predicate['value_semantics']=='not_applicable'
    assert journal['semantic_claims_added'] is False


def test_extension_cannot_mutate_existing_component():
    changed=profile();changed['components'][1]['role']='renamed'
    changed['components'].append({'kind':'object_type','id':'extra','label':'Extra','description':'extra','metadata_constraints':[]})
    with pytest.raises(ValueError,match='EXTENSION_MUTATES_BASE_COMPONENT'):
        adjudicate_profile_route(features=features(True),available_profiles=[available()],observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
            'selected_profile_revision':REV_A,'feature_dispositions':[
                disposition('f-name','mapped','name'),disposition('f-purpose','unresolved',evidence='cell:B1')],
            'rejected_profiles':[],'proposed_profile':changed,'confidence':'high','ambiguity_notes':[]})


def test_new_profile_requires_explicit_rejection_of_every_available_profile():
    new_profile=profile('maintenance')
    with pytest.raises(ValueError,match='NEW_REQUIRES_ALL_PROFILE_COMPARISONS'):
        adjudicate_profile_route(features=features(),available_profiles=[available(REV_A),available(REV_B)],observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'new','domain':'maintenance',
            'selected_profile_revision':None,'feature_dispositions':[disposition('f-name','unresolved')],
            'rejected_profiles':[{'revision':REV_A,'missing_feature_ids':['f-name'],'reason':'incompatible'}],
            'proposed_profile':new_profile,'confidence':'medium','ambiguity_notes':['new domain']})


def test_new_profile_is_candidate_and_never_self_activates():
    new_profile=profile('maintenance')
    candidates=[available(REV_A),available(REV_B)]
    result=adjudicate_profile_route(features=features(),available_profiles=candidates,observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'new','domain':'maintenance',
        'selected_profile_revision':None,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[
            {'revision':REV_A,'missing_feature_ids':['f-name'],'reason':'incompatible process meaning'},
            {'revision':REV_B,'missing_feature_ids':['f-name'],'reason':'incompatible process meaning'}],
        'proposed_profile':new_profile,'confidence':'medium','ambiguity_notes':['review domain ownership']})
    assert result['branch']=='new'
    assert result['status']=='requires_semantic_review'
    assert result['canonical_projection_eligible'] is False
    assert result['semantic_truth_proven'] is False


def test_new_profile_cannot_map_any_source_field_to_object_type():
    source_features=features(True)
    new_profile=profile('maintenance')
    candidates=[available(REV_A)]
    with pytest.raises(ValueError,match='NEW_FIELDS_REQUIRE_PREDICATES'):
        adjudicate_profile_route(features=source_features,available_profiles=candidates,observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'new','domain':'maintenance',
            'selected_profile_revision':None,'feature_dispositions':[
                disposition('f-name','mapped','record'),
                disposition('f-purpose','mapped','name',evidence='cell:B1')],
            'rejected_profiles':[{'revision':REV_A,'missing_feature_ids':['f-name','f-purpose'],
                'reason':'incompatible process meaning'}],
            'proposed_profile':new_profile,'confidence':'medium','ambiguity_notes':[]})


def test_workbook_features_are_neutral_column_inventory():
    records=[{'fields':[
        {'text':'param_desc','value_kind':'string','span_ref':'EvidenceSpan:sha256:'+'1'*64,
         'structural_metadata':{'sheet':'적재본','excel_column':'I'}},
        {'text':'RF ON time','value_kind':'string','span_ref':'EvidenceSpan:sha256:'+'2'*64,
         'structural_metadata':{'sheet':'적재본','excel_column':'I'}},
        {'text':'20','value_kind':'number','span_ref':'EvidenceSpan:sha256:'+'3'*64,
         'structural_metadata':{'sheet':'적재본','excel_column':'L'}}]}]
    found=workbook_source_features(records)
    assert [item.feature_id for item in found]==['workbook:적재본:I','workbook:적재본:L']
    assert found[0].label=='param_desc'
    assert found[0].value_kinds==('text',)
    assert found[1].label=='20'
    assert found[1].value_kinds==('decimal',)
    assert found[0].source_path=='workbook:적재본:I'


def test_workbook_records_keep_exact_row_evidence_and_other_sheets():
    records=[{'record_locator':'sheet:적재본:row:2','fields':[
        {'text':'S-1','span_ref':'cell-a','structural_metadata':{
            'sheet':'적재본','excel_column':'A'}},
        {'text':'RF power','span_ref':'cell-b','structural_metadata':{
            'sheet':'적재본','excel_column':'B'}}]},
        {'record_locator':'sheet:가이드:row:1','fields':[
        {'text':'설명','span_ref':'cell-c','structural_metadata':{
            'sheet':'가이드','excel_column':'A'}}]}]
    found=workbook_profile_records(records)
    assert found[0]=={'workbook:적재본:A':'S-1','workbook:적재본:B':'RF power',
        '__source_record_locator__':'sheet:적재본:row:2',
        '__evidence_refs__':{'workbook:적재본:A':['cell-a'],'workbook:적재본:B':['cell-b']},
        '__record_evidence_refs__':['cell-a','cell-b'],'__unmapped_fields__':[]}
    assert found[1]['workbook:가이드:A']=='설명'


def test_workbook_records_keep_layout_and_package_records_as_explicit_context():
    records=[{'record_locator':'/sheet/layout','fields':[{'text':'<cols/>',
      'span_ref':'layout-span','field_locator':'/sheet/layout/cols','value_kind':'xml'}]}]
    found=workbook_profile_records(records)
    assert len(found)==1 and found[0]['__source_record_locator__']=='/sheet/layout'
    assert found[0]['__record_evidence_refs__']==['layout-span']
    assert found[0]['__unmapped_fields__'][0]['value_kind']=='xml'


def test_routing_prompt_contains_all_profiles_without_filename_routing():
    prompt=routing_prompt(features=features(),available_profiles=[available()],source_scope={
        'source_digest':'sha256:'+'c'*64,'file_name':'vendor-sample.xlsx'})
    assert REV_A['ref'] in prompt
    assert 'vendor-sample.xlsx' in prompt
    assert 'filename' in prompt.lower()
    packet=json.loads(prompt.split('MATERIAL:\n',1)[1])
    schema=packet['output_schema']
    assert set(schema['properties']['branch']['enum'])=={'reuse','extend','new'}
    assert {'revision','missing_feature_ids','reason'}<=set(
        schema['$defs']['RejectedProfile']['required'])
    assert schema['$defs']['RejectedProfile']['additionalProperties'] is False


def test_package_admissions_replace_namespace_heuristics_and_keep_reference_non_anchor():
    process_asset={'revision':REV_A,'namespace':'process-ns','declaration':profile('process')}
    reference_asset={'revision':REV_B,'namespace':'common-ns','declaration':profile('quantity')}
    packages=[{'id':'common','dependencies':[],'dependency_versions':{},
        'profile_admissions':[{'namespace':'common-ns','profile_id':'quantity','role':'reference',
            'can_anchor_extension':False}]},
        {'id':'process','dependencies':['common'],'dependency_versions':{},
         'profile_admissions':[{'namespace':'process-ns','profile_id':'process','role':'root',
            'can_anchor_extension':True}]}]
    available_profiles,receipt=available_profiles_from_package_admissions(
        profile_assets=[process_asset,reference_asset],package_catalog=packages,domain='process')
    found={item.declaration.profile_id:item for item in available_profiles}
    assert set(found)=={'process','quantity'}
    assert found['process'].can_anchor_extension is True
    assert found['quantity'].can_anchor_extension is False
    assert found['quantity'].allowed_domains==('process',)
    assert receipt['package_closure']==['common','process']
    assert receipt['semantic_identity_decided'] is False


def test_unlisted_profile_is_not_available_even_when_namespace_spelling_matches():
    packages=[{'id':'process','dependencies':[],'dependency_versions':{},
        'profile_admissions':[{'namespace':'process-ns','profile_id':'process','role':'root',
            'can_anchor_extension':True}]}]
    listed={'revision':REV_A,'namespace':'process-ns','declaration':profile('process')}
    unlisted={'revision':REV_B,'namespace':'process-lookalike','declaration':profile('process-copy')}
    available_profiles,_=available_profiles_from_package_admissions(
        profile_assets=[listed,unlisted],package_catalog=packages,domain='process')
    assert [item.declaration.profile_id for item in available_profiles]==['process']


def test_complete_package_catalog_unions_allowed_domains_by_exact_revision():
    common={'revision':REV_A,'namespace':'common-ns','declaration':profile('concept')}
    process={'revision':REV_B,'namespace':'process-ns','declaration':profile('process')}
    packages=[{'id':'common','dependencies':[],'dependency_versions':{},
        'profile_admissions':[{'namespace':'common-ns','profile_id':'concept','role':'reference',
            'can_anchor_extension':False}]},
        {'id':'process','dependencies':['common'],'dependency_versions':{},
         'profile_admissions':[{'namespace':'process-ns','profile_id':'process','role':'root',
            'can_anchor_extension':True}]}]
    catalog,receipt=available_profile_catalog_from_package_admissions(
        profile_assets=[common,process],package_catalog=packages)
    found={item.declaration.profile_id:item for item in catalog}
    assert found['concept'].allowed_domains==('common','process')
    assert found['concept'].can_anchor_extension is False
    assert found['process'].allowed_domains==('process',)
    assert receipt['profile_count']==2 and receipt['semantic_identity_decided'] is False


def test_routing_prompt_carries_pinned_domain_guidance():
    prompt=routing_prompt(features=features(),available_profiles=[available()],source_scope={'source':'x'},
        domain_guidance={'package_id':'process','manifest_digest':'sha256:'+'d'*64,
            'instructions':'Corrections remain evidence context.'})
    assert 'Corrections remain evidence context.' in prompt
    assert 'manifest_digest' in prompt


def test_evidence_context_is_preserved_without_blocking_reuse():
    source_features=features()+[{'feature_id':'f-correction','label':'보완내역',
        'value_kinds':['text'],'evidence_refs':['cell:C1'],'required_for_reuse':True}]
    result=adjudicate_profile_route(features=source_features,available_profiles=[available()],observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[
            disposition('f-name','mapped','name'),
            disposition('f-correction','evidence_context',evidence='cell:C1')],
        'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]})
    assert result['status']=='ready_for_domain_authoring'
    assert result['coverage']['evidence_context']==1


def test_redundant_invalid_extension_is_replaced_by_exact_selected_profile():
    raw={'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[],'proposed_profile':profile(),'confidence':'high','ambiguity_notes':[]}
    raw['proposed_profile']['components'][1]['value_semantics']='absolute'  # invalid for text
    normalized,journal=normalize_redundant_profile_extension(
        raw_observation=raw,available_profiles=[available()])
    assert normalized['branch']=='reuse' and normalized['proposed_profile'] is None
    assert journal['code']=='redundant_extension_removed'
    assert journal['semantic_changes_accepted'] is False
    observed,_=validate_or_repair_routing_observation(first_value=normalized,
        repair=lambda value,error:pytest.fail(error))
    assert observed.branch=='reuse'


def test_extension_with_new_component_is_never_normalized_away():
    added={'kind':'predicate','id':'purpose','label':'Purpose','description':'purpose',
        'subject_type':{'component_id':'record'},'value_kind':'text','target_type':None,'role':'purpose',
        'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'many',
        'allowed_operators':['eq']}
    raw={'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[],'proposed_profile':profile(extra=(added,)),
        'confidence':'high','ambiguity_notes':[]}
    normalized,journal=normalize_redundant_profile_extension(
        raw_observation=raw,available_profiles=[available()])
    assert normalized==raw and journal is None


def test_empty_extension_collapses_only_when_all_mappings_are_in_exact_base():
    raw={'contract_version':'boi/profile-routing-observation@1','branch':'extend','domain':'process',
      'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
      'rejected_profiles':[],'proposed_profile':{'contract_version':'boi/profile-extension-delta@1',
        'base_profile_revision':REV_A,'additive_components':[]},
      'confidence':'high','ambiguity_notes':[]}
    normalized,journal=normalize_empty_profile_extension(raw_observation=raw,
      available_profiles=[available()])
    assert normalized['branch']=='reuse' and normalized['proposed_profile'] is None
    assert journal['semantic_changes_accepted'] is False
    changed=deepcopy(raw);changed['feature_dispositions'][0]['component_id']='unknown'
    assert normalize_empty_profile_extension(raw_observation=changed,
      available_profiles=[available()])==(changed,None)


def test_reuse_with_invalid_exact_profile_copy_discards_the_copy_only():
    raw={'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[],'proposed_profile':profile(),'confidence':'high','ambiguity_notes':[]}
    raw['proposed_profile']['components'][1]['value_semantics']='absolute'
    normalized,journal=normalize_redundant_profile_extension(
        raw_observation=raw,available_profiles=[available()])
    assert normalized['branch']=='reuse' and normalized['proposed_profile'] is None
    assert journal['code']=='redundant_reuse_profile_copy_removed'


def test_candidate_first_pass_is_compact_and_requires_complete_catalog_coverage():
    candidates=[available(REV_A),available(REV_B)]
    prompt=profile_candidate_prompt(features=features(),available_profiles=candidates,
        source_scope={'source':'x'},domain_guidance={'package_id':'process'})
    assert REV_A['ref'] in prompt and REV_B['ref'] in prompt
    assert 'allowed_domains' in prompt and 'output_schema' in prompt
    observation={'contract_version':'boi/profile-candidate-observation@1','domain':'process',
        'dispositions':[
            {'revision':REV_A,'disposition':'selected','reason':'covers source name'},
            {'revision':REV_B,'disposition':'deferred_incompatible','reason':'different scope'}]}
    selected,receipt=adjudicate_profile_candidates(available_profiles=candidates,
        observation=observation)
    assert [item.revision.ref for item in selected]==[REV_A['ref']]
    assert receipt['full_catalog_compared'] is True
    with pytest.raises(ValueError,match='CATALOG_COVERAGE_INCOMPLETE'):
        adjudicate_profile_candidates(available_profiles=candidates,
            observation={**observation,'dispositions':observation['dispositions'][:1]})


def test_domain_admission_fallback_is_complete_but_never_decides_identity():
    process=available(REV_A)
    other={**available(REV_B),'allowed_domains':['svid']}
    observation,selected,receipt=domain_admitted_profile_candidates(
        available_profiles=[process,other],domain='process')
    assert len(observation.dispositions)==2
    assert [item.revision.ref for item in selected]==[REV_A['ref']]
    assert observation.dispositions[0].disposition=='deferred_insufficient_summary'
    assert observation.dispositions[1].disposition=='deferred_incompatible'
    assert receipt['full_catalog_compared'] is True
    assert receipt['semantic_identity_decided'] is False


def test_native_query_projection_is_rejected_at_source_intake_profile_boundary():
    native={'contract_version':'boi/native-profile-projection@2',
        'definition_review_revision':REV_A,'definition_revisions':[REV_A],
        'catalog_snapshot_digest':'sha256:'+'c'*64,'schema_digest':'sha256:'+'d'*64,
        'entries':[{'entry_id':'query:route','category':'query','definition_revision':REV_A,
            'definition_pointer':'/query','payload_json':'{"query_spec_id":"query:route"}',
            'physical':None,'source_revision':None}],
        'semantic_equivalence_proven':False,'execution_authority_granted':False}
    with pytest.raises(ValueError):
        adjudicate_profile_route(features=features(),available_profiles=[{
            'revision':REV_A,'declaration':native,'allowed_domains':['dexa'],
            'package_ids':['dexa']}],observation={
            'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'dexa',
            'selected_profile_revision':REV_A,
            'feature_dispositions':[disposition('f-name','mapped','query:route')],
            'rejected_profiles':[],'proposed_profile':None,'confidence':'high',
            'ambiguity_notes':[]})


def test_nested_revision_object_is_repaired_not_accepted_as_route():
    valid={'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'process',
        'selected_profile_revision':REV_A,'feature_dispositions':[disposition('f-name','mapped','name')],
        'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]}
    calls=[]
    observed,errors=validate_or_repair_routing_observation(first_value=REV_A,
        repair=lambda value,error:(calls.append((value,error)) or valid))
    assert observed.branch=='reuse'
    assert len(errors)==1 and len(calls)==1


def test_invalid_route_stays_failed_after_bounded_repair():
    with pytest.raises(ValueError,match='PROFILE_ROUTE_OBSERVATION_INVALID'):
        validate_or_repair_routing_observation(first_value=REV_A,
            repair=lambda value,error:{'still':'invalid'})
