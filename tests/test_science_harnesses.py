from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_HARNESS_ROOT = REPO_ROOT / "harness"
PUBLIC_HARNESS_ROOT = REPO_ROOT / "data" / "boi" / "public" / "harness"
HARNESS_NAMES = (
    "science-source-curation-harness.md",
    "science-knowledge-authoring-harness.md",
    "science-equation-knowledge-harness.md",
    "science-rule-qualification-harness.md",
    "science-verification-harness.md",
)
COMMON_SECTIONS = (
    "Purpose",
    "Inputs",
    "Observation",
    "Context",
    "Control",
    "Action",
    "State",
    "Verification",
    "Failure Artifacts",
    "Release-Blocking Conditions",
)
PRIMARY_VERDICTS = (
    "VIOLATION",
    "CONSISTENT",
    "INSUFFICIENT_INFORMATION",
    "OUTSIDE_VALIDITY_DOMAIN",
    "EMPIRICAL_VERIFICATION_REQUIRED",
)


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, f"{path} must have YAML frontmatter"
    return yaml.safe_load(match.group(1)) or {}, match.group(2).strip()


@pytest.mark.parametrize("name", HARNESS_NAMES)
def test_repo_and_public_science_harnesses_have_identical_normative_bodies(name: str):
    repo_metadata, repo_body = _frontmatter_and_body(REPO_HARNESS_ROOT / name)
    public_metadata, public_body = _frontmatter_and_body(PUBLIC_HARNESS_ROOT / name)

    assert repo_body == public_body
    assert repo_metadata["type"] == "boi/harness"
    assert public_metadata["type"] == "boi/harness"
    assert public_metadata["boi_id"] == f"boi:public:harness:{name.removesuffix('.md')}"
    assert public_metadata["status"] == "draft"
    assert public_metadata["author"] == {"type": "agent", "agent_id": "codex"}
    assert public_metadata["review"] == {
        "review_status": "pending_review",
        "required_role": "Admin",
        "authorized_review_events": [],
    }
    assert public_metadata["sci_profile_version"] == "0.1"
    assert {item["ref"] for item in public_metadata["source_refs"]} >= {
        f"harness/{name}",
        "data/okf/profiles/sci-profile.yaml",
    }


@pytest.mark.parametrize("name", HARNESS_NAMES)
def test_each_science_harness_has_the_operational_contract_and_release_gates(name: str):
    _metadata, body = _frontmatter_and_body(REPO_HARNESS_ROOT / name)

    for section in COMMON_SECTIONS:
        assert f"## {section}" in body
    for gate in range(8):
        assert f"G{gate}" in body
    assert "science.admin" in body
    assert "self-approval" in body
    assert "user_confirmed" in body
    assert "release-blocking" in body.lower()
    assert "AI" in body and "판정" in body


def test_source_harness_keeps_locator_hash_translation_and_review_load_bearing():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-source-curation-harness.md"
    )

    for required in (
        "original_url",
        "requested_url",
        "resolved_url",
        "retrieved_resource_hash",
        "original_text_hash",
        "claim_scope_hash",
        "exact locator",
        "reviewed_translation",
        "license",
        "ACL",
        "decision_eligibility",
        "authorized_review_events",
    ):
        assert required in body
    assert "초록만" in body
    assert "원문 Evidence로 승격하지 않는다" in body
    assert "출처 후보를 찾는 것" in body
    assert "판정 근거" in body


def test_knowledge_harness_preserves_atomic_scientific_scope_between_dictionary_and_evidence():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-knowledge-authoring-harness.md"
    )

    for required in (
        "atomic statement",
        "definitions",
        "assumptions",
        "applicability",
        "limitations",
        "invalid_outside",
        "EvidenceUse",
        "claim_family",
        "purpose",
        "excluded_evidence_refs",
        "Dictionary",
        "Ontology",
        "Evidence",
    ):
        assert required in body
    assert "결과 방향" in body
    assert "온톨로지" in body
    assert "수치 confidence" in body


