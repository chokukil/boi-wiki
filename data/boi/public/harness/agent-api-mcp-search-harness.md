---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: BoI Agent API, MCP, Ontology Search Harness
description: BoI Agent, ontology search, dictionary, memory, inbox, manual handoff API/MCP 사용 기준
tags:
  - BoIWiki
  - Agent
  - MCP
  - OntologySearch
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:harness:agent-api-mcp-search-harness
visibility: public
classification: internal
owner: aix-tf
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
review:
  reviewer: harness-curator
  review_status: reviewed
source_refs:
  - type: repo
    ref: skills/boi-wiki-agent/SKILL.md
---

# Summary

BoI Agent를 외부에서 쓸 때 공식 경로는 BoI API와 `boi-wiki-mcp`이다. Production backend는 `boi-api` 내부 Native BoI Agent이며, Langflow는 visual workflow, demo, debug backend로 유지한다. 일반 사용자나 외부 agent가 Langflow URL을 직접 호출하는 구조로 문서화하지 않는다.

이 하네스는 Codex, Claude, Cursor, Langflow tool, custom agent가 같은 기준으로 BoI Wiki를 탐색하고 수정하도록 정리한다.

## Search Routing

| 사용 상황 | 우선 경로 | 의미 |
|---|---|---|
| BoI 문서 목록이 필요함 | `GET /api/boi` 또는 MCP `boi_search` | 하위 호환 document-only search |
| SOP, Event, Action, Dictionary, runtime evidence를 함께 탐색 | `GET /api/search/ontology` 또는 MCP `ontology_search` | ontology-assisted grouped search |
| 현재 페이지를 바탕으로 질문 | `POST /api/agents/boi-wiki/chat` 또는 MCP `boi_agent_chat` | page-aware BoI Agent |
| Web Pet처럼 진행 상태를 보여주는 질문 | `POST /api/agents/boi-wiki/chat/stream` | Server-Sent Events로 `status`, `answer_delta`, `final` 전송 |
| 현장 용어/약어 해석 | `GET /api/dictionary/resolve` 또는 MCP `dictionary_resolve` | private -> team -> public dictionary priority |
| 담당자가 처리할 task 확인 | `GET /api/agents/boi-wiki/inbox` 또는 MCP `agent_inbox` | manual/approval/follow-up inbox |

`boi_search`는 계속 문서 검색 의미를 유지한다. 검색 UX가 부족하다고 해서 `boi_search` 응답에 Action/Event/Dictionary를 섞지 않는다. 복합 탐색은 `ontology_search`를 사용한다. 사람이 보는 Web Pet Agent는 `/chat/stream`을 기본으로 쓰고, MCP와 자동화는 JSON 처리가 쉬운 `/chat` 또는 `boi_agent_chat`을 기본으로 쓴다.

## BoI Agent Routing

`boi_agent_chat`은 LLM Router 우선, rules fallback 방식으로 동작한다. Router는 답변을 만들지 않고 `route`와 `intent`만 분류한다. `route`는 backend 선택이고, `intent`는 업무 의도다.

- `fast`: 현재 화면을 서버에서 다시 해석한 Page Context와 `ontology_search`로 즉시 답한다.
- `deep`: Native BoI Agent의 LangGraph tool loop를 사용해 Mermaid, gap check, workflow 설명, trace reasoning 같은 산출물을 만든다.
- `inbox`: 현재 사번의 open manual/approval/follow-up task를 조회한다.
- `manual_handoff`, `approval_required`: 사용자 명시 확인이 필요한 상태 변경 flow로 안내한다.

Intent 기준은 다음처럼 고정한다.

- `search`, `page_qa`, `summarize`: fast path.
- `diagram`, `workflow_explain`, `gap_check`, `trace_reasoning`: Native BoI Agent deep path.
- `inbox`: Inbox API.
- `manual_complete`, `approval`: safety/confirmation flow.

예를 들어 “이 SOP를 Mermaid 프로세스 플로우로 보여줘”, “이 Event가 발생하면 어떤 Action이 이어져?”, “부족한 Action Spec 찾아줘”는 검색어가 포함되어 있어도 deep intent다. Deep Agent 입력에는 `question`, `intent`, `current_url`, `page_context_pack`, `ontology_search_seed`, `employee_id`가 함께 들어가며, 최종 응답은 `answer_markdown`, `links`, `citations`, `suggested_questions`, `artifacts`, `context_summary`, `tool_trace`, `coverage_report` JSON contract를 따라야 한다. Mermaid는 `artifacts`와 Markdown code block 둘 다 제공한다.

