from copy import deepcopy

import pytest

from agent_kit.python.boi_profile_record_query import (
    adjudicate_profile_record_layout, execute_profile_query, profile_query_prompt,
    profile_record_layout_prompt, project_profile_records, route_profile_declaration)
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


PROFILE={'contract_version':'boi/knowledge-profile@1','profile_id':'maintenance',
 'schema_ref':'maintenance@1','label':'Maintenance','description':'work orders','components':[
 {'kind':'object_type','id':'work-order','label':'Work order','description':'record','metadata_constraints':[]},
 {'kind':'predicate','id':'status','label':'Status','description':'result status',
  'subject_type':{'component_id':'work-order'},'value_kind':'text','target_type':None,'role':'status',
  'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'one',
  'allowed_operators':['eq']},
 {'kind':'predicate','id':'asset','label':'Asset','description':'asset identifier',
  'subject_type':{'component_id':'work-order'},'value_kind':'text','target_type':None,'role':'asset',
  'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'one',
  'allowed_operators':['eq']} ]}


def setup():
    records=[{'result_status':'closed','asset_id':'PUMP-07'},
             {'result_status':'monitoring','asset_id':'MFC-12'}]
    features=[{'feature_id':'f-status','label':'status','value_kinds':['text'],
      'evidence_refs':['cell:A1'],'source_path':'result_status'},
     {'feature_id':'f-asset','label':'asset','value_kinds':['text'],
      'evidence_refs':['cell:B1'],'source_path':'asset_id'}]
    route={'contract_version':'boi/profile-intake-route@1','branch':'new','domain':'maintenance',
      'status':'requires_semantic_review','selected_profile_revision':None,'proposed_profile':PROFILE,
      'extension_delta':None,'coverage':{'total':2,'mapped':2,'unresolved':0,'evidence_context':0,
        'outside_scope':0,'complete':True},'feature_dispositions':[
          {'feature_id':'f-status','disposition':'mapped','component_id':'status','evidence_refs':['cell:A1'],'reason':'x'},
          {'feature_id':'f-asset','disposition':'mapped','component_id':'asset','evidence_refs':['cell:B1'],'reason':'x'}],
      'rejected_profiles':[],'release_authority_granted':False,'canonical_projection_eligible':False,
      'semantic_truth_proven':False}
    route['route_digest']=semantic_digest(route)
    source=semantic_digest(records)
    review={'contract_version':'boi/profile-route-review@1','route_digest':route['route_digest'],
      'source_snapshot_digest':source,'decision':'accepted','reviewer_ref':'fixture-reviewer',
      'reason':'source fields and Profile roles checked'}
    return records,features,route,source,review


def test_reviewed_route_projects_and_queries_source_bound_values():
    records,features,route,source,review=setup()
    projection=project_profile_records(records=records,features=features,route=route,
      source_snapshot_digest=source,review=review)
    result=execute_profile_query(projection=projection,profile=PROFILE,plan={
      'contract_version':'boi/profile-query-plan@1','filters':[{'component_id':'status','operator':'eq','value':'monitoring'}],
      'select':['asset','status']})
    assert result['row_count']==1
    assert result['rows'][0]['values']=={'asset':'MFC-12','status':'monitoring'}
    assert result['rows'][0]['evidence_refs']['asset']==['cell:B1']


def test_review_and_source_revision_are_exact_fences():
    records,features,route,source,review=setup()
    with pytest.raises(ValueError,match='ACCEPTED_REVIEW_REQUIRED'):
        project_profile_records(records=records,features=features,route=route,
          source_snapshot_digest=source,review={**review,'route_digest':'sha256:'+'0'*64})
    changed=deepcopy(records);changed[1]['result_status']='closed'
    with pytest.raises(ValueError,match='SOURCE_SNAPSHOT_MISMATCH'):
        project_profile_records(records=changed,features=features,route=route,
          source_snapshot_digest=source,review=review)


def test_planner_sees_profile_but_not_source_records():
    prompt=profile_query_prompt(question='monitoring 상태의 자산은?',profile=PROFILE)
    assert 'monitoring 상태의 자산은?' in prompt
    assert 'result_status' not in prompt and 'MFC-12' not in prompt


def test_planner_can_be_limited_to_actually_bound_profile_components():
    prompt=profile_query_prompt(question='자산은?',profile=PROFILE,
      queryable_component_ids=['asset'])
    assert '"id": "asset"' in prompt
    assert '"id": "status"' not in prompt


def test_reuse_route_resolves_exact_selected_profile_for_new_query():
    route={'branch':'reuse','selected_profile_revision':{'ref':'r','revision_digest':'sha256:'+'a'*64}}
    available=[{'revision':route['selected_profile_revision'],'declaration':PROFILE},
               {'revision':{'ref':'other','revision_digest':'sha256:'+'b'*64},'declaration':PROFILE}]
    assert route_profile_declaration(route=route,available_profiles=available)['profile_id']=='maintenance'
    with pytest.raises(ValueError,match='SELECTED_PROFILE_UNAVAILABLE'):
        route_profile_declaration(route=route,available_profiles=[])


def test_projection_uses_exact_row_evidence_and_skips_unmapped_context_sheets():
    records,features,route,_,review=setup()
    records=[{'result_status':'closed','asset_id':'PUMP-07',
              '__source_record_locator__':'work:2',
              '__evidence_refs__':{'result_status':['cell:A1'],'asset_id':['cell:B1']}},
             {'guide_text':'do not treat as a work order'}]
    source=semantic_digest(records); review={**review,'source_snapshot_digest':source}
    projection=project_profile_records(records=records,features=features,route=route,
        source_snapshot_digest=source,review=review)
    assert len(projection['records'])==1
    assert projection['records'][0]['source_record_locator']=='work:2'
    assert projection['records'][0]['evidence_refs']=={
        'status':['cell:A1'],'asset':['cell:B1']}


