#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.workflow_materializer import (  # noqa: E402
    RepairCandidate,
    build_enriched_body,
    find_repair_candidates,
    rewrite_legacy_text,
    split_frontmatter_text,
)
import yaml  # noqa: E402


class EnrichmentRepairCandidate(NamedTuple):
    path: Path
    boi_id: str
    employee_id: str
    trace_id: str
    event_id: str


def resolve_boi_root(root: Path) -> Path:
    if root.name == "boi":
        return root
    if (root / "boi").exists():
        return root / "boi"
    return root


def resolve_actions_root(root: Path, actions_root: str | None) -> Path:
    if actions_root:
        return Path(actions_root)
    if root.name == "boi":
        return root.parent / "actions"
    if (root / "actions").exists():
        return root / "actions"
    if (root.parent / "actions").exists():
        return root.parent / "actions"
    return Path("data/actions")


def candidate_payload(candidate: RepairCandidate) -> dict[str, str]:
    return {
        "path": str(candidate.path),
        "boi_id": candidate.boi_id,
        "event_type": candidate.event_type,
    }


def compose_markdown(metadata: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n" + body.strip() + "\n"


def read_action_logs(actions_root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(actions_root.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                row["_log_ref"] = f"action:{path.name}:{line_number}"
                rows.append(row)
    return rows


def is_enriched_langflow_repair_candidate(metadata: dict, body: str, boi_id: str | None = None) -> bool:
    author = metadata.get("author") or {}
    enrichment = metadata.get("enrichment") or {}
    if boi_id and metadata.get("boi_id") != boi_id:
        return False
    return (
        metadata.get("visibility") == "private"
        and str((author or {}).get("agent_id") or "").startswith("boi-writer-")
        and enrichment.get("status") == "enriched"
        and "# Action Results" in body
        and (
            "# Langflow BoI Execution Result" in body
            or "BoI Write Result" in body
            or "**R |" in body
        )
    )


def find_enrichment_repair_candidates(root: Path, boi_id: str | None = None) -> list[EnrichmentRepairCandidate]:
    candidates: list[EnrichmentRepairCandidate] = []
    for path in sorted(root.glob("private/*/*.md")):
        try:
            metadata, body = split_frontmatter_text(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not is_enriched_langflow_repair_candidate(metadata, body, boi_id=boi_id):
            continue
        source_event = metadata.get("source_event") or {}
        candidates.append(
            EnrichmentRepairCandidate(
                path=path,
                boi_id=str(metadata.get("boi_id") or ""),
                employee_id=str(metadata.get("owner") or path.parent.name),
                trace_id=str(source_event.get("trace_id") or ""),
                event_id=str(source_event.get("event_id") or ""),
            )
        )
    return candidates


def enrichment_candidate_payload(candidate: EnrichmentRepairCandidate, action_count: int = 0) -> dict[str, str | int]:
    return {
        "path": str(candidate.path),
        "boi_id": candidate.boi_id,
        "employee_id": candidate.employee_id,
        "trace_id": candidate.trace_id,
        "event_id": candidate.event_id,
        "action_count": action_count,
    }


def dispatch_result_for_candidate(candidate: EnrichmentRepairCandidate, action_rows: list[dict]) -> dict:
    results = []
    for row in action_rows:
        if candidate.trace_id and row.get("trace_id") != candidate.trace_id:
            continue
        if candidate.boi_id and row.get("boi_id") != candidate.boi_id:
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        if not result:
            result = {"status": row.get("status"), "request_id": row.get("request_id")}
        results.append(
            {
                "action_key": row.get("action_key"),
                "type": row.get("action_type"),
                "connector_kind": row.get("connector_kind"),
                "doc_ref": row.get("doc_ref"),
                "request_id": row.get("request_id"),
                "_log_ref": row.get("_log_ref"),
                "result": result,
                "status_code": row.get("status_code"),
                "error": row.get("error"),
            }
        )
    return {"ok": True, "status": "dispatched", "boi_id": candidate.boi_id, "results": results}


def rewrite_enriched_text(candidate: EnrichmentRepairCandidate, action_rows: list[dict]) -> tuple[str, int]:
    metadata, body = split_frontmatter_text(candidate.path.read_text(encoding="utf-8"))
    dispatch_result = dispatch_result_for_candidate(candidate, action_rows)
    request_to_ref = {
        str(row.get("request_id") or ""): str(row.get("_log_ref") or "")
        for row in action_rows
        if row.get("request_id")
    }

    def raw_url_resolver(request_id: str, raw_log_ref: str) -> str:
        ref = raw_log_ref or request_to_ref.get(request_id, "")
        return f"/actions/raw/{quote(ref, safe='')}?employee_id={candidate.employee_id}" if ref else ""

    rewritten_body, sections = build_enriched_body(body, dispatch_result, raw_url_resolver=raw_url_resolver)
    metadata["enrichment"] = {
        **(metadata.get("enrichment") or {}),
        "repair": "langflow-summary-v1",
        "sections_updated": sections,
    }
    return compose_markdown(metadata, rewritten_body), len(dispatch_result.get("results") or [])


def apply_enrichment_repair(candidate: EnrichmentRepairCandidate, action_rows: list[dict]) -> dict[str, str | int]:
    rewritten, action_count = rewrite_enriched_text(candidate, action_rows)
    original = candidate.path.read_text(encoding="utf-8")
    backup_path = candidate.path.with_suffix(candidate.path.suffix + ".langflow-enrichment.bak")
    if not backup_path.exists():
        backup_path.write_text(original, encoding="utf-8")
    candidate.path.write_text(rewritten, encoding="utf-8")
    return {**enrichment_candidate_payload(candidate, action_count=action_count), "backup_path": str(backup_path)}


def apply_repair(candidate: RepairCandidate) -> dict[str, str]:
    original = candidate.path.read_text(encoding="utf-8")
    rewritten = rewrite_legacy_text(original)
    backup_path = candidate.path.with_suffix(candidate.path.suffix + ".legacy-boilerplate.bak")
    if not backup_path.exists():
        backup_path.write_text(original, encoding="utf-8")
    candidate.path.write_text(rewritten, encoding="utf-8")
    return {**candidate_payload(candidate), "backup_path": str(backup_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair legacy generated private workflow BoI boilerplate.")
    parser.add_argument("--root", default="data/boi", help="BoI markdown root, or data root containing boi/")
    parser.add_argument("--actions-root", default=None, help="Action log root. Defaults to sibling actions/ under the data root.")
    parser.add_argument("--repair-enrichment", action="store_true", help="Repair enriched Langflow Action Results/Analysis Draft sections.")
    parser.add_argument("--boi-id", default="", help="Limit enrichment repair to one BoI id.")
    parser.add_argument("--apply", action="store_true", help="Rewrite candidate files after writing .legacy-boilerplate.bak backups")
    parser.add_argument("--dry-run", action="store_true", help="Only list candidates. This is the default.")
    args = parser.parse_args()

    root = Path(args.root)
    boi_root = resolve_boi_root(root)
    if args.repair_enrichment:
        actions_root = resolve_actions_root(root, args.actions_root)
        action_rows = read_action_logs(actions_root)
        candidates = find_enrichment_repair_candidates(boi_root, boi_id=args.boi_id or None)
        if args.apply:
            repaired = [apply_enrichment_repair(candidate, action_rows) for candidate in candidates]
            payload = {
                "ok": True,
                "mode": "apply-enrichment",
                "root": str(boi_root),
                "actions_root": str(actions_root),
                "count": len(repaired),
                "items": repaired,
            }
        else:
            payload = {
                "ok": True,
                "mode": "dry-run-enrichment",
                "root": str(boi_root),
                "actions_root": str(actions_root),
                "count": len(candidates),
                "items": [
                    enrichment_candidate_payload(candidate, action_count=len(dispatch_result_for_candidate(candidate, action_rows).get("results") or []))
                    for candidate in candidates
                ],
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    candidates = find_repair_candidates(boi_root)
    if args.apply:
        repaired = [apply_repair(candidate) for candidate in candidates]
        payload = {"ok": True, "mode": "apply", "root": str(boi_root), "count": len(repaired), "items": repaired}
    else:
        payload = {
            "ok": True,
            "mode": "dry-run",
            "root": str(boi_root),
            "count": len(candidates),
            "items": [candidate_payload(candidate) for candidate in candidates],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
