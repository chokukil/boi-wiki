"""A concrete, escaped preview of the exact locally prepared batch."""
import html
import json
from pathlib import Path

_REVIEW_SCRIPT = Path(__file__).with_name('local_bundle_review.js').read_text(encoding='utf-8')
_IMPACT_SCRIPT = Path(__file__).with_name('local_bundle_impact.js').read_text(encoding='utf-8')
_ARCHIVE_SCRIPT = Path(__file__).with_name('local_bundle_archive.js').read_text(encoding='utf-8')


def render_bundle_confirmation(value):
    def esc(text):
        return html.escape(str(text or ''), quote=True)
    def size(count):
        return f'{count / (1024 * 1024):.2f} MB' if count >= 1024 * 1024 else f'{count:,} 바이트'
    manifest, preview = value['manifest'], value['preview']
    context = value.get('confirmation_context') or value.get('confirmation_session_context') or {}
    confirmation_notice = ''
    if context.get('auth_source') == 'dev_session':
        participation = '사용자 위임에 따른 에이전트 대리 확인' if context.get('delegation_ref') else '개발 계정 확인'
        confirmation_notice = '<p class="status">개발 실행 · ' + esc(participation) + ' · ' + esc(context.get('actor')) + '</p>'
    use_labels = {'read':'본문 열람', 'compute':'계산', 'explain':'근거를 바탕으로 설명',
        'compare':'비교', 'filter':'조건에 맞는 지식 찾기', 'aggregate':'집계',
        'formula_input':'Formula 입력', 'traverse':'관계 탐색'}
    requested_uses = ', '.join(use_labels[purpose] for purpose in manifest['intended_uses'])
    target = preview['sharing']['target']
    audience = {'private':'본인만 열람', 'team':'팀 구성원 · ' + str(target['team_id']),
                'public':'기존 Wiki 공개 지식의 독자 범위'}[target['visibility']]
    capacity_blocked = preview.get('publication_capacity',{}).get('status') == 'atomic_unit_plan_required'
    disabled = (value['state'] != 'awaiting_confirmation' or not value['basis_current']
                or preview['impact']['head_conflicts'] > 0 or capacity_blocked)
    capacity_notice = ('<p class="warning">자료 간 연결을 유지하면서 처리 가능한 게시 단위로 나누는 계획이 필요합니다. '
        '이 계획이 준비된 뒤 묶음을 확인할 수 있습니다.</p>' if capacity_blocked else '')
    plan=preview.get('publication_plan')
    progress=value.get('publication_progress')
    if plan and plan['units']:
        titles={c['object_id']:c['title'] for c in manifest['changes']}
        states={u['unit_id']:u['state'] for u in (progress or {}).get('units',[])}
        labels={'pending':'대기','prepared':'게시 준비','reserved':'게시 진행 중',
            'projection_prepared':'완료 확인 전','published':'게시 완료',
            'aborting':'미게시 변경 정리 중','aborted':'게시 중단'}
        units=''.join('<details><summary>'+f'{i+1}번째 반영 · {len(u["object_ids"])}개 지식 · '+
            labels[states.get(u['unit_id'],'pending')]+
            '</summary><p>'+esc(', '.join(titles[x] for x in u['object_ids']))+'</p></details>' for i,u in enumerate(plan['units']))
        capacity_notice+=f'<p>자료를 {len(plan["units"])}개 게시 단위로 나눠 순서대로 반영합니다. '
        capacity_notice+='완료된 단위부터 사용할 수 있으며, 같은 단위의 자료가 일부만 공개되지는 않습니다. '
        capacity_notice+='선행 자료의 결과가 미확정이면 그 자료에 의존하는 단위는 기다립니다.</p>'+units
    status = {'awaiting_confirmation':'전송 전 확인', 'receiving':'파일 전송 중',
              'uploaded_requires_validation':'전송 완료 · 서버 검사 대기', 'stopped':'전송 중단',
              'published':'자료 게시 완료','publication_partial':'일부 단위 게시 완료',
              'publication_in_progress':'자료 게시 진행 중',
              'publication_needs_attention':'중단된 게시 단위 확인 필요'}[value['state']]
    if progress and progress['published_units']:
        capacity_notice+=f'<p>{progress["published_units"]}개 단위 게시 완료 · {progress["remaining_units"]}개 단위 남음. '
        capacity_notice+='질의·계산에 사용할 수 있는 범위는 각 지식의 검사 결과에 따라 달라집니다.</p>'
    if progress and progress['aborted_units']:
        capacity_notice+='<p class="warning">중단된 단위는 게시되지 않았습니다. 이미 게시된 다른 단위는 유지됩니다.</p>'
    purpose = {'raw_source':'원천 자료', 'native_proposal':'정리한 지식', 'check_evidence':'로컬 검사 결과'}
    files = ''.join(f'<tr><td>{esc(x["display_name"])}<details><summary>파일 해시</summary><code>{esc(x["byte_digest"])}</code></details></td>'
        f'<td>{purpose[x["purpose"]]}</td><td>{size(x["byte_length"])}</td></tr>' for x in manifest['objects'])
    changes = ''.join(f'<article><h3>{esc(x["title"])}</h3><p>{esc(x["summary"])}</p>'
        f'<p>{"개정" if x["operation"] == "revise" else "새 지식"} · {esc(x["namespace"])}</p>'
        + (f'<p><strong>교정 이유</strong> {esc(x["correction"]["reason"])}</p>'
           f'<p><strong>원천과의 차이</strong> {esc(x["correction"]["source_difference"])}</p>'
           + ('<p>같은 자료 정리 기준을 개정합니다. 새 스키마 원천을 연결하고 기존 원천·지식의 참조·공유 범위를 유지합니다.</p>'
              if x['kind'] == 'profile' else
              '<p>같은 지식의 새 개정으로 게시합니다. 원문과 공유 범위를 유지합니다.</p>')
           if x.get('correction') else '') +
        f'<p>현재: {esc(x["current_title"]) or "등록된 지식 없음"}</p>'
        f'<details><summary>현재 개정 확인</summary><code>{esc(json.dumps(x["current_revision"], ensure_ascii=False))}</code></details>'
        f'{"<p class=warning>준비 당시 개정과 다릅니다. 새 비교가 필요합니다.</p>" if x["head_conflict"] else ""}</article>'
        for x in preview['changes'])
    pending = ''.join('<li>' + esc(x) + '</li>' for x in manifest['unresolved']) or '<li>작성자가 신고한 미해결 항목 없음</li>'
    # Only server-generated identifiers enter executable JSON; escape HTML script delimiters too.
    payload = json.dumps({key:value[key] for key in ('bundle_ref','manifest_digest','preview_digest')},
                        ensure_ascii=True).replace('<', '\\u003c')
    review_payload = json.dumps({**{key:manifest[key] for key in ('changes','objects','references')},
        'impact_required':value.get('impact_review_required',False)},
        ensure_ascii=True).replace('<', '\\u003c')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>로컬 자료 등록 확인 · BoI Wiki</title><style>
