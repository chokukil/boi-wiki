---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground 사내 SSO 방식 선택 가이드
description: OIDC, trusted header, Token Bridge, embedded SSO와 native 모드의 적용 계약
tags: [Manual, Operations, AgentPlayground, SSO, OIDC, TrustedHeader, Langflow]
timestamp: 2026-07-28T13:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:agent-playground-sso-deployment
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
    ref: boi_api/app/auth.py
  - type: repo
    ref: sso_token_bridge/app/main.py
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 선택 순서

1. 사내 OIDC client 등록이 가능하고 대상 Langflow patch에서 브라우저 회귀까지
   통과하면 `oidc + external_jwt`를 사용한다.
2. client 등록은 불가능하지만 인증 gateway가 검증한 사번 header를 제공하면
   `trusted_header + trusted_header_bridge`를 사용한다.
3. 사내 SSO Langflow 이미지나 gateway가 제공되면 `embedded_sso` 계약을 검사한다.
4. 세 방식이 모두 불가능할 때만 `native`를 사용한다. 화면에는 별도 로그인이
   필요하다고 표시하며 SSO 준비 완료로 보지 않는다.

Keycloak은 로컬 기준 구현체일 뿐 사내 필수 제품이 아니다. 모든 방식은
`AuthIdentity(employee_id, display_name, email, teams, roles, auth_source)`로
수렴하며 HCP를 업무 권한의 최종 권위로 사용한다.

# OIDC와 JWKS

BoI는 `BOI_AUTH_MODE=oidc`에서 Authorization Code와 PKCE S256을 사용한다.
공급자 중립 설정은 다음과 같다.

```text
BOI_OIDC_ISSUER_URL
BOI_OIDC_INTERNAL_URL
BOI_OIDC_AUTHORIZATION_URL
BOI_OIDC_TOKEN_URL
BOI_OIDC_JWKS_URL
BOI_OIDC_CLIENT_ID
BOI_OIDC_CLIENT_SECRET
BOI_OIDC_REDIRECT_URI
BOI_OIDC_EMPLOYEE_CLAIM
BOI_OIDC_TEAMS_CLAIM
BOI_OIDC_ROLES_CLAIM
BOI_SSO_LOGOUT_URL
```

기존 `KEYCLOAK_*` 값은 대응하는 `BOI_OIDC_*`가 없을 때만 호환값으로 읽는다.
Langflow는 공식 external auth 설정으로 JWT 서명, issuer, audience, expiry를
검증한다. trusted decode는 사용하지 않는다. API에서 JWT 검증과 사용자 식별이
성공한 것만으로 Canvas 준비 완료로 판단하지 않으며, 실제 브라우저의 초기 세션
생성·`whoami`·Flow 편집 화면까지 함께 시험한다.

# Trusted Header와 Token Bridge

`BOI_AUTH_MODE=trusted_header`는 다음 조건을 모두 만족할 때만 허용한다.

- gateway가 외부 요청의 identity header를 제거하고 인증 결과로 다시 생성한다.
- BoI가 proxy shared secret과 source CIDR를 모두 검증한다.
- header의 role은 권위로 쓰지 않고 HCP를 다시 조회한다.
- BoI backend와 Token Bridge는 gateway 뒤에서만 접근할 수 있다.

```text
BOI_TRUSTED_EMPLOYEE_HEADER
BOI_TRUSTED_NAME_HEADER
BOI_TRUSTED_EMAIL_HEADER
BOI_TRUSTED_TEAMS_HEADER
BOI_TRUSTED_PROXY_SECRET_HEADER
BOI_TRUSTED_PROXY_SHARED_SECRET
BOI_TRUSTED_PROXY_CIDRS
```

JWT를 제공하지 않는 gateway에서는 독립 Token Bridge가 60초 RS256 JWT를 만든다.
JWT에는 사번·이름·이메일·issuer·audience·만료만 넣고 역할은 넣지 않는다.
private key는 Secret Manager에서 주입하며 Bridge에는 외부 공개 포트를 만들지 않는다.

로컬 회귀에서는 gateway가 사용자가 제출한 신원 header를 제거한 뒤 세션 사번을
다시 주입하고, Bridge JWT를 서버 사이에서만 전달한다. 다른 사번 header와 query
spoof는 거부하며 JWT 원문은 HTML·URL·브라우저 API 응답에 반환하지 않는다.

# Embedded SSO

