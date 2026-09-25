(function () {
  const root = document.querySelector("[data-helper-builder-v2]");
  if (!root) return;
  const configForm = root.querySelector("[data-helper-builder-form]");
  const previewForm = root.querySelector("[data-helper-preview-form]");
  const skillForm = root.querySelector("[data-helper-skill-form]");
  const elements = {
    save: root.querySelector("[data-helper-save-state]"),
    activate: root.querySelector("[data-helper-activate]"),
    templates: root.querySelector("[data-helper-templates]"),
    skillList: root.querySelector("[data-helper-skill-list]"),
    skillSearch: root.querySelector("[data-helper-skill-search]"),
    capabilities: root.querySelector("[data-helper-capabilities]"),
    previewTitle: root.querySelector("[data-helper-preview-title]"),
    previewStatus: root.querySelector("[data-helper-preview-status]"),
    previewMessages: root.querySelector("[data-helper-preview-messages]"),
    skillDrawer: root.querySelector("[data-helper-skill-drawer]"),
    skillBackdrop: root.querySelector("[data-helper-skill-backdrop]"),
    skillStatus: root.querySelector("[data-helper-skill-status]"),
    skillTestResults: root.querySelector("[data-helper-skill-test-results]"),
  };
  const params = new URLSearchParams(location.search);
  const state = {
    draft: null,
    bootstrap: null,
    skills: [],
    selectedSkills: new Set(),
    previewSessionId: "",
    saveTimer: null,
    hydrating: false,
    saving: false,
    dirty: false,
    skillCandidate: null,
  };

  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const checked = (name) => Array.from(configForm.querySelectorAll(`[name="${name}"]:checked`)).map((item) => item.value);

  function previewMarkdown(value) {
    let output = escapeHtml(value);
    output = output.replace(/^### (.+)$/gm, "<h4>$1</h4>").replace(/^## (.+)$/gm, "<h3>$1</h3>");
    output = output.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    output = output.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    output = output.replace(/^- (.+)$/gm, "<li>$1</li>").replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");
    return output.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
  }

  async function api(path, options) {
    const response = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...(options || {}) });
    let payload = {};
    try { payload = await response.json(); } catch (_error) { payload = {}; }
    if (!response.ok) {
      const detail = payload.detail || payload;
      const error = new Error(typeof detail === "string" ? detail : detail.message || detail.status || `HTTP ${response.status}`);
      error.status = response.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  function setDraftUrl(draftId) {
    const url = new URL(location.href);
    url.searchParams.set("draft", draftId);
    history.replaceState({}, "", url);
  }

  function setChecked(name, values) {
    const selected = new Set(values || []);
    configForm.querySelectorAll(`[name="${name}"]`).forEach((input) => { input.checked = selected.has(input.value); });
  }

  function hydrate(draft) {
    state.hydrating = true;
    state.draft = draft;
    configForm.elements.name.value = draft.name || "";
    configForm.elements.instructions.value = draft.instructions || "";
    setChecked("source_scopes", draft.source_scopes);
    setChecked("capability_ids", draft.capability_ids);
    setChecked("surfaces", draft.surfaces);
    setChecked("connector_refs", draft.connector_refs);
    state.selectedSkills = new Set(draft.skill_ids || []);
    elements.previewTitle.textContent = draft.name || "나만의 BoI Agent";
    elements.save.textContent = draft.status === "activated" ? "사용 중" : `자동 저장됨 · 버전 ${draft.revision}`;
    renderSkills(elements.skillSearch.value);
    state.dirty = false;
    previewForm.querySelector("button[type=submit]").disabled = false;
    elements.activate.disabled = draft.status === "activated";
    state.hydrating = false;
  }

  function draftPatch() {
    return {
      expected_revision: state.draft.revision,
      name: configForm.elements.name.value.trim(),
      instructions: configForm.elements.instructions.value.trim(),
      capability_ids: checked("capability_ids"),
      source_scopes: checked("source_scopes"),
      skill_ids: Array.from(state.selectedSkills),
      connector_refs: checked("connector_refs"),
      surfaces: checked("surfaces"),
      visibility: "private",
    };
  }

  function queueSave() {
    if (state.hydrating || !state.draft) return;
    elements.save.textContent = "저장 중...";
    state.dirty = true;
    elements.previewTitle.textContent = configForm.elements.name.value.trim() || "나만의 BoI Agent";
    clearTimeout(state.saveTimer);
    state.saveTimer = window.setTimeout(saveNow, 500);
  }

  async function saveNow() {
    if (!state.draft || state.saving || !state.dirty) return state.draft;
    clearTimeout(state.saveTimer);
    state.saving = true;
    try {
      state.draft = await api(`/api/v2/helper-drafts/${encodeURIComponent(state.draft.draft_id)}`, { method: "PATCH", body: JSON.stringify(draftPatch()) });
      state.dirty = false;
      elements.save.textContent = `자동 저장됨 · 버전 ${state.draft.revision}`;
      return state.draft;
    } catch (error) {
      if (error.status === 409 && error.detail?.helper) {
        state.draft = error.detail.helper;
        elements.save.textContent = "다른 화면의 변경을 반영했습니다. 다시 확인해주세요.";
      } else {
        elements.save.textContent = `저장하지 못했습니다 · ${error.message}`;
      }
      throw error;
    } finally { state.saving = false; }
  }

  async function createDraft(templateId) {
    const draft = await api("/api/v2/helper-drafts", { method: "POST", body: JSON.stringify({ template_id: templateId || "blank" }) });
    setDraftUrl(draft.draft_id);
    hydrate(draft);
    return draft;
  }

  function renderCapabilities() {
    elements.capabilities.innerHTML = "";
    (state.bootstrap?.capabilities || []).forEach((item) => {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" name="capability_ids" value="${escapeHtml(item.capability_id)}" ${item.state === "unavailable" ? "disabled" : ""}/><span>${escapeHtml(item.title)}</span>`;
      elements.capabilities.appendChild(label);
    });
  }

  function renderSkills(query) {
    const clean = String(query || "").trim().toLowerCase();
    const items = state.skills.filter((item) => !clean || `${item.title} ${item.description}`.toLowerCase().includes(clean));
    elements.skillList.innerHTML = "";
    if (!items.length) {
      elements.skillList.innerHTML = "<p>조건에 맞는 기존 Skill이 없습니다. 새 Skill 만들기로 후보를 만들 수 있습니다.</p>";
      return;
    }
    items.slice(0, 20).forEach((item) => {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" value="${escapeHtml(item.skill_id)}" ${state.selectedSkills.has(item.skill_id) ? "checked" : ""}/><span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.description || "검토된 업무 능력")}</small></span>`;
      label.querySelector("input").addEventListener("change", (event) => {
        if (event.target.checked) state.selectedSkills.add(item.skill_id);
        else state.selectedSkills.delete(item.skill_id);
        queueSave();
      });
      elements.skillList.appendChild(label);
    });
  }

  function clearPreviewEmpty() { elements.previewMessages.querySelector(".helper-preview-empty")?.remove(); }

  function addPreviewMessage(role, text, extras) {
    clearPreviewEmpty();
    const article = document.createElement("article");
    article.className = role;
    article.innerHTML = role === "user" ? escapeHtml(text) : `<div><p>${previewMarkdown(text)}</p></div>`;
    if (extras?.evidence?.length) {
      const evidence = document.createElement("div");
      evidence.className = "helper-preview-evidence";
      evidence.innerHTML = extras.evidence.slice(0, 5).map((item) => `<a href="${escapeHtml(item.url || "#")}">${escapeHtml(item.title)}</a>`).join("");
      article.appendChild(evidence);
    }
    if (extras?.artifact) article.appendChild(extras.artifact);
    elements.previewMessages.appendChild(article);
    elements.previewMessages.scrollTop = elements.previewMessages.scrollHeight;
  }

  async function artifactPreview(ref) {
    const artifact = await api(`/api/v2/artifacts/${encodeURIComponent(ref.artifact_id)}`);
    const section = document.createElement("section");
    section.className = "helper-preview-artifact";
    const tasks = artifact.draft?.tasks || [];
    section.innerHTML = `<span>private 초안</span><strong>${escapeHtml(artifact.title)}</strong>${tasks.length ? `<ol>${tasks.map((task) => `<li><b>${escapeHtml(task.name)}</b><small>${escapeHtml(task.purpose)}</small></li>`).join("")}</ol>` : `<p>${escapeHtml(artifact.draft?.summary || artifact.draft?.description || "검토할 초안이 준비되었습니다.")}</p>`}<a href="/agent?session=${encodeURIComponent(artifact.work_session_id || state.previewSessionId)}&artifact=${encodeURIComponent(artifact.artifact_id)}">작업공간에서 계속하기</a>`;
    return section;
  }

  async function previewTurn(event) {
    event.preventDefault();
    if (!state.draft) {
      elements.previewStatus.textContent = "초안을 준비하고 있습니다.";
      return;
    }
    const question = previewForm.elements.question.value.trim();
    if (!question) return;
    try { await saveNow(); } catch (_error) { return; }
    addPreviewMessage("user", question);
    previewForm.elements.question.value = "";
    previewForm.querySelector("button").disabled = true;
    elements.previewStatus.textContent = "시험 중";
    try {
      const payload = await api(`/api/v2/helper-drafts/${encodeURIComponent(state.draft.draft_id)}/preview-turns`, { method: "POST", body: JSON.stringify({ question, work_session_id: state.previewSessionId || null }) });
      state.previewSessionId = payload.work_session_id || state.previewSessionId;
      const artifact = payload.artifact_refs?.[0] ? await artifactPreview(payload.artifact_refs[0]) : null;
      addPreviewMessage("assistant", payload.answer?.markdown || payload.answer?.summary || "결과가 없습니다.", { evidence: payload.evidence_refs || [], artifact });
      elements.previewStatus.textContent = payload.status === "queued" ? "심층 작업 진행 중" : "시험 완료";
    } catch (error) {
      addPreviewMessage("assistant", `시험하지 못했습니다. ${error.message}`);
      elements.previewStatus.textContent = "확인 필요";
    } finally { previewForm.querySelector("button").disabled = false; }
  }

  function openSkillDrawer() {
    state.skillCandidate = null;
    elements.skillTestResults.hidden = true;
    elements.skillTestResults.innerHTML = "";
    elements.skillStatus.textContent = "후보를 만든 뒤 같은 자리에서 실제 결과를 시험합니다.";
    elements.skillDrawer.hidden = false;
    elements.skillBackdrop.hidden = false;
    skillForm.elements.title.focus();
  }
  function closeSkillDrawer() { elements.skillDrawer.hidden = true; elements.skillBackdrop.hidden = true; }

  async function createSkillCandidate(event) {
    event.preventDefault();
    const title = skillForm.elements.title.value.trim();
    const description = skillForm.elements.description.value.trim();
    const scenario = skillForm.elements.scenario.value.trim();
    const expectedContains = String(skillForm.elements.expected.value || "").split(/\n/).map((item) => item.trim()).filter(Boolean);
    elements.skillStatus.textContent = "Skill 후보를 만들고 있습니다.";
    elements.skillTestResults.hidden = true;
    skillForm.querySelector("button[type=submit]").disabled = true;
    try {
      const payload = await api("/api/v2/agent/turns", { method: "POST", body: JSON.stringify({
        question: `${title} Skill 후보를 만들어줘.\n\n${description}`,
        capability_id: "skill.plan",
        page_ref: "/helpers/new",
        work_session_id: state.previewSessionId || null,
      }) });
      state.previewSessionId = payload.work_session_id || state.previewSessionId;
      const artifact = payload.artifact_refs?.[0];
      if (!artifact) throw new Error("Skill 후보가 생성되지 않았습니다.");
      const fullArtifact = await api(`/api/v2/artifacts/${encodeURIComponent(artifact.artifact_id)}`);
      state.skillCandidate = fullArtifact;
      elements.skillStatus.textContent = "실제 시험 결과를 확인하고 있습니다.";
      const test = await api(`/api/v2/artifacts/${encodeURIComponent(artifact.artifact_id)}/skill-tests`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: fullArtifact.revision,
          scenario,
          sample_input: {},
          expected_contains: expectedContains,
        }),
      });
      elements.skillTestResults.hidden = false;
      elements.skillTestResults.innerHTML = `<strong>${test.status === "passed" ? "시험 통과" : "보완 필요"}</strong>${(test.checks || []).map((check) => `<p class="${check.passed ? "passed" : "failed"}"><span>${check.passed ? "확인" : "수정"}</span>${escapeHtml(check.message || check.check_id)}</p>`).join("")}`;
      if (test.status !== "passed") {
        elements.skillStatus.textContent = "시험에서 확인되지 않은 항목을 설명에 보완한 뒤 다시 만들어주세요.";
        return;
      }
      const activated = await api(`/api/v2/artifacts/${encodeURIComponent(artifact.artifact_id)}/skill-activate`, {
        method: "POST",
        body: JSON.stringify({expected_revision: fullArtifact.revision}),
      });
      state.skills.unshift(activated);
      state.selectedSkills.add(activated.skill_id);
      state.dirty = true;
      renderSkills(elements.skillSearch.value);
      await saveNow();
      elements.skillStatus.textContent = "시험을 통과한 Skill을 BoI Agent에 연결했습니다.";
      window.setTimeout(closeSkillDrawer, 1200);
    } catch (error) { elements.skillStatus.textContent = `만들지 못했습니다. ${error.message}`; }
    finally { skillForm.querySelector("button[type=submit]").disabled = false; }
  }

  async function activate() {
    try {
      await saveNow();
      const helper = await api(`/api/v2/helper-drafts/${encodeURIComponent(state.draft.draft_id)}/activate`, { method: "POST", body: JSON.stringify({ expected_revision: state.draft.revision }) });
      elements.save.textContent = "사용할 수 있는 BoI Agent로 저장했습니다.";
      elements.activate.textContent = "사용 중";
      elements.activate.disabled = true;
      elements.previewStatus.textContent = helper.name;
    } catch (error) { elements.save.textContent = `사용을 시작하지 못했습니다 · ${error.message}`; }
  }

  configForm.addEventListener("input", queueSave);
  configForm.addEventListener("change", queueSave);
  previewForm.addEventListener("submit", previewTurn);
  previewForm.elements.question.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); previewForm.requestSubmit(); } });
  elements.templates.addEventListener("click", (event) => { const id = event.target.closest("[data-template-id]")?.dataset.templateId; if (id) createDraft(id).catch((error) => { elements.save.textContent = error.message; }); });
  elements.skillSearch.addEventListener("input", () => renderSkills(elements.skillSearch.value));
  root.querySelector("[data-helper-new-skill]").addEventListener("click", openSkillDrawer);
  root.querySelector("[data-helper-skill-close]").addEventListener("click", closeSkillDrawer);
  elements.skillBackdrop.addEventListener("click", closeSkillDrawer);
  skillForm.addEventListener("submit", createSkillCandidate);
  elements.activate.addEventListener("click", activate);
  window.addEventListener("pagehide", () => { if (state.draft && state.dirty) fetch(`/api/v2/helper-drafts/${encodeURIComponent(state.draft.draft_id)}`, { method: "PATCH", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draftPatch()), keepalive: true }); });

  async function initialize() {
    try {
      const [bootstrap, skillPayload] = await Promise.all([api("/api/v2/bootstrap?page_ref=/helpers/new"), api("/api/v2/skills?limit=50")]);
      state.bootstrap = bootstrap;
      state.skills = skillPayload.items || [];
      renderCapabilities();
      const draftId = params.get("draft");
      const legacyDraftId = params.get("legacy_draft_id");
      let draft;
      if (draftId) draft = await api(`/api/v2/helper-drafts/${encodeURIComponent(draftId)}`);
      else if (legacyDraftId) {
        draft = await api("/api/v2/helper-drafts/import", {method: "POST", body: JSON.stringify({legacy_draft_id: legacyDraftId})});
        setDraftUrl(draft.draft_id);
        elements.save.textContent = "기존 BoI Agent 초안을 가져왔습니다.";
      } else draft = await createDraft("blank");
      hydrate(draft);
    } catch (error) {
      elements.save.textContent = `BoI Agent 초안을 열지 못했습니다 · ${error.message}`;
    }
  }
  initialize();
})();
