---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Action and Event Skill Registry Guide
description: BoI Agent가 Event와 Action을 업무 의미로 이해하도록 Skill registry를 관리하는 기준
tags: [BoIWiki, SkillRegistry, Agent, Action, Event]
timestamp: 2026-06-27T11:15:00+09:00
boi_id: boi:public:boi-wiki-manual:workflows:action-event-skill-registry-guide
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: data/event_skill_catalog/skills.yaml
  - type: repo
    ref: data/action_skill_catalog/skills.yaml
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

`connector_kind`는 실행 방식이고 Skill registry는 업무 의미다. 같은 MCP나 API connector라도 “시계열 예측”, “Event 발행”, “Manual Handoff 완료”처럼 Agent가 이해해야 하는 의미는 다르다.

# Registry Files

| File | Scope |
|---|---|
| `data/event_skill_catalog/skills.yaml` | Event를 trigger, transition, escalation 등으로 해석 |
| `data/action_skill_catalog/skills.yaml` | Action을 evidence collection, forecast, publish, manual completion 등으로 해석 |
| `data/workflow_catalog/workflows.yaml` | Event Skill과 Action Skill을 WorkflowDefinition 안에서 조합 |

# Agent Rule

BoI Agent는 추천 질문과 실행 카드를 만들 때 WorkflowDefinition의 `affordances`, `event_skill_refs`, `action_skill_refs`를 먼저 본다. Registry에 없는 후속 행동은 추천하지 않는다.

# Example

```yaml
action_skills:
  - skill_key: event.publish
    title: Event 발행
    affordances:
      - request_execution
    safety:
      requires_confirmation: true
```

이 Skill이 연결된 WorkflowDefinition는 Agent가 “다음 Event 발행 전 확인” 같은 confirmation card를 만들 수 있다.
