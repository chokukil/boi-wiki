"""A product page for actual coverage failures, unresolved references and sources."""
from html import escape


def process_coverage_page(view):
    esc=lambda x:escape(str(x),quote=True)
    cards=[]
    for item in view['failures']:
        source=''.join('<p><code>'+esc(s['field_locator'])+'</code></p><blockquote>'+esc(s['quoted_anchor'])+'</blockquote>'
            '<details><summary>조건·이유를 포함한 원문 전체 문맥</summary><p>'+esc(s['full_field_context'])+'</p><code>'+esc(s['field_span_ref'])+'</code></details>' for s in item['source_fields'])
        components=''.join('<li>'+esc(c['value'])+'<br><code>'+esc(c['pointer'])+'</code></li>' for c in item['components'])
        cards.append('<article data-coverage-failure><p><strong>'+esc(', '.join(item.get('process_names',[])))+'</strong></p><h2>'+esc(item['missing_meaning'])+'</h2><p>'+esc(item['reason'])+'</p>'
            +source+'<details><summary>저장된 설명과 정확한 검토 위치</summary><ul>'+components+'</ul><p>검토 자산의 content_json → <code>'
            +esc(item['stored_location']['content_json_pointer'])+'</code></p><code>'+esc(view['alignment_revision']['ref'])+'</code></details></article>')
    pending='<aside data-coverage-pending><strong>참조 검토 미완료 '+str(view['pending_count'])+'건</strong><details><summary>미완료 항목과 이유 보기</summary><p>설명 누락과 별개로, 이 항목들은 참조 위치가 검토 계약과 맞지 않아 판정을 확정하지 못했습니다.</p><p>'+esc(', '.join(view['pending_unit_ids']))+'</p></details></aside>' if view['pending_count'] else ''
    if 'current_reference_check' in view:
        current=view['current_reference_check']
        pending='<aside data-coverage-pending><strong>현재 참조 연결 미확인 '+str(len(current['pending_unit_ids']))+'건 · 과거 참조 실패 '+str(view['pending_count'])+'건</strong><details><summary>참조 계약 변경과 보존된 실패</summary><p>새 참조 역할 검사로 원문 위치 '+str(len(current['resolved_context_references']))+'건의 연결을 확인했습니다. 과거 검토 결과는 변경하지 않았습니다. 원문에 남아 있다는 확인이며, 후보에 의미가 충분히 반영됐거나 분류가 옳다는 판정은 아닙니다.</p><code>'+esc(current['contract_version'])+'</code><p>과거 미완료: '+esc(', '.join(view['pending_unit_ids']))+'</p><p>현재 미확인: '+esc(', '.join(current['pending_unit_ids']))+'</p></details></aside>'
    receipts=''.join('<li>실행 <code>'+esc(x['execution_ref']['ref'])+'</code><br>읽기 <code>'+esc(x['reading_ref']['ref'])+'</code></li>' for x in view['receipts'])
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>공정 설명의 원문 반영 검토</title><style>body{font:16px/1.7 system-ui,sans-serif;color:#183044;background:#f4f7fa;margin:0}main{max-width:900px;margin:auto;padding:24px}article,aside{background:white;padding:22px;margin:20px 0;border:1px solid #ccd7df;border-radius:12px}aside{border-left:5px solid #ab6711}h1{font-size:28px}h2{font-size:20px}h1,h2{word-break:keep-all;overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}blockquote{border-left:3px solid #678797;padding-left:16px;margin-left:0}summary{cursor:pointer}p,li{overflow-wrap:anywhere}</style><main><a href="/">BoI Wiki</a><h1>공정 설명의 원문 반영 검토</h1><p>원문 의미 '+str(view['unit_count'])+'건 중 참조가 유효한 판정 '+str(view['valid_unit_count'])+'건 · 설명 누락 '+str(view['failure_count'])+'건</p><p>PROVISIONAL · 원문 충실성에 대한 모델 의견입니다. 과학적 진위는 검증하지 않았습니다.</p>'+pending+''.join(cards)+'<details><summary>저장 revision과 실제 receipt</summary><p>후보 <code>'+esc(view['candidate_revision']['ref'])+'</code></p><p>검토 <code>'+esc(view['alignment_revision']['ref'])+'</code></p><ul>'+receipts+'</ul><p>기존 실행과 읽기 기록을 조회했습니다. 이 화면을 열어 새 검토나 receipt를 만들지 않았습니다.</p></details></main></html>'
