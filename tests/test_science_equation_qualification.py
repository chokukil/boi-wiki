from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.equations import ScienceEquationKnowledge, SemanticExpression
from boi_api.app.science.exceptions import ScienceCatalogError
from boi_api.app.science.models import NormalizedClaim
from boi_api.app.science.rules import (
    EQUATION_EVALUATOR_CONTRACT_DIGEST,
    EQUATION_EVALUATOR_ID,
    EQUATION_EVALUATOR_VERSION,
    EquationConstraint,
    OperationalEquationBindingIdentity,
    VerificationRule,
    evaluate_equation_constraint,
    validate_equation_knowledge_for_operational_binding,
    validate_semantic_expression_for_operational_binding,
)
from tests.test_science_catalog import science_tree as _science_tree_fixture
from tests.test_science_catalog_equations import _install_equation
from tests.test_science_equations import valid_equation_payload


_FORCE = {"mass": 1, "length": 1, "time": -2}
_MASS = {"mass": 1}
_ACCELERATION = {"length": 1, "time": -2}
_CONCENTRATION = {"length": -3, "amount_of_substance": 1}
_AMOUNT = {"amount_of_substance": 1}
_VOLUME = {"length": 3}
_VOLTAGE = {"mass": 1, "length": 2, "time": -3, "electric_current": -1}
_CURRENT = {"electric_current": 1}
_RESISTANCE = {
    "mass": 1,
    "length": 2,
    "time": -3,
    "electric_current": -2,
}
_CONDUCTIVITY = {
    "mass": -1,
    "length": -3,
    "time": 3,
    "electric_current": 2,
}
_CHARGE = {"time": 1, "electric_current": 1}
_NUMBER_DENSITY = {"length": -3}
_MOBILITY = {"mass": -1, "time": 2, "electric_current": 1}
_DIFFUSIVITY = {"length": 2, "time": -1}
_ENERGY = {"mass": 1, "length": 2, "time": -2}
_BOLTZMANN = {
    "mass": 1,
    "length": 2,
    "time": -2,
    "thermodynamic_temperature": -1,
}
_TEMPERATURE = {"thermodynamic_temperature": 1}
_LENGTH = {"length": 1}
_ANGULAR_SPEED = {"time": -1}


def _variable(
    variable_id: str,
    symbol: str,
    quantity_kind: str,
    dimension: dict[str, int],
    unit: str,
    *,
    sign: str = "any",
) -> dict[str, object]:
    return {
        "variable_id": variable_id,
        "symbol": symbol,
        "concept_ref": f"sci:concept:{quantity_kind}",
        "quantity_kind": quantity_kind,
        "dimension": dimension,
        "unit": unit,
        "definition": f"Reviewed {quantity_kind.replace('_', ' ')} quantity.",
        "domain": "real",
        "sign_constraint": sign,
    }


def _var(variable_id: str) -> dict[str, str]:
    return {"op": "variable", "variable_id": variable_id}


def _binary(operator: str, left: dict, right: dict) -> dict:
    return {"op": operator, "left": left, "right": right}


def _relation(left: dict, right: dict, relation: str = "eq") -> dict:
    return {"op": "relation", "relation": relation, "left": left, "right": right}


def _finalize(payload: dict) -> dict:
    use = payload["evidence_uses"][0]
    transcription = use["transcription"]
    transcription["original_notation_hash"] = (
        "sha256:"
        + hashlib.sha256(transcription["original_notation"].encode("utf-8")).hexdigest()
    )
    transcription["variable_context_hash"] = sha256_digest(
        transcription["variable_context"]
    )
    conventions = {
        "coordinate_convention": transcription["coordinate_convention"],
        "sign_convention": transcription["sign_convention"],
        "unit_convention": transcription["unit_convention"],
    }
    transcription["conventions_hash"] = sha256_digest(conventions)
    transcription["semantic_expression_digest"] = sha256_digest(
        payload["semantic_expression"]
    )
    transcription["transcription_digest"] = sha256_digest(
        {
            key: value
            for key, value in transcription.items()
            if key != "transcription_digest"
        }
    )
    use["locator_digest"] = sha256_digest(use["locator"])
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )
    return payload


