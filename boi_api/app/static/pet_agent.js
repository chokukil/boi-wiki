(function () {
  const root = document.getElementById("boi-agent-root");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";

  const employeeId = root.dataset.employeeId || new URLSearchParams(location.search).get("employee_id") || "100001";
  const pageTitle = root.dataset.pageTitle || document.title || "BoI Wiki";
  const storageKey = `boiAgent.v5.${employeeId}`;
  let activeRequest = null;
  let restoreScrollOnce = true;

  function currentUrl() {
    return root.dataset.currentUrl || `${location.pathname}${location.search}`;
  }

  function selectedText() {
    return String(window.getSelection?.().toString() || "").trim().slice(0, 1200);
  }

  function defaultState() {
    return {
      open: false,
      expanded: false,
      tab: "agent",
      suggestions: [],
      inbox: [],
      messages: [],
      draft: "",
      busyTask: "",
      sending: false,
      scrollTop: 0,
      viewer: null,
    };
  }

  function loadState() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
      return { ...defaultState(), ...saved, suggestions: [], inbox: [], busyTask: "", sending: false, viewer: null };
    } catch (_error) {
      return defaultState();
    }
  }

  const state = loadState();

  function persistState() {
    const saved = {
      open: state.open,
      expanded: state.expanded,
      tab: state.tab,
      messages: state.messages.slice(-20),
      draft: state.draft,
      scrollTop: state.scrollTop,
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
    const { signal, ...fetchOptions } = options || {};
    return fetch(url, {
      headers: { "Content-Type": "application/json" },
      signal,
      ...fetchOptions,
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

  function escapeAttr(value) {
    return escapeHtml(value).replace(/'/g, "&#39;");
  }

  function normalizeMermaidSource(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function mermaidSourcesFromMarkdown(value) {
    const found = new Set();
    const fence = /```[^\S\r\n]*([A-Za-z0-9_-]+)?[^\S\r\n]*(?:\r?\n)([\s\S]*?)```/g;
    let match;
    while ((match = fence.exec(String(value || "")))) {
      if (String(match[1] || "").toLowerCase() === "mermaid") {
        found.add(normalizeMermaidSource(match[2]));
      }
    }
    return found;
  }

  function renderInlineMarkdown(value) {
    const tokens = [];
    const stash = (html) => {
      const token = `@@BOI_AGENT_TOKEN_${tokens.length}@@`;
      tokens.push({ token, html });
      return token;
    };
    let text = String(value || "")
      .replace(/`([^`]+)`/g, (_match, code) => stash(`<code>${escapeHtml(code)}</code>`))
      .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, url) => {
        const src = String(url || "").trim();
        return src
          ? stash(`<img class="boi-agent-inline-image" src="${escapeAttr(src)}" alt="${escapeAttr(alt || "Markdown image")}" loading="lazy" decoding="async">`)
          : "";
      })
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, url) => {
        const href = String(url || "").trim();
        return href ? stash(`<a href="${escapeAttr(href)}">${escapeHtml(label)}</a>`) : escapeHtml(label);
      });
    text = escapeHtml(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>")
      .replace(/~~([^~]+)~~/g, "<del>$1</del>")
      .replace(/\*([^*\s][^*]*?)\*/g, "<em>$1</em>")
      .replace(/(^|[\s>])(https?:\/\/[^\s<]+[^<.,;:\s)])/g, (_match, prefix, url) => `${prefix}<a href="${escapeAttr(url)}">${escapeHtml(url)}</a>`);
    for (const item of tokens) {
      text = text.replace(item.token, item.html);
    }
    return text;
  }

  function isTableSeparatorLine(line) {
    const cells = splitTableRow(line);
    return cells.length >= 2 && cells.every((cell) => /^:?\s*-{3,}\s*:?$/.test(cell.trim()));
  }

  function isLikelyTableStart(lines, index) {
    return Boolean(
      lines[index]?.includes("|")
      && lines[index + 1]?.includes("|")
      && isTableSeparatorLine(lines[index + 1])
    );
  }

  function renderMarkdownTable(lines) {
    if (lines.length < 2 || !isTableSeparatorLine(lines[1])) return "";
    const headers = splitTableRow(lines[0]);
    const bodyRows = lines.slice(2)
      .map(splitTableRow)
      .filter((row) => row.length)
      .map((row) => normalizeTableRow(row, headers.length));
    if (!headers.length) return "";
    return `<div class="boi-agent-table-wrap"><table><thead><tr>${headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead><tbody>${bodyRows.map((row) => `<tr>${headers.map((_header, index) => `<td>${renderInlineMarkdown(row[index] || "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  function normalizeTableRow(row, expectedLength) {
    if (!expectedLength || row.length <= expectedLength) return row;
    const head = row.slice(0, expectedLength - 1);
    head.push(row.slice(expectedLength - 1).join(" | "));
    return head;
  }

  function splitTableRow(line) {
    const source = String(line || "").trim().replace(/^\|/, "").replace(/\|$/, "");
    const cells = [];
    let cell = "";
    let escaped = false;
    let inCode = false;
    let parenDepth = 0;
    for (const char of source) {
      if (escaped) {
        cell += char === "|" ? "|" : `\\${char}`;
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === "`") {
        inCode = !inCode;
        cell += char;
      } else if (!inCode && char === "(") {
        parenDepth += 1;
        cell += char;
      } else if (!inCode && char === ")" && parenDepth > 0) {
        parenDepth -= 1;
        cell += char;
      } else if (char === "|") {
        if (inCode || parenDepth > 0) {
          cell += char;
        } else {
          cells.push(cell.trim());
          cell = "";
        }
      } else {
        cell += char;
      }
    }
    cells.push(cell.trim());
    return cells;
  }

  function renderTextMarkdown(value) {
    const lines = String(value || "").split(/\n/);
    const parts = [];
    for (let i = 0; i < lines.length; i += 1) {
      if (!lines[i].trim()) continue;
      if (isLikelyTableStart(lines, i)) {
        const tableLines = [];
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
          tableLines.push(lines[i]);
          i += 1;
        }
        i -= 1;
        const table = renderMarkdownTable(tableLines);
        if (table) {
          parts.push(table);
          continue;
        }
      }
      const line = lines[i];
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        const level = Math.min(6, heading[1].length + 2);
        parts.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
        continue;
      }
      if (/^\s*[-*+]\s+/.test(line)) {
        const listItems = [];
        while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
          const rawItem = lines[i].replace(/^\s*[-*+]\s+/, "");
          const task = rawItem.match(/^\[( |x|X)\]\s+(.*)$/);
          if (task) {
            const checked = task[1].toLowerCase() === "x";
            listItems.push(`<li><input type="checkbox" disabled${checked ? " checked" : ""}> ${renderInlineMarkdown(task[2])}</li>`);
          } else {
            listItems.push(`<li>${renderInlineMarkdown(rawItem)}</li>`);
          }
          i += 1;
        }
        i -= 1;
        parts.push(`<ul>${listItems.join("")}</ul>`);
        continue;
      }
      if (/^\s*\d+\.\s+/.test(line)) {
        const listItems = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          listItems.push(`<li>${renderInlineMarkdown(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`);
          i += 1;
        }
        i -= 1;
        parts.push(`<ol>${listItems.join("")}</ol>`);
        continue;
      }
      if (/^\s*>\s?/.test(line)) {
        const quoteLines = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          quoteLines.push(lines[i].replace(/^\s*>\s?/, ""));
          i += 1;
        }
        i -= 1;
        parts.push(`<blockquote>${quoteLines.map((quote) => `<p>${renderInlineMarkdown(quote)}</p>`).join("")}</blockquote>`);
        continue;
      }
      if (/^\s*---+\s*$/.test(line)) {
        parts.push("<hr>");
        continue;
      }
      const paragraph = [line.trim()];
      while (
        i + 1 < lines.length
        && lines[i + 1].trim()
        && !/^(#{1,4})\s+/.test(lines[i + 1])
        && !/^\s*([-*+]|\d+\.)\s+/.test(lines[i + 1])
        && !/^\s*>\s?/.test(lines[i + 1])
        && !isLikelyTableStart(lines, i + 1)
        && !/^\s*---+\s*$/.test(lines[i + 1])
      ) {
        i += 1;
        paragraph.push(lines[i].trim());
      }
      parts.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    }
    return parts.join("");
  }

  function renderMermaidBlock(source, title, viewerPayload) {
    const escapedSource = escapeHtml(source);
    const id = viewerPayload ? ` data-viewer-id="${escapeAttr(viewerPayload.id)}"` : "";
    return `
      <div class="mermaid-diagram boi-agent-artifact" data-mermaid-state="pending"${id}>
        <div class="boi-agent-artifact-title">
          ${title ? `<strong>${escapeHtml(title)}</strong>` : "<strong>Diagram</strong>"}
          ${viewerPayload ? `<button type="button" data-open-artifact="${escapeAttr(viewerPayload.id)}">크게 보기</button>` : ""}
        </div>
        <div class="mermaid">${escapedSource}</div>
        <p class="mermaid-status">Rendering Mermaid diagram...</p>
        <details class="mermaid-source-fallback">
          <summary>Mermaid source</summary>
          <pre><code>${escapedSource}</code></pre>
        </details>
      </div>`;
  }

  function renderMarkdownLite(value, options) {
    const text = String(value || "");
    const skipMermaidSources = options?.skipMermaidSources || new Set();
    const parts = [];
    const fence = /```[^\S\r\n]*([A-Za-z0-9_-]+)?[^\S\r\n]*(?:\r?\n)([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;
    while ((match = fence.exec(text))) {
      if (match.index > lastIndex) parts.push(renderTextMarkdown(text.slice(lastIndex, match.index).trim()));
      const lang = String(match[1] || "").toLowerCase();
      const source = String(match[2] || "").trim();
      if (lang === "mermaid") {
        if (!skipMermaidSources.has(normalizeMermaidSource(source))) {
          const id = `markdown-mermaid-${parts.length}-${Math.abs(hashString(source))}`;
          parts.push(renderMermaidBlock(source, "Diagram", { id, source, type: "mermaid" }));
        }
      } else {
        const className = lang ? ` class="language-${escapeAttr(lang)}"` : "";
        parts.push(`<pre><code${className}>${escapeHtml(source)}</code></pre>`);
      }
      lastIndex = fence.lastIndex;
    }
    if (lastIndex < text.length) parts.push(renderTextMarkdown(text.slice(lastIndex).trim()));
    return parts.filter(Boolean).join("");
  }

  function hashString(value) {
    let hash = 0;
    for (let index = 0; index < String(value).length; index += 1) {
      hash = ((hash << 5) - hash) + String(value).charCodeAt(index);
      hash |= 0;
    }
    return hash;
  }

  function artifactItems(message) {
    const markdownMermaid = mermaidSourcesFromMarkdown(message.text || "");
    const seenMermaidSources = new Set();
    return (message.artifacts || []).filter((artifact) => {
      if (!artifact || typeof artifact !== "object") return false;
      if (artifact.type === "mermaid" && artifact.source) {
        const source = normalizeMermaidSource(artifact.source);
        if (seenMermaidSources.has(source)) return false;
        seenMermaidSources.add(source);
        if (markdownMermaid.has(source)) return true;
      }
      return true;
    });
  }

  function mermaidSourcesFromArtifacts(message) {
    const found = new Set();
    for (const artifact of message.artifacts || []) {
      if (artifact?.type === "mermaid" && artifact.source) found.add(normalizeMermaidSource(artifact.source));
    }
    return found;
  }

  function renderArtifacts(message, messageIndex) {
    const artifacts = artifactItems(message);
    if (!artifacts.length) return "";
    return `<div class="boi-agent-artifacts">${artifacts.map((artifact, artifactIndex) => {
      const viewerId = `artifact-${messageIndex}-${artifactIndex}`;
      if (artifact.type === "mermaid" && artifact.source) {
        return renderMermaidBlock(artifact.source, artifact.title || "Diagram", { id: viewerId, type: "mermaid", source: artifact.source });
      }
      if (artifact.type === "gap_table" && Array.isArray(artifact.data)) {
        return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "Gap Check")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${renderObjectTable(artifact.data)}</div>`;
      }
      if (artifact.type === "workflow_summary" && artifact.data) {
        const rows = Array.isArray(artifact.data) ? artifact.data : [artifact.data];
        return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "Workflow Summary")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${renderObjectTable(rows)}</div>`;
      }
      if (artifact.type === "task_cards" && Array.isArray(artifact.data)) {
        return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "Tasks")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${artifact.data.map((item) => renderTaskDisplay(item || {})).join("")}</div>`;
      }
      if (artifact.type === "confirmation_required" && artifact.data) {
        return renderConfirmationArtifact(artifact, viewerId);
      }
      if (artifact.type === "image" && artifact.url) {
        return `<figure class="boi-agent-artifact boi-agent-image-artifact" data-viewer-id="${escapeAttr(viewerId)}"><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "Image")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div><img src="${escapeAttr(artifact.url)}" alt="${escapeAttr(artifact.alt || artifact.title || "Artifact image")}"></figure>`;
      }
      return "";
    }).join("")}</div>`;
  }

  function renderConfirmationArtifact(artifact, viewerId) {
    const data = artifact.data || {};
    const operation = String(data.operation || "");
    const payload = data.payload && typeof data.payload === "object" ? data.payload : {};
    const canExecute = operation && Object.keys(payload).length > 0;
    const title = artifact.title || data.title || "확인 필요";
    const message = data.message || "상태 변경이나 승인 절차가 필요한 요청입니다. 내용을 확인한 뒤 명시적으로 실행해야 합니다.";
    const primaryLabel = data.primary_label || (canExecute ? "요청 실행" : "먼저 확인");
    const payloadJson = JSON.stringify(payload);
    return `
      <div class="boi-agent-artifact boi-agent-confirmation-card" data-viewer-id="${escapeAttr(viewerId)}">
        <div class="boi-agent-artifact-title">
          <strong>${escapeHtml(title)}</strong>
          <button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button>
        </div>
        <p>${escapeHtml(message)}</p>
        <div class="boi-agent-confirmation-actions">
          ${canExecute ? `<button type="button" data-agent-approve data-operation="${escapeAttr(operation)}" data-payload="${escapeAttr(payloadJson)}">${escapeHtml(primaryLabel)}</button>` : `<span>${escapeHtml(primaryLabel)}</span>`}
        </div>
        <details class="boi-agent-technical">
          <summary>기술 세부정보</summary>
          <dl>
            ${data.route ? `<div><dt>Route</dt><dd>${escapeHtml(data.route)}</dd></div>` : ""}
            ${data.intent ? `<div><dt>Intent</dt><dd>${escapeHtml(data.intent)}</dd></div>` : ""}
            ${operation ? `<div><dt>Operation</dt><dd>${escapeHtml(operation)}</dd></div>` : ""}
          </dl>
          ${Object.keys(payload).length ? `<pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>` : ""}
        </details>
      </div>`;
  }

  function renderObjectTable(rows) {
    if (!Array.isArray(rows) || !rows.length) return "";
    const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row || {}))));
    return `<div class="boi-agent-table-wrap"><table><thead><tr>${keys.map((key) => `<th>${escapeHtml(key)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${keys.map((key) => `<td>${renderCellValue(row?.[key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  function renderCellValue(value) {
    if (value === null || value === undefined || value === "") return "-";
    if (Array.isArray(value)) {
      if (!value.length) return "-";
      return `<ul>${value.map((item) => `<li>${renderCellValue(item)}</li>`).join("")}</ul>`;
    }
    if (typeof value === "object") {
      return `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
    }
    return renderInlineMarkdown(value);
  }

  window.BoiAgentMarkdownDebug = {
    renderInlineMarkdown,
    renderMarkdownLite,
    renderMarkdownTable,
    renderCellValue,
    splitTableRow,
    mermaidSourcesFromMarkdown,
    mermaidSourcesFromArtifacts,
  };

  function renderLinks(links) {
    if (!links || !links.length) return "";
    return `<div class="boi-agent-links">${links
      .filter((item) => item.url)
      .map((item) => `<a href="${escapeAttr(item.url)}">${escapeHtml(item.label || item.url)}</a>`)
      .join("")}</div>`;
  }

  function renderMessageMeta(message) {
    const meta = message.meta || {};
    const chips = [];
    const intentLabels = {
      search: "검색",
      page_qa: "현재 페이지 답변",
      summarize: "요약",
      diagram: "도식 생성",
      workflow_explain: "업무 흐름 분석",
      gap_check: "누락 점검",
      trace_reasoning: "실행 근거 분석",
      inbox: "Inbox",
      manual_complete: "조치 확인",
      approval: "승인 필요",
      access_denied: "권한 확인",
    };
    const routeLabels = {
      manual_handoff: "조치 확인",
      approval_required: "승인 필요",
      inbox: "Inbox",
    };
    if (meta.intent && intentLabels[meta.intent]) chips.push(intentLabels[meta.intent]);
    if (!chips.length && meta.route && routeLabels[meta.route]) chips.push(routeLabels[meta.route]);
    if (!chips.length) return "";
    return `<div class="boi-agent-meta">${chips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("")}</div>`;
  }

  function tabLabel(tab) {
    return { agent: "Agent", inbox: "Inbox" }[tab] || tab;
  }

  function renderMessages() {
    if (!state.messages.length) return "";
    return `<div class="boi-agent-messages">${state.messages
      .map((message, index) => {
        const artifactMermaid = mermaidSourcesFromArtifacts(message);
        const answerHtml = renderMarkdownLite(message.text || "", { skipMermaidSources: artifactMermaid });
        return `
        <article class="boi-agent-message ${message.role === "user" ? "user" : "assistant"}">
          <strong class="boi-agent-message-author">${message.role === "user" ? "You" : "BoI Agent"}</strong>
          ${renderMessageMeta(message)}
          <div class="boi-agent-answer">${answerHtml}</div>
          ${renderArtifacts(message, index)}
          ${renderLinks(message.links || [])}
        </article>`;
      })
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
      <section class="boi-agent-panel ${state.open ? "open" : ""} ${state.expanded ? "expanded" : ""}" aria-label="BoI Agent">
        <header>
          <div class="boi-agent-header-main">
            <img class="boi-agent-pet small" src="/static/assets/boi-agent-pet.png" alt="" loading="lazy" decoding="async">
            <div>
              <h2>BoI Agent</h2>
              <p>${escapeHtml(pageTitle)}</p>
            </div>
          </div>
          <div class="boi-agent-window-actions">
            <button type="button" class="boi-agent-new" aria-label="새 대화">새 대화</button>
            <button type="button" class="boi-agent-expand" aria-label="창 크기">${state.expanded ? "축소" : "확대"}</button>
            <button type="button" class="boi-agent-close" aria-label="Close">×</button>
          </div>
        </header>
        <nav class="boi-agent-tabs" aria-label="BoI Agent tabs">
          ${["agent", "inbox"].map((tab) => `<button type="button" data-tab="${tab}" class="${state.tab === tab ? "active" : ""}">${tabLabel(tab)}</button>`).join("")}
        </nav>
        <div class="boi-agent-content">${renderTab()}</div>
      </section>
      ${renderViewer()}
    `;
    bind();
    restoreOrPinScroll();
    root.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
  }

  function renderTab() {
    if (state.tab === "inbox") {
      if (!state.inbox.length) return `<div class="boi-agent-empty">현재 처리할 Action이 없습니다.</div>`;
      return `<div class="boi-agent-list">${state.inbox
        .map((item) => {
          const isManual = ["manual_required", "manual_blocked", "needs_followup"].includes(item.status || "");
          const display = item.display || {};
          return `
          <article class="boi-agent-task">
            ${renderTaskDisplay(display, item)}
            <div class="boi-agent-links">
              ${display.primary_url ? `<a href="${escapeAttr(display.primary_url)}">${escapeHtml(display.primary_label || "업무 상태 보기")}</a>` : ""}
              ${item.workflow_url ? `<a href="${escapeAttr(item.workflow_url)}">Workflow</a>` : ""}
              ${item.raw_url ? `<a href="${escapeAttr(item.raw_url)}">Raw</a>` : ""}
            </div>
            <details class="boi-agent-technical">
              <summary>기술 세부정보</summary>
              <dl>
                ${item.status ? `<div><dt>상태</dt><dd>${escapeHtml(item.status)}</dd></div>` : ""}
                ${item.action_key ? `<div><dt>Action</dt><dd>${escapeHtml(item.action_key)}</dd></div>` : ""}
                ${item.request_id ? `<div><dt>요청</dt><dd>${escapeHtml(item.request_id)}</dd></div>` : ""}
                ${item.trace_id ? `<div><dt>Trace</dt><dd>${escapeHtml(item.trace_id)}</dd></div>` : ""}
              </dl>
            </details>
            ${isManual ? `
              <form class="boi-agent-handoff-form" data-task-id="${escapeAttr(item.task_id || "")}">
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
              </form>` : `<p class="boi-agent-hint">승인이 필요한 업무입니다. Workflow와 원본 기록을 확인한 뒤 명시 승인으로 처리합니다.</p>`}
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
        ${state.suggestions.map((item) => `<button type="button" data-question="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}
      </div>
      ${renderMessages()}
      <form class="boi-agent-chat-form">
        <textarea name="question" placeholder="현재 페이지 기준으로 묻거나, SOP/Event/Action을 찾아보세요." required>${escapeHtml(state.draft)}</textarea>
        <div class="boi-agent-form-actions">
          ${state.sending ? `<button type="button" class="boi-agent-stop">중지</button>` : ""}
          <button type="submit" ${state.sending ? "disabled" : ""}>Agent에게 묻기</button>
        </div>
      </form>
      <p class="boi-agent-hint">Enter로 전송, Shift+Enter로 줄바꿈</p>
    `;
  }

  function renderTaskDisplay(display, rawItem) {
    const item = display || {};
    const fallback = rawItem || {};
    return `
      <div class="boi-agent-task-display">
        <div class="boi-agent-task-title">
          <strong>${escapeHtml(item.title || fallback.action_key || "업무 확인")}</strong>
          <span>${escapeHtml(item.status_label || fallback.status || "확인 필요")}</span>
        </div>
        ${item.risk_label ? `<small>${escapeHtml(item.risk_label)}</small>` : ""}
        <p>${escapeHtml(item.why_it_matters || fallback.summary || "")}</p>
        ${item.next_action ? `<p class="boi-agent-next-action">${escapeHtml(item.next_action)}</p>` : ""}
      </div>`;
  }

  function renderViewer() {
    if (!state.viewer) return "";
    return `
      <div class="boi-agent-viewer-backdrop" role="presentation">
        <section class="boi-agent-viewer" role="dialog" aria-modal="true" aria-label="Artifact viewer">
          <header>
            <strong>${escapeHtml(state.viewer.title || "Artifact")}</strong>
            <button type="button" class="boi-agent-viewer-close">닫기</button>
          </header>
          <div class="boi-agent-viewer-body">${state.viewer.html || ""}</div>
        </section>
      </div>`;
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
    root.querySelector(".boi-agent-expand")?.addEventListener("click", () => {
      state.expanded = !state.expanded;
      render();
    });
    root.querySelector(".boi-agent-new")?.addEventListener("click", () => {
      if (activeRequest) activeRequest.abort();
      activeRequest = null;
      state.messages = [];
      state.draft = "";
      state.sending = false;
      state.scrollTop = 0;
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
    root.querySelector(".boi-agent-stop")?.addEventListener("click", () => {
      if (activeRequest) activeRequest.abort();
    });
    const content = root.querySelector(".boi-agent-content");
    content?.addEventListener("scroll", () => {
      state.scrollTop = content.scrollTop;
      persistState();
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
    root.querySelectorAll("[data-open-artifact]").forEach((button) => {
      button.addEventListener("click", () => openArtifact(button.dataset.openArtifact || ""));
    });
    root.querySelectorAll(".boi-agent-answer img, .boi-agent-artifact img").forEach((image) => {
      image.addEventListener("click", () => openImageArtifact(image));
    });
    root.querySelectorAll("[data-agent-approve]").forEach((button) => {
      button.addEventListener("click", () => {
        let payload = {};
        try {
          payload = JSON.parse(button.dataset.payload || "{}");
        } catch (_error) {
          payload = {};
        }
        const operation = button.dataset.operation || "";
        if (!operation) return;
        state.busyTask = `approve:${operation}`;
        render();
        api("/api/agents/boi-wiki/approve", {
          method: "POST",
          body: JSON.stringify({
            operation,
            payload,
            user_confirmed: true,
            note: "BoI Agent confirmation card",
          }),
        }).then((body) => {
          showAgentMessage(`${operation} 요청을 처리했습니다. 상태: ${body.status || "완료"}`);
          return refreshInbox();
        }).catch((error) => showAgentMessage(`요청 실행에 실패했습니다: ${error.message}`))
          .finally(() => {
            state.busyTask = "";
            render();
          });
      });
    });
    root.querySelector(".boi-agent-viewer-close")?.addEventListener("click", () => {
      state.viewer = null;
      render();
    });
    root.querySelector(".boi-agent-viewer-backdrop")?.addEventListener("click", (event) => {
      if (event.target === event.currentTarget) {
        state.viewer = null;
        render();
      }
    });
  }

  function restoreOrPinScroll() {
    const content = root.querySelector(".boi-agent-content");
    if (!content) return;
    if (restoreScrollOnce && state.scrollTop) {
      content.scrollTop = state.scrollTop;
      restoreScrollOnce = false;
      return;
    }
    if (state.open && state.tab === "agent") content.scrollTop = content.scrollHeight;
  }

  function openArtifact(id) {
    const node = root.querySelector(`[data-viewer-id="${CSS.escape(id)}"]`);
    if (!node) return;
    const clone = node.cloneNode(true);
    clone.querySelectorAll("[data-open-artifact]").forEach((button) => button.remove());
    state.viewer = {
      title: clone.querySelector("strong")?.textContent || "Artifact",
      html: clone.outerHTML,
    };
    render();
  }

  function openImageArtifact(image) {
    const src = image.getAttribute("src") || "";
    if (!src) return;
    const alt = image.getAttribute("alt") || "Image";
    state.viewer = {
      title: alt,
      html: `<figure class="boi-agent-image-viewer"><img src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"></figure>`,
    };
    render();
  }

  function showAgentMessage(text, links) {
    state.messages.push({ role: "assistant", text, links: links || [] });
    state.open = true;
    state.tab = "agent";
    render();
  }

  function ask(question) {
    if (!question.trim() || state.sending) return;
    const controller = new AbortController();
    activeRequest = controller;
    state.draft = "";
    state.sending = true;
    state.messages.push({ role: "user", text: question });
    const pendingIndex = state.messages.push({ role: "assistant", text: "확인 중입니다..." }) - 1;
    state.open = true;
    state.tab = "agent";
    render();
    api("/api/agents/boi-wiki/chat", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({
        question,
        selected_text: selectedText(),
        current_url: currentUrl(),
        page_context: { title: pageTitle },
        conversation: state.messages.slice(-10).map((item) => ({ role: item.role, content: item.text })),
      }),
    }).then((body) => {
      state.messages[pendingIndex] = {
        role: "assistant",
        text: body.display_markdown || body.answer_markdown || "",
        rawText: body.answer_markdown || "",
        links: body.links || [],
        meta: {
          route: body.route,
          intent: body.intent || body.context_summary?.intent,
          used_backend: body.used_backend,
          router_backend: body.router_backend,
          latency_ms: body.latency_ms,
        },
        artifacts: body.artifacts || [],
      };
      if (body.suggested_questions) state.suggestions = body.suggested_questions;
    }).catch((error) => {
      state.messages[pendingIndex] = {
        role: "assistant",
        text: error.name === "AbortError" ? "생성을 중지했습니다." : `Agent 호출에 실패했습니다: ${error.message}`,
      };
    }).finally(() => {
      if (activeRequest === controller) activeRequest = null;
      state.sending = false;
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
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.viewer) {
      state.viewer = null;
      render();
    }
  });
})();
