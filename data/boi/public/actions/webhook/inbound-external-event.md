---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: 외부 Webhook 이벤트 수신
description: 외부 시스템이 BoI API inbound webhook으로 업무 event를 전달하는 명세
tags: [Webhook, EventBroker, Inbound]
timestamp: 2026-06-17T12:12:00+09:00
boi_id: boi:public:actions:webhook:inbound-external-event
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: webhook.inbound.external_event
connector_kind: webhook
execution_mode: inbound
event_types: [external.webhook.received.v1]
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: [event_type, payload]
  optional: [source_refs, trace_id]
result_contract:
  status: event_published
  fields: [event_id, trace_id, topic]
source_refs:
  - type: route
    ref: /api/webhooks/{source}
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Usage

사내 시스템 또는 테스트 스크립트가 webhook으로 업무 event를 발행할 때 사용한다.
