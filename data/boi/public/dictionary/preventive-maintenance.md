---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Preventive Maintenance
description: 고장 발생 전 정기/조건 기반으로 수행하는 설비 보전 활동
tags:
- Dictionary
- Semiconductor
- equipment-maintenance
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:preventive-maintenance
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
term: Preventive Maintenance
definition: 고장 발생 전 정기/조건 기반으로 수행하는 설비 보전 활동
aliases:
- PM
- 예방보전
- 정기보전
- maintenance
domain: equipment-maintenance
examples:
- PM history는 alarm root cause와 corrective action 판단의 근거가 된다.
links:
- /public/actions/api/request-maintenance-guide.md
- /public/actions/manual/confirm-maintenance-done.md
related_terms:
- Equipment
- Root Cause Analysis
- Corrective Action
- Manual Handoff
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
maps_to_action_key: sop.equipment.request_maintenance_guide
---

# Summary

고장 발생 전 정기/조건 기반으로 수행하는 설비 보전 활동

# BoI Usage

- [request-maintenance-guide](/public/actions/api/request-maintenance-guide.md)
- [confirm-maintenance-done](/public/actions/manual/confirm-maintenance-done.md)

# Agent Notes

- Agent는 `Preventive Maintenance` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
