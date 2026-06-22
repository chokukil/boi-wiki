---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 품질 시스템 Response Trend 확인 시뮬레이션
description: 품질 시스템 Response Trend 확인을 BoI Universal Simulator Agent로 시뮬레이션한다.
  실제 품질 시스템 호출이 아니다.
tags:
- ActionGateway
- Langflow
- EquipmentWorkflow
timestamp: 2026-06-17 12:06:00+09:00
boi_id: boi:public:actions:api:request-trend-history
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: sop.equipment.request_trend_history
connector_kind: langflow
execution_mode: gateway
event_types:
- equipment.alarm.raised.v1
- trend.anomaly.detected.v1
- root_cause.analysis.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
simulation: true
simulation_mode: langflow_universal
simulation_label: SIMULATED
simulated_system: 품질 시스템
real_system_status: unavailable
payload_contract:
  required:
  - equipment_id
  optional:
  - lot_id
  - wafer_id
  - alarm_code
result_contract:
  status: langflow_invoked
  fields:
  - source_system
  - response_series
  - frequency
  - time_range
  - trend_status
  - anomaly_basis
  - series_ref
  - real_system_connected
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: langflow
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
      const: langflow_invoked
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
    event_type: equipment.alarm.raised.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: langflow_invoked
  action: sop.equipment.request_trend_history
  simulation: true
  simulation_label: SIMULATED
  simulated_system: 품질 시스템
  real_system_connected: false
  result:
    source_system: quality_system
    trend_status: simulated_response_trend_anomaly_detected
    anomaly_basis: SOP/action contract based simulation
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"sop.equipment.request_trend_history","employee_id":"100001","event":{"event_type":"equipment.alarm.raised.v1","trace_id":"trace-equipment-demo"},"payload":{"equipment_id":"ETCH-VM-01","lot_id":"LOT-POC-001","wafer_id":"WF-POC-001"},"dry_run":false}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: sop.equipment.request_trend_history
  catalog_type: langflow_run
  doc_ref: boi:public:actions:api:request-trend-history
  flow_name: BoI Universal Action Simulator Flow
  resolve_latest: true
health_check:
  type: script
  command: python scripts/setup_langflow_reference_flows.py --auth-mode api-key --summary
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
---

# Usage

이상 감지와 원인 분석 단계에서 품질 시스템 Response Trend 이상 여부를 확인한다. 현재 PoC에서는 실제 품질 시스템 connector가 없으므로, 이 action은 `BoI Universal Simulator Agent`가 SOP와 action contract를 근거로 `SIMULATED` evidence packet을 생성한다.

# SIMULATED Boundary

이 action은 실제 품질 시스템 호출이 아니다. Action Raw와 Generated BoI에는 `simulation=true`, `real_system_connected=false`, `simulated_system=품질 시스템`이 남아야 한다.
