---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Action으로 연결하고 Wiki에서 실행하기
description: 검증된 Flow를 공통 Action 계약으로 등록하고 일반 Wiki와 SOP Task에서 실행하는 방법
tags: [Manual, AgentPlayground, Action, Ontology, SOP]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki
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
    ref: docs/CONNECTOR_AGNOSTIC_ARCHITECTURE_V0_4.md
  - type: boi
    ref: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Flow를 검증한다

`Playground 테스트`에서 실제 내 Task 또는 일반 Wiki 질문을 선택한다. 결과는 다음 순서로 확인한다.

1. 업무 맥락
2. Ontology 관계와 provenance
3. Wiki 문서 근거
4. 부족한 근거
5. 미리보기 또는 내 초안 저장 결과

SOP Task는 Task, Workflow, Stage, Event, Action, 선행 결과와 필요한 근거를 서버가 해석한다. SOP가 없는 Task에는 존재하지 않는 SOP 정보를 만들지 않는다.

# Action으로 연결한다

1. `action_ready` Flow에서 `Action 연결`을 연다.
2. `나만 사용` 또는 내가 속한 HCP 팀의 `팀에서 사용`을 선택한다.
3. `Action 등록 초안 만들기`를 누른다.
4. 등록 화면에서 업무 목적, 입력·출력, 근거와 승인 정책을 확인한다.
5. validate를 실행하고 명시적으로 publish-request를 요청한다.

Action 계약은 API, MCP, Webhook, Manual, Event Broker, BoI Writer와 Langflow에 공통이다. 이 Flow를 실행하는 `connector_binding`만 Langflow다.

# Wiki에서 실행한다

- 일반 Wiki에서는 질문과 현재 문서를 Context로 사용한다.
- SOP Task에서는 선택한 Task anchor와 실제 Workflow Context를 사용한다.
- Langflow 호출은 endpoint 소유자의 서버 저장 Key를 사용한다.
- Wiki 읽기와 개인 초안은 Action을 누른 사용자의 권한을 사용한다.

저장 기본값은 `미리보기`다. `내 Wiki 개인 초안`을 직접 선택한 경우에만 호출자 개인 공간에 초안을 만든다.
