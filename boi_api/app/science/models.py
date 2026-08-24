from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScienceModel(BaseModel):
    """Base model that rejects undeclared packet fields."""

    model_config = ConfigDict(extra="forbid")


_REVIEWED_UNIT_ALIASES = {
    "K": "kelvin",
    "kelvin": "kelvin",
    "°C": "°C",
    "degC": "°C",
    "degree_Celsius": "°C",
    "m": "meter",
    "meter": "meter",
    "cm": "centimeter",
    "centimeter": "centimeter",
    "V": "volt",
    "volt": "volt",
    "A": "ampere",
    "ampere": "ampere",
    "Ω": "ohm",
    "ohm": "ohm",
}


def _is_unit_identifier_character(character: str) -> bool:
    return (
        character == "_"
        or character.isalpha()
        or (character.isascii() and character.isdigit())
    )


def _contains_ambiguous_ph_identifier(expression: str) -> bool:
    start = 0
    while (index := expression.find("pH", start)) >= 0:
        before = expression[index - 1] if index else ""
        after_index = index + 2
        after = expression[after_index] if after_index < len(expression) else ""
        if (not before or not _is_unit_identifier_character(before)) and (
            not after or not _is_unit_identifier_character(after)
        ):
            return True
        start = after_index
    return False


def canonical_science_unit_token(value: object) -> str:
    """Return the reviewed canonical spelling for a unit or registered product."""

    if not isinstance(value, str):
        raise ValueError("unit token must be a string")
    token = value.strip()
    if not token:
        raise ValueError("unit token must be nonempty")
    if _contains_ambiguous_ph_identifier(token):
        raise ValueError("ambiguous unit token: pH")
    if token.count("*") == 1:
        factors = [
            _REVIEWED_UNIT_ALIASES.get(factor.strip(), factor.strip())
            for factor in token.split("*")
        ]
        if sorted(factors) == ["ampere", "ohm"]:
            return "ampere * ohm"
    return _REVIEWED_UNIT_ALIASES.get(token, token)


def _canonical_identifier(value: str, field_name: str) -> str:
    identifier = value.strip()
    if not identifier:
        raise ValueError(f"{field_name} must be nonempty")
    return identifier


class PrimaryVerdict(str, Enum):
    VIOLATION = "VIOLATION"
    CONSISTENT = "CONSISTENT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    OUTSIDE_VALIDITY_DOMAIN = "OUTSIDE_VALIDITY_DOMAIN"
    EMPIRICAL_VERIFICATION_REQUIRED = "EMPIRICAL_VERIFICATION_REQUIRED"


class RelationKind(str, Enum):
    MONOTONIC_DIRECTION = "monotonic_direction"
    EQUATION = "equation"
    DIMENSIONAL_RELATION = "dimensional_relation"
    CAUSAL_RELATION = "causal_relation"
    EMPIRICAL_RELATION = "empirical_relation"


class ConversionKind(str, Enum):
    MULTIPLICATIVE = "multiplicative"
    AFFINE = "affine"
    LOGARITHMIC = "logarithmic"
    PROCEDURE_DEFINED = "procedure_defined"


class RuleKind(str, Enum):
    DIRECTIONAL_RELATION = "directional_relation"
    EQUATION_CONSTRAINT = "equation_constraint"
    DIMENSION_CONSTRAINT = "dimension_constraint"
    VALIDITY_DOMAIN = "validity_domain"
    EMPIRICAL_BOUNDARY = "empirical_boundary"


class PackRelationKind(str, Enum):
    DEPENDS_ON = "depends_on"
    USES = "uses"
    SPECIALIZES = "specializes"
    ADDS_EVIDENCE = "adds_evidence"
    VALIDATED_BY = "validated_by"
    SUPERSEDES = "supersedes"


class PackDependency(ScienceModel):
    relation: PackRelationKind
    ref: str = Field(min_length=1, pattern=r"^sci-pack:[^\s]+$")


