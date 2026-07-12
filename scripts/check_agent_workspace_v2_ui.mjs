#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function argsOf(argv) {
  const args = {
    baseUrl: "http://127.0.0.1:8765",
    employeeId: "100001",
    timeoutMs: 120000,
    desktopWidth: 1440,
    desktopHeight: 900,
    screenshot: ".tmp/agent-v2-ui-desktop.png",
    focusScreenshot: ".tmp/agent-v2-ui-focus.png",
    mobileScreenshot: ".tmp/agent-v2-ui-mobile.png",
    launcherScreenshot: ".tmp/agent-v2-ui-launcher.png",
    launcherOnly: false,
    surfaceOnly: false,
    mermaidOnly: false,
    starterOnly: false,
    sessionId: "",
    artifactId: "",
    expectArtifactActions: false,
    expectWorkflowDraft: false,
    strict: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--base-url") args.baseUrl = argv[++index];
    else if (value === "--employee-id") args.employeeId = argv[++index];
    else if (value === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (value === "--width") args.desktopWidth = Number(argv[++index] || args.desktopWidth);
    else if (value === "--height") args.desktopHeight = Number(argv[++index] || args.desktopHeight);
    else if (value === "--screenshot") args.screenshot = argv[++index];
    else if (value === "--focus-screenshot") args.focusScreenshot = argv[++index];
    else if (value === "--mobile-screenshot") args.mobileScreenshot = argv[++index];
    else if (value === "--launcher-screenshot") args.launcherScreenshot = argv[++index];
    else if (value === "--launcher-only") args.launcherOnly = true;
    else if (value === "--surface-only") args.surfaceOnly = true;
    else if (value === "--mermaid-only") args.mermaidOnly = true;
    else if (value === "--starter-only") args.starterOnly = true;
    else if (value === "--session-id") args.sessionId = argv[++index];
    else if (value === "--artifact-id") args.artifactId = argv[++index];
    else if (value === "--expect-artifact-actions") args.expectArtifactActions = true;
    else if (value === "--expect-workflow-draft") args.expectWorkflowDraft = true;
    else if (value === "--strict") args.strict = true;
  }
  return args;
}

function chromePath() {
  const candidates = [
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  const found = candidates.find((item) => existsSync(item));
  if (!found) throw new Error("Chrome/Chromium binary not found");
  return found;
}

function getJson(url, timeoutMs = 1500) {
  return new Promise((resolve, reject) => {
    const request = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try { resolve(JSON.parse(body)); }
        catch (error) { reject(error); }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`timeout: ${url}`)));
  });
}

async function waitJson(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try { return await getJson(url); }
    catch (error) { lastError = error; await sleep(150); }
  }
  throw lastError || new Error(`timeout: ${url}`);
}

class Cdp {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const pending = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message || JSON.stringify(message.error)));
        else pending.resolve(message.result || {});
        return;
      }
      for (const listener of this.listeners.get(message.method) || []) listener(message.params || {});
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(listener);
  }

  once(method) {
    return new Promise((resolve) => {
      const handler = (payload) => {
        this.listeners.get(method)?.delete(handler);
        resolve(payload);
      };
      this.on(method, handler);
    });
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "browser expression failed");
    }
    return result.result?.value;
  }

  close() { this.ws?.close(); }
}

async function waitUntil(cdp, expression, timeoutMs, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await cdp.eval(expression);
    if (lastValue) return lastValue;
    await sleep(intervalMs);
  }
  throw new Error(`timeout waiting for ${expression}; last=${JSON.stringify(lastValue)}`);
}

async function navigate(cdp, url) {
  const loaded = cdp.once("Page.loadEventFired");
  await cdp.send("Page.navigate", { url });
  await loaded;
  await waitUntil(cdp, `document.readyState === "complete" && !!document.querySelector("[data-agent-v2-workspace]")`, 20000);
}

async function openPet(cdp) {
  await cdp.eval(`document.querySelector("[data-agent-v2-open]")?.click()`);
  await waitUntil(cdp, `!document.querySelector("[data-agent-v2-surface]")?.hidden`, 10000);
}

async function submit(cdp, question, timeoutMs) {
  const before = await cdp.eval(`document.querySelectorAll(".agent-v2-message.assistant").length`);
  await cdp.eval(`(() => {
    const form = document.querySelector("[data-agent-v2-form]");
    const input = form?.elements.question;
    if (!form || !input) return false;
    input.value = ${JSON.stringify(question)};
    input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: input.value }));
    form.requestSubmit();
    return true;
  })()`);
  await waitUntil(
    cdp,
    `(() => {
      const form = document.querySelector("[data-agent-v2-form]");
      const assistants = document.querySelectorAll(".agent-v2-message.assistant");
      const latest = assistants[assistants.length - 1];
      return assistants.length > ${before} && (latest?.textContent || "").trim().length > 20 && !form?.elements.question.disabled;
    })()`,
    timeoutMs,
    250,
  );
}

