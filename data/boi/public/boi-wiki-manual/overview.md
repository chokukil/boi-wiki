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
- [Local Private 시작하기](/public/boi-wiki-manual/local-private/overview.md)
- [OKF media와 Browser screenshot 규칙](/public/boi-wiki-manual/media/okf-media-and-screenshots.md)
- [Web draft와 Git commit 정책](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
- [SSO와 권한 체계](/public/boi-wiki-manual/security/sso-and-permissions.md)

# Operating Model

1. OKF Markdown 문서와 action catalog가 source of truth다.
2. Web/MCP 저장은 draft-only다.
3. Codex/Claude 같은 agent가 draft를 검증, 적용, 테스트, commit한다.
4. Langflow는 실행 채널 중 하나이며 API, Webhook, MCP, Manual, Event Broker action과 같은 수준으로 관리한다.

# Local Private

Local Private은 개인 PC의 `boi-wiki-local` workspace에만 저장되는 개인 BoI 영역이다. 일반 사용자는 MCP나 Git을 몰라도 agent 하네스가 OKF 구조, lifecycle metadata, self-check, 승격 draft 절차를 수행한다.

- [Codex로 BoI Wiki Local 사용하기](/public/boi-wiki-manual/local-private/codex-setup.md)
- [MCP 없이도 쓰는 BoI Wiki Local](/public/boi-wiki-manual/local-private/mcp-optional.md)
- [Local Private 승격과 공유 절차](/public/boi-wiki-manual/local-private/promotion-flow.md)
- [Private BoI 보관 정책](/public/boi-wiki-manual/local-private/private-lifecycle.md)

# Citations

- [BoI Agent Harness Overview](/public/harness/overview.md)
- [Public Action Library](/public/actions/overview.md)
