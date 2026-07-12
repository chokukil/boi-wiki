#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function parseArgs(argv) {
  const args = {
    url: "http://127.0.0.1:8765/helpers/new?employee_id=100001",
    timeoutMs: 90000,
    screenshot: "",
    strict: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--url") args.url = argv[++index] || args.url;
    else if (item === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (item === "--screenshot") args.screenshot = argv[++index] || "";
    else if (item === "--strict") args.strict = true;
    else if (item === "-h" || item === "--help") {
      console.log("Usage: node scripts/check_agent_builder_ui.mjs [--url URL] [--timeout-ms MS] [--screenshot FILE] [--strict]");
      process.exit(0);
    }
  }
  return args;
}

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].filter(Boolean);
  const chrome = candidates.find((candidate) => existsSync(candidate));
  if (!chrome) throw new Error("Chrome/Chromium binary not found. Set CHROME_BIN to run Agent Builder UI smoke.");
  return chrome;
}

function fetchJson(url, timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const req = get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`timeout fetching ${url}`));
    });
  });
}

async function waitForJson(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      return await fetchJson(url, 5000);
    } catch (error) {
      lastError = error;
      await sleep(150);
    }
  }
  throw lastError || new Error(`timed out waiting for ${url}`);
}

class CdpClient {
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
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
        else resolve(message.result || {});
        return;
      }
      if (message.method && this.listeners.has(message.method)) {
        for (const listener of this.listeners.get(message.method)) listener(message.params || {});
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(listener);
  }

  async evaluate(expression, awaitPromise = true) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      const details = result.exceptionDetails;
      const message = details.exception?.description || details.exception?.value || details.text || "Runtime.evaluate exception";
      throw new Error(message);
    }
    return result.result?.value;
  }

  async screenshot(path) {
    const result = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    if (path && result.data) writeFileSync(path, Buffer.from(result.data, "base64"));
    return result.data || "";
  }

  close() {
    this.ws?.close();
  }
}

async function waitUntil(cdp, expression, timeoutMs, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await cdp.evaluate(expression);
    if (lastValue) return lastValue;
    await sleep(intervalMs);
  }
  throw new Error(`timed out waiting for expression: ${expression}. Last value: ${JSON.stringify(lastValue)}`);
}

async function terminateChrome(child) {
  if (!child || child.killed) return;
  const exited = new Promise((resolve) => child.once("exit", resolve));
  child.kill("SIGTERM");
  await Promise.race([exited, sleep(2000)]);
  if (!child.killed) {
    child.kill("SIGKILL");
    await Promise.race([exited, sleep(1000)]);
  }
}

function relevantConsoleErrors(consoleErrors) {
  return consoleErrors.filter((item) => !/favicon\.ico|404 \(Not Found\)/i.test(item));
}

