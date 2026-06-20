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
    assert body["capabilities"]["tools"] == 14
    assert body["capability_lists"]["tools"][0]["name"] == "boi_search"
    tool_names = [item["name"] for item in body["capability_lists"]["tools"]]
    assert "source_preview" in tool_names
    assert "source_apply" in tool_names
    assert "doc_body_preview" in tool_names
    assert "doc_body_apply" in tool_names
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
    assert "Tools" in body and "14" in body
    assert "Resource templates" in body and "4" in body
    assert "Prompts" in body and "5" in body
    assert "boi_search" in body
    assert "workflow_status" in body
    assert "action_invoke" in body
    assert "source_apply" in body
    assert "doc_body_apply" in body
    assert "promotion_submit" in body
    assert "boi://docs/{boi_id}" in body
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


def test_check_boi_wiki_mcp_details_and_client_checklist(monkeypatch, capsys):
    import scripts.check_boi_wiki_mcp as script

    async def fake_check_protocol(*args, **kwargs):
        return {
            "tools": 14,
            "resources": 0,
            "resource_templates": 4,
            "prompts": 5,
            "tool_names": [
                "boi_search",
                "boi_get",
                "workflow_status",
                "action_invoke",
                "source_preview",
                "source_apply",
                "doc_body_preview",
                "doc_body_apply",
                "promotion_submit",
                "promotion_status",
            ],
            "resource_template_uris": ["boi://docs/{boi_id}"],
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
    assert "source_apply" in output
    assert "doc_body_apply" in output
    assert "promotion_submit" in output
    assert "Codex" in output
    assert "Claude Desktop" in output
    assert "Cursor" in output
    assert "http://localhost:8200/mcp" in output
    assert "folder_tree" not in output
