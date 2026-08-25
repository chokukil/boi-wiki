from __future__ import annotations

import hashlib
import importlib
import sys

from fastapi.testclient import TestClient
import httpx
import pytest


SCIENCE_TOOLS = {
    "science_interpret",
    "science_aliases_detect",
    "science_claim_submit",
    "science_interpretation_confirm",
    "science_verify_claim",
    "science_verify_document",
    "science_evidence_get",
    "science_report_get",
    "science_report_export",
    "science_proposal_create",
    "science_source_validate",
    "science_evidence_validate",
    "science_knowledge_validate",
    "science_rule_qualify",
    "science_release_validate",
    "science_release_activate",
    "science_release_withdraw",
}


@pytest.fixture()
def mcp_module(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    monkeypatch.setenv("DEFAULT_EMPLOYEE_ID", "100001")
    sys.modules.pop("boi_wiki_mcp.app.main", None)
    return importlib.import_module("boi_wiki_mcp.app.main")


@pytest.fixture()
def authenticated_science_user(mcp_module):
    token = mcp_module.MCP_CALLER_BEARER_TOKEN.set("test-user-bearer")
    try:
        yield
    finally:
        mcp_module.MCP_CALLER_BEARER_TOKEN.reset(token)


def test_science_tools_are_discoverable_as_one_group(mcp_module):
    health = TestClient(mcp_module.app).get("/health").json()
    tool_names = {item["name"] for item in health["capability_lists"]["tools"]}
    science_group = next(
        group for group in health["tool_groups"] if group["name"] == "Science Verifier"
    )

    assert SCIENCE_TOOLS <= tool_names
    assert {item["name"] for item in science_group["tools"]} == SCIENCE_TOOLS


@pytest.mark.asyncio
async def test_science_tools_require_an_authenticated_user_bearer(mcp_module):
    with pytest.raises(PermissionError, match="interactive_user_identity_required"):
        await mcp_module.science_interpret(
            "원문", request_id="r-1", idempotency_key="idem-1"
        )


@pytest.mark.asyncio
async def test_verification_tools_forward_stored_identity_contract_unchanged(
    mcp_module, monkeypatch, authenticated_science_user
):
    calls: list[tuple[str, str, dict]] = []
    release_selection = {"foundation": "sci-release:0.1.0", "domains": []}

    async def fake_post(path, **kwargs):
        calls.append(("POST", path, kwargs))
        return {"verdict": "INSUFFICIENT_INFORMATION", "path": path}

    async def fake_get(path, **kwargs):
        calls.append(("GET", path, kwargs))
        return {"path": path}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_get)

    await mcp_module.science_aliases_detect(
        document="원문", request_id="aliases-1"
    )
    await mcp_module.science_claim_submit(
        candidate={"normalized_claim": {"predicate": "increases"}},
        client_kind="codex",
        idempotency_key="claim-submit-1",
        document="원문",
    )
    await mcp_module.science_interpret(
        "원문", request_id="r-1", idempotency_key="idem-1"
    )
    await mcp_module.science_interpretation_confirm(
        "i-1", ["c-1"], user_confirmed=True, idempotency_key="idem-2"
    )
    await mcp_module.science_verify_claim("i-2", "c-1", release_selection)
    await mcp_module.science_verify_document(
        "i-2", release_selection, idempotency_key="idem-3"
    )
    await mcp_module.science_evidence_get("e-1")
    await mcp_module.science_report_get("report-1")

    assert [(method, path) for method, path, _ in calls] == [
        ("POST", "/api/science/aliases/detect"),
        ("POST", "/api/science/claims/submit"),
        ("POST", "/api/science/interpret"),
        ("POST", "/api/science/interpretations/i-1/confirm"),
        ("POST", "/api/science/claims/c-1/verify"),
        ("POST", "/api/science/verify-document"),
        ("GET", "/api/science/evidence/e-1"),
        ("GET", "/api/science/reports/report-1"),
    ]
    for _method, _path, kwargs in calls:
        assert kwargs["bearer_token"] == "test-user-bearer"
        assert kwargs.get("employee_id") is None
    assert calls[0][2]["payload"] == {
        "document": "원문",
        "request_id": "aliases-1",
    }
    assert calls[1][2]["payload"] == {
        "document": "원문",
        "client_kind": "codex",
        "candidate": {"normalized_claim": {"predicate": "increases"}},
        "idempotency_key": "claim-submit-1",
    }
    assert calls[4][2]["payload"] == {
        "interpretation_id": "i-2",
        "release_selection": release_selection,
    }
    assert calls[5][2]["payload"] == {
        "interpretation_id": "i-2",
        "release_selection": release_selection,
        "idempotency_key": "idem-3",
    }