def _domain_equation(
    *,
    domain: str,
    role: str,
    decision_use: str,
    root: dict,
    variables: list[dict[str, object]],
    notation: str,
    latex: str,
    operators: list[str],
    relation_notation: str = "equals",
    boundary_conditions: list[dict[str, object]] | None = None,
    approximation: dict[str, object] | None = None,
) -> dict:
    payload = valid_equation_payload(decision_use=decision_use)
    payload.update(
        {
            "equation_id": f"sci:equation:qualification-{domain}",
            "scientific_role": role,
            "semantic_expression": {
                "schema_version": "science-expression/0.1",
                "root": root,
            },
            "display_latex": latex,
            "plain_text": notation,
            "accessibility_reading": notation,
            "variables": variables,
            "assumptions": ["All named quantities use their reviewed definitions."],
            "applicability": ["Use only under the stated reviewed conditions."],
            "invalid_outside": [
                "Outside the reviewed domain, retain this equation for explanation only."
            ],
            "boundary_conditions": boundary_conditions or [],
            "approximation": approximation,
            "empirical_fit": None,
            "original_notation_mapping": [
                {"source_symbol": item["symbol"], "variable_id": item["variable_id"]}
                for item in variables
            ],
            "evaluator": (
                {
                    "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
                    "version": "0.1.0",
                    "expression_schema_version": "science-expression/0.1",
                    "allowed_operators": operators,
                    "evaluator_digest": "sha256:" + "3" * 64,
                }
                if decision_use == "deterministic_rule"
                else None
            ),
        }
    )
    use = payload["evidence_uses"][0]
    use["locator"]["equation_label"] = f"Qualification {domain} equation"
    transcription = use["transcription"]
    transcription.update(
        {
            "transcription_id": f"sci:transcription:qualification-{domain}",
            "original_notation": notation,
            "variable_context": [
                {
                    "source_symbol": item["symbol"],
                    "definition": item["definition"],
                    "unit_text": item["unit"],
                }
                for item in variables
            ],
            "coordinate_convention": "Coordinates are exactly those stated by the source.",
            "sign_convention": "Signs are exactly those stated by the source.",
            "unit_convention": "Units are the reviewed SI-compatible units listed here.",
            "relation_notation": relation_notation,
            "reviewed_at": datetime(2026, 8, 25, tzinfo=timezone.utc).isoformat(),
        }
    )
    return _finalize(payload)


def _physics_equation() -> dict:
    return _domain_equation(
        domain="physics",
        role="law",
        decision_use="deterministic_rule",
        root=_relation(
            _var("force"), _binary("multiply", _var("mass"), _var("acceleration"))
        ),
        variables=[
            _variable("force", "F", "force", _FORCE, "newton"),
            _variable("mass", "m", "mass", _MASS, "kilogram", sign="positive"),
            _variable(
                "acceleration",
                "a",
                "acceleration",
                _ACCELERATION,
                "meter / second ** 2",
            ),
        ],
        notation="F = m a",
        latex=r"F = m \cdot a",
        operators=["variable", "multiply", "relation"],
    )


def _chemistry_equation() -> dict:
    return _domain_equation(
        domain="chemistry",
        role="definition",
        decision_use="deterministic_rule",
        root=_relation(
            _var("amount_concentration"),
            _binary("divide", _var("amount"), _var("volume")),
        ),
        variables=[
            _variable(
                "amount_concentration",
                "c",
                "amount_concentration",
                _CONCENTRATION,
                "mole / meter ** 3",
                sign="nonnegative",
            ),
            _variable("amount", "n", "amount", _AMOUNT, "mole", sign="nonnegative"),
            _variable("volume", "V", "volume", _VOLUME, "meter ** 3", sign="positive"),
        ],
        notation="c = n / V",
        latex=r"c = \frac{n}{V}",
        operators=["variable", "divide", "relation"],
        relation_notation="definition",
        boundary_conditions=[
            {
                "condition_id": "positive-volume",
                "statement": "Volume must be positive.",
                "variable_id": "volume",
                "operator": "gt",
                "value": "0",
                "unit": "meter ** 3",
            }
        ],
    )


def _circuits_equation() -> dict:
    return _domain_equation(
        domain="circuits",
        role="law",
        decision_use="deterministic_rule",
        root=_relation(
            _var("voltage"), _binary("multiply", _var("current"), _var("resistance"))
        ),
        variables=[
            _variable("voltage", "V", "voltage", _VOLTAGE, "volt"),
            _variable("current", "I", "electric_current", _CURRENT, "ampere"),
            _variable(
                "resistance",
                "R",
                "electrical_resistance",
                _RESISTANCE,
                "ohm",
                sign="nonnegative",
            ),
        ],
        notation="V = I R",
        latex=r"V = I \cdot R",
        operators=["variable", "multiply", "relation"],
    )


