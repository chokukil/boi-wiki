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

BoI Wiki MCP는 agent-facing 표준 인터페이스다. API를 직접 외우는 대신 MCP server를 등록하면 BoI 문서, OKF graph, workflow status, action catalog, source draft 저장, Team/Public promotion submit을 같은 방식으로 사용할 수 있다. Web UI의 일반 사용자는 `BoI Wiki / SOP / Event Broker / Action / Advanced` 메뉴로 접근하고, MCP client는 같은 기능을 tool로 호출한다.

# Endpoint

| Purpose | URL |
|---|---|
| Human status page | `http://localhost:8200/` |
| MCP Streamable HTTP | `http://localhost:8200/mcp` |
| Action Gateway bridge 호환 | `http://localhost:8200/api/mcp/call` |
| Health check | `http://localhost:8200/health` |

`/mcp`는 UI가 아니라 MCP Streamable HTTP endpoint다. 브라우저 주소창이나 일반 `curl`로 열면 MCP `Accept` header가 없어서 `406 Not Acceptable`이 나올 수 있다. 이 상태는 서버 장애가 아니다. 사람이 확인할 때는 `http://localhost:8200/` 상태 페이지와 아래 검증 스크립트를 사용한다.

# Authentication

BoI Wiki MCP에는 두 호출 경로가 있다.

| Path | Purpose | Auth |
|---|---|---|
| `/mcp` | 표준 Streamable HTTP MCP endpoint | `MCP_REQUIRE_SERVICE_TOKEN=true`이면 `x-service-token` 또는 `Authorization: Bearer <token>` 필요 |
| `/api/mcp/call` | 테스트/호환용 bridge endpoint | 항상 `x-service-token` 필요 |

로컬 개발처럼 신뢰된 장비에서만 열 때는 `MCP_REQUIRE_SERVICE_TOKEN=false`로 둘 수 있다. NAS나 사내 네트워크처럼 다른 사용자가 접근 가능한 endpoint로 열 때는 `.env`에 `MCP_REQUIRE_SERVICE_TOKEN=true`를 설정하고 `boi-wiki-mcp` 컨테이너를 재생성한다. 이 값이 켜진 상태에서 token 없이 `/mcp`를 호출하면 `401 MCP service token is required`가 정상이다.

MCP client가 custom header를 지원하면 다음 둘 중 하나를 보낸다.

- `x-service-token: <SERVICE_TOKEN>`
- `Authorization: Bearer <SERVICE_TOKEN>`

token 값은 Git, README, Wiki 문서, chat log에 남기지 않는다. 상태 페이지 `/health`와 `/status`의 `mcp_auth.required`가 현재 설정을 보여준다.

# Codex 등록

Codex에서 BoI Wiki MCP를 사용할 때 이름은 `boi-wiki-mcp`, transport는 Streamable HTTP, URL은 `http://localhost:8200/mcp`로 둔다. 등록 후 `boi_search`, `boi_get`, `workflow_status`, `action_invoke`, `boi_inbox`, `boi_inbox_report_get`, `boi_inbox_decision_preview`, `boi_inbox_decision_submit`, `sop_registration_plan`, `sop_registration_preview`, `event_publish_plan`, `event_pattern_preview`, `sop_run_history`, `sop_registration_draft_create`, `sop_registration_validate`, `sop_registration_publish`, `event_type_draft_create`, `workflow_definitions_search` 같은 tool이 보이면 정상이다.

