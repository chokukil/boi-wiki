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
from jsonschema import validate
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


def write_private_inbox_report_fixture(boi_app_module, *, report_id: str, title: str, body: str = "# Report\n\nGenerated") -> dict[str, Any]:
    metadata = boi_app_module.make_metadata(
        boi_type="boi/inbox-review-report",
        title=title,
        description=title,
        owner="100001",
        visibility="private",
        classification="internal",
        source_refs=[{"type": "test", "ref": report_id}],
        status="reviewed",
        tags=["BoI", "Inbox", "ReviewReport"],
    )
    metadata.update(
        {
            "artifact_visibility": "background",
            "lifecycle_state": "background",
            "stable_artifact_key": f"inbox-report:{report_id}:test",
            "inbox_report": {
                "report_id": report_id,
                "report_hash": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                "contract_version": "test",
                "generated_at": boi_app_module.now_iso(),
                "quality": "verified",
            },
        }
    )
    return boi_app_module.write_boi_to_subfolder(metadata, body, "inbox-reports")


def install_fake_boi_agent_router(boi_app_module, monkeypatch, *, route: str | None = None, intent: str | None = None):
    """Install an LLM-router test double without reintroducing rule fallback."""

    def fake_router(req, employee_id: str):
        selected_intent = intent or req.intent or "search"
        selected_intent = boi_app_module.normalize_agent_intent(selected_intent, fallback="search")
        selected_route = route or boi_app_module.route_for_agent_intent(selected_intent)
        return {
            "route": selected_route,
            "confidence": 0.93,
            "intent": selected_intent,
            "reason": "test llm router",
            "requires_mutation": selected_route in {"manual_handoff", "approval_required"},
            "requires_deep_reasoning": selected_route == "deep",
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    return fake_router


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


def test_private_generated_docs_are_hidden_by_default_and_visible_with_flag(boi_app_module):
    client = TestClient(boi_app_module.app)
    report_id = "pytest-private-filter"
    report = write_private_inbox_report_fixture(
        boi_app_module,
        report_id=report_id,
        title="Pytest Generated Report Hidden By Default",
    )
    boi_id = str((report.get("metadata") or {}).get("boi_id") or "")

    default_page = client.get("/?employee_id=100001&q=Pytest Generated Report Hidden By Default")
    explicit_page = client.get("/?employee_id=100001&q=Pytest Generated Report Hidden By Default&include_generated=true")
    default_api = client.get("/api/boi?employee_id=100001&q=Pytest Generated Report Hidden By Default")
    explicit_api = client.get("/api/boi?employee_id=100001&q=Pytest Generated Report Hidden By Default&include_generated=true")

    assert default_page.status_code == 200
    assert boi_id not in default_page.text
    assert explicit_page.status_code == 200
    assert boi_id in explicit_page.text
    assert default_api.status_code == 200
    assert default_api.json()["count"] == 0
    assert explicit_api.status_code == 200
    assert explicit_api.json()["count"] == 1


def test_private_memory_cleanup_preview_quarantine_and_restore(boi_app_module):
    client = TestClient(boi_app_module.app)
    report_id = "pytest-cleanup-duplicate"
    old_a = write_private_inbox_report_fixture(boi_app_module, report_id=report_id, title="Cleanup Duplicate Report A", body="# A")
    time.sleep(0.01)
    old_b = write_private_inbox_report_fixture(boi_app_module, report_id=report_id, title="Cleanup Duplicate Report B", body="# B")
    time.sleep(0.01)
    latest = write_private_inbox_report_fixture(boi_app_module, report_id=report_id, title="Cleanup Duplicate Report Latest", body="# Latest")
    old_ids = {
        str((old_a.get("metadata") or {}).get("boi_id") or ""),
        str((old_b.get("metadata") or {}).get("boi_id") or ""),
    }
    latest_id = str((latest.get("metadata") or {}).get("boi_id") or "")

    preview = client.get("/api/private-memory/cleanup-preview?employee_id=100001")

    assert preview.status_code == 200
    payload = preview.json()
    candidate_ids = {item["boi_id"] for item in payload["candidates"]}
    keep_ids = {item["boi_id"] for item in payload["keep"]}
    assert old_ids.issubset(candidate_ids)
    assert latest_id in keep_ids
    assert payload["quarantine_days"] == 7

    rejected = client.post(
        "/api/private-memory/cleanup-run?employee_id=100001",
        json={"selected_boi_ids": sorted(old_ids), "user_confirmed": False},
    )
    assert rejected.status_code == 400

    cleanup = client.post(
        "/api/private-memory/cleanup-run?employee_id=100001",
        json={"cleanup_id": "pytest-cleanup", "selected_boi_ids": sorted(old_ids), "user_confirmed": True},
    )

    assert cleanup.status_code == 200
    cleanup_payload = cleanup.json()
    assert cleanup_payload["moved_count"] == 2
    manifest_path = boi_app_module.PRIVATE_MEMORY_TRASH_ROOT / "100001" / "pytest-cleanup" / "manifest.json"
    assert manifest_path.exists()
    for boi_id in old_ids:
        assert boi_app_module.find_doc_by_id(boi_id, "100001") is None
    assert boi_app_module.find_doc_by_id(latest_id, "100001") is not None

    restored = client.post(
        "/api/private-memory/restore?employee_id=100001",
        json={"cleanup_id": "pytest-cleanup", "boi_ids": sorted(old_ids), "user_confirmed": True},
    )

    assert restored.status_code == 200
    assert restored.json()["restored_count"] == 2
    for boi_id in old_ids:
        assert boi_app_module.find_doc_by_id(boi_id, "100001") is not None


def test_inbox_report_materialization_updates_existing_report_boi(boi_app_module):
    report_id = "pytest-stable-report"
    first_report = {
        "title": "Stable Report Test",
        "generated_at": "2026-07-01T00:00:00+09:00",
        "conclusion": {"summary": "첫 보고서"},
        "comparison": {"items": []},
        "evidence": {"items": []},
        "similar_cases": {"items": []},
    }
    second_report = {
        **first_report,
        "generated_at": "2026-07-01T01:00:00+09:00",
        "conclusion": {"summary": "갱신된 보고서"},
        "evidence": {"items": [{"label": "Trend", "summary": "확인됨", "status": "ready"}]},
    }

    first = boi_app_module.materialize_inbox_review_report_boi("100001", report_id=report_id, report=first_report)
    second = boi_app_module.materialize_inbox_review_report_boi("100001", report_id=report_id, report=second_report)

    assert first["report_boi_ref"] == second["report_boi_ref"]
    report_docs = []
    for path in (boi_app_module.DATA_ROOT / "private" / "100001" / "inbox-reports").glob("*.md"):
        metadata, body = boi_app_module.split_frontmatter(path.read_text(encoding="utf-8"))
        report_meta = metadata.get("inbox_report") if isinstance(metadata.get("inbox_report"), dict) else {}
        if report_meta.get("report_id") == report_id:
            report_docs.append((metadata, body))
    assert len(report_docs) == 1
    metadata, body = report_docs[0]
    assert metadata["artifact_visibility"] == "background"
    assert metadata["lifecycle_state"] == "background"
    assert "갱신된 보고서" in body


def test_runtime_config_exposes_sanitized_gemma_settings(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/runtime/config")

    assert response.status_code == 200
    body = response.json()
    assert body["features"]["pet_agent_enabled"] is False
    assert body["features"]["ops_center_enabled"] is False
    assert body["llm"]["base_url"] == "http://llm-gateway.example:1236/v1"
    assert body["llm"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["llm"]["api_key_configured"] is True
    assert "api_key" not in body["llm"]
    assert body["openai_runtime"]["active_model"] == "gpt-5.5"
    assert isinstance(body["openai_runtime"]["api_key_present"], bool)
    assert body["agents_sdk_runtime"]["runtime"] in {"native", "agents_sdk"}
    assert isinstance(body["agents_sdk_runtime"]["available"], bool)
    assert body["agents_sdk_runtime"]["sandbox"]["backend"] in {"unix_local", "docker", "external"}
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
    assert body["boi_agent"]["suggestions"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["boi_agent"]["suggestions"]["required"] is True
    assert body["boi_agent"]["suggestions"]["max_attempts"] >= 1
    assert "api_key" not in body["boi_agent"]["suggestions"]
    assert body["boi_agent"]["work_context_narrative"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["boi_agent"]["work_context_narrative"]["required"] is True
    assert "api_key" not in body["boi_agent"]["work_context_narrative"]
    assert body["boi_agent"]["llm_concurrency"]["max_concurrency"] >= 1
    assert body["boi_agent"]["llm_concurrency"]["queue_timeout_seconds"] >= 1
    assert body["boi_agent"]["langgraph"]["required"] is True
    assert body["boi_agent"]["langgraph"]["runtime"] in {"LangGraph", "unavailable"}
    assert body["boi_agent"]["cache_warmup"]["enabled"] is True
    assert body["boi_agent"]["cache_warmup"]["status"] in {"not_started", "running", "completed", "failed", "disabled"}
    assert body["readiness"]["profile"] == "local-full"
    assert isinstance(body["readiness"]["ok"], bool)
    assert isinstance(body["readiness"]["failures"], list)
    assert body["deployment"]["profile"] == "local-full"
    assert body["deployment"]["content_root"].endswith("/boi")
    assert body["deployment"]["runtime_root"]
    assert body["git"]["auto_commit"] is True
    assert body["git"]["auto_push"] is False
    assert body["index"]["persisted_enabled"] is True
    assert body["index"]["markdown_documents"] > 0
    assert body["event_broker"]["mode"] == "local"
    assert body["event_broker"]["security_protocol"] == "PLAINTEXT"
    assert body["event_broker"]["sasl_configured"] is False
    assert body["connectors"]["langflow_mode"] == "local"
    assert body["langflow_simulator"]["mode"] == "langflow"
    assert body["langflow_simulator"]["health"] in {"unknown", "ok", "failed"}
    assert "flow_audit" in body["langflow_simulator"]
    assert "last_smoke_at" in body["langflow_simulator"]
    assert "KAFKA_SASL_PASSWORD" not in response.text


def test_workflow_definition_registries_and_api_expose_event_native_contract(boi_app_module):
    client = TestClient(boi_app_module.app)

    workflow_definitions = client.get("/api/workflow-definitions?employee_id=100001")
    legacy = client.get("/api/capabilities?employee_id=100001")
    event_skills = client.get("/api/event-skills?employee_id=100001")
    action_skills = client.get("/api/action-skills?employee_id=100001")

    assert workflow_definitions.status_code == 200
    assert legacy.status_code == 200
    assert legacy.json()["deprecated_alias"] == "/api/capabilities"
    workflow_definition_body = workflow_definitions.json()
    assert workflow_definition_body["ok"] is True
    assert workflow_definition_body["count"] >= 1
    equipment = next(item for item in workflow_definition_body["items"] if item["workflow_definition_key"] == "equipment-anomaly-response")
    assert equipment["workflow_engine"] == "event_native"
    assert equipment["process_model"] == "sop_based"
    assert "설비 이상 감지 BoI" in equipment["work_boi_outputs"]
    assert equipment["entry_events"] == ["equipment.alarm.raised.v1"]
    assert "sop.equipment.request_trend_history" in equipment["action_refs"]
    assert "event.publish" in equipment["action_skill_refs"]

    detail = client.get("/api/workflow-definitions/equipment-anomaly-response?employee_id=100001")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["item"]["event_contracts"][0]["event_type"] == "equipment.alarm.raised.v1"
    assert detail_body["item"]["event_contracts"][0]["trace_policy"] == "required"
    assert detail_body["item"]["required_connectors"]
    assert "langflow" not in detail_body["item"]["required_connectors"]

    assert event_skills.status_code == 200
    assert any(item["skill_key"] == "event.workflow_trigger" for item in event_skills.json()["items"])
    assert action_skills.status_code == 200
    assert any(item["skill_key"] == "evidence.quality_trend" for item in action_skills.json()["items"])


def test_workflow_definition_deduplicate_prefers_existing_event_and_action_contracts(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/workflow-definitions/deduplicate?employee_id=100001",
        json={
            "event_type": "equipment.alarm.raised.v1",
            "payload_schema": {"required": ["equipment_id", "alarm_code"]},
            "action_keys": ["sop.equipment.request_trend_history"],
            "connector": {"kind": "api", "url": "http://quality-system.example/response-trend"},
            "terms": ["Response Trend", "설비 Alarm"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["recommendation"] in {"reuse", "extend"}
    assert body["candidates"]
    top = body["candidates"][0]
    assert top["workflow_definition_key"] == "equipment-anomaly-response"
    assert "event_type" in top["matched_on"]
    assert "action_key" in top["matched_on"]


def test_ontology_search_groups_workflow_definitions_without_changing_document_search(boi_app_module):
    client = TestClient(boi_app_module.app)

    ontology = client.get("/api/search/ontology?employee_id=100001&q=equipment.alarm.raised.v1&view=compact")
    docs = client.get("/api/boi?employee_id=100001&q=equipment.alarm.raised.v1")

    assert ontology.status_code == 200
    ontology_body = ontology.json()
    workflow_definition_items = ontology_body["groups"]["workflow_definitions"]
    assert any(item["workflow_definition_key"] == "equipment-anomaly-response" for item in workflow_definition_items)
    assert ontology_body["knowledge_panel"]["top_workflow_definition"][0]["workflow_definition_key"] == "equipment-anomaly-response"

    assert docs.status_code == 200
    assert "workflow_definitions" not in docs.json()


def test_boi_folder_api_supports_free_business_unit_hierarchy(boi_app_module):
    client = TestClient(boi_app_module.app)

    folders = client.get("/api/boi/folders?employee_id=100001&scope=all")
    assert folders.status_code == 200
    body = folders.json()
    assert body["free_hierarchy"] is True
    assert body["allowed_roots"] == ["public", "team", "private"]
    assert body["folder_tree"]["path"] == ""

    draft = client.post(
        "/api/boi/folders?employee_id=100001",
        json={
            "scope": "private",
            "folder": "weekly-fab-trend",
            "title": "주간 FAB Trend",
            "description": "반복 보고 업무용 개인 업무 단위",
        },
    )
    assert draft.status_code == 200
    draft_body = draft.json()
    assert draft_body["status"] == "draft_required"
    assert draft_body["folder"] == "private/100001/weekly-fab-trend"
    assert draft_body["draft_metadata"]["visibility"] == "private"
    assert draft_body["draft_metadata"]["acl_policy"] == "acl:private:100001"
    assert "빈 폴더" in draft_body["message"]


def test_workflow_definitions_page_renders_registration_studio_entry_and_nav(boi_app_module):
    client = TestClient(boi_app_module.app)

    home = client.get("/?employee_id=100001")
    page = client.get("/workflows/definitions?employee_id=100001")
    legacy = client.get("/capabilities?employee_id=100001")

    assert home.status_code == 200
    assert "BoI Wiki" in home.text
    assert "BoI Wiki Explorer" in home.text
    assert "public, team, private 아래 업무 단위 폴더와 문서를 탐색합니다." in home.text
    assert "업무 BoI를 중심으로 공식 SOP" not in home.text
    assert "boi-wiki-catalog-intro" not in home.text
    assert 'data-nav-id="connections"' not in home.text
    assert page.status_code == 200
    assert legacy.status_code == 200
    assert "업무 흐름 정의" in page.text
    assert "업무 BoI" in page.text
    assert "추가 / 연결 시작" in page.text
    assert "equipment-anomaly-response" in page.text
    assert "SOP 기반 업무" in page.text
    assert "중복 확인" in page.text
    assert re.search(r'<a[^>]+data-nav-id="library"[^>]+aria-current="page"', page.text)


def test_publish_event_kafka_disabled_keeps_event_log_without_broker_publish(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "KAFKA_MODE", "disabled")
    boi_app_module.AIOKafkaProducer.sent_events = []

    response = client.post(
        "/api/events/publish?employee_id=100001",
        json={
            "event_type": "equipment.alarm.raised.v1",
            "actor_employee_id": "100001",
            "payload": {
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-001",
                "wafer_id": "WF-001",
                "alarm_code": "PRESSURE_SPIKE",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["broker"]["status"] == "disabled"
    assert boi_app_module.AIOKafkaProducer.sent_events == []
    event_rows = boi_app_module.cached_event_log_rows()
    assert event_rows
    latest = event_rows[-1]
    assert latest["payload"]["equipment_id"] == "ETCH-VM-01"
    assert latest["business_context"]["equipment_id"] == "ETCH-VM-01"
    assert latest["business_context"]["lot_id"] == "LOT-001"
    assert latest["business_context"]["alarm_code"] == "PRESSURE_SPIKE"


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
    assert body["streaming"]["events"] == ["accepted", "status", "answer_delta", "answer_ready", "followups", "final", "error"]
    assert body["status_writer"]["required"] is True
    assert body["status_writer"]["model"]
    assert body["composer"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["composer"]["timeout_seconds"] <= 30
    assert body["composer"]["max_attempts"] == 2
    assert body["native_agent"]["langgraph_required"] is True
    assert body["native_agent"]["runtime"] in {"LangGraph", "unavailable"}
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    assert body["response_contract"]["canonical_endpoint"] == "/api/agents/boi-wiki/chat"
    assert body["response_contract"]["approve_endpoint"] == "/api/agents/boi-wiki/approve"
    assert body["response_contract"]["schema_endpoint"] == "/api/agents/boi-wiki/response-schema"
    assert "boi_wiki_mcp" in body["response_contract"]["consumers"]
    assert "status_updates" in body["response_contract"]["required_fields"]
    assert "status_events" not in body["response_contract"]["required_fields"]
    assert body["response_contract"]["status_fields"] == {
        "canonical": "status_updates",
        "alias": "status_events",
        "stream_event": "status",
    }
    assert "tool_trace" in body["response_contract"]["required_fields"]
    assert "access_summary" in body["response_contract"]["required_fields"]
    assert "execution_card_fields" in body["response_contract"]
    assert "required_role" in body["response_contract"]["execution_card_required_fields"]
    assert "permission" in body["response_contract"]["execution_card_required_fields"]
    assert body["response_contract"]["schema"]["properties"]["agent_contract_version"]["const"] == "boi-agent.response.v1"
    assert "status_events" in body["response_contract"]["schema"]["properties"]
    assert "mermaid" in body["response_contract"]["schema"]["properties"]["artifacts"]["items"]["properties"]["type"]["enum"]
    assert "action_requirements" in body["response_contract"]["schema"]["properties"]["artifacts"]["items"]["properties"]["type"]["enum"]
    execution_card_item = body["response_contract"]["schema"]["properties"]["execution_cards"]["items"]
    card_schema = execution_card_item["properties"]
    assert card_schema["required_role"]["type"] == "string"
    assert card_schema["permission"]["type"] == "object"
    assert "required_role" in execution_card_item["required"]
    assert "permission" in execution_card_item["required"]
    assert "progressive response streaming" in body["features"]
    for operation in body["supported_execution_cards"]:
        assert operation in body["write_confirmation_required"]
    for operation in ["event_publish", "workflow_start", "event_type_draft", "source_apply", "doc_body_apply"]:
        assert operation in body["write_confirmation_required"]
        assert operation in body["supported_execution_cards"]

    schema_response = client.get("/api/agents/boi-wiki/response-schema")
    assert schema_response.status_code == 200
    schema_body = schema_response.json()
    assert schema_body["agent_contract_version"] == "boi-agent.response.v1"
    assert schema_body["schema"]["required"] == body["response_contract"]["required_fields"]


def test_agent_context_pack_uses_current_page_seed_for_page_first_gap_check(boi_app_module, monkeypatch):
    monkeypatch.setattr(
        boi_app_module,
        "resolve_agent_page_context",
        lambda current_url, employee_id: {
            "resolved": True,
            "page_kind": "doc",
            "boi_id": "boi:public:sop:equipment-abnormal-response",
            "title": "설비 이상 대응 SOP",
            "type": "boi/sop",
            "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "access": {"can_read": True, "can_use_in_agent_context": True, "can_cite": True},
        },
    )

    def fail_broad_search(*_args, **_kwargs):
        raise AssertionError("page-first gap check should not run broad ontology search")

    monkeypatch.setattr(boi_app_module, "ontology_search_payload", fail_broad_search)

    pack = boi_app_module.agent_context_pack(
        boi_app_module.BoiAgentChatRequest(
            question="이 SOP를 실행하려면 부족한 Action Spec이 있는지 찾아줘.",
            current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        ),
        "100001",
    )

    seed = pack["ontology_search_seed"]
    assert seed["ok"] is True
    assert seed["scope"] == "page_context"
    assert seed["best_matches"][0]["match_reason"] == "current_page"
    assert seed["document_rank_refs"] == ["boi:public:sop:equipment-abnormal-response"]


def test_ontology_compact_view_skips_graph_path_resolution(boi_app_module, monkeypatch):
    doc = {
        "metadata": {
            "boi_id": "boi:public:sop:sample",
            "title": "설비 SOP",
            "description": "설비 이상 대응",
            "type": "boi/sop",
            "visibility": "public",
            "classification": "internal",
        },
        "uri": "/public/sop/sample.md",
        "path": "/tmp/sample.md",
        "body": "설비 이상 대응",
    }
    monkeypatch.setattr(
        boi_app_module,
        "search_index_for_employee",
        lambda employee_id: {
            "docs": [doc],
            "doc_records": [
                {
                    "ref": "boi:public:sop:sample",
                    "doc": doc,
                    "blob": "설비 이상 대응",
                    "title": "설비 SOP",
                    "id_text": "boi:public:sop:sample",
                    "description": "설비 이상 대응",
                    "type": "boi/sop",
                    "access": {"can_read": True, "can_use_in_agent_context": True, "can_cite": True},
                }
            ],
            "dictionary": [],
            "event_types": [],
            "actions": [],
        },
    )
    monkeypatch.setattr(
        boi_app_module,
        "find_doc_by_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compact ontology should not resolve graph docs")),
    )

    payload = boi_app_module.ontology_search_payload("설비", "100001", view="compact")

    assert payload["view"] == "compact"
    assert payload["graph_paths"] == []
    assert payload["best_matches"][0]["boi_id"] == "boi:public:sop:sample"


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


def test_native_agent_tool_progress_does_not_generate_user_status_text():
    from boi_api.app import native_agent

    progress_events: list[dict[str, Any]] = []
    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "count": 1},
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
        native_agent.NativeAgentConfig(require_langgraph=False, progress_callback=progress_events.append),
    )
    state: dict[str, Any] = {"tool_trace": []}

    result = runtime._call_tool(
        "ontology_search",
        {"query": "SOP"},
        lambda: {"ok": True, "count": 1},
        state,
    )

    assert result["count"] == 1
    assert len(progress_events) == 2
    assert {event["stage"] for event in progress_events} == {"tool_start", "tool_done"}
    assert all("message" not in event for event in progress_events)
    assert state["tool_trace"][0].summary == "count=1"


def test_native_agent_workflow_mermaid_uses_specific_workflow_items():
    from boi_api.app import native_agent

    doc = {
        "metadata": {
            "workflow": {
                "stages": [
                    {
                        "id": "detect",
                        "name": "이상 감지",
                        "event_types": ["equipment.alarm.raised.v1", "trend.anomaly.detected.v1"],
                        "automated_actions": [
                            "sop.equipment.request_raw_data",
                            "sop.equipment.request_trend_history",
                        ],
                        "manual_actions": ["manual.equipment.confirm_alarm_context"],
                    },
                    {
                        "id": "analyze",
                        "name": "원인 분석",
                        "event_types": ["root_cause.analysis.requested.v1"],
                        "automated_actions": ["langflow.equipment.stage_analysis"],
                        "manual_actions": ["manual.equipment.review_root_cause"],
                    },
                ]
            }
        }
    }

    source = native_agent.workflow_mermaid(doc)

    assert 'e1_1["alarm.raised"] --> s1' in source
    assert 'e1_2["anomaly.detected"] --> s1' in source
    assert 's1 --> a1_1["request_raw_data"]' in source
    assert 's1 --> a1_2["request_trend_history"]' in source
    assert 's1 --> m1_1["confirm_alarm_context"]' in source
    assert 's2 --> a2_1["stage_analysis"]' in source
    assert "업무 이벤트 2개" not in source
    assert "자동 업무 요청 2개" not in source
    assert "수동 조치" not in source


def test_native_agent_diagram_answer_describes_specific_item_labels():
    from boi_api.app import native_agent

    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "count": 0},
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
    runtime = native_agent.NativeBoiAgent(tools, native_agent.NativeAgentConfig(require_langgraph=False))
    state: dict[str, Any] = {
        "tool_results": {
            "current_doc": {
                "metadata": {
                    "title": "테스트 SOP",
                    "workflow": {
                        "stages": [
                            {
                                "id": "detect",
                                "name": "이상 감지",
                                "event_types": ["equipment.alarm.raised.v1"],
                                "automated_actions": ["sop.equipment.request_raw_data"],
                                "manual_actions": ["manual.equipment.confirm_alarm_context"],
                            }
                        ]
                    },
                }
            }
        },
        "search": {},
    }

    runtime._compose_diagram_answer(state)

    assert "항목 개수 중심" not in state["answer_markdown"]
    assert "구체 항목 이름" in state["answer_markdown"]


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
    assert payloads[0]["json"]["response_format"]["type"] == "text"
    assert "json_schema" not in payloads[0]["json"]["response_format"]
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


def test_boi_agent_stream_plan_requests_three_distinct_statuses(boi_app_module, monkeypatch):
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
                                    "route": "fast",
                                    "confidence": 0.95,
                                    "intent": "page_qa",
                                    "requires_mutation": False,
                                    "requires_deep_reasoning": False,
                                    "statuses": [
                                        {"stage": "page_context", "message": "현재 화면의 맥락을 확인하고 있습니다."},
                                        {"stage": "retrieval", "message": "관련 근거와 연결 문서를 살펴보고 있습니다."},
                                        {"stage": "compose", "message": "확인한 내용을 한 문장으로 정리하고 있습니다."},
                                    ],
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
            payloads.append(json)
            return FakeResponse()

    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BASE_URL", "http://router.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    plan = boi_app_module.call_boi_agent_stream_plan_llm(
        boi_app_module.BoiAgentChatRequest(
            question="현재 페이지 기준으로 진행 상태 한 줄을 만들고 짧게 답해줘",
            current_url="/docs/boi:public:sop:equipment-abnormal-response",
        ),
        "100001",
    )

    assert payloads[0]["response_format"] == {"type": "text"}
    prompt = payloads[0]["messages"][1]["content"]
    assert "exactly 3 distinct Korean nontechnical messages" in prompt
    assert len(plan["status_steps"]) == 3


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


def test_boi_agent_stream_status_deduplicates_llm_messages(boi_app_module):
    steps = boi_app_module.normalize_llm_status_steps(
        {
            "statuses": [
                {
                    "stage": "page_context",
                    "message": "현재 페이지의 내용을 분석 중입니다.",
                },
                {
                    "stage": "intent",
                    "message": "현재 페이지의 내용을 분석 중입니다.",
                },
                {
                    "stage": "compose",
                    "message": "분석된 정보를 바탕으로 답변을 구성합니다.",
                },
            ]
        }
    )

    assert steps == [
        {
            "stage": "page_context",
            "message": "현재 페이지의 내용을 분석 중입니다.",
            "source": "llm_status",
        },
        {
            "stage": "compose",
            "message": "분석된 정보를 바탕으로 답변을 구성합니다.",
            "source": "llm_status",
        },
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


def test_dictionary_resolve_is_bounded_for_large_match_sets(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    terms = []
    for index in range(40):
        terms.append(
            {
                "term": f"scale-term-{index:03d}",
                "definition": "대량 dictionary context budget 검증용 설명입니다. " * 20,
                "aliases": ["ETCH", *[f"alias-{index}-{alias_index}" for alias_index in range(20)]],
                "related_terms": [f"related-{index}-{related_index}" for related_index in range(20)],
                "scope": "public",
                "priority": 2,
                "domain": "scale-test",
                "url": f"/docs/scale-term-{index:03d}",
            }
        )
    monkeypatch.setattr(boi_app_module, "dictionary_terms_for_employee", lambda employee_id, scope="all": terms)

    response = client.get("/api/dictionary/resolve?employee_id=100001&q=etch&limit=8")

    assert response.status_code == 200
    body = response.json()
    assert len(body["matches"]) == 8
    assert body["overflow"]["total_matches"] == 40
    assert body["overflow"]["omitted_count"] == 32
    assert len(body["expanded_terms"]) <= 24
    assert all(len(item.get("definition", "")) <= 240 for item in body["matches"])
    assert all(len(item.get("aliases", [])) <= 8 for item in body["matches"])
    assert all(len(item.get("related_terms", [])) <= 8 for item in body["matches"])


def test_dictionary_terms_support_cursor_pagination_and_compact_items(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    terms = [
        {
            "term": f"cursor-term-{index:03d}",
            "definition": "cursor pagination validation " * 30,
            "aliases": [f"alias-{index}-{alias_index}" for alias_index in range(12)],
            "related_terms": [f"related-{index}-{related_index}" for related_index in range(12)],
            "scope": "public",
            "priority": 2,
        }
        for index in range(12)
    ]
    monkeypatch.setattr(boi_app_module, "dictionary_terms_for_employee", lambda employee_id, scope="all": terms)

    first = client.get("/api/dictionary/terms?employee_id=100001&limit=5")
    second = client.get("/api/dictionary/terms?employee_id=100001&limit=5&cursor=5")

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["total"] == 12
    assert first_body["count"] == 5
    assert first_body["next_cursor"] == "5"
    assert len(first_body["items"][0]["definition"]) <= 240
    assert len(first_body["items"][0]["aliases"]) <= 8
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["items"][0]["term"] == "cursor-term-005"
    assert second_body["next_cursor"] == "10"


def test_dictionary_resolve_returns_canonical_term_kind_and_alias_match(boi_app_module):
    client = TestClient(boi_app_module.app)

    dist = client.get("/api/dictionary/resolve?employee_id=100001&q=0-PG%20Dist")
    stack = client.get("/api/dictionary/resolve?employee_id=100001&q=4HI")
    terms = client.get("/api/dictionary/terms?employee_id=100001&q=Memory%20Stack%20Height")

    assert dist.status_code == 200
    dist_match = dist.json()["matches"][0]
    assert dist_match["term"] == "Word Line Disturbance Test"
    assert dist_match["term_kind"] == "test-method"
    assert dist_match["matched_as"] == "alias"
    assert dist_match["matched_value"] == "0-PG Dist"
    assert "NAND Flash" in dist_match["broader"]

    assert stack.status_code == 200
    stack_match = stack.json()["matches"][0]
    assert stack_match["term"] == "Memory Stack Height"
    assert stack_match["term_kind"] == "concept"
    assert stack_match["matched_as"] == "alias"
    assert stack_match["matched_value"] == "4HI"

    assert terms.status_code == 200
    assert terms.json()["items"][0]["term_kind"] == "concept"


def test_compact_ontology_search_caps_dictionary_context_budget(boi_app_module, monkeypatch):
    terms = [
        {
            "term": f"ontology-scale-{index:03d}",
            "definition": "compact ontology context budget validation " * 30,
            "aliases": ["ETCH", *[f"alias-{index}-{alias_index}" for alias_index in range(20)]],
            "related_terms": [f"related-{index}-{related_index}" for related_index in range(20)],
            "scope": "public",
            "priority": 2,
        }
        for index in range(30)
    ]
    monkeypatch.setattr(boi_app_module, "dictionary_terms_for_employee", lambda employee_id, scope="all": terms)
    monkeypatch.setattr(
        boi_app_module,
        "search_index_for_employee",
        lambda employee_id: {
            "doc_records": [],
            "dictionary": [],
            "event_types": [],
            "actions": [],
            "workflow_definitions": [],
        },
    )

    payload = boi_app_module.ontology_search_payload("etch", "100001", limit=8, view="compact")

    assert payload["view"] == "compact"
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= 96 * 1024
    assert len(payload["query_expansion"]) <= 24
    assert payload["dictionary_overflow"]["total_matches"] == 30
    for item in payload["groups"]["dictionary"]:
        assert len(item.get("definition", "")) <= 240
        assert len(item.get("aliases", [])) <= 8
        assert len(item.get("related_terms", [])) <= 8


def test_dictionary_term_create_allows_private_but_rejects_shared_scope_without_editor(boi_app_module):
    client = TestClient(boi_app_module.app)

    private_create = client.post(
        "/api/dictionary/terms?employee_id=100003",
        json={
            "scope": "private",
            "term": "pytest-viewer-private-term",
            "definition": "개인 용어는 일반 구성원도 추가할 수 있다.",
        },
    )
    team_create = client.post(
        "/api/dictionary/terms?employee_id=100003",
        json={
            "scope": "team",
            "team_id": "platform",
            "term": "pytest-viewer-team-term",
            "definition": "팀 용어는 공유 검색 의미를 바꾸므로 편집 권한이 필요하다.",
        },
    )
    public_create = client.post(
        "/api/dictionary/terms?employee_id=100003",
        json={
            "scope": "public",
            "term": "pytest-viewer-public-term",
            "definition": "공개 용어는 공유 검색 의미를 바꾸므로 편집 권한이 필요하다.",
        },
    )

    assert private_create.status_code == 200
    private_item = private_create.json()["item"]
    assert private_item["metadata"]["visibility"] == "private"
    assert private_item["metadata"]["owner"] == "100003"
    assert private_item["metadata"]["acl_policy"] == "acl:private:100003"
    assert private_item["folder"] == "private/100003/dictionary"
    assert team_create.status_code == 403
    assert "missing required role: boi.editor" in team_create.text
    assert public_create.status_code == 403
    assert "missing required role: boi.editor" in public_create.text


def test_dictionary_term_create_rejects_team_scope_when_editor_is_not_team_member(boi_app_module):
    client = TestClient(boi_app_module.app)

    non_member_team = client.post(
        "/api/dictionary/terms?employee_id=100002",
        json={
            "scope": "team",
            "team_id": "platform",
            "term": "pytest-editor-wrong-team-term",
            "definition": "편집자라도 자신이 속하지 않은 팀 용어는 추가할 수 없다.",
        },
    )
    own_team = client.post(
        "/api/dictionary/terms?employee_id=100002",
        json={
            "scope": "team",
            "team_id": "aix-tf",
            "term": "pytest-editor-own-team-term",
            "definition": "편집자는 자신이 속한 팀의 공유 용어를 추가할 수 있다.",
        },
    )

    assert non_member_team.status_code == 403
    assert "employee is not member of team: platform" in non_member_team.text
    assert own_team.status_code == 200
    metadata = own_team.json()["item"]["metadata"]
    assert metadata["visibility"] == "team"
    assert metadata["team_id"] == "aix-tf"
    assert metadata["owner"] == "aix-tf"
    assert metadata["acl_policy"] == "acl:team:aix-tf"


def test_ontology_and_boi_search_filter_private_docs_by_employee(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100002:ontology-acl-private-leak-test"
    needle = "ontology-acl-private-needle"
    title = "Ontology ACL Private Leak Test"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": title,
            "description": needle,
            "tags": ["ACL", "Search"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100002",
            "author": {"type": "agent", "agent_id": "pytest"},
            "acl_policy": "acl:private:100002",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "ontology-private-acl"}],
        },
        f"# Summary\n\n{needle} must only be searchable by owner 100002.",
    )

    forbidden_ontology = client.get(f"/api/search/ontology?employee_id=100001&q={quote(needle)}&view=compact")
    allowed_ontology = client.get(f"/api/search/ontology?employee_id=100002&q={quote(needle)}&view=compact")
    forbidden_boi = client.get(f"/api/boi?employee_id=100001&q={quote(needle)}")
    allowed_boi = client.get(f"/api/boi?employee_id=100002&q={quote(needle)}")

    assert forbidden_ontology.status_code == 200
    assert allowed_ontology.status_code == 200
    forbidden_dump = json.dumps(
        {
            "groups": forbidden_ontology.json().get("groups"),
            "best_matches": forbidden_ontology.json().get("best_matches"),
            "citations": forbidden_ontology.json().get("citations"),
            "document_rank_refs": forbidden_ontology.json().get("document_rank_refs"),
        },
        ensure_ascii=False,
    )
    allowed_dump = json.dumps(
        {
            "groups": allowed_ontology.json().get("groups"),
            "best_matches": allowed_ontology.json().get("best_matches"),
            "citations": allowed_ontology.json().get("citations"),
            "document_rank_refs": allowed_ontology.json().get("document_rank_refs"),
        },
        ensure_ascii=False,
    )
    assert boi_id not in forbidden_dump
    assert title not in forbidden_dump
    assert boi_id in allowed_dump
    assert title in allowed_dump

    assert forbidden_boi.status_code == 200
    assert allowed_boi.status_code == 200
    assert all((item.get("metadata") or {}).get("boi_id") != boi_id for item in forbidden_boi.json()["items"])
    assert any((item.get("metadata") or {}).get("boi_id") == boi_id for item in allowed_boi.json()["items"])


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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="search")
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
    assert isinstance(body["status_updates"], list)
    assert isinstance(body["execution_cards"], list)
    assert isinstance(body["access_summary"], dict)
    assert "설비" in body["answer_markdown"]
    assert isinstance(body["links"], list)


def test_boi_agent_chat_json_embeds_stream_plan_status_for_api_and_mcp(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
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
    status_steps = [
        {"stage": "page_context", "message": "현재 SOP 화면과 접근 권한을 확인합니다.", "source": "llm_status"},
        {"stage": "tool_loop", "message": "SOP 단계와 연결 업무 요청을 조회합니다.", "source": "llm_status"},
        {"stage": "compose", "message": "다이어그램과 링크를 정리합니다.", "source": "llm_status"},
    ]
    received_routes: list[dict[str, Any]] = []

    def fake_stream_plan(req, employee_id: str):
        return {"route": planned_route, "status_steps": status_steps}

    def fake_agent_response(req, employee_id: str, progress_callback=None, route=None):
        received_routes.append(route or {})
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "## SOP Diagram\n\n```mermaid\nflowchart TD\nA[Start] --> B[End]\n```",
            "links": [],
            "citations": [],
            "artifacts": [{"type": "mermaid", "title": "SOP", "source": "flowchart TD\nA[Start] --> B[End]"}],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)
    monkeypatch.setattr(boi_app_module, "agent_stream_plan", fake_stream_plan)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert received_routes == [planned_route]
    assert body["route"] == "deep"
    assert body["intent"] == "diagram"
    assert body["status_updates"][:3] == status_steps
    assert body["status_events"][:3] == status_steps
    assert body["status_updates"][0]["message"] == "현재 SOP 화면과 접근 권한을 확인합니다."


def test_boi_agent_chat_fast_first_does_not_block_on_status_or_followups(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    received_routes: list[dict[str, Any]] = []

    def forbidden_stream_plan(req, employee_id: str):
        raise AssertionError("fast-first REST must not wait for status/router planning")

    def forbidden_followups(req, response, employee_id: str):
        raise AssertionError("fast-first REST must not wait for follow-up suggestions")

    def fake_agent_response(req, employee_id: str, progress_callback=None, route=None):
        received_routes.append(route or {})
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "## 부족 근거\n\nRaw Data endpoint 확인 후 승인 여부를 판단하세요.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "artifacts": [],
            "context_summary": {"intent": "page_qa", "latency_ms": 17},
            "route": (route or {}).get("route") or "fast",
            "intent": (route or {}).get("intent") or "page_qa",
            "router_backend": (route or {}).get("router_backend") or "native_goal_router",
            "used_backend": "native_langgraph",
            "latency_ms": 17,
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_FOLLOWUPS_BLOCKING", False)
    monkeypatch.setattr(boi_app_module, "agent_stream_plan", forbidden_stream_plan)
    monkeypatch.setattr(boi_app_module, "ensure_agent_answer_followups", forbidden_followups)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 보고서에서 부족한 근거가 뭐야?",
            "current_url": "/docs/boi:private:100001:20260630125008:035b77?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert received_routes
    assert received_routes[0]["router_backend"] in {"agent_goal_registry", "native_goal_router"}
    assert body["latency_contract"] == "fast_first"
    assert body["followups_state"] in {"pending", "ready"}
    assert body["answer_refinement_state"] in {"skipped", "pending", "ready"}
    assert body["component_timings"]["native_agent_ms"] == 17
    assert "Raw Data endpoint" in body["answer_markdown"]


def test_boi_agent_fast_first_routes_report_question_to_page_qa(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(
        question="이 보고서에서 부족한 근거가 뭐야?",
        current_url="/docs/boi:private:100001:20260630125008:035b77?employee_id=100001",
    )

    route = boi_app_module.fast_first_agent_route(req, "100001")

    assert route["intent"] == "page_qa"
    assert route["route"] == "fast"
    assert route["router_backend"] == "native_goal_router"


def test_boi_agent_fast_first_routes_report_related_sop_question_to_related_items(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(
        question="sop가 뭐있니",
        current_url="/docs/boi:private:100001:20260630125008:035b77?employee_id=100001",
    )

    route = boi_app_module.fast_first_agent_route(req, "100001")

    assert route["intent"] == "search"
    assert route["response_profile"] == "related_items"
    assert route["semantic_route"]["target_kind"] == "related_sop"
    assert route["route"] == "fast"
    assert route["router_backend"] == "semantic_hybrid_router"


def test_boi_agent_sop_catalog_all_scope_lists_all_sops(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "SOP 리스트 전부 보여줘",
            "current_url": "/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
            "page_context": {"page_kind": "doc", "title": "직개발 결과 확인 및 Reporting SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response_profile"] == "related_items"
    assert body["semantic_route"]["target_kind"] == "related_sop"
    assert body["related_item_context"]["scope"] == "catalog_all"
    assert body["related_item_context"]["direct_count"] >= 2
    rendered = json.dumps(body["related_item_context"]["items"], ensure_ascii=False)
    assert "설비 이상" in rendered
    assert "직개발" in rendered
    assert "현재 페이지와 직접 연결된 SOP" not in body["answer_markdown"]


def test_boi_agent_sop_catalog_search_scope_filters_by_question(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "설비 이상 관련 SOP 보여줘",
            "current_url": "/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
            "page_context": {"page_kind": "doc", "title": "직개발 결과 확인 및 Reporting SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["related_item_context"]["scope"] == "catalog_search"
    rendered = json.dumps(body["related_item_context"]["items"], ensure_ascii=False)
    assert "설비 이상" in rendered
    assert "직개발 결과 확인" not in rendered


def test_boi_agent_fast_first_related_target_beats_current_report_terms(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(
        question="이 보고서랑 연결된 action 뭐야?",
        current_url="/docs/boi:private:100001:20260630125008:035b77?employee_id=100001",
    )

    route = boi_app_module.fast_first_agent_route(req, "100001")

    assert route["intent"] == "search"
    assert route["response_profile"] == "related_items"
    assert route["semantic_route"]["target_kind"] == "related_action"


def test_boi_agent_multiturn_keeps_previous_related_sop_target(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(
        question="전체 리스트 알려줘",
        current_url="/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
        page_context={"title": "직개발 결과 확인 및 Reporting SOP"},
        conversation=[
            {"role": "user", "content": "sop 리스트 알려줘"},
            {
                "role": "assistant",
                "content": "현재 페이지와 직접 연결된 SOP는 1건입니다.",
                "response_profile": "related_items",
                "semantic_route": {"target_kind": "related_sop"},
                "related_item_context": {
                    "target_kind": "related_sop",
                    "items": [
                        {
                            "title": "직개발 결과 확인 및 Reporting SOP",
                            "url": "/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
                        }
                    ],
                },
            },
        ],
    )

    route = boi_app_module.fast_first_agent_route(req, "100001")

    assert route["intent"] == "search"
    assert route["response_profile"] == "related_items"
    assert route["semantic_route"]["target_kind"] == "related_sop"
    assert route["semantic_route"]["continuation_of"] == "related_sop"
    assert route["semantic_route"]["resolved_from_turn"] == "previous_assistant"
    assert route["semantic_route"]["scope"] == "catalog_all"


def test_boi_agent_multiturn_can_switch_from_sop_to_action(boi_app_module):
    req = boi_app_module.BoiAgentChatRequest(
        question="그럼 action은?",
        current_url="/docs/boi:public:sop:direct-development-reporting?employee_id=100001",
        page_context={"title": "직개발 결과 확인 및 Reporting SOP"},
        conversation=[
            {"role": "user", "content": "sop 리스트 알려줘"},
            {
                "role": "assistant",
                "content": "현재 페이지와 직접 연결된 SOP는 1건입니다.",
                "response_profile": "related_items",
                "semantic_route": {"target_kind": "related_sop"},
                "related_item_context": {"target_kind": "related_sop", "items": []},
            },
        ],
    )

    route = boi_app_module.fast_first_agent_route(req, "100001")

    assert route["intent"] == "search"
    assert route["response_profile"] == "related_items"
    assert route["semantic_route"]["target_kind"] == "related_action"
    assert route["semantic_route"].get("continuation_of") != "related_sop"


def test_boi_agent_chat_normalizes_minimal_backend_response_to_agent_contract(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def minimal_agent_response(req, employee_id):
        return {"ok": True, "used_backend": "test_minimal_backend"}

    monkeypatch.setattr(boi_app_module, "agent_chat_response", minimal_agent_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/sops"},
    )

    assert response.status_code == 200
    body = response.json()
    schema = client.get("/api/agents/boi-wiki/response-schema").json()["schema"]
    for field in schema["required"]:
        assert field in body
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    assert body["answer_markdown"] == ""
    assert body["display_markdown"] == ""
    assert body["links"] == []
    assert body["citations"] == []
    assert body["artifacts"] == []
    assert body["execution_cards"] == []
    assert body["status_updates"] == []
    assert body["status_events"] == []
    assert body["tool_trace"] == []
    assert body["access_summary"] == {}
    assert body["guardrails_applied"] == []


def test_boi_agent_chat_generates_answer_scoped_followups_when_backend_omits_them(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    seen_requests: list[Any] = []

    def minimal_agent_response(req, employee_id):
        return {
            "ok": True,
            "used_backend": "native_langgraph",
            "answer_markdown": "## SOP 흐름\n\n설비 이상 SOP를 Mermaid artifact와 원본 매핑 표로 정리했습니다.",
            "links": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
            "citations": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
            "artifacts": [{"type": "mermaid", "title": "SOP", "source": "flowchart TD\nA[이상 감지] --> B[원인 분석]"}],
            "tool_trace": [{"tool": "boi_get", "status": "ok", "summary": "설비 SOP"}],
            "route": "deep",
            "intent": "diagram",
            "suggested_questions": [],
            "suggested_questions_source": "suggestions_endpoint_required",
        }

    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        seen_requests.append(req)
        assert req.answer_context["question"] == "이 SOP를 Mermaid 프로세스 플로우로 보여줘."
        assert req.answer_context["intent"] == "diagram"
        assert req.answer_context["artifacts"][0]["type"] == "mermaid"
        assert req.answer_context["links"][0]["label"] == "설비 SOP"
        return [
            "이 Mermaid에서 원인 분석 단계의 Action Spec 누락을 점검해줘.",
            "이 SOP의 Event와 Manual Handoff 관계를 표로 다시 정리해줘.",
            "이 흐름을 실행하려면 먼저 확인해야 할 승인 항목을 알려줘.",
        ]

    monkeypatch.setattr(boi_app_module, "agent_chat_response", minimal_agent_response)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_FOLLOWUPS_BLOCKING", True)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 SOP"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert seen_requests
    assert body["suggested_questions_source"] == "answer_scoped_llm"
    assert body["suggested_questions"][0].startswith("이 Mermaid")
    assert body["evidence_ledger"]
    assert body["affordances"]
    assert body["answer_quality"]["followups_generated"] is True


def test_boi_agent_followup_context_includes_private_memory_preferences(boi_app_module, monkeypatch):
    captured: list[Any] = []

    def fake_memory_items(employee_id: str, q: str = "", limit: int = 20, include_archived: bool = False):
        return [
            {
                "memory_id": "boi:private:100001:agent-memory:style",
                "title": "답변 선호",
                "memory_kind": "answer_style",
                "description": "표보다 단계별 체크리스트를 선호합니다.",
                "scope": "private",
                "priority": 100,
                "url": "/docs/boi:private:100001:agent-memory:style?employee_id=100001",
            }
        ]

    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        captured.append(req.answer_context)
        return ["이 내용을 단계별 체크리스트로 정리해줘."]

    monkeypatch.setattr(boi_app_module, "agent_memory_items", fake_memory_items)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)

    req = boi_app_module.BoiAgentChatRequest(
        question="이 SOP 관계를 정리해줘.",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        page_context={"title": "설비 이상 SOP"},
    )
    response = {
        "answer_markdown": "설비 이상 SOP 관계를 정리했습니다.",
        "route": "deep",
        "intent": "workflow_explain",
        "artifacts": [{"type": "workflow_summary", "data": [{"stage": "이상 감지"}]}],
        "links": [],
        "citations": [],
        "suggested_questions": [],
    }

    result = boi_app_module.ensure_agent_answer_followups(req, response, "100001")

    assert result["suggested_questions"] == ["이 내용을 단계별 체크리스트로 정리해줘."]
    assert captured
    assert captured[0]["memory_preferences"][0]["memory_kind"] == "answer_style"
    assert captured[0]["memory_preferences"][0]["scope"] == "private"
    assert "단계별 체크리스트" in captured[0]["memory_preferences"][0]["description"]


def test_boi_agent_followups_drop_repeated_original_question(boi_app_module, monkeypatch):
    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        return [
            "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
            "이 Mermaid 흐름의 근거 문서를 더 자세히 보여줘.",
            "이 프로세스에서 누락된 Action Spec이 있는지 점검해줘.",
        ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)

    req = boi_app_module.BoiAgentChatRequest(
        question="이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        page_context={"title": "설비 이상 SOP"},
    )
    response = {
        "answer_markdown": "SOP Mermaid 다이어그램을 만들었습니다.",
        "route": "deep",
        "intent": "diagram",
        "artifacts": [{"type": "mermaid", "source": "flowchart TD\nA --> B"}],
        "links": [],
        "citations": [],
        "affordances": [{"type": "ask_more", "label": "근거 자세히 보기"}],
        "suggested_questions": [],
    }

    result = boi_app_module.ensure_agent_answer_followups(req, response, "100001")

    assert result["suggested_questions"] == [
        "이 Mermaid 흐름의 근거 문서를 더 자세히 보여줘.",
        "이 프로세스에서 누락된 Action Spec이 있는지 점검해줘.",
    ]


def test_boi_agent_suggestion_normalization_strips_planning_labels(boi_app_module):
    assert (
        boi_app_module.normalize_suggestion_text("Suggestion 1 (Evidence): 방금 답변의 근거가 되는 문서를 더 자세히 보여줘.")
        == "방금 답변의 근거가 되는 문서를 더 자세히 보여줘."
    )
    assert (
        boi_app_module.normalize_suggestion_text("Question 2 (Action): 다음 이벤트 발행 전에 확인할 내용을 정리해줘.")
        == "다음 이벤트 발행 전에 확인할 내용을 정리해줘."
    )


def test_boi_agent_followups_drop_mutation_questions_without_affordance(boi_app_module, monkeypatch):
    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        return [
            "신규 Event Type 초안을 만들어줘.",
            "방금 답변의 근거를 더 자세히 설명해줘.",
        ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)

    req = boi_app_module.BoiAgentChatRequest(
        question="알 수 없는 업무를 자동 처리해줘.",
        current_url="/",
        page_context={"title": "BoI Wiki"},
    )
    response = {
        "answer_markdown": "연결된 WorkflowDefinition이 없어 먼저 업무 흐름 연결이 필요합니다.",
        "route": "deep",
        "intent": "workflow_explain",
        "artifacts": [],
        "links": [],
        "citations": [],
        "affordances": [{"type": "ask_more", "label": "근거 자세히 보기"}],
        "suggested_questions": [],
    }

    result = boi_app_module.ensure_agent_answer_followups(req, response, "100001")

    assert result["suggested_questions"] == ["방금 답변의 근거를 더 자세히 설명해줘."]


def test_boi_agent_followups_retry_when_affordance_filter_removes_all(boi_app_module, monkeypatch):
    captured: list[dict[str, Any]] = []

    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        captured.append(req.answer_context)
        if len(captured) == 1:
            return ["신규 Event Type 초안을 만들어줘."]
        assert req.answer_context["followup_repair"]["previous_error"]
        return ["연결 가능한 WorkflowDefinition 후보를 찾아줘."]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)

    req = boi_app_module.BoiAgentChatRequest(
        question="알 수 없는 업무를 자동 처리해줘.",
        current_url="/",
        page_context={"title": "BoI Wiki"},
    )
    response = {
        "answer_markdown": "연결된 WorkflowDefinition이 없어 먼저 업무 흐름 연결이 필요합니다.",
        "route": "deep",
        "intent": "workflow_explain",
        "artifacts": [],
        "links": [],
        "citations": [],
        "affordances": [{"type": "ask_more", "label": "근거 자세히 보기"}],
        "suggested_questions": [],
    }

    result = boi_app_module.ensure_agent_answer_followups(req, response, "100001")

    assert len(captured) == 2
    assert result["suggested_questions"] == ["연결 가능한 WorkflowDefinition 후보를 찾아줘."]


def test_boi_agent_followups_drop_immediate_mutation_even_with_affordance(boi_app_module, monkeypatch):
    def fake_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        return [
            "업무 요청을 지금 바로 실행해줘.",
            "실행 전에 입력값과 승인 근거를 점검해줘.",
        ]

    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", fake_suggestions)

    req = boi_app_module.BoiAgentChatRequest(
        question="Action 실행해줘.",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        page_context={"title": "설비 이상 SOP"},
    )
    response = {
        "answer_markdown": "실행 전 확인 카드가 필요합니다.",
        "route": "approval_required",
        "intent": "action_invoke",
        "artifacts": [{"type": "confirmation_required", "data": {"operation": "action_invoke"}}],
        "links": [],
        "citations": [],
        "affordances": [{"type": "request_execution", "label": "요청 실행 전 확인"}],
        "execution_cards": [{"operation": "action_invoke", "requires_confirmation": True}],
        "suggested_questions": [],
    }

    result = boi_app_module.ensure_agent_answer_followups(req, response, "100001")

    assert result["suggested_questions"] == ["실행 전에 입력값과 승인 근거를 점검해줘."]


def test_boi_agent_chat_preserves_answer_when_answer_scoped_followups_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def minimal_agent_response(req, employee_id):
        return {
            "ok": True,
            "used_backend": "native_langgraph",
            "answer_markdown": "현재 SOP 근거를 확인했습니다.",
            "route": "fast",
            "intent": "page_qa",
            "suggested_questions": [],
            "suggested_questions_source": "suggestions_endpoint_required",
        }

    def broken_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        raise boi_app_module.BoiAgentSuggestionsUnavailable("answer follow-up model timeout")

    monkeypatch.setattr(boi_app_module, "agent_chat_response", minimal_agent_response)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", broken_suggestions)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_FOLLOWUPS_BLOCKING", True)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "현재 화면 기준으로 설명해줘.",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] == "현재 SOP 근거를 확인했습니다."
    assert body["suggested_questions"] == ["방금 답변의 근거를 더 자세히 설명해줘."]
    assert body["suggested_questions_source"] == "affordance_contract_after_llm_error"
    assert body["answer_quality"]["followups_generated"] is True
    assert "answer follow-up model timeout" in body["answer_quality"]["followups_error"]
    assert body["component_errors"][0]["component"] == "followup_suggestions"


def test_workflow_status_page_context_includes_manual_handoff_details(boi_app_module):
    context = boi_app_module.resolve_agent_page_context(
        "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-agent-manual-context",
        "100001",
    )

    assert context["page_kind"] == "workflow_status"
    assert context["manual_handoff_count"] == 5
    assert len(context["manual_handoffs"]) == 5
    assert "manual.equipment.confirm_alarm_context" in context["manual_handoffs"]
    assert context["manual_action_details"]["manual.equipment.confirm_alarm_context"]["title"]
    assert context["expected_manual_actions"] == context["manual_handoffs"]


def test_boi_agent_workflow_manual_summary_survives_composer_and_followup_failures(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.93,
            "intent": "workflow_explain",
            "reason": "test workflow manual summary",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    def broken_llm(employee_id: str, task: str, payload: dict):
        if task == "compose":
            return {"error": "no_valid_json_answer"}
        return None

    def broken_suggestions(req, employee_id: str, page_context: dict[str, Any]):
        raise boi_app_module.BoiAgentSuggestionsUnavailable("answer follow-up model timeout")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", broken_llm)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", broken_suggestions)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "남은 수동 조치 5건을 일반 업무 관점으로 정리해줘.",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-agent-manual-summary",
            "page_context": {"title": "Workflow Status"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "fast"
    assert body["intent"] == "workflow_explain"
    assert body["response_profile"] == "workflow_manual_summary"
    assert body["goal_model"]["goal_type"] == "workflow_manual_summary"
    assert "수동 조치" in body["answer_markdown"]
    assert "5건" in body["answer_markdown"]
    assert "없" not in body["answer_markdown"]
    summary = next(item for item in body["artifacts"] if item["type"] == "manual_handoff_summary")
    assert len(summary["data"]) == 5
    assert summary["data"][0]["action_key"].startswith("manual.equipment.")
    assert body["answer_quality"]["authoritative_contract"] == "workflow_manual_summary"
    assert body["answer_quality"]["followups_generated"] is True
    assert body["suggested_questions_source"] == "workflow_manual_affordance"
    assert body["context_summary"]["composer_backend"] == "native_structured"
    assert body["component_errors"] == []


def test_boi_agent_workflow_manual_followup_rechecks_source_of_truth(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "fast",
            "confidence": 0.91,
            "intent": "workflow_explain",
            "reason": "test follow-up correction",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", lambda *args, **kwargs: ["남은 조치 중 먼저 볼 항목을 알려줘."])

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "수동 조치 사항이 없다고 한 근거를 더 자세히 알려줘.",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-agent-manual-correction",
            "page_context": {"title": "Workflow Status"},
            "conversation": [
                {"role": "user", "content": "남은 수동 조치 5건을 일반 업무 관점으로 정리해줘."},
                {"role": "assistant", "content": "장비 이상 워크플로우 기준 수동 조치 사항이 없습니다."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "workflow_explain"
    assert "현재 기준" in body["answer_markdown"]
    assert "5건" in body["answer_markdown"]
    assert "수동 조치 사항이 없습니다" not in body["answer_markdown"]


def test_boi_agent_chat_normalizes_execution_cards_to_agent_schema(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def minimal_card_response(req, employee_id):
        return {
            "ok": True,
            "used_backend": "test_minimal_backend",
            "answer_markdown": "이 작업은 실행 전 확인이 필요합니다.",
            "execution_cards": [
                {
                    "operation": "event_publish",
                    "title": "이벤트 발행 확인",
                    "payload": {"event_type": "meeting.closed.v1"},
                    "display": {
                        "status_label": "확인 필요",
                        "risk_label": "명시 확인 후 실행",
                    },
                }
            ],
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", minimal_card_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "meeting.closed.v1 이벤트를 발행해줘", "current_url": "/events"},
    )

    assert response.status_code == 200
    body = response.json()
    schema = client.get("/api/agents/boi-wiki/response-schema").json()["schema"]
    validate(instance=body, schema=schema)
    card = body["execution_cards"][0]
    assert card["contract_version"] == "boi-agent.response.v1"
    assert card["requires_confirmation"] is True
    assert card["user_confirmed_required"] is True
    assert card["approve_url"] == "/api/agents/boi-wiki/approve"
    assert card["display"]["next_action"]
    assert card["technical_details"]["operation"] == "event_publish"


def test_boi_agent_execution_cards_include_required_role_and_permission_decision(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def minimal_card_response(req, employee_id):
        return {
            "ok": True,
            "used_backend": "test_minimal_backend",
            "answer_markdown": "이 작업은 실행 전 확인이 필요합니다.",
            "execution_cards": [
                {
                    "operation": "event_publish",
                    "title": "이벤트 발행 확인",
                    "payload": {"event_type": "meeting.closed.v1"},
                }
            ],
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", minimal_card_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100003",
        json={"question": "meeting.closed.v1 이벤트를 발행해줘", "current_url": "/events"},
    )

    assert response.status_code == 200
    card = response.json()["execution_cards"][0]
    assert card["required_role"] == "boi.workflow_runner"
    assert card["permission"]["allowed"] is False
    assert card["permission"]["role"] == "boi.workflow_runner"
    assert card["display"]["status_label"] == "권한 필요"
    assert "boi.workflow_runner" in card["display"]["risk_label"]
    assert card["technical_details"]["required_role"] == "boi.workflow_runner"


def test_boi_agent_execution_cards_are_acl_sanitized(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unsafe_card_response(req, employee_id):
        return {
            "ok": True,
            "used_backend": "test_minimal_backend",
            "answer_markdown": "다른 사번 private 문서를 근거로 실행할 수 없습니다.",
            "execution_cards": [
                {
                    "operation": "event_publish",
                    "title": "이벤트 발행 확인",
                    "payload": {
                        "event_type": "meeting.closed.v1",
                        "doc_ref": "boi:private:100002:hidden-source",
                    },
                    "technical_details": {
                        "doc_ref": "boi:private:100002:hidden-source",
                    },
                    "display": {
                        "why_it_matters": "[숨김 문서](/docs/boi:private:100002:hidden-source?employee_id=100001)",
                    },
                }
            ],
        }

    monkeypatch.setattr(boi_app_module, "agent_chat_response", unsafe_card_response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "meeting.closed.v1 이벤트를 발행해줘", "current_url": "/events"},
    )

    assert response.status_code == 200
    body = response.json()
    card = body["execution_cards"][0]
    assert "doc_ref" not in card["payload"]
    assert "boi:private:100002" not in json.dumps(card, ensure_ascii=False)
    assert body["redacted_count"] >= 1


def test_boi_agent_fast_summary_preserves_native_structured_answer_when_composer_enabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    compose_calls: list[dict] = []

    def fake_llm(employee_id: str, task: str, payload: dict):
        compose_calls.append({"employee_id": employee_id, "task": task, "payload": payload})
        assert task == "compose"
        return {
            "answer_markdown": "## 답변\n\n- 설비 이상 SOP는 Event, Action, Manual Handoff 근거를 연결합니다.",
            "suggested_questions": ["이 SOP의 부족한 Action Spec을 찾아줘."],
            "composer_contract": "answer_plan",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="summarize")
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
    assert compose_calls == []
    assert body["context_summary"]["composer_backend"] == "native_structured"
    assert body["context_summary"]["composer_error"] == ""
    assert "설비" in body["answer_markdown"]
    assert body["answer_quality"]["authoritative_contract"] == "page_context_summary"


def test_boi_agent_home_summary_preserves_library_page_context_not_search_hit(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    compose_calls: list[dict] = []

    def fake_llm(employee_id: str, task: str, payload: dict):
        compose_calls.append({"employee_id": employee_id, "task": task, "payload": payload})
        assert task == "compose"
        return {
            "answer_markdown": "## BoI Wiki Explorer\n\n문서, SOP, Event, Action을 한 화면에서 탐색하는 첫 화면입니다.",
            "composer_contract": "answer_plan",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="summarize")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "현재 페이지를 한 문장으로 요약해줘",
            "mode": "fast",
            "current_url": "/?employee_id=100001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert compose_calls == []
    assert body["context_summary"]["page_context"]["page_kind"] == "library"
    assert "BoI Wiki" in body["answer_markdown"]
    assert "자유 업무 단위 폴더" in body["answer_markdown"]
    assert "설비 이상 감지" not in body["answer_markdown"]
    assert body["answer_quality"]["authoritative_contract"] == "page_context_summary"


def test_boi_agent_trace_reasoning_uses_llm_composer_when_enabled(boi_app_module, monkeypatch):
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="trace_reasoning")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 trace 리스크를 분석해줘",
            "mode": "deep",
            "intent": "trace_reasoning",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-test-composer",
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


def test_boi_agent_diagram_uses_structured_artifact_with_llm_composer(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    compose_calls: list[dict] = []

    def fake_llm(employee_id: str, task: str, payload: dict):
        compose_calls.append({"employee_id": employee_id, "task": task, "payload": payload})
        assert task == "compose"
        assert "```mermaid" not in payload["structured_draft"]
        assert "structured artifact" in payload["artifact_policy"]["mermaid"]
        return {
            "answer_markdown": "## SOP 프로세스 플로우\n\nSOP 단계와 연결된 Event, Action, Manual Handoff를 업무 관점으로 정리했습니다.",
            "suggested_questions": ["이 SOP의 부족한 Action Spec을 찾아줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="diagram")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

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
    assert compose_calls
    assert body["intent"] == "diagram"
    assert body["context_summary"]["composer_backend"] == "llm"
    assert body["artifacts"][0]["type"] == "mermaid"
    assert any(item.get("type") == "workflow_summary" for item in body["artifacts"])
    assert body["answer_markdown"].startswith("## SOP 프로세스 플로우")
    assert "## 원본 매핑" not in body["answer_markdown"]
    assert "| 단계 | 이벤트 | 업무 요청 | 수동 조치 | 다음 |" not in body["answer_markdown"]
    assert "```mermaid" not in body["display_markdown"]
    assert body["suggested_questions"] == ["이 SOP의 부족한 Action Spec을 찾아줘."]


def test_boi_agent_required_llm_composer_failure_preserves_typed_answer(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def empty_llm(employee_id: str, task: str, payload: dict):
        return None

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="trace_reasoning")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", empty_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 trace 리스크를 분석해줘",
            "mode": "deep",
            "intent": "trace_reasoning",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-test-composer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    assert body["answer_markdown"]
    assert body["component_errors"]
    assert any(item.get("component") == "answer_composer" for item in body["component_errors"])


def test_boi_agent_required_llm_composer_exception_preserves_typed_answer(boi_app_module, monkeypatch):
    from boi_api.app import native_agent

    def invalid_json_llm(task: str, payload: dict):
        raise native_agent.NativeAgentRuntimeUnavailable(
            "LLM answer composer returned invalid final answer: no_valid_json_answer"
        )

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
        llm_json=invalid_json_llm,
    )
    runtime = native_agent.NativeBoiAgent(
        tools,
        native_agent.NativeAgentConfig(
            llm_enabled=False,
            require_langgraph=False,
            composer_enabled=True,
            composer_required=True,
        ),
    )

    body = runtime.run(
        {
            "question": "Trend 확인 근거를 더 자세히 검토해줘",
            "mode": "deep",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-test-composer",
        },
        {"route": "deep", "intent": "trace_reasoning", "router_backend": "test", "confidence": 1.0},
        {
            "page_context": {"resolved": True, "page_kind": "workflow_status", "title": "Workflow Status"},
            "ontology_search_seed": {"ok": True, "best_matches": []},
            "access_summary": {"can_read": True, "can_use_in_agent_context": True},
        },
    )

    assert body["answer_markdown"]
    assert body["component_errors"]
    assert body["component_errors"][0]["component"] == "answer_composer"
    assert body["component_errors"][0]["status"] == "failed"


def test_boi_agent_required_llm_composer_disabled_preserves_typed_answer(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def unexpected_llm(*args, **kwargs):
        raise AssertionError("disabled composer must fail before calling LLM")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="trace_reasoning")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", unexpected_llm)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "이 trace 리스크를 분석해줘",
            "mode": "deep",
            "intent": "trace_reasoning",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-test-composer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    assert body["answer_markdown"]
    assert body["component_errors"]
    assert any(item.get("component") == "answer_composer" for item in body["component_errors"])


def test_boi_agent_chat_fails_when_langgraph_required_but_unavailable(boi_app_module, monkeypatch):
    from boi_api.app import native_agent

    client = TestClient(boi_app_module.app)

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="search")
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="search")
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="search")
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="search")
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


def test_native_agent_page_qa_answers_action_requirement_from_action_spec(monkeypatch):
    from boi_api.app import native_agent

    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)
    doc = {
        "metadata": {
            "boi_id": "boi:public:sop:equipment-abnormal-response",
            "title": "설비 이상 감지 SOP",
            "workflow": {
                "stages": [
                    {
                        "name": "이상 감지",
                        "automated_actions": ["sop.equipment.request_trend_history"],
                    }
                ]
            },
        },
        "access": {"can_cite": True},
        "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    }
    spec = {
        "action_key": "sop.equipment.request_trend_history",
        "url": "/docs/boi:public:actions:api:request-trend-history?employee_id=100001",
        "item": {
            "action_key": "sop.equipment.request_trend_history",
            "name_ko": "품질 시스템 Response Trend 확인 시뮬레이션",
            "description": "품질 시스템 Response Trend 확인",
            "simulated_system": "품질 시스템",
            "real_system_status": "unavailable",
        },
        "doc": {
            "metadata": {
                "title": "품질 시스템 Response Trend 확인 시뮬레이션",
                "action_key": "sop.equipment.request_trend_history",
                "payload_contract": {
                    "required": ["equipment_id"],
                    "optional": ["lot_id", "wafer_id", "alarm_code"],
                },
                "result_contract": {
                    "fields": ["response_series", "frequency", "time_range", "trend_status", "anomaly_basis"],
                },
                "example_request": {"payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-POC-001"}},
                "simulated_system": "품질 시스템",
                "real_system_status": "unavailable",
            }
        },
    }
    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "best_matches": []},
        boi_get=lambda ref: doc,
        event_type_lookup=lambda event_type: None,
        action_spec_lookup=lambda action_key: spec if action_key == "sop.equipment.request_trend_history" else None,
        workflow_status=lambda workflow_key, trace_id: None,
        trace_context_lookup=lambda trace_id: {"ok": True, "events": [], "actions": []},
        dictionary_resolve=lambda query: {"ok": True, "terms": []},
        memory_recall=lambda query, limit=5: {"ok": True, "items": []},
        agent_inbox=lambda limit=10: {"ok": True, "items": []},
        llm_json=lambda task, payload: pytest.fail("Action requirement answer must not depend on LLM composer"),
    )
    runtime = native_agent.NativeBoiAgent(
        tools,
        native_agent.NativeAgentConfig(
            llm_enabled=False,
            require_langgraph=False,
            composer_enabled=True,
            composer_required=True,
        ),
    )

    body = runtime.run(
        {
            "question": "설비 이상 감지 시 Trend 확인을 위해 어떤 데이터가 필요한지 알려줘",
            "mode": "fast",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        },
        {"route": "fast", "intent": "page_qa", "router_backend": "test", "confidence": 1.0},
        {
            "page_context": {
                "resolved": True,
                "boi_id": "boi:public:sop:equipment-abnormal-response",
                "title": "설비 이상 감지 SOP",
            },
            "ontology_search_seed": {"ok": True, "best_matches": []},
            "access_summary": {"can_read": True, "can_use_in_agent_context": True},
        },
    )

    assert body["context_summary"]["composer_backend"] == "native_structured"
    assert "equipment_id" in body["answer_markdown"]
    assert "response_series" in body["answer_markdown"]
    assert "제공된 근거 자료에제시되어 있지 않습니다" not in body["answer_markdown"]
    assert body["artifacts"][0]["type"] == "action_requirements"
    assert body["artifacts"][0]["data"][0]["필수 입력"] == "equipment_id"
    assert body["suggested_questions"]
    assert body["suggested_questions_source"] == "action_spec_affordance"


def test_native_agent_page_qa_answers_missing_evidence_from_report_body(monkeypatch):
    from boi_api.app import native_agent

    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)
    report_body = """
## 결론
승인 전 원본 근거를 보강해야 합니다.

## 개별 비교
- 06-29 22:57 ETCH-VM-01 / LOT-A-240626 / WF-07 · 압력 Spike 현상
- 확인할 일: Raw Data endpoint 확인 후 승인 또는 반려 여부를 결정하세요.

## 판단 근거
- Trend: 이상 (확인됨)
- Raw Data: 확보됨 (확인됨)
- 부족 근거: Raw Data endpoint 확인 (확인 필요)
- 승인 리스크: Spec/Rule 변경 승인 (확인 필요)

## 조치
승인, 반려, 보류, 추가 근거 요청은 BoI Inbox에서 사유를 남기고 기록합니다.
"""
    report_excerpt = " ".join(report_body.split())
    doc = {
        "metadata": {
            "boi_id": "boi:private:100001:report",
            "title": "Spec / Rule 변경 요청 승인 필요",
            "type": "boi/inbox-review-report",
        },
        "body_excerpt": report_excerpt,
        "url": "/docs/boi:private:100001:report?employee_id=100001",
        "access": {"can_cite": True},
    }
    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "best_matches": []},
        boi_get=lambda ref: doc,
        event_type_lookup=lambda event_type: None,
        action_spec_lookup=lambda action_key: None,
        workflow_status=lambda workflow_key, trace_id: None,
        trace_context_lookup=lambda trace_id: {"ok": True, "events": [], "actions": []},
        dictionary_resolve=lambda query: {"ok": True, "terms": []},
        memory_recall=lambda query, limit=5: {"ok": True, "items": []},
        agent_inbox=lambda limit=10: {"ok": True, "items": []},
        llm_json=lambda task, payload: pytest.fail("Report missing evidence QA must not wait for LLM"),
    )
    runtime = native_agent.NativeBoiAgent(
        tools,
        native_agent.NativeAgentConfig(
            llm_enabled=False,
            require_langgraph=False,
            composer_enabled=True,
            composer_required=True,
        ),
    )

    body = runtime.run(
        {
            "question": "이 보고서에서 부족한 근거가 뭐야?",
            "mode": "fast",
            "current_url": "/docs/boi:private:100001:report?employee_id=100001",
        },
        {"route": "fast", "intent": "page_qa", "router_backend": "test", "confidence": 1.0},
        {
            "page_context": {
                "resolved": True,
                "page_kind": "doc",
                "boi_id": "boi:private:100001:report",
                "title": "Spec / Rule 변경 요청 승인 필요",
                "body_excerpt": report_excerpt,
            },
            "ontology_search_seed": {"ok": True, "best_matches": []},
            "access_summary": {"can_read": True, "can_use_in_agent_context": True},
        },
    )

    assert body["context_summary"]["composer_backend"] == "native_structured"
    assert body["answer_quality"]["authoritative_contract"] == "page_context_report_qa"
    assert "Raw Data endpoint 확인" in body["answer_markdown"]
    assert "승인 또는 반려 전에" in body["answer_markdown"]
    assert "현재 화면 **Spec / Rule 변경 요청 승인 필요** 기준으로 요약합니다" not in body["answer_markdown"]
    assert "source_id" not in body["answer_markdown"]


def test_native_agent_related_sop_question_uses_page_affordance_not_report_summary(monkeypatch):
    from boi_api.app import native_agent

    monkeypatch.setattr(native_agent, "StateGraph", None, raising=False)
    doc = {
        "metadata": {
            "boi_id": "boi:private:100001:report",
            "title": "Spec / Rule 변경 요청 승인 필요",
            "type": "boi/inbox-review-report",
        },
        "body_excerpt": "부족 근거: Raw Data endpoint 확인 필요",
        "url": "/docs/boi:private:100001:report?employee_id=100001",
        "access": {"can_cite": True},
    }
    sop_doc = {
        "ok": True,
        "boi_id": "boi:public:sop:equipment-abnormal-response",
        "title": "설비 이상 대응 SOP",
        "description": "설비 이상 감지, 원인 분석, 이상 조치 기준 절차",
        "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        "metadata": {
            "boi_id": "boi:public:sop:equipment-abnormal-response",
            "title": "설비 이상 대응 SOP",
            "type": "boi/sop",
        },
    }
    tools = native_agent.NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: {"ok": True, "best_matches": []},
        boi_get=lambda ref: sop_doc if ref == "boi:public:sop:equipment-abnormal-response" else doc,
        event_type_lookup=lambda event_type: None,
        action_spec_lookup=lambda action_key: None,
        workflow_status=lambda workflow_key, trace_id: None,
        trace_context_lookup=lambda trace_id: {"ok": True, "events": [], "actions": []},
        dictionary_resolve=lambda query: {"ok": True, "terms": []},
        memory_recall=lambda query, limit=5: {"ok": True, "items": []},
        agent_inbox=lambda limit=10: {"ok": True, "items": []},
        llm_json=lambda task, payload: pytest.fail("Related SOP lookup must not wait for LLM"),
    )
    runtime = native_agent.NativeBoiAgent(
        tools,
        native_agent.NativeAgentConfig(
            llm_enabled=False,
            require_langgraph=False,
            composer_enabled=True,
            composer_required=True,
        ),
    )

    body = runtime.run(
        {
            "question": "sop가 뭐있니",
            "mode": "fast",
            "current_url": "/docs/boi:private:100001:report?employee_id=100001",
        },
        {
            "route": "fast",
            "intent": "search",
            "response_profile": "related_items",
            "router_backend": "semantic_hybrid_router",
            "confidence": 0.86,
            "semantic_route": {
                "target_kind": "related_sop",
                "matched_affordance": "related_sop",
                "confidence": 0.86,
            },
        },
        {
            "page_context": {
                "resolved": True,
                "page_kind": "doc",
                "boi_id": "boi:private:100001:report",
                "title": "Spec / Rule 변경 요청 승인 필요",
                "body_excerpt": "부족 근거: Raw Data endpoint 확인 필요",
            },
            "workflow_definition_context": {
                "workflow_definition_key": "equipment-anomaly-response",
                "sop_refs": ["boi:public:sop:equipment-abnormal-response"],
                "action_refs": ["sop.equipment.change_spec_rule"],
                "entry_events": ["equipment.alarm.raised.v1"],
            },
            "ontology_search_seed": {"ok": True, "best_matches": []},
            "access_summary": {"can_read": True, "can_use_in_agent_context": True},
        },
    )

    assert body["intent"] == "search"
    assert body["response_profile"] == "related_items"
    assert body["answer_quality"]["authoritative_contract"] == "related_items_lookup"
    assert "설비 이상 대응 SOP" in body["answer_markdown"]
    assert "직접 연결된 SOP" in body["answer_markdown"]
    assert "현재 화면 **Spec / Rule 변경 요청 승인 필요** 기준으로 요약합니다" not in body["answer_markdown"]
    assert any(link["kind"] == "sop" for link in body["links"])


def test_native_agent_action_requirement_preserves_evidence_requirements():
    from boi_api.app import native_agent

    rows = native_agent.action_contract_rows(
        [
            {
                "item": {
                    "action_key": "manual.direct_development.decide_cross_section",
                    "name_ko": "단면검사 필요 여부 판단",
                },
                "doc": {
                    "metadata": {
                        "payload_contract": {"required": ["event", "payload", "assignee"]},
                        "result_contract": {"fields": ["owner", "checklist", "manual_required"]},
                        "evidence_requirements": [
                            {
                                "evidence_key": "response_trend",
                                "source_action": "direct_development.quality_response_trend.simulate",
                                "required_fields": ["trend_status"],
                                "simulated_allowed": True,
                            },
                            {
                                "evidence_key": "map_view",
                                "source_action": "direct_development.map_view.simulate",
                                "required_fields": ["map_pattern_summary"],
                                "simulated_allowed": True,
                            },
                        ],
                    }
                },
            }
        ]
    )

    row = rows[0]
    assert "response_trend" in row["필수 근거"]
    assert "map_view" in row["필수 근거"]
    assert "trend_status" in row["근거 필드"]
    assert "map_pattern_summary" in row["근거 필드"]
    assert "simulated_prerequisite" in row["시뮬레이션 정책"]


def test_native_agent_workflow_definition_rows_include_event_recommended_actions():
    from boi_api.app import native_agent

    rows = native_agent.workflow_definition_summary_rows(
        {
            "workflow_definition_key": "equipment-anomaly-response",
            "workflow_key": "equipment-anomaly",
            "action_refs": ["sop.equipment.request_trend_history"],
            "emitted_events": ["root_cause.analysis.requested.v1"],
        },
        {
            "event_type": "trend.anomaly.detected.v1",
            "sop_stage_id": "detect",
            "recommended_actions": [
                "sop.equipment.request_trend_history",
                "mcp.timesfm.forecast",
                "sop.equipment.create_root_cause_event",
            ],
            "recommended_manual_actions": ["manual.equipment.confirm_alarm_context"],
        },
    )

    row = rows[0]
    assert "trend.anomaly.detected.v1" in row["events"]
    assert "mcp.timesfm.forecast" in row["actions"]
    assert "manual.equipment.confirm_alarm_context" in row["manual_actions"]


def test_native_agent_approval_route_uses_current_action_spec_payload():
    from boi_api.app import native_agent

    payload = native_agent.confirmation_payload_for_state(
        {
            "route_name": "approval_required",
            "intent": "approval",
            "question": "공정 진행 금지 요청 실행해줘.",
            "current_url": "/docs/boi:public:actions:api:block-process-progress?employee_id=100001",
            "page_context": {
                "action_key": "sop.equipment.block_process_progress",
                "event_type": "corrective_action.requested.v1",
            },
        }
    )

    assert payload["data"]["operation"] == "action_invoke"
    assert payload["data"]["payload"]["action_key"] == "sop.equipment.block_process_progress"
    assert payload["data"]["primary_label"] == "Action 실행"


def test_native_agent_ontology_context_preserves_dictionary_expansion():
    from boi_api.app import native_agent

    context = native_agent.compact_ontology_context(
        {
            "query_expansion": ["Map View", "Response Trend", "mcp.timesfm.forecast"],
            "used_dictionary_terms": [
                {
                    "term": "Map View",
                    "aliases": ["맵뷰"],
                    "related_terms": ["Response Trend"],
                    "maps_to_event_type": "direct_development.map_view.requested.v1",
                    "maps_to_action_key": "direct_development.map_view.simulate",
                    "maps_to_sop": "boi:public:sop:direct-development-reporting",
                }
            ],
            "best_matches": [
                {
                    "kind": "action",
                    "action_key": "direct_development.map_view.simulate",
                    "title": "Map View Image 확인 시뮬레이션",
                    "url": "/docs/boi:public:actions:langflow:direct-development-map-view-simulate",
                }
            ],
        }
    )

    dumped = json.dumps(context, ensure_ascii=False)
    assert "Response Trend" in dumped
    assert "mcp.timesfm.forecast" in dumped
    assert "direct_development.map_view.simulate" in dumped


def test_boi_agent_composer_rejects_degenerate_repetition(boi_app_module):
    answer = "## 요약\n\n" + ("적절-적절-적절 " * 30)
    repeated_phrase = "## 답변\n\narchitecture v0.1 기준입니다. architecture v0.1 기준입니다. architecture v0.1 기준입니다."

    assert boi_app_module.invalid_agent_composer_answer_reason(answer) == "degenerate_repetition"
    assert boi_app_module.invalid_agent_composer_answer_reason("요약입니다. de la vie, de la vie, de la vie") == "degenerate_repetition"
    assert boi_app_module.invalid_agent_composer_answer_reason(repeated_phrase) == "degenerate_repetition"


def test_boi_agent_composer_rejects_mixed_language_noise(boi_app_module):
    mixed_script = (
        "### Spitzenberg (Spitzenberg)ization of Current Page Content\n\n"
        "* **核心 (Core/Core)**: BoI Wiki 내용을 operator/العمليات/оператор 관점으로 정리합니다."
    )
    english_heading = "### Current Page Content\n\n- BoI Wiki 관련 문서는 아래 링크를 확인하세요."

    assert boi_app_module.invalid_agent_composer_answer_reason(mixed_script) == "non_korean_script"
    assert boi_app_module.invalid_agent_composer_answer_reason(english_heading) == "english_dominant_line"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\nBoI Wiki Agent가 SOP와 Action 근거를 한국어로 정리했습니다.") == ""


def test_boi_agent_composer_rejects_broken_json_fence_fragment(boi_app_module):
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n정리했습니다.\n```json way=") == "broken_markdown_fence"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n```json\n{\"answer\":\"x\"}\n```") == "json_fence_fragment"


def test_boi_agent_composer_rejects_korean_hyphen_noise(boi_app_module):
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n업무 지식 베이스리스트-업데이트-리스트") == "korean_hyphen_noise"


def test_boi_agent_composer_rejects_corrupt_model_artifacts(boi_app_module):
    bad = "## 답변\n\nworkflow-key를 de/v1 이벤트에 연결하고 SOP'izationizationization $\\text{_}$ 조각을 포함합니다."

    assert boi_app_module.invalid_agent_composer_answer_reason(bad) == "corrupt_model_artifact"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n업무 지식을-") == "dangling_hyphen_fragment"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n정리했습니다. thought_process: {") == "corrupt_model_artifact"
    assert boi_app_module.invalid_agent_composer_answer_reason("## 답변\n\n정리 중 <|channel> 조각") == "corrupt_model_artifact"


def test_boi_agent_deep_summarize_relation_question_overrides_to_workflow_explain(boi_app_module):
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
    assert fixed["router_backend"] == "llm"
    assert fixed["goal_model"]["goal_type"] == "workflow_relationship_summary"
    assert fixed["response_profile"] == "workflow_summary"


def test_boi_agent_relation_table_show_request_is_not_search(boi_app_module):
    question = "이 SOP의 Event, Action, Manual Handoff 관계를 표로 보여줘."
    request = boi_app_module.BoiAgentChatRequest(
        question=question,
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    )
    route = {
        "route": "fast",
        "intent": "search",
        "confidence": 0.98,
        "router_backend": "llm",
    }

    fixed = boi_app_module.apply_agent_route_overrides(request, route)
    assert fixed["route"] == "deep"
    assert fixed["intent"] == "workflow_explain"
    assert fixed["goal_model"]["goal_type"] == "workflow_relationship_summary"
    assert fixed["response_profile"] == "workflow_summary"


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


def test_doc_access_rejects_private_docs_missing_required_acl_fields(boi_app_module):
    client = TestClient(boi_app_module.app)

    cases = [
        (
            "boi:private:100001:missing-owner-policy-test",
            {
                "acl_policy": "acl:private:100001",
            },
            "private owner is required",
        ),
        (
            "boi:private:100001:missing-acl-policy-test",
            {
                "owner": "100001",
            },
            "private acl_policy is required",
        ),
    ]
    for boi_id, required_field_subset, expected_reason in cases:
        metadata = {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": f"Malformed Private ACL {boi_id}",
            "description": "private docs must declare owner and acl_policy explicitly",
            "tags": ["ACL"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "author": {"type": "agent", "agent_id": "pytest"},
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "acl-required-fields"}],
        }
        metadata.update(required_field_subset)
        path = boi_app_module.DATA_ROOT / "private" / "100001" / f"{boi_app_module.safe_filename(boi_id)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            boi_app_module.compose_markdown(metadata, "# Summary\n\nmalformed private ACL fixture"),
            encoding="utf-8",
        )

        boi_app_module.invalidate_doc_caches()
        response = client.get(f"/api/docs/{boi_id}/access?employee_id=100001")

        assert response.status_code == 200
        access = response.json()["access"]
        assert access["can_read"] is False
        assert expected_reason in access["reasons"]


def test_doc_access_rejects_team_docs_missing_required_acl_fields(boi_app_module):
    client = TestClient(boi_app_module.app)

    cases = [
        (
            "boi:team:platform:missing-team-id-policy-test",
            {
                "acl_policy": "acl:team:platform",
            },
            "team_id is required",
        ),
        (
            "boi:team:platform:missing-team-acl-policy-test",
            {
                "team_id": "platform",
            },
            "team acl_policy is required",
        ),
    ]
    for boi_id, required_field_subset, expected_reason in cases:
        metadata = {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": f"Malformed Team ACL {boi_id}",
            "description": "team docs must declare team_id and acl_policy explicitly",
            "tags": ["ACL"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "team",
            "classification": "internal",
            "owner": "platform",
            "author": {"type": "agent", "agent_id": "pytest"},
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "team-acl-required-fields"}],
        }
        metadata.update(required_field_subset)
        path = boi_app_module.DATA_ROOT / "team" / "platform" / f"{boi_app_module.safe_filename(boi_id)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            boi_app_module.compose_markdown(metadata, "# Summary\n\nmalformed team ACL fixture"),
            encoding="utf-8",
        )

        boi_app_module.invalidate_doc_caches()
        response = client.get(f"/api/docs/{boi_id}/access?employee_id=100001")

        assert response.status_code == 200
        access = response.json()["access"]
        assert access["can_read"] is False
        assert expected_reason in access["reasons"]


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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="diagram")
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="fast", intent="page_qa")
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


def test_boi_agent_final_response_normalizes_hostless_app_links(boi_app_module):
    response = {
        "answer_markdown": (
            "참고: [배포 문서](https:///docs/boi:public:boi-wiki-manual:agent:deployment-and-verification"
            "?employee_id=100001)\brr\n"
            "외부: [OpenAI](https://example.com/docs)"
        ),
        "links": [
            {
                "label": "배포 문서",
                "url": "https:///docs/boi:public:boi-wiki-manual:agent:deployment-and-verification?employee_id=100001",
            },
            {"label": "외부", "url": "https://example.com/docs"},
        ],
        "citations": [],
        "artifacts": [],
        "suggested_questions": [],
        "tool_trace": [],
        "context_summary": {},
    }

    redactions = boi_app_module.sanitize_agent_final_references(response, "100001")
    body = boi_app_module.enrich_agent_answer_html(response, "100001")
    dumped = json.dumps(body, ensure_ascii=False)

    assert redactions == 0
    assert "https:///" not in dumped
    assert "\b" not in body["answer_markdown"]
    assert "](/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification" in body["answer_markdown"]
    assert body["links"][0]["url"].startswith("/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification")
    assert body["links"][1]["url"] == "https://example.com/docs"
    assert 'href="/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification' in body["answer_html"]


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
    assert 'pattern="[0-9]{7}"' in response.text
    assert "7자리 사번 또는 team_id" in response.text
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


def test_rbac_team_member_requires_seven_digit_employee_id(boi_app_module):
    client = TestClient(boi_app_module.app)
    team_id = "pytest-seven-digit-team"

    created = client.post(
        "/api/rbac/teams?employee_id=100001",
        json={"team_id": team_id, "display_name": "Seven Digit Team"},
    )
    six_digit = client.post(
        f"/api/rbac/teams/{team_id}/members?employee_id=100001",
        json={"employee_id": "123456", "role": "member", "action": "add"},
    )
    seven_digit = client.post(
        f"/api/rbac/teams/{team_id}/members?employee_id=100001",
        json={"employee_id": "1234567", "role": "member", "action": "add"},
    )

    assert created.status_code == 200
    assert six_digit.status_code == 400
    assert "7 digits" in six_digit.text
    assert seven_digit.status_code == 200
    assert "1234567" in seven_digit.json()["team"]["members"]
    assert "123456" not in seven_digit.json()["team"]["members"]


def test_rbac_employee_role_binding_requires_seven_digit_subject_id(boi_app_module):
    client = TestClient(boi_app_module.app)

    invalid_employee = client.post(
        "/api/rbac/bindings?employee_id=100001",
        json={"subject_type": "employee", "subject_id": "123456", "roles": ["boi.viewer"]},
    )
    valid_employee = client.post(
        "/api/rbac/bindings?employee_id=100001",
        json={"subject_type": "employee", "subject_id": "1234567", "roles": ["boi.viewer"]},
    )
    team_binding = client.post(
        "/api/rbac/bindings?employee_id=100001",
        json={"subject_type": "team", "subject_id": "pytest-rbac-team", "roles": ["boi.viewer"]},
    )

    assert invalid_employee.status_code == 400
    assert "7 digits" in invalid_employee.text
    assert valid_employee.status_code == 200
    assert valid_employee.json()["binding"]["subject_id"] == "1234567"
    assert team_binding.status_code == 200
    assert team_binding.json()["binding"]["subject_id"] == "pytest-rbac-team"


def test_rbac_audit_api_requires_manager_and_supports_filters(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_rbac_audit("100001", "pytest_audit_visible", {"team_id": "pytest-audit"})
    boi_app_module.append_rbac_audit("100002", "pytest_audit_other", {"team_id": "pytest-audit"})

    allowed = client.get("/api/rbac/audit?employee_id=100001&action=pytest_audit_visible&limit=5")
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["count"] == 1
    assert body["items"][0]["action"] == "pytest_audit_visible"
    assert body["items"][0]["actor"] == "100001"

    monkeypatch.setattr(boi_app_module, "rbac_can_manage", lambda _employee_id, **_kwargs: False)
    denied = client.get("/api/rbac/audit?employee_id=100003")
    assert denied.status_code == 403


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
    assert draft["draft_boi_id"].startswith("boi:private:100001:")
    draft_doc = client.get(f"/api/docs/{draft['draft_boi_id']}/access?employee_id=100001")
    assert draft_doc.status_code == 200
    assert draft_doc.json()["access"]["can_read"] is True
    denied_doc = client.get(f"/api/docs/{draft['draft_boi_id']}/access?employee_id=100002")
    assert denied_doc.status_code == 200
    assert denied_doc.json()["access"]["can_read"] is False
    assert boi_app_module.get_event_type(event_type) is None

    validate = client.post(f"/api/event-types/drafts/{draft['draft_id']}/validate?employee_id=100001")
    assert validate.status_code == 200
    assert validate.json()["draft"]["validation"]["valid"] is True


def test_event_type_draft_apply_updates_catalog_after_confirmation(boi_app_module, monkeypatch, tmp_path):
    catalog_root = tmp_path / "event_catalog"
    catalog_root.mkdir(parents=True)
    catalog_path = catalog_root / "event_types.yaml"
    catalog_path.write_text("event_types: []\n", encoding="utf-8")
    monkeypatch.setattr(boi_app_module, "EVENT_CATALOG_ROOT", catalog_root)
    monkeypatch.setenv("BOI_EDIT_REQUIRE_COMMIT", "false")
    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda _employee_id: ["boi.viewer", "boi.editor", "boi.promoter"],
    )
    boi_app_module.invalidate_catalog_caches()
    client = TestClient(boi_app_module.app)
    event_type = "pytest.applied.event.requested.v1"

    created = client.post(
        "/api/event-types/drafts?employee_id=100001",
        json={
            "event_type": event_type,
            "name_ko": "적용 이벤트",
            "description": "draft 검증 후 catalog에 반영되는 이벤트",
            "workflow_stage": "적용 검증",
            "sop_stage_id": "apply_check",
            "wiki_usage": "draft apply 검증용 event type",
            "recommended_actions": ["boi.materialize_event"],
            "recommended_manual_actions": ["manual.equipment.confirm_alarm_context"],
            "user_confirmed": True,
        },
    )
    draft_id = created.json()["draft"]["draft_id"]
    unconfirmed = client.post(f"/api/event-types/drafts/{draft_id}/apply?employee_id=100001", json={})
    applied = client.post(
        f"/api/event-types/drafts/{draft_id}/apply?employee_id=100001",
        json={"user_confirmed": True, "note": "catalog apply test"},
    )
    repeated = client.post(
        f"/api/event-types/drafts/{draft_id}/apply?employee_id=100001",
        json={"user_confirmed": True, "note": "catalog apply test"},
    )

    assert created.status_code == 200
    assert unconfirmed.status_code == 400
    assert applied.status_code == 200
    body = applied.json()
    assert body["status"] == "applied"
    assert body["draft"]["status"] == "applied"
    assert body["draft"]["catalog_entry"]["event_type"] == event_type
    assert body["draft"]["catalog_entry"]["sop_stage_id"] == "apply_check"
    assert body["draft"]["catalog_entry"]["recommended_manual_actions"] == ["manual.equipment.confirm_alarm_context"]
    draft_boi_id = body["draft"]["draft_boi_id"]
    draft_doc = boi_app_module.find_doc_by_id(draft_boi_id, "100001", include_inaccessible=True)
    assert draft_doc is not None
    draft_metadata = draft_doc["metadata"]
    assert draft_metadata["status"] == "reviewed"
    assert draft_metadata["event_type_draft_status"] == "applied"
    assert draft_metadata["catalog_entry"]["event_type"] == event_type
    assert draft_metadata["apply_result"]["status"] == "applied"
    assert "catalog 반영 완료 기록" in draft_doc["body"]
    assert "# Apply Result" in draft_doc["body"]
    owner_access = client.get(f"/api/docs/{draft_boi_id}/access?employee_id=100001")
    other_access = client.get(f"/api/docs/{draft_boi_id}/access?employee_id=100002")
    assert owner_access.status_code == 200
    assert owner_access.json()["access"]["can_read"] is True
    assert other_access.status_code == 200
    assert other_access.json()["access"]["can_read"] is False
    assert body["apply_result"]["status"] == "applied"
    assert body["apply_result"]["commit_status"] in {"disabled", "unavailable", "unchanged", "committed"}
    assert boi_app_module.get_event_type(event_type)["name_ko"] == "적용 이벤트"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    entry = next(item for item in catalog["event_types"] if item["event_type"] == event_type)
    assert entry["wiki_usage"] == "draft apply 검증용 event type"
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "already_applied"


def test_boi_agent_approve_can_apply_event_type_draft(boi_app_module, monkeypatch, tmp_path):
    catalog_root = tmp_path / "event_catalog"
    catalog_root.mkdir(parents=True)
    (catalog_root / "event_types.yaml").write_text("event_types: []\n", encoding="utf-8")
    monkeypatch.setattr(boi_app_module, "EVENT_CATALOG_ROOT", catalog_root)
    monkeypatch.setenv("BOI_EDIT_REQUIRE_COMMIT", "false")
    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda _employee_id: ["boi.viewer", "boi.editor", "boi.promoter"],
    )
    boi_app_module.invalidate_catalog_caches()
    client = TestClient(boi_app_module.app)
    event_type = "pytest.agent.apply.requested.v1"

    created = client.post(
        "/api/event-types/drafts?employee_id=100001",
        json={
            "event_type": event_type,
            "name_ko": "Agent 적용 이벤트",
            "description": "Agent approve로 catalog에 반영되는 이벤트",
            "workflow_stage": "Agent 적용",
            "user_confirmed": True,
        },
    )
    draft_id = created.json()["draft"]["draft_id"]
    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "event_type_draft_apply",
            "user_confirmed": True,
            "note": "agent approved event type apply",
            "payload": {"draft_id": draft_id},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "event_type_draft_apply"
    assert body["status"] == "applied"
    assert boi_app_module.get_event_type(event_type)["workflow_stage"] == "Agent 적용"


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
    draft = response.json()["draft"]
    assert boi_app_module.get_event_type(event_type) is None

    page = client.get("/event-types?employee_id=100001")
    assert page.status_code == 200
    assert "신규 이벤트 유형 초안" in page.text
    assert event_type in page.text
    assert "운영 목록에는 아직 반영되지 않음" in page.text
    assert "검증 완료" in page.text
    assert "Private draft BoI 보기" in page.text
    assert f"/docs/{draft['draft_boi_id']}?employee_id=100001" in page.text

    other_employee = client.get("/event-types?employee_id=100003")
    assert other_employee.status_code == 200
    assert event_type not in other_employee.text


