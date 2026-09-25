"""Deterministic page-text projections for immutable Science PDF sources."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Callable

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, canonical_json


class SciencePdfProjectionError(RuntimeError):
    """A PDF cannot be projected without weakening source or page closure."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


def _full_digest(value: str, *, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise SciencePdfProjectionError(f"{label} digest is invalid")
    return "sha256:" + digest


def _pypdf_pages(path: Path) -> tuple[bytes, ...]:
    try:
        import pypdf

        reader = pypdf.PdfReader(path)
        return tuple((page.extract_text() or "").encode("utf-8") for page in reader.pages)
    except Exception as error:
        raise SciencePdfProjectionError("PDF page extraction failed") from error


@dataclass(frozen=True)
class SciencePdfProjectedPage:
    page_number: int
    source_artifact_id: str
    content_digest: str
    byte_length: int
    object_ref: str
    parser_id: str
    parser_digest: str


@dataclass(frozen=True)
class SciencePdfTextProjection:
    schema: str
    raw_source_artifact_id: str
    source_content_digest: str
    source_object_ref: str
    resource: str
    page_count: int
    pages: tuple[SciencePdfProjectedPage, ...]
    projection_digest: str
    extractor_code_digest: str
    model_invocations: int = 0
    verdict: None = None
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class PdfPhraseEvidenceRequest:
    candidate_digest: str
    exact_phrase: str
    projection_digest: str
    page_source_artifact_ids: tuple[str, ...]
    section_start_phrase: str | None = None
    section_end_phrase: str | None = None


@dataclass(frozen=True)
class SciencePdfPhraseEvidence:
    schema: str
    evidence_span_id: str
    page_source_artifact_id: str
    raw_source_artifact_id: str
    candidate_digest: str
    projection_digest: str
    page_number: int
    exact_phrase_digest: str
    exact_match_count: int
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


class SciencePdfTextProjectionService:
    """Persist raw PDF and deterministic page text as linked SourceArtifacts."""

    SCHEMA = "boi-science-pdf-text-projection/v1"
    MAX_PAGE_BYTES = 1024 * 1024

    def __init__(
        self,
        *,
        artifact_root: Path | str,
        ledger: GovernedRuntimeLedger,
        page_extractor: Callable[[Path], tuple[bytes, ...]] | None = None,
        parser_id: str | None = None,
        parser_digest: str | None = None,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.ledger = ledger
        self.page_extractor = page_extractor or _pypdf_pages
        if parser_id is None:
            try:
                import pypdf
            except ImportError as error:
                raise SciencePdfProjectionError("pypdf parser is unavailable") from error
            parser_id = f"pypdf/{pypdf.__version__}"
        self.parser_id = parser_id
        self.parser_digest = _full_digest(
            parser_digest
            or _digest(
                {
                    "parser_id": self.parser_id,
                    "adapter_code_digest": _digest_bytes(Path(__file__).read_bytes()),
                }
            ),
            label="parser",
        )

    def _store(self, payload: bytes) -> str:
        digest = _digest_bytes(payload).removeprefix("sha256:")
        ref = Path("objects") / "sha256" / digest
        path = self.artifact_root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != payload:
                raise SciencePdfProjectionError("content-addressed object conflict")
            return ref.as_posix()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return ref.as_posix()

    def project(
        self,
        *,
        source_path: Path | str,
        resource: str,
        expected_source_digest: str,
        occurred_at: str,
    ) -> SciencePdfTextProjection:
        path = Path(source_path)
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise SciencePdfProjectionError("PDF source is unavailable") from error
        expected = _full_digest(expected_source_digest, label="source")
        if _digest_bytes(raw) != expected:
            raise SciencePdfProjectionError("PDF source digest is invalid")
        if not raw.startswith(b"%PDF-"):
            raise SciencePdfProjectionError("source is not a PDF")
        if not resource:
            raise SciencePdfProjectionError("source resource is empty")
        try:
            pages = tuple(self.page_extractor(path))
        except SciencePdfProjectionError:
            raise
        except Exception as error:
            raise SciencePdfProjectionError("PDF page extraction failed") from error
        if (
            not pages
            or any(
                not isinstance(page, bytes) or len(page) > self.MAX_PAGE_BYTES
                for page in pages
            )
            or not any(pages)
        ):
            raise SciencePdfProjectionError("PDF page projection is empty or oversized")

        extractor_code_digest = _digest_bytes(Path(__file__).read_bytes())
        page_descriptors = [
            {
                "page_number": number,
                "content_digest": _digest_bytes(payload),
                "byte_length": len(payload),
            }
            for number, payload in enumerate(pages, start=1)
        ]
        projection_digest = _digest(
            {
                "schema": self.SCHEMA,
                "source_content_digest": expected,
                "resource": resource,
                "parser_id": self.parser_id,
                "parser_digest": self.parser_digest,
                "pages": page_descriptors,
                "extractor_code_digest": extractor_code_digest,
            }
        )

        raw_ref = self._store(raw)
        page_refs = [self._store(payload) for payload in pages]
        raw_record = self.ledger.append(
            RecordKind.SOURCE_ARTIFACT,
            {
                "content_digest": expected,
                "byte_length": len(raw),
                "resource": resource,
                "source_family": "pdf",
                "media_type": "application/pdf",
                "object_ref": raw_ref,
            },
            authority="intake_service",
            occurred_at=occurred_at,
        )
        projected: list[SciencePdfProjectedPage] = []
        for descriptor, object_ref in zip(page_descriptors, page_refs, strict=True):
            record = self.ledger.append(
                RecordKind.SOURCE_ARTIFACT,
                {
                    **descriptor,
                    "resource": resource,
                    "source_family": "pdf-page-text-projection",
                    "media_type": "text/plain; charset=utf-8",
                    "object_ref": object_ref,
                    "derived_from_source_artifact_id": raw_record.record_id,
                    "source_content_digest": expected,
                    "projection_digest": projection_digest,
                    "parser_id": self.parser_id,
                    "parser_digest": self.parser_digest,
                    "extractor_code_digest": extractor_code_digest,
                },
                authority="intake_service",
                occurred_at=occurred_at,
            )
            projected.append(
                SciencePdfProjectedPage(
                    page_number=int(descriptor["page_number"]),
                    source_artifact_id=record.record_id,
                    content_digest=str(descriptor["content_digest"]),
                    byte_length=int(descriptor["byte_length"]),
                    object_ref=object_ref,
                    parser_id=self.parser_id,
                    parser_digest=self.parser_digest,
                )
            )
        return SciencePdfTextProjection(
            schema=self.SCHEMA,
            raw_source_artifact_id=raw_record.record_id,
            source_content_digest=expected,
            source_object_ref=raw_ref,
            resource=resource,
            page_count=len(projected),
            pages=tuple(projected),
            projection_digest=projection_digest,
            extractor_code_digest=extractor_code_digest,
        )


class SciencePdfPhraseEvidenceExtractor:
    """Bind one exact phrase occurrence to one verified projected PDF page."""

    SCHEMA = "boi-science-pdf-exact-phrase-evidence/v1"
    SECTION_SCHEMA = "boi-science-pdf-section-phrase-evidence/v2"
    CONTEXT_BYTES = 4096

    @classmethod
    def extract(
        cls,
        *,
        artifact_root: Path | str,
        ledger: GovernedRuntimeLedger,
        request: PdfPhraseEvidenceRequest,
        occurred_at: str,
    ) -> SciencePdfPhraseEvidence:
        candidate_digest = _full_digest(request.candidate_digest, label="candidate")
        projection_digest = _full_digest(request.projection_digest, label="projection")
        try:
            phrase = request.exact_phrase.encode("utf-8")
        except UnicodeEncodeError as error:
            raise SciencePdfProjectionError("exact phrase is invalid") from error
        if (
            len(phrase) < 4
            or len(phrase) > 512
            or any(byte < 32 for byte in phrase)
            or not request.page_source_artifact_ids
            or len(set(request.page_source_artifact_ids))
            != len(request.page_source_artifact_ids)
        ):
            raise SciencePdfProjectionError("exact phrase or page closure is invalid")

        root = Path(artifact_root)
        pages = []
        closure: tuple[str, str, str] | None = None
        try:
            for page_id in request.page_source_artifact_ids:
                record = ledger.read(page_id)
                payload = record.payload
                if (
                    record.kind is not RecordKind.SOURCE_ARTIFACT
                    or payload.get("source_family") != "pdf-page-text-projection"
                    or payload.get("projection_digest") != projection_digest
                ):
                    raise SciencePdfProjectionError("PDF page closure is invalid")
                object_ref = Path(str(payload.get("object_ref") or ""))
                if object_ref.is_absolute() or ".." in object_ref.parts:
                    raise SciencePdfProjectionError("PDF page object ref is invalid")
                page_bytes = (root / object_ref).read_bytes()
                if (
                    _digest_bytes(page_bytes) != payload.get("content_digest")
                    or len(page_bytes) != payload.get("byte_length")
                ):
                    raise SciencePdfProjectionError("PDF page bytes are invalid")
                page_closure = (
                    str(payload.get("derived_from_source_artifact_id") or ""),
                    str(payload.get("source_content_digest") or ""),
                    str(payload.get("parser_digest") or ""),
                )
                if not all(page_closure) or (closure is not None and closure != page_closure):
                    raise SciencePdfProjectionError("PDF page closure is inconsistent")
                closure = page_closure
                pages.append((record, page_bytes))
        except (LedgerError, OSError) as error:
            raise SciencePdfProjectionError("PDF page bytes are unavailable") from error

        section: dict[str, object] = {}
        if (request.section_start_phrase is None) != (request.section_end_phrase is None):
            raise SciencePdfProjectionError("PDF section closure is incomplete")
        if request.section_start_phrase is not None:
            try:
                section_start = request.section_start_phrase.encode("utf-8")
                section_end = request.section_end_phrase.encode("utf-8")  # type: ignore[union-attr]
            except UnicodeEncodeError as error:
                raise SciencePdfProjectionError("PDF section phrase is invalid") from error
            if any(
                len(value) < 4
                or len(value) > 512
                or any(byte < 32 for byte in value)
                for value in (section_start, section_end)
            ):
                raise SciencePdfProjectionError("PDF section phrase is invalid")
            start_hits = [
                index
                for index, (_record, page_bytes) in enumerate(pages)
                for _occurrence in range(page_bytes.count(section_start))
            ]
            end_hits = [
                index
                for index, (_record, page_bytes) in enumerate(pages)
                for _occurrence in range(page_bytes.count(section_end))
            ]
            if (
                len(start_hits) != 1
                or len(end_hits) != 1
                or start_hits[0] >= end_hits[0]
            ):
                raise SciencePdfProjectionError("PDF section boundary is missing or ambiguous")
            start_index, end_index = start_hits[0], end_hits[0]
            section = {
                "section_start_phrase_digest": _digest_bytes(section_start),
                "section_end_phrase_digest": _digest_bytes(section_end),
                "section_page_start": int(pages[start_index][0].payload["page_number"]),
                "section_page_end_exclusive": int(
                    pages[end_index][0].payload["page_number"]
                ),
            }
            pages = pages[start_index:end_index]

        matches = []
        for record, page_bytes in pages:
            offset = 0
            while True:
                position = page_bytes.find(phrase, offset)
                if position < 0:
                    break
                matches.append((record, page_bytes, position))
                offset = position + len(phrase)
        if not matches:
            raise SciencePdfProjectionError("exact PDF phrase is missing")
        if len(matches) != 1:
            raise SciencePdfProjectionError("exact PDF phrase is ambiguous")
        record, page_bytes, position = matches[0]
        byte_start = max(0, position - cls.CONTEXT_BYTES)
        byte_end = min(len(page_bytes), position + len(phrase) + cls.CONTEXT_BYTES)
        evidence_bytes = page_bytes[byte_start:byte_end]
        extractor_code_digest = _digest_bytes(Path(__file__).read_bytes())
        extraction = {
            "schema": cls.SECTION_SCHEMA if section else cls.SCHEMA,
            "page_source_artifact_id": record.record_id,
            "raw_source_artifact_id": closure[0],
            "candidate_digest": candidate_digest,
            "projection_digest": projection_digest,
            "page_number": record.payload["page_number"],
            "exact_phrase_digest": _digest_bytes(phrase),
            "exact_match_count": 1,
            "byte_start": byte_start,
            "byte_end": byte_end,
            "evidence_content_digest": _digest_bytes(evidence_bytes),
            "extractor_code_digest": extractor_code_digest,
            "verdict": None,
            **section,
        }
        extraction_digest = _digest(extraction)
        span = ledger.append(
            RecordKind.EVIDENCE_SPAN,
            {
                **extraction,
                "content_digest": extraction["evidence_content_digest"],
                "extraction_digest": extraction_digest,
                "resource": record.payload.get("resource"),
            },
            authority="evidence_service",
            occurred_at=occurred_at,
        )
        return SciencePdfPhraseEvidence(
            schema=cls.SECTION_SCHEMA if section else cls.SCHEMA,
            evidence_span_id=span.record_id,
            page_source_artifact_id=record.record_id,
            raw_source_artifact_id=closure[0],
            candidate_digest=candidate_digest,
            projection_digest=projection_digest,
            page_number=int(record.payload["page_number"]),
            exact_phrase_digest=_digest_bytes(phrase),
            exact_match_count=1,
            byte_start=byte_start,
            byte_end=byte_end,
            evidence_bytes=evidence_bytes,
            extraction_digest=extraction_digest,
            extractor_code_digest=extractor_code_digest,
        )


__all__ = [
    "PdfPhraseEvidenceRequest",
    "SciencePdfPhraseEvidence",
    "SciencePdfPhraseEvidenceExtractor",
    "SciencePdfProjectedPage",
    "SciencePdfProjectionError",
    "SciencePdfTextProjection",
    "SciencePdfTextProjectionService",
]
