---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Langflow Reference Flow 호출 예시
description: Langflow reference flow에 event와 payload를 전달하는 connector 예시
tags: [Langflow, Webhook, ReferenceFlow]
timestamp: 2026-06-17T12:14:00+09:00
boi_id: boi:public:actions:langflow:reference-flow
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: langflow.boi.reference_flow
connector_kind: langflow
execution_mode: gateway
event_types: [meeting.closed.v1, action.created.v1, report.requested.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [event, payload]
  optional: [flow_id]
result_contract:
  status: invoked
  fields: [http_status, response]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

Gemma OpenAI-compatible LLM 설정을 가진 Langflow reference flow와 연결하는 예시다.
