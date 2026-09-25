"""Rebuild bounded Science semantic-Pi requests from immutable evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Mapping

from ..okf import split_frontmatter
from .ledger import GovernedRuntimeLedger, RecordKind, canonical_json
from .local_model_routing import LocalModelPolicy
from .science_semantic_pi import ScienceSemanticPiRequest, ScienceSemanticPiWorker


class ScienceSemanticRequestBuildError(RuntimeError):
    """A preserved candidate/evidence closure cannot be reconstructed safely."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_relative(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ScienceSemanticRequestBuildError(f"{label} is invalid")
    normalized = value.removeprefix("./")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ScienceSemanticRequestBuildError(f"{label} is invalid")
    return normalized


def _inventory(path: Path) -> tuple[dict[str, tuple[str, int]], str]:
    payload = path.read_bytes()
    rows: dict[str, tuple[str, int]] = {}
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ScienceSemanticRequestBuildError("snapshot inventory is invalid") from error
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 3 or not parts[1].isdigit():
            raise ScienceSemanticRequestBuildError("snapshot inventory is invalid")
        digest, raw_size, raw_path = parts
        member = _safe_relative(raw_path, label="snapshot inventory path")
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or member in rows
        ):
            raise ScienceSemanticRequestBuildError("snapshot inventory is invalid")
        rows[member] = ("sha256:" + digest, int(raw_size))
    return rows, _digest_bytes(payload)


def _claim(
    *, metadata: Mapping[str, object], body: str, science_kind: str
) -> str:
    title = metadata.get("title")
    description = metadata.get("description")
    if not isinstance(title, str) or not title.strip() or not isinstance(description, str):
        raise ScienceSemanticRequestBuildError("candidate claim metadata is invalid")
    claim: dict[str, object] = {
        "title": title.strip(),
        "description": description.strip(),
    }
    if science_kind == "dictionary":
        definition = metadata.get("definition")
        aliases = metadata.get("aliases", [])
        if (
            not isinstance(definition, str)
            or not definition.strip()
            or not isinstance(aliases, list)
            or any(not isinstance(alias, str) for alias in aliases)
        ):
            raise ScienceSemanticRequestBuildError("dictionary claim metadata is invalid")
        claim["definition"] = definition.strip()
        claim["aliases"] = aliases
    else:
        equations = [item.strip() for item in re.findall(r"\$\$(.*?)\$\$", body, re.DOTALL)]
        if not equations or not equations[0]:
            raise ScienceSemanticRequestBuildError("formula primary equation is unavailable")
        claim["primary_equation"] = equations[0]
    return canonical_json(claim).decode("utf-8")


@dataclass(frozen=True)
class ScienceSemanticRequestBatch:
    requests: tuple[ScienceSemanticPiRequest, ...]
    manifest: dict[str, object]
    manifest_digest: str