def test_event_type_draft_validate_rejects_invisible_draft_even_for_editor(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    created = client.post(
        "/api/event-types/drafts?employee_id=100001",
        json={
            "event_type": "pytest.invisible.validate.requested.v1",
            "name_ko": "보이지 않는 검증 초안",
            "description": "작성자나 admin이 아닌 editor는 검증 상태를 바꾸면 안 됨",
            "workflow_stage": "초안 검토",
            "user_confirmed": True,
        },
    )
    assert created.status_code == 200
    draft_id = created.json()["draft"]["draft_id"]

    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda employee_id: ["boi.viewer", "boi.editor"] if employee_id == "100003" else ["boi.viewer", "boi.editor"],
    )

    response = client.post(f"/api/event-types/drafts/{draft_id}/validate?employee_id=100003")

    assert response.status_code == 403
    assert "not visible" in response.text
    draft = json.loads(boi_app_module.event_type_draft_path(draft_id).read_text(encoding="utf-8"))
    assert draft.get("validated_by") != "100003"


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
    assert "업무 이벤트 발행" in event_card["title"]

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
    assert "SOP 업무 흐름 시작" in workflow_card["title"]

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
    assert "Action 실행" in action_card["title"]


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
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LATENCY_MODE", "blocking")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", False)
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


