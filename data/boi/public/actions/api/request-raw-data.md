---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Raw / Source Data 확인 요청
description: HyVIS/TAS/설비 시스템의 Raw Data와 Source Data를 조회하는 API action
tags:
- ActionGateway
- API
- EquipmentWorkflow
timestamp: 2026-06-17 12:07:00+09:00
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
event_types:
- equipment.alarm.raised.v1
- root_cause.analysis.requested.v1
- maintenance.guide.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - equipment_id
  optional:
  - lot_id
  - wafer_id
result_contract:
  status: mocked
  fields:
  - raw_data_ref
  - source_data_ref
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/poc/equipment/raw-data
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
  action: sop.equipment.request_raw_data
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/poc/equipment/raw-data'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.request_raw_data
  catalog_type: api
  doc_ref: boi:public:actions:api:request-raw-data
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/poc/equipment/raw-data' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

원인 후보 판단과 보전 가이드 생성 전에 Raw/Source Data 참조를 확보한다.
