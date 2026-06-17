---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Event를 BoI로 자산화
description: Event Broker에서 받은 업무 이벤트를 OKF 기반 BoI 문서로 생성하는 1급 BoI Writer connector
tags: [ActionGateway, BoIWriter, EventBroker]
timestamp: 2026-06-17T12:01:00+09:00
boi_id: boi:public:actions:boi-writer:materialize-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: boi.materialize_event
connector_kind: boi_writer
execution_mode: gateway
event_types: ["*"]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [event_id, event_type, payload]
  optional: [source_refs, trace_id, actor]
result_contract:
  status: materialized
  fields: [boi_id, boi_uri]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

Event Router가 모든 업무 이벤트에 대해 가장 먼저 호출해 event-linked Private BoI를 만든다.
