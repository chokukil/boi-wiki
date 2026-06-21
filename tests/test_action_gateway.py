from __future__ import annotations

import importlib
import sys
from pathlib import Path

import httpx
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


def test_fallback_action_summary_truncates_at_word_boundary_with_ellipsis(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    long_message = "Current Finding " + ("stable summary word " * 80)

    summary = gateway.summarize_action_result({"ok": True, "status": "invoked", "message": long_message})

    assert len(summary) <= 503
    assert summary.endswith("...")
    assert not summary.endswith(" ...")


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
                                {"data": {"display_name": "BoI Wiki Writer"}},
                                {"data": {"template": {"model_name": {"value": "google/gemma-4-26b-a4b-qat"}}}},
                            ]
                        },
                    },
                    {
                        "id": "simulator-flow-id",
                        "name": "BoI Universal Action Simulator Flow",
                        "endpoint_name": "boi-universal-action-simulator",
                        "updated_at": "2026-06-21T00:00:00+00:00",
                        "data": {
                            "nodes": [
                                {"data": {"display_name": "BoI Wiki Writer"}},
                                {"data": {"template": {"model_name": {"value": "google/gemma-4-26b-a4b-qat"}}}},
                            ]
                        },
                    },
                ]
            )
        return FakeHttpResponse(status_code=404, body={"detail": "not found"})

    async def post(self, url, headers=None, json=None):
        self.requests.append({"method": "POST", "url": url, "headers": headers or {}, "json": json or {}})
        if url.endswith("/api/simulations/universal-agent"):
            return FakeHttpResponse(
                body={
                    "ok": True,
                    "status": "simulated_context_ready",
                    "agent": {"name": "BoI Simulation Agent", "version": "0.1", "retrieval_rounds": 3},
                    "context_pack": {
                        "documents": [
                            {
                                "role": "action_spec",
                                "title": "Response Trend 확인 시뮬레이션",
                                "boi_id": "boi:public:actions:langflow:direct-development-quality-response-trend-simulate",
                                "uri": "/public/actions/langflow/direct-development-quality-response-trend-simulate.md",
                                "match_reason": "exact_ref",
                            }
                        ]
                    },
                    "retrieval_trace": [{"round": 1, "objective": "Resolve exact references.", "found_docs": []}],
                    "coverage_report": {"coverage_score": 1.0, "missing_context": [], "covered": {"action_contract": True}},
                    "evidence_packets": [
                        {
                            "evidence_key": "response_trend",
                            "title": "Response Trend evidence",
                            "action_key": "direct_development.quality_response_trend.simulate",
                            "provenance": "simulated_prerequisite",
                            "fields": {"trend_status": "simulated_response_trend_abnormality_reviewed"},
                        }
                    ],
                    "citations": [{"label": "action_spec", "title": "Response Trend 확인 시뮬레이션"}],
                    "limitations": ["SIMULATED dry-run result only; no unavailable internal system was called."],
                    "simulation_result": {
                        "status": "simulated",
                        "markdown": "# SIMULATED BoI Wiki Simulation Result\n\n## Current Finding\nAgent context ready",
                    },
                }
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


class FakeLangflowTimeoutAsyncClient(FakeLangflowAsyncClient):
    async def request(self, method, url, headers=None, json=None):
        self.requests.append({"method": method, "url": url, "headers": headers or {}, "json": json or {}})
        raise httpx.ReadTimeout("renderer exceeded timeout")


class FakeLangflowResolveTimeoutAsyncClient(FakeLangflowAsyncClient):
    async def get(self, url, headers=None):
        self.requests.append({"method": "GET", "url": url, "headers": headers or {}})
        if url.endswith("/api/v1/auto_login"):
            return FakeHttpResponse(body={"access_token": "langflow-test-token"})
        if url.endswith("/api/v1/flows/"):
            raise httpx.ReadTimeout("flow list exceeded timeout")
        return FakeHttpResponse(status_code=404, body={"detail": "not found"})


class FakeDispatchAsyncClient:
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
                        "id": "stage-flow-id",
                        "name": "BoI Equipment Stage Analysis Flow",
                        "endpoint_name": "boi-equipment-stage-analysis",
                        "updated_at": "2026-06-18T00:00:00+00:00",
                        "data": {
                            "nodes": [
                                {"data": {"display_name": "BoI Wiki Writer"}},
                                {"data": {"template": {"model_name": {"value": "google/gemma-4-26b-a4b-qat"}}}},
                            ]
                        },
                    }
                ]
            )
        return FakeHttpResponse(status_code=404, body={"detail": "not found"})

    async def post(self, url, headers=None, json=None):
        self.requests.append({"method": "POST", "url": url, "headers": headers or {}, "json": json or {}})
        if url.endswith("/api/boi/materialize-event"):
            return FakeHttpResponse(
                body={
                    "ok": True,
                    "item": {
                        "metadata": {"boi_id": "boi:private:100001:dispatch-prior-results"},
                        "body": "# Summary\n\npending enrichment",
                    },
                }
            )
        if "/api/events/publish" in url:
            return FakeHttpResponse(body={"ok": True, "event": {"event_type": json.get("event_type")}})
        return FakeHttpResponse(body={"ok": True})

    async def request(self, method, url, headers=None, json=None):
        self.requests.append({"method": method, "url": url, "headers": headers or {}, "json": json or {}})
        if url.endswith("/api/poc/equipment/raw-data"):
            return FakeHttpResponse(
                body={
                    "ok": True,
                    "status": "invoked",
                    "result": {
                        "raw_data_ref": "/mock/vision-inspection/raw-data/ETCH-VM-01/LOT-001",
                        "message": "Raw data loaded",
                    },
                }
            )
        if url.endswith("/api/poc/equipment/maintenance-guide"):
            return FakeHttpResponse(
                body={
                    "ok": True,
                    "status": "invoked",
                    "result": {
                        "guide_boi_ref": "boi:public:sop:equipment-abnormal-response",
                        "message": "Guide loaded",
                    },
                }
            )
        if "/api/v1/run/" in url:
            return FakeHttpResponse(
                body={
                    "outputs": [
                        {
                            "outputs": [
                                {
                                    "results": {
                                        "message": {"text": "Stage analysis from Langflow"}
                                    }
                                }
                            ]
                        }
                    ]
                }
            )
        return FakeHttpResponse(body={"ok": True, "status": "invoked"})


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


