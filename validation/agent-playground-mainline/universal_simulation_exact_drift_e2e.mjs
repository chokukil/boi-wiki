#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const evidencePath = process.env.EXACT_CHAIN_EVIDENCE;
const outputDir = process.env.EXACT_DRIFT_EVIDENCE_DIR;
const boiUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const langflowUrl = process.env.LANGFLOW_URL || "http://localhost:7867";
const boiIdentityFile =
  process.env.AGENT_HUB_IDENTITY_FILE || "/tmp/boi-ap-agent-hub-sso-users.json";
const langflowIdentityFile =
  process.env.LANGFLOW_IDENTITY_FILE
  || "/tmp/boi-ap-ux-final-langflow-users-20260727.json";

if (!evidencePath || !outputDir) {
  throw new Error("EXACT_CHAIN_EVIDENCE and EXACT_DRIFT_EVIDENCE_DIR are required");
}

const evidence = JSON.parse(await fs.readFile(evidencePath, "utf8"));
const identities = JSON.parse(await fs.readFile(boiIdentityFile, "utf8"));
const langflowIdentities = JSON.parse(await fs.readFile(langflowIdentityFile, "utf8"));
const chain = evidence.exact_chain || {};
const reference = chain.deployment_reference || {};
const flowId = String(chain.flow_id || "");
const actionKey = String(chain.action_key || "");
const endpointId = String(reference.endpoint_connection_id || "");
const projectId = String(reference.project_id || "");
const deploymentId = String(reference.deployment_id || "");
const registeredChecksum = String(reference.artifact_checksum || "");
const taskRef = String(
  chain.execution?.sop_execution?.task_context?.task_ref
  || chain.execution?.private_draft_execution?.task_context?.task_ref
  || "",
);
const langflowAccount = langflowIdentities.users?.["100002"] || {};

for (const [name, value] of Object.entries({
  flowId,
  actionKey,
  endpointId,
  projectId,
  deploymentId,
  registeredChecksum,
  taskRef,
  boiPassword: identities["100002"],
  langflowUsername: langflowAccount.username,
  langflowPassword: langflowAccount.password,
})) {
  if (!String(value || "")) throw new Error(`${name} is required`);
}