async function main() {
  const args = parseArgs(process.argv);
  const chrome = findChrome();
  const userDataDir = mkdtempSync(join(tmpdir(), "boi-agent-builder-ui-"));
  const port = 9300 + Math.floor(Math.random() * 1000);
  const child = spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--window-size=1440,1100",
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const consoleErrors = [];
  let cdp;
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`, 10000);
    const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`, 5000);
    const pageTarget = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
    if (!pageTarget) throw new Error("Chrome page target not found");
    cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable");
    cdp.on("Runtime.exceptionThrown", (params) => {
      consoleErrors.push(params.exceptionDetails?.exception?.description || params.exceptionDetails?.text || "Runtime exception");
    });
    cdp.on("Runtime.consoleAPICalled", (params) => {
      if (["error", "warning"].includes(params.type)) {
        consoleErrors.push((params.args || []).map((arg) => arg.value || arg.description || "").join(" "));
      }
    });
    cdp.on("Log.entryAdded", (params) => {
      const entry = params.entry || {};
      if (["error", "warning"].includes(entry.level)) consoleErrors.push(entry.text || "");
    });

    await cdp.send("Page.navigate", { url: args.url });
    await waitUntil(
      cdp,
      "document.readyState === 'complete' && !!document.querySelector('[data-helper-builder-v2]') && !document.querySelector('[data-helper-preview-form] button').disabled",
      args.timeoutMs,
    );
    const initialDraftId = await cdp.evaluate("new URL(location.href).searchParams.get('draft') || ''");
    await cdp.evaluate(`
      (() => {
        const originalFetch = window.fetch.bind(window);
        window.__helperPreviewResponse = null;
        window.fetch = async (...args) => {
          const response = await originalFetch(...args);
          const url = String(args[0] || '');
          if (url.includes('/preview-turns')) {
            response.clone().json().then((payload) => { window.__helperPreviewResponse = payload; }).catch(() => {});
          }
          return response;
        };
        document.querySelector('[data-template-id="sop"]').click();
        return true;
      })()
    `);
    await waitUntil(
      cdp,
      `(() => {
        const id = new URL(location.href).searchParams.get('draft') || '';
        const name = document.querySelector('[data-helper-builder-form] [name="name"]')?.value || '';
        return id && id !== ${JSON.stringify("__INITIAL__")} && name.includes('SOP');
      })()`.replace(JSON.stringify("__INITIAL__"), JSON.stringify(initialDraftId)),
      args.timeoutMs,
    );
    const activeDraftId = await cdp.evaluate("new URL(location.href).searchParams.get('draft') || ''");
    await cdp.evaluate(`
      (() => {
        const form = document.querySelector('[data-helper-builder-form]');
        const instructions = form.elements.instructions;
        instructions.value = '현재 업무 맥락과 검토된 BoI 지식을 먼저 확인하고, SOP를 Task와 완료된 모습, 확인할 자료로 구체화해줘.';
        instructions.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: instructions.value }));
        return true;
      })()
    `);
    await waitUntil(cdp, "document.querySelector('[data-helper-save-state]')?.textContent.includes('자동 저장됨')", args.timeoutMs);
    await cdp.evaluate(`
      (() => {
        const form = document.querySelector('[data-helper-preview-form]');
        form.elements.question.value = '직개발 결과 확인 및 Reporting SOP를 참고해 Task 3개짜리 private SOP 초안을 만들어줘.';
        form.requestSubmit();
        return true;
      })()
    `);
    await waitUntil(
      cdp,
      "document.querySelector('[data-helper-preview-status]')?.textContent.includes('시험 완료') && !!window.__helperPreviewResponse",
      args.timeoutMs,
    );

    const snapshot = await cdp.evaluate(`
      (() => {
        const text = document.body.innerText;
        const layout = document.querySelector('.helper-gems-layout');
        const preview = window.__helperPreviewResponse || {};
        return {
          readyState: document.readyState,
          url: location.href,
          title: document.title,
          hasBuilder: !!document.querySelector('[data-helper-builder-v2]'),
          activeNav: document.querySelector('[data-subnav-id="agent_builder"]')?.textContent.trim() || '',
          heading: document.querySelector('.helper-builder-v2-header h2')?.textContent.trim() || '',
          templateCount: document.querySelectorAll('[data-template-id]').length,
          gridColumns: getComputedStyle(layout).gridTemplateColumns,
          saveState: document.querySelector('[data-helper-save-state]')?.textContent || '',
          previewStatus: document.querySelector('[data-helper-preview-status]')?.textContent || '',
          previewMessageCount: document.querySelectorAll('[data-helper-preview-messages] article').length,
          previewCapability: preview.capability_id || '',
          previewGrounding: preview.grounding_status || '',
          previewArtifactType: preview.artifact_refs?.[0]?.artifact_type || '',
          previewSessionId: preview.work_session_id || '',
          advancedClosed: !document.querySelector('.helper-builder-advanced')?.open,
          technicalTermsVisible: /pgvector|DeepAgents|LangGraph|raw payload|context manifest/.test(text),
          horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
        };
      })()
    `);

    if (args.screenshot) await cdp.screenshot(args.screenshot);
    const checks = {
      page_loaded: snapshot.readyState === "complete" && snapshot.hasBuilder,
      boi_agent_branding: snapshot.title.includes("나만의 BoI Agent") && snapshot.activeNav === "BoI Agent 만들기",
      simple_templates_present: snapshot.templateCount === 3,
      two_column_builder: snapshot.gridColumns.trim().split(/\s+/).length === 2,
      autosave_completed: snapshot.saveState.includes("자동 저장됨"),
      real_preview_completed: snapshot.previewStatus.includes("시험 완료") && snapshot.previewMessageCount >= 2,
      preview_uses_agent_contract: !!snapshot.previewCapability && snapshot.previewGrounding === "grounded",
      preview_returns_editable_artifact: snapshot.previewArtifactType === "sop_draft" && !!snapshot.previewSessionId,
      advanced_settings_are_progressive: snapshot.advancedClosed && !snapshot.technicalTermsVisible,
      no_horizontal_overflow: !snapshot.horizontalOverflow,
      console_clean: relevantConsoleErrors(consoleErrors).length === 0,
    };
    const report = {
      ok: Object.values(checks).every(Boolean),
      checks,
      snapshot,
      consoleErrors,
      ignoredConsoleErrors: consoleErrors.filter((item) => !relevantConsoleErrors([item]).length),
      screenshot: args.screenshot,
      browser: "Chrome DevTools Protocol",
      browserFallbackReason: "Browser plugin not available; used repo CDP smoke harness.",
    };
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !report.ok) process.exitCode = 1;
    await cdp.evaluate(`
      (async () => {
        const ids = ${JSON.stringify([initialDraftId, activeDraftId])};
        const sessionId = window.__helperPreviewResponse?.work_session_id || '';
        if (sessionId) await fetch('/api/v2/work-sessions/' + encodeURIComponent(sessionId), { method: 'DELETE' });
        for (const id of ids) if (id) await fetch('/api/v2/helper-drafts/' + encodeURIComponent(id), { method: 'DELETE' });
        return true;
      })()
    `);
  } finally {
    cdp?.close();
    await terminateChrome(child);
    rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.message, stack: error.stack }, null, 2));
  process.exit(1);
});
