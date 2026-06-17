---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: MCP 기반 BoI 검색 Tool 호출 예시
description: MCP Bridge를 통해 BoI 검색 tool을 호출하는 connector 예시
tags: [MCP, BoIWiki, Search]
timestamp: 2026-06-17T12:15:00+09:00
boi_id: boi:public:actions:mcp:boi-search-sample
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: mcp.boi_search.sample
connector_kind: mcp
execution_mode: gateway
event_types: [report.requested.v1, maintenance.guide.requested.v1]
risk_level: low
approval_required: false
dry_run_default: true
payload_contract:
  required: [query, employee_id]
  optional: [allowed_visibility]
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

권한 있는 BoI를 lazy loading하기 위한 MCP search connector 명세다.
