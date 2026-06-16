#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "langflow" / "flows" / "boi_reference_flow.manifest.json"
DEFAULT_ENDPOINT_NAME = "boi-reference-flow"


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    flow_file = ROOT / manifest["flow_file"]
    if not flow_file.exists():
        raise FileNotFoundError(f"flow file not found: {flow_file}")
    manifest["_flow_file_path"] = str(flow_file)
    return manifest


def env(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/") if name.endswith("URL") else os.getenv(name, default)


def get_auth_headers(client: httpx.Client, langflow_url: str, api_key: str, auth_mode: str) -> dict[str, str]:
    if auth_mode == "api-key":
        return {"x-api-key": api_key}

    response = client.get(f"{langflow_url}/api/v1/auto_login")
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Langflow auto_login response did not include access_token")
    return {"Authorization": f"Bearer {token}"}


def upload_flow(client: httpx.Client, langflow_url: str, headers: dict[str, str], flow_file: Path) -> dict[str, Any]:
    url = f"{langflow_url}/api/v1/flows/upload/"
    with flow_file.open("rb") as handle:
        response = client.post(url, headers=headers, files={"file": (flow_file.name, handle, "application/json")})
    response.raise_for_status()
    return response.json()


def smoke_run(client: httpx.Client, langflow_url: str, headers: dict[str, str], endpoint_name: str) -> dict[str, Any]:
    url = f"{langflow_url}/api/v1/run/{endpoint_name}"
    request_headers = {**headers, "Content-Type": "application/json"}
    payload = {
        "input_value": "BoI Wiki PoC Langflow smoke test. Respond with one short Korean sentence.",
        "input_type": "chat",
        "output_type": "chat",
    }
    response = client.post(url, headers=request_headers, json=payload)
    response.raise_for_status()
    return response.json()


def resolve_smoke_target(upload_result: Any, fallback_endpoint_name: str) -> str:
    uploaded_flow = upload_result[0] if isinstance(upload_result, list) and upload_result else upload_result
    if isinstance(uploaded_flow, dict):
        return uploaded_flow.get("id") or uploaded_flow.get("endpoint_name") or fallback_endpoint_name
    return fallback_endpoint_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and smoke-test BoI reference Langflow flows.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--langflow-url", default=env("LANGFLOW_URL", "http://localhost:7860"))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me"))
    parser.add_argument("--auth-mode", choices=["auto-login", "api-key"], default=os.getenv("LANGFLOW_AUTH_MODE", "auto-login"))
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    flow_file = Path(manifest["_flow_file_path"])
    langflow_url = args.langflow_url.rstrip("/")
    endpoint_name = manifest.get("endpoint_name") or DEFAULT_ENDPOINT_NAME

    with httpx.Client(timeout=60) as client:
        headers = get_auth_headers(client, langflow_url, args.langflow_api_key, args.auth_mode)
        upload_result = upload_flow(client, langflow_url, headers, flow_file)
        smoke_target = resolve_smoke_target(upload_result, endpoint_name)
        result: dict[str, Any] = {
            "ok": True,
            "langflow_url": langflow_url,
            "endpoint_name": endpoint_name,
            "smoke_target": smoke_target,
            "flow_file": str(flow_file),
            "auth_mode": args.auth_mode,
            "upload": upload_result,
        }
        if not args.skip_smoke:
            result["smoke"] = smoke_run(client, langflow_url, headers, smoke_target)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
