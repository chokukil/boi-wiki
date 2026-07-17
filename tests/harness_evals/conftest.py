from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from boi_api.app import harness_meta

REPO_ROOT = Path(__file__).resolve().parents[2]

# grading 판정과 무관한 suite 자체의 실행 통계 (harness_eval_status 기록용).
_RESULTS = {"total": 0, "passed": 0}


def pytest_runtest_logreport(report):
    if report.when != "call" or "harness_evals" not in str(report.nodeid):
        return
    _RESULTS["total"] += 1
    if report.passed:
        _RESULTS["passed"] += 1


@pytest.fixture(scope="session", autouse=True)
def record_harness_eval_status():
    """suite 종료 시 eval 상태를 실제 repo runtime root(data/)에 기록한다.

    기본은 기록하지 않는다: CI/임시 환경 실행이 트리를 더럽히지 않도록
    env BOI_HARNESS_EVAL_RECORD=1일 때만 기록한다 (harness/README.md 참조).
    acceptance `Meta` 버킷의 harness_eval_status가 이 기록을 소비한다.
    """
    yield
    if os.getenv("BOI_HARNESS_EVAL_RECORD") != "1":
        return
    if not _RESULTS["total"]:
        return
    harness_meta.write_eval_status(
        REPO_ROOT / "data",
        {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "total": _RESULTS["total"],
            "passed": _RESULTS["passed"],
        },
    )


@pytest.fixture()
def mcp_app_module(monkeypatch: pytest.MonkeyPatch):
    """boi_wiki_mcp를 서버 없이 standalone import한다 (쓰기 경계 거부는 API 호출 전에 일어난다)."""
    monkeypatch.setenv("SERVICE_TOKEN", "harness-eval-service-token")
    monkeypatch.setenv("DEFAULT_EMPLOYEE_ID", "100001")
    sys.modules.pop("boi_wiki_mcp.app.main", None)
    module = importlib.import_module("boi_wiki_mcp.app.main")
    yield module
    sys.modules.pop("boi_wiki_mcp.app.main", None)
