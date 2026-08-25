from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.equations import SemanticExpression
from boi_api.app.science.safety import (
    reject_sensitive_persistence,
    validate_credential_free_https_url,
    validate_model_identifier,
)


class ScienceModel(BaseModel):
    """Base model that rejects undeclared packet fields."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


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
        numeric = isinstance(self.value, (int, float)) and not isinstance(
            self.value, bool
        )
        if self.unit is not None and not numeric:
            raise ValueError("condition unit requires a numeric value")
        return self


ConditionScalar: TypeAlias = str | int | float | bool
ClaimSubmissionClientKind: TypeAlias = Literal[
    "user", "codex", "claude", "qwen", "other"
]


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
            if len(
                {(type(value).__name__, repr(value)) for value in self.values}
            ) != len(self.values):
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
                raise ValueError(
                    "membership condition values must have one scalar type"
                )
            if any(
                isinstance(value, float) and not isfinite(value)
                for value in self.values
            ):
                raise ValueError("membership condition values must be finite")
        elif self.value is None or self.range is not None or self.values is not None:
            raise ValueError("condition operator requires only a value operand")
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("condition constraint value must be finite")
        numeric = isinstance(self.value, (int, float)) and not isinstance(
            self.value, bool
        )
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
    proposed_ontology_refs: list[str] = Field(default_factory=list)
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
        """Adapt the original single-Foundation boundary without new roles."""
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
        if [
            release.release_id for release in self.domain_releases
        ] != self.selection.domains:
            raise ValueError("Domain releases do not match original selection")
        if [
            release.release_id for release in self.application_releases
        ] != self.selection.applications:
            raise ValueError("Application releases do not match original selection")
        releases = (
            self.foundation_release,
            *self.domain_releases,
            *self.application_releases,
        )
        expected_digests = {
            release.release_id: release.content_hash for release in releases
        }
        if self.release_digests != expected_digests:
            raise ValueError("release digest map does not match resolved selection")
        release_components = tuple(
            sorted(
                (component for release in releases for component in release.components),
                key=lambda item: item.ref,
            )
        )
        release_component_refs = [component.ref for component in release_components]
        if len(release_component_refs) != len(set(release_component_refs)):
            raise ValueError("resolved releases contain duplicate components")
        if self.components != release_components:
            raise ValueError(
                "combined release components must exactly match resolved releases"
            )
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


class LLMModelSettings(ScienceModel):
    """Persist only reviewed, non-secret generation controls."""

    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, gt=0)
    seed: int | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    context_length: int | None = Field(default=None, ge=2048, le=1_048_576)

    @field_validator("temperature", "top_p", "timeout_seconds", mode="before")
    @classmethod
    def finite_float_setting(cls, value):
        if value is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("model setting must be a finite number") from exc
            if not isfinite(numeric):
                raise ValueError("model setting must be finite")
        return value


InterpretationIssueCode: TypeAlias = Literal[
    "USER_CONFIRMATION_REQUIRED",
    "ONTOLOGY_REFS_REQUIRED",
    "UNKNOWN_ONTOLOGY_REF",
    "ONTOLOGY_REF_MISMATCH",
    "SUBJECT_BINDING_REQUIRED",
    "RELATION_BINDING_REQUIRED",
    "OBJECT_BINDING_REQUIRED",
    "BINDING_CONCEPT_MISMATCH",
    "ALIAS_BINDING_MISMATCH",
    "COMPLETE_RELATION_SPAN_REQUIRED",
    "EXTERNAL_CONTEXT_REQUIRES_USER_REVISION",
    "FORMULA_OUTSIDE_CLAIM_SPAN",
    "FORMULA_SPAN_OVERLAP",
    "FORMULA_SYMBOL_INCOMPLETE",
    "FORMULA_SYMBOL_OVERLAP",
    "FORMULA_UNDECLARED_VARIABLE",
    "FORMULA_ONTOLOGY_MISMATCH",
    "FORMULA_SYMBOL_AMBIGUITY",
    "FORMULA_CONTEXT_REQUIRES_USER_REVISION",
    "UNKNOWN_EQUATION_REF",
    "EQUATION_IDENTITY_MISMATCH",
    "FORMULA_SEMANTIC_MISMATCH",
]

FormulaInterpretationIssueCode: TypeAlias = Literal[
    "FORMULA_OUTSIDE_CLAIM_SPAN",
    "FORMULA_SPAN_OVERLAP",
    "FORMULA_SYMBOL_INCOMPLETE",
    "FORMULA_SYMBOL_OVERLAP",
    "FORMULA_UNDECLARED_VARIABLE",
    "FORMULA_ONTOLOGY_MISMATCH",
    "FORMULA_SYMBOL_AMBIGUITY",
    "FORMULA_CONTEXT_REQUIRES_USER_REVISION",
    "UNKNOWN_EQUATION_REF",
    "EQUATION_IDENTITY_MISMATCH",
    "FORMULA_SEMANTIC_MISMATCH",
]


class CandidateMeaningRecord(ScienceModel):
    claim_id: str = Field(min_length=1)
    ambiguity_id: str | None = None
    concept_role: Literal["subject", "relation", "object"]
    surface_term: str = Field(min_length=1)
    ontology_ref: str = Field(min_length=1)
    binding_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    concept_id: str | None = None
    meaning: str | None = None
    domain: str | None = None


class FormulaSymbolInterpretationRecord(ScienceModel):
    """Server-normalized but still non-authoritative symbol proposal."""

    variable_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
    symbol: str = Field(min_length=1, max_length=32)
    source_span: SourceSpan
    concept_ref: str = Field(pattern=r"^sci:concept:[A-Za-z0-9._:-]+$")
    quantity_kind: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    unit: str | None = Field(default=None, max_length=128)
    ontology_ref: str = Field(pattern=r"^sci:binding:[A-Za-z0-9._:-]+$")
    binding_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_variable_match: bool | None = None

    @field_validator("unit")
    @classmethod
    def canonical_candidate_unit(cls, value: str | None) -> str | None:
        return canonical_science_unit_token(value) if value is not None else None


class FormulaInterpretationRecord(ScienceModel):
    """Safe UI proposal record that can never carry verdict authority."""

    claim_id: str = Field(min_length=1)
    formula_span: SourceSpan
    semantic_expression: SemanticExpression
    semantic_expression_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    proposed_equation_id: str | None = Field(
        default=None, pattern=r"^sci:equation:[A-Za-z0-9._:-]+$"
    )
    proposed_equation_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    catalog_match_status: Literal[
        "not_proposed",
        "unknown_equation",
        "mismatch",
        "exact_candidate_match",
    ]
    symbol_candidates: list[FormulaSymbolInterpretationRecord] = Field(
        min_length=1, max_length=64
    )
    condition_candidates: list[ClaimCondition] = Field(
        default_factory=list, max_length=64
    )
    sign_convention_candidate: str | None = Field(default=None, max_length=2048)
    ontology_refs: list[str] = Field(default_factory=list, max_length=64)
    issue_codes: list[FormulaInterpretationIssueCode] = Field(default_factory=list)
    verdict_authority: Literal[False] = False
    candidate_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_non_authoritative_record(self) -> "FormulaInterpretationRecord":
        semantic_payload = self.semantic_expression.model_dump(
            mode="json", exclude_none=True
        )
        if self.semantic_expression_digest != sha256_digest(semantic_payload):
            raise ValueError("formula semantic expression digest is not exact")
        if (self.proposed_equation_id is None) != (
            self.proposed_equation_digest is None
        ):
            raise ValueError("formula Equation proposal must be an exact identity pair")
        if self.catalog_match_status == "not_proposed" and (
            self.proposed_equation_id is not None
            or self.proposed_equation_digest is not None
        ):
            raise ValueError("not_proposed cannot contain an Equation identity")
        if self.catalog_match_status != "not_proposed" and (
            self.proposed_equation_id is None
            or self.proposed_equation_digest is None
        ):
            raise ValueError("Equation match status requires a proposed identity")
        if len(self.ontology_refs) != len(set(self.ontology_refs)):
            raise ValueError("formula interpretation ontology refs must be unique")
        if len(self.issue_codes) != len(set(self.issue_codes)):
            raise ValueError("formula interpretation issue codes must be unique")
        digest_payload = self.model_dump(
            mode="json", exclude={"candidate_digest"}, exclude_none=False
        )
        if self.candidate_digest != sha256_digest(digest_payload):
            raise ValueError("formula candidate digest is not exact")
        return self


class DetectedAlias(ScienceModel):
    binding_id: str = Field(min_length=1)
    ontology_ref: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    surface_term: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    meaning: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    binding_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_span_and_binding(self) -> "DetectedAlias":
        if self.binding_id != self.ontology_ref:
            raise ValueError("detected alias binding identities must match")
        if self.end - self.start != len(self.surface_term):
            raise ValueError("detected alias span must match its exact surface term")
        return self


class AliasDetectionResult(ScienceModel):
    document_ref: str = Field(min_length=1)
    document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    matches: list[DetectedAlias]


class InterpretationDecisionImpact(ScienceModel):
    claim_id: str = Field(min_length=1)
    outcome_impact: Literal["unresolved"] = "unresolved"
    status: Literal["requires_user_confirmation", "blocked_semantic_mismatch"]
    issue_codes: list[InterpretationIssueCode] = Field(min_length=1)

    @field_validator("issue_codes")
    @classmethod
    def unique_issue_codes(cls, value: list[InterpretationIssueCode]):
        if len(value) != len(set(value)):
            raise ValueError("interpretation issue codes must be unique")
        return value


class InterpretationRevisionEvent(ScienceModel):
    action: Literal["claim_confirmed"]
    actor_id: str = Field(min_length=1)
    source_interpretation_id: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    occurred_at: datetime

    @field_validator("claim_ids")
    @classmethod
    def unique_claim_ids(cls, value: list[str]):
        if len(value) != len(set(value)):
            raise ValueError("revision claim IDs must be unique")
        return value


class ScienceOperationBinding(ScienceModel):
    operation: Literal[
        "interpret_document",
        "submit_claim_candidate",
        "confirm_interpretation",
        "verify_document",
    ]
    idempotency_key_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    actor_id: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    release_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    prompt_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_interpretation_id: str | None
    claim_ids: list[str]

    @model_validator(mode="after")
    def exact_operation_shape(self) -> "ScienceOperationBinding":
        if len(self.claim_ids) != len(set(self.claim_ids)):
            raise ValueError("operation claim IDs must be unique")
        if self.claim_ids != sorted(self.claim_ids):
            raise ValueError("operation claim IDs must be canonical")
        if self.operation in {"interpret_document", "submit_claim_candidate"}:
            if (
                self.source_interpretation_id is not None
                or self.release_digest is not None
            ):
                raise ValueError("interpret operation cannot claim a source or release")
        elif self.source_interpretation_id is None:
            raise ValueError(
                "authoritative operation requires an interpretation dependency"
            )
        return self


def _confirmed_packet_digest(claims: list[ClaimPacket]) -> str | None:
    if not claims:
        return None
    if len(claims) == 1:
        return sha256_digest(claims[0])
    return sha256_digest({"claim_packets": claims})


class InterpretationRecord(ScienceModel):
    interpretation_id: str
    document_digest: str
    candidate_claims: list[ClaimPacket]
    model_id: str
    model_settings: LLMModelSettings
    prompt_version: str
    dictionary_release_id: str
    ontology_release_id: str
    ontology_refs: list[str]
    candidate_meanings: list[CandidateMeaningRecord]
    formula_candidates: list[FormulaInterpretationRecord] = Field(default_factory=list)
    decision_impact: list[InterpretationDecisionImpact]
    user_revision_history: list[InterpretationRevisionEvent]
    confirmed_claim_packet_digest: str | None
    response_digest: str
    operation_binding: ScienceOperationBinding
    submission_client_kind: ClaimSubmissionClientKind | None = None
    supersedes_claim_id: str | None = Field(default=None, min_length=1)
    canonical_source_document_ref: str | None = Field(default=None, min_length=1)
    canonical_source_document_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )

    @field_validator("model_id")
    @classmethod
    def safe_model_id(cls, value: str) -> str:
        return validate_model_identifier(value)

    @model_validator(mode="after")
    def safe_non_source_provenance(self) -> "InterpretationRecord":
        payload = self.model_dump(mode="json", exclude_none=False)
        for claim in payload["candidate_claims"]:
            claim.pop("source_span", None)
        for meaning in payload["candidate_meanings"]:
            meaning.pop("surface_term", None)
        for formula in payload["formula_candidates"]:
            formula.pop("formula_span", None)
            for symbol in formula["symbol_candidates"]:
                symbol.pop("source_span", None)
                symbol.pop("symbol", None)
        reject_sensitive_persistence(payload, path="interpretation")
        claim_ids = [claim.claim_id for claim in self.candidate_claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("interpretation claim IDs must be unique")
        if {meaning.claim_id for meaning in self.candidate_meanings} - set(claim_ids):
            raise ValueError("candidate meaning references an unknown claim")
        if {formula.claim_id for formula in self.formula_candidates} - set(claim_ids):
            raise ValueError("formula candidate references an unknown claim")
        formula_identities = [
            (
                formula.claim_id,
                formula.formula_span.start,
                formula.formula_span.end,
                formula.semantic_expression_digest,
            )
            for formula in self.formula_candidates
        ]
        if len(formula_identities) != len(set(formula_identities)) and not any(
            "FORMULA_SPAN_OVERLAP" in formula.issue_codes
            for formula in self.formula_candidates
        ):
            raise ValueError("duplicate formula candidates require an overlap issue")
        if {impact.claim_id for impact in self.decision_impact} != set(claim_ids):
            raise ValueError("decision impact must cover every candidate claim")
        canonical_ref = self.canonical_source_document_ref
        canonical_digest = self.canonical_source_document_digest
        if (canonical_ref is None) != (canonical_digest is None):
            raise ValueError("canonical source lineage must be an exact ref/digest pair")
        if canonical_ref is not None:
            if not canonical_ref.startswith("boi:") or canonical_ref.startswith(
                "boi:submitted:"
            ):
                raise ValueError("canonical source lineage must reference a Wiki document")
            if self.supersedes_claim_id is None or any(
                not claim.document_ref.startswith("boi:submitted:")
                for claim in self.candidate_claims
            ):
                raise ValueError(
                    "canonical source lineage is only valid for a submitted revision"
                )
        expected_refs = sorted(
            {
                ref
                for claim in self.candidate_claims
                for ref in claim.interpretation.ontology_refs
            }
        )
        if self.ontology_refs != expected_refs:
            raise ValueError("interpretation ontology refs do not match its claims")
        confirmed = [
            claim
            for claim in self.candidate_claims
            if claim.interpretation.user_confirmed
            and not claim.interpretation.ambiguity_ids
        ]
        if self.confirmed_claim_packet_digest != _confirmed_packet_digest(confirmed):
            raise ValueError("confirmed Claim Packet digest does not match its claims")
        binding = self.operation_binding
        if binding.document_digest != self.document_digest:
            raise ValueError("operation document digest does not match interpretation")
        if binding.operation in {"interpret_document", "submit_claim_candidate"}:
            expected_claim_digest = sha256_digest(
                {"claim_packets": self.candidate_claims}
            )
            if binding.claim_digest != expected_claim_digest:
                raise ValueError("operation claim digest does not match proposals")
            if binding.claim_ids != sorted(claim_ids):
                raise ValueError("proposal operation claim IDs are inconsistent")
            if confirmed or self.confirmed_claim_packet_digest is not None:
                raise ValueError("proposal operation cannot contain confirmed claims")
            if self.user_revision_history:
                raise ValueError("proposal operation cannot contain user revisions")
            if binding.operation == "interpret_document" and (
                self.submission_client_kind is not None
                or self.supersedes_claim_id is not None
            ):
                raise ValueError("LLM interpretation cannot claim external submission")
            if (
                binding.operation == "submit_claim_candidate"
                and self.submission_client_kind is None
            ):
                raise ValueError("external submission requires a client kind")
        elif binding.operation == "confirm_interpretation":
            confirmed_ids = sorted(claim.claim_id for claim in confirmed)
            if binding.claim_digest != self.confirmed_claim_packet_digest:
                raise ValueError("operation claim digest does not match confirmation")
            if binding.claim_ids != confirmed_ids:
                raise ValueError("confirmation binding does not match confirmed claims")
            if len(self.user_revision_history) != 1:
                raise ValueError("confirmation requires exactly one explicit revision")
            revision = self.user_revision_history[0]
            if (
                revision.actor_id != binding.actor_id
                or revision.source_interpretation_id != binding.source_interpretation_id
                or revision.claim_ids != binding.claim_ids
            ):
                raise ValueError("confirmation revision is not exactly identity-bound")
        else:
            raise ValueError("report operation cannot bind an interpretation")
        return self


class SourceLookupIdentity(ScienceModel):
    source_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    boi_id: str = Field(min_length=1)
    versioned_path: str = Field(min_length=1)
    visibility: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    acl_policy: str = Field(min_length=1)
    lookup_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_lookup_digest(self) -> "SourceLookupIdentity":
        expected = sha256_digest(
            self.model_dump(mode="json", exclude={"lookup_digest"})
        )
        if self.lookup_digest != expected:
            raise ValueError("source lookup digest does not match its exact identity")
        return self


class EvidenceLocator(ScienceModel):
    medium: str | None = None
    resource_url: str | None = None
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    section: str | None = None
    equation: str | None = None
    retrieved_at: str | None = None
    exact: bool | None = None
    requested_url: str | None = None
    resolved_url: str | None = None
    preservation_status: str | None = None
    pdf_page_index: int | None = Field(default=None, ge=0)
    printed_page: str | None = None
    hash_scope: str | None = None
    heading: str | None = None
    sentence_ordinal: int | None = Field(default=None, ge=0)
    prefix: str | None = None
    suffix: str | None = None
    retrieved_resource_hash: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    sentence_label: str | None = None
    field_path: str | None = None
    figure: str | None = None
    record_path: str | None = None
    transcription_method: str | None = None
    visual_transcription_scope: str | None = None

    @field_validator("resource_url", "requested_url", "resolved_url")
    @classmethod
    def credential_free_url(cls, value: str | None) -> str | None:
        return validate_credential_free_https_url(value) if value is not None else None

    @model_validator(mode="after")
    def recursively_non_secret(self) -> "EvidenceLocator":
        payload = self.model_dump(mode="json", exclude_none=True)
        for field_name in ("resource_url", "requested_url", "resolved_url"):
            payload.pop(field_name, None)
        reject_sensitive_persistence(payload, path="evidence_locator")
        if not payload and not any(
            (self.resource_url, self.requested_url, self.resolved_url)
        ):
            raise ValueError("Evidence locator must contain a reviewed location")
        return self


class ReviewedSourceURLProfile(ScienceModel):
    schema_version: Literal["science-reviewed-source-url/0.1"] = (
        "science-reviewed-source-url/0.1"
    )
    qualification_state: Literal["candidate", "active"]
    release_set_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_id: str = Field(min_length=1)
    evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    canonical_source_url: str = Field(min_length=1)
    canonical_source_url_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locator: EvidenceLocator
    locator_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    locator_url_digests: dict[str, str]
    profile_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("canonical_source_url")
    @classmethod
    def canonical_public_source_url(cls, value: str) -> str:
        return validate_credential_free_https_url(value)

    @model_validator(mode="after")
    def exact_qualification_digests(self) -> "ReviewedSourceURLProfile":
        if self.canonical_source_url_digest != sha256_digest(self.canonical_source_url):
            raise ValueError("reviewed Source URL digest is not exact")
        if self.locator_digest != sha256_digest(self.locator):
            raise ValueError("reviewed Evidence locator digest is not exact")
        expected_url_digests = {
            field_name: sha256_digest(value)
            for field_name in ("resource_url", "requested_url", "resolved_url")
            if (value := getattr(self.locator, field_name)) is not None
        }
        if self.locator_url_digests != expected_url_digests:
            raise ValueError("reviewed Evidence locator URL digests are not exact")
        expected_profile_digest = sha256_digest(
            self.model_dump(mode="json", exclude={"profile_digest"})
        )
        if self.profile_digest != expected_profile_digest:
            raise ValueError("reviewed Source URL profile digest is not exact")
        return self


class EvidenceLink(ScienceModel):
    evidence_id: str = Field(min_length=1)
    evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    original_text_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    quote_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    url: str = Field(min_length=1)
    locator: EvidenceLocator
    source_lookup: SourceLookupIdentity
    reviewed_source: ReviewedSourceURLProfile

    @field_validator("url")
    @classmethod
    def credential_free_source_url(cls, value: str) -> str:
        return validate_credential_free_https_url(value)

    @model_validator(mode="after")
    def exact_quote_and_source_identity(self) -> "EvidenceLink":
        if self.quote_hash != self.original_text_hash:
            raise ValueError("Evidence quote hash must match original_text_hash")
        if (
            self.source_lookup.source_id != self.source_id
            or self.source_lookup.source_digest != self.source_digest
        ):
            raise ValueError("Evidence Source lookup identity does not match its link")
        reviewed = self.reviewed_source
        if reviewed.qualification_state != "active":
            raise ValueError("Evidence link requires an active reviewed Source URL")
        if (
            reviewed.source_id != self.source_id
            or reviewed.source_digest != self.source_digest
            or reviewed.evidence_id != self.evidence_id
            or reviewed.evidence_digest != self.evidence_digest
            or reviewed.canonical_source_url != self.url
            or reviewed.locator != self.locator
        ):
            raise ValueError(
                "Evidence link does not match its reviewed Source identity"
            )
        return self


class GroundedAnnotation(ScienceModel):
    claim_id: str = Field(min_length=1)
    fact_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    knowledge_id: str = Field(min_length=1)
    knowledge_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_links: list[EvidenceLink] = Field(min_length=1)


class VerificationReport(ScienceModel):
    report_id: str
    document_ref: str | None
    document_digest: str
    release_selection: ReleaseSelection
    release_digests: dict[str, str]
    interpretation_ids: list[str] = Field(min_length=1)
    confirmed_claims: list[ClaimPacket] = Field(min_length=1)
    verdict_packets: list[VerdictPacket] = Field(min_length=1)
    unresolved_ambiguities: list[InterpretationDecisionImpact]
    annotations: list[GroundedAnnotation]
    created_at: datetime
    created_by: str
    report_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    operation_binding: ScienceOperationBinding

    @model_validator(mode="after")
    def safe_non_source_provenance(self) -> "VerificationReport":
        payload = self.model_dump(mode="json", exclude_none=False)
        for claim in payload["confirmed_claims"]:
            claim.pop("source_span", None)
        for verdict in payload["verdict_packets"]:
            verdict.pop("corrected_claim", None)
            verdict.pop("limitations", None)
        for annotation in payload["annotations"]:
            annotation.pop("text", None)
            for link in annotation["evidence_links"]:
                link.pop("url", None)
                for locator in (
                    link["locator"],
                    link["reviewed_source"]["locator"],
                ):
                    for field_name in (
                        "resource_url",
                        "requested_url",
                        "resolved_url",
                    ):
                        locator.pop(field_name, None)
                link["reviewed_source"].pop("canonical_source_url", None)
                link["reviewed_source"].pop("locator_url_digests", None)
        reject_sensitive_persistence(payload, path="report")
        binding = self.operation_binding
        if binding.operation != "verify_document":
            raise ValueError("report requires a verify_document operation binding")
        if binding.actor_id != self.created_by:
            raise ValueError("report actor does not match its operation binding")
        if binding.document_digest != self.document_digest:
            raise ValueError("report document digest does not match its operation")
        if len(self.interpretation_ids) != 1:
            raise ValueError("report requires one exact interpretation identity")
        if binding.source_interpretation_id != self.interpretation_ids[0]:
            raise ValueError("report dependency does not match its interpretation")
        if self.unresolved_ambiguities:
            raise ValueError("authoritative report cannot contain unresolved claims")
        if any(
            not claim.interpretation.user_confirmed
            or claim.interpretation.ambiguity_ids
            for claim in self.confirmed_claims
        ):
            raise ValueError("report contains an unconfirmed claim")
        claim_digest = _confirmed_packet_digest(self.confirmed_claims)
        claim_ids = sorted(claim.claim_id for claim in self.confirmed_claims)
        if binding.claim_digest != claim_digest or binding.claim_ids != claim_ids:
            raise ValueError("report operation claim identity is inconsistent")
        if binding.release_digest != sha256_digest(self.release_selection):
            raise ValueError("report operation release digest is inconsistent")
        expected_release_ids = {
            self.release_selection.foundation,
            *self.release_selection.domains,
            *self.release_selection.applications,
        }
        if set(self.release_digests) != expected_release_ids or any(
            not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            for digest in self.release_digests.values()
        ):
            raise ValueError("report release digest map is not exact")
        expected_request_digest = sha256_digest(
            {
                "operation": "verify_document",
                "interpretation_id": self.interpretation_ids[0],
                "claim_digest": claim_digest,
                "release_selection": self.release_selection,
            }
        )
        if binding.request_digest != expected_request_digest:
            raise ValueError("report operation request digest is inconsistent")
        verdict_ids = [verdict.claim_id for verdict in self.verdict_packets]
        if len(verdict_ids) != len(set(verdict_ids)) or set(verdict_ids) != set(
            claim_ids
        ):
            raise ValueError("report verdicts do not cover exact confirmed claims")
        claims_by_id = {claim.claim_id: claim for claim in self.confirmed_claims}
        for verdict in self.verdict_packets:
            claim = claims_by_id[verdict.claim_id]
            if verdict.claim_packet_digest != sha256_digest(claim):
                raise ValueError("report verdict Claim Packet digest is inconsistent")
            if (
                verdict.releases.selection != self.release_selection
                or verdict.releases.digests != self.release_digests
            ):
                raise ValueError("report verdict release linkage is inconsistent")
        if any(
            claim.document_digest != self.document_digest
            or claim.document_ref != self.document_ref
            for claim in self.confirmed_claims
        ):
            raise ValueError("report claims do not match its document")
        if any(
            annotation.claim_id not in set(claim_ids) for annotation in self.annotations
        ):
            raise ValueError("report annotation references an unknown claim")
        expected_facts: dict[tuple[str, str], ExplanationFact] = {}
        for verdict in self.verdict_packets:
            fact_ids = [fact.fact_id for fact in verdict.explanation_facts]
            if len(fact_ids) != len(set(fact_ids)):
                raise ValueError("report verdict has duplicate explanation facts")
            fact_knowledge = {
                ref for fact in verdict.explanation_facts for ref in fact.knowledge_refs
            }
            fact_evidence = {
                ref for fact in verdict.explanation_facts for ref in fact.evidence_refs
            }
            if (
                set(verdict.knowledge_refs) != fact_knowledge
                or set(verdict.evidence_refs) != fact_evidence
            ):
                raise ValueError(
                    "report verdict references do not match its explanation facts"
                )
            for fact in verdict.explanation_facts:
                key = (verdict.claim_id, fact.fact_id)
                if key in expected_facts:
                    raise ValueError("report has duplicate explanation fact identities")
                expected_facts[key] = fact

        annotations_by_fact: dict[tuple[str, str], list[GroundedAnnotation]] = {}
        annotation_identities: set[tuple[str, str, str]] = set()
        for annotation in self.annotations:
            key = (annotation.claim_id, annotation.fact_id)
            annotations_by_fact.setdefault(key, []).append(annotation)
            identity = (*key, annotation.knowledge_id)
            if identity in annotation_identities:
                raise ValueError("report duplicates a grounded explanation fact")
            annotation_identities.add(identity)
            evidence_ids = [link.evidence_id for link in annotation.evidence_links]
            if len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError("report duplicates Evidence in an explanation fact")

        if set(annotations_by_fact) != set(expected_facts):
            raise ValueError(
                "report annotations do not exactly cover verdict explanation facts"
            )
        for key, fact in expected_facts.items():
            annotations = annotations_by_fact[key]
            if {item.knowledge_id for item in annotations} != set(
                fact.knowledge_refs
            ) or {
                link.evidence_id for item in annotations for link in item.evidence_links
            } != set(fact.evidence_refs):
                raise ValueError(
                    "report grounding does not match its verdict explanation fact"
                )
        verdict_release_set_digests = {
            verdict.releases.combined_digest for verdict in self.verdict_packets
        }
        if len(verdict_release_set_digests) != 1:
            raise ValueError("report verdicts do not share one release-set digest")
        release_set_digest = next(iter(verdict_release_set_digests))
        if any(
            link.reviewed_source.release_set_digest != release_set_digest
            for annotation in self.annotations
            for link in annotation.evidence_links
        ):
            raise ValueError("report Evidence profile does not match its release set")
        expected_report_digest = sha256_digest(
            self.model_dump(mode="json", exclude={"report_digest"})
        )
        if self.report_digest != expected_report_digest:
            raise ValueError("report digest does not match immutable report bytes")
        return self
