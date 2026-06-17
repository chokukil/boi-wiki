---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 원인 분석 이벤트 발행
description: 이상 감지 event를 원인 분석 요청 event로 전환한다.
tags:
- ActionGateway
- EventBroker
- EquipmentWorkflow
timestamp: 2026-06-17 12:03:00+09:00
boi_id: boi:public:actions:event-broker:create-root-cause-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.create_root_cause_event
connector_kind: event_broker
execution_mode: gateway
event_types:
- equipment.alarm.raised.v1
- trend.anomaly.detected.v1
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
  emits: root_cause.analysis.requested.v1
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
    event_type: equipment.alarm.raised.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: sop.equipment.create_root_cause_event
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/events/publish'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.create_root_cause_event
  catalog_type: event_publish
  doc_ref: boi:public:actions:event-broker:create-root-cause-event
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/events/publish' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

이상 감지 Agent가 데이터 조회 후 원인 분석 Agent를 깨우는 handoff action이다.
