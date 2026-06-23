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

Native Agent는 LangGraph state graph와 순차 fallback을 함께 제공한다. LLM은 Router와 선택적 planner/composer에 쓰이고, 실행 경계는 Python typed tool dispatcher가 통제한다.

# Architecture

```mermaid
flowchart TD
  UI["Web Pet Agent"] --> API["BoI API<br/>/api/agents/boi-wiki/chat"]
  MCP["boi-wiki-mcp<br/>boi_agent_chat"] --> API
  API --> ROUTER["LLM Router first<br/>rules fallback"]
  ROUTER --> AGENT["Native BoI Agent<br/>LangGraph + sequential fallback"]
  AGENT --> RET["Ontology Retrieval<br/>Dictionary + OKF graph + catalogs"]
  AGENT --> TOOLS["Typed Tool Dispatcher"]
  TOOLS --> DOCS["BoI Markdown / OKF docs"]
  TOOLS --> LOGS["Event / Action / Activity JSONL"]
  TOOLS --> CAT["Event / Action catalogs"]
  TOOLS --> MEM["Private Memory / Dictionary"]
  AGENT --> SAFE["Safety Gate<br/>mutation requires confirmation"]
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
- [Deployment and Verification](/public/boi-wiki-manual/agent/deployment-and-verification.md)
