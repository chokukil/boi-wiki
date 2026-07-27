#!/usr/bin/env python3
"""Prove that BoI components come only from a read-only external bundle.

The verifier compares two running containers created from the same official
Langflow image:

* a pristine runtime without ``/app/custom_components``;
* a runtime with the BoI bundle mounted read-only.

It uses Docker inspection and Langflow's public HTTP API. Credentials are read
from each isolated validation container's environment and are never rendered.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx


BOI_COMPONENTS = (
    "BoIWikiKnowledge",
    "BoIWikiSave",
    "BoIModelAgent",
    "BoIUniversalSimulationMCPAgent",
)
DEFAULT_IMAGE = (
    "langflowai/langflow:1.11.0@"
    "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
)
PACKAGE_HASH_COMMAND = r"""
set -eu
root="$(find /app/.venv/lib -type d -path '*/site-packages/langflow' | head -n 1)"
test -n "$root"
find "$root" -type f \( -name '*.py' -o -name 'py.typed' \) -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  | sha256sum \
  | awk '{print $1}'
"""


def docker_inspect(name: str) -> dict[str, Any]:
    raw = subprocess.check_output(["docker", "inspect", name], text=True)
    payload = json.loads(raw)[0]
    env = {
        key: value
        for key, value in (
            item.split("=", 1)
            for item in payload.get("Config", {}).get("Env", [])
            if "=" in item
        )
    }
    mounts = payload.get("Mounts") or []
    component_mount = next(
        (
            item
            for item in mounts
            if str(item.get("Destination") or "") == "/app/custom_components"
        ),
        None,
    )
    return {
        "env": env,
        "public": {
            "name": name,
            "configured_image": payload.get("Config", {}).get("Image"),
            "image_id": payload.get("Image"),
            "status": payload.get("State", {}).get("Status"),
            "component_mount": (
                {
                    "destination": component_mount.get("Destination"),
                    "read_only": not bool(component_mount.get("RW")),
                }
                if component_mount
                else None
            ),
        },
    }


def package_hash(container: str) -> str:
    return subprocess.check_output(
        ["docker", "exec", container, "sh", "-lc", PACKAGE_HASH_COMMAND],
        text=True,
    ).strip()


def pristine_package_hash(image: str) -> str:
    return subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            image,
            "-lc",
            PACKAGE_HASH_COMMAND,
        ],
        text=True,
    ).strip()


def login_and_catalog(
    client: httpx.Client,
    *,
    url: str,
    env: dict[str, str],
) -> dict[str, Any]:
    username = env.get("LANGFLOW_SUPERUSER", "")
    password = env.get("LANGFLOW_SUPERUSER_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("validation container does not expose isolated superuser credentials")
    login = client.post(
        f"{url.rstrip('/')}/api/v1/login",
        data={"username": username, "password": password},
    )
    if login.status_code >= 400:
        raise RuntimeError(f"Langflow login returned HTTP {login.status_code}")
    token = str(login.json().get("access_token") or "")
    if not token:
        raise RuntimeError("Langflow login did not return an access token")
    headers = {"Authorization": f"Bearer {token}"}
    health = client.get(f"{url.rstrip('/')}/health")
    version = client.get(f"{url.rstrip('/')}/api/v1/version", headers=headers)
    catalog = client.get(f"{url.rstrip('/')}/api/v1/all", headers=headers)
    for response, label in ((health, "health"), (version, "version"), (catalog, "catalog")):
        if response.status_code >= 400:
            raise RuntimeError(f"Langflow {label} returned HTTP {response.status_code}")
    serialized = json.dumps(catalog.json(), ensure_ascii=False)
    return {
        "health_ok": True,
        "version": str(
            version.json().get("version")
            or version.json().get("main_version")
            or ""
        ),
        "components": {
            name: name in serialized
            for name in BOI_COMPONENTS
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pure-container", required=True)
    parser.add_argument("--pure-url", required=True)
    parser.add_argument("--bundle-container", required=True)
    parser.add_argument("--bundle-url", required=True)
    parser.add_argument("--expected-image", default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    pure = docker_inspect(args.pure_container)
    bundle = docker_inspect(args.bundle_container)
    expected_image_id = subprocess.check_output(
        ["docker", "image", "inspect", args.expected_image, "--format", "{{.Id}}"],
        text=True,
    ).strip()
    if pure["public"]["status"] != "running" or bundle["public"]["status"] != "running":
        raise RuntimeError("both validation Langflow containers must be running")
    if pure["public"]["image_id"] != expected_image_id:
        raise RuntimeError("pure Langflow container is not using the approved image digest")
    if bundle["public"]["image_id"] != expected_image_id:
        raise RuntimeError("bundle Langflow container is not using the approved image digest")
    if pure["public"]["component_mount"] is not None:
        raise RuntimeError("pure Langflow unexpectedly has a custom component mount")
    mount = bundle["public"]["component_mount"]
    if not mount or not mount["read_only"]:
        raise RuntimeError("BoI component bundle is not mounted read-only")

    pristine_hash = pristine_package_hash(args.expected_image)
    pure_hash = package_hash(args.pure_container)
    bundle_hash = package_hash(args.bundle_container)
    if len({pristine_hash, pure_hash, bundle_hash}) != 1:
        raise RuntimeError("installed Langflow Python package differs from the official image")

    with httpx.Client(timeout=180) as client:
        pure_api = login_and_catalog(client, url=args.pure_url, env=pure["env"])
        bundle_api = login_and_catalog(client, url=args.bundle_url, env=bundle["env"])
    if any(pure_api["components"].values()):
        raise RuntimeError("BoI components appeared in the pure Langflow catalog")
    if not all(bundle_api["components"].values()):
        raise RuntimeError("one or more BoI components are missing from the bundle catalog")

    result = {
        "ok": True,
        "official_image": {
            "reference": args.expected_image,
            "image_id": expected_image_id,
        },
        "package_integrity": {
            "algorithm": "sha256-of-sorted-python-file-sha256",
            "official_image": pristine_hash,
            "pure_runtime": pure_hash,
            "bundle_runtime": bundle_hash,
            "identical": True,
        },
        "pure": {
            **pure["public"],
            "api": pure_api,
        },
        "bundle": {
            **bundle["public"],
            "api": bundle_api,
        },
        "secrets_redacted": True,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        os.chmod(args.output, 0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
