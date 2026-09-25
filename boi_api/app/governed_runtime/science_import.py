"""Science snapshot -> inactive, content-addressed candidate package importer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from .okf_v02 import validate_boi_profile_v02


class ScienceCandidateImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScienceCandidatePackage:
    package_digest: str
    path: Path
    candidate_count: int
    attention_count: int


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _yaml_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _yaml_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_yaml_safe(item) for item in value]
    return value


def _split_markdown(payload: bytes) -> tuple[dict[str, Any], str]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ScienceCandidateImportError("science Markdown is not UTF-8") from exc
    match = re.match(r"\A---\r?\n(?P<header>.*?)\r?\n---\r?\n(?P<body>.*)\Z", text, flags=re.DOTALL)
    if not match:
        raise ScienceCandidateImportError("science knowledge document requires frontmatter")
    metadata = yaml.safe_load(match.group("header")) or {}
    if not isinstance(metadata, dict):
        raise ScienceCandidateImportError("science frontmatter must be a mapping")
    return metadata, match.group("body")


def _render_markdown(metadata: Mapping[str, Any], body: str) -> bytes:
    header = yaml.safe_dump(_yaml_safe(dict(metadata)), allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{header}\n---\n{body}".encode("utf-8")


def _science_kind(concept_type: str) -> str:
    if concept_type == "boi/dictionary-term":
        return "dictionary"
    if concept_type.startswith("boi/sci-"):
        return concept_type.removeprefix("boi/sci-")
    return "unknown"


def _source_resource(source: Mapping[str, Any]) -> str:
    if source.get("artifact_id"):
        return f"datalake:{str(source['artifact_id']).strip()}"
    for key in ("resource", "ref", "url", "uri", "source_id"):
        value = str(source.get(key) or "").strip()
        if value:
            return value
    return ""


def _sources(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for family, default_relation in (
        ("sources", "evidence"),
        ("source_refs", "evidence"),
        ("generated_from", "derived-from"),
    ):
        values = metadata.get(family)
        if isinstance(values, Mapping):
            values = [values]
        if not isinstance(values, list):
            continue
        for source in values:
            if not isinstance(source, Mapping):
                continue
            resource = _source_resource(source)
            if not resource:
                continue
            item: dict[str, Any] = {
                "type": str(source.get("type") or source.get("kind") or "legacy-reference"),
                "resource": resource,
                "relation": str(source.get("relation") or default_relation),
            }
            for key in (
                "sha256",
                "note",
                "title",
                "download_url",
                "attachment_role",
                "validation_state",
                "locator",
            ):
                if source.get(key) not in (None, ""):
                    item[key] = _yaml_safe(source[key])
            if item not in normalized:
                normalized.append(item)
    return normalized


def _migrate_science(metadata: Mapping[str, Any], body: str, *, generated_at: str, stale_after: str) -> bytes:
    migrated = deepcopy(dict(metadata))
    kind = _science_kind(str(metadata.get("type") or ""))
    raw_domains = metadata.get("domains") if metadata.get("domains") is not None else metadata.get("domain")
    if isinstance(raw_domains, str):
        science_domains = [raw_domains] if raw_domains.strip() else []
    elif isinstance(raw_domains, list):
        science_domains = [str(item) for item in raw_domains if str(item).strip()]
    else:
        science_domains = []
    migrated["okf_version"] = "0.2"
    migrated["boi_profile_version"] = "0.2"
    migrated["profiles"] = ["boi/sci@0.7.0"]
    migrated["science"] = {"kind": kind, "layer": str(metadata.get("layer") or "")}
    if science_domains:
        migrated["science"]["domains"] = science_domains
    migrated["status"] = "draft"
    migrated["visibility"] = "private" if metadata.get("visibility") == "local-private" else metadata.get("visibility")
    owner = str(metadata.get("owner") or "")
    if migrated.get("visibility") == "private":
        migrated["acl_policy"] = f"acl:private:{owner}"
    elif migrated.get("visibility") == "team":
        migrated["acl_policy"] = f"acl:team:{metadata.get('team_id') or ''}"
    elif migrated.get("visibility") == "public":
        migrated["acl_policy"] = "acl:public"
    migrated["generated"] = {
        "by": "process:boi-science-candidate-import",
        "at": _yaml_safe(metadata.get("timestamp") or generated_at),
    }
    migrated["stale_after"] = stale_after
    migrated["sources"] = _sources(metadata)

    historical_assertions = {
        key: _yaml_safe(metadata[key])
        for key in ("status", "review_status", "check_status", "value_status")
        if metadata.get(key) not in (None, "")
    }
    historical_assertions["not_qualification"] = True
    migrated["historical_assertions"] = historical_assertions
    if isinstance(metadata.get("review"), Mapping):
        migrated["historical_review"] = _yaml_safe(metadata["review"])
    if "variables" in metadata and "symbols" not in metadata:
        migrated["symbols"] = _yaml_safe(metadata["variables"])

    for field in (
        "source_refs",
        "generated_from",
        "timestamp",
        "layer",
        "variables",
        "review_status",
        "check_status",
        "review",
        "domain",
        "domains",
    ):
        migrated.pop(field, None)
    return _render_markdown(migrated, body)


class ScienceCandidatePackageBuilder:
    KNOWLEDGE_PREFIXES = (
        "data/boi/private/0000000/dictionary/",
        "data/boi/private/0000000/science/formulas/",
        "data/boi/private/0000000/science/constants/",
        "data/boi/private/0000000/science/units/",
        "data/boi/private/0000000/science/derivations/",
    )
    HISTORY_PREFIXES = ("cases/sci-verify/", "reports/")

    def __init__(self, source_root: Path | str, output_root: Path | str):
        self.source_root = Path(source_root)
        self.output_root = Path(output_root)

    @staticmethod
    def _is_knowledge(path: str) -> bool:
        return path.endswith(".md") and any(path.startswith(prefix) for prefix in ScienceCandidatePackageBuilder.KNOWLEDGE_PREFIXES)

    @staticmethod
    def _is_history(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in ScienceCandidatePackageBuilder.HISTORY_PREFIXES)

    def _inventory(self) -> list[tuple[str, bytes]]:
        inventory: list[tuple[str, bytes]] = []
        for path in sorted(self.source_root.rglob("*")):
            if path.is_symlink():
                raise ScienceCandidateImportError(f"symlink is forbidden in snapshot input: {path}")
            if path.is_file():
                inventory.append((path.relative_to(self.source_root).as_posix(), path.read_bytes()))
        return inventory

    def build(
        self,
        *,
        snapshot_digest: str,
        generated_at: str,
        stale_after: str,
    ) -> ScienceCandidatePackage:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot_digest):
            raise ScienceCandidateImportError("snapshot_digest must be canonical sha256")
        inventory = self._inventory()
        source_tree_digest = _digest(
            _canonical_json([{"path": path, "digest": _digest(payload)} for path, payload in inventory])
        )
        knowledge: list[dict[str, Any]] = []
        historical: list[dict[str, Any]] = []
        originals: dict[str, bytes] = {}
        candidates: dict[str, bytes] = {}

        for relative, payload in inventory:
            if self._is_knowledge(relative):
                originals[relative] = payload
                error_codes: list[str] = []
                candidate: bytes | None = None
                try:
                    metadata, body = _split_markdown(payload)
                    candidate = _migrate_science(
                        metadata,
                        body,
                        generated_at=generated_at,
                        stale_after=stale_after,
                    )
                    migrated_metadata, _ = _split_markdown(candidate)
                    result = validate_boi_profile_v02(migrated_metadata)
                    error_codes = sorted({issue.code for issue in result.errors})
                except ScienceCandidateImportError:
                    error_codes = ["SCIENCE_IMPORT_PARSE_FAILED"]
                state = "candidate" if candidate is not None and not error_codes else "attention_required"
                if state == "candidate":
                    candidates[relative] = candidate
                knowledge.append(
                    {
                        "path": relative,
                        "original_digest": _digest(payload),
                        "candidate_digest": _digest(candidate) if state == "candidate" and candidate is not None else None,
                        "state": state,
                        "error_codes": error_codes,
                    }
                )
            elif self._is_history(relative):
                historical.append(
                    {
                        "path": relative,
                        "digest": _digest(payload),
                        "qualification_eligible": False,
                    }
                )

        manifest_base = {
            "schema": "boi-science-candidate-package/v1",
            "status": "candidate",
            "snapshot_digest": snapshot_digest,
            "source_tree_digest": source_tree_digest,
            "generated_at": generated_at,
            "stale_after": stale_after,
            "knowledge": knowledge,
            "historical_evidence": historical,
            "historical_evidence_reused_for_qualification": False,
            "qualification_receipt_id": None,
            "release_authority": False,
            "active_release_transition": False,
            "canonical_write": False,
        }
        package_digest = _digest(_canonical_json(manifest_base))
        manifest = {**manifest_base, "package_digest": package_digest}
        target = self.output_root / package_digest.removeprefix("sha256:")
        expected_files: dict[str, bytes] = {"candidate-manifest.json": _canonical_json(manifest) + b"\n"}
        expected_files.update({f"original/{path}": payload for path, payload in originals.items()})
        expected_files.update({f"candidate/{path}": payload for path, payload in candidates.items()})

        if target.exists():
            self._verify_existing(target, expected_files)
        else:
            self.output_root.mkdir(parents=True, exist_ok=True)
            temporary = self.output_root / f".{target.name}.staging"
            if temporary.exists():
                shutil.rmtree(temporary)
            try:
                for relative, payload in expected_files.items():
                    path = temporary / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
                os.replace(temporary, target)
            except Exception:
                if temporary.exists():
                    shutil.rmtree(temporary)
                raise

        candidate_count = sum(1 for item in knowledge if item["state"] == "candidate")
        return ScienceCandidatePackage(
            package_digest=package_digest,
            path=target,
            candidate_count=candidate_count,
            attention_count=len(knowledge) - candidate_count,
        )

    @staticmethod
    def _verify_existing(target: Path, expected_files: Mapping[str, bytes]) -> None:
        actual_files = {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        if set(actual_files) != set(expected_files):
            raise ScienceCandidateImportError("candidate package inventory conflict")
        for relative, expected in expected_files.items():
            if actual_files[relative] != expected:
                raise ScienceCandidateImportError(f"candidate package byte conflict: {relative}")