class SourceSpan(ScienceModel):
    offset_encoding: Literal["unicode_code_point"] = "unicode_code_point"
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    exact: str = Field(min_length=1)
    prefix: str = ""
    suffix: str = ""

    @model_validator(mode="after")
    def valid_range(self) -> "SourceSpan":
        if self.end <= self.start or self.end - self.start != len(self.exact):
            raise ValueError("source span does not match Unicode code-point length")
        return self


class ClaimQuantity(ScienceModel):
    quantity_kind: str
    value: Decimal
    unit: str

    @field_validator("quantity_kind")
    @classmethod
    def canonical_quantity_kind(cls, value: str) -> str:
        return _canonical_identifier(value, "quantity_kind")

    @field_validator("unit")
    @classmethod
    def canonical_unit(cls, value: str) -> str:
        return canonical_science_unit_token(value)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("quantity value must be finite")
        return value


class ClaimCondition(ScienceModel):
    condition_id: str
    value: str | int | float | bool | None
    unit: str | None = None

    @field_validator("condition_id")
    @classmethod
    def canonical_condition_id(cls, value: str) -> str:
        return _canonical_identifier(value, "condition_id")

    @field_validator("unit")
    @classmethod
    def canonical_unit(cls, value: str | None) -> str | None:
        return canonical_science_unit_token(value) if value is not None else None

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: str | int | float | bool | None):
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("condition value must be finite")
        return value

    @model_validator(mode="after")
    def unit_requires_numeric_value(self) -> "ClaimCondition":
        numeric = isinstance(self.value, (int, float)) and not isinstance(self.value, bool)
        if self.unit is not None and not numeric:
            raise ValueError("condition unit requires a numeric value")
        return self


ConditionScalar: TypeAlias = str | int | float | bool


class ConditionRange(ScienceModel):
    minimum: Decimal
    maximum: Decimal
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True

    @model_validator(mode="after")
    def finite_ordered_range(self) -> "ConditionRange":
        if not self.minimum.is_finite() or not self.maximum.is_finite():
            raise ValueError("condition range must be finite")
        if self.minimum > self.maximum:
            raise ValueError("condition range minimum cannot exceed maximum")
        return self


class ConditionConstraint(ScienceModel):
    key: str = Field(min_length=1)
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "range", "in"]
    value: ConditionScalar | None = None
    range: ConditionRange | None = None
    values: list[ConditionScalar] | None = None
    unit: str | None = None

    @field_validator("unit")
    @classmethod
    def canonical_unit(cls, value: str | None) -> str | None:
        return canonical_science_unit_token(value) if value is not None else None

    @model_validator(mode="after")
    def valid_operand(self) -> "ConditionConstraint":
        if self.operator == "range":
            if self.range is None or self.value is not None or self.values is not None:
                raise ValueError("range condition requires only a range operand")
        elif self.operator == "in":
            if (
                not self.values
                or self.value is not None
                or self.range is not None
                or self.unit is not None
            ):
                raise ValueError("membership condition requires only nonempty values")
            if len({(type(value).__name__, repr(value)) for value in self.values}) != len(
                self.values
            ):
                raise ValueError("membership condition values must be unique")
            kinds = {
                "boolean"
                if isinstance(value, bool)
                else "numeric"
                if isinstance(value, (int, float))
                else "string"
                for value in self.values
            }
            if len(kinds) != 1:
                raise ValueError("membership condition values must have one scalar type")
            if any(
                isinstance(value, float) and not isfinite(value)
                for value in self.values
            ):
                raise ValueError("membership condition values must be finite")
        elif self.value is None or self.range is not None or self.values is not None:
            raise ValueError("condition operator requires only a value operand")
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("condition constraint value must be finite")
        numeric = isinstance(self.value, (int, float)) and not isinstance(self.value, bool)
        if self.unit is not None and self.operator != "range" and not numeric:
            raise ValueError("condition unit requires a numeric value")
        if self.operator in {"lt", "lte", "gt", "gte"} and not numeric:
            raise ValueError("ordered condition operator requires a numeric value")
        return self


