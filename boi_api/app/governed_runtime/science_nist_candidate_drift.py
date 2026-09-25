"""Read-only drift audit between Science candidates and NIST EvidenceSpans."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import unicodedata

import yaml

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, canonical_json
from ..okf import split_frontmatter


class ScienceNistCandidateDriftError(RuntimeError):
    """Candidate or NIST evidence closure is missing, altered, or ambiguous."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _normalized_text(value: object) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split()).casefold()


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ScienceNistCandidateDriftError("numeric evidence is invalid") from error
    if not result.is_finite():
        raise ScienceNistCandidateDriftError("numeric evidence is invalid")
    return result.normalize()


def _uncertainty_matches(candidate: object, observed: object) -> bool:
    candidate_value = str(candidate or "").strip()
    observed_value = str(observed or "").strip()
    if observed_value.casefold() == "exact":
        return candidate_value == ""
    if not candidate_value or not observed_value:
        return False
    return _decimal(candidate_value) == _decimal(observed_value)


@dataclass(frozen=True)
class ScienceNistCandidateDriftItem:
    candidate_path: str
    candidate_digest: str
    resource: str
    source_artifact_id: str
    evidence_span_id: str
    source_status: str
    candidate_value_status: str
    name_matched: bool
    value_matched: bool
    relative_uncertainty_matched: bool
    value_status_compared: bool
    unit_ref_compared: bool
    outcome: str


