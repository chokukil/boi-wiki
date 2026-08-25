#!/usr/bin/env node
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const nodeModules = process.env.CODEX_NODE_MODULES || "/mnt/c/Users/choku/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const pptxgen = require(join(nodeModules, "pptxgenjs"));
const sharp = require(join(nodeModules, "sharp"));

const scriptRoot = dirname(fileURLToPath(import.meta.url));
const root = resolve(process.argv[2] || dirname(scriptRoot));
const artifactRoot = join(root, "artifacts/science-verifier");
const deckRoot = join(artifactRoot, "deck");
const assets = join(deckRoot, "assets");
const rendered = join(deckRoot, "rendered");
mkdirSync(rendered, { recursive: true });

function fileDigest(path) {
  return "sha256:" + createHash("sha256").update(readFileSync(path)).digest("hex");
}

const verificationPath = join(artifactRoot, "verification-manifest.json");
const verification = JSON.parse(readFileSync(verificationPath, "utf8"));
const currentCommit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
const trackedStatus = execFileSync(
  "git",
  ["status", "--porcelain=v1", "--untracked-files=no"],
  { cwd: root, encoding: "utf8" },
).trim();
if (trackedStatus) {
  throw new Error("refusing to build evidence deck because tracked files differ from HEAD");
}
const browserEvidence = verification.evidence?.browser;
const qualificationEvidence = verification.evidence?.qualification;
const reviewEvidence = verification.evidence?.independent_review;
const browserChecks = browserEvidence?.check_results;
const requiredGates = {
  G0: "PASS", G1: "PASS", G2: "PASS", G3: "PASS", G4: "PASS",
  G5: "PENDING", G6: "PENDING", G7: "PENDING",
};
const evidenceIsFinal =
  verification.schema_version === "science-verifier-evidence-manifest/0.2"
  && verification.report_state === "FINAL"
  && verification.implementation_status === "VERIFIED"
  && Array.isArray(verification.failure_reasons)
  && verification.failure_reasons.length === 0
  && verification.git?.commit === currentCommit
  && verification.git?.dirty === false
  && verification.activation_eligible === false
  && browserEvidence?.passed === true
  && Array.isArray(browserChecks)
  && browserChecks.length === 21
  && browserChecks.every((check) => check?.status === "passed")
  && reviewEvidence?.passed === true
  && reviewEvidence?.findings?.critical === 0
  && reviewEvidence?.findings?.important === 0
  && qualificationEvidence?.lifecycle === "release_candidate"
  && qualificationEvidence?.activation_eligible === false
  && Object.entries(requiredGates).every(([gate, status]) => verification.gates?.[gate] === status);
if (!evidenceIsFinal) {
  throw new Error("refusing to build evidence deck from non-final or unbound verification manifest");
}
const publicCaseCount = qualificationEvidence.public_case_count;
const browserCheckCount = browserChecks.length;
const gatePassLabel = `G0–G4  ${verification.gates.G0}`;
const implementationHeadline = "구현은 검증됐고, 과학 지식 Release는 아직 비활성이다";
const qualificationDigestShort = verification.qualification_result_digest.slice(7, 15);

const paths = {
  architecture: join(assets, "science-integrity-layer.png"),
  ui: join(assets, "review-canvas-desktop.png"),
  report: join(assets, "final-qualification-report.png"),
  pptx: join(deckRoot, "science-verifier-evidence.pptx"),
};
for (const [name, path] of Object.entries(paths)) {
  if (name !== "pptx" && name !== "report" && !statSync(path).isFile()) throw new Error(`missing deck input: ${path}`);
}
const desktopCaptures = browserEvidence?.capture_files?.filter(
  (capture) => basename(capture?.path || "") === "review-canvas-desktop.png",
);
const uiDigest = fileDigest(paths.ui);
if (
  !Array.isArray(desktopCaptures)
  || desktopCaptures.length !== 1
  || desktopCaptures[0]?.sha256 !== uiDigest
  || desktopCaptures[0]?.actual_sha256 !== uiDigest
) {
  throw new Error("desktop UI capture does not match browser evidence expected/actual digests");
}
const reportPdf = join(artifactRoot, "qualification-report.pdf");
if (fileDigest(reportPdf) !== verification.pdf?.sha256) {
  throw new Error("qualification report PDF does not match verification manifest");
}
const python = process.env.BOI_PYTHON || process.env.PYTHON || "python3";
try {
  execFileSync(
    python,
    [
      join(scriptRoot, "render_verified_pdf_page.py"),
      reportPdf,
      paths.report,
      verification.pdf.sha256,
    ],
    { cwd: root, encoding: "utf8", stdio: "pipe" },
  );
} catch (error) {
  throw new Error(
    "failed to render verified qualification report PDF; set BOI_PYTHON or PYTHON to an interpreter with pypdfium2",
    { cause: error },
  );
}
if (!statSync(paths.report).isFile()) {
  throw new Error("verified qualification report render did not produce a PNG");
}

