---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 업무 관계와 동적 결과 활용 가이드
description: 사람·팀·Task·SOP·Event·Action의 검증된 관계를 질문하고 결과에 맞는 표, Timeline, Mermaid와 관계 탐색 화면을 사용하는 방법
tags: [BoIWiki, BoIAgent, Ontology, WorkRelation, DynamicResult, Evidence]
timestamp: 2026-07-14T23:20:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:work-relations-and-dynamic-results
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
agent_entrypoint_areas: [current_work, knowledge]
agent_entrypoint_prompts:
  current_work:
    label: 내 역할과 지금 맡은 일을 한눈에 보기
    prompt: 내 공식 역할과 검증된 업무 관계를 현재 Inbox 업무와 구분해 표로 보여줘.
  knowledge:
    label: 현재 지식과 직접 연결된 항목을 관계로 보기
    prompt: 현재 화면을 출발점으로 직접 확인되는 관계만 탐색할 수 있게 보여줘.
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:agent:using-boi-agent
relationships:
  - relation: part_of
    target: boi:public:boi-wiki-manual:guide:final-operator-guide
    label: 종합 가이드의 관계 탐색 여정
  - relation: guides
    target: boi:public:boi-wiki-manual:workflows:task-execution-ontology-guide
    label: Task 배정과 수행 관계 활용
  - relation: uses
    target: boi:public:boi-wiki-manual:agent:using-boi-agent
    label: BoI Agent의 동적 결과 화면
  - type: boi
    ref: boi:public:boi-wiki-manual:workflows:task-execution-ontology-guide
  - type: boi
    ref: boi:public:boi-wiki-manual:knowledge:living-knowledge-system
implementation_refs:
  - type: repo
    ref: boi_api/app/v2/knowledge_system.py
  - type: repo
    ref: boi_api/app/v2/a2ui.py
  - type: repo
    ref: boi_api/app/static/agent_workspace_v2.js
review:
  reviewer: harness-curator
  review_status: needs_revision
---

# 무엇을 구분해서 보나

업무 관계 질문은 문서 검색 결과와 Inbox 목록을 한데 섞지 않는다.

| 보고 싶은 것 | 사용하는 근거 | 예시 |
|---|---|---|
| 현재 업무 | 현재 배정과 Inbox 상태 | 지금 처리할 업무만 보여줘 |
| 공식 역할 | directory의 역할·팀 선언 | 내가 맡은 역할은 무엇인가 |
| 수행 관계 | WorkRecord와 검증된 완료 기록 | 최근 어떤 Task를 수행했나 |
| 영향 관계 | SOP·Event·Action·BoI 연결 | 이 Event 이후 어디가 영향을 받나 |

“내가 하는 일이 뭐지?”처럼 넓은 질문은 공식 역할·검증된 관계와 현재 Inbox를 두 영역으로 나누어 보여준다.

# 관계가 만들어지는 방식

```mermaid
flowchart LR
  DIR["사람·팀·역할"] --> GRAPH["업무 관계"]
  ASSIGN["Task 배정·재배정"] --> GRAPH
  WORK["WorkRecord"] --> GRAPH
  COMPLETE["검증된 완료 기록"] --> GRAPH
  ASSET["SOP·Event·Action·근거·결과 BoI"] --> GRAPH
  GRAPH --> CONTEXT["다음 질문과 Task Context"]
```

관계마다 정본에 명시됐는지, 구조에서 추출됐는지, 사람이 검증했는지와 근거 revision을 함께 저장한다. AI가 추론한 관계는 검토 전에는 권한, 자동 배정, 완료 판단에 쓰지 않는다.

`반복 수행`은 단순 배정 횟수가 아니다. 최근 180일 안에 서로 다른 업무 실행에서 검증 완료가 세 번 이상 확인될 때만 `WorkRoleProfile`로 계산한다. 오래된 완료, 같은 실행의 중복 기록과 한 번의 배정은 반복 수행에 포함하지 않는다.

# 결과 화면은 질문에 따라 달라진다

- 항목이 적고 비교가 중요하면 **관계표**를 사용한다.
- 배정·처리·완료가 시간에 따라 바뀌면 **시간 흐름**을 사용한다.
- 짧은 업무 순서나 연결 경로는 **흐름 그림**으로 보여준다.
- 관계가 많고 직접 이동하며 보고 싶으면 **관계 탐색**을 연다.
- 판단·조치·근거를 남겨야 하면 **업무 기록 입력**을 연다.
- 외부 부작용이 있는 Action은 **실행 전 확인**을 거친다.

