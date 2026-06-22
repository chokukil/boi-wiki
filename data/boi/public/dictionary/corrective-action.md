---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Corrective Action
description: 확인된 이상 원인 또는 위험에 대해 수행하는 조치 계획/실행/확인
tags:
- Dictionary
- Semiconductor
- workflow
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:corrective-action
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
term: Corrective Action
definition: 확인된 이상 원인 또는 위험에 대해 수행하는 조치 계획/실행/확인
aliases:
- 이상 조치
- corrective action request
- 조치 요청
- CAPA
domain: workflow
examples:
- Corrective Action은 notify, hold, spec change, manual completion 같은 action으로 분해된다.
links:
- /public/event-types/corrective_action.requested.v1.md
- /public/actions/api/notify-action-owner.md
related_terms:
- Process Hold
- Spec / Rule
- Approval
- Manual Handoff
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
maps_to_event_type: corrective_action.requested.v1
---

# Summary

확인된 이상 원인 또는 위험에 대해 수행하는 조치 계획/실행/확인

# BoI Usage

- [corrective_action.requested.v1](/public/event-types/corrective_action.requested.v1.md)
- [notify-action-owner](/public/actions/api/notify-action-owner.md)

# Agent Notes

- Agent는 `Corrective Action` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
