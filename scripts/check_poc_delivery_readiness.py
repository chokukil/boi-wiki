#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_SUMMARY = ROOT / "outputs" / "manual-20260619" / "e2e-evidence" / "summary.json"
DEFAULT_CAPTURE_TARGETS = ROOT / "artifacts" / "boi-poc" / "capture-targets.json"
DEFAULT_CAPTURE_MANIFEST = ROOT / "artifacts" / "boi-poc" / "capture-manifest.json"
DEFAULT_ARTIFACT_PPTX = (
    ROOT
    / "outputs"
    / "manual-20260619"
    / "presentations"
    / "boi-e2e-evidence"
    / "output"
    / "boi-wiki-e2e-evidence-brief.pptx"
)
DEFAULT_OUTPUT = ROOT / "outputs" / "manual-20260619" / "e2e-evidence" / "delivery-readiness.json"
DEFAULT_SERVICE_TOKEN = "dev-service-token-change-me"
DEFAULT_LANGFLOW_API_KEY = "dev-langflow-key-change-me"
REQUIRED_LANGFLOW_ACTIONS = {"langflow.boi.reference_flow", "langflow.equipment.stage_analysis"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def project_path(path: str | Path) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else ROOT / resolved


def compact_stdout(stdout: str, limit: int = 4000) -> str:
    text = stdout.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit // 2]}\n...\n{text[-limit // 2 :]}"


def parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": compact_stdout(completed.stdout),
        "json": parse_json_stdout(completed.stdout),
    }


def evaluate_e2e_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    blockers: list[str] = []
    if not summary:
        return {"ok": False, "trace_id": "", "blockers": ["E2E evidence summary is missing"]}

    trace_id = str(summary.get("trace_id") or "")
    event_count = int(summary.get("event_count") or 0)
    action_count = int(summary.get("action_count") or 0)
    generated_doc_count = int(summary.get("generated_doc_count") or 0)
    manual_handoff_count = int(summary.get("manual_handoff_count") or 0)
    failed_count = int(summary.get("failed_count") or 0)
    langflow_actions = summary.get("langflow_actions") if isinstance(summary.get("langflow_actions"), list) else []
    langflow_keys = {str(item.get("action_key")) for item in langflow_actions if isinstance(item, dict)}
    langflow_bad = [
        str(item.get("action_key") or "unknown")
        for item in langflow_actions
        if isinstance(item, dict) and item.get("status") != "langflow_invoked"
    ]

    if not trace_id:
        blockers.append("E2E trace_id is missing")
    if event_count < 4:
        blockers.append(f"E2E event count is too low: {event_count}")
    if action_count < 1:
        blockers.append(f"E2E action count is too low: {action_count}")
    if generated_doc_count < 4:
        blockers.append(f"E2E generated BoI count is too low: {generated_doc_count}")
    if manual_handoff_count < 1:
        blockers.append(f"E2E manual handoff count is too low: {manual_handoff_count}")
    if failed_count:
        blockers.append(f"E2E has failed action count: {failed_count}")
    missing_langflow = sorted(REQUIRED_LANGFLOW_ACTIONS - langflow_keys)
    if missing_langflow:
        blockers.append(f"Langflow action evidence is missing: {', '.join(missing_langflow)}")
    if langflow_bad:
        blockers.append(f"Langflow actions did not invoke successfully: {', '.join(langflow_bad)}")

    return {
        "ok": not blockers,
        "trace_id": trace_id,
        "event_count": event_count,
        "action_count": action_count,
        "generated_doc_count": generated_doc_count,
        "manual_handoff_count": manual_handoff_count,
        "failed_count": failed_count,
        "langflow_action_count": len(langflow_actions),
        "blockers": blockers,
    }


def evaluate_summary_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "path": str(path), "blockers": [f"E2E evidence summary file not found: {path}"]}
    report = evaluate_e2e_summary(load_json(path))
    report["path"] = str(path)
    return report


