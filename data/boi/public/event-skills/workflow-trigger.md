---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-skill
title: Event Workflow Trigger Skill
description: Event가 workflow 시작점으로 쓰일 때 BoI Agent와 Event Router가 해석하는 기준
tags: [EventSkill, EventBroker, Workflow]
timestamp: 2026-06-27T11:35:00+09:00
boi_id: boi:public:event-skills:workflow-trigger
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
skill_key: event.workflow_trigger
source_refs:
  - type: catalog
    ref: data/event_skill_catalog/skills.yaml#event.workflow_trigger
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

`event.workflow_trigger`는 Event가 SOP workflow를 시작한다는 의미를 가진다. 이 Skill이 Workflow 정의에 연결되면 BoI Agent는 Event Type을 시작점으로 SOP, Action, Manual Handoff, Next Event를 설명할 수 있다.

# Required Context

- Event Type
- payload schema
- trace policy
- linked SOP/stage
- recommended actions
- visibility policy
