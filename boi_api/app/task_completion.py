from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping


COMPLETION_VERSION = 1
TASK_MODES = {"manual", "copilot", "autopilot"}
CONFIRMATION_KINDS = {"human", "system"}
SOURCE_KINDS = {
    "boi",
    "event",
    "action_result",
    "data_artifact",
    "file",
    "human_note",
    "external_ai",
}
PROVIDER_KINDS = {"human", "agent", "system"}
BINDING_KINDS = {"none", "event", "action_result", "artifact", "data_field", "state"}
SYSTEM_BINDING_KINDS = BINDING_KINDS - {"none"}

_TECHNICAL_REF_RE = re.compile(
    r"(?:boi:[A-Za-z0-9_.:/-]+|(?:event|action|workflow|skill|data):[A-Za-z0-9_.:/-]+|[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+){2,})"
)

_IDENTIFIER_LABELS = {
    "alarm": "Alarm 내용",
    "alarm_context": "Alarm 맥락",
    "trend": "Trend 그래프",
    "trend_history": "Trend 이력",
    "raw_data": "Raw Data",
    "review_note": "담당자 검토 기록",
    "action_results": "Action 결과",
    "current_event": "현재 업무 이벤트",
    "maintenance_guide": "보전 가이드",
    "approval_result": "승인 결과",
}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[\n,]", value) if item.strip()]
    return [value]


