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
  langflowUrl: process.env.LANGFLOW_URL || "http://localhost:7867",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  langflowIdentityFile:
    process.env.LANGFLOW_IDENTITY_FILE
    || "/tmp/boi-mainline-secrets.e5IZjp/langflow-users.json",
  crossAuthorResult:
    process.env.CROSS_AUTHOR_RESULT
    || "artifacts/agent-playground-current/browser/cross-author-composition/cross-author-adoption-result.json",
  teamActionResult:
    process.env.TEAM_ACTION_RESULT
    || "artifacts/agent-playground-current/browser/team-action-execution/result.json",
  incompatibleResult:
    process.env.INCOMPATIBLE_COMPONENT_RESULT
    || "artifacts/agent-playground-current/browser/incompatible-component/result.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-current/browser/component-composition-drift",
  boiContainer:
    process.env.BOI_MAINLINE_CONTAINER
    || "boi-agent-playground-mainline-boi-api-1",
};

const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const langflowIdentities = JSON.parse(
  await fs.readFile(config.langflowIdentityFile, "utf8"),
);
const storedLangflowAccount = (
  langflowIdentities.users?.["100002"]
  || langflowIdentities.recovery_user
);
const langflowAccount = {
  ...storedLangflowAccount,
  password: process.env.LANGFLOW_PASSWORD || storedLangflowAccount?.password || "",
};
const cross = JSON.parse(await fs.readFile(config.crossAuthorResult, "utf8"));
const team = JSON.parse(await fs.readFile(config.teamActionResult, "utf8"));
const incompatible = JSON.parse(
  await fs.readFile(config.incompatibleResult, "utf8"),
);
const deploymentId = String(team.operator?.deployment_reference?.deployment_id || "");
const flowId = String(cross.validation?.exact_flow_id || "");
const registeredChecksum = String(cross.validation?.checksum || "");
const taskRef = String(cross.composition?.task?.taskRef || "");
const componentId = String(cross.authorship?.assets?.find((item) => item.type === "py")?.id || "");
if (
  !identities["100001"]
  || !identities["100002"]
  || !langflowAccount?.password
  || !deploymentId
  || !flowId
  || !taskRef
) {
  throw new Error("drift validation fixture is incomplete");
}
await fs.mkdir(config.evidenceDir, { recursive: true });

const result = {
  ok: false,
  disconnected: cross.composition?.disconnected || {},
  compose: {
    public_patch_status: cross.composition?.compose?.public_patch_status,
    previous_checksum: cross.composition?.compose?.previous_checksum,
    live_checksum: cross.composition?.compose?.live_checksum,
    end_to_end_reachable:
      cross.composition?.compose?.end_to_end_reachable,
  },
  runtime: {
    status: cross.validation?.status === "action_ready" ? 200 : 500,
    component_id: componentId,
    executed_component_ids: cross.validation?.executed_component_ids || [],
  },
  incompatible: {
    status: incompatible.compose?.status,
    patch_request_count: incompatible.compose?.patch_request_count,
    reason: incompatible.compose?.reason,
    canvas_url: incompatible.compose?.canvas_url,
    checksum_before: incompatible.compose?.checksum_before,
    checksum_after: incompatible.compose?.checksum_after,
    asset_id: incompatible.asset?.asset_id,
  },
  drift: {},
  revalidation: {},
  page_errors: [],
  console_errors: [],
  ignored_console_errors: [],
  unexpected_http_errors: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function diagnostics(page, scope) {
  page.on("pageerror", (error) => {
    result.page_errors.push({ scope, text: String(error.message || error) });
  });
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error"
      && /^Duplicate request: \/api\/v1\/projects\/?$/.test(text)
    ) {
      result.ignored_console_errors.push({
        scope,
        text,
        reason: "unmodified Langflow frontend duplicate-request guard",
      });
      return;
    }
    if (
      message.type() === "error"
      && !text.startsWith("Failed to load resource:")
      && !text.includes("favicon")
    ) {
      result.console_errors.push({ scope, text });
    }
  });
}

