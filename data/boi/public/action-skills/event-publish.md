---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-skill
title: Event Publish Action Skill
description: Agent가 다음 Event 발행을 실행 후보로 제안할 때 사용하는 Action Skill
tags: [ActionSkill, EventBroker, Agent, Confirmation]
timestamp: 2026-06-27T11:40:00+09:00
boi_id: boi:public:action-skills:event-publish
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
skill_key: event.publish
source_refs:
  - type: catalog
    ref: data/action_skill_catalog/skills.yaml#event.publish
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

`event.publish`는 Agent가 다음 Event를 발행할 수 있는지 판단할 때 쓰는 업무 의미다. 실제 발행은 즉시 실행하지 않고 confirmation card와 RBAC/ACL/safety gate를 통과해야 한다.

# UX Rule

일반 사용자 UI에서는 `dry-run`이나 `invoke` 대신 “먼저 확인”, “요청 실행”, “승인 필요” 같은 표현을 쓴다.
