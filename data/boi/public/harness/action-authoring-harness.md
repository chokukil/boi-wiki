---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Action Authoring Harness
description: API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 같은 방식으로 정의하는 기준
tags: [Harness, ActionGateway, API, Webhook, MCP, Langflow, Manual]
timestamp: 2026-06-18T00:48:00+09:00
boi_id: boi:public:harness:action-authoring-harness
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

Action Authoring Harness는 실행 가능한 action spec과 `data/action_catalog/actions.yaml` patch draft를 일관되게 만들기 위한 기준이다. Langflow는 connector 중 하나이며 기본값이 아니다.

# Common Fields

`action_key`, `connector_kind`, `type`, `execution_mode`, `doc_ref`, `event_types`, `risk_level`, `approval_required`, `auto_dispatch`, `dry_run_default`, `owner`는 모든 action에 필요하다.

# Connector Requirements

- API/Webhook: method, url, auth, headers, request_schema, response_schema, examples, curl, health_check
- MCP: mcp_server, tool_name, transport, input_schema, output_schema, example_tool_call
- Langflow: flow_name, endpoint_name, run_url, required_components, input_value_template, result_boi_policy
- Manual: assignee_role, checklist, completion_contract, approval_policy
- Event Broker: emits_event_type, event_body_template, trace_policy
- BoI Writer: materialization_policy, metadata_policy, enrichment_policy

# Safety Defaults

신규 action은 `enabled=false`, `auto_dispatch=false`, `dry_run_default=true`로 시작한다. 고위험 action은 `requires_manual_action` 없이는 활성화할 수 없다.

# Authoring Flow

1. [BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md) `actions_search`로 기존 action을 찾는다.
2. 실제 업무에 가장 좁고 적합한 connector_kind를 고른다.
3. public action-spec BoI 문서와 catalog patch draft를 만든다.
4. connector별 테스트와 runtime smoke evidence를 남긴다.
5. 공개 문서와 log에 secret을 남기지 않는다.

# Example

- [Public Action Library](/public/actions/overview.md)
- [Multi-action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)

# Citations

- [Harness Overview](/public/harness/overview.md)
