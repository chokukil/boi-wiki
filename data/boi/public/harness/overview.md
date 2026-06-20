---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: BoI Agent Harness Overview
description: SOP, Action, Web validated edit 작업을 모든 agent가 같은 방식으로 수행하기 위한 public harness 진입점
tags: [Harness, Agent, SOP, Action, Edit]
timestamp: 2026-06-18T00:45:00+09:00
boi_id: boi:public:harness:overview
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: harness/README.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Agent Harness는 Codex, Claude, Langflow, Custom Agent가 BoI Wiki, Event Broker, Action Gateway를 같은 방식으로 다루도록 하는 운영 기준이다.

# Harness Documents

- [Web Validated Editing Guide](/public/harness/web-draft-editing-guide.md)
- [SOP Authoring Harness](/public/harness/sop-authoring-harness.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
- [Agent Harness SOP](/public/public-sop-agent-harness.md)
- [BoI Wiki Manual Overview](/public/boi-wiki-manual/overview.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)

# Operating Rule

Source/body 직접 수정은 preview, validation, apply, auto-commit 경로를 사용한다. Team/Public promotion은 사용자의 preview 승인과 원격 자동 검증을 통과하면 즉시 게시되며, 품질/정책 판단은 HOTL로 사후 개입한다.

Codex skill은 얇은 bootstrap으로 유지하고, 상세 절차는 BoI Wiki MCP resource와 public harness 문서를 우선 읽는다.

# Citations

- Repo source: `harness/README.md`
