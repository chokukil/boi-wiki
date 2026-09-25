from copy import deepcopy
import json

from agent_kit.python.boi_ontology_query_host import (
    PUBLISHED_CLAIM_SELECTION_SYSTEM, published_answer_contract,
    published_claim_selection_catalog, run_ontology_host,
    validate_published_claim_part_map,
)


def document_fixture():
    values=[('장비', 'REACTOR_Q'), ('항목명', 'CoolingCurrent'),
            ('식별자', '7319'), ('단위', 'mA'),
            ('영문 설명의 범위', '-20 to +20'), ('국문 설명의 범위', '20에서 +20')]
    claims=[]
    for i,(label,value) in enumerate(values):
        claims.append({'pointer':f'/assertions/{i}', 'value':{
            'id':f'claim_{i}', 'assertion_kind':'source_reported',
            'statement':label+':', 'value':{'kind':'text','value':value},
            'polarity':'positive','modality':'asserted','conditions':[],
            'exceptions':[],'applicability':[], 'valid_time':{'state':'unknown'},
            'depends_on':[], 'uncertainties':[]},
            'source_bindings':[{'field_locator':f'/sheets/Records/cells/{chr(65+i)}8'}]})
    return {'contract_version':'boi/published-document-view@1',
        'typed_meaning':True,'is_current_revision':True,'source_access_granted':False,
        'title':'CoolingCurrent 정의','claims':claims,
        'uses':[{'purpose':'explain','status':'usable_with_limits',
            'qualified_roots':[c['pointer'] for c in claims]}],
        'unresolved':[
            {'meaning_pointer':None,'description':'G8(min), H8(max)는 빈 셀이다.'},
            {'meaning_pointer':None,'description':
                '영문 -20 to +20과 국문 20에서 +20은 아래쪽 부호가 다르다. '
                '이 행만으로 운영 범위인지 알람 기준인지 확정되지 않았다.'},
        ]}


def test_default_answer_delivers_identity_values_without_free_text_reauthoring():
    doc=document_fixture()
    question='REACTOR_Q 장비의 CoolingCurrent 식별자와 단위를 알려줘'
    actions=iter([
        {'action':'call','tool':'boi_knowledge_query','arguments':{'operation':'discover',
            'request':{'set_ref':'knowledge-set:sha256:'+'a'*64,'query':'CoolingCurrent'}}},
        {'action':'call','tool':'boi_knowledge_read','arguments':{'view':'document',
            'revision':{'ref':'current','revision_digest':'sha256:'+'a'*64}}},
    ])
    model_calls=[]
    def select(system,context):
        assert system==PUBLISHED_CLAIM_SELECTION_SYSTEM
        model_calls.append(system)
        catalog=json.loads(context)['catalog']
        indexes={item.get('literal'):item['index'] for item in catalog}
        return {'request_parts':[
            {'question_quote':'식별자','evidence_indexes':[indexes['7319']]},
            {'question_quote':'단위','evidence_indexes':[indexes['mA']]}],
            'unresolved_request_quotes':[]}
    def call(tool,args):
        if tool=='boi_knowledge_set':return {'set_ref':'knowledge-set:sha256:'+'a'*64},None,None
        if tool=='boi_knowledge_read':return doc,None,None
        return {'items':[{'kind':'object_type'}]},None,None
    result=run_ontology_host(question,schemas=[],decide=lambda *_:next(actions),call=call,
        ground_decide=select,route_decide=lambda *_:{'mode':'explanation','reason':'definition'})
    assert result['final_delivery_observed'] is True, result['error']
    assert len(model_calls)==1
    assert all(value in result['answer_plain'] for value in ('REACTOR_Q','CoolingCurrent','7319','mA'))
    assert {'/claims/0/value','/claims/1/value','/claims/2/value','/claims/3/value'} <= {
        ref['pointer'] for ref in result['citations']}
    audit=result['raw']['grounded_delivery_reviews'][0]
    assert audit['contract_version']=='boi/published-answer-claim-scope@1'
    assert audit['request_part_coverage_verified'] is False


