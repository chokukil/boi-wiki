#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("BOI_API_URL", "http://localhost:28000").rstrip("/")
EMPLOYEE_ID = os.getenv("EMPLOYEE_ID", "100001")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")
BOI_AUTH_BEARER = os.getenv("BOI_AUTH_BEARER", "")
TIMEOUT_SECONDS = int(os.getenv("POC_SMOKE_TIMEOUT_SECONDS", "180"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("POC_SMOKE_HTTP_TIMEOUT_SECONDS", "180"))
POLL_SECONDS = float(os.getenv("POC_SMOKE_POLL_SECONDS", "2"))

REQUIRED_EVENTS = {
    "equipment.alarm.raised.v1",
    "root_cause.analysis.requested.v1",
    "maintenance.guide.requested.v1",
    "corrective_action.requested.v1",
}
REQUIRED_MANUAL_HANDOFFS = {
    "manual.equipment.confirm_alarm_context",
    "manual.equipment.review_root_cause",
    "manual.equipment.approve_process_hold",
    "manual.equipment.approve_spec_rule_change",
    "manual.equipment.confirm_maintenance_done",
}
REQUIRED_SIMULATOR_ACTIONS = {"sop.equipment.request_trend_history"}
REQUIRED_LANGFLOW_FLOW_NAMES = {"BoI Universal Action Simulator Flow"}

SEMICONDUCTOR_VARIED_SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "etch-pressure-spike",
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
        "root_cause_candidate": "chamber pressure drift",
        "missing_evidence": "raw_endpoint_confirmation",
        "approval_risk": "spec_rule_change_required",
    },
    {
        "scenario_id": "cvd-temperature-drift",
        "title": "CVD temperature drift",
        "equipment_id": "CVD-ALD-02",
        "chamber_id": "CH-B",
        "fab": "FAB-B",
        "lot_id": "LOT-B-240626",
        "wafer_id": "WF-13",
        "alarm_code": "TEMP_DRIFT",
        "severity": "medium",
        "process_step": "CVD",
        "trend_status": "unconfirmed",
        "raw_data_status": "retry_required",
        "root_cause_candidate": "heater calibration drift",
        "missing_evidence": "trend_history",
        "approval_risk": "raw_data_required_before_hold",
    },
    {
        "scenario_id": "metrology-ring-pattern",
        "title": "Metrology ring pattern",
        "equipment_id": "MET-OVL-03",
        "chamber_id": "STAGE-1",
        "fab": "FAB-A",
        "lot_id": "LOT-C-240626",
        "wafer_id": "WF-21",
        "alarm_code": "RING_PATTERN",
        "severity": "medium",
        "process_step": "METROLOGY",
        "trend_status": "map_view_abnormal",
        "raw_data_status": "wafer_history_needed",
        "root_cause_candidate": "edge ring response deviation",
        "missing_evidence": "wafer_history_compare",
        "approval_risk": "metrology_review_required",
    },
    {
        "scenario_id": "furnace-recipe-mismatch",
        "title": "Furnace recipe mismatch",
        "equipment_id": "FURN-HT-04",
        "chamber_id": "TUBE-2",
        "fab": "FAB-C",
        "lot_id": "LOT-D-240626",
        "wafer_id": "WF-04",
        "alarm_code": "RECIPE_MISMATCH",
        "severity": "high",
        "process_step": "FURNACE",
        "trend_status": "source_data_mismatch",
        "raw_data_status": "available",
        "root_cause_candidate": "recipe/source data mismatch",
        "missing_evidence": "maintenance_guide_confirmation",
        "approval_risk": "process_hold_required",
    },
]


def request_headers(content_type: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = "application/json"
    if SERVICE_TOKEN:
        headers["x-service-token"] = SERVICE_TOKEN
    if BOI_AUTH_BEARER:
        headers["Authorization"] = f"Bearer {BOI_AUTH_BEARER}"
    return headers


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers=request_headers(content_type=True),
    )
    with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(path: str) -> str:
    req = Request(f"{BASE_URL}{path}", method="GET", headers=request_headers())
    with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def start_demo(scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID})
    payload = {
        "user_confirmed": True,
        "equipment_id": "ETCH-VM-01",
        "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
        "title": "Response Chain 이상 Alarm 발생",
        "lot_id": "LOT-POC-001",
        "wafer_id": "WF-POC-001",
    }
    if scenario:
        payload.update({key: value for key, value in scenario.items() if key != "scenario_id"})
    return request_json(
        "POST",
        f"/api/workflows/demo/equipment-anomaly/start?{query}",
        payload,
    )


