#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const boiUrl = process.env.BOI_URL || "http://localhost:28005";
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const identityFile =
  process.env.AGENT_HUB_IDENTITY_FILE
  || "/tmp/boi-ap-agent-hub-sso-users.json";
const identities = JSON.parse(await fs.readFile(identityFile, "utf8"));
const password =
  process.env.BOI_SSO_PASSWORD
  || String(identities[employeeId] || "");
const evidenceDir =
  process.env.PLAYWRIGHT_EVIDENCE_DIR
  || "artifacts/agent-playground-wiki-onboarding";
const docs = [
  {
    key: "onboarding",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding",
    heading: "Agent Playground 시작 가이드",
    expected: [
      "3분 빠른 시작",
      "Langflow 처음 연결하기",
      "Agent Hub",
      "Action",
    ],
  },
  {
    key: "langflow-setup",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-langflow-setup",
    heading: "Langflow 처음 연결하기",
    expected: ["Settings → API Keys", "BOI_WIKI_PAT", "자동 준비"],
  },
  {
    key: "browser-sso",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-browser-sso",
    heading: "회사 SSO로 Langflow 원본 Flow 열기",
    expected: [
      "DEV · Playground",
      "PRD · Agent Hub",
      "Browser SSO",
      "embedded_sso",
    ],
  },
  {
    key: "my-flow-deploy",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-my-flow-deploy",
    heading: "내 Flow를 Agent Hub에 배포하기",
    expected: ["연결 시험", "boi-{사번}", "배포 결과 확인", "checksum"],
  },
  {
    key: "shared-assets",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-shared-assets",
    heading: "Agent Hub 공유 자산 활용하기",
    expected: ["배포됨", "연결 필요", "실행 검증됨", "boi.agent-slot.v1"],
  },
  {
    key: "action-wiki",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki",
    heading: "Action으로 연결하고 Wiki에서 실행하기",
    expected: ["Ontology", "connector_binding", "SOP Task", "개인 초안"],
  },
  {
    key: "troubleshooting",
    pathname:
      "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-troubleshooting",
    heading: "Agent Playground 문제 해결",
    expected: ["API Key 오류", "Agent Hub 배포 오류", "Flow 변경 감지"],
  },
  {
    key: "operator",
    pathname:
      "/docs/boi:public:boi-wiki-manual:operations:agent-playground-operator-runbook",
    heading: "Agent Playground 운영 가이드",
    expected: [
      "지원 버전과 이미지",
      "custom component",
      "migration",
      "rollback",
    ],
  },
  {
    key: "sso-deployment",
    pathname:
      "/docs/boi:public:boi-wiki-manual:operations:agent-playground-sso-deployment",
    heading: "Agent Playground 사내 SSO 방식 선택 가이드",
    expected: [
      "OIDC와 JWKS",
      "Trusted Header와 Token Bridge",
      "공식 Langflow 1.11.0 검증 결과",
      "Agent Hub",
    ],
  },
  {
    key: "hub-boundary",
    pathname:
      "/docs/boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary",
    heading: "Agent Hub 연동 경계와 운영 책임",
    expected: ["Agent Hub는 BoI 개발 영역이 아니다", "금지하는 연동", "읽기 전용"],
  },
];

if (!password) throw new Error(`${employeeId} validation password is unavailable`);
await fs.mkdir(evidenceDir, { recursive: true });

const result = {
  ok: false,
  oidc: {},
  documents: [],
  screenshots: [],
  console_errors: [],
  page_errors: [],
  unexpected_http_errors: [],
};
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
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
page.on("response", (response) => {
  if (response.status() < 400) return;
  const url = new URL(response.url());
  result.unexpected_http_errors.push({
    status: response.status(),
    method: response.request().method(),
    url: `${url.origin}${url.pathname}`,
  });
});

async function capture(name) {
  const target = path.join(evidenceDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  result.screenshots.push(target);
}

try {
  await page.goto(`${boiUrl}/playground`, { waitUntil: "domcontentloaded" });
  if (!page.url().includes("/protocol/openid-connect/")) {
    throw new Error("BoI did not start OIDC login");
  }
  const authorization = new URL(page.url());
  result.oidc = {
    state: Boolean(authorization.searchParams.get("state")),
    nonce: Boolean(authorization.searchParams.get("nonce")),
    pkce_s256: authorization.searchParams.get("code_challenge_method") === "S256",
  };
  if (!Object.values(result.oidc).every(Boolean)) {
    throw new Error("OIDC+PKCE evidence is incomplete");
  }
  await page.locator("#username").fill(employeeId);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  await page.waitForURL((url) => url.origin === new URL(boiUrl).origin);
  await page.locator("[data-agent-playground]").waitFor();

  for (const doc of docs) {
    const response = await page.goto(`${boiUrl}${doc.pathname}`, {
      waitUntil: "networkidle",
    });
    if (!response || response.status() !== 200) {
      throw new Error(`${doc.key} Wiki document returned HTTP ${response?.status()}`);
    }
    await page.getByRole("heading", { name: doc.heading, exact: true }).waitFor();
    const bodyText = await page.locator("body").innerText();
    for (const expected of doc.expected) {
      if (!bodyText.toLowerCase().includes(expected.toLowerCase())) {
        throw new Error(`${doc.key} Wiki document is missing: ${expected}`);
      }
    }
    const petDomCount = await page.locator(
      '[data-pet], [class*="pet-agent"], script[src*="pet"], img[src*="pet"]',
    ).count();
    if (petDomCount !== 0) {
      throw new Error(`${doc.key} Wiki document contains pet DOM/assets`);
    }
    await capture(`01-${doc.key}-desktop`);
    await page.setViewportSize({ width: 390, height: 844 });
    const dimensions = await page.evaluate(() => ({
      viewport: window.innerWidth,
      body: document.body.scrollWidth,
    }));
    if (dimensions.body > dimensions.viewport) {
      throw new Error(
        `${doc.key} mobile horizontal overflow: ${JSON.stringify(dimensions)}`,
      );
    }
    await capture(`02-${doc.key}-mobile`);
    result.documents.push({
      key: doc.key,
      url: `${boiUrl}${doc.pathname}`,
      status: response.status(),
      heading: doc.heading,
      required_sections: doc.expected,
      pet_dom_count: petDomCount,
      mobile: dimensions,
    });
    await page.setViewportSize({ width: 1440, height: 1050 });
  }

  result.ok = (
    result.console_errors.length === 0
    && result.page_errors.length === 0
    && result.unexpected_http_errors.length === 0
  );
  if (!result.ok) throw new Error("browser diagnostics recorded unexpected errors");
} finally {
  await context.close();
  await browser.close();
  await fs.writeFile(
    path.join(evidenceDir, "wiki-onboarding-docs-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
}

console.log(JSON.stringify({ ok: result.ok, evidence_dir: evidenceDir }));
