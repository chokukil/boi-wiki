---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Langflow Reference Flow 호출 예시
description: Langflow reference flow에 event와 payload를 전달하는 connector 예시
tags:
- Langflow
- Webhook
- ReferenceFlow
timestamp: 2026-06-17 12:14:00+09:00
boi_id: boi:public:actions:langflow:reference-flow
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: langflow.boi.reference_flow
connector_kind: langflow
execution_mode: gateway
event_types:
- meeting.closed.v1
- action.created.v1
- report.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event
  - payload
  optional:
  - flow_id
result_contract:
  status: invoked
  fields:
  - http_status
  - response
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://langflow:7860/api/v1/webhook/{flow_id}
auth:
  type: header
  header: x-api-key
  value: $LANGFLOW_API_KEY
headers:
  Content-Type: application/json
  x-api-key: $LANGFLOW_API_KEY
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
    event_type: meeting.closed.v1
  dry_run: true
  approved_by: ''
example_response:
  ok: true
  status: invoked
  action: langflow.boi.reference_flow
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://langflow:7860/api/v1/webhook/{flow_id}'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: langflow.boi.reference_flow
  catalog_type: langflow_webhook
  doc_ref: boi:public:actions:langflow:reference-flow
health_check:
  type: http
  command: curl -fsS 'http://langflow:7860/api/v1/webhook/{flow_id}' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

Gemma OpenAI-compatible LLM 설정을 가진 Langflow reference flow와 연결하는 예시다.
