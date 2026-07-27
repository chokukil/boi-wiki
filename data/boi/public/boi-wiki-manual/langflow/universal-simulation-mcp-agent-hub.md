---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Hub에서 대표 Flow 배포하기
description: 수정 없는 Agent Hub UI로 Universal Simulation MCP를 개인 프로젝트에 배포하는 절차
tags: [Manual, AgentHub, Langflow, Deployment]
timestamp: 2026-07-27T15:15:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-agent-hub
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: langflow/agent_hub/README.md
  - type: repo
    ref: validation/agent-hub/playwright_e2e.mjs
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 배포

1. Playground에서 대표 Flow의 preview와 MCP 호출을 통과시킨다.
2. secret-free 자산을 내려받는다.
3. Agent Hub 기존 UI에서 개인 Langflow endpoint와 API Key를 등록한다.
4. 연결 시험 후 `boi-{사번}` 프로젝트를 선택한다.
5. Flow JSON과 필요한 Component를 배포한다.
6. Playground로 돌아와 같은 endpoint/project에서 배포 결과를 찾는다.
7. exact Flow ID와 live checksum이 맞는 Flow만 전체 검증한다.

Agent Hub에 BoI PAT나 Action run token을 등록하지 않는다. Agent Hub는 배포 Control Plane이며 Action 실행 경로에 들어가지 않는다. 대표 모달 선정은 검증 자료를 받은 Agent Hub 담당자가 후속으로 수행한다.

# 두 URL

- 브라우저 URL: 사용자가 Canvas를 여는 주소
- 배포 URL: Agent Hub에서 `/api/v1`을 호출할 수 있는 host-root 주소

사내 Caddy/DNS는 이 저장소에서 수정하지 않는다.
