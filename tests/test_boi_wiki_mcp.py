from __future__ import annotations

import argparse
import asyncio
import builtins
import importlib
import importlib.util
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from jsonschema import validate
import pytest


@pytest.fixture()
def mcp_module(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("DEFAULT_EMPLOYEE_ID", "100001")
    sys.modules.pop("boi_wiki_mcp.app.main", None)
    return importlib.import_module("boi_wiki_mcp.app.main")


def test_boi_wiki_mcp_health(mcp_module):
    client = TestClient(mcp_module.app)

    response = client.get("/health", headers={"host": "boi-wiki-mcp.example:28200"})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "boi-wiki-mcp"
    assert body["mcp_endpoint"] == "http://boi-wiki-mcp.example:28200/mcp"
    assert body["bridge_endpoint"] == "http://boi-wiki-mcp.example:28200/api/mcp/call"
    assert body["health_endpoint"] == "http://boi-wiki-mcp.example:28200/health"
    assert body["capabilities"]["tools"] == 108
    assert body["capabilities"]["resource_templates"] == 11
    assert body["capability_lists"]["tools"][0]["name"] == "boi_search"
    group_names = [group["name"] for group in body["tool_groups"]]
    assert group_names[:6] == ["BoI Wiki", "BoI Inbox", "SOP", "Event Broker", "Action", "Advanced"]
    boi_inbox_group = next(group for group in body["tool_groups"] if group["name"] == "BoI Inbox")
    boi_inbox_tools = {tool["name"] for tool in boi_inbox_group["tools"]}
    assert {
        "boi_inbox",
        "boi_inbox_report_get",
        "boi_inbox_decision_preview",
        "boi_inbox_decision_submit",
        "boi_ops_overview",
        "boi_ops_recent_events",
        "agent_draft_create",
        "agent_draft_test",
        "agent_draft_publish",
        "agent_catalog_search",
        "agent_link_to_me",
        "agent_unlink_from_me",
        "agent_conversation_create",
        "agent_conversation_message",
        "agent_sandbox_job_create",
        "agent_sandbox_job_get",
        "agent_sandbox_job_events",
        "agent_sandbox_adopt_evidence",
        "reporting_analysis_plan",
        "reporting_analysis_job_create",
        "reporting_report_draft_create",
        "reporting_report_publish",
    } <= boi_inbox_tools
    boi_wiki_group = next(group for group in body["tool_groups"] if group["name"] == "BoI Wiki")
    boi_wiki_tools = {tool["name"] for tool in boi_wiki_group["tools"]}
    assert {
        "private_memory_cleanup_preview",
        "private_memory_cleanup_run",
        "private_memory_restore",
        "private_memory_mark_memory",
    } <= boi_wiki_tools
    sop_group = next(group for group in body["tool_groups"] if group["name"] == "SOP")
    sop_tools = {tool["name"] for tool in sop_group["tools"]}
    assert {"sop_catalog_search", "sop_run_get", "sop_run_graph", "sop_run_context"} <= sop_tools
    data_lake_group = next(group for group in body["tool_groups"] if group["name"] == "Optional Data Lake")
    data_lake_tools = {tool["name"] for tool in data_lake_group["tools"]}
    assert {
        "data_lake_status",
        "data_lake_sources",
        "data_lake_query_plan",
        "data_lake_query_preview",
        "data_lake_query_execute",
        "data_lake_artifact_get",
        "data_lake_import_sources",
    } <= data_lake_tools
    assert "Deprecated / Compatibility" in group_names
    deprecated = next(group for group in body["tool_groups"] if group["name"] == "Deprecated / Compatibility")
    assert [tool["name"] for tool in deprecated["tools"]] == [
        "agent_inbox",
        "agent_inbox_context",
        "agent_inbox_decision_preview",
        "agent_inbox_decision_submit",
        "agent_inbox_review_report",
        "capabilities_search",
        "capability_deduplicate",
        "capability_get",
    ]
    assert body["agent_interfaces"]["json_api"] == "/api/agents/boi-wiki/chat"
    assert body["agent_interfaces"]["streaming_api"] == "/api/agents/boi-wiki/chat/stream"
    assert body["agent_interfaces"]["mcp_tool"] == "boi_agent_chat"
    assert body["agent_interfaces"]["response_contract_version"] == "boi-agent.response.v1"
    assert body["agent_interfaces"]["streaming_events"] == ["accepted", "status", "answer_delta", "answer_ready", "followups", "final", "error"]
    assert body["agent_response_contract"]["version"] == "boi-agent.response.v1"
    assert body["agent_response_contract"]["canonical_endpoint"] == "/api/agents/boi-wiki/chat"
    assert body["agent_response_contract"]["stream_endpoint"] == "/api/agents/boi-wiki/chat/stream"
    assert body["agent_response_contract"]["schema_endpoint"] == "/api/agents/boi-wiki/response-schema"
    assert body["agent_response_contract"]["mcp_tool"] == "boi_agent_chat"
    assert body["agent_response_contract"]["mcp_resource_template"] == "boi://agent/response-schema/{version}"
    assert body["agent_response_schema"]["properties"]["agent_contract_version"]["const"] == "boi-agent.response.v1"
    assert body["agent_response_schema"]["properties"]["artifacts"]["items"]["properties"]["type"]["enum"]
    assert body["mcp_auth"]["required"] is False
    assert body["mcp_auth"]["bridge_always_requires_service_token"] is True
    assert "x-service-token" in body["mcp_auth"]["accepted_headers"]
    assert "web_pet" in body["agent_response_contract"]["consumers"]
    assert "boi_wiki_mcp" in body["agent_response_contract"]["consumers"]
    assert "external_api" in body["agent_response_contract"]["consumers"]
    assert "answer_markdown" in body["agent_response_contract"]["required_fields"]
    assert "artifacts" in body["agent_response_contract"]["required_fields"]
    assert "status_updates" in body["agent_response_contract"]["required_fields"]
    assert "status_events" not in body["agent_response_contract"]["required_fields"]
    assert body["agent_response_contract"]["status_fields"] == {
        "canonical": "status_updates",
        "alias": "status_events",
        "stream_event": "status",
    }
    assert "tool_trace" in body["agent_response_contract"]["required_fields"]
    assert "access_summary" in body["agent_response_contract"]["required_fields"]
    assert "guardrails_applied" in body["agent_response_contract"]["required_fields"]
    assert "required_role" in body["agent_response_contract"]["execution_card_required_fields"]
    assert "permission" in body["agent_response_contract"]["execution_card_required_fields"]
    execution_card_item = body["agent_response_schema"]["properties"]["execution_cards"]["items"]
    card_schema = execution_card_item["properties"]
    assert card_schema["required_role"]["type"] == "string"
    assert card_schema["permission"]["type"] == "object"
    assert "required_role" in execution_card_item["required"]
    assert "permission" in execution_card_item["required"]
    assert "mermaid" in body["agent_response_contract"]["artifact_types"]
    assert "gap_table" in body["agent_response_contract"]["artifact_types"]
    assert "action_requirements" in body["agent_response_contract"]["artifact_types"]
    tool_names = [item["name"] for item in body["capability_lists"]["tools"]]
    assert "source_preview" in tool_names
    assert "source_apply" in tool_names
    assert "doc_body_preview" in tool_names
    assert "doc_body_apply" in tool_names
    assert "boi_agent_chat" in tool_names
    assert "boi_agent_capabilities" in tool_names
    assert "boi_agent_approve" in tool_names
    assert "ontology_search" in tool_names
    assert "boi_inbox" in tool_names
    assert "boi_inbox_report_get" in tool_names
    assert "boi_inbox_decision_preview" in tool_names
    assert "boi_inbox_decision_submit" in tool_names
    assert "boi_ops_overview" in tool_names
    assert "agent_draft_create" in tool_names
    assert "agent_draft_test" in tool_names
    assert "agent_draft_publish" in tool_names
    assert "agent_catalog_search" in tool_names
    assert "agent_link_to_me" in tool_names
    assert "agent_unlink_from_me" in tool_names
    assert "agent_conversation_create" in tool_names
    assert "agent_conversation_message" in tool_names
    assert "agent_sandbox_job_create" in tool_names
    assert "agent_sandbox_job_get" in tool_names
    assert "agent_sandbox_job_events" in tool_names
    assert "agent_sandbox_adopt_evidence" in tool_names
    assert "boi_ops_recent_events" in tool_names
    assert "sop_catalog_search" in tool_names
    assert "sop_run_get" in tool_names
    assert "sop_run_graph" in tool_names
    assert "sop_run_context" in tool_names
    assert "data_lake_status" in tool_names
    assert "data_lake_query_preview" in tool_names
    assert "agent_inbox" in tool_names
    assert "private_memory_cleanup_preview" in tool_names
    assert "private_memory_cleanup_run" in tool_names
    assert "private_memory_restore" in tool_names
    assert "private_memory_mark_memory" in tool_names
    assert "work_context_get" in tool_names
    assert "agent_inbox_context" in tool_names
    assert "similar_cases_search" in tool_names
    assert "agent_signals" in tool_names
    assert "work_patterns_search" in tool_names
    assert "work_pattern_derive" in tool_names
    assert "skill_candidate_create" in tool_names
    assert "manual_handoff_complete" in tool_names
    assert "rbac_me" in tool_names
    assert "rbac_check" in tool_names
    assert "doc_access_check" in tool_names
    assert "rbac_audit" in tool_names
    assert "registration_draft_create" in tool_names
    assert "registration_plan" in tool_names
    assert "registration_verification_preview" in tool_names
    assert "registration_drafts" in tool_names
    assert "registration_draft_validate" in tool_names
    assert "registration_draft_publish" in tool_names
    assert "sop_registration_plan" in tool_names
    assert "sop_registration_preview" in tool_names
    assert "sop_registration_draft_create" in tool_names
    assert "sop_registration_validate" in tool_names
    assert "sop_registration_publish" in tool_names
    assert "sop_draft_create" in tool_names
    assert "action_draft_create" in tool_names
    assert "event_type_draft_create" in tool_names
    assert "event_publish_plan" in tool_names
    assert "event_publish_preview" in tool_names
    assert "event_pattern_preview" in tool_names
    assert "event_pattern_promote_to_draft" in tool_names
    assert "sop_run_history" in tool_names
    assert "event_type_drafts" in tool_names
    assert "event_type_draft_validate" in tool_names
    assert "event_type_draft_apply" in tool_names
    assert "workflow_definitions_search" in tool_names
    assert "workflow_definition_get" in tool_names
    assert "workflow_definition_deduplicate" in tool_names
    assert "workflow_definition_publish" in tool_names
    assert "capabilities_search" in tool_names
    assert "capability_get" in tool_names
    assert "capability_deduplicate" in tool_names
    assert "event_skills_list" in tool_names
    assert "action_skills_list" in tool_names
    assert "source_create_draft" not in tool_names
    assert "doc_body_create_draft" not in tool_names
    assert any(item["name"] == "promotion_submit" for item in body["capability_lists"]["tools"])
    assert any(item["uri"] == "boi://docs/{boi_id}" for item in body["capability_lists"]["resource_templates"])
    assert any(item["uri"] == "boi://employees/{employee_id}/docs/{boi_id}" for item in body["capability_lists"]["resource_templates"])
    assert any(item["uri"] == "boi://employees/{employee_id}/search/ontology/{query}" for item in body["capability_lists"]["resource_templates"])
    assert any(item["uri"] == "boi://agent/response-schema/{version}" for item in body["capability_lists"]["resource_templates"])
    assert any(item["name"] == "create_sop_from_source" for item in body["capability_lists"]["prompts"])


def test_boi_wiki_mcp_status_page_explains_human_browser_usage(mcp_module):
    client = TestClient(mcp_module.app)

    response = client.get("/", headers={"host": "boi-wiki-mcp.example:28200"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "BoI Wiki MCP" in body
    assert "http://boi-wiki-mcp.example:28200/mcp" in body
    assert "http://localhost:8200/mcp" not in body
    assert "Streamable HTTP" in body
    assert "Tools" in body and "86" in body
    assert "Tools by BoI Wiki IA" in body
    assert "BoI Inbox" in body
    assert "Optional Data Lake" in body
    assert "Event Broker" in body
    assert "Deprecated / Compatibility" in body
    assert "Resource templates" in body and "11" in body
    assert "Prompts" in body and "5" in body
    assert "boi_search" in body
    assert "workflow_status" in body
    assert "action_invoke" in body
    assert "source_apply" in body
    assert "doc_body_apply" in body
    assert "promotion_submit" in body
    assert "boi_agent_chat" in body
    assert "boi_agent_capabilities" in body
    assert "boi_agent_approve" in body
    assert "boi-agent.response.v1" in body
    assert "MCP auth" in body
    assert "not required" in body
    assert "/api/agents/boi-wiki/chat/stream" in body
    assert "answer_delta" in body
    assert "ontology_search" in body
    assert "agent_inbox" in body
    assert "boi_ops_overview" in body
    assert "sop_run_graph" in body
    assert "rbac_me" in body
    assert "rbac_check" in body
    assert "doc_access_check" in body
    assert "rbac_audit" in body
    assert "registration_draft_create" in body
    assert "registration_draft_publish" in body
    assert "sop_registration_plan" in body
    assert "sop_registration_draft_create" in body
    assert "sop_draft_create" in body
    assert "action_draft_create" in body
    assert "event_type_draft_create" in body
    assert "event_type_draft_apply" in body
    assert "workflow_definitions_search" in body
    assert "workflow_definition_deduplicate" in body
    assert "event_skills_list" in body
    assert "action_skills_list" in body
    assert "boi://docs/{boi_id}" in body
    assert "boi://search/ontology/{query}" in body
    assert "boi://agent/response-schema/{version}" in body
    assert "create_sop_from_source" in body
    assert "406" in body
    assert "Codex" in body
    assert "Claude Desktop" in body
    assert "Cursor" in body


def test_boi_wiki_mcp_status_alias_works(mcp_module):
    client = TestClient(mcp_module.app)

    response = client.get("/status")

    assert response.status_code == 200
    assert "BoI Wiki MCP" in response.text


def test_boi_agent_response_schema_resource(mcp_module, monkeypatch):
    async def fake_api_get(path, **kwargs):
        return {
            "ok": True,
            "agent_contract_version": "boi-agent.response.v1",
            "schema": mcp_module.AGENT_RESPONSE_SCHEMA,
        }

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)

    body = json.loads(asyncio.run(mcp_module.boi_agent_response_schema_resource("latest")))

    assert body["ok"] is True
    assert body["agent_contract_version"] == "boi-agent.response.v1"
    assert body["schema"]["required"] == mcp_module.AGENT_RESPONSE_REQUIRED_FIELDS
    assert body["schema"]["properties"]["agent_contract_version"]["const"] == "boi-agent.response.v1"
    assert "mermaid" in body["schema"]["properties"]["artifacts"]["items"]["properties"]["type"]["enum"]


def test_mcp_employee_scoped_resources_use_uri_employee_id(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_boi_get(boi_id, employee_id):
        calls.append({"tool": "boi_get", "boi_id": boi_id, "employee_id": employee_id})
        return {"ok": True, "employee_id": employee_id, "boi_id": boi_id}

    async def fake_boi_search(*args, **kwargs):
        calls.append({"tool": "boi_search", **kwargs})
        return {"ok": True, "employee_id": kwargs.get("employee_id"), "folder": kwargs.get("folder")}

    async def fake_action_get(action_key, employee_id):
        calls.append({"tool": "action_get", "action_key": action_key, "employee_id": employee_id})
        return {"ok": True, "employee_id": employee_id, "action_key": action_key}

    async def fake_workflow_status(workflow_key, trace_id, employee_id):
        calls.append({"tool": "workflow_status", "workflow_key": workflow_key, "trace_id": trace_id, "employee_id": employee_id})
        return {"ok": True, "employee_id": employee_id, "workflow_key": workflow_key, "trace_id": trace_id}

    async def fake_ontology_search(*args, **kwargs):
        calls.append({"tool": "ontology_search", **kwargs})
        return {"ok": True, "employee_id": kwargs.get("employee_id"), "query": kwargs.get("query")}

    monkeypatch.setattr(mcp_module, "boi_get", fake_boi_get)
    monkeypatch.setattr(mcp_module, "boi_search", fake_boi_search)
    monkeypatch.setattr(mcp_module, "action_get", fake_action_get)
    monkeypatch.setattr(mcp_module, "workflow_status", fake_workflow_status)
    monkeypatch.setattr(mcp_module, "ontology_search", fake_ontology_search)

    assert json.loads(asyncio.run(mcp_module.boi_doc_for_employee_resource("100003", "boi:private:100003:test")))["employee_id"] == "100003"
    assert json.loads(asyncio.run(mcp_module.boi_folder_for_employee_resource("100003", "private/100003")))["employee_id"] == "100003"
    assert json.loads(asyncio.run(mcp_module.action_for_employee_resource("100003", "action.test")))["employee_id"] == "100003"
    assert json.loads(asyncio.run(mcp_module.workflow_status_for_employee_resource("100003", "equipment-anomaly", "trace-1")))["employee_id"] == "100003"
    assert json.loads(asyncio.run(mcp_module.ontology_search_for_employee_resource("100003", "SOP")))["employee_id"] == "100003"

    assert {call["employee_id"] for call in calls} == {"100003"}


def test_unscoped_mcp_resources_do_not_use_default_employee_for_private_context(mcp_module, monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("employee-scoped data must not be loaded by unscoped resource")

    monkeypatch.setattr(mcp_module, "boi_get", fail_if_called)
    monkeypatch.setattr(mcp_module, "workflow_status", fail_if_called)
    monkeypatch.setattr(mcp_module, "ontology_search", fail_if_called)

    private_doc = json.loads(asyncio.run(mcp_module.boi_doc_resource("boi:private:100001:secret")))
    workflow = json.loads(asyncio.run(mcp_module.workflow_status_resource("equipment-anomaly", "trace-private")))
    ontology = json.loads(asyncio.run(mcp_module.ontology_search_resource("private trace")))

    assert private_doc["ok"] is False
    assert workflow["ok"] is False
    assert ontology["ok"] is False
    assert private_doc["error"] == "employee_scoped_resource_required"
    assert workflow["employee_scoped_uri"].startswith("boi://employees/{employee_id}/")


def test_mcp_static_agent_response_schema_matches_boi_api_contract(mcp_module, boi_app_module):
    assert mcp_module.AGENT_RESPONSE_REQUIRED_FIELDS == boi_app_module.BOI_AGENT_RESPONSE_REQUIRED_FIELDS
    assert mcp_module.AGENT_ARTIFACT_TYPES == boi_app_module.BOI_AGENT_ARTIFACT_TYPES
    assert mcp_module.AGENT_RESPONSE_SCHEMA == boi_app_module.BOI_AGENT_RESPONSE_SCHEMA


def test_boi_agent_response_schema_resource_uses_boi_api_as_canonical_schema(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_get(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {
            "ok": True,
            "agent_contract_version": "boi-agent.response.v1",
            "schema": {
                "required": ["agent_contract_version", "answer_markdown"],
                "properties": {
                    "agent_contract_version": {"const": "boi-agent.response.v1"},
                    "sentinel": {"const": "api-canonical-schema"},
                },
            },
        }

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)

    body = json.loads(asyncio.run(mcp_module.boi_agent_response_schema_resource("latest")))

    assert calls[0]["path"] == "/api/agents/boi-wiki/response-schema"
    assert calls[0]["service_token"] is True
    assert body["schema"]["properties"]["sentinel"]["const"] == "api-canonical-schema"


def test_boi_wiki_mcp_status_uses_forwarded_headers(mcp_module):
    client = TestClient(mcp_module.app)

    response = client.get(
        "/health",
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "wiki.example.com",
            "x-forwarded-port": "443",
        },
    )

    assert response.status_code == 200
    assert response.json()["mcp_endpoint"] == "https://wiki.example.com:443/mcp"


def test_boi_wiki_mcp_bridge_invokes_search_tool(mcp_module, monkeypatch):
    async def fake_boi_search_impl(*args, **kwargs):
        return {
            "count": 1,
            "items": [
                {
                    "metadata": {
                        "boi_id": "boi:public:sop:equipment-abnormal-response",
                        "title": "설비 이상 SOP",
                    }
                }
            ],
            "kwargs": kwargs,
        }

    monkeypatch.setattr(mcp_module, "boi_search_impl", fake_boi_search_impl)
    client = TestClient(mcp_module.app)

    response = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi.search",
            "arguments": {"query": "설비", "employee_id": "100001"},
            "request_id": "act-mcp-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "mcp_invoked"
    assert body["tool"] == "boi.search"
    assert body["request_id"] == "act-mcp-test"
    assert body["response"]["count"] == 1
    assert body["result"]["count"] == 1
    assert body["response"]["kwargs"]["query"] == "설비"
    assert body["response"]["kwargs"]["service_token"] is True


def test_boi_wiki_mcp_bridge_requires_service_token(mcp_module):
    client = TestClient(mcp_module.app)

    response = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "wrong"},
        json={"tool": "boi.search", "arguments": {"query": "Kafka"}},
    )

    assert response.status_code == 401


def test_boi_wiki_mcp_bridge_invokes_ontology_tool(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_get(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "groups": {"sop": []}}

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    response = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "ontology.search",
            "arguments": {"query": "설비", "employee_id": "100001"},
            "request_id": "act-ontology-test",
        },
    )

    assert response.status_code == 200
    assert response.json()["response"]["ok"] is True
    assert response.json()["result"]["ok"] is True
    assert calls[0]["path"] == "/api/search/ontology"
    assert calls[0]["service_token"] is True


def test_boi_wiki_mcp_bridge_invokes_agent_chat_and_inbox_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {
            "ok": True,
            "agent_contract_version": "boi-agent.response.v1",
            "answer_markdown": "agent answer",
            "display_markdown": "agent answer",
            "links": [{"label": "SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
            "citations": [{"label": "SOP", "ref": "boi:public:sop:equipment-abnormal-response"}],
            "artifacts": [{"type": "mermaid", "title": "SOP flow", "source": "flowchart TD\nA[Start] --> B[Action]"}],
            "status_updates": [{"stage": "retrieval", "message": "관련 BoI 지식을 확인했습니다.", "source": "llm_status"}],
            "status_events": [{"stage": "retrieval", "message": "관련 BoI 지식을 확인했습니다.", "source": "llm_status"}],
            "tool_trace": [{"tool": "ontology_search", "status": "ok", "elapsed_ms": 5, "summary": "best_matches=1"}],
            "evidence_ledger": [
                {
                    "kind": "current_page",
                    "label": "SOP",
                    "url": "/sops",
                    "source": "page_context",
                    "confidence": 1.0,
                    "acl_decision": {"can_read": True, "can_cite": True},
                    "used_for": ["answer", "followup"],
                }
            ],
            "affordances": [{"type": "ask_more", "label": "근거 자세히 보기", "question_hint": "근거를 더 설명해줘."}],
            "answer_quality": {"followups_generated": True, "evidence_count": 1, "affordance_count": 1},
            "goal_model": {
                "goal_type": "wiki_search",
                "intent": "search",
                "response_profile": "search",
                "route": "fast",
                "source": "agent_goal_registry",
            },
            "response_profile": "search",
            "component_errors": [],
            "execution_cards": [
                {
                    "contract_version": "boi-agent.response.v1",
                    "operation": "event_publish",
                    "payload": {"event_type": "meeting.closed.v1"},
                    "requires_confirmation": True,
                    "user_confirmed_required": True,
                    "approve_url": "/api/agents/boi-wiki/approve",
                    "required_role": "boi.workflow_runner",
                    "permission": {"allowed": True, "reason": "role_present", "role": "boi.workflow_runner"},
                    "display": {"title": "이벤트 발행 확인", "next_action": "요청 실행"},
                    "technical_details": {"operation": "event_publish", "required_role": "boi.workflow_runner"},
                }
            ],
            "access_summary": {"can_read": True, "can_use_in_agent_context": True},
            "guardrails_applied": ["acl_policy", "mutation_confirmation"],
            "redacted_count": 0,
        }

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "items": [{"task_id": "task-1"}]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    chat = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi_agent_chat",
            "arguments": {
                "question": "SOP 찾아줘",
                "employee_id": "100001",
                "mode": "fast",
                "intent": "search",
                "current_url": "/sops",
                "selected_text": "SOP",
                "conversation": [{"role": "user", "content": "이전 질문"}],
                "save_memory": False,
            },
        },
    )
    inbox = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi_inbox",
            "arguments": {"employee_id": "100001", "limit": 3},
        },
    )

    assert chat.status_code == 200
    agent_result = chat.json()["result"]
    validate(instance=agent_result, schema=mcp_module.AGENT_RESPONSE_SCHEMA)
    assert agent_result["agent_contract_version"] == "boi-agent.response.v1"
    assert agent_result["answer_markdown"] == "agent answer"
    assert agent_result["links"][0]["label"] == "SOP"
    assert agent_result["artifacts"][0]["type"] == "mermaid"
    assert agent_result["status_updates"][0]["source"] == "llm_status"
    assert agent_result["status_events"] == agent_result["status_updates"]
    assert agent_result["tool_trace"][0]["tool"] == "ontology_search"
    assert agent_result["execution_cards"][0]["requires_confirmation"] is True
    assert agent_result["access_summary"]["can_read"] is True
    assert "mutation_confirmation" in agent_result["guardrails_applied"]
    assert inbox.status_code == 200
    assert inbox.json()["result"]["items"][0]["task_id"] == "task-1"
    assert calls[0]["path"] == "/api/agents/boi-wiki/chat"
    assert calls[0]["payload"]["mode"] == "fast"
    assert calls[1]["path"] == "/api/inbox"
    assert calls[0]["payload"]["intent"] == "search"
    assert calls[0]["payload"]["selected_text"] == "SOP"
    assert calls[0]["payload"]["conversation"] == [{"role": "user", "content": "이전 질문"}]
    assert calls[0]["payload"]["save_memory"] is False
    assert calls[1]["params"]["include_context"] == "compact"