async function loginBoi(browser, employeeId) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, `boi-${employeeId}`);
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    await page.locator("#username").fill(employeeId);
    await page.locator("#password").fill(identities[employeeId]);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  return { context, page };
}

async function loginLangflow(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "langflow-owner");
  await page.goto(`${config.langflowUrl}/flow/${flowId}`, {
    waitUntil: "domcontentloaded",
  });
  const password = page.locator('input[type="password"]');
  await password.waitFor({ state: "visible", timeout: 8_000 }).catch(() => null);
  if (await password.isVisible().catch(() => false)) {
    await page
      .locator('input[name="username"], input[type="text"]')
      .first()
      .fill(langflowAccount.username);
    await password.fill(langflowAccount.password);
    await Promise.all([
      page.waitForURL((url) => !url.pathname.endsWith("/login")),
      page.getByRole("button", { name: "Sign In", exact: true }).click(),
    ]);
  }
  const whoamiResponse = await context.request.get(
    `${config.langflowUrl}/api/v1/users/whoami`,
  );
  const whoami = {
    status: whoamiResponse.status(),
    body: await whoamiResponse.json(),
  };
  assert(whoami.status === 200, "Langflow browser session is not authenticated");
  assert(whoami.body.username === "100002", "Langflow Flow owner changed");
  return { context, page };
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

