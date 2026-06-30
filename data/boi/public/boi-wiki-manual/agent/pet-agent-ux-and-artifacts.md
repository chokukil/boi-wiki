---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Pet Agent UX and Artifacts
description: BoI Agent 우측 하단 Pet UI, artifact 렌더링, Inbox, 대화 상태 유지 기준
tags: [Manual, Agent, UX, PetAgent, Artifacts]
timestamp: 2026-06-24T09:15:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:pet-agent-ux-and-artifacts
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
    ref: boi_api/app/static/pet_agent.js
  - type: repo
    ref: boi_api/app/static/style.css
review:
  reviewer: ux-curator
  review_status: reviewed
---

# Summary

Pet Agent는 모든 BoI Wiki 화면에서 현재 페이지를 이해하고 질문, 검색, 분석, 초안 작성, 산출물 확인을 돕는 보조 UI다. 업무 검토와 승인 판단은 Pet 안의 탭이 아니라 상단 메뉴 `BoI Inbox`에서 처리한다. Memory와 Dictionary도 Pet 메뉴가 아니라 BoI 문서와 harness/MCP 기능으로 관리한다.

Pet 왼쪽 말풍선은 고정 문구가 아니라 `AgentSignal`이다. Signal은 새 BoI Inbox 보고서, 현재 페이지 관련 high-priority task, 빠진 근거, answer-scoped follow-up, page starter 순서로 ranking한다. 업무함 항목은 Pet에 직접 렌더링하지 않고 `/inbox` 보고서로 안내한다. 사용자가 이미 본 signal은 sessionStorage와 activity log에 남겨 반복 노출을 줄인다.

# UX Principles

- 현재 페이지 context를 기본으로 질문을 추천한다.
- 링크 클릭으로 페이지가 바뀌면 Pet panel은 닫고, messages와 draft는 sessionStorage에 유지한다.
- Enter는 전송, Shift+Enter는 줄바꿈이다.
- 생성 중지는 사용자가 긴 답변을 멈추기 위한 기본 조작이다.
- Agent가 오래 걸리는 질문을 처리할 때는 한 줄 진행 상태를 먼저 보여주고, 답변 본문은 도착하는 조각대로 누적 렌더링한다.
- Mermaid, 표, 이미지, task card artifact는 작은 채팅 영역에 억지로 밀어 넣지 않고 큰 viewer로 열 수 있어야 한다.
- `새 대화`는 desktop과 mobile 모두에서 접근 가능해야 한다.
- BoI Inbox 보고서가 있으면 signal은 일반 구성원 문구로 보여주고, 클릭 시 `/inbox` 또는 검증된 보고서 BoI로 이동한다.

# Progressive Response UX

Pet Agent의 기본 호출 경로는 `POST /api/agents/boi-wiki/chat/stream`이다. 이 endpoint는 Server-Sent Events를 사용한다.

| Event | UI behavior |
|---|---|
| `status` | 말풍선 위 작은 진행 줄에 마지막 상태 한 줄을 표시한다. 문구는 요청별 LLM stream planner가 생성한다. |
| `answer_delta` | 같은 assistant 말풍선의 Markdown 본문에 누적한다. 표와 목록은 조각이 쌓일수록 다시 렌더링될 수 있다. |
| `final` | 최종 `answer_html`, `links`, `artifacts`, `evidence_ledger`, `affordances`, `suggested_questions`로 말풍선을 확정한다. |
| `error` | 현재 말풍선을 실패 메시지로 바꾸고 사용자가 다시 시도할 수 있게 한다. |

기본 화면에서 사용자가 계속 보게 되는 진행 정보는 `status`의 마지막 한 줄이다. 이 한 줄은 고정 rule 문구가 아니라 질문, 현재 페이지, 예상 산출물에 맞춰 LLM stream planner가 생성한다. stream planner는 같은 JSON에서 route도 함께 결정해 SSE 요청 안에서 status와 router LLM 호출이 중복되지 않게 한다. 운영 계약은 “서로 다른 LLM-generated status 후보를 요청하고, usable한 고유 status만 표시”하는 방식이다. Gemma가 중복 문장을 만들면 서버는 중복을 반복 노출하지 않는다. stream planner가 usable status를 하나도 만들지 못하거나 JSON plan을 만들지 못하면 서버는 규칙 문구로 보충하지 않고 `diagnostic` event에 `status_generation_failed` 또는 `boi_agent_router_unavailable`을 남긴다. Native Agent가 답할 수 있으면 같은 assistant 말풍선은 `answer_ready`와 `final`까지 계속 진행한다. 상세 진행 이력은 같은 말풍선 안의 접힌 `진행 단계` details에 보관해 디버깅과 설명 가능성은 유지하되, 긴 Agent 요청 중 화면을 진행 로그로 채우지 않는다.

