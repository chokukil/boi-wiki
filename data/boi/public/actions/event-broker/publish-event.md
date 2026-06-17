---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: Event Broker로 이벤트 발행
description: Agent, Langflow, API에서 업무 이벤트를 Kafka Event Broker로 발행하는 공통 action
tags: [ActionGateway, EventBroker, Kafka]
timestamp: 2026-06-17T12:02:00+09:00
boi_id: boi:public:actions:event-broker:publish-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: boi.publish_event
connector_kind: event_broker
execution_mode: gateway
event_types: [manual.input.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [event_type, payload]
  optional: [source_refs]
result_contract:
  status: event_published
  fields: [event_id, trace_id, topic]
source_refs:
  - type: action_catalog
    ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

수동 입력이나 외부 도구가 다음 workflow event를 깨울 때 사용한다.
