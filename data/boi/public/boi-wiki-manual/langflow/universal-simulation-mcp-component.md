---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 공유 Agent Component로 교체하기
description: Agent Hub 공유 Component를 대표 Flow의 Agent 자리에 안전하게 조합하는 방법
tags: [Manual, AgentHub, Component, AgentSlot]
timestamp: 2026-07-27T15:20:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-component
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: langflow/custom_components/boi/boi_universal_simulation_mcp_agent.py
  - type: repo
    ref: validation/agent-playground/assets/shared_gemma_simulation_agent.py
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 상태를 구분한다

- `배포됨`: Component가 프로젝트에 존재한다.
- `Agent 연결 필요`: Flow 실행 경로에는 아직 없다.
- `연결됨`: `boi.agent-slot.v1` 계약으로 기존 Agent 자리를 교체했다.
- `실행 검증됨`: 실제 runtime provenance에 Component ID가 남았다.

배포만 된 Component를 사용 완료로 보지 않는다. Chat Input에서 Chat Output까지 경로가 이어지고 결과가 `BoIWikiSave`로 전달되어야 한다.

# 자동 연결 조건

입력 `agent_context`, 출력 `agent_result`가 명확하고 근거·Task Context·저장 계약을 보존하는 Component만 자동 연결한다. 포트가 여러 개거나 타입이 불명확하면 Langflow Canvas에서 수동 연결하고 다시 검증한다.

사내 Python MCP 파일을 적용할 때도 원본 파일을 올리지 않고 이 계약의 Component로 변환한다.
