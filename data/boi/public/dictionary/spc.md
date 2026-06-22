---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: SPC
description: 통계적 공정 관리와 관리 한계 기반 이상 감시
tags: [Dictionary, Semiconductor, SPC, Quality]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:spc
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: SPC
definition: Statistical Process Control. 공정 지표를 통계적으로 관리하고 관리 한계를 벗어나는 변동을 탐지하는 품질/공정 관리 방법.
aliases: [Statistical Process Control, 통계적 공정 관리, 관리도, 관리 한계, control chart]
domain: process-quality
examples:
  - SPC trend가 관리 한계를 벗어나면 trend.anomaly.detected.v1 event 후보가 된다.
links:
  - /public/event-types/trend.anomaly.detected.v1.md
  - /public/actions/api/request-trend-history.md
related_terms: [FDC, Response Trend, Spec / Rule]
maps_to_event_type: trend.anomaly.detected.v1
maps_to_action_key: sop.equipment.request_trend_history
source_refs:
  - {type: external-standard, ref: "SEMI compilation of terms", url: "https://www.semi.org/sites/semi.org/files/2020-02/CompilationTerms1218_0.pdf"}
---

# Summary

SPC는 공정 지표를 통계적으로 관리하는 방법이다. BoI Wiki에서는 Trend 이상, Spec/Rule 변경, 품질 시스템 evidence를 해석하는데 사용한다.

# BoI Usage

- [Trend / 이력 확인 요청](/public/actions/api/request-trend-history.md)
- [Trend 이상 감지](/public/event-types/trend.anomaly.detected.v1.md)

# Citations

- [SEMI International Standards: Compilation of Terms](https://www.semi.org/sites/semi.org/files/2020-02/CompilationTerms1218_0.pdf)
