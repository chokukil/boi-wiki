"""Strict semantic-only Domain Profile 0.2 contracts.

Draft validation proves one entry is structurally meaningful. Release
qualification additionally proves exact logical reference closure and authority.
Physical identifiers belong to the data-mapping profile and are rejected at any
depth here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Annotated, Any, Literal, Mapping, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from .semantic_binding_contract import SemanticAuthorityBasis

AuthorityBasis = SemanticAuthorityBasis
_PHYSICAL_FIELDS = frozenset(
    {
        "source", "source_id", "table", "column", "physical", "sql", "raw_sql",
        "dialect", "schema_snapshot", "schema_snapshot_digest",
    }
)


def _digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _deep_physical_fields(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).casefold()
            if key in _PHYSICAL_FIELDS:
                found.add(key)
            found.update(_deep_physical_fields(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_deep_physical_fields(child))
    return found


class ApplicabilityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str = Field(min_length=1)
    conditions: tuple[dict[str, Any], ...]


class EffectiveWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> "EffectiveWindow":
        if (
            self.start.tzinfo is None
            or self.end.tzinfo is None
            or self.start.utcoffset() is None
            or self.end.utcoffset() is None
        ):
            raise ValueError("EFFECTIVE_WINDOW_OFFSET_REQUIRED")
        if self.start >= self.end:
            raise ValueError("EFFECTIVE_WINDOW_ORDER_INVALID")
        return self


class DomainProfileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    id: str = Field(min_length=1)
    name: str | None = None
    aliases: tuple[str, ...] = ()
    description: str | None = None
    authority_basis: AuthorityBasis
    applicability: ApplicabilityContract

    @model_validator(mode="after")
    def validate_lexical_contract(self) -> "DomainProfileEntry":
        if self.name is not None and not self.name.strip():
            raise ValueError("DOMAIN_NAME_EMPTY")
        if self.description is not None and not self.description.strip():
            raise ValueError("DOMAIN_DESCRIPTION_EMPTY")
        normalized = tuple(item.strip().casefold() for item in self.aliases)
        if any(not item for item in normalized):
            raise ValueError("DOMAIN_ALIAS_EMPTY")
        if len(normalized) != len(set(normalized)):
            raise ValueError("DOMAIN_ALIAS_DUPLICATE")
        return self

    @model_validator(mode="before")
    @classmethod
    def forbid_physical_fields(cls, value: object) -> object:
        if fields := _deep_physical_fields(value):
            raise ValueError(
                "DOMAIN_PHYSICAL_BOUNDARY_VIOLATION:" + ",".join(sorted(fields))
            )
        return value


class TermEntry(DomainProfileEntry):
    kind: Literal["Term"]
    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()


class UnitConversion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_unit_ref: str = Field(min_length=1)
    scale: str = Field(min_length=1)
    offset: str = "0"

    @model_validator(mode="after")
    def validate_affine_conversion(self) -> "UnitConversion":
        try:
            scale = Decimal(self.scale)
            offset = Decimal(self.offset)
        except InvalidOperation as error:
            raise ValueError("UNIT_CONVERSION_NUMBER_INVALID") from error
        if not scale.is_finite() or not offset.is_finite() or scale == 0:
            raise ValueError("UNIT_CONVERSION_NUMBER_INVALID")
        return self


class ValueTypeEntry(DomainProfileEntry):
    kind: Literal["ValueType"]
    primitive_type: Literal[
        "string", "integer", "number", "boolean", "date", "datetime", "duration"
    ]
    unit_semantics: Literal["not_applicable", "dimensionless", "declared"]
    time_semantics: str = Field(min_length=1)
    unit_ref: str | None = None
    unit_conversions: tuple[UnitConversion, ...] = ()

    @model_validator(mode="after")
    def validate_unit(self) -> "ValueTypeEntry":
        if self.unit_semantics == "declared" and not self.unit_ref:
            raise ValueError("VALUE_TYPE_UNIT_REF_REQUIRED")
        if self.unit_semantics != "declared" and self.unit_ref is not None:
            raise ValueError("VALUE_TYPE_UNIT_REF_FORBIDDEN")
        if self.unit_semantics != "declared" and self.unit_conversions:
            raise ValueError("VALUE_TYPE_UNIT_CONVERSION_FORBIDDEN")
        conversion_refs = tuple(item.from_unit_ref for item in self.unit_conversions)
        if len(conversion_refs) != len(set(conversion_refs)):
            raise ValueError("VALUE_TYPE_UNIT_CONVERSION_DUPLICATE")
        if self.unit_ref in conversion_refs:
            raise ValueError("VALUE_TYPE_CANONICAL_UNIT_CONVERSION_FORBIDDEN")
        return self


class ObjectTypeEntry(DomainProfileEntry):
    kind: Literal["ObjectType"]
    identity_property_ref: str = Field(min_length=1)
    property_refs: tuple[str, ...] = Field(min_length=1)
    logical_grain: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_grain(self) -> "ObjectTypeEntry":
        if self.identity_property_ref not in self.property_refs:
            raise ValueError("OBJECT_IDENTITY_NOT_IN_PROPERTIES")
        if self.identity_property_ref not in self.logical_grain:
            raise ValueError("OBJECT_IDENTITY_NOT_IN_GRAIN")
        if len(set(self.property_refs)) != len(self.property_refs) or len(
            set(self.logical_grain)
        ) != len(self.logical_grain):
            raise ValueError("OBJECT_PROPERTY_OR_GRAIN_DUPLICATE")
        return self


class PropertyDefinitionEntry(DomainProfileEntry):
    kind: Literal["PropertyDefinition"]
    owner_ref: str = Field(min_length=1)
    value_type_ref: str = Field(min_length=1)
    logical_role: Literal["identity", "attribute", "event_time", "effective_time"]
    unit_semantics: Literal["not_applicable", "dimensionless", "declared"]
    time_semantics: str = Field(min_length=1)
    unit_ref: str | None = None

    @model_validator(mode="after")
    def validate_unit(self) -> "PropertyDefinitionEntry":
        if self.unit_semantics == "declared" and not self.unit_ref:
            raise ValueError("PROPERTY_UNIT_REF_REQUIRED")
        if self.unit_semantics != "declared" and self.unit_ref is not None:
            raise ValueError("PROPERTY_UNIT_REF_FORBIDDEN")
        return self


class RelationTypeEntry(DomainProfileEntry):
    kind: Literal["RelationType"]
    semantic_name: str = Field(min_length=1)
    left_endpoint_ref: str = Field(min_length=1)
    right_endpoint_ref: str = Field(min_length=1)
    left_property_refs: tuple[str, ...] = Field(min_length=1)
    right_property_refs: tuple[str, ...] = Field(min_length=1)
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    left_optional: bool
    right_optional: bool
    relationship_identity_ref: str | None
    temporal_semantics: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relationship_identity(self) -> "RelationTypeEntry":
        if self.cardinality == "many_to_many" and not self.relationship_identity_ref:
            raise ValueError("RELATIONSHIP_IDENTITY_REQUIRED")
        if len(self.left_property_refs) != len(self.right_property_refs):
            raise ValueError("RELATIONSHIP_LOGICAL_KEY_ARITY_MISMATCH")
        if (
            len(set(self.left_property_refs)) != len(self.left_property_refs)
            or len(set(self.right_property_refs)) != len(self.right_property_refs)
        ):
            raise ValueError("RELATIONSHIP_LOGICAL_KEY_DUPLICATE")
        return self


class MetricEntry(DomainProfileEntry):
    kind: Literal["Metric"]
    grain: tuple[str, ...] = Field(min_length=1)
    unit: str = Field(min_length=1)
    aggregation: str = Field(min_length=1)
    time_semantics: str = Field(min_length=1)
    inclusion: dict[str, Any]
    exclusion: dict[str, Any]


class RuleEntry(DomainProfileEntry):
    kind: Literal["Rule"]
    priority: int
    conflict_policy: Literal[
        "higher_priority_wins", "deny_overrides", "allow_overrides", "manual_resolution"
    ]
    effective_window: EffectiveWindow
    expression: dict[str, Any]


DomainEntryUnion = Annotated[
    Union[
        TermEntry,
        ObjectTypeEntry,
        PropertyDefinitionEntry,
        RelationTypeEntry,
        ValueTypeEntry,
        MetricEntry,
        RuleEntry,
    ],
    Field(discriminator="kind"),
]
_ENTRY_ADAPTER = TypeAdapter(DomainEntryUnion)


class DomainReleaseQualification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["DRAFT_VALID", "RELEASE_QUALIFIED"]
    draft_valid: Literal[True] = True
    release_qualified: bool
    entry_count: int
    revision_closure_digest: str
    reason_codes: tuple[str, ...]


def validate_domain_profile_entry(value: object) -> DomainProfileEntry:
    return _ENTRY_ADAPTER.validate_python(value)


def domain_profile_json_schema() -> dict[str, Any]:
    return _ENTRY_ADAPTER.json_schema()


def _expression_refs(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).endswith("_ref") and isinstance(child, str):
                refs.add(child)
            refs.update(_expression_refs(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            refs.update(_expression_refs(child))
    return refs


def _structural_entry_references(entry):
    if isinstance(entry,ObjectTypeEntry):return set(entry.property_refs)|set(entry.logical_grain)
    if isinstance(entry,PropertyDefinitionEntry):
        return {entry.owner_ref,entry.value_type_ref}|({entry.unit_ref} if entry.unit_ref else set())
    if isinstance(entry,RelationTypeEntry):
        return {entry.left_endpoint_ref,entry.right_endpoint_ref,*entry.left_property_refs,*entry.right_property_refs}|(
            {entry.relationship_identity_ref} if entry.relationship_identity_ref else set())
    if isinstance(entry,ValueTypeEntry) and entry.unit_ref:
        return {entry.unit_ref,*(item.from_unit_ref for item in entry.unit_conversions)}
    if isinstance(entry,MetricEntry):return set(entry.grain)
    if isinstance(entry,RuleEntry):return _expression_refs(entry.expression)
    return set()


def domain_entry_references(entry):
    """Typed logical dependencies shared by retrieval of a closure and validation."""
    refs=_structural_entry_references(entry)
    for clause in entry.applicability.conditions:
        if clause.get('contract_version')=='boi/semantic-qualifier@1':
            from .semantic_qualifier import SemanticQualifier
            qualifier=SemanticQualifier.model_validate(clause)
            for predicate in qualifier.predicates:
                refs.add(predicate.property_ref)
                if predicate.unit_ref:refs.add(predicate.unit_ref)
    return refs


def domain_reference_closure_reasons(entries):
    """Logical dependency checks shared by draft use and Release qualification."""
    by_id = {entry.id: entry for entry in entries}
    reasons: set[str] = set()
    if len(by_id) != len(entries):
        reasons.add("DOMAIN_ID_DUPLICATE")

    referenced: set[str] = set()
    for entry in entries:
        referenced.update(domain_entry_references(entry))
        if isinstance(entry, ObjectTypeEntry):
            for property_ref in entry.property_refs:
                property_entry = by_id.get(property_ref)
                if not isinstance(property_entry, PropertyDefinitionEntry) or (
                    property_entry.owner_ref != entry.id
                ):
                    reasons.add("DOMAIN_OBJECT_PROPERTY_OWNERSHIP_INVALID")
        elif isinstance(entry, RelationTypeEntry):
            expected_left_owner = entry.left_endpoint_ref
            expected_right_owner = entry.right_endpoint_ref
            if any(
                not isinstance(by_id.get(property_ref), PropertyDefinitionEntry)
                or by_id[property_ref].owner_ref != expected_left_owner
                for property_ref in entry.left_property_refs
            ) or any(
                not isinstance(by_id.get(property_ref), PropertyDefinitionEntry)
                or by_id[property_ref].owner_ref != expected_right_owner
                for property_ref in entry.right_property_refs
            ):
                reasons.add("DOMAIN_RELATIONSHIP_KEY_OWNERSHIP_INVALID")
    if not referenced <= set(by_id):
        reasons.add("DOMAIN_REFERENCE_CLOSURE_INCOMPLETE")

    return reasons


def qualify_domain_profile_release(
    values: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> DomainReleaseQualification:
    entries = tuple(validate_domain_profile_entry(value) for value in values)
    reasons = domain_reference_closure_reasons(entries)
    # Preserving either an observation or a source's definition is not a
    # declaration of independently qualified domain/release authority.
    if any(entry.authority_basis in {"observed", "source_reported"} for entry in entries):
        reasons.add("DOMAIN_AUTHORITY_NOT_RELEASE_QUALIFIED")

    serialized = tuple(
        entry.model_dump(mode="json") for entry in sorted(entries, key=lambda item: item.id)
    )
    qualified = not reasons
    return DomainReleaseQualification(
        status="RELEASE_QUALIFIED" if qualified else "DRAFT_VALID",
        release_qualified=qualified,
        entry_count=len(entries),
        revision_closure_digest=_digest(serialized),
        reason_codes=tuple(sorted(reasons)),
    )


__all__ = [
    "DomainProfileEntry",
    "DomainReleaseQualification",
    "domain_profile_json_schema",
    "qualify_domain_profile_release",
    "validate_domain_profile_entry",
]
