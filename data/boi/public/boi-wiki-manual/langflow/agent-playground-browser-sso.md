---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: 회사 SSO로 Langflow 원본 Flow 열기
description: Agent Playground에서 별도 비밀번호 입력 없이 exact Langflow Canvas를 여는 방법과 상태 의미
tags: [Manual, AgentPlayground, Langflow, SSO, Canvas]
timestamp: 2026-07-28T13:30:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-browser-sso
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

# 무엇이 달라지는가

Playground의 `원본 열기`는 Flow를 단순 그림으로 다시 그리지 않고 실제 Langflow
Canvas를 연다. 회사 SSO가 준비된 환경에서는 BoI에 로그인한 사번으로 Langflow도
인식하므로 Langflow 계정과 비밀번호를 다시 입력하지 않는다.

사내 인증 제품이 반드시 Keycloak일 필요는 없다. OIDC, 검증된 회사 SSO header,
직원별로 격리된 사내 Langflow SSO 중 운영자가 검증한 방식을 사용하며 화면에는
현재 방식과 준비 상태가 표시된다.

Flow 배지는 실행 위치가 아니라 자산이 거친 경로를 뜻한다.

| 배지 | 의미 |
|---|---|
| `DEV · Playground` | 개인 프로젝트에서 개발·시험 중 |
| `PRD · Agent Hub` | Agent Hub 배포 결과를 exact Flow ID로 다시 찾음 |

PRD라도 검증이 끝났다는 뜻은 아니다. `검증 필요`, `Action 연결 가능`,
`변경되어 재검증 필요` 상태를 함께 확인한다.

# 화면에서 확인할 것

1. 온보딩의 `원본 Flow 로그인`이 `회사 SSO 준비됨`인지 확인한다.
2. Flow를 선택하고 `회사 SSO로 원본 Flow 열기`를 누른다.
3. Langflow Canvas의 프로젝트와 Flow 이름을 확인한다.
4. BoI 사번과 Langflow 사용자가 다르면 편집하지 말고 Playground로 돌아온다.

상태가 `별도 Langflow 로그인 필요`이면 현재 endpoint가 비상용 `native` 모드다.
이는 사내 SSO 준비 완료 상태가 아니다. `사번 불일치`나 `공유 사용자 사용 불가`는
소유권 격리가 깨진 상태이므로 Flow 배포와 Action 연결을 진행하지 않는다.

# 로그인과 Key는 서로 다르다

- Browser SSO: 사람이 BoI와 Langflow 화면을 열 때 사용한다.
- Langflow API Key: Playground가 프로젝트·Flow를 조회하고 Agent Hub가 배포할 때 사용한다.
- BoI PAT: Langflow 내부 Component가 Wiki·Ontology를 읽는 장기 연결이다.
- Action run token: Action을 실행한 사람의 Wiki 권한을 한 번의 실행에만 전달한다.

SSO가 정상이어도 Agent Hub 배포에는 개인 Langflow API Key가 계속 필요하다. Key를
URL, Flow JSON, Wiki 문서에 넣지 않는다.

# 문제가 생겼을 때

- 다시 로그인 화면이 뜨면 `원본 Flow 로그인` 상태와 SSO gateway 상태를 확인한다.
- Canvas는 열리지만 사용자 확인이 실패하면 Langflow 외부 인증의 issuer, audience,
  JWKS와 JIT 사용자 생성 로그를 확인한다.
- 사번이 다르면 다른 직원의 Key나 공유 Langflow 사용자를 연결하지 않았는지 확인한다.
- `host.docker.internal` 주소가 보이면 내부 API 주소가 브라우저 URL로 잘못 노출된
  것이므로 운영자에게 알린다.
- 공식 Langflow 1.11 external JWT에서 Canvas가 계속 로딩되면 Langflow를 직접
  수정하지 않는다. 운영 가이드의 patch별 external-auth 회귀 결과를 확인하고,
  검증된 employee-isolated `embedded_sso` 경로를 사용한다.

[Langflow API Key와 SSO의 차이](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-langflow-setup)
[SSO·Key·Flow 연결 문제 해결](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-troubleshooting)
