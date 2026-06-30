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
| 내부 WorkflowDefinition 중복 확인 | MCP `workflow_definitions_search`, `workflow_definition_deduplicate` | 새 업무/API/MCP/Skill 등록 전 재사용 후보 확인. 사용자 화면에서는 SOP 추가/BoI Wiki 탐색 후보로 표시 |
| 자연어 SOP 통합 등록 | MCP `sop_registration_plan`, `sop_registration_preview` | 사용자가 schema/topic/key를 몰라도 Event/SOP/Action 후보와 선택 사항을 한 흐름으로 확인 |
| 개별 등록 계획 | MCP `registration_plan`, `registration_verification_preview` | 기존 호환 경로. 내부 컴포넌트 단위 draft가 필요할 때 사용 |
| Event 발생/패턴 승격 | MCP `event_publish_plan`, `event_publish_preview`, `event_pattern_preview` | 업무 Event 발생 전 확인과 기존 Event Stream 조건의 Event 정의 초안 승격 |
| SOP 수행 이력 | MCP `sop_run_history` | raw Event Stream 대신 SOP 기준 Timeline과 남은 승인/수동 조치 확인 |
| 현재 페이지를 바탕으로 질문 | `POST /api/agents/boi-wiki/chat` 또는 MCP `boi_agent_chat` | page-aware BoI Agent |
| Web Pet처럼 진행 상태를 보여주는 질문 | `POST /api/agents/boi-wiki/chat/stream` | Server-Sent Events로 `status`, `answer_delta`, `final` 전송 |
| 현장 용어/약어 해석 | `GET /api/dictionary/resolve` 또는 MCP `dictionary_resolve` | private -> team -> public dictionary priority |
| 담당자가 처리할 보고서 확인 | `GET /api/inbox` 또는 MCP `boi_inbox` | 검증된 BoI Inbox 보고서와 조치 후보 |

`boi_search`는 계속 문서 검색 의미를 유지한다. 검색 UX가 부족하다고 해서 `boi_search` 응답에 Action/Event/Dictionary를 섞지 않는다. 복합 탐색은 `ontology_search`를 사용한다. 새 업무를 등록하거나 API/MCP/Skill을 연결할 때는 먼저 `workflow_definitions_search`와 `workflow_definition_deduplicate`로 내부 WorkflowDefinition 재사용 가능성을 확인한다. 다만 외부 UI와 Agent 답변 링크는 `/workflows/definitions`를 직접 노출하지 않고 `관련 SOP 보기`, `BoI Wiki에서 보기`, `Event 보기`, `Action 보기`처럼 5대 메뉴 안의 화면으로 연결한다. 사용자의 자연어 요청은 기본적으로 `sop_registration_plan`과 `sop_registration_preview`로 Event/SOP/Action을 한 흐름에서 정리하고, 내부 컴포넌트 단독 draft가 필요할 때만 `registration_plan`과 `registration_verification_preview`를 사용한다. Event Broker에 새 Event를 발생시키려는 요청은 `event_publish_plan`과 `event_publish_preview`로 기존 Event 후보, 연결 SOP, 과거 이력을 먼저 보여준다. 사람이 보는 Web Pet Agent는 `/chat/stream`을 기본으로 쓰고, MCP와 자동화는 JSON 처리가 쉬운 `/chat` 또는 `boi_agent_chat`을 기본으로 쓴다.

`/chat`, `/chat/stream`, MCP `boi_agent_chat`은 모두 `boi-agent.response.v1`을 반환한다. 차이는 전송 방식뿐이다. Web Pet은 SSE의 `status`와 `answer_delta`를 실시간으로 렌더링하고, REST/MCP client는 최종 JSON 안의 `status_updates`, `answer_markdown`, `display_markdown`, `artifacts`, `execution_cards`, `tool_trace`를 사용한다. 따라서 진행 상태, Mermaid, 표, 승인 카드 같은 기능은 Web 전용 HTML이 아니라 typed response contract로 구현해야 한다.

## BoI Agent Routing

`boi_agent_chat`은 Native Agent Query Kernel로 진입한다. LLM Router는 답변 생성의 필수 관문이 아니라 goal hypothesis 후보 생성기다. Router LLM이 timeout, invalid JSON, low confidence를 반환해도 사용 가능한 page context, ontology search, WorkContextPack이 있으면 Agent는 가능한 답변을 유지하고 기술 진단은 diagnostics에만 남긴다.

