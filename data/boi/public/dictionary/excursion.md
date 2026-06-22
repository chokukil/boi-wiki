---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Excursion
description: 정상 공정 window 또는 관리 기준에서 벗어난 일시적/구간성 이상
tags:
- Dictionary
- Semiconductor
- quality
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:excursion
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
term: Excursion
definition: 정상 공정 window 또는 관리 기준에서 벗어난 일시적/구간성 이상
aliases:
- 공정 이탈
- 품질 이탈
- process excursion
- abnormal excursion
domain: quality
examples:
- Excursion이 확인되면 lot scope, affected wafer, process hold 여부를 추적한다.
links:
- /public/sop/equipment-abnormal-response.md
related_terms:
- Out-of-Control
- Process Hold
- Root Cause Analysis
- Lot
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
- type: external-reference
  ref: Applied Materials Metrology and Inspection
  url: https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html
maps_to_sop: boi:public:sop:equipment-abnormal-response
---

# Summary

정상 공정 window 또는 관리 기준에서 벗어난 일시적/구간성 이상

# BoI Usage

- [equipment-abnormal-response](/public/sop/equipment-abnormal-response.md)

# Agent Notes

- Agent는 `Excursion` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
- [Applied Materials Metrology and Inspection](https://www.appliedmaterials.com/us/en/semiconductor/products/processes/metrology-and-inspection.html)
