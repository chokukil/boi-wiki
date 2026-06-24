---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Native BoI Agent Architecture
description: BoI Agent production path를 boi-api 내부 Native Agent로 운영하는 전체 아키텍처
tags: [BoIWiki, Agent, LangGraph, OntologySearch, Architecture]
timestamp: 2026-06-23T10:00:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:native-boi-agent-architecture
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
    ref: boi_api/app/native_agent.py
  - type: repo
    ref: boi_api/app/main.py
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

BoI Agent의 production path는 `boi-api` 내부 Native Agent다. Langflow는 visual workflow, demo, debug backend로 유지하지만 사용자-facing Agent 응답의 필수 runtime dependency가 아니다.

Native Agent는 LangGraph state graph와 순차 fallback을 함께 제공한다. LLM은 Router와 선택적 planner/composer에 쓰이고, 실행 경계는 Python typed tool dispatcher가 통제한다. Router는 `llm_first`가 기본이며, `BOI_AGENT_ROUTER_LLM_ENABLED=auto`에서는 실제 OpenAI-compatible LLM URL이 설정된 배포에서 LLM Router를 사용하고 placeholder 개발 URL에서는 rules fallback을 사용한다. Router LLM은 사용자 답변을 생성하지 않고 `route`, `intent`, `confidence` JSON만 반환한다. JSON이 없거나 timeout이면 rules fallback이 이어받는다.

# Architecture

```mermaid
flowchart TD
  UI["Web Pet Agent"] --> STREAM["BoI API SSE<br/>/api/agents/boi-wiki/chat/stream"]
  MCP["boi-wiki-mcp<br/>boi_agent_chat"] --> API
  STREAM --> API["BoI API JSON<br/>/api/agents/boi-wiki/chat"]
  API --> ROUTER["LLM Router first<br/>rules fallback"]
  ROUTER --> AGENT["Native BoI Agent<br/>LangGraph + sequential fallback"]
  AGENT --> ACL["Access Policy Gate<br/>visibility + classification + team RBAC"]
  AGENT --> RET["Ontology Retrieval<br/>Dictionary + OKF graph + catalogs"]
  AGENT --> TOOLS["Typed Tool Dispatcher"]
  TOOLS --> DOCS["BoI Markdown / OKF docs"]
  TOOLS --> LOGS["Event / Action / Activity JSONL"]
  TOOLS --> CAT["Event / Action catalogs"]
  TOOLS --> MEM["Private Memory / Dictionary"]
  RET --> ACL2["ACL pruning"]
  TOOLS --> ACL2
  ACL2 --> SAFE["Safety Gate<br/>mutation requires confirmation"]
  SAFE --> OUT["Unified Agent Response<br/>links + citations + artifacts"]
  OUT --> UI
  OUT --> MCP
  LF["Langflow"] -. "optional visual/debug backend" .-> API
```

# Runtime Components

| Component | Role |
|---|---|
| `boi-api` | Official Agent API, auth, ACL, page context, search, tool dispatch, safety boundary |
| `NativeBoiAgent` | LangGraph nodes and deterministic fallback |
| Ontology search | Compact grouped retrieval for SOP, Event, Action, Dictionary, BoI, runtime evidence |
| MCP | External agent interface that calls the same BoI API |
| Langflow | Optional visual workflow and connector demo, not the required Agent engine |

# Response Streaming Contract

BoI Agent는 동기 JSON API와 streaming API를 모두 제공한다.

| Interface | Use |
|---|---|
| `POST /api/agents/boi-wiki/chat` | machine-to-machine JSON response, MCP bridge fallback, tests |
| `POST /api/agents/boi-wiki/chat/stream` | Web Pet Agent default. Server-Sent Events로 진행 상태와 답변 조각을 전달 |

Streaming response는 다음 event 순서를 따른다.

```mermaid
sequenceDiagram
  participant UI as Pet Agent UI
  participant API as BoI API
  participant Agent as Native BoI Agent

  UI->>API: POST /chat/stream
  API-->>UI: status "현재 화면 맥락을 확인하고 있습니다."
  API->>Agent: route + page context + ontology retrieval
  loop while Agent runs
    API-->>UI: status "관련 BoI 문서와 Event/Action을 찾고 있습니다."
  end
  Agent-->>API: unified response
  API-->>UI: answer_delta chunks
  API-->>UI: final full JSON response
```

`status` event는 사용자가 장시간 요청을 멈춘 것으로 오해하지 않도록 한 줄 진행 상황만 전달한다. 실제 최종 응답의 canonical contract는 `final` event의 JSON이며, 기존 `/chat` 응답과 같은 `answer_markdown`, `answer_html`, `links`, `citations`, `artifacts`, `context_summary`, `route`, `intent` 필드를 유지한다.

# Backend Selection

`BOI_AGENT_BACKEND` controls the runtime:

| Value | Meaning |
|---|---|
| `native` | Default. Fast and deep routes use Native BoI Agent. |
| `hybrid` | Native first, optional Langflow fallback for deep requests. |
| `langflow` | Legacy/debug mode. Deep route calls Langflow and returns 503 if unavailable. |

# Related Documents

- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
- [Native BoI Agent Tool Loop](/public/boi-wiki-manual/agent/native-boi-agent-tool-loop.md)
- [Ontology Retrieval and Search](/public/boi-wiki-manual/agent/ontology-retrieval-and-search.md)
- [Safety, Approval, and Memory](/public/boi-wiki-manual/agent/safety-approval-and-memory.md)
- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [BoI Profile ACL Policy](/public/boi-wiki-manual/security/boi-profile-acl-policy.md)
- [Deployment and Verification](/public/boi-wiki-manual/agent/deployment-and-verification.md)
