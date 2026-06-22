---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Out-of-Control
description: SPC/control chart에서 통계적 관리 상태를 벗어난 신호 또는 조건
tags:
- Dictionary
- Semiconductor
- spc
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:out-of-control
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
term: Out-of-Control
definition: SPC/control chart에서 통계적 관리 상태를 벗어난 신호 또는 조건
aliases:
- OOC
- 관리이탈
- out of control
- control limit violation
domain: spc
examples:
- OOC 조건은 trend anomaly나 corrective action requested event의 trigger가 될 수 있다.
links:
- /public/event-types/trend.anomaly.detected.v1.md
- /public/event-types/corrective_action.requested.v1.md
related_terms:
- SPC
- Control Chart
- Trend 이상 감지
- Corrective Action
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_event_type: trend.anomaly.detected.v1
---

# Summary

SPC/control chart에서 통계적 관리 상태를 벗어난 신호 또는 조건

# BoI Usage

- [trend.anomaly.detected.v1](/public/event-types/trend.anomaly.detected.v1.md)
- [corrective_action.requested.v1](/public/event-types/corrective_action.requested.v1.md)

# Agent Notes

- Agent는 `Out-of-Control` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