BoI Agent 관련 tool은 BoI API와 같은 guardrail을 사용한다. `boi_search`는 document-only search이고, 복합 업무 탐색은 `ontology_search`, 현재 페이지 기반 질의응답은 `boi_agent_chat`, 담당 업무 보고서는 `boi_inbox`를 사용한다. `boi_inbox`는 검증된 보고서 BoI 링크와 우선순위, 사용자 링크를 반환하고, 승인이나 반려가 필요한 업무는 `boi_inbox_report_get`으로 결론, 개별 비교, 판단 근거, 유사 사례, 조치 후보를 먼저 확인한다. `boi_inbox_decision_preview`는 group 판단의 가능 여부를 확인하고, 고위험 bulk approve를 차단한다. 실제 기록은 `boi_inbox_decision_submit`으로 개별 task에 대해 `note`와 `user_confirmed=true`를 넘길 때만 가능하다. 기존 `agent_inbox*` tool은 한 릴리즈 동안 compatibility alias로 남긴다. 이 narrative는 LLM이 실제 WorkContextPack source id만 사용해 쓴 업무 요약이며, 준비되지 않았을 때는 상태 단어 목록을 fallback처럼 보여주지 않는다. `workflow_definitions_search`, `workflow_definition_get`, `workflow_definition_deduplicate`는 내부 실행 정의인 WorkflowDefinition을 다루는 Advanced/API 도구다. Web UI에서는 이를 독립 메뉴처럼 노출하지 않고 SOP 추가, BoI Wiki 탐색, Event/Action 카탈로그에서 재사용 후보로만 보여준다. 신규 등록은 기본적으로 `sop_registration_plan`과 `sop_registration_preview`로 자연어 요청을 Event/SOP/Action 후보, 추천 필드, 권한, 과거 이력으로 바꾼다. 이 흐름은 Web UI의 `/sops/new`와 같다. 업무 Event를 실제로 발생시키려는 요청은 `event_publish_plan`과 `event_publish_preview`로 기존 Event 후보와 연결 SOP를 확인한다. 기존 Event Stream 조건을 새 Event 정의로 승격하려면 `event_pattern_preview`로 샘플과 공통 조건을 확인하고, 사용자 확인 후에만 `event_pattern_promote_to_draft`를 호출한다. `sop_run_history`는 raw Event Stream이 아니라 SOP 기준 실행 카드와 Timeline 요약을 반환한다. `registration_plan`, `registration_verification_preview`, `registration_draft_create`, `sop_draft_create`, `action_draft_create`는 컴포넌트 단위 호환 도구로 유지한다. Action draft는 7종 connector(`api`, `mcp`, `webhook`, `manual`, `event_broker`, `boi_writer`, `langflow`) 중 하나를 `connector_kind`로 지정하고, API endpoint나 MCP tool 같은 종류별 설정은 `connector_config`로 전달한다. 이 도구들은 draft만 만들고 catalog를 즉시 바꾸지 않으며, MCP에서는 `user_confirmed=true` 없이는 생성도 차단된다. `registration_draft_validate`와 `sop_registration_validate`는 필수값을 검증하고, publish 도구들은 별도 사용자 확인 후 게시 요청만 수행한다. `boi_agent_chat`은 Web Pet Agent와 같은 입력 필드와 같은 `boi-agent.response.v1` 응답 계약을 반환한다. 응답에는 `answer_markdown`, `display_markdown`, `links`, `citations`, `artifacts`, `execution_cards`, `status_updates`, `status_events`, `tool_trace`, `evidence_ledger`, `affordances`, `answer_quality`, `access_summary`, `guardrails_applied`, `suggested_questions`, `event_context`, `workflow_definition_context`가 포함된다. 단, 사용자-facing 링크는 `user_links` 또는 `links`의 표시 라벨을 기준으로 BoI Wiki, BoI Inbox, SOP, Event Broker, Action 화면 중 하나로 연결해야 하며 WorkflowDefinition URL은 diagnostics나 내부 필드로만 다룬다. `boi_agent_approve`, `boi_inbox_decision_submit`, `manual_handoff_complete`, `sop_registration_draft_create`, `sop_registration_publish`, `registration_draft_create`, `sop_draft_create`, `action_draft_create`, `registration_draft_publish`, `event_pattern_promote_to_draft`, `event_type_draft_create`, `event_type_draft_apply`, apply, promotion, action 실행 계열은 사용자 확인과 RBAC/ACL 검증 없이는 실행되지 않는다.

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

