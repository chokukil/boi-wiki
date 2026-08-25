const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const XMLNS_NAMESPACE = "http://www.w3.org/2000/xmlns/";
const SHA256_PATTERN = /^sha256:[0-9a-f]{64}$/;
const SAFE_GEOMETRY = /^[A-Za-z0-9+.,()\-\s]*$/;
const SAFE_COLOR = /^(?:currentColor|none|transparent|#[0-9a-f]{3,8})$/i;
const ALLOWED_TAGS = new Set([
  "svg", "g", "path", "rect", "line", "polyline", "polygon", "circle", "ellipse",
]);
const ALLOWED_ATTRIBUTES = new Set([
  "width", "height", "role", "focusable", "viewBox", "preserveAspectRatio",
  "aria-label", "stroke", "fill", "stroke-width", "transform", "d", "x", "y",
  "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "points",
]);
const MAX_SVG_BYTES = 512 * 1024;
const MAX_ELEMENTS = 50_000;
const MAX_DEPTH = 256;

function textNode(documentRef, tag, value, className = "") {
  const node = documentRef.createElement(tag);
  node.textContent = String(value ?? "");
  if (className) node.className = className;
  return node;
}

function validReference(reference) {
  return reference
    && typeof reference.equation_id === "string"
    && SHA256_PATTERN.test(reference.equation_digest || "");
}

export function resolveEquationAssets(report, claimId) {
  if (!report || typeof report !== "object" || typeof claimId !== "string") return [];
  if (!Array.isArray(report.explanations) || !Array.isArray(report.equation_assets)) return [];
  const references = report.explanations
    .filter((explanation) => explanation?.claim_id === claimId && Array.isArray(explanation.equation_refs))
    .flatMap((explanation) => explanation.equation_refs)
    .filter(validReference);
  const resolved = [];
  const seen = new Set();
  for (const reference of references) {
    const identity = `${reference.equation_id}\n${reference.equation_digest}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    const matches = report.equation_assets.filter(
      (asset) => asset?.equation_id === reference.equation_id
        && asset?.equation_digest === reference.equation_digest,
    );
    if (matches.length === 1) resolved.push(matches[0]);
  }
  return resolved;
}

export function equationEvidenceLinks(assets) {
  if (!Array.isArray(assets)) return [];
  return assets
    .flatMap((asset) => Array.isArray(asset?.evidence_links) ? asset.evidence_links : [])
    .filter((link) => {
      if (typeof link?.evidence_id !== "string" || typeof link?.source_id !== "string" || typeof link?.url !== "string") return false;
      try {
        const url = new URL(link.url);
        return url.protocol === "https:" && !url.username && !url.password;
      } catch {
        return false;
      }
    });
}

async function sha256(value, cryptoRef) {
  if (!cryptoRef?.subtle || typeof cryptoRef.subtle.digest !== "function") return null;
  try {
    const bytes = new TextEncoder().encode(value);
    const digest = await cryptoRef.subtle.digest("SHA-256", bytes);
    return `sha256:${[...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join("")}`;
  } catch {
    return null;
  }
}

function validAttribute(attribute, root, asset) {
  const name = attribute.name;
  const lower = name.toLowerCase();
  if (attribute.namespaceURI === XMLNS_NAMESPACE) {
    return root === attribute.ownerElement && name === "xmlns" && attribute.value === SVG_NAMESPACE;
  }
  if (attribute.namespaceURI || lower === "style" || lower === "href" || lower.startsWith("on") || lower.startsWith("xlink:")) return false;
  if (!ALLOWED_ATTRIBUTES.has(name)) return false;
  if (name === "role") return attribute.value === "img";
  if (name === "focusable") return attribute.value === "false";
  if (name === "aria-label") return attribute.value === asset.accessibility_reading
    && attribute.value.trim().length > 0
    && attribute.value.length <= 1000
    && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(attribute.value);
  if (name === "stroke" || name === "fill") return SAFE_COLOR.test(attribute.value);
  return SAFE_GEOMETRY.test(attribute.value);
}

function validSvgTree(root, asset) {
  if (root?.namespaceURI !== SVG_NAMESPACE || root.localName !== "svg") return false;
  if (root.getAttribute("role") !== "img" || root.getAttribute("focusable") !== "false") return false;
  if (root.getAttribute("aria-label") !== asset.accessibility_reading) return false;
  for (const required of ["width", "height", "viewBox"]) if (!root.hasAttribute(required)) return false;
  const stack = [[root, 1]];
  let count = 0;
  while (stack.length) {
    const [element, depth] = stack.pop();
    count += 1;
    if (count > MAX_ELEMENTS || depth > MAX_DEPTH) return false;
    if (element.namespaceURI !== SVG_NAMESPACE || !ALLOWED_TAGS.has(element.localName)) return false;
    if (element !== root && element.localName === "svg") return false;
    for (const child of element.childNodes) {
      if (child.nodeType === 1) stack.push([child, depth + 1]);
      else if (child.nodeType === 3 && child.nodeValue.trim()) return false;
      else if (child.nodeType !== 3) return false;
    }
    for (const attribute of element.attributes) if (!validAttribute(attribute, root, asset)) return false;
  }
  return true;
}

async function validatedSvgNode(asset, options) {
  const svg = asset?.sanitized_svg;
  if (typeof svg !== "string" || !SHA256_PATTERN.test(asset?.svg_digest || "")) return null;
  const bytes = new TextEncoder().encode(svg);
  if (bytes.length > MAX_SVG_BYTES) return null;
  if (/<!\s*(?:DOCTYPE|ENTITY)\b/i.test(svg) || /<\?|<!--|\bxmlns\s*:/i.test(svg)) return null;
  const actualDigest = await sha256(svg, options.crypto);
  if (actualDigest !== asset.svg_digest) return null;
  let parsed;
  try {
    parsed = new options.DOMParser().parseFromString(svg, "image/svg+xml");
  } catch {
    return null;
  }
  if (parsed.doctype || parsed.querySelector("parsererror") || !validSvgTree(parsed.documentElement, asset)) return null;
  return options.document.importNode(parsed.documentElement, true);
}

function appendListSection(documentRef, parent, heading, values, formatter = (value) => value) {
  if (!Array.isArray(values) || !values.length) return;
  const section = documentRef.createElement("section");
  section.className = "science-equation-detail-section";
  section.appendChild(textNode(documentRef, "h5", heading));
  const list = documentRef.createElement("ul");
  for (const value of values) list.appendChild(textNode(documentRef, "li", formatter(value)));
  section.appendChild(list);
  parent.appendChild(section);
}

function variableText(variable) {
  if (!variable || typeof variable !== "object") return "변수 설명 없음";
  return [variable.symbol, variable.definition, variable.unit ? `[${variable.unit}]` : ""]
    .filter((value) => typeof value === "string" && value.trim())
    .join(" · ");
}

function copyButton(documentRef, label, value, success, status, writeClipboard) {
  const button = textNode(documentRef, "button", label, "secondary-button science-equation-copy");
  button.type = "button";
  button.setAttribute("aria-label", label);
  button.addEventListener("click", async () => {
    try {
      await writeClipboard(value);
      status.textContent = success;
    } catch {
      status.textContent = "복사할 수 없습니다. 직접 선택해 복사하세요.";
    }
  });
  return button;
}

async function mountResolvedAsset(container, asset, options) {
  const documentRef = options.document;
  const section = documentRef.createElement("section");
  section.className = "science-equation-view";
  section.dataset.equationId = String(asset.equation_id || "");
  section.dataset.equationDigest = String(asset.equation_digest || "");
  section.appendChild(textNode(documentRef, "h4", "검토된 수식"));

  const figure = documentRef.createElement("figure");
  const scroll = documentRef.createElement("div");
  scroll.className = "science-equation-scroll";
  scroll.tabIndex = 0;
  scroll.setAttribute("aria-label", "수식 표시 영역");
  const fallback = textNode(
    documentRef,
    "p",
    typeof asset.plain_text === "string" && asset.plain_text.trim()
      ? asset.plain_text
      : "수식을 표시할 수 없습니다.",
    "science-equation-fallback",
  );
  scroll.appendChild(fallback);
  figure.appendChild(scroll);
  section.appendChild(figure);

  const status = textNode(documentRef, "span", "", "science-equation-copy-status");
  status.setAttribute("aria-live", "polite");
  status.setAttribute("aria-atomic", "true");
  const actions = documentRef.createElement("div");
  actions.className = "science-equation-copy-actions";
  actions.append(
    copyButton(documentRef, "LaTeX 복사", String(asset.display_latex || ""), "LaTeX를 복사했습니다.", status, options.writeClipboard),
    copyButton(documentRef, "일반 텍스트 복사", fallback.textContent, "일반 텍스트를 복사했습니다.", status, options.writeClipboard),
    status,
  );
  section.appendChild(actions);

  const details = documentRef.createElement("details");
  details.className = "science-equation-details";
  details.appendChild(textNode(documentRef, "summary", "변수·적용 조건·한계"));
  const detailList = documentRef.createElement("div");
  detailList.className = "science-equation-detail-list";
  appendListSection(documentRef, detailList, "변수", asset.variables, variableText);
  appendListSection(documentRef, detailList, "적용 조건", asset.applicability);
  appendListSection(documentRef, detailList, "적용 범위 밖", asset.invalid_outside);
  details.appendChild(detailList);
  section.appendChild(details);
  container.appendChild(section);

  let svgNode = null;
  try {
    svgNode = await validatedSvgNode(asset, options);
  } catch {
    svgNode = null;
  }
  if (svgNode) {
    scroll.appendChild(svgNode);
    fallback.hidden = true;
  }
  return section;
}

function defaultClipboard(value) {
  if (!globalThis.navigator?.clipboard?.writeText) return Promise.reject(new Error("clipboard unavailable"));
  return globalThis.navigator.clipboard.writeText(value);
}

export async function mountResolvedEquationAssets(container, assets, overrides = {}) {
  if (!container?.ownerDocument || !Array.isArray(assets)) return [];
  const options = {
    document: container.ownerDocument,
    DOMParser: globalThis.DOMParser,
    crypto: globalThis.crypto,
    writeClipboard: defaultClipboard,
    ...overrides,
  };
  if (typeof options.DOMParser !== "function") return [];
  return Promise.all(assets.map((asset) => mountResolvedAsset(container, asset, options)));
}

export async function mountEquationAssets(container, report, claimId, overrides = {}) {
  return mountResolvedEquationAssets(container, resolveEquationAssets(report, claimId), overrides);
}
