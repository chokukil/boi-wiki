---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Alarm / Trend / 이력 맥락 확인
description: 담당자가 설비 Alarm, Trend, Lot/Wafer 이력 맥락을 확인하는 manual action
tags:
- Manual
- EquipmentWorkflow
- HumanHandoff
timestamp: 2026-06-17 12:17:00+09:00
boi_id: boi:public:actions:manual:confirm-alarm-context
visibility: public
classification: internal
owner: AIX 확산 TF / 제조 PoC
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.confirm_alarm_context
connector_kind: manual
execution_mode: human
event_types:
- equipment.alarm.raised.v1
- trend.anomaly.detected.v1
risk_level: low
approval_required: false
dry_run_default: true
payload_contract:
  required:
  - equipment_id
  - owner
  optional:
  - alarm_code
  - lot_id
  - wafer_id
result_contract:
  status: manual_required
  fields:
  - assignee
  - checklist
  - completion_note
source_refs:
- type: sop
  ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: manual
method: HUMAN
url: manual://manual.equipment.confirm_alarm_context
auth:
  type: human_handoff
  approval_required: false
headers:
  x-service-token: $SERVICE_TOKEN
  content-type: application/json
request_schema:
  type: object
  required:
  - payload
  - assignee
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
    assignee:
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
      const: manual_required
    request_id:
      type: string
    result:
      type: object
example_request:
  payload:
    equipment_id: ETCH-VM-01
    owner: '100001'
    note: 사람 확인 필요
  event:
    event_type: equipment.alarm.raised.v1
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: manual_required
  manual_handoff:
    owner: AIX 확산 TF / 제조 PoC
    doc_ref: boi:public:actions:manual:confirm-alarm-context
curl: 'curl -X POST http://localhost:8100/api/actions/invoke -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"manual.equipment.confirm_alarm_context","payload":{"equipment_id":"ETCH-VM-01"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: manual.equipment.confirm_alarm_context
  catalog_type: manual_task
  doc_ref: boi:public:actions:manual:confirm-alarm-context
health_check:
  type: manual
  check: 담당자와 승인권자 지정 여부 확인
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Checklist

- Alarm 발생 시간과 설비 ID를 확인한다.
- Trend/Raw Data 조회 결과가 실제 이력과 맞는지 확인한다.
- 원인 분석 요청으로 넘길 추가 context를 남긴다.
