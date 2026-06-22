---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Response Trend
description: 품질 시스템에서 직개발 결과 또는 설비 반응 변화를 시간 흐름으로 확인하는 evidence
tags: [Dictionary, QualitySystem, Trend, DirectDevelopment]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:response-trend
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Response Trend
definition: 품질 시스템에서 직개발 결과나 설비 response 변화를 trend로 확인하는 evidence. 실제 품질 시스템이 연결되지 않은 PoC에서는 Universal Simulator가 SIMULATED evidence packet으로 생성한다.
aliases: [Response, Response 데이터, 응답 Trend, 응답 트렌드, 품질 Trend, 품질 시스템 Trend]
domain: direct-development-workflow
examples:
  - Response Trend가 이상 패턴이면 Map View 확인과 단면검사 판단으로 이어진다.
links:
  - /public/sop/direct-development-reporting.md
  - /public/actions/langflow/direct-development-quality-response-trend-simulate.md
related_terms: [Quality System, Map View, Cross-section Inspection]
maps_to_event_type: direct_development.result_check.requested.v1
maps_to_action_key: direct_development.quality_response_trend.simulate
maps_to_sop: boi:public:sop:direct-development-reporting
source_refs:
  - {type: internal-doc, ref: "/public/sop/direct-development-reporting.md"}
---

# Summary

Response Trend는 직개발 결과 확인 workflow의 첫 evidence다. 품질 시스템 실제 연동 전에는 [Response Trend 확인 시뮬레이션](/public/actions/langflow/direct-development-quality-response-trend-simulate.md)이 Action Spec과 SOP 근거를 바탕으로 `SIMULATED` evidence packet을 만든다.

# BoI Usage

- [direct_development.result_check.requested.v1](/public/event-types/direct_development.result_check.requested.v1.md)
- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)

# Citations

- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
