---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki Manual Overview
description: BoI Wiki, MCP, multi-action runtime, Langflow, draft editing, OKF media 운영 가이드 진입점
tags: [Manual, BoIWiki, MCP, Action, Langflow, OKF]
timestamp: 2026-06-18T15:00:00+09:00
boi_id: boi:public:boi-wiki-manual:overview
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

BoI Wiki는 OKF 기반 LLM Wiki와 실행 가능한 workflow runtime을 함께 제공한다. 사용자는 문서를 읽고, agent는 [BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)를 통해 같은 지식을 검색하고 workflow/action/draft 작업을 수행한다.

# Core Manuals

- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
- [Langflow connected flow guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
- [SOP workflow 작성과 runtime 연결](/public/boi-wiki-manual/sop-workflows/create-and-connect-sop.md)
- [OKF media와 Browser screenshot 규칙](/public/boi-wiki-manual/media/okf-media-and-screenshots.md)
- [Web draft와 Git commit 정책](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
- [SSO와 권한 체계](/public/boi-wiki-manual/security/sso-and-permissions.md)

# Operating Model

1. OKF Markdown 문서와 action catalog가 source of truth다.
2. Web/MCP 저장은 draft-only다.
3. Codex/Claude 같은 agent가 draft를 검증, 적용, 테스트, commit한다.
4. Langflow는 실행 채널 중 하나이며 API, Webhook, MCP, Manual, Event Broker action과 같은 수준으로 관리한다.

# Citations

- [BoI Agent Harness Overview](/public/harness/overview.md)
- [Public Action Library](/public/actions/overview.md)
