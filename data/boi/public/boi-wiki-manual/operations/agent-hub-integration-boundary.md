---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Hub 연동 경계와 운영 책임
description: Agent Hub를 수정하지 않고 Agent Playground와 연계하는 허용 계약과 책임 분리
tags: [Manual, Operations, AgentHub, AgentPlayground]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary
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
  - type: repo
    ref: scripts/check_agent_playground_mainline_boundary.py
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 고정 원칙

Agent Hub는 BoI 개발 영역이 아니다. 지정된 Agent Hub 버전을 외부 배포 Control Plane으로 사용하며 소스, UI, API route와 DB schema를 수정하지 않는다.

# 허용하는 연동

- 기존 Agent Hub UI에서 endpoint·API Key 등록과 연결 시험
- 기존 프로젝트 선택·자산 업로드·배포
- 기존 승인 자산 목록과 상세 API의 읽기 전용 조회
- Agent Hub 배포 후 Langflow 공개 API에서 exact Flow 재발견
- 격리 Agent Hub DB에 E2E용 runtime record 생성

# 금지하는 연동

- Agent Hub frontend·backend 패치
- Agent Hub migration·schema 변경
- BoI의 Agent Hub DB 직접 접근
- Agent Hub 저장 API Key 동기화
- BoI backend의 Agent Hub POST·PATCH·PUT·DELETE 요청
- 대표 Flow·대표 모달 제어 API 추가
- Agent Hub patch나 commit을 BoI handoff에 포함

# 책임 분리

| 영역 | 책임 |
|---|---|
| Agent Hub | 승인 자산 catalog, endpoint 연결 UI, 프로젝트 선택, 배포 |
| Agent Playground | secret-free 자산 준비, 배포 안내, exact Flow 재발견·검증 |
| Langflow | 개인 Flow runtime과 공개 `/api/v1` |
| BoI Action | connector-neutral 업무 계약, 승인, 실행 연결 |
| BoI Wiki·Ontology | Action 호출자의 Context·ACL·근거·개인 초안 |

Agent Hub는 Action runtime 경로에 들어가지 않는다.

로컬 검증에서는 Agent Hub backend network namespace의 loopback forwarder가
`http://localhost:7867`을 공식 Langflow 1.11 container로 전달한다. 사용자가 Agent Hub
UI에 입력하고 배포 결과로 받는 주소도 localhost를 유지한다. 이 구성은 BoI 검증
wrapper에만 있으며 Agent Hub 소스·DB schema·API를 변경하지 않는다.

# 버전과 변경 대응

검증 checkout은 SHA `7ca556b7885f316eedd757a7190b748bb7e0f7e5`와 clean diff를 확인한다. Agent Hub 계약이 바뀌면 Agent Hub를 패치하지 않고 BoI adapter와 문서를 새 계약에 맞춰 회귀 검증한다.

대표 Flow 선정과 대표 모달 노출은 Agent Hub 담당자에게 검증 증거를 전달한 뒤 구두로 요청한다.