등록 후 tool 목록에 `boi_search`, `boi_get`, `workflow_status`, `action_invoke`, `boi_agent_chat`, `ontology_search`, `boi_inbox`가 보이면 정상이다. 클라이언트 버전에 따라 설정 파일 위치나 transport key 이름은 다를 수 있지만, endpoint는 항상 `http://localhost:8200/mcp`다.

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
| `boi_agent_chat` / `boi_agent_suggestions` / `boi_agent_capabilities` / `boi_agent_approve` | Native BoI Agent의 page-aware 질의응답, 현재 화면 기반 추천 질문, Agent backend/contract discovery, execution card 승인 |
| `workflow_definitions_search` / `workflow_definition_get` / `workflow_definition_deduplicate` | 내부 WorkflowDefinition 조회, 상세 확인, 신규 등록 전 중복 후보 산출. Web UI에서는 SOP 추가나 BoI Wiki 탐색 후보로만 노출 |
| `event_skills_list` / `action_skills_list` | Event Skill과 Action Skill registry 조회 |
| `ontology_search` | Dictionary, SOP workflow, Event Type, Action Spec, BoI 문서, runtime evidence를 함께 보는 업무 지식 그래프 검색 |
| `dictionary_resolve` / `dictionary_terms` | private → team → public 우선순위로 업무 용어와 alias 해석 |
| `agent_memory_search` | 사번별 private Agent Memory BoI 검색 |
| `boi_inbox` / `boi_inbox_report_get` / `boi_inbox_decision_preview` / `boi_inbox_decision_submit` | BoI Inbox 보고서 목록, 검증된 보고서 BoI 조회, 승인/반려/보류/추가 근거 요청 검토와 기록. 고위험 group bulk approve는 차단하며, 실제 기록은 개별 task 사유와 `user_confirmed=true`가 있어야 한다. |
| `data_lake_status` / `data_lake_sources` / `data_lake_query_plan` / `data_lake_query_preview` / `data_lake_query_execute` / `data_lake_artifact_get` / `data_lake_import_sources` | Optional Data Lake 도구. PostgreSQL/MinIO가 없는 기본 profile에서는 disabled contract를 반환하며 BoI Wiki core를 실패시키지 않는다. 실행은 plan/preview 이후 `user_confirmed=true`가 필요하다. `data_lake_import_sources`는 선택한 source profile을 private OKF Data Context BoI로 materialize할 때만 사용한다. |
| `agent_inbox*` | Deprecated compatibility aliases. 새 client는 `boi_inbox*`를 사용한다. |
| `manual_handoff_complete` | 사용자 확인된 manual handoff 완료 기록. 완료 대상 task는 같은 사번의 Inbox에 보이는 항목이어야 한다. |
| `rbac_me` / `rbac_check` / `doc_access_check` / `rbac_audit` | 현재 사번의 팀·역할, 역할 binding, BoI Profile ACL/classification 접근 가능성, 권한 audit 확인 |
| `sop_registration_plan` / `sop_registration_preview` / `sop_registration_draft_create` / `sop_registration_validate` / `sop_registration_publish` | 자연어 SOP 추가 요청을 Event/SOP/Action 3단 흐름으로 계획, 확인, draft 생성, 검증, 게시 요청. 생성과 publish는 `user_confirmed=true`가 없으면 MCP 단계에서 차단 |
| `registration_draft_create` / `registration_drafts` / `registration_draft_validate` / `registration_draft_publish` | SOP/Event/Action 공통 registration draft 생성, 조회, 검증, 게시 요청. 생성과 publish는 `user_confirmed=true`가 없으면 MCP 단계에서 차단 |
| `registration_plan` / `registration_verification_preview` | 자연어 등록 요청을 기존 후보, 추천 필드, 권한, 과거 이력 기반 실행 전 확인으로 전환 |
| `sop_draft_create` / `action_draft_create` | 공통 registration draft 엔진으로 들어가는 SOP/Action 전용 shortcut. Action은 `connector_kind`와 connector별 `connector_config`를 함께 전달 |
| `event_publish_plan` / `event_publish_preview` / `event_pattern_preview` / `event_pattern_promote_to_draft` | 업무 Event 발생 요청과 기존 이력 패턴 승격을 계획, 확인, draft화 |
| `sop_run_history` | SOP 기준 실행 현황과 Timeline 요약 조회 |
| `event_type_draft_create` / `event_type_drafts` / `event_type_draft_validate` / `event_type_draft_apply` | 신규 Event Type draft 작성, 조회, 검증, 사용자 승인된 catalog 반영 |
| `source_preview` / `doc_body_preview` | source/body 수정 전 preview와 validation feedback |
| `source_apply` / `doc_body_apply` | 사용자 승인된 source/body 수정 apply와 자동 commit |
| `promotion_submit` | 사용자 승인된 Team/Public promotion candidate 원격 검증/즉시 게시. `user_confirmed=true`가 없으면 MCP 단계에서 차단 |
| `promotion_status` | promotion validation, publish, HOTL, commit 상태 조회 |

