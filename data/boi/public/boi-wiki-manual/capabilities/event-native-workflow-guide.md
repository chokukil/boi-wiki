---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Event-Native Workflow Guide
description: Langflow 없이 Event Broker와 Capability Pack으로 BoI workflow를 운영하는 기준
tags: [BoIWiki, EventNative, EventBroker, Workflow, Capability]
timestamp: 2026-06-27T11:10:00+09:00
boi_id: boi:public:boi-wiki-manual:capabilities:event-native-workflow-guide
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
    ref: data/capability_catalog/capabilities.yaml
  - type: repo
    ref: event_router
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

`event_native` workflow는 BoI Wiki Pilot의 기본 엔진이다. Event Broker가 업무 발생과 전이를 전달하고, Action Gateway가 실행 가능한 요청을 처리하며, BoI Writer가 실행 근거와 결과를 문서화한다.

Langflow는 `langflow_assisted` Capability에서만 필요하다. Capability의 `required_connectors`에 Langflow가 없으면 Langflow 장애와 무관하게 workflow가 계속 동작해야 한다.

# Workflow Engine Policy

| Engine | Use |
|---|---|
| `event_native` | 기본값. Event Catalog, SOP metadata, Action Catalog로 동작 |
| `external_orchestrator` | 사내 orchestration 시스템이 주도 |
| `manual_only` | 사람이 수행하고 BoI에 기록 |
| `langflow_assisted` | 특정 stage/action에서 Langflow를 선택적으로 사용 |

# Runtime Flow

```mermaid
sequenceDiagram
  participant User as User or System
  participant Broker as Event Broker
  participant Router as Event Router
  participant Gateway as Action Gateway
  participant Writer as BoI Writer
  participant Agent as BoI Agent

  User->>Broker: Publish Event
  Broker->>Router: Route by Event Type
  Router->>Gateway: Dispatch recommended Action
  Gateway-->>Router: Action Result
  Router->>Writer: Materialize Generated BoI
  Writer-->>Agent: Searchable evidence
  Agent-->>User: SOP/Event/Action/Next Event guidance
```

# Validation

Event-native Capability publish requires:

- Event schema validation
- Event Broker publish smoke
- Connector smoke for required actions
- ACL/RBAC check
- secret/sensitive scan
- BoI document and catalog patch preview

Failure must be visible. A missing Langflow flow is not an error for `event_native`.
