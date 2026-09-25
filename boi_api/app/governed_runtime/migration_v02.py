"""Deterministic OKF 0.1 -> 0.2 sibling-tree migration reference engine."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

from .okf_v02 import LEGACY_PROVENANCE_FIELDS, validate_boi_profile_v02


class MigrationError(RuntimeError):
    pass


class CutoverGateFailure(MigrationError):
    pass


class ExactPlanHashMismatch(MigrationError):
    pass


class PointerCASMismatch(MigrationError):
    pass


class MixedCanonicalStorage(MigrationError):
    pass


class ProtectedWriterViolation(MigrationError):
    pass


@dataclass(frozen=True)
class MigrationFile:
    path: str
    original_digest: str
    candidate_digest: str
    legacy_lineage_digest: str | None
    kind: str
    candidate_bytes: bytes

    def manifest_item(self) -> dict[str, Any]:
        item = {
            "path": self.path,
            "original_digest": self.original_digest,
            "candidate_digest": self.candidate_digest,
            "kind": self.kind,
        }
        if self.legacy_lineage_digest:
            item["legacy_lineage_digest"] = self.legacy_lineage_digest
        return item


@dataclass(frozen=True)
class MigrationPlan:
    plan_hash: str
    source_tree_digest: str
    candidate_tree_digest: str
    profile_validation_digest: str
    generated_at: str
    stale_after: str
    files: tuple[MigrationFile, ...]

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "boi-okf-v02-migration-plan/v1",
            "plan_hash": self.plan_hash,
            "source_tree_digest": self.source_tree_digest,
            "candidate_tree_digest": self.candidate_tree_digest,
            "profile_validation_digest": self.profile_validation_digest,
            "generated_at": self.generated_at,
            "stale_after": self.stale_after,
            "files": [item.manifest_item() for item in self.files],
        }

    def safe_preview(self) -> dict[str, Any]:
        markdown = sum(1 for item in self.files if item.kind == "markdown")
        return {
            "schema": "boi-okf-v02-safe-preview/v1",
            "plan_hash": self.plan_hash,
            "source_tree_digest": self.source_tree_digest,
            "candidate_tree_digest": self.candidate_tree_digest,
            "profile_validation_digest": self.profile_validation_digest,
            "counts": {
                "files": len(self.files),
                "markdown": markdown,
                "binary_or_passthrough": len(self.files) - markdown,
                "errors": 0,
            },
        }


@dataclass(frozen=True)
class RevisionVerification:
    errors: tuple[str, ...] = ()
    original_count: int = 0
    candidate_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CorpusQualification:
    plan_hash: str
    status: str
    file_count: int
    migrated_document_count: int
    passthrough_count: int
    original_hash_parity_count: int
    candidate_hash_parity_count: int
    semantic_parity_count: int
    strict_profile_pass_count: int
    unresolved_reference_count: int
    errors: tuple[str, ...]

    def manifest(self) -> dict[str, Any]:
        payload = {
            "schema": "boi-okf-v02-real-corpus-qualification/v1",
            "plan_hash": self.plan_hash,
            "status": self.status,
            "file_count": self.file_count,
            "migrated_document_count": self.migrated_document_count,
            "passthrough_count": self.passthrough_count,
            "original_hash_parity_count": self.original_hash_parity_count,
            "candidate_hash_parity_count": self.candidate_hash_parity_count,
            "semantic_parity_count": self.semantic_parity_count,
            "strict_profile_pass_count": self.strict_profile_pass_count,
            "unresolved_reference_count": self.unresolved_reference_count,
            "errors": list(self.errors),
        }
        payload["qualification_digest"] = _digest(_canonical_json(payload))
        return payload


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _tree_digest(items: list[tuple[str, str]]) -> str:
    return _digest(_canonical_json([{"path": path, "digest": digest} for path, digest in items]))


def _yaml_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _yaml_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_yaml_safe(item) for item in value]
    return value


def _split_markdown(payload: bytes) -> tuple[dict[str, Any], str] | None:
    text = payload.decode("utf-8-sig")
    match = re.match(r"\A---\r?\n(?P<header>.*?)\r?\n---\r?\n(?P<body>.*)\Z", text, flags=re.DOTALL)
    if not match:
        return None
    metadata = yaml.safe_load(match.group("header")) or {}
    if not isinstance(metadata, dict):
        raise CutoverGateFailure("frontmatter must be a mapping")
    return metadata, match.group("body")


def _render_markdown(metadata: Mapping[str, Any], body: str) -> bytes:
    header = yaml.safe_dump(_yaml_safe(dict(metadata)), allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{header}\n---\n{body}".encode("utf-8")


def _status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"stable", "reviewed", "approved", "verified", "memory"}:
        return "stable"
    if normalized in {"deprecated", "superseded", "archived", "deleted", "delete_candidate"}:
        return "deprecated"
    return "draft"


def _source(item: Mapping[str, Any], relation: str) -> dict[str, Any] | None:
    resource = next(
        (str(item.get(key) or "").strip() for key in ("resource", "ref", "url", "uri", "source_id") if str(item.get(key) or "").strip()),
        "",
    )
    if not resource:
        return None
    result = {
        "type": str(item.get("type") or item.get("kind") or "legacy-reference"),
        "resource": resource,
        "relation": relation,
    }
    for key in ("note", "title", "sha256", "locator"):
        if item.get(key) not in (None, ""):
            result[key] = _yaml_safe(item[key])
    return result


def _profile(metadata: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    concept_type = str(metadata.get("type") or "")
    if concept_type == "boi/dictionary-term":
        return "boi/domain@0.1.0", {
            "domain": {
                "kind": "Term",
                "id": str(metadata.get("boi_id") or ""),
                "authority_basis": "steward_review" if metadata.get("review") else "observed",
                "term": deepcopy(metadata.get("term")),
                "definition": deepcopy(metadata.get("definition")),
                "domain_name": deepcopy(metadata.get("domain")),
                "aliases": deepcopy(metadata.get("aliases") or []),
                "related_terms": deepcopy(metadata.get("related_terms") or []),
            }
        }
    if concept_type.startswith("boi/sci-"):
        kind = concept_type.removeprefix("boi/sci-")
        if kind == "concept":
            kind = "dictionary"
        return "boi/sci@0.7.0", {"science": {"kind": kind, "layer": str(metadata.get("layer") or "")}}
    if concept_type.startswith("boi/domain-"):
        return "boi/domain@0.1.0", {"domain": deepcopy(dict(metadata.get("domain") or {}))}
    if concept_type.startswith("boi/data-mapping"):
        return "boi/data-mapping@0.1.0", {"data_mapping": deepcopy(dict(metadata.get("data_mapping") or {}))}
    if concept_type in {"Attested Computation", "boi/query"} or concept_type.startswith("boi/query-"):
        return "boi/query@0.1.0", {"query": deepcopy(dict(metadata.get("query") or {}))}
    governed_content_types = {
        "boi/action",
        "boi/action-skill",
        "boi/action-spec",
        "boi/data-context",
        "boi/event-skill",
        "boi/event-type",
        "boi/harness",
        "boi/manual",
        "boi/reference",
        "boi/report",
        "boi/sop",
        "boi/source-wiki-page",
        "boi/validation-report",
        "boi/workflow-definition",
    }
    if concept_type in governed_content_types:
        return "boi/content@0.1.0", {
            "content": {
                "kind": concept_type.removeprefix("boi/"),
                "legacy_type": concept_type,
            }
        }
    raise CutoverGateFailure(f"no deterministic profile mapping for type: {concept_type}")


def _migrate(metadata: Mapping[str, Any], body: str, generated_at: str, stale_after: str) -> tuple[bytes, str | None]:
    migrated = deepcopy(dict(metadata))
    profile, payload = _profile(metadata)
    migrated["okf_version"] = "0.2"
    migrated["boi_profile_version"] = "0.2"
    migrated["profiles"] = [profile]
    migrated.update(payload)
    migrated["status"] = _status(metadata.get("status") or metadata.get("lifecycle_state"))
    if migrated.get("visibility") == "team" and not migrated.get("team_id"):
        acl_policy = str(migrated.get("acl_policy") or "")
        if acl_policy.startswith("acl:team:") and acl_policy.removeprefix("acl:team:"):
            migrated["team_id"] = acl_policy.removeprefix("acl:team:")
    raw_generated_at = metadata.get("timestamp") or generated_at
    migrated["generated"] = {
        "by": "process:boi-okf-v02-migration",
        "at": _yaml_safe(raw_generated_at),
    }
    migrated["stale_after"] = stale_after

    sources: list[dict[str, Any]] = []
    for family, relation in (("sources", "evidence"), ("source_refs", "evidence"), ("generated_from", "derived-from")):
        values = metadata.get(family)
        if isinstance(values, Mapping):
            values = [values]
        if isinstance(values, list):
            for item in values:
                if isinstance(item, Mapping):
                    normalized = _source(item, str(item.get("relation") or relation))
                    if normalized and normalized not in sources:
                        sources.append(normalized)
    migrated["sources"] = sources
    lineage = {
        key: _yaml_safe(metadata[key])
        for key in ("generated_from",)
        if key in metadata
    }
    lineage_digest = _digest(_canonical_json(lineage)) if lineage else None
    for legacy in ("source_refs", "generated_from", "timestamp", "layer"):
        migrated.pop(legacy, None)
    rendered = _render_markdown(migrated, body)
    validation = validate_boi_profile_v02(migrated)
    if not validation.ok:
        detail = ", ".join(f"{item.code}:{item.path}" for item in validation.errors)
        raise CutoverGateFailure(f"migrated profile failed strict validation: {detail}")
    return rendered, lineage_digest


class OkfV02CorpusMigration:
    SURFACES = ("search", "graph", "mcp", "download")

    def __init__(self, source_root: Path | str, store_root: Path | str):
        self.source_root = Path(source_root)
        self.store_root = Path(store_root)
        self.revisions_root = self.store_root / "revisions"
        self.pointer_path = self.store_root / "canonical-pointer.json"
        self.lock_path = self.store_root / ".cutover.lock"
        self.rollback_root = self.store_root / "rollback-receipts"
        self.revisions_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.store_root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def plan(self, *, generated_at: str, stale_after: str) -> MigrationPlan:
        files: list[MigrationFile] = []
        validation_items: list[dict[str, str]] = []
        for source_path in sorted(self.source_root.rglob("*")):
            if source_path.is_symlink():
                raise CutoverGateFailure(f"symlink is not allowed in migration source: {source_path}")
            if not source_path.is_file():
                continue
            relative = source_path.relative_to(self.source_root).as_posix()
            original = source_path.read_bytes()
            candidate = original
            lineage_digest = None
            kind = "passthrough"
            if source_path.suffix.lower() == ".md":
                parsed = _split_markdown(original)
                if parsed and str(parsed[0].get("okf_version") or "").startswith("0.1"):
                    candidate, lineage_digest = _migrate(parsed[0], parsed[1], generated_at, stale_after)
                    kind = "markdown"
                    validation_items.append({"path": relative, "result": "pass", "digest": _digest(candidate)})
            files.append(
                MigrationFile(
                    path=relative,
                    original_digest=_digest(original),
                    candidate_digest=_digest(candidate),
                    legacy_lineage_digest=lineage_digest,
                    kind=kind,
                    candidate_bytes=candidate,
                )
            )
        source_tree = _tree_digest([(item.path, item.original_digest) for item in files])
        candidate_tree = _tree_digest([(item.path, item.candidate_digest) for item in files])
        validation_digest = _digest(_canonical_json(validation_items))
        plan_base = {
            "schema": "boi-okf-v02-migration-plan/v1",
            "source_tree_digest": source_tree,
            "candidate_tree_digest": candidate_tree,
            "profile_validation_digest": validation_digest,
            "generated_at": generated_at,
            "stale_after": stale_after,
            "files": [item.manifest_item() for item in files],
        }
        plan_hash = _digest(_canonical_json(plan_base))
        return MigrationPlan(
            plan_hash=plan_hash,
            source_tree_digest=source_tree,
            candidate_tree_digest=candidate_tree,
            profile_validation_digest=validation_digest,
            generated_at=generated_at,
            stale_after=stale_after,
            files=tuple(files),
        )

    def revision_path(self, plan: MigrationPlan) -> Path:
        return self.revisions_root / plan.plan_hash.removeprefix("sha256:")

    def verify_source(self, plan: MigrationPlan) -> tuple[str, ...]:
        errors: list[str] = []
        expected = {item.path: item.original_digest for item in plan.files}
        actual_paths: set[str] = set()
        for source_path in sorted(self.source_root.rglob("*")):
            if source_path.is_symlink():
                errors.append(f"symlink:{source_path.relative_to(self.source_root).as_posix()}")
                continue
            if not source_path.is_file():
                continue
            relative = source_path.relative_to(self.source_root).as_posix()
            actual_paths.add(relative)
            if relative not in expected:
                errors.append(f"unexpected:{relative}")
            elif _digest(source_path.read_bytes()) != expected[relative]:
                errors.append(f"hash:{relative}")
        for relative in sorted(set(expected) - actual_paths):
            errors.append(f"missing:{relative}")
        return tuple(errors)

    @staticmethod
    def _assert_plan_fresh(plan: MigrationPlan) -> None:
        try:
            expires_at = datetime.fromisoformat(plan.stale_after.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CutoverGateFailure("migration plan stale_after is invalid") from exc
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise CutoverGateFailure("migration plan stale_after requires an offset")
        if datetime.now(expires_at.tzinfo) > expires_at:
            raise CutoverGateFailure("migration plan is stale")

    def stage(self, plan: MigrationPlan) -> Path:
        target = self.revision_path(plan)
        if target.exists():
            if not self.verify_revision(plan).ok:
                raise CutoverGateFailure("existing immutable revision failed digest verification")
            return target
        temporary = self.revisions_root / f".{target.name}.staging"
        if temporary.exists():
            shutil.rmtree(temporary)
        try:
            for item in plan.files:
                source = self.source_root / item.path
                original_target = temporary / "okf-0.1" / item.path
                candidate_target = temporary / "okf-0.2" / item.path
                original_target.parent.mkdir(parents=True, exist_ok=True)
                candidate_target.parent.mkdir(parents=True, exist_ok=True)
                original = source.read_bytes()
                if _digest(original) != item.original_digest:
                    raise CutoverGateFailure(f"source changed after planning: {item.path}")
                original_target.write_bytes(original)
                candidate_target.write_bytes(item.candidate_bytes)
            (temporary / "migration-manifest.json").write_bytes(_canonical_json(plan.manifest()) + b"\n")
            os.replace(temporary, target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        verification = self.verify_revision(plan)
        if not verification.ok:
            raise CutoverGateFailure("staged revision failed digest verification")
        return target

    def verify_revision(self, plan: MigrationPlan) -> RevisionVerification:
        root = self.revision_path(plan)
        errors: list[str] = []
        originals = 0
        candidates = 0
        expected_paths = {item.path for item in plan.files}
        for item in plan.files:
            original_path = root / "okf-0.1" / item.path
            candidate_path = root / "okf-0.2" / item.path
            if not original_path.exists() or _digest(original_path.read_bytes()) != item.original_digest:
                errors.append(f"original:{item.path}")
            else:
                originals += 1
            if not candidate_path.exists() or _digest(candidate_path.read_bytes()) != item.candidate_digest:
                errors.append(f"candidate:{item.path}")
            else:
                candidates += 1
        manifest_path = root / "migration-manifest.json"
        if not manifest_path.exists() or manifest_path.read_bytes() != _canonical_json(plan.manifest()) + b"\n":
            errors.append("manifest")
        for version in ("okf-0.1", "okf-0.2"):
            version_root = root / version
            actual_paths = {
                path.relative_to(version_root).as_posix()
                for path in version_root.rglob("*")
                if path.is_file()
            } if version_root.exists() else set()
            if actual_paths != expected_paths:
                errors.append(f"inventory:{version}")
        return RevisionVerification(tuple(errors), originals, candidates)

    def qualify_revision(self, plan: MigrationPlan) -> CorpusQualification:
        root = self.revision_path(plan)
        errors: list[str] = []
        original_hash_parity = 0
        candidate_hash_parity = 0
        semantic_parity = 0
        strict_profile_pass = 0
        unresolved_references = 0
        migrated_documents = 0
        passthrough = 0
        stable_fields = (
            "type",
            "title",
            "description",
            "boi_id",
            "visibility",
            "classification",
            "owner",
            "acl_policy",
            "author",
            "aliases",
            "review",
            "review_history",
            "tags",
            "links",
        )

        for item in plan.files:
            original_path = root / "okf-0.1" / item.path
            candidate_path = root / "okf-0.2" / item.path
            original = original_path.read_bytes() if original_path.exists() else b""
            candidate = candidate_path.read_bytes() if candidate_path.exists() else b""
            if _digest(original) == item.original_digest:
                original_hash_parity += 1
            else:
                errors.append(f"ORIGINAL_HASH:{item.path}")
            if _digest(candidate) == item.candidate_digest:
                candidate_hash_parity += 1
            else:
                errors.append(f"CANDIDATE_HASH:{item.path}")

            if item.kind != "markdown":
                passthrough += 1
                if original == candidate:
                    semantic_parity += 1
                else:
                    errors.append(f"PASSTHROUGH_BYTES:{item.path}")
                continue

            migrated_documents += 1
            original_parsed = _split_markdown(original)
            candidate_parsed = _split_markdown(candidate)
            if original_parsed is None or candidate_parsed is None:
                errors.append(f"FRONTMATTER:{item.path}")
                continue
            original_metadata, original_body = original_parsed
            candidate_metadata, candidate_body = candidate_parsed
            semantic_errors: list[str] = []
            if original_body != candidate_body:
                semantic_errors.append("body")
            for field in stable_fields:
                if field in original_metadata and candidate_metadata.get(field) != _yaml_safe(
                    original_metadata[field]
                ):
                    semantic_errors.append(field)
            if candidate_metadata.get("generated", {}).get("at") != _yaml_safe(
                original_metadata.get("timestamp") or plan.generated_at
            ):
                semantic_errors.append("generated.at")
            if candidate_metadata.get("status") != _status(
                original_metadata.get("status") or original_metadata.get("lifecycle_state")
            ):
                semantic_errors.append("status")

            expected_sources: list[dict[str, Any]] = []
            for family, relation in (
                ("sources", "evidence"),
                ("source_refs", "evidence"),
                ("generated_from", "derived-from"),
            ):
                values = original_metadata.get(family)
                if isinstance(values, Mapping):
                    values = [values]
                if isinstance(values, list):
                    for source_item in values:
                        if not isinstance(source_item, Mapping):
                            unresolved_references += 1
                            continue
                        normalized = _source(
                            source_item,
                            str(source_item.get("relation") or relation),
                        )
                        if normalized is None:
                            unresolved_references += 1
                        elif normalized not in expected_sources:
                            expected_sources.append(normalized)
            if candidate_metadata.get("sources") != expected_sources:
                semantic_errors.append("sources")
            if any(field in candidate_metadata for field in LEGACY_PROVENANCE_FIELDS):
                semantic_errors.append("legacy-provenance")
            if semantic_errors:
                errors.append(f"SEMANTIC:{item.path}:{','.join(sorted(set(semantic_errors)))}")
            else:
                semantic_parity += 1

            validation = validate_boi_profile_v02(candidate_metadata)
            if validation.ok:
                strict_profile_pass += 1
            else:
                errors.append(f"PROFILE:{item.path}")

        errors.extend(f"SOURCE:{item}" for item in self.verify_source(plan))
        verification = self.verify_revision(plan)
        errors.extend(f"REVISION:{item}" for item in verification.errors)
        if unresolved_references:
            errors.append(f"UNRESOLVED_REFERENCES:{unresolved_references}")
        unique_errors = tuple(dict.fromkeys(errors))
        return CorpusQualification(
            plan_hash=plan.plan_hash,
            status="passed" if not unique_errors else "failed",
            file_count=len(plan.files),
            migrated_document_count=migrated_documents,
            passthrough_count=passthrough,
            original_hash_parity_count=original_hash_parity,
            candidate_hash_parity_count=candidate_hash_parity,
            semantic_parity_count=semantic_parity,
            strict_profile_pass_count=strict_profile_pass,
            unresolved_reference_count=unresolved_references,
            errors=unique_errors,
        )

    @staticmethod
    def pointer_digest(pointer: Mapping[str, Any]) -> str:
        content = {key: deepcopy(value) for key, value in pointer.items() if key != "pointer_digest"}
        return _digest(_canonical_json(content))

    def _pointer(self, *, version: str, plan: MigrationPlan, code_digest: str, qualification_digest: str | None) -> dict[str, Any]:
        tree_digest = plan.source_tree_digest if version == "0.1" else plan.candidate_tree_digest
        pointer = {
            "schema": "boi-okf-canonical-pointer/v1",
            "version": version,
            "revision": plan.plan_hash,
            "tree_digest": tree_digest,
            "code_digest": code_digest,
            "qualification_receipt_digest": qualification_digest,
            "surfaces": {
                surface: {"version": version, "revision": plan.plan_hash}
                for surface in self.SURFACES
            },
        }
        pointer["pointer_digest"] = self.pointer_digest(pointer)
        return pointer

    def _write_pointer(self, pointer: Mapping[str, Any]) -> None:
        temporary = self.store_root / ".canonical-pointer.json.tmp"
        temporary.write_bytes(_canonical_json(pointer) + b"\n")
        os.replace(temporary, self.pointer_path)

    def canonical_pointer(self) -> dict[str, Any] | None:
        if not self.pointer_path.exists():
            return None
        pointer = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        if pointer.get("pointer_digest") != self.pointer_digest(pointer):
            raise MixedCanonicalStorage("canonical pointer digest is invalid")
        return pointer

    def initialize_legacy_pointer(self, plan: MigrationPlan, *, code_digest: str) -> dict[str, Any]:
        if not self.verify_revision(plan).ok:
            raise CutoverGateFailure("revision must be staged before initializing legacy pointer")
        pointer = self._pointer(version="0.1", plan=plan, code_digest=code_digest, qualification_digest=None)
        with self._locked():
            current = self.canonical_pointer()
            if current is not None and current != pointer:
                raise PointerCASMismatch("canonical pointer already initialized")
            if current is None:
                self._write_pointer(pointer)
        return pointer

    def cutover(
        self,
        plan: MigrationPlan,
        *,
        approved_plan_hash: str,
        qualification_receipt: Mapping[str, Any],
        expected_pointer_digest: str,
    ) -> dict[str, Any]:
        if approved_plan_hash != plan.plan_hash:
            raise ExactPlanHashMismatch("approval is not bound to the exact migration plan")
        self._assert_plan_fresh(plan)
        if self.verify_source(plan):
            raise CutoverGateFailure("source tree changed after planning")
        required = {
            "schema": "boi-okf-v02-cutover-qualification/v1",
            "status": "passed",
            "plan_hash": plan.plan_hash,
            "source_tree_digest": plan.source_tree_digest,
            "candidate_tree_digest": plan.candidate_tree_digest,
            "profile_validation_digest": plan.profile_validation_digest,
        }
        if any(qualification_receipt.get(key) != value for key, value in required.items()):
            raise CutoverGateFailure("qualification receipt does not match the exact staged plan")
        code_digest = qualification_receipt.get("code_digest")
        if not isinstance(code_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", code_digest):
            raise CutoverGateFailure("qualification receipt requires code_digest")
        if not self.verify_revision(plan).ok:
            raise CutoverGateFailure("staged revision failed before cutover")
        receipt_digest = _digest(_canonical_json(dict(qualification_receipt)))
        pointer = self._pointer(
            version="0.2",
            plan=plan,
            code_digest=code_digest,
            qualification_digest=receipt_digest,
        )
        with self._locked():
            current = self.canonical_pointer()
            if current is None or current.get("pointer_digest") != expected_pointer_digest:
                raise PointerCASMismatch("canonical pointer changed after preview")
            self._write_pointer(pointer)
        return pointer

    def assert_single_canonical_version(self) -> str:
        pointer = self.canonical_pointer()
        if pointer is None:
            raise MixedCanonicalStorage("canonical pointer is absent")
        expected = (pointer.get("version"), pointer.get("revision"))
        surfaces = pointer.get("surfaces")
        if not isinstance(surfaces, dict) or set(surfaces) != set(self.SURFACES):
            raise MixedCanonicalStorage("canonical surface set is incomplete")
        if any((surface.get("version"), surface.get("revision")) != expected for surface in surfaces.values()):
            raise MixedCanonicalStorage("mixed canonical versions are forbidden")
        if expected[0] not in {"0.1", "0.2"}:
            raise MixedCanonicalStorage("unsupported canonical version")
        return str(expected[0])

    def read_canonical(self, relative_path: str) -> bytes:
        version = self.assert_single_canonical_version()
        pointer = self.canonical_pointer()
        root = self.revisions_root / pointer["revision"].removeprefix("sha256:") / f"okf-{version}"
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise MigrationError("canonical read path escapes revision") from exc
        return candidate.read_bytes()

    def read_legacy(self, plan: MigrationPlan, relative_path: str) -> bytes:
        root = (self.revision_path(plan) / "okf-0.1").resolve()
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise MigrationError("legacy read path escapes revision") from exc
        return candidate.read_bytes()

    @staticmethod
    def validate_protected_writer(metadata: Mapping[str, Any]) -> None:
        result = validate_boi_profile_v02(metadata)
        if not result.ok:
            detail = ", ".join(f"{issue.code}:{issue.path}" for issue in result.errors)
            raise ProtectedWriterViolation(detail)

    def rollback(
        self,
        prior_pointer: Mapping[str, Any],
        *,
        expected_pointer_digest: str,
        reason: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise CutoverGateFailure("rollback reason is required")
        if prior_pointer.get("pointer_digest") != self.pointer_digest(prior_pointer):
            raise CutoverGateFailure("prior pointer digest is invalid")
        with self._locked():
            current = self.canonical_pointer()
            if current is None or current.get("pointer_digest") != expected_pointer_digest:
                raise PointerCASMismatch("canonical pointer changed before rollback")
            self._write_pointer(prior_pointer)
            receipt = {
                "schema": "boi-okf-v02-rollback-receipt/v1",
                "from_pointer_digest": current["pointer_digest"],
                "to_pointer_digest": prior_pointer["pointer_digest"],
                "reason": reason,
            }
            receipt["receipt_digest"] = _digest(_canonical_json(receipt))
            self.rollback_root.mkdir(parents=True, exist_ok=True)
            path = self.rollback_root / f"{receipt['receipt_digest'].removeprefix('sha256:')}.json"
            if not path.exists():
                path.write_bytes(_canonical_json(receipt) + b"\n")
            return receipt
