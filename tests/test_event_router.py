from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path
from typing import Any


class FakeKafkaProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def send_and_wait(self, topic: str, payload: dict[str, Any]) -> None:
        self.sent.append((topic, payload))


class FakeHttpResponse:
    def __init__(self, body: dict[str, Any] | None = None, status_code: int = 200) -> None:
        self._body = body or {"ok": True}
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._body

    def raise_for_status(self) -> None:
        return None


class FakeRouterHttpClient:
    requests: list[dict[str, Any]] = []
    init_kwargs: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.init_kwargs.append(dict(kwargs))

    async def __aenter__(self) -> "FakeRouterHttpClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def post(self, url: str, headers: dict[str, str] | None = None, json: dict[str, Any] | None = None) -> FakeHttpResponse:
        self.requests.append({"url": url, "headers": headers or {}, "json": json or {}})
        if url.endswith("/api/actions/dispatch"):
            return FakeHttpResponse(
                {
                    "ok": True,
                    "status": "dispatched",
                    "boi_id": "boi:private:100001:event-router-enrich",
                    "results": [
                        {
                            "action_key": "boi.materialize_event",
                            "type": "boi_materialize",
                            "result": {"status": "materialized"},
                        },
                        {
                            "action_key": "sop.equipment.request_raw_data",
                            "type": "api",
                            "result": {"status": "invoked"},
                        },
                    ],
                }
            )
        if url.endswith("/api/boi/enrich-from-dispatch"):
            return FakeHttpResponse({"ok": True, "enriched": True, "boi_id": "boi:private:100001:event-router-enrich"})
        return FakeHttpResponse({"ok": True})


def load_event_router(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")
    fake_aiokafka.AIOKafkaConsumer = object
    fake_aiokafka.AIOKafkaProducer = object
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("event_adapter.app.main", None)
    module = importlib.import_module("event_adapter.app.main")
    FakeRouterHttpClient.requests = []
    FakeRouterHttpClient.init_kwargs = []
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeRouterHttpClient)
    return module


def test_event_router_enriches_generated_boi_after_dispatch(monkeypatch):
    router = load_event_router(monkeypatch)
    producer = FakeKafkaProducer()
    event = {
        "event_id": "evt-router-enrich",
        "event_type": "root_cause.analysis.requested.v1",
        "trace_id": "trace-router-enrich",
        "actor": {"employee_id": "100001"},
        "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
    }

    asyncio.run(router.process_event(event, producer))

    enrich_calls = [req for req in FakeRouterHttpClient.requests if req["url"].endswith("/api/boi/enrich-from-dispatch")]
    assert enrich_calls
    assert enrich_calls[0]["json"]["event"] == event
    assert enrich_calls[0]["json"]["employee_id"] == "100001"
    assert enrich_calls[0]["json"]["dispatch_result"]["boi_id"] == "boi:private:100001:event-router-enrich"


def test_event_router_dispatch_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("EVENT_ROUTER_DISPATCH_TIMEOUT_SECONDS", "240")
    router = load_event_router(monkeypatch)
    event = {
        "event_id": "evt-router-timeout",
        "event_type": "direct_development.cross_section.requested.v1",
        "actor": {"employee_id": "100001"},
        "payload": {},
    }

    result = asyncio.run(router.dispatch_event(event))

    assert result["status"] == "dispatched"
    dispatch_client_kwargs = [
        kwargs
        for kwargs, request in zip(FakeRouterHttpClient.init_kwargs, FakeRouterHttpClient.requests, strict=False)
        if request["url"].endswith("/api/actions/dispatch")
    ]
    assert dispatch_client_kwargs
    assert dispatch_client_kwargs[0]["timeout"] == 240


def test_event_router_uses_manual_offset_commit(monkeypatch):
    router = load_event_router(monkeypatch)
    source = Path(router.__file__).read_text(encoding="utf-8")

    assert "enable_auto_commit=False" in source
    assert "await consumer.commit()" in source


def test_event_router_compacts_dispatch_result_for_audit(monkeypatch):
    router = load_event_router(monkeypatch)
    large_message = "SIMULATED evidence " * 1000

    compacted = router.compact_dispatch_result_for_audit(
        {
            "ok": True,
            "status": "dispatched",
            "results": [
                {
                    "action_key": "direct_development.fab_trend_compare.simulate",
                    "type": "langflow",
                    "result": {
                        "status": "langflow_invoked",
                        "message": large_message,
                        "simulation_agent": {
                            "coverage_report": {"coverage_score": 1.0, "missing_context": []},
                            "agent": {"retrieval_rounds": 4},
                            "context_pack": {
                                "documents": [
                                    {
                                        "role": "action_spec",
                                        "boi_id": "boi:public:actions:langflow:direct-development-fab-trend-compare-simulate",
                                        "uri": "/public/actions/langflow/direct-development-fab-trend-compare-simulate.md",
                                        "title": "FAB Trend 비교 시뮬레이션",
                                    }
                                ]
                            },
                            "evidence_packets": [
                                {
                                    "id": "fab_trend",
                                    "label": "FAB Trend",
                                    "provenance": "simulated_prerequisite",
                                    "source_action": "direct_development.fab_trend_compare.simulate",
                                }
                            ],
                        },
                    },
                }
            ],
        }
    )

    message = compacted["results"][0]["result"]["message"]
    assert len(message) < len(large_message)
    assert "truncated for event audit" in message
    assert compacted["results"][0]["result"]["simulation_agent"]["coverage_score"] == 1.0
    assert compacted["result_count"] == 1
