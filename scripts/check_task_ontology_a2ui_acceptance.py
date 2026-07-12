#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import statistics
import time
from pathlib import Path
from typing import Any

import httpx
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests/fixtures/task_ontology_a2ui_acceptance.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Task, Ontology and A2UI acceptance contracts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--skip-deterministic", action="store_true")
    parser.add_argument("--deterministic-timeout", type=float, default=180.0)
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 2)


def timed(client: httpx.Client, method: str, url: str, **kwargs: Any) -> tuple[httpx.Response, float]:
    started = time.monotonic()
    response = client.request(method, url, **kwargs)
    return response, (time.monotonic() - started) * 1000


def residency(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("model_residency") if isinstance(payload.get("model_residency"), dict) else {}
    return {
        "loaded_models": sorted(str(item) for item in state.get("loaded_models") or []),
        "load_requests": list(state.get("load_requests") or []),
        "unload_requests": int(state.get("unload_requests") or 0),
    }


def execute_handlers(fixture: dict[str, Any], timeout: float) -> tuple[list[dict[str, Any]], list[str]]:
    scenarios = [item for items in (fixture.get("groups") or {}).values() for item in items]
    handlers = sorted({str(item.get("handler") or "") for item in scenarios if item.get("handler")})
    results_by_handler: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for handler in handlers:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                ["pytest", "-s", "-q", handler],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            passed = completed.returncode == 0
            output = (completed.stdout + "\n" + completed.stderr).strip()[-4000:]
        except subprocess.TimeoutExpired as exc:
            passed = False
            output = f"timeout after {timeout}s: {(exc.stdout or '')} {(exc.stderr or '')}"[-4000:]
        results_by_handler[handler] = {
            "handler": handler,
            "passed": passed,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "output": output,
        }
    scenario_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        handler = str(scenario.get("handler") or "")
        handler_result = results_by_handler.get(handler)
        passed = bool(handler_result and handler_result["passed"])
        if not handler:
            failures.append(f"{scenario.get('id')}: executable handler is missing")
        elif not passed:
            failures.append(f"{scenario.get('id')}: handler failed: {handler}")
        scenario_results.append(
            {
                "scenario_id": scenario.get("id"),
                "handler": handler,
                "passed": passed,
                "duration_ms": handler_result.get("duration_ms", 0) if handler_result else 0,
            }
        )
    return scenario_results, failures


def main() -> int:
    args = parse_args()
    fixture = yaml.safe_load(args.fixture.read_text(encoding="utf-8")) or {}
    scenario_count = sum(len(items) for items in (fixture.get("groups") or {}).values())
    expected_scenario_count = int(fixture.get("expected_scenarios") or scenario_count)
    base = args.base_url.rstrip("/")
    params = {"employee_id": args.employee_id}
    failures: list[str] = []
    scenario_results: list[dict[str, Any]] = []
    if not args.skip_deterministic:
        scenario_results, handler_failures = execute_handlers(fixture, args.deterministic_timeout)
        failures.extend(handler_failures)

    snapshot_latencies: list[float] = []
    graph_latencies: list[float] = []
    snapshot_status = "skipped"
    before_residency: dict[str, Any] = {}
    after_residency: dict[str, Any] = {}
    if not args.skip_runtime:
        with httpx.Client(timeout=args.timeout) as client:
            before_response = client.get(f"{base}/api/v2/system/readiness", params=params)
            before_response.raise_for_status()
            before = before_response.json()

            inbox = client.get(f"{base}/api/inbox", params={**params, "limit": 20})
            inbox.raise_for_status()
            items = [item for item in inbox.json().get("items") or [] if item.get("task_ref")]
            snapshot_status = "not_available"
            if items:
                task_ref = str(items[0]["task_ref"])
                for _ in range(5):
                    response, latency = timed(
                        client,
                        "GET",
                        f"{base}/api/tasks/{task_ref}/execution-snapshot",
                        params=params,
                    )
                    response.raise_for_status()
                    snapshot_latencies.append(latency)
                snapshot_status = "ready"

            graph_payload = {
                "focal_entities": ["boi:public:sop:equipment-abnormal-response"],
                "query_kind": "neighbors",
                "depth": 1,
                "limit": 80,
                "presentation": "auto",
            }
            for _ in range(5):
                response, latency = timed(
                    client,
                    "POST",
                    f"{base}/api/v2/knowledge-graph/query",
                    params=params,
                    json=graph_payload,
                )
                response.raise_for_status()
                graph_latencies.append(latency)

            after_response = client.get(f"{base}/api/v2/system/readiness", params=params)
            after_response.raise_for_status()
            after = after_response.json()

    snapshot_p95 = percentile(snapshot_latencies, 0.95)
    graph_p95 = percentile(graph_latencies, 0.95)
    if not args.skip_runtime:
        before_residency = residency(before)
        after_residency = residency(after)
    if scenario_count != expected_scenario_count:
        failures.append(
            f"acceptance scenario count must be {expected_scenario_count}, got {scenario_count}"
        )
    if snapshot_latencies and snapshot_p95 > 500:
        failures.append(f"warm Task snapshot p95 must be <=500ms, got {snapshot_p95}ms")
    if graph_latencies and graph_p95 > 200:
        failures.append(f"1-hop graph p95 must be <=200ms, got {graph_p95}ms")
    if before_residency and after_residency["load_requests"] != before_residency["load_requests"]:
        failures.append("LM Studio load requests changed during acceptance navigation")
    if before_residency and after_residency["unload_requests"] != before_residency["unload_requests"]:
        failures.append("LM Studio unload requests changed during acceptance navigation")

    report = {
        "ok": not failures,
        "scenario_count": scenario_count,
        "expected_scenario_count": expected_scenario_count,
        "deterministic": {
            "executed": not args.skip_deterministic,
            "passed": sum(1 for item in scenario_results if item["passed"]),
            "total": len(scenario_results),
            "scenarios": scenario_results,
        },
        "task_snapshot": {
            "status": snapshot_status,
            "samples": len(snapshot_latencies),
            "p50_ms": round(statistics.median(snapshot_latencies), 2) if snapshot_latencies else 0,
            "p95_ms": snapshot_p95,
        },
        "graph_1hop": {
            "samples": len(graph_latencies),
            "p50_ms": round(statistics.median(graph_latencies), 2) if graph_latencies else 0,
            "p95_ms": graph_p95,
        },
        "model_residency": {"before": before_residency, "after": after_residency},
        "failures": failures,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
