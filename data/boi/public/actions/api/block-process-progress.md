---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 공정 진행 금지 요청
description: 이상 조치 Agent가 공정 진행 금지를 요청하는 고위험 API action
tags: [ActionGateway, API, HighRisk, EquipmentWorkflow]
timestamp: 2026-06-17T12:10:00+09:00
boi_id: boi:public:actions:api:block-process-progress
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.block_process_progress
connector_kind: api
execution_mode: gateway
event_types: [corrective_action.requested.v1]
risk_level: high
approval_required: true
dry_run_default: true
requires_manual_action: manual.equipment.approve_process_hold
payload_contract:
  required: [equipment_id, owner]
  optional: [alarm_code, lot_id]
result_contract:
  status: approval_required
  fields: [requested_state, equipment_id]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

PoC에서는 승인 전 dry-run 또는 approval_required 상태로만 기록한다.
