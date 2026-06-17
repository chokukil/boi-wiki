---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Langflow 회의 BoI Writer Flow 호출 예시
description: Langflow Webhook Flow를 연결하는 connector 예시
tags: [Langflow, Webhook, BoIWriter]
timestamp: 2026-06-17T12:13:00+09:00
boi_id: boi:public:actions:langflow:meeting-writer-sample
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: langflow.meeting_writer.sample
connector_kind: langflow
execution_mode: gateway
event_types: [meeting.closed.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [langflow_flow_id]
  optional: [payload]
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

Flow ID를 준비하고 catalog에서 enabled=true로 바꾸면 Event Router가 호출할 수 있다.
