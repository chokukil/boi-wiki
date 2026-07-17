from __future__ import annotations

"""골든 태스크 회귀 eval — LLM 호출 없음, 순수 pytest (계획서 §4.5 Phase 4).

이 파일은 결과물 생성(게시/호출)만 수행하고, 판정은 전부 grading 모듈(단일
평가자)에 위임한다. 채점 로직을 여기에 추가하지 말 것 (생성자/평가자 분리).
"""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from harness_evals import grading

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN_HTML = (FIXTURES / "golden-dashboard.html").read_text(encoding="utf-8")
GOLDEN_NAME = "harness-eval-golden-dashboard"


def publish_golden(boi_app_module) -> TestClient:
    boi_app_module.BOI_AUTO_COMMIT = False
    client = TestClient(boi_app_module.app)
    response = client.post(
        "/api/share/html?employee_id=100001",
        data={
            "title": "주간 설비 가동 대시보드",
            "description": "harness eval golden task",
            "visibility": "public",
            "name": GOLDEN_NAME,
        },
        files={"file": ("golden-dashboard.html", GOLDEN_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 200, f"golden publish failed (generation step): {response.text}"
    return client


def test_eval_a_html_share_golden_task(boi_app_module):
    client = publish_golden(boi_app_module)
    data_root = boi_app_module.DATA_ROOT
    stored = data_root / "public" / "html" / f"{GOLDEN_NAME}.html"
    viewer = client.get(f"/{GOLDEN_NAME}?employee_id=100002")
    raw = client.get(f"/r/{GOLDEN_NAME}?employee_id=100002")

    failures = grading.grade_html_share(
        data_root=data_root,
        stored_path=stored,
        viewer_html=viewer.text,
        raw_headers=raw.headers,
    )
    assert not failures, "\n".join(failures)


def test_eval_a_confirmed_write_boundary(mcp_app_module):
    # MCP tool handler를 서버 없이 직접 호출한다: user_confirmed 거부는 API 호출보다 앞선다.
    refusal: BaseException | None = None
    try:
        asyncio.run(
            mcp_app_module.html_share_publish(
                content=GOLDEN_HTML,
                name=GOLDEN_NAME,
                employee_id="100001",
                user_confirmed=False,
            )
        )
    except RuntimeError as exc:
        refusal = exc

    failures = grading.grade_confirmed_write_refusal(refusal)
    assert not failures, "\n".join(failures)


def test_eval_b_knowledge_card_contract(boi_app_module):
    publish_golden(boi_app_module)
    data_root = boi_app_module.DATA_ROOT
    stored = data_root / "public" / "html" / f"{GOLDEN_NAME}.html"

    failures = grading.grade_okf_doc(
        card_path=stored.with_suffix(".md"),
        data_root=data_root,
        html_path=stored,
    )
    assert not failures, "\n".join(failures)


def test_eval_c_harness_doc_integrity():
    failures = grading.grade_harness_meta(REPO_ROOT, REPO_ROOT / "data" / "boi")
    assert not failures, "\n".join(failures)
