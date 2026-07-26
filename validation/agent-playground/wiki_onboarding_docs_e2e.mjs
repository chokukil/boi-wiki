#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const boiUrl = process.env.BOI_URL || "http://localhost:28005";
const employeeId = process.env.BOI_EMPLOYEE_ID || "100002";
const password = process.env.BOI_SSO_PASSWORD || "";
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
      "Langflow 연결 키 발급",
      "BoI 지식 연결 자동 준비",
      "Agent Hub",
      "Action",
    ],
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
];

if (!password) throw new Error("BOI_SSO_PASSWORD is required");
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
