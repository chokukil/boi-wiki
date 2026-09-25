from agent_kit.python.boi_ontology_query_host import (
    normalize_task_route, published_claim_selection_catalog,
    validate_published_claim_part_map, published_answer_contract,
)
from tests.test_published_answer_claim_scope import document_fixture


def test_frozen_request_inventory_exposes_omitted_requirement_without_inventing_answer():
    question='CoolingCurrent 식별자와 단위와 적용 조건'
    route=normalize_task_route({'mode':'explanation','request_parts':['식별자','단위','적용 조건']},question)
    journal=[{'step':0,'tool':'boi_knowledge_read','result':document_fixture(),'error':None}]
    catalog=published_claim_selection_catalog(journal,[0])
    selected=validate_published_claim_part_map({'request_parts':[
        {'question_quote':'식별자','evidence_indexes':[2]},
        {'question_quote':'단위','evidence_indexes':[3]}],'unresolved_request_quotes':[]},
        question,catalog,required_quotes=route['request_parts'])
    assert selected['missing_request_quotes']==['적용 조건']
    assert selected['unresolved_request_quotes']==['적용 조건']
    result=published_answer_contract(journal,selected)
    assert '### 적용 조건' in result['answer']
    assert '7319' in result['answer'] and 'mA' in result['answer']
    assert result['answer'].index('### 식별자')<result['answer'].index('### 확인 한계')
    assert result['_published_answer_contract']['request_part_coverage_verified'] is False


def test_final_answer_keeps_conflicts_and_blank_scope_after_reordering():
    question='CoolingCurrent 최소·최대값'
    journal=[{'step':0,'tool':'boi_knowledge_read','result':document_fixture(),'error':None}]
    selected=validate_published_claim_part_map({'request_parts':[
        {'question_quote':'최소·최대값','evidence_indexes':[4,5]}],
        'unresolved_request_quotes':['최소·최대값']},question,
        published_claim_selection_catalog(journal,[0]),required_quotes=['최소·최대값'])
    answer=published_answer_contract(journal,selected)['answer']
    assert '-20 to +20' in answer and '20에서 +20' in answer
    assert 'G8(min), H8(max)는 빈 셀이다.' in answer
    assert '원문 전체에 값이 없다' not in answer
