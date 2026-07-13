---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Event 카탈로그와 업무 발생 이력
description: 업무 이벤트의 정의와 실제 발생 건, 연결된 Workflow·Action·결과 BoI, 기술 로그의 차이를 설명하는 사용자 가이드
tags: [Manual, Event, EventCatalog, Workflow, Action, WorkHistory]
timestamp: 2026-07-12T20:30:00+09:00
boi_id: boi:public:boi-wiki-manual:events:event-catalog-and-work-history
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
agent_entrypoint_areas: [event_action]
agent_entrypoint_prompts:
  event_action:
    label: 어떤 업무가 발생했고 어디까지 처리됐는지 보기
    prompt: Event 카탈로그와 업무 발생 이력의 차이, 한 업무 건에서 SOP와 Action과 결과 BoI를 확인하는 방법을 알려줘.
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:workflows:business-event-definition-guide
  - type: boi
    ref: boi:public:boi-wiki-manual:use-cases:event-to-action-workflow-planning
  - type: boi
    ref: boi:public:boi-wiki-manual:actions:multi-action-connector-guide
implementation_refs:
  - type: repo
    ref: boi_api/app/templates/event_occurrences.html
  - type: repo
    ref: boi_api/app/main.py
review:
  reviewer: workflow-owner
  review_status: reviewed
---

# 정의와 실제 업무 건을 구분하기

`Event 카탈로그`는 어떤 순간을 업무가 발생한 것으로 부를지 정리한 목록이다. `업무 발생 이력`은 그 정의에 맞는 Event가 실제로 들어와 Workflow와 Action이 실행된 업무 건을 보여준다. Kafka payload와 dispatch 정보는 운영 진단용 기술 로그다.

```mermaid
flowchart LR
  SIGNAL["외부 신호"] --> DETECT["업무 이벤트 판단"]
  DETECT --> EVENT["업무 Event 발생"]
  EVENT --> FLOW["Workflow · Task"]
  FLOW --> ACTION["Action · 사람 조치"]
  ACTION --> RESULT["결과 BoI"]
```

# Event 카탈로그

상단 `Event Broker`를 누르면 Event 카탈로그가 열린다. 각 Event Type에서 다음을 확인한다.

![업무 이벤트 정의와 연결 자산을 찾는 Event 카탈로그](../_media/browser/current-guide/20260713-event-catalog-1440x1000.png)

- 사람이 이해할 수 있는 업무 이름과 발생 의미
- 어떤 BoI와 Workflow에서 사용하는지
- 실제 발생 이력과 연결 Action
- 소유자와 현재 사용 상태

`상세`는 주 작업 버튼이고, 실제 연결이 있을 때만 관련 BoI·업무 발생 이력·Action 버튼이 나타난다.

# 업무 발생 이력

업무 발생 이력은 같은 trace에 속한 Event, SOP, Action, 수동 확인과 결과 BoI를 하나의 `BusinessEventOccurrence`로 묶는다.

![동일 trace의 Event와 실행 결과를 업무 건으로 묶은 업무 발생 이력](../_media/browser/current-guide/20260713-event-occurrences-1440x1000.png)

```mermaid
flowchart LR
  E["Event · 발생 시각"] --> S["연결 SOP · 진행 상태"]
  S --> A["실행 Action"]
  A --> H["남은 사람 확인"]
  H --> B["결과 BoI"]
```

기본 화면에서는 업무 제목, 진행 상태, 연결 SOP, 실행 Action 수, 남은 확인과 결과만 본다. trace ID, producer, connector, dispatch와 raw JSON은 일반 업무 판단에 필요하지 않으므로 `연결 정보` 또는 권한 있는 Advanced의 `Event 기술 로그`에서 확인한다.

# 상태 해석

| 상태 | 의미 |
|---|---|
| 진행 중 | Workflow나 Action이 처리 중이다 |
| 확인 필요 | 담당자의 판단 또는 근거 보완이 남았다 |
| 완료 | 완료 조건과 필요한 확인이 충족됐다 |
| 실패 | 실행이 중단됐으며 원인과 재시도 여부를 확인해야 한다 |

# 반복 발생 분석

반복 여부는 로그 한 줄마다 표시하지 않는다. 기간과 Event 종류를 먼저 필터링한 뒤 `반복 발생 분석`으로 같은 대상·원인의 반복과 업무 이벤트 정의 개선 후보를 검토한다. 반복됐다는 이유만으로 새 SOP나 Event를 자동 생성하지 않는다.

# 관련 문서

- [업무 이벤트 정의 가이드](/docs/boi:public:boi-wiki-manual:workflows:business-event-definition-guide)
- [SOP 작성과 연결](/docs/boi:public:boi-wiki-manual:sop-workflows:create-and-connect-sop)
- [BoI Wiki 종합 가이드](/docs/boi:public:boi-wiki-manual:guide:final-operator-guide)
