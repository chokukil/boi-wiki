from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import canonical_json_bytes
from boi_api.app.science.engine import UnresolvedAmbiguityError, verify_claim
from boi_api.app.science.models import (
    ClaimPacket,
    PrimaryVerdict,
    ResolvedRelease,
)
from boi_api.app.science.rules import VerificationRule, evaluate_rule
from boi_api.app.science.units import (
    IncompatibleDimensionsError,
    InvalidQuantityError,
    compare_quantities,
    normalized_quantity,
    ureg,
    validate_quantity,
)


KNOWLEDGE_REF = "sci:knowledge:fixture"
EVIDENCE_REF = "sci:evidence:fixture"


def claim_fixture(
    claim_id: str,
    *,
    subject: str,
    relation: str,
    predicate: str,
    object_: str,
    conditions: dict[str, object] | None = None,
    quantities: list[dict[str, object]] | None = None,
    process_stage: str | None = None,
    material_state: str | None = None,
    ambiguity_ids: list[str] | None = None,
) -> ClaimPacket:
    exact = f"{subject} {predicate} {object_}"
    return ClaimPacket.model_validate(
        {
            "claim_id": claim_id,
            "document_ref": "boi:public:science:document:fixture",
            "document_digest": "sha256:document-fixture",
            "source_span": {
                "start": 0,
                "end": len(exact),
                "exact": exact,
            },
            "normalized_claim": {
                "subject_concept_id": subject,
                "relation_kind": relation,
                "predicate": predicate,
                "object_concept_id": object_,
                "polarity": "positive",
                "quantities": quantities or [],
                "conditions": [
                    {"condition_id": key, "value": value}
                    for key, value in (conditions or {}).items()
                ],
                "process_stage": process_stage,
                "material_state": material_state,
            },
            "interpretation": {
                "ontology_refs": [subject, object_],
                "ambiguity_ids": ambiguity_ids or [],
                "user_confirmed": not ambiguity_ids,
            },
        }
    )


def rule_fixture(
    rule_id: str,
    kind: str,
    *,
    subject: str,
    object_: str,
    relation: str | None = None,
    expected_predicate: str | None = None,
    required_conditions: dict[str, object] | None = None,
    validity_conditions: dict[str, object] | None = None,
    expected_dimensions: dict[str, str] | None = None,
    equation: dict[str, object] | None = None,
    observation_condition_id: str | None = None,
    corrected_claim: str | None = None,
) -> VerificationRule:
    return VerificationRule.model_validate(
        {
            "rule_id": rule_id,
            "rule_kind": kind,
            "subject_concept_id": subject,
            "object_concept_id": object_,
            "relation_kind": relation,
            "expected_predicate": expected_predicate,
            "required_conditions": required_conditions or {},
            "validity_conditions": validity_conditions or {},
            "expected_dimensions": expected_dimensions or {},
            "equation": equation,
            "observation_condition_id": observation_condition_id,
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "corrected_claim": corrected_claim,
        }
    )


@pytest.fixture
def rules() -> tuple[VerificationRule, ...]:
    return (
        rule_fixture(
            "sci:rule:spin-direction",
            "directional_relation",
            subject="sci:concept:spin-speed",
            object_="sci:concept:film-thickness",
            relation="monotonic_direction",
            expected_predicate="decreases",
            required_conditions={"resist": "same", "viscosity": "same"},
            validity_conditions={"process_stage": "final-coat"},
            corrected_claim="At fixed conditions, increasing spin speed decreases film thickness.",
        ),
        rule_fixture(
            "sci:rule:ohm",
            "equation_constraint",
            subject="sci:concept:voltage",
            object_="sci:concept:current",
            relation="monotonic_direction",
            expected_predicate="increases",
            required_conditions={"resistance": "fixed"},
        ),
        rule_fixture(
            "sci:rule:boiling-pressure",
            "directional_relation",
            subject="sci:concept:pressure",
            object_="sci:concept:boiling-point",
            relation="monotonic_direction",
            expected_predicate="increases",
            required_conditions={"pressure_basis": "specified"},
        ),
        rule_fixture(
            "sci:rule:ideal-gas-domain",
            "validity_domain",
            subject="sci:concept:ideal-gas-law",
            object_="sci:concept:pressure",
            relation="equation",
            validity_conditions={"material_state": "gas"},
        ),
        rule_fixture(
            "sci:rule:device-lifetime",
            "empirical_boundary",
            subject="sci:concept:device",
            object_="sci:concept:lifetime",
            relation="empirical_relation",
            observation_condition_id="qualified_observation",
        ),
    )


