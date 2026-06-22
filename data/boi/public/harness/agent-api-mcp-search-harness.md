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

BoI Agent를 외부에서 쓸 때 공식 경로는 BoI API와 `boi-wiki-mcp`이다. Langflow는 reasoning/orchestration backend이며, 일반 사용자나 외부 agent가 직접 호출하는 public Agent API로 문서화하지 않는다.

이 하네스는 Codex, Claude, Cursor, Langflow tool, custom agent가 같은 기준으로 BoI Wiki를 탐색하고 수정하도록 정리한다.

## Search Routing

| 사용 상황 | 우선 경로 | 의미 |
|---|---|---|
| BoI 문서 목록이 필요함 | `GET /api/boi` 또는 MCP `boi_search` | 하위 호환 document-only search |
| SOP, Event, Action, Dictionary, runtime evidence를 함께 탐색 | `GET /api/search/ontology` 또는 MCP `ontology_search` | ontology-assisted grouped search |
| 현재 페이지를 바탕으로 질문 | `POST /api/agents/boi-wiki/chat` 또는 MCP `boi_agent_chat` | page-aware BoI Agent |
| 현장 용어/약어 해석 | `GET /api/dictionary/resolve` 또는 MCP `dictionary_resolve` | private -> team -> public dictionary priority |
| 담당자가 처리할 task 확인 | `GET /api/agents/boi-wiki/inbox` 또는 MCP `agent_inbox` | manual/approval/follow-up inbox |

`boi_search`는 계속 문서 검색 의미를 유지한다. 검색 UX가 부족하다고 해서 `boi_search` 응답에 Action/Event/Dictionary를 섞지 않는다. 복합 탐색은 `ontology_search`를 사용한다.

## Agent Write Boundary

다음 작업은 반드시 사용자 명시 확인이 필요하다.

- `manual_handoff_complete`
- `action_invoke`
- `source_apply`
- `doc_body_apply`
- `promotion_submit`

Agent는 확인 없이 source file, body, promotion, action execution을 변경하지 않는다. Manual handoff completion은 기존 action log를 수정하지 않고 append-only completion row로 남긴다.

## Dictionary

Dictionary는 사람이 쉽게 입력할 수 있어야 한다. 기본 폼은 다음 5개만 요구한다.

- 용어
- 별칭/약어
- 뜻
- 예시
- 연결 문서

고급 relation은 선택이다: `related_terms`, `broader`, `narrower`, `same_as`, `maps_to_event_type`, `maps_to_action_key`, `maps_to_sop`.

동일 용어가 여러 scope에 있으면 `private -> team -> public` 순서로 해석한다. Dictionary는 검색과 언어 이해를 돕지만 실행 권한이나 approval policy를 바꾸지 않는다.

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

- Chat: 현재 페이지 기반 질의응답
- 추천 질문: 페이지 종류별 next question
- 내 Action: open manual/approval/follow-up task
- Memory: Private memory 빠른 저장
- Dictionary: Private dictionary term 빠른 저장

JS가 실패해도 기존 BoI Wiki 본문 탐색은 정상 동작해야 한다.

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
