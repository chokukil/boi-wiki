#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from http.client import RemoteDisconnected
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("BOI_API_URL", "http://localhost:8000").rstrip("/")
ACTION_INVOKE_URL = os.getenv("ACTION_INVOKE_URL", f"{BASE_URL}/api/actions/invoke").rstrip("/")
EMPLOYEE_ID = os.getenv("EMPLOYEE_ID", "100001")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")
BOI_AUTH_BEARER = os.getenv("BOI_AUTH_BEARER", "")
TIMEOUT_SECONDS = int(os.getenv("POC_SMOKE_TIMEOUT_SECONDS", "240"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("POC_SMOKE_HTTP_TIMEOUT_SECONDS", "180"))
POLL_SECONDS = float(os.getenv("POC_SMOKE_POLL_SECONDS", "2"))
HTTP_RETRY_COUNT = int(os.getenv("POC_SMOKE_HTTP_RETRY_COUNT", "4"))
HTTP_RETRY_DELAY_SECONDS = float(os.getenv("POC_SMOKE_HTTP_RETRY_DELAY_SECONDS", "2"))
WORKFLOW_KEY = "direct-development-reporting"

REQUIRED_EVENTS = {
    "direct_development.result_check.requested.v1",
    "direct_development.map_view.requested.v1",
    "direct_development.cross_section.decision_required.v1",
    "direct_development.cross_section.requested.v1",
    "direct_development.fab_trend.compare_requested.v1",
    "direct_development.reporting.requested.v1",
    "direct_development.share.requested.v1",
}
REQUIRED_SIMULATED_ACTIONS = {
    "direct_development.quality_response_trend.simulate",
    "direct_development.map_view.simulate",
    "direct_development.cross_section_request.simulate",
    "direct_development.cross_section_result.simulate",
    "direct_development.fab_trend_compare.simulate",
    "direct_development.reporting.simulate",
    "direct_development.messenger_share_preview.simulate",
}
REQUIRED_EVENT_ACTIONS = {
    "direct_development.create_map_view_event",
    "direct_development.create_cross_section_decision_event",
    "direct_development.create_fab_compare_event",
    "direct_development.create_reporting_event",
    "direct_development.create_share_event",
}
REQUIRED_MANUAL_ACTIONS = {
    "manual.direct_development.decide_cross_section",
}
REQUIRED_APPROVAL_ACTIONS = {
    "direct_development.messenger_share.publish",
}


def request_headers(content_type: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = "application/json"
    if SERVICE_TOKEN:
        headers["x-service-token"] = SERVICE_TOKEN
    if BOI_AUTH_BEARER:
        headers["Authorization"] = f"Bearer {BOI_AUTH_BEARER}"
    return headers


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    for attempt in range(1, HTTP_RETRY_COUNT + 1):
        req = Request(url, data=body, method=method, headers=request_headers(content_type=payload is not None))
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError:
            raise
        except (RemoteDisconnected, TimeoutError, URLError) as exc:
            if attempt >= HTTP_RETRY_COUNT:
                raise
            print(f"retrying request_json attempt={attempt} error={type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(HTTP_RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError("unreachable request_json retry state")


def request_text(url: str) -> str:
    for attempt in range(1, HTTP_RETRY_COUNT + 1):
        req = Request(url, method="GET", headers=request_headers())
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except HTTPError:
            raise
        except (RemoteDisconnected, TimeoutError, URLError) as exc:
            if attempt >= HTTP_RETRY_COUNT:
                raise
            print(f"retrying request_text attempt={attempt} error={type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(HTTP_RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError("unreachable request_text retry state")


def boi_url(path: str) -> str:
    return f"{BASE_URL}{path}"


def start_workflow() -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID})
    return request_json(
        "POST",
        boi_url(f"/api/workflows/{WORKFLOW_KEY}/start?{query}"),
        {
            "payload": {
                "title": "직개발 결과 확인 및 Reporting PoC",
                "product": "Product-A",
                "tech": "Tech-A",
                "work_id": "1.10",
                "lot_id": "LOT-DD-001",
                "wafer_id": "WF-DD-001",
                "owner": EMPLOYEE_ID,
                "source_image_ref": "/public/boi-wiki-manual/_media/source/natural-language-poc/sop_sample_image.png",
                "simulation_notice": "SIMULATED: 실제 사내 시스템 호출이 아니라 BoI Universal Action Simulator Flow 기반 PoC evidence입니다.",
            },
            "source_refs": [
                {
                    "type": "sop-image",
                    "ref": "/public/boi-wiki-manual/_media/source/natural-language-poc/sop_sample_image.png",
                },
                {"type": "sop", "ref": "boi:public:sop:direct-development-reporting"},
            ],
        },
    )


def get_status(trace_id: str) -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID, "trace_id": trace_id})
    return request_json("GET", boi_url(f"/api/workflows/{WORKFLOW_KEY}/status?{query}"))