def test_universal_simulator_langflow_action_records_simulation_metadata(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeLangflowAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeLangflowAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "direct_development.quality_response_trend.simulate",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-direct-sim-test",
                "event_type": "direct_development.result_check.requested.v1",
                "trace_id": "trace-direct-sim-test",
                "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
            },
            "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "langflow_invoked"
    assert body["flow_id"] == "simulator-flow-id"
    assert body["simulation"] is True
    assert body["simulation_label"] == "SIMULATED"
    assert body["real_system_connected"] is False
    assert body["simulated_system"] == "품질 시스템"
    assert body["retrieval_rounds"] == 3
    assert body["coverage_score"] == 1.0
    assert body["evidence_packets"][0]["evidence_key"] == "response_trend"
    assert body["used_docs"][0]["role"] == "action_spec"

    agent_request = next(req for req in FakeLangflowAsyncClient.requests if req["url"] == "http://boi-api:8000/api/simulations/universal-agent")
    assert agent_request["headers"]["x-service-token"] == "test-service-token"
    assert agent_request["json"]["action_key"] == "direct_development.quality_response_trend.simulate"
    assert agent_request["json"]["simulation_depth"] == "stage_prerequisites"
    run_request = next(req for req in FakeLangflowAsyncClient.requests if "/api/v1/run/" in req["url"])
    assert run_request["url"] == "http://langflow:7860/api/v1/run/simulator-flow-id"
    assert "BoI Simulation Agent retrieved context" in run_request["json"]["input_value"]
    assert "retrieval_trace" in run_request["json"]["input_value"]
    assert "SIMULATED action request" in run_request["json"]["input_value"]
    assert "Tech-A" in run_request["json"]["input_value"]

    logs = client.get("/api/actions/logs", headers={"x-service-token": "test-service-token"}).json()["items"]
    assert logs[0]["action_key"] == "direct_development.quality_response_trend.simulate"
    assert logs[0]["status"] == "langflow_invoked"
    assert logs[0]["simulation"] is True
    assert logs[0]["simulation_label"] == "SIMULATED"
    assert logs[0]["retrieval_rounds"] == 3
    assert logs[0]["coverage_score"] == 1.0
    assert logs[0]["evidence_packets"][0]["provenance"] == "simulated_prerequisite"
    assert logs[0]["used_docs"][0]["role"] == "action_spec"


