---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 공정 진행 금지 승인
description: 공정 진행 금지 요청을 승인 또는 반려하는 manual approval action
tags:
- Manual
- Approval
- HighRisk
- EquipmentWorkflow
timestamp: 2026-06-17 12:19:00+09:00
boi_id: boi:public:actions:manual:approve-process-hold
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.approve_process_hold
connector_kind: manual
execution_mode: human
event_types:
- corrective_action.requested.v1
risk_level: high
approval_required: true
dry_run_default: true
payload_contract:
  required:
  - equipment_id
  - owner
  optional:
  - alarm_code
  - lot_id
  - root_cause
result_contract:
  status: manual_required
  fields:
  - approved_by
  - approval_decision
  - approval_note
source_refs:
- type: action
  ref: sop.equipment.block_process_progress
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: manual
method: HUMAN
url: manual://manual.equipment.approve_process_hold
auth:
  type: human_handoff
  approval_required: true
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
      const: manual_required or approval_required
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
  approved_by: $APPROVER_ID
example_response:
  ok: true
  status: manual_required
  manual_handoff:
    owner: 제조/품질 담당 조직
    doc_ref: boi:public:actions:manual:approve-process-hold
curl: 'curl -X POST http://localhost:8100/api/actions/invoke -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"manual.equipment.approve_process_hold","payload":{"equipment_id":"ETCH-VM-01"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: manual.equipment.approve_process_hold
  catalog_type: manual_task
  doc_ref: boi:public:actions:manual:approve-process-hold
health_check:
  type: manual
  check: 담당자와 승인권자 지정 여부 확인
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Checklist

- 공정 Hold 영향 범위를 확인한다.
- 품질/생산 승인권자 결재를 확보한다.
- 승인 전 system action은 dry-run 또는 approval_required 상태로만 둔다.
