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

    assert "langflow.equipment.stage_analysis" in root_cause_keys
    assert "langflow.equipment.stage_analysis" in maintenance_keys
    assert "langflow.equipment.stage_analysis" in corrective_keys
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


def test_public_action_specs_include_executable_contracts_without_secrets():
    forbidden = [
        "dev-service-token-change-me",
        "dev-langflow-key-change-me",
        "not-needed",
        "x-service-token: dev",
    ]

    for spec_id, spec in public_action_specs().items():
        meta = spec["metadata"]
        text = spec["path"].read_text(encoding="utf-8")

        assert meta.get("protocol"), spec_id
        assert meta.get("auth"), spec_id
        assert meta.get("request_schema"), spec_id
        assert meta.get("response_schema"), spec_id
        assert meta.get("example_request"), spec_id
        assert meta.get("example_response"), spec_id
        assert meta.get("security_notes"), spec_id

        if meta.get("connector_kind") == "mcp":
            assert meta.get("mcp_server"), spec_id
            assert meta.get("tool_name"), spec_id
            assert meta.get("transport"), spec_id
            assert meta.get("input_schema"), spec_id
            assert meta.get("output_schema"), spec_id
            assert meta.get("example_tool_call"), spec_id
        else:
            assert meta.get("method"), spec_id
            assert meta.get("url"), spec_id
            assert meta.get("headers"), spec_id
            assert meta.get("curl"), spec_id
            assert meta.get("action_gateway_mapping"), spec_id
            assert meta.get("health_check"), spec_id

        for secret in forbidden:
            assert secret not in text, f"{spec_id} leaks {secret}"


def test_equipment_api_and_mcp_actions_are_wired_to_real_poc_endpoints():
    actions = {action["action_key"]: action for action in load_actions()}

    equipment_api_urls = {
        "sop.equipment.request_trend_history": "http://boi-api:8000/api/poc/equipment/trend-history",
        "sop.equipment.request_raw_data": "http://boi-api:8000/api/poc/equipment/raw-data",
        "sop.equipment.request_maintenance_guide": "http://boi-api:8000/api/poc/equipment/maintenance-guide",
        "sop.equipment.notify_action_owner": "http://boi-api:8000/api/poc/equipment/notify-owner",
        "sop.equipment.block_process_progress": "http://boi-api:8000/api/poc/equipment/process-hold",
        "sop.equipment.change_spec_rule": "http://boi-api:8000/api/poc/equipment/spec-rule-change",
    }

    for action_key, url in equipment_api_urls.items():
        action = actions[action_key]
        assert action["type"] == "api"
        assert action["method"] == "POST"
        assert action["url"] == url
        assert action["headers"]["x-service-token"] == "${service_token}"
        assert "payload" in action["body"]
        assert "dry_run" in action["body"]
        assert "approved_by" in action["body"]

    mcp_action = actions["mcp.boi_search.sample"]
    assert mcp_action["enabled"] is True
    assert mcp_action["type"] == "mcp_tool"
    assert mcp_action["url"] == "http://boi-wiki-mcp:8200/api/mcp/call"
    assert mcp_action["tool_name"] == "boi.search"

    timesfm = actions["mcp.timesfm.forecast"]
    assert timesfm["enabled"] is True
    assert timesfm["auto_dispatch"] is False
    assert timesfm["type"] == "mcp_tool"
    assert timesfm["connector_kind"] == "mcp"
    assert timesfm["transport"] == "sse"
    assert timesfm["mcp_server"]["url"] == "${timesfm_mcp_url}"
    assert timesfm["tool_name"] == "forecast"
    assert "timeseries.forecast.requested.v1" in timesfm["event_types"]


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

    alarm = next(event for event in equipment_events if event["event_type"] == "equipment.alarm.raised.v1")
    assert "langflow.boi.reference_flow" in alarm["recommended_actions"]

    trend = next(event for event in equipment_events if event["event_type"] == "trend.anomaly.detected.v1")
    assert trend["sop_stage_id"] == "detect"
    assert trend["workflow_stage"] == "이상 감지"

    for event_type in [
        "root_cause.analysis.requested.v1",
        "maintenance.guide.requested.v1",
        "corrective_action.requested.v1",
    ]:
        event = next(item for item in equipment_events if item["event_type"] == event_type)
        assert "langflow.equipment.stage_analysis" in event["recommended_actions"]

    corrective = next(event for event in equipment_events if event["event_type"] == "corrective_action.requested.v1")
    assert set(corrective["recommended_manual_actions"]) >= {
        "manual.equipment.approve_process_hold",
        "manual.equipment.approve_spec_rule_change",
        "manual.equipment.confirm_maintenance_done",
    }


