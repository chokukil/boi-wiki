---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Platform Team Kafka Event Broker SOP
description: PoC Kafka topic과 Event Adapter 운영 기준
tags: [Kafka, EventBroker, SOP]
timestamp: 2026-06-16T10:20:00+09:00
boi_id: boi:team:platform:kafka-sop-v0.1
visibility: team
team_id: platform
classification: internal
owner: platform-team
author:
  type: human
  agent_id: seed
acl_policy: acl:team:platform
status: reviewed
source_refs:
  - type: platform-sop
    ref: kafka-poc
review:
  reviewer: platform-lead
  reviewed_at: 2026-06-16T10:20:00+09:00
  review_status: reviewed
---

# Summary

Kafka는 업무 이벤트 발생 시점을 Agent Flow에 전달하는 Event Broker 역할을 한다.

# Topics

- boi.events
- boi.audit
- boi.dead-letter
