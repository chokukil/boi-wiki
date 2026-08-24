"""Indexed, immutable resolution of reviewed Science documents."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TypeAlias

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from boi_api.app.okf import (
    split_frontmatter,
    validate_boi_profile_metadata,
    validate_boi_profile_path_acl,
    validate_okf_core_metadata,
)
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.models import (
    ConditionConstraint,
    PackDependency,
    PackRelationKind,
    ReleaseCompatibilityResult,
    ReleaseSelection,
    ResolvedComponent,
    ResolvedRelease,
    ResolvedReleaseSet,
)
from boi_api.app.science.operational import (
    OperationalVerification,
    _issue_operational_verification,
)
from boi_api.app.science.profile import SCIENCE_TYPE_REQUIREMENTS, validate_sci_profile_metadata
from boi_api.app.science.rules import (
    QualificationRuleSet,
    ReleasedRule,
    ResolvedRuleSet,
    VerificationRule,
)


ObjectKind = Literal[
    "source", "evidence", "knowledge", "rule", "ontology_binding", "qualification_matrix", "pack", "release"
]

ReviewerRoleResolver: TypeAlias = Callable[[Mapping[str, str]], Iterable[str]]

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
    okf_status: str
    okf_author: dict[str, Any] | None = None
    okf_timestamp: str
    okf_review: dict[str, Any]
    okf_activation: dict[str, Any] | None = None


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

    def __init__(
        self,
        boi_root: Path,
        *,
        reviewer_role_resolver: ReviewerRoleResolver | None = None,
        trusted_clock: Callable[[], datetime] | None = None,
        clock_skew: timedelta = timedelta(seconds=30),
    ):
        if clock_skew < timedelta(0) or clock_skew > timedelta(minutes=1):
            raise ValueError("ScienceCatalog clock_skew must be between zero and one minute")
        self.boi_root = Path(boi_root)
        self.science_root = self.boi_root / "public" / "science"
        self._reviewer_role_resolver = reviewer_role_resolver
        self._trusted_clock = trusted_clock
        self._clock_skew = clock_skew
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
                okf_status=str(normalized_metadata.get("status", "")),
                okf_author=deepcopy(normalized_metadata.get("author")),
                okf_timestamp=str(normalized_metadata.get("timestamp", "")),
                okf_review=deepcopy(normalized_metadata.get("review", {})),
                okf_activation=deepcopy(normalized_metadata.get("activation")),
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
            self._require_many("pack", (edge.ref for edge in self._pack_dependencies(pack)))
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

    def _pack_dependencies(self, pack: ScienceObject) -> tuple[PackDependency, ...]:
        value = getattr(pack, "dependencies", None)
        if not isinstance(value, list):
            raise ScienceCatalogError(f"science pack has invalid dependencies: {pack.object_id}")
        try:
            return tuple(PackDependency.model_validate(item) for item in value)
        except ValidationError as exc:
            raise ScienceCatalogError(
                f"science pack has invalid typed relationship edges: {pack.object_id}"
            ) from exc

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

    @staticmethod
    def _verification_rule(rule: ScienceObject) -> VerificationRule:
        payload = {
            field_name: deepcopy(getattr(rule, field_name))
            for field_name in VerificationRule.model_fields
            if hasattr(rule, field_name)
        }
        try:
            return VerificationRule.model_validate(payload)
        except ValidationError as exc:
            raise ScienceCatalogError(f"invalid verification rule payload: {rule.object_id}") from exc

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
                    semantic_digest=(
                        sha256_digest(self._verification_rule(component))
                        if component.kind == "rule"
                        else None
                    ),
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
        resolved = ResolvedRelease(
            release_id=release_id,
            schema_version=schema_version,
            content_hash=declared_content_hash,
            status=status,
            components=tuple(components),
            component_digests={ref: declared_digests[ref] for ref in refs},
            known_limitations=list(known_limitations),
        )
        return resolved

    def _resolved_rule_set(self, release_set: ResolvedReleaseSet) -> ResolvedRuleSet:
        released_rules: list[ReleasedRule] = []
        for component in release_set.rule_components:
            stored = self._require("rule", component.ref)
            if (
                stored.digest != component.actual_digest
                or component.declared_digest != component.actual_digest
            ):
                raise ScienceCatalogError(f"rule component digest mismatch: {component.ref}")
            rule = self._verification_rule(stored)
            self._assert_rule_evidence_scope(rule)
            semantic_digest = sha256_digest(rule)
            if component.semantic_digest != semantic_digest:
                raise ScienceCatalogError(f"rule semantic digest mismatch: {component.ref}")
            released_rules.append(
                ReleasedRule(
                    rule=rule,
                    component_digest=component.actual_digest,
                    semantic_digest=semantic_digest,
                )
            )
        return ResolvedRuleSet(
            release_set_digest=release_set.combined_digest,
            rules=tuple(released_rules),
        )

    def resolve_qualification_rule_set(
        self, release_set: ResolvedReleaseSet
    ) -> QualificationRuleSet:
        """Resolve a serializable candidate Rule set for qualification only."""

        resolved = self._resolved_rule_set(release_set)
        return QualificationRuleSet.model_validate(
            resolved.model_dump(mode="json", exclude_unset=True)
        )

    def resolve_operational_rule_set(
        self, release_set: ResolvedReleaseSet
    ) -> OperationalVerification:
        """Issue the only capability accepted by the public verification Engine."""

        releases = (
            release_set.foundation_release,
            *release_set.domain_releases,
            *release_set.application_releases,
        )
        if any(release.status not in {"active", "superseded"} for release in releases):
            raise ScienceOperationalError(
                "release candidate or withdrawn release cannot be evaluated as active"
            )
        approval_snapshot: list[dict[str, Any]] = []
        for release in releases:
            approval_snapshot.extend(self._assert_active_decision_components(release))
        resolved = self._resolved_rule_set(release_set)
        return _issue_operational_verification(
            release_set,
            resolved,
            sorted(
                approval_snapshot,
                key=lambda item: (
                    str(item.get("release_id", "")),
                    str(item.get("object_id", "")),
                    str(item.get("event_kind", "")),
                    str(item.get("occurred_at", "")),
                ),
            ),
        )

    def resolve_rule_set(
        self, release_set: ResolvedReleaseSet
    ) -> OperationalVerification:
        """Backward-named operational resolver; qualification has a distinct method/type."""

        return self.resolve_operational_rule_set(release_set)

    @staticmethod
    def _family_is_within(claim_family: str, boundary: str) -> bool:
        return claim_family == boundary or claim_family.startswith(boundary + ".")

    def _assert_rule_evidence_scope(self, rule: VerificationRule) -> None:
        for use in rule.evidence_uses:
            evidence = self._require("evidence", use.evidence_ref)
            scope = getattr(evidence, "claim_scope", None)
            if not isinstance(scope, Mapping):
                raise ScienceCatalogError(
                    f"Evidence has no embedded claim scope: {use.evidence_ref}"
                )
            forbidden = scope.get("forbidden_claim_families")
            allowed = scope.get("allowed_claims")
            if not isinstance(forbidden, list) or not isinstance(allowed, list):
                raise ScienceCatalogError(
                    f"Evidence has invalid embedded claim scope: {use.evidence_ref}"
                )
            if any(
                isinstance(boundary, str)
                and self._family_is_within(use.claim_family, boundary)
                for boundary in forbidden
            ):
                raise ScienceCatalogError(
                    f"Evidence use selects a forbidden claim family: {use.evidence_ref}"
                )
            matches = [
                claim
                for claim in allowed
                if isinstance(claim, Mapping)
                and claim.get("claim_family") == use.claim_family
            ]
            if len(matches) != 1:
                raise ScienceCatalogError(
                    f"Evidence use is outside allowed claim scope: {use.evidence_ref}"
                )
            claim = matches[0]
            if claim.get("purpose") != use.purpose:
                raise ScienceCatalogError(
                    f"Evidence use purpose does not match embedded claim scope: {use.evidence_ref}"
                )
            raw_constraints = claim.get("required_conditions")
            if not isinstance(raw_constraints, list):
                raise ScienceCatalogError(
                    f"Evidence has invalid embedded claim scope: {use.evidence_ref}"
                )
            try:
                scope_constraints = [
                    ConditionConstraint.model_validate(item)
                    for item in raw_constraints
                ]
            except ValidationError as exc:
                raise ScienceCatalogError(
                    f"Evidence has invalid embedded claim scope: {use.evidence_ref}"
                ) from exc
            executable = {
                sha256_digest(condition): condition
                for condition in (*rule.required_conditions, *rule.validity_conditions)
            }
            for constraint in scope_constraints:
                if sha256_digest(constraint) not in executable:
                    raise ScienceCatalogError(
                        "Rule does not enforce required Evidence condition: "
                        f"{use.evidence_ref}:{constraint.key}"
                    )

    def resolve_release_set(self, selection: ReleaseSelection) -> ResolvedReleaseSet:
        release_ids = (selection.foundation, *selection.domains, *selection.applications)
        if len(set(release_ids)) != len(release_ids):
            raise ScienceOperationalError("Science release selection contains duplicate release IDs")
        foundation = self.resolve_release(selection.foundation)
        domains = tuple(self.resolve_release(release_id) for release_id in selection.domains)
        applications = tuple(
            self.resolve_release(release_id) for release_id in selection.applications
        )
        releases = (foundation, *domains, *applications)

        combined_by_ref: dict[str, ResolvedComponent] = {}
        for release in releases:
            for component in release.components:
                previous = combined_by_ref.get(component.ref)
                if previous is not None:
                    qualifier = (
                        "conflicting" if previous.actual_digest != component.actual_digest else "duplicate"
                    )
                    raise ScienceOperationalError(
                        f"{qualifier} component across releases: {component.ref}"
                    )
                combined_by_ref[component.ref] = component
        components = tuple(sorted(combined_by_ref.values(), key=lambda item: item.ref))
        selected_packs = {
            component.ref for component in components if component.kind == "pack"
        }
        checked_edges: list[PackDependency] = []
        for pack_id in sorted(selected_packs):
            pack = self._require("pack", pack_id)
            for edge in sorted(
                self._pack_dependencies(pack),
                key=lambda item: (item.relation.value, item.ref),
            ):
                checked_edges.append(edge)
                if edge.ref == pack_id:
                    raise ScienceOperationalError(
                        f"incompatible Pack dependency: {pack_id} cannot reference itself"
                    )
                if edge.relation is PackRelationKind.SUPERSEDES:
                    if edge.ref in selected_packs:
                        raise ScienceOperationalError(
                            f"incompatible Pack dependency: {pack_id} supersedes selected {edge.ref}"
                        )
                elif edge.ref not in selected_packs:
                    raise ScienceOperationalError(
                        f"incompatible Pack dependency: {pack_id} requires unselected {edge.ref}"
                    )

        release_digests = {
            release.release_id: release.content_hash
            for release in sorted(releases, key=lambda item: item.release_id)
        }
        compatibility = ReleaseCompatibilityResult(
            compatible=True,
            checked_pack_dependencies=tuple(checked_edges),
        )
        combined_digest = sha256_digest(
            {
                "selection": selection,
                "release_digests": release_digests,
                "components": components,
                "compatibility": compatibility,
            }
        )
        return ResolvedReleaseSet(
            selection=selection,
            foundation_release=foundation,
            domain_releases=domains,
            application_releases=applications,
            compatibility=compatibility,
            release_digests=release_digests,
            combined_digest=combined_digest,
            components=components,
            rule_components=tuple(
                component for component in components if component.kind == "rule"
            ),
        )

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
            resolved = self.resolve_release(selected.object_id)
            self._assert_active_decision_components(resolved)
            return resolved
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
        resolved = self.resolve_release(safe_id)
        self._assert_active_decision_components(resolved)
        return resolved

    @staticmethod
    def _actor_identity(actor: object) -> tuple[str, str] | None:
        """Return one canonical typed identity only for the closed actor schema."""

        if not isinstance(actor, Mapping):
            return None
        actor_type = actor.get("type")
        if actor_type == "human" and set(actor) == {"type", "user_id"}:
            value = actor.get("user_id")
            return (
                ("human", value.strip())
                if isinstance(value, str) and value.strip()
                else None
            )
        if actor_type == "agent" and set(actor) == {"type", "agent_id"}:
            value = actor.get("agent_id")
            return (
                ("agent", value.strip())
                if isinstance(value, str) and value.strip()
                else None
            )
        return None

    @staticmethod
    def _timestamp(value: object, *, label: str, object_id: str) -> datetime:
        if not isinstance(value, str):
            raise ScienceOperationalError(
                f"active decision component has invalid {label}: {object_id}"
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ScienceOperationalError(
                f"active decision component has invalid {label}: {object_id}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ScienceOperationalError(
                f"active decision component has invalid {label}: {object_id}"
            )
        return parsed

    def _trusted_now(self) -> datetime:
        if self._trusted_clock is None:
            raise ScienceOperationalError(
                "active Science release requires an injected trusted clock"
            )
        try:
            now = self._trusted_clock()
        except Exception as exc:
            raise ScienceOperationalError("trusted Science clock failed") from exc
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ScienceOperationalError("trusted Science clock must return an aware datetime")
        return now

    def _trusted_admin_roles(self, identity: tuple[str, str], object_id: str) -> set[str]:
        if self._reviewer_role_resolver is None:
            raise ScienceOperationalError(
                "active decision components require a trusted reviewer-role resolver"
            )
        if identity[0] != "human":
            raise ScienceOperationalError(f"active review actor is invalid: {object_id}")
        try:
            return set(
                self._reviewer_role_resolver(
                    {"type": "human", "user_id": identity[1]}
                )
            )
        except Exception as exc:
            raise ScienceOperationalError(
                f"trusted reviewer-role resolution failed: {object_id}"
            ) from exc

    def _authorship_boundary(self, component: ScienceObject) -> datetime:
        boundary = self._timestamp(
            component.okf_timestamp,
            label="authored timestamp",
            object_id=component.object_id,
        )
        for field_name in ("retrieved_at", "curated_at"):
            value = getattr(component, field_name, None)
            if value is not None:
                boundary = max(
                    boundary,
                    self._timestamp(value, label=field_name, object_id=component.object_id),
                )
        locator = getattr(component, "locator", None)
        if isinstance(locator, Mapping) and locator.get("retrieved_at") is not None:
            boundary = max(
                boundary,
                self._timestamp(
                    locator["retrieved_at"],
                    label="locator.retrieved_at",
                    object_id=component.object_id,
                ),
            )
        return boundary

    def _assert_active_decision_components(
        self, release: ResolvedRelease
    ) -> list[dict[str, Any]]:
        """Gate the Release and every pinned interpretation/decision component."""

        if self._reviewer_role_resolver is None:
            raise ScienceOperationalError(
                "active decision components require a trusted reviewer-role resolver"
            )
        now = self._trusted_now()
        stored_release = self._require("release", release.release_id)
        activation = stored_release.okf_activation
        if not isinstance(activation, Mapping):
            raise ScienceOperationalError(
                f"active Release lacks an authorized activation: {release.release_id}"
            )
        events = activation.get("authorized_activation_events")
        activated_events = (
            [
                event
                for event in events
                if isinstance(event, Mapping) and event.get("decision") == "activated"
            ]
            if isinstance(events, list)
            else []
        )
        if (
            activation.get("activation_status") not in {"active", "superseded"}
            or len(activated_events) != 1
        ):
            raise ScienceOperationalError(
                f"active Release lacks an authorized activation: {release.release_id}"
            )
        activation_event = activated_events[0]
        activation_identity = self._actor_identity(activation_event.get("actor"))
        if activation_identity is None or activation_identity[0] != "human":
            raise ScienceOperationalError(
                f"active Release activation actor is invalid: {release.release_id}"
            )
        activation_at = self._timestamp(
            activation_event.get("occurred_at"),
            label="activation occurred_at",
            object_id=release.release_id,
        )
        if activation_at > now + self._clock_skew:
            raise ScienceOperationalError(
                f"active Release activation occurs after trusted clock: {release.release_id}"
            )
        if activation_at < self._authorship_boundary(stored_release):
            raise ScienceOperationalError(
                f"active Release activation precedes authorship: {release.release_id}"
            )
        release_author = self._actor_identity(stored_release.okf_author)
        if release_author is None:
            raise ScienceOperationalError(
                f"active Release author actor is invalid: {release.release_id}"
            )
        if release_author == activation_identity:
            raise ScienceOperationalError(
                f"active Release forbids author self-activation: {release.release_id}"
            )
        if "science.admin" not in self._trusted_admin_roles(
            activation_identity, release.release_id
        ):
            raise ScienceOperationalError(
                f"activation actor is not authorized as science.admin: {release.release_id}"
            )

        component_refs = {component.ref for component in release.components}
        components = [self._find_component(component.ref) for component in release.components]
        for component in components:
            if component.kind == "evidence":
                source_id = self._string_field(component, "source_id")
                if source_id not in component_refs:
                    raise ScienceOperationalError(
                        f"active Evidence requires its pinned Source component: {component.object_id}"
                    )

        snapshot = self._assert_component_admin_approved(
            stored_release,
            activation_at=activation_at,
            now=now,
            label="Release",
        )
        for component in components:
            snapshot.extend(
                self._assert_component_admin_approved(
                    component,
                    activation_at=activation_at,
                    now=now,
                    label="decision component",
                )
            )
        snapshot.append(
            {
                "release_id": release.release_id,
                "object_id": release.release_id,
                "object_digest": stored_release.digest,
                "event_kind": "activation",
                "actor": {"type": "human", "user_id": activation_identity[1]},
                "occurred_at": activation_at.isoformat(),
            }
        )
        return snapshot

    def _assert_component_admin_approved(
        self,
        component: ScienceObject,
        *,
        activation_at: datetime,
        now: datetime,
        label: str,
    ) -> list[dict[str, Any]]:
        if component.okf_status != "approved":
            raise ScienceOperationalError(
                f"active {label} must be approved: {component.object_id}"
            )
        if getattr(component, "release_eligibility", None) != "active_release_eligible":
            raise ScienceOperationalError(
                f"active {label} has blocked release eligibility: {component.object_id}"
            )
        if component.kind == "source" and getattr(component, "retrieval_status", None) != "verified":
            raise ScienceOperationalError(
                f"active Source retrieval is not verified: {component.object_id}"
            )
        if component.kind == "evidence" and getattr(component, "decision_eligibility", None) != "eligible":
            raise ScienceOperationalError(
                f"active Evidence has invalid decision eligibility: {component.object_id}"
            )

        review = component.okf_review
        events = review.get("authorized_review_events")
        if review.get("review_status") != "approved" or not isinstance(events, list) or not events:
            raise ScienceOperationalError(
                f"active decision component lacks an authorized approved review: {component.object_id}"
            )
        boundary = self._authorship_boundary(component)

        approved_events = [
            event
            for event in events
            if isinstance(event, Mapping) and event.get("decision") == "approved"
        ]
        if not approved_events:
            raise ScienceOperationalError(
                f"active decision component lacks an authorized approved review: {component.object_id}"
            )
        author_identity = self._actor_identity(component.okf_author)
        if author_identity is None:
            raise ScienceOperationalError(
                f"active {label} author actor is invalid: {component.object_id}"
            )
        snapshot: list[dict[str, Any]] = []
        for event in approved_events:
            actor = event.get("actor")
            actor_identity = self._actor_identity(actor)
            if actor_identity is None or actor_identity[0] != "human":
                raise ScienceOperationalError(
                    f"active {label} review actor is invalid: {component.object_id}"
                )
            if actor_identity == author_identity:
                raise ScienceOperationalError(
                    f"active decision component forbids author self-approval: {component.object_id}"
                )
            occurred_at = self._timestamp(
                event.get("occurred_at"),
                label="approval occurred_at",
                object_id=component.object_id,
            )
            if occurred_at > now + self._clock_skew:
                raise ScienceOperationalError(
                    f"active {label} approval occurs after trusted clock: {component.object_id}"
                )
            if occurred_at < boundary:
                raise ScienceOperationalError(
                    f"active decision component has temporally invalid approval: {component.object_id}"
                )
            if occurred_at > activation_at:
                raise ScienceOperationalError(
                    f"active {label} approval occurs after Release activation: {component.object_id}"
                )
            trusted_roles = self._trusted_admin_roles(actor_identity, component.object_id)
            if "science.admin" not in trusted_roles:
                raise ScienceOperationalError(
                    f"reviewer is not authorized as science.admin: {component.object_id}"
                )
            snapshot.append(
                {
                    "object_id": component.object_id,
                    "object_kind": component.kind,
                    "object_digest": component.digest,
                    "event_kind": "approval",
                    "actor": {"type": "human", "user_id": actor_identity[1]},
                    "occurred_at": occurred_at.isoformat(),
                }
            )
        return snapshot

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
