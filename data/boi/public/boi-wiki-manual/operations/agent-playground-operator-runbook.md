---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground 운영 가이드
description: Langflow 비수정 원칙, SSO 권한, bundle 배포, Agent Hub와 Action 검증 및 rollback 기준
tags: [Manual, Operations, AgentPlayground, Langflow, SSO]
timestamp: 2026-07-26T07:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:agent-playground-operator-runbook
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
    ref: langflow/compatibility-manifest.json
  - type: repo
    ref: docker-compose.langflow-1.11-validation.yml
  - type: repo
    ref: validation/agent-hub/README.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 운영 경계

Langflow와 Agent Hub는 외부 제품이며 BoI 배포를 위해 소스, UI, API route, 내부 DB를 수정하지 않는다.

허용하는 연결 방식은 다음뿐이다.

- Langflow 공개 `/api/v1` API
- `/api/v1/run/{flow_id}`
- Flow JSON import/export
- `LANGFLOW_COMPONENTS_PATH`
- read-only custom component mount
- Langflow Credential/Global Variable

BoI 문제가 생기면 BoI adapter나 component bundle을 수정한다. Langflow package를 monkey patch하거나 `site-packages`를 덮어쓰지 않는다.

# 지원 버전과 이미지

정본은 `langflow/compatibility-manifest.json`이다.

- 지원 범위: `>=1.11.0,<1.12.0`
- 검증 이미지: manifest의 exact digest
- bundle: `1.1.0`
- mount: `/app/custom_components:ro`

업데이트 절차:

1. 새 공식 digest로 격리 stack을 만든다.
2. `python scripts/check_agent_playground_langflow_boundary.py`를 실행한다.
3. health, version, whoami, project, variable, Flow import, build, `/api/v1/run`을 회귀한다.
4. canonical Flow와 model Agent Flow를 각각 검증한다.
5. 1.10 export import와 DB clone migration을 공식 migration으로 실행한다.
6. 실패 시 이전 image, DB backup, `LANGFLOW_SECRET_KEY`를 한 세트로 복원한다.

BoI 서비스가 Langflow DB에 직접 접속하는 구성은 허용하지 않는다.

# SSO와 권한

- 표준 사번 claim은 `empno`다.
- SSO Principal과 HCP 권한이 소유권과 실행 권한의 기준이다.
- query, form, header의 employee ID는 SSO 소유권 판단에 사용하지 않는다.
- `100002` 계약은 조회, 편집, Flow 실행, Action 실행이다.
- `100003` 계약은 조회 전용이다.
- Langflow 사용자는 사번별 native 사용자와 개인 API Key를 사용한다.
- 여러 사번을 하나의 공유 Langflow 사용자에 연결하면 readiness를 실패시킨다.

# URL 계약

| 용도 | 환경변수 | 예 |
|---|---|---|
| 사용자가 여는 화면 | `LANGFLOW_EXTERNAL_URL` | `http://wiki.skhynix.com/builder` |
| Agent Hub와 BoI API 호출 | `LANGFLOW_DEPLOY_URL` | host root에서 `/api/v1`이 열리는 주소 |

Agent Hub PR #25는 입력 URL의 path를 제거하므로 `/builder`가 포함된 브라우저 주소를 endpoint로 등록하지 않는다.

SSO도 브라우저 공개 URL과 컨테이너 내부 URL을 분리한다.

| 용도 | 로컬 검증값 |
|---|---|
| Playground | `http://localhost:28005/playground` |
| Agent Hub | `http://localhost:18080` |
| Agent Hub에 등록할 검증 Langflow | `http://localhost:7867` |
| Keycloak browser·issuer | `http://localhost:18082` |
| 컨테이너 내부 Keycloak | 서버 전용 주소 |

브라우저 redirect, discovery issuer와 HTML에는 `host.docker.internal`을 노출하지 않는다. 이 값은 컨테이너가 host 서비스를 호출하는 내부 연결에만 사용할 수 있다.

로컬 검증 compose는 BoI API와 Agent Hub backend의 network namespace에 read-only
runtime용 loopback forwarder를 둔다. 따라서 두 UI 모두 `http://localhost:7867`을
사용하면서 공식 Langflow container를 호출한다. 이 forwarder는 검증 wrapper일 뿐
Agent Hub나 Langflow 소스 변경이 아니다.

# Secret 관리

- Langflow API Key는 BoI 전용 암호화 키로 암호화한다.
- 응답에는 `has_api_key`와 fingerprint만 제공한다.
- BoI PAT는 BoI 저장소에 hash만 남기고 Langflow Credential에는 원문을 한 번 등록한다.
- Action run token은 caller, Action, deployment, endpoint, project, exact Flow,
  trace, execution ID, capability, scope, TTL에 묶고 실행 종료 후 폐기한다.
- PAT 인증과 Action 실행 시작 때 HCP를 강제로 다시 조회한다. HCP 장애는 503,
  비활성화·권한 축소는 403으로 fail-closed한다.
- Flow, manifest, README, Wiki 초안, 일반 로그와 스크린샷을 secret scan한다.

# Agent Hub와 Action 검증

Agent Hub checkout은 지정 SHA를 유지하고 diff가 없어야 한다.

상세 허용·금지 계약은 [Agent Hub 연동 경계와 운영 책임](/docs/boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary)을 따른다. BoI backend의 Agent Hub 호출은 승인 catalog 목록·상세 `GET`만 허용하며, 배포와 상태 변경은 기존 Agent Hub UI에서 사용자가 수행한다.