const C = {
  ink: "111827", muted: "667085", paper: "F5F7FB", white: "FFFFFF",
  purple: "6D28D9", teal: "0F766E", green: "15803D", amber: "D97706",
  amberBg: "FFF7ED", border: "D7DCE5", soft: "EEF2FF", dark: "0B1220",
};
const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "BoI Wiki Science Verifier";
pptx.subject = "Deterministic Science Verifier implementation evidence";
pptx.title = "Science Verifier Evidence";
pptx.company = "AIX 확산 TF";
pptx.lang = "ko-KR";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "ko-KR",
};

function addPage(slide, current) {
  slide.addText(`${current}/3`, { x: 12.45, y: 7.1, w: 0.55, h: 0.2, fontFace: "Aptos", fontSize: 8.5, color: C.muted, align: "right", margin: 0 });
}

function addSource(slide, text) {
  slide.addText(text, { x: 0.45, y: 7.08, w: 11.2, h: 0.22, fontFace: "Aptos", fontSize: 7.2, color: C.muted, margin: 0 });
}

function title(slide, kicker, headline, note = "") {
  slide.addText(kicker, { x: 0.45, y: 0.27, w: 3.4, h: 0.22, fontFace: "Aptos", fontSize: 8.5, bold: true, color: C.purple, charSpacing: 1.5, margin: 0 });
  slide.addText(headline, { x: 0.45, y: 0.55, w: 11.8, h: 0.48, fontFace: "Aptos Display", fontSize: 23, bold: true, color: C.ink, margin: 0 });
  if (note) slide.addText(note, { x: 0.47, y: 1.0, w: 11.5, h: 0.3, fontFace: "Aptos", fontSize: 10.5, color: C.muted, margin: 0 });
}

async function contain(path, x, y, w, h) {
  const meta = await sharp(path).metadata();
  const scale = Math.min(w / meta.width, h / meta.height);
  const iw = meta.width * scale;
  const ih = meta.height * scale;
  return { x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih };
}

function metric(slide, x, y, value, label, accent) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w: 2.0, h: 1.0, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: C.border, width: 1 } });
  slide.addText(value, { x: x + 0.16, y: y + 0.14, w: 1.68, h: 0.36, fontFace: "Aptos Display", fontSize: 21, bold: true, color: accent, margin: 0 });
  slide.addText(label, { x: x + 0.16, y: y + 0.58, w: 1.7, h: 0.2, fontFace: "Aptos", fontSize: 8.5, color: C.muted, margin: 0 });
}

const slide1 = pptx.addSlide();
slide1.background = { color: C.paper };
slide1.addImage({ path: paths.architecture, x: 0, y: 0, w: 13.333, h: 7.5, sizing: "crop" });
slide1.addShape(pptx.ShapeType.roundRect, { x: 0.34, y: 0.24, w: 1.55, h: 0.38, rectRadius: 0.07, fill: { color: C.dark, transparency: 8 }, line: { color: C.dark, transparency: 100 } });
slide1.addText("운영 목표 구조", { x: 0.5, y: 0.34, w: 1.22, h: 0.15, fontFace: "Aptos", fontSize: 9, bold: true, color: C.white, align: "center", margin: 0 });
slide1.addShape(pptx.ShapeType.roundRect, { x: 10.34, y: 0.22, w: 2.6, h: 0.48, rectRadius: 0.08, fill: { color: C.amberBg, transparency: 4 }, line: { color: C.amber, width: 1.2 } });
slide1.addText("현재 Release · 비활성 후보", { x: 10.55, y: 0.37, w: 2.2, h: 0.16, fontFace: "Aptos", fontSize: 10, bold: true, color: C.amber, align: "center", margin: 0 });
slide1.addShape(pptx.ShapeType.roundRect, { x: 3.37, y: 6.78, w: 6.58, h: 0.45, rectRadius: 0.07, fill: { color: C.dark, transparency: 5 }, line: { color: C.dark, transparency: 100 } });
slide1.addText("AI·사용자 = 해석 후보  ·  활성 Rule + 조건 + Evidence = 판정", { x: 3.62, y: 6.92, w: 6.08, h: 0.16, fontFace: "Aptos", fontSize: 10, bold: true, color: C.white, align: "center", margin: 0 });
addPage(slide1, 1);
slide1.addNotes("목표 구조를 설명한다. 그림의 approved release 단계는 운영 목표이며, 현재 Candidate는 active가 아니다.");

