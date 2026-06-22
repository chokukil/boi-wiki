---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Action Gateway
description: allowlisted API/Webhook/MCP/Langflow/Manual/Event Broker action을 실행·기록하는 계층
tags: [Dictionary, BoIWiki, ActionGateway]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:action-gateway
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Action Gateway
definition: action catalog에 등록된 allowlisted connector action을 실행하고 결과를 action log에 남기는 runtime 계층. 고위험 action은 approval policy를 적용한다.
aliases: [액션 게이트웨이, Action 실행, connector gateway, action invoke]
domain: boi-runtime
examples:
  - Action Gateway는 Langflow, API, MCP, Manual action을 같은 trace에 기록한다.
links:
  - /public/actions/overview.md
  - /public/boi-wiki-manual/actions/multi-action-connector-guide.md
related_terms: [Event Broker, Manual Handoff, Action Spec]
source_refs:
  - {type: internal-doc, ref: "/public/actions/overview.md"}
---

# Summary

Action Gateway는 BoI Wiki workflow에서 실행 가능한 action을 담당한다. API, webhook, MCP, Langflow, manual, event broker, BoI writer connector를 같은 catalog/approval/logging 기준으로 다룬다.

# BoI Usage

- [Public Action Library](/public/actions/overview.md)
- [Multi Action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)

# Citations

- [Public Action Library](/public/actions/overview.md)
