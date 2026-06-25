#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdtempSync, rmSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function parseArgs(argv) {
  const args = {
    url: "http://localhost:8000/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    question: "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
    timeoutMs: 90000,
    screenshot: "",
    strict: false,
    expectArtifact: "mermaid",
    approveExecutionCard: false,
    expectApprovalStatus: "",
  };
  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--url") args.url = argv[++index];
    else if (item === "--question") args.question = argv[++index];
    else if (item === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (item === "--screenshot") args.screenshot = argv[++index];
    else if (item === "--expect-artifact") args.expectArtifact = argv[++index] || args.expectArtifact;
    else if (item === "--approve-execution-card") args.approveExecutionCard = true;
    else if (item === "--expect-approval-status") args.expectApprovalStatus = argv[++index] || "";
    else if (item === "--strict") args.strict = true;
    else if (item === "-h" || item === "--help") {
      console.log(`Usage: node scripts/check_pet_agent_ui.mjs [--url URL] [--question TEXT] [--expect-artifact mermaid|workflow_summary|table|confirmation_required] [--approve-execution-card] [--expect-approval-status STATUS] [--screenshot FILE] [--strict]`);
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
  if (!chrome) throw new Error("Chrome/Chromium binary not found. Set CHROME_BIN to run Pet Agent UI smoke.");
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
      return await fetchJson(url, 1200);
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

  once(method) {
    return new Promise((resolve) => {
      const listener = (params) => {
        this.off(method, listener);
        resolve(params);
      };
      this.on(method, listener);
    });
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(listener);
  }

  off(method, listener) {
    this.listeners.get(method)?.delete(listener);
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

  close() {
    this.ws?.close();
  }
}

async function waitUntil(cdp, expression, timeoutMs, intervalMs = 150) {
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
  const exited = new Promise((resolve) => {
    child.once("exit", resolve);
  });
  child.kill("SIGTERM");
  await Promise.race([exited, sleep(2000)]);
  if (!child.killed) {
    child.kill("SIGKILL");
    await Promise.race([exited, sleep(1000)]);
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const chrome = findChrome();
  const profileDir = mkdtempSync(join(tmpdir(), "boi-agent-chrome-"));
  const port = 9333 + Math.floor(Math.random() * 1000);
  const child = spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  let cdp;
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`, 10000);
    const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`, 5000);
    const pageTarget = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
    if (!pageTarget) throw new Error("Chrome page target not found");
    cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");
    const networkProbe = {
      suggestionRequests: 0,
      suggestionUrls: [],
    };
    cdp.on("Network.requestWillBeSent", (params) => {
      const url = String(params.request?.url || "");
      if (url.includes("/api/agents/boi-wiki/suggestions")) {
        networkProbe.suggestionRequests += 1;
        networkProbe.suggestionUrls.push(url);
      }
    });
    const loaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: args.url });
    await loaded;
    await waitUntil(
      cdp,
      "document.readyState === 'complete' && !!document.querySelector('#boi-agent-root .boi-agent-launcher')",
      15000,
    );

    await cdp.evaluate(`(() => {
      window.__boiAgentUiProbe = {
        answerTexts: [],
        liveStatuses: [],
        statusTrailCounts: [],
        stopSeen: false,
        panelOpenSeen: false,
        viewerSeen: false,
        lastRenderAt: Date.now(),
      };
      const root = document.querySelector("#boi-agent-root");
      const record = () => {
        const probe = window.__boiAgentUiProbe;
        const panel = root.querySelector(".boi-agent-panel.open");
        const answer = root.querySelector(".boi-agent-message.assistant:last-of-type .boi-agent-answer");
        const status = root.querySelector(".boi-agent-live-status span");
        const trail = root.querySelectorAll(".boi-agent-status-trail li");
        if (panel) probe.panelOpenSeen = true;
        if (root.querySelector(".boi-agent-stop")) probe.stopSeen = true;
        if (root.querySelector(".boi-agent-viewer")) probe.viewerSeen = true;
        if (status && status.textContent.trim()) probe.liveStatuses.push(status.textContent.trim());
        if (trail.length) probe.statusTrailCounts.push(trail.length);
        if (answer) {
          const text = answer.textContent.trim();
          if (text && probe.answerTexts[probe.answerTexts.length - 1] !== text) probe.answerTexts.push(text);
        }
        probe.lastRenderAt = Date.now();
      };
      window.__boiAgentUiObserver = new MutationObserver(record);
      window.__boiAgentUiObserver.observe(root, { childList: true, subtree: true, characterData: true });
      window.__boiAgentUiTimer = setInterval(record, 50);
      record();
      return true;
    })()`);

    await cdp.evaluate(`(() => {
      document.querySelector(".boi-agent-launcher").click();
      return true;
    })()`);
    await waitUntil(cdp, "!!document.querySelector('.boi-agent-panel.open .boi-agent-chat-form textarea')", 10000);
    await cdp.evaluate(`(() => {
      const textarea = document.querySelector(".boi-agent-chat-form textarea");
      textarea.value = ${JSON.stringify(args.question)};
      textarea.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: textarea.value }));
      document.querySelector(".boi-agent-chat-form").requestSubmit();
      return true;
    })()`);

    await waitUntil(
      cdp,
      `(() => {
        const root = document.querySelector("#boi-agent-root");
        const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
        const answer = latest?.querySelector(".boi-agent-answer");
        const artifact = latest?.querySelector(".boi-agent-artifact");
        return !root.querySelector(".boi-agent-stop") && latest && ((answer && answer.textContent.trim().length > 30) || artifact);
      })()`,
      args.timeoutMs,
      250,
    );

    try {
      await waitUntil(
        cdp,
        `(() => {
          const latest = document.querySelector("#boi-agent-root .boi-agent-message.assistant:last-of-type");
          const diagrams = Array.from(latest?.querySelectorAll(".mermaid-diagram") || []);
          return diagrams.length > 0 && diagrams.every((diagram) => !["pending", "rendering"].includes(diagram.dataset.mermaidState || "pending"));
        })()`,
        12000,
        250,
      );
    } catch (_error) {
      // The strict report below records whether Mermaid actually rendered or fell back.
    }
    try {
      await waitUntil(
        cdp,
        `document.querySelectorAll("#boi-agent-root .boi-agent-suggestions [data-question]").length > 0`,
        12000,
        250,
      );
    } catch (_error) {
      // The structured report below records whether suggestion buttons returned.
    }

    await cdp.evaluate(`(() => {
      document.querySelector(".boi-agent-expand")?.click();
      return true;
    })()`);
    await sleep(150);
    const beforeNew = await cdp.evaluate(`(() => {
      const root = document.querySelector("#boi-agent-root");
      const probe = window.__boiAgentUiProbe || {};
      const uniqueAnswers = Array.from(new Set(probe.answerTexts || []));
      const latestMessage = root.querySelector(".boi-agent-message.assistant:last-of-type");
      const answerNode = latestMessage?.querySelector(".boi-agent-answer");
      const diagrams = Array.from(latestMessage?.querySelectorAll(".boi-agent-artifacts .mermaid-diagram, .boi-agent-answer .mermaid-diagram") || []);
      const normalizedSources = new Set(diagrams.map((diagram) => {
        const source = diagram.querySelector(".mermaid-source-fallback code")?.textContent || diagram.querySelector(".mermaid")?.textContent || "";
        return source.trim().replace(/\\s+/g, " ");
      }).filter(Boolean));
      const answerText = answerNode?.textContent || "";
      return {
        panelOpen: !!root.querySelector(".boi-agent-panel.open"),
        expanded: !!root.querySelector(".boi-agent-panel.expanded"),
        stopSeen: !!probe.stopSeen,
        liveStatusCount: (probe.liveStatuses || []).length,
        statusTrailMax: Math.max(0, ...(probe.statusTrailCounts || [0])),
        answerSnapshotCount: uniqueAnswers.length,
        answerTextLength: (uniqueAnswers[uniqueAnswers.length - 1] || "").length,
        viewerOpen: !!root.querySelector(".boi-agent-viewer"),
        hasNewButton: !!root.querySelector(".boi-agent-new"),
        hasExpandButton: !!root.querySelector(".boi-agent-expand"),
        hasStopButtonNow: !!root.querySelector(".boi-agent-stop"),
        hasArtifactOpenButton: !!root.querySelector("[data-open-artifact]"),
        hasAnswerOpenButton: !!root.querySelector("[data-open-answer]"),
        hasHorizontalOverflow: root.querySelector(".boi-agent-content") ? root.querySelector(".boi-agent-content").scrollWidth > root.querySelector(".boi-agent-content").clientWidth + 2 : false,
        mermaidDiagramCount: diagrams.length,
        mermaidRenderedCount: diagrams.filter((diagram) => diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg")).length,
        mermaidFallbackCount: diagrams.filter((diagram) => diagram.dataset.mermaidState === "fallback").length,
        uniqueMermaidSourceCount: normalizedSources.size,
        answerMarkdownTableCount: answerNode ? answerNode.querySelectorAll(".boi-agent-table-wrap table, .markdown-table").length : 0,
        artifactTableCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-artifacts .boi-agent-table-wrap table").length : 0,
        confirmationCardCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-confirmation-card").length : 0,
        approveButtonCount: latestMessage ? latestMessage.querySelectorAll("[data-agent-approve]").length : 0,
        rawMermaidFenceLeak: new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(answerText),
        rawTableSeparatorLeak: new RegExp("\\\\|\\\\s*:?-{3,}:?\\\\s*\\\\|").test(answerText),
        suggestionButtonCount: root.querySelectorAll(".boi-agent-suggestions [data-question]").length,
      };
    })()`);

    await cdp.evaluate(`(() => {
      document.querySelector("[data-open-artifact]")?.click();
      return true;
    })()`);
    await waitUntil(cdp, "!!document.querySelector('#boi-agent-root .boi-agent-viewer')", 5000);
    try {
      await waitUntil(
        cdp,
        `(() => {
          const viewer = document.querySelector("#boi-agent-root .boi-agent-viewer");
          const diagram = viewer?.querySelector(".mermaid-diagram");
          if (!diagram) return true;
          return diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg");
        })()`,
        8000,
        250,
      );
    } catch (_error) {
      // The structured viewer report below records whether the diagram rendered.
    }
    const artifactViewer = await cdp.evaluate(`(() => {
      const viewer = document.querySelector("#boi-agent-root .boi-agent-viewer");
      const diagram = viewer?.querySelector(".mermaid-diagram");
      return {
        open: !!viewer,
        hasMermaid: !!diagram,
        hasTable: !!viewer?.querySelector(".boi-agent-table-wrap table, .markdown-table"),
        hasConfirmation: !!viewer?.querySelector(".boi-agent-confirmation-card"),
        hasApproveButton: !!viewer?.querySelector("[data-agent-approve]"),
        mermaidRendered: !diagram || (diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg")),
        rawMermaidFenceLeak: viewer ? new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(viewer.textContent || "") : false,
      };
    })()`);
    await cdp.evaluate(`document.querySelector("#boi-agent-root .boi-agent-viewer-close")?.click()`);
    await sleep(150);

    await cdp.evaluate(`(() => {
      document.querySelector("[data-open-answer]")?.click();
      return true;
    })()`);
    await waitUntil(cdp, "!!document.querySelector('#boi-agent-root .boi-agent-viewer')", 5000);
    const answerViewer = await cdp.evaluate(`(() => {
      const viewer = document.querySelector("#boi-agent-root .boi-agent-viewer");
      return {
        open: !!viewer,
        hasAnswer: !!viewer?.querySelector(".boi-agent-answer-viewer"),
        hasTable: !!viewer?.querySelector(".boi-agent-table-wrap table, .markdown-table"),
      };
    })()`);
    await cdp.evaluate(`document.querySelector("#boi-agent-root .boi-agent-viewer-close")?.click()`);
    await sleep(150);

    let approvalResult = { skipped: !args.approveExecutionCard };
    if (args.approveExecutionCard) {
      const beforeApproveCount = await cdp.evaluate(`document.querySelectorAll("#boi-agent-root .boi-agent-message").length`);
      await cdp.evaluate(`(() => {
        const note = document.querySelector("#boi-agent-root .boi-agent-confirmation-card [data-agent-approve-note]");
        if (note) {
          note.value = "Pet Agent UI smoke confirmation";
          note.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: note.value }));
        }
        document.querySelector("#boi-agent-root [data-agent-approve]")?.click();
        return true;
      })()`);
      await waitUntil(
        cdp,
        `(() => {
          const root = document.querySelector("#boi-agent-root");
          const count = root.querySelectorAll(".boi-agent-message").length;
          const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
          return !root.querySelector("[data-agent-approve][disabled]") && count > ${Number(beforeApproveCount)} && latest && latest.textContent.trim().length > 10;
        })()`,
        args.timeoutMs,
        250,
      );
      approvalResult = await cdp.evaluate(`(() => {
        const messages = Array.from(document.querySelectorAll("#boi-agent-root .boi-agent-message.assistant"));
        const latest = messages[messages.length - 1];
        const text = latest?.textContent.trim() || "";
        return {
          skipped: false,
          messageCount: document.querySelectorAll("#boi-agent-root .boi-agent-message").length,
          latestText: text,
          containsDraftCreated: text.includes("이벤트 유형 초안을 만들었습니다"),
          containsExecuted: /요청을 처리했습니다|요청을 보냈습니다|초안을 만들었습니다|반영했습니다/.test(text),
        };
      })()`);
    }

    const navUrl = new URL(args.url);
    navUrl.pathname = "/sops";
    navUrl.search = "employee_id=100001";
    const navLoaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: navUrl.toString() });
    await navLoaded;
    await waitUntil(
      cdp,
      "document.readyState === 'complete' && !!document.querySelector('#boi-agent-root .boi-agent-launcher')",
      15000,
    );
    try {
      await waitUntil(
        cdp,
        `(() => {
          const root = document.querySelector("#boi-agent-root");
          const latest = root?.querySelector(".boi-agent-message.assistant:last-of-type");
          const diagrams = Array.from(latest?.querySelectorAll(".mermaid-diagram") || []);
          return diagrams.length > 0 && diagrams.every((diagram) => diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg"));
        })()`,
        12000,
        250,
      );
    } catch (_error) {
      // The structured report below records restoration/render status.
    }
    const afterNavigation = await cdp.evaluate(`(() => {
      const root = document.querySelector("#boi-agent-root");
      const latest = root?.querySelector(".boi-agent-message.assistant:last-of-type");
      const diagrams = Array.from(latest?.querySelectorAll(".mermaid-diagram") || []);
      const answerText = latest?.querySelector(".boi-agent-answer")?.textContent || "";
      return {
        panelOpen: !!root?.querySelector(".boi-agent-panel.open"),
        messageCount: root?.querySelectorAll(".boi-agent-message").length || 0,
        mermaidDiagramCount: diagrams.length,
        mermaidRenderedCount: diagrams.filter((diagram) => diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg")).length,
        artifactTableCount: latest ? latest.querySelectorAll(".boi-agent-artifacts .boi-agent-table-wrap table").length : 0,
        rawMermaidFenceLeak: new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(answerText),
      };
    })()`);

    if (args.screenshot) {
      const screenshot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
      createWriteStream(args.screenshot).end(Buffer.from(screenshot.data, "base64"));
    }

    await cdp.evaluate(`(() => {
      document.querySelector(".boi-agent-viewer-close")?.click();
      document.querySelector(".boi-agent-new")?.click();
      return true;
    })()`);
    await sleep(150);
    const afterNew = await cdp.evaluate(`(() => {
      const root = document.querySelector("#boi-agent-root");
      return {
        messageCount: root.querySelectorAll(".boi-agent-message").length,
        draft: root.querySelector(".boi-agent-chat-form textarea")?.value || "",
      };
    })()`);

    const expectsMermaid = args.expectArtifact === "mermaid";
    const expectsTable = ["workflow_summary", "table"].includes(args.expectArtifact);
    const expectsConfirmation = args.expectArtifact === "confirmation_required";
    const checks = {
      panel_opened: beforeNew.panelOpen,
      stop_seen_during_generation: beforeNew.stopSeen,
      live_status_seen: beforeNew.liveStatusCount > 0,
      status_trail_seen: beforeNew.statusTrailMax >= 1,
      streamed_answer_updates_seen: beforeNew.answerSnapshotCount >= 2 || beforeNew.answerTextLength < 180,
      answer_rendered: beforeNew.answerTextLength > 30 || beforeNew.mermaidDiagramCount > 0 || beforeNew.artifactTableCount > 0,
      expand_control_worked: beforeNew.expanded,
      no_horizontal_overflow: !beforeNew.hasHorizontalOverflow,
      artifact_viewer_opened: artifactViewer.open,
      artifact_viewer_expected_content: expectsMermaid
        ? artifactViewer.open && artifactViewer.mermaidRendered && !artifactViewer.rawMermaidFenceLeak
        : expectsConfirmation
          ? artifactViewer.open && artifactViewer.hasConfirmation && artifactViewer.hasApproveButton
          : artifactViewer.open && artifactViewer.hasTable,
      answer_viewer_opened: expectsTable ? (answerViewer.open && answerViewer.hasAnswer && answerViewer.hasTable) : (answerViewer.open && answerViewer.hasAnswer),
      state_restored_after_navigation: afterNavigation.panelOpen && afterNavigation.messageCount >= 2,
      artifact_restored_after_navigation: expectsMermaid
        ? afterNavigation.mermaidDiagramCount >= 1 && afterNavigation.mermaidRenderedCount >= 1 && !afterNavigation.rawMermaidFenceLeak
        : expectsTable
          ? afterNavigation.artifactTableCount >= 1
          : true,
      mermaid_diagram_present: expectsMermaid ? beforeNew.mermaidDiagramCount >= 1 : true,
      mermaid_diagram_rendered: expectsMermaid ? beforeNew.mermaidRenderedCount >= 1 && beforeNew.mermaidFallbackCount === 0 : true,
      mermaid_not_duplicated: expectsMermaid ? beforeNew.mermaidDiagramCount === beforeNew.uniqueMermaidSourceCount : true,
      markdown_table_rendered: expectsTable ? (beforeNew.answerMarkdownTableCount + beforeNew.artifactTableCount) >= 1 : true,
      expected_table_artifact_rendered: expectsTable ? beforeNew.artifactTableCount >= 1 : true,
      confirmation_card_rendered: expectsConfirmation ? beforeNew.confirmationCardCount >= 1 && beforeNew.approveButtonCount >= 1 : true,
      execution_card_approved: args.approveExecutionCard ? approvalResult.containsExecuted === true : true,
      expected_approval_status_seen: args.expectApprovalStatus ? String(approvalResult.latestText || "").includes(args.expectApprovalStatus) : true,
      suggestions_refreshed_through_api: networkProbe.suggestionRequests >= 2 && beforeNew.suggestionButtonCount >= 1,
      no_raw_markdown_leak: !beforeNew.rawMermaidFenceLeak && !beforeNew.rawTableSeparatorLeak,
      new_chat_cleared_messages: afterNew.messageCount === 0 && afterNew.draft === "",
    };
    const ok = Object.values(checks).every(Boolean);
    const report = { ok, url: args.url, checks, network: networkProbe, before_new: beforeNew, artifact_viewer: artifactViewer, answer_viewer: answerViewer, approval: approvalResult, after_navigation: afterNavigation, after_new: afterNew, screenshot: args.screenshot || "" };
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !ok) process.exitCode = 1;
  } finally {
    try { cdp?.close(); } catch (_error) {}
    await terminateChrome(child);
    try {
      rmSync(profileDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    } catch (_error) {
      // Chrome may leave transient Windows/WSL profile locks. The smoke result is more important than cleanup.
    }
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.message }, null, 2));
  process.exit(1);
});