자산 작성자, Hub 자산 소유자, Langflow endpoint 소유자, Action 호출자는 서로 다른 주체일 수 있다.
권한과 비밀값은 다음 경계를 넘겨 섞지 않는다.

| 주체 | 보유하는 것 | BoI가 신뢰하는 근거 |
|---|---|---|
| 자산 작성자 | Flow JSON·custom component·버전 | Agent Hub에서 접근 가능한 승인 자산 |
| endpoint 소유자 | 개인 Langflow URL·API Key·프로젝트 | SSO Principal |
| Action 소유자 | exact deployment reference | endpoint·project·Flow ID·version·checksum |
| Action 호출자 | Wiki 조회·저장 권한 | HCP 역할과 1회성 run token |

Action의 공통 계약과 실행 연결은 분리한다.

- `action_contract`: 업무 목적, 입력·출력, 근거, 위험도, 승인 정책
- `execution_mode=gateway`: 모든 Action이 거치는 공통 실행 계층
- `connector_binding`: API, MCP, Webhook, Manual, Event Broker, BoI Writer,
  Langflow 중 실제 adapter와 설정 reference

Playground는 Langflow Flow를 배포·검증하는 제품 영역이므로 새 초안의
`connector_binding.kind`만 `langflow`다. 공통 Action schema, 등록 UI, catalog와
Gateway의 다른 connector를 Langflow 전용으로 바꾸지 않는다.

일반 사용자는 다른 작성자의 Agent Hub 자산을 자신의 endpoint와 프로젝트로 배포한다. 이번
버전에는 팀 endpoint가 없다. 팀 Action도 등록자의 개인 endpoint reference를 서버에서 해석하고,
호출자의 HCP 팀 권한과 Wiki ACL을 별도로 적용한다. 다른 직원의 개인 API Key를 복사하거나
BoI와 Agent Hub 사이에서 key를 동기화하지 않는다.

1. 사용자 API Key로 실제 Langflow 연결을 시험한다.
2. `boi-{사번}` 프로젝트를 선택한다.
3. canonical Flow와 model Agent Flow를 배포한다.
4. Playground가 exact Flow ID를 live API로 다시 찾는다.
5. structural, 실제 `/api/v1/run`, Task Context, Ontology, private draft를 Flow별로 검증한다.
6. `action_ready` Flow만 등록 초안을 만든다.
7. validate와 publish-request 후 운영 승인 절차로 catalog에 반영한다.
8. BoI Wiki 일반 화면과 SOP Task에서 같은 Action을 실행한다.

model Agent Flow는 `model_trace.real_inference=true`와 실제 모델명, 응답 ID 또는 usage 증거가 있어야 통과한다.
Agent Hub가 component를 미연결 노드로 배포한 사실만으로 사용 완료로 처리하지 않는다.
`boi.agent-slot.v1`의 단일 입출력 규약이 명확할 때만 Playground가 공개 Flow PATCH API로
`agent_slot`을 교체한다. 그 외에는 수동 연결 사유와 Canvas URL을 제공한다. 실제 실행 경로와
runtime provenance에서 component ID가 확인되지 않으면 `disconnected_component`로 차단한다.

지식 facade는 Task anchor를 먼저 실제 업무 Context로 해석하고 Ontology Registry의 typed
workflow·responsibility·lineage·impact 관계를 기본으로 조회한다. Markdown link는 document
관계로만 사용하며 graph가 없을 때만 `grounded_document_fallback`으로 표시한다. 내부 MCP
호환 이름은 운영 구현 세부정보이며 Playground나 시작·운영 화면에 별도 검색 기능으로
노출하지 않는다.

# 장애와 rollback

- endpoint Key 오류: 새 Langflow Key로 교체하되 빈 입력은 기존 Key를 유지한다.
- BoI PAT 오류: 원자적으로 새 PAT를 등록한 뒤 기존 PAT를 폐기한다.
- bundle build 오류: Langflow 이미지를 패치하지 않고 호환 bundle을 다시 만든다.
- Langflow 버전 범위 초과: 연결 정보는 보존하지만 bootstrap·배포·Action 등록을 차단한다.
- Action 장애: exact endpoint/project/Flow/version/checksum을 대조하고 불일치 catalog fixture를 적용하지 않는다.
- Flow drift: draft·validate·operator 적용·실행 직전에 live checksum을 다시 읽고,
  등록 checksum과 다르면 `blocked`로 전환한다.

# 완료 증거

증거는 `/tmp`가 아닌 `artifacts/agent-playground-handoff/<run_id>/`에 둔다.

- image digest와 read-only mount
- boundary 검사 결과
- SSO 로그인과 spoof 차단
- 신규 사용자 온보딩
- Agent Hub 연결·배포
- exact Flow ID·checksum
- model inference trace
- Action 일반/SOP 실행
- source references·Ontology provenance·private draft owner
- desktop·mobile 화면
- secret scan
- `SHA256SUMS`와 cherry-pick 순서

과거 `d85c44a6`의 45/45 감사와 handoff는 보완 재검증의 근거로 사용하지 않는다.
새 감사는 HCP 축소, audience 오용, 가짜 Task, 미연결 component, checksum drift,
팀 호출자 초안 소유권 같은 부정 테스트의 실제 요청·응답을 함께 포함해야 한다.
