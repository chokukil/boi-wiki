---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Capability Registration Guide
description: API, MCP, Webhook, Langflow, Manual, skill, harness, SOP를 Event-native Capability Pack으로 등록하는 기준
tags: [BoIWiki, Capability, EventBroker, ActionGateway, Registration]
timestamp: 2026-06-27T11:00:00+09:00
boi_id: boi:public:boi-wiki-manual:capabilities:capability-registration-guide
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
    ref: data/event_skill_catalog/skills.yaml
  - type: repo
    ref: data/action_skill_catalog/skills.yaml
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

BoI Wiki Pilot의 등록 단위는 단일 Action이 아니라 Capability Pack이다. API, MCP, Webhook, Langflow flow, Manual 업무, skill, harness, SOP를 등록하면 Event Contract, Capability Pack, Action/Event Skill, 문서, 테스트, 권한 정책이 함께 연결되어야 한다.

Langflow는 실행 방식 중 하나다. 기본 workflow engine은 `event_native`이며, Event Broker, SOP metadata, Action Catalog, BoI Writer만으로 동작해야 한다.

# Registration Flow

```mermaid
flowchart TD
  A["등록 대상 선택<br/>API/MCP/Webhook/Langflow/Manual/Skill/SOP"] --> B["Schema/URL/문서 입력"]
  B --> C["Ontology-assisted dedupe"]
  C --> D{"판정"}
  D -->|"재사용 권장"| R["기존 Capability/Action 확장"]
  D -->|"신규 필요"| N["Capability draft 생성"]
  D -->|"차이 확인 필요"| X["비교 근거 기록"]
  R --> M["Event Type + SOP Stage 매핑"]
  N --> M
  X --> M
  M --> E["workflow_engine 선택<br/>기본 event_native"]
  E --> T["Event Broker publish smoke<br/>connector test"]
  T --> P["BoI 문서 + catalog patch preview"]
  P --> G["RBAC/ACL/secret scan"]
  G --> U["사용자 확인 후 publish"]
```

# Required Objects

| Object | Purpose |
|---|---|
| Event Type | 업무가 발생했다는 runtime 계약 |
| Capability Pack | Event, SOP, Action, Manual Handoff, evidence, affordance를 묶는 업무 능력 |
| Action Skill | Agent가 Action을 어떤 업무 의미로 이해할지 설명 |
| Event Skill | Agent가 Event를 workflow trigger/transition으로 해석하는 기준 |
| Action Spec | Action Gateway가 실제 실행할 connector 계약 |
| BoI Manual | 사람이 읽고 검토할 운영 문서 |

# Publish Rule

Capability publish는 draft, dedupe, schema validation, Event Broker smoke, connector smoke, RBAC/ACL, secret scan을 통과해야 한다. 승인 전에는 catalog에 반영하지 않는다.

# Related Documents

- [Event Contract Guide](/public/boi-wiki-manual/capabilities/event-contract-guide.md)
- [Event-Native Workflow Guide](/public/boi-wiki-manual/capabilities/event-native-workflow-guide.md)
- [Action/Event Skill Registry Guide](/public/boi-wiki-manual/capabilities/action-event-skill-registry-guide.md)
- [Duplicate Detection Guide](/public/boi-wiki-manual/capabilities/duplicate-detection-guide.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
