from __future__ import annotations

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