def test_blank_cells_cannot_be_rewritten_as_source_wide_absence_or_drop_conflict():
    doc=document_fixture()
    journal=[{'step':0,'tool':'boi_knowledge_read','result':doc,'error':None}]
    catalog=published_claim_selection_catalog(journal,[0])
    question='REACTOR_Q CoolingCurrent 단위와 최소·최대값을 알려줘'
    mapping={'request_parts':[
        {'question_quote':'단위','evidence_indexes':[3]},
        {'question_quote':'최소·최대값','evidence_indexes':[4,5,6]}],
        'unresolved_request_quotes':['최소·최대값']}
    assert validate_published_claim_part_map({**mapping,'answer':'원문 전체에 값이 없다'},
        question,catalog) is None
    selected=validate_published_claim_part_map(mapping,question,catalog)
    result=published_answer_contract(journal,selected)
    assert 'G8(min), H8(max)는 빈 셀이다.' in result['answer']
    assert '-20 to +20' in result['answer'] and '20에서 +20' in result['answer']
    assert '이 행만으로 운영 범위인지 알람 기준인지 확정되지 않았다.' in result['answer']
    assert '원문 전체에 값이 없다' not in result['answer']
    assert {'step':0,'pointer':'/unresolved/1'} in result['evidence']
    assert result['_published_answer_contract']['source_absence_inferred'] is False


def test_conditions_remain_attached_to_their_claim_and_dependency_notes_close():
    doc=document_fixture()
    doc['claims'][2]['value'].update(statement='첫 확인',value={'kind':'text','value':'첫 확인'},
        conditions=[{'statement':'공정 A 이후'}],depends_on=['claim_3'])
    doc['claims'][3]['value'].update(statement='둘째 확인',value={'kind':'text','value':'둘째 확인'})
    doc['unresolved']=[{'meaning_pointer':'/assertions/3',
        'description':'둘째 확인의 시점은 이 근거에서 확정되지 않았다.'}]
    journal=[{'step':0,'tool':'boi_knowledge_read','result':doc,'error':None}]
    catalog=published_claim_selection_catalog(journal,[0])
    selected=validate_published_claim_part_map({'request_parts':[
        {'question_quote':'첫 확인','evidence_indexes':[2]},
        {'question_quote':'둘째 확인','evidence_indexes':[3]}],
        'unresolved_request_quotes':[]},'첫 확인 및 둘째 확인 시점',catalog)
    result=published_answer_contract(journal,selected)
    assert result['answer'].count('조건: 공정 A 이후')==1
    assert result['answer'].index('조건: 공정 A 이후') < result['answer'].index('- 둘째 확인')
    assert '둘째 확인의 시점은 이 근거에서 확정되지 않았다.' in result['answer']
    assert {'step':0,'pointer':'/claims/3/value'} in result['evidence']
    dependency_only=deepcopy(selected)
    dependency_only['evidence']=[{'step':0,'pointer':'/claims/2/value'}]
    closed=published_answer_contract(journal,dependency_only)
    assert '둘째 확인의 시점은 이 근거에서 확정되지 않았다.' in closed['answer']
    broken=deepcopy(journal)
    broken[0]['result']['claims'][2]['value']['depends_on']=['missing']
    assert published_answer_contract(broken,selected) is None


def test_selected_raw_field_keeps_unqualified_same_field_scope_note():
    doc=document_fixture()
    doc['claims'][5]['source_bindings']=deepcopy(doc['claims'][4]['source_bindings'])
    doc['uses'][0]['qualified_roots'].remove('/assertions/5')
    doc['unresolved']=[{'meaning_pointer':'/assertions/5',
        'description':'별도 확인 사항의 시점은 미확정이다.'}]
    journal=[{'step':0,'tool':'boi_knowledge_read','result':doc,'error':None}]
    catalog=published_claim_selection_catalog(journal,[0])
    selected=validate_published_claim_part_map({'request_parts':[
        {'question_quote':'원문','evidence_indexes':[4]}],
        'unresolved_request_quotes':[]},'원문을 알려줘',catalog)
    result=published_answer_contract(journal,selected)
    assert '별도 확인 사항의 시점은 미확정이다.' in result['answer']
    assert '/claims/5/value' not in [ref['pointer'] for ref in result['evidence']]
