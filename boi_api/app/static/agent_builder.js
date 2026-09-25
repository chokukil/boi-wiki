(function () {
  const root = document.querySelector("[data-agent-builder]");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";

  const employeeId = root.dataset.employeeId || new URLSearchParams(window.location.search).get("employee_id") || "100001";
  const form = root.querySelector("[data-agent-builder-form]");
  const sandboxForm = root.querySelector("[data-agent-builder-sandbox-form]");
  const result = root.querySelector("[data-agent-builder-result]");
  const status = root.querySelector("[data-agent-builder-status]");
  const sandboxStatus = root.querySelector("[data-agent-sandbox-status]");
  const testButton = root.querySelector("[data-agent-builder-test]");
  const publishButton = root.querySelector("[data-agent-builder-publish]");
  let currentDraft = null;

  function apiUrl(path) {
    const url = new URL(path, window.location.origin);
    url.searchParams.set("employee_id", employeeId);
    return url.toString();
  }

  function setStatus(node, message, state) {
    if (!node) return;
    node.textContent = message;
    node.dataset.state = state || "info";
  }

  function lines(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function fileNotes(value) {
    return lines(value).map((line) => {
      const [name, ...rest] = line.split(/\s+-\s+/);
      return { name: name.trim(), note: rest.join(" - ").trim() };
    });
  }

  function checkedValues(name) {
    return Array.from(form.querySelectorAll(`input[name="${name}"]:checked`))
      .map((input) => input.value)
      .filter(Boolean);
  }

  function uniqueValues(values) {
    return Array.from(new Set((values || []).map((value) => String(value || "").trim()).filter(Boolean)));
  }

  async function postJson(path, body) {
    const response = await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function humanList(values, emptyText) {
    const list = Array.isArray(values) ? values.map((value) => String(value || "").trim()).filter(Boolean) : [];
    return list.length ? list.slice(0, 6).join(", ") : emptyText;
  }

  function skillCandidateText(values) {
    const list = Array.isArray(values) ? values : [];
    const names = list
      .map((item) => item && typeof item === "object" ? (item.title || item.name || item.description) : item)
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    return names.length ? names.slice(0, 4).join(", ") : "없음";
  }

  function skillDraftText(values) {
    const list = Array.isArray(values) ? values : [];
    const names = list
      .map((item) => item && typeof item === "object" ? (item.title || item.candidate_id) : item)
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    return names.length ? names.slice(0, 4).join(", ") : "없음";
  }

  function scopeLabel(value) {
    return {
      private: "나만 사용",
      team: "팀과 함께 사용",
      public: "전체 공개",
    }[String(value || "private")] || "나만 사용";
  }

  function renderPayload(title, payload) {
    if (!result) return;
    const data = payload && typeof payload === "object" ? payload : {};
    const card = document.createElement("article");
    card.className = "agent-builder-result-card";
    const heading = document.createElement("header");
    const headingText = document.createElement("strong");
    headingText.textContent = title;
    const state = document.createElement("span");
    state.className = "badge status";
    state.textContent = data.status || data.state || data.runtime_backend || "초안";
    heading.append(headingText, state);
    const summaryText = document.createElement("p");
    summaryText.textContent = data.summary || data.title || data.prompt || "BoI Agent 초안이 준비되었습니다.";
    const meta = document.createElement("div");
    meta.className = "agent-builder-result-meta";
    const rows = [
      ["쓸 곳", humanList(data.helper_surfaces, "선택 없음")],
      ["할 수 있는 일", humanList(data.capabilities, "선택 없음")],
      ["붙은 능력", humanList(data.skills || data.tool_boundary?.skills, "없음")],
      ["새 능력 후보", skillCandidateText(data.skill_candidates || data.tool_boundary?.skill_candidates)],
      ["능력 초안", skillDraftText(data.skill_candidate_drafts || data.skill_creator?.drafts)],
      ["연결", humanList(data.connection_presets || data.tool_boundary?.connection_presets || data.mcp_servers || data.tool_boundary?.mcp_servers, "기본 연결")],
    ];
    rows.forEach(([label, value]) => {
      const item = document.createElement("div");
      const key = document.createElement("span");
      key.textContent = label;
      const val = document.createElement("strong");
      val.textContent = value;
      item.append(key, val);
      meta.append(item);
    });
    const details = document.createElement("details");
    const detailSummary = document.createElement("summary");
    detailSummary.textContent = "진단 정보";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    details.append(detailSummary, pre);
    card.append(heading, summaryText, meta, details);
    result.prepend(card);
  }

  function draftPayload() {
    const data = new FormData(form);
    const connectionPresets = checkedValues("connection_presets");
    const presetMcpServers = [];
    if (connectionPresets.includes("boi_wiki")) presetMcpServers.push("boi-wiki-local");
    if (connectionPresets.includes("data_lake")) presetMcpServers.push("data-lake");
    const capabilities = checkedValues("capabilities");
    if (connectionPresets.includes("action_gateway")) capabilities.push("action_request");
    const selectedSkills = checkedValues("selected_skills");
    const manualSkills = lines(data.get("skills"));
    const skillTitle = String(data.get("new_skill_title") || "").trim();
    const skillDescription = String(data.get("new_skill_description") || "").trim();
    const skillCandidates = [];
    if (skillTitle || skillDescription) {
      skillCandidates.push({
        title: skillTitle || "새 능력 후보",
        description: skillDescription,
        source: "agent_builder",
        status: "candidate",
      });
    }
    const urls = lines(data.get("urls"));
    if (connectionPresets.includes("langflow") && root.dataset.langflowUrl) {
      urls.push(root.dataset.langflowUrl);
    }
    return {
      title: String(data.get("title") || "").trim(),
      prompt: String(data.get("prompt") || "").trim(),
      scope: data.get("scope") || "private",
      urls: uniqueValues(urls),
      git_repos: lines(data.get("git_repos")),
      mcp_servers: uniqueValues([...presetMcpServers, ...lines(data.get("mcp_servers"))]),
      skills: uniqueValues([...selectedSkills, ...manualSkills]),
      skill_candidates: skillCandidates,
      connection_presets: connectionPresets,
      files: fileNotes(data.get("files")),
      helper_surfaces: checkedValues("helper_surfaces"),
      capabilities: uniqueValues(capabilities),
      reference_sources: checkedValues("reference_sources"),
      use_cases: lines(data.get("use_cases")),
    };
  }

  function setButtons(disabled) {
    form.querySelectorAll("button").forEach((button) => {
      button.disabled = disabled || (button === testButton && !currentDraft) || (button === publishButton && !currentDraft);
    });
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setButtons(true);
    setStatus(status, "도우미 초안을 만들고 있습니다...", "loading");
    try {
      const payload = draftPayload();
      if (!payload.title || !payload.prompt) {
        throw new Error("도우미 이름과 요청 내용을 입력하세요.");
      }
      const created = await postJson("/api/agents/drafts", payload);
      currentDraft = created.draft;
      renderPayload("도우미 초안", created.draft);
      setStatus(status, `초안 생성 완료`, "success");
    } catch (error) {
      setStatus(status, `실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  testButton?.addEventListener("click", async () => {
    if (!currentDraft) return;
    setButtons(true);
    setStatus(status, "도우미를 먼저 시험해보고 있습니다...", "loading");
    try {
      const tested = await postJson(`/api/agents/drafts/${encodeURIComponent(currentDraft.draft_id)}/test`, {});
      currentDraft.last_test = tested.test;
      renderPayload("시험 결과", tested.test);
      setStatus(status, "시험 결과를 만들었습니다.", "success");
    } catch (error) {
      setStatus(status, `테스트 실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  publishButton?.addEventListener("click", async () => {
    if (!currentDraft) return;
    const scope = form.querySelector('[name="scope"]')?.value || currentDraft.scope || "private";
    const confirmed = window.confirm(`${scopeLabel(scope)} 범위로 도우미를 저장/배포할까요?`);
    if (!confirmed) return;
    setButtons(true);
    setStatus(status, "도우미를 저장/배포하고 있습니다...", "loading");
    try {
      const published = await postJson(`/api/agents/drafts/${encodeURIComponent(currentDraft.draft_id)}/publish`, {
        scope,
        note: "BoI Agent Builder 저장",
        user_confirmed: true,
      });
      currentDraft = published.draft;
      renderPayload("저장/배포 결과", published.draft);
      setStatus(status, `${scopeLabel(scope)} 범위로 저장했습니다.`, "success");
    } catch (error) {
      setStatus(status, `배포 실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  sandboxForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const confirmed = window.confirm("별도 작업공간에서 시험 근거를 만들어볼까요?");
    if (!confirmed) return;
    sandboxForm.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    setStatus(sandboxStatus, "시험 실행 중...", "loading");
    try {
      const data = new FormData(sandboxForm);
      const job = await postJson("/api/agents/sandbox/jobs", {
        title: String(data.get("title") || "").trim(),
        task: String(data.get("task") || "").trim(),
        code: String(data.get("code") || ""),
        language: "python",
        evidence_intent: "agent_builder_validation",
        user_confirmed: true,
      });
      renderPayload("시험 결과", job.job);
      setStatus(sandboxStatus, `시험 완료: ${job.job.status || job.job.state}`, "success");
    } catch (error) {
      setStatus(sandboxStatus, `시험 실패: ${error.message}`, "error");
    } finally {
      sandboxForm.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    }
  });

  async function loadHealth() {
    const healthUrl = root.dataset.openaiHealthUrl;
    if (!healthUrl) return;
    try {
      const response = await fetch(healthUrl);
      const payload = await response.json();
      const strip = root.querySelector("[data-agent-runtime]");
      if (strip && payload) {
        strip.insertAdjacentHTML(
          "beforeend",
          `<span>모델 상태 <strong>${payload.quota_state || "unchecked"}</strong></span>`
        );
      }
    } catch (_error) {
      // Health is informational; Builder APIs remain usable.
    }
  }

  loadHealth();
})();