Pet UI가 보내는 `current_url`, `page_title`, `selected_text`는 힌트다. 서버는 클라이언트 데이터를 신뢰하지 않고 `current_url` 기준으로 `/docs`, `/workflows/.../status`, `/events`, `/actions/raw`, `/event-types` 데이터를 권한 체크 후 다시 로드한다. Router LLM이 실패하거나 confidence가 낮으면 rules fallback으로 진행하며, 승인/실행/편집/publish 요청은 Router 결과와 무관하게 safety guard가 최종 차단한다.

자세한 구현 기준은 [Native BoI Agent Architecture](/public/boi-wiki-manual/agent/native-boi-agent-architecture.md)와 [Native BoI Agent Tool Loop](/public/boi-wiki-manual/agent/native-boi-agent-tool-loop.md)를 따른다.

## Agent Write Boundary

다음 작업은 반드시 사용자 명시 확인이 필요하다.

- `manual_handoff_complete`
- `action_invoke`
- `source_apply`
- `doc_body_apply`
- `promotion_submit`

Agent는 확인 없이 source file, body, promotion, action execution을 변경하지 않는다. Manual handoff completion은 기존 action log를 수정하지 않고 append-only completion row로 남긴다.

## ACL and RBAC Guardrail

모든 Agent API와 MCP tool은 BoI Profile ACL을 통과해야 한다. 단순히 `/api/boi`에서 보이는 문서를 filter하는 수준이 아니라, 답변 context, citation, artifact, memory, external action payload까지 같은 decision을 적용한다.

| 대상 | 적용 기준 |
|---|---|
| `boi_search` | 접근 가능한 document-only result만 반환 |
| `ontology_search` | SOP/Event/Action/Dictionary/runtime evidence 중 접근 가능한 항목만 그룹화 |
| `boi_agent_chat` | page context와 tool result를 ACL pruning 후 답변 |
| `agent_inbox` | 현재 사번 또는 팀/역할에 매핑된 task만 표시 |
| `manual_handoff_complete` | `boi.workflow_runner` role과 task ownership 확인 |
| mutation/apply/promotion | user confirmation + RBAC + ACL + classification + audit. MCP `action_invoke`는 실제 실행(`dry_run=false`)에서, `promotion_submit`은 모든 제출에서 API 호출 전 `user_confirmed=true`를 요구한다. |

private 문서는 `data/boi/private/{7자리사번}` 경로, `owner`, `acl:private:{사번}`이 일치해야 한다. Team 문서는 `team_id`, `acl:team:{team_id}`, 내부 팀 멤버십이 일치해야 한다. 자세한 기준은 [BoI Profile ACL Policy](/public/boi-wiki-manual/security/boi-profile-acl-policy.md)와 [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)를 따른다.

## Execution and Event Authoring

Agent는 Event 발행, Workflow 시작, Action 호출, Manual Handoff 완료, 신규 Event Type draft 생성을 제안할 수 있다. 하지만 사용자에게는 `simulation`, `preview-only run`, `invoke` 같은 개발자 용어를 노출하지 않고 `먼저 확인`, `요청 실행`, `승인 필요`, `조치 내용 입력 필요`로 표현한다.

신규 Event Type은 catalog에 즉시 반영하지 않고 draft와 catalog patch proposal을 만든다. 적용은 validation, review, 승인, lint 후 별도 apply 단계에서 진행한다.

- [Agent Execution and Event Authoring](/public/boi-wiki-manual/agent/agent-execution-and-event-authoring.md)
- [Team RBAC Management](/public/boi-wiki-manual/security/team-rbac-management.md)

## Dictionary

Dictionary는 사람이 쉽게 입력할 수 있어야 한다. 기본 폼은 다음 5개만 요구한다.

- 용어
- 별칭/약어
- 뜻
- 예시
- 연결 문서

고급 relation은 선택이다: `related_terms`, `broader`, `narrower`, `same_as`, `maps_to_event_type`, `maps_to_action_key`, `maps_to_sop`.