def test_boi_agent_required_router_disabled_still_enters_native_agent(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    received_routes: list[dict[str, Any]] = []

    def fake_native_agent(req, employee_id: str, route, started_at, progress_callback=None):
        received_routes.append(route)
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\nSOP 문서를 기준으로 답변합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_BACKEND", "native")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_native_boi_agent", fake_native_agent)
    monkeypatch.setattr(boi_app_module, "ensure_agent_answer_followups", lambda req, response, employee_id: response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["used_backend"] == "native_langgraph"
    assert received_routes
    assert received_routes[0]["router_backend"] in {"native_goal_router", "agent_goal_registry"}
    assert received_routes[0]["component_errors"][0]["component"] == "router"
    assert received_routes[0]["component_errors"][0]["status"] == "boi_agent_router_unavailable"


def test_boi_agent_goal_profile_registry_routes_new_semiconductor_goal_without_code_branch(boi_app_module, monkeypatch):
    custom_profiles = [
        {
            "goal_type": "semiconductor_yield_review",
            "intent": "page_qa",
            "route": "fast",
            "response_profile": "qa",
            "description": "Answer semiconductor yield review questions.",
            "match": {
                "keywords": ["수율", "스크랩", "불량률"],
                "page_kinds": ["doc"],
            },
        }
    ]
    monkeypatch.setattr(boi_app_module, "load_agent_goal_profiles", lambda: custom_profiles, raising=False)
    request = boi_app_module.BoiAgentChatRequest(
        question="수율 스크랩 기준을 현재 문서 기준으로 알려줘",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    )

    route = boi_app_module.deterministic_agent_route_for_request(request)

    assert route["route"] == "fast"
    assert route["intent"] == "page_qa"
    assert route["response_profile"] == "qa"
    assert route["goal_model"]["goal_type"] == "semiconductor_yield_review"
    assert route["router_backend"] == "agent_goal_registry"


def test_boi_agent_mutation_intent_not_swallowed_by_page_profile(boi_app_module):
    request = boi_app_module.BoiAgentChatRequest(
        question="api.equipment.request_trend_history Action 실행해줘.",
        current_url="/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
    )

    route = boi_app_module.deterministic_agent_route_for_request(request)

    assert route["route"] == "approval_required"
    assert route["intent"] == "action_invoke"
    assert "goal_model" not in route or route["goal_model"].get("goal_type") != "page_question_answer"


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

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        assert payload["intent"] == "diagram"
        return {
            "answer_markdown": "## SOP 흐름 도식\n\nAgent가 SOP 근거를 확인해 Mermaid artifact와 함께 정리했습니다.",
            "suggested_questions": ["이 SOP의 Action Spec 누락을 확인해줘."],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "call_langflow_boi_agent", fail_langflow)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

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
    assert "request_raw_data" in body["artifacts"][0]["source"]
    assert "confirm_alarm_context" in body["artifacts"][0]["source"]
    assert "업무 이벤트" not in body["artifacts"][0]["source"]
    assert body["context_summary"]["composer_backend"] == "llm"
    assert any(item.get("type") == "workflow_summary" for item in body["artifacts"])
    assert "```mermaid" not in body["answer_markdown"]
    assert "```mermaid" not in body["display_markdown"]
    assert "## 원본 매핑" not in body["answer_markdown"]
    assert "| 단계 | 이벤트 | 업무 요청 | 수동 조치 | 다음 |" not in body["answer_markdown"]
    assert "SOP 근거" in body["display_markdown"]
    assert "answer_html" in body
    assert "```mermaid" not in body["answer_html"]
    assert "mermaid-diagram" not in body["answer_html"]


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

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        assert payload["intent"] == "diagram"
        return {
            "answer_markdown": "## 설비 이상 SOP 프로세스 플로우\n\n설비 이상 감지 SOP를 현재 검색 결과에서 찾아 Mermaid artifact로 정리했습니다.",
            "suggested_questions": [],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

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
    assert body["suggested_questions"]
    assert body["suggested_questions_source"] == "answer_scoped_llm"


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

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        assert payload["intent"] == "workflow_explain"
        return {
            "answer_markdown": "## Event, Action, Manual Handoff 관계\n\nAgent가 SOP metadata와 Action Spec 근거를 확인해 관계 표 artifact로 정리했습니다.",
            "suggested_questions": [],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

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
    assert body["context_summary"]["composer_backend"] == "native_structured"
    assert "관계 요약" in body["answer_markdown"]
    assert body["answer_quality"]["authoritative_contract"] == "workflow_summary"
    assert any(item.get("type") == "workflow_summary" for item in body["artifacts"])


def test_boi_agent_event_question_uses_workflow_definition_context(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_router(req, employee_id: str):
        return {
            "route": "deep",
            "confidence": 0.96,
            "intent": "workflow_explain",
            "reason": "event to workflow definition question",
            "requires_mutation": False,
            "requires_deep_reasoning": True,
            "requires_langflow": False,
            "router_backend": "llm",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "equipment.alarm.raised.v1 이벤트가 발생하면 뭘 해야 해?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_context"]["event_type"] == "equipment.alarm.raised.v1"
    assert body["workflow_definition_context"]["workflow_definition_key"] == "equipment-anomaly-response"
    assert body["workflow_definition_context"]["workflow_engine"] == "event_native"
    assert "Event" in body["answer_markdown"]
    assert "|---|" not in body["answer_markdown"]
    assert any(item.get("type") == "workflow_summary" for item in body["artifacts"])
    workflow_artifact = next(item for item in body["artifacts"] if item.get("type") == "workflow_summary")
    assert "sop.equipment.request_trend_history" in json.dumps(workflow_artifact, ensure_ascii=False)
    assert any(item.get("skill_key") == "event.publish" for item in body["affordances"])


def test_boi_agent_router_parser_accepts_reasoning_content_json(boi_app_module):
    payload = boi_app_module.parse_router_payload(
        'thinking about policy {"allowed_routes":["fast"]} final {"route":"fast","confidence":0.92,"intent":"lookup"}'
    )

    assert payload is not None
    assert payload["route"] == "fast"
    assert payload["confidence"] == 0.92


def test_boi_agent_composer_parser_accepts_json_contract_not_plain_markdown(boi_app_module):
    alias_payload = boi_app_module.parse_agent_compose_payload('{"answer":"## 답변\\n근거를 기준으로 정리했습니다."}')
    plan_payload = boi_app_module.parse_agent_compose_payload(
        '{"title":"답변","summary":"근거를 기준으로 정리했습니다.","bullets":[{"text":"SOP와 Action을 연결합니다."}]}'
    )
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
    assert plan_payload["answer_plan"]["title"] == "답변"
    assert plan_payload["answer_plan"]["bullets"] == []
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


def test_boi_agent_composer_llm_requests_answer_plan_schema(boi_app_module, monkeypatch):
    payloads: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"답변","summary":"현재 화면 근거를 기준으로 정리했습니다.",'
                                '"suggested_question_1":"다음 질문"}'
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

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            payloads.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_BASE_URL", "http://composer.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    result = boi_app_module.call_boi_agent_composer_llm(
        {
            "structured_draft": "## 초안" + (" 긴 근거" * 800),
            "large_unused": "x" * 5000,
            "page_context": {
                "page_kind": "doc",
                "title": "설비 SOP",
                "body_excerpt": "# Summary\n| 단계 | 내용 |\n| --- | --- |\n| 감지 | [링크](/docs/x) |",
            },
        },
        "100001",
    )

    assert result["answer_markdown"].startswith("## 답변")
    assert "현재 화면 근거" in result["answer_markdown"]
    assert result["composer_contract"] == "answer_plan"
    assert payloads[0]["json"]["response_format"]["type"] == "json_schema"
    assert payloads[0]["json"]["response_format"]["json_schema"]["name"] == "boi_agent_answer_plan"
    schema = payloads[0]["json"]["response_format"]["json_schema"]["schema"]
    assert "answer_markdown" not in schema["properties"]
    assert "direct_answer" in schema["properties"]
    assert "evidence_used" in schema["properties"]
    assert "what_to_check_next" in schema["properties"]
    assert "links_or_actions" in schema["properties"]
    assert "title" in schema["required"]
    assert payloads[0]["json"]["max_tokens"] >= 256
    user_payload = json.loads(payloads[0]["json"]["messages"][1]["content"])
    assert "large_unused" not in user_payload
    assert "structured_draft" in user_payload
    assert len(user_payload["structured_draft"]) > 900
    assert "긴 근거" in user_payload["structured_draft"]
    assert user_payload["evidence_summary"]
    assert user_payload["page_context"]["title"] == "설비 SOP"
    assert "body_excerpt" not in user_payload["page_context"]


def test_boi_agent_composer_payload_preserves_report_evidence_detail(boi_app_module):
    body = boi_app_module.boi_agent_composer_request_body(
        {
            "question": "부족한 근거가 뭐야?",
            "route": "fast",
            "intent": "page_qa",
            "structured_draft": (
                "## 결론\n\n승인 전 Raw Data endpoint 확인이 필요합니다.\n\n"
                "## 판단 근거\n\nTrend는 확보됐지만 Raw Data 링크가 없고, "
                "Spec/Rule 변경 승인 전 원본 데이터를 먼저 대조해야 합니다."
            ),
            "current_doc": {
                "title": "Inbox 검토 보고서",
                "boi_id": "boi:private:100001:report",
                "body_excerpt": "부족 근거: Raw Data endpoint 확인 필요",
            },
            "page_context": {"page_kind": "doc", "title": "Inbox 검토 보고서"},
        },
        "100001",
    )

    user_payload = json.loads(body["messages"][1]["content"])
    assert "Raw Data endpoint 확인" in user_payload["structured_draft"]
    assert user_payload["current_doc"]["title"] == "Inbox 검토 보고서"
    assert user_payload["question"] == "부족한 근거가 뭐야?"


def test_boi_agent_composer_merge_preserves_page_qa_structured_details():
    from boi_api.app.native_agent import merge_composer_answer_with_structured_details

    merged = merge_composer_answer_with_structured_details(
        "page_qa",
        "## 답변\n\n승인 전 근거 확인이 필요합니다.",
        "## 판단 근거\n\nRaw Data endpoint 확인 후 Spec/Rule 변경 승인 여부를 판단하세요.",
    )

    assert "승인 전 근거 확인" in merged
    assert "Raw Data endpoint 확인" in merged


def test_boi_agent_composer_llm_skips_mixed_language_candidate(boi_app_module, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"Current Page Content","summary":"核心: operator/العمليات/оператор 설명입니다."}'
                            )
                        }
                    },
                    {
                        "message": {
                            "content": '{"title":"답변","summary":"BoI Wiki Agent가 확인한 SOP 근거를 한국어로 정리했습니다.","suggested_question_1":"관련 Action도 볼까요?"}'
                        }
                    },
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_BASE_URL", "http://composer.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    result = boi_app_module.call_boi_agent_composer_llm({"structured_draft": "## 초안"}, "100001")

    assert result["answer_markdown"].startswith("## 답변")
    assert "Current Page Content" not in result["answer_markdown"]
    assert result["suggested_questions"] == ["관련 Action도 볼까요?"]


