---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 외부 Webhook 이벤트 수신
description: 외부 시스템이 BoI API inbound webhook으로 업무 event를 전달하는 명세
tags:
- Webhook
- EventBroker
- Inbound
timestamp: 2026-06-17 12:12:00+09:00
boi_id: boi:public:actions:webhook:inbound-external-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: webhook.inbound.external_event
connector_kind: webhook
execution_mode: inbound
event_types:
- external.webhook.received.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event_type
  - payload
  optional:
  - source_refs
  - trace_id
result_contract:
  status: event_published
  fields:
  - event_id
  - trace_id
  - topic
source_refs:
- type: route
  ref: /api/webhooks/{source}
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://localhost:8000/api/webhooks/{source}
auth:
  type: header
  header: x-service-token
  value: $SERVICE_TOKEN
headers:
  Content-Type: application/json
  x-service-token: $SERVICE_TOKEN
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
    event_type: external.webhook.received.v1
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: webhook.inbound.external_event
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://localhost:8000/api/webhooks/{source}'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: webhook.inbound.external_event
  catalog_type: internal_webhook
  doc_ref: boi:public:actions:webhook:inbound-external-event
health_check:
  type: http
  command: curl -fsS 'http://localhost:8000/api/webhooks/{source}' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

사내 시스템 또는 테스트 스크립트가 webhook으로 업무 event를 발행할 때 사용한다.
