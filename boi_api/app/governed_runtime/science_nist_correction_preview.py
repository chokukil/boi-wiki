"""Strict, read-only previews for evidence-bound NIST correction candidates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..okf import split_frontmatter
from .canonical_candidate_writer import CanonicalCandidateWriter, CanonicalCandidateWriterError
from .ledger import canonical_json
from .okf_v02 import validate_boi_profile_v02
from .science_nist_correction_candidates import ScienceNistCorrectionCandidateBuilder


class ScienceNistCorrectionPreviewError(RuntimeError):
    """The frozen candidate or correction closure cannot be previewed safely."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ScienceNistCorrectionPreviewError(f"{label} is unavailable") from error
    if not isinstance(value, dict):
        raise ScienceNistCorrectionPreviewError(f"{label} is invalid")
    return value


def _safe_relative(value: object, *, label: str) -> Path:
    path = Path(str(value or ""))
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ScienceNistCorrectionPreviewError(f"{label} is invalid")
    return path


@dataclass(frozen=True)
class ScienceNistCorrectionPreviewItem:
    candidate_path: str
    before_digest: str
    before_metadata_digest: str
    after_metadata_digest: str
    preview_document_digest: str
    body_digest: str
    body_digest_unchanged: bool
    changed_fields: tuple[str, ...]
    evidence_span_id: str
    patch_digest: str


