---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: SOP 담당자 Internal Alpha Preview 사용 안내
description: SOP 담당자가 BoI Wiki Web 화면에서 근거 확인부터 안전한 실행과 결과 재사용까지 따라 하는 사내 제한 시연 안내
tags: [Manual, SOP, InternalAlpha, Demo, BoIAgent, WorkLearning]
aliases: [SOP 담당자 데모 안내, SOP 사내 시연 참석자 가이드]
timestamp: 2026-07-21T00:00:00+09:00
boi_id: boi:public:boi-wiki-manual:agent:sop-owner-internal-alpha-guide
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:agent:using-boi-agent
  - type: boi
    ref: boi:public:boi-wiki-manual:agent:work-learning-system
  - type: boi
    ref: boi:public:sop:equipment-abnormal-response
  - type: boi
    ref: boi:public:event-types:equipment.alarm.raised.v1
implementation_refs:
  - type: repo
    ref: boi_api/app/templates/_agent_surface_v2.html
  - type: repo
    ref: boi_api/app/templates/task_console.html
  - type: repo
    ref: boi_api/app/static/agent_workspace_v2.js
relationships:
  - relation: guided_by
    target: boi:public:boi-wiki-manual:operations:sop-demo-facilitator-runbook
    label: 진행자용 Setup 및 실행 절차
review:
  reviewer: sop-demo-owner
  review_status: needs_validation
---

# 이 안내의 목적

이 안내는 SOP 담당자가 별도의 AI 개발 도구나 내부 구현 지식 없이 BoI Wiki Web 화면으로 하나의 업무를 처음부터 끝까지 시험하기 위한 것이다. 이번 자리는 **사내 제한 시연(Internal Alpha Preview)** 이며 정식 운영이나 전사 배포 준비 완료를 뜻하지 않는다.

BoI Agent는 일반 구성원이 사용하는 기본 Web Client다. Codex, Claude, 사내 Custom Agent, REST API와 MCP도 별도 업무 규칙을 만드는 것이 아니라 같은 BoI Wiki Harness의 의미, 권한, 실행 전 확인, 완료 판단과 근거 기록 규칙을 사용한다.

# 참석자가 준비할 것

- 진행자가 전달한 `<BOI_BASE_URL>`과 데모 시간
- 본인 사내 계정 또는 진행자가 발급한 시험 계정
- 샘플 업무만 사용한다는 동의
- 실제 실행 확인 버튼은 변경 내용을 읽은 뒤 직접 누른다는 원칙
- 오류가 나면 반복 클릭하지 않고 진행자에게 화면을 보여준다는 원칙

비밀번호, 개인 접근 토큰과 서비스 비밀값은 이 문서나 채팅에 붙여 넣지 않는다. 계정 권한이 맞지 않으면 진행자가 별도 시험 계정을 준비한다.

# 10~15분 표준 여정

이번 시연은 `설비 Alarm 발생` 샘플 Event와 `설비 이상 감지·원인 분석·이상 조치 SOP`를 사용한다. 실제 설비와 운영 데이터는 사용하지 않는다.

| 시간 | 참석자가 할 일 | 화면에서 확인할 것 |
|---|---|---|
| 0~2분 | 샘플 Event 또는 “설비 Alarm 대응 업무를 시작하려면 무엇을 확인해야 해?”라고 요청 | 현재 업무 맥락, 관련 Wiki 근거, 제한 상태 안내 |
| 2~4분 | 답변의 citation을 선택 | 문서 제목, 정확한 문단 또는 행, 원문 열기 |
| 4~6분 | “관련 사람·조직·Task·Agent/System 관계를 보여줘”라고 요청 | 관계 표, Mermaid 또는 Ontology Explorer와 각 관계의 근거 |
| 6~8분 | “이 근거로 SOP 초안을 만들어줘” 또는 연결된 기존 Task 열기 | private 초안 또는 Task, 완료 항목, 필요한 근거 |
| 8~10분 | 샘플 Action의 실행 전 확인 카드 열기 | 실행 내용, 입력, 바뀌는 상태, 승인 필요 여부 |
| 10~11분 | 진행자 확인 후 한 번만 실행 확인 | 사용자가 누르기 전에는 실제 변경이 없었는지 |
| 11~12분 | 진행자가 같은 요청을 같은 시험 식별값으로 한 번 더 보냄 | 실제 결과가 한 건만 생겼는지 |
| 12~13분 | WorkRun, Outcome과 Evidence Ledger 확인 | 진행 상태, 결과, 결과를 뒷받침한 근거 |
| 13~14분 | 검증된 결과에서 `나만의 지식으로 저장` 선택 | private 표시와 저장된 내용 |
| 14~15분 | 새 작업을 열고 저장한 지식을 묻기 | 새 WorkSession에서 재사용되고 다른 계정에는 보이지 않는지 |

