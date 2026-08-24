from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

import pytest

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.engine import verify_claim
from boi_api.app.science.exceptions import ScienceOperationalError
from boi_api.app.science.models import (
    ClaimPacket,
    ClaimQuantity,
    PrimaryVerdict,
    ResolvedComponent,
    ResolvedRelease,
    ResolvedReleaseSet,
)
from boi_api.app.science.operational import OperationalVerification
from boi_api.app.science.rules import (
    QualificationRuleSet,
    QualifiedObservation,
    VerificationRule,
    evaluate_rule,
)
from boi_api.app.science.units import (
    compare_quantities,
    expected_dimensionality,
    validate_quantity,
)


BOI_ROOT = Path(__file__).resolve().parents[1] / "data" / "boi"
FOUNDATION_PACK_ID = "sci-pack:science-foundation/0.1.0"
PACKS = {
    "physical-principles": ("physics", 5),
    "chemical-principles": ("chemistry", 5),
    "circuit-principles": ("circuits", 6),
    "materials-science": ("materials", 5),
    "semiconductor-devices": ("semiconductor-devices", 6),
    "spin-coating": ("spin-coating", 5),
}
PACK_IDS = {
    name: f"sci-pack:{name}/0.1.0" for name in PACKS
}
EXPECTED_DEPENDENCIES = {
    "physical-principles": [("depends_on", FOUNDATION_PACK_ID)],
    "chemical-principles": [("depends_on", FOUNDATION_PACK_ID)],
    "circuit-principles": [("depends_on", FOUNDATION_PACK_ID)],
    "materials-science": [("depends_on", FOUNDATION_PACK_ID)],
    "semiconductor-devices": [
        ("depends_on", "sci-pack:materials-science/0.1.0")
    ],
    "spin-coating": [
        ("depends_on", "sci-pack:physical-principles/0.1.0"),
        ("depends_on", "sci-pack:chemical-principles/0.1.0"),
        ("depends_on", "sci-pack:materials-science/0.1.0"),
    ],
}
REQUIRED_TEN_CASE_KINDS = {
    "clear_violation",
    "in_scope_consistency",
    "missing_required_condition",
    "outside_validity_domain",
    "empirical_verification_required",
    "negation",
    "unit_variation",
    "decision_changing_ambiguity",
    "paraphrase",
    "false_red_prevention",
}
DOMAIN_BINDING_IDS = {
    f"sci:binding:domain:{slug}"
    for slug in (
        "angular-speed",
        "viscosity",
        "catalyst",
        "equilibrium-constant",
        "resistance",
        "electric-power",
        "bulk-property",
        "thin-film-property",
        "semiconductor",
        "mobility",
        "conductivity",
        "spin-speed",
        "film-thickness",
        "photoresist",
    )
}


@pytest.fixture(scope="module")
def science_catalog() -> ScienceCatalog:
    return ScienceCatalog(BOI_ROOT)


def _all_pack_rule_ids(catalog: ScienceCatalog) -> list[str]:
    ids = list(catalog.pack(FOUNDATION_PACK_ID).rule_refs)
    for name in PACKS:
        ids.extend(catalog.pack(PACK_IDS[name]).rule_refs)
    return ids


def _typed_rule(catalog: ScienceCatalog, rule_id: str) -> VerificationRule:
    stored = catalog.rule(rule_id)
    return VerificationRule.model_validate(
        {
            field_name: deepcopy(getattr(stored, field_name))
            for field_name in VerificationRule.model_fields
            if hasattr(stored, field_name)
        }
    )


def _candidate_qualification(
    catalog: ScienceCatalog,
) -> tuple[QualificationRuleSet, ResolvedReleaseSet]:
    components: list[ResolvedComponent] = []
    for rule_id in _all_pack_rule_ids(catalog):
        stored = catalog.rule(rule_id)
        rule = _typed_rule(catalog, rule_id)
        components.append(
            ResolvedComponent(
                ref=rule_id,
                kind="rule",
                declared_digest=stored.digest,
                actual_digest=stored.digest,
                semantic_digest=sha256_digest(rule),
            )
        )
    release = ResolvedRelease(
        release_id="sci-release:candidate-domain-packs-task3",
        schema_version="sci-profile/0.1",
        content_hash=sha256_digest({"task": "knowledge-task3-candidate"}),
        status="release_candidate",
        components=tuple(components),
        component_digests={item.ref: item.actual_digest for item in components},
        known_limitations=[
            "AI-authored domain drafts; authorized Admin reviews are absent."
        ],
    )
    release_set = ResolvedReleaseSet.from_single_foundation(release)
    return catalog.resolve_qualification_rule_set(release_set), release_set


