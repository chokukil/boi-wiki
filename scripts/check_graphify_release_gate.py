#!/usr/bin/env python3
"""Run the optional Graphify release gate against an actual code corpus."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "1")

from boi_api.app.main import AGENT_V2_SERVICE
from boi_api.app.v2.model_gateway import lmstudio_model_residency_state
from boi_api.app.v2.models import KnowledgeSourceCreateRequest, KnowledgeSourceRollbackRequest, Principal


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "evidence.py").write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class Evidence:\n"
        "    source_ref: str\n\n"
        "def verify_evidence(item: Evidence) -> bool:\n"
        "    return bool(item.source_ref)\n",
        encoding="utf-8",
    )
    (root / "workflow.py").write_text(
        "from evidence import Evidence, verify_evidence\n\n"
        "def complete_task(source_ref: str) -> bool:\n"
        "    return verify_evidence(Evidence(source_ref=source_ref))\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    parser.add_argument("--timeout-seconds", type=float, default=180)
    args = parser.parse_args()
    service = AGENT_V2_SERVICE
    principal = Principal(
        employee_id="100001",
        display_name="Graphify Release Gate",
        auth_source="release_gate",
        roles=["boi.viewer", "boi.editor", "boi.admin"],
        scopes=["boi.read", "boi.draft", "boi.admin"],
    )
    # Graphify intentionally ignores code below hidden directories. Use a
    # non-hidden isolated corpus so the gate matches an actual source checkout.
    fixture = ROOT / "adapter-release-input" / "graphify-release-gate"
    shutil.rmtree(fixture, ignore_errors=True)
    build_fixture(fixture)
    executable = shutil.which("graphify")
    before = lmstudio_model_residency_state(service.settings)
    report: dict = {
        "ok": False,
        "adapter": "graphify",
        "executable": executable or "",
        "input_path": str(fixture),
    }
    if not executable:
        report["error"] = "graphify_not_installed"
    else:
        source = service.knowledge.create_source(
            principal,
            KnowledgeSourceCreateRequest(
                name=f"Graphify release gate {int(time.time())}",
                source_kind="graphify",
                location=str(fixture),
                visibility="private",
                adapter_config={"timeout_seconds": args.timeout_seconds},
            ),
        )
        job = service.knowledge.sync_source(principal, source["source_id"])["job"]
        deadline = time.monotonic() + args.timeout_seconds + 30
        while job.get("status") not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
            time.sleep(0.1)
            job = service.knowledge.source_job(principal, job["job_id"])
        manifest = job.get("manifest") if isinstance(job.get("manifest"), dict) else {}
        validation = manifest.get("validation_report") if isinstance(manifest.get("validation_report"), dict) else {}
        rollback = {}
        if job.get("status") == "completed":
            rollback = service.knowledge.rollback_source_import(
                principal,
                source["source_id"],
                KnowledgeSourceRollbackRequest(user_confirmed=True, reason="실제 Graphify import rollback 검증"),
            )
        after = lmstudio_model_residency_state(service.settings)
        report.update(
            {
                "source_id": source["source_id"],
                "job_id": job.get("job_id"),
                "job_status": job.get("status"),
                "job_stage": job.get("stage"),
                "error": job.get("error") or "",
                "node_count": validation.get("node_count", 0),
                "edge_count": validation.get("edge_count", 0),
                "canonical_changed": validation.get("canonical_changed"),
                "raw_artifact_url": manifest.get("raw_artifact_url") or "",
                "rollback": rollback,
                "model_residency_before": before,
                "model_residency_after": after,
            }
        )
        report["ok"] = bool(
            job.get("status") == "completed"
            and int(validation.get("node_count") or 0) > 0
            and int(validation.get("edge_count") or 0) > 0
            and validation.get("canonical_changed") is False
            and int(rollback.get("removed_nodes") or 0) == int(validation.get("node_count") or 0)
            and not before.get("load_requests")
            and not after.get("load_requests")
            and int(before.get("unload_requests") or 0) == 0
            and int(after.get("unload_requests") or 0) == 0
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    shutil.rmtree(fixture, ignore_errors=True)
    try:
        fixture.parent.rmdir()
    except OSError:
        pass
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
