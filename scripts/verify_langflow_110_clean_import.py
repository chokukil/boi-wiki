#!/usr/bin/env python3
"""Import and run a 1.10 Flow JSON in a clean official 1.11 runtime."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx


def container_environment(name: str) -> dict[str, str]:
    payload = json.loads(
        subprocess.check_output(["docker", "inspect", name], text=True)
    )[0]
    return {
        key: value
        for key, value in (
            item.split("=", 1)
            for item in payload.get("Config", {}).get("Env", [])
            if "=" in item
        )
    }


def login(
    client: httpx.Client,
    url: str,
    *,
    environment: dict[str, str] | None = None,
) -> dict[str, str]:
    auto = client.get(f"{url}/api/v1/auto_login")
    if auto.status_code == 200 and auto.json().get("access_token"):
        return {"Authorization": f"Bearer {auto.json()['access_token']}"}
    environment = environment or {}
    response = client.post(
        f"{url}/api/v1/login",
        data={
            "username": environment.get("LANGFLOW_SUPERUSER", ""),
            "password": environment.get("LANGFLOW_SUPERUSER_PASSWORD", ""),
        },
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Langflow login returned HTTP {response.status_code}")
    token = str(response.json().get("access_token") or "")
    if not token:
        raise RuntimeError("Langflow login returned no access token")
    return {"Authorization": f"Bearer {token}"}


def version(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    response = client.get(f"{url}/api/v1/version", headers=headers)
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("version") or payload.get("main_version") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default="http://localhost:7863")
    parser.add_argument(
        "--source-flow-prefix",
        default="BoI 1.10 Import Runtime Proof",
    )
    parser.add_argument("--target-url", default="http://localhost:7865")
    parser.add_argument(
        "--target-container",
        default="boi-ap-pure-langflow-20260726",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source_url = args.source_url.rstrip("/")
    target_url = args.target_url.rstrip("/")
    with httpx.Client(timeout=180) as client:
        source_headers = login(client, source_url)
        target_headers = login(
            client,
            target_url,
            environment=container_environment(args.target_container),
        )
        source_version = version(client, source_url, source_headers)
        target_version = version(client, target_url, target_headers)
        source_flows = client.get(
            f"{source_url}/api/v1/flows/",
            headers=source_headers,
        )
        source_flows.raise_for_status()
        source_flow = next(
            (
                item
                for item in source_flows.json()
                if isinstance(item, dict)
                and str(item.get("name") or "").startswith(args.source_flow_prefix)
            ),
            None,
        )
        if not source_flow:
            raise RuntimeError("1.10 runtime-proof Flow is missing")
        detail = client.get(
            f"{source_url}/api/v1/flows/{source_flow['id']}",
            headers=source_headers,
        )
        detail.raise_for_status()
        source_detail = detail.json()
        export = {
            key: source_detail.get(key)
            for key in (
                "name",
                "description",
                "endpoint_name",
                "data",
                "webhook",
                "access_type",
                "tags",
            )
            if source_detail.get(key) is not None
        }
        export["name"] = f"{source_detail['name']} - clean 1.11 import"

        target_flows = client.get(
            f"{target_url}/api/v1/flows/",
            headers=target_headers,
        )
        target_flows.raise_for_status()
        for item in target_flows.json():
            if (
                isinstance(item, dict)
                and str(item.get("name") or "") == export["name"]
            ):
                deleted = client.delete(
                    f"{target_url}/api/v1/flows/{item['id']}",
                    headers=target_headers,
                )
                if deleted.status_code not in {200, 202, 204, 404}:
                    deleted.raise_for_status()
        uploaded = client.post(
            f"{target_url}/api/v1/flows/upload/",
            headers=target_headers,
            files={
                "file": (
                    "langflow-1.10-runtime-proof.json",
                    json.dumps(export, ensure_ascii=False).encode(),
                    "application/json",
                )
            },
        )
        uploaded.raise_for_status()
        upload_payload: Any = uploaded.json()
        imported = (
            upload_payload[0]
            if isinstance(upload_payload, list) and upload_payload
            else upload_payload
        )
        flow_id = str((imported or {}).get("id") or "")
        if not flow_id:
            raise RuntimeError("1.11 upload returned no Flow ID")
        key_response = client.post(
            f"{target_url}/api/v1/api_key/",
            headers={**target_headers, "Content-Type": "application/json"},
            json={"name": "origin-main-clean-import-proof"},
        )
        key_response.raise_for_status()
        key_payload = key_response.json()
        runtime_key = str(key_payload.get("api_key") or "")
        if not runtime_key:
            raise RuntimeError("clean 1.11 runtime returned no temporary API Key")
        try:
            run = client.post(
                f"{target_url}/api/v1/run/{flow_id}",
                headers={"x-api-key": runtime_key, "Content-Type": "application/json"},
                json={
                    "input_value": "origin/main Langflow 1.10 export import proof",
                    "input_type": "chat",
                    "output_type": "chat",
                },
            )
            run.raise_for_status()
            run_payload = run.json()
        finally:
            key_id = str(key_payload.get("id") or "")
            if key_id:
                client.delete(
                    f"{target_url}/api/v1/api_key/{key_id}",
                    headers=target_headers,
                )

    result = {
        "ok": (
            source_version.startswith("1.10.")
            and target_version.startswith("1.11.")
            and bool(run_payload.get("session_id"))
        ),
        "source": {
            "version": source_version,
            "flow_id": str(source_detail.get("id") or ""),
            "flow_name": str(source_detail.get("name") or ""),
        },
        "target": {
            "version": target_version,
            "flow_id": flow_id,
            "flow_name": str((imported or {}).get("name") or ""),
            "upload_http": uploaded.status_code,
            "run_http": run.status_code,
            "session_id_present": bool(run_payload.get("session_id")),
            "temporary_api_key_removed": bool(key_payload.get("id")),
        },
        "public_api_only": True,
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
