from __future__ import annotations

import base64
from functools import partial
import hashlib
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import shutil
import subprocess
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _equation_browser_result(tmp_path: Path) -> dict[str, object]:
    module_path = REPO_ROOT / "boi_api/app/static/science_equation_view.mjs"
    target_module = tmp_path / module_path.name
    if module_path.exists():
        shutil.copyfile(module_path, target_module)
    else:
        target_module.write_text(
            "export async function mountEquationAssets() { return []; }\n",
            encoding="utf-8",
        )
    shutil.copyfile(
        REPO_ROOT / "boi_api/app/static/science_verifier_core.mjs",
        tmp_path / "science_verifier_core.mjs",
    )
    shutil.copyfile(REPO_ROOT / "boi_api/app/static/style.css", tmp_path / "style.css")

    safe_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" '
        'viewBox="0 0 240 80" role="img" focusable="false" '
        'aria-label="전압은 전류와 저항의 곱입니다.">'
        '<path d="M10 40 L230 40" fill="none" stroke="currentColor" '
        'stroke-width="2"/></svg>'
    )
    hostile_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" '
        'viewBox="0 0 240 80" role="img" focusable="false" '
        'aria-label="공격 수식"><script>document.body.dataset.pwned="yes"</script>'
        '<path d="M0 0 L10 10"/></svg>'
    )
    attribute_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" '
        'viewBox="0 0 240 80" role="img" focusable="false" '
        'aria-label="속성 공격"><path d="M0 0 L10 10" '
        'style="fill:url(https://example.invalid/x)" href="https://example.invalid/x" '
        'onload="document.body.dataset.pwned=\'yes\'"/></svg>'
    )
    xlink_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" width="240" height="80" '
        'viewBox="0 0 240 80" role="img" focusable="false" '
        'aria-label="링크 공격"><path d="M0 0 L10 10" '
        'xlink:href="https://example.invalid/x"/></svg>'
    )
    safe_digest = "sha256:" + hashlib.sha256(safe_svg.encode()).hexdigest()
    hostile_digest = "sha256:" + hashlib.sha256(hostile_svg.encode()).hexdigest()
    equation_digest = "sha256:" + "a" * 64
    asset_base = {
        "equation_id": "sci:equation:ohms-law",
        "equation_digest": equation_digest,
        "display_latex": r"V = I \\cdot R",
        "plain_text": "V = I * R",
        "accessibility_reading": "전압은 전류와 저항의 곱입니다.",
        "variables": [
            {
                "symbol": "V",
                "definition": "전압",
                "unit": "V",
            },
            {
                "symbol": "I",
                "definition": "전류",
                "unit": "A",
            },
        ],
        "applicability": ["검토된 저항 모델 안에서 사용"],
        "invalid_outside": ["비선형 소자에 일반화하지 않음"],
        "evidence_links": [
            {
                "evidence_id": "sci:evidence:ohms-law",
                "source_id": "sci:source:ohms-law",
                "url": "https://example.test/ohms-law",
            },
            {
                "evidence_id": "sci:evidence:unsafe",
                "source_id": "sci:source:unsafe",
                "url": "javascript:document.body.dataset.pwned='yes'",
            },
        ],
    }
    payload = {
        "safe_svg": safe_svg,
        "safe_digest": safe_digest,
        "hostile_svg": hostile_svg,
        "hostile_digest": hostile_digest,
        "attribute_svg": attribute_svg,
        "attribute_digest": "sha256:"
        + hashlib.sha256(attribute_svg.encode()).hexdigest(),
        "xlink_svg": xlink_svg,
        "xlink_digest": "sha256:" + hashlib.sha256(xlink_svg.encode()).hexdigest(),
        "equation_digest": equation_digest,
        "asset_base": asset_base,
    }
    encoded_payload = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="./style.css"></head>
