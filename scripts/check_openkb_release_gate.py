#!/usr/bin/env python3
"""Run the optional OpenKB release gate against an actual PDF and preloaded LM Studio."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_boi_model_environment(path: Path) -> None:
    """Load only the local model settings without evaluating dotenv as shell code."""

    allowed_prefixes = ("BOI_V2_MODEL", "BOI_LLM_", "BOI_AGENT_LLM_", "BOI_KNOWLEDGE_")
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (item.strip() for item in line.split("=", 1))
        if not key.startswith(allowed_prefixes) or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


load_boi_model_environment(ROOT / ".env")

# Settings and the adapter worker are constructed while importing the app.
# Enable the optional adapter before that import so the release gate exercises
# the same path as an explicitly enabled deployment.
os.environ.setdefault("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "1")

from boi_api.app.main import AGENT_V2_SERVICE
from boi_api.app.v2.models import KnowledgeSourceCreateRequest, Principal


def build_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=A4)
    document.setTitle("Equipment Alarm Evidence Review")
    document.drawString(72, 780, "Equipment Alarm Evidence Review")
    document.drawString(72, 748, "Verify the alarm timestamp, trend window, raw data checksum, and operator action.")
    document.drawString(72, 716, "A task is complete only after evidence and the human decision are recorded.")
    document.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    parser.add_argument("--timeout-seconds", type=float, default=300)
    args = parser.parse_args()
    service = AGENT_V2_SERVICE
    principal = Principal(
        employee_id="100001",
        display_name="OpenKB Release Gate",
        auth_source="release_gate",
        roles=["boi.viewer", "boi.editor", "boi.admin"],
        scopes=["boi.read", "boi.draft", "boi.admin"],
    )
    input_path = service.settings.runtime_root / "knowledge-adapters" / "release-gate" / "alarm-evidence.pdf"
    build_pdf(input_path)
    executable = shutil.which("openkb")
    report: dict = {
        "ok": False,
        "adapter": "openkb",
        "executable": executable or "",
        "input_path": str(input_path),
        "model_endpoint": service.settings.model_base_url,
        "model_management_requests": 0,
    }
    if not executable:
        report["error"] = "openkb_not_installed"
    else:
        source = service.knowledge.create_source(
            principal,
            KnowledgeSourceCreateRequest(
                name=f"OpenKB release gate {int(time.time())}",
                source_kind="openkb",
                location=str(input_path),
                visibility="private",
                adapter_config={
                    "model": f"openai/{service.settings.model_name}",
                    "language": "ko",
                    "timeout_seconds": args.timeout_seconds,
                },
            ),
        )
        job = service.knowledge.sync_source(principal, source["source_id"])["job"]
        deadline = time.monotonic() + args.timeout_seconds + 30
        while job.get("status") not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
            time.sleep(0.25)
            job = service.knowledge.source_job(principal, job["job_id"])
        manifest = job.get("manifest") if isinstance(job.get("manifest"), dict) else {}
        candidate_ids = list(manifest.get("candidate_ids") or [])
        candidates = [service.store.get("knowledge_candidates", candidate_id) or {} for candidate_id in candidate_ids]
        navigation_candidates = [
            item.get("title") for item in candidates
            if str(item.get("title") or "").strip().lower() in {"index", "log", "agents"}
        ]
        gateway = job.get("compatibility_gateway") if isinstance(job.get("compatibility_gateway"), dict) else {}
        model_management_requests = int(gateway.get("load_requests") or 0) + int(gateway.get("unload_requests") or 0)
        report.update(
            {
                "source_id": source["source_id"],
                "job_id": job.get("job_id"),
                "job_status": job.get("status"),
                "job_stage": job.get("stage"),
                "error": job.get("error") or "",
                "candidate_ids": candidate_ids,
                "candidate_titles": [item.get("title") for item in candidates],
                "navigation_candidates": navigation_candidates,
                "compatibility_gateway": gateway,
                "model_management_requests": model_management_requests,
                "canonical_changed": (manifest.get("validation_report") or {}).get("canonical_changed"),
            }
        )
        report["ok"] = bool(
            job.get("status") == "completed"
            and candidate_ids
            and not navigation_candidates
            and model_management_requests == 0
            and (manifest.get("validation_report") or {}).get("canonical_changed") is False
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
