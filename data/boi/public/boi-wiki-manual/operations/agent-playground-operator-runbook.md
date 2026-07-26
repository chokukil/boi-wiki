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
  reviewer: platform-lead
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

# Secret 관리

- Langflow API Key는 BoI 전용 암호화 키로 암호화한다.
- 응답에는 `has_api_key`와 fingerprint만 제공한다.
- BoI PAT는 BoI 저장소에 hash만 남기고 Langflow Credential에는 원문을 한 번 등록한다.
- Action run token은 caller, Action, Flow, trace, scope, TTL에 묶고 사용 후 폐기한다.
- Flow, manifest, README, Wiki 초안, 일반 로그와 스크린샷을 secret scan한다.

# Agent Hub와 Action 검증

Agent Hub checkout은 지정 SHA를 유지하고 diff가 없어야 한다.

자산 작성자, Hub 자산 소유자, Langflow endpoint 소유자, Action 호출자는 서로 다른 주체일 수 있다.
권한과 비밀값은 다음 경계를 넘겨 섞지 않는다.

| 주체 | 보유하는 것 | BoI가 신뢰하는 근거 |
|---|---|---|
| 자산 작성자 | Flow JSON·custom component·버전 | Agent Hub에서 접근 가능한 승인 자산 |
| endpoint 소유자 | Langflow URL·API Key·프로젝트 | SSO Principal 또는 운영자가 관리하는 팀 연결 |
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

일반 사용자는 다른 작성자의 Agent Hub 자산을 자신의 endpoint와 프로젝트로 배포한다. 이미 공유
endpoint에 배포된 Flow를 그대로 사용하는 경로는 운영자가 팀 연결을 등록하고 HCP 사용 권한을
부여한 경우에만 허용한다. 다른 직원의 개인 API Key를 복사하거나 BoI와 Agent Hub 사이에서 key를
동기화하지 않는다.

1. 사용자 API Key로 실제 Langflow 연결을 시험한다.
2. `boi-{사번}` 프로젝트를 선택한다.
3. canonical Flow와 model Agent Flow를 배포한다.
4. Playground가 exact Flow ID를 live API로 다시 찾는다.
5. structural, build, runtime, SOP Task, Ontology, private draft를 Flow별로 검증한다.
6. `action_ready` Flow만 등록 초안을 만든다.
7. validate와 publish-request 후 운영 승인 절차로 catalog에 반영한다.
8. BoI Wiki 일반 화면과 SOP Task에서 같은 Action을 실행한다.

model Agent Flow는 `model_trace.real_inference=true`와 실제 모델명, 응답 ID 또는 usage 증거가 있어야 통과한다.
중간 Agent 영역은 특정 노드 ID로 제한하지 않는다. Agent Hub의 custom component를 조합한 Flow도
`BoIWikiKnowledge`, `BoIWikiSave`, 선언된 `boi_contract`, build와 실제 실행 검증을 통과하면
Action 후보가 된다. 일부만 완성된 Flow는 registry에 남기되 `action_ready`로 승격하지 않는다.

# 장애와 rollback

- endpoint Key 오류: 새 Langflow Key로 교체하되 빈 입력은 기존 Key를 유지한다.
- BoI PAT 오류: 원자적으로 새 PAT를 등록한 뒤 기존 PAT를 폐기한다.
- bundle build 오류: Langflow 이미지를 패치하지 않고 호환 bundle을 다시 만든다.
- Langflow 버전 범위 초과: 연결 정보는 보존하지만 bootstrap·배포·Action 등록을 차단한다.
- Action 장애: exact endpoint/project/Flow/version/checksum을 대조하고 불일치 catalog fixture를 적용하지 않는다.

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
