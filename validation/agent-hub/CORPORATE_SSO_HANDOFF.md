# 사내 SSO 등록·적용 handoff

이 mainline 브랜치는 SSO 연동을 가정한 인증 계약을 구현한다. 사내 Keycloak/HCP
인프라 자체와 Caddy/DNS는 이 브랜치의 구현 범위가 아니다. 적용 기준점은
`origin/main@53912644c443b0a2af0e5c367901575a111b18ae`다.

## OIDC client 요청값

| 항목 | 값 |
| --- | --- |
| Client ID | `boi-wiki` |
| Client type | confidential, server-side |
| Flow | authorization code |
| PKCE | S256 required |
| Direct access grants | disabled |
| Redirect URI | `http://wiki.skhynix.com/auth/callback`, `http://wiki.skhynix.com/builder/oauth2/callback` |
| Web origin | `http://wiki.skhynix.com` |
| Employee claim | `empno` |

공급자는 Keycloak일 필요가 없다. `employee_id` mapper는 전환 호환용으로만 둘 수
있고 BoI의 표준 claim은 Agent Hub와 같은 `empno`다. OIDC client 등록이 불가능하면
검증된 회사 gateway header와 Token Bridge 또는 사내 embedded SSO Langflow를
선택한다.

BoI API와 Langflow browser 인증 프록시는 같은 `client_id=boi-wiki`와 client
secret을 사용한다. 별도 browser client나 audience mapper는 등록하지 않는다.
client secret은 사내 Secret Manager로 두 서비스에 주입한다.

## BoI 환경변수

```text
BOI_AUTH_MODE=oidc
BOI_EXTERNAL_URL=http://wiki.skhynix.com
BOI_OIDC_CLIENT_ID=boi-wiki
BOI_OIDC_CLIENT_SECRET=<secret-manager reference>
BOI_OIDC_EMPLOYEE_CLAIM=empno
BOI_OIDC_REDIRECT_URI=http://wiki.skhynix.com/auth/callback
BOI_OIDC_ISSUER_URL=<browser-visible issuer>
BOI_OIDC_INTERNAL_URL=<server-reachable issuer>
HCP_AUTHZ_URL=<HCP permission endpoint>
```

기존 `KEYCLOAK_*`는 대응하는 `BOI_OIDC_*`가 없을 때만 호환값으로 읽는다.
SSO mode에서는 query, form, header의 사번을 소유권에 사용하지 않는다. 로그인
`AuthIdentity`와 다른 사번을 전달하면 403이다. SSO는 신원·그룹을 제공하고 HCP
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
3. 선택한 SSO 방식과 `empno` mapper를 등록한다.
4. HCP endpoint와 확정 권한을 연결한다.
5. Langflow 1.11 bundle을 설치한다.
6. BoI SSO callback·spoof·logout smoke를 실행한다.
7. Agent Hub endpoint/project/Flow 배포를 확인한다.
8. exact Flow의 Action draft→validate→publish-request를 확인한다.
9. 사내 승인 절차로 catalog를 반영한다.
10. 일반 Wiki와 SOP Task에서 Action을 실행한다.

validation-only operator helper는 로컬 격리 DB용이다. 운영 catalog를 자동
반영하는 공개 API가 아니며 사내 승인·운영자 절차를 대체하지 않는다.

## 사내 acceptance gate

로컬 증거를 사내 완료 증거로 재사용하지 않는다. 사내 pre-production에서 HCP 역할
축소 `403`, 계정 비활성화 `403`, HCP 장애 `503`, 복구 `200` 결과를 비밀값 없이
`corporate-hcp-evidence.example.json` 형식으로 기록한 뒤 다음 runner를 실행한다.

```bash
CORPORATE_ACCEPTANCE_ENVIRONMENT=corporate \
CORPORATE_AUTH_MODE=external_jwt \
BOI_CORPORATE_URL=http://wiki.skhynix.com \
LANGFLOW_EXTERNAL_URL=http://wiki.skhynix.com/builder \
CORPORATE_EXPECTED_EMPLOYEE_ID=100002 \
CORPORATE_EXPECTED_FLOW_ID=<Agent Hub exact Flow ID> \
CORPORATE_EXPECTED_PROJECT_ID=<boi-100002 project ID> \
CORPORATE_HCP_EVIDENCE_FILE=/secure/tmp/corporate-hcp-evidence.json \
CORPORATE_SSO_INTERACTIVE=1 \
CORPORATE_EVIDENCE_DIR=artifacts/agent-playground-corporate-sso \
node validation/agent-playground-mainline/corporate_sso_acceptance_e2e.mjs
```

`CORPORATE_AUTH_MODE`은 실제 Langflow browser mode에 맞춰 `external_jwt`,
`trusted_header_bridge`, `embedded_sso` 중 하나를 사용한다. runner는 다음을 모두
확인해야 `final_acceptance=true`를 기록한다.

- exact PRD Flow가 Agent Hub 출처로 재발견됨
- Canvas에서 별도 password form이 없음
- BoI와 Langflow `whoami` 사번이 일치함
- query 사번 spoof가 `403`
- 로그아웃 후 BoI와 Langflow session이 모두 무효화됨
- HCP fail-closed 네 상태가 사내 증거와 일치함
- console/page/HTTP 오류와 token·API Key 노출이 없음

승인된 browser storage state를 사용하는 경우 파일은 인증 세션 비밀값이다.
`CORPORATE_STORAGE_STATE_OUTPUT`으로 만든 파일은 runner가 `0600`으로 저장하지만
handoff, Git, 메일, Wiki에 첨부하지 않는다.

마지막으로 감사 파일을 갱신한다.

```bash
python scripts/build_agent_playground_provider_sso_audit.py \
  --evidence-root artifacts \
  --output-dir artifacts/agent-playground-current/audit \
  --corporate-evidence \
    artifacts/agent-playground-corporate-sso/corporate-sso-acceptance.json
```

`goal_complete=true`, `external_gate=pass`가 동시에 나오기 전에는 사내 전체 목표
완료로 처리하지 않는다.
