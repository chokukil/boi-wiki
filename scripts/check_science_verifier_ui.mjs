#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { basename, dirname, join, relative } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

function parseArgs(argv) {
  const args = {
    url: "http://localhost:28000/science-verifier?employee_id=100001",
    timeoutMs: 60000,
    screenshot: "",
    mobileScreenshot: "",
    reportJson: "",
    gitCommit: "",
    strict: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--url") args.url = argv[++index] || args.url;
    else if (item === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (item === "--screenshot") args.screenshot = argv[++index] || "";
    else if (item === "--mobile-screenshot") args.mobileScreenshot = argv[++index] || "";
    else if (item === "--report-json") args.reportJson = argv[++index] || "";
    else if (item === "--git-commit") args.gitCommit = argv[++index] || "";
    else if (item === "--strict") args.strict = true;
    else if (item === "-h" || item === "--help") {
      console.log("Usage: node scripts/check_science_verifier_ui.mjs [--url URL] [--timeout-ms MS] [--screenshot FILE] [--mobile-screenshot FILE] [--report-json FILE] [--git-commit SHA] [--strict]");
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
  if (!chrome) throw new Error("Chrome/Chromium binary not found. Set CHROME_BIN to verify Science Verifier UI.");
  return chrome;
}

function fetchJson(url, timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const request = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`timeout fetching ${url}`)));
  });
}

async function waitForJson(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try { return await fetchJson(url, 5000); } catch (error) { lastError = error; }
    await sleep(150);
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

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Runtime.evaluate exception");
    }
    return result.result?.value;
  }

  async screenshot(path) {
    const result = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: true });
    if (path && result.data) writeFileSync(path, Buffer.from(result.data, "base64"));
  }

  close() { this.ws?.close(); }
}

async function waitUntil(cdp, expression, timeoutMs, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await cdp.evaluate(expression);
    if (lastValue) return lastValue;
    await sleep(intervalMs);
  }
  throw new Error(`timed out waiting for ${expression}; last=${JSON.stringify(lastValue)}`);
}

async function terminateChrome(child) {
  if (!child || child.killed) return;
  const exited = new Promise((resolve) => child.once("exit", resolve));
  child.kill("SIGTERM");
  await Promise.race([exited, sleep(2000)]);
  if (!child.killed) child.kill("SIGKILL");
}

function relevantConsoleErrors(errors) {
  return errors.filter((item) => !/favicon\.ico|404 \(Not Found\)/i.test(item));
}

