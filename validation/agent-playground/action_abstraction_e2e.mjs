#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const boiUrl = process.env.BOI_URL || "http://localhost:28005";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE || "/tmp/boi-ap-agent-hub-sso-users.json";
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR ||
  "artifacts/agent-playground-action-abstraction";
const teamActionResultFile =
  process.env.TEAM_ACTION_RESULT ||
  "artifacts/agent-playground-current/browser/team-action-execution/result.json";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "";

const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const teamActionResult = JSON.parse(
  await fs.readFile(teamActionResultFile, "utf8"),
);
const exactLangflowActionKey = String(teamActionResult.action?.action_key || "");
const password = String(process.env.BOI_SSO_PASSWORD || identities["100002"] || "");
if (!password || !exactLangflowActionKey) {
  throw new Error("100002 or exact Langflow Action validation fixture is unavailable");
}
await fs.mkdir(evidenceDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  ...(executablePath ? { executablePath } : {}),
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const pageErrors = [];
const consoleErrors = [];
const unexpectedHttp = [];

page.on("pageerror", (error) => pageErrors.push(String(error)));
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("response", (response) => {
  if (response.status() >= 400) {
    unexpectedHttp.push({
      status: response.status(),
      url: response.url().replace(/[?#].*$/, ""),
    });
  }
});

async function screenshot(name) {
  await page.screenshot({
    path: path.join(evidenceDir, `${name}.png`),
    fullPage: true,
  });
}

try {
  await page.goto(`${boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (page.url().includes("/protocol/openid-connect/auth")) {
    await page.locator("#username").fill("100002");
    await page.locator("#password").fill(password);
    await Promise.all([
      page.waitForURL((url) => url.origin === new URL(boiUrl).origin, {
        timeout: 30_000,
      }),
      page.locator("#kc-login").click(),
    ]);
  }
  await page.waitForSelector("[data-agent-playground]");

  const created = await page.evaluate(async () => {
    const response = await fetch("/api/registration/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entry_kind: "action",
        scope: "private",
        title: "Connector Neutral API Action",
        business_goal: "Action 업무 계약과 API 실행 연결을 분리해 검증한다.",
        connector_kind: "api",
        connector_config: {
          method: "POST",
          endpoint: "https://quality.example/api/evidence",
          auth_profile: "quality-api-profile",
        },
        input_fields: ["question", "task_ref"],
        output_fields: ["answer", "source_references"],
        risk_level: "medium",
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(body));
    return body.draft;
  });

  const request = created.request || {};
  const patch = created.catalog_patch_proposal || {};
  if (request.execution_mode !== "gateway") throw new Error("execution mode is not gateway");
  if ((request.action_contract || {}).schema_version !== "boi.action-contract.v1") {
    throw new Error("connector-neutral Action contract is missing");
  }
  if ((request.connector_binding || {}).kind !== "api") {
    throw new Error("API connector binding was not preserved");
  }
  if (Object.prototype.hasOwnProperty.call(patch, "execution_kind")) {
    throw new Error("new Action patch still conflates execution_kind and connector_kind");
  }

  await page.goto(`${boiUrl}/actions/drafts/${encodeURIComponent(created.draft_id)}`, {
    waitUntil: "networkidle",
  });
  await page.getByText("Action contract → Connector binding", { exact: true }).waitFor();
  await page.getByText("api 실행 연결", { exact: true }).waitFor();
  await page.getByText("action_gateway.api", { exact: true }).waitFor();
  if (await page.getByText("배포 Flow 식별자", { exact: true }).count()) {
    throw new Error("generic API Action incorrectly rendered a Langflow deployment panel");
  }
  await screenshot("01-generic-api-action-contract");

  await page.locator("[data-validate-draft]").click();
  await page.locator("[data-validation-state]").filter({ hasText: "통과" }).waitFor({
    timeout: 15_000,
  });
  await screenshot("02-generic-api-action-validated");

  const playgroundDraft = await page.evaluate(async () => {
    const response = await fetch("/api/registration/drafts");
    const body = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(body));
    return (body.items || []).find(
      (item) =>
        item?.request?.connector_kind === "langflow" &&
        item?.request?.connector_config?.connection_source === "agent_playground",
    );
  });
  if (!playgroundDraft) throw new Error("existing exact Playground Action draft was not found");

  await page.goto(
    `${boiUrl}/actions/drafts/${encodeURIComponent(playgroundDraft.draft_id)}`,
    { waitUntil: "networkidle" },
  );
  await page.getByText("Langflow connector binding", { exact: true }).waitFor();
  await page.getByText("배포 Flow 식별자", { exact: true }).waitFor();
  const flowId = String(playgroundDraft.request.connector_config.flow_id || "");
  if (!flowId) throw new Error("Playground Action exact Flow ID is missing");
  await page.getByText(flowId, { exact: true }).waitFor();
  await screenshot("03-playground-langflow-binding");

  const gatewayCases = [
    {
      connector_kind: "api",
      action_key: "sop.equipment.request_raw_data",
      event_type: "equipment.alarm.raised.v1",
      payload: {
        equipment_id: "EQ-CONNECTOR-REGRESSION",
        lot_id: "LOT-CONNECTOR-REGRESSION",
      },
      expected_status: "invoked",
    },
    {
      connector_kind: "mcp",
      action_key: "mcp.boi_search.sample",
      event_type: "report.requested.v1",
      payload: { query: "Agent Playground Ontology" },
      expected_status: "mcp_invoked",
      dry_run: false,
    },
    {
      connector_kind: "webhook",
      action_key: "direct_development.messenger_share.publish",
      event_type: "direct_development.share.requested.v1",
      payload: {
        title: "Connector-neutral webhook validation",
        message: "승인된 격리 검증 webhook 호출",
      },
      approved_by: "100001",
      expected_status: "invoked",
    },
    {
      connector_kind: "manual",
      action_key: "manual.equipment.confirm_alarm_context",
      event_type: "equipment.alarm.raised.v1",
      payload: {
        title: "Connector-neutral manual validation",
        equipment_id: "EQ-CONNECTOR-REGRESSION",
      },
      expected_status: "manual_required",
      dry_run: false,
    },
    {
      connector_kind: "event_broker",
      action_key: "boi.publish_event",
      event_type: "manual.input.v1",
      payload: {
        event_type: "manual.input.v1",
        trace_id: `trace-connector-event-${Date.now()}`,
        payload: { title: "Connector-neutral event validation" },
        source_refs: [],
      },
      expected_status: "event_published",
      dry_run: false,
    },
    {
      connector_kind: "boi_writer",
      action_key: "boi.materialize_event",
      event_type: "meeting.closed.v1",
      payload: {
        title: "Connector-neutral BoI Writer validation",
        summary: "격리 콘텐츠에만 생성하는 실제 Gateway 검증",
      },
      expected_status: "materialized",
      dry_run: false,
    },
    {
      connector_kind: "langflow",
      action_key: exactLangflowActionKey,
      event_type: "agent.playground.requested.v1",
      payload: {
        question: "connector-neutral exact Langflow preview",
        save_mode: "preview",
      },
      expected_status: "langflow_invoked",
      dry_run: false,
    },
  ];
  const gatewayInvocations = [];
  for (const scenario of gatewayCases) {
    const traceId = `trace-connector-${scenario.connector_kind}-${Date.now()}`;
    const invoked = await page.evaluate(async ({ scenario, traceId }) => {
      const response = await fetch("/api/actions/invoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_key: scenario.action_key,
          event: {
            event_id: `evt-${scenario.connector_kind}-${Date.now()}`,
            event_type: scenario.event_type,
            trace_id: traceId,
            payload: scenario.payload,
            actor: { employee_id: "100002" },
          },
          payload: scenario.payload,
          dry_run: scenario.dry_run ?? false,
          approved_by: scenario.approved_by || null,
        }),
      });
      return {
        http_status: response.status,
        body: await response.json().catch(() => ({})),
      };
    }, { scenario, traceId });
    if (invoked.http_status !== 200) {
      throw new Error(
        `${scenario.connector_kind} Gateway returned HTTP ${invoked.http_status}: `
        + JSON.stringify(invoked.body),
      );
    }
    if (invoked.body.status !== scenario.expected_status) {
      throw new Error(
        `${scenario.connector_kind} Gateway status is ${invoked.body.status}, `
        + `expected ${scenario.expected_status}`,
      );
    }
    gatewayInvocations.push({
      connector_kind: scenario.connector_kind,
      action_key: scenario.action_key,
      called: true,
      http_status: invoked.http_status,
      status: invoked.body.status,
      request_id: invoked.body.request_id,
      trace_id: traceId,
    });
  }
  await screenshot("04-connector-neutral-gateway-invocations");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${boiUrl}/actions/drafts/${encodeURIComponent(created.draft_id)}`, {
    waitUntil: "networkidle",
  });
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    body: document.body.scrollWidth,
  }));
  if (dimensions.body > dimensions.viewport) {
    throw new Error(`mobile horizontal overflow: ${JSON.stringify(dimensions)}`);
  }
  await screenshot("05-generic-api-action-mobile");

  const result = {
    ok: true,
    principal: "100002",
    generic_action: {
      draft_id: created.draft_id,
      execution_mode: request.execution_mode,
      contract_schema: request.action_contract.schema_version,
      connector_kind: request.connector_binding.kind,
      adapter: request.connector_binding.adapter,
      validated: true,
    },
    playground_action: {
      draft_id: playgroundDraft.draft_id,
      connector_kind: playgroundDraft.request.connector_kind,
      exact_flow_id: flowId,
    },
    gateway_invocations: gatewayInvocations,
    mobile: dimensions,
    page_errors: pageErrors,
    console_errors: consoleErrors,
    unexpected_http: unexpectedHttp,
  };
  if (pageErrors.length || consoleErrors.length || unexpectedHttp.length) {
    throw new Error(`browser diagnostics failed: ${JSON.stringify(result)}`);
  }
  await fs.writeFile(
    path.join(evidenceDir, "action-abstraction-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
