#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  hcpUrl: process.env.HCP_URL || "http://localhost:18083",
  employeeId: "100002",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-security-context-hardening",
  boiContainer:
    process.env.BOI_MAINLINE_CONTAINER
    || "boi-agent-playground-mainline-boi-api-1",
};
const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
for (const employeeId of ["100001", "100002"]) {
  if (!identities[employeeId]) {
    throw new Error(`${employeeId} validation password is unavailable`);
  }
}
await fs.mkdir(config.evidenceDir, { recursive: true });

const result = {
  ok: false,
  oidc: {},
  hcp: {},
  run_token_audience: {},
  task_context: {},
  typed_ontology: {},
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function hcpState(payload) {
  const response = await fetch(`${config.hcpUrl}/__validation/state`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-validation-token": "boi-hcp-validation-control",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HCP validation control returned ${response.status}`);
  return response.json();
}

async function resetHcp() {
  const response = await fetch(`${config.hcpUrl}/__validation/state`, {
    method: "DELETE",
    headers: { "x-validation-token": "boi-hcp-validation-control" },
  });
  if (!response.ok) throw new Error(`HCP validation reset returned ${response.status}`);
}

async function login(context, employeeId) {
  const page = await context.newPage();
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error"
      && !text.includes("favicon")
      && !text.startsWith("Failed to load resource:")
    ) {
      result.console_errors.push(text.slice(0, 500));
    }
  });
  page.on("pageerror", (error) => result.page_errors.push(String(error).slice(0, 500)));
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    result.oidc = {
      state: Boolean(authorization.searchParams.get("state")),
      nonce: Boolean(authorization.searchParams.get("nonce")),
      pkce_s256: authorization.searchParams.get("code_challenge_method") === "S256",
    };
    await page.locator("#username").fill(employeeId);
    await page.locator("#password").fill(String(identities[employeeId]));
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  return page;
}

async function sessionFetch(page, pathname, options = {}) {
  return page.evaluate(
    async ({ pathname: target, options: requestOptions }) => {
      const response = await fetch(target, requestOptions);
      const text = await response.text();
      let body = {};
      try {
        body = JSON.parse(text);
      } catch {
        body = { text };
      }
      return { status: response.status, body };
    },
    { pathname, options },
  );
}

async function issuePat(page, name) {
  const created = await sessionFetch(page, "/api/v2/tokens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      scopes: ["boi.read", "boi.draft"],
      expires_in_days: null,
    }),
  });
  assert(created.status === 200, `PAT create returned ${created.status}`);
  return created.body.token;
}

