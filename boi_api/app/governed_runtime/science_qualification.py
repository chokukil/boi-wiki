"""Review-only Science qualification staging over the common runtime ledger.

This module may create candidate revisions, deterministic checks, and an exact
QualificationReceipt.  It never creates a ReleaseManifest or mutates the active
Release pointer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, record_digest
from .okf_v02 import validate_boi_profile_v02
from .qualification_contract import (
    QualificationContractError,
    build_qualification_receipt_payload,
    validate_qualification_receipt_payload,
)
from .science_canary import SHA256_RE, ScienceCanaryError, ScienceCanaryRunner
from .science_canary_campaign_v2 import (
    MINIMUM_DURATION,
    REQUEST_COUNT,
    ScienceCanaryScheduleV2,
    ScienceCanaryV2Ledger,
)
from .science_canary_campaign_v3 import (
    ScienceCanaryScheduleV3,
    ScienceCanaryV3Ledger,
)
from ..okf import split_frontmatter


class ScienceQualificationError(RuntimeError):
    """A selected Science closure cannot safely advance."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _require_digest(value: str, label: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ScienceQualificationError(f"{label} must be a canonical sha256 digest")


def _artifact_closure(artifacts: Mapping[str, Path], label: str) -> tuple[dict[str, str], str]:
    if not artifacts:
        raise ScienceQualificationError(f"{label} artifacts are required")
    digests: dict[str, str] = {}
    for name, candidate in sorted(artifacts.items()):
        path = Path(candidate)
        if not name.strip() or path.is_symlink() or not path.is_file():
            raise ScienceQualificationError(f"{label} artifact is missing or unsafe")
        digests[name] = _bytes_digest(path.read_bytes())
    return digests, _digest(digests)


