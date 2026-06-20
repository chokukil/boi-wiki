---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Workflow Simulation
description: event payload를 기준으로 실제 action 호출 없이 SOP workflow를 dry-run하는 사례
tags: [Manual, UseCase, Workflow, Simulation, EventBroker]
timestamp: 2026-06-20T00:14:00+09:00
boi_id: boi:public:boi-wiki-manual:use-cases:workflow-simulation
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
    ref: boi:public:sop:equipment-abnormal-response
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Workflow Simulation은 실제 Kafka event나 Action Gateway 호출 없이, 주어진 event payload가 어떤 SOP stage와 action, manual handoff, generated BoI로 이어질지 dry-run하는 사례다.

# User Request

```text
이 event payload가 들어오면 BoI Wiki workflow가 어떻게 진행될지 dry-run으로 보여줘.
```

# Agent Flow

1. Local workspace에서는 `boi-workflow-simulator` skill을 사용한다.
2. 시뮬레이션임을 명시하고 실제 action 결과처럼 쓰지 않는다.
3. remote MCP가 있으면 SOP/Event/Action 문서를 조회할 수 있지만, `workflow_start`나 `action_invoke`는 사용자 승인 전 호출하지 않는다.
4. Mermaid trace와 expected generated BoI 목록을 만든다.

# Output Contract

- Input Event
- Expected SOP Stages
- Expected Actions
- Manual Handoffs
- Generated BoI Records
- Risk and Approval Notes
- Mermaid Trace
- Citations

# Citations

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [Event-to-Action Workflow Planning](event-to-action-workflow-planning.md)
