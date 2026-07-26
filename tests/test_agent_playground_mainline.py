from __future__ import annotations

import inspect
import json
import threading
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

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
        deployment_id="deployment-exact",
        endpoint_id="endpoint-exact",
        project_id="project-exact",
        flow_id="flow-exact",
        trace_id="trace-exact",
        execution_id="execution-exact",
        allowed_capabilities=["boi.search", "boi.get", "knowledge.draft"],
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


def test_run_token_audience_is_enforced_without_consuming_normal_multi_call_use(tmp_path: Path):
    current = identity(
        "100002",
        ["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    service = PlaygroundCredentialService(
        tmp_path,
        hash_secret="audience-token-hash-secret",
        identity_provider=lambda _employee_id: current,
    )
    issued = service.create_run_token(
        current,
        action_key="action.shared",
        deployment_id="deployment-exact",
        endpoint_id="endpoint-exact",
        project_id="project-exact",
        flow_id="flow-exact",
        trace_id="trace-exact",
        execution_id="execution-exact",
        allowed_capabilities=["boi.search", "boi.get", "knowledge.draft"],
        scopes=["boi.read", "boi.draft"],
        ttl_seconds=60,
    )
    authentication = service.authenticate_run_token(str(issued["token"]))
    assert authentication is not None
    audience = {
        "action_key": "action.shared",
        "deployment_id": "deployment-exact",
        "endpoint_id": "endpoint-exact",
        "project_id": "project-exact",
        "flow_id": "flow-exact",
        "trace_id": "trace-exact",
        "execution_id": "execution-exact",
    }
    authentication.require_audience(**audience, capability="boi.search")
    authentication.require_audience(**audience, capability="boi.get")
    authentication.require_audience(**audience, capability="knowledge.draft")

    for field in audience:
        wrong = {**audience, field: f"wrong-{field}"}
        with pytest.raises(HTTPException) as exc:
            authentication.require_audience(**wrong, capability="boi.search")
        assert exc.value.status_code == 403
        assert field in exc.value.detail["fields"]
    with pytest.raises(HTTPException) as capability_error:
        authentication.require_audience(**audience, capability="boi.publish")
    assert capability_error.value.status_code == 403

    assert service.authenticate_run_token(str(issued["token"])) is not None
    assert service.consume_run_token(str(issued["token_id"])) is True
    assert service.authenticate_run_token(str(issued["token"])) is None


def test_run_token_audience_is_enforced_by_wiki_facade_routes(boi_app_module):
    identity_value = identity(
        "100002",
        ["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    issued = boi_app_module.AGENT_PLAYGROUND_CREDENTIALS.create_run_token(
        identity_value,
        action_key="action.shared",
        deployment_id="deployment-exact",
        endpoint_id="endpoint-exact",
        project_id="project-exact",
        flow_id="flow-exact",
        trace_id="trace-exact",
        execution_id="execution-exact",
        allowed_capabilities=["boi.search", "boi.get"],
        scopes=["boi.read"],
        ttl_seconds=60,
    )
    client = TestClient(boi_app_module.app)
    headers = {
        "x-service-token": boi_app_module.SERVICE_TOKEN,
        "Authorization": f"Bearer {issued['token']}",
        "X-BOI-Action-Key": "action.shared",
        "X-BOI-Deployment-ID": "deployment-exact",
        "X-BOI-Endpoint-ID": "endpoint-exact",
        "X-BOI-Project-ID": "project-exact",
        "X-BOI-Flow-ID": "flow-exact",
        "X-BOI-Trace-ID": "trace-exact",
        "X-BOI-Execution-ID": "execution-exact",
    }
    first = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "Langflow", "view": "ranked"},
    )
    second = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "Agent Playground", "view": "ranked"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    wrong_flow = client.get(
        "/internal/agent-playground/wiki/search",
        headers={**headers, "X-BOI-Flow-ID": "flow-other"},
        params={"q": "Langflow", "view": "ranked"},
    )
    assert wrong_flow.status_code == 403
    assert wrong_flow.json()["detail"]["code"] == "run_token_audience_mismatch"

    assert boi_app_module.AGENT_PLAYGROUND_CREDENTIALS.consume_run_token(
        str(issued["token_id"])
    )
    consumed = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "Langflow", "view": "ranked"},
    )
    assert consumed.status_code == 401


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


