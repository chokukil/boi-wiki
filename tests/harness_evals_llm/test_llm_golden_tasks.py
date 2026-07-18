from __future__ import annotations

"""LLM 골든 태스크 eval (계획서 §10 P2-20) — 옵트인 스켈레톤.

`tests/harness_evals/`(결정적 suite)와 별도 디렉터리다: 실제 에이전트/LLM 호출로 저작
태스크를 수행시키고 결과를 채점하는 이 suite는 네트워크·LLM 가용성에 의존하므로
`tests/harness_evals`의 회귀 게이트(harness_eval_status)에는 절대 포함하지 않는다.

기본 실행(`pytest` 전체 또는 이 파일 단독)은 항상 SKIP된다:
- `BOI_HARNESS_LLM_EVALS=1`이 아니면 skip.
- composer LLM 엔드포인트(`BOI_AGENT_COMPOSER_BASE_URL`/`BOI_AGENT_COMPOSER_MODEL`)가
  설정되어 있지 않아도 skip.

옵트인되면 fixture 텍스트로 "공유 HTML의 제목/설명/태그를 초안하라"는 태스크를 composer에
요청하고, 채점은 전부 `grading_llm.py`(생성자/평가자 분리)에 위임한다.
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from harness_evals_llm import grading_llm

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "golden-share-source.txt"


def _composer_base_url() -> str:
    return str(os.getenv("BOI_AGENT_COMPOSER_BASE_URL") or "").strip()


def _composer_model() -> str:
    return str(os.getenv("BOI_AGENT_COMPOSER_MODEL") or "").strip()


def _composer_configured() -> bool:
    return bool(_composer_base_url()) and bool(_composer_model())


def _llm_evals_enabled() -> bool:
    return os.getenv("BOI_HARNESS_LLM_EVALS", "").strip() == "1" and _composer_configured()


SKIP_REASON = (
    "opt-in only: set BOI_HARNESS_LLM_EVALS=1 and configure BOI_AGENT_COMPOSER_BASE_URL/"
    "BOI_AGENT_COMPOSER_MODEL to run this suite (계획서 §10 P2-20)"
)


def call_composer_for_share_draft(source_text: str) -> dict[str, Any]:
    """composer LLM에 공유 HTML 제목/설명/태그 초안을 요청한다 (기존 BOI_AGENT_COMPOSER_* 재사용).

    실패(HTTP 오류/JSON 파싱 실패)는 그대로 예외로 전파한다 — 이 함수는 결과물을 만들
    뿐 채점하지 않는다(생성자/평가자 분리).
    """
    base_url = _composer_base_url().rstrip("/")
    model = _composer_model()
    api_key = str(os.getenv("BOI_AGENT_COMPOSER_API_KEY") or "").strip()
    timeout_seconds = float(os.getenv("BOI_AGENT_COMPOSER_TIMEOUT_SECONDS", "30") or "30")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 512,
        "messages": [
            {
                "role": "system",
                "content": (
                    "JSON만 출력하세요. 주어진 한국어 본문을 근거로 공유 HTML 문서의 제목(title)과 "
                    "설명(description)을 한국어로 작성하고, 태그(tags)를 최대 8개까지 문자열 배열로 "
                    "제안하세요. 근거에 없는 내용을 만들지 마세요."
                ),
            },
            {"role": "user", "content": source_text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "boi_share_draft",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "description"],
                },
            },
        },
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        raw = response.json()
    text = raw["choices"][0]["message"]["content"]
    return json.loads(text)


@pytest.mark.skipif(not _llm_evals_enabled(), reason=SKIP_REASON)
def test_composer_drafts_korean_share_title_description_tags_for_golden_fixture():
    source_text = FIXTURE_PATH.read_text(encoding="utf-8")
    result = call_composer_for_share_draft(source_text)
    failures = grading_llm.grade_share_draft(result)
    assert not failures, "\n".join(failures)
