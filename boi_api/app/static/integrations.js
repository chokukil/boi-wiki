(function () {
  const page = document.querySelector("[data-integrations-page]");
  if (!page) return;
  const message = page.querySelector("[data-integrations-message]");
  const refreshButton = page.querySelector("[data-integrations-refresh]");

  function render(payload) {
    (payload.items || []).forEach((item) => {
      const row = page.querySelector(`[data-integration-id="${CSS.escape(item.integration_id)}"]`);
      if (!row) return;
      const dot = row.querySelector(".integration-dot");
      const state = row.querySelector(".integration-state");
      const impact = row.querySelector(".integration-impact");
      dot.classList.toggle("ready", Boolean(item.available));
      dot.classList.toggle("warning", !item.available && Boolean(item.configured));
      state.textContent = item.stale ? "상태를 다시 확인 중" : item.user_status;
      if (impact) impact.textContent = item.user_impact || "";
    });
  }

  async function load() {
    try {
      const response = await fetch(page.dataset.statusUrl, {headers: {Accept: "application/json"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
      message.textContent = "";
    } catch (_error) {
      message.textContent = "상태 갱신이 지연되고 있습니다.";
    }
  }

  refreshButton.addEventListener("click", async () => {
    refreshButton.disabled = true;
    message.textContent = "다시 확인하고 있습니다.";
    try {
      await fetch(page.dataset.refreshUrl, {method: "POST", headers: {Accept: "application/json"}});
      setTimeout(load, 700);
    } finally {
      setTimeout(() => { refreshButton.disabled = false; }, 800);
    }
  });
  window.setInterval(() => { if (!document.hidden) load(); }, 5000);
})();
