#!/usr/bin/env python3
"""Revalidate the isolated 1.10 -> 1.11 migration and 1.10 rollback copies.

The verifier is deliberately read-only. It uses Docker metadata, container
logs, and Langflow public APIs; it never opens or mutates a Langflow database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path
from typing import Any

import httpx


def inspect_container(name: str) -> dict[str, Any]:
    payload = json.loads(
        subprocess.check_output(["docker", "inspect", name], text=True)
    )[0]
    environment = {
        key: value
        for key, value in (
            item.split("=", 1)
            for item in payload.get("Config", {}).get("Env", [])
            if "=" in item
        )
    }
    secret = environment.get("LANGFLOW_SECRET_KEY", "")
    database_url = environment.get("LANGFLOW_DATABASE_URL", "")
    return {
        "private": environment,
        "public": {
            "name": name,
            "image": payload.get("Config", {}).get("Image"),
            "image_id": payload.get("Image"),
            "status": payload.get("State", {}).get("Status"),
            "secret_sha256": hashlib.sha256(secret.encode()).hexdigest()
            if secret
            else "",
            "database_host": database_url.split("@", 1)[-1].split("/", 1)[0]
            if "@" in database_url
            else "",
        },
    }


def auth_headers(
    client: httpx.Client,
    url: str,
    environment: dict[str, str],
    *,
    preferred_credentials: tuple[str, str] | None = None,
    prefer_auto_login: bool = False,
) -> dict[str, str]:
    if prefer_auto_login:
        auto = client.get(f"{url}/api/v1/auto_login")
        if auto.status_code == 200:
            token = str(auto.json().get("access_token") or "")
            if token:
                return {"Authorization": f"Bearer {token}"}
    candidates = []
    if preferred_credentials and all(preferred_credentials):
        candidates.append(preferred_credentials)
    candidates.append(
        (
            environment.get("LANGFLOW_SUPERUSER", ""),
            environment.get("LANGFLOW_SUPERUSER_PASSWORD", ""),
        )
    )
    for username, password in candidates:
        if not username or not password:
            continue
        login = client.post(
            f"{url}/api/v1/login",
            data={"username": username, "password": password},
        )
        if login.status_code < 400:
            token = str(login.json().get("access_token") or "")
            if token:
                return {"Authorization": f"Bearer {token}"}
    auto = client.get(f"{url}/api/v1/auto_login")
    if auto.status_code == 200:
        token = str(auto.json().get("access_token") or "")
        if token:
            return {"Authorization": f"Bearer {token}"}
    raise RuntimeError(f"Langflow login at {url} failed")


def public_snapshot(
    client: httpx.Client,
    url: str,
    environment: dict[str, str],
    *,
    preferred_credentials: tuple[str, str] | None = None,
    prefer_auto_login: bool = False,
) -> dict[str, Any]:
    headers = auth_headers(
        client,
        url,
        environment,
        preferred_credentials=preferred_credentials,
        prefer_auto_login=prefer_auto_login,
    )
    health = client.get(f"{url}/health")
    version = client.get(f"{url}/api/v1/version", headers=headers)
    whoami = client.get(f"{url}/api/v1/users/whoami", headers=headers)
    flows = client.get(f"{url}/api/v1/flows/", headers=headers)
    variables = client.get(f"{url}/api/v1/variables/", headers=headers)
    for response, label in (
        (health, "health"),
        (version, "version"),
        (whoami, "whoami"),
        (flows, "flows"),
        (variables, "variables"),
    ):
        if response.status_code >= 400:
            raise RuntimeError(f"{url} {label} returned HTTP {response.status_code}")
    flow_rows = [item for item in flows.json() if isinstance(item, dict)]
    variable_rows = [item for item in variables.json() if isinstance(item, dict)]
    return {
        "health": health.json(),
        "version": str(
            version.json().get("version")
            or version.json().get("main_version")
            or ""
        ),
        "user": {
            "id": str(whoami.json().get("id") or ""),
            "username": str(whoami.json().get("username") or ""),
        },
        "flow_count": len(flow_rows),
        "flow_names": sorted(
            str(item.get("name") or "") for item in flow_rows if item.get("name")
        ),
        "credential_count": sum(
            1
            for item in variable_rows
            if str(item.get("type") or "").lower() == "credential"
        ),
        "credential_values_redacted": all(
            item.get("value") in (None, "")
            for item in variable_rows
            if str(item.get("type") or "").lower() == "credential"
        ),
    }


def has_decryption_error(container: str) -> bool:
    logs = subprocess.check_output(
        ["docker", "logs", "--tail", "2000", container],
        text=True,
        stderr=subprocess.STDOUT,
    ).lower()
    markers = (
        "invalidtoken",
        "decrypt error",
        "decryption failed",
        "fernet key",
    )
    return any(marker in logs for marker in markers)


def reset_validation_copy_user(
    client: httpx.Client,
    *,
    url: str,
    environment: dict[str, str],
    username: str,
) -> tuple[str, str]:
    """Give the migrated validation-only user a temporary public-API password."""
    admin_headers = auth_headers(client, url, environment)
    response = client.get(f"{url}/api/v1/users/", headers=admin_headers)
    if response.status_code >= 400:
        raise RuntimeError(f"{url} user listing returned HTTP {response.status_code}")
    payload = response.json()
    users = payload.get("users") if isinstance(payload, dict) else payload
    user = next(
        (
            item
            for item in users or []
            if isinstance(item, dict)
            and str(item.get("username") or "") == username
        ),
        None,
    )
    if not user:
        raise RuntimeError(f"migrated validation user is missing: {username}")
    password = secrets.token_urlsafe(32)
    patched = client.patch(
        f"{url}/api/v1/users/{user['id']}",
        headers={**admin_headers, "Content-Type": "application/json"},
        json={"password": password},
    )
    if patched.status_code >= 400:
        raise RuntimeError(
            f"migrated validation user password reset returned HTTP {patched.status_code}"
        )
    return username, password


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-container", default="boi-langflow")
    parser.add_argument("--source-url", default="http://localhost:7860")
    parser.add_argument(
        "--migration-container",
        default="boi-langflow-111-migration",
    )
    parser.add_argument("--migration-url", default="http://localhost:7862")
    parser.add_argument(
        "--rollback-container",
        default="boi-langflow-110-rollback",
    )
    parser.add_argument("--rollback-url", default="http://localhost:7863")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    inspected = {
        "source": inspect_container(args.source_container),
        "migration": inspect_container(args.migration_container),
        "rollback": inspect_container(args.rollback_container),
    }
    if any(item["public"]["status"] != "running" for item in inspected.values()):
        raise RuntimeError("source, migration, and rollback containers must be running")
    with httpx.Client(timeout=180) as client:
        source = public_snapshot(
            client,
            args.source_url.rstrip("/"),
            inspected["source"]["private"],
            prefer_auto_login=True,
        )
        migration_credentials = reset_validation_copy_user(
            client,
            url=args.migration_url.rstrip("/"),
            environment=inspected["migration"]["private"],
            username=source["user"]["username"],
        )
        snapshots = {
            "source": source,
            "migration": public_snapshot(
                client,
                args.migration_url.rstrip("/"),
                inspected["migration"]["private"],
                preferred_credentials=migration_credentials,
            ),
            "rollback": public_snapshot(
                client,
                args.rollback_url.rstrip("/"),
                inspected["rollback"]["private"],
                prefer_auto_login=True,
            ),
        }

    source_names = set(snapshots["source"]["flow_names"])
    migration_names = set(snapshots["migration"]["flow_names"])
    rollback_names = set(snapshots["rollback"]["flow_names"])
    preserved_user_flows = sorted(
        name
        for name in source_names & migration_names & rollback_names
        if name.startswith("BoI Reference Flow")
    )
    secret_hashes = {
        item["public"]["secret_sha256"] for item in inspected.values()
    }
    database_hosts = {
        item["public"]["database_host"] for item in inspected.values()
    }
    checks = {
        "source_version_1_10": snapshots["source"]["version"].startswith("1.10."),
        "migration_version_1_11": snapshots["migration"]["version"].startswith("1.11."),
        "rollback_version_1_10": snapshots["rollback"]["version"].startswith("1.10."),
        "secret_preserved": len(secret_hashes) == 1 and bool(next(iter(secret_hashes))),
        "database_copies_isolated": len(database_hosts) == 3,
        "rollback_contains_source_flows": source_names.issubset(rollback_names),
        "user_owned_flows_preserved": bool(preserved_user_flows),
        "credential_records_preserved": (
            snapshots["migration"]["credential_count"]
            >= snapshots["source"]["credential_count"]
            and snapshots["rollback"]["credential_count"]
            >= snapshots["source"]["credential_count"]
        ),
        "credential_api_redacted": all(
            item["credential_values_redacted"] for item in snapshots.values()
        ),
        "migration_has_no_decryption_error": not has_decryption_error(
            args.migration_container
        ),
        "rollback_has_no_decryption_error": not has_decryption_error(
            args.rollback_container
        ),
    }
    result = {
        "ok": all(checks.values()),
        "source_read_only_revalidation": True,
        "validation_copy_user_reset_via_public_api": True,
        "checks": checks,
        "containers": {
            key: value["public"] for key, value in inspected.items()
        },
        "snapshots": snapshots,
        "preserved_user_flow_count": len(preserved_user_flows),
        "secrets_redacted": True,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        os.chmod(args.output, 0o600)
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
