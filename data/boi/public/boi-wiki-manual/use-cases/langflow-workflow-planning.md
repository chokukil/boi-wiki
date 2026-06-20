---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Langflow Workflow Planning
description: SOP와 Action 문서를 기준으로 BoI 연계 Langflow workflow를 설계하는 사례
tags: [Manual, UseCase, Langflow, Workflow, BoI]
timestamp: 2026-06-20T00:15:00+09:00
boi_id: boi:public:boi-wiki-manual:use-cases:langflow-workflow-planning
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
    ref: boi:public:boi-wiki-manual:langflow:connected-flow-guide
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Langflow Workflow Planning은 SOP stage 중 LLM reasoning이 필요한 부분만 Langflow로 연결하고, 나머지는 API, Event Broker, Manual Action으로 유지하는 사례다.

# User Request

```text
이 SOP를 Langflow와 BoI Action Gateway에 어떻게 연결하면 좋을지 설계해줘.
```

# Agent Flow

1. Local workspace에서는 `boi-langflow-connector-planner` skill을 사용한다.
2. Langflow가 꼭 필요한 stage인지 먼저 판단한다.
3. remote MCP가 있으면 Langflow guide, SOP, action spec을 검색한다.
4. required components, input schema, output BoI policy, validation checklist를 만든다.
5. 연결되지 않은 canvas나 smoke 미검증 flow를 완료로 보지 않는다.

# Validation Checklist

- Required BoI context inputs are explicit.
- Action Gateway invoke points are allowlisted.
- Output body boundaries and generated BoI policy are explicit.
- Runtime smoke evidence is required before calling it live.

# Citations

- [Langflow connected flow guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
