#!/usr/bin/env python3
"""Repeat the BoI contract checks after replacing the official Langflow image.

The script deliberately treats Langflow as an external process. It only uses
Docker inspection and the public HTTP API; it never imports Langflow modules or
opens the Langflow database.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value or "").split("-", 1)[0].split(".")
    if len(parts) < 2:
        raise RuntimeError(f"invalid Langflow version: {value!r}")
    normalized = [int(part) for part in parts[:3]]
    while len(normalized) < 3:
        normalized.append(0)
    return tuple(normalized)  # type: ignore[return-value]


def public_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    **kwargs: Any,
) -> Any:
    response = client.request(method, url, headers=headers, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} returned HTTP {response.status_code}")
    return response.json() if response.content else None


def inspect_container(name: str) -> dict[str, Any]:
    raw = subprocess.check_output(["docker", "inspect", name], text=True)
    payload = json.loads(raw)[0]
    mounts = payload.get("Mounts") or []
    component_mount = next(
        (item for item in mounts if str(item.get("Destination") or "") == "/app/custom_components"),
        None,
    )
    if component_mount is None or bool(component_mount.get("RW")):
        raise RuntimeError("BoI component bundle is not mounted read-only")
    return {
        "name": name,
        "image": payload.get("Config", {}).get("Image"),
        "image_id": payload.get("Image"),
        "status": payload.get("State", {}).get("Status"),
        "component_mount": {
            "destination": component_mount.get("Destination"),
            "read_only": not bool(component_mount.get("RW")),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a replacement official Langflow 1.11.x image through public contracts."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--container", default="")
    parser.add_argument("--api-key-env", default="LANGFLOW_API_KEY")
    parser.add_argument("--expect-user", default="")
    parser.add_argument("--expect-project", default="")
    parser.add_argument("--flow-id", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        raise RuntimeError(f"{args.api_key_env} must contain a user-owned Langflow API Key")
    base_url = args.url.rstrip("/")
    headers = {"x-api-key": api_key}
    result: dict[str, Any] = {
        "ok": False,
        "external_runtime_only": True,
        "url": base_url,
        "checks": {},
    }

    boundary = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_agent_playground_langflow_boundary.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if boundary.returncode:
        raise RuntimeError("Langflow non-modification boundary check failed")
    result["checks"]["boundary"] = json.loads(boundary.stdout)

    if args.container:
        result["checks"]["container"] = inspect_container(args.container)

    with httpx.Client(timeout=180) as client:
        health = public_json(client, "GET", f"{base_url}/health", headers={})
        version_payload = public_json(client, "GET", f"{base_url}/api/v1/version", headers=headers)
        version = str(
            (version_payload or {}).get("version")
            or (version_payload or {}).get("main_version")
            or ""
        )
        parsed = version_tuple(version)
        if not ((1, 11, 0) <= parsed < (1, 12, 0)):
            raise RuntimeError(f"unsupported Langflow version: {version}")
        whoami = public_json(client, "GET", f"{base_url}/api/v1/users/whoami", headers=headers)
        username = str((whoami or {}).get("username") or "")
        if args.expect_user and username != args.expect_user:
            raise RuntimeError(f"API Key owner mismatch: expected {args.expect_user}, got {username}")
        projects = public_json(client, "GET", f"{base_url}/api/v1/projects/", headers=headers)
        project_names = [
            str(item.get("name") or "") for item in projects or [] if isinstance(item, dict)
        ]
        if args.expect_project and args.expect_project not in project_names:
            raise RuntimeError(f"project not found: {args.expect_project}")
        variables = public_json(client, "GET", f"{base_url}/api/v1/variables/", headers=headers)
        credentials_redacted = all(
            item.get("value") in (None, "")
            for item in variables or []
            if isinstance(item, dict) and str(item.get("type") or "").lower() == "credential"
        )
        if not credentials_redacted:
            raise RuntimeError("Langflow public API returned a raw Credential value")

        runtime: dict[str, Any] = {"skipped": not bool(args.flow_id)}
        if args.flow_id:
            run_payload = public_json(
                client,
                "POST",
                f"{base_url}/api/v1/run/{args.flow_id}",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "input_value": "Langflow patch compatibility smoke",
                    "input_type": "chat",
                    "output_type": "chat",
                },
            )
            runtime = {
                "skipped": False,
                "ok": True,
                "session_id_present": bool((run_payload or {}).get("session_id")),
            }
        result["checks"]["public_api"] = {
            "health": health,
            "version": version,
            "user": username,
            "projects": project_names,
            "credential_values_redacted": credentials_redacted,
            "run": runtime,
        }

    result["ok"] = True
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
        os.chmod(args.output, 0o600)
    print(rendered)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
