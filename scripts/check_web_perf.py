#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class Target:
    name: str
    path: str
    max_ms: float
    max_bytes: int | None = None


def fetch(base_url: str, path: str) -> tuple[int, int, float]:
    url = base_url.rstrip("/") + path
    req = Request(url, headers={"Accept": "text/html,application/json"})
    started = time.perf_counter()
    with urlopen(req, timeout=30) as response:
        body = response.read()
        status = response.status
    elapsed_ms = (time.perf_counter() - started) * 1000
    return status, len(body), elapsed_ms


def measure(base_url: str, target: Target, samples: int) -> dict[str, object]:
    measurements = []
    for _ in range(samples):
        status, size, elapsed_ms = fetch(base_url, target.path)
        measurements.append({"status": status, "bytes": size, "ms": elapsed_ms})
    warm = measurements[-1]
    ok = warm["status"] == 200 and warm["ms"] <= target.max_ms
    if target.max_bytes is not None:
        ok = ok and warm["bytes"] <= target.max_bytes
    return {
        "name": target.name,
        "path": target.path,
        "max_ms": target.max_ms,
        "max_bytes": target.max_bytes,
        "ok": ok,
        "samples": measurements,
        "warm": warm,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure BoI Wiki web route performance.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when a target exceeds its threshold.")
    args = parser.parse_args()

    employee_id = quote(args.employee_id, safe="")
    trace_id = quote(args.trace_id, safe="")
    targets = [
        Target("events", f"/events?employee_id={employee_id}", max_ms=1000, max_bytes=300_000),
        Target(
            "events_trace",
            f"/events?employee_id={employee_id}&trace_id={trace_id}" if trace_id else f"/events?employee_id={employee_id}&limit=20",
            max_ms=700,
        ),
        Target(
            "sop_detail",
            f"/docs/boi:public:sop:equipment-abnormal-response?employee_id={employee_id}&folder=public%2Fsop",
            max_ms=800,
        ),
        Target(
            "sop_graph_api",
            f"/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id={employee_id}",
            max_ms=200,
        ),
    ]
    results = [measure(args.base_url, target, max(1, args.samples)) for target in targets]
    print(json.dumps({"ok": all(item["ok"] for item in results), "results": results}, ensure_ascii=False, indent=2))
    return 1 if args.strict and not all(item["ok"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
