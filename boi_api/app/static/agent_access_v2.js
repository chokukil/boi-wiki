(function () {
  const root = document.querySelector("[data-agent-access-v2]");
  if (!root) return;
  const form = root.querySelector("[data-agent-token-form]");
  const list = root.querySelector("[data-agent-token-list]");
  const result = root.querySelector("[data-agent-token-result]");
  const tokenValue = root.querySelector("[data-agent-token-value]");

  root.querySelectorAll("[data-access-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      root.querySelectorAll("[data-access-tab]").forEach((item) => item.classList.toggle("active", item === button));
      root.querySelectorAll("[data-access-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.accessPanel !== button.dataset.accessTab;
      });
    });
  });

  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  async function api(path, options) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...(options || {}),
    });
    let payload = {};
    try { payload = await response.json(); } catch (_error) { payload = {}; }
    if (!response.ok) {
      const detail = payload.detail || payload;
      throw new Error(typeof detail === "string" ? detail : detail.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function formatDate(value) {
    if (!value) return "-";
    try { return new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium" }).format(new Date(value)); }
    catch (_error) { return value; }
  }

  async function loadTokens() {
    list.innerHTML = "<p>확인 중입니다.</p>";
    try {
      const payload = await api("/api/v2/tokens");
      const items = payload.items || [];
      if (!items.length) { list.innerHTML = "<p>아직 연결된 외부 도구가 없습니다.</p>"; return; }
      list.innerHTML = items.map((item) => `
        <article data-token-id="${escapeHtml(item.token_id)}">
          <div><strong>${escapeHtml(item.name)}</strong><span>${item.revoked_at ? "폐기됨" : "사용 가능"}</span></div>
          <p>${escapeHtml((item.scopes || []).join(" · "))}</p>
          <small>만료 ${formatDate(item.expires_at)} · 최근 사용 ${formatDate(item.last_used_at)}</small>
          ${item.revoked_at ? "" : '<button type="button" data-revoke>폐기</button>'}
        </article>`).join("");
      list.querySelectorAll("[data-revoke]").forEach((button) => {
        button.addEventListener("click", async () => {
          const article = button.closest("[data-token-id]");
          if (!confirm("이 연결 키를 폐기할까요? 연결된 외부 도구는 즉시 사용할 수 없게 됩니다.")) return;
          await api(`/api/v2/tokens/${encodeURIComponent(article.dataset.tokenId)}`, { method: "DELETE" });
          await loadTokens();
        });
      });
    } catch (error) { list.innerHTML = `<p>연결 목록을 확인하지 못했습니다. ${escapeHtml(error.message)}</p>`; }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const scopes = ["boi.read", ...Array.from(form.querySelectorAll('[name="scopes"]:checked:not(:disabled)')).map((item) => item.value)];
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const payload = await api("/api/v2/tokens", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          expires_in_days: Number(data.get("expires_in_days") || 30),
          scopes,
        }),
      });
      tokenValue.textContent = payload.token;
      result.hidden = false;
      await loadTokens();
    } catch (error) { alert(`연결 키를 만들지 못했습니다. ${error.message}`); }
    finally { button.disabled = false; }
  });

  root.querySelector("[data-agent-token-copy]").addEventListener("click", async () => {
    await navigator.clipboard.writeText(tokenValue.textContent || "");
    root.querySelector("[data-agent-token-copy]").textContent = "복사됨";
  });
  root.querySelector("[data-agent-token-refresh]").addEventListener("click", loadTokens);
  loadTokens();
})();
