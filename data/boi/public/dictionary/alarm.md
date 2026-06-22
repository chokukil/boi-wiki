---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Alarm
description: 설비/공정/품질 시스템에서 이상 조건을 알리는 event signal
tags:
- Dictionary
- Semiconductor
- equipment-monitoring
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:alarm
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
term: Alarm
definition: 설비/공정/품질 시스템에서 이상 조건을 알리는 event signal
aliases:
- 알람
- 설비 알람
- equipment alarm
- warning
domain: equipment-monitoring
examples:
- Alarm은 Event Broker가 BoI workflow를 시작하는 대표 trigger다.
links:
- /public/event-types/equipment.alarm.raised.v1.md
- /public/actions/manual/confirm-alarm-context.md
related_terms:
- FDC
- Equipment
- Event Broker
- Manual Handoff
source_refs:
- type: external-reference
  ref: Applied Materials Technical Glossary
  url: https://www.appliedmaterials.com/us/en/glossary.html
maps_to_event_type: equipment.alarm.raised.v1
---

# Summary

설비/공정/품질 시스템에서 이상 조건을 알리는 event signal

# BoI Usage

- [equipment.alarm.raised.v1](/public/event-types/equipment.alarm.raised.v1.md)
- [confirm-alarm-context](/public/actions/manual/confirm-alarm-context.md)

# Agent Notes

- Agent는 `Alarm` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
