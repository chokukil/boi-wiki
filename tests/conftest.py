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
    monkeypatch.setenv("WORKFLOW_CATALOG_ROOT", str(Path.cwd() / "data" / "workflow_catalog"))
    monkeypatch.setenv("EVENT_SKILL_CATALOG_ROOT", str(Path.cwd() / "data" / "event_skill_catalog"))
    monkeypatch.setenv("ACTION_SKILL_CATALOG_ROOT", str(Path.cwd() / "data" / "action_skill_catalog"))
    monkeypatch.setenv("ACTION_LOG_ROOT", str(tmp_path / "actions"))
    monkeypatch.setenv("BOI_LLM_BASE_URL", "http://llm-gateway.example:1236/v1")
    monkeypatch.setenv("BOI_LLM_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setenv("BOI_LLM_API_KEY", "not-needed")
    # Unit tests use placeholder LLM endpoints unless a test explicitly
    # monkeypatches an LLM caller. The *_REQUIRED env names remain for compose
    # compatibility, but the runtime policy is intentionally not downgradeable.
    monkeypatch.setenv("BOI_AGENT_COMPOSER_REQUIRED", "0")

    FakeKafkaProducer.sent_events = []
    sys.modules.pop("boi_api.app.main", None)
    module = importlib.import_module("boi_api.app.main")
    module.AIOKafkaProducer = FakeKafkaProducer
    original_suggestions = module.call_boi_agent_suggestions_llm

    def test_suggestions_llm(req, employee_id: str, page_context: dict[str, Any]) -> list[str]:
        """Keep route tests offline unless they explicitly enable the LLM path.

        Runtime policy still treats missing suggestion generation as a service
        error.  The default test fixture uses placeholder LLM endpoints, so this
        test double only stands in while the LLM flag is disabled.  Tests that
        validate the real request payload flip the flag back on and exercise the
        original implementation.
        """

        if getattr(module, "BOI_AGENT_SUGGESTIONS_LLM_ENABLED", False):
            return original_suggestions(req, employee_id, page_context)
        if getattr(req, "answer_context", None):
            intent = str(req.answer_context.get("intent") or "답변")
            return [
                f"방금 {intent} 답변에서 사용한 근거를 더 자세히 설명해줘.",
                "답변에 나온 관련 문서와 업무 요청을 표로 정리해줘.",
                "이 내용을 기준으로 다음에 확인해야 할 업무를 알려줘.",
            ]
        title = str((page_context or {}).get("title") or "현재 페이지")
        return [
            f"{title}에서 가장 중요한 BoI 근거를 요약해줘.",
            "이 화면과 연결된 Event, Action, SOP를 찾아줘.",
            "현재 맥락에서 다음에 확인해야 할 업무를 알려줘.",
        ]

    monkeypatch.setattr(module, "call_boi_agent_suggestions_llm", test_suggestions_llm)
    try:
        yield module
    finally:
        sys.modules.pop("boi_api.app.main", None)
        shutil.rmtree(tmp_path, ignore_errors=True)