def _semiconductor_equation() -> dict:
    carriers = _binary(
        "add",
        _binary("multiply", _var("electron_density"), _var("electron_mobility")),
        _binary("multiply", _var("hole_density"), _var("hole_mobility")),
    )
    return _domain_equation(
        domain="semiconductor-devices",
        role="derived_model",
        decision_use="explanation_only",
        root=_relation(
            _var("conductivity"), _binary("multiply", _var("charge"), carriers)
        ),
        variables=[
            _variable(
                "conductivity",
                "sigma",
                "conductivity",
                _CONDUCTIVITY,
                "siemens / meter",
                sign="nonnegative",
            ),
            _variable(
                "charge", "q", "elementary_charge", _CHARGE, "coulomb", sign="positive"
            ),
            _variable(
                "electron_density",
                "n",
                "electron_density",
                _NUMBER_DENSITY,
                "1 / meter ** 3",
                sign="nonnegative",
            ),
            _variable(
                "electron_mobility",
                "mu_n",
                "electron_mobility",
                _MOBILITY,
                "meter ** 2 / volt / second",
                sign="nonnegative",
            ),
            _variable(
                "hole_density",
                "p",
                "hole_density",
                _NUMBER_DENSITY,
                "1 / meter ** 3",
                sign="nonnegative",
            ),
            _variable(
                "hole_mobility",
                "mu_p",
                "hole_mobility",
                _MOBILITY,
                "meter ** 2 / volt / second",
                sign="nonnegative",
            ),
        ],
        notation="sigma = q (n mu_n + p mu_p)",
        latex=r"\sigma = q(n\mu_n + p\mu_p)",
        operators=["variable", "multiply", "add", "relation"],
    )


def _materials_equation() -> dict:
    exponent = {
        "op": "negate",
        "operand": _binary(
            "divide",
            _var("activation_energy"),
            _binary("multiply", _var("boltzmann_constant"), _var("temperature")),
        ),
    }
    return _domain_equation(
        domain="materials-science",
        role="derived_model",
        decision_use="explanation_only",
        root=_relation(
            _var("diffusivity"),
            _binary(
                "multiply",
                _var("preexponential_diffusivity"),
                {"op": "function", "function_name": "exp", "operands": [exponent]},
            ),
        ),
        variables=[
            _variable(
                "diffusivity",
                "D",
                "diffusivity",
                _DIFFUSIVITY,
                "meter ** 2 / second",
                sign="positive",
            ),
            _variable(
                "preexponential_diffusivity",
                "D_0",
                "preexponential_diffusivity",
                _DIFFUSIVITY,
                "meter ** 2 / second",
                sign="positive",
            ),
            _variable(
                "activation_energy",
                "E_a",
                "activation_energy",
                _ENERGY,
                "joule",
                sign="positive",
            ),
            _variable(
                "boltzmann_constant",
                "k_B",
                "boltzmann_constant",
                _BOLTZMANN,
                "joule / kelvin",
                sign="positive",
            ),
            _variable(
                "temperature",
                "T",
                "thermodynamic_temperature",
                _TEMPERATURE,
                "kelvin",
                sign="positive",
            ),
        ],
        notation="D = D_0 exp(-E_a / (k_B T))",
        latex=r"D = D_0 \exp\left(-\frac{E_a}{k_B T}\right)",
        operators=["variable", "multiply", "divide", "negate", "function", "relation"],
    )


def _spin_equation() -> dict:
    return _domain_equation(
        domain="spin-coating",
        role="approximation",
        decision_use="explanation_only",
        root=_relation(
            _var("film_thickness"),
            _binary(
                "power",
                _var("angular_speed"),
                {"op": "literal", "value": "-0.5"},
            ),
            relation="proportional",
        ),
        variables=[
            _variable(
                "film_thickness",
                "h",
                "film_thickness",
                _LENGTH,
                "meter",
                sign="positive",
            ),
            _variable(
                "angular_speed",
                "omega",
                "angular_speed",
                _ANGULAR_SPEED,
                "radian / second",
                sign="positive",
            ),
        ],
        notation="h is proportional to omega ** -0.5",
        latex=r"h \propto \omega^{-1/2}",
        operators=["variable", "literal", "power", "relation"],
        relation_notation="proportionality",
        approximation={
            "approximation_kind": "continuum_model",
            "error_statement": "No universal numeric error is claimed outside a qualified process window.",
            "validity_conditions": [
                "Resist, environment, recipe stage, and process window are fixed."
            ],
        },
    )


