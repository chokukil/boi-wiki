---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: TimesFM
description: 범용 시계열 예측 모델 또는 이를 제공하는 MCP forecast action
tags:
- Dictionary
- Semiconductor
- ai-analytics
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:timesfm
visibility: public
classification: internal
owner: aix-tf
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
review:
  reviewer: dictionary-curator
  review_status: reviewed
term: TimesFM
definition: 범용 시계열 예측 모델 또는 이를 제공하는 MCP forecast action
aliases:
- TimesFM MCP
- time series foundation model
- forecast MCP
- 시계열 foundation model
domain: ai-analytics
examples:
- TimesFM action은 trend forecast가 명시적으로 필요할 때만 opt-in으로 호출한다.
links:
- /public/actions/mcp/timesfm-forecast.md
- /public/event-types/timeseries.forecast.requested.v1.md
related_terms:
- Time Series Forecast
- Response Trend
- Action Gateway
- MCP
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_event_type: timeseries.forecast.requested.v1
maps_to_action_key: mcp.timesfm.forecast
---

# Summary

범용 시계열 예측 모델 또는 이를 제공하는 MCP forecast action

# BoI Usage

- [timesfm-forecast](/public/actions/mcp/timesfm-forecast.md)
- [timeseries.forecast.requested.v1](/public/event-types/timeseries.forecast.requested.v1.md)

# Agent Notes

- Agent는 `TimesFM` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
