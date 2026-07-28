---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground 시작 가이드
description: Langflow 연결 키 발급부터 Agent Hub 배포와 BoI Action 연결까지 처음 한 번 준비하는 방법
tags: [Manual, AgentPlayground, Langflow, AgentHub, Action]
timestamp: 2026-07-26T07:30:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
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
    ref: boi_api/app/templates/agent_playground.html
  - type: repo
    ref: langflow/compatibility-manifest.json
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 3분 빠른 시작

Agent Playground는 내 사번의 Langflow 프로젝트에서 Flow를 만들고 시험하는 개인 개발 공간이다. 검증을 마친 Flow는 기존 Agent Hub UI에서 배포하고, Playground가 배포 결과를 다시 찾아 BoI Action으로 연결한다.

로컬 시연에서는 운영 사내 계정과 별개로 `boi-dev` 공용 로그인을 준비할 수
있다. 이 계정은 새 사번이나 별도 프로젝트가 아니라 검증용 `100002` 개발자
공간의 OIDC 별칭이다. 준비와 복구는
`validation/agent-playground-mainline/prepare_demo_account.py`와
`restore_demo_account.py`로만 수행하며 사내·운영 환경에는 배포하지 않는다.

1. `/playground`를 열어 현재 SSO 사용자를 확인한다.
2. `Langflow 설정에서 키 발급`으로 개인 API Key를 만든다.
3. Playground에서 연결을 시험하고 `내 개발 공간 자동 준비`를 실행한다.
4. `Langflow 프로젝트 열기`에서 Agent를 편집한다.
5. `Playground 테스트`에서 업무 맥락, Ontology 관계, Wiki 근거와 저장 결과를 확인한다.
6. `Agent Hub`에서 내 Flow를 배포하거나 승인된 공유 자산을 가져온다.
7. 배포 Flow를 다시 찾아 검증한 뒤 `Action 연결`을 진행한다.

Langflow와 Agent Hub는 BoI가 수정하지 않는다. Playground는 공개 API와 기존 UI만 사용한다.

Playground는 복잡한 Flow를 자체 순서도로 다시 그리지 않는다. Flow 목록의 `원본 열기`나
선택 화면의 `Langflow에서 원본 Flow 열기`로 분기·병합·루프를 포함한 실제 Canvas를
확인한다.

# DEV와 PRD를 구분한다

| 배지 | 의미 |
|---|---|
| `DEV · Playground` | 개인 Langflow 프로젝트에서 개발·시험하는 Flow |
| `PRD · Agent Hub` | Agent Hub 배포 결과를 live exact Flow로 다시 찾아 연결한 Flow |

PRD는 배포 경로를 뜻한다. `Runtime 확인`, `Action 연결`, `변경되어 재검증 필요` 같은
검증 상태는 별도다. PRD 배지가 있어도 검증이 끝나지 않았을 수 있다.

Action 연결을 마치면 Action 카탈로그에서 연결된 exact Flow를 확인할 수 있다. Flow
소유자는 Playground 또는 원본 Langflow Canvas로 이동할 수 있다. 공유 Action 사용자는
다른 사용자의 개인 개발 공간으로 이동하지 않는다.

# 어떤 경로로 시작할까

## 내 Flow를 배포한다

내 프로젝트에서 만든 Flow를 충분히 시험한 뒤 Agent Hub에 올린다.

[내 Flow를 Agent Hub에 배포하기](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-my-flow-deploy)

## 공유 Flow·Component를 활용한다

다른 직원이 만든 승인 Flow나 Component를 내 프로젝트에 배포하고 실제 실행 경로에 연결한다.

[Agent Hub 공유 자산 활용하기](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-shared-assets)

# 처음 연결하는 경우

두 키의 역할이 다르다.

| 구분 | 준비 방법 | 사용 위치 |
|---|---|---|
| Langflow 연결 키 | Langflow 표준 설정에서 사용자가 발급 | Playground와 Agent Hub에 각각 한 번 입력 |
| BoI 지식 연결 | Playground가 자동 준비 | Langflow 안에서 Wiki·Ontology 조회와 개인 초안 저장 |

[Langflow 처음 연결하기](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-langflow-setup)

# Action과 Wiki에서 사용하기

Action은 Langflow 전용 기능이 아니다. 업무 목적과 입력·출력·근거·승인 정책은 공통 Action 계약으로 유지하고, 이 Flow를 실행하는 연결만 Langflow binding으로 둔다.

지식 조회는 업무 Context와 Ontology를 우선 사용한다. 관계 근거가 없을 때만 권한 내 Wiki 문서로 보완한다. 저장 기본값은 미리보기이며, 사용자가 직접 선택한 경우에만 내 개인 초안을 만든다.

[Action으로 연결하고 Wiki에서 실행하기](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-action-wiki)

# 문제가 생겼다면

[Agent Playground 문제 해결](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-troubleshooting)

API Key, `BOI_WIKI_PAT`, 실행 token과 모델 Key는 문서·화면·스크린샷에 남기지 않는다.