@pytest.mark.parametrize(
    ("domain", "factory", "expected_decision_use"),
    [
        ("physics", _physics_equation, "deterministic_rule"),
        ("chemistry", _chemistry_equation, "deterministic_rule"),
        ("circuits", _circuits_equation, "deterministic_rule"),
        ("semiconductor-devices", _semiconductor_equation, "explanation_only"),
        ("materials-science", _materials_equation, "explanation_only"),
        ("spin-coating", _spin_equation, "explanation_only"),
    ],
)
def test_six_domains_share_one_closed_equation_contract(
    domain: str, factory, expected_decision_use: str
) -> None:
    equation = ScienceEquationKnowledge.model_validate(factory())

    assert equation.equation_id == f"sci:equation:qualification-{domain}"
    assert equation.decision_use == expected_decision_use
    assert equation.computed_digest() == equation.equation_digest
    assert equation.evidence_uses[0].locator.exact is True
    assert equation.evidence_uses[0].transcription.review_state == "reviewed"


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("wrong_dimension", "dimensionally inconsistent"),
        ("missing_variable", "semantic variables must exactly match"),
        ("extra_variable", "semantic variables must exactly match"),
        ("ambiguous_mapping", "source symbols must be unique"),
    ],
)
def test_closed_schema_rejects_dimension_variable_and_mapping_drift(
    mutation: str, match: str
) -> None:
    payload = _circuits_equation()
    if mutation == "wrong_dimension":
        payload["variables"][0]["dimension"] = _LENGTH
    elif mutation == "missing_variable":
        payload["variables"].pop()
        payload["original_notation_mapping"].pop()
        payload["evidence_uses"][0]["transcription"]["variable_context"].pop()
    elif mutation == "extra_variable":
        extra = _variable("time", "t", "time", {"time": 1}, "second")
        payload["variables"].append(extra)
        payload["original_notation_mapping"].append(
            {"source_symbol": "t", "variable_id": "time"}
        )
        payload["evidence_uses"][0]["transcription"]["variable_context"].append(
            {
                "source_symbol": "t",
                "definition": extra["definition"],
                "unit_text": "second",
            }
        )
    else:
        payload["original_notation_mapping"][1]["source_symbol"] = "V"
        payload["evidence_uses"][0]["transcription"]["variable_context"][1][
            "source_symbol"
        ] = "V"
    _finalize(payload)

    with pytest.raises(ValidationError, match=match):
        ScienceEquationKnowledge.model_validate(payload)


def test_catalog_rejects_a_unit_label_that_disagrees_with_declared_dimension(
    tmp_path: Path,
) -> None:
    science_tree = _science_tree_fixture.__wrapped__(tmp_path)
    _install_equation(
        science_tree,
        mutate=lambda equation: equation["variables"][0].update({"unit": "meter"}),
    )

    from boi_api.app.science.catalog import ScienceCatalog

    with pytest.raises(ScienceCatalogError, match="unit.*dimension"):
        ScienceCatalog(science_tree)


def _product_identity() -> OperationalEquationBindingIdentity:
    return OperationalEquationBindingIdentity(
        equation_id="sci:equation:qualification-physics",
        equation_digest="sha256:" + "1" * 64,
        evaluator_id=EQUATION_EVALUATOR_ID,
        evaluator_version=EQUATION_EVALUATOR_VERSION,
        evaluator_digest=EQUATION_EVALUATOR_CONTRACT_DIGEST,
        constraint_operator="product",
        operand_variable_ids={
            "left": "force",
            "right_1": "mass",
            "right_2": "acceleration",
        },
        claim_quantity_kinds={
            "left": "force",
            "right_1": "mass",
            "right_2": "acceleration",
        },
    )