@pytest.mark.asyncio
async def test_equation_claim_candidate_crosses_mcp_without_authority_rewriting(
    mcp_module, monkeypatch, authenticated_science_user
):
    captured: dict = {}
    formula_candidate = {
        "formula_span": {
            "start": 0,
            "end": 7,
            "exact": "V = I R",
            "prefix": "",
            "suffix": "",
        },
        "semantic_expression": {
            "schema_version": "science-expression/0.1",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": {"op": "variable", "variable_id": "voltage"},
                "right": {
                    "op": "multiply",
                    "left": {"op": "variable", "variable_id": "current"},
                    "right": {"op": "variable", "variable_id": "resistance"},
                },
            },
        },
        "proposed_equation_id": "sci:equation:ohms-law",
        "proposed_equation_digest": "sha256:" + "a" * 64,
        "symbol_candidates": [],
        "condition_candidates": [],
        "sign_convention_candidate": None,
        "ontology_refs": [],
    }
    candidate = {
        "normalized_claim": {"predicate": "equation"},
        "formula_candidates": [formula_candidate],
    }

    async def fake_post(path, **kwargs):
        captured.update({"path": path, **kwargs})
        return {"interpretation_id": "submitted"}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)

    await mcp_module.science_claim_submit(
        candidate=candidate,
        client_kind="codex",
        idempotency_key="equation-claim-mcp",
        document="V = I R",
    )

    assert captured["path"] == "/api/science/claims/submit"
    assert captured["payload"]["candidate"] == candidate


def test_authenticated_bridge_forwards_external_claim_submission(
    mcp_module, monkeypatch
):
    captured: dict = {}

    async def fake_post(path, **kwargs):
        captured.update({"path": path, **kwargs})
        return {"interpretation_id": "submitted"}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={
            "x-service-token": "test-service-token",
            "authorization": "Bearer real-user-token",
        },
        json={
            "tool": "science_claim_submit",
            "arguments": {
                "document": "원문",
                "client_kind": "claude",
                "candidate": {"normalized_claim": {"predicate": "increases"}},
                "supersedes_claim_id": "sci-claim:old",
                "idempotency_key": "claim-submit-bridge",
            },
        },
    )

    assert response.status_code == 200
    assert captured["path"] == "/api/science/claims/submit"
    assert captured["bearer_token"] == "real-user-token"
    assert captured["payload"] == {
        "document": "원문",
        "client_kind": "claude",
        "candidate": {"normalized_claim": {"predicate": "increases"}},
        "idempotency_key": "claim-submit-bridge",
        "supersedes_claim_id": "sci-claim:old",
    }


@pytest.mark.asyncio
async def test_export_preserves_report_digest_and_distinct_content_hash(
    mcp_module, monkeypatch
):
    content = b"%PDF-1.4"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            assert kwargs["headers"] == {"authorization": "Bearer user-token"}
            assert "employee_id" not in kwargs["params"]
            return httpx.Response(
                200,
                content=content,
                headers={
                    "content-type": "application/pdf",
                    "x-science-report-digest": "sha256:" + "a" * 64,
                    "content-disposition": 'attachment; filename="report.pdf"',
                },
            )

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", FakeClient)

    result = await mcp_module.api_get_bytes(
        "/api/science/reports/report-1/export",
        params={"format": "pdf"},
        bearer_token="user-token",
    )

    assert result["report_digest"] == "sha256:" + "a" * 64
    assert result["content_sha256"] == hashlib.sha256(content).hexdigest()
    assert result["content_type"] == "application/pdf"
    assert result["content_disposition"] == 'attachment; filename="report.pdf"'
    assert "sha256" not in result


