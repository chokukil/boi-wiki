---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Reporting 요청 이벤트 발행
description: 비교 Trend 확인 후 직개발 결과 Reporting stage를 시작하는 이벤트를 발행한다.
tags:
- DirectDevelopment
- ActionGateway
- event_broker
timestamp: '2026-06-21T09:10:00+09:00'
boi_id: boi:public:actions:event-broker:direct-development-create-reporting-event
visibility: public
classification: internal
owner: AIX 확산 TF / Direct Development PoC
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: direct_development.create_reporting_event
connector_kind: event_broker
execution_mode: gateway
event_types:
- direct_development.fab_trend.compare_requested.v1
risk_level: low
approval_required: false
dry_run_default: false
simulation: false
payload_contract:
  required:
  - event
  - payload
  optional:
  - prior_results
  - source_refs
  - simulation_reason
  - approved_by
result_contract:
  status: event_published
  fields:
  - event_id
  - event_type
  - trace_id
  simulation_required: false
source_refs:
- type: sop
  ref: boi:public:sop:direct-development-reporting
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http+event-broker
method: POST
url: http://boi-api:8000/api/events/publish
auth:
  type: service_network
  source: Action Gateway trusted service call
headers:
  Content-Type: application/json
  x-service-token: $SERVICE_TOKEN
request_schema:
  type: object
  required:
  - action_key
  - employee_id
  - event
  - payload
  properties:
    action_key:
      const: direct_development.create_reporting_event
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
  action_key: direct_development.create_reporting_event
  employee_id: '100001'
  event:
    event_type: direct_development.fab_trend.compare_requested.v1
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
  status: event_published
  action: direct_development.create_reporting_event
  simulation: false
  simulation_label: null
  result:
    message: Action Gateway result recorded.
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"direct_development.create_reporting_event","employee_id":"100001","event":{"event_type":"direct_development.fab_trend.compare_requested.v1","trace_id":"trace-direct-development-demo"},"payload":{"tech":"Tech-A","work_id":"1.10","owner":"100001"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: direct_development.create_reporting_event
  catalog_type: event_publish
  doc_ref: boi:public:actions:event-broker:direct-development-create-reporting-event
  flow_name: null
  resolve_latest: null
health_check:
  type: http
  command: curl -fsS 'http://localhost:8000/health'
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
- This public redacted spec uses Tech-A and generic system names only.
---

# Usage

`direct_development.create_reporting_event`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 실행 단계에 연결된 action spec이다.

# Citations

- Action catalog: `data/action_catalog/actions.yaml`
- SOP: `boi:public:sop:direct-development-reporting`
