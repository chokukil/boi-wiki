#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check SOP runtime graph contract.")
    parser.add_argument("--base-url", default="http://localhost:28000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    query = urlencode({"employee_id": args.employee_id, "status": "open", "limit": 20})
    try:
        runs = fetch_json(f"{base_url}/api/sop-runs?{query}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"SOP runs request failed: {exc}", file=sys.stderr)
        return 1

    items = runs.get("items") if isinstance(runs.get("items"), list) else []
    run_id = args.run_id or (str(items[0].get("run_id") or "") if items else "")
    if not run_id:
        if args.allow_empty:
            print("No SOP runs available; skipped graph smoke")
            return 0
        print("No SOP runs available for graph smoke", file=sys.stderr)
        return 1

    try:
        graph = fetch_json(f"{base_url}/api/sop-runs/{run_id}/graph?{urlencode({'employee_id': args.employee_id})}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"SOP graph request failed: {exc}", file=sys.stderr)
        return 1
    try:
        page_html = fetch_text(f"{base_url}/sop-runs/{run_id}?{urlencode({'employee_id': args.employee_id})}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"SOP run page request failed: {exc}", file=sys.stderr)
        return 1

    checks = {
        "api_ok": graph.get("ok") is True,
        "run_id": graph.get("run_id") == run_id,
        "nodes": isinstance(graph.get("nodes"), list) and len(graph.get("nodes") or []) > 0,
        "edges": isinstance(graph.get("edges"), list),
        "decision_packet": isinstance(graph.get("decision_packet"), dict) and bool((graph.get("decision_packet") or {}).get("why_assigned")),
        "page_stage_buttons": 'data-stage-node' in page_html and 'role="button"' in page_html,
        "page_stage_panel": 'data-stage-panel-title' in page_html and 'data-stage-panel-summary' in page_html,
        "page_stage_script": 'sop_run.js' in page_html,
    }
    if args.summary:
        print(json.dumps({"checks": checks, "run": graph.get("run"), "decision_packet": graph.get("decision_packet")}, ensure_ascii=False, indent=2))
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print(f"SOP runtime graph smoke failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("SOP runtime graph smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
