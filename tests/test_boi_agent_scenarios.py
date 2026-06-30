from __future__ import annotations

import json
from pathlib import Path

import pytest


def base_agent_response(**overrides):
    response = {
        "agent_contract_version": "boi-agent.response.v1",
        "answer_markdown": "## 관계 요약\n\n설비 이상 SOP의 Event, Action, Manual Handoff 관계를 정리했습니다.",
        "display_markdown": "## 관계 요약\n\n설비 이상 SOP의 Event, Action, Manual Handoff 관계를 정리했습니다.",
        "route": "deep",
        "intent": "workflow_explain",
        "used_backend": "native_langgraph",
        "links": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
        "citations": [{"label": "설비 SOP", "url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001"}],
        "artifacts": [{"type": "workflow_summary", "data": [{"stage": "이상 감지", "actions": "api.equipment.request_trend_history"}]}],
        "execution_cards": [],
        "evidence_ledger": [{"kind": "current_page", "label": "설비 SOP", "used_for": ["answer", "followup"]}],
        "affordances": [{"type": "make_artifact", "label": "Mermaid로 보기", "question_hint": "이 관계 표를 Mermaid 프로세스 플로우로 다시 보여줘."}],
        "suggested_questions": ["이 관계 표를 Mermaid 프로세스 플로우로 다시 보여줘."],
        "access_summary": {"can_read": True},
        "guardrails_applied": ["artifact_link_acl"],
    }
    response.update(overrides)
    return response


def workflow_scenario(**expect_overrides):
    scenario = {
        "id": "sop-workflow-summary",
        "question": "이 SOP의 Event, Action, Manual Handoff 관계를 표로 요약해줘.",
        "current_url": "/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001",
        "expect": {
            "route": "deep",
            "intent": "workflow_explain",
            "artifact_types": ["workflow_summary"],
            "min_followups": 1,
            "require_evidence": True,
            "require_affordances": True,
            "require_links_or_citations": True,
            **expect_overrides,
        },
    }
    return scenario


def test_validate_agent_scenario_accepts_valid_workflow_response():
    import scripts.check_boi_agent_scenarios as script

    summary = script.validate_scenario_response(workflow_scenario(), base_agent_response())

    assert summary["ok"] is True
    assert summary["artifact_types"] == ["workflow_summary"]
    assert summary["followup_count"] == 1


def test_validate_agent_scenario_rejects_missing_followups():
    import scripts.check_boi_agent_scenarios as script

    with pytest.raises(script.ScenarioValidationError, match="suggested_questions"):
        script.validate_scenario_response(
            workflow_scenario(),
            base_agent_response(suggested_questions=[]),
        )


def test_validate_agent_scenario_rejects_impossible_mutation_followup():
    import scripts.check_boi_agent_scenarios as script

    with pytest.raises(script.ScenarioValidationError, match="not backed by affordances"):
        script.validate_scenario_response(
            workflow_scenario(),
            base_agent_response(suggested_questions=["이 Action을 바로 실행해줘."]),
        )


def test_validate_agent_scenario_requires_confirmation_card_for_mutation():
    import scripts.check_boi_agent_scenarios as script

    scenario = workflow_scenario(
        route="approval_required",
        intent="action_invoke",
        artifact_types=["confirmation_required"],
        min_followups=1,
        mutation_confirmation_only=True,
    )
    response = base_agent_response(
        route="approval_required",
        intent="action_invoke",
        artifacts=[{"type": "confirmation_required", "data": {"operation": "action_invoke"}}],
        execution_cards=[
            {
                "operation": "action_invoke",
                "requires_confirmation": True,
                "user_confirmed_required": True,
                "permission": {"allowed": True},
            }
        ],
        affordances=[{"type": "request_execution", "operation": "action_invoke", "question_hint": "요청 실행 전에 확인할 내용을 정리해줘."}],
        suggested_questions=["요청 실행 전에 확인할 내용을 정리해줘."],
    )

    summary = script.validate_scenario_response(scenario, response)

    assert summary["ok"] is True
    assert summary["execution_card_count"] == 1


