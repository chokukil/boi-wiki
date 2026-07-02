#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function parseArgs(argv) {
  const args = {
    url: "http://localhost:28000/inbox?employee_id=100001",
    timeoutMs: 30000,
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
      console.log("Usage: node scripts/check_boi_inbox_ui.mjs [--url URL] [--timeout-ms MS] [--screenshot FILE] [--strict]");
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
  if (!chrome) throw new Error("Chrome/Chromium binary not found. Set CHROME_BIN to run BoI Inbox UI smoke.");
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

  async screenshot(path) {
    const result = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    if (path && result.data) writeFileSync(path, Buffer.from(result.data, "base64"));
    return result.data || "";
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
  const exited = new Promise((resolve) => child.once("exit", resolve));
  child.kill("SIGTERM");
  await Promise.race([exited, sleep(2000)]);
  if (!child.killed) {
    child.kill("SIGKILL");
    await Promise.race([exited, sleep(1000)]);
  }
}

function checkReport(snapshot, consoleErrors, apiManifest) {
  const expectedNav = ["BoI Wiki", "BoI Inbox", "SOP", "Event Broker", "Action", "Advanced"];
  const expectedSubnav = ["BoI Operations Center", "받은 보고서", "승인/조치", "처리 이력"];
  const checks = {
    page_loaded: snapshot.readyState === "complete" && snapshot.hasInboxPage,
    primary_nav_order: JSON.stringify(snapshot.primaryNavLabels) === JSON.stringify(expectedNav),
    boi_inbox_active: snapshot.activeNavLabel === "BoI Inbox" && ["inbox", "boi_inbox"].includes(snapshot.activeNavId),
    subnav_order: JSON.stringify(snapshot.subnavLabels) === JSON.stringify(expectedSubnav),
    section_intro_matches: snapshot.introTitle === "받은 보고서" && /검증된 보고서 BoI/.test(snapshot.introDescription || ""),
    no_header_actions: !snapshot.hasPagePrimaryActions && !snapshot.hasUtilityNav,
    summary_cards_present: snapshot.summaryCardCount >= 3,
    inbox_content_present: snapshot.inboxCardCount > 0 || snapshot.emptyStatePresent,
    report_state_visible: snapshot.reportLinkCount > 0 || snapshot.reportPendingCount > 0 || snapshot.emptyStatePresent,
    no_group_report_cta: !snapshot.groupReportCtaVisible,
    no_internal_terms_visible: snapshot.forbiddenVisibleTerms.length === 0,
    agent_has_no_inbox_tab: snapshot.agentPanelOpen && !snapshot.agentHasInboxTab && !snapshot.agentHasLegacyInboxText,
    decisions_subnav_works: snapshot.decisionsTitle === "승인/조치",
    history_subnav_works: snapshot.historyTitle === "처리 이력",
    api_manifest_background: apiManifest?.ok === true && apiManifest?.canonical === true && apiManifest?.context_mode === "background",
    api_report_manifest_present: Array.isArray(apiManifest?.items)
      && typeof apiManifest?.report_warmup_scheduled === "number"
      && (apiManifest.items.length === 0 || apiManifest.items.every((item) => item.report_id && item.report_state && item.report_boi_link)),
    api_groups_are_rollups_only: Array.isArray(apiManifest?.groups)
      && apiManifest.groups.every((group) => group.rollup_only === true
        && group.report_scope === "item"
        && !("report_state" in group)
        && !("report_boi_url" in group)
        && !("report_boi_link" in group)),
    console_clean: relevantConsoleErrors(consoleErrors).length === 0,
  };
  return { ok: Object.values(checks).every(Boolean), checks };
}

function checkOpsReport(snapshot, consoleErrors, apiManifest) {
  const expectedNav = ["BoI Wiki", "BoI Inbox", "SOP", "Event Broker", "Action", "Advanced"];
  const expectedSubnav = ["BoI Operations Center", "받은 보고서", "승인/조치", "처리 이력"];
  const checks = {
    page_loaded: snapshot.readyState === "complete" && snapshot.hasOpsPage,
    primary_nav_order: JSON.stringify(snapshot.primaryNavLabels) === JSON.stringify(expectedNav),
    boi_inbox_active: snapshot.activeNavLabel === "BoI Inbox" && ["inbox", "boi_inbox"].includes(snapshot.activeNavId),
    subnav_order: JSON.stringify(snapshot.subnavLabels) === JSON.stringify(expectedSubnav),
    section_intro_matches: snapshot.introTitle === "BoI Operations Center" && /SOP/.test(snapshot.introDescription || ""),
    no_header_actions: !snapshot.hasPagePrimaryActions && !snapshot.hasUtilityNav,
    summary_cards_present: snapshot.summaryCardCount >= 4,
    modebar_present: snapshot.opsModeCount >= 3,
    workstream_map_present: snapshot.opsSopNodeCount > 0 || snapshot.emptyStatePresent,
    workstream_weight_present: snapshot.opsWeightedNodeCount > 0 || snapshot.emptyStatePresent,
    workstream_edge_badges_present: snapshot.opsEdgeCount > 0 && snapshot.opsEdgeBadgeCount > 0 || snapshot.emptyStatePresent,
    queue_present: snapshot.opsQueueCount > 0 || snapshot.emptyStatePresent,
    decision_panel_present: snapshot.opsDecisionPanelPresent,
    run_selection_updates_drawer: snapshot.emptyStatePresent || snapshot.opsRunClickProof?.clicked === true,
    decision_tab_exposes_actions: snapshot.emptyStatePresent || snapshot.opsDecisionTabProof?.clicked === true,
    evidence_tab_exposes_workspace: snapshot.opsEvidenceTabProof?.clicked === true,
    source_backed_sandbox_nodes_optional: snapshot.opsSandboxNodeCount >= 0 && snapshot.opsEvidenceNodeCount >= 0,
    sandbox_drawer_present: snapshot.opsSandboxDrawerOpen,
    sandbox_jobs_or_empty_state_present: snapshot.opsSandboxJobCount > 0 || snapshot.opsSandboxEmptyVisible,
    sandbox_artifacts_visible_when_jobs_exist: snapshot.opsSandboxJobCount === 0 || snapshot.opsSandboxArtifactLinkCount > 0 || snapshot.opsSandboxSummaryVisible,
    sandbox_actions_work_when_jobs_exist: snapshot.opsSandboxJobCount === 0 || /보고서 .*연결했습니다/.test(snapshot.opsSandboxActionStatus || ""),
    ops_nodes_do_not_overlap: snapshot.emptyStatePresent || snapshot.opsNodeOverlapCount === 0,
    ops_edge_labels_do_not_cover_nodes: snapshot.emptyStatePresent || snapshot.opsLargeEdgeLabelOverlapCount === 0,
    ops_sop_node_density_reduced: snapshot.emptyStatePresent || snapshot.opsSopNodePreviewMax <= 1,
    agent_has_no_inbox_tab: !snapshot.agentHasInboxTab && !snapshot.agentHasLegacyInboxText,
    api_ops_manifest_present: apiManifest?.ok === true
      && Array.isArray(apiManifest?.workstream_nodes)
      && Array.isArray(apiManifest?.priority_queue)
      && apiManifest?.summary
      && typeof apiManifest.summary.open_count === "number",
    api_ops_visual_model_present: Array.isArray(apiManifest?.workstream_nodes)
      && Array.isArray(apiManifest?.workstream_edges)
      && apiManifest.workstream_nodes.filter((node) => node.type === "sop_workstream").every((node) => node.size_class && node.visual_state)
      && (apiManifest.workstream_edges.length > 0 || apiManifest.summary?.open_count === 0),
    console_clean: relevantConsoleErrors(consoleErrors).length === 0,
  };
  return { ok: Object.values(checks).every(Boolean), checks };
}

function relevantConsoleErrors(consoleErrors) {
  return consoleErrors.filter((message) => {
    const text = String(message || "");
    if (/favicon\.ico/i.test(text)) return false;
    if (/Failed to load resource: the server responded with a status of 404/i.test(text)) return false;
    return true;
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const isOps = new URL(args.url).pathname === "/ops";
  const pageSelector = isOps ? ".ops-page" : ".boi-inbox-page";
  const chrome = findChrome();
  const profileDir = mkdtempSync(join(tmpdir(), "boi-inbox-chrome-"));
  const port = 9433 + Math.floor(Math.random() * 1000);
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
  const consoleErrors = [];
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
    cdp.on("Log.entryAdded", (params) => {
      const entry = params.entry || {};
      if (entry.level === "error") consoleErrors.push(entry.text || "console error");
    });

    const loaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: args.url });
    await loaded;
    await waitUntil(cdp, `document.readyState === "complete" && !!document.querySelector(${JSON.stringify(pageSelector)})`, args.timeoutMs);

    if (!isOps) {
      await waitUntil(cdp, `!!document.querySelector("#boi-agent-root .boi-agent-launcher")`, args.timeoutMs);
      await cdp.evaluate(`(() => {
        const panel = document.querySelector("#boi-agent-root .boi-agent-panel.open");
        if (!panel) document.querySelector("#boi-agent-root .boi-agent-launcher")?.click();
        return true;
      })()`);
      await waitUntil(cdp, `!!document.querySelector("#boi-agent-root .boi-agent-panel.open")`, args.timeoutMs);
    }
    if (isOps) {
      await waitUntil(
        cdp,
        `!!document.querySelector(".ops-center-shell") && (document.querySelectorAll(".ops-workstream-node").length > 0 || document.querySelectorAll(".ops-focus-item").length > 0)`,
        args.timeoutMs
      );
    }

    const decisionsHref = isOps ? "" : await cdp.evaluate(`document.querySelector('.section-subnav-link[href*="view=decisions"]')?.href || ""`);
    if (decisionsHref) {
      const decisionsLoaded = cdp.once("Page.loadEventFired");
      await cdp.send("Page.navigate", { url: decisionsHref });
      await decisionsLoaded;
      await waitUntil(cdp, `document.querySelector(".section-intro-panel h2")?.textContent.trim() === "승인/조치"`, args.timeoutMs);
    }
    const decisionsTitle = await cdp.evaluate(`document.querySelector(".section-intro-panel h2")?.textContent.trim() || ""`);

    const historyHref = isOps ? "" : await cdp.evaluate(`document.querySelector('.section-subnav-link[href*="view=history"]')?.href || ""`);
    if (historyHref) {
      const historyLoaded = cdp.once("Page.loadEventFired");
      await cdp.send("Page.navigate", { url: historyHref });
      await historyLoaded;
      await waitUntil(cdp, `document.querySelector(".section-intro-panel h2")?.textContent.trim() === "처리 이력"`, args.timeoutMs);
    }
    const historyTitle = await cdp.evaluate(`document.querySelector(".section-intro-panel h2")?.textContent.trim() || ""`);

    const reportsLoaded = cdp.once("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: args.url });
    await reportsLoaded;
    await waitUntil(cdp, `document.readyState === "complete" && !!document.querySelector(${JSON.stringify(pageSelector)})`, args.timeoutMs);
    if (!isOps) {
      await waitUntil(cdp, `!!document.querySelector("#boi-agent-root .boi-agent-launcher")`, args.timeoutMs);
      await cdp.evaluate(`(() => {
        const panel = document.querySelector("#boi-agent-root .boi-agent-panel.open");
        if (!panel) document.querySelector("#boi-agent-root .boi-agent-launcher")?.click();
        return true;
      })()`);
      await waitUntil(cdp, `!!document.querySelector("#boi-agent-root .boi-agent-panel.open")`, args.timeoutMs);
    }
    let opsRunClickProof = { clicked: false, reason: isOps ? "not_checked" : "not_ops" };
    let opsDecisionTabProof = { clicked: false, reason: isOps ? "not_checked" : "not_ops" };
    let opsEvidenceTabProof = { clicked: false, reason: isOps ? "not_checked" : "not_ops" };
    if (isOps) {
      await waitUntil(
        cdp,
        `!!document.querySelector(".ops-center-shell") && (document.querySelectorAll(".ops-workstream-node").length > 0 || document.querySelectorAll(".ops-focus-item").length > 0)`,
        args.timeoutMs
      );
      opsRunClickProof = await cdp.evaluate(`(() => {
        const item = document.querySelector(".ops-focus-item");
        if (!item) return { clicked: false, reason: "empty_queue" };
        const label = item.innerText || "";
        item.click();
        return { clicked: true, label };
      })()`);
      if (opsRunClickProof.clicked) {
        await waitUntil(
          cdp,
          `(() => {
            const text = document.querySelector(".ops-context-drawer")?.innerText || "";
            return /현재 단계/.test(text) && /왜 나에게 왔나/.test(text) && /업무 맥락/.test(text) && /의사결정 흐름/.test(text);
          })()`,
          args.timeoutMs
        );
      }
      opsDecisionTabProof = await cdp.evaluate(`(() => {
        const button = Array.from(document.querySelectorAll(".ops-drawer-tabs button"))
          .find((item) => (item.textContent || "").trim() === "판단");
        if (!button) return { clicked: false, reason: "decision_tab_missing" };
        button.click();
        const text = document.querySelector(".ops-context-drawer")?.innerText || "";
        return { clicked: true, hasDecisionButtons: /승인/.test(text) && /반려/.test(text) && /추가 근거 요청/.test(text) };
      })()`);
      await waitUntil(
        cdp,
        `(() => {
          const text = document.querySelector(".ops-context-drawer")?.innerText || "";
          return /의사결정 흐름/.test(text) && /보고서 보기/.test(text) && /승인/.test(text) && /반려/.test(text) && /보류/.test(text);
        })()`,
        args.timeoutMs
      );
      opsEvidenceTabProof = await cdp.evaluate(`(() => {
        const button = Array.from(document.querySelectorAll(".ops-drawer-tabs button"))
          .find((item) => (item.textContent || "").trim() === "근거");
        if (!button) return { clicked: false, reason: "evidence_tab_missing" };
        button.click();
        const text = document.querySelector(".ops-context-drawer")?.innerText || "";
        return { clicked: true, hasWorkspace: /Computational Evidence Workspace/.test(text) };
      })()`);
      await waitUntil(
        cdp,
        `/Computational Evidence Workspace/.test(document.querySelector(".ops-context-drawer")?.innerText || "")`,
        args.timeoutMs
      );
      await cdp.evaluate(`(() => {
        const node = document.querySelector(".ops-sandboxJobNode-node, .ops-evidenceNode-node");
        if (node) node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
        return !!node;
      })()`);
      await waitUntil(
        cdp,
        `(() => {
          const drawer = document.querySelector(".ops-context-drawer");
          if (!drawer) return false;
          const text = drawer.innerText || "";
          return /Computational Evidence Workspace|최근 Sandbox 결과/.test(text) && !/Sandbox 결과를 불러오는 중입니다/.test(text);
        })()`,
        args.timeoutMs
      );
      const sandboxJobCount = await cdp.evaluate(`document.querySelectorAll("[data-sandbox-job-id]").length`);
      if (sandboxJobCount > 0) {
        await cdp.evaluate(`document.querySelector("[data-sandbox-adopt]")?.click()`);
        await waitUntil(
          cdp,
          `/검증 근거로 채택했습니다|근거 채택 실패/.test(document.querySelector(".ops-context-drawer")?.innerText || "")`,
          args.timeoutMs
        );
        await cdp.evaluate(`document.querySelector("[data-sandbox-attach]")?.click()`);
        await waitUntil(
          cdp,
          `/보고서 .*연결했습니다|보고서 반영 실패/.test(document.querySelector(".ops-context-drawer")?.innerText || "")`,
          args.timeoutMs
        );
      }
    }

    const snapshot = await cdp.evaluate(`(() => {
      const text = document.body.innerText || "";
      const agentText = document.querySelector("#boi-agent-root")?.innerText || "";
      const forbiddenPatterns = [/source_id/i, /WorkflowDefinition/, /schema dump/i, /trace-[a-z0-9-]+/i, /act-[0-9a-z-]{8,}/i];
      return {
        readyState: document.readyState,
        url: location.href,
        title: document.title,
        hasInboxPage: !!document.querySelector(".boi-inbox-page"),
        hasOpsPage: !!document.querySelector(".ops-page"),
        primaryNavLabels: Array.from(document.querySelectorAll(".primary-nav .global-nav-link")).map((item) => item.textContent.trim()).filter(Boolean),
        activeNavId: document.querySelector(".primary-nav .global-nav-link.active")?.dataset.navId || "",
        activeNavLabel: document.querySelector(".primary-nav .global-nav-link.active")?.textContent.trim() || "",
        subnavLabels: Array.from(document.querySelectorAll(".section-subnav .section-subnav-link")).map((item) => item.textContent.trim()).filter(Boolean),
        introTitle: document.querySelector(".section-intro-panel h2")?.textContent.trim() || "",
        introDescription: document.querySelector(".section-intro-panel p:not(.eyebrow)")?.textContent.trim() || "",
        hasPagePrimaryActions: !!document.querySelector(".page-primary-actions"),
        hasUtilityNav: !!document.querySelector(".utility-nav"),
        summaryCardCount: document.querySelectorAll(".status-summary-card, .ops-center-metrics strong").length,
        opsModeCount: document.querySelectorAll(".ops-flow-panel-toolbar button").length,
        opsSopNodeCount: document.querySelectorAll(".ops-workstream-node").length,
        opsWeightedNodeCount: document.querySelectorAll(".ops-workstream-node.risk-high, .ops-workstream-node.risk-medium, .ops-workstream-node.risk-normal").length,
        opsEdgeCount: document.querySelectorAll(".react-flow__edge").length,
        opsEdgeBadgeCount: document.querySelectorAll(".ops-rf-edge-label, .react-flow__edge-text").length,
        opsQueueCount: document.querySelectorAll(".ops-focus-item").length,
        opsDecisionPanelPresent: !!document.querySelector(".ops-context-drawer"),
        opsEvidenceNodeCount: document.querySelectorAll(".ops-evidenceNode-node").length,
        opsSandboxNodeCount: document.querySelectorAll(".ops-sandboxJobNode-node").length,
        opsSandboxDrawerOpen: /Computational Evidence Workspace/.test(document.querySelector(".ops-context-drawer")?.innerText || ""),
        opsSandboxJobCount: document.querySelectorAll("[data-sandbox-job-id]").length,
        opsSandboxArtifactLinkCount: document.querySelectorAll(".ops-sandbox-artifacts a").length,
        opsSandboxSummaryVisible: /GPT-5\\.5 검증 요약/.test(document.querySelector(".ops-context-drawer")?.innerText || ""),
        opsSandboxEmptyVisible: /Sandbox 실행 결과가 없습니다/.test(document.querySelector(".ops-context-drawer")?.innerText || ""),
        opsSandboxActionStatus: document.querySelector(".ops-sandbox-action-status")?.textContent?.trim() || "",
        opsNodeOverlapCount: (() => {
          const rects = Array.from(document.querySelectorAll(".react-flow__node"))
            .map((node) => {
              const rect = node.getBoundingClientRect();
              return { id: node.getAttribute("data-id") || node.className || "", left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
            })
            .filter((rect) => rect.width > 8 && rect.height > 8);
          let overlaps = 0;
          for (let left = 0; left < rects.length; left += 1) {
            for (let right = left + 1; right < rects.length; right += 1) {
              const a = rects[left];
              const b = rects[right];
              const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
              const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
              if (x * y > 24) overlaps += 1;
            }
          }
          return overlaps;
        })(),
        opsLargeEdgeLabelOverlapCount: (() => {
          const nodeRects = Array.from(document.querySelectorAll(".react-flow__node"))
            .map((node) => node.getBoundingClientRect())
            .filter((rect) => rect.width > 8 && rect.height > 8);
          const labelRects = Array.from(document.querySelectorAll(".ops-rf-edge-label:not(.dot-only), .react-flow__edge-text"))
            .map((label) => label.getBoundingClientRect())
            .filter((rect) => rect.width > 18 && rect.height > 12);
          let overlaps = 0;
          for (const label of labelRects) {
            for (const node of nodeRects) {
              const x = Math.max(0, Math.min(label.right, node.right) - Math.max(label.left, node.left));
              const y = Math.max(0, Math.min(label.bottom, node.bottom) - Math.max(label.top, node.top));
              if (x * y > 20) overlaps += 1;
            }
          }
          return overlaps;
        })(),
        opsSopNodePreviewMax: Math.max(0, ...Array.from(document.querySelectorAll(".ops-workstream-node")).map((node) => node.querySelectorAll("[data-run-preview]").length)),
        opsRunClickProof: ${JSON.stringify(opsRunClickProof)},
        opsDecisionTabProof: ${JSON.stringify(opsDecisionTabProof)},
        opsEvidenceTabProof: ${JSON.stringify(opsEvidenceTabProof)},
        opsRunDrawerHadCoreSections: ${JSON.stringify(Boolean(opsRunClickProof.clicked))},
        inboxCardCount: document.querySelectorAll(".boi-inbox-list .boi-inbox-card").length,
        emptyStatePresent: !!document.querySelector(".empty-state"),
        reportLinkCount: Array.from(document.querySelectorAll("a")).filter((item) => /보고서 BoI/.test(item.textContent || "")).length,
        reportPendingCount: Array.from(document.querySelectorAll(".badge")).filter((item) => /보고서/.test(item.textContent || "")).length,
        groupReportCtaVisible: /묶음 보고서/.test(text),
        forbiddenVisibleTerms: forbiddenPatterns.map((pattern) => pattern.source).filter((_source, index) => forbiddenPatterns[index].test(text)),
        agentPanelOpen: !!document.querySelector("#boi-agent-root .boi-agent-panel.open"),
        agentHasInboxTab: !!document.querySelector("#boi-agent-root [role='tab'], #boi-agent-root .boi-agent-tabs"),
        agentHasLegacyInboxText: Array.from(document.querySelectorAll("#boi-agent-root button, #boi-agent-root a"))
          .some((item) => ["Inbox", "BoI Inbox", "받은 보고서", "승인/조치"].includes((item.textContent || "").trim())),
        decisionsTitle: ${JSON.stringify(decisionsTitle)},
        historyTitle: ${JSON.stringify(historyTitle)}
      };
    })()`);

    const employeeId = new URL(args.url).searchParams.get("employee_id") || "100001";
    const apiUrl = new URL(isOps ? "/api/ops/overview" : "/api/inbox", args.url);
    apiUrl.searchParams.set("employee_id", employeeId);
    if (!isOps) apiUrl.searchParams.set("limit", "5");
    const apiManifest = await waitForJson(apiUrl.toString(), args.timeoutMs);

    if (args.screenshot) await cdp.screenshot(args.screenshot);
    const report = {
      ...(isOps ? checkOpsReport(snapshot, consoleErrors, apiManifest) : checkReport(snapshot, consoleErrors, apiManifest)),
      url: args.url,
      browser: "Chrome DevTools Protocol",
      snapshot,
      apiManifest: {
        ok: apiManifest?.ok,
        canonical: apiManifest?.canonical,
        context_mode: apiManifest?.context_mode,
        employee_id: apiManifest?.employee_id,
        open_count: apiManifest?.summary?.open_count,
        workstream_count: apiManifest?.workstream_nodes?.length,
        priority_count: apiManifest?.priority_queue?.length,
        sandbox_node_count: snapshot.opsSandboxNodeCount,
        sandbox_job_count: snapshot.opsSandboxJobCount,
        sandbox_artifact_link_count: snapshot.opsSandboxArtifactLinkCount,
        sandbox_action_status: snapshot.opsSandboxActionStatus,
        count: apiManifest?.count,
        group_count: apiManifest?.group_count,
        report_count: apiManifest?.report_count,
        report_warmup_scheduled: apiManifest?.report_warmup_scheduled,
      },
      consoleErrors: relevantConsoleErrors(consoleErrors),
      ignoredConsoleErrors: consoleErrors.filter((message) => !relevantConsoleErrors([message]).length),
      screenshot: args.screenshot,
    };
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !report.ok) process.exitCode = 1;
  } catch (error) {
    console.log(JSON.stringify({ ok: false, error: error.message, consoleErrors }, null, 2));
    process.exitCode = 1;
  } finally {
    cdp?.close();
    await terminateChrome(child);
    rmSync(profileDir, { recursive: true, force: true });
  }
}

main();
