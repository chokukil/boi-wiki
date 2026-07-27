---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Universal Simulation MCP 3분 시작하기
description: 자연어 요청을 Wiki·Ontology 근거와 Gemma 시뮬레이션으로 처리하고 미리보기로 확인하는 빠른 시작
tags: [Manual, AgentPlayground, Langflow, MCP, Simulation]
timestamp: 2026-07-27T15:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-quickstart
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: langflow/flows/boi_universal_simulation_mcp.json
  - type: repo
    ref: langflow/compatibility-manifest.json
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 무엇을 하는 Flow인가

`BoI Universal Simulation MCP`는 업무 요청을 실제 시스템에 반영하지 않고 다음 순서로 검토한다.

1. 질문이나 선택한 Task를 받는다.
2. 접근 가능한 Wiki와 provenance가 있는 Ontology 관계로 업무 맥락을 만든다.
3. LM Studio Gemma가 근거 안에서 처리 과정과 예상 결과를 시뮬레이션한다.
4. source reference, Ontology provenance, 부족 근거와 제한을 보존한다.
5. 기본값으로 Wiki를 바꾸지 않는 초안 후보를 보여준다.

# 3분 실행

1. `/playground`에서 Langflow 연결과 자동 준비를 완료한다.
2. 추천 Flow `BoI Universal Simulation MCP`를 선택한다.
3. `샘플 요청 실행`을 누른다.
4. 업무 맥락, Ontology 관계, Wiki 근거와 부족 근거를 확인한다.
5. 필요하면 `MCP 도구 준비` 후 `실제 MCP 호출`을 실행한다.

결과의 `SIMULATED` 표시는 실제 업무 시스템을 호출하지 않았다는 뜻이다. 외부 MCP 실행은 항상 preview이며 개인 Wiki에 저장하지 않는다.

# 다음 단계

- [대표 Flow Canvas 읽는 법](/docs/boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-canvas)
- [Langflow 프로젝트를 MCP 도구로 연결하기](/docs/boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-connect)
- [Agent Hub에서 대표 Flow 배포하기](/docs/boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-agent-hub)
