#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  employeeId: process.env.BOI_EMPLOYEE_ID || "100002",
  ssoPassword: process.env.BOI_SSO_PASSWORD || "",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  langflowUrl: process.env.LANGFLOW_URL || "http://localhost:7867",
  langflowCredentialFile:
    process.env.LANGFLOW_CREDENTIAL_FILE
    || "/tmp/boi-mainline-secrets/agenthub-key.json",
  langflowIdentityFile: process.env.LANGFLOW_IDENTITY_FILE || "",
  projectId: process.env.LANGFLOW_PROJECT_ID || "",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-model-incompatible",
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

async function langflowJson(method, pathname, apiKey, body) {
  const response = await fetch(`${config.langflowUrl}${pathname}`, {
    method,
    headers: {
      "x-api-key": apiKey,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  assert(response.ok, `Langflow ${method} ${pathname} returned HTTP ${response.status}`);
  return payload;
}

function nodeContains(node, marker) {
  return JSON.stringify(node).includes(marker);
}

async function createIncompatibleFlow(apiKey, runId) {
  const flows = await langflowJson("GET", "/api/v1/flows/", apiKey);
  const canonical = flows.find(
    (flow) =>
      flow.name === "BoI Wiki Agent Loop"
      && String(flow.folder_id || flow.project_id || "") === config.projectId,
  );
  assert(canonical, "canonical Flow is missing from the personal project");
  const source = await langflowJson(
    "GET",
    `/api/v1/flows/${encodeURIComponent(canonical.id)}`,
    apiKey,
  );
  const data = structuredClone(source.data || {});
  const removedIds = new Set(
    (data.nodes || [])
      .filter((node) => nodeContains(node, "BoIWikiSave"))
      .map((node) => String(node.id || "")),
  );
  assert(removedIds.size > 0, "incompatible fixture could not remove BoIWikiSave");
  data.nodes = (data.nodes || []).filter((node) => !removedIds.has(String(node.id || "")));
  data.edges = (data.edges || []).filter(
    (edge) =>
      !removedIds.has(String(edge.source || ""))
      && !removedIds.has(String(edge.target || "")),
  );
  const payload = {
    name: `BoI Wiki Agent Loop - Incompatible ${runId}`,
    description: "Validation-only Flow missing the required BoIWikiSave facade.",
    endpoint_name: `boi-wiki-agent-loop-incompatible-${runId.toLowerCase()}`,
    data,
    webhook: false,
    access_type: "PRIVATE",
    tags: ["boi", "agent-playground", "validation", "incompatible"],
    folder_id: config.projectId,
    project_id: config.projectId,
  };
  const created = await langflowJson("POST", "/api/v1/flows/", apiKey, payload);
  return {
    flow: created,
    checksum: sha256(JSON.stringify(payload)),
    removed_component: "BoIWikiSave",
  };
}

async function ensureModelFlow(apiKey) {
  const flows = await langflowJson("GET", "/api/v1/flows/", apiKey);
  const existing = flows.find(
    (flow) =>
      flow.name === "BoI Wiki Agent Loop - Model Agent Example"
      && String(flow.folder_id || flow.project_id || "") === config.projectId,
  );
  if (existing) return existing;
  const artifact = JSON.parse(
    await fs.readFile(
      path.resolve("langflow/flows/boi_wiki_agent_loop_model_agent.json"),
      "utf8",
    ),
  );
  return langflowJson("POST", "/api/v1/flows/", apiKey, {
    ...artifact,
    folder_id: config.projectId,
    project_id: config.projectId,
  });
}

async function api(page, method, pathname, body) {
  return page.evaluate(
    async ({ method: requestMethod, pathname: requestPath, body: requestBody }) => {
      const response = await fetch(requestPath, {
        method: requestMethod,
        headers: requestBody ? { "Content-Type": "application/json" } : {},
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch {
        payload = {};
      }
      return { status: response.status, body: payload };
    },
    { method, pathname, body },
  );
}

async function createActualTask(page, runId) {
  const traceId = `trace-model-agent-${runId}`;
  const eventId = `evt-model-agent-${runId}`;
  const response = await api(page, "POST", "/api/actions/invoke", {
    action_key: "manual.equipment.review_root_cause",
    event: {
      event_id: eventId,
      event_type: "root_cause.analysis.requested.v1",
      trace_id: traceId,
    },
    payload: {
      title: "Model Agent SOP context validation",
      equipment_id: "EQ-AP-MODEL-AGENT",
      owner: "100002",
    },
    dry_run: false,
  });
  assert(response.status === 200, `actual Task creation returned HTTP ${response.status}`);
  assert(response.body.status === "manual_required", "actual Task was not recorded");
  return {
    task_ref: `task:${response.body.request_id}`,
    trace_id: traceId,
    event_id: eventId,
  };
}

const credentialsDocument = process.env.LANGFLOW_API_KEY
  ? {}
  : JSON.parse(
    await fs.readFile(
      config.langflowIdentityFile || config.langflowCredentialFile,
      "utf8",
    ),
  );
const credentials = process.env.LANGFLOW_API_KEY
  ? { api_key: process.env.LANGFLOW_API_KEY }
  : (
    credentialsDocument.users?.[config.employeeId]
    || credentialsDocument.recovery_user
    || credentialsDocument
  );
const ssoIdentities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const ssoPassword = config.ssoPassword || String(ssoIdentities[config.employeeId] || "");
const apiKey = String(credentials.api_key || "");
assert(apiKey.length >= 16, "Langflow validation API Key is unavailable");
assert(config.projectId, "LANGFLOW_PROJECT_ID is required");
assert(ssoPassword, "BoI SSO validation password is required");

const runId =
  process.env.PLAYWRIGHT_RUN_ID
  || new Date().toISOString().replace(/\W/g, "").slice(0, 15);
await fs.mkdir(config.evidenceDir, { recursive: true });
const ensuredModelFlow = await ensureModelFlow(apiKey);
const incompatible = await createIncompatibleFlow(apiKey, runId);

const result = {
  ok: false,
  run_id: runId,
  oidc: {},
  model_flow: {},
  incompatible_flow: {},
  screenshots: [],
  expected_http_errors: [],
  unexpected_http_errors: [],
  console_errors: [],
  page_errors: [],
};

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
page.setDefaultTimeout(30_000);
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
page.on("response", (response) => {
  if (response.status() < 400) return;
  const url = new URL(response.url());
  const entry = {
    status: response.status(),
    method: response.request().method(),
    url: `${url.origin}${url.pathname}`,
  };
  if (
    entry.status === 409
    && entry.method === "POST"
    && /\/api\/agent-playground\/deployments\/.+\/action-draft$/.test(url.pathname)
  ) {
    result.expected_http_errors.push(entry);
  } else {
    result.unexpected_http_errors.push(entry);
  }
});

async function screenshot(name) {
  const target = path.join(config.evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

try {
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  assert(page.url().includes("/protocol/openid-connect/"), "BoI OIDC login did not start");
  const authorization = new URL(page.url());
  result.oidc = {
    state: Boolean(authorization.searchParams.get("state")),
    nonce: Boolean(authorization.searchParams.get("nonce")),
    pkce_s256: authorization.searchParams.get("code_challenge_method") === "S256",
  };
  assert(Object.values(result.oidc).every(Boolean), "OIDC+PKCE evidence is incomplete");
  await page.locator("#username").fill(config.employeeId);
  await page.locator("#password").fill(ssoPassword);
  await page.locator("#kc-login").click();
  await page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin);
  await page.locator("[data-agent-playground]").waitFor();

  const stateResponse = await api(page, "GET", "/api/agent-playground");
  assert(stateResponse.status === 200, "Playground state failed");
  assert(stateResponse.body.identity?.employee_id === config.employeeId, "OIDC Principal mismatch");
  assert(
    ["oidc", "keycloak"].includes(stateResponse.body.identity?.auth_source),
    "OIDC Principal was not used",
  );
  const endpoint = (stateResponse.body.endpoints || []).find(
    (item) => item.endpoint_id === stateResponse.body.default_endpoint_id,
  ) || (stateResponse.body.endpoints || []).find(
    (item) => {
      const candidates = [
        item.base_url,
        item.deploy_url,
        item.external_url,
        item.browser_url,
      ]
        .filter(Boolean)
        .map((value) => String(value).replace("host.docker.internal", "localhost").replace(/\/+$/, ""));
      return candidates.includes(config.langflowUrl.replace(/\/+$/, ""));
    },
  );
  assert(endpoint, "primary Langflow endpoint is missing from Playground");
  const flowsResponse = await api(
    page,
    "GET",
    `/api/agent-playground/endpoints/${endpoint.endpoint_id}/projects/${config.projectId}/flows`,
  );
  assert(flowsResponse.status === 200, "Playground live Flow discovery failed");
  const modelFlow = (flowsResponse.body.flows || []).find(
    (flow) => flow.id === ensuredModelFlow.id,
  );
  const incompatibleFlow = (flowsResponse.body.flows || []).find(
    (flow) => flow.id === incompatible.flow.id,
  );
  assert(modelFlow, "model Agent Flow was not rediscovered in the personal project");
  assert(incompatibleFlow, "incompatible Flow was not rediscovered in the personal project");

  const modelArtifact = await fs.readFile(
    path.resolve("langflow/flows/boi_wiki_agent_loop_model_agent.json"),
  );
  const modelDeployment = await api(page, "POST", "/api/agent-playground/deployments", {
    endpoint_id: endpoint.endpoint_id,
    project_id: config.projectId,
    flow_id: modelFlow.id,
    endpoint_name: "boi-wiki-agent-loop-model-agent",
    asset_version: "1.1.0-model-agent",
    artifact_checksum: sha256(modelArtifact),
  });
  assert(modelDeployment.status === 200, "model Flow deployment record failed");
  const incompatibleDeployment = await api(page, "POST", "/api/agent-playground/deployments", {
    endpoint_id: endpoint.endpoint_id,
    project_id: config.projectId,
    flow_id: incompatibleFlow.id,
    endpoint_name: incompatibleFlow.endpoint_name || "",
    asset_version: "1.1.0-incompatible",
    artifact_checksum: incompatible.checksum,
  });
  assert(incompatibleDeployment.status === 200, "incompatible Flow deployment record failed");

  await page.locator('[data-workbench-step="create"]').click();
  const filter = page.locator("[data-flow-filter]");
  await filter.fill("Model Agent Example");
  await page.getByText("BoI Wiki Agent Loop - Model Agent Example", { exact: true }).waitFor();
  await screenshot("01-model-flow-rediscovered");
  const actualTask = await createActualTask(page, runId);

  const modelValidation = await api(
    page,
    "POST",
    `/api/agent-playground/flows/${modelFlow.id}/validate`,
    {
      endpoint_id: endpoint.endpoint_id,
      project_id: config.projectId,
      artifact_version: "1.1.0-model-agent",
      artifact_checksum: sha256(modelArtifact),
      question: "Agent Playground와 BoI Wiki 연계 근거를 실제 모델로 정리해줘.",
      task_ref: actualTask.task_ref,
    },
  );
  assert(modelValidation.status === 200, `model validation returned HTTP ${modelValidation.status}`);
  assert(modelValidation.body.validation_status === "action_ready", modelValidation.body.failure_reason);
  const runtimeStage = (modelValidation.body.history || []).find(
    (item) => item.stage === "runtime_validated",
  );
  const taskStage = (modelValidation.body.history || []).find(
    (item) => item.stage === "task_validated",
  );
  assert(runtimeStage?.details?.model_inference?.fields?.real_inference === true, "real model inference missing");
  assert(runtimeStage?.details?.model_inference?.model === "google/gemma-4-26b-a4b-qat", "Gemma model mismatch");
  assert(taskStage?.status === "passed", "model SOP Task validation failed");
  result.model_flow = {
    flow_id: modelFlow.id,
    deployment_id: modelDeployment.body.deployment.deployment_id,
    validation_status: modelValidation.body.validation_status,
    artifact_checksum: modelValidation.body.artifact_checksum,
    model_inference: runtimeStage.details.model_inference,
    task_validation: taskStage.status,
    task_anchor: actualTask,
  };

  await filter.fill("Incompatible");
  await page.getByText(incompatibleFlow.name, { exact: true }).waitFor();
  await screenshot("02-incompatible-flow-rediscovered");
  const incompatibleValidation = await api(
    page,
    "POST",
    `/api/agent-playground/flows/${incompatibleFlow.id}/validate`,
    {
      endpoint_id: endpoint.endpoint_id,
      project_id: config.projectId,
      artifact_version: "1.1.0-incompatible",
      artifact_checksum: incompatible.checksum,
    },
  );
  assert(
    incompatibleValidation.status === 200
      && incompatibleValidation.body.validation_status === "blocked",
    "incompatible Flow was not blocked",
  );
  assert(
    String(incompatibleValidation.body.failure_reason || "").includes("BoIWikiSave"),
    "incompatible Flow failure reason does not identify BoIWikiSave",
  );
  const draftAttempt = await api(
    page,
    "POST",
    `/api/agent-playground/deployments/${incompatibleDeployment.body.deployment.deployment_id}/action-draft`,
    {},
  );
  assert(draftAttempt.status === 409, "blocked Flow Action registration was not rejected");
  result.incompatible_flow = {
    flow_id: incompatibleFlow.id,
    deployment_id: incompatibleDeployment.body.deployment.deployment_id,
    removed_component: incompatible.removed_component,
    validation_status: incompatibleValidation.body.validation_status,
    failure_reason: incompatibleValidation.body.failure_reason,
    action_draft_status: draftAttempt.status,
  };
  await screenshot("03-incompatible-action-blocked");

  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "browser diagnostics recorded unexpected errors");
} finally {
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "model-incompatible-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
