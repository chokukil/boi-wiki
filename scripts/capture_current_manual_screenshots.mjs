#!/usr/bin/env node
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const ROOT = resolve(import.meta.dirname, "..");
const OUTPUT_ROOT = join(
  ROOT,
  "data/boi/public/boi-wiki-manual/_media/browser/current-guide",
);
const BASE_URL = process.env.BOI_BASE_URL || "http://127.0.0.1:8765";
const EMPLOYEE_ID = process.env.BOI_CAPTURE_EMPLOYEE_ID || "100001";
const SOURCE_REVISION = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: ROOT,
  encoding: "utf8",
}).trim();

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

function getJson(url, timeoutMs = 2000) {
  return new Promise((resolvePromise, reject) => {
    const request = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try { resolvePromise(JSON.parse(body)); }
        catch (error) { reject(error); }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`timeout: ${url}`)));
  });
}

async function waitJson(url, timeoutMs = 20000) {
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
    await new Promise((resolvePromise, reject) => {
      this.ws.addEventListener("open", resolvePromise, { once: true });
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
    return new Promise((resolvePromise, reject) => this.pending.set(id, { resolve: resolvePromise, reject }));
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(listener);
  }

  once(method) {
    return new Promise((resolvePromise) => {
      const handler = (payload) => {
        this.listeners.get(method)?.delete(handler);
        resolvePromise(payload);
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

async function waitUntil(cdp, expression, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await cdp.eval(expression);
    if (lastValue) return lastValue;
    await sleep(180);
  }
  throw new Error(`timeout waiting for ${expression}; last=${JSON.stringify(lastValue)}`);
}

async function viewport(cdp, width, height) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 600,
  });
}

async function navigate(cdp, path, selector = "main") {
  const loaded = cdp.once("Page.loadEventFired");
  await cdp.send("Page.navigate", { url: `${BASE_URL}${path}` });
  await loaded;
  await waitUntil(cdp, `document.readyState === "complete" && !!document.querySelector(${JSON.stringify(selector)})`);
  await sleep(500);
}

async function redact(cdp) {
  await cdp.eval(`(() => {
    const replacements = [
      [/\\b${EMPLOYEE_ID}\\b/g, "현재 사용자"],
      [/ws_[a-f0-9]{12,}/gi, "작업 공간"],
      [/artifact_[a-f0-9]{12,}/gi, "작업 결과"],
      [/trace[-_][a-z0-9_-]{12,}/gi, "업무 이력"],
      [/boi:private:[a-z0-9:_-]+/gi, "private BoI"],
      [/https?:\\/\\/(?:127\\.0\\.0\\.1|localhost):8200/gi, "<BOI_MCP_URL>"],
      [/https?:\\/\\/(?:127\\.0\\.0\\.1|localhost)(?::\\d+)?/gi, "<BOI_BASE_URL>"],
    ];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      let value = node.nodeValue || "";
      for (const [pattern, replacement] of replacements) value = value.replace(pattern, replacement);
      node.nodeValue = value;
    }
    for (const option of document.querySelectorAll("option")) {
      if ((option.textContent || "").trim() === ${JSON.stringify(EMPLOYEE_ID)}) option.textContent = "현재 사용자";
    }
    for (const input of document.querySelectorAll('input[value="${EMPLOYEE_ID}"]')) input.value = "현재 사용자";
    document.documentElement.dataset.captureRedacted = "true";
    return true;
  })()`);
}

async function capture(cdp, scenario, metadata) {
  await redact(cdp);
  await cdp.send("Page.bringToFront");
  await cdp.eval(`(() => { void document.body.offsetHeight; return true; })()`);
  await sleep(600);
  mkdirSync(dirname(scenario.output), { recursive: true });
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  writeFileSync(scenario.output, Buffer.from(result.data, "base64"));
  const bytes = readFileSync(scenario.output);
  metadata.push({
    path: scenario.output.replace(`${ROOT}/data/boi/`, ""),
    sha256: createHash("sha256").update(bytes).digest("hex"),
    source_kind: "browser-screenshot",
    captured_url: `${BASE_URL}${scenario.routeTemplate}`,
    captured_at: new Date().toISOString(),
    viewport: `${scenario.width}x${scenario.height}`,
    related_doc: scenario.relatedDoc,
    created_by: "codex",
    route_template: scenario.routeTemplate,
    scenario: scenario.name,
    source_revision: SOURCE_REVISION,
    selector: scenario.selector,
  });
}

function output(name) {
  return join(OUTPUT_ROOT, `20260712-${name}.png`);
}

async function main() {
  mkdirSync(OUTPUT_ROOT, { recursive: true });
  const profile = mkdtempSync(join(tmpdir(), "boi-manual-capture-"));
  const port = 9900 + Math.floor(Math.random() * 80);
  const child = spawn(chromePath(), [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars=false",
    "--no-sandbox",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { stdio: "ignore" });
  let cdp;
  const metadata = [];
  try {
    const targets = await waitJson(`http://127.0.0.1:${port}/json/list`);
    const target = targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    if (!target) throw new Error("Chrome page target was not available");
    cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Network.enable");
    const mermaidRequests = [];
    const pageExceptions = [];
    cdp.on("Network.requestWillBeSent", ({ request }) => {
      const url = String(request?.url || "");
      if (url.includes("mermaid") && url.includes("cdn.jsdelivr.net")) mermaidRequests.push(url);
    });
    cdp.on("Runtime.exceptionThrown", ({ exceptionDetails }) => {
      pageExceptions.push(exceptionDetails?.exception?.description || exceptionDetails?.text || "browser exception");
    });

    const shot = async ({ name, path, selector = "main", relatedDoc, routeTemplate = path, width = 1440, height = 1000, prepare }) => {
      await viewport(cdp, width, height);
      await navigate(cdp, path, selector);
      if (prepare) await prepare(cdp);
      await capture(cdp, {
        name,
        output: output(`${name}-${width}x${height}`),
        routeTemplate,
        relatedDoc,
        selector,
        width,
        height,
      }, metadata);
    };

    // Keep the starter UX contract executable: one click is one Agent turn.
    await viewport(cdp, 1440, 1000);
    await navigate(
      cdp,
      `/docs/boi:public:boi-wiki-manual:guide:final-operator-guide?employee_id=${EMPLOYEE_ID}`,
      "main",
    );
    await cdp.eval(`document.querySelector("[data-agent-v2-open]")?.click()`);
    await waitUntil(cdp, `document.querySelectorAll("[data-agent-v2-starters] > button").length >= 4`, 20000);
    await cdp.eval(`(() => {
      window.__boiStarterTurnPosts = 0;
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init = {}) => {
        const url = String(typeof input === "string" ? input : input?.url || "");
        if (url.includes("/api/v2/agent/turns") && String(init.method || "GET").toUpperCase() === "POST") {
          window.__boiStarterTurnPosts += 1;
        }
        return originalFetch(input, init);
      };
      document.querySelector("[data-agent-v2-starters] > button")?.click();
      return true;
    })()`);
    await waitUntil(cdp, `window.__boiStarterTurnPosts === 1`, 3000);
    await waitUntil(cdp, `document.querySelectorAll(".agent-v2-message.user").length === 1`, 3000);
    await sleep(700);
    const starterTurnPosts = await cdp.eval(`window.__boiStarterTurnPosts`);
    if (starterTurnPosts !== 1) throw new Error(`Starter click sent ${starterTurnPosts} Agent turns`);

    await shot({
      name: "explorer",
      path: `/?employee_id=${EMPLOYEE_ID}&view=explorer`,
      routeTemplate: "/?view=explorer",
      relatedDoc: "boi:public:boi-wiki-manual:guide:final-operator-guide",
    });
    await shot({
      name: "boi-agent-compact",
      path: `/docs/boi:public:boi-wiki-manual:guide:final-operator-guide?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/docs/{boi_id}",
      relatedDoc: "boi:public:boi-wiki-manual:agent:using-boi-agent",
      prepare: async (browser) => {
        let mermaidReady = false;
        try {
          await waitUntil(browser, `!!document.querySelector('.mermaid-diagram[data-mermaid-state="rendered"] svg')`, 35000);
          mermaidReady = true;
        } catch (_error) { mermaidReady = false; }
        if (!mermaidReady) {
          const mermaidDiagnostic = await browser.eval(`Array.from(document.querySelectorAll('.mermaid-diagram')).map((item) => ({state: item.dataset.mermaidState, status: item.querySelector('.mermaid-status')?.textContent, svg: !!item.querySelector('svg')}))`);
          throw new Error(`Mermaid did not render: ${JSON.stringify(mermaidDiagnostic)} exceptions=${JSON.stringify(pageExceptions)}`);
        }
        await browser.eval(`document.querySelector("[data-agent-v2-open]")?.click()`);
        await waitUntil(browser, `!document.querySelector("[data-agent-v2-surface]")?.hidden`);
        await waitUntil(browser, `document.querySelectorAll("[data-agent-v2-starters] > button").length >= 4`, 20000);
        const rawFailure = await browser.eval(`document.body.textContent.includes("Failed to fetch")`);
        if (rawFailure) throw new Error("BoI Agent exposed a raw fetch failure");
      },
    });
    await shot({
      name: "boi-agent-expanded",
      path: `/docs/boi:public:boi-wiki-manual:guide:final-operator-guide?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/docs/{boi_id}",
      relatedDoc: "boi:public:boi-wiki-manual:agent:using-boi-agent",
      prepare: async (browser) => {
        await browser.eval(`document.querySelector("[data-agent-v2-open]")?.click()`);
        await waitUntil(browser, `document.querySelectorAll("[data-agent-v2-starters] > button").length >= 4`, 20000);
        await browser.eval(`document.querySelector("[data-agent-v2-expand]")?.click()`);
        await waitUntil(browser, `document.querySelectorAll(".agent-v2-starter-area").length === 6`, 20000);
      },
    });
    await shot({
      name: "boi-agent-mermaid",
      path: `/agent?employee_id=${EMPLOYEE_ID}&session=ws_f2a00b3bfce94f85b265b440cc46450c&artifact=artifact_1b4bfa1b1c174eb089d5ab1dbe157c81`,
      routeTemplate: "/agent?session={work_session_id}&artifact={artifact_id}",
      relatedDoc: "boi:public:boi-wiki-manual:agent:using-boi-agent",
      selector: "[data-agent-v2-workspace]",
      prepare: async (browser) => {
        await waitUntil(browser, `!!document.querySelector(".mermaid svg") || !!document.querySelector("[data-agent-v2-artifact-list] article")`, 30000);
      },
    });
    await shot({
      name: "boi-agent-mobile",
      path: `/docs/boi:public:boi-wiki-manual:guide:final-operator-guide?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/docs/{boi_id}",
      relatedDoc: "boi:public:boi-wiki-manual:agent:using-boi-agent",
      width: 390,
      height: 844,
      prepare: async (browser) => {
        await browser.eval(`document.querySelector("[data-agent-v2-open]")?.click()`);
        await waitUntil(browser, `!document.querySelector("[data-agent-v2-surface]")?.hidden`);
      },
    });

    await shot({
      name: "inbox",
      path: `/inbox?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/inbox",
      relatedDoc: "boi:public:boi-wiki-manual:inbox:inbox-and-task-guide",
      selector: "main.boi-inbox-page",
      prepare: async (browser) => {
        await waitUntil(browser, `document.querySelectorAll(".boi-inbox-card").length > 0`, 30000);
      },
    });
    const reportHref = await cdp.eval(`Array.from(document.querySelectorAll(".boi-inbox-actions a")).find((item) => (item.textContent || "").includes("검증된 보고서"))?.getAttribute("href") || ""`);
    const taskHref = await cdp.eval(`Array.from(document.querySelectorAll(".boi-inbox-actions a")).find((item) => (item.textContent || "").includes("업무 수행"))?.getAttribute("href") || ""`);
    if (!reportHref || !taskHref) throw new Error("Inbox report/task links were not available");
    await shot({
      name: "inbox-report",
      path: reportHref,
      routeTemplate: "/docs/{private_report_boi_id}",
      relatedDoc: "boi:public:boi-wiki-manual:inbox:inbox-and-task-guide",
      selector: "main.doc-page",
      prepare: async (browser) => {
        await waitUntil(browser, `!!document.querySelector(".report-workflow-preview")`, 30000);
      },
    });
    await shot({
      name: "task-console",
      path: taskHref,
      routeTemplate: "/tasks/console?task_id={task_ref}",
      relatedDoc: "boi:public:boi-wiki-manual:inbox:inbox-and-task-guide",
      selector: "main.task-console-page",
    });

    await shot({
      name: "sop-task-map",
      path: `/sops/new?employee_id=${EMPLOYEE_ID}&focus=sop`,
      routeTemplate: "/sops/new",
      relatedDoc: "boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step",
      prepare: async (browser) => {
        await browser.eval(`document.querySelector('[data-registration-step="stages"]')?.click()`);
        await waitUntil(browser, `!document.querySelector('[data-step-panel="stages"]')?.hidden`);
        await browser.eval(`(() => {
          document.querySelector('[data-step-panel="stages"]')?.scrollIntoView({ block: "start" });
          window.scrollBy(0, -180);
          return true;
        })()`);
        await sleep(700);
      },
    });
    await shot({
      name: "business-event-definition",
      path: `/sops/new?employee_id=${EMPLOYEE_ID}&focus=sop`,
      routeTemplate: "/sops/new#business-event-definition",
      relatedDoc: "boi:public:boi-wiki-manual:workflows:business-event-definition-guide",
      prepare: async (browser) => {
        await browser.eval(`document.querySelector('[data-registration-step="entry"]')?.click()`);
        await waitUntil(browser, `!document.querySelector('[data-step-panel="entry"]')?.hidden`);
        await browser.eval(`document.querySelector('[data-section-mode="event_mode"][data-mode-value="draft"]')?.click()`);
        await waitUntil(browser, `!document.querySelector('[data-event-definition-panel]')?.hidden`);
        await browser.eval(`(() => {
          document.querySelector('[data-step-panel="entry"]')?.scrollIntoView({ block: "start" });
          window.scrollBy(0, -180);
          return true;
        })()`);
        await sleep(700);
      },
    });

    await shot({
      name: "data-library",
      path: `/data-library?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/data-library",
      relatedDoc: "boi:public:boi-wiki-manual:data-lake:data-lake-artifact-lifecycle",
    });
    await shot({
      name: "event-catalog",
      path: `/event-types?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/event-types",
      relatedDoc: "boi:public:boi-wiki-manual:events:event-catalog-and-work-history",
    });
    await shot({
      name: "event-occurrences",
      path: `/events?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/events",
      relatedDoc: "boi:public:boi-wiki-manual:events:event-catalog-and-work-history",
      selector: "main.event-occurrence-page",
    });
    await shot({
      name: "sop-history",
      path: `/sops/history?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/sops/history",
      relatedDoc: "boi:public:boi-wiki-manual:sop-workflows:create-and-connect-sop",
    });
    await shot({
      name: "action-catalog",
      path: `/actions?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/actions",
      relatedDoc: "boi:public:boi-wiki-manual:actions:multi-action-connector-guide",
    });
    await shot({
      name: "external-agent-access",
      path: `/agent/access?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/agent/access",
      relatedDoc: "boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp",
      selector: "main.agent-access-v2",
    });
    await shot({
      name: "integration-status",
      path: `/integrations?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/integrations",
      relatedDoc: "boi:public:boi-wiki-manual:operations:operator-runbook",
      selector: "main.integrations-page",
    });
    await shot({
      name: "api-v2-reference",
      path: `/api/reference`,
      routeTemplate: "/api/reference",
      relatedDoc: "boi:public:boi-wiki-manual:api:boi-wiki-api-v2",
      selector: "#swagger-ui",
    });
    await shot({
      name: "mcp-status",
      path: `/advanced/mcp?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/advanced/mcp",
      relatedDoc: "boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp",
      selector: "main.advanced-interface-page",
    });
    await shot({
      name: "custom-boi-agent",
      path: `/helpers/new?employee_id=${EMPLOYEE_ID}`,
      routeTemplate: "/helpers/new",
      relatedDoc: "boi:public:boi-wiki-manual:agent:using-boi-agent",
      selector: "main.helper-builder-v2",
    });

    if (mermaidRequests.length) throw new Error(`Mermaid used the external CDN: ${mermaidRequests.join(", ")}`);
    if (pageExceptions.length) throw new Error(`Browser exceptions: ${pageExceptions.slice(0, 5).join(" | ")}`);

    const metadataPath = join(ROOT, ".tmp/current-manual-capture-manifest.json");
    mkdirSync(dirname(metadataPath), { recursive: true });
    writeFileSync(metadataPath, `${JSON.stringify({ media: metadata }, null, 2)}\n`);
    console.log(JSON.stringify({ ok: true, count: metadata.length, metadata: metadataPath }, null, 2));
  } finally {
    cdp?.close();
    child.kill("SIGTERM");
    await sleep(200);
    rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
