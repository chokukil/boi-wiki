#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def fetch(base_url: str, query: str, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/v2/search?" + urllib.parse.urlencode({"q": query, "limit": 8})
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied URL
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate BoI Agent v2 hybrid retrieval against curated cases.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "agent_v2_search_golden.yaml",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    fixture = yaml.safe_load(args.fixture.read_text(encoding="utf-8")) or {}
    cases = fixture.get("cases") or []
    failures: list[str] = []
    recall_hits = 0
    top3_hits = 0
    details: list[dict[str, Any]] = []
    for case in cases:
        query = str(case.get("query") or "")
        try:
            result = fetch(args.base_url, query, args.timeout)
        except Exception as exc:
            failures.append(f"{query}: {type(exc).__name__}: {exc}")
            continue
        ids = [str(item.get("evidence_id") or "") for item in result.get("items") or []]
        expected = set(str(item) for item in case.get("expected_any") or [])
        authoritative = set(str(item) for item in case.get("authoritative_any") or [])
        recall = bool(expected & set(ids[:8]))
        top3 = bool(authoritative & set(ids[:3]))
        recall_hits += int(recall)
        top3_hits += int(top3)
        details.append({"query": query, "recall_at_8": recall, "authoritative_top_3": top3, "top_3": ids[:3]})

    denominator = max(1, len(cases))
    recall_score = recall_hits / denominator
    top3_score = top3_hits / denominator
    thresholds = fixture.get("thresholds") or {}
    accepted = (
        not failures
        and recall_score >= float(thresholds.get("recall_at_8") or 0.85)
        and top3_score >= float(thresholds.get("authoritative_top_3") or 0.9)
    )
    print(
        json.dumps(
            {
                "accepted": accepted,
                "cases": len(cases),
                "recall_at_8": round(recall_score, 3),
                "authoritative_top_3": round(top3_score, 3),
                "failures": failures,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
