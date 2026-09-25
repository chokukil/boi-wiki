"""Build immutable candidate-only numeric correction patches from NIST drift evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from .ledger import GovernedRuntimeLedger, LedgerError, canonical_json
from .science_nist_candidate_drift import (
    ScienceNistCandidateDriftAuditor,
    ScienceNistCandidateDriftError,
)


class ScienceNistCorrectionCandidateError(RuntimeError):
    """Correction candidates cannot be produced from the exact frozen closure."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ScienceNistCorrectionCandidatePackage:
    schema: str
    package_digest: str
    package_path: Path
    patch_refs: tuple[str, ...]
    candidate_count: int
    attention_required: int
    excluded_exact: int
    excluded_name_mismatch: int
    audit_result_digest: str
    model_invocations: int = 0
    checks_recorded: int = 0
    verdicts: int = 0
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceNistCorrectionCandidateBuilder:
    """Propose exact field patches; never edit a source candidate or grant authority."""

    SCHEMA = "boi-science-nist-correction-candidate-package/v1"
    PATCH_SCHEMA = "boi-science-nist-correction-candidate/v1"
    MAX_CANDIDATES = 100

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @classmethod
    def build(
        cls,
        *,
        candidate_package: Path | str,
        evidence_root: Path | str,
        output_root: Path | str,
    ) -> ScienceNistCorrectionCandidatePackage:
        package = Path(candidate_package)
        evidence = Path(evidence_root)
        try:
            audit = ScienceNistCandidateDriftAuditor.audit(
                candidate_package=package, evidence_root=evidence
            )
        except ScienceNistCandidateDriftError as error:
            raise ScienceNistCorrectionCandidateError("NIST drift audit failed") from error
        ledger = GovernedRuntimeLedger(evidence / "ledger")
        proposals: list[tuple[str, bytes, dict[str, object]]] = []
        excluded_exact = 0
        excluded_name_mismatch = 0
        for item in audit.items:
            if item.outcome == "EXACT_NUMERIC_AND_UNCERTAINTY":
                excluded_exact += 1
                continue
            if not item.name_matched:
                excluded_name_mismatch += 1
                continue
            try:
                span = ledger.read(item.evidence_span_id)
            except LedgerError as error:
                raise ScienceNistCorrectionCandidateError("NIST EvidenceSpan is missing") from error
            semantic = span.payload.get("semantic_fields")
            if not isinstance(semantic, dict):
                raise ScienceNistCorrectionCandidateError("NIST semantic evidence is missing")
            operations = []
            if not item.relative_uncertainty_matched:
                observed = str(semantic.get("relative_standard_uncertainty") or "")
                operations.append(
                    {
                        "op": "replace",
                        "path": "/uncertainty",
                        "value": "" if observed.casefold() == "exact" else observed,
                    }
                )
            if not item.value_matched:
                operations.append(
                    {
                        "op": "replace",
                        "path": "/value",
                        "value": str(semantic.get("numerical_value") or ""),
                    }
                )
            if not operations:
                raise ScienceNistCorrectionCandidateError(
                    "non-exact matched-name item has no numeric patch"
                )
            proposal = {
                "schema": cls.PATCH_SCHEMA,
                "status": "candidate",
                "approval_ready": False,
                "attention_reason": item.outcome,
                "candidate_path": item.candidate_path,
                "before_digest": item.candidate_digest,
                "source_artifact_id": item.source_artifact_id,
                "evidence_span_id": item.evidence_span_id,
                "resource": item.resource,
                "source_status": item.source_status,
                "audit_result_digest": audit.result_digest,
                "operations": operations,
                "unchanged_unverified_fields": ["expressed_in_ref", "value_status"],
                "checks_recorded": 0,
                "verdict": None,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            }
            payload = canonical_json(proposal)
            digest = _digest_bytes(payload)
            ref = f"patches/{digest.removeprefix('sha256:')}.json"
            proposals.append((ref, payload, {"ref": ref, "digest": digest}))
        if len(proposals) > cls.MAX_CANDIDATES:
            raise ScienceNistCorrectionCandidateError("correction shard exceeds 100 candidates")
        manifest_body = {
            "schema": cls.SCHEMA,
            "source_candidate_package_digest": audit.package_digest,
            "audit_result_digest": audit.result_digest,
            "candidate_count": len(proposals),
            "attention_required": len(proposals),
            "excluded_exact": excluded_exact,
            "excluded_name_mismatch": excluded_name_mismatch,
            "patches": [descriptor for _ref, _payload, descriptor in proposals],
            "authority": {
                "model_invocations": 0,
                "checks_recorded": 0,
                "verdicts": 0,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
        }
        package_digest = _digest_bytes(canonical_json(manifest_body))
        manifest = {**manifest_body, "package_digest": package_digest}
        files = {ref: payload for ref, payload, _descriptor in proposals}
        files["candidate-manifest.json"] = canonical_json(manifest)
        target = Path(output_root) / package_digest.removeprefix("sha256:")
        if target.exists():
            actual = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            if actual != files:
                raise ScienceNistCorrectionCandidateError(
                    "content-addressed correction package conflict"
                )
        else:
            target.mkdir(parents=True, exist_ok=False)
            for ref, payload in sorted(files.items()):
                cls._write_once(target / ref, payload)
        return ScienceNistCorrectionCandidatePackage(
            schema=cls.SCHEMA,
            package_digest=package_digest,
            package_path=target,
            patch_refs=tuple(ref for ref, _payload, _descriptor in proposals),
            candidate_count=len(proposals),
            attention_required=len(proposals),
            excluded_exact=excluded_exact,
            excluded_name_mismatch=excluded_name_mismatch,
            audit_result_digest=audit.result_digest,
        )


__all__ = [
    "ScienceNistCorrectionCandidateBuilder",
    "ScienceNistCorrectionCandidateError",
    "ScienceNistCorrectionCandidatePackage",
]
