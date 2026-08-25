const SHA256 = /^sha256:[0-9a-f]{64}$/;
const IDENTIFIER = /^[a-z][a-z0-9_.:-]*$/;

function codePoints(value) {
  return Array.from(String(value || ""));
}

function codePointSlice(value, start, end) {
  return codePoints(value).slice(start, end).join("");
}

function exactSpan(documentText, start, end) {
  const text = codePoints(documentText);
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length) {
    throw new Error("주장 구간이 문서의 Unicode code-point 범위와 일치하지 않습니다.");
  }
  return {
    offset_encoding: "unicode_code_point",
    start,
    end,
    exact: text.slice(start, end).join(""),
    prefix: text.slice(Math.max(0, start - 64), start).join(""),
    suffix: text.slice(end, end + 64).join(""),
  };
}

function parseScalar(raw) {
  const value = raw.trim();
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null") return null;
  if (/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value)) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) throw new Error("조건 값은 유한한 수여야 합니다.");
    return numeric;
  }
  return value;
}

export function parseConditions(value) {
  const results = [];
  const seen = new Set();
  for (const line of String(value || "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const separator = trimmed.indexOf("=");
    if (separator <= 0) throw new Error("조건은 condition_id=value 형식으로 입력하세요.");
    const conditionId = trimmed.slice(0, separator).trim();
    if (!IDENTIFIER.test(conditionId)) throw new Error(`조건 ID 형식을 확인하세요: ${conditionId}`);
    if (seen.has(conditionId)) throw new Error(`중복된 조건입니다: ${conditionId}`);
    seen.add(conditionId);
    const operand = trimmed.slice(separator + 1).trim();
    if (!operand) throw new Error(`조건 값이 필요합니다: ${conditionId}`);
    const parts = operand.split(/\s+/);
    const scalar = parseScalar(parts[0]);
    const unit = parts.length > 1 ? parts.slice(1).join(" ") : null;
    if (unit && typeof scalar !== "number") throw new Error(`단위는 수치 조건에만 쓸 수 있습니다: ${conditionId}`);
    results.push({ condition_id: conditionId, value: scalar, unit });
  }
  return results;
}

function validateMatch(documentText, match, claimStart, claimEnd) {
  if (!match || typeof match !== "object") throw new Error("주장 역할에 등록 용어를 선택하세요.");
  if (!match.ontology_ref || !match.concept_id || !match.surface_term || !match.meaning) {
    throw new Error("등록 용어의 ontology_ref·개념·표면형·의미가 완전하지 않습니다.");
  }
  if (!SHA256.test(String(match.binding_digest || ""))) throw new Error("등록 용어 digest가 올바르지 않습니다.");
  if (!Number.isInteger(match.start) || !Number.isInteger(match.end) || match.start < claimStart || match.end > claimEnd) {
    throw new Error("선택한 용어가 주장 구간 안에 없습니다.");
  }
  if (codePointSlice(documentText, match.start, match.end) !== match.surface_term) {
    throw new Error("선택한 용어가 현재 문서 구간과 일치하지 않습니다.");
  }
  return match;
}

export function buildManualCandidate({
  documentText,
  claimStart,
  claimEnd,
  matches,
  selected,
  relationKind,
  polarity,
  conditionsText = "",
  processStage = "",
  materialState = "",
}) {
  const span = exactSpan(documentText, claimStart, claimEnd);
  const roleOrder = ["subject", "relation", "object"];
  const indices = roleOrder.map((role) => Number(selected?.[role]));
  if (indices.some((index) => !Number.isInteger(index)) || new Set(indices).size !== 3) {
    throw new Error("주어·관계·목적어에 서로 다른 등록 용어를 선택하세요.");
  }
  const selectedMatches = Object.fromEntries(
    roleOrder.map((role, position) => [
      role,
      validateMatch(documentText, matches[indices[position]], claimStart, claimEnd),
    ]),
  );
  const ontologyRefs = [...new Set(roleOrder.map((role) => selectedMatches[role].ontology_ref))].sort();
  return {
    source_span: span,
    normalized_claim: {
      subject_concept_id: selectedMatches.subject.concept_id,
      relation_kind: relationKind,
      predicate: selectedMatches.relation.concept_id,
      object_concept_id: selectedMatches.object.concept_id,
      polarity,
      quantities: [],
      conditions: parseConditions(conditionsText),
      process_stage: processStage.trim() || null,
      material_state: materialState.trim() || null,
    },
    ontology_refs: ontologyRefs,
    ambiguity_ids: [],
    candidate_meanings: roleOrder.map((role) => ({
      ambiguity_id: null,
      concept_role: role,
      surface_term: selectedMatches[role].surface_term,
      ontology_ref: selectedMatches[role].ontology_ref,
      meaning: selectedMatches[role].meaning,
    })),
    decision_impact: [],
  };
}

function locatorIsExact(locator) {
  if (!locator || typeof locator !== "object") return false;
  return [
    "section", "equation", "printed_page", "pdf_page_index", "paragraph",
    "figure", "table", "resource_url", "requested_url", "resolved_url",
  ].some((key) => locator[key] !== undefined && locator[key] !== null && String(locator[key]).trim() !== "");
}

export function trustedViolationState(verdict, annotations, operational) {
  if (!operational || verdict?.verdict !== "VIOLATION") return false;
  if (!Array.isArray(verdict.decisive_rule_ids) || verdict.decisive_rule_ids.length === 0) return false;
  if (!Array.isArray(verdict.condition_evaluations) || verdict.condition_evaluations.length === 0) return false;
  if (verdict.condition_evaluations.some((item) => item?.satisfied !== true)) return false;
  if (!Array.isArray(verdict.evidence_refs) || verdict.evidence_refs.length === 0) return false;
  const links = (Array.isArray(annotations) ? annotations : []).flatMap((annotation) => annotation?.evidence_links || []);
  if (links.length === 0) return false;
  const linkedIds = new Set(links.map((link) => link?.evidence_id));
  if (verdict.evidence_refs.some((ref) => !linkedIds.has(ref))) return false;
  return links.every((link) => (
    Boolean(link?.evidence_id)
    && locatorIsExact(link?.locator)
    && link?.reviewed_source?.qualification_state === "active"
    && /^https:\/\//.test(String(link?.url || ""))
  ));
}

export function codePointLength(value) {
  return codePoints(value).length;
}
