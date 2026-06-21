---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: TimesFM 시계열 예측 MCP Action
description: TimesFM MCP 서버를 통해 업무 시계열 데이터를 forecast하는 opt-in action 명세
tags: [MCP, TimesFM, Forecast, TimeSeries, ActionGateway]
timestamp: 2026-06-22T09:30:00+09:00
boi_id: boi:public:actions:mcp:timesfm-forecast
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: mcp.timesfm.forecast
connector_kind: mcp
execution_mode: gateway
event_types:
  - timeseries.forecast.requested.v1
  - trend.anomaly.detected.v1
  - direct_development.result_check.requested.v1
  - direct_development.fab_trend.compare_requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
    - series
    - horizon
    - frequency
  optional:
    - timestamp_column
    - target_column
    - group_id
    - confidence_level
    - context
result_contract:
  status: mcp_invoked
  fields:
    - response
    - forecast
    - horizon
    - frequency
    - limitations
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: mcp-over-sse
auth:
  type: deployment_env
  source: TIMESFM_MCP_URL
request_schema:
  type: object
  required: [series, horizon, frequency]
  properties:
    series:
      type: array
      description: 시간 순서대로 정렬된 numeric series 또는 timestamp/value object 배열
    horizon:
      type: integer
      minimum: 1
    frequency:
      type: string
      description: D, H, min 같은 모델 입력 주기
    timestamp_column:
      type: string
    target_column:
      type: string
    group_id:
      type: string
    confidence_level:
      type: number
    context:
      type: object
response_schema:
  type: object
  required: [ok, status, response]
  properties:
    ok:
      type: boolean
    status:
      enum: [mcp_invoked, mcp_unavailable]
    response:
      type: object
    forecast:
      type: array
    limitations:
      type: array
example_request:
  series:
    - {timestamp: "2026-06-22T09:00:00+09:00", value: 101.2}
    - {timestamp: "2026-06-22T10:00:00+09:00", value: 102.4}
    - {timestamp: "2026-06-22T11:00:00+09:00", value: 104.1}
  horizon: 3
  frequency: H
  target_column: value
  confidence_level: 0.9
  context:
    business_reason: 설비 trend 이상 가능성 사전 확인
example_response:
  ok: true
  status: mcp_invoked
  tool: forecast
  response:
    forecast:
      - {step: 1, value: 104.8}
      - {step: 2, value: 105.1}
      - {step: 3, value: 105.4}
    model: TimesFM
action_gateway_mapping:
  invoke_url: http://action-gateway:8100/api/actions/invoke
  action_key: mcp.timesfm.forecast
  catalog_type: mcp_tool
  doc_ref: boi:public:actions:mcp:timesfm-forecast
health_check:
  type: mcp_sse
  command: python scripts/check_timesfm_mcp.py --url "$TIMESFM_MCP_URL" --list-tools
security_notes:
  - 실제 TimesFM MCP URL은 Git에 커밋하지 않고 runtime .env에만 둔다.
  - Action Gateway allowlist에 등록된 host만 호출한다.
  - forecast 결과는 의사결정 근거 중 하나이며, 고위험 조치는 별도 승인 action을 따른다.
mcp_server:
  name: timesfm
  transport: sse
  url: ${TIMESFM_MCP_URL}
tool_name: forecast
transport: sse
input_schema:
  type: object
  required: [series, horizon, frequency]
  properties:
    series:
      type: array
    horizon:
      type: integer
    frequency:
      type: string
    timestamp_column:
      type: string
    target_column:
      type: string
    group_id:
      type: string
    confidence_level:
      type: number
    context:
      type: object
output_schema:
  type: object
  required: [forecast]
  properties:
    forecast:
      type: array
    model:
      type: string
    confidence_interval:
      type: array
    limitations:
      type: array
example_tool_call:
  server:
    name: timesfm
    transport: sse
    url: ${TIMESFM_MCP_URL}
  tool: forecast
  arguments:
    series: [101.2, 102.4, 104.1, 103.8]
    horizon: 3
    frequency: H
    confidence_level: 0.9
---

# Summary

이 action은 [시계열 예측 요청](/public/event-types/timeseries.forecast.requested.v1.md) 또는 forecast가 명시적으로 필요한 SOP stage에서 TimesFM MCP tool을 호출한다.

# Operating Rules

- 기본은 opt-in이다. 기존 Trend event 전체에 자동 실행하지 않는다.
- `TIMESFM_MCP_URL`과 allowlist는 deployment `.env`에서만 관리한다.
- Action Raw와 Generated BoI에는 forecast horizon, 주기, 예측 sample, 한계, 사용 tool을 남긴다.

# Citations

[1] Action Catalog: `data/action_catalog/actions.yaml`