def find_event(status: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    for event in status.get("events", []):
        if event.get("event_type") == event_type:
            return event
    return None


def invoke_manual_cross_section(decision_event: dict[str, Any]) -> dict[str, Any]:
    event_result = decision_event.get("result") if isinstance(decision_event.get("result"), dict) else {}
    event_payload = event_result.get("payload") if isinstance(event_result.get("payload"), dict) else {}
    payload = {
        **event_payload,
        "product": "Product-A",
        "tech": "Tech-A",
        "work_id": "1.10",
        "lot_id": "LOT-DD-001",
        "wafer_id": "WF-DD-001",
        "owner": EMPLOYEE_ID,
        "manual_decision": "cross_section_required",
        "manual_completion_note": "Smoke harness가 사람 판단 완료를 명시적으로 시뮬레이션했다.",
    }
    return request_json(
        "POST",
        ACTION_INVOKE_URL,
        {
            "action_key": "manual.direct_development.decide_cross_section",
            "employee_id": EMPLOYEE_ID,
            "event": {
                "event_id": decision_event.get("event_id"),
                "event_type": decision_event.get("event_type"),
                "trace_id": decision_event.get("trace_id"),
                "payload": payload,
            },
            "payload": payload,
            "dry_run": True,
        },
    )


def publish_cross_section_requested(trace_id: str, decision_event: dict[str, Any], manual_result: dict[str, Any]) -> dict[str, Any]:
    query = urlencode({"employee_id": EMPLOYEE_ID})
    return request_json(
        "POST",
        boi_url(f"/api/events/publish?{query}"),
        {
            "event_type": "direct_development.cross_section.requested.v1",
            "actor_employee_id": EMPLOYEE_ID,
            "trace_id": trace_id,
            "payload": {
                "title": "단면검사 의뢰 및 결과 확인 - 1.10",
                "product": "Product-A",
                "tech": "Tech-A",
                "work_id": "1.10",
                "lot_id": "LOT-DD-001",
                "wafer_id": "WF-DD-001",
                "owner": EMPLOYEE_ID,
                "manual_decision": "cross_section_required",
                "manual_action_request_id": manual_result.get("request_id"),
                "simulation_notice": "Smoke harness가 manual_required 단계 완료 event를 명시적으로 발행했다.",
            },
            "source_refs": [
                {"type": "event", "ref": decision_event.get("event_id")},
                {"type": "action", "ref": manual_result.get("request_id")},
            ],
        },
    )


def generated_docs_have_simulated_marker(generated_docs: list[dict[str, Any]]) -> bool:
    for doc in generated_docs:
        doc_url = doc.get("doc_url")
        if not doc_url:
            continue
        html = request_text(boi_url(doc_url))
        if "SIMULATED" in html and "실제 시스템 호출" in html:
            return True
    return False


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
                "simulation": bool(row.get("simulation") or result.get("simulation")),
                "simulation_label": row.get("simulation_label") or result.get("simulation_label"),
                "simulated_system": row.get("simulated_system") or result.get("simulated_system"),
                "flow_name": result.get("flow_name"),
                "flow_id": result.get("flow_id"),
                "raw_log_ref": row.get("_log_ref"),
            }
        )
    return compacted


