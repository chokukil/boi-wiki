// Included in the confirmation page's hashed CSP. Local files are only read;
// the existing, separately confirmed upload handler owns all byte transmission.
const reviewFiles = new Map();
const reviewStatus = document.getElementById('review-status');
const reviewSelect = document.getElementById('review-select');
const confirmButton = document.getElementById('confirm');
const reviewAllowed = !confirmButton.disabled;
let reviewGeneration = 0, renderGeneration = 0;
let reviewVerified = false, reviewConsentPending = reviewAllowed, reviewConfirmBusy = false;
confirmButton.disabled = true;
function updateConfirmAvailability() {
  confirmButton.disabled = !reviewConsentPending || !reviewVerified || reviewConfirmBusy || !impactReady;
}
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
const changeIndex = new Map(reviewData.changes.map(c => [c.object_id, c]));
const objectIndex = new Map(reviewData.objects.map(o => [o.object_id, o]));
const referenceIndex = new Map();
for (const r of reviewData.references) {
  if (!referenceIndex.has(r.object_id)) referenceIndex.set(r.object_id, []);
  referenceIndex.get(r.object_id).push(r);
}
for (const c of reviewData.changes) reviewSelect.append(new Option(c.title, c.object_id));

// Keep exact JSON token slices for metadata/numbers/extensions. JSON.parse by
// itself silently accepts duplicate keys and rounds large numbers. The reader
// rejects duplicate keys and excessive nesting; it is not a domain validator.
function localDocument(raw) {
  const ranges = new Map(); let pos = 0, tokens = 0;
  const skip = () => {while (pos < raw.length && /[\x20\t\r\n]/.test(raw[pos])) pos++;};
  const fail = () => {throw new Error('중복 키 또는 잘못된 JSON입니다. 로컬 검사 후 다시 준비해 주세요.');};
  function string() {
    const start = pos++;
    while (pos < raw.length) {
      if (raw[pos] === '\\') {pos += 2; continue;}
      if (raw[pos++] === '"') return JSON.parse(raw.slice(start, pos));
    }
    fail();
  }
  function read(path, depth) {
    if (depth > 64 || ++tokens > 200000) throw new Error('비교할 JSON의 깊이 또는 항목 수가 한도를 넘었습니다.');
    skip(); const start = pos;
    if (raw[pos] === '{') {
      pos++; skip(); const keys = new Set();
      if (raw[pos] !== '}') while (true) {
        skip(); if (raw[pos] !== '"') fail(); const key = string();
        if (keys.has(key)) fail(); keys.add(key); skip(); if (raw[pos++] !== ':') fail();
        read(path + '/' + key.replaceAll('~', '~0').replaceAll('/', '~1'), depth + 1);
        skip(); if (raw[pos] === '}') break; if (raw[pos++] !== ',') fail();
      }
      pos++;
    } else if (raw[pos] === '[') {
      pos++; skip(); let index = 0;
      if (raw[pos] !== ']') while (true) {
        read(path + '/' + index++, depth + 1); skip();
        if (raw[pos] === ']') break; if (raw[pos++] !== ',') fail();
      }
      pos++;
    } else if (raw[pos] === '"') string();
    else {
      const match = /^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(raw.slice(pos));
      if (!match) fail(); pos += match[0].length;
    }
    ranges.set(path, [start, pos]);
  }
  read('', 0); skip(); if (pos !== raw.length) fail();
  const at = path => {const r = ranges.get(path); return r ? raw.slice(...r) : undefined;};
  const value = path => {const token = at(path); return token === undefined ? undefined : JSON.parse(token);};
  return {raw, at, value};
}
async function readProposal(file, change) {
    if (file.size > 16 * 1024 * 1024) throw new Error('정리한 지식 파일은 16 MB 이하여야 합니다.');
  const bytes = await file.arrayBuffer(), expected = objectIndex.get(change.object_id);
  if (bytes.byteLength !== expected.byte_length || await digest(bytes) !== expected.byte_digest)
    throw new Error('로컬 파일이 확인할 묶음과 다릅니다.');
  const raw = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
  const doc = localDocument(raw);
  if (doc.value('/contract_version') !== 'boi/local-native-draft@1' ||
      !doc.at('/content')?.startsWith('{') || !doc.at('/draft')?.startsWith('{') ||
      ['namespace','logical_id','kind','title'].some(k => doc.value('/draft/' + k) !== change[k]))
    throw new Error('파일의 지식 식별 정보가 확인할 변경 목록과 다릅니다.');
  return doc;
}
function details(label, text) {
  const e = node('details'); e.append(node('summary', label), node('pre', text, 'review-json')); return e;
}
function contentPanel(parent, doc, prefix) {
  const version = doc.value(prefix + '/contract_version');
  const body = version === 'boi/knowledge-content@1' ? doc.value(prefix + '/document/body') : undefined;
  if (typeof body === 'string') parent.append(node('div', body, 'review-body'));
  else if (version === 'boi/knowledge-profile@1') {
    parent.append(node('p', doc.value(prefix + '/label')), node('p', doc.value(prefix + '/description')));
    parent.append(details('Profile 구성', doc.at(prefix + '/components') || '구성 없음'));
  } else parent.append(node('p', '이 형식의 본문은 아래 원본 JSON에서 확인할 수 있습니다.'));
  if (doc.value(prefix + '/meaning/contract_version') === 'boi/typed-knowledge-meaning@1') {
    const assertions = doc.value(prefix + '/meaning/assertions');
    const evidence = doc.value(prefix + '/evidence_bindings');
    if (Array.isArray(assertions)) {
      const byId = new Map(assertions.map(c => [c.id,c]));
      const byPointer = new Map();
      if (Array.isArray(evidence)) for (const item of evidence) {
        if (!byPointer.has(item.meaning_pointer)) byPointer.set(item.meaning_pointer, []);
        byPointer.get(item.meaning_pointer).push(item);
      }
      const group = node('details'); group.append(node('summary', `구조화한 주장 ${assertions.length}개 · 조건과 근거 보기`));
      assertions.forEach((claim, index) => {
        const article = node('article'); article.dataset.assertionId = claim.id;
        const labels = {positive:'긍정 주장',negative:'부정 주장',asserted:'원천 보고',intended:'목적',
          possible:'가능성',required:'요구사항'};
        article.append(node('small', [labels[claim.polarity] || claim.polarity,
          labels[claim.modality] || claim.modality].join(' · ')), node('p', claim.statement));
        for (const [key, label] of [['conditions','조건'],['exceptions','예외'],['applicability','적용 범위']]) {
          if (Array.isArray(claim[key])) for (const clause of claim[key]) {
            const p = node('p', label + ': ' + clause.statement); p.dataset.qualifier = key; article.append(p);
          }
        }
        if (Array.isArray(claim.depends_on)) for (const id of claim.depends_on)
          article.append(node('p', '함께 읽을 주장: ' + (byId.get(id)?.statement || id)));
        if (Array.isArray(claim.uncertainties)) for (const unknown of claim.uncertainties)
          article.append(node('p', unknown, 'warning'));
        if (claim.valid_time?.state === 'unknown') article.append(node('small', '적용 시점 미상'));
        const quotes = byPointer.get('/assertions/' + index) || [];
        if (quotes.length) {
          const sources = node('details'); sources.append(node('summary', '원문에 기록된 근거'));
          for (const q of quotes) sources.append(node('blockquote', q.quote), node('small', q.field_locator));
          article.append(sources);
        }
        group.append(article);
      });
      parent.append(group);
    }
  }
  const unresolved = doc.value(prefix + '/unresolved');
  if (Array.isArray(unresolved) && unresolved.length) {
    const unknowns = node('details'); unknowns.append(node('summary', `미상·미해결 내용 ${unresolved.length}개`));
    for (const item of unresolved) unknowns.append(node('p', item.description));
    parent.append(unknowns);
  }
  for (const [key, label] of [['/document/frontmatter','문서 메타데이터'],['/profiles','적용 Profile'],
    ['/meaning','구조화한 의미 · 조건·부정·예외 포함'],['/evidence_bindings','원문 인용과 근거 위치'],
    ['/body_bindings','본문과 의미의 연결'],['/unresolved','미상·미해결 내용'],['/extensions','확장 정보']]) {
    const text = doc.at(prefix + key); if (text !== undefined) parent.append(details(label, text));
  }
  parent.append(details('내용의 정확한 JSON', doc.at(prefix)));
}
async function showComparison() {
  reviewVerified = false; updateConfirmAvailability();
  const generation = ++renderGeneration, change = changeIndex.get(reviewSelect.value);
  const host = document.getElementById('review-content'); host.replaceChildren();
  const file = reviewFiles.get(change.object_id);
  if (!file) {host.append(node('p', '이 지식의 로컬 파일을 선택해 주세요.')); return;}
  host.append(node('p', '로컬 본문과 현재 개정을 읽고 있습니다.'));
  try {
    const doc = await readProposal(file, change);
    const url = '/api/v2/local-bundles/' + intent.bundle_ref.split(':').pop() + '/changes/' +
      encodeURIComponent(change.object_id) + '/baseline?preview_digest=' + encodeURIComponent(intent.preview_digest);
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
    const baseline = await response.json();
    if (!response.ok) throw new Error(baseline.detail?.reason_code || '현재 내용을 읽지 못했습니다.');
    if (baseline.preview_digest !== intent.preview_digest || baseline.manifest_digest !== intent.manifest_digest ||
        baseline.bundle_ref !== intent.bundle_ref || baseline.object_id !== change.object_id)
      throw new Error('LOCAL_BUNDLE_COMPARISON_BINDING_MISMATCH');
    if (generation !== renderGeneration) return;
    host.replaceChildren(node('h3', change.title));
    const columns = node('div', undefined, 'review-columns'), before = node('section'), after = node('section');
    before.append(node('h4', '현재 Wiki 내용')); after.append(node('h4', '로컬에서 준비한 내용'));
    if (baseline.current) {
      const current = localDocument(baseline.current.content_json);
      if (await digest(new TextEncoder().encode(baseline.current.content_json)) !== baseline.current.content_byte_digest)
        throw new Error('LOCAL_BUNDLE_COMPARISON_BINDING_MISMATCH');
      if (generation !== renderGeneration) return;
      before.append(node('p', baseline.current.title)); contentPanel(before, current, '');
      const oldBody = current.value('/document/body'), newBody = doc.value('/content/document/body');
      host.append(node('p', typeof oldBody === 'string' && typeof newBody === 'string' ?
        (oldBody === newBody ? '본문 텍스트가 같습니다. 메타데이터와 근거도 비교해 주세요.' : '본문 텍스트가 변경됩니다.') :
        '현재 내용과 준비한 내용을 나란히 비교해 주세요.'));
    } else before.append(node('p', '이 식별자로 등록된 현재 지식이 없습니다. 관련된 다른 지식의 부재를 뜻하지는 않습니다.'));
    contentPanel(after, doc, '/content'); columns.append(before, after); host.append(columns);
    const refs = referenceIndex.get(change.object_id) || [];
    const dependencies = refs.filter(r => r.kind === 'knowledge_revision');
    const names = new Map(reviewData.objects.map(o => [o.object_id, o.display_name]));
    const declared = node('div'); declared.append(node('h4', '이 파일에 선언된 연결'));
    const targets = [...new Set(dependencies.map(r => r.target_object_id))];
    declared.append(node('p', targets.length ? targets.map(id => changeIndex.get(id)?.title || names.get(id)).join(' · ') :
      '묶음 내부 지식으로 연결한 참조가 없습니다.'));
    declared.append(node('p', '선언된 참조이며, 의미 충돌이나 다른 지식으로 퍼지는 영향을 검사한 결과는 아닙니다.', 'warning'));
    for (const [key,label] of [['sources','원천 참조'],['dependencies','필요한 지식'],
      ['conflicts_with','충돌한다고 기록한 지식'],['supersedes','대체한다고 기록한 지식']]) {
      const text = doc.at('/draft/' + key); if (text !== undefined) declared.append(details(label, text));
    }
    const sourceRefs = refs.filter(r => r.kind !== 'knowledge_revision');
    declared.append(details('전송할 원천과 연결 위치', sourceRefs.map(r =>
      (names.get(r.target_object_id) || r.target_object_id) + (r.field_locator ? ' · ' + r.field_locator : '') + ' → ' + r.pointer).join('\n') || '선언 없음'));
    host.append(declared, details('선택한 파일의 정확한 JSON', doc.raw));
    host.dataset.objectId = change.object_id;
    reviewVerified = reviewData.changes.every(c => reviewFiles.has(c.object_id));
    updateConfirmAvailability();
  } catch (error) {
    if (generation !== renderGeneration) return;
    host.replaceChildren(node('p', '현재 비교를 완료하지 못했습니다. ' + error.message, 'warning'));
    confirmButton.disabled = true;
  }
}
reviewSelect.onchange = showComparison;
document.getElementById('files').addEventListener('change', async function() {
  const generation = ++reviewGeneration; ++renderGeneration;
  reviewFiles.clear(); reviewVerified = false; confirmButton.disabled = true;
  document.getElementById('review-content').replaceChildren();
  try {
    const files = await selectedBundleFiles(this), matched = new Map();
    if (generation !== reviewGeneration) return;
    for (const file of files) {
      if (file.size > 256 * 1024 * 1024) throw new Error('파일당 한도는 256 MB입니다.');
      reviewStatus.textContent = file.name + ' 파일을 로컬에서 대조하고 있습니다.';
      const hash = await digest(await file.arrayBuffer());
      if (generation !== reviewGeneration) return;
      const objects = reviewData.objects.filter(o => o.byte_digest === hash && o.byte_length === file.size);
      if (!objects.length) throw new Error(file.name + ': 준비한 묶음과 다른 파일입니다.');
      for (const obj of objects) {
        if (changeIndex.has(obj.object_id)) await readProposal(file, changeIndex.get(obj.object_id));
        if (generation !== reviewGeneration) return;
        matched.set(obj.object_id, file);
      }
    }
    for (const [id, file] of matched) reviewFiles.set(id, file);
    const available = reviewData.changes.filter(c => matched.has(c.object_id)).length;
    reviewStatus.textContent = `${reviewData.changes.length}개 지식 중 ${available}개 본문을 로컬에서 열 수 있습니다. ` +
      '파일 일치 확인이며 의미·사실 검증 결과는 아닙니다. 아직 전송하지 않았습니다.';
    await showComparison();
  } catch (error) {
    if (generation !== reviewGeneration) return;
    reviewFiles.clear(); reviewVerified = false; reviewStatus.textContent = error.message;
    document.getElementById('review-content').replaceChildren();
    confirmButton.disabled = true;
  }
});
