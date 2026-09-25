"""Exact MathML-digest EvidenceSpans from immutable Science snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile

from .ledger import GovernedRuntimeLedger, RecordKind, canonical_json


class ScienceMathMlEvidenceError(RuntimeError):
    """A declared MathML locator cannot be resolved exactly and safely."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


def _full_digest(value: str, *, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ScienceMathMlEvidenceError(f"{label} digest is invalid")
    return "sha256:" + digest


def _member_name(value: str) -> str:
    name = value.removeprefix("./")
    if not name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
        raise ScienceMathMlEvidenceError("snapshot member path is invalid")
    return name


def _inventory(payload: bytes) -> dict[str, tuple[str, int]]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ScienceMathMlEvidenceError("snapshot inventory is invalid") from error
    result: dict[str, tuple[str, int]] = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 3 or not parts[1].isdigit():
            raise ScienceMathMlEvidenceError("snapshot inventory is invalid")
        digest, size, raw_name = parts
        name = _member_name(raw_name)
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or name in result
        ):
            raise ScienceMathMlEvidenceError("snapshot inventory is invalid")
        result[name] = ("sha256:" + digest, int(size))
    return result


@dataclass(frozen=True)
class MathMlSourceRef:
    member_path: str
    expected_member_digest: str


@dataclass(frozen=True)
class MathMlEvidenceRequest:
    candidate_digest: str
    locator_digests: tuple[str, ...]
    sources: tuple[MathMlSourceRef, ...]


@dataclass(frozen=True)
class ScienceMathMlEvidence:
    schema: str
    source_artifact_id: str
    evidence_span_id: str
    member_path: str
    candidate_digest: str
    locator_digest: str
    mathml_digest: str
    byte_start: int
    byte_end: int
    evidence_bytes: bytes
    extraction_digest: str
    extractor_code_digest: str
    model_invocations: int = 0
    verdict: None = None
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class _ResolvedMathMl:
    source: MathMlSourceRef
    payload: bytes
    locator_digest: str
    mathml_digest: str
    math_start: int
    math_end: int


