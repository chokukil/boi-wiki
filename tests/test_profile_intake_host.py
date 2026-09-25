import json
import stat
import pytest

from agent_kit.python.boi_profile_intake_host import (
    complete_profile_layout, complete_profile_route, execute_profile_question,
    correct_profile_layout,
    prepare_profile_intake, prepare_profile_layout,
    prepare_profile_relation_authoring,
    prepare_profile_question, prepare_profile_question_recovery,
    render_profile_question, resume_profile_workflow, run_profile_workflow,
    select_profile_candidates)
from agent_kit.python.boi_business_profile import extend_business_profile
from agent_kit.python.boi_profile_intake_router import adjudicate_profile_route
from agent_kit.python.boi_profile_mcp_intake import (
    intake_workbook_profile_session, resume_workbook_profile_request,
    revise_workbook_profile_request, run_workbook_profile_request)
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


REV={'ref':'KnowledgeRevision:sha256:'+'a'*64,'revision_digest':'sha256:'+'a'*64}
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








PROFILE_CORRECTION={'expected_policy_revision':{
  'ref':'KnowledgeSpacePolicy:sha256:'+'d'*64,'revision_digest':'sha256:'+'d'*64},
  'reason':'Add source-bound business relations.',
  'source_difference':'Keep the source rows and add only typed source-local relations.'}








def workbook_records():
    rows=[('status','asset'),('closed','PUMP-07'),('monitoring','MFC-12')]
    return [{'record_locator':f'sheet:Work:row:{index}','fields':[
        {'text':status,'value_kind':'string','span_ref':f'cell:A{index}',
         'structural_metadata':{'sheet':'Work','excel_column':'A'}},
        {'text':asset,'value_kind':'string','span_ref':f'cell:B{index}',
         'structural_metadata':{'sheet':'Work','excel_column':'B'}}]}
        for index,(status,asset) in enumerate(rows,1)]