@dataclass(frozen=True)
class ScienceNistCandidateDriftAudit:
    schema: str
    package_digest: str
    items: tuple[ScienceNistCandidateDriftItem, ...]
    total: int
    exact_numeric_and_uncertainty: int
    attention_required: int
    result_digest: str
    model_invocations: int = 0
    checks_recorded: int = 0
    verdicts: int = 0
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceNistCandidateDriftAuditor:
    """Join by declared NIST resource and compare only source-observed fields."""

    SCHEMA = "boi-science-nist-candidate-drift-audit/v1"

    @classmethod
    def audit(
        cls,
        *,
        candidate_package: Path | str,
        evidence_root: Path | str,
    ) -> ScienceNistCandidateDriftAudit:
        package = Path(candidate_package)
        root = Path(evidence_root)
        try:
            manifest = json.loads((package / "candidate-manifest.json").read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ScienceNistCandidateDriftError("candidate manifest is unavailable") from error
        knowledge = manifest.get("knowledge")
        package_digest = str(manifest.get("package_digest") or "")
        if not isinstance(knowledge, list) or not package_digest.startswith("sha256:"):
            raise ScienceNistCandidateDriftError("candidate manifest is invalid")
        manifest_items = {
            str(item.get("path") or ""): str(item.get("candidate_digest") or "")
            for item in knowledge
            if isinstance(item, dict)
        }
        ledger = GovernedRuntimeLedger(root / "ledger")
        evidence_by_resource: dict[str, tuple[object, object, dict[str, object]]] = {}
        for path in sorted((root / "ledger/records/EvidenceSpan").glob("*.json")):
            try:
                raw_record = json.loads(path.read_text())
                span = ledger.read(str(raw_record["record_id"]))
                source = ledger.read(str(span.payload.get("source_artifact_id") or ""))
            except (OSError, json.JSONDecodeError, KeyError, LedgerError) as error:
                raise ScienceNistCandidateDriftError("NIST evidence ledger is invalid") from error
            semantic = span.payload.get("semantic_fields")
            resource = str(span.payload.get("resource") or "")
            if (
                span.kind is not RecordKind.EVIDENCE_SPAN
                or source.kind is not RecordKind.SOURCE_ARTIFACT
                or source.payload.get("source_family") != "nist"
                or source.payload.get("resource") != resource
                or not isinstance(semantic, dict)
            ):
                continue
            object_ref = Path(str(source.payload.get("object_ref") or ""))
            if object_ref.is_absolute() or ".." in object_ref.parts:
                raise ScienceNistCandidateDriftError("NIST source object ref is invalid")
            try:
                source_bytes = (root / "artifacts" / object_ref).read_bytes()
                start = int(span.payload.get("byte_start"))
                end = int(span.payload.get("byte_end"))
            except (OSError, TypeError, ValueError) as error:
                raise ScienceNistCandidateDriftError("NIST source bytes are unavailable") from error
            if (
                _digest_bytes(source_bytes) != source.payload.get("content_digest")
                or len(source_bytes) != source.payload.get("byte_length")
                or start < 0
                or end <= start
                or end > len(source_bytes)
                or _digest_bytes(source_bytes[start:end]) != span.payload.get("content_digest")
            ):
                raise ScienceNistCandidateDriftError("NIST source bytes are invalid")
            if resource in evidence_by_resource:
                raise ScienceNistCandidateDriftError("NIST resource evidence is ambiguous")
            evidence_by_resource[resource] = (source, span, semantic)

        items = []
        for relative, expected_digest in sorted(manifest_items.items()):
            parts = Path(relative).parts
            if not any(
                parts[index : index + 2] == ("science", "constants")
                for index in range(max(0, len(parts) - 1))
            ):
                continue
            candidate_path = package / "candidate" / relative
            try:
                candidate_bytes = candidate_path.read_bytes()
            except OSError as error:
                raise ScienceNistCandidateDriftError("candidate bytes are unavailable") from error
            if _digest_bytes(candidate_bytes) != expected_digest:
                raise ScienceNistCandidateDriftError("candidate digest is invalid")
            try:
                metadata, _body = split_frontmatter(candidate_bytes.decode("utf-8"))
                if not metadata:
                    continue
                parsed = yaml.safe_load(candidate_bytes.decode("utf-8").split("---", 2)[1])
            except (UnicodeDecodeError, ValueError, yaml.YAMLError) as error:
                raise ScienceNistCandidateDriftError("candidate frontmatter is invalid") from error
            if not isinstance(parsed, dict) or parsed.get("type") != "boi/sci-constant":
                continue
            resources = [
                str(source.get("resource") or "")
                for source in parsed.get("sources", [])
                if isinstance(source, dict) and source.get("relation") == "evidence"
            ]
            matches = [resource for resource in resources if resource in evidence_by_resource]
            if not matches:
                continue
            if len(matches) != 1:
                raise ScienceNistCandidateDriftError("candidate NIST evidence is ambiguous")
            resource = matches[0]
            source, span, semantic = evidence_by_resource[resource]
            required = {
                "name", "numerical_value", "relative_standard_uncertainty", "source_status"
            }
            if not required <= set(semantic):
                raise ScienceNistCandidateDriftError("NIST semantic evidence is incomplete")
            name_matched = _normalized_text(semantic["name"]) in _normalized_text(parsed.get("title"))
            value_matched = _decimal(parsed.get("value")) == _decimal(semantic["numerical_value"])
            uncertainty_matched = _uncertainty_matches(
                parsed.get("uncertainty"), semantic["relative_standard_uncertainty"]
            )
            if not name_matched:
                outcome = "NAME_MISMATCH"
            elif value_matched and uncertainty_matched:
                outcome = "EXACT_NUMERIC_AND_UNCERTAINTY"
            elif not value_matched and not uncertainty_matched:
                outcome = "VALUE_AND_UNCERTAINTY_DRIFT"
            elif not value_matched:
                outcome = "VALUE_DRIFT"
            else:
                outcome = "UNCERTAINTY_DRIFT"
            items.append(
                ScienceNistCandidateDriftItem(
                    candidate_path=relative,
                    candidate_digest=expected_digest,
                    resource=resource,
                    source_artifact_id=source.record_id,
                    evidence_span_id=span.record_id,
                    source_status=str(semantic["source_status"]),
                    candidate_value_status=str(parsed.get("value_status") or ""),
                    name_matched=name_matched,
                    value_matched=value_matched,
                    relative_uncertainty_matched=uncertainty_matched,
                    value_status_compared=False,
                    unit_ref_compared=False,
                    outcome=outcome,
                )
            )
        envelope = {
            "schema": cls.SCHEMA,
            "package_digest": package_digest,
            "items": [asdict(item) for item in items],
            "value_status_compared": False,
            "unit_ref_compared": False,
        }
        exact = sum(item.outcome == "EXACT_NUMERIC_AND_UNCERTAINTY" for item in items)
        return ScienceNistCandidateDriftAudit(
            schema=cls.SCHEMA,
            package_digest=package_digest,
            items=tuple(items),
            total=len(items),
            exact_numeric_and_uncertainty=exact,
            attention_required=len(items) - exact,
            result_digest=_digest_bytes(canonical_json(envelope)),
        )


__all__ = [
    "ScienceNistCandidateDriftAudit",
    "ScienceNistCandidateDriftAuditor",
    "ScienceNistCandidateDriftError",
    "ScienceNistCandidateDriftItem",
]
