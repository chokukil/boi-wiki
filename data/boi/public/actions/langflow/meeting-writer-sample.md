---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Langflow 회의 BoI Writer Flow 호출 예시
description: Langflow Webhook Flow를 연결하는 connector 예시
tags:
- Langflow
- Webhook
- BoIWriter
timestamp: 2026-06-17 12:13:00+09:00
boi_id: boi:public:actions:langflow:meeting-writer-sample
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: langflow.meeting_writer.sample
connector_kind: langflow
execution_mode: gateway
event_types:
- meeting.closed.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - langflow_flow_id
  optional:
  - payload
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
  action: langflow.meeting_writer.sample
  result:
    message: PoC endpoint invoked
curl: 'curl -X POST ''http://langflow:7860/api/v1/webhook/{flow_id}'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"payload":{"equipment_id":"ETCH-VM-01"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: langflow.meeting_writer.sample
  catalog_type: langflow_webhook
  doc_ref: boi:public:actions:langflow:meeting-writer-sample
health_check:
  type: http
  command: curl -fsS 'http://langflow:7860/api/v1/webhook/{flow_id}' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

Flow ID를 준비하고 catalog에서 enabled=true로 바꾸면 Event Router가 호출할 수 있다.