def _stable_id(prefix: str, value: str, index: int) -> str:
    digest = hashlib.sha256(f"{prefix}:{index}:{value}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _clean_lookup(label_lookup: Mapping[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (label_lookup or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            result[clean_key] = clean_value
            result.setdefault(clean_key.lower(), clean_value)
    return result


def _lookup_label(value: str, lookup: Mapping[str, str]) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    candidates = [
        clean,
        clean.lower(),
        f"event:{clean}",
        f"action:{clean}",
        f"workflow:{clean}",
        f"skill:{clean}",
    ]
    for candidate in candidates:
        if candidate in lookup:
            return str(lookup[candidate])
    return ""


def _find_known_ref(value: str, lookup: Mapping[str, str]) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if clean in lookup or clean.lower() in lookup:
        return clean
    for candidate in sorted((key for key in lookup if len(key) >= 7), key=len, reverse=True):
        if candidate.lower() in clean.lower():
            return candidate
    for candidate in _TECHNICAL_REF_RE.findall(clean):
        if _lookup_label(candidate, lookup):
            return candidate
        if candidate.startswith(("boi:", "event:", "action:", "workflow:", "data:")):
            return candidate
    return ""


def _binding_kind(ref: str, source_kind: str = "") -> str:
    lowered = str(ref or "").lower()
    if (
        source_kind == "event"
        or lowered.startswith("event:")
        or ":event-types:" in lowered
        or bool(re.fullmatch(r"[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+\.v\d+", lowered))
    ):
        return "event"
    if source_kind == "action_result" or lowered.startswith("action:"):
        return "action_result"
    if source_kind == "data_artifact" or lowered.startswith("data:"):
        return "artifact"
    if "status" in lowered or "state" in lowered:
        return "state"
    return "none"


def _source_kind(ref: str, fallback: str = "") -> str:
    if fallback in SOURCE_KINDS:
        return fallback
    lowered = str(ref or "").lower()
    if lowered.startswith("event:") or ":event-types:" in lowered:
        return "event"
    if lowered.startswith("action:"):
        return "action_result"
    if lowered.startswith("data:") or "artifact" in lowered:
        return "data_artifact"
    if lowered.startswith(("boi:", "workflow:", "skill:")):
        return "boi"
    return "human_note"


def _friendly_identifier(value: str) -> str:
    clean = str(value or "").strip()
    if clean in _IDENTIFIER_LABELS:
        return _IDENTIFIER_LABELS[clean]
    if re.fullmatch(r"[A-Za-z0-9_-]+", clean) and ("_" in clean or "-" in clean):
        return clean.replace("_", " ").replace("-", " ").strip()
    return clean


def friendly_label(value: str, label_lookup: Mapping[str, str] | None = None, *, check: bool = False) -> str:
    lookup = _clean_lookup(label_lookup)
    raw = str(value or "").strip()
    if not raw:
        return ""
    ref = _find_known_ref(raw, lookup)
    resolved = _lookup_label(ref or raw, lookup)
    if raw == ref and resolved:
        return resolved

    text = raw
    if ref and resolved:
        text = re.sub(re.escape(ref), resolved, text, flags=re.IGNORECASE)
    if check and "시작 트리거" in text:
        return f"{resolved or '업무 신호'} 접수가 확인되어 업무를 시작할 수 있어요"
    if check and "업무 흐름 입력으로 전달" in text:
        return f"{resolved} 결과를 다음 Task에 전달했어요" if resolved else "확인한 내용을 다음 Task에 전달했어요"
    if check and "Task로 연결" in text:
        return "다음 Task로 이어갈 준비가 되었어요"
    if check and "전달 가능" in text:
        return "확인 결과를 다음 Task에 전달할 준비가 되었어요"
    if check:
        text = text.replace("식별됨", "확인되었어요")
        text = text.replace("확인됨", "확인되었어요")
        text = text.replace("기록됨", "기록되었어요")
        text = text.replace("전달됨", "전달되었어요")
        text = text.replace("완료됨", "완료되었어요")
        text = text.replace("확보됨", "확보했어요")
        text = text.replace("생성됨", "생성되었어요")
        text = text.replace("검토됨", "검토했어요")
        if text.endswith("됨"):
            text = text[:-1] + "었어요"
    return _friendly_identifier(text)


def _normalise_binding(value: Any, *, fallback_ref: str = "", source_kind: str = "") -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    ref = str(raw.get("ref") or fallback_ref or "").strip()
    kind = str(raw.get("kind") or _binding_kind(ref, source_kind)).strip().lower()
    if kind not in BINDING_KINDS:
        kind = "none"
    binding = {
        "kind": kind,
        "ref": ref,
        "field": str(raw.get("field") or "").strip(),
        "operator": str(raw.get("operator") or "").strip(),
        "value": raw.get("value"),
    }
    if kind == "none" and not any(binding[key] for key in ("ref", "field", "operator")) and binding["value"] is None:
        return {}
    return binding


def normalise_completion_design(
    task: Mapping[str, Any],
    *,
    label_lookup: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    lookup = _clean_lookup(label_lookup)
    mode = str(task.get("execution_mode") or "copilot").strip().lower()
    if mode not in TASK_MODES:
        mode = "copilot"
    raw_design = task.get("completion_design") if isinstance(task.get("completion_design"), dict) else {}

    raw_checks = raw_design.get("checks") if isinstance(raw_design.get("checks"), list) else []
    legacy_checks = [str(item).strip() for item in _list(task.get("exit_criteria")) if str(item).strip()]
    design_check_projection = [
        str(item.get("label") or "").strip()
        for item in raw_checks
        if isinstance(item, dict) and str(item.get("label") or "").strip()
    ]
    if legacy_checks and raw_checks and legacy_checks != design_check_projection:
        raw_checks = [{"label": item} for item in legacy_checks]
    if not raw_checks:
        raw_checks = [{"label": item} for item in legacy_checks]
    checks: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_checks):
        item = raw_item if isinstance(raw_item, dict) else {"label": str(raw_item or "")}
        raw_label = str(item.get("label") or item.get("text") or "").strip()
        inferred_ref = str((item.get("binding") or {}).get("ref") or "") if isinstance(item.get("binding"), dict) else ""
        inferred_ref = inferred_ref or _find_known_ref(raw_label, lookup)
        binding = _normalise_binding(item.get("binding"), fallback_ref=inferred_ref)
        label = friendly_label(raw_label or inferred_ref, lookup, check=True)
        if not label:
            continue
        confirmation = str(item.get("confirmation") or ("system" if mode == "autopilot" else "human")).lower()
        if confirmation not in CONFIRMATION_KINDS:
            confirmation = "system" if mode == "autopilot" else "human"
        checks.append(
            {
                "check_id": str(item.get("check_id") or _stable_id("check", inferred_ref or label, index)),
                "label": label,
                "confirmation": confirmation,
                "binding": binding,
            }
        )

    raw_evidence = raw_design.get("evidence") if isinstance(raw_design.get("evidence"), list) else []
    legacy_evidence = [str(item).strip() for item in _list(task.get("required_evidence")) if str(item).strip()]
    design_evidence_projection = [
        str(item.get("ref") or item.get("label") or "").strip()
        for item in raw_evidence
        if isinstance(item, dict) and str(item.get("ref") or item.get("label") or "").strip()
    ]
    if legacy_evidence and raw_evidence and legacy_evidence != design_evidence_projection:
        raw_evidence = [{"label": item} for item in legacy_evidence]
    if not raw_evidence:
        raw_evidence = [{"label": item} for item in legacy_evidence]
    evidence: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_evidence):
        item = raw_item if isinstance(raw_item, dict) else {"label": str(raw_item or "")}
        raw_label = str(item.get("label") or item.get("title") or item.get("ref") or "").strip()
        ref = str(item.get("ref") or _find_known_ref(raw_label, lookup)).strip()
        if not ref and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", raw_label) and ("_" in raw_label or "-" in raw_label):
            ref = raw_label
        source_kind = _source_kind(ref, str(item.get("source_kind") or "").strip().lower())
        label = friendly_label(raw_label or ref, lookup)
        if not label:
            continue
        default_provider = "human" if mode == "manual" else "system" if mode == "autopilot" else "agent"
        provided_by = str(item.get("provided_by") or default_provider).strip().lower()
        if provided_by not in PROVIDER_KINDS:
            provided_by = default_provider
        evidence.append(
            {
                "evidence_id": str(item.get("evidence_id") or _stable_id("evidence", ref or label, index)),
                "label": label,
                "source_kind": source_kind,
                "ref": ref,
                "provided_by": provided_by,
                "required": bool(item.get("required", True)),
            }
        )

    label_counts: dict[str, int] = {}
    for item in evidence:
        label_counts[item["label"]] = label_counts.get(item["label"], 0) + 1
    for item in evidence:
        if label_counts.get(item["label"], 0) < 2:
            continue
        ref = str(item.get("ref") or "")
        if ref.startswith("workflow:"):
            item["label"] = f"{item['label']} · 업무 흐름 정의"
        elif ":workflows:" in ref:
            item["label"] = f"{item['label']} · BoI 문서"

    return {"version": COMPLETION_VERSION, "checks": checks, "evidence": evidence}


