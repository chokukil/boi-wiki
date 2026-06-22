---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Map View
description: wafer 또는 검사 결과를 위치/패턴 관점에서 보는 map image evidence
tags: [Dictionary, MapView, Wafer, Quality]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:map-view
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Map View
definition: wafer 또는 검사 결과를 위치 좌표와 패턴으로 확인하는 map/image evidence. 직개발 workflow에서는 Response Trend 이후 단면검사 판단의 핵심 입력이다.
aliases: [Map View Image, 맵뷰, 맵 이미지, Wafer Map, Map 분석]
domain: direct-development-workflow
examples:
  - Map View에서 특정 영역 패턴이 확인되면 단면검사 필요 여부를 판단한다.
links:
  - /public/actions/langflow/direct-development-map-view-simulate.md
  - /public/actions/manual/direct-development-decide-cross-section.md
related_terms: [Wafer, Response Trend, Cross-section Inspection]
maps_to_event_type: direct_development.map_view.requested.v1
maps_to_action_key: direct_development.map_view.simulate
maps_to_sop: boi:public:sop:direct-development-reporting
source_refs:
  - {type: external-glossary, ref: "Hitachi High-Tech Semiconductor Glossary", url: "https://www.hitachi-hightech.com/global/en/knowledge/semiconductor/room/words.html"}
  - {type: internal-doc, ref: "/public/sop/direct-development-reporting.md"}
---

# Summary

Map View는 wafer 또는 검사 결과의 위치/패턴 evidence다. BoI Wiki에서는 Response Trend와 함께 단면검사 판단의 prerequisite evidence로 취급한다.

# BoI Usage

- [Map View 확인 시뮬레이션](/public/actions/langflow/direct-development-map-view-simulate.md)
- [단면검사 필요 여부 판단](/public/actions/manual/direct-development-decide-cross-section.md)

# Related Dictionary Terms

- [Wafer](wafer.md)
- [Response Trend](response-trend.md)
- [Cross-section Inspection](cross-section-inspection.md)

# Citations

- [Hitachi High-Tech Semiconductor Glossary](https://www.hitachi-hightech.com/global/en/knowledge/semiconductor/room/words.html)
- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