def _single_rule_verdict(evaluation) -> PrimaryVerdict:
    if evaluation.applicability in {"MISSING_CONDITIONS", "NOT_APPLICABLE"}:
        return PrimaryVerdict.INSUFFICIENT_INFORMATION
    if evaluation.applicability == "OUTSIDE_DOMAIN":
        return PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
    if evaluation.applicability == "EMPIRICAL_ONLY":
        return PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED
    if evaluation.outcome == "CONTRADICTS":
        return PrimaryVerdict.VIOLATION
    if evaluation.outcome == "SUPPORTS":
        return PrimaryVerdict.CONSISTENT
    return PrimaryVerdict.INSUFFICIENT_INFORMATION


def _case_observations(case) -> tuple[QualifiedObservation, ...]:
    raw = getattr(case, "qualified_observation", None)
    if raw is None:
        return ()
    assert raw.get("fixture_only") is True
    return (
        QualifiedObservation.model_validate(
            {key: value for key, value in raw.items() if key != "fixture_only"}
        ),
    )


def _evaluate_case(case, rules_by_id, *, alternative: bool = False):
    packet = ClaimPacket.model_validate(
        getattr(case, "alternative_claim_packet" if alternative else "claim_packet")
    )
    rule = rules_by_id[case.evaluation_rule_id]
    evaluation = evaluate_rule(
        rule,
        packet.normalized_claim,
        qualified_observations=_case_observations(case),
    )
    return _single_rule_verdict(evaluation), evaluation


def test_domain_packs_have_exact_rules_cases_and_typed_dependencies(
    science_catalog: ScienceCatalog,
):
    domain_case_count = 0
    for name, (domain, count) in PACKS.items():
        pack = science_catalog.pack_by_name(name)
        assert pack.pack_id == PACK_IDS[name]
        assert len(pack.rule_refs) == count
        assert len(pack.knowledge_refs) == count
        assert len(pack.qualification_refs) == count
        assert "override" not in pack.model_dump_json()
        assert [
            (edge["relation"], edge["ref"]) for edge in pack.dependencies
        ] == EXPECTED_DEPENDENCIES[name]
        cases = science_catalog.qualification_cases_for_pack(pack.pack_id)
        assert len(cases) == count * 10
        domain_case_count += len(cases)

        for rule_id in pack.rule_refs:
            matrix_cases = science_catalog.qualification_cases(rule_id)
            assert len(matrix_cases) == 10
            assert {case.case_kind for case in matrix_cases} == REQUIRED_TEN_CASE_KINDS
            assert len(
                {
                    ClaimPacket.model_validate(case.claim_packet).source_span.exact
                    for case in matrix_cases
                }
            ) == 10
            assert all(
                science_catalog.qualification_matrix(matrix_id).release_refs == []
                for matrix_id in pack.qualification_refs
            )
            stored_rule = science_catalog.rule(rule_id)
            all_constraints = [
                *stored_rule.required_conditions,
                *stored_rule.validity_conditions,
                *stored_rule.empirical_trigger_conditions,
            ]
            boolean_constraints = {
                (item["key"], item.get("value"))
                for item in all_constraints
                if isinstance(item.get("value"), bool)
            }
            assert boolean_constraints <= {
                ("material_parameters_known", True),
                ("carrier_state_parameters_known", True),
            }
            for use in stored_rule.evidence_uses:
                evidence = science_catalog.evidence(use["evidence_ref"])
                assert evidence.decision_eligibility == "pending_review"
                allowed = evidence.claim_scope["allowed_claims"]
                assert {
                    "claim_family": use["claim_family"],
                    "purpose": use["purpose"],
                } in [
                    {
                        "claim_family": item["claim_family"],
                        "purpose": item["purpose"],
                    }
                    for item in allowed
                ]
        assert all(rule_id.startswith(f"sci-rule:{domain}:") for rule_id in pack.rule_refs)

    assert domain_case_count == 320
    assert sum(
        len(science_catalog.qualification_cases_for_pack(PACK_IDS[name]))
        for name in PACKS
        if name != "spin-coating"
    ) == 270
    assert domain_case_count + len(
        science_catalog.qualification_cases_for_pack(FOUNDATION_PACK_ID)
    ) == 440


