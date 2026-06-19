(function () {
  function edgeList(title, edges, urlKey, labelKey) {
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = title;
    const list = document.createElement("ul");
    list.className = "relationship-list";
    if (!edges.length) {
      const empty = document.createElement("li");
      empty.className = "empty-state";
      empty.textContent = title === "Outgoing OKF Links" ? "No outgoing OKF document links." : "No backlinks from accessible OKF concepts.";
      list.appendChild(empty);
    }
    for (const edge of edges) {
      const item = document.createElement("li");
      const url = edge[urlKey];
      if (url) {
        const link = document.createElement("a");
        link.href = url;
        link.textContent = edge[labelKey] || edge.source || edge.target;
        item.appendChild(link);
      } else {
        const span = document.createElement("span");
        span.textContent = edge[labelKey] || edge.source || edge.target;
        item.appendChild(span);
      }
      const small = document.createElement("small");
      const count = Number(edge.occurrence_count || 1);
      small.textContent = (edge.source || "") + " -> " + (edge.target || "") + (count > 1 ? " · x" + count : "");
      item.appendChild(small);
      list.appendChild(item);
    }
    section.appendChild(heading);
    section.appendChild(list);
    return section;
  }

  async function loadGraph(panel) {
    const button = panel.querySelector(".load-relationship-graph");
    const content = panel.querySelector(".relationship-graph-content");
    if (!button || !content) return;
    if (content.dataset.loaded === "true") {
      content.hidden = false;
      return;
    }
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const response = await fetch(panel.dataset.graphUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const graph = await response.json();
      content.innerHTML = "";
      const concept = document.createElement("p");
      concept.innerHTML = "<strong>Concept ID:</strong> ";
      const code = document.createElement("code");
      code.textContent = graph.concept_id || "";
      concept.appendChild(code);
      const columns = document.createElement("div");
      columns.className = "relationship-columns";
      columns.appendChild(edgeList("Outgoing OKF Links", graph.outgoing || [], "target_url", "label"));
      columns.appendChild(edgeList("Backlinks", graph.incoming || [], "source_url", "source"));
      content.appendChild(concept);
      content.appendChild(columns);
      content.dataset.loaded = "true";
      content.hidden = false;
      button.textContent = "Refresh Relationship Graph";
    } catch (error) {
      content.textContent = "Relationship graph load failed: " + error.message;
      content.hidden = false;
      button.textContent = "Load Relationship Graph";
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest(".load-relationship-graph");
    if (!button) return;
    event.preventDefault();
    const panel = button.closest("#relationship-graph-panel");
    if (panel) loadGraph(panel);
  });
})();