def test_boi_wiki_mcp_bridge_invokes_ops_and_sop_scope_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        if path == "/api/ops/overview":
            return {"ok": True, "workstream_nodes": [{"id": "employee:100001"}], "priority_queue": []}
        if path == "/api/ops/recent-events":
            return {"ok": True, "items": [{"type": "boi.ops.task.created"}]}
        if path == "/api/sops":
            return {"ok": True, "scope": kwargs["params"]["scope"], "items": [{"title": "설비 이상 SOP"}]}
        if path == "/api/sop-runs/run-1":
            return {"ok": True, "run": {"run_id": "run-1"}}
        if path == "/api/sop-runs/run-1/graph":
            return {"ok": True, "run_id": "run-1", "nodes": [{"id": "detect"}]}
        if path == "/api/sop-runs/run-1/context":
            return {"ok": True, "decision_packet": {"why_assigned": "확인 필요"}}
        raise AssertionError(f"unexpected GET {path}")

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    for tool, arguments in [
        ("boi_ops_overview", {"employee_id": "100001"}),
        ("boi_ops_recent_events", {"employee_id": "100001", "limit": 5}),
        ("sop_catalog_search", {"employee_id": "100001", "scope": "catalog_search", "query": "설비 이상", "limit": 7}),
        ("sop_run_get", {"employee_id": "100001", "run_id": "run-1"}),
        ("sop_run_graph", {"employee_id": "100001", "run_id": "run-1"}),
        ("sop_run_context", {"employee_id": "100001", "run_id": "run-1"}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["result"]["ok"] is True

    assert [call["path"] for call in calls] == [
        "/api/ops/overview",
        "/api/ops/recent-events",
        "/api/sops",
        "/api/sop-runs/run-1",
        "/api/sop-runs/run-1/graph",
        "/api/sop-runs/run-1/context",
    ]
    assert calls[2]["params"] == {"scope": "catalog_search", "q": "설비 이상", "limit": 7}
    assert all(call["employee_id"] == "100001" for call in calls)
    assert all(call["service_token"] is True for call in calls)


def test_boi_wiki_mcp_bridge_invokes_agent_builder_and_sandbox_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        if path == "/api/agents/drafts":
            payload = kwargs["payload"]
            return {"ok": True, "draft": {"draft_id": "agent-draft-1", "files": payload["files"], "runtime": {"model": "gpt-5.5"}}}
        if path == "/api/agents/drafts/agent-draft-1/test":
            return {"ok": True, "draft_id": "agent-draft-1", "test": {"runtime_backend": "agents_sdk", "model": "gpt-5.5"}}
        if path == "/api/agents/drafts/agent-draft-1/publish":
            return {"ok": True, "draft": {"draft_id": "agent-draft-1", "status": "published", "scope": kwargs["payload"]["scope"]}}
        if path == "/api/agents/agent-1/link-to-me":
            return {"ok": True, "agent": {"agent_id": "agent-1", "is_linked_to_me": True}}
        if path == "/api/agents/agent-1/unlink-from-me":
            return {"ok": True, "agent_id": "agent-1", "linked": False}
        if path == "/api/agents/agent-1/conversations":
            return {"ok": True, "conversation": {"conversation_id": "agent-conv-1", "agent_id": "agent-1"}}
        if path == "/api/agents/agent-1/conversations/agent-conv-1/messages":
            return {"ok": True, "message": {"role": "assistant", "content": "확인했습니다."}}
        if path == "/api/agents/sandbox/jobs":
            return {"ok": True, "job": {"job_id": "sandbox-job-1", "status": "completed", "artifacts": [{"path": "result.csv"}]}}
        if path == "/api/agents/sandbox/jobs/sandbox-job-1/adopt-evidence":
            return {"ok": True, "job": {"job_id": "sandbox-job-1", "evidence_state": kwargs["payload"]["evidence_state"]}}
        raise AssertionError(f"unexpected POST {path}")

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        if path == "/api/agents/sandbox/jobs/sandbox-job-1":
            return {"ok": True, "job": {"job_id": "sandbox-job-1", "status": "completed"}}
        if path == "/api/agents/sandbox/jobs/sandbox-job-1/events":
            return {"ok": True, "job_id": "sandbox-job-1", "items": [{"type": "boi.sandbox.job.executed"}]}
        if path == "/api/agents":
            return {"ok": True, "items": [{"agent_id": "agent-1"}]}
        raise AssertionError(f"unexpected GET {path}")

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    create = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "agent_draft_create",
            "arguments": {
                "employee_id": "100001",
                "title": "MCP Evidence Agent",
                "prompt": "Raw Data를 검증해줘.",
                "files": [{"name": "raw.csv", "note": "sample"}],
                "urls": ["https://example.com/spec"],
                "git_repos": ["https://github.com/example/repo"],
                "mcp_servers": ["boi-wiki-local"],
                "skills": ["data-analytics:validate-data"],
                "scope": "private",
            },
        },
    )
    assert create.status_code == 200
    assert create.json()["result"]["draft"]["runtime"]["model"] == "gpt-5.5"

    for tool, arguments in [
        ("agent_draft_test", {"employee_id": "100001", "draft_id": "agent-draft-1"}),
        (
            "agent_sandbox_job_create",
            {
                "employee_id": "100001",
                "title": "MCP Sandbox",
                "task": "CSV를 검증해줘.",
                "code": "print('ok')",
                "language": "python",
                "evidence_intent": "mcp_validation",
                "user_confirmed": True,
            },
        ),
        ("agent_sandbox_job_get", {"employee_id": "100001", "job_id": "sandbox-job-1"}),
        ("agent_sandbox_job_events", {"employee_id": "100001", "job_id": "sandbox-job-1"}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["result"]["ok"] is True

    publish_without_confirmation = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "agent_draft_publish", "arguments": {"employee_id": "100001", "draft_id": "agent-draft-1"}},
    )
    assert publish_without_confirmation.status_code == 400
    assert "user_confirmed=true" in publish_without_confirmation.json()["detail"]

    publish = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "agent_draft_publish",
            "arguments": {"employee_id": "100001", "draft_id": "agent-draft-1", "scope": "team", "note": "reviewed", "user_confirmed": True},
        },
    )
    assert publish.status_code == 200
    assert publish.json()["result"]["draft"]["status"] == "published"

    for tool, arguments in [
        ("agent_catalog_search", {"employee_id": "100001", "scope": "mine", "q": "evidence", "limit": 5}),
        ("agent_link_to_me", {"employee_id": "100001", "agent_id": "agent-1"}),
        ("agent_conversation_create", {"employee_id": "100001", "agent_id": "agent-1", "title": "검증 대화"}),
        ("agent_conversation_message", {"employee_id": "100001", "agent_id": "agent-1", "conversation_id": "agent-conv-1", "message": "확인해줘"}),
        ("agent_unlink_from_me", {"employee_id": "100001", "agent_id": "agent-1"}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    adopt_without_confirmation = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "agent_sandbox_adopt_evidence", "arguments": {"employee_id": "100001", "job_id": "sandbox-job-1"}},
    )
    assert adopt_without_confirmation.status_code == 400
    assert "user_confirmed=true" in adopt_without_confirmation.json()["detail"]

    adopt = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "agent_sandbox_adopt_evidence",
            "arguments": {
                "employee_id": "100001",
                "job_id": "sandbox-job-1",
                "evidence_state": "verified_evidence",
                "validation_note": "checked",
                "user_confirmed": True,
            },
        },
    )
    assert adopt.status_code == 200
    assert adopt.json()["result"]["job"]["evidence_state"] == "verified_evidence"

    create_call = calls[0]
    assert create_call["path"] == "/api/agents/drafts"
    assert create_call["payload"]["files"] == [{"name": "raw.csv", "note": "sample"}]
    assert create_call["payload"]["mcp_servers"] == ["boi-wiki-local"]
    assert create_call["payload"]["skills"] == ["data-analytics:validate-data"]
    assert [call["path"] for call in calls] == [
        "/api/agents/drafts",
        "/api/agents/drafts/agent-draft-1/test",
        "/api/agents/sandbox/jobs",
        "/api/agents/sandbox/jobs/sandbox-job-1",
        "/api/agents/sandbox/jobs/sandbox-job-1/events",
        "/api/agents/drafts/agent-draft-1/publish",
        "/api/agents",
        "/api/agents/agent-1/link-to-me",
        "/api/agents/agent-1/conversations",
        "/api/agents/agent-1/conversations/agent-conv-1/messages",
        "/api/agents/agent-1/unlink-from-me",
        "/api/agents/sandbox/jobs/sandbox-job-1/adopt-evidence",
    ]
    assert all(call["employee_id"] == "100001" for call in calls)
    assert all(call["service_token"] is True for call in calls)