const slide2 = pptx.addSlide();
slide2.background = { color: C.paper };
title(slide2, "REAL DOCUMENT REVIEW", "Qwen 없이도 문서 검토와 Claim 확인이 끝난다", "실제 실행 화면 · release_candidate · 운영 판정과 빨간 표시 없음");
slide2.addShape(pptx.ShapeType.roundRect, { x: 0.43, y: 1.36, w: 5.25, h: 5.5, rectRadius: 0.06, fill: { color: C.white }, line: { color: C.border, width: 1 } });
slide2.addImage({ path: paths.ui, ...(await contain(paths.ui, 0.53, 1.46, 5.05, 5.3)) });
metric(slide2, 5.96, 1.5, `${browserCheckCount}/${browserCheckCount}`, "실제 Chromium checks", C.green);
metric(slide2, 8.12, 1.5, "0", "inactive 빨간 표시", C.purple);
metric(slide2, 10.28, 1.5, "0", "기본 Qwen 호출", C.teal);
slide2.addShape(pptx.ShapeType.roundRect, { x: 5.96, y: 2.8, w: 6.32, h: 2.4, rectRadius: 0.07, fill: { color: C.white }, line: { color: C.border, width: 1 } });
slide2.addText("서버가 다시 확인하는 것", { x: 6.25, y: 3.05, w: 2.8, h: 0.3, fontFace: "Aptos Display", fontSize: 15, bold: true, color: C.ink, margin: 0 });
slide2.addText([
  { text: "01  ", options: { bold: true, color: C.purple } }, { text: "canonical 문서의 exact Unicode span\n" },
  { text: "02  ", options: { bold: true, color: C.purple } }, { text: "등록 alias와 subject / relation / object 역할\n" },
  { text: "03  ", options: { bold: true, color: C.purple } }, { text: "ontology_ref, 조건, 사용자 확인 event\n" },
  { text: "04  ", options: { bold: true, color: C.purple } }, { text: "client_kind와 무관한 동일 Claim 결과" },
], { x: 6.25, y: 3.52, w: 5.55, h: 1.32, fontFace: "Aptos", fontSize: 11.5, color: C.ink, breakLine: false, margin: 0.02, paraSpaceAfterPt: 7 });
slide2.addShape(pptx.ShapeType.roundRect, { x: 5.96, y: 5.46, w: 6.32, h: 1.1, rectRadius: 0.07, fill: { color: C.amberBg }, line: { color: C.amber, width: 1.2 } });
slide2.addText("release_candidate에서는 confirm 뒤에도 verify를 호출하지 않는다", { x: 6.25, y: 5.74, w: 5.7, h: 0.3, fontFace: "Aptos Display", fontSize: 14, bold: true, color: C.amber, margin: 0 });
slide2.addText("문서 위 표시는 별칭 해석이며 판정이 아니다.", { x: 6.25, y: 6.12, w: 5.3, h: 0.2, fontFace: "Aptos", fontSize: 9.2, color: C.muted, margin: 0 });
addSource(slide2, "Source · live /science-verifier · Chromium CDP strict run · 2026-08-25");
addPage(slide2, 2);
slide2.addNotes("실제 비활성 상태의 화면이다. active Release가 없으므로 red가 없는 것이 올바른 결과다.");

