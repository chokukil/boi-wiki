from __future__ import annotations

from pathlib import Path

import yaml


def load_actions() -> list[dict]:
    return yaml.safe_load(Path("data/action_catalog/actions.yaml").read_text(encoding="utf-8"))["actions"]


def actions_for(event_type: str) -> list[dict]:
    return [
        action
        for action in load_actions()
        if action.get("enabled", True)
        and action.get("auto_dispatch", True)
        and (event_type in (action.get("event_types") or []) or "*" in (action.get("event_types") or []))
    ]


def action_keys(event_type: str) -> list[str]:
    return [action["action_key"] for action in sorted(actions_for(event_type), key=lambda x: int(x.get("order", 100)))]


def test_boi_materializer_runs_before_system_actions_for_alarm_events():
    keys = action_keys("equipment.alarm.raised.v1")

    assert keys[0] == "boi.materialize_event"
    assert "sop.equipment.request_trend_history" in keys
    assert "sop.equipment.request_raw_data" in keys
    assert "sop.equipment.create_root_cause_event" in keys


def test_sop_workflow_has_event_publish_chain_to_corrective_action():
    root_cause_keys = action_keys("root_cause.analysis.requested.v1")
    maintenance_keys = action_keys("maintenance.guide.requested.v1")
    corrective_keys = action_keys("corrective_action.requested.v1")

    assert "sop.equipment.create_maintenance_guide_event" in root_cause_keys
    assert "sop.equipment.create_corrective_action_event" in maintenance_keys
    assert "sop.equipment.notify_action_owner" in corrective_keys
    assert "sop.equipment.block_process_progress" in corrective_keys
    assert "sop.equipment.change_spec_rule" in corrective_keys


def test_high_risk_corrective_actions_require_approval():
    high_risk = [
        action
        for action in actions_for("corrective_action.requested.v1")
        if action.get("risk_level") == "high"
    ]

    assert {action["action_key"] for action in high_risk} == {
        "sop.equipment.block_process_progress",
        "sop.equipment.change_spec_rule",
    }
    assert all(action.get("approval_required") is True for action in high_risk)
