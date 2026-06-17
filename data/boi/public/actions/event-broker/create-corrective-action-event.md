---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 이상 조치 요청 이벤트 발행
description: 보전 가이드 요청을 이상 조치 요청 event로 전환한다.
tags:
- ActionGateway
- EventBroker
- EquipmentWorkflow
timestamp: 2026-06-17 12:05:00+09:00
boi_id: boi:public:actions:event-broker:create-corrective-action-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.create_corrective_action_event
connector_kind: event_broker
execution_mode: gateway
event_types:
- maintenance.guide.requested.v1
risk_level: medium
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - equipment_id
  - alarm_code
  - owner
  optional:
  - lot_id
  - wafer_id
result_contract:
  status: event_published
  emits: corrective_action.requested.v1
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
    event_type: maintenance.guide.requested.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: sop.equipment.create_corrective_action_event
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/events/publish'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.create_corrective_action_event
  catalog_type: event_publish
  doc_ref: boi:public:actions:event-broker:create-corrective-action-event
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/events/publish' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

보전 가이드 Agent가 담당자 조치와 승인 후보를 기록해야 할 때 호출한다.
