---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: API Doc to Action Spec
description: 기존 시스템 API 문서를 BoI Action Spec과 catalog patch draft로 변환하는 사례
tags: [Manual, UseCase, API, ActionSpec, ActionGateway]
timestamp: 2026-06-20T00:12:00+09:00
boi_id: boi:public:boi-wiki-manual:use-cases:api-doc-to-action-spec
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
    ref: boi:public:harness:action-authoring-harness
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

API Doc to Action Spec은 사용자가 기존 시스템 API 문서를 주면 agent가 BoI Wiki Action Gateway에서 다룰 수 있는 실행 명세 초안으로 바꾸는 사례다.

# User Request

```text
이 API 문서를 BoI Action Spec 초안으로 만들어줘.
```

# Agent Flow

1. Local workspace에서는 `boi-action-author` skill을 사용한다.
2. connector kind를 `api`, `webhook`, `mcp`, `langflow`, `manual`, `event_broker`, `boi_writer` 중 하나로 분류한다.
3. request/response schema, example, approval policy, security notes, catalog patch draft를 만든다.
4. token, password, 실제 secret은 문서에 넣지 않는다.
5. shared 반영은 promotion draft와 사용자 승인 이후에만 한다.

# Required Output

- Public action spec draft
- Catalog patch draft
- Safety defaults: `enabled=false`, `auto_dispatch=false`, high risk approval
- Test and smoke checklist

# Citations

- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
- [Multi-action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
- [Public Action Library](/public/actions/overview.md)