def test_task3_objects_are_unapproved_agent_drafts_and_bindings_only_interpret(
    science_catalog: ScienceCatalog,
):
    objects = []
    binding_ids = set()
    for name in PACKS:
        pack = science_catalog.pack(PACK_IDS[name])
        objects.append(pack)
        objects.extend(science_catalog.knowledge(item) for item in pack.knowledge_refs)
        objects.extend(science_catalog.rule(item) for item in pack.rule_refs)
        objects.extend(
            science_catalog.qualification_matrix(item)
            for item in pack.qualification_refs
        )
        binding_ids.update(pack.ontology_binding_refs)
    assert binding_ids == DOMAIN_BINDING_IDS
    objects.extend(science_catalog.ontology_binding(item) for item in binding_ids)

    for item in objects:
        assert item.okf_status == "draft"
        assert item.okf_author == {"type": "agent", "agent_id": "codex"}
        assert item.okf_review == {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        }
        assert item.release_eligibility == "blocked_pending_authorized_admin_review"
    for binding_id in binding_ids:
        binding = science_catalog.ontology_binding(binding_id)
        assert binding.interpretation_only is True
        assert binding.must_not_collapse
        assert not hasattr(binding, "expected_predicate")
        assert not hasattr(binding, "outcome_direction")
        assert "association" not in binding.aliases
        assert "correlation" not in binding.aliases


def test_320_natural_claims_execute_through_candidate_rules_without_false_authority(
    science_catalog: ScienceCatalog,
):
    qualification, release_set = _candidate_qualification(science_catalog)
    assert type(qualification) is QualificationRuleSet
    assert not isinstance(qualification, OperationalVerification)
    rules = {released.rule.rule_id: released.rule for released in qualification.rules}
    assert len(rules) == 44

    evaluated = 0
    non_spin_verdicts = set()
    for name in PACKS:
        for case in science_catalog.qualification_cases_for_pack(PACK_IDS[name]):
            evaluated += 1
            packet = ClaimPacket.model_validate(case.claim_packet)
            exact = packet.source_span.exact
            assert packet.document_digest == "sha256:" + hashlib.sha256(
                exact.encode("utf-8")
            ).hexdigest()
            assert len(exact) >= 40
            assert exact[0].isupper()
            assert exact.rstrip().endswith(".")
            assert "Foundation topic" not in exact
            assert "qualification case" not in exact.lower()
            assert not re.search(r"(clear[-_ ]violation|in[-_ ]scope[-_ ]consistency)", exact, re.I)
            assert packet.source_span.end == len(exact)

            if case.case_kind == "decision_changing_ambiguity":
                alternative = ClaimPacket.model_validate(case.alternative_claim_packet)
                assert alternative.source_span.exact == exact
                assert packet.interpretation.ambiguity_ids
                assert packet.interpretation.user_confirmed is False
                first, _ = _evaluate_case(case, rules)
                second, _ = _evaluate_case(case, rules, alternative=True)
                assert first != second
                assert case.expected_gate == "ambiguity_gate"
                continue

            actual, evaluation = _evaluate_case(case, rules)
            assert case.evaluation_rule_id == case.matrix_rule_id
            assert evaluation.rule_id == case.matrix_rule_id
            assert actual.value == case.expected_verdict
            assert evaluation.evidence_refs == sorted(case.expected_evidence_path)
            if name != "spin-coating":
                non_spin_verdicts.add(actual.value)
            if case.case_kind == "unit_variation":
                rule = rules[case.matrix_rule_id]
                baseline_case = next(
                    item
                    for item in science_catalog.qualification_cases(case.matrix_rule_id)
                    if item.case_kind == "in_scope_consistency"
                )
                baseline_packet = ClaimPacket.model_validate(baseline_case.claim_packet)
                first, second = case.unit_equivalence
                assert first["quantity_kind"] == second["quantity_kind"]
                quantity_kind = first["quantity_kind"]
                assert quantity_kind in rule.context_dimensions
                assert compare_quantities(
                    first, second
                ) == 0
                assert any(
                    quantity == ClaimQuantity.model_validate(second)
                    for quantity in packet.normalized_claim.quantities
                )
                assert str(second["value"]) in exact
                assert second["unit"] in exact
                assert any(
                    quantity == ClaimQuantity.model_validate(first)
                    for quantity in baseline_packet.normalized_claim.quantities
                )
                assert validate_quantity(second).dimensionality == expected_dimensionality(
                    rule.context_dimensions[quantity_kind]
                )
                baseline_verdict, _ = _evaluate_case(baseline_case, rules)
                assert baseline_verdict == actual
                assert (
                    baseline_packet.normalized_claim.subject_concept_id,
                    baseline_packet.normalized_claim.relation_kind,
                    baseline_packet.normalized_claim.object_concept_id,
                    baseline_packet.normalized_claim.predicate,
                ) == (
                    packet.normalized_claim.subject_concept_id,
                    packet.normalized_claim.relation_kind,
                    packet.normalized_claim.object_concept_id,
                    packet.normalized_claim.predicate,
                )
            if case.case_kind == "empirical_verification_required":
                rule = rules[case.matrix_rule_id]
                assert rule.empirical_trigger_conditions
                assert evaluation.reason_codes == ["EMPIRICAL_TRIGGER_MATCHED"]
                assert evaluation.applicability == "EMPIRICAL_ONLY"
            if case.case_kind == "false_red_prevention":
                violation_case = next(
                    item
                    for item in science_catalog.qualification_cases(case.matrix_rule_id)
                    if item.case_kind == "clear_violation"
                )
                violation = ClaimPacket.model_validate(violation_case.claim_packet)
                assert actual is not PrimaryVerdict.VIOLATION
                assert (
                    packet.normalized_claim.subject_concept_id,
                    packet.normalized_claim.relation_kind,
                    packet.normalized_claim.object_concept_id,
                    packet.normalized_claim.predicate,
                ) == (
                    violation.normalized_claim.subject_concept_id,
                    violation.normalized_claim.relation_kind,
                    violation.normalized_claim.object_concept_id,
                    violation.normalized_claim.predicate,
                )
                assert (
                    packet.normalized_claim.conditions,
                    packet.normalized_claim.process_stage,
                    packet.normalized_claim.material_state,
                ) != (
                    violation.normalized_claim.conditions,
                    violation.normalized_claim.process_stage,
                    violation.normalized_claim.material_state,
                )
                last_required_key = rule.required_conditions[-1].key
                assert last_required_key.replace("_", " ") in exact.lower()
                assert "outside this rule's required scope" in exact.lower()

    assert evaluated == 320
    assert non_spin_verdicts == {item.value for item in PrimaryVerdict}

    first_case = science_catalog.qualification_cases("sci-rule:physics:001")[0]
    with pytest.raises(TypeError, match="operational verification"):
        verify_claim(
            ClaimPacket.model_validate(first_case.claim_packet),
            qualification,  # type: ignore[arg-type]
        )
    with pytest.raises(
        ScienceOperationalError,
        match="release candidate or withdrawn release cannot be evaluated as active",
    ):
        science_catalog.resolve_operational_rule_set(release_set)


