from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RepairCandidate:
    path: Path
    boi_id: str
    event_type: str


def md_link(label: str, uri: str) -> str:
    return f"[{label}]({uri})" if uri else label


def stage_from_sop_doc(sop_doc: dict[str, Any] | None, stage_id: str | None) -> dict[str, Any]:
    if not sop_doc or not stage_id:
        return {}
    workflow = (sop_doc.get("metadata") or {}).get("workflow") or {}
    stages = workflow.get("stages") or []
    for stage in stages:
        if isinstance(stage, dict) and str(stage.get("id") or "") == str(stage_id):
            return stage
    return {}


def action_detail_line(detail: dict[str, Any]) -> str:
    if detail.get("missing"):
        return f"- `{detail.get('action_key')}`: catalog entry missing"
    action_key = str(detail.get("action_key") or "")
    label = str(detail.get("name_ko") or action_key)
    doc_uri = str(detail.get("doc_uri") or "")
    action_ref = md_link(label, doc_uri)
    manual_note = f" / requires_manual_action=`{detail.get('requires_manual_action')}`" if detail.get("requires_manual_action") else ""
    return (
        f"- `{action_key}`: {action_ref}"
        f" / connector={detail.get('connector_kind')}"
        f" / risk={detail.get('risk_level')}"
        f" / approval_required={detail.get('approval_required')}"
        f"{manual_note}"
    )


def details_markdown(details: list[dict[str, Any]]) -> str:
    return "\n".join(action_detail_line(detail) for detail in details) if details else "- 등록된 Action 없음"


def list_markdown(values: Any) -> str:
    if not values:
        return "- 없음"
    if not isinstance(values, list):
        values = [values]
    return "\n".join(f"- {value}" for value in values)


def payload_facts(payload: dict[str, Any]) -> str:
    rows = [
        ("equipment_id", "Equipment"),
        ("lot_id", "Lot"),
        ("wafer_id", "Wafer"),
        ("alarm_code", "Alarm"),
        ("case_id", "Case"),
        ("request_id", "Request"),
        ("customer_id", "Customer"),
        ("system_id", "System"),
        ("owner", "Owner"),
    ]
    lines = [f"- {label}: `{payload.get(key)}`" for key, label in rows if payload.get(key)]
    known_keys = {key for key, _label in rows} | {"title", "workflow"}
    for key, value in payload.items():
        if key in known_keys or not isinstance(value, (str, int, float, bool)):
            continue
        lines.append(f"- {key}: `{value}`")
        if len(lines) >= 12:
            break
    return "\n".join(lines) if lines else "- Payload에 핵심 식별자가 없습니다."


def event_type_link(event_type: str, label: str | None = None) -> str:
    return md_link(label or event_type, f"/public/event-types/{event_type}.md")


