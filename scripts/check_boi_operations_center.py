#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check BoI Operations Center.")
    parser.add_argument("--base-url", default="http://localhost:28000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    query = urlencode({"employee_id": args.employee_id})
    try:
        html = fetch_text(f"{base_url}/ops?{query}")
        overview = fetch_json(f"{base_url}/api/ops/overview?{query}")
        canvas = fetch_json(f"{base_url}/api/ops/canvas?{query}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Operations Center request failed: {exc}", file=sys.stderr)
        return 1

    node_types = {node.get("type") for node in canvas.get("nodes", []) if isinstance(node, dict)}
    edge_kinds = {edge.get("data", {}).get("kind") for edge in canvas.get("edges", []) if isinstance(edge, dict)}
    canvas_text = json.dumps(canvas, ensure_ascii=False)
    checks = {
        "page_title": "BoI Operations Center" in html,
        "react_mount": 'id="boi-ops-center"' in html,
        "react_bundle": "dist/ops-center.js" in html and "dist/ops-center.css" in html,
        "no_svg_fallback": "ops-map-edges" not in html,
        "api_ok": overview.get("ok") is True,
        "api_nodes": isinstance(overview.get("workstream_nodes"), list),
        "api_queue": isinstance(overview.get("priority_queue"), list),
        "api_visual_model": all(
            node.get("size_class") and node.get("visual_state")
            for node in overview.get("workstream_nodes", [])
            if node.get("type") == "sop_workstream"
        ),
        "api_edges": isinstance(overview.get("workstream_edges"), list),
        "canvas_ok": canvas.get("ok") is True,
        "canvas_node_types": {"personNode", "sopWorkstreamNode"}.issubset(node_types),
        "no_static_agent_placeholders": "Agent Office" not in canvas_text and "Evidence Sandbox" not in canvas_text and "Decision Flow" not in canvas_text,
        "canvas_edge_kinds": "assigned_to" in edge_kinds,
    }
    if args.summary:
        print(json.dumps({"checks": checks, "summary": overview.get("summary") or {}, "canvas": canvas.get("performance") or {}}, ensure_ascii=False, indent=2))
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print(f"Operations Center smoke failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("Operations Center smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
