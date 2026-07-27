#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const priorEvidencePath =
  process.env.EXACT_CHAIN_EVIDENCE
  || path.join(
    repoRoot,
    "artifacts/agent-playground-handoff/universal-simulation-mcp-7b5e19be-final",
    "evidence/agent-hub-action/playwright-result.json",
  );
const outputDir =
  process.env.EXACT_CHAIN_EVIDENCE_DIR
  || path.join(
    repoRoot,
    "artifacts/agent-playground-handoff",
    `universal-simulation-exact-chain-${new Date().toISOString().replaceAll(/[:.]/g, "-")}`,
  );
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const baseUrl = process.env.BOI_BASE_URL || "http://localhost:28005";
const keycloakUrl = process.env.KEYCLOAK_URL || "http://localhost:18082";
const boiContainer =
  process.env.BOI_MAINLINE_CONTAINER
  || "boi-agent-playground-mainline-boi-api-1";
const employeeId = "100002";
const viewerId = "100003";
const priorEvidence = JSON.parse(await fs.readFile(priorEvidencePath, "utf8"));
const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const priorChain = priorEvidence.exact_chain || {};
const exactFlowId = String(priorChain.flow_id || "");
const deployment = priorChain.deployment_reference || {};
const endpointId = String(deployment.endpoint_connection_id || "");
const projectId = String(deployment.project_id || "");
const expectedChecksum = String(deployment.artifact_checksum || "");
const actionKey = String(priorChain.action_key || "");
const chainId = `universal-exact-${Date.now()}`;

for (const [name, value] of Object.entries({
  exactFlowId,
  endpointId,
  projectId,
  expectedChecksum,
  actionKey,
  ownerPassword: identities[employeeId],
})) {
  if (!String(value || "")) throw new Error(`${name} is required`);
}

await fs.mkdir(outputDir, { recursive: true });
const result = {
  ok: false,
  chain_id: chainId,
  exact_reference: {
    endpoint_id: endpointId,
    project_id: projectId,
    flow_id: exactFlowId,
    artifact_checksum: expectedChecksum,
    action_key: actionKey,
  },
  oidc: {},
  mcp: {},
  run_api: {},
  contract_comparison: {},
  caller_bound_save: {},
  action: {},
  no_sop_task: {},
  viewer: {},
  screenshots: [],
  unexpected: [],
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function decodeJsonStrings(value, depth = 0) {
  if (depth > 16) return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}"))
      || (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return decodeJsonStrings(JSON.parse(trimmed), depth + 1);
      } catch {
        return value;
      }
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => decodeJsonStrings(item, depth + 1));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        decodeJsonStrings(item, depth + 1),
      ]),
    );
  }
  return value;
}

function decodeMachineResults(value, found = []) {
  if (typeof value === "string") {
    const pattern = /BOI_RESULT_JSON_B64(?::|\s)+([A-Za-z0-9+/=]+)/g;
    for (const match of value.matchAll(pattern)) {
      try {
        found.push(
          JSON.parse(Buffer.from(match[1], "base64").toString("utf8")),
        );
      } catch {
        // A malformed contract must not mask the ordinary result traversal.
      }
    }
  } else if (Array.isArray(value)) {
    value.forEach((item) => decodeMachineResults(item, found));
  } else if (value && typeof value === "object") {
    Object.values(value).forEach((item) => decodeMachineResults(item, found));
  }
  return found;
}

function deepValues(value, key, found = []) {
  if (Array.isArray(value)) {
    value.forEach((item) => deepValues(item, key, found));
  } else if (value && typeof value === "object") {
    for (const [candidate, item] of Object.entries(value)) {
      if (candidate === key) found.push(item);
      deepValues(item, key, found);
    }
  }
  return found;
}

