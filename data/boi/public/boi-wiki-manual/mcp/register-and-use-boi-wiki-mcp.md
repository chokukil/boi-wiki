---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki MCP 등록과 사용
description: agent가 BoI Wiki를 MCP server 하나로 검색, workflow 실행, action 탐색, draft 생성하도록 등록하는 방법
tags: [Manual, MCP, Agent, BoIWiki]
timestamp: 2026-06-18T15:05:00+09:00
boi_id: boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: action-spec
    ref: boi:public:actions:mcp:boi-search-sample
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Wiki MCP는 agent-facing 표준 인터페이스다. API를 직접 외우는 대신 MCP server를 등록하면 BoI 문서, OKF graph, workflow status, action catalog, draft 저장 prompt를 같은 방식으로 사용할 수 있다.

# Endpoint

| Purpose | URL |
|---|---|
| MCP Streamable HTTP | `http://localhost:8200/mcp` |
| Action Gateway bridge 호환 | `http://localhost:8200/api/mcp/call` |
| Health check | `http://localhost:8200/health` |

# Tools

| Tool | Use |
|---|---|
| `boi_search` | 권한 내 BoI 검색 |
| `boi_get` | 단일 BoI 문서 조회 |
| `okf_graph_doc` | 특정 문서 outgoing/backlink 조회 |
| `actions_search` / `action_get` | multi-action catalog 탐색 |
| `action_invoke` | Action Gateway 경유 실행 |
| `workflow_start` / `workflow_status` | SOP 기반 workflow 실행/상태 확인 |
| `source_create_draft` / `doc_body_create_draft` | draft-only 수정 요청 |

# Resources and Prompts

- Resource 예: `boi://docs/boi:public:sop:equipment-abnormal-response`
- Resource 예: `boi://actions/mcp.boi_search.sample`
- Prompt 예: `create_sop_from_source`, `author_action_spec`, `build_langflow_boi_flow`

# Validation

```bash
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
```

# Runtime Evidence

![BoI Wiki MCP Server Action Spec](/public/boi-wiki-manual/_media/screenshots/boi-wiki-mcp-server-spec-20260618.png)

# Citations

- [MCP BoI Search Action Spec](/public/actions/mcp/boi-search-sample.md)
- [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
