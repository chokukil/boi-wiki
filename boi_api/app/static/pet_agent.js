(function () {
  const root = document.getElementById("boi-agent-root");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";

  const employeeId = root.dataset.employeeId || new URLSearchParams(location.search).get("employee_id") || "100001";
  const pageTitle = root.dataset.pageTitle || document.title || "BoI Wiki";
  const storageKey = `boiAgent.v2.${employeeId}`;

  function currentUrl() {
    return root.dataset.currentUrl || `${location.pathname}${location.search}`;
  }

  function defaultState() {
    return { open: false, tab: "agent", suggestions: [], inbox: [], messages: [], draft: "", busyTask: "" };
  }

  function loadState() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
      return { ...defaultState(), ...saved, suggestions: [], inbox: [], busyTask: "" };
    } catch (_error) {
      return defaultState();
    }
  }

  const state = loadState();

  function persistState() {
    const saved = {
      open: state.open,
      tab: state.tab,
      messages: state.messages.slice(-12),
      draft: state.draft,
    };
    sessionStorage.setItem(storageKey, JSON.stringify(saved));
  }

  function syncViewportPosition() {
    const visual = window.visualViewport;
    if (!visual) return;
    const hiddenRight = Math.max(0, window.innerWidth - visual.width - visual.offsetLeft);
    const hiddenBottom = Math.max(0, window.innerHeight - visual.height - visual.offsetTop);
    if (hiddenRight > 1 || hiddenBottom > 1) {
      root.style.setProperty("--boi-agent-right", `${hiddenRight + 12}px`);
      root.style.setProperty("--boi-agent-bottom", `${hiddenBottom + 12}px`);
    } else {
      root.style.removeProperty("--boi-agent-right");
      root.style.removeProperty("--boi-agent-bottom");
    }
  }

  function api(path, options) {
    const url = new URL(path, location.origin);
    url.searchParams.set("employee_id", employeeId);
    return fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    });
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderMarkdownLite(value) {
    return escapeHtml(value)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/^- (.*)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
      .replace(/\n{2,}/g, "</p><p>")
      .replace(/\n/g, "<br>");
  }

  function renderLinks(links) {
    if (!links || !links.length) return "";
    return `<div class="boi-agent-links">${links
      .filter((item) => item.url)
      .map((item) => `<a href="${escapeHtml(item.url)}">${escapeHtml(item.label || item.url)}</a>`)
      .join("")}</div>`;
  }

  function tabLabel(tab) {
    return { agent: "Agent", inbox: "Inbox" }[tab] || tab;
  }

  function renderMessages() {
    if (!state.messages.length) return "";
    return `<div class="boi-agent-messages">${state.messages
      .map((message) => `
        <article class="boi-agent-message ${message.role === "user" ? "user" : "assistant"}">
          <strong>${message.role === "user" ? "You" : "BoI Agent"}</strong>
          <p>${renderMarkdownLite(message.text || "")}</p>
          ${renderLinks(message.links || [])}
        </article>`)
      .join("")}</div>`;
  }

  function render() {
    syncViewportPosition();
    persistState();
    root.innerHTML = `
      <button class="boi-agent-launcher" type="button" aria-expanded="${state.open ? "true" : "false"}">
        <span class="boi-agent-launcher-copy">
          <span>BoI Agent</span>
          <small>${state.inbox.length ? `${state.inbox.length}개 Action` : "무엇을 도와드릴까요"}</small>
        </span>
        <img class="boi-agent-pet" src="/static/assets/boi-agent-pet.png" alt="" loading="lazy" decoding="async">
        ${state.inbox.length ? `<strong aria-label="Open action count">${state.inbox.length}</strong>` : ""}
      </button>
      <section class="boi-agent-panel ${state.open ? "open" : ""}" aria-label="BoI Agent">
        <header>
          <div class="boi-agent-header-main">
            <img class="boi-agent-pet small" src="/static/assets/boi-agent-pet.png" alt="" loading="lazy" decoding="async">
            <div>
              <h2>BoI Agent</h2>
              <p>${escapeHtml(pageTitle)}</p>
            </div>
          </div>
          <button type="button" class="boi-agent-close" aria-label="Close">×</button>
        </header>
        <nav class="boi-agent-tabs" aria-label="BoI Agent tabs">
          ${["agent", "inbox"].map((tab) => `<button type="button" data-tab="${tab}" class="${state.tab === tab ? "active" : ""}">${tabLabel(tab)}</button>`).join("")}
        </nav>
        <div class="boi-agent-content">${renderTab()}</div>
      </section>
    `;
    bind();
  }

  function renderTab() {
    if (state.tab === "inbox") {
      if (!state.inbox.length) return `<div class="boi-agent-empty">현재 처리할 Action이 없습니다.</div>`;
      return `<div class="boi-agent-list">${state.inbox
        .map((item) => {
          const isManual = ["manual_required", "manual_blocked", "needs_followup"].includes(item.status || "");
          return `
          <article class="boi-agent-task">
            <strong>${escapeHtml(item.action_key || item.status)}</strong>
            <p>${escapeHtml(item.summary || item.status)}</p>
            <dl>
              ${item.status ? `<div><dt>상태</dt><dd>${escapeHtml(item.status)}</dd></div>` : ""}
              ${item.request_id ? `<div><dt>요청</dt><dd>${escapeHtml(item.request_id)}</dd></div>` : ""}
              ${item.trace_id ? `<div><dt>Trace</dt><dd>${escapeHtml(item.trace_id)}</dd></div>` : ""}
            </dl>
            <div class="boi-agent-links">
              ${item.workflow_url ? `<a href="${escapeHtml(item.workflow_url)}">Workflow</a>` : ""}
              ${item.raw_url ? `<a href="${escapeHtml(item.raw_url)}">Raw</a>` : ""}
            </div>
            ${isManual ? `
              <form class="boi-agent-handoff-form" data-task-id="${escapeHtml(item.task_id || "")}">
                <label>
                  <span>조치 결과</span>
                  <select name="outcome">
                    <option value="completed">완료</option>
                    <option value="not_needed">필요 없음</option>
                    <option value="blocked">보류</option>
                  </select>
                </label>
                <label>
                  <span>조치 내용</span>
                  <textarea name="note" placeholder="수행한 확인, 판단, 조치 내용을 남겨주세요." required></textarea>
                </label>
                <button type="submit" ${state.busyTask === item.task_id ? "disabled" : ""}>완료 기록</button>
              </form>` : `<p class="boi-agent-hint">고위험 승인 요청은 Workflow/Raw를 확인한 뒤 명시 승인 절차로 처리합니다.</p>`}
          </article>`;
        })
        .join("")}</div>`;
    }
    return `
      <section class="boi-agent-context-card">
        <strong>현재 페이지를 보고 있습니다</strong>
        <p>${escapeHtml(pageTitle)}</p>
      </section>
      <div class="boi-agent-suggestions">
        ${state.suggestions.map((item) => `<button type="button" data-question="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}
      </div>
      ${renderMessages()}
      <form class="boi-agent-chat-form">
        <textarea name="question" placeholder="현재 페이지 기준으로 묻거나, SOP/Event/Action을 찾아보세요." required>${escapeHtml(state.draft)}</textarea>
        <button type="submit">Agent에게 묻기</button>
      </form>
      <p class="boi-agent-hint">Enter로 전송, Shift+Enter로 줄바꿈</p>
    `;
  }

  function bind() {
    root.querySelector(".boi-agent-launcher")?.addEventListener("click", () => {
      state.open = !state.open;
      render();
    });
    root.querySelector(".boi-agent-close")?.addEventListener("click", () => {
      state.open = false;
      render();
    });
    root.querySelectorAll(".boi-agent-tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        state.tab = button.dataset.tab || "agent";
        render();
      });
    });
    root.querySelectorAll("[data-question]").forEach((button) => {
      button.addEventListener("click", () => ask(button.dataset.question || ""));
    });
    const form = root.querySelector(".boi-agent-chat-form");
    const textarea = form?.querySelector("textarea");
    textarea?.addEventListener("input", (event) => {
      state.draft = event.currentTarget.value;
      persistState();
    });
    textarea?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        form?.requestSubmit();
      }
    });
    form?.addEventListener("submit", (event) => {
      event.preventDefault();
      const question = new FormData(event.currentTarget).get("question");
      ask(String(question || ""));
    });
    root.querySelectorAll(".boi-agent-handoff-form").forEach((handoffForm) => {
      handoffForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const target = event.currentTarget;
        const taskId = target.dataset.taskId || "";
        const data = Object.fromEntries(new FormData(target).entries());
        state.busyTask = taskId;
        render();
        api("/api/agents/boi-wiki/manual-handoffs/complete", {
          method: "POST",
          body: JSON.stringify({
            task_id: taskId,
            outcome: data.outcome || "completed",
            note: data.note,
            user_confirmed: true,
          }),
        }).then(() => refreshInbox("Manual Handoff 완료 기록을 남겼습니다."))
          .catch((error) => showAgentMessage(`Manual Handoff 완료 기록에 실패했습니다: ${error.message}`))
          .finally(() => {
            state.busyTask = "";
            render();
          });
      });
    });
  }

  function showAgentMessage(text, links) {
    state.messages.push({ role: "assistant", text, links: links || [] });
    state.open = true;
    state.tab = "agent";
    render();
  }

  function ask(question) {
    if (!question.trim()) return;
    state.draft = "";
    state.messages.push({ role: "user", text: question });
    const pendingIndex = state.messages.push({ role: "assistant", text: "확인 중입니다..." }) - 1;
    state.open = true;
    state.tab = "agent";
    render();
    api("/api/agents/boi-wiki/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        current_url: currentUrl(),
        page_context: { title: pageTitle },
        conversation: state.messages.slice(-10).map((item) => ({ role: item.role, content: item.text })),
      }),
    }).then((body) => {
      state.messages[pendingIndex] = { role: "assistant", text: body.answer_markdown || "", links: body.links || [] };
      if (body.suggested_questions) state.suggestions = body.suggested_questions;
      render();
    }).catch((error) => {
      state.messages[pendingIndex] = { role: "assistant", text: `Agent 호출에 실패했습니다: ${error.message}` };
      render();
    });
  }

  function refreshInbox(message) {
    return api("/api/agents/boi-wiki/inbox").then((body) => {
      state.inbox = body.items || [];
      if (message) showAgentMessage(message);
    });
  }

  Promise.allSettled([
    api("/api/agents/boi-wiki/suggestions", {
      method: "POST",
      body: JSON.stringify({ current_url: currentUrl(), page_context: { title: pageTitle } }),
    }).then((body) => { state.suggestions = body.suggestions || []; }),
    refreshInbox(),
  ]).finally(render);

  window.visualViewport?.addEventListener("resize", syncViewportPosition);
  window.visualViewport?.addEventListener("scroll", syncViewportPosition);
  window.addEventListener("resize", syncViewportPosition);
})();