def test_validate_agent_scenario_supports_extended_semiconductor_expectations():
    import scripts.check_boi_agent_scenarios as script

    scenario = workflow_scenario(
        require_json_terms=["equipment.alarm.raised.v1", "api.equipment.request_trend_history"],
        require_artifact_terms=["api.equipment.request_trend_history"],
        require_followup_terms=["Mermaid"],
        forbid_followup_terms=["Idea", "Suggestion", "->"],
        expect_execution_operation="action_invoke",
    )
    response = base_agent_response(
        answer_markdown="equipment.alarm.raised.v1 발생 시 Trend 확인과 Raw Data 확인이 필요합니다.",
        artifacts=[
            {
                "type": "workflow_summary",
                "data": [{"stage": "이상 감지", "actions": "api.equipment.request_trend_history"}],
            }
        ],
        execution_cards=[
            {
                "operation": "action_invoke",
                "requires_confirmation": True,
                "user_confirmed_required": True,
            }
        ],
        affordances=[{"type": "request_execution", "operation": "action_invoke"}],
        suggested_questions=["이 흐름을 Mermaid 프로세스 플로우로 보여줘."],
    )

    summary = script.validate_scenario_response(scenario, response)

    assert summary["ok"] is True


def test_validate_agent_scenario_rejects_model_planning_followup_text():
    import scripts.check_boi_agent_scenarios as script

    with pytest.raises(script.ScenarioValidationError, match="model planning text"):
        script.validate_scenario_response(
            workflow_scenario(),
            base_agent_response(suggested_questions=["Idea 2: Ask about Raw Data -> Raw Data 확인 결과를 대조해줘."]),
        )


def test_validate_agent_scenario_accepts_expected_http_error():
    import scripts.check_boi_agent_scenarios as script

    scenario = workflow_scenario(
        expect_http_status=503,
        require_json_terms=["boi_agent_suggestions_unavailable"],
        expect_component_error_status="boi_agent_suggestions_unavailable",
    )

    summary = script.validate_error_scenario_response(
        scenario,
        503,
        {
            "detail": "boi_agent_suggestions_unavailable",
            "component_errors": [{"status": "boi_agent_suggestions_unavailable"}],
        },
        "",
    )

    assert summary["ok"] is True


def test_validate_agent_scenario_rejects_mutation_without_confirmation_card():
    import scripts.check_boi_agent_scenarios as script

    scenario = workflow_scenario(
        route="approval_required",
        intent="action_invoke",
        mutation_confirmation_only=True,
    )

    with pytest.raises(script.ScenarioValidationError, match="confirmation"):
        script.validate_scenario_response(
            scenario,
            base_agent_response(route="approval_required", intent="action_invoke", execution_cards=[]),
        )


def test_load_scenarios_accepts_json_yaml_superset(tmp_path: Path):
    import scripts.check_boi_agent_scenarios as script

    path = tmp_path / "scenarios.yaml"
    path.write_text(json.dumps({"scenarios": [workflow_scenario()]}, ensure_ascii=False), encoding="utf-8")

    scenarios = script.load_scenarios(path)

    assert scenarios[0]["id"] == "sop-workflow-summary"


def test_semiconductor_rest_scenario_fixture_loads():
    import scripts.check_boi_agent_scenarios as script

    scenarios = script.load_scenarios(Path("tests/fixtures/boi_agent_semiconductor_scenarios.json"))

    ids = {scenario["id"] for scenario in scenarios}
    assert "equipment-alarm-stage-flow" in ids
    assert "direct-development-cross-section-prereq" in ids
    assert "restricted-export-negative" in ids


def test_semiconductor_ui_scenario_fixture_loads():
    payload = json.loads(Path("tests/fixtures/boi_agent_ui_semiconductor_scenarios.json").read_text(encoding="utf-8"))

    scenarios = payload["scenarios"]
    assert scenarios[0]["expect_artifact"] == "mermaid"
    assert {scenario["expect_artifact"] for scenario in scenarios} >= {
        "mermaid",
        "action_requirements",
        "confirmation_required",
    }
