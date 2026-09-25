"""User-readable, protected native query result without internal output IDs."""
import html
import json


def render_native_query_result(value):
    if value.get('contract_version') != 'boi/native-query-host-result@1':
        raise ValueError('NATIVE_QUERY_RESULT_VIEW_CONTRACT_INVALID')
    artifact = value.get('artifact') or {}
    result_sets = artifact.get('result_sets') or []
    displays = value.get('display_sets') or []
    if len(result_sets) != len(displays) or not result_sets:
        raise ValueError('NATIVE_QUERY_RESULT_VIEW_SCOPE_MISMATCH')
    binding = (artifact.get('source_execution') or {}).get('binding') or {}
    authority = artifact.get('candidate_authority') or {}
    source = artifact.get('source_snapshot_digest')
    if (not isinstance(source, str)
            or (binding and binding.get('source_revision') != source)
            or (not binding and authority.get('source_snapshot_digest') != source)):
        raise ValueError('NATIVE_QUERY_RESULT_VIEW_SOURCE_MISMATCH')

    def esc(item):
        if item is None:
            item = 'NULL'
        elif isinstance(item, (dict, list, tuple)):
            item = json.dumps(item, ensure_ascii=False, sort_keys=True)
        return html.escape(str(item), quote=True)

    sections = []
    for index, (result, display) in enumerate(zip(result_sets, displays), 1):
        if result.get('result_set_id') != display.get('result_set_id'):
            raise ValueError('NATIVE_QUERY_RESULT_VIEW_SET_MISMATCH')
        columns = display.get('columns') or []
        if not columns or [column['output_name'] for column in columns] != [
                item[0] for item in result.get('result_schema') or []]:
            raise ValueError('NATIVE_QUERY_RESULT_VIEW_COLUMNS_MISMATCH')
        if result.get('row_count') != len(result.get('rows') or []):
            raise ValueError('NATIVE_QUERY_RESULT_VIEW_ROWS_MISMATCH')
        headings = ''.join('<th scope="col">'+esc(column['label'])+'</th>' for column in columns)
        rows = ''.join('<tr>'+''.join('<td>'+esc(row[column['output_name']])+'</td>'
            for column in columns)+'</tr>' for row in result['rows'])
        sections.append('<section><h2>결과 집합 '+str(index)+'</h2><p>원천 '+esc(display['source_id'])
            +' · 표 '+esc(display['table'])+' · 저장 행 '+str(result['row_count'])
            +'개</p><div class="scroll"><table><thead><tr>'+headings
            +'</tr></thead><tbody>'+rows+'</tbody></table></div></section>')
    associations = artifact.get('occurrence_associations') or []
    relation = ''.join('<li>연관 쌍 '+esc(item.get('candidate_pair_count', 0))
        +'개 · 대상 저장 행 '+esc(item.get('target_occurrence_count', 0))
        +'개</li>' for item in associations)
    scope = ('원천 개정 '+esc(artifact['source_snapshot_digest'])
        +' · 최신성 '+esc(binding.get('source_freshness', 'unknown'))
        +' · 원천 권위 '+esc(binding.get('source_authority', 'unknown')))
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>보호 조회 결과와 원천 범위</title>'
        '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;'
        'padding:0 1rem;color:#1f2937}h1{font-size:1.5rem}h2{font-size:1.15rem}'
        'section{margin:2rem 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #d1d5db;padding:.4rem .6rem;text-align:left;white-space:nowrap}'
        'th{background:#f3f4f6}p.note{color:#4b5563}</style><main>'
        '<h1>보호 조회 결과와 원천 범위</h1><p class="note">현재 권한과 원천 개정을 '
        '다시 확인한 탐색 조회 결과입니다. 최신성·업무 정본성·실제 납품 사실은 이 결과만으로 '
        '입증되지 않습니다.</p><p>'+scope+'</p>'
        +''.join(sections)
        +('<section><h2>연관 발생</h2><ul>'+relation+'</ul></section>' if relation else '')
        +'</main></html>')