추천 질문은 두 종류로 나눈다. 첫 대화 전에는 `/api/agents/boi-wiki/suggestions`가 현재 URL, page context, 접근 정책, Agent 기능에 맞는 page starter 질문을 생성한다. Agent가 답변한 뒤에는 `/api/agents/boi-wiki/chat`의 `final.suggested_questions`가 canonical이다. 이 질문은 원 질문, 최종 답변 요약, `evidence_ledger`, `artifacts`, `affordances`, links, citations, tool trace, ACL/RBAC 결과를 바탕으로 생성한 answer-scoped follow-up이다.

Suggestion writer가 timeout, invalid JSON, 미설정으로 실패하면 서버는 템플릿 질문을 조용히 내보내지 않고 `component_errors`에 `boi_agent_suggestions_unavailable`을 남긴다. 답변 본문과 artifact는 유지되며, Pet UI는 해당 assistant 말풍선 아래에서 추천 질문 상태만 작게 실패로 표시한다. 템플릿 기반 `page_context_suggestions()`는 내부 테스트에서 명시적으로 monkeypatch할 때만 쓰는 보조 경로이며, 운영 fallback으로 쓰지 않는다. Pet UI는 답변 완료 후 page starter를 다시 덮어쓰지 않고, 각 assistant 말풍선 아래에 `다음에 물어볼 수 있는 질문`으로 answer-scoped follow-up chip을 렌더링한다. follow-up chip을 누르면 직전 message context를 `conversation`에 포함해 서버로 보내므로 “그럼 부족한 것 초안 만들어줘”, “첫 번째 Action 자세히 봐줘” 같은 생략형 질문도 이전 답변의 근거와 affordance를 기준으로 해석한다.

```mermaid
flowchart TD
  ASK["User submits question"] --> PENDING["Pending assistant message"]
  PENDING --> STATUS["status event<br/>one-line progress"]
  STATUS --> DELTA["answer_delta<br/>append Markdown text"]
  DELTA --> FINAL["final event<br/>replace with rendered HTML + artifacts"]
  STATUS --> STOP{"User clicks 중지?"}
  STOP -->|yes| ABORT["AbortController cancels request"]
  STOP -->|no| DELTA
```

```mermaid
flowchart TD
  ANSWER["Agent final answer"] --> LEDGER["Evidence ledger<br/>docs, events, actions, trace, memory"]
  ANSWER --> ART["Artifacts<br/>Mermaid, table, cards"]
  ANSWER --> AFF["Affordances<br/>ask, open, check, draft, approve"]
  LEDGER --> FUP["LLM follow-up writer"]
  ART --> FUP
  AFF --> FUP
  FUP --> VERIFY["ACL/action/link validation"]
  VERIFY --> CHIPS["Answer-scoped follow-up chips"]
```

`중지`는 현재 streaming request의 `AbortController`를 중단한다. 중지 후에는 상태를 `생성을 중지했습니다.`로 바꾸고, 사용자가 새 질문이나 `새 대화`를 바로 시작할 수 있어야 한다.

Streaming 중에도 panel은 하단으로 자동 스크롤된다. 사용자가 다른 BoI Wiki 페이지로 이동하면 sessionStorage에 저장된 messages/draft/scroll 상태를 복원하고, 현재 URL과 page title만 새 화면 기준으로 갱신한다. Agent 안 링크 클릭으로 화면 전환이 발생하면 panel은 닫힌 상태로 둔다.

# Artifact Rendering Flow

```mermaid
flowchart TD
  RESP["Agent response"] --> MD["Markdown answer"]
  RESP --> ART["artifacts array"]
  MD --> TABLE["Markdown table renderer"]
  MD --> M1["Mermaid fenced block"]
  MD --> IMG["Markdown image"]
  ART --> M2["Mermaid artifact"]
  M1 --> DEDUPE["dedupe Mermaid by normalized source"]
  M2 --> DEDUPE
  IMG --> INLINE
  DEDUPE --> INLINE["inline compact render"]
  INLINE --> VIEWER["click to large viewer"]
```

# Markdown Rendering Contract

Pet Agent는 서버가 내려준 `answer_markdown`을 그대로 원문 텍스트로 노출하지 않는다. 다음 문법은 채팅 안에서 HTML로 렌더링되어야 한다.