def test_boi_wiki_mcp_exposes_workflow_definition_and_skill_tools(mcp_module, monkeypatch):
    async def fake_api_get(path, **kwargs):
        if path == "/api/workflow-definitions":
            return {"ok": True, "items": [{"workflow_definition_key": "equipment-anomaly-response"}]}
        if path == "/api/workflow-definitions/equipment-anomaly-response":
            return {"ok": True, "item": {"workflow_definition_key": "equipment-anomaly-response", "workflow_engine": "event_native"}}
        if path == "/api/event-skills":
            return {"ok": True, "items": [{"skill_key": "event.workflow_trigger"}]}
        if path == "/api/action-skills":
            return {"ok": True, "items": [{"skill_key": "event.publish"}]}
        raise AssertionError(f"unexpected GET {path}")

    async def fake_api_post(path, **kwargs):
        assert path == "/api/workflow-definitions/deduplicate"
        return {"ok": True, "recommendation": "reuse", "candidates": [{"workflow_definition_key": "equipment-anomaly-response"}]}

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    client = TestClient(mcp_module.app)

    status = client.get("/health")
    tool_names = [item["name"] for item in status.json()["capability_lists"]["tools"]]
    for name in [
        "workflow_definitions_search",
        "workflow_definition_get",
        "workflow_definition_deduplicate",
        "event_skills_list",
        "action_skills_list",
    ]:
        assert name in tool_names

    search = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "workflow_definitions_search", "arguments": {"employee_id": "100001"}},
    )
    dedupe = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "workflow_definition_deduplicate",
            "arguments": {"employee_id": "100001", "event_type": "equipment.alarm.raised.v1"},
        },
    )

    assert search.status_code == 200
    assert search.json()["result"]["items"][0]["workflow_definition_key"] == "equipment-anomaly-response"
    assert dedupe.status_code == 200
    assert dedupe.json()["result"]["recommendation"] == "reuse"