- `fast`: 현재 화면을 서버에서 다시 해석한 Page Context와 `ontology_search`로 즉시 답한다.
- `deep`: Native BoI Agent tool loop를 사용해 Mermaid, gap check, 업무 흐름 설명, trace reasoning 같은 산출물을 만든다.
- `inbox`: 현재 사번의 open manual/approval/follow-up task를 조회한다.
- `manual_handoff`, `approval_required`: 사용자 명시 확인이 필요한 상태 변경 flow로 안내한다.

Intent 기준은 다음처럼 해석한다.

- `search`, `page_qa`, `summarize`: fast path.
- `diagram`, `workflow_explain`, `gap_check`, `trace_reasoning`: Native BoI Agent tool loop.
- `inbox`: Inbox API.
- `manual_complete`, `approval`: safety/confirmation flow.

예를 들어 “이 SOP를 Mermaid 프로세스 플로우로 보여줘”, “이 Event가 발생하면 어떤 업무 BoI를 채워야 해?”, “부족한 Action 명세를 찾아줘”는 검색어가 포함되어 있어도 업무 흐름 산출물 intent다. Agent 입력에는 `question`, `intent`, `current_url`, `page_context_pack`, `work_context_pack`, `ontology_search_seed`, `employee_id`가 함께 들어가며, 최종 응답은 `answer_markdown`, `display_markdown`, `links`, `citations`, `suggested_questions`, `artifacts`, `execution_cards`, `status_updates`, `context_summary`, `tool_trace`, `coverage_report`, `access_summary`, `guardrails_applied` JSON contract를 따라야 한다. Mermaid는 API/MCP 호환성을 위해 `artifacts`에 구조화해서 제공하고, 원본 투명성이 필요할 때만 `answer_markdown`에도 code block으로 남긴다.

Pet UI가 보내는 `current_url`, `page_title`, `selected_text`는 힌트다. 서버는 클라이언트 데이터를 신뢰하지 않고 `current_url` 기준으로 `/docs`, `/workflows/.../status`, `/events`, `/actions/raw`, `/event-types` 데이터를 권한 체크 후 다시 로드한다. Router LLM이 실패하거나 confidence가 낮으면 Agent는 deterministic goal registry와 page context로 가능한 답변을 만들고, 실패 원인은 `component_errors`에 남긴다. 승인/실행/편집/publish 요청은 Router 결과와 무관하게 safety guard가 최종 차단한다.

자세한 구현 기준은 [Native BoI Agent Architecture](/public/boi-wiki-manual/agent/native-boi-agent-architecture.md)와 [Native BoI Agent Tool Loop](/public/boi-wiki-manual/agent/native-boi-agent-tool-loop.md)를 따른다.

## Agent Write Boundary

다음 작업은 반드시 사용자 명시 확인이 필요하다.

- `manual_handoff_complete`
- `event_type_draft_create`
- `event_type_draft_apply`
- `action_invoke`
- `source_apply`
- `doc_body_apply`
- `promotion_submit`

Agent는 확인 없이 source file, body, promotion, action execution, Event Type draft 생성/반영을 변경하지 않는다. Manual handoff completion은 기존 action log를 수정하지 않고 append-only completion row로 남긴다. 신규 Event Type은 `event_type_draft_create`로 draft와 catalog patch proposal을 만든 뒤 `event_type_draft_validate`를 거치고, 별도 확인과 `boi.promoter` 권한이 있을 때만 `event_type_draft_apply`로 catalog에 반영한다.

## ACL and RBAC Guardrail

모든 Agent API와 MCP tool은 BoI Profile ACL을 통과해야 한다. 단순히 `/api/boi`에서 보이는 문서를 filter하는 수준이 아니라, 답변 context, citation, artifact, memory, external action payload까지 같은 decision을 적용한다.

