---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Deposition
description: wafer 표면에 원하는 물질의 얇은 막을 형성하는 공정 범주
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:deposition
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
term: Deposition
definition: wafer 표면에 원하는 물질의 얇은 막을 형성하는 공정 범주
aliases:
- 증착
- thin film deposition
- 박막 증착
domain: process-module
examples:
- Deposition rate 또는 film thickness trend 이상은 FDC/SPC로 감지한다.
links:
- /public/event-types/trend.anomaly.detected.v1.md
related_terms:
- CVD
- PVD
- ALD
- Metrology
- Response Trend
source_refs:
- type: external-reference
  ref: Lam Research Deposition Essentials
  url: https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true
- type: external-reference
  ref: Lam Research Our Processes
  url: https://www.lamresearch.com/products/our-processes/
maps_to_event_type: trend.anomaly.detected.v1
---

# Summary

wafer 표면에 원하는 물질의 얇은 막을 형성하는 공정 범주

# BoI Usage

- [trend.anomaly.detected.v1](/public/event-types/trend.anomaly.detected.v1.md)

# Agent Notes

- Agent는 `Deposition` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [CVD](cvd.md)
- [PVD](pvd.md)
- [ALD](ald.md)
- [Metrology](metrology.md)
- [Response Trend](response-trend.md)

# Citations

- [Lam Research Deposition Essentials](https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true)
- [Lam Research Our Processes](https://www.lamresearch.com/products/our-processes/)