def test_boi_wiki_mcp_bridge_covers_agent_dictionary_memory_and_manual_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "path": path}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    requests = [
        ("boi_agent_capabilities", {"employee_id": "100001"}),
        (
            "boi_agent_suggestions",
            {
                "employee_id": "100001",
                "current_url": "/sops",
                "page_context": {"title": "SOP"},
                "answer_context": {"intent": "diagram", "affordances": [{"type": "check_gap"}]},
            },
        ),
        ("dictionary_terms", {"employee_id": "100001", "query": "단면검사", "scope": "all", "limit": 5}),
        ("agent_memory_search", {"employee_id": "100001", "query": "선호", "include_archived": False, "limit": 3}),
        ("private_memory_cleanup_preview", {"employee_id": "100001", "scope": "generated"}),
        ("private_memory_cleanup_run", {"employee_id": "100001", "cleanup_id": "pytest", "selected_boi_ids": ["boi:private:100001:test"], "user_confirmed": True}),
        ("private_memory_restore", {"employee_id": "100001", "cleanup_id": "pytest", "boi_ids": ["boi:private:100001:test"], "user_confirmed": True}),
        ("private_memory_mark_memory", {"employee_id": "100001", "boi_id": "boi:private:100001:test", "user_confirmed": True}),
        ("work_context_get", {"employee_id": "100001", "task_id": "task:act-1"}),
        ("agent_inbox_context", {"employee_id": "100001", "task_id": "task:act-1"}),
        ("similar_cases_search", {"employee_id": "100001", "task_id": "task:act-1", "action_key": "manual.equipment.confirm_alarm_context", "limit": 3}),
        ("agent_signals", {"employee_id": "100001", "current_url": "/docs/boi:public:sop:equipment-abnormal-response"}),
        ("work_patterns_search", {"employee_id": "100001", "query": "Mermaid", "limit": 3}),
        ("work_pattern_derive", {"employee_id": "100001", "limit": 3}),
        ("skill_candidate_create", {"employee_id": "100001", "pattern_id": "pattern-1", "title": "Mermaid 정리 Skill 후보"}),
        ("rbac_me", {"employee_id": "100001"}),
        ("rbac_check", {"employee_id": "100001", "required_role": "boi.action_invoker", "scope": "action", "resource": "sop.equipment.request_raw_data"}),
        ("doc_access_check", {"employee_id": "100001", "boi_id": "boi:public:sop:equipment-abnormal-response"}),
        ("rbac_audit", {"employee_id": "100001", "limit": 5, "action": "team_upsert"}),
    ]
    for tool, arguments in requests:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "manual_handoff_complete",
            "arguments": {"employee_id": "100001", "task_id": "task-1", "note": "done", "user_confirmed": False},
        },
    )
    approved = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "manual_handoff_complete",
            "arguments": {"employee_id": "100001", "task_id": "task-1", "note": "done", "user_confirmed": True},
        },
    )

    assert denied.status_code == 400
    assert "user_confirmed=true" in denied.json()["detail"]
    assert approved.status_code == 200
    assert [item["path"] for item in calls] == [
        "/api/agents/boi-wiki/capabilities",
        "/api/agents/boi-wiki/suggestions",
        "/api/dictionary/terms",
        "/api/agents/boi-wiki/memory",
        "/api/private-memory/cleanup-preview",
        "/api/private-memory/cleanup-run",
        "/api/private-memory/restore",
        "/api/docs/boi:private:100001:test/mark-memory",
        "/api/context/work",
        "/api/agents/boi-wiki/inbox/task:act-1/context",
        "/api/agents/boi-wiki/inbox/task:act-1/history",
        "/api/agents/boi-wiki/signals",
        "/api/agents/boi-wiki/patterns",
        "/api/agents/boi-wiki/patterns/derive",
        "/api/rbac/me",
        "/api/rbac/check",
        "/api/docs/boi:public:sop:equipment-abnormal-response/access",
        "/api/rbac/audit",
        "/api/agents/boi-wiki/manual-handoffs/complete",
    ]
    assert calls[1]["payload"]["answer_context"]["intent"] == "diagram"
    assert calls[-1]["payload"]["user_confirmed"] is True


def test_boi_wiki_mcp_rbac_tools_delegate_to_boi_api(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "path": path, "roles": ["boi.viewer"]}

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path, "decision": {"allowed": True}}

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    me = asyncio.run(mcp_module.rbac_me(employee_id="100001"))
    check = asyncio.run(
        mcp_module.rbac_check(
            employee_id="100001",
            required_role="boi.action_invoker",
            scope="action",
            resource="sop.equipment.request_raw_data",
            action_key="sop.equipment.request_raw_data",
        )
    )
    access = asyncio.run(mcp_module.doc_access_check("boi:public:sop:equipment-abnormal-response", employee_id="100001"))
    audit = asyncio.run(mcp_module.rbac_audit(employee_id="100001", limit=5, action="team_upsert"))

    assert me["path"] == "/api/rbac/me"
    assert check["decision"]["allowed"] is True
    assert access["path"] == "/api/docs/boi:public:sop:equipment-abnormal-response/access"
    assert audit["path"] == "/api/rbac/audit"
    assert [item["path"] for item in calls] == [
        "/api/rbac/me",
        "/api/rbac/check",
        "/api/docs/boi:public:sop:equipment-abnormal-response/access",
        "/api/rbac/audit",
    ]
    assert calls[1]["payload"]["required_role"] == "boi.action_invoker"
    assert calls[3]["params"]["action"] == "team_upsert"


def test_boi_wiki_mcp_agent_capabilities_delegate_to_boi_api(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "path": path, "agent_contract_version": "boi-agent.response.v1"}

    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)

    result = asyncio.run(mcp_module.boi_agent_capabilities(employee_id="100001"))

    assert result["path"] == "/api/agents/boi-wiki/capabilities"
    assert result["agent_contract_version"] == "boi-agent.response.v1"
    assert calls == [{"method": "get", "path": "/api/agents/boi-wiki/capabilities", "employee_id": "100001"}]


def test_boi_wiki_mcp_agent_approve_requires_confirmation_and_delegates(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "operation": kwargs["payload"]["operation"]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.boi_agent_approve(
                operation="workflow_start",
                payload={"workflow_key": "equipment-anomaly"},
                employee_id="100001",
                user_confirmed=False,
            )
        )
    result = asyncio.run(
        mcp_module.boi_agent_approve(
            operation="workflow_start",
            payload={"workflow_key": "equipment-anomaly"},
            employee_id="100001",
            user_confirmed=True,
            note="사용자 확인",
        )
    )

    assert result["operation"] == "workflow_start"
    assert calls == [
        {
            "path": "/api/agents/boi-wiki/approve",
            "employee_id": "100001",
            "payload": {
                "operation": "workflow_start",
                "payload": {"workflow_key": "equipment-anomaly"},
                "user_confirmed": True,
                "note": "사용자 확인",
            },
        }
    ]


def test_boi_wiki_mcp_bridge_covers_event_type_draft_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path, "draft": {"draft_id": "event-type-test"}}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "items": [{"draft_id": "event-type-test"}]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    create_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "event_type_draft_create",
            "arguments": {"employee_id": "100001", "event_type": "quality.forecast.requested.v1"},
        },
    )
    create_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "event_type_draft_create",
            "arguments": {
                "employee_id": "100001",
                "event_type": "quality.forecast.requested.v1",
                "name_ko": "품질 예측 요청",
                "description": "품질 시스템 예측이 필요한 시점",
                "recommended_actions": ["mcp.timesfm.forecast"],
                "user_confirmed": True,
            },
        },
    )
    list_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "event_type_drafts", "arguments": {"employee_id": "100001"}},
    )
    validate_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "event_type_draft_validate", "arguments": {"employee_id": "100001", "draft_id": "event-type-test"}},
    )
    apply_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "event_type_draft_apply", "arguments": {"employee_id": "100001", "draft_id": "event-type-test"}},
    )
    apply_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "event_type_draft_apply",
            "arguments": {"employee_id": "100001", "draft_id": "event-type-test", "user_confirmed": True, "note": "confirmed"},
        },
    )

    assert create_denied.status_code == 400
    assert "user_confirmed=true" in create_denied.json()["detail"]
    assert create_ok.status_code == 200
    assert list_ok.status_code == 200
    assert validate_ok.status_code == 200
    assert apply_denied.status_code == 400
    assert "user_confirmed=true" in apply_denied.json()["detail"]
    assert apply_ok.status_code == 200
    assert [item["path"] for item in calls] == [
        "/api/event-types/drafts",
        "/api/event-types/drafts",
        "/api/event-types/drafts/event-type-test/validate",
        "/api/event-types/drafts/event-type-test/apply",
    ]
    assert calls[0]["payload"]["event_type"] == "quality.forecast.requested.v1"
    assert calls[0]["payload"]["user_confirmed"] is True
    assert calls[-1]["payload"]["user_confirmed"] is True


