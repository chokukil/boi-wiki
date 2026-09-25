"""Exact-anchor EvidenceSpan extraction from immutable local Science snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import tarfile

from .ledger import GovernedRuntimeLedger, RecordKind, canonical_json


class ScienceLocalEvidenceError(RuntimeError):
    """A local source member or exact anchor is not safe to use as evidence."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


def _normalized_digest(value: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ScienceLocalEvidenceError("snapshot member digest is invalid")
    return "sha256:" + digest


def _inventory(payload: bytes) -> dict[str, tuple[str, int]]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ScienceLocalEvidenceError("snapshot inventory is invalid") from error
    result: dict[str, tuple[str, int]] = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 3 or not parts[1].isdigit():
            raise ScienceLocalEvidenceError("snapshot inventory is invalid")
        digest, size, raw_path = parts
        path = raw_path.removeprefix("./")
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
            or path in result
        ):
            raise ScienceLocalEvidenceError("snapshot inventory is invalid")
        result[path] = ("sha256:" + digest, int(size))
    return result


@dataclass(frozen=True)
class ScienceLocalEvidence:
    schema: str
    source_artifact_id: str
    evidence_span_id: str
    member_path: str
    candidate_digest: str
    anchor: str
    match_count: int
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
class LocalEvidenceRequest:
    member_path: str
    expected_member_digest: str
    anchor: str
    candidate_digest: str


