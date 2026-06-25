from __future__ import annotations

import argparse
import asyncio
import importlib
import sys

from fastapi.testclient import TestClient
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
    assert body["capabilities"]["tools"] == 26
    assert body["capabilities"]["resource_templates"] == 5
    assert body["capability_lists"]["tools"][0]["name"] == "boi_search"
    assert body["agent_interfaces"]["json_api"] == "/api/agents/boi-wiki/chat"
    assert body["agent_interfaces"]["streaming_api"] == "/api/agents/boi-wiki/chat/stream"
    assert body["agent_interfaces"]["mcp_tool"] == "boi_agent_chat"
    assert body["agent_interfaces"]["response_contract_version"] == "boi-agent.response.v1"
    assert body["agent_interfaces"]["streaming_events"] == ["status", "answer_delta", "final", "error"]
    assert body["agent_response_contract"]["version"] == "boi-agent.response.v1"
    assert body["agent_response_contract"]["canonical_endpoint"] == "/api/agents/boi-wiki/chat"
    assert body["agent_response_contract"]["stream_endpoint"] == "/api/agents/boi-wiki/chat/stream"
    assert body["agent_response_contract"]["mcp_tool"] == "boi_agent_chat"
    assert "web_pet" in body["agent_response_contract"]["consumers"]
    assert "boi_wiki_mcp" in body["agent_response_contract"]["consumers"]
    assert "external_api" in body["agent_response_contract"]["consumers"]
    assert "answer_markdown" in body["agent_response_contract"]["required_fields"]
    assert "artifacts" in body["agent_response_contract"]["required_fields"]
    assert "guardrails_applied" in body["agent_response_contract"]["required_fields"]
    assert "mermaid" in body["agent_response_contract"]["artifact_types"]
    assert "gap_table" in body["agent_response_contract"]["artifact_types"]
    tool_names = [item["name"] for item in body["capability_lists"]["tools"]]
    assert "source_preview" in tool_names
    assert "source_apply" in tool_names
    assert "doc_body_preview" in tool_names
    assert "doc_body_apply" in tool_names
    assert "boi_agent_chat" in tool_names
    assert "ontology_search" in tool_names
    assert "agent_inbox" in tool_names
    assert "manual_handoff_complete" in tool_names
    assert "event_type_draft_create" in tool_names
    assert "event_type_drafts" in tool_names
    assert "event_type_draft_validate" in tool_names
    assert "event_type_draft_apply" in tool_names
    assert "source_create_draft" not in tool_names
    assert "doc_body_create_draft" not in tool_names
    assert any(item["name"] == "promotion_submit" for item in body["capability_lists"]["tools"])
    assert any(item["uri"] == "boi://docs/{boi_id}" for item in body["capability_lists"]["resource_templates"])
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
    assert "Tools" in body and "26" in body
    assert "Resource templates" in body and "5" in body
    assert "Prompts" in body and "5" in body
    assert "boi_search" in body
    assert "workflow_status" in body
    assert "action_invoke" in body
    assert "source_apply" in body
    assert "doc_body_apply" in body
    assert "promotion_submit" in body
    assert "boi_agent_chat" in body
    assert "boi-agent.response.v1" in body
    assert "/api/agents/boi-wiki/chat/stream" in body
    assert "answer_delta" in body
    assert "ontology_search" in body
    assert "agent_inbox" in body
    assert "event_type_draft_create" in body
    assert "event_type_draft_apply" in body
    assert "boi://docs/{boi_id}" in body
    assert "boi://search/ontology/{query}" in body
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
            "execution_cards": [
                {
                    "operation": "event_publish",
                    "requires_confirmation": True,
                    "user_confirmed_required": True,
                    "display": {"title": "이벤트 발행 확인", "next_action": "요청 실행"},
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
            "arguments": {"question": "SOP 찾아줘", "employee_id": "100001", "mode": "fast", "current_url": "/sops", "selected_text": "SOP"},
        },
    )
    inbox = client.post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "agent_inbox",
            "arguments": {"employee_id": "100001", "limit": 3},
        },
    )

    assert chat.status_code == 200
    agent_result = chat.json()["result"]
    assert agent_result["agent_contract_version"] == "boi-agent.response.v1"
    assert agent_result["answer_markdown"] == "agent answer"
    assert agent_result["links"][0]["label"] == "SOP"
    assert agent_result["artifacts"][0]["type"] == "mermaid"
    assert agent_result["execution_cards"][0]["requires_confirmation"] is True
    assert agent_result["access_summary"]["can_read"] is True
    assert "mutation_confirmation" in agent_result["guardrails_applied"]
    assert inbox.status_code == 200
    assert inbox.json()["result"]["items"][0]["task_id"] == "task-1"
    assert calls[0]["path"] == "/api/agents/boi-wiki/chat"
    assert calls[0]["payload"]["mode"] == "fast"
    assert calls[0]["payload"]["selected_text"] == "SOP"
    assert calls[1]["path"] == "/api/agents/boi-wiki/inbox"


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
        ("boi_agent_suggestions", {"employee_id": "100001", "current_url": "/sops", "page_context": {"title": "SOP"}}),
        ("dictionary_terms", {"employee_id": "100001", "query": "단면검사", "scope": "all", "limit": 5}),
        ("agent_memory_search", {"employee_id": "100001", "query": "선호", "include_archived": False, "limit": 3}),
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
        "/api/agents/boi-wiki/suggestions",
        "/api/dictionary/terms",
        "/api/agents/boi-wiki/memory",
        "/api/agents/boi-wiki/manual-handoffs/complete",
    ]
    assert calls[-1]["payload"]["user_confirmed"] is True


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


