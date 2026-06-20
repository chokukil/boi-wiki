---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 협의체 메신저 공유 실행
description: 협의체 공유 preview를 실제 메신저에 발송하는 고위험 action. PoC에서는 승인 전 approval_required로만
  기록한다.
tags:
- DirectDevelopment
- ActionGateway
- webhook
timestamp: '2026-06-21T09:10:00+09:00'
boi_id: boi:public:actions:webhook:direct-development-messenger-share-publish
visibility: public
classification: internal
owner: AIX 확산 TF / Direct Development PoC
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: direct_development.messenger_share.publish
connector_kind: webhook
execution_mode: gateway
event_types:
- direct_development.share.requested.v1
risk_level: high
approval_required: true
dry_run_default: false
simulation: true
simulation_mode: langflow_universal
simulation_label: SIMULATED
simulated_system: 메신저
real_system_status: unavailable
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
  status: approval_required
  fields:
  - approval_required
  - simulation
  - simulation_notice
  simulation_required: true
source_refs:
- type: sop
  ref: boi:public:sop:direct-development-reporting
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http+webhook
method: POST
url: http://boi-api:8000/api/poc/direct-development/messenger-share
auth:
  type: service_token
  source: Action Gateway service token
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
      const: direct_development.messenger_share.publish
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
  action_key: direct_development.messenger_share.publish
  employee_id: '100001'
  event:
    event_type: direct_development.share.requested.v1
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
  status: approval_required
  action: direct_development.messenger_share.publish
  simulation: true
  simulation_label: SIMULATED
  result:
    message: 'SIMULATED: 실제 메신저 발송은 수행하지 않고 approval_required 상태만 기록합니다.'
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"direct_development.messenger_share.publish","employee_id":"100001","event":{"event_type":"direct_development.share.requested.v1","trace_id":"trace-direct-development-demo"},"payload":{"tech":"Tech-A","work_id":"1.10","owner":"100001"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: direct_development.messenger_share.publish
  catalog_type: webhook
  doc_ref: boi:public:actions:webhook:direct-development-messenger-share-publish
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

`direct_development.messenger_share.publish`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 실행 단계에 연결된 action spec이다.

# SIMULATED Boundary

이 action은 `SIMULATED` evidence 전용이다. 실제 시스템 호출은 수행하지 않으며, Action Gateway result에는 `simulation=true`, `real_system_connected=false`, `real_system_status=unavailable`을 남긴다.

# Citations

- Action catalog: `data/action_catalog/actions.yaml`
- SOP: `boi:public:sop:direct-development-reporting`