<body><mark class="science-violation">원문 위반 표시</mark><article id="card" class="science-correction-card violation"></article><pre id="result"></pre>
<script type="module">
import {{ equationEvidenceLinks, mountEquationAssets }} from './science_equation_view.mjs';
import {{ appendGroundedExplanationBlocks }} from './science_verifier_core.mjs';
const fixture = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('{encoded_payload}'), (character) => character.charCodeAt(0))));
const report = (asset, refDigest = fixture.equation_digest) => ({{
  explanations: [{{ claim_id: 'claim-1', equation_refs: [{{ equation_id: asset.equation_id, equation_digest: refDigest }}] }}],
  equation_assets: [asset],
}});
const mount = async (asset, options = {{}}) => {{
  const host = document.createElement('section');
  document.querySelector('#card').appendChild(host);
  await mountEquationAssets(host, report(asset), 'claim-1', options);
  return host;
}};
const copied = [];
const safe = await mount({{ ...fixture.asset_base, sanitized_svg: fixture.safe_svg, svg_digest: fixture.safe_digest }}, {{ writeClipboard: async (value) => copied.push(value) }});
for (const button of safe.querySelectorAll('button')) {{ button.click(); await Promise.resolve(); }}
const hostile = await mount({{ ...fixture.asset_base, plain_text: 'hostile fallback', accessibility_reading: '공격 수식', sanitized_svg: fixture.hostile_svg, svg_digest: fixture.hostile_digest }});
const attributes = await mount({{ ...fixture.asset_base, plain_text: 'attribute fallback', accessibility_reading: '속성 공격', sanitized_svg: fixture.attribute_svg, svg_digest: fixture.attribute_digest }});
const xlink = await mount({{ ...fixture.asset_base, plain_text: 'xlink fallback', accessibility_reading: '링크 공격', sanitized_svg: fixture.xlink_svg, svg_digest: fixture.xlink_digest }});
const mismatched = await mount({{ ...fixture.asset_base, plain_text: 'digest fallback', sanitized_svg: fixture.safe_svg, svg_digest: 'sha256:' + '0'.repeat(64) }});
const noCrypto = await mount({{ ...fixture.asset_base, plain_text: 'crypto fallback', sanitized_svg: fixture.safe_svg, svg_digest: fixture.safe_digest }}, {{ crypto: null }});
const orphan = document.createElement('section');
await mountEquationAssets(orphan, report({{ ...fixture.asset_base, sanitized_svg: fixture.safe_svg, svg_digest: fixture.safe_digest }}, 'sha256:' + 'b'.repeat(64)), 'claim-1');
const legacy = document.createElement('section');
await mountEquationAssets(legacy, {{ verdict_packets: [] }}, 'claim-1');
const grounded = document.createElement('section');
appendGroundedExplanationBlocks(grounded, {{
  explanations: [{{
    claim_id: 'claim-1', fact_id: 'fact-1', blocks: [
      {{ sequence: 1, block_kind: 'applied_principle', text: '이미 표시된 원리' }},
      {{ sequence: 2, block_kind: 'claim_mapping', text: 'R은 Claim의 회전 속도에 대응합니다.' }},
      {{ sequence: 3, block_kind: 'scientific_consequence', text: '회전 속도 증가 주장은 검토된 관계와 반대입니다.' }},
      {{ sequence: 4, block_kind: 'evidence', text: '<img src=x onerror=document.body.dataset.pwned="yes">' }},
    ],
  }}],
}}, 'claim-1', {{ excludedTexts: ['이미 표시된 원리'] }});
const detail = safe.querySelector('.science-equation-detail-list');
const scroll = safe.querySelector('.science-equation-scroll');
document.querySelector('#result').textContent = JSON.stringify({{
  safeSvg: Boolean(safe.querySelector('svg')),
  safeAria: safe.querySelector('svg')?.getAttribute('aria-label') || null,
  safeFallbackHidden: safe.querySelector('.science-equation-fallback')?.hidden === true,
  hostileFallback: hostile.querySelector('.science-equation-fallback')?.textContent || null,
  hostileSvg: Boolean(hostile.querySelector('svg, script')),
  attributeFallback: attributes.querySelector('.science-equation-fallback')?.textContent || null,
  attributeSvg: Boolean(attributes.querySelector('svg')),
  xlinkFallback: xlink.querySelector('.science-equation-fallback')?.textContent || null,
  xlinkSvg: Boolean(xlink.querySelector('svg')),
  mismatchFallback: mismatched.querySelector('.science-equation-fallback')?.textContent || null,
  noCryptoFallback: noCrypto.querySelector('.science-equation-fallback')?.textContent || null,
  orphanChildren: orphan.childElementCount,
  legacyChildren: legacy.childElementCount,
  groundedText: grounded.textContent,
  groundedKinds: [...grounded.querySelectorAll('[data-science-explanation-kind]')].map((node) => node.dataset.scienceExplanationKind),
  groundedImages: grounded.querySelectorAll('img').length,
  copied,
  buttonLabels: [...safe.querySelectorAll('button')].map((node) => node.textContent),
  live: safe.querySelector('[aria-live="polite"]')?.textContent || null,
  summary: safe.querySelector('summary')?.textContent || null,
  equationEvidence: equationEvidenceLinks([fixture.asset_base]).map((link) => link.source_id),
  cardClass: document.querySelector('#card').className,
  redMarks: document.querySelectorAll('.science-violation').length,
  pwned: document.body.dataset.pwned || null,
  mobileColumns: detail ? getComputedStyle(detail).gridTemplateColumns : null,
  scrollOverflow: scroll ? getComputedStyle(scroll).overflowX : null,
}});
</script></body></html>"""
    (tmp_path / "index.html").write_text(page, encoding="utf-8")

    handler = partial(_QuietStaticHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    chromium = (
        shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
    )
    assert chromium, "a Chromium browser is required for equation DOM tests"
    try:
        completed = subprocess.run(
            [
                chromium,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--window-size=390,844",
                "--dump-dom",
                f"http://127.0.0.1:{server.server_port}/index.html",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert completed.returncode == 0, completed.stderr
    match = re.search(r'<pre id="result">(.*?)</pre>', completed.stdout, re.S)
    assert match, completed.stdout
    return json.loads(html.unescape(match.group(1)))


@pytest.fixture(scope="module")
def equation_browser_result(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, object]:
    return _equation_browser_result(tmp_path_factory.mktemp("science-equation-view"))


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


def test_equation_view_renders_only_explicitly_bound_safe_assets(
    equation_browser_result: dict[str, object],
) -> None:
    assert equation_browser_result["safeSvg"] is True
    assert equation_browser_result["safeAria"] == "전압은 전류와 저항의 곱입니다."
    assert equation_browser_result["safeFallbackHidden"] is True
    assert equation_browser_result["orphanChildren"] == 0
    assert equation_browser_result["legacyChildren"] == 0


def test_equation_view_fails_to_plain_text_without_mutating_verdict_marks(
    equation_browser_result: dict[str, object],
) -> None:
    assert equation_browser_result["hostileFallback"] == "hostile fallback"
    assert equation_browser_result["hostileSvg"] is False
    assert equation_browser_result["attributeFallback"] == "attribute fallback"
    assert equation_browser_result["attributeSvg"] is False
    assert equation_browser_result["xlinkFallback"] == "xlink fallback"
    assert equation_browser_result["xlinkSvg"] is False
    assert equation_browser_result["mismatchFallback"] == "digest fallback"
    assert equation_browser_result["noCryptoFallback"] == "crypto fallback"
    assert equation_browser_result["cardClass"] == "science-correction-card violation"
    assert equation_browser_result["redMarks"] == 1
    assert equation_browser_result["pwned"] is None


def test_equation_view_copy_aria_and_mobile_contract(
    equation_browser_result: dict[str, object],
) -> None:
    assert equation_browser_result["copied"] == [r"V = I \\cdot R", "V = I * R"]
    assert equation_browser_result["buttonLabels"] == [
        "LaTeX 복사",
        "일반 텍스트 복사",
    ]
    assert equation_browser_result["live"] == "일반 텍스트를 복사했습니다."
    assert equation_browser_result["summary"] == "변수·적용 조건·한계"
    assert equation_browser_result["equationEvidence"] == ["sci:source:ohms-law"]
    assert equation_browser_result["mobileColumns"] != "none"
    assert equation_browser_result["scrollOverflow"] == "auto"


def test_web_grounded_explanation_shows_claim_mapping_and_scientific_consequence(
    equation_browser_result: dict[str, object],
) -> None:
    """The Web details must preserve reviewed explanation text without HTML trust."""

    assert "R은 Claim의 회전 속도에 대응합니다." in equation_browser_result[
        "groundedText"
    ]
    assert "회전 속도 증가 주장은 검토된 관계와 반대입니다." in (
        equation_browser_result["groundedText"]
    )
    assert "이미 표시된 원리" not in equation_browser_result["groundedText"]
    assert equation_browser_result["groundedKinds"] == [
        "claim_mapping",
        "scientific_consequence",
        "evidence",
    ]
    assert equation_browser_result["groundedImages"] == 0
    assert equation_browser_result["pwned"] is None


def test_science_verifier_loads_equation_view_as_optional_report_layer(
    boi_app_module,
) -> None:
    client = TestClient(boi_app_module.app)

    response = client.get("/science-verifier?employee_id=100001")

    assert response.status_code == 200
    assert "data-science-equation-view-url" in response.text
    script = (REPO_ROOT / "boi_api/app/static/science_verifier.js").read_text(
        encoding="utf-8"
    )
    assert "scienceEquationViewUrl" in script
    assert "mountResolvedEquationAssets" in script
    assert "groundedExplanationBlocks" in script
    assert "appendGroundedExplanationBlocks" in script


def test_science_release_operational_ui_requires_authoritative_catalog_capability(
    boi_app_module,
) -> None:
    """An active label must never substitute for the operational authority gate."""

    class RejectingCatalog:
        def active_release(self):
            from boi_api.app.science.exceptions import ScienceOperationalError

            raise ScienceOperationalError("holdout is not exact")

    active = SimpleNamespace(release_id="sci-release:fixture", status="active")
    candidate = SimpleNamespace(
        release_id="sci-release:fixture", status="release_candidate"
    )

    assert boi_app_module.science_release_operational_state(
        RejectingCatalog(), active
    ) == (False, "operational_authority_unavailable")
    assert boi_app_module.science_release_operational_state(
        RejectingCatalog(), candidate
    ) == (False, "release_not_active")

    class AuthorizedCatalog:
        def active_release(self):
            return active

        def resolve_release_set(self, selection):
            assert selection.foundation == active.release_id
            return "resolved-release-set"

        def resolve_operational_rule_set(self, release_set):
            assert release_set == "resolved-release-set"
            return "operational-capability"

    assert boi_app_module.science_release_operational_state(
        AuthorizedCatalog(), active
    ) == (True, "operational_authority_verified")


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
    script = (REPO_ROOT / "boi_api/app/static/science_verifier.js").read_text(
        encoding="utf-8"
    )
    assert "사용자 확인 대상 조건" in script
    assert "Rule에 조건이 필요하면 판정을 보류합니다" in script
    assert "Science API returned invalid JSON; no result was accepted." in script


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
        locator:{{
          medium:'pdf', exact:true, section:'3.2', pdf_page_index:6,
          printed_page:'7', resource_url:'https://example.test/source.pdf',
          requested_url:'https://example.test/source.pdf',
          resolved_url:'https://example.test/source.pdf',
          content_hash:'sha256:{'1' * 64}', retrieved_at:'2026-08-25T00:00:00Z',
          hash_scope:'retrieved_resource'
        }},
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


def test_browser_contract_carries_only_server_returned_document_lineage() -> None:
    module_url = (REPO_ROOT / "boi_api/app/static/science_verifier_core.mjs").as_uri()
    script = f"""
      import {{ sourceDocumentLineage, revisionPayload }} from {json.dumps(module_url)};
      const valid = sourceDocumentLineage({{
        document_digest: 'sha256:' + 'a'.repeat(64),
        candidate_claims: [{{ document_ref: 'boi:submitted:stable', claim_id: 'sci-claim:one' }}],
      }});
      const canonical = sourceDocumentLineage({{
        document_digest: 'sha256:' + 'b'.repeat(64),
        candidate_claims: [{{ document_ref: 'boi:public:science:document:one', claim_id: 'sci-claim:two' }}],
      }});
      const incomplete = sourceDocumentLineage({{
        document_digest: 'sha256:forged',
        candidate_claims: [{{ document_ref: 'boi:submitted:stable', claim_id: 'sci-claim:three' }}],
      }});
      const revision = revisionPayload('sci-claim:one', valid);
      const unbound = revisionPayload(null, valid);
      const canonicalRevision = revisionPayload('sci-claim:two', canonical);
      console.log(JSON.stringify({{ valid, canonical, incomplete, revision, unbound, canonicalRevision }}));
    """

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "valid": {
            "document_ref": "boi:submitted:stable",
            "document_digest": "sha256:" + "a" * 64,
        },
        "canonical": {
            "document_ref": "boi:public:science:document:one",
            "document_digest": "sha256:" + "b" * 64,
        },
        "incomplete": None,
        "revision": {
            "supersedes_claim_id": "sci-claim:one",
            "source_lineage": {
                "document_ref": "boi:submitted:stable",
                "document_digest": "sha256:" + "a" * 64,
            },
        },
        "unbound": {},
        "canonicalRevision": {
            "supersedes_claim_id": "sci-claim:two",
            "source_lineage": {
                "document_ref": "boi:public:science:document:one",
                "document_digest": "sha256:" + "b" * 64,
            },
        },
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


def test_browser_disabled_adapter_contract_rejects_other_qwen_failures() -> None:
    """A timeout must not be mislabeled as proof that the adapter is disabled."""

    module_url = (REPO_ROOT / "scripts" / "science_browser_contract.mjs").as_uri()
    script = f"""
      import {{ isExactDisabledAdapterResponse }} from {json.dumps(module_url)};
      const base = {{
        url: 'http://localhost/api/science/interpret',
        status: 503,
        payload: {{ detail: {{
          code: 'science_interpretation_unavailable',
          diagnostic_code: 'adapter_disabled',
        }} }},
      }};
      console.log(JSON.stringify({{
        exact: isExactDisabledAdapterResponse(base),
        timeout: isExactDisabledAdapterResponse({{
          ...base,
          payload: {{ detail: {{ ...base.payload.detail, diagnostic_code: 'timeout' }} }},
        }}),
        connection: isExactDisabledAdapterResponse({{
          ...base,
          payload: {{ detail: {{ ...base.payload.detail, diagnostic_code: 'connection_unavailable' }} }},
        }}),
        wrongPath: isExactDisabledAdapterResponse({{ ...base, url: 'http://localhost/api/science/aliases/detect' }}),
        wrongStatus: isExactDisabledAdapterResponse({{ ...base, status: 500 }}),
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
    assert json.loads(completed.stdout) == {
        "exact": True,
        "timeout": False,
        "connection": False,
        "wrongPath": False,
        "wrongStatus": False,
    }
