---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Spec / Rule 변경 요청
description: Spec 또는 Rule 변경 후보를 생성하는 고위험 API action
tags: [ActionGateway, API, HighRisk, EquipmentWorkflow]
timestamp: 2026-06-17T12:11:00+09:00
boi_id: boi:public:actions:api:change-spec-rule
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.change_spec_rule
connector_kind: api
execution_mode: gateway
event_types: [corrective_action.requested.v1]
risk_level: high
approval_required: true
dry_run_default: true
requires_manual_action: manual.equipment.approve_spec_rule_change
payload_contract:
  required: [equipment_id, owner]
  optional: [alarm_code, lot_id]
result_contract:
  status: approval_required
  fields: [requested_change, equipment_id]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

변경관리 승인 전에는 실제 변경을 수행하지 않는다.