async function screenshot(cdp, path) {
  if (!path) return;
  mkdirSync(dirname(path), { recursive: true });
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: false,
  });
  writeFileSync(path, Buffer.from(result.data, "base64"));
}

async function main() {
  const args = argsOf(process.argv);
  const profile = mkdtempSync(join(tmpdir(), "boi-agent-v2-ui-"));
  const port = 9550 + Math.floor(Math.random() * 300);
  const child = spawn(chromePath(), [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  let cdp;
  const consoleErrors = [];
  const failedRequests = [];
  const turnRequests = [];
  try {
    await waitJson(`http://127.0.0.1:${port}/json/version`, 12000);
    const targets = await waitJson(`http://127.0.0.1:${port}/json/list`, 5000);
    const target = targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    if (!target) throw new Error("Chrome page target missing");
    cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.connect();
    await Promise.all([cdp.send("Page.enable"), cdp.send("Runtime.enable"), cdp.send("Network.enable")]);
    cdp.on("Runtime.exceptionThrown", (event) => consoleErrors.push(event.exceptionDetails?.exception?.description || event.exceptionDetails?.text || "runtime exception"));
    cdp.on("Network.loadingFailed", (event) => {
      if (!String(event.errorText || "").includes("ERR_ABORTED")) failedRequests.push(event.errorText || event.requestId);
    });
    cdp.on("Network.requestWillBeSent", (event) => {
      if (String(event.request?.url || "").includes("/api/v2/agent/turns")) turnRequests.push(event.request.url);
    });
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: args.desktopWidth,
      height: args.desktopHeight,
      deviceScaleFactor: 1,
      mobile: false,
    });

    if (args.artifactId) {
      const artifactUrl = `${args.baseUrl}/agent?employee_id=${args.employeeId}&session=${encodeURIComponent(args.sessionId)}&artifact=${encodeURIComponent(args.artifactId)}`;
      await navigate(cdp, artifactUrl);
      await waitUntil(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid][data-mermaid-state="rendered"] svg')`, 30000);
      await sleep(600);
      const desktop = await cdp.eval(`(() => {
        const diagram = document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid]');
        const svg = diagram?.querySelector("svg");
        const bounds = svg?.getBoundingClientRect();
        const nodeLines = [...(svg?.querySelectorAll("g.node tspan") || [])];
        const nodeLabels = nodeLines.length ? nodeLines : [...(svg?.querySelectorAll("g.node text") || [])];
        const edgeLines = [...(svg?.querySelectorAll("g.edgeLabel tspan") || [])];
        const edgeLabels = edgeLines.length ? edgeLines : [...(svg?.querySelectorAll("g.edgeLabel text") || [])];
        const minHeight = (items) => items.length ? Math.min(...items.map((item) => item.getBoundingClientRect().height).filter((height) => height > 1)) : 0;
        const artifactTitle = document.querySelector("[data-agent-v2-artifact-title]");
        const artifactTitleBounds = artifactTitle?.getBoundingClientRect();
        return {
          brand: document.querySelector(".agent-surface-heading > span")?.textContent.trim() || "",
          title: document.querySelector("[data-agent-v2-artifact-title]")?.textContent.trim() || "",
          titleWidth: Math.round(artifactTitleBounds?.width || 0),
          titleHeight: Math.round(artifactTitleBounds?.height || 0),
          titleDisplay: artifactTitle ? getComputedStyle(artifactTitle).display : "",
          state: diagram?.dataset.mermaidState || "",
          viewMode: diagram?.dataset.viewMode || "",
          zoomLabel: diagram?.querySelector("[data-mermaid-zoom]")?.textContent.trim() || "",
          nodeTextHeight: minHeight(nodeLabels),
          edgeTextHeight: minHeight(edgeLabels),
          width: Math.round(bounds?.width || 0),
          height: Math.round(bounds?.height || 0),
          workbenchWidth: Math.round(document.querySelector("[data-agent-v2-workbench]")?.getBoundingClientRect().width || 0),
          focusControlVisible: (() => { const node = document.querySelector("[data-agent-v2-artifact-focus]"); return !!node && !node.hidden && getComputedStyle(node).display !== "none"; })(),
          workflowDraft: !!document.querySelector(".agent-v2-workflow-result"),
          taskCandidates: document.querySelectorAll(".agent-v2-task-candidate").length,
          fullSopEditor: (() => {
            const node = document.querySelector("[data-agent-v2-full-editor]");
            return !!node && !node.hidden && getComputedStyle(node).display !== "none";
          })(),
          taskAction: !!diagram?.querySelector('[data-v2-mermaid-action="split_tasks"]'),
          sopAction: !!diagram?.querySelector('[data-v2-mermaid-action="create_sop_draft"]'),
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        };
      })()`);
      await cdp.eval(`document.querySelector("[data-agent-v2-artifact-focus]")?.click()`);
      await waitUntil(cdp, `document.querySelector("[data-agent-v2-workspace]")?.classList.contains("artifact-focus-open")`, 5000);
      await sleep(250);
      const focused = await cdp.eval(`(() => {
        const artifacts = document.querySelector("[data-agent-v2-artifact-list]");
        const canvas = artifacts?.querySelector(".mermaid-v2-canvas");
        const svg = canvas?.querySelector("svg");
        return {
          active: document.querySelector("[data-agent-v2-workspace]")?.classList.contains("artifact-focus-open") || false,
          conversationHidden: getComputedStyle(document.querySelector(".agent-surface-conversation")).display === "none",
          workbenchWidth: Math.round(document.querySelector("[data-agent-v2-workbench]")?.getBoundingClientRect().width || 0),
          outerOverflow: getComputedStyle(artifacts).overflowY,
          canvasOverflow: getComputedStyle(canvas).overflow,
          svgWidth: Math.round(svg?.getBoundingClientRect().width || 0),
        };
      })()`);
      await screenshot(cdp, args.focusScreenshot);
      await cdp.eval(`document.querySelector('[data-mermaid-view="fit"]')?.click()`);
      await sleep(150);
      const fitView = await cdp.eval(`(() => {
        const diagram = document.querySelector("[data-v2-mermaid]");
        const canvas = diagram?.querySelector(".mermaid-v2-canvas");
        return { mode: diagram?.dataset.viewMode || "", zoom: diagram?.querySelector("[data-mermaid-zoom]")?.textContent.trim() || "", fitsWidth: canvas ? canvas.scrollWidth <= canvas.clientWidth + 3 : false };
      })()`);
      await cdp.eval(`document.querySelector('[data-mermaid-view="read"]')?.click()`);
      await sleep(150);
      const centerBefore = await cdp.eval(`(() => {
        const canvas = document.querySelector(".mermaid-v2-canvas");
        canvas.scrollLeft = Math.max(0, (canvas.scrollWidth - canvas.clientWidth) / 2);
        canvas.scrollTop = Math.max(0, (canvas.scrollHeight - canvas.clientHeight) / 2);
        return { x:(canvas.scrollLeft + canvas.clientWidth / 2) / canvas.scrollWidth, y:(canvas.scrollTop + canvas.clientHeight / 2) / canvas.scrollHeight };
      })()`);
      await cdp.eval(`document.querySelector('[data-mermaid-view="in"]')?.click()`);
      await sleep(150);
      const centerAfter = await cdp.eval(`(() => {
        const canvas = document.querySelector(".mermaid-v2-canvas");
        return { x:(canvas.scrollLeft + canvas.clientWidth / 2) / canvas.scrollWidth, y:(canvas.scrollTop + canvas.clientHeight / 2) / canvas.scrollHeight };
      })()`);
      await cdp.eval(`document.querySelector('[data-mermaid-view="read"]')?.click()`);
      await sleep(150);
      await cdp.eval(`document.dispatchEvent(new KeyboardEvent("keydown", { key:"Escape", bubbles:true }))`);
      await waitUntil(cdp, `!document.querySelector("[data-agent-v2-workspace]")?.classList.contains("artifact-focus-open")`, 5000);
      await sleep(150);
      const afterEscape = await cdp.eval(`(() => ({
        focused: document.querySelector("[data-agent-v2-workspace]")?.classList.contains("artifact-focus-open") || false,
        conversationVisible: getComputedStyle(document.querySelector(".agent-surface-conversation")).display !== "none",
      }))()`);
      const beforeReload = await cdp.eval(`(() => {
        const canvas = document.querySelector(".mermaid-v2-canvas");
        return { mode:document.querySelector("[data-v2-mermaid]")?.dataset.viewMode || "", left:Math.round(canvas?.scrollLeft || 0), top:Math.round(canvas?.scrollTop || 0) };
      })()`);
      await cdp.send("Page.reload", { ignoreCache: true });
      await waitUntil(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid][data-mermaid-state="rendered"] svg')`, 30000);
      await sleep(350);
      const restored = await cdp.eval(`(() => {
        const diagram = document.querySelector("[data-v2-mermaid]");
        const canvas = diagram?.querySelector(".mermaid-v2-canvas");
        return { mode:diagram?.dataset.viewMode || "", left:Math.round(canvas?.scrollLeft || 0), top:Math.round(canvas?.scrollTop || 0), focus:document.querySelector("[data-agent-v2-workspace]")?.classList.contains("artifact-focus-open") || false };
      })()`);
      await screenshot(cdp, args.screenshot);
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
      await cdp.send("Page.reload", { ignoreCache: true });
      await waitUntil(cdp, `!!document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid][data-mermaid-state="rendered"] svg')`, 30000);
      await sleep(800);
      const mobile = await cdp.eval(`(() => {
        const diagram = document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid]');
        const svg = diagram?.querySelector("svg");
        const lines = [...(svg?.querySelectorAll("g.node tspan") || [])];
        const labels = lines.length ? lines : [...(svg?.querySelectorAll("g.node text") || [])];
        const heights = labels.map((item) => item.getBoundingClientRect().height).filter((height) => height > 1);
        return {
          rootOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
          surfaceOverflow: (() => { const node = document.querySelector("[data-agent-v2-surface]"); return node ? node.scrollWidth > node.clientWidth + 2 : false; })(),
          tabsVisible: (() => { const node = document.querySelector("[data-agent-v2-mobile-tabs]"); return !!node && getComputedStyle(node).display !== "none"; })(),
          svgVisible: !!svg,
          viewMode: diagram?.dataset.viewMode || "",
          zoomLabel: diagram?.querySelector("[data-mermaid-zoom]")?.textContent.trim() || "",
          nodeTextHeight: heights.length ? Math.min(...heights) : 0,
        };
      })()`);
      await screenshot(cdp, args.mobileScreenshot);
      const checks = {
        boi_agent_brand_visible: desktop.brand === "BoI Agent",
        artifact_title_is_visible: desktop.title.length > 0 && desktop.titleWidth > 80 && desktop.titleHeight > 10 && desktop.titleDisplay !== "none",
        mermaid_svg_is_nonblank: desktop.state === "rendered" && desktop.width > 120 && desktop.height > 80,
        mermaid_defaults_to_readable_labels: desktop.viewMode === "read" && desktop.nodeTextHeight >= 13.5 && (!desktop.edgeTextHeight || desktop.edgeTextHeight >= 11.5),
        readable_zoom_is_visible: /^\d+%$/.test(desktop.zoomLabel),
        focus_view_uses_full_result_width: desktop.focusControlVisible && focused.active && focused.conversationHidden && focused.workbenchWidth > desktop.workbenchWidth * 1.25,
        focused_diagram_has_one_scroll_owner: focused.outerOverflow === "hidden" && /auto|scroll/.test(focused.canvasOverflow),
        fit_and_read_views_are_distinct: fitView.mode === "fit" && fitView.zoom === "100%" && fitView.fitsWidth,
        zoom_preserves_view_center: Math.abs(centerBefore.x - centerAfter.x) < .06 && Math.abs(centerBefore.y - centerAfter.y) < .06,
        escape_restores_split_view: !afterEscape.focused && afterEscape.conversationVisible,
        diagram_view_restores_after_reload: beforeReload.mode === "read" && restored.mode === "read" && !restored.focus && Math.abs(beforeReload.left - restored.left) < 4 && Math.abs(beforeReload.top - restored.top) < 4,
        artifact_kind_matches_expectation: args.expectWorkflowDraft
          ? desktop.workflowDraft && desktop.taskCandidates > 0 && !desktop.fullSopEditor
          : !desktop.workflowDraft,
        mermaid_actions_match_intent: args.expectArtifactActions
          ? desktop.taskAction && desktop.sopAction
          : !desktop.taskAction && !desktop.sopAction,
        desktop_has_no_horizontal_overflow: desktop.overflow === false,
        mobile_has_no_horizontal_overflow: mobile.rootOverflow === false && mobile.surfaceOverflow === false,
        mobile_result_tab_available: mobile.tabsVisible && mobile.svgVisible,
        mobile_readable_labels: mobile.viewMode === "read" && mobile.nodeTextHeight >= 13.5,
        no_console_exceptions: consoleErrors.length === 0,
        no_failed_requests: failedRequests.length === 0,
      };
      const ok = Object.values(checks).every(Boolean);
      console.log(JSON.stringify({ ok, checks, desktop, focused, fitView, centerBefore, centerAfter, afterEscape, beforeReload, restored, mobile, consoleErrors, failedRequests }, null, 2));
      if (args.strict && !ok) process.exitCode = 1;
      return;
    }

    const docUrl = `${args.baseUrl}/docs/boi:public:sop:direct-development-reporting?employee_id=${args.employeeId}`;
    await navigate(cdp, docUrl);
    const initial = await cdp.eval(`(() => ({
      launcher: !!document.querySelector("[data-agent-v2-open]"),
      launcherText: document.querySelector("[data-agent-v2-open]")?.textContent.trim() || "",
      launcherWidth: Math.round(document.querySelector("[data-agent-v2-open]")?.getBoundingClientRect().width || 0),
      petImage: document.querySelector("[data-agent-v2-open] img")?.getAttribute("src") || "",
      surfaceHidden: document.querySelector("[data-agent-v2-surface]")?.hidden,
      capabilityCards: document.querySelectorAll("[data-capability-id], .boi-agent-v2-offers").length,
      technicalTerms: /pgvector|DeepAgents|LangGraph|raw payload|context manifest/.test(document.body.innerText),
    }))()`);
    await screenshot(cdp, args.launcherScreenshot);
    if (args.launcherOnly) {
      const ok = initial.launcher && initial.launcherWidth >= 84 && initial.petImage.includes("boi-agent-pet.png");
      console.log(JSON.stringify({ ok, initial, screenshot: args.launcherScreenshot }, null, 2));
      if (args.strict && !ok) process.exitCode = 1;
      return;
    }
    await openPet(cdp);
    await waitUntil(cdp, `document.querySelectorAll("[data-agent-v2-starters] button").length > 0`, 15000);
    const opened = await cdp.eval(`(() => ({
      starters: document.querySelectorAll("[data-agent-v2-starters] button").length,
      brand: document.querySelector(".agent-surface-heading > span")?.textContent.trim() || "",
      context: document.querySelector("[data-agent-v2-context]")?.textContent.trim() || "",
      mode: document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode || "",
      resultHidden: document.querySelector("[data-agent-v2-workbench]")?.hidden,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    }))()`);

    if (args.starterOnly) {
      const beforeRequests = turnRequests.length;
      await cdp.eval(`document.querySelector('[data-agent-v2-starters] button:not(.agent-v2-starters-more)')?.click()`);
      await waitUntil(
        cdp,
        `(() => {
          const form = document.querySelector('[data-agent-v2-form]');
          return document.querySelectorAll('.agent-v2-message.user').length === 1
            && document.querySelectorAll('.agent-v2-message.assistant').length === 1
            && !form?.elements.question.disabled;
        })()`,
        args.timeoutMs,
        250,
      );
      const result = await cdp.eval(`(() => ({
        userMessages: document.querySelectorAll('.agent-v2-message.user').length,
        assistantMessages: document.querySelectorAll('.agent-v2-message.assistant').length,
        composer: document.querySelector('[data-agent-v2-form]')?.elements.question.value || '',
        busy: document.querySelector('[data-agent-v2-workspace]')?.getAttribute('aria-busy') || 'false',
      }))()`);
      const checks = {
        starter_sends_exactly_one_turn: turnRequests.length - beforeRequests === 1,
        starter_adds_one_user_and_assistant_message: result.userMessages === 1 && result.assistantMessages === 1,
        starter_does_not_require_composer_submit: result.composer === '' && result.busy === 'false',
        no_console_exceptions: consoleErrors.length === 0,
        no_failed_requests: failedRequests.length === 0,
      };
      const ok = Object.values(checks).every(Boolean);
      console.log(JSON.stringify({ ok, checks, result, turnRequests, consoleErrors, failedRequests }, null, 2));
      if (args.strict && !ok) process.exitCode = 1;
      return;
    }

    if (args.surfaceOnly) {
      await screenshot(cdp, args.screenshot);
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
      await sleep(300);
      const mobile = await cdp.eval(`(() => ({
        rootOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        surfaceOverflow: (() => { const node = document.querySelector("[data-agent-v2-surface]"); return node ? node.scrollWidth > node.clientWidth + 2 : false; })(),
        launcherWidth: Math.round(document.querySelector("[data-agent-v2-open]")?.getBoundingClientRect().width || 0),
      }))()`);
      await screenshot(cdp, args.mobileScreenshot);
      const checks = {
        launcher_uses_visible_pet: initial.launcher && initial.launcherWidth >= 84 && initial.petImage.includes("boi-agent-pet.png"),
        boi_agent_brand_visible: opened.brand === "BoI Agent",
        contextual_starters_visible: opened.starters > 0 && opened.starters <= 5,
        compact_is_conversation_only: opened.mode === "compact" && opened.resultHidden === true,
        current_page_context_visible: opened.context.includes("직개발 결과 확인 및 Reporting SOP"),
        desktop_has_no_horizontal_overflow: opened.overflow === false,
        mobile_has_no_horizontal_overflow: mobile.rootOverflow === false && mobile.surfaceOverflow === false,
        no_console_exceptions: consoleErrors.length === 0,
        no_failed_requests: failedRequests.length === 0,
      };
      const ok = Object.values(checks).every(Boolean);
      console.log(JSON.stringify({ ok, checks, initial, opened, mobile, consoleErrors, failedRequests }, null, 2));
      if (args.strict && !ok) process.exitCode = 1;
      return;
    }

    if (args.mermaidOnly) {
      await submit(cdp, "현재 SOP에서 업무 이벤트가 Task와 Action으로 이어지는 관계를 BoI Wiki 전체 근거와 함께 설명해줘.", args.timeoutMs);
      const firstTurn = await cdp.eval(`(() => ({
        sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
        answer: document.querySelector(".agent-v2-message.assistant:last-of-type")?.textContent.trim() || "",
        diagramCount: document.querySelectorAll("[data-agent-v2-surface] [data-v2-mermaid]").length,
        mode: document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode || "",
      }))()`);
      await submit(cdp, "방금 설명한 흐름을 머메이드 차트로 그려줘.", args.timeoutMs);
      await waitUntil(
        cdp,
        `!!document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid][data-mermaid-state="rendered"] svg')`,
        args.timeoutMs,
        250,
      );
      const secondTurn = await cdp.eval(`(() => {
        const diagram = document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid]');
        const svg = diagram?.querySelector("svg");
        const bounds = svg?.getBoundingClientRect();
        return {
          sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
          answer: document.querySelector(".agent-v2-message.assistant:last-of-type")?.textContent.trim() || "",
          mode: document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode || "",
          artifactTitle: document.querySelector(".agent-v2-diagram-result h3")?.textContent.trim() || "",
          diagramState: diagram?.dataset.mermaidState || "",
          svgWidth: Math.round(bounds?.width || 0),
          svgHeight: Math.round(bounds?.height || 0),
          sourceLength: (diagram?.dataset.mermaidSource || "").length,
          taskAction: !!diagram?.querySelector('[data-v2-mermaid-action="split_tasks"]'),
          sopAction: !!diagram?.querySelector('[data-v2-mermaid-action="create_sop_draft"]'),
          rootOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        };
      })()`);
      await screenshot(cdp, args.screenshot);
      await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
      await sleep(300);
      const mobile = await cdp.eval(`(() => ({
        rootOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        surfaceOverflow: (() => { const node = document.querySelector("[data-agent-v2-surface]"); return node ? node.scrollWidth > node.clientWidth + 2 : false; })(),
        tabsVisible: (() => { const node = document.querySelector("[data-agent-v2-mobile-tabs]"); return !!node && getComputedStyle(node).display !== "none"; })(),
        svgVisible: !!document.querySelector('[data-agent-v2-artifact-list] [data-v2-mermaid] svg'),
      }))()`);
      await screenshot(cdp, args.mobileScreenshot);
      const checks = {
        launcher_uses_visible_pet: initial.launcher && initial.launcherWidth >= 84 && initial.petImage.includes("boi-agent-pet.png"),
        boi_agent_brand_visible: opened.brand === "BoI Agent",
        contextual_starters_visible: opened.starters > 0 && opened.starters <= 5,
        compact_is_conversation_only: opened.mode === "compact" && opened.resultHidden === true,
        explanation_remains_prose: firstTurn.answer.length > 20 && firstTurn.diagramCount === 0 && firstTurn.mode === "compact",
        same_session_multiturn: firstTurn.sessionId && secondTurn.sessionId === firstTurn.sessionId,
        mermaid_artifact_expands_result: secondTurn.mode === "expanded" && secondTurn.artifactTitle.length > 0,
        mermaid_svg_is_nonblank: secondTurn.diagramState === "rendered" && secondTurn.svgWidth > 120 && secondTurn.svgHeight > 80 && secondTurn.sourceLength > 30,
        explanation_has_no_transform_actions: !secondTurn.taskAction && !secondTurn.sopAction,
        desktop_has_no_horizontal_overflow: secondTurn.rootOverflow === false,
        mobile_has_no_horizontal_overflow: mobile.rootOverflow === false && mobile.surfaceOverflow === false,
        mobile_result_tab_available: mobile.tabsVisible && mobile.svgVisible,
        no_console_exceptions: consoleErrors.length === 0,
        no_failed_requests: failedRequests.length === 0,
      };
      const ok = Object.values(checks).every(Boolean);
      console.log(JSON.stringify({
        ok,
        checks,
        initial,
        opened,
        firstTurn: { ...firstTurn, answer: firstTurn.answer.slice(0, 400) },
        secondTurn: { ...secondTurn, answer: secondTurn.answer.slice(0, 400) },
        mobile,
        consoleErrors,
        failedRequests,
        screenshots: [args.launcherScreenshot, args.screenshot, args.mobileScreenshot],
      }, null, 2));
      if (args.strict && !ok) process.exitCode = 1;
      return;
    }

    await submit(cdp, "현재 SOP의 핵심 흐름과 완료 기준을 BoI Wiki 전체 근거와 함께 설명해줘.", args.timeoutMs);
    const first = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      messages: document.querySelectorAll(".agent-v2-message").length,
      citations: document.querySelectorAll('.agent-v2-message.assistant:last-of-type a[href^="/api/v2/citations/"]').length,
      related: document.querySelectorAll("[data-agent-v2-related] button").length,
      nextActions: document.querySelectorAll("[data-agent-v2-next-actions] button").length,
      answer: document.querySelector(".agent-v2-message.assistant:last-of-type")?.textContent.trim() || "",
      inputEnabled: !document.querySelector("[data-agent-v2-form]")?.elements.question.disabled,
    }))()`);
    if (first.citations) {
      await cdp.eval(`document.querySelector('.agent-v2-message.assistant:last-of-type a[href^="/api/v2/citations/"]')?.click()`);
      await waitUntil(cdp, `!document.querySelector("[data-agent-v2-source-preview]")?.hidden`, 10000);
    } else {
      await cdp.eval(`Array.from(document.querySelectorAll('[data-agent-v2-next-actions] button')).find((item) => item.textContent.includes("사용한 지식"))?.click()`);
      await waitUntil(cdp, `!document.querySelector("[data-agent-v2-sources]")?.hidden`, 10000);
    }
    const sourcePreview = await cdp.eval(`(() => ({
      previewOpen: !document.querySelector("[data-agent-v2-source-preview]")?.hidden,
      sourcesOpen: !document.querySelector("[data-agent-v2-sources]")?.hidden,
      excerpt: document.querySelector("[data-agent-v2-source-preview] blockquote")?.textContent.trim() || "",
      sourceRows: document.querySelectorAll("[data-agent-v2-source-list] article").length,
    }))()`);
    await cdp.eval(`document.querySelector("[data-agent-v2-source-preview-close]")?.click(); document.querySelector("[data-agent-v2-sources-close]")?.click()`);

    await submit(cdp, "그중 담당자가 직접 확인해야 하는 부분만 이어서 정리해줘.", args.timeoutMs);
    const second = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      messages: document.querySelectorAll(".agent-v2-message").length,
      latest: document.querySelector(".agent-v2-message.assistant:last-of-type")?.textContent.trim() || "",
    }))()`);

    await navigate(cdp, `${args.baseUrl}/events?employee_id=${args.employeeId}`);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-message").length >= ${second.messages}`, 20000);
    const afterNavigation = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      messages: document.querySelectorAll(".agent-v2-message").length,
      mode: document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode || "",
      surfaceHidden: document.querySelector("[data-agent-v2-surface]")?.hidden,
    }))()`);

    await navigate(cdp, docUrl);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-message").length >= ${second.messages}`, 20000);
    const reloaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.reload", { ignoreCache: false });
    await reloaded;
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-message").length >= ${second.messages}`, 20000);
    const afterReload = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      messages: document.querySelectorAll(".agent-v2-message").length,
      context: document.querySelector("[data-agent-v2-context]")?.textContent.trim() || "",
    }))()`);

    await cdp.eval(`document.querySelector("[data-agent-v2-new]")?.click()`);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-message").length === 0 && !!document.querySelector("[data-agent-v2-starters]")`, 15000);
    await submit(cdp, "설비 Alarm 대응 SOP를 Task와 완료된 모습, 확인할 자료까지 자세히 설계해줘.", args.timeoutMs);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-task-map [data-task-id]").length > 0`, 30000);
    const sopBefore = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      taskCount: document.querySelectorAll(".agent-v2-task-map [data-task-id]").length,
      fullEditor: document.querySelector("[data-agent-v2-full-editor]")?.href || "",
      artifactTitle: document.querySelector(".agent-v2-sop-result h3")?.textContent.trim() || "",
    }))()`);
    await cdp.eval(`document.querySelector("[data-agent-v2-open-tasks]")?.click()`);
    await waitUntil(cdp, `!document.querySelector("[data-agent-v2-task-sheet]")?.hidden`, 10000);
    const marker = `UI continuity ${Date.now()}`;
    await cdp.eval(`(() => {
      const field = document.querySelector('[data-agent-v2-task-form] [name="purpose"]');
      field.value = [field.value, ${JSON.stringify(marker)}].filter(Boolean).join(" ");
      field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: ${JSON.stringify(marker)} }));
      return field.value;
    })()`);
    await waitUntil(cdp, `/저장됨 · 버전/.test(document.querySelector("[data-agent-v2-task-status]")?.textContent || "")`, 20000);
    const taskSaved = await cdp.eval(`(() => ({
      purpose: document.querySelector('[data-agent-v2-task-form] [name="purpose"]')?.value || "",
      status: document.querySelector("[data-agent-v2-task-status]")?.textContent || "",
    }))()`);
    await cdp.eval(`document.querySelector("[data-agent-v2-task-close]")?.click()`);
    await navigate(cdp, `${args.baseUrl}/inbox?employee_id=${args.employeeId}`);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-task-map [data-task-id]").length > 0`, 20000);
    await cdp.eval(`document.querySelector("[data-agent-v2-open-tasks]")?.click()`);
    await waitUntil(cdp, `!document.querySelector("[data-agent-v2-task-sheet]")?.hidden`, 10000);
    const taskRestored = await cdp.eval(`(() => ({
      purpose: document.querySelector('[data-agent-v2-task-form] [name="purpose"]')?.value || "",
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      fullEditor: document.querySelector("[data-agent-v2-full-editor]")?.href || "",
    }))()`);
    await cdp.eval(`document.querySelector("[data-agent-v2-task-close]")?.click()`);
    await navigate(cdp, taskRestored.fullEditor);
    await waitUntil(cdp, `!!document.querySelector("[data-v2-sop-editor-bar]") && document.body.innerText.includes(${JSON.stringify(marker)})`, 20000);
    const fullEditor = await cdp.eval(`(() => ({
      artifactId: document.querySelector("[data-v2-artifact-id]")?.dataset.v2ArtifactId || "",
      sessionId: document.querySelector("[data-v2-work-session-id]")?.dataset.v2WorkSessionId || "",
      saveState: document.querySelector("[data-v2-builder-save-state]")?.textContent.trim() || "",
      returnHref: document.querySelector("[data-v2-sop-editor-bar] a")?.href || "",
      markerVisible: document.body.innerText.includes(${JSON.stringify(marker)}),
    }))()`);
    await navigate(cdp, fullEditor.returnHref);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-task-map [data-task-id]").length > 0`, 20000);
    const afterEditorReturn = await cdp.eval(`(() => ({
      sessionId: sessionStorage.getItem("boiAgentV2WorkSession") || "",
      mode: document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode || "",
      taskCount: document.querySelectorAll(".agent-v2-task-map [data-task-id]").length,
      artifactTitle: document.querySelector(".agent-v2-sop-result h3")?.textContent.trim() || "",
    }))()`);
    await cdp.eval(`(() => {
      const root = document.querySelector("[data-agent-v2-workspace]");
      if (root?.dataset.surfaceMode !== "expanded") document.querySelector("[data-agent-v2-expand]")?.click();
    })()`);
    await waitUntil(cdp, `document.querySelector("[data-agent-v2-workspace]")?.dataset.surfaceMode === "expanded"`, 5000);
    await screenshot(cdp, args.screenshot);

    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await sleep(250);
    const mobile = await cdp.eval(`(() => ({
      viewport: [innerWidth, innerHeight],
      rootOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      surfaceOverflow: (() => { const node = document.querySelector("[data-agent-v2-surface]"); return node ? node.scrollWidth > node.clientWidth + 2 : false; })(),
      tabsVisible: (() => { const node = document.querySelector("[data-agent-v2-mobile-tabs]"); return !!node && getComputedStyle(node).display !== "none"; })(),
      taskSheetHidden: document.querySelector("[data-agent-v2-task-sheet]")?.hidden,
    }))()`);
    await screenshot(cdp, args.mobileScreenshot);

    const checks = {
      launcher_uses_visible_pet: initial.launcher && initial.launcherWidth >= 84 && initial.petImage.includes("boi-agent-pet.png"),
      starts_closed: initial.surfaceHidden === true,
      no_capability_picker: initial.capabilityCards === 0,
      no_technical_terms: initial.technicalTerms === false,
      current_page_context_visible: opened.context.includes("직개발 결과 확인 및 Reporting SOP"),
      boi_agent_brand_visible: opened.brand === "BoI Agent",
      starters_are_bounded: opened.starters > 0 && opened.starters <= 5,
      compact_is_conversation_only: opened.resultHidden === true,
      compact_has_no_page_overflow: opened.overflow === false,
      grounded_answer_rendered: first.answer.length > 20 && first.inputEnabled,
      related_questions_bounded: first.related <= 3,
      next_actions_bounded: first.nextActions <= 3,
      source_or_citation_opens_in_pet: sourcePreview.previewOpen || sourcePreview.sourcesOpen,
      citation_has_exact_excerpt_when_present: !first.citations || sourcePreview.excerpt.length > 10,
      same_session_multiturn: first.sessionId && second.sessionId === first.sessionId && second.messages >= 4,
      session_survives_page_navigation: afterNavigation.sessionId === first.sessionId && afterNavigation.messages >= second.messages && afterNavigation.mode === "compact" && afterNavigation.surfaceHidden === false,
      session_survives_reload: afterReload.sessionId === first.sessionId && afterReload.messages >= second.messages,
      sop_artifact_created: sopBefore.taskCount > 0 && sopBefore.artifactTitle.length > 0,
      task_autosave_completed: taskSaved.purpose.includes(marker) && taskSaved.status.includes("저장됨"),
      task_restored_after_navigation: taskRestored.sessionId === sopBefore.sessionId && taskRestored.purpose.includes(marker),
      full_editor_keeps_same_artifact: taskRestored.fullEditor.includes("work_session_id=") && taskRestored.fullEditor.includes("artifact_id=") && taskRestored.fullEditor.includes("return_to="),
      full_editor_loaded_same_revision: fullEditor.sessionId === sopBefore.sessionId && fullEditor.artifactId.length > 0 && fullEditor.saveState.includes("버전") && fullEditor.markerVisible,
      pet_restored_after_editor_return: afterEditorReturn.sessionId === sopBefore.sessionId && afterEditorReturn.mode === "expanded" && afterEditorReturn.taskCount === sopBefore.taskCount && afterEditorReturn.artifactTitle === sopBefore.artifactTitle,
      mobile_no_horizontal_overflow: mobile.rootOverflow === false && mobile.surfaceOverflow === false,
      mobile_tabs_available: mobile.tabsVisible,
      no_console_exceptions: consoleErrors.length === 0,
      no_failed_requests: failedRequests.length === 0,
    };
    const ok = Object.values(checks).every(Boolean);
    const report = {
      ok,
      checks,
      initial,
      opened,
      first: { ...first, answer: first.answer.slice(0, 400) },
      sourcePreview,
      second: { ...second, latest: second.latest.slice(0, 400) },
      afterNavigation,
      afterReload,
      sopBefore,
      taskSaved,
      taskRestored,
      fullEditor,
      afterEditorReturn,
      mobile,
      consoleErrors,
      failedRequests,
      screenshots: [args.launcherScreenshot, args.screenshot, args.mobileScreenshot],
    };
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !ok) process.exitCode = 1;
  } finally {
    try { cdp?.close(); } catch (_error) {}
    child.kill("SIGTERM");
    await sleep(300);
    try { rmSync(profile, { recursive: true, force: true }); } catch (_error) {}
  }
}

main().catch((error) => {
  console.log(JSON.stringify({ ok: false, error: error.message }, null, 2));
  process.exit(1);
});