function contractData(payload) {
  const decoded = decodeJsonStrings(payload);
  const machineResults = decodeMachineResults(decoded);
  const candidates = [];
  const visit = (value) => {
    if (!value || typeof value !== "object") return;
    if (
      !Array.isArray(value)
      && Array.isArray(value.source_references)
      && Array.isArray(value.ontology_relationships)
      && value.task_context
      && typeof value.task_context === "object"
    ) {
      candidates.push(value);
    }
    for (const child of Array.isArray(value) ? value : Object.values(value)) {
      visit(child);
    }
  };
  visit(decoded);
  machineResults.forEach((item) => visit(item));
  const selected = (
    machineResults.find(
      (item) => item.schema_version === "boi.universal-simulation.result.v1",
    )
    || candidates.find((item) => item.simulation_label === "SIMULATED")
    || candidates.find((item) => item.draft_reference || item.save_status)
    || candidates.at(-1)
    || {}
  );
  const merged = { ...selected };
  const contractTree = [decoded, ...machineResults];
  const sourceArrays = deepValues(contractTree, "source_references").filter(Array.isArray);
  const ontologyArrays = deepValues(contractTree, "ontology_relationships").filter(Array.isArray);
  const taskContexts = deepValues(contractTree, "task_context").filter(
    (item) => item && typeof item === "object" && !Array.isArray(item),
  );
  merged.source_references = sourceArrays.sort((left, right) => right.length - left.length)[0]
    || merged.source_references
    || [];
  merged.ontology_relationships = ontologyArrays.sort(
    (left, right) => right.length - left.length,
  )[0] || merged.ontology_relationships || [];
  merged.task_context = taskContexts.find((item) => item.profile)
    || merged.task_context
    || {};
  for (const key of [
    "simulation_label",
    "real_system_called",
    "simulation_notice",
    "coverage_report",
    "draft_reference",
    "wiki_url",
    "save_status",
    "grounding_status",
    "provenance",
  ]) {
    if (merged[key] === undefined || merged[key] === "") {
      const values = deepValues(contractTree, key);
      const preferred = (
        key === "simulation_label"
          ? values.find((item) => item === "SIMULATED")
          : values.find((item) => item !== undefined && item !== "")
      );
      if (preferred !== undefined) merged[key] = preferred;
    }
  }
  const serialized = JSON.stringify(contractTree);
  if (!merged.simulation_label && /\bSIMULATED\b/.test(serialized)) {
    merged.simulation_label = "SIMULATED";
  }
  if (
    merged.real_system_called === undefined
    && /실제 시스템[^\\n]*(?:호출하지|미호출)|실제 시스템을 호출하지/.test(serialized)
  ) {
    merged.real_system_called = false;
  }
  return merged;
}

function modelTrace(payload) {
  const decoded = decodeJsonStrings(payload);
  return deepValues([decoded, ...decodeMachineResults(decoded)], "model_trace").find(
    (item) => item && typeof item === "object" && item.real_inference === true,
  ) || {};
}

function referenceKey(item) {
  if (!item || typeof item !== "object") return String(item || "");
  return String(
    item.ref
    || item.boi_id
    || item.doc_ref
    || item.source_id
    || item.url
    || item.title
    || "",
  );
}

function relationKey(item) {
  if (!item || typeof item !== "object") return String(item || "");
  return [
    item.source || item.source_id || item.from || "",
    item.relation || item.type || "",
    item.target || item.target_id || item.to || "",
  ].join("|");
}

function assertGroundedContract(
  data,
  label,
  expectedProfile,
  { evidenceRequired = true } = {},
) {
  assert(data.simulation_label === "SIMULATED", `${label} is not marked SIMULATED`);
  assert(
    data.real_system_called === false
      || /미호출|호출하지 않/i.test(String(data.simulation_notice || data.answer || "")),
    `${label} does not state that the real system was not called`,
  );
  const sourceCount = (data.source_references || []).length;
  const relationshipCount = (data.ontology_relationships || []).length;
  if (evidenceRequired) {
    assert(sourceCount > 0, `${label} has no Wiki sources`);
    assert(relationshipCount > 0, `${label} has no Ontology relationships`);
  } else if (sourceCount === 0 && relationshipCount === 0) {
    assert(
      data.grounding_status === "no_accessible_evidence",
      `${label} hid its lack of accessible evidence`,
    );
    assert(
      (data.coverage_report?.missing_context || []).includes(
        "source_or_ontology_evidence",
      ),
      `${label} did not report missing Wiki/Ontology evidence`,
    );
  }
  assert(
    (data.ontology_relationships || []).every(
      (item) => item && typeof item === "object" && item.provenance,
    ),
    `${label} contains an Ontology edge without provenance`,
  );
  assert(
    data.task_context?.profile === expectedProfile,
    `${label} profile is ${data.task_context?.profile}, expected ${expectedProfile}`,
  );
  if (expectedProfile !== "sop_task_execution") {
    assert(!data.task_context?.sop_ref, `${label} created a false SOP reference`);
  }
}