class NormalizedClaim(ScienceModel):
    subject_concept_id: str
    relation_kind: RelationKind
    predicate: str
    object_concept_id: str
    polarity: Literal["positive", "negative"]
    quantities: list[ClaimQuantity]
    conditions: list[ClaimCondition]
    process_stage: str | None
    material_state: str | None

    @model_validator(mode="after")
    def unambiguous_lookup_identifiers(self) -> "NormalizedClaim":
        quantity_kinds = [quantity.quantity_kind for quantity in self.quantities]
        if len(quantity_kinds) != len(set(quantity_kinds)):
            raise ValueError("quantity_kind values must be unique")
        condition_ids = [condition.condition_id for condition in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("condition_id values must be unique")
        reserved = {"process_stage", "material_state"} & set(condition_ids)
        if reserved:
            raise ValueError(
                f"reserved condition_id is not allowed: {', '.join(sorted(reserved))}"
            )
        return self


class ClaimInterpretation(ScienceModel):
    ontology_refs: list[str]
    ambiguity_ids: list[str]
    user_confirmed: bool


class ClaimPacket(ScienceModel):
    claim_id: str
    document_ref: str
    document_digest: str
    source_span: SourceSpan
    normalized_claim: NormalizedClaim
    interpretation: ClaimInterpretation


class ConditionEvaluation(ScienceModel):
    condition_id: str
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "range", "in"] = "eq"
    expected: ConditionScalar | list[ConditionScalar] | ConditionRange | None
    actual: str | int | float | bool | None
    expected_unit: str | None = None
    actual_unit: str | None = None
    satisfied: bool
    reason_code: str | None = None


class ReleaseSelection(ScienceModel):
    foundation: str
    domains: list[str] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)


class ResolvedComponent(ScienceModel):
    ref: str
    kind: Literal[
        "source",
        "evidence",
        "knowledge",
        "rule",
        "ontology_binding",
        "qualification_matrix",
        "pack",
    ]
    declared_digest: str
    actual_digest: str
    semantic_digest: str | None = None


class ResolvedRelease(ScienceModel):
    release_id: str
    schema_version: Literal["sci-profile/0.1"]
    content_hash: str
    status: Literal["release_candidate", "active", "superseded", "withdrawn"]
    components: tuple[ResolvedComponent, ...]
    component_digests: dict[str, str]
    known_limitations: list[str]


class ReleaseCompatibilityResult(ScienceModel):
    compatible: bool
    checked_pack_dependencies: tuple[PackDependency, ...]


class ResolvedReleaseSet(ScienceModel):
    selection: ReleaseSelection
    foundation_release: ResolvedRelease
    domain_releases: tuple[ResolvedRelease, ...]
    application_releases: tuple[ResolvedRelease, ...]
    compatibility: ReleaseCompatibilityResult
    release_digests: dict[str, str]
    combined_digest: str
    components: tuple[ResolvedComponent, ...]
    rule_components: tuple[ResolvedComponent, ...]

    @staticmethod
    def combined_digest_for(
        selection: ReleaseSelection,
        release_digests: dict[str, str],
        components: tuple[ResolvedComponent, ...],
        compatibility: ReleaseCompatibilityResult,
    ) -> str:
        from boi_api.app.science.digests import sha256_digest

        return sha256_digest(
            {
                "selection": selection,
                "release_digests": release_digests,
                "components": components,
                "compatibility": compatibility,
            }
        )

    @classmethod
    def from_single_foundation(cls, release: ResolvedRelease) -> "ResolvedReleaseSet":
        """Adapt the original single-Foundation boundary without inventing other roles."""
        selection = ReleaseSelection(foundation=release.release_id)
        components = tuple(sorted(release.components, key=lambda item: item.ref))
        compatibility = ReleaseCompatibilityResult(
            compatible=True,
            checked_pack_dependencies=(),
        )
        release_digests = {release.release_id: release.content_hash}
        combined_digest = cls.combined_digest_for(
            selection,
            release_digests,
            components,
            compatibility,
        )
        return cls(
            selection=selection,
            foundation_release=release,
            domain_releases=(),
            application_releases=(),
            compatibility=compatibility,
            release_digests=release_digests,
            combined_digest=combined_digest,
            components=components,
            rule_components=tuple(
                component for component in components if component.kind == "rule"
            ),
        )

    @model_validator(mode="after")
    def exact_selection_and_combined_order(self) -> "ResolvedReleaseSet":
        if self.foundation_release.release_id != self.selection.foundation:
            raise ValueError("Foundation release does not match original selection")
        if [release.release_id for release in self.domain_releases] != self.selection.domains:
            raise ValueError("Domain releases do not match original selection")
        if [release.release_id for release in self.application_releases] != self.selection.applications:
            raise ValueError("Application releases do not match original selection")
        releases = (
            self.foundation_release,
            *self.domain_releases,
            *self.application_releases,
        )
        expected_digests = {release.release_id: release.content_hash for release in releases}
        if self.release_digests != expected_digests:
            raise ValueError("release digest map does not match resolved selection")
        release_components = tuple(
            sorted(
                (
                    component
                    for release in releases
                    for component in release.components
                ),
                key=lambda item: item.ref,
            )
        )
        release_component_refs = [component.ref for component in release_components]
        if len(release_component_refs) != len(set(release_component_refs)):
            raise ValueError("resolved releases contain duplicate components")
        if self.components != release_components:
            raise ValueError("combined release components must exactly match resolved releases")
        if self.rule_components != tuple(
            component for component in self.components if component.kind == "rule"
        ):
            raise ValueError("combined release rule components are inconsistent")
        if self.combined_digest != self.combined_digest_for(
            self.selection,
            self.release_digests,
            self.components,
            self.compatibility,
        ):
            raise ValueError("Release set has an invalid exact combined digest")
        return self


