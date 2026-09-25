"""Escaped, read-only Wiki views of current-authorized published knowledge."""
from html import escape
import json
from urllib.parse import urlencode

from markdown_it import MarkdownIt


def _e(value):return escape(str(value),quote=True)


def _details(label,value):
    return '<details><summary>'+_e(label)+'</summary><pre>'+_e(json.dumps(value,ensure_ascii=False,indent=2))+'</pre></details>'


def _markdown(body):
    renderer=MarkdownIt('commonmark',{'html':False}).enable('table')
    # Attachments need their own authenticated readers, not raw Markdown URLs.
    renderer.add_render_rule('image',lambda self,tokens,index,options,env:
        '<span class="knowledge-image-reference">이미지 · '+_e(tokens[index].content)+'</span>')
    return renderer.render(body)


FEEDBACK_SCRIPT='''<script>
document.addEventListener('submit',async event=>{
 const form=event.target;if(!form.matches('[data-document-feedback]'))return;event.preventDefault();
 const button=form.querySelector('button'),input=form.querySelector('textarea'),status=form.querySelector('[role=status]');
 if(!form.feedbackPayload){
  if(!input.value.trim())return;
  form.feedbackPayload={operation:'document_feedback',request:{revision:{ref:form.dataset.revision,revision_digest:form.dataset.digest},
    comment:input.value,idempotency_key:crypto.randomUUID()}};
 }
 button.disabled=true;input.readOnly=true;status.textContent='의견을 전달하고 있습니다.';
 try{
  const response=await fetch('/api/v2/knowledge-supervision',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'BoI-Wiki'},body:JSON.stringify(form.feedbackPayload)});
  if(!response.ok)throw new Error('submit');
  const value=await response.json();if(!value.feedback_ref)throw new Error('receipt');
  status.textContent='의견이 접수되었습니다. 담당자 Inbox에서 확인하고 교정에 반영할 수 있습니다.';
  button.textContent='접수됨';form.dataset.feedbackRef=JSON.stringify(value.feedback_ref);
 }catch(error){status.textContent='접수 결과를 확인하지 못했습니다. 같은 의견으로 다시 확인해 주세요.';button.disabled=false;button.textContent='접수 다시 확인';}
});
</script>'''


def feedback_form(value):
    revision=value['revision']
    return ('<section id="feedback"><h2>이 내용에 의견 보내기</h2><p>잘못된 설명이나 빠진 조건을 알려주세요. 현재 보고 있는 문서 개정과 함께 담당자에게 전달합니다.</p>'
        '<form data-document-feedback data-revision="'+_e(revision['ref'])+'" data-digest="'+_e(revision['revision_digest'])+'">'
        '<label>수정하거나 확인할 내용<textarea required maxlength="8000" rows="4" style="display:block;width:100%;box-sizing:border-box;font:inherit" name="comment"></textarea></label>'
        '<button type="submit">의견 보내기</button><p role="status" aria-live="polite"></p></form></section>')


def render_feedback_inbox(items):
    parts=['<section aria-label="피드백 Inbox"><h2>피드백 Inbox</h2><p>담당 지식에 도착한 의견입니다. 연결된 교정이 게시되면 그 결과를 함께 확인할 수 있습니다.</p>']
    if not items:parts+=['<p>현재 확인할 수 있는 의견이 없습니다.</p>']
    for item in items:
        parts+=['<article class="knowledge-card" data-feedback-item><p><strong>'+('교정 게시됨' if item['state']=='correction_published' else '접수된 의견')+'</strong></p>',
            '<p style="white-space:pre-wrap">'+_e(item['comment'])+'</p><a href="'+_e(item['document_url'])+'">의견이 달린 지식 보기</a>']
        if item.get('resolution_url'):parts+=[' · <a href="'+_e(item['resolution_url'])+'">교정 내용 보기</a>']
        parts+=[_details('에이전트에게 전달할 의견 참조',{'feedback_ref':item['feedback_ref'],'revision':item['revision']}),'</article>']
    return ''.join(parts+['</section>'])


