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
    if (status) status.textContent = "세부 정보를 불러오고 있습니다.";
    try {
      const response = await fetch(details.dataset.metadataUrl, { headers: { Accept: "text/html" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      content.innerHTML = await response.text();
      content.dataset.loaded = "true";
      content.hidden = false;
      if (status) status.textContent = "세부 정보를 불러왔습니다.";
      if (button) button.textContent = "세부 정보 새로고침";
    } catch (error) {
      if (status) status.textContent = "세부 정보를 불러오지 못했습니다.";
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
