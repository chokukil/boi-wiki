from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Any
from urllib.parse import quote, unquote

from fastapi.testclient import TestClient
import pytest
import yaml


def tiny_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01"
        b"\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def append_action_log_row(boi_app_module, row: dict, filename: str = "actions-20990101.jsonl") -> str:
    boi_app_module.ensure_dirs()
    path = boi_app_module.ACTION_LOG_ROOT / filename
    line_number = len(path.read_text(encoding="utf-8").splitlines()) + 1 if path.exists() else 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    boi_app_module._FILE_SIGNATURE_CACHE.clear()
    boi_app_module._ACTION_LOG_CACHE["signature"] = None
    boi_app_module._ACTION_LOG_CACHE["rows"] = []
    return f"action:{filename}:{line_number}"


def append_event_log_row(boi_app_module, row: dict, filename: str = "events-20990101.jsonl") -> str:
    boi_app_module.ensure_dirs()
    path = boi_app_module.EVENTS_ROOT / filename
    line_number = len(path.read_text(encoding="utf-8").splitlines()) + 1 if path.exists() else 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    boi_app_module._FILE_SIGNATURE_CACHE.clear()
    boi_app_module._EVENT_LOG_CACHE["signature"] = None
    boi_app_module._EVENT_LOG_CACHE["rows"] = []
    return f"event:{filename}:{line_number}"


def test_sops_page_lists_seed_sops(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/sops?employee_id=100001")

    assert response.status_code == 200
    assert "Agent Harness SOP v0.1" in response.text
    assert "BoI Wiki SOP v0.1" in response.text


def test_sops_page_searches_and_keeps_generated_boi_out_of_default_category(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/sop",
            "title": "검색 설비 SOP 테스트",
            "description": "SOP 검색 필터 대상",
            "tags": ["SOP", "Search"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:public:sop:search-equipment-test",
            "visibility": "public",
            "classification": "internal",
            "owner": "public",
            "author": {"type": "agent", "agent_id": "test"},
            "acl_policy": "acl:public",
            "status": "reviewed",
            "review": {"reviewer": "pytest", "review_status": "reviewed"},
            "source_refs": [{"type": "test", "ref": "sop-search"}],
        },
        "# Summary\n\n설비 검색 대상 SOP 본문",
    )
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/action",
            "title": "Generated SOP Instance Should Not Default",
            "description": "SOP stage 기반 업무 실행 기록",
            "tags": ["SOP", "AI-Native-Workflow"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:sop-generated-filter-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "test"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "sop-generated"}],
        },
        "# Summary\n\nGenerated SOP related record",
    )

    filtered = client.get("/sops?employee_id=100001&q=설비&visibility=public&status=reviewed")
    default_page = client.get("/sops?employee_id=100001")
    related = client.get("/sops?employee_id=100001&category=all-related")

    assert filtered.status_code == 200
    assert "검색 설비 SOP 테스트" in filtered.text
    assert "Generated SOP Instance Should Not Default" not in filtered.text
    assert "필터 적용" in filtered.text
    assert "필터 해제" in filtered.text
    assert default_page.status_code == 200
    assert "Generated SOP Instance Should Not Default" not in default_page.text
    assert related.status_code == 200
    assert "Generated SOP Instance Should Not Default" in related.text