def evaluate_capture_targets(
    *,
    targets: Path,
    service_token: str,
    langflow_api_key: str,
    timeout: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/check_poc_capture_targets.py",
        "--targets",
        str(targets),
        "--service-token",
        service_token,
        "--langflow-api-key",
        langflow_api_key,
        "--timeout",
        str(timeout),
    ]
    result = run_command(command)
    payload = result["json"] or {}
    blockers = [
        f"capture target preflight failed: {item.get('id')} {item.get('reason') or ''}".strip()
        for item in payload.get("results", [])
        if isinstance(item, dict) and not item.get("ok")
    ]
    if result["returncode"] != 0 and not blockers:
        blockers.append("capture target preflight command failed")
    return {
        "ok": result["returncode"] == 0 and bool(payload.get("ok", False)),
        "command": result["command"],
        "target_count": payload.get("target_count"),
        "results": payload.get("results", []),
        "stdout": result["stdout"],
        "blockers": blockers,
    }


def evaluate_screenshots(manifest: Path) -> dict[str, Any]:
    result = run_command([sys.executable, "scripts/insert_poc_screenshots.py", "--manifest", str(manifest), "--check"])
    payload = result["json"] or {}
    missing = payload.get("missing") if isinstance(payload.get("missing"), list) else []
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    blockers = [
        f"required screenshot not ready: {item.get('file')} ({item.get('reason')})"
        for item in issues
        if isinstance(item, dict)
    ]
    if not blockers:
        blockers = [f"required screenshot missing: {path}" for path in missing]
    if result["returncode"] != 0 and not blockers:
        blockers.append("screenshot availability check failed")
    return {
        "ok": result["returncode"] == 0 and bool(payload.get("ok", False)),
        "command": result["command"],
        "missing": missing,
        "issues": issues,
        "stdout": result["stdout"],
        "blockers": blockers,
    }


def evaluate_ppt_runtime() -> dict[str, Any]:
    result = run_command([sys.executable, "scripts/build_boi_e2e_ppt.py"])
    blockers: list[str] = []
    if result["returncode"] != 0:
        if "artifact-tool runtime is unavailable" in result["stdout"]:
            blockers.append("artifact-tool runtime is unavailable for PPTX export")
        else:
            blockers.append("artifact-tool PPT build command failed")
    return {
        "ok": result["returncode"] == 0,
        "command": result["command"],
        "stdout": result["stdout"],
        "blockers": blockers,
    }


def evaluate_final_deck(path: Path = DEFAULT_ARTIFACT_PPTX) -> dict[str, Any]:
    path = project_path(path)
    ok = path.exists() and path.stat().st_size > 0
    return {
        "ok": ok,
        "path": str(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "blockers": [] if ok else [f"artifact-tool final deck is not present: {path}"],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    requirements = {
        "e2e_evidence": evaluate_summary_file(args.summary),
        "capture_targets": evaluate_capture_targets(
            targets=args.targets,
            service_token=args.service_token,
            langflow_api_key=args.langflow_api_key,
            timeout=args.timeout,
        ),
        "screenshots": evaluate_screenshots(args.manifest),
        "ppt_runtime": evaluate_ppt_runtime(),
        "final_deck": evaluate_final_deck(args.artifact_pptx),
    }
    blockers = [
        blocker
        for requirement in requirements.values()
        for blocker in requirement.get("blockers", [])
    ]
    return {
        "ok": all(requirement.get("ok") for requirement in requirements.values()),
        "requirements": requirements,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final BoI Wiki PoC delivery readiness.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_EVIDENCE_SUMMARY)
    parser.add_argument("--targets", type=Path, default=DEFAULT_CAPTURE_TARGETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CAPTURE_MANIFEST)
    parser.add_argument("--artifact-pptx", type=Path, default=DEFAULT_ARTIFACT_PPTX)
    parser.add_argument("--service-token", default=os.getenv("SERVICE_TOKEN", DEFAULT_SERVICE_TOKEN))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", DEFAULT_LANGFLOW_API_KEY))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = build_report(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
