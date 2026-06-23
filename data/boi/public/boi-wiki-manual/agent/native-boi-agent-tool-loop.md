---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Native BoI Agent Tool Loop
description: Native BoI Agent의 state graph, bounded tool loop, artifact 생성 기준
tags: [BoIWiki, Agent, LangGraph, ToolLoop]
timestamp: 2026-06-23T10:05:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:native-boi-agent-tool-loop
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
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

Native BoI Agent는 LangGraph node 이름을 코드 구조와 일치시킨다. LangGraph가 없거나 버전 차이로 실패하면 같은 node 순서를 순차 실행한다.

# State Graph

```mermaid
flowchart TD
  A["classify_intent"] --> B["resolve_page_context"]
  B --> C["retrieve_ontology"]
  C --> D["plan_tools"]
  D --> E["execute_tools_loop"]
  E --> F["evaluate_coverage"]
  F --> G["compose_answer"]
  G --> H["verify_links_and_artifacts"]
  H --> I["safety_gate"]
```

# Tool Loop

```mermaid
sequenceDiagram
  participant U as User
  participant API as BoI API
  participant Agent as Native Agent
  participant Search as Ontology Search
  participant Tool as Typed Tools

  U->>API: question + current_url
  API->>Agent: route + page context pack
  Agent->>Search: compact retrieval
  Search-->>Agent: grouped results + knowledge panel
  loop max 5 tool calls
    Agent->>Tool: boi_get / workflow_status / action_spec_lookup
    Tool-->>Agent: typed result
  end
  Agent->>Agent: coverage + artifact generation
  Agent-->>API: answer_markdown + links + citations + artifacts
```

# Tool Set

| Tool | Purpose |
|---|---|
| `ontology_search` | Dictionary, OKF graph, SOP/Event/Action catalog, runtime evidence 검색 |
| `boi_get` | 특정 BoI/OKF 문서 조회 |
| `event_type_lookup` | Event Type catalog 조회 |
| `action_spec_lookup` | Action contract와 문서 조회 |
| `workflow_status` | trace 기준 SOP 진행 상태 조회 |
| `trace_context_lookup` | event/action/generated BoI evidence 조회 |
| `dictionary_resolve` | private -> team -> public 용어 해석 |
| `memory_recall` | private agent-memory 요약 조회 |
| `agent_inbox` | 담당자가 처리해야 할 action inbox 조회 |

# Artifact Policy

| Intent | Artifact |
|---|---|
| `diagram` | Mermaid flowchart |
| `gap_check` | missing Action Spec table |
| `workflow_explain` | Event -> SOP -> Action -> Manual Handoff table |
| `trace_reasoning` | trace evidence summary |
| `inbox` | 일반 구성원용 업무 카드 |

Mermaid는 `artifacts`와 Markdown code block 둘 다 제공한다. Web BoI Wiki는 `mermaid` fenced block을 diagram으로 렌더링한다.
