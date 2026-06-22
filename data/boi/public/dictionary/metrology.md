---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Metrology
description: 공정 결과가 목표 물리/전기 특성에 맞는지 계측하는 활동
tags:
- Dictionary
- Semiconductor
- quality-metrology
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:metrology
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
term: Metrology
definition: 공정 결과가 목표 물리/전기 특성에 맞는지 계측하는 활동
aliases:
- 계측
- 측정
- measurement
- CD metrology
- film metrology
domain: quality-metrology
examples:
- Metrology result는 SOP에서 원인 분석과 spec/rule 변경 근거로 쓰인다.
links:
- /public/actions/api/request-raw-data.md
- /public/actions/api/request-trend-history.md
related_terms:
- Inspection
- SPC
- Response Trend
- Spec / Rule
source_refs:
- type: external-reference
  ref: Applied Materials Metrology and Inspection
  url: https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html
- type: external-reference
  ref: KLA Wafer Inspection and Metrology for Advanced Packaging
  url: https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging
maps_to_action_key: sop.equipment.request_raw_data
---

# Summary

공정 결과가 목표 물리/전기 특성에 맞는지 계측하는 활동

# BoI Usage

- [request-raw-data](/public/actions/api/request-raw-data.md)
- [request-trend-history](/public/actions/api/request-trend-history.md)

# Agent Notes

- Agent는 `Metrology` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Metrology and Inspection](https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html)
- [KLA Wafer Inspection and Metrology for Advanced Packaging](https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging)