class ScienceSemanticRequestBuilder:
    """Verify exact source/candidate closure and produce no-authority Pi inputs."""

    SCHEMA = "boi-science-semantic-request-manifest/v1"

    @classmethod
    def build(
        cls,
        *,
        candidate_package_root: Path | str,
        evidence_ledger_root: Path | str,
        snapshot_path: Path | str,
        inventory_path: Path | str,
    ) -> ScienceSemanticRequestBatch:
        package = Path(candidate_package_root)
        snapshot = Path(snapshot_path)
        inventory_file = Path(inventory_path)
        try:
            manifest_bytes = (package / "candidate-manifest.json").read_bytes()
            candidate_manifest = json.loads(manifest_bytes)
            entries = candidate_manifest["knowledge"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ScienceSemanticRequestBuildError("candidate manifest is invalid") from error
        if not isinstance(entries, list):
            raise ScienceSemanticRequestBuildError("candidate manifest is invalid")

        candidates: dict[str, str] = {}
        manifest_attention_count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ScienceSemanticRequestBuildError("candidate manifest is invalid")
            digest = entry.get("candidate_digest")
            relative = _safe_relative(entry.get("path"), label="candidate path")
            if digest is None:
                if entry.get("state") != "attention_required" or not entry.get("error_codes"):
                    raise ScienceSemanticRequestBuildError("candidate manifest is invalid")
                manifest_attention_count += 1
                continue
            if (
                not isinstance(digest, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                or digest in candidates
            ):
                raise ScienceSemanticRequestBuildError("candidate manifest is invalid")
            candidates[digest] = relative

        snapshot_digest = _file_digest(snapshot)
        rows, inventory_digest = _inventory(inventory_file)
        declared_snapshot = candidate_manifest.get("snapshot_digest")
        if declared_snapshot is not None and declared_snapshot != snapshot_digest:
            raise ScienceSemanticRequestBuildError("snapshot digest does not match candidate package")

        ledger = GovernedRuntimeLedger(evidence_ledger_root)
        verification = ledger.verify()
        if not verification.ok:
            raise ScienceSemanticRequestBuildError("evidence ledger verification failed")
        record_files = sorted((ledger.records_root / RecordKind.EVIDENCE_SPAN.value).glob("*.json"))
        if not record_files:
            raise ScienceSemanticRequestBuildError("evidence ledger has no EvidenceSpan")

        requests: list[ScienceSemanticPiRequest] = []
        request_refs: list[dict[str, object]] = []
        policy = LocalModelPolicy()
        try:
            with tarfile.open(snapshot, "r:gz") as archive:
                archive_members = {
                    item.name.removeprefix("./"): item
                    for item in archive.getmembers()
                    if item.isfile()
                }
                for record_file in record_files:
                    raw_record = json.loads(record_file.read_text("utf-8"))
                    span = ledger.read(raw_record["record_id"])
                    if span.kind is not RecordKind.EVIDENCE_SPAN:
                        raise ScienceSemanticRequestBuildError("evidence record kind is invalid")
                    payload = span.payload
                    candidate_digest = payload.get("candidate_digest")
                    if candidate_digest not in candidates:
                        raise ScienceSemanticRequestBuildError("evidence candidate is not in manifest")
                    relative = candidates[candidate_digest]
                    candidate_file = package / "candidate" / relative
                    candidate_bytes = candidate_file.read_bytes()
                    if _digest_bytes(candidate_bytes) != candidate_digest:
                        raise ScienceSemanticRequestBuildError("candidate digest mismatch")
                    metadata, body = split_frontmatter(candidate_bytes.decode("utf-8"))

                    if "/dictionary/" in "/" + relative:
                        science_kind = "dictionary"
                    elif "/science/formulas/" in "/" + relative:
                        science_kind = "formula"
                    else:
                        raise ScienceSemanticRequestBuildError("candidate kind is unsupported")

                    source_id = payload.get("source_artifact_id")
                    if not isinstance(source_id, str):
                        raise ScienceSemanticRequestBuildError("source artifact ref is invalid")
                    source = ledger.read(source_id)
                    if source.kind is not RecordKind.SOURCE_ARTIFACT:
                        raise ScienceSemanticRequestBuildError("source artifact kind is invalid")
                    resource = _safe_relative(payload.get("resource"), label="evidence resource")
                    if source.payload.get("resource") != resource:
                        raise ScienceSemanticRequestBuildError("source/evidence resource mismatch")
                    if (
                        source.payload.get("snapshot_digest") != snapshot_digest
                        or source.payload.get("snapshot_inventory_digest") != inventory_digest
                    ):
                        raise ScienceSemanticRequestBuildError("source snapshot closure mismatch")
                    member_info = archive_members.get(resource)
                    if member_info is None or resource not in rows:
                        raise ScienceSemanticRequestBuildError("source member is unavailable")
                    handle = archive.extractfile(member_info)
                    if handle is None:
                        raise ScienceSemanticRequestBuildError("source member is unavailable")
                    source_bytes = handle.read()
                    observed_source = (_digest_bytes(source_bytes), len(source_bytes))
                    if observed_source != rows[resource] or (
                        source.payload.get("content_digest"), source.payload.get("byte_length")
                    ) != observed_source:
                        raise ScienceSemanticRequestBuildError("source member digest mismatch")

                    start = payload.get("byte_start")
                    end = payload.get("byte_end")
                    if (
                        not isinstance(start, int)
                        or isinstance(start, bool)
                        or not isinstance(end, int)
                        or isinstance(end, bool)
                        or start < 0
                        or end <= start
                        or end > len(source_bytes)
                    ):
                        raise ScienceSemanticRequestBuildError("evidence byte range is invalid")
                    evidence = source_bytes[start:end]
                    evidence_digest = _digest_bytes(evidence)
                    if evidence_digest != payload.get("content_digest"):
                        raise ScienceSemanticRequestBuildError("evidence digest mismatch")

                    request = ScienceSemanticPiRequest(
                        candidate_digest=candidate_digest,
                        science_kind=science_kind,
                        claim=_claim(
                            metadata=metadata,
                            body=body,
                            science_kind=science_kind,
                        ),
                        evidence_span_id=span.record_id,
                        evidence_digest=evidence_digest,
                        evidence_bytes=evidence,
                        kb_revision=f"KnowledgeRevision:{candidate_digest}",
                    )
                    serialized_bytes = len(ScienceSemanticPiWorker._serialized(request))
                    if serialized_bytes > policy.max_serialized_input_bytes:
                        raise ScienceSemanticRequestBuildError("semantic request exceeds byte limit")
                    requests.append(request)
                    request_refs.append(
                        {
                            "candidate_digest": candidate_digest,
                            "candidate_path": relative,
                            "claim_digest": _digest(request.claim),
                            "evidence_span_id": span.record_id,
                            "evidence_span_ids": [span.record_id],
                            "evidence_digest": evidence_digest,
                            "serialized_input_bytes": serialized_bytes,
                        }
                    )
        except (OSError, tarfile.TarError, UnicodeDecodeError, KeyError) as error:
            raise ScienceSemanticRequestBuildError("semantic request closure is invalid") from error

        source_evidence_span_count = len(requests)
        deduplicated: dict[
            tuple[str, str, str, str], tuple[ScienceSemanticPiRequest, dict[str, object]]
        ] = {}
        for request, request_ref in zip(requests, request_refs):
            semantic_key = (
                request.candidate_digest,
                request.claim,
                request.evidence_digest,
                request.kb_revision,
            )
            existing = deduplicated.get(semantic_key)
            if existing is None:
                deduplicated[semantic_key] = (request, request_ref)
                continue
            existing_request, existing_ref = existing
            if existing_request.evidence_bytes != request.evidence_bytes:
                raise ScienceSemanticRequestBuildError("semantic deduplication conflict")
            span_ids = existing_ref["evidence_span_ids"]
            if not isinstance(span_ids, list):
                raise ScienceSemanticRequestBuildError("semantic request manifest is invalid")
            span_ids.append(request.evidence_span_id)

        ordered = sorted(deduplicated.values(), key=lambda item: item[0].evidence_span_id)
        requests = [item[0] for item in ordered]
        request_refs = [item[1] for item in ordered]
        manifest = {
            "schema": cls.SCHEMA,
            "candidate_package_digest": candidate_manifest.get("package_digest"),
            "candidate_manifest_digest": _digest_bytes(manifest_bytes),
            "snapshot_digest": snapshot_digest,
            "snapshot_inventory_digest": inventory_digest,
            "evidence_ledger_record_count": verification.record_count,
            "manifest_attention_count": manifest_attention_count,
            "source_evidence_span_count": source_evidence_span_count,
            "deduplicated_equivalent_span_count": source_evidence_span_count - len(requests),
            "request_count": len(requests),
            "requests": request_refs,
            "raw_evidence_embedded": False,
            "model_invocations": 0,
            "verdicts": 0,
            "qualification_receipt_id": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        return ScienceSemanticRequestBatch(tuple(requests), manifest, _digest(manifest))


__all__ = [
    "ScienceSemanticRequestBatch",
    "ScienceSemanticRequestBuildError",
    "ScienceSemanticRequestBuilder",
]
