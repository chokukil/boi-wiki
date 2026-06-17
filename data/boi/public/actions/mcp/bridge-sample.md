---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: MCP Bridge 호출 예시
description: MCP 서버와 tool 호출을 Action Gateway allowlist로 관리하는 connector 예시
tags: [MCP, Bridge, ActionGateway]
timestamp: 2026-06-17T12:16:00+09:00
boi_id: boi:public:actions:mcp:bridge-sample
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: connector.mcp.sample
connector_kind: mcp
execution_mode: gateway
event_types: [report.requested.v1]
risk_level: medium
approval_required: false
dry_run_default: true
payload_contract:
  required: [query, employee_id]
  optional: [server, tool]
result_contract:
  status: mcp_invoked
  fields: [response]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

PoC 기본값은 비활성화이며 MCP Bridge가 준비되면 활성화한다.