STYLES='''<style>
.published-knowledge{max-width:1040px;margin:auto;line-height:1.65;overflow-wrap:anywhere}
.published-knowledge>header{display:block;padding:1.25rem 0;background:transparent;color:var(--fg,#16181d)}
.published-knowledge h1{font-size:clamp(1.55rem,3vw,2.25rem);line-height:1.3}
.published-knowledge h2{font-size:1.25rem;margin-top:1.8rem}.published-knowledge .meta{color:#536579}
.published-knowledge .badges{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0}
.published-knowledge .badge{background:#edf4fa;color:#244760;border-radius:1rem;padding:.2rem .75rem;font-size:.85rem}
.published-knowledge .document-body{padding:1.25rem 0;border-block:1px solid #dae3ec}
.published-knowledge .claim{padding:1.1rem;margin:1rem 0;border:1px solid #d6e1ec;border-radius:.8rem;background:#f8fafc}
.published-knowledge .claim:target{outline:2px solid #26739b}.published-knowledge .claim h3{margin:0;font-size:1.05rem}
.published-knowledge blockquote{margin:1rem 0;padding:.5rem 1rem;border-left:3px solid #8daeca;white-space:pre-wrap}
.published-knowledge pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}
.published-knowledge table{display:block;overflow:auto;border-collapse:collapse;max-width:100%}
.published-knowledge th,.published-knowledge td{padding:.5rem;border:1px solid #d6e1ec}
.published-knowledge summary{cursor:pointer}.published-knowledge li{margin:.3rem 0}
.published-knowledge nav{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.published-knowledge .source-note{background:#eef5f4;padding:1rem;border-radius:.6rem}
@media(max-width:600px){.published-knowledge .claim{padding:.85rem}.published-knowledge h2{font-size:1.1rem}}
</style>'''


PURPOSES={'explain':'설명','compare':'비교','filter':'조건 탐색','aggregate':'정확 집계','formula_input':'계산 입력','traverse':'관계 탐색'}
STATES={'usable_with_limits':'검사한 주장 범위에서 사용 가능','not_qualified':'사용 요건 미충족',
    'not_assessed':'사용 판정 없음','current_use_unavailable':'현재 사용 자격 확인 필요'}
MODALITIES={'asserted':'서술','possible':'가능성','intended':'의도','required':'요구 사항'}
KINDS={'source_reported':'원천에 기록된 내용','interpretation':'해석','derived':'도출','recommendation':'권고'}


