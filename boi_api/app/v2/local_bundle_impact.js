// Same-origin human preview; no local body or source file is sent by these GETs.
let impactReady = !reviewData.impact_required, impactReview = null, impactGeneration = 0;
const impactStatus = document.getElementById('impact-status');
const impactContent = document.getElementById('impact-content');
const impactLoad = document.getElementById('impact-load');
const impactRoot = '/api/v2/local-bundles/' + encodeURIComponent(intent.bundle_ref.split(':').pop()) + '/impact';
function invalidateImpact(error) {
  impactGeneration++;
  impactReady = !reviewData.impact_required;
  impactReview = null;
  impactContent.replaceChildren();
  impactStatus.textContent = error?.message === 'LOCAL_BUNDLE_IMPACT_BROWSER_REQUIRED'
    ? 'Wiki에 로그인한 화면에서 현재 연결을 확인할 수 있습니다.'
    : '지식이나 권한이 바뀌었거나 조회를 완료하지 못했습니다. 현재 연결을 다시 조회해 주세요.';
  updateConfirmAvailability();
}
async function impactGet(url) {
  const response = await fetch(url, {credentials:'same-origin',cache:'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail?.reason_code || 'LOCAL_BUNDLE_IMPACT_READ_FAILED');
  return data;
}
function spaceName(target) {
  return target.visibility === 'private' ? '내 Private 지식' : target.visibility === 'public'
    ? '공개 지식' : '팀 · ' + target.team_id;
}
function drawScope(scope, scopeIndex, generation) {
  const card = node('article');
  card.append(node('h3', spaceName(scope.target)), node('p',
    `조회 대상 ${scope.visible_members}개 · 직접 연결 ${scope.matching_visible_members}개 · 참조 미정리 ${scope.unprepared_visible_members}개`));
  if (scope.unprepared_visible_members) card.append(node('p',
    '참조 미정리 지식은 연결 조사에서 빠져 있습니다. 정리가 끝나기 전에는 연결 건수를 전체 영향으로 볼 수 없습니다.', 'warning'));
  if (scope.matching_visible_members) {
    const list = node('div'), button = node('button', '연결된 지식 보기', 'secondary');
    let cursor = null;
    button.onclick = async () => {
      if (!impactReady || generation !== impactGeneration || reviewConfirmBusy) return;
      button.disabled = true;
      try {
        const params = new URLSearchParams({impact_ref:impactReview.impact_ref,scope_index:String(scopeIndex)});
        if (cursor) params.set('cursor',cursor);
        const result = await impactGet(impactRoot + '/page?' + params);
        if (generation !== impactGeneration) return;
        if (result.impact_ref !== impactReview.impact_ref || result.scope_index !== scopeIndex)
          throw new Error('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED');
        for (const item of result.items) {
          const details = node('details');
          details.append(node('summary',item.title),node('p',
            '이 문서에 선언된 연결입니다. 사실 검증이나 의미 충돌 판정은 아닙니다.'));
          for (const edge of item.declared_references) {
            const label = {dependency:'참조',declared_conflict:'충돌 선언',supersedes:'대체 선언'}[edge.kind] || edge.kind;
            details.append(node('p', label + (edge.role ? ' · ' + edge.role : '') + (edge.reason ? ': ' + edge.reason : '')));
          }
          details.append(node('code',item.revision.ref));
          list.append(details);
        }
        cursor = result.next_cursor;
        button.textContent = cursor ? '다음 연결 보기' : '직접 연결 조회 완료';
        button.disabled = !cursor;
      } catch (error) { if (generation === impactGeneration) invalidateImpact(error); }
    };
    card.append(button,list);
  }
  impactContent.append(card);
}
impactLoad.onclick = async () => {
  if (reviewConfirmBusy || !reviewConsentPending) return;
  const generation = ++impactGeneration;
  impactReady = false; impactReview = null;
  impactLoad.disabled = true;
  impactContent.replaceChildren();
  impactStatus.textContent = '현재 권한과 게시된 지식의 연결을 확인하고 있습니다.';
  updateConfirmAvailability();
  try {
    const result = await impactGet(impactRoot + '?preview_digest=' + encodeURIComponent(intent.preview_digest));
    if (generation !== impactGeneration) return;
    if (result.bundle_ref !== intent.bundle_ref || result.preview_digest !== intent.preview_digest
        || result.manifest_digest !== intent.manifest_digest) throw new Error('LOCAL_BUNDLE_IMPACT_BINDING_CHANGED');
    impactReview = result; impactReady = true;
    impactStatus.textContent = `${result.scopes.length}개 공간에서 기존 개정 ${result.target_revision_count}개에 대한 직접 연결을 조회했습니다. ` +
      '같은 문서가 여러 공간에 나타날 수 있어 공간별 건수를 합산하지 않습니다.';
    result.scopes.forEach((scope,index) => drawScope(scope,index,generation));
    if (!result.target_revision_count) impactContent.prepend(node('p',
      '이 묶음에는 조사할 기존 개정이 없습니다. 새 지식과 기존 내용의 의미상 관련성은 아직 평가하지 못했습니다.', 'warning'));
  } catch (error) { if (generation === impactGeneration) invalidateImpact(error); }
  finally { impactLoad.disabled = false; updateConfirmAvailability(); }
};
if (!reviewData.impact_required) {
  impactLoad.disabled = true;
  impactStatus.textContent = reviewConsentPending
    ? '이 저장 경로에서는 현재 연결 조회가 준비되지 않았습니다. 전체 영향 확인이 끝난 상태로 보지 않습니다.'
    : '이미 확인한 묶음은 기존 확인 기록으로 이어갑니다. 같은 전송에 새 확인을 요구하지 않습니다.';
}
updateConfirmAvailability();
