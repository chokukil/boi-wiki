#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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


def main() -> int:
    args = parse_args()
    fixture = yaml.safe_load(args.fixture.read_text(encoding="utf-8")) or {}
    scenario_count = sum(len(items) for items in (fixture.get("groups") or {}).values())
    base = args.base_url.rstrip("/")
    params = {"employee_id": args.employee_id}
    failures: list[str] = []
    with httpx.Client(timeout=args.timeout) as client:
        before_response = client.get(f"{base}/api/v2/system/readiness", params=params)
        before_response.raise_for_status()
        before = before_response.json()

        inbox = client.get(f"{base}/api/inbox", params={**params, "limit": 20})
        inbox.raise_for_status()
        items = [item for item in inbox.json().get("items") or [] if item.get("task_ref")]
        snapshot_latencies: list[float] = []
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

        graph_latencies: list[float] = []
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
    before_residency = residency(before)
    after_residency = residency(after)
    if scenario_count != 32:
        failures.append(f"acceptance scenario count must be 32, got {scenario_count}")
    if snapshot_latencies and snapshot_p95 > 500:
        failures.append(f"warm Task snapshot p95 must be <=500ms, got {snapshot_p95}ms")
    if graph_p95 > 200:
        failures.append(f"1-hop graph p95 must be <=200ms, got {graph_p95}ms")
    if after_residency["load_requests"] != before_residency["load_requests"]:
        failures.append("LM Studio load requests changed during acceptance navigation")
    if after_residency["unload_requests"] != before_residency["unload_requests"]:
        failures.append("LM Studio unload requests changed during acceptance navigation")

    report = {
        "ok": not failures,
        "scenario_count": scenario_count,
        "task_snapshot": {
            "status": snapshot_status,
            "samples": len(snapshot_latencies),
            "p50_ms": round(statistics.median(snapshot_latencies), 2) if snapshot_latencies else 0,
            "p95_ms": snapshot_p95,
        },
        "graph_1hop": {
            "samples": len(graph_latencies),
            "p50_ms": round(statistics.median(graph_latencies), 2),
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
