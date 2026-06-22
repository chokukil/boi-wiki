---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Time Series Forecast
description: 시간 순서 데이터의 미래 값을 horizon 기준으로 예측하는 분석 작업
tags:
- Dictionary
- Semiconductor
- ai-analytics
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:time-series-forecast
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
term: Time Series Forecast
definition: 시간 순서 데이터의 미래 값을 horizon 기준으로 예측하는 분석 작업
aliases:
- 시계열 예측
- forecast
- trend forecast
- 예측 모델
domain: ai-analytics
examples:
- Response Trend나 품질 trend가 있을 때 TimesFM MCP forecast action 후보로 연결한다.
links:
- /public/actions/mcp/timesfm-forecast.md
- /public/event-types/timeseries.forecast.requested.v1.md
related_terms:
- Response Trend
- TimesFM
- SPC
- Control Chart
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_event_type: timeseries.forecast.requested.v1
maps_to_action_key: mcp.timesfm.forecast
---

# Summary

시간 순서 데이터의 미래 값을 horizon 기준으로 예측하는 분석 작업

# BoI Usage

- [timesfm-forecast](/public/actions/mcp/timesfm-forecast.md)
- [timeseries.forecast.requested.v1](/public/event-types/timeseries.forecast.requested.v1.md)

# Agent Notes

- Agent는 `Time Series Forecast` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Response Trend](response-trend.md)
- [TimesFM](timesfm.md)
- [SPC](spc.md)
- [Control Chart](control-chart.md)

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