동일 용어가 여러 scope에 있으면 `private -> team -> public` 순서로 해석한다. Dictionary는 검색과 언어 이해를 돕지만 실행 권한이나 approval policy를 바꾸지 않는다.

### Public Semiconductor Seed Vocabulary

`public/dictionary`는 BoI Agent의 공통 도메인 seed vocabulary이다. 최소한 다음 범주의 용어를 public fallback으로 유지한다.

- 반도체 object: `Fab`, `Wafer`, `Lot`, `Die`, `Reticle / Photomask`
- 공정 module: `Lithography`, `Deposition`, `CVD`, `PVD`, `ALD`, `CMP`, `Etch`, `Ion Implant`
- 품질/검사/SPC: `Metrology`, `Inspection`, `Defect`, `Yield`, `Control Chart`, `Cpk`, `Out-of-Control`, `Excursion`
- 설비/운영: `Equipment`, `Chamber`, `Recipe`, `Alarm`, `FDC`, `Preventive Maintenance`, `Root Cause Analysis`, `Corrective Action`
- memory/package: `DRAM`, `NAND Flash`, `HBM`, `TSV`, `Advanced Packaging`, `Hybrid Bonding`, `Interposer`
- AI Native Workflow: `Event Broker`, `Action Gateway`, `Manual Handoff`, `Approval`, `Time Series Forecast`, `TimesFM`

Agent는 사용자의 용어가 낯설거나 약어일 때 바로 전체 wiki를 훑지 말고 `dictionary_resolve`를 먼저 호출한다. `maps_to_event_type`, `maps_to_action_key`, `maps_to_sop`가 있는 경우 해당 Event/Action/SOP를 context pack에 포함한다. 관련 mapping이 없으면 dictionary term과 backlink를 근거로 `ontology_search`를 호출한다.

## Memory

Private memory는 `data/boi/private/{employee_id}/agent-memory/*.md`에 `boi/agent-memory`로 저장한다.

저장 가능한 memory kind:

- `preference`
- `answer_style`
- `domain_context`
- `workflow_preference`
- `recurring_task`
- `avoidance`
- `reflection`

token, password, secret, 계정정보, high-risk action 자동 승인 선호, 승인 우회 선호는 자동 저장하지 않는다. 중복 memory는 새 문서 무한 생성 대신 archive/supersede/compact 후보로 관리한다.

## Pet Agent UI

Web shell은 우측 하단 BoI Agent를 제공한다.

- Agent: 현재 페이지 기반 질의응답
- 추천 질문: 페이지 종류별 next question
- Inbox: open manual/approval/follow-up task

Pet UI에는 `Agent`와 `Inbox` 두 탭만 둔다. Memory는 `data/boi/private/{employee_id}/agent-memory/*.md` 문서로 보고 수정하는 것이 공식 UX이고, Dictionary는 Pet 메뉴가 아니라 ontology search, MCP, agent harness의 용어 해석 기능이다.

JS가 실패해도 기존 BoI Wiki 본문 탐색은 정상 동작해야 한다.

긴 질문은 사용자가 기다리는 동안 불확실성을 느끼지 않도록 progressive response를 사용한다. Pet UI는 `/api/agents/boi-wiki/chat/stream`의 `status` event를 한 줄 진행 메시지로 보여주고, `answer_delta`를 같은 말풍선에 누적한다. `final` event가 오면 server-rendered `answer_html`, links, artifacts로 메시지를 확정한다. 중지 버튼은 현재 streaming request만 취소하고 BoI Wiki 페이지 상태나 이전 대화 기록을 지우지 않는다.

## MCP Tool 기준

필수 Agent/Search MCP tools:

- `boi_agent_chat`
- `boi_agent_suggestions`
- `ontology_search`
- `dictionary_resolve`
- `dictionary_terms`
- `agent_memory_search`
- `agent_inbox`
- `manual_handoff_complete`

기존 tools는 유지한다: `boi_search`, `boi_get`, `workflow_status`, `actions_search`, `action_get`, `action_invoke`, validated edit/promotion tools.

# Citations

- [BoI Wiki Agent Skill](/public/harness/agent-api-mcp-search-harness.md)
