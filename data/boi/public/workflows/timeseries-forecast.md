---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/workflow-definition
title: Timeseries Forecast WorkflowDefinition
description: TimesFM MCP 기반 시계열 예측을 Event-native workflow에서 선택적으로 사용하는 WorkflowDefinition
tags: [WorkflowDefinition, Timeseries, MCP, Forecast]
timestamp: 2026-06-27T11:30:00+09:00
boi_id: boi:public:workflows:timeseries-forecast
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
workflow_definition_key: timeseries-forecast
workflow_engine: event_native
entry_events:
  - timeseries.forecast.requested.v1
emitted_events:
  - timeseries.forecast.completed.v1
action_refs:
  - mcp.timesfm.forecast
event_skill_refs:
  - event.workflow_trigger
action_skill_refs:
  - timeseries.forecast
source_refs:
  - type: catalog
    ref: data/workflow_catalog/workflows.yaml#timeseries-forecast
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

Timeseries Forecast WorkflowDefinition는 시계열 예측이 명시적으로 필요한 업무에서 `mcp.timesfm.forecast` Action을 사용할 수 있게 한다. TimesFM MCP endpoint는 tracked 문서에 고정하지 않고 runtime env로 주입한다.

# Policy

- 모든 forecast 결과는 model/tool, horizon, confidence interval, limitations를 함께 기록한다.
- 모든 trend 이벤트에 자동 실행하지 않는다.
- `payload.forecast_required=true` 또는 WorkflowDefinition에서 권장된 경우에만 실행 후보가 된다.

# Related

- [TimesFM Forecast Action](/public/actions/mcp/timesfm-forecast.md)
- [WorkflowDefinition Registration Guide](/public/boi-wiki-manual/workflows/workflow-definition-registration-guide.md)
