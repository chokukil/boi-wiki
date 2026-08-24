"""Indexed, immutable resolution of reviewed Science documents."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from boi_api.app.okf import (
    split_frontmatter,
    validate_boi_profile_metadata,
    validate_boi_profile_path_acl,
    validate_okf_core_metadata,
)
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.models import ReleaseSelection, ResolvedComponent, ResolvedRelease
from boi_api.app.science.profile import SCIENCE_TYPE_REQUIREMENTS, validate_sci_profile_metadata


ObjectKind = Literal[
    "source", "evidence", "knowledge", "rule", "ontology_binding", "qualification_matrix", "pack", "release"
]

_TYPE_TO_KIND: dict[str, ObjectKind] = {
    "boi/science-source": "source",
    "boi/science-evidence": "evidence",
    "boi/science-knowledge": "knowledge",
    "boi/science-rule": "rule",
    "boi/science-ontology-binding": "ontology_binding",
    "boi/science-qualification-matrix": "qualification_matrix",
    "boi/science-pack": "pack",
    "boi/science-release": "release",
}

_KIND_ID_FIELD: dict[ObjectKind, str] = {
    "source": "source_id",
    "evidence": "evidence_id",
    "knowledge": "knowledge_id",
    "rule": "rule_id",
    "ontology_binding": "binding_id",
    "qualification_matrix": "matrix_id",
    "pack": "pack_id",
    "release": "release_id",
}


class ScienceObject(BaseModel):
    """A frozen stored Science object with its profile fields available as attributes."""

    model_config = ConfigDict(extra="allow", frozen=True)

    kind: ObjectKind
    object_id: str
    digest: str
    release_manifest_digest: str | None = None
    body: str
    path: Path


class QualificationCase(BaseModel):
    """A frozen qualification case embedded in a Qualification Matrix."""

    model_config = ConfigDict(extra="allow", frozen=True)

    case_id: str = Field(min_length=1)


def _normalized(value: Any) -> Any:
    """Convert YAML values to canonical JSON-compatible values without filesystem state."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if isinstance(value, tuple):
        return [_normalized(item) for item in value]
    return value


def _release_manifest_digest(metadata: dict[str, Any], body: str) -> str:
    """Hash a Release manifest and body without its self-declared content hash."""
    manifest = deepcopy(metadata)
    science = manifest.get("science")
    if not isinstance(science, dict):
        raise ScienceCatalogError("science release manifest has invalid science metadata")
    science.pop("content_hash", None)
    return sha256_digest({"metadata": manifest, "body": body})


