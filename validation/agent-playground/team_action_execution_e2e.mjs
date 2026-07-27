#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  keycloakUrl: process.env.KEYCLOAK_URL || "http://localhost:18082",
  hcpUrl: process.env.HCP_URL || "http://localhost:18083",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  crossAuthorResult:
    process.env.CROSS_AUTHOR_RESULT
    || "artifacts/agent-playground-current/browser/cross-author-composition/cross-author-adoption-result.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-current/browser/team-action-execution",
  boiContainer:
    process.env.BOI_MAINLINE_CONTAINER
    || "boi-agent-playground-mainline-boi-api-1",
};

const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const cross = await fs.readFile(config.crossAuthorResult, "utf8")
  .then((value) => JSON.parse(value))
  .catch(() => ({}));
const draftId = String(
  process.env.TEAM_ACTION_DRAFT_ID
  || cross.validation?.action_draft_id
  || "",
);
const expectedFlowId = String(
  process.env.TEAM_ACTION_FLOW_ID
  || cross.validation?.exact_flow_id
  || "",
);
const expectedChecksum = String(
  process.env.TEAM_ACTION_CHECKSUM
  || cross.validation?.checksum
  || "",
);
const expectedTaskRef = String(
  process.env.TEAM_ACTION_TASK_REF
  || cross.validation?.task_ref
  || "",
);
if (!identities["100001"] || !identities["100002"] || !draftId || !expectedFlowId) {
  throw new Error("cross-author or OIDC validation fixture is incomplete");
}
await fs.mkdir(config.evidenceDir, { recursive: true });

const result = {
  ok: false,
  registration: {},
  operator: {},
  action: {},
  endpoint_owner: {},
  caller: {},
  private_draft: {},
  viewer: {},
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function setHcpPrincipal(employeeId, payload) {
  const response = await fetch(`${config.hcpUrl}/__validation/state`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-validation-token": "boi-hcp-validation-control",
    },
    body: JSON.stringify({ employee_id: employeeId, ...payload }),
  });
  assert(response.ok, `HCP fixture update for ${employeeId} returned ${response.status}`);
}

async function resetHcpFixtures() {
  const response = await fetch(`${config.hcpUrl}/__validation/state`, {
    method: "DELETE",
    headers: { "x-validation-token": "boi-hcp-validation-control" },
  });
  assert(response.ok, `HCP fixture reset returned ${response.status}`);
}