# Resources and Prompts

- Resource 예: `boi://docs/boi:public:sop:equipment-abnormal-response`
- Resource 예: `boi://actions/mcp.boi_search.sample`
- Employee-scoped Resource 예: `boi://employees/100001/docs/boi:private:100001:20260618070858:d1f2eb`
- Employee-scoped Resource 예: `boi://employees/100001/search/ontology/설비%20이상`
- Prompt 예: `create_sop_from_source`, `author_action_spec`, `build_langflow_boi_flow`

현재 프로토콜 기준 기대값은 `tools: 80`, `resources: 0`, `resource_templates: 11`, `prompts: 5`다. `resources: 0`은 오류가 아니다. 정적 resource를 미리 노출하지 않고 resource template으로 필요한 문서, 검색 결과, Agent 응답 스키마를 읽는다. 늘어난 tool 7개는 Optional Data Lake용이며, PostgreSQL/MinIO가 없는 기본 profile에서는 disabled contract를 반환해야 한다.

Unscoped resource template인 `boi://docs/{boi_id}`, `boi://folders/{folder}`, `boi://actions/{action_key}`는 public 문서와 public action 확인용이다. Workflow status와 ontology search처럼 사번별 ACL/RBAC 판단이 필요한 resource는 `boi://employees/{employee_id}/workflows/{workflow_key}/status/{trace_id}`, `boi://employees/{employee_id}/search/ontology/{query}`처럼 employee-scoped URI를 사용한다. Unscoped URI로 private/team 문서, trace, ontology search를 읽으려 하면 MCP server는 기본 사번으로 대신 조회하지 않고 `employee_scoped_resource_required` 오류와 올바른 employee-scoped URI를 반환한다. 일반 tool 호출에서는 기존처럼 `employee_id` argument를 명시한다.

검색 tool은 목적별로 나눠 쓴다. 단순 BoI 문서 목록이 필요하면 `boi_search`를 사용한다. SOP, Event, Action, Dictionary, runtime evidence를 관계까지 포함해 탐색하려면 `ontology_search`를 사용한다. 현재 페이지를 바탕으로 답변이나 산출물이 필요하면 `boi_agent_chat`을 사용한다. MCP client도 REST API와 같이 `intent` 힌트, 최근 `conversation`, `save_memory=false` 같은 제어 값을 넘길 수 있다. 세 경로는 모두 BoI API의 ACL/RBAC guardrail을 통과하므로 MCP client가 Web UI보다 더 넓은 문서를 볼 수 없다.

# Validation

```bash
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
```

상세 확인과 client 등록 전 점검은 다음 명령을 사용한다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --boi-api-url http://localhost:28000 \
  --agent-contract \
  --agent-artifact-smoke \
  --details \
  --client-checklist
