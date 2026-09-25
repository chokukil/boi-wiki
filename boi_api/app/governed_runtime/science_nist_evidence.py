"""Deterministic EvidenceSpan extraction from NIST CODATA value pages."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import re
from pathlib import Path

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, canonical_json


class ScienceNISTEvidenceError(RuntimeError):
    """NIST source bytes are missing, changed, or semantically incomplete."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


class _NISTHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._in_title = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag == "title":
            self._in_title = True
        elif tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title":
            self._in_title = False
        elif tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._in_title:
            self.title.append(data)
        if self._cell is not None:
            self._cell.append(data)


def _scientific(value: str) -> str:
    normalized = " ".join(value.replace("×", "x").split())
    if normalized.casefold() == "(exact)":
        return "exact"
    normalized = normalized.replace("...", "")
    exponent_match = re.search(r"\s+x\s*10\s*([+-]?\d+)", normalized, re.IGNORECASE)
    mantissa_text = normalized[: exponent_match.start()] if exponent_match else normalized
    match = re.match(r"([+-]?[0-9][0-9. ]*)", mantissa_text)
    if match is None:
        raise ScienceNISTEvidenceError("NIST numeric field is invalid")
    mantissa = match.group(1).replace(" ", "").rstrip(".")
    exponent = exponent_match.group(1) if exponent_match else None
    return mantissa if exponent is None else f"{mantissa}e{exponent}"


@dataclass(frozen=True)
class ScienceNISTEvidence:
    schema: str
    source_artifact_id: str
    evidence_span_id: str
    resource: str
    byte_start: int
    byte_end: int
    evidence_bytes: bytes
    name: str
    numerical_value: str
    standard_uncertainty: str
    relative_standard_uncertainty: str
    source_status: str
    extraction_digest: str
    extractor_code_digest: str
    model_invocations: int = 0
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceNISTEvidenceExtractor:
    """Extract a bounded raw HTML span; never compare it to a candidate."""

    SCHEMA = "boi-nist-codata-evidence-extraction/v1"

    @classmethod
    def extract(
        cls,
        *,
        source_path: Path | str,
        source_artifact_id: str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceNISTEvidence:
        try:
            source = ledger.read(source_artifact_id)
        except LedgerError as error:
            raise ScienceNISTEvidenceError("SourceArtifact is missing") from error
        if (
            source.kind is not RecordKind.SOURCE_ARTIFACT
            or source.authority != "intake_service"
            or source.payload.get("source_family") != "nist"
        ):
            raise ScienceNISTEvidenceError("SourceArtifact authority is invalid")
        path = Path(source_path)
        if path.is_symlink() or not path.is_file():
            raise ScienceNISTEvidenceError("source bytes are unavailable")
        payload = path.read_bytes()
        if (
            _digest_bytes(payload) != source.payload.get("content_digest")
            or len(payload) != source.payload.get("byte_length")
        ):
            raise ScienceNISTEvidenceError("source bytes are invalid")
        try:
            decoded = payload.decode("utf-8")
        except UnicodeDecodeError:
            decoded = payload.decode("latin-1")
        parser = _NISTHTMLParser()
        parser.feed(decoded)
        title = " ".join("".join(parser.title).split())
        prefix = "CODATA Value:"
        if not title.startswith(prefix):
            raise ScienceNISTEvidenceError("NIST title is invalid")
        name = title.removeprefix(prefix).strip()
        name = re.sub(r"<sup>.*?</sup>", "", name, flags=re.IGNORECASE)
        name = re.sub(r"(?:dagger|†)\s*$", "", name, flags=re.IGNORECASE).strip()
        fields: dict[str, str] = {}
        for row in parser.rows:
            if len(row) < 2:
                continue
            label = " ".join(row[0].split()).casefold()
            if label in {
                "numerical value",
                "standard uncertainty",
                "relative standard uncertainty",
            }:
                fields[label] = row[1]
        required = {
            "numerical value",
            "standard uncertainty",
            "relative standard uncertainty",
        }
        if set(fields) != required:
            raise ScienceNISTEvidenceError("NIST required field is missing")
        plain = " ".join(" ".join(parser.text).split())
        source_match = re.search(r"Source:\s*(20\d{2}\s+CODATA)", plain)
        if source_match is None:
            raise ScienceNISTEvidenceError("NIST source status is missing")
        numerical_value = _scientific(fields["numerical value"])
        standard_uncertainty = _scientific(fields["standard uncertainty"])
        relative_uncertainty = _scientific(fields["relative standard uncertainty"])

        numerical_at = payload.find(b"Numerical value")
        source_at = payload.find(b"Source:", numerical_at)
        name_at = payload.rfind(name.encode("utf-8"), 0, numerical_at)
        if name_at < 0:
            name_at = payload.rfind(name.encode("latin-1", errors="ignore"), 0, numerical_at)
        if numerical_at < 0 or source_at < 0 or name_at < 0:
            raise ScienceNISTEvidenceError("NIST evidence bounds are unavailable")
        byte_start = max(0, name_at - 256)
        byte_end = min(len(payload), source_at + 512)
        evidence_bytes = payload[byte_start:byte_end]
        if len(evidence_bytes) > 11 * 1024:
            raise ScienceNISTEvidenceError("NIST evidence span exceeds bounded input limit")
        resource = str(source.payload.get("resource") or "")
        extractor_code_digest = _digest_bytes(Path(__file__).read_bytes())
        extraction = {
            "schema": cls.SCHEMA,
            "source_artifact_id": source.record_id,
            "source_content_digest": source.payload["content_digest"],
            "resource": resource,
            "byte_start": byte_start,
            "byte_end": byte_end,
            "evidence_content_digest": _digest_bytes(evidence_bytes),
            "name": name,
            "numerical_value": numerical_value,
            "standard_uncertainty": standard_uncertainty,
            "relative_standard_uncertainty": relative_uncertainty,
            "source_status": source_match.group(1),
            "extractor_code_digest": extractor_code_digest,
            "candidate_digest": None,
            "verdict": None,
        }
        extraction_digest = _digest(extraction)
        span = ledger.append(
            RecordKind.EVIDENCE_SPAN,
            {
                "source_artifact_id": source.record_id,
                "resource": resource,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "content_digest": _digest_bytes(evidence_bytes),
                "extraction_digest": extraction_digest,
                "extractor_code_digest": extractor_code_digest,
                "semantic_fields": {
                    "name": name,
                    "numerical_value": numerical_value,
                    "standard_uncertainty": standard_uncertainty,
                    "relative_standard_uncertainty": relative_uncertainty,
                    "source_status": source_match.group(1),
                },
                "candidate_digest": None,
                "verdict": None,
            },
            authority="evidence_service",
            occurred_at=occurred_at,
        )
        return ScienceNISTEvidence(
            schema=cls.SCHEMA,
            source_artifact_id=source.record_id,
            evidence_span_id=span.record_id,
            resource=resource,
            byte_start=byte_start,
            byte_end=byte_end,
            evidence_bytes=evidence_bytes,
            name=name,
            numerical_value=numerical_value,
            standard_uncertainty=standard_uncertainty,
            relative_standard_uncertainty=relative_uncertainty,
            source_status=source_match.group(1),
            extraction_digest=extraction_digest,
            extractor_code_digest=extractor_code_digest,
        )


__all__ = [
    "ScienceNISTEvidence",
    "ScienceNISTEvidenceError",
    "ScienceNISTEvidenceExtractor",
]
