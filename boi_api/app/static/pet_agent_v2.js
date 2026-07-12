(function () {
  const root = document.getElementById("boi-agent-root");
  if (!root || root.dataset.v2Initialized === "true") return;
  root.dataset.v2Initialized = "true";

  const state = {
    open: false,
    busy: false,
    bootstrap: null,
    messages: [],
    selectedCapability: "",
    lastRunId: "",
    workSessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
  };

  const pageRef = () => `${location.pathname}${location.search}`;
  const api = async (path, options) => {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...(options || {}),
    });
    let payload = {};
    try { payload = await response.json(); } catch (_error) { payload = {}; }
    if (!response.ok) {
      const detail = payload.detail || payload;
      const message = typeof detail === "string" ? detail : detail.message || detail.status || `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload;
  };

  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  function markdown(value) {
    const mermaidBlocks = [];
    let source = String(value || "").replace(/```mermaid\s*([\s\S]*?)```/gi, (_all, diagram) => {
      const index = mermaidBlocks.push(diagram.trim()) - 1;
      return `@@MERMAID_${index}@@`;
    });
    let output = escapeHtml(source);
    output = output.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    output = output.replace(/^## (.+)$/gm, "<h3>$1</h3>");
    output = output.replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, '<a href="$2">$1</a>');
    output = output.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    output = output.replace(/^- (.+)$/gm, "<li>$1</li>");
    output = output.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");
    output = output.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    mermaidBlocks.forEach((diagram, index) => {
      const safe = escapeHtml(diagram);
      const viewer = `<div class="mermaid-diagram" data-v2-mermaid data-mermaid-state="pending" data-mermaid-title="업무 흐름" data-mermaid-source="${safe}"><span class="mermaid-status">흐름 그림 준비 중</span><div class="mermaid">${safe}</div><div class="mermaid-v2-actions"><button type="button" data-v2-mermaid-action="draft">Task로 나누기</button><button type="button" data-v2-mermaid-action="actions">Action 찾기</button><button type="button" data-v2-mermaid-action="agent">작업공간에서 이어가기</button></div><details class="mermaid-source-fallback"><summary>원문 보기</summary><pre>${safe}</pre></details></div>`;
      output = output.replace(`@@MERMAID_${index}@@`, viewer);
    });
    return output;
  }

  function buildShell() {
    root.innerHTML = `
      <button type="button" class="boi-agent-v2-launcher" data-v2-open aria-expanded="false">
        <span class="boi-agent-v2-launcher-icon" aria-hidden="true">⌕</span>
        <span><strong>업무 도우미</strong><small>검색하고 다음 일을 찾습니다</small></span>
      </button>
      <section class="boi-agent-v2-panel" data-v2-panel aria-label="업무 도우미">
        <header>
          <div><strong>업무 도우미</strong><small>BoI Wiki 전체에서 근거를 찾습니다.</small></div>
          <div>
            <a href="/agent" class="icon-button" data-v2-workspace-link title="전체 작업공간" aria-label="전체 작업공간">↗</a>
            <button type="button" class="icon-button" data-v2-close title="닫기" aria-label="닫기">×</button>
          </div>
        </header>
        <div class="boi-agent-v2-notice" data-v2-notice hidden></div>
        <div class="boi-agent-v2-offers" data-v2-offers></div>
        <div class="boi-agent-v2-messages" data-v2-messages>
          <div class="boi-agent-v2-empty"><strong>검색하듯 물어보세요.</strong><p>관련 문서, 업무 흐름, 유사 사례를 함께 찾습니다.</p></div>
        </div>
        <form class="boi-agent-v2-form" data-v2-form>
          <textarea name="question" rows="2" placeholder="무엇을 찾거나 진행할까요?" required></textarea>
          <div><span data-v2-mode></span><button type="submit" class="primary-button">보내기</button></div>
        </form>
      </section>`;
    root.querySelector("[data-v2-open]").addEventListener("click", () => toggle(true));
    root.querySelector("[data-v2-close]").addEventListener("click", () => toggle(false));
    root.querySelector("[data-v2-form]").addEventListener("submit", submit);
  }

  function toggle(open) {
    state.open = open;
    root.classList.toggle("agent-v2-is-open", open);
    root.querySelector("[data-v2-panel]").classList.toggle("open", open);
    root.querySelector("[data-v2-open]").setAttribute("aria-expanded", String(open));
    if (open) root.querySelector("textarea").focus();
  }

  function renderNotice() {
    const notice = root.querySelector("[data-v2-notice]");
    notice.hidden = true;
    notice.textContent = "";
  }

  function renderOffers() {
    const holder = root.querySelector("[data-v2-offers]");
    holder.innerHTML = "";
    (state.bootstrap?.offers || []).forEach((offer) => {
      if (offer.state === "unavailable") return;
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.offerId = offer.offer_id;
      button.dataset.capabilityId = offer.capability_id;
      button.dataset.state = offer.state;
      button.innerHTML = `<strong>${escapeHtml(offer.label)}</strong><small>${escapeHtml(offer.state === "needs_input" ? "내용을 적고 시작" : offer.reason)}</small>`;
      button.addEventListener("click", () => useOffer(offer));
      holder.appendChild(button);
    });
  }

  function renderMessages() {
    const holder = root.querySelector("[data-v2-messages]");
    if (!state.messages.length) return;
    holder.innerHTML = "";
    state.messages.forEach((message) => {
      const article = document.createElement("article");
      article.className = `boi-agent-v2-message ${message.role}`;
      if (message.role === "assistant") {
        article.innerHTML = `<div>${markdown(message.markdown || message.summary)}</div>`;
        if (message.evidence?.length) {
          const evidence = document.createElement("div");
          evidence.className = "boi-agent-v2-evidence-links";
          message.evidence.slice(0, 4).forEach((item) => {
            const link = document.createElement("a");
            link.href = item.url || "#";
            link.textContent = item.title;
            evidence.appendChild(link);
          });
          article.appendChild(evidence);
        }
        if (message.nextActions?.length) {
          const actions = document.createElement("div");
          actions.className = "boi-agent-v2-evidence-links";
          message.nextActions.slice(0, 3).forEach((item) => {
            const link = document.createElement("a");
            link.href = item.href || (state.workSessionId ? `/agent?session=${encodeURIComponent(state.workSessionId)}` : "/agent");
            link.textContent = item.label;
            actions.appendChild(link);
          });
          article.appendChild(actions);
        }
      } else {
        article.textContent = message.summary;
      }
      holder.appendChild(article);
    });
    holder.scrollTop = holder.scrollHeight;
    document.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
  }

  function setBusy(busy) {
    state.busy = busy;
    root.querySelector("textarea").disabled = busy;
    root.querySelector("[data-v2-form] button").disabled = busy;
    root.querySelector("[data-v2-form] button").textContent = busy ? "확인 중" : "보내기";
  }

  function selectCapability(capabilityId, label) {
    state.selectedCapability = capabilityId;
    root.querySelector("[data-v2-mode]").textContent = label ? `${label} 선택됨` : "";
  }

  async function useOffer(offer) {
    if (state.busy) return;
    if (offer.state === "needs_input") {
      selectCapability(offer.capability_id, offer.label);
      const input = root.querySelector("textarea");
      input.placeholder = `${offer.label}에 필요한 내용을 적어주세요.`;
      input.focus();
      return;
    }
    setBusy(true);
    try {
      const payload = await api(`/api/v2/offers/${encodeURIComponent(offer.offer_id)}/execute`, {
        method: "POST",
        body: JSON.stringify({ page_ref: pageRef(), input_delta: {} }),
      });
      appendResponse(payload);
    } catch (error) {
      state.messages.push({ role: "assistant", summary: `이 작업을 진행하지 못했습니다. ${error.message}` });
      renderMessages();
    } finally { setBusy(false); }
  }

  function appendResponse(payload) {
    state.lastRunId = payload.run_id || state.lastRunId;
    state.workSessionId = payload.work_session_id || state.workSessionId;
    if (state.workSessionId) {
      sessionStorage.setItem("boiAgentV2WorkSession", state.workSessionId);
      root.querySelector("[data-v2-workspace-link]").href = `/agent?session=${encodeURIComponent(state.workSessionId)}`;
    }
    state.messages.push({
      role: "assistant",
      summary: payload.answer?.summary || "결과를 확인하지 못했습니다.",
      markdown: payload.answer?.markdown || payload.answer?.summary || "",
      evidence: payload.evidence_refs || [],
      nextActions: payload.next_actions || [],
    });
    renderMessages();
  }

  async function submit(event) {
    event.preventDefault();
    if (state.busy) return;
    const input = root.querySelector("textarea");
    const question = input.value.trim();
    if (!question) return;
    state.messages.push({ role: "user", summary: question });
    input.value = "";
    renderMessages();
    setBusy(true);
    try {
      const payload = await api("/api/v2/agent/turns", {
        method: "POST",
        body: JSON.stringify({
          question,
          page_ref: pageRef(),
          work_session_id: state.workSessionId || null,
          capability_id: state.selectedCapability || null,
        }),
      });
      selectCapability("", "");
      appendResponse(payload);
    } catch (error) {
      state.messages.push({ role: "assistant", summary: `답을 만들지 못했습니다. ${error.message}` });
      renderMessages();
    } finally { setBusy(false); }
  }

  async function initialize() {
    buildShell();
    try {
      state.bootstrap = await api(`/api/v2/bootstrap?page_ref=${encodeURIComponent(pageRef())}`);
      renderNotice();
      renderOffers();
      if (state.workSessionId) {
        try {
          const bundle = await api(`/api/v2/work-sessions/${encodeURIComponent(state.workSessionId)}`);
          state.messages = (bundle.timeline || []).slice(-6).map((item) => ({
            role: item.role,
            summary: item.display_text,
            markdown: item.display_text,
            evidence: item.evidence_refs || [],
          }));
          root.querySelector("[data-v2-workspace-link]").href = `/agent?session=${encodeURIComponent(state.workSessionId)}`;
          renderMessages();
        } catch (_error) {
          state.workSessionId = "";
          sessionStorage.removeItem("boiAgentV2WorkSession");
        }
      }
    } catch (error) {
      const notice = root.querySelector("[data-v2-notice]");
      notice.hidden = false;
      notice.textContent = `업무 도우미에 연결하지 못했습니다. ${error.message}`;
    }
  }

  initialize();
})();