def test_universal_simulator_uses_simulation_agent_result_when_langflow_renderer_times_out(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeLangflowTimeoutAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeLangflowTimeoutAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "direct_development.quality_response_trend.simulate",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-direct-sim-timeout",
                "event_type": "direct_development.result_check.requested.v1",
                "trace_id": "trace-direct-sim-timeout",
                "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
            },
            "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "langflow_invoked"
    assert body["langflow_renderer_status"] == "timeout_fallback"
    assert body["response"]["fallback"] == "boi_simulation_agent"
    assert "SIMULATED BoI Wiki Simulation Result" in body["message"]
    assert body["coverage_score"] == 1.0
    assert body["evidence_packets"][0]["evidence_key"] == "response_trend"

    logs = client.get("/api/actions/logs", headers={"x-service-token": "test-service-token"}).json()["items"]
    assert logs[0]["status"] == "langflow_invoked"
    assert logs[0]["langflow_renderer_status"] == "timeout_fallback"
    assert logs[0]["coverage_score"] == 1.0
    assert logs[0]["evidence_packets"][0]["provenance"] == "simulated_prerequisite"


def test_universal_simulator_uses_simulation_agent_result_when_langflow_flow_resolve_times_out(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeLangflowResolveTimeoutAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeLangflowResolveTimeoutAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "direct_development.quality_response_trend.simulate",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-direct-sim-resolve-timeout",
                "event_type": "direct_development.result_check.requested.v1",
                "trace_id": "trace-direct-sim-resolve-timeout",
                "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
            },
            "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "langflow_invoked"
    assert body["langflow_renderer_status"] == "timeout_fallback"
    assert body["response"]["fallback"] == "boi_simulation_agent"
    assert body["coverage_score"] == 1.0
    assert body["evidence_packets"][0]["evidence_key"] == "response_trend"


def test_dispatch_passes_prior_results_to_stage_langflow_action(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeDispatchAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeDispatchAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/dispatch",
        headers={"x-service-token": "test-service-token"},
        json={
            "employee_id": "100001",
            "event": {
                "event_id": "evt-dispatch-prior-results",
                "event_type": "root_cause.analysis.requested.v1",
                "trace_id": "trace-dispatch-prior-results",
                "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "owner": "100001"},
            },
            "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "owner": "100001"},
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    result_by_key = {row["action_key"]: row for row in body["results"]}
    assert "langflow.equipment.stage_analysis" in result_by_key
    assert result_by_key["langflow.equipment.stage_analysis"]["connector_kind"] == "langflow"
    assert result_by_key["langflow.equipment.stage_analysis"]["doc_ref"] == "boi:public:actions:langflow:stage-analysis"
    assert result_by_key["langflow.equipment.stage_analysis"]["request_id"]
    assert result_by_key["langflow.equipment.stage_analysis"]["summary"]
    run_request = next(req for req in FakeDispatchAsyncClient.requests if "/api/v1/run/" in req["url"])
    input_value = run_request["json"]["input_value"]
    assert "Prior Action Results" in input_value
    assert "sop.equipment.request_raw_data" in input_value
    assert "/mock/vision-inspection/raw-data/ETCH-VM-01/LOT-001" in input_value


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
    assert FakeAsyncClient.requests[0]["url"] == "http://boi-wiki-mcp:8200/api/mcp/call"
    assert FakeAsyncClient.requests[0]["headers"]["x-service-token"] == "test-service-token"
    assert FakeAsyncClient.requests[0]["json"]["tool"] == "boi.search"
    assert FakeAsyncClient.requests[0]["json"]["arguments"]["query"] == "Kafka"


def test_event_publish_action_delegates_with_service_token(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    FakeAsyncClient.requests = []
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "sop.equipment.create_root_cause_event",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-publish-test",
                "event_type": "equipment.alarm.raised.v1",
                "trace_id": "trace-publish-test",
            },
            "payload": {
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-001",
                "wafer_id": "WF-001",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
                "owner": "100001",
            },
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "event_published"
    assert FakeAsyncClient.requests[0]["url"] == "http://boi-api:8000/api/events/publish?employee_id=100001"
    assert FakeAsyncClient.requests[0]["headers"]["x-service-token"] == "test-service-token"
    assert FakeAsyncClient.requests[0]["json"]["event_type"] == "root_cause.analysis.requested.v1"


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
