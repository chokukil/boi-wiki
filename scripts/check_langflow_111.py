#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value or "").split("-", 1)[0].split(".")
    if len(parts) < 2:
        raise ValueError(f"invalid Langflow version: {value!r}")
    normalized = [int(part) for part in parts[:3]]
    while len(normalized) < 3:
        normalized.append(0)
    return tuple(normalized)  # type: ignore[return-value]


def assert_111(value: str) -> None:
    parsed = version_tuple(value)
    if not ((1, 11, 0) <= parsed < (1, 12, 0)):
        raise RuntimeError(f"Langflow 1.11.x is required; received {value}")


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
    allowed = expected or {200}
    if response.status_code not in allowed:
        raise RuntimeError(f"{method} {url} returned {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the isolated Langflow 1.11 Agent Playground contract.")
    parser.add_argument("--url", default="http://localhost:7867")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--expect-user", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--flow", default="")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    headers = {"x-api-key": args.api_key} if args.api_key else {}
    checks: dict[str, Any] = {}
    with httpx.Client(timeout=60) as client:
        version = request_json(client, "GET", f"{base_url}/api/v1/version", headers=headers)
        exact_version = str((version or {}).get("version") or (version or {}).get("main_version") or "")
        assert_111(exact_version)
        checks["version"] = exact_version

        if not args.api_key:
            checks["authenticated_contracts"] = "skipped: --api-key not supplied"
            print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False, indent=2))
            return 0

        whoami = request_json(client, "GET", f"{base_url}/api/v1/users/whoami", headers=headers)
        username = str((whoami or {}).get("username") or "")
        if args.expect_user and username != args.expect_user:
            raise RuntimeError(f"API key owner mismatch: expected {args.expect_user}, received {username}")
        checks["user"] = {"id": whoami.get("id"), "username": username}

        projects = request_json(client, "GET", f"{base_url}/api/v1/projects/", headers=headers)
        checks["projects"] = [str(item.get("name") or "") for item in projects if isinstance(item, dict)]
        if args.project and args.project not in checks["projects"]:
            raise RuntimeError(f"project not found: {args.project}")

        variables = request_json(client, "GET", f"{base_url}/api/v1/variables/", headers=headers)
        checks["credential_variables"] = [
            str(item.get("name") or "")
            for item in variables
            if isinstance(item, dict) and str(item.get("type") or "").lower() == "credential"
        ]
        checks["credential_values_redacted"] = all(
            item.get("value") in (None, "")
            for item in variables
            if isinstance(item, dict) and str(item.get("type") or "").lower() == "credential"
        )
        if not checks["credential_values_redacted"]:
            raise RuntimeError("Langflow returned a raw Credential Variable value")

        flows = request_json(client, "GET", f"{base_url}/api/v1/flows/", headers=headers)
        checks["flows"] = [
            {"id": item.get("id"), "name": item.get("name"), "endpoint_name": item.get("endpoint_name")}
            for item in flows
            if isinstance(item, dict)
        ]
        if args.flow and not any(
            args.flow in {str(item.get("id") or ""), str(item.get("endpoint_name") or ""), str(item.get("name") or "")}
            for item in flows
            if isinstance(item, dict)
        ):
            raise RuntimeError(f"flow not found: {args.flow}")
        if args.run:
            if not args.flow:
                raise RuntimeError("--run requires --flow")
            run_result = request_json(
                client,
                "POST",
                f"{base_url}/api/v1/run/{args.flow}",
                headers={**headers, "Content-Type": "application/json"},
                json={"input_value": "BoI Agent Playground 1.11 smoke", "input_type": "chat", "output_type": "chat"},
            )
            checks["run"] = {"session_id": (run_result or {}).get("session_id"), "ok": True}

    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc
