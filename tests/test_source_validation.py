from __future__ import annotations

from pathlib import Path


def test_manual_high_risk_approval_actions_do_not_require_nested_manual_action(boi_app_module):
    content = """
actions:
  - action_key: sop.equipment.block_process_progress
    type: api
    connector_kind: api
    doc_ref: boi:public:actions:api:block-process-progress
    risk_level: high
    requires_manual_action: manual.equipment.approve_process_hold
  - action_key: manual.equipment.approve_process_hold
    type: manual_task
    connector_kind: manual
    doc_ref: boi:public:actions:manual:approve-process-hold
    risk_level: high
    approval_required: true
"""

    validation = boi_app_module.validate_source_content(Path("actions.yaml"), content)

    assert validation["ok"] is True
    assert validation["errors"] == []


def test_non_manual_high_risk_actions_require_manual_action_reference(boi_app_module):
    content = """
actions:
  - action_key: sop.equipment.block_process_progress
    type: api
    connector_kind: api
    doc_ref: boi:public:actions:api:block-process-progress
    risk_level: high
"""

    validation = boi_app_module.validate_source_content(Path("actions.yaml"), content)

    assert validation["ok"] is False
    assert validation["errors"] == [
        "sop.equipment.block_process_progress high-risk action requires requires_manual_action"
    ]


def test_non_manual_high_risk_actions_must_reference_existing_manual_action(boi_app_module):
    missing_manual = """
actions:
  - action_key: sop.equipment.block_process_progress
    type: api
    connector_kind: api
    doc_ref: boi:public:actions:api:block-process-progress
    risk_level: high
    requires_manual_action: manual.equipment.missing_approval
"""
    non_manual_target = """
actions:
  - action_key: sop.equipment.block_process_progress
    type: api
    connector_kind: api
    doc_ref: boi:public:actions:api:block-process-progress
    risk_level: high
    requires_manual_action: sop.equipment.notify_action_owner
  - action_key: sop.equipment.notify_action_owner
    type: api
    connector_kind: api
    doc_ref: boi:public:actions:api:notify-action-owner
    risk_level: medium
"""

    missing_validation = boi_app_module.validate_source_content(Path("actions.yaml"), missing_manual)
    non_manual_validation = boi_app_module.validate_source_content(Path("actions.yaml"), non_manual_target)

    assert missing_validation["ok"] is False
    assert missing_validation["errors"] == [
        "sop.equipment.block_process_progress requires_manual_action references missing action: manual.equipment.missing_approval"
    ]
    assert non_manual_validation["ok"] is False
    assert non_manual_validation["errors"] == [
        "sop.equipment.block_process_progress requires_manual_action must reference a manual action: sop.equipment.notify_action_owner"
    ]
