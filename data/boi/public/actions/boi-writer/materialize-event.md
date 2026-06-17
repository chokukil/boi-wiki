---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Event를 BoI로 자산화
description: Event Broker에서 받은 업무 이벤트를 OKF 기반 BoI 문서로 생성하는 1급 BoI Writer connector
tags:
- ActionGateway
- BoIWriter
- EventBroker
timestamp: 2026-06-17 12:01:00+09:00
boi_id: boi:public:actions:boi-writer:materialize-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: boi.materialize_event
connector_kind: boi_writer
execution_mode: gateway
event_types:
- '*'
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event_id
  - event_type
  - payload
  optional:
  - source_refs
  - trace_id
  - actor
result_contract:
  status: materialized
  fields:
  - boi_id
  - boi_uri
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/boi/materialize-event
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
    event_type: '*'
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: boi.materialize_event
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/boi/materialize-event'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: boi.materialize_event
  catalog_type: boi_materialize
  doc_ref: boi:public:actions:boi-writer:materialize-event
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/boi/materialize-event' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

Event Router가 모든 업무 이벤트에 대해 가장 먼저 호출해 event-linked Private BoI를 만든다.