def main() -> int:
    started = start_workflow()
    trace_id = started["event"]["trace_id"]
    print(f"started trace_id={trace_id}")
    print(f"sop={started['workflow']['sop_ref']} uri={started['workflow']['sop_uri']}")

    manual_invoked = False
    manual_result: dict[str, Any] = {}
    cross_section_published = False
    last_status: dict[str, Any] = {}
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        last_status = get_status(trace_id)
        seen_events = {row.get("event_type") for row in last_status.get("events", [])}
        decision_event = find_event(last_status, "direct_development.cross_section.decision_required.v1")

        if decision_event and not manual_invoked:
            manual_result = invoke_manual_cross_section(decision_event)
            manual_invoked = True
            print(
                "manual handoff completed",
                json.dumps(
                    {
                        "action_key": manual_result.get("action_key"),
                        "status": manual_result.get("status"),
                        "request_id": manual_result.get("request_id"),
                    },
                    ensure_ascii=False,
                ),
            )

        if decision_event and manual_invoked and not cross_section_published:
            published = publish_cross_section_requested(trace_id, decision_event, manual_result)
            cross_section_published = True
            print(
                "manual completion event published",
                json.dumps(
                    {
                        "event_type": published.get("event", {}).get("event_type"),
                        "event_id": published.get("event", {}).get("event_id"),
                    },
                    ensure_ascii=False,
                ),
            )

        simulated_actions = [
            row
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_SIMULATED_ACTIONS
            and row.get("status") == "langflow_invoked"
            and bool(row.get("simulation") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("simulation"))
        ]
        seen_simulated_actions = {row.get("action_key") for row in simulated_actions}
        seen_event_actions = {
            row.get("action_key")
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_EVENT_ACTIONS and row.get("status") == "event_published"
        }
        seen_manual_actions = {
            row.get("action_key")
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_MANUAL_ACTIONS and row.get("status") == "manual_required"
        }
        seen_approval_actions = {
            row.get("action_key")
            for row in last_status.get("actions", [])
            if row.get("action_key") in REQUIRED_APPROVAL_ACTIONS
            and row.get("status") == "approval_required"
            and bool(row.get("simulation") or ((row.get("result") or {}) if isinstance(row.get("result"), dict) else {}).get("simulation", True))
        }
        generated_docs = last_status.get("generated_docs", [])
        workflow_runtime_complete = (
            REQUIRED_EVENTS <= seen_events
            and REQUIRED_SIMULATED_ACTIONS <= seen_simulated_actions
            and REQUIRED_EVENT_ACTIONS <= seen_event_actions
            and REQUIRED_MANUAL_ACTIONS <= seen_manual_actions
            and REQUIRED_APPROVAL_ACTIONS <= seen_approval_actions
            and bool(generated_docs)
        )
        docs_marked_simulated = generated_docs_have_simulated_marker(generated_docs) if workflow_runtime_complete else False

        if workflow_runtime_complete and docs_marked_simulated:
            print("direct-development SOP PoC smoke passed")
            print(
                json.dumps(
                    {
                        "trace_id": trace_id,
                        "workflow_key": WORKFLOW_KEY,
                        "status_page_url": f"/workflows/{WORKFLOW_KEY}/status?" + urlencode({"employee_id": EMPLOYEE_ID, "trace_id": trace_id}),
                        "status_raw_url": f"/api/workflows/{WORKFLOW_KEY}/status/raw?" + urlencode({"employee_id": EMPLOYEE_ID, "trace_id": trace_id}),
                        "events": sorted(seen_events),
                        "generated_docs": generated_docs,
                        "simulated_actions": compact_action_rows(simulated_actions),
                        "event_publish_actions": sorted(seen_event_actions),
                        "manual_required_actions": sorted(seen_manual_actions),
                        "approval_required_actions": sorted(seen_approval_actions),
                        "docs_marked_simulated": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        print(
            "waiting",
            json.dumps(
                {
                    "events": sorted(seen_events),
                    "simulated_actions": sorted(seen_simulated_actions),
                    "event_publish_actions": sorted(seen_event_actions),
                    "manual_actions": sorted(seen_manual_actions),
                    "approval_actions": sorted(seen_approval_actions),
                    "generated_docs": len(generated_docs),
                    "docs_marked_simulated": docs_marked_simulated if workflow_runtime_complete else "not_checked_until_runtime_complete",
                },
                ensure_ascii=False,
            ),
        )
        time.sleep(POLL_SECONDS)

    print("direct-development SOP PoC smoke failed", file=sys.stderr)
    print(json.dumps(last_status, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