class ScienceMathMlEvidenceExtractor:
    """Resolve declared digest prefixes to exactly one raw MathML element."""

    SCHEMA = "boi-science-mathml-digest-evidence/v1"
    CONTEXT_BYTES = 4096
    MAX_EVIDENCE_BYTES = 11 * 1024
    _MATH = re.compile(br"<math\b[^>]*>.*?</math>", re.DOTALL)

    @classmethod
    def extract(
        cls,
        *,
        snapshot_path: Path | str,
        inventory_path: Path | str,
        request: MathMlEvidenceRequest,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> tuple[ScienceMathMlEvidence, ...]:
        candidate_digest = _full_digest(request.candidate_digest, label="candidate")
        if not request.sources or not request.locator_digests:
            raise ScienceMathMlEvidenceError("MathML source closure is empty")
        if len(set(request.locator_digests)) != len(request.locator_digests):
            raise ScienceMathMlEvidenceError("MathML locator digest is duplicated")
        locators = []
        for raw in request.locator_digests:
            locator = raw.removeprefix("sha256:").lower()
            if (
                len(locator) < 12
                or len(locator) > 64
                or any(char not in "0123456789abcdef" for char in locator)
            ):
                raise ScienceMathMlEvidenceError("MathML locator digest is invalid")
            locators.append(locator)

        normalized_sources = tuple(
            MathMlSourceRef(
                _member_name(source.member_path),
                _full_digest(source.expected_member_digest, label="snapshot member"),
            )
            for source in request.sources
        )
        if len({source.member_path for source in normalized_sources}) != len(
            normalized_sources
        ):
            raise ScienceMathMlEvidenceError("snapshot member is duplicated")

        snapshot = Path(snapshot_path)
        inventory_file = Path(inventory_path)
        try:
            inventory_payload = inventory_file.read_bytes()
            inventory = _inventory(inventory_payload)
            with tarfile.open(snapshot, "r:gz") as archive:
                members = {
                    item.name.removeprefix("./"): item
                    for item in archive.getmembers()
                    if item.isfile()
                    and item.name.removeprefix("./")
                    in {source.member_path for source in normalized_sources}
                }
                if set(members) != {source.member_path for source in normalized_sources}:
                    raise ScienceMathMlEvidenceError("snapshot member is unavailable")
                payloads: dict[str, bytes] = {}
                for source in normalized_sources:
                    row = inventory.get(source.member_path)
                    handle = archive.extractfile(members[source.member_path])
                    if row is None or handle is None:
                        raise ScienceMathMlEvidenceError("snapshot member is unavailable")
                    payload = handle.read()
                    observed = (_digest_bytes(payload), len(payload))
                    if observed != row or observed[0] != source.expected_member_digest:
                        raise ScienceMathMlEvidenceError("snapshot member digest is invalid")
                    payloads[source.member_path] = payload
        except (OSError, tarfile.TarError) as error:
            raise ScienceMathMlEvidenceError("snapshot is unavailable") from error

        resolved: list[_ResolvedMathMl] = []
        for locator in locators:
            matches: list[_ResolvedMathMl] = []
            for source in normalized_sources:
                payload = payloads[source.member_path]
                for match in cls._MATH.finditer(payload):
                    mathml_digest = _digest_bytes(match.group())
                    if mathml_digest.removeprefix("sha256:").startswith(locator):
                        matches.append(
                            _ResolvedMathMl(
                                source=source,
                                payload=payload,
                                locator_digest="sha256:" + locator,
                                mathml_digest=mathml_digest,
                                math_start=match.start(),
                                math_end=match.end(),
                            )
                        )
            if not matches:
                raise ScienceMathMlEvidenceError("MathML locator is missing")
            if len(matches) != 1:
                raise ScienceMathMlEvidenceError("MathML locator is ambiguous")
            resolved.append(matches[0])

        # Validate the complete request before creating even a SourceArtifact.
        # This keeps multi-locator extraction all-or-nothing at the ledger boundary.
        for item in resolved:
            byte_start = max(0, item.math_start - cls.CONTEXT_BYTES)
            byte_end = min(len(item.payload), item.math_end + cls.CONTEXT_BYTES)
            if byte_end - byte_start > cls.MAX_EVIDENCE_BYTES:
                raise ScienceMathMlEvidenceError("evidence span exceeds bounded input limit")

        snapshot_digest = _digest_bytes(snapshot.read_bytes())
        inventory_digest = _digest_bytes(inventory_payload)
        extractor_code_digest = _digest_bytes(Path(__file__).read_bytes())
        results: list[ScienceMathMlEvidence] = []
        sources_by_path = {}
        for item in resolved:
            source_record = sources_by_path.get(item.source.member_path)
            if source_record is None:
                source_record = ledger.append(
                    RecordKind.SOURCE_ARTIFACT,
                    {
                        "content_digest": item.source.expected_member_digest,
                        "byte_length": len(item.payload),
                        "resource": item.source.member_path,
                        "source_family": "local-snapshot",
                        "snapshot_digest": snapshot_digest,
                        "snapshot_inventory_digest": inventory_digest,
                    },
                    authority="intake_service",
                    occurred_at=occurred_at,
                )
                sources_by_path[item.source.member_path] = source_record
            byte_start = max(0, item.math_start - cls.CONTEXT_BYTES)
            byte_end = min(len(item.payload), item.math_end + cls.CONTEXT_BYTES)
            evidence_bytes = item.payload[byte_start:byte_end]
            extraction = {
                "schema": cls.SCHEMA,
                "source_artifact_id": source_record.record_id,
                "source_content_digest": item.source.expected_member_digest,
                "member_path": item.source.member_path,
                "candidate_digest": candidate_digest,
                "locator_digest": item.locator_digest,
                "mathml_digest": item.mathml_digest,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "evidence_content_digest": _digest_bytes(evidence_bytes),
                "extractor_code_digest": extractor_code_digest,
                "verdict": None,
            }
            extraction_digest = _digest(extraction)
            span = ledger.append(
                RecordKind.EVIDENCE_SPAN,
                {
                    "source_artifact_id": source_record.record_id,
                    "resource": item.source.member_path,
                    "byte_start": byte_start,
                    "byte_end": byte_end,
                    "content_digest": _digest_bytes(evidence_bytes),
                    "candidate_digest": candidate_digest,
                    "locator_digest": item.locator_digest,
                    "mathml_digest": item.mathml_digest,
                    "extraction_digest": extraction_digest,
                    "extractor_code_digest": extractor_code_digest,
                    "verdict": None,
                },
                authority="evidence_service",
                occurred_at=occurred_at,
            )
            results.append(
                ScienceMathMlEvidence(
                    schema=cls.SCHEMA,
                    source_artifact_id=source_record.record_id,
                    evidence_span_id=span.record_id,
                    member_path=item.source.member_path,
                    candidate_digest=candidate_digest,
                    locator_digest=item.locator_digest,
                    mathml_digest=item.mathml_digest,
                    byte_start=byte_start,
                    byte_end=byte_end,
                    evidence_bytes=evidence_bytes,
                    extraction_digest=extraction_digest,
                    extractor_code_digest=extractor_code_digest,
                )
            )
        return tuple(results)


__all__ = [
    "MathMlEvidenceRequest",
    "MathMlSourceRef",
    "ScienceMathMlEvidence",
    "ScienceMathMlEvidenceError",
    "ScienceMathMlEvidenceExtractor",
]
