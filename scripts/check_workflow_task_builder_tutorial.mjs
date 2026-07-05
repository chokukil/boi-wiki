#!/usr/bin/env node
import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve, relative } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import net from "node:net";

const ROOT = resolve(new URL("..", import.meta.url).pathname);
const DEFAULT_CAPTURE_DIR = "data/boi/public/boi-wiki-manual/_media/browser/workflow-task-builder";
const DEFAULT_MANIFEST_OUT = "data/boi/public/boi-wiki-manual/sop-workflows/workflow-task-builder-capture-manifest.json";
const VIEWPORT = { width: 1440, height: 1100 };

function parseArgs(argv) {
  const args = {
    baseUrl: "http://localhost:28000",
    employeeId: "100001",
    captureDir: DEFAULT_CAPTURE_DIR,
    manifestOut: DEFAULT_MANIFEST_OUT,
    traceId: "",
    runSmoke: false,
    strict: false,
    timeoutMs: 480000,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (item === "--employee-id") args.employeeId = argv[++index] || args.employeeId;
    else if (item === "--capture-dir") args.captureDir = argv[++index] || args.captureDir;
    else if (item === "--manifest-out") args.manifestOut = argv[++index] || args.manifestOut;
    else if (item === "--trace-id") args.traceId = argv[++index] || "";
    else if (item === "--run-smoke") args.runSmoke = true;
    else if (item === "--strict") args.strict = true;
    else if (item === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (item === "-h" || item === "--help") {
      console.log("Usage: node scripts/check_workflow_task_builder_tutorial.mjs [--base-url URL] [--employee-id ID] [--capture-dir DIR] [--manifest-out FILE] [--trace-id ID] [--run-smoke] [--strict]");
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
  ].filter(Boolean);
  const chrome = candidates.find((candidate) => existsSync(candidate));
  if (!chrome) throw new Error("Chrome/Chromium binary not found. Set CHROME_BIN.");
  return chrome;
}

function fetchJson(url, timeoutMs = 5000) {
  return new Promise((resolvePromise, reject) => {
    const req = get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => {
        try {
          resolvePromise(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(timeoutMs, () => req.destroy(new Error(`timeout fetching ${url}`)));
  });
}

async function freePort() {
  return new Promise((resolvePromise, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePromise(port));
    });
    server.on("error", reject);
  });
}

async function waitForJson(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      return await fetchJson(url, 3000);
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
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolvePromise, reject) => {
      this.ws.addEventListener("open", resolvePromise, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve: resolvePromise, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
      else resolvePromise(message.result || {});
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolvePromise, reject) => {
      this.pending.set(id, { resolve: resolvePromise, reject });
    });
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
      throw new Error(details.exception?.description || details.exception?.value || details.text || "Runtime.evaluate exception");
    }
    return result.result?.value;
  }

  async navigate(url) {
    await this.send("Page.navigate", { url });
    await waitUntil(this, "document.readyState === 'complete'", 30000);
  }

  async screenshot(path) {
    const result = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(path, Buffer.from(result.data, "base64"));
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
  throw new Error(`timed out waiting for expression: ${expression}; last=${JSON.stringify(lastValue)}`);
}

