"""Pinned deterministic Science canary execution; never a Release activator."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ledger import GovernedRuntimeLedger, RecordKind
from .science_evaluator import (
    CheckApplicability,
    CheckOutcome,
    PrimaryVerdict,
    ScienceCheckInput,
    ScienceEvaluationInput,
    ScienceEvaluator,
)


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ScienceCanaryError(RuntimeError):
    pass


class PinnedCheckSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1)
    mode: Literal["constant_file"]
    script_path: Path
    script_digest: str
    timeout_seconds: int = Field(default=30, ge=1, le=30)

    @field_validator("script_digest")
    @classmethod
    def digest_format(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("script_digest must be canonical sha256")
        return value


@dataclass(frozen=True)
class ScienceCanaryReceipt:
    package_digest: str
    check_id: str
    check_script_digest: str
    request_count: int
    verdict_counts: dict[str, int]
    execution_error_counts: dict[str, int]
    results_digest: str
    run_id: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


def _canonical_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest_json(value) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class ScienceCanaryRunner:
    @staticmethod
    def _load_manifest(package_root: Path) -> dict:
        manifest = json.loads((package_root / "candidate-manifest.json").read_text(encoding="utf-8"))
        package_digest = manifest.get("package_digest")
        base = {key: value for key, value in manifest.items() if key != "package_digest"}
        if (
            manifest.get("schema") != "boi-science-candidate-package/v1"
            or package_digest != _digest_json(base)
            or manifest.get("active_release_transition") is not False
            or manifest.get("canonical_write") is not False
        ):
            raise ScienceCanaryError("candidate package contract is invalid")
        return manifest

    @classmethod
    def run(
        cls,
        package_path: Path | str,
        *,
        relative_paths: list[str],
        check: PinnedCheckSpec,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceCanaryReceipt:
        if not relative_paths or len(relative_paths) != len(set(relative_paths)):
            raise ScienceCanaryError("canary paths must be nonempty and unique")
        if check.script_path.is_symlink():
            raise ScienceCanaryError("pinned check script is missing or unsafe")
        script_path = check.script_path.resolve()
        if not script_path.is_file():
            raise ScienceCanaryError("pinned check script is missing or unsafe")
        script_bytes = script_path.read_bytes()
        if _digest_bytes(script_bytes) != check.script_digest:
            raise ScienceCanaryError("pinned check script digest mismatch")

        package_root = Path(package_path)
        manifest = cls._load_manifest(package_root)
        candidate_items = {
            str(item.get("path")): item
            for item in manifest.get("knowledge") or []
            if item.get("state") == "candidate"
        }
        candidate_root = (package_root / "candidate").resolve()
        preflight: list[tuple[str, dict, Path, bytes]] = []
        for relative in sorted(relative_paths):
            item = candidate_items.get(relative)
            if item is None:
                raise ScienceCanaryError(f"canary path is not a candidate: {relative}")
            raw_path = candidate_root / relative
            if raw_path.is_symlink():
                raise ScienceCanaryError(f"canary candidate is missing or unsafe: {relative}")
            path = raw_path.resolve()
            try:
                path.relative_to(candidate_root)
            except ValueError as exc:
                raise ScienceCanaryError("canary path escapes package") from exc
            if not path.is_file():
                raise ScienceCanaryError(f"canary candidate is missing or unsafe: {relative}")
            payload = path.read_bytes()
            if _digest_bytes(payload) != item.get("candidate_digest"):
                raise ScienceCanaryError(f"canary candidate digest mismatch: {relative}")
            preflight.append((relative, item, path, payload))

        source = ledger.append(
            RecordKind.SOURCE_ARTIFACT,
            {
                "content_digest": manifest["snapshot_digest"],
                "locator": f"candidate-package:{manifest['package_digest']}",
                "byte_length": (package_root / "candidate-manifest.json").stat().st_size,
            },
            authority="intake_service",
            occurred_at=occurred_at,
        )
        rows: list[dict] = []
        verdict_counts: dict[str, int] = {}
        error_counts: dict[str, int] = {}
        for relative, item, candidate_path, payload in preflight:
            revision = ledger.append(
                RecordKind.KNOWLEDGE_REVISION,
                {
                    "status": "candidate",
                    "source_ids": [source.record_id],
                    "document_digest": item["candidate_digest"],
                    "package_digest": manifest["package_digest"],
                    "path_digest": _digest_json(relative),
                },
                authority="migration_service",
                occurred_at=occurred_at,
            )
            output_digest: str
            execution_error: str | None = None
            try:
                completed = subprocess.run(
                    [sys.executable, str(script_path), "--file", str(candidate_path)],
                    capture_output=True,
                    check=False,
                    timeout=check.timeout_seconds,
                )
                output_digest = _digest_bytes(completed.stdout)
                try:
                    output = json.loads(completed.stdout.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    output = None
                if isinstance(output, dict) and output.get("pass") is True and completed.returncode == 0:
                    outcome = CheckOutcome.PASS
                elif isinstance(output, dict) and output.get("pass") is False:
                    outcome = CheckOutcome.FAIL
                else:
                    outcome = CheckOutcome.NOT_RUN
                    execution_error = "INVALID_CHECK_OUTPUT"
            except subprocess.TimeoutExpired as exc:
                output_digest = _digest_bytes(exc.stdout or b"")
                outcome = CheckOutcome.NOT_RUN
                execution_error = "CHECK_TIMEOUT"
            if execution_error:
                error_counts[execution_error] = error_counts.get(execution_error, 0) + 1
            science_check = ScienceCheckInput(
                check_id=f"{check.check_id}:{_digest_json(relative)[7:23]}",
                outcome=outcome,
                applicability=CheckApplicability.IN_SCOPE,
                required=True,
                rule_digest=check.script_digest,
                evidence_digest=_digest_bytes(payload),
            )
            result, verdict_record = ScienceEvaluator.evaluate_to_ledger(
                ScienceEvaluationInput(
                    knowledge_revision_id=revision.record_id,
                    checks=[science_check],
                    coverage_complete=True,
                    evidence_complete=True,
                    historical_labels=[],
                ),
                ledger=ledger,
                occurred_at=occurred_at,
            )
            verdict_counts[result.verdict.value] = verdict_counts.get(result.verdict.value, 0) + 1
            rows.append(
                {
                    "revision_id": revision.record_id,
                    "verdict_id": verdict_record.record_id,
                    "verdict": result.verdict.value,
                    "result_digest": result.result_digest,
                    "output_digest": output_digest,
                    "execution_error": execution_error,
                }
            )
        results_digest = _digest_json(rows)
        run = ledger.append(
            RecordKind.RUN,
            {
                "scope": "science-canary",
                "package_digest": manifest["package_digest"],
                "check_id": check.check_id,
                "check_script_digest": check.script_digest,
                "request_count": len(preflight),
                "verdict_counts": verdict_counts,
                "execution_error_counts": error_counts,
                "results_digest": results_digest,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
            authority="science_evaluator",
            occurred_at=occurred_at,
        )
        return ScienceCanaryReceipt(
            package_digest=manifest["package_digest"],
            check_id=check.check_id,
            check_script_digest=check.script_digest,
            request_count=len(preflight),
            verdict_counts=verdict_counts,
            execution_error_counts=error_counts,
            results_digest=results_digest,
            run_id=run.record_id,
        )