def test_boi_agent_composer_llm_repairs_invalid_first_response(boi_app_module, monkeypatch):
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            calls.append(json)
            if len(calls) == 1:
                return FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"title":"Current Page Content","summary":"核心: operator/العمليات/оператор 설명입니다."}'
                                    )
                                }
                            }
                        ]
                    }
                )
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"title":"답변","summary":"현재 페이지의 BoI Wiki 내용을 한국어 업무 문장으로 정리했습니다."}'
                            }
                        }
                    ]
                }
            )

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_BASE_URL", "http://composer.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    result = boi_app_module.call_boi_agent_composer_llm({"structured_draft": "## 초안"}, "100001")

    assert len(calls) == 2
    assert "quality_repair" not in json.loads(calls[0]["messages"][1]["content"])
    assert json.loads(calls[1]["messages"][1]["content"])["quality_repair"]["previous_rejection_reasons"] == ["non_korean_script"]
    assert result["quality_repair_used"] is True
    assert result["answer_markdown"].startswith("## 답변")


def test_boi_agent_composer_llm_rejects_markdown_fence_inside_answer_plan(boi_app_module, monkeypatch):
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            calls.append(json)
            if len(calls) == 1:
                return FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"title":"답변","summary":"```json way="}'
                                }
                            }
                        ]
                    }
                )
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"title":"답변","summary":"서버가 Markdown을 렌더링할 수 있는 구조화 요약입니다."}'
                            }
                        }
                    ]
                }
            )

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_BASE_URL", "http://composer.example/v1")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_API_KEY", "dummy")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MODEL", "google/gemma-4-26b-a4b-qat")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(boi_app_module.httpx, "Client", FakeClient)

    result = boi_app_module.call_boi_agent_composer_llm({"structured_draft": "## 초안"}, "100001")

    assert len(calls) == 2
    assert json.loads(calls[1]["messages"][1]["content"])["quality_repair"]["previous_rejection_reasons"] == [
        "broken_markdown_fence"
    ]
    assert result["composer_contract"] == "answer_plan"
    assert "```json" not in result["answer_markdown"]


def test_boi_agent_chat_router_failure_records_diagnostic_and_answers_when_required(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    received_routes: list[dict[str, Any]] = []

    def broken_router(req, employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("router timeout")

    def fake_native_agent(req, employee_id: str, route, started_at, progress_callback=None):
        received_routes.append(route)
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\n라우터 장애와 무관하게 현재 문서 근거로 답변합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LATENCY_MODE", "blocking")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", broken_router)
    monkeypatch.setattr(boi_app_module, "call_native_boi_agent", fake_native_agent)
    monkeypatch.setattr(boi_app_module, "ensure_agent_answer_followups", lambda req, response, employee_id: response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["component_errors"][0]["component"] == "router"
    assert body["component_errors"][0]["status"] == "boi_agent_router_unavailable"
    assert body["component_errors"][0]["recoverable"] is True
    assert received_routes[0]["router_backend"] in {"native_goal_router", "agent_goal_registry"}


def test_boi_agent_chat_router_failure_is_recoverable_when_required_flag_disabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def broken_router(req, employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("router timeout")

    def fake_native_agent(req, employee_id: str, route, started_at, progress_callback=None):
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\nNative Agent가 계속 답변합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_LATENCY_MODE", "blocking")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", broken_router)
    monkeypatch.setattr(boi_app_module, "call_native_boi_agent", fake_native_agent)
    monkeypatch.setattr(boi_app_module, "ensure_agent_answer_followups", lambda req, response, employee_id: response)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={"question": "SOP 찾아줘", "current_url": "/"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["component_errors"][0]["component"] == "router"
    assert body["component_errors"][0]["status"] == "boi_agent_router_unavailable"


def test_boi_agent_explicit_modes_use_request_hint_not_llm_router(boi_app_module, monkeypatch):
    calls: list[str] = []

    def fake_router(req, employee_id: str):
        calls.append(req.mode)
        raise boi_app_module.BoiAgentRouterUnavailable("router should not run for explicit mode")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", fake_router)

    fast_req = boi_app_module.BoiAgentChatRequest(question="현재 페이지를 요약해줘", mode="fast", current_url="/")
    fast_route = boi_app_module.route_boi_agent_request(fast_req, "100001")

    deep_req = boi_app_module.BoiAgentChatRequest(question="현재 페이지를 더 분석해줘", mode="deep", current_url="/")
    deep_route = boi_app_module.route_boi_agent_request(deep_req, "100001")

    assert calls == []
    assert fast_route["router_backend"] == "request_hint"
    assert fast_route["route"] == "fast"
    assert "client requested fast mode" in fast_route["reason"]
    assert deep_route["router_backend"] == "request_hint"
    assert deep_route["route"] == "deep"
    assert deep_route["intent"] == "page_qa"
    assert "client requested deep mode" in deep_route["reason"]


def test_boi_agent_explicit_fast_search_does_not_fail_on_low_router_confidence(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def low_confidence_router(req, employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("LLM router confidence is below threshold")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", False)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", low_confidence_router)

    response = client.post(
        "/api/agents/boi-wiki/chat?employee_id=100001",
        json={
            "question": "SOP",
            "mode": "fast",
            "intent": "search",
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "save_memory": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "fast"
    assert body["intent"] == "search"
    assert body["router_backend"] == "request_hint"


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


def test_boi_agent_router_network_failure_records_diagnostic_backoff_when_required(boi_app_module, monkeypatch):
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
    first_route = boi_app_module.route_boi_agent_request(request, "100001")
    second_route = boi_app_module.route_boi_agent_request(request, "100001")
    assert calls["post"] == 1
    assert first_route["component_errors"][0]["status"] == "boi_agent_router_unavailable"
    assert "router unavailable" in first_route["component_errors"][0]["message"]
    assert second_route["component_errors"][0]["status"] == "boi_agent_router_unavailable"
    assert "backoff active" in second_route["component_errors"][0]["message"]


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
            "question": "장비 점검 완료 이벤트 유형 maintenance.inspection.completed.v1 초안을 만들어줘. 작업자는 7자리 사번이고 SOP는 설비 이상 감지 SOP와 연결해줘.",
            "current_url": "/event-types?employee_id=100001",
            "page_context": {"title": "Event Types"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "approval_required"
    assert body["intent"] == "event_type_draft"
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    artifact = body["artifacts"][0]
    assert artifact["type"] == "confirmation_required"
    assert body["execution_cards"][0]["operation"] == "event_type_draft"
    assert body["execution_cards"][0]["requires_confirmation"] is True
    assert body["execution_cards"][0]["user_confirmed_required"] is True
    assert body["execution_cards"][0]["approve_url"] == "/api/agents/boi-wiki/approve"
    assert body["execution_cards"][0]["contract_version"] == "boi-agent.response.v1"
    assert body["execution_cards"][0]["display"]["status_label"] == "확인 필요"
    assert body["execution_cards"][0]["display"]["next_action"] == "이벤트 유형 초안 만들기"
    assert body["execution_cards"][0]["technical_details"]["operation"] == "event_type_draft"
    payload = artifact["data"]["payload"]
    assert payload["event_type"] == "maintenance.inspection.completed.v1"
    assert payload["name_ko"] == "장비 점검 완료"
    assert payload["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert payload["workflow_stage"]
    assert payload["topic"] == "maintenance.inspection"
    assert payload["payload_schema"]["properties"]["owner_employee_id"]["pattern"] == "^\\d{7}$"
    assert "equipment_id" in payload["payload_schema"]["properties"]
    assert payload.get("recommended_actions", []) == []

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

    def fake_llm(employee_id: str, task: str, payload: dict):
        assert task == "compose"
        assert payload["intent"] == "workflow_explain"
        return {
            "answer_markdown": "## SOP 관계 요약\n\nAgent가 Event, Action, Manual Handoff 관계를 업무 관점으로 설명했습니다.",
            "suggested_questions": [],
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_ROUTER_MODE", "llm_first")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_LLM_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_COMPOSER_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_router_llm", wrong_fast_router)
    monkeypatch.setattr(boi_app_module, "native_agent_llm_json", fake_llm)

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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="search")
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
    install_fake_boi_agent_router(boi_app_module, monkeypatch, route="deep", intent="diagram")
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
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)

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
    assert event_names[0] == "accepted"
    assert "status" in event_names
    assert "answer_delta" in event_names
    assert "answer_ready" in event_names
    assert "followups" in event_names
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
    answer_ready = json.loads(next(item["data"] for item in events if item["event"] == "answer_ready"))
    assert answer_ready["answer_html"]
    assert answer_ready["suggested_questions"] == []
    followups = json.loads(next(item["data"] for item in events if item["event"] == "followups"))
    assert followups["suggested_questions"]
    assert event_names.index("answer_ready") < event_names.index("followups") < event_names.index("final")
    final = json.loads(events[-1]["data"])
    assert final["answer_html"]
    assert final["links"][0]["label"] == "설비 SOP"
    assert final["used_backend"] == "native_langgraph"
    assert final["status_updates"]
    assert final["status_events"] == final["status_updates"]
    assert final["status_updates"][0]["message"] == llm_steps[0]["message"]
    assert any(item.get("stage") == "answer_stream" for item in final["status_updates"])
    assert received_routes == [planned_route]


def test_boi_agent_chat_stream_fast_first_does_not_wait_for_stream_plan(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    received_routes: list[dict[str, Any]] = []

    def forbidden_stream_plan(req, employee_id: str):
        raise AssertionError("fast-first stream must not block on LLM status plan")

    def fake_agent_response(req, employee_id: str, progress_callback=None, route=None):
        received_routes.append(route or {})
        return {
            "ok": True,
            "employee_id": employee_id,
            "answer_markdown": "현재 문서의 부족 근거는 Raw Data endpoint 확인입니다.",
            "display_markdown": "현재 문서의 부족 근거는 Raw Data endpoint 확인입니다.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "artifacts": [],
            "context_summary": {"intent": "page_qa"},
            "route": (route or {}).get("route") or "fast",
            "intent": (route or {}).get("intent") or "page_qa",
            "router_backend": (route or {}).get("router_backend") or "native_goal_router",
            "used_backend": "native_langgraph",
            "latency_ms": 9,
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", False)
    monkeypatch.setattr(boi_app_module, "agent_stream_plan", forbidden_stream_plan)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent_response)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "부족한 근거가 뭐야?", "current_url": "/docs/boi:private:100001:report"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    event_names = [item["event"] for item in events]
    assert event_names[0] == "accepted"
    assert "answer_ready" in event_names
    assert "diagnostic" not in event_names
    status_payloads = [json.loads(item["data"]) for item in events if item["event"] == "status"]
    assert status_payloads
    assert status_payloads[0]["source"] == "native_status"
    answer_ready = json.loads(next(item["data"] for item in events if item["event"] == "answer_ready"))
    assert answer_ready["latency_contract"] == "fast_first"
    assert "Raw Data endpoint" in answer_ready["answer_markdown"]
    assert received_routes and received_routes[0]["router_backend"] in {"agent_goal_registry", "native_goal_router"}


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
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "천천히 확인해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    assert events[0]["event"] == "accepted"
    status_payloads = [json.loads(item["data"]) for item in events if item["event"] == "status"]
    assert len(status_payloads) >= 2
    assert status_payloads[0]["stage"] == "page_context"
    assert all(item.get("source") == "llm_status" for item in status_payloads)
    assert any(item["stage"] != "page_context" for item in status_payloads[1:])
    assert "answer_ready" in [item["event"] for item in events]
    assert events[-1]["event"] == "final"


def test_boi_agent_chat_stream_emits_accepted_then_error_when_status_llm_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_status(_req, _employee_id: str):
        raise boi_app_module.BoiAgentStatusUnavailable("status model unavailable")

    def fake_agent(req, employee_id: str, progress_callback=None, route=None):
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\n현재 페이지 기준으로 설명합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "agent_stream_plan", fail_status)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    event_names = [item["event"] for item in events]
    assert event_names[0] == "accepted"
    assert "error" not in event_names
    assert "diagnostic" in event_names
    assert "answer_ready" in event_names
    assert event_names[-1] == "final"
    payload = json.loads(next(item["data"] for item in events if item["event"] == "diagnostic"))
    assert payload["status"] == "status_generation_failed"
    assert "status model unavailable" in payload["message"]


def test_boi_agent_chat_stream_emits_accepted_then_error_when_status_required_is_disabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fake_agent(req, employee_id: str, progress_callback=None, route=None):
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\n현재 페이지 기준으로 설명합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_REQUIRED", False)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    event_names = [item["event"] for item in events]
    assert event_names[0] == "accepted"
    assert "error" not in event_names
    assert "diagnostic" in event_names
    assert "answer_ready" in event_names
    assert event_names[-1] == "final"
    payload = json.loads(next(item["data"] for item in events if item["event"] == "diagnostic"))
    assert payload["status"] == "status_generation_failed"
    assert payload["required"] is False
    assert "disabled" in payload["message"]


def test_boi_agent_chat_stream_records_diagnostic_and_answers_when_router_plan_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def fail_router(_req, _employee_id: str):
        raise boi_app_module.BoiAgentRouterUnavailable("router model unavailable")

    def fake_agent(req, employee_id: str, progress_callback=None, route=None):
        return {
            "ok": True,
            "answer_markdown": "## 확인\n\n현재 페이지 기준으로 설명합니다.",
            "links": [],
            "citations": [],
            "artifacts": [],
            "route": route["route"],
            "intent": route["intent"],
            "router_backend": route["router_backend"],
            "component_errors": route.get("component_errors") or [],
            "used_backend": "native_langgraph",
        }

    monkeypatch.setattr(boi_app_module, "agent_stream_plan", fail_router)
    monkeypatch.setattr(boi_app_module, "agent_chat_response", fake_agent)
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_STATUS_BLOCKING", True)

    with client.stream(
        "POST",
        "/api/agents/boi-wiki/chat/stream?employee_id=100001",
        json={"question": "현재 페이지 기준으로 설명해줘", "current_url": "/"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = parse_sse_events(raw)
    event_names = [item["event"] for item in events]
    assert event_names[0] == "accepted"
    assert "error" not in event_names
    assert "diagnostic" in event_names
    assert "answer_ready" in event_names
    diagnostic = json.loads(next(item["data"] for item in events if item["event"] == "diagnostic"))
    assert diagnostic["status"] == "boi_agent_router_unavailable"
    assert diagnostic["recoverable"] is True
    answer_ready = json.loads(next(item["data"] for item in events if item["event"] == "answer_ready"))
    assert answer_ready["component_errors"][0]["component"] == "stream_plan"


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
    assert target["workflow_run_url"].startswith("/workflows/equipment-anomaly/status?")
    assert target["workflow_url"] == target["workflow_run_url"]
    assert target["workflow_definition_url"].startswith("/workflows/definitions?")
    assert "equipment-anomaly-response" in unquote(target["workflow_definition_url"])
    user_link_labels = [item["label"] for item in target["user_links"]]
    assert "관련 SOP 보기" in user_link_labels
    assert "Action 보기" in user_link_labels
    assert "업무 흐름 정의" not in user_link_labels
    assert "WorkflowDefinition" not in user_link_labels
    assert "업무 흐름과" not in target["display"]["next_action"]
    assert target["technical_links"][0]["url"] == target["workflow_definition_url"]
    assert complete.status_code == 200
    assert complete.json()["item"]["completion_for_request_id"] == "act-manual-required-test"
    assert not any(item["request_id"] == "act-manual-required-test" for item in inbox_after.json()["items"])


def test_agent_inbox_groups_repeated_tasks_for_member_readability(boi_app_module):
    client = TestClient(boi_app_module.app)
    for idx in range(2):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": f"act-approval-group-test-{idx}",
                "action_key": "direct_development.messenger_share.publish",
                "status": "approval_required",
                "summary": "공유 전 승인 필요",
                "trace_id": f"trace-agent-inbox-approval-group-{idx}",
                "event_type": "report.requested.v1" if idx == 0 else "meeting.closed.v1",
                "logged_at": f"2026-06-26T22:3{idx}:00+09:00",
                "payload": {
                    "equipment_id": "ETCH-VM-01" if idx == 0 else "CVD-ALD-02",
                    "lot_id": "LOT-A" if idx == 0 else "LOT-B",
                    "wafer_id": "WF-01" if idx == 0 else "WF-09",
                    "alarm_code": "PRESSURE_SPIKE" if idx == 0 else "TEMP_DRIFT",
                    "trend_status": "anomaly_detected" if idx == 0 else "trend_check_failed",
                    "raw_data_status": "available" if idx == 0 else "missing",
                    "severity": "high",
                },
            },
        )

    response = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact")
    body = response.json()

    assert response.status_code == 200
    group = next(
        item
        for item in body["groups"]
        if item["status"] == "approval_required" and item["action_key"] == "direct_development.messenger_share.publish"
    )
    assert group["count"] >= 2
    assert "건" in group["display"]["title"]
    assert "같은 유형의 업무" not in group["display"]["why_it_matters"]
    assert "업무 흐름과" not in group["display"]["next_action"]
    assert "업무 정보" in group["display"]["next_action"]
    assert group["display"]["primary_url"] == ""
    assert group["group_context_summary"]["time_range"]
    assert group["group_context_summary"]["top_differences"]
    assert group["group_context_summary"]["top_business_differences"]
    assert "ETCH-VM-01" in json.dumps(group["group_context_summary"], ensure_ascii=False)
    assert "CVD-ALD-02" in json.dumps(group["group_context_summary"], ensure_ascii=False)
    assert "PRESSURE_SPIKE" in json.dumps(group["group_context_summary"], ensure_ascii=False)
    assert not any("서로 다른 trace" in item for item in group["group_context_summary"]["top_differences"])
    assert group["group_context_summary"]["recommended_order"][0] == "고위험 건"
    assert group["group_work_context_narrative"]["overall_summary"]
    assert len(group["preview_items"]) >= 2
    assert all(item["item_brief"]["occurred_at_label"] for item in group["preview_items"])
    assert all(item["item_brief"]["difference_summary"] for item in group["preview_items"])
    assert any("ETCH-VM-01" in item["item_brief"]["difference_summary"] for item in group["preview_items"])
    assert all("request_id" in item for item in group["items"])


def test_inbox_group_narrative_qa_blocks_trace_and_repetition(boi_app_module):
    compact = {
        "group_id": "approval_required:sop.equipment.change_spec_rule",
        "source_items": [
            {
                "source_id": "inbox:act-1",
                "occurred_at_label": "06-29 22:09",
                "comparison_candidates": [
                    {"label": "장비", "value": "FURN-HT-04", "source_id": "inbox:act-1", "why_relevant": "승인 대상 장비"},
                    {"label": "Alarm", "value": "RECIPE_MISMATCH", "source_id": "inbox:act-1", "why_relevant": "승인 전 확인할 이상 유형"},
                ],
            },
            {
                "source_id": "inbox:act-2",
                "occurred_at_label": "06-29 22:08",
                "comparison_candidates": [
                    {"label": "장비", "value": "MET-OVL-03", "source_id": "inbox:act-2", "why_relevant": "승인 대상 장비"},
                    {"label": "Alarm", "value": "RING_PATTERN", "source_id": "inbox:act-2", "why_relevant": "승인 전 확인할 이상 유형"},
                ],
            },
        ],
    }

    ready = boi_app_module.normalize_inbox_group_narrative_payload(
        {
            "summary": "승인이 필요한 Spec / Rule 변경 요청이 2건 있으며, Furnace recipe mismatch와 Metrology ring pattern으로 확인 포인트가 나뉩니다.",
            "priority_note": "Recipe mismatch 건은 공정 Hold 위험을 먼저 확인하고, ring pattern 건은 wafer 이력 비교 여부를 확인하세요.",
            "preview_items": [
                {
                    "source_id": "inbox:act-1",
                    "unique_context": "FURN-HT-04의 RECIPE_MISMATCH 건은 recipe/source data 불일치가 핵심입니다.",
                    "next_check": "승인 전 보전 가이드 확인 여부를 먼저 보세요.",
                },
                {
                    "source_id": "inbox:act-2",
                    "unique_context": "MET-OVL-03의 RING_PATTERN 건은 Map View와 wafer 이력 비교가 핵심입니다.",
                    "next_check": "승인 전 wafer 이력 비교가 끝났는지 확인하세요.",
                },
            ],
        },
        compact,
    )

    assert ready["state"] == "ready"
    assert ready["narrative_quality"] == "ready"
    assert "trace" not in json.dumps(ready, ensure_ascii=False)
    assert ready["preview_items"][0]["unique_context"] != ready["preview_items"][1]["unique_context"]

    bad_payloads = [
        {"summary": "서로 다른 trace 2건에서 같은 Action이 발생했습니다.", "preview_items": []},
        {
            "summary": "source_id: inbox:act-1 기준으로 처리 중입니다.",
            "preview_items": [{"source_id": "inbox:act-1", "unique_context": "처리 중", "next_check": "처리 중"}],
        },
        {
            "summary": "승인 필요 건을 확인하세요.",
            "preview_items": [
                {"source_id": "inbox:act-1", "unique_context": "SOP, 실행 현황, 원본 기록을 확인하세요.", "next_check": "SOP, 실행 현황, 원본 기록을 확인하세요."},
                {"source_id": "inbox:act-2", "unique_context": "SOP, 실행 현황, 원본 기록을 확인하세요.", "next_check": "SOP, 실행 현황, 원본 기록을 확인하세요."},
            ],
        },
    ]
    for payload in bad_payloads:
        with pytest.raises(ValueError):
            boi_app_module.normalize_inbox_group_narrative_payload(payload, compact)


def test_agent_inbox_group_user_fields_require_qa_ready_narrative(boi_app_module):
    client = TestClient(boi_app_module.app)
    for idx, equipment in enumerate(["FURN-HT-04", "MET-OVL-03", "ETCH-VM-01"]):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": f"act-qa-group-test-{idx}",
                "action_key": "sop.equipment.change_spec_rule",
                "status": "approval_required",
                "summary": "Spec / Rule 변경 요청 승인 필요",
                "trace_id": f"trace-qa-group-test-{idx}",
                "event_type": "corrective_action.requested.v1",
                "logged_at": f"2026-06-29T22:0{idx}:00+09:00",
                "payload": {
                    "equipment_id": equipment,
                    "lot_id": f"LOT-QA-{idx}",
                    "wafer_id": f"WF-QA-{idx}",
                    "alarm_code": ["RECIPE_MISMATCH", "RING_PATTERN", "PRESSURE_SPIKE"][idx],
                    "trend_status": ["source_data_mismatch", "map_view_abnormal", "abnormal"][idx],
                    "raw_data_status": ["available", "wafer_history_needed", "available"][idx],
                    "severity": "high",
                },
            },
        )

    response = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=50")
    assert response.status_code == 200
    group = next(
        item
        for item in response.json()["groups"]
        if item["status"] == "approval_required" and item["action_key"] == "sop.equipment.change_spec_rule"
    )

    assert group["group_narrative"]["state"] == "ready"
    assert group["group_narrative"]["narrative_quality"] == "ready"
    assert group["group_narrative"]["summary"]
    visible_text = " ".join(
        [
            str((group.get("group_narrative") or {}).get("summary") or ""),
            str((group.get("group_narrative") or {}).get("priority_note") or ""),
            str((group.get("display") or {}).get("why_it_matters") or ""),
            str((group.get("display") or {}).get("next_action") or ""),
            " ".join(
                " ".join(
                    [
                        str((item.get("brief") or {}).get("unique_context") or ""),
                        str((item.get("brief") or {}).get("next_check") or ""),
                    ]
                )
                for item in group.get("preview_items") or []
            ),
        ]
    )
    for forbidden in ["서로 다른 trace", "같은 Action", "source_id", "라우팅", "처리 중", "WorkflowDefinition"]:
        assert forbidden not in visible_text
    contexts = [
        (item.get("brief") or {}).get("unique_context")
        for item in group["preview_items"][:3]
    ]
    assert len(set(contexts)) == len(contexts)
    assert all(contexts)


def test_agent_inbox_group_narrative_uses_safe_fallback_context_when_business_context_is_sparse(boi_app_module):
    client = TestClient(boi_app_module.app)
    rows = [
        ("act-manual-sparse-context-0", "Alarm 담당자 확인 요청", "manual.input.v1", "2026-06-29T21:05:10+09:00"),
        ("act-manual-sparse-context-1", "Raw Data 재확인 요청", "manual.input.v1", "2026-06-29T21:05:20+09:00"),
        ("act-manual-sparse-context-2", "보전 가이드 담당 검토 요청", "manual.input.v1", "2026-06-29T21:05:30+09:00"),
    ]
    for request_id, summary, event_type, logged_at in rows:
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": request_id,
                "action_key": "manual.test.sparse_context_review",
                "status": "manual_required",
                "summary": summary,
                "event_type": event_type,
                "logged_at": logged_at,
                "payload": {"severity": "medium"},
            },
        )

    response = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=50")
    assert response.status_code == 200
    group = next(
        item
        for item in response.json()["groups"]
        if item["status"] == "manual_required" and item["action_key"] == "manual.test.sparse_context_review"
    )

    assert group["group_narrative"]["state"] == "ready"
    preview_briefs = [(item.get("brief") or {}) for item in group["preview_items"][:3]]
    contexts = [str(item.get("unique_context") or "") for item in preview_briefs]
    assert len(contexts) == 3
    assert len(set(contexts)) == 3
    assert all("06-29" in context for context in contexts)
    assert any("Raw Data" in context for context in contexts)
    visible_text = " ".join(
        [
            str(group["group_narrative"].get("summary") or ""),
            str(group["group_narrative"].get("priority_note") or ""),
            " ".join(
                " ".join([str(item.get("unique_context") or ""), str(item.get("next_check") or "")])
                for item in group["group_narrative"].get("preview_items") or []
            ),
        ]
    )
    for forbidden in ["source_id", "trace", "라우팅", "처리 중", "WorkflowDefinition", "SOP, 실행 현황, 원본 기록"]:
        assert forbidden not in visible_text


def test_agent_inbox_group_narrative_distinguishes_same_minute_same_summary_items(boi_app_module):
    client = TestClient(boi_app_module.app)
    for idx, second in enumerate(["10", "20", "30"]):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": f"act-manual-same-minute-{idx}",
                "action_key": "manual.test.same_minute_context_review",
                "status": "manual_required",
                "summary": "원인 후보 검토 및 판단 조치 필요",
                "event_type": "manual.input.v1",
                "logged_at": f"2026-06-29T21:05:{second}+09:00",
                "payload": {"severity": "medium"},
            },
        )

    response = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=50")
    assert response.status_code == 200
    group = next(
        item
        for item in response.json()["groups"]
        if item["status"] == "manual_required" and item["action_key"] == "manual.test.same_minute_context_review"
    )

    assert group["group_narrative"]["state"] == "ready"
    contexts = [
        str((item.get("brief") or {}).get("unique_context") or "")
        for item in group["preview_items"][:3]
    ]
    assert len(contexts) == 3
    assert len(set(contexts)) == 3
    assert any("21:05:10" in context for context in contexts)
    assert all("trace" not in context for context in contexts)
    visible_text = " ".join(
        contexts
        + [
            str((item.get("brief") or {}).get("next_check") or "")
            for item in group["preview_items"][:3]
        ]
    )
    assert "필요은" not in visible_text
    assert "필요에 필요한" not in visible_text


