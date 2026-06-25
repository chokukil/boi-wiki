from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeKafkaProducer:
    sent_events: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send_and_wait(self, topic: str, event: dict[str, Any]) -> None:
        self.sent_events.append({"topic": topic, "event": event})


def _fast_tmp_path(prefix: str) -> Path:
    base = Path(os.getenv("BOI_TEST_TMPDIR") or "/tmp")
    if not base.exists() or not os.access(base, os.W_OK):
        base = Path(tempfile.gettempdir())
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(base)))


@pytest.fixture()
def boi_app_module(monkeypatch: pytest.MonkeyPatch):
    fake_aiokafka = types.ModuleType("aiokafka")
    fake_aiokafka.AIOKafkaProducer = FakeKafkaProducer
    fake_aiokafka.AIOKafkaConsumer = object
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)

    tmp_path = _fast_tmp_path("boi-api-test-")
    data_root = tmp_path / "boi"
    shutil.copytree(ROOT / "data" / "boi", data_root)

    monkeypatch.setenv("TMPDIR", "/tmp")
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("EVENTS_ROOT", str(tmp_path / "events"))
    monkeypatch.setenv("EVENT_CATALOG_ROOT", str(Path.cwd() / "data" / "event_catalog"))
    monkeypatch.setenv("ACTION_CATALOG_ROOT", str(Path.cwd() / "data" / "action_catalog"))
    monkeypatch.setenv("ACTION_LOG_ROOT", str(tmp_path / "actions"))
    monkeypatch.setenv("BOI_LLM_BASE_URL", "http://llm-gateway.example:1236/v1")
    monkeypatch.setenv("BOI_LLM_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setenv("BOI_LLM_API_KEY", "not-needed")
    # Unit tests use placeholder LLM endpoints unless a test explicitly enables
    # the composer. Runtime defaults remain stricter.
    monkeypatch.setenv("BOI_AGENT_COMPOSER_REQUIRED", "0")

    FakeKafkaProducer.sent_events = []
    sys.modules.pop("boi_api.app.main", None)
    module = importlib.import_module("boi_api.app.main")
    module.AIOKafkaProducer = FakeKafkaProducer
    try:
        yield module
    finally:
        sys.modules.pop("boi_api.app.main", None)
        shutil.rmtree(tmp_path, ignore_errors=True)