function assertModelTrace(trace, label) {
  assert(trace.real_inference === true, `${label} did not perform real inference`);
  assert(/gemma/i.test(String(trace.model || "")), `${label} did not use Gemma`);
  assert(trace.response_id, `${label} has no model response ID`);
  assert(Number(trace.latency_ms) > 0, `${label} has no model latency`);
  assert(Number(trace.usage?.total_tokens) > 0, `${label} has no model usage`);
}

async function privateFiles(owner) {
  try {
    const { stdout } = await execFileAsync(
      "docker",
      [
        "exec",
        boiContainer,
        "find",
        `/content/private/${owner}`,
        "-type",
        "f",
        "-name",
        "*.md",
      ],
      { maxBuffer: 1024 * 1024 },
    );
    return stdout.split(/\r?\n/).filter(Boolean).sort();
  } catch {
    return [];
  }
}

function monitor(page, label) {
  page.on("pageerror", (error) => {
    result.unexpected.push({ label, kind: "pageerror", message: error.message });
  });
  page.on("console", (message) => {
    const text = message.text();
    if (
      message.type() === "error"
      && !text.includes("favicon")
      && !text.startsWith("Failed to load resource:")
    ) {
      result.unexpected.push({ label, kind: "console", message: text.slice(0, 500) });
    }
  });
  page.on("response", (response) => {
    if (
      response.status() >= 400
      && !response.url().includes("/favicon")
      && !(label === "viewer" && response.status() === 403)
    ) {
      const url = new URL(response.url());
      result.unexpected.push({
        label,
        kind: "http",
        status: response.status(),
        url: `${url.origin}${url.pathname}`,
      });
    }
  });
}