“같은 실행 요청이 반복되어도 실제 결과는 한 번만 반영되도록 중복 실행을 막는 성질”을 기술 문서에서는 `멱등성`이라고 부르기도 한다. 참석자는 용어보다, 같은 요청을 다시 보냈을 때 Task·Action·Outcome 수가 늘어나지 않는지를 확인하면 된다.

# 화면을 여는 방법

## Pet과 Compact

BoI Wiki의 문서, SOP, Event, Action, Task 또는 Inbox 화면에서 오른쪽 아래 `BoI Agent` 캐릭터를 누른다. 작은 대화창인 Compact가 열리며 현재 화면의 업무 맥락이 함께 전달된다.

## Expanded

Compact 위쪽의 `↗` 버튼을 누른다. 관계 그림, 표, SOP 초안과 실행 전 확인을 읽기 쉬운 넓은 화면으로 전환한다. `Esc` 또는 `↙`로 Compact로 돌아갈 수 있다.

## Fullpage

위쪽의 `▣` `전체 화면에서 이어보기`를 누르면 `/agent` 전체 화면이 열린다. 같은 WorkSession을 이어가므로 대화, 사용한 지식과 작업 결과가 유지되어야 한다. `새 작업`을 누른 경우에만 새 WorkSession이 시작된다.

## Task Console

연결된 Task 카드의 `Task 열기`를 선택한다. 주소를 직접 확인할 때는 진행자가 준비한 `<BOI_BASE_URL>/tasks/console?task_id=<DEMO_TASK_REF>`를 사용한다. `task_id` 없이 Task Console만 열면 사용할 Task를 정할 수 없어 오류가 날 수 있다. Task 제목, 현재 단계, 완료 항목, 확인한 내용, 수행 조치, 판단·결과와 근거를 확인한다. Task Console에서 Pet을 열었을 때 해당 Task가 현재 맥락으로 표시되어야 한다.

# 근거와 관계 확인

## Citation 원문

답변 아래 citation 번호나 근거 제목을 누른다. `원문 근거` 화면에서 문서 제목, 문단 또는 행 범위, 인용 부분을 확인하고 필요하면 `원문 열기`를 누른다. citation이 열리지 않거나 답변과 원문이 다르면 그 답을 실행 근거로 사용하지 않는다.

## 사용한 지식

답변의 `사용한 지식 N개` 또는 모바일의 `사용한 지식` 탭을 연다. 실제 답변에 사용된 source만 표시되어야 한다. 단순 검색 후보와 접근 권한이 없는 문서는 여기에 섞이면 안 된다.

## Ontology 관계

관계 결과는 상황에 따라 다음 중 하나로 보인다.

- 표: 관계와 근거를 빠르게 비교한다.
- Mermaid: 업무 순서를 짧은 그림으로 본다.
- Ontology Explorer: 사람·조직·Task·Agent/System 연결을 선택하며 확장한다.

관계 항목을 선택하면 아래쪽 상세 정보와 citation을 확인한다. 한 번의 Task 배정이 공식 책임이나 전문성으로 표시되면 안 된다. 추론된 관계는 권한 부여, 자동 배정과 완료 판정에 사용하지 않는다.

# 실행 전 확인과 실행 결과

Action 실행 전 확인 카드에서 다음 네 항목을 소리 내어 확인한다.

1. 무엇을 실행하는가
2. 어떤 샘플 입력을 사용하는가
3. 어떤 정보나 상태가 바뀌는가
4. 추가 승인 또는 담당자 판단이 필요한가

카드가 없거나 위 항목을 확인할 수 없으면 실행하지 않는다. `실행 확인` 전후로 Task·Action·Outcome 건수를 비교한다. 확인 전에는 바뀐 것이 없어야 한다.

확인 후에는 WorkRun의 진행 상태가 `완료`, `추가 확인 필요`, `실패` 또는 `취소` 중 무엇인지 본다. Outcome에서는 실제 결과를, Evidence Ledger에서는 어떤 근거가 어떤 완료 항목을 뒷받침했는지 확인한다. 답변 문장만 있고 실제 결과나 근거가 없으면 완료로 보지 않는다.

# private 지식 저장과 재사용

결과와 근거를 검토한 뒤 `나만의 지식으로 저장`을 선택한다. 저장 후보에서 제목, 핵심 내용, source와 `private` 표시를 확인한다. 다음 순서로 재사용을 확인한다.

1. 현재 WorkSession ID 또는 제목을 기록한다.
2. `새 작업`을 눌러 새 WorkSession을 만든다.
3. “방금 검증해 저장한 설비 Alarm 대응 지식을 알려줘”라고 묻는다.
4. 저장한 내용과 source가 다시 사용되는지 확인한다.
5. 진행자가 권한 없는 별도 시험 계정으로 같은 질문을 한다.
6. 그 계정에는 private 내용과 citation이 보이지 않는지 확인한다.

