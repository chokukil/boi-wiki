#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_kit.python.boi_v2_client import BoiV2Client
from boi_wiki_mcp.app import v2 as mcp_v2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify REST, MCP v2, and Agent Kit contract parity.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def source_refs(payload: dict[str, Any]) -> list[str]:
    return [str(item.get("source_ref") or "") for item in payload.get("citations") or [] if item.get("source_ref")]


def evidence_ids(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("evidence_refs") or payload.get("items") or []
    return [str(item.get("evidence_id") or "") for item in rows if item.get("evidence_id")]


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    web_params = {"employee_id": args.employee_id}
    token_id = ""
    token = ""
    sessions: set[str] = set()
    candidate_ids: set[str] = set()
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    with httpx.Client(base_url=base_url, timeout=args.timeout) as web_client:
        created = web_client.post(
            "/api/v2/tokens",
            params=web_params,
            json={"name": "Interface parity smoke", "scopes": ["boi.read", "boi.draft"]},
        )
        created.raise_for_status()
        token_payload = created.json()
        token_id = str(token_payload.get("token_id") or "")
        token = str(token_payload.get("token") or "")
        if not token.startswith("boi_pat_"):
            raise RuntimeError("Web session did not issue a BoI PAT")

        def cleanup_smoke_state() -> None:
            try:
                if token:
                    with httpx.Client(base_url=base_url, timeout=20, headers={"Authorization": f"Bearer {token}"}) as cleanup:
                        for candidate_id in candidate_ids:
                            current = cleanup.get(f"/api/v2/knowledge-candidates/{candidate_id}")
                            if current.status_code != 200 or current.json().get("status") == "archived":
                                continue
                            candidate = current.json()
                            cleanup.patch(
                                f"/api/v2/knowledge-candidates/{candidate_id}",
                                json={"expected_revision": candidate["revision"], "status": "archived"},
                            )
                        for session_id in {item for item in sessions if item}:
                            cleanup.delete(f"/api/v2/work-sessions/{session_id}")
                if token_id:
                    httpx.delete(
                        f"{base_url}/api/v2/tokens/{token_id}",
                        params=web_params,
                        timeout=20,
                    )
            except Exception:
                pass

        atexit.register(cleanup_smoke_state)

        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=base_url, timeout=args.timeout, headers=headers) as rest:
            previous_api_url, previous_pat = mcp_v2.BOI_API_URL, mcp_v2.BOI_API_PAT
            mcp_v2.BOI_API_URL = base_url
            mcp_v2.BOI_API_PAT = token
            try:
                canonical_guide = "boi:public:boi-wiki-manual:guide:final-operator-guide"
                question = "현재 BoI Wiki 종합 가이드의 찾기, 이해하기, 수행하기, 결과 남기기, 재사용하기 흐름을 근거와 함께 알려줘."
                page_ref = f"/docs/{canonical_guide}"
                rest_response = rest.post(
                    "/api/v2/agent/turns",
                    json={"question": question, "page_ref": page_ref},
                )
                rest_response.raise_for_status()
                rest_turn = rest_response.json()
                sessions.add(str(rest_turn.get("work_session_id") or ""))

                mcp_turn = asyncio.run(mcp_v2.boi_agent(question, page_ref=page_ref))
                sessions.add(str(mcp_turn.get("work_session_id") or ""))
                with BoiV2Client(base_url=base_url, token=token, timeout=args.timeout) as kit:
                    kit_turn = kit.agent(question, page_ref=page_ref)
                    sessions.add(str(kit_turn.get("work_session_id") or ""))
                    kit_bootstrap = kit.bootstrap(page_ref)

                rest_sources = source_refs(rest_turn)
                mcp_sources = source_refs(mcp_turn)
                kit_sources = source_refs(kit_turn)
                rest_context = rest.get(f"/api/v2/context/{rest_turn['context_ref']}")
                mcp_context_for_turn = rest.get(f"/api/v2/context/{mcp_turn['context_ref']}")
                kit_context = rest.get(f"/api/v2/context/{kit_turn['context_ref']}")
                for response in (rest_context, mcp_context_for_turn, kit_context):
                    response.raise_for_status()
                rest_context_ids = evidence_ids(rest_context.json())
                mcp_context_ids = evidence_ids(mcp_context_for_turn.json())
                kit_context_ids = evidence_ids(kit_context.json())
                rest_search_response = rest.get("/api/v2/search", params={"q": question, "limit": 8})
                rest_search_response.raise_for_status()
                rest_search_ids = evidence_ids(rest_search_response.json())
                mcp_search_ids = evidence_ids(asyncio.run(mcp_v2.boi_search(question, limit=8)))
                with BoiV2Client(base_url=base_url, token=token, timeout=args.timeout) as kit:
                    kit_search_ids = evidence_ids(kit.search(question, limit=8))
                checks["natural_route_matches"] = (
                    rest_turn.get("capability_id")
                    == mcp_turn.get("capability_id")
                    == kit_turn.get("capability_id")
                    == "knowledge.search"
                    and (rest_turn.get("work_intent") or {}).get("operation")
                    == (mcp_turn.get("work_intent") or {}).get("operation")
                    == (kit_turn.get("work_intent") or {}).get("operation")
                )
                checks["grounded_source_contract_matches"] = (
                    bool(rest_sources and mcp_sources and kit_sources)
                    and set(rest_sources).issubset(set(rest_context_ids))
                    and set(mcp_sources).issubset(set(mcp_context_ids))
                    and set(kit_sources).issubset(set(kit_context_ids))
                )
                checks["canonical_guide_is_cited_cross_interfaces"] = (
                    canonical_guide in rest_sources
                    and canonical_guide in mcp_sources
                    and canonical_guide in kit_sources
                )
                checks["evidence_contract_matches"] = (
                    bool(rest_context_ids)
                    and rest_context_ids == mcp_context_ids == kit_context_ids
                )
                checks["deterministic_search_ids_match"] = (
                    bool(rest_search_ids)
                    and rest_search_ids == mcp_search_ids == kit_search_ids
                )
                checks["agent_kit_bootstraps_same_v2"] = (
                    kit_bootstrap.get("version") == "2.0"
                    and (kit_bootstrap.get("readiness") or {}).get("ready") is True
                )

                mcp_run = asyncio.run(mcp_v2.boi_get(str(rest_turn["run_id"])))
                mcp_context = asyncio.run(mcp_v2.boi_context(str(rest_turn["context_ref"])))
                checks["mcp_reads_exact_rest_run"] = (
                    (mcp_run.get("response") or {}).get("run_id") == rest_turn.get("run_id")
                    and (mcp_run.get("response") or {}).get("work_run_id") == rest_turn.get("work_run_id")
                    and (mcp_run.get("response") or {}).get("goal_plan_ref") == rest_turn.get("goal_plan_ref")
                )
                checks["mcp_reads_exact_context"] = (
                    mcp_context.get("context_id") == rest_turn.get("context_ref")
                    and [item.get("evidence_id") for item in mcp_context.get("evidence_refs") or []]
                    == [item.get("evidence_id") for item in rest.get(f"/api/v2/context/{rest_turn['context_ref']}").json().get("evidence_refs") or []]
                )

                task_started_response = rest.post(
                    "/api/v2/agent/turns",
                    json={
                        "question": "단면검사 Task를 완료 처리하고 판단 결과를 지식으로 남겨줘. 담당자 확인을 기다려줘.",
                        "page_ref": "/docs/boi:public:sop:direct-development-reporting",
                        "task_ref": "cross_section_decision",
                    },
                )
                task_started_response.raise_for_status()
                task_started = task_started_response.json()
                sessions.add(str(task_started.get("work_session_id") or ""))
                continued = asyncio.run(
                    mcp_v2.boi_agent(
                        work_run_id=str(task_started["work_run_id"]),
                        delta_kind="human_input",
                        delta_summary="담당자가 Response Trend와 Map View Image를 확인하고 판단과 예외 사항을 기록했습니다.",
                        delta_ref="boi:public:sop:direct-development-reporting",
                        confirm=True,
                    )
                )
                completed_run = continued.get("work_run") or {}
                candidate_ids.update(
                    str(item.get("candidate_id") or "")
                    for item in continued.get("knowledge_candidates") or []
                    if item.get("candidate_id")
                )
                rest_run = rest.get(f"/api/v2/work-runs/{task_started['work_run_id']}")
                rest_run.raise_for_status()
                with BoiV2Client(base_url=base_url, token=token, timeout=args.timeout) as kit:
                    kit_run = kit.work_run(str(task_started["work_run_id"]))
                checks["mcp_continues_rest_work_run"] = (
                    task_started.get("capability_id") == "task.work"
                    and (task_started.get("loop_state") or {}).get("status") == "waiting_human"
                    and completed_run.get("work_run_id") == task_started.get("work_run_id")
                    and completed_run.get("status") == "completed"
                    and rest_run.json().get("status") == "completed"
                    and kit_run.get("status") == "completed"
                )
                checks["same_learning_ids_cross_interfaces"] = (
                    bool(candidate_ids)
                    and set(rest_run.json().get("knowledge_candidate_ids") or []) == candidate_ids
                    and set(kit_run.get("knowledge_candidate_ids") or []) == candidate_ids
                )
                details = {
                    "capability_id": rest_turn.get("capability_id"),
                    "source_refs": rest_sources,
                    "search_ids": rest_search_ids,
                    "context_evidence_ids": rest_context_ids,
                    "rest_run_id": rest_turn.get("run_id"),
                    "shared_work_run_id": task_started.get("work_run_id"),
                    "candidate_ids": sorted(candidate_ids),
                }
            finally:
                mcp_v2.BOI_API_URL = previous_api_url
                mcp_v2.BOI_API_PAT = previous_pat

            for candidate_id in candidate_ids:
                candidate_response = rest.get(f"/api/v2/knowledge-candidates/{candidate_id}")
                if candidate_response.status_code != 200:
                    continue
                candidate = candidate_response.json()
                if candidate.get("status") == "archived":
                    continue
                archived = rest.patch(
                    f"/api/v2/knowledge-candidates/{candidate_id}",
                    json={"expected_revision": candidate["revision"], "status": "archived"},
                )
                archived.raise_for_status()
            for session_id in {item for item in sessions if item}:
                response = rest.delete(f"/api/v2/work-sessions/{session_id}")
                if response.status_code not in {200, 404}:
                    response.raise_for_status()

        revoked = web_client.delete(f"/api/v2/tokens/{token_id}", params=web_params)
        revoked.raise_for_status()
        candidate_ids.clear()
        sessions.clear()
        token_id = ""
        token = ""

    accepted = bool(checks) and all(checks.values())
    print(json.dumps({"accepted": accepted, "checks": checks, "details": details}, ensure_ascii=False, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