def test_mcp_sourced_profile_intake_reuse_reaches_fresh_nl_query():
    material={'profiles':[{'revision':REV,'declaration':PROFILE,'allowed_domains':['maintenance'],
        'package_ids':['maintenance'],'can_anchor_extension':True}],
        'admission':{'contract_version':'boi/profile-package-catalog@1',
            'semantic_identity_decided':False,'release_authority_granted':False},
        'profile_catalog_scope_status':'complete'}
    prepared=prepare_profile_intake(preserved_workbook_records=workbook_records(),
        profile_material=material,source_scope={'artifact_ref':'source:one'})
    assert 'MFC-12' not in prepared['candidate_prompt']
    candidate=select_profile_candidates(preparation=prepared,observation={
        'contract_version':'boi/profile-candidate-observation@1','domain':'maintenance',
        'dispositions':[{'revision':REV,'disposition':'selected',
            'reason':'full Profile content must be compared with the two source roles'}]})
    route=complete_profile_route(candidate_stage=candidate,observation={
        'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'maintenance',
        'selected_profile_revision':REV,'feature_dispositions':[
            {'feature_id':'workbook:Work:A','disposition':'mapped','component_id':'status',
             'evidence_refs':['cell:A1'],'reason':'source column has the reviewed status role'},
            {'feature_id':'workbook:Work:B','disposition':'mapped','component_id':'asset',
             'evidence_refs':['cell:B1'],'reason':'source column has the reviewed asset role'}],
        'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]})
    layout_preparation=prepare_profile_layout(session=route)
    layout=complete_profile_layout(preparation=layout_preparation,observation={
      'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
        {'record_index':0,'role':'header','evidence_refs':['cell:A1','cell:B1'],
         'reason':'values label the two mapped columns'},
        {'record_index':1,'role':'domain_record','evidence_refs':['cell:A2','cell:B2'],
         'reason':'complete work-order instance'},
        {'record_index':2,'role':'domain_record','evidence_refs':['cell:A3','cell:B3'],
         'reason':'complete work-order instance'}]})
    source=layout['source_snapshot_digest']
    layout_review={'contract_version':'boi/profile-record-layout-review@1',
      'layout_digest':layout['layout']['layout_digest'],'source_snapshot_digest':source,
      'decision':'accepted','reviewer_ref':'source-owner',
      'reason':'the first workbook row is the supplied column header'}
    question=prepare_profile_question(session=layout,question='monitoring 상태인 자산은?',
      layout_review=layout_review)
    assert 'MFC-12' not in question['query_prompt']
    answer=execute_profile_question(preparation=question,plan={
        'contract_version':'boi/profile-query-plan@1',
        'filters':[{'component_id':'status','operator':'eq','value':'monitoring'}],
        'select':['asset','status'],'limit':50})
    assert answer['result']['row_count']==1
    assert answer['result']['rows'][0]['values']=={'asset':'MFC-12','status':'monitoring'}
    assert answer['result']['rows'][0]['evidence_refs']=={
        'asset':['cell:B3'],'status':['cell:A3']}
    assert answer['planner_saw_source_records'] is False
    display=render_profile_question(preparation=question,execution=answer,
      source_name='maintenance.xlsx')
    assert '- Asset: MFC-12' in display['answer']
    assert 'maintenance.xlsx · sheet:Work:row:3' in display['answer']
    changed=__import__('copy').deepcopy(answer)
    changed['result']['rows'][0]['values']['asset']=''
    changed.pop('execution_digest')
    changed['execution_digest']=semantic_digest(changed)
    missing=render_profile_question(preparation=question,execution=changed,
      source_name='maintenance.xlsx')
    assert '- Asset: 원문에 값이 기록되어 있지 않습니다.' in missing['answer']
    zero=__import__('copy').deepcopy(answer)
    zero['result']['row_count']=0;zero['result']['rows']=[]
    zero.pop('execution_digest');zero['execution_digest']=semantic_digest(zero)
    recovery=prepare_profile_question_recovery(preparation=question,execution=zero)
    assert recovery['records_exposed'] is False
    assert 'MFC-12' not in recovery['recovery_prompt']
    assert '"row_count": 0' in recovery['recovery_prompt']


def test_intake_session_fences_source_and_route_mutation():
    material={'profiles':[{'revision':REV,'declaration':PROFILE,'allowed_domains':['maintenance'],
        'package_ids':['maintenance'],'can_anchor_extension':True}],
        'admission':{'semantic_identity_decided':False,'release_authority_granted':False},
        'profile_catalog_scope_status':'complete'}
    prepared=prepare_profile_intake(preserved_workbook_records=workbook_records(),
        profile_material=material,source_scope={'artifact_ref':'source:one'})
    prepared['records'][1]['workbook:Work:A']='changed'
    with pytest.raises(ValueError,match='PREPARATION_CHANGED'):
        select_profile_candidates(preparation=prepared,observation={})


@pytest.mark.asyncio
async def test_workbook_mcp_and_profile_catalog_form_one_bound_session(tmp_path, monkeypatch):
    source_records=workbook_records()
    async def fake_intake(client,*,path,namespace,output_dir):
        output_dir.mkdir(parents=True,exist_ok=True)
        (output_dir/'source-records.json').write_text(__import__('json').dumps(source_records))
        return {'source':{'artifact_ref':'Artifact:one','digest':'sha256:'+'c'*64},
          'source_index_revision':{'ref':'KnowledgeRevision:index','revision_digest':'sha256:'+'d'*64},
          'file_name':'input.xlsx','record_count':3,'field_count':6,
          'source_preserved':True,'domain_interpretation_complete':False,'model_calls':0}
    import agent_kit.python.boi_profile_mcp_intake as profile_mcp_module
    monkeypatch.setattr(profile_mcp_module,'intake_workbook',fake_intake)
    class Client:
        async def profile_intake_material(self,domain=None):
            assert domain=='maintenance'
            return {'profiles':[{'revision':REV,'declaration':PROFILE,
              'allowed_domains':['maintenance'],'package_ids':['maintenance'],
              'can_anchor_extension':True}],
              'admission':{'catalog_digest':'sha256:'+'e'*64,
                'semantic_identity_decided':False,'release_authority_granted':False},
              'profile_catalog_scope_status':'complete'}
    path=tmp_path/'input.xlsx';path.write_bytes(b'fixture')
    result=await intake_workbook_profile_session(Client(),path=path,namespace='team',
      output_dir=tmp_path/'run',domain='maintenance')
    assert result['receipt']['routing_status']=='awaiting_model_observation'
    assert result['receipt']['source_snapshot_digest']==result['preparation']['source_snapshot_digest']
    assert (tmp_path/'run/profile-session-receipt.json').exists()


def workflow_material():
    return {'profiles':[{'revision':REV,'declaration':PROFILE,'allowed_domains':['maintenance'],
        'package_ids':['maintenance'],'can_anchor_extension':True}],
        'admission':{'contract_version':'boi/profile-package-catalog@1',
            'semantic_identity_decided':False,'release_authority_granted':False},
        'profile_catalog_scope_status':'complete'}


def workflow_observer(calls, *, zero_first=False):
    def observe(*, stage, prompt):
        calls.append((stage,prompt))
        if stage=='profile_candidates':
            return {'contract_version':'boi/profile-candidate-observation@1','domain':'maintenance',
                'dispositions':[{'revision':REV,'disposition':'selected',
                    'reason':'complete admitted maintenance Profile covers both source roles'}]}
        if stage=='profile_route':
            return {'contract_version':'boi/profile-routing-observation@1','branch':'reuse',
                'domain':'maintenance','selected_profile_revision':REV,'feature_dispositions':[
                    {'feature_id':'workbook:Work:A','disposition':'mapped','component_id':'status',
                     'evidence_refs':['cell:A1'],'reason':'reviewed status source role'},
                    {'feature_id':'workbook:Work:B','disposition':'mapped','component_id':'asset',
                     'evidence_refs':['cell:B1'],'reason':'reviewed asset source role'}],
                'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]}
        if stage=='record_layout':
            return {'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
                {'record_index':0,'role':'header','evidence_refs':['cell:A1','cell:B1'],'reason':'labels'},
                {'record_index':1,'role':'domain_record','evidence_refs':['cell:A2','cell:B2'],'reason':'record'},
                {'record_index':2,'role':'domain_record','evidence_refs':['cell:A3','cell:B3'],'reason':'record'}]}
        if stage=='query_plan':
            if zero_first:
                return {'contract_version':'boi/profile-query-plan@1','filters':[
                    {'component_id':'asset','operator':'eq','value':'MFC 12'}],
                    'select':['asset','status'],'limit':50}
            return {'contract_version':'boi/profile-query-plan@1','filters':[
                {'component_id':'status','operator':'eq','value':'monitoring'}],
                'select':['asset','status'],'limit':50}
        assert stage=='query_recovery'
        return {'contract_version':'boi/profile-query-plan@1','filters':[
            {'component_id':'status','operator':'eq','value':'monitoring'}],
            'select':['asset','status'],'limit':50}
    return observe


@pytest.mark.asyncio
async def test_one_workflow_call_stops_at_real_review_instead_of_inventing_approval():
    calls=[]
    result=await run_profile_workflow(preserved_workbook_records=workbook_records(),
        profile_material=workflow_material(),source_scope={'artifact_ref':'source:one'},
        observer=workflow_observer(calls),question='monitoring 상태인 자산은?',
        source_name='maintenance.xlsx')
    assert result['status']=='review_required'
    assert [item['stage'] for item in result['required_reviews']]==['layout_review']
    assert [stage for stage,_ in calls]==['profile_candidates','profile_route','record_layout']
    assert result['question_executed'] is False

    resumed_calls=[]
    def reviewer(*,stage,request):
        return {'contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':request['layout_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner','reason':'confirmed source rows'}
    resumed=await resume_profile_workflow(session=result['session'],
        observer=workflow_observer(resumed_calls),reviewer=reviewer,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx',
        prior_trace=result['trace'])
    assert resumed['status']=='answer_ready'
    assert [stage for stage,_ in resumed_calls]==['query_plan']
    assert 'maintenance.xlsx · sheet:Work:row:3' in resumed['answer']['answer']


@pytest.mark.asyncio
async def test_one_workflow_call_reaches_cited_answer_with_bound_review_and_recovery():
    calls=[]
    def reviewer(*,stage,request):
        assert stage=='layout_review'
        return {'contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':request['layout_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner',
            'reason':'confirmed the supplied header and two source records'}
    result=await run_profile_workflow(preserved_workbook_records=workbook_records(),
        profile_material=workflow_material(),source_scope={'artifact_ref':'source:one'},
        observer=workflow_observer(calls,zero_first=True),reviewer=reviewer,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx')
    assert result['status']=='answer_ready' and result['recovery_used'] is True
    assert 'Asset: MFC-12' in result['answer']['answer']
    assert 'maintenance.xlsx · sheet:Work:row:3' in result['answer']['answer']
    assert [stage for stage,_ in calls]==[
        'profile_candidates','profile_route','record_layout','query_plan','query_recovery']
    query_prompts=[prompt for stage,prompt in calls if stage in {'query_plan','query_recovery'}]
    assert all('PUMP-07' not in prompt and 'MFC-12' not in prompt for prompt in query_prompts)
    assert result['publication_authority_granted'] is False

    reused_calls=[]
    def no_second_review(**kwargs):
        raise AssertionError('bound accepted review must be reused')
    reused=await resume_profile_workflow(session=result['session'],
        observer=workflow_observer(reused_calls),reviewer=no_second_review,
        accepted_reviews=result['accepted_reviews'],question='monitoring 상태인 자산은?',
        source_name='maintenance.xlsx')
    assert reused['status']=='answer_ready'
    assert [stage for stage,_ in reused_calls]==['query_plan']


@pytest.mark.asyncio
async def test_mcp_bound_single_request_preserves_source_then_answers(tmp_path,monkeypatch):
    preparation=prepare_profile_intake(preserved_workbook_records=workbook_records(),
        profile_material=workflow_material(),source_scope={'artifact_ref':'source:one'})
    async def bound_session(client,**kwargs):
        assert kwargs['path'].name=='maintenance.xlsx'
        return {'outcome':{'source_preserved':True},'preparation':preparation,
            'receipt':{'receipt_digest':'sha256:'+'f'*64,
                'source_scope':{'source_revision_digest':'sha256:'+'1'*64,
                    'artifact_ref':'source:one','file_name':'maintenance.xlsx'}}}
    import agent_kit.python.boi_profile_mcp_intake as module
    monkeypatch.setattr(module,'intake_workbook_profile_session',bound_session)
    def reviewer(*,stage,request):
        return {'contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':request['layout_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner','reason':'confirmed rows'}
    source=tmp_path/'maintenance.xlsx';source.write_bytes(b'fixture')
    result=await run_workbook_profile_request(object(),path=source,namespace='team',
        output_dir=tmp_path/'run',observer=workflow_observer([]),reviewer=reviewer,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx',domain='maintenance')
    assert result['outcome']['source_preserved'] is True
    assert result['workflow']['status']=='answer_ready'
    assert result['receipt']['question_executed'] is True
    assert json.loads((tmp_path/'run/profile-request-result.json').read_text())==result['receipt']
    assert json.loads((tmp_path/'run/profile-workflow-state.json').read_text())==result['state']
    assert stat.S_IMODE((tmp_path/'run/profile-workflow-state.json').stat().st_mode)==0o600
    resumed_calls=[]
    def no_second_review(**kwargs):
        raise AssertionError('persisted accepted review must be reused')
    resumed=await resume_workbook_profile_request(
        state_path=tmp_path/'run/profile-workflow-state.json',output_dir=tmp_path/'resumed',
        observer=workflow_observer(resumed_calls),reviewer=no_second_review,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx')
    assert resumed['source_recaptured'] is False
    assert resumed['workflow']['status']=='answer_ready'
    assert [stage for stage,_ in resumed_calls]==['query_plan']

    corrected_records=workbook_records()
    corrected_records[2]['fields'][0]['text']='closed'
    corrected_preparation=prepare_profile_intake(preserved_workbook_records=corrected_records,
        profile_material=workflow_material(),source_scope={
            'artifact_ref':'source:two','source_revision_digest':'sha256:'+'2'*64})
    async def corrected_bound(client,**kwargs):
        return {'outcome':{'source_preserved':True},'preparation':corrected_preparation,
            'receipt':{'receipt_digest':'sha256:'+'e'*64,
                'source_scope':{'source_revision_digest':'sha256:'+'2'*64,
                    'artifact_ref':'source:two','file_name':'maintenance.xlsx'}}}
    monkeypatch.setattr(module,'intake_workbook_profile_session',corrected_bound)
    old_state_bytes=(tmp_path/'run/profile-workflow-state.json').read_bytes()
    correction={'contract_version':'boi/profile-source-correction@1',
        'previous_state_digest':result['state']['state_digest'],
        'previous_source_revision_digest':'sha256:'+'1'*64,
        'source_owner_ref':'source-owner','reason':'confirmed corrected final status'}
    stages=[]
    base=workflow_observer(stages)
    def corrected_observer(*,stage,prompt):
        if stage=='query_plan':
            stages.append((stage,prompt))
            return {'contract_version':'boi/profile-query-plan@1','filters':[
                {'component_id':'asset','operator':'eq','value':'MFC-12'}],
                'select':['asset','status'],'limit':50}
        return base(stage=stage,prompt=prompt)
    revised=await revise_workbook_profile_request(object(),
        previous_state_path=tmp_path/'run/profile-workflow-state.json',correction=correction,
        path=source,namespace='team',output_dir=tmp_path/'revised',
        observer=corrected_observer,reviewer=reviewer,
        question='MFC-12 상태는?',source_name='maintenance.xlsx',domain='maintenance')
    assert revised['source_recaptured'] is True
    assert revised['lineage']['before_source_revision_digest']=='sha256:'+'1'*64
    assert revised['lineage']['after_source_revision_digest']=='sha256:'+'2'*64
    assert 'Status: closed' in revised['workflow']['answer']['answer']
    assert (tmp_path/'run/profile-workflow-state.json').read_bytes()==old_state_bytes


@pytest.mark.asyncio
async def test_pending_layout_review_preserves_exact_accepted_route_on_resume(tmp_path,monkeypatch):
    preparation=prepare_profile_intake(preserved_workbook_records=workbook_records(),
        profile_material=workflow_material(),source_scope={'artifact_ref':'source:one'})
    async def bound_session(client,**_kwargs):
        return {'outcome':{'source_preserved':True},'preparation':preparation,
            'receipt':{'receipt_digest':'sha256:'+'f'*64,
                'source_scope':{'source_revision_digest':'sha256:'+'1'*64,
                    'artifact_ref':'source:one','file_name':'maintenance.xlsx'}}}
    import agent_kit.python.boi_profile_mcp_intake as mcp_module
    monkeypatch.setattr(mcp_module,'intake_workbook_profile_session',bound_session)
    base=workflow_observer([])
    def observer(*,stage,prompt):
        observation=base(stage=stage,prompt=prompt)
        if stage=='profile_route':observation['confidence']='medium'
        return observation
    review_calls=[]
    def partial_reviewer(*,stage,request):
        review_calls.append(stage)
        if stage=='layout_review':return None
        return {'contract_version':'boi/profile-route-review@1',
            'route_digest':request['route_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner','reason':'route confirmed'}
    source=tmp_path/'maintenance.xlsx';source.write_bytes(b'fixture')
    first=await run_workbook_profile_request(object(),path=source,namespace='team',
        output_dir=tmp_path/'first',observer=observer,reviewer=partial_reviewer,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx')
    assert first['workflow']['status']=='review_required'
    assert review_calls==['route_review','layout_review']
    assert list(first['state']['accepted_reviews'])==['route_review']
    assert [item['stage'] for item in first['workflow']['required_reviews']]==['layout_review']

    def finish_reviewer(*,stage,request):
        assert stage=='layout_review'
        return {'contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':request['layout_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner','reason':'rows confirmed'}
    resumed=await resume_workbook_profile_request(
        state_path=tmp_path/'first/profile-workflow-state.json',output_dir=tmp_path/'resumed',
        observer=workflow_observer([]),reviewer=finish_reviewer,
        question='monitoring 상태인 자산은?',source_name='maintenance.xlsx')
    assert resumed['source_recaptured'] is False
    assert resumed['workflow']['status']=='answer_ready'
    assert set(resumed['state']['accepted_reviews'])=={'route_review','layout_review'}
    assert any(item.get('stage')=='route_review' and item.get('reused') is True
               for item in resumed['workflow']['trace'])


@pytest.mark.asyncio
async def test_layout_correction_creates_new_session_and_preserves_unrelated_record():
    def reviewer(*,stage,request):
        return {'contract_version':'boi/profile-record-layout-review@1',
            'layout_digest':request['layout_digest'],
            'source_snapshot_digest':request['source_snapshot_digest'],
            'decision':'accepted','reviewer_ref':'source-owner','reason':'confirmed source row roles'}
    ready=await run_profile_workflow(preserved_workbook_records=workbook_records(),
        profile_material=workflow_material(),source_scope={'artifact_ref':'source:one'},
        observer=workflow_observer([]),reviewer=reviewer)
    assert ready['status']=='ready_for_question'
    original=ready['session']
    corrected=correct_profile_layout(session=original,correction={
        'contract_version':'boi/profile-layout-correction@1',
        'previous_layout_session_digest':original['layout_session_digest'],
        'source_snapshot_digest':original['source_snapshot_digest'],
        'reviewer_ref':'source-owner','reason':'row 3 is a note, not a work-order instance',
        'replacement_observation':{
            'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
                {'record_index':0,'role':'header','evidence_refs':['cell:A1','cell:B1'],'reason':'labels'},
                {'record_index':1,'role':'domain_record','evidence_refs':['cell:A2','cell:B2'],'reason':'record'},
                {'record_index':2,'role':'evidence_context','evidence_refs':['cell:A3','cell:B3'],
                 'reason':'source owner confirmed this row is explanatory context'}]}})
    assert original['layout']['dispositions'][2]['role']=='domain_record'
    assert corrected['layout']['dispositions'][2]['role']=='evidence_context'
    assert corrected['layout_session_digest']!=original['layout_session_digest']
    assert corrected['layout']['correction']['previous_layout_session_digest']==original['layout_session_digest']
    with pytest.raises(ValueError,match='ACCEPTED_REVIEW_BINDING_REQUIRED'):
        await resume_profile_workflow(session=corrected,observer=workflow_observer([]),
            accepted_reviews=ready['accepted_reviews'],question='closed 상태인 자산은?',
            source_name='maintenance.xlsx')

    calls=[]
    def closed_plan(*,stage,prompt):
        calls.append(stage)
        assert stage=='query_plan'
        return {'contract_version':'boi/profile-query-plan@1','filters':[
            {'component_id':'status','operator':'eq','value':'closed'}],
            'select':['asset','status'],'limit':50}
    answer=await resume_profile_workflow(session=corrected,observer=closed_plan,
        reviewer=reviewer,question='closed 상태인 자산은?',source_name='maintenance.xlsx')
    assert answer['status']=='answer_ready' and calls==['query_plan']
    assert 'Asset: PUMP-07' in answer['answer']['answer']
    assert 'MFC-12' not in answer['answer']['answer']
