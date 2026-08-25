from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import sha256_digest


def _sha256_text(value: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_equation_payload(*, decision_use: str = "deterministic_rule") -> dict:
    original_notation = "V = I R"
    variable_context = [
        {
            "source_symbol": "V",
            "definition": "potential difference across the element",
            "unit_text": "volt",
        },
        {
            "source_symbol": "I",
            "definition": "current through the element",
            "unit_text": "ampere",
        },
        {
            "source_symbol": "R",
            "definition": "resistance of the element",
            "unit_text": "ohm",
        },
    ]
    conventions = {
        "coordinate_convention": "Passive sign convention at the element terminals.",
        "sign_convention": "Positive current enters the positive-voltage terminal.",
        "unit_convention": "SI coherent units: V, A, and ohm.",
    }
    locator = {
        "medium": "pdf",
        "resource_url": "https://example.test/circuits.pdf",
        "content_hash": "sha256:" + "1" * 64,
        "exact": True,
        "section": "2.1 Ohm's law",
        "pdf_page_index": 14,
        "printed_page": "9",
        "equation_label": "Equation 2.3",
    }
    semantic_expression = {
        "schema_version": "science-expression/0.1",
        "root": {
            "op": "relation",
            "relation": "eq",
            "left": {"op": "variable", "variable_id": "voltage"},
            "right": {
                "op": "multiply",
                "left": {"op": "variable", "variable_id": "current"},
                "right": {"op": "variable", "variable_id": "resistance"},
            },
        },
    }
    payload = {
        "equation_id": "sci:equation:ohms-law",
        "scientific_role": "law",
        "decision_use": decision_use,
        "semantic_expression": semantic_expression,
        "display_latex": r"V = I \\cdot R",
        "plain_text": "V = I * R",
        "accessibility_reading": "Voltage equals current multiplied by resistance.",
        "variables": [
            {
                "variable_id": "voltage",
                "symbol": "V",
                "concept_ref": "sci:concept:voltage",
                "quantity_kind": "voltage",
                "dimension": {
                    "mass": 1,
                    "length": 2,
                    "time": -3,
                    "electric_current": -1,
                },
                "unit": "volt",
                "definition": "Potential difference across the element.",
                "domain": "real",
                "sign_constraint": "any",
            },
            {
                "variable_id": "current",
                "symbol": "I",
                "concept_ref": "sci:concept:electric-current",
                "quantity_kind": "electric_current",
                "dimension": {"electric_current": 1},
                "unit": "ampere",
                "definition": "Current through the element.",
                "domain": "real",
                "sign_constraint": "any",
            },
            {
                "variable_id": "resistance",
                "symbol": "R",
                "concept_ref": "sci:concept:resistance",
                "quantity_kind": "electrical_resistance",
                "dimension": {
                    "mass": 1,
                    "length": 2,
                    "time": -3,
                    "electric_current": -2,
                },
                "unit": "ohm",
                "definition": "Electrical resistance of the element.",
                "domain": "real",
                "sign_constraint": "nonnegative",
            },
        ],
        "assumptions": ["The element is represented by its reviewed resistive model."],
        "applicability": [
            "Use only inside the reviewed element model and sign convention."
        ],
        "invalid_outside": [
            "Do not generalize a fitted nonlinear device into an ohmic element."
        ],
        "boundary_conditions": [
            {
                "condition_id": "resistance-domain",
                "statement": "Resistance is nonnegative.",
                "variable_id": "resistance",
                "operator": "gte",
                "value": "0",
                "unit": "ohm",
            }
        ],
        "approximation": None,
        "empirical_fit": None,
        "original_notation_mapping": [
            {"source_symbol": "V", "variable_id": "voltage"},
            {"source_symbol": "I", "variable_id": "current"},
            {"source_symbol": "R", "variable_id": "resistance"},
        ],
        "evidence_uses": [
            {
                "evidence_ref": "sci:evidence:ohms-law",
                "purpose": "Bind the reviewed formula and its variable/sign context.",
                "claim_scope_hash": "sha256:" + "2" * 64,
                "locator": locator,
                "locator_digest": sha256_digest(locator),
                "transcription": {
                    "transcription_id": "sci:transcription:ohms-law",
                    "original_notation": original_notation,
                    "original_notation_hash": _sha256_text(original_notation),
                    "variable_context": variable_context,
                    "variable_context_hash": sha256_digest(variable_context),
                    **conventions,
                    "conventions_hash": sha256_digest(conventions),
                    "relation_notation": "equals",
                    "transcription_method": "manual",
                    "review_state": "reviewed",
                    "reviewer": "science-admin",
                    "reviewed_at": datetime(
                        2026, 8, 25, tzinfo=timezone.utc
                    ).isoformat(),
                    "semantic_expression_digest": sha256_digest(semantic_expression),
                    "transcription_digest": "",
                },
            }
        ],
        "evaluator": {
            "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
            "version": "0.1.0",
            "expression_schema_version": "science-expression/0.1",
            "allowed_operators": ["variable", "multiply", "relation"],
            "evaluator_digest": "sha256:" + "3" * 64,
        },
        "equation_digest": "",
    }
    transcription = payload["evidence_uses"][0]["transcription"]
    transcription["transcription_digest"] = sha256_digest(
        {
            key: value
            for key, value in transcription.items()
            if key != "transcription_digest"
        }
    )
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )
    return payload


