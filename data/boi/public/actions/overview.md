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

이 라이브러리는 [Event Router](/public/actions/event-broker/publish-event.md)와 [Action Gateway](/public/actions/boi-writer/materialize-event.md)가 실행할 수 있는 action, 그리고 사람이 수행해야 하는 manual action을 public OKF 문서로 정리한다.

# Categories

- [BoI Writer](/public/actions/boi-writer/materialize-event.md): Event를 BoI로 자산화하는 connector
- [Event Broker](/public/actions/event-broker/publish-event.md): workflow event 발행 action
- [API Actions](/public/actions/api/request-trend-history.md): 사내 시스템 API 또는 PoC API action
- [Webhook Actions](/public/actions/webhook/inbound-external-event.md): inbound/outbound webhook action
- [MCP Actions](/public/actions/mcp/boi-search-sample.md): MCP bridge/tool action
- [BoI Wiki MCP Server](/public/actions/mcp/boi-wiki-server.md): agent-facing MCP server
- [Langflow Actions](/public/actions/langflow/reference-flow.md): Langflow webhook flow action
- [Manual Actions](/public/actions/manual/confirm-alarm-context.md): 사람이 판단, 승인, 현장 조치, 완료 확인하는 action

# Operating Rule

이 문서는 실행 권한이 아니라 명세다. 실제 실행은 `data/action_catalog/actions.yaml` allowlist, Action Gateway, approval policy가 통제한다.

# Citations

[1] [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)