def test_agent_inbox_review_report_group_and_item_are_user_facing(boi_app_module):
    client = TestClient(boi_app_module.app)
    for idx, payload in enumerate(
        [
            {
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-A",
                "wafer_id": "WF-01",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "missing_evidence": "raw_endpoint_confirmation",
                "severity": "high",
            },
            {
                "equipment_id": "FURN-HT-04",
                "lot_id": "LOT-B",
                "wafer_id": "WF-04",
                "alarm_code": "RECIPE_MISMATCH",
                "trend_status": "source_data_mismatch",
                "raw_data_status": "available",
                "missing_evidence": "maintenance_guide_confirmation",
                "severity": "high",
            },
        ]
    ):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": f"act-review-report-{idx}",
                "action_key": "sop.equipment.change_spec_rule",
                "status": "approval_required",
                "summary": "Spec / Rule 변경 요청 승인 필요",
                "trace_id": f"trace-review-report-{idx}",
                "event_type": "corrective_action.requested.v1",
                "logged_at": f"2026-06-29T23:1{idx}:00+09:00",
                "payload": payload,
            },
        )

    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=50")
    group = next(
        item
        for item in inbox.json()["groups"]
        if item["status"] == "approval_required" and item["action_key"] == "sop.equipment.change_spec_rule"
    )
    group_report = client.get(
        f"/api/agents/boi-wiki/inbox/groups/{group['group_id']}/review-report?employee_id=100001"
    )
    item_report = client.get(
        "/api/agents/boi-wiki/inbox/task:act-review-report-0/review-report?employee_id=100001"
    )

    assert group_report.status_code == 200
    body = group_report.json()
    assert body["ok"] is True
    assert body["report"]["report_type"] == "group"
    assert body["report"]["conclusion"]["summary"]
    assert body["report"]["comparison"]["items"]
    assert body["report"]["evidence"]["items"]
    assert body["report"]["actions"]["items"]
    assert body["report"]["actions"]["bulk_decisions"]
    assert "approve" not in body["report"]["actions"]["bulk_decisions"]
    visible_text = json.dumps(body["report"], ensure_ascii=False)
    for forbidden in ["source_id", "WorkflowDefinition", "schema", "trace-review-report", "act-review-report"]:
        assert forbidden not in visible_text
    assert "Raw Data endpoint 확인" in visible_text
    assert item_report.status_code == 200
    assert item_report.json()["report"]["report_type"] == "item"
    assert item_report.json()["report"]["actions"]["items"][0]["decision"] == "approve"


def test_agent_inbox_decision_rejects_bulk_high_risk_approve_and_requires_note(boi_app_module):
    client = TestClient(boi_app_module.app)
    for idx in range(2):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": f"act-decision-report-{idx}",
                "action_key": "sop.equipment.change_spec_rule",
                "status": "approval_required",
                "summary": "Spec / Rule 변경 요청 승인 필요",
                "risk_level": "high",
                "trace_id": f"trace-decision-report-{idx}",
                "event_type": "corrective_action.requested.v1",
                "payload": {
                    "equipment_id": f"ETCH-VM-0{idx}",
                    "lot_id": f"LOT-DEC-{idx}",
                    "wafer_id": f"WF-DEC-{idx}",
                    "alarm_code": "PRESSURE_SPIKE",
                    "severity": "high",
                },
            },
        )
    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=50")
    group = next(
        item
        for item in inbox.json()["groups"]
        if item["status"] == "approval_required" and item["action_key"] == "sop.equipment.change_spec_rule"
    )

    missing_note = client.post(
        "/api/agents/boi-wiki/inbox/task:act-decision-report-0/decision?employee_id=100001",
        json={"decision": "reject", "note": "", "user_confirmed": True},
    )
    bulk_approve = client.post(
        f"/api/agents/boi-wiki/inbox/groups/{group['group_id']}/decision-preview?employee_id=100001",
        json={"decision": "approve", "note": "일괄 승인", "selected_task_ids": [item["task_id"] for item in group["items"]], "user_confirmed": True},
    )
    item_reject = client.post(
        "/api/agents/boi-wiki/inbox/task:act-decision-report-0/decision?employee_id=100001",
        json={"decision": "reject", "note": "Raw Data 확인 전이라 반려", "user_confirmed": True},
    )

    assert missing_note.status_code == 400
    assert "note" in str(missing_note.json()["detail"])
    assert bulk_approve.status_code == 400
    assert "bulk approve" in str(bulk_approve.json()["detail"])
    assert item_reject.status_code == 200
    assert item_reject.json()["item"]["completion_for_request_id"] == "act-decision-report-0"
    assert item_reject.json()["item"]["decision"] == "reject"


def test_agent_inbox_does_not_default_unknown_workflow_to_equipment_status(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-unknown-workflow-test",
            "action_key": "manual.unknown.no_workflow",
            "status": "manual_required",
            "summary": "연결되지 않은 수동 조치",
            "trace_id": "trace-unknown-workflow-test",
        },
    )

    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001")

    assert inbox.status_code == 200
    target = next(item for item in inbox.json()["items"] if item["request_id"] == "act-unknown-workflow-test")
    assert target["workflow_run_url"] == ""
    assert target["workflow_url"] == ""
    assert target["display"]["primary_url"] == ""
    assert "equipment-anomaly" not in json.dumps(target, ensure_ascii=False)


def test_manual_handoff_completion_rejects_task_not_visible_to_employee(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100002",
            "request_id": "act-manual-required-other-employee",
            "action_key": "manual.equipment.review_root_cause",
            "status": "manual_required",
            "summary": "다른 사번의 수동 조치",
            "trace_id": "trace-agent-inbox-other-employee",
        },
    )

    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001")
    complete = client.post(
        "/api/agents/boi-wiki/manual-handoffs/complete?employee_id=100001",
        json={
            "task_id": "task:act-manual-required-other-employee",
            "outcome": "completed",
            "note": "보이지 않는 업무를 완료하면 안 됨",
            "user_confirmed": True,
        },
    )

    assert inbox.status_code == 200
    assert not any(item["request_id"] == "act-manual-required-other-employee" for item in inbox.json()["items"])
    assert complete.status_code == 403
    assert "not visible" in complete.text
    completed = boi_app_module.completion_request_ids()
    assert "act-manual-required-other-employee" not in completed


def test_agent_inbox_snooze_and_dismiss_require_confirmation_and_role(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-confirmation-test",
            "action_key": "manual.equipment.review_root_cause",
            "status": "manual_required",
            "summary": "확인 후 잠시 미루기",
            "trace_id": "trace-agent-inbox-confirmation",
        },
    )

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


def test_agent_inbox_snooze_and_dismiss_reject_tasks_not_visible_to_employee(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100002",
            "request_id": "act-inbox-mutation-other-employee",
            "action_key": "manual.equipment.review_root_cause",
            "status": "manual_required",
            "summary": "다른 사번의 Inbox 업무",
            "trace_id": "trace-agent-inbox-mutation-other-employee",
        },
    )

    snooze = client.post(
        "/api/agents/boi-wiki/inbox/task:act-inbox-mutation-other-employee/snooze?employee_id=100001",
        json={"note": "보이지 않는 업무를 미루면 안 됨", "user_confirmed": True},
    )
    dismiss = client.post(
        "/api/agents/boi-wiki/inbox/task:act-inbox-mutation-other-employee/dismiss?employee_id=100001",
        json={"note": "보이지 않는 업무를 숨기면 안 됨", "user_confirmed": True},
    )

    assert snooze.status_code == 403
    assert dismiss.status_code == 403
    completed = boi_app_module.completion_request_ids()
    assert "act-inbox-mutation-other-employee" not in completed


def test_boi_agent_approve_rejects_unsupported_operation(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={"operation": "not_a_supported_operation", "payload": {"title": "Noop"}, "user_confirmed": True},
    )

    assert response.status_code == 400
    assert "unsupported Agent approval operation" in response.json()["detail"]


def test_boi_agent_approve_requires_confirmation_before_any_mutation(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    async def fail_async(*_args, **_kwargs):
        raise AssertionError("mutation function must not be called without user confirmation")

    def fail_sync(*_args, **_kwargs):
        raise AssertionError("mutation function must not be called without user confirmation")

    monkeypatch.setattr(boi_app_module, "publish_event", fail_async)
    monkeypatch.setattr(boi_app_module, "start_workflow_from_data", fail_async)
    monkeypatch.setattr(boi_app_module, "invoke_action_gateway", fail_async)
    monkeypatch.setattr(boi_app_module, "complete_manual_handoff", fail_async)
    monkeypatch.setattr(boi_app_module, "submit_promotion", fail_async)
    monkeypatch.setattr(boi_app_module, "apply_source_edit_api", fail_async)
    monkeypatch.setattr(boi_app_module, "apply_doc_body_edit", fail_async)
    monkeypatch.setattr(boi_app_module, "create_event_type_draft", fail_sync)
    monkeypatch.setattr(boi_app_module, "apply_event_type_draft", fail_sync)

    cases = [
        ("event_publish", {"event_type": "equipment.alarm.raised.v1", "payload": {"title": "alarm"}}),
        ("workflow_start", {"workflow_key": "equipment-anomaly", "payload": {"equipment_id": "ETCH-VM-01"}}),
        ("action_invoke", {"action_key": "sop.equipment.request_raw_data", "payload": {"equipment_id": "ETCH-VM-01"}}),
        ("manual_handoff_complete", {"task_id": "task-1", "note": "done"}),
        ("event_type_draft", {"event_type": "maintenance.inspection.completed.v1", "name_ko": "점검 완료"}),
        ("event_type_draft_apply", {"draft_id": "event-type-draft-1"}),
        ("promotion_submit", {"target_visibility": "team", "title": "Team Draft", "body": "# Summary\n\nDraft"}),
        ("source_apply", {"path": "data/boi/public/sop/equipment-abnormal-response.md", "base_sha256": "sha", "proposed_content": "content"}),
        ("doc_body_apply", {"boi_id": "boi:public:sop:equipment-abnormal-response", "base_sha256": "sha", "proposed_body": "# Body"}),
    ]

    for operation, payload in cases:
        response = client.post(
            "/api/agents/boi-wiki/approve?employee_id=100001",
            json={"operation": operation, "payload": payload, "user_confirmed": False},
        )
        assert response.status_code == 400, operation
        assert "user_confirmed=true is required" in response.json()["detail"]


def test_boi_agent_approve_requires_rbac_before_any_mutation(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    async def fail_async(*_args, **_kwargs):
        raise AssertionError("mutation function must not be called when Agent approval RBAC is denied")

    def fail_sync(*_args, **_kwargs):
        raise AssertionError("mutation function must not be called when Agent approval RBAC is denied")

    monkeypatch.setattr(boi_app_module, "roles_for", lambda _employee_id: ["boi.viewer"])
    monkeypatch.setattr(boi_app_module, "publish_event", fail_async)
    monkeypatch.setattr(boi_app_module, "start_workflow_from_data", fail_async)
    monkeypatch.setattr(boi_app_module, "invoke_action_gateway", fail_async)
    monkeypatch.setattr(boi_app_module, "complete_manual_handoff", fail_async)
    monkeypatch.setattr(boi_app_module, "submit_promotion", fail_async)
    monkeypatch.setattr(boi_app_module, "apply_source_edit_api", fail_async)
    monkeypatch.setattr(boi_app_module, "apply_doc_body_edit", fail_async)
    monkeypatch.setattr(boi_app_module, "create_event_type_draft", fail_sync)
    monkeypatch.setattr(boi_app_module, "apply_event_type_draft", fail_sync)

    cases = [
        ("event_publish", {"event_type": "equipment.alarm.raised.v1", "payload": {"title": "alarm"}}),
        ("workflow_start", {"workflow_key": "equipment-anomaly", "payload": {"equipment_id": "ETCH-VM-01"}}),
        ("action_invoke", {"action_key": "sop.equipment.request_raw_data", "payload": {"equipment_id": "ETCH-VM-01"}}),
        ("manual_handoff_complete", {"task_id": "task-1", "note": "done"}),
        ("event_type_draft", {"event_type": "maintenance.inspection.completed.v1", "name_ko": "점검 완료"}),
        ("event_type_draft_apply", {"draft_id": "event-type-draft-1"}),
        ("promotion_submit", {"target_visibility": "team", "title": "Team Draft", "body": "# Summary\n\nDraft"}),
        ("source_apply", {"path": "data/boi/public/sop/equipment-abnormal-response.md", "base_sha256": "sha", "proposed_content": "content"}),
        ("doc_body_apply", {"boi_id": "boi:public:sop:equipment-abnormal-response", "base_sha256": "sha", "proposed_body": "# Body"}),
    ]

    for operation, payload in cases:
        response = client.post(
            "/api/agents/boi-wiki/approve?employee_id=100003",
            json={"operation": operation, "payload": payload, "user_confirmed": True},
        )
        assert response.status_code == 403, operation
        detail = response.json()["detail"]
        assert detail["message"] == "Agent approval requires an allowed RBAC decision"
        assert detail["operation"] == operation
        assert detail["required_role"].startswith("boi.")


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


def test_agent_approve_does_not_treat_general_note_as_admin_override_reason(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    async def fake_publish_event_to_kafka(_event):
        raise AssertionError("Agent approve must not publish delegated events without explicit override reason")

    monkeypatch.setattr(
        boi_app_module,
        "roles_for",
        lambda _employee_id: ["boi.viewer", "boi.workflow_runner", "boi.action_invoker", "boi.admin"],
    )
    monkeypatch.setattr(boi_app_module, "publish_event_to_kafka", fake_publish_event_to_kafka)

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "event_publish",
            "user_confirmed": True,
            "note": "일반 승인 메모는 대리 실행 사유가 아니다",
            "payload": {
                "event_type": "equipment.alarm.raised.v1",
                "actor_employee_id": "100002",
                "payload": {"title": "agent admin override without explicit reason"},
            },
        },
    )

    assert response.status_code == 400
    assert "admin_override_reason" in response.text


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


def test_boi_agent_approve_source_apply_uses_validated_source_apply_path(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "committed", "commit_hash": "agent-src123"})
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")
    source = client.get(f"/api/source?employee_id=100001&path={source_ref}").json()

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "source_apply",
            "user_confirmed": True,
            "note": "agent source apply test",
            "payload": {
                "path": source_ref,
                "base_sha256": source["sha256"],
                "proposed_content": before + "\n<!-- agent source apply test -->\n",
                "author": "100001",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "source_apply"
    assert body["status"] == "applied"
    assert body["result"]["commit_hash"] == "agent-src123"
    assert "agent source apply test" in source_path.read_text(encoding="utf-8")


def test_boi_agent_approve_doc_body_apply_uses_validated_body_apply_path(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "git_commit_for_path", lambda path, message: {"status": "committed", "commit_hash": "agent-body123"})
    client = TestClient(boi_app_module.app)
    boi_id = "boi:public:sop:equipment-abnormal-response"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")
    editor = client.get(f"/api/docs/{boi_id}/body-editor?employee_id=100001").json()

    response = client.post(
        "/api/agents/boi-wiki/approve?employee_id=100001",
        json={
            "operation": "doc_body_apply",
            "user_confirmed": True,
            "note": "agent body apply test",
            "payload": {
                "boi_id": boi_id,
                "base_sha256": editor["base_sha256"],
                "proposed_body": "# Agent Body Apply\n\n본문 apply 테스트",
                "author": "100001",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "doc_body_apply"
    assert body["status"] == "applied"
    assert body["result"]["commit_hash"] == "agent-body123"
    assert "Agent Body Apply" in source_path.read_text(encoding="utf-8")
    assert source_path.read_text(encoding="utf-8") != before


def test_pet_agent_mount_is_hidden_by_default_on_home(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'id="boi-agent-root"' not in response.text
    assert "/static/mermaid_render.js?v=" in response.text
    assert "/static/pet_agent.js?v=" not in response.text
    assert "BoI Operations Center" not in response.text
    assert "boi:public:boi-wiki-manual:operations:boi-operations-center" not in response.text


def test_pet_agent_mount_is_available_when_feature_enabled(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_PET_AGENT_ENABLED", True)

    response = client.get("/?employee_id=100001")
    script = (boi_app_module.APP_DIR / "static" / "pet_agent.js").read_text(encoding="utf-8")
    style = (boi_app_module.APP_DIR / "static" / "style.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'id="boi-agent-root"' in response.text
    assert "/static/mermaid_render.js?v=" in response.text
    assert "/static/pet_agent.js?v=" in response.text
    assert "sessionStorage" in script
    assert "boiAgent.v8" in script
    assert "contextFingerprintFromUrl" in script
    assert "previousContextStorageKey" in script
    assert "answerSending" in script
    assert "followupsLoading" in script
    assert "if (!question.trim() || state.answerSending) return;" in script
    assert "state.answerSending = false;" in script
    assert "semanticRoute: body.semantic_route || {}" in script
    assert "relatedItemContext: body.related_item_context || {}" in script
    assert "semantic_route: item.semanticRoute || {}" in script
    assert "related_item_context: item.relatedItemContext || {}" in script
    assert "boiAgent.v6" not in script
    assert "boiAgent.v7.${employeeId}" not in script
    assert "pinToBottom" in script
    assert "captureScrollState" in script
    assert "isNearBottom" in script
    assert "Agent" in script
    assert "Inbox" not in script
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
    assert "diagnostic(payload)" in script
    assert "componentErrors: [...existingComponentErrors, payload]" in script
    assert "statusLines" in script
    assert "statusLines: statusLines.slice(-6)" in script
    assert 'if (!lines.length) return "";' in script
    assert "readAgentStream" in script
    assert "refreshSuggestions" in script
    assert "suggestionsLoading" in script
    assert "추천 질문 생성 중..." in script
    assert ".boi-agent-suggestions-loading" in style
    assert "state.inboxGroups = body.groups || []" not in script
    assert "inboxReport" not in script
    assert "renderInboxReport" not in script
    assert "data-inbox-report-group" not in script
    assert "data-inbox-report-task" not in script
    assert "검토 보고서 보기" not in script
    assert "/api/agents/boi-wiki/inbox/groups/${encoded}/review-report" not in script
    assert "/api/agents/boi-wiki/inbox/${encoded}/review-report" not in script
    assert "/api/agents/boi-wiki/inbox/${encodeURIComponent(draft.taskId)}/decision" not in script
    assert "판단 사유" not in script
    assert "추가 근거 요청" not in script
    assert "renderInboxGroup" not in script
    assert "group_narrative" not in script
    assert "narrative_quality" not in script
    assert "preview.brief" not in script
    assert "renderInboxLinks" not in script
    assert "업무 흐름 정의" not in script
    assert "내부 실행 정의" not in script
    assert "WorkflowDefinition" not in script
    assert "업무 흐름 상태 확인" not in script
    assert "연결된 업무 흐름" not in script
    assert "suggestedQuestions: body.suggested_questions || []" in script
    assert "renderMessageFollowups" in script
    assert "다음에 물어볼 수 있는 질문" in script
    assert "activeRequest.abort()" in script
    assert "생성을 중지했습니다." in script
    assert "formatAgentStreamError" in script
    assert "답변을 완성하지 못했습니다" in script
    assert "BoI Agent 장애" not in script
    assert "진행 상태 모델 장애입니다" not in script
    assert "LLM 라우터" not in script
    assert "요청을 중단했습니다" not in script
    assert "boi-agent-new" in script


def test_boi_inbox_nav_page_and_api_are_canonical(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-canonical",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-canonical",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-29T23:50:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-09",
                "lot_id": "LOT-INBOX",
                "wafer_id": "WF-11",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "missing_evidence": "raw_endpoint_confirmation",
                "severity": "high",
            },
        },
    )

    page = client.get("/inbox?employee_id=100001")
    body = page.text

    assert page.status_code == 200
    nav_labels = re.findall(r'class="global-nav-link[^"]*"[^>]*>([^<]+)</a>', body)
    assert nav_labels[:6] == ["BoI Wiki", "BoI Inbox", "SOP", "Event Broker", "Action", "Advanced"]
    assert 'data-nav-id="inbox" class="global-nav-link active"' in body
    assert "BoI Operations Center" not in body
    assert "받은 보고서" in body
    assert "승인/조치" in body
    assert "처리 이력" in body
    assert "보고서" in body
    assert "보고서 생성" in body
    assert "보고서 상태 보기" not in body
    assert "SOP, 실행 현황, 원본 기록" not in body
    assert "act-boi-inbox-canonical" not in body
    assert "trace-boi-inbox-canonical" not in body

    api = client.get("/api/inbox?employee_id=100001&include_context=compact&limit=50")
    assert api.status_code == 200
    payload = api.json()
    assert payload["ok"] is True
    assert payload["canonical"] is True
    assert payload["context_mode"] == "background"
    group = next(group for group in payload["groups"] if group["action_key"] == "sop.equipment.change_spec_rule")
    assert group.get("rollup_only") is True
    assert group.get("report_scope") == "item"
    assert "report_state" not in group
    assert "report_boi_url" not in group
    assert "report_boi_link" not in group
    assert any(item.get("report_boi_link", {}).get("label") for item in payload["items"])
    assert all("report_state" in item for item in payload["items"])
    assert "work_context_narrative" not in group["items"][0]
    visible_api_text = json.dumps(
        {
            "items": [
                {
                    "display": item.get("display"),
                    "item_brief": item.get("item_brief"),
                }
                for item in payload["items"][:5]
            ],
            "groups": [
                {
                    "display": group.get("display"),
                    "preview_items": group.get("preview_items"),
                }
                for group in payload["groups"][:3]
            ],
        },
        ensure_ascii=False,
    )
    assert "SOP, 실행 현황, 원본 기록" not in visible_api_text
    assert "묶음 보고서" not in body


def test_api_sops_scope_contract_supports_catalog_all_and_search(boi_app_module):
    client = TestClient(boi_app_module.app)

    all_response = client.get("/api/sops?employee_id=100001&scope=catalog_all&limit=20")
    assert all_response.status_code == 200
    all_body = all_response.json()
    assert all_body["ok"] is True
    assert all_body["scope"] == "catalog_all"
    assert all_body["total"] >= 2
    all_titles = json.dumps(all_body["items"], ensure_ascii=False)
    assert "설비 이상" in all_titles
    assert "직개발" in all_titles

    search_response = client.get("/api/sops?employee_id=100001&scope=catalog_search&q=설비%20이상&limit=20")
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["scope"] == "catalog_search"
    assert search_body["total"] >= 1
    search_titles = json.dumps(search_body["items"], ensure_ascii=False)
    assert "설비 이상" in search_titles
    assert "직개발 결과 확인" not in search_titles


def test_boi_operations_center_hidden_by_default_and_api_compatible(boi_app_module):
    client = TestClient(boi_app_module.app)

    page = client.get("/ops?employee_id=100001", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/inbox?employee_id=100001"

    overview = client.get("/api/ops/overview?employee_id=100001")
    assert overview.status_code == 200
    assert overview.json()["feature_enabled"] is False

    canvas = client.get("/api/ops/canvas?employee_id=100001")
    assert canvas.status_code == 200
    assert canvas.json()["feature_enabled"] is False


def test_boi_operations_center_page_and_overview_api(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_OPS_CENTER_ENABLED", True)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-ops-center-spec-approval",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-ops-center-equipment",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T12:00:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-OPS",
                "wafer_id": "WF-07",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "missing",
                "severity": "high",
            },
        },
    )

    page = client.get("/ops?employee_id=100001")
    assert page.status_code == 200
    assert "BoI Operations Center" in page.text
    assert 'id="boi-ops-center"' in page.text
    assert "ops-center-bootstrap" in page.text
    assert "dist/ops-center.js" in page.text
    assert "ops-map-edges" not in page.text
    assert 'data-nav-id="inbox" class="global-nav-link active"' in page.text

    overview = client.get("/api/ops/overview?employee_id=100001")
    assert overview.status_code == 200
    body = overview.json()
    assert body["ok"] is True
    assert body["feature_enabled"] is True
    assert body["me"]["employee_id"] == "100001"
    assert body["summary"]["open_count"] >= 1
    rendered = json.dumps(body, ensure_ascii=False)
    assert "설비 이상" in rendered
    assert "Spec / Rule 변경 요청 승인 필요" in rendered
    assert body["workstream_nodes"]
    assert body["priority_queue"]
    sop_nodes = [node for node in body["workstream_nodes"] if node.get("type") == "sop_workstream"]
    assert sop_nodes
    assert any(node.get("size_class") in {"small", "medium", "large"} for node in sop_nodes)
    assert any(node.get("visual_state") in {"approval", "evidence", "running"} for node in sop_nodes)
    edge_text = json.dumps(body["workstream_edges"], ensure_ascii=False)
    assert "승인" in edge_text or "근거 부족" in edge_text or "보고서" in edge_text

    canvas = client.get("/api/ops/canvas?employee_id=100001")
    assert canvas.status_code == 200
    canvas_body = canvas.json()
    assert canvas_body["ok"] is True
    assert canvas_body["feature_enabled"] is True
    node_types = {node.get("type") for node in canvas_body["nodes"]}
    assert {"personNode", "sopWorkstreamNode"} <= node_types
    rendered_canvas = json.dumps(canvas_body, ensure_ascii=False)
    assert "Agent Office" not in rendered_canvas
    assert "Evidence Sandbox" not in rendered_canvas
    assert "Decision Flow" not in rendered_canvas
    assert all(node.get("data", {}).get("lane") for node in canvas_body["nodes"])
    assert all("display_priority" in node.get("data", {}) for node in canvas_body["nodes"])
    assert all("collapsed" in node.get("data", {}) for node in canvas_body["nodes"])
    assert all(
        node.get("data", {}).get("collapsed") is True
        for node in canvas_body["nodes"]
        if node.get("type") == "sopWorkstreamNode"
    )
    edge_kinds = {edge.get("data", {}).get("kind") for edge in canvas_body["edges"]}
    assert "assigned_to" in edge_kinds
    assert all(edge.get("data", {}).get("bundle_id") for edge in canvas_body["edges"])
    assert all(edge.get("data", {}).get("display_mode") in {"dot", "label", "expanded"} for edge in canvas_body["edges"])
    assert canvas_body["performance"]["source"] in {"manifest", "fallback_scan"}


def test_ops_overview_uses_runtime_manifest_without_rescanning_logs(boi_app_module, monkeypatch, tmp_path):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "OPS_RUNTIME_INDEX_ROOT", tmp_path / "ops")
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-ops-manifest",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec 변경 승인 필요",
            "trace_id": "trace-ops-manifest",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T12:00:00+09:00",
            "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-MANIFEST", "alarm_code": "PRESSURE_SPIKE"},
        },
    )

    first = client.get("/api/ops/overview?employee_id=100001")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["performance"]["source"] == "manifest"
    assert first_body["selected_run_id"]

    def fail_scan(*_args, **_kwargs):
        raise AssertionError("ops overview should read warm manifest instead of rescanning logs")

    monkeypatch.setattr(boi_app_module, "collect_sop_run_rows", fail_scan)
    second = client.get("/api/ops/overview?employee_id=100001")
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["performance"]["source"] == "manifest"
    assert second_body["summary"]["open_count"] >= 1


def test_ops_page_renders_connected_map_previews_and_in_place_detail(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_OPS_CENTER_ENABLED", True)
    trace_id = "trace-ops-map-preview"
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-ops-map-preview",
            "action_key": "sop.equipment.request_raw_data",
            "status": "failed",
            "summary": "Raw Data 확인 필요",
            "trace_id": trace_id,
            "event_type": "equipment.alarm.raised.v1",
            "logged_at": "2026-06-30T12:10:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-02",
                "lot_id": "LOT-PREVIEW",
                "wafer_id": "WF-03",
                "alarm_code": "RAW_MISSING",
                "raw_data_status": "missing",
            },
        },
    )

    page = client.get("/ops?employee_id=100001")
    assert page.status_code == 200
    assert "ops-center-bootstrap" in page.text
    assert "Raw Data 확인 필요" not in page.text
    canvas = client.get("/api/ops/canvas?employee_id=100001")
    assert canvas.status_code == 200
    rendered = json.dumps(canvas.json(), ensure_ascii=False)
    assert "Raw Data 확인 필요" in rendered
    assert "LOT-PREVIEW" in rendered


