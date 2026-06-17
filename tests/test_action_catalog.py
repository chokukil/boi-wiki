from __future__ import annotations

from pathlib import Path

import yaml


def split_frontmatter(markdown: str) -> tuple[dict, str]:
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    return yaml.safe_load(parts[1]) or {}, parts[2]


def public_action_specs() -> dict[str, dict]:
    specs: dict[str, dict] = {}
    for path in Path("data/boi/public/actions").rglob("*.md"):
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("type") == "boi/action-spec" and meta.get("action_key"):
            specs[str(meta["boi_id"])] = {"metadata": meta, "path": path}
    return specs


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


def test_every_catalog_action_has_public_spec_doc_ref():
    specs = public_action_specs()

    for action in load_actions():
        assert action.get("connector_kind"), action["action_key"]
        assert action.get("doc_ref"), action["action_key"]
        assert action["doc_ref"] in specs, action["action_key"]
        spec = specs[action["doc_ref"]]["metadata"]
        assert spec["action_key"] == action["action_key"]
        assert spec["connector_kind"] == action["connector_kind"]
        assert spec.get("execution_mode")
        assert spec.get("payload_contract")
        assert spec.get("result_contract")


def test_manual_equipment_actions_are_registered_but_not_auto_dispatched():
    manual_actions = {
        action["action_key"]: action
        for action in load_actions()
        if action.get("connector_kind") == "manual"
    }

    assert set(manual_actions) >= {
        "manual.equipment.confirm_alarm_context",
        "manual.equipment.review_root_cause",
        "manual.equipment.approve_process_hold",
        "manual.equipment.approve_spec_rule_change",
        "manual.equipment.confirm_maintenance_done",
    }
    assert all(action["type"] == "manual_task" for action in manual_actions.values())
    assert all(action.get("auto_dispatch") is False for action in manual_actions.values())
    assert manual_actions["manual.equipment.approve_process_hold"]["approval_required"] is True
    assert manual_actions["manual.equipment.approve_spec_rule_change"]["approval_required"] is True


def test_high_risk_system_actions_reference_manual_approval_actions():
    actions = {action["action_key"]: action for action in load_actions()}

    assert actions["sop.equipment.block_process_progress"]["requires_manual_action"] == "manual.equipment.approve_process_hold"
    assert actions["sop.equipment.change_spec_rule"]["requires_manual_action"] == "manual.equipment.approve_spec_rule_change"


def test_equipment_events_reference_public_sop_and_manual_actions():
    event_types = yaml.safe_load(Path("data/event_catalog/event_types.yaml").read_text(encoding="utf-8"))["event_types"]
    equipment_events = [event for event in event_types if str(event["event_type"]).startswith(("equipment.", "trend.", "root_cause.", "maintenance.", "corrective_"))]

    assert equipment_events
    for event in equipment_events:
        assert event["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
        assert event.get("sop_stage_id")
        assert "recommended_manual_actions" in event

    corrective = next(event for event in equipment_events if event["event_type"] == "corrective_action.requested.v1")
    assert set(corrective["recommended_manual_actions"]) >= {
        "manual.equipment.approve_process_hold",
        "manual.equipment.approve_spec_rule_change",
        "manual.equipment.confirm_maintenance_done",
    }