def test_runtime_config_exposes_sanitized_gemma_settings(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/runtime/config")

    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["base_url"] == "http://llm-gateway.example:1236/v1"
    assert body["llm"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["llm"]["api_key_configured"] is True
    assert "api_key" not in body["llm"]
    assert body["boi_agent"]["router"]["mode"] == "llm_first"
    assert body["boi_agent"]["router"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["boi_agent"]["router"]["llm_enabled"] is False
    assert body["boi_agent"]["router"]["required"] is True
    assert body["boi_agent"]["router"]["failure_backoff_seconds"] == 30
    assert body["boi_agent"]["router"]["backoff_remaining_seconds"] >= 0
    assert body["boi_agent"]["router"]["max_tokens"] == 1536
    assert "api_key" not in body["boi_agent"]["router"]
    assert body["boi_agent"]["status_writer"]["timeout_seconds"] == 30
    assert body["boi_agent"]["status_writer"]["max_tokens"] == 1536
    assert body["boi_agent"]["composer"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["boi_agent"]["composer"]["max_tokens"] == 1536
    assert body["boi_agent"]["langgraph"]["required"] is True
    assert body["boi_agent"]["langgraph"]["runtime"] in {"LangGraph", "unavailable"}
    assert body["boi_agent"]["cache_warmup"]["enabled"] is True
    assert body["boi_agent"]["cache_warmup"]["status"] in {"not_started", "running", "completed", "failed", "disabled"}


def test_agent_cache_warmup_populates_runtime_indexes(boi_app_module):
    state = boi_app_module.warm_agent_runtime_caches("100001", force=True)

    assert state["status"] == "completed"
    assert state["employee_id"] == "100001"
    assert state["elapsed_ms"] >= 0
    assert state["checks"]["event_types"] >= 1
    assert state["checks"]["actions"] >= 1
    assert state["checks"]["accessible_docs"] >= 1
    assert state["checks"]["search_docs"] >= 1
    assert state["checks"]["sample_page_context_resolved"] is True


def test_agent_router_auto_enables_for_real_llm_url(boi_app_module):
    assert boi_app_module.resolve_router_llm_enabled("auto", "llm_first", "http://router.example:1236/v1") is True
    assert boi_app_module.resolve_router_llm_enabled("auto", "llm_first", "http://llm-gateway.example:1236/v1") is False
    assert boi_app_module.resolve_router_llm_enabled("false", "llm_first", "http://router.example:1236/v1") is False
    assert boi_app_module.resolve_router_llm_enabled("true", "rules", "http://llm-gateway.example:1236/v1") is True


def test_boi_agent_capabilities_expose_streaming_interface(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/agents/boi-wiki/capabilities?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["streaming"]["enabled"] is True
    assert body["streaming"]["endpoint"] == "/api/agents/boi-wiki/chat/stream"
    assert body["streaming"]["events"] == ["status", "answer_delta", "final", "error"]
    assert body["status_writer"]["required"] is True
    assert body["status_writer"]["model"]
    assert body["composer"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["native_agent"]["langgraph_required"] is True
    assert body["native_agent"]["runtime"] in {"LangGraph", "unavailable"}
    assert "progressive response streaming" in body["features"]


def test_boi_agent_stream_status_steps_require_llm_generated_plan(boi_app_module, monkeypatch):
    request = boi_app_module.BoiAgentChatRequest(
        question="이 SOP를 Mermaid 프로세스 플로우로 보여줘",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    )

    llm_steps = [
        {"stage": "page_context", "message": "현재 SOP와 접근 권한을 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "intent", "message": "요청이 프로세스 도식 생성인지 판단하고 있습니다.", "source": "llm_status"},
        {"stage": "retrieval", "message": "SOP의 Event와 Action 근거를 모으고 있습니다.", "source": "llm_status"},
        {"stage": "tool_loop", "message": "누락된 연결이 없는지 근거를 다시 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "compose", "message": "Mermaid와 표를 함께 정리하고 있습니다.", "source": "llm_status"},
        {"stage": "answer_stream", "message": "정리된 답변을 화면에 보여주고 있습니다.", "source": "llm_status"},
        {"stage": "waiting", "message": "분석이 길어져도 계속 근거를 확인하고 있습니다.", "source": "llm_status"},
    ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_status_llm", lambda req, employee_id: llm_steps)

    steps = boi_app_module.agent_stream_status_steps(request, "100001")

    assert steps == llm_steps
    assert all(step["source"] == "llm_status" for step in steps)


def test_boi_agent_stream_status_plan_without_usable_status_is_failure(boi_app_module):
    with pytest.raises(boi_app_module.BoiAgentStatusUnavailable):
        boi_app_module.normalize_llm_status_steps(
            {
                "statuses": [
                    {"stage": "unknown", "message": "현재 페이지를 확인하고 있습니다."},
                    {"stage": "intent", "message": ""},
                ]
            }
        )


def test_boi_agent_stream_plan_uses_single_llm_call_for_route_and_status(boi_app_module, monkeypatch):
    payloads = []
    statuses = [
        {"stage": "page_context", "message": "현재 SOP와 권한을 확인하고 있습니다."},
        {"stage": "intent", "message": "프로세스 도식 요청인지 판단하고 있습니다."},
        {"stage": "retrieval", "message": "SOP와 Event 근거를 찾고 있습니다."},
        {"stage": "tool_loop", "message": "Action과 Handoff 연결을 확인하고 있습니다."},
        {"stage": "compose", "message": "Mermaid와 표를 정리하고 있습니다."},
        {"stage": "answer_stream", "message": "완성된 답변을 보여주고 있습니다."},
        {"stage": "waiting", "message": "작업이 길어져도 계속 확인하고 있습니다."},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "route": "deep",
                                    "confidence": 0.93,
                                    "intent": "diagram",
                                    "reason": "stream plan",
                                    "requires_mutation": False,
                                    "requires_deep_reasoning": True,
                                    "statuses": statuses,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BASE_URL", "http://router.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    plan = boi_app_module.call_boi_agent_stream_plan_llm(
        boi_app_module.BoiAgentChatRequest(
            question="이 SOP를 Mermaid 프로세스 플로우로 보여줘",
            current_url="/docs/boi:public:sop:equipment-abnormal-response",
        ),
        "100001",
    )

    assert len(payloads) == 1
    assert payloads[0]["url"] == "http://router.example/v1/chat/completions"
    assert payloads[0]["json"]["response_format"]["type"] == "json_schema"
    assert payloads[0]["json"]["response_format"]["json_schema"]["name"] == "boi_agent_stream_plan"
    assert plan["route"]["route"] == "deep"
    assert plan["route"]["intent"] == "diagram"
    assert plan["route"]["router_backend"] == "llm"
    assert [item["stage"] for item in plan["status_steps"]] == list(boi_app_module.REQUIRED_AGENT_STATUS_STAGES)
    assert all(item["source"] == "llm_status" for item in plan["status_steps"])


def test_boi_agent_stream_plan_fails_when_llm_returns_no_usable_status(boi_app_module, monkeypatch):
    payloads = []
    unusable_statuses = [{"stage": "unknown", "message": "현재 SOP 페이지를 확인하고 있습니다."}]

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json_module.dumps(
                                    {
                                        "route": "fast",
                                        "confidence": 0.92,
                                        "intent": "page_qa",
                                        "requires_mutation": False,
                                        "requires_deep_reasoning": False,
                                        "statuses": unusable_statuses,
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            )

    # Avoid shadowing pytest's imported json module through the FakeClient.post parameter name.
    json_module = json
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BASE_URL", "http://router.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    with pytest.raises(boi_app_module.BoiAgentStatusUnavailable, match="no usable status"):
        boi_app_module.call_boi_agent_stream_plan_llm(
            boi_app_module.BoiAgentChatRequest(
                question="현재 페이지 기준으로 진행 상태 한 줄을 만들고 짧게 답해줘",
                current_url="/docs/boi:public:sop:equipment-abnormal-response",
            ),
            "100001",
        )

    assert len(payloads) == 1


def test_boi_agent_stream_plan_accepts_single_llm_status_message(boi_app_module):
    steps = boi_app_module.normalize_llm_status_steps(
        {
            "statuses": [
                {
                    "stage": "page_context",
                    "message": "현재 SOP 페이지를 확인하고 있습니다.",
                }
            ]
        }
    )

    assert steps == [
        {
            "stage": "page_context",
            "message": "현재 SOP 페이지를 확인하고 있습니다.",
            "source": "llm_status",
        }
    ]


def test_boi_agent_stream_status_filters_degenerated_llm_messages(boi_app_module):
    steps = boi_app_module.normalize_llm_status_steps(
        {
            "statuses": [
                {"stage": "page_context", "message": "현재 페이지의 문서를-문서 내용을 확인합니다."},
                {
                    "stage": "intent",
                    "message": "질문의 의도를도를 확인하며 thoughtful-thoughtful 반복이 생겼습니다.",
                },
                {"stage": "retrieval", "message": "질문의 의-목을 파악하고 있습니다."},
                {"stage": "compose", "message": "한 문장으로 상태를 정리합니다."},
            ]
        }
    )

    assert steps == [
        {
            "stage": "compose",
            "message": "한 문장으로 상태를 정리합니다.",
            "source": "llm_status",
        }
    ]


def test_boi_agent_llm_route_rejects_invalid_route_or_intent(boi_app_module):
    request = boi_app_module.BoiAgentChatRequest(
        question="이 SOP를 Mermaid 프로세스 플로우로 보여줘",
        current_url="/docs/boi:public:sop:equipment-abnormal-response",
    )

    with pytest.raises(boi_app_module.BoiAgentRouterUnavailable, match="invalid route"):
        boi_app_module.normalize_llm_route_payload(
            {
                "route": "maybe_fast",
                "confidence": 0.99,
                "intent": "diagram",
                "reason": "bad route",
            },
            request,
        )

    with pytest.raises(boi_app_module.BoiAgentRouterUnavailable, match="invalid intent"):
        boi_app_module.normalize_llm_route_payload(
            {
                "route": "deep",
                "confidence": 0.99,
                "intent": "",
                "reason": "missing intent",
            },
            request,
        )


def test_boi_agent_user_facing_llm_contracts_are_not_env_downgradeable(boi_app_module):
    assert boi_app_module.BOI_AGENT_ROUTER_REQUIRED is True
    assert boi_app_module.BOI_AGENT_STATUS_REQUIRED is True
    assert boi_app_module.BOI_AGENT_COMPOSER_REQUIRED is True
    assert boi_app_module.BOI_AGENT_SUGGESTIONS_REQUIRED is True


def test_auth_me_exposes_dev_identity(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/auth/me?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["auth_mode"] == "dev"
    assert body["employee_id"] == "100001"
    assert "platform" in body["teams"]
    assert "boi.editor" in body["roles"]


def test_ontology_search_dictionary_and_boi_search_remain_distinct(boi_app_module):
    client = TestClient(boi_app_module.app)

    create = client.post(
        "/api/dictionary/terms?employee_id=100001",
        json={
            "scope": "private",
            "term": "응답체인",
            "aliases": ["Response Chain"],
            "definition": "설비 응답 흐름 이상을 부르는 현장 표현",
            "example": "응답체인 알람이면 설비 이상 대응 SOP를 확인한다.",
            "maps_to_sop": "boi:public:sop:equipment-abnormal-response",
        },
    )
    ontology = client.get("/api/search/ontology?employee_id=100001&q=Response%20Chain")
    boi_search = client.get("/api/boi?employee_id=100001&q=Response%20Chain")

    assert create.status_code == 200
    assert create.json()["item"]["folder"].endswith("dictionary")
    assert ontology.status_code == 200
    body = ontology.json()
    assert body["ok"] is True
    assert "dictionary" in body["groups"]
    assert any(item["term"] == "응답체인" for item in body["groups"]["dictionary"])
    assert "event_types" in body["groups"]
    assert boi_search.status_code == 200
    assert "items" in boi_search.json()
    assert all((item.get("metadata") or {}).get("type") for item in boi_search.json()["items"])

    equipment = client.get("/api/search/ontology?employee_id=100001&q=설비%20SOP&view=compact")
    assert equipment.status_code == 200
    best_matches = equipment.json()["best_matches"]
    identities = []
    for item in best_matches:
        if item.get("event_type"):
            identities.append(f"event:{item['event_type']}")
        elif item.get("action_key"):
            identities.append(f"action:{item['action_key']}")
        else:
            identities.append(str(item.get("boi_id") or item.get("doc_ref") or item.get("url") or item.get("title")))
    assert len(identities) == len(set(identities))
    assert identities.count("boi:public:sop:equipment-abnormal-response") <= 1


def test_boi_agent_chat_uses_native_backend_by_default(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_langflow(*args, **kwargs):
        raise AssertionError("native default must not call Langflow")

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        return {
            "answer_markdown": "## Native Agent 답변\n\n설비 이상 대응 SOP와 연결 Action을 확인했습니다.",
            "suggested_questions": ["이 SOP의 Event와 Action 관계를 표로 보여줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 대응 SOP와 Action을 찾아줘",
            "mode": "deep",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["used_backend"] == "native_langgraph"
    assert body["deployment_revision"]
    assert body["run_id"].startswith("boi-agent-run-")
    assert isinstance(body["tool_trace"], list)
    assert "설비" in body["answer_markdown"]
    assert isinstance(body["links"], list)


def test_boi_agent_native_uses_llm_composer_when_enabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    compose_calls: list[dict] = []

    def fake_llm(employee_id: str, task: str, payload: dict):
        compose_calls.append({"employee_id": employee_id, "task": task, "payload": payload})
        assert task == "compose"
        return {
            "answer_markdown": "## LLM Composer 답변\n\nSOP 근거와 Action 연결을 업무 관점으로 다시 정리했습니다.",
            "suggested_questions": ["이 SOP의 부족한 Action Spec을 찾아줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 짧게 요약해줘",
            "mode": "fast",
            "intent": "summarize",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert compose_calls
    assert compose_calls[0]["payload"]["structured_draft"]
    assert body["answer_markdown"].startswith("## LLM Composer 답변")
    assert body["context_summary"]["composer_backend"] == "llm"
    assert body["suggested_questions"] == ["이 SOP의 부족한 Action Spec을 찾아줘."]
    assert body["suggested_questions_source"] == "llm_composer"


def test_boi_agent_diagram_uses_native_artifact_without_llm_composer(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unexpected_llm(*args, **kwargs):
        raise AssertionError("diagram artifact path should not call the LLM answer composer")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", unexpected_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘",
            "mode": "deep",
            "intent": "diagram",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "diagram"
    assert body["context_summary"]["composer_backend"] == "native_artifact"
    assert body["artifacts"][0]["type"] == "mermaid"
    assert "```mermaid" not in body["display_markdown"]


def test_boi_agent_required_llm_composer_failure_is_service_error(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def empty_llm(employee_id: str, task: str, payload: dict):
        return None

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", empty_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 짧게 요약해줘",
            "mode": "fast",
            "intent": "summarize",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "native_agent_runtime_unavailable"
    assert "composer" in detail["message"].lower()


def test_boi_agent_required_llm_composer_disabled_is_service_error(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unexpected_llm(*args, **kwargs):
        raise AssertionError("disabled composer must fail before calling LLM")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", unexpected_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 짧게 요약해줘",
            "mode": "fast",
            "intent": "summarize",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "native_agent_runtime_unavailable"
    assert "composer" in detail["message"].lower()


def test_boi_agent_chat_fails_when_langgraph_required_but_unavailable(boi_app_module, monkeypatch):
    from boi_api.app import native_agent

    client = TestClient(boi_app_module.app)

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LANGGRAPH_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "LANGGRAPH_AVAILABLE", False)
    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 대응 SOP와 Action을 찾아줘",
            "mode": "deep",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "native_agent_runtime_unavailable"
    assert detail["langgraph_required"] is True


def test_boi_agent_hybrid_does_not_hide_langgraph_required_failure(boi_app_module, monkeypatch):
    from boi_api.app import native_agent

    client = TestClient(boi_app_module.app)

    def fail_langflow(*args, **kwargs):
        raise AssertionError("LangGraph required failure must not fall back to Langflow")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "hybrid")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LANGGRAPH_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "LANGGRAPH_AVAILABLE", False)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)
    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 대응 SOP와 Action을 찾아줘",
            "mode": "deep",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "native_agent_runtime_unavailable"


def test_boi_agent_hybrid_does_not_fallback_on_native_runtime_error(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_native(*args, **kwargs):
        raise RuntimeError("native boom")

    def fail_langflow(*args, **kwargs):
        raise AssertionError("Native runtime failures must not fall back to Langflow")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "hybrid")
    monkeypatch.setattr(boi_app_module, "call_native_boi_agent", fail_native)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 대응 SOP와 Action을 찾아줘",
            "mode": "fast",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "native_agent_runtime_unavailable"
    assert "native boom" in detail["message"]


def test_boi_agent_unknown_backend_is_service_error(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_native(*args, **kwargs):
        raise AssertionError("Unknown backend must not silently use native")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "mystery")
    monkeypatch.setattr(boi_app_module, "call_native_boi_agent", fail_native)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 대응 SOP와 Action을 찾아줘",
            "mode": "fast",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "native_agent_runtime_unavailable"
    assert "Unknown BOI_AGENT_BACKEND: mystery" in detail["message"]


def test_boi_agent_composer_parser_rejects_partial_answer_markdown(boi_app_module):
    partial = '{"answer_markdown": "## 요약\\n\\n설비 이상 SOP는 Event, Action, Manual Handoff를 순서대로 연결합니다.'

    parsed = boi_app_module.parse_agent_compose_payload(partial)

    assert parsed is None


def test_native_agent_direct_auto_route_requires_llm_classifier(monkeypatch):
    from boi_api.app import native_agent

    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)
    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "best_matches": []},
        boi_get=lambda ref: None,
        event_type_lookup=lambda event_type: None,
        action_spec_lookup=lambda action_key: None,
        workflow_status=lambda workflow_key, trace_id: None,
        trace_context_lookup=lambda trace_id: {"ok": True, "events": [], "actions": []},
        dictionary_resolve=lambda query: {"ok": True, "terms": []},
        memory_recall=lambda query, limit=5: {"ok": True, "items": []},
        agent_inbox=lambda limit=10: {"ok": True, "items": []},
        llm_json=None,
    )
    runtime = native_agent.NativeBoiAgent(
        tools,
        native_agent.NativeAgentConfig(
            llm_enabled=True,
            require_langgraph=False,
            composer_enabled=False,
            composer_required=False,
        ),
    )

    with pytest.raises(native_agent.NativeAgentRuntimeUnavailable, match="route classifier"):
        runtime.run(
            {"question": "SOP 찾아줘", "mode": "auto", "current_url": "/"},
            {},
            {"page_context": {}, "ontology_search_seed": {}, "access_summary": {}},
        )


def test_boi_agent_composer_rejects_degenerate_repetition(boi_app_module):
    answer = "## 요약\n\n" + ("적절-적절-적절 " * 30)

    assert boi_app_module.invalid_agent_composer_answer_reason(answer) == "degenerate_repetition"
    assert boi_app_module.invalid_agent_composer_answer_reason("요약입니다. de la vie, de la vie, de la vie") == "degenerate_repetition"


def test_boi_agent_deep_summarize_relation_question_overrides_to_workflow_explain(boi_app_module):
    from boi_api.app import native_agent

    request = boi_app_module.BoiAgentChatRequest(
        question="이 SOP의 Event, Action, Manual Handoff 관계를 짧게 요약해줘.",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    )
    route = {
        "route": "deep",
        "intent": "summarize",
        "confidence": 0.9,
        "router_backend": "llm",
    }

    fixed = boi_app_module.apply_agent_route_overrides(request, route)
    assert fixed["route"] == "deep"
    assert fixed["intent"] == "workflow_explain"

    native_fixed = native_agent.finalize_native_route(
        {"question": request.question, "current_url": request.current_url},
        {"route": "deep", "intent": "summarize", "router_backend": "llm"},
    )
    assert native_fixed["route"] == "deep"
    assert native_fixed["intent"] == "workflow_explain"


def test_boi_agent_stream_fails_when_langgraph_required_but_unavailable(boi_app_module, monkeypatch):
    from boi_api.app import native_agent

    client = TestClient(boi_app_module.app)
    llm_steps = [
        {"stage": "page_context", "message": "현재 페이지와 권한을 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "intent", "message": "질문의 의도를 판단하고 있습니다.", "source": "llm_status"},
        {"stage": "retrieval", "message": "필요한 근거를 찾고 있습니다.", "source": "llm_status"},
        {"stage": "tool_loop", "message": "관련 도구 호출을 준비하고 있습니다.", "source": "llm_status"},
        {"stage": "compose", "message": "답변을 구성하고 있습니다.", "source": "llm_status"},
        {"stage": "answer_stream", "message": "답변을 화면에 보여주고 있습니다.", "source": "llm_status"},
        {"stage": "waiting", "message": "조금 더 확인하고 있습니다.", "source": "llm_status"},
    ]
    planned_route = {
        "route": "deep",
        "confidence": 0.93,
        "intent": "diagram",
        "reason": "test stream plan",
        "requires_mutation": False,
        "requires_deep_reasoning": True,
        "requires_langflow": False,
        "router_backend": "llm",
    }

    monkeypatch.setattr(boi_app_module, "agent_stream_plan", lambda req, employee_id: {"status_steps": llm_steps, "route": planned_route})
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LANGGRAPH_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "LANGGRAPH_AVAILABLE", False)
    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "이 SOP를 Mermaid로 보여줘", "current_url": "/docs/boi:public:sop:equipment-abnormal-response"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    payloads = [json.loads(item["data"]) for item in events if item["event"] == "error"]
    assert payloads
    assert payloads[-1]["status"] == "native_agent_runtime_unavailable"
    assert payloads[-1]["langgraph_required"] is True


def test_rbac_me_and_doc_access_guard_private_boi(boi_app_module):
    client = TestClient(boi_app_module.app)

    me = client.get("/api/rbac/me?employee_id=100001")
    assert me.status_code == 200
    assert me.json()["rbac_enabled"] if "rbac_enabled" in me.json() else me.json()["ok"]
    assert "boi.viewer" in me.json()["roles"]

    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "Private ACL Test",
            "description": "private ACL test",
            "tags": ["ACL"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:acl-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "acl"}],
        },
        "# Summary\n\nprivate body",
    )

    allowed = client.get("/api/docs/boi:private:100001:acl-test/access?employee_id=100001")
    denied = client.get("/api/docs/boi:private:100001:acl-test/access?employee_id=100002")

    assert allowed.status_code == 200
    assert allowed.json()["access"]["can_read"] is True
    assert denied.status_code == 200
    assert denied.json()["access"]["can_read"] is False
    assert "another employee" in " ".join(denied.json()["access"]["reasons"])


def test_dev_unknown_employee_gets_viewer_only_rbac(boi_app_module):
    client = TestClient(boi_app_module.app)

    me = client.get("/api/rbac/me?employee_id=9999999")

    assert me.status_code == 200
    body = me.json()
    assert body["roles"] == ["boi.viewer"]
    assert body["can_manage"] is False


def test_break_glass_allows_admin_private_read_with_reason_and_audit(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100002:break-glass-readable"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "Break Glass Readable",
            "description": "admin break-glass should allow audited private read",
            "tags": ["ACL", "BreakGlass"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100002",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:private:100002",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "break-glass-readable"}],
        },
        "# Summary\n\nprivate body",
    )

    response = client.post(
        f"/api/docs/{boi_id}/break-glass?employee_id=100001",
        json={"reason": "운영 장애 원인 확인", "ticket_ref": "INC-ACL-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access"]["can_read"] is True
    assert "break-glass admin read" in body["access"]["reasons"]
    assert body["audit"]["action"] == "break_glass_access"
    assert body["audit"]["payload"]["reason"] == "운영 장애 원인 확인"


def test_break_glass_rejects_structurally_invalid_private_policy(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100002:break-glass-invalid-policy"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "Break Glass Invalid Policy",
            "description": "break-glass must not bypass malformed private ACL",
            "tags": ["ACL", "BreakGlass"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:private:100002",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "break-glass-invalid"}],
        },
        "# Summary\n\ninvalid private body",
    )

    response = client.post(
        f"/api/docs/{boi_id}/break-glass?employee_id=100001",
        json={"reason": "운영 장애 원인 확인", "ticket_ref": "INC-ACL-2"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"]["access"]["can_read"] is False
    assert "private acl_policy mismatch" in body["detail"]["access"]["reasons"]


def test_boi_agent_restricted_docs_are_pruned_from_context_and_artifacts(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    restricted_phrase = "restricted-agent-secret-body-token"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/sop",
            "title": "Restricted Agent Leak Test",
            "description": "restricted context should not be used by Agent",
            "tags": ["Restricted", "Agent"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:public:sop:restricted-agent-leak-test",
            "visibility": "public",
            "classification": "restricted",
            "owner": "public",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:public",
            "status": "draft",
            "review": {"reviewer": "pytest", "review_status": "draft"},
            "source_refs": [{"type": "test", "ref": "restricted-agent"}],
            "workflow": {
                "workflow_key": "restricted-agent-leak-test",
                "stages": [
                    {
                        "id": "restricted",
                        "name": "Restricted Stage",
                        "event_types": ["restricted.event.v1"],
                        "automated_actions": ["restricted.action"],
                    }
                ],
            },
        },
        f"# Summary\n\n{restricted_phrase}\n\n[Hidden Link](/public/sop/equipment-abnormal-response.md)",
    )

    compact_search = client.get(
        f"/api/search/ontology?employee_id=100001&q={restricted_phrase}&view=compact"
    )
    assert compact_search.status_code == 200
    compact_body = compact_search.json()
    compact_result_dump = json.dumps(
        {
            "groups": compact_body.get("groups"),
            "best_matches": compact_body.get("best_matches"),
            "citations": compact_body.get("citations"),
            "document_rank_refs": compact_body.get("document_rank_refs"),
        },
        ensure_ascii=False,
    )
    assert restricted_phrase not in compact_result_dump
    assert "restricted-agent-leak-test" not in compact_result_dump

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 제한 문서를 Mermaid로 보여줘.",
            "mode": "deep",
            "current_url": "/docs/boi:public:sop:restricted-agent-leak-test?employee_id=100001",
            "page_context": {"title": "Restricted Agent Leak Test"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    dumped = json.dumps(body, ensure_ascii=False)
    assert body["used_backend"] == "native_langgraph"
    assert body["access_summary"]["can_read"] is True
    assert body["access_summary"]["can_use_in_agent_context"] is False
    assert body["redacted_count"] >= 1
    assert "classification_redaction" in body["guardrails_applied"]
    assert restricted_phrase not in dumped
    assert "restricted.action" not in dumped
    assert "restricted.event.v1" not in dumped
    assert not any("restricted-agent-leak-test" in str(link.get("url") or "") for link in body["links"])
    assert not any("restricted-agent-leak-test" in str(citation.get("url") or "") for citation in body["citations"])


def test_boi_agent_final_response_filters_inaccessible_doc_references(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    forbidden_id = "boi:private:100002:agent-final-leak"
    forbidden_doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "다른 사번 Private Agent Leak",
            "description": "Agent final response must not expose this link",
            "tags": ["ACL", "Agent"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": forbidden_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100002",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:private:100002",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "agent-final-leak"}],
        },
        "# Summary\n\nforbidden private body",
    )
    forbidden_uri = forbidden_doc["uri"]

    class LeakyNativeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        def run(self, *_args, **_kwargs):
            return {
                "ok": True,
                "answer_markdown": (
                    f"보면 안 되는 링크: [private](/docs/{forbidden_id}?employee_id=100001) "
                    f"그리고 [private md]({forbidden_uri})"
                ),
                "links": [
                    {"label": "forbidden", "url": f"/docs/{forbidden_id}?employee_id=100001", "kind": "boi"},
                    {"label": "forbidden-md", "url": forbidden_uri, "kind": "boi"},
                    {"label": "public", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001", "kind": "boi"},
                ],
                "citations": [{"label": "forbidden", "ref": forbidden_id, "url": f"/docs/{forbidden_id}?employee_id=100001"}],
                "artifacts": [
                    {
                        "type": "gap_table",
                        "data": [
                            {"name": "forbidden", "url": f"/docs/{forbidden_id}?employee_id=100001"},
                            {"name": "forbidden-md", "url": forbidden_uri},
                            {"name": "public", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"},
                        ],
                    }
                ],
                "context_summary": {"route": "fast", "intent": "page_qa", "page_context": {"boi_id": forbidden_id}},
                "route": "fast",
                "intent": "page_qa",
                "used_backend": "native_langgraph",
                "guardrails_applied": ["acl_policy"],
                "tool_trace": [
                    {
                        "tool": "boi_get",
                        "status": "ok",
                        "elapsed_ms": 1,
                        "summary": forbidden_id,
                        "result": {"boi_id": forbidden_id, "url": f"/docs/{forbidden_id}?employee_id=100001"},
                    }
                ],
            }

    monkeypatch.setattr(boi_app_module, "NativeBoiAgent", LeakyNativeAgent)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "권한 필터 테스트", "mode": "fast", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    dumped = json.dumps(
        {
            "answer_markdown": body.get("answer_markdown"),
            "links": body.get("links"),
            "citations": body.get("citations"),
            "artifacts": body.get("artifacts"),
            "tool_trace": body.get("tool_trace"),
            "context_summary": body.get("context_summary"),
        },
        ensure_ascii=False,
    )
    assert forbidden_id not in dumped
    assert forbidden_uri not in dumped
    assert "agent_final_reference_acl" in body["guardrails_applied"]
    assert body["redacted_count"] >= 1
    assert any("equipment-abnormal-response" in str(link.get("url") or "") for link in body["links"])


def test_permissions_page_exposes_management_forms_for_admin(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/permissions?employee_id=100001")
    script = (boi_app_module.APP_DIR / "static" / "permissions.js").read_text(encoding="utf-8")
    style = (boi_app_module.APP_DIR / "static" / "style.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "/static/permissions.js?v=" in response.text
    assert 'data-rbac-form="team"' in response.text
    assert 'data-rbac-form="member"' in response.text
    assert 'data-rbac-form="binding"' in response.text
    assert 'data-rbac-form="doc-access"' in response.text
    assert "문서 접근 확인" in response.text
    assert "/api/rbac/teams" in script
    assert "/api/rbac/bindings" in script
    assert "/api/docs/${encodeURIComponent(boiId)}/access" in script
    assert "Agent context 가능" in script
    assert "data-rbac-result" in response.text
    assert ".permission-form-grid" in style
    assert ".rbac-result" in style


def test_permissions_page_hides_role_bindings_and_audit_for_non_manager(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    monkeypatch.setattr(boi_app_module, "roles_for", lambda _employee_id: ["boi.viewer"])
    monkeypatch.setattr(boi_app_module, "rbac_can_manage", lambda _employee_id, **_kwargs: False)

    response = client.get("/permissions?employee_id=100003")

    assert response.status_code == 200
    assert 'data-rbac-admin' not in response.text
    assert 'data-rbac-form="team"' not in response.text
    assert 'data-rbac-form="binding"' not in response.text
    assert "조회만 가능합니다" in response.text
    assert "Role Bindings" not in response.text
    assert ">Audit<" not in response.text
    assert "역할 부여를 저장했습니다" not in response.text


def test_rbac_mutation_apis_reject_non_manager(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    monkeypatch.setattr(boi_app_module, "roles_for", lambda _employee_id: ["boi.viewer"])
    monkeypatch.setattr(boi_app_module, "rbac_can_manage", lambda _employee_id, **_kwargs: False)

    create_team = client.post(
        "/api/rbac/teams?employee_id=100003",
        json={"team_id": "pytest-viewer-denied", "display_name": "Denied"},
    )
    add_member = client.post(
        "/api/rbac/teams/aix-tf/members?employee_id=100003",
        json={"employee_id": "100009", "role": "member", "action": "add"},
    )
    bind_role = client.post(
        "/api/rbac/bindings?employee_id=100003",
        json={"subject_type": "employee", "subject_id": "100003", "roles": ["boi.admin"]},
    )

    assert create_team.status_code == 403
    assert add_member.status_code == 403
    assert bind_role.status_code == 403


def test_event_type_draft_create_and_validate_does_not_apply_catalog(boi_app_module):
    client = TestClient(boi_app_module.app)
    event_type = "pytest.sample.event.requested.v1"

    response = client.post(
        "/api/event-types/drafts?employee_id=100001",
        json={
            "event_type": event_type,
            "name_ko": "Pytest 신규 이벤트",
            "description": "catalog에는 바로 반영되지 않는 draft",
            "user_confirmed": True,
        },
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["event_type"] == event_type
    assert draft["validation"]["valid"] is True
    assert boi_app_module.get_event_type(event_type) is None

    validate = client.post(f"/api/event-types/drafts/{draft['draft_id']}/validate?employee_id=100001")
    assert validate.status_code == 200
    assert validate.json()["draft"]["validation"]["valid"] is True


def test_event_types_page_shows_visible_drafts_without_catalog_apply(boi_app_module):
    client = TestClient(boi_app_module.app)
    event_type = "pytest.visible.draft.requested.v1"

    response = client.post(
        "/api/event-types/drafts?employee_id=100001",
        json={
            "event_type": event_type,
            "name_ko": "화면 표시 초안",
            "description": "Event Types 화면에서 확인할 수 있는 draft-only 초안",
            "workflow_stage": "초안 검토",
            "recommended_actions": ["boi.materialize_event"],
            "user_confirmed": True,
        },
    )
    assert response.status_code == 200
    assert boi_app_module.get_event_type(event_type) is None

    page = client.get("/event-types?employee_id=100001")
    assert page.status_code == 200
    assert "신규 Event Type 초안" in page.text
    assert event_type in page.text
    assert "catalog에는 아직 반영되지 않음" in page.text
    assert "validation ok" in page.text

    other_employee = client.get("/event-types?employee_id=100003")
    assert other_employee.status_code == 200
    assert event_type not in other_employee.text


def test_boi_agent_approve_event_type_draft_requires_editor_role(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def viewer_only(employee_id: str):
        return ["boi.viewer"]

    monkeypatch.setattr(boi_app_module, "roles_for", viewer_only)

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100003",
        json={
            "operation": "event_type_draft",
            "user_confirmed": True,
            "payload": {
                "event_type": "pytest.unauthorized.event.v1",
                "name_ko": "권한 없는 이벤트",
                "description": "권한 없는 사용자가 만들면 안 되는 Event Type draft",
            },
        },
    )

    assert response.status_code == 403
    assert "boi.editor" in response.text
    drafts = client.get("/api/event-types/drafts?employee_id=100003")
    assert drafts.status_code == 200
    assert all(item.get("event_type") != "pytest.unauthorized.event.v1" for item in drafts.json()["items"])


def test_boi_agent_execution_requests_return_specific_confirmation_cards(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        question = req.question
        if "이벤트" in question:
            intent = "event_publish"
        elif "workflow" in question:
            intent = "workflow_start"
        else:
            intent = "action_invoke"
        return {
            "route": "approval_required",
            "confidence": 0.98,
            "intent": intent,
            "reason": "execution confirmation request",
            "requires_mutation": True,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    event_response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "equipment.alarm.raised.v1 이벤트를 발행해줘.",
            "current_url": "/event-types/equipment.alarm.raised.v1?employee_id=100001",
        },
    )
    assert event_response.status_code == 200
    event_body = event_response.json()
    event_card = event_body["artifacts"][0]
    assert event_body["route"] == "approval_required"
    assert event_body["intent"] == "event_publish"
    assert event_card["type"] == "confirmation_required"
    assert event_card["data"]["operation"] == "event_publish"
    assert event_card["data"]["payload"]["event_type"] == "equipment.alarm.raised.v1"
    assert "Event 발행" in event_card["title"]

    workflow_response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 workflow 시작해줘.",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )
    assert workflow_response.status_code == 200
    workflow_body = workflow_response.json()
    workflow_card = workflow_body["artifacts"][0]
    assert workflow_body["route"] == "approval_required"
    assert workflow_body["intent"] == "workflow_start"
    assert workflow_card["data"]["operation"] == "workflow_start"
    assert workflow_card["data"]["payload"]["workflow_key"] == "equipment-anomaly"
    assert "Workflow 시작" in workflow_card["title"]

    action_response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "sop.equipment.request_raw_data action 실행해줘.",
            "current_url": "/actions?employee_id=100001",
        },
    )
    assert action_response.status_code == 200
    action_body = action_response.json()
    action_card = action_body["artifacts"][0]
    assert action_body["route"] == "approval_required"
    assert action_body["intent"] == "action_invoke"
    assert action_card["data"]["operation"] == "action_invoke"
    assert action_card["data"]["payload"]["action_key"] == "sop.equipment.request_raw_data"
    assert "Action 요청 실행" in action_card["title"]


def test_boi_agent_chat_fast_uses_llm_router_and_current_doc_context(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.91,
            "intent": "page_summary",
            "reason": "simple current page question",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    def fail_langflow(*args, **kwargs):
        raise AssertionError("fast route must not call Langflow")

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        return {
            "answer_markdown": "## 현재 페이지 해석\n\n설비 이상 대응 SOP를 현재 문서 맥락으로 요약했습니다.",
            "suggested_questions": ["이 SOP를 Mermaid로 보여줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "현재 페이지를 기준으로 어떻게 이해하면 돼?",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "fast"
    assert body["router_backend"] == "llm"
    assert body["used_backend"] == "native_langgraph"
    assert body["context_summary"]["page_context"]["page_kind"] == "doc"
    assert body["context_summary"]["page_context"]["resolved"] is True
    assert "설비" in body["answer_markdown"]


def test_boi_agent_page_context_uses_resolution_status_not_fallback_key(boi_app_module):
    context = boi_app_module.resolve_agent_page_context(
        "/docs/boi:public:missing:doc?employee_id=100001",
        "100001",
    )

    assert context["page_kind"] == "doc"
    assert context["resolved"] is False
    assert context["context_resolution"] == "ontology_search_only"
    assert "fallback" not in context


def test_boi_agent_required_router_disabled_returns_service_error(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "boi_agent_router_unavailable"
    assert body["required"] is True
    assert "not configured" in body["message"]


def test_boi_agent_native_reuses_api_router_without_internal_llm(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    calls = {"router": 0}

    def fake_router(req, employee_id: str):
        calls["router"] += 1
        return {
            "route": "fast",
            "confidence": 0.91,
            "intent": "search",
            "reason": "test router",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    def fake_internal_llm(employee_id: str, task: str, payload: dict):
        if task == "route":
            raise AssertionError("native graph must not re-run LLM routing when API route is provided")
        assert task == "compose"
        return {
            "answer_markdown": "## Router 재사용 확인\n\nAPI Router 결과를 재사용해 현재 페이지 기준 답변을 구성했습니다.",
            "suggested_questions": ["관련 SOP를 더 찾아줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_internal_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "현재 페이지 기준으로 답해줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert calls["router"] == 1
    assert body["used_backend"] == "native_langgraph"
    assert body["router_backend"] == "llm"
    assert body["router_confidence"] == 0.91
    assert body["intent"] == "search"


def test_boi_agent_mermaid_request_overrides_fast_router_to_deep(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.95,
            "intent": "search",
            "reason": "router guessed search",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    def fail_langflow(*args, **kwargs):
        raise AssertionError("native diagram path must not call Langflow")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "deep"
    assert body["intent"] == "diagram"
    assert body["used_backend"] == "native_langgraph"
    assert body["artifacts"][0]["type"] == "mermaid"
    assert "```mermaid" in body["answer_markdown"]
    assert "```mermaid" not in body["display_markdown"]
    assert "Source Mapping" in body["display_markdown"]
    assert "answer_html" in body
    assert "```mermaid" not in body["answer_html"]
    assert "mermaid-diagram" not in body["answer_html"]
    assert '<table class="markdown-table">' in body["answer_html"]


def test_boi_agent_deep_request_uses_ontology_match_when_not_on_doc_page(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "deep",
            "confidence": 0.95,
            "intent": "diagram",
            "reason": "diagram request",
            "requires_mutation": False,
            "requires_deep_reasoning": True,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 SOP를 Mermaid 프로세스 플로우로 보여줘",
            "current_url": "/?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "deep"
    assert body["intent"] == "diagram"
    assert body["used_backend"] == "native_langgraph"
    assert body["coverage_report"]["coverage_score"] == 1.0
    assert "current_doc" in body["coverage_report"]["covered"]
    assert any(item["tool"] == "boi_get" and "equipment-abnormal-response" in str(item["args"]) for item in body["tool_trace"])
    assert "설비 이상 감지" in body["answer_markdown"]
    assert "workflow metadata 확인 필요" not in body["answer_markdown"]
    assert any(item.get("type") == "mermaid" for item in body["artifacts"])
    assert body["suggested_questions"] == []
    assert body["suggested_questions_source"] == "suggestions_endpoint_required"


def test_boi_agent_workflow_explain_renders_relationship_table(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "deep",
            "confidence": 0.94,
            "intent": "workflow_explain",
            "reason": "workflow relationship question",
            "requires_mutation": False,
            "requires_deep_reasoning": True,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP의 Event, Action, Manual Handoff 관계를 표로 요약해줘",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "workflow_explain"
    assert "| Stage | Event | Action | Manual Handoff | Next |" in body["answer_markdown"]
    assert '<table class="markdown-table">' in body["answer_html"]
    assert "manual.equipment.confirm_alarm_context" in body["answer_html"]
    assert any(item.get("type") == "workflow_summary" for item in body["artifacts"])


def test_boi_agent_router_parser_accepts_reasoning_content_json(boi_app_module):
    payload = boi_app_module.parse_router_payload(
        'thinking about policy {"allowed_routes":["fast"]} final {"route":"fast","confidence":0.92,"intent":"lookup"}'
    )

    assert payload is not None
    assert payload["route"] == "fast"
    assert payload["confidence"] == 0.92


def test_boi_agent_composer_parser_accepts_json_contract_not_plain_markdown(boi_app_module):
    alias_payload = boi_app_module.parse_agent_compose_payload('{"answer":"## 답변\\n근거를 기준으로 정리했습니다."}')
    plain_payload = boi_app_module.parse_agent_compose_payload("## 답변\n\n근거를 기준으로 정리했습니다.")
    fenced_json_payload = boi_app_module.parse_agent_compose_payload(
        '```json\n{"answer_markdown":"## 답변\\n\\n| 항목 | 내용 |\\n| --- | --- |\\n| 근거 | SOP |"}\n```'
    )
    id_payload = boi_app_module.parse_agent_compose_payload("chatcmpl-ehtj17bt32uiwqj0hp4cig")
    openai_candidates = boi_app_module.iter_langflow_text_candidates(
        {
            "id": "chatcmpl-ehtj17bt32uiwqj0hp4cig",
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"answer_markdown":"## 답변\\n\\n업무 관점으로 정리했습니다."}\n```'
                    }
                }
            ],
        }
    )
    openai_payload = boi_app_module.parse_agent_compose_payload(openai_candidates[0])

    assert alias_payload["answer_markdown"].startswith("## 답변")
    assert plain_payload is None
    assert fenced_json_payload["answer_markdown"].startswith("## 답변")
    assert openai_candidates[0].startswith("```json")
    assert openai_payload["answer_markdown"].startswith("## 답변")
    assert id_payload is None
    assert boi_app_module.invalid_agent_composer_answer_reason("* User wants a Mermaid process flow") == "prompt_echo"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 최종 답변\n\n업무 흐름을 정리했습니다.") == ""


def test_boi_agent_display_markdown_removes_all_mermaid_when_artifacts_exist(boi_app_module):
    markdown = (
        "## 답변\n\n"
        "```mermaid\nflowchart TD\n  A --> B\n```\n\n"
        "설명입니다.\n\n"
        "```mermaid\nflowchart TD\n  C --> D\n```"
    )
    display = boi_app_module.markdown_without_duplicate_mermaid_artifacts(
        markdown,
        [{"type": "mermaid", "source": "flowchart TD\n  A --> B"}],
    )

    assert "```mermaid" not in display
    assert "설명입니다." in display


def test_boi_agent_llm_compose_payload_strips_diagram_mermaid_source():
    from boi_api.app.native_agent import llm_compose_payload

    payload = llm_compose_payload(
        {
            "intent": "diagram",
            "question": "SOP를 그려줘",
            "route_name": "deep",
            "answer_markdown": "## 답변\n\n```mermaid\nflowchart TD\n  A --> B\n```\n\n## Source Mapping\n\n| stage | events |\n|---|---|",
            "search": {},
            "page_context": {},
            "tool_results": {},
            "coverage_report": {},
            "tool_trace": [],
        }
    )

    assert "```mermaid" not in payload["structured_draft"]
    assert "structured artifact" in payload["artifact_policy"]["mermaid"]


def test_boi_agent_composer_llm_requests_json_schema(boi_app_module, monkeypatch):
    payloads: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"answer_markdown":"## 답변\\n\\n정상 답변입니다.","suggested_questions":["다음 질문"]}'}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_BASE_URL", "http://composer.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    result = boi_app_module.call_boi_agent_composer_llm({"structured_draft": "## 초안"}, "100001")

    assert result["answer_markdown"].startswith("## 답변")
    assert result["suggested_questions"] == ["다음 질문"]
    assert payloads[0]["json"]["response_format"]["type"] == "json_schema"
    assert payloads[0]["json"]["response_format"]["json_schema"]["name"] == "boi_agent_final_answer"


def test_boi_agent_chat_router_failure_returns_service_error_when_required(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def broken_router(req, employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("router timeout")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", broken_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "boi_agent_router_unavailable"
    assert body["required"] is True
    assert "router timeout" in body["message"]


def test_boi_agent_chat_router_failure_is_not_rule_fallback_even_when_required_flag_disabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def broken_router(req, employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("router timeout")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", broken_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "boi_agent_router_unavailable"
    assert body["required"] is False
    assert "router timeout" in body["message"]


def test_boi_agent_obvious_search_uses_llm_router_first(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    calls = {"router": 0}

    def fake_router(req, employee_id: str):
        calls["router"] += 1
        return {
            "route": "fast",
            "confidence": 0.91,
            "intent": "search",
            "reason": "document search request",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        return {
            "answer_markdown": "## 검색 결과\n\n설비 SOP 관련 Event와 Action을 BoI Wiki 근거로 정리했습니다.",
            "suggested_questions": ["이 결과를 workflow summary로 보여줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "설비 SOP 관련 Event와 Action을 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "fast"
    assert body["intent"] == "search"
    assert body["router_backend"] == "llm"
    assert body["used_backend"] == "native_langgraph"
    assert calls["router"] == 1


def test_boi_agent_router_network_failure_surfaces_backoff_when_required(boi_app_module, monkeypatch):
    calls = {"post": 0}

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            calls["post"] += 1
            raise boi_app_module.httpx.ConnectTimeout("router unavailable")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_BASE_URL", "http://router.example:1236/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS", 60)
    monkeypatch.setattr(boi_app_module, "_BOI_AGENT_ROUTER_BACKOFF_UNTIL", 0.0)
    monkeypatch.setattr(boi_app_module, "_BOI_AGENT_ROUTER_BACKOFF_REASON", "")
    monkeypatch.setattr(boi_app_module.httpx, "Client", FailingClient)

    request = boi_app_module.BoiAgentChatRequest(question="현재 페이지 기준으로 답해줘", current_url="/")
    with pytest.raises(boi_app_module.BoiAgentRouterUnavailable, match="router unavailable"):
        boi_app_module.route_boi_agent_request(request, "100001")
    with pytest.raises(boi_app_module.BoiAgentRouterUnavailable, match="backoff active"):
        boi_app_module.route_boi_agent_request(request, "100001")
    assert calls["post"] == 1


def test_boi_agent_chat_safety_overrides_llm_fast_route_for_manual_completion(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unsafe_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.99,
            "intent": "summary",
            "reason": "wrongly classified",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", unsafe_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "이 manual handoff 조치 완료 처리해줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "manual_handoff"
    assert body["used_backend"] == "native_langgraph"
    assert "확인 카드" in body["answer_markdown"]
    assert body["artifacts"][0]["type"] == "confirmation_required"
    assert body["artifacts"][0]["data"]["route"] == "manual_handoff"


def test_boi_agent_event_type_draft_card_uses_ontology_context(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "approval_required",
            "confidence": 0.95,
            "intent": "event_type_draft",
            "reason": "event type draft request",
            "requires_mutation": True,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "장비 점검 완료 이벤트 타입 maintenance.inspection.completed.v1 초안을 만들어줘. 작업자는 7자리 사번이고 SOP는 설비 이상 감지 SOP와 연결해줘.",
            "current_url": "/event-types?employee_id=100001",
            "page_context": {"title": "Event Types"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "approval_required"
    assert body["intent"] == "event_type_draft"
    artifact = body["artifacts"][0]
    assert artifact["type"] == "confirmation_required"
    assert body["execution_cards"][0]["operation"] == "event_type_draft"
    assert body["execution_cards"][0]["requires_confirmation"] is True
    payload = artifact["data"]["payload"]
    assert payload["event_type"] == "maintenance.inspection.completed.v1"
    assert payload["name_ko"] == "장비 점검 완료"
    assert payload["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert payload["workflow_stage"]
    assert payload["topic"] == "maintenance.inspection"
    assert payload["payload_schema"]["properties"]["owner_employee_id"]["pattern"] == "^\\d{7}$"
    assert "equipment_id" in payload["payload_schema"]["properties"]

    approve = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={"operation": artifact["data"]["operation"], "payload": payload, "user_confirmed": True},
    )
    assert approve.status_code == 200
    draft = approve.json()["draft"]
    assert draft["status"] == "draft"
    assert draft["validation"]["valid"] is True
    assert draft["catalog_patch_proposal"]["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert boi_app_module.get_event_type(payload["event_type"]) is None


def test_boi_agent_manual_handoff_relationship_question_is_not_mutation(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def wrong_fast_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.99,
            "intent": "search",
            "reason": "router guessed search",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", wrong_fast_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP의 Event, Action, Manual Handoff 관계를 요약해줘.",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 감지·원인 분석·이상 조치 SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "deep"
    assert body["intent"] == "workflow_explain"
    assert body["used_backend"] == "native_langgraph"
    assert body["artifacts"][0]["type"] == "workflow_summary"
    assert "confirmation_required" not in {artifact.get("type") for artifact in body["artifacts"]}


def test_boi_agent_chat_safety_overrides_router_requires_mutation_flag(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unsafe_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.99,
            "intent": "edit",
            "reason": "router detected mutation but wrong route",
            "requires_mutation": True,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", unsafe_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "이 내용을 반영해줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "approval_required"
    assert body["used_backend"] == "native_langgraph"
    assert body["artifacts"][0]["type"] == "confirmation_required"


def test_boi_agent_router_parses_openai_compatible_json_response(boi_app_module, monkeypatch):
    payloads: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "chatcmpl-router-test",
                "object": "chat.completion",
                "model": "google/gemma-4-26b-a4b-qat",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "route": "deep",
                                    "confidence": 0.92,
                                    "intent": "workflow_reasoning",
                                    "reason": "multi-hop 판단",
                                    "requires_mutation": False,
                                    "requires_deep_reasoning": True,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_BASE_URL", "http://router.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_TIMEOUT_SECONDS", 8)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MAX_TOKENS", 768)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    route = boi_app_module.call_boi_agent_router_llm(
        boi_app_module.BoiAgentChatRequest(question="이 workflow를 판단해줘", current_url="/"),
        "100001",
    )

    assert route["route"] == "deep"
    assert route["router_backend"] == "llm"
    assert route["requires_deep_reasoning"] is True
    assert route["requires_langflow"] is False
    assert payloads[0]["url"] == "http://router.example/v1/chat/completions"
    assert payloads[0]["json"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert payloads[0]["json"]["response_format"] == {"type": "text"}
    assert payloads[0]["json"]["max_tokens"] == 768


def test_boi_agent_parser_prefers_nested_langflow_answer_payload(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(question="SOP 찾아줘", current_url="/")
    answer_payload = {
        "answer_markdown": "- **링크**: [설비 SOP](/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001)",
        "links": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
        "citations": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
        "suggested_questions": ["이 SOP의 Action을 보여줘."],
        "context_summary": {"source": "langflow"},
    }
    run_result = {
        "outputs": [
            {
                "outputs": [
                    {
                        "results": {
                            "message": {
                                "data": {"text": json.dumps(answer_payload, ensure_ascii=False)},
                                "text": json.dumps(answer_payload, ensure_ascii=False),
                            }
                        },
                        "artifacts": {"message": json.dumps({"answer_markdown": "BoI Agent returned an empty answer."})},
                    }
                ]
            }
        ]
    }

    body = boi_app_module.normalize_langflow_agent_response(run_result, req, "100001")

    assert body["answer_markdown"].startswith("- **링크**")
    assert body["links"][0]["label"] == "설비 SOP"
    assert body["suggested_questions"] == ["이 SOP의 Action을 보여줘."]
    assert body["suggested_questions_source"] == "llm_composer"
    assert body["context_summary"]["langflow_flow"] == "boi-agent"


def test_boi_agent_langflow_response_does_not_template_missing_suggestions(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(question="SOP 찾아줘", current_url="/")
    run_result = {
        "outputs": [
            {
                "outputs": [
                    {
                        "results": {
                            "message": {
                                "text": json.dumps({"answer_markdown": "## 답변\n\n근거를 기준으로 답변합니다."}, ensure_ascii=False)
                            }
                        }
                    }
                ]
            }
        ]
    }

    body = boi_app_module.normalize_langflow_agent_response(run_result, req, "100001")

    assert body["suggested_questions"] == []
    assert body["suggested_questions_source"] == "suggestions_endpoint_required"
    assert "현재 페이지" not in " ".join(body["suggested_questions"])


def test_boi_agent_chat_returns_503_when_langflow_agent_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_call(req, employee_id: str, route=None, started_at=None):
        raise boi_app_module.LangflowBoiAgentUnavailable("BoI Agent Flow not found")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "langflow")
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fake_call)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "mode": "deep", "current_url": "/"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "langflow_boi_agent_unavailable"
    assert "BoI Agent Flow not found" in body["message"]
    assert "BoI Wiki 기준" not in response.text


def test_boi_agent_langflow_diagram_requires_real_mermaid_artifact(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_call(req, employee_id: str, route=None, started_at=None):
        run_result = {"outputs": [{"outputs": [{"results": {"message": {"text": json.dumps({"answer_markdown": "도식 설명만 있습니다.", "artifacts": []}, ensure_ascii=False)}}}]}]}
        return boi_app_module.normalize_langflow_agent_response(run_result, req, employee_id, route=route, started_at=started_at)

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "langflow")
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fake_call)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "이 SOP를 Mermaid로 그려줘", "mode": "deep", "current_url": "/docs/boi:public:sop:equipment-abnormal-response"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "langflow_boi_agent_unavailable"
    assert "required Mermaid artifact" in body["message"]
    assert "현재 페이지 관계도" not in response.text


def parse_sse_events(raw: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for block in raw.split("\n\n"):
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        if data_lines:
            events.append({"event": event_name, "data": "\n".join(data_lines)})
    return events


def test_boi_agent_chat_stream_emits_status_delta_and_final(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    received_routes: list[dict] = []
    llm_steps = [
        {"stage": "page_context", "message": "현재 페이지와 접근 권한을 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "intent", "message": "질문이 간단 설명인지 판단하고 있습니다.", "source": "llm_status"},
        {"stage": "retrieval", "message": "관련 BoI 근거를 찾아보고 있습니다.", "source": "llm_status"},
        {"stage": "tool_loop", "message": "필요한 근거를 더 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "compose", "message": "표와 링크를 정리하고 있습니다.", "source": "llm_status"},
        {"stage": "answer_stream", "message": "답변을 화면에 보여주고 있습니다.", "source": "llm_status"},
        {"stage": "waiting", "message": "작업이 길어져도 계속 처리하고 있습니다.", "source": "llm_status"},
    ]
    planned_route = {
        "route": "fast",
        "confidence": 0.91,
        "intent": "page_qa",
        "reason": "test stream plan",
        "requires_mutation": False,
        "requires_deep_reasoning": False,
        "requires_langflow": False,
        "router_backend": "llm",
    }

    def fake_agent_response(req, employee_id: str, progress_callback=None, route=None):
        received_routes.append(route or {})
        if progress_callback:
            progress_callback({"stage": "tool_start", "tool": "ontology_search", "message": "관련 BoI 지식을 확인하고 있습니다."})
            progress_callback(
                {
                    "stage": "tool_done",
                    "tool": "ontology_search",
                    "status": "ok",
                    "elapsed_ms": 7,
                    "summary": "best_matches=2",
                    "message": "관련 BoI 지식 확인을 마쳤습니다 (best_matches=2).",
                }
            )
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": (
                "현재 페이지를 확인했습니다.\n\n"
                "| 항목 | 값 |\n| --- | --- |\n| 상태 | 완료 |\n\n"
                "이 응답은 스트리밍 UI가 부분 답변을 여러 조각으로 렌더링하는지 검증하기 위해 "
                "일부러 길게 작성한 본문입니다. BoI Agent는 오래 걸리는 작업 중에는 현재 진행 상태를 "
                "한 줄로 알려주고, 답변이 준비되면 여러 chunk로 나누어 사용자에게 보여줘야 합니다."
            ),
            "display_markdown": (
                "현재 페이지를 확인했습니다.\n\n"
                "| 항목 | 값 |\n| --- | --- |\n| 상태 | 완료 |\n\n"
                "이 응답은 스트리밍 UI가 부분 답변을 여러 조각으로 렌더링하는지 검증하기 위해 "
                "일부러 길게 작성한 본문입니다. BoI Agent는 오래 걸리는 작업 중에는 현재 진행 상태를 "
                "한 줄로 알려주고, 답변이 준비되면 여러 chunk로 나누어 사용자에게 보여줘야 합니다."
            ),
            "links": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
            "citations": [],
            "suggested_questions": ["깊게 분석해줘."],
            "artifacts": [],
            "context_summary": {"intent": "page_qa"},
            "route": "fast",
            "intent": "page_qa",
            "router_backend": "llm",
            "used_backend": "native_langgraph",
            "latency_ms": 12,
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent_response)
    monkeypatch.setattr(boi_app_module, "agent_stream_plan", lambda req, employee_id: {"status_steps": llm_steps, "route": planned_route})

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    event_names = [item["event"] for item in events]
    assert "status" in event_names
    assert "answer_delta" in event_names
    assert event_names[-1] == "final"
    status_payloads = [json.loads(item["data"]) for item in events if item["event"] == "status"]
    assert all(item.get("stage") for item in status_payloads)
    assert all(item.get("source") == "llm_status" for item in status_payloads)
    assert any(item["message"] == llm_steps[0]["message"] for item in status_payloads)
    assert not any(item.get("stage") == "tool_start" for item in status_payloads)
    assert any(item.get("stage") == "answer_stream" for item in status_payloads)
    answer_deltas = [json.loads(item["data"])["delta"] for item in events if item["event"] == "answer_delta"]
    assert len(answer_deltas) >= 2
    assert "현재 페이지를 확인했습니다" in "".join(answer_deltas)
    final = json.loads(events[-1]["data"])
    assert final["answer_html"]
    assert final["links"][0]["label"] == "설비 SOP"
    assert final["used_backend"] == "native_langgraph"
    assert received_routes == [planned_route]


def test_boi_agent_chat_stream_emits_heartbeat_while_agent_is_running(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STREAM_HEARTBEAT_SECONDS", 0.05)
    llm_steps = [
        {"stage": "page_context", "message": "요청한 화면의 맥락을 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "intent", "message": "사용자가 원하는 답변 유형을 판단하고 있습니다.", "source": "llm_status"},
        {"stage": "retrieval", "message": "필요한 BoI 근거를 찾고 있습니다.", "source": "llm_status"},
        {"stage": "tool_loop", "message": "관련 근거를 추가로 확인하고 있습니다.", "source": "llm_status"},
        {"stage": "compose", "message": "답변을 정리하고 있습니다.", "source": "llm_status"},
        {"stage": "answer_stream", "message": "답변을 이어서 보여주고 있습니다.", "source": "llm_status"},
        {"stage": "waiting", "message": "조금 더 확인하고 있습니다.", "source": "llm_status"},
    ]

    planned_route = {
        "route": "fast",
        "confidence": 0.9,
        "intent": "page_qa",
        "reason": "test stream plan",
        "requires_mutation": False,
        "requires_deep_reasoning": False,
        "requires_langflow": False,
        "router_backend": "llm",
    }

    def fake_slow_agent_response(req, employee_id: str, progress_callback=None, route=None):
        time.sleep(0.65)
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "느린 작업을 마쳤습니다.",
            "display_markdown": "느린 작업을 마쳤습니다.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "artifacts": [],
            "context_summary": {"intent": "page_qa"},
            "route": "fast",
            "intent": "page_qa",
            "router_backend": "llm",
            "used_backend": "native_langgraph",
            "latency_ms": 180,
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_slow_agent_response)
    monkeypatch.setattr(boi_app_module, "agent_stream_plan", lambda req, employee_id: {"status_steps": llm_steps, "route": planned_route})

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "천천히 확인해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    status_payloads = [json.loads(item["data"]) for item in events if item["event"] == "status"]
    assert len(status_payloads) >= 2
    assert status_payloads[0]["stage"] == "page_context"
    assert all(item.get("source") == "llm_status" for item in status_payloads)
    assert any(item["stage"] != "page_context" for item in status_payloads[1:])
    assert events[-1]["event"] == "final"


def test_boi_agent_chat_stream_fails_when_status_llm_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_status(_req, _employee_id: str):
        raise boi_app_module.BoiAgentStatusUnavailable("status model unavailable")

    def unexpected_agent(*args, **kwargs):
        raise AssertionError("agent should not run without LLM status text")

    monkeypatch.setattr(boi_app_module, "agent_stream_plan", fail_status)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", unexpected_agent)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    assert events[-1]["event"] == "error"
    payload = json.loads(events[-1]["data"])
    assert payload["status"] == "status_generation_failed"
    assert "status model unavailable" in payload["message"]


def test_boi_agent_chat_stream_fails_when_status_required_is_disabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unexpected_agent(*args, **kwargs):
        raise AssertionError("agent should not run when LLM status generation is disabled")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", unexpected_agent)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    assert events[-1]["event"] == "error"
    payload = json.loads(events[-1]["data"])
    assert payload["status"] == "status_generation_failed"
    assert payload["required"] is False
    assert "disabled" in payload["message"]


def test_boi_agent_chat_endpoint_offloads_agent_work(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    worker_threads: list[str] = []

    def fake_agent_response(req, employee_id: str, progress_callback=None):
        worker_threads.append(threading.current_thread().name)
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "일반 API 응답입니다.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "artifacts": [],
            "context_summary": {"intent": "page_qa"},
            "route": "fast",
            "intent": "page_qa",
            "router_backend": "llm",
            "used_backend": "native_langgraph",
            "latency_ms": 10,
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    )

    assert response.status_code == 200
    assert response.json()["answer_html"]
    assert worker_threads
    assert worker_threads[0] != threading.current_thread().name


def test_boi_agent_chat_endpoint_returns_service_timeout_instead_of_hanging(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def slow_agent_response(req, employee_id: str, progress_callback=None):
        time.sleep(0.08)
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "늦게 도착한 답변입니다.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "artifacts": [],
            "context_summary": {"intent": "page_qa"},
            "route": "fast",
            "intent": "page_qa",
            "router_backend": "llm",
            "used_backend": "native_langgraph",
            "latency_ms": 80,
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_CHAT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", slow_agent_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    )

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["status"] == "boi_agent_timeout"
    assert body["timeout_seconds"] == 0.01
    assert body["used_backend"] == boi_app_module.BOI_AGENT_BACKEND


def test_agent_memory_blocks_sensitive_values_and_saves_private_memory(boi_app_module):
    client = TestClient(boi_app_module.app)

    blocked = client.post(
        "/api/agents/boi-wiki/memory?employee_id=100001",
        json={"title": "토큰", "body": "api key token을 기억해줘"},
    )
    saved = client.post(
        "/api/agents/boi-wiki/memory?employee_id=100001",
        json={"title": "답변 선호", "body": "SOP 답변은 stage 기준으로 짧게 정리한다.", "memory_kind": "answer_style"},
    )
    listed = client.get("/api/agents/boi-wiki/memory?employee_id=100001&q=SOP")

    assert blocked.status_code == 400
    assert saved.status_code == 200
    assert saved.json()["item"]["folder"].endswith("agent-memory")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1


def test_agent_inbox_and_manual_handoff_completion_are_append_only(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-manual-required-test",
            "action_key": "manual.equipment.review_root_cause",
            "status": "manual_required",
            "summary": "원인 후보 검토 필요",
            "trace_id": "trace-agent-inbox-test",
        },
    )

    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001")
    complete = client.post(
        "/api/agents/boi-wiki/manual-handoffs/complete?employee_id=100001",
        json={
            "task_id": "task:act-manual-required-test",
            "outcome": "completed",
            "note": "원인 후보 검토 완료",
            "user_confirmed": True,
        },
    )
    inbox_after = client.get("/api/agents/boi-wiki/inbox?employee_id=100001")

    assert inbox.status_code == 200
    assert any(item["request_id"] == "act-manual-required-test" for item in inbox.json()["items"])
    target = next(item for item in inbox.json()["items"] if item["request_id"] == "act-manual-required-test")
    assert target["display"]["status_label"] == "조치 필요"
    assert "조치" in target["display"]["next_action"]
    assert target["display"]["primary_url"]
    assert complete.status_code == 200
    assert complete.json()["item"]["completion_for_request_id"] == "act-manual-required-test"
    assert not any(item["request_id"] == "act-manual-required-test" for item in inbox_after.json()["items"])


def test_agent_inbox_snooze_and_dismiss_require_confirmation_and_role(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    unconfirmed = client.post(
        "/api/agents/boi-wiki/inbox/task:act-confirmation-test/snooze?employee_id=100001",
        json={"note": "잠시 뒤 확인"},
    )
    confirmed = client.post(
        "/api/agents/boi-wiki/inbox/task:act-confirmation-test/snooze?employee_id=100001",
        json={"note": "잠시 뒤 확인", "user_confirmed": True},
    )

    monkeypatch.setattr(boi_app_module, "roles_for", lambda _employee_id: ["boi.viewer"])
    denied = client.post(
        "/api/agents/boi-wiki/inbox/task:act-confirmation-test/dismiss?employee_id=100003",
        json={"note": "대상 아님", "user_confirmed": True},
    )

    assert unconfirmed.status_code == 400
    assert "user_confirmed=true" in str(unconfirmed.json()["detail"])
    assert confirmed.status_code == 200
    assert confirmed.json()["item"]["completion_for_request_id"] == "act-confirmation-test"
    assert confirmed.json()["item"]["status"] == "snoozed"
    assert confirmed.json()["item"]["note"] == "잠시 뒤 확인"
    assert denied.status_code == 403
    assert "boi.workflow_runner" in denied.text


def test_boi_agent_approve_rejects_unsupported_operation(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={"operation": "not_a_supported_operation", "payload": {"title": "Noop"}, "user_confirmed": True},
    )

    assert response.status_code == 400
    assert "unsupported Agent approval operation" in response.json()["detail"]


def test_agent_mutation_apis_reject_employee_spoofing(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda _employee_id: ["boi.viewer", "boi.workflow_runner", "boi.action_invoker"],
    )

    event_response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "event_publish",
            "user_confirmed": True,
            "payload": {
                "event_type": "equipment.alarm.raised.v1",
                "actor_employee_id": "100002",
                "payload": {"title": "spoof attempt"},
            },
        },
    )
    action_response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "action_invoke",
            "user_confirmed": True,
            "payload": {
                "action_key": "sop.equipment.request_raw_data",
                "employee_id": "100002",
                "payload": {"title": "spoof attempt"},
            },
        },
    )
    direct_action_response = client.post(
        "/api/actions/invoke?employee_id=100001",
        json={
            "action_key": "sop.equipment.request_raw_data",
            "employee_id": "100002",
            "payload": {"title": "spoof attempt"},
        },
    )

    assert event_response.status_code == 403
    assert "actor_employee_id must match" in event_response.text
    assert action_response.status_code == 403
    assert "action employee_id must match" in action_response.text
    assert direct_action_response.status_code == 403
    assert "action employee_id must match" in direct_action_response.text


def test_admin_employee_override_requires_reason_and_audit(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    async def fake_publish_event_to_kafka(_event):
        return None

    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda _employee_id: ["boi.viewer", "boi.workflow_runner", "boi.action_invoker", "boi.admin"],
    )
    monkeypatch.setattr(boi_app_module, "publish_event_to_kafka", fake_publish_event_to_kafka)

    event_without_reason = client.post(
        "/api/events/publish?employee_id=100001",
        json={
            "event_type": "equipment.alarm.raised.v1",
            "actor_employee_id": "100002",
            "payload": {"title": "admin override without reason"},
        },
    )
    agent_event_without_reason = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "event_publish",
            "user_confirmed": True,
            "payload": {
                "event_type": "equipment.alarm.raised.v1",
                "actor_employee_id": "100002",
                "payload": {"title": "agent admin override without reason"},
            },
        },
    )
    action_without_reason = client.post(
        "/api/actions/invoke?employee_id=100001",
        json={
            "action_key": "sop.equipment.request_raw_data",
            "employee_id": "100002",
            "payload": {"title": "admin override without reason"},
        },
    )
    event_with_reason = client.post(
        "/api/events/publish?employee_id=100001",
        json={
            "event_type": "equipment.alarm.raised.v1",
            "actor_employee_id": "100002",
            "admin_override_reason": "pytest delegated operation audit",
            "payload": {"title": "admin override with reason"},
        },
    )

    assert event_without_reason.status_code == 400
    assert "admin_override_reason" in event_without_reason.text
    assert agent_event_without_reason.status_code == 400
    assert "admin_override_reason" in agent_event_without_reason.text
    assert action_without_reason.status_code == 400
    assert "admin_override_reason" in action_without_reason.text
    assert event_with_reason.status_code == 200
    assert event_with_reason.json()["event"]["actor"]["employee_id"] == "100002"
    audits = boi_app_module.rbac_audit_rows(limit=20)
    assert any(
        row.get("action") == "admin_event_publish_employee_override"
        and (row.get("payload") or {}).get("requested_employee_id") == "100002"
        for row in audits
    )


def test_boi_agent_approve_promotion_submit_uses_validation_path(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "promotion_submit",
            "user_confirmed": True,
            "payload": {
                "target_visibility": "public",
                "title": "Agent Promotion Secret Guard Test",
                "description": "Agent approval must reuse promotion validation.",
                "body": "# Summary\n\nsecret=sk-agent-approval-validation-test",
                "source_refs": [{"type": "local-private", "ref": "agent-promotion-secret-test"}],
            },
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "validation_failed"
    assert "potential secret token detected" in detail["validation"]["errors"]


def test_pet_agent_mount_is_available_on_home(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001")
    script = (boi_app_module.APP_DIR / "static" / "pet_agent.js").read_text(encoding="utf-8")
    style = (boi_app_module.APP_DIR / "static" / "style.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'id="boi-agent-root"' in response.text
    assert "/static/mermaid_render.js?v=" in response.text
    assert "/static/pet_agent.js?v=" in response.text
    assert "sessionStorage" in script
    assert "boiAgent.v5" in script
    assert "pinToBottom" in script
    assert "captureScrollState" in script
    assert "isNearBottom" in script
    assert "Agent" in script
    assert "Inbox" in script
    assert "boi-agent-meta" in script
    assert "renderArtifacts" in script
    assert "mermaid-diagram" in script
    assert "BoiAgentMarkdownDebug" in script
    assert "renderMarkdownTable" in script
    assert "renderRunSummary" in script
    assert "html: body.answer_html || \"\"" in script
    assert "body.display_markdown || body.answer_markdown" in script
    assert "rawText: body.answer_markdown" in script
    assert "looksLikeRawMarkdownHtml" in script
    assert "shouldUseServerHtml" in script
    assert "const serverHtml = shouldUseServerHtml(message, artifactMermaid)" in script
    assert "serverHtml || renderMarkdownLite(message.text || \"\", { skipMermaidSources: artifactMermaid })" in script
    assert "/api/agents/boi-wiki/chat/stream" in script
    assert "answer_delta" in script
    assert "statusLines" in script
    assert "readAgentStream" in script
    assert "refreshSuggestions" in script
    assert "body.suggested_questions" not in script
    assert "activeRequest.abort()" in script
    assert "생성을 중지했습니다." in script
    assert "formatAgentStreamError" in script
    assert "BoI Agent 장애" in script
    assert "status_generation_failed" in script
    assert "boi-agent-new" in script
    assert "boi-agent-expand" in script
    assert "data-open-answer" in script
    assert "data-open-artifact" in script
    assert 'data-mermaid-state="pending"' in script
    assert 'data-mermaid-state="pending"] > .mermaid' in style
    assert "width:min(900px" in style
    assert ".boi-agent-table-wrap, .boi-agent-answer .table-wrap { max-width:100%; margin:9px 0; overflow:auto;" in style
    assert "boi-agent-expand" in script
    assert "currentStatus" in script
    assert "state.currentStatus" in script
    assert "진행 상태" in script
    assert "state.sending ? state.currentStatus" in script
    assert "let pageUnloading = false" in script
    assert 'window.addEventListener("pagehide"' in script
    assert "if (pageUnloading) return;" in script
    assert "state.messages.splice(pendingIndex, 1)" in script
    assert "text: streamedText," in script
    assert '${answerHtml ? `<div class="boi-agent-answer"' in script
    assert "state.messages.slice(-20)" in script
    assert "content.scrollTop = content.scrollHeight" in script
    assert "tool_trace: body.tool_trace || []" in script
    assert "coverage_report: body.coverage_report || {}" in script
    assert "Agent가 확인한 내용" in script
    assert "renderStatusTrail" in script
    assert "boi-agent-status-trail" in script
    assert "<details class=\"boi-agent-status-trail\">" in script
    assert "진행 단계 ${lines.length}개" in script
    assert "```[^\\S\\r\\n]*([A-Za-z0-9_-]+)?" in script
    assert "renderCellValue" in script
    assert "isTableSeparatorLine" in script
    assert "isLikelyTableStart" in script
    assert "normalizeTableRow" in script
    assert "inCode || parenDepth > 0" in script
    assert "boi-agent-message-author" in script
    assert "boi-agent-inline-image" in script
    assert "openImageArtifact" in script
    assert 'event.key === "Escape" && state.viewer' in script
    assert "data-open-answer" in script
    assert "openAnswer" in script
    assert "답변 크게 보기" in script
    assert "boi-agent-answer-viewer" in script
    assert "seenMermaidSources" in script
    assert 'artifact.type === "workflow_summary"' in script
    assert "renderObjectTable(rows)" in script
    assert "JSON.stringify(artifact.data, null, 2)" not in script
    assert "[-*+]" in script
    assert "https?:" in script
    assert "requestModeForQuestion" not in script
    assert "mode: routeHint.mode" not in script
    assert "selected_text" in script
    assert "boi-agent-handoff-form" in script
    assert "boi-agent-confirmation-card" in script
    assert "/api/agents/boi-wiki/approve" in script
    assert "data-agent-approve" in script
    assert "data-agent-approve-note" in script
    assert "BoI Agent confirmation card" not in script
    assert "agentApprovalResultMessage" in script
    assert "Event 발행 요청을 보냈습니다." in script
    assert "업무 흐름 시작 요청을 보냈습니다." in script
    assert "Action 실행 요청을 보냈습니다." in script
    assert "Manual Handoff 완료 기록을 남겼습니다." in script
    assert "Event Type 초안을 만들었습니다." in script
    assert "공유 요청을 제출했습니다." in script
    assert "기술 세부정보" in script
    assert ">Workflow<" not in script
    assert ">Raw<" not in script
    assert "업무 흐름과 원본 기록" in script
    assert "boi-agent-memory-form" not in script
    assert "boi-agent-dictionary-form" not in script
    assert "event.shiftKey" in script
    assert "/api/agents/boi-wiki/manual-handoffs/complete" in script
    assert "width:min(900px" in style
    assert "width:min(1120px" in style
    assert ".boi-agent-approve-note" in style
    assert ".boi-agent-content { overflow-y:auto; overflow-x:hidden;" in style
    assert ".boi-agent-answer pre, .boi-agent-artifact pre { margin:8px 0; max-height:220px; overflow-y:auto; overflow-x:hidden;" in style
    assert ".boi-agent-inline-image" in style
    assert ".boi-agent-message > .boi-agent-message-author" in style
    assert ".boi-agent-message strong { display:block;" not in style
    assert "table-layout:fixed" in style
    assert ".boi-agent-run-summary" in style
    assert ".boi-agent-status-trail" in style
    assert ".boi-agent-status-trail summary" in style
    assert ".boi-agent-answer-actions" in style
    assert ".boi-agent-answer-viewer .boi-agent-answer" in style
    assert ".boi-agent-window-actions .boi-agent-new { display:none; }" not in style

    source = (boi_app_module.APP_DIR / "main.py").read_text(encoding="utf-8")
    assert "stream_plan = await asyncio.to_thread(agent_stream_plan, req, employee_id)" in source


def test_mermaid_loader_retries_after_cdn_load_failure(boi_app_module):
    script = (boi_app_module.APP_DIR / "static" / "mermaid_render.js").read_text(encoding="utf-8")

    assert "let loadPromise = null;" in script
    assert "let settled = false;" in script
    assert "loadPromise = null;" in script
    assert "script.remove();" in script
    assert "script.onerror = () => fail(new Error(\"Mermaid library load failed\"));" in script
    assert "fail(new Error(\"Mermaid library load timed out\"))" in script


def test_pet_agent_markdown_renderer_executes_core_gfm_cases(boi_app_module):
    if not shutil.which("node"):
        pytest.skip("node is required for Pet Agent Markdown renderer smoke")
    script = r"""
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("boi_api/app/static/pet_agent.js", "utf8");
const root = {
  dataset: {},
  style: { setProperty() {}, removeProperty() {} },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  dispatchEvent() {},
  innerHTML: "",
};
global.document = { getElementById() { return root; }, title: "Test", addEventListener() {} };
global.window = { getSelection() { return { toString() { return ""; } }; }, addEventListener() {}, visualViewport: null };
global.location = { search: "?employee_id=100001", pathname: "/", origin: "http://localhost:8000" };
global.URLSearchParams = URLSearchParams;
global.URL = URL;
global.sessionStorage = { getItem() { return null; }, setItem() {} };
global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ suggestions: [], items: [] }) });
global.CustomEvent = function CustomEvent(name, opts) { return { name, ...opts }; };
global.CSS = { escape: (value) => String(value) };
vm.runInThisContext(code);

const markdown = [
  "## Source Mapping",
  "",
  "| Stage | Evidence | Link |",
  "| --- | --- | --- |",
  "| 이상 감지 | `equipment.alarm.raised.v1` and trend | [SOP](/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001) |",
  "",
  "- **확인**: 링크와 굵게",
  "- 줄바꿈된 항목",
  "  같은 bullet에 이어져야 함",
  "1. 첫 번째",
  "   같은 numbered item에 이어져야 함",
  "2. 두 번째",
  "   - 하위 bullet",
  "     하위 bullet 설명",
  "   1. 하위 numbered",
  "",
  "> 인용 문장",
  "> - 인용 목록",
  "",
  "---",
  "",
  "```mermaid",
  "flowchart TD",
  "  A[Start] --> B[End]",
  "```",
].join("\n");
const mermaidSource = "flowchart TD\n  A[Start] --> B[End]";
const html = window.BoiAgentMarkdownDebug.renderMarkdownLite(markdown, {
  skipMermaidSources: new Set([window.BoiAgentMarkdownDebug.normalizeMermaidSource?.(mermaidSource) || mermaidSource.replace(/\s+/g, " ").trim()]),
});
const tableHtml = window.BoiAgentMarkdownDebug.renderMarkdownTable([
  "| Stage | Evidence | Link |",
  "| --- | --- | --- |",
  "| 이상 감지 | `equipment.alarm.raised.v1` | [SOP](/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001) |",
]);
const rawServerHtml = "<p>| 항목 | 값 |<br>| --- | --- |<br>| 상태 | 완료 |</p>";
const rawHeadingHtml = "<p># 제목<br>- 항목<br>1. 순서</p>";
const renderedServerHtml = "<table><thead><tr><th>항목</th><th>값</th></tr></thead></table>";
const renderedMermaidServerHtml = "<div class=\"rendered-markdown\"><div class=\"mermaid-diagram\"><div class=\"mermaid\">flowchart TD</div></div></div>";
const runSummaryHtml = window.BoiAgentMarkdownDebug.renderRunSummary({
  role: "assistant",
  meta: {
    tool_trace: [{ tool: "ontology_search", status: "ok", elapsed_ms: 12, summary: "best_matches=3" }],
    coverage_report: { coverage_score: 1, missing: [] },
    guardrails_applied: ["acl_policy"],
  },
});
console.log(JSON.stringify({
  html,
  tableHtml,
  hasTable: html.includes("boi-agent-table-wrap"),
  hasCode: html.includes("<code>equipment.alarm.raised.v1</code>"),
  hasLink: html.includes('href="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"'),
  hasStrong: html.includes("<strong>확인</strong>"),
  hasOrderedList: html.includes("<ol><li>첫 번째 같은 numbered item에 이어져야 함</li><li>두 번째"),
  hasNestedBullet: html.includes("<li>두 번째<ul><li>하위 bullet 하위 bullet 설명</li></ul><ol><li>하위 numbered</li></ol></li>"),
  skippedMermaid: !html.includes("mermaid-diagram") && !html.includes("```mermaid"),
  rawTableSeparatorLeaked: html.includes("| --- |"),
  hasWrappedBullet: html.includes("줄바꿈된 항목 같은 bullet에 이어져야 함"),
  hasWrappedOrderedItem: html.includes("첫 번째 같은 numbered item에 이어져야 함"),
  hasBlockquote: html.includes("<blockquote>") && html.includes("인용 문장") && html.includes("<li>인용 목록</li>"),
  hasHr: html.includes("<hr>"),
  tableKeepsLink: tableHtml.includes("<a href="),
  detectsRawServerMarkdown: window.BoiAgentMarkdownDebug.looksLikeRawMarkdownHtml(rawServerHtml),
  detectsRawHeadingMarkdown: window.BoiAgentMarkdownDebug.looksLikeRawMarkdownHtml(rawHeadingHtml),
  detectsRawBlockquoteMarkdown: window.BoiAgentMarkdownDebug.looksLikeRawMarkdownHtml("<p>&gt; 인용</p>"),
  detectsRawHrMarkdown: window.BoiAgentMarkdownDebug.looksLikeRawMarkdownHtml("<p>---</p>"),
  exposesNormalizeMermaid: typeof window.BoiAgentMarkdownDebug.normalizeMermaidSource === "function",
  acceptsRenderedServerHtml: !window.BoiAgentMarkdownDebug.looksLikeRawMarkdownHtml(renderedServerHtml),
  rejectsDuplicateMermaidServerHtml: !window.BoiAgentMarkdownDebug.shouldUseServerHtml(
    { html: renderedMermaidServerHtml },
    new Set([window.BoiAgentMarkdownDebug.normalizeMermaidSource?.(mermaidSource) || mermaidSource.replace(/\s+/g, " ").trim()])
  ),
  acceptsPlainRenderedServerHtml: window.BoiAgentMarkdownDebug.shouldUseServerHtml(
    { html: renderedServerHtml },
    new Set([window.BoiAgentMarkdownDebug.normalizeMermaidSource?.(mermaidSource) || mermaidSource.replace(/\s+/g, " ").trim()])
  ),
  hasRunSummary: runSummaryHtml.includes("Agent가 확인한 내용") && runSummaryHtml.includes("관련 지식 검색") && runSummaryHtml.includes("권한/보안 가드레일"),
}));
"""
    result = subprocess.run(
        ["node"],
        input=script,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert payload["hasTable"]
    assert payload["hasCode"]
    assert payload["hasLink"]
    assert payload["hasStrong"]
    assert payload["hasOrderedList"]
    assert payload["hasNestedBullet"]
    assert payload["skippedMermaid"]
    assert not payload["rawTableSeparatorLeaked"]
    assert payload["hasWrappedBullet"]
    assert payload["hasWrappedOrderedItem"]
    assert payload["hasBlockquote"]
    assert payload["hasHr"]
    assert payload["tableKeepsLink"]
    assert payload["detectsRawServerMarkdown"]
    assert payload["detectsRawHeadingMarkdown"]
    assert payload["detectsRawBlockquoteMarkdown"]
    assert payload["detectsRawHrMarkdown"]
    assert payload["exposesNormalizeMermaid"]
    assert payload["acceptsRenderedServerHtml"]
    assert payload["rejectsDuplicateMermaidServerHtml"]
    assert payload["acceptsPlainRenderedServerHtml"]
    assert payload["hasRunSummary"]


def test_server_markdown_renderer_handles_agent_quote_hr_and_inline_styles(boi_app_module):
    html = str(
        boi_app_module.render_markdown(
            "\n".join(
                [
                    "> **중요** 인용",
                    "> - 인용 목록",
                    "",
                    "---",
                    "",
                    "본문에는 *강조*, ~~삭제~~, `*코드는 그대로*`가 있습니다.",
                ]
            ),
            employee_id="100001",
        )
    )

    assert "<blockquote>" in html
    assert "<strong>중요</strong>" in html
    assert "<li>인용 목록</li>" in html
    assert "<hr>" in html
    assert "<em>강조</em>" in html
    assert "<del>삭제</del>" in html
    assert "<code>*코드는 그대로*</code>" in html
    assert "<em>코드는 그대로</em>" not in html


def test_boi_agent_suggestions_resolve_current_sop_context(boi_app_module, monkeypatch):
    seen_contexts: list[dict[str, Any]] = []

    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        seen_contexts.append(page_context)
        assert page_context["stage_count"] == 4
        assert page_context["workflow_action_count"] > 0
        assert page_context["workflow_manual_action_count"] > 0
        return [
            f"{page_context['title']}의 Action과 Manual Handoff 관계를 질문해보세요.",
            "이 SOP 실행에 필요한 Action Spec 누락 여부를 점검해줘.",
        ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "client supplied title should not win"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    suggestions = body["suggestions"]
    joined = " ".join(suggestions)
    assert body["suggestions_source"] == "llm"
    assert seen_contexts
    assert body["page_context"]["stage_count"] == 4
    assert body["page_context"]["workflow_action_count"] > 0
    assert body["page_context"]["workflow_manual_action_count"] > 0
    assert "설비 이상 감지·원인 분석·이상 조치 SOP" in joined
    assert "client supplied title should not win" not in joined
    assert "Action" in joined
    assert "Manual Handoff" in joined


def test_boi_agent_suggestions_use_event_type_context(boi_app_module, monkeypatch):
    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        assert page_context["event_type"] == "equipment.alarm.raised.v1"
        assert page_context["sop_ref"]
        assert page_context["recommended_actions"]
        return [
            f"{page_context['event_type']}의 SOP stage를 기준으로 설명해줘.",
            "recommended action이 실제 Action Spec과 연결되는지 확인해줘.",
        ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={"current_url": "/event-types/equipment.alarm.raised.v1?employee_id=100001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions_source"] == "llm"
    suggestions = body["suggestions"]
    joined = " ".join(suggestions)
    assert "equipment.alarm.raised.v1" in joined
    assert "SOP stage" in joined
    assert "recommended action" in joined


def test_boi_agent_suggestions_respect_restricted_context(boi_app_module, monkeypatch):
    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        assert page_context["access"]["classification"] == "restricted"
        assert page_context["access"]["can_use_in_agent_context"] is False
        return ["접근 정책 때문에 이 문서의 원문을 Agent 컨텍스트로 쓰지 않는 이유를 알려줘."]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)
    client = TestClient(boi_app_module.app)
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/sop",
            "title": "Restricted Suggestion Test",
            "description": "restricted suggestions must not invite context use",
            "tags": ["Restricted", "Agent"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:public:sop:restricted-suggestion-test",
            "visibility": "public",
            "classification": "restricted",
            "owner": "public",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:public",
            "status": "draft",
            "review": {"reviewer": "pytest", "review_status": "draft"},
            "source_refs": [{"type": "test", "ref": "restricted-suggestion"}],
            "workflow": {"workflow_key": "restricted-suggestion-test", "stages": [{"id": "restricted", "name": "Restricted Stage"}]},
        },
        "# Summary\n\nrestricted context body",
    )

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={"current_url": "/docs/boi:public:sop:restricted-suggestion-test?employee_id=100001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions_source"] == "llm"
    suggestions = body["suggestions"]
    joined = " ".join(suggestions)
    assert "접근 정책" in joined
    assert "Mermaid" not in joined
    assert "Action Spec" not in joined


def test_boi_agent_suggestions_use_llm_writer_when_required(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "suggestions": [
                                        "현재 SOP의 단계별 Event와 Action 흐름을 그림으로 정리해줘.",
                                        "이 SOP에서 사람이 확인해야 하는 조치 항목만 모아줘.",
                                        "이 SOP 실행에 필요한 Action Spec 누락 여부를 점검해줘.",
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_BASE_URL", "http://router.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={"current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions_source"] == "llm"
    assert body["suggestions"][0].startswith("현재 SOP")
    assert payloads[0]["url"] == "http://router.example/v1/chat/completions"
    prompt = payloads[0]["json"]["messages"][1]["content"]
    assert "boi_agent_page_suggestions_only" in prompt
    assert "설비 이상 감지·원인 분석·이상 조치 SOP" in prompt


def test_boi_agent_suggestions_fail_when_required_llm_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def broken_suggestions(req, employee_id: str, page_context):
        raise boi_app_module.BoiAgentSuggestionsUnavailable("suggestion model timeout")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", broken_suggestions)

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={"current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "boi_agent_suggestions_unavailable"
    assert detail["required"] is True
    assert "suggestion model timeout" in detail["message"]


def test_boi_agent_suggestions_placeholder_env_inherits_router_llm(boi_app_module):
    assert (
        boi_app_module.inherit_llm_env_value(
            "http://llm-gateway.example:1236/v1",
            "http://router.example/v1",
        )
        == "http://router.example/v1"
    )
    assert (
        boi_app_module.inherit_llm_env_value(
            "not-needed",
            "real-router-key",
            secret=True,
        )
        == "real-router-key"
    )


def test_trusted_header_identity_blocks_employee_query_spoof(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "trusted_header")
    client = TestClient(boi_app_module.app)
    headers = {
        "x-hynix-employee-id": "200001",
        "x-hynix-name": "SKH SSO User",
        "x-hynix-teams": "platform",
        "x-hynix-roles": "boi.viewer,boi.editor",
    }

    me = client.get("/api/auth/me?employee_id=200001", headers=headers)
    spoof = client.get("/api/auth/me?employee_id=100001", headers=headers)

    assert me.status_code == 200
    assert me.json()["employee_id"] == "200001"
    assert me.json()["teams"] == ["platform"]
    assert spoof.status_code == 403


def test_trusted_header_teams_drive_acl_without_dev_user_map(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "trusted_header")
    client = TestClient(boi_app_module.app)
    headers = {
        "x-hynix-employee-id": "200001",
        "x-hynix-teams": "platform",
        "x-hynix-roles": "boi.viewer",
    }

    response = client.get("/api/boi?employee_id=200001&folder=team/platform", headers=headers)
    private_response = client.get("/api/boi?employee_id=200001&folder=private/100001", headers=headers)

    assert response.status_code == 200
    assert response.json()["count"] >= 1
    assert all(item["uri"].startswith("/team/platform/") for item in response.json()["items"])
    assert private_response.status_code == 200
    assert private_response.json()["count"] == 0


def test_trusted_header_editor_role_required_for_source_apply(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "trusted_header")
    client = TestClient(boi_app_module.app)
    viewer_headers = {
        "x-hynix-employee-id": "200001",
        "x-hynix-teams": "platform",
        "x-hynix-roles": "boi.viewer",
    }
    editor_headers = {**viewer_headers, "x-hynix-roles": "boi.viewer,boi.editor"}
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source = client.get(f"/api/source?employee_id=200001&path={source_ref}", headers=viewer_headers).json()

    denied = client.post(
        "/api/source/apply?employee_id=200001",
        headers=viewer_headers,
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": source["content"] + "\n<!-- viewer denied -->\n",
            "author": "200001",
        },
    )
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "committed", "commit_hash": "abc123"})
    allowed = client.post(
        "/api/source/apply?employee_id=200001",
        headers=editor_headers,
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": source["content"] + "\n<!-- editor allowed -->\n",
            "author": "200001",
        },
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["applied"] is True
    assert allowed.json()["commit_status"] == "committed"


def test_hynix_hcp_project_roles_map_to_boi_roles(boi_app_module, monkeypatch):
    import boi_api.app.auth as auth

    auth._HCP_CACHE.clear()
    monkeypatch.setenv("KEYCLOAK_HCP_API_URL", "http://mock-hcp/v1/projects/langflow/roles")

    class FakeResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "project": "langflow",
                "response": {
                    "managers": ["100001"],
                    "deployApprovers": ["100003"],
                    "developers": ["100002"],
                },
            }

    monkeypatch.setattr(auth.httpx, "get", lambda *args, **kwargs: FakeResponse())

    manager = auth.hcp_permissions("100001")
    developer = auth.hcp_permissions("100002")
    approver = auth.hcp_permissions("100003")

    assert "boi.admin" in manager["roles"]
    assert "boi.action_invoker" in developer["roles"]
    assert "boi.promoter" not in developer["roles"]
    assert "boi.promoter" in approver["roles"]
    assert approver["hcp_role_groups"] == ["deployApprovers"]

    with pytest.raises(auth.AuthError) as exc:
        auth.hcp_permissions("100009")
    assert exc.value.status_code == 403


def test_keycloak_allowed_employee_alias_and_admin_bypass(boi_app_module, monkeypatch):
    import boi_api.app.auth as auth

    monkeypatch.delenv("BOI_ALLOWED_EMPLOYEE_IDS", raising=False)
    monkeypatch.setenv("KEYCLOAK_ALLOWED_EMPLOYEE", "100001")
    monkeypatch.setenv("KEYCLOAK_ADMIN_EMPLOYEES", "100003")

    auth.allowed_employee_check(auth.AuthIdentity(employee_id="100001", display_name="allowed"))
    auth.allowed_employee_check(auth.AuthIdentity(employee_id="100003", display_name="admin-employee"))
    auth.allowed_employee_check(auth.AuthIdentity(employee_id="100004", display_name="admin-role", roles=["boi.admin"]))

    with pytest.raises(auth.AuthError) as exc:
        auth.allowed_employee_check(auth.AuthIdentity(employee_id="100002", display_name="denied"))
    assert exc.value.status_code == 403


def test_keycloak_external_server_url_is_used_for_browser_redirect(boi_app_module, monkeypatch):
    import boi_api.app.auth as auth

    monkeypatch.setenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
    monkeypatch.setenv("KEYCLOAK_EXTERNAL_SERVER_URL", "http://localhost:8088")
    monkeypatch.setenv("KEYCLOAK_REALM", "boi-dev")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "boi-wiki")
    monkeypatch.setenv("KEYCLOAK_REDIRECT_URI", "http://localhost:8000/auth/callback")

    url = auth.keycloak_authorization_url(state="state-1", code_challenge="challenge-1")

    assert url.startswith("http://localhost:8088/realms/boi-dev/protocol/openid-connect/auth?")
    assert "client_id=boi-wiki" in url


def test_service_token_delegates_employee_identity_in_sso_mode(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "keycloak")
    client = TestClient(boi_app_module.app)

    response = client.get(
        "/api/boi?employee_id=100001&folder=team/platform",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
    )
    no_token = client.get("/api/boi?employee_id=100001&folder=team/platform")

    assert response.status_code == 200
    assert response.json()["count"] >= 1
    assert no_token.status_code == 401


def test_boi_api_lists_accessible_docs_with_yaml_timestamps(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/boi?employee_id=100001&q=SOP")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any("SOP" in item["metadata"].get("title", "") for item in body["items"])


def test_equipment_anomaly_demo_route_publishes_first_event(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/workflows/demo/equipment-anomaly/start?employee_id=100001",
        json={
            "user_confirmed": True,
            "equipment_id": "ETCH-VM-01",
            "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            "title": "Response Chain 이상 Alarm 발생",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["workflow"]["name"] == "equipment-anomaly"
    assert body["workflow"]["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert body["workflow"]["sop_uri"] == "/public/sop/equipment-abnormal-response.md"
    assert body["workflow"]["status_url"].startswith("/api/workflows/demo/equipment-anomaly/status?trace_id=")
    assert "manual.equipment.confirm_alarm_context" in body["workflow"]["expected_manual_actions"]
    assert body["event"]["event_type"] == "equipment.alarm.raised.v1"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["topic"] == "boi.events"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["event"]["payload"]["equipment_id"] == "ETCH-VM-01"


def test_events_page_renders_structured_result_instead_of_raw_dict(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-rendering-test",
            "event_type": "corrective_action.requested.v1",
            "actor": "agent",
            "producer": "test",
            "trace_id": "trace-rendering-test",
            "payload": {"title": "렌더링 테스트"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {"ok": True, "status": "dispatched"},
            "body": '# Summary\n\n- 첫 번째 조치\n\n```json\n{"risk": "high", "approval_required": true}\n```',
        },
    )

    response = client.get("/events?employee_id=100001")

    assert response.status_code == 200
    assert "structured-data" in response.text
    assert '<div class="kv-key">routed_by</div>' in response.text
    assert "<h3>Summary</h3>" in response.text
    assert "<li>첫 번째 조치</li>" in response.text
    assert '<div class="kv-key">approval_required</div>' in response.text
    assert "{&#x27;routed_by&#x27;" not in response.text


def test_events_page_uses_pagination_and_lazy_raw_json(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-lazy-events-test"
    large_payload = {"response": {"item": {"metadata": {"boi_id": "boi-large-raw-test"}, "body": "RAW_BODY_SHOULD_BE_LAZY"}}}
    for index in range(55):
        boi_app_module.append_event_log(
            status="handled",
            event={
                "event_id": f"evt-lazy-events-{index:02d}",
                "event_type": "equipment.alarm.raised.v1",
                "actor": "agent",
                "producer": "test",
                "trace_id": trace_id,
                "payload": {"title": f"Lazy 이벤트 {index:02d}"},
            },
            result={
                "routed_by": "event-router",
                "dispatch_result": {
                    "ok": True,
                    "status": "handled",
                    "results": [{"action_key": "boi.materialize_event", "result": large_payload}],
                },
            },
        )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert response.text.count('class="doc-row event-row"') == 50
    assert 'name="limit"' in response.text
    assert "Page 1" in response.text
    assert "Next" in response.text
    assert "Raw JSON 불러오기" in response.text
    assert "/api/events/raw/" in response.text
    assert "RAW_BODY_SHOULD_BE_LAZY" not in response.text


def test_event_raw_api_returns_single_row_payload(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-event-raw-api-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-event-raw-api-test",
            "event_type": "equipment.alarm.raised.v1",
            "actor": "agent",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "Raw API 테스트"},
        },
        result={"raw_marker": "RAW_API_MARKER", "dispatch_result": {"ok": True, "status": "handled", "results": []}},
    )
    events = client.get(f"/events?employee_id=100001&trace_id={trace_id}").text
    match = re.search(r"/api/events/raw/([^?\"&]+)\?employee_id=100001", events)

    assert match
    response = client.get(f"/api/events/raw/{unquote(match.group(1))}?employee_id=100001")
    missing = client.get("/api/events/raw/no-such-row?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["row"]["result"]["raw_marker"] == "RAW_API_MARKER"
    assert body["row"]["trace_id"] == trace_id
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")


def test_action_raw_api_and_html_show_single_action_result_with_links(boi_app_module):
    client = TestClient(boi_app_module.app)
    log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-18T13:00:00+09:00",
            "action_key": "langflow.equipment.stage_analysis",
            "request_id": "act-action-raw-link",
            "employee_id": "100001",
            "event_id": "evt-action-raw-link",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": "trace-action-raw-link",
            "boi_id": "boi:private:100001:action:raw",
            "status": "langflow_invoked",
            "doc_ref": "boi:public:actions:langflow:stage-analysis",
            "result": {
                "message": (
                    "# Langflow BoI Execution Result\n\n"
                    "## Analysis Draft\n"
                    "**Current Finding**\n"
                    "FULL_LANGFLOW_MESSAGE_START " + ("원본 결과 " * 20) + " FULL_LANGFLOW_MESSAGE_END\n\n"
                    "**Evidence Used**\n"
                    "- event_type: root_cause.analysis.requested.v1\n\n"
                    "## BoI Write Result\n"
                    "```json\n{\"raw_only_marker\":\"RAW_DETAIL_ONLY\"}\n```"
                ),
                "headers": {"x-service-token": "secret-should-redact"},
            },
        },
    )
    encoded = quote(log_ref, safe="")

    api_response = client.get(f"/api/actions/raw/{encoded}?employee_id=100001")
    html_response = client.get(f"/actions/raw/{encoded}?employee_id=100001")
    missing = client.get("/api/actions/raw/no-such-row?employee_id=100001")

    assert api_response.status_code == 200
    assert api_response.json()["row"]["request_id"] == "act-action-raw-link"
    assert "FULL_LANGFLOW_MESSAGE_END" in api_response.json()["row"]["result"]["message"]
    assert api_response.json()["row"]["result"]["headers"]["x-service-token"] == "[REDACTED]"
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")

    assert html_response.status_code == 200
    assert html_response.headers["content-type"].startswith("text/html")
    assert "Action Raw Detail" in html_response.text
    assert "Readable Result" in html_response.text
    assert 'class="workflow-panel action-readable-result"' in html_response.text
    readable_section = html_response.text.split("Compact Raw Metadata", 1)[0]
    assert "FULL_LANGFLOW_MESSAGE_END" in html_response.text
    assert "FULL_LANGFLOW_MESSAGE_END" in readable_section
    assert "BoI Write Result" not in readable_section
    assert "RAW_DETAIL_ONLY" not in readable_section
    assert '<details class="workflow-panel raw-log-details">' in html_response.text
    assert "/events?employee_id=100001&amp;event_id=evt-action-raw-link" in html_response.text
    assert "/workflows/equipment-anomaly/status?employee_id=100001&amp;trace_id=trace-action-raw-link" in html_response.text
    assert "/docs/boi:public:actions:langflow:stage-analysis?employee_id=100001" in html_response.text
    assert "secret-should-redact" not in html_response.text


def test_doc_page_renders_markdown_body(boi_app_module):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Markdown Rendering Test",
            "description": "Markdown 렌더링 확인",
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi-rendering-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "acl_policy": {"agent": "boi-writer-v0.1"},
            "status": "draft",
        },
        "# Summary\n\n본문이 **굵게** 보이고 `inline code`도 보입니다.\n\n1. 첫 번째 확인\n2. 두 번째 확인\n\n- [x] 완료 항목\n- [ ] 대기 항목\n+ 플러스 목록도 지원\n\n| 항목 | 상태 |\n|---|---|\n| Markdown | OK |\n\n항목 | 상태\n--- | ---\nGFM table | OK\n\n| Case | Value | Link |\n| --- | --- | --- |\n| escaped pipe | A\\|B | [SOP](/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001) |\n| code pipe | `a|b` | [Pipe URL](/events?employee_id=100001&trace_id=trace-a|b) |\n\n```mermaid\nflowchart TD\n  A[Start] --> B[End]\n```\n\n```python\nprint('plain code')\n```",
    )

    response = client.get("/docs/boi-rendering-test?employee_id=100001")
    uri_response = client.get(f"/docs{doc['uri']}?employee_id=100001")

    assert response.status_code == 200
    assert uri_response.status_code == 200
    assert '<div class="markdown-body rendered-content">' in response.text
    assert "<h3>Summary</h3>" in response.text
    assert "<strong>굵게</strong>" in response.text
    assert "<code>inline code</code>" in response.text
    assert "<ol><li>첫 번째 확인</li><li>두 번째 확인</li></ol>" in response.text
    assert '<input type="checkbox" disabled checked>' in response.text
    assert '<input type="checkbox" disabled>' in response.text
    assert "플러스 목록도 지원" in response.text
    assert '<table class="markdown-table">' in response.text
    assert response.text.count('<table class="markdown-table">') >= 3
    assert "GFM table" in response.text
    assert "A|B" in response.text
    assert "<code>a|b</code>" in response.text
    assert "/events?employee_id=100001&amp;trace_id=trace-a|b" in response.text
    assert '/static/mermaid_render.js?v=' in response.text
    assert response.text.count('/static/mermaid_render.js?v=') == 1
    assert '<div class="mermaid-diagram" data-mermaid-state="pending">' in response.text
    assert '<div class="mermaid">' in response.text
    assert "flowchart TD" in response.text
    assert "Mermaid source" in response.text
    assert "print(&#x27;plain code&#x27;)" in response.text
    assert "<pre class=\"markdown-body\">" not in response.text


def test_doc_markdown_tables_preserve_readable_columns(boi_app_module):
    style = Path("boi_api/app/static/style.css").read_text(encoding="utf-8")

    assert ".rendered-content .table-wrap { overflow-x:auto;" in style
    assert ".rendered-content .markdown-table { width:max-content; min-width:100%;" in style
    assert "word-break:keep-all" in style
    assert ".rendered-content .markdown-table a, .rendered-content .markdown-table code { word-break:break-word; overflow-wrap:anywhere; }" in style


def test_index_renders_okf_folder_tree_for_accessible_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'class="library-layout"' in response.text
    assert "BoI Wiki Explorer" in response.text
    assert "All Accessible" in response.text
    assert "public" in response.text
    assert "team/aix-tf" in response.text
    assert "team/platform" in response.text
    assert "private/100001" in response.text


def test_index_renders_resizable_folder_sidebar_controls(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001")
    library_js = Path("boi_api/app/static/library.js").read_text(encoding="utf-8")
    style_css = Path("boi_api/app/static/style.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'class="folder-resize-handle"' in response.text
    assert 'aria-label="BoI Wiki Explorer width 조절"' in response.text
    assert 'role="separator"' in response.text
    assert "--folder-sidebar-width" in style_css
    assert "boiWiki.folderSidebarWidth" in library_js
    assert "initSidebarResize" in library_js


def test_index_folder_filter_limits_documents_by_uri_prefix(boi_app_module):
    client = TestClient(boi_app_module.app)

    platform_response = client.get("/?employee_id=100001&folder=team/platform")
    private_response = client.get("/?employee_id=100001&folder=private/100001")

    assert platform_response.status_code == 200
    assert "Platform Team Kafka Event Broker SOP" in platform_response.text
    assert "AIX 확산 TF 업무 맥락 자산화 PoC 계획" not in platform_response.text
    assert "개인 Private BoI 예시" not in platform_response.text
    assert 'class="breadcrumb"' in platform_response.text

    assert private_response.status_code == 200
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" in private_response.text
    assert "Platform Team Kafka Event Broker SOP" not in private_response.text


def test_index_does_not_leak_inaccessible_folder_documents(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100002&folder=private/100001")

    assert response.status_code == 200
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" not in response.text
    assert "Platform Team Kafka Event Broker SOP" not in response.text
    assert 'class="empty-state"' in response.text


def test_boi_api_filters_by_okf_folder_and_returns_tree_context(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/boi?employee_id=100001&folder=team/platform")

    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == "team/platform"
    assert body["count"] >= 1
    assert all(item["uri"].startswith("/team/platform/") for item in body["items"])
    assert any(item["label"] == "team" for item in body["breadcrumbs"])
    assert body["folder_tree"]["path"] == ""
    assert any(child["path"] == "team" for child in body["folder_tree"]["children"])


def test_doc_page_renders_metadata_as_readable_key_value_grid(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:team:platform:kafka-sop-v0.1?employee_id=100001")
    fragment = client.get("/api/docs/boi:team:platform:kafka-sop-v0.1/metadata-fragment?employee_id=100001")

    assert response.status_code == 200
    assert fragment.status_code == 200
    assert '<details class="metadata"' in response.text
    assert '<section class="metadata">' not in response.text
    assert response.text.index('<section class="body">') < response.text.index('<details class="metadata"')
    assert 'class="metadata-grid metadata-summary-grid"' in response.text
    assert "Load Full Metadata" in response.text
    assert response.text.count("Load Full Metadata") == 1
    assert "/api/docs/boi:team:platform:kafka-sop-v0.1/metadata-fragment?employee_id=100001" in response.text
    assert "/api/docs/boi:team:platform:kafka-sop-v0.1/access?employee_id=100001" in response.text
    assert "Access Policy" in response.text
    assert '<dt class="metadata-key">visibility</dt>' in response.text
    assert '<dd class="metadata-value"><span class="scalar string">team</span></dd>' in response.text
    assert '<dt class="metadata-key">acl_policy</dt>' not in response.text
    assert '<dt class="metadata-key">okf_version</dt>' in fragment.text
    assert '<dd class="metadata-value"><span class="scalar string">0.1</span></dd>' in fragment.text
    assert '<dt class="metadata-key">acl_policy</dt>' in fragment.text
    assert '<dd class="metadata-value"><span class="scalar string">acl:team:platform</span></dd>' in fragment.text


def test_app_shell_renders_consistent_global_nav_and_dev_auth_state(boi_app_module):
    client = TestClient(boi_app_module.app)
    cases = {
        "/?employee_id=100001": "library",
        "/events?employee_id=100001": "events",
        "/event-types?employee_id=100001": "event_types",
        "/actions?employee_id=100001": "actions",
        "/sops?employee_id=100001": "sops",
        "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001": "sops",
    }

    for url, active_nav in cases.items():
        response = client.get(url)
        assert response.status_code == 200
        assert 'class="app-header"' in response.text
        assert 'class="global-nav"' in response.text
        assert "BoI Wiki" in response.text
        assert "SOP" in response.text
        assert "Event Types" in response.text
        assert "Event Stream" in response.text
        assert "Actions" in response.text
        assert "Workflows" not in response.text
        assert "/static/mermaid_render.js?v=" in response.text
        assert 'class="utility-nav"' in response.text
        assert "Langflow" in response.text
        assert "Kafka UI" in response.text
        assert "MCP Status" in response.text
        assert "DEV" in response.text
        assert "SSO 가이드" in response.text
        assert 'class="identity-strip"' in response.text
        assert 'class="auth-card"' not in response.text
        assert 'class="auth-mode-banner"' not in response.text
        assert 'class="dev-employee-switch"' in response.text
        assert re.search(rf'<a[^>]+data-nav-id="{active_nav}"[^>]+aria-current="page"', response.text)

    home = client.get("/?employee_id=100001")
    assert "AI Agent의 협업 표준 문서를 업무 단위의 Event와 SOP 기반의 AI Native Workflow 그리고 Action을 기준으로 탐색합니다." in home.text
    assert "<title>BoI Wiki</title>" in home.text


def test_app_shell_infers_same_host_tool_urls_for_external_host(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KAFKA_UI_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("BOI_WIKI_MCP_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app, base_url="http://boi-wiki.example:28000")

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'class="utility-nav"' in response.text
    assert "API Docs" in response.text
    assert 'href="http://boi-wiki.example:27860"' in response.text
    assert 'href="http://boi-wiki.example:28081"' in response.text
    assert 'href="http://boi-wiki.example:28200"' in response.text
    assert "http://localhost" not in response.text


def test_app_shell_uses_request_domain_when_external_url_is_blank_or_local(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://localhost:8000")
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KAFKA_UI_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("BOI_WIKI_MCP_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app, base_url="http://wiki.example.internal:28000")

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'href="http://wiki.example.internal:27860"' in response.text
    assert 'href="http://wiki.example.internal:28081"' in response.text
    assert 'href="http://wiki.example.internal:28200"' in response.text
    assert "http://localhost" not in response.text


def test_app_shell_uses_configured_external_tool_urls(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.setenv("LANGFLOW_EXTERNAL_URL", "http://langflow.example:27860")
    monkeypatch.setenv("KAFKA_UI_EXTERNAL_URL", "http://kafka-ui.example:28081")
    monkeypatch.setenv("BOI_WIKI_MCP_EXTERNAL_URL", "http://boi-wiki-mcp.example:28200")
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001", headers={"host": "boi-wiki.example:28000"})

    assert response.status_code == 200
    assert "http://langflow.example:27860" in response.text
    assert "http://kafka-ui.example:28081" in response.text
    assert "http://boi-wiki-mcp.example:28200" in response.text
    assert "http://localhost:7860" not in response.text
    assert "http://localhost:8081" not in response.text
    assert "http://localhost:8200" not in response.text


def test_app_shell_shows_sso_state_and_hides_dev_employee_switch_in_non_dev_mode(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "trusted_header")
    client = TestClient(boi_app_module.app)
    headers = {
        "x-hynix-employee-id": "200001",
        "x-hynix-name": "SKH SSO User",
        "x-hynix-teams": "platform",
        "x-hynix-roles": "boi.viewer,boi.editor",
    }

    response = client.get("/?employee_id=200001", headers=headers)

    assert response.status_code == 200
    assert "SSO" in response.text
    assert "SKH SSO User" in response.text
    assert "platform" in response.text
    assert "Logout" in response.text
    assert 'class="identity-strip"' in response.text
    assert 'class="auth-card"' not in response.text
    assert 'class="auth-mode-banner"' not in response.text
    assert ">DEV<" not in response.text
    assert 'class="dev-employee-switch"' not in response.text
    assert "employee_id query 허용" not in response.text


def test_doc_page_moves_local_links_into_page_actions_bar(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    header = response.text.split("</header>", 1)[0]
    assert "폴더로 돌아가기" not in header
    assert "Source 보기 / Draft 수정" not in header
    assert 'class="page-actions"' in response.text
    assert "폴더로 돌아가기" in response.text
    assert "Source 보기 / 검증 편집" in response.text
    assert "같은 Event Type BoI" in response.text


def test_event_types_page_filters_by_search_sop_and_workflow_stage(boi_app_module):
    client = TestClient(boi_app_module.app)

    alarm = client.get("/event-types?employee_id=100001&q=alarm")
    has_sop = client.get("/event-types?employee_id=100001&has_sop=true")
    detect_stage = client.get("/event-types?employee_id=100001&workflow_stage=이상%20감지")

    assert alarm.status_code == 200
    assert "equipment.alarm.raised.v1" in alarm.text
    assert "meeting.closed.v1" not in alarm.text
    assert "필터 적용" in alarm.text
    assert "필터 해제" in alarm.text
    assert has_sop.status_code == 200
    assert "equipment.alarm.raised.v1" in has_sop.text
    assert "meeting.closed.v1" not in has_sop.text
    assert detect_stage.status_code == 200
    assert "equipment.alarm.raised.v1" in detect_stage.text
    assert "trend.anomaly.detected.v1" in detect_stage.text
    assert "root_cause.analysis.requested.v1" not in detect_stage.text


def test_keycloak_login_still_redirects_to_authorization_endpoint(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "keycloak")
    monkeypatch.setenv("BOI_SESSION_SECRET", "dev-boi-session-secret-change-me")
    monkeypatch.setenv("KEYCLOAK_SERVER_URL", "http://localhost:8088")
    monkeypatch.setenv("KEYCLOAK_EXTERNAL_SERVER_URL", "http://localhost:8088")
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", "http://localhost:8088")
    monkeypatch.setenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
    monkeypatch.setenv("KEYCLOAK_REALM", "boi-dev")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "boi-wiki")
    monkeypatch.setenv("KEYCLOAK_REDIRECT_URI", "http://localhost:8000/auth/callback")
    client = TestClient(boi_app_module.app)

    response = client.get("/auth/login?next=/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:8088/realms/boi-dev/protocol/openid-connect/auth?"
    )


def test_index_loads_library_script_and_prioritizes_library_surface(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=team/platform")

    assert response.status_code == 200
    assert '/static/library.js?v=' in response.text
    assert response.text.index('id="boi-library"') < response.text.index('class="poc-guide"')
    assert 'href="/?employee_id=100001&amp;folder=team%2Fplatform"' in response.text
    assert 'aria-current="page"' in response.text


def test_index_partial_returns_only_library_fragment(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=team/platform&partial=library")

    assert response.status_code == 200
    assert 'id="boi-library"' in response.text
    assert 'class="library-layout"' in response.text
    assert "<header>" not in response.text
    assert "보이는 범위" not in response.text
    assert "Platform Team Kafka Event Broker SOP" in response.text
    assert "AIX 확산 TF 업무 맥락 자산화 PoC 계획" not in response.text


def test_index_partial_does_not_leak_inaccessible_documents(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100002&folder=private/100001&partial=library")

    assert response.status_code == 200
    assert 'id="boi-library"' in response.text
    assert 'class="empty-state"' in response.text
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" not in response.text
    assert "Platform Team Kafka Event Broker SOP" not in response.text


def test_library_static_js_supports_partial_navigation(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/static/library.js")

    assert response.status_code == 200
    assert "history.pushState" in response.text
    assert "popstate" in response.text
    assert "partial" in response.text
    assert "scrollTo" in response.text


def test_public_sop_and_action_folders_are_browsable(boi_app_module):
    client = TestClient(boi_app_module.app)

    cases = {
        "public/sop": "설비 이상 감지·원인 분석·이상 조치 SOP",
        "public/actions": "Public Action Library",
        "public/event-types": "설비 Alarm 발생",
        "public/actions/api": "품질 시스템 Response Trend 확인 시뮬레이션",
        "public/actions/webhook": "외부 Webhook 이벤트 수신",
        "public/actions/mcp": "MCP 기반 BoI 검색 Tool 호출 예시",
        "public/actions/langflow": "Langflow Reference Flow 호출",
        "public/actions/manual": "공정 진행 금지 승인",
    }

    for folder, expected_title in cases.items():
        response = client.get(f"/?employee_id=100001&folder={folder}")
        assert response.status_code == 200
        assert expected_title in response.text


def test_doc_page_rewrites_okf_markdown_links_to_accessible_doc_routes(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert 'href="/docs/boi:public:actions:api:request-trend-history?employee_id=100001">Trend 확인</a>' in response.text
    assert 'href="/docs/boi:public:event-types:equipment.alarm.raised.v1?employee_id=100001">equipment.alarm.raised.v1</a>' in response.text
    assert 'href="/public/actions/api/request-trend-history.md"' not in response.text
    assert 'href="/public/event-types/equipment.alarm.raised.v1.md"' not in response.text
    assert "Relationship Graph" in response.text
    assert "Citations" in response.text


def test_doc_page_defers_relationship_graph_to_lazy_api(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert 'id="relationship-graph-panel"' in response.text
    assert 'data-graph-url="/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001"' in response.text
    assert "Load Relationship Graph" in response.text
    assert "public/sop/equipment-abnormal-response → public/actions/api/request-trend-history" not in response.text


def test_doc_relationship_graph_api_returns_doc_edges(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["concept_id"] == "public/sop/equipment-abnormal-response"
    assert any(edge["target"] == "public/actions/api/request-trend-history" for edge in body["outgoing"])
    assert "nodes" not in body


def test_doc_page_exposes_validated_source_edit_guidance(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")
    editor = client.get("/api/docs/boi:public:sop:equipment-abnormal-response/body-editor?employee_id=100001")

    assert response.status_code == 200
    assert editor.status_code == 200
    assert "draft-only" not in response.text
    assert "Source 보기 / 검증 편집" in response.text
    assert "Body 수정" in response.text
    assert "Preview / Validate" in response.text
    assert "Apply & Commit" in response.text
    assert 'data-editor-url="/api/docs/boi:public:sop:equipment-abnormal-response/body-editor?employee_id=100001"' in response.text
    assert "data-base-sha=" not in response.text
    assert '<textarea class="body-draft-textarea" spellcheck="false"></textarea>' in response.text
    assert "Body source is loaded on demand." in response.text
    assert "# Summary" in editor.json()["body"]
    assert "Public SOP 문서" in editor.json()["body"]
    assert editor.json()["base_sha256"]
    assert "/source?employee_id=100001&amp;path=data%2Fboi%2Fpublic%2Fsop%2Fequipment-abnormal-response.md" in response.text
    assert "/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001" in response.text


def test_doc_body_editor_previews_and_applies_with_commit(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "committed", "commit_hash": "body123"})
    client = TestClient(boi_app_module.app)
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")
    proposed_body = "# Edited Body Apply\n\n본문 apply 테스트"

    preview = client.post(
        "/api/docs/boi:public:sop:equipment-abnormal-response/body-preview?employee_id=100001",
        json={
            "base_sha256": boi_app_module.hashlib.sha256(before.encode("utf-8")).hexdigest(),
            "proposed_body": proposed_body,
            "author": "100001",
            "note": "inline body editor test",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["ok"] is True
    assert "Edited Body Apply" in preview.json()["body_preview_html"]
    assert source_path.read_text(encoding="utf-8") == before

    response = client.post(
        "/api/docs/boi:public:sop:equipment-abnormal-response/body-apply?employee_id=100001",
        json={
            "base_sha256": boi_app_module.hashlib.sha256(before.encode("utf-8")).hexdigest(),
            "proposed_body": proposed_body,
            "author": "100001",
            "note": "inline body editor test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert body["applied"] is True
    assert body["commit_status"] == "committed"
    assert body["commit_hash"] == "body123"
    assert "Edited Body Apply" in source_path.read_text(encoding="utf-8")


def test_generated_private_doc_page_uses_direct_lookup_without_accessible_docs(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/action",
            "title": "Generated Direct Lookup Test",
            "description": "Generated private doc should not need full accessible_docs scan",
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:20990101010101:fastpath",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "boi-writer-fastpath-test"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_event": {"event_id": "evt-fastpath", "event_type": "corrective_action.requested.v1", "trace": "trace-fastpath"},
        },
        "# Summary\n\nGenerated private body fast path",
    )

    def blocked_accessible_docs(employee_id):
        raise AssertionError("accessible_docs should not be called for generated private doc page")

    monkeypatch.setattr(boi_app_module, "accessible_docs", blocked_accessible_docs)
    response = client.get(f"/docs/{doc['metadata']['boi_id']}?employee_id=100001")

    assert response.status_code == 200
    assert "Generated Direct Lookup Test" in response.text
    assert "Generated private body fast path" in response.text


def test_action_spec_is_collapsed_by_default_and_source_citation_is_clickable(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:actions:api:change-spec-rule?employee_id=100001")

    assert response.status_code == 200
    assert '<details class="executable-spec"' in response.text
    assert '<section class="executable-spec"' not in response.text
    assert "data/action_catalog/actions.yaml" in response.text
    assert "/source?employee_id=100001&amp;path=data%2Faction_catalog%2Factions.yaml" in response.text


def test_action_spec_display_rewrites_localhost_examples_for_external_host(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("BOI_WIKI_MCP_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app)

    response = client.get(
        "/docs/boi:public:actions:api:request-raw-data?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )

    assert response.status_code == 200
    assert "http://boi-wiki.example:28000/api/poc/equipment/raw-data" in response.text
    assert "http://boi-wiki.example:28100/api/actions/invoke" in response.text
    assert "ACTION_GATEWAY_EXTERNAL_URL_NOT_CONFIGURED" not in response.text
    assert "http://localhost" not in response.text
    assert "http://boi-api:8000" not in response.text


def test_langflow_simulation_action_spec_uses_agent_flow_display_urls(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app)

    response = client.get(
        "/docs/boi:public:actions:api:request-trend-history?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )

    assert response.status_code == 200
    assert "BoI Universal Simulator Agent" in response.text
    assert "품질 시스템" in response.text
    assert "http://boi-wiki.example:27860/api/v1/run/{flow_id}" in response.text
    assert "http://boi-wiki.example:28100/api/actions/invoke" in response.text
    assert "http://localhost" not in response.text
    assert "http://langflow:7860" not in response.text


def test_workflow_poc_and_promotion_curls_use_external_boi_url(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    client = TestClient(boi_app_module.app)

    sop_response = client.get(
        "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )
    private_response = client.get(
        "/docs/boi:private:100001:seed-note-v0.1?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )

    assert sop_response.status_code == 200
    assert 'curl -X POST "http://boi-wiki.example:28000/api/workflows/equipment-anomaly/start?employee_id=100001"' in sop_response.text
    assert '"user_confirmed":true' in sop_response.text
    assert 'curl -X POST "http://localhost:8000/api/workflows' not in sop_response.text
    assert private_response.status_code == 200
    assert 'curl -X POST "http://boi-wiki.example:28000/api/boi/boi:private:100001:seed-note-v0.1/promote?employee_id=100001"' in private_response.text
    assert 'curl -X POST "http://localhost:8000/api/boi/' not in private_response.text


def test_doc_body_curl_examples_use_external_boi_url_for_external_host(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    client = TestClient(boi_app_module.app)

    direct_sop = client.get(
        "/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )
    event_type = client.get(
        "/docs/boi:public:event-types:equipment.alarm.raised.v1?employee_id=100001",
        headers={"host": "boi-wiki.example:28000"},
    )

    assert direct_sop.status_code == 200
    assert "http://boi-wiki.example:28000/api/workflows/direct-development-reporting/start?employee_id=100001" in direct_sop.text
    assert '"user_confirmed":true' in direct_sop.text
    assert "http://boi-wiki.example:28000/workflows/direct-development-reporting/status?employee_id=100001" in direct_sop.text
    assert "http://localhost:8000/api/workflows/direct-development-reporting" not in direct_sop.text
    assert "http://localhost:8000/workflows/direct-development-reporting" not in direct_sop.text
    assert event_type.status_code == 200
    assert "http://boi-wiki.example:28000/api/workflows/demo/equipment-anomaly/start?employee_id=100001" in event_type.text
    assert "user_confirmed" in event_type.text
    assert "http://localhost:8000/api/workflows/demo/equipment-anomaly" not in event_type.text


def test_action_catalog_source_api_is_valid_with_manual_high_risk_approvals(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/source?employee_id=100001&path=data/action_catalog/actions.yaml")

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "data/action_catalog/actions.yaml"
    assert body["validation"]["ok"] is True
    assert body["validation"]["errors"] == []


def test_source_page_opens_in_read_mode_before_editing(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/source?employee_id=100001&path=data/action_catalog/actions.yaml")

    assert response.status_code == 200
    assert "Source Viewer" in response.text
    assert '<section class="source-viewer" id="source-viewer">' in response.text
    assert '<button id="edit-source" type="button">수정</button>' in response.text
    assert '<section class="source-editor" id="source-editor" hidden>' in response.text
    assert "Preview / Validate 후 Apply & Commit을 실행합니다." in response.text
    assert "Apply & Commit" in response.text
    assert "Save Draft" not in response.text
    assert response.text.index('id="source-viewer"') < response.text.index('id="source-editor"')


def test_source_editor_previews_and_applies_with_commit(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "committed", "commit_hash": "src123"})
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")

    source_response = client.get(f"/api/source?employee_id=100001&path={source_ref}")
    assert source_response.status_code == 200
    source = source_response.json()
    assert "draft_only" not in source
    assert source["validation"]["ok"] is True

    proposed = before + "\n<!-- validated apply test -->\n"
    preview_response = client.post(
        "/api/source/preview?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": proposed,
            "author": "100001",
            "note": "test preview",
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["ok"] is True
    assert preview["changed"] is True
    assert preview["preview"]["kind"] == "markdown"
    assert source_path.read_text(encoding="utf-8") == before

    apply_response = client.post(
        "/api/source/apply?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": proposed,
            "author": "100001",
            "note": "test apply",
        },
    )

    assert apply_response.status_code == 200
    body = apply_response.json()
    assert body["status"] == "applied"
    assert body["applied"] is True
    assert body["commit_status"] == "committed"
    assert body["commit_hash"] == "src123"
    assert source_path.read_text(encoding="utf-8") == proposed


def test_source_apply_validation_failure_does_not_mutate_or_commit(boi_app_module, monkeypatch):
    commits: list[dict[str, str]] = []
    monkeypatch.setattr(
        boi_app_module,
        "git_commit_for_path",
        lambda path, message: commits.append({"path": str(path), "message": message}) or {"status": "committed", "commit_hash": "bad"},
    )
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")
    source = client.get(f"/api/source?employee_id=100001&path={source_ref}").json()

    response = client.post(
        "/api/source/apply?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": "# Missing frontmatter\n\ninvalid",
            "author": "100001",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "validation_failed"
    assert response.json()["detail"]["fix_suggestions"]
    assert source_path.read_text(encoding="utf-8") == before
    assert commits == []


def test_source_apply_stale_base_does_not_mutate(boi_app_module):
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")

    response = client.post(
        "/api/source/apply?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": "stale",
            "proposed_content": before + "\n<!-- stale test -->\n",
            "author": "100001",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["status"] == "stale_base"
    assert source_path.read_text(encoding="utf-8") == before


def test_source_apply_commit_failure_rolls_back(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "failed", "commit_hash": "", "error": "boom"})
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")
    source = client.get(f"/api/source?employee_id=100001&path={source_ref}").json()

    response = client.post(
        "/api/source/apply?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": before + "\n<!-- rollback test -->\n",
            "author": "100001",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"]["status"] == "commit_failed"
    assert source_path.read_text(encoding="utf-8") == before


def test_draft_edit_api_is_removed(boi_app_module):
    client = TestClient(boi_app_module.app)

    source_response = client.post("/api/source/drafts?employee_id=100001", json={})
    body_response = client.post("/api/docs/boi:public:sop:equipment-abnormal-response/body-drafts?employee_id=100001", json={})

    assert source_response.status_code == 404
    assert body_response.status_code == 404


def test_user_confirmed_public_promotion_publishes_and_hotl_can_hide(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/promotions/submit?employee_id=100001",
        json={
            "target_visibility": "public",
            "title": "User Confirmed Public Promotion Test",
            "description": "사용자 승인 후 즉시 공개되는 promotion 테스트",
            "body": "# Summary\n\n사용자가 확인한 Public promotion 본문입니다.",
            "boi_type": "boi/reference",
            "classification": "internal",
            "tags": ["Promotion", "HOTL"],
            "source_refs": [{"type": "local-private", "ref": "local-note-001"}],
            "source_local_id": "local-note-001",
            "source_sha256": "abc123",
            "user_confirmed": True,
            "reviewer": "hotl-curator",
        },
    )

    assert response.status_code == 200
    body = response.json()
    metadata = body["target"]["metadata"]
    assert body["status"] == "published"
    assert metadata["visibility"] == "public"
    assert metadata["status"] == "reviewed"
    assert metadata["review"]["review_status"] == "user_confirmed"
    assert metadata["hotl"]["status"] == "watching"
    assert metadata["promotion"]["validation_report_id"] == body["promotion_id"]
    assert "commit_status" in body

    listed = client.get("/api/boi?employee_id=100001&q=User Confirmed Public Promotion Test")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    hidden = client.post(
        f"/api/promotions/{body['promotion_id']}/hotl?employee_id=100001",
        json={"status": "hidden", "note": "quality issue"},
    )

    assert hidden.status_code == 200
    assert hidden.json()["hotl"]["status"] == "hidden"
    hidden_list = client.get("/api/boi?employee_id=100001&q=User Confirmed Public Promotion Test")
    assert hidden_list.status_code == 200
    assert hidden_list.json()["count"] == 0
    status = client.get(f"/api/promotions/{body['promotion_id']}?employee_id=100001")
    assert status.status_code == 200
    assert status.json()["hotl"]["status"] == "hidden"


def test_promotion_validation_failure_does_not_publish(boi_app_module):
    client = TestClient(boi_app_module.app)
    public_files_before = sorted((boi_app_module.DATA_ROOT / "public").glob("*.md"))

    response = client.post(
        "/api/promotions/submit?employee_id=100001",
        json={
            "target_visibility": "public",
            "title": "Invalid Public Promotion Secret Test",
            "description": "검증 실패 테스트",
            "body": "# Summary\n\nsecret=sk-abcdefghijklmnop",
            "source_refs": [{"type": "local-private", "ref": "local-secret-note"}],
            "user_confirmed": True,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "validation_failed"
    assert "potential secret token detected" in detail["validation"]["errors"]
    assert sorted((boi_app_module.DATA_ROOT / "public").glob("*.md")) == public_files_before
    listed = client.get("/api/boi?employee_id=100001&q=Invalid Public Promotion Secret Test")
    assert listed.status_code == 200
    assert listed.json()["count"] == 0


def test_public_harness_docs_are_browsable(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=public/harness")

    assert response.status_code == 200
    assert "BoI Agent Harness Overview" in response.text
    assert "SOP Authoring Harness" in response.text
    assert "Action Authoring Harness" in response.text
    assert "Web Validated Editing Guide" in response.text


def test_doc_page_does_not_rescan_docs_for_each_markdown_link(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    repeated_links = "\n".join(
        "- [Trend 확인](/public/actions/api/request-trend-history.md)" for _ in range(8)
    )
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Repeated Link Rendering Test",
            "description": "Repeated OKF links should use the request doc index",
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi-repeated-link-rendering-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "acl_policy": {"agent": "boi-writer-v0.1"},
            "status": "draft",
        },
        "# Summary\n\n" + repeated_links,
    )
    original_find_doc_by_id = boi_app_module.find_doc_by_id
    calls: list[str] = []

    def counted_find_doc_by_id(ref, employee_id=None):
        calls.append(str(ref))
        return original_find_doc_by_id(ref, employee_id)

    monkeypatch.setattr(boi_app_module, "find_doc_by_id", counted_find_doc_by_id)

    response = client.get("/docs/boi-repeated-link-rendering-test?employee_id=100001")

    assert response.status_code == 200
    assert "boi:public:actions:api:request-trend-history" in response.text
    assert len(calls) <= 1


def test_doc_page_renders_okf_media_images_from_media_directory(boi_app_module):
    client = TestClient(boi_app_module.app)
    image_path = boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "_media" / "browser" / "media-render-test.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = tiny_png_bytes()
    image_path.write_bytes(image_bytes)
    digest = hashlib.sha256(image_bytes).hexdigest()
    (boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "_media" / "media-manifest.yaml").write_text(
        "media:\n"
        "  - path: /public/boi-wiki-manual/_media/browser/media-render-test.png\n"
        f"    sha256: {digest}\n"
        "    source_kind: test\n",
        encoding="utf-8",
    )
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/reference",
        "title": "Media Render Test",
        "description": "OKF media render test",
        "tags": ["Media"],
        "timestamp": boi_app_module.now_iso(),
        "boi_id": "boi:public:boi-wiki-manual:media-render-test",
        "visibility": "public",
        "classification": "internal",
        "owner": "AIX 확산 TF",
        "author": {"type": "agent", "agent_id": "test"},
        "acl_policy": "acl:public",
        "status": "reviewed",
        "source_refs": [{"type": "test", "ref": "media-render"}],
        "review": {"reviewer": "test", "review_status": "reviewed"},
    }
    doc_path = boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "media-render-test.md"
    doc_path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n\n# Summary\n\n![Workflow Status 화면](/public/boi-wiki-manual/_media/browser/media-render-test.png)\n",
        encoding="utf-8",
    )
    boi_app_module.invalidate_doc_caches()

    response = client.get("/docs/boi:public:boi-wiki-manual:media-render-test?employee_id=100001")
    media_response = client.get("/okf-media/public/boi-wiki-manual/_media/browser/media-render-test.png")
    blocked_response = client.get("/okf-media/public/boi-wiki-manual/media-render-test.md")

    assert response.status_code == 200
    assert '<figure class="okf-image">' in response.text
    assert 'alt="Workflow Status 화면"' in response.text
    assert "/okf-media/public/boi-wiki-manual/_media/browser/media-render-test.png" in response.text
    assert media_response.status_code == 200
    assert blocked_response.status_code == 404


def test_doc_graph_api_reuses_okf_graph_between_employee_requests(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    boi_app_module._OKF_GRAPH_CACHE.clear()
    boi_app_module._OKF_GRAPH_INDEX_CACHE["signature"] = None
    boi_app_module._OKF_GRAPH_INDEX_CACHE["by_employee"] = {}
    original_okf_graph_for_docs = boi_app_module.okf_graph_for_docs
    calls = 0

    def counted_okf_graph_for_docs(docs, employee_id):
        nonlocal calls
        calls += 1
        return original_okf_graph_for_docs(docs, employee_id)

    monkeypatch.setattr(boi_app_module, "okf_graph_for_docs", counted_okf_graph_for_docs)

    response_one = client.get("/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001")
    response_two = client.get("/api/okf/graph/doc/boi:team:platform:kafka-sop-v0.1?employee_id=100001")

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert calls == 1


def test_api_okf_graph_exposes_markdown_edges_and_backlinks(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/okf/graph?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] > 0
    assert body["edge_count"] > 0
    assert any(node["concept_id"] == "public/sop/equipment-abnormal-response" for node in body["nodes"])
    assert any(
        edge["source"] == "public/sop/equipment-abnormal-response"
        and edge["target"] == "public/actions/api/request-trend-history"
        for edge in body["edges"]
    )
    trend_node = next(node for node in body["nodes"] if node["concept_id"] == "public/actions/api/request-trend-history")
    assert "public/sop/equipment-abnormal-response" in trend_node["backlinks"]


def test_okf_doc_graph_dedupes_repeated_markdown_edges(boi_app_module):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Repeated Graph Link Test",
            "description": "Repeated OKF link graph test",
            "tags": ["Graph"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:graph-dedupe",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "test"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "graph-dedupe"}],
        },
        (
            "# Summary\n\n"
            "[SOP](/public/sop/equipment-abnormal-response.md)\n\n"
            "다시 [SOP](/public/sop/equipment-abnormal-response.md)\n"
        ),
    )

    response = client.get(f"/api/okf/graph/doc/{doc['metadata']['boi_id']}?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    matching = [
        edge
        for edge in body["outgoing"]
        if edge["target"] == "public/sop/equipment-abnormal-response" and edge["label"] == "SOP"
    ]
    assert len(matching) == 1
    assert matching[0]["occurrence_count"] == 2


def test_okf_doc_graph_excludes_action_raw_drilldown_links(boi_app_module):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Raw Link Graph Exclusion Test",
            "description": "Raw action links are operational, not OKF graph edges",
            "tags": ["Graph"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:graph-raw-exclusion",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "test"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "graph-raw"}],
        },
        (
            "# Summary\n\n"
            "[Raw](/actions/raw/action%3Aactions-20990101.jsonl%3A1?employee_id=100001)\n\n"
            "[SOP](/public/sop/equipment-abnormal-response.md)\n"
        ),
    )

    response = client.get(f"/api/okf/graph/doc/{doc['metadata']['boi_id']}?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert any(edge["target"] == "public/sop/equipment-abnormal-response" for edge in body["outgoing"])
    assert all(edge["label"] != "Raw" for edge in body["outgoing"])
    assert all("actions/raw" not in edge["href"] for edge in body["outgoing"])


def test_action_catalog_page_links_public_action_specs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/actions?employee_id=100001&event_type=corrective_action.requested.v1")

    assert response.status_code == 200
    assert "manual.equipment.approve_process_hold" in response.text
    assert "manual handoff" in response.text
    assert "/docs/boi:public:actions:manual:approve-process-hold" in response.text
    assert "/docs/boi:public:actions:api:block-process-progress" in response.text


def test_action_catalog_page_uses_external_boi_url_for_invoke_curl(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    client = TestClient(boi_app_module.app)

    response = client.get(
        "/actions?employee_id=100001&event_type=corrective_action.requested.v1",
        headers={"host": "boi-wiki.example:28000"},
    )

    assert response.status_code == 200
    assert 'curl -X POST "http://boi-wiki.example:28000/api/actions/invoke?employee_id=100001"' in response.text
    assert 'curl -X POST "http://localhost:8000/api/actions/invoke' not in response.text


def test_materialized_equipment_boi_links_sop_and_action_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-equipment-docref-test",
            "event_type": "corrective_action.requested.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "이상 조치 요청 - ETCH-VM-01",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "owner": "100001",
            },
            "source_refs": [{"type": "event", "ref": "evt-source"}],
            "trace_id": "trace-equipment-docref-test",
        },
    )

    assert response.status_code == 200
    body = response.json()["item"]["body"]
    metadata = response.json()["item"]["metadata"]
    assert "[설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)" in body
    assert "[공정 진행 금지 요청](/public/actions/api/block-process-progress.md)" in body
    assert "[Spec / Rule 변경 요청](/public/actions/api/change-spec-rule.md)" in body
    assert "[공정 진행 금지 승인](/public/actions/manual/approve-process-hold.md)" in body
    assert "[Spec / Rule 변경 승인](/public/actions/manual/approve-spec-rule-change.md)" in body
    assert "# Citations" in body
    assert any(rel["type"] == "implements_sop" for rel in metadata["relations"])
    assert any(rel["type"] == "uses_action_spec" for rel in metadata["relations"])

    alarm_response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-equipment-langflow-docref-test",
            "event_type": "equipment.alarm.raised.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "Response Chain 이상 Alarm 발생",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "owner": "100001",
            },
            "source_refs": [{"type": "demo-workflow", "ref": "equipment-anomaly"}],
            "trace_id": "trace-equipment-langflow-docref-test",
        },
    )

    assert alarm_response.status_code == 200
    alarm_body = alarm_response.json()["item"]["body"]
    assert "[Langflow Reference Flow 호출](/public/actions/langflow/reference-flow.md)" in alarm_body


def test_root_cause_generated_boi_is_stage_execution_record_without_architecture_boilerplate(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-root-cause-stage-record",
            "event_type": "root_cause.analysis.requested.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "원인 분석 요청 - ETCH-VM-01",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
                "owner": "100001",
            },
            "source_refs": [{"type": "event", "ref": "evt-detect-stage"}],
            "trace_id": "trace-root-cause-stage-record",
        },
    )

    assert response.status_code == 200
    body = response.json()["item"]["body"]
    assert "# AI Native Workflow Interpretation" not in body
    assert "Event Broker는 업무 시점" not in body
    assert "첨부 SOP 사례를 AI Native Workflow로 실행하기 위한 Private BoI 인스턴스" not in body
    for section in [
        "# Event Snapshot",
        "# SOP Stage",
        "# Evidence / Inputs",
        "# Action Plan",
        "# Manual Handoff",
        "# Next Stage",
        "# Action Results",
        "# Citations",
    ]:
        assert section in body
    assert "[Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)" in body
    assert "[장비 보전 가이드 요청](/public/actions/api/request-maintenance-guide.md)" in body
    assert "[원인 후보 검토 및 판단](/public/actions/manual/review-root-cause.md)" in body
    assert "[장비 보전 가이드 요청](/public/event-types/maintenance.guide.requested.v1.md)" in body
    assert "pending enrichment" in body


def test_generated_boi_enrichment_adds_dispatch_results_and_langflow_analysis(boi_app_module):
    client = TestClient(boi_app_module.app)
    event = {
        "event_id": "evt-enrich-root-cause",
        "event_type": "root_cause.analysis.requested.v1",
        "actor": {"type": "human", "employee_id": "100001"},
        "trace_id": "trace-enrich-root-cause",
        "payload": {
            "title": "원인 분석 요청 - ETCH-VM-01",
            "equipment_id": "ETCH-VM-01",
            "lot_id": "LOT-POC-001",
            "wafer_id": "WF-POC-001",
            "owner": "100001",
        },
    }
    materialized = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json=event,
    )
    boi_id = materialized.json()["item"]["metadata"]["boi_id"]
    long_langflow_message = (
        "# Langflow BoI Execution Result\n\n"
        "## Analysis Draft\n"
        "**Current Finding**\n"
        "ETCH-VM-01 설비에서 RESPONSE_CHAIN_ABNORMAL 알람이 발생하여 원인 분석 단계가 활성화되었습니다.\n\n"
        "**Evidence Used**\n"
        "- Event: root_cause.analysis.requested.v1\n"
        "- SOP Stage: analyze\n"
        "- Prior Action Result: sop.equipment.request_raw_data\n\n"
        "**Recommended Next Check**\n"
        + "\n".join(f"- 상세 점검 항목 {index}: Raw Data와 Trend 근거를 비교합니다." for index in range(1, 35))
        + "\n\n**Manual Handoff**\n"
        "- manual.equipment.review_root_cause 담당자가 최종 원인 후보를 확인합니다.\n\n"
        "**Risk/Approval Notes**\n"
        "- 승인 선행 필요 최종 문장까지 전문이 보존되어야 합니다.\n\n"
        "## BoI Write Result\n"
        "```json\n"
        '{"ok": true, "body": "internal writer result should not be repeated"}\n'
        "```"
    )
    raw_log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-18T00:00:00+09:00",
            "action_key": "langflow.equipment.stage_analysis",
            "request_id": "act-langflow-enrich",
            "employee_id": "100001",
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "trace_id": event["trace_id"],
            "boi_id": boi_id,
            "status": "langflow_invoked",
            "result": {"status": "langflow_invoked", "request_id": "act-langflow-enrich", "message": long_langflow_message},
        },
    )
    dispatch_result = {
        "ok": True,
        "status": "dispatched",
        "boi_id": boi_id,
        "results": [
            {
                "action_key": "sop.equipment.request_raw_data",
                "type": "api",
                "result": {
                    "status": "invoked",
                    "request_id": "act-raw-enrich",
                    "response": {
                        "result": {
                            "raw_data_ref": "/mock/vision-inspection/raw-data/ETCH-VM-01/LOT-POC-001",
                            "source_data_ref": "/mock/quality-system/source-data/ETCH-VM-01",
                            "message": "Raw/Source Data 참조 링크를 생성했습니다.",
                        }
                    },
                },
            },
            {
                "action_key": "langflow.equipment.stage_analysis",
                "type": "langflow_run",
                "result": {
                    "status": "langflow_invoked",
                    "request_id": "act-langflow-enrich",
                    "message": long_langflow_message,
                },
            },
            {
                "action_key": "manual.equipment.review_root_cause",
                "type": "manual_task",
                "result": {
                    "status": "manual_required",
                    "request_id": "act-manual-enrich",
                    "manual_handoff": {"owner": "AIX 확산 TF / 제조 PoC"},
                },
            },
        ],
    }

    response = client.post(
        "/api/boi/enrich-from-dispatch",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"employee_id": "100001", "event": event, "dispatch_result": dispatch_result},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["boi_id"] == boi_id
    assert body["enriched"] is True
    assert "Action Results" in body["sections_updated"]
    doc = boi_app_module.find_doc_by_id(boi_id, "100001")
    assert doc is not None
    enriched_body = doc["body"]
    assert "# Action Results" in enriched_body
    assert "# Analysis Draft" in enriched_body
    assert "/mock/vision-inspection/raw-data/ETCH-VM-01/LOT-POC-001" in enriched_body
    assert "승인 선행 필요 최종 문장까지 전문이 보존되어야 합니다." in enriched_body
    action_results = enriched_body.split("# Analysis Draft", 1)[0]
    assert "# Langflow BoI Execution Result" not in enriched_body
    assert "BoI Write Result" not in enriched_body
    assert "internal writer result should not be repeated" not in enriched_body
    assert "**R |" not in action_results
    assert "승인 선행 필요 최종 문장" not in action_results
    assert "Current Finding: ETCH-VM-01 설비에서 RESPONSE_CHAIN_ABNORMAL 알람이 발생" in action_results
    assert f"/actions/raw/{quote(raw_log_ref, safe='')}?employee_id=100001" in action_results
    assert "Event Broker는 업무 시점을 발행합니다." not in enriched_body
    assert "Team BoI 승격 기준" not in enriched_body
    assert "manual_required" in enriched_body
    assert "pending enrichment" not in enriched_body


def test_enrichment_skips_non_generated_or_non_private_boi(boi_app_module):
    client = TestClient(boi_app_module.app)
    public_doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "Public enrichment target",
            "description": "Should not be enriched",
            "tags": ["Test"],
            "timestamp": "2026-06-18T00:00:00+09:00",
            "boi_id": "boi:public:test:enrichment-skip",
            "visibility": "public",
            "classification": "internal",
            "owner": "AIX",
            "author": {"type": "human", "agent_id": "human"},
            "acl_policy": "acl:public",
            "status": "reviewed",
            "source_event": {"event_id": "evt-public-skip", "event_type": "root_cause.analysis.requested.v1"},
            "source_refs": [{"type": "test", "ref": "enrichment-skip"}],
            "review": {"reviewer": "tf-lead", "review_status": "reviewed"},
        },
        "# Summary\n\nOriginal public content",
    )

    response = client.post(
        "/api/boi/enrich-from-dispatch",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "employee_id": "100001",
            "event": {"event_id": "evt-public-skip", "event_type": "root_cause.analysis.requested.v1", "trace_id": "trace-public-skip"},
            "dispatch_result": {"boi_id": public_doc["metadata"]["boi_id"], "results": []},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["enriched"] is False
    assert body["skipped_reason"] == "not_generated_private_boi"


def test_equipment_demo_status_summarizes_trace_context(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-test"

    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-status-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "상태 조회 테스트"},
        },
    )
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "상태 조회 테스트"},
        },
        result={"boi_id": "boi-status-test", "boi_uri": "/private/100001/boi-status-test.md"},
    )

    response = client.get(f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == trace_id
    assert body["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert body["sop_uri"] == "/public/sop/equipment-abnormal-response.md"
    assert any(item["event_type"] == "equipment.alarm.raised.v1" for item in body["events"])
    assert "langflow.boi.reference_flow" in body["expected_actions"]
    assert "manual.equipment.confirm_alarm_context" in body["manual_handoffs"]
    assert "manual.equipment.confirm_alarm_context" in body["expected_manual_actions"]
    assert body["generated_boi_refs"] == body["generated_docs"]
    assert "relation_graph" in body
    assert body["relation_graph"]["node_count"] < 50


def test_workflow_status_reads_trace_logs_without_full_jsonl_caches(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-streaming-actions"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-streaming-actions",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "직개발 결과 확인"},
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-21T12:00:00+09:00",
            "action_key": "direct_development.quality_response_trend.simulate",
            "request_id": "act-status-streaming-actions",
            "employee_id": "100001",
            "event_id": "evt-status-streaming-actions",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "status": "langflow_invoked",
            "connector_kind": "langflow",
            "coverage_score": 1.0,
        },
    )

    def fail_full_event_cache():
        raise AssertionError("workflow status should stream trace event logs instead of loading the full event cache")

    def fail_full_action_cache():
        raise AssertionError("workflow status should stream trace action logs instead of loading the full action cache")

    monkeypatch.setattr(boi_app_module, "cached_event_log_rows", fail_full_event_cache)
    monkeypatch.setattr(boi_app_module, "cached_action_log_rows", fail_full_action_cache)

    response = client.get(f"/api/workflows/direct-development-reporting/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert response.status_code == 200
    body = response.json()
    assert any(row["action_key"] == "direct_development.quality_response_trend.simulate" for row in body["actions"])


def test_workflow_status_compact_omits_large_results_but_keeps_simulation_fields(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-compact-actions"
    large_message = "Response Trend evidence " + ("x" * 5000)
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-compact-actions",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "직개발 결과 확인"},
        },
        result={"dispatch_result": {"response": {"item": {"body": "large raw dispatch payload"}}}},
    )
    append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-21T12:00:00+09:00",
            "action_key": "direct_development.quality_response_trend.simulate",
            "request_id": "act-status-compact-actions",
            "employee_id": "100001",
            "event_id": "evt-status-compact-actions",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "status": "langflow_invoked",
            "connector_kind": "langflow",
            "result": {
                "status": "langflow_invoked",
                "simulation": True,
                "coverage_score": 1.0,
                "message": large_message,
                "response": {"huge": "raw-result-should-not-be-returned"},
                "simulation_agent": {
                    "coverage_report": {"coverage_score": 1.0, "missing_context": []},
                    "context_pack": {"documents": [{"ref": "/public/sop/direct-development-reporting.md"}]},
                    "evidence_packets": [{"name": "Response Trend", "provenance": "simulated_prerequisite"}],
                },
            },
        },
    )

    response = client.get(
        f"/api/workflows/direct-development-reporting/status?employee_id=100001&trace_id={trace_id}&format=json&compact=true"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["compact"] is True
    assert body["relation_graph"]["omitted"].startswith("compact workflow status")
    rendered = json.dumps(body, ensure_ascii=False)
    assert "raw-result-should-not-be-returned" not in rendered
    assert len(rendered) < 20000
    action = next(row for row in body["actions"] if row["action_key"] == "direct_development.quality_response_trend.simulate")
    assert action["simulation"] is True
    assert action["coverage_score"] == 1.0
    assert action["result"]["message"].endswith("...")
    assert action["evidence_packets"][0]["provenance"] == "simulated_prerequisite"


def test_generic_workflow_status_uses_sop_stage_registry(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-generic-workflow-registry"

    response = client.get(f"/api/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_key"] == "equipment-anomaly"
    assert body["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    stages = body["expected_stages"]
    assert [stage["sop_stage_id"] for stage in stages] == ["detect", "analyze", "guide", "correct"]
    assert stages[0]["event_types"] == ["equipment.alarm.raised.v1", "trend.anomaly.detected.v1"]
    assert sum(1 for stage in stages if stage["stage"] == "원인 분석") == 1
    assert "langflow.equipment.stage_analysis" in body["expected_actions"]
    assert "manual.equipment.review_root_cause" in body["expected_manual_actions"]
    assert body["status_page_url"].startswith("/workflows/equipment-anomaly/status?")


def test_direct_development_workflow_registry_exposes_simulated_actions(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-direct-development-registry"

    response = client.get(f"/api/workflows/direct-development-reporting/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_key"] == "direct-development-reporting"
    assert body["sop_ref"] == "boi:public:sop:direct-development-reporting"
    assert [stage["sop_stage_id"] for stage in body["expected_stages"]] == [
        "response_trend",
        "map_view",
        "cross_section_decision",
        "cross_section_execution",
        "fab_trend_compare",
        "reporting",
        "share",
    ]
    assert "direct_development.quality_response_trend.simulate" in body["expected_actions"]
    assert "manual.direct_development.decide_cross_section" in body["expected_manual_actions"]
    action_details = {row["action_key"]: row for row in body["action_details"]}
    assert action_details["direct_development.quality_response_trend.simulate"]["simulation"] is True
    assert action_details["direct_development.quality_response_trend.simulate"]["simulation_label"] == "SIMULATED"
    assert action_details["direct_development.quality_response_trend.simulate"]["real_system_status"] == "unavailable"


def test_generic_workflow_start_publishes_sop_entry_event(boi_app_module):
    client = TestClient(boi_app_module.app)

    unconfirmed = client.post(
        "/api/workflows/equipment-anomaly/start?employee_id=100001",
        json={
            "payload": {
                "title": "Generic workflow start",
                "equipment_id": "ETCH-VM-01",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            }
        },
    )

    assert unconfirmed.status_code == 400
    assert "user_confirmed=true" in str(unconfirmed.json()["detail"])

    response = client.post(
        "/api/workflows/equipment-anomaly/start?employee_id=100001",
        json={
            "user_confirmed": True,
            "payload": {
                "title": "Generic workflow start",
                "equipment_id": "ETCH-VM-01",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["workflow"]["workflow_key"] == "equipment-anomaly"
    assert body["workflow"]["first_event_type"] == "equipment.alarm.raised.v1"
    assert body["workflow"]["status_page_url"].startswith("/workflows/equipment-anomaly/status?")
    assert body["event"]["event_type"] == "equipment.alarm.raised.v1"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["event"]["payload"]["equipment_id"] == "ETCH-VM-01"
    assert "user_confirmed" not in boi_app_module.AIOKafkaProducer.sent_events[-1]["event"]["payload"]


def test_demo_workflow_start_requires_user_confirmation(boi_app_module):
    client = TestClient(boi_app_module.app)

    unconfirmed = client.post("/api/workflows/demo/equipment-anomaly/start?employee_id=100001", json={})

    assert unconfirmed.status_code == 400
    assert "user_confirmed=true" in str(unconfirmed.json()["detail"])

    confirmed = client.post(
        "/api/workflows/demo/equipment-anomaly/start?employee_id=100001",
        json={"user_confirmed": True, "equipment_id": "ETCH-VM-01", "alarm_code": "RESPONSE_CHAIN_ABNORMAL"},
    )

    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["ok"] is True
    assert body["workflow"]["workflow_key"] == "equipment-anomaly"


def test_generic_workflow_status_page_groups_multiple_events_in_sop_stage(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-sop-stage-grouping"
    for event_id, event_type, title in [
        ("evt-stage-group-alarm", "equipment.alarm.raised.v1", "Alarm 발생"),
        ("evt-stage-group-trend", "trend.anomaly.detected.v1", "Trend 이상"),
        ("evt-stage-group-root", "root_cause.analysis.requested.v1", "원인 분석 요청"),
    ]:
        boi_app_module.append_event_log(
            status="handled",
            event={
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "payload": {"title": title},
            },
            result={"dispatch_result": {"ok": True, "status": "handled", "results": []}},
        )

    response = client.get(f"/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert response.text.count('class="workflow-stage-row"') == 4
    assert "equipment.alarm.raised.v1" in response.text
    assert "trend.anomaly.detected.v1" in response.text
    assert response.text.count("<h3>원인 분석</h3>") == 1
    assert response.text.index("trend.anomaly.detected.v1") < response.text.index("<h3>원인 분석</h3>")


def test_custom_sop_event_materializes_workflow_boi_without_equipment_prefix(boi_app_module, tmp_path):
    client = TestClient(boi_app_module.app)
    custom_sop = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/sop",
            "title": "Custom Ops SOP",
            "description": "Generic workflow registry fixture",
            "tags": ["SOP", "Workflow"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:public:sop:custom-ops",
            "visibility": "public",
            "classification": "internal",
            "owner": "workflow-team",
            "author": {"type": "human", "agent_id": "test"},
            "acl_policy": "acl:public",
            "status": "reviewed",
            "source_refs": [{"type": "test", "ref": "custom-sop"}],
            "review": {"reviewer": "test", "review_status": "reviewed"},
            "workflow": {
                "workflow_key": "custom-ops",
                "stages": [
                    {
                        "id": "triage",
                        "name": "Triage",
                        "entry_event": "custom.case.opened.v1",
                        "event_types": ["custom.case.opened.v1"],
                        "automated_actions": [],
                        "manual_actions": [],
                        "outputs": ["triage note"],
                    }
                ],
            },
        },
        "# Summary\n\nCustom workflow SOP",
    )
    catalog_root = tmp_path / "event_catalog"
    catalog_root.mkdir()
    (catalog_root / "event_types.yaml").write_text(
        yaml.safe_dump(
            {
                "event_types": [
                    {
                        "event_type": "custom.case.opened.v1",
                        "name_ko": "Custom Case Opened",
                        "default_boi_type": "boi/workflow-instance",
                        "default_flow_key": "custom-flow",
                        "workflow_stage": "Triage",
                        "sop_ref": custom_sop["metadata"]["boi_id"],
                        "sop_stage_id": "triage",
                        "recommended_actions": [],
                        "recommended_manual_actions": [],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    boi_app_module.EVENT_CATALOG_ROOT = catalog_root
    boi_app_module._EVENT_TYPES_CACHE["signature"] = None
    boi_app_module._EVENT_TYPES_CACHE["items"] = []
    boi_app_module._FILE_SIGNATURE_CACHE.clear()

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-custom-case-opened",
            "event_type": "custom.case.opened.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {"title": "Custom case opened", "case_id": "CASE-001", "owner": "100001"},
            "trace_id": "trace-custom-case-opened",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["metadata"]["sop_ref"] == "boi:public:sop:custom-ops"
    assert item["metadata"]["sop_stage_id"] == "triage"
    assert "# SOP Stage" in item["body"]
    assert "Custom workflow SOP" not in item["body"]
    assert f"[Custom Ops SOP]({custom_sop['uri']})" in item["body"]
    assert "CASE-001" in item["body"]


def test_equipment_demo_status_renders_human_readable_html_for_browsers(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-html-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-html-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "HTML 상태 조회 테스트"},
        },
        result={
            "boi_id": "boi:private:100001:status-html-test",
            "boi_uri": "/private/100001/status-html-test.md",
            "dispatch_result": {
                "ok": True,
                "status": "handled",
                "results": [
                    {
                        "action_key": "langflow.boi.reference_flow",
                        "result": {
                            "status": "invoked",
                            "request_id": "act-status-html-test",
                            "doc_ref": "boi:public:actions:langflow:reference-flow",
                            "response": {
                                "item": {
                                    "metadata": {"boi_id": "boi:private:100001:status-html-test"},
                                    "body": "INLINE_RAW_BODY_SHOULD_NOT_RENDER",
                                }
                            },
                        },
                    }
                ],
            },
        },
    )
    html_route = client.get(f"/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")
    api_accept_html = client.get(
        f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}",
        headers={"accept": "text/html,application/xhtml+xml"},
    )
    api_json = client.get(f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert html_route.status_code == 200
    assert html_route.headers["content-type"].startswith("text/html")
    assert api_accept_html.status_code == 200
    assert api_accept_html.headers["content-type"].startswith("text/html")
    assert api_json.status_code == 200
    assert api_json.headers["content-type"].startswith("application/json")
    for text in (html_route.text, api_accept_html.text):
        assert "Workflow Status" in text
        assert "Timeline" in text
        assert "Actions" in text
        assert "Manual Handoffs" in text
        assert "Generated BoIs" in text
        assert "Trace Graph" in text
        assert "Raw JSON 불러오기" in text
        assert "INLINE_RAW_BODY_SHOULD_NOT_RENDER" not in text
        assert '"edges"' not in text


def test_direct_development_workflow_status_and_raw_pages_mark_simulated_actions(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-direct-development-simulated"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-direct-simulated",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
        },
        result={"boi_id": "boi:private:100001:direct-development-simulated", "boi_uri": "/private/100001/direct-development-simulated.md"},
    )
    log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-21T10:00:00+09:00",
            "action_key": "direct_development.quality_response_trend.simulate",
            "request_id": "act-direct-simulated",
            "employee_id": "100001",
            "event_id": "evt-direct-simulated",
            "event_type": "direct_development.result_check.requested.v1",
            "trace_id": trace_id,
            "status": "langflow_invoked",
            "connector_kind": "langflow",
            "doc_ref": "boi:public:actions:langflow:direct-development-quality-response-trend-simulate",
            "simulation": True,
            "simulation_label": "SIMULATED",
            "simulation_notice": "SIMULATED: 실제 품질 시스템 호출이 아니라 BoI Universal Action Simulator Flow가 생성한 PoC 결과입니다.",
            "real_system_status": "unavailable",
            "real_system_connected": False,
            "simulated_system": "품질 시스템",
            "retrieval_rounds": 3,
            "coverage_score": 1.0,
            "used_docs": [
                {
                    "role": "action_spec",
                    "title": "Response Trend 확인 시뮬레이션",
                    "boi_id": "boi:public:actions:langflow:direct-development-quality-response-trend-simulate",
                    "uri": "/public/actions/langflow/direct-development-quality-response-trend-simulate.md",
                    "match_reason": "exact_ref",
                }
            ],
            "result": {
                "status": "langflow_invoked",
                "message": "SIMULATED Response Trend 확인 결과",
                "simulation": True,
                "simulation_label": "SIMULATED",
                "real_system_connected": False,
                "simulated_system": "품질 시스템",
                "retrieval_rounds": 3,
                "coverage_score": 1.0,
                "simulation_agent": {
                    "agent": {"name": "BoI Simulation Agent", "retrieval_rounds": 3},
                    "coverage_report": {"coverage_score": 1.0, "missing_context": []},
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
                    "retrieval_trace": [{"round": 1, "objective": "Resolve exact references."}],
                    "simulation_result": {
                        "markdown": "# SIMULATED BoI Wiki Simulation Result\n\n## Current Finding\nAgent rendered result",
                    },
                },
            },
        },
    )
    encoded = quote(log_ref, safe="")

    status = client.get(f"/workflows/direct-development-reporting/status?employee_id=100001&trace_id={trace_id}")
    raw = client.get(f"/actions/raw/{encoded}?employee_id=100001")

    assert status.status_code == 200
    assert "SIMULATED" in status.text
    assert "품질 시스템" in status.text
    assert "실제 시스템 호출" in status.text
    assert "BoI Simulation Agent" in status.text
    assert "coverage=1.0" in status.text
    assert raw.status_code == 200
    assert "SIMULATED" in raw.text
    assert "BoI Simulation Agent" in raw.text
    assert "Agent rendered result" in raw.text
    assert "실제 시스템 호출" in raw.text


def test_universal_simulation_agent_builds_context_from_action_event_and_sop(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/simulations/universal-agent",
        headers={"x-service-token": "dev-service-token-change-me"},
        json={
            "action_key": "direct_development.quality_response_trend.simulate",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-agent-context",
                "event_type": "direct_development.result_check.requested.v1",
                "trace_id": "trace-agent-context",
                "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
            },
            "payload": {"title": "직개발 결과 확인", "tech": "Tech-A", "work_id": "1.10"},
            "prior_results": [{"action_key": "boi.materialize.event", "status": "materialized", "summary": "BoI generated"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["simulation"] is True
    assert body["agent"]["name"] == "BoI Simulation Agent"
    assert body["agent"]["strategy"] == "bounded-tool-loop"
    assert 1 <= body["agent"]["retrieval_rounds"] <= 4
    assert 1 <= body["agent"]["agent_iterations"] <= 5
    assert body["tool_calls"]
    assert any(call["tool"] == "action_spec_lookup" for call in body["tool_calls"])
    assert any(call["tool"] == "coverage_evaluator" for call in body["tool_calls"])
    assert body["coverage_report"]["covered"]["action_contract"] is True
    assert body["coverage_report"]["covered"]["expected_output_schema"] is True
    assert body["coverage_report"]["covered"]["prior_evidence"] is True
    assert body["simulation_result"]["status"] == "simulated"
    assert "SIMULATED" in body["simulation_result"]["markdown"]
    refs = {item["ref"] for item in body["citations"]}
    assert "boi:public:actions:langflow:direct-development-quality-response-trend-simulate" in refs
    assert any("direct_development.result_check.requested.v1" in item["uri"] for item in body["citations"])


def test_universal_simulation_agent_generates_quality_system_response_trend_evidence(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/simulations/universal-agent",
        headers={"x-service-token": "dev-service-token-change-me"},
        json={
            "action_key": "sop.equipment.request_trend_history",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-equipment-quality-system",
                "event_type": "equipment.alarm.raised.v1",
                "trace_id": "trace-equipment-quality-system",
                "payload": {"title": "이상 감지", "equipment_id": "ETCH-VM-01", "lot_id": "LOT-001"},
            },
            "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"},
            "simulation_depth": "stage_prerequisites",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["coverage_report"]["coverage_score"] >= 0.85
    assert body["coverage_report"]["passed"] is True
    assert "trend_status" not in body["coverage_report"]["missing_context"]
    packets = {packet["evidence_key"]: packet for packet in body["evidence_packets"]}
    assert packets["quality_system_response_trend"]["provenance"] == "simulated_prerequisite"
    assert packets["quality_system_response_trend"]["fields"]["source_system"] == "quality_system"
    assert packets["quality_system_response_trend"]["fields"]["trend_status"]
    assert body["simulation_result"]["generated_result"]["real_system_connected"] is False
    assert "품질 시스템" in body["simulation_result"]["markdown"]
    assert "SIMULATED Evidence Packets" in body["simulation_result"]["markdown"]


def test_universal_simulation_agent_generates_manual_prerequisite_evidence_without_prior_logs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/simulations/universal-agent",
        headers={"x-service-token": "dev-service-token-change-me"},
        json={
            "action_key": "manual.direct_development.decide_cross_section",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-agent-manual-no-prior",
                "event_type": "direct_development.cross_section.decision_required.v1",
                "trace_id": "trace-agent-manual-no-prior",
                "payload": {"title": "단면검사 판단", "tech": "Tech-A", "work_id": "1.10", "owner": "100001"},
            },
            "payload": {"title": "단면검사 판단", "tech": "Tech-A", "work_id": "1.10", "owner": "100001"},
            "simulation_depth": "stage_prerequisites",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["coverage_report"]["coverage_score"] >= 0.85
    assert body["coverage_report"]["passed"] is True
    assert "trend_status" not in body["coverage_report"]["missing_context"]
    assert "map_pattern_summary" not in body["coverage_report"]["missing_context"]
    packets = {packet["evidence_key"]: packet for packet in body["evidence_packets"]}
    assert packets["response_trend"]["provenance"] == "simulated_prerequisite"
    assert packets["map_view"]["provenance"] == "simulated_prerequisite"
    assert packets["cross_section_decision_rule"]["fields"]["next_event"] == "direct_development.cross_section.requested.v1"
    assert "SIMULATED Evidence Packets" in body["simulation_result"]["markdown"]
    assert "Response Trend" in body["simulation_result"]["markdown"]
    assert "Map View" in body["simulation_result"]["markdown"]


def test_universal_simulation_agent_reuses_trace_prior_logs_for_manual_decision(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-agent-manual-prior"
    append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-21T12:00:00+09:00",
            "action_key": "direct_development.quality_response_trend.simulate",
            "request_id": "act-trend-prior",
            "employee_id": "100001",
            "trace_id": trace_id,
            "status": "langflow_invoked",
            "doc_ref": "boi:public:actions:langflow:direct-development-quality-response-trend-simulate",
            "simulation": True,
            "result": {
                "status": "langflow_invoked",
                "simulation": True,
                "evidence_packets": [
                    {
                        "evidence_key": "response_trend",
                        "title": "Response Trend evidence",
                        "action_key": "direct_development.quality_response_trend.simulate",
                        "provenance": "real_log",
                        "simulation": True,
                        "fields": {"trend_status": "simulated_prior_trend_status"},
                    }
                ],
            },
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-21T12:01:00+09:00",
            "action_key": "direct_development.map_view.simulate",
            "request_id": "act-map-prior",
            "employee_id": "100001",
            "trace_id": trace_id,
            "status": "langflow_invoked",
            "doc_ref": "boi:public:actions:langflow:direct-development-map-view-simulate",
            "simulation": True,
            "result": {
                "status": "langflow_invoked",
                "simulation": True,
                "evidence_packets": [
                    {
                        "evidence_key": "map_view",
                        "title": "Map View evidence",
                        "action_key": "direct_development.map_view.simulate",
                        "provenance": "real_log",
                        "simulation": True,
                        "fields": {"map_pattern_summary": "simulated_prior_map_pattern"},
                    }
                ],
            },
        },
    )

    response = client.post(
        "/api/simulations/universal-agent",
        headers={"x-service-token": "dev-service-token-change-me"},
        json={
            "action_key": "manual.direct_development.decide_cross_section",
            "employee_id": "100001",
            "event": {
                "event_id": "evt-agent-manual-prior",
                "event_type": "direct_development.cross_section.decision_required.v1",
                "trace_id": trace_id,
                "payload": {"title": "단면검사 판단", "tech": "Tech-A", "work_id": "1.10", "owner": "100001"},
            },
            "payload": {"title": "단면검사 판단", "tech": "Tech-A", "work_id": "1.10", "owner": "100001"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    packets = {packet["evidence_key"]: packet for packet in body["evidence_packets"]}
    assert body["coverage_report"]["coverage_score"] >= 0.85
    assert packets["response_trend"]["provenance"] == "real_log"
    assert packets["response_trend"]["fields"]["trend_status"] == "simulated_prior_trend_status"
    assert packets["map_view"]["provenance"] == "real_log"
    assert packets["map_view"]["fields"]["map_pattern_summary"] == "simulated_prior_map_pattern"


def test_workflow_status_links_action_raw_ids_and_dedupes_generated_bois(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-workflow-raw-links"
    boi_id = "boi:private:100001:workflow:raw-links"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/analysis",
            "title": "Workflow Raw Links BoI",
            "description": "Workflow raw link target",
            "tags": ["Workflow"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "boi-writer-v0.4"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_event": {"event_id": "evt-workflow-raw-links", "event_type": "root_cause.analysis.requested.v1", "trace_id": trace_id},
        },
        "# Summary\n\nWorkflow raw link target",
    )
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "Workflow Raw Link 이벤트"},
        },
        result={"boi_id": boi_id, "boi_uri": "/private/100001/workflow-raw-links.md"},
    )
    boi_app_module.append_event_log(
        status="enriched",
        event={
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "Workflow Raw Link 이벤트"},
        },
        result={"boi_id": boi_id, "boi_uri": "/private/100001/workflow-raw-links.md"},
    )
    log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-18T13:10:00+09:00",
            "action_key": "langflow.equipment.stage_analysis",
            "request_id": "act-workflow-raw-links",
            "employee_id": "100001",
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "boi_id": boi_id,
            "status": "langflow_invoked",
            "connector_kind": "langflow",
            "doc_ref": "boi:public:actions:langflow:stage-analysis",
            "result": {"message": "ROW_LEVEL_RAW_MARKER"},
        },
    )
    encoded = quote(log_ref, safe="")

    response = client.get(f"/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert f"/actions/raw/{encoded}?employee_id=100001" in response.text
    assert f"/api/actions/raw/{encoded}?employee_id=100001" in response.text
    assert "/events?employee_id=100001&amp;event_id=evt-workflow-raw-links" in response.text
    assert f"/events?employee_id=100001&amp;trace_id={trace_id}" in response.text
    assert f"/docs/{boi_id}?employee_id=100001" in response.text
    assert "act-workflow-raw-links" in response.text
    assert response.text.count('<span class="badge private">BoI</span>') == 1
    assert "ROW_LEVEL_RAW_MARKER" not in response.text


def test_workflow_status_raw_endpoint_returns_lazy_sections(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-raw-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-raw-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "Raw status 테스트"},
        },
        result={"raw_status_marker": "STATUS_RAW_MARKER"},
    )

    events = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=events")
    generic_events = client.get(f"/api/workflows/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=events")
    graph = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=graph")
    missing_section = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=nope")

    assert events.status_code == 200
    assert events.json()["section"] == "events"
    assert events.json()["data"][0]["result"]["raw_status_marker"] == "STATUS_RAW_MARKER"
    assert generic_events.status_code == 200
    assert generic_events.json()["workflow_key"] == "equipment-anomaly"
    assert graph.status_code == 200
    assert graph.json()["section"] == "graph"
    assert "nodes" in graph.json()["data"]
    assert missing_section.status_code == 422


def test_events_page_links_to_workflow_status_html_route(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-link-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-link-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "Status 링크 테스트"},
        },
        result={"dispatch_result": {"ok": True, "status": "handled", "results": []}},
    )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert f"/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}" in response.text
    assert f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}" not in response.text


def test_poc_equipment_api_endpoints_are_service_token_protected_and_callable(boi_app_module):
    client = TestClient(boi_app_module.app)

    unauthorized = client.post(
        "/api/poc/equipment/trend-history",
        json={"payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"}},
    )
    assert unauthorized.status_code == 401

    response = client.post(
        "/api/poc/equipment/trend-history",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "invoked"
    assert body["result"]["trend_status"] == "anomaly_detected"
    assert body["result"]["lot_history_ref"].endswith("/LOT-001")


def test_poc_high_risk_api_requires_human_approval_even_if_called_directly(boi_app_module):
    client = TestClient(boi_app_module.app)

    rejected = client.post(
        "/api/poc/equipment/process-hold",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01"}, "dry_run": False},
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"]["status"] == "approval_required"

    approved = client.post(
        "/api/poc/equipment/process-hold",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01"}, "dry_run": False, "approved_by": "line-manager-001"},
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "invoked"
    assert approved.json()["result"]["approved_by"] == "line-manager-001"


def test_poc_mcp_call_searches_accessible_boi_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/poc/mcp/call",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi.search",
            "arguments": {"query": "Kafka", "employee_id": "100001", "allowed_visibility": ["public", "team", "private"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "mcp_invoked"
    assert body["tool"] == "boi.search"
    assert any("Kafka" in item["title"] for item in body["results"])


def test_event_type_detail_page_explains_empty_boi_state_and_links_specs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/event-types/meeting.closed.v1?employee_id=100001")

    assert response.status_code == 200
    assert "회의 종료" in response.text
    assert "meeting.closed.v1" in response.text
    assert "아직 이 Event Type으로 생성된 BoI가 없습니다" in response.text
    assert "/events?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "/actions?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "python scripts/publish_event.py meeting.closed.v1 --employee 100001" in response.text
    assert "boi:public:actions:boi-writer:materialize-event" in response.text


def test_event_type_catalog_uses_detail_route_as_primary_cta(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/event-types?employee_id=100001")

    assert response.status_code == 200
    assert 'href="/event-types/meeting.closed.v1?employee_id=100001"' in response.text
    assert "Event Type 상세" in response.text


def test_index_event_type_filter_has_context_bar_and_specific_empty_state(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&event_type=meeting.closed.v1")

    assert response.status_code == 200
    assert 'class="event-context-bar"' in response.text
    assert "회의 종료" in response.text
    assert "/event-types/meeting.closed.v1?employee_id=100001" in response.text
    assert "/events?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "아직 이 Event Type으로 생성된 BoI가 없습니다" in response.text


def test_events_page_summarizes_dispatch_results_and_keeps_raw_json_collapsed(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-compact-render-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-compact-render-test",
            "event_type": "maintenance.guide.requested.v1",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "컴팩트 렌더링 테스트"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {
                "ok": True,
                "status": "dispatched",
                "boi_id": "boi:private:100001:compact:test",
                "results": [
                    {
                        "action_key": "boi.materialize_event",
                        "type": "boi_materialize",
                        "result": {
                            "status": "materialized",
                            "request_id": "act-1",
                            "response": {
                                "item": {
                                    "metadata": recovered_metadata("boi:private:100001:compact:test"),
                                    "uri": "/private/100001/compact-test.md",
                                    "body": "# Should stay inside raw JSON only",
                                }
                            },
                        },
                    },
                    {
                        "action_key": "sop.equipment.block_process_progress",
                        "type": "api",
                        "result": {"status": "approval_required", "request_id": "act-2", "doc_ref": "boi:public:actions:api:block-process-progress"},
                    },
                ],
            },
        },
    )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert 'class="action-summary-table"' in response.text
    assert "boi.materialize_event" in response.text
    assert "approval_required" in response.text
    assert "/docs/boi:private:100001:compact:test?employee_id=100001" in response.text
    assert 'class="raw-event-json"' in response.text
    assert "Should stay inside raw JSON only" not in response.text.split('class="raw-event-json"')[0]


def test_api_event_logs_can_filter_by_trace_id(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-trace-a", "event_type": "meeting.closed.v1", "trace_id": "trace-a", "payload": {"title": "A"}},
    )
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-trace-b", "event_type": "meeting.closed.v1", "trace_id": "trace-b", "payload": {"title": "B"}},
    )

    response = client.get("/api/events/log?trace_id=trace-a")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["event_id"] == "evt-trace-a"


def test_events_page_and_api_can_filter_by_event_id(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-filter-target", "event_type": "meeting.closed.v1", "trace_id": "trace-filter-target", "payload": {"title": "Target Event"}},
    )
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-filter-other", "event_type": "meeting.closed.v1", "trace_id": "trace-filter-other", "payload": {"title": "Other Event"}},
    )

    api_response = client.get("/api/events/log?event_id=evt-filter-target")
    html_response = client.get("/events?employee_id=100001&event_id=evt-filter-target")

    assert api_response.status_code == 200
    assert api_response.json()["count"] == 1
    assert api_response.json()["items"][0]["event_id"] == "evt-filter-target"
    assert html_response.status_code == 200
    assert "Target Event" in html_response.text
    assert "Other Event" not in html_response.text
    assert "/events?employee_id=100001&amp;event_id=evt-filter-target" in html_response.text


def test_event_logs_filter_by_time_range_in_api_and_html(boi_app_module):
    client = TestClient(boi_app_module.app)
    event_type = "time.range.test.v1"
    for event_id, logged_at, title in [
        ("evt-time-old", "2026-06-19T08:30:00+09:00", "Old Event"),
        ("evt-time-target", "2026-06-19T10:15:00+09:00", "Target Time Event"),
        ("evt-time-future", "2026-06-19T18:30:00+09:00", "Future Event"),
    ]:
        append_event_log_row(
            boi_app_module,
            {
                "logged_at": logged_at,
                "status": "published",
                "event_id": event_id,
                "event_type": event_type,
                "producer": "pytest",
                "trace_id": f"trace-{event_id}",
                "payload_title": title,
            },
            filename="events-20990102.jsonl",
        )

    api_response = client.get(
        f"/api/events/log?event_type={event_type}&from_time=2026-06-19T09:00&to_time=2026-06-19T18:00"
    )
    html_response = client.get(
        f"/events?employee_id=100001&event_type={event_type}&from_time=2026-06-19T09:00&to_time=2026-06-19T18:00"
    )

    assert api_response.status_code == 200
    body = api_response.json()
    assert body["count"] == 1
    assert body["items"][0]["event_id"] == "evt-time-target"
    assert body["time_filter"]["active"] is True
    assert html_response.status_code == 200
    assert "Target Time Event" in html_response.text
    assert "Old Event" not in html_response.text
    assert "Future Event" not in html_response.text
    assert 'name="from_time"' in html_response.text
    assert 'name="to_time"' in html_response.text
    assert "시간 범위" in html_response.text


def test_event_stream_time_preset_preserves_pagination_url(boi_app_module):
    client = TestClient(boi_app_module.app)
    event_type = "time.preset.test.v1"
    for index in range(2):
        append_event_log_row(
            boi_app_module,
            {
                "logged_at": boi_app_module.now_iso(),
                "status": "published",
                "event_id": f"evt-time-preset-{index}",
                "event_type": event_type,
                "producer": "pytest",
                "trace_id": f"trace-time-preset-{index}",
                "payload_title": f"Preset Event {index}",
            },
            filename="events-20990103.jsonl",
        )
    append_event_log_row(
        boi_app_module,
        {
            "logged_at": "2000-01-01T00:00:00+09:00",
            "status": "published",
            "event_id": "evt-time-preset-old",
            "event_type": event_type,
            "producer": "pytest",
            "trace_id": "trace-time-preset-old",
            "payload_title": "Preset Old Event",
        },
        filename="events-20990103.jsonl",
    )

    api_response = client.get(f"/api/events/log?event_type={event_type}&time_preset=24h")
    html_response = client.get(f"/events?employee_id=100001&event_type={event_type}&time_preset=24h&limit=1")

    assert api_response.status_code == 200
    body = api_response.json()
    assert body["total"] == 2
    assert body["time_filter"]["time_preset"] == "24h"
    assert html_response.status_code == 200
    assert "최근 24시간" in html_response.text
    assert "Preset Old Event" not in html_response.text
    assert "time_preset=24h" in html_response.text
    assert "Next" in html_response.text


def test_event_stream_time_filter_errors_are_not_500s(boi_app_module):
    client = TestClient(boi_app_module.app)

    invalid_api = client.get("/api/events/log?from_time=not-a-time")
    reversed_api = client.get("/api/events/log?from_time=2026-06-19T18:00&to_time=2026-06-19T09:00")
    invalid_html = client.get("/events?employee_id=100001&from_time=not-a-time")

    assert invalid_api.status_code == 400
    assert reversed_api.status_code == 400
    assert invalid_html.status_code == 200
    assert "시간 필터 오류" in invalid_html.text
    assert "시간 필터를 적용할 수 없습니다." in invalid_html.text


def test_home_recent_event_stream_links_to_trace_and_filters_by_event_type(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-home-meeting",
            "event_type": "meeting.closed.v1",
            "trace_id": "trace-home-meeting",
            "producer": "pytest",
            "payload": {"title": "Home Meeting Event"},
        },
    )
    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-home-report",
            "event_type": "report.requested.v1",
            "trace_id": "trace-home-report",
            "producer": "pytest",
            "payload": {"title": "Home Report Event"},
        },
    )

    response = client.get("/?employee_id=100003&event_type=meeting.closed.v1")

    assert response.status_code == 200
    assert "Recent Event Stream" in response.text
    assert "Home Meeting Event" in response.text
    assert "Home Report Event" not in response.text
    assert "/events?employee_id=100003&amp;trace_id=trace-home-meeting" in response.text
    assert "/events?employee_id=100003&amp;event_id=evt-home-meeting" in response.text
    assert "Workflow Status" not in response.text


def test_home_recent_event_stream_links_workflow_status_for_workflow_events(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-home-workflow",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": "trace-home-workflow",
            "producer": "pytest",
            "payload": {"title": "Home Workflow Event"},
        },
    )

    response = client.get("/?employee_id=100001&event_type=equipment.alarm.raised.v1")

    assert response.status_code == 200
    assert "Home Workflow Event" in response.text
    assert "Workflow Status" in response.text
    assert "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-home-workflow" in response.text


def test_home_recent_event_stream_empty_state_for_event_type_filter(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100003&event_type=external.webhook.received.v1")

    assert response.status_code == 200
    assert "아직 이 Event Type으로 발행된 이벤트가 없습니다." in response.text
    assert "/events?employee_id=100003&amp;event_type=external.webhook.received.v1" in response.text
    assert "python scripts/publish_event.py external.webhook.received.v1 --employee 100003" in response.text


def recovered_metadata(boi_id: str = "boi:private:100001:recovered:001") -> dict:
    return {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/action",
        "title": "Recovered Generated BoI",
        "description": "Recovered from materialized event log",
        "tags": ["SOP", "Recovery"],
        "timestamp": "2026-06-17T15:00:00+09:00",
        "boi_id": boi_id,
        "visibility": "private",
        "classification": "internal",
        "owner": "100001",
        "author": {"type": "agent", "agent_id": "boi-writer-v0.4"},
        "acl_policy": "acl:private:100001",
        "status": "draft",
        "source_event": {"event_id": "evt-recovered", "event_type": "corrective_action.requested.v1"},
        "event_type": "corrective_action.requested.v1",
    }


def append_materialized_log(boi_app_module, *, trace_id: str, boi_id: str, include_item: bool = True) -> None:
    action_result = {"status": "materialized", "request_id": "act-recovered"}
    if include_item:
        action_result["response"] = {
            "item": {
                "metadata": recovered_metadata(boi_id),
                "uri": "/private/100001/boi-private-100001-recovered-001.md",
                "body": "# Summary\n\nRecovered generated body",
            }
        }
    boi_app_module.append_event_log(
        status="processed",
        event={
            "event_id": "evt-recovered",
            "event_type": "corrective_action.requested.v1",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "Recovered Generated BoI"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {
                "ok": True,
                "status": "dispatched",
                "boi_id": boi_id,
                "results": [
                    {"action_key": "boi.materialize_event", "type": "boi_materialize", "result": action_result}
                ],
            },
        },
    )


def test_doc_page_recovers_generated_boi_from_materialized_event_log(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100001:recovered:001"
    append_materialized_log(boi_app_module, trace_id="trace-recovered-doc", boi_id=boi_id)

    response = client.get(f"/docs/{boi_id}?employee_id=100001")

    assert response.status_code == 200
    assert "Recovered Generated BoI" in response.text
    assert "Recovered generated body" in response.text
    assert "Recovered from event/action log" in response.text


def test_recovered_private_boi_is_not_visible_to_other_employee(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100001:recovered:secret"
    append_materialized_log(boi_app_module, trace_id="trace-recovered-secret", boi_id=boi_id)

    response = client.get(f"/docs/{boi_id}?employee_id=100002")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Recovered Generated BoI" not in response.text
    assert "BoI not found or not accessible" in response.text


def test_missing_boi_returns_html_missing_page_instead_of_json_detail(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:private:100001:missing:no-log?employee_id=100001")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert response.text.lstrip().startswith("<!doctype html>")
    assert '{"detail"' not in response.text
    assert "BoI not found or not accessible" in response.text


def test_events_page_links_recoverable_generated_boi_and_marks_unrecoverable_boi(boi_app_module):
    client = TestClient(boi_app_module.app)
    recoverable_id = "boi:private:100001:recoverable:event"
    missing_id = "boi:private:100001:missing:event"
    append_materialized_log(boi_app_module, trace_id="trace-event-links", boi_id=recoverable_id)
    append_materialized_log(boi_app_module, trace_id="trace-event-links", boi_id=missing_id, include_item=False)

    response = client.get("/events?employee_id=100001&trace_id=trace-event-links")

    assert response.status_code == 200
    assert f"/docs/{recoverable_id}?employee_id=100001" in response.text
    assert "Generated BoI" in response.text
    assert "BoI missing" in response.text
    assert missing_id in response.text
    assert f'href="/docs/{missing_id}?employee_id=100001"' not in response.text


def test_events_page_does_not_render_doc_links_that_return_404(boi_app_module):
    client = TestClient(boi_app_module.app)
    recoverable_id = "boi:private:100001:crawl:ok"
    missing_id = "boi:private:100001:crawl:missing"
    append_materialized_log(boi_app_module, trace_id="trace-crawl-links", boi_id=recoverable_id)
    append_materialized_log(boi_app_module, trace_id="trace-crawl-links", boi_id=missing_id, include_item=False)

    response = client.get("/events?employee_id=100001&trace_id=trace-crawl-links")
    hrefs = [
        unquote(match)
        for match in re.findall(r'href="(/docs/[^"]+)"', response.text)
        if "employee_id=100001" in match
    ]

    assert hrefs
    for href in hrefs:
        linked = client.get(href)
        assert linked.status_code != 404, href
