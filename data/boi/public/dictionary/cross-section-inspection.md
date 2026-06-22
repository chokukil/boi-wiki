---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Cross-section Inspection
description: 구조 또는 결함 확인을 위해 단면을 관찰하는 검사 업무
tags: [Dictionary, Inspection, DirectDevelopment]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:cross-section-inspection
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Cross-section Inspection
definition: wafer, sample, device 구조를 단면으로 확인해 이상 원인이나 구조적 결함을 판단하는 검사 업무. BoI Wiki에서는 manual decision과 simulated request/result action으로 나뉜다.
aliases: [단면검사, 단면 검사, Cross Section, X-section, 단면 분석]
domain: direct-development-workflow
examples:
  - Response Trend와 Map View evidence가 충분하면 단면검사 의뢰 event로 이어진다.
links:
  - /public/actions/manual/direct-development-decide-cross-section.md
  - /public/actions/langflow/direct-development-cross-section-request-simulate.md
  - /public/actions/langflow/direct-development-cross-section-result-simulate.md
related_terms: [Map View, Response Trend, Manual Handoff]
maps_to_event_type: direct_development.cross_section.decision_required.v1
maps_to_action_key: manual.direct_development.decide_cross_section
maps_to_sop: boi:public:sop:direct-development-reporting
source_refs:
  - {type: internal-doc, ref: "/public/sop/direct-development-reporting.md"}
---

# Summary

Cross-section Inspection은 단면검사다. BoI Wiki에서는 자동 실행이 아니라 사람이 Response Trend와 Map View evidence를 보고 필요 여부를 판단한 뒤 다음 event/action으로 넘긴다.

# BoI Usage

- [단면검사 필요 여부 판단](/public/actions/manual/direct-development-decide-cross-section.md)
- [단면검사 의뢰 시뮬레이션](/public/actions/langflow/direct-development-cross-section-request-simulate.md)

# Citations

- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
