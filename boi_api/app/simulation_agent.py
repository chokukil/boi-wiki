from __future__ import annotations

import json
import re
from typing import Any


REQUIRED_COVERAGE = [
    "sop_stage",
    "action_contract",
    "expected_output_schema",
    "prior_evidence",
    "manual_or_approval_condition",
    "next_stage_or_event",
]

COMMON_COVERAGE = [
    "sop_stage",
    "action_contract",
    "event_context",
    "output_schema",
    "next_event",
    "citation",
]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _lower_blob(value: Any) -> str:
    return _stringify(value).lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [item for item in _as_list(value) if isinstance(item, dict)]


def _doc_ref_candidates(ref: str) -> list[str]:
    text = str(ref or "").strip()
    if not text:
        return []
    candidates = [text]
    if text.startswith("boi:"):
        path = text.removeprefix("boi:").replace(":", "/")
        candidates.extend([path, f"/{path}.md", f"/{path}"])
    elif text.startswith("/"):
        candidates.append(text.removesuffix(".md").lstrip("/"))
    return list(dict.fromkeys(candidates))


def _doc_matches_ref(doc: dict[str, Any], ref: str) -> bool:
    metadata = doc.get("metadata") or {}
    uri = str(doc.get("uri") or "")
    path = str(doc.get("path") or "")
    body_id = str(metadata.get("boi_id") or "")
    haystack = {uri, uri.removeprefix("/"), uri.removesuffix(".md"), uri.removeprefix("/").removesuffix(".md"), path, body_id}
    return any(candidate in haystack for candidate in _doc_ref_candidates(ref))


