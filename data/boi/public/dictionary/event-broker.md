---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Event Broker
description: 업무 시점을 event로 발행하고 workflow runtime에 전달하는 계층
tags: [Dictionary, BoIWiki, EventBroker]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:event-broker
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Event Broker
definition: 업무에서 의미 있는 시점을 event로 발행하고 Event Router/Action Gateway로 전달하는 runtime 계층. 현재 PoC에서는 Kafka가 주요 broker 역할을 한다.
aliases: [Kafka Event Broker, 이벤트 브로커, 이벤트 발행, event publish, Kafka]
domain: boi-runtime
examples:
  - Event Broker가 equipment.alarm.raised.v1을 발행하면 SOP workflow가 시작된다.
links:
  - /public/actions/event-broker/publish-event.md
  - /public/boi-wiki-manual/actions/multi-action-connector-guide.md
related_terms: [Action Gateway, Event Type, Workflow]
source_refs:
  - {type: internal-doc, ref: "/public/boi-wiki-manual/actions/multi-action-connector-guide.md"}
---

# Summary

Event Broker는 업무 시점을 event로 바꾸는 계층이다. BoI Wiki에서 event는 SOP stage, Action Gateway 실행, Generated BoI와 연결된다.

# BoI Usage

- [workflow event publish](/public/actions/event-broker/publish-event.md)
- [multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)

# Citations

- [Multi Action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
