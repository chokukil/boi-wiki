"""Retire legacy semantic shortcuts without granting alternative authority."""
from typing import NoReturn
from fastapi import HTTPException

def reject_unstructured_selection() -> NoReturn:
    raise HTTPException(status_code=409, detail={
        "code": "SEMANTIC_PLAN_SUBMISSION_REQUIRED",
        "message": "의미 판단 불가: 이 경로의 문자열 기반 선택은 차단되었습니다. 공식 native query에 구조화된 계획을 제출하고 현재 명세 검증을 수행하세요.",
        "operation_outcome": "not_established",
        "automatic_retry": False,
    })
