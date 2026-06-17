---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 정비 조치 완료 확인
description: 현장 정비 또는 조치 완료 여부를 확인하고 BoI에 완료 근거를 남기는 manual action
tags:
- Manual
- Maintenance
- EquipmentWorkflow
timestamp: 2026-06-17 12:21:00+09:00
boi_id: boi:public:actions:manual:confirm-maintenance-done
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.confirm_maintenance_done
connector_kind: manual
execution_mode: human
event_types:
- corrective_action.requested.v1
risk_level: medium
approval_required: false
dry_run_default: true
payload_contract:
  required:
  - equipment_id
  - owner
  optional:
  - maintenance_ticket
  - action_note
result_contract:
  status: manual_required
  fields:
  - confirmed_by
  - completion_note
  - completion_time
source_refs:
- type: sop
  ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: manual
method: HUMAN
url: manual://manual.equipment.confirm_maintenance_done
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
    event_type: corrective_action.requested.v1
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: manual_required
  manual_handoff:
    owner: 제조/품질 담당 조직
    doc_ref: boi:public:actions:manual:confirm-maintenance-done
curl: 'curl -X POST http://localhost:8100/api/actions/invoke -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"manual.equipment.confirm_maintenance_done","payload":{"equipment_id":"ETCH-VM-01"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: manual.equipment.confirm_maintenance_done
  catalog_type: manual_task
  doc_ref: boi:public:actions:manual:confirm-maintenance-done
health_check:
  type: manual
  check: 담당자와 승인권자 지정 여부 확인
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Checklist

- 정비 ticket 또는 현장 조치 기록을 확인한다.
- 장비 상태와 재발 방지 필요 여부를 확인한다.
- 완료 근거를 event-linked BoI에 남긴다.
