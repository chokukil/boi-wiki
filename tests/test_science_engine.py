from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.engine import UnresolvedAmbiguityError
from boi_api.app.science.engine import _verify_resolved_claim as verify_claim
from boi_api.app.science.engine import verify_claim as verify_operational_claim
from boi_api.app.science.exceptions import ScienceOperationalError
from boi_api.app.science.models import (
    ClaimPacket,
    PrimaryVerdict,
    ResolvedRelease,
    ResolvedReleaseSet,
)
from boi_api.app.science.rules import (
    QualifiedObservation,
    ReleasedRule,
    ResolvedRuleSet,
    VerificationRule,
    evaluate_rule,
)
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
MEASUREMENT_REF = "sci:knowledge:measurement-fixture"
OTHER_EVIDENCE_REF = "sci:evidence:other-fixture"


def evidence_use_fixture() -> list[dict[str, object]]:
    return [
        {
            "evidence_ref": EVIDENCE_REF,
            "claim_family": "fixture.rule_support",
            "purpose": "Support the fixture rule under its stated conditions.",
        }
    ]


def claim_fixture(
    claim_id: str,
    *,
    subject: str,
    relation: str,
    predicate: str,
    object_: str,
    conditions: dict[str, object] | None = None,
    typed_conditions: list[dict[str, object]] | None = None,
    quantities: list[dict[str, object]] | None = None,
    process_stage: str | None = None,
    material_state: str | None = None,
    ambiguity_ids: list[str] | None = None,
    polarity: str = "positive",
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
                "polarity": polarity,
                "quantities": quantities or [],
                "conditions": typed_conditions
                if typed_conditions is not None
                else [
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
    contradiction_predicates: list[str] | None = None,
    required_conditions: dict[str, object] | list[dict[str, object]] | None = None,
    validity_conditions: dict[str, object] | list[dict[str, object]] | None = None,
    empirical_trigger_conditions: list[dict[str, object]] | None = None,
    context_dimensions: dict[str, str] | None = None,
    quantity_equivalence_constraints: list[dict[str, object]] | None = None,
    expected_dimensions: dict[str, str] | None = None,
    equation: dict[str, object] | None = None,
    corrected_claim: str | None = None,
) -> VerificationRule:
    payload = {
        "rule_id": rule_id,
        "rule_kind": kind,
        "subject_concept_id": subject,
        "object_concept_id": object_,
        "relation_kind": relation,
        "expected_predicate": expected_predicate,
        "required_conditions": (
            [
                {"key": key, "operator": "eq", "value": value}
                for key, value in required_conditions.items()
            ]
            if isinstance(required_conditions, dict)
            else (required_conditions or [])
        ),
        "validity_conditions": (
            [
                {"key": key, "operator": "eq", "value": value}
                for key, value in validity_conditions.items()
            ]
            if isinstance(validity_conditions, dict)
            else (validity_conditions or [])
        ),
        "empirical_trigger_conditions": empirical_trigger_conditions or [],
        "context_dimensions": context_dimensions or {},
        "quantity_equivalence_constraints": quantity_equivalence_constraints or [],
        "expected_dimensions": expected_dimensions or {},
        "equation": equation,
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": evidence_use_fixture(),
        "corrected_claim": corrected_claim,
    }
    if kind == "directional_relation" or contradiction_predicates is not None:
        payload["contradiction_predicates"] = contradiction_predicates or []
    return VerificationRule.model_validate(payload)


def test_rule_quantity_equivalence_rejects_unregistered_same_dimension_conversion_safely():
    """An unreviewed conversion must not escape as an evaluator exception."""
    rule = rule_fixture(
        "sci:rule:closed-quantity-equivalence",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        quantity_equivalence_constraints=[
            {
                "scientific_role": "travel_distance",
                "quantity_kind": "travel_distance",
                "reference_quantity_kind": "travel_distance_reference",
            }
        ],
    )
    packet = claim_fixture(
        "claim:unregistered-equivalent-unit",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        quantities=[
            {"quantity_kind": "travel_distance", "value": 1000, "unit": "millimeter"},
            {"quantity_kind": "travel_distance_reference", "value": 1, "unit": "meter"},
        ],
    )

    evaluation = evaluate_rule(rule, packet.normalized_claim)

    assert evaluation.applicability == "OUTSIDE_DOMAIN"
    assert evaluation.reason_codes == ["UNREGISTERED_QUANTITY_EQUIVALENCE"]


def test_rule_local_empirical_trigger_requires_measurement_instead_of_reusing_another_rule():
    """An equipment-specific claim must stay tied to the rule it is qualifying."""
    rule = rule_fixture(
        "sci:rule:local-empirical-trigger",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        empirical_trigger_conditions=[
            {
                "key": "claim_specificity",
                "operator": "eq",
                "value": "equipment_or_numeric",
            }
        ],
    )
    generic = claim_fixture(
        "claim:local-empirical-generic",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
    )
    equipment_specific = claim_fixture(
        "claim:local-empirical-equipment",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        conditions={"claim_specificity": "equipment_or_numeric"},
    )

    generic_evaluation = evaluate_rule(rule, generic.normalized_claim)
    empirical_evaluation = evaluate_rule(rule, equipment_specific.normalized_claim)

    assert generic_evaluation.applicability == "IN_SCOPE"
    assert generic_evaluation.outcome == "SUPPORTS"
    assert empirical_evaluation.rule_id == rule.rule_id
    assert empirical_evaluation.applicability == "EMPIRICAL_ONLY"
    assert empirical_evaluation.outcome == "UNDECIDED"
    assert empirical_evaluation.reason_codes == ["QUALIFIED_OBSERVATION_REQUIRED"]

    contradicted = equipment_specific.normalized_claim.model_copy(
        update={"predicate": "increases"}
    )
    contradiction = evaluate_rule(rule, contradicted)
    assert contradiction.applicability == "IN_SCOPE"
    assert contradiction.outcome == "CONTRADICTS"
    assert contradiction.reason_codes == ["RULE_CONTRADICTS"]
    assert empirical_evaluation.evidence_refs == [EVIDENCE_REF]


def test_rule_context_dimension_is_executable_for_equivalent_units_and_wrong_dimensions():
    """Unit variation must alter a quantity consumed by the target rule's gate."""
    rule = rule_fixture(
        "sci:rule:typed-context-dimension",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        context_dimensions={"travel_distance": "meter"},
    )
    equivalent = claim_fixture(
        "claim:typed-context-equivalent",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        quantities=[
            {"quantity_kind": "travel_distance", "value": "100", "unit": "centimeter"}
        ],
    )
    incompatible = claim_fixture(
        "claim:typed-context-incompatible",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        quantities=[
            {"quantity_kind": "travel_distance", "value": "1", "unit": "second"}
        ],
    )
    missing = claim_fixture(
        "claim:typed-context-missing",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
    )

    assert evaluate_rule(rule, equivalent.normalized_claim).applicability == "IN_SCOPE"
    wrong = evaluate_rule(rule, incompatible.normalized_claim)
    assert wrong.applicability == "OUTSIDE_DOMAIN"
    assert wrong.reason_codes == ["CONTEXT_DIMENSION_MISMATCH"]
    absent = evaluate_rule(rule, missing.normalized_claim)
    assert absent.applicability == "MISSING_CONDITIONS"
    assert absent.reason_codes == ["MISSING_CONTEXT_QUANTITIES"]


@pytest.mark.parametrize(
    ("quantity_kind", "left_value", "left_unit", "right_value", "right_unit"),
    [
        ("angular_rate", "1", "radian / second", "0.001", "radian / millisecond"),
        ("force", "1", "newton", "1000", "millinewton"),
        ("energy", "1", "joule", "1000", "millijoule"),
        ("pressure", "1", "pascal", "1000", "millipascal"),
        ("molarity", "1", "mole / liter", "1000", "mole / meter ** 3"),
        ("current", "1", "ampere", "1000", "milliampere"),
        ("voltage", "1", "volt", "1000", "millivolt"),
        ("resistance", "1", "ohm", "1000", "milliohm"),
        ("capacitance", "1", "farad", "1000", "millifarad"),
        ("diffusivity", "1", "meter ** 2 / second", "10000", "centimeter ** 2 / second"),
        ("carrier_energy", "1", "electron_volt", "1000", "millielectron_volt"),
        ("conductivity", "1", "siemens / meter", "10", "millisiemens / centimeter"),
        ("thickness", "1", "nanometer", "0.001", "micrometer"),
        ("viscosity", "1", "pascal * second", "1000", "millipascal * second"),
        ("spin_rate", "1", "rpm", "1", "revolution / minute"),
    ],
)
def test_task3_scientific_unit_variants_use_explicit_exact_conversion_registrations(
    quantity_kind: str,
    left_value: str,
    left_unit: str,
    right_value: str,
    right_unit: str,
):
    """Domain qualification must not disguise metre-only probes as general SI support."""
    assert compare_quantities(
        {"quantity_kind": quantity_kind, "value": left_value, "unit": left_unit},
        {"quantity_kind": quantity_kind, "value": right_value, "unit": right_unit},
    ) == 0


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
            contradiction_predicates=["increases"],
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
            required_conditions={"resistance": "fixed"},
            equation={
                "left_quantity_kind": "voltage",
                "right_quantity_kinds": ["current", "resistance_value"],
                "operator": "product",
            },
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
            "semantic_digest": sha256_digest(rule),
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
            {
                "ref": MEASUREMENT_REF,
                "kind": "knowledge",
                "declared_digest": "sha256:" + "c" * 64,
                "actual_digest": "sha256:" + "c" * 64,
            },
            {
                "ref": OTHER_EVIDENCE_REF,
                "kind": "evidence",
                "declared_digest": "sha256:" + "d" * 64,
                "actual_digest": "sha256:" + "d" * 64,
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


def make_rule_set(
    rules: tuple[VerificationRule, ...] | list[VerificationRule],
    release_set: ResolvedReleaseSet,
) -> ResolvedRuleSet:
    components = {component.ref: component for component in release_set.components}
    return ResolvedRuleSet(
        release_set_digest=release_set.combined_digest,
        rules=tuple(
            ReleasedRule(
                rule=rule,
                component_digest=components[rule.rule_id].actual_digest,
                semantic_digest=components[rule.rule_id].semantic_digest or "",
            )
            for rule in rules
        ),
    )


def test_engine_rejects_candidate_release_even_with_a_structurally_valid_rule_set(
    rules: tuple[VerificationRule, ...],
    release_set: ResolvedReleaseSet,
):
    """Qualification-only resolution must not be usable as an active verdict path."""
    candidate = release_set.foundation_release.model_copy(
        update={"status": "release_candidate"}
    )
    candidate_set = ResolvedReleaseSet.from_single_foundation(candidate)
    candidate_rules = make_rule_set(rules, candidate_set)
    claim = claim_fixture(
        "claim:candidate-must-not-evaluate",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )

    with pytest.raises(ScienceOperationalError, match="not operational for verification"):
        verify_claim(claim, candidate_set, rule_set=candidate_rules)


def test_public_engine_rejects_direct_caller_constructed_release_and_rule_sets(
    rules: tuple[VerificationRule, ...],
    release_set: ResolvedReleaseSet,
):
    """Public verification must require a sealed Catalog-issued operational input."""
    claim = claim_fixture(
        "claim:direct-constructed-active",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    rule_set = make_rule_set(rules, release_set)

    with pytest.raises(TypeError, match="Catalog-issued operational verification"):
        verify_operational_claim(claim, release_set, rule_set=rule_set)


def test_operational_capability_cannot_be_constructed_copied_or_serialized():
    """Callers cannot manufacture, mutate, copy, or persist an operational grant."""
    import copy
    import pickle

    from boi_api.app.science.operational import OperationalVerification

    with pytest.raises(TypeError, match="issued only by active ScienceCatalog"):
        OperationalVerification()
    assert not hasattr(OperationalVerification, "model_copy")

    forged = object.__new__(OperationalVerification)
    with pytest.raises(TypeError, match="Catalog-issued operational verification"):
        verify_operational_claim(
            claim_fixture(
                "claim:forged-operational",
                subject="sci:concept:spin-speed",
                relation="monotonic_direction",
                predicate="increases",
                object_="sci:concept:film-thickness",
            ),
            forged,
        )
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(forged)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(forged)


def repin_single_foundation_rule(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
    replacement: VerificationRule,
) -> tuple[ResolvedReleaseSet, ResolvedRuleSet]:
    """Build a coherent single-Foundation fixture around one replacement Rule."""
    semantic_digest = sha256_digest(replacement)
    components = tuple(
        component.model_copy(update={"semantic_digest": semantic_digest})
        if component.ref == replacement.rule_id
        else component
        for component in release_set.foundation_release.components
    )
    foundation = release_set.foundation_release.model_copy(update={"components": components})
    updated_release_set = ResolvedReleaseSet.from_single_foundation(foundation)
    updated_rule_set = ResolvedRuleSet(
        release_set_digest=updated_release_set.combined_digest,
        rules=tuple(
            released.model_copy(
                update={"rule": replacement, "semantic_digest": semantic_digest}
            )
            if released.rule.rule_id == replacement.rule_id
            else released
            for released in rule_set.rules
        ),
    )
    return updated_release_set, updated_rule_set


@pytest.fixture
def release_set(release: ResolvedRelease) -> ResolvedReleaseSet:
    return ResolvedReleaseSet.from_single_foundation(release)


@pytest.fixture
def rule_set(
    rules: tuple[VerificationRule, ...], release_set: ResolvedReleaseSet
) -> ResolvedRuleSet:
    return make_rule_set(rules, release_set)


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
                quantities=[
                    {"quantity_kind": "voltage", "value": "10", "unit": "volt"},
                    {"quantity_kind": "current", "value": "2", "unit": "ampere"},
                    {
                        "quantity_kind": "resistance_value",
                        "value": "5",
                        "unit": "ohm",
                    },
                ],
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
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """A wrong precedence branch or deterministic outcome must fail a named case."""
    packet = verify_claim(claim, release_set, rule_set=rule_set)

    assert packet.verdict is expected, case_id


def test_different_conditions_do_not_create_false_violation(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
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

    packet = verify_claim(claim, release_set, rule_set=rule_set)

    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert packet.corrected_claim is None


@pytest.mark.parametrize(
    ("predicate", "polarity", "expected_outcome"),
    [
        ("decreases", "positive", "SUPPORTS"),
        ("increases", "positive", "CONTRADICTS"),
        ("unchanged", "positive", "UNDECIDED"),
        ("associated_with", "positive", "UNDECIDED"),
        ("becomes_thinner", "positive", "UNDECIDED"),
        ("decreases", "negative", "CONTRADICTS"),
        ("increases", "negative", "SUPPORTS"),
        ("unchanged", "negative", "UNDECIDED"),
    ],
)
def test_directional_rule_only_decides_expected_or_explicit_contradiction(
    predicate: str,
    polarity: str,
    expected_outcome: str,
):
    """Treating every non-expected wording as an opposite direction must fail this table."""
    rule = rule_fixture(
        "sci:rule:directional-explicit-opposites",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
    )
    claim = claim_fixture(
        f"claim:directional:{predicate}:{polarity}",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate=predicate,
        object_="sci:concept:response",
        polarity=polarity,
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == expected_outcome
    assert (evaluation.outcome == "CONTRADICTS") is (
        (predicate == "increases" and polarity == "positive")
        or (predicate == "decreases" and polarity == "negative")
    )


def test_negative_claim_cannot_consist_with_a_satisfied_equation():
    """Ignoring polarity would mark denial of a numerically satisfied equation consistent."""
    rule = rule_fixture(
        "sci:rule:negative-equation",
        "equation_constraint",
        subject="sci:concept:circuit",
        object_="sci:concept:voltage",
        equation={
            "left_quantity_kind": "voltage",
            "right_quantity_kinds": ["current", "resistance"],
            "operator": "product",
        },
    )
    claim = claim_fixture(
        "claim:negative-equation",
        subject="sci:concept:circuit",
        relation="equation",
        predicate="equals",
        object_="sci:concept:voltage",
        polarity="negative",
        quantities=[
            {"quantity_kind": "voltage", "value": "10", "unit": "volt"},
            {"quantity_kind": "current", "value": "2", "unit": "ampere"},
            {"quantity_kind": "resistance", "value": "5", "unit": "ohm"},
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.outcome == "CONTRADICTS"
    assert evaluation.reason_codes == ["NEGATED_EQUATION_SATISFIED"]


def test_negative_claim_cannot_consist_with_a_satisfied_dimension():
    """Ignoring polarity would mark denial of a matching dimension consistent."""
    rule = rule_fixture(
        "sci:rule:negative-dimension",
        "dimension_constraint",
        subject="sci:concept:measurement",
        object_="sci:concept:length",
        expected_dimensions={"measured_length": "meter"},
    )
    claim = claim_fixture(
        "claim:negative-dimension",
        subject="sci:concept:measurement",
        relation="dimensional_relation",
        predicate="has_dimension",
        object_="sci:concept:length",
        polarity="negative",
        quantities=[{"quantity_kind": "measured_length", "value": "3", "unit": "meter"}],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.outcome == "CONTRADICTS"
    assert evaluation.reason_codes == ["NEGATED_DIMENSION_MATCH"]


def test_negative_claim_cannot_consist_with_a_satisfied_validity_proposition():
    """Ignoring polarity would mark denial of the matched validity proposition consistent."""
    rule = rule_fixture(
        "sci:rule:negative-validity",
        "validity_domain",
        subject="sci:concept:model",
        object_="sci:concept:gas",
        validity_conditions={"material_state": "gas"},
    )
    claim = claim_fixture(
        "claim:negative-validity",
        subject="sci:concept:model",
        relation="equation",
        predicate="applies",
        object_="sci:concept:gas",
        polarity="negative",
        material_state="gas",
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.outcome == "CONTRADICTS"
    assert evaluation.reason_codes == ["NEGATED_VALIDITY_DOMAIN_MATCH"]


def test_negative_claim_cannot_consist_with_a_qualified_empirical_proposition():
    """Ignoring polarity would mark denial of a qualified observation consistent."""
    rule = rule_fixture(
        "sci:rule:negative-empirical",
        "empirical_boundary",
        subject="sci:concept:device",
        object_="sci:concept:lifetime",
    )
    claim = claim_fixture(
        "claim:negative-empirical",
        subject="sci:concept:device",
        relation="empirical_relation",
        predicate="lasts",
        object_="sci:concept:lifetime",
        polarity="negative",
    )
    observation = QualifiedObservation(
        observation_id="sci:observation:negative-empirical",
        rule_id=rule.rule_id,
        verified=True,
        measurement_ref=MEASUREMENT_REF,
        evidence_ref=EVIDENCE_REF,
    )

    evaluation = evaluate_rule(
        rule,
        claim.normalized_claim,
        qualified_observations=(observation,),
    )

    assert evaluation.outcome == "CONTRADICTS"
    assert evaluation.reason_codes == ["NEGATED_QUALIFIED_OBSERVATION"]


def test_rule_conditions_reject_primitive_maps_and_accept_typed_constraints():
    """Restoring primitive map equality would discard operator, range, and unit semantics."""
    payload = {
        "rule_id": "sci:rule:typed-condition-schema",
        "rule_kind": "directional_relation",
        "subject_concept_id": "sci:concept:input",
        "object_concept_id": "sci:concept:response",
        "expected_predicate": "decreases",
        "contradiction_predicates": ["increases"],
        "required_conditions": {"temperature": 25},
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": evidence_use_fixture(),
    }

    with pytest.raises(ValidationError, match="required_conditions"):
        VerificationRule.model_validate(payload)

    payload["required_conditions"] = [
        {"key": "temperature", "operator": "eq", "value": 25, "unit": "°C"}
    ]
    assert VerificationRule.model_validate(payload).required_conditions[0].unit == "°C"


def test_rule_requires_typed_evidence_uses_with_exact_reference_identity():
    """Detached evidence refs must not authorize a claim family or purpose."""
    payload = {
        "rule_id": "sci:rule:evidence-use-schema",
        "rule_kind": "directional_relation",
        "subject_concept_id": "sci:concept:input",
        "object_concept_id": "sci:concept:response",
        "expected_predicate": "decreases",
        "contradiction_predicates": ["increases"],
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": [
            {
                "evidence_ref": EVIDENCE_REF,
                "claim_family": "fixture.direction",
                "purpose": "Support only the fixture directional relation.",
            }
        ],
    }

    rule = VerificationRule.model_validate(payload)
    assert rule.evidence_uses[0].evidence_ref == EVIDENCE_REF

    payload["evidence_uses"][0]["evidence_ref"] = OTHER_EVIDENCE_REF
    with pytest.raises(ValidationError, match="exactly match evidence_refs"):
        VerificationRule.model_validate(payload)

    payload["evidence_uses"][0]["evidence_ref"] = EVIDENCE_REF
    payload["evidence_refs"] = [EVIDENCE_REF, EVIDENCE_REF]
    with pytest.raises(ValidationError, match="evidence_refs must be unique"):
        VerificationRule.model_validate(payload)


@pytest.mark.parametrize("missing_field", ["claim_family", "purpose"])
def test_evidence_use_rejects_incomplete_executable_scope(missing_field: str):
    """Every use must state the exact family and purpose checked by the Catalog."""
    payload = {
        "rule_id": "sci:rule:incomplete-evidence-use",
        "rule_kind": "directional_relation",
        "subject_concept_id": "sci:concept:input",
        "object_concept_id": "sci:concept:response",
        "expected_predicate": "decreases",
        "contradiction_predicates": ["increases"],
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": [
            {
                "evidence_ref": EVIDENCE_REF,
                "claim_family": "fixture.direction",
                "purpose": "Support only the fixture directional relation.",
            }
        ],
    }
    del payload["evidence_uses"][0][missing_field]

    with pytest.raises(ValidationError):
        VerificationRule.model_validate(payload)


def test_contradiction_predicates_are_explicit_and_directional_only():
    """Moving or defaulting the opposite-predicate allowlist must fail the Rule schema."""
    directional = {
        "rule_id": "sci:rule:missing-explicit-opposites",
        "rule_kind": "directional_relation",
        "subject_concept_id": "sci:concept:a",
        "object_concept_id": "sci:concept:b",
        "expected_predicate": "increases",
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": evidence_use_fixture(),
    }
    equation = {
        "rule_id": "sci:rule:foreign-explicit-opposites",
        "rule_kind": "equation_constraint",
        "subject_concept_id": "sci:concept:a",
        "object_concept_id": "sci:concept:b",
        "contradiction_predicates": [],
        "equation": {
            "left_quantity_kind": "left",
            "right_quantity_kinds": ["right"],
            "operator": "equal",
        },
        "knowledge_refs": [KNOWLEDGE_REF],
        "evidence_refs": [EVIDENCE_REF],
        "evidence_uses": evidence_use_fixture(),
    }

    with pytest.raises(ValidationError, match="directional_relation"):
        VerificationRule.model_validate(directional)
    with pytest.raises(ValidationError, match="equation_constraint"):
        VerificationRule.model_validate(equation)


def test_typed_condition_normalizes_compatible_units_before_comparison():
    """Comparing 25 Celsius directly with 298.15 Kelvin must not create missing coverage or red."""
    rule = rule_fixture(
        "sci:rule:typed-temperature",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "temperature", "operator": "eq", "value": 25, "unit": "°C"}
        ],
    )
    claim = claim_fixture(
        "claim:typed-temperature",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        typed_conditions=[
            {"condition_id": "temperature", "value": 298.15, "unit": "K"}
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "SUPPORTS"
    assert evaluation.condition_evaluations[0].satisfied is True


def test_typed_condition_range_normalizes_units_at_both_boundaries():
    """Changing range normalization would reject an in-range Kelvin value for a Celsius rule."""
    rule = rule_fixture(
        "sci:rule:typed-temperature-range",
        "validity_domain",
        subject="sci:concept:model",
        object_="sci:concept:material",
        validity_conditions=[
            {
                "key": "temperature",
                "operator": "range",
                "range": {"minimum": 20, "maximum": 30},
                "unit": "°C",
            }
        ],
    )
    claim = claim_fixture(
        "claim:typed-temperature-range",
        subject="sci:concept:model",
        relation="equation",
        predicate="applies",
        object_="sci:concept:material",
        typed_conditions=[
            {"condition_id": "temperature", "value": 298.15, "unit": "K"}
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.condition_evaluations[0].satisfied is True


@pytest.mark.parametrize(
    ("rule_value", "rule_unit", "claim_value", "claim_unit"),
    [
        (1, "meter", 1, "m"),
        (1, "m", 1, "meter"),
        (25, "degree_Celsius", 298.15, "K"),
        (298.15, "kelvin", 25, "degC"),
    ],
)
def test_condition_evaluator_accepts_reviewed_aliases_in_both_orders(
    rule_value: int | float,
    rule_unit: str,
    claim_value: int | float,
    claim_unit: str,
):
    """Alias spelling or argument order must not turn a reviewed condition unregistered."""
    rule = rule_fixture(
        "sci:rule:reviewed-condition-alias",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {
                "key": "setting",
                "operator": "eq",
                "value": rule_value,
                "unit": rule_unit,
            }
        ],
    )
    claim = claim_fixture(
        "claim:reviewed-condition-alias",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="decreases",
        object_="sci:concept:response",
        typed_conditions=[
            {"condition_id": "setting", "value": claim_value, "unit": claim_unit}
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "SUPPORTS"
    assert evaluation.condition_evaluations[0].satisfied is True


def test_typed_condition_missing_required_unit_is_missing_conditions():
    """A bare number cannot satisfy a Rule that declares a measurement unit."""
    rule = rule_fixture(
        "sci:rule:typed-temperature-missing-unit",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "temperature", "operator": "eq", "value": 25, "unit": "°C"}
        ],
    )
    claim = claim_fixture(
        "claim:typed-temperature-missing-unit",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:response",
        conditions={"temperature": 25},
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "MISSING_CONDITIONS"
    assert evaluation.outcome == "UNDECIDED"
    assert "INCOMPATIBLE_CONDITION_UNIT_PRESENCE" in evaluation.reason_codes


def test_same_number_with_incompatible_condition_units_cannot_create_false_red():
    """Treating equal magnitudes as equal conditions must not compare length with time in scope."""
    rule = rule_fixture(
        "sci:rule:typed-incompatible-units",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        validity_conditions=[
            {"key": "window", "operator": "eq", "value": 1, "unit": "meter"}
        ],
    )
    claim = claim_fixture(
        "claim:typed-incompatible-units",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:response",
        typed_conditions=[{"condition_id": "window", "value": 1, "unit": "second"}],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "OUTSIDE_DOMAIN"
    assert evaluation.outcome == "UNDECIDED"
    assert "INCOMPATIBLE_CONDITION_UNITS" in evaluation.reason_codes


@pytest.mark.parametrize(
    "constraint",
    [
        {"key": "setting", "operator": "eq", "value": 1},
        {"key": "setting", "operator": "ne", "value": 2},
        {
            "key": "setting",
            "operator": "range",
            "range": {"minimum": 0, "maximum": 2},
        },
        {"key": "setting", "operator": "gt", "value": 0},
    ],
    ids=["eq", "ne", "range", "ordered"],
)
@pytest.mark.parametrize("unit_side", ["claim", "rule"])
def test_condition_evaluator_requires_symmetric_unit_presence(
    constraint: dict[str, object],
    unit_side: str,
):
    """Dropping either unit-presence check would let an incomparable magnitude gate red."""
    rule_constraint = dict(constraint)
    if unit_side == "rule":
        rule_constraint["unit"] = "second"
    claim_condition: dict[str, object] = {"condition_id": "setting", "value": 1}
    if unit_side == "claim":
        claim_condition["unit"] = "second"
    rule = rule_fixture(
        "sci:rule:symmetric-unit-presence",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[rule_constraint],
    )
    claim = claim_fixture(
        "claim:symmetric-unit-presence",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:response",
        typed_conditions=[claim_condition],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "MISSING_CONDITIONS"
    assert evaluation.outcome == "UNDECIDED"
    assert "INCOMPATIBLE_CONDITION_UNIT_PRESENCE" in evaluation.reason_codes


@pytest.mark.parametrize(
    "constraint",
    [
        {"key": "setting", "operator": "eq", "value": 1},
        {"key": "setting", "operator": "ne", "value": 2},
        {
            "key": "setting",
            "operator": "range",
            "range": {"minimum": 0, "maximum": 2},
        },
        {"key": "setting", "operator": "gte", "value": 1},
    ],
    ids=["eq", "ne", "range", "ordered"],
)
@pytest.mark.parametrize("unit_side", ["claim", "rule"])
def test_verify_claim_cannot_turn_one_sided_condition_unit_red(
    constraint: dict[str, object],
    unit_side: str,
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """One-sided units cannot satisfy a comparison in full verification."""
    rule_constraint = dict(constraint)
    if unit_side == "rule":
        rule_constraint["unit"] = "second"
    claim_condition: dict[str, object] = {"condition_id": "setting", "value": 1}
    if unit_side == "claim":
        claim_condition["unit"] = "second"
    replacement = rule_fixture(
        "sci:rule:spin-direction",
        "directional_relation",
        subject="sci:concept:spin-speed",
        object_="sci:concept:film-thickness",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[rule_constraint],
    )
    pinned_release_set, pinned_rule_set = repin_single_foundation_rule(
        release_set, rule_set, replacement
    )
    claim = claim_fixture(
        "claim:verify-one-sided-condition-unit",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        typed_conditions=[claim_condition],
    )

    packet = verify_claim(claim, pinned_release_set, rule_set=pinned_rule_set)

    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert "INCOMPATIBLE_CONDITION_UNIT_PRESENCE" in packet.reason_codes
    assert packet.corrected_claim is None


@pytest.mark.parametrize("value", ["fixed", True, None])
def test_claim_condition_rejects_a_unit_on_nonnumeric_value(value: object):
    """A categorical or missing value cannot acquire measurement semantics from a unit token."""
    with pytest.raises(ValidationError, match="condition unit requires a numeric value"):
        claim_fixture(
            "claim:nonnumeric-condition-unit",
            subject="sci:concept:input",
            relation="monotonic_direction",
            predicate="increases",
            object_="sci:concept:response",
            typed_conditions=[
                {"condition_id": "setting", "value": value, "unit": "second"}
            ],
        )


@pytest.mark.parametrize("identifier", ["", "   "])
def test_claim_rejects_empty_quantity_kind_and_condition_id(identifier: str):
    """Blank identifiers must not disappear into quantity/condition lookup maps."""
    with pytest.raises(ValidationError, match="nonempty"):
        claim_fixture(
            "claim:empty-quantity-kind",
            subject="sci:concept:input",
            relation="equation",
            predicate="equals",
            object_="sci:concept:output",
            quantities=[{"quantity_kind": identifier, "value": 1, "unit": "meter"}],
        )
    with pytest.raises(ValidationError, match="nonempty"):
        claim_fixture(
            "claim:empty-condition-id",
            subject="sci:concept:input",
            relation="monotonic_direction",
            predicate="increases",
            object_="sci:concept:output",
            typed_conditions=[{"condition_id": identifier, "value": "fixed"}],
        )


def test_claim_rejects_duplicate_quantity_and_condition_identifiers():
    """Last-value-wins maps must not resolve ambiguous repeated scientific inputs."""
    with pytest.raises(ValidationError, match="quantity_kind values must be unique"):
        claim_fixture(
            "claim:duplicate-quantity-kind",
            subject="sci:concept:input",
            relation="equation",
            predicate="equals",
            object_="sci:concept:output",
            quantities=[
                {"quantity_kind": "length", "value": 1, "unit": "meter"},
                {"quantity_kind": "length", "value": 2, "unit": "meter"},
            ],
        )
    with pytest.raises(ValidationError, match="condition_id values must be unique"):
        claim_fixture(
            "claim:duplicate-condition-id",
            subject="sci:concept:input",
            relation="monotonic_direction",
            predicate="increases",
            object_="sci:concept:output",
            typed_conditions=[
                {"condition_id": "temperature", "value": 100, "unit": "°C"},
                {"condition_id": "temperature", "value": 25, "unit": "°C"},
            ],
        )


@pytest.mark.parametrize("reserved", ["process_stage", "material_state"])
def test_claim_condition_ids_cannot_collide_with_reserved_synthetic_conditions(
    reserved: str,
):
    """A typed condition must not override process_stage or material_state lookup."""
    with pytest.raises(ValidationError, match="reserved condition_id"):
        claim_fixture(
            f"claim:reserved-condition:{reserved}",
            subject="sci:concept:input",
            relation="monotonic_direction",
            predicate="increases",
            object_="sci:concept:output",
            typed_conditions=[{"condition_id": reserved, "value": "attacker-value"}],
            process_stage="reviewed-stage",
            material_state="reviewed-state",
        )


@pytest.mark.parametrize(
    ("operator", "expected", "actual"),
    [("eq", 1, True), ("ne", 0, True), ("eq", "1", 1)],
)
def test_unitless_condition_evaluator_rejects_incompatible_scalar_kinds(
    operator: str,
    expected: object,
    actual: object,
):
    """Python bool/numeric equality must not satisfy a decision-changing Rule gate."""
    rule = rule_fixture(
        "sci:rule:typed-scalar-condition",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "setting", "operator": operator, "value": expected}
        ],
    )
    claim = claim_fixture(
        "claim:typed-scalar-condition",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:response",
        typed_conditions=[{"condition_id": "setting", "value": actual}],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "MISSING_CONDITIONS"
    assert evaluation.outcome == "UNDECIDED"
    assert "INCOMPATIBLE_CONDITION_TYPES" in evaluation.reason_codes


def test_verify_claim_cannot_turn_bool_numeric_condition_ambiguity_red(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """Full verification must keep bool distinct from integer before predicate red."""
    replacement = rule_fixture(
        "sci:rule:spin-direction",
        "directional_relation",
        subject="sci:concept:spin-speed",
        object_="sci:concept:film-thickness",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "numeric-setting", "operator": "eq", "value": 1}
        ],
    )
    pinned_release_set, pinned_rule_set = repin_single_foundation_rule(
        release_set, rule_set, replacement
    )
    claim = claim_fixture(
        "claim:verify-bool-numeric-condition",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        typed_conditions=[
            {"condition_id": "numeric-setting", "value": True}
        ],
    )

    packet = verify_claim(claim, pinned_release_set, rule_set=pinned_rule_set)

    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert "INCOMPATIBLE_CONDITION_TYPES" in packet.reason_codes
    assert packet.corrected_claim is None


def test_condition_evaluator_rejects_an_unregistered_cross_unit_conversion():
    """Falling back to Pint would let 1 inch satisfy a 2.54 centimeter red gate."""
    from boi_api.app.science.units import UnregisteredConversionError

    rule = rule_fixture(
        "sci:rule:unregistered-condition-conversion",
        "directional_relation",
        subject="sci:concept:input",
        object_="sci:concept:response",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "distance", "operator": "eq", "value": 2.54, "unit": "centimeter"}
        ],
    )
    claim = claim_fixture(
        "claim:unregistered-condition-conversion",
        subject="sci:concept:input",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:response",
        typed_conditions=[
            {"condition_id": "distance", "value": 1, "unit": "inch"}
        ],
    )

    with pytest.raises(UnregisteredConversionError, match="unregistered"):
        evaluate_rule(rule, claim.normalized_claim)


def test_verify_claim_rejects_unregistered_condition_conversion_before_red(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """The full verifier must not turn an unreviewed Pint conversion into VIOLATION."""
    from boi_api.app.science.units import UnregisteredConversionError

    replacement = rule_fixture(
        "sci:rule:spin-direction",
        "directional_relation",
        subject="sci:concept:spin-speed",
        object_="sci:concept:film-thickness",
        relation="monotonic_direction",
        expected_predicate="decreases",
        contradiction_predicates=["increases"],
        required_conditions=[
            {"key": "distance", "operator": "eq", "value": 2.54, "unit": "centimeter"}
        ],
    )
    pinned_release_set, pinned_rule_set = repin_single_foundation_rule(
        release_set, rule_set, replacement
    )
    claim = claim_fixture(
        "claim:verify-unregistered-condition-conversion",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        typed_conditions=[
            {"condition_id": "distance", "value": 1, "unit": "inch"}
        ],
    )

    with pytest.raises(UnregisteredConversionError, match="unregistered"):
        verify_claim(claim, pinned_release_set, rule_set=pinned_rule_set)


@pytest.mark.parametrize("observation_value", ["unqualified", "false"])
def test_empirical_strings_cannot_qualify_an_observation(
    observation_value: str,
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """A nonblank claim string must not masquerade as reviewed measurement evidence."""
    claim = claim_fixture(
        "claim:device-unqualified-string",
        subject="sci:concept:device",
        relation="empirical_relation",
        predicate="lasts",
        object_="sci:concept:lifetime",
        conditions={"qualified_observation": observation_value},
    )

    packet = verify_claim(claim, release_set, rule_set=rule_set)

    assert packet.verdict is PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED


def test_empirical_rule_requires_a_verified_typed_observation(
    rules: tuple[VerificationRule, ...],
):
    """Only a typed, verified measurement record can satisfy an empirical boundary."""
    claim = claim_fixture(
        "claim:device-qualified-observation",
        subject="sci:concept:device",
        relation="empirical_relation",
        predicate="lasts",
        object_="sci:concept:lifetime",
    )
    device_rule = next(rule for rule in rules if rule.rule_id == "sci:rule:device-lifetime")
    unverified = QualifiedObservation(
        observation_id="sci:observation:device-unverified",
        rule_id=device_rule.rule_id,
        verified=False,
        measurement_ref=MEASUREMENT_REF,
        evidence_ref=EVIDENCE_REF,
    )
    verified = unverified.model_copy(
        update={"observation_id": "sci:observation:device-verified", "verified": True}
    )

    rejected = evaluate_rule(
        device_rule,
        claim.normalized_claim,
        qualified_observations=(unverified,),
    )
    accepted = evaluate_rule(
        device_rule,
        claim.normalized_claim,
        qualified_observations=(verified,),
    )

    assert rejected.applicability == "EMPIRICAL_ONLY"
    assert accepted.applicability == "IN_SCOPE"
    assert accepted.outcome == "SUPPORTS"


@pytest.mark.parametrize(
    ("verified", "measurement_ref", "evidence_ref", "expected"),
    [
        (True, MEASUREMENT_REF, EVIDENCE_REF, PrimaryVerdict.CONSISTENT),
        (False, MEASUREMENT_REF, EVIDENCE_REF, PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED),
        (
            True,
            "sci:knowledge:unresolved-measurement",
            EVIDENCE_REF,
            PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED,
        ),
        (
            True,
            MEASUREMENT_REF,
            OTHER_EVIDENCE_REF,
            PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED,
        ),
    ],
)
def test_empirical_observation_must_be_verified_and_release_grounded(
    verified: bool,
    measurement_ref: str,
    evidence_ref: str,
    expected: PrimaryVerdict,
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """Verification, measurement pinning, and exact Rule Evidence are all mandatory."""
    claim = claim_fixture(
        "claim:device-observation-grounding",
        subject="sci:concept:device",
        relation="empirical_relation",
        predicate="lasts",
        object_="sci:concept:lifetime",
    )
    observation = QualifiedObservation(
        observation_id="sci:observation:device-grounding",
        rule_id="sci:rule:device-lifetime",
        verified=verified,
        measurement_ref=measurement_ref,
        evidence_ref=evidence_ref,
    )

    packet = verify_claim(
        claim,
        release_set,
        rule_set=rule_set,
        qualified_observations=(observation,),
    )

    assert packet.verdict is expected


def test_contradiction_candidate_cannot_override_missing_conditions_or_domain(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
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

    missing_packet = verify_claim(missing, release_set, rule_set=rule_set)
    outside_packet = verify_claim(outside, release_set, rule_set=rule_set)

    assert missing_packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert outside_packet.verdict is PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
    assert missing_packet.corrected_claim is None
    assert outside_packet.corrected_claim is None


def test_unresolved_ambiguity_stops_before_rule_evaluation(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
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
        verify_claim(claim, release_set, rule_set=rule_set)


def test_incompatible_release_set_is_an_operational_error_not_a_verdict(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """Release incompatibility must never be reported as absent scientific information."""
    incompatible = release_set.model_copy(
        update={
            "compatibility": release_set.compatibility.model_copy(
                update={"compatible": False}
            )
        }
    )
    claim = claim_fixture(
        "claim:incompatible-release-set",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )

    with pytest.raises(ScienceOperationalError, match="INCOMPATIBLE_RELEASE_SET"):
        verify_claim(claim, incompatible, rule_set=rule_set)


def test_release_must_pin_the_rule_and_every_explanation_reference(
    release: ResolvedRelease,
    rule_set: ResolvedRuleSet,
):
    """An unpinned rule or citation must never ground a deterministic verdict."""
    claim = claim_fixture(
        "claim:ohm-grounding",
        subject="sci:concept:voltage",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:current",
        conditions={"resistance": "fixed"},
        quantities=[
            {"quantity_kind": "voltage", "value": "10", "unit": "volt"},
            {"quantity_kind": "current", "value": "2", "unit": "ampere"},
            {"quantity_kind": "resistance_value", "value": "5", "unit": "ohm"},
        ],
    )
    unpinned = release.model_copy(
        update={
            "components": tuple(
                component for component in release.components if component.ref != "sci:rule:ohm"
            )
        }
    )

    with pytest.raises(
        ScienceOperationalError,
        match="RULE_SET_RELEASE_SET_MISMATCH",
    ):
        verify_claim(
            claim,
            ResolvedReleaseSet.from_single_foundation(unpinned),
            rule_set=rule_set,
        )


def test_omitting_any_release_pinned_rule_fails_complete_coverage(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
):
    """Supplying only the decisive rule must not bypass exact Release completeness."""
    claim = claim_fixture(
        "claim:spin-omitted-release-rule",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    omitted = rule_set.model_copy(
        update={
            "rules": tuple(
                released
                for released in rule_set.rules
                if released.rule.rule_id == "sci:rule:spin-direction"
            )
        }
    )

    with pytest.raises(ScienceOperationalError, match="RULE_SET_INCOMPLETE"):
        verify_claim(claim, release_set, rule_set=omitted)


def test_same_id_substituted_rule_body_fails_semantic_integrity(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
):
    """Keeping a pinned ID while changing its semantic body must not authorize a verdict."""
    claim = claim_fixture(
        "claim:spin-substituted-body",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    substituted = rule_set.model_copy(
        update={
            "rules": tuple(
                released.model_copy(
                    update={
                        "rule": released.rule.model_copy(
                            update={"expected_predicate": "increases"}
                        )
                    }
                )
                if released.rule.rule_id == "sci:rule:spin-direction"
                else released
                for released in rule_set.rules
            )
        }
    )

    with pytest.raises(ScienceOperationalError, match="RULE_SEMANTIC_DIGEST_MISMATCH"):
        verify_claim(claim, release_set, rule_set=substituted)


def test_substituted_rule_cannot_replace_the_resolved_component_semantic_digest(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
):
    """Rehashing a substituted body cannot replace the semantic digest pinned by Release."""
    claim = claim_fixture(
        "claim:spin-substituted-rehashed-body",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    substituted_rules: list[ReleasedRule] = []
    for released in rule_set.rules:
        if released.rule.rule_id != "sci:rule:spin-direction":
            substituted_rules.append(released)
            continue
        substituted_rule = released.rule.model_copy(update={"expected_predicate": "increases"})
        substituted_rules.append(
            released.model_copy(
                update={
                    "rule": substituted_rule,
                    "semantic_digest": sha256_digest(substituted_rule),
                }
            )
        )
    substituted = rule_set.model_copy(update={"rules": tuple(substituted_rules)})

    with pytest.raises(ScienceOperationalError, match="RULE_SEMANTIC_DIGEST_MISMATCH"):
        verify_claim(claim, release_set, rule_set=substituted)


def test_released_rule_component_digest_must_match_exact_release_component(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
):
    """A semantic match cannot compensate for a different OKF component digest."""
    claim = claim_fixture(
        "claim:spin-component-digest",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    altered = rule_set.model_copy(
        update={
            "rules": tuple(
                released.model_copy(update={"component_digest": "sha256:" + "9" * 64})
                if released.rule.rule_id == "sci:rule:spin-direction"
                else released
                for released in rule_set.rules
            )
        }
    )

    with pytest.raises(ScienceOperationalError, match="RULE_COMPONENT_DIGEST_MISMATCH"):
        verify_claim(claim, release_set, rule_set=altered)


def test_extra_unpinned_rule_fails_exact_release_coverage(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
):
    """An otherwise valid unpinned Rule cannot expand an immutable Release."""
    claim = claim_fixture(
        "claim:spin-extra-rule",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )
    spin = next(
        released
        for released in rule_set.rules
        if released.rule.rule_id == "sci:rule:spin-direction"
    )
    extra_rule = spin.rule.model_copy(update={"rule_id": "sci:rule:unpinned-extra"})
    extra = ReleasedRule(
        rule=extra_rule,
        component_digest="sha256:" + "e" * 64,
        semantic_digest=sha256_digest(extra_rule),
    )
    expanded = rule_set.model_copy(update={"rules": (*rule_set.rules, extra)})

    with pytest.raises(ScienceOperationalError, match="RULE_SET_HAS_EXTRA_RULES"):
        verify_claim(claim, release_set, rule_set=expanded)


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_rule_ids_are_rejected_before_evaluation_in_any_order(
    reverse: bool,
    rule_set: ResolvedRuleSet,
):
    """Duplicate rule IDs must fail before their order can influence a verdict."""
    spin = next(
        released
        for released in rule_set.rules
        if released.rule.rule_id == "sci:rule:spin-direction"
    )
    duplicated = [*rule_set.rules, spin]
    if reverse:
        duplicated.reverse()

    with pytest.raises(ValidationError, match="duplicate rule ID"):
        ResolvedRuleSet(
            release_set_digest=rule_set.release_set_digest,
            rules=tuple(duplicated),
        )


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
        quantities=[
            {"quantity_kind": "voltage", "value": "10", "unit": "volt"},
            {"quantity_kind": "current", "value": "2", "unit": "ampere"},
            {"quantity_kind": "resistance_value", "value": "5", "unit": "ohm"},
        ],
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
            "operator": "eq",
            "expected": "fixed",
            "actual": "fixed",
            "expected_unit": None,
            "actual_unit": None,
            "satisfied": True,
            "reason_code": "CONDITION_SATISFIED",
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


def test_incompatible_equation_operands_are_rejected_not_contradicted():
    """A malformed equation input must never become a scientific violation."""
    rule = rule_fixture(
        "sci:rule:equation-dimensions",
        "equation_constraint",
        subject="sci:concept:circuit",
        object_="sci:concept:voltage",
        equation={
            "left_quantity_kind": "voltage",
            "right_quantity_kinds": ["current", "duration"],
            "operator": "product",
        },
    )
    claim = claim_fixture(
        "claim:equation-dimensions",
        subject="sci:concept:circuit",
        relation="equation",
        predicate="equals",
        object_="sci:concept:voltage",
        quantities=[
            {"quantity_kind": "voltage", "value": "10", "unit": "volt"},
            {"quantity_kind": "current", "value": "2", "unit": "ampere"},
            {"quantity_kind": "duration", "value": "5", "unit": "second"},
        ],
    )

    with pytest.raises(IncompatibleDimensionsError, match="incompatible equation dimensions"):
        evaluate_rule(rule, claim.normalized_claim)


def test_equation_evaluator_rejects_an_unregistered_cross_unit_conversion():
    """An equal equation must not use Pint to equate inch with centimeter implicitly."""
    from boi_api.app.science.units import UnregisteredConversionError

    rule = rule_fixture(
        "sci:rule:unregistered-equation-conversion",
        "equation_constraint",
        subject="sci:concept:length-comparison",
        object_="sci:concept:length",
        equation={
            "left_quantity_kind": "left_length",
            "right_quantity_kinds": ["right_length"],
            "operator": "equal",
        },
    )
    claim = claim_fixture(
        "claim:unregistered-equation-conversion",
        subject="sci:concept:length-comparison",
        relation="equation",
        predicate="equals",
        object_="sci:concept:length",
        quantities=[
            {"quantity_kind": "left_length", "value": 1, "unit": "inch"},
            {"quantity_kind": "right_length", "value": 2.54, "unit": "centimeter"},
        ],
    )

    with pytest.raises(UnregisteredConversionError, match="unregistered"):
        evaluate_rule(rule, claim.normalized_claim)


def test_product_equation_rejects_unregistered_composite_unit_conversion():
    """Pint scaling of composite inch units must not decide an area equation."""
    from boi_api.app.science.units import UnregisteredConversionError

    rule = rule_fixture(
        "sci:rule:unregistered-product-conversion",
        "equation_constraint",
        subject="sci:concept:area-comparison",
        object_="sci:concept:area",
        equation={
            "left_quantity_kind": "area",
            "right_quantity_kinds": ["width", "height"],
            "operator": "product",
        },
    )
    claim = claim_fixture(
        "claim:unregistered-product-conversion",
        subject="sci:concept:area-comparison",
        relation="equation",
        predicate="equals",
        object_="sci:concept:area",
        quantities=[
            {"quantity_kind": "area", "value": 6.4516, "unit": "centimeter ** 2"},
            {"quantity_kind": "width", "value": 1, "unit": "inch"},
            {"quantity_kind": "height", "value": 1, "unit": "inch"},
        ],
    )

    with pytest.raises(UnregisteredConversionError, match="unregistered"):
        evaluate_rule(rule, claim.normalized_claim)


@pytest.mark.parametrize(
    ("left_unit", "right_unit"),
    [("V", "volt"), ("volt", "V")],
)
def test_equal_equation_accepts_reviewed_voltage_aliases_in_both_orders(
    left_unit: str,
    right_unit: str,
):
    """An equal equation over a reviewed alias family must not require a new conversion."""
    rule = rule_fixture(
        "sci:rule:reviewed-equal-alias",
        "equation_constraint",
        subject="sci:concept:voltage-comparison",
        object_="sci:concept:voltage",
        equation={
            "left_quantity_kind": "left_voltage",
            "right_quantity_kinds": ["right_voltage"],
            "operator": "equal",
        },
    )
    claim = claim_fixture(
        "claim:reviewed-equal-alias",
        subject="sci:concept:voltage-comparison",
        relation="equation",
        predicate="equals",
        object_="sci:concept:voltage",
        quantities=[
            {"quantity_kind": "left_voltage", "value": 10, "unit": left_unit},
            {"quantity_kind": "right_voltage", "value": 10, "unit": right_unit},
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "SUPPORTS"


@pytest.mark.parametrize(
    ("right_kinds", "quantities"),
    [
        (
            ["current", "resistance"],
            [
                {"quantity_kind": "current", "value": 2, "unit": "A"},
                {"quantity_kind": "resistance", "value": 5, "unit": "Ω"},
            ],
        ),
        (
            ["resistance", "current"],
            [
                {"quantity_kind": "resistance", "value": 5, "unit": "ohm"},
                {"quantity_kind": "current", "value": 2, "unit": "ampere"},
            ],
        ),
    ],
    ids=["symbol-aliases", "commuted-product"],
)
def test_ohm_law_product_uses_reviewed_aliases_and_commutative_canonical_order(
    right_kinds: list[str],
    quantities: list[dict[str, object]],
):
    """Changing alias or factor order must retain the one reviewed Ohm-law conversion."""
    rule = rule_fixture(
        "sci:rule:reviewed-ohm-product-alias",
        "equation_constraint",
        subject="sci:concept:circuit",
        object_="sci:concept:voltage",
        equation={
            "left_quantity_kind": "voltage",
            "right_quantity_kinds": right_kinds,
            "operator": "product",
        },
    )
    claim = claim_fixture(
        "claim:reviewed-ohm-product-alias",
        subject="sci:concept:circuit",
        relation="equation",
        predicate="equals",
        object_="sci:concept:voltage",
        quantities=[
            {"quantity_kind": "voltage", "value": 10, "unit": "V"},
            *quantities,
        ],
    )

    evaluation = evaluate_rule(rule, claim.normalized_claim)

    assert evaluation.applicability == "IN_SCOPE"
    assert evaluation.outcome == "SUPPORTS"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "rule_id": "sci:rule:directional-equation-only",
            "rule_kind": "directional_relation",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "equation": {
                "left_quantity_kind": "left",
                "right_quantity_kinds": ["right"],
                "operator": "equal",
            },
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
        {
            "rule_id": "sci:rule:equation-predicate-only",
            "rule_kind": "equation_constraint",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "expected_predicate": "increases",
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
        {
            "rule_id": "sci:rule:directional-dimension-payload",
            "rule_kind": "directional_relation",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "expected_predicate": "increases",
            "expected_dimensions": {"length": "meter"},
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
        {
            "rule_id": "sci:rule:equation-directional-polarity",
            "rule_kind": "equation_constraint",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "expected_polarity": "negative",
            "equation": {
                "left_quantity_kind": "left",
                "right_quantity_kinds": ["right"],
                "operator": "equal",
            },
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
        {
            "rule_id": "sci:rule:validity-correction",
            "rule_kind": "validity_domain",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "validity_conditions": [
                {"key": "material_state", "operator": "eq", "value": "gas"}
            ],
            "corrected_claim": "This evaluator cannot produce a correction.",
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
        {
            "rule_id": "sci:rule:empirical-correction",
            "rule_kind": "empirical_boundary",
            "subject_concept_id": "sci:concept:a",
            "object_concept_id": "sci:concept:b",
            "corrected_claim": "Observation is not a deterministic correction.",
            "knowledge_refs": [KNOWLEDGE_REF],
            "evidence_refs": [EVIDENCE_REF],
            "evidence_uses": evidence_use_fixture(),
        },
    ],
)
def test_rule_kind_rejects_payload_for_a_different_evaluator(payload: dict[str, object]):
    """A rule kind must not smuggle fields interpreted by another evaluator."""
    with pytest.raises(ValidationError, match="rule kind payload"):
        VerificationRule.model_validate(payload)


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


@pytest.mark.parametrize(
    ("left_unit", "right_unit"),
    [
        ("K", "kelvin"),
        ("°C", "degC"),
        ("degC", "degree_Celsius"),
        ("m", "meter"),
        ("cm", "centimeter"),
        ("V", "volt"),
        ("A", "ampere"),
        ("Ω", "ohm"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_every_registered_unit_family_has_reviewed_alias_normalization(
    left_unit: str,
    right_unit: str,
    reverse: bool,
):
    """Removing any reviewed alias must fail equality in at least one argument order."""
    if reverse:
        left_unit, right_unit = right_unit, left_unit

    assert compare_quantities(
        {"quantity_kind": "left", "value": 1, "unit": left_unit},
        {"quantity_kind": "right", "value": 1, "unit": right_unit},
    ) == 0


@pytest.mark.parametrize(
    ("left_value", "left_unit", "right_value", "right_unit"),
    [
        (1, "m", 100, "cm"),
        (100, "centimeter", 1, "meter"),
        (25, "degree_Celsius", 298.15, "K"),
        (298.15, "kelvin", 25, "degC"),
    ],
)
def test_registered_conversions_accept_canonical_aliases_in_both_directions(
    left_value: int | float,
    left_unit: str,
    right_value: int | float,
    right_unit: str,
):
    """Alias normalization must happen before exact reviewed conversion lookup."""
    assert compare_quantities(
        {"quantity_kind": "left", "value": left_value, "unit": left_unit},
        {"quantity_kind": "right", "value": right_value, "unit": right_unit},
    ) == 0


@pytest.mark.parametrize(
    ("source_unit", "target_unit", "kind"),
    [
        ("K", "kelvin", "affine"),
        ("degC", "degree_Celsius", "affine"),
        ("m", "meter", "multiplicative"),
        ("cm", "centimeter", "multiplicative"),
        ("V", "volt", "multiplicative"),
        ("A", "ampere", "multiplicative"),
        ("Ω", "ohm", "multiplicative"),
    ],
)
def test_convert_value_treats_reviewed_aliases_as_identity_before_lookup(
    source_unit: str,
    target_unit: str,
    kind: str,
):
    """Canonical aliases are one unit and must not require an invented conversion entry."""
    from boi_api.app.science.models import ConversionKind
    from boi_api.app.science.units import convert_value

    assert convert_value(
        Decimal("1"),
        source_unit,
        target_unit,
        kind=ConversionKind(kind),
    ) == Decimal("1")


def test_allowlisted_multiplicative_and_affine_conversions_use_decimal_arithmetic():
    """Changing scale/offset handling or falling back to float must break exact conversions."""
    from boi_api.app.science.models import ConversionKind
    from boi_api.app.science.units import convert_value

    assert convert_value(
        Decimal("100"), "centimeter", "meter", kind=ConversionKind.MULTIPLICATIVE
    ) == Decimal("1.00")
    assert convert_value(
        Decimal("25"), "°C", "K", kind=ConversionKind.AFFINE
    ) == Decimal("298.15")
    assert convert_value(
        Decimal("10"), "°C", "K", kind=ConversionKind.AFFINE, interval=True
    ) == Decimal("10")
    assert compare_quantities(
        {"quantity_kind": "temperature", "value": "25", "unit": "°C"},
        {"quantity_kind": "temperature", "value": "298.15", "unit": "K"},
    ) == 0


def test_logarithmic_and_unregistered_procedure_conversions_fail_explicitly():
    """Removing the kind gate would let Pint or an arbitrary procedure invent a conversion."""
    from boi_api.app.science.models import ConversionKind
    from boi_api.app.science.units import (
        UnregisteredConversionError,
        UnsupportedConversionError,
        convert_value,
    )

    with pytest.raises(UnsupportedConversionError, match="logarithmic conversion is unsupported"):
        convert_value(Decimal("3"), "dB", "ratio", kind=ConversionKind.LOGARITHMIC)
    with pytest.raises(UnregisteredConversionError, match="procedure conversion is unregistered"):
        convert_value(
            Decimal("7"),
            "instrument_count",
            "concentration",
            kind=ConversionKind.PROCEDURE_DEFINED,
            conversion_id="procedure:unregistered",
        )


def test_ambiguous_ph_token_is_not_parsed_as_an_si_prefix_unit():
    """Removing the denylist would silently interpret pH as picohenry."""
    from boi_api.app.science.units import AmbiguousUnitError, expected_dimensionality

    with pytest.raises(AmbiguousUnitError, match="ambiguous unit token: pH"):
        validate_quantity({"quantity_kind": "acidity", "value": "7", "unit": "pH"})
    with pytest.raises(AmbiguousUnitError, match="ambiguous unit token: pH"):
        expected_dimensionality("pH")


AMBIGUOUS_COMPOSITE_PH_UNITS = [
    pytest.param("pH / meter", id="division"),
    pytest.param("pH ** 2", id="exponent"),
    pytest.param("pH²", id="unicode-exponent"),
    pytest.param("meter * pH * second", id="three-factor"),
    pytest.param("meter / (pH * second)", id="parenthesized"),
]


@pytest.mark.parametrize("unit", AMBIGUOUS_COMPOSITE_PH_UNITS)
def test_composite_ph_is_rejected_at_claim_and_rule_schema_boundaries(unit: str):
    """Any standalone pH identifier in a unit expression must fail before storage."""
    with pytest.raises(ValidationError, match="ambiguous unit token: pH"):
        claim_fixture(
            "claim:ambiguous-composite-ph-schema",
            subject="sci:concept:sample",
            relation="dimensional_relation",
            predicate="has_gradient",
            object_="sci:concept:gradient",
            quantities=[{"quantity_kind": "gradient", "value": 7, "unit": unit}],
        )
    with pytest.raises(ValidationError, match="ambiguous unit token: pH"):
        rule_fixture(
            "sci:rule:ambiguous-composite-ph-schema",
            "dimension_constraint",
            subject="sci:concept:sample",
            object_="sci:concept:gradient",
            expected_dimensions={"gradient": unit},
        )


def _stored_dimension_pair_with_unvalidated_unit(
    unit: str,
    *,
    polarity: str = "positive",
    rule_id: str = "sci:rule:stored-composite-ph",
) -> tuple[VerificationRule, ClaimPacket]:
    """Model a previously stored payload so evaluators retain their own boundary."""
    rule = rule_fixture(
        rule_id,
        "dimension_constraint",
        subject="sci:concept:sample",
        object_="sci:concept:gradient",
        expected_dimensions={"gradient": "meter"},
    ).model_copy(update={"expected_dimensions": {"gradient": unit}})
    claim = claim_fixture(
        "claim:stored-composite-ph",
        subject="sci:concept:sample",
        relation="dimensional_relation",
        predicate="has_gradient",
        object_="sci:concept:gradient",
        polarity=polarity,
        quantities=[{"quantity_kind": "gradient", "value": 7, "unit": "meter"}],
    )
    quantity = claim.normalized_claim.quantities[0].model_copy(update={"unit": unit})
    normalized = claim.normalized_claim.model_copy(update={"quantities": [quantity]})
    return rule, claim.model_copy(update={"normalized_claim": normalized})


@pytest.mark.parametrize("unit", AMBIGUOUS_COMPOSITE_PH_UNITS)
def test_dimension_evaluator_rejects_composite_ph_in_stored_payloads(unit: str):
    """A stored schema bypass must not let Pint turn composite pH into picohenry."""
    from boi_api.app.science.units import AmbiguousUnitError

    rule, claim = _stored_dimension_pair_with_unvalidated_unit(unit)

    with pytest.raises(AmbiguousUnitError, match="ambiguous unit token: pH"):
        evaluate_rule(rule, claim.normalized_claim)


@pytest.mark.parametrize("unit", AMBIGUOUS_COMPOSITE_PH_UNITS)
def test_comparison_boundary_rejects_composite_ph(unit: str):
    """Identical ambiguous expressions must not short-circuit to numeric equality."""
    from boi_api.app.science.units import AmbiguousUnitError

    quantity = {"quantity_kind": "gradient", "value": 7, "unit": unit}

    with pytest.raises(AmbiguousUnitError, match="ambiguous unit token: pH"):
        compare_quantities(quantity, quantity)


@pytest.mark.parametrize("polarity", ["positive", "negative"])
@pytest.mark.parametrize("unit", AMBIGUOUS_COMPOSITE_PH_UNITS)
def test_verify_claim_never_selects_a_verdict_for_composite_ph(
    unit: str,
    polarity: str,
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
):
    """Neither matching nor negated composite pH dimensions may reach verdict selection."""
    from boi_api.app.science.units import AmbiguousUnitError

    replacement, claim = _stored_dimension_pair_with_unvalidated_unit(
        unit,
        polarity=polarity,
        rule_id="sci:rule:spin-direction",
    )
    pinned_release_set, pinned_rule_set = repin_single_foundation_rule(
        release_set, rule_set, replacement
    )

    with pytest.raises(AmbiguousUnitError, match="ambiguous unit token: pH"):
        verify_claim(claim, pinned_release_set, rule_set=pinned_rule_set)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("pHase", "pHase"),
        ("alpha_pH", "alpha_pH"),
        ("pH2", "pH2"),
        ("A * Ω", "ampere * ohm"),
        ("Ω * A", "ampere * ohm"),
    ],
)
def test_ph_lexical_guard_preserves_other_identifiers_and_reviewed_products(
    unit: str,
    expected: str,
):
    """Substring matches must not reject identifiers or alter reviewed products."""
    from boi_api.app.science.models import canonical_science_unit_token

    assert canonical_science_unit_token(unit) == expected


@pytest.mark.parametrize("unit", ["pH ", " pH", "\tpH\n"])
def test_whitespace_ph_variants_are_rejected_at_claim_and_rule_boundaries(unit: str):
    """Removing token canonicalization would let Pint reinterpret whitespace pH as picohenry."""
    with pytest.raises(ValidationError, match="ambiguous unit token: pH"):
        claim_fixture(
            "claim:ambiguous-ph-boundary",
            subject="sci:concept:sample",
            relation="dimensional_relation",
            predicate="has_acidity",
            object_="sci:concept:acidity",
            quantities=[{"quantity_kind": "acidity", "value": 7, "unit": unit}],
        )
    with pytest.raises(ValidationError, match="ambiguous unit token: pH"):
        rule_fixture(
            "sci:rule:ambiguous-ph-boundary",
            "dimension_constraint",
            subject="sci:concept:sample",
            object_="sci:concept:acidity",
            expected_dimensions={"acidity": unit},
        )


def test_claim_and_rule_units_are_canonicalized_at_their_schema_boundaries():
    """Keeping surrounding whitespace would make allowlist keys depend on spelling noise."""
    claim = claim_fixture(
        "claim:canonical-unit-token",
        subject="sci:concept:sample",
        relation="dimensional_relation",
        predicate="has_length",
        object_="sci:concept:length",
        quantities=[{"quantity_kind": "length", "value": 1, "unit": " meter "}],
        typed_conditions=[
            {"condition_id": "temperature", "value": 25, "unit": " °C "}
        ],
    )
    rule = rule_fixture(
        "sci:rule:canonical-unit-token",
        "dimension_constraint",
        subject="sci:concept:sample",
        object_="sci:concept:length",
        expected_dimensions={"length": " meter "},
        required_conditions=[
            {"key": "temperature", "operator": "eq", "value": 25, "unit": " °C "}
        ],
    )

    assert claim.normalized_claim.quantities[0].unit == "meter"
    assert claim.normalized_claim.conditions[0].unit == "°C"
    assert rule.expected_dimensions == {"length": "meter"}
    assert rule.required_conditions[0].unit == "°C"


def test_verdict_packet_is_byte_stable_and_only_violation_has_a_correction(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
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

    first = verify_claim(claim, release_set, rule_set=rule_set)
    reversed_rule_set = rule_set.model_copy(update={"rules": tuple(reversed(rule_set.rules))})
    second = verify_claim(claim, release_set, rule_set=reversed_rule_set)

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first.corrected_claim == (
        "At fixed conditions, increasing spin speed decreases film thickness."
    )
    assert all(fact.knowledge_refs and fact.evidence_refs for fact in first.explanation_facts)


def test_verdict_preserves_complete_release_selection_and_exact_digests(
    release: ResolvedRelease,
    rule_set: ResolvedRuleSet,
):
    """Collapsing every resolved Rule into Foundation must lose this role-exact record."""
    from boi_api.app.science.models import (
        ReleaseCompatibilityResult,
        ReleaseSelection,
        ResolvedReleaseSet,
    )

    domain = release.model_copy(
        update={
            "release_id": "sci-release:domain:0.1.0",
            "content_hash": "sha256:" + "1" * 64,
            "components": (),
            "component_digests": {},
            "known_limitations": ["domain-fixture"],
        }
    )
    application = release.model_copy(
        update={
            "release_id": "sci-release:application:0.1.0",
            "content_hash": "sha256:" + "2" * 64,
            "components": (),
            "component_digests": {},
            "known_limitations": ["application-fixture"],
        }
    )
    selection = ReleaseSelection(
        foundation=release.release_id,
        domains=[domain.release_id],
        applications=[application.release_id],
    )
    combined_components = tuple(sorted(release.components, key=lambda item: item.ref))
    release_digests = {
        release.release_id: release.content_hash,
        domain.release_id: domain.content_hash,
        application.release_id: application.content_hash,
    }
    compatibility = ReleaseCompatibilityResult(
        compatible=True,
        checked_pack_dependencies=(),
    )
    release_set = ResolvedReleaseSet(
        selection=selection,
        foundation_release=release,
        domain_releases=(domain,),
        application_releases=(application,),
        compatibility=compatibility,
        release_digests=release_digests,
        combined_digest=ResolvedReleaseSet.combined_digest_for(
            selection,
            release_digests,
            combined_components,
            compatibility,
        ),
        components=combined_components,
        rule_components=tuple(
            component for component in combined_components if component.kind == "rule"
        ),
    )
    combined_rules = ResolvedRuleSet(
        release_set_digest=release_set.combined_digest,
        rules=rule_set.rules,
    )
    claim = claim_fixture(
        "claim:complete-release-selection",
        subject="sci:concept:spin-speed",
        relation="monotonic_direction",
        predicate="increases",
        object_="sci:concept:film-thickness",
        conditions={"resist": "same", "viscosity": "same"},
        process_stage="final-coat",
    )

    packet = verify_claim(claim, release_set, rule_set=combined_rules)

    assert packet.verdict is PrimaryVerdict.VIOLATION
    assert packet.releases.selection == selection
    assert packet.releases.digests == release_set.release_digests
    assert packet.releases.combined_digest == release_set.combined_digest
    assert packet.limitations == ["application-fixture", "domain-fixture", "fixture-only"]