def test_equation_knowledge_accepts_closed_digest_bound_semantics():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    equation = ScienceEquationKnowledge.model_validate(valid_equation_payload())

    assert equation.equation_id == "sci:equation:ohms-law"
    assert equation.semantic_expression.root.op == "relation"
    assert equation.equation_digest == equation.computed_digest()


def test_equation_evidence_reference_accepts_existing_science_pack_id_style():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["evidence_uses"][0]["evidence_ref"] = "sci-evidence:circuits:ohms-law"
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    equation = ScienceEquationKnowledge.model_validate(payload)

    assert equation.evidence_uses[0].evidence_ref == ("sci-evidence:circuits:ohms-law")


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("unknown_ast_field", "[Ee]xtra inputs are not permitted"),
        ("unknown_operator", "Input should be"),
        ("dangerous_latex", "unsafe or unsupported LaTeX"),
        ("oversized_latex", "String should have at most 4096 characters"),
    ],
)
def test_equation_schema_is_closed_and_display_input_is_bounded(
    mutation: str, match: str
):
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    if mutation == "unknown_ast_field":
        payload["semantic_expression"]["root"]["advisory"] = "trust me"
    elif mutation == "unknown_operator":
        payload["semantic_expression"]["root"]["op"] = "python_eval"
    elif mutation == "dangerous_latex":
        payload["display_latex"] = r"\\href{file:///etc/passwd}{open}"
    else:
        payload["display_latex"] = "x" * 4097
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match=match):
        ScienceEquationKnowledge.model_validate(payload)


def test_equation_digest_detects_display_or_semantic_drift():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["plain_text"] = "V equals I times R"

    with pytest.raises(ValidationError, match="equation_digest"):
        ScienceEquationKnowledge.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    ["original_notation", "variable_context", "sign_convention", "locator"],
)
def test_equation_evidence_transcription_drift_fails_closed(mutation: str):
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    use = payload["evidence_uses"][0]
    transcription = use["transcription"]
    if mutation == "original_notation":
        transcription["original_notation"] = "V = I / R"
    elif mutation == "variable_context":
        transcription["variable_context"][0]["unit_text"] = "millivolt"
    elif mutation == "sign_convention":
        transcription["sign_convention"] = "Sign convention omitted."
    else:
        use["locator"]["printed_page"] = "10"
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="hash|digest"):
        ScienceEquationKnowledge.model_validate(payload)


def test_all_semantic_variables_must_be_defined_and_notation_mapped():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["variables"] = payload["variables"][:-1]
    payload["original_notation_mapping"] = payload["original_notation_mapping"][:-1]
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="semantic variables must exactly match"):
        ScienceEquationKnowledge.model_validate(payload)


def test_dimensionally_inconsistent_equation_is_rejected():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["variables"][0]["dimension"] = {"length": 1}
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="dimensionally inconsistent"):
        ScienceEquationKnowledge.model_validate(payload)


@pytest.mark.parametrize("mutation", ["missing_evaluator", "operator_not_allowlisted"])
def test_deterministic_rule_requires_an_explicit_evaluator_allowlist(mutation: str):
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    if mutation == "missing_evaluator":
        payload["evaluator"] = None
    else:
        payload["evaluator"]["allowed_operators"] = ["variable", "relation"]
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="deterministic_rule"):
        ScienceEquationKnowledge.model_validate(payload)


