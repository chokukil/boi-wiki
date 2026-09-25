"""Readable source evidence view; derives no semantic or scientific verdict."""
import html
import json
from agent_kit.python.boi_process_answer_layout import RESPONSIVE_TABLE_CSS

from boi_api.app.governed_runtime.source_envelope import byte_digest


def process_result_html(packet, *, questions=(), sources=(), answer_review_binding=None, citation_display=None):
    esc=lambda value:html.escape(str(value))
    question_names={q['id']:q['question']+
        ('\n추가 요청: '+q['response_request'] if q.get('response_request') else '')+
        ('\n요청한 본문 길이: '+str(q['max_body_characters'])+'자 이내' if q.get('max_body_characters') is not None else '')
        for q in (questions or packet.get('questions',()))}
    fields={(s['source']['digest'],f['field_locator']):f for s in sources for f in s['fields']}
    state_names={'not_evaluated':'아직 평가하지 않음','PROVISIONAL':'잠정 결과',
        'candidate':'후보 자산','legacy_unbound':'근거가 연결되지 않은 과거 자산'}
    m=packet['wiki_metadata']
    def state(key):return esc(state_names.get(m[key],m[key]))
    sections=[]
    scopes={e['number'] for e in citation_display['sources'] if e['role']=='source_scope'} if citation_display else set()
    from .process_citation_display import process_display_groups,process_display_numbers
    display_numbers=process_display_numbers(citation_display) if citation_display else {}
    citation_label=lambda n:('확인 범위 ' if n in scopes else '')+str(display_numbers.get(n,n))
    entries={e['number']:e for e in citation_display['sources']} if citation_display else {}
    claim_labels={s['pointer']:s['text'] for a in citation_display['answers'] for part in ('sentences','limitations') for s in a[part]} if citation_display else {}
    def source_target(number,pointer):
        from .process_citation_display import statement_source_anchor
        return statement_source_anchor(entries[number],pointer)
    answer_link=answer_review_binding or {}
    answer_gaps=answer_link.get('check',{}).get('unanswered_requests',[]) if answer_link.get('status')=='bound' else []
    for answer_index,answer in enumerate(packet['answer']['answers']):
        statements=[*answer['sentences'],*answer['limitations']]
        evidence=[]
        for i,statement in enumerate(statements,1):
            quotes=[];seen=set()
            for citation in statement['citations']:
                if citation['kind']=='source_scope':
                    quotes.append('<p class="muted">자료 전체를 읽은 범위에서 확인한 근거 부족입니다. '
                        '다른 자료에도 없다는 뜻은 아닙니다.</p>')
                for binding in citation['source_bindings']:
                    key=(binding['source_revision_digest'],binding['field_locator'],binding['start'],binding['end'])
                    if key in seen:continue
                    seen.add(key);field=fields.get(key[:2])
                    if field is None:continue
                    text=field['text'][binding['start']:binding['end']]
                    if byte_digest(text.encode())!=binding['quote_digest']:
                        raise ValueError('PROCESS_VIEW_QUOTATION_DIGEST_MISMATCH')
                    quotes.append('<blockquote>'+esc(text)+'</blockquote><p class="locator">원문 위치: '+
                        esc(binding['field_locator'])+' · 자료 revision '+esc(binding['source_revision_digest'])+'</p>')
            evidence.append('<article><h3>설명 '+str(i)+'</h3><p>'+esc(statement['text'])+'</p>'+
                (''.join(quotes) if quotes else '<p>세부 원문은 아래 구조화된 기록에서 확인할 수 있습니다.</p>')+'</article>')
        gap_html=''.join('<p>'+esc(g['reason'])+'</p>' for g in answer_gaps if g['question_id']==answer['question_id'])
        gap_html=('<aside data-process-answer-gaps><strong>아직 충분히 답하지 못한 부분 · 모델 검토 의견</strong>'+gap_html+'</aside>') if gap_html else ''
        if answer_link.get('status')=='bound':
            for failure in answer_link.get('check',{}).get('failures',[]):
                pointer=failure.get('target_pointer','')
                if pointer.startswith(f'/answers/{answer_index}/'):
                    label='일부 문장의 인용을 보완해야 합니다.' if failure['failure_kind']=='incomplete_citation' else '일부 설명의 원문 근거를 확인해야 합니다.'
                    gap_html+='<aside data-process-answer-citation-gap><p>'+label+'</p><details><summary>해당 설명과 검토 이유</summary><p>'+esc(failure['reason'])+'</p></details></aside>'
        for issue in answer_link.get('check',{}).get('quality_failures',[]) if answer_link.get('status')=='bound' else []:
            if issue['question_id']==answer['question_id']:
                gap_html+='<aside data-process-answer-quality-gap><p>이 답변의 설명을 보완해야 합니다.</p><details><summary>해당 위치와 이해에 미치는 영향</summary><p>'+esc(issue['reason'])+'</p><p>'+esc(issue['user_impact'])+'</p><p class="locator">'+esc(', '.join(issue['target_pointers']))+'</p></details></aside>'
        issues=[v for v in answer_link.get('protocol_issues',[]) if
            answer_link.get('status')=='bound' and v.get('target_pointer','').startswith(f'/answers/{answer_index}/')]
        if issues:
            gap_html+=('<aside data-process-answer-protocol><strong>답변 검토가 완료되지 않았습니다</strong>'
                '<p>실제 검토 실행은 확인했지만, 검토 모델이 원문 근거와 Wiki 상태를 섞어 판단했습니다. '
                '답변 전체를 수용한 결과가 아니며 원문으로 제공 가능한 내용은 계속 표시합니다.</p>'+
                ''.join('<p class="locator">대상: '+esc(v['target_pointer'])+'</p>' for v in issues)+'</aside>')
        displayed=citation_display['answers'][answer_index] if citation_display else None
        def numbered(item):
            anchor='claim-'+item['pointer'].strip('/').replace('/','-')
            return '<span id="'+anchor+'" tabindex="-1">'+esc(item['text'])+'</span>'+''.join(
                '<a class="citation" data-source-link data-claim-anchor="'+anchor+'" href="'+source_target(n,item['pointer'])+'" aria-label="출처 '+citation_label(n)+' 관련 구절 보기">['+citation_label(n)+']</a>' for n in item['source_numbers'])
        body=esc(answer['body']);limitations=''.join('<p class="muted">'+esc(s['text'])+'</p>' for s in answer['limitations'])
        if displayed:
            # Exact bound prose is preserved; numbering is presentation only.
            if ' '.join(s['text'] for s in displayed['sentences'])!=answer['body']:
                raise ValueError('PROCESS_VIEW_BODY_STATEMENTS_MISMATCH')
            body=''.join('<p>'+numbered(s)+'</p>' for s in displayed['sentences'])
            limitations=''.join('<p class="muted">'+numbered(s)+'</p>' for s in displayed['limitations'])
            if displayed.get('layout'):
                from agent_kit.python.boi_process_answer_layout import render_layout
                def resolve(pointer):
                    _,section,index=pointer.split('/')
                    return numbered(displayed[section][int(index)])
                body=render_layout(displayed['layout'],resolve,html=True,escape=esc)
                limitations=''
        sections.append('<section><h2>답변'+(f' {len(sections)+1}' if len(packet['answer']['answers'])>1 else '')+'</h2>'+
            '<div data-process-answer-body>'+body+'</div>'+gap_html+limitations+
            '<details data-process-user-request><summary>사용자 질문과 첨부 맥락 보기</summary><p style="white-space:pre-wrap">'+
            esc(question_names.get(answer['question_id'],'저장된 질문: '+answer['question_id']))+'</p></details>'+
            ('' if displayed else '<details><summary>문장별 원문과 조건 확인</summary>'+''.join(evidence)+'</details>')+'</section>')
    if citation_display:
        cards=[]
        for entry in citation_display['sources']:
            number=str(entry['number']);source=entry['source']
            if entry['field_locator'] is None:
                original='\n\n'.join(f['field_locator']+'\n'+fields[(source['digest'],f['field_locator'])]['text']
                    for f in entry['citation_reference']['field_inventory'])
            else:original='\n\n'.join(locator+'\n'+fields[(source['digest'],locator)]['text'] for locator in entry.get('field_locators',[entry['field_locator']]))
            from .process_citation_display import visible_quote_indices
            visible=visible_quote_indices(entry)
            def quoted(i,q):return '<p class="locator">원문 항목: '+esc(q['binding']['field_locator'])+'</p><blockquote tabindex="-1" id="source-'+number+'-quote-'+str(i)+'">'+esc(q['text'])+'</blockquote>'
            quotes=''.join(quoted(i,q) for i,q in enumerate(entry['quotes']) if i in visible)
            extra=''.join(quoted(i,q) for i,q in enumerate(entry['quotes']) if i not in visible)
            if extra:quotes+='<details data-source-graph-quotes><summary>정의 연결에 사용한 추가 원문 구절</summary>'+extra+'</details>'
            pointers=list(dict.fromkeys([*entry.get('statement_pointers',[]),
                *(p for q in entry['quotes'] for p in q['statement_pointers'])]))
            returns=['<p><a data-answer-return href="#claim-'+p.strip('/').replace('/','-')+'">답변으로 돌아가기: '+
                esc(claim_labels.get(p,'해당 설명')[:55])+('…' if len(claim_labels.get(p,''))>55 else '')+'</a></p>' for p in pointers]
            back=returns[0] if returns else ''
            if len(returns)>1:
                back+='<details data-other-answer-returns><summary>이 출처를 사용하는 다른 설명</summary>'+''.join(returns[1:])+'</details>'
            cards.append('<section data-source-reference id="source-'+number+'" tabindex="-1">'+quotes+
                ('<p>'+esc(entry['scope_note'])+'</p>' if entry['scope_note'] else '')+
                '<details data-source-context><summary>원문 항목 전체 보기</summary><blockquote>'+esc(original)+
                '</blockquote><details><summary>정확한 revision·역할·EvidenceSpan 참조</summary><pre>'+esc(json.dumps(entry,ensure_ascii=False,indent=2))+
                '</pre></details></details>'+back+'</section>')
        grouped=[]
        for card in process_display_groups(citation_display):
            entry=citation_display['sources'][card['reference_indices'][0]]
            grouped.append('<article data-source-card><h3>['+str(card['number'])+'] '+esc(entry['title'])+'</h3>'
                '<p data-source-type>'+esc(entry['source_type'])+'</p>'+''.join(cards[i] for i in card['reference_indices'])+'</article>')
        sections.append('<section data-process-sources><h2>답변의 출처</h2>'+''.join(grouped)+'</section>')
    unresolved=packet.get('unresolved_use_pointers',[])
    result='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>공정 자료 활용 결과</title><style>