async function launchChrome() {
  const chrome = findChrome();
  const port = await freePort();
  const userDataDir = join(tmpdir(), `boi-workflow-task-builder-${Date.now()}`);
  const child = spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  await waitForJson(`http://127.0.0.1:${port}/json/version`, 15000);
  const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`, 15000);
  const pageTarget = Array.isArray(targets) ? targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl) : null;
  if (!pageTarget) throw new Error("Chrome page target not found");
  const cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return { child, cdp, userDataDir };
}

async function terminateChrome(runtime) {
  runtime.cdp?.close();
  const child = runtime.child;
  if (child && !child.killed) {
    child.kill("SIGTERM");
    await sleep(500);
    if (!child.killed) child.kill("SIGKILL");
  }
  if (runtime.userDataDir) rmSync(runtime.userDataDir, { recursive: true, force: true });
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function runSmokeIfRequested(args) {
  if (!args.runSmoke || args.traceId) return args.traceId;
  const smokeSeconds = Math.max(240, Math.floor(args.timeoutMs / 1000) - 30);
  const env = {
    ...process.env,
    BOI_API_URL: args.baseUrl,
    EMPLOYEE_ID: args.employeeId,
    POC_SMOKE_TIMEOUT_SECONDS: String(smokeSeconds),
  };
  const result = spawnSync("python", ["scripts/run_direct_development_sop_poc.py"], {
    cwd: ROOT,
    env,
    encoding: "utf8",
    timeout: args.timeoutMs,
  });
  if (result.status !== 0) {
    throw new Error(`direct development smoke failed\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`);
  }
  const match = result.stdout.match(/started trace_id=([^\s]+)/);
  if (!match) throw new Error(`could not parse trace_id from smoke output\n${result.stdout}`);
  return match[1];
}

async function setField(cdp, name, value) {
  await cdp.evaluate(`(() => {
    const field = document.querySelector(${JSON.stringify(`[name="${name}"]`)});
    if (!field) throw new Error(${JSON.stringify(`missing field ${name}`)});
    field.value = ${JSON.stringify(value)};
    field.dispatchEvent(new Event("input", {bubbles:true}));
    field.dispatchEvent(new Event("change", {bubbles:true}));
    return true;
  })()`);
}

async function click(cdp, selector) {
  await cdp.evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    if (!el) throw new Error(${JSON.stringify(`missing selector ${selector}`)});
    el.click();
    return true;
  })()`);
}

async function selectStep(cdp, step) {
  await click(cdp, `[data-registration-step="${step}"]`);
  await waitUntil(cdp, `!document.querySelector('[data-step-panel="${step}"]')?.hidden`, 10000);
  await sleep(250);
}

async function scrollStepIntoView(cdp, step) {
  await cdp.evaluate(`(() => {
    const panels = [...document.querySelectorAll(${JSON.stringify(`[data-step-panel="${step}"]`)})]
      .filter((panel) => !panel.hidden);
    const panel = panels.find((item) => item.closest("form")) || panels[0];
    if (!panel) return false;
    panel.scrollIntoView({block:"start", inline:"nearest"});
    window.scrollBy(0, -96);
    return true;
  })()`);
  await sleep(250);
}