@pytest.mark.parametrize(
    ("right", "relation", "match"),
    [
        (
            {
                "op": "negate",
                "operand": _binary("multiply", _var("mass"), _var("acceleration")),
            },
            "eq",
            "exact product form",
        ),
        (
            _binary("power", _var("mass"), _var("acceleration")),
            "eq",
            "exact product form",
        ),
        (
            _binary("divide", _var("mass"), _var("acceleration")),
            "eq",
            "exact product form",
        ),
        (
            _binary("multiply", _var("mass"), _var("acceleration")),
            "approx",
            "exact equality relation",
        ),
    ],
)
def test_operational_binding_rejects_wrong_sign_exponent_operator_or_relation(
    right: dict, relation: str, match: str
) -> None:
    expression = SemanticExpression.model_validate(
        {
            "schema_version": "science-expression/0.1",
            "root": _relation(_var("force"), right, relation=relation),
        }
    )

    with pytest.raises(ValueError, match=match):
        validate_semantic_expression_for_operational_binding(
            _product_identity(), expression
        )


def test_deterministic_division_requires_a_nonzero_denominator_domain() -> None:
    payload = _chemistry_equation()
    payload["variables"][2]["sign_constraint"] = "any"
    payload["boundary_conditions"] = []
    _finalize(payload)

    with pytest.raises(ValidationError, match="singular denominator"):
        ScienceEquationKnowledge.model_validate(payload)


def test_invalid_boundary_range_is_rejected_before_equation_use() -> None:
    payload = _chemistry_equation()
    payload["boundary_conditions"] = [
        {
            "condition_id": "invalid-volume-range",
            "statement": "Invalid reversed range.",
            "variable_id": "volume",
            "operator": "range",
            "minimum": "10",
            "maximum": "1",
            "minimum_inclusive": True,
            "maximum_inclusive": True,
            "unit": "meter ** 3",
        }
    ]
    _finalize(payload)

    with pytest.raises(ValidationError, match="minimum cannot exceed maximum"):
        ScienceEquationKnowledge.model_validate(payload)


def test_approximation_records_scope_but_cannot_become_red_mark_authority() -> None:
    equation = ScienceEquationKnowledge.model_validate(_spin_equation())
    identity = _product_identity().model_copy(
        update={
            "equation_id": equation.equation_id,
            "equation_digest": equation.equation_digest,
        }
    )

    assert equation.approximation is not None
    assert equation.approximation.maximum_absolute_error is None
    assert equation.approximation.validity_conditions == [
        "Resist, environment, recipe stage, and process window are fixed."
    ]
    assert equation.invalid_outside
    with pytest.raises(ValueError, match="explanation-only"):
        validate_equation_knowledge_for_operational_binding(identity, equation)


def test_approximation_numeric_tolerance_requires_its_unit() -> None:
    payload = _spin_equation()
    payload["approximation"]["maximum_absolute_error"] = "0.0000001"
    _finalize(payload)

    with pytest.raises(ValidationError, match="error and unit"):
        ScienceEquationKnowledge.model_validate(payload)


def _product_rule(
    *,
    tolerance: str = "0",
    validity_conditions: list[dict] | None = None,
) -> VerificationRule:
    binding = {
        "equation_id": "sci:equation:qualification-circuits",
        "equation_digest": "sha256:" + "4" * 64,
        "evaluator_id": EQUATION_EVALUATOR_ID,
        "evaluator_version": EQUATION_EVALUATOR_VERSION,
        "evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST,
        "constraint_operator": "product",
        "variable_mappings": [
            {
                "equation_variable_id": "voltage",
                "claim_quantity_kind": "voltage",
                "constraint_operand": "left",
            },
            {
                "equation_variable_id": "current",
                "claim_quantity_kind": "current",
                "constraint_operand": "right_1",
            },
            {
                "equation_variable_id": "resistance",
                "claim_quantity_kind": "resistance",
                "constraint_operand": "right_2",
            },
        ],
    }
    binding["binding_digest"] = sha256_digest(binding)
    return VerificationRule.model_validate(
        {
            "rule_id": "sci:rule:qualification-circuits",
            "rule_kind": "equation_constraint",
            "subject_concept_id": "sci:concept:voltage",
            "object_concept_id": "sci:concept:resistance",
            "validity_conditions": validity_conditions or [],
            "equation": {
                "left_quantity_kind": "voltage",
                "right_quantity_kinds": ["current", "resistance"],
                "operator": "product",
                "relative_tolerance": tolerance,
            },
            "equation_binding": binding,
            "knowledge_refs": ["sci:knowledge:qualification-circuits"],
            "evidence_refs": ["sci:evidence:qualification-circuits"],
            "evidence_uses": [
                {
                    "evidence_ref": "sci:evidence:qualification-circuits",
                    "claim_family": "qualification.circuits",
                    "purpose": "Qualify exact product semantics.",
                }
            ],
        }
    )


