from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.equations import SemanticExpression
from boi_api.app.science.models import NormalizedClaim
from boi_api.app.science.rules import (
    EQUATION_EVALUATOR_CONTRACT,
    EQUATION_EVALUATOR_CONTRACT_DIGEST,
    EQUATION_EVALUATOR_ID,
    EQUATION_EVALUATOR_REGISTRY,
    EQUATION_EVALUATOR_VERSION,
    EquationRuleBinding,
    VerificationRule,
    evaluate_equation_constraint,
    validate_operational_equation_binding,
    validate_equation_knowledge_for_operational_binding,
    validate_semantic_expression_for_operational_binding,
)


EQUATION_ID = "sci:equation:ohms-law"
EQUATION_DIGEST = "sha256:" + "1" * 64
EVIDENCE_REF = "sci:evidence:ohms-law"


def _binding_payload(
    *,
    operator: str = "product",
    mappings: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "equation_id": EQUATION_ID,
        "equation_digest": EQUATION_DIGEST,
        "evaluator_id": EQUATION_EVALUATOR_ID,
        "evaluator_version": EQUATION_EVALUATOR_VERSION,
        "evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST,
        "constraint_operator": operator,
        "variable_mappings": mappings
        or [
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
    payload["binding_digest"] = sha256_digest(payload)
    return payload


def _rule_payload(*, binding: dict[str, object] | None | object = ...) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_id": "sci:rule:ohms-law",
        "rule_kind": "equation_constraint",
        "subject_concept_id": "sci:concept:voltage",
        "object_concept_id": "sci:concept:resistance",
        "equation": {
            "left_quantity_kind": "voltage",
            "right_quantity_kinds": ["current", "resistance"],
            "operator": "product",
            "relative_tolerance": "0",
        },
        "knowledge_refs": ["sci:knowledge:ohms-law"],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": [
            {
                "evidence_ref": EVIDENCE_REF,
                "claim_family": "circuits.ohms_law",
                "purpose": "Check the exact audited product form.",
            }
        ],
    }
    if binding is not ...:
        payload["equation_binding"] = binding
    return payload


def _semantic_expression(
    *,
    left: str = "voltage",
    operator: str = "multiply",
    right_1: str = "current",
    right_2: str = "resistance",
    relation: str = "eq",
) -> SemanticExpression:
    return SemanticExpression.model_validate(
        {
            "schema_version": "science-expression/0.1",
            "root": {
                "op": "relation",
                "relation": relation,
                "left": {"op": "variable", "variable_id": left},
                "right": {
                    "op": operator,
                    "left": {"op": "variable", "variable_id": right_1},
                    "right": {"op": "variable", "variable_id": right_2},
                },
            },
        }
    )


def test_registry_contract_is_closed_canonical_and_digest_bound():
    assert EQUATION_EVALUATOR_CONTRACT["evaluator_id"] == EQUATION_EVALUATOR_ID
    assert EQUATION_EVALUATOR_CONTRACT["version"] == EQUATION_EVALUATOR_VERSION
    assert EQUATION_EVALUATOR_CONTRACT["operators"] == {
        "equal": {"right_arity": 1},
        "product": {"right_arity": 2},
        "quotient": {"right_arity": 2},
    }
    assert sha256_digest(EQUATION_EVALUATOR_CONTRACT) == (
        EQUATION_EVALUATOR_CONTRACT_DIGEST
    )
    assert list(EQUATION_EVALUATOR_REGISTRY) == [
        f"{EQUATION_EVALUATOR_ID}@{EQUATION_EVALUATOR_VERSION}"
    ]
    with pytest.raises(TypeError):
        EQUATION_EVALUATOR_CONTRACT["evaluator_id"] = "python:eval"  # type: ignore[index]


def test_exact_binding_accepts_one_audited_product_form():
    rule = VerificationRule.model_validate(_rule_payload(binding=_binding_payload()))

    identity = validate_operational_equation_binding(rule)

    assert identity is not None
    assert identity.equation_id == EQUATION_ID
    assert identity.equation_digest == EQUATION_DIGEST
    assert identity.required_decision_use == "deterministic_rule"
    assert identity.evaluator_digest == EQUATION_EVALUATOR_CONTRACT_DIGEST
    assert identity.operand_variable_ids == {
        "left": "voltage",
        "right_1": "current",
        "right_2": "resistance",
    }


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("equation_digest", "sha256:not-a-digest", "SHA-256"),
        ("evaluator_digest", "sha256:short", "SHA-256"),
        ("binding_digest", "sha256:short", "SHA-256"),
        ("evaluator_id", "python:eval", "registered"),
        ("evaluator_version", "9.9.9", "version"),
        ("evaluator_digest", "sha256:" + "f" * 64, "contract digest"),
    ],
)
def test_binding_rejects_digest_and_evaluator_spoofing(
    field: str, value: str, match: str
):
    payload = _binding_payload()
    payload[field] = value
    if field != "binding_digest":
        payload["binding_digest"] = sha256_digest(
            {key: item for key, item in payload.items() if key != "binding_digest"}
        )

    with pytest.raises(ValidationError, match=match):
        EquationRuleBinding.model_validate(payload)


