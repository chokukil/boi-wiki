---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Approval
description: 고위험 action 실행 또는 외부 공유 전에 권한자가 명시적으로 승인하는 절차
tags:
- Dictionary
- Semiconductor
- governance
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:approval
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
term: Approval
definition: 고위험 action 실행 또는 외부 공유 전에 권한자가 명시적으로 승인하는 절차
aliases:
- 승인
- approval required
- 승인 필요
- 결재
- 검토 승인
domain: governance
examples:
- Process Hold와 Spec / Rule 변경은 승인 없이 자동 실행하지 않는다.
links:
- /public/actions/manual/approve-process-hold.md
- /public/actions/manual/approve-spec-rule-change.md
related_terms:
- Manual Handoff
- Process Hold
- Spec / Rule
- Action Gateway
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_action_key: manual.equipment.approve_process_hold
---

# Summary

고위험 action 실행 또는 외부 공유 전에 권한자가 명시적으로 승인하는 절차

# BoI Usage

- [approve-process-hold](/public/actions/manual/approve-process-hold.md)
- [approve-spec-rule-change](/public/actions/manual/approve-spec-rule-change.md)

# Agent Notes

- Agent는 `Approval` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Manual Handoff](manual-handoff.md)
- [Process Hold](process-hold.md)
- [Spec / Rule](spec-rule.md)
- [Action Gateway](action-gateway.md)

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
