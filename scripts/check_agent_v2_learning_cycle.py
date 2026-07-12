#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Task completion, evidence capture, private learning, and new-session reuse."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--keep-candidate", action="store_true")
    return parser.parse_args()


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    params: dict[str, str],
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method, url, params=params, json=body)
    response.raise_for_status()
    return response.json()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    params = {"employee_id": args.employee_id}
    marker = f"learning-cycle-{int(time.time() * 1000)}"
    generated_candidates: list[dict[str, Any]] = []
    sessions: list[str] = []
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"marker": marker}

    with httpx.Client(timeout=args.timeout) as client:
        try:
            started = request_json(
                client,
                "POST",
                f"{base_url}/api/v2/agent/turns",
                params=params,
                body={
                    "question": (
                        "단면검사 Task를 지금 완료 처리하고 이번 판단을 다음 업무에서 재사용할 "
                        "지식으로 남겨줘. 담당자 확인이 필요한 완료 항목을 제시한 뒤 확인을 기다려줘."
                    ),
                    "page_ref": "/docs/boi:public:sop:direct-development-reporting",
                    "task_ref": "cross_section_decision",
                },
            )
            sessions.append(str(started.get("work_session_id") or ""))
            checks["natural_request_routes_to_task_work"] = started.get("capability_id") == "task.work"
            checks["manual_task_waits_for_human"] = (
                started.get("status") == "needs_input"
                and (started.get("loop_state") or {}).get("status") == "waiting_human"
            )
            details["started"] = {
                "status": started.get("status"),
                "capability_id": started.get("capability_id"),
                "loop_status": (started.get("loop_state") or {}).get("status"),
            }

            work_run_id = str(started.get("work_run_id") or "")
            revision = int((started.get("loop_state") or {}).get("revision") or 0)
            completed = request_json(
                client,
                "POST",
                f"{base_url}/api/v2/work-runs/{work_run_id}/continue",
                params=params,
                body={
                    "expected_revision": revision,
                    "confirmation": "confirm",
                    "delta": {
                        "kind": "human_input",
                        "summary": (
                            f"{marker}: Response Trend와 Map View Image를 담당자가 직접 확인했고, "
                            "단면검사가 필요하다는 판단과 예외 사항을 검토 기록에 남겼습니다."
                        ),
                        "ref": "boi:public:sop:direct-development-reporting",
                    },
                },
            )
            completed_run = completed.get("work_run") or {}
            candidates = completed.get("knowledge_candidates") or []
            checks["same_work_run_completes"] = (
                completed_run.get("work_run_id") == work_run_id
                and completed_run.get("status") == "completed"
            )
            checks["evidence_creates_private_candidate"] = bool(candidates)
            if candidates:
                selected_ref = next(
                    (
                        item
                        for item in candidates
                        if marker in str(item.get("title") or "")
                    ),
                    candidates[0],
                )
                candidate_id = str(selected_ref.get("candidate_id") or "")
                candidate = request_json(
                    client,
                    "GET",
                    f"{base_url}/api/v2/knowledge-candidates/{candidate_id}",
                    params=params,
                )
                generated_candidates = [
                    request_json(
                        client,
                        "GET",
                        f"{base_url}/api/v2/knowledge-candidates/{str(item.get('candidate_id') or '')}",
                        params=params,
                    )
                    for item in candidates
                    if item.get("candidate_id")
                ]
                checks["candidate_keeps_provenance_without_transcript"] = (
                    candidate.get("status") == "provisional"
                    and candidate.get("source_work_run_id") == work_run_id
                    and candidate.get("raw_transcript_stored") is False
                )

                direct_search = request_json(
                    client,
                    "GET",
                    f"{base_url}/api/v2/search",
                    params={
                        **params,
                        "q": (
                            f"{marker} 단면검사 Response Trend Map View Image "
                            "예외 사항 판단 기록"
                        ),
                    },
                )
                checks["candidate_enters_private_search_read_model"] = candidate_id in {
                    str(item.get("evidence_id") or "")
                    for item in direct_search.get("items") or []
                }

                reused = request_json(
                    client,
                    "POST",
                    f"{base_url}/api/v2/agent/turns",
                    params=params,
                    body={
                        "question": (
                            f"{marker} 단면검사에서 Response Trend와 Map View Image를 확인하고 "
                            "예외 사항을 기록한 판단을 찾아줘."
                        )
                    },
                )
                sessions.append(str(reused.get("work_session_id") or ""))
                returned_citations = {
                    str(item.get("citation_id") or ""): str(item.get("source_ref") or "")
                    for item in reused.get("citations") or []
                }
                rendered_citations = set(
                    re.findall(
                        r"/api/v2/citations/(cite_[A-Za-z0-9]+)",
                        str((reused.get("answer") or {}).get("markdown") or ""),
                    )
                )
                checks["new_session_reuses_candidate"] = candidate_id in returned_citations.values()
                checks["rendered_citations_match_contract"] = (
                    bool(rendered_citations)
                    and rendered_citations == set(returned_citations)
                )
                checks["response_stays_compact"] = len(
                    json.dumps(reused, ensure_ascii=False).encode("utf-8")
                ) <= 8192
                details.update(
                    {
                        "work_run_id": work_run_id,
                        "candidate_id": candidate_id,
                        "reuse_session_id": reused.get("work_session_id"),
                        "citation_sources": list(returned_citations.values()),
                        "reuse_answer": (reused.get("answer") or {}).get("summary") or "",
                    }
                )
        finally:
            if not args.keep_candidate:
                for candidate in generated_candidates:
                    if candidate.get("status") == "archived":
                        continue
                    request_json(
                        client,
                        "PATCH",
                        f"{base_url}/api/v2/knowledge-candidates/{candidate['candidate_id']}",
                        params=params,
                        body={"expected_revision": candidate["revision"], "status": "archived"},
                    )
            for session_id in dict.fromkeys(item for item in sessions if item):
                response = client.delete(
                    f"{base_url}/api/v2/work-sessions/{session_id}",
                    params=params,
                )
                if response.status_code not in {200, 404}:
                    response.raise_for_status()

    accepted = bool(checks) and all(checks.values())
    print(json.dumps({"accepted": accepted, "checks": checks, "details": details}, ensure_ascii=False, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