def test_unsupported_expression_can_only_remain_explanation_only():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload(decision_use="explanation_only")
    payload["semantic_expression"]["root"] = {
        "op": "integral",
        "integrand": {"op": "variable", "variable_id": "current"},
        "with_respect_to": "time",
    }
    payload["variables"] = [
        payload["variables"][1],
        {
            "variable_id": "time",
            "symbol": "t",
            "concept_ref": "sci:concept:time",
            "quantity_kind": "time",
            "dimension": {"time": 1},
            "unit": "second",
            "definition": "Time coordinate.",
            "domain": "real",
            "sign_constraint": "nonnegative",
        },
    ]
    payload["original_notation_mapping"] = [
        {"source_symbol": "I", "variable_id": "current"},
        {"source_symbol": "t", "variable_id": "time"},
    ]
    payload["boundary_conditions"] = []
    transcription = payload["evidence_uses"][0]["transcription"]
    transcription["original_notation"] = "integral of I with respect to t"
    transcription["original_notation_hash"] = _sha256_text(
        transcription["original_notation"]
    )
    transcription["variable_context"] = [
        {
            "source_symbol": "I",
            "definition": "current through the element",
            "unit_text": "ampere",
        },
        {
            "source_symbol": "t",
            "definition": "time coordinate",
            "unit_text": "second",
        },
    ]
    transcription["variable_context_hash"] = sha256_digest(
        transcription["variable_context"]
    )
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
    payload["evaluator"] = None
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    equation = ScienceEquationKnowledge.model_validate(payload)

    assert equation.decision_use == "explanation_only"


def test_approximation_and_empirical_fit_roles_require_their_limits():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload(decision_use="explanation_only")
    payload["scientific_role"] = "empirical_fit"
    payload["evaluator"] = None
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="empirical_fit metadata"):
        ScienceEquationKnowledge.model_validate(payload)


@pytest.mark.parametrize(
    "display_latex",
    [
        r"\\newcommand{\\x}{attack}",
        r"x + \\unknownmacro{y}",
        r"<script>alert(1)</script>",
        r"\\includegraphics{https://example.test/a.png}",
        r"\\begin{document}x\\end{document}",
    ],
)
def test_display_latex_rejects_macros_html_urls_and_unknown_environments(
    display_latex: str,
):
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["display_latex"] = display_latex
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="unsafe or unsupported LaTeX"):
        ScienceEquationKnowledge.model_validate(payload)


def test_duplicate_symbols_are_rejected_as_ambiguous():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["variables"][1]["symbol"] = "V"
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="symbols must be unambiguous"):
        ScienceEquationKnowledge.model_validate(payload)


def test_approximate_relation_cannot_be_transcribed_as_exact_equality():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload(decision_use="explanation_only")
    payload["semantic_expression"]["root"]["relation"] = "approx"
    payload["evaluator"] = None
    transcription = payload["evidence_uses"][0]["transcription"]
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
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="relation notation"):
        ScienceEquationKnowledge.model_validate(payload)


def test_proportional_relation_is_typed_but_never_a_deterministic_equality():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload(decision_use="explanation_only")
    payload["scientific_role"] = "approximation"
    payload["semantic_expression"]["root"] = {
        "op": "relation",
        "relation": "proportional",
        "left": {"op": "variable", "variable_id": "thickness"},
        "right": {
            "op": "power",
            "left": {"op": "variable", "variable_id": "angular_speed"},
            "right": {"op": "literal", "value": "-0.5"},
        },
    }
    payload["display_latex"] = r"h \propto \omega^{-1/2}"
    payload["plain_text"] = "h is proportional to angular speed to the power -1/2"
    payload["variables"] = [
        {
            "variable_id": "thickness",
            "symbol": "h",
            "concept_ref": "sci:concept:film-thickness",
            "quantity_kind": "film_thickness",
            "dimension": {"length": 1},
            "unit": "meter",
            "definition": "Attainable dry film thickness.",
            "domain": "real",
            "sign_constraint": "positive",
        },
        {
            "variable_id": "angular_speed",
            "symbol": "omega",
            "concept_ref": "sci:concept:angular-speed",
            "quantity_kind": "angular_speed",
            "dimension": {"time": -1},
            "unit": "radian / second",
            "definition": "Final spin angular speed.",
            "domain": "real",
            "sign_constraint": "positive",
        },
    ]
    payload["boundary_conditions"] = []
    payload["approximation"] = {
        "approximation_kind": "continuum_model",
        "error_statement": "The exponent is an approximate process relation, not a recipe guarantee.",
        "validity_conditions": ["Drying terminates radial thinning."],
    }
    payload["original_notation_mapping"] = [
        {"source_symbol": "film thickness", "variable_id": "thickness"},
        {"source_symbol": "spin speed", "variable_id": "angular_speed"},
    ]
    transcription = payload["evidence_uses"][0]["transcription"]
    transcription["original_notation"] = (
        "film thickness decreases in a good approximation with the reciprocal "
        "square root of the spin speed"
    )
    transcription["original_notation_hash"] = _sha256_text(
        transcription["original_notation"]
    )
    transcription["variable_context"] = [
        {
            "source_symbol": "film thickness",
            "definition": "Attainable dry film thickness.",
            "unit_text": "not specified in the cited sentence",
        },
        {
            "source_symbol": "spin speed",
            "definition": "Attained spin speed.",
            "unit_text": "not specified in the cited sentence",
        },
    ]
    transcription["variable_context_hash"] = sha256_digest(
        transcription["variable_context"]
    )
    transcription["relation_notation"] = "proportionality"
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
    payload["evaluator"] = None
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    equation = ScienceEquationKnowledge.model_validate(payload)
    assert equation.semantic_expression.root.relation == "proportional"

    payload["decision_use"] = "deterministic_rule"
    payload["evaluator"] = valid_equation_payload()["evaluator"]
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )
    with pytest.raises(ValidationError, match="exact equality"):
        ScienceEquationKnowledge.model_validate(payload)


