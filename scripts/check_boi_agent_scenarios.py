#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


AGENT_CONTRACT_VERSION = "boi-agent.response.v1"
DEFAULT_CURRENT_URL = "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"
DEFAULT_SCENARIO_FILE = Path("tests/fixtures/boi_agent_scenarios.json")
MUTATION_FOLLOWUP_TERMS = (
    "실행",
    "호출",
    "발행",
    "게시",
    "배포",
    "반영",
    "적용",
    "완료",
    "초안",
    "draft",
    "invoke",
    "publish",
)
IMMEDIATE_MUTATION_TERMS = ("바로 실행", "즉시 실행", "바로 발행", "즉시 발행", "바로 반영", "즉시 반영")
MUTATION_AFFORDANCE_TYPES = {"create_draft", "request_execution", "complete_handoff", "approval"}


class ScenarioValidationError(RuntimeError):
    pass


def built_in_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "sop-workflow-summary",
            "name": "SOP Event/Action/Manual Handoff relationship",
            "question": "이 SOP의 Event, Action, Manual Handoff 관계를 표로 요약해줘.",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "deep",
                "intent": "workflow_explain",
                "artifact_types": ["workflow_summary"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
            },
        },
        {
            "id": "sop-mermaid",
            "name": "SOP Mermaid diagram",
            "question": "이 SOP를 Mermaid 프로세스 플로우로 보여줘.",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "deep",
                "intent": "diagram",
                "artifact_types": ["mermaid"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
            },
        },
        {
            "id": "sop-gap-check",
            "name": "Action Spec gap check",
            "question": "이 SOP를 실행하려면 부족한 Action Spec이 있는지 찾아줘.",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "deep",
                "intent": "gap_check",
                "artifact_types": ["gap_table"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
            },
        },
        {
            "id": "trend-required-data",
            "name": "Action requirement from current SOP",
            "question": "설비 이상 감지 시 Trend 확인을 위해 어떤 데이터가 필요한지 알려줘",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "fast",
                "intent": "page_qa",
                "artifact_types": ["action_requirements"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
                "require_answer_terms": ["equipment_id", "response_series"],
            },
        },
        {
            "id": "workflow-status-manual-summary",
            "name": "Workflow Status remaining manual work",
            "question": "남은 수동 조치 5건을 일반 업무 관점으로 정리해줘.",
            "current_url": "/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-90fec4f5af564e7a8590053ea7c926ae",
            "expect": {
                "route": "fast",
                "intent": "workflow_explain",
                "response_profile": "workflow_manual_summary",
                "goal_type": "workflow_manual_summary",
                "artifact_types": ["manual_handoff_summary"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
                "require_answer_terms": ["수동 조치", "5건"],
                "forbid_answer_terms": ["수동 조치 사항이 없습니다"],
            },
        },
        {
            "id": "event-to-action",
            "name": "Event to WorkflowDefinition/SOP/Action flow",
            "question": "equipment.alarm.raised.v1 이벤트가 발생하면 뭘 해야 해?",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "deep",
                "intent": "workflow_explain",
                "artifact_types": ["workflow_summary"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "require_links_or_citations": True,
                "event_type": "equipment.alarm.raised.v1",
                "workflow_definition_key": "equipment-anomaly-response",
            },
        },
        {
            "id": "action-invoke-confirmation",
            "name": "Action invoke confirmation only",
            "question": "api.equipment.request_trend_history Action 실행해줘.",
            "current_url": DEFAULT_CURRENT_URL,
            "expect": {
                "route": "approval_required",
                "intent": "action_invoke",
                "artifact_types": ["confirmation_required"],
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "mutation_confirmation_only": True,
            },
        },
        {
            "id": "unknown-workflow-definition",
            "name": "Unknown workflow definition should not hallucinate execution",
            "question": "EUV 노광 Overlay drift 보정 이벤트가 발생하면 자동으로 처리해줘.",
            "current_url": "/",
            "expect": {
                "min_followups": 1,
                "require_evidence": True,
                "require_affordances": True,
                "forbid_answer_terms": ["처리했습니다", "실행했습니다", "발행했습니다"],
            },
        },
    ]