def test_direct_development_events_actions_and_simulation_metadata_are_wired():
    event_types = yaml.safe_load(Path("data/event_catalog/event_types.yaml").read_text(encoding="utf-8"))["event_types"]
    direct_events = [event for event in event_types if str(event["event_type"]).startswith("direct_development.")]
    actions = {action["action_key"]: action for action in load_actions()}

    assert {event["event_type"] for event in direct_events} >= {
        "direct_development.result_check.requested.v1",
        "direct_development.map_view.requested.v1",
        "direct_development.cross_section.decision_required.v1",
        "direct_development.cross_section.requested.v1",
        "direct_development.fab_trend.compare_requested.v1",
        "direct_development.reporting.requested.v1",
        "direct_development.share.requested.v1",
    }
    for event in direct_events:
        assert event["sop_ref"] == "boi:public:sop:direct-development-reporting"
        assert event.get("sop_stage_id")
        assert "recommended_manual_actions" in event

    simulator_keys = {
        "direct_development.quality_response_trend.simulate",
        "direct_development.map_view.simulate",
        "direct_development.cross_section_request.simulate",
        "direct_development.cross_section_result.simulate",
        "direct_development.fab_trend_compare.simulate",
        "direct_development.reporting.simulate",
        "direct_development.messenger_share_preview.simulate",
    }
    for action_key in simulator_keys:
        action = actions[action_key]
        assert action["type"] == "langflow_run"
        assert action["connector_kind"] == "langflow"
        assert action["flow_name"] == "BoI Universal Action Simulator Flow"
        assert action["dry_run"] is False
        assert action["simulation_mode"] == "langflow_universal"
        assert action["simulation_label"] == "SIMULATED"
        assert action["real_system_status"] == "unavailable"

    decision = next(event for event in direct_events if event["event_type"] == "direct_development.cross_section.decision_required.v1")
    assert decision["recommended_actions"] == []
    assert decision["recommended_manual_actions"] == ["manual.direct_development.decide_cross_section"]

    share = next(event for event in direct_events if event["event_type"] == "direct_development.share.requested.v1")
    assert "direct_development.messenger_share.publish" in share["recommended_actions"]
    assert share["recommended_manual_actions"] == ["manual.direct_development.approve_committee_share"]
    assert actions["direct_development.messenger_share.publish"]["approval_required"] is True
    assert actions["direct_development.messenger_share.publish"]["requires_manual_action"] == "manual.direct_development.approve_committee_share"


def test_event_publish_actions_allow_slow_kafka_publish_roundtrips():
    actions = [action for action in load_actions() if action.get("type") == "event_publish"]

    assert actions
    for action in actions:
        assert int(action.get("timeout_seconds", 0)) >= 120


def test_timesfm_forecast_event_is_opt_in_and_documented():
    event_types = yaml.safe_load(Path("data/event_catalog/event_types.yaml").read_text(encoding="utf-8"))["event_types"]
    forecast = next(event for event in event_types if event["event_type"] == "timeseries.forecast.requested.v1")

    assert forecast["default_boi_type"] == "boi/analysis"
    assert forecast["recommended_actions"] == ["mcp.timesfm.forecast"]
    assert forecast["recommended_manual_actions"] == []
    assert Path("data/boi/public/event-types/timeseries.forecast.requested.v1.md").exists()
    assert Path("data/boi/public/actions/mcp/timesfm-forecast.md").exists()
