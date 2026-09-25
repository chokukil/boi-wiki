"""Strict OKF 0.2 candidate writer without Release or activation authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .okf_v02 import normalize_okf_v02_metadata, validate_boi_profile_v02


class CanonicalCandidateWriterError(ValueError):
    pass


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class CanonicalCandidateWriteResult:
    document_digest: str
    document_path: Path
    manifest_path: Path
    receipt_digest: str


class CanonicalCandidateWriter:
    """Write immutable strict candidates; never write canonical storage pointers."""

    def __init__(self, candidate_root: Path | str):
        self.candidate_root = Path(candidate_root)

    @staticmethod
    def render(metadata: Mapping[str, Any], body: str) -> bytes:
        normalized = normalize_okf_v02_metadata(metadata)
        validation = validate_boi_profile_v02(normalized)
        if not validation.ok:
            codes = "|".join(sorted({item.code for item in validation.errors}))
            raise CanonicalCandidateWriterError(codes or "BOI_V02_INVALID")
        if not isinstance(body, str):
            raise CanonicalCandidateWriterError("CANONICAL_BODY_MUST_BE_STRING")
        frontmatter = yaml.safe_dump(
            normalized,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{frontmatter}---{body}".encode("utf-8")

    @staticmethod
    def _write_immutable(path: Path, payload: bytes) -> None:
        if path.exists():
            if path.read_bytes() != payload:
                raise CanonicalCandidateWriterError("CANDIDATE_DIGEST_COLLISION")
            return
        path.write_bytes(payload)

    def write(
        self,
        *,
        metadata: Mapping[str, Any],
        body: str,
        authority: str,
    ) -> CanonicalCandidateWriteResult:
        if not authority.strip():
            raise CanonicalCandidateWriterError("CANDIDATE_AUTHORITY_REQUIRED")
        document = self.render(metadata, body)
        document_digest = _digest(document)
        digest = document_digest.removeprefix("sha256:")
        manifest: dict[str, object] = {
            "schema": "boi-canonical-candidate-write/v1",
            "status": "candidate",
            "authority": authority,
            "boi_id": str(metadata.get("boi_id") or ""),
            "document_digest": document_digest,
            "canonical_write": False,
            "release_manifest_created": False,
            "promotion": False,
            "active_pointer_transition": False,
        }
        receipt_digest = _digest(_canonical_json(manifest))
        manifest["receipt_digest"] = receipt_digest
        manifest_payload = _canonical_json(manifest) + b"\n"
        self.candidate_root.mkdir(parents=True, exist_ok=True)
        document_path = self.candidate_root / f"{digest}.md"
        manifest_path = self.candidate_root / f"{digest}.manifest.json"
        self._write_immutable(document_path, document)
        self._write_immutable(manifest_path, manifest_payload)
        return CanonicalCandidateWriteResult(
            document_digest=document_digest,
            document_path=document_path,
            manifest_path=manifest_path,
            receipt_digest=receipt_digest,
        )


__all__ = [
    "CanonicalCandidateWriteResult",
    "CanonicalCandidateWriter",
    "CanonicalCandidateWriterError",
]