def render_published_document(value):
    url=value['document_url']
    correction=value.get('content_correction')
    correction_html=''
    if correction:
        correction_html=('<aside class="source-note" data-content-correction><strong>Wiki 교정 · 원문 보존</strong>'
            '<details><summary>교정 이유와 원천과의 차이</summary><p>'+_e(correction['reason'])
            +'</p><p>'+_e(correction['source_difference'])+'</p></details></aside>')
    scopes=['나만 보기' if s['visibility']=='private' else '전체 공개' if s['visibility']=='public' else '팀 · '+s['team_id']
        for s in value['targets']]
    parts=[STYLES,'<article class="published-knowledge" data-published-knowledge><header><p class="meta">지식 문서</p><h1>',
        _e(value['title']),'</h1><div class="badges"><span class="badge" data-publication-state>게시됨</span>',
        ''.join('<span class="badge">'+_e(s)+'</span>' for s in scopes),
        '</div><p class="meta">'+('현재 개정' if value['is_current_revision'] else '공개가 허용된 이전 개정')+'</p></header>',
        '<nav aria-label="문서 안에서 이동"><a href="#document-body">본문</a><a href="#knowledge-claims">주장과 조건</a>',
        '<a href="#knowledge-uses">사용 범위</a><a href="#feedback">의견 보내기</a><a href="/knowledge?tab=inbox">피드백 Inbox</a></nav>',
        correction_html,'<section class="document-body rendered-content" id="document-body" data-published-body>',
        _markdown(value['document']['body'] or ''),'</section>',
        '<section id="knowledge-claims"><h2>주장과 조건</h2><p class="meta">조건·예외와 함께 읽고, 필요한 근거를 열어 확인하세요.</p>']
    source_cards=value.get('source_bundle',{}).get('source_cards',[])
    material_numbers={r['binding_index']:card['number'] for card in source_cards for r in card['references']}
    for i,claim in enumerate(value['claims'],value['claim_offset']+1):
        data=claim['value'];typed=isinstance(data,dict) and 'assertion_kind' in data and 'polarity' in data
        fallback=value['title'] if claim['pointer']=='' else claim['pointer']
        parts+=['<article class="claim" data-knowledge-claim><h3>',_e(data.get('statement',fallback) if isinstance(data,dict) else data),'</h3>']
        if claim.get('formula_selection'):
            descriptor=data['semantic_descriptor']
            role={'measurement':'측정값','setpoint':'설정값','upper_limit':'상한','lower_limit':'하한','computed':'계산값'}.get(descriptor['role'],descriptor['role'])
            parts+=['<div data-formula-definition><p>'+_e(data['parameter_name'])+' · '+_e(role)+' · '+_e(descriptor['unit_ref'])+'</p>',
                '<p>대상 · '+_e(data['component'])+'</p><p>'+('명시된 정의로 계산 입력을 준비할 수 있습니다.' if claim.get('formula_qualification')
                    else '계산 입력으로 쓰기 위한 확인이 필요합니다. 설명과 원문은 읽을 수 있습니다.')+'</p>',
                '<p>관측값과 관측 시각은 계산할 때 별도로 제공해야 합니다.</p></div>']
            for key,label in (('conditions','조건'),('exceptions','예외')):
                for condition in descriptor[key]:parts+=['<p>'+label+' · '+_e(condition)+'</p>']
            if data['uncertainties']:parts+=['<p>미확인 사항 · '+_e(' · '.join(data['uncertainties']))+'</p>']
        if typed:
            labels=[KINDS.get(data['assertion_kind'],data['assertion_kind']),MODALITIES.get(data['modality'],data['modality']),
                '부정' if data['polarity']=='negative' else '긍정']
            parts+=['<p class="meta">'+_e(' · '.join(labels))+'</p>']
            for field,label in (('conditions','조건'),('exceptions','예외'),('applicability','적용 범위')):
                if data.get(field):parts+=['<div data-claim-'+field+'><strong>'+label+'</strong><ul>',
                    ''.join('<li>'+_e(c['statement'])+'</li>' for c in data[field]),'</ul></div>']
            time=data['valid_time'];label={'unknown':'시점 미상','timeless':'시점과 무관하게 선언됨'}.get(time['state'])
            parts+=['<p>'+_e(label or ('적용 시점 · '+str(time.get('start'))+' ~ '+str(time.get('end') or '끝 시점 미상')))+'</p>']
            if data['uncertainties']:parts+=['<p>미확인 사항 · '+_e(' · '.join(data['uncertainties']))+'</p>']
            if claim.get('dependency_reads'):
                parts+=['<p>함께 읽을 내용 · '+ ' · '.join('<a href="'+_e(d['url'])+'">연결된 주장 '+str(j)+'</a>'
                    for j,d in enumerate(claim['dependency_reads'],1))+'</p>']
        sources={}
        for source in claim['source_bindings']:sources.setdefault(source['source_key'],source)
        parts+=['<nav aria-label="이 주장의 근거">'+''.join('<a data-published-source href="'+_e(s['source_url'])+'">근거 '+str(material_numbers.get(s['binding_index'],j))+' · '+_e(s['field_locator'] or '전체 원문 필드')+'</a>'
            for j,s in enumerate(sources.values(),1))+'</nav>',_details('구조화된 내용과 정확한 참조',data),'</article>']
    if source_cards:
        parts+=['<section data-published-source-cards><h2>원자료</h2>']
        for card in source_cards:
            parts+=['<article data-source-card><h3>자료 '+str(card['number'])+'</h3><ul>']
            for reference in card['references']:
                parts+=['<li><a data-material-reference href="'+_e(reference['citation_url'])+'">'+_e(reference['field_locator'])+'</a></li>']
            parts+=['</ul></article>']
        parts+=['</section>']
    if value['next_claim_offset'] is not None:
        parts+=['<a rel="next" href="'+_e(url+'?'+urlencode({'claim_offset':value['next_claim_offset']}))+'#knowledge-claims">다음 주장 보기</a>']
    parts+=['</section><section id="knowledge-uses"><h2>사용 범위</h2><p>용도별 검사는 명시된 주장에 적용됩니다. 사실 여부와 원문 접근 권한은 별도로 확인합니다.</p><ul>']
    for use in value['uses']:
        parts+=['<li><strong>'+_e(PURPOSES.get(use['purpose'],use['purpose']))+'</strong> · '+_e(STATES.get(use['status'],use['status']))+
            ('<span class="meta"> · 검사한 주장 '+str(len(use['qualified_roots']))+'개</span>' if use['qualified_roots'] else '')+'</li>']
    parts+=['</ul></section>']
    if value['unresolved']:
        parts+=['<section><h2>아직 확인하지 못한 내용</h2><ul>'+''.join('<li>'+_e(u['description'])+'</li>' for u in value['unresolved'])+'</ul></section>']
    parts+=[feedback_form(value),_details('문서 정보와 Profile',{'metadata':value['document']['frontmatter'],'profiles':value['profiles'],
        'revision':value['revision'],'policy_revision':value['policy_revision']}),'</article>']
    return ''.join(parts)


