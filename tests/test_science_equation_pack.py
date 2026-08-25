from __future__ import annotations

import subprocess
from pathlib import Path

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.rules import (
    validate_equation_knowledge_for_operational_binding,
    validate_operational_equation_binding,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BOI_ROOT = REPO_ROOT / "data/boi"

EQUATIONS = {
    "sci:equation:physics:applied-work-kinetic-energy-change": (
        "sci:physics:003",
        "deterministic_rule",
    ),
    "sci:equation:chemistry:molar-concentration-definition": (
        "sci:chemistry:001",
        "deterministic_rule",
    ),
    "sci:equation:circuits:kvl-loop-balance": (
        "sci:circuits:002",
        "deterministic_rule",
    ),
    "sci:equation:semiconductor:low-field-conductivity": (
        "sci:semiconductor-devices:003",
        "explanation_only",
    ),
    "sci:equation:materials:arrhenius-diffusion": (
        "sci:materials:004",
        "explanation_only",
    ),
    "sci:equation:spin-coating:drying-limited-power-law": (
        "sci:spin-coating:004",
        "explanation_only",
    ),
}


def test_six_domain_equation_pack_is_reproducible_and_inactive() -> None:
    completed = subprocess.run(
        [
            "python3.11",
            str(REPO_ROOT / "scripts/build_science_equation_pack.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--check",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"release_activation": "not_performed"' in completed.stdout

    catalog = ScienceCatalog(BOI_ROOT)
    for equation_id, (knowledge_id, decision_use) in EQUATIONS.items():
        resolved = catalog.equation(equation_id)
        knowledge = catalog.knowledge(knowledge_id)
        assert resolved.knowledge_id == knowledge_id
        assert resolved.knowledge_digest == knowledge.digest
        assert resolved.equation.decision_use == decision_use
        assert knowledge.okf_status == "draft"
        assert knowledge.okf_review["review_status"] == "pending_review"
        assert knowledge.release_eligibility == (
            "blocked_pending_authorized_admin_review"
        )


def test_equation_transcriptions_and_variables_remain_exactly_evidence_bound() -> None:
    catalog = ScienceCatalog(BOI_ROOT)

    for equation_id in EQUATIONS:
        equation = catalog.equation(equation_id).equation
        assert equation.equation_digest == equation.computed_digest()
        for use in equation.evidence_uses:
            evidence = catalog.evidence(use.evidence_ref)
            source_notation = getattr(evidence, "locator").get(
                "equation", evidence.original_text
            )
            assert use.transcription.original_notation == source_notation
            assert use.claim_scope_hash == evidence.claim_scope_hash
            assert all(
                mapping.source_symbol in source_notation
                for mapping in equation.original_notation_mapping
            )


def test_only_three_closed_arithmetic_equations_bind_candidate_rules() -> None:
    catalog = ScienceCatalog(BOI_ROOT)
    bound = {
        "sci-rule:physics:003": (
            "sci:equation:physics:applied-work-kinetic-energy-change"
        ),
        "sci-rule:chemistry:001": (
            "sci:equation:chemistry:molar-concentration-definition"
        ),
        "sci-rule:circuits:002": "sci:equation:circuits:kvl-loop-balance",
    }

    for rule_id, equation_id in bound.items():
        rule = catalog._verification_rule(catalog.rule(rule_id))
        identity = validate_operational_equation_binding(rule)
        assert identity is not None
        assert identity.equation_id == equation_id
        validate_equation_knowledge_for_operational_binding(
            identity, catalog.equation(equation_id).equation
        )

    for equation_id in EQUATIONS:
        equation = catalog.equation(equation_id).equation
        if equation.decision_use == "explanation_only":
            assert equation.evaluator is None
