from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from boi_api.app import auth
from mock_hcp.app.main import DEFAULT_PERMISSIONS


ROOT = Path(__file__).resolve().parents[1]


def test_hcp_roles_replace_keycloak_role_claims(monkeypatch):
    monkeypatch.setenv("HCP_AUTHZ_URL", "http://mock-hcp/permissions")
    monkeypatch.setenv("BOI_ALLOWED_EMPLOYEE_IDS", "100002")
    monkeypatch.setattr(
        auth,
        "hcp_permissions",
        lambda employee_id, bearer_token=None: {
            "employee_id": employee_id,
            "allowed": True,
            "teams": ["aix-tf"],
            "roles": ["boi.viewer", "boi.editor", "boi.action_invoker"],
        },
    )

    identity = auth.identity_from_claims(
        {
            "empno": "100002",
            "preferred_username": "100002",
            "realm_access": {"roles": ["boi.admin", "boi.promoter"]},
        },
        auth_source="keycloak",
    )

    assert identity.employee_id == "100002"
    assert "boi.action_invoker" in identity.roles
    assert "boi.admin" not in identity.roles
    assert "boi.promoter" not in identity.roles


def test_existing_session_reloads_authoritative_hcp_roles(monkeypatch):
    monkeypatch.setenv("HCP_AUTHZ_URL", "http://mock-hcp/permissions")
    monkeypatch.setenv("BOI_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("BOI_ALLOWED_EMPLOYEE_IDS", "100003")
    session = auth.create_session_token(
        auth.AuthIdentity(
            employee_id="100003",
            display_name="Viewer",
            roles=["boi.viewer", "boi.admin", "boi.action_invoker"],
            auth_source="keycloak",
        )
    )
    monkeypatch.setattr(
        auth,
        "hcp_permissions",
        lambda employee_id, bearer_token=None: {
            "employee_id": employee_id,
            "allowed": True,
            "teams": ["platform"],
            "roles": ["boi.viewer"],
        },
    )

    identity = auth.identity_from_session_token(session)

    assert identity.roles == ["boi.viewer"]
    assert identity.teams == ["platform"]


def test_hcp_failure_is_closed_outside_dev(monkeypatch):
    auth._HCP_CACHE.clear()
    monkeypatch.setenv("BOI_AUTH_MODE", "keycloak")
    monkeypatch.setenv("HCP_AUTHZ_URL", "http://unavailable/permissions")
    monkeypatch.setattr(auth.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    with pytest.raises(auth.AuthError) as exc:
        auth.hcp_permissions("100002")

    assert exc.value.status_code == 503


def test_force_refresh_bypasses_stale_hcp_identity_cache(monkeypatch):
    auth._HCP_CACHE.clear()
    monkeypatch.setenv("BOI_AUTH_MODE", "keycloak")
    monkeypatch.setenv("HCP_AUTHZ_URL", "http://mock-hcp/permissions")
    responses = [
        {
            "employee_id": "100002",
            "allowed": True,
            "teams": ["aix-tf"],
            "roles": ["boi.viewer", "boi.editor", "boi.action_invoker"],
        },
        {
            "employee_id": "100002",
            "allowed": True,
            "teams": ["aix-tf"],
            "roles": ["boi.viewer"],
        },
    ]

    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *args, **kwargs: Response(responses.pop(0)),
    )

    initial = auth.hcp_permissions("100002")
    cached = auth.hcp_permissions("100002")
    refreshed = auth.hcp_permissions("100002", force_refresh=True)

    assert initial == cached
    assert "boi.action_invoker" in initial["roles"]
    assert refreshed["roles"] == ["boi.viewer"]


def test_durable_playground_identity_ignores_login_identity_cache(
    boi_app_module,
    monkeypatch,
):
    boi_app_module._IDENTITY_CACHE["100002"] = auth.AuthIdentity(
        employee_id="100002",
        display_name="Stale Session",
        teams=["aix-tf"],
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
        auth_source="stale_session",
    )
    monkeypatch.setattr(boi_app_module, "auth_mode", lambda: "keycloak")
    monkeypatch.setattr(
        boi_app_module,
        "hcp_authorization_configured",
        lambda: True,
    )
    calls = []

    def permissions(employee_id, bearer_token=None, *, force_refresh=False):
        calls.append(force_refresh)
        return {
            "employee_id": employee_id,
            "allowed": True,
            "teams": ["aix-tf"],
            "roles": ["boi.viewer"],
        }

    monkeypatch.setattr(boi_app_module, "hcp_permissions", permissions)
    current = boi_app_module.credential_identity_for_employee("100002")

    assert calls == [True]
    assert current.roles == ["boi.viewer"]
    assert current.auth_source == "hcp_credential_refresh"


def test_action_start_rechecks_hcp_instead_of_trusting_session_identity(
    boi_app_module,
    monkeypatch,
):
    stale_session = auth.AuthIdentity(
        employee_id="100002",
        display_name="Stale session",
        teams=["aix-tf"],
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
        auth_source="keycloak_session",
    )
    refreshes: list[str] = []

    def refreshed(employee_id: str):
        refreshes.append(employee_id)
        return auth.AuthIdentity(
            employee_id=employee_id,
            display_name="Refreshed viewer",
            teams=["aix-tf"],
            roles=["boi.viewer"],
            auth_source="hcp_credential_refresh",
        )

    monkeypatch.setattr(boi_app_module, "credential_identity_for_employee", refreshed)
    request = boi_app_module.ActionInvokeRequest(
        action_key="team.shared.action",
        employee_id="100002",
        payload={},
    )

    with pytest.raises(boi_app_module.HTTPException) as exc:
        asyncio.run(
            boi_app_module.invoke_action_gateway(
                request,
                "100002",
                stale_session,
            )
        )

    assert exc.value.status_code == 403
    assert refreshes == ["100002"]


def test_keycloak_and_mock_hcp_identity_contracts_do_not_drift():
    realm = json.loads((ROOT / "infra" / "keycloak" / "boi-dev-realm.json").read_text(encoding="utf-8"))
    client = next(item for item in realm["clients"] if item["clientId"] == "boi-wiki")
    users = {item["username"]: item for item in realm["users"]}
    mappers = {item["config"]["claim.name"] for item in client["protocolMappers"]}

    assert client["publicClient"] is False
    assert client["standardFlowEnabled"] is True
    assert client["directAccessGrantsEnabled"] is False
    assert "empno" in mappers
    assert "employee_id" in mappers
    assert "http://localhost:28002/auth/callback" in client["redirectUris"]
    assert "http://wiki.skhynix.com/auth/callback" in client["redirectUris"]
    assert all(item["realmRoles"] == ["boi.viewer"] for item in users.values())
    assert all(item["attributes"]["empno"] == [username] for username, item in users.items())

    assert "boi.action_invoker" in DEFAULT_PERMISSIONS["100002"]["roles"]
    assert DEFAULT_PERMISSIONS["100003"]["roles"] == ["boi.viewer"]

    validation_realm = json.loads(
        (ROOT / "validation" / "agent-hub" / "keycloak-realm.json").read_text(encoding="utf-8")
    )
    validation_client = next(item for item in validation_realm["clients"] if item["clientId"] == "boi-wiki")
    assert validation_client["publicClient"] is False
    assert validation_client["directAccessGrantsEnabled"] is False
    assert validation_client["redirectUris"] == [
        "http://localhost:28002/auth/callback",
        "http://localhost:28005/auth/callback",
    ]
