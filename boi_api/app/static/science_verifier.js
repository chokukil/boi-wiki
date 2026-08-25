(async () => {
  const root = document.querySelector("[data-science-review-canvas]");
  if (!root) return;
  const core = await import(root.dataset.scienceCoreUrl || "/static/science_verifier_core.mjs");
  let equationView = null;
  try {
    equationView = await import(root.dataset.scienceEquationViewUrl || "/static/science_equation_view.mjs");
  } catch {
    equationView = null;
  }
  let bootstrap = {};
  try { bootstrap = JSON.parse(document.querySelector("#science-verifier-bootstrap")?.textContent || "{}"); } catch { bootstrap = {}; }

  const storageKey = "boi.science.selection.v1";
  const documentForm = root.querySelector("[data-science-interpret-form]");
  const candidateSection = root.querySelector("[data-science-candidate-editor]");
  const candidateForm = root.querySelector("[data-science-candidate-form]");
  const input = documentForm?.elements?.document;
  const documentRefInput = documentForm?.elements?.document_ref;
  const status = root.querySelector("[data-science-status]");
  const aliasResults = root.querySelector("[data-science-alias-results]");
  const liveReview = root.querySelector("[data-science-live-review]");
  const liveDocument = root.querySelector("[data-science-live-document]");
  const liveClaims = root.querySelector("[data-science-live-claims]");
  const qwenButton = root.querySelector("[data-science-qwen-experimental]");
  const dialog = root.querySelector("[data-science-edit-dialog]");
  const dialogTitle = dialog?.querySelector("[data-science-dialog-title]");
  const dialogHelp = dialog?.querySelector("[data-science-dialog-help]");
  const dialogText = dialog?.querySelector("[data-science-dialog-text]");

  let pendingSelection = null;
  let claimSpan = null;
  let aliasMatches = [];
  let latestInterpretation = null;
  let supersedesClaimId = null;
  let sourceLineage = null;
  const reportsByClaim = new Map();
  const evidenceDetails = new Map();

  function endpoint(path) {
    const url = new URL(path, location.origin);
    url.searchParams.set("employee_id", String(bootstrap.employee_id || root.dataset.employeeId || ""));
    return `${url.pathname}${url.search}`;
  }

  function setStatus(message, kind = "") {
    if (!status) return;
    status.textContent = message;
    status.className = `science-form-status ${kind}`.trim();
  }

  async function requestJson(path, options = {}) {
    const response = await fetch(endpoint(path), {
      ...options,
      headers: { "content-type": "application/json", ...(options.headers || {}) },
    });
    let body = {};
    try { body = await response.json(); }
    catch {
      if (response.ok) throw new Error("Science API returned invalid JSON; no result was accepted.");
      body = {};
    }
    if (!response.ok) {
      const detail = body?.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || `HTTP ${response.status}`);
    }
    return body;
  }

  function appendText(parent, tag, value, className = "") {
    const node = document.createElement(tag);
    node.textContent = String(value ?? "");
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  }

  function codePointOffset(text, codeUnitOffset) {
    return core.codePointLength(String(text || "").slice(0, codeUnitOffset));
  }

  function anchorForRange(documentText, start, end) {
    const points = Array.from(documentText);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > points.length) return null;
    return {
      offset_encoding: "unicode_code_point",
      start,
      end,
      exact: points.slice(start, end).join(""),
      prefix: points.slice(Math.max(0, start - 64), start).join(""),
      suffix: points.slice(end, end + 64).join(""),
    };
  }

  function uniqueAnchor(documentText, exact) {
    const first = documentText.indexOf(exact);
    if (!exact || first < 0 || documentText.indexOf(exact, first + exact.length) >= 0) return null;
    const start = codePointOffset(documentText, first);
    return anchorForRange(documentText, start, start + core.codePointLength(exact));
  }

  function selectedAnchor() {
    const text = String(input?.value || "");
    if (!text.trim()) throw new Error("검토할 문서를 입력하세요.");
    if (pendingSelection) return pendingSelection;
    if (input.selectionEnd > input.selectionStart) {
      return anchorForRange(text, codePointOffset(text, input.selectionStart), codePointOffset(text, input.selectionEnd));
    }
    const startUnit = text.length - text.trimStart().length;
    const endUnit = text.trimEnd().length;
    return anchorForRange(text, codePointOffset(text, startUnit), codePointOffset(text, endUnit));
  }

  function sourcePayload(text) {
    const ref = String(documentRefInput?.value || "");
    return ref ? { document_ref: ref } : { document: text };
  }

  function hydrateWikiSelection() {
    if (!input || !documentRefInput?.value) return;
    let transfer = null;
    try { transfer = JSON.parse(sessionStorage.getItem(storageKey) || "null"); } catch { transfer = null; }
    if (!transfer || transfer.document_ref !== documentRefInput.value) return;
    pendingSelection = uniqueAnchor(input.value, String(transfer.exact || ""));
    sessionStorage.removeItem(storageKey);
    if (!pendingSelection) {
      setStatus("선택 문구를 원문에서 하나로 확정하지 못했습니다. 범위를 다시 선택하세요.", "warning");
      return;
    }
    const before = Array.from(input.value).slice(0, pendingSelection.start).join("");
    input.setSelectionRange(before.length, before.length + pendingSelection.exact.length);
    input.focus();
    setStatus("Wiki 선택 영역을 ACL 확인된 원문에서 다시 찾았습니다. 등록 용어 찾기를 시작하세요.", "ready");
  }

  function renderDocumentRanges(ranges) {
    if (!liveDocument || !input) return;
    liveDocument.replaceChildren();
    const points = Array.from(input.value);
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    for (const range of [...ranges].sort((a, b) => a.start - b.start || b.end - a.end)) {
      if (range.start < cursor || range.end > points.length) continue;
      fragment.appendChild(document.createTextNode(points.slice(cursor, range.start).join("")));
      const node = document.createElement(range.kind === "violation" ? "mark" : "span");
      node.textContent = points.slice(range.start, range.end).join("");
      node.className = range.kind === "violation" ? "science-violation" : range.kind === "ambiguity" ? "science-ambiguity" : "science-alias-match";
      if (range.claimId) node.dataset.claimId = range.claimId;
      if (range.ontologyRef) node.dataset.ontologyRef = range.ontologyRef;
      fragment.appendChild(node);
      cursor = range.end;
    }
    fragment.appendChild(document.createTextNode(points.slice(cursor).join("")));
    const body = document.createElement("p");
    body.className = "science-live-document-text";
    body.appendChild(fragment);
    liveDocument.appendChild(body);
  }

  function renderDocument() {
    if (!latestInterpretation) {
      renderDocumentRanges(aliasMatches.map((match) => ({ ...match, ontologyRef: match.ontology_ref })));
      return;
    }
    const impacts = new Map((latestInterpretation.decision_impact || []).map((item) => [item.claim_id, item]));
    const ranges = (latestInterpretation.candidate_claims || []).map((claim) => {
      const report = reportsByClaim.get(claim.claim_id);
      const impact = impacts.get(claim.claim_id);
      const outcomeAmbiguity = (claim.interpretation?.ambiguity_ids || []).length > 0 && impact?.outcome_impact === "unresolved";
      return { ...claim.source_span, claimId: claim.claim_id, kind: report?.trustedViolation ? "violation" : outcomeAmbiguity ? "ambiguity" : "" };
    });
    renderDocumentRanges(ranges);
  }

  function locatorText(locator = {}) {
    return [locator.section, locator.equation, locator.printed_page, locator.pdf_page_index !== undefined ? `PDF page ${Number(locator.pdf_page_index) + 1}` : null, locator.paragraph]
      .filter((value) => value !== undefined && value !== null && String(value).trim()).join(" / ");
  }

  function renderEvidence(card, state, claimId) {
    const annotations = state?.annotations || [];
    const equations = equationView?.resolveEquationAssets?.(state?.report, claimId) || [];
    const groundedBlocks = core.groundedExplanationBlocks(state?.report, claimId);
    const equationLinks = equationView?.equationEvidenceLinks?.(equations) || [];
    const links = [...new Map([
      ...annotations.flatMap((item) => item.evidence_links || []),
      ...equationLinks,
    ].map((link) => [link.evidence_id, link])).values()].slice(0, 2);
    if (!links.length && !equations.length && !groundedBlocks.length) return;
    if (links.length) {
      const sourceLine = document.createElement("p");
      sourceLine.className = "science-source-line";
      appendText(sourceLine, "strong", "핵심 근거");
      for (const link of links) {
        const anchor = document.createElement("a");
        anchor.href = link.url;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        anchor.textContent = link.source_id;
        sourceLine.appendChild(anchor);
      }
      card.appendChild(sourceLine);
    }
    const details = document.createElement("details");
    details.className = "science-evidence-details";
    appendText(details, "summary", "과학적 설명과 원문 근거 펼쳐보기");
    const explanation = document.createElement("section");
    explanation.className = "science-explanation";
    appendText(explanation, "h3", "과학적 설명");
    if (groundedBlocks.length) {
      appendText(
        explanation,
        "p",
        "활성 Release의 검토된 Knowledge·Rule·Evidence에서 구성한 설명입니다. 이 표시 문구는 판정 입력을 바꾸지 않습니다.",
        "science-explanation-origin",
      );
      core.appendGroundedExplanationBlocks(explanation, state?.report, claimId, {
        excludedTexts: [state?.verdict?.corrected_claim, ...(state?.verdict?.limitations || [])],
      });
    } else {
      for (const annotation of annotations) appendText(explanation, "p", annotation.text);
    }
    if (equations.length) {
      const equationHost = document.createElement("div");
      equationHost.className = "science-equation-host";
      explanation.appendChild(equationHost);
      void equationView.mountResolvedEquationAssets(equationHost, equations);
    }
    details.appendChild(explanation);
    const list = document.createElement("dl");
    for (const link of links) {
      const evidence = evidenceDetails.get(link.evidence_id) || {};
      for (const [term, value] of [
        ["Evidence", link.evidence_id], ["원문", evidence.original_text || "상세 Evidence를 불러오지 못했습니다."],
        ["검토 번역", evidence.reviewed_translation || "검토된 번역 없음"], ["원문 위치", locatorText(link.locator)], ["Evidence hash", link.evidence_digest],
      ]) {
        const row = document.createElement("div"); appendText(row, "dt", term); appendText(row, "dd", value); list.appendChild(row);
      }
      const row = document.createElement("div"); appendText(row, "dt", "Source URL");
      const dd = document.createElement("dd"); const url = document.createElement("a");
      url.href = link.url; url.target = "_blank"; url.rel = "noopener noreferrer"; url.textContent = link.url;
      dd.appendChild(url); row.appendChild(dd); list.appendChild(row);
    }
    details.appendChild(list); card.appendChild(details);
  }

  function renderClaims(record) {
    if (!liveClaims) return;
    liveClaims.replaceChildren();
    const impacts = new Map((record.decision_impact || []).map((item) => [item.claim_id, item]));
    for (const claim of record.candidate_claims || []) {
      const impact = impacts.get(claim.claim_id);
      const state = reportsByClaim.get(claim.claim_id);
      const verdict = state?.verdict;
      const ambiguity = (claim.interpretation?.ambiguity_ids || []).length > 0 && impact?.outcome_impact === "unresolved";
      const card = document.createElement("article");
      card.className = `science-correction-card ${state?.trustedViolation ? "violation" : ambiguity ? "ambiguity" : "interpretation"}`;
      const header = document.createElement("header");
      appendText(header, "span", verdict?.verdict || (ambiguity ? "해석 확인 필요" : "해석 후보"), `science-verdict ${state?.trustedViolation ? "violation" : ambiguity ? "ambiguity" : "neutral"}`);
      appendText(header, "small", claim.claim_id); card.appendChild(header);
      appendText(card, "p", claim.source_span?.exact || "", "science-claim-text");
      const normalized = claim.normalized_claim || {};
      const assertedContext = [
        ...(normalized.conditions || []).map((item) => `${item.condition_id}=${item.value}${item.unit ? ` ${item.unit}` : ""}`),
        ...(normalized.process_stage ? [`process_stage=${normalized.process_stage}`] : []),
        ...(normalized.material_state ? [`material_state=${normalized.material_state}`] : []),
        ...(normalized.quantities || []).map((item) => `${item.quantity_kind}=${item.value} ${item.unit}`),
      ];
      appendText(
        card,
        "p",
        assertedContext.length
          ? `사용자 확인 대상 조건: ${assertedContext.join(" · ")}`
          : "사용자가 주장한 적용 조건 없음 — Rule에 조건이 필요하면 판정을 보류합니다.",
        "science-asserted-context",
      );
      if (verdict) {
        appendText(card, "h3", "판정과 적용 조건");
        appendText(card, "p", (verdict.condition_evaluations || []).length ? verdict.condition_evaluations.map((item) => `${item.condition_id}: ${item.satisfied ? "충족" : "미충족"}`).join(" · ") : "적용 조건이 확인되지 않아 빨간 표시를 만들지 않습니다.");
        if (verdict.corrected_claim) appendText(card, "p", verdict.corrected_claim, "science-corrected-claim");
        for (const limitation of verdict.limitations || []) appendText(card, "p", limitation, "science-limitation");
        renderEvidence(card, state, claim.claim_id);
      } else {
        appendText(card, "p", `해석 참조: ${(claim.interpretation?.ontology_refs || []).join(", ") || "확정되지 않음"}`, "science-ontology-summary");
        if (!claim.interpretation?.user_confirmed && impact?.issue_codes?.length) appendText(card, "p", `확인 필요: ${impact.issue_codes.join(", ")}`, "science-issue-codes");
        appendText(card, "p", "온톨로지는 용어 해석과 지식 탐색에만 사용되며 판정 방향을 만들지 않습니다.");
      }
      const actions = document.createElement("div"); actions.className = "science-card-actions";
      const revise = document.createElement("button"); revise.type = "button"; revise.className = "secondary-button"; revise.dataset.scienceLocalEdit = ""; revise.dataset.claimText = claim.source_span?.exact || ""; revise.textContent = "이번 검증에서만 수정";
      const propose = document.createElement("button"); propose.type = "button"; propose.className = "secondary-button"; propose.dataset.scienceProposal = ""; propose.dataset.claimText = claim.source_span?.exact || ""; propose.textContent = "전역 용어 개선 제안";
      actions.append(revise, propose); card.appendChild(actions); liveClaims.appendChild(card);
    }
  }

  function renderInterpretation(record) {
    latestInterpretation = record;
    if (liveReview) liveReview.hidden = false;
    renderDocument(); renderClaims(record);
  }

  function renderAliases(record) {
    const points = Array.from(input.value);
    aliasMatches = (record.matches || []).filter((match) => Number.isInteger(match.start) && Number.isInteger(match.end) && points.slice(match.start, match.end).join("") === match.surface_term);
    latestInterpretation = null; reportsByClaim.clear(); renderDocument();
    if (liveReview) liveReview.hidden = false;
    if (liveClaims) { liveClaims.replaceChildren(); const card = document.createElement("article"); card.className = "science-correction-card interpretation"; appendText(card, "h3", "등록 용어 탐지"); appendText(card, "p", `${aliasMatches.length}개의 일치 구간을 찾았습니다. 이 표시는 판정이 아닙니다.`); liveClaims.appendChild(card); }
    if (aliasResults) { aliasResults.replaceChildren(); aliasMatches.forEach((match, index) => { const chip = appendText(aliasResults, "span", `${match.surface_term} → ${match.concept_id}`, "science-alias-chip"); chip.title = `${match.ontology_ref} · ${match.meaning}`; chip.dataset.matchIndex = String(index); }); }
    for (const role of ["subject", "relation", "object"]) {
      const select = candidateForm?.elements?.[`${role}_match`]; if (!select) continue;
      select.replaceChildren(new Option("선택하세요", "")); aliasMatches.forEach((match, index) => select.add(new Option(`${match.surface_term} — ${match.concept_id}`, String(index))));
    }
    if (candidateSection) candidateSection.hidden = false;
  }

  async function detectAliases() {
    const text = String(input?.value || "");
    claimSpan = selectedAnchor();
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStatus("등록된 별칭을 결정적으로 찾고 있습니다. 외부 LLM을 호출하지 않습니다.", "working");
    const record = await requestJson("/api/science/aliases/detect", { method: "POST", body: JSON.stringify({ ...sourcePayload(text), selection: claimSpan, request_id: `science-alias-${nonce}` }) });
    renderAliases(record);
    setStatus("등록 용어를 찾았습니다. 표시된 개념은 과학적 판정이 아니며, 주장 역할을 직접 확인해야 합니다.", "ready");
  }

  function currentCandidate() {
    if (!claimSpan) throw new Error("등록 용어 찾기를 먼저 실행하세요.");
    return core.buildManualCandidate({
      documentText: input.value, claimStart: claimSpan.start, claimEnd: claimSpan.end, matches: aliasMatches,
      selected: { subject: Number(candidateForm.elements.subject_match.value), relation: Number(candidateForm.elements.relation_match.value), object: Number(candidateForm.elements.object_match.value) },
      relationKind: candidateForm.elements.relation_kind.value, polarity: candidateForm.elements.polarity.value,
      conditionsText: candidateForm.elements.conditions.value, processStage: candidateForm.elements.process_stage.value, materialState: candidateForm.elements.material_state.value,
    });
  }

  async function fetchEvidence(report) {
    const ids = [...new Set((report.annotations || []).flatMap((item) => (item.evidence_links || []).map((link) => link.evidence_id)))];
    await Promise.all(ids.map(async (id) => { try { evidenceDetails.set(id, await requestJson(`/api/science/evidence/${encodeURIComponent(id)}`)); } catch { evidenceDetails.delete(id); } }));
  }

  async function confirmAndVerify(record, claim) {
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStatus("사용자가 확인한 해석을 불변 기록으로 고정하고 있습니다.", "working");
    const confirmationRequest = { claim_ids: [claim.claim_id], idempotency_key: `science-confirm-${nonce}` };
    const confirmationChallenge = await requestJson(`/api/science/interpretations/${encodeURIComponent(record.interpretation_id)}/confirmation-challenge`, { method: "POST", body: JSON.stringify(confirmationRequest) });
    const confirmed = await requestJson(`/api/science/interpretations/${encodeURIComponent(record.interpretation_id)}/confirm`, { method: "POST", body: JSON.stringify({ ...confirmationRequest, challenge_id: confirmationChallenge.challenge_id }) });
    latestInterpretation = confirmed;
    if (!bootstrap.operational) {
      renderInterpretation(confirmed);
      setStatus("해석은 확인했지만 Admin 승인과 독립 holdout을 통과한 활성 Science Release가 없어 판정을 실행하지 않았습니다.", "warning");
      return;
    }
    const report = await requestJson("/api/science/verify-document", { method: "POST", body: JSON.stringify({ interpretation_id: confirmed.interpretation_id, release_selection: { foundation: bootstrap.release_id, domains: [], applications: [] }, idempotency_key: `science-report-${nonce}` }) });
    await fetchEvidence(report);
    for (const verdict of report.verdict_packets || []) {
      const annotations = (report.annotations || []).filter((item) => item.claim_id === verdict.claim_id);
      const evidenceReadable = (verdict.evidence_refs || []).every((id) => evidenceDetails.has(id));
      reportsByClaim.set(verdict.claim_id, { verdict, annotations, report, trustedViolation: evidenceReadable && core.trustedViolationState(verdict, annotations, bootstrap.operational === true) });
    }
    renderInterpretation(confirmed);
    const verdict = report.verdict_packets?.find((item) => item.claim_id === claim.claim_id);
    setStatus(`활성 Release의 결정적 판정: ${verdict?.verdict || "판정 보류"}`, verdict?.verdict === "VIOLATION" ? "error" : "ready");
  }

  async function submitManualCandidate() {
    const text = String(input?.value || "");
    const candidate = currentCandidate();
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStatus("확정한 Claim 후보의 원문 구간·별칭·ontology_ref·개념 역할을 서버가 다시 검증하고 있습니다.", "working");
    reportsByClaim.clear();
    const revision = core.revisionPayload(supersedesClaimId, sourceLineage);
    const userRevisionRequest = { ...sourcePayload(text), candidate, ...revision, idempotency_key: `science-user-claim-${nonce}` };
    const userRevisionChallenge = await requestJson("/api/science/user-revisions/challenge", { method: "POST", body: JSON.stringify(userRevisionRequest) });
    const record = await requestJson("/api/science/user-revisions/commit", { method: "POST", body: JSON.stringify({ ...userRevisionRequest, challenge_id: userRevisionChallenge.challenge_id }) });
    renderInterpretation(record);
    const claim = record.candidate_claims?.[0];
    const impact = record.decision_impact?.find((item) => item.claim_id === claim?.claim_id);
    if (claim) {
      supersedesClaimId = claim.claim_id;
      sourceLineage = core.sourceDocumentLineage(record);
    }
    if (!claim || impact?.status !== "requires_user_confirmation" || impact.issue_codes?.some((code) => code !== "USER_CONFIRMATION_REQUIRED")) {
      setStatus("서버 교차 검증에서 주장 해석을 확정하지 못했습니다. 해당 주장만 수정하세요. 빨간 표시나 판정은 만들지 않았습니다.", "warning");
      return;
    }
    await confirmAndVerify(record, claim);
  }

  async function experimentalQwen() {
    const text = String(input?.value || ""); if (!text.trim()) throw new Error("검토할 문서를 입력하세요.");
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStatus("선택적·실험적 Qwen 어댑터에 해석 후보만 요청합니다. 응답은 판정·Rule·Evidence로 신뢰하지 않습니다.", "working");
    reportsByClaim.clear();
    try {
      const payload = { ...sourcePayload(text), request_id: `science-qwen-${nonce}`, idempotency_key: `science-qwen-${nonce}`, ...(pendingSelection ? { selection: pendingSelection } : {}) };
      renderInterpretation(await requestJson("/api/science/interpret", { method: "POST", body: JSON.stringify(payload) }));
      setStatus("Qwen이 제출한 해석 후보입니다. 서버 교차 검증과 사용자 확인 전에는 판정하지 않습니다.", "warning");
    } catch {
      reportsByClaim.clear(); latestInterpretation = null; renderDocument();
      setStatus("Qwen 해석을 사용할 수 없습니다. 판정과 빨간 표시를 만들지 않았으며, 등록 용어 찾기와 사용자 Claim 경로를 계속 사용할 수 있습니다.", "warning");
    }
  }

  function openDialog(mode, text) {
    if (!dialog || !dialogText) return;
    dialog.dataset.mode = mode; dialogText.value = text;
    dialogTitle.textContent = mode === "proposal" ? "전역 용어 개선 제안" : "이번 검증에서만 수정";
    dialogHelp.textContent = mode === "proposal" ? "제안은 전역 지식을 바로 바꾸지 않습니다. Power User 또는 Admin의 별도 채택 전에는 반영되지 않습니다." : "수정은 현재 검증에만 적용하고 이 주장만 다시 탐지합니다.";
    dialog.showModal();
  }

  function canonicalJson(value) {
    if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
    if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
    return JSON.stringify(value);
  }

  async function digest(value) {
    const bytes = new TextEncoder().encode(canonicalJson(value));
    const hashed = await crypto.subtle.digest("SHA-256", bytes);
    return `sha256:${[...new Uint8Array(hashed)].map((item) => item.toString(16).padStart(2, "0")).join("")}`;
  }

  async function submitProposal(text) {
    const match = aliasMatches[Number(candidateForm?.elements?.subject_match?.value)] || aliasMatches[0];
    if (!match) throw new Error("제안과 연결할 등록 용어를 먼저 찾으세요.");
    const domain = String(match.domain || "common").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-|-$/g, "") || "common";
    const proposal = { domain, kind: "term_alias", payload: { proposed_alias: text, original_surface_term: match.surface_term, ontology_ref: match.ontology_ref, concept_id: match.concept_id, source_interpretation_id: latestInterpretation?.interpretation_id || null } };
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    await requestJson("/api/science/proposals", { method: "POST", body: JSON.stringify({ proposal, request_digest: await digest(proposal), idempotency_key: `science-proposal-${nonce}`, user_confirmed: true }) });
    setStatus("전역 용어 개선 제안을 별도 검토 대상으로 저장했습니다. Power User 또는 Admin이 채택하기 전에는 전역 지식이 바뀌지 않습니다.", "ready");
  }

  async function applyLocalRevision(text) {
    if (!claimSpan) throw new Error("수정할 주장 구간이 없습니다.");
    const points = Array.from(input.value);
    input.value = `${points.slice(0, claimSpan.start).join("")}${text}${points.slice(claimSpan.end).join("")}`;
    if (documentRefInput) documentRefInput.value = "";
    claimSpan = anchorForRange(input.value, claimSpan.start, claimSpan.start + core.codePointLength(text)); pendingSelection = claimSpan;
    latestInterpretation = null; reportsByClaim.clear(); await detectAliases();
    setStatus("수정한 주장 하나에서 등록 용어를 다시 찾았습니다. 역할과 조건을 확인해 재검증하세요.", "ready");
  }

  documentForm?.addEventListener("submit", async (event) => { event.preventDefault(); try { await detectAliases(); } catch (error) { setStatus(error.message || "등록 용어 탐지에 실패했습니다.", "error"); } });
  candidateForm?.addEventListener("submit", async (event) => { event.preventDefault(); try { await submitManualCandidate(); } catch (error) { setStatus(error.message || "Claim 후보 제출에 실패했습니다.", "error"); } });
  qwenButton?.addEventListener("click", experimentalQwen);
  root.addEventListener("click", (event) => {
    const local = event.target.closest("[data-science-local-edit], [data-science-reinterpret]"); if (local) openDialog("local", local.dataset.claimText || claimSpan?.exact || "");
    const proposal = event.target.closest("[data-science-proposal]"); if (proposal) openDialog("proposal", proposal.dataset.claimText || claimSpan?.exact || "");
  });
  dialog?.addEventListener("close", async () => {
    if (dialog.returnValue !== "apply" || !dialogText?.value.trim()) return;
    try { if (dialog.dataset.mode === "proposal") await submitProposal(dialogText.value.trim()); else await applyLocalRevision(dialogText.value.trim()); }
    catch (error) { setStatus(error.message || "작업을 적용하지 못했습니다.", "error"); }
  });
  hydrateWikiSelection();
})().catch((error) => {
  const status = document.querySelector("[data-science-status]");
  if (status) { status.textContent = `Science Verifier 클라이언트를 시작하지 못했습니다: ${error.message || "알 수 없는 오류"}`; status.className = "science-form-status error"; }
});