@dataclass(frozen=True)
class ScienceNistCorrectionPreview:
    schema: str
    correction_package_digest: str
    source_candidate_package_digest: str
    items: tuple[ScienceNistCorrectionPreviewItem, ...]
    candidate_count: int
    strict_draft_valid: int
    preview_digest: str
    approval_ready: bool = False
    model_invocations: int = 0
    checks_recorded: int = 0
    verdicts: int = 0
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceNistCorrectionPreviewer:
    """Apply numeric patches in memory and validate the would-be strict documents."""

    SCHEMA = "boi-science-nist-correction-preview/v1"
    ALLOWED_PATHS = frozenset({"/uncertainty", "/value"})

    @classmethod
    def preview(
        cls,
        *,
        candidate_package: Path | str,
        correction_package: Path | str,
    ) -> ScienceNistCorrectionPreview:
        source_root = Path(candidate_package)
        correction_root = Path(correction_package)
        source_manifest = _read_json(
            source_root / "candidate-manifest.json", label="source candidate manifest"
        )
        manifest = _read_json(
            correction_root / "candidate-manifest.json", label="correction manifest"
        )
        if manifest.get("schema") != ScienceNistCorrectionCandidateBuilder.SCHEMA:
            raise ScienceNistCorrectionPreviewError("correction manifest schema is invalid")
        package_digest = str(manifest.get("package_digest") or "")
        manifest_body = {key: value for key, value in manifest.items() if key != "package_digest"}
        if package_digest != _digest_bytes(canonical_json(manifest_body)):
            raise ScienceNistCorrectionPreviewError("correction package digest is invalid")
        source_package_digest = str(source_manifest.get("package_digest") or "")
        if (
            not source_package_digest.startswith("sha256:")
            or manifest.get("source_candidate_package_digest") != source_package_digest
        ):
            raise ScienceNistCorrectionPreviewError("source candidate package digest is invalid")
        descriptors = manifest.get("patches")
        if not isinstance(descriptors, list) or len(descriptors) > 100:
            raise ScienceNistCorrectionPreviewError("correction patch closure is invalid")
        if manifest.get("candidate_count") != len(descriptors):
            raise ScienceNistCorrectionPreviewError("correction candidate count is invalid")

        referenced_files = {"candidate-manifest.json"}
        patch_payloads: list[tuple[dict[str, Any], str]] = []
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                raise ScienceNistCorrectionPreviewError("correction patch descriptor is invalid")
            relative = _safe_relative(descriptor.get("ref"), label="correction patch ref")
            if relative.parts[0] != "patches" or relative.suffix != ".json":
                raise ScienceNistCorrectionPreviewError("correction patch ref is invalid")
            ref = relative.as_posix()
            if ref in referenced_files:
                raise ScienceNistCorrectionPreviewError("correction patch ref is duplicated")
            referenced_files.add(ref)
            try:
                payload = (correction_root / relative).read_bytes()
            except OSError as error:
                raise ScienceNistCorrectionPreviewError("correction patch is unavailable") from error
            patch_digest = _digest_bytes(payload)
            if descriptor.get("digest") != patch_digest:
                raise ScienceNistCorrectionPreviewError("patch digest is invalid")
            try:
                patch = json.loads(payload)
            except json.JSONDecodeError as error:
                raise ScienceNistCorrectionPreviewError("correction patch is invalid") from error
            if not isinstance(patch, dict):
                raise ScienceNistCorrectionPreviewError("correction patch is invalid")
            patch_payloads.append((patch, patch_digest))
        actual_files = {
            path.relative_to(correction_root).as_posix()
            for path in correction_root.rglob("*")
            if path.is_file()
        }
        if actual_files != referenced_files:
            raise ScienceNistCorrectionPreviewError("correction patch closure is invalid")

        items: list[ScienceNistCorrectionPreviewItem] = []
        seen_candidate_paths: set[str] = set()
        for patch, patch_digest in patch_payloads:
            if (
                patch.get("schema") != ScienceNistCorrectionCandidateBuilder.PATCH_SCHEMA
                or patch.get("status") != "candidate"
                or patch.get("approval_ready") is not False
                or patch.get("active_release_transition") is not False
            ):
                raise ScienceNistCorrectionPreviewError("correction patch authority is invalid")
            candidate_relative = _safe_relative(
                patch.get("candidate_path"), label="candidate path"
            )
            candidate_path = candidate_relative.as_posix()
            if candidate_path in seen_candidate_paths:
                raise ScienceNistCorrectionPreviewError("candidate path is duplicated")
            seen_candidate_paths.add(candidate_path)
            try:
                source_bytes = (source_root / "candidate" / candidate_relative).read_bytes()
            except OSError as error:
                raise ScienceNistCorrectionPreviewError("candidate bytes are unavailable") from error
            before_digest = _digest_bytes(source_bytes)
            if patch.get("before_digest") != before_digest:
                raise ScienceNistCorrectionPreviewError("before digest is stale")
            try:
                metadata, body = split_frontmatter(source_bytes.decode("utf-8"))
            except UnicodeDecodeError as error:
                raise ScienceNistCorrectionPreviewError("candidate document is not UTF-8") from error
            if not metadata:
                raise ScienceNistCorrectionPreviewError("candidate frontmatter is invalid")
            updated: dict[str, Any] = deepcopy(metadata)
            operations = patch.get("operations")
            if not isinstance(operations, list) or not operations:
                raise ScienceNistCorrectionPreviewError("correction operations are invalid")
            changed_fields: list[str] = []
            for operation in operations:
                if not isinstance(operation, Mapping):
                    raise ScienceNistCorrectionPreviewError("correction operation is invalid")
                pointer = str(operation.get("path") or "")
                if operation.get("op") != "replace" or pointer not in cls.ALLOWED_PATHS:
                    raise ScienceNistCorrectionPreviewError("correction operation is not allowed")
                field = pointer.removeprefix("/")
                if field in changed_fields:
                    raise ScienceNistCorrectionPreviewError("correction field is duplicated")
                if not isinstance(operation.get("value"), str):
                    raise ScienceNistCorrectionPreviewError("correction value must be a string")
                updated[field] = operation["value"]
                changed_fields.append(field)
            validation = validate_boi_profile_v02(updated)
            if not validation.ok:
                codes = "|".join(sorted({error.code for error in validation.errors}))
                raise ScienceNistCorrectionPreviewError(
                    f"strict draft validation failed: {codes or 'BOI_V02_INVALID'}"
                )
            try:
                preview_document = CanonicalCandidateWriter.render(updated, body)
            except CanonicalCandidateWriterError as error:
                raise ScienceNistCorrectionPreviewError("strict draft rendering failed") from error
            body_digest = _digest_bytes(body.encode("utf-8"))
            items.append(
                ScienceNistCorrectionPreviewItem(
                    candidate_path=candidate_path,
                    before_digest=before_digest,
                    before_metadata_digest=_digest_bytes(canonical_json(metadata)),
                    after_metadata_digest=_digest_bytes(canonical_json(updated)),
                    preview_document_digest=_digest_bytes(preview_document),
                    body_digest=body_digest,
                    body_digest_unchanged=True,
                    changed_fields=tuple(sorted(changed_fields)),
                    evidence_span_id=str(patch.get("evidence_span_id") or ""),
                    patch_digest=patch_digest,
                )
            )
        envelope = {
            "schema": cls.SCHEMA,
            "correction_package_digest": package_digest,
            "source_candidate_package_digest": source_package_digest,
            "items": [asdict(item) for item in items],
            "candidate_count": len(items),
            "strict_draft_valid": len(items),
            "authority": {
                "approval_ready": False,
                "model_invocations": 0,
                "checks_recorded": 0,
                "verdicts": 0,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
        }
        return ScienceNistCorrectionPreview(
            schema=cls.SCHEMA,
            correction_package_digest=package_digest,
            source_candidate_package_digest=source_package_digest,
            items=tuple(items),
            candidate_count=len(items),
            strict_draft_valid=len(items),
            preview_digest=_digest_bytes(canonical_json(envelope)),
        )


__all__ = [
    "ScienceNistCorrectionPreview",
    "ScienceNistCorrectionPreviewError",
    "ScienceNistCorrectionPreviewItem",
    "ScienceNistCorrectionPreviewer",
]