body{font:16px/1.65 system-ui,sans-serif;background:#f4f6f8;color:#182d36;margin:0}main{max-width:1050px;margin:auto;padding:28px}
a{color:#14587b}header,p{overflow-wrap:anywhere}h1{font-size:30px;line-height:1.3}h2{font-size:21px;margin-top:30px}
article,.card{background:white;border:1px solid #d4dfe4;padding:20px;border-radius:12px;margin:14px 0}h3{margin-top:0}
table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #d4dfe4}
code{font-size:12px;overflow-wrap:anywhere}td:last-child{max-width:280px}.scroll{overflow-x:auto}.warning{color:#83400e}
button{font:inherit;padding:12px 18px;border-radius:7px;border:1px solid #185578;background:#185578;color:white;cursor:pointer}
button:disabled{background:#64727a;cursor:default}.secondary{background:white;color:#185578}input{font:inherit;max-width:100%}summary{cursor:pointer}
.secondary:disabled{background:#e4ebef;color:#3d515c;border-color:#b6c6cf}
label{display:block;margin:16px 0}.status{font-weight:700;color:#185578}#message{white-space:pre-wrap}small{color:#49606d}
.review-columns{display:grid;grid-template-columns:1fr 1fr;gap:22px}.review-columns>section{min-width:0}
.review-body,.review-json{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}
.review-body{max-height:65vh;overflow:auto;padding:12px;border:1px solid #d4dfe4;background:#fafcfd}
.review-json{max-height:50vh;overflow:auto;font-size:13px}select{font:inherit;max-width:100%;padding:8px}
@media(max-width:600px){main{padding:16px}h1{font-size:25px}article,.card{padding:14px}td,th{padding:8px}}
@media(max-width:760px){.review-columns{grid-template-columns:1fr}}
</style><main><header><a href="/knowledge?tab=work">← 자산화 작업</a><p class="status" id="stage">''' + esc(status) + '''</p>
<h1>''' + esc(manifest['title']) + '''</h1><p>''' + esc(manifest['description']) + '''</p>''' + confirmation_notice + '''</header>
<section class="card"><h2>확인하는 범위</h2><p>''' + f'{len(manifest["changes"]):,}개 지식 · {preview["object_count"]:,}개 파일 · {size(preview["total_bytes"])}' + '''</p>
<p>게시할 공간: ''' + esc(audience) + '''</p><p>준비한 사람: ''' + esc(preview['sharing']['owner']) + '''</p>
<p>요청한 활용: ''' + esc(requested_uses) + '''. 실제 활용 가능 여부는 각 용도의 검사 결과에 따라 달라집니다.</p>
<p>아래 변경과 파일을 확인하면 전송을 시작할 수 있습니다. 전송을 중단해도 이미 받은 파일은 보존됩니다.</p>''' + capacity_notice + '''
<details><summary>확인 범위</summary><p class="warning">같은 지식의 개정 충돌과 아래에서 조회하는 직접 연결을 구분합니다. 내용의 의미상 충돌과 간접 영향은 아직 평가하지 못했습니다.</p></details>
<p><small>전송 후 외부 AI가 서버 검사와 용도별 판정을 확인하고 게시를 이어갈 수 있습니다. 게시된 문서와 실제 활용 가능한 범위는 따로 표시됩니다.</small></p></section>
<section class="card" id="impact-section"><h2>기존 지식과 연결 확인</h2>
<p>현재 접근 가능한 공간에 게시된 OKF 지식에서 이 묶음의 기존 개정을 참조하는 지식을 찾습니다. 기존 파일과 공간 밖 자료는 이 조회에 포함되지 않습니다.</p>
<button id="impact-load" class="secondary">현재 연결 조회</button>
<p id="impact-status" role="status" aria-live="polite">현재 연결을 조회해 주세요. 원천 파일과 로컬 본문은 전송하지 않습니다.</p>
<div id="impact-content"></div>
<p class="warning">이 조회는 문서에 선언된 직접 연결만 다룹니다. 새 지식과의 의미상 관련성·내용 충돌·간접 영향·접근할 수 없는 지식은 아직 평가하지 못했습니다. 연결 0건은 전체 영향이 없다는 뜻이 아닙니다.</p></section>
<section class="card"><h2>본문을 보고 확인하기</h2>
<p>외부 AI가 준비한 묶음 파일 하나를 선택하면 이 브라우저에서 본문·조건·근거를 확인할 수 있습니다. 파일 선택만으로 내용이 서버에 전송되지는 않습니다.</p>
<label>준비된 묶음 선택 <input id="files" type="file" multiple></label>
<p id="review-status" role="status" aria-live="polite">AI가 전달한 .boi-bundle.zip 파일을 선택해 주세요. 이전에 준비한 개별 파일도 함께 선택해 사용할 수 있습니다.</p>
<label>비교할 지식 <select id="review-select"></select></label><div id="review-content"></div>
<p><small>각 항목을 승인할 필요는 없습니다. 필요한 내용을 살펴보고 아래에서 묶음을 한 번 확인합니다. 원천 인용은 문서에 기록된 내용이며 원천 파일 열람 권한이나 사실 검증을 뜻하지 않습니다.</small></p></section>
<details><summary>전체 변경 목록</summary>''' + changes + '''</details><h2>전송할 파일</h2><p>서버에는 파일 이름·크기·해시와 변경 설명이 먼저 전달됩니다. 본문 비교에서 읽은 로컬 내용은 확인 전까지 브라우저에 머뭅니다.</p>
<div class="scroll"><table><thead><tr><th>파일</th><th>용도</th><th>크기</th></tr></thead><tbody>''' + files + '''</tbody></table></div>
<details><summary>미해결 항목</summary><ul>''' + pending + '''</ul></details>
<section class="card"><h2>확인 및 전송</h2><p id="message" role="status" aria-live="polite">''' + esc(status) + '''</p>
<button id="confirm" ''' + ('disabled' if disabled else '') + '''>이 묶음의 전송 확인</button>
<small>외부 에이전트에서도 확인된 같은 파일을 올릴 수 있습니다. 브라우저는 전송 직전에 로컬 파일 해시를 대조합니다.</small>
<p><button id="upload" class="secondary" ''' + ('disabled' if not value['confirmation_recorded'] or value['state'] == 'stopped' else '') + '''>선택한 파일 전송 / 이어 올리기</button>
<button id="refresh" class="secondary">상태 새로고침</button> <button id="stop" class="secondary">전송 중단</button></p>
<progress id="progress" value="0" max="1" aria-label="파일 전송 진행률"></progress></section>
<details><summary>묶음 식별 정보</summary><p>''' + esc(value['bundle_ref']) + '''</p><code>''' + esc(value['manifest_digest']) + '''</code></details></main>
<script>
const intent = ''' + payload + ''';
const reviewData = ''' + review_payload + ''';
const message = document.getElementById('message');
const headers = {'Content-Type':'application/json','X-Requested-With':'BoI-Wiki'};
async function jsonRequest(url, body) {
  const response = await fetch(url, {method:'POST',headers,credentials:'same-origin',body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.detail?.reason_code || '요청에 실패했습니다.');
  return value;
}
async function work(phase) {
  return jsonRequest('/api/v2/knowledge-work', {operation:'publication',request:{contract_version:'boi/local-publication@1',phase,payload:{bundle_ref:intent.bundle_ref}}});
}
function failure(error) {
  const labels = {LOCAL_BUNDLE_WEB_SESSION_NOT_AUTHORIZED:'Wiki에 로그인한 편집자 세션에서 확인해 주세요.',
    LOCAL_BUNDLE_IMPACT_REVIEW_REQUIRED:'현재 연결을 조회한 뒤 묶음을 확인해 주세요.',
    LOCAL_BUNDLE_IMPACT_SCOPE_CHANGED:'지식 공간이나 권한이 바뀌었습니다. 현재 연결을 다시 조회해 주세요.',
    LOCAL_BUNDLE_IMPACT_SNAPSHOT_CHANGED:'연결된 지식이 바뀌었습니다. 현재 연결을 다시 조회해 주세요.',
    LOCAL_BUNDLE_IMPACT_BINDING_CHANGED:'확인할 묶음과 연결 조회 결과가 다릅니다. 화면을 새로 열어 주세요.',
    LOCAL_BUNDLE_PREVIEW_BASIS_CHANGED:'준비한 뒤 지식이 바뀌었습니다. 최신 개정으로 변경 비교를 다시 만들어 주세요.',
    LOCAL_BUNDLE_UPLOAD_NOT_AUTHORIZED:'이 묶음은 아직 확인되지 않았거나 전송이 중단되었습니다.',
    LOCAL_BUNDLE_POLICY_CHANGED:'권한이나 공유 정책이 바뀌었습니다. 현재 접근 권한을 확인해 주세요.'};
  message.textContent = labels[error.message] || ('진행을 멈췄습니다. ' + error.message);
}
document.getElementById('confirm').onclick = async function() {
  if (!reviewVerified || !reviewConsentPending || reviewConfirmBusy || !impactReady) return;
  reviewConfirmBusy = true;
  this.disabled = true;
  try {
    const impact = impactReview ? {impact_ref:impactReview.impact_ref} : {};
    const challenge = await jsonRequest('/api/v2/local-bundles/challenge', {bundle_ref:intent.bundle_ref,...impact});
    if (challenge.preview_digest !== intent.preview_digest || challenge.manifest_digest !== intent.manifest_digest) throw new Error('확인할 내용이 변경되었습니다.');
    if (challenge.impact_ref !== impact.impact_ref) throw new Error('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED');
    try { await jsonRequest('/api/v2/local-bundles/confirm', {...intent,...impact,nonce:challenge.nonce}); }
    catch(error) {
      const status = await work('status');
      if (!status.confirmation_recorded || status.manifest_digest !== intent.manifest_digest || status.state === 'stopped'
          || (status.confirmed_impact_ref || undefined) !== impact.impact_ref) throw error;
    }
    message.textContent = '확인되었습니다. 같은 파일을 전송하거나 외부 에이전트에서 이어 올릴 수 있습니다.';
    document.getElementById('stage').textContent = '전송 준비됨';
    document.getElementById('upload').disabled = false;
    reviewConsentPending = false;
  } catch(error) {
    if (error.message.startsWith('LOCAL_BUNDLE_IMPACT_')) invalidateImpact(error);
    failure(error);
  }
  finally { reviewConfirmBusy = false; updateConfirmAvailability(); }
};
document.getElementById('refresh').onclick = () => location.reload();
document.getElementById('stop').onclick = async () => { try {await work('stop'); location.reload();} catch(error) {failure(error);} };
async function digest(buffer) {
  const hash = await crypto.subtle.digest('SHA-256', buffer);
  return 'sha256:' + Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2,'0')).join('');
}
document.getElementById('upload').onclick = async function() {
  this.disabled = true;
  try {
    const state = await work('status');
    if (!state.confirmation_recorded || !state.basis_current || state.state === 'stopped') throw new Error('LOCAL_BUNDLE_UPLOAD_NOT_AUTHORIZED');
    const selected = await selectedBundleFiles(document.getElementById('files')), matched = [];
    if (!selected.length) throw new Error('올릴 파일을 선택해 주세요.');
    for (const file of selected) {
      // The bounded browser path hashes one file at a time. The agent kit can
      // stream larger files; no source body enters the JSON control endpoint.
      if (file.size > 256 * 1024 * 1024) throw new Error('파일당 전송 한도는 256 MB입니다.');
      message.textContent = file.name + ' 파일을 로컬에서 대조하고 있습니다.';
      const hash = await digest(await file.arrayBuffer());
      const candidates = state.manifest.objects.filter(x => x.byte_length === file.size && x.byte_digest === hash);
      if (!candidates.length) throw new Error(file.name + ': 확인한 묶음에 없는 파일입니다.');
      for (const obj of candidates) if (!matched.some(x=>x.obj.object_id===obj.object_id)) matched.push({file,obj});
    }
    const chunks = [], width = state.upload_limits.chunk_bytes;
    document.getElementById('stage').textContent = '파일 전송 중';
    for (const {file,obj} of matched) {
      const old = state.uploads.find(x=>x.object_id===obj.object_id);
      if (old.complete) continue;
      for (let offset=0; offset<file.size; offset+=width) if (!old.received_offsets.includes(offset)) chunks.push({file,obj,offset});
    }
    let next=0, completed=0, failed=false;
    const progress = document.getElementById('progress'); progress.max=Math.max(1,chunks.length); progress.value=0;
    async function worker() {
      while (!failed && next<chunks.length) {
        const {file,obj,offset}=chunks[next++], raw=await file.slice(offset,offset+width).arrayBuffer();
        const url='/api/v2/local-bundles/'+intent.bundle_ref.split(':').pop()+'/objects/'+encodeURIComponent(obj.object_id)+'?offset='+offset;
        try {
          const response=await fetch(url,{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream','X-Requested-With':'BoI-Wiki','X-Boi-Chunk-Digest':await digest(raw)},body:raw});
          const result=await response.json(); if (!response.ok) throw new Error(result.detail?.reason_code || '파일 전송 실패');
          completed++; progress.value=completed; message.textContent='전송 중 '+completed+' / '+chunks.length;
        } catch(error) {failed=true; throw error;}
      }
    }
    const results=await Promise.allSettled(Array.from({length:Math.min(4,chunks.length)},worker));
    const rejected=results.find(x=>x.status==='rejected'); if (rejected) throw rejected.reason;
    const latest=await work('status');
    message.textContent = latest.state==='uploaded_requires_validation' ? '전송 완료. 연결한 AI에서 서버 검사와 게시를 이어갈 수 있습니다.' : '선택한 파일을 받았습니다. 남은 파일을 선택해 이어 올릴 수 있습니다.';
    document.getElementById('stage').textContent = latest.state==='uploaded_requires_validation' ? '전송 완료 · 서버 검사 대기' : '파일 전송 중';
  } catch(error) {failure(error);} finally {this.disabled=false;}
};
''' + _ARCHIVE_SCRIPT + _REVIEW_SCRIPT + _IMPACT_SCRIPT + '''
</script></html>'''