@pytest.fixture
def release(rules: tuple[VerificationRule, ...]) -> ResolvedRelease:
    components = [
        {
            "ref": rule.rule_id,
            "kind": "rule",
            "declared_digest": f"sha256:{index:064x}",
            "actual_digest": f"sha256:{index:064x}",
        }
        for index, rule in enumerate(rules, start=1)
    ]
    components.extend(
        [
            {
                "ref": KNOWLEDGE_REF,
                "kind": "knowledge",
                "declared_digest": "sha256:" + "a" * 64,
                "actual_digest": "sha256:" + "a" * 64,
            },
            {
                "ref": EVIDENCE_REF,
                "kind": "evidence",
                "declared_digest": "sha256:" + "b" * 64,
                "actual_digest": "sha256:" + "b" * 64,
            },
        ]
    )
    return ResolvedRelease.model_validate(
        {
            "release_id": "sci-release:foundation:0.1.0",
            "schema_version": "sci-profile/0.1",
            "content_hash": "sha256:" + "f" * 64,
            "status": "active",
            "components": components,
            "component_digests": {
                component["ref"]: component["declared_digest"] for component in components
            },
            "known_limitations": ["fixture-only"],
        }
    )


@pytest.mark.parametrize(
    ("case_id", "claim", "expected"),
    [
        (
            "spin-rpm-increase-thickness-increase",
            claim_fixture(
                "claim:spin-violation",
                subject="sci:concept:spin-speed",
                relation="monotonic_direction",
                predicate="increases",
                object_="sci:concept:film-thickness",
                conditions={"resist": "same", "viscosity": "same"},
                process_stage="final-coat",
            ),
            PrimaryVerdict.VIOLATION,
        ),
        (
            "ohm-voltage-current-fixed-resistance",
            claim_fixture(
                "claim:ohm-consistent",
                subject="sci:concept:voltage",
                relation="monotonic_direction",
                predicate="increases",
                object_="sci:concept:current",
                conditions={"resistance": "fixed"},
            ),
            PrimaryVerdict.CONSISTENT,
        ),
        (
            "boiling-point-pressure-omitted",
            claim_fixture(
                "claim:boiling-missing",
                subject="sci:concept:pressure",
                relation="monotonic_direction",
                predicate="increases",
                object_="sci:concept:boiling-point",
            ),
            PrimaryVerdict.INSUFFICIENT_INFORMATION,
        ),
        (
            "ideal-gas-condensed-phase",
            claim_fixture(
                "claim:ideal-gas-outside",
                subject="sci:concept:ideal-gas-law",
                relation="equation",
                predicate="applies",
                object_="sci:concept:pressure",
                material_state="condensed",
            ),
            PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN,
        ),
        (
            "unqualified-device-lifetime",
            claim_fixture(
                "claim:device-empirical",
                subject="sci:concept:device",
                relation="empirical_relation",
                predicate="lasts",
                object_="sci:concept:lifetime",
            ),
            PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED,
        ),
    ],
)
def test_primary_verdict_cases(
    case_id: str,
    claim: ClaimPacket,
    expected: PrimaryVerdict,
    release: ResolvedRelease,
    rules: tuple[VerificationRule, ...],
):
    """A wrong precedence branch or deterministic outcome must fail a named case."""
    packet = verify_claim(claim, release, rules=rules)

    assert packet.verdict is expected, case_id