async function resetViewerPassword() {
  const password = crypto.randomBytes(24).toString("base64url");
  const tokenResponse = await fetch(
    `${config.keycloakUrl}/realms/master/protocol/openid-connect/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "password",
        client_id: "admin-cli",
        username: "validation-admin",
        password: "validation-admin",
      }),
    },
  );
  assert(tokenResponse.ok, `Keycloak admin login returned ${tokenResponse.status}`);
  const adminToken = (await tokenResponse.json()).access_token;
  const usersResponse = await fetch(
    `${config.keycloakUrl}/admin/realms/boi-validation/users?username=100003&exact=true`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  assert(usersResponse.ok, `Keycloak viewer lookup returned ${usersResponse.status}`);
  const user = (await usersResponse.json())[0];
  assert(user?.id, "Keycloak 100003 fixture is missing");
  const resetResponse = await fetch(
    `${config.keycloakUrl}/admin/realms/boi-validation/users/${user.id}/reset-password`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${adminToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        type: "password",
        value: password,
        temporary: false,
      }),
    },
  );
  assert(resetResponse.status === 204, `Keycloak viewer reset returned ${resetResponse.status}`);
  return password;
}

function diagnostics(page, scope) {
  page.on("pageerror", (error) => {
    result.page_errors.push({ scope, text: String(error.message || error) });
  });
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error"
      && !text.startsWith("Failed to load resource:")
      && !text.includes("favicon")
    ) {
      result.console_errors.push({ scope, text });
    }
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status < 400) return;
    const url = new URL(response.url());
    const expected = (
      scope === "viewer-100003"
      && status === 403
      && url.pathname === "/api/actions/invoke"
    );
    if (!expected) {
      result.unexpected_http_errors.push({
        scope,
        status,
        method: response.request().method(),
        url: `${url.origin}${url.pathname}`,
      });
    }
  });
}

async function login(browser, employeeId, password) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, `viewer-${employeeId}`);
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    await page.locator("#username").fill(employeeId);
    await page.locator("#password").fill(password);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  const identity = await page.evaluate(async () => {
    const response = await fetch("/api/agent-playground");
    return (await response.json()).identity;
  });
  assert(identity?.employee_id === employeeId, `OIDC principal mismatch for ${employeeId}`);
  return { context, page, identity };
}

async function sessionFetch(page, url, options = {}) {
  return page.evaluate(async ({ url, options }) => {
    const response = await fetch(url, options);
    return {
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  }, { url, options });
}

function collectFields(value, key, output = []) {
  if (Array.isArray(value)) {
    value.forEach((item) => collectFields(item, key, output));
  } else if (value && typeof value === "object") {
    for (const [name, item] of Object.entries(value)) {
      if (name === key) output.push(item);
      collectFields(item, key, output);
    }
  }
  return output;
}

function executionSummary(body) {
  const taskContext = collectFields(body, "task_context")
    .find((item) => item && typeof item === "object" && !Array.isArray(item)) || {};
  const sourceReferences = collectFields(body, "source_references")
    .filter(Array.isArray)
    .sort((left, right) => right.length - left.length)[0] || [];
  const ontologyRelationships = collectFields(body, "ontology_relationships")
    .filter(Array.isArray)
    .sort((left, right) => right.length - left.length)[0] || [];
  return {
    status: String(body.status || ""),
    flow_id: String(body.flow_id || ""),
    grounding_status: String(
      collectFields(body, "grounding_status").map(String).find(Boolean) || "",
    ),
    source_reference_count: sourceReferences.length,
    ontology_relationship_count: ontologyRelationships.length,
    task_context: taskContext,
  };
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let ownerSession;
let callerSession;
let viewerSession;
try {
  ownerSession = await login(browser, "100002", identities["100002"]);
  await ownerSession.page.goto(
    `${config.boiUrl}/actions/drafts/${encodeURIComponent(draftId)}`,
    { waitUntil: "networkidle" },
  );
  const draftsBefore = await sessionFetch(
    ownerSession.page,
    "/api/registration/drafts",
  );
  const draftBefore = {
    status: draftsBefore.status,
    body: {
      draft: (draftsBefore.body.items || []).find(
        (item) => item.draft_id === draftId,
      ),
    },
  };
  assert(draftBefore.status === 200, "team Action draft lookup failed");
  assert(draftBefore.body.draft, "team Action draft was not found");
  assert(draftBefore.body.draft?.scope === "team", "Action draft is not team-scoped");
  assert(
    draftBefore.body.draft?.folder === "team/aix-tf/action-drafts",
    "Action team is not aix-tf",
  );
  assert(
    draftBefore.body.draft?.request?.connector_config?.flow_id === expectedFlowId,
    "registration exact Flow ID changed",
  );
  assert(
    draftBefore.body.draft?.request?.connector_config?.artifact_checksum
      === expectedChecksum,
    "registration exact checksum changed",
  );
  const connector = draftBefore.body.draft.request.connector_config;
  const ownerInbox = await sessionFetch(ownerSession.page, "/api/inbox?limit=50");
  const ownerTaskRef = expectedTaskRef || (ownerInbox.body.items || [])
    .map((item) => String(item.task_id || ""))
    .find((value) => value.startsWith("task:"));
  assert(ownerTaskRef, "endpoint owner has no ACL-checked Task anchor for revalidation");
  const exactRevalidation = await sessionFetch(
    ownerSession.page,
    `/api/agent-playground/flows/${encodeURIComponent(expectedFlowId)}/validate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint_id: connector.endpoint_connection_id,
        project_id: connector.project_id,
        task_ref: ownerTaskRef,
      }),
    },
  );
  assert(exactRevalidation.status === 200, "linked team Flow revalidation failed");
  assert(
    exactRevalidation.body.validation_status === "action_linked",
    "successful revalidation did not preserve action_linked",
  );
  if (draftBefore.body.draft?.status !== "publish_requested") {
    await ownerSession.page.locator("[data-validate-draft]").click();
    await ownerSession.page
      .locator("[data-validation-state]")
      .filter({ hasText: "통과" })
      .waitFor();
    await ownerSession.page.locator("[data-publish-draft]").click();
    await ownerSession.page
      .locator("[data-draft-status]")
      .filter({ hasText: "publish_requested" })
      .waitFor();
  }
  await ownerSession.page.screenshot({
    path: path.join(config.evidenceDir, "01-team-action-publish-requested.png"),
    fullPage: true,
  });
  result.screenshots.push("01-team-action-publish-requested.png");

  const operatorRaw = execFileSync(
    "docker",
    [
      "exec",
      config.boiContainer,
      "python",
      "/workspace/scripts/apply_agent_playground_action_fixture.py",
      "--runtime-root",
      "/runtime",
      "--catalog-root",
      "/action_catalog",
      "--employee-id",
      "100002",
      "--draft-id",
      draftId,
    ],
    { encoding: "utf8", timeout: 120_000 },
  );
  const operator = JSON.parse(operatorRaw.trim());
  assert(operator.ok, "validation operator did not apply the Action");
  assert(operator.deployment_reference.flow_id === expectedFlowId, "operator Flow ID drifted");
  assert(
    operator.deployment_reference.artifact_checksum === expectedChecksum,
    "operator checksum drifted",
  );
  result.registration = {
    draft_id: draftId,
    scope: "team",
    team_id: "aix-tf",
    status: "publish_requested",
    exact_flow_id: expectedFlowId,
    artifact_checksum: expectedChecksum,
    revalidation_status: exactRevalidation.body.validation_status,
  };
  result.operator = operator;

  await setHcpPrincipal("100001", {
    allowed: true,
    teams: ["aix-tf", "platform"],
    roles: [
      "boi.viewer",
      "boi.editor",
      "boi.workflow_runner",
      "boi.action_invoker",
      "boi.admin",
    ],
    projects: ["boi-100001"],
  });
  callerSession = await login(browser, "100001", identities["100001"]);
  const catalog = await sessionFetch(callerSession.page, "/api/actions/catalog");
  assert(catalog.status === 200, "team Action catalog lookup failed");
  const action = (catalog.body.items || []).find(
    (item) => item.action_key === operator.action_key,
  );
  assert(action, "team Action is not visible to the same-team caller");
  assert(action.scope === "team" && action.team_id === "aix-tf", "catalog team scope drifted");
  const inbox = await sessionFetch(callerSession.page, "/api/inbox?limit=50");
  assert(inbox.status === 200, "caller Task inbox lookup failed");
  let actualTaskRef = (inbox.body.items || [])
    .map((item) => String(item.task_id || item.task_ref || ""))
    .find((value) => value.startsWith("task:"));
  let taskSource = "existing_acl_inbox";
  if (!actualTaskRef) {
    const taskTraceId = `trace-team-caller-task-${Date.now()}`;
    const prior = await sessionFetch(callerSession.page, "/api/actions/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: "manual.equipment.confirm_alarm_context",
        event: {
          event_id: `evt-team-caller-prior-${Date.now()}`,
          event_type: "equipment.alarm.raised.v1",
          trace_id: taskTraceId,
        },
        payload: {
          title: "Team Action caller prior evidence",
          equipment_id: "EQ-TEAM-CALLER",
        },
        dry_run: false,
      }),
    });
    assert(
      prior.status === 200 && prior.body.status === "manual_required",
      "caller prior Task evidence could not be created",
    );
    const task = await sessionFetch(callerSession.page, "/api/actions/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: "manual.equipment.review_root_cause",
        event: {
          event_id: `evt-team-caller-task-${Date.now()}`,
          event_type: "root_cause.analysis.requested.v1",
          trace_id: taskTraceId,
        },
        payload: {
          title: "Team Action caller actual Task",
          equipment_id: "EQ-TEAM-CALLER",
        },
        dry_run: false,
      }),
    });
    assert(
      task.status === 200 && task.body.status === "manual_required",
      "caller actual Task could not be created",
    );
    actualTaskRef = `task:${task.body.request_id}`;
    taskSource = "actual_manual_action_task";
  }
  assert(actualTaskRef, "caller has no ACL-checked Task anchor");

  const invoke = async (payload, label) => {
    const now = Date.now();
    const response = await sessionFetch(callerSession.page, "/api/actions/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: operator.action_key,
        event: {
          event_id: `evt-team-action-${label}-${now}`,
          event_type: "agent.playground.requested.v1",
          trace_id: `trace-team-action-${label}-${now}`,
        },
        payload,
        dry_run: false,
      }),
    });
    assert(response.status === 200, `${label} team Action returned ${response.status}`);
    assert(response.body.status === "langflow_invoked", `${label} team Action did not invoke Langflow`);
    assert(response.body.flow_id === expectedFlowId, `${label} team Action Flow ID drifted`);
    return response;
  };

  const general = await invoke(
    {
      question: "일반 Wiki 질문을 Task Context·Ontology 근거로 정리해줘.",
      save_mode: "preview",
    },
    "general",
  );
  const generalSummary = executionSummary(general.body);
  assert(
    generalSummary.task_context.profile === "knowledge_lookup"
      && !generalSummary.task_context.sop_ref,
    "ordinary question created false SOP context",
  );
  assert(
    generalSummary.source_reference_count > 0
      && generalSummary.ontology_relationship_count > 0,
    "ordinary question lost source or Ontology evidence",
  );

  const sop = await invoke(
    {
      question: "이 Task의 SOP 단계, 선행 결과, 필요한 근거와 부족한 근거를 정리해줘.",
      task_ref: actualTaskRef,
      save_mode: "preview",
    },
    "sop",
  );
  const sopSummary = executionSummary(sop.body);
  assert(
    sopSummary.task_context.profile === "sop_task_execution"
      && sopSummary.task_context.task_ref === actualTaskRef
      && sopSummary.task_context.sop_ref
      && sopSummary.task_context.sop_stage
      && sopSummary.task_context.event_ref
      && sopSummary.task_context.action_ref,
    "actual SOP Task Context was not preserved",
  );
  assert(
    Array.isArray(sopSummary.task_context.prior_results)
      && Array.isArray(sopSummary.task_context.required_evidence)
      && Array.isArray(sopSummary.task_context.missing_evidence),
    "actual SOP evidence fields are incomplete",
  );

  const traceId = `trace-team-action-${Date.now()}`;
  const invoked = await sessionFetch(callerSession.page, "/api/actions/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_key: operator.action_key,
      event: {
        event_id: `evt-team-action-${Date.now()}`,
        event_type: "agent.playground.requested.v1",
        trace_id: traceId,
      },
      payload: {
        question: "같은 팀 공유 Action으로 Wiki·Ontology 근거를 정리해줘.",
        save_mode: "private_draft",
        title: "팀 공유 Action 호출자 개인 초안",
      },
      dry_run: false,
    }),
  });
  assert(invoked.status === 200, `team Action execution returned ${invoked.status}`);
  assert(invoked.body.status === "langflow_invoked", "team Action did not invoke Langflow");
  assert(invoked.body.flow_id === expectedFlowId, "team Action runtime Flow ID drifted");
  const draftReferences = collectFields(invoked.body, "draft_reference")
    .map(String)
    .filter(Boolean);
  const saveStatuses = collectFields(invoked.body, "save_status")
    .concat(collectFields(invoked.body, "status"))
    .map(String);
  const privateEvidenceRaw = execFileSync(
    "docker",
    [
      "exec",
      config.boiContainer,
      "python",
      "-c",
      [
        "import json,sys",
        "from pathlib import Path",
        "title=sys.argv[1]",
        "rows=[]",
        "for p in Path('/runtime/agent-playground/wiki-plans').glob('*.json'):",
        " d=json.loads(p.read_text())",
        " if str((d.get('input') or {}).get('title') or '')==title: rows.append((p.stat().st_mtime,d))",
        "assert rows, 'private draft evidence was not found'",
        "d=sorted(rows,key=lambda item:item[0],reverse=True)[0][1]",
        "print(json.dumps({'employee_id':d.get('employee_id'),'status':d.get('status'),'plan_id':d.get('plan_id'),'wiki_url':d.get('wiki_url'),'confirmed_at':d.get('confirmed_at')}))",
      ].join("\n"),
      "팀 공유 Action 호출자 개인 초안",
    ],
    { encoding: "utf8", timeout: 30_000 },
  );
  const privateEvidence = JSON.parse(privateEvidenceRaw.trim());
  assert(
    privateEvidence.employee_id === "100001" && privateEvidence.status === "saved",
    `private draft is not saved for the caller: ${privateEvidenceRaw}`,
  );
  const privatePage = await sessionFetch(callerSession.page, privateEvidence.wiki_url);
  assert(privatePage.status === 200, "caller cannot open the generated private Wiki draft");
  result.action = {
    action_key: operator.action_key,
    scope: action.scope,
    team_id: action.team_id,
    status: invoked.body.status,
    flow_id: invoked.body.flow_id,
    trace_id: traceId,
    general_execution: generalSummary,
    sop_execution: sopSummary,
    task_source: taskSource,
  };
  result.endpoint_owner = {
    employee_id: "100002",
    endpoint_id: operator.deployment_reference.endpoint_connection_id,
  };
  result.caller = {
    employee_id: "100001",
    teams: callerSession.identity.teams,
  };
  result.private_draft = {
    owner_employee_id: privateEvidence.employee_id,
    draft_reference: draftReferences[0] || privateEvidence.plan_id,
    wiki_url: privateEvidence.wiki_url,
    confirmed_at: privateEvidence.confirmed_at,
    save_statuses: [...new Set(saveStatuses)],
  };
  await callerSession.page.goto(`${config.boiUrl}/actions`, {
    waitUntil: "domcontentloaded",
  });
  await callerSession.page.getByText(action.name_ko, { exact: true }).first().waitFor();
  await callerSession.page.screenshot({
    path: path.join(config.evidenceDir, "02-team-action-caller-catalog.png"),
    fullPage: true,
  });
  result.screenshots.push("02-team-action-caller-catalog.png");

  const viewerPassword = await resetViewerPassword();
  viewerSession = await login(browser, "100003", viewerPassword);
  const denied = await sessionFetch(viewerSession.page, "/api/actions/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_key: operator.action_key,
      event: {
        event_id: `evt-viewer-denied-${Date.now()}`,
        event_type: "agent.playground.requested.v1",
        trace_id: `trace-viewer-denied-${Date.now()}`,
      },
      payload: { question: "viewer must not execute", save_mode: "private_draft" },
      dry_run: false,
    }),
  });
  assert(denied.status === 403, `100003 Action execution returned ${denied.status}`);
  result.viewer = {
    employee_id: "100003",
    roles: viewerSession.identity.roles,
    execution_status: denied.status,
  };

  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "unexpected browser diagnostics were recorded");
} finally {
  await ownerSession?.context.close().catch(() => {});
  await callerSession?.context.close().catch(() => {});
  await viewerSession?.context.close().catch(() => {});
  await resetHcpFixtures().catch(() => {});
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
