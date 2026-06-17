from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_gateway_module(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ACTION_CATALOG_ROOT", str(Path.cwd() / "data" / "action_catalog"))
    monkeypatch.setenv("ACTION_LOG_ROOT", str(tmp_path / "actions"))
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    sys.modules.pop("action_gateway.app.main", None)
    return importlib.import_module("action_gateway.app.main")


def test_manual_task_invocation_records_human_handoff_without_external_call(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.confirm_alarm_context",
            "employee_id": "100001",
            "event": {"event_id": "evt-manual-test", "event_type": "equipment.alarm.raised.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "manual_required"
    assert body["action_key"] == "manual.equipment.confirm_alarm_context"
    assert body["manual_handoff"]["owner"] == "AIX 확산 TF / 제조 PoC"

    logs = client.get("/api/actions/logs", headers={"x-service-token": "test-service-token"}).json()["items"]
    assert logs[0]["status"] == "manual_required"
    assert logs[0]["action_type"] == "manual_task"


def test_manual_approval_task_requires_approved_by_before_completion(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.approve_process_hold",
            "employee_id": "100001",
            "event": {"event_id": "evt-approval-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "approval_required"
    assert body["action"]["type"] == "manual_task"

    approved = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.approve_process_hold",
            "employee_id": "100001",
            "event": {"event_id": "evt-approval-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
            "approved_by": "line-manager-001",
        },
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "manual_required"
    assert approved.json()["manual_handoff"]["approved_by"] == "line-manager-001"


class FakeHttpResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {"ok": True, "status": "invoked"}
        self.text = str(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def request(self, method, url, headers=None, json=None):
        self.requests.append({"method": method, "url": url, "headers": headers or {}, "json": json or {}})
        return FakeHttpResponse(body={"ok": True, "status": "invoked", "result": {"trend_status": "anomaly_detected"}})

    async def post(self, url, headers=None, json=None):
        self.requests.append({"method": "POST", "url": url, "headers": headers or {}, "json": json or {}})
        return FakeHttpResponse(body={"ok": True, "status": "mcp_invoked", "tool": "boi.search", "results": [{"title": "Kafka SOP"}]})


class FakeLangflowAsyncClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers=None):
        self.requests.append({"method": "GET", "url": url, "headers": headers or {}})
        if url.endswith("/api/v1/auto_login"):
            return FakeHttpResponse(body={"access_token": "langflow-test-token"})
        if url.endswith("/api/v1/flows/"):
            return FakeHttpResponse(
                body=[
                    {
                        "id": "old-flow-id",
                        "name": "BoI Reference Flow",
                        "endpoint_name": "boi-reference-flow",
                        "updated_at": "2026-06-16T16:04:25+00:00",
                        "data": {"nodes": []},
                    },
                    {
                        "id": "latest-flow-id",
                        "name": "BoI Reference Flow (3)",
                        "endpoint_name": "boi-reference-flow-3",
                        "updated_at": "2026-06-17T05:48:49+00:00",
                        "data": {
                            "nodes": [
                                {"data": {"display_name": "BoI Event Input"}},
                                {"data": {"template": {"model_name": {"value": "google/gemma-4-26b-a4b-qat"}}}},
                            ]
                        },
                    },
                ]
            )
        return FakeHttpResponse(status_code=404, body={"detail": "not found"})

    async def request(self, method, url, headers=None, json=None):
        self.requests.append({"method": method, "url": url, "headers": headers or {}, "json": json or {}})
        return FakeHttpResponse(
            body={
                "session_id": "latest-flow-id",
                "outputs": [
                    {
                        "outputs": [
                            {
                                "results": {
                                    "message": {
                                        "text": "Langflow Gemma response",
                                        "properties": {
                                            "source": {
                                                "source": "google/gemma-4-26b-a4b-qat",
                                            }
                                        },
                                    }
                                }
                            }
                        ]
                    }
                ],
            }
        )


def test_langflow_reference_action_is_enabled_for_real_dispatch():
    import yaml

    catalog = yaml.safe_load((Path.cwd() / "data" / "action_catalog" / "actions.yaml").read_text(encoding="utf-8"))
    action = next(item for item in catalog["actions"] if item["action_key"] == "langflow.boi.reference_flow")

    assert action["enabled"] is True
    assert action["auto_dispatch"] is True
    assert action["type"] == "langflow_run"
    assert action["dry_run"] is False
    assert action["flow_name"] == "BoI Reference Flow"
    assert "equipment.alarm.raised.v1" in action["event_types"]


def test_langflow_run_action_resolves_latest_flow_and_invokes_run_endpoint(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeLangflowAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeLangflowAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "langflow.boi.reference_flow",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-langflow-test",
                "event_type": "equipment.alarm.raised.v1",
                "trace_id": "trace-langflow-test",
                "payload": {"title": "Langflow 연결 검증", "equipment_id": "ETCH-VM-01"},
            },
            "payload": {"title": "Langflow 연결 검증", "equipment_id": "ETCH-VM-01"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "langflow_invoked"
    assert body["flow_id"] == "latest-flow-id"
    assert body["message"] == "Langflow Gemma response"
    assert FakeLangflowAsyncClient.requests[0]["url"] == "http://langflow:7860/api/v1/auto_login"
    assert FakeLangflowAsyncClient.requests[1]["headers"]["Authorization"] == "Bearer langflow-test-token"
    run_request = FakeLangflowAsyncClient.requests[2]
    assert run_request["url"] == "http://langflow:7860/api/v1/run/latest-flow-id"
    assert run_request["json"]["input_type"] == "chat"
    assert "Langflow 연결 검증" in run_request["json"]["input_value"]


def test_api_action_invokes_configured_boi_api_endpoint(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "sop.equipment.request_trend_history",
            "employee_id": "100001",
            "event": {"event_id": "evt-api-test", "event_type": "equipment.alarm.raised.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"},
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invoked"
    assert FakeAsyncClient.requests[0]["url"] == "http://boi-api:8000/api/poc/equipment/trend-history"
    assert FakeAsyncClient.requests[0]["headers"]["x-service-token"] == "test-service-token"
    assert FakeAsyncClient.requests[0]["json"]["payload"]["equipment_id"] == "ETCH-VM-01"


def test_mcp_action_invokes_boi_api_bridge_endpoint(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "mcp.boi_search.sample",
            "employee_id": "100001",
            "event": {"event_id": "evt-mcp-test", "event_type": "maintenance.guide.requested.v1"},
            "payload": {"query": "Kafka"},
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mcp_invoked"
    assert FakeAsyncClient.requests[0]["url"] == "http://boi-api:8000/api/poc/mcp/call"
    assert FakeAsyncClient.requests[0]["headers"]["x-service-token"] == "test-service-token"
    assert FakeAsyncClient.requests[0]["json"]["tool"] == "boi.search"
    assert FakeAsyncClient.requests[0]["json"]["arguments"]["query"] == "Kafka"


def test_high_risk_api_action_invokes_endpoint_only_after_approval(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(gateway.app)

    blocked = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "sop.equipment.block_process_progress",
            "employee_id": "100001",
            "event": {"event_id": "evt-risk-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01"},
            "dry_run": False,
        },
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "approval_required"
    assert FakeAsyncClient.requests == []

    approved = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "sop.equipment.block_process_progress",
            "employee_id": "100001",
            "event": {"event_id": "evt-risk-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01"},
            "dry_run": False,
            "approved_by": "line-manager-001",
        },
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "invoked"
    assert FakeAsyncClient.requests[0]["url"] == "http://boi-api:8000/api/poc/equipment/process-hold"
    assert FakeAsyncClient.requests[0]["json"]["approved_by"] == "line-manager-001"