def test_boi_wiki_mcp_bridge_covers_registration_draft_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path, "draft": {"draft_id": "registration-test", "entry_kind": kwargs.get("payload", {}).get("entry_kind")}}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "items": [{"draft_id": "registration-test", "entry_kind": "sop"}]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    create_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "sop_draft_create",
            "arguments": {"employee_id": "100001", "title": "설비 이상 SOP"},
        },
    )
    create_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "sop_draft_create",
            "arguments": {
                "employee_id": "100001",
                "scope": "team",
                "folder": "team/aix-tf/equipment/anomaly",
                "title": "설비 이상 SOP",
                "business_goal": "알람 발생 시 원인 분석 근거와 수동 조치를 표준화한다.",
                "steps": ["이상 감지", "원인 분석", "이상 조치"],
                "evidence_requirements": ["Trend", "Raw Data"],
                "user_confirmed": True,
            },
        },
    )
    list_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "registration_drafts", "arguments": {"employee_id": "100001", "entry_kind": "sop"}},
    )
    validate_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "registration_draft_validate", "arguments": {"employee_id": "100001", "draft_id": "registration-test"}},
    )
    publish_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "registration_draft_publish", "arguments": {"employee_id": "100001", "draft_id": "registration-test"}},
    )
    publish_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "registration_draft_publish",
            "arguments": {"employee_id": "100001", "draft_id": "registration-test", "user_confirmed": True, "note": "confirmed"},
        },
    )

    assert create_denied.status_code == 400
    assert "user_confirmed=true" in create_denied.json()["detail"]
    assert create_ok.status_code == 200
    assert list_ok.status_code == 200
    assert validate_ok.status_code == 200
    assert publish_denied.status_code == 400
    assert "user_confirmed=true" in publish_denied.json()["detail"]
    assert publish_ok.status_code == 200
    assert [item["path"] for item in calls] == [
        "/api/registration/drafts",
        "/api/registration/drafts",
        "/api/registration/drafts/registration-test/validate",
        "/api/registration/drafts/registration-test/publish",
    ]
    assert calls[0]["payload"]["entry_kind"] == "sop"
    assert calls[0]["payload"]["steps"] == ["이상 감지", "원인 분석", "이상 조치"]
    assert calls[-1]["payload"]["user_confirmed"] is True


def test_boi_wiki_mcp_bridge_covers_natural_language_registration_and_event_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path, "payload": kwargs.get("payload", {})}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "path": path, "items": []}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    for tool, arguments in [
        ("registration_plan", {"employee_id": "100001", "entry_kind": "event", "raw_request": "ETCH alarm을 Event로 만들고 싶어"}),
        ("registration_verification_preview", {"employee_id": "100001", "entry_kind": "event", "plan": {"draft_payload": {"event_type": "equipment.alarm.raised.v1"}}}),
        ("sop_registration_plan", {"employee_id": "100001", "raw_request": "ETCH alarm 대응 SOP를 Event와 Action까지 연결하고 싶어", "focus": "event"}),
        ("sop_registration_preview", {"employee_id": "100001", "plan": {"plan_type": "sop_registration_plan"}, "payload": {"sop_mode": "draft"}}),
        ("event_publish_plan", {"employee_id": "100001", "raw_request": "ETCH 장비 Alarm 발생했어"}),
        ("event_publish_preview", {"employee_id": "100001", "event_type": "equipment.alarm.raised.v1"}),
        ("event_pattern_preview", {"employee_id": "100001", "q": "raw data", "limit": 3}),
        ("sop_run_history", {"employee_id": "100001", "limit": 5}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200, response.text

    promote_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "event_pattern_promote_to_draft", "arguments": {"employee_id": "100001"}},
    )
    promote_ok = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "event_pattern_promote_to_draft",
            "arguments": {"employee_id": "100001", "preview": {"suggested_event_type": "raw.data.pattern_detected.v1"}, "user_confirmed": True},
        },
    )

    assert promote_denied.status_code == 400
    assert "user_confirmed=true" in promote_denied.json()["detail"]
    assert promote_ok.status_code == 200
    assert [item["path"] for item in calls] == [
        "/api/registration/plan",
        "/api/registration/verification-preview",
        "/api/sop-registration/plan",
        "/api/sop-registration/preview",
        "/api/events/plan",
        "/api/events/verification-preview",
        "/api/events/patterns/preview",
        "/api/sops/history",
        "/api/events/patterns/promote-to-draft",
    ]


def test_boi_wiki_mcp_bridge_covers_optional_data_lake_tools(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "path": path, "payload": kwargs.get("payload", {})}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "path": path, "enabled": False, "items": []}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)
    client = TestClient(mcp_module.app)

    for tool, arguments in [
        ("data_lake_status", {"employee_id": "100001"}),
        ("data_lake_sources", {"employee_id": "100001"}),
        ("data_lake_query_plan", {"employee_id": "100001", "question": "ETCH trend raw data 찾아줘", "source": "mes"}),
        (
            "data_lake_query_preview",
            {
                "employee_id": "100001",
                "question": "LOT별 pressure spike",
                "source": "mes",
                "sql": "select * from etch where lot_id = :lot",
                "parameters": {"lot": "LOT-A"},
                "limit": 20,
            },
        ),
        (
            "data_lake_query_execute",
            {
                "employee_id": "100001",
                "question": "승인 전 raw data 확인",
                "sql": "select 1",
                "user_confirmed": True,
            },
        ),
        ("data_lake_artifact_get", {"employee_id": "100001", "artifact_id": "artifact-1"}),
        (
            "data_lake_import_sources",
            {
                "employee_id": "100001",
                "source_ids": ["ontology.exports.etch_process_sequence"],
                "user_confirmed": True,
            },
        ),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 200, response.text

    execute_denied = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"server": {"name": "boi-wiki-mcp"}, "tool": "data_lake_query_execute", "arguments": {"employee_id": "100001", "sql": "select 1"}},
    )

    assert execute_denied.status_code == 400
    assert "user_confirmed=true" in execute_denied.json()["detail"]
    assert [item["path"] for item in calls] == [
        "/api/data-lake/status",
        "/api/data-lake/sources",
        "/api/data-lake/query/plan",
        "/api/data-lake/query/preview",
        "/api/data-lake/query/execute",
        "/api/data-lake/artifacts/artifact-1",
        "/api/data-lake/import",
    ]
    assert calls[4]["payload"]["user_confirmed"] is True
    assert calls[6]["payload"]["user_confirmed"] is True