def test_projection_rejects_partially_populated_selected_record():
    records,features,route,_,review=setup()
    records=[{'result_status':'closed'}]
    source=semantic_digest(records); review={**review,'source_snapshot_digest':source}
    with pytest.raises(ValueError,match='PARTIAL_MAPPED_ROW'):
        project_profile_records(records=records,features=features,route=route,
            source_snapshot_digest=source,review=review)


def test_layout_requires_complete_exact_evidence_and_review_before_header_exclusion():
    _,features,route,_,review=setup()
    records=[{'result_status':'Status','asset_id':'Asset',
      '__evidence_refs__':{'result_status':['cell:A1'],'asset_id':['cell:B1']}},
     {'result_status':'monitoring','asset_id':'MFC-12',
      '__evidence_refs__':{'result_status':['cell:A2'],'asset_id':['cell:B2']}}]
    # Feature evidence must cover every row-level citation.
    features[0]['evidence_refs']=['cell:A1','cell:A2']
    features[1]['evidence_refs']=['cell:B1','cell:B2']
    source=semantic_digest(records); review={**review,'source_snapshot_digest':source}
    observation={'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
      {'record_index':0,'role':'header','evidence_refs':['cell:A1','cell:B1'],'reason':'labels'},
      {'record_index':1,'role':'domain_record','evidence_refs':['cell:A2','cell:B2'],'reason':'instance'}]}
    layout=adjudicate_profile_record_layout(records=records,features=features,route=route,
      observation=observation)
    assert layout['requires_review'] is True
    with pytest.raises(ValueError,match='LAYOUT_ACCEPTED_REVIEW_REQUIRED'):
        project_profile_records(records=records,features=features,route=route,
          source_snapshot_digest=source,review=review,layout=layout)
    layout_review={'contract_version':'boi/profile-record-layout-review@1',
      'layout_digest':layout['layout_digest'],'source_snapshot_digest':source,
      'decision':'accepted','reviewer_ref':'layout-reviewer','reason':'header and instance checked'}
    projection=project_profile_records(records=records,features=features,route=route,
      source_snapshot_digest=source,review=review,layout=layout,layout_review=layout_review)
    assert [item['values']['asset'] for item in projection['records']]==['MFC-12']


def test_layout_prompt_contains_rows_but_does_not_silently_classify_them():
    records,features,route,_,_=setup()
    records[0]['__evidence_refs__']={'result_status':['cell:A1'],'asset_id':['cell:B1']}
    prompt=profile_record_layout_prompt(records=records,features=features,route=route)
    assert 'closed' in prompt and 'domain_record' in prompt and 'header' in prompt
    with pytest.raises(ValueError,match='COVERAGE_INCOMPLETE'):
        adjudicate_profile_record_layout(records=records,features=features,route=route,
          observation={'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
            {'record_index':0,'role':'domain_record','evidence_refs':['cell:A1'],'reason':'only one'}]})


def test_profile_scoped_text_search_ranks_candidates_without_claiming_semantic_proof():
    records,features,route,source,review=setup()
    projection=project_profile_records(records=records,features=features,route=route,
      source_snapshot_digest=source,review=review)
    result=execute_profile_query(projection=projection,profile=PROFILE,plan={
      'contract_version':'boi/profile-query-plan@1','filters':[],
      'text_search':{'query':'monitoring MFC','component_ids':['status','asset'],
        'mode':'ranked_candidates'},'select':['asset','status'],'limit':10})
    assert result['rows'][0]['values']['asset']=='MFC-12'
    assert result['rows'][0]['retrieval']['score']==1
    assert result['retrieval_candidates'] is True and result['semantic_match_verified'] is False


def test_query_rejects_profile_component_without_source_binding():
    records,features,route,source,review=setup()
    projection=project_profile_records(records=records,features=features,route=route,
      source_snapshot_digest=source,review=review)
    projection['queryable_component_ids']=['asset']
    with pytest.raises(ValueError,match='COMPONENT_UNBOUND'):
        execute_profile_query(projection=projection,profile=PROFILE,plan={
          'contract_version':'boi/profile-query-plan@1','filters':[],
          'select':['status'],'limit':10})


def test_profile_text_search_accepts_complete_bounded_domain_profile():
    from agent_kit.python.boi_profile_record_query import ProfileTextSearch
    value=ProfileTextSearch(query='gas pressure',component_ids=tuple(
        f'description_{index}' for index in range(19)))
    assert len(value.component_ids)==19


def test_profile_text_search_matches_spaced_equipment_channel_number():
    records,features,route,source,review=setup()
    records[0]['asset_id']='MFC12AFVOnePointError'
    records[1]['asset_id']='MFC13AFVOnePointError'
    source=semantic_digest(records)
    review={**review,'source_snapshot_digest':source}
    projection=project_profile_records(records=records,features=features,route=route,
      source_snapshot_digest=source,review=review)
    result=execute_profile_query(projection=projection,profile=PROFILE,plan={
      'contract_version':'boi/profile-query-plan@1','filters':[],
      'text_search':{'query':'MFC 12 error','component_ids':['asset'],
        'mode':'ranked_candidates'},'select':['asset'],'limit':10})
    assert result['rows'][0]['values']['asset']=='MFC12AFVOnePointError'
