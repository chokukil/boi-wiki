---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 업무 BoI-first 개념 모델
description: SOP 기반 업무, 반복 업무, 비정형 업무를 업무 BoI 중심으로 이해하고 WorkflowDefinition으로 연결하는 기준
tags: [BoIWiki, WorkBoI, WorkflowDefinition, SOP, Agent]
timestamp: 2026-06-28T16:00:00+09:00
boi_id: boi:public:boi-wiki-manual:concepts:work-boi-first-model
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
    ref: data/workflow_catalog/workflows.yaml
  - type: repo
    ref: boi_api/app/native_agent.py
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

BoI Wiki의 중심은 `업무 BoI`다. SOP는 공식 절차가 있는 업무를 설명하는 강한 기준이지만 모든 업무가 처음부터 SOP를 갖지는 않는다. 따라서 Agent와 사용자는 먼저 업무 목적과 필요한 근거를 확인하고, SOP가 있으면 SOP 흐름에 맞추며, SOP가 없으면 비정형 업무 BoI 또는 반복 업무 패턴으로 시작한다.

# Concept Flow

```mermaid
flowchart TD
  Q["사용자 요청"] --> G["업무 목적 파악"]
  G --> B["채워야 할 업무 BoI 정의"]
  B --> D{"공식 SOP가 있는가?"}
  D -->|"있음"| S["SOP 기반 업무"]
  D -->|"없지만 반복됨"| P["반복 업무 / work-pattern"]
  D -->|"일회성"| A["비정형 업무 BoI"]
  S --> W["WorkflowDefinition 연결"]
  P --> W
  A --> L["Local Private BoI로 정리"]
  L --> R{"반복 가치가 있는가?"}
  R -->|"예"| W
  R -->|"아니오"| K["개인/팀 지식으로 보관"]
  W --> E["Event / Action / 수동 조치 / 근거 연결"]
  E --> C["완결 조건 확인"]
```

# 업무 유형

| 유형 | 언제 쓰는가 | 대표 산출물 |
|---|---|---|
| SOP 기반 업무 | 공식 절차와 단계가 있는 업무 | SOP, WorkflowDefinition, 실행 현황, Action, 수동 조치 |
| 반복 업무 | 매주/매월/상황별로 반복되지만 공식 SOP가 없는 업무 | work-pattern, WorkflowDefinition draft, Skill 후보 |
| 일회성 비정형 업무 | 회의 정리, 임시 분석, 개인 보고 초안처럼 바로 표준화할 필요가 없는 업무 | local-private 업무 BoI, context pack, promotion draft |

# 반도체 도메인 예시

| 요청 | 판단 | 처리 방향 |
|---|---|---|
| 설비 Alarm이 발생했을 때 Trend/Raw/원인 분석 흐름을 알려줘 | SOP 기반 업무 | 설비 이상 대응 SOP와 WorkflowDefinition을 기준으로 설명 |
| 직개발 결과 확인에서 Response Trend와 Map View를 확인해야 해 | SOP + evidence 기반 업무 | SOP 단계, 필요한 evidence, Action 명세를 연결 |
| 매주 FAB Trend 비교 보고를 자동화하고 싶어 | 반복 업무 | 개인/팀 work-pattern을 만들고 WorkflowDefinition draft 후보 제안 |
| 오늘 회의 내용을 BoI로 정리해줘 | 비정형 업무 | Local Private 업무 BoI로 저장하고 공유 필요 시 promotion draft 생성 |
| 신규 품질 API를 등록하고 싶어 | 업무 흐름 연결 | 업무 목적, 중복 WorkflowDefinition, Action 연결, 검증 초안 순서로 처리 |

# Agent 판단 기준

BoI Agent는 질문을 받으면 먼저 SOP 여부를 묻지 않는다. 대신 업무 목적, 필요한 업무 BoI, 근거, 다음 행동을 확인한다. SOP가 있으면 SOP 단계로 정렬하고, SOP가 없으면 업무 패턴이나 비정형 업무 BoI로 답한다. 반복 가치가 보이면 WorkflowDefinition, SOP, Skill 후보를 제안한다.

# Related Documents

- [WorkflowDefinition Registration Guide](/public/boi-wiki-manual/workflows/workflow-definition-registration-guide.md)
- [Work Context Pack](/public/boi-wiki-manual/agent/work-context-pack.md)
- [BoI Wiki Local Integration](/public/boi-wiki-manual/local/boi-wiki-local-integration.md)