def render_published_source(value):
    from .native_definition_sources import source_quote_html
    back=(value['document_url']+('?' + urlencode({'meaning':value['meaning_pointer']})
        if value['meaning_pointer'] else '')+'#knowledge-claims')
    parts=[STYLES,'<article class="published-knowledge" data-published-source-view><h1>인용한 원문 확인</h1>',
        '<nav><a href="'+_e(back)+'">해당 주장으로 돌아가기</a></nav>',
        ('<p>출처 파일 · '+_e(value['source_display_name'])+'</p>' if value.get('source_display_name') else ''),
        '<p>원문 위치 · '+_e(value['field_locator'] or '전체 원문 필드')+'</p><div data-source-quote>'+source_quote_html(value['quote'])+'</div>',
        '<p class="source-note">이 인용은 저장된 원문 위치와 일치합니다. 주장 해석의 타당성과 사실 여부를 별도로 확인해야 합니다.</p>',
        '<h2>주변 원문</h2><details data-source-context-details><summary>주변 원문 표기와 위치 보기</summary>',
        '<p class="meta">'+str(value['offset'])+'–'+str(value['end'])+' / '+str(value['character_count'])+'자</p>',
        # A bounded context page may start mid-tag. Preserve its exact text;
        # only the complete selected quote is eligible for an inert preview.
        '<pre data-source-context>'+_e(value['text'])+'</pre>']
    if value['offset']>0:
        parts+=['<a href="?offset=0">원문 필드 처음부터 보기</a>']
    if value['next_offset'] is not None:
        parts+=['<a rel="next" href="?offset='+str(value['next_offset'])+'">다음 원문 보기</a>']
    parts+=['</details>',_details('원문 상태와 변환 정보',{'field_metadata':value['field_metadata'],'transformations':value['transformations'],
        'source_revision_digest':value['source_revision_digest'],'span':value['span']}),'</article>']
    return ''.join(parts)


def render_published_unavailable(*,source,status):
    title='원문을 열 수 없습니다' if source else '지식을 열 수 없습니다'
    message=('현재 계정에 열람 권한이 없거나 공개 범위가 변경되었습니다.' if status in (401,403,404)
        else '현재 개정과 접근 조건을 확인하지 못했습니다. 이전에 저장된 결과로 대신 표시하지 않습니다.')
    return (STYLES+'<article class="published-knowledge" data-published-unavailable><h1>'+title+'</h1><p>'+message+'</p>'+(
        '<p>지식 문서와 원문 자료의 공개 범위는 다를 수 있습니다.</p>' if source else '')+
        '<a href="/knowledge">내 지식 공간으로 이동</a></article>')
