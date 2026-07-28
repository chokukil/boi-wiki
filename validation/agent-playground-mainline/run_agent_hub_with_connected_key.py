#!/usr/bin/env python3
"""Run immutable Agent Hub E2E with the key already stored by Playground.

This validation-only launcher keeps the decrypted Langflow API key in process
memory.  It never writes or prints the key, and replaces itself with the Node
runner so the key is discarded when the E2E process exits.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTAINER = os.getenv(
    "BOI_VALIDATION_CONTAINER",
    "boi-agent-playground-mainline-boi-api-1",
)
EMPLOYEE_ID = os.getenv("AGENT_HUB_USERNAME", "100002")


def _container_json(path: str) -> dict:
    value = subprocess.check_output(
        ["docker", "exec", CONTAINER, "cat", path],
        text=True,
    )
    return json.loads(value)


def _container_environment() -> dict[str, str]:
    inspected = json.loads(
        subprocess.check_output(["docker", "inspect", CONTAINER], text=True)
    )[0]
    return {
        key: value
        for item in inspected["Config"]["Env"]
        if "=" in item
        for key, value in [item.split("=", 1)]
    }


def _connected_api_key(record: dict, secret: str) -> str:
    default_endpoint_id = str(record.get("default_endpoint_id") or "")
    endpoint = next(
        (
            item
            for item in record.get("endpoints") or []
            if str(item.get("endpoint_id") or "") == default_endpoint_id
        ),
        None,
    )
    if not endpoint:
        raise RuntimeError("Playground default Langflow endpoint is missing")
    encrypted = str(endpoint.get("api_key_encrypted") or "")
    if not encrypted:
        raise RuntimeError("Playground default Langflow endpoint has no API key")
    packed = base64.urlsafe_b64decode(encrypted.encode("ascii"))
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    return AESGCM(key).decrypt(
        packed[:12],
        packed[12:],
        EMPLOYEE_ID.encode("utf-8"),
    ).decode("utf-8")


def main() -> None:
    record = _container_json(
        f"/runtime/agent-playground/users/{EMPLOYEE_ID}.json"
    )
    if str(record.get("employee_id") or "") != EMPLOYEE_ID:
        raise RuntimeError("Playground credential owner mismatch")
    environment = _container_environment()
    encryption_secret = str(
        environment.get("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY") or ""
    )
    if not encryption_secret:
        raise RuntimeError("Playground encryption key is unavailable")
    api_key = _connected_api_key(record, encryption_secret)

    child_environment = dict(os.environ)
    child_environment.update(
        {
            "LANGFLOW_API_KEY": api_key,
            "LANGFLOW_BROWSER_AUTH_MODE": "embedded_sso",
            "LANGFLOW_BROWSER_URL": "http://localhost:17867",
            "LANGFLOW_ENDPOINT_FOR_AGENT_HUB": "http://localhost:7867",
            "LANGFLOW_ENDPOINT_FOR_PLAYGROUND": "http://host.docker.internal:7867",
            "FLOW_JSON_PATH": str(
                REPO_ROOT / "langflow/flows/boi_universal_simulation_mcp.json"
            ),
            "PLAYWRIGHT_EVIDENCE_DIR": str(
                REPO_ROOT / "artifacts/agent-playground-agent-hub-sso"
            ),
        }
    )
    runner = REPO_ROOT / "validation/agent-hub/playwright_e2e.mjs"
    os.execvpe("node", ["node", str(runner)], child_environment)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Agent Hub E2E launcher failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