def test_equation_harness_closes_semantics_source_review_qualification_and_rendering():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-equation-knowledge-harness.md"
    )

    # Baseline pressure failure this catches: the pre-equation harness set said only
    # "equation/unit constraints", so a rushed curator could promote OCR LaTeX or an
    # Agent/CAS result without a reviewed semantic authority or safe channel parity.
    for required in (
        "equation_id",
        "scientific_role",
        "decision_use",
        "semantic_expression",
        "display_latex",
        "plain_text",
        "accessibility_reading",
        "variable_id",
        "quantity_kind",
        "dimension",
        "sign_constraints",
        "boundary_conditions",
        "invalid_outside",
        "approximation",
        "original_notation",
        "notation_mapping",
        "EvidenceUse",
        "equation locator",
        "equation_digest",
        "operator allowlist",
        "deterministic_rule",
        "explanation_only",
        "OCR",
        "numerator",
        "denominator",
        "singular",
        "tolerance",
        "malicious",
        "Web",
        "Markdown",
        "PDF",
        "MathML",
        "rendering fallback",
        "report_digest",
        "export_digest",
    ):
        assert required in body
    for role in (
        "definition",
        "invariant",
        "law",
        "derived_model",
        "approximation",
        "empirical_fit",
        "qualified_relation",
    ):
        assert role in body
    for decision_use in (
        "explanation_only",
        "deterministic_rule",
        "formal_reference",
    ):
        assert decision_use in body
    assert "semantic_expression이 권위" in body
    assert "LaTeX는 권위가 아닌" in body
    assert "arbitrary Python" in body
    assert "Admin" in body and "Power User" in body


def test_all_science_harnesses_reference_equation_contract_without_changing_authority():
    for name in (
        "science-source-curation-harness.md",
        "science-knowledge-authoring-harness.md",
        "science-rule-qualification-harness.md",
        "science-verification-harness.md",
    ):
        _metadata, body = _frontmatter_and_body(REPO_HARNESS_ROOT / name)
        assert "science-equation-knowledge-harness.md" in body
        assert "science.admin" in body
        assert "self-approval" in body


def test_equation_harness_grounds_each_explanation_block_to_exact_release_objects():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-equation-knowledge-harness.md"
    )

    # A prose-only explanation could look plausible while losing the exact equation,
    # rule, quote, and source identities that constrain it.
    for required in (
        "fact_id",
        "knowledge_ref",
        "equation_ref",
        "rule_ref",
        "evidence_ref",
        "source_ref",
        "quote_hash",
    ):
        assert required in body


def test_rule_harness_requires_real_claims_and_ten_decisive_case_kinds():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-rule-qualification-harness.md"
    )

    for verdict in PRIMARY_VERDICTS:
        assert verdict in body
    for case_kind in (
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
    ):
        assert case_kind in body
    assert "source_span.exact" in body
    assert "실제 과학 주장" in body
    assert "evaluation_rule_id" in body
    assert "자기 Rule" in body
    assert "unrelated subject" in body
    assert "candidate" in body
    assert "OperationalVerification" in body
    for forbidden in (
        "RPM 설정값",
        "변경 백분율",
        "DOE 시작점",
        "recipe recommendation",
    ):
        assert forbidden in body


def test_verification_harness_proves_visible_evidence_and_cross_channel_parity():
    _metadata, body = _frontmatter_and_body(
        REPO_HARNESS_ROOT / "science-verification-harness.md"
    )

    for verdict in PRIMARY_VERDICTS:
        assert verdict in body
    for required in (
        "Unicode code point",
        "보라색 점선",
        "빨간색 밑줄",
        "user confirmation",
        "ontology_refs",
        "original_text",
        "reviewed_translation",
        "locator",
        "original_url",
        "original_text_hash",
        "Knowledge digest",
        "Evidence digest",
        "Source digest",
        "Web",
        "REST",
        "MCP",
        "Markdown",
        "PDF",
        "report_digest",
    ):
        assert required in body
    assert "CONSISTENT는" in body
    assert "참·안전·승인" in body
    assert "종합 점수" in body
    assert "과학적 설명" in body
    assert "1~2개" in body


def test_science_harnesses_are_linked_from_repo_and_public_indexes():
    repo_readme = (REPO_HARNESS_ROOT / "README.md").read_text(encoding="utf-8")
    repo_matrix = (REPO_HARNESS_ROOT / "harness-responsibility-matrix.md").read_text(
        encoding="utf-8"
    )
    public_index = (PUBLIC_HARNESS_ROOT / "index.md").read_text(encoding="utf-8")
    public_matrix = (
        PUBLIC_HARNESS_ROOT / "harness-responsibility-matrix.md"
    ).read_text(encoding="utf-8")

    for name in HARNESS_NAMES:
        assert name in repo_readme
        assert name in public_index
    for label in (
        "Science Source Curation",
        "Science Knowledge Authoring",
        "Science Equation Knowledge",
        "Science Rule Qualification",
        "Science Verification",
    ):
        assert label in repo_matrix
        assert label in public_matrix
