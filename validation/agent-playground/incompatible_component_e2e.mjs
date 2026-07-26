#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const config = {
  boiUrl: process.env.BOI_URL || "http://localhost:28005",
  agentHubUrl:
    process.env.AGENT_HUB_URL || "http://localhost:18080/AgentHub.html",
  langflowContainerUrl:
    process.env.LANGFLOW_CONTAINER_URL || "http://host.docker.internal:7867",
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
const team = JSON.parse(await fs.readFile(config.teamResult, "utf8"));
const endpointId = String(team.operator?.deployment_reference?.endpoint_connection_id || "");
const projectId = String(team.operator?.deployment_reference?.project_id || "");
const activeFlowId = String(team.operator?.deployment_reference?.flow_id || "");
if (!identities["100002"] || !endpointId || !projectId || !activeFlowId) {
  throw new Error("incompatible component fixture is incomplete");
}
await fs.mkdir(config.evidenceDir, { recursive: true });

const result = {
  ok: false,
  asset: {},
  deployment: {},
  compose: {},
  page_errors: [],
  console_errors: [],
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
      result.console_errors.push({ scope, text });
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

async function loginAgentHub(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  diagnostics(page, "agent-hub-100002");
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
    await username.fill("100002");
    await page.locator("#password").fill(identities["100002"]);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(config.agentHubUrl).origin),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.waitForFunction(() => Boolean(localStorage.getItem("agenthub_token")));
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

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
let boiSession;
let hubSession;
try {
  boiSession = await loginBoi(browser);
  const flowsResponse = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/endpoints/${encodeURIComponent(endpointId)}`
      + `/projects/${encodeURIComponent(projectId)}/flows`,
  );
  assert(flowsResponse.status === 200, "Playground live Flow list failed");
  const target = (flowsResponse.body.flows || []).find(
    (flow) => (
      flow.flow_id !== activeFlowId
      && String(flow.name || "").startsWith("BoI Wiki Agent Loop Mainline")
      && String(flow.name || "").includes("retry1")
      && !String(flow.name || "").includes("Incompatible")
    ),
  );
  assert(target?.flow_id && target?.name, "isolated target Flow for incompatible component is missing");

  const assetsResponse = await sessionFetch(
    boiSession.page,
    "/api/agent-playground/agent-hub/assets?asset_type=py&limit=100",
  );
  assert(assetsResponse.status === 200, "Agent Hub approved component search failed");
  const asset = (assetsResponse.body.items || []).find(
    (item) => (
      item.type === "py"
      && item.status === "approved"
      && item.author?.employee_id === "100001"
      && /T01\d+Z$/.test(String(item.title || ""))
    ),
  );
  assert(asset?.asset_id, "approved incompatible component is missing");
  const adoptionResponse = await sessionFetch(
    boiSession.page,
    "/api/agent-playground/agent-hub/adoptions",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint_id: endpointId,
        project_id: projectId,
        asset_ids: [asset.asset_id],
        validation_profile: "generic_action",
      }),
    },
  );
  assert(adoptionResponse.status === 200, "incompatible adoption begin failed");
  const adoption = adoptionResponse.body.adoption;

  hubSession = await loginAgentHub(browser);
  await hubSession.page.goto(
    `${config.agentHubUrl}#/component/${asset.asset_id}`,
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
      === `/api/v1/deploy/components/${asset.asset_id}`
  ));
  await modal.getByRole("button", { name: "배포", exact: true }).last().click();
  const deployResponse = await deployResponsePromise;
  assert(deployResponse.ok(), `Agent Hub incompatible deployment returned ${deployResponse.status()}`);
  const deployed = await deployResponse.json();
  assert(deployed.flow_id === target.flow_id, "incompatible component target Flow changed");
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
    (discovered.body.candidates || []).some((item) => item.flow_id === target.flow_id),
    "modified target Flow was not rediscovered",
  );
  const confirmed = await sessionFetch(
    boiSession.page,
    `/api/agent-playground/agent-hub/adoptions/${encodeURIComponent(adoption.adoption_id)}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flow_id: target.flow_id }),
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
        flow_id: target.flow_id,
        component_asset_id: asset.asset_id,
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
    (flow) => flow.flow_id === target.flow_id,
  );
  assert(targetAfter?.live_checksum === checksumBefore, "manual-required compose changed the Flow");

  result.asset = {
    asset_id: asset.asset_id,
    title: asset.title,
    author_employee_id: asset.author?.employee_id,
    contract: compose.body.actual_contract,
  };
  result.deployment = {
    flow_id: target.flow_id,
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