```

`--agent-contract`는 BoI API의 `/api/agents/boi-wiki/response-schema`를 읽고 MCP `/health`의 `agent_response_schema`가 같은 canonical schema인지 비교한 뒤, REST `/api/agents/boi-wiki/chat` 응답이 같은 `boi-agent.response.v1` JSON Schema를 만족하는지 확인한다. `--agent-artifact-smoke`를 더하면 schema뿐 아니라 실제 업무 산출물도 확인한다. smoke 질문은 설비 SOP 페이지 기준 workflow 설명 요청이고, REST API와 MCP bridge 양쪽에서 `workflow_summary` artifact와 row가 반환되어야 한다. service token이 없으면 MCP bridge의 `boi_agent_chat` contract와 artifact 검증은 `skipped`로 남지만, REST API contract, REST artifact, MCP status schema contract는 확인된다. `MCP_REQUIRE_SERVICE_TOKEN=false`인 로컬 개발 endpoint에서는 token 없이 실행해도 protocol count를 확인하고 authenticated bridge는 `skipped`로 표시된다. 이 상태는 등록 전 tool 목록 확인에는 충분하지만, write/action/promotion bridge까지 검증한 것은 아니다.

`MCP_REQUIRE_SERVICE_TOKEN=true`인 protected endpoint에서는 token 없이 protocol check 자체가 `auth_required`로 실패하는 것이 정상이다. 이 경우 아래처럼 환경변수나 NAS `.env`에서 token을 읽게 한다.

protected MCP와 bridge를 함께 검증할 때는 token을 환경 변수로만 넘긴다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --boi-api-url http://localhost:28000 \
  --service-token-env SERVICE_TOKEN \
  --require-bridge \
  --agent-contract \
  --agent-artifact-smoke \
  --summary
```

정상 결과는 protocol count, MCP `/health` AgentResponse schema 일치, authenticated bridge 호출, REST AgentResponse contract, MCP bridge `boi_agent_chat` contract, REST/MCP bridge `workflow_summary` artifact smoke가 모두 성공이어야 한다. `boi_search`로 `employee_id=100001`, query `SOP`를 검색했을 때 BoI Wiki 문서가 반환되고, `ontology_search`와 `boi_agent_chat` smoke가 같은 권한 범위에서 응답하면 agent가 실제 Wiki와 Native BoI Agent에 접근 가능한 상태다.

NAS host처럼 `httpx`나 MCP client library가 없는 Python 환경에서는 `--agent-contract-only`로 BoI API schema, MCP `/health` schema, REST/MCP bridge AgentResponse contract만 확인할 수 있다. 이 모드는 stdlib HTTP client와 경량 schema 검증을 사용한다. NAS app directory에서 실행할 때는 token이 process argument에 남지 않도록 `.env`에서 직접 읽는다.

```bash
python3 scripts/check_boi_wiki_mcp.py \
  --base-url http://127.0.0.1:28200 \
  --boi-api-url http://127.0.0.1:28000 \
  --service-token-dotenv .env \
  --agent-contract-only \
  --agent-artifact-smoke \
  --require-bridge
```

`/health`와 `/status`의 `agent_response_contract.version`은 `boi-agent.response.v1`이어야 한다. Web Pet Agent, REST API, MCP `boi_agent_chat`, 외부 자동화는 모두 이 계약을 기준으로 `answer_markdown`, `display_markdown`, `links`, `citations`, `artifacts`, `execution_cards`, `status_updates`, `status_events`, `tool_trace`, `evidence_ledger`, `affordances`, `answer_quality`, `access_summary`, `guardrails_applied`, `suggested_questions`를 해석한다. REST client는 `agent_response_contract.schema_endpoint`, MCP client는 `agent_response_contract.mcp_resource_template`로 JSON Schema를 확인한다. MCP의 `boi://agent/response-schema/latest`는 BoI API의 `/api/agents/boi-wiki/response-schema`를 canonical source로 사용하므로, 두 endpoint의 required field와 artifact type이 달라지면 배포가 잘못된 상태로 본다. MCP client에서 `boi_agent_chat`이 다른 형태의 임의 문자열만 반환하면 구버전 MCP image나 잘못된 bridge endpoint를 보고 있는 상태로 판단한다.