def test_boi_wiki_mcp_bridge_requires_confirmation_for_write_tools(mcp_module):
    client = TestClient(mcp_module.app)
    for tool, arguments in [
        ("workflow_start", {"workflow_key": "equipment-anomaly"}),
        ("boi_agent_approve", {"operation": "event_publish", "payload": {"event_type": "meeting.closed.v1"}}),
        ("registration_draft_create", {"entry_kind": "sop", "title": "x"}),
        ("sop_registration_draft_create", {"payload": {"sop_mode": "draft"}}),
        ("sop_draft_create", {"title": "x"}),
        ("action_draft_create", {"title": "x"}),
        ("registration_draft_publish", {"draft_id": "registration-test"}),
        ("sop_registration_publish", {"draft_id": "sop-registration-test"}),
        ("event_pattern_promote_to_draft", {"preview": {"suggested_event_type": "x.detected.v1"}}),
        ("event_type_draft_create", {"event_type": "quality.forecast.requested.v1"}),
        ("event_type_draft_apply", {"draft_id": "event-type-test"}),
        ("source_apply", {"path": "data/boi/public/test.md", "base_sha256": "x", "proposed_content": "x"}),
        ("doc_body_apply", {"boi_id": "boi:public:test", "base_sha256": "x", "proposed_body": "x"}),
        ("promotion_submit", {"title": "x", "body": "x", "source_refs": []}),
        ("data_lake_query_execute", {"sql": "select 1"}),
        ("data_lake_import_sources", {"source_ids": ["ontology.exports.etch_process_sequence"]}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 400
        assert "user_confirmed=true" in response.json()["detail"]


def test_boi_wiki_mcp_bridge_can_approve_agent_execution_card(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "operation": kwargs["payload"]["operation"], "status": "executed"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    client = TestClient(mcp_module.app)

    response = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi_agent_approve",
            "arguments": {
                "employee_id": "100001",
                "operation": "event_publish",
                "payload": {"event_type": "meeting.closed.v1", "payload": {"topic": "주간회의"}},
                "note": "사용자 확인",
                "user_confirmed": True,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["operation"] == "event_publish"
    assert calls == [
        {
            "path": "/api/agents/boi-wiki/approve",
            "employee_id": "100001",
            "payload": {
                "operation": "event_publish",
                "payload": {"event_type": "meeting.closed.v1", "payload": {"topic": "주간회의"}},
                "user_confirmed": True,
                "note": "사용자 확인",
            },
            "service_token": True,
        }
    ]


def test_boi_wiki_mcp_streamable_http_initializes(mcp_module):
    with TestClient(mcp_module.app) as client:
        response = client.post(
            "/mcp",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.1"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["serverInfo"]["name"] == "boi-wiki-mcp"


def test_boi_wiki_mcp_streamable_http_can_require_service_token(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("DEFAULT_EMPLOYEE_ID", "100001")
    monkeypatch.setenv("MCP_REQUIRE_SERVICE_TOKEN", "true")
    sys.modules.pop("boi_wiki_mcp.app.main", None)
    module = importlib.import_module("boi_wiki_mcp.app.main")
    request_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0.1"},
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }

    with TestClient(module.app) as client:
        denied = client.post("/mcp", headers=headers, json=request_body)
        allowed = client.post("/mcp", headers={**headers, "x-service-token": "test-service-token"}, json=request_body)
        health = client.get("/health")

    assert denied.status_code == 401
    assert denied.json()["detail"] == "MCP service token is required"
    assert allowed.status_code == 200
    assert allowed.json()["result"]["serverInfo"]["name"] == "boi-wiki-mcp"
    assert health.json()["mcp_auth"]["required"] is True


def test_mcp_registration_draft_tools_require_confirmation_for_mutations(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "status": "ok", "draft": {"draft_id": "registration-test"}}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "items": [{"draft_id": "registration-test"}]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(mcp_module.registration_draft_create(entry_kind="sop", title="설비 이상 SOP", employee_id="100001"))
    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(mcp_module.sop_draft_create(title="설비 이상 SOP", employee_id="100001"))
    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(mcp_module.action_draft_create(title="Trend 조회 Action", employee_id="100001"))
    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(mcp_module.registration_draft_publish(draft_id="registration-test", employee_id="100001"))
    assert calls == []

    create_result = asyncio.run(
        mcp_module.registration_draft_create(
            entry_kind="action",
            employee_id="100001",
            title="Trend 조회 Action",
            business_goal="설비 이상 분석 전 Trend 근거를 조회한다.",
            connector_kind="api",
            connector_config={"method": "POST", "endpoint": "https://quality.example/api/trends"},
            input_fields=["equipment_id", "time_window"],
            output_fields=["trend_summary"],
            user_confirmed=True,
        )
    )
    action_result = asyncio.run(
        mcp_module.action_draft_create(
            employee_id="100001",
            title="TimesFM 예측 Action",
            business_goal="시계열 예측이 필요한 경우 MCP tool을 명시적으로 호출한다.",
            connector_kind="mcp",
            connector_config={"server": "timesfm", "tool": "forecast"},
            input_fields=["series"],
            output_fields=["forecast"],
            user_confirmed=True,
        )
    )
    sop_result = asyncio.run(
        mcp_module.sop_draft_create(
            employee_id="100001",
            title="설비 이상 SOP",
            steps=["이상 감지", "원인 분석"],
            user_confirmed=True,
        )
    )
    list_result = asyncio.run(mcp_module.registration_drafts(employee_id="100001", entry_kind="action"))
    validate_result = asyncio.run(mcp_module.registration_draft_validate(draft_id="registration-test", employee_id="100001"))
    publish_result = asyncio.run(mcp_module.registration_draft_publish(draft_id="registration-test", employee_id="100001", user_confirmed=True))

    assert create_result["ok"] is True
    assert action_result["ok"] is True
    assert sop_result["ok"] is True
    assert list_result["items"][0]["draft_id"] == "registration-test"
    assert validate_result["ok"] is True
    assert publish_result["ok"] is True
    assert [item["path"] for item in calls] == [
        "/api/registration/drafts",
        "/api/registration/drafts",
        "/api/registration/drafts",
        "/api/registration/drafts",
        "/api/registration/drafts/registration-test/validate",
        "/api/registration/drafts/registration-test/publish",
    ]
    assert calls[0]["payload"]["entry_kind"] == "action"
    assert calls[0]["payload"]["connector_kind"] == "api"
    assert calls[0]["payload"]["connector_config"]["endpoint"] == "https://quality.example/api/trends"
    assert calls[0]["payload"]["input_fields"] == ["equipment_id", "time_window"]
    assert calls[1]["payload"]["entry_kind"] == "action"
    assert calls[1]["payload"]["connector_kind"] == "mcp"
    assert calls[1]["payload"]["connector_config"]["tool"] == "forecast"
    assert calls[2]["payload"]["entry_kind"] == "sop"
    assert calls[-1]["payload"]["user_confirmed"] is True


def test_mcp_source_apply_requires_user_confirmation(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "status": "applied"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.source_apply(
                path="data/boi/public/example.md",
                base_sha256="sha",
                proposed_content="content",
                user_confirmed=False,
            )
        )
    assert calls == []

    result = asyncio.run(
        mcp_module.source_apply(
            path="data/boi/public/example.md",
            base_sha256="sha",
            proposed_content="content",
            user_confirmed=True,
        )
    )

    assert result["status"] == "applied"
    assert calls[0]["path"] == "/api/source/apply"


def test_mcp_doc_body_apply_requires_user_confirmation(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "status": "applied"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.doc_body_apply(
                boi_id="boi:public:test",
                base_sha256="sha",
                proposed_body="body",
                user_confirmed=False,
            )
        )
    assert calls == []

    result = asyncio.run(
        mcp_module.doc_body_apply(
            boi_id="boi:public:test",
            base_sha256="sha",
            proposed_body="body",
            user_confirmed=True,
        )
    )

    assert result["status"] == "applied"
    assert calls[0]["path"] == "/api/docs/boi:public:test/body-apply"


def test_mcp_event_type_draft_tools_require_confirmation_for_mutations(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"method": "post", "path": path, **kwargs})
        return {"ok": True, "status": "ok", "draft": {"draft_id": "event-type-test"}}

    async def fake_api_get(path, **kwargs):
        calls.append({"method": "get", "path": path, **kwargs})
        return {"ok": True, "items": [{"draft_id": "event-type-test"}]}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_api_get)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.event_type_draft_create(
                event_type="quality.forecast.requested.v1",
                employee_id="100001",
                user_confirmed=False,
            )
        )
    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.event_type_draft_apply(
                draft_id="event-type-test",
                employee_id="100001",
                user_confirmed=False,
            )
        )
    assert calls == []

    create_result = asyncio.run(
        mcp_module.event_type_draft_create(
            event_type="quality.forecast.requested.v1",
            employee_id="100001",
            name_ko="품질 예측 요청",
            user_confirmed=True,
        )
    )
    list_result = asyncio.run(mcp_module.event_type_drafts(employee_id="100001"))
    validate_result = asyncio.run(mcp_module.event_type_draft_validate(draft_id="event-type-test", employee_id="100001"))
    apply_result = asyncio.run(
        mcp_module.event_type_draft_apply(
            draft_id="event-type-test",
            employee_id="100001",
            user_confirmed=True,
        )
    )

    assert create_result["ok"] is True
    assert list_result["items"][0]["draft_id"] == "event-type-test"
    assert validate_result["ok"] is True
    assert apply_result["ok"] is True
    assert [item["path"] for item in calls] == [
        "/api/event-types/drafts",
        "/api/event-types/drafts",
        "/api/event-types/drafts/event-type-test/validate",
        "/api/event-types/drafts/event-type-test/apply",
    ]
    assert calls[0]["payload"]["event_type"] == "quality.forecast.requested.v1"
    assert calls[0]["payload"]["user_confirmed"] is True
    assert calls[-1]["payload"]["user_confirmed"] is True


def test_mcp_action_invoke_requires_confirmation_for_real_execution(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "status": "invoked"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.action_invoke(
                action_key="sop.equipment.request_raw_data",
                employee_id="100001",
                dry_run=False,
                user_confirmed=False,
            )
        )
    assert calls == []

    dry_run_result = asyncio.run(
        mcp_module.action_invoke(
            action_key="sop.equipment.request_raw_data",
            employee_id="100001",
            dry_run=True,
            user_confirmed=False,
        )
    )
    assert dry_run_result["status"] == "invoked"
    assert calls[0]["payload"]["dry_run"] is True

    real_result = asyncio.run(
        mcp_module.action_invoke(
            action_key="sop.equipment.request_raw_data",
            employee_id="100001",
            dry_run=False,
            user_confirmed=True,
        )
    )
    assert real_result["status"] == "invoked"
    assert calls[1]["payload"]["dry_run"] is False
    assert calls[1]["payload"]["user_confirmed"] is True


def test_mcp_workflow_start_requires_user_confirmation(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "trace_id": "trace-confirmed"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.workflow_start(
                workflow_key="equipment-anomaly",
                employee_id="100001",
                payload={"equipment_id": "ETCH-VM-01"},
                user_confirmed=False,
            )
        )
    assert calls == []

    result = asyncio.run(
        mcp_module.workflow_start(
            workflow_key="equipment-anomaly",
            employee_id="100001",
            payload={"equipment_id": "ETCH-VM-01"},
            user_confirmed=True,
        )
    )

    assert result["trace_id"] == "trace-confirmed"
    assert calls[0]["path"] == "/api/workflows/equipment-anomaly/start"
    assert calls[0]["payload"]["equipment_id"] == "ETCH-VM-01"
    assert calls[0]["payload"]["user_confirmed"] is True


def test_mcp_promotion_submit_requires_user_confirmation(mcp_module, monkeypatch):
    calls: list[dict[str, object]] = []

    async def fake_api_post(path, **kwargs):
        calls.append({"path": path, **kwargs})
        return {"ok": True, "promotion_id": "promo-test"}

    monkeypatch.setattr(mcp_module, "api_post", fake_api_post)

    with pytest.raises(RuntimeError, match="user_confirmed=true"):
        asyncio.run(
            mcp_module.promotion_submit(
                title="Team 공유 후보",
                body="# Summary\n\n공유 후보",
                source_refs=[{"type": "boi", "ref": "local-private:test"}],
                employee_id="100001",
                user_confirmed=False,
            )
        )
    assert calls == []

    result = asyncio.run(
        mcp_module.promotion_submit(
            title="Team 공유 후보",
            body="# Summary\n\n공유 후보",
            source_refs=[{"type": "boi", "ref": "local-private:test"}],
            employee_id="100001",
            user_confirmed=True,
        )
    )
    assert result["promotion_id"] == "promo-test"
    assert calls[0]["path"] == "/api/promotions/submit"
    assert calls[0]["payload"]["user_confirmed"] is True


def test_check_boi_wiki_mcp_details_and_client_checklist(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_protocol(*args, **kwargs):
        return {
            "tools": 80,
            "resources": 0,
            "resource_templates": 11,
            "prompts": 5,
            "tool_names": [
                "boi_search",
                "boi_get",
                "workflow_status",
                "boi_agent_chat",
                "boi_agent_capabilities",
                "boi_agent_approve",
                "ontology_search",
                "agent_inbox",
                "registration_draft_create",
                "registration_drafts",
                "registration_draft_validate",
                "registration_draft_publish",
                "sop_registration_plan",
                "sop_registration_draft_create",
                "sop_draft_create",
                "action_draft_create",
                "event_type_draft_create",
                "event_type_drafts",
                "event_type_draft_validate",
                "event_type_draft_apply",
                "action_invoke",
                "source_preview",
                "source_apply",
                "doc_body_preview",
                "doc_body_apply",
                "promotion_submit",
                "promotion_status",
            ],
            "resource_template_uris": ["boi://docs/{boi_id}", "boi://search/ontology/{query}"],
            "prompt_names": ["create_sop_from_source"],
        }

    async def fake_check_bridge(*args, **kwargs):
        return {
            "ok": True,
            "status": "mcp_invoked",
            "tool": "boi.search",
            "request_id": "check-boi-wiki-mcp",
            "response": {"folder_tree": {"path": ""}},
        }

    monkeypatch.setattr(script, "check_protocol", fake_check_protocol)
    monkeypatch.setattr(script, "check_bridge", fake_check_bridge)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        service_token="test-service-token",
        query="SOP",
        summary=False,
        details=True,
        client_checklist=True,
        full_bridge=False,
        require_bridge=False,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "boi_search" in output
    assert "workflow_status" in output
    assert "boi_agent_chat" in output
    assert "boi_agent_capabilities" in output
    assert "boi_agent_approve" in output
    assert "ontology_search" in output
    assert "agent_inbox" in output
    assert "registration_draft_create" in output
    assert "registration_draft_publish" in output
    assert "sop_registration_plan" in output
    assert "sop_registration_draft_create" in output
    assert "sop_draft_create" in output
    assert "action_draft_create" in output
    assert "event_type_draft_create" in output
    assert "event_type_draft_apply" in output
    assert "source_apply" in output
    assert "doc_body_apply" in output
    assert "promotion_submit" in output
    assert "Codex" in output
    assert "Claude Desktop" in output
    assert "Cursor" in output
    assert "http://localhost:8200/mcp" in output
    assert "folder_tree" not in output


def test_check_boi_wiki_mcp_skips_authenticated_bridge_without_token(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_protocol(*args, **kwargs):
        return {
            "tools": 80,
            "resources": 0,
            "resource_templates": 11,
            "prompts": 5,
        }

    async def fail_bridge(*args, **kwargs):
        raise AssertionError("bridge must not be called without a service token")

    monkeypatch.setattr(script, "check_protocol", fake_check_protocol)
    monkeypatch.setattr(script, "check_bridge", fail_bridge)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        service_token="",
        query="SOP",
        summary=True,
        details=False,
        client_checklist=False,
        full_bridge=False,
        require_bridge=False,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["bridge"]["status"] == "skipped"


def test_check_boi_wiki_mcp_can_require_authenticated_bridge(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_protocol(*args, **kwargs):
        return {
            "tools": 80,
            "resources": 0,
            "resource_templates": 11,
            "prompts": 5,
        }

    monkeypatch.setattr(script, "check_protocol", fake_check_protocol)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        service_token="",
        query="SOP",
        summary=True,
        details=False,
        client_checklist=False,
        full_bridge=False,
        require_bridge=True,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is False
    assert body["bridge"]["status"] == "skipped"


def test_check_boi_wiki_mcp_agent_contract_validates_rest_and_mcp(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    agent_schema = {
        "type": "object",
        "required": [
            "agent_contract_version",
            "answer_markdown",
            "display_markdown",
            "links",
            "citations",
            "artifacts",
            "execution_cards",
            "status_updates",
            "tool_trace",
            "access_summary",
            "guardrails_applied",
        ],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "display_markdown": {"type": "string"},
            "links": {"type": "array"},
            "citations": {"type": "array"},
            "artifacts": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "tool_trace": {"type": "array"},
            "access_summary": {"type": "object"},
            "guardrails_applied": {"type": "array"},
        },
    }
    agent_response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "계약 검증 응답",
        "display_markdown": "계약 검증 응답",
        "links": [],
        "citations": [],
        "artifacts": [],
        "execution_cards": [
            {
                "contract_version": "boi-agent.response.v1",
                "operation": "event_publish",
                "requires_confirmation": True,
                "user_confirmed_required": True,
                "required_role": "boi.workflow_runner",
                "permission": {"allowed": True, "role": "boi.workflow_runner"},
            }
        ],
        "status_updates": [],
        "status_events": [],
        "tool_trace": [],
        "access_summary": {},
        "guardrails_applied": [],
    }

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            self.calls.append(("get", url, kwargs))
            if url == "http://boi-api.test/api/agents/boi-wiki/response-schema":
                return FakeResponse({"ok": True, "agent_contract_version": "boi-agent.response.v1", "schema": agent_schema})
            if url == "http://mcp.test/health":
                return FakeResponse({"ok": True, "agent_response_schema": agent_schema})
            raise AssertionError(url)

        async def post(self, url, **kwargs):
            self.calls.append(("post", url, kwargs))
            if url == "http://boi-api.test/api/agents/boi-wiki/chat":
                assert kwargs["params"]["employee_id"] == "100001"
                return FakeResponse(agent_response)
            if url == "http://mcp.test/api/mcp/call":
                assert kwargs["headers"]["x-service-token"] == "test-service-token"
                assert kwargs["json"]["tool"] == "boi_agent_chat"
                return FakeResponse({"ok": True, "result": agent_response})
            raise AssertionError(url)

    monkeypatch.setattr(script.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        script.check_agent_contract(
            boi_api_url="http://boi-api.test",
            mcp_base_url="http://mcp.test",
            employee_id="100001",
            service_token="test-service-token",
            question="SOP 찾아줘",
            current_url="/sops",
        )
    )

    assert result["ok"] is True
    assert result["schema"]["version"] == "boi-agent.response.v1"
    assert result["rest_chat"]["schema_valid"] is True
    assert result["rest_chat"]["status_alias_matches"] is True
    assert result["mcp_status_schema"]["matches_api_schema"] is True
    assert result["mcp_status_schema"]["status_alias_supported"] is True
    assert result["mcp_bridge_chat"]["schema_valid"] is True
    assert result["mcp_bridge_chat"]["status_alias_matches"] is True


def test_check_boi_wiki_mcp_agent_contract_artifact_smoke_validates_rest_and_mcp(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    agent_schema = {
        "type": "object",
        "required": [
            "agent_contract_version",
            "answer_markdown",
            "display_markdown",
            "links",
            "citations",
            "artifacts",
            "execution_cards",
            "status_updates",
            "tool_trace",
            "access_summary",
            "guardrails_applied",
        ],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "display_markdown": {"type": "string"},
            "links": {"type": "array"},
            "citations": {"type": "array"},
            "artifacts": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "tool_trace": {"type": "array"},
            "access_summary": {"type": "object"},
            "guardrails_applied": {"type": "array"},
        },
    }

    def agent_response(*, artifacts=None, intent="search"):
        return {
            "agent_contract_version": "boi-agent.response.v1",
            "answer_markdown": "계약 검증 응답",
            "display_markdown": "계약 검증 응답",
            "links": [],
            "citations": [],
            "artifacts": artifacts or [],
            "execution_cards": [],
            "status_updates": [],
            "status_events": [],
            "tool_trace": [],
            "access_summary": {},
            "guardrails_applied": [],
            "route": "deep" if artifacts else "fast",
            "intent": intent,
            "used_backend": "native_langgraph",
        }

    smoke_response = agent_response(
        artifacts=[
            {
                "type": "workflow_summary",
                "title": "SOP 관계 요약",
                "data": [
                    {
                        "stage": "이상 감지",
                        "events": "equipment.alarm.raised.v1",
                        "actions": "api.equipment.request_trend_history",
                        "manual_actions": "manual.root_cause.review",
                        "next_stage": "원인 분석",
                    }
                ],
            }
        ],
        intent="workflow_explain",
    )

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.posts = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            if url == "http://boi-api.test/api/agents/boi-wiki/response-schema":
                return FakeResponse({"ok": True, "agent_contract_version": "boi-agent.response.v1", "schema": agent_schema})
            if url == "http://mcp.test/health":
                return FakeResponse({"ok": True, "agent_response_schema": agent_schema})
            raise AssertionError(url)

        async def post(self, url, **kwargs):
            self.posts.append((url, kwargs))
            if url == "http://boi-api.test/api/agents/boi-wiki/chat":
                payload = kwargs["json"]
                assert kwargs["params"]["employee_id"] == "100001"
                if "Manual Handoff 관계" in payload["question"]:
                    assert "mode" not in payload
                    return FakeResponse(smoke_response)
                return FakeResponse(agent_response())
            if url == "http://mcp.test/api/mcp/call":
                payload = kwargs["json"]
                assert kwargs["headers"]["x-service-token"] == "test-service-token"
                assert payload["tool"] == "boi_agent_chat"
                arguments = payload["arguments"]
                if "Manual Handoff 관계" in arguments["question"]:
                    assert "mode" not in arguments
                    return FakeResponse({"ok": True, "result": smoke_response})
                return FakeResponse({"ok": True, "result": agent_response()})
            raise AssertionError(url)

    monkeypatch.setattr(script.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        script.check_agent_contract(
            boi_api_url="http://boi-api.test",
            mcp_base_url="http://mcp.test",
            employee_id="100001",
            service_token="test-service-token",
            artifact_smoke=True,
        )
    )

    assert result["ok"] is True
    assert result["artifact_smoke"]["rest_chat"]["schema_valid"] is True
    assert result["artifact_smoke"]["rest_chat"]["workflow_summary"]["row_count"] == 1
    assert result["artifact_smoke"]["mcp_bridge_chat"]["schema_valid"] is True
    assert result["artifact_smoke"]["mcp_bridge_chat"]["workflow_summary"]["row_count"] == 1


def test_check_boi_wiki_mcp_agent_contract_artifact_smoke_rejects_missing_artifact(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    schema = {
        "type": "object",
        "required": [
            "agent_contract_version",
            "answer_markdown",
            "display_markdown",
            "links",
            "citations",
            "artifacts",
            "execution_cards",
            "status_updates",
            "tool_trace",
            "access_summary",
            "guardrails_applied",
        ],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
        },
    }
    response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "ok",
        "display_markdown": "ok",
        "links": [],
        "citations": [],
        "artifacts": [],
        "execution_cards": [],
        "status_updates": [],
        "status_events": [],
        "tool_trace": [],
        "access_summary": {},
        "guardrails_applied": [],
    }

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            if url.endswith("/api/agents/boi-wiki/response-schema"):
                return FakeResponse({"agent_contract_version": "boi-agent.response.v1", "schema": schema})
            if url.endswith("/health"):
                return FakeResponse({"ok": True, "agent_response_schema": schema})
            raise AssertionError(url)

        async def post(self, url, **kwargs):
            if url.endswith("/api/agents/boi-wiki/chat"):
                return FakeResponse(response)
            raise AssertionError(url)

    monkeypatch.setattr(script.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="workflow_summary artifact"):
        asyncio.run(
            script.check_agent_contract(
                boi_api_url="http://boi-api.test",
                mcp_base_url="http://mcp.test",
                employee_id="100001",
                artifact_smoke=True,
            )
        )


def test_check_boi_wiki_mcp_agent_contract_rejects_status_alias_drift():
    import scripts.check_boi_wiki_mcp as script

    schema = {
        "type": "object",
        "required": ["agent_contract_version", "answer_markdown", "execution_cards", "status_updates"],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "operation": {"type": "string"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
        },
    }
    response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "계약 검증 응답",
        "execution_cards": [],
        "status_updates": [{"stage": "retrieval", "message": "검색 중", "source": "llm_status"}],
        "status_events": [{"stage": "compose", "message": "답변 작성 중", "source": "llm_status"}],
    }

    with pytest.raises(RuntimeError, match="status_events must match canonical status_updates"):
        script.agent_response_summary(response, schema)


def test_check_boi_wiki_mcp_agent_contract_rejects_mcp_status_schema_drift(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    agent_schema = {
        "type": "object",
        "required": ["agent_contract_version", "answer_markdown", "execution_cards", "status_updates"],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
        },
    }
    drifted_schema = {
        "type": "object",
        "required": ["agent_contract_version", "answer_markdown", "execution_cards", "status_updates"],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                        "unexpected_mcp_only_field": {"type": "string"},
                    },
                },
            },
        },
    }
    agent_response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "계약 검증 응답",
        "status_updates": [],
        "status_events": [],
        "execution_cards": [
            {
                "contract_version": "boi-agent.response.v1",
                "operation": "event_publish",
                "requires_confirmation": True,
                "user_confirmed_required": True,
                "required_role": "boi.workflow_runner",
                "permission": {"allowed": True, "role": "boi.workflow_runner"},
            }
        ],
    }

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            if url == "http://boi-api.test/api/agents/boi-wiki/response-schema":
                return FakeResponse({"ok": True, "agent_contract_version": "boi-agent.response.v1", "schema": agent_schema})
            if url == "http://mcp.test/health":
                return FakeResponse({"ok": True, "agent_response_schema": drifted_schema})
            raise AssertionError(url)

        async def post(self, url, **kwargs):
            if url == "http://boi-api.test/api/agents/boi-wiki/chat":
                return FakeResponse(agent_response)
            raise AssertionError(url)

    monkeypatch.setattr(script.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="MCP status AgentResponse schema does not match BoI API schema"):
        asyncio.run(
            script.check_agent_contract(
                boi_api_url="http://boi-api.test",
                mcp_base_url="http://mcp.test",
                employee_id="100001",
            )
        )


