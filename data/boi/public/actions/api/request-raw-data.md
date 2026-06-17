---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Raw / Source Data 확인 요청
description: HyVIS/TAS/설비 시스템의 Raw Data와 Source Data를 조회하는 API action
tags: [ActionGateway, API, EquipmentWorkflow]
timestamp: 2026-06-17T12:07:00+09:00
boi_id: boi:public:actions:api:request-raw-data
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.request_raw_data
connector_kind: api
execution_mode: gateway
event_types: [equipment.alarm.raised.v1, root_cause.analysis.requested.v1, maintenance.guide.requested.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [equipment_id]
  optional: [lot_id, wafer_id]
result_contract:
  status: mocked
  fields: [raw_data_ref, source_data_ref]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

원인 후보 판단과 보전 가이드 생성 전에 Raw/Source Data 참조를 확보한다.