def test_boi_wiki_mcp_bridge_requires_confirmation_for_write_tools(mcp_module):
    client = TestClient(mcp_module.app)
    for tool, arguments in [
        ("workflow_start", {"workflow_key": "equipment-anomaly"}),
        ("event_type_draft_create", {"event_type": "quality.forecast.requested.v1"}),
        ("event_type_draft_apply", {"draft_id": "event-type-test"}),
        ("source_apply", {"path": "data/boi/public/test.md", "base_sha256": "x", "proposed_content": "x"}),
        ("doc_body_apply", {"boi_id": "boi:public:test", "base_sha256": "x", "proposed_body": "x"}),
        ("promotion_submit", {"title": "x", "body": "x", "source_refs": []}),
    ]:
        response = client.post(
            "/api/mcp/call",
            headers={"x-service-token": "test-service-token"},
            json={"server": {"name": "boi-wiki-mcp"}, "tool": tool, "arguments": arguments},
        )
        assert response.status_code == 400
        assert "user_confirmed=true" in response.json()["detail"]


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
            "tools": 26,
            "resources": 0,
            "resource_templates": 5,
            "prompts": 5,
            "tool_names": [
                "boi_search",
                "boi_get",
                "workflow_status",
                "boi_agent_chat",
                "ontology_search",
                "agent_inbox",
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
    )

    exit_code = asyncio.run(script.main_async(args))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "boi_search" in output
    assert "workflow_status" in output
    assert "boi_agent_chat" in output
    assert "ontology_search" in output
    assert "agent_inbox" in output
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


def test_check_boi_wiki_mcp_uses_stateless_json_protocol_when_client_stream_breaks(monkeypatch):
    import scripts.check_boi_wiki_mcp as script

    async def broken_client(*args, **kwargs):
        raise RuntimeError("stream client broke before tools/list")

    async def stateless_json(*args, **kwargs):
        return {
            "tools": 22,
            "resources": 0,
            "resource_templates": 5,
            "prompts": 5,
            "tool_names": ["boi_agent_chat", "ontology_search", "agent_inbox"],
            "resource_template_uris": ["boi://search/ontology/{query}"],
            "prompt_names": ["create_sop_from_source"],
        }

    monkeypatch.setattr(script, "check_protocol_mcp_client", broken_client)
    monkeypatch.setattr(script, "check_protocol_stateless_json", stateless_json)

    result = asyncio.run(script.check_protocol("http://localhost:8200/mcp", include_details=True))

    assert result["tools"] == 22
    assert result["resource_templates"] == 5
    assert result["prompts"] == 5
    assert result["transport_mode"] == "stateless_json_rpc"
    assert "stream client broke" in result["client_warning"]