class ScienceLocalEvidenceExtractor:
    """Create evidence only for one unique, literal ASCII source anchor."""

    SCHEMA = "boi-science-local-exact-anchor-evidence/v1"
    CONTEXT_BYTES = 4096

    @classmethod
    def extract(
        cls,
        *,
        snapshot_path: Path | str,
        inventory_path: Path | str,
        member_path: str,
        expected_member_digest: str,
        anchor: str,
        candidate_digest: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceLocalEvidence:
        member_name = member_path.removeprefix("./")
        if (
            PurePosixPath(member_name).is_absolute()
            or ".." in PurePosixPath(member_name).parts
            or not member_name
        ):
            raise ScienceLocalEvidenceError("snapshot member path is invalid")
        try:
            anchor_bytes = anchor.encode("ascii")
        except UnicodeEncodeError as error:
            raise ScienceLocalEvidenceError("anchor must be bounded ASCII") from error
        if len(anchor_bytes) < 4 or len(anchor_bytes) > 512 or any(byte < 32 for byte in anchor_bytes):
            raise ScienceLocalEvidenceError("anchor must be bounded ASCII")
        if (
            not candidate_digest.startswith("sha256:")
            or len(candidate_digest) != 71
        ):
            raise ScienceLocalEvidenceError("candidate digest is invalid")
        snapshot = Path(snapshot_path)
        inventory_file = Path(inventory_path)
        try:
            inventory_payload = inventory_file.read_bytes()
            row = _inventory(inventory_payload)[member_name]
            with tarfile.open(snapshot, "r:gz") as archive:
                matches = [
                    item
                    for item in archive.getmembers()
                    if item.name.removeprefix("./") == member_name
                ]
                if len(matches) != 1 or not matches[0].isfile():
                    raise ScienceLocalEvidenceError("snapshot member is unavailable")
                handle = archive.extractfile(matches[0])
                if handle is None:
                    raise ScienceLocalEvidenceError("snapshot member is unavailable")
                payload = handle.read()
        except KeyError as error:
            raise ScienceLocalEvidenceError("snapshot member is absent from inventory") from error
        except (OSError, tarfile.TarError) as error:
            raise ScienceLocalEvidenceError("snapshot member is unavailable") from error
        return cls._record(
            payload=payload,
            inventory_row=row,
            snapshot_digest=_digest_bytes(snapshot.read_bytes()),
            inventory_digest=_digest_bytes(inventory_payload),
            request=LocalEvidenceRequest(
                member_name, expected_member_digest, anchor, candidate_digest
            ),
            ledger=ledger,
            occurred_at=occurred_at,
        )

    @classmethod
    def _record(
        cls,
        *,
        payload: bytes,
        inventory_row: tuple[str, int],
        snapshot_digest: str,
        inventory_digest: str,
        request: LocalEvidenceRequest,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceLocalEvidence:
        member_name = request.member_path.removeprefix("./")
        anchor = request.anchor
        candidate_digest = request.candidate_digest
        if (
            PurePosixPath(member_name).is_absolute()
            or ".." in PurePosixPath(member_name).parts
            or not member_name
        ):
            raise ScienceLocalEvidenceError("snapshot member path is invalid")
        if not candidate_digest.startswith("sha256:") or len(candidate_digest) != 71:
            raise ScienceLocalEvidenceError("candidate digest is invalid")
        try:
            anchor_bytes = anchor.encode("ascii")
        except UnicodeEncodeError as error:
            raise ScienceLocalEvidenceError("anchor must be bounded ASCII") from error
        if len(anchor_bytes) < 4 or len(anchor_bytes) > 512 or any(byte < 32 for byte in anchor_bytes):
            raise ScienceLocalEvidenceError("anchor must be bounded ASCII")
        observed = (_digest_bytes(payload), len(payload))
        expected_member_digest = _normalized_digest(request.expected_member_digest)
        if observed != inventory_row or observed[0] != expected_member_digest:
            raise ScienceLocalEvidenceError("snapshot member digest is invalid")
        lowered = payload.lower()
        needle = anchor_bytes.lower()
        positions: list[int] = []
        offset = 0
        while True:
            match = lowered.find(needle, offset)
            if match < 0:
                break
            positions.append(match)
            offset = match + len(needle)
        if not positions:
            raise ScienceLocalEvidenceError("exact anchor was not found")
        if len(positions) != 1:
            raise ScienceLocalEvidenceError("exact anchor is ambiguous")
        anchor_at = positions[0]
        byte_start = max(0, anchor_at - cls.CONTEXT_BYTES)
        byte_end = min(len(payload), anchor_at + len(anchor_bytes) + cls.CONTEXT_BYTES)
        evidence_bytes = payload[byte_start:byte_end]
        if len(evidence_bytes) > 11 * 1024:
            raise ScienceLocalEvidenceError("evidence span exceeds bounded input limit")
        extractor_code_digest = _digest_bytes(Path(__file__).read_bytes())
        source = ledger.append(
            RecordKind.SOURCE_ARTIFACT,
            {
                "content_digest": observed[0],
                "byte_length": observed[1],
                "resource": member_name,
                "source_family": "local-snapshot",
                "snapshot_digest": snapshot_digest,
                "snapshot_inventory_digest": inventory_digest,
            },
            authority="intake_service",
            occurred_at=occurred_at,
        )
        extraction = {
            "schema": cls.SCHEMA,
            "source_artifact_id": source.record_id,
            "source_content_digest": observed[0],
            "member_path": member_name,
            "candidate_digest": candidate_digest,
            "anchor": anchor,
            "match_count": 1,
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
                "source_artifact_id": source.record_id,
                "resource": member_name,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "content_digest": _digest_bytes(evidence_bytes),
                "candidate_digest": candidate_digest,
                "anchor_digest": _digest_bytes(anchor_bytes),
                "match_count": 1,
                "extraction_digest": extraction_digest,
                "extractor_code_digest": extractor_code_digest,
                "verdict": None,
            },
            authority="evidence_service",
            occurred_at=occurred_at,
        )
        return ScienceLocalEvidence(
            schema=cls.SCHEMA,
            source_artifact_id=source.record_id,
            evidence_span_id=span.record_id,
            member_path=member_name,
            candidate_digest=candidate_digest,
            anchor=anchor,
            match_count=1,
            byte_start=byte_start,
            byte_end=byte_end,
            evidence_bytes=evidence_bytes,
            extraction_digest=extraction_digest,
            extractor_code_digest=extractor_code_digest,
        )

    @classmethod
    def extract_many(
        cls,
        *,
        snapshot_path: Path | str,
        inventory_path: Path | str,
        requests: tuple[LocalEvidenceRequest, ...],
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> tuple[ScienceLocalEvidence, ...]:
        if not requests:
            return ()
        snapshot = Path(snapshot_path)
        inventory_file = Path(inventory_path)
        try:
            inventory_payload = inventory_file.read_bytes()
            rows = _inventory(inventory_payload)
            wanted = {item.member_path.removeprefix("./") for item in requests}
            with tarfile.open(snapshot, "r:gz") as archive:
                members = {
                    item.name.removeprefix("./"): item
                    for item in archive.getmembers()
                    if item.isfile() and item.name.removeprefix("./") in wanted
                }
                if set(members) != wanted:
                    raise ScienceLocalEvidenceError("snapshot member is unavailable")
                payloads = {}
                for name, member in members.items():
                    handle = archive.extractfile(member)
                    if handle is None:
                        raise ScienceLocalEvidenceError("snapshot member is unavailable")
                    payloads[name] = handle.read()
        except (OSError, KeyError, tarfile.TarError) as error:
            raise ScienceLocalEvidenceError("snapshot batch is unavailable") from error
        snapshot_digest = _digest_bytes(snapshot.read_bytes())
        inventory_digest = _digest_bytes(inventory_payload)
        results = []
        for request in requests:
            name = request.member_path.removeprefix("./")
            if name not in rows:
                raise ScienceLocalEvidenceError("snapshot member is absent from inventory")
            results.append(
                cls._record(
                    payload=payloads[name],
                    inventory_row=rows[name],
                    snapshot_digest=snapshot_digest,
                    inventory_digest=inventory_digest,
                    request=request,
                    ledger=ledger,
                    occurred_at=occurred_at,
                )
            )
        return tuple(results)


__all__ = [
    "LocalEvidenceRequest",
    "ScienceLocalEvidence",
    "ScienceLocalEvidenceError",
    "ScienceLocalEvidenceExtractor",
]