def test_different_conditions_do_not_create_false_violation(
    release: ResolvedRelease, rules: tuple[VerificationRule, ...]
):
    """Treating a changed resist as held constant must not create a red verdict."""
    claim = claim_fixture(
        "claim:spin-different-resist",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "different", "viscosity": "same"},
        process_stage="final-coat",
    )

    packet = verify_claim(claim, release, rules=rules)

    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert packet.corrected_claim is None


def test_contradiction_candidate_cannot_override_missing_conditions_or_domain(
    release: ResolvedRelease, rules: tuple[VerificationRule, ...]
):
    """A contradiction candidate must remain gated by conditions and validity."""
    missing = claim_fixture(
        "claim:spin-stage-missing",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
    )
    outside = claim_fixture(
        "claim:spin-outside-domain",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="shear-thinning-regime",
    )

    missing_packet = verify_claim(missing, release, rules=rules)
    outside_packet = verify_claim(outside, release, rules=rules)

    assert missing_packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert outside_packet.verdict is PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
    assert missing_packet.corrected_claim is None
    assert outside_packet.corrected_claim is None


def test_unresolved_ambiguity_stops_before_rule_evaluation(
    release: ResolvedRelease, rules: tuple[VerificationRule, ...]
):
    """Sending a decision-changing ambiguity to the dispatcher must fail closed."""
    claim = claim_fixture(
        "claim:ambiguous",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        ambiguity_ids=["ambiguity:stage"],
    )

    with pytest.raises(UnresolvedAmbiguityError, match="ambiguity:stage"):
        verify_claim(claim, release, rules=rules)


def test_release_must_pin_the_rule_and_every_explanation_reference(
    release: ResolvedRelease, rules: tuple[VerificationRule, ...]
):
    """An unpinned rule or citation must never ground a deterministic verdict."""
    claim = claim_fixture(
        "claim:ohm-grounding",
        subject="sci:concept:voltage",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:current",
        conditions={"resistance": "fixed"},
    )
    ohm = next(rule for rule in rules if rule.rule_id == "sci:rule:ohm")
    unpinned = release.model_copy(
        update={
            "components": tuple(
                component for component in release.components if component.ref != ohm.rule_id
            )
        }
    )

    packet = verify_claim(claim, unpinned, rules=(ohm,))

    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert packet.explanation_facts == []


def test_rule_evaluation_reports_matched_concepts_compared_conditions_and_refs(
    rules: tuple[VerificationRule, ...]
):
    """Dropping concept or condition comparison detail must break the audit trail."""
    claim = claim_fixture(
        "claim:ohm-audit",
        subject="sci:concept:voltage",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:current",
        conditions={"resistance": "fixed"},
    )
    ohm = next(rule for rule in rules if rule.rule_id == "sci:rule:ohm")

    evaluation = evaluate_rule(ohm, claim.normalized_claim)

    assert evaluation.matched_concept_ids == [
        "sci:concept:current",
        "sci:concept:voltage",
    ]
    assert [item.model_dump() for item in evaluation.condition_evaluations] == [
        {
            "condition_id": "resistance",
            "expected": "fixed",
            "actual": "fixed",
            "satisfied": True,
        }
    ]
    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "SUPPORTS"
    assert evaluation.knowledge_refs == [KNOWLEDGE_REF]
    assert evaluation.evidence_refs == [EVIDENCE_REF]