def test_binding_rejects_an_operator_outside_the_closed_registry():
    payload = _binding_payload()
    payload["constraint_operator"] = "power"
    payload["binding_digest"] = sha256_digest(
        {key: item for key, item in payload.items() if key != "binding_digest"}
    )

    with pytest.raises(ValidationError, match="constraint_operator"):
        EquationRuleBinding.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        ("empty", "nonempty"),
        ("duplicate_variable", "equation variables must be unique"),
        ("duplicate_quantity", "Claim quantity kinds must be unique"),
        ("duplicate_operand", "constraint operands must be unique"),
    ],
)
def test_binding_rejects_empty_or_duplicate_mapping(mutate: str, match: str):
    payload = _binding_payload()
    mappings = payload["variable_mappings"]
    assert isinstance(mappings, list)
    if mutate == "empty":
        mappings[0]["claim_quantity_kind"] = " "
    elif mutate == "duplicate_variable":
        mappings[1]["equation_variable_id"] = mappings[0]["equation_variable_id"]
    elif mutate == "duplicate_quantity":
        mappings[1]["claim_quantity_kind"] = mappings[0]["claim_quantity_kind"]
    else:
        mappings[1]["constraint_operand"] = mappings[0]["constraint_operand"]
    payload["binding_digest"] = sha256_digest(
        {key: item for key, item in payload.items() if key != "binding_digest"}
    )

    with pytest.raises(ValidationError, match=match):
        EquationRuleBinding.model_validate(payload)


@pytest.mark.parametrize("mutation", ["missing", "extra", "swap", "operator"])
def test_rule_rejects_mapping_that_is_not_the_exact_declared_operand_form(
    mutation: str,
):
    binding = _binding_payload()
    mappings = binding["variable_mappings"]
    assert isinstance(mappings, list)
    if mutation == "missing":
        mappings.pop()
    elif mutation == "extra":
        mappings.append(
            {
                "equation_variable_id": "conductance",
                "claim_quantity_kind": "conductance",
                "constraint_operand": "right_2",
            }
        )
    elif mutation == "swap":
        mappings[1]["claim_quantity_kind"], mappings[2]["claim_quantity_kind"] = (
            mappings[2]["claim_quantity_kind"],
            mappings[1]["claim_quantity_kind"],
        )
    else:
        binding["constraint_operator"] = "quotient"
    binding["binding_digest"] = sha256_digest(
        {key: item for key, item in binding.items() if key != "binding_digest"}
    )

    with pytest.raises(ValidationError, match="exact equation operand mapping"):
        VerificationRule.model_validate(_rule_payload(binding=binding))


def test_binding_is_equation_only_but_direct_legacy_rule_remains_parseable():
    legacy = VerificationRule.model_validate(_rule_payload())
    directional = _rule_payload(binding=_binding_payload())
    directional.update(
        {
            "rule_kind": "directional_relation",
            "expected_predicate": "increases",
            "contradiction_predicates": ["decreases"],
            "equation": None,
        }
    )

    assert legacy.equation_binding is None
    with pytest.raises(ValidationError, match="equation_constraint only"):
        VerificationRule.model_validate(directional)
    with pytest.raises(ValueError, match="operational equation rule requires"):
        validate_operational_equation_binding(legacy)


@pytest.mark.parametrize(
    ("expression", "match"),
    [
        (
            _semantic_expression(relation="approx"),
            "exact equality relation",
        ),
        (
            _semantic_expression(operator="divide"),
            "exact product form",
        ),
        (
            _semantic_expression(left="resistance"),
            "exact equation variable mapping",
        ),
        (
            _semantic_expression(right_1="resistance", right_2="current"),
            "exact equation variable mapping",
        ),
    ],
)
def test_semantically_similar_or_rearranged_expression_is_not_auto_accepted(
    expression: SemanticExpression, match: str
):
    rule = VerificationRule.model_validate(_rule_payload(binding=_binding_payload()))
    identity = validate_operational_equation_binding(rule)
    assert identity is not None

    with pytest.raises(ValueError, match=match):
        validate_semantic_expression_for_operational_binding(identity, expression)


def test_exact_semantic_form_is_accepted_but_explanation_only_is_not_authority():
    rule = VerificationRule.model_validate(_rule_payload(binding=_binding_payload()))
    identity = validate_operational_equation_binding(rule)
    assert identity is not None
    expression = _semantic_expression()

    validate_semantic_expression_for_operational_binding(identity, expression)
    explanation_only = SimpleNamespace(
        equation_id=identity.equation_id,
        equation_digest=identity.equation_digest,
        decision_use="explanation_only",
        evaluator=None,
        semantic_expression=expression,
    )
    with pytest.raises(ValueError, match="explanation-only"):
        validate_equation_knowledge_for_operational_binding(
            identity, explanation_only  # type: ignore[arg-type]
        )


def test_runtime_mutation_of_binding_fails_before_equation_verdict():
    rule = VerificationRule.model_validate(_rule_payload(binding=_binding_payload()))
    assert rule.equation_binding is not None
    rule.equation_binding.evaluator_digest = "sha256:" + "f" * 64
    claim = NormalizedClaim.model_validate(
        {
            "subject_concept_id": "sci:concept:voltage",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:resistance",
            "polarity": "positive",
            "quantities": [
                {"quantity_kind": "voltage", "value": 10, "unit": "volt"},
                {"quantity_kind": "current", "value": 2, "unit": "ampere"},
                {"quantity_kind": "resistance", "value": 5, "unit": "ohm"},
            ],
            "conditions": [],
            "process_stage": None,
            "material_state": None,
        }
    )

    with pytest.raises(ValueError, match="contract digest"):
        evaluate_equation_constraint(rule, claim)


def test_binding_digest_detects_any_payload_tampering():
    payload = _binding_payload()
    original = deepcopy(payload)
    payload["equation_id"] = "sci:equation:lookalike"

    with pytest.raises(ValidationError, match="binding_digest"):
        EquationRuleBinding.model_validate(payload)

    assert EquationRuleBinding.model_validate(original).binding_digest == original[
        "binding_digest"
    ]
