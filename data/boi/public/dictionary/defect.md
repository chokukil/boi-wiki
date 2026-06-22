---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Defect
description: wafer/die/package에서 목표 spec이나 pattern에서 벗어난 결함
tags:
- Dictionary
- Semiconductor
- quality-metrology
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:defect
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
term: Defect
definition: wafer/die/package에서 목표 spec이나 pattern에서 벗어난 결함
aliases:
- 불량
- 결함
- particle
- pattern defect
- killer defect
domain: quality-metrology
examples:
- Defect 위치와 반복 패턴은 Map View와 Cross-section Inspection 판단에 쓰인다.
links:
- /public/actions/langflow/direct-development-map-view-simulate.md
related_terms:
- Inspection
- Map View
- Defect Density
- Yield
source_refs:
- type: external-reference
  ref: KLA Defect Inspection and Review
  url: https://www.kla.com/products/chip-manufacturing/defect-inspection-review
- type: external-reference
  ref: Intel Common Chip Terms
  url: https://newsroom.intel.com/de/tech101/explaining-common-chip-terms
maps_to_action_key: direct_development.map_view.simulate
---

# Summary

wafer/die/package에서 목표 spec이나 pattern에서 벗어난 결함

# BoI Usage

- [direct-development-map-view-simulate](/public/actions/langflow/direct-development-map-view-simulate.md)

# Agent Notes

- Agent는 `Defect` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [KLA Defect Inspection and Review](https://www.kla.com/products/chip-manufacturing/defect-inspection-review)
- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
