---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Context Pack
description: 특정 업무를 수행하기 위해 필요한 SOP, Event, Action, BoI 링크를 agent-ready context pack으로 묶는 사례
tags: [Manual, UseCase, ContextPack, Agent, OKF]
timestamp: 2026-06-20T00:13:00+09:00
boi_id: boi:public:boi-wiki-manual:use-cases:agent-context-pack
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:local-private:overview
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Agent Context Pack은 회의, 장애 대응, 보고서, SOP 작성 같은 특정 업무를 위해 필요한 BoI 문서와 실행 맥락을 링크 중심으로 묶는 사례다.

# User Request

```text
원격 BoI Wiki를 검색해서 이번 업무용 context pack을 만들어줘.
```

# Agent Flow

1. Local workspace에서는 `boi-context-pack-builder` skill을 사용한다.
2. Local docs를 먼저 읽고, MCP가 있으면 shared SOP/Event/Action/Workflow Status를 조회한다.
3. 전문 덤프 대신 링크, 짧은 요약, open gap, 다음 agent action을 기록한다.
4. Local Private 원본은 원격으로 보내지 않는다.

# Context Pack Sections

- Purpose
- Relevant BoIs
- SOP and stage refs
- Event Types
- Actions and manual handoffs
- Open gaps
- Suggested next agent actions
- Citations

# Citations

- [Local Private 시작하기](/public/boi-wiki-manual/local-private/overview.md)
- [MCP 없이도 쓰는 BoI Wiki Local](/public/boi-wiki-manual/local-private/mcp-optional.md)
- [BoI Agent Harness Overview](/public/harness/overview.md)
