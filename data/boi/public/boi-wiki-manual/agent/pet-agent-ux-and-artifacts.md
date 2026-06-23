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

Pet Agent는 모든 BoI Wiki 화면에서 현재 페이지를 이해하고 질문, 검색, 도식, Inbox 확인, 조치 기록을 도와주는 보조 UI다. 메뉴는 `Agent`와 `Inbox` 두 개만 둔다. Memory와 Dictionary는 Pet 메뉴가 아니라 BoI 문서와 harness/MCP 기능으로 관리한다.

# UX Principles

- 현재 페이지 context를 기본으로 질문을 추천한다.
- 링크 클릭으로 페이지가 바뀌어도 panel, tab, messages, draft, scroll 상태를 유지한다.
- Enter는 전송, Shift+Enter는 줄바꿈이다.
- 생성 중지는 사용자가 긴 답변을 멈추기 위한 기본 조작이다.
- Mermaid, 표, 이미지, task card artifact는 작은 채팅 영역에 억지로 밀어 넣지 않고 큰 viewer로 열 수 있어야 한다.

# Artifact Rendering Flow

```mermaid
flowchart TD
  RESP["Agent response"] --> MD["Markdown answer"]
  RESP --> ART["artifacts array"]
  MD --> TABLE["Markdown table renderer"]
  MD --> M1["Mermaid fenced block"]
  ART --> M2["Mermaid artifact"]
  M1 --> DEDUPE["dedupe by source"]
  M2 --> DEDUPE
  DEDUPE --> INLINE["inline compact render"]
  INLINE --> VIEWER["click to large viewer"]
```

# Inbox Display

Inbox는 기술 ID보다 일반 사용자가 이해할 업무 문구를 우선한다.

| Internal status | Display wording |
|---|---|
| `approval_required` | 공유 전 승인 필요 |
| `manual_required` | 조치 내용 입력 필요 |
| `manual_blocked` | 업무 상태 확인 필요 |
| `needs_followup` | 후속 확인 필요 |

`trace_id`, `action_key`, `request_id`, raw URL은 `기술 세부정보`에 접는다.

# Related Documents

- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
