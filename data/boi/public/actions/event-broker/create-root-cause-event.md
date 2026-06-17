---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 원인 분석 이벤트 발행
description: 이상 감지 event를 원인 분석 요청 event로 전환한다.
tags: [ActionGateway, EventBroker, EquipmentWorkflow]
timestamp: 2026-06-17T12:03:00+09:00
boi_id: boi:public:actions:event-broker:create-root-cause-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.create_root_cause_event
connector_kind: event_broker
execution_mode: gateway
event_types: [equipment.alarm.raised.v1, trend.anomaly.detected.v1]
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required: [equipment_id, alarm_code, owner]
  optional: [lot_id, wafer_id]
result_contract:
  status: event_published
  emits: root_cause.analysis.requested.v1
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

이상 감지 Agent가 데이터 조회 후 원인 분석 Agent를 깨우는 handoff action이다.
