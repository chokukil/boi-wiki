#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "agent_v2_work_scenarios.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate live BoI Agent v2 semantic work scenarios.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=0,
        help="Repeat every scenario this many times; 0 uses the fixture value.",
    )
    parser.add_argument("--keep-state", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume completed scenario ids from a compatible running checkpoint.",
    )
    parser.add_argument(
        "--implementation-revision",
        default="",
        help="Server implementation revision. Defaults to the current Git HEAD.",
    )
    parser.add_argument("--scenario-id", action="append", default=[], help="Run only the selected scenario id; repeatable.")
    parser.add_argument("--judge-failures", action="store_true", help="Mark failed or ambiguous cases for explicit GPT-5.5 test adjudication.")
    return parser.parse_args()


def expected_operation_matches(scenario: dict[str, Any], actual: str) -> bool:
    expected = str(scenario.get("expected_operation") or "")
    if expected:
        return actual == expected
    return actual in {str(item) for item in scenario.get("expected_operations") or []}


def expand_scenarios(fixture: dict[str, Any], *, repetitions: int) -> list[dict[str, Any]]:
    defaults = fixture.get("defaults") if isinstance(fixture.get("defaults"), dict) else {}
    rows = [copy.deepcopy(item) for item in fixture.get("scenarios") or [] if isinstance(item, dict)]
    for group in fixture.get("intent_groups") or []:
        if not isinstance(group, dict):
            continue
        expressions = [str(item).strip() for item in group.get("expressions") or [] if str(item).strip()]
        common = {
            key: copy.deepcopy(value)
            for key, value in group.items()
            if key not in {"id", "expressions"}
        }
        for index, expression in enumerate(expressions, start=1):
            rows.append(
                {
                    **common,
                    "id": f"{group.get('id') or 'intent'}_{index:02d}",
                    "question": expression,
                }
            )
    repeated: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for row in rows:
            scenario = {**copy.deepcopy(defaults), **copy.deepcopy(row)}
            scenario["base_id"] = str(scenario.get("id") or "")
            scenario["repetition"] = repetition
            if repetitions > 1:
                scenario["id"] = f"{scenario['base_id']}__r{repetition}"
            repeated.append(scenario)
    return repeated


