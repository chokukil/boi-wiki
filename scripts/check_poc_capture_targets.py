#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = ROOT / "artifacts" / "boi-poc" / "capture-targets.json"
DEFAULT_SERVICE_TOKEN = "dev-service-token-change-me"
DEFAULT_LANGFLOW_API_KEY = "dev-langflow-key-change-me"


def load_targets(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"capture targets file has no targets: {path}")
    return payload


def langflow_flow_ids(client: httpx.Client, langflow_base: str, api_key: str) -> set[str]:
    response = client.get(f"{langflow_base.rstrip('/')}/api/v1/flows/", headers={"x-api-key": api_key})
    response.raise_for_status()
    flows = response.json()
    if not isinstance(flows, list):
        raise RuntimeError("Langflow flows API did not return a list")
    return {str(flow.get("id")) for flow in flows if isinstance(flow, dict) and flow.get("id")}


def expected_text_for_target(target: dict[str, Any]) -> str:
    target_id = str(target.get("id") or "")
    if target_id == "event_stream":
        return "trace-609660cf137c4946aaa833c891f704b7"
    if target_id == "action_logs":
        return "Workflow Status"
    if target_id == "private_boi":
        return "boi:private:100001:20260619014436:7ff90d"
    if target_id == "event_type_catalog":
        return "equipment.alarm.raised.v1"
    if target_id == "sop_library":
        return "public"
    return ""


def check_boi_url(client: httpx.Client, target: dict[str, Any], service_token: str) -> dict[str, Any]:
    url = str(target["url"])
    response = client.get(
        url,
        headers={
            "x-service-token": service_token,
            "Accept": "text/html,application/json",
        },
        follow_redirects=False,
    )
    ok = response.status_code == 200
    reason = ""
    expected = expected_text_for_target(target)
    if ok and expected and expected not in response.text:
        ok = False
        reason = f"expected text not found: {expected}"
    if ok and response.headers.get("content-type", "").startswith("application/json") and '"detail"' in response.text:
        ok = False
        reason = "target returned JSON error detail"
    if not ok and not reason:
        reason = f"HTTP {response.status_code}"
    return {
        "id": target.get("id"),
        "url": url,
        "status_code": response.status_code,
        "ok": ok,
        "reason": reason,
    }


def check_langflow_url(client: httpx.Client, target: dict[str, Any], api_key: str) -> dict[str, Any]:
    parsed = urlparse(str(target["url"]))
    flow_id = Path(parsed.path).name
    base = f"{parsed.scheme}://{parsed.netloc}"
    ids = langflow_flow_ids(client, base, api_key)
    ok = flow_id in ids
    return {
        "id": target.get("id"),
        "url": target.get("url"),
        "flow_id": flow_id,
        "ok": ok,
        "reason": "" if ok else "flow id not found in Langflow API",
    }


def check_generic_url(client: httpx.Client, target: dict[str, Any]) -> dict[str, Any]:
    response = client.get(str(target["url"]), follow_redirects=False)
    ok = 200 <= response.status_code < 400
    return {
        "id": target.get("id"),
        "url": target.get("url"),
        "status_code": response.status_code,
        "ok": ok,
        "reason": "" if ok else f"HTTP {response.status_code}",
    }


def check_target(client: httpx.Client, target: dict[str, Any], service_token: str, langflow_api_key: str) -> dict[str, Any]:
    parsed = urlparse(str(target["url"]))
    host = parsed.netloc
    if host.endswith(":28000") or host.endswith(":8000"):
        return check_boi_url(client, target, service_token)
    if host.endswith(":7860") and parsed.path.startswith("/flow/"):
        return check_langflow_url(client, target, langflow_api_key)
    return check_generic_url(client, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight PoC screenshot capture URLs without browser automation.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--service-token", default=os.getenv("SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", DEFAULT_LANGFLOW_API_KEY))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON report output path.")
    args = parser.parse_args()

    payload = load_targets(args.targets)
    with httpx.Client(timeout=args.timeout) as client:
        results = [
            check_target(client, target, args.service_token, args.langflow_api_key)
            for target in payload["targets"]
        ]
    report = {
        "ok": all(result["ok"] for result in results),
        "target_count": len(results),
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
