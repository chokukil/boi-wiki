#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

import httpx


DEV_EMPLOYEES = ("100001", "100002", "100003")


def login(client: httpx.Client, base_url: str, username: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{base_url}/api/v1/login",
        data={"username": username, "password": password},
    )
    response.raise_for_status()
    if not str(response.json().get("access_token") or ""):
        raise RuntimeError(f"login did not return an access token for {username}")
    # Langflow 1.11 authenticates its own UI/API session through the standard
    # HttpOnly cookies set by /api/v1/login.  Sending the returned bearer JWT
    # as well can shadow the valid session on early 1.11 builds, so bootstrap
    # uses the public login cookie until it creates the user's standard API key.
    return {}


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    expected: set[int] | None = None,
    **kwargs: Any,
) -> Any:
    response = client.request(method, url, headers=headers, **kwargs)
    if response.status_code not in (expected or {200}):
        raise RuntimeError(f"{method} {url} returned {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Create isolated Langflow users, API keys, and personal projects.")
    parser.add_argument("--url", default="http://localhost:7867")
    parser.add_argument("--admin-user", default=os.getenv("LANGFLOW_111_SUPERUSER", "boi-platform-admin"))
    parser.add_argument(
        "--admin-password",
        default=os.getenv("LANGFLOW_111_SUPERUSER_PASSWORD", "BoiValidation-111!ChangeMe"),
    )
    parser.add_argument("--output", required=True, help="Mode-0600 JSON file that receives one-time API keys.")
    parser.add_argument("--rotate-keys", action="store_true")
    parser.add_argument(
        "--users-only",
        action="store_true",
        help="Create native users only; leave API keys and boi-* projects for the onboarding E2E.",
    )
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    output = Path(args.output)
    if output.exists() and not args.rotate_keys:
        raise RuntimeError("output already exists; use a new path or --rotate-keys")
    credentials: dict[str, Any] = {}
    with httpx.Client(timeout=30) as client:
        for employee_id in DEV_EMPLOYEES:
            username = employee_id
            password = os.getenv(
                f"LANGFLOW_111_USER_{employee_id}_PASSWORD",
                f"BoiPlayground-{employee_id}!ChangeMe",
            )
            signup = client.post(
                f"{base_url}/api/v1/users/",
                json={"username": username, "password": password},
            )
            if signup.status_code not in {200, 201, 400}:
                raise RuntimeError(
                    f"POST {base_url}/api/v1/users/ returned {signup.status_code}: "
                    f"{signup.text[:500]}"
                )
            if signup.status_code == 400 and "unavailable" not in signup.text.lower():
                raise RuntimeError(
                    f"Langflow could not prepare {username}: {signup.text[:500]}"
                )
            if args.users_only:
                credentials[employee_id] = {
                    "username": username,
                    "password": password,
                    "api_key": "",
                    "project_id": "",
                    "project_name": f"boi-{employee_id}",
                }
                continue
            user_headers = login(client, base_url, username, password)
            keys = request_json(client, "GET", f"{base_url}/api/v1/api_key/", headers=user_headers)
            existing = [
                item
                for item in (keys.get("api_keys") or [])
                if isinstance(item, dict) and str(item.get("name") or "") == "BoI Agent Playground"
            ]
            if existing and args.rotate_keys:
                for item in existing:
                    request_json(
                        client,
                        "DELETE",
                        f"{base_url}/api/v1/api_key/{item['id']}",
                        headers=user_headers,
                        expected={200, 204},
                    )
                existing = []
            if existing:
                raise RuntimeError(
                    f"{username} already has a masked Agent Playground key; rerun with --rotate-keys to obtain a new raw key"
                )
            api_key = request_json(
                client,
                "POST",
                f"{base_url}/api/v1/api_key/",
                headers=user_headers,
                expected={200, 201},
                json={"name": "BoI Agent Playground", "expires_at": None},
            )
            key_headers = {"x-api-key": str(api_key["api_key"])}
            whoami = request_json(client, "GET", f"{base_url}/api/v1/users/whoami", headers=key_headers)
            projects = request_json(client, "GET", f"{base_url}/api/v1/projects/", headers=key_headers)
            project_name = f"boi-{employee_id}"
            project = next(
                (
                    item
                    for item in projects
                    if isinstance(item, dict) and str(item.get("name") or "") == project_name
                ),
                None,
            )
            if project is None:
                project = request_json(
                    client,
                    "POST",
                    f"{base_url}/api/v1/projects/",
                    headers=key_headers,
                    expected={200, 201},
                    json={"name": project_name, "description": "BoI Agent Playground personal project"},
                )
            credentials[employee_id] = {
                "username": username,
                "user_id": str(whoami.get("id") or ""),
                "password": password,
                "api_key": str(api_key["api_key"]),
                "project_id": str(project.get("id") or ""),
                "project_name": project_name,
            }

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"langflow_url": base_url, "users": credentials}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"ok": True, "output": str(output), "users": list(credentials)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
