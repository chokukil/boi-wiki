"""Pure verdict construction from a Claim Packet and release-pinned rules."""

from __future__ import annotations

from collections.abc import Iterable

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import (
    ClaimPacket,
    ConditionEvaluation,
    ExplanationFact,
    PrimaryVerdict,
    ResolvedReleaseSet,
    VerdictPacket,
    VerdictReleaseSet,
)
from boi_api.app.science.rules import (
    DetailedRuleEvaluation,
    QualifiedObservation,
    ResolvedRuleSet,
    VerificationRule,
    evaluate_rule,
)


class UnresolvedAmbiguityError(ValueError):
    """A decision-changing ambiguity must be resolved before verification."""


def _resolved_refs(release_set: ResolvedReleaseSet, kind: str) -> set[str]:
    return {
        component.ref
        for component in release_set.components
        if component.kind == kind
        and component.declared_digest == component.actual_digest
    }


def _is_concept_candidate(rule: VerificationRule, claim: ClaimPacket) -> bool:
    normalized = claim.normalized_claim
    return (
        rule.subject_concept_id == normalized.subject_concept_id
        and rule.object_concept_id == normalized.object_concept_id
        and (rule.relation_kind is None or rule.relation_kind is normalized.relation_kind)
    )


def _grounded(
    rule: VerificationRule,
    knowledge_refs: set[str],
    evidence_refs: set[str],
) -> bool:
    return (
        bool(rule.knowledge_refs)
        and bool(rule.evidence_refs)
        and set(rule.knowledge_refs) <= knowledge_refs
        and set(rule.evidence_refs) <= evidence_refs
    )


def _rule_set_integrity(
    release_set: ResolvedReleaseSet, rule_set: ResolvedRuleSet
) -> list[str]:
    if not release_set.compatibility.compatible:
        return ["INCOMPATIBLE_RELEASE_SET"]
    if release_set.combined_digest != ResolvedReleaseSet.combined_digest_for(
        release_set.selection,
        release_set.release_digests,
        release_set.components,
        release_set.compatibility,
    ):
        return ["RELEASE_SET_DIGEST_MISMATCH"]
    if rule_set.release_set_digest != release_set.combined_digest:
        return ["RULE_SET_RELEASE_SET_MISMATCH"]

    supplied_ids = [released.rule.rule_id for released in rule_set.rules]
    if len(supplied_ids) != len(set(supplied_ids)):
        return ["DUPLICATE_RULE_ID"]
    pinned = {component.ref: component for component in release_set.rule_components}
    supplied = set(supplied_ids)
    pinned_ids = set(pinned)
    if supplied != pinned_ids:
        if supplied < pinned_ids:
            return ["RULE_SET_INCOMPLETE"]
        if pinned_ids < supplied:
            return ["RULE_SET_HAS_EXTRA_RULES"]
        return ["RULE_SET_ID_MISMATCH"]

    reasons: set[str] = set()
    for released in rule_set.rules:
        rule_id = released.rule.rule_id
        component = pinned[rule_id]
        if (
            released.component_digest != component.actual_digest
            or component.declared_digest != component.actual_digest
        ):
            reasons.add("RULE_COMPONENT_DIGEST_MISMATCH")
        if (
            released.semantic_digest != component.semantic_digest
            or sha256_digest(released.rule) != released.semantic_digest
        ):
            reasons.add("RULE_SEMANTIC_DIGEST_MISMATCH")
    return sorted(reasons)


def _select_verdict(
    evaluations: list[DetailedRuleEvaluation],
    *,
    coverage_missing: bool,
) -> tuple[PrimaryVerdict, list[DetailedRuleEvaluation], list[str]]:
    missing = [item for item in evaluations if item.applicability == "MISSING_CONDITIONS"]
    if coverage_missing or missing or not evaluations:
        reasons = ["MISSING_RULE_COVERAGE"] if coverage_missing or not evaluations else []
        reasons.extend(code for item in missing for code in item.reason_codes)
        return PrimaryVerdict.INSUFFICIENT_INFORMATION, missing, sorted(set(reasons))

    outside = [item for item in evaluations if item.applicability == "OUTSIDE_DOMAIN"]
    if outside:
        return (
            PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN,
            outside,
            sorted({code for item in outside for code in item.reason_codes}),
        )

    empirical = [item for item in evaluations if item.applicability == "EMPIRICAL_ONLY"]
    if empirical:
        return (
            PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED,
            empirical,
            sorted({code for item in empirical for code in item.reason_codes}),
        )

    in_scope = [item for item in evaluations if item.applicability == "IN_SCOPE"]
    contradictions = [item for item in in_scope if item.outcome == "CONTRADICTS"]
    supports = [item for item in in_scope if item.outcome == "SUPPORTS"]
    if contradictions and supports:
        return (
            PrimaryVerdict.INSUFFICIENT_INFORMATION,
            in_scope,
            ["CONFLICTING_QUALIFIED_RULES"],
        )
    if contradictions:
        return (
            PrimaryVerdict.VIOLATION,
            contradictions,
            sorted({code for item in contradictions for code in item.reason_codes}),
        )
    if supports:
        return (
            PrimaryVerdict.CONSISTENT,
            supports,
            sorted({code for item in supports for code in item.reason_codes}),
        )
    return PrimaryVerdict.INSUFFICIENT_INFORMATION, [], ["NO_DECISIVE_IN_SCOPE_RULE"]