@pytest.mark.asyncio
async def test_governance_tools_preserve_exact_requests_and_user_identity(
    mcp_module, monkeypatch, authenticated_science_user
):
    calls: list[tuple[str, dict]] = []
    qualification = {
        "rule_id": "r-1",
        "rule_digest": "sha256:" + "1" * 64,
        "case_set_digest": "sha256:" + "2" * 64,
        "case_ids": ["case-1"],
    }

    async def fake_post(path, **kwargs):
        calls.append((path, kwargs))
        return {"ok": True, "path": path}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)

    await mcp_module.science_source_validate({"source_id": "s-1"})
    await mcp_module.science_evidence_validate({"evidence_id": "e-1"})
    await mcp_module.science_knowledge_validate({"knowledge_id": "k-1"})
    await mcp_module.science_rule_qualify("r-1", qualification)
    await mcp_module.science_release_validate(
        "rel-1", "sha256:" + "3" * 64, "sha256:" + "4" * 64
    )
    await mcp_module.science_proposal_create(
        {"kind": "alias"},
        request_digest="sha256:" + "5" * 64,
        idempotency_key="idem-p",
        user_confirmed=True,
    )
    await mcp_module.science_release_activate(
        "rel-1",
        "sha256:" + "3" * 64,
        request_digest="sha256:" + "6" * 64,
        idempotency_key="idem-a",
        user_confirmed=True,
    )
    await mcp_module.science_release_withdraw(
        "rel-1",
        "sha256:" + "3" * 64,
        request_digest="sha256:" + "7" * 64,
        idempotency_key="idem-w",
        user_confirmed=True,
    )

    assert [path for path, _ in calls] == [
        "/api/science/admin/sources/validate",
        "/api/science/admin/evidence/validate",
        "/api/science/admin/knowledge/validate",
        "/api/science/admin/rules/r-1/qualify",
        "/api/science/admin/releases/validate",
        "/api/science/proposals",
        "/api/science/admin/releases/rel-1/activate",
        "/api/science/admin/releases/rel-1/withdraw",
    ]
    assert calls[3][1]["payload"] == qualification
    assert calls[4][1]["payload"] == {
        "release_id": "rel-1",
        "release_digest": "sha256:" + "3" * 64,
        "holdout_manifest_digest": "sha256:" + "4" * 64,
    }
    for path, kwargs in calls:
        assert kwargs["bearer_token"] == "test-user-bearer", path
        assert kwargs.get("employee_id") is None, path
    for path, kwargs in calls[-3:]:
        assert kwargs["payload"]["user_confirmed"] is True, path
        assert kwargs["payload"]["request_digest"].startswith("sha256:"), path
        assert kwargs["payload"]["idempotency_key"], path


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "science_interpretation_confirm",
            {
                "interpretation_id": "i-1",
                "claim_ids": ["c-1"],
                "idempotency_key": "idem-c",
            },
        ),
        (
            "science_proposal_create",
            {
                "proposal": {"kind": "alias"},
                "request_digest": "sha256:" + "5" * 64,
                "idempotency_key": "idem-p",
            },
        ),
    ],
)
def test_authenticated_bridge_requires_explicit_confirmation(
    mcp_module, tool, args
):
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={
            "x-service-token": "test-service-token",
            "authorization": "Bearer test-user-bearer",
        },
        json={"tool": tool, "arguments": args},
    )

    assert response.status_code == 400
    assert "user_confirmed=true" in response.json()["detail"]


@pytest.mark.parametrize(
    "tool",
    [
        "science_interpret",
        "science_interpretation_confirm",
        "science_proposal_create",
        "science_release_activate",
        "science_release_withdraw",
    ],
)
def test_service_token_only_bridge_cannot_use_science_identity(
    mcp_module, tool
):
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "tool": tool,
            "arguments": {
                "employee_id": "admin-claimed-by-client",
                "user_confirmed": True,
            },
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "interactive_user_identity_required"


def test_authenticated_bridge_ignores_forged_employee_and_forwards_bearer(
    mcp_module, monkeypatch
):
    captured: dict = {}

    async def fake_post(path, **kwargs):
        captured.update({"path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={
            "x-service-token": "test-service-token",
            "authorization": "Bearer real-user-token",
        },
        json={
            "tool": "science_verify_claim",
            "arguments": {
                "employee_id": "forged-user",
                "interpretation_id": "i-1",
                "claim_id": "c-1",
                "release_selection": {"foundation": "sci-release:0.1.0"},
            },
        },
    )

    assert response.status_code == 200
    assert captured["bearer_token"] == "real-user-token"
    assert captured.get("employee_id") is None
    assert captured["payload"]["interpretation_id"] == "i-1"
