"""Protected relation rows retain every occurrence and require exact key closure."""
from copy import deepcopy

from agent_kit.python.boi_ontology_query_host import (
    native_markdown_row_coverage, protected_native_rows_decision,
)


def _case():
    snapshot = 'sha256:' + 'a' * 64
    root = {'result_set_id': 'root', 'row_count': 2,
        'result_schema': [['root_supplier_id', 'string'], ['root_name', 'string']],
        'exact_grain': ['root_supplier_id', 'root_name'],
        'rows': [{'root_supplier_id': 'S-1', 'root_name': 'Supplier'},
                 {'root_supplier_id': 'S-1', 'root_name': 'Supplier'}]}
    child = {'result_set_id': 'child', 'row_count': 2,
        'result_schema': [['child_item_id', 'string'],
                          ['child_supplier_id', 'string'], ['child_name', 'string']],
        'exact_grain': ['child_item_id', 'child_supplier_id', 'child_name'],
        'rows': [{'child_item_id': 'I-1', 'child_supplier_id': 'S-1',
                  'child_name': 'Inventory'},
                 {'child_item_id': 'I-1', 'child_supplier_id': 'S-1',
                  'child_name': 'Inventory'}]}
    association = {'root_result_set_id': 'root', 'target_result_set_id': 'child',
        'relationship_ref': 'relation', 'root_occurrence_count': 2,
        'target_occurrence_count': 2, 'candidate_pair_count': 4,
        'target_candidate_counts': [2, 2], 'unmatched_root_ordinals': [],
        'identity_semantics': 'RESULT_SNAPSHOT_ORDINAL',
        'equality': 'TYPED_BINARY_EQUALITY',
        'pairs': [{'root_ordinal': left, 'target_ordinal': right}
                  for left in range(2) for right in range(2)]}
    result = {'business_query_executed': False, 'plan_ref': 'plan:1',
        'artifact': {'source_snapshot_digest': snapshot,
            'source_execution': {'binding': {'source_revision': snapshot,
                'source_freshness': 'unknown', 'source_authority': 'unknown'}},
            'result_sets': [root, child],
            'occurrence_associations': [association]},
        'execution': {'result': {'result_sets': [
            {**root, 'returned_row_count': 2, 'truncated': False},
            {**child, 'returned_row_count': 2, 'truncated': False}],
            'occurrence_associations': [association]}}}
    preparation = {'native_input': {'logical_context': [
        {'entry_id': 'supplier', 'logical_payload': {
            'name': '공급업체 기록', 'aliases': ['공급사']}},
        {'entry_id': 'inventory', 'logical_payload': {
            'name': '재고 품목 기록', 'aliases': ['자재']}}]}}
    planned_sets = [
        {'result_set_id': 'root', 'role': 'ROOT', 'object_ref': 'supplier',
         'row_limit_policy': 'FAIL_IF_EXCEEDED', 'projections': [
             {'property_ref': 'supplier:id', 'output_name': 'root_supplier_id'},
             {'property_ref': 'supplier:name', 'output_name': 'root_name'}]},
        {'result_set_id': 'child', 'role': 'CHILD', 'object_ref': 'inventory',
         'row_limit_policy': 'FAIL_IF_EXCEEDED', 'parent_link': {
             'parent_result_set_id': 'root', 'relationship_ref': 'relation',
             'parent_property_refs': ['supplier:id'],
             'child_property_refs': ['inventory:supplier_id']},
         'projections': [
             {'property_ref': 'inventory:id', 'output_name': 'child_item_id'},
             {'property_ref': 'inventory:supplier_id',
              'output_name': 'child_supplier_id'},
             {'property_ref': 'inventory:name', 'output_name': 'child_name'}]}]
    plan = {'plan_ref': 'plan:1', 'planned': {'status': 'READY',
        'semantic_plan': {'result_sets': planned_sets}}}
    evidence = [{'step': 4,
        'pointer': '/artifact/occurrence_associations/0'}]
    demand = [{'kind': 'rows',
        'quote': '공급업체와 연결된 재고 품목을 모두 알려줘'}]
    return result, preparation, plan, evidence, demand


def _render(case):
    return protected_native_rows_decision(*case)


def test_compound_relation_request_renders_complete_duplicate_rows():
    case = _case()
    rendered = _render(case)
    assert rendered is not None
    assert rendered['_deterministic_native_rows']
    assert rendered['answer'].count('| S-1 | Supplier |') == 2
    assert rendered['answer'].count('| I-1 | S-1 | Inventory |') == 2
    assert '저장 행 연결 발생 쌍: 4쌍' in rendered['answer']
    result, _, plan, _, _ = case
    coverage = native_markdown_row_coverage(rendered['answer'],
        result['artifact']['result_sets'],
        plan['planned']['semantic_plan']['result_sets'])
    assert [item['status'] for item in coverage] == ['complete', 'complete']


def test_relation_target_counts_are_per_target_and_unmatched_roots_are_explicit():
    result, preparation, plan, evidence, demand = deepcopy(_case())
    result['artifact']['result_sets'][0]['rows'].append({
        'root_supplier_id': 'S-2', 'root_name': 'Unlinked'})
    result['artifact']['result_sets'][0]['row_count'] = 3
    result['execution']['result']['result_sets'][0]['row_count'] = 3
    result['execution']['result']['result_sets'][0]['returned_row_count'] = 3
    association = result['artifact']['occurrence_associations'][0]
    association['root_occurrence_count'] = 3
    association['target_candidate_counts'] = [2, 2]
    association['unmatched_root_ordinals'] = [2]
    rendered = _render((result, preparation, plan, evidence, demand))
    assert rendered is not None
    assert '| S-2 | Unlinked |' in rendered['answer']
    assert '연결되지 않은 상위 1행' in rendered['answer']
    coverage = native_markdown_row_coverage(rendered['answer'],
        result['artifact']['result_sets'],
        plan['planned']['semantic_plan']['result_sets'])
    assert [item['status'] for item in coverage] == ['complete', 'complete']


def test_relation_renderer_rejects_missing_evidence_or_unmentioned_child():
    result, preparation, plan, evidence, demand = _case()
    assert _render((result, preparation, plan, [], demand)) is None
    assert _render((result, preparation, plan, evidence,
        [{'kind': 'rows', 'quote': '공급업체를 모두 알려줘'}])) is None


def test_relation_renderer_rejects_pair_and_key_corruption():
    for corrupt in ('missing_pair', 'wrong_key', 'wrong_count', 'truncated',
                    'at_limit'):
        result, preparation, plan, evidence, demand = deepcopy(_case())
        association = result['artifact']['occurrence_associations'][0]
        if corrupt == 'missing_pair':
            association['pairs'].pop()
            association['candidate_pair_count'] = 3
            association['target_candidate_counts'] = [2, 1]
        elif corrupt == 'wrong_key':
            for place in (result['artifact']['result_sets'][1],
                          result['execution']['result']['result_sets'][1]):
                place['rows'][1]['child_supplier_id'] = 'S-2'
        elif corrupt == 'wrong_count':
            association['target_candidate_counts'] = [1, 3]
        elif corrupt == 'truncated':
            result['execution']['result']['result_sets'][1]['truncated'] = True
        else:
            planned = plan['planned']['semantic_plan']['result_sets'][1]
            planned['row_limit_policy'] = 'TRUNCATE'
            planned['result_row_limit'] = 2
        assert _render((result, preparation, plan, evidence, demand)) is None
