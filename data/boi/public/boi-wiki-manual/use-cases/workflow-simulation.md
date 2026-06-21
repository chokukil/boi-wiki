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

# Agentic Runtime Pattern

shared BoI Wiki runtime의 Universal Simulator는 단순 LLM prompt가 아니라 `BoI Simulation Agent`를 먼저 실행한다. Agent는 다음 순서로 context를 수집한다.

1. action key로 Action Catalog와 public action spec을 exact lookup한다.
2. event type 문서와 SOP workflow stage를 찾는다.
3. prior action result와 payload term으로 관련 BoI를 추가 검색한다.
4. `sop_stage`, `action_contract`, `expected_output_schema`, `prior_evidence`, `manual_or_approval_condition`, `next_stage_or_event` coverage를 평가한다.
5. 부족한 context는 `missing_context`로 남기고, 근거 없는 simulation을 꾸며내지 않는다.

Langflow는 이 agent가 만든 `context_pack`, `retrieval_trace`, `coverage_report`를 받아 최종 한국어 결과를 렌더링한다. 따라서 Raw Action과 Workflow Status에서 어떤 Wiki 문서를 근거로 삼았는지 확인할 수 있어야 한다.

# Output Contract

- Input Event
- Expected SOP Stages
- Expected Actions
- Manual Handoffs
- Generated BoI Records
- Risk and Approval Notes
- Mermaid Trace
- Retrieval Trace
- Coverage Report
- Citations

# Citations

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [Event-to-Action Workflow Planning](event-to-action-workflow-planning.md)
- [Langflow Connected Flow Guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