const slide3 = pptx.addSlide();
slide3.background = { color: C.paper };
title(slide3, "QUALIFICATION BOUNDARY", implementationHeadline, "자동 통과 항목과 사람 승인 대기를 같은 화면에 고정");
slide3.addShape(pptx.ShapeType.roundRect, { x: 0.43, y: 1.36, w: 6.3, h: 5.5, rectRadius: 0.06, fill: { color: C.white }, line: { color: C.border, width: 1 } });
slide3.addImage({ path: paths.report, ...(await contain(paths.report, 0.52, 1.45, 6.12, 5.31)) });
slide3.addText("자동 검증", { x: 7.06, y: 1.52, w: 2.4, h: 0.28, fontFace: "Aptos Display", fontSize: 15, bold: true, color: C.ink, margin: 0 });
slide3.addShape(pptx.ShapeType.roundRect, { x: 7.06, y: 1.9, w: 5.75, h: 1.12, rectRadius: 0.07, fill: { color: "ECFDF3" }, line: { color: "86EFAC", width: 1 } });
slide3.addText(gatePassLabel, { x: 7.34, y: 2.13, w: 2.1, h: 0.34, fontFace: "Aptos Display", fontSize: 21, bold: true, color: C.green, margin: 0 });
slide3.addText(`${publicCaseCount}/${publicCaseCount} public candidate cases\n반복 qualification bytes 동일`, { x: 9.43, y: 2.09, w: 2.9, h: 0.55, fontFace: "Aptos", fontSize: 9.2, color: C.ink, margin: 0 });
slide3.addText("사람 승인 대기", { x: 7.06, y: 3.4, w: 2.4, h: 0.28, fontFace: "Aptos Display", fontSize: 15, bold: true, color: C.ink, margin: 0 });
for (const [index, row] of [
  ["G5", "독립 sealed holdout"],
  ["G6", "active stored-report channel parity"],
  ["G7", "Science Admin 원문 검토·activation audit"],
].entries()) {
  const y = 3.84 + index * 0.64;
  slide3.addShape(pptx.ShapeType.roundRect, { x: 7.06, y, w: 5.75, h: 0.52, rectRadius: 0.05, fill: { color: C.amberBg }, line: { color: "FED7AA", width: 0.8 } });
  slide3.addText(row[0], { x: 7.28, y: y + 0.15, w: 0.5, h: 0.16, fontFace: "Aptos", fontSize: 10, bold: true, color: C.amber, margin: 0 });
  slide3.addText(row[1], { x: 7.83, y: y + 0.14, w: 4.55, h: 0.18, fontFace: "Aptos", fontSize: 9.5, color: C.ink, margin: 0 });
}
slide3.addShape(pptx.ShapeType.roundRect, { x: 7.06, y: 5.95, w: 5.75, h: 0.72, rectRadius: 0.06, fill: { color: C.dark }, line: { color: C.dark } });
slide3.addText("완료 = 구현 + 자동 검증\n완료 아님 = 과학적 진실·공정 승인·Release 활성화", { x: 7.34, y: 6.12, w: 5.1, h: 0.38, fontFace: "Aptos", fontSize: 10.5, bold: true, color: C.white, margin: 0, breakLine: false });
addSource(slide3, `Source · qualification-report.{md,pdf} · qualification digest ${qualificationDigestShort}…`);
addPage(slide3, 3);
slide3.addNotes("G5-G7이 PENDING이므로 Release를 활성화하거나 운영 검증 완료로 표현하지 않는다.");

await pptx.writeFile({ fileName: paths.pptx });

