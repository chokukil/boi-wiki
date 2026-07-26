from __future__ import annotations

import inspect
import json
import threading
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from boi_api.app.agent_playground_credentials import (
    PlaygroundCredentialService,
    TokenCreateRequest,
)
from boi_api.app.auth import AuthIdentity
from boi_wiki_mcp.app import v2 as mcp_v2


def identity(employee_id: str, roles: list[str]) -> AuthIdentity:
    return AuthIdentity(
        employee_id=employee_id,
        display_name=f"User {employee_id}",
        teams=["platform"],
        roles=roles,
        auth_source="test",
    )


def test_sqlite_run_token_is_consumed_exactly_once(tmp_path: Path):
    current = identity(
        "100002",
        ["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    service = PlaygroundCredentialService(
        tmp_path,
        hash_secret="mainline-token-hash-secret",
        identity_provider=lambda _employee_id: current,
    )
    issued = service.create_run_token(
        current,
        action_key="action.shared",
        flow_id="flow-exact",
        trace_id="trace-exact",
        scopes=["boi.read", "boi.draft"],
        ttl_seconds=60,
    )
    results: list[bool] = []

    def consume() -> None:
        results.append(service.consume_run_token(str(issued["token_id"])))

    workers = [threading.Thread(target=consume) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert results.count(True) == 1
    assert results.count(False) == 7
    assert service.authenticate_run_token(str(issued["token"])) is None
    assert service.store.path == tmp_path / "agent-playground" / "credentials.sqlite3"


def test_token_api_never_returns_hash_and_rejects_scope_escalation(boi_app_module):
    client = TestClient(boi_app_module.app)
    created = client.post(
        "/api/v2/tokens?employee_id=100002",
        json={
            "name": "Agent Playground",
            "scopes": ["boi.read", "boi.draft"],
            "expires_in_days": None,
        },
    )
    assert created.status_code == 200
    issued = created.json()["token"]
    assert issued["token"].startswith("boi_pat_")
    assert issued["expires_at"] is None
    assert "token_hash" not in json.dumps(created.json())

    listed = client.get("/api/v2/tokens?employee_id=100002")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["token_id"] == issued["token_id"]
    assert issued["token"] not in listed.text

    denied = client.post(
        "/api/v2/tokens?employee_id=100003",
        json={
            "name": "Escalation",
            "scopes": ["boi.read", "boi.draft"],
            "expires_in_days": None,
        },
    )
    assert denied.status_code == 403


def test_minimal_mcp_v2_contract_has_no_employee_id():
    assert {item["name"] for item in mcp_v2.MCP_V2_TOOLS} == {
        "boi_search",
        "boi_get",
        "boi_plan",
        "boi_confirm",
    }
    for tool in (mcp_v2.boi_search, mcp_v2.boi_get, mcp_v2.boi_plan, mcp_v2.boi_confirm):
        assert "employee_id" not in inspect.signature(tool).parameters


def test_pat_driven_wiki_preview_and_private_draft_are_owner_scoped(boi_app_module):
    client = TestClient(boi_app_module.app)
    issued = client.post(
        "/api/v2/tokens?employee_id=100002",
        json={
            "name": "Wiki facade",
            "scopes": ["boi.read", "boi.draft"],
            "expires_in_days": None,
        },
    ).json()["token"]
    headers = {
        "x-service-token": boi_app_module.SERVICE_TOKEN,
        "Authorization": f"Bearer {issued['token']}",
    }

    search = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "Langflow", "view": "ranked", "limit": 5},
    )
    assert search.status_code == 200
    assert search.json()["count"] >= 1
    assert "employee_id" not in search.json()

    ontology = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={
            "view": "workflow",
            "source_ref": "boi:public:sop:equipment-abnormal-response",
            "depth": 2,
            "limit": 40,
        },
    )
    assert ontology.status_code == 200
    graph = ontology.json()
    assert graph["resolved_source_id"] == "public/sop/equipment-abnormal-response"
    assert graph["ontology_status"] == "grounded"
    assert graph["edges"]
    assert all(edge["payload"]["provenance"] for edge in graph["edges"])
    assert all(edge["payload"]["source_refs"] for edge in graph["edges"])

    plan = client.post(
        "/internal/agent-playground/wiki/plans",
        headers=headers,
        json={
            "capability_id": "knowledge.draft",
            "goal": "검증 결과를 개인 초안으로 저장",
            "page_ref": "/playground",
            "input": {
                "title": "Playground private draft",
                "body": "근거를 바탕으로 작성한 검증 결과",
                "source_refs": [{"ref": "boi:public:boi-wiki-manual:index"}],
                "provenance": {"flow_id": "flow-exact", "trace_id": "trace-exact"},
            },
        },
    )
    assert plan.status_code == 200
    assert plan.json()["production_changed"] is False
    private_before = list((boi_app_module.DATA_ROOT / "private" / "100002").glob("*.md"))

    confirmed = client.post(
        f"/internal/agent-playground/wiki/plans/{plan.json()['plan_id']}/confirm",
        headers=headers,
        json={"reason": "private_draft selected"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["domain_ref"].startswith("boi:private:100002:")
    private_after = list((boi_app_module.DATA_ROOT / "private" / "100002").glob("*.md"))
    assert len(private_after) == len(private_before) + 1
    assert not list((boi_app_module.DATA_ROOT / "private" / "100001").glob("*Playground*"))


def test_playground_and_manual_pages_hide_pet_assets(boi_app_module):
    client = TestClient(boi_app_module.app)
    pages = [
        client.get("/playground?employee_id=100002"),
        client.get(
            "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding"
            "?employee_id=100002"
        ),
        client.get(
            "/docs/boi:public:boi-wiki-manual:operations:agent-playground-operator-runbook"
            "?employee_id=100002"
        ),
    ]
    assert [page.status_code for page in pages] == [200, 200, 200]
    for page in pages:
        assert "pet_agent.js" not in page.text
        assert "boi-pet-agent" not in page.text
        assert "pet-agent-avatar" not in page.text


def test_connector_neutral_action_catalog_has_interactive_preview(boi_app_module):
    client = TestClient(boi_app_module.app)
    page = client.get("/actions?employee_id=100002")
    assert page.status_code == 200
    assert "data-action-catalog" in page.text
    assert "action_catalog.js" in page.text

    catalog = client.get("/api/actions/catalog").json()["items"]
    action_key = str(catalog[0]["action_key"])
    detail = client.get(
        f"/api/actions/catalog/{quote(action_key, safe='')}?employee_id=100002"
    )
    assert detail.status_code == 200
    action = detail.json()["action"]
    assert action["action_key"] == action_key
    assert action["connector_kind"]
    payload = {
        item["name"]: ["sample"] if item["type"] == "array" else "sample"
        for item in action["input_fields"]
    }
    preview = client.post(
        f"/api/actions/catalog/{quote(action_key, safe='')}/preview?employee_id=100002",
        json={"payload": payload},
    )
    assert preview.status_code == 200
    assert preview.json()["state"] == "ready"


def test_mainline_handoff_docs_do_not_point_to_stale_integration_evidence():
    root = Path(__file__).resolve().parents[1]
    paths = (
        root / "docs" / "AGENT_PLAYGROUND_INTEGRATION.md",
        root / "validation" / "agent-hub" / "README.md",
        root / "validation" / "agent-hub" / "COMPLETION_AUDIT.md",
        root / "validation" / "agent-hub" / "CORPORATE_SSO_HANDOFF.md",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "BoI SSO: `http://localhost:28002`" not in combined
    assert "Langflow 1.11: `http://localhost:7861`" not in combined
    assert "/tmp/boi-agent-playground-validation/evidence" not in combined
    assert "CHERRY_PICK_ORDER.txt" not in combined
    assert "`Principal(employee_id" not in combined
    assert "codex/agent-playground-mainline" in combined
    assert "AuthIdentity" in combined
    assert "artifacts/agent-playground-handoff/<run_id>-mainline-final-audit/" in combined


def test_mainline_handoff_builder_runs_requirement_audit():
    root = Path(__file__).resolve().parents[1]
    audit = root / "scripts" / "audit_agent_playground_mainline_completion.py"
    builder = (root / "scripts" / "build_agent_playground_handoff.py").read_text(
        encoding="utf-8"
    )
    assert audit.is_file()
    assert "mainline-completion-audit.json" in builder
    assert "--live-audit" in builder
    assert "--connector-regression-log" in builder
