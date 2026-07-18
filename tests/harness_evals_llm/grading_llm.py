from __future__ import annotations

"""LLM 골든 태스크 eval 채점기 (계획서 §10 P2-20, 옵트인 스켈레톤).

생성자/평가자 분리(tests/harness_evals/grading.py와 같은 원칙): 결과물을 만드는 코드
(LLM 호출)와 채점하는 이 모듈을 분리한다. 이 모듈은 무겁지 않아야 한다 — 이 파일은
`BOI_HARNESS_LLM_EVALS`가 꺼져 있어도(기본값) pytest 수집 시 항상 import되므로,
`boi_api.app.main`처럼 무거운 모듈을 끌어오지 않는다(로드 자체가 skip 여부와 무관하게
비용이 들면 "기본 실행은 skip으로 가볍게"라는 목표를 깨뜨린다).
"""

import re
from typing import Any

MAX_TAGS = 8
MIN_TITLE_CHARS = 2
MAX_TITLE_CHARS = 120
MIN_DESCRIPTION_CHARS = 10
MAX_DESCRIPTION_CHARS = 600

_HANGUL_RE = re.compile(r"[가-힣]")
# boi_api.app.main.SECRET_VALUE_RE를 그대로 복제한다(이 모듈은 main.py를 import하지 않는다 —
# 기본 skip 경로의 수집 비용을 낮게 유지하기 위해서다. 두 정의가 갈라지면 안 되므로 패턴을
# 바꿀 때는 반드시 boi_api/app/main.py의 SECRET_VALUE_RE도 함께 갱신할 것).
_SECRET_VALUE_RE = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})"
    r"|(?i:(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{8,})"
)


def _has_korean(text: str) -> bool:
    return bool(_HANGUL_RE.search(str(text or "")))


def grade_share_draft(result: dict[str, Any]) -> list[str]:
    """composer가 생성한 {title, description, tags} 초안을 결정적으로 채점한다.

    하드 기준: 한국어 출력, title/description 길이 범위, tags 8개 이하, 비밀 값 패턴 없음.
    """
    failures: list[str] = []
    if not isinstance(result, dict):
        return [f"composer result must be a dict, got {type(result)!r}"]

    title = str(result.get("title") or "").strip()
    description = str(result.get("description") or "").strip()
    tags = result.get("tags") or []

    if not title:
        failures.append("title must not be empty")
    elif not (MIN_TITLE_CHARS <= len(title) <= MAX_TITLE_CHARS):
        failures.append(f"title length must be within [{MIN_TITLE_CHARS}, {MAX_TITLE_CHARS}], got {len(title)}")
    elif not _has_korean(title):
        failures.append(f"title must be Korean output, got {title!r}")

    if not description:
        failures.append("description must not be empty")
    elif not (MIN_DESCRIPTION_CHARS <= len(description) <= MAX_DESCRIPTION_CHARS):
        failures.append(
            f"description length must be within [{MIN_DESCRIPTION_CHARS}, {MAX_DESCRIPTION_CHARS}], got {len(description)}"
        )
    elif not _has_korean(description):
        failures.append(f"description must be Korean output, got {description!r}")

    if not isinstance(tags, list):
        failures.append(f"tags must be a list, got {type(tags)!r}")
    elif len(tags) > MAX_TAGS:
        failures.append(f"tags must have at most {MAX_TAGS} items, got {len(tags)}")

    combined_text = " ".join([title, description, " ".join(str(tag) for tag in tags)])
    if _SECRET_VALUE_RE.search(combined_text):
        failures.append("composer output must not contain secret-looking values (api key/token/password patterns)")

    return failures
