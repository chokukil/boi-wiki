---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Quality System
description: 품질 데이터, trend, source data, 검사 결과 evidence를 제공하는 시스템 범주
tags: [Dictionary, QualitySystem, Evidence]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:quality-system
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Quality System
definition: BoI Wiki PoC에서 Response Trend, Source Data, 품질 이력, 검사 evidence를 제공하는 시스템 범주. 현재 실제 연결이 없으면 Universal Simulator가 SIMULATED evidence를 생성한다.
aliases: [품질 시스템, 품질 DB, 품질 데이터, Source Data]
domain: quality-evidence
examples:
  - 품질 시스템 미연결 시에도 Action Spec result contract에 맞춘 simulated evidence packet을 남긴다.
links:
  - /public/sop/direct-development-reporting.md
  - /public/actions/langflow/direct-development-quality-response-trend-simulate.md
related_terms: [Response Trend, SPC, Source Data]
maps_to_action_key: direct_development.quality_response_trend.simulate
source_refs:
  - {type: internal-doc, ref: "/public/sop/direct-development-reporting.md"}
---

# Summary

Quality System은 품질 evidence source를 가리키는 범주 term이다. 특정 사내 시스템명이 확정되지 않았으므로 tracked 문서에서는 "품질 시스템"으로 표현한다.

# BoI Usage

- [Response Trend 확인 시뮬레이션](/public/actions/langflow/direct-development-quality-response-trend-simulate.md)
- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)

# Related Dictionary Terms

- [Response Trend](response-trend.md)
- [SPC](spc.md)

# Citations

- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