def load_scenarios(path: str | Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = DEFAULT_SCENARIO_FILE if DEFAULT_SCENARIO_FILE.exists() else None
    if not path:
        return built_in_scenarios()
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScenarioValidationError(
            f"{target} must be JSON or YAML 1.2 JSON-superset content; failed to parse JSON: {exc}"
        ) from exc
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else payload
    if not isinstance(scenarios, list):
        raise ScenarioValidationError(f"{target} must contain a scenario list or {{'scenarios': [...]}}")
    return [scenario for scenario in scenarios if isinstance(scenario, dict)]


def normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def artifact_types(response: dict[str, Any]) -> list[str]:
    found = []
    for artifact in normalize_list(response.get("artifacts")):
        if isinstance(artifact, dict) and artifact.get("type"):
            found.append(str(artifact["type"]))
    return found


def has_mutation_affordance(response: dict[str, Any]) -> bool:
    for item in normalize_list(response.get("affordances")):
        if isinstance(item, dict) and str(item.get("type") or "") in MUTATION_AFFORDANCE_TYPES:
            return True
    return bool(normalize_list(response.get("execution_cards")))


def assert_followups_are_supported(scenario: dict[str, Any], response: dict[str, Any], failures: list[str]) -> None:
    question = str(scenario.get("question") or "").strip()
    suggestions = [str(item).strip() for item in normalize_list(response.get("suggested_questions")) if str(item).strip()]
    for suggestion in suggestions:
        if suggestion in {".", "..", "...", "…"} or len(suggestion) < 8:
            failures.append(f"suggested question is too short or placeholder: {suggestion!r}")
        if not any("\uac00" <= char <= "\ud7a3" for char in suggestion):
            failures.append(f"suggested question must contain Korean text: {suggestion!r}")
        if "->" in suggestion or suggestion.lower().startswith(("idea ", "suggestion ", "follow-up ", "question ", "focus on ")):
            failures.append(f"suggested question leaks model planning text: {suggestion!r}")
        if question and suggestion == question:
            failures.append("suggested_questions must not repeat the original question")
        lower = suggestion.lower()
        has_mutation_term = any(term in lower for term in MUTATION_FOLLOWUP_TERMS)
        has_immediate_term = any(term in lower for term in IMMEDIATE_MUTATION_TERMS)
        if has_immediate_term:
            failures.append(f"suggested question implies immediate mutation: {suggestion!r}")
        if has_mutation_term and not has_mutation_affordance(response):
            failures.append(f"suggested mutation question is not backed by affordances: {suggestion!r}")


def assert_mutation_confirmation_only(response: dict[str, Any], failures: list[str]) -> None:
    cards = [item for item in normalize_list(response.get("execution_cards")) if isinstance(item, dict)]
    has_confirmation_artifact = "confirmation_required" in artifact_types(response)
    if not cards and not has_confirmation_artifact:
        failures.append("mutation scenario requires a confirmation card or confirmation_required artifact")
    for card in cards:
        if card.get("requires_confirmation") is not True:
            failures.append("execution card must require confirmation")
        if card.get("user_confirmed_required") is not True:
            failures.append("execution card must require explicit user confirmation")
    answer = str(response.get("answer_markdown") or response.get("display_markdown") or "")
    for term in ("실행했습니다", "발행했습니다", "반영했습니다", "게시했습니다", "완료했습니다"):
        if term in answer:
            failures.append(f"mutation confirmation-only answer must not claim completed work: {term}")


def validate_scenario_response(scenario: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    expect = normalize_dict(scenario.get("expect"))
    failures: list[str] = []
    expected_http_status = int(expect.get("expect_http_status") or 200)
    if expected_http_status != 200:
        failures.append(f"expect_http_status expected {expected_http_status}, got 200")
    if response.get("agent_contract_version") != AGENT_CONTRACT_VERSION:
        failures.append(f"agent_contract_version must be {AGENT_CONTRACT_VERSION}")
    if not str(response.get("answer_markdown") or response.get("display_markdown") or "").strip():
        failures.append("answer_markdown/display_markdown must not be empty")
    if expect.get("route") and response.get("route") != expect["route"]:
        failures.append(f"route expected {expect['route']!r}, got {response.get('route')!r}")
    if expect.get("intent") and response.get("intent") != expect["intent"]:
        failures.append(f"intent expected {expect['intent']!r}, got {response.get('intent')!r}")
    if expect.get("response_profile") and response.get("response_profile") != expect["response_profile"]:
        failures.append(
            f"response_profile expected {expect['response_profile']!r}, got {response.get('response_profile')!r}"
        )
    if expect.get("goal_type"):
        goal_model = normalize_dict(response.get("goal_model"))
        if goal_model.get("goal_type") != expect["goal_type"]:
            failures.append(f"goal_type expected {expect['goal_type']!r}, got {goal_model.get('goal_type')!r}")

    found_artifacts = artifact_types(response)
    for expected_type in normalize_list(expect.get("artifact_types")):
        if str(expected_type) not in found_artifacts:
            failures.append(f"expected artifact type {expected_type!r}, got {found_artifacts!r}")

    min_followups = int(expect.get("min_followups") or 0)
    if len(normalize_list(response.get("suggested_questions"))) < min_followups:
        failures.append(f"suggested_questions must contain at least {min_followups} item(s)")
    assert_followups_are_supported(scenario, response, failures)

    if expect.get("require_evidence") and not normalize_list(response.get("evidence_ledger")):
        failures.append("evidence_ledger must not be empty")
    if expect.get("require_affordances") and not normalize_list(response.get("affordances")):
        failures.append("affordances must not be empty")
    if expect.get("require_links_or_citations") and not (normalize_list(response.get("links")) or normalize_list(response.get("citations"))):
        failures.append("links or citations must not be empty")
    if expect.get("mutation_confirmation_only"):
        assert_mutation_confirmation_only(response, failures)
    expected_operation = str(expect.get("expect_execution_operation") or "")
    if expected_operation:
        operation_dump = json_text(response)
        operations = [
            str(item.get("operation") or "")
            for item in normalize_list(response.get("execution_cards"))
            if isinstance(item, dict)
        ]
        artifact_operations = [
            str(item.get("operation") or "")
            for item in normalize_list(response.get("artifacts"))
            if isinstance(item, dict) and item.get("operation")
        ]
        if expected_operation not in operations and expected_operation not in artifact_operations and expected_operation not in operation_dump:
            failures.append(f"expected execution operation {expected_operation!r}, got {operations + artifact_operations!r}")
    expected_component_status = str(expect.get("expect_component_error_status") or "")
    if expected_component_status:
        statuses = [
            str(item.get("status") or "")
            for item in normalize_list(response.get("component_errors"))
            if isinstance(item, dict)
        ]
        if expected_component_status not in statuses:
            failures.append(f"expected component error status {expected_component_status!r}, got {statuses!r}")

    event_type = str(expect.get("event_type") or "")
    if event_type:
        event_context = normalize_dict(response.get("event_context"))
        answer_dump = json.dumps(response, ensure_ascii=False)
        if event_context.get("event_type") != event_type and event_type not in answer_dump:
            failures.append(f"expected event_type {event_type!r} in event_context or response")
    workflow_definition_key = str(expect.get("workflow_definition_key") or "")
    if workflow_definition_key:
        workflow_definition_context = normalize_dict(response.get("workflow_definition_context"))
        answer_dump = json.dumps(response, ensure_ascii=False)
        if workflow_definition_context.get("workflow_definition_key") != workflow_definition_key and workflow_definition_key not in answer_dump:
            failures.append(f"expected workflow_definition_key {workflow_definition_key!r} in workflow_definition_context or response")

    answer_text = str(response.get("answer_markdown") or response.get("display_markdown") or "")
    response_dump = json_text(response)
    artifact_dump = json_text(response.get("artifacts") or [])
    followup_text = " ".join(str(item) for item in normalize_list(response.get("suggested_questions")))
    for term in normalize_list(expect.get("require_json_terms")):
        if str(term) not in response_dump:
            failures.append(f"response JSON must include term {term!r}")
    for term in normalize_list(expect.get("require_artifact_terms")):
        if str(term) not in artifact_dump:
            failures.append(f"artifacts must include term {term!r}")
    for term in normalize_list(expect.get("require_followup_terms")):
        if str(term) not in followup_text:
            failures.append(f"suggested_questions must include term {term!r}")
    for term in normalize_list(expect.get("forbid_followup_terms")):
        if str(term) in followup_text:
            failures.append(f"suggested_questions must not include term {term!r}")
    for term in normalize_list(expect.get("require_answer_terms")):
        if str(term) not in answer_text:
            failures.append(f"answer must include term {term!r}")
    for term in normalize_list(expect.get("forbid_answer_terms")):
        if str(term) in answer_text:
            failures.append(f"answer must not include term {term!r}")

    if failures:
        scenario_id = scenario.get("id") or scenario.get("name") or "unnamed"
        raise ScenarioValidationError(f"{scenario_id}: " + "; ".join(failures))
    return {
        "ok": True,
        "id": scenario.get("id") or "",
        "name": scenario.get("name") or "",
        "route": response.get("route"),
        "intent": response.get("intent"),
        "response_profile": response.get("response_profile"),
        "used_backend": response.get("used_backend"),
        "artifact_types": found_artifacts,
        "followup_count": len(normalize_list(response.get("suggested_questions"))),
        "evidence_count": len(normalize_list(response.get("evidence_ledger"))),
        "affordance_count": len(normalize_list(response.get("affordances"))),
        "execution_card_count": len(normalize_list(response.get("execution_cards"))),
    }


def validate_error_scenario_response(scenario: dict[str, Any], status_code: int, payload: Any, body_text: str) -> dict[str, Any]:
    expect = normalize_dict(scenario.get("expect"))
    expected_http_status = int(expect.get("expect_http_status") or 200)
    failures: list[str] = []
    if status_code != expected_http_status:
        failures.append(f"HTTP status expected {expected_http_status}, got {status_code}")
    dump = json_text(payload if payload is not None else body_text)
    for term in normalize_list(expect.get("require_json_terms")):
        if str(term) not in dump:
            failures.append(f"error JSON must include term {term!r}")
    for term in normalize_list(expect.get("forbid_answer_terms")):
        if str(term) in dump:
            failures.append(f"error body must not include term {term!r}")
    expected_component_status = str(expect.get("expect_component_error_status") or "")
    if expected_component_status and expected_component_status not in dump:
        failures.append(f"expected component error status {expected_component_status!r} in error body")
    if failures:
        scenario_id = scenario.get("id") or scenario.get("name") or "unnamed"
        raise ScenarioValidationError(f"{scenario_id}: " + "; ".join(failures))
    return {
        "ok": True,
        "id": scenario.get("id") or "",
        "name": scenario.get("name") or "",
        "http_status": status_code,
        "route": "",
        "intent": "",
        "response_profile": "",
        "used_backend": "",
        "artifact_types": [],
        "followup_count": 0,
        "evidence_count": 0,
        "affordance_count": 0,
        "execution_card_count": 0,
    }


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - operator-supplied smoke URL
        return json.loads(response.read().decode("utf-8"))


def run_scenario(base_url: str, scenario: dict[str, Any], employee_id: str, timeout: float) -> dict[str, Any]:
    target_employee = str(scenario.get("employee_id") or employee_id)
    payload = {
        "question": scenario.get("question") or "",
        "current_url": scenario.get("current_url") or DEFAULT_CURRENT_URL,
        "page_title": scenario.get("page_title") or "",
        "save_memory": False,
    }
    if scenario.get("mode"):
        payload["mode"] = scenario["mode"]
    if scenario.get("intent"):
        payload["intent"] = scenario["intent"]
    if isinstance(scenario.get("conversation"), list):
        payload["conversation"] = scenario["conversation"]
    query = urllib.parse.urlencode({"employee_id": target_employee})
    url = f"{base_url.rstrip('/')}/api/agents/boi-wiki/chat?{query}"
    started = time.perf_counter()
    try:
        response = post_json(url, payload, timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body)
        except json.JSONDecodeError:
            error_payload = None
        expected_status = int(normalize_dict(scenario.get("expect")).get("expect_http_status") or 200)
        if exc.code == expected_status:
            summary = validate_error_scenario_response(scenario, exc.code, error_payload, body)
            summary["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            return summary
        raise ScenarioValidationError(f"{scenario.get('id') or 'scenario'}: HTTP {exc.code} {body[:500]}") from exc
    summary = validate_scenario_response(scenario, response)
    summary["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BoI Agent REST scenario matrix checks.")
    parser.add_argument("--base-url", default="http://localhost:28000", help="BoI Wiki base URL.")
    parser.add_argument("--employee-id", default="100001", help="Default employee id for scenarios.")
    parser.add_argument("--scenario-file", default=str(DEFAULT_SCENARIO_FILE), help="JSON/YAML-JSON scenario file.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-scenario HTTP timeout seconds.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any scenario fails.")
    parser.add_argument("--summary", action="store_true", help="Print compact summary.")
    args = parser.parse_args()

    scenario_path = Path(args.scenario_file)
    scenarios = load_scenarios(scenario_path if scenario_path.exists() else None)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_id = str(scenario.get("id") or f"scenario-{index}")
        print(f"[{index}/{len(scenarios)}] {scenario_id}: {scenario.get('question') or ''}", file=sys.stderr, flush=True)
        try:
            results.append(run_scenario(args.base_url, scenario, args.employee_id, args.timeout))
        except Exception as exc:
            failures.append({"id": str(scenario.get("id") or ""), "name": str(scenario.get("name") or ""), "error": str(exc)})

    report = {
        "ok": not failures,
        "base_url": args.base_url,
        "scenario_count": len(scenarios),
        "passed": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
    }
    if args.summary:
        print(json.dumps({k: report[k] for k in ("ok", "base_url", "scenario_count", "passed", "failed", "failures")}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