def _conditions(evaluations: list[DetailedRuleEvaluation]) -> list[ConditionEvaluation]:
    keyed: dict[tuple[object, ...], ConditionEvaluation] = {}
    for evaluation in evaluations:
        for condition in evaluation.condition_evaluations:
            key = (
                condition.condition_id,
                repr(condition.expected),
                repr(condition.actual),
                condition.satisfied,
            )
            keyed[key] = condition
    return [keyed[key] for key in sorted(keyed)]


def verify_claim(
    claim: ClaimPacket,
    release_set: ResolvedReleaseSet,
    verifier_version: str = "science-verifier/0.1.0",
    *,
    rule_set: ResolvedRuleSet,
    qualified_observations: Iterable[QualifiedObservation] = (),
) -> VerdictPacket:
    """Build a byte-stable verdict without filesystem, network, or dynamic code access."""

    if claim.interpretation.ambiguity_ids or not claim.interpretation.user_confirmed:
        ambiguity = ", ".join(sorted(claim.interpretation.ambiguity_ids)) or "unconfirmed interpretation"
        raise UnresolvedAmbiguityError(
            f"unresolved decision-changing ambiguity must stop before verification: {ambiguity}"
        )

    integrity_reasons = _rule_set_integrity(release_set, rule_set)
    supplied_rules = tuple(released.rule for released in rule_set.rules)
    pinned_rules = _resolved_refs(release_set, "rule")
    knowledge_refs = _resolved_refs(release_set, "knowledge")
    evidence_refs = _resolved_refs(release_set, "evidence")
    candidates = [rule for rule in supplied_rules if _is_concept_candidate(rule, claim)]
    trusted = [
        rule
        for rule in candidates
        if rule.rule_id in pinned_rules and _grounded(rule, knowledge_refs, evidence_refs)
    ]
    coverage_missing = bool(integrity_reasons) or len(trusted) != len(candidates) or not candidates
    observations = tuple(qualified_observations)

    def observations_for(rule: VerificationRule) -> tuple[QualifiedObservation, ...]:
        return tuple(
            observation
            for observation in observations
            if observation.rule_id == rule.rule_id
            and observation.verified
            and observation.measurement_ref in knowledge_refs
            and observation.evidence_ref in evidence_refs
            and observation.evidence_ref in rule.evidence_refs
        )

    evaluations = [
        evaluate_rule(
            rule,
            claim.normalized_claim,
            qualified_observations=observations_for(rule),
        )
        for rule in sorted(trusted, key=lambda item: item.rule_id)
    ] if not integrity_reasons else []
    evaluations = [item for item in evaluations if item.applicability != "NOT_APPLICABLE"]

    verdict, decisive, reason_codes = _select_verdict(
        evaluations,
        coverage_missing=coverage_missing,
    )
    reason_codes = sorted(set(reason_codes) | set(integrity_reasons))
    decisive = sorted(decisive, key=lambda item: item.rule_id)
    decisive_rule_ids = [item.rule_id for item in decisive]
    selected_knowledge = sorted(
        {ref for item in decisive for ref in item.knowledge_refs if ref in knowledge_refs}
    )
    selected_evidence = sorted(
        {ref for item in decisive for ref in item.evidence_refs if ref in evidence_refs}
    )
    explanation_facts = [
        ExplanationFact(
            fact_id=f"fact:{item.rule_id}:{item.outcome.lower()}",
            knowledge_refs=sorted(set(item.knowledge_refs) & knowledge_refs),
            evidence_refs=sorted(set(item.evidence_refs) & evidence_refs),
        )
        for item in decisive
        if set(item.knowledge_refs) & knowledge_refs and set(item.evidence_refs) & evidence_refs
    ]

    rule_by_id = {rule.rule_id: rule for rule in trusted}
    corrected_claim = None
    if verdict is PrimaryVerdict.VIOLATION:
        corrected_claim = next(
            (
                rule_by_id[rule_id].corrected_claim
                for rule_id in decisive_rule_ids
                if rule_by_id[rule_id].corrected_claim is not None
            ),
            None,
        )

    return VerdictPacket(
        claim_id=claim.claim_id,
        claim_packet_digest=sha256_digest(claim),
        verifier_version=verifier_version,
        releases=VerdictReleaseSet(
            selection=release_set.selection,
            digests=release_set.release_digests,
            combined_digest=release_set.combined_digest,
        ),
        verdict=verdict,
        reason_codes=reason_codes,
        condition_evaluations=_conditions(decisive),
        decisive_rule_ids=decisive_rule_ids,
        knowledge_refs=selected_knowledge,
        evidence_refs=selected_evidence,
        corrected_claim=corrected_claim,
        explanation_facts=explanation_facts,
        limitations=sorted(
            {
                limitation
                for release in (
                    release_set.foundation_release,
                    *release_set.domain_releases,
                    *release_set.application_releases,
                )
                for limitation in release.known_limitations
            }
        ),
    )
