#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "agent_v2_work_scenarios.yaml"
GENERIC_TERMS = {
    "boi", "wiki", "현재", "관련", "업무", "근거", "함께", "설명", "보여", "만들어", "초안",
    "확인", "기준", "결과", "대한", "있는", "어떻게", "무엇", "해주세요", "해줘", "알려줘",
    "어떤", "하는지", "해야", "부터", "까지", "실제로", "지금",
}

KOREAN_SUFFIXES = (
    "으로부터", "에서부터", "에게서는", "이라는", "에서는", "으로는", "까지는",
    "에게서", "에서", "으로", "처럼", "보다", "부터", "까지", "하고", "하며",
    "해야", "하는", "한테", "에게", "이라", "라고", "이랑", "랑", "와", "과",
    "은", "는", "이", "가", "을", "를", "의", "에", "도", "만",
)


def normalize_content_token(token: str) -> str:
    normalized = token.casefold()
    if re.search(r"[가-힣]", normalized):
        for suffix in KOREAN_SUFFIXES:
            if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
                normalized = normalized[: -len(suffix)]
                break
    return normalized


def content_terms(value: str) -> set[str]:
    return {
        normalize_content_token(token)
        for token in re.findall(r"[A-Za-z0-9가-힣._-]{2,}", str(value or ""))
        if normalize_content_token(token) not in GENERIC_TERMS
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate live BoI Agent v2 semantic work scenarios.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--keep-state", action="store_true")
    return parser.parse_args()


def expected_operation_matches(scenario: dict[str, Any], actual: str) -> bool:
    expected = str(scenario.get("expected_operation") or "")
    if expected:
        return actual == expected
    return actual in {str(item) for item in scenario.get("expected_operations") or []}


def evaluate_response(scenario: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    intent = response.get("work_intent") if isinstance(response.get("work_intent"), dict) else {}
    artifacts = [item for item in response.get("artifact_refs") or [] if isinstance(item, dict)]
    actual_artifact_types = {str(item.get("artifact_type") or "") for item in artifacts}
    loop_state = response.get("loop_state") if isinstance(response.get("loop_state"), dict) else {}
    context_usage = response.get("context_usage") if isinstance(response.get("context_usage"), dict) else {}
    route_ok = response.get("capability_id") == scenario.get("expected_capability")
    operation_ok = expected_operation_matches(scenario, str(intent.get("operation") or ""))
    grounding_ok = not scenario.get("require_grounding") or (
        response.get("grounding_status") == "grounded" and bool(response.get("citations"))
    )
    artifact_type = str(scenario.get("expected_artifact_type") or "")
    artifact_ok = not artifact_type or artifact_type in actual_artifact_types
    plan_ok = not scenario.get("require_plan") or bool(response.get("plan_ref"))
    page_anchor = context_usage.get("page_anchor") if isinstance(context_usage.get("page_anchor"), dict) else {}
    page_anchor_ok = not scenario.get("require_page_anchor") or bool(page_anchor.get("resolved"))
    expected_status = str(scenario.get("expected_status") or "")
    status_ok = not expected_status or response.get("status") == expected_status
    confirmation_ok = not scenario.get("require_confirmation_wait") or (
        bool(response.get("plan_ref"))
        and loop_state.get("status") in {"waiting_human", "waiting_review"}
        and loop_state.get("decision") == "needs_human"
    )
    safety_ok = all(item.get("status") in {"draft", "provisional"} for item in artifacts)
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    answer_text = str(answer.get("markdown") or answer.get("summary") or "").strip()
    citations = [item for item in response.get("citations") or [] if isinstance(item, dict)]
    evidence = [item for item in response.get("evidence_refs") or [] if isinstance(item, dict)]
    evidence_ids = {str(item.get("evidence_id") or "") for item in evidence}
    citation_sources = {str(item.get("source_ref") or "") for item in citations}
    citation_integrity_ok = not scenario.get("require_grounding") or (
        bool(citations)
        and citation_sources <= evidence_ids
        and all(str(item.get("citation_id") or "") in answer_text for item in citations)
    )
    question_terms = content_terms(str(scenario.get("question") or ""))
    resolved_terms = content_terms(str(intent.get("resolved_goal") or ""))
    intent_overlap = len(question_terms & resolved_terms) / max(1, len(question_terms))
    intent_preservation_ok = bool(intent.get("resolved_goal")) and intent_overlap >= 0.25
    source_terms = content_terms(
        " ".join(
            f"{item.get('title') or ''} {item.get('summary') or ''}"
            for item in evidence[:4]
        )
    )
    source_relevance_ok = not scenario.get("require_grounding") or bool(question_terms & source_terms)
    context_use_ok = (
        (not scenario.get("require_grounding") or int(context_usage.get("selected_source_count") or 0) > 0)
        and page_anchor_ok
    )
    read_only_expected = (
        str(scenario.get("expected_capability") or "") in {"knowledge.search", "cases.similar", "work.inbox"}
        and not scenario.get("expected_artifact_type")
        and not scenario.get("require_plan")
    )
    no_unrequested_transition_ok = not read_only_expected or (not artifacts and not response.get("plan_ref"))
    related_questions = [item for item in response.get("related_questions") or [] if isinstance(item, dict)]
    related_grounding_ok = len(related_questions) <= 3 and all(
        set(str(ref) for ref in item.get("source_refs") or []) <= citation_sources
        and str(item.get("question") or "").strip() != str(scenario.get("question") or "").strip()
        for item in related_questions
    )
    answer_substantive_ok = len(answer_text) >= 30
    checks = {
        "route": route_ok,
        "operation": operation_ok,
        "grounding": grounding_ok,
        "artifact": artifact_ok,
        "plan": plan_ok,
        "page_anchor": page_anchor_ok,
        "status": status_ok,
        "confirmation": confirmation_ok,
        "safety": safety_ok,
        "answer_substantive": answer_substantive_ok,
        "citation_integrity": citation_integrity_ok,
        "intent_preservation": intent_preservation_ok,
        "context_use": context_use_ok,
        "source_relevance": source_relevance_ok,
        "no_unrequested_transition": no_unrequested_transition_ok,
        "related_question_grounding": related_grounding_ok,
    }
    return {
        "id": scenario.get("id"),
        "passed": all(checks.values()),
        "checks": checks,
        "actual": {
            "capability_id": response.get("capability_id"),
            "operation": intent.get("operation"),
            "operation_plan": intent.get("operation_plan"),
            "status": response.get("status"),
            "loop_status": loop_state.get("status"),
            "grounding_status": response.get("grounding_status"),
            "artifact_types": sorted(actual_artifact_types),
            "plan_ref": response.get("plan_ref"),
            "intent_overlap": round(intent_overlap, 3),
            "citation_sources": sorted(citation_sources),
            "evidence_ids": sorted(evidence_ids),
        },
    }


def main() -> int:
    args = parse_args()
    fixture = yaml.safe_load(args.fixture.read_text(encoding="utf-8")) or {}
    scenarios = [item for item in fixture.get("scenarios") or [] if isinstance(item, dict)]
    if not scenarios:
        raise SystemExit("scenario fixture is empty")
    base_url = args.base_url.rstrip("/")
    params = {"employee_id": args.employee_id}
    results: list[dict[str, Any]] = []
    session_ids: list[str] = []
    deep_jobs: dict[str, int] = {}
    with httpx.Client(timeout=args.timeout) as client:
        try:
            readiness_response = client.get(f"{base_url}/api/v2/system/readiness", params=params)
            readiness_response.raise_for_status()
            readiness = readiness_response.json()
            model_state = readiness.get("model") if isinstance(readiness.get("model"), dict) else {}
            if not model_state.get("generation"):
                raise SystemExit("Agent v2 structured intent model is not ready")
            for scenario in scenarios:
                payload = {
                    "question": scenario["question"],
                    "page_ref": scenario.get("page_ref") or "",
                    "input_delta": scenario.get("input_delta") or {},
                }
                response = client.post(f"{base_url}/api/v2/agent/turns", params=params, json=payload)
                if response.status_code >= 400:
                    results.append(
                        {
                            "id": scenario.get("id"),
                            "passed": False,
                            "checks": {"http": False},
                            "actual": {"status_code": response.status_code, "body": response.text[:1000]},
                        }
                    )
                    continue
                response_payload = response.json()
                session_id = str(response_payload.get("work_session_id") or "")
                if session_id:
                    session_ids.append(session_id)
                context_ref = str(response_payload.get("context_ref") or "")
                if context_ref:
                    context_response = client.get(
                        f"{base_url}/api/v2/context/{context_ref}",
                        params=params,
                    )
                    if context_response.status_code == 200:
                        response_payload["evidence_refs"] = context_response.json().get("evidence_refs") or []
                results.append(evaluate_response(scenario, response_payload))
                job_ref = str(response_payload.get("job_ref") or "")
                if job_ref:
                    deep_jobs[job_ref] = len(results) - 1
            for job_id, result_index in deep_jobs.items():
                deadline = time.monotonic() + args.timeout
                job: dict[str, Any] = {}
                while time.monotonic() < deadline:
                    job_response = client.get(
                        f"{base_url}/api/v2/deep-jobs/{job_id}",
                        params=params,
                    )
                    job_response.raise_for_status()
                    job = job_response.json()
                    if job.get("status") in {"completed", "failed", "cancelled"}:
                        break
                    time.sleep(1)
                deep_ok = bool(
                    job.get("status") == "completed"
                    and job.get("artifact_id")
                    and job.get("usage_ref")
                )
                results[result_index]["checks"]["deep_job_completed"] = deep_ok
                results[result_index]["actual"].update(
                    {
                        "deep_job_id": job_id,
                        "deep_job_status": job.get("status") or "timeout",
                        "deep_artifact_id": job.get("artifact_id") or "",
                        "deep_usage_ref": job.get("usage_ref") or "",
                        "deep_usage_total": (job.get("usage") or {}).get("total_tokens") or 0,
                        "deep_job_error": job.get("error") or "",
                    }
                )
                results[result_index]["passed"] = bool(results[result_index]["passed"] and deep_ok)
        finally:
            if not args.keep_state:
                for session_id in dict.fromkeys(session_ids):
                    response = client.delete(
                        f"{base_url}/api/v2/work-sessions/{session_id}",
                        params=params,
                    )
                    if response.status_code not in {200, 404}:
                        response.raise_for_status()

    route_rows = [item for item in results if "route" in item.get("checks", {})]
    operation_rows = [item for item in results if "operation" in item.get("checks", {})]
    safety_rows = [item for item in results if "safety" in item.get("checks", {})]
    content_rows = [item for item in results if "intent_preservation" in item.get("checks", {})]
    context_rows = [item for item in results if "context_use" in item.get("checks", {})]
    relevance_rows = [item for item in results if "source_relevance" in item.get("checks", {})]
    transition_rows = [item for item in results if "no_unrequested_transition" in item.get("checks", {})]
    metrics = {
        "routing_accuracy": sum(item["checks"]["route"] for item in route_rows) / max(1, len(route_rows)),
        "operation_accuracy": sum(item["checks"]["operation"] for item in operation_rows) / max(1, len(operation_rows)),
        "safety_accuracy": sum(item["checks"]["safety"] for item in safety_rows) / max(1, len(safety_rows)),
        "intent_preservation": sum(item["checks"]["intent_preservation"] for item in content_rows) / max(1, len(content_rows)),
        "context_utilization": sum(item["checks"]["context_use"] for item in context_rows) / max(1, len(context_rows)),
        "source_relevance": sum(item["checks"]["source_relevance"] for item in relevance_rows) / max(1, len(relevance_rows)),
        "transition_precision": sum(item["checks"]["no_unrequested_transition"] for item in transition_rows) / max(1, len(transition_rows)),
        "scenario_pass_rate": sum(item["passed"] for item in results) / len(results),
    }
    thresholds = fixture.get("thresholds") or {}
    accepted = all(metrics.get(name, 0.0) >= float(value) for name, value in thresholds.items())
    report = {
        "accepted": accepted,
        "fixture_version": fixture.get("version"),
        "base_url": base_url,
        "metrics": metrics,
        "thresholds": thresholds,
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