async function scrollSelectorIntoView(cdp, selector) {
  await cdp.evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return false;
    el.scrollIntoView({block:"start", inline:"nearest"});
    window.scrollBy(0, -112);
    return true;
  })()`);
  await sleep(250);
}

async function setStageField(cdp, key, value) {
  await cdp.evaluate(`(() => {
    const field = document.querySelector(${JSON.stringify(`[data-stage-field="${key}"]`)});
    if (!field) throw new Error(${JSON.stringify(`missing stage field ${key}`)});
    field.value = ${JSON.stringify(value)};
    field.dispatchEvent(new Event("input", {bubbles:true}));
    field.dispatchEvent(new Event("change", {bubbles:true}));
    return true;
  })()`);
  await sleep(40);
}

async function fillSelectedTask(cdp, task) {
  await setStageField(cdp, "stage_name", task.name);
  await setStageField(cdp, "stage_goal", task.goal);
  await setStageField(cdp, "execution_mode", task.mode);
  await setStageField(cdp, "copilot_source", task.copilotSource || "unknown");
  await setStageField(cdp, "decision_question", task.question);
  await setStageField(cdp, "required_evidence", task.evidence);
  await setStageField(cdp, "expected_outputs", task.outputs);
  await setStageField(cdp, "knowledge_update_policy", task.knowledge);
  await setStageField(cdp, "tat_target", task.tatTarget);
  await setStageField(cdp, "baseline_tat", task.baselineTat);
  await setStageField(cdp, "measurement_policy", "event_action_timestamp");
  await setStageField(cdp, "fallback_owner", task.fallbackOwner);
}

async function fillTutorialScenario(cdp, args) {
  const baseUrl = args.baseUrl.replace(/\/$/, "");
  await cdp.navigate(`${baseUrl}/sops/new?employee_id=${encodeURIComponent(args.employeeId)}`);
  await waitUntil(cdp, "Boolean(document.querySelector('.registration-form'))", 15000);
  await cdp.evaluate("localStorage.clear()");
  await cdp.navigate(`${baseUrl}/sops/new?employee_id=${encodeURIComponent(args.employeeId)}`);
  await waitUntil(cdp, "Boolean(document.querySelector('.registration-form'))", 15000);

  await setField(cdp, "raw_request", "직개발 결과 확인부터 협의체 공유 전 승인까지 이어지는 Reporting Workflow를 만들고 싶다.");
  await setField(cdp, "title", "직개발 결과 확인 및 Reporting");
  await setField(cdp, "business_goal", "직개발 결과 확인, 단면검사 판단, 보고서 작성, 협의체 공유 전 승인 기록을 하나의 Workflow로 남긴다.");
  await setField(cdp, "work_target", "Product-A / Tech-A / Work ID 1.10");
  await setField(cdp, "work_situation", "직개발 결과가 발생하면 Response Trend와 Map View를 확인하고 단면검사 필요 여부를 판단한다.");
  await setField(cdp, "decision_question", "단면검사가 필요한가? 협의체 공유 전에 근거와 승인 상태가 충분한가?");
  await setField(cdp, "required_evidence_context", "Response Trend, Map View Image, 단면검사 결과, 연구소-양산 FAB 비교 Trend, Reporting 초안");
  await setField(cdp, "expected_result", "검증 보고서 BoI, 결정 기록, 협의체 공유 승인 기록");
  await setField(cdp, "knowledge_update_goal", "유사 직개발 Reporting 기준과 Task별 TAT 개선 후보로 남긴다.");

  await selectStep(cdp, "stages");
  const tasks = [
    {
      name: "Response Trend 확인",
      goal: "직개발 결과의 Response Trend 이상 여부를 확인한다.",
      mode: "autopilot",
      question: "Response Trend가 기준 범위 안에 있는가?",
      evidence: "Response Trend, Work ID, 측정 시각",
      outputs: "Trend 확인 BoI, Map View 요청 Event",
      knowledge: "Trend 이상 패턴을 유사 사례 후보로 남김",
      tatTarget: "30분",
      baselineTat: "평균 2h",
      fallbackOwner: "품질 시스템 담당자",
    },
    {
      name: "Map View 확인",
      goal: "Map View Image에서 패턴 이상 여부를 확인한다.",
      mode: "autopilot",
      question: "Map View 패턴이 단면검사 판단 근거로 충분한가?",
      evidence: "Map View Image, 불량 위치, 패턴 요약",
      outputs: "Map View 분석 BoI, 단면검사 판단 요청",
      knowledge: "반복 패턴을 Dictionary/유사 사례 후보로 남김",
      tatTarget: "30분",
      baselineTat: "평균 1h",
      fallbackOwner: "Map 분석 담당자",
    },
    {
      name: "단면검사 판단",
      goal: "Trend와 Map View 근거를 보고 단면검사 필요 여부를 사람이 결정한다.",
      mode: "manual",
      question: "단면검사를 의뢰해야 하는가?",
      evidence: "Response Trend, Map View Image, 담당자 판단 사유",
      outputs: "Manual decision record, 단면검사 의뢰 Event",
      knowledge: "판단 사유와 부족 근거를 개선 후보로 남김",
      tatTarget: "15분",
      baselineTat: "최근 3건 40분",
      fallbackOwner: "직개발 담당자",
    },
    {
      name: "단면검사 의뢰/결과 확인",
      goal: "단면검사 의뢰와 결과 확인을 연결한다.",
      mode: "copilot",
      copilotSource: "mixed",
      question: "단면검사 결과가 Reporting 판단에 충분한가?",
      evidence: "단면검사 의뢰, 결과 이미지, 담당자 메모",
      outputs: "단면검사 결과 BoI, FAB 비교 요청 Event",
      knowledge: "검사 결과 해석 기준을 업데이트 후보로 남김",
      tatTarget: "1일",
      baselineTat: "평균 2일",
      fallbackOwner: "단면검사 담당자",
    },
    {
      name: "연구소-양산 FAB 비교",
      goal: "연구소와 양산 FAB Trend 차이를 비교한다.",
      mode: "autopilot",
      question: "양산 FAB에서 같은 경향이 재현되는가?",
      evidence: "비교 Trend, Lot/Wafer mapping, FAB 조건",
      outputs: "FAB 비교 BoI, Reporting 요청 Event",
      knowledge: "비교 기준과 mapping 이슈를 후보로 남김",
      tatTarget: "1h",
      baselineTat: "평균 4h",
      fallbackOwner: "FAB 분석 담당자",
    },
    {
      name: "Reporting",
      goal: "근거와 판단을 보고서 초안으로 정리한다.",
      mode: "copilot",
      copilotSource: "internal",
      question: "보고서에 필요한 근거와 한계가 모두 포함됐는가?",
      evidence: "Trend, Map View, 단면검사 결과, FAB 비교 결과",
      outputs: "보고서 BoI, 협의체 공유 요청 Event",
      knowledge: "보고서 품질 기준과 누락 근거를 업데이트 후보로 남김",
      tatTarget: "1h",
      baselineTat: "평균 4h",
      fallbackOwner: "Reporting 담당자",
    },
    {
      name: "협의체 공유",
      goal: "공유 preview를 만들고 승인 후 공유한다.",
      mode: "copilot",
      copilotSource: "internal",
      question: "협의체 공유 전에 승인과 민감정보 확인이 끝났는가?",
      evidence: "Reporting 초안, 공유 대상, 승인 기록",
      outputs: "공유 preview, approval_required 기록",
      knowledge: "승인/공유 지연 원인을 TAT 개선 후보로 남김",
      tatTarget: "30분",
      baselineTat: "평균 2h",
      fallbackOwner: "협의체 공유 승인자",
    },
  ];
  for (let index = 0; index < tasks.length; index += 1) {
    if (index > 0) {
      await click(cdp, '[data-stage-action="add"]');
      await sleep(150);
    }
    await fillSelectedTask(cdp, tasks[index]);
  }
}

async function capture(cdp, captureDir, entries, id, file, title, url, purpose) {
  const path = join(captureDir, file);
  await cdp.screenshot(path);
  entries.push({
    id,
    file,
    title,
    url,
    purpose,
    sha256: sha256(path),
    viewport: `${VIEWPORT.width}x${VIEWPORT.height}`,
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const captureDir = resolve(ROOT, args.captureDir);
  mkdirSync(captureDir, { recursive: true });
  const traceId = runSmokeIfRequested(args);
  const runtime = await launchChrome();
  const entries = [];
  const baseUrl = args.baseUrl.replace(/\/$/, "");
  let hiddenChecks = {};
  try {
    await fillTutorialScenario(runtime.cdp, args);
    await selectStep(runtime.cdp, "context");
    await scrollStepIntoView(runtime.cdp, "context");
    await scrollSelectorIntoView(runtime.cdp, '[name="raw_request"]');
    await capture(runtime.cdp, captureDir, entries, "workflow_overview", "workflow-task-01-workflow-overview.png", "Workflow 개요", `${baseUrl}/sops/new?employee_id=${args.employeeId}`, "업무 맥락, 판단 질문, 필요한 근거, 남길 결과 입력");

    await selectStep(runtime.cdp, "stages");
    await scrollStepIntoView(runtime.cdp, "stages");
    await capture(runtime.cdp, captureDir, entries, "task_map", "workflow-task-02-task-map.png", "Task 맵", `${baseUrl}/sops/new?employee_id=${args.employeeId}`, "Workflow 전체 Task와 Manual/Copilot/Autopilot, TAT badge 확인");

    await runtime.cdp.evaluate(`(() => {
      const target = [...document.querySelectorAll("[data-stage-select]")].find((button) => button.textContent.includes("단면검사 판단"));
      if (!target) throw new Error("단면검사 판단 task card not found");
      target.click();
      return true;
    })()`);
    await sleep(300);
    await scrollStepIntoView(runtime.cdp, "stages");
    await capture(runtime.cdp, captureDir, entries, "task_detail", "workflow-task-03-task-detail.png", "Task 상세", `${baseUrl}/sops/new?employee_id=${args.employeeId}`, "선택한 Task의 실행 방식, 판단 질문, 필요한 근거, 산출물, TAT 설정");

    await selectStep(runtime.cdp, "entry");
    await runtime.cdp.evaluate(`(() => {
      const reuse = document.querySelector('[data-section-mode="event_mode"][data-mode-value="reuse"]');
      if (reuse) reuse.click();
      return true;
    })()`);
    await sleep(1200);
    await scrollStepIntoView(runtime.cdp, "entry");
    await capture(runtime.cdp, captureDir, entries, "start_signal", "workflow-task-04-start-signal.png", "시작/연결", `${baseUrl}/sops/new?employee_id=${args.employeeId}`, "기존 Event, Webhook/API/MCP/Kafka/수동 시작 방식 확인");

    await selectStep(runtime.cdp, "review");
    await scrollStepIntoView(runtime.cdp, "review");
    await capture(runtime.cdp, captureDir, entries, "review_save", "workflow-task-05-review-save.png", "검증·저장", `${baseUrl}/sops/new?employee_id=${args.employeeId}`, "운영 중 Data Lake 첨부 기준과 초안 저장/검증/게시 요청 흐름");

    hiddenChecks = await runtime.cdp.evaluate(`(() => {
      const parse = (name) => {
        const value = document.querySelector('[name="' + name + '"]')?.value || "";
        try { return JSON.parse(value); } catch { return null; }
      };
      const tasks = parse("workflow_tasks");
      const model = parse("workflow_model");
      return {
        workflowTasksLength: Array.isArray(tasks) ? tasks.length : 0,
        workflowTitle: model?.title || "",
        hasManual: Array.isArray(tasks) && tasks.some((task) => task.execution_mode === "manual"),
        hasCopilot: Array.isArray(tasks) && tasks.some((task) => task.execution_mode === "copilot"),
        hasAutopilot: Array.isArray(tasks) && tasks.some((task) => task.execution_mode === "autopilot"),
      };
    })()`);

    await runtime.cdp.navigate(`${baseUrl}/docs/boi:public:sop:direct-development-reporting?employee_id=${args.employeeId}`);
    await waitUntil(runtime.cdp, "document.body.textContent.includes('직개발 결과 확인 및 Reporting SOP')", 30000);
    await capture(runtime.cdp, captureDir, entries, "saved_sop", "workflow-task-06-saved-sop.png", "저장된 SOP 문서", `${baseUrl}/docs/boi:public:sop:direct-development-reporting?employee_id=${args.employeeId}`, "튜토리얼의 기준 public SOP 문서와 원본 이미지/Workflow 표");

    if (traceId) {
      const statusUrl = `${baseUrl}/workflows/direct-development-reporting/status?employee_id=${args.employeeId}&trace_id=${encodeURIComponent(traceId)}`;
      await runtime.cdp.navigate(statusUrl);
      await waitUntil(runtime.cdp, "document.body.textContent.includes('Workflow') || document.body.textContent.includes('직개발')", 30000);
      await capture(runtime.cdp, captureDir, entries, "runtime_status", "workflow-task-07-runtime-status.png", "실행 status", statusUrl, "direct-development workflow smoke 실행 결과와 simulated/manual/approval 단계");
    }

    const tatUrl = `${baseUrl}/workflows/direct-development-reporting/tat?employee_id=${args.employeeId}`;
    await runtime.cdp.navigate(tatUrl);
    await waitUntil(runtime.cdp, "document.body.textContent.includes('TAT SCORECARD') && document.body.textContent.includes('Task별 TAT 비교')", 30000);
    await capture(runtime.cdp, captureDir, entries, "tat_summary", "workflow-task-08-tat-summary.png", "TAT summary", tatUrl, "Workflow/Task TAT 성과 scorecard와 병목/개선/guardrail 확인");

    const report = {
      ok: entries.length >= (traceId ? 8 : 7)
        && hiddenChecks.workflowTasksLength >= 7
        && hiddenChecks.hasManual
        && hiddenChecks.hasCopilot
        && hiddenChecks.hasAutopilot,
      generated_at: new Date().toISOString(),
      base_url: baseUrl,
      employee_id: args.employeeId,
      trace_id: traceId,
      capture_dir: relative(ROOT, captureDir),
      viewport: `${VIEWPORT.width}x${VIEWPORT.height}`,
      hidden_checks: hiddenChecks,
      required: entries,
    };
    const manifestOut = resolve(ROOT, args.manifestOut);
    mkdirSync(resolve(manifestOut, ".."), { recursive: true });
    writeFileSync(manifestOut, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !report.ok) process.exitCode = 1;
  } finally {
    await terminateChrome(runtime);
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
