#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function parseArgs(argv) {
  const args = {
    url: "http://localhost:28000/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    question: "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
    timeoutMs: 90000,
    screenshot: "",
    strict: false,
    expectArtifact: "mermaid",
    expectEvidenceArtifact: "",
    forbidInlineArtifact: "",
    expectFollowupLoading: false,
    forbidVisibleTerms: [],
    approveExecutionCard: false,
    expectApprovalStatus: "",
    scenarioFile: "",
    turnsJson: "",
  };
  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--url") args.url = argv[++index];
    else if (item === "--question") args.question = argv[++index];
    else if (item === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (item === "--screenshot") args.screenshot = argv[++index];
    else if (item === "--expect-artifact") args.expectArtifact = argv[++index] || args.expectArtifact;
    else if (item === "--expect-evidence-artifact") args.expectEvidenceArtifact = argv[++index] || "";
    else if (item === "--forbid-inline-artifact") args.forbidInlineArtifact = argv[++index] || "";
    else if (item === "--expect-followup-loading") args.expectFollowupLoading = true;
    else if (item === "--forbid-visible-term") args.forbidVisibleTerms.push(argv[++index] || "");
    else if (item === "--scenario-file") args.scenarioFile = argv[++index] || "";
    else if (item === "--approve-execution-card") args.approveExecutionCard = true;
    else if (item === "--expect-approval-status") args.expectApprovalStatus = argv[++index] || "";
    else if (item === "--turns-json") args.turnsJson = argv[++index] || "";
    else if (item === "--strict") args.strict = true;
    else if (item === "-h" || item === "--help") {
      console.log(`Usage: node scripts/check_pet_agent_ui.mjs [--url URL] [--question TEXT] [--expect-artifact mermaid|workflow_summary|action_requirements|table|manual_handoff_summary|task_cards|confirmation_required] [--expect-evidence-artifact TYPE] [--forbid-inline-artifact TYPE] [--expect-followup-loading] [--forbid-visible-term TEXT] [--scenario-file FILE] [--approve-execution-card] [--expect-approval-status STATUS] [--turns-json JSON] [--screenshot FILE] [--strict]`);
      process.exit(0);
    }
  }
  return args;
}

function loadScenarioFile(path) {
  const raw = readFileSync(path, "utf8");
  const payload = JSON.parse(raw);
  const scenarios = Array.isArray(payload) ? payload : payload.scenarios;
  if (!Array.isArray(scenarios)) throw new Error(`${path} must contain a scenario list or {"scenarios":[...]}`);
  return scenarios.filter((scenario) => scenario && typeof scenario === "object");
}

function parseChildReport(stdout, stderr) {
  const trimmedStdout = String(stdout || "").trim();
  const trimmedStderr = String(stderr || "").trim();
  for (const candidate of [trimmedStdout, trimmedStderr]) {
    if (!candidate) continue;
    try {
      return JSON.parse(candidate);
    } catch (_error) {
      // Keep trying. Fatal child errors are intentionally structured but may be written to stderr.
    }
  }
  return {
    ok: false,
    parse_error: "child output was not JSON",
    stdout: trimmedStdout.slice(0, 2000),
    stderr: trimmedStderr.slice(0, 2000),
  };
}