function patHeaders(token) {
  return {
    "x-service-token": "mainline-validation-service-token",
    Authorization: `Bearer ${token}`,
  };
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let ownerContext;
let developerContext;
try {
  await resetHcp();
  ownerContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const ownerPage = await login(ownerContext, "100001");
  const ownerPat = await issuePat(ownerPage, "ACL aggregate validation");
  const hiddenTerm = `QuasarNeedle${Date.now()}`;
  const hiddenPlan = await sessionFetch(
    ownerPage,
    "/internal/agent-playground/wiki/plans",
    {
      method: "POST",
      headers: {
        ...patHeaders(ownerPat.token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        capability_id: "knowledge.draft",
        goal: "ACL aggregate validation",
        input: {
          title: `${hiddenTerm} private evidence`,
          body: `${hiddenTerm} must remain private to 100001.`,
          source_refs: [],
          provenance: { validation: "acl-aggregate" },
        },
      }),
    },
  );
  assert(hiddenPlan.status === 200, "private ACL validation plan failed");
  const hiddenConfirm = await sessionFetch(
    ownerPage,
    `/internal/agent-playground/wiki/plans/${encodeURIComponent(hiddenPlan.body.plan_id)}/confirm`,
    {
      method: "POST",
      headers: {
        ...patHeaders(ownerPat.token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason: "isolated ACL validation" }),
    },
  );
  assert(hiddenConfirm.status === 200, "private ACL validation confirm failed");

  developerContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await login(developerContext, config.employeeId);
  const pat = await issuePat(page, "Security context hardening");

  const traceId = `trace-agent-playground-${Date.now()}`;
  const eventId = `evt-agent-playground-${Date.now()}`;
  const priorAction = await sessionFetch(page, "/api/actions/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_key: "manual.equipment.confirm_alarm_context",
      event: {
        event_id: `${eventId}-prior`,
        event_type: "equipment.alarm.raised.v1",
        trace_id: traceId,
      },
      payload: {
        title: "Agent Playground prior Task validation",
        equipment_id: "EQ-AP-VALIDATION",
        owner: config.employeeId,
      },
      dry_run: false,
    }),
  });
  assert(priorAction.status === 200, `prior manual Action returned ${priorAction.status}`);
  assert(
    priorAction.body.status === "manual_required",
    "prior Action did not create lineage evidence",
  );
  const action = await sessionFetch(page, "/api/actions/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_key: "manual.equipment.review_root_cause",
      event: {
        event_id: eventId,
        event_type: "root_cause.analysis.requested.v1",
        trace_id: traceId,
      },
      payload: {
        title: "Agent Playground actual Task validation",
        equipment_id: "EQ-AP-VALIDATION",
        owner: config.employeeId,
      },
      dry_run: false,
    }),
  });
  assert(action.status === 200, `actual manual Action returned ${action.status}`);
  assert(action.body.status === "manual_required", "actual Action did not create a Task");
  const taskRef = `task:${action.body.request_id}`;

  const taskSearch = await sessionFetch(
    page,
    `/internal/agent-playground/wiki/search?q=${encodeURIComponent("이 Task의 근거를 정리해줘")}`
      + `&task_ref=${encodeURIComponent(taskRef)}`
      + `&trace_id=${encodeURIComponent(traceId)}`
      + `&event_id=${encodeURIComponent(eventId)}`
      + `&action_key=${encodeURIComponent("manual.equipment.review_root_cause")}`,
    { headers: patHeaders(pat.token) },
  );
  assert(taskSearch.status === 200, `actual Task context returned ${taskSearch.status}`);
  const contextPack = taskSearch.body.context_pack || {};
  result.task_context = {
    request: { task_ref: taskRef, trace_id: traceId, event_id: eventId },
    response: {
      context_profile: taskSearch.body.context_profile,
      retrieval_strategy: taskSearch.body.retrieval_strategy,
      context_pack: {
        task: contextPack.task,
        sop_stage: contextPack.sop_stage,
        trace_context: contextPack.trace_context,
      },
    },
    semantic_assertions: {
      server_resolved:
        contextPack.task?.task_id === taskRef
        && contextPack.task?.action_key === "manual.equipment.review_root_cause"
        && contextPack.trace_context?.trace_id === traceId,
    },
  };

  const relationSets = {};
  let allEdgesHaveProvenance = true;
  let markdownLinksNotTypedWorkflow = true;
  for (const view of ["workflow", "responsibility", "lineage", "impact"]) {
    const graph = await sessionFetch(
      page,
      `/internal/agent-playground/wiki/search?view=${view}`
        + `&source_ref=${encodeURIComponent(taskRef)}&limit=100`,
      { headers: patHeaders(pat.token) },
    );
    assert(graph.status === 200, `${view} graph returned ${graph.status}`);
    relationSets[view] = [...new Set((graph.body.edges || []).map((edge) => edge.relation))];
    for (const edge of graph.body.edges || []) {
      allEdgesHaveProvenance &&= Boolean(
        edge.payload?.provenance && (edge.payload?.source_refs || []).length,
      );
      if (view !== "document") {
        markdownLinksNotTypedWorkflow &&=
          edge.payload?.provenance !== "okf_markdown_link";
      }
    }
  }
  const fallback = await sessionFetch(
    page,
    "/internal/agent-playground/wiki/search"
      + "?view=workflow&source_ref=boi%3Apublic%3Ano-relations-validation&limit=20",
    { headers: patHeaders(pat.token) },
  );
  const acl = await sessionFetch(
    page,
    `/internal/agent-playground/wiki/search?q=${encodeURIComponent(hiddenTerm)}&limit=10`,
    { headers: patHeaders(pat.token) },
  );
  const aclSerialized = JSON.stringify(acl.body);
  const aclItems = Array.isArray(acl.body.items) ? acl.body.items : [];
  result.typed_ontology = {
    relation_sets: relationSets,
    all_edges_have_provenance: allEdgesHaveProvenance,
    markdown_links_not_typed_workflow: markdownLinksNotTypedWorkflow,
    fallback: { ontology_status: fallback.body.ontology_status },
    acl_exclusion: {
      count: acl.body.permission_excluded_count,
      leaked_ids: aclSerialized.includes("boi:private:100001")
        || aclItems.some(
          (item) => String(item?.title || "").includes(hiddenTerm),
        )
        ? ["private_identity_leaked"]
        : [],
    },
  };

  const missing = await sessionFetch(
    page,
    "/internal/agent-playground/wiki/search?q=missing"
      + "&task_ref=task%3Adoes-not-exist",
    { headers: patHeaders(pat.token) },
  );
  const inaccessible = await sessionFetch(
    page,
    "/internal/agent-playground/wiki/search?q=inaccessible"
      + "&task_ref=task%3Aother-user-private",
    { headers: patHeaders(pat.token) },
  );
  const ordinary = await sessionFetch(
    page,
    `/internal/agent-playground/wiki/search?q=${encodeURIComponent("일반 질문에 허위 SOP를 만들지 마")}`,
    { headers: patHeaders(pat.token) },
  );
  result.task_context.negative = {
    missing_task_status: missing.status,
    inaccessible_task_status: inaccessible.status,
  };
  result.task_context.ordinary_question = {
    context_profile: ordinary.body.context_profile,
  };

  await hcpState({
    employee_id: config.employeeId,
    allowed: true,
    teams: ["aix-tf"],
    roles: ["boi.viewer"],
    projects: ["boi-100002"],
  });
  const reduced = await sessionFetch(
    page,
    "/internal/agent-playground/wiki/plans",
    {
      method: "POST",
      headers: {
        ...patHeaders(pat.token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        capability_id: "knowledge.draft",
        goal: "must be denied after role reduction",
        input: {},
      }),
    },
  );
  await hcpState({ employee_id: config.employeeId, allowed: false });
  const disabled = await sessionFetch(
    page,
    `/internal/agent-playground/wiki/search?q=${encodeURIComponent("disabled")}`,
    { headers: patHeaders(pat.token) },
  );
  await hcpState({
    employee_id: config.employeeId,
    allowed: true,
    roles: [
      "boi.viewer",
      "boi.editor",
      "boi.workflow_runner",
      "boi.action_invoker",
    ],
    outage: true,
  });
  const outage = await sessionFetch(
    page,
    `/internal/agent-playground/wiki/search?q=${encodeURIComponent("outage")}`,
    { headers: patHeaders(pat.token) },
  );
  await resetHcp();
  let recovered = { status: 503, body: {} };
  for (let attempt = 0; attempt < 40; attempt += 1) {
    recovered = await sessionFetch(page, "/api/agent-playground");
    if (recovered.status === 200) break;
    await page.waitForTimeout(500);
  }
  assert(recovered.status === 200, "HCP authorization did not recover after validation reset");
  result.hcp = {
    role_reduction: {
      request: { employee_id: config.employeeId, required_scope: "boi.draft" },
      response: { status: reduced.status },
    },
    account_disabled: { response: { status: disabled.status } },
    outage: { response: { status: outage.status } },
    recovered: { response: { status: recovered.status } },
    cache_bypassed:
      reduced.status === 403
      && disabled.status === 403
      && outage.status === 503
      && recovered.status === 200,
  };

  const rawRunTokenEvidence = execFileSync(
    "docker",
    [
      "exec",
      "-e",
      `BOI_VALIDATION_TASK_REF=${taskRef}`,
      config.boiContainer,
      "python",
      "/workspace/scripts/verify_agent_playground_live_run_token.py",
    ],
    { encoding: "utf8", timeout: 120_000 },
  );
  result.run_token_audience = JSON.parse(rawRunTokenEvidence.trim());
  await page.screenshot({
    path: path.join(config.evidenceDir, "01-oidc-task-ontology-workbench.png"),
    fullPage: true,
  });
  result.screenshots.push("01-oidc-task-ontology-workbench.png");

  assert(Object.values(result.oidc).every(Boolean), "OIDC evidence is incomplete");
  assert(result.hcp.cache_bypassed, "HCP fail-closed checks did not pass");
  assert(result.run_token_audience.ok, "run-token audience checks did not pass");
  assert(result.task_context.semantic_assertions.server_resolved, "Task was not server-resolved");
  assert(
    result.task_context.response.retrieval_strategy
      === "task_context_ontology_hybrid",
    "Task retrieval was not ontology-first",
  );
  assert(
    result.typed_ontology.fallback.ontology_status
      === "grounded_document_fallback",
    "document fallback was not explicit",
  );
  assert(
    result.typed_ontology.acl_exclusion.count > 0
      && result.typed_ontology.acl_exclusion.leaked_ids.length === 0,
    "ACL aggregate result is incomplete or leaked hidden identity",
  );
  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "unexpected browser diagnostics were recorded");
} finally {
  await resetHcp().catch(() => {});
  if (ownerContext) await ownerContext.close();
  if (developerContext) await developerContext.close();
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
