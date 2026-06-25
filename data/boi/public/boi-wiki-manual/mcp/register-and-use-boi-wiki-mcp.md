---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki MCP 등록과 사용
description: agent가 BoI Wiki를 MCP server 하나로 검색, workflow 실행, action 탐색, draft 생성, promotion 게시하도록 등록하는 방법
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

BoI Wiki MCP는 agent-facing 표준 인터페이스다. API를 직접 외우는 대신 MCP server를 등록하면 BoI 문서, OKF graph, workflow status, action catalog, source draft 저장, Team/Public promotion submit을 같은 방식으로 사용할 수 있다.

# Endpoint

| Purpose | URL |
|---|---|
| Human status page | `http://localhost:8200/` |
| MCP Streamable HTTP | `http://localhost:8200/mcp` |
| Action Gateway bridge 호환 | `http://localhost:8200/api/mcp/call` |
| Health check | `http://localhost:8200/health` |

`/mcp`는 UI가 아니라 MCP Streamable HTTP endpoint다. 브라우저 주소창이나 일반 `curl`로 열면 MCP `Accept` header가 없어서 `406 Not Acceptable`이 나올 수 있다. 이 상태는 서버 장애가 아니다. 사람이 확인할 때는 `http://localhost:8200/` 상태 페이지와 아래 검증 스크립트를 사용한다.

# Codex 등록

Codex에서 BoI Wiki MCP를 사용할 때 이름은 `boi-wiki-mcp`, transport는 Streamable HTTP, URL은 `http://localhost:8200/mcp`로 둔다. 등록 후 `boi_search`, `boi_get`, `workflow_status`, `action_invoke`, `event_type_draft_create` 같은 tool이 보이면 정상이다.

BoI Agent 관련 tool은 BoI API와 같은 guardrail을 사용한다. `boi_search`는 document-only search이고, 복합 업무 탐색은 `ontology_search`, 현재 페이지 기반 질의응답은 `boi_agent_chat`, 담당 업무 확인은 `agent_inbox`를 사용한다. `boi_agent_chat`은 Web Pet Agent와 같은 `boi-agent.response.v1` 응답 계약을 반환하며 `answer_markdown`, `links`, `citations`, `artifacts`, `execution_cards`, `guardrails_applied`를 포함한다. 신규 Event Type은 `event_type_draft_create`로 draft를 만들고 `event_type_draft_validate`로 검증한 뒤, 별도 승인 후 `event_type_draft_apply`로 catalog에 반영한다. `manual_handoff_complete`, `event_type_draft_create`, `event_type_draft_apply`, apply, promotion, action 실행 계열은 사용자 확인과 RBAC/ACL 검증 없이는 실행되지 않는다.

```json
{
  "mcpServers": {
    "boi-wiki-mcp": {
      "type": "http",
      "url": "http://localhost:8200/mcp"
    }
  }
}
```

# Claude Desktop 등록

Claude Desktop에서 remote/HTTP MCP server를 추가할 때 이름은 `boi-wiki-mcp`, transport는 Streamable HTTP, URL은 `http://localhost:8200/mcp`로 둔다.

```json
{
  "mcpServers": {
    "boi-wiki-mcp": {
      "type": "http",
      "url": "http://localhost:8200/mcp"
    }
  }
}
```

등록 후 tool 목록에 `boi_search`, `boi_get`, `workflow_status`, `action_invoke`, `boi_agent_chat`, `ontology_search`, `agent_inbox`가 보이면 정상이다. 클라이언트 버전에 따라 설정 파일 위치나 transport key 이름은 다를 수 있지만, endpoint는 항상 `http://localhost:8200/mcp`다.

# Cursor 등록

Cursor에서도 같은 MCP server를 등록한다. workspace 또는 user MCP 설정에 아래 값을 넣고 MCP 목록을 refresh한다.

```json
{
  "mcpServers": {
    "boi-wiki-mcp": {
      "type": "http",
      "url": "http://localhost:8200/mcp"
    }
  }
}
```

Cursor UI에서 static resource가 비어 보일 수 있다. BoI Wiki MCP는 정적 resource 대신 resource template과 tools를 중심으로 노출한다.

# Tools