class RuleEvaluation(ScienceModel):
    rule_id: str
    applicability: Literal[
        "IN_SCOPE",
        "MISSING_CONDITIONS",
        "OUTSIDE_DOMAIN",
        "EMPIRICAL_ONLY",
        "NOT_APPLICABLE",
    ]
    outcome: Literal["CONTRADICTS", "SUPPORTS", "UNDECIDED"]
    reason_codes: list[str]
    condition_evaluations: list[ConditionEvaluation]
    knowledge_refs: list[str]
    evidence_refs: list[str]


class ExplanationFact(ScienceModel):
    fact_id: str
    knowledge_refs: list[str]
    evidence_refs: list[str]


class VerdictReleaseSet(ScienceModel):
    selection: ReleaseSelection
    digests: dict[str, str]
    combined_digest: str


class VerdictPacket(ScienceModel):
    claim_id: str
    claim_packet_digest: str
    verifier_version: str
    releases: VerdictReleaseSet
    verdict: PrimaryVerdict
    reason_codes: list[str]
    condition_evaluations: list[ConditionEvaluation]
    decisive_rule_ids: list[str]
    knowledge_refs: list[str]
    evidence_refs: list[str]
    corrected_claim: str | None
    explanation_facts: list[ExplanationFact]
    limitations: list[str]


class InterpretationRecord(ScienceModel):
    interpretation_id: str
    document_digest: str
    candidate_claims: list[ClaimPacket]
    model_id: str
    model_settings: dict[str, str | int | float | bool]
    prompt_version: str
    dictionary_release_id: str
    ontology_release_id: str
    ontology_refs: list[str]
    candidate_meanings: list[dict[str, Any]]
    decision_impact: list[dict[str, Any]]
    user_revision_history: list[dict[str, Any]]
    confirmed_claim_packet_digest: str | None
    response_digest: str

    @field_validator("model_settings")
    @classmethod
    def finite_model_settings(
        cls, settings: dict[str, str | int | float | bool]
    ) -> dict[str, str | int | float | bool]:
        if any(isinstance(value, float) and not isfinite(value) for value in settings.values()):
            raise ValueError("model settings must be finite")
        return settings


class VerificationReport(ScienceModel):
    report_id: str
    document_ref: str | None
    document_digest: str
    release_selection: ReleaseSelection
    release_digests: dict[str, str]
    interpretation_ids: list[str]
    verdict_packets: list[VerdictPacket]
    unresolved_ambiguities: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    created_at: datetime
    created_by: str
    report_digest: str
