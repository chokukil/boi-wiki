from __future__ import annotations

import importlib
import sys

from fastapi.testclient import TestClient
import pytest


SCIENCE_TOOLS = {
    "science_interpret",
    "science_interpretation_confirm",
    "science_verify_claim",
    "science_verify_document",
    "science_evidence_get",
    "science_report_get",
    "science_report_export",
    "science_proposal_create",
    "science_source_validate",
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


def test_science_tools_are_discoverable_as_one_group(mcp_module):
    health = TestClient(mcp_module.app).get("/health").json()
    tool_names = {item["name"] for item in health["capability_lists"]["tools"]}
    science_group = next(
        group for group in health["tool_groups"] if group["name"] == "Science Verifier"
    )

    assert SCIENCE_TOOLS <= tool_names
    assert {item["name"] for item in science_group["tools"]} == SCIENCE_TOOLS


@pytest.mark.asyncio
async def test_verification_tools_are_thin_api_adapters(mcp_module, monkeypatch):
    calls: list[tuple[str, str, dict]] = []

    async def fake_post(path, **kwargs):
        calls.append(("POST", path, kwargs))
        return {"verdict": "INSUFFICIENT_INFORMATION", "path": path}

    async def fake_get(path, **kwargs):
        calls.append(("GET", path, kwargs))
        return {"path": path}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)
    monkeypatch.setattr(mcp_module, "api_get", fake_get)

    await mcp_module.science_interpret("원문", employee_id="u-1", request_id="r-1")
    await mcp_module.science_interpretation_confirm(
        "i-1", "b-1", user_confirmed=True, employee_id="u-1", request_id="r-2"
    )
    await mcp_module.science_verify_claim(
        "c-1", employee_id="u-1", request_id="r-3"
    )
    await mcp_module.science_verify_document(
        "문서", employee_id="u-1", request_id="r-4"
    )
    await mcp_module.science_evidence_get("e-1", employee_id="u-1")
    await mcp_module.science_report_get("report-1", employee_id="u-1")

    assert [(method, path) for method, path, _ in calls] == [
        ("POST", "/api/science/interpret"),
        ("POST", "/api/science/interpretations/i-1/confirm"),
        ("POST", "/api/science/claims/c-1/verify"),
        ("POST", "/api/science/verify-document"),
        ("GET", "/api/science/evidence/e-1"),
        ("GET", "/api/science/reports/report-1"),
    ]
    for _method, _path, kwargs in calls[:4]:
        assert kwargs["employee_id"] == "u-1"


@pytest.mark.asyncio
async def test_export_preserves_api_bytes_and_digest(mcp_module, monkeypatch):
    async def fake_bytes(path, **kwargs):
        assert path == "/api/science/reports/report-1/export"
        assert kwargs["params"] == {"format": "pdf"}
        return {
            "content_base64": "JVBERi0xLjQ=",
            "content_type": "application/pdf",
            "sha256": "abc123",
        }

    monkeypatch.setattr(mcp_module, "api_get_bytes", fake_bytes)

    result = await mcp_module.science_report_export(
        "report-1", format="pdf", employee_id="u-1"
    )

    assert result == {
        "content_base64": "JVBERi0xLjQ=",
        "content_type": "application/pdf",
        "sha256": "abc123",
    }


@pytest.mark.asyncio
async def test_governance_tools_keep_validation_separate_from_mutation(
    mcp_module, monkeypatch
):
    calls: list[tuple[str, dict]] = []

    async def fake_post(path, **kwargs):
        calls.append((path, kwargs))
        return {"ok": True, "path": path}

    monkeypatch.setattr(mcp_module, "api_post", fake_post)

    await mcp_module.science_source_validate({"source_id": "s-1"}, employee_id="a")
    await mcp_module.science_knowledge_validate(
        {"knowledge_id": "k-1"}, employee_id="a"
    )
    await mcp_module.science_rule_qualify("r-1", employee_id="a")
    await mcp_module.science_release_validate(
        {"release_id": "rel-1"}, employee_id="a"
    )
    await mcp_module.science_proposal_create(
        {"kind": "alias"}, user_confirmed=True, employee_id="p"
    )
    await mcp_module.science_release_activate(
        "rel-1", user_confirmed=True, employee_id="a"
    )
    await mcp_module.science_release_withdraw(
        "rel-1", user_confirmed=True, employee_id="a"
    )

    assert [path for path, _ in calls] == [
        "/api/science/admin/sources/validate",
        "/api/science/admin/knowledge/validate",
        "/api/science/admin/rules/r-1/qualify",
        "/api/science/admin/releases/validate",
        "/api/science/proposals",
        "/api/science/admin/releases/rel-1/activate",
        "/api/science/admin/releases/rel-1/withdraw",
    ]
    for path, kwargs in calls[-3:]:
        assert kwargs["payload"]["user_confirmed"] is True, path


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "science_interpretation_confirm",
            {"interpretation_id": "i-1", "binding_id": "b-1"},
        ),
        ("science_proposal_create", {"proposal": {"kind": "alias"}}),
    ],
)
def test_bridge_requires_explicit_confirmation_for_science_mutations(
    mcp_module, tool, args
):
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={"tool": tool, "arguments": args},
    )

    assert response.status_code == 400
    assert "user_confirmed=true" in response.json()["detail"]


@pytest.mark.parametrize(
    "tool",
    ["science_release_activate", "science_release_withdraw"],
)
def test_service_token_bridge_cannot_activate_or_withdraw_release(mcp_module, tool):
    response = TestClient(mcp_module.app).post(
        "/api/mcp/call",
        headers={"x-service-token": "test-service-token"},
        json={
            "tool": tool,
            "arguments": {
                "release_id": "rel-1",
                "employee_id": "admin-claimed-by-client",
                "user_confirmed": True,
            },
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "interactive_admin_identity_required"