def test_check_boi_wiki_mcp_agent_contract_rejects_missing_execution_permission_fields(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    legacy_schema = {
        "type": "object",
        "required": [
            "agent_contract_version",
            "answer_markdown",
            "display_markdown",
            "links",
            "citations",
            "artifacts",
            "execution_cards",
            "status_updates",
            "tool_trace",
            "access_summary",
            "guardrails_applied",
        ],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "answer_markdown": {"type": "string"},
            "display_markdown": {"type": "string"},
            "links": {"type": "array"},
            "citations": {"type": "array"},
            "artifacts": {"type": "array"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["contract_version", "operation", "requires_confirmation", "user_confirmed_required"],
                    "properties": {"contract_version": {"const": "boi-agent.response.v1"}},
                },
            },
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
            "tool_trace": {"type": "array"},
            "access_summary": {"type": "object"},
            "guardrails_applied": {"type": "array"},
        },
    }
    legacy_response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "legacy contract response",
        "display_markdown": "legacy contract response",
        "links": [],
        "citations": [],
        "artifacts": [],
        "execution_cards": [
            {
                "contract_version": "boi-agent.response.v1",
                "operation": "event_publish",
                "requires_confirmation": True,
                "user_confirmed_required": True,
            }
        ],
        "status_updates": [],
        "status_events": [],
        "tool_trace": [],
        "access_summary": {},
        "guardrails_applied": [],
    }

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            if url == "http://boi-api.test/api/agents/boi-wiki/response-schema":
                return FakeResponse({"ok": True, "agent_contract_version": "boi-agent.response.v1", "schema": legacy_schema})
            if url == "http://mcp.test/health":
                return FakeResponse({"ok": True, "agent_response_schema": legacy_schema})
            raise AssertionError(url)

        async def post(self, url, **kwargs):
            if url == "http://boi-api.test/api/agents/boi-wiki/chat":
                return FakeResponse(legacy_response)
            raise AssertionError(url)

    monkeypatch.setattr(script.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="execution_cards schema must require"):
        asyncio.run(
            script.check_agent_contract(
                boi_api_url="http://boi-api.test",
                mcp_base_url="http://mcp.test",
                employee_id="100001",
            )
        )


