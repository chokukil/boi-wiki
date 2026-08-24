"""Closed, deterministic evaluators for reviewed scientific rule objects."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from boi_api.app.science.models import (
    ClaimCondition,
    ConditionConstraint,
    ConditionEvaluation,
    NormalizedClaim,
    RelationKind,
    RuleEvaluation,
    RuleKind,
    ScienceModel,
)
from boi_api.app.science.units import (
    IncompatibleDimensionsError,
    UnregisteredConversionError,
    canonical_unit_token,
    comparable_values,
    compare_quantities,
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


class QuantityEquivalenceConstraint(ScienceModel):
    """Two claim operands that must express one scientific quantity."""

    scientific_role: str = Field(min_length=1)
    quantity_kind: str = Field(min_length=1)
    reference_quantity_kind: str = Field(min_length=1)
    interval: bool = False

    @model_validator(mode="after")
    def distinct_operands(self) -> "QuantityEquivalenceConstraint":
        if self.quantity_kind == self.reference_quantity_kind:
            raise ValueError("quantity equivalence operands must be distinct")
        return self


class ArrheniusDirectionConstraint(ScienceModel):
    """Typed operands for the positive-activation-energy temperature direction."""

    activation_energy_kind: str
    temperature_before_kind: str
    temperature_after_kind: str
    diffusivity_before_kind: str
    diffusivity_after_kind: str


class CarrierConductivityConstraint(ScienceModel):
    """Typed operands for sigma = q(n mu_n + p mu_p)."""

    electron_concentration_kind: str
    hole_concentration_kind: str
    electron_mobility_kind: str
    hole_mobility_kind: str
    conductivity_kind: str
    relative_tolerance: Decimal = Field(default=Decimal("1e-12"), ge=0)


class QualifiedObservation(ScienceModel):
    """An untrusted observation proposal; never sufficient as operational authority."""

    observation_id: str
    rule_id: str
    verified: bool
    measurement_ref: str
    evidence_ref: str


class EvidenceUse(ScienceModel):
    """One closed, executable authorization to use an Evidence span."""

    evidence_ref: str = Field(min_length=1)
    claim_family: str = Field(min_length=1)
    purpose: str = Field(min_length=1)

    @field_validator("evidence_ref", "claim_family", "purpose")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence use text fields must be nonblank")
        return value


class VerificationRule(ScienceModel):
    """A validated rule description; it contains data, never executable code."""

    rule_id: str
    rule_kind: RuleKind
    subject_concept_id: str
    object_concept_id: str
    relation_kind: RelationKind | None = None
    expected_predicate: str | None = None
    contradiction_predicates: list[str] = Field(default_factory=list)
    expected_polarity: Literal["positive", "negative"] = "positive"
    required_conditions: list[ConditionConstraint] = Field(default_factory=list)
    validity_conditions: list[ConditionConstraint] = Field(default_factory=list)
    empirical_trigger_conditions: list[ConditionConstraint] = Field(
        default_factory=list
    )
    context_dimensions: dict[str, str] = Field(default_factory=dict)
    quantity_equivalence_constraints: list[QuantityEquivalenceConstraint] = Field(
        default_factory=list
    )
    nonnegative_quantity_kinds: list[str] = Field(default_factory=list)
    arrhenius_direction_constraint: ArrheniusDirectionConstraint | None = None
    carrier_conductivity_constraint: CarrierConductivityConstraint | None = None
    expected_dimensions: dict[str, str] = Field(default_factory=dict)
    equation: EquationConstraint | None = None
    knowledge_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    evidence_uses: list[EvidenceUse] = Field(min_length=1)
    corrected_claim: str | None = None

    @field_validator("context_dimensions", "expected_dimensions")
    @classmethod
    def canonical_dimension_units(cls, value: dict[str, str]) -> dict[str, str]:
        return {kind: canonical_unit_token(unit) for kind, unit in value.items()}

    @model_validator(mode="after")
    def has_kind_specific_constraint(self) -> "VerificationRule":
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")
        evidence_use_refs = [use.evidence_ref for use in self.evidence_uses]
        if len(evidence_use_refs) != len(set(evidence_use_refs)):
            raise ValueError("evidence_uses must bind each evidence_ref exactly once")
        if set(evidence_use_refs) != set(self.evidence_refs):
            raise ValueError("evidence_uses must exactly match evidence_refs")
        condition_keys = [
            condition.key
            for condition in (
                *self.required_conditions,
                *self.validity_conditions,
                *self.empirical_trigger_conditions,
            )
        ]
        if len(condition_keys) != len(set(condition_keys)):
            raise ValueError("condition constraint keys must be unique across a rule")
        equivalence_operands = [
            operand
            for constraint in self.quantity_equivalence_constraints
            for operand in (
                constraint.quantity_kind,
                constraint.reference_quantity_kind,
            )
        ]
        if len(equivalence_operands) != len(set(equivalence_operands)):
            raise ValueError(
                "quantity equivalence operands must be unique across a rule"
            )
        if len(self.nonnegative_quantity_kinds) != len(
            set(self.nonnegative_quantity_kinds)
        ):
            raise ValueError("nonnegative quantity kinds must be unique")
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
            if (
                self.expected_predicate is None
                or "contradiction_predicates" not in self.model_fields_set
                or self.equation is not None
                or self.expected_dimensions
            ):
                raise ValueError("rule kind payload invalid for directional_relation")
            if (
                self.expected_predicate in self.contradiction_predicates
                or len(set(self.contradiction_predicates))
                != len(self.contradiction_predicates)
                or any(
                    not predicate.strip() for predicate in self.contradiction_predicates
                )
            ):
                raise ValueError(
                    "directional contradiction predicates must be unique explicit opposites"
                )
        elif self.rule_kind is RuleKind.EQUATION_CONSTRAINT:
            if (
                self.equation is None
                or self.expected_predicate is not None
                or "contradiction_predicates" in self.model_fields_set
                or self.expected_dimensions
            ):
                raise ValueError("rule kind payload invalid for equation_constraint")
        elif self.rule_kind is RuleKind.DIMENSION_CONSTRAINT:
            if (
                not self.expected_dimensions
                or self.expected_predicate is not None
                or "contradiction_predicates" in self.model_fields_set
                or self.equation is not None
            ):
                raise ValueError("rule kind payload invalid for dimension_constraint")
        else:
            if (
                self.expected_predicate is not None
                or "contradiction_predicates" in self.model_fields_set
                or self.equation is not None
                or self.expected_dimensions
            ):
                raise ValueError(
                    f"rule kind payload invalid for {self.rule_kind.value}"
                )
        if self.rule_kind is RuleKind.VALIDITY_DOMAIN and not self.validity_conditions:
            raise ValueError("rule kind payload invalid for validity_domain")
        return self


class ReleasedRule(ScienceModel):
    """A typed rule payload bound to its OKF and semantic digests."""

    rule: VerificationRule
    component_digest: str
    semantic_digest: str


class ResolvedRuleSet(ScienceModel):
    """The complete set of typed rules resolved for one immutable Release set."""

    release_set_digest: str
    rules: tuple[ReleasedRule, ...]

    @model_validator(mode="after")
    def unique_rule_ids(self) -> "ResolvedRuleSet":
        rule_ids = [released.rule.rule_id for released in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate rule ID in resolved rule set")
        return self


class QualificationRuleSet(ScienceModel):
    """Serializable Rule set for qualification only; never an Engine capability."""

    release_set_digest: str
    rules: tuple[ReleasedRule, ...]

    @model_validator(mode="after")
    def unique_rule_ids(self) -> "QualificationRuleSet":
        rule_ids = [released.rule.rule_id for released in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate rule ID in qualification rule set")
        return self


class DetailedRuleEvaluation(RuleEvaluation):
    """RuleEvaluation with the matched concepts needed for an audit trail."""

    matched_concept_ids: list[str]


RuleEvaluator: TypeAlias = Callable[
    [VerificationRule, NormalizedClaim, tuple[QualifiedObservation, ...]],
    DetailedRuleEvaluation,
]


def _claim_values(claim: NormalizedClaim) -> dict[str, ClaimCondition]:
    values = {condition.condition_id: condition for condition in claim.conditions}
    values["process_stage"] = ClaimCondition(
        condition_id="process_stage", value=claim.process_stage
    )
    values["material_state"] = ClaimCondition(
        condition_id="material_state", value=claim.material_state
    )
    return values


def has_complete_quantity_equivalence_operands(
    rule: VerificationRule, claim: NormalizedClaim
) -> bool:
    """Qualification guard requiring both representations for every declared pair."""

    kinds = {quantity.quantity_kind for quantity in claim.quantities}
    return all(
        {
            constraint.quantity_kind,
            constraint.reference_quantity_kind,
        }
        <= kinds
        for constraint in rule.quantity_equivalence_constraints
    )


def _concept_match(rule: VerificationRule, claim: NormalizedClaim) -> bool:
    return (
        rule.subject_concept_id == claim.subject_concept_id
        and rule.object_concept_id == claim.object_concept_id
        and (rule.relation_kind is None or rule.relation_kind is claim.relation_kind)
    )


def _is_numeric_scalar(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _scalar_kind(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if _is_numeric_scalar(value):
        return "numeric"
    if isinstance(value, str):
        return "string"
    return "unsupported"


def _compatible_condition_scalar(
    constraint: ConditionConstraint, actual_value: object
) -> bool:
    if constraint.operator == "in":
        assert constraint.values is not None
        return all(
            _scalar_kind(actual_value) == _scalar_kind(expected)
            for expected in constraint.values
        )
    if (
        constraint.operator == "range"
        or constraint.unit is not None
        or constraint.operator in {"lt", "lte", "gt", "gte"}
    ):
        return _is_numeric_scalar(actual_value)
    return _scalar_kind(actual_value) == _scalar_kind(constraint.value)


def _condition_evaluations(
    expected: list[ConditionConstraint], claim: NormalizedClaim
) -> list[ConditionEvaluation]:
    actual = _claim_values(claim)
    evaluations: list[ConditionEvaluation] = []
    for constraint in sorted(expected, key=lambda item: item.key):
        actual_condition = actual.get(constraint.key)
        actual_value = actual_condition.value if actual_condition is not None else None
        actual_unit = actual_condition.unit if actual_condition is not None else None
        expected_value: object = (
            constraint.range or constraint.values or constraint.value
        )
        satisfied = False
        reason_code = "CONDITION_VALUE_MISMATCH"
        if actual_value is None:
            reason_code = "MISSING_CONDITION_VALUE"
        elif (constraint.unit is None) != (actual_unit is None):
            reason_code = "INCOMPATIBLE_CONDITION_UNIT_PRESENCE"
        elif not _compatible_condition_scalar(constraint, actual_value):
            reason_code = "INCOMPATIBLE_CONDITION_TYPES"
        else:
            try:
                if constraint.operator == "range":
                    assert constraint.range is not None
                    if constraint.unit is not None and actual_unit is not None:
                        lower = compare_quantities(
                            {
                                "quantity_kind": constraint.key,
                                "value": actual_value,
                                "unit": actual_unit,
                            },
                            {
                                "quantity_kind": constraint.key,
                                "value": constraint.range.minimum,
                                "unit": constraint.unit,
                            },
                        )
                        upper = compare_quantities(
                            {
                                "quantity_kind": constraint.key,
                                "value": actual_value,
                                "unit": actual_unit,
                            },
                            {
                                "quantity_kind": constraint.key,
                                "value": constraint.range.maximum,
                                "unit": constraint.unit,
                            },
                        )
                    else:
                        actual_decimal = Decimal(str(actual_value))
                        lower = (actual_decimal > constraint.range.minimum) - (
                            actual_decimal < constraint.range.minimum
                        )
                        upper = (actual_decimal > constraint.range.maximum) - (
                            actual_decimal < constraint.range.maximum
                        )
                    lower_ok = (
                        lower >= 0 if constraint.range.minimum_inclusive else lower > 0
                    )
                    upper_ok = (
                        upper <= 0 if constraint.range.maximum_inclusive else upper < 0
                    )
                    satisfied = lower_ok and upper_ok
                elif constraint.operator == "in":
                    assert constraint.values is not None
                    satisfied = actual_value in constraint.values
                elif constraint.unit is not None and actual_unit is not None:
                    compared = compare_quantities(
                        {
                            "quantity_kind": constraint.key,
                            "value": actual_value,
                            "unit": actual_unit,
                        },
                        {
                            "quantity_kind": constraint.key,
                            "value": constraint.value,
                            "unit": constraint.unit,
                        },
                    )
                    satisfied = {
                        "eq": compared == 0,
                        "ne": compared != 0,
                        "lt": compared < 0,
                        "lte": compared <= 0,
                        "gt": compared > 0,
                        "gte": compared >= 0,
                    }[constraint.operator]
                elif constraint.operator in {"eq", "ne"}:
                    satisfied = (
                        actual_value == constraint.value
                        if constraint.operator == "eq"
                        else actual_value != constraint.value
                    )
                else:
                    actual_decimal = Decimal(str(actual_value))
                    expected_decimal = Decimal(str(constraint.value))
                    satisfied = {
                        "lt": actual_decimal < expected_decimal,
                        "lte": actual_decimal <= expected_decimal,
                        "gt": actual_decimal > expected_decimal,
                        "gte": actual_decimal >= expected_decimal,
                    }[constraint.operator]
                reason_code = "CONDITION_SATISFIED" if satisfied else reason_code
            except IncompatibleDimensionsError:
                reason_code = "INCOMPATIBLE_CONDITION_UNITS"
        evaluations.append(
            ConditionEvaluation(
                condition_id=constraint.key,
                operator=constraint.operator,
                expected=expected_value,
                actual=actual_value,
                expected_unit=constraint.unit,
                actual_unit=actual_unit,
                satisfied=satisfied,
                reason_code=reason_code,
            )
        )
    return evaluations


def _base_evaluation(
    rule: VerificationRule,
    claim: NormalizedClaim,
    *,
    applicability: Literal[
        "IN_SCOPE",
        "MISSING_CONDITIONS",
        "OUTSIDE_DOMAIN",
        "EMPIRICAL_ONLY",
        "NOT_APPLICABLE",
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


def _missing_quantity_evaluation(
    rule: VerificationRule,
    claim: NormalizedClaim,
    reason_code: str,
    conditions: list[ConditionEvaluation],
) -> DetailedRuleEvaluation:
    return _base_evaluation(
        rule,
        claim,
        applicability="MISSING_CONDITIONS",
        outcome="UNDECIDED",
        reason_codes=[reason_code],
        conditions=conditions,
    )


def _outside_quantity_evaluation(
    rule: VerificationRule,
    claim: NormalizedClaim,
    reason_code: str,
    conditions: list[ConditionEvaluation],
) -> DetailedRuleEvaluation:
    return _base_evaluation(
        rule,
        claim,
        applicability="OUTSIDE_DOMAIN",
        outcome="UNDECIDED",
        reason_codes=[reason_code],
        conditions=conditions,
    )


def _quantity_constraint_gate(
    rule: VerificationRule,
    claim: NormalizedClaim,
    conditions: list[ConditionEvaluation],
) -> DetailedRuleEvaluation | None:
    quantities = {quantity.quantity_kind: quantity for quantity in claim.quantities}

    for constraint in rule.quantity_equivalence_constraints:
        reference = quantities.get(constraint.reference_quantity_kind)
        quantity = quantities.get(constraint.quantity_kind)
        if reference is None:
            continue
        if quantity is None:
            return _missing_quantity_evaluation(
                rule,
                claim,
                "INCOMPLETE_QUANTITY_EQUIVALENCE",
                conditions,
            )
        try:
            equivalent = (
                compare_quantities(
                    quantity,
                    reference,
                    interval=constraint.interval,
                )
                == 0
            )
        except UnregisteredConversionError:
            return _outside_quantity_evaluation(
                rule,
                claim,
                "UNREGISTERED_QUANTITY_EQUIVALENCE",
                conditions,
            )
        except IncompatibleDimensionsError:
            equivalent = False
        if not equivalent:
            return _outside_quantity_evaluation(
                rule,
                claim,
                "QUANTITY_EQUIVALENCE_MISMATCH",
                conditions,
            )

    for quantity_kind in rule.nonnegative_quantity_kinds:
        quantity = quantities.get(quantity_kind)
        if quantity is None:
            return _missing_quantity_evaluation(
                rule,
                claim,
                "MISSING_NONNEGATIVE_QUANTITY",
                conditions,
            )
        if quantity.value < 0:
            return _outside_quantity_evaluation(
                rule,
                claim,
                "NONNEGATIVE_QUANTITY_VIOLATION",
                conditions,
            )

    if rule.arrhenius_direction_constraint is not None:
        constraint = rule.arrhenius_direction_constraint
        kinds = (
            constraint.activation_energy_kind,
            constraint.temperature_before_kind,
            constraint.temperature_after_kind,
            constraint.diffusivity_before_kind,
            constraint.diffusivity_after_kind,
        )
        if any(kind not in quantities for kind in kinds):
            return _missing_quantity_evaluation(
                rule,
                claim,
                "MISSING_ARRHENIUS_QUANTITIES",
                conditions,
            )
        activation_energy = quantities[constraint.activation_energy_kind]
        temperature_before = quantities[constraint.temperature_before_kind]
        temperature_after = quantities[constraint.temperature_after_kind]
        diffusivity_before = quantities[constraint.diffusivity_before_kind]
        diffusivity_after = quantities[constraint.diffusivity_after_kind]
        try:
            activation_is_positive = (
                compare_quantities(
                    activation_energy,
                    {
                        "quantity_kind": constraint.activation_energy_kind,
                        "value": 0,
                        "unit": activation_energy.unit,
                    },
                )
                > 0
            )
            temperature_increases = (
                compare_quantities(temperature_after, temperature_before) > 0
            )
            diffusivity_increases = (
                compare_quantities(diffusivity_after, diffusivity_before) > 0
            )
        except IncompatibleDimensionsError:
            activation_is_positive = temperature_increases = diffusivity_increases = (
                False
            )
        if not (
            activation_is_positive and temperature_increases and diffusivity_increases
        ):
            return _outside_quantity_evaluation(
                rule,
                claim,
                "ARRHENIUS_CROSS_FIELD_MISMATCH",
                conditions,
            )

    if rule.carrier_conductivity_constraint is not None:
        constraint = rule.carrier_conductivity_constraint
        kinds = (
            constraint.electron_concentration_kind,
            constraint.hole_concentration_kind,
            constraint.electron_mobility_kind,
            constraint.hole_mobility_kind,
            constraint.conductivity_kind,
        )
        if any(kind not in quantities for kind in kinds):
            return _missing_quantity_evaluation(
                rule,
                claim,
                "MISSING_CARRIER_CONDUCTIVITY_QUANTITIES",
                conditions,
            )
        normalized = {kind: validate_quantity(quantities[kind]) for kind in kinds}
        required_dimensions = {
            constraint.electron_concentration_kind: expected_dimensionality(
                "1 / meter ** 3"
            ),
            constraint.hole_concentration_kind: expected_dimensionality(
                "1 / meter ** 3"
            ),
            constraint.electron_mobility_kind: expected_dimensionality(
                "meter ** 2 / volt / second"
            ),
            constraint.hole_mobility_kind: expected_dimensionality(
                "meter ** 2 / volt / second"
            ),
            constraint.conductivity_kind: expected_dimensionality("siemens / meter"),
        }
        if any(
            normalized[kind].dimensionality != dimension
            for kind, dimension in required_dimensions.items()
        ):
            return _outside_quantity_evaluation(
                rule,
                claim,
                "CARRIER_CONDUCTIVITY_DIMENSION_MISMATCH",
                conditions,
            )
        elementary_charge = Decimal("1.602176634e-19")
        expected_conductivity = elementary_charge * (
            normalized[constraint.electron_concentration_kind].magnitude
            * normalized[constraint.electron_mobility_kind].magnitude
            + normalized[constraint.hole_concentration_kind].magnitude
            * normalized[constraint.hole_mobility_kind].magnitude
        )
        actual_conductivity = normalized[constraint.conductivity_kind].magnitude
        scale = max(abs(expected_conductivity), Decimal("1e-30"))
        if abs(actual_conductivity - expected_conductivity) > (
            constraint.relative_tolerance * scale
        ):
            return _outside_quantity_evaluation(
                rule,
                claim,
                "CARRIER_CONDUCTIVITY_MISMATCH",
                conditions,
            )
    return None


def _applicability_gate(
    rule: VerificationRule, claim: NormalizedClaim
) -> (
    DetailedRuleEvaluation | tuple[list[ConditionEvaluation], list[ConditionEvaluation]]
):
    if not _concept_match(rule, claim):
        return _base_evaluation(
            rule,
            claim,
            applicability="NOT_APPLICABLE",
            outcome="UNDECIDED",
            reason_codes=["CONCEPTS_NOT_MATCHED"],
        )
    required = _condition_evaluations(rule.required_conditions, claim)
    if any(item.reason_code == "INCOMPATIBLE_CONDITION_UNITS" for item in required):
        return _base_evaluation(
            rule,
            claim,
            applicability="OUTSIDE_DOMAIN",
            outcome="UNDECIDED",
            reason_codes=["INCOMPATIBLE_CONDITION_UNITS"],
            conditions=required,
        )
    if any(not item.satisfied for item in required):
        details = {
            item.reason_code
            for item in required
            if not item.satisfied and item.reason_code is not None
        }
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=sorted({"MISSING_REQUIRED_CONDITIONS", *details}),
            conditions=required,
        )
    validity = _condition_evaluations(rule.validity_conditions, claim)
    if any(item.reason_code == "INCOMPATIBLE_CONDITION_UNITS" for item in validity):
        return _base_evaluation(
            rule,
            claim,
            applicability="OUTSIDE_DOMAIN",
            outcome="UNDECIDED",
            reason_codes=["INCOMPATIBLE_CONDITION_UNITS"],
            conditions=required + validity,
        )
    if any(
        item.reason_code
        in {
            "MISSING_CONDITION_VALUE",
            "INCOMPATIBLE_CONDITION_UNIT_PRESENCE",
            "INCOMPATIBLE_CONDITION_TYPES",
        }
        for item in validity
    ):
        details = {
            item.reason_code
            for item in validity
            if not item.satisfied and item.reason_code is not None
        }
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=sorted({"MISSING_VALIDITY_CONDITIONS", *details}),
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
    quantities = {quantity.quantity_kind: quantity for quantity in claim.quantities}
    missing_context = sorted(set(rule.context_dimensions) - set(quantities))
    if missing_context:
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["MISSING_CONTEXT_QUANTITIES"],
            conditions=required + validity,
        )
    context_matches = all(
        validate_quantity(quantities[kind]).dimensionality
        == expected_dimensionality(unit)
        for kind, unit in sorted(rule.context_dimensions.items())
    )
    if not context_matches:
        return _base_evaluation(
            rule,
            claim,
            applicability="OUTSIDE_DOMAIN",
            outcome="UNDECIDED",
            reason_codes=["CONTEXT_DIMENSION_MISMATCH"],
            conditions=required + validity,
        )
    quantity_gate = _quantity_constraint_gate(rule, claim, required + validity)
    if quantity_gate is not None:
        return quantity_gate
    return required, validity


def _predicate_evaluation(
    rule: VerificationRule, claim: NormalizedClaim
) -> DetailedRuleEvaluation:
    gated = _applicability_gate(rule, claim)
    if isinstance(gated, DetailedRuleEvaluation):
        return gated
    required, validity = gated
    same_polarity = claim.polarity == rule.expected_polarity
    if claim.predicate == rule.expected_predicate:
        outcome = "SUPPORTS" if same_polarity else "CONTRADICTS"
    elif claim.predicate in rule.contradiction_predicates:
        outcome = "CONTRADICTS" if same_polarity else "SUPPORTS"
    else:
        outcome = "UNDECIDED"
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome=outcome,
        reason_codes=[
            {
                "SUPPORTS": "RULE_SUPPORTS",
                "CONTRADICTS": "RULE_CONTRADICTS",
                "UNDECIDED": "PREDICATE_NOT_EXPLICITLY_CLASSIFIED",
            }[outcome]
        ],
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
    left = quantities[equation.left_quantity_kind]
    right_items = [quantities[kind] for kind in equation.right_quantity_kinds]
    if equation.operator == "equal":
        right_value = right_items[0].value
        right_unit = right_items[0].unit
    elif equation.operator == "product":
        right_value = right_items[0].value * right_items[1].value
        right_unit = f"{right_items[0].unit} * {right_items[1].unit}"
    else:
        right_value = right_items[0].value / right_items[1].value
        right_unit = f"{right_items[0].unit} / {right_items[1].unit}"
    try:
        left_value, right_value = comparable_values(
            left.value,
            left.unit,
            right_value,
            right_unit,
        )
    except IncompatibleDimensionsError as exc:
        raise IncompatibleDimensionsError("incompatible equation dimensions") from exc
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
    if claim.polarity == "negative":
        evaluated_outcome = "CONTRADICTS" if outcome else "UNDECIDED"
        reason_code = (
            "NEGATED_EQUATION_SATISFIED" if outcome else "NEGATED_EQUATION_UNDECIDED"
        )
    else:
        evaluated_outcome = "SUPPORTS" if outcome else "CONTRADICTS"
        reason_code = "EQUATION_SATISFIED" if outcome else "EQUATION_CONTRADICTION"
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome=evaluated_outcome,
        reason_codes=[reason_code],
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
        validate_quantity(quantities[kind]).dimensionality
        == expected_dimensionality(unit)
        for kind, unit in sorted(rule.expected_dimensions.items())
    )
    if claim.polarity == "negative":
        outcome = "CONTRADICTS" if matches else "UNDECIDED"
        reason_code = (
            "NEGATED_DIMENSION_MATCH" if matches else "NEGATED_DIMENSION_UNDECIDED"
        )
    else:
        outcome = "SUPPORTS" if matches else "CONTRADICTS"
        reason_code = "DIMENSION_MATCH" if matches else "DIMENSION_MISMATCH"
    return _base_evaluation(
        rule,
        claim,
        applicability="IN_SCOPE",
        outcome=outcome,
        reason_codes=[reason_code],
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
        outcome="CONTRADICTS" if claim.polarity == "negative" else "SUPPORTS",
        reason_codes=[
            "NEGATED_VALIDITY_DOMAIN_MATCH"
            if claim.polarity == "negative"
            else "VALIDITY_DOMAIN_MATCH"
        ],
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
    return _base_evaluation(
        rule,
        claim,
        applicability="EMPIRICAL_ONLY",
        outcome="UNDECIDED",
        reason_codes=["QUALIFIED_OBSERVATION_REQUIRED"],
        conditions=required + validity,
    )


RULE_EVALUATORS: dict[RuleKind, RuleEvaluator] = {
    RuleKind.DIRECTIONAL_RELATION: evaluate_directional_relation,
    RuleKind.EQUATION_CONSTRAINT: evaluate_equation_constraint,
    RuleKind.DIMENSION_CONSTRAINT: evaluate_dimension_constraint,
    RuleKind.VALIDITY_DOMAIN: evaluate_validity_domain,
    RuleKind.EMPIRICAL_BOUNDARY: evaluate_empirical_boundary,
}


def _apply_empirical_requirement(
    rule: VerificationRule,
    claim: NormalizedClaim,
    evaluation: DetailedRuleEvaluation,
    qualified_observations: tuple[QualifiedObservation, ...],
) -> DetailedRuleEvaluation:
    """Require a bound observation only after deterministic contradictions survive."""

    if (
        not rule.empirical_trigger_conditions
        or evaluation.applicability != "IN_SCOPE"
        or evaluation.outcome == "CONTRADICTS"
    ):
        return evaluation
    actual = _claim_values(claim)
    provided = [
        constraint.key
        for constraint in rule.empirical_trigger_conditions
        if constraint.key in actual and actual[constraint.key].value is not None
    ]
    if not provided:
        return evaluation
    empirical = _condition_evaluations(rule.empirical_trigger_conditions, claim)
    if len(provided) != len(rule.empirical_trigger_conditions):
        return _base_evaluation(
            rule,
            claim,
            applicability="MISSING_CONDITIONS",
            outcome="UNDECIDED",
            reason_codes=["INCOMPLETE_EMPIRICAL_TRIGGER"],
            conditions=[*evaluation.condition_evaluations, *empirical],
        )
    if not all(item.satisfied for item in empirical):
        return evaluation
    return _base_evaluation(
        rule,
        claim,
        applicability="EMPIRICAL_ONLY",
        outcome="UNDECIDED",
        reason_codes=["QUALIFIED_OBSERVATION_REQUIRED"],
        conditions=[*evaluation.condition_evaluations, *empirical],
    )


def evaluate_rule(
    rule: VerificationRule,
    claim: NormalizedClaim,
    *,
    qualified_observations: tuple[QualifiedObservation, ...] = (),
) -> DetailedRuleEvaluation:
    """Dispatch one validated rule through the closed evaluator allowlist."""

    try:
        evaluator = RULE_EVALUATORS[rule.rule_kind]
    except (
        KeyError
    ) as exc:  # Defensive boundary if an invalid object bypasses Pydantic.
        raise ValueError(f"unsupported rule kind: {rule.rule_kind}") from exc
    evaluation = evaluator(rule, claim, qualified_observations)
    if rule.rule_kind is RuleKind.EMPIRICAL_BOUNDARY:
        return evaluation
    return _apply_empirical_requirement(
        rule,
        claim,
        evaluation,
        qualified_observations,
    )
