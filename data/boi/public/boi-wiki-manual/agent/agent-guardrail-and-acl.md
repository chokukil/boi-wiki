---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Agent 권한과 실행 안전 기준
description: Web·REST·MCP·외부 Agent가 같은 identity, ACL, Task mode, Harness와 confirmation을 적용하는 기준
tags: [Manual, Agent, ACL, RBAC, Guardrail, Harness, MCP]
timestamp: 2026-07-12T10:45:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:agent-guardrail-and-acl
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
    ref: boi_api/app/v2/policy.py
  - type: repo
    ref: boi_api/app/v2/harness.py
  - type: repo
    ref: boi_api/app/v2/routes.py
  - type: repo
    ref: boi_api/app/v2/models.py
review:
  reviewer: agent-curator
  review_status: reviewed
---

# 핵심 원칙

BoI Agent는 자연어를 이해하지만 실행 권한까지 LLM이 결정하지 않는다. LLM은 목적과 계획 후보를 구조화하고, 코드는 identity, ACL, 입력·출력 schema, Task mode, 위험도와 confirmation을 검증한다.

```mermaid
flowchart LR
  REQ["사용자·외부 Agent 요청"] --> ID["SSO 또는 PAT identity"]
  ID --> ACL["문서·업무 ACL"]
  ACL --> MODE["Manual·Copilot·Autopilot"]
  MODE --> H["Harness preflight·validate"]
  H --> RISK{"외부 영향·위험도"}
  RISK -->|읽기·private draft| GO["계속"]
  RISK -->|실행·게시·중고위험| CONF["담당자 확인"]
  CONF --> APPLY["적용 후 재검증"]
```

# Identity

- Web은 사내 SSO session identity를 사용한다.
- MCP, Codex와 Claude는 BoI Wiki에서 발급한 PAT를 사용한다.
- v2는 query string의 `employee_id`를 권한 근거로 신뢰하지 않는다.
- PAT는 한 번만 표시하고 hash로 저장한다. 기본 scope는 `boi.read`, `boi.draft`다.
- `boi.execute.low`는 RBAC가 허용하는 사용자만 선택할 수 있으며 `boi.admin`은 자체 발급할 수 없다.

# 읽기와 검색

검색 전과 citation 반환 전에 모두 ACL을 확인한다. Private 문서, 팀 문서, Data Lake 원본과 runtime 이력은 사용자에게 보일 수 있는 범위만 Context에 들어간다. ACL이 다른 source의 존재 여부도 응답으로 새지 않게 한다.

# 초안과 실행

| 요청 | 기본 처리 |
|---|---|
| 질문·검색·관계 보기 | 권한 범위 안에서 즉시 수행 |
| private 노트·SOP/Event/Skill 초안 | preview와 draft 생성 가능 |
| Team/Public 지식 변경 | Harness 검증 후 promotion review |
| 저위험 allowlist Action | Task mode와 scope가 허용할 때 plan/confirm |
| 중·고위험 또는 외부 부작용 | 항상 명시적 confirmation 필요 |

Deep Work와 subagent는 production mutation tool을 받지 않는다. 결과는 evidence가 연결된 draft로만 반환하며 실제 적용은 BoI API의 plan과 confirmation을 다시 거친다.

# Task mode

- Manual: 실행과 완료 판단은 사람이 한다.
- Copilot: Agent가 private draft와 preview를 준비하지만 사람이 최종 확인한다.
- Autopilot: allowlist의 저위험 작업과 검증 가능한 system binding만 자동 수행한다.

Autopilot Task에 연결된 완료 근거가 없으면 초안 저장은 가능하지만 실행은 `연결 필요`로 차단한다.

# 기록과 감사

모든 plan, confirmation, Action 결과, 사람 입력, Evidence Ledger와 promotion은 principal, timestamp, source refs를 남긴다. Agent의 chain-of-thought는 저장하거나 노출하지 않고, 검증에 필요한 계획 요약·근거·결과만 보존한다.

# 관련 문서

- [Work Learning System](/docs/boi:public:boi-wiki-manual:agent:work-learning-system)
- [MCP 등록과 사용](/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp)
- [Visibility와 승격 정책](/docs/boi:public:boi-wiki-manual:operations:visibility-and-promotion-policy)