def test_each_evidence_use_requires_complete_nonduplicated_variable_context():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    transcription = payload["evidence_uses"][0]["transcription"]
    transcription["variable_context"][2]["source_symbol"] = "I"
    transcription["variable_context_hash"] = sha256_digest(
        transcription["variable_context"]
    )
    transcription["transcription_digest"] = sha256_digest(
        {
            key: value
            for key, value in transcription.items()
            if key != "transcription_digest"
        }
    )
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="variable context"):
        ScienceEquationKnowledge.model_validate(payload)


def test_deterministic_division_requires_a_nonzero_denominator_domain():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["semantic_expression"]["root"]["right"] = {
        "op": "divide",
        "left": {"op": "variable", "variable_id": "current"},
        "right": {"op": "variable", "variable_id": "resistance"},
    }
    payload["variables"][0]["dimension"] = {
        "electric_current": 3,
        "mass": -1,
        "length": -2,
        "time": 3,
    }
    payload["variables"][2]["sign_constraint"] = "nonnegative"
    payload["evaluator"]["allowed_operators"] = [
        "variable",
        "divide",
        "relation",
    ]
    transcription = payload["evidence_uses"][0]["transcription"]
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
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="singular denominator"):
        ScienceEquationKnowledge.model_validate(payload)


def test_semantic_expression_depth_is_bounded():
    from boi_api.app.science.equations import SemanticExpression

    node: dict = {"op": "variable", "variable_id": "x"}
    for _ in range(17):
        node = {"op": "negate", "operand": node}

    with pytest.raises(ValidationError, match="depth 16"):
        SemanticExpression.model_validate(
            {"schema_version": "science-expression/0.1", "root": node}
        )


def test_chemical_reaction_is_a_closed_explanation_only_equation_without_fake_variables():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload(decision_use="explanation_only")
    payload["semantic_expression"]["root"] = {
        "op": "chemical_reaction",
        "reactants": [
            {"species_id": "hydrogen", "stoichiometric_coefficient": "2"},
            {"species_id": "oxygen", "stoichiometric_coefficient": "1"},
        ],
        "products": [{"species_id": "water", "stoichiometric_coefficient": "2"}],
        "reversible": False,
    }
    payload["display_latex"] = r"\\ce{2H2 + O2 -> 2H2O}"
    payload["plain_text"] = "2 H2 + O2 -> 2 H2O"
    payload["accessibility_reading"] = (
        "Two molecules of hydrogen react with one molecule of oxygen to form two molecules of water."
    )
    payload["variables"] = []
    payload["boundary_conditions"] = []
    payload["original_notation_mapping"] = []
    payload["evaluator"] = None
    transcription = payload["evidence_uses"][0]["transcription"]
    transcription["original_notation"] = "2H2 + O2 -> 2H2O"
    transcription["original_notation_hash"] = _sha256_text(
        transcription["original_notation"]
    )
    transcription["variable_context"] = []
    transcription["variable_context_hash"] = sha256_digest([])
    transcription["relation_notation"] = "reaction"
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
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    equation = ScienceEquationKnowledge.model_validate(payload)

    assert equation.semantic_expression.root.op == "chemical_reaction"
    assert equation.variables == []


def test_accessibility_reading_matches_the_local_renderer_limit():
    from boi_api.app.science.equations import ScienceEquationKnowledge

    payload = valid_equation_payload()
    payload["accessibility_reading"] = "x" * 1001
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )

    with pytest.raises(ValidationError, match="at most 1000 characters"):
        ScienceEquationKnowledge.model_validate(payload)
