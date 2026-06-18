---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Langflow Reference Flow 호출
description: 최신 Langflow BoI Reference Flow를 resolve해 OpenAI-compatible Gemma LLM으로 이벤트 맥락 요약을 생성하는 실행형 connector
tags:
- Langflow
- RunAPI
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
- equipment.alarm.raised.v1
- report.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event
  - payload
  optional:
  - flow_name
  - resolve_latest
result_contract:
  status: langflow_invoked
  fields:
  - http_status
  - flow_id
  - flow_endpoint_name
  - message
  - response
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://langflow:7860/api/v1/run/{flow_id}
auth:
  type: bearer
  source: Langflow auto_login token inside trusted PoC network
headers:
  Content-Type: application/json
  Authorization: Bearer $LANGFLOW_AUTO_LOGIN_TOKEN
request_schema:
  type: object
  required:
  - input_value
  - input_type
  - output_type
  properties:
    input_value:
      type: string
    input_type:
      const: chat
    output_type:
      const: chat
    flow_name:
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
      const: langflow_invoked
    request_id:
      type: string
    flow_id:
      type: string
    message:
      type: string
example_request:
  input_value: BoI Wiki Event를 분석해 Private BoI 초안 요약을 한국어로 작성하세요.
  input_type: chat
  output_type: chat
example_response:
  ok: true
  status: langflow_invoked
  action: langflow.boi.reference_flow
  flow_id: 07b9f3e5-a90b-4a61-8996-a10aa8df2895
  message: Langflow를 통한 업무 맥락 자산화와 Event Broker/Action Gateway의 연동을 검증합니다.
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"langflow.boi.reference_flow","employee_id":"100001","event":{"event_type":"equipment.alarm.raised.v1","trace_id":"trace-demo","payload":{"title":"Response Chain 이상 Alarm 발생","equipment_id":"ETCH-VM-01","owner":"100001"}},"payload":{"title":"Response Chain 이상 Alarm 발생","equipment_id":"ETCH-VM-01","owner":"100001"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: langflow.boi.reference_flow
  catalog_type: langflow_run
  doc_ref: boi:public:actions:langflow:reference-flow
  flow_name: BoI Reference Flow
  resolve_latest: true
  require_marker: BoI Wiki Writer
health_check:
  type: http
  command: python scripts/setup_langflow_reference_flows.py
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

Gemma OpenAI-compatible LLM 설정과 BoI custom component chain을 가진 Langflow reference flow와 실제로 연결되는 실행형 action이다. Action Gateway는 Langflow `auto_login`으로 flow 목록을 읽고, `BoI Reference Flow` 이름이며 `BoI Wiki Writer` marker를 포함한 최신 정상 flow를 찾아 `/api/v1/run/{flow_id}`로 호출한다.
