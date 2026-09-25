"""Candidate-independent SI base-unit registry projection from BIPM page text."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, canonical_json


class ScienceBipmBaseUnitRegistryError(RuntimeError):
    """The official page closure cannot produce an exact base-unit registry."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


def _full_digest(value: str, *, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ScienceBipmBaseUnitRegistryError(f"{label} digest is invalid")
    return "sha256:" + digest


@dataclass(frozen=True)
class ScienceBipmBaseUnitRegistryEntry:
    name: str
    symbol: str
    quantity: str
    definition: str
    source_artifact_id: str
    evidence_span_id: str
    object_ref: str
    content_digest: str


@dataclass(frozen=True)
class ScienceBipmBaseUnitRegistryProjection:
    schema: str
    projection_digest: str
    source_projection_digest: str
    entries: tuple[ScienceBipmBaseUnitRegistryEntry, ...]
    projector_code_digest: str
    candidate_inputs: int = 0
    model_invocations: int = 0
    verdict: None = None
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceBipmBaseUnitRegistryProjector:
    """Parse the seven official definition sentences without candidate input."""

    SCHEMA = "boi-science-bipm-base-unit-registry-projection/v1"
    ENTRY_SCHEMA = "boi-si-unit-registry-entry/v1"
    LANDING_RESOURCE = "https://www.bipm.org/en/publications/si-brochure"
    SECTION_START = b"2.3.1  Base units"
    SECTION_END = b"2.3.3  Dimensions of quantities"
    DEFINITION = re.compile(
        rb"The (?P<name>[a-z]+), symbol (?P<symbol>[A-Za-z]+), is the SI unit of "
        rb"(?P<quantity>[^.\r\n]+)\."
    )

    @staticmethod
    def _store(root: Path, payload: bytes) -> str:
        digest = _digest_bytes(payload).removeprefix("sha256:")
        ref = Path("objects") / "sha256" / digest
        path = root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != payload:
                raise ScienceBipmBaseUnitRegistryError("content-addressed object conflict")
            return ref.as_posix()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return ref.as_posix()

    @classmethod
    def project(
        cls,
        *,
        artifact_root: Path | str,
        ledger: GovernedRuntimeLedger,
        projection_digest: str,
        page_source_artifact_ids: tuple[str, ...],
        declared_resource: str,
        occurred_at: str,
    ) -> ScienceBipmBaseUnitRegistryProjection:
        source_projection_digest = _full_digest(projection_digest, label="projection")
        if declared_resource != cls.LANDING_RESOURCE:
            raise ScienceBipmBaseUnitRegistryError("BIPM declared resource is invalid")
        if (
            not page_source_artifact_ids
            or len(set(page_source_artifact_ids)) != len(page_source_artifact_ids)
        ):
            raise ScienceBipmBaseUnitRegistryError("PDF page closure is invalid")

        root = Path(artifact_root)
        pages: list[tuple[object, bytes]] = []
        closure: tuple[str, str, str] | None = None
        previous_page = 0
        try:
            for page_id in page_source_artifact_ids:
                record = ledger.read(page_id)
                payload = record.payload
                page_number = int(payload.get("page_number") or 0)
                if (
                    record.kind is not RecordKind.SOURCE_ARTIFACT
                    or payload.get("source_family") != "pdf-page-text-projection"
                    or payload.get("projection_digest") != source_projection_digest
                    or page_number <= previous_page
                ):
                    raise ScienceBipmBaseUnitRegistryError("PDF page closure is invalid")
                object_ref = Path(str(payload.get("object_ref") or ""))
                if object_ref.is_absolute() or ".." in object_ref.parts:
                    raise ScienceBipmBaseUnitRegistryError("PDF page object ref is invalid")
                page_bytes = (root / object_ref).read_bytes()
                if (
                    _digest_bytes(page_bytes) != payload.get("content_digest")
                    or len(page_bytes) != payload.get("byte_length")
                ):
                    raise ScienceBipmBaseUnitRegistryError("PDF page bytes are invalid")
                page_closure = (
                    str(payload.get("derived_from_source_artifact_id") or ""),
                    str(payload.get("source_content_digest") or ""),
                    str(payload.get("parser_digest") or ""),
                )
                if not all(page_closure) or (closure is not None and page_closure != closure):
                    raise ScienceBipmBaseUnitRegistryError("PDF page closure is inconsistent")
                closure = page_closure
                previous_page = page_number
                pages.append((record, page_bytes))
        except (LedgerError, OSError, TypeError, ValueError) as error:
            if isinstance(error, ScienceBipmBaseUnitRegistryError):
                raise
            raise ScienceBipmBaseUnitRegistryError("PDF page bytes are unavailable") from error

        joined = b"\n".join(page for _record, page in pages)
        if joined.count(cls.SECTION_START) != 1 or joined.count(cls.SECTION_END) != 1:
            raise ScienceBipmBaseUnitRegistryError("BIPM base-unit section is missing or ambiguous")
        start = joined.index(cls.SECTION_START)
        end = joined.index(cls.SECTION_END)
        if start >= end:
            raise ScienceBipmBaseUnitRegistryError("BIPM base-unit section is invalid")
        section = joined[start:end]
        matches = list(cls.DEFINITION.finditer(section))
        parsed = [
            {
                key: match.group(key).decode("utf-8").strip()
                for key in ("name", "symbol", "quantity")
            }
            | {"definition": match.group(0).decode("utf-8")}
            for match in matches
        ]
        if (
            len(parsed) != 7
            or len({item["name"] for item in parsed}) != 7
            or len({item["symbol"] for item in parsed}) != 7
        ):
            raise ScienceBipmBaseUnitRegistryError(
                "BIPM base-unit section must contain exactly seven unique definitions"
            )

        projector_code_digest = _digest_bytes(Path(__file__).read_bytes())
        descriptors = []
        for item in parsed:
            entry = {
                "schema": cls.ENTRY_SCHEMA,
                "symbol": item["symbol"],
                "name": item["name"],
                "quantity": item["quantity"],
                "classification": "si-base",
                "definition": item["definition"],
                "si_factor": "1",
                "si_unit": f"{item['symbol']} (base)",
                "si_base": {item["symbol"]: 1},
                "source_projection_digest": source_projection_digest,
                "source_section_digest": _digest_bytes(section),
            }
            entry_bytes = json.dumps(
                entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            descriptors.append((item, entry_bytes, _digest_bytes(entry_bytes)))
        registry_projection_digest = _digest(
            {
                "schema": cls.SCHEMA,
                "source_projection_digest": source_projection_digest,
                "raw_source_artifact_id": closure[0],
                "declared_resource": declared_resource,
                "section_start_digest": _digest_bytes(cls.SECTION_START),
                "section_end_digest": _digest_bytes(cls.SECTION_END),
                "entries": [digest for _item, _bytes, digest in descriptors],
                "projector_code_digest": projector_code_digest,
            }
        )

        results = []
        for item, entry_bytes, content_digest in descriptors:
            object_ref = cls._store(root, entry_bytes)
            source = ledger.append(
                RecordKind.SOURCE_ARTIFACT,
                {
                    "content_digest": content_digest,
                    "byte_length": len(entry_bytes),
                    "resource": declared_resource,
                    "source_resource": pages[0][0].payload.get("resource"),
                    "source_family": "bipm-si-base-registry-projection",
                    "media_type": "application/json",
                    "object_ref": object_ref,
                    "derived_from_source_artifact_id": closure[0],
                    "derived_from_page_source_artifact_ids": list(page_source_artifact_ids),
                    "source_projection_digest": source_projection_digest,
                    "registry_projection_digest": registry_projection_digest,
                    "projector_code_digest": projector_code_digest,
                },
                authority="intake_service",
                occurred_at=occurred_at,
            )
            span = ledger.append(
                RecordKind.EVIDENCE_SPAN,
                {
                    "source_artifact_id": source.record_id,
                    "byte_start": 0,
                    "byte_end": len(entry_bytes),
                    "content_digest": content_digest,
                    "resource": declared_resource,
                    "source_projection_digest": source_projection_digest,
                    "registry_projection_digest": registry_projection_digest,
                    "projector_code_digest": projector_code_digest,
                },
                authority="evidence_service",
                occurred_at=occurred_at,
            )
            results.append(
                ScienceBipmBaseUnitRegistryEntry(
                    name=item["name"],
                    symbol=item["symbol"],
                    quantity=item["quantity"],
                    definition=item["definition"],
                    source_artifact_id=source.record_id,
                    evidence_span_id=span.record_id,
                    object_ref=object_ref,
                    content_digest=content_digest,
                )
            )
        return ScienceBipmBaseUnitRegistryProjection(
            schema=cls.SCHEMA,
            projection_digest=registry_projection_digest,
            source_projection_digest=source_projection_digest,
            entries=tuple(results),
            projector_code_digest=projector_code_digest,
        )


__all__ = [
    "ScienceBipmBaseUnitRegistryEntry",
    "ScienceBipmBaseUnitRegistryError",
    "ScienceBipmBaseUnitRegistryProjection",
    "ScienceBipmBaseUnitRegistryProjector",
]