body{font:17px/1.75 system-ui,sans-serif;color:#18303a;max-width:960px;margin:32px auto;padding:0 24px;overflow-wrap:anywhere}
h1{font-size:30px}h2{font-size:21px}h3{font-size:17px}header{background:#edf4f8;padding:16px 20px;border-radius:8px}
section{padding:20px 0;border-bottom:1px solid #dce4e7}.muted{color:#526875}.locator{font-size:12px;overflow-wrap:anywhere;color:#526875}
aside[data-process-answer-gaps]{background:#fff6e0;padding:12px 16px;border-left:3px solid #c99a39}aside p{margin:8px 0}
summary{cursor:pointer;color:#185770;padding:8px 0}summary:focus-visible{outline:2px solid #185770}
.citation{font-size:14px;padding:8px 5px;display:inline-block}a:focus-visible,[tabindex="-1"]:focus{outline:2px solid #185770;outline-offset:3px}
[data-source-card]{scroll-margin-top:16px;padding:12px 0}[data-source-card]:target{background:#edf4f8}
blockquote{margin:12px 0;padding:10px 16px;background:#f4f7f8;border-left:3px solid #82a5b4;white-space:pre-wrap}
article{border-top:1px solid #dce4e7}pre{font:12px/1.6 monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f8;padding:16px}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:16px}th,td{text-align:left;vertical-align:top;border:1px solid #dce4e7;padding:10px}th{background:#edf4f8}
.citation{white-space:nowrap}table th:first-child,table td:first-child{min-width:3rem}
''' + RESPONSIVE_TABLE_CSS + '''

</style><h1>공정 자료 활용 결과</h1>'''
    inspection=('<p data-process-authority>'+state('authority')+' · '+state('display_status')+'</p>')
    inspection+=('<p>원문 충실성: '+state('source_fidelity')+'<br>도메인 검증: '+state('domain_verdict')+'</p>')
    binding=packet.get('review_binding',{})
    if binding.get('status') in ('bound','partially_bound'):
        inspection+='<p data-review-binding>저장된 검토와 실제 실행의 입력·출력 연결을 확인했습니다. 의미 정확성이나 과학적 진위를 증명한 것은 아닙니다.</p>'
    else:
        inspection+='<p data-review-binding>추출 검토의 실행 연결을 확인하지 못했습니다. 확인되지 않은 의미 자산의 인용은 보류하며, 직접 원문으로 제공할 수 있는 내용은 계속 표시합니다.</p>'
    if packet.get('withheld_statements'):
        result+='<p data-withheld-statements>검토 연결이나 의존 근거를 확인해야 하는 설명 '+str(len(packet['withheld_statements']))+'건을 보류했습니다. 이전 답변과 원문은 저장된 revision에 보존되어 있습니다.</p>'
    if unresolved:
        inspection+=('<p>정의 연결 '+str(len(unresolved))+'건은 검토 후에도 해결되지 않았습니다. '
            '원문으로 직접 설명할 수 있는 내용과 함께, 아래 기록에서 미해결 연결을 확인할 수 있습니다.</p>')
    failures=packet.get('source_review_failures',[])
    if failures:
        inspection+=('<details><summary>추출 검토의 미해결 항목 '+str(len(failures))+'건</summary>'+
            '<p>외부 모델 검토에서 남은 항목입니다. 원문 자체의 과학적 오류 판정과는 구분합니다.</p>'+
            ''.join('<article><p>'+esc(f['reason'])+'</p><p class="locator">대상: '+esc(f['target_pointer'])+
                '</p></article>' for f in failures)+'</details>')
    protocol_failures=packet.get('source_review_protocol_failures',[])
    if protocol_failures:
        inspection+=('<details><summary>검토 기록 확인 필요 '+str(len(protocol_failures))+'건</summary>'+
            '<p>검토 형식이나 인용 확인이 끝나지 않은 항목입니다. 원문이나 공정 설명이 틀렸다는 판정은 아닙니다. '
            '확인된 다른 부분은 계속 활용할 수 있습니다.</p>'+
            ''.join('<p class="locator">대상: '+esc(f.get('target_pointer') or f.get('field_locator') or '검토 기록')+
                ' · '+esc(f['reason_code'])+'</p>' for f in protocol_failures)+'</details>')
    response_review=packet.get('response_review')
    if response_review:
        answer_link=answer_review_binding or {}
        inspection+=('<p data-answer-review-binding>답변 검토의 실제 실행 연결: '+
            ('확인됨. 저장된 모델 의견과 해당 입력·출력이 일치합니다.' if answer_link.get('status')=='bound' else
             '확인되지 않음. 아래 저장 의견을 실행이 확인된 검증 결과로 해석하지 마세요.')+'</p>')
        recovery=answer_link.get('output_integrity_recovery')
        if answer_link.get('status')=='bound' and recovery:
            inspection+='<p data-output-byte-recovery>원본 출력 바이트를 추가로 보존하여 과거 줄바꿈 변환을 확인했습니다. 기존 답변·모델 의견·receipt는 재작성하지 않았습니다. 원본 출력: <code>'+esc(recovery['source']['artifact_ref'])+'</code></p>'
        last=response_review['attempts'][-1]['check']
        label='답변 수용 의견' if last.get('model_assessment_accepts_answers') else '미해결 의견 있음'
        inspection+='<details><summary>저장된 답변 검토 의견: '+esc(label)+'</summary><p>자산에 기록된 외부 모델의 의견입니다. Wiki 검증 상태와 구분하며, 이 화면은 모델 실행이나 과학적 진위를 새로 검증하지 않습니다. 최초 답변과 수정 이력은 함께 보존됩니다.</p>'
        for failure in last.get('failures',[]):
            inspection+='<p>'+esc(failure['reason'])+'</p>'
        for missing in last.get('unanswered_requests',[]):
            inspection+='<p>'+esc(missing['reason'])+'</p>'
        if last.get('diagnostic'):inspection+='<p>검토 출력의 무결성을 확인하지 못했습니다.</p>'
        inspection+='</details>'
    result+=''.join(sections)+'<details data-process-review-summary><summary>검토 상태와 범위</summary>'+inspection+'</details><details><summary>Wiki 자산·검토 기록과 구조화된 근거</summary><pre>'+esc(
        json.dumps({'wiki_metadata':m,'unresolved_use_pointers':unresolved,'answer':packet['answer']},ensure_ascii=False,indent=2))+'</pre></details></html>'
    return result


def process_result_page(view):
    """Product route uses the server-validated shared service projection."""
    esc=lambda value:html.escape(str(value))
    content=process_result_html(view['packet'],sources=view['sources'],answer_review_binding=view.get('answer_review_binding'),citation_display=view.get('citation_display'))
    records='<details data-process-result-history><summary>수정 이력과 읽기 기록</summary>'
    records+='<p class="locator">답변 revision '+esc(view['stored_answer_revision']['revision_digest'])+'</p>'
    for item in view.get('followup_history',[]):
        records+='<p><a href="'+esc(item['ui_url'])+'">개선 요청의 이전 답변 보기</a></p>'
    if view['history']:
        records+='<ul>'+''.join('<li><a href="'+esc(item['ui_url'])+'">이전 답변: '+
            esc(item['revision']['revision_digest'])+'</a></li>' for item in view['history'])+'</ul>'
    elif view.get('history_status')=='unavailable':records+='<p>이전 이력을 지금 확인할 수 없습니다. 현재 확인된 답변과 근거는 계속 표시합니다.</p>'
    else:records+='<p>이 답변의 이전 revision은 없습니다.</p>'
    if view.get('meaning_history'):
        records+='<div data-process-meaning-history><h3>사용한 공정 지식의 수정 이력</h3>'
        labels={'retracted':'공정의 구조화된 주장 철회','added':'추가','changed':'내용 변경','pointer_moved':'참조 위치 이동'}
        for item in view['meaning_history']:
            records+='<p class="locator">이전 지식 revision '+esc(item['previous_revision']['revision_digest'])+'</p>'
            records+='<p>'+('원문 revision이 변경되었습니다.' if item['source_revision_changed'] else '원문 revision을 보존했습니다.')+'</p><ul>'
            for change in item['changes']:
                node=change['current_value'] or change['previous_value'] or {}
                records+='<li>'+esc(labels.get(change['operation'],change['operation']))+': '+esc(node.get('statement',node.get('label',change['node_id'])))+'</li>'
            records+='</ul>'
            if item.get('unchanged_candidate_notes'):
                records+='<p>후보의 다음 메모는 그대로 보존되어 있습니다. Wiki가 검증한 사실을 뜻하지 않습니다.</p><ul>'
                for note in item['unchanged_candidate_notes']:
                    records+='<li>'+esc(note['text'])+' <span class="locator">'+esc(note['pointer'])+'</span></li>'
                records+='</ul>'
            records+='<details><summary>과거 검토 의견과 정확한 참조 대응</summary><p>과거 모델 의견과 저장된 변경 기록입니다. 현재의 새 과학 검증 결과가 아닙니다.</p><pre>'+esc(json.dumps(item,ensure_ascii=False,indent=2))+'</pre></details>'
        records+='</div>'
    if view.get('meaning_history_status')=='unavailable':
        records+='<p>공정 지식의 이전 이력 일부를 지금 확인할 수 없습니다. 현재 유효한 답변과 근거는 계속 표시합니다.</p>'
    records+='<details><summary>Wiki 원문·정의·검토 읽기 receipt '+str(len(view['receipts']))+'건</summary>'
    records+='<p>당시 발급된 기록을 조회했습니다. 아래 reading_ref가 읽기 receipt입니다. 화면 주소와 자산 revision은 receipt 자체가 아닙니다. 새 검토나 과학적 검증을 수행한 것은 아닙니다.</p>'
    for receipt in view['receipts']:
        records+='<pre>'+esc(json.dumps(receipt,ensure_ascii=False,indent=2))+'</pre>'
    records+='</details></details>'
    return content.replace('<h1>공정 자료 활용 결과</h1>',
        '<nav aria-label="서비스">BoI Wiki · 저장된 공정 자료 활용</nav><main data-process-result><h1>공정 자료 활용 결과</h1>',1).replace(
        '</html>',records+'</main>'+PROCESS_RETURN_SCRIPT+'</html>')


PROCESS_RETURN_SCRIPT = """<script type="module">
let origin = null;
document.addEventListener('click', event => {
  const citation = event.target.closest('[data-source-link]');
  if (citation) {
    const target = document.getElementById(citation.hash.slice(1));
    const card = target?.closest('[data-source-card]');
    const claim = document.getElementById(citation.dataset.claimAnchor);
    if (!card || !claim) return;
    origin = {claim, y: scrollY};
    document.querySelectorAll('[data-current-answer-return]').forEach(node => node.remove());
    const back = document.createElement('a');
    back.href = '#' + claim.id;
    back.dataset.currentAnswerReturn = '';
    back.textContent = '읽던 답변으로 돌아가기';
    card.prepend(back);
  }
  const back = event.target.closest('[data-current-answer-return]');
  if (back && origin) {
    event.preventDefault();
    history.pushState(null, '', '#' + origin.claim.id);
    origin.claim.focus({preventScroll: true});
    scrollTo(0, origin.y);
  }
});
</script>"""

def process_result_csp():
    import base64
    import hashlib
    script = PROCESS_RETURN_SCRIPT.split('>', 1)[1].rsplit('</script>', 1)[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return "default-src 'none'; script-src 'sha256-" + digest + "'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