| 대상 | 적용 기준 |
|---|---|
| `boi_search` | 접근 가능한 document-only result만 반환 |
| `ontology_search` | SOP/Event/Action/Dictionary/runtime evidence 중 접근 가능한 항목만 그룹화 |
| `boi_agent_chat` | page context와 tool result를 ACL pruning 후 답변 |
| `boi_inbox` | 현재 사번 또는 팀/역할에 매핑된 보고서만 표시 |
| `agent_inbox*` | Deprecated compatibility alias. 새 client는 `boi_inbox*` 사용 |
| `manual_handoff_complete` | `boi.workflow_runner` role과 task ownership 확인 |
| mutation/apply/promotion/Event Type draft | user confirmation + RBAC + ACL + classification + audit. `workflow_start`, `promotion_submit`, `event_type_draft_create`, `event_type_draft_apply`는 API/MCP 모든 실행/제출에서, `action_invoke`는 실제 실행(`dry_run=false`)에서 API 호출 전 `user_confirmed=true`를 요구한다. |

private 문서는 `data/boi/private/{7자리사번}` 경로, `owner`, `acl:private:{사번}`이 일치해야 한다. Team 문서는 `team_id`, `acl:team:{team_id}`, 내부 팀 멤버십이 일치해야 한다. 자세한 기준은 [BoI Profile ACL Policy](/public/boi-wiki-manual/security/boi-profile-acl-policy.md)와 [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)를 따른다.

## Execution and Event Authoring

Agent는 Event 발행, Workflow 시작, Action 호출, Manual Handoff 완료, 신규 Event Type draft 생성을 제안할 수 있다. 하지만 사용자에게는 `simulation`, `preview-only run`, `invoke` 같은 개발자 용어를 노출하지 않고 `먼저 확인`, `요청 실행`, `승인 필요`, `조치 내용 입력 필요`로 표현한다.

신규 Event Type은 catalog에 즉시 반영하지 않고 private draft BoI와 catalog patch proposal을 함께 만든다. 적용은 validation, review, 승인, lint 후 별도 apply 단계에서 진행한다. Apply가 완료되면 private draft BoI도 `event_type_draft_status: applied`, catalog entry, source edit 결과를 담은 적용 기록으로 갱신된다.

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

Agent는 사용자의 용어가 낯설거나 약어일 때 바로 전체 wiki를 훑지 말고 `dictionary_resolve`를 먼저 호출한다. 기본 응답은 compact/bounded contract이며 match 8건, 최대 25건, query expansion 24개를 넘기지 않는다. `overflow.has_more=true`이면 전체 dictionary를 읽지 말고 검색어, domain, scope를 좁힌다. `maps_to_event_type`, `maps_to_action_key`, `maps_to_sop`가 있는 경우 해당 Event/Action/SOP를 context pack에 포함한다. 관련 mapping이 없으면 dictionary term과 backlink를 근거로 `ontology_search`를 호출한다.

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
- BoI Inbox: open manual/approval/follow-up report BoI

Pet UI는 `Agent` 단일 화면만 둔다. 업무 검토와 승인/반려/보류/추가 근거 요청은 상단 메뉴 `BoI Inbox`의 전용 화면과 검증된 보고서 BoI에서 처리한다. Memory는 `data/boi/private/{employee_id}/agent-memory/*.md` 문서로 보고 수정하는 것이 공식 UX이고, Dictionary는 Pet 메뉴가 아니라 ontology search, MCP, agent harness의 용어 해석 기능이다.

JS가 실패해도 기존 BoI Wiki 본문 탐색은 정상 동작해야 한다.

긴 질문은 사용자가 기다리는 동안 불확실성을 느끼지 않도록 progressive response를 사용한다. Pet UI는 `/api/agents/boi-wiki/chat/stream`의 `status` event를 한 줄 진행 메시지로 보여주고, `answer_delta`를 같은 말풍선에 누적한다. `final` event가 오면 server-rendered `answer_html`, links, artifacts로 메시지를 확정한다. LLM stream planner가 요청별 status 문구를 만들지 못하면 SSE는 `diagnostic` event로 실패 원인을 남기고, Native Agent가 답할 수 있으면 `answer_ready`와 `final`을 계속 보낸다. 중지 버튼은 현재 streaming request만 취소하고 BoI Wiki 페이지 상태나 이전 대화 기록을 지우지 않는다.

