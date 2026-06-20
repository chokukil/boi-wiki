---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: MCP 없이도 쓰는 BoI Wiki Local
description: MCP 설정을 모르는 일반 사용자를 위한 Local Private fallback 기준
tags: [Manual, MCP, LocalPrivate, Fallback]
timestamp: 2026-06-19T18:03:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:mcp-optional
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
    ref: boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

MCP는 원격 BoI Wiki를 편하게 쓰는 선택 기능이다. Local Private BoI 작성은 MCP 없이도 가능하다.

# Without MCP

agent는 local `index.md`, `log.md`, private folder, 사용자가 제공한 파일과 링크를 기반으로 작업한다. 원격 문서가 필요하면 사용자가 Web BoI Wiki 링크나 복사한 내용을 제공한다.

# With MCP

agent는 원격 `boi-wiki-mcp`로 shared SOP, Event Type, Action Spec, Workflow Status를 검색한다. 공식 사용자 경로에서 local MCP 서버는 요구하지 않는다. 그래도 Local Private 원문 전송과 Team/Public promotion submit은 사용자 명시 승인 없이는 금지된다.

# Use Cases

- [SOP Flow Visualization](/public/boi-wiki-manual/use-cases/sop-flow-visualization.md)
- [Event-to-Action Workflow Planning](/public/boi-wiki-manual/use-cases/event-to-action-workflow-planning.md)
- [API Doc to Action Spec](/public/boi-wiki-manual/use-cases/api-doc-to-action-spec.md)
- [Agent Context Pack](/public/boi-wiki-manual/use-cases/agent-context-pack.md)

# Citations

- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [Codex Setup](/public/boi-wiki-manual/local-private/codex-setup.md)
