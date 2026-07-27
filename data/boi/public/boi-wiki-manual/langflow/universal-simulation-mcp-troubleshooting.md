---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Universal Simulation MCP 문제 해결
description: 대표 Flow, Gemma, MCP, Agent Hub 배포와 저장 권한 오류 점검
tags: [Manual, Troubleshooting, MCP, Langflow]
timestamp: 2026-07-27T15:30:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-troubleshooting
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: validation/agent-playground-mainline/universal_simulation_mcp_e2e.mjs
  - type: repo
    ref: scripts/check_agent_playground_langflow_boundary.py
review:
  reviewer: tf-lead
  review_status: reviewed
---

# MCP 도구가 보이지 않는다

대표 Flow와 프로젝트가 맞는지 확인하고 `MCP 도구 준비`를 다시 실행한다. tool 이름은 정확히 `boi_universal_simulate`여야 하며 인증 방식은 API Key다.

# Gemma 호출이 실패한다

Langflow 환경의 `BOI_LLM_BASE_URL`, `BOI_AGENT_EXAMPLE_MODEL`, `BOI_LLM_API_KEY` Credential 이름을 확인한다. 값은 Flow JSON이나 화면에 복사하지 않는다. 응답은 정해진 JSON 필드를 반환해야 한다.

# 근거가 부족하다

Ontology provenance가 없으면 문서 fallback으로 표시되는 것이 정상이다. 접근 권한이 없는 항목의 ID나 내용은 보이지 않고 제외 건수만 표시된다. 질문에 SOP라는 단어가 있다고 허위 SOP Context를 만들지 않는다.

# MCP에서 개인 초안이 저장되지 않는다

정상 동작이다. 외부 MCP는 preview-only다. 개인 저장은 Playground 또는 BoI Action에서 `private_draft`를 명시하고 호출자 run token이 검증된 경우에만 가능하다.

# Agent Hub 배포 결과가 안 보인다

Agent Hub에서 선택한 endpoint와 프로젝트가 Playground와 같은지 확인한다. 새로 배포한 뒤 Flow 목록을 새로고침하고 exact Flow ID와 checksum을 다시 검증한다. Agent Hub 코드를 수정해서 우회하지 않는다.
