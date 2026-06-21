---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 단면검사 필요 여부 판단
description: Map View와 Trend 근거를 보고 사람이 단면검사 필요 여부를 판단하는 manual action
tags:
- DirectDevelopment
- ActionGateway
- manual
timestamp: '2026-06-21T09:10:00+09:00'
boi_id: boi:public:actions:manual:direct-development-decide-cross-section
visibility: public
classification: internal
owner: 공정 담당자 / Direct Development PoC
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: manual.direct_development.decide_cross_section
connector_kind: manual
execution_mode: human
event_types:
- direct_development.cross_section.decision_required.v1
risk_level: medium
approval_required: false
dry_run_default: true
simulation: false
payload_contract:
  required:
  - event
  - payload
  - assignee
  optional:
  - prior_results
  - source_refs
  - simulation_reason
  - approved_by
result_contract:
  status: manual_required
  fields:
  - owner
  - checklist
  - manual_required
  simulation_required: false
evidence_requirements:
- evidence_key: response_trend
  source_action: direct_development.quality_response_trend.simulate
  required_fields:
  - trend_status
  simulated_allowed: true
- evidence_key: map_view
  source_action: direct_development.map_view.simulate
  required_fields:
  - map_pattern_summary
  simulated_allowed: true
- evidence_key: cross_section_decision_rule
  source_action: manual.direct_development.decide_cross_section
  required_fields:
  - decision_rule
  - manual_handoff
  - next_event
  simulated_allowed: true
source_refs:
- type: sop
  ref: boi:public:sop:direct-development-reporting
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: manual
method: HUMAN
url: manual://manual.direct_development.decide_cross_section
auth:
  type: human_handoff
  approval_required: false
headers:
  x-service-token: $SERVICE_TOKEN
  Content-Type: application/json
request_schema:
  type: object
  required:
  - action_key
  - employee_id
  - event
  - payload
  properties:
    action_key:
      const: manual.direct_development.decide_cross_section
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
  action_key: manual.direct_development.decide_cross_section
  employee_id: '100001'
  event:
    event_type: direct_development.cross_section.decision_required.v1
    trace_id: trace-direct-development-demo
  payload:
    product: Product-A
    tech: Tech-A
    work_id: '1.10'
    lot_id: LOT-DD-001
    wafer_id: WF-DD-001
    owner: '100001'
  dry_run: true
example_response:
  ok: true
  status: manual_required
  action: manual.direct_development.decide_cross_section
  simulation: false
  simulation_label: null
  result:
    message: Action Gateway result recorded.
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"manual.direct_development.decide_cross_section","employee_id":"100001","event":{"event_type":"direct_development.cross_section.decision_required.v1","trace_id":"trace-direct-development-demo"},"payload":{"tech":"Tech-A","work_id":"1.10","owner":"100001"}}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: manual.direct_development.decide_cross_section
  catalog_type: manual_task
  doc_ref: boi:public:actions:manual:direct-development-decide-cross-section
  flow_name: null
  resolve_latest: null
health_check:
  type: manual
  check: 담당자와 승인권자 지정 여부 확인
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
- This public redacted spec uses Tech-A and generic system names only.
---

# Usage

`manual.direct_development.decide_cross_section`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 실행 단계에 연결된 action spec이다.

# Checklist

- Response Trend와 Map View 근거 확인
- 단면검사 필요 여부 판단
- 완료 시 direct_development.cross_section.requested.v1 이벤트 발행

# Prerequisite Evidence

이 manual action은 단순히 "사람 판단 필요"만 남기면 충분하지 않다. 판단 전에는 아래 evidence packet이 있어야 한다.

| Evidence | Source Action | Required Field | Simulation Policy |
|---|---|---|---|
| Response Trend | [Response Trend 확인 시뮬레이션](/public/actions/langflow/direct-development-quality-response-trend-simulate.md) | `trend_status` | 실제 품질 시스템이 없으면 `SIMULATED prerequisite`로 생성 가능 |
| Map View | [Map View 확인 시뮬레이션](/public/actions/langflow/direct-development-map-view-simulate.md) | `map_pattern_summary` | 실제 Map 분석 시스템이 없으면 `SIMULATED prerequisite`로 생성 가능 |
| 판단 기준 | 이 manual action spec | `decision_rule`, `manual_handoff`, `next_event` | SOP/action spec 근거로 생성 가능 |

`BoI Simulation Agent`는 같은 `trace_id`의 action log와 generated BoI를 먼저 찾고, 누락된 전제는 위 계약에 맞춰 `provenance=simulated_prerequisite` evidence packet으로 만든다. 이는 실제 데이터가 있다는 의미가 아니라, public SOP와 action spec에 근거한 dry-run evidence다.

# Citations

- Action catalog: `data/action_catalog/actions.yaml`
- SOP: `boi:public:sop:direct-development-reporting`
