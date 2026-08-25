#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { mathjax } from "@mathjax/src/js/mathjax.js";
import { liteAdaptor } from "@mathjax/src/js/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "@mathjax/src/js/handlers/html.js";
import { TeX } from "@mathjax/src/js/input/tex.js";
import "@mathjax/src/js/input/tex/ams/AmsConfiguration.js";
import "@mathjax/src/js/input/tex/mhchem/MhchemConfiguration.js";
import { SVG } from "@mathjax/src/js/output/svg.js";
import { MathJaxMhchemFontExtension } from "@mathjax/mathjax-mhchem-font-extension/js/svg.js";
import { MathJaxNewcmFont } from "@mathjax/mathjax-newcm-font/js/svg.js";


export const RENDERER_IDENTITY = Object.freeze({
  engine: "MathJax",
  version: "4.1.3",
  output: "sanitized-svg-paths",
  font: "MathJax-Newcm 4.1.3 with Mhchem extension 4.1.3",
});

const MAX_REQUEST_BYTES = 65536;
const MAX_LATEX_LENGTH = 4096;
const MAX_READING_LENGTH = 1000;
const FORBIDDEN_COMMAND = /\\(?:href|url|require|include|input|class|style|cssId|htmlClass|htmlId|htmlStyle|unicode|bbox|newcommand|renewcommand|def)\b/i;
const ALLOWED_TAGS = new Set([
  "svg",
  "g",
  "path",
  "rect",
  "line",
  "polyline",
  "polygon",
  "circle",
  "ellipse",
]);
const ALLOWED_ATTRIBUTES = new Set([
  "xmlns",
  "width",
  "height",
  "role",
  "focusable",
  "viewBox",
  "preserveAspectRatio",
  "stroke",
  "fill",
  "stroke-width",
  "transform",
  "d",
  "x",
  "y",
  "x1",
  "x2",
  "y1",
  "y2",
  "cx",
  "cy",
  "r",
  "rx",
  "ry",
  "points",
]);
const SAFE_GEOMETRY = /^[A-Za-z0-9+.,()\-\s]*$/;
const SAFE_COLOR = /^(?:currentColor|none|transparent|#[0-9a-f]{3,8})$/i;

let fontExtensionInstalled = false;


export class EquationRenderError extends Error {
  constructor(message) {
    super(message);
    this.name = "EquationRenderError";
  }
}


function installFontExtension() {
  if (!fontExtensionInstalled) {
    MathJaxNewcmFont.addExtension(MathJaxMhchemFontExtension);
    fontExtensionInstalled = true;
  }
}


function validateRequest(request) {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new EquationRenderError("request must be a JSON object");
  }
  const { latex, accessibility_reading: reading, display = true } = request;
  if (typeof latex !== "string" || latex.trim().length === 0) {
    throw new EquationRenderError("latex must be a non-empty string");
  }
  if (latex.length > MAX_LATEX_LENGTH) {
    throw new EquationRenderError("latex exceeds the 4096 character limit");
  }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(latex)) {
    throw new EquationRenderError("latex contains a forbidden control character");
  }
  if (FORBIDDEN_COMMAND.test(latex)) {
    throw new EquationRenderError("latex contains a command outside the local allowlist");
  }
  if (typeof reading !== "string" || reading.trim().length === 0) {
    throw new EquationRenderError("accessibility_reading must be a non-empty string");
  }
  if (reading.length > MAX_READING_LENGTH) {
    throw new EquationRenderError("accessibility_reading exceeds the 1000 character limit");
  }
  if (typeof display !== "boolean") {
    throw new EquationRenderError("display must be boolean");
  }
  return { latex, reading: reading.trim(), display };
}