def test_openai_health_contract_is_non_blocking_without_check(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/runtime/openai-health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["active_model"] == "gpt-5.5"
    assert "api_key" not in body
    assert body["quota_state"] in {"not_configured", "unchecked", "ready", "degraded"}


def test_agent_builder_sandbox_and_report_evidence_contracts(boi_app_module, monkeypatch, tmp_path):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_RUNTIME", "contract_only")

    draft_response = client.post(
        "/api/agents/drafts?employee_id=100001",
        json={
            "title": "FAB Trend Helper",
            "prompt": "Trend와 Raw Data를 확인해줘.",
            "urls": ["https://example.com/manual"],
            "mcp_servers": ["boi-wiki-local"],
            "skills": ["data-analytics:visualize-data"],
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()["draft"]
    assert draft["runtime"]["model"] == "gpt-5.5"

    test_response = client.post(f"/api/agents/drafts/{draft['draft_id']}/test?employee_id=100001")
    assert test_response.status_code == 200
    test_payload = test_response.json()["test"]
    assert test_payload["sandbox_supported"] is True
    assert test_payload["runtime_backend"] in {"agents_sdk", "contract_only"}

    publish_without_confirmation = client.post(f"/api/agents/drafts/{draft['draft_id']}/publish?employee_id=100001", json={"scope": "private"})
    assert publish_without_confirmation.status_code == 400
    publish_response = client.post(
        f"/api/agents/drafts/{draft['draft_id']}/publish?employee_id=100001",
        json={"scope": "private", "note": "ready", "user_confirmed": True},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["draft"]["status"] == "published"
    deployment = publish_response.json()["deployment"]
    agent_id = deployment["agent_id"]
    assert deployment["owner_employee_id"] == "100001"
    assert deployment["is_linked_to_me"] is True

    mine = client.get("/api/agents?employee_id=100001&scope=mine")
    assert mine.status_code == 200
    assert any(item["agent_id"] == agent_id for item in mine.json()["items"])
    private_other = client.get("/api/agents?employee_id=100002&scope=mine")
    assert private_other.status_code == 200
    assert all(item["agent_id"] != agent_id for item in private_other.json()["items"])
    ops_canvas = client.get("/api/ops/canvas?employee_id=100001")
    assert ops_canvas.status_code == 200
    ops_body = ops_canvas.json()
    assert any(node.get("type") == "agentNode" and node.get("data", {}).get("agent_id") == agent_id for node in ops_body["nodes"])
    assert any(edge.get("data", {}).get("kind") == "owns_agent" for edge in ops_body["edges"])
    ops_other = client.get("/api/ops/canvas?employee_id=100002")
    assert ops_other.status_code == 200
    assert agent_id not in json.dumps(ops_other.json(), ensure_ascii=False)

    created_conversation = client.post(f"/api/agents/{agent_id}/conversations?employee_id=100001", json={"title": "Raw 확인"})
    assert created_conversation.status_code == 200
    conversation_id = created_conversation.json()["conversation"]["conversation_id"]
    message_response = client.post(
        f"/api/agents/{agent_id}/conversations/{conversation_id}/messages?employee_id=100001",
        json={"message": "Raw Data 확인 방법 알려줘"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["conversation"]["messages"][-1]["role"] == "assistant"
    conversations = client.get(f"/api/agents/{agent_id}/conversations?employee_id=100001")
    assert conversations.status_code == 200
    assert any(item["conversation_id"] == conversation_id for item in conversations.json()["items"])
    ingest = client.post(
        f"/api/agents/conversations/{conversation_id}/ingest-to-boi?employee_id=100001",
        json={"title": "Raw 확인 Agent 대화", "user_confirmed": True},
    )
    assert ingest.status_code == 200
    assert "/docs/" in ingest.json()["doc_url"]

    public_draft_response = client.post(
        "/api/agents/drafts?employee_id=100001",
        json={"title": "Shared Agent", "prompt": "공유 Agent", "scope": "public"},
    )
    assert public_draft_response.status_code == 200
    public_draft = public_draft_response.json()["draft"]
    public_publish = client.post(
        f"/api/agents/drafts/{public_draft['draft_id']}/publish?employee_id=100001",
        json={"scope": "public", "note": "share", "user_confirmed": True},
    )
    assert public_publish.status_code == 200
    public_agent_id = public_publish.json()["deployment"]["agent_id"]
    available = client.get("/api/agents?employee_id=100002&scope=available")
    assert available.status_code == 200
    assert any(item["agent_id"] == public_agent_id for item in available.json()["items"])
    before_link = client.get("/api/ops/canvas?employee_id=100002")
    assert public_agent_id not in json.dumps(before_link.json(), ensure_ascii=False)
    link_response = client.post(f"/api/agents/{public_agent_id}/link-to-me?employee_id=100002")
    assert link_response.status_code == 200
    after_link = client.get("/api/ops/canvas?employee_id=100002")
    assert public_agent_id in json.dumps(after_link.json(), ensure_ascii=False)
    unlink_response = client.post(f"/api/agents/{public_agent_id}/unlink-from-me?employee_id=100002")
    assert unlink_response.status_code == 200
    after_unlink = client.get("/api/ops/canvas?employee_id=100002")
    assert public_agent_id not in json.dumps(after_unlink.json(), ensure_ascii=False)

    sandbox_response = client.post(
        "/api/agents/sandbox/jobs?employee_id=100001",
        json={
            "title": "Raw Data 확인",
            "task": "CSV raw data를 분석해 이상 여부를 확인",
            "language": "python",
            "code": "from pathlib import Path\nPath('result.json').write_text('{\"ok\": true}', encoding='utf-8')\nprint('ok')",
            "user_confirmed": True,
        },
    )
    assert sandbox_response.status_code == 200
    job = sandbox_response.json()["job"]
    assert job["execution_mode"] in {"agents_sdk_unix_local", "agents_sdk_unavailable", "sandbox_disabled"}
    if job["execution_mode"] == "agents_sdk_unix_local":
        assert job["status"] == "completed"
        assert "ok" in job["stdout"]
        assert job["validation_result"]["state"] == "passed"
        assert any(item["path"] == "result.json" for item in job["artifacts"])

    list_response = client.get("/api/agents/sandbox/jobs?employee_id=100001")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["ok"] is True
    assert list_body["items"]
    assert any(item["job_id"] == job["job_id"] for item in list_body["items"])

    adopt_without_confirmation = client.post(
        f"/api/agents/sandbox/jobs/{job['job_id']}/adopt-evidence?employee_id=100001",
        json={"evidence_state": "verified_evidence"},
    )
    assert adopt_without_confirmation.status_code == 400
    adopt_response = client.post(
        f"/api/agents/sandbox/jobs/{job['job_id']}/adopt-evidence?employee_id=100001",
        json={"evidence_state": "verified_evidence", "validation_note": "source and code checked", "user_confirmed": True},
    )
    assert adopt_response.status_code == 200
    assert adopt_response.json()["job"]["evidence_state"] == "verified_evidence"

    attach_response = client.post(
        "/api/inbox/reports/report-001/attach-evidence?employee_id=100001",
        json={"evidence_refs": [{"type": "sandbox_job", "id": job["job_id"]}], "note": "보고서 근거로 채택", "user_confirmed": True},
    )
    assert attach_response.status_code == 200
    assert attach_response.json()["attachment"]["report_id"] == "report-001"


def test_agent_builder_page_exposes_gems_style_builder(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/agents/builder?employee_id=100001")
    script = (boi_app_module.APP_DIR / "static" / "agent_builder.js").read_text(encoding="utf-8")
    style = (boi_app_module.APP_DIR / "static" / "style.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "/static/agent_builder.js?v=" in response.text
    assert "프롬프트와 선택 자료만으로 업무 Agent를 만들고" in response.text
    assert "GPT-5.5/Agents SDK 테스트" in response.text
    assert 'data-agent-builder-form' in response.text
    assert 'data-agent-builder-sandbox-form' in response.text
    assert 'data-ops-url=""' in response.text
    assert "BoI Operations Center" not in response.text
    assert 'href="/ops?employee_id=100001"' not in response.text
    assert "MCP 서버" in response.text
    assert "Skill" in response.text
    assert "Git repo" in response.text
    assert "바로 테스트" in response.text
    assert "저장/배포" in response.text
    assert "Sandbox 테스트" in response.text
    assert "/api/agents/drafts" in script
    assert "/api/agents/sandbox/jobs" in script
    assert "user_confirmed: true" in script
    assert ".agent-builder-layout" in style
    assert ".agent-builder-result-card" in style


def test_reporting_agents_and_facade_contracts(boi_app_module, monkeypatch, tmp_path):
    client = TestClient(boi_app_module.app)
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_RUNTIME", "contract_only")
    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SANDBOX_ENABLED", False)

    mine = client.get("/api/agents?employee_id=100001&scope=mine&q=분석")
    assert mine.status_code == 200
    mine_items = mine.json()["items"]
    analysis_report_agent = next(item for item in mine_items if item["title"] == "분석 보고서 Agent")
    assert analysis_report_agent["is_system_template"] is True
    assert analysis_report_agent["is_linked_to_me"] is True
    assert "data-analytics:build-report" in analysis_report_agent["skills"]
    assert "data-analytics:visualize-data" in analysis_report_agent["skills"]
    assert "boi-wiki-local" in analysis_report_agent["mcp_servers"]

    available = client.get("/api/agents?employee_id=100001&scope=available&q=Data Analysis Agent")
    assert available.status_code == 200
    assert any(item["title"] == "Data Analysis Agent" for item in available.json()["items"])
    report_available = client.get("/api/agents?employee_id=100001&scope=available&q=Report Agent")
    assert report_available.status_code == 200
    assert any(item["title"] == "Report Agent" for item in report_available.json()["items"])

    canvas = client.get("/api/ops/canvas?employee_id=100001")
    assert canvas.status_code == 200
    canvas_body = canvas.json()
    assert any(node.get("type") == "agentNode" and node.get("data", {}).get("title") == "분석 보고서 Agent" for node in canvas_body["nodes"])

    plan_response = client.post(
        "/api/reporting/analysis-plan?employee_id=100001",
        json={
            "question": "Raw Data 확인 결과를 차트와 함께 보고서로 정리해줘.",
            "target_refs": [{"type": "boi", "ref": "boi:private:100001:sample"}],
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()["plan"]
    assert plan["recommended_agent_id"] == "system-analysis-report-agent"
    assert plan["report_brief"]["question"].startswith("Raw Data")
    assert plan["visualization_candidates"]
    assert plan["confirmation_required"] is True

    job_response = client.post(
        "/api/reporting/analysis-jobs?employee_id=100001",
        json={
            "title": "Raw Data 분석",
            "question": "Raw Data 확인 결과를 표와 차트로 정리",
            "input_artifacts": [{"name": "raw.csv", "content": "ts,value\n1,10\n2,12\n"}],
            "code": "from pathlib import Path\nPath('analysis_summary.md').write_text('# 분석 요약\\n\\nRaw Data 이상 없음', encoding='utf-8')\n",
            "language": "python",
            "user_confirmed": True,
        },
    )
    assert job_response.status_code == 200
    job = job_response.json()["job"]
    assert job["evidence_intent"] == "reporting_analysis"

    job_get = client.get(f"/api/reporting/analysis-jobs/{job['job_id']}?employee_id=100001")
    assert job_get.status_code == 200
    evidence_pack = job_get.json()["analysis_evidence_pack"]
    assert evidence_pack["kind"] == "AnalysisEvidencePack"
    assert evidence_pack["job_id"] == job["job_id"]
    assert "validation_result" in evidence_pack

    draft_response = client.post(
        "/api/reporting/reports/drafts?employee_id=100001",
        json={
            "title": "Raw Data 판단 보고서",
            "report_brief": plan["report_brief"],
            "evidence_refs": [{"type": "sandbox_job", "id": job["job_id"], "label": "Raw Data 분석"}],
            "analysis_job_id": job["job_id"],
            "user_confirmed": True,
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()["draft"]
    assert draft["kind"] == "report_draft"
    assert draft["report_boi"]["kind"] == "ReportBoI"
    visible = json.dumps(draft["report_boi"], ensure_ascii=False)
    assert "source_id" not in visible
    assert "schema" not in visible
    assert "trace" not in visible
    assert "artifact" in visible.lower()

    publish_without_confirmation = client.post(
        f"/api/reporting/reports/drafts/{draft['draft_id']}/publish?employee_id=100001",
        json={"visibility": "private"},
    )
    assert publish_without_confirmation.status_code == 400
    publish_response = client.post(
        f"/api/reporting/reports/drafts/{draft['draft_id']}/publish?employee_id=100001",
        json={"visibility": "private", "user_confirmed": True},
    )
    assert publish_response.status_code == 200
    published = publish_response.json()
    assert published["report_state"] == "published"
    assert "/docs/" in published["doc_url"]


def test_sop_run_graph_and_context_api(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-ops-center-sop-run"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-ops-center-alarm",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {
                "title": "설비 Alarm 발생",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-OPS",
                "wafer_id": "WF-07",
                "alarm_code": "PRESSURE_SPIKE",
            },
        },
        result={"dispatch_result": {"ok": True, "status": "handled", "results": []}},
    )
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-ops-center-raw-missing",
            "action_key": "sop.equipment.request_raw_data",
            "status": "failed",
            "summary": "Raw Data 확인 실패",
            "trace_id": trace_id,
            "event_type": "equipment.alarm.raised.v1",
            "logged_at": "2026-06-30T12:05:00+09:00",
            "payload": {"equipment_id": "ETCH-VM-01", "raw_data_status": "missing"},
        },
    )

    runs = client.get("/api/sop-runs?employee_id=100001&status=open")
    assert runs.status_code == 200
    run = next(item for item in runs.json()["items"] if item["trace_id"] == trace_id)
    run_id = run["run_id"]

    graph = client.get(f"/api/sop-runs/{run_id}/graph?employee_id=100001")
    assert graph.status_code == 200
    graph_body = graph.json()
    assert graph_body["ok"] is True
    assert graph_body["run_id"] == run_id
    assert graph_body["current_stage_id"]
    assert graph_body["nodes"]
    assert graph_body["edges"]
    assert graph_body["decision_packet"]["why_assigned"]
    rendered_graph = json.dumps(graph_body, ensure_ascii=False)
    assert "Raw Data" in rendered_graph

    context = client.get(f"/api/sop-runs/{run_id}/context?employee_id=100001")
    assert context.status_code == 200
    assert context.json()["decision_packet"]["recommended_action"]

    page = client.get(f"/sop-runs/{run_id}?employee_id=100001")
    assert page.status_code == 200
    assert "data-stage-node" in page.text
    assert 'role="button"' in page.text
    assert "data-stage-panel-title" in page.text
    assert "data-stage-panel-summary" in page.text
    assert "sop_run.js" in page.text


def test_boi_inbox_decisions_view_records_item_decision_from_report_card(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-decision-ui",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-decision-ui",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-29T23:55:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-11",
                "lot_id": "LOT-DECISION-UI",
                "wafer_id": "WF-21",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "missing_evidence": "raw_endpoint_confirmation",
                "severity": "high",
            },
        },
    )
    inbox = client.get("/api/inbox?employee_id=100001&limit=50").json()
    item = next(item for item in inbox["items"] if item["task_id"] == "task:act-boi-inbox-decision-ui")
    refresh = client.post(f"/api/inbox/reports/{item['report_id']}/refresh?employee_id=100001")
    assert refresh.status_code == 200

    page = client.get("/inbox?employee_id=100001&view=decisions")
    body = page.text
    assert page.status_code == 200
    assert "승인/조치" in body
    assert "data-inbox-decision-form" in body
    assert 'name="decision"' in body
    assert 'name="note"' in body
    assert "승인" in body
    assert "반려" in body
    assert "보류" in body
    assert "추가 근거 요청" in body
    assert "사유를 입력" in body
    assert "act-boi-inbox-decision-ui" not in re.sub(r'action="[^"]+"', "", body)

    submit = client.post(
        "/inbox/tasks/task:act-boi-inbox-decision-ui/decision?employee_id=100001",
        data={"decision": "reject", "note": "Raw Data endpoint 확인 전이라 반려", "user_confirmed": "true"},
        follow_redirects=False,
    )
    assert submit.status_code == 303
    assert "/inbox?" in submit.headers["location"]
    assert "view=history" in submit.headers["location"]
    decision_rows = [
        row
        for row in boi_app_module.cached_action_log_rows()
        if row.get("completion_for_request_id") == "act-boi-inbox-decision-ui"
    ]
    assert decision_rows
    assert decision_rows[-1]["decision"] == "reject"
    assert decision_rows[-1]["note"] == "Raw Data endpoint 확인 전이라 반려"


def test_boi_inbox_history_view_lists_recorded_decisions_not_open_tasks(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-history-ui",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-history-ui",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T00:20:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-12",
                "lot_id": "LOT-HISTORY-UI",
                "wafer_id": "WF-22",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "severity": "high",
            },
        },
    )
    submit = client.post(
        "/inbox/tasks/task:act-boi-inbox-history-ui/decision?employee_id=100001",
        data={"decision": "reject", "note": "Raw Data 확인 전이라 반려", "user_confirmed": "true"},
        follow_redirects=False,
    )
    assert submit.status_code == 303

    page = client.get("/inbox?employee_id=100001&view=history")
    body = page.text

    assert page.status_code == 200
    assert "처리 이력" in body
    assert "반려" in body
    assert "Raw Data 확인 전이라 반려" in body
    assert "Spec / Rule 변경 요청 승인 필요" in body
    assert "data-inbox-decision-form" not in body
    assert "보고서 생성" not in body
    assert "act-boi-inbox-history-ui" not in body
    assert "trace-boi-inbox-history-ui" not in body


def test_boi_inbox_report_get_is_non_mutating_and_refresh_materializes_item_report(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-refresh-item",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-refresh-item",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T00:10:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-10",
                "lot_id": "LOT-REFRESH",
                "wafer_id": "WF-12",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "missing_evidence": "spec_owner_confirmation",
                "severity": "high",
            },
        },
    )

    inbox = client.get("/api/inbox?employee_id=100001&limit=10")
    item = next(item for item in inbox.json()["items"] if item["task_id"] == "task:act-boi-inbox-refresh-item")
    report_id = item["report_id"]

    first_get = client.get(f"/api/inbox/reports/{report_id}?employee_id=100001")
    web_refresh = client.post(f"/inbox/reports/{report_id}/refresh?employee_id=100001", follow_redirects=False)
    second_get = client.get(f"/api/inbox/reports/{report_id}?employee_id=100001")

    assert first_get.status_code == 200
    assert first_get.json()["report_state"] == "not_ready"
    assert first_get.json()["report"] == {}
    assert web_refresh.status_code == 303
    assert "/docs/" in web_refresh.headers["location"]
    assert second_get.status_code == 200
    body = second_get.json()
    assert body["report_state"] == "ready"
    assert body["report"]["report_type"] == "item"
    assert body["report"]["work_context"]["summary"]
    assert body["report"]["stage_history"]["items"]
    assert body["report"]["decision_support"]["readiness"] == "needs_more_evidence"
    assert body["report"]["decision_support"]["recommended_judgment"] == "추가 근거 요청부터 처리"
    assert body["report"]["comparison"]["items"][0]["decision_support"]["blockers"]
    assert "업무 맥락" in body["boi"]["body"]
    assert "이전 단계 이력" in body["boi"]["body"]
    assert "판단 준비도" in body["boi"]["body"]
    visible_text = json.dumps({"report": body["report"], "boi": body["boi"]}, ensure_ascii=False)
    assert "확인 확인" not in visible_text
    assert "검증 보고서에서 확보된 근거" not in visible_text
    for forbidden in ["source_id", "WorkflowDefinition", "schema", "trace-boi-inbox-refresh-item", "act-boi-inbox-refresh-item"]:
        assert forbidden not in visible_text

    report_page = client.get(web_refresh.headers["location"])
    assert report_page.status_code == 200
    default_visible_html = report_page.text
    for forbidden in ["source_id", "WorkflowDefinition", "schema", "trace-boi-inbox-refresh-item", "act-boi-inbox-refresh-item"]:
        assert forbidden not in default_visible_html


def test_inbox_review_report_strips_ui_fallback_and_runtime_ids_from_visible_text(boi_app_module):
    item = {
        "task_id": "task:assistenza-20260630010101-abcdef",
        "request_id": "assistenza-20260630010101-abcdef",
        "status": "approval_required",
        "action_key": "sop.equipment.change_spec_rule",
        "event_type": "corrective_action.requested.v1",
        "logged_at": "2026-06-30T01:01:01+09:00",
        "business_context": {
            "equipment_id": "ETCH-VM-77",
            "lot_id": "LOT-REPORT-QA",
            "wafer_id": "WF-77",
            "alarm_code": "PRESSURE_SPIKE",
            "trend_status": "abnormal",
            "raw_data_status": "available",
            "missing_evidence": "raw_endpoint_confirmation",
            "approval_risk": "spec_rule_change_required",
        },
        "display": {
            "title": "Spec / Rule 변경 요청 승인 필요",
            "risk_label": "고위험",
            "next_action": "검증 보고서에서 확보된 근거와 부족한 근거를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
        },
        "item_brief": {
            "occurred_at": "2026-06-30T01:01:01+09:00",
            "occurred_at_label": "06-30 01:01",
            "event_or_stage": "이상 조치 요청",
            "difference_summary": "규격/규칙 변경 요청이 assistenza-20260630010101-abcdef 기준으로 접수되었습니다.",
            "recommended_next_check": "검증 보고서에서 확보된 근거와 부족한 근거를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
        },
    }

    report = boi_app_module.inbox_review_report_from_items([item], report_type="item")
    body = boi_app_module.inbox_report_visible_markdown(report)
    visible_text = json.dumps({"report": report, "body": body}, ensure_ascii=False)

    assert "검증 보고서에서 확보된 근거" not in visible_text
    assert "assistenza-20260630010101-abcdef" not in visible_text
    assert "Raw Data endpoint 확인" in visible_text
    assert "Spec/Rule 변경 승인" in visible_text


def test_inbox_report_generation_hydrates_llm_work_context_narrative(boi_app_module, monkeypatch):
    item = {
        "task_id": "task:act-report-llm-hydrate",
        "request_id": "act-report-llm-hydrate",
        "status": "approval_required",
        "action_key": "sop.equipment.change_spec_rule",
        "event_type": "corrective_action.requested.v1",
        "logged_at": "2026-06-30T01:05:00+09:00",
        "summary": "Spec / Rule 변경 요청 승인 필요",
        "business_context": {
            "equipment_id": "ETCH-VM-80",
            "lot_id": "LOT-LLM",
            "alarm_code": "PRESSURE_SPIKE",
            "missing_evidence": "raw_endpoint_confirmation",
        },
    }

    def fake_work_context_pack(employee_id: str, task_id: str = "", **_kwargs):
        assert employee_id == "100001"
        assert task_id == "task:act-report-llm-hydrate"
        return {
            "context_id": "ctx-llm-hydrate",
            "task": {
                "task_id": task_id,
                "action_key": "sop.equipment.change_spec_rule",
                "event_type": "corrective_action.requested.v1",
            },
            "sop_stage": {"sop_stage_id": "correct"},
            "trace_context": {"trace_id": "trace-llm-hydrate", "events": [], "actions": [], "generated_bois": []},
            "workflow_manual_handoffs": [],
            "stage_history_summary": [
                {
                    "source_id": "action:llm",
                    "kind": "action",
                    "title": "Raw Data 확인",
                    "summary": "Raw Data 확인 결과를 검토했습니다.",
                    "status_label": "확인됨",
                    "logged_at": "2026-06-30T01:04:00+09:00",
                }
            ],
            "evidence_summary": {"acquired": [], "missing": ["raw_endpoint_confirmation"]},
            "similar_case_summaries": [],
            "historical_patterns": [],
            "recommended_next_steps": [],
            "draft_completion_note": "",
        }

    def fake_narrative(compact, employee_id, *, async_generate=True):
        assert async_generate is False
        assert employee_id == "100001"
        return {
            "summary_state": "ready",
            "overall_summary": {"text": "LLM 요약: ETCH-VM-80의 압력 Spike 승인 전 Raw Data endpoint 확인이 필요합니다."},
            "difference_summary": {"text": "LLM 비교: LOT-LLM은 Raw Data endpoint 확인만 남아 있습니다."},
            "recommended_action_note": {"text": "LLM 권장: Raw Data endpoint를 먼저 확인한 뒤 승인 또는 반려 사유를 남기세요."},
            "source_ids": ["action:llm"],
        }

    monkeypatch.setattr(boi_app_module, "work_context_pack", fake_work_context_pack)
    monkeypatch.setattr(boi_app_module, "work_context_narrative_for_compact", fake_narrative)

    hydrated = boi_app_module.hydrate_inbox_report_items("100001", [item])
    assert hydrated[0]["work_context_narrative"]["summary_state"] == "ready"
    assert "LLM 비교" in hydrated[0]["item_brief"]["difference_summary"]

    report = boi_app_module.inbox_review_report_from_items(hydrated, report_type="item")
    body = boi_app_module.inbox_report_visible_markdown(report)

    assert "LLM 비교" in body
    assert "LLM 권장" in body


def test_inbox_review_report_evidence_hides_internal_routing_statuses(boi_app_module):
    item = {
        "task_id": "task:act-report-routing-status",
        "request_id": "act-report-routing-status",
        "status": "approval_required",
        "action_key": "sop.equipment.change_spec_rule",
        "event_type": "corrective_action.requested.v1",
        "logged_at": "2026-06-30T01:10:00+09:00",
        "business_context": {
            "equipment_id": "ETCH-VM-78",
            "lot_id": "LOT-REPORT-STATUS",
            "wafer_id": "WF-78",
            "alarm_code": "PRESSURE_SPIKE",
            "trend_status": "abnormal",
            "raw_data_status": "available",
            "missing_evidence": "raw_endpoint_confirmation",
        },
        "context_preview": {
            "evidence_summary": {
                "acquired": [
                    {"summary": "설비 Alarm 발생 발생 · 실행됨"},
                    {"summary": "설비 Alarm 발생 발생 · 라우팅"},
                    {"summary": "설비 Alarm 발생 발생 · 처리 중"},
                ],
                "missing": ["raw_endpoint_confirmation"],
            }
        },
    }

    report = boi_app_module.inbox_review_report_from_items([item], report_type="item")
    body = boi_app_module.inbox_report_visible_markdown(report)

    assert "발생 발생" not in body
    assert "라우팅" not in body
    assert "처리 중" not in body
    assert "설비 Alarm 발생" in body


def test_inbox_review_report_separates_simulation_from_verified_evidence(boi_app_module):
    item = {
        "task_id": "task:act-report-simulated-evidence",
        "request_id": "act-report-simulated-evidence",
        "status": "approval_required",
        "action_key": "sop.equipment.change_spec_rule",
        "event_type": "corrective_action.requested.v1",
        "logged_at": "2026-06-30T01:20:00+09:00",
        "business_context": {
            "equipment_id": "ETCH-VM-79",
            "lot_id": "LOT-REPORT-SIM",
            "wafer_id": "WF-79",
            "alarm_code": "PRESSURE_SPIKE",
            "missing_evidence": "raw_data_endpoint",
        },
        "context_preview": {
            "stage_history_summary": [
                {
                    "kind": "action",
                    "title": "품질 시스템 Response Trend 확인",
                    "summary": "SIMULATED dry_run 품질 시스템 Trend 이상 결과",
                    "status_label": "실행됨",
                    "simulation": True,
                    "simulation_label": "SIMULATED",
                    "logged_at": "2026-06-30T01:19:00+09:00",
                },
                {
                    "kind": "event",
                    "title": "이상 조치 요청",
                    "summary": "이상 조치 요청 발생",
                    "logged_at": "2026-06-30T01:20:00+09:00",
                },
            ],
            "evidence_summary": {
                "acquired": [
                    {
                        "label": "시뮬레이션 Trend",
                        "summary": "SIMULATED simulated_prerequisite Trend 이상",
                        "simulation": True,
                        "provenance": "simulated_prerequisite",
                    }
                ],
                "missing": ["raw_data_endpoint"],
            },
        },
    }

    report = boi_app_module.inbox_review_report_from_items([item], report_type="item")
    body = boi_app_module.inbox_report_visible_markdown(report)
    verified_text = json.dumps(
        {
            "stage_history": report["stage_history"],
            "evidence": report["evidence"],
            "decision_support": report["decision_support"],
        },
        ensure_ascii=False,
    )

    assert "품질 시스템 Response Trend 확인" not in verified_text
    assert "시뮬레이션 Trend" not in verified_text
    assert report["simulation_results"]["items"]
    assert "시뮬레이션 결과" in body
    assert "품질 시스템 Response Trend 확인" in body
    assert "SIMULATED" not in body
    assert "simulated_prerequisite" not in body
    assert "dry_run" not in body
    assert report["decision_support"]["readiness"] == "needs_more_evidence"
    assert "raw_data_endpoint" not in body
    assert "Raw Data endpoint 확인" in body


def test_boi_inbox_manifest_warms_individual_reports_before_group_rollup(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_WARM_LIMIT", 1)
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_MAX_IN_FLIGHT", 1)
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_DELAY_SECONDS", 60.0)
    with boi_app_module._INBOX_REPORT_LOCK:
        boi_app_module._INBOX_REPORT_IN_FLIGHT.clear()
        boi_app_module._INBOX_REPORT_QUEUE.clear()
        boi_app_module._INBOX_REPORT_LAST_ERRORS.clear()
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-warm-item-first",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-warm-item-first",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T00:20:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-30",
                "lot_id": "LOT-WARM",
                "wafer_id": "WF-30",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "missing_evidence": "raw_confirmation",
                "severity": "high",
            },
        },
    )

    inbox = client.get("/api/inbox?employee_id=100001&limit=1")

    assert inbox.status_code == 200
    body = inbox.json()
    item = next(item for item in body["items"] if item["task_id"] == "task:act-boi-inbox-warm-item-first")
    group = body["groups"][0]
    assert body["report_warmup_scheduled"] == 1
    assert item["report_state"] in {"pending", "ready"}
    assert group["rollup_only"] is True
    assert group["report_scope"] == "item"
    assert "report_state" not in group
    assert "report_boi_url" not in group


def test_boi_inbox_manifest_queues_multiple_item_reports_without_blocking_groups(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_WARM_LIMIT", 3)
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_MAX_IN_FLIGHT", 1)
    monkeypatch.setattr(boi_app_module, "INBOX_REPORT_BACKGROUND_DELAY_SECONDS", 60.0)
    with boi_app_module._INBOX_REPORT_LOCK:
        boi_app_module._INBOX_REPORT_IN_FLIGHT.clear()
        boi_app_module._INBOX_REPORT_QUEUE.clear()
        boi_app_module._INBOX_REPORT_LAST_ERRORS.clear()
    client = TestClient(boi_app_module.app)
    request_ids = [f"act-boi-inbox-queued-{idx}" for idx in range(3)]
    for idx, request_id in enumerate(request_ids):
        append_action_log_row(
            boi_app_module,
            {
                "employee_id": "100001",
                "request_id": request_id,
                "action_key": "sop.equipment.change_spec_rule",
                "status": "approval_required",
                "summary": "Spec / Rule 변경 요청 승인 필요",
                "trace_id": f"trace-boi-inbox-queued-{idx}",
                "event_type": "corrective_action.requested.v1",
                "logged_at": f"2026-06-30T00:3{idx}:00+09:00",
                "payload": {
                    "equipment_id": f"ETCH-VM-4{idx}",
                    "lot_id": f"LOT-QUEUE-{idx}",
                    "wafer_id": f"WF-4{idx}",
                    "alarm_code": "PRESSURE_SPIKE",
                    "trend_status": "abnormal",
                    "raw_data_status": "available",
                    "missing_evidence": "raw_confirmation",
                    "severity": "high",
                },
            },
        )

    inbox = client.get("/api/inbox?employee_id=100001&limit=3")

    assert inbox.status_code == 200
    body = inbox.json()
    assert body["report_warmup_scheduled"] == 3
    queued_items = [item for item in body["items"] if item["task_id"].replace("task:", "") in request_ids]
    assert len(queued_items) == 3
    assert {item["report_state"] for item in queued_items} == {"pending"}
    with boi_app_module._INBOX_REPORT_LOCK:
        assert len(boi_app_module._INBOX_REPORT_IN_FLIGHT) == 1
        assert len(boi_app_module._INBOX_REPORT_QUEUE) >= 2


def test_data_lake_disabled_contract_is_optional(boi_app_module):
    client = TestClient(boi_app_module.app)
    status = client.get("/api/data-lake/status?employee_id=100001")
    sources = client.get("/api/data-lake/sources?employee_id=100001")
    plan = client.post(
        "/api/data-lake/query/plan?employee_id=100001",
        json={"question": "HBM4 low-yield LOT 근거를 찾아줘", "limit": 5},
    )
    preview = client.post(
        "/api/data-lake/query/preview?employee_id=100001",
        json={"question": "HBM4 low-yield LOT 근거를 찾아줘", "limit": 5},
    )
    execute = client.post(
        "/api/data-lake/query/execute?employee_id=100001",
        json={"question": "실행", "user_confirmed": False},
    )

    assert status.status_code == 200
    assert status.json()["core_required"] is False
    assert status.json()["enabled"] is False
    for response in (sources, plan, preview, execute):
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "disabled"
        assert body["enabled"] is False
        assert body["core_required"] is False
        assert body["user_facing_name"] == "Data Lake"
        assert body["data_lake"]["core_required"] is False


def test_data_lake_enabled_fixture_adapter_plan_preview_execute_and_artifact(boi_app_module, tmp_path, monkeypatch):
    fixture_root = tmp_path / "ontology"
    fixture_path = fixture_root / "exports"
    fixture_path.mkdir(parents=True)
    (fixture_path / "etch_process_sequence_by_product_route.csv").write_text(
        "product,route,step,equipment,lot_id\n"
        "PFO-A,R1,ETCH,ETCH-VM-01,LOT-A-240626\n"
        "PFO-B,R2,CVD,CVD-HT-04,LOT-B-240626\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_PROFILE", "local-full-datalake")
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_FIXTURE_ROOT", fixture_root)
    client = TestClient(boi_app_module.app)

    status = client.get("/api/data-lake/status?employee_id=100001")
    sources = client.get("/api/data-lake/sources?employee_id=100001")
    plan = client.post(
        "/api/data-lake/query/plan?employee_id=100001",
        json={"question": "ETCH LOT-A route 근거를 찾아줘", "source": "etch_process_sequence", "limit": 5},
    )
    preview = client.post(
        "/api/data-lake/query/preview?employee_id=100001",
        json={"question": "ETCH LOT-A route 근거를 찾아줘", "source": "etch_process_sequence", "limit": 5},
    )
    execute = client.post(
        "/api/data-lake/query/execute?employee_id=100001",
        json={
            "question": "ETCH LOT-A route 근거를 찾아줘",
            "source": "etch_process_sequence",
            "limit": 5,
            "user_confirmed": True,
        },
    )

    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["status"] == "ready"
    assert any(source["available"] for source in status.json()["fixture_sources"])
    assert sources.status_code == 200
    assert sources.json()["status"] == "ready"
    assert plan.status_code == 200
    assert plan.json()["status"] == "planned"
    assert plan.json()["rows"] == []
    assert preview.status_code == 200
    assert preview.json()["status"] == "preview_ready"
    assert preview.json()["rows"][0]["equipment"] == "ETCH-VM-01"
    assert execute.status_code == 200
    assert execute.json()["status"] == "executed"
    artifact_id = execute.json()["artifacts"][0]["artifact_id"]
    artifact = client.get(f"/api/data-lake/artifacts/{artifact_id}?employee_id=100001")
    assert artifact.status_code == 200
    assert artifact.json()["status"] == "ready"
    assert artifact.json()["rows"][0]["lot_id"] == "LOT-A-240626"


def test_data_lake_status_reports_optional_service_reachability(boi_app_module, tmp_path, monkeypatch):
    fixture_root = tmp_path / "ontology"
    fixture_path = fixture_root / "exports"
    fixture_path.mkdir(parents=True)
    (fixture_path / "etch_process_sequence_by_product_route.csv").write_text(
        "product,route,step,equipment,lot_id\n"
        "PFO-A,R1,ETCH,ETCH-VM-01,LOT-A-240626\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_PROFILE", "local-full-datalake")
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_FIXTURE_ROOT", fixture_root)
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_POSTGRES_DSN", "postgresql://user:pass@127.0.0.1:1/db")
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_MINIO_ENDPOINT", "http://127.0.0.1:1")
    client = TestClient(boi_app_module.app)

    status = client.get("/api/data-lake/status?employee_id=100001")

    assert status.status_code == 200
    body = status.json()
    assert body["core_required"] is False
    assert body["enabled"] is True
    assert body["configured"] is True
    assert body["status"] == "service_degraded"
    assert body["services"]["postgres"]["configured"] is True
    assert body["services"]["postgres"]["reachable"] is False
    assert body["services"]["minio"]["configured"] is True
    assert body["services"]["minio"]["reachable"] is False
    assert body["adapter"] == "fixture_file"


def test_data_lake_import_materializes_private_data_context_boi(boi_app_module, tmp_path, monkeypatch):
    shutil.rmtree(boi_app_module.DATA_ROOT / "private" / "100001" / "data-context", ignore_errors=True)
    fixture_root = tmp_path / "ontology"
    fixture_path = fixture_root / "exports"
    fixture_path.mkdir(parents=True)
    (fixture_path / "etch_process_sequence_by_product_route.csv").write_text(
        "product_id,route_id,oper_seq,operation_name,area,detail_area\n"
        "A123456-A1,flow_ABC,050,STI ETCH,ETCH,DRY\n"
        "A123456-A1,flow_ABC,150,GATE ETCH,ETCH,DRY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_PROFILE", "local-full-datalake")
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_FIXTURE_ROOT", fixture_root)
    client = TestClient(boi_app_module.app)

    rejected = client.post(
        "/api/data-lake/import?employee_id=100001",
        json={"source_ids": ["ontology.exports.etch_process_sequence"], "user_confirmed": False},
    )
    imported = client.post(
        "/api/data-lake/import?employee_id=100001",
        json={"source_ids": ["ontology.exports.etch_process_sequence"], "user_confirmed": True},
    )
    sources_after = client.get("/api/data-lake/sources?employee_id=100001")

    assert rejected.status_code == 400
    assert imported.status_code == 200
    body = imported.json()
    assert body["ok"] is True
    assert body["status"] == "imported"
    assert body["created_count"] == 1
    doc = body["items"][0]["boi"]
    assert doc["metadata"]["type"] == "boi/data-context"
    assert doc["metadata"]["visibility"] == "private"
    assert "data-context" in doc["uri"]
    assert "ETCH process sequence" in doc["body"]
    assert "product_id" in doc["body"]
    assert body["items"][0]["url"].startswith("/docs/")
    source_entry = next(
        source for source in sources_after.json()["sources"]
        if source["source_id"] == "ontology.exports.etch_process_sequence"
    )
    assert source_entry["data_context_boi_url"].startswith("/docs/")
    assert source_entry["data_context_boi_ref"] == doc["metadata"]["boi_id"]


def test_inbox_report_uses_enabled_data_lake_as_optional_evidence(boi_app_module, tmp_path, monkeypatch):
    fixture_root = tmp_path / "ontology"
    fixture_path = fixture_root / "exports"
    fixture_path.mkdir(parents=True)
    (fixture_path / "etch_process_sequence_by_product_route.csv").write_text(
        "product,route,step,equipment,lot_id,wafer_id,alarm_code\n"
        "PFO-A,R1,ETCH,ETCH-VM-21,LOT-DL-001,WF-DL-01,PRESSURE_SPIKE\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_ENABLED", True)
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_PROFILE", "local-full-datalake")
    monkeypatch.setattr(boi_app_module, "BOI_DATALAKE_FIXTURE_ROOT", fixture_root)
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-boi-inbox-datalake-item",
            "action_key": "sop.equipment.change_spec_rule",
            "status": "approval_required",
            "summary": "Spec / Rule 변경 요청 승인 필요",
            "trace_id": "trace-boi-inbox-datalake-item",
            "event_type": "corrective_action.requested.v1",
            "logged_at": "2026-06-30T00:25:00+09:00",
            "payload": {
                "equipment_id": "ETCH-VM-21",
                "lot_id": "LOT-DL-001",
                "wafer_id": "WF-DL-01",
                "alarm_code": "PRESSURE_SPIKE",
                "trend_status": "abnormal",
                "raw_data_status": "available",
                "severity": "high",
            },
        },
    )

    inbox = client.get("/api/inbox?employee_id=100001&limit=20")
    item = next(item for item in inbox.json()["items"] if item["task_id"] == "task:act-boi-inbox-datalake-item")
    refresh = client.post(f"/api/inbox/reports/{item['report_id']}/refresh?employee_id=100001")
    report = client.get(f"/api/inbox/reports/{item['report_id']}?employee_id=100001").json()

    assert refresh.status_code == 200
    assert report["report_state"] == "ready"
    assert report["report"]["data_lake"]["status"] == "ready"
    assert report["report"]["data_lake"]["items"]
    assert report["report"]["decision_support"]["readiness"] in {
        "needs_more_evidence",
        "individual_review_ready",
        "review_ready",
    }
    assert report["report"]["decision_support"]["recommended_judgment"]
    assert "Data Lake 근거" in report["boi"]["body"]
    visible_text = json.dumps({"report": report["report"], "boi": report["boi"]}, ensure_ascii=False)
    assert "Data Lake" in visible_text
    for forbidden in ["source_id", "WorkflowDefinition", "trace-boi-inbox-datalake-item", "act-boi-inbox-datalake-item"]:
        assert forbidden not in visible_text


