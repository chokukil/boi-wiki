"""Digest-pinned adapters for preserved deterministic Science check assets."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from typing import Any

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .science_evaluator import CheckOutcome, ScienceCheckInput
from .science_source_family_expansion import (
    ScienceSourceFamilyCheckBundle,
    ScienceSourceFamilyCheckReceiptRecorder,
    ScienceSourceFamilyDeterministicCheckRunner,
    ScienceSourceFamilyExpansionError,
    ScienceSourceFamilyExpansionPlan,
    ScienceSourceFamilyExpansionPlanner,
    science_source_family_planner_code_digest,
)
from ..okf import split_frontmatter


class ScienceDerivationCheckAssetError(ScienceSourceFamilyExpansionError):
    """A preserved derivation executor asset is absent, altered, or invalid."""


class ScienceSourceEvidenceError(ScienceSourceFamilyExpansionError):
    """An authoritative SourceArtifact or exact EvidenceSpan is unavailable."""


def _bytes_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return _bytes_digest(encoded)


def _inventory(payload: bytes) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ScienceDerivationCheckAssetError("asset inventory is not UTF-8") from error
    for line in lines:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ScienceDerivationCheckAssetError("asset inventory row is invalid")
        digest, size, raw_path = parts
        path = raw_path.removeprefix("./")
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or not size.isdigit()
            or not path
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
            or path in result
        ):
            raise ScienceDerivationCheckAssetError("asset inventory closure is invalid")
        result[path] = (f"sha256:{digest}", int(size))
    return result


def _read_snapshot_member(snapshot: Path, relative: str) -> bytes:
    with tarfile.open(snapshot, mode="r:gz") as archive:
        matches = [
            member
            for member in archive.getmembers()
            if member.name.removeprefix("./") == relative
        ]
        if len(matches) != 1 or not matches[0].isfile():
            raise ScienceDerivationCheckAssetError("registered check asset is not a regular snapshot member")
        handle = archive.extractfile(matches[0])
        if handle is None:
            raise ScienceDerivationCheckAssetError("registered check asset cannot be read")
        return handle.read()


def _parse_check_result(stdout: bytes) -> dict[str, Any]:
    if len(stdout) > 65536:
        raise ScienceDerivationCheckAssetError("check output exceeds the bounded limit")
    for line in reversed(stdout.decode("utf-8", errors="strict").splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("pass"), bool):
            return value
    raise ScienceDerivationCheckAssetError("check output has no typed result")


def _candidate_and_metadata(
    plan: ScienceSourceFamilyExpansionPlan,
    *,
    shard_id: str,
    candidate_path: str,
    package_path: Path | str,
    expected_kind: str,
):
    ScienceSourceFamilyExpansionPlanner._validate_plan(plan)
    selected = [shard for shard in plan.shards if shard.shard_id == shard_id]
    if len(selected) != 1:
        raise ScienceSourceEvidenceError("exact shard is required")
    matches = [item for item in selected[0].candidates if item.path == candidate_path]
    if len(matches) != 1 or matches[0].science_kind != expected_kind:
        raise ScienceSourceEvidenceError(f"exact {expected_kind} candidate is required")
    candidate = matches[0]
    root = Path(package_path).resolve()
    candidate_root = (root / "candidate").resolve()
    raw_path = candidate_root / candidate.path
    if raw_path.is_symlink():
        raise ScienceSourceEvidenceError("candidate path is unsafe")
    path = raw_path.resolve()
    try:
        path.relative_to(candidate_root)
        payload = path.read_bytes()
        metadata, _body = split_frontmatter(payload.decode("utf-8"))
    except (ValueError, OSError, UnicodeDecodeError) as error:
        raise ScienceSourceEvidenceError("candidate cannot be parsed") from error
    if _bytes_digest(payload) != candidate.candidate_digest:
        raise ScienceSourceEvidenceError("candidate digest is invalid")
    return selected[0], candidate, metadata


def _authoritative_span(
    *,
    source_path: Path | str,
    source_artifact_id: str,
    evidence_span_id: str,
    candidate_sources: object,
    ledger: GovernedRuntimeLedger,
) -> tuple[bytes, object, object]:
    try:
        source = ledger.read(source_artifact_id)
    except LedgerError as error:
        raise ScienceSourceEvidenceError("SourceArtifact is missing") from error
    if source.kind is not RecordKind.SOURCE_ARTIFACT or source.authority != "intake_service":
        raise ScienceSourceEvidenceError("SourceArtifact authority is invalid")
    path = Path(source_path)
    if path.is_symlink() or not path.is_file():
        raise ScienceSourceEvidenceError("SourceArtifact bytes are unavailable")
    payload = path.read_bytes()
    if (
        _bytes_digest(payload) != source.payload.get("content_digest")
        or len(payload) != source.payload.get("byte_length")
    ):
        raise ScienceSourceEvidenceError("SourceArtifact bytes do not match intake")
    try:
        span = ledger.read(evidence_span_id)
    except LedgerError as error:
        raise ScienceSourceEvidenceError("EvidenceSpan is missing") from error
    if span.kind is not RecordKind.EVIDENCE_SPAN or span.authority not in {
        "intake_service",
        "evidence_service",
    }:
        raise ScienceSourceEvidenceError("EvidenceSpan authority is invalid")
    if span.payload.get("source_artifact_id") != source.record_id:
        raise ScienceSourceEvidenceError("EvidenceSpan source binding is invalid")
    try:
        start = int(span.payload["byte_start"])
        end = int(span.payload["byte_end"])
    except (KeyError, TypeError, ValueError) as error:
        raise ScienceSourceEvidenceError("EvidenceSpan bounds are invalid") from error
    if not 0 <= start < end <= len(payload):
        raise ScienceSourceEvidenceError("EvidenceSpan bounds are invalid")
    span_bytes = payload[start:end]
    if _bytes_digest(span_bytes) != span.payload.get("content_digest"):
        raise ScienceSourceEvidenceError("EvidenceSpan digest is invalid")
    resource = str(source.payload.get("resource") or "")
    declared = {
        str(item.get("resource") or "")
        for item in candidate_sources
        if isinstance(item, dict) and item.get("relation") == "evidence"
    } if isinstance(candidate_sources, list) else set()
    if not resource or resource not in declared or span.payload.get("resource") != resource:
        raise ScienceSourceEvidenceError("EvidenceSpan is outside candidate source closure")
    return span_bytes, source, span


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ScienceSourceEvidenceError("SI factor is invalid") from error
    if not result.is_finite():
        raise ScienceSourceEvidenceError("SI factor is invalid")
    return result.normalize()


class ScienceUnitSIRegistryCheckRunner:
    """Compare one unit candidate with one exact authoritative SI registry span."""

    @classmethod
    def run(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        source_path: Path | str,
        source_artifact_id: str,
        evidence_span_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        _shard, candidate, metadata = _candidate_and_metadata(
            plan,
            shard_id=shard_id,
            candidate_path=candidate_path,
            package_path=package_path,
            expected_kind="unit",
        )
        span_bytes, source, span = _authoritative_span(
            source_path=source_path,
            source_artifact_id=source_artifact_id,
            evidence_span_id=evidence_span_id,
            candidate_sources=metadata.get("sources"),
            ledger=ledger,
        )
        try:
            registry = json.loads(span_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ScienceSourceEvidenceError("SI registry EvidenceSpan is malformed") from error
        if not isinstance(registry, dict) or registry.get("schema") != "boi-si-unit-registry-entry/v1":
            raise ScienceSourceEvidenceError("SI registry EvidenceSpan schema is invalid")
        candidate_base = metadata.get("si_base")
        registry_base = registry.get("si_base")
        if not isinstance(candidate_base, dict) or not isinstance(registry_base, dict):
            raise ScienceSourceEvidenceError("SI base dimension is invalid")
        matched = (
            str(metadata.get("symbol") or "") == str(registry.get("symbol") or "")
            and _decimal(metadata.get("si_factor")) == _decimal(registry.get("si_factor"))
            and str(metadata.get("si_unit") or "") == str(registry.get("si_unit") or "")
            and {str(key): int(value) for key, value in candidate_base.items()}
            == {str(key): int(value) for key, value in registry_base.items()}
        )
        definition_grounded = matched and all(
            isinstance(registry.get(field), str) and bool(registry[field].strip())
            for field in ("name", "quantity", "classification", "definition")
        ) and (
            str(registry["name"]).casefold()
            in str(metadata.get("title") or "").casefold()
            and str(registry["classification"]) == str(metadata.get("category") or "")
        )
        preflight = ScienceSourceFamilyDeterministicCheckRunner.run_preflight(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            package_path=package_path,
            ledger=ledger,
            occurred_at=occurred_at,
        )
        identity_evidence = {
            "rule": "boi-unit-si-registry-identity/v1",
            "source_artifact_id": source.record_id,
            "source_content_digest": source.payload["content_digest"],
            "evidence_span_id": span.record_id,
            "evidence_span_digest": span.payload["content_digest"],
            "candidate_digest": candidate.candidate_digest,
            "matched": matched,
        }
        definition_evidence = {
            "rule": "boi-unit-source-definition-grounding/v1",
            "source_artifact_id": source.record_id,
            "evidence_span_id": span.record_id,
            "candidate_digest": candidate.candidate_digest,
            "identity_matched": matched,
            "definition_present": bool(str(registry.get("definition") or "").strip()),
            "grounded": definition_grounded,
        }
        checks: list[ScienceCheckInput] = []
        for item in preflight.checks:
            if item.check_id == "unit-si-registry-identity":
                checks.append(
                    item.model_copy(
                        update={
                            "outcome": CheckOutcome.PASS if matched else CheckOutcome.FAIL,
                            "evidence_digest": _canonical_digest(identity_evidence),
                        }
                    )
                )
            elif item.check_id == "unit-source-definition-grounding":
                checks.append(
                    item.model_copy(
                        update={
                            "outcome": CheckOutcome.PASS
                            if definition_grounded
                            else CheckOutcome.FAIL,
                            "evidence_digest": _canonical_digest(definition_evidence),
                        }
                    )
                )
            else:
                checks.append(item)
        executor_digest = _canonical_digest(
            {
                "adapter_code_digest": _bytes_digest(Path(__file__).read_bytes()),
                "source_family_contract_digest": science_source_family_planner_code_digest(),
                "rules": [
                    "boi-unit-si-registry-identity/v1",
                    "boi-unit-source-definition-grounding/v1",
                ],
                "source_content_digest": source.payload["content_digest"],
                "evidence_span_digest": span.payload["content_digest"],
            }
        )
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            checks=checks,
            coverage_complete=all(item.outcome is not CheckOutcome.NOT_RUN for item in checks),
            evidence_complete=True,
            check_executor_code_digest=executor_digest,
            executor_resource_ids=[source.record_id],
            evidence_span_ids=[span.record_id],
            ledger=ledger,
            occurred_at=occurred_at,
        )


class ScienceConstantValueCheckRunner:
    """Compare a constant candidate with one exact authoritative registry span."""

    @classmethod
    def run(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        source_path: Path | str,
        source_artifact_id: str,
        evidence_span_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        _shard, candidate, metadata = _candidate_and_metadata(
            plan,
            shard_id=shard_id,
            candidate_path=candidate_path,
            package_path=package_path,
            expected_kind="constant",
        )
        span_bytes, source, span = _authoritative_span(
            source_path=source_path,
            source_artifact_id=source_artifact_id,
            evidence_span_id=evidence_span_id,
            candidate_sources=metadata.get("sources"),
            ledger=ledger,
        )
        try:
            registry = json.loads(span_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ScienceSourceEvidenceError("constant registry EvidenceSpan is malformed") from error
        required = (
            "name",
            "value",
            "expressed_in_ref",
            "value_status",
            "uncertainty",
        )
        if (
            not isinstance(registry, dict)
            or registry.get("schema") != "boi-nist-constant-registry-entry/v1"
            or any(field not in registry for field in required)
        ):
            raise ScienceSourceEvidenceError("constant registry EvidenceSpan schema is invalid")
        name_grounded = str(registry["name"]).casefold() in str(
            metadata.get("title") or ""
        ).casefold()
        candidate_uncertainty = str(metadata.get("uncertainty") or "").strip()
        registry_uncertainty = str(registry.get("uncertainty") or "").strip()
        uncertainty_matched = (
            candidate_uncertainty == registry_uncertainty == ""
            or (
                bool(candidate_uncertainty)
                and bool(registry_uncertainty)
                and _decimal(candidate_uncertainty) == _decimal(registry_uncertainty)
            )
        )
        matched = (
            name_grounded
            and _decimal(metadata.get("value")) == _decimal(registry["value"])
            and str(metadata.get("expressed_in_ref") or "")
            == str(registry["expressed_in_ref"])
            and str(metadata.get("value_status") or "") == str(registry["value_status"])
            and uncertainty_matched
        )
        preflight = ScienceSourceFamilyDeterministicCheckRunner.run_preflight(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            package_path=package_path,
            ledger=ledger,
            occurred_at=occurred_at,
        )
        evidence = {
            "rule": "boi-constant-source-value-verification/v1",
            "source_artifact_id": source.record_id,
            "source_content_digest": source.payload["content_digest"],
            "evidence_span_id": span.record_id,
            "evidence_span_digest": span.payload["content_digest"],
            "candidate_digest": candidate.candidate_digest,
            "name_grounded": name_grounded,
            "uncertainty_matched": uncertainty_matched,
            "matched": matched,
        }
        checks = [
            item.model_copy(
                update={
                    "outcome": CheckOutcome.PASS if matched else CheckOutcome.FAIL,
                    "evidence_digest": _canonical_digest(evidence),
                }
            )
            if item.check_id == "constant-source-value-verification"
            else item
            for item in preflight.checks
        ]
        executor_digest = _canonical_digest(
            {
                "adapter_code_digest": _bytes_digest(Path(__file__).read_bytes()),
                "source_family_contract_digest": science_source_family_planner_code_digest(),
                "rule": "boi-constant-source-value-verification/v1",
                "source_content_digest": source.payload["content_digest"],
                "evidence_span_digest": span.payload["content_digest"],
            }
        )
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            checks=checks,
            coverage_complete=all(item.outcome is not CheckOutcome.NOT_RUN for item in checks),
            evidence_complete=True,
            check_executor_code_digest=executor_digest,
            executor_resource_ids=[source.record_id],
            evidence_span_ids=[span.record_id],
            ledger=ledger,
            occurred_at=occurred_at,
        )


def _normalized_formula(value: object) -> str:
    return " ".join(str(value or "").split())


class ScienceFormulaCheckRunner:
    """Independently verify formula dimensions and authoritative equation text."""

    @classmethod
    def run(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        source_path: Path | str,
        source_artifact_id: str,
        evidence_span_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        _shard, candidate, metadata = _candidate_and_metadata(
            plan,
            shard_id=shard_id,
            candidate_path=candidate_path,
            package_path=package_path,
            expected_kind="formula",
        )
        span_bytes, source, span = _authoritative_span(
            source_path=source_path,
            source_artifact_id=source_artifact_id,
            evidence_span_id=evidence_span_id,
            candidate_sources=metadata.get("sources"),
            ledger=ledger,
        )
        try:
            registry = json.loads(span_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ScienceSourceEvidenceError("formula EvidenceSpan is malformed") from error
        if (
            not isinstance(registry, dict)
            or registry.get("schema") != "boi-authoritative-formula-entry/v1"
            or not isinstance(registry.get("symbol_dimensions"), dict)
            or not isinstance(registry.get("dimension_check"), dict)
        ):
            raise ScienceSourceEvidenceError("formula EvidenceSpan schema is invalid")
        raw_symbols = metadata.get("symbols")
        if not isinstance(raw_symbols, list):
            raise ScienceSourceEvidenceError("formula candidate symbols are invalid")
        candidate_dimensions = {
            str(item.get("key") or ""): str(item.get("dimension_ref") or "")
            for item in raw_symbols
            if isinstance(item, dict)
            and item.get("role") != "label"
            and item.get("key")
            and item.get("dimension_ref")
        }
        source_dimensions = {
            str(key): str(value) for key, value in registry["symbol_dimensions"].items()
        }
        raw_dimension_check = metadata.get("dimension_check")
        factor_keys = {
            str(key)
            for term in (raw_dimension_check or {}).get("terms", [])
            if isinstance(term, dict)
            for key in (term.get("factors") or {})
        } if isinstance(raw_dimension_check, dict) else set()
        dimension_matched = (
            candidate_dimensions == source_dimensions
            and raw_dimension_check == registry["dimension_check"]
            and factor_keys <= set(candidate_dimensions)
        )
        equation_matched = (
            bool(_normalized_formula(registry.get("latex")))
            and _normalized_formula(metadata.get("latex"))
            == _normalized_formula(registry.get("latex"))
            and str(registry.get("name") or "").casefold()
            in str(metadata.get("title") or "").casefold()
        )
        preflight = ScienceSourceFamilyDeterministicCheckRunner.run_preflight(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            package_path=package_path,
            ledger=ledger,
            occurred_at=occurred_at,
        )
        common = {
            "source_artifact_id": source.record_id,
            "source_content_digest": source.payload["content_digest"],
            "evidence_span_id": span.record_id,
            "evidence_span_digest": span.payload["content_digest"],
            "candidate_digest": candidate.candidate_digest,
        }
        checks: list[ScienceCheckInput] = []
        for item in preflight.checks:
            if item.check_id == "formula-symbol-dimension-verification":
                evidence = {**common, "rule": "boi-formula-symbol-dimension/v1", "matched": dimension_matched}
                checks.append(item.model_copy(update={"outcome": CheckOutcome.PASS if dimension_matched else CheckOutcome.FAIL, "evidence_digest": _canonical_digest(evidence)}))
            elif item.check_id == "formula-source-equation-grounding":
                evidence = {**common, "rule": "boi-formula-source-equation/v1", "matched": equation_matched}
                checks.append(item.model_copy(update={"outcome": CheckOutcome.PASS if equation_matched else CheckOutcome.FAIL, "evidence_digest": _canonical_digest(evidence)}))
            else:
                checks.append(item)
        executor_digest = _canonical_digest(
            {
                "adapter_code_digest": _bytes_digest(Path(__file__).read_bytes()),
                "source_family_contract_digest": science_source_family_planner_code_digest(),
                "rules": ["boi-formula-symbol-dimension/v1", "boi-formula-source-equation/v1"],
                "source_content_digest": source.payload["content_digest"],
                "evidence_span_digest": span.payload["content_digest"],
            }
        )
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            checks=checks,
            coverage_complete=all(item.outcome is not CheckOutcome.NOT_RUN for item in checks),
            evidence_complete=True,
            check_executor_code_digest=executor_digest,
            executor_resource_ids=[source.record_id],
            evidence_span_ids=[span.record_id],
            ledger=ledger,
            occurred_at=occurred_at,
        )


def _normalized_semantic_text(value: object) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split()).casefold()


class ScienceDictionarySemanticCheckRunner:
    """Ground an exact term-definition pair without confidence-based passing."""

    @classmethod
    def run(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        source_path: Path | str,
        source_artifact_id: str,
        evidence_span_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        _shard, candidate, metadata = _candidate_and_metadata(
            plan, shard_id=shard_id, candidate_path=candidate_path,
            package_path=package_path, expected_kind="dictionary",
        )
        span_bytes, source, span = _authoritative_span(
            source_path=source_path, source_artifact_id=source_artifact_id,
            evidence_span_id=evidence_span_id, candidate_sources=metadata.get("sources"),
            ledger=ledger,
        )
        try:
            evidence_entry = json.loads(span_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ScienceSourceEvidenceError("dictionary EvidenceSpan is malformed") from error
        if (
            not isinstance(evidence_entry, dict)
            or evidence_entry.get("schema") != "boi-authoritative-dictionary-entry/v1"
            or not _normalized_semantic_text(evidence_entry.get("term"))
            or not _normalized_semantic_text(evidence_entry.get("definition"))
        ):
            raise ScienceSourceEvidenceError("dictionary EvidenceSpan schema is invalid")
        matched = (
            _normalized_semantic_text(metadata.get("term"))
            == _normalized_semantic_text(evidence_entry["term"])
            and _normalized_semantic_text(metadata.get("definition"))
            == _normalized_semantic_text(evidence_entry["definition"])
        )
        preflight = ScienceSourceFamilyDeterministicCheckRunner.run_preflight(
            plan, shard_id=shard_id, candidate_path=candidate.path,
            package_path=package_path, ledger=ledger, occurred_at=occurred_at,
        )
        evidence = {
            "rule": "boi-dictionary-source-semantic-grounding/v1",
            "source_artifact_id": source.record_id,
            "source_content_digest": source.payload["content_digest"],
            "evidence_span_id": span.record_id,
            "evidence_span_digest": span.payload["content_digest"],
            "candidate_digest": candidate.candidate_digest,
            "matched": matched,
            "confidence_used": False,
        }
        checks = [
            item.model_copy(update={
                "outcome": CheckOutcome.PASS if matched else CheckOutcome.FAIL,
                "evidence_digest": _canonical_digest(evidence),
            }) if item.check_id == "dictionary-source-semantic-grounding" else item
            for item in preflight.checks
        ]
        executor_digest = _canonical_digest({
            "adapter_code_digest": _bytes_digest(Path(__file__).read_bytes()),
            "source_family_contract_digest": science_source_family_planner_code_digest(),
            "rule": "boi-dictionary-source-semantic-grounding/v1",
            "source_content_digest": source.payload["content_digest"],
            "evidence_span_digest": span.payload["content_digest"],
        })
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan, shard_id=shard_id, candidate_path=candidate.path, checks=checks,
            coverage_complete=all(item.outcome is not CheckOutcome.NOT_RUN for item in checks),
            evidence_complete=True, check_executor_code_digest=executor_digest,
            executor_resource_ids=[source.record_id], evidence_span_ids=[span.record_id],
            ledger=ledger, occurred_at=occurred_at,
        )


class ScienceDerivationCheckRunner:
    """Execute only a digest-pinned, candidate-declared derivation check.

    The snapshot and its inventory must already be registered by the intake
    authority. Historical labels and historical run outcomes are not inputs.
    """

    @classmethod
    def run(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        snapshot_path: Path | str,
        inventory_path: Path | str,
        snapshot_source_artifact_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
        timeout_seconds: float = 30.0,
    ) -> ScienceSourceFamilyCheckBundle:
        ScienceSourceFamilyExpansionPlanner._validate_plan(plan)
        selected = [shard for shard in plan.shards if shard.shard_id == shard_id]
        if len(selected) != 1:
            raise ScienceDerivationCheckAssetError("exact shard is required")
        matches = [item for item in selected[0].candidates if item.path == candidate_path]
        if len(matches) != 1 or matches[0].science_kind != "derivation":
            raise ScienceDerivationCheckAssetError("exact derivation candidate is required")
        candidate = matches[0]
        try:
            asset = ledger.read(snapshot_source_artifact_id)
        except LedgerError as error:
            raise ScienceDerivationCheckAssetError("snapshot SourceArtifact is missing") from error
        if asset.kind is not RecordKind.SOURCE_ARTIFACT or asset.authority != "intake_service":
            raise ScienceDerivationCheckAssetError("snapshot SourceArtifact authority is invalid")

        snapshot = Path(snapshot_path)
        inventory = Path(inventory_path)
        snapshot_bytes_digest = _bytes_digest(snapshot.read_bytes())
        inventory_payload = inventory.read_bytes()
        inventory_digest = _bytes_digest(inventory_payload)
        if snapshot_bytes_digest != asset.payload.get("content_digest"):
            raise ScienceDerivationCheckAssetError("snapshot digest does not match SourceArtifact")
        if inventory_digest != asset.payload.get("inventory_digest"):
            raise ScienceDerivationCheckAssetError("inventory digest does not match SourceArtifact")

        candidate_file = Path(package_path) / "candidate" / candidate.path
        try:
            metadata, _body = split_frontmatter(candidate_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ScienceDerivationCheckAssetError("derivation candidate cannot be parsed") from error
        check_ref = str(metadata.get("check_ref") or "").strip().removeprefix("./")
        if (
            not check_ref.startswith("scripts/sci/checks/")
            or PurePosixPath(check_ref).is_absolute()
            or ".." in PurePosixPath(check_ref).parts
            or not check_ref.endswith(".py")
        ):
            raise ScienceDerivationCheckAssetError("candidate check_ref is not an allowed asset path")
        inventory_rows = _inventory(inventory_payload)
        expected = inventory_rows.get(check_ref)
        if expected is None:
            raise ScienceDerivationCheckAssetError("candidate check_ref is absent from the inventory")
        script = _read_snapshot_member(snapshot, check_ref)
        if (_bytes_digest(script), len(script)) != expected:
            raise ScienceDerivationCheckAssetError("registered check asset digest or size is invalid")

        preflight = ScienceSourceFamilyDeterministicCheckRunner.run_preflight(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            package_path=package_path,
            ledger=ledger,
            occurred_at=occurred_at,
        )
        with tempfile.TemporaryDirectory(prefix="boi-science-check-") as temporary:
            executable = Path(temporary) / "check.py"
            executable.write_bytes(script)
            try:
                process = subprocess.run(
                    [sys.executable, str(executable)],
                    cwd=temporary,
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "PYTHONHASHSEED": "0",
                    },
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise ScienceDerivationCheckAssetError("registered derivation check timed out") from error
        if len(process.stderr) > 65536:
            raise ScienceDerivationCheckAssetError("check stderr exceeds the bounded limit")
        parsed = _parse_check_result(process.stdout)
        passed = process.returncode == 0 and parsed["pass"] is True
        check_evidence = {
            "snapshot_source_artifact_id": asset.record_id,
            "snapshot_digest": snapshot_bytes_digest,
            "inventory_digest": inventory_digest,
            "check_ref_digest": _canonical_digest(check_ref),
            "script_digest": _bytes_digest(script),
            "stdout_digest": _bytes_digest(process.stdout),
            "stderr_digest": _bytes_digest(process.stderr),
            "return_code": process.returncode,
            "typed_pass": parsed["pass"],
        }
        updated: list[ScienceCheckInput] = []
        for check in preflight.checks:
            if check.check_id == "registered-symbolic-derivation":
                updated.append(
                    check.model_copy(
                        update={
                            "outcome": CheckOutcome.PASS if passed else CheckOutcome.FAIL,
                            "evidence_digest": _canonical_digest(check_evidence),
                        }
                    )
                )
            else:
                updated.append(check)
        executor_digest = _canonical_digest(
            {
                "adapter_code_digest": _bytes_digest(Path(__file__).read_bytes()),
                "source_family_contract_digest": science_source_family_planner_code_digest(),
                "snapshot_digest": snapshot_bytes_digest,
                "inventory_digest": inventory_digest,
                "script_digest": _bytes_digest(script),
            }
        )
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            checks=updated,
            coverage_complete=True,
            evidence_complete=True,
            check_executor_code_digest=executor_digest,
            executor_resource_ids=[asset.record_id],
            ledger=ledger,
            occurred_at=occurred_at,
        )
