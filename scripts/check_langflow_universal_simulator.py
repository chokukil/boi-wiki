#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from audit_langflow_flows import REQUIRED_RUNTIME_FLOWS, audit_flow, runtime_flows  # noqa: E402


DEFAULT_SERVICE_TOKEN = "dev-service-token-change-me"
FORBIDDEN_LANGFLOW_TEXT = (
    "outdated component",
    "outdated components",
    "connection error",
    "error running graph",
    "traceback",
)
REQUIRED_BUSINESS_FIELDS = ("equipment_id", "lot_id", "wafer_id")
REQUIRED_EVIDENCE_FIELDS = ("trend_status", "source_system")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def recursive_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            texts.extend(recursive_texts(child))
    elif isinstance(value, list):
        for child in value:
            texts.extend(recursive_texts(child))
    return texts


def compact_json(value: Any, limit: int = 4000) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return rendered[:limit]


def audit_runtime_universal_flow(langflow_url: str, api_key: str, auth_mode: str, timeout: float) -> dict[str, Any]:
    errors: list[str] = []
    flows = runtime_flows(langflow_url, api_key, auth_mode, timeout=timeout)
    by_name = {str(flow.get("name") or ""): flow for flow in flows if isinstance(flow, dict)}
    rule = REQUIRED_RUNTIME_FLOWS["BoI Universal Action Simulator Flow"]
    flow = by_name.get("BoI Universal Action Simulator Flow")
    if not flow:
        return {"ok": False, "errors": ["runtime flow missing: BoI Universal Action Simulator Flow"], "flow_count": len(flows)}
    errors.extend(
        audit_flow(
            flow,
            require_boi_components=bool(rule.get("require_boi_components")),
            require_simulation_agent=bool(rule.get("require_simulation_agent")),
        )
    )
    return {
        "ok": not errors,
        "errors": errors,
        "flow_count": len(flows),
        "flow_id": flow.get("id") or flow.get("flow_id") or "",
        "endpoint": rule.get("endpoint"),
    }


def simulator_payload(employee_id: str) -> dict[str, Any]:
    event_payload = {
        "title": "ETCH chamber pressure spike",
        "equipment_id": "ETCH-VM-01",
        "chamber_id": "CH-A",
        "fab": "FAB-A",
        "lot_id": "LOT-A-240626",
        "wafer_id": "WF-07",
        "alarm_code": "PRESSURE_SPIKE",
        "severity": "high",
        "process_step": "ETCH",
        "trend_status": "abnormal",
        "raw_data_status": "available",
    }
    return {
        "action_key": "sop.equipment.request_trend_history",
        "employee_id": employee_id,
        "event": {
            "event_id": "evt-langflow-smoke-universal",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": "trace-langflow-smoke-universal",
            "payload": event_payload,
        },
        "payload": dict(event_payload),
        "simulation_depth": "stage_prerequisites",
    }


def run_langflow_flow(client: httpx.Client, langflow_url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"{langflow_url.rstrip('/')}/api/v1/run/boi-universal-action-simulator",
        headers={"x-api-key": api_key},
        json={
            "input_value": json.dumps(payload, ensure_ascii=False),
            "input_type": "chat",
            "output_type": "chat",
        },
    )
    response.raise_for_status()
    return response.json()