| Markdown input | Rendered behavior |
|---|---|
| heading, paragraph | 읽기 쉬운 section과 문단 |
| `-`, `*`, `+` list | bullet list |
| `1.` list | ordered list |
| `- [ ]`, `- [x]` | disabled checklist |
| table | `.boi-agent-table-wrap` 안의 HTML table |
| inline code, link, bold, italic, strike | inline semantic HTML |
| bare `http://` or `https://` URL | clickable link |
| Markdown image syntax | inline image with click-to-zoom viewer |
| `mermaid` fenced block | Mermaid diagram with source fallback |

`workflow_summary`와 `gap_table` artifact는 JSON `<pre>`가 아니라 table artifact로 보여준다. 객체나 배열 cell은 표 안에서 list 또는 compact JSON block으로 정리하되, 일반 workflow 요약은 사람이 바로 읽는 표가 기본이다.

Markdown 본문 스타일은 메시지 작성자 라벨 스타일과 분리한다. 예를 들어 `**굵게**`는 문단 안의 inline emphasis로 남아야 하며, 작성자 라벨처럼 block으로 떨어지면 안 된다. 표 parser는 inline code, link URL, escaped pipe 안의 `|`를 셀 분리자로 오해하지 않아야 한다.

# Execution Cards

상태 변경이 필요한 Agent 응답은 `artifacts`에 confirmation card를 넣을 수도 있고, canonical field인 `execution_cards`에만 넣을 수도 있다. Pet UI는 둘을 같은 승인 카드로 렌더링해야 하며, 같은 operation/payload가 양쪽에 중복되어 있으면 한 번만 보여준다. 이 규칙 덕분에 Web Pet, REST API client, MCP client가 같은 `boi-agent.response.v1` 응답을 소비할 수 있다.

실행 카드는 권한 판단을 UI가 추정하지 않는다. 서버가 내려준 required field인 `required_role`과 `permission`을 표시하고, `permission.allowed`가 `false`이면 primary 실행 버튼을 만들지 않는다. 사용자에게는 `권한 필요`와 필요한 role을 보여주고, 자세한 role binding 사유는 `기술 세부정보`에 접는다.

| Field | UI behavior |
|---|---|
| `display.title` | 카드 제목 |
| `display.status_label` | `먼저 확인`, `승인 필요`, `권한 필요` 같은 업무 상태 |
| `display.risk_label` | 고위험/권한 필요/일반 요청 표시 |
| `required_role` | 필요한 role을 technical details와 권한 안내에 표시 |
| `permission.allowed=false` | 실행 버튼 숨김, `권한이 필요합니다` 안내 표시 |
| `technical_details` | operation, required role, trace/action id 같은 식별자를 접힌 영역에 표시 |

# Artifact Viewer

Artifact는 채팅 안에서는 compact하게 보이고, `크게 보기`를 누르면 modal viewer에서 크게 확인한다. Viewer 대상은 Mermaid, table, image, task card, confirmation card다. Markdown image도 이미지를 클릭하면 같은 viewer로 열린다. Mermaid는 Markdown fenced block과 artifact가 같은 source를 포함하면 하나만 렌더링하고, artifacts 배열 안에 같은 source가 중복되어도 한 번만 보여준다.

Pet Agent는 모든 주요 화면에 공통으로 mount된다. 따라서 Mermaid renderer도 문서 상세 전용이 아니라 app shell 전역 script로 로드한다. 사용자가 문서 페이지에서 다이어그램 답변을 받은 뒤 Event Types, Actions, Events 같은 다른 화면으로 이동해도 sessionStorage에서 복원된 Mermaid artifact는 다시 SVG로 렌더링되어야 한다.

Mermaid library 로드 실패는 일시적인 네트워크/CDN 장애일 수 있으므로 실패한 loader promise를 세션 동안 고정하지 않는다. 렌더링 실패 시 해당 diagram은 source fallback을 열어 사용자가 원문을 볼 수 있게 하고, 다음 페이지 이동이나 새 Agent 답변에서 renderer 로드를 다시 시도한다. 이렇게 해야 한 번의 CDN timeout 때문에 이후 모든 artifact가 렌더링되지 않는 상태로 고정되지 않는다.

# BoI Inbox Handoff

Pet Agent에는 Inbox 탭을 두지 않는다. Agent가 업무 검토나 승인 판단이 필요하다고 판단하면 답변 안에 `BoI Inbox에서 보기`, `검증된 보고서 BoI 보기`, `관련 SOP 보기`, `Event 보기`, `Action 보기` 같은 사용자-facing 링크만 제공한다.

업무 카드, 검토 보고서, 승인/반려/보류/추가 근거 요청 UI는 `/inbox` 전용 화면의 책임이다. Pet Agent는 보고서 내용을 바탕으로 질문에 답할 수 있지만, 업무함 목록이나 decision UI를 직접 렌더링하지 않는다.

# Related Documents

- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
