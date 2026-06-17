---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 정비 조치 완료 확인
description: 현장 정비 또는 조치 완료 여부를 확인하고 BoI에 완료 근거를 남기는 manual action
tags: [Manual, Maintenance, EquipmentWorkflow]
timestamp: 2026-06-17T12:21:00+09:00
boi_id: boi:public:actions:manual:confirm-maintenance-done
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.confirm_maintenance_done
connector_kind: manual
execution_mode: human
event_types: [corrective_action.requested.v1]
risk_level: medium
approval_required: false
dry_run_default: true
payload_contract:
  required: [equipment_id, owner]
  optional: [maintenance_ticket, action_note]
result_contract:
  status: manual_required
  fields: [confirmed_by, completion_note, completion_time]
source_refs:
  - type: sop
    ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Checklist

- 정비 ticket 또는 현장 조치 기록을 확인한다.
- 장비 상태와 재발 방지 필요 여부를 확인한다.
- 완료 근거를 event-linked BoI에 남긴다.
