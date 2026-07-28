#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import crypto from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  agentHubUrl:
    process.env.AGENT_HUB_URL || "http://localhost:18080/AgentHub.html",
  langflowContainerUrl:
    process.env.LANGFLOW_CONTAINER_URL || "http://localhost:7867",
  langflowUrl: process.env.LANGFLOW_URL || "http://localhost:7867",
  langflowIdentityFile:
    process.env.LANGFLOW_IDENTITY_FILE
    || "/tmp/boi-ap-ux-final-langflow-users-20260727.json",
  incompatibleComponentFile:
    process.env.INCOMPATIBLE_COMPONENT_FILE
    || "validation/agent-playground/assets/incompatible_agent_slot.py",
  identityFile:
    process.env.AGENT_HUB_IDENTITY_FILE
    || "/tmp/boi-ap-agent-hub-sso-users.json",
  teamResult:
    process.env.TEAM_ACTION_RESULT
    || "artifacts/agent-playground-current/browser/team-action-execution/result.json",
  evidenceDir:
    process.env.PLAYWRIGHT_EVIDENCE_DIR
    || "artifacts/agent-playground-current/browser/incompatible-component",
};

const identities = JSON.parse(await fs.readFile(config.identityFile, "utf8"));
const langflowIdentities = JSON.parse(
  await fs.readFile(config.langflowIdentityFile, "utf8"),
);
const storedLangflowAccount = langflowIdentities.users?.["100002"] || {};
const langflowAccount = {
  ...storedLangflowAccount,
  api_key: process.env.LANGFLOW_API_KEY || storedLangflowAccount.api_key || "",
};
const team = JSON.parse(await fs.readFile(config.teamResult, "utf8"));
const endpointId = String(team.operator?.deployment_reference?.endpoint_connection_id || "");
const projectId = String(team.operator?.deployment_reference?.project_id || "");
const activeFlowId = String(team.operator?.deployment_reference?.flow_id || "");
if (
  !identities["100001"]
  || !identities["100002"]
  || !identities["2074795"]
  || !langflowAccount?.api_key
  || !endpointId
  || !projectId
  || !activeFlowId
) {
  throw new Error("incompatible component fixture is incomplete");
}
await fs.mkdir(config.evidenceDir, { recursive: true });
const runId = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
const componentTitle = `Incompatible Agent Slot ${runId}`;

const result = {
  ok: false,
  asset: {},
  deployment: {},
  compose: {},
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
      && !text.startsWith("Failed to load resource:")
      && !text.includes("favicon")
      && !text.startsWith("Duplicate request:")
    ) {
      if (text.startsWith("Failed to load components: TypeError: Failed to fetch")) {
        result.ignored_console_errors.push({
          scope,
          text,
          reason: "immutable Agent Hub optional component lookup during auth bootstrap",
        });
      } else {
        result.console_errors.push({ scope, text });
      }
    }
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    const expected = (
      response.status() === 403
      && (
        url.pathname === "/api/v1/auto_login"
        || (
          response.request().method() === "GET"
          && ["/api/v1/users/me", "/api/v1/admin/settings"].includes(url.pathname)
        )
      )
    );
    if (!expected) {
      result.unexpected_http_errors.push({
        scope,
        status: response.status(),
        method: response.request().method(),
        url: `${url.origin}${url.pathname}`,
      });
    }
  });
}

