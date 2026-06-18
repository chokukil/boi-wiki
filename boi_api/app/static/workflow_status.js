(function () {
  function prettyJson(value) {
    return JSON.stringify(value, null, 2);
  }

  async function loadWorkflowRaw(button) {
    const panel = button.closest(".workflow-raw-panel");
    if (!panel) return;
    const output = panel.querySelector(".workflow-raw-output");
    if (!output) return;
    const section = button.dataset.section || "all";
    if (output.dataset.section === section && output.dataset.loaded === "true") {
      output.hidden = false;
      return;
    }
    const original = button.textContent;
    const url = new URL(panel.dataset.rawUrl, window.location.origin);
    url.searchParams.set("section", section);
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      output.textContent = prettyJson(payload.data);
      output.dataset.section = section;
      output.dataset.loaded = "true";
      output.hidden = false;
      button.textContent = original;
    } catch (error) {
      output.textContent = "Raw JSON load failed: " + error.message;
      output.hidden = false;
      button.textContent = original;
    } finally {
      button.disabled = false;
    }
  }

  async function loadActionRaw(button) {
    const cell = button.closest("td");
    if (!cell) return;
    const output = cell.querySelector(".workflow-action-raw-output");
    if (!output) return;
    const rawUrl = button.dataset.rawUrl;
    if (!rawUrl) return;
    if (output.dataset.loaded === "true") {
      output.hidden = false;
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const response = await fetch(rawUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      output.textContent = prettyJson(payload.row || payload);
      output.dataset.loaded = "true";
      output.hidden = false;
      button.textContent = original;
    } catch (error) {
      output.textContent = "Action raw load failed: " + error.message;
      output.hidden = false;
      button.textContent = original;
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest(".load-workflow-raw, .load-action-raw");
    if (!button) return;
    event.preventDefault();
    if (button.classList.contains("load-action-raw")) {
      loadActionRaw(button);
    } else {
      loadWorkflowRaw(button);
    }
  });
})();
