#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def run_harness_eval_suite() -> dict[str, Any]:
    """§10 P1-11: `scripts/run_harness_evals.sh`를 실행해 골든 태스크 회귀를 재검증한다.

    이 readiness 체크와 같은 스타일로 (ok, 요약 메시지, 실패 시 tail 로그) 반환한다.
    실행 자체가 안 된다면(스크립트 부재/권한 등) 그것도 실패로 취급한다.
    """
    script_path = REPO_ROOT / "scripts" / "run_harness_evals.sh"
    if not script_path.exists():
        return {"ok": False, "summary": f"harness eval runner missing: {script_path}"}
    try:
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "summary": f"harness eval runner failed to start: {exc}"}
    output = (result.stdout or "") + (result.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-15:])
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "summary": tail or f"exit code {result.returncode}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BoI Wiki local-full runtime readiness.")
    parser.add_argument("--base-url", default="http://localhost:28000", help="BoI Wiki base URL.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument("--profile", default="local-full", help="Expected deployment profile.")
    parser.add_argument("--json", action="store_true", help="Print full runtime config JSON.")
    parser.add_argument(
        "--harness-evals",
        action="store_true",
        help="Also run scripts/run_harness_evals.sh (tests/harness_evals golden-task regression) and fold the result into the readiness summary (§10 P1-11).",
    )
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
    for component in ("router", "status_writer", "composer", "suggestions", "work_context_narrative"):
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

    harness_evals: dict[str, Any] | None = None
    if args.harness_evals:
        harness_evals = run_harness_eval_suite()
        body["harness_evals"] = harness_evals
        if not harness_evals["ok"]:
            failures.append(f"harness eval suite failed (scripts/run_harness_evals.sh): {harness_evals['summary']}")

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
        if harness_evals is not None:
            print(f"- harness evals: OK ({harness_evals['summary'].splitlines()[-1] if harness_evals['summary'] else 'passed'})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
