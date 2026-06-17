---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 이상 조치 담당자 알림
description: 조치 담당자에게 이상 조치 요청을 발송하는 Webhook/API action
tags:
- ActionGateway
- API
- EquipmentWorkflow
timestamp: 2026-06-17 12:09:00+09:00
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
event_types:
- corrective_action.requested.v1
- promotion.requested.v1
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - owner
  - equipment_id
  optional:
  - alarm_code
  - lot_id
result_contract:
  status: mocked
  fields:
  - notification_status
  - recipient
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/poc/equipment/notify-owner
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
    event_type: corrective_action.requested.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: sop.equipment.notify_action_owner
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/poc/equipment/notify-owner'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.notify_action_owner
  catalog_type: api
  doc_ref: boi:public:actions:api:notify-action-owner
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/poc/equipment/notify-owner' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

이상 조치 단계에서 담당자에게 확인과 조치를 요청한다.
