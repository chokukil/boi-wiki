#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: float) -> str:
    request = urllib.request.Request(url, headers={"accept": "text/plain,*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return response.read().decode("utf-8", errors="replace")


def nested_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BoI Wiki local-full runtime readiness.")
    parser.add_argument("--base-url", default="http://localhost:28000", help="BoI Wiki base URL.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds; the default allows a cold local model preflight to finish.",
    )
    parser.add_argument("--profile", default="local-full", help="Expected deployment profile.")
    parser.add_argument("--json", action="store_true", help="Print full runtime config JSON.")
    parser.add_argument(
        "--require-agent-v2-full",
        action="store_true",
        help="Fail unless model, embedding index, DeepAgents worker, PAT, and MCP v2 all pass live probes.",
    )
    args = parser.parse_args()

    integration_url = args.base_url.rstrip("/") + "/api/integrations/status"
    integration_deadline = time.monotonic() + args.timeout
    while time.monotonic() < integration_deadline:
        try:
            integration_state = fetch_json(integration_url, min(args.timeout, 10.0))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.25)
            continue
        required_unavailable = [
            item
            for item in integration_state.get("items") or []
            if item.get("required") and not item.get("available")
        ]
        if not required_unavailable:
            break
        time.sleep(0.25)

    url = args.base_url.rstrip("/") + "/api/runtime/config"
    try:
        body = fetch_json(url, args.timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"readiness failed: cannot fetch {url}: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    if nested_get(body, "deployment.profile") != args.profile:
        failures.append(f"deployment.profile expected {args.profile!r}, got {nested_get(body, 'deployment.profile')!r}")
    if not nested_get(body, "build.revision") or nested_get(body, "build.revision") == "unknown":
        failures.append("build.revision must not be unknown")
    if nested_get(body, "git.auto_commit") and not nested_get(body, "git.available"):
        failures.append("git.available must be true when git.auto_commit is true")
    if nested_get(body, "event_broker.mode") != "local":
        failures.append(f"event_broker.mode expected 'local', got {nested_get(body, 'event_broker.mode')!r}")
    if int(nested_get(body, "content.markdown_documents") or nested_get(body, "index.markdown_documents") or 0) <= 0:
        failures.append(f"content.markdown_documents must be greater than 0 for {nested_get(body, 'content.configured_root')!r}")
    if nested_get(body, "content.expected_guide_exists") is False:
        failures.append(f"content.expected_guide_exists must be true at {nested_get(body, 'content.expected_guide_path')!r}")
    runtime_readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    if runtime_readiness.get("failures"):
        failures.extend(str(item) for item in runtime_readiness.get("failures") or [])
    guide_url = args.base_url.rstrip("/") + "/docs/boi:public:boi-wiki-manual:guide:final-operator-guide?employee_id=100001"
    try:
        guide_html = fetch_text(guide_url, args.timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        failures.append(f"cannot fetch final operator guide: {exc}")
    else:
        if "BoI not found" in guide_html or "BoI Wiki 종합 가이드" not in guide_html:
            failures.append("final operator guide route did not render the expected document")
    registration_js_url = args.base_url.rstrip("/") + f"/static/registration.js?v={nested_get(body, 'build.revision') or ''}"
    try:
        registration_js = fetch_text(registration_js_url, args.timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        failures.append(f"cannot fetch registration.js from runtime: {exc}")
    else:
        stale_patterns = (
            "auto_apply_seconds",
            "초 뒤 비어 있는 초안 필드에 자동 적용됩니다",
            "setTimeout(() => applyDraftSuggestion",
        )
        for pattern in stale_patterns:
            if pattern in registration_js:
                failures.append(f"registration.js contains stale auto-apply pattern: {pattern}")

    agent_v2: dict[str, Any] = {}
    acceptance: dict[str, Any] = {}
    try:
        agent_v2 = fetch_json(args.base_url.rstrip("/") + "/api/v2/system/readiness?probe_model=true", args.timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        failures.append(f"cannot fetch Agent v2 readiness: {exc}")
    else:
        dependencies = agent_v2.get("dependencies") if isinstance(agent_v2.get("dependencies"), dict) else {}
        if not agent_v2.get("enabled"):
            failures.append("Agent v2 must be enabled")
        if args.require_agent_v2_full and not agent_v2.get("default"):
            failures.append("Agent v2 must be the default Web surface for full acceptance")
        if not agent_v2.get("ready"):
            failures.append("Agent v2 core readiness must be true")
        if nested_get(agent_v2, "quick_agent.engine") != "langgraph":
            failures.append("Agent v2 Quick Agent must use LangGraph")
        if not dependencies.get("postgres"):
            failures.append("Agent v2 Postgres/pgvector must be ready")
        if not dependencies.get("deep_worker"):
            failures.append("Agent v2 DeepAgents worker heartbeat must be ready")
        if not dependencies.get("pat"):
            failures.append("Agent v2 PAT signing must be ready")
        if dependencies.get("embedding") and not dependencies.get("search_index"):
            failures.append("Agent v2 semantic search index must be fresh when embeddings are enabled")

    try:
        acceptance = fetch_json(args.base_url.rstrip("/") + "/api/v2/harness/acceptance", max(args.timeout, 30.0))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        failures.append(f"cannot fetch Agent v2 acceptance: {exc}")
    else:
        if not acceptance.get("core_accepted"):
            failed = [key for key, value in (acceptance.get("core_checks") or {}).items() if not value]
            failures.append("Agent v2 core acceptance failed: " + ", ".join(failed))
        if args.require_agent_v2_full and not acceptance.get("full_accepted"):
            failed = [key for key, value in (acceptance.get("full_checks") or {}).items() if not value]
            failures.append("Agent v2 full acceptance failed: " + ", ".join(failed))

    if args.json:
        print(json.dumps(body, ensure_ascii=False, indent=2))
    elif failures:
        print("BoI Wiki local-full readiness: FAILED")
        for failure in dict.fromkeys(failures):
            print(f"- {failure}")
    else:
        git = body.get("git") if isinstance(body.get("git"), dict) else {}
        print("BoI Wiki local-full readiness: OK")
        print(f"- revision: {nested_get(body, 'build.revision')}")
        print(f"- content: {nested_get(body, 'content.configured_root')} docs={nested_get(body, 'content.markdown_documents')}")
        print(f"- git: {git.get('branch', '')} {git.get('revision', '')} dirty={git.get('dirty', False)}")
        print(
            "- agent v2: "
            f"ready={agent_v2.get('ready')} core={acceptance.get('core_accepted')} "
            f"full={acceptance.get('full_accepted')}"
        )
        print(f"- event broker: {nested_get(body, 'event_broker.mode')} {nested_get(body, 'event_broker.topic')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
