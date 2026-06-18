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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

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