async function main() {
  const args = parseArgs(process.argv);
  const chrome = findChrome();
  const profileDir = mkdtempSync(join(tmpdir(), "science-verifier-chrome-"));
  const port = 9400 + Math.floor(Math.random() * 500);
  const child = spawn(chrome, [
    "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`,
    "--window-size=1440,1100", "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const consoleErrors = [];
  const scienceRequests = [];
  let cdp;
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`, 10000);
    const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`, 5000);
    const target = targets.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    if (!target) throw new Error("Chrome page target not found");
    cdp = new CdpClient(target.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable");
    cdp.on("Runtime.exceptionThrown", (params) => consoleErrors.push(params.exceptionDetails?.exception?.description || params.exceptionDetails?.text || "Runtime exception"));
    cdp.on("Runtime.consoleAPICalled", (params) => {
      if (["error", "warning"].includes(params.type)) consoleErrors.push((params.args || []).map((arg) => arg.value || arg.description || "").join(" "));
    });
    cdp.on("Log.entryAdded", (params) => {
      if (["error", "warning"].includes(params.entry?.level)) consoleErrors.push(params.entry?.text || "");
    });
    cdp.on("Network.requestWillBeSent", (params) => {
      const url = params.request?.url || "";
      if (url.includes("/api/science/")) scienceRequests.push({ url, method: params.request?.method || "" });
    });

    await cdp.send("Page.navigate", { url: args.url });
    await waitUntil(cdp, "document.readyState === 'complete' && !!document.querySelector('[data-science-review-canvas]')", args.timeoutMs);
    await cdp.evaluate(`
      (() => {
        const input = document.querySelector('[name="document"]');
        input.value = 'Photo Track에서 Spin Coating 두께를 높이려면 final spin RPM을 높여야 한다.';
        input.setSelectionRange(0, input.value.length);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        document.querySelector('[data-science-alias-detect]').click();
      })()
    `);
    await waitUntil(cdp, "!document.querySelector('[data-science-candidate-editor]').hidden && document.querySelectorAll('.science-alias-chip').length >= 3", args.timeoutMs);
    const desktop = await cdp.evaluate(`
      (() => {
        const root = document.querySelector('[data-science-review-canvas]');
        const nav = [...document.querySelectorAll('[data-nav-id]')].map((node) => node.dataset.navId);
        const text = document.body.innerText;
        const local = document.querySelector('[data-science-candidate-editor] [data-science-local-edit]');
        local?.focus();
        return {
          nav,
          releaseStatus: root?.dataset.releaseStatus,
          operational: root?.dataset.operational,
          redCount: document.querySelectorAll('.science-violation').length,
          purpleCount: document.querySelectorAll('.science-ambiguity').length,
          aliasCount: document.querySelectorAll('.science-alias-match').length,
          aliasChipCount: document.querySelectorAll('.science-alias-chip').length,
          candidateEditorVisible: !document.querySelector('[data-science-candidate-editor]').hidden,
          roleSelects: document.querySelectorAll('[name="subject_match"], [name="relation_match"], [name="object_match"]').length,
          qwenExperimental: !!document.querySelector('[data-science-qwen-experimental]'),
          candidateBoundary: text.includes('운영 판정이 아닙니다'),
          noLlmBoundary: text.includes('Qwen 없이도 검토와 검증을 완료할 수 있습니다'),
          noScore: !text.includes('종합점수'),
          noDoe: !text.includes('DOE'),
          distinctActions: !!document.querySelector('[data-science-local-edit]') && !!document.querySelector('[data-science-proposal]'),
          focusVisibleTarget: !local || document.activeElement === local,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        };
      })()
    `);
    if (args.screenshot) await cdp.screenshot(args.screenshot);

    await cdp.evaluate(`
      (() => {
        const choose = (name, exact) => {
          const select = document.querySelector('[name="' + name + '"]');
          const option = [...select.options].find((item) => item.textContent.startsWith(exact + ' — '));
          if (!option) throw new Error('missing role option: ' + name + '=' + exact);
          select.value = option.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
        };
        choose('subject_match', 'RPM');
        choose('relation_match', '높여야 한다');
        choose('object_match', '두께');
        document.querySelector('[name="process_stage"]').value = 'final_coat_spin';
        document.querySelector('[name="material_state"]').value = 'liquid_film';
        document.querySelector('[data-science-candidate-form]').requestSubmit();
      })()
    `);
    await waitUntil(cdp, "document.querySelector('[data-science-status]')?.textContent.includes('활성 Science Release가 없어 판정을 실행하지 않았습니다')", args.timeoutMs);
    const manualRoute = await cdp.evaluate(`
      (() => ({
        status: document.querySelector('[data-science-status]')?.textContent || '',
        redCount: document.querySelectorAll('.science-violation').length,
        cards: document.querySelectorAll('[data-science-live-claims] .science-correction-card').length,
        leakedConfirmationCode: document.body.innerText.includes('USER_CONFIRMATION_REQUIRED'),
      }))()
    `);
    const defaultNonQwenPath = scienceRequests.some((item) => new URL(item.url).pathname === "/api/science/aliases/detect")
      && !scienceRequests.some((item) => new URL(item.url).pathname === "/api/science/interpret")
      && !scienceRequests.some((item) => new URL(item.url).pathname === "/api/science/verify-document");

    const failureMatrix = await cdp.evaluate(`
      (async () => {
        const originalFetch = window.fetch.bind(window);
        const status = () => document.querySelector('[data-science-status]')?.textContent || '';
        const redCount = () => document.querySelectorAll('.science-violation').length;
        const waitFor = async (predicate, timeout = 4000) => {
          const deadline = Date.now() + timeout;
          while (Date.now() < deadline) {
            if (predicate()) return true;
            await new Promise((resolve) => setTimeout(resolve, 25));
          }
          return false;
        };
        const failureResponse = (diagnostic) => new Response(
          JSON.stringify({ detail: { code: 'science_interpretation_unavailable', diagnostic_code: diagnostic } }),
          { status: 503, headers: { 'content-type': 'application/json' } },
        );
        const qwenCases = {
          connection_unavailable: () => Promise.reject(new Error('fixture connection unavailable')),
          timeout: () => new Promise((resolve) => setTimeout(() => resolve(failureResponse('timeout')), 75)),
          empty_content: () => Promise.resolve(failureResponse('empty_content')),
          invalid_json: () => Promise.resolve(new Response('not-json', { status: 200, headers: { 'content-type': 'application/json' } })),
          schema_mismatch: () => Promise.resolve(failureResponse('schema_mismatch')),
        };
        const qwen = {};
        for (const [caseId, responder] of Object.entries(qwenCases)) {
          window.fetch = (input, init) => String(input).includes('/api/science/interpret') ? responder() : originalFetch(input, init);
          document.querySelector('[data-science-status]').textContent = 'browser matrix pending: ' + caseId;
          document.querySelector('[data-science-qwen-experimental]').click();
          const closed = await waitFor(() => status().includes('Qwen 해석을 사용할 수 없습니다'));
          qwen[caseId] = { closed, redCount: redCount(), status: status() };
        }
        window.fetch = originalFetch;

        const post = async (path, payload) => {
          const response = await originalFetch(path, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(payload),
          });
          let body = null;
          try { body = await response.json(); } catch { body = null; }
          return { status: response.status, body };
        };
        const documentText = 'Photo Track에서 Spin Coating 두께를 높이려면 final spin RPM을 높여야 한다.';
        const aliases = await post('/api/science/aliases/detect', {
          document: documentText,
          request_id: 'browser-matrix-aliases',
        });
        const matches = aliases.body?.matches || [];
        const pick = (surface) => matches.find((item) => item.surface_term === surface);
        const selected = { subject: pick('RPM'), relation: pick('높여야 한다'), object: pick('두께') };
        if (!selected.subject || !selected.relation || !selected.object) throw new Error('browser matrix aliases unavailable');
        const span = {
          offset_encoding: 'unicode_code_point', start: 0,
          end: Array.from(documentText).length, exact: documentText, prefix: '', suffix: '',
        };
        const baseCandidate = {
          source_span: span,
          normalized_claim: {
            subject_concept_id: selected.subject.concept_id,
            relation_kind: 'monotonic_direction', predicate: selected.relation.concept_id,
            object_concept_id: selected.object.concept_id, polarity: 'positive',
            quantities: [], conditions: [], process_stage: null, material_state: null,
          },
          ontology_refs: [selected.subject.ontology_ref, selected.relation.ontology_ref, selected.object.ontology_ref],
          ambiguity_ids: [],
          candidate_meanings: ['subject', 'relation', 'object'].map((role) => ({
            ambiguity_id: null, concept_role: role, surface_term: selected[role].surface_term,
            ontology_ref: selected[role].ontology_ref, meaning: selected[role].meaning,
          })),
          decision_impact: [],
        };
        const clone = (value) => JSON.parse(JSON.stringify(value));
        const mutations = {
          unknown_ontology_ref(candidate) { candidate.ontology_refs.push('sci:binding:does-not-exist'); },
          alias_absent_from_document(candidate) { candidate.candidate_meanings[0].surface_term = '문서에 없는 별칭'; },
          overlapping_role_span(candidate) { candidate.candidate_meanings[1].surface_term = 'RPM'; },
          incomplete_claim_span(candidate) {
            candidate.source_span.exact = 'Photo Track에서 Spin Coating';
            candidate.source_span.end = Array.from(candidate.source_span.exact).length;
          },
        };
        const claims = {};
        for (const [caseId, mutate] of Object.entries(mutations)) {
          const candidate = clone(baseCandidate); mutate(candidate);
          const response = await post('/api/science/claims/submit', {
            document: documentText, client_kind: 'codex', candidate,
            idempotency_key: 'browser-matrix-' + caseId,
          });
          claims[caseId] = {
            status: response.status,
            decision: response.body?.decision_impact?.[0]?.status || null,
            issues: response.body?.decision_impact?.[0]?.issue_codes || [],
            redCount: redCount(),
          };
        }
        const parity = {};
        for (const clientKind of ['codex', 'claude']) {
          parity[clientKind] = await post('/api/science/claims/submit', {
            document: documentText, client_kind: clientKind, candidate: baseCandidate,
            idempotency_key: 'browser-matrix-parity-' + clientKind,
          });
        }
        const core = await import('/static/science_verifier_core.mjs');
        const locator = {
          medium: 'pdf', exact: true, section: '3.2', pdf_page_index: 6, printed_page: '7',
          resource_url: 'https://example.test/source.pdf', requested_url: 'https://example.test/source.pdf',
          resolved_url: 'https://example.test/source.pdf', content_hash: 'sha256:' + '1'.repeat(64),
          retrieved_at: '2026-08-25T00:00:00Z', hash_scope: 'retrieved_resource',
        };
        const verdict = {
          verdict: 'VIOLATION', decisive_rule_ids: ['sci:rule:test'],
          condition_evaluations: [{ condition_id: 'scope', satisfied: true }],
          evidence_refs: ['sci:evidence:test'],
        };
        const annotation = { evidence_links: [{
          evidence_id: 'sci:evidence:test', locator, url: 'https://example.test/source.pdf',
          reviewed_source: { qualification_state: 'active' },
        }] };
        return {
          qwen,
          claims,
          parity: {
            statuses: [parity.codex.status, parity.claude.status],
            sameClaim: parity.codex.body?.candidate_claims?.[0]?.claim_id === parity.claude.body?.candidate_claims?.[0]?.claim_id,
            sameDecision: JSON.stringify(parity.codex.body?.decision_impact) === JSON.stringify(parity.claude.body?.decision_impact),
            redCount: redCount(),
          },
          redGate: {
            exactActiveFixtureAccepted: core.trustedViolationState(verdict, [annotation], true),
            inexactLocatorRejected: !core.trustedViolationState(verdict, [{ evidence_links: [{ ...annotation.evidence_links[0], locator: { section: '3.2' } }] }], true),
            inactiveReleaseRejected: !core.trustedViolationState(verdict, [annotation], false),
          },
        };
      })()
    `);

    await cdp.evaluate(`
      (() => {
        const input = document.querySelector('[name="document"]');
        input.value = 'RPM은 회전 속도이고, R은 저항이다.';
        input.setSelectionRange(0, input.value.length);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        document.querySelector('[data-science-alias-detect]').click();
      })()
    `);
    await waitUntil(cdp, "document.querySelector('[data-science-status]')?.textContent.includes('등록 용어를 찾았습니다') && document.querySelectorAll('.science-alias-chip').length > 0", args.timeoutMs);
    const tokenBoundary = await cdp.evaluate(`
      (() => ({
        resistanceChips: [...document.querySelectorAll('.science-alias-chip')].filter((node) => node.textContent === 'R → sci:concept:resistance').length,
        resistanceMarks: [...document.querySelectorAll('[data-ontology-ref="sci:binding:domain:resistance"]')].filter((node) => node.textContent === 'R').length,
        rpmChips: [...document.querySelectorAll('.science-alias-chip')].filter((node) => node.textContent === 'RPM → sci:concept:spin-speed').length,
      }))()
    `);

    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await sleep(250);
    const mobile = await cdp.evaluate(`
      (() => ({
        width: window.innerWidth,
        columns: getComputedStyle(document.querySelector('.science-live-grid')).gridTemplateColumns,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        editorVisible: !document.querySelector('[data-science-candidate-editor]').hidden,
      }))()
    `);
    if (args.mobileScreenshot) await cdp.screenshot(args.mobileScreenshot);

    await cdp.send("Emulation.clearDeviceMetricsOverride");
    const origin = new URL(args.url).origin;
    const documentUrl = `${origin}/docs/boi:public:science:knowledge:spin-coating:004?employee_id=100001`;
    await cdp.send("Page.navigate", { url: documentUrl });
    await waitUntil(cdp, "document.readyState === 'complete' && !!document.querySelector('[data-science-selection-launcher]')", args.timeoutMs);
    await cdp.evaluate(`
      (() => {
        const paragraph = document.querySelector('.markdown-body p');
        const textNode = paragraph?.firstChild;
        if (!textNode) return false;
        const range = document.createRange();
        range.selectNodeContents(paragraph);
        const selection = getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        document.querySelector('[data-science-selection-launcher]').click();
        return true;
      })()
    `);
    await waitUntil(cdp, "location.pathname === '/science-verifier' && document.querySelector('[data-science-status]')?.textContent.length > 0", args.timeoutMs);
    const handoff = await cdp.evaluate(`
      (() => ({
        documentRef: document.querySelector('[name="document_ref"]')?.value || '',
        textareaHasContent: (document.querySelector('[name="document"]')?.value || '').length > 100,
        selectionReady: document.querySelector('[data-science-status]')?.textContent.includes('ACL 확인된 원문'),
      }))()
    `);

    const checks = {
      page_loaded: desktop.releaseStatus === "release_candidate",
      candidate_not_operational: desktop.operational === "false" && desktop.candidateBoundary,
      nav_order: desktop.nav.indexOf("sops") < desktop.nav.indexOf("science") && desktop.nav.indexOf("science") < desktop.nav.indexOf("events"),
      inactive_release_has_no_red: desktop.redCount === 0,
      deterministic_aliases_visible: desktop.aliasCount >= 3 && desktop.aliasChipCount >= 3,
      manual_claim_editor_visible: desktop.candidateEditorVisible && desktop.roleSelects === 3,
      qwen_is_separate_experimental_action: desktop.qwenExperimental && desktop.noLlmBoundary,
      default_used_deterministic_non_qwen_path: defaultNonQwenPath,
      manual_claim_confirmed_without_llm_or_verdict: manualRoute.redCount === 0 && manualRoute.cards === 1 && !manualRoute.leakedConfirmationCode && scienceRequests.some((item) => item.url.includes("/api/science/claims/submit")) && scienceRequests.some((item) => item.url.includes("/api/science/interpretations/") && item.url.includes("/confirm")) && !scienceRequests.some((item) => item.url.includes("/api/science/verify-document")),
      ascii_alias_token_boundary: tokenBoundary.resistanceChips === 1 && tokenBoundary.resistanceMarks === 1 && tokenBoundary.rpmChips === 1,
      qwen_failure_matrix_has_no_red: Object.values(failureMatrix.qwen).every((item) => item.closed && item.redCount === 0),
      invalid_claim_matrix_has_no_red: Object.values(failureMatrix.claims).every((item) => item.redCount === 0 && (item.decision === "blocked_semantic_mismatch" || item.status >= 400)),
      external_clients_submit_same_claim: failureMatrix.parity.statuses.every((status) => status === 200) && failureMatrix.parity.sameClaim && failureMatrix.parity.sameDecision && failureMatrix.parity.redCount === 0,
      red_gate_requires_active_rule_conditions_and_exact_evidence: failureMatrix.redGate.exactActiveFixtureAccepted && failureMatrix.redGate.inexactLocatorRejected && failureMatrix.redGate.inactiveReleaseRejected,
      prohibited_ui_absent: desktop.noScore && desktop.noDoe,
      actions_separated_and_focusable: desktop.distinctActions && desktop.focusVisibleTarget,
      desktop_no_overflow: !desktop.horizontalOverflow,
      mobile_single_column: mobile.width === 390 && mobile.columns.split(" ").length === 1 && !mobile.horizontalOverflow && mobile.editorVisible,
      wiki_selection_handoff: handoff.documentRef === "boi:public:science:knowledge:spin-coating:004" && handoff.textareaHasContent && handoff.selectionReady,
      console_clean: relevantConsoleErrors(consoleErrors).length === 0,
    };
    const report = {
      ok: Object.values(checks).every(Boolean),
      checks,
      desktop,
      mobile,
      handoff,
      manualRoute,
      tokenBoundary,
      failureMatrix,
      scienceRequests,
      consoleErrors: relevantConsoleErrors(consoleErrors),
      screenshot: args.screenshot,
      mobileScreenshot: args.mobileScreenshot,
      browser: "Chrome DevTools Protocol",
      browserFallbackReason: "agent-browser CLI unavailable; used the repository CDP verification pattern.",
    };
    if (args.reportJson) {
      const fileDigest = (path) => path && existsSync(path)
        ? `sha256:${createHash("sha256").update(readFileSync(path)).digest("hex")}`
        : "";
      const manifestDir = dirname(args.reportJson);
      const captures = [args.screenshot, args.mobileScreenshot]
        .filter((path) => path && existsSync(path))
        .map((path) => ({ path: relative(manifestDir, path) || basename(path), sha256: fileDigest(path) }));
      const captureManifest = {
        schema_version: "science-browser-capture-manifest/0.1",
        captured_at: new Date().toISOString(),
        git_commit: args.gitCommit,
        route: new URL(args.url).pathname,
        release_status: desktop.releaseStatus,
        operational: desktop.operational === "true",
        checks: Object.entries(checks).map(([check_id, passed]) => ({ check_id, status: passed ? "passed" : "failed" })),
        captures,
        screenshots: {
          desktop: { path: args.screenshot, sha256: fileDigest(args.screenshot) },
          mobile: { path: args.mobileScreenshot, sha256: fileDigest(args.mobileScreenshot) },
        },
        science_requests: scienceRequests.map((item) => ({ path: new URL(item.url).pathname, method: item.method })),
        console_errors: relevantConsoleErrors(consoleErrors),
        browser: report.browser,
        browser_fallback_reason: report.browserFallbackReason,
      };
      writeFileSync(args.reportJson, `${JSON.stringify(captureManifest, null, 2)}\n`);
    }
    console.log(JSON.stringify(report, null, 2));
    if (args.strict && !report.ok) process.exitCode = 1;
  } finally {
    cdp?.close();
    await terminateChrome(child);
    rmSync(profileDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.message, stack: error.stack }, null, 2));
  process.exit(1);
});