def completion_readiness(task: Mapping[str, Any], design: Mapping[str, Any] | None = None) -> dict[str, Any]:
    mode = str(task.get("execution_mode") or "copilot").strip().lower()
    model = dict(design or normalise_completion_design(task))
    checks = [item for item in model.get("checks") or [] if isinstance(item, dict)]
    evidence = [item for item in model.get("evidence") or [] if isinstance(item, dict)]
    if not checks or not evidence:
        return {
            "status": "incomplete",
            "label": "완료 항목을 더 적어주세요",
            "automation_ready": False,
            "unresolved_check_ids": [str(item.get("check_id") or "") for item in checks],
            "unresolved_evidence_ids": [str(item.get("evidence_id") or "") for item in evidence],
        }
    if mode != "autopilot":
        return {
            "status": "human_confirmation",
            "label": "담당자 확인으로 완료",
            "automation_ready": False,
            "unresolved_check_ids": [],
            "unresolved_evidence_ids": [],
        }

    unresolved_checks = []
    for item in checks:
        binding = item.get("binding") if isinstance(item.get("binding"), dict) else {}
        has_target = bool(binding.get("ref") or binding.get("field"))
        if item.get("confirmation") != "system" or binding.get("kind") not in SYSTEM_BINDING_KINDS or not has_target:
            unresolved_checks.append(str(item.get("check_id") or ""))
    unresolved_evidence = []
    for item in evidence:
        if not item.get("required"):
            continue
        if item.get("provided_by") != "system" or not str(item.get("ref") or "").strip():
            unresolved_evidence.append(str(item.get("evidence_id") or ""))
    ready = not unresolved_checks and not unresolved_evidence
    return {
        "status": "ready" if ready else "needs_connection",
        "label": "자동 확인 가능" if ready else "연결 필요",
        "automation_ready": ready,
        "unresolved_check_ids": unresolved_checks,
        "unresolved_evidence_ids": unresolved_evidence,
    }


def normalise_task_completion(
    task: Mapping[str, Any],
    *,
    label_lookup: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result = dict(task)
    design = normalise_completion_design(result, label_lookup=label_lookup)
    result["completion_design"] = design
    result["completion_readiness"] = completion_readiness(result, design)
    result["exit_criteria"] = [str(item.get("label") or "") for item in design["checks"] if item.get("label")]
    result["required_evidence"] = [
        str(item.get("ref") or item.get("label") or "")
        for item in design["evidence"]
        if item.get("ref") or item.get("label")
    ]
    return result
