#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return json.loads(response.read().decode("utf-8"))


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
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument("--profile", default="local-full", help="Expected deployment profile.")
    parser.add_argument("--json", action="store_true", help="Print full runtime config JSON.")
    args = parser.parse_args()

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
    if nested_get(body, "boi_agent.backend") != "native":
        failures.append("boi_agent.backend must be native")
    for component in ("router", "status_writer", "composer", "suggestions"):
        if nested_get(body, f"boi_agent.{component}.required") and not nested_get(body, f"boi_agent.{component}.llm_enabled"):
            failures.append(f"boi_agent.{component}.llm_enabled must be true")
    if int(nested_get(body, "boi_agent.llm_concurrency.max_concurrency") or 0) < 1:
        failures.append("boi_agent.llm_concurrency.max_concurrency must be at least 1")
    if float(nested_get(body, "boi_agent.llm_concurrency.queue_timeout_seconds") or 0) <= 0:
        failures.append("boi_agent.llm_concurrency.queue_timeout_seconds must be positive")
    if nested_get(body, "boi_agent.langgraph.required") and not nested_get(body, "boi_agent.langgraph.available"):
        failures.append("boi_agent.langgraph.available must be true")
    if nested_get(body, "event_broker.mode") != "local":
        failures.append(f"event_broker.mode expected 'local', got {nested_get(body, 'event_broker.mode')!r}")
    runtime_readiness = body.get("readiness") if isinstance(body.get("readiness"), dict) else {}
    if runtime_readiness.get("failures"):
        failures.extend(str(item) for item in runtime_readiness.get("failures") or [])

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
        print(f"- git: {git.get('branch', '')} {git.get('revision', '')} dirty={git.get('dirty', False)}")
        print(f"- agent: {nested_get(body, 'boi_agent.backend')} / {nested_get(body, 'boi_agent.router.model')}")
        print(
            "- agent llm queue: "
            f"max={nested_get(body, 'boi_agent.llm_concurrency.max_concurrency')} "
            f"timeout={nested_get(body, 'boi_agent.llm_concurrency.queue_timeout_seconds')}s"
        )
        print(f"- event broker: {nested_get(body, 'event_broker.mode')} {nested_get(body, 'event_broker.topic')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