def test_dimension_rule_rejects_an_incompatible_claim_quantity():
    """Accepting time as a length quantity must produce a deterministic contradiction."""
    rule = rule_fixture(
        "sci:rule:length-dimension",
        "dimension_constraint",
        subject="sci:concept:measurement",
        object_="sci:concept:length",
        expected_dimensions={"measured_length": "meter"},
    )
    claim = claim_fixture(
        "claim:wrong-dimension",
        subject="sci:concept:measurement",
        relation="dimensional_relation",
        predicate="has_dimension",
        object_="sci:concept:length",
        quantities=[{"quantity_kind": "measured_length", "value": "3", "unit": "second"}],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "CONTRADICTS"
    assert evaluation.reason_codes == ["DIMENSION_MISMATCH"]


def test_undefined_unit_is_rejected_instead_of_becoming_a_violation():
    """Malformed unit input must not be converted into a false red verdict."""
    rule = rule_fixture(
        "sci:rule:length-unit-validation",
        "dimension_constraint",
        subject="sci:concept:measurement",
        object_="sci:concept:length",
        expected_dimensions={"measured_length": "meter"},
    )
    claim = claim_fixture(
        "claim:undefined-unit",
        subject="sci:concept:measurement",
        relation="dimensional_relation",
        predicate="has_dimension",
        object_="sci:concept:length",
        quantities=[
            {"quantity_kind": "measured_length", "value": "3", "unit": "attacker_unit"}
        ],
    )

    with pytest.raises(InvalidQuantityError, match="undefined unit"):
        evaluate_rule(rule, claim.normalized_claim)


def test_unknown_rule_kind_is_validation_error_and_never_dispatched():
    """Adding a free-form evaluator name must fail at the schema boundary."""
    with pytest.raises(ValidationError, match="rule_kind"):
        rule_fixture(
            "sci:rule:dynamic",
            "python_expression",
            subject="sci:concept:a",
            object_="sci:concept:b",
        )


def test_quantity_validation_is_finite_defined_and_dimension_safe(tmp_path):
    """Undefined/nonfinite units and cross-dimensional comparison must be rejected."""
    normalized = validate_quantity(
        {"quantity_kind": "length", "value": Decimal("12.5"), "unit": "centimeter"}
    )
    same = compare_quantities(
        {"quantity_kind": "length", "value": Decimal("1"), "unit": "meter"},
        {"quantity_kind": "length", "value": Decimal("100"), "unit": "centimeter"},
    )

    assert normalized.magnitude == Decimal("0.125")
    assert normalized_quantity(Decimal("12.5"), "centimeter") == normalized
    assert normalized.unit == "m"
    assert same == 0
    for invalid in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(InvalidQuantityError, match="finite"):
            validate_quantity({"quantity_kind": "length", "value": invalid, "unit": "meter"})
    with pytest.raises(InvalidQuantityError, match="undefined unit"):
        validate_quantity({"quantity_kind": "length", "value": 1, "unit": "made_up_unit"})
    with pytest.raises(IncompatibleDimensionsError, match="incompatible dimensions"):
        compare_quantities(
            {"quantity_kind": "length", "value": 1, "unit": "meter"},
            {"quantity_kind": "duration", "value": 1, "unit": "second"},
        )

    definitions = tmp_path / "attacker-units.txt"
    definitions.write_text("smoot = 1.7018 * meter", encoding="utf-8")
    with pytest.raises(PermissionError, match="locked"):
        ureg.load_definitions(definitions)


def test_verdict_packet_is_byte_stable_and_only_violation_has_a_correction(
    release: ResolvedRelease, rules: tuple[VerificationRule, ...]
):
    """Iteration or set ordering must not alter canonical VerdictPacket bytes."""
    claim = claim_fixture(
        "claim:stable",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"viscosity": "same", "resist": "same"},
        process_stage="final-coat",
    )

    first = verify_claim(claim, release, rules=rules)
    second = verify_claim(claim, release, rules=tuple(reversed(rules)))

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first.corrected_claim == (
        "At fixed conditions, increasing spin speed decreases film thickness."
    )
    assert all(fact.knowledge_refs and fact.evidence_refs for fact in first.explanation_facts)