class ScienceCatalog:
    """Load Science documents only from ``<boi_root>/public/science`` and resolve IDs."""

    def __init__(self, boi_root: Path):
        self.boi_root = Path(boi_root)
        self.science_root = self.boi_root / "public" / "science"
        self._objects = self._load_objects()
        self._validate_references()
        self._cases = self._load_cases()

    def _load_objects(self) -> dict[ObjectKind, dict[str, ScienceObject]]:
        objects: dict[ObjectKind, dict[str, ScienceObject]] = {kind: {} for kind in _KIND_ID_FIELD}
        indexed_kinds: dict[str, ObjectKind] = {}
        if not self.science_root.exists():
            return objects
        if not self.science_root.is_dir():
            raise ScienceCatalogError(f"science root is not a directory: {self.science_root}")

        root = self.science_root.resolve()
        for path in sorted(self.science_root.rglob("*.md"), key=lambda item: item.as_posix()):
            resolved_path = path.resolve()
            if not resolved_path.is_relative_to(root):
                raise ScienceCatalogError(f"science document escapes science root: {path}")
            try:
                metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise ScienceCatalogError(f"cannot read science document: {path}") from exc
            if not isinstance(metadata, dict) or metadata.get("type") not in SCIENCE_TYPE_REQUIREMENTS:
                continue

            errors = (
                validate_okf_core_metadata(metadata)
                + validate_boi_profile_metadata(metadata)
                + validate_boi_profile_path_acl(metadata, path, self.boi_root)
                + validate_sci_profile_metadata(metadata)
            )
            if errors:
                raise ScienceCatalogError(f"invalid science document {path}: {'; '.join(errors)}")
            science = metadata.get("science")
            if not isinstance(science, Mapping):  # validated above; retain a safe boundary here.
                raise ScienceCatalogError(f"invalid science document: {path}")
            kind = _TYPE_TO_KIND[str(metadata["type"])]
            id_field = _KIND_ID_FIELD[kind]
            object_id = science.get(id_field)
            if not isinstance(object_id, str) or not object_id.strip():
                raise ScienceCatalogError(f"invalid science {kind} ID: {path}")
            if object_id in objects[kind]:
                raise ScienceCatalogError(f"duplicate science {kind} ID: {object_id}")
            if object_id in indexed_kinds:
                raise ScienceCatalogError(f"duplicate science ID: {object_id}")

            normalized_metadata = _normalized(metadata)
            normalized_science = _normalized(science)
            normalized_body = body.replace("\r\n", "\n")
            digest = sha256_digest({"metadata": normalized_metadata, "body": normalized_body})
            release_manifest_digest = (
                _release_manifest_digest(normalized_metadata, normalized_body) if kind == "release" else None
            )
            objects[kind][object_id] = ScienceObject(
                kind=kind,
                object_id=object_id,
                digest=digest,
                release_manifest_digest=release_manifest_digest,
                body=normalized_body,
                path=resolved_path,
                **deepcopy(normalized_science),
            )
            indexed_kinds[object_id] = kind
        return objects

    def _load_cases(self) -> dict[str, QualificationCase]:
        cases: dict[str, QualificationCase] = {}
        for matrix in self._objects["qualification_matrix"].values():
            raw_cases = getattr(matrix, "cases", None)
            if not isinstance(raw_cases, list):
                raise ScienceCatalogError(f"qualification matrix cases must be a list: {matrix.object_id}")
            for raw_case in raw_cases:
                if not isinstance(raw_case, Mapping):
                    raise ScienceCatalogError(f"qualification case must be an object: {matrix.object_id}")
                case_id = raw_case.get("case_id")
                if not isinstance(case_id, str) or not case_id.strip():
                    raise ScienceCatalogError(f"qualification case has invalid case_id: {matrix.object_id}")
                if case_id in cases:
                    raise ScienceCatalogError(f"duplicate qualification case ID: {case_id}")
                cases[case_id] = QualificationCase(**deepcopy(_normalized(raw_case)))
        return cases

    def _validate_references(self) -> None:
        for evidence in self._objects["evidence"].values():
            self._require("source", self._string_field(evidence, "source_id"))
        for knowledge in self._objects["knowledge"].values():
            self._require("pack", self._string_field(knowledge, "pack_id"))
            self._require_many("evidence", self._references(knowledge, "evidence_refs"))
        for rule in self._objects["rule"].values():
            self._require("pack", self._string_field(rule, "pack_id"))
            self._require_many("knowledge", self._references(rule, "knowledge_refs"))
            self._require_many("evidence", self._references(rule, "evidence_refs"))
        for pack in self._objects["pack"].values():
            self._require_many("pack", self._references(pack, "dependencies"))
            self._require_many("knowledge", self._references(pack, "knowledge_refs"))
            self._require_many("rule", self._references(pack, "rule_refs"))
            self._require_many("qualification_matrix", self._references(pack, "qualification_refs"))
        for matrix in self._objects["qualification_matrix"].values():
            self._require("rule", self._string_field(matrix, "rule_id"))
            self._require_many("release", self._references(matrix, "release_refs"))
        for release in self._objects["release"].values():
            for ref in self._release_component_refs(release):
                component = self._find_component(ref)
                if component.kind == "release":
                    raise ScienceCatalogError(f"release cannot be its own component: {ref}")

    @staticmethod
    def _string_field(obj: ScienceObject, name: str) -> str:
        value = getattr(obj, name, None)
        if not isinstance(value, str) or not value.strip():
            raise ScienceCatalogError(f"science {obj.kind} has invalid {name}: {obj.object_id}")
        return value

    def _references(self, obj: ScienceObject, field_name: str) -> tuple[str, ...]:
        value = getattr(obj, field_name, None)
        if not isinstance(value, list):
            raise ScienceCatalogError(f"science {obj.kind} has invalid {field_name}: {obj.object_id}")
        refs: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                refs.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("ref"), str) and item["ref"].strip():
                refs.append(item["ref"])
            else:
                raise ScienceCatalogError(f"science {obj.kind} has invalid {field_name}: {obj.object_id}")
        return tuple(refs)

    def _require_many(self, kind: ObjectKind, refs: Iterable[str]) -> None:
        for ref in refs:
            self._require(kind, ref)

    def _require(self, kind: ObjectKind, object_id: str) -> ScienceObject:
        object_ = self._objects[kind].get(object_id)
        if object_ is None:
            raise ScienceCatalogError(f"unknown science {kind}: {object_id}")
        return object_

    def _find_component(self, ref: str) -> ScienceObject:
        for kind in ("source", "evidence", "knowledge", "rule", "ontology_binding", "qualification_matrix", "pack"):
            object_ = self._objects[kind].get(ref)
            if object_ is not None:
                return object_
        raise ScienceCatalogError(f"unknown science component: {ref}")

    def _release_component_refs(self, release: ScienceObject) -> tuple[str, ...]:
        value = getattr(release, "components", None)
        if not isinstance(value, list):
            raise ScienceCatalogError(f"science release has invalid components: {release.object_id}")
        refs: list[str] = []
        for component in value:
            if isinstance(component, str) and component.strip():
                refs.append(component)
                continue
            if isinstance(component, Mapping) and isinstance(component.get("ref"), str) and component["ref"].strip():
                refs.append(component["ref"])
                continue
            raise ScienceCatalogError(f"science release has invalid component reference: {release.object_id}")
        if len(set(refs)) != len(refs):
            raise ScienceCatalogError(f"science release has duplicate component reference: {release.object_id}")
        return tuple(sorted(refs))

    def _declared_component_digests(self, release: ScienceObject) -> Mapping[str, str]:
        value = getattr(release, "component_digests", None)
        if not isinstance(value, Mapping):
            raise ScienceCatalogError(f"science release has invalid component_digests: {release.object_id}")
        if any(not isinstance(ref, str) or not isinstance(digest, str) or not digest for ref, digest in value.items()):
            raise ScienceCatalogError(f"science release has invalid component_digests: {release.object_id}")
        return value

    def resolve_release(self, release_id: str) -> ResolvedRelease:
        release = self._require("release", release_id)
        declared_content_hash = self._string_field(release, "content_hash")
        if declared_content_hash != release.release_manifest_digest:
            raise ScienceCatalogError(f"release content hash mismatch: {release_id}")
        declared_digests = self._declared_component_digests(release)
        refs = self._release_component_refs(release)
        if set(declared_digests) != set(refs):
            raise ScienceCatalogError(f"component digest manifest does not match components: {release_id}")
        components: list[ResolvedComponent] = []
        for ref in refs:
            component = self._find_component(ref)
            declared_digest = declared_digests[ref]
            if declared_digest != component.digest:
                raise ScienceCatalogError(f"component digest mismatch: {ref}")
            components.append(
                ResolvedComponent(
                    ref=ref,
                    kind=component.kind,
                    declared_digest=declared_digest,
                    actual_digest=component.digest,
                )
            )
        schema_version = self._string_field(release, "schema_version")
        if schema_version != "sci-profile/0.1":
            raise ScienceCatalogError(f"unsupported science release schema: {schema_version}")
        status = self._string_field(release, "status")
        if status not in {"release_candidate", "active", "superseded", "withdrawn"}:
            raise ScienceCatalogError(f"invalid science release status: {status}")
        known_limitations = getattr(release, "known_limitations", None)
        if not isinstance(known_limitations, list) or not all(isinstance(item, str) for item in known_limitations):
            raise ScienceCatalogError(f"science release has invalid known_limitations: {release_id}")
        return ResolvedRelease(
            release_id=release_id,
            schema_version=schema_version,
            content_hash=declared_content_hash,
            status=status,
            components=tuple(components),
            component_digests={ref: declared_digests[ref] for ref in refs},
            known_limitations=list(known_limitations),
        )

    def resolve_release_set(self, selection: ReleaseSelection) -> tuple[ResolvedRelease, ...]:
        release_ids = (selection.foundation, *sorted(selection.domains), *sorted(selection.applications))
        if len(set(release_ids)) != len(release_ids):
            raise ScienceOperationalError("Science release selection contains duplicate release IDs")
        return tuple(self.resolve_release(release_id) for release_id in release_ids)

    def active_release(self) -> ResolvedRelease:
        candidates = [
            release
            for release in self._objects["release"].values()
            if getattr(release, "active", False) is True or getattr(release, "status", None) == "active"
        ]
        if len(candidates) != 1:
            raise ScienceOperationalError("exactly one active Science release is required")
        selected = candidates[0]
        selected_status = getattr(selected, "status", None)
        if selected_status == "active":
            return self.resolve_release(selected.object_id)
        if selected_status != "withdrawn":
            raise ScienceOperationalError("active pointer has invalid status")
        safe_id = getattr(selected, "last_safe_release_id", None)
        if not isinstance(safe_id, str) or not safe_id.strip():
            raise ScienceOperationalError("withdrawn active release has no last_safe_release_id")
        try:
            safe = self._require("release", safe_id)
        except ScienceCatalogError as exc:
            raise ScienceOperationalError(f"last safe release is unavailable: {safe_id}") from exc
        if getattr(safe, "status", None) == "withdrawn":
            raise ScienceOperationalError("last safe release is withdrawn")
        if getattr(safe, "status", None) == "release_candidate":
            raise ScienceOperationalError("last safe release is not an operational release")
        return self.resolve_release(safe_id)

    def source(self, source_id: str) -> ScienceObject:
        return self._copy_object(self._require("source", source_id))

    def evidence(self, evidence_id: str) -> ScienceObject:
        return self._copy_object(self._require("evidence", evidence_id))

    def knowledge(self, knowledge_id: str) -> ScienceObject:
        return self._copy_object(self._require("knowledge", knowledge_id))

    def rule(self, rule_id: str) -> ScienceObject:
        return self._copy_object(self._require("rule", rule_id))

    def ontology_binding(self, binding_id: str) -> ScienceObject:
        return self._copy_object(self._require("ontology_binding", binding_id))

    def pack(self, pack_id: str) -> ScienceObject:
        return self._copy_object(self._require("pack", pack_id))

    def pack_by_name(self, name: str) -> ScienceObject:
        matches = []
        for pack in self._objects["pack"].values():
            pack_name = getattr(pack, "name", None)
            if not isinstance(pack_name, str) or not pack_name:
                pack_name = pack.pack_id.removeprefix("sci-pack:").split("/", 1)[0]
            if pack_name == name:
                matches.append(pack)
        if len(matches) != 1:
            raise ScienceCatalogError(f"unknown science pack name: {name}")
        return self._copy_object(matches[0])

    def qualification_matrix(self, matrix_id: str) -> ScienceObject:
        return self._copy_object(self._require("qualification_matrix", matrix_id))

    def qualification_cases(self, rule_id: str) -> tuple[QualificationCase, ...]:
        self._require("rule", rule_id)
        case_ids: list[str] = []
        for matrix in self._objects["qualification_matrix"].values():
            if getattr(matrix, "rule_id", None) == rule_id:
                case_ids.extend(case["case_id"] for case in getattr(matrix, "cases"))
        return tuple(self._copy_case(self._cases[case_id]) for case_id in sorted(case_ids))

    def qualification_cases_for_pack(self, pack_id: str) -> tuple[QualificationCase, ...]:
        pack = self.pack(pack_id)
        case_ids: list[str] = []
        for matrix_id in self._references(pack, "qualification_refs"):
            matrix = self.qualification_matrix(matrix_id)
            case_ids.extend(case["case_id"] for case in getattr(matrix, "cases"))
        return tuple(self._copy_case(self._cases[case_id]) for case_id in sorted(case_ids))

    def claim_fixture(self, case_id: str) -> dict[str, Any]:
        case = self._cases.get(case_id)
        if case is None:
            raise ScienceCatalogError(f"unknown qualification case: {case_id}")
        claim_packet = getattr(case, "claim_packet", None)
        if not isinstance(claim_packet, Mapping):
            raise ScienceCatalogError(f"qualification case has no claim_packet: {case_id}")
        return deepcopy(dict(claim_packet))

    @staticmethod
    def _copy_object(object_: ScienceObject) -> ScienceObject:
        return object_.model_copy(deep=True)

    @staticmethod
    def _copy_case(case: QualificationCase) -> QualificationCase:
        return case.model_copy(deep=True)