def _circuits_claim(
    *,
    voltage: str = "10",
    include_resistance: bool = True,
    temperature: float | None = None,
) -> NormalizedClaim:
    quantities = [
        {"quantity_kind": "voltage", "value": voltage, "unit": "volt"},
        {"quantity_kind": "current", "value": "2", "unit": "ampere"},
    ]
    if include_resistance:
        quantities.append({"quantity_kind": "resistance", "value": "5", "unit": "ohm"})
    conditions = (
        [{"condition_id": "temperature", "value": temperature, "unit": "kelvin"}]
        if temperature is not None
        else []
    )
    return NormalizedClaim.model_validate(
        {
            "subject_concept_id": "sci:concept:voltage",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:resistance",
            "polarity": "positive",
            "quantities": quantities,
            "conditions": conditions,
            "process_stage": None,
            "material_state": None,
        }
    )


def test_missing_quantity_and_extrapolation_are_undecided_not_false_red() -> None:
    missing = evaluate_equation_constraint(
        _product_rule(), _circuits_claim(include_resistance=False)
    )
    extrapolated = evaluate_equation_constraint(
        _product_rule(
            validity_conditions=[
                {
                    "key": "temperature",
                    "operator": "range",
                    "range": {"minimum": 280, "maximum": 320},
                    "unit": "kelvin",
                }
            ]
        ),
        _circuits_claim(temperature=500),
    )

    assert (missing.applicability, missing.outcome, missing.reason_codes) == (
        "MISSING_CONDITIONS",
        "UNDECIDED",
        ["MISSING_EQUATION_QUANTITIES"],
    )
    assert (extrapolated.applicability, extrapolated.outcome) == (
        "OUTSIDE_DOMAIN",
        "UNDECIDED",
    )
    assert extrapolated.reason_codes == ["VALIDITY_DOMAIN_MISMATCH"]


def test_relative_tolerance_has_a_closed_nonnegative_boundary() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        EquationConstraint.model_validate(
            {
                "left_quantity_kind": "voltage",
                "right_quantity_kinds": ["current", "resistance"],
                "operator": "product",
                "relative_tolerance": "-0.01",
            }
        )

    just_inside = evaluate_equation_constraint(
        _product_rule(tolerance="0.01"), _circuits_claim(voltage="10.1")
    )
    just_outside = evaluate_equation_constraint(
        _product_rule(tolerance="0.01"), _circuits_claim(voltage="10.1001")
    )
    assert just_inside.outcome == "SUPPORTS"
    assert just_outside.outcome == "CONTRADICTS"


def test_integral_expression_is_structured_but_must_remain_explanation_only() -> None:
    payload = _domain_equation(
        domain="unsupported-integral",
        role="derived_model",
        decision_use="explanation_only",
        root={
            "op": "integral",
            "integrand": _var("current"),
            "with_respect_to": "time",
        },
        variables=[
            _variable("current", "I", "electric_current", _CURRENT, "ampere"),
            _variable("time", "t", "time", {"time": 1}, "second", sign="nonnegative"),
        ],
        notation="integral of I with respect to t",
        latex=r"\int I\,\mathrm{d}t",
        operators=["variable", "integral"],
    )
    equation = ScienceEquationKnowledge.model_validate(payload)
    assert equation.decision_use == "explanation_only"

    payload["decision_use"] = "deterministic_rule"
    payload["evaluator"] = {
        "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
        "version": "0.1.0",
        "expression_schema_version": "science-expression/0.1",
        "allowed_operators": ["variable", "integral"],
        "evaluator_digest": "sha256:" + "3" * 64,
    }
    _finalize(payload)
    with pytest.raises(ValidationError, match="deterministic|eligible"):
        ScienceEquationKnowledge.model_validate(payload)


@pytest.mark.parametrize(
    "malicious_latex",
    [
        r"\input{/etc/passwd}",
        r"\href{file:///etc/passwd}{open}",
        r"\newcommand{\steal}{x}",
        r"<script>alert(1)</script>",
    ],
)
def test_malicious_latex_is_never_accepted_as_equation_knowledge(
    malicious_latex: str,
) -> None:
    payload = deepcopy(_materials_equation())
    payload["display_latex"] = malicious_latex
    _finalize(payload)

    with pytest.raises(ValidationError, match="unsafe or unsupported LaTeX"):
        ScienceEquationKnowledge.model_validate(payload)
