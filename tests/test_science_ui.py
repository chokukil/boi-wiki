from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_admin_review_canvas_is_candidate_only_and_nav_follows_sop(
    boi_app_module,
) -> None:
    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001")

    assert response.status_code == 200
    html = response.text
    assert (
        html.index('data-nav-id="sops"')
        < html.index('data-nav-id="science"')
        < html.index('data-nav-id="events"')
    )
    assert 'data-science-review-canvas' in html
    assert 'data-science-chat' not in html
    assert 'data-release-status="release_candidate"' in html
    assert 'data-operational="false"' in html
    assert "Admin candidate qualification preview" in html
    assert "운영 판정이 아닙니다" in html
    assert "종합점수" not in html
    assert "DOE" not in html


def test_science_release_operational_ui_requires_exact_active_status(
    boi_app_module,
) -> None:
    """Treating superseded knowledge as operational could authorize a red mark."""

    assert boi_app_module.science_release_is_operational("active") is True
    assert boi_app_module.science_release_is_operational("release_candidate") is False
    assert boi_app_module.science_release_is_operational("superseded") is False
    assert boi_app_module.science_release_is_operational("withdrawn") is False


def test_candidate_demo_never_renders_inactive_expected_violation_as_red(
    boi_app_module,
) -> None:
    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001&demo=1")

    assert response.status_code == 200
    html = response.text
    assert html.count('class="science-violation"') == 0
    assert html.count('class="science-preview-expected-violation"') == 1
    assert html.count('class="science-ambiguity"') == 1
    assert 'data-preview-outcome="VIOLATION"' in html
    assert 'data-preview-outcome="AMBIGUITY_GATE"' in html
    assert "자동화 후보 Qualification 기대 결과" in html
    assert "충분한 과학적 설명" in html
    assert "이번 검증에서 수정" in html
    assert "전역 개선 제안" in html


def test_candidate_demo_exposes_traceable_source_and_interpretation_details(
    boi_app_module,
) -> None:
    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001&demo=1")

    assert response.status_code == 200
    html = response.text
    assert "결정 근거 1" in html
    assert "microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf" in html
    assert "원문" in html
    assert "검토 번역" in html
    assert "Influence of the Attained Spin Speed" in html
    assert "통상적으로 레지스트의 스핀 오프가 건조로 멈출 때까지" in html
    assert "sci:binding:domain:spin-speed" in html
    assert "sci:binding:domain:film-thickness" in html
    assert "온톨로지는 해석에만 사용하며 판정 방향을 만들지 않습니다" in html


def test_science_ui_and_navigation_preserve_admin_only_gate(boi_app_module) -> None:
    client = TestClient(boi_app_module.app)

    power_user_response = client.get("/science-verifier?employee_id=100002")
    viewer_sops = client.get("/sops?employee_id=100003")
    admin_sops = client.get("/sops?employee_id=100001")

    assert power_user_response.status_code == 403
    assert 'data-nav-id="science"' not in viewer_sops.text
    assert 'data-nav-id="science"' in admin_sops.text


def test_authorized_wiki_document_offers_selection_handoff(boi_app_module) -> None:
    client = TestClient(boi_app_module.app)
    boi_id = "boi:public:science:knowledge:spin-coating:004"

    response = client.get(f"/docs/{boi_id}?employee_id=100001")

    assert response.status_code == 200
    html = response.text
    assert 'data-science-document-ref="boi:public:science:knowledge:spin-coating:004"' in html
    assert "선택 영역 과학 검증" in html
    assert "/static/science_verifier_selection.js" in html


def test_default_web_path_is_deterministic_and_qwen_is_explicitly_experimental(
    boi_app_module,
) -> None:
    """Removing the alias-first controls must break the no-LLM product path."""

    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001")

    assert response.status_code == 200
    html = response.text
    assert 'data-science-alias-detect' in html
    assert "1. 등록 용어 찾기" in html
    assert "2. 주장 구조 확인" in html
    assert "3. 확정한 주장 검증" in html
    assert 'data-science-candidate-editor' in html
    assert 'data-science-qwen-experimental' in html
    assert "선택적·실험적 Qwen 해석" in html
    assert "Qwen 없이도 검토와 검증을 완료할 수 있습니다" in html
    assert html.count('class="science-violation"') == 0


