(function () {
  const root = document.getElementById("boi-agent-root");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";

  const employeeId = root.dataset.employeeId || new URLSearchParams(location.search).get("employee_id") || "100001";
  const pageTitle = root.dataset.pageTitle || document.title || "BoI Wiki";
  const IDLE_RESET_MS = 2 * 60 * 60 * 1000;
  let activeRequest = null;
  let restoreScrollOnce = true;
  let pageUnloading = false;

  function currentUrl() {
    return root.dataset.currentUrl || `${location.pathname}${location.search}`;
  }

  function contextFingerprintFromUrl() {
    const url = new URL(currentUrl(), location.origin);
    const path = url.pathname;
    const docMatch = path.match(/^\/docs\/([^/]+)/);
    if (docMatch) return `doc:${decodeURIComponent(docMatch[1])}`;
    const workflowMatch = path.match(/^\/workflows\/([^/]+)\/status/);
    if (workflowMatch) return `workflow:${decodeURIComponent(workflowMatch[1])}:${url.searchParams.get("trace_id") || "latest"}`;
    const rawActionMatch = path.match(/^\/actions\/raw\/([^/]+)/);
    if (rawActionMatch) return `action-raw:${decodeURIComponent(rawActionMatch[1])}`;
    const eventTypeMatch = path.match(/^\/event-types\/([^/]+)/);
    if (eventTypeMatch) return `event-type:${decodeURIComponent(eventTypeMatch[1])}`;
    if (path === "/events") return `events:${url.searchParams.get("trace_id") || url.searchParams.get("event_type") || url.searchParams.get("q") || "list"}`;
    if (path === "/actions") return `actions:${url.searchParams.get("view") || "catalog"}:${url.searchParams.get("action_key") || url.searchParams.get("q") || "all"}`;
    if (path === "/inbox") return `inbox:${url.searchParams.get("report_id") || url.searchParams.get("task_id") || url.searchParams.get("group_id") || url.searchParams.get("view") || "reports"}`;
    return `path:${path}`;
  }

  function storageSafeFingerprint(value) {
    return String(value || "home").replace(/[^A-Za-z0-9_.:-]+/g, "_").slice(0, 220);
  }

  const contextFingerprint = storageSafeFingerprint(contextFingerprintFromUrl());
  const storageKey = `boiAgent.v8.${employeeId}.${contextFingerprint}`;
  const lastContextStorageKey = `boiAgent.v8.lastContext.${employeeId}`;
  const lastContextFingerprint = sessionStorage.getItem(lastContextStorageKey) || "";
  const previousContextStorageKey = lastContextFingerprint && lastContextFingerprint !== contextFingerprint
    ? `boiAgent.v8.${employeeId}.${storageSafeFingerprint(lastContextFingerprint)}`
    : "";
  sessionStorage.setItem(lastContextStorageKey, contextFingerprint);

  function selectedText() {
    return String(window.getSelection?.().toString() || "").trim().slice(0, 1200);
  }

  function defaultState() {
    return {
      open: false,
      expanded: false,
      tab: "agent",
      suggestions: [],
      suggestionsLoading: false,
      suggestionError: "",
      signal: null,
      signals: [],
      messages: [],
      draft: "",
      busyTask: "",
      sending: false,
      answerSending: false,
      followupsLoading: false,
      currentStatus: "",
      lastActiveAt: Date.now(),
      scrollTop: 0,
      pinToBottom: true,
      previousContextStorageKey,
      viewer: null,
    };
  }

  function loadState() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
      return { ...defaultState(), ...saved, tab: "agent", suggestions: [], suggestionsLoading: false, suggestionError: "", signal: null, signals: [], busyTask: "", currentStatus: "", sending: false, answerSending: false, followupsLoading: false, previousContextStorageKey, viewer: null };
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
      lastActiveAt: state.lastActiveAt,
      scrollTop: state.scrollTop,
      pinToBottom: state.pinToBottom,
    };
    sessionStorage.setItem(storageKey, JSON.stringify(saved));
  }

  function isNearBottom(element, threshold) {
    if (!element) return true;
    const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
    return remaining <= (threshold || 96);
  }

  function captureScrollState() {
    const content = root.querySelector(".boi-agent-content");
    if (!content || !state.open || state.tab !== "agent") return;
    state.scrollTop = content.scrollTop;
    state.pinToBottom = isNearBottom(content);
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
    }).then(async (response) => {
      if (!response.ok) {
        let detail = null;
        try {
          detail = await response.json();
        } catch (_error) {
          detail = null;
        }
        const payload = detail?.detail || detail || {};
        const status = payload.status ? ` ${payload.status}` : "";
        const message = payload.message ? `: ${payload.message}` : "";
        throw new Error(`HTTP ${response.status}${status}${message}`);
      }
      return response.json();
    });
  }

  function recordActivity(activityType, target, title, metadata) {
    return api("/api/agents/boi-wiki/activity", {
      method: "POST",
      body: JSON.stringify({
        activity_type: activityType,
        target: target || "",
        title: title || "",
        metadata: metadata || {},
      }),
    }).catch(() => null);
  }

  function sseUrl(path) {
    const url = new URL(path, location.origin);
    url.searchParams.set("employee_id", employeeId);
    return url;
  }

  function parseSseBlock(block) {
    const event = { event: "message", data: "" };
    const data = [];
    String(block || "").split(/\r?\n/).forEach((line) => {
      if (line.startsWith("event:")) {
        event.event = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        data.push(line.slice(5).trimStart());
      }
    });
    event.data = data.join("\n");
    return event;
  }

  async function readAgentStream(response, handlers) {
    if (!response.body || !window.ReadableStream) {
      throw new Error("이 브라우저는 Agent 스트리밍을 지원하지 않습니다.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const rawBlock = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        dispatchSseEvent(parseSseBlock(rawBlock), handlers);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) dispatchSseEvent(parseSseBlock(buffer), handlers);
  }

  function dispatchSseEvent(event, handlers) {
    if (!event.data) return;
    let payload = {};
    try {
      payload = JSON.parse(event.data);
    } catch (_error) {
      payload = { message: event.data };
    }
    const handler = handlers[event.event];
    if (handler) handler(payload);
  }

  function formatAgentStreamError(payload) {
    const status = String(payload?.status || "agent_stream_error");
    const labels = {
      status_generation_failed: "답변을 완성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      boi_agent_router_unavailable: "답변을 완성하지 못했습니다. 질문을 조금 더 구체적으로 적어 다시 시도해 주세요.",
      native_agent_runtime_unavailable: "답변을 완성하지 못했습니다. 확인할 근거를 줄여 다시 요청해 주세요.",
      langflow_boi_agent_unavailable: "연결된 SOP/Action 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      agent_stream_error: "답변을 완성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    };
    return labels[status] || "답변을 완성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
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

  function listLineInfo(line) {
    const match = String(line || "").match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
    if (!match) return null;
    return {
      indent: match[1].replace(/\t/g, "    ").length,
      ordered: /^\d+\./.test(match[2]),
      text: match[3],
    };
  }

  function renderListItemText(rawItem) {
    const task = String(rawItem || "").match(/^\[( |x|X)\]\s+(.*)$/);
    if (task) {
      const checked = task[1].toLowerCase() === "x";
      return `<input type="checkbox" disabled${checked ? " checked" : ""}> ${renderInlineMarkdown(task[2])}`;
    }
    return renderInlineMarkdown(rawItem);
  }

  function renderListBlock(lines, startIndex, baseIndent) {
    const first = listLineInfo(lines[startIndex]);
    if (!first) return { html: "", nextIndex: startIndex };
    const ordered = first.ordered;
    const tag = ordered ? "ol" : "ul";
    const items = [];
    let i = startIndex;

    while (i < lines.length) {
      const info = listLineInfo(lines[i]);
      if (!info || info.indent < baseIndent || info.indent !== baseIndent || info.ordered !== ordered) break;
      let rawItem = info.text;
      let nestedHtml = "";
      i += 1;

      while (i < lines.length) {
        const nextInfo = listLineInfo(lines[i]);
        if (nextInfo) {
          if (nextInfo.indent > baseIndent) {
            const nested = renderListBlock(lines, i, nextInfo.indent);
            nestedHtml += nested.html;
            i = nested.nextIndex;
            continue;
          }
          break;
        }
        if (!lines[i].trim()) break;
        if (/^\s{2,}\S/.test(lines[i]) && !isLikelyTableStart(lines, i)) {
          rawItem += ` ${lines[i].trim()}`;
          i += 1;
          continue;
        }
        break;
      }
      items.push(`<li>${renderListItemText(rawItem)}${nestedHtml}</li>`);
    }

    return { html: `<${tag}>${items.join("")}</${tag}>`, nextIndex: i };
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
      const listInfo = listLineInfo(line);
      if (listInfo) {
        const list = renderListBlock(lines, i, listInfo.indent);
        parts.push(list.html);
        i = list.nextIndex - 1;
        continue;
      }
      if (/^\s*>\s?/.test(line)) {
        const quoteLines = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          quoteLines.push(lines[i].replace(/^\s*>\s?/, ""));
          i += 1;
        }
        i -= 1;
        parts.push(`<blockquote>${renderTextMarkdown(quoteLines.join("\n"))}</blockquote>`);
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
    const attrs = viewerPayload?.attrs || "";
    return `
      <div class="mermaid-diagram boi-agent-artifact" data-mermaid-state="pending" data-mermaid-source="${escapeAttr(source)}"${id}${attrs}>
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

  function looksLikeRawMarkdownHtml(value) {
    const text = String(value || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<[^>]+>/g, "\n");
    return /```/.test(text)
      || /\|\s*:?-{3,}:?\s*\|/.test(text)
      || /^\s*:?-{3,}:?\s*\|\s*:?-{3,}:?/m.test(text)
      || /^\s{0,3}#{1,6}\s+\S/m.test(text)
      || /^\s{0,3}[-*+]\s+\S/m.test(text)
      || /^\s{0,3}\d+\.\s+\S/m.test(text)
      || /^\s{0,3}(?:>|&gt;)\s*\S/m.test(text)
      || /^\s{0,3}(?:-{3,}|_{3,}|\*{3,})\s*$/m.test(text);
  }

  function shouldUseServerHtml(message, artifactMermaid) {
    const html = String(message?.html || "");
    if (!html || looksLikeRawMarkdownHtml(html)) return false;
    if (artifactMermaid?.size && /class=["'][^"']*mermaid-diagram|class=["'][^"']*\bmermaid\b/i.test(html)) {
      return false;
    }
    return true;
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
    const seenConfirmation = new Set();
    const artifacts = [...(message.artifacts || []), ...executionCardArtifacts(message)];
    return artifacts.filter((artifact) => {
      if (!artifact || typeof artifact !== "object") return false;
      if (artifact.type === "mermaid" && artifact.source) {
        const source = normalizeMermaidSource(artifact.source);
        if (seenMermaidSources.has(source)) return false;
        seenMermaidSources.add(source);
        if (markdownMermaid.has(source)) return true;
      }
      if (artifact.type === "confirmation_required") {
        const data = artifact.data || {};
        const key = `${data.operation || ""}:${JSON.stringify(data.payload || {})}`;
        if (seenConfirmation.has(key)) return false;
        seenConfirmation.add(key);
      }
      return true;
    }).map(normalizeArtifactPresentation);
  }

  function executionCardArtifacts(message) {
    const cards = message.executionCards || message.execution_cards || [];
    if (!Array.isArray(cards)) return [];
    return cards
      .filter((card) => card && typeof card === "object")
      .map((card) => ({
        type: "confirmation_required",
        role: "primary",
        display_mode: "inline",
        priority: 10,
        reason: "상태 변경 전 사용자 확인이 필요한 요청",
        user_requested: true,
        title: card.title || card.operation || "확인 필요",
        data: {
          ...card,
          operation: card.operation || card.type || "",
          payload: card.payload || {},
          primary_label: card.primary_label || card.display?.next_action || "확인 후 실행",
          message: card.message || card.display?.why_it_matters || "",
          required_role: card.required_role || card.technical_details?.required_role || "",
          permission: card.permission || {},
          display: card.display || {},
          technical_details: card.technical_details || {},
        },
      }));
  }

  function normalizeArtifactPresentation(artifact) {
    const type = String(artifact?.type || "");
    const defaults = {
      role: "primary",
      display_mode: "inline",
      priority: 10,
      reason: "요청에 맞춰 바로 확인할 산출물",
      user_requested: true,
    };
    if (!["mermaid", "gap_table", "workflow_summary", "manual_handoff_summary", "action_requirements", "task_cards", "confirmation_required", "image"].includes(type)) {
      defaults.role = "supporting";
      defaults.display_mode = "collapsed";
      defaults.priority = 60;
      defaults.reason = "답변을 보강하는 참고 자료";
      defaults.user_requested = false;
    }
    const role = ["primary", "supporting", "evidence", "diagnostic"].includes(artifact.role) ? artifact.role : defaults.role;
    const displayMode = ["inline", "collapsed", "viewer_only", "hidden_diagnostic"].includes(artifact.display_mode) ? artifact.display_mode : defaults.display_mode;
    return {
      ...artifact,
      role,
      display_mode: displayMode,
      priority: Number.isFinite(Number(artifact.priority)) ? Number(artifact.priority) : defaults.priority,
      reason: artifact.reason || defaults.reason,
      user_requested: typeof artifact.user_requested === "boolean" ? artifact.user_requested : defaults.user_requested,
      default_collapsed: Boolean(artifact.default_collapsed || role === "evidence" || role === "diagnostic" || displayMode !== "inline"),
    };
  }

  function artifactPresentationRole(artifact) {
    return normalizeArtifactPresentation(artifact).role;
  }

  function artifactDisplayMode(artifact) {
    return normalizeArtifactPresentation(artifact).display_mode;
  }

  function inlineArtifactItems(message) {
    return artifactItems(message)
      .filter((artifact) => artifactPresentationRole(artifact) === "primary" && artifactDisplayMode(artifact) === "inline")
      .sort((a, b) => Number(a.priority || 50) - Number(b.priority || 50));
  }

  function supportingArtifactItems(message) {
    return artifactItems(message)
      .filter((artifact) => {
        const role = artifactPresentationRole(artifact);
        const mode = artifactDisplayMode(artifact);
        return role !== "diagnostic" && !(role === "primary" && mode === "inline") && mode !== "hidden_diagnostic";
      })
      .sort((a, b) => Number(a.priority || 50) - Number(b.priority || 50));
  }

  function diagnosticArtifactItems(message) {
    return artifactItems(message)
      .filter((artifact) => artifactPresentationRole(artifact) === "diagnostic" || artifactDisplayMode(artifact) === "hidden_diagnostic")
      .sort((a, b) => Number(a.priority || 80) - Number(b.priority || 80));
  }

  function mermaidSourcesFromArtifacts(message) {
    const found = new Set();
    for (const artifact of message.artifacts || []) {
      if (artifact?.type === "mermaid" && artifact.source) found.add(normalizeMermaidSource(artifact.source));
    }
    return found;
  }

  function renderTaskDisplay(item) {
    const title = item.title || item.name || item.action_key || "처리할 일";
    const statusLabel = item.status_label || item.status || "확인 필요";
    const riskLabel = item.risk_label || item.priority_label || "";
    const why = item.why_it_matters || item.summary || item.description || "";
    const nextAction = item.next_action || item.recommended_next_check || "";
    const primaryUrl = item.primary_url || item.url || "";
    const primaryLabel = item.primary_label || "자세히 보기";
    return `
      <section class="boi-agent-task-display">
        <div class="boi-agent-task-title">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(statusLabel)}</span>
        </div>
        ${riskLabel ? `<small>${escapeHtml(riskLabel)}</small>` : ""}
        ${why ? `<p>${escapeHtml(why)}</p>` : ""}
        ${nextAction ? `<p><strong>다음 행동</strong> ${escapeHtml(nextAction)}</p>` : ""}
        ${primaryUrl ? `<a href="${escapeAttr(primaryUrl)}">${escapeHtml(primaryLabel)}</a>` : ""}
      </section>`;
  }

  function renderArtifactNode(artifact, viewerId) {
    const presentationAttrs = ` data-artifact-type="${escapeAttr(artifact.type || "")}" data-artifact-role="${escapeAttr(artifact.role || "")}" data-artifact-display="${escapeAttr(artifact.display_mode || "")}"`;
    if (artifact.type === "mermaid" && artifact.source) {
      return renderMermaidBlock(artifact.source, artifact.title || "Diagram", { id: viewerId, type: "mermaid", source: artifact.source, attrs: presentationAttrs });
    }
    if (artifact.type === "gap_table" && Array.isArray(artifact.data)) {
      return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "명세 점검")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${renderObjectTable(artifact.data)}</div>`;
    }
    if (artifact.type === "workflow_summary" && artifact.data) {
      const rows = Array.isArray(artifact.data) ? artifact.data : [artifact.data];
      return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "업무 흐름 요약")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${renderObjectTable(rows)}</div>`;
    }
    if (artifact.type === "manual_handoff_summary" && artifact.data) {
      const rows = Array.isArray(artifact.data) ? artifact.data : [artifact.data];
      return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "수동 조치 정리")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${rows.map((item) => renderTaskDisplay({
        title: item.title || item.action_key || "수동 조치",
        status_label: item.status_label || "조치 필요",
        why_it_matters: item.why_it_matters || item.required_evidence || "",
        next_action: item.next_action || "",
        risk_label: item.risk_label || "수동 조치",
        primary_label: "근거 보기",
        primary_url: item.doc_uri || "",
      })).join("")}</div>`;
    }
    if (artifact.type === "action_requirements" && artifact.data) {
      const rows = Array.isArray(artifact.data) ? artifact.data : [artifact.data];
      return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "필요 데이터")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${renderObjectTable(rows)}</div>`;
    }
    if (artifact.type === "task_cards" && Array.isArray(artifact.data)) {
      return `<div class="boi-agent-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "처리할 일")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div>${artifact.data.map((item) => renderTaskDisplay(item || {})).join("")}</div>`;
    }
    if (artifact.type === "confirmation_required" && artifact.data) {
      return renderConfirmationArtifact(artifact, viewerId, presentationAttrs);
    }
    if (artifact.type === "image" && artifact.url) {
      return `<figure class="boi-agent-artifact boi-agent-image-artifact" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs}><div class="boi-agent-artifact-title"><strong>${escapeHtml(artifact.title || "Image")}</strong><button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button></div><img src="${escapeAttr(artifact.url)}" alt="${escapeAttr(artifact.alt || artifact.title || "Artifact image")}"></figure>`;
    }
    return "";
  }

  function renderArtifacts(message, messageIndex) {
    const artifacts = inlineArtifactItems(message);
    if (!artifacts.length) return "";
    return `<div class="boi-agent-artifacts">${artifacts.map((artifact, artifactIndex) => renderArtifactNode(artifact, `artifact-${messageIndex}-${artifactIndex}`)).join("")}</div>`;
  }

  function renderSupportingArtifacts(message, messageIndex) {
    const artifacts = supportingArtifactItems(message);
    if (!artifacts.length) return "";
    return `<details class="boi-agent-artifact-group boi-agent-evidence-artifacts">
      <summary>근거 자료 보기 <span>${artifacts.length}개</span></summary>
      <div>${artifacts.map((artifact, artifactIndex) => renderArtifactNode(artifact, `artifact-${messageIndex}-evidence-${artifactIndex}`)).join("")}</div>
    </details>`;
  }

  function renderDiagnosticArtifacts(message, messageIndex) {
    const artifacts = diagnosticArtifactItems(message);
    if (!artifacts.length) return "";
    return `<div class="boi-agent-diagnostic-artifacts">${artifacts.map((artifact, artifactIndex) => renderArtifactNode(artifact, `artifact-${messageIndex}-diagnostic-${artifactIndex}`)).join("")}</div>`;
  }

  function renderConfirmationArtifact(artifact, viewerId, presentationAttrs) {
    const data = artifact.data || {};
    const operation = String(data.operation || "");
    const payload = data.payload && typeof data.payload === "object" ? data.payload : {};
    const canExecute = operation && Object.keys(payload).length > 0;
    const title = artifact.title || data.title || "확인 필요";
    const message = data.message || "상태 변경이나 승인 절차가 필요한 요청입니다. 내용을 확인한 뒤 명시적으로 실행해야 합니다.";
    const primaryLabel = data.primary_label || (canExecute ? "요청 실행" : "먼저 확인");
    const display = data.display && typeof data.display === "object" ? data.display : {};
    const permission = data.permission && typeof data.permission === "object" ? data.permission : {};
    const permissionAllowed = permission.allowed !== false;
    const requiredRole = data.required_role || data.technical_details?.required_role || permission.role || "";
    const statusLabel = display.status_label || (permissionAllowed ? "확인 필요" : "권한 필요");
    const riskLabel = display.risk_label || (permissionAllowed ? "명시 확인 후 실행" : `권한 필요${requiredRole ? `: ${requiredRole}` : ""}`);
    const payloadJson = JSON.stringify(payload);
    return `
      <div class="boi-agent-artifact boi-agent-confirmation-card" data-viewer-id="${escapeAttr(viewerId)}"${presentationAttrs || ""}>
        <div class="boi-agent-artifact-title">
          <strong>${escapeHtml(title)}</strong>
          <button type="button" data-open-artifact="${escapeAttr(viewerId)}">크게 보기</button>
        </div>
        <div class="boi-agent-task-status">
          <span>${escapeHtml(statusLabel)}</span>
          <small>${escapeHtml(riskLabel)}</small>
        </div>
        <p>${escapeHtml(message)}</p>
        <div class="boi-agent-confirmation-actions">
          <label class="boi-agent-approve-note">
            <span>실행 사유 / 메모</span>
            <textarea data-agent-approve-note placeholder="필요 시 승인 메모를 남깁니다. 다른 사번 대신 실행하는 예외 사유는 별도 admin_override_reason으로만 처리됩니다."></textarea>
          </label>
          ${canExecute && permissionAllowed ? `<button type="button" data-agent-approve data-operation="${escapeAttr(operation)}" data-payload="${escapeAttr(payloadJson)}">${escapeHtml(primaryLabel)}</button>` : `<span>${escapeHtml(permissionAllowed ? primaryLabel : "권한이 필요합니다")}</span>`}
        </div>
        <details class="boi-agent-technical">
          <summary>기술 세부정보</summary>
          <dl>
            ${data.route ? `<div><dt>Route</dt><dd>${escapeHtml(data.route)}</dd></div>` : ""}
            ${data.intent ? `<div><dt>Intent</dt><dd>${escapeHtml(data.intent)}</dd></div>` : ""}
            ${operation ? `<div><dt>Operation</dt><dd>${escapeHtml(operation)}</dd></div>` : ""}
            ${requiredRole ? `<div><dt>Required role</dt><dd>${escapeHtml(requiredRole)}</dd></div>` : ""}
            ${permission.reason ? `<div><dt>Permission</dt><dd>${escapeHtml(permission.reason)}</dd></div>` : ""}
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
    renderRunSummary,
    renderArtifacts,
    renderSupportingArtifacts,
    renderDiagnosticDetails,
    renderMessageFollowups,
    artifactItems,
    inlineArtifactItems,
    supportingArtifactItems,
    diagnosticArtifactItems,
    normalizeArtifactPresentation,
    listLineInfo,
    splitTableRow,
    mermaidSourcesFromMarkdown,
    mermaidSourcesFromArtifacts,
    normalizeMermaidSource,
    looksLikeRawMarkdownHtml,
    shouldUseServerHtml,
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
      workflow_explain: "SOP 실행 흐름 분석",
      gap_check: "누락 점검",
      trace_reasoning: "실행 근거 분석",
      inbox: "업무함 안내",
      manual_complete: "조치 확인",
      approval: "승인 필요",
      access_denied: "권한 확인",
    };
    const routeLabels = {
      manual_handoff: "조치 확인",
      approval_required: "승인 필요",
      inbox: "업무함 안내",
    };
    if (meta.intent && intentLabels[meta.intent]) chips.push(intentLabels[meta.intent]);
    if (!chips.length && meta.route && routeLabels[meta.route]) chips.push(routeLabels[meta.route]);
    if (!chips.length) return "";
    return `<div class="boi-agent-meta">${chips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("")}</div>`;
  }

  function toolDisplayLabel(tool) {
    return {
      ontology_search: "관련 지식 검색",
      boi_get: "BoI 문서 조회",
      action_spec_lookup: "Action 명세 확인",
      trace_context_lookup: "Trace 근거 확인",
      workflow_status: "실행 현황 확인",
      dictionary_resolve: "업무 용어 확인",
      memory_recall: "Private memory 확인",
      agent_inbox: "업무함 확인",
      route_classifier: "질문 유형 판단",
    }[tool] || "근거 확인";
  }

  function toolStatusLabel(status) {
    return {
      ok: "완료",
      empty: "결과 없음",
      failed: "실패",
    }[status] || status || "확인";
  }

  function renderRunSummary(message) {
    if (message.role !== "assistant") return "";
    const meta = message.meta || {};
    const toolTrace = Array.isArray(meta.tool_trace) ? meta.tool_trace : [];
    const coverage = meta.coverage_report && typeof meta.coverage_report === "object" ? meta.coverage_report : {};
    const guardrails = Array.isArray(meta.guardrails_applied) ? meta.guardrails_applied : [];
    if (!toolTrace.length && !Object.keys(coverage).length && !guardrails.length) return "";
    const toolRows = toolTrace.slice(0, 8).map((item) => {
      const elapsed = Number.isFinite(Number(item.elapsed_ms)) ? ` · ${Number(item.elapsed_ms)}ms` : "";
      const summary = item.summary ? `<small>${escapeHtml(item.summary)}</small>` : "";
      return `<li><strong>${escapeHtml(toolDisplayLabel(item.tool))}</strong><span>${escapeHtml(toolStatusLabel(item.status))}${elapsed}</span>${summary}</li>`;
    }).join("");
    const coverageScore = Number.isFinite(Number(coverage.coverage_score)) ? Math.round(Number(coverage.coverage_score) * 100) : null;
    const missing = Array.isArray(coverage.missing) ? coverage.missing : [];
    return `
      <section class="boi-agent-run-summary">
        <h4>Agent가 확인한 근거${coverageScore !== null ? ` · ${coverageScore}%` : ""}</h4>
        ${toolRows ? `<ul>${toolRows}</ul>` : ""}
        ${missing.length ? `<p>더 확인이 필요한 항목: ${missing.map((item) => `<code>${escapeHtml(item)}</code>`).join(" ")}</p>` : ""}
        ${guardrails.length ? `<p>권한/보안 가드레일 적용: ${guardrails.length}건</p>` : ""}
      </section>`;
  }

  function componentDisplayLabel(component) {
    return {
      router: "질문 이해 보조",
      stream_plan: "진행 상태 준비",
      answer_composer: "답변 표현 보조",
      followup_suggestions: "다음 질문 제안",
      status_writer: "진행 상태 문구",
    }[component] || "보조 기능";
  }

  function componentStatusLabel(item) {
    const status = item?.status || "";
    if (item?.recoverable === true) return "기본 답변 유지";
    return {
      failed: "확인 필요",
      invalid_output: "확인 필요",
      not_configured: "설정 확인 필요",
      status_generation_failed: "상태 문구 생략",
      boi_agent_router_unavailable: "기본 이해 경로 사용",
    }[status] || "확인";
  }

  function renderComponentDiagnostics(message) {
    const errors = Array.isArray(message.componentErrors) ? message.componentErrors : [];
    if (!errors.length) return "";
    return `
      <section class="boi-agent-run-summary compact">
        <h4>보조 기능 상태</h4>
        <ul>${errors.slice(0, 6).map((item) => `
          <li><strong>${escapeHtml(componentDisplayLabel(item.component))}</strong><span>${escapeHtml(componentStatusLabel(item))}</span></li>
        `).join("")}</ul>
      </section>`;
  }

  function renderStatusTrail(message) {
    const lines = (message.statusLines || []).filter(Boolean).slice(-5);
    if (!lines.length) return "";
    return `<details class="boi-agent-status-trail">
      <summary>진행 단계 ${lines.length}개</summary>
      <ol aria-label="Agent 진행 단계">
        ${lines.map((line, index) => `<li class="${index === lines.length - 1 ? "current" : ""}">${escapeHtml(line)}</li>`).join("")}
      </ol>
      </details>`;
  }

  function renderMessageFollowups(message) {
    if (message.role !== "assistant") return "";
    const suggestions = Array.isArray(message.suggestedQuestions)
      ? message.suggestedQuestions.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    const stateLabel = message.followupState || (suggestions.length ? "ready" : (message.followupError ? "error" : ""));
    if (stateLabel === "loading") {
      return `
        <div class="boi-agent-message-followups loading" aria-label="다음에 물어볼 질문 준비 중">
          <strong>다음에 물어볼 질문을 준비 중입니다...</strong>
          <div class="boi-agent-followup-skeleton" aria-hidden="true">
            <span></span><span></span><span></span>
          </div>
        </div>`;
    }
    if (!suggestions.length && !message.followupError) return "";
    return `
      <div class="boi-agent-message-followups ${stateLabel === "cancelled" ? "cancelled" : ""}" aria-label="다음에 물어볼 수 있는 질문">
        <strong>${message.followupError ? "추천 질문 상태" : "다음에 물어볼 수 있는 질문"}</strong>
        ${message.followupError ? `<p class="boi-agent-hint error">${escapeHtml(message.followupError)}</p>` : ""}
        ${suggestions.length ? `<div>
          ${suggestions.map((item) => `<button type="button" data-question="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}
        </div>` : ""}
      </div>`;
  }

  function renderDiagnosticDetails(message, messageIndex) {
    if (message.role !== "assistant") return "";
    const statusTrail = renderStatusTrail(message);
    const runSummary = renderRunSummary(message);
    const componentDiagnostics = renderComponentDiagnostics(message);
    const diagnosticArtifacts = renderDiagnosticArtifacts(message, messageIndex);
    if (!statusTrail && !runSummary && !componentDiagnostics && !diagnosticArtifacts) return "";
    return `<details class="boi-agent-artifact-group boi-agent-diagnostic-details">
      <summary>처리 과정 보기</summary>
      ${statusTrail}
      ${runSummary}
      ${componentDiagnostics}
      ${diagnosticArtifacts}
    </details>`;
  }

  function renderMessages() {
    if (!state.messages.length) return "";
    return `<div class="boi-agent-messages">${state.messages
      .map((message, index) => {
        const artifactMermaid = mermaidSourcesFromArtifacts(message);
        const serverHtml = shouldUseServerHtml(message, artifactMermaid) ? message.html : "";
        const answerHtml = serverHtml || renderMarkdownLite(message.text || "", { skipMermaidSources: artifactMermaid });
        const meta = message.meta || {};
        const approvalStatus = meta.approval_status ? ` data-agent-approval-status="${escapeAttr(meta.approval_status)}"` : "";
        const approvalOperation = meta.approval_operation ? ` data-agent-approval-operation="${escapeAttr(meta.approval_operation)}"` : "";
        return `
        <article class="boi-agent-message ${message.role === "user" ? "user" : "assistant"}"${approvalStatus}${approvalOperation}>
          <strong class="boi-agent-message-author">${message.role === "user" ? "You" : "BoI Agent"}</strong>
          ${renderMessageMeta(message)}
          ${message.progressText ? `<p class="boi-agent-progress">${escapeHtml(message.progressText)}</p>` : ""}
          ${answerHtml ? `<div class="boi-agent-answer" data-answer-id="answer-${index}">${answerHtml}</div>` : ""}
          ${message.role === "assistant" && answerHtml ? `<div class="boi-agent-answer-actions"><button type="button" data-open-answer="answer-${index}">답변 크게 보기</button></div>` : ""}
          ${renderArtifacts(message, index)}
          ${renderSupportingArtifacts(message, index)}
          ${renderDiagnosticDetails(message, index)}
          ${renderMessageFollowups(message)}
          ${renderLinks(message.links || [])}
        </article>`;
      })
      .join("")}</div>`;
  }

  function render() {
    captureScrollState();
    syncViewportPosition();
    persistState();
    const launcherStatus = state.answerSending ? state.currentStatus || "" : (state.signal?.message || "무엇을 도와드릴까요");
    root.innerHTML = `
      <button class="boi-agent-launcher" type="button" aria-expanded="${state.open ? "true" : "false"}">
        <span class="boi-agent-launcher-copy">
          <span>BoI Agent</span>
          <small aria-live="polite">${escapeHtml(launcherStatus)}</small>
        </span>
        <img class="boi-agent-pet" src="/static/assets/boi-agent-pet.png" alt="" loading="lazy" decoding="async">
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
        ${state.answerSending && state.currentStatus ? `<div class="boi-agent-live-status" aria-live="polite"><strong>진행 상태</strong><span>${escapeHtml(state.currentStatus)}</span></div>` : ""}
        <div class="boi-agent-content">${renderTab()}</div>
      </section>
      ${renderViewer()}
    `;
    bind();
    restoreOrPinScroll();
    root.dispatchEvent(new CustomEvent("boi:markdown-rendered", { bubbles: true }));
  }

  function renderTab() {
      return `
      <section class="boi-agent-context-card">
        <strong>현재 페이지를 보고 있습니다</strong>
        <p>${escapeHtml(pageTitle)}</p>
      </section>
      ${!state.messages.length ? `<div class="boi-agent-suggestions">
        ${state.suggestions.map((item) => `<button type="button" data-question="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}
        ${state.suggestionsLoading ? `<span class="boi-agent-suggestions-loading" aria-live="polite">추천 질문 생성 중...</span>` : ""}
      </div>` : ""}
      ${!state.messages.length && state.previousContextStorageKey ? `<button type="button" class="boi-agent-previous-context" data-load-previous-context="true">이전 화면 대화 보기</button>` : ""}
      ${state.suggestionError ? `<p class="boi-agent-hint error">${escapeHtml(state.suggestionError)}</p>` : ""}
      ${renderMessages()}
      <form class="boi-agent-chat-form">
        <textarea name="question" placeholder="현재 페이지 기준으로 묻거나, SOP/Event/Action을 찾아보세요." required>${escapeHtml(state.draft)}</textarea>
        <div class="boi-agent-form-actions">
          ${state.answerSending ? `<button type="button" class="boi-agent-stop">중지</button>` : ""}
          <button type="submit" ${state.answerSending ? "disabled" : ""}>Agent에게 묻기</button>
        </div>
      </form>
      <p class="boi-agent-hint">Enter로 전송, Shift+Enter로 줄바꿈</p>
    `;
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
      if (state.signal && state.open) {
        state.tab = state.signal.target_tab || "agent";
        if (state.signal.signal_id) {
          api(`/api/agents/boi-wiki/signals/${encodeURIComponent(state.signal.signal_id)}/seen`, {
            method: "POST",
            body: JSON.stringify({ note: "Pet launcher signal opened", metadata: { type: state.signal.type || "" } }),
          }).catch(() => null);
        }
      }
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
      state.answerSending = false;
      state.followupsLoading = false;
      state.currentStatus = "";
      state.scrollTop = 0;
      state.pinToBottom = true;
      render();
    });
    root.querySelector("[data-load-previous-context]")?.addEventListener("click", () => {
      try {
        const saved = JSON.parse(sessionStorage.getItem(state.previousContextStorageKey) || "{}");
        state.messages = Array.isArray(saved.messages) ? saved.messages : [];
        state.draft = "";
        state.scrollTop = 0;
        state.pinToBottom = true;
      } catch (_error) {
        state.previousContextStorageKey = "";
      }
      render();
    });
    root.querySelector(".boi-agent-stop")?.addEventListener("click", () => {
      if (activeRequest) activeRequest.abort();
    });
    const content = root.querySelector(".boi-agent-content");
    content?.addEventListener("scroll", () => {
      state.scrollTop = content.scrollTop;
      state.pinToBottom = isNearBottom(content);
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
    root.querySelectorAll("[data-open-artifact]").forEach((button) => {
      button.addEventListener("click", () => openArtifact(button.dataset.openArtifact || ""));
    });
    root.querySelectorAll("[data-open-answer]").forEach((button) => {
      button.addEventListener("click", () => openAnswer(button.dataset.openAnswer || ""));
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
        const note = button.closest(".boi-agent-confirmation-card")?.querySelector("[data-agent-approve-note]")?.value || "";
        state.busyTask = `approve:${operation}`;
        render();
        api("/api/agents/boi-wiki/approve", {
          method: "POST",
          body: JSON.stringify({
            operation,
            payload,
            user_confirmed: true,
            note,
          }),
        }).then((body) => {
          showAgentMessage(agentApprovalResultMessage(operation, body), [], {
            approval_status: body?.status || "",
            approval_operation: operation,
          });
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
    if (restoreScrollOnce) {
      if (state.open && state.tab === "agent" && state.pinToBottom) {
        content.scrollTop = content.scrollHeight;
      } else if (state.scrollTop) {
        content.scrollTop = state.scrollTop;
      }
      restoreScrollOnce = false;
      return;
    }
    if (state.open && state.tab === "agent") {
      if (state.answerSending || state.pinToBottom) {
        content.scrollTop = content.scrollHeight;
      } else {
        content.scrollTop = state.scrollTop;
      }
    }
  }

  function stickToBottomAfterLayout() {
    if (!state.open || state.tab !== "agent" || !state.pinToBottom) return;
    window.requestAnimationFrame(() => {
      const content = root.querySelector(".boi-agent-content");
      if (!content) return;
      content.scrollTop = content.scrollHeight;
      state.scrollTop = content.scrollTop;
      state.pinToBottom = true;
      persistState();
    });
  }

  function openArtifact(id) {
    const node = root.querySelector(`[data-viewer-id="${CSS.escape(id)}"]`);
    if (!node) return;
    recordActivity("artifact_open", currentUrl(), node.querySelector("strong")?.textContent || "Artifact 크게 보기", {
      artifact_id: id,
      artifact_type: node.classList.contains("mermaid-diagram") ? "mermaid" : "artifact",
    });
    if (node.classList.contains("mermaid-diagram")) {
      const source = node.dataset.mermaidSource
        || node.querySelector(".mermaid-source-fallback code")?.textContent
        || node.querySelector(".mermaid")?.textContent
        || "";
      state.viewer = {
        title: node.querySelector("strong")?.textContent || "Diagram",
        html: renderMermaidBlock(source, node.querySelector("strong")?.textContent || "Diagram", null),
      };
      render();
      return;
    }
    const clone = node.cloneNode(true);
    clone.querySelectorAll("[data-open-artifact]").forEach((button) => button.remove());
    state.viewer = {
      title: clone.querySelector("strong")?.textContent || "Artifact",
      html: clone.outerHTML,
    };
    render();
  }

  function openAnswer(id) {
    const node = root.querySelector(`[data-answer-id="${CSS.escape(id)}"]`);
    if (!node) return;
    recordActivity("answer_open", currentUrl(), "답변 크게 보기", { answer_id: id });
    const clone = node.cloneNode(true);
    clone.removeAttribute("data-answer-id");
    state.viewer = {
      title: "BoI Agent 답변",
      html: `<div class="boi-agent-answer-viewer">${clone.outerHTML}</div>`,
    };
    render();
  }

  function openImageArtifact(image) {
    const src = image.getAttribute("src") || "";
    if (!src) return;
    const alt = image.getAttribute("alt") || "Image";
    recordActivity("artifact_open", currentUrl(), alt, { artifact_type: "image", src });
    state.viewer = {
      title: alt,
      html: `<figure class="boi-agent-image-viewer"><img src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"></figure>`,
    };
    render();
  }

  function showAgentMessage(text, links, meta) {
    state.messages.push({ role: "assistant", text, links: links || [], meta: meta || {} });
    state.open = true;
    state.tab = "agent";
    render();
  }

  function nestedValue(source, path) {
    return path.split(".").reduce((value, key) => {
      if (!value || typeof value !== "object") return "";
      return value[key] || "";
    }, source);
  }

  function agentApprovalResultMessage(operation, body) {
    const messages = {
      event_publish: "이벤트 발행 요청을 보냈습니다.",
      publish_event: "이벤트 발행 요청을 보냈습니다.",
      workflow_start: "업무 흐름 시작 요청을 보냈습니다.",
      start_workflow: "업무 흐름 시작 요청을 보냈습니다.",
      action_invoke: "Action 실행 요청을 보냈습니다.",
      invoke_action: "Action 실행 요청을 보냈습니다.",
      manual_handoff_complete: "조치 완료 기록을 남겼습니다.",
      manual_complete: "조치 완료 기록을 남겼습니다.",
      event_type_draft: "이벤트 유형 초안을 만들었습니다.",
      create_event_type_draft: "이벤트 유형 초안을 만들었습니다.",
      event_type_draft_apply: "이벤트 유형 초안을 운영 목록에 반영했습니다.",
      apply_event_type_draft: "이벤트 유형 초안을 운영 목록에 반영했습니다.",
      promotion_submit: "공유 요청을 제출했습니다.",
      submit_promotion: "공유 요청을 제출했습니다.",
    };
    const statusLabels = {
      draft_created: "초안 생성 완료",
      draft_applied: "운영 목록 반영 완료",
      applied: "반영 완료",
      completed: "완료 기록 저장",
      invoked: "요청 접수",
      event_published: "이벤트 발행 완료",
      published: "게시 요청 접수",
      submitted: "제출 완료",
    };
    const statusLabel = statusLabels[body?.status] || "";
    const status = statusLabel ? ` 처리 결과: ${statusLabel}.` : "";
    const draftBoiId = nestedValue(body, "draft.draft_boi_id") || nestedValue(body, "result.draft.draft_boi_id");
    const draftBoiUrl = nestedValue(body, "draft.draft_boi_url") || nestedValue(body, "result.draft.draft_boi_url");
    const draftDocUrl = draftBoiId ? `/docs/${encodeURIComponent(draftBoiId)}?employee_id=${encodeURIComponent(employeeId)}` : "";
    const url = nestedValue(body, "result.workflow_status_url")
      || nestedValue(body, "result.status_url")
      || nestedValue(body, "result.raw_url")
      || nestedValue(body, "draft.url")
      || draftBoiUrl
      || draftDocUrl;
    const link = url ? ` [상태 보기](${url})` : "";
    return `${messages[operation] || "요청을 처리했습니다."}${status}${link}`;
  }

  function ask(question) {
    if (!question.trim() || state.answerSending) return;
    if (Date.now() - Number(state.lastActiveAt || 0) > IDLE_RESET_MS) {
      state.messages = [];
      state.scrollTop = 0;
      state.pinToBottom = true;
    }
    const controller = new AbortController();
    activeRequest = controller;
    const statusLines = [];
    let streamedText = "";
    let streamError = "";
    let finalBody = null;
    let answerReadyBody = null;
    const conversationContext = state.messages.slice(-10).map((item) => ({
      role: item.role,
      content: item.text,
      artifacts: item.artifacts || [],
      links: item.links || [],
      suggested_questions: item.suggestedQuestions || [],
      evidence_ledger: item.evidenceLedger || [],
      affordances: item.affordances || [],
      work_context_summary: item.workContextSummary || {},
      goal_model: item.goalModel || {},
      response_profile: item.responseProfile || "",
      component_errors: item.componentErrors || [],
      semantic_route: item.semanticRoute || {},
      related_item_context: item.relatedItemContext || {},
      page_fingerprint: item.pageFingerprint || contextFingerprint,
      created_at: item.createdAt || "",
    }));
    state.draft = "";
    state.sending = true;
    state.answerSending = true;
    state.followupsLoading = false;
    state.lastActiveAt = Date.now();
    state.currentStatus = "";
    state.pinToBottom = true;
    state.messages.push({ role: "user", text: question, createdAt: new Date().toISOString(), pageFingerprint: contextFingerprint });
    const pendingIndex = state.messages.push({ role: "assistant", text: "", progressText: "", createdAt: new Date().toISOString(), pageFingerprint: contextFingerprint }) - 1;
    state.open = true;
    state.tab = "agent";
    render();
    function updateAssistantFromBody(body, options = {}) {
      const responseStatusUpdates = Array.isArray(body.status_updates) ? body.status_updates : (Array.isArray(body.status_events) ? body.status_events : []);
      const finalStatusLines = responseStatusUpdates.length
        ? responseStatusUpdates.map((item) => item?.message || "").filter(Boolean).slice(-6)
        : statusLines.slice(-6);
      const previous = state.messages[pendingIndex] || {};
      const previousComponentErrors = Array.isArray(previous.componentErrors) ? previous.componentErrors : [];
      const bodyComponentErrors = Array.isArray(body.component_errors) ? body.component_errors : [];
      const componentErrorKeys = new Set();
      const componentErrors = [...previousComponentErrors, ...bodyComponentErrors].filter((item) => {
        const key = JSON.stringify({
          component: item?.component || "",
          status: item?.status || "",
          message: item?.message || "",
        });
        if (componentErrorKeys.has(key)) return false;
        componentErrorKeys.add(key);
        return true;
      });
      state.messages[pendingIndex] = {
        role: "assistant",
        text: body.display_markdown || body.answer_markdown || streamedText || "",
        html: body.answer_html || "",
        rawText: body.answer_markdown || "",
        links: body.links || [],
        statusLines: finalStatusLines.length ? finalStatusLines : statusLines.slice(-6),
        meta: {
          route: body.route,
          intent: body.intent || body.context_summary?.intent,
          used_backend: body.used_backend,
          router_backend: body.router_backend,
          latency_ms: body.latency_ms,
          tool_trace: body.tool_trace || [],
          status_updates: responseStatusUpdates,
          status_events: responseStatusUpdates,
          coverage_report: body.coverage_report || {},
          guardrails_applied: body.guardrails_applied || [],
        },
        artifacts: body.artifacts || [],
        executionCards: body.execution_cards || [],
        evidenceLedger: body.evidence_ledger || [],
        affordances: body.affordances || [],
        workContextSummary: body.work_context_summary || {},
        goalModel: body.goal_model || {},
        responseProfile: body.response_profile || "",
        semanticRoute: body.semantic_route || {},
        relatedItemContext: body.related_item_context || {},
        componentErrors,
        suggestedQuestions: Array.isArray(options.suggestedQuestions) ? options.suggestedQuestions : (body.suggested_questions || []),
        followupState: options.followupState || (Array.isArray(options.suggestedQuestions) && options.suggestedQuestions.length ? "ready" : previous.followupState || ""),
        followupError: options.followupError || previous.followupError || "",
      };
    }
    fetch(sseUrl("/api/agents/boi-wiki/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        question,
        selected_text: selectedText(),
        current_url: currentUrl(),
        page_context: { title: pageTitle },
        conversation: conversationContext,
      }),
    }).then(async (response) => {
      if (!response.ok) {
        let payload = null;
        try {
          payload = await response.json();
        } catch (_error) {
          payload = null;
        }
        const detail = payload?.detail || payload || { status: "agent_stream_error", message: `HTTP ${response.status}` };
        throw new Error(formatAgentStreamError(detail));
      }
      await readAgentStream(response, {
        accepted(payload) {
          const message = payload.message || "요청을 받았습니다.";
          state.currentStatus = message;
          state.messages[pendingIndex] = {
            ...state.messages[pendingIndex],
            progressText: message,
            statusLines: [message],
          };
          render();
        },
        status(payload) {
          const message = payload.message || "";
          if (!message) return;
          statusLines.push(message);
          state.currentStatus = message;
          state.messages[pendingIndex] = {
            ...state.messages[pendingIndex],
            text: streamedText,
            progressText: message,
            statusLines: statusLines.slice(-6),
          };
          render();
        },
        answer_delta(payload) {
          streamedText += payload.delta || "";
          state.messages[pendingIndex] = {
            ...state.messages[pendingIndex],
            text: streamedText,
            progressText: statusLines[statusLines.length - 1] || "",
          };
          render();
        },
        diagnostic(payload) {
          const existing = state.messages[pendingIndex] || {};
          const existingComponentErrors = Array.isArray(existing.componentErrors) ? existing.componentErrors : [];
          state.messages[pendingIndex] = {
            ...existing,
            componentErrors: [...existingComponentErrors, payload],
          };
          render();
        },
        answer_ready(payload) {
          answerReadyBody = payload;
          updateAssistantFromBody(payload, { suggestedQuestions: [], followupState: "loading", followupError: "" });
          state.answerSending = false;
          state.sending = false;
          state.followupsLoading = true;
          if (activeRequest === controller) activeRequest = null;
          state.currentStatus = "";
          render();
        },
        followups(payload) {
          const existing = state.messages[pendingIndex] || {};
          if (payload.ok === false) {
            state.messages[pendingIndex] = {
              ...existing,
              followupError: `추천 질문 생성 장애: ${payload.message || payload.status || "상태를 확인해주세요."}`,
              followupState: "error",
              suggestedQuestions: [],
            };
          } else {
            state.messages[pendingIndex] = {
              ...existing,
              suggestedQuestions: payload.suggested_questions || [],
              followupState: "ready",
              followupError: "",
            };
          }
          state.followupsLoading = false;
          render();
        },
        final(payload) {
          finalBody = payload;
        },
        error(payload) {
          streamError = formatAgentStreamError(payload);
        },
      });
      if (streamError) throw new Error(streamError);
      if (!finalBody) throw new Error("Agent 응답이 완료되지 않았습니다.");
      const body = finalBody;
      state.pinToBottom = true;
      updateAssistantFromBody(body, {
        suggestedQuestions: body.suggested_questions || [],
        followupState: (body.suggested_questions || []).length ? "ready" : (state.messages[pendingIndex]?.followupState || ""),
      });
      state.followupsLoading = false;
      if (activeRequest === controller) {
        state.answerSending = false;
        state.sending = false;
        activeRequest = null;
      }
      state.currentStatus = "";
      if (!state.messages.length) refreshSuggestions();
    }).catch((error) => {
      if (pageUnloading) {
        const pending = state.messages[pendingIndex] || {};
        if (pending.role === "assistant" && !pending.text && !pending.rawText && !pending.artifacts?.length) {
          state.messages.splice(pendingIndex, 1);
        }
        if (activeRequest === controller) {
          state.sending = false;
          state.answerSending = false;
          state.currentStatus = "";
        }
        persistState();
        return;
      }
      const message = String(error.message || "");
      if (error.name === "AbortError" && answerReadyBody) {
        const existing = state.messages[pendingIndex] || {};
        state.messages[pendingIndex] = {
          ...existing,
          followupState: "cancelled",
          followupError: "후속 질문 생성을 중지했습니다.",
          suggestedQuestions: [],
          progressText: "",
        };
        state.currentStatus = "";
        return;
      }
      state.messages[pendingIndex] = {
        role: "assistant",
        text: error.name === "AbortError" ? "생성을 중지했습니다." : (message || "답변을 완성하지 못했습니다. 잠시 후 다시 시도해 주세요."),
      };
      state.currentStatus = "";
      if (activeRequest === controller) {
        state.answerSending = false;
        state.sending = false;
      }
    }).finally(() => {
      if (pageUnloading) return;
      if (activeRequest === controller) {
        activeRequest = null;
        state.sending = false;
        state.answerSending = false;
        state.currentStatus = "";
      }
      render();
    });
  }


  function refreshSignals() {
    const url = new URL("/api/agents/boi-wiki/signals", location.origin);
    url.searchParams.set("current_url", currentUrl());
    return api(`${url.pathname}${url.search}`).then((body) => {
      state.signals = body.signals || [];
      state.signal = state.signals[0] || null;
    }).catch(() => {
      state.signals = [];
      state.signal = null;
    });
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function refreshSuggestions(attempt = 0) {
    state.suggestionsLoading = true;
    if (state.open && state.tab === "agent") render();
    return api("/api/agents/boi-wiki/suggestions", {
      method: "POST",
      body: JSON.stringify({ current_url: currentUrl(), page_context: { title: pageTitle } }),
    }).then((body) => {
      const suggestions = Array.isArray(body.suggestions) ? body.suggestions.filter(Boolean) : [];
      if (!suggestions.length) {
        throw new Error(body.status || "empty_suggestions");
      }
      state.suggestions = suggestions;
      state.suggestionError = "";
      state.suggestionsLoading = false;
      render();
    }).catch((error) => {
      if (attempt < 2) {
        return delay(500 * (attempt + 1)).then(() => refreshSuggestions(attempt + 1));
      }
      if (!state.suggestions.length) {
        state.suggestionError = `추천 질문을 생성하지 못했습니다. Agent 상태를 확인해주세요. (${String(error.message || error)})`;
      }
      state.suggestionsLoading = false;
      render();
    });
  }

  function closeAgentForLinkNavigation(event) {
    const target = event.target;
    const link = target instanceof Element ? target.closest("a[href]") : null;
    if (!link || !root.contains(link)) return;
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.dataset.keepAgentOpen === "true") return;
    const href = (link.getAttribute("href") || "").trim();
    if (!href || href.toLowerCase().startsWith("javascript:")) return;
    const linkTarget = (link.getAttribute("target") || "").toLowerCase();
    if (linkTarget === "_blank") return;
    state.open = false;
    state.viewer = null;
    persistState();
    window.setTimeout(() => {
      if (!pageUnloading && !state.open) render();
    }, 0);
  }

  render();
  Promise.allSettled([
    refreshSuggestions(),
    refreshSignals(),
  ]).finally(render);

  window.visualViewport?.addEventListener("resize", syncViewportPosition);
  window.visualViewport?.addEventListener("scroll", syncViewportPosition);
  window.addEventListener("resize", syncViewportPosition);
  root.addEventListener("click", (event) => {
    const button = event.target?.closest?.("[data-question]");
    if (!button || !root.contains(button)) return;
    event.preventDefault();
    const question = button.dataset.question || "";
    recordActivity("followup_click", currentUrl(), question, { source: "pet_agent" });
    ask(question);
  });
  root.addEventListener("click", closeAgentForLinkNavigation);
  document.addEventListener("click", (event) => {
    const trigger = event.target?.closest?.("[data-boi-agent-question]");
    if (!trigger) return;
    event.preventDefault();
    const question = trigger.dataset.boiAgentQuestion || "";
    if (!question) return;
    state.open = true;
    state.tab = "agent";
    render();
    ask(question);
  });
  document.addEventListener("boi:mermaid-rendered", stickToBottomAfterLayout);
  window.addEventListener("pagehide", () => {
    pageUnloading = true;
    if (activeRequest) activeRequest.abort();
    persistState();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (state.viewer) {
      state.viewer = null;
      render();
      return;
    }
    if (state.open) {
      state.open = false;
      render();
    }
  });
  document.addEventListener("pointerdown", (event) => {
    if (!state.open || state.viewer) return;
    const target = event.target;
    if (target instanceof Node && !root.contains(target)) {
      state.open = false;
      render();
    }
  });
})();