@dataclass(frozen=True)
class ScienceQualificationStagingReceipt:
    schema: str
    status: str
    package_digest: str
    schedule_digest: str
    selected_paths: tuple[str, ...]
    revision_ids: tuple[str, ...]
    required_evidence: tuple[tuple[str, str], ...]
    profile_versions: tuple[tuple[str, str], ...]
    schema_versions: tuple[tuple[str, str], ...]
    evaluator_code_digest: str
    catalog_snapshot_digest: str
    schema_snapshot_digest: str
    freshness_policy_digest: str
    policy_digest: str
    promotion_candidate_id: str
    staging_digest: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class ScienceQualificationFinalReceipt:
    schema: str
    status: str
    staging_digest: str
    qualification_receipt_id: str
    qualification_contract_digest: str
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class ScienceReleaseProposalReceipt:
    schema: str
    status: str
    staging_digest: str
    qualification_receipt_id: str
    qualification_contract_digest: str
    supersedes_promotion_candidate_id: str
    proposal_candidate_id: str
    proposal_digest: str
    production_release_qualified: bool = False
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceQualificationService:
    """Stages and qualifies an exact selected Science candidate closure."""

    @classmethod
    def stage(
        cls,
        *,
        package_path: Path | str,
        relative_paths: Sequence[str],
        profile_artifacts: Mapping[str, Path],
        evaluator_artifacts: Mapping[str, Path],
        schedule: ScienceCanaryScheduleV2 | ScienceCanaryScheduleV3,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
        freshness_policy_digest: str,
        policy_digest: str,
    ) -> ScienceQualificationStagingReceipt:
        _require_digest(freshness_policy_digest, "freshness policy")
        _require_digest(policy_digest, "policy")
        try:
            event_time = datetime.fromisoformat(occurred_at)
        except ValueError as error:
            raise ScienceQualificationError("occurred_at is invalid") from error
        if event_time.tzinfo is None or event_time.utcoffset() is None:
            raise ScienceQualificationError("occurred_at timezone is required")
        if event_time.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(seconds=5):
            raise ScienceQualificationError("future occurred_at is forbidden")
        selected = tuple(sorted(str(item).strip() for item in relative_paths))
        if not selected or any(not item for item in selected) or len(selected) != len(set(selected)):
            raise ScienceQualificationError("selected paths must be nonempty and unique")
        scheduled = {item.relative_path for item in schedule.requests}
        if set(selected) != scheduled:
            raise ScienceQualificationError("schedule selection does not match candidate closure")

        root = Path(package_path)
        try:
            manifest = ScienceCanaryRunner._load_manifest(root)
        except (OSError, ValueError, KeyError) as error:
            raise ScienceQualificationError("candidate package contract is invalid") from error
        if manifest.get("package_digest") != schedule.package_digest:
            raise ScienceQualificationError("schedule package digest mismatch")
        by_path = {str(item.get("path")): item for item in manifest.get("knowledge") or []}
        candidate_root = (root / "candidate").resolve()

        prepared: list[dict[str, object]] = []
        for relative in selected:
            item = by_path.get(relative)
            if not isinstance(item, dict) or item.get("state") != "candidate" or item.get("error_codes"):
                raise ScienceQualificationError("selected candidate has unresolved Attention")
            raw = candidate_root / relative
            if raw.is_symlink():
                raise ScienceQualificationError("candidate path is unsafe")
            path = raw.resolve()
            try:
                path.relative_to(candidate_root)
            except ValueError as error:
                raise ScienceQualificationError("candidate path escapes package") from error
            if not path.is_file():
                raise ScienceQualificationError("selected candidate is missing")
            payload = path.read_bytes()
            if _bytes_digest(payload) != item.get("candidate_digest"):
                raise ScienceQualificationError("candidate digest mismatch")
            try:
                metadata, _body = split_frontmatter(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as error:
                raise ScienceQualificationError("candidate frontmatter is invalid") from error
            validation = validate_boi_profile_v02(metadata)
            if not validation.ok or metadata.get("profiles") != ["boi/sci@0.7.0"]:
                raise ScienceQualificationError("strict Science profile conformance failed")
            sources = metadata.get("sources")
            if (
                not isinstance(sources, list)
                or not sources
                or any(
                    not isinstance(source, dict)
                    or not str(source.get("resource") or "").strip()
                    or not str(source.get("relation") or "").strip()
                    for source in sources
                )
            ):
                raise ScienceQualificationError("source reference closure is incomplete")
            prepared.append(
                {
                    "path": relative,
                    "candidate_digest": item["candidate_digest"],
                    "byte_length": len(payload),
                    "boi_id": metadata.get("boi_id"),
                    "sources_digest": _digest(sources),
                }
            )

        profile_digests, profile_closure_digest = _artifact_closure(profile_artifacts, "profile")
        evaluator_digests, evaluator_code_digest = _artifact_closure(evaluator_artifacts, "evaluator")
        source = ledger.append(
            RecordKind.SOURCE_ARTIFACT,
            {
                "content_digest": manifest["snapshot_digest"],
                "locator": f"candidate-package:{manifest['package_digest']}",
                "byte_length": (root / "candidate-manifest.json").stat().st_size,
                "package_digest": manifest["package_digest"],
            },
            authority="intake_service",
            occurred_at=occurred_at,
        )

        revision_ids: list[str] = []
        evidence_span_ids: list[str] = []
        for item in prepared:
            span = ledger.append(
                RecordKind.EVIDENCE_SPAN,
                {
                    "source_artifact_id": source.record_id,
                    "locator": f"candidate/{item['path']}",
                    "content_digest": item["candidate_digest"],
                    "byte_start": 0,
                    "byte_end": item["byte_length"],
                    "sources_digest": item["sources_digest"],
                },
                authority="evidence_service",
                occurred_at=occurred_at,
            )
            revision = ledger.append(
                RecordKind.KNOWLEDGE_REVISION,
                {
                    "status": "candidate",
                    "boi_id": item["boi_id"],
                    "source_ids": [source.record_id],
                    "evidence_span_ids": [span.record_id],
                    "document_digest": item["candidate_digest"],
                    "package_digest": manifest["package_digest"],
                    "path_digest": _digest(item["path"]),
                    "profile": "boi/sci@0.7.0",
                },
                authority="migration_service",
                occurred_at=occurred_at,
            )
            evidence_span_ids.append(span.record_id)
            revision_ids.append(revision.record_id)

        check_inputs = {
            "attention-clearance": {"paths": list(selected), "unresolved": 0},
            "candidate-byte-parity": [
                {"path": item["path"], "digest": item["candidate_digest"]} for item in prepared
            ],
            "evaluator-binding": evaluator_digests,
            "source-reference-closure": [
                {"path": item["path"], "sources_digest": item["sources_digest"]} for item in prepared
            ],
            "strict-sci-profile-conformance": {
                "profile": "boi/sci@0.7.0",
                "artifacts": profile_digests,
                "validated": list(selected),
            },
        }
        required_evidence: list[tuple[str, str]] = []
        for check_id, evidence in sorted(check_inputs.items()):
            evidence_digest = _digest(evidence)
            check = ledger.append(
                RecordKind.CHECK,
                {
                    "scope": "science-qualification-staging",
                    "check_id": check_id,
                    "status": "PASS",
                    "evidence_digest": evidence_digest,
                    "package_digest": manifest["package_digest"],
                    "schedule_digest": schedule.schedule_digest,
                },
                authority="qualification_service",
                occurred_at=occurred_at,
            )
            required_evidence.append((check_id, record_digest(check.record_id)))

        profile_versions = (("boi/core", "0.2"), ("boi/sci", "0.7.0"))
        schema_versions = (
            ("candidate-package", "boi-science-candidate-package/v1"),
            ("canary-schedule", schedule.schema_name),
            ("ledger", ledger.SCHEMA),
        )
        staging_values = {
            "schema": "boi-science-qualification-staging/v1",
            "status": "IN_PROGRESS",
            "package_digest": manifest["package_digest"],
            "schedule_digest": schedule.schedule_digest,
            "selected_paths": list(selected),
            "revision_ids": revision_ids,
            "evidence_span_ids": evidence_span_ids,
            "required_evidence": dict(required_evidence),
            "profile_versions": dict(profile_versions),
            "schema_versions": dict(schema_versions),
            "evaluator_code_digest": evaluator_code_digest,
            "catalog_snapshot_digest": manifest["snapshot_digest"],
            "schema_snapshot_digest": profile_closure_digest,
            "freshness_policy_digest": freshness_policy_digest,
            "policy_digest": policy_digest,
            "qualification_receipt_id": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        staging_digest = _digest(staging_values)
        promotion = ledger.append(
            RecordKind.PROMOTION_CANDIDATE,
            {
                **staging_values,
                "staging_digest": staging_digest,
                "approval_ready": False,
                "production_qualified": False,
            },
            authority="promotion_service",
            occurred_at=occurred_at,
        )
        return ScienceQualificationStagingReceipt(
            schema="boi-science-qualification-staging/v1",
            status="IN_PROGRESS",
            package_digest=manifest["package_digest"],
            schedule_digest=schedule.schedule_digest,
            selected_paths=selected,
            revision_ids=tuple(revision_ids),
            required_evidence=tuple(required_evidence),
            profile_versions=profile_versions,
            schema_versions=schema_versions,
            evaluator_code_digest=evaluator_code_digest,
            catalog_snapshot_digest=manifest["snapshot_digest"],
            schema_snapshot_digest=profile_closure_digest,
            freshness_policy_digest=freshness_policy_digest,
            policy_digest=policy_digest,
            promotion_candidate_id=promotion.record_id,
            staging_digest=staging_digest,
        )

    @staticmethod
    def finalize(
        *,
        staged: ScienceQualificationStagingReceipt,
        schedule: ScienceCanaryScheduleV2 | ScienceCanaryScheduleV3,
        canary_ledger: ScienceCanaryV2Ledger | ScienceCanaryV3Ledger,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceQualificationFinalReceipt:
        try:
            canary_progress, canary_evidence_digest = canary_ledger.qualification_snapshot(schedule)
        except ScienceCanaryError as error:
            raise ScienceQualificationError("canary is not qualification eligible") from error
        elapsed_seconds = getattr(
            canary_progress,
            "host_elapsed_seconds",
            getattr(canary_progress, "elapsed_seconds", None),
        )
        carried_request_count = getattr(
            canary_progress,
            "prior_campaign_carried_request_count",
            getattr(canary_progress, "v1_carried_request_count", None),
        )
        if (
            canary_progress.campaign_id == ""
            or canary_progress.schedule_digest != staged.schedule_digest
            or canary_progress.completed_requests != REQUEST_COUNT
            or canary_progress.consistent_requests != REQUEST_COUNT
            or canary_progress.failed_requests != 0
            or elapsed_seconds is None
            or elapsed_seconds < int(MINIMUM_DURATION.total_seconds())
            or not canary_progress.request_gate_passed
            or not canary_progress.duration_gate_passed
            or not canary_progress.quality_gate_passed
            or not canary_progress.eligible_for_qualification
            or carried_request_count != 0
            or canary_progress.qualification_receipt_id is not None
            or canary_progress.release_manifest_id is not None
            or canary_progress.active_release_transition
        ):
            raise ScienceQualificationError("canary is not qualification eligible")
        required_evidence = dict(staged.required_evidence)
        required_evidence["canary-100-over-48h"] = canary_evidence_digest
        payload = build_qualification_receipt_payload(
            revision_ids=staged.revision_ids,
            required_evidence=required_evidence,
            profile_versions=dict(staged.profile_versions),
            schema_versions=dict(staged.schema_versions),
            evaluator_code_digest=staged.evaluator_code_digest,
            catalog_snapshot_digest=staged.catalog_snapshot_digest,
            schema_snapshot_digest=staged.schema_snapshot_digest,
            freshness_policy_digest=staged.freshness_policy_digest,
            policy_digest=staged.policy_digest,
        )
        payload.update(
            {
                "science_staging_digest": staged.staging_digest,
                "canary_progress_digest": canary_progress.progress_digest,
                "canary_evidence_digest": canary_evidence_digest,
                "release_manifest_id": None,
                "active_release_transition": False,
            }
        )
        receipt = ledger.append(
            RecordKind.QUALIFICATION_RECEIPT,
            payload,
            authority="qualification_service",
            # The trusted scheduler observation, not a retry caller's clock,
            # makes finalization content-addressed and idempotent.
            occurred_at=canary_progress.observed_at,
        )
        return ScienceQualificationFinalReceipt(
            schema="boi-science-qualification-final/v1",
            status="QUALIFIED_INACTIVE",
            staging_digest=staged.staging_digest,
            qualification_receipt_id=receipt.record_id,
            qualification_contract_digest=str(payload["qualification_contract_digest"]),
        )

    @staticmethod
    def propose_for_review(
        *,
        staged: ScienceQualificationStagingReceipt,
        finalized: ScienceQualificationFinalReceipt,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceReleaseProposalReceipt:
        """Create an idempotent inactive proposal, never a ReleaseManifest."""

        if finalized.status != "QUALIFIED_INACTIVE" or finalized.staging_digest != staged.staging_digest:
            raise ScienceQualificationError("final qualification staging digest mismatch")
        try:
            event_time = datetime.fromisoformat(occurred_at)
        except ValueError as error:
            raise ScienceQualificationError("occurred_at is invalid") from error
        if event_time.tzinfo is None or event_time.utcoffset() is None:
            raise ScienceQualificationError("occurred_at timezone is required")
        if event_time.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(seconds=5):
            raise ScienceQualificationError("future occurred_at is forbidden")
        try:
            qualification = ledger.read(finalized.qualification_receipt_id)
            original = ledger.read(staged.promotion_candidate_id)
        except LedgerError as error:
            raise ScienceQualificationError("proposal parent record is missing") from error
        if (
            qualification.kind is not RecordKind.QUALIFICATION_RECEIPT
            or qualification.authority != "qualification_service"
        ):
            raise ScienceQualificationError("proposal parent is not a QualificationReceipt")
        try:
            validate_qualification_receipt_payload(qualification.payload)
        except QualificationContractError as error:
            raise ScienceQualificationError("proposal QualificationReceipt is invalid") from error
        if (
            qualification.payload.get("science_staging_digest") != staged.staging_digest
            or tuple(qualification.payload.get("revision_ids") or ()) != staged.revision_ids
            or qualification.payload.get("qualification_contract_digest")
            != finalized.qualification_contract_digest
        ):
            raise ScienceQualificationError("proposal qualification closure mismatch")
        contract = qualification.payload.get("qualification_contract") or {}
        if not any(
            item.get("check_id") == "canary-100-over-48h"
            for item in contract.get("required_checks") or ()
        ):
            raise ScienceQualificationError("proposal canary evidence is missing")
        if (
            original.kind is not RecordKind.PROMOTION_CANDIDATE
            or original.authority != "promotion_service"
            or original.payload.get("staging_digest") != staged.staging_digest
            or tuple(original.payload.get("revision_ids") or ()) != staged.revision_ids
            or original.payload.get("approval_ready") is not False
            or original.payload.get("production_qualified") is not False
        ):
            raise ScienceQualificationError("original PromotionCandidate closure mismatch")

        payload = {
            "schema": "boi-science-release-proposal/v1",
            "status": "REVIEW_READY_INACTIVE",
            "science_staging_digest": staged.staging_digest,
            "supersedes_promotion_candidate_id": original.record_id,
            "qualification_receipt_id": qualification.record_id,
            "qualification_receipt_digest": record_digest(qualification.record_id),
            "qualification_contract_digest": finalized.qualification_contract_digest,
            "revision_ids": list(staged.revision_ids),
            "qualification_complete": True,
            "user_review_required": True,
            "production_release_qualified": False,
            "release_manifest_id": None,
            "promotion_performed": False,
            "active_release_transition": False,
        }
        proposal = ledger.append(
            RecordKind.PROMOTION_CANDIDATE,
            payload,
            authority="promotion_service",
            occurred_at=qualification.occurred_at,
        )
        return ScienceReleaseProposalReceipt(
            schema="boi-science-release-proposal-receipt/v1",
            status="REVIEW_READY_INACTIVE",
            staging_digest=staged.staging_digest,
            qualification_receipt_id=qualification.record_id,
            qualification_contract_digest=finalized.qualification_contract_digest,
            supersedes_promotion_candidate_id=original.record_id,
            proposal_candidate_id=proposal.record_id,
            proposal_digest=record_digest(proposal.record_id),
        )


__all__ = [
    "ScienceQualificationError",
    "ScienceQualificationFinalReceipt",
    "ScienceQualificationService",
    "ScienceQualificationStagingReceipt",
    "ScienceReleaseProposalReceipt",
]
