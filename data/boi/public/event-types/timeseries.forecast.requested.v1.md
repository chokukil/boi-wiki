---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: 시계열 예측 요청
description: 업무 시계열 데이터에 대해 TimesFM 기반 forecast가 명시적으로 필요한 이벤트
tags: [EventType, TimesFM, Forecast, TimeSeries, MCP]
timestamp: 2026-06-22T09:35:00+09:00
boi_id: boi:public:event-types:timeseries.forecast.requested.v1
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: event_catalog
    ref: data/event_catalog/event_types.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
event_type: timeseries.forecast.requested.v1
---

# Summary

`timeseries.forecast.requested.v1`는 업무 시계열 데이터에 대해 [TimesFM 시계열 예측 MCP Action](/public/actions/mcp/timesfm-forecast.md)을 명시적으로 호출해야 하는 시점이다.

# Payload

- `series`: 시간 순서대로 정렬된 값 또는 timestamp/value object 배열
- `horizon`: 예측 step 수
- `frequency`: 입력 주기
- `context`: 예측 목적, 설비/공정/업무 맥락

# Recommended Actions

- [TimesFM 시계열 예측 MCP Action](/public/actions/mcp/timesfm-forecast.md)

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