사내 제공 Langflow SSO URL은 `LANGFLOW_EXTERNAL_URL`에 그대로 설정한다. 공개
`whoami` 결과와 BoI 사번을 대조한다. 여러 직원을 하나의 무제한 shared Langflow
user로 연결하면 readiness를 실패시킨다. 직원별로 완전히 격리된 instance는 해당
instance가 한 사번에 제한된 경우에만 shared local user를 허용한다.

Langflow source, 사내 이미지, DB를 BoI 저장소에서 수정하지 않는다.

# 공식 Langflow 1.11.0 검증 결과

고정 digest의 공식 1.11.0에서 external JWT의 서명·issuer·audience·expiry 검증과
SQLite 기반 JIT API 인증은 확인했다. 그러나 다음 브라우저·DB 제약도 함께
확인되었다.

- 1.11.0 frontend가 external JWT 수락 뒤에도 내장 refresh-cookie lifecycle을
  시작해 Canvas가 로딩 상태에 머물 수 있다.
- PostgreSQL JIT 사용자 생성에는 user row flush 전 연관 row를 쓰는 순서 문제가
  발생할 수 있다.

이 제약을 Langflow source patch나 DB 직접 수정으로 우회하지 않는다. 로컬 완전
브라우저 회귀는 회사 SSO gateway가 한 사번만 허용하고 공식 Langflow auto-login
사용자도 같은 사번인 `embedded_sso` fallback으로 통과시켰다. 새로운 공식
1.11.x patch에서 external JWT browser·PostgreSQL 회귀가 통과하면 설정만
`external_jwt`로 전환한다.

# Browser URL과 API URL

```text
LANGFLOW_EXTERNAL_URL  = 사람이 여는 SSO Canvas와 Settings 주소
LANGFLOW_DEPLOY_URL    = Playground, Agent Hub, Action이 API Key로 호출하는 host-root
LANGFLOW_MCP_EXTERNAL_URL = 외부 MCP client가 API Key로 호출하는 공개 host-root
```

SSO browser proxy가 API Key 기반 MCP client를 받지 않는 경우가 있으므로 MCP URL을
Canvas URL과 분리한다. 컨테이너 전용 주소, JWT, API Key를 브라우저 응답과 링크에
넣지 않는다. Agent Hub에는 `LANGFLOW_DEPLOY_URL`과 개인 API Key를 사용자가 기존
UI에서 직접 등록한다.

# Readiness와 장애

`GET /api/agent-playground`의 `browser_sso.status`는 다음 중 하나다.

- `ready`
- `native_login_required`
- `principal_mismatch`
- `shared_identity_not_allowed`
- `gateway_unreachable`
- `token_validation_failed`
- `unchecked`

Canvas HTML 200만으로 `ready` 처리하지 않는다. 실제 `whoami`와 BoI 사번을 비교해야
한다. 공식 Langflow의 external-auth JIT 오류가 발생하면 Langflow를 패치하거나 DB를
직접 수정하지 말고 `token_validation_failed`로 차단한 뒤, 수정된 공식 이미지 또는
검증된 `embedded_sso` 경로를 사용한다.

# 로컬 공급자 독립 회귀 주소

| 경로 | 주소 | 확인 내용 |
|---|---|---|
| OIDC 기준 BoI | `http://localhost:28005` | Authorization Code + PKCE, `auth_source=oidc` |
| OIDC Langflow | `http://localhost:17867` | 같은 OIDC 세션, 추가 비밀번호 없음 |
| Mock 회사 gateway | `http://localhost:28006` | trusted header, HCP 재조회, spoof 차단 |
| Mock 회사 Langflow gateway | `http://localhost:17870` | 동일 gateway 세션, employee-isolated embedded SSO |

`17870`은 공식 1.11.0 external JWT frontend 제약 때문에 사용하는 검증 fallback이다.
Token Bridge JWT는 매 요청마다 server-side로 주입되지만 이 fallback의 Langflow는
그 JWT를 인증 근거로 사용하지 않는다. 따라서 Bridge 서명 계약과 embedded Canvas
계약을 각각 검증한 것이며, external JWT frontend 통과를 과장하지 않는다.

# 외부 제품 경계

Langflow와 Agent Hub 소스·화면·DB·인증 코드는 BoI에서 수정하지 않는다. Agent Hub
배포는 기존 UI에서 수행하고 BoI는 배포 후 exact Flow ID와 checksum을 공개 Langflow
API에서 다시 찾는다.
