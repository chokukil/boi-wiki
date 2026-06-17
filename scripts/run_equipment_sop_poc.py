#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("BOI_API_URL", "http://localhost:8000").rstrip("/")
EMPLOYEE_ID = os.getenv("EMPLOYEE_ID", "100001")
TIMEOUT_SECONDS = int(os.getenv("POC_SMOKE_TIMEOUT_SECONDS", "90"))
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


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def start_demo() -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID})
    return request_json(
        "POST",
        f"/api/workflows/demo/equipment-anomaly/start?{query}",
        {
            "equipment_id": "ETCH-VM-01",
            "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            "title": "Response Chain 이상 Alarm 발생",
            "lot_id": "LOT-POC-001",
            "wafer_id": "WF-POC-001",
        },
    )


def get_status(trace_id: str) -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID, "trace_id": trace_id})
    return request_json("GET", f"/api/workflows/demo/equipment-anomaly/status?{query}")


def main() -> int:
    started = start_demo()
    trace_id = started["event"]["trace_id"]
    print(f"started trace_id={trace_id}")
    print(f"sop={started['workflow']['sop_ref']} uri={started['workflow']['sop_uri']}")

    deadline = time.time() + TIMEOUT_SECONDS
    last_status: dict[str, Any] = {}
    while time.time() < deadline:
        last_status = get_status(trace_id)
        seen_events = {row.get("event_type") for row in last_status.get("events", [])}
        manual_handoffs = set(last_status.get("manual_handoffs", []))
        generated_docs = last_status.get("generated_docs", [])
        if REQUIRED_EVENTS <= seen_events and REQUIRED_MANUAL_HANDOFFS <= manual_handoffs and generated_docs:
            print("equipment SOP PoC smoke passed")
            print(json.dumps(
                {
                    "trace_id": trace_id,
                    "events": sorted(seen_events),
                    "generated_docs": generated_docs,
                    "approval_required_actions": last_status.get("approval_required_actions", []),
                    "manual_handoffs": sorted(manual_handoffs),
                },
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        print(
            "waiting",
            json.dumps(
                {
                    "events": sorted(seen_events),
                    "generated_docs": len(generated_docs),
                    "manual_handoffs": sorted(manual_handoffs),
                },
                ensure_ascii=False,
            ),
        )
        time.sleep(POLL_SECONDS)

    print("equipment SOP PoC smoke failed", file=sys.stderr)
    print(json.dumps(last_status, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
