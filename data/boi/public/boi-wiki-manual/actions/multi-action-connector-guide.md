---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Multi-action Connector Guide
description: API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 같은 catalog/runtime 규칙으로 작성하는 가이드
tags: [Manual, ActionGateway, API, Webhook, MCP, Langflow, Manual]
timestamp: 2026-06-18T15:10:00+09:00
boi_id: boi:public:boi-wiki-manual:actions:multi-action-connector-guide
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
    ref: harness/action-authoring-harness.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Langflow는 action connector 중 하나다. SOP workflow는 API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 모두 같은 catalog와 Action Gateway 규칙으로 연결한다.

# Common Fields

모든 action은 `action_key`, `connector_kind`, `type`, `execution_mode`, `doc_ref`, `event_types`, `risk_level`, `approval_required`, `auto_dispatch`, `dry_run_default`, `owner`를 가져야 한다.

# Connector Rules

| connector_kind | Required spec |
|---|---|
| `api` | method, url, auth, headers, request_schema, response_schema, curl, health_check |
| `webhook` | inbound/outbound direction, source, payload mapping, auth, retry/security policy |
| `mcp` | mcp_server, tool_name, transport, input_schema, output_schema, example_tool_call |
| `langflow` | flow_name, endpoint_name, required_components, input template, result policy |
| `manual` | assignee_role, checklist, approval/completion contract |
| `event_broker` | emits_event_type, body template, trace policy |
| `boi_writer` | materialization target, metadata policy, enrichment policy |

# High-risk Rule

고위험 system action은 자동 실행하지 않는다. 대응 manual approval action을 `requires_manual_action`으로 참조하고, Action Gateway와 endpoint 양쪽에서 승인 여부를 확인한다.

# Citations

- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
