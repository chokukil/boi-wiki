#!/usr/bin/env python3
"""Run an isolated UI acceptance server with a reviewable Harness candidate."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_local_model_environment(path: Path) -> None:
    allowed_prefixes = (
        "BOI_V2_MODEL", "BOI_LLM_", "BOI_AGENT_LLM_", "BOI_AGENT_ROUTER_",
        "BOI_LMSTUDIO_", "BOI_EMBEDDING_",
    )
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (item.strip() for item in line.split("=", 1))
        if not key.startswith(allowed_prefixes) or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


if "--use-local-model" in sys.argv:
    load_local_model_environment(ROOT / ".env")

from boi_api.app.main import AGENT_V2_SERVICE, app
from boi_api.app.v2.models import (
    HarnessCandidateCreateRequest,
    HarnessCandidateEvaluateRequest,
    HarnessCandidateReviewRequest,
    HarnessCandidateShadowRequest,
    Principal,
)


def seed_harness_candidate(employee_id: str) -> str:
    service = AGENT_V2_SERVICE
    principal = Principal(
        employee_id=employee_id,
        display_name="Browser Acceptance Admin",
        auth_source="acceptance_fixture",
        roles=["boi.viewer", "boi.editor", "boi.admin"],
        scopes=["boi.read", "boi.draft", "boi.admin"],
    )
    failure_id = "browser-acceptance-harness-failure"
    service.store.put(
        "harness_failure_records",
        failure_id,
        {
            "failure_record_id": failure_id,
            "employee_id": employee_id,
            "harness_id": "context.work",
            "causal_agent_stage": "context.evidence",
            "status": "open",
            "summary": "브라우저 검증용 반복 근거 누락",
        },
    )
    candidate = service.learning.create_harness_candidate(
        principal,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=[failure_id],
            model_profile=service.learning.model_profile,
            changes={"retrieval_policy": {"authority_weight": 1.05}},
            rationale="격리 브라우저 검증에서 검토 화면과 배포 연습 경계를 확인하는 후보입니다.",
        ),
    )
    shadow = service.learning.shadow_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateShadowRequest(fixture_revision="browser-acceptance-v1"),
    )
    evaluated = service.learning.evaluate_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateEvaluateRequest(
            shadow_run_id=shadow["shadow_run"]["shadow_run_id"],
            held_in={"passed": True},
            held_out={"passed": True, "regressions": 0},
            adversarial={"passed": True, "unauthorized_mutations": 0},
            long_term={"passed": True, "regressions": 0},
            fixture_revision="browser-acceptance-v1",
        ),
    )
    service.learning.review_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateReviewRequest(
            decision="approve_for_release",
            expected_eval_id=evaluated["evaluation"]["eval_id"],
            note="격리 브라우저에서 배포 연습 UI만 검증합니다.",
        ),
    )
    service.knowledge.compile_graph(principal)
    return str(candidate["candidate_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--use-local-model", action="store_true")
    args = parser.parse_args()
    seed_harness_candidate(args.employee_id)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
