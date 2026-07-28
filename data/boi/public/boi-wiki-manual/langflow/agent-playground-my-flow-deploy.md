---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 내 Flow를 Agent Hub에 배포하기
description: Playground에서 검증한 Flow를 수정 없는 Agent Hub UI로 배포하고 다시 찾는 절차
tags: [Manual, AgentPlayground, AgentHub, Deployment]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-my-flow-deploy
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
    ref: validation/agent-hub/README.md
  - type: boi
    ref: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 배포 전에 확인한다

- 내 프로젝트에서 Flow가 정상 실행된다.
- 미리보기 결과에 업무 맥락, Ontology 관계와 Wiki 근거가 있다.
- Flow 자산에 API Key, PAT, 실행 token과 모델 Key가 없다.

# 처음 Agent Hub를 연결한다

1. Playground의 `Agent Hub` 단계에서 `내 Flow 배포하기`를 선택한다.
2. 안내된 endpoint 별칭과 host-root URL을 확인한다.
3. `Agent Hub에서 배포`를 눌러 기존 Agent Hub UI를 연다.
4. Agent Hub에서 endpoint를 등록한다.
5. Langflow에서 발급한 개인 연결 Key를 직접 입력한다.
6. `연결 시험`이 성공하는지 확인한다.
7. `boi-{사번}` 프로젝트를 선택한다.

BoI와 Agent Hub는 저장된 Key를 서로 읽지 않는다. Agent Hub 소스·API·DB 구조를 BoI 용도로 변경하지 않는다.

# 내 Flow를 배포한다

1. Playground에서 배포할 Flow를 선택한다.
   - 이 단계의 Flow는 `DEV · Playground`로 표시된다.
   - `원본 열기`로 실제 Langflow Canvas를 확인할 수 있다.
2. `배포 자산 내려받기`로 secret-free 자산을 준비한다.
3. Agent Hub의 기존 업로드·배포 화면에서 자산을 배포한다.
4. Playground로 돌아와 `배포 결과 확인`을 누른다.
5. 새 Flow가 하나면 자동 선택된다. 여러 개면 내가 배포한 Flow를 선택한다.
6. `이 Flow를 배포 결과로 연결`한다.
7. 업무 Task를 선택하고 `Flow 전체 검증`을 실행한다.

Flow 이름이 같아도 Flow ID와 checksum이 다르면 별도 배포 버전이다. 화면에서는 이 값을 숨기지만 Action 연결 전 서버가 정확히 대조한다.

배포 결과 연결이 끝나면 Flow는 `PRD · Agent Hub`로 표시된다. 이 배지는 Agent Hub를
거쳐 배포됐다는 뜻이며 검증 완료를 뜻하지 않는다. 실제 실행 graph는 `Langflow에서
원본 Flow 열기`에서 확인하고, 승인 자산의 설명·작성자·버전은 `Agent Hub에서 배포
자산 보기`에서 확인한다.

# 배포 후 Flow를 수정했다면

Langflow Canvas에서 graph를 바꾸면 live checksum이 달라진다. 해당 Flow와 Action은 재검증 전까지 차단된다.
