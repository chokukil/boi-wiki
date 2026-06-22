---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Control Chart
description: 시간 순서의 품질/공정 데이터를 관리 한계와 함께 표시해 이상 신호를 보는 SPC 도구
tags:
- Dictionary
- Semiconductor
- spc
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:control-chart
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
term: Control Chart
definition: 시간 순서의 품질/공정 데이터를 관리 한계와 함께 표시해 이상 신호를 보는 SPC 도구
aliases:
- 관리도
- SPC chart
- Xbar chart
- R chart
- control limit chart
domain: spc
examples:
- Control Chart의 out-of-control signal은 trend anomaly event로 연결된다.
links:
- /public/event-types/trend.anomaly.detected.v1.md
related_terms:
- SPC
- Out-of-Control
- Response Trend
- Process Capability
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_event_type: trend.anomaly.detected.v1
---

# Summary

시간 순서의 품질/공정 데이터를 관리 한계와 함께 표시해 이상 신호를 보는 SPC 도구

# BoI Usage

- [trend.anomaly.detected.v1](/public/event-types/trend.anomaly.detected.v1.md)

# Agent Notes

- Agent는 `Control Chart` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [SPC](spc.md)
- [Out-of-Control](out-of-control.md)
- [Response Trend](response-trend.md)
- [Process Capability](process-capability.md)

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
