from __future__ import annotations

import copy
import asyncio
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib import error as urllib_error, request as urllib_request
from urllib.parse import urlsplit


@dataclass(frozen=True)
class IntegrationTarget:
    integration_id: str
    label: str
    target: str
    probe: Literal["http", "tcp", "kafka"] = "http"
    required: bool = False
    json_contract: dict[str, Any] = field(default_factory=dict)
    probe_options: dict[str, Any] = field(default_factory=dict)


class IntegrationHealthRegistry:
    """Small non-blocking registry shared by navigation and diagnostics."""

    def __init__(self, targets: list[IntegrationTarget], *, interval_seconds: float = 10.0):
        self.targets = {item.integration_id: item for item in targets}
        self.interval_seconds = max(2.0, float(interval_seconds))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._inflight: set[str] = set()
        self._state: dict[str, dict[str, object]] = {
            key: self._initial_state(item) for key, item in self.targets.items()
        }

    @staticmethod
    def _initial_state(target: IntegrationTarget) -> dict[str, object]:
        return {
            "integration_id": target.integration_id,
            "label": target.label,
            "configured": bool(target.target),
            "available": False,
            "required": target.required,
            "checked_at": 0.0,
            "latency_ms": 0,
            "status": "checking" if target.target else "not_configured",
            "error": "",
        }

    @staticmethod
    def _tcp_target(value: str) -> tuple[str, int]:
        raw = value.split(",", 1)[0].strip()
        parsed = urlsplit(raw if "://" in raw else f"tcp://{raw}")
        return parsed.hostname or "", int(parsed.port or 0)

    @classmethod
    def _probe(cls, target: IntegrationTarget) -> tuple[bool, str, dict[str, Any]]:
        if not target.target:
            return False, "not configured", {}
        if target.probe == "kafka":
            return cls._probe_kafka(target)
        if target.probe == "tcp":
            host, port = cls._tcp_target(target.target)
            if not host or not port:
                return False, "invalid TCP target", {}
            try:
                with socket.create_connection((host, port), timeout=0.6):
                    return True, "", {}
            except OSError as exc:
                return False, type(exc).__name__, {}
        try:
            req = urllib_request.Request(target.target.rstrip("/"), method="GET")
            with urllib_request.urlopen(req, timeout=0.8) as response:  # noqa: S310 - operator-configured integration.
                metadata: dict[str, Any] = {}
                if target.json_contract:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, dict):
                        return False, "invalid JSON contract", {}
                    metadata = {
                        "service": payload.get("service"),
                        "contract_version": (payload.get("agent_response_contract") or {}).get("version"),
                        "tool_count": (payload.get("capabilities") or {}).get("tools"),
                    }
                    for dotted_key, expected in target.json_contract.items():
                        value: Any = payload
                        for part in dotted_key.split("."):
                            value = value.get(part) if isinstance(value, dict) else None
                        if value != expected:
                            return False, f"contract mismatch: {dotted_key}", metadata
                return int(response.status) < 500, "", metadata
        except urllib_error.HTTPError as exc:
            return exc.code < 500, "" if exc.code < 500 else f"HTTP {exc.code}", {}
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return False, type(exc).__name__, {}

    @staticmethod
    def _probe_kafka(target: IntegrationTarget) -> tuple[bool, str, dict[str, Any]]:
        # aiokafka creates internal futures before its first DNS failure is
        # reported. A cheap socket preflight keeps an invalid Docker-only host
        # from leaving unobserved future exceptions in the API process.
        try:
            host, port = IntegrationHealthRegistry._tcp_target(target.target)
            if not host or not port:
                return False, "invalid Kafka target", {}
            with socket.create_connection((host, port), timeout=0.6):
                pass
        except OSError as exc:
            return False, type(exc).__name__, {}

        async def inspect_topics() -> tuple[set[str], set[str]]:
            from aiokafka.admin import AIOKafkaAdminClient

            options = dict(target.probe_options)
            expected_topics = options.pop("expected_topics", [])
            timeout_seconds = float(options.pop("timeout_seconds", 1.5))
            admin = AIOKafkaAdminClient(bootstrap_servers=target.target, **options)
            try:
                await asyncio.wait_for(admin.start(), timeout=timeout_seconds)
                topics = await asyncio.wait_for(admin.list_topics(), timeout=timeout_seconds)
                return {str(item) for item in topics}, {str(item) for item in expected_topics}
            finally:
                await admin.close()

        try:
            topics, expected = asyncio.run(inspect_topics())
        except Exception as exc:
            return False, type(exc).__name__, {}
        missing = sorted(expected - topics)
        metadata = {
            "topic_count": len(topics),
            "expected_topics": sorted(expected),
            "missing_topics": missing,
        }
        if missing:
            return False, "missing Kafka topic metadata", metadata
        return True, "", metadata

    def _refresh_target(self, key: str, target: IntegrationTarget) -> None:
        started = time.perf_counter()
        try:
            probe_result = self._probe(target)
            if len(probe_result) == 2:  # Compatibility for small test and deployment probes.
                available, error = probe_result
                metadata = {}
            else:
                available, error, metadata = probe_result
            refreshed = {
                **self._initial_state(target),
                "available": available,
                "checked_at": time.time(),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "status": "ready" if available else ("unavailable" if target.target else "not_configured"),
                "error": error,
                "metadata": metadata,
            }
            with self._lock:
                self._state[key] = refreshed
        except Exception as exc:
            with self._lock:
                self._state[key] = {
                    **self._initial_state(target),
                    "checked_at": time.time(),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "status": "unavailable",
                    "error": type(exc).__name__,
                }
        finally:
            with self._lock:
                self._inflight.discard(key)

    def refresh(self) -> dict[str, dict[str, object]]:
        """Start independent probes and return immediately with the cached state."""
        for key, target in self.targets.items():
            if not target.target:
                with self._lock:
                    self._state[key] = self._initial_state(target)
                continue
            with self._lock:
                if key in self._inflight:
                    continue
                self._inflight.add(key)
            threading.Thread(
                target=self._refresh_target,
                args=(key, target),
                name=f"boi-integration-health-{key}",
                daemon=True,
            ).start()
        return self.snapshot()

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return copy.deepcopy(self._state)

    def available(self, integration_id: str) -> bool:
        return bool(self.snapshot().get(integration_id, {}).get("available"))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def run() -> None:
            while not self._stop.is_set():
                self.refresh()
                self._stop.wait(self.interval_seconds)

        self._thread = threading.Thread(target=run, name="boi-integration-health", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
