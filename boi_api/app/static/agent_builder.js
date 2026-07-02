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

  function renderPayload(title, payload) {
    if (!result) return;
    const details = document.createElement("details");
    details.open = true;
    details.className = "agent-builder-result-card";
    const summary = document.createElement("summary");
    summary.textContent = title;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    details.append(summary, pre);
    result.prepend(details);
  }

  function draftPayload() {
    const data = new FormData(form);
    return {
      title: String(data.get("title") || "").trim(),
      prompt: String(data.get("prompt") || "").trim(),
      scope: data.get("scope") || "private",
      urls: lines(data.get("urls")),
      git_repos: lines(data.get("git_repos")),
      mcp_servers: lines(data.get("mcp_servers")),
      skills: lines(data.get("skills")),
      files: fileNotes(data.get("files")),
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
    setStatus(status, "초안을 만들고 있습니다...", "loading");
    try {
      const payload = draftPayload();
      if (!payload.title || !payload.prompt) {
        throw new Error("Agent 이름과 요청 내용을 입력하세요.");
      }
      const created = await postJson("/api/agents/drafts", payload);
      currentDraft = created.draft;
      renderPayload("Agent 초안", created.draft);
      setStatus(status, `초안 생성 완료: ${created.draft.draft_id}`, "success");
    } catch (error) {
      setStatus(status, `실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  testButton?.addEventListener("click", async () => {
    if (!currentDraft) return;
    setButtons(true);
    setStatus(status, "GPT-5.5/Agents SDK 테스트 중...", "loading");
    try {
      const tested = await postJson(`/api/agents/drafts/${encodeURIComponent(currentDraft.draft_id)}/test`, {});
      currentDraft.last_test = tested.test;
      renderPayload("바로 테스트 결과", tested.test);
      const backend = tested.test.runtime_backend || "contract_only";
      setStatus(status, `테스트 완료: ${backend}`, "success");
    } catch (error) {
      setStatus(status, `테스트 실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  publishButton?.addEventListener("click", async () => {
    if (!currentDraft) return;
    const scope = form.querySelector('[name="scope"]')?.value || currentDraft.scope || "private";
    const confirmed = window.confirm(`${scope} 범위로 Agent를 저장/배포할까요?`);
    if (!confirmed) return;
    setButtons(true);
    setStatus(status, "Agent를 저장/배포하고 있습니다...", "loading");
    try {
      const published = await postJson(`/api/agents/drafts/${encodeURIComponent(currentDraft.draft_id)}/publish`, {
        scope,
        note: "Agent Builder UI publish",
        user_confirmed: true,
      });
      currentDraft = published.draft;
      renderPayload("저장/배포 결과", published.draft);
      setStatus(status, `${scope} 범위로 저장했습니다.`, "success");
    } catch (error) {
      setStatus(status, `배포 실패: ${error.message}`, "error");
    } finally {
      setButtons(false);
    }
  });

  sandboxForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const confirmed = window.confirm("Sandbox workspace에서 코드를 실행해 검증 artifact를 만들까요?");
    if (!confirmed) return;
    sandboxForm.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    setStatus(sandboxStatus, "Sandbox job 실행 중...", "loading");
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
      renderPayload("Sandbox 검증 결과", job.job);
      setStatus(sandboxStatus, `Sandbox 완료: ${job.job.status || job.job.state}`, "success");
    } catch (error) {
      setStatus(sandboxStatus, `Sandbox 실패: ${error.message}`, "error");
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
          `<span>OpenAI <strong>${payload.quota_state || "unchecked"}</strong></span>`
        );
      }
    } catch (_error) {
      // Health is informational; Builder APIs remain usable.
    }
  }

  loadHealth();
})();