| Tool | Use |
|---|---|
| `boi_search` | 권한 내 BoI 검색 |
| `boi_get` | 단일 BoI 문서 조회 |
| `okf_graph_doc` | 특정 문서 outgoing/backlink 조회 |
| `actions_search` / `action_get` | multi-action catalog 탐색 |
| `action_invoke` | Action Gateway 경유 실행. 실제 실행(`dry_run=false`)은 `user_confirmed=true`가 없으면 MCP 단계에서 차단 |
| `workflow_start` / `workflow_status` | SOP 기반 workflow 실행/상태 확인. `workflow_start`는 entry event를 발행하므로 API/MCP 모두 `user_confirmed=true`가 없으면 차단 |
| `boi_agent_chat` / `boi_agent_suggestions` | Native BoI Agent의 page-aware 질의응답과 현재 화면 기반 추천 질문 |
| `ontology_search` | Dictionary, SOP workflow, Event Type, Action Spec, BoI 문서, runtime evidence를 함께 보는 업무 지식 그래프 검색 |
| `dictionary_resolve` / `dictionary_terms` | private → team → public 우선순위로 업무 용어와 alias 해석 |
| `agent_memory_search` | 사번별 private Agent Memory BoI 검색 |
| `agent_inbox` / `manual_handoff_complete` | 담당 action inbox 조회와 사용자 확인된 manual handoff 완료 기록 |
| `event_type_draft_create` / `event_type_drafts` / `event_type_draft_validate` / `event_type_draft_apply` | 신규 Event Type draft 작성, 조회, 검증, 사용자 승인된 catalog 반영 |
| `source_preview` / `doc_body_preview` | source/body 수정 전 preview와 validation feedback |
| `source_apply` / `doc_body_apply` | 사용자 승인된 source/body 수정 apply와 자동 commit |
| `promotion_submit` | 사용자 승인된 Team/Public promotion candidate 원격 검증/즉시 게시. `user_confirmed=true`가 없으면 MCP 단계에서 차단 |
| `promotion_status` | promotion validation, publish, HOTL, commit 상태 조회 |

# Resources and Prompts

- Resource 예: `boi://docs/boi:public:sop:equipment-abnormal-response`
- Resource 예: `boi://actions/mcp.boi_search.sample`
- Resource 예: `boi://search/ontology/설비%20이상`
- Prompt 예: `create_sop_from_source`, `author_action_spec`, `build_langflow_boi_flow`

현재 프로토콜 기준 기대값은 `tools: 26`, `resources: 0`, `resource_templates: 5`, `prompts: 5`다. `resources: 0`은 오류가 아니다. 정적 resource를 미리 노출하지 않고 `boi://docs/{boi_id}`, `boi://folders/{folder}`, `boi://actions/{action_key}`, `boi://workflows/{workflow_key}/status/{trace_id}`, `boi://search/ontology/{query}` resource template으로 필요한 문서와 검색 결과를 읽는다.

검색 tool은 목적별로 나눠 쓴다. 단순 BoI 문서 목록이 필요하면 `boi_search`를 사용한다. SOP, Event, Action, Dictionary, runtime evidence를 관계까지 포함해 탐색하려면 `ontology_search`를 사용한다. 현재 페이지를 바탕으로 답변이나 산출물이 필요하면 `boi_agent_chat`을 사용한다. 세 경로는 모두 BoI API의 ACL/RBAC guardrail을 통과하므로 MCP client가 Web UI보다 더 넓은 문서를 볼 수 없다.

# Validation

```bash
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
```

상세 확인과 client 등록 전 점검은 다음 명령을 사용한다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --details \
  --client-checklist
```

정상 결과는 protocol count와 bridge 호출이 모두 성공이어야 한다. `boi_search`로 `employee_id=100001`, query `SOP`를 검색했을 때 BoI Wiki 문서가 반환되고, `ontology_search`와 `boi_agent_chat` smoke가 같은 권한 범위에서 응답하면 agent가 실제 Wiki와 Native BoI Agent에 접근 가능한 상태다.

# Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `http://localhost:8200/`가 열리지 않음 | MCP container 또는 port publish 문제 | `docker compose ps boi-wiki-mcp`, `curl http://localhost:8200/health` 확인 |
| `/mcp`가 `406` 반환 | 일반 브라우저/curl이 MCP Accept header를 보내지 않음 | 정상일 수 있음. MCP client나 검증 스크립트로 확인 |
| root가 `404` | 구버전 image가 떠 있거나 rebuild 전 상태 | `docker compose up -d --build boi-wiki-mcp` |
| `ClosedResourceError` 로그 | MCP stream client가 연결을 닫을 때 생기는 benign disconnect 로그일 수 있음 | protocol check가 성공하면 장애로 보지 않음. 반복 실패와 함께 발생하면 client 설정 확인 |
| port 충돌 | 다른 process가 8200 사용 | `.env`의 `BOI_WIKI_MCP_PORT`를 바꾸고 client URL도 같이 변경 |
| bridge `401` | service token 불일치 | `.env`와 호출 header `x-service-token` 확인 |

# Runtime Evidence

상태 페이지는 서버 health뿐 아니라 실제 MCP capabilities 목록을 보여준다. `tools=26`, `resource_templates=5`, `prompts=5`, `resources=0`이 현재 기준이며, `resources=0`은 정적 resource 대신 resource template을 쓰는 설계라서 정상이다. 상태 페이지의 목록에는 `boi_agent_chat`, `ontology_search`, `agent_inbox`, `manual_handoff_complete`, Event Type draft tool이 함께 보여야 한다.

![BoI Wiki MCP Status capabilities](/public/boi-wiki-manual/_media/browser/mcp-status/20260619-151048-boi-wiki-mcp-status-capabilities-current-1440x1000-89caadae3b92.png)

# Citations

- [MCP BoI Search Action Spec](/public/actions/mcp/boi-search-sample.md)
- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
- [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
