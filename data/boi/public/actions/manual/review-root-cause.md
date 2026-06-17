---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 원인 후보 검토 및 판단
description: 원인 분석 Agent가 제시한 후보와 데이터 근거를 사람이 검토하는 manual action
tags:
- Manual
- EquipmentWorkflow
- RootCause
timestamp: 2026-06-17 12:18:00+09:00
boi_id: boi:public:actions:manual:review-root-cause
visibility: public
classification: internal
owner: AIX 확산 TF / 제조 PoC
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.equipment.review_root_cause
connector_kind: manual
execution_mode: human
event_types:
- root_cause.analysis.requested.v1
- maintenance.guide.requested.v1
risk_level: medium
approval_required: false
dry_run_default: true
payload_contract:
  required:
  - equipment_id
  - owner
  optional:
  - raw_data_ref
  - source_data_ref
  - guide_boi_ref
result_contract:
  status: manual_required
  fields:
  - reviewer
  - accepted_cause
  - rejected_causes
  - note
source_refs:
- type: sop
  ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: manual
method: HUMAN
url: manual://manual.equipment.review_root_cause
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
    event_type: root_cause.analysis.requested.v1
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: manual_required
  manual_handoff:
    owner: AIX 확산 TF / 제조 PoC
    doc_ref: boi:public:actions:manual:review-root-cause
curl: 'curl -X POST http://localhost:8100/api/actions/invoke -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"manual.equipment.review_root_cause","payload":{"equipment_id":"ETCH-VM-01"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: manual.equipment.review_root_cause
  catalog_type: manual_task
  doc_ref: boi:public:actions:manual:review-root-cause
health_check:
  type: manual
  check: 담당자와 승인권자 지정 여부 확인
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Checklist

- Raw/Source Data 근거를 확인한다.
- 장비 이상 여부와 공정 영향 가능성을 판단한다.
- 이상 조치 단계로 넘길 판단 근거를 남긴다.
