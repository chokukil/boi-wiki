#!/usr/bin/env python3
"""Verify the live local Keycloak reference contract without exposing secrets.

Keycloak is only the validation implementation for the provider-neutral OIDC
contract.  This script queries its admin API to prove that the single boi-wiki
client is confidential, requires PKCE S256, emits the employee claim, and owns
both the BoI and Langflow browser callbacks. End-user login remains
Authorization Code + PKCE and is exercised separately by Playwright.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def request_json(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    token: str = "",
    content_type: str = "",
) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Keycloak request failed with {exc.code}: {detail}") from exc


def mapper_config(client: dict[str, Any], protocol_mapper: str) -> list[dict[str, str]]:
    return [
        dict(mapper.get("config") or {})
        for mapper in client.get("protocolMappers") or []
        if mapper.get("protocolMapper") == protocol_mapper
    ]


def client_summary(client: dict[str, Any]) -> dict[str, Any]:
    employee_mappers = mapper_config(client, "oidc-usermodel-attribute-mapper")
    audience_mappers = mapper_config(client, "oidc-audience-mapper")
    return {
        "client_id": str(client.get("clientId") or ""),
        "confidential": client.get("publicClient") is False,
        "standard_flow_enabled": client.get("standardFlowEnabled") is True,
        "direct_access_grants_enabled": client.get("directAccessGrantsEnabled") is True,
        "pkce_method": str((client.get("attributes") or {}).get("pkce.code.challenge.method") or ""),
        "redirect_uris": list(client.get("redirectUris") or []),
        "web_origins": list(client.get("webOrigins") or []),
        "employee_claim": any(
            mapper.get("user.attribute") == "empno"
            and mapper.get("claim.name") == "empno"
            for mapper in employee_mappers
        ),
        "audiences": sorted(
            {
                str(mapper.get("included.client.audience") or "")
                for mapper in audience_mappers
                if mapper.get("included.client.audience")
            }
        ),
        "secret_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--base-url",
        default=os.getenv("BOI_KEYCLOAK_VALIDATION_URL", "http://localhost:18082"),
    )
    parser.add_argument("--realm", default="boi-validation")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    admin_username = os.getenv("BOI_KEYCLOAK_VALIDATION_ADMIN", "validation-admin")
    admin_password = os.getenv(
        "BOI_KEYCLOAK_VALIDATION_ADMIN_PASSWORD",
        "validation-admin",
    )
    token_payload = urllib.parse.urlencode(
        {
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": admin_username,
            "password": admin_password,
        }
    ).encode()
    token_body = request_json(
        f"{base}/realms/master/protocol/openid-connect/token",
        method="POST",
        data=token_payload,
        content_type="application/x-www-form-urlencoded",
    )
    admin_token = str(token_body.get("access_token") or "")
    if not admin_token:
        raise RuntimeError("Keycloak admin token response had no access token")

    query = urllib.parse.urlencode({"clientId": "boi-wiki"})
    rows = request_json(
        f"{base}/admin/realms/{urllib.parse.quote(args.realm)}/clients?{query}",
        token=admin_token,
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("expected exactly one live Keycloak client: boi-wiki")
    boi = client_summary(rows[0])
    checks = {
        "boi_confidential_pkce": (
            boi["confidential"]
            and boi["standard_flow_enabled"]
            and not boi["direct_access_grants_enabled"]
            and boi["pkce_method"] == "S256"
        ),
        "boi_callback": "http://localhost:28005/auth/callback" in boi["redirect_uris"],
        "langflow_callback": (
            "http://localhost:17867/oauth2/callback" in boi["redirect_uris"]
        ),
        "corporate_boi_callback": (
            "http://wiki.skhynix.com/auth/callback" in boi["redirect_uris"]
        ),
        "corporate_langflow_callback": (
            "http://wiki.skhynix.com/builder/oauth2/callback"
            in boi["redirect_uris"]
        ),
        "boi_empno": boi["employee_claim"],
    }
    result = {
        "ok": all(checks.values()),
        "provider_role": "local reference implementation only",
        "base_url": base,
        "realm": args.realm,
        "checks": checks,
        "clients": {"boi-wiki": boi},
        "admin_token_exposed": False,
    }
    if not result["ok"]:
        raise RuntimeError(f"Keycloak reference contract failed: {checks}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
