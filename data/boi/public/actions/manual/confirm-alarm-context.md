---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Alarm / Trend / 이력 맥락 확인
description: 담당자가 설비 Alarm, Trend, Lot/Wafer 이력 맥락을 확인하는 manual action
tags: [Manual, EquipmentWorkflow, HumanHandoff]
timestamp: 2026-06-17T12:17:00+09:00
boi_id: boi:public:actions:manual:confirm-alarm-context
visibility: public
classification: internal
owner: AIX 확산 TF / 제조 PoC
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.confirm_alarm_context
connector_kind: manual
execution_mode: human
event_types: [equipment.alarm.raised.v1, trend.anomaly.detected.v1]
risk_level: low
approval_required: false
dry_run_default: true
payload_contract:
  required: [equipment_id, owner]
  optional: [alarm_code, lot_id, wafer_id]
result_contract:
  status: manual_required
  fields: [assignee, checklist, completion_note]
source_refs:
  - type: sop
    ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Checklist

- Alarm 발생 시간과 설비 ID를 확인한다.
- Trend/Raw Data 조회 결과가 실제 이력과 맞는지 확인한다.
- 원인 분석 요청으로 넘길 추가 context를 남긴다.
