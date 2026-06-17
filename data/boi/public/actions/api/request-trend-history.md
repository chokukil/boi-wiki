---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Trend / 이력 확인 요청
description: 장비/공정 Trend와 Lot/Wafer 이력을 조회하는 시스템 API action
tags: [ActionGateway, API, EquipmentWorkflow]
timestamp: 2026-06-17T12:06:00+09:00
boi_id: boi:public:actions:api:request-trend-history
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.request_trend_history
connector_kind: api
execution_mode: gateway
event_types: [equipment.alarm.raised.v1, trend.anomaly.detected.v1, root_cause.analysis.requested.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [equipment_id]
  optional: [lot_id, wafer_id, alarm_code]
result_contract:
  status: mocked
  fields: [trend_status, lot_history_ref, wafer_history_ref]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

이상 감지와 원인 분석 단계에서 Trend 이상 여부와 Lot/Wafer 이력을 확인한다.