def get_status(trace_id: str) -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID, "trace_id": trace_id})
    return request_json("GET", f"/api/workflows/demo/equipment-anomaly/status?{query}")


def generated_docs_have_no_boilerplate(generated_docs: list[dict[str, Any]]) -> bool:
    if not generated_docs:
        return False
    for doc in generated_docs:
        doc_url = doc.get("doc_url")
        if not doc_url:
            return False
        html = request_text(doc_url)
        if "AI Native Workflow Interpretation" in html or "Event Broker는 업무 시점" in html:
            return False
        if "pending enrichment" in html:
            return False
    return True


def compact_action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted = []
    for row in rows:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        compacted.append(
            {
                "action_key": row.get("action_key"),
                "status": row.get("status"),
                "request_id": row.get("request_id"),
                "doc_ref": row.get("doc_ref"),
                "flow_name": result.get("flow_name"),
                "flow_id": result.get("flow_id"),
            }
        )
    return compacted


def scenario_for(profile: str, index: int) -> dict[str, Any] | None:
    if profile == "semiconductor-varied":
        return SEMICONDUCTOR_VARIED_SCENARIOS[index % len(SEMICONDUCTOR_VARIED_SCENARIOS)]
    return None


def run_one(profile: str, index: int) -> dict[str, Any] | None:
    scenario = scenario_for(profile, index)
    started = start_demo(scenario)
    trace_id = started["event"]["trace_id"]
    scenario_id = str((scenario or {}).get("scenario_id") or "default")
    print(f"started trace_id={trace_id} scenario={scenario_id}")
    print(f"sop={started['workflow']['sop_ref']} uri={started['workflow']['sop_uri']}")

    deadline = time.time() + TIMEOUT_SECONDS
    last_status: dict[str, Any] = {}
    while time.time() < deadline:
        last_status = get_status(trace_id)
        seen_events = {row.get("event_type") for row in last_status.get("events", [])}
        manual_handoffs = set(last_status.get("manual_handoffs", []))
        generated_docs = last_status.get("generated_docs", [])
        simulator_actions = [
            row
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_SIMULATOR_ACTIONS
            and row.get("status") == "langflow_invoked"
            and (row.get("result") or {}).get("flow_name") in REQUIRED_LANGFLOW_FLOW_NAMES
        ]
        seen_simulator_actions = {row.get("action_key") for row in simulator_actions}
        docs_enriched = generated_docs_have_no_boilerplate(generated_docs)
        if (
            REQUIRED_EVENTS <= seen_events
            and REQUIRED_MANUAL_HANDOFFS <= manual_handoffs
            and generated_docs
            and REQUIRED_SIMULATOR_ACTIONS <= seen_simulator_actions
            and docs_enriched
        ):
            print("equipment SOP PoC smoke passed")
            return {
                "scenario_id": scenario_id,
                "business_context": scenario or {},
                "trace_id": trace_id,
                "events": sorted(seen_events),
                "generated_docs": generated_docs,
                "langflow_actions": compact_action_rows(simulator_actions),
                "generated_docs_have_no_boilerplate": True,
                "approval_required_actions": last_status.get("approval_required_actions", []),
                "manual_handoffs": sorted(manual_handoffs),
            }
        print(
            "waiting",
            json.dumps(
                {
                    "events": sorted(seen_events),
                    "generated_docs": len(generated_docs),
                    "langflow_actions": sorted(seen_simulator_actions),
                    "generated_docs_have_no_boilerplate": docs_enriched,
                    "manual_handoffs": sorted(manual_handoffs),
                },
                ensure_ascii=False,
            ),
        )
        time.sleep(POLL_SECONDS)

    print("equipment SOP PoC smoke failed", file=sys.stderr)
    print(json.dumps(last_status, ensure_ascii=False, indent=2), file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run equipment anomaly SOP PoC through Event Broker and Action Gateway.")
    parser.add_argument("--scenario-profile", choices=["default", "semiconductor-varied"], default=os.getenv("POC_SCENARIO_PROFILE", "default"))
    parser.add_argument("--count", type=int, default=int(os.getenv("POC_SCENARIO_COUNT", "1")))
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for index in range(max(1, args.count)):
        result = run_one(args.scenario_profile, index)
        if result is None:
            return 1
        results.append(result)
    print(json.dumps({"ok": True, "scenario_profile": args.scenario_profile, "count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
