---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Recipe
description: 설비가 wafer를 처리할 때 사용하는 공정 parameter와 step set
tags:
- Dictionary
- Semiconductor
- equipment
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:recipe
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
term: Recipe
definition: 설비가 wafer를 처리할 때 사용하는 공정 parameter와 step set
aliases:
- 레시피
- process recipe
- 공정 조건
- parameter set
domain: equipment
examples:
- Recipe 변경은 Spec / Rule 변경과 달리 실행 전 승인/검증 기준이 필요하다.
links:
- /public/actions/api/change-spec-rule.md
- /public/actions/manual/approve-spec-rule-change.md
related_terms:
- Equipment
- Spec / Rule
- Process Capability
- Approval
source_refs:
- type: external-reference
  ref: Applied Materials Technical Glossary
  url: https://www.appliedmaterials.com/us/en/glossary.html
- type: external-reference
  ref: Lam Research Our Processes
  url: https://www.lamresearch.com/products/our-processes/
maps_to_action_key: sop.equipment.change_spec_rule
---

# Summary

설비가 wafer를 처리할 때 사용하는 공정 parameter와 step set

# BoI Usage

- [change-spec-rule](/public/actions/api/change-spec-rule.md)
- [approve-spec-rule-change](/public/actions/manual/approve-spec-rule-change.md)

# Agent Notes

- Agent는 `Recipe` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Equipment](equipment.md)
- [Spec / Rule](spec-rule.md)
- [Process Capability](process-capability.md)
- [Approval](approval.md)

# Citations

- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
- [Lam Research Our Processes](https://www.lamresearch.com/products/our-processes/)