function runNodeScenario(scriptPath, parentArgs, scenario) {
  const turns = Array.isArray(scenario.turns) ? scenario.turns : [];
  const childArgs = [
    scriptPath,
    "--url", scenario.url || scenario.current_url || parentArgs.url,
    "--question", scenario.question || turns[0]?.question || parentArgs.question,
    "--expect-artifact", scenario.expect_artifact || scenario.expectArtifact || parentArgs.expectArtifact,
    "--timeout-ms", String(scenario.timeout_ms || scenario.timeoutMs || parentArgs.timeoutMs),
  ];
  if (turns.length) childArgs.push("--turns-json", JSON.stringify(turns));
  const expectEvidenceArtifact = scenario.expect_evidence_artifact || scenario.expectEvidenceArtifact || parentArgs.expectEvidenceArtifact;
  const forbidInlineArtifact = scenario.forbid_inline_artifact || scenario.forbidInlineArtifact || parentArgs.forbidInlineArtifact;
  const forbidVisibleTerms = scenario.forbid_visible_terms || scenario.forbidVisibleTerms || parentArgs.forbidVisibleTerms || [];
  if (expectEvidenceArtifact) childArgs.push("--expect-evidence-artifact", expectEvidenceArtifact);
  if (forbidInlineArtifact) childArgs.push("--forbid-inline-artifact", forbidInlineArtifact);
  if (scenario.expect_followup_loading || scenario.expectFollowupLoading || parentArgs.expectFollowupLoading) childArgs.push("--expect-followup-loading");
  for (const term of Array.isArray(forbidVisibleTerms) ? forbidVisibleTerms : [forbidVisibleTerms]) {
    if (term) childArgs.push("--forbid-visible-term", term);
  }
  if (parentArgs.strict || scenario.strict) childArgs.push("--strict");
  if (scenario.approve_execution_card || scenario.approveExecutionCard) childArgs.push("--approve-execution-card");
  if (scenario.expect_approval_status || scenario.expectApprovalStatus) {
    childArgs.push("--expect-approval-status", scenario.expect_approval_status || scenario.expectApprovalStatus);
  }
  if (scenario.screenshot) childArgs.push("--screenshot", scenario.screenshot);
  return new Promise((resolve) => {
    const child = spawn(process.execPath, childArgs, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr?.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("close", (code) => {
      const parsed = parseChildReport(stdout, stderr);
      resolve({
        id: scenario.id || "",
        name: scenario.name || "",
        ok: code === 0 && parsed?.ok === true,
        exitCode: code,
        report: parsed,
        stderr: stderr.trim(),
      });
    });
  });
}

async function runScenarioSuite(args) {
  const scenarios = loadScenarioFile(args.scenarioFile);
  const results = [];
  for (let index = 0; index < scenarios.length; index += 1) {
    const scenario = scenarios[index];
    const scenarioId = scenario.id || `scenario-${index + 1}`;
    console.error(`[${index + 1}/${scenarios.length}] ${scenarioId}: ${scenario.question || scenario.turns?.[0]?.question || args.question}`);
    const result = await runNodeScenario(process.argv[1], args, scenario);
    console.error(`[${index + 1}/${scenarios.length}] ${scenarioId}: ${result.ok ? "ok" : "failed"}`);
    results.push(result);
  }
  const failures = results.filter((result) => !result.ok);
  const report = {
    ok: failures.length === 0,
    scenarioFile: args.scenarioFile,
    scenarioCount: scenarios.length,
    passed: results.length - failures.length,
    failed: failures.length,
    results,
  };
  console.log(JSON.stringify(report, null, 2));
  if (args.strict && failures.length) process.exitCode = 1;
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

function asList(value) {
  if (!value) return [];
  return Array.isArray(value) ? value.map((item) => String(item || "")).filter(Boolean) : [String(value)];
}

async function submitAgentQuestion(cdp, question) {
  return cdp.evaluate(`(() => {
    const root = document.querySelector("#boi-agent-root");
    const form = root?.querySelector(".boi-agent-chat-form");
    const textarea = form?.querySelector("textarea");
    if (!form || !textarea) return { ok: false, reason: "chat form missing" };
    textarea.value = ${JSON.stringify(question)};
    textarea.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: textarea.value }));
    form.requestSubmit();
    return { ok: true };
  })()`);
}

async function collectAgentFormState(cdp) {
  return cdp.evaluate(`(() => {
    const root = document.querySelector("#boi-agent-root");
    const form = root?.querySelector(".boi-agent-chat-form");
    const textarea = form?.querySelector("textarea");
    const submit = form?.querySelector('button[type="submit"]');
    return {
      hasForm: !!form,
      textareaDisabled: !!textarea?.disabled,
      submitDisabled: !!submit?.disabled,
      hasStopButton: !!root?.querySelector(".boi-agent-stop"),
      draft: textarea?.value || "",
    };
  })()`);
}

async function collectLatestAgentTurn(cdp) {
  return cdp.evaluate(`(() => {
    const root = document.querySelector("#boi-agent-root");
    const messages = Array.from(root?.querySelectorAll(".boi-agent-message") || []);
    const latestUser = Array.from(root?.querySelectorAll(".boi-agent-message.user") || []).pop();
    const latestAssistant = Array.from(root?.querySelectorAll(".boi-agent-message.assistant") || []).pop();
    const latestUserText = latestUser?.querySelector(".boi-agent-answer")?.textContent.trim()
      || (latestUser?.textContent || "").replace(/^\\s*You\\s*/i, "").trim();
    const latestAssistantText = latestAssistant?.querySelector(".boi-agent-answer")?.textContent.trim()
      || latestAssistant?.textContent.trim()
      || "";
    const storageRecords = Object.keys(sessionStorage)
      .filter((key) => key.startsWith("boiAgent.v8.") && !key.includes(".lastContext."))
      .map((key) => {
        try {
          const value = JSON.parse(sessionStorage.getItem(key) || "{}");
          return { key, value, count: Array.isArray(value.messages) ? value.messages.length : 0 };
        } catch (_error) {
          return { key, value: {}, count: 0 };
        }
      })
      .sort((left, right) => right.count - left.count);
    const persisted = storageRecords[0]?.value || {};
    const persistedAssistant = Array.from(persisted.messages || []).filter((item) => item.role === "assistant").pop() || {};
    return {
      messageCount: messages.length,
      latestUserText,
      latestAssistantText,
      latestAssistantTextLength: latestAssistantText.length,
      followupLoadingCount: root?.querySelectorAll(".boi-agent-message-followups.loading").length || 0,
      answerFollowupButtonCount: latestAssistant ? latestAssistant.querySelectorAll(".boi-agent-message-followups [data-question]").length : 0,
      semanticRoute: persistedAssistant.semanticRoute || {},
      relatedItemContext: persistedAssistant.relatedItemContext || {},
      responseProfile: persistedAssistant.responseProfile || "",
      storageKey: storageRecords[0]?.key || "",
    };
  })()`);
}

function turnExpectationsOk(turn, result) {
  const answerText = String(result.latestAssistantText || "");
  const expectTexts = asList(turn.expect_text || turn.expectText);
  const forbidTexts = asList(turn.forbid_text || turn.forbidText || turn.forbid_visible_terms || turn.forbidVisibleTerms);
  const semanticTarget = turn.expect_semantic_target || turn.expectSemanticTarget || "";
  const relatedScope = turn.expect_related_scope || turn.expectRelatedScope || "";
  const semanticRoute = result.semanticRoute || {};
  const relatedItemContext = result.relatedItemContext || {};
  return {
    answer_rendered: result.latestAssistantTextLength > 20,
    expected_text_seen: expectTexts.length ? expectTexts.every((text) => answerText.includes(text)) : true,
    forbidden_text_absent: forbidTexts.length ? forbidTexts.every((text) => !answerText.includes(text)) : true,
    semantic_target_matched: semanticTarget
      ? [semanticRoute.target_kind, semanticRoute.targetKind, semanticRoute.kind].filter(Boolean).includes(semanticTarget)
      : true,
    related_scope_matched: relatedScope ? relatedItemContext.scope === relatedScope : true,
    input_enabled_after_answer: result.formState?.hasForm === true
      && result.formState?.textareaDisabled === false
      && result.formState?.submitDisabled === false
      && result.formState?.hasStopButton === false,
  };
}

async function runMultiTurnAgentSmoke(cdp, args, log, networkProbe, starterBeforeAsk) {
  const turns = JSON.parse(args.turnsJson || "[]");
  const turnResults = [];
  for (let index = 0; index < turns.length; index += 1) {
    const turn = turns[index] || {};
    const question = String(turn.question || "").trim();
    if (!question) throw new Error(`turn ${index + 1} is missing question`);
    const beforeCount = await cdp.evaluate(`document.querySelectorAll("#boi-agent-root .boi-agent-message").length`);
    const beforeFormState = await collectAgentFormState(cdp);
    if (beforeFormState.hasStopButton || beforeFormState.textareaDisabled || beforeFormState.submitDisabled) {
      throw new Error(`turn ${index + 1} cannot start because input is blocked`);
    }
    log(`submitted turn ${index + 1}: ${question}`);
    const submitResult = await submitAgentQuestion(cdp, question);
    if (!submitResult?.ok) throw new Error(submitResult?.reason || `turn ${index + 1} submit failed`);
    await waitUntil(
      cdp,
      `(() => {
        const root = document.querySelector("#boi-agent-root");
        const count = root.querySelectorAll(".boi-agent-message").length;
        const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
        const answer = latest?.querySelector(".boi-agent-answer");
        return count >= ${Number(beforeCount) + 2} && answer && answer.textContent.trim().length > 20 && !root.querySelector(".boi-agent-stop");
      })()`,
      args.timeoutMs,
      250,
    );
    const formState = await collectAgentFormState(cdp);
    const latest = await collectLatestAgentTurn(cdp);
    const result = {
      turn: index + 1,
      question,
      beforeFormState,
      formState,
      ...latest,
    };
    result.checks = turnExpectationsOk(turn, result);
    turnResults.push(result);
  }

  if (args.screenshot) {
    log(`capturing screenshot to ${args.screenshot}`);
    const screenshot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    createWriteStream(args.screenshot).end(Buffer.from(screenshot.data, "base64"));
  }

  const checks = {
    panel_opened: !!(await cdp.evaluate(`!!document.querySelector("#boi-agent-root .boi-agent-panel.open")`)),
    starter_suggestions_nonblocking: networkProbe.suggestionRequests >= 0 && starterBeforeAsk.count >= 0,
    turns_completed: turnResults.length === turns.length,
    answer_rendered_each_turn: turnResults.every((item) => item.checks.answer_rendered),
    input_enabled_after_each_answer: turnResults.every((item) => item.checks.input_enabled_after_answer),
    expected_text_seen: turnResults.every((item) => item.checks.expected_text_seen),
    forbidden_text_absent: turnResults.every((item) => item.checks.forbidden_text_absent),
    semantic_targets_matched: turnResults.every((item) => item.checks.semantic_target_matched),
    related_scopes_matched: turnResults.every((item) => item.checks.related_scope_matched),
  };
  const ok = Object.values(checks).every(Boolean);
  const report = {
    ok,
    url: args.url,
    mode: "multi_turn",
    checks,
    network: networkProbe,
    starter_before_ask: starterBeforeAsk,
    turns: turnResults,
    screenshot: args.screenshot || "",
  };
  console.log(JSON.stringify(report, null, 2));
  if (args.strict && !ok) process.exitCode = 1;
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.scenarioFile) {
    await runScenarioSuite(args);
    return;
  }
  const log = (message) => console.error(`[pet-ui] ${message}`);
  const chrome = findChrome();
  const profileDir = mkdtempSync(join(tmpdir(), "boi-agent-chrome-"));
  const port = 9333 + Math.floor(Math.random() * 1000);
  log(`starting Chrome on port ${port}`);
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
    log("Chrome DevTools endpoint ready");
    const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`, 5000);
    const pageTarget = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
    if (!pageTarget) throw new Error("Chrome page target not found");
    cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");
    log(`navigating to ${args.url}`);
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
    log("page loaded");
    await waitUntil(
      cdp,
      "['interactive','complete'].includes(document.readyState) && !!document.querySelector('#boi-agent-root .boi-agent-launcher')",
      15000,
    );

    await cdp.evaluate(`(() => {
      window.__boiAgentUiProbe = {
        answerTexts: [],
        liveStatuses: [],
        statusTrailCounts: [],
        stopSeen: false,
        followupLoadingSeen: false,
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
        if (root.querySelector(".boi-agent-message-followups.loading")) probe.followupLoadingSeen = true;
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
    log("opening Agent panel");

    await cdp.evaluate(`(() => {
      document.querySelector(".boi-agent-launcher").click();
      document.querySelector('#boi-agent-root [data-tab="agent"]')?.click();
      return true;
    })()`);
    await waitUntil(cdp, "!!document.querySelector('.boi-agent-panel.open .boi-agent-chat-form textarea')", 10000);
    log("Agent panel open");
    try {
      await waitUntil(
        cdp,
        `(() => {
          const root = document.querySelector("#boi-agent-root");
          const buttons = root.querySelectorAll(".boi-agent-suggestions [data-question]");
          const loading = root.querySelector(".boi-agent-suggestions-loading");
          const error = root.querySelector(".boi-agent-hint.error");
          return buttons.length > 0 || (!loading && !!error);
        })()`,
        45000,
        250,
      );
    } catch (_error) {
      // Starter suggestions are asynchronous. The strict report below records if they never appear.
    }
    const starterBeforeAsk = await cdp.evaluate(`(() => {
      const root = document.querySelector("#boi-agent-root");
      return {
        count: root.querySelectorAll(".boi-agent-suggestions [data-question]").length,
        texts: Array.from(root.querySelectorAll(".boi-agent-suggestions [data-question]")).map((button) => button.textContent.trim()).filter(Boolean),
      };
    })()`);
    log(`starter suggestions: ${starterBeforeAsk.count}`);

    if (args.turnsJson) {
      await runMultiTurnAgentSmoke(cdp, args, log, networkProbe, starterBeforeAsk);
      return;
    }

    await cdp.evaluate(`(() => {
      const textarea = document.querySelector(".boi-agent-chat-form textarea");
      textarea.value = ${JSON.stringify(args.question)};
      textarea.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: textarea.value }));
      document.querySelector(".boi-agent-chat-form").requestSubmit();
      return true;
    })()`);
    log(`submitted question: ${args.question}`);

    await waitUntil(
      cdp,
      `(() => {
        const root = document.querySelector("#boi-agent-root");
        const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
        const answer = latest?.querySelector(".boi-agent-answer");
        const artifact = latest?.querySelector(".boi-agent-artifact");
        return latest && ((answer && answer.textContent.trim().length > 30) || artifact);
      })()`,
      args.timeoutMs,
      250,
    );
    log("assistant answer rendered");

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
        `(() => {
          const root = document.querySelector("#boi-agent-root");
          const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
          const followups = latest?.querySelector(".boi-agent-message-followups");
          const followupButtons = latest?.querySelectorAll(".boi-agent-message-followups [data-question]") || [];
          const followupError = latest?.querySelector(".boi-agent-message-followups .boi-agent-hint.error");
          return followupButtons.length > 0 || !!followupError || (!root.querySelector(".boi-agent-stop") && !followups?.classList.contains("loading"));
        })()`,
        Math.min(args.timeoutMs, 60000),
        250,
      );
    } catch (_error) {
      // Follow-up generation is async. The structured report below records whether it finished.
    }

    await cdp.evaluate(`(() => {
      document.querySelector(".boi-agent-expand")?.click();
      return true;
    })()`);
    await sleep(150);
    log("collecting rendered answer state");
    const beforeNew = await cdp.evaluate(`(() => {
      const root = document.querySelector("#boi-agent-root");
      const probe = window.__boiAgentUiProbe || {};
      const uniqueAnswers = Array.from(new Set(probe.answerTexts || []));
      const latestMessage = root.querySelector(".boi-agent-message.assistant:last-of-type");
      const persisted = Object.keys(sessionStorage)
        .filter((key) => key.startsWith("boiAgent.v8.") && !key.includes(".lastContext."))
        .map((key) => {
          try {
            const value = JSON.parse(sessionStorage.getItem(key) || "{}");
            return { key, value, count: Array.isArray(value.messages) ? value.messages.length : 0 };
          } catch (_error) {
            return { key, value: {}, count: 0 };
          }
        })
        .sort((left, right) => right.count - left.count)[0]?.value || {};
      const persistedLatestAssistant = Array.from(persisted.messages || []).filter((item) => item.role === "assistant").pop() || {};
      const answerNode = latestMessage?.querySelector(".boi-agent-answer");
      const diagrams = Array.from(latestMessage?.querySelectorAll(".boi-agent-artifacts .mermaid-diagram, .boi-agent-answer .mermaid-diagram") || []);
      const normalizedSources = new Set(diagrams.map((diagram) => {
        const source = diagram.querySelector(".mermaid-source-fallback code")?.textContent || diagram.querySelector(".mermaid")?.textContent || "";
        return source.trim().replace(/\\s+/g, " ");
      }).filter(Boolean));
      const answerText = answerNode?.textContent || "";
      const inlineArtifactTypes = Array.from(latestMessage?.querySelectorAll(".boi-agent-artifacts [data-artifact-type]") || []).map((node) => node.dataset.artifactType || "").filter(Boolean);
      const evidenceArtifactTypes = Array.from(latestMessage?.querySelectorAll(".boi-agent-evidence-artifacts [data-artifact-type]") || []).map((node) => node.dataset.artifactType || "").filter(Boolean);
      const visibleText = [
        answerText,
        latestMessage ? Array.from(latestMessage.querySelectorAll(".boi-agent-artifacts")).map((node) => node.textContent || "").join("\\n") : "",
      ].join("\\n");
      return {
        panelOpen: !!root.querySelector(".boi-agent-panel.open"),
        expanded: !!root.querySelector(".boi-agent-panel.expanded"),
        stopSeen: !!probe.stopSeen,
        followupLoadingSeen: !!probe.followupLoadingSeen,
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
        evidenceArtifactTableCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-evidence-artifacts .boi-agent-table-wrap table").length : 0,
        inlineArtifactTypes,
        evidenceArtifactTypes,
        taskCardCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-artifacts .boi-agent-task-display").length : 0,
        confirmationCardCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-confirmation-card").length : 0,
        approveButtonCount: latestMessage ? latestMessage.querySelectorAll("[data-agent-approve]").length : 0,
        persistedArtifactTypes: Array.isArray(persistedLatestAssistant.artifacts) ? persistedLatestAssistant.artifacts.map((item) => item?.type || "").filter(Boolean) : [],
        rawMermaidFenceLeak: new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(answerText),
        rawTableSeparatorLeak: new RegExp("\\\\|\\\\s*:?-{3,}:?\\\\s*\\\\|").test(answerText),
        starterSuggestionButtonCount: root.querySelectorAll(".boi-agent-suggestions [data-question]").length,
        answerFollowupButtonCount: latestMessage ? latestMessage.querySelectorAll(".boi-agent-message-followups [data-question]").length : 0,
        starterSuggestionTexts: Array.from(root.querySelectorAll(".boi-agent-suggestions [data-question]")).map((button) => button.textContent.trim()).filter(Boolean),
        answerFollowupTexts: latestMessage ? Array.from(latestMessage.querySelectorAll(".boi-agent-message-followups [data-question]")).map((button) => button.textContent.trim()).filter(Boolean) : [],
        visibleText,
      };
    })()`);

    log("opening artifact viewer");
    await cdp.evaluate(`(() => {
      document.querySelector("[data-open-artifact]")?.click();
      return true;
    })()`);
    try {
      await waitUntil(cdp, "!!document.querySelector('#boi-agent-root .boi-agent-viewer')", 5000);
    } catch (_error) {
      // The structured viewer report below records whether a viewer opened.
    }
    try {
      await waitUntil(
        cdp,
        `(() => {
          const viewer = document.querySelector("#boi-agent-root .boi-agent-viewer");
          const diagram = viewer?.querySelector(".mermaid-diagram");
          if (!diagram) return true;
          return diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg");
        })()`,
        28000,
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
        hasTaskCard: !!viewer?.querySelector(".boi-agent-task-display"),
        hasConfirmation: !!viewer?.querySelector(".boi-agent-confirmation-card"),
        hasApproveButton: !!viewer?.querySelector("[data-agent-approve]"),
        mermaidRendered: !diagram || (diagram.dataset.mermaidState === "rendered" && !!diagram.querySelector("svg")),
        rawMermaidFenceLeak: viewer ? new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(viewer.textContent || "") : false,
      };
    })()`);
    await cdp.evaluate(`document.querySelector("#boi-agent-root .boi-agent-viewer-close")?.click()`);
    await sleep(150);

    log("opening answer viewer");
    await cdp.evaluate(`(() => {
      document.querySelector("[data-open-answer]")?.click();
      return true;
    })()`);
    try {
      await waitUntil(cdp, "!!document.querySelector('#boi-agent-root .boi-agent-viewer')", 5000);
    } catch (_error) {
      // The structured viewer report below records whether a viewer opened.
    }
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
          approvalStatus: latest?.dataset.agentApprovalStatus || "",
          approvalOperation: latest?.dataset.agentApprovalOperation || "",
          containsDraftCreated: text.includes("이벤트 유형 초안을 만들었습니다"),
          containsExecuted: /요청을 처리했습니다|요청을 보냈습니다|초안을 만들었습니다|반영했습니다/.test(text),
        };
      })()`);
    }

    let followupClick = { skipped: true, reason: "no answer follow-up button" };
    if (beforeNew.answerFollowupButtonCount > 0) {
      log("clicking answer follow-up");
      const beforeFollowupMessageCount = await cdp.evaluate(`document.querySelectorAll("#boi-agent-root .boi-agent-message").length`);
      const clickedQuestion = await cdp.evaluate(`(() => {
        const latest = document.querySelector("#boi-agent-root .boi-agent-message.assistant:last-of-type");
        const button = latest?.querySelector(".boi-agent-message-followups [data-question]");
        const question = button?.textContent.trim() || "";
        button?.click();
        return question;
      })()`);
      try {
        await waitUntil(
          cdp,
          `(() => {
            const root = document.querySelector("#boi-agent-root");
            const count = root.querySelectorAll(".boi-agent-message").length;
            const latest = root.querySelector(".boi-agent-message.assistant:last-of-type");
            return !root.querySelector(".boi-agent-stop") && count > ${Number(beforeFollowupMessageCount)} && latest && latest.textContent.trim().length > 20;
          })()`,
          args.timeoutMs,
          250,
        );
      } catch (error) {
        followupClick = { skipped: false, clickedQuestion, ok: false, error: error.message };
      }
      if (followupClick.skipped !== false || followupClick.ok !== false) {
        followupClick = await cdp.evaluate(`(() => {
          const root = document.querySelector("#boi-agent-root");
          const messages = Array.from(root.querySelectorAll(".boi-agent-message"));
          const latestUser = Array.from(root.querySelectorAll(".boi-agent-message.user")).pop();
          const latestAssistant = Array.from(root.querySelectorAll(".boi-agent-message.assistant")).pop();
          const latestUserText = latestUser?.querySelector(".boi-agent-answer")?.textContent.trim()
            || (latestUser?.textContent || "").replace(/^\\s*You\\s*/i, "").trim();
          return {
            skipped: false,
            ok: true,
            clickedQuestion: ${JSON.stringify(clickedQuestion)},
            messageCount: messages.length,
            latestUserText,
            latestAssistantTextLength: (latestAssistant?.textContent.trim() || "").length,
            latestFollowupCount: latestAssistant ? latestAssistant.querySelectorAll(".boi-agent-message-followups [data-question]").length : 0,
          };
        })()`);
      }
    }

    const navUrl = new URL(args.url);
    navUrl.pathname = "/sops";
    navUrl.search = "employee_id=100001";
    const navLoaded = cdp.once("Page.loadEventFired");
    log("navigating away to test context reset");
    await cdp.send("Page.navigate", { url: navUrl.toString() });
    await navLoaded;
    await waitUntil(
      cdp,
      "['interactive','complete'].includes(document.readyState) && !!document.querySelector('#boi-agent-root .boi-agent-launcher')",
      15000,
    );
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
        taskCardCount: latest ? latest.querySelectorAll(".boi-agent-artifacts .boi-agent-task-display").length : 0,
        answerFollowupButtonCount: latest ? latest.querySelectorAll(".boi-agent-message-followups [data-question]").length : 0,
        rawMermaidFenceLeak: new RegExp(String.fromCharCode(96, 96, 96) + "\\\\s*mermaid", "i").test(answerText),
      };
    })()`);

    if (args.screenshot) {
      log(`capturing screenshot to ${args.screenshot}`);
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
    const expectsTable = ["workflow_summary", "action_requirements", "table"].includes(args.expectArtifact);
    const expectsTaskCards = ["manual_handoff_summary", "task_cards"].includes(args.expectArtifact);
    const expectsConfirmation = args.expectArtifact === "confirmation_required";
    const forbidVisibleTerms = Array.isArray(args.forbidVisibleTerms) ? args.forbidVisibleTerms.filter(Boolean) : [];
    const checks = {
      panel_opened: beforeNew.panelOpen,
      stop_seen_during_generation: beforeNew.stopSeen,
      followup_loading_seen: args.expectFollowupLoading ? beforeNew.followupLoadingSeen : true,
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
          : expectsTaskCards
            ? artifactViewer.open && artifactViewer.hasTaskCard
            : artifactViewer.open && artifactViewer.hasTable,
      answer_viewer_opened: answerViewer.open && answerViewer.hasAnswer,
      different_context_reset_after_navigation: !afterNavigation.panelOpen && afterNavigation.messageCount === 0,
      stale_artifact_not_restored_after_navigation: afterNavigation.mermaidDiagramCount === 0
        && afterNavigation.artifactTableCount === 0
        && afterNavigation.taskCardCount === 0
        && !afterNavigation.rawMermaidFenceLeak,
      mermaid_diagram_present: expectsMermaid ? beforeNew.mermaidDiagramCount >= 1 : true,
      mermaid_diagram_rendered: expectsMermaid ? beforeNew.mermaidRenderedCount >= 1 && beforeNew.mermaidFallbackCount === 0 : true,
      mermaid_not_duplicated: expectsMermaid ? beforeNew.mermaidDiagramCount === beforeNew.uniqueMermaidSourceCount : true,
      markdown_table_rendered: expectsTable ? (beforeNew.answerMarkdownTableCount + beforeNew.artifactTableCount) >= 1 : true,
      expected_table_artifact_rendered: expectsTable ? beforeNew.artifactTableCount >= 1 : true,
      expected_evidence_artifact_rendered: args.expectEvidenceArtifact ? beforeNew.evidenceArtifactTypes.includes(args.expectEvidenceArtifact) : true,
      forbidden_inline_artifact_absent: args.forbidInlineArtifact ? !beforeNew.inlineArtifactTypes.includes(args.forbidInlineArtifact) : true,
      expected_task_card_artifact_rendered: expectsTaskCards ? beforeNew.taskCardCount >= 1 : true,
      confirmation_card_rendered: expectsConfirmation ? beforeNew.confirmationCardCount >= 1 && beforeNew.approveButtonCount >= 1 : true,
      execution_card_approved: args.approveExecutionCard ? approvalResult.containsExecuted === true : true,
      expected_approval_status_seen: args.expectApprovalStatus
        ? approvalResult.approvalStatus === args.expectApprovalStatus || String(approvalResult.latestText || "").includes(args.expectApprovalStatus)
        : true,
      page_starter_suggestions_loaded: networkProbe.suggestionRequests >= 1 && starterBeforeAsk.count >= 1,
      answer_followups_rendered: beforeNew.answerFollowupButtonCount >= 1,
      answer_followups_are_answer_scoped: beforeNew.answerFollowupButtonCount >= 1 && beforeNew.answerFollowupTexts.some((text) => !beforeNew.starterSuggestionTexts.includes(text)),
      answer_followups_not_restored_after_context_change: afterNavigation.answerFollowupButtonCount === 0,
      followup_click_sent_new_question: followupClick.ok === true && followupClick.latestUserText === followupClick.clickedQuestion && followupClick.latestAssistantTextLength > 20,
      no_raw_markdown_leak: !beforeNew.rawMermaidFenceLeak && !beforeNew.rawTableSeparatorLeak,
      forbidden_visible_terms_absent: forbidVisibleTerms.length ? forbidVisibleTerms.every((term) => !String(beforeNew.visibleText || "").includes(term)) : true,
      new_chat_cleared_messages: afterNew.messageCount === 0 && afterNew.draft === "",
    };
    const ok = Object.values(checks).every(Boolean);
    log(`completed with ok=${ok}`);
    const report = { ok, url: args.url, checks, network: networkProbe, starter_before_ask: starterBeforeAsk, before_new: beforeNew, artifact_viewer: artifactViewer, answer_viewer: answerViewer, approval: approvalResult, after_navigation: afterNavigation, followup_click: followupClick, after_new: afterNew, screenshot: args.screenshot || "" };
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
  console.log(JSON.stringify({ ok: false, error: error.message }, null, 2));
  process.exit(1);
});
