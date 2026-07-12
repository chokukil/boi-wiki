from __future__ import annotations

import json
import time

from boi_api.app.integration_health import IntegrationHealthRegistry, IntegrationTarget


def wait_for(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_integration_probes_are_independent_and_refresh_returns_immediately(monkeypatch):
    registry = IntegrationHealthRegistry(
        [
            IntegrationTarget("slow", "Slow", "http://slow.example"),
            IntegrationTarget("fast", "Fast", "http://fast.example"),
        ],
        interval_seconds=2,
    )
    calls = {"slow": 0, "fast": 0}

    def probe(target: IntegrationTarget):
        calls[target.integration_id] += 1
        if target.integration_id == "slow":
            time.sleep(0.35)
        return True, ""

    monkeypatch.setattr(registry, "_probe", probe)
    started = time.perf_counter()
    snapshot = registry.refresh()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.1
    assert snapshot["slow"]["status"] == "checking"
    wait_for(lambda: registry.snapshot()["fast"]["status"] == "ready")
    assert registry.snapshot()["slow"]["status"] == "checking"

    registry.refresh()
    assert calls["slow"] == 1
    wait_for(lambda: registry.snapshot()["slow"]["status"] == "ready")


def test_integration_probe_exception_becomes_unavailable(monkeypatch):
    registry = IntegrationHealthRegistry(
        [IntegrationTarget("broken", "Broken", "http://broken.example")],
        interval_seconds=2,
    )

    def fail(_target: IntegrationTarget):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(registry, "_probe", fail)
    registry.refresh()
    wait_for(lambda: registry.snapshot()["broken"]["status"] == "unavailable")

    state = registry.snapshot()["broken"]
    assert state["available"] is False
    assert state["error"] == "RuntimeError"
    assert state["checked_at"] > 0


def test_json_contract_probe_validates_mcp_version_and_tool_count(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {
                    "service": "boi-wiki-mcp",
                    "agent_response_contract": {"version": "2.0"},
                    "capabilities": {"tools": 10},
                }
            ).encode()

    monkeypatch.setattr("boi_api.app.integration_health.urllib_request.urlopen", lambda *_args, **_kwargs: Response())
    target = IntegrationTarget(
        "mcp",
        "MCP",
        "http://mcp.example/status.json",
        json_contract={
            "service": "boi-wiki-mcp",
            "agent_response_contract.version": "2.0",
            "capabilities.tools": 10,
        },
    )

    available, error, metadata = IntegrationHealthRegistry._probe(target)

    assert available is True
    assert error == ""
    assert metadata == {"service": "boi-wiki-mcp", "contract_version": "2.0", "tool_count": 10}


def test_json_contract_probe_rejects_an_incompatible_mcp_surface(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"service":"boi-wiki-mcp","agent_response_contract":{"version":"1.0"},"capabilities":{"tools":137}}'

    monkeypatch.setattr("boi_api.app.integration_health.urllib_request.urlopen", lambda *_args, **_kwargs: Response())
    target = IntegrationTarget(
        "mcp",
        "MCP",
        "http://mcp.example/status.json",
        json_contract={"agent_response_contract.version": "2.0", "capabilities.tools": 10},
    )

    available, error, metadata = IntegrationHealthRegistry._probe(target)

    assert available is False
    assert error == "contract mismatch: agent_response_contract.version"
    assert metadata["tool_count"] == 137


def test_kafka_probe_requires_expected_topic_metadata(monkeypatch):
    class FakeAdmin:
        def __init__(self, **kwargs):
            assert kwargs["bootstrap_servers"] == "kafka.example:9092"

        async def start(self):
            return None

        async def list_topics(self):
            return {"boi.events", "boi.audit"}

        async def close(self):
            return None

    monkeypatch.setattr("aiokafka.admin.AIOKafkaAdminClient", FakeAdmin)
    target = IntegrationTarget(
        "event_broker",
        "Event Broker",
        "kafka.example:9092",
        probe="kafka",
        probe_options={"expected_topics": ["boi.events"], "timeout_seconds": 0.1},
    )

    available, error, metadata = IntegrationHealthRegistry._probe(target)

    assert available is True
    assert error == ""
    assert metadata["expected_topics"] == ["boi.events"]
    assert metadata["missing_topics"] == []


def test_kafka_probe_rejects_open_port_without_expected_topic(monkeypatch):
    class FakeAdmin:
        def __init__(self, **_kwargs):
            pass

        async def start(self):
            return None

        async def list_topics(self):
            return {"unrelated.topic"}

        async def close(self):
            return None

    monkeypatch.setattr("aiokafka.admin.AIOKafkaAdminClient", FakeAdmin)
    target = IntegrationTarget(
        "event_broker",
        "Event Broker",
        "kafka.example:9092",
        probe="kafka",
        probe_options={"expected_topics": ["boi.events"], "timeout_seconds": 0.1},
    )

    available, error, metadata = IntegrationHealthRegistry._probe(target)

    assert available is False
    assert error == "missing Kafka topic metadata"
    assert metadata["missing_topics"] == ["boi.events"]
