from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScienceModel(BaseModel):
    """Base model that rejects undeclared packet fields."""

    model_config = ConfigDict(extra="forbid")


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


class ClaimCondition(ScienceModel):
    condition_id: str
    value: str | int | float | bool | None
    unit: str | None = None


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
    expected: str | int | float | bool | None
    actual: str | int | float | bool | None
    satisfied: bool


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


class VerdictPacket(ScienceModel):
    claim_id: str
    claim_packet_digest: str
    verifier_version: str
    releases: ReleaseSelection
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