def test_check_boi_wiki_mcp_main_can_include_agent_contract(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_protocol(*args, **kwargs):
        return {"tools": 80, "resources": 0, "resource_templates": 11, "prompts": 5}

    async def fake_check_bridge(*args, **kwargs):
        return {"ok": True, "status": "mcp_invoked", "tool": "boi.search", "request_id": "check-boi-wiki-mcp"}

    async def fake_check_agent_contract(**kwargs):
        return {
            "ok": True,
            "schema": {"version": "boi-agent.response.v1"},
            "rest_chat": {"schema_valid": True},
            "mcp_bridge_chat": {"schema_valid": True},
        }

    monkeypatch.setattr(script, "check_protocol", fake_check_protocol)
    monkeypatch.setattr(script, "check_bridge", fake_check_bridge)
    monkeypatch.setattr(script, "check_agent_contract", fake_check_agent_contract)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        boi_api_url="http://localhost:8000",
        service_token="test-service-token",
        query="SOP",
        employee_id="100001",
        agent_contract=True,
        agent_question="SOP 찾아줘",
        agent_current_url="/sops",
        summary=True,
        details=False,
        client_checklist=False,
        full_bridge=False,
        require_bridge=False,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["agent_contract"]["schema"]["version"] == "boi-agent.response.v1"
    assert body["agent_contract"]["rest_chat"]["schema_valid"] is True
    assert body["agent_contract"]["mcp_bridge_chat"]["schema_valid"] is True


def test_check_boi_wiki_mcp_reads_service_token_from_dotenv_without_printing(monkeypatch, capsys, tmp_path):
    import scripts.check_boi_wiki_mcp as script

    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join(
            [
                "IGNORED=value",
                "SERVICE_TOKEN=dotenv-secret-token",
                "OTHER_SECRET=must-not-appear",
            ]
        ),
        encoding="utf-8",
    )
    seen: dict[str, str] = {}

    async def fake_check_protocol(*args, **kwargs):
        seen["protocol_token"] = kwargs.get("service_token", "")
        return {"tools": 80, "resources": 0, "resource_templates": 11, "prompts": 5}

    async def fake_check_bridge(base_url, service_token, query):
        seen["bridge_token"] = service_token
        return {"ok": True, "status": "mcp_invoked", "tool": "boi.search", "request_id": "check-boi-wiki-mcp"}

    async def fake_check_agent_contract(**kwargs):
        seen["agent_token"] = kwargs.get("service_token", "")
        return {
            "ok": True,
            "schema": {"version": "boi-agent.response.v1"},
            "rest_chat": {"schema_valid": True},
            "mcp_bridge_chat": {"schema_valid": True},
        }

    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.setattr(script, "check_protocol", fake_check_protocol)
    monkeypatch.setattr(script, "check_bridge", fake_check_bridge)
    monkeypatch.setattr(script, "check_agent_contract", fake_check_agent_contract)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        boi_api_url="http://localhost:8000",
        service_token="",
        service_token_env="",
        service_token_dotenv=str(dotenv),
        query="SOP",
        employee_id="100001",
        agent_contract=True,
        agent_question="SOP 찾아줘",
        agent_current_url="/sops",
        summary=True,
        details=False,
        client_checklist=False,
        full_bridge=False,
        require_bridge=True,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 0
    assert seen == {
        "protocol_token": "dotenv-secret-token",
        "bridge_token": "dotenv-secret-token",
        "agent_token": "dotenv-secret-token",
    }
    output = capsys.readouterr().out
    assert "dotenv-secret-token" not in output
    assert "must-not-appear" not in output
    body = json.loads(output)
    assert body["ok"] is True
    assert body["bridge"]["status"] == "mcp_invoked"


def test_check_boi_wiki_mcp_agent_contract_only_can_require_bridge(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_agent_contract(**kwargs):
        return {
            "ok": True,
            "schema": {"version": "boi-agent.response.v1"},
            "rest_chat": {"schema_valid": True},
            "mcp_bridge_chat": {
                "schema_valid": None,
                "status": "skipped",
                "reason": "service token not provided",
            },
        }

    monkeypatch.setattr(script, "check_agent_contract", fake_check_agent_contract)
    args = argparse.Namespace(
        base_url="http://localhost:8200",
        mcp_url="http://localhost:8200/mcp",
        boi_api_url="http://localhost:8000",
        service_token="",
        service_token_env="",
        service_token_dotenv="",
        query="SOP",
        employee_id="100001",
        agent_contract=False,
        agent_contract_only=True,
        agent_question="SOP 찾아줘",
        agent_current_url="/sops",
        summary=True,
        details=False,
        client_checklist=False,
        full_bridge=False,
        require_bridge=True,
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is False
    assert body["agent_contract"]["mcp_bridge_chat"]["status"] == "skipped"


def test_check_boi_wiki_mcp_agent_contract_only_works_without_optional_dependencies(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_boi_wiki_mcp.py"
    spec = importlib.util.spec_from_file_location("check_boi_wiki_mcp_no_optional_deps", script_path)
    module = importlib.util.module_from_spec(spec)
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "httpx" or name == "jsonschema" or name == "mcp" or name.startswith("mcp."):
            raise ImportError(f"blocked optional dependency: {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.httpx is None
    assert module.validate is None
    monkeypatch.delattr(module.asyncio, "to_thread", raising=False)

    schema = {
        "type": "object",
        "required": [
            "agent_contract_version",
            "answer_markdown",
            "display_markdown",
            "links",
            "citations",
            "artifacts",
            "execution_cards",
            "status_updates",
            "tool_trace",
            "access_summary",
            "guardrails_applied",
        ],
        "properties": {
            "agent_contract_version": {"const": "boi-agent.response.v1"},
            "execution_cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "contract_version",
                        "operation",
                        "requires_confirmation",
                        "user_confirmed_required",
                        "required_role",
                        "permission",
                    ],
                    "properties": {
                        "contract_version": {"const": "boi-agent.response.v1"},
                        "required_role": {"type": "string"},
                        "permission": {"type": "object"},
                    },
                },
            },
            "status_updates": {"type": "array"},
            "status_events": {"type": "array"},
        },
    }
    response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "ok",
        "display_markdown": "ok",
        "links": [],
        "citations": [],
        "artifacts": [],
        "execution_cards": [],
        "status_updates": [],
        "status_events": [],
        "tool_trace": [],
        "access_summary": {},
        "guardrails_applied": [],
    }

    class FakeHTTPResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url.endswith("/api/agents/boi-wiki/response-schema"):
            return FakeHTTPResponse({"agent_contract_version": "boi-agent.response.v1", "schema": schema})
        if url.endswith("/health"):
            return FakeHTTPResponse({"ok": True, "agent_response_schema": schema})
        if url.endswith("/api/agents/boi-wiki/chat?employee_id=100001"):
            return FakeHTTPResponse(response)
        if url.endswith("/api/mcp/call"):
            return FakeHTTPResponse({"ok": True, "result": response})
        raise AssertionError(url)

    monkeypatch.setattr(module.urllib_request, "urlopen", fake_urlopen)

    result = asyncio.run(
        module.check_agent_contract(
            boi_api_url="http://boi-api.test",
            mcp_base_url="http://mcp.test",
            employee_id="100001",
            service_token="test-token",
        )
    )

    assert result["ok"] is True
    assert result["rest_chat"]["schema_valid"] is True
    assert result["mcp_status_schema"]["matches_api_schema"] is True
    assert result["mcp_bridge_chat"]["schema_valid"] is True


def test_check_boi_wiki_mcp_uses_stateless_json_protocol_when_client_stream_breaks(monkeypatch):
    import scripts.check_boi_wiki_mcp as script
    seen_tokens: list[tuple[str, str]] = []

    async def broken_client(*args, **kwargs):
        seen_tokens.append(("client", str(kwargs.get("service_token") or "")))
        raise RuntimeError("stream client broke before tools/list")

    async def stateless_json(*args, **kwargs):
        seen_tokens.append(("stateless", str(kwargs.get("service_token") or "")))
        return {
            "tools": 22,
            "resources": 0,
            "resource_templates": 11,
            "prompts": 5,
            "tool_names": ["boi_agent_chat", "ontology_search", "agent_inbox"],
            "resource_template_uris": ["boi://search/ontology/{query}"],
            "prompt_names": ["create_sop_from_source"],
        }

    monkeypatch.setattr(script, "check_protocol_mcp_client", broken_client)
    monkeypatch.setattr(script, "check_protocol_stateless_json", stateless_json)

    result = asyncio.run(script.check_protocol("http://localhost:8200/mcp", include_details=True, service_token="test-token"))

    assert result["tools"] == 22
    assert result["resource_templates"] == 11
    assert result["prompts"] == 5
    assert result["transport_mode"] == "stateless_json_rpc"
    assert "stream client broke" in result["client_warning"]
    assert seen_tokens == [("client", "test-token"), ("stateless", "test-token")]


def test_check_boi_wiki_mcp_reports_auth_required_without_token(monkeypatch):
    import httpx
    import scripts.check_boi_wiki_mcp as script

    async def broken_client(*args, **kwargs):
        raise RuntimeError("stream client unauthorized")

    async def unauthorized_stateless(*args, **kwargs):
        request = httpx.Request("POST", "http://localhost:8200/mcp")
        response = httpx.Response(401, request=request, json={"detail": "MCP service token is required"})
        raise httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)

    monkeypatch.setattr(script, "check_protocol_mcp_client", broken_client)
    monkeypatch.setattr(script, "check_protocol_stateless_json", unauthorized_stateless)

    result = asyncio.run(script.check_protocol("http://localhost:8200/mcp", include_details=False, service_token=""))

    assert result["status"] == "auth_required"
    assert result["auth_required"] is True
    assert result["tools"] == 0
    assert "--service-token" in result["message"]
