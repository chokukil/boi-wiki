---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Event-to-Action Workflow Planning
description: 업무 이벤트가 발생했을 때 SOP stage, action, manual handoff, generated BoI 흐름을 계획하는 사례
tags: [Manual, UseCase, EventBroker, Workflow, ActionGateway]
timestamp: 2026-06-20T00:11:00+09:00
boi_id: boi:public:boi-wiki-manual:use-cases:event-to-action-workflow-planning
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Event-to-Action Workflow Planning은 사용자가 "이 이벤트가 발생하면 어떻게 해줘"라고 말했을 때 Event Type, SOP stage, Action, Manual Handoff, 생성 BoI를 한 번에 설계하는 사례다.

# User Request

```text
이 이벤트가 발생하면 어떤 SOP와 Action이 이어지는지 알려줘.
```

# Agent Flow

1. Local workspace에서는 `boi-event-workflow-planner` skill을 사용한다.
2. 원격 MCP가 있으면 Event Type, SOP, Action Spec을 먼저 검색한다.
3. 기존 Event Type이 있으면 재사용하고, 없으면 `domain.signal.requested.v1` 형태의 후보를 만든다.
4. 고위험 action에는 manual approval을 반드시 표시한다.
5. 실제 `workflow_start` 또는 `action_invoke`는 사용자 승인 전 실행하지 않는다.

# Output Contract

- Event Type or candidate
- Trigger payload
- SOP and stage mapping
- Automated actions
- Manual handoffs
- Expected generated BoI
- Gap list and questions

# Citations

- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [Public Event Types](/public/event-types/equipment.alarm.raised.v1.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
