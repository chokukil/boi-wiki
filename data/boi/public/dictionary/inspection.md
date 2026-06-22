---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Inspection
description: wafer, die, package의 defect나 pattern 이상을 찾아내는 검사 활동
tags:
- Dictionary
- Semiconductor
- quality-metrology
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:inspection
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
term: Inspection
definition: wafer, die, package의 defect나 pattern 이상을 찾아내는 검사 활동
aliases:
- 검사
- defect inspection
- wafer inspection
- pattern inspection
domain: quality-metrology
examples:
- Inspection 결과는 Map View나 defect list로 manual decision의 evidence가 된다.
links:
- /public/event-types/direct_development.map_view.requested.v1.md
related_terms:
- Defect
- Map View
- Cross-section Inspection
- Yield
source_refs:
- type: external-reference
  ref: Applied Materials Metrology and Inspection
  url: https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html
- type: external-reference
  ref: KLA Defect Inspection and Review
  url: https://www.kla.com/products/chip-manufacturing/defect-inspection-review
- type: external-reference
  ref: KLA Wafer Inspection and Metrology for Advanced Packaging
  url: https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging
maps_to_event_type: direct_development.map_view.requested.v1
---

# Summary

wafer, die, package의 defect나 pattern 이상을 찾아내는 검사 활동

# BoI Usage

- [direct_development.map_view.requested.v1](/public/event-types/direct_development.map_view.requested.v1.md)

# Agent Notes

- Agent는 `Inspection` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Metrology and Inspection](https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html)
- [KLA Defect Inspection and Review](https://www.kla.com/products/chip-manufacturing/defect-inspection-review)
- [KLA Wafer Inspection and Metrology for Advanced Packaging](https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging)