def test_cross_domain_failure_examples_are_explicit_and_decisive(
    science_catalog: ScienceCatalog,
):
    expected_phrases = {
        "sci-rule:circuits:003": ("fixed voltage", "resistance", "power"),
        "sci-rule:circuits:004": ("fixed current", "resistance", "power"),
        "sci-rule:chemistry:005": ("catalyst", "equilibrium constant"),
        "sci-rule:materials:005": ("bulk", "thin-film"),
        "sci-rule:semiconductor-devices:003": ("doping", "mobility", "conductivity"),
        "sci-rule:semiconductor-devices:005": ("ideal MOS", "zero gate current"),
        "sci-rule:semiconductor-devices:006": ("real", "gate leakage"),
        "sci-rule:spin-coating:004": ("final coat spin", "spin speed", "film thickness"),
    }
    for rule_id, phrases in expected_phrases.items():
        case = next(
            item
            for item in science_catalog.qualification_cases(rule_id)
            if item.case_kind == "clear_violation"
        )
        text = ClaimPacket.model_validate(case.claim_packet).source_span.exact.lower()
        assert all(phrase.lower() in text for phrase in phrases)
        assert case.expected_verdict == "VIOLATION"

    spin_pack = science_catalog.pack(PACK_IDS["spin-coating"])
    serialized = "\n".join(
        [spin_pack.body, spin_pack.model_dump_json()]
        + [science_catalog.rule(item).model_dump_json() for item in spin_pack.rule_refs]
        + [science_catalog.knowledge(item).model_dump_json() for item in spin_pack.knowledge_refs]
        + [
            science_catalog.qualification_matrix(item).model_dump_json()
            for item in spin_pack.qualification_refs
        ]
    ).lower()
    for forbidden in (
        "rpm_setting",
        "recommended_rpm",
        "percentage_change",
        "doe_starting_point",
        "recipe_recommendation",
        "set rpm to",
    ):
        assert forbidden not in serialized

    emslie = science_catalog.knowledge("sci:spin-coating:002")
    meyerhofer = science_catalog.knowledge("sci:spin-coating:003")
    assert emslie.excluded_evidence_refs == ["sci-evidence:spin-coating:emslie-model"]
    assert meyerhofer.excluded_evidence_refs == [
        "sci-evidence:spin-coating:meyerhofer-model"
    ]
    assert "inactive" in emslie.exclusion_reason.lower()
    assert "inactive" in meyerhofer.exclusion_reason.lower()
    assert "sci-evidence:spin-coating:emslie-model" not in science_catalog.rule(
        "sci-rule:spin-coating:002"
    ).evidence_refs
    assert "sci-evidence:spin-coating:meyerhofer-model" not in science_catalog.rule(
        "sci-rule:spin-coating:003"
    ).evidence_refs
