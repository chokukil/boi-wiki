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
    observation_condition_id: str | None = None
    knowledge_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    corrected_claim: str | None = None

    @model_validator(mode="after")
    def has_kind_specific_constraint(self) -> "VerificationRule":
        if self.rule_kind in {RuleKind.DIRECTIONAL_RELATION, RuleKind.EQUATION_CONSTRAINT}:
            if self.expected_predicate is None and self.equation is None:
                raise ValueError("directional/equation rule requires a predicate or equation")
        if self.rule_kind is RuleKind.DIMENSION_CONSTRAINT and not self.expected_dimensions:
            raise ValueError("dimension rule requires expected_dimensions")
        if self.rule_kind is RuleKind.VALIDITY_DOMAIN and not self.validity_conditions:
            raise ValueError("validity rule requires validity_conditions")
        return self


class DetailedRuleEvaluation(RuleEvaluation):
    """RuleEvaluation with the matched concepts needed for an audit trail."""

    matched_concept_ids: list[str]


RuleEvaluator: TypeAlias = Callable[[VerificationRule, NormalizedClaim], DetailedRuleEvaluation]


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
    rule: VerificationRule, claim: NormalizedClaim
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
    except pint.DimensionalityError:
        return False
    left_value = Decimal(str(left.magnitude))
    right_value = Decimal(str(right.magnitude))
    scale = max(abs(right_value), Decimal(1))
    return abs(left_value - right_value) <= equation.relative_tolerance * scale


def evaluate_equation_constraint(
    rule: VerificationRule, claim: NormalizedClaim
) -> DetailedRuleEvaluation:
    if rule.expected_predicate is not None:
        return _predicate_evaluation(rule, claim)
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
    rule: VerificationRule, claim: NormalizedClaim
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
    rule: VerificationRule, claim: NormalizedClaim
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
    rule: VerificationRule, claim: NormalizedClaim
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    values = _claim_values(claim)
    observation = (
        values.get(rule.observation_condition_id)
        if rule.observation_condition_id is not None
        else None
    )
    if observation is not True and not (isinstance(observation, str) and bool(observation.strip())):
        return _base_evaluation(
            rule,
            claim,
            applicability="EMPIRICAL_ONLY",
            outcome="UNDECIDED",
            reason_codes=["QUALIFIED_OBSERVATION_REQUIRED"],
            conditions=required + validity,
        )
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome="SUPPORTS",
        reason_codes=["QUALIFIED_OBSERVATION_PRESENT"],
        conditions=required + validity,
    )


RULE_EVALUATORS: dict[RuleKind, RuleEvaluator] = {
    RuleKind.DIRECTIONAL_RELATION: evaluate_directional_relation,
    RuleKind.EQUATION_CONSTRAINT: evaluate_equation_constraint,
    RuleKind.DIMENSION_CONSTRAINT: evaluate_dimension_constraint,
    RuleKind.VALIDITY_DOMAIN: evaluate_validity_domain,
    RuleKind.EMPIRICAL_BOUNDARY: evaluate_empirical_boundary,
}


def evaluate_rule(rule: VerificationRule, claim: NormalizedClaim) -> DetailedRuleEvaluation:
    """Dispatch one validated rule through the closed evaluator allowlist."""

    try:
        evaluator = RULE_EVALUATORS[rule.rule_kind]
    except KeyError as exc:  # Defensive boundary if an invalid object bypasses Pydantic.
        raise ValueError(f"unsupported rule kind: {rule.rule_kind}") from exc
    return evaluator(rule, claim)