def test_pet_agent_static_scripts_parse_before_runtime_smokes(boi_app_module):
    if not shutil.which("node"):
        pytest.skip("node is required for Pet Agent JavaScript syntax check")

    repo_root = Path(__file__).resolve().parents[1]
    static_scripts = [
        repo_root / "boi_api/app/static/pet_agent.js",
        repo_root / "boi_api/app/static/mermaid_render.js",
    ]

    for script_path in static_scripts:
        result = subprocess.run(
            ["node", "--check", str(script_path)],
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr

    pet_script = static_scripts[0].read_text(encoding="utf-8")
    assert pet_script.count("form?.requestSubmit();") == 1
    assert pet_script.count("const bodyRows = lines.slice(2)") == 1
    assert "stage_history_summary" not in pet_script
    assert "similar_case_summaries" not in pet_script
    assert "work_context_narrative" not in pet_script
    assert "업무 맥락 요약을 준비 중입니다" not in pet_script
    assert "renderTaskDisplay" in pet_script
    assert "Action ${escapeHtml(trace.action_count" not in pet_script


def test_mermaid_loader_retries_after_cdn_load_failure(boi_app_module):
    script = (boi_app_module.APP_DIR / "static" / "mermaid_render.js").read_text(encoding="utf-8")

    assert "let loadPromise = null;" in script
    assert "let settled = false;" in script
    assert "loadPromise = null;" in script
    assert "script.remove();" in script
    assert "script.onerror = () => fail(new Error(\"Mermaid library load failed\"));" in script
    assert "fail(new Error(\"Mermaid library load timed out\"))" in script
    assert 'new CustomEvent("boi:mermaid-rendered"' in script
    assert 'state === "rendered" || state === "fallback"' in script


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
  hasRunSummary: runSummaryHtml.includes("Agent가 확인한 근거") && runSummaryHtml.includes("관련 지식 검색") && runSummaryHtml.includes("권한/보안 가드레일"),
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


def test_pet_agent_artifact_renderer_consumes_agent_response_contract(boi_app_module):
    if not shutil.which("node"):
        pytest.skip("node is required for Pet Agent artifact renderer smoke")
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

const mermaid = "flowchart TD\n  A[Start] --> B[End]";
const message = {
  text: [
    "## SOP Flow",
    "",
    "```mermaid",
    mermaid,
    "```",
  ].join("\n"),
  artifacts: [
    { type: "mermaid", title: "SOP Flow", source: mermaid },
    { type: "mermaid", title: "Duplicate Flow", source: mermaid },
    { type: "gap_table", title: "Action Gap", data: [{ item: "Trend", status: "ready", link: "[Spec](/docs/boi:public:actions:api:request-trend-history?employee_id=100001)" }] },
    { type: "workflow_summary", title: "Workflow", data: [{ stage: "detect", action: "collect evidence" }] },
    { type: "task_cards", title: "Tasks", data: [{ title: "공유 전 승인 필요", status_label: "승인 필요", why_it_matters: "외부 공유 전 확인", next_action: "내용 확인" }] },
    { type: "image", title: "Preview", url: "/static/assets/boi-agent-pet.png", alt: "BoI Agent pet" },
    { type: "confirmation_required", title: "요청 실행 전 확인", data: { operation: "event_publish", payload: { event_type: "demo.v1" }, primary_label: "요청 실행" } },
  ],
};
const executionOnlyMessage = {
  text: "실행 전 확인이 필요합니다.",
  artifacts: [],
  executionCards: [
    {
      operation: "event_publish",
      title: "이벤트 발행 확인",
      primary_label: "요청 실행",
      required_role: "boi.workflow_runner",
      permission: { allowed: false, reason: "missing_role", role: "boi.workflow_runner" },
      payload: { event_type: "demo.v1" },
      display: { status_label: "권한 필요", risk_label: "권한 필요: boi.workflow_runner" },
      technical_details: { operation: "event_publish", required_role: "boi.workflow_runner" },
    },
  ],
};

const items = window.BoiAgentMarkdownDebug.artifactItems(message);
const html = window.BoiAgentMarkdownDebug.renderArtifacts(message, 0);
const executionHtml = window.BoiAgentMarkdownDebug.renderArtifacts(executionOnlyMessage, 1);
console.log(JSON.stringify({
  artifactItemCount: items.length,
  mermaidDiagramCount: (html.match(/mermaid-diagram/g) || []).length,
  hasGapTable: html.includes("Action Gap") && html.includes("<table"),
  rendersMarkdownLinkInTable: html.includes('href="/docs/boi:public:actions:api:request-trend-history?employee_id=100001"'),
  hasWorkflowSummary: html.includes("Workflow") && html.includes("detect"),
  hasTaskCard: html.includes("공유 전 승인 필요") && html.includes("내용 확인"),
  hasImageViewerButton: html.includes("BoI Agent pet") && html.includes("data-open-artifact"),
  hasConfirmationCard: html.includes("요청 실행 전 확인") && html.includes("data-agent-approve"),
  hasTechnicalDetails: html.includes("기술 세부정보"),
  rendersExecutionCards: executionHtml.includes("이벤트 발행 확인") && executionHtml.includes("권한 필요"),
  disablesDeniedExecution: executionHtml.includes("boi.workflow_runner") && !executionHtml.includes("data-agent-approve data-operation"),
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

    assert payload["artifactItemCount"] == 6
    assert payload["mermaidDiagramCount"] == 1
    assert payload["hasGapTable"]
    assert payload["rendersMarkdownLinkInTable"]
    assert payload["hasWorkflowSummary"]
    assert payload["hasTaskCard"]
    assert payload["hasImageViewerButton"]
    assert payload["hasConfirmationCard"]
    assert payload["hasTechnicalDetails"]
    assert payload["rendersExecutionCards"]
    assert payload["disablesDeniedExecution"]


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
        assert "이상 감지" in page_context["workflow_stage_names"]
        assert "equipment.alarm.raised.v1" in page_context["workflow_event_types"]
        assert "sop.equipment.request_trend_history" in page_context["workflow_actions"]
        assert "manual.equipment.confirm_alarm_context" in page_context["workflow_manual_actions"]
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
    assert "specific_page_terms" in prompt
    assert "contextual_candidate_tasks" in prompt
    assert "equipment.alarm.raised.v1" in prompt
    assert "sop.equipment.request_trend_history" in prompt
    assert "manual.equipment.confirm_alarm_context" in prompt
    assert "avoid suggestions that could fit any unrelated page" in prompt
    assert "natural user-facing sentence" in prompt
    assert "Mermaid 플로우 생성" in prompt


def test_boi_agent_suggestions_accept_answer_context_for_followups(boi_app_module, monkeypatch):
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
                                        "방금 만든 Mermaid에서 Action Spec 누락을 점검해줘.",
                                        "원본 매핑 표를 기준으로 수동 조치만 따로 정리해줘.",
                                        "이 SOP 실행 전 승인이나 확인이 필요한 항목을 알려줘.",
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
        json={
            "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
            "page_context": {"title": "설비 이상 SOP"},
            "answer_context": {
                "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
                "answer_summary": "Mermaid artifact와 원본 매핑 표를 생성했습니다.",
                "route": "deep",
                "intent": "diagram",
                "artifacts": [{"type": "mermaid", "title": "SOP workflow"}],
                "affordances": [{"type": "check_gap", "label": "Action Spec 누락 점검"}],
                "links": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions_source"] == "answer_scoped_llm"
    assert body["suggestions"][0].startswith("방금 만든 Mermaid")
    prompt = payloads[0]["json"]["messages"][1]["content"]
    assert "boi_agent_answer_followups" in prompt
    assert "answer_context" in prompt
    assert "Action Spec 누락 점검" in prompt
    assert "boi_agent_page_suggestions_only" not in prompt


def test_boi_agent_suggestions_strip_markdown_artifacts(boi_app_module):
    suggestions = boi_app_module.normalize_llm_suggestions(
        {
            "suggestions": [
                "1. `equipment.alarm.raised.v1` 발생 시 대응 절차 알려줘",
                "- 현재 SOP의 Action Spec 누락 점검해줘",
                "워크플로우를 Mermaid 다이어그램으로 시각화해줘",
                "24시간 이벤트 로그를 기준으로 이상 흐름 찾아줘",
            ]
        }
    )

    assert suggestions[0] == "equipment.alarm.raised.v1 발생 시 대응 절차 알려줘"
    assert suggestions[1] == "현재 SOP의 Action Spec 누락 점검해줘"
    assert suggestions[3] == "24시간 이벤트 로그를 기준으로 이상 흐름 찾아줘"
    assert all("`" not in item for item in suggestions)


def test_boi_agent_suggestions_strip_internal_affordance_labels(boi_app_module):
    suggestions = boi_app_module.normalize_llm_suggestions(
        {
            "suggestions": [
                'check_gap: "이 Mermaid 흐름에서 부족한 Action Spec을 점검해줘."',
                "make_artifact: 이 흐름을 업무 관계 표로 정리해줘.",
                "What would they want next?",
            ]
        }
    )

    assert suggestions == [
        "이 Mermaid 흐름에서 부족한 Action Spec을 점검해줘.",
        "이 흐름을 업무 관계 표로 정리해줘.",
    ]
    assert all(":" not in item.split()[0] for item in suggestions)


def test_boi_agent_suggestions_strip_model_planning_prefixes(boi_app_module):
    suggestions = boi_app_module.normalize_llm_suggestions(
        {
            "suggestions": [
                "Idea 2: Ask about the Raw Data comparison -> Raw Data 확인 결과를 대조해줘.",
                'Suggestion 1: "현재 승인이 필요한 공정 Hold 항목을 보여줘."',
                "Follow-up: 단면검사 판단 전에 Map View에서 확인할 패턴을 알려줘.",
                'Focus on the SOP mentioned. "설비 이상 대응 SOP의 상세 내용을 보여줘',
            ]
        }
    )

    assert suggestions == [
        "Raw Data 확인 결과를 대조해줘.",
        "현재 승인이 필요한 공정 Hold 항목을 보여줘.",
        "단면검사 판단 전에 Map View에서 확인할 패턴을 알려줘.",
        "설비 이상 대응 SOP의 상세 내용을 보여줘",
    ]
    assert all("Idea" not in item and "Suggestion" not in item and "Focus" not in item and "->" not in item for item in suggestions)


def test_boi_agent_suggestions_accept_single_answer_scoped_question(boi_app_module):
    suggestions = boi_app_module.normalize_llm_suggestions(
        {
            "suggestions": [
                "부족한 업무 요청 명세 초안을 먼저 만들어줘",
                "다음 Event는 무엇인가요?",
                "수동 조치는 어떻게 해야 하나요?",
                "승인 전에 확인할 근거를 정리해 주세요.",
            ]
        }
    )

    assert suggestions == [
        "부족한 업무 요청 명세 초안을 먼저 만들어줘",
        "다음 Event는 무엇인가요?",
        "수동 조치는 어떻게 해야 하나요?",
        "승인 전에 확인할 근거를 정리해 주세요.",
    ]


def test_boi_agent_suggestions_reject_noun_phrase_only_outputs(boi_app_module):
    with pytest.raises(boi_app_module.BoiAgentSuggestionsUnavailable):
        boi_app_module.normalize_llm_suggestions(
            {
                "suggestions": [
                    "장비 보전 가이드",
                    "Response Trend",
                ]
            }
        )


def test_boi_agent_suggestions_parse_plain_llm_question_lines(boi_app_module):
    payload = boi_app_module.parse_suggestions_payload(
        "1. 이 요청과 유사한 WorkflowDefinition을 먼저 검색해줘.\n"
        "2. 신규 Event Type 초안을 만들기 전에 필요한 payload를 정리해줘."
    )

    assert payload == {
        "suggestions": [
            "이 요청과 유사한 WorkflowDefinition을 먼저 검색해줘.",
            "신규 Event Type 초안을 만들기 전에 필요한 payload를 정리해줘.",
        ]
    }


def test_boi_agent_suggestions_parse_common_llm_alias_fields(boi_app_module):
    payload = boi_app_module.parse_suggestions_payload(
        '검토 결과입니다.\n{"suggested_questions":["승인 전에 필요한 근거 문서를 보여줘."]}'
    )

    assert payload == {"suggestions": ["승인 전에 필요한 근거 문서를 보여줘."]}


def test_boi_agent_suggestions_parse_raw_json_array(boi_app_module):
    payload = boi_app_module.parse_suggestions_payload(
        '["이 Action을 실행하기 전에 입력 payload를 점검해줘."]'
    )

    assert payload == {"suggestions": ["이 Action을 실행하기 전에 입력 payload를 점검해줘."]}


def test_boi_agent_suggestions_drop_placeholder_questions(boi_app_module):
    suggestions = boi_app_module.normalize_llm_suggestions(
        {
            "suggestions": [
                "...",
                "확인",
                "이 답변의 근거 문서를 자세히 설명해줘",
            ]
        }
    )

    assert suggestions == ["이 답변의 근거 문서를 자세히 설명해줘"]


def test_boi_agent_suggestions_degrade_when_required_llm_unavailable(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)

    def broken_suggestions(req, employee_id: str, page_context):
        raise boi_app_module.BoiAgentSuggestionsUnavailable("suggestion model timeout")

    monkeypatch.setattr(boi_app_module, "BOI_AGENT_SUGGESTIONS_REQUIRED", True)
    monkeypatch.setattr(boi_app_module, "call_boi_agent_suggestions_llm", broken_suggestions)

    response = client.post(
        "/api/agents/boi-wiki/suggestions?employee_id=100001",
        json={"current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["suggestions_state"] == "failed"
    assert body["suggestions_source"] in {"page_context_after_llm_error", "unavailable"}
    assert body["component_errors"][0]["status"] == "boi_agent_suggestions_unavailable"
    assert body["component_errors"][0]["required"] is True
    assert "suggestion model timeout" in body["component_errors"][0]["message"]


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
            "acl_policy": "acl:private:100001",
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
    assert "WorkflowDefinition" not in response.text
    assert "Capability Pack" not in response.text
    assert "Workflow Status" not in response.text


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


def test_boi_api_respects_explicit_limit_without_changing_total_count(boi_app_module):
    client = TestClient(boi_app_module.app)

    full = client.get("/api/boi?employee_id=100001&q=SOP")
    limited = client.get("/api/boi?employee_id=100001&q=SOP&limit=2&page=1")

    assert full.status_code == 200
    assert limited.status_code == 200
    full_body = full.json()
    limited_body = limited.json()
    assert full_body["count"] >= 2
    assert limited_body["count"] == full_body["count"]
    assert limited_body["returned_count"] == 2
    assert len(limited_body["items"]) == 2
    assert limited_body["limit"] == 2
    assert limited_body["page"] == 1


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
        "/?employee_id=100001": ("library", "explorer"),
        "/events?employee_id=100001": ("events", "event_history"),
        "/event-types?employee_id=100001": ("events", "event_catalog"),
        "/actions?employee_id=100001": ("actions", "action_catalog"),
        "/actions?employee_id=100001&view=history": ("actions", "action_history"),
        "/sops?employee_id=100001": ("sops", "sop_catalog"),
        "/sops/new?employee_id=100001": ("sops", "sop_add"),
        "/sops/new?employee_id=100001&focus=event": ("sops", "sop_add"),
        "/sops/new?employee_id=100001&focus=action": ("sops", "sop_add"),
        "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001": ("sops", "sop_catalog"),
        "/workflows/definitions?employee_id=100001": ("library", "explorer"),
        "/permissions?employee_id=100001": ("advanced", "permissions"),
    }

    for url, (active_nav, active_subnav) in cases.items():
        response = client.get(url)
        assert response.status_code == 200
        assert 'class="app-header"' in response.text
        assert 'class="global-nav"' in response.text
        assert 'class="section-subnav"' in response.text
        assert 'class="page-actions"' not in response.text
        assert 'class="page-primary-actions"' not in response.text
        assert 'class="utility-nav"' not in response.text
        assert len(re.findall(r'data-nav-id="(?:library|sops|events|actions|advanced)"', response.text)) == 5
        assert "BoI Wiki" in response.text
        assert "SOP" in response.text
        assert "Event Broker" in response.text
        assert "Action" in response.text
        assert "Advanced" in response.text
        assert 'data-nav-id="connections"' not in response.text
        assert "/static/mermaid_render.js?v=" in response.text
        if active_nav == "advanced":
            assert "권한 관리" in response.text
            assert "Agent Builder" in response.text
            assert "Kafka" in response.text
            assert "BoI Wiki API" in response.text
            assert "BoI Wiki MCP" in response.text
        else:
            assert "Agent Builder" not in response.text
            assert "Kafka UI" not in response.text
            assert "MCP Status" not in response.text
        assert "DEV" in response.text
        assert "SSO 가이드" in response.text
        assert 'class="identity-strip"' in response.text
        assert 'class="auth-card"' not in response.text
        assert 'class="auth-mode-banner"' not in response.text
        assert 'class="dev-employee-switch"' in response.text
        if active_nav:
            assert re.search(rf'<a[^>]+data-nav-id="{active_nav}"[^>]+aria-current="page"', response.text)
        if active_subnav:
            assert re.search(rf'<a[^>]+data-subnav-id="{active_subnav}"[^>]+aria-current="page"', response.text)

    home = client.get("/?employee_id=100001")
    assert "BoI Wiki Explorer" in home.text
    assert "public, team, private 아래 업무 단위 폴더와 문서를 탐색합니다." in home.text
    assert "<title>BoI Wiki</title>" in home.text

    agent_builder = client.get("/agents/builder?employee_id=100001", follow_redirects=False)
    assert agent_builder.status_code == 200
    assert "Agent Builder" in agent_builder.text
    assert "GPT-5.5/Agents SDK 테스트" in agent_builder.text
    assert "/api/agents/drafts?employee_id=100001" in agent_builder.text


def test_app_shell_infers_same_host_tool_urls_for_external_host(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KAFKA_UI_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("BOI_WIKI_MCP_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app, base_url="http://boi-wiki.example:28000")

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'class="utility-nav"' not in response.text

    advanced = client.get("/permissions?employee_id=100001")
    assert advanced.status_code == 200
    assert "BoI Wiki API" in advanced.text
    assert 'href="/docs"' in advanced.text
    assert 'href="http://boi-wiki.example:28081"' in advanced.text
    assert 'href="http://boi-wiki.example:28200"' in advanced.text
    assert "http://localhost" not in advanced.text


def test_app_shell_uses_request_domain_when_external_url_is_blank_or_local(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://localhost:8000")
    monkeypatch.delenv("LANGFLOW_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KAFKA_UI_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("BOI_WIKI_MCP_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("ACTION_GATEWAY_EXTERNAL_URL", raising=False)
    client = TestClient(boi_app_module.app, base_url="http://wiki.example.internal:28000")

    response = client.get("/?employee_id=100001")
    advanced = client.get("/permissions?employee_id=100001")

    assert response.status_code == 200
    assert advanced.status_code == 200
    assert 'href="/docs"' in advanced.text
    assert 'href="http://wiki.example.internal:28081"' in advanced.text
    assert 'href="http://wiki.example.internal:28200"' in advanced.text
    assert "http://localhost" not in advanced.text


def test_app_shell_uses_configured_external_tool_urls(boi_app_module, monkeypatch):
    monkeypatch.setenv("BOI_EXTERNAL_URL", "http://boi-wiki.example:28000")
    monkeypatch.setenv("LANGFLOW_EXTERNAL_URL", "http://langflow.example:27860")
    monkeypatch.setenv("KAFKA_UI_EXTERNAL_URL", "http://kafka-ui.example:28081")
    monkeypatch.setenv("BOI_WIKI_MCP_EXTERNAL_URL", "http://boi-wiki-mcp.example:28200")
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001", headers={"host": "boi-wiki.example:28000"})
    advanced = client.get("/permissions?employee_id=100001", headers={"host": "boi-wiki.example:28000"})
    builder = client.get("/agents/builder?employee_id=100001", headers={"host": "boi-wiki.example:28000"})

    assert response.status_code == 200
    assert advanced.status_code == 200
    assert builder.status_code == 200
    assert "http://langflow.example:27860" not in advanced.text
    assert "http://langflow.example:27860" in builder.text
    assert "http://kafka-ui.example:28081" in advanced.text
    assert "http://boi-wiki-mcp.example:28200" in advanced.text
    assert "http://localhost:7860" not in advanced.text
    assert "http://localhost:8081" not in advanced.text
    assert "http://localhost:8200" not in advanced.text


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


def test_dedicated_registration_new_pages_and_legacy_start_redirects(boi_app_module):
    client = TestClient(boi_app_module.app)
    response = client.get("/sops/new?employee_id=100001")

    assert response.status_code == 200
    assert "SOP 추가" in response.text
    assert "어떤 업무를 SOP 실행 흐름으로 정리할까요?" in response.text
    assert 'data-entry-kind="sop"' in response.text
    assert 'data-focus=""' in response.text
    assert "/api/sop-registration/drafts" in response.text
    assert "/api/sop-registration/plan" in response.text
    assert "1. Event" not in response.text
    assert "<h3>Event</h3>" in response.text
    assert "<h3>SOP</h3>" in response.text
    assert "<h3>Action</h3>" in response.text
    assert "기존 Event 선택" in response.text
    assert "새 Event 초안 만들기" in response.text
    assert "이력 패턴으로 만들기" in response.text
    assert "정해진 시간에 발생" in response.text
    assert "기존 SOP 선택" in response.text
    assert "신규 SOP 초안" in response.text
    assert "기존 Action 선택" in response.text
    assert "새 Action 초안" in response.text
    assert "Manual Action 초안" in response.text
    assert "이번에는 건너뛰기" in response.text
    assert "Agent 제안" in response.text
    assert "추천 받기" in response.text
    assert "선택한 항목으로 확인" in response.text
    assert "업무 단위 폴더" in response.text
    assert "일정 설정" in response.text
    assert "매주 월요일 09:00에 Event 초안이 만들어집니다." in response.text
    assert 'name="schedule_config"' in response.text
    assert "Cron 표현식" not in response.text
    assert "고급 설정" in response.text
    assert "Cron 직접 입력" in response.text
    assert "SOP 실행 흐름 초안 만들기" in response.text
    assert "검증하기" in response.text

    redirects = {
        "/workflows/definitions?employee_id=100001&start=sop": "/sops/new?employee_id=100001",
        "/workflows/definitions?employee_id=100001&start=event-type": "/sops/new?employee_id=100001&focus=event",
        "/workflows/definitions?employee_id=100001&start=action": "/sops/new?employee_id=100001&focus=action",
        "/event-types/new?employee_id=100001": "/sops/new?employee_id=100001&focus=event",
        "/actions/new?employee_id=100001": "/sops/new?employee_id=100001&focus=action",
        "/workflows/new?employee_id=100001&focus=action": "/sops/new?employee_id=100001&focus=action",
    }
    for source, target in redirects.items():
        response = client.get(source, follow_redirects=False)
        assert response.status_code in {302, 303, 307}
        assert response.headers["location"] == target


def test_action_new_page_renders_seven_connector_wizard_instead_of_free_text_kind(boi_app_module):
    client = TestClient(boi_app_module.app)

    redirect = client.get("/actions/new?employee_id=100001", follow_redirects=False)
    assert redirect.status_code in {302, 303, 307}
    assert redirect.headers["location"] == "/sops/new?employee_id=100001&focus=action"

    response = client.get("/sops/new?employee_id=100001&focus=action")

    assert response.status_code == 200
    text = response.text
    assert "<h3>Action</h3>" in text
    assert "기존 Action 선택" in text
    assert "새 Action 초안" in text
    assert "Manual Action 초안" in text
    for connector in ["API", "MCP", "Webhook", "Manual", "Event Broker", "BoI Writer", "Langflow"]:
        assert connector in text
    for connector_kind in ["api", "mcp", "webhook", "manual", "event_broker", "boi_writer", "langflow"]:
        assert f'data-connector-kind="{connector_kind}"' in text
    assert 'name="execution_kind"' not in text
    assert 'name="connector_kind"' in text
    assert 'data-connector-panel="api"' not in text


def test_registration_draft_api_creates_validates_and_requires_confirmation_to_publish(boi_app_module):
    client = TestClient(boi_app_module.app)

    create = client.post(
        "/api/registration/drafts?employee_id=100001",
        json={
            "entry_kind": "action",
            "scope": "team",
            "folder": "team/aix-tf/direct-development/reporting",
            "title": "Response Trend 확인 Action",
            "business_goal": "직개발 Reporting 전에 Response Trend 근거를 확인한다.",
            "connector_kind": "api",
            "connector_config": {"method": "POST", "endpoint": "https://quality.example/api/response-trend"},
            "input_fields": ["lot_id", "wafer_id", "trend_window"],
            "output_fields": ["trend_status", "evidence_refs"],
            "linked_event_types": ["direct_development.result_check.requested.v1"],
            "risk_level": "medium",
            "approval_required": False,
        },
    )

    assert create.status_code == 200
    body = create.json()
    assert body["ok"] is True
    assert body["draft"]["entry_kind"] == "action"
    assert body["draft"]["status"] == "draft"
    assert body["draft"]["draft_boi"]["metadata"]["type"] == "boi/action-draft"
    assert body["draft"]["catalog_patch_proposal"]["kind"] == "action"
    assert "dedupe_candidates" in body["draft"]
    assert body["draft"]["publish_confirmation"]["requires_confirmation"] is True

    draft_id = body["draft"]["draft_id"]
    validate = client.post(f"/api/registration/drafts/{draft_id}/validate?employee_id=100001")
    assert validate.status_code == 200
    validation = validate.json()["draft"]["validation"]
    assert validation["valid"] is True
    assert "dedupe" in validation["checks"]
    assert "rbac" in validation["checks"]

    blocked = client.post(f"/api/registration/drafts/{draft_id}/publish?employee_id=100001", json={})
    assert blocked.status_code == 400
    assert "user_confirmed" in blocked.text

    publish = client.post(
        f"/api/registration/drafts/{draft_id}/publish?employee_id=100001",
        json={"operation": "registration_draft_publish", "user_confirmed": True, "note": "test publish request"},
    )
    assert publish.status_code == 200
    published = publish.json()
    assert published["draft"]["status"] == "publish_requested"
    assert published["draft"]["entry_kind"] == "action"
    assert published["draft"]["catalog_applied"] is False


def test_action_registration_draft_validates_connector_specific_required_fields(boi_app_module):
    client = TestClient(boi_app_module.app)
    connector_cases = {
        "api": {"connector_config": {"method": "POST", "endpoint": "https://quality.example/api/trends", "auth_profile": "quality-api"}, "input_fields": ["equipment_id"], "output_fields": ["trend_status"]},
        "mcp": {"connector_config": {"server": "timesfm", "tool": "forecast", "auth_profile": "service-token"}, "input_fields": ["series"], "output_fields": ["forecast"]},
        "webhook": {"connector_config": {"direction": "outbound", "url": "https://hook.example/events", "method": "POST"}, "input_fields": ["payload"], "output_fields": ["http_status"]},
        "manual": {"connector_config": {"assignee_policy": "role:equipment_owner", "completion_criteria": "근거 확인 후 승인/반려 기록"}, "input_fields": ["evidence_refs"], "output_fields": ["decision"]},
        "event_broker": {"connector_config": {"event_type": "maintenance.guide.requested.v1", "topic": "boi.events", "idempotency_key_fields": ["trace_id"]}, "input_fields": ["trace_id"], "output_fields": ["event_id"]},
        "boi_writer": {"connector_config": {"boi_type": "boi/analysis", "target_folder": "public/equipment/anomaly-response", "template": "analysis-summary"}, "input_fields": ["source_refs"], "output_fields": ["boi_id"]},
        "langflow": {"connector_config": {"flow_ref": "equipment-stage-analysis", "endpoint": "stage-analysis"}, "input_fields": ["event"], "output_fields": ["analysis"]},
    }

    for connector_kind, payload in connector_cases.items():
        create = client.post(
            "/api/registration/drafts?employee_id=100001",
            json={
                "entry_kind": "action",
                "scope": "private",
                "title": f"{connector_kind} Action",
                "business_goal": f"{connector_kind} 방식으로 반도체 업무 근거를 처리한다.",
                "connector_kind": connector_kind,
                "linked_event_types": ["equipment.alarm.raised.v1"],
                **payload,
            },
        )
        assert create.status_code == 200
        draft = create.json()["draft"]
        assert draft["catalog_patch_proposal"]["connector_kind"] == connector_kind
        assert draft["catalog_patch_proposal"]["connector_config"] == payload["connector_config"]

        validate = client.post(f"/api/registration/drafts/{draft['draft_id']}/validate?employee_id=100001")
        assert validate.status_code == 200
        validation = validate.json()["draft"]["validation"]
        assert validation["valid"] is True, validation

    missing = client.post(
        "/api/registration/drafts?employee_id=100001",
        json={
            "entry_kind": "action",
            "scope": "private",
            "title": "불완전 API Action",
            "business_goal": "필수 endpoint가 빠진 API action을 검증한다.",
            "connector_kind": "api",
            "input_fields": ["equipment_id"],
            "output_fields": ["trend_status"],
        },
    )
    draft_id = missing.json()["draft"]["draft_id"]
    validate_missing = client.post(f"/api/registration/drafts/{draft_id}/validate?employee_id=100001")
    assert validate_missing.status_code == 200
    invalid = validate_missing.json()["draft"]["validation"]
    assert invalid["valid"] is False
    assert any("api.endpoint" in error for error in invalid["errors"])


def test_registration_plan_preview_and_explorer_support_natural_language_flow(boi_app_module):
    client = TestClient(boi_app_module.app)

    event_plan = client.post(
        "/api/registration/plan?employee_id=100001",
        json={
            "entry_kind": "event",
            "raw_request": "ETCH 장비 Alarm이 발생하면 Trend와 Raw Data를 남기고 SOP에 연결하고 싶어",
            "scope": "private",
        },
    )
    assert event_plan.status_code == 200
    plan = event_plan.json()
    assert plan["ok"] is True
    assert plan["target_kind"] == "event"
    assert plan["draft_payload"]["topic"] == boi_app_module.BOI_EVENTS_TOPIC
    assert "payload_fields" in plan["field_candidates"]
    assert plan["candidate_references"]["event_types"]

    preview = client.post(
        "/api/registration/verification-preview?employee_id=100001",
        json={"entry_kind": "event", "plan": plan, "payload": plan["draft_payload"]},
    )
    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["preview_type"] == "registration_verification"
    assert "dry_run" in preview_body["internal_terms_hidden"]
    assert any(card["title"] == "과거 처리 이력" for card in preview_body["cards"])

    explorer = client.get("/api/registration/explorer?employee_id=100001&entry_kind=sop&scope=public")
    assert explorer.status_code == 200
    explorer_body = explorer.json()
    assert explorer_body["ok"] is True
    assert "public/sop" in explorer_body["root_hints"]
    assert explorer_body["folders"]["free_hierarchy"] is True

    candidates = client.get("/api/registration/link-candidates?employee_id=100001&entry_kind=action&q=trend&scope=all")
    assert candidates.status_code == 200
    candidate_body = candidates.json()
    assert candidate_body["ok"] is True
    assert candidate_body["groups"]["event_types"]
    assert candidate_body["groups"]["actions"]


def test_sop_registration_plan_preview_draft_and_publish_guard(boi_app_module):
    client = TestClient(boi_app_module.app)

    plan_response = client.post(
        "/api/sop-registration/plan?employee_id=100001",
        json={
            "raw_request": "ETCH 장비 Alarm이 발생하면 Trend와 Raw Data를 확인하고 보전 조치 Action까지 연결하는 SOP가 필요해",
            "scope": "private",
            "folder": "private/100001/sop-drafts",
            "focus": "event",
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["ok"] is True
    assert plan["plan_type"] == "sop_registration_plan"
    assert plan["event_section"]["section_id"] == "event"
    assert plan["sop_section"]["section_id"] == "sop"
    assert plan["action_sections"][0]["section_id"] == "action"
    assert plan["schedule_section"]["topic_default"] == boi_app_module.BOI_EVENTS_TOPIC
    assert plan["draft_payload"]["event_mode"] == "draft"
    assert plan["draft_payload"]["sop_mode"] == "skip"
    assert plan["draft_payload"]["action_mode"] == "skip"
    assert plan["recommended_next_step"]

    preview_response = client.post(
        "/api/sop-registration/preview?employee_id=100001",
        json={"plan": plan, "payload": {**plan["draft_payload"], "sop_mode": "draft", "steps": ["이상 감지", "Trend 확인"]}},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["preview_type"] == "sop_registration_preview"
    assert any(card["title"] == "Event" for card in preview["cards"])
    assert "payload" in preview["internal_terms_hidden"]
    assert "schema" in preview["internal_terms_hidden"]
    assert "topic" in preview["internal_terms_hidden"]

    create_response = client.post(
        "/api/sop-registration/drafts?employee_id=100001",
        json={"plan": plan, "payload": {**plan["draft_payload"], "sop_mode": "draft", "steps": ["이상 감지", "Trend 확인"]}},
    )
    assert create_response.status_code == 200
    draft = create_response.json()["draft"]
    assert draft["entry_kind"] == "sop_registration"
    assert draft["status"] == "draft"
    assert draft["catalog_applied"] is False
    assert draft["component_draft_payloads"]["event"]["event_type"]

    draft_id = draft["draft_id"]
    validate_response = client.post(f"/api/sop-registration/drafts/{draft_id}/validate?employee_id=100001")
    assert validate_response.status_code == 200
    validation = validate_response.json()["draft"]["validation"]
    assert validation["valid"] is True
    assert "draft_first" in validation["checks"]

    blocked = client.post(f"/api/sop-registration/drafts/{draft_id}/publish?employee_id=100001", json={})
    assert blocked.status_code == 400
    assert "user_confirmed" in blocked.text

    publish_response = client.post(
        f"/api/sop-registration/drafts/{draft_id}/publish?employee_id=100001",
        json={"operation": "sop_registration_publish", "user_confirmed": True, "note": "확인"},
    )
    assert publish_response.status_code == 200
    published = publish_response.json()["draft"]
    assert published["status"] == "publish_requested"
    assert published["catalog_applied"] is False


def test_sop_registration_schedule_config_replaces_cron_for_general_users(boi_app_module):
    client = TestClient(boi_app_module.app)

    schedule_config = {
        "repeat_type": "weekly",
        "time": "09:00",
        "weekdays": ["MON"],
        "timezone": "Asia/Seoul",
    }
    plan_response = client.post(
        "/api/sop-registration/plan?employee_id=100001",
        json={
            "raw_request": "매주 월요일 9시에 FAB Trend 보고 Event 초안을 만들고 싶어",
            "scope": "private",
            "folder": "private/100001/sop-drafts",
            "focus": "event",
            "payload": {"event_mode": "schedule", "schedule_config": schedule_config},
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["schedule_section"]["enabled"] is True
    assert plan["schedule_section"]["schedule_summary"] == "매주 월요일 09:00에 Event 초안이 만들어집니다."
    assert plan["schedule_section"]["cron"] == "0 9 * * MON"

    payload = {
        **plan["draft_payload"],
        "event_mode": "schedule",
        "schedule_config": schedule_config,
    }
    preview_response = client.post(
        "/api/sop-registration/preview?employee_id=100001",
        json={"plan": plan, "payload": payload},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["schedule_section"]["schedule_summary"] == "매주 월요일 09:00에 Event 초안이 만들어집니다."
    assert preview["schedule_section"]["cron"] == "0 9 * * MON"

    create_response = client.post(
        "/api/sop-registration/drafts?employee_id=100001",
        json={"plan": plan, "payload": payload},
    )
    assert create_response.status_code == 200
    draft = create_response.json()["draft"]
    assert draft["schedule_section"]["schedule_summary"] == "매주 월요일 09:00에 Event 초안이 만들어집니다."
    assert draft["schedule_section"]["cron"] == "0 9 * * MON"

    validate_response = client.post(f"/api/sop-registration/drafts/{draft['draft_id']}/validate?employee_id=100001")
    assert validate_response.status_code == 200
    validation = validate_response.json()["draft"]["validation"]
    assert validation["valid"] is True
    assert all("cron" not in warning.lower() for warning in validation["warnings"])

    missing = client.post(
        "/api/sop-registration/drafts?employee_id=100001",
        json={
            "plan": {"raw_request": "", "schedule_section": {}, "draft_payload": {}},
            "payload": {
                "entry_kind": "sop",
                "event_mode": "schedule",
                "sop_mode": "skip",
                "action_mode": "skip",
                "business_goal": "정기 Event 초안",
                "schedule_text": "",
                "cron": "",
                "schedule_config": {},
            },
        },
    )
    missing_draft = missing.json()["draft"]
    missing_validate = client.post(f"/api/sop-registration/drafts/{missing_draft['draft_id']}/validate?employee_id=100001")
    assert missing_validate.status_code == 200
    warnings = missing_validate.json()["draft"]["validation"]["warnings"]
    assert any("일정을 선택" in warning for warning in warnings)


def test_event_pattern_preview_and_sop_history_are_business_oriented(boi_app_module):
    client = TestClient(boi_app_module.app)

    pattern = client.post(
        "/api/events/patterns/preview?employee_id=100001",
        json={"q": "definitely-no-such-event-pattern", "limit": 3},
    )
    assert pattern.status_code == 200
    pattern_body = pattern.json()
    assert pattern_body["preview_type"] == "event_pattern"
    assert pattern_body["low_sample_warning"] is True
    assert "참고 데이터가 적" not in pattern_body.get("summary", "")

    history_api = client.get("/api/sops/history?employee_id=100001&limit=5")
    assert history_api.status_code == 200
    assert history_api.json()["ok"] is True

    history_page = client.get("/sops/history?employee_id=100001")
    assert history_page.status_code == 200
    assert "SOP 수행 이력" in history_page.text
    assert "SOP 기준 최근 실행 현황, 남은 승인, 수동 조치를 확인합니다." in history_page.text
    assert 'href="/sops/history?employee_id=100001"' in client.get("/sops?employee_id=100001").text


def test_registration_new_pages_use_natural_language_and_preview_flow(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/sops/new?employee_id=100001")
    assert response.status_code == 200
    text = response.text
    assert "어떤 업무를 SOP 실행 흐름으로 정리할까요?" in text
    assert "추천 받기" in text
    assert "선택/보강" in text
    assert "선택한 항목으로 확인" in text
    assert "폴더 선택" in text
    assert "기존 Event 탐색" in text
    assert "기존 SOP 탐색" in text
    assert "기존 Action 탐색" in text
    assert "고급 설정" in text
    assert "직접 ID 입력" not in text
    assert "dry run" not in text.lower()

    event_redirect = client.get("/event-types/new?employee_id=100001", follow_redirects=False)
    action_redirect = client.get("/actions/new?employee_id=100001", follow_redirects=False)
    assert event_redirect.headers["location"] == "/sops/new?employee_id=100001&focus=event"
    assert action_redirect.headers["location"] == "/sops/new?employee_id=100001&focus=action"


def test_doc_page_moves_local_links_into_document_actions(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert 'class="page-actions"' not in response.text
    assert 'class="page-primary-actions"' not in response.text
    header = response.text.split("</header>", 1)[0]
    assert "폴더로 돌아가기" not in header
    assert "Source 보기 / 검증 편집" not in header
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
            "acl_policy": "acl:private:100001",
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
    assert "Action 찾기" in response.text
    assert "최근 Action 실행 이력" not in response.text
    assert "Action 실행 요청, 승인 대기, 수동 조치" not in response.text
    assert "manual.equipment.approve_process_hold" in response.text
    assert "manual handoff" in response.text
    assert "/docs/boi:public:actions:manual:approve-process-hold" in response.text
    assert "/docs/boi:public:actions:api:block-process-progress" in response.text


def test_action_history_page_is_separated_from_catalog(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-page-test",
            "action_key": "sop.equipment.request_trend_history",
            "status": "success",
            "summary": "Action history page test",
            "trace_id": "trace-action-history-page-test",
            "event_type": "equipment.alarm.raised.v1",
            "logged_at": boi_app_module.now_iso(),
        },
    )

    response = client.get("/actions?employee_id=100001&view=history")

    assert response.status_code == 200
    assert "Action 실행 이력" in response.text
    assert "최근 Action 실행 요청, 승인 대기, 수동 조치, 결과 로그를 시간순으로 확인합니다." in response.text
    assert "act-history-page-test" in response.text
    assert "Action 찾기" not in response.text
    assert "curl -X POST" not in response.text
    assert "Event를 BoI로 자산화" not in response.text


def test_action_history_page_default_path_renders_next_page_url(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-next-page-a",
            "action_key": "sop.equipment.request_trend_history",
            "status": "success",
            "summary": "Action history next page A",
            "trace_id": "trace-action-history-next-page",
            "event_type": "equipment.alarm.raised.v1",
            "logged_at": "2099-01-01T10:00:00+09:00",
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-next-page-b",
            "action_key": "sop.equipment.request_raw_data",
            "status": "success",
            "summary": "Action history next page B",
            "trace_id": "trace-action-history-next-page",
            "event_type": "equipment.alarm.raised.v1",
            "logged_at": "2099-01-01T10:01:00+09:00",
        },
    )

    response = client.get("/actions?employee_id=100001&view=history&limit=1")

    assert response.status_code == 200
    assert "Action 실행 이력" in response.text
    assert "다음 더 보기" in response.text
    assert "employee_id=100001" in response.text
    assert "view=history" in response.text
    assert "employee_id=100001&amp;employee_id=100001" not in response.text


def test_api_action_logs_filter_and_normalize_operational_history(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-filter-failed",
            "action_key": "sop.equipment.request_trend_history",
            "status": "failed",
            "summary": "Trend 확인 실패: connector timeout",
            "trace_id": "trace-action-history-filter",
            "event_type": "equipment.alarm.raised.v1",
            "connector_kind": "langflow",
            "logged_at": "2099-01-01T10:00:00+09:00",
            "result": {"summary": "Trend 확인 실패: connector timeout"},
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-filter-success",
            "action_key": "sop.equipment.request_raw_data",
            "status": "invoked",
            "summary": "Raw Data 확인 완료",
            "trace_id": "trace-action-history-filter",
            "event_type": "root_cause.analysis.requested.v1",
            "connector_kind": "api",
            "logged_at": "2099-01-01T10:01:00+09:00",
        },
    )

    response = client.get(
        "/api/actions/logs?employee_id=100001&status=FAILED&q=trend&connector_kind=langflow&limit=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["summary"]["failed"] == 1
    assert body["summary"]["shown"] == 1
    assert body["filters"]["status"] == "failed"
    assert body["filters"]["q"] == "trend"
    item = body["items"][0]
    assert item["request_id"] == "act-history-filter-failed"
    assert item["status"] == "failed"
    assert item["status_label"] == "실패"
    assert item["action_display_name"]
    assert "Trend 확인 실패" in item["result_summary"]
    assert item["workflow_run_url"].startswith("/workflows/equipment-anomaly/status?")
    assert item["raw_url"].startswith("/actions/raw/")
    user_link_labels = [link["label"] for link in item["user_links"]]
    assert "업무 상태 보기" in user_link_labels
    assert "관련 SOP 보기" in user_link_labels
    assert "Action 보기" in user_link_labels
    assert "업무 흐름 정의" not in user_link_labels
    assert "WorkflowDefinition" not in user_link_labels
    assert item["technical_links"][0]["url"] == item["workflow_definition_url"]


def test_action_history_page_renders_filters_summary_and_agent_analysis_cta(boi_app_module):
    client = TestClient(boi_app_module.app)
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-ui-failed",
            "action_key": "sop.equipment.request_trend_history",
            "status": "failed",
            "summary": "Trend 확인 실패",
            "trace_id": "trace-action-history-ui",
            "event_type": "equipment.alarm.raised.v1",
            "connector_kind": "langflow",
            "logged_at": "2099-01-01T10:02:00+09:00",
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-ui-success",
            "action_key": "sop.equipment.request_raw_data",
            "status": "invoked",
            "summary": "Raw Data 확인 완료",
            "trace_id": "trace-action-history-ui",
            "event_type": "root_cause.analysis.requested.v1",
            "connector_kind": "api",
            "logged_at": "2099-01-01T10:03:00+09:00",
        },
    )

    response = client.get("/actions?employee_id=100001&view=history&status=FAILED&q=trend&limit=20")

    assert response.status_code == 200
    assert "Action 실행 이력" in response.text
    assert "Action 실행 조건" in response.text
    assert 'name="status"' in response.text
    assert 'name="connector_kind"' in response.text
    assert 'name="q"' in response.text
    assert "실패" in response.text
    assert "승인 필요" in response.text
    assert "Agent에게 이 조건으로 분석" in response.text
    assert "act-history-ui-failed" in response.text
    assert "act-history-ui-success" not in response.text
    assert "업무 상태 보기" in response.text
    assert "업무 흐름 정의" not in response.text
    assert "관련 SOP 보기" in response.text
    assert "Action 보기" in response.text
    assert "원본 기록" in response.text
    assert "curl -X POST" not in response.text
    assert "Event를 BoI로 자산화" not in response.text


def test_action_history_page_context_uses_filtered_action_logs_for_agent(boi_app_module):
    append_action_log_row(
        boi_app_module,
        {
            "employee_id": "100001",
            "request_id": "act-history-context-failed",
            "action_key": "sop.equipment.request_trend_history",
            "status": "failed",
            "summary": "Trend 확인 실패",
            "trace_id": "trace-action-history-context",
            "event_type": "equipment.alarm.raised.v1",
            "connector_kind": "langflow",
            "logged_at": "2099-01-01T10:04:00+09:00",
        },
    )

    context = boi_app_module.resolve_agent_page_context(
        "/actions?employee_id=100001&view=history&status=failed&q=trend",
        "100001",
    )

    assert context["page_kind"] == "action_history"
    assert context["resolved"] is True
    assert context["filters"]["status"] == "failed"
    assert context["summary"]["failed"] >= 1
    assert any(item["request_id"] == "act-history-context-failed" for item in context["action_logs"])


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
        assert "업무 상태 보기" in text
        assert "처리 타임라인" in text
        assert "Action 실행 결과" in text
        assert "수동 조치" in text
        assert "생성 BoI" in text
        assert "실행 관계" in text
        assert "Workflow Status" not in text
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
    assert body["business_context"]["equipment_id"] == "ETCH-VM-01"
    assert body["business_context"]["lot_id"] == "LOT-001"
    assert body["business_context"]["wafer_id"] == "WF-001"
    assert body["business_context"]["trend_status"] == packets["quality_system_response_trend"]["fields"]["trend_status"]
    assert body["context_pack"]["business_context"].get("alarm_code") or body["business_context"]["trend_status"]
    assert body["simulation_result"]["generated_result"]["real_system_connected"] is False
    assert body["simulation_result"]["generated_result"]["business_context"]["equipment_id"] == "ETCH-VM-01"
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
    assert "업무 상태 보기" in response.text
    assert "Workflow Status" not in response.text
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


def test_work_context_pack_includes_trace_history_and_low_sample_patterns(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-work-context-pack"
    request_id = "act-work-context-current"
    action_key = "manual.test.work_context_confirm_alarm_context"

    append_event_log_row(
        boi_app_module,
        {
            "event_id": "evt-work-context-1",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "status": "processed",
            "logged_at": boi_app_module.now_iso(),
            "payload": {"equipment_id": "EQ-1", "alarm_code": "A-1"},
        },
    )
    append_action_log_row(
        boi_app_module,
        {
            "request_id": "act-work-context-trend",
            "employee_id": "100001",
            "trace_id": trace_id,
            "event_id": "evt-work-context-1",
            "event_type": "equipment.alarm.raised.v1",
            "action_key": "sop.equipment.request_trend_history",
            "status": "success",
            "summary": "Trend 확인 완료",
            "logged_at": boi_app_module.now_iso(),
        },
    )
    generated = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/action",
            "title": "Work Context Generated BoI",
            "description": "trace context generated evidence",
            "tags": ["WorkContext"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:work-context:generated",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_event": {"event_id": "evt-work-context-1", "event_type": "equipment.alarm.raised.v1", "trace_id": trace_id},
        },
        "# Summary\n\nTrend 확인 결과를 근거로 알람 맥락을 확인했습니다.",
    )
    assert generated
    for index in range(2):
        append_action_log_row(
            boi_app_module,
            {
                "request_id": f"act-work-context-history-{index}",
                "employee_id": "100001",
                "trace_id": f"trace-work-context-history-{index}",
                "event_type": "equipment.alarm.raised.v1",
                "action_key": action_key,
                "status": "manual_completed",
                "outcome": "completed",
                "note": "Trend와 Raw Data 확인 후 현장 담당자에게 조치 내용을 공유했습니다.",
                "logged_at": boi_app_module.now_iso(),
            },
        )
    append_action_log_row(
        boi_app_module,
        {
            "request_id": request_id,
            "employee_id": "100001",
            "trace_id": trace_id,
            "event_id": "evt-work-context-1",
            "event_type": "equipment.alarm.raised.v1",
            "action_key": action_key,
            "status": "manual_required",
            "summary": "알람 맥락 확인 필요",
            "logged_at": boi_app_module.now_iso(),
        },
    )

    response = client.get(f"/api/context/work?employee_id=100001&task_id=task:{request_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["task"]["request_id"] == request_id
    assert body["trace_context"]["trace_id"] == trace_id
    assert any(item["action_key"] == "sop.equipment.request_trend_history" for item in body["trace_context"]["actions"])
    assert any(item["boi_id"] == "boi:private:100001:work-context:generated" for item in body["trace_context"]["generated_bois"])
    assert body["historical_patterns"]
    pattern = body["historical_patterns"][0]
    assert 2 <= pattern["sample_size"] <= 3
    assert pattern["low_sample_warning"] is True
    assert "참고 데이터가 적" in pattern["confidence_label"]
    assert body["recommended_next_steps"]
    assert any(
        item["kind"] == "action" and "Trend 확인 완료" in item["summary"]
        for item in body["stage_history_summary"]
    )
    assert all(item.get("source_id") for item in body["stage_history_summary"])
    assert any(
        item["kind"] == "generated_boi" and "Work Context Generated BoI" in item["title"]
        for item in body["stage_history_summary"]
    )
    assert "Trend 확인 완료" in json.dumps(body["evidence_summary"], ensure_ascii=False)
    assert body["similar_case_summaries"]
    assert all(item.get("source_id") for item in body["similar_case_summaries"])
    assert body["similar_case_summaries"][0]["low_sample_warning"] is True
    assert "Trend와 Raw Data" in body["similar_case_summaries"][0]["note_excerpt"]
    assert "Trend와 Raw Data" in body["draft_completion_note"] or "Trend 확인 완료" in body["draft_completion_note"]
    assert body["work_context_narrative"]["summary_state"] == "pending"
    assert body["work_context_narrative"]["stage_history_narrative"] == []

    inbox = client.get("/api/agents/boi-wiki/inbox?employee_id=100001&include_context=compact&limit=20")
    assert inbox.status_code == 200
    target = next(item for item in inbox.json()["items"] if item["request_id"] == request_id)
    compact = target["context_preview"]
    assert any("Trend 확인 완료" in item["summary"] for item in compact["stage_history_summary"])
    assert any("Work Context Generated BoI" in item["title"] for item in compact["stage_history_summary"])
    assert "Trend 확인 완료" in json.dumps(compact["evidence_summary"], ensure_ascii=False)
    assert compact["similar_case_summaries"]
    assert compact["similar_case_summaries"][0]["low_sample_warning"] is True
    assert "Trend와 Raw Data" in compact["similar_case_summaries"][0]["note_excerpt"]
    assert "Trend와 Raw Data" in compact["draft_completion_note"] or "Trend 확인 완료" in compact["draft_completion_note"]
    assert target["work_context_narrative"]["summary_state"] == "pending"
    assert compact["work_context_narrative"]["summary_state"] == "pending"
    assert not any(step.get("label") == "Trend 확인 근거 확보" for step in compact["recommended_next_steps"])


def test_stage_history_summary_keeps_focused_action_and_dedupes_event_lifecycle(boi_app_module):
    trace_context = {
        "events": [
            {
                "event_id": "evt-current",
                "event_type": "equipment.alarm.raised.v1",
                "status": "published",
                "logged_at": "2026-06-30T09:00:00+09:00",
            },
            {
                "event_id": "evt-current",
                "event_type": "equipment.alarm.raised.v1",
                "status": "routing",
                "logged_at": "2026-06-30T09:00:10+09:00",
            },
            {
                "event_id": "evt-current",
                "event_type": "equipment.alarm.raised.v1",
                "status": "handling",
                "logged_at": "2026-06-30T09:00:20+09:00",
            },
        ],
        "actions": [
            {
                "request_id": "act-old",
                "action_key": "boi.materialize_event",
                "status": "materialized",
                "result_summary": "관련 BoI 문서를 생성했습니다.",
                "logged_at": "2026-06-30T09:01:00+09:00",
            },
            {
                "request_id": "act-current",
                "action_key": "sop.equipment.change_spec_rule",
                "status": "approval_required",
                "result_summary": "Spec/Rule 변경 승인을 위해 Trend와 Raw Data 확인이 필요합니다.",
                "logged_at": "2026-06-30T09:05:00+09:00",
            },
        ],
        "generated_bois": [],
    }

    summary = boi_app_module.work_context_stage_history_summary(
        trace_context,
        limit=3,
        focus_event_id="evt-current",
        focus_event_type="equipment.alarm.raised.v1",
        focus_action_key="sop.equipment.change_spec_rule",
        focus_request_id="act-current",
    )

    visible_text = json.dumps(summary, ensure_ascii=False)
    assert sum(1 for item in summary if item["kind"] == "event") == 1
    assert any(item.get("request_id") == "act-current" for item in summary)
    assert "Spec/Rule 변경 승인" in visible_text
    assert "라우팅" not in visible_text
    assert "처리 중" not in visible_text


def test_work_context_narrative_requires_source_bound_business_sentences(boi_app_module):
    compact = {
        "context_id": "ctx-test",
        "stage_history_summary": [
            {
                "kind": "action",
                "source_id": "action:act-trend",
                "title": "Trend 확인",
                "summary": "Trend 확인 Action 완료",
            }
        ],
        "similar_case_summaries": [
            {
                "source_id": "case:case-1",
                "note_excerpt": "Trend와 Raw Data 확인 후 현장 담당자에게 공유했습니다.",
                "sample_size": 2,
                "low_sample_warning": True,
            }
        ],
    }
    context_hash = boi_app_module.work_context_narrative_hash(compact)

    ready = boi_app_module.normalize_work_context_narrative_payload(
        {
            "overall_summary": {
                "text": "Trend 확인 결과가 확보되어 알람 맥락 판단을 위한 추세 근거가 준비되었습니다.",
                "source_ids": ["action:act-trend"],
            },
            "difference_summary": {
                "text": "이번 건은 Trend 근거는 있으나 Raw Data 대조 여부를 추가로 확인해야 합니다.",
                "source_ids": ["action:act-trend", "case:case-1"],
            },
            "recommended_action_note": {
                "text": "Raw Data 대조 결과를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
                "source_ids": ["action:act-trend", "case:case-1"],
            },
            "stage_history_narrative": [
                {
                    "text": "Trend 확인 Action이 완료되어 원인 분석에 필요한 추세 근거를 확보했습니다.",
                    "source_ids": ["action:act-trend"],
                }
            ],
            "similar_case_narrative": {
                "text": "유사 사례 2건은 Trend와 Raw Data를 확인한 뒤 현장 담당자에게 공유한 흐름입니다.",
                "source_ids": ["case:case-1"],
                "sample_size": 2,
                "low_sample_warning": True,
            },
            "similar_case_insights": [
                {
                    "text": "이전에도 Trend와 Raw Data를 같이 확인한 뒤 담당자에게 공유했습니다.",
                    "how_it_was_handled": "Trend와 Raw Data 확인 후 현장 담당자에게 공유했습니다.",
                    "why_similar": "같은 Action과 같은 Event 근거를 사용했습니다.",
                    "difference_or_caution": "사례 수가 적어 참고용으로만 봐야 합니다.",
                    "source_ids": ["case:case-1"],
                    "sample_size": 2,
                    "low_sample_warning": True,
                }
            ],
        },
        compact,
        context_hash,
    )

    assert ready["summary_state"] == "ready"
    assert ready["overall_summary"]["text"].startswith("Trend 확인")
    assert ready["difference_summary"]["text"].startswith("이번 건")
    assert ready["recommended_action_note"]["text"].startswith("Raw Data")
    assert ready["stage_history_narrative"][0]["source_ids"] == ["action:act-trend"]
    assert ready["similar_case_narrative"]["low_sample_warning"] is True
    assert ready["similar_case_insights"][0]["why_similar"]

    with pytest.raises(ValueError):
        boi_app_module.normalize_work_context_narrative_payload(
            {"stage_history_narrative": [{"text": "실행됨", "source_ids": ["action:act-trend"]}]},
            compact,
            context_hash,
        )
    with pytest.raises(ValueError):
        boi_app_module.normalize_work_context_narrative_payload(
            {
                "stage_history_narrative": [
                    {
                        "text": "요청이 라우팅되어 담당 단계에서 처리 중입니다.",
                        "source_ids": ["action:act-trend"],
                    }
                ]
            },
            compact,
            context_hash,
        )
    cleaned = boi_app_module.normalize_work_context_narrative_payload(
        {
            "overall_summary": {
                "text": "Trend 확인 Action이 완료되어 알람 맥락 판단 근거가 준비되었습니다. action:act-trend",
                "source_ids": ["action:act-trend"],
            },
            "difference_summary": {
                "text": "이번 건은 Trend 근거 확인 후 Raw Data 대조 여부를 추가 확인해야 합니다.",
                "source_ids": ["action:act-trend"],
            },
            "recommended_action_note": {
                "text": "Raw Data 대조 결과를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
                "source_ids": ["action:act-trend"],
            },
            "stage_history_narrative": [
                {
                    "text": "Trend 확인 Action이 완료되었습니다. action:act-trend",
                    "source_ids": ["action:act-trend"],
                }
            ]
        },
        compact,
        context_hash,
    )
    assert "action:" not in cleaned["stage_history_narrative"][0]["text"]
    cleaned_source_label = boi_app_module.normalize_work_context_narrative_payload(
        {
            "overall_summary": {
                "text": "Trend 확인 Action이 완료되어 알람 맥락 판단 근거가 준비되었습니다. source_id: action:act-trend",
                "source_ids": ["action:act-trend"],
            },
            "difference_summary": {
                "text": "이번 건은 Trend 근거 확인 후 Raw Data 대조 여부를 추가 확인해야 합니다.",
                "source_ids": ["action:act-trend"],
            },
            "recommended_action_note": {
                "text": "Raw Data 대조 결과를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
                "source_ids": ["action:act-trend"],
            },
            "stage_history_narrative": [
                {
                    "text": "Trend 확인 Action이 완료되어 근거를 확보했습니다. source_id: action:act-trend",
                    "source_ids": ["action:act-trend"],
                }
            ]
        },
        compact,
        context_hash,
    )
    assert "source_id" not in cleaned_source_label["stage_history_narrative"][0]["text"]
    no_case_compact = {**compact, "similar_case_summaries": []}
    no_case_hash = boi_app_module.work_context_narrative_hash(no_case_compact)
    no_case_ready = boi_app_module.normalize_work_context_narrative_payload(
        {
            "overall_summary": {
                "text": "Trend 확인 Action이 완료되어 알람 맥락 판단 근거가 준비되었습니다.",
                "source_ids": ["action:act-trend"],
            },
            "difference_summary": {
                "text": "이번 건은 Trend 근거 확인 후 Raw Data 대조 여부를 추가 확인해야 합니다.",
                "source_ids": ["action:act-trend"],
            },
            "recommended_action_note": {
                "text": "Raw Data 대조 결과를 확인한 뒤 승인 또는 반려 사유를 남기세요.",
                "source_ids": ["action:act-trend"],
            },
            "stage_history_narrative": [
                {
                    "text": "Trend 확인 Action이 완료되어 원인 분석에 필요한 추세 근거를 확보했습니다.",
                    "source_ids": ["action:act-trend"],
                }
            ],
            "similar_case_insights": [
                {
                    "text": "없는 과거 사례를 참고했습니다.",
                    "source_ids": ["action:act-trend"],
                    "sample_size": 0,
                    "low_sample_warning": False,
                }
            ],
        },
        no_case_compact,
        no_case_hash,
    )
    assert no_case_ready["similar_case_insights"] == []
    assert no_case_ready["similar_case_narrative"] == {}
    with pytest.raises(ValueError):
        boi_app_module.normalize_work_context_narrative_payload(
            {
                "stage_history_narrative": [
                    {
                        "text": "Trend 확인 Action이 완료되어 원인 분석에 필요한 추세 근거를 확보했습니다.",
                        "source_ids": ["action:unknown"],
                    }
                ]
            },
            compact,
            context_hash,
        )


def test_agent_signals_prioritize_current_page_inbox_context(boi_app_module):
    client = TestClient(boi_app_module.app)
    request_id = "act-agent-signal-current"
    append_action_log_row(
        boi_app_module,
        {
            "request_id": request_id,
            "employee_id": "100001",
            "trace_id": "trace-agent-signal",
            "event_type": "equipment.alarm.raised.v1",
            "action_key": "manual.equipment.confirm_alarm_context",
            "status": "manual_required",
            "summary": "현재 SOP 관련 조치 필요",
            "logged_at": boi_app_module.now_iso(),
        },
    )

    response = client.get(
        "/api/agents/boi-wiki/signals?employee_id=100001"
        "&current_url=/docs/boi:public:sop:equipment-abnormal-response"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["signals"]
    signal = body["signals"][0]
    assert signal["type"] in {"new_inbox", "high_priority_task", "current_page_context"}
    assert signal["target_tab"] == "inbox"
    assert signal["task_id"] == f"task:{request_id}"
    assert "trace" not in signal["message"].lower()
    assert "request_id" not in signal["message"]


def test_work_pattern_derivation_uses_agent_activity_without_publishing(boi_app_module):
    client = TestClient(boi_app_module.app)
    for index in range(3):
        posted = client.post(
            "/api/agents/boi-wiki/activity?employee_id=100001",
            json={
                "activity_type": "artifact_open",
                "target": "/docs/boi:public:sop:equipment-abnormal-response",
                "title": "Mermaid 크게 보기",
                "metadata": {"artifact_type": "mermaid", "question": "이 SOP를 Mermaid로 보여줘", "index": index},
            },
        )
        assert posted.status_code == 200

    response = client.post("/api/agents/boi-wiki/patterns/derive?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["candidates"]
    candidate = body["candidates"][0]
    assert candidate["pattern_kind"] in {"answer_preference", "workflow_habit", "recurring_task", "manual_to_ai_candidate", "skill_candidate", "workflow_definition_gap"}
    assert candidate["usage_count"] >= 3
    assert candidate["visibility"] == "private"
    assert body["published"] is False