private 지식이 다른 계정에 보이면 즉시 데모를 중지하고 화면과 시간을 기록한다.

# 기능이 준비되지 않았을 때의 대체 절차

정상 진행이 어려울 때 사용할 대체 절차는 다음과 같다.

| 상황 | 참석자에게 안내할 내용 | 이어갈 방법 |
|---|---|---|
| Web 또는 Agent가 열리지 않음 | 현재 연결이 준비되지 않았다 | 진행자가 준비한 동일 버전 화면 캡처로 UI 위치만 설명한다 |
| citation 원문이 열리지 않음 | 이 답을 근거로 실행하지 않는다 | 원본 Wiki 문서를 직접 열어 같은 문단을 확인한다 |
| 관계 그림이 보이지 않음 | 관계 데이터 또는 그림 표시가 제한 상태다 | 같은 citation으로 만든 관계 표를 사용한다 |
| Action 미리보기가 없음 | 실행 안전 조건을 확인할 수 없다 | 실제 실행을 생략하고 미리 준비한 확인 카드와 결과를 비교한다 |
| 실행이 지연됨 | 반복 클릭하면 안 된다 | WorkRun 상태만 새로 확인하고, 필요하면 취소 상태를 확인한다 |
| private 저장 또는 새 세션 재사용 실패 | 지식 재사용은 미검증이다 | 화면과 WorkSession을 기록하고 이번 시연의 제한으로 남긴다 |
| MCP 또는 외부 Agent 연결 실패 | Web 여정의 실패는 아니다 | Web 결과의 의미 필드와 준비된 REST/MCP 증거를 읽기 전용으로 비교한다 |

# 이번 시연에서 사용하지 않는 기능

- 운영 데이터와 실제 설비 제어
- 공정 Hold, Spec/Rule 변경 등 고위험 Action
- Team/Public 지식 게시 또는 승격
- DeepAgents worker에 성공이 의존하는 작업
- 장시간 Deep Work, 대규모 동시 실행과 자동 반복 업무
- 관리자용 raw JSON, 내부 추적 로그와 평가기 조정
- 준비되지 않은 connector를 즉석에서 연결하는 작업

# 현재 알려진 제한과 미검증 항목

- 이 문서 브랜치의 기준 commit에는 진행 중인 North Star 안정화 변경이 포함되지 않는다. Ontology query, Outcome 조회, 전역 BoI Agent 메뉴 등 일부 경로는 dirty 안정화 checkout과 그 로컬 runtime에서만 관측됐다. 데모에는 문서 브랜치 단독 build가 아니라 해당 기능이 정식으로 통합된 build를 사용해야 한다.
- 2026-07-21 로컬 감사에서는 API는 응답했지만 DB, 검색 색인과 worker가 모두 준비된 상태가 아니었다. 이 결과는 데모 환경의 최신 상태를 대신하지 않는다.
- Pet·Expanded·Fullpage·Task Console의 같은 업무 맥락 유지는 코드 경로가 확인됐지만 실제 브라우저 4면 연속 여정은 데모 환경에서 다시 확인해야 한다.
- Action 미리보기와 확인 화면은 등록돼 있으나 최근 관측된 화면 수가 0이었다. 데모 전에 샘플 Action으로 확인해야 한다.
- private 저장, 새 세션 재사용과 다른 사용자 비노출은 영속 DB가 준비된 환경에서 다시 확인해야 한다.
- REST와 MCP의 동일 의미 비교는 현재 문서·계약 수준이며 실제 연결 상태를 데모 전에 확인해야 한다.

# 피드백 양식

시연이 끝나면 다음 항목을 짧게 남긴다.

- 참여자 역할:
- 가장 이해하기 쉬웠던 단계:
- 막히거나 설명이 더 필요했던 화면:
- citation과 사용한 지식을 신뢰할 수 있었는가: 예 / 아니오 / 판단 어려움
- 실행 전 무엇이 바뀌는지 이해할 수 있었는가: 예 / 아니오 / 판단 어려움
- 실행 결과와 Evidence를 찾을 수 있었는가: 예 / 아니오
- private 저장과 새 작업 재사용 결과:
- 실제 SOP 업무에 적용하고 싶은 첫 사례:
- 사용하지 말아야 한다고 느낀 기능 또는 위험:
- 오류 시각, 화면, WorkSession 제목:
- 추가 의견:

# 더 읽기

- [BoI Agent 사용 가이드](/docs/boi:public:boi-wiki-manual:agent:using-boi-agent)
- [Work Learning System](/docs/boi:public:boi-wiki-manual:agent:work-learning-system)
- [SOP 데모 진행자 Setup 및 Runbook](/docs/boi:public:boi-wiki-manual:operations:sop-demo-facilitator-runbook)
