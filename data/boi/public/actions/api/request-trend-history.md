---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Trend / 이력 확인 요청
description: 장비/공정 Trend와 Lot/Wafer 이력을 조회하는 시스템 API action
tags:
- ActionGateway
- API
- EquipmentWorkflow
timestamp: 2026-06-17 12:06:00+09:00
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
event_types:
- equipment.alarm.raised.v1
- trend.anomaly.detected.v1
- root_cause.analysis.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - equipment_id
  optional:
  - lot_id
  - wafer_id
  - alarm_code
result_contract:
  status: mocked
  fields:
  - trend_status
  - lot_history_ref
  - wafer_history_ref
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/poc/equipment/trend-history
auth:
  type: header
  header: x-service-token
  value: $SERVICE_TOKEN
headers:
  Content-Type: application/json
  x-service-token: ${service_token}
request_schema:
  type: object
  required:
  - payload
  properties:
    payload:
      type: object
    event:
      type: object
    request_id:
      type: string
    dry_run:
      type: boolean
    approved_by:
      type: string
response_schema:
  type: object
  required:
  - ok
  - status
  properties:
    ok:
      type: boolean
    status:
      const: invoked
    request_id:
      type: string
    result:
      type: object
example_request:
  payload:
    equipment_id: ETCH-VM-01
    lot_id: LOT-POC-001
    wafer_id: WF-POC-001
    owner: '100001'
    alarm_code: RESPONSE_CHAIN_ABNORMAL
  event:
    event_type: equipment.alarm.raised.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: sop.equipment.request_trend_history
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/poc/equipment/trend-history'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.request_trend_history
  catalog_type: api
  doc_ref: boi:public:actions:api:request-trend-history
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/poc/equipment/trend-history' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

이상 감지와 원인 분석 단계에서 Trend 이상 여부와 Lot/Wafer 이력을 확인한다.
