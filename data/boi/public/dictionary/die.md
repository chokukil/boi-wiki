---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Die
description: wafer 위에 반복 형성되는 개별 반도체 chip 단위
tags:
- Dictionary
- Semiconductor
- semiconductor-object
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:die
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
term: Die
definition: wafer 위에 반복 형성되는 개별 반도체 chip 단위
aliases:
- chip die
- 칩
- die unit
- 다이
domain: semiconductor-object
examples:
- 불량 die 분포는 Map View와 Yield 분석의 기본 단위다.
links:
- /public/event-types/direct_development.map_view.requested.v1.md
related_terms:
- Wafer
- Yield
- Map View
- Defect
source_refs:
- type: external-reference
  ref: Lam Research Technical Glossary
  url: https://www.lamresearch.com/technical-glossary/
- type: external-reference
  ref: Intel Common Chip Terms
  url: https://newsroom.intel.com/de/tech101/explaining-common-chip-terms
---

# Summary

wafer 위에 반복 형성되는 개별 반도체 chip 단위

# BoI Usage

- [direct_development.map_view.requested.v1](/public/event-types/direct_development.map_view.requested.v1.md)

# Agent Notes

- Agent는 `Die` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Lam Research Technical Glossary](https://www.lamresearch.com/technical-glossary/)
- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
