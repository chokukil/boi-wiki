---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Event Broker로 이벤트 발행
description: Agent, Langflow, API에서 업무 이벤트를 Kafka Event Broker로 발행하는 공통 action
tags:
- ActionGateway
- EventBroker
- Kafka
timestamp: 2026-06-17 12:02:00+09:00
boi_id: boi:public:actions:event-broker:publish-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: boi.publish_event
connector_kind: event_broker
execution_mode: gateway
event_types:
- manual.input.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event_type
  - payload
  optional:
  - source_refs
result_contract:
  status: event_published
  fields:
  - event_id
  - trace_id
  - topic
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http+kafka
method: POST
url: http://boi-api:8000/api/events/publish
auth:
  type: none
  note: Published through trusted Action Gateway service network
headers:
  Content-Type: application/json
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
    event_type: manual.input.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: boi.publish_event
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/events/publish'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: boi.publish_event
  catalog_type: event_publish
  doc_ref: boi:public:actions:event-broker:publish-event
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/events/publish' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

수동 입력이나 외부 도구가 다음 workflow event를 깨울 때 사용한다.
