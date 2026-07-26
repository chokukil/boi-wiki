---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Langflow 처음 연결하기
description: Agent Playground에서 개인 Langflow 프로젝트와 BoI 지식 연결을 처음 준비하는 절차
tags: [Manual, AgentPlayground, Langflow, Onboarding]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-langflow-setup
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 준비 결과

처음 연결을 마치면 내 사번에 다음 항목이 연결된다.

- 개인 Langflow 사용자와 API Key
- `boi-{사번}` 프로젝트
- `BoI Wiki Agent Loop` 기준 Flow
- BoI가 자동 관리하는 Wiki·Ontology Credential
- Wiki를 바꾸지 않는 첫 preview 결과

# 연결 순서

1. `/playground`에서 현재 SSO 사용자와 권한을 확인한다.
2. `Langflow 설정에서 키 발급`을 누른다.
3. Langflow `Settings → API Keys`에서 `BoI Agent Playground` Key를 만든다.
4. 화면에 한 번 표시되는 Key를 복사한다.
5. Playground의 `방금 발급한 API Key`에 붙여 넣는다.
6. `연결 시험`으로 Langflow 1.11과 내 사용자 소유권을 확인한다.
7. `확인하고 저장`을 누른다.
8. `내 개발 공간 자동 준비`를 실행한다.
9. 기준 Flow preview가 성공하면 `Playground 시작`을 누른다.

API Key는 저장 후 다시 표시되지 않는다. Key 입력을 비워 둔 채 endpoint를 수정하면 기존 Key를 유지한다.

# 두 키의 차이

`Langflow 연결 키`는 Langflow 사용자·프로젝트·Flow를 관리한다. Playground와 Agent Hub가 서로 Key를 동기화하지 않으므로 각 화면에 한 번씩 직접 입력한다.

`BoI 지식 연결`은 Playground가 자동 발급하고 Langflow 표준 Credential Variable `BOI_WIKI_PAT`에 등록한다. 사용자는 PAT나 MCP 전용 Key를 따로 만들 필요가 없으며, 이 값은 화면이나 Flow export에 표시되지 않는다.

# 자동 준비가 중단된 경우

같은 endpoint에서 `내 개발 공간 자동 준비`를 다시 누른다. 이미 성공한 프로젝트·Credential·Flow는 재사용하고 실패한 단계부터 이어간다.

지원 버전 밖의 Langflow는 연결 정보를 보존하지만 자동 준비와 Action 등록을 차단한다.
