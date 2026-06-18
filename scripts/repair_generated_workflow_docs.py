#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.workflow_materializer import (  # noqa: E402
    RepairCandidate,
    find_repair_candidates,
    rewrite_legacy_text,
)


def resolve_boi_root(root: Path) -> Path:
    if root.name == "boi":
        return root
    if (root / "boi").exists():
        return root / "boi"
    return root


def candidate_payload(candidate: RepairCandidate) -> dict[str, str]:
    return {
        "path": str(candidate.path),
        "boi_id": candidate.boi_id,
        "event_type": candidate.event_type,
    }


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
    parser.add_argument("--apply", action="store_true", help="Rewrite candidate files after writing .legacy-boilerplate.bak backups")
    parser.add_argument("--dry-run", action="store_true", help="Only list candidates. This is the default.")
    args = parser.parse_args()

    boi_root = resolve_boi_root(Path(args.root))
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