function assertSafeAttribute(name, value) {
  if (!ALLOWED_ATTRIBUTES.has(name)) {
    throw new EquationRenderError(`renderer emitted unsupported SVG attribute: ${name}`);
  }
  if (name === "xmlns" && value !== "http://www.w3.org/2000/svg") {
    throw new EquationRenderError("renderer emitted an unexpected SVG namespace");
  }
  if ((name === "stroke" || name === "fill") && !SAFE_COLOR.test(value)) {
    throw new EquationRenderError(`renderer emitted unsafe ${name}`);
  }
  if (
    !["xmlns", "role", "focusable", "preserveAspectRatio", "stroke", "fill"].includes(name)
    && !SAFE_GEOMETRY.test(value)
  ) {
    throw new EquationRenderError(`renderer emitted unsafe SVG geometry: ${name}`);
  }
}


function sanitizeNode(adaptor, node) {
  const kind = adaptor.kind(node);
  if (!ALLOWED_TAGS.has(kind)) {
    throw new EquationRenderError(`renderer emitted unsupported SVG element: ${kind}`);
  }

  for (const { name, value } of adaptor.allAttributes(node)) {
    if (name === "style" || name.startsWith("data-")) {
      adaptor.removeAttribute(node, name);
      continue;
    }
    assertSafeAttribute(name, value);
  }

  for (const child of adaptor.childNodes(node)) {
    const childKind = adaptor.kind(child);
    if (childKind === "#comment" || childKind === "#text") {
      throw new EquationRenderError(`renderer emitted unsupported SVG node: ${childKind}`);
    }
    sanitizeNode(adaptor, child);
  }
}


export function renderEquation(request) {
  const { latex, reading, display } = validateRequest(request);
  installFontExtension();

  const adaptor = liteAdaptor();
  RegisterHTMLHandler(adaptor);
  const input = new TeX({
    packages: ["base", "ams", "mhchem"],
    maxBuffer: MAX_LATEX_LENGTH,
    maxTemplateSubtitutions: 50,
  });
  const output = new SVG({
    fontCache: "none",
    fontData: MathJaxNewcmFont,
  });
  const document = mathjax.document("", { InputJax: input, OutputJax: output });

  let container;
  try {
    container = document.convert(latex, { display });
  } catch (error) {
    throw new EquationRenderError(`local renderer rejected the expression: ${error.message}`);
  }

  for (const group of adaptor.tags(container, "g")) {
    if (adaptor.getAttribute(group, "data-mml-node") === "merror") {
      throw new EquationRenderError("local renderer produced a MathML error node");
    }
  }
  const roots = adaptor.tags(container, "svg");
  if (roots.length !== 1) {
    throw new EquationRenderError("local renderer did not produce exactly one SVG root");
  }
  const root = roots[0];
  sanitizeNode(adaptor, root);
  adaptor.setAttribute(root, "role", "img");
  adaptor.setAttribute(root, "focusable", "false");
  adaptor.setAttribute(root, "aria-label", reading);

  // aria-label is added after the structural sanitizer and serialized by the
  // local adaptor, which XML-escapes untrusted accessibility text.
  const svg = adaptor.serializeXML(root);
  if (/<(?:script|foreignObject|image|a)\b/i.test(svg) || /\b(?:href|xlink:href|on\w+)\s*=/i.test(svg)) {
    throw new EquationRenderError("sanitized SVG contains an external-capable element or attribute");
  }
  const svgDigest = `sha256:${createHash("sha256").update(svg, "utf8").digest("hex")}`;
  return {
    svg,
    svg_digest: svgDigest,
    renderer: RENDERER_IDENTITY,
  };
}


function failurePayload(error) {
  return {
    code: "science_equation_render_failed",
    detail: error instanceof Error ? error.message : String(error),
    rendering_effect: "none",
    verdict_effect: "none",
    red_mark_effect: "none",
  };
}


async function main() {
  try {
    const raw = readFileSync(0, "utf8");
    if (Buffer.byteLength(raw, "utf8") > MAX_REQUEST_BYTES) {
      throw new EquationRenderError("request exceeds the 64 KiB input limit");
    }
    const request = JSON.parse(raw);
    process.stdout.write(`${JSON.stringify(renderEquation(request))}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify(failurePayload(error))}\n`);
    process.exitCode = 2;
  }
}


if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
