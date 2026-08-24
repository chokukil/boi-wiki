"""Closed, deterministic evaluators for reviewed scientific rule objects."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Literal, TypeAlias

import pint
from pydantic import Field, model_validator

from boi_api.app.science.models import (
    ConditionEvaluation,
    NormalizedClaim,
    RelationKind,
    RuleEvaluation,
    RuleKind,
    ScienceModel,
)
from boi_api.app.science.units import (
    IncompatibleDimensionsError,
    _pint_quantity,
    expected_dimensionality,
    validate_quantity,
)


ConditionValue: TypeAlias = str | int | float | bool | None


class EquationConstraint(ScienceModel):
    """One of the small, auditable equation forms accepted by the engine."""

    left_quantity_kind: str
    right_quantity_kinds: list[str] = Field(min_length=1, max_length=2)
    operator: Literal["equal", "product", "quotient"] = "equal"
    relative_tolerance: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def valid_arity(self) -> "EquationConstraint":
        expected = 1 if self.operator == "equal" else 2
        if len(self.right_quantity_kinds) != expected:
            raise ValueError(f"{self.operator} requires {expected} right quantities")
        return self


class QualifiedObservation(ScienceModel):
    """A reviewed measurement record considered by an empirical rule."""

    observation_id: str
    rule_id: str
    verified: bool
    measurement_ref: str
    evidence_ref: str


class VerificationRule(ScienceModel):
    """A validated rule description; it contains data, never executable code."""

    rule_id: str
    rule_kind: RuleKind
    subject_concept_id: str
    object_concept_id: str
    relation_kind: RelationKind | None = None
    expected_predicate: str | None = None
    expected_polarity: Literal["positive", "negative"] = "positive"
    required_conditions: dict[str, ConditionValue] = Field(default_factory=dict)
    validity_conditions: dict[str, ConditionValue] = Field(default_factory=dict)
    expected_dimensions: dict[str, str] = Field(default_factory=dict)
    equation: EquationConstraint | None = None
    knowledge_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    corrected_claim: str | None = None

    @model_validator(mode="after")
    def has_kind_specific_constraint(self) -> "VerificationRule":
        if (
            self.rule_kind is not RuleKind.DIRECTIONAL_RELATION
            and "expected_polarity" in self.model_fields_set
        ):
            raise ValueError(f"rule kind payload invalid for {self.rule_kind.value}")
        if (
            self.rule_kind in {RuleKind.VALIDITY_DOMAIN, RuleKind.EMPIRICAL_BOUNDARY}
            and self.corrected_claim is not None
        ):
            raise ValueError(f"rule kind payload invalid for {self.rule_kind.value}")
        if self.rule_kind is RuleKind.DIRECTIONAL_RELATION:
            if self.expected_predicate is None or self.equation is not None or self.expected_dimensions:
                raise ValueError("rule kind payload invalid for directional_relation")
        elif self.rule_kind is RuleKind.EQUATION_CONSTRAINT:
            if self.equation is None or self.expected_predicate is not None or self.expected_dimensions:
                raise ValueError("rule kind payload invalid for equation_constraint")
        elif self.rule_kind is RuleKind.DIMENSION_CONSTRAINT:
            if not self.expected_dimensions or self.expected_predicate is not None or self.equation is not None:
                raise ValueError("rule kind payload invalid for dimension_constraint")
        else:
            if self.expected_predicate is not None or self.equation is not None or self.expected_dimensions:
                raise ValueError(f"rule kind payload invalid for {self.rule_kind.value}")
        if self.rule_kind is RuleKind.VALIDITY_DOMAIN and not self.validity_conditions:
            raise ValueError("rule kind payload invalid for validity_domain")
        return self


class ReleasedRule(ScienceModel):
    """A typed rule payload bound to its OKF and semantic digests."""

    rule: VerificationRule
    component_digest: str
    semantic_digest: str


class ResolvedRuleSet(ScienceModel):
    """The complete set of typed rules resolved for one immutable Release."""

    release_id: str
    rules: tuple[ReleasedRule, ...]

    @model_validator(mode="after")
    def unique_rule_ids(self) -> "ResolvedRuleSet":
        rule_ids = [released.rule.rule_id for released in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate rule ID in resolved rule set")
        return self


class DetailedRuleEvaluation(RuleEvaluation):
    """RuleEvaluation with the matched concepts needed for an audit trail."""

    matched_concept_ids: list[str]


RuleEvaluator: TypeAlias = Callable[
    [VerificationRule, NormalizedClaim, tuple[QualifiedObservation, ...]],
    DetailedRuleEvaluation,
]


def _claim_values(claim: NormalizedClaim) -> dict[str, ConditionValue]:
    values = {condition.condition_id: condition.value for condition in claim.conditions}
    values["process_stage"] = claim.process_stage
    values["material_state"] = claim.material_state
    return values


def _concept_match(rule: VerificationRule, claim: NormalizedClaim) -> bool:
    return (
        rule.subject_concept_id == claim.subject_concept_id
        and rule.object_concept_id == claim.object_concept_id
        and (rule.relation_kind is None or rule.relation_kind is claim.relation_kind)
    )


def _condition_evaluations(
    expected: dict[str, ConditionValue], claim: NormalizedClaim
) -> list[ConditionEvaluation]:
    actual = _claim_values(claim)
    return [
        ConditionEvaluation(
            condition_id=condition_id,
            expected=expected_value,
            actual=actual.get(condition_id),
            satisfied=condition_id in actual
            and actual[condition_id] is not None
            and actual[condition_id] == expected_value,
        )
        for condition_id, expected_value in sorted(expected.items())
    ]


def _base_evaluation(
    rule: VerificationRule,
    claim: NormalizedClaim,
    *,
    applicability: Literal[
        "IN_SCOPE", "MISSING_CONDITIONS", "OUTSIDE_DOMAIN", "EMPIRICAL_ONLY", "NOT_APPLICABLE"
    ],
    outcome: Literal["CONTRADICTS", "SUPPORTS", "UNDECIDED"],
    reason_codes: list[str],
    conditions: list[ConditionEvaluation] | None = None,
) -> DetailedRuleEvaluation:
    matched = (
        sorted({claim.subject_concept_id, claim.object_concept_id})
        if rule.subject_concept_id == claim.subject_concept_id
        and rule.object_concept_id == claim.object_concept_id
        else []
    )
    return DetailedRuleEvaluation(
        rule_id=rule.rule_id,
        matched_concept_ids=matched,
        applicability=applicability,
        outcome=outcome,
        reason_codes=reason_codes,
        condition_evaluations=conditions or [],
        knowledge_refs=sorted(set(rule.knowledge_refs)),
        evidence_refs=sorted(set(rule.evidence_refs)),
    )


def _applicability_gate(
    rule: VerificationRule, claim: NormalizedClaim
) -> DetailedRuleEvaluation | tuple[list[ConditionEvaluation], list[ConditionEvaluation]]:
    if not _concept_match(rule, claim):
        return _base_evaluation(
            rule,
            claim,
            applicability="NOT_APPLICABLE",
            outcome="UNDECIDED",
            reason_codes=["CONCEPTS_NOT_MATCHED"],
        )
    required = _condition_evaluations(rule.required_conditions, claim)
    if any(not item.satisfied for item in required):
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["MISSING_REQUIRED_CONDITIONS"],
            conditions=required,
        )
    validity = _condition_evaluations(rule.validity_conditions, claim)
    if any(item.actual is None for item in validity):
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["MISSING_VALIDITY_CONDITIONS"],
            conditions=required + validity,
        )
    if any(not item.satisfied for item in validity):
        return _base_evaluation(
            rule,
            claim,
            applicability="OUTSIDE_DOMAIN",
            outcome="UNDECIDED",
            reason_codes=["VALIDITY_DOMAIN_MISMATCH"],
            conditions=required + validity,
        )
    return required, validity


def _predicate_evaluation(
    rule: VerificationRule, claim: NormalizedClaim
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    matches = (
        claim.predicate == rule.expected_predicate
        and claim.polarity == rule.expected_polarity
    )
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome="SUPPORTS" if matches else "CONTRADICTS",
        reason_codes=["RULE_SUPPORTS" if matches else "RULE_CONTRADICTS"],
        conditions=required + validity,
    )


def evaluate_directional_relation(
    rule: VerificationRule,
    claim: NormalizedClaim,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    return _predicate_evaluation(rule, claim)


def _equation_outcome(rule: VerificationRule, claim: NormalizedClaim) -> bool | None:
    equation = rule.equation
    if equation is None:
        return None
    quantities = {quantity.quantity_kind: quantity for quantity in claim.quantities}
    kinds = [equation.left_quantity_kind, *equation.right_quantity_kinds]
    if any(kind not in quantities for kind in kinds):
        return None
    left = _pint_quantity(quantities[equation.left_quantity_kind])
    right_items = [_pint_quantity(quantities[kind]) for kind in equation.right_quantity_kinds]
    if equation.operator == "equal":
        right = right_items[0]
    elif equation.operator == "product":
        right = right_items[0] * right_items[1]
    else:
        right = right_items[0] / right_items[1]
    try:
        right = right.to(left.units)
    except pint.DimensionalityError as exc:
        raise IncompatibleDimensionsError(
            f"incompatible equation dimensions: {right.dimensionality} and {left.dimensionality}"
        ) from exc
    left_value = Decimal(str(left.magnitude))
    right_value = Decimal(str(right.magnitude))
    scale = max(abs(right_value), Decimal(1))
    return abs(left_value - right_value) <= equation.relative_tolerance * scale


def evaluate_equation_constraint(
    rule: VerificationRule,
    claim: NormalizedClaim,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    outcome = _equation_outcome(rule, claim)
    if outcome is None:
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["MISSING_EQUATION_QUANTITIES"],
            conditions=required + validity,
        )
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome="SUPPORTS" if outcome else "CONTRADICTS",
        reason_codes=["EQUATION_SATISFIED" if outcome else "EQUATION_CONTRADICTION"],
        conditions=required + validity,
    )


def evaluate_dimension_constraint(
    rule: VerificationRule,
    claim: NormalizedClaim,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    quantities = {quantity.quantity_kind: quantity for quantity in claim.quantities}
    if any(kind not in quantities for kind in rule.expected_dimensions):
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["MISSING_DIMENSION_QUANTITIES"],
            conditions=required + validity,
        )
    matches = all(
        validate_quantity(quantities[kind]).dimensionality == expected_dimensionality(unit)
        for kind, unit in sorted(rule.expected_dimensions.items())
    )
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome="SUPPORTS" if matches else "CONTRADICTS",
        reason_codes=["DIMENSION_MATCH" if matches else "DIMENSION_MISMATCH"],
        conditions=required + validity,
    )


def evaluate_validity_domain(
    rule: VerificationRule,
    claim: NormalizedClaim,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome="SUPPORTS",
        reason_codes=["VALIDITY_DOMAIN_MATCH"],
        conditions=required + validity,
    )


def evaluate_empirical_boundary(
    rule: VerificationRule,
    claim: NormalizedClaim,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    qualified = any(
        observation.rule_id == rule.rule_id and observation.verified
        for observation in qualified_observations
    )
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE" if qualified else "EMPIRICAL_ONLY",
        outcome="SUPPORTS" if qualified else "UNDECIDED",
        reason_codes=[
            "QUALIFIED_OBSERVATION_PRESENT" if qualified else "QUALIFIED_OBSERVATION_REQUIRED"
        ],
        conditions=required + validity,
    )


RULE_EVALUATORS: dict[RuleKind, RuleEvaluator] = {
    RuleKind.DIRECTIONAL_RELATION: evaluate_directional_relation,
    RuleKind.EQUATION_CONSTRAINT: evaluate_equation_constraint,
    RuleKind.DIMENSION_CONSTRAINT: evaluate_dimension_constraint,
    RuleKind.VALIDITY_DOMAIN: evaluate_validity_domain,
    RuleKind.EMPIRICAL_BOUNDARY: evaluate_empirical_boundary,
}


def evaluate_rule(
    rule: VerificationRule,
    claim: NormalizedClaim,
    *,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    """Dispatch one validated rule through the closed evaluator allowlist."""

    try:
        evaluator = RULE_EVALUATORS[rule.rule_kind]
    except KeyError as exc:  # Defensive boundary if an invalid object bypasses Pydantic.
        raise ValueError(f"unsupported rule kind: {rule.rule_kind}") from exc
    return evaluator(rule, claim, qualified_observations)
