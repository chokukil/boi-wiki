---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Manual Handoff
description: Agent가 자동 실행하지 않고 담당자 판단/승인/현장 조치로 넘기는 업무 단계
tags:
- Dictionary
- Semiconductor
- ai-native-workflow
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:manual-handoff
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
term: Manual Handoff
definition: Agent가 자동 실행하지 않고 담당자 판단/승인/현장 조치로 넘기는 업무 단계
aliases:
- human handoff
- 수동 조치
- 사람 판단
- 담당자 조치
- manual task
domain: ai-native-workflow
examples:
- 단면검사 필요 여부 판단, process hold 승인, spec 변경 승인은 manual handoff로 추적한다.
links:
- /public/actions/manual/direct-development-decide-cross-section.md
- /public/actions/manual/approve-process-hold.md
related_terms:
- Approval
- Action Gateway
- Cross-section Inspection
- Corrective Action
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_action_key: manual.direct_development.decide_cross_section
---

# Summary

Agent가 자동 실행하지 않고 담당자 판단/승인/현장 조치로 넘기는 업무 단계

# BoI Usage

- [direct-development-decide-cross-section](/public/actions/manual/direct-development-decide-cross-section.md)
- [approve-process-hold](/public/actions/manual/approve-process-hold.md)

# Agent Notes

- Agent는 `Manual Handoff` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Approval](approval.md)
- [Action Gateway](action-gateway.md)
- [Cross-section Inspection](cross-section-inspection.md)
- [Corrective Action](corrective-action.md)

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