async function loginBoi(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "boi-100002");
  await page.goto(`${config.boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/")) {
    await page.locator("#username").fill("100002");
    await page.locator("#password").fill(identities["100002"]);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.boiUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.locator("[data-agent-playground]").waitFor();
  return { context, page };
}

async function loginAgentHub(browser, employeeId) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, `agent-hub-${employeeId}`);
  await page.goto(config.agentHubUrl, { waitUntil: "domcontentloaded" });
  const username = page.locator("#username");
  await Promise.race([
    username.waitFor({ state: "visible", timeout: 20_000 }).catch(() => null),
    page.waitForFunction(
      () => Boolean(localStorage.getItem("agenthub_token")),
      null,
      { timeout: 20_000 },
    ).catch(() => null),
  ]);
  if (await username.isVisible().catch(() => false)) {
    await username.fill(employeeId);
    await page.locator("#password").fill(identities[employeeId]);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.agentHubUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.waitForFunction(() => Boolean(localStorage.getItem("agenthub_token")));
  const me = await page.evaluate(async () => {
    const response = await fetch("/api/v1/users/me");
    return { status: response.status, body: await response.json() };
  });
  assert(me.status === 200, `Agent Hub login failed for ${employeeId}`);
  assert(me.body.employee_id === employeeId, `Agent Hub principal mismatch for ${employeeId}`);
  return { context, page, user: me.body };
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

async function langflowJson(method, pathname, body) {
  const response = await fetch(`${config.langflowUrl}${pathname}`, {
    method,
    headers: {
      "x-api-key": langflowAccount.api_key,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  assert(response.ok, `Langflow ${method} ${pathname} returned ${response.status}`);
  return payload;
}

async function createIsolatedTargetFlow() {
  const flows = await langflowJson("GET", "/api/v1/flows/");
  const canonical = flows.find(
    (flow) => (
      flow.name === "BoI Wiki Agent Loop"
      && String(flow.folder_id || flow.project_id || "") === projectId
    ),
  );
  assert(canonical?.id, "canonical Flow is missing from boi-100002");
  const source = await langflowJson(
    "GET",
    `/api/v1/flows/${encodeURIComponent(canonical.id)}`,
  );
  const created = await langflowJson("POST", "/api/v1/flows/", {
    name: `BoI Wiki Agent Loop - Component Contract Guard ${runId}`,
    description: "Validation-only clean target for an incompatible Agent Hub component.",
    endpoint_name: `boi-wiki-component-guard-${runId.toLowerCase()}`,
    data: structuredClone(source.data || {}),
    webhook: false,
    access_type: "PRIVATE",
    tags: ["boi", "agent-playground", "validation", "component-contract"],
    folder_id: projectId,
    project_id: projectId,
  });
  assert(created?.id, "isolated target Flow creation failed");
  return created;
}

async function uploadAsset(page) {
  await page.getByRole("button", { name: /제출|Upload/i }).first().click();
  const modal = page.locator(".modal");
  await modal.waitFor();
  const chooserPromise = page.waitForEvent("filechooser");
  await modal.locator(".dropzone").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(path.resolve(config.incompatibleComponentFile));
  await modal.getByRole("button", { name: /다음|Next/i }).click();
  const fields = modal.locator("input.input");
  await fields.nth(0).fill(componentTitle);
  await fields.nth(1).fill(
    "boi.agent-slot.v1과 맞지 않아 자동 연결이 차단되어야 하는 검증 컴포넌트입니다.",
  );
  await modal.locator("textarea").fill(
    [
      "## 검증 목적",
      "",
      "- Agent Hub 소스 변경 없이 공유 컴포넌트를 실제 배포합니다.",
      "- boi.agent-slot.v2 계약이므로 Playground 자동 연결은 허용되지 않습니다.",
      "- 수동 연결 안내와 정확한 차단 사유가 남아야 합니다.",
    ].join("\n"),
  );
  await modal.getByRole("button", { name: /다음|Next/i }).click();
  const selects = modal.locator("select.select");
  await selects.nth(0).selectOption("1.9.1");
  await selects.nth(1).selectOption({ index: 0 });
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/v1/components"
  ));
  await modal.getByRole("button", { name: /제출하기|Submit/i }).click();
  const response = await responsePromise;
  assert(response.status() === 201, `Agent Hub upload returned ${response.status()}`);
  return response.json();
}

async function approveAsset(page) {
  await page.goto(`${config.agentHubUrl}#/admin`, { waitUntil: "domcontentloaded" });
  const row = page.locator(".sub-row").filter({ hasText: componentTitle });
  await row.waitFor();
  await row.locator('input[type="checkbox"]').click();
  const responsePromise = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/v1/admin/review/bulk"
  ));
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: /일괄 승인 \(1\)/ }).click();
  const response = await responsePromise;
  assert(response.ok(), `Agent Hub approval returned ${response.status()}`);
}

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let boiSession;
let hubSession;
let authorSession;
let approverSession;
try {
  const target = await createIsolatedTargetFlow();

  authorSession = await loginAgentHub(browser, "100001");
  const asset = await uploadAsset(authorSession.page);
  await authorSession.context.close();
  authorSession = null;

  approverSession = await loginAgentHub(browser, "2074795");
  assert(approverSession.user.role === "admin", "Agent Hub reviewer is not an admin");
  await approveAsset(approverSession.page);
  await approverSession.context.close();
  approverSession = null;

  boiSession = await loginBoi(browser);
  const adoptionResponse = await sessionFetch(
    boiSession.page,
    "/api/agent-playground/agent-hub/adoptions",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint_id: endpointId,
        project_id: projectId,
        asset_ids: [asset.id],
        validation_profile: "generic_action",
      }),
    },
  );
  assert(
    adoptionResponse.status === 200,
    `incompatible adoption begin failed: ${JSON.stringify(adoptionResponse.body)}`,
  );
  const adoption = adoptionResponse.body.adoption;

  hubSession = await loginAgentHub(browser, "100002");
  await hubSession.page.goto(
    `${config.agentHubUrl}#/component/${asset.id}`,
    { waitUntil: "domcontentloaded" },
  );
  await hubSession.page.getByRole("button", { name: "배포", exact: true }).waitFor();
  await hubSession.page.getByRole("button", { name: "배포", exact: true }).click();
  const modal = hubSession.page.locator(".modal").filter({ hasText: "Agent Builder에 배포" });
  await modal.waitFor();
  const endpointText = modal
    .getByText(config.langflowContainerUrl, { exact: true })
    .first();
  await endpointText.waitFor();
  await endpointText.locator("xpath=../..").click();
  await hubSession.page.waitForFunction(
    () => [...document.querySelectorAll(".modal select.select option")]
      .some((option) => option.textContent.includes("boi-100002")),
  );
  const selects = modal.locator("select.select");
  await selects.first().selectOption({
    label: (await selects.first().locator("option").allTextContents())
      .find((text) => text.includes("boi-100002")),
  });
  await hubSession.page.waitForFunction(
    ({ name }) => [...document.querySelectorAll(".modal select option")]
      .some((option) => option.textContent.includes(name)),
    { name: target.name },
  );
  await selects.last().selectOption({
    label: (await selects.last().locator("option").allTextContents())
      .find((text) => text.includes(target.name)),
  });
  const deployResponsePromise = hubSession.page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname
      === `/api/v1/deploy/components/${asset.id}`
  ));
  await modal.getByRole("button", { name: "배포", exact: true }).last().click();
  const deployResponse = await deployResponsePromise;
  assert(deployResponse.ok(), `Agent Hub incompatible deployment returned ${deployResponse.status()}`);
  const deployed = await deployResponse.json();
  assert(deployed.flow_id === target.id, "incompatible component target Flow changed");
  await modal.getByText("배포 완료!").waitFor();
  await hubSession.page.screenshot({
    path: path.join(config.evidenceDir, "01-incompatible-component-deployed.png"),
    fullPage: true,
  });

  const discovered = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(adoption.adoption_id)}/discover`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
  );
  assert(discovered.status === 200, "incompatible component discovery failed");
  assert(
    (discovered.body.candidates || []).some((item) => item.flow_id === target.id),
    "modified target Flow was not rediscovered",
  );
  const confirmed = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(adoption.adoption_id)}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flow_id: target.id }),
    },
  );
  assert(confirmed.status === 200, "incompatible exact Flow confirmation failed");
  const checksumBefore = confirmed.body.deployment.artifact_checksum;
  const compose = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(adoption.adoption_id)}/compose`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        flow_id: target.id,
        component_asset_id: asset.id,
        replace_agent_slot: true,
      }),
    },
  );
  assert(compose.status === 200, "incompatible compose request failed");
  assert(compose.body.status === "manual_required", "incompatible component was auto-connected");
  assert(
    compose.body.reason === "component_contract_incompatible",
    `unexpected incompatible reason: ${compose.body.reason}`,
  );
  const flowsAfter = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}/flows`,
  );
  const targetAfter = (flowsAfter.body.flows || []).find(
    (flow) => flow.flow_id === target.id,
  );
  assert(targetAfter?.live_checksum === checksumBefore, "manual-required compose changed the Flow");

  result.asset = {
    asset_id: asset.id,
    title: asset.title || componentTitle,
    author_employee_id: "100001",
    contract: compose.body.actual_contract,
  };
  result.deployment = {
    flow_id: target.id,
    checksum: checksumBefore,
  };
  result.compose = {
    status: compose.body.status,
    reason: compose.body.reason,
    patch_request_count: 0,
    checksum_before: checksumBefore,
    checksum_after: targetAfter.live_checksum,
    canvas_url: compose.body.langflow_canvas_url,
  };
  result.ok = (
    result.compose.status === "manual_required"
    && result.compose.reason === "component_contract_incompatible"
    && result.compose.checksum_before === result.compose.checksum_after
    && result.page_errors.length === 0
    && result.console_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  assert(result.ok, "incompatible component evidence is incomplete");
} finally {
  await authorSession?.context.close().catch(() => {});
  await approverSession?.context.close().catch(() => {});
  await boiSession?.context.close().catch(() => {});
  await hubSession?.context.close().catch(() => {});
  await browser.close();
  await fs.writeFile(
    path.join(config.evidenceDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    { mode: 0o600 },
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: config.evidenceDir }));
