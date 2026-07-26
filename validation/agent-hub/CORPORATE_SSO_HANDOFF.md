# 사내 SSO 등록·적용 handoff

이 mainline 브랜치는 SSO 연동을 가정한 인증 계약을 구현한다. 사내 Keycloak/HCP
인프라 자체와 Caddy/DNS는 이 브랜치의 구현 범위가 아니다. 적용 기준점은
`origin/main@53912644c443b0a2af0e5c367901575a111b18ae`다.

## Keycloak client 요청값

| 항목 | 값 |
| --- | --- |
| Client ID | `boi-wiki` |
| Client type | confidential, server-side |
| Flow | authorization code |
| PKCE | S256 required |
| Direct access grants | disabled |
| Redirect URI | `http://wiki.skhynix.com/auth/callback` |
| Web origin | `http://wiki.skhynix.com` |
| Employee claim | `empno` |

`employee_id` mapper는 전환 호환용으로만 둘 수 있다. BoI의 표준 claim은
Agent Hub와 같은 `empno`다.

## BoI 환경변수

```text
BOI_AUTH_MODE=keycloak
BOI_EXTERNAL_URL=http://wiki.skhynix.com
KEYCLOAK_CLIENT_ID=boi-wiki
KEYCLOAK_CLIENT_SECRET=<secret-manager reference>
KEYCLOAK_REALM=<corporate realm>
KEYCLOAK_EMPLOYEE_CLAIM=empno
KEYCLOAK_REDIRECT_URI=http://wiki.skhynix.com/auth/callback
KEYCLOAK_ISSUER_URL=<browser-visible issuer>
KEYCLOAK_INTERNAL_URL=<server-reachable issuer>
HCP_AUTHZ_URL=<HCP permission endpoint>
```

SSO mode에서는 query, form, header의 사번을 소유권에 사용하지 않는다. 로그인
`AuthIdentity`와 다른 사번을 전달하면 403이다. Keycloak은 신원·그룹을 제공하고 HCP
응답이 업무 역할의 최종 권위다. HCP 실패는 fail-closed다.

확정 역할 fixture:

- `100001`: admin, editor, workflow runner, Action invoker
- `100002`: viewer, editor, workflow runner, Action invoker
- `100003`: viewer only

## Langflow와 URL 경계

Langflow 사내 SSO 이미지가 없어도 BoI SSO와 Action 권한 계약은 검증할 수 있다.
Langflow는 사번별 native user/API Key/project로 분리한다.

```text
LANGFLOW_EXTERNAL_URL=http://wiki.skhynix.com/builder
LANGFLOW_DEPLOY_URL=<host-root where /api/v1 is reachable>
```

Agent Hub PR #25는 endpoint의 path를 제거하므로 `/builder` 주소를 endpoint로
등록하지 않는다. Caddy는 사내 환경에서 위 두 URL 계약을 만족시켜야 한다.

## 체리픽과 적용 순서

Handoff 패키지의 `CHERRY_PICK_ORDER.md`를 적용한다. 파일에는 main 기준점 다음의
단일 mainline 커밋 full SHA가 기록되어 있다. 과거
`codex/agent-playground-integration`이나 `9fee2118`은 적용하지 않는다. 적용 후:

1. DB/runtime root를 백업한다.
2. `BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY`를 secret manager에서 주입한다.
3. Keycloak client와 `empno` mapper를 등록한다.
4. HCP endpoint와 확정 권한을 연결한다.
5. Langflow 1.11 bundle을 설치한다.
6. BoI SSO callback·spoof·logout smoke를 실행한다.
7. Agent Hub endpoint/project/Flow 배포를 확인한다.
8. exact Flow의 Action draft→validate→publish-request를 확인한다.
9. 사내 승인 절차로 catalog를 반영한다.
10. 일반 Wiki와 SOP Task에서 Action을 실행한다.

validation-only operator helper는 로컬 격리 DB용이다. 운영 catalog를 자동
반영하는 공개 API가 아니며 사내 승인·운영자 절차를 대체하지 않는다.
