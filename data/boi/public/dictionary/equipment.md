---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Equipment
description: 공정/검사/계측을 수행하는 생산 설비 단위
tags:
- Dictionary
- Semiconductor
- equipment
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:equipment
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
term: Equipment
definition: 공정/검사/계측을 수행하는 생산 설비 단위
aliases:
- 설비
- tool
- machine
- 장비
domain: equipment
examples:
- Equipment alarm은 설비 이상 대응 SOP의 entry event가 된다.
links:
- /public/event-types/equipment.alarm.raised.v1.md
related_terms:
- Fab
- Chamber
- Alarm
- Recipe
source_refs:
- type: external-reference
  ref: Lam Research Our Processes
  url: https://www.lamresearch.com/products/our-processes/
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
maps_to_event_type: equipment.alarm.raised.v1
maps_to_sop: boi:public:sop:equipment-abnormal-response
---

# Summary

공정/검사/계측을 수행하는 생산 설비 단위

# BoI Usage

- [equipment.alarm.raised.v1](/public/event-types/equipment.alarm.raised.v1.md)

# Agent Notes

- Agent는 `Equipment` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Fab](fab.md)
- [Chamber](chamber.md)
- [Alarm](alarm.md)
- [Recipe](recipe.md)

# Citations

- [Lam Research Our Processes](https://www.lamresearch.com/products/our-processes/)
- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
