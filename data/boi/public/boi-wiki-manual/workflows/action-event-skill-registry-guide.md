---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Action and Event Skill Registry Guide
description: BoI Agent가 Event, Action, Task Skill을 업무 의미로 이해하도록 Skill registry를 관리하는 기준
tags: [BoIWiki, SkillRegistry, Agent, Action, Event, Workflow, Task]
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

`connector_kind`는 실행 채널이고 Skill registry는 업무 의미다. 같은 MCP나 API connector라도 “시계열 예측”, “Event 발행”, “Manual Handoff 완료”처럼 Agent가 이해해야 하는 의미는 다르다. 현재 SOP Builder에서는 Action 또는 Skill을 특정 Task에 연결한다.

# Registry Files

| File | Scope |
|---|---|
| `data/event_skill_catalog/skills.yaml` | Event를 trigger, transition, escalation 등으로 해석 |
| `data/action_skill_catalog/skills.yaml` | Action을 evidence collection, forecast, publish, manual completion 등으로 해석 |
| `data/workflow_catalog/workflows.yaml` | Event Skill과 Action Skill을 내부 WorkflowDefinition 안에서 조합 |

# Agent Rule

BoI Agent는 추천 질문과 실행 카드를 만들 때 Workflow/Task의 `actions`, `skills`, 내부 WorkflowDefinition의 `affordances`, `event_skill_refs`, `action_skill_refs`를 함께 본다. Registry에 없는 후속 행동은 추천하지 않는다.

# Task Skill Rule

Task에 연결되는 Skill은 다음 중 하나로 분류한다.

| Skill kind | 의미 | 실행 기준 |
|---|---|---|
| `guide_only` | Markdown 설명과 절차만 제공 | 사용자가 읽고 Manual 또는 Copilot으로 처리 |
| `agent_tool` | Agent가 MCP/API/tool로 호출 가능 | Copilot 또는 Autopilot Task에서 사용 |
| `sandbox_run` | script나 notebook 실행이 필요 | Sandbox 또는 Agent Runtime을 통해 실행 |

Script-backed Skill은 브라우저에서 직접 실행하지 않는다. Sandbox 또는 Agent Runtime을 통해 실행하고, 입력, 출력, artifact, validation result를 남긴다. 사용자 화면에는 Skill 이름, 목적, 필요한 입력, 예상 산출물만 보이고 내부 경로와 script 세부정보는 접힌 기술 세부정보에 둔다.

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

이 Skill이 연결된 Workflow Task나 내부 WorkflowDefinition는 Agent가 “다음 Event 발행 전 확인” 같은 confirmation card를 만들 수 있다.

# Related Documents

- [Workflow/Task Builder 따라하기](/docs/boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step)
- [SOP Workflow 작성과 Runtime 연결](/public/boi-wiki-manual/sop-workflows/create-and-connect-sop.md)
