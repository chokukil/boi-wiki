---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Spec / Rule 변경 승인
description: Spec 또는 Rule 변경 요청을 승인 또는 반려하는 manual approval action
tags: [Manual, Approval, HighRisk, EquipmentWorkflow]
timestamp: 2026-06-17T12:20:00+09:00
boi_id: boi:public:actions:manual:approve-spec-rule-change
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.approve_spec_rule_change
connector_kind: manual
execution_mode: human
event_types: [corrective_action.requested.v1]
risk_level: high
approval_required: true
dry_run_default: true
payload_contract:
  required: [equipment_id, owner]
  optional: [alarm_code, requested_change, root_cause]
result_contract:
  status: manual_required
  fields: [approved_by, approval_decision, change_ticket]
source_refs:
  - type: action
    ref: sop.equipment.change_spec_rule
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Checklist

- 변경관리 ticket과 영향 범위를 확인한다.
- 승인권자와 적용 시점을 확정한다.
- 승인 전 system action은 dry-run 또는 approval_required 상태로만 둔다.
