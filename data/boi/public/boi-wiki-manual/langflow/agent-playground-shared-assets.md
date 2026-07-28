---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Hub 공유 자산 활용하기
description: 다른 작성자의 승인 Flow와 Component를 개인 프로젝트에서 조합하고 검증하는 절차
tags: [Manual, AgentPlayground, AgentHub, Component]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-shared-assets
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

# 공유 Flow를 사용한다

1. `Agent Hub → 공유 자산 가져오기`를 연다.
2. 승인 자산을 이름·태그로 찾는다.
3. 작성자, 버전, 용도와 지원 Langflow 버전을 확인한다.
4. `이 자산 사용`을 선택하고 `배포 준비`를 누른다.
5. 기존 Agent Hub UI에서 내 endpoint와 `boi-{사번}` 프로젝트로 배포한다.
6. Playground로 돌아와 `배포 결과 확인`을 누른다.
7. 배포된 정확한 Flow를 선택하고 전체 검증을 수행한다.

배포 결과로 연결된 Flow에는 `PRD · Agent Hub` 배지가 붙는다. `Langflow에서 원본 Flow
열기`는 내 endpoint에 배포된 실행 Canvas를 열고, `Agent Hub에서 배포 자산 보기`는
공유 자산의 작성자·버전·설명을 연다. 두 링크는 같은 대상을 뜻하지 않는다.

# Component 상태를 구분한다

| 상태 | 의미 |
|---|---|
| 배포됨 | endpoint에는 있지만 Flow 실행 경로는 확인 전 |
| 연결 필요 | Flow graph에 있으나 Agent 경로와 연결되지 않음 |
| 연결됨 | `boi.agent-slot.v1` 계약으로 실행 경로에 연결됨 |
| 실행 검증됨 | 실제 runtime provenance에 Component ID가 남음 |

Component가 Flow에 보인다는 이유만으로 완료 처리하지 않는다.

# 자동 연결과 수동 연결

입력 `agent_context`, 출력 `agent_result`의 단일 포트가 명확한 `boi.agent-slot.v1` Component만 `Agent 자리에 연결`할 수 있다.

포트가 여러 개거나 타입이 불명확하면 자동 연결하지 않는다. 선택한 Flow의 `원본 열기`로
Langflow Canvas를 열어 직접 연결한 뒤 Playground 검증을 다시 실행한다.

연결 후에도 다음 항목이 보존되어야 한다.

- 업무 Task·SOP Context
- Ontology 관계와 provenance
- Wiki source references
- Agent 결과의 저장 입력
- 실제 Component 실행 provenance
