---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: Langflow 설비 SOP Stage 분석
description: 설비 SOP stage의 event payload와 prior action results를 받아 분석/가이드/조치 후보 초안을 생성하는 실행형 Langflow action
tags:
- Langflow
- EquipmentWorkflow
- SOP
timestamp: 2026-06-18 09:00:00+09:00
boi_id: boi:public:actions:langflow:stage-analysis
visibility: public
classification: internal
owner: AIX 확산 TF / 제조 PoC
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: langflow.equipment.stage_analysis
connector_kind: langflow
execution_mode: gateway
event_types:
- root_cause.analysis.requested.v1
- maintenance.guide.requested.v1
- corrective_action.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - event
  - payload
  - prior_results
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
- type: sop
  ref: boi:public:sop:equipment-abnormal-response
  uri: /public/sop/equipment-abnormal-response.md
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
      description: Event, SOP stage, prior action results, manual handoff requirements.
    input_type:
      const: chat
    output_type:
      const: chat
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
  input_value: |
    설비 이상 대응 SOP의 현재 stage 실행 기록을 한국어로 작성하세요.
    Prior Action Results:
    [{"action_key":"sop.equipment.request_raw_data","summary":"raw_data_ref=/mock/hyvis/raw-data/ETCH-VM-01/LOT-001"}]
  input_type: chat
  output_type: chat
example_response:
  ok: true
  status: langflow_invoked
  action: langflow.equipment.stage_analysis
  flow_name: BoI Equipment Stage Analysis Flow
  message: Raw Data와 장비 보전 가이드 기준상 원인 후보는 Response Chain 이상이며, manual review가 필요합니다.
curl: 'curl -X POST ''http://localhost:8100/api/actions/invoke'' -H ''x-service-token: $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"action_key":"langflow.equipment.stage_analysis","employee_id":"100001","event":{"event_type":"root_cause.analysis.requested.v1","trace_id":"trace-demo"},"payload":{"title":"원인 분석 요청 - ETCH-VM-01","equipment_id":"ETCH-VM-01","lot_id":"LOT-001","owner":"100001"},"prior_results":[{"action_key":"sop.equipment.request_raw_data","summary":"raw_data_ref=/mock/hyvis/raw-data/ETCH-VM-01/LOT-001"}]}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: langflow.equipment.stage_analysis
  catalog_type: langflow_run
  doc_ref: boi:public:actions:langflow:stage-analysis
  flow_name: BoI Equipment Stage Analysis Flow
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

이 action은 [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)의 stage 실행 중 호출된다. Action Gateway는 앞서 수행된 [Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md), [장비 보전 가이드 요청](/public/actions/api/request-maintenance-guide.md), manual handoff 후보를 `prior_results`로 누적한 뒤 Langflow `BoI Equipment Stage Analysis Flow`에 전달한다.

# Output Boundary

Langflow 출력은 자동 system action 지시가 아니라 generated Private BoI의 `# Analysis Draft` 섹션에 반영되는 초안이다. [공정 진행 금지 요청](/public/actions/api/block-process-progress.md), [Spec / Rule 변경 요청](/public/actions/api/change-spec-rule.md) 같은 고위험 action은 승인 필요 상태로만 기록한다.

# Citations

[1] `data/action_catalog/actions.yaml`
[2] [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
