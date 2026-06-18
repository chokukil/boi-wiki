(function () {
  function prettyJson(value) {
    return JSON.stringify(value, null, 2);
  }

  async function loadRaw(button) {
    const output = button.parentElement.querySelector(".raw-json-output");
    if (!output || output.dataset.loaded === "true") {
      if (output) output.hidden = false;
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const response = await fetch(button.dataset.rawUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      output.textContent = prettyJson(payload.row || payload);
      output.dataset.loaded = "true";
      output.hidden = false;
      button.textContent = "Raw JSON 새로고침";
    } catch (error) {
      output.textContent = "Raw JSON load failed: " + error.message;
      output.hidden = false;
      button.textContent = original;
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest(".load-raw-event");
    if (!button) return;
    event.preventDefault();
    loadRaw(button);
  });
})();
