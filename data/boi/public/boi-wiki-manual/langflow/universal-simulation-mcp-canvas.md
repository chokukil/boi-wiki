---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 대표 Flow Canvas 읽는 법
description: BoI Universal Simulation MCP의 다섯 단계와 교체 가능한 Agent 경계
tags: [Manual, Langflow, Canvas, Ontology]
timestamp: 2026-07-27T15:05:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-canvas
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: scripts/setup_langflow_reference_flows.py
  - type: repo
    ref: langflow/flows/boi_universal_simulation_mcp.json
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 다섯 단계

```text
요청 입력
→ Wiki·Ontology 업무 맥락
→ 업무 시뮬레이션 Agent
→ Wiki 지식 자산화
→ 결과 확인
```

- `요청 입력`: 자연어만 입력해도 된다. 실제 Task는 Playground에서 선택한다.
- `Wiki·Ontology 업무 맥락`: Task/SOP/Wiki/일반 질문을 판별하고 Ontology를 우선 사용한다. 검증된 관계가 없을 때만 문서로 보완한다.
- `업무 시뮬레이션 Agent`: LM Studio Gemma를 호출하되 실제 사내 시스템을 처리한 것처럼 쓰지 않는다.
- `Wiki 지식 자산화`: 근거와 provenance를 보존한다. 외부 MCP에서는 preview만 허용한다.
- `결과 확인`: 사람이 읽는 Markdown과 Action이 쓰는 구조화 data를 함께 유지한다.

이 다섯 단계는 대표 Flow의 이해를 돕는 설명이다. Playground가 모든 Flow를 이 선형
구조로 다시 그린다는 뜻은 아니다. 분기·병합·루프를 포함한 실제 구조는 Flow 목록의
`원본 열기`에서 Langflow Canvas로 확인한다.

# 무엇을 교체할 수 있나

세 번째 Agent만 `boi.agent-slot.v1` 호환 Component로 교체할 수 있다. 입력 `agent_context`, 출력 `agent_result`를 지키고 source references, Ontology provenance, Task Context와 grounding을 삭제하면 안 된다.

Canvas의 Note에는 키를 넣지 않는다. Langflow API Key, BoI PAT, Action run token은 Flow JSON에도 저장하지 않는다.
