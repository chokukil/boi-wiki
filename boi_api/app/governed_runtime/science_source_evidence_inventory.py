"""Deterministic readiness inventory for preserved Science source evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Literal, Sequence

from ..okf import split_frontmatter


class ScienceSourceEvidenceInventoryError(RuntimeError):
    """The preserved source closure is missing, malformed, or inconsistent."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )


ByteStatus = Literal[
    "SOURCE_BYTES_READY",
    "REMOTE_ACQUISITION_REQUIRED",
    "SOURCE_MEMBER_MISSING",
    "SOURCE_DIGEST_MISMATCH",
]


@dataclass(frozen=True)
class ScienceSourceEvidenceCandidate:
    path: str
    science_kind: str
    candidate_digest: str
    byte_status: ByteStatus
    matched_source_refs: tuple[str, ...]
    declared_local_source_refs: tuple[str, ...]
    semantic_span_status: Literal["EXTRACTION_REQUIRED", "REGISTERED_EXECUTOR_REQUIRED"]
    evaluator_ready: bool = False


@dataclass(frozen=True)
class ScienceSourceEvidenceInventory:
    schema: str
    package_digest: str
    snapshot_digest: str
    snapshot_inventory_digest: str
    total_candidates: int
    excluded_candidates: int
    expansion_candidates: int
    candidates: tuple[ScienceSourceEvidenceCandidate, ...]
    inventory_digest: str
    model_invocations: int = 0
    raw_source_model_bytes: int = 0
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


def _parse_inventory(payload: bytes) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ScienceSourceEvidenceInventoryError("snapshot inventory is not UTF-8") from error
    for line in lines:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ScienceSourceEvidenceInventoryError("snapshot inventory row is invalid")
        digest, size, raw_path = parts
        path = raw_path.removeprefix("./")
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or not size.isdigit()
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
            or path in result
        ):
            raise ScienceSourceEvidenceInventoryError("snapshot inventory closure is invalid")
        result[path] = ("sha256:" + digest, int(size))
    return result


class ScienceSourceEvidenceInventoryBuilder:
    """Classify bytes only; never infer semantic spans or grant authority."""

    @classmethod
    def build(
        cls,
        *,
        package_path: Path | str,
        snapshot_path: Path | str,
        snapshot_inventory_path: Path | str,
        excluded_paths: Sequence[str],
    ) -> ScienceSourceEvidenceInventory:
        package = Path(package_path)
        snapshot = Path(snapshot_path)
        inventory_path = Path(snapshot_inventory_path)
        try:
            manifest = json.loads((package / "candidate-manifest.json").read_text("utf-8"))
            inventory_payload = inventory_path.read_bytes()
            inventory = _parse_inventory(inventory_payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ScienceSourceEvidenceInventoryError("Science evidence inputs are invalid") from error
        excluded = tuple(sorted(str(item) for item in excluded_paths))
        if len(excluded) != len(set(excluded)):
            raise ScienceSourceEvidenceInventoryError("excluded path closure is invalid")
        knowledge = [
            item for item in manifest.get("knowledge", [])
            if isinstance(item, dict) and item.get("state") == "candidate"
        ]
        by_path = {str(item.get("path") or ""): item for item in knowledge}
        if len(by_path) != len(knowledge) or not set(excluded) <= set(by_path):
            raise ScienceSourceEvidenceInventoryError("candidate manifest closure is invalid")

        try:
            archive = tarfile.open(snapshot, mode="r:gz")
        except (OSError, tarfile.TarError) as error:
            raise ScienceSourceEvidenceInventoryError("snapshot archive is invalid") from error
        with archive:
            members: dict[str, tarfile.TarInfo] = {}
            for member in archive.getmembers():
                name = member.name.removeprefix("./")
                if member.isfile():
                    if name in members:
                        raise ScienceSourceEvidenceInventoryError("snapshot member is duplicated")
                    members[name] = member
            candidates: list[ScienceSourceEvidenceCandidate] = []
            root = (package / "candidate").resolve()
            for relative, item in sorted(by_path.items()):
                if relative in excluded:
                    continue
                path = (root / relative).resolve()
                try:
                    path.relative_to(root)
                    payload = path.read_bytes()
                    metadata, _body = split_frontmatter(payload.decode("utf-8"))
                except (OSError, UnicodeDecodeError, ValueError) as error:
                    raise ScienceSourceEvidenceInventoryError("candidate bytes are invalid") from error
                candidate_digest = str(item.get("candidate_digest") or "")
                if _digest_bytes(payload) != candidate_digest:
                    raise ScienceSourceEvidenceInventoryError("candidate digest is invalid")
                science = metadata.get("science")
                kind = str(science.get("kind") if isinstance(science, dict) else "")
                sources = metadata.get("sources")
                if kind not in {"unit", "constant", "formula", "dictionary", "derivation"} or not isinstance(sources, list):
                    raise ScienceSourceEvidenceInventoryError("candidate source profile is invalid")
                local_refs: list[str] = []
                matched: list[str] = []
                missing = False
                mismatch = False
                for source in sources:
                    if not isinstance(source, dict) or source.get("type") != "local-snapshot":
                        continue
                    ref = str(source.get("resource") or "").removeprefix("./")
                    local_refs.append(ref)
                    member = members.get(ref)
                    inventory_row = inventory.get(ref)
                    if member is None or inventory_row is None:
                        missing = True
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        missing = True
                        continue
                    source_bytes = handle.read()
                    observed = (_digest_bytes(source_bytes), len(source_bytes))
                    declared = "sha256:" + str(source.get("sha256") or "").removeprefix("sha256:")
                    if observed != inventory_row or observed[0] != declared:
                        mismatch = True
                    else:
                        matched.append(ref)
                if matched:
                    byte_status: ByteStatus = "SOURCE_BYTES_READY"
                elif mismatch:
                    byte_status = "SOURCE_DIGEST_MISMATCH"
                elif missing:
                    byte_status = "SOURCE_MEMBER_MISSING"
                else:
                    byte_status = "REMOTE_ACQUISITION_REQUIRED"
                candidates.append(
                    ScienceSourceEvidenceCandidate(
                        path=relative,
                        science_kind=kind,
                        candidate_digest=candidate_digest,
                        byte_status=byte_status,
                        matched_source_refs=tuple(sorted(matched)),
                        declared_local_source_refs=tuple(sorted(local_refs)),
                        semantic_span_status=(
                            "REGISTERED_EXECUTOR_REQUIRED"
                            if kind == "derivation"
                            else "EXTRACTION_REQUIRED"
                        ),
                    )
                )
        digest_values = {
            "schema": "boi-science-source-evidence-inventory/v1",
            "package_digest": manifest["package_digest"],
            "snapshot_digest": _digest_bytes(snapshot.read_bytes()),
            "snapshot_inventory_digest": _digest_bytes(inventory_payload),
            "total_candidates": len(by_path),
            "excluded_candidates": len(excluded),
            "expansion_candidates": len(candidates),
            "candidates": [asdict(item) for item in candidates],
            "model_invocations": 0,
            "raw_source_model_bytes": 0,
            "qualification_receipt_id": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        return ScienceSourceEvidenceInventory(
            schema=digest_values["schema"],
            package_digest=digest_values["package_digest"],
            snapshot_digest=digest_values["snapshot_digest"],
            snapshot_inventory_digest=digest_values["snapshot_inventory_digest"],
            total_candidates=digest_values["total_candidates"],
            excluded_candidates=digest_values["excluded_candidates"],
            expansion_candidates=digest_values["expansion_candidates"],
            candidates=tuple(candidates),
            inventory_digest=_digest(digest_values),
        )