async function patchDescription(session, description) {
  const currentResponse = await session.context.request.get(
    `${config.langflowUrl}/api/v1/flows/${encodeURIComponent(flowId)}`,
  );
  const current = await currentResponse.json();
  if (!currentResponse.ok()) {
    return { status: currentResponse.status(), body: current };
  }
  const response = await session.context.request.patch(
    `${config.langflowUrl}/api/v1/flows/${encodeURIComponent(flowId)}`,
    {
      headers: { "Content-Type": "application/json" },
      data: {
        name: current.name,
        description,
        endpoint_name: current.endpoint_name,
        folder_id: current.folder_id,
        project_id: current.project_id,
        data: current.data,
      },
    },
  );
  return {
    status: response.status(),
    body: await response.json(),
    previous_description: current.description || "",
  };
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let langflowSession;
let ownerSession;
let callerSession;
let originalDescription = "";
try {
  langflowSession = await loginLangflow(browser);
  const driftMarker = `checksum drift validation ${Date.now()}`;
  const driftPatch = await patchDescription(langflowSession, driftMarker);
  assert(driftPatch.status === 200, `Langflow public PATCH returned ${driftPatch.status}`);
  originalDescription = driftPatch.previous_description;

  ownerSession = await loginBoi(browser, "100002");
  const reference = team.operator.deployment_reference;
  const flows = await sessionFetch(
    ownerSession.page,
    `/api/agent-playground/endpoints/${encodeURIComponent(reference.endpoint_connection_id)}`
      + `/projects/${encodeURIComponent(reference.project_id)}/flows`,
  );
  assert(flows.status === 200, "live Flow drift discovery failed");
  const driftedFlow = (flows.body.flows || []).find((item) => item.flow_id === flowId);
  assert(driftedFlow?.checksum_state === "drifted", "live checksum drift was not detected");
  const draftAttempt = await sessionFetch(
    ownerSession.page,
    `/api/agent-playground/deployments/${encodeURIComponent(deploymentId)}/action-draft`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "team", team_id: "aix-tf" }),
    },
  );
  assert(draftAttempt.status === 409, `drifted Action draft returned ${draftAttempt.status}`);

  let operatorStatus = "unexpected_success";
  try {
    execFileSync(
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
        team.registration.draft_id,
      ],
      { stdio: "pipe", timeout: 120_000 },
    );
  } catch {
    operatorStatus = "rejected";
  }
  assert(operatorStatus === "rejected", "operator accepted a drifted Flow");

  callerSession = await loginBoi(browser, "100001");
  const executionAttempt = await sessionFetch(
    callerSession.page,
    "/api/actions/invoke",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: team.action.action_key,
        event: {
          event_id: `evt-drift-${Date.now()}`,
          event_type: "agent.playground.requested.v1",
          trace_id: `trace-drift-${Date.now()}`,
        },
        payload: { question: "drifted Flow must not run", save_mode: "preview" },
        dry_run: false,
      }),
    },
  );
  assert(executionAttempt.status === 409, `drifted Action execution returned ${executionAttempt.status}`);
  result.drift = {
    registered_checksum: registeredChecksum,
    live_checksum: driftedFlow.live_checksum,
    flow_status: driftedFlow.validation_status,
    draft_status: draftAttempt.status,
    operator_status: operatorStatus,
    execution_status: executionAttempt.status,
  };

  const restored = await patchDescription(langflowSession, originalDescription);
  assert(restored.status === 200, "Langflow exact Flow restore failed");
  const revalidated = await sessionFetch(
    ownerSession.page,
    `/api/agent-playground/flows/${encodeURIComponent(flowId)}/validate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint_id: reference.endpoint_connection_id,
        project_id: reference.project_id,
        artifact_version: reference.artifact_version,
        artifact_checksum: registeredChecksum,
        task_ref: taskRef,
      }),
    },
  );
  assert(revalidated.status === 200, "restored Flow validation request failed");
  assert(
    revalidated.body.validation_status === "action_linked",
    `restored Flow did not preserve action_linked: ${revalidated.body.failure_reason}`,
  );
  assert(
    revalidated.body.artifact_checksum === registeredChecksum,
    "restored Flow checksum does not match the registered exact reference",
  );
  const executionRecovered = await sessionFetch(
    callerSession.page,
    "/api/actions/invoke",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_key: team.action.action_key,
        event: {
          event_id: `evt-drift-recovered-${Date.now()}`,
          event_type: "agent.playground.requested.v1",
          trace_id: `trace-drift-recovered-${Date.now()}`,
        },
        payload: { question: "restored exact Flow preview", save_mode: "preview" },
        dry_run: false,
      }),
    },
  );
  assert(executionRecovered.status === 200, "restored exact Action did not recover");
  assert(
    executionRecovered.body.status === "langflow_invoked",
    "restored exact Action did not invoke Langflow",
  );
  result.revalidation = {
    status: revalidated.body.validation_status,
    checksum: revalidated.body.artifact_checksum,
    same_exact_reference:
      revalidated.body.flow_id === flowId
      && revalidated.body.artifact_checksum === registeredChecksum,
    execution_status: executionRecovered.body.status,
  };
  await ownerSession.page.screenshot({
    path: path.join(config.evidenceDir, "01-restored-exact-flow-action-linked.png"),
    fullPage: true,
  });

  result.ok = (
    result.disconnected.validation_status === "blocked"
    && result.disconnected.failure_reason === "disconnected_component"
    && result.compose.public_patch_status === 200
    && result.compose.previous_checksum !== result.compose.live_checksum
    && result.compose.end_to_end_reachable === true
    && result.runtime.executed_component_ids.includes(result.runtime.component_id)
    && result.incompatible.status === "manual_required"
    && result.incompatible.reason === "component_contract_incompatible"
    && result.incompatible.patch_request_count === 0
    && result.incompatible.checksum_before === result.incompatible.checksum_after
    && result.drift.draft_status === 409
    && result.drift.operator_status === "rejected"
    && result.drift.execution_status === 409
    && result.revalidation.same_exact_reference === true
    && result.page_errors.length === 0
    && result.console_errors.length === 0
  );
  assert(result.ok, "component composition or drift evidence is incomplete");
} finally {
  if (originalDescription && langflowSession?.page) {
    await patchDescription(langflowSession, originalDescription).catch(() => {});
  }
  await langflowSession?.context.close().catch(() => {});
  await ownerSession?.context.close().catch(() => {});
  await callerSession?.context.close().catch(() => {});
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
