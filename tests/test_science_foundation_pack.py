from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.engine import verify_claim
from boi_api.app.science.exceptions import ScienceOperationalError
from boi_api.app.science.models import (
    ClaimPacket,
    PrimaryVerdict,
    ReleaseSelection,
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
from boi_api.app.science.units import compare_quantities


BOI_ROOT = Path(__file__).resolve().parents[1] / "data" / "boi"
PACK_ID = "sci-pack:science-foundation/0.1.0"
RULE_IDS = [f"sci-rule:common:{number:03d}" for number in range(1, 13)]
KNOWLEDGE_IDS = [f"sci:common:{number:03d}" for number in range(1, 13)]
MATRIX_IDS = [f"sci-matrix:common:{number:03d}" for number in range(1, 13)]
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


@pytest.fixture(scope="module")
def science_catalog() -> ScienceCatalog:
    return ScienceCatalog(BOI_ROOT)


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
    for rule_id in RULE_IDS:
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
        release_id="sci-release:candidate-science-foundation-task2",
        schema_version="sci-profile/0.1",
        content_hash=sha256_digest({"task": "knowledge-task2-candidate"}),
        status="release_candidate",
        components=tuple(components),
        component_digests={item.ref: item.actual_digest for item in components},
        known_limitations=[
            "AI-authored draft for qualification only; authorized Admin review is absent."
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


def _evaluate_case(
    case,
    rules_by_id: dict[str, VerificationRule],
    *,
    alternative: bool = False,
) -> tuple[PrimaryVerdict, object]:
    packet_field = "alternative_claim_packet" if alternative else "claim_packet"
    packet = ClaimPacket.model_validate(getattr(case, packet_field))
    target_rule = rules_by_id[getattr(case, "evaluation_rule_id")]
    evaluation = evaluate_rule(
        target_rule,
        packet.normalized_claim,
        qualified_observations=_case_observations(case),
    )
    return _single_rule_verdict(evaluation), evaluation


def test_foundation_has_twelve_topics_bindings_rules_and_matrices(
    science_catalog: ScienceCatalog,
):
    pack = science_catalog.pack(PACK_ID)
    assert pack.rule_refs == RULE_IDS
    assert pack.knowledge_refs == KNOWLEDGE_IDS
    assert pack.qualification_refs == MATRIX_IDS
    assert len(pack.ontology_binding_refs) == 12
    assert pack.release_eligibility == "blocked_pending_authorized_admin_review"

    for number, rule_id in enumerate(RULE_IDS, start=1):
        matrix = science_catalog.qualification_matrix(
            f"sci-matrix:common:{number:03d}"
        )
        cases = science_catalog.qualification_cases(rule_id)
        assert matrix.standard_id == f"Q-COM-{number:03d}"
        assert matrix.release_refs == []
        assert len(cases) == 10
        assert {case.case_kind for case in cases} == REQUIRED_TEN_CASE_KINDS
        assert len({sha256_digest(case.model_dump(mode="json")) for case in cases}) == 10


def test_foundation_objects_are_agent_drafts_and_cannot_claim_release_eligibility(
    science_catalog: ScienceCatalog,
):
    pack = science_catalog.pack(PACK_ID)
    objects = [pack]
    objects.extend(science_catalog.knowledge(item) for item in KNOWLEDGE_IDS)
    objects.extend(science_catalog.rule(item) for item in RULE_IDS)
    objects.extend(science_catalog.qualification_matrix(item) for item in MATRIX_IDS)
    objects.extend(
        science_catalog.ontology_binding(item) for item in pack.ontology_binding_refs
    )

    for item in objects:
        assert item.okf_status == "draft"
        assert item.okf_author == {"type": "agent", "agent_id": "codex"}
        assert item.okf_review == {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        }
        assert item.release_eligibility == "blocked_pending_authorized_admin_review"


def test_atomic_knowledge_and_interpretation_only_ontology_are_explicit(
    science_catalog: ScienceCatalog,
):
    pack = science_catalog.pack(PACK_ID)
    for number, knowledge_id in enumerate(KNOWLEDGE_IDS, start=1):
        knowledge = science_catalog.knowledge(knowledge_id)
        assert knowledge.foundation_topic_id == f"SCI-COM-{number:03d}"
        assert knowledge.statement.strip()
        assert knowledge.definitions
        assert isinstance(knowledge.assumptions, list)
        assert knowledge.applicability
        assert knowledge.limitations
        assert knowledge.invalid_outside
        assert isinstance(knowledge.related_knowledge, list)
        assert knowledge.evidence_roles

    outcome_words = {"increase", "decrease", "increases", "decreases"}
    for binding_id in pack.ontology_binding_refs:
        binding = science_catalog.ontology_binding(binding_id)
        assert binding.interpretation_only is True
        assert binding.meaning.strip()
        assert binding.aliases
        assert binding.must_not_collapse
        serialized = binding.model_dump(mode="json")
        assert not (outcome_words & set(serialized))
        assert not hasattr(binding, "expected_predicate")
        assert not hasattr(binding, "outcome_direction")


def test_each_matrix_case_changes_the_intended_qualification_boundary(
    science_catalog: ScienceCatalog,
):
    for rule_id in RULE_IDS:
        cases = {
            case.case_kind: case
            for case in science_catalog.qualification_cases(rule_id)
        }
        consistent = ClaimPacket.model_validate(
            cases["in_scope_consistency"].claim_packet
        )
        missing = ClaimPacket.model_validate(
            cases["missing_required_condition"].claim_packet
        )
        outside = ClaimPacket.model_validate(
            cases["outside_validity_domain"].claim_packet
        )
        negation = ClaimPacket.model_validate(cases["negation"].claim_packet)
        ambiguity = ClaimPacket.model_validate(
            cases["decision_changing_ambiguity"].claim_packet
        )
        alternative = ClaimPacket.model_validate(
            cases["decision_changing_ambiguity"].alternative_claim_packet
        )
        paraphrase = ClaimPacket.model_validate(cases["paraphrase"].claim_packet)
        false_red = ClaimPacket.model_validate(
            cases["false_red_prevention"].claim_packet
        )

        consistent_conditions = {
            item.condition_id for item in consistent.normalized_claim.conditions
        }
        missing_conditions = {
            item.condition_id for item in missing.normalized_claim.conditions
        }
        assert missing_conditions < consistent_conditions
        assert {
            item.condition_id for item in outside.normalized_claim.conditions
        } == consistent_conditions
        assert outside.normalized_claim.conditions != consistent.normalized_claim.conditions
        assert negation.normalized_claim.polarity == "negative"
        assert ambiguity.interpretation.ambiguity_ids
        assert ambiguity.normalized_claim != alternative.normalized_claim
        assert paraphrase.normalized_claim == consistent.normalized_claim
        assert paraphrase.source_span.exact != consistent.source_span.exact
        assert (
            false_red.normalized_claim.subject_concept_id
            != consistent.normalized_claim.subject_concept_id
        )


def test_all_120_cases_run_through_candidate_qualification_without_active_authority(
    science_catalog: ScienceCatalog,
):
    qualification, release_set = _candidate_qualification(science_catalog)
    assert type(qualification) is QualificationRuleSet
    assert not isinstance(qualification, OperationalVerification)
    rules_by_id = {released.rule.rule_id: released.rule for released in qualification.rules}
    assert sorted(rules_by_id) == RULE_IDS

    evaluated = 0
    for matrix_id in MATRIX_IDS:
        matrix = science_catalog.qualification_matrix(matrix_id)
        for case in science_catalog.qualification_cases(matrix.rule_id):
            evaluated += 1
            if case.case_kind == "decision_changing_ambiguity":
                packet = ClaimPacket.model_validate(case.claim_packet)
                assert packet.interpretation.ambiguity_ids
                assert packet.interpretation.user_confirmed is False
                first, _ = _evaluate_case(case, rules_by_id)
                second, _ = _evaluate_case(case, rules_by_id, alternative=True)
                assert first != second
                assert case.expected_gate == "ambiguity_gate"
                continue

            actual, evaluation = _evaluate_case(case, rules_by_id)
            assert actual.value == case.expected_verdict
            assert evaluation.evidence_refs == sorted(case.expected_evidence_path)
            if case.case_kind == "empirical_verification_required":
                assert case.evaluation_rule_id == "sci-rule:common:008"
                assert actual is PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED
            if case.case_kind == "unit_variation":
                assert compare_quantities(
                    case.unit_equivalence[0], case.unit_equivalence[1]
                ) == 0
            if case.case_kind == "false_red_prevention":
                assert actual is not PrimaryVerdict.VIOLATION

    assert evaluated == 120

    first_claim = ClaimPacket.model_validate(
        science_catalog.qualification_cases(RULE_IDS[0])[0].claim_packet
    )
    with pytest.raises(TypeError, match="operational verification"):
        verify_claim(first_claim, qualification)  # type: ignore[arg-type]
    with pytest.raises(
        ScienceOperationalError,
        match="release candidate or withdrawn release cannot be evaluated as active",
    ):
        science_catalog.resolve_operational_rule_set(release_set)