REST API와 MCP는 SSE를 소비하지 않으므로 같은 LLM status plan을 최종 응답의 `status_updates` 배열에 포함한다. MCP client는 `answer_html`에 의존하지 않고 `display_markdown`과 typed `artifacts`를 각 client UI에 맞게 렌더링한다. Web Pet의 artifact viewer는 presentation layer이며, MCP/API 호환성의 source of truth는 `artifacts[].type`, `source` 또는 `data`, `execution_cards[]`의 confirmation contract다.

## MCP Tool 기준

필수 Agent/Search MCP tools:

- `boi_agent_chat`
- `boi_agent_suggestions`
- `ontology_search`
- `dictionary_resolve`
- `dictionary_terms`
- `agent_memory_search`
- `work_context_get`
- `similar_cases_search`
- `agent_signals`
- `work_patterns_search`
- `work_pattern_derive`
- `skill_candidate_create`
- `boi_inbox`
- `boi_inbox_report_get`
- `boi_inbox_decision_preview`
- `boi_inbox_decision_submit`
- `manual_handoff_complete`
- `event_type_draft_create`
- `event_type_drafts`
- `event_type_draft_validate`
- `event_type_draft_apply`

기존 tools는 유지한다: `boi_search`, `boi_get`, `workflow_status`, `actions_search`, `action_get`, `action_invoke`, validated edit/promotion tools.

## Work Context and Work Patterns

Agent는 단순 검색 결과를 바로 답변으로 내보내지 않는다. `work_context_get` 또는 `/api/context/work`로 현재 task, trace, SOP stage, generated BoI, 필요한 evidence, 유사 과거 사례를 모은 뒤 답변에 반영한다. 업무함 UI는 Agent가 아니라 `/inbox`와 `boi_inbox*` contract가 담당한다.

BoI Inbox에서는 `include_context=compact`를 기본으로 사용한다. 같은 유형이 여러 건이면 `group_context_summary`, `group_narrative`, `preview_items`로 시간 범위, 공통점, 주요 차이점, 상위 3건의 다음 확인 사항을 먼저 보여준다. 검증된 보고서는 `report_boi_ref`와 `report_boi_url`로 materialize되어야 하며, 기술 식별자는 보고서 기본 화면이 아니라 기술 세부정보에 접는다. Narrative가 아직 준비되지 않았으면 deterministic 상태 목록을 fallback 답변처럼 보여주지 않고, 보고서 준비/품질 상태만 보여준다.

승인/반려 판단은 `boi_inbox_report_get`의 보고서 품질을 통과해야 한다. 하네스는 보고서의 `conclusion`, `comparison`, `evidence`, `similar_cases`, `actions`를 확인하고, visible report JSON에 `source_id`, raw trace/action id, schema, WorkflowDefinition이 노출되면 실패시킨다. 고위험 group bulk approve는 `boi_inbox_decision_preview`에서 실패해야 하며, 실제 기록은 `boi_inbox_decision_submit`으로 개별 task에 사유와 `user_confirmed=true`가 있을 때만 통과한다.

개인화는 Pet 메뉴가 아니라 activity와 private BoI 문서로 운영한다. `work_pattern_derive`는 반복 follow-up, artifact viewer 사용, Inbox 처리 방식 같은 활동을 `boi/work-pattern` 후보로 제안한다. 후보는 자동 publish하지 않고 private draft로 남기며, skill이나 Workflow 정의로 전환하려면 사용자 확인과 promotion flow를 거친다.

Pet 말풍선은 고정 문구가 아니라 `agent_signals` 결과를 사용한다. Signal은 새 Inbox task, 현재 페이지 관련 task, 빠진 evidence, 답변 follow-up, page starter 순서로 ranking하며, 사용자가 본 signal은 activity에 남겨 반복 노출을 줄인다.

자세한 기준은 [Work Context Pack](/public/boi-wiki-manual/agent/work-context-pack.md), [Inbox Work Context and Historical Patterns](/public/boi-wiki-manual/agent/inbox-work-context-and-history.md), [Personal Work Pattern Assets](/public/boi-wiki-manual/agent/personal-work-pattern-assets.md), [Proactive Signal Bubble](/public/boi-wiki-manual/agent/proactive-signal-bubble.md)를 따른다.

# Citations

- [BoI Wiki Agent Skill](/public/harness/agent-api-mcp-search-harness.md)
