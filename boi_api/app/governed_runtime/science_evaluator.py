"""Deterministic reducer for Science checks and the exact five Verdicts.

This module ports the verdict precedence already proven in the preserved Science
Verifier checkpoint. It does not parse claims, execute rules, or grant Release
authority; it reduces authenticated deterministic check results only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ledger import GovernedRuntimeLedger, LedgerRecord, RecordKind
from .okf_v02 import validate_boi_profile_v02


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class PrimaryVerdict(str, Enum):
    VIOLATION = "VIOLATION"
    CONSISTENT = "CONSISTENT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    OUTSIDE_VALIDITY_DOMAIN = "OUTSIDE_VALIDITY_DOMAIN"
    EMPIRICAL_VERIFICATION_REQUIRED = "EMPIRICAL_VERIFICATION_REQUIRED"


class CheckOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    SKIP = "SKIP"
    NOT_RUN = "NOT_RUN"


class CheckApplicability(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    OUTSIDE_DOMAIN = "OUTSIDE_DOMAIN"
    EMPIRICAL_ONLY = "EMPIRICAL_ONLY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ScienceCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1)
    outcome: CheckOutcome
    applicability: CheckApplicability
    required: bool = True
    rule_digest: str
    evidence_digest: str

    @field_validator("check_id")
    @classmethod
    def canonical_check_id(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("check_id must be canonical")
        return value

    @field_validator("rule_digest", "evidence_digest")
    @classmethod
    def canonical_digest(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("check digests must be canonical sha256")
        return value


class ScienceEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    knowledge_revision_id: str = Field(min_length=1)
    checks: list[ScienceCheckInput]
    coverage_complete: bool
    evidence_complete: bool
    historical_labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_checks(self) -> "ScienceEvaluationInput":
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("check_id values must be unique")
        return self


@dataclass(frozen=True)
class ScienceEvaluationResult:
    knowledge_revision_id: str
    verdict: PrimaryVerdict
    reason_codes: tuple[str, ...]
    decisive_check_ids: tuple[str, ...]
    checked_scope_digest: str
    result_digest: str
    meaning: str
    historical_labels_ignored: bool = True
    truth_claim: bool = False
    safety_claim: bool = False
    approval: bool = False
    qualification: bool = False
    release_authority: bool = False


@dataclass(frozen=True)
class HistoricalReevaluationReceipt:
    package_digest: str
    candidate_count: int
    withheld_count: int
    verdict_counts: dict[str, int]
    results_digest: str
    run_id: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _candidate_metadata(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("candidate is not UTF-8") from exc
    match = re.match(r"\A---\n(?P<header>.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise ValueError("candidate frontmatter is missing")
    metadata = yaml.safe_load(match.group("header")) or {}
    if not isinstance(metadata, dict):
        raise ValueError("candidate frontmatter must be a mapping")
    return metadata


class ScienceEvaluator:
    VERSION = "boi-science-verdict-reducer/0.1.0"

    @classmethod
    def evaluate(cls, evaluation: ScienceEvaluationInput) -> ScienceEvaluationResult:
        checks = sorted(evaluation.checks, key=lambda item: item.check_id)
        required_incomplete = [
            item
            for item in checks
            if item.required and item.outcome in {CheckOutcome.PARTIAL, CheckOutcome.SKIP, CheckOutcome.NOT_RUN}
        ]
        missing_reasons: list[str] = []
        if not evaluation.evidence_complete:
            missing_reasons.append("EVIDENCE_INCOMPLETE")
        if not evaluation.coverage_complete:
            missing_reasons.append("RULE_COVERAGE_INCOMPLETE")
        missing_reasons.extend(f"REQUIRED_CHECK_{item.outcome.value}" for item in required_incomplete)

        decisive: list[ScienceCheckInput] = []
        if missing_reasons:
            verdict = PrimaryVerdict.INSUFFICIENT_INFORMATION
            reasons = sorted(set(missing_reasons))
        elif not checks:
            verdict = PrimaryVerdict.INSUFFICIENT_INFORMATION
            reasons = ["NO_DECISIVE_IN_SCOPE_CHECK"]
        else:
            outside = [item for item in checks if item.applicability is CheckApplicability.OUTSIDE_DOMAIN]
            empirical = [item for item in checks if item.applicability is CheckApplicability.EMPIRICAL_ONLY]
            in_scope = [
                item
                for item in checks
                if item.applicability is CheckApplicability.IN_SCOPE
                and item.outcome in {CheckOutcome.PASS, CheckOutcome.FAIL}
            ]
            failures = [item for item in in_scope if item.outcome is CheckOutcome.FAIL]
            passes = [item for item in in_scope if item.outcome is CheckOutcome.PASS]
            if outside:
                verdict = PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
                decisive = outside
                reasons = ["CHECK_OUTSIDE_VALIDITY_DOMAIN"]
            elif empirical:
                verdict = PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED
                decisive = empirical
                reasons = ["EMPIRICAL_OBSERVATION_REQUIRED"]
            elif failures and passes:
                verdict = PrimaryVerdict.INSUFFICIENT_INFORMATION
                decisive = in_scope
                reasons = ["CONFLICTING_QUALIFIED_CHECKS"]
            elif failures:
                verdict = PrimaryVerdict.VIOLATION
                decisive = failures
                reasons = ["DETERMINISTIC_CHECK_VIOLATION"]
            elif passes:
                verdict = PrimaryVerdict.CONSISTENT
                decisive = passes
                reasons = ["CHECKED_SCOPE_NO_CONTRADICTION"]
            else:
                verdict = PrimaryVerdict.INSUFFICIENT_INFORMATION
                reasons = ["NO_DECISIVE_IN_SCOPE_CHECK"]

        check_projection = [
            {
                "check_id": item.check_id,
                "outcome": item.outcome.value,
                "applicability": item.applicability.value,
                "required": item.required,
                "rule_digest": item.rule_digest,
                "evidence_digest": item.evidence_digest,
            }
            for item in checks
        ]
        scope_digest = _digest(check_projection)
        decisive_ids = tuple(sorted(item.check_id for item in decisive))
        result_projection = {
            "evaluator_version": cls.VERSION,
            "knowledge_revision_id": evaluation.knowledge_revision_id,
            "verdict": verdict.value,
            "reason_codes": reasons,
            "decisive_check_ids": decisive_ids,
            "checked_scope_digest": scope_digest,
            "coverage_complete": evaluation.coverage_complete,
            "evidence_complete": evaluation.evidence_complete,
        }
        meaning = (
            "no contradiction found within the checked scope"
            if verdict is PrimaryVerdict.CONSISTENT
            else "deterministic result within the declared checked scope"
        )
        return ScienceEvaluationResult(
            knowledge_revision_id=evaluation.knowledge_revision_id,
            verdict=verdict,
            reason_codes=tuple(reasons),
            decisive_check_ids=decisive_ids,
            checked_scope_digest=scope_digest,
            result_digest=_digest(result_projection),
            meaning=meaning,
        )

    @classmethod
    def evaluate_to_ledger(
        cls,
        evaluation: ScienceEvaluationInput,
        *,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> tuple[ScienceEvaluationResult, LedgerRecord]:
        result = cls.evaluate(evaluation)
        check_records: list[LedgerRecord] = []
        for item in sorted(evaluation.checks, key=lambda value: value.check_id):
            check_records.append(
                ledger.append(
                    RecordKind.CHECK,
                    {
                        "scope": "science",
                        "knowledge_revision_id": evaluation.knowledge_revision_id,
                        "check_id": item.check_id,
                        "outcome": item.outcome.value,
                        "applicability": item.applicability.value,
                        "required": item.required,
                        "rule_digest": item.rule_digest,
                        "evidence_digest": item.evidence_digest,
                    },
                    authority="science_evaluator",
                    occurred_at=occurred_at,
                )
            )
        verdict_record = ledger.append(
            RecordKind.VERDICT,
            {
                "scope": "science",
                "knowledge_revision_id": evaluation.knowledge_revision_id,
                "code": result.verdict.value,
                "reason_codes": list(result.reason_codes),
                "check_ids": [record.record_id for record in check_records],
                "checked_scope_digest": result.checked_scope_digest,
                "result_digest": result.result_digest,
                "truth_claim": False,
                "safety_claim": False,
                "approval": False,
                "qualification": False,
                "release_authority": False,
            },
            authority="science_evaluator",
            occurred_at=occurred_at,
        )
        return result, verdict_record

    @classmethod
    def reevaluate_candidate_package_history(
        cls,
        package_path: Path | str,
        *,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> HistoricalReevaluationReceipt:
        """Re-evaluate historical labels with zero current checks, fail-closed.

        This is deliberately a withholding migration pass. It establishes fresh
        KnowledgeRevision and Verdict records but cannot issue qualification or
        Release records.
        """

        package_root = Path(package_path)
        manifest_path = package_root / "candidate-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "boi-science-candidate-package/v1":
            raise ValueError("candidate package schema is invalid")
        package_digest = manifest.get("package_digest")
        manifest_base = {key: value for key, value in manifest.items() if key != "package_digest"}
        if package_digest != _digest(manifest_base):
            raise ValueError("candidate package digest is invalid")
        if manifest.get("active_release_transition") is not False or manifest.get("canonical_write") is not False:
            raise ValueError("historical re-evaluation accepts inactive candidate packages only")

        candidate_root = (package_root / "candidate").resolve()
        preflight: list[tuple[Mapping[str, Any], bytes, dict[str, Any]]] = []
        for item in manifest.get("knowledge") or []:
            if item.get("state") != "candidate":
                continue
            relative = str(item.get("path") or "")
            candidate_path = (candidate_root / relative).resolve()
            try:
                candidate_path.relative_to(candidate_root)
            except ValueError as exc:
                raise ValueError("candidate path escapes package") from exc
            if candidate_path.is_symlink() or not candidate_path.is_file():
                raise ValueError(f"candidate is missing or unsafe: {relative}")
            payload = candidate_path.read_bytes()
            if _bytes_digest(payload) != item.get("candidate_digest"):
                raise ValueError(f"candidate digest mismatch: {relative}")
            metadata = _candidate_metadata(payload)
            validation = validate_boi_profile_v02(metadata)
            if not validation.ok:
                raise ValueError(f"candidate strict profile failed: {relative}")
            preflight.append((item, payload, metadata))

        source_record = ledger.append(
            RecordKind.SOURCE_ARTIFACT,
            {
                "content_digest": manifest["snapshot_digest"],
                "locator": f"candidate-package:{package_digest}",
                "byte_length": manifest_path.stat().st_size,
            },
            authority="intake_service",
            occurred_at=occurred_at,
        )
        result_rows: list[dict[str, Any]] = []
        verdict_counts: dict[str, int] = {}
        for item, _payload, metadata in preflight:
            revision = ledger.append(
                RecordKind.KNOWLEDGE_REVISION,
                {
                    "status": "candidate",
                    "source_ids": [source_record.record_id],
                    "document_digest": item["candidate_digest"],
                    "package_digest": package_digest,
                    "path_digest": _digest(str(item["path"])),
                },
                authority="migration_service",
                occurred_at=occurred_at,
            )
            historical = metadata.get("historical_assertions")
            labels = []
            if isinstance(historical, Mapping):
                labels = [
                    str(value)
                    for key, value in historical.items()
                    if key != "not_qualification" and value not in (None, "")
                ]
            result, verdict_record = cls.evaluate_to_ledger(
                ScienceEvaluationInput(
                    knowledge_revision_id=revision.record_id,
                    checks=[],
                    coverage_complete=False,
                    evidence_complete=False,
                    historical_labels=labels,
                ),
                ledger=ledger,
                occurred_at=occurred_at,
            )
            verdict_counts[result.verdict.value] = verdict_counts.get(result.verdict.value, 0) + 1
            result_rows.append(
                {
                    "revision_id": revision.record_id,
                    "verdict_id": verdict_record.record_id,
                    "verdict": result.verdict.value,
                    "result_digest": result.result_digest,
                }
            )
        results_digest = _digest(result_rows)
        run = ledger.append(
            RecordKind.RUN,
            {
                "scope": "science-historical-reevaluation",
                "package_digest": package_digest,
                "candidate_count": len(preflight),
                "verdict_counts": verdict_counts,
                "results_digest": results_digest,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
            },
            authority="science_evaluator",
            occurred_at=occurred_at,
        )
        return HistoricalReevaluationReceipt(
            package_digest=str(package_digest),
            candidate_count=len(preflight),
            withheld_count=verdict_counts.get(PrimaryVerdict.INSUFFICIENT_INFORMATION.value, 0),
            verdict_counts=verdict_counts,
            results_digest=results_digest,
            run_id=run.record_id,
        )