def _doc_title(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata") or {}
    return str(metadata.get("title") or metadata.get("boi_id") or doc.get("uri") or "")


def _doc_boi_id(doc: dict[str, Any]) -> str:
    return str((doc.get("metadata") or {}).get("boi_id") or "")


def _doc_excerpt(doc: dict[str, Any], limit: int = 650) -> str:
    text = " ".join(str(doc.get("body") or "").split())
    return text[:limit].rstrip()


def _doc_summary(doc: dict[str, Any], *, role: str, match_reason: str) -> dict[str, str]:
    return {
        "role": role,
        "match_reason": match_reason,
        "title": _doc_title(doc),
        "boi_id": _doc_boi_id(doc),
        "uri": str(doc.get("uri") or ""),
        "excerpt": _doc_excerpt(doc),
    }


def _score_doc(doc: dict[str, Any], terms: list[str]) -> int:
    blob = _lower_blob({"metadata": doc.get("metadata") or {}, "body": doc.get("body") or ""})
    score = 0
    for raw_term in terms:
        term = str(raw_term or "").strip().lower()
        if not term:
            continue
        if term in blob:
            score += max(1, min(6, len(term) // 6))
    return score


def _search_docs(docs: list[dict[str, Any]], terms: list[str], *, limit: int = 4) -> list[dict[str, Any]]:
    scored = [(score, doc) for doc in docs if (score := _score_doc(doc, terms)) > 0]
    scored.sort(key=lambda item: (-item[0], _doc_title(item[1])))
    return [doc for _, doc in scored[:limit]]


def _event_doc_ref(event_type: str) -> str:
    return f"/public/event-types/{event_type}.md" if event_type else ""


def _extract_expected_contract(value: Any) -> str:
    text = _stringify(value)
    match = re.search(r"Expected result contract:\s*(.+?)(?:\n\S|$)", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return " ".join(match.group(1).split())
    contract = re.search(r"(status=simulated[^\\n]+)", text, flags=re.IGNORECASE)
    return " ".join(contract.group(1).split()) if contract else ""


def _action_output_schema(action: dict[str, Any], action_body: Any) -> str:
    result_contract = action.get("result_contract") or action.get("response_schema")
    if result_contract:
        return _stringify(result_contract)
    return _extract_expected_contract(action_body)


def _extract_stage(value: Any) -> str:
    text = _stringify(value)
    match = re.search(r"Stage:\s*([^\n]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_sop_ref(value: Any) -> str:
    text = _stringify(value)
    match = re.search(r"SOP:\s*([^\s\n]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_next_event(value: Any, stage: dict[str, Any] | None = None) -> str:
    text = _stringify(value)
    match = re.search(r"recommended_next_event\s*=\s*([A-Za-z0-9_.-]+)", text)
    if match:
        return match.group(1).strip()
    if stage:
        emits = _as_list(stage.get("emits_event"))
        if emits:
            return str(emits[0])
        next_stage = stage.get("next_stage")
        if next_stage:
            return str(next_stage)
    return ""


def _manual_or_approval(action: dict[str, Any], stage: dict[str, Any] | None) -> str:
    parts = []
    if action.get("approval_required"):
        parts.append("approval_required=true")
    manual_actions = _as_list((stage or {}).get("manual_actions"))
    if manual_actions:
        parts.append("manual_actions=" + ", ".join(str(item) for item in manual_actions))
    if action.get("risk_level"):
        parts.append(f"risk_level={action.get('risk_level')}")
    return "; ".join(parts)


def _prior_evidence(prior_results: list[dict[str, Any]]) -> str:
    if not prior_results:
        return ""
    items = []
    for row in prior_results[-5:]:
        action_key = row.get("action_key") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("action_key")
        status = row.get("status") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("status")
        summary = row.get("summary") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("message")
        items.append(" / ".join(str(item) for item in (action_key, status, summary) if item))
    return "\n".join(f"- {item}" for item in items)


def _find_nested_key(value: Any, wanted_keys: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in wanted_keys and item not in (None, ""):
                return item
        for item in value.values():
            found = _find_nested_key(item, wanted_keys)
            if found not in (None, ""):
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_nested_key(item, wanted_keys)
            if found not in (None, ""):
                return found
    return None


def _result_blob(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    return {
        "row": row,
        "result": result,
        "response": result.get("response") if isinstance(result.get("response"), dict) else {},
        "simulation_agent": result.get("simulation_agent") if isinstance(result.get("simulation_agent"), dict) else {},
    }


def _evidence_from_existing_packet(packet: dict[str, Any], *, fallback_action_key: str = "") -> dict[str, Any]:
    return {
        "evidence_key": str(packet.get("evidence_key") or packet.get("kind") or fallback_action_key or "evidence"),
        "title": str(packet.get("title") or packet.get("evidence_key") or fallback_action_key or "Evidence"),
        "action_key": str(packet.get("action_key") or fallback_action_key or ""),
        "provenance": str(packet.get("provenance") or "real_log"),
        "simulation": bool(packet.get("simulation")),
        "status": str(packet.get("status") or "available"),
        "source_request_id": str(packet.get("source_request_id") or packet.get("request_id") or ""),
        "source_log_ref": str(packet.get("source_log_ref") or packet.get("_log_ref") or ""),
        "doc_ref": str(packet.get("doc_ref") or ""),
        "fields": packet.get("fields") if isinstance(packet.get("fields"), dict) else {},
        "summary": str(packet.get("summary") or ""),
    }


def _extract_prior_evidence_packets(prior_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(packet: dict[str, Any]) -> None:
        key = (
            str(packet.get("evidence_key") or ""),
            str(packet.get("action_key") or ""),
            str(packet.get("source_request_id") or packet.get("source_log_ref") or packet.get("summary") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        packets.append(packet)

    for row in prior_results:
        action_key = str(row.get("action_key") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("action_key") or "")
        blob = _result_blob(row)
        for source in (
            row.get("evidence_packets"),
            blob["result"].get("evidence_packets"),
            blob["simulation_agent"].get("evidence_packets"),
            (blob["simulation_agent"].get("context_pack") or {}).get("evidence_packets")
            if isinstance(blob["simulation_agent"].get("context_pack"), dict)
            else None,
        ):
            for packet in _dict_items(source):
                add(_evidence_from_existing_packet(packet, fallback_action_key=action_key))

        if action_key == "direct_development.quality_response_trend.simulate":
            trend_status = _find_nested_key(blob, {"trend_status"}) or "simulated_response_trend_reviewed"
            add(
                {
                    "evidence_key": "response_trend",
                    "title": "Response Trend evidence",
                    "action_key": action_key,
                    "provenance": "real_log",
                    "simulation": bool(row.get("simulation") or blob["result"].get("simulation")),
                    "status": "available",
                    "source_request_id": str(row.get("request_id") or blob["result"].get("request_id") or ""),
                    "source_log_ref": str(row.get("_log_ref") or ""),
                    "doc_ref": str(row.get("doc_ref") or ""),
                    "fields": {
                        "trend_status": str(trend_status),
                        "evidence_ref": str(row.get("request_id") or row.get("_log_ref") or ""),
                    },
                    "summary": str(row.get("summary") or blob["result"].get("message") or "Response Trend action log evidence"),
                }
            )
        if action_key == "direct_development.map_view.simulate":
            map_summary = _find_nested_key(blob, {"map_pattern_summary"}) or "simulated_map_pattern_reviewed"
            add(
                {
                    "evidence_key": "map_view",
                    "title": "Map View evidence",
                    "action_key": action_key,
                    "provenance": "real_log",
                    "simulation": bool(row.get("simulation") or blob["result"].get("simulation")),
                    "status": "available",
                    "source_request_id": str(row.get("request_id") or blob["result"].get("request_id") or ""),
                    "source_log_ref": str(row.get("_log_ref") or ""),
                    "doc_ref": str(row.get("doc_ref") or ""),
                    "fields": {
                        "map_pattern_summary": str(map_summary),
                        "evidence_ref": str(row.get("request_id") or row.get("_log_ref") or ""),
                    },
                    "summary": str(row.get("summary") or blob["result"].get("message") or "Map View action log evidence"),
                }
            )
    return packets


def _simulated_prerequisite_packet(
    *,
    evidence_key: str,
    action_key: str,
    title: str,
    doc_ref: str,
    payload: dict[str, Any],
    fields: dict[str, Any],
) -> dict[str, Any]:
    work_id = payload.get("work_id") or payload.get("lot_id") or payload.get("title") or "unknown-work"
    return {
        "evidence_key": evidence_key,
        "title": title,
        "action_key": action_key,
        "provenance": "simulated_prerequisite",
        "simulation": True,
        "status": "simulated",
        "source_request_id": "",
        "source_log_ref": "",
        "doc_ref": doc_ref,
        "fields": {
            **fields,
            "work_id": str(work_id),
            "simulation_boundary": "No real internal system was called. Values follow the public action result contract.",
        },
        "summary": f"{title} generated as SIMULATED prerequisite evidence for {work_id}.",
    }


def _required_evidence(action: dict[str, Any]) -> list[dict[str, Any]]:
    return _dict_items(action.get("evidence_requirements") or action.get("simulation_evidence_requirements"))


def _ensure_required_evidence_packets(
    *,
    action: dict[str, Any],
    payload: dict[str, Any],
    packets: list[dict[str, Any]],
    simulation_depth: str,
) -> list[dict[str, Any]]:
    by_key = {str(packet.get("evidence_key") or ""): packet for packet in packets}
    generated = list(packets)
    if simulation_depth not in {"stage_prerequisites", "auto", "full"}:
        return generated
    for requirement in _required_evidence(action):
        evidence_key = str(requirement.get("evidence_key") or "")
        if not evidence_key or evidence_key in by_key:
            continue
        source_action = str(requirement.get("source_action") or "")
        fields = requirement.get("simulated_fields") if isinstance(requirement.get("simulated_fields"), dict) else {}
        if not source_action or not fields:
            continue
        packet = _simulated_prerequisite_packet(
            evidence_key=evidence_key,
            action_key=source_action,
            title=str(requirement.get("title") or evidence_key),
            doc_ref=str(requirement.get("doc_ref") or ""),
            payload=payload,
            fields={key: _stringify(value) for key, value in fields.items()},
        )
        generated.append(packet)
        by_key[evidence_key] = packet
    return generated


def _action_specific_coverage(action: dict[str, Any], evidence_packets: list[dict[str, Any]]) -> dict[str, bool]:
    covered: dict[str, bool] = {}
    by_key = {str(packet.get("evidence_key") or ""): packet for packet in evidence_packets}
    for requirement in _required_evidence(action):
        evidence_key = str(requirement.get("evidence_key") or "")
        required_fields = [str(item) for item in _as_list(requirement.get("required_fields")) if item]
        packet = by_key.get(evidence_key)
        for field in required_fields:
            covered[field] = bool(packet and (packet.get("fields") or {}).get(field))
    return covered


def _evidence_markdown(evidence_packets: list[dict[str, Any]]) -> str:
    if not evidence_packets:
        return "No evidence packets were available or generated."
    lines = []
    for packet in evidence_packets:
        fields = packet.get("fields") if isinstance(packet.get("fields"), dict) else {}
        field_text = ", ".join(f"{key}={value}" for key, value in fields.items() if value)
        lines.append(
            f"- **{packet.get('title') or packet.get('evidence_key')}** "
            f"({packet.get('provenance')}, action={packet.get('action_key') or '-'})"
            + (f": {field_text}" if field_text else "")
        )
    return "\n".join(lines)


def _find_stage(workflow: dict[str, Any] | None, event_type: str, sop_stage_id: str, stage_hint: str) -> dict[str, Any]:
    workflow = workflow or {}
    stages = workflow.get("stages") or workflow.get("expected_stages") or []
    for stage in stages:
        stage_events = {str(item) for item in _as_list(stage.get("event_types") or stage.get("event_type")) if item}
        stage_ids = {str(stage.get("sop_stage_id") or ""), str(stage.get("stage_id") or ""), str(stage.get("stage") or "")}
        if event_type and event_type in stage_events:
            return dict(stage)
        if sop_stage_id and sop_stage_id in stage_ids:
            return dict(stage)
        if stage_hint and stage_hint in stage_ids:
            return dict(stage)
    return {}


def build_simulation_agent_result(
    *,
    action: dict[str, Any],
    event: dict[str, Any],
    payload: dict[str, Any],
    prior_results: list[dict[str, Any]],
    employee_id: str,
    docs: list[dict[str, Any]],
    event_def: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    sop_ref: str = "",
    sop_stage_id: str = "",
    max_rounds: int = 4,
    simulation_depth: str = "stage_prerequisites",
) -> dict[str, Any]:
    action_key = str(action.get("action_key") or "")
    event_type = str(event.get("event_type") or "")
    action_body = action.get("body") or {}
    stage_hint = sop_stage_id or str(event_def.get("sop_stage_id") if event_def else "") or _extract_stage(action_body)
    stage = _find_stage(workflow, event_type, sop_stage_id, stage_hint)
    resolved_sop_ref = (
        sop_ref
        or str(action.get("sop_ref") or "")
        or str(event_def.get("sop_ref") if event_def else "")
        or str((workflow or {}).get("sop_ref") or "")
        or _extract_sop_ref(action_body)
    )
    expected_contract = _action_output_schema(action, action_body)
    next_event = _extract_next_event(action_body, stage)
    manual_condition = _manual_or_approval(action, stage)
    prior_evidence = _prior_evidence(prior_results)
    evidence_packets = _ensure_required_evidence_packets(
        action=action,
        payload=payload,
        packets=_extract_prior_evidence_packets(prior_results),
        simulation_depth=simulation_depth,
    )

    selected: dict[str, dict[str, Any]] = {}
    context_docs: list[dict[str, str]] = []
    trace: list[dict[str, Any]] = []

    def add_doc(doc: dict[str, Any], *, role: str, reason: str, round_no: int) -> None:
        key = str(doc.get("uri") or _doc_boi_id(doc) or doc.get("path") or "")
        if not key or key in selected:
            return
        selected[key] = doc
        context_docs.append(_doc_summary(doc, role=role, match_reason=reason))
        if trace:
            trace[-1].setdefault("found_docs", []).append({"uri": str(doc.get("uri") or ""), "title": _doc_title(doc), "role": role})

    exact_refs = [str(action.get("doc_ref") or ""), _event_doc_ref(event_type), resolved_sop_ref]
    trace.append(
        {
            "round": 1,
            "objective": "Resolve exact SOP, Event Type, and Action Spec references.",
            "exact_refs": [ref for ref in exact_refs if ref],
            "queries": [],
            "found_docs": [],
        }
    )
    for ref in exact_refs:
        for doc in docs:
            if _doc_matches_ref(doc, ref):
                role = "action_spec" if ref == action.get("doc_ref") else ("event_type" if event_type and event_type in ref else "sop")
                add_doc(doc, role=role, reason=f"exact_ref:{ref}", round_no=1)
                break

    term_rounds = [
        [
            action_key,
            str(action.get("name_ko") or ""),
            str(action.get("description") or ""),
            str(action.get("simulated_system") or ""),
        ],
        [
            event_type,
            str((event.get("payload") or {}).get("title") or ""),
            *[str(value) for value in (payload or {}).values() if isinstance(value, (str, int, float))][:6],
        ],
        [
            resolved_sop_ref,
            stage_hint,
            str(stage.get("stage") or ""),
            str(stage.get("description") or ""),
            expected_contract,
        ],
    ]
    for index, terms in enumerate(term_rounds, start=2):
        if index > max_rounds:
            break
        trace.append(
            {
                "round": index,
                "objective": "Search BoI Wiki for missing simulation context.",
                "exact_refs": [],
                "queries": [term for term in terms if str(term or "").strip()],
                "found_docs": [],
            }
        )
        for doc in _search_docs(docs, [term for term in terms if str(term or "").strip()], limit=3):
            add_doc(doc, role="supporting_context", reason="search_terms", round_no=index)

    covered = {
        "sop_stage": bool(stage or stage_hint or resolved_sop_ref),
        "action_contract": bool(action.get("doc_ref") and any(item["role"] == "action_spec" for item in context_docs)),
        "event_context": bool(event_type or event),
        "output_schema": bool(expected_contract),
        "next_event": bool(next_event),
        "citation": bool(context_docs),
        "expected_output_schema": bool(expected_contract),
        "prior_evidence": bool(prior_evidence or prior_results or evidence_packets),
        "manual_or_approval_condition": bool(manual_condition or action.get("approval_required") is not None),
        "next_stage_or_event": bool(next_event),
    }
    covered.update(_action_specific_coverage(action, evidence_packets))
    required = list(dict.fromkeys(COMMON_COVERAGE + [str(field) for req in _required_evidence(action) for field in _as_list(req.get("required_fields")) if field]))
    if not required:
        required = REQUIRED_COVERAGE
    missing = [key for key in required if not covered.get(key)]
    score = round(sum(1 for key in required if covered.get(key)) / len(required), 2)
    for row in trace:
        row["coverage_after"] = {
            "coverage_score": score,
            "missing_context": missing,
        }

    citations = [
        {
            "label": item["role"],
            "title": item["title"],
            "ref": item["boi_id"] or item["uri"],
            "uri": item["uri"],
        }
        for item in context_docs[:10]
    ]
    limitations = [
        "SIMULATED dry-run result only; no unavailable internal system was called.",
        "Use cited BoI Wiki documents and action raw logs before operational use.",
    ]
    if missing:
        limitations.append("Missing context: " + ", ".join(missing))

    current_finding = (
        f"{action_key} action을 {str(action.get('simulated_system') or action.get('name_ko') or action_key)} 대상으로 "
        f"BoI Wiki 근거 기반으로 시뮬레이션했습니다."
    )
    if event_type:
        current_finding += f" 입력 event는 {event_type}입니다."
    stage_label = str(stage.get("stage") or stage_hint or "unknown")
    markdown = "\n\n".join(
        [
            "# SIMULATED BoI Wiki Simulation Result",
            "## Current Finding\n" + current_finding,
            "## Evidence Used\n"
            + "\n".join(
                [f"- Event: {event_type or '-'} / trace={event.get('trace_id') or '-'}", f"- SOP Stage: {stage_label}", f"- Action Spec: {action.get('doc_ref') or '-'}"]
                + [f"- Wiki: {item['title']} ({item['boi_id'] or item['uri']})" for item in context_docs[:5]]
            ),
            "## Expected Result Contract\n" + (expected_contract or "명시된 expected result contract가 부족합니다."),
            "## Prior Evidence\n" + (prior_evidence or "이 action 이전에 제공된 prior result가 없습니다."),
            "## SIMULATED Evidence Packets\n" + _evidence_markdown(evidence_packets),
            "## Simulation Draft\n"
            + (
                f"- status=simulated\n- simulated_action_key={action_key}\n"
                f"- simulated_system={action.get('simulated_system') or action.get('name_ko') or action_key}\n"
                f"- coverage_score={score}\n- recommended_next_event={next_event or '-'}\n"
                f"- human_review_required={'true' if 'manual' in manual_condition or action.get('risk_level') in {'medium', 'high'} else 'false'}"
            ),
            "## Limitations\n" + "\n".join(f"- {item}" for item in limitations),
            "## Citations\n" + ("\n".join(f"- [{item['label']}] {item['title']} ({item['ref']})" for item in citations) or "- No BoI Wiki citation resolved."),
        ]
    )
    return {
        "ok": True,
        "status": "simulated_context_ready",
        "simulation": True,
        "agent": {
            "name": "BoI Simulation Agent",
            "version": "0.1",
            "strategy": "bounded-retrieval-loop",
            "max_rounds": max_rounds,
            "retrieval_rounds": len(trace),
        },
        "employee_id": employee_id,
        "action_key": action_key,
        "event_type": event_type,
        "trace_id": str(event.get("trace_id") or ""),
        "context_pack": {
            "documents": context_docs,
            "event": event,
            "payload": payload,
            "action": {
                "action_key": action_key,
                "doc_ref": action.get("doc_ref"),
                "connector_kind": action.get("connector_kind"),
                "simulation_mode": action.get("simulation_mode"),
                "simulated_system": action.get("simulated_system"),
                "risk_level": action.get("risk_level"),
                "approval_required": bool(action.get("approval_required")),
            },
            "workflow": {
                "workflow_key": (workflow or {}).get("workflow_key"),
                "sop_ref": resolved_sop_ref,
                "sop_stage_id": stage.get("sop_stage_id") or stage_hint,
                "stage": stage,
            },
            "prior_results": prior_results,
            "evidence_packets": evidence_packets,
        },
        "evidence_packets": evidence_packets,
        "retrieval_trace": trace,
        "coverage_report": {
            "required": required,
            "covered": covered,
            "missing_context": missing,
            "coverage_score": score,
            "pass_threshold": 0.85,
            "passed": score >= 0.85,
        },
        "citations": citations,
        "limitations": limitations,
        "next_recommended_events": [next_event] if next_event and ".v" in next_event else [],
        "next_recommended_actions": _as_list(stage.get("automated_actions") if stage else []),
        "simulation_result": {
            "status": "simulated",
            "simulation": True,
            "summary": current_finding,
            "markdown": markdown,
            "generated_result": {
                "coverage_score": score,
                "missing_context": missing,
                "recommended_next_event": next_event,
                "human_review_required": "manual" in manual_condition or action.get("risk_level") in {"medium", "high"},
                "evidence_packets": evidence_packets,
            },
        },
    }
