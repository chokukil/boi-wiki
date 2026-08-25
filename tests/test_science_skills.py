from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFIER = REPO_ROOT / "skills" / "boi-science-verifier" / "SKILL.md"
CURATOR = REPO_ROOT / "skills" / "boi-science-curator" / "SKILL.md"
PARENT = REPO_ROOT / "skills" / "boi-wiki-agent" / "SKILL.md"


def _skill(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, f"{path} must have YAML frontmatter"
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def test_science_verifier_skill_is_discoverable_and_thin():
    metadata, body = _skill(VERIFIER)

    assert metadata["name"] == "boi-science-verifier"
    assert metadata["description"].startswith("Use when ")
    assert "fact check" in metadata["description"].lower()
    assert len(metadata["description"]) < 500
    assert len(body.split()) < 650
    assert "harness/science-verification-harness.md" in body
    assert "도메인 법칙" not in body
    assert "원문 인용문" not in body
    assert "mangugil" not in body


def test_verifier_skill_preserves_boi_authority_and_the_confirmation_loop():
    _metadata, body = _skill(VERIFIER)

    for tool in (
        "science_aliases_detect",
        "science_claim_submit",
        "science_verify_document",
        "science_evidence_get",
        "science_report_get",
        "science_report_export",
    ):
        assert tool in body
    assert "science_interpretation_confirm" not in body
    assert "browser-session-bound confirmation" in body
    assert "must not call a confirmation" in body
    assert body.index("science_aliases_detect") < body.index("science_claim_submit")
    assert body.index("science_claim_submit") < body.index(
        "Science Verifier web review canvas"
    )
    assert body.index("Science Verifier web review canvas") < body.index(
        "science_verify_document"
    )
    for required in (
        "결과가 달라지는 모호성",
        "명시적 사용자 확인",
        "BoI가 반환한 Verdict를 변경하지 않는다",
        "자체 지식으로 Citation",
        "Agent 기억으로 대체하지 않는다",
        "ontology_refs",
        "원문",
        "locator",
        "release",
        "report_digest",
        "optional, experimental",
        "no Claim, verdict, Evidence, Rule, or red annotation",
    ):
        assert required in body
    assert "authenticated user bearer" in body
    assert "service token" in body and "사용자 identity가 아니다" in body
    for verdict in (
        "VIOLATION",
        "CONSISTENT",
        "INSUFFICIENT_INFORMATION",
        "OUTSIDE_VALIDITY_DOMAIN",
        "EMPIRICAL_VERIFICATION_REQUIRED",
    ):
        assert verdict in body
    assert "CONSISTENT" in body and "참·안전·승인" in body
    assert "verification unavailable" in body


def test_verifier_skill_pressure_contract_keeps_equation_candidates_untrusted_and_explainable():
    _metadata, body = _skill(VERIFIER)

    # Baseline pressure failure this catches: the former skill did not tell an Agent
    # how to submit formula spans, surface symbol ambiguity, or preserve one reviewed
    # Equation identity through accessible Web/Markdown/PDF output.
    for required in (
        "equation claim proposal",
        "source span",
        "parsed expression candidate",
        "symbol",
        "quantity kind",
        "unit",
        "sign",
        "reference direction",
        "ontology",
        "purple dotted",
        "reviewed Equation",
        "semantic expression",
        "display LaTeX",
        "plain-text fallback",
        "accessibility reading",
        "report_digest",
        "export_digest",
    ):
        assert required in body
    assert "V" in body and "voltage" in body and "volume" in body
    assert "Agent가 만든 변수" in body
    assert "확인되지 않은 단위" in body
    assert "판정에 사용하지 않는다" in body


def test_curator_skill_is_proposal_only_and_matches_role_boundaries():
    metadata, body = _skill(CURATOR)

    assert metadata["name"] == "boi-science-curator"
    assert metadata["description"].startswith("Use when ")
    assert len(body.split()) < 800
    for phase in (
        "Source",
        "Evidence",
        "Knowledge",
        "Rule",
        "Qualification",
        "Release Candidate",
    ):
        assert phase in body
    for harness in (
        "science-source-curation-harness.md",
        "science-knowledge-authoring-harness.md",
        "science-equation-knowledge-harness.md",
        "science-rule-qualification-harness.md",
        "science-verification-harness.md",
    ):
        assert harness in body
    for required in (
        "제안만",
        "self-approval",
        "science.power_user:<domain>",
        "별칭·용어·해석·개념 연결",
        "법칙·수식·판정 규칙·Evidence",
        "science.admin",
        "최종 Release 활성화",
        "user_confirmed: true",
        "exact digest",
        "draft",
        "pending_review",
    ):
        assert required in body
    assert "자신이 만든 제안" in body and "승인하지 않는다" in body
    assert "authenticated user bearer" in body
    assert "service token" in body and "사용자 identity가 아니다" in body
    assert "RPM을" not in body
    assert "촉매는" not in body
    assert "옴의 법칙" not in body


def test_curator_skill_requires_validation_before_mutation_and_never_auto_activates():
    _metadata, body = _skill(CURATOR)

    for tool in (
        "science_source_validate",
        "science_evidence_validate",
        "science_knowledge_validate",
        "science_rule_qualify",
        "science_release_validate",
        "science_proposal_create",
    ):
        assert tool in body
    assert "검증 통과가 승인이라는 뜻은 아니다" in body
    assert "자동 활성화하지 않는다" in body
    assert "Admin이 원문과 exact object digest를 직접 확인" in body
    assert "inactive Evidence" in body
    assert "aggregate score" in body


def test_curator_skill_pressure_contract_requires_reviewed_equation_semantics():
    _metadata, body = _skill(CURATOR)

    # Baseline pressure failure this catches: OCR transcription, display notation,
    # executable semantics, qualification, and safe rendering were previously folded
    # into one generic "equation" word and could be treated as interchangeable.
    for required in (
        "Equation Knowledge",
        "semantic_expression",
        "display_latex",
        "plain_text",
        "accessibility_reading",
        "operator allowlist",
        "deterministic_rule",
        "explanation_only",
        "original notation",
        "notation mapping",
        "OCR",
        "equation locator",
        "equation digest",
        "science.admin",
        "Power User",
    ):
        assert required in body
    assert "LaTeX" in body and "권위가 아니다" in body
    assert "arbitrary Python" in body
    assert "수식이 있다는 이유만으로" in body
    assert "자동 활성화" in body


def test_parent_boi_skill_routes_science_work_without_copying_the_full_contract():
    _metadata, body = _skill(PARENT)

    assert "boi-science-verifier" in body
    assert "boi-science-curator" in body
    assert "science_aliases_detect" in body
    assert "science_claim_submit" in body
    assert "science_interpret" in body and "optional experimental" in body
    assert "과학적 팩트 체크" in body
    assert "Science Verifier" in body
    assert "외부 사용자 Agent" in body
    assert "내장 과학 Agent" in body
    assert "harness/science-verification-harness.md" in body
    assert body.count("VIOLATION") <= 1
    assert body.count("CONSISTENT") <= 1