def test_pat_scopes_follow_current_hcp_role_reduction(tmp_path: Path):
    current = {
        "identity": identity(
            "100002",
            ["boi.viewer", "boi.editor", "boi.action_invoker"],
        )
    }
    service = PlaygroundCredentialService(
        tmp_path,
        hash_secret="mainline-token-hash-secret",
        identity_provider=lambda _employee_id: current["identity"],
    )
    created = service.create(
        current["identity"],
        TokenCreateRequest(
            name="role shrink",
            scopes=["boi.read", "boi.draft"],
        ),
    )
    authenticated = service.authenticate(str(created["token"]))
    assert authenticated is not None
    assert authenticated.scopes == ("boi.draft", "boi.read")

    current["identity"] = identity("100002", ["boi.viewer"])
    reduced = service.authenticate(str(created["token"]))
    assert reduced is not None
    assert reduced.scopes == ("boi.read",)
    with pytest.raises(HTTPException) as exc:
        reduced.require_scope("boi.draft")
    assert exc.value.status_code == 403


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
    assert graph["resolved_source_id"] == "workflow:equipment-anomaly-response"
    assert graph["ontology_status"] == "grounded_typed_relationships"
    assert graph["edges"]
    assert all(edge["payload"]["provenance"] for edge in graph["edges"])
    assert all(edge["payload"]["source_refs"] for edge in graph["edges"])
    assert all(
        edge["payload"]["provenance"] != "okf_markdown_link"
        for edge in graph["edges"]
    )

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


def test_wiki_search_resolves_real_task_context_and_distinct_typed_relationships(
    boi_app_module,
):
    client = TestClient(boi_app_module.app)
    issued = client.post(
        "/api/v2/tokens?employee_id=100002",
        json={
            "name": "Task context",
            "scopes": ["boi.read"],
            "expires_in_days": None,
        },
    ).json()["token"]
    headers = {
        "x-service-token": boi_app_module.SERVICE_TOKEN,
        "Authorization": f"Bearer {issued['token']}",
    }
    trace_id = "trace-agent-playground-real-task"
    event_id = "evt-agent-playground-real-task"
    request_id = "act-agent-playground-real-task"
    action_key = "langflow.equipment.stage_analysis"
    boi_app_module.append_event_log(
        status="processed",
        event={
            "event_id": event_id,
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "payload": {"equipment_id": "EQ-REAL-TASK"},
        },
    )
    boi_app_module.append_action_log_row(
        {
            "request_id": request_id,
            "employee_id": "100002",
            "trace_id": trace_id,
            "event_id": event_id,
            "event_type": "root_cause.analysis.requested.v1",
            "action_key": action_key,
            "status": "manual_required",
            "summary": "원인 분석 근거 확인 필요",
            "logged_at": boi_app_module.now_iso(),
        }
    )

    search = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={
            "q": "이 Task의 근거를 정리해줘",
            "task_ref": f"task:{request_id}",
            "trace_id": trace_id,
            "event_id": event_id,
            "action_key": action_key,
        },
    )
    assert search.status_code == 200
    body = search.json()
    context = body["context_pack"]
    assert body["context_profile"] == "sop_task_execution"
    assert body["retrieval_strategy"] == "task_context_ontology_hybrid"
    assert context["task"]["task_id"] == f"task:{request_id}"
    assert context["task"]["action_key"] == action_key
    assert context["sop_stage"]["sop_stage_id"] == "analyze"
    assert context["sop_stage"]["workflow_definition_key"] == "equipment-anomaly-response"
    assert context["trace_context"]["trace_id"] == trace_id

    public_task_ref = boi_app_module.inbox_task_public_ref(
        "100002",
        f"task:{request_id}",
    )
    public_ref_search = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={
            "q": "UI에서 선택한 이 Task의 온톨로지 근거를 정리해줘",
            "task_ref": public_task_ref,
            "trace_id": trace_id,
            "event_id": event_id,
            "action_key": action_key,
        },
    )
    assert public_ref_search.status_code == 200
    public_ref_body = public_ref_search.json()
    assert public_ref_body["context_profile"] == "sop_task_execution"
    assert public_ref_body["retrieval_strategy"] == "task_context_ontology_hybrid"
    assert public_ref_body["task_ref"] == public_task_ref
    assert public_ref_body["context_pack"]["task"]["task_id"] == f"task:{request_id}"

    relation_sets = {}
    for view in ("workflow", "responsibility", "lineage", "impact"):
        response = client.get(
            "/internal/agent-playground/wiki/search",
            headers=headers,
            params={
                "view": view,
                "source_ref": f"task:{request_id}",
                "limit": 100,
            },
        )
        assert response.status_code == 200
        graph = response.json()
        relation_sets[view] = {edge["relation"] for edge in graph["edges"]}
        if graph["ontology_status"] == "grounded_typed_relationships":
            assert all(
                edge["payload"]["provenance"] != "okf_markdown_link"
                for edge in graph["edges"]
            )
    assert relation_sets["workflow"] != relation_sets["responsibility"]
    assert relation_sets["workflow"] != relation_sets["impact"]
    assert "owned_by" in relation_sets["responsibility"]

    missing = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "근거", "task_ref": "task:does-not-exist"},
    )
    assert missing.status_code == 404
    inaccessible_public_ref = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={"q": "근거", "task_ref": "inbox-ref-not-accessible"},
    )
    assert inaccessible_public_ref.status_code == 404

    ordinary = client.get(
        "/internal/agent-playground/wiki/search",
        headers=headers,
        params={
            "q": "일반 Wiki 질문에 SOP를 만들어내지 마",
            "trace_id": "trace-ordinary-action-execution",
            "event_id": "evt-ordinary-action-execution",
            "action_key": "agent-playground.ordinary",
        },
    )
    assert ordinary.status_code == 200
    assert ordinary.json()["context_profile"] == "knowledge_lookup"
    assert ordinary.json()["retrieval_strategy"] == "ontology_hybrid"
    assert ordinary.json()["context_pack"] == {}