async function login(context, user, label) {
  const page = await context.newPage();
  monitor(page, label);
  await page.goto(`${baseUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    const authorization = new URL(page.url());
    if (user === employeeId) {
      result.oidc = {
        employee_id: user,
        state: Boolean(authorization.searchParams.get("state")),
        nonce: Boolean(authorization.searchParams.get("nonce")),
        pkce_s256: authorization.searchParams.get("code_challenge_method") === "S256",
      };
    }
    await page.locator("#username").fill(user);
    await page.locator("#password").fill(String(identities[user]));
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(baseUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor({
    state: "visible",
    timeout: 30_000,
  });
  const identity = await fetchJson(page, "/api/auth/me");
  assert(identity.status === 200, `${user} identity lookup failed`);
  assert(identity.body.employee_id === user, `${user} OIDC identity mismatch`);
  return page;
}

async function fetchJson(page, pathname, options = {}) {
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
  return fetchJson(page, pathname, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function invokeAction(page, payload) {
  return postJson(page, "/api/actions/invoke", payload);
}

async function resetViewerPassword() {
  const password = crypto.randomBytes(24).toString("base64url");
  const tokenResponse = await fetch(
    `${keycloakUrl}/realms/master/protocol/openid-connect/token`,
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
    `${keycloakUrl}/admin/realms/boi-validation/users?username=${viewerId}&exact=true`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  assert(usersResponse.ok, `Keycloak viewer lookup returned ${usersResponse.status}`);
  const user = (await usersResponse.json())[0];
  assert(user?.id, `Keycloak ${viewerId} fixture is missing`);
  const resetResponse = await fetch(
    `${keycloakUrl}/admin/realms/boi-validation/users/${user.id}/reset-password`,
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

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let failure;
try {
  const ownerContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await login(ownerContext, employeeId, "exact-chain-owner");
  const stateResponse = await fetchJson(page, "/api/agent-playground");
  assert(stateResponse.status === 200, "Playground state lookup failed");
  const state = stateResponse.body;
  const storedDeployment = (state.deployments || []).find(
    (item) => item.flow_id === exactFlowId,
  );
  assert(storedDeployment, "exact Agent Hub deployment is not in Playground state");
  assert(
    storedDeployment.artifact_checksum === expectedChecksum,
    "stored Agent Hub deployment checksum changed",
  );

  const flowsResponse = await fetchJson(
    page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}/flows`,
  );
  assert(flowsResponse.status === 200, "live Flow lookup failed");
  const liveFlow = (flowsResponse.body.flows || []).find(
    (item) => item.flow_id === exactFlowId,
  );
  assert(liveFlow, "exact Agent Hub Flow was not rediscovered live");
  assert(liveFlow.checksum_state === "matched", "exact Flow checksum is not matched");
  assert(liveFlow.live_checksum === expectedChecksum, "live exact Flow checksum changed");

  const enableMcp = await fetchJson(
    page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}`
      + `/flows/${encodeURIComponent(exactFlowId)}/mcp`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: true,
        action_name: "boi_universal_simulate",
        action_description: (
          "Wiki·Ontology와 선택한 Task 맥락으로 실제 시스템을 호출하지 않는 "
          + "업무 시뮬레이션과 초안 후보를 만듭니다."
        ),
        auth_type: "apikey",
      }),
    },
  );
  assert(enableMcp.status === 200, `MCP enable returned ${enableMcp.status}`);
  assert(enableMcp.body.status === "available", "exact Flow MCP is not available");

  const question = `설비 이상 판단에 필요한 Wiki·Ontology 근거와 예상 결과를 정리해줘. ${chainId}`;
  const beforeMcpPrivate = await privateFiles(employeeId);
  const mcpPreview = await postJson(
    page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}`
      + `/flows/${encodeURIComponent(exactFlowId)}/mcp/test`,
    { question, save_mode: "preview" },
  );
  assert(mcpPreview.status === 200, `MCP preview returned ${mcpPreview.status}`);
  assert(mcpPreview.body.flow_id === exactFlowId, "MCP preview used another Flow");
  const mcpTools = mcpPreview.body.result?.tools || [];
  const representativeTools = mcpTools.filter(
    (item) => item.name === "boi_universal_simulate",
  );
  assert(
    representativeTools.length === 1,
    "MCP list_tools did not expose exactly one boi_universal_simulate tool",
  );
  const representativeTool = representativeTools[0];
  assert(
    representativeTool.input_schema?.type === "object"
      && Object.hasOwn(representativeTool.input_schema?.properties || {}, "input_value"),
    "MCP natural-language input schema is invalid",
  );
  const mcpData = contractData(mcpPreview.body.result);
  const mcpTrace = modelTrace(mcpPreview.body.result);
  assert(
    mcpData.schema_version === "boi.universal-simulation.result.v1",
    "MCP response did not preserve the versioned structured result contract",
  );
  assertGroundedContract(mcpData, "MCP preview", "knowledge_lookup");
  assertModelTrace(mcpTrace, "MCP preview");

  const forcedPrivate = await postJson(
    page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}`
      + `/flows/${encodeURIComponent(exactFlowId)}/mcp/test`,
    { question, save_mode: "private_draft" },
  );
  assert(forcedPrivate.status === 200, `forced MCP private draft returned ${forcedPrivate.status}`);
  assert(forcedPrivate.body.write_allowed === false, "MCP write was unexpectedly allowed");
  assert(forcedPrivate.body.write_blocked === true, "MCP private draft was not blocked");
  const forcedData = contractData(forcedPrivate.body.result);
  assert(!forcedData.draft_reference, "MCP private draft returned a draft reference");
  const afterMcpPrivate = await privateFiles(employeeId);
  assert(
    JSON.stringify(afterMcpPrivate) === JSON.stringify(beforeMcpPrivate),
    "MCP private_draft mutated the Wiki",
  );

  const runPreview = await postJson(
    page,
    `/api/agent-playground/flows/${encodeURIComponent(exactFlowId)}/test`,
    {
      endpoint_id: endpointId,
      project_id: projectId,
      question,
      business_context: `single exact Flow comparison ${chainId}`,
      save_mode: "preview",
      title: "Universal exact Flow preview",
    },
  );
  assert(runPreview.status === 200, `/api/v1/run preview returned ${runPreview.status}`);
  assert(runPreview.body.flow_id === exactFlowId, "/api/v1/run used another Flow");
  const runData = contractData(runPreview.body.result);
  const runTrace = modelTrace(runPreview.body.result);
  assertGroundedContract(runData, "/api/v1/run preview", "knowledge_lookup");
  assertModelTrace(runTrace, "/api/v1/run preview");

  const mcpSourceKeys = new Set((mcpData.source_references || []).map(referenceKey));
  const runSourceKeys = new Set((runData.source_references || []).map(referenceKey));
  const commonSources = [...mcpSourceKeys].filter((item) => item && runSourceKeys.has(item));
  const mcpRelationKeys = new Set((mcpData.ontology_relationships || []).map(relationKey));
  const runRelationKeys = new Set((runData.ontology_relationships || []).map(relationKey));
  const commonRelations = [...mcpRelationKeys].filter(
    (item) => item && runRelationKeys.has(item),
  );
  assert(commonSources.length > 0, "MCP and /api/v1/run do not share source references");
  assert(commonRelations.length > 0, "MCP and /api/v1/run do not share Ontology relationships");

  const beforePlaygroundSave = await privateFiles(employeeId);
  const playgroundPrivate = await postJson(
    page,
    `/api/agent-playground/flows/${encodeURIComponent(exactFlowId)}/test`,
    {
      endpoint_id: endpointId,
      project_id: projectId,
      question: `검증 결과를 호출자 개인 초안으로 저장해줘. ${chainId}`,
      business_context: `caller-bound Playground save ${chainId}`,
      save_mode: "private_draft",
      title: `Universal exact Playground draft ${chainId}`,
    },
  );
  assert(
    playgroundPrivate.status === 200,
    `caller-bound Playground private draft returned ${playgroundPrivate.status}`,
  );
  const playgroundPrivateData = contractData(playgroundPrivate.body.result);
  assert(
    String(playgroundPrivateData.draft_reference || "").startsWith("boi:private:100002:"),
    "Playground run token did not create a caller-owned private draft",
  );
  const afterPlaygroundSave = await privateFiles(employeeId);
  assert(
    afterPlaygroundSave.length === beforePlaygroundSave.length + 1,
    "Playground private draft did not create exactly one Wiki document",
  );

  const generalAction = await invokeAction(page, {
    action_key: actionKey,
    payload: {
      question: `일반 Wiki 질문의 근거와 예상 결과를 정리해줘. ${chainId}`,
      business_context: `SOP 없는 일반 질문 ${chainId}`,
      save_mode: "preview",
      title: "Universal exact Action general",
    },
    dry_run: false,
  });
  assert(generalAction.status === 200, `general Action returned ${generalAction.status}`);
  assert(generalAction.body.flow_id === exactFlowId, "general Action used another Flow");
  const generalData = contractData(generalAction.body);
  assertGroundedContract(generalData, "general Action", "knowledge_lookup");

  const inbox = await fetchJson(page, "/api/inbox?limit=100");
  assert(inbox.status === 200, "Task inbox lookup failed");
  const sopTaskRef = (inbox.body.items || [])
    .map((item) => String(item.task_id || ""))
    .find((item) => item.startsWith("task:"));
  assert(sopTaskRef, "no actual SOP Task is available");
  const sopAction = await invokeAction(page, {
    action_key: actionKey,
    payload: {
      question: `선택한 SOP Task의 Stage·Event·Action과 선행 결과를 정리해줘. ${chainId}`,
      business_context: `actual SOP Task ${chainId}`,
      task_ref: sopTaskRef,
      save_mode: "preview",
      title: "Universal exact Action SOP",
    },
    dry_run: false,
  });
  assert(sopAction.status === 200, `SOP Action returned ${sopAction.status}`);
  assert(sopAction.body.flow_id === exactFlowId, "SOP Action used another Flow");
  const sopData = contractData(sopAction.body);
  assertGroundedContract(sopData, "SOP Action", "sop_task_execution");
  for (const key of ["task_ref", "sop_ref", "sop_stage", "event_ref", "action_ref"]) {
    assert(sopData.task_context?.[key], `SOP Action is missing ${key}`);
  }
  assert(
    Array.isArray(sopData.task_context?.prior_results),
    "SOP Action did not preserve prior results",
  );

  const adHocTraceId = `${chainId}-manual-task`;
  const adHocRequest = await invokeAction(page, {
    action_key: "manual.equipment.confirm_alarm_context",
    payload: {
      title: `SOP 없는 임시 검토 Task ${chainId}`,
      trace_id: adHocTraceId,
    },
    dry_run: false,
  });
  assert(adHocRequest.status === 200, `ad-hoc Task creation returned ${adHocRequest.status}`);
  const adHocTaskRef = `task:${adHocRequest.body.request_id}`;
  const adHocAction = await invokeAction(page, {
    action_key: actionKey,
    payload: {
      question: `SOP 없는 임시 검토 Task의 업무 맥락을 정리해줘. ${chainId}`,
      business_context: `actual non-SOP manual Task ${chainId}`,
      task_ref: adHocTaskRef,
      save_mode: "preview",
      title: "Universal exact Action ad-hoc Task",
    },
    dry_run: false,
  });
  assert(adHocAction.status === 200, `ad-hoc Task Action returned ${adHocAction.status}`);
  const adHocData = contractData(adHocAction.body);
  assertGroundedContract(
    adHocData,
    "SOP-free Task Action",
    "task_execution",
    { evidenceRequired: false },
  );
  assertModelTrace(modelTrace(adHocAction.body), "SOP-free Task Action");
  assert(adHocData.task_context?.task_ref === adHocTaskRef, "ad-hoc Task anchor changed");
  assert(!adHocData.task_context?.sop_ref, "ad-hoc Task received a false SOP");

  const beforeActionSave = await privateFiles(employeeId);
  const privateAction = await invokeAction(page, {
    action_key: actionKey,
    payload: {
      question: `SOP Task 결과를 호출자 개인 초안으로 저장해줘. ${chainId}`,
      business_context: `caller-bound Action save ${chainId}`,
      task_ref: sopTaskRef,
      save_mode: "private_draft",
      title: `Universal exact Action draft ${chainId}`,
    },
    dry_run: false,
  });
  assert(privateAction.status === 200, `private Action returned ${privateAction.status}`);
  assert(privateAction.body.flow_id === exactFlowId, "private Action used another Flow");
  const privateActionData = contractData(privateAction.body);
  assert(
    String(privateActionData.draft_reference || "").startsWith("boi:private:100002:"),
    "Action run token did not create a caller-owned private draft",
  );
  const afterActionSave = await privateFiles(employeeId);
  assert(
    afterActionSave.length === beforeActionSave.length + 1,
    "Action private draft did not create exactly one Wiki document",
  );
  const draftCatalog = await fetchJson(
    page,
    "/api/boi?visibility=private&include_generated=true&limit=200",
  );
  assert(draftCatalog.status === 200, "private Wiki catalog lookup failed");
  const savedDraft = (draftCatalog.body.items || []).find(
    (item) => (
      String(item.metadata?.boi_id || item.boi_id || "")
      === privateActionData.draft_reference
    ),
  );
  assert(savedDraft, "caller-owned private draft is not visible to its owner");
  const savedText = JSON.stringify(savedDraft);
  assert(
    /source_refs|source_references/i.test(savedText),
    "saved Wiki draft lost source references",
  );
  assert(/provenance/i.test(savedText), "saved Wiki draft lost provenance");

  await page.goto(
    `${baseUrl}/playground?stage=test&endpoint_id=${encodeURIComponent(endpointId)}`
      + `&project_id=${encodeURIComponent(projectId)}&flow_id=${encodeURIComponent(exactFlowId)}`,
    { waitUntil: "domcontentloaded" },
  );
  await page.locator("[data-agent-playground]").waitFor({ state: "visible" });
  const desktopShot = path.join(outputDir, "01-exact-flow-playground.png");
  await page.screenshot({ path: desktopShot, fullPage: true });
  result.screenshots.push(desktopShot);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const width = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
  }));
  assert(width.body <= width.viewport + 1, "390px Playground has horizontal page overflow");
  const mobileShot = path.join(outputDir, "02-exact-flow-playground-mobile.png");
  await page.screenshot({ path: mobileShot, fullPage: true });
  result.screenshots.push(mobileShot);
  await ownerContext.close();

  const viewerContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  identities[viewerId] = await resetViewerPassword();
  const viewerPage = await login(viewerContext, viewerId, "viewer");
  const viewerInvoke = await invokeAction(viewerPage, {
    action_key: actionKey,
    payload: {
      question: "조회 전용 사용자의 private draft 차단 확인",
      save_mode: "private_draft",
      title: "must not be created",
    },
    dry_run: false,
  });
  assert(viewerInvoke.status === 403, `viewer Action returned ${viewerInvoke.status}`);
  result.viewer = {
    employee_id: viewerId,
    action_status: viewerInvoke.status,
    private_draft_status: viewerInvoke.status,
  };
  await viewerContext.close();

  result.mcp = {
    flow_id: mcpPreview.body.flow_id,
    tool_name: representativeTool.name,
    result_schema_version: mcpData.schema_version,
    representative_tool_count: representativeTools.length,
    project_tool_count: mcpTools.length,
    schema: representativeTool.input_schema,
    model_trace: {
      model: mcpTrace.model,
      response_id: mcpTrace.response_id,
      latency_ms: mcpTrace.latency_ms,
      usage: mcpTrace.usage,
    },
    forced_private_draft: {
      write_allowed: forcedPrivate.body.write_allowed,
      write_blocked: forcedPrivate.body.write_blocked,
      wiki_files_before: beforeMcpPrivate.length,
      wiki_files_after: afterMcpPrivate.length,
    },
  };
  result.run_api = {
    flow_id: runPreview.body.flow_id,
    model_trace: {
      model: runTrace.model,
      response_id: runTrace.response_id,
      latency_ms: runTrace.latency_ms,
      usage: runTrace.usage,
    },
    grounding_status: runData.grounding_status,
    source_reference_count: runData.source_references.length,
    ontology_relationship_count: runData.ontology_relationships.length,
  };
  result.contract_comparison = {
    exact_flow_id: exactFlowId,
    mcp_profile: mcpData.task_context.profile,
    run_profile: runData.task_context.profile,
    simulation_label: "SIMULATED",
    common_source_references: commonSources.length,
    common_ontology_relationships: commonRelations.length,
    fields: [
      "simulation_label",
      "answer",
      "coverage_report",
      "task_context",
      "source_references",
      "ontology_relationships",
      "grounding_status",
      "model_trace",
      "draft_reference",
      "wiki_url",
      "provenance",
    ],
  };
  result.caller_bound_save = {
    playground: {
      draft_reference: playgroundPrivateData.draft_reference,
      owner_employee_id: employeeId,
      created_file_count: afterPlaygroundSave.length - beforePlaygroundSave.length,
    },
    action: {
      draft_reference: privateActionData.draft_reference,
      owner_employee_id: employeeId,
      created_file_count: afterActionSave.length - beforeActionSave.length,
      source_references_preserved: true,
      provenance_preserved: true,
    },
  };
  result.action = {
    exact_flow_id: exactFlowId,
    action_key: actionKey,
    general: {
      request_id: generalAction.body.request_id,
      trace_id: generalData.provenance?.trace_id || "",
      profile: generalData.task_context.profile,
    },
    sop: {
      request_id: sopAction.body.request_id,
      trace_id: sopData.provenance?.trace_id || "",
      task_context: sopData.task_context,
    },
    private_draft: {
      request_id: privateAction.body.request_id,
      trace_id: privateActionData.provenance?.trace_id || "",
      draft_reference: privateActionData.draft_reference,
    },
  };
  result.no_sop_task = {
    task_ref: adHocTaskRef,
    request_id: adHocAction.body.request_id,
    trace_id: adHocData.provenance?.trace_id || "",
    profile: adHocData.task_context.profile,
    sop_ref: adHocData.task_context.sop_ref || "",
  };
  assert(result.unexpected.length === 0, `unexpected browser errors: ${JSON.stringify(result.unexpected)}`);
  result.ok = true;
} catch (error) {
  failure = error;
  result.error = String(error.stack || error.message || error);
} finally {
  await browser.close();
  await fs.writeFile(
    path.join(outputDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, output_dir: outputDir, chain_id: chainId }));
if (failure) throw failure;
