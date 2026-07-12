---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki 한눈에 보기
description: BoI Wiki가 지식, 업무 흐름, 실행 결과를 연결해 다음 업무에 재사용하는 전체 운영 모델
tags: [Manual, BoIWiki, BoIAgent, Workflow, WorkLearning, LivingKnowledge]
timestamp: 2026-07-12T10:45:00+09:00
boi_id: boi:public:boi-wiki-manual:overview
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
    ref: README.md
  - type: manual
    ref: boi:public:boi-wiki-manual:guide:final-operator-guide
review:
  reviewer: harness-curator
  review_status: reviewed
---

# BoI Wiki란

BoI Wiki는 문서 검색 서비스와 업무 실행 시스템을 분리하지 않는다. 접근 가능한 Wiki 전체에서 관련 지식과 과거 사례를 찾고, SOP와 Task를 수행하며, 판단 근거와 결과를 다음 업무에서 재사용할 수 있는 BoI 자산으로 남긴다.

정본은 OKF Markdown, JSONL, catalog와 Git이다. Postgres/pgvector, ontology graph와 검색 index는 정본에서 다시 만들 수 있는 조회 모델이다. 긴 원본 파일은 `자료 보관함`에 보존하고 Wiki에는 요약, 표본, checksum과 권한이 적용된 연결만 남긴다.

```mermaid
flowchart LR
  ASK["질문·업무·이벤트"] --> CONTEXT["업무 맥락 구성"]
  CONTEXT --> RECALL["지식·관계·사례 찾기"]
  RECALL --> WORK["사람·AI·Action 수행"]
  WORK --> VERIFY["근거와 완료 항목 검증"]
  VERIFY --> RESULT["결과 BoI"]
  RESULT --> LEARN["지식·SOP·Skill 개선 후보"]
  LEARN --> RECALL
```

# 주요 화면

| 화면 | 하는 일 |
|---|---|
| BoI Wiki | 문서, 업무 용어, 관계와 검토된 지식을 찾는다. |
| BoI Agent | 현재 화면을 출발점으로 Wiki 전체를 활용해 질문, 비교, 초안과 업무 수행을 이어간다. |
| BoI Inbox | 자동 생성된 검증 보고서와 업무 흐름을 보고 승인, 반려, 보류, 근거 보완을 기록한다. |
| SOP | Workflow와 Task, 완료된 모습, 확인할 자료, 실행 방식을 설계하고 수행 이력을 본다. |
| Event Broker | 업무가 발생하는 기준을 Event 카탈로그에서 보고, 하위 업무 발생 이력에서 실제 처리 건을 확인한다. |
| Action | 등록된 실행 요청, 입력, 위험도, dry-run과 실제 사용처를 확인한다. |
| 자료 보관함 | 긴 원본 파일을 보존하고 BoI, Task, 보고서의 근거로 연결한다. |
| Advanced | 권한, API·MCP contract와 외부 연결 상태를 진단한다. BoI Agent의 일상 사용 화면은 아니다. |

# 사람과 AI의 협업 방식

| 방식 | 역할 |
|---|---|
| Manual | 사람이 수행하고 판단한다. BoI Agent는 필요한 지식과 기록을 돕는다. |
| Copilot | 내부 또는 외부 AI가 자료와 초안을 준비하고 사람이 최종 확인한다. |
| Autopilot | 허용된 저위험 Action과 시스템에서 확인 가능한 완료 항목만 자동 처리한다. |

# 어디서 시작할까

- 처음 사용한다면 [BoI Wiki 종합 가이드](/docs/boi:public:boi-wiki-manual:guide:final-operator-guide)
- 질문과 검색부터 시작한다면 [BoI Agent 사용 가이드](/docs/boi:public:boi-wiki-manual:agent:using-boi-agent)
- 업무 수행과 판단을 처리한다면 [BoI Inbox와 Task 수행](/docs/boi:public:boi-wiki-manual:inbox:inbox-and-task-guide)
- SOP를 설계한다면 [Workflow/Task Builder 따라하기](/docs/boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step)
- 원본 자료를 업무 근거로 연결한다면 [자료 보관함과 업무 근거](/docs/boi:public:boi-wiki-manual:data-lake:data-lake-artifact-lifecycle)
- 외부 Agent를 연결한다면 [BoI Wiki MCP 등록과 사용](/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp)
- 실제 Event 처리 건을 확인한다면 [Event 카탈로그와 업무 발생 이력](/docs/boi:public:boi-wiki-manual:events:event-catalog-and-work-history)
- REST API로 연동한다면 [BoI Wiki API v2](/docs/boi:public:boi-wiki-manual:api:boi-wiki-api-v2)
