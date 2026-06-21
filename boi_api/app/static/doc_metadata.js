(function () {
  async function loadMetadata(details) {
    const content = details.querySelector(".metadata-fragment-content");
    const button = details.querySelector(".load-metadata-fragment");
    const status = details.querySelector(".metadata-load-status");
    if (!content || !details.dataset.metadataUrl) return;
    if (content.dataset.loaded === "true") {
      content.hidden = false;
      return;
    }
    if (button) button.disabled = true;
    if (status) status.textContent = "Loading full metadata...";
    try {
      const response = await fetch(details.dataset.metadataUrl, { headers: { Accept: "text/html" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      content.innerHTML = await response.text();
      content.dataset.loaded = "true";
      content.hidden = false;
      if (status) status.textContent = "Full metadata loaded.";
      if (button) button.textContent = "Refresh Full Metadata";
    } catch (error) {
      if (status) status.textContent = "Metadata load failed: " + error.message;
      content.hidden = false;
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.addEventListener("toggle", function (event) {
    const details = event.target;
    if (!(details instanceof HTMLDetailsElement) || !details.matches("details.metadata") || !details.open) return;
    loadMetadata(details);
  }, true);

  document.addEventListener("click", function (event) {
    const button = event.target.closest(".load-metadata-fragment");
    if (!button) return;
    event.preventDefault();
    const details = button.closest("details.metadata");
    if (details) loadMetadata(details);
  });
})();
