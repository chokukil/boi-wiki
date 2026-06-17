---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 이상 조치 요청 이벤트 발행
description: 보전 가이드 요청을 이상 조치 요청 event로 전환한다.
tags: [ActionGateway, EventBroker, EquipmentWorkflow]
timestamp: 2026-06-17T12:05:00+09:00
boi_id: boi:public:actions:event-broker:create-corrective-action-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.create_corrective_action_event
connector_kind: event_broker
execution_mode: gateway
event_types: [maintenance.guide.requested.v1]
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required: [equipment_id, alarm_code, owner]
  optional: [lot_id, wafer_id]
result_contract:
  status: event_published
  emits: corrective_action.requested.v1
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

보전 가이드 Agent가 담당자 조치와 승인 후보를 기록해야 할 때 호출한다.
