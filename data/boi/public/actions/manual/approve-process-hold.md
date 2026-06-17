---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 공정 진행 금지 승인
description: 공정 진행 금지 요청을 승인 또는 반려하는 manual approval action
tags: [Manual, Approval, HighRisk, EquipmentWorkflow]
timestamp: 2026-06-17T12:19:00+09:00
boi_id: boi:public:actions:manual:approve-process-hold
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.approve_process_hold
connector_kind: manual
execution_mode: human
event_types: [corrective_action.requested.v1]
risk_level: high
approval_required: true
dry_run_default: true
payload_contract:
  required: [equipment_id, owner]
  optional: [alarm_code, lot_id, root_cause]
result_contract:
  status: manual_required
  fields: [approved_by, approval_decision, approval_note]
source_refs:
  - type: action
    ref: sop.equipment.block_process_progress
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Checklist

- 공정 Hold 영향 범위를 확인한다.
- 품질/생산 승인권자 결재를 확보한다.
- 승인 전 system action은 dry-run 또는 approval_required 상태로만 둔다.