await fs.mkdir(outputDir, { recursive: true });
const result = {
  ok: false,
  exact_reference: {
    endpoint_id: endpointId,
    project_id: projectId,
    deployment_id: deploymentId,
    flow_id: flowId,
    checksum: registeredChecksum,
    action_key: actionKey,
  },
  drift: {},
  recovery: {},
  ignored: [],
  unexpected: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function monitor(page, scope) {
  page.on("pageerror", (error) => {
    result.unexpected.push({ scope, kind: "pageerror", message: error.message });
  });
  page.on("console", (message) => {
    if (
      message.type() === "error"
      && message.text().startsWith("Duplicate request:")
    ) {
      result.ignored.push({
        scope,
        kind: "console",
        reason: "unmodified Langflow frontend duplicate-request guard",
        message: message.text().slice(0, 500),
      });
      return;
    }
    if (
      message.type() === "error"
      && !message.text().startsWith("Failed to load resource:")
      && !message.text().includes("favicon")
    ) {
      result.unexpected.push({
        scope,
        kind: "console",
        message: message.text().slice(0, 500),
      });
    }
  });
}

async function loginBoi(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  monitor(page, "boi-owner");
  await page.goto(`${boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    await page.locator("#username").fill("100002");
    await page.locator("#password").fill(String(identities["100002"]));
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  return { context, page };
}

async function loginLangflow(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  monitor(page, "langflow-owner");
  await page.goto(`${langflowUrl}/flow/${flowId}`, { waitUntil: "domcontentloaded" });
  const password = page.locator('input[type="password"]');
  await password.waitFor({ state: "visible", timeout: 8_000 }).catch(() => null);
  if (await password.isVisible().catch(() => false)) {
    await page.locator('input[name="username"], input[type="text"]').first()
      .fill(String(langflowAccount.username));
    await password.fill(String(langflowAccount.password));
    await Promise.all([
      page.waitForURL((url) => !url.pathname.endsWith("/login")),
      page.getByRole("button", { name: "Sign In", exact: true }).click(),
    ]);
  }
  const whoami = await context.request.get(`${langflowUrl}/api/v1/users/whoami`);
  assert(whoami.status() === 200, "Langflow browser session is not authenticated");
  assert((await whoami.json()).username === "100002", "Langflow owner changed");
  return { context, page };
}

async function patchDescription(session, description) {
  const currentResponse = await session.context.request.get(
    `${langflowUrl}/api/v1/flows/${encodeURIComponent(flowId)}`,
  );
  const current = await currentResponse.json();
  assert(currentResponse.status() === 200, "exact Flow GET failed");
  const response = await session.context.request.patch(
    `${langflowUrl}/api/v1/flows/${encodeURIComponent(flowId)}`,
    {
      headers: { "Content-Type": "application/json" },
      data: {
        name: current.name,
        description,
        endpoint_name: current.endpoint_name,
        folder_id: current.folder_id,
        project_id: current.project_id,
        data: current.data,
        mcp_enabled: current.mcp_enabled,
        action_name: current.action_name,
        action_description: current.action_description,
      },
    },
  );
  return {
    status: response.status(),
    previousDescription: String(current.description || ""),
  };
}

async function sessionJson(page, pathname, options = {}) {
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

async function postJson(page, pathname, body) {
  return sessionJson(page, pathname, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let langflowSession;
let boiSession;
let originalDescription = "";
let failure;
try {
  langflowSession = await loginLangflow(browser);
  const patched = await patchDescription(
    langflowSession,
    `Universal Simulation MCP drift proof ${Date.now()}`,
  );
  assert(patched.status === 200, `Langflow PATCH returned ${patched.status}`);
  originalDescription = patched.previousDescription;

  boiSession = await loginBoi(browser);
  const mcpAttempt = await postJson(
    boiSession.page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}`
      + `/flows/${encodeURIComponent(flowId)}/mcp/test`,
    { question: "drifted MCP Flow must not run", save_mode: "preview" },
  );
  assert(mcpAttempt.status === 409, `drifted MCP test returned ${mcpAttempt.status}`);
  assert(
    mcpAttempt.body?.detail?.code === "flow_checksum_drift",
    "MCP drift response did not identify checksum drift",
  );

  const actionAttempt = await postJson(boiSession.page, "/api/actions/invoke", {
    action_key: actionKey,
    payload: { question: "drifted Action must not run", save_mode: "preview" },
    dry_run: false,
  });
  assert(actionAttempt.status === 409, `drifted Action returned ${actionAttempt.status}`);
  result.drift = {
    mcp_status: mcpAttempt.status,
    mcp_code: mcpAttempt.body.detail.code,
    action_status: actionAttempt.status,
  };

  const restored = await patchDescription(langflowSession, originalDescription);
  assert(restored.status === 200, "exact Flow restore failed");
  const revalidated = await postJson(
    boiSession.page,
    `/api/agent-playground/flows/${encodeURIComponent(flowId)}/validate`,
    {
      endpoint_id: endpointId,
      project_id: projectId,
      artifact_version: reference.artifact_version || "1.0.0",
      artifact_checksum: registeredChecksum,
      task_ref: taskRef,
    },
  );
  assert(revalidated.status === 200, `restored validation returned ${revalidated.status}`);
  assert(
    revalidated.body.artifact_checksum === registeredChecksum,
    "restored Flow checksum changed",
  );
  let recovered = {};
  const recoveryAttempts = [];
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    recovered = await postJson(boiSession.page, "/api/actions/invoke", {
      action_key: actionKey,
      payload: { question: "restored exact Flow preview", save_mode: "preview" },
      dry_run: false,
    });
    recoveryAttempts.push({
      attempt,
      status: recovered.status,
      detail: String(
        recovered.body?.detail?.code
        || recovered.body?.detail
        || recovered.body?.status
        || "",
      ).slice(0, 200),
    });
    if (recovered.status === 200 || recovered.status !== 503) break;
    await boiSession.page.waitForTimeout(1500);
  }
  assert(recovered.status === 200, `restored Action returned ${recovered.status}`);
  assert(recovered.body.flow_id === flowId, "restored Action used another Flow");
  result.recovery = {
    validation_status: revalidated.body.validation_status,
    checksum: revalidated.body.artifact_checksum,
    action_status: recovered.body.status,
    flow_id: recovered.body.flow_id,
    attempts: recoveryAttempts,
  };
  await boiSession.page.screenshot({
    path: path.join(outputDir, "01-exact-flow-restored.png"),
    fullPage: true,
  });
  assert(result.unexpected.length === 0, "unexpected browser errors occurred");
  result.ok = true;
} catch (error) {
  failure = error;
  result.error = String(error.stack || error.message || error);
} finally {
  if (originalDescription && langflowSession) {
    await patchDescription(langflowSession, originalDescription).catch(() => {});
  }
  await langflowSession?.context.close().catch(() => {});
  await boiSession?.context.close().catch(() => {});
  await browser.close();
  await fs.writeFile(
    path.join(outputDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, output_dir: outputDir, flow_id: flowId }));
if (failure) throw failure;
