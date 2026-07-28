from __future__ import annotations

import importlib

import jwt
from fastapi.testclient import TestClient


def bridge_client(monkeypatch):
    monkeypatch.setenv("SSO_BRIDGE_ALLOW_EPHEMERAL_KEY", "true")
    monkeypatch.setenv("SSO_BRIDGE_PROXY_SHARED_SECRET", "trusted-proxy-secret")
    monkeypatch.setenv("SSO_BRIDGE_TRUSTED_PROXY_CIDRS", "testclient")
    monkeypatch.setenv("SSO_BRIDGE_ISSUER", "https://bridge.example")
    monkeypatch.setenv("SSO_BRIDGE_AUDIENCE", "langflow-browser")
    import sso_token_bridge.app.main as bridge

    return bridge, TestClient(importlib.reload(bridge).app)


def test_bridge_issues_short_lived_employee_bound_rs256_token(monkeypatch):
    bridge, client = bridge_client(monkeypatch)

    response = client.get(
        "/auth",
        headers={
            "x-boi-proxy-secret": "trusted-proxy-secret",
            "x-boi-employee-id": "100002",
            "x-boi-name": "BoI Developer",
            "x-boi-email": "100002@example.test",
        },
    )

    assert response.status_code == 204
    assert response.text == ""
    token = response.headers["x-forwarded-access-token"]
    claims = jwt.decode(
        token,
        bridge.BRIDGE_KEY.private_key.public_key(),
        algorithms=["RS256"],
        audience="langflow-browser",
        issuer="https://bridge.example",
    )
    assert claims["empno"] == "100002"
    assert claims["preferred_username"] == "100002"
    assert claims["exp"] - claims["iat"] == 60
    assert "roles" not in claims

    jwks = client.get("/.well-known/jwks.json").json()
    assert jwks["keys"][0]["kid"] == bridge.BRIDGE_KEY.kid
    assert token not in client.get("/health").text


def test_bridge_rejects_direct_or_spoofed_requests(monkeypatch):
    _bridge, client = bridge_client(monkeypatch)

    no_secret = client.get("/auth", headers={"x-boi-employee-id": "100002"})
    wrong_secret = client.get(
        "/auth",
        headers={
            "x-boi-proxy-secret": "wrong",
            "x-boi-employee-id": "100002",
        },
    )
    no_employee = client.get(
        "/auth",
        headers={"x-boi-proxy-secret": "trusted-proxy-secret"},
    )

    assert no_secret.status_code == 401
    assert wrong_secret.status_code == 401
    assert no_employee.status_code == 401
