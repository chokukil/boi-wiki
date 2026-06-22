---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 단면검사 의뢰 시뮬레이션
description: 단면 검사 시스템 의뢰 절차를 BoI Universal Action Simulator Flow로 시뮬레이션한다.
tags:
- DirectDevelopment
- ActionGateway
- langflow
timestamp: '2026-06-21T09:10:00+09:00'
boi_id: boi:public:actions:langflow:direct-development-cross-section-request-simulate
visibility: public
classification: internal
owner: AIX 확산 TF / Direct Development PoC
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: direct_development.cross_section_request.simulate
connector_kind: langflow
execution_mode: gateway
event_types:
- direct_development.cross_section.requested.v1
risk_level: medium
approval_required: false
dry_run_default: false
simulation: true
simulation_mode: langflow_universal
simulation_label: SIMULATED
simulated_system: 단면 검사 시스템
real_system_status: unavailable
payload_contract:
  required:
  - event
  - payload
  - expected_result_contract
  optional:
  - prior_results
  - source_refs
  - simulation_reason
  - approved_by
result_contract:
  status: langflow_invoked
  fields:
  - flow_id
  - flow_endpoint_name
  - message
  - response
  - simulation
  simulation_required: true
source_refs:
- type: sop
  ref: boi:public:sop:direct-development-reporting
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
  source: Langflow auto-login token inside trusted PoC network
headers:
  Content-Type: application/json
  Authorization: Bearer $LANGFLOW_AUTO_LOGIN_TOKEN
request_schema:
  type: object
  required:
  - action_key
  - employee_id
  - event
  - payload
  properties:
    action_key:
      const: direct_development.cross_section_request.simulate
    employee_id:
      type: string
    event:
      type: object
    payload:
      type: object
    dry_run:
      type: boolean
    approved_by:
      type: string
response_schema:
  type: object
  required:
  - ok
  - status
  - request_id
  properties:
    ok:
      type: boolean
    status:
      type: string
    request_id:
      type: string
    result:
      type: object
    simulation:
      type: boolean
example_request:
  action_key: direct_development.cross_section_request.simulate
  employee_id: '100001'
  event:
    event_type: direct_development.cross_section.requested.v1
    trace_id: trace-direct-development-demo
  payload:
    product: Product-A
    tech: Tech-A
    work_id: '1.10'
    lot_id: LOT-DD-001
    wafer_id: WF-DD-001
    owner: '100001'
  dry_run: false
example_response:
  ok: true
  status: langflow_invoked
  action: direct_development.cross_section_request.simulate
  simulation: true
  simulation_label: SIMULATED
  result:
    message: 'SIMULATED: 실제 단면 검사 시스템 호출이 아니라 BoI Universal Action Simulator Flow가
      생성한 PoC 결과입니다.'
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"direct_development.cross_section_request.simulate","employee_id":"100001","event":{"event_type":"direct_development.cross_section.requested.v1","trace_id":"trace-direct-development-demo"},"payload":{"tech":"Tech-A","work_id":"1.10","owner":"100001"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: direct_development.cross_section_request.simulate
  catalog_type: langflow_run
  doc_ref: boi:public:actions:langflow:direct-development-cross-section-request-simulate
  flow_name: BoI Universal Action Simulator Flow
  resolve_latest: true
health_check:
  type: script
  command: python scripts/setup_langflow_reference_flows.py --auth-mode api-key
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
- This public redacted spec uses Tech-A and generic system names only.
---

# Usage

`direct_development.cross_section_request.simulate`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 실행 단계에 연결된 action spec이다.

# SIMULATED Boundary

이 action은 `SIMULATED` evidence 전용이다. 실제 시스템 호출은 수행하지 않으며, Action Gateway result에는 `simulation=true`, `real_system_connected=false`, `real_system_status=unavailable`을 남긴다.

Langflow Universal Simulator Agent가 Action Spec, Event Type, SOP stage, prior result를 seed로 BoI Wiki tool loop를 실행하고 `agent_iterations`, `tool_calls`, `retrieval_trace`, `used_docs`, `coverage_score`, `missing_context`를 action log에 남긴다. LLM은 Agent 내부 reasoning engine일 뿐이며, 공식 결과는 Agent output이다.

# Citations

- Action catalog: `data/action_catalog/actions.yaml`
- SOP: `boi:public:sop:direct-development-reporting`
