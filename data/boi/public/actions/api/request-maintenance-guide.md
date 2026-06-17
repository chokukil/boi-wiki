---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 장비 보전 가이드 요청
description: 장비 이상 가능성이 있을 때 보전 SOP와 조치 기준을 요청하는 API action
tags: [ActionGateway, API, EquipmentWorkflow]
timestamp: 2026-06-17T12:08:00+09:00
boi_id: boi:public:actions:api:request-maintenance-guide
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.request_maintenance_guide
connector_kind: api
execution_mode: gateway
event_types: [root_cause.analysis.completed.v1, maintenance.guide.requested.v1]
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required: [equipment_id, alarm_code]
  optional: [lot_id, wafer_id]
result_contract:
  status: mocked
  fields: [guide_boi_ref, recommended_steps]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

장비 이상 가능성이 확인된 뒤 SOP와 장비 이력을 참조해 보전 기준을 반환한다.