def load_resume_checkpoint(
    path: Path,
    *,
    fixture_version: Any,
    base_url: str,
    scenario_ids: list[str],
    implementation_revision: str,
    runner_revision: str,
    fixture_checksum: str,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    previous = json.loads(path.read_text(encoding="utf-8"))
    previous_results = [item for item in previous.get("results") or [] if isinstance(item, dict)]
    previous_ids = [str(item.get("id") or "") for item in previous_results]
    compatible = (
        previous.get("fixture_version") == fixture_version
        and str(previous.get("base_url") or "").rstrip("/") == base_url.rstrip("/")
        and str(previous.get("implementation_revision") or "") == implementation_revision
        and str(previous.get("runner_revision") or "") == runner_revision
        and str(previous.get("fixture_checksum") or "") == fixture_checksum
        and int(previous.get("total") or 0) == len(scenario_ids)
        and previous_ids == scenario_ids[: len(previous_ids)]
    )
    if not compatible:
        raise ValueError("existing checkpoint is not compatible with this evaluation run")
    return previous_results


def current_git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def evaluate_response(scenario: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    intent = response.get("work_intent") if isinstance(response.get("work_intent"), dict) else {}
    artifacts = [item for item in response.get("artifact_refs") or [] if isinstance(item, dict)]
    actual_artifact_types = {str(item.get("artifact_type") or "") for item in artifacts}
    loop_state = response.get("loop_state") if isinstance(response.get("loop_state"), dict) else {}
    context_usage = response.get("context_usage") if isinstance(response.get("context_usage"), dict) else {}
    route_ok = response.get("capability_id") == scenario.get("expected_capability")
    operation_ok = expected_operation_matches(scenario, str(intent.get("operation") or ""))
    grounding_ok = not scenario.get("require_grounding") or (
        response.get("grounding_status") in {"grounded", "partial"} and bool(response.get("citations"))
    )
    artifact_type = str(scenario.get("expected_artifact_type") or "")
    artifact_ok = not artifact_type or artifact_type in actual_artifact_types
    expected_presentation = str(scenario.get("expected_presentation") or "")
    presentation_by_artifact_type = {
        "mermaid_diagram": "mermaid",
    }
    actual_presentations = {
        str(
            (item.get("metadata") or {}).get("presentation")
            or (item.get("payload") or {}).get("presentation")
            or item.get("presentation")
            or presentation_by_artifact_type.get(str(item.get("artifact_type") or ""), "")
        )
        for item in artifacts
    }
    presentation_ok = not expected_presentation or expected_presentation in {
        *actual_presentations,
        str(intent.get("presentation_mode") or ""),
    }
    expected_effect = str(scenario.get("expected_user_effect") or "")
    user_effect_ok = not expected_effect or intent.get("user_effect") == expected_effect
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
    answerability = response.get("answerability") if isinstance(response.get("answerability"), dict) else {}
    expected_answerability = str(scenario.get("expected_answerability") or "")
    answerability_ok = not expected_answerability or answerability.get("status") == expected_answerability
    grounded_claims = [item for item in response.get("grounded_claims") or [] if isinstance(item, dict)]
    claim_support_ok = not scenario.get("require_grounded_claims") or (
        bool(grounded_claims)
        and all(item.get("support_status") == "supported" for item in grounded_claims)
        and all(item.get("source_refs") and item.get("supporting_chunk_ids") for item in grounded_claims)
    )
    citations = [item for item in response.get("citations") or [] if isinstance(item, dict)]
    evidence = [item for item in response.get("evidence_refs") or [] if isinstance(item, dict)]
    evidence_ids = {str(item.get("evidence_id") or "") for item in evidence}
    citation_sources = {str(item.get("source_ref") or "") for item in citations}
    used_source_refs = {str(item) for item in response.get("used_source_refs") or [] if str(item).strip()}
    required_used_source_refs = {
        str(item) for item in scenario.get("require_used_source_refs") or [] if str(item).strip()
    }
    required_used_sources_ok = required_used_source_refs <= used_source_refs
    internal_sources_only_ok = not scenario.get("require_internal_sources_only") or all(
        not ref.startswith(("http://", "https://", "official_web:"))
        for ref in citation_sources | evidence_ids | used_source_refs
    )
    citation_integrity_ok = not scenario.get("require_grounding") or (
        bool(citations)
        and citation_sources <= evidence_ids
        and all(str(item.get("citation_id") or "") in answer_text for item in citations)
    )
    intent_preservation_ok = bool(intent.get("resolved_goal")) and route_ok and operation_ok and user_effect_ok
    source_relevance_ok = not scenario.get("require_grounding") or (
        bool(grounded_claims)
        and all(item.get("source_refs") and item.get("supporting_chunk_ids") for item in grounded_claims)
    )
    context_use_ok = (
        (not scenario.get("require_grounding") or int(context_usage.get("selected_source_count") or 0) > 0)
        and page_anchor_ok
    )
    read_only_expected = bool(scenario.get("forbid_unrequested_transition")) or (
        expected_effect == "read"
        and not scenario.get("expected_artifact_type")
        and not scenario.get("require_plan")
    )
    presentation_artifacts = {"ontology_graph", "knowledge_graph", "mermaid_diagram"}
    no_unrequested_transition_ok = not read_only_expected or (
        not response.get("plan_ref")
        and actual_artifact_types <= presentation_artifacts
    )
    related_questions = [item for item in response.get("related_questions") or [] if isinstance(item, dict)]
    related_grounding_ok = len(related_questions) <= 3 and all(
        set(str(ref) for ref in item.get("source_refs") or []) <= (citation_sources | evidence_ids)
        and str(item.get("question") or "").strip() != str(scenario.get("question") or "").strip()
        for item in related_questions
    )
    answer_substantive_ok = (
        (
            response.get("status") == "needs_input"
            and bool(answer_text)
        )
        or len(answer_text) >= 30
        or expected_answerability in {"insufficient", "conflicting"}
        and "확인된 근거가 없습니다" in answer_text
    )
    forbidden_answer_terms_ok = not any(
        str(term) in answer_text for term in scenario.get("forbid_answer_terms") or []
    )
    required_answer_terms_ok = all(
        str(term) in answer_text for term in scenario.get("require_answer_terms") or []
    )
    expected_topic_mode = str(scenario.get("expected_topic_mode") or "")
    topic_mode_ok = not expected_topic_mode or intent.get("topic_mode") == expected_topic_mode
    expected_semantic_change = str(scenario.get("expected_followup_semantic_change") or "")
    semantic_change_ok = (
        not expected_semantic_change
        or intent.get("followup_semantic_change") == expected_semantic_change
    )
    topic_subject_contains = str(scenario.get("topic_subject_contains") or "")
    topic_subject_ok = not topic_subject_contains or topic_subject_contains in str(intent.get("topic_subject") or "")
    semantic_plan_ok = not scenario.get("require_semantic_plan") or bool(response.get("semantic_plan_ref"))
    checks = {
        "route": route_ok,
        "operation": operation_ok,
        "user_effect": user_effect_ok,
        "grounding": grounding_ok,
        "artifact": artifact_ok and presentation_ok,
        "plan": plan_ok,
        "page_anchor": page_anchor_ok,
        "status": status_ok,
        "confirmation": confirmation_ok,
        "safety": safety_ok,
        "answer_substantive": answer_substantive_ok,
        "answerability": answerability_ok,
        "claim_support": claim_support_ok,
        "internal_sources_only": internal_sources_only_ok,
        "required_used_sources": required_used_sources_ok,
        "forbidden_answer_terms": forbidden_answer_terms_ok,
        "required_answer_terms": required_answer_terms_ok,
        "topic_mode": topic_mode_ok,
        "followup_semantic_change": semantic_change_ok,
        "topic_subject": topic_subject_ok,
        "semantic_plan": semantic_plan_ok,
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
            "answer_intent": intent.get("answer_intent"),
            "desired_outcome": intent.get("desired_outcome"),
            "result_purpose": intent.get("result_purpose"),
            "requested_transition": intent.get("requested_transition"),
            "analysis_depth": intent.get("analysis_depth"),
            "topic_structure": intent.get("topic_structure"),
            "referenceable_topic_entities": intent.get("referenceable_topic_entities"),
            "followup_reference_resolution": intent.get("followup_reference_resolution"),
            "status": response.get("status"),
            "loop_status": loop_state.get("status"),
            "grounding_status": response.get("grounding_status"),
            "answerability": answerability.get("status"),
            "grounded_claim_count": len(grounded_claims),
            "topic_mode": intent.get("topic_mode"),
            "followup_semantic_change": intent.get("followup_semantic_change"),
            "topic_subject": intent.get("topic_subject"),
            "artifact_types": sorted(actual_artifact_types),
            "artifact_presentations": sorted(item for item in actual_presentations if item),
            "plan_ref": response.get("plan_ref"),
            "user_effect": intent.get("user_effect"),
            "semantic_plan_ref": response.get("semantic_plan_ref"),
            "error_code": response.get("error_code"),
            "stop_reason": response.get("stop_reason"),
            "citation_sources": sorted(citation_sources),
            "evidence_ids": sorted(evidence_ids),
            "used_source_refs": sorted(used_source_refs),
            "answer_text": answer_text,
            "grounded_claims": [
                {
                    key: item.get(key)
                    for key in (
                        "claim_id",
                        "text",
                        "claim_kind",
                        "source_scope",
                        "source_refs",
                        "supporting_chunk_ids",
                        "support_status",
                        "confidence",
                        "required_for_answer",
                    )
                }
                for item in grounded_claims
            ],
        },
    }


def main() -> int:
    args = parse_args()
    fixture_bytes = args.fixture.read_bytes()
    fixture = yaml.safe_load(fixture_bytes.decode("utf-8")) or {}
    implementation_revision = args.implementation_revision.strip() or current_git_revision()
    runner_revision = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fixture_checksum = hashlib.sha256(fixture_bytes).hexdigest()
    repetitions = args.repetitions or int(fixture.get("repetitions") or 1)
    if repetitions < 1:
        raise SystemExit("repetitions must be at least 1")
    scenarios = expand_scenarios(fixture, repetitions=repetitions)
    if args.scenario_id:
        selected = set(args.scenario_id)
        scenarios = [item for item in scenarios if str(item.get("id") or "") in selected]
    if not scenarios:
        raise SystemExit("scenario fixture is empty")
    base_url = args.base_url.rstrip("/")
    params = {"employee_id": args.employee_id}
    results: list[dict[str, Any]] = []
    if args.resume and args.output and args.output.exists():
        expected_ids = [str(item.get("id") or "") for item in scenarios]
        try:
            results.extend(
                load_resume_checkpoint(
                    args.output,
                    fixture_version=fixture.get("version"),
                    base_url=base_url,
                    scenario_ids=expected_ids,
                    implementation_revision=implementation_revision,
                    runner_revision=runner_revision,
                    fixture_checksum=fixture_checksum,
                )
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    session_ids: list[str] = []
    deep_jobs: dict[str, int] = {}

    def checkpoint(scenario_id: str) -> None:
        passed = sum(bool(item.get("passed")) for item in results)
        failed = len(results) - passed
        if args.output:
            payload = {
                "status": "running",
                "accepted": False,
                "fixture_version": fixture.get("version"),
                "base_url": base_url,
                "implementation_revision": implementation_revision,
                "runner_revision": runner_revision,
                "fixture_checksum": fixture_checksum,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "completed": len(results),
                "passed": passed,
                "failed": failed,
                "remaining": max(0, len(scenarios) - len(results)),
                "total": len(scenarios),
                "results": results,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(args.output)
        latest = results[-1] if results else {}
        state = "passed" if latest.get("passed") else "failed"
        print(
            f"[semantic-holdout] {len(results)}/{len(scenarios)} "
            f"passed={passed} failed={failed} remaining={max(0, len(scenarios) - len(results))} "
            f"{scenario_id} {state}",
            file=sys.stderr,
            flush=True,
        )

    with httpx.Client(timeout=args.timeout) as client:
        try:
            readiness_response = client.get(f"{base_url}/api/v2/system/readiness", params=params)
            readiness_response.raise_for_status()
            readiness = readiness_response.json()
            model_state = readiness.get("model") if isinstance(readiness.get("model"), dict) else {}
            if not model_state.get("generation"):
                raise SystemExit("Agent v2 structured intent model is not ready")
            completed_ids = {str(item.get("id") or "") for item in results}
            for scenario in scenarios:
                if str(scenario.get("id") or "") in completed_ids:
                    continue
                turns = [str(item) for item in scenario.get("turns") or [] if str(item).strip()]
                if not turns:
                    turns = [str(scenario["question"])]
                response = None
                active_session = ""
                turn_latencies: list[int] = []
                turn_results: list[dict[str, Any]] = []
                request_error = ""
                for turn_index, question in enumerate(turns):
                    payload = {
                        "question": question,
                        "page_ref": scenario.get("page_ref") or "",
                        "input_delta": scenario.get("input_delta") or {},
                    }
                    if active_session:
                        payload["work_session_id"] = active_session
                    started = time.monotonic()
                    try:
                        response = client.post(f"{base_url}/api/v2/agent/turns", params=params, json=payload)
                    except Exception as exc:
                        request_error = f"{type(exc).__name__}: {exc}"
                        response = None
                    turn_latencies.append(round((time.monotonic() - started) * 1000))
                    if response is None:
                        break
                    if response.status_code >= 400:
                        break
                    turn_payload = response.json()
                    active_session = str(turn_payload.get("work_session_id") or active_session)
                    if active_session:
                        session_ids.append(active_session)
                    run_diagnostics: dict[str, Any] = {}
                    turn_run_id = str(turn_payload.get("run_id") or "")
                    if turn_run_id and turn_payload.get("error_code"):
                        run_response = client.get(
                            f"{base_url}/api/v2/agent/runs/{turn_run_id}",
                            params=params,
                        )
                        if run_response.status_code == 200:
                            run_diagnostics = run_response.json()
                    session_topic: dict[str, Any] = {}
                    restored_session: dict[str, Any] = {}
                    if active_session:
                        restored = client.get(
                            f"{base_url}/api/v2/work-sessions/{active_session}",
                            params=params,
                        )
                        restored.raise_for_status()
                        restored_payload = restored.json()
                        restored_session = (
                            restored_payload.get("session")
                            if isinstance(restored_payload.get("session"), dict)
                            else restored_payload
                        )
                        session_topic = (
                            restored_session.get("topic_state")
                            if isinstance(restored_session.get("topic_state"), dict)
                            else {}
                        )
                    turn_intent = (
                        turn_payload.get("work_intent")
                        if isinstance(turn_payload.get("work_intent"), dict)
                        else {}
                    )
                    turn_results.append(
                        {
                            "turn": turn_index + 1,
                            "question": question,
                            "latency_ms": turn_latencies[-1],
                            "status": turn_payload.get("status"),
                            "run_id": turn_run_id,
                            "capability_id": turn_payload.get("capability_id"),
                            "error_code": turn_payload.get("error_code"),
                            "plan_validation": run_diagnostics.get("plan_validation") or {},
                            "error_disposition": run_diagnostics.get("error_disposition") or "",
                            "semantic_plan_ref": turn_payload.get("semantic_plan_ref"),
                            "operation": turn_intent.get("operation"),
                            "topic_mode": turn_intent.get("topic_mode"),
                            "topic_subject": turn_intent.get("topic_subject"),
                            "referenceable_topic_entities": turn_intent.get("referenceable_topic_entities") or [],
                            "answerability": (turn_payload.get("answerability") or {}).get("status"),
                            "used_source_refs": turn_payload.get("used_source_refs") or [],
                            "grounded_claim_count": len(turn_payload.get("grounded_claims") or []),
                            "session_topic_state": session_topic,
                        }
                    )
                    if (
                        scenario.get("reload_session_between_turns")
                        and turn_index < len(turns) - 1
                        and active_session
                    ):
                        if str(restored_session.get("session_id") or "") != active_session:
                            raise RuntimeError("restored WorkSession does not match the active session")
                        restored_topic = restored_session.get("topic_state")
                        if not isinstance(restored_topic, dict) or not restored_topic.get("topic_state_ref"):
                            raise RuntimeError("restored WorkSession is missing its verified topic state")
                        if not any(
                            isinstance(item, dict) and item.get("support_status") == "supported"
                            for item in restored_topic.get("claims") or []
                        ):
                            raise RuntimeError("restored WorkSession is missing its verified grounded claims")
                if response is None:
                    results.append(
                        {
                            "id": scenario.get("id"),
                            "passed": False,
                            "checks": {"http": False},
                            "actual": {
                                "status_code": 0,
                                "error": request_error or "request did not return a response",
                                "turn_count": len(turns),
                                "turn_latencies_ms": turn_latencies,
                                "turns": turn_results,
                            },
                        }
                    )
                    checkpoint(str(scenario.get("id") or ""))
                    continue
                if response.status_code >= 400:
                    results.append(
                        {
                            "id": scenario.get("id"),
                            "passed": False,
                            "checks": {"http": False},
                            "actual": {"status_code": response.status_code, "body": response.text[:1000]},
                        }
                    )
                    checkpoint(str(scenario.get("id") or ""))
                    continue
                response_payload = response.json()
                response_payload["_scenario_question"] = turns[-1]
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
                evaluation_scenario = {**scenario, "question": " ".join(turns)}
                evaluated = evaluate_response(evaluation_scenario, response_payload)
                evaluated["actual"]["turn_count"] = len(turns)
                evaluated["actual"]["turn_latencies_ms"] = turn_latencies
                evaluated["actual"]["turns"] = turn_results
                results.append(evaluated)
                checkpoint(str(scenario.get("id") or ""))
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
            if args.judge_failures:
                import os
                if os.getenv("BOI_GPT55_TEST_MODE", "").strip().lower() not in {"1", "true", "yes"}:
                    raise SystemExit("--judge-failures requires BOI_GPT55_TEST_MODE=1")
                for result in results:
                    if not result.get("passed"):
                        result["gpt55_adjudication"] = {
                            "status": "candidate",
                            "reason": "실패·모호 사례만 별도 독립 평가 대상으로 내보냅니다.",
                        }
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
    effect_rows = [item for item in results if "user_effect" in item.get("checks", {})]
    safety_rows = [item for item in results if "safety" in item.get("checks", {})]
    content_rows = [item for item in results if "intent_preservation" in item.get("checks", {})]
    context_rows = [item for item in results if "context_use" in item.get("checks", {})]
    relevance_rows = [item for item in results if "source_relevance" in item.get("checks", {})]
    transition_rows = [item for item in results if "no_unrequested_transition" in item.get("checks", {})]
    answerability_rows = [
        item for item in results if item.get("id") and any(
            str(scenario.get("id") or "") == str(item.get("id") or "")
            and scenario.get("expected_answerability")
            for scenario in scenarios
        )
    ]
    claim_rows = [
        item for item in results if item.get("id") and any(
            str(scenario.get("id") or "") == str(item.get("id") or "")
            and scenario.get("require_grounded_claims")
            for scenario in scenarios
        )
    ]
    internal_source_rows = [
        item for item in results if item.get("id") and any(
            str(scenario.get("id") or "") == str(item.get("id") or "")
            and scenario.get("require_internal_sources_only")
            for scenario in scenarios
        )
    ]
    topic_rows = [
        item for item in results if item.get("id") and any(
            str(scenario.get("id") or "") == str(item.get("id") or "")
            and (scenario.get("expected_topic_mode") or scenario.get("topic_subject_contains"))
            for scenario in scenarios
        )
    ]

    def check_rate(rows: list[dict[str, Any]], check: str) -> float:
        # A targeted scenario run should not fail a metric that has no
        # applicable cases. The fixture still controls which rows contribute
        # to each acceptance dimension.
        if not rows:
            return 1.0
        return sum(bool(item["checks"].get(check)) for item in rows) / len(rows)

    metrics = {
        "routing_accuracy": check_rate(route_rows, "route"),
        "operation_accuracy": check_rate(operation_rows, "operation"),
        "user_effect_accuracy": check_rate(effect_rows, "user_effect"),
        "safety_accuracy": check_rate(safety_rows, "safety"),
        "intent_preservation": check_rate(content_rows, "intent_preservation"),
        "context_utilization": check_rate(context_rows, "context_use"),
        "source_relevance": check_rate(relevance_rows, "source_relevance"),
        "transition_precision": check_rate(transition_rows, "no_unrequested_transition"),
        "answerability_accuracy": check_rate(answerability_rows, "answerability"),
        "claim_support_integrity": check_rate(claim_rows, "claim_support"),
        "internal_source_integrity": check_rate(internal_source_rows, "internal_sources_only"),
        "topic_state_accuracy": (
            1.0
            if not topic_rows
            else sum(
                item["checks"]["topic_mode"] and item["checks"]["topic_subject"]
                for item in topic_rows
            ) / len(topic_rows)
        ),
        "scenario_pass_rate": sum(item["passed"] for item in results) / len(results),
    }
    thresholds = fixture.get("thresholds") or {}
    accepted = all(metrics.get(name, 0.0) >= float(value) for name, value in thresholds.items())
    report = {
        "status": "completed",
        "accepted": accepted,
        "fixture_version": fixture.get("version"),
        "base_url": base_url,
        "implementation_revision": implementation_revision,
        "runner_revision": runner_revision,
        "fixture_checksum": fixture_checksum,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "completed": len(results),
        "passed": sum(bool(item.get("passed")) for item in results),
        "failed": sum(not bool(item.get("passed")) for item in results),
        "remaining": max(0, len(scenarios) - len(results)),
        "total": len(scenarios),
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
