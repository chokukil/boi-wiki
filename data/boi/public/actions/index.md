---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Public Action Library
description: Action Gateway와 사람이 사용할 public action spec의 진입점
tags: [ActionGateway, PublicActions, API, Webhook, MCP, Manual]
timestamp: 2026-06-17T12:00:00+09:00
boi_id: boi:public:actions:index
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: planning
    ref: public-actions-plan
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

이 라이브러리는 Event Router와 Action Gateway가 실행할 수 있는 action, 그리고 사람이 수행해야 하는 manual action을 public OKF 문서로 정리한다.

# Categories

- `public/actions/boi-writer`: Event를 BoI로 자산화하는 connector
- `public/actions/event-broker`: workflow event 발행 action
- `public/actions/api`: 사내 시스템 API 또는 PoC mock API action
- `public/actions/webhook`: inbound/outbound webhook action
- `public/actions/mcp`: MCP bridge/tool action
- `public/actions/langflow`: Langflow webhook flow action
- `public/actions/manual`: 사람이 판단, 승인, 현장 조치, 완료 확인하는 action

# Operating Rule

이 문서는 실행 권한이 아니라 명세다. 실제 실행은 `data/action_catalog/actions.yaml` allowlist, Action Gateway, approval policy가 통제한다.