def render_stage_execution_body(
    *,
    event: dict[str, Any],
    payload: dict[str, Any],
    event_def: dict[str, Any],
    sop_doc: dict[str, Any] | None,
    sop_ref: str,
    sop_uri: str,
    sop_title: str,
    event_label: str,
    action_details: list[dict[str, Any]],
    manual_action_details: list[dict[str, Any]],
    event_labels: dict[str, str] | None = None,
) -> str:
    event_type = str(event.get("event_type") or "")
    stage_id = str(event_def.get("sop_stage_id") or "")
    stage = stage_from_sop_doc(sop_doc, stage_id)
    stage_name = str(event_def.get("workflow_stage") or stage.get("name") or "SOP Stage")
    default_flow = str(event_def.get("default_flow_key") or "")
    emits_event = str(stage.get("emits_event") or "")
    next_stage = stage.get("next_stage") or ""
    sop_link = md_link(sop_title or sop_ref, sop_uri)
    next_event_label = (event_labels or {}).get(emits_event, emits_event)
    next_event_line = event_type_link(emits_event, next_event_label) if emits_event and emits_event != "None" else "없음"
    title = payload.get("title") or stage_name
    purpose = stage.get("purpose") or event_def.get("description") or event_def.get("wiki_usage") or "이 stage의 업무 맥락을 실행 기록으로 남깁니다."
    outputs = list_markdown(stage.get("outputs") or [])
    failure_modes = list_markdown(stage.get("failure_modes") or [])
    source_systems = list_markdown(stage.get("source_systems") or [])
    evidence_refs = list_markdown(stage.get("evidence_refs") or [])

    return f"""# Summary

`{title}` 이벤트를 기준으로 `{stage_name}` stage의 실행 기록을 생성했습니다. 이 문서는 PoC 구조 설명이 아니라, trace `{event.get('trace_id') or ''}`에서 확인해야 할 입력, action 계획, manual handoff, 다음 stage를 추적하는 Private BoI입니다.

# Event Snapshot

| Field | Value |
|---|---|
| Event Type | {event_type_link(event_type, event_label)} |
| Event ID | `{event.get('event_id') or ''}` |
| Trace ID | `{event.get('trace_id') or ''}` |
| Occurred At | `{event.get('occurred_at') or ''}` |
| Default Flow | `{default_flow}` |

# SOP Stage

- SOP: {sop_link}
- Stage: `{stage_id}` / {stage_name}
- Purpose: {purpose}
- Source Systems:
{source_systems}
- Expected Outputs:
{outputs}
- Failure Modes:
{failure_modes}

# Evidence / Inputs

{payload_facts(payload)}

## Evidence References

{evidence_refs}

## Event Payload

```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```

# Action Plan

## Automated Actions

{details_markdown(action_details)}

# Manual Handoff

{details_markdown(manual_action_details)}

# Next Stage

- Next Stage: `{next_stage or 'complete'}`
- Emits Event: {next_event_line}

# Action Results

pending enrichment

# Citations

[1] Source Event `{event.get('event_id') or ''}` / trace `{event.get('trace_id') or ''}`
[2] {sop_link}
"""


def extract_response_payload(result: dict[str, Any]) -> Any:
    response = result.get("response")
    if isinstance(response, dict):
        if "result" in response:
            return response["result"]
        return response
    if "mock_response" in result:
        return result["mock_response"]
    if "manual_handoff" in result:
        return result["manual_handoff"]
    return result


def compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("message", "text"):
            found = first_text(value.get(key))
            if found:
                return found
        for child in value.values():
            found = first_text(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = first_text(child)
            if found:
                return found
    return ""


ARCHITECTURE_ANALYSIS_TERMS = (
    "업무 맥락 자산화",
    "Event Broker",
    "Action Gateway",
    "Team BoI",
    "승격 기준",
    "AI Native Workflow Designer",
    "SK하이닉스 BoI Wiki PoC",
    "PoC 아키텍처",
)


def sanitize_stage_analysis_message(message: str) -> str:
    lines = message.splitlines()
    cleaned: list[str] = []
    skip_section = False
    for line in lines:
        stripped = line.strip()
        is_heading = bool(re.match(r"^#{1,6}\s+", stripped))
        if is_heading:
            skip_section = any(term in stripped for term in ARCHITECTURE_ANALYSIS_TERMS)
            if skip_section:
                continue
        elif skip_section:
            continue
        if any(term in stripped for term in ARCHITECTURE_ANALYSIS_TERMS):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def table_safe_summary(value: str, limit: int = 500) -> str:
    summary = re.sub(r"\s+", " ", value).strip()
    summary = summary.replace("|", "\\|")
    return summary[:limit] + ("..." if len(summary) > limit else "")


def action_result_summary(action_key: str, result: dict[str, Any]) -> str:
    payload = extract_response_payload(result)
    message = first_text(payload) or first_text(result)
    if action_key == "langflow.equipment.stage_analysis":
        message = sanitize_stage_analysis_message(message)
    important = []
    if isinstance(payload, dict):
        for key in (
            "trend_status",
            "raw_data_ref",
            "source_data_ref",
            "guide_boi_ref",
            "notification_status",
            "requested_state",
            "requested_change",
            "approved_by",
        ):
            if payload.get(key):
                important.append(f"{key}={payload[key]}")
    summary = " / ".join(important) if important else message
    if action_key == "langflow.equipment.stage_analysis" and not summary:
        return "Langflow result unavailable"
    return summary or compact_json(payload)


def render_action_results(dispatch_result: dict[str, Any]) -> tuple[str, str]:
    rows = []
    analysis_messages = []
    for item in dispatch_result.get("results") or []:
        action_key = str(item.get("action_key") or "")
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        status = str(result.get("status") or item.get("status_code") or item.get("error") or "unknown")
        request_id = str(result.get("request_id") or "")
        summary = str(item.get("summary") or "")
        if action_key == "langflow.equipment.stage_analysis":
            summary = sanitize_stage_analysis_message(summary)
        if not summary:
            summary = action_result_summary(action_key, result) if result else compact_json(item.get("error") or "")
        summary = table_safe_summary(summary)
        rows.append(f"| `{action_key}` | `{status}` | `{request_id}` | {summary} |")
        if action_key == "langflow.equipment.stage_analysis":
            message = str(result.get("message") or first_text(result.get("response")) or "").strip()
            if message:
                analysis_messages.append(sanitize_stage_analysis_message(message) or "Langflow result unavailable")
            elif status in {"failed", "error"} or item.get("error"):
                analysis_messages.append("Langflow result unavailable")
    table = "\n".join(["| Action | Status | Request | Summary |", "|---|---|---|---|", *rows]) if rows else "No action results were recorded."
    analysis = "\n\n".join(f"- {message}" for message in analysis_messages) if analysis_messages else ""
    return table, analysis


def replace_or_insert_section(body: str, heading: str, content: str) -> tuple[str, bool]:
    section = f"# {heading}"
    replacement = f"{section}\n\n{content.strip()}\n\n"
    pattern = re.compile(rf"^{re.escape(section)}\n.*?(?=^# |\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(body):
        return pattern.sub(replacement, body).rstrip() + "\n", True
    citations = re.search(r"^# Citations\b", body, flags=re.MULTILINE)
    if citations:
        return (body[: citations.start()] + replacement + body[citations.start():]).rstrip() + "\n", True
    return body.rstrip() + "\n\n" + replacement, False


def build_enriched_body(original_body: str, dispatch_result: dict[str, Any]) -> tuple[str, list[str]]:
    action_results, analysis = render_action_results(dispatch_result)
    body, _ = replace_or_insert_section(original_body, "Action Results", action_results)
    sections = ["Action Results"]
    if analysis:
        body, _ = replace_or_insert_section(body, "Analysis Draft", analysis)
        sections.append("Analysis Draft")
    return body, sections


def split_frontmatter_text(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return yaml.safe_load(parts[1]) or {}, parts[2].lstrip("\n")
    return {}, text


def is_private_generated_workflow_doc(metadata: dict[str, Any], body: str) -> bool:
    author = metadata.get("author") or {}
    source_event = metadata.get("source_event") or {}
    event_type = str(metadata.get("event_type") or source_event.get("event_type") or "")
    return (
        metadata.get("visibility") == "private"
        and str((author or {}).get("agent_id") or "").startswith("boi-writer-")
        and bool(event_type)
        and "# AI Native Workflow Interpretation" in body
    )


def find_repair_candidates(root: Path) -> list[RepairCandidate]:
    candidates: list[RepairCandidate] = []
    for path in sorted(root.glob("private/*/*.md")):
        try:
            metadata, body = split_frontmatter_text(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if is_private_generated_workflow_doc(metadata, body):
            candidates.append(
                RepairCandidate(
                    path=path,
                    boi_id=str(metadata.get("boi_id") or ""),
                    event_type=str(metadata.get("event_type") or ""),
                )
            )
    return candidates


def rewrite_legacy_text(text: str) -> str:
    metadata, body = split_frontmatter_text(text)
    body, _ = replace_or_insert_section(
        body,
        "AI Native Workflow Interpretation",
        "Legacy boilerplate removed. This document was generated before stage-aware workflow materialization was introduced.",
    )
    body = body.replace("# AI Native Workflow Interpretation", "# Legacy Notes")
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body.lstrip("\n")
