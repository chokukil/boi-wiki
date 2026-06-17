---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Spec / Rule 변경 요청
description: Spec 또는 Rule 변경 후보를 생성하는 고위험 API action
tags:
- ActionGateway
- API
- HighRisk
- EquipmentWorkflow
timestamp: 2026-06-17 12:11:00+09:00
boi_id: boi:public:actions:api:change-spec-rule
visibility: public
classification: internal
owner: 제조/품질 담당 조직
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.change_spec_rule
connector_kind: api
execution_mode: gateway
event_types:
- corrective_action.requested.v1
risk_level: high
approval_required: true
dry_run_default: true
requires_manual_action: manual.equipment.approve_spec_rule_change
payload_contract:
  required:
  - equipment_id
  - owner
  optional:
  - alarm_code
  - lot_id
result_contract:
  status: approval_required
  fields:
  - requested_change
  - equipment_id
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/poc/equipment/spec-rule-change
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
      const: invoked or approval_required
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
  dry_run: true
  approved_by: $APPROVER_ID
example_response:
  ok: true
  status: invoked
  action: sop.equipment.change_spec_rule
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://boi-api:8000/api/poc/equipment/spec-rule-change'' -H
  ''x-service-token: $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.change_spec_rule
  catalog_type: api
  doc_ref: boi:public:actions:api:change-spec-rule
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/api/poc/equipment/spec-rule-change' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

변경관리 승인 전에는 실제 변경을 수행하지 않는다.
