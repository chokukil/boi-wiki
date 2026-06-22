---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Process Capability
description: 공정이 안정 상태에서 spec limit 안에 결과를 낼 수 있는 능력
tags:
- Dictionary
- Semiconductor
- spc
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:process-capability
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
term: Process Capability
definition: 공정이 안정 상태에서 spec limit 안에 결과를 낼 수 있는 능력
aliases:
- 공정능력
- capability
- process capability index
domain: spc
examples:
- Process Capability 악화는 spec/rule 변경이나 hold 검토의 근거가 될 수 있다.
links:
- /public/actions/api/change-spec-rule.md
- /public/actions/api/block-process-progress.md
related_terms:
- Cpk
- Spec / Rule
- SPC
- Process Hold
source_refs:
- type: external-reference
  ref: NIST Process Capability
  url: https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm
- type: external-reference
  ref: NIST Cpk
  url: https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/cpk.pdf
maps_to_action_key: sop.equipment.change_spec_rule
---

# Summary

공정이 안정 상태에서 spec limit 안에 결과를 낼 수 있는 능력

# BoI Usage

- [change-spec-rule](/public/actions/api/change-spec-rule.md)
- [block-process-progress](/public/actions/api/block-process-progress.md)

# Agent Notes

- Agent는 `Process Capability` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Cpk](cpk.md)
- [Spec / Rule](spec-rule.md)
- [SPC](spc.md)
- [Process Hold](process-hold.md)

# Citations

- [NIST Process Capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm)
- [NIST Cpk](https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/cpk.pdf)