function esc(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
function dataUri(path) {
  return `data:image/png;base64,${readFileSync(path).toString("base64")}`;
}
async function svgContain(path, x, y, w, h) {
  const meta = await sharp(path).metadata();
  const scale = Math.min(w / meta.width, h / meta.height);
  const iw = meta.width * scale;
  const ih = meta.height * scale;
  return `<image href="${dataUri(path)}" x="${x + (w - iw) / 2}" y="${y + (h - ih) / 2}" width="${iw}" height="${ih}"/>`;
}
const font = "Arial, 'WenQuanYi Zen Hei', sans-serif";
function text(x, y, content, size, color = "#111827", weight = 400, anchor = "start") {
  return `<text x="${x}" y="${y}" font-family="${font}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}">${esc(content)}</text>`;
}
function lines(x, y, content, size, color, weight = 400, gap = 1.35) {
  return String(content).split("\n").map((line, index) => text(x, y + index * size * gap, line, size, color, weight)).join("");
}
function page(current) { return text(1545, 866, `${current}/3`, 14, "#667085", 400, "end"); }
function svgFrame(body, bg = "#F5F7FB") { return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><rect width="1600" height="900" fill="${bg}"/>${body}</svg>`; }
function rounded(x, y, w, h, fill, stroke = "none", radius = 16, sw = 1) { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`; }

const slideSvgs = [];
slideSvgs.push(svgFrame(`
  <image href="${dataUri(paths.architecture)}" x="0" y="0" width="1600" height="900" preserveAspectRatio="xMidYMid slice"/>
  ${rounded(40, 30, 186, 48, "#0B1220eF", "none", 10)}${text(133, 61, "운영 목표 구조", 17, "#FFFFFF", 700, "middle")}
  ${rounded(1240, 28, 310, 56, "#FFF7EDf5", "#D97706", 12, 2)}${text(1395, 63, "현재 Release · 비활성 후보", 18, "#D97706", 700, "middle")}
  ${rounded(405, 812, 790, 54, "#0B1220f5", "none", 10)}${text(800, 846, "AI·사용자 = 해석 후보  ·  활성 Rule + 조건 + Evidence = 판정", 19, "#FFFFFF", 700, "middle")}
  ${page(1)}
`, "#FFFFFF"));

const uiImage = await svgContain(paths.ui, 64, 164, 630, 642);
slideSvgs.push(svgFrame(`
  ${text(54, 44, "REAL DOCUMENT REVIEW", 14, "#6D28D9", 700)}
  ${text(54, 92, "Qwen 없이도 문서 검토와 Claim 확인이 끝난다", 32, "#111827", 700)}
  ${text(56, 128, "실제 실행 화면 · release_candidate · 운영 판정과 빨간 표시 없음", 17, "#667085", 400)}
  ${rounded(52, 160, 642, 650, "#FFFFFF", "#D7DCE5", 12, 1)}${uiImage}
  ${rounded(718, 180, 240, 118, "#FFFFFF", "#D7DCE5", 12)}${text(742, 228, `${browserCheckCount}/${browserCheckCount}`, 34, "#15803D", 700)}${text(742, 270, "실제 Chromium checks", 14, "#667085")}
  ${rounded(978, 180, 240, 118, "#FFFFFF", "#D7DCE5", 12)}${text(1002, 228, "0", 34, "#6D28D9", 700)}${text(1002, 270, "inactive 빨간 표시", 14, "#667085")}
  ${rounded(1238, 180, 240, 118, "#FFFFFF", "#D7DCE5", 12)}${text(1262, 228, "0", 34, "#0F766E", 700)}${text(1262, 270, "기본 Qwen 호출", 14, "#667085")}
  ${rounded(718, 334, 760, 286, "#FFFFFF", "#D7DCE5", 12)}${text(750, 376, "서버가 다시 확인하는 것", 23, "#111827", 700)}
  ${lines(752, 425, "01   canonical 문서의 exact Unicode span\n02   등록 alias와 subject / relation / object 역할\n03   ontology_ref, 조건, 사용자 확인 event\n04   client_kind와 무관한 동일 Claim 결과", 18, "#111827", 400, 1.6)}
  ${rounded(718, 652, 760, 128, "#FFF7ED", "#D97706", 12, 2)}${text(750, 704, "release_candidate에서는 confirm 뒤에도 verify를 호출하지 않는다", 20, "#D97706", 700)}${text(750, 742, "문서 위 표시는 별칭 해석이며 판정이 아니다.", 15, "#667085")}
  ${text(54, 862, "Source · live /science-verifier · Chromium CDP strict run · 2026-08-25", 12, "#667085")}${page(2)}
`));

const reportImage = await svgContain(paths.report, 62, 164, 700, 642);
slideSvgs.push(svgFrame(`
  ${text(54, 44, "QUALIFICATION BOUNDARY", 14, "#6D28D9", 700)}
  ${text(54, 92, implementationHeadline, 32, "#111827", 700)}
  ${text(56, 128, "자동 통과 항목과 사람 승인 대기를 같은 화면에 고정", 17, "#667085")}
  ${rounded(52, 160, 720, 650, "#FFFFFF", "#D7DCE5", 12)}${reportImage}
  ${text(816, 206, "자동 검증", 23, "#111827", 700)}
  ${rounded(816, 230, 690, 130, "#ECFDF3", "#86EFAC", 12)}${text(850, 292, gatePassLabel, 34, "#15803D", 700)}${lines(1150, 278, `${publicCaseCount}/${publicCaseCount} public candidate cases\n반복 qualification bytes 동일`, 15, "#111827", 400, 1.45)}
  ${text(816, 414, "사람 승인 대기", 23, "#111827", 700)}
  ${rounded(816, 442, 690, 62, "#FFF7ED", "#FED7AA", 10)}${text(844, 481, "G5", 17, "#D97706", 700)}${text(910, 481, "독립 sealed holdout", 16, "#111827")}
  ${rounded(816, 516, 690, 62, "#FFF7ED", "#FED7AA", 10)}${text(844, 555, "G6", 17, "#D97706", 700)}${text(910, 555, "active stored-report channel parity", 16, "#111827")}
  ${rounded(816, 590, 690, 62, "#FFF7ED", "#FED7AA", 10)}${text(844, 629, "G7", 17, "#D97706", 700)}${text(910, 629, "Science Admin 원문 검토·activation audit", 16, "#111827")}
  ${rounded(816, 694, 690, 90, "#0B1220", "#0B1220", 12)}${lines(850, 734, "완료 = 구현 + 자동 검증\n완료 아님 = 과학적 진실·공정 승인·Release 활성화", 17, "#FFFFFF", 700, 1.35)}
  ${text(54, 862, `Source · qualification-report.{md,pdf} · qualification digest ${qualificationDigestShort}…`, 12, "#667085")}${page(3)}
`));

for (let index = 0; index < slideSvgs.length; index += 1) {
  await sharp(Buffer.from(slideSvgs[index])).png().toFile(join(rendered, `slide-${index + 1}.png`));
}
const slides = [1, 2, 3].map((number) => join(rendered, `slide-${number}.png`));
const thumbWidth = 760;
const thumbHeight = 428;
const whole = sharp({ create: { width: 1600, height: 1010, channels: 4, background: "#0B1220" } });
const composites = [];
for (let index = 0; index < slides.length; index += 1) {
  const input = await sharp(slides[index]).resize(thumbWidth, thumbHeight).png().toBuffer();
  const left = index < 2 ? 25 + index * 790 : 420;
  const top = index < 2 ? 25 : 557;
  composites.push({ input, left, top });
}
await whole.composite(composites).png().toFile(join(rendered, "whole-deck.png"));
await sharp(slides[2]).png().toFile(join(rendered, "representative-evidence-slide.png"));

function digest(path) { return fileDigest(path); }
const manifest = {
  slide_count: 3,
  release_status: "release_candidate",
  activation_eligible: false,
  evidence_binding: {
    git_commit: currentCommit,
    verification_manifest: { path: relative(root, verificationPath), sha256: digest(verificationPath) },
    report_record_digest: verification.report_record_digest,
    browser_checks: browserCheckCount,
    public_cases: publicCaseCount,
  },
  pptx: { path: relative(root, paths.pptx), sha256: digest(paths.pptx) },
  inputs: Object.fromEntries(Object.entries(paths).filter(([key]) => key !== "pptx").map(([key, path]) => [key, { path: relative(root, path), sha256: digest(path) }])),
  rendered: Object.fromEntries(slides.map((path, index) => [`slide_${index + 1}`, { path: relative(root, path), sha256: digest(path) }])),
};
writeFileSync(join(deckRoot, "build-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
writeFileSync(join(deckRoot, "quality-scorecard.md"), `# Science Verifier Evidence Deck Quality Scorecard\n\n- Slide count: 3/3\n- Editable PPTX: PASS\n- Per-slide PNG: PASS\n- Whole-deck preview: PASS\n- Actual UI evidence: PASS\n- Actual final report evidence: PASS\n- Release inactive boundary visible: PASS\n- G5–G7 PENDING visible: PASS\n- Aspect ratio distortion: automated render available; human visual inspection: PENDING\n- Text overflow/collision: human visual inspection: PENDING\n`);
console.log(JSON.stringify(manifest, null, 2));