def run_boi_simulator(client: httpx.Client, boi_api_url: str, service_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"{boi_api_url.rstrip('/')}/api/simulations/universal-agent",
        headers={"x-service-token": service_token},
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def validate_langflow_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = "\n".join(recursive_texts(result)).lower()
    for forbidden in FORBIDDEN_LANGFLOW_TEXT:
        if forbidden in text:
            errors.append(f"Langflow result contains failure text: {forbidden}")
    if "universal simulator agent result" not in text and "simulated boi wiki simulation result" not in text:
        errors.append("Langflow run did not return Universal Simulator result text")
    return errors


def validate_boi_result(result: dict[str, Any], min_coverage: float) -> list[str]:
    errors: list[str] = []
    coverage_score = float(((result.get("coverage_report") or {}).get("coverage_score") or 0))
    if coverage_score < min_coverage:
        errors.append(f"coverage_score {coverage_score:.2f} is below {min_coverage:.2f}")
    packets = result.get("evidence_packets") if isinstance(result.get("evidence_packets"), list) else []
    if not packets:
        errors.append("evidence_packets is empty")
    packet_fields: dict[str, Any] = {}
    for packet in packets:
        if isinstance(packet, dict) and isinstance(packet.get("fields"), dict):
            packet_fields.update(packet["fields"])
    for field in REQUIRED_EVIDENCE_FIELDS:
        if not packet_fields.get(field):
            errors.append(f"evidence packet is missing {field}")
    business_context = result.get("business_context") if isinstance(result.get("business_context"), dict) else {}
    for field in REQUIRED_BUSINESS_FIELDS:
        if not business_context.get(field):
            errors.append(f"business_context is missing {field}")
    if not (business_context.get("alarm_code") or business_context.get("trend_status")):
        errors.append("business_context is missing alarm_code/trend_status")
    return errors


def business_context_quality(context: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_BUSINESS_FIELDS if not context.get(field)]
    has_status = bool(context.get("alarm_code") or context.get("trend_status"))
    if not has_status:
        missing.append("alarm_code_or_trend_status")
    return {
        "has_business_context": bool(context),
        "missing_core_fields": missing,
        "quality": "ready" if not missing else ("partial" if context else "missing"),
    }


def write_health(path: str, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Langflow BoI Universal Action Simulator acceptance criteria.")
    parser.add_argument("--langflow-url", default=os.getenv("LANGFLOW_URL", "http://localhost:7860"))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me"))
    parser.add_argument("--auth-mode", choices=["auto-login", "api-key"], default=os.getenv("LANGFLOW_AUTH_MODE", "api-key"))
    parser.add_argument("--boi-api-url", default=os.getenv("BOI_API_URL", "http://localhost:28000"))
    parser.add_argument("--service-token", default=os.getenv("SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN))
    parser.add_argument("--employee-id", default=os.getenv("EMPLOYEE_ID", "100001"))
    parser.add_argument("--min-coverage", type=float, default=float(os.getenv("LANGFLOW_SIMULATOR_MIN_COVERAGE", "0.85")))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("LANGFLOW_SIMULATOR_SMOKE_TIMEOUT", "45")))
    parser.add_argument(
        "--health-output",
        default=os.getenv("LANGFLOW_SIMULATOR_HEALTH_FILE", str(ROOT / "data" / "actions" / "_health" / "langflow_universal_simulator.json")),
        help="Write last smoke result for /api/runtime/config to read.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    checked_at = now_iso()
    flow_audit: dict[str, Any] = {"ok": False, "errors": ["not run"]}
    langflow_result: dict[str, Any] = {}
    boi_result: dict[str, Any] = {}

    payload = simulator_payload(args.employee_id)
    try:
        flow_audit = audit_runtime_universal_flow(args.langflow_url, args.langflow_api_key, args.auth_mode, args.timeout)
        errors.extend(str(error) for error in flow_audit.get("errors") or [])
    except Exception as exc:
        errors.append(f"flow audit failed: {type(exc).__name__}: {exc}")

    with httpx.Client(timeout=args.timeout) as client:
        try:
            langflow_result = run_langflow_flow(client, args.langflow_url, args.langflow_api_key, payload)
            errors.extend(validate_langflow_result(langflow_result))
        except Exception as exc:
            errors.append(f"Langflow run failed: {type(exc).__name__}: {exc}")
        try:
            boi_result = run_boi_simulator(client, args.boi_api_url, args.service_token, payload)
            errors.extend(validate_boi_result(boi_result, args.min_coverage))
        except Exception as exc:
            errors.append(f"BoI simulator API failed: {type(exc).__name__}: {exc}")

    coverage_score = ((boi_result.get("coverage_report") or {}).get("coverage_score") if isinstance(boi_result, dict) else None)
    business_context = boi_result.get("business_context") if isinstance(boi_result.get("business_context"), dict) else {}
    health = {
        "ok": not errors,
        "checked_at": checked_at,
        "errors": errors,
        "flow_audit": flow_audit,
        "coverage_score": coverage_score,
        "evidence_packet_count": len(boi_result.get("evidence_packets") or []) if isinstance(boi_result, dict) else 0,
        "business_context": business_context,
        "business_context_quality": business_context_quality(business_context),
        "langflow_sample": compact_json(langflow_result, limit=1200) if langflow_result else "",
    }
    write_health(args.health_output, health)
    print(json.dumps(health, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
