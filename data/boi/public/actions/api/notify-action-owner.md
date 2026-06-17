---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 이상 조치 담당자 알림
description: 조치 담당자에게 이상 조치 요청을 발송하는 Webhook/API action
tags: [ActionGateway, API, EquipmentWorkflow]
timestamp: 2026-06-17T12:09:00+09:00
boi_id: boi:public:actions:api:notify-action-owner
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.notify_action_owner
connector_kind: api
execution_mode: gateway
event_types: [corrective_action.requested.v1, promotion.requested.v1]
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required: [owner, equipment_id]
  optional: [alarm_code, lot_id]
result_contract:
  status: mocked
  fields: [notification_status, recipient]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

이상 조치 단계에서 담당자에게 확인과 조치를 요청한다.
