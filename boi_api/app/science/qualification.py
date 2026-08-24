"""Deterministic preflight for an inactive Science Release candidate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Literal

from pydantic import Field

from boi_api.app.okf import split_frontmatter
from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import (
    ClaimPacket,
    PrimaryVerdict,
    ReleaseSelection,
    ScienceModel,
)
from boi_api.app.science.rules import (
    QualifiedObservation,
    VerificationRule,
    evaluate_rule,
)

GateStatus = Literal["PASS", "FAIL", "PENDING"]


class QualificationGate(ScienceModel):
    gate_id: str
    status: GateStatus
    summary: str


class QualificationCaseResult(ScienceModel):
    case_id: str
    case_kind: str
    rule_id: str
    claim_text: str
    expected_outcome: str
    actual_outcome: str
    evidence_refs: list[str]
    deterministic: bool


class QualificationResult(ScienceModel):
    release_id: str
    release_digest: str
    release_status: str
    result_digest: str
    gates: dict[str, QualificationGate]
    aggregate_score: None = None
    activation_eligible: bool
    public_case_count: int
    component_digests: dict[str, str]
    pack_dependencies: dict[str, list[dict[str, str]]]
    holdout_manifest_digest: str | None
    case_results: list[QualificationCaseResult]
    missed_violations: list[str] = Field(default_factory=list)
    false_red_cases: list[str] = Field(default_factory=list)
    wrong_interpretations: list[str] = Field(default_factory=list)
    validity_range_errors: list[str] = Field(default_factory=list)
    unsupported_scope_errors: list[str] = Field(default_factory=list)
    broken_evidence_locators: list[str] = Field(default_factory=list)
    ungrounded_explanation_facts: list[str] = Field(default_factory=list)
    nondeterministic_cases: list[str] = Field(default_factory=list)


def _single_rule_verdict(evaluation: object) -> PrimaryVerdict:
    applicability = getattr(evaluation, "applicability")
    outcome = getattr(evaluation, "outcome")
    if applicability in {"MISSING_CONDITIONS", "NOT_APPLICABLE"}:
        return PrimaryVerdict.INSUFFICIENT_INFORMATION
    if applicability == "OUTSIDE_DOMAIN":
        return PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
    if applicability == "EMPIRICAL_ONLY":
        return PrimaryVerdict.EMPIRICAL_VERIFICATION_REQUIRED
    if outcome == "CONTRADICTS":
        return PrimaryVerdict.VIOLATION
    if outcome == "SUPPORTS":
        return PrimaryVerdict.CONSISTENT
    return PrimaryVerdict.INSUFFICIENT_INFORMATION


def _case_observations(case: object) -> tuple[QualifiedObservation, ...]:
    raw = getattr(case, "qualified_observation", None)
    if raw is None:
        return ()
    if not isinstance(raw, Mapping) or raw.get("fixture_only") is not True:
        return ()
    return (
        QualifiedObservation.model_validate(
            {key: value for key, value in raw.items() if key != "fixture_only"}
        ),
    )


def _typed_rule(catalog: ScienceCatalog, rule_id: str) -> VerificationRule:
    stored = catalog.rule(rule_id)
    return VerificationRule.model_validate(
        {
            field_name: deepcopy(getattr(stored, field_name))
            for field_name in VerificationRule.model_fields
            if hasattr(stored, field_name)
        }
    )


def _evaluate(
    rule: VerificationRule,
    packet: ClaimPacket,
    observations: tuple[QualifiedObservation, ...],
) -> tuple[PrimaryVerdict, object, str]:
    evaluation = evaluate_rule(
        rule,
        packet.normalized_claim,
        qualified_observations=observations,
    )
    verdict = _single_rule_verdict(evaluation)
    digest = sha256_digest(
        {"verdict": verdict.value, "evaluation": evaluation.model_dump(mode="json")}
    )
    return verdict, evaluation, digest


def _structurally_broken_evidence(catalog: ScienceCatalog) -> list[str]:
    broken: list[str] = []
    for evidence_id, evidence in sorted(catalog._objects["evidence"].items()):
        locator = getattr(evidence, "locator", None)
        source_id = getattr(evidence, "source_id", None)
        source = catalog._objects["source"].get(source_id)
        original_url = getattr(source, "original_url", None) if source else None
        original_text = getattr(evidence, "original_text", None)
        original_text_hash = getattr(evidence, "original_text_hash", None)
        exact_hash = (
            "sha256:" + hashlib.sha256(original_text.encode("utf-8")).hexdigest()
            if isinstance(original_text, str)
            else None
        )
        if (
            not isinstance(locator, Mapping)
            or not locator
            or not isinstance(original_url, str)
            or not original_url.startswith("https://")
            or original_text_hash != exact_hash
        ):
            broken.append(evidence_id)
    return broken


def _holdout_manifest(boi_root: Path) -> tuple[str | None, Mapping[str, object] | None]:
    path = (
        Path(boi_root)
        / "public"
        / "science"
        / "qualification"
        / "holdouts"
        / "manifest.md"
    )
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    metadata, _body = split_frontmatter(raw.decode("utf-8"))
    holdout = metadata.get("science_holdout")
    return "sha256:" + hashlib.sha256(raw).hexdigest(), (
        holdout if isinstance(holdout, Mapping) else None
    )


def _gate(gate_id: str, status: GateStatus, summary: str) -> QualificationGate:
    return QualificationGate(gate_id=gate_id, status=status, summary=summary)


def qualify_release_candidate(
    boi_root: Path,
    release_id: str,
    *,
    holdout_path: Path | None = None,
) -> QualificationResult:
    """Run public candidate gates without issuing operational authority."""

    catalog = ScienceCatalog(Path(boi_root))
    release_set = catalog.resolve_release_set(ReleaseSelection(foundation=release_id))
    release = release_set.foundation_release
    qualification = catalog.resolve_qualification_rule_set(release_set)
    rules = {released.rule.rule_id: released.rule for released in qualification.rules}
    pinned_knowledge = {
        component.ref
        for component in release.components
        if component.kind == "knowledge"
    }
    pinned_evidence = {
        component.ref
        for component in release.components
        if component.kind == "evidence"
    }

    case_results: list[QualificationCaseResult] = []
    missed_violations: list[str] = []
    false_red_cases: list[str] = []
    wrong_interpretations: list[str] = []
    validity_range_errors: list[str] = []
    unsupported_scope_errors: list[str] = []
    ungrounded: list[str] = []
    nondeterministic: list[str] = []

    for case_id, case in sorted(catalog._cases.items()):
        rule_id = str(getattr(case, "evaluation_rule_id"))
        rule = rules[rule_id]
        packet = ClaimPacket.model_validate(getattr(case, "claim_packet"))
        observations = _case_observations(case)
        first, evaluation, first_digest = _evaluate(rule, packet, observations)
        second, _second_evaluation, second_digest = _evaluate(
            rule, packet, observations
        )
        deterministic = first == second and first_digest == second_digest
        actual_outcome = first.value
        expected_outcome = str(getattr(case, "expected_verdict", ""))

        if case.case_kind == "decision_changing_ambiguity":
            alternative = ClaimPacket.model_validate(
                getattr(case, "alternative_claim_packet")
            )
            alternative_verdict, alternative_evaluation, alternative_digest = _evaluate(
                rule, alternative, observations
            )
            (
                alternative_again,
                _alternative_again_evaluation,
                alternative_again_digest,
            ) = _evaluate(rule, alternative, observations)
            deterministic = deterministic and (
                alternative_verdict == alternative_again
                and alternative_digest == alternative_again_digest
            )
            expected_outcome = "AMBIGUITY_GATE"
            actual_outcome = (
                "AMBIGUITY_GATE"
                if first != alternative_verdict
                else "AMBIGUITY_NOT_DECISION_CHANGING"
            )
            if actual_outcome != expected_outcome:
                wrong_interpretations.append(case_id)
            if (
                not alternative_evaluation.knowledge_refs
                or not alternative_evaluation.evidence_refs
                or not set(alternative_evaluation.knowledge_refs) <= pinned_knowledge
                or not set(alternative_evaluation.evidence_refs) <= pinned_evidence
            ):
                ungrounded.append(case_id)
        else:
            if (
                expected_outcome == PrimaryVerdict.VIOLATION.value
                and first is not PrimaryVerdict.VIOLATION
            ):
                missed_violations.append(case_id)
            if (
                expected_outcome != PrimaryVerdict.VIOLATION.value
                and first is PrimaryVerdict.VIOLATION
            ):
                false_red_cases.append(case_id)
            if expected_outcome != first.value:
                if case.case_kind == "outside_validity_domain":
                    validity_range_errors.append(case_id)
                elif case.case_kind in {
                    "missing_required_condition",
                    "false_red_prevention",
                }:
                    unsupported_scope_errors.append(case_id)
                elif case.case_kind in {"negation", "paraphrase"}:
                    wrong_interpretations.append(case_id)
                else:
                    unsupported_scope_errors.append(case_id)

        if (
            not evaluation.knowledge_refs
            or not evaluation.evidence_refs
            or not set(evaluation.knowledge_refs) <= pinned_knowledge
            or not set(evaluation.evidence_refs) <= pinned_evidence
            or sorted(evaluation.evidence_refs)
            != sorted(getattr(case, "expected_evidence_path", []))
        ):
            ungrounded.append(case_id)
        if not deterministic:
            nondeterministic.append(case_id)

        case_results.append(
            QualificationCaseResult(
                case_id=case_id,
                case_kind=str(case.case_kind),
                rule_id=rule_id,
                claim_text=packet.source_span.exact,
                expected_outcome=expected_outcome,
                actual_outcome=actual_outcome,
                evidence_refs=sorted(evaluation.evidence_refs),
                deterministic=deterministic,
            )
        )

    broken_evidence = _structurally_broken_evidence(catalog)
    holdout_manifest_digest, holdout_manifest = _holdout_manifest(Path(boi_root))
    public_errors = {
        *missed_violations,
        *false_red_cases,
        *wrong_interpretations,
        *validity_range_errors,
        *unsupported_scope_errors,
    }
    gates = {
        "G0": _gate(
            "G0",
            "PASS" if release.status == "release_candidate" else "FAIL",
            "Schema, IDs, references, immutable component digests, and candidate lifecycle are valid.",
        ),
        "G1": _gate(
            "G1",
            "PASS" if not broken_evidence else "FAIL",
            "Source/Evidence hashes and locator structures are internally reproducible.",
        ),
        "G2": _gate(
            "G2",
            "PASS" if not ungrounded else "FAIL",
            "Every public decision remains inside release-pinned Knowledge and Evidence.",
        ),
        "G3": _gate(
            "G3",
            "PASS" if len(case_results) == 440 and not public_errors else "FAIL",
            "All 440 public cases match their expected verdict or ambiguity gate.",
        ),
        "G4": _gate(
            "G4",
            "PASS" if not nondeterministic else "FAIL",
            "Repeated public qualification is byte-stable.",
        ),
        "G5": _gate(
            "G5",
            "PENDING",
            (
                "Independent sealed holdout is not commissioned."
                if not holdout_manifest
                or holdout_manifest.get("state") != "sealed_independent_holdout"
                or holdout_path is None
                else "Sealed holdout support is reserved for the post-freeze final checker."
            ),
        ),
        "G6": _gate(
            "G6",
            "PENDING",
            (
                "Web/REST/MCP/explanation/export parity must be established by the "
                "authoritative post-integration checker; caller assertions cannot pass "
                "this gate."
            ),
        ),
        "G7": _gate(
            "G7",
            "PENDING",
            (
                "Authorized human Admin review and activation must be resolved from "
                "the operational audit store; caller assertions cannot pass this gate."
            ),
        ),
    }

    pack_dependencies = {
        pack_id: [
            dependency.model_dump(mode="json")
            for dependency in catalog._pack_dependencies(pack)
        ]
        for pack_id, pack in sorted(catalog._objects["pack"].items())
    }
    payload = {
        "release_id": release.release_id,
        "release_digest": release.content_hash,
        "release_status": release.status,
        "gates": gates,
        "aggregate_score": None,
        "activation_eligible": all(gate.status == "PASS" for gate in gates.values()),
        "public_case_count": len(case_results),
        "component_digests": dict(sorted(release.component_digests.items())),
        "pack_dependencies": pack_dependencies,
        "holdout_manifest_digest": holdout_manifest_digest,
        "case_results": case_results,
        "missed_violations": sorted(set(missed_violations)),
        "false_red_cases": sorted(set(false_red_cases)),
        "wrong_interpretations": sorted(set(wrong_interpretations)),
        "validity_range_errors": sorted(set(validity_range_errors)),
        "unsupported_scope_errors": sorted(set(unsupported_scope_errors)),
        "broken_evidence_locators": sorted(set(broken_evidence)),
        "ungrounded_explanation_facts": sorted(set(ungrounded)),
        "nondeterministic_cases": sorted(set(nondeterministic)),
    }
    result_digest = sha256_digest(payload)
    return QualificationResult(result_digest=result_digest, **payload)


def render_preflight_markdown(result: QualificationResult) -> str:
    """Render a deterministic candidate report without implying activation."""

    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/report",
        "title": "Science Release 0.1.0 public preflight",
        "description": "Automated candidate-only G0..G4 preflight; no human approval or activation",
        "tags": ["ScienceVerifier", "Qualification", "ReleaseCandidate"],
        "timestamp": "2026-08-25T16:00:00+09:00",
        "boi_id": "boi:public:science:qualification-report:release-0.1.0-preflight",
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "author": {"type": "agent", "agent_id": "science-qualification-runner"},
        "acl_policy": "acl:public",
        "status": "draft",
        "source_refs": [{"type": "boi", "ref": "boi:public:science:release:0.1.0"}],
        "review": {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        },
        "science_qualification": {
            "release_id": result.release_id,
            "release_digest": result.release_digest,
            "result_digest": result.result_digest,
            "lifecycle": result.release_status,
            "public_case_count": result.public_case_count,
            "activation_eligible": result.activation_eligible,
        },
    }
    lines = [
        "---",
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=False),
        "---",
        "# Science Release 0.1.0 public preflight",
        "",
        "> Candidate qualification only. This report is not a human review, approval, or active Science Release.",
        "",
        f"- Release ID: `{result.release_id}`",
        f"- Release digest: `{result.release_digest}`",
        f"- Result digest: `{result.result_digest}`",
        f"- Lifecycle: `{result.release_status}`",
        f"- Public cases: {result.public_case_count}",
        f"- activation_eligible: {str(result.activation_eligible).lower()}",
        "",
        "## Release gates",
        "",
    ]
    lines.extend(
        f"- {gate_id} | {gate.status} | {gate.summary}"
        for gate_id, gate in result.gates.items()
    )
    lines.extend(
        [
            "",
            "## Failure inventory",
            "",
            f"- Missed violations: {len(result.missed_violations)}",
            f"- False-red: {len(result.false_red_cases)}",
            f"- Wrong interpretations: {len(result.wrong_interpretations)}",
            f"- Validity/range errors: {len(result.validity_range_errors)}",
            f"- Unsupported-scope errors: {len(result.unsupported_scope_errors)}",
            f"- Broken Evidence locators: {len(result.broken_evidence_locators)}",
            f"- Ungrounded explanation facts: {len(result.ungrounded_explanation_facts)}",
            f"- Nondeterministic cases: {len(result.nondeterministic_cases)}",
            "",
            "## Case results",
            "",
            "| Case | Kind | Rule | Expected | Actual | Deterministic |",
            "|---|---|---|---|---|---|",
        ]
    )
    lines.extend(
        "| {case_id} | {kind} | {rule} | {expected} | {actual} | {stable} |".format(
            case_id=item.case_id,
            kind=item.case_kind,
            rule=item.rule_id,
            expected=item.expected_outcome,
            actual=item.actual_outcome,
            stable="yes" if item.deterministic else "no",
        )
        for item in result.case_results
    )
    lines.extend(
        [
            "",
            "## Component digest inventory",
            "",
            "The exact component map remains in the Release manifest; this report lists one digest per pinned object.",
            "",
        ]
    )
    lines.extend(
        f"- `{ref}` — `{digest}`" for ref, digest in result.component_digests.items()
    )
    return "\n".join(lines) + "\n"