def test_manual_claim_editor_exposes_roles_conditions_and_local_proposal_boundary(
    boi_app_module,
) -> None:
    """Collapsing S/R/O or proposal actions would make manual verification unsafe."""

    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001")

    assert response.status_code == 200
    html = response.text
    assert 'name="subject_match"' in html
    assert 'name="relation_match"' in html
    assert 'name="object_match"' in html
    assert 'name="relation_kind"' in html
    assert 'name="polarity"' in html
    assert 'name="conditions"' in html
    assert 'name="process_stage"' in html
    assert 'name="material_state"' in html
    assert "이번 검증에서만 수정" in html
    assert "전역 용어 개선 제안" in html
    assert "Power User 또는 Admin이 채택하기 전에는 전역 지식이 바뀌지 않습니다" in html


def test_browser_contract_builds_exact_manual_candidate_and_gates_red_mark() -> None:
    """A permissive client payload or red-mark gate must fail this contract test."""

    module_url = (REPO_ROOT / "boi_api/app/static/science_verifier_core.mjs").as_uri()
    script = f"""
      import {{ buildManualCandidate, trustedViolationState }} from {json.dumps(module_url)};
      const documentText = '동일 조건에서 RPM을 높이면 두께가 증가한다.';
      const matches = [
        {{ ontology_ref:'sci:binding:rpm', binding_digest:'sha256:'+'a'.repeat(64), concept_id:'sci:concept:rpm', surface_term:'RPM', start:8, end:11, meaning:'rotation speed', domain:'spin' }},
        {{ ontology_ref:'sci:binding:increases', binding_digest:'sha256:'+'b'.repeat(64), concept_id:'increases', surface_term:'높이면', start:13, end:16, meaning:'asserted increase', domain:'common' }},
        {{ ontology_ref:'sci:binding:thickness', binding_digest:'sha256:'+'c'.repeat(64), concept_id:'sci:concept:film-thickness', surface_term:'두께', start:17, end:19, meaning:'film thickness', domain:'spin' }},
      ];
      const candidate = buildManualCandidate({{
        documentText, claimStart:8, claimEnd:25, matches,
        selected: {{ subject:0, relation:1, object:2 }},
        relationKind:'monotonic_direction', polarity:'positive',
        conditionsText:'same_resist=true\\nspin_time=30 s',
        processStage:'final_coat_spin', materialState:'liquid_film'
      }});
      const complete = {{
        verdict:'VIOLATION', decisive_rule_ids:['sci-rule:spin:1'],
        evidence_refs:['sci:evidence:1'],
        condition_evaluations:[{{ condition_id:'same_resist', satisfied:true }}]
      }};
      const annotation = {{ evidence_links:[{{
        evidence_id:'sci:evidence:1',
        locator:{{ section:'3.2' }},
        reviewed_source:{{ qualification_state:'active' }},
        url:'https://example.org/source'
      }}] }};
      console.log(JSON.stringify({{
        candidate,
        inactive: trustedViolationState(complete, [annotation], false),
        noEvidence: trustedViolationState(complete, [], true),
        complete: trustedViolationState(complete, [annotation], true),
      }}));
    """

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    candidate = payload["candidate"]
    assert candidate["source_span"]["exact"] == "RPM을 높이면 두께가 증가한다"
    assert candidate["normalized_claim"]["subject_concept_id"] == "sci:concept:rpm"
    assert candidate["normalized_claim"]["predicate"] == "increases"
    assert candidate["normalized_claim"]["object_concept_id"] == "sci:concept:film-thickness"
    assert candidate["normalized_claim"]["conditions"] == [
        {"condition_id": "same_resist", "value": True, "unit": None},
        {"condition_id": "spin_time", "value": 30, "unit": "s"},
    ]
    assert payload == {
        "candidate": candidate,
        "inactive": False,
        "noEvidence": False,
        "complete": True,
    }


def test_real_alias_api_does_not_match_r_inside_rpm_but_keeps_standalone_r(
    boi_app_module,
) -> None:
    """The Web API must expose the same token-safe deterministic detector."""

    client = TestClient(boi_app_module.app)
    document = "RPM은 회전 속도이고, R은 저항이다."

    response = client.post(
        "/api/science/aliases/detect?employee_id=100001",
        json={"document": document, "request_id": "science-ui-token-boundary"},
    )

    assert response.status_code == 200
    matches = [
        match
        for match in response.json()["matches"]
        if match["concept_id"] == "sci:concept:resistance"
        and match["surface_term"] == "R"
    ]
    assert [(match["start"], match["end"]) for match in matches] == [
        (document.index(", R") + 2, document.index(", R") + 3)
    ]