`status_updates`는 UI 장식이 아니라 Agent 실행 설명 contract다. Web Pet은 `/chat/stream`의 `status` event를 먼저 보여주고 `final.status_updates`로 확정한다. MCP와 일반 REST client는 streaming을 쓰지 않더라도 `boi_agent_chat` 결과의 `status_updates`를 그대로 표시할 수 있다. `status_events`는 같은 배열을 담는 alias이므로 event 기반 UI framework를 쓰는 client가 이름을 맞춰 쓰기 쉽다. 새 client는 `status_updates`를 canonical로 저장하고, `status_events`는 호환 alias로만 다룬다. Mermaid와 표도 같은 원칙이다. Web Pet은 artifact viewer로 크게 보여주지만, MCP/API 소비자는 `artifacts[].type`과 `artifacts[].source` 또는 `artifacts[].data`를 기준으로 자기 환경에서 렌더링한다.

# Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `http://localhost:8200/`가 열리지 않음 | MCP container 또는 port publish 문제 | `docker compose ps boi-wiki-mcp`, `curl http://localhost:8200/health` 확인 |
| `/mcp`가 `406` 반환 | 일반 브라우저/curl이 MCP Accept header를 보내지 않음 | 정상일 수 있음. MCP client나 검증 스크립트로 확인 |
| `/mcp`가 `401` 반환 | `MCP_REQUIRE_SERVICE_TOKEN=true`인데 token header가 없음 | MCP client에 `x-service-token` 또는 `Authorization: Bearer` 설정 |
| root가 `404` | 구버전 image가 떠 있거나 rebuild 전 상태 | `docker compose up -d --build boi-wiki-mcp` |
| `ClosedResourceError` 로그 | MCP stream client가 연결을 닫을 때 생기는 benign disconnect 로그일 수 있음 | protocol check가 성공하면 장애로 보지 않음. 반복 실패와 함께 발생하면 client 설정 확인 |
| port 충돌 | 다른 process가 8200 사용 | `.env`의 `BOI_WIKI_MCP_PORT`를 바꾸고 client URL도 같이 변경 |
| bridge `401` | service token 불일치 | `.env`와 호출 header `x-service-token` 확인 |

# Runtime Evidence

상태 페이지는 서버 health뿐 아니라 실제 MCP capabilities 목록과 MCP auth 상태를 보여준다. `tools=80`, `resource_templates=11`, `prompts=5`, `resources=0`이 현재 기준이며, 요약 표기에서는 `tools: 80`, `resource_templates: 11`, `resources: 0`처럼 보인다. `resources=0`은 정적 resource 대신 resource template을 쓰는 설계라서 정상이다. 상태 페이지의 tool 목록은 `BoI Wiki`, `BoI Inbox`, `SOP`, `Event Broker`, `Action`, `Advanced`, `Optional Data Lake`, `Deprecated / Compatibility` 그룹으로 먼저 보이고, 전체 tool 목록은 호환 확인용으로 함께 남는다. WorkflowDefinition tool은 Advanced 내부 도구로 분류하고, Data Lake tool은 선택형 사내 Data Lake demo profile이 켜진 경우에만 실제 query/artifact를 반환한다. legacy `agent_inbox*`와 `capabilities_*` tool은 Deprecated / Compatibility 그룹에만 둔다. 외부에 공개된 endpoint에서는 `mcp_auth.required=true`가 권장된다.

![BoI Wiki MCP Status capabilities](/public/boi-wiki-manual/_media/browser/mcp-status/20260619-151048-boi-wiki-mcp-status-capabilities-current-1440x1000-89caadae3b92.png)

# Citations

- [MCP BoI Search Action Spec](/public/actions/mcp/boi-search-sample.md)
- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
- [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