관계 탐색은 처음에 한 단계 이웃만 연다. 항목을 선택할 때 필요한 주변 관계만 추가하므로 큰 Wiki 전체를 한 번에 브라우저로 보내지 않는다. 25개 이하에서는 중심 항목을 기준으로 여러 원에 배치해 모든 이름을 읽을 수 있게 하고, 그보다 큰 관계는 ForceAtlas2와 겹침 방지 배치를 사용한다. 중심·선택·직접 이웃의 이름은 항상 표시하고 선택 경로 밖의 관계는 흐리게 구분한다.

그래프는 결과 폭을 모두 사용하고, 선택 항목의 설명과 근거는 오른쪽 고정 열이 아니라 아래쪽 정보 영역에 연다. 정보 영역을 닫으면 그래프가 전체 높이를 다시 사용한다. 방향 화살표, 항목 종류 범례, 관계 필터와 검색 자동완성을 이용해 단순한 점 무리가 아니라 실제 업무 관계를 따라간다.

동적 결과는 저장만 하는 JSON이 아니다. BoI Agent가 검증된 surface를 다시 읽어 관계표, 시간 흐름, 흐름 그림 또는 관계 탐색 DOM을 만든다. Task 수행 화면도 같은 계약의 `업무 기록 입력`과 `근거 선택`을 사용한다. surface가 손상됐거나 client가 지원하지 않으면 같은 의미의 기존 typed 화면으로 복구한다.

![공식 역할과 검증된 수행 관계를 표로 구분한 BoI Agent 화면](../_media/browser/current-guide/20260713-boi-agent-role-table-1440x1000.png)

관계를 더 넓게 살펴볼 때만 탐색 화면을 연다. 처음부터 전체 Wiki를 그리지 않고 현재 대상을 중심으로 한 단계씩 확장한다.

![검증된 업무 관계를 한 단계씩 확장하는 관계 탐색 화면](../_media/browser/current-guide/20260713-ontology-explorer-1440x1000.png)

모바일에서는 대화와 결과를 탭으로 나누고, 같은 관계와 근거를 유지한다.

![모바일에서 역할 관계표를 확인하는 BoI Agent 화면](../_media/browser/current-guide/20260713-boi-agent-role-table-390x844.png)

![모바일에서 필요한 관계만 확장하는 관계 탐색 화면](../_media/browser/current-guide/20260713-ontology-explorer-390x844.png)

# 근거를 확인하는 방법

일반 사용자는 이동 가능한 BoI, Task, Event, Action과 자료 근거만 본다. 권한이 없으면 명시적으로 제한 상태를 표시한다. 코드 파일은 업무 근거가 아니며 관리자에게만 접힌 `기술 검증 근거`와 읽기 전용 화면으로 제공한다.

관계 결과의 citation은 실제 문서·업무 화면으로 이동한다. 같은 source·relation·target이 여러 추출기에서 발견돼도 화면에서는 provenance가 더 강한 하나의 관계로 합쳐 보여준다. 관계 근거가 없어 빈 탐색 화면이 될 추천은 만들지 않고, 검토된 문서 답변으로 안전하게 전환하거나 추천 자체를 생략한다.

표시된 관계가 한 번의 배정인지, 공식 역할인지, 반복 수행인지 확인한다. 한 번의 배정은 전문성의 증거가 아니다.

# 안전한 사용

- 현재 화면은 관계 탐색의 출발점이며 Wiki 전체 검색을 제한하지 않는다.
- 동명이인이나 동일한 이름의 자산이 둘 이상일 때만 대상을 한 번 확인한다.
- 화면 표현이 실패하면 같은 의미의 기존 답변·표·입력 화면으로 복구한다.
- 동적 결과 화면에서 Action, 배정, 완료를 직접 우회 실행하지 않는다.
- 공유 지식 변경은 preview, Harness와 검토를 거친다.

# 함께 보기

- [BoI Agent 사용 가이드](/docs/boi:public:boi-wiki-manual:agent:using-boi-agent)
- [Task 수행과 업무 관계 활용 가이드](/docs/boi:public:boi-wiki-manual:workflows:task-execution-ontology-guide)
- [Living Knowledge System](/docs/boi:public:boi-wiki-manual:knowledge:living-knowledge-system)
- [Task·Ontology·동적 화면 검증 기준](/docs/boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance)
