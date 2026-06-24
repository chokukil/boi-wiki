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
REQUIRED_LANGFLOW_ACTIONS = {"langflow.boi.reference_flow", "langflow.equipment.stage_analysis"}


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


def start_demo() -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID})
    return request_json(
        "POST",
        f"/api/workflows/demo/equipment-anomaly/start?{query}",
        {
            "user_confirmed": True,
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
        langflow_actions = [
            row
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_LANGFLOW_ACTIONS and row.get("status") == "langflow_invoked"
        ]
        seen_langflow_actions = {row.get("action_key") for row in langflow_actions}
        docs_enriched = generated_docs_have_no_boilerplate(generated_docs)
        if (
            REQUIRED_EVENTS <= seen_events
            and REQUIRED_MANUAL_HANDOFFS <= manual_handoffs
            and generated_docs
            and REQUIRED_LANGFLOW_ACTIONS <= seen_langflow_actions
            and docs_enriched
        ):
            print("equipment SOP PoC smoke passed")
            print(json.dumps(
                {
                    "trace_id": trace_id,
                    "events": sorted(seen_events),
                    "generated_docs": generated_docs,
                    "langflow_actions": compact_action_rows(langflow_actions),
                    "generated_docs_have_no_boilerplate": True,
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
                    "langflow_actions": sorted(seen_langflow_actions),
                    "generated_docs_have_no_boilerplate": docs_enriched,
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