def test_wiki_search_reports_only_aggregate_acl_exclusion(boi_app_module):
    hidden_root = boi_app_module.DATA_ROOT / "private" / "100001"
    hidden_root.mkdir(parents=True, exist_ok=True)
    hidden_path = hidden_root / "acl-excluded-agent-playground-proof.md"
    hidden_ref = "boi:private:100001:acl-excluded-agent-playground-proof"
    hidden_path.write_text(
        "---\n"
        f"boi_id: {hidden_ref}\n"
        "title: QuasarNeedle restricted evidence\n"
        "visibility: private\n"
        "owner_employee_id: '100001'\n"
        "---\n\n"
        "QuasarNeedle is private evidence and must never be disclosed.\n",
        encoding="utf-8",
    )
    boi_app_module._DOCS_CACHE["signature"] = None
    try:
        client = TestClient(boi_app_module.app)
        issued = client.post(
            "/api/v2/tokens?employee_id=100002",
            json={
                "name": "ACL aggregate",
                "scopes": ["boi.read"],
                "expires_in_days": None,
            },
        ).json()["token"]
        response = client.get(
            "/internal/agent-playground/wiki/search",
            headers={
                "x-service-token": boi_app_module.SERVICE_TOKEN,
                "Authorization": f"Bearer {issued['token']}",
            },
            params={"q": "QuasarNeedle", "limit": 10},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["permission_excluded_count"] == 1
        serialized = json.dumps(body, ensure_ascii=False)
        assert hidden_ref not in serialized
        assert "restricted evidence" not in serialized
    finally:
        hidden_path.unlink(missing_ok=True)
        boi_app_module._DOCS_CACHE["signature"] = None


def test_playground_and_manual_pages_hide_pet_assets(boi_app_module):
    client = TestClient(boi_app_module.app)
    pages = [
        client.get("/playground?employee_id=100002"),
        client.get(
            "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding"
            "?employee_id=100002"
        ),
        client.get(
            "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-my-flow-deploy"
            "?employee_id=100002"
        ),
        client.get(
            "/docs/boi:public:boi-wiki-manual:langflow:agent-playground-shared-assets"
            "?employee_id=100002"
        ),
        client.get(
            "/docs/boi:public:boi-wiki-manual:operations:agent-playground-operator-runbook"
            "?employee_id=100002"
        ),
        client.get(
            "/docs/boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary"
            "?employee_id=100002"
        ),
    ]
    assert [page.status_code for page in pages] == [200, 200, 200, 200, 200, 200]
    for page in pages:
        assert "pet_agent.js" not in page.text
        assert "boi-pet-agent" not in page.text
        assert "pet-agent-avatar" not in page.text
    playground = pages[0].text
    assert playground.count("data-workbench-step=") == 4
    assert "data-task-select" in playground
    assert "data-action-scope" in playground
    assert "내 Flow 배포하기" in playground
    assert "공유 자산 가져오기" in playground
    assert "data-next-action" in playground
    assert "boi_search" not in playground
    assert "Ontology" in playground
    assert "boi_search" not in pages[1].text


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


def test_team_action_catalog_visibility_uses_current_hcp_team(boi_app_module):
    action = {
        "action_key": "team.shared.action",
        "scope": "team",
        "team_id": "aix-tf",
        "owner_employee_id": "100002",
    }
    owner = AuthIdentity(
        employee_id="100002",
        display_name="Owner",
        teams=["aix-tf"],
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
        auth_source="hcp",
    )
    same_team_caller = AuthIdentity(
        employee_id="100001",
        display_name="Same team caller",
        teams=["aix-tf", "platform"],
        roles=["boi.viewer", "boi.action_invoker"],
        auth_source="hcp",
    )
    other_team_viewer = AuthIdentity(
        employee_id="100003",
        display_name="Other team viewer",
        teams=["platform"],
        roles=["boi.viewer"],
        auth_source="hcp",
    )

    assert boi_app_module.action_catalog_item_visible(action, owner)
    assert boi_app_module.action_catalog_item_visible(action, same_team_caller)
    assert not boi_app_module.action_catalog_item_visible(action, other_team_viewer)


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
