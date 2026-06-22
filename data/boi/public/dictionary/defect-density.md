---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Defect Density
description: wafer 단위 면적당 defect 수 또는 밀도
tags:
- Dictionary
- Semiconductor
- quality
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:defect-density
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
term: Defect Density
definition: wafer 단위 면적당 defect 수 또는 밀도
aliases:
- DD
- 결함밀도
- defects per area
- defect rate
domain: quality
examples:
- Defect Density가 높아지면 yield impact와 root cause candidate를 함께 검토한다.
links:
- /public/event-types/direct_development.map_view.requested.v1.md
related_terms:
- Defect
- Yield
- Inspection
- Map View
source_refs:
- type: external-reference
  ref: AnySilicon Defect Density
  url: https://anysilicon.com/semipedia/defect-density-dd/
- type: external-reference
  ref: Intel Common Chip Terms
  url: https://newsroom.intel.com/de/tech101/explaining-common-chip-terms
---

# Summary

wafer 단위 면적당 defect 수 또는 밀도

# BoI Usage

- [direct_development.map_view.requested.v1](/public/event-types/direct_development.map_view.requested.v1.md)

# Agent Notes

- Agent는 `Defect Density` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [AnySilicon Defect Density](https://anysilicon.com/semipedia/defect-density-dd/)
- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
