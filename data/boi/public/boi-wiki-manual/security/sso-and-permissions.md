---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: SSO and Permission Model
description: SK hynix Keycloak/HCP SSO, local development auth, BoI Wiki ACL, MCP, Langflow 권한 운영 기준
tags: [Manual, SSO, Keycloak, HCP, Authorization, Langflow, MCP]
timestamp: 2026-06-19T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:security:sso-and-permissions
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
    ref: docker-compose.sso-dev.yml
  - type: repo
    ref: infra/keycloak/boi-dev-realm.json
  - type: external
    ref: https://github.com/YeonghyeonKO/langflow-hynix
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Wiki의 운영 권한은 OKF 문서 ACL과 사용자 identity를 함께 본다. 개발 모드는 사번 selector를 유지하지만, SSO 모드에서는 Keycloak claim과 HCP 권한 응답이 source of truth다.

# SK hynix SSO Baseline

이 PoC의 SSO 기준은 [langflow-hynix](https://github.com/YeonghyeonKO/langflow-hynix)의 Keycloak/HCP 모델과 맞춘다.

| 항목 | BoI Wiki | Langflow-Hynix |
| --- | --- | --- |
| Browser SSO | `/auth/login` -> Keycloak Authorization Code + PKCE | `/api/v1/keycloak/login` -> Keycloak Authorization Code + PKCE |
| Issuer/JWKS split | `KEYCLOAK_ISSUER_URL`, `KEYCLOAK_INTERNAL_URL` | `KEYCLOAK_SERVER_URL`, `KEYCLOAK_EXTERNAL_SERVER_URL` |
| Employee claim | `BOI_EMPLOYEE_CLAIM` 또는 `KEYCLOAK_EMPLOYEE_CLAIM` | `KEYCLOAK_EMPLOYEE_CLAIM` |
| Project authorization | `HCP_AUTHZ_URL` 또는 `KEYCLOAK_HCP_API_URL` | `KEYCLOAK_HCP_API_URL` |
| Per-instance restriction | `BOI_ALLOWED_EMPLOYEE_IDS` 또는 `KEYCLOAK_ALLOWED_EMPLOYEE` | `KEYCLOAK_ALLOWED_EMPLOYEE` |
| Admin bypass | `boi.admin` 또는 `KEYCLOAK_ADMIN_EMPLOYEES` | `KEYCLOAK_ADMIN_EMPLOYEES` |

Langflow-Hynix는 SSO 성공 사용자를 shared Langflow account에 매핑하고, 접근 가능 여부는 Keycloak employee claim과 HCP project roles로 판단한다. BoI Wiki는 같은 employee/team/role 의미를 사용하되, BoI 문서 ACL과 action/workflow role까지 같이 검증한다.

# Auth Modes

| Mode | 용도 | Identity source | 주의 |
| --- | --- | --- | --- |
| `dev` | 로컬 PoC와 테스트 | `employee_id` query, dev user map | 사내 공유 환경에서 사용하지 않는다. |
| `keycloak` | SK hynix SSO | Keycloak OIDC + HCP permission API | `employee_id` query가 로그인 사용자와 다르면 403이다. |
| `trusted_header` | 사내 인증 proxy 뒤 배포 | `X-Hynix-*` trusted headers | proxy가 헤더를 덮어쓰는 구조에서만 사용한다. |

# Permission Rules

| Scope | Read rule | Write/draft rule |
| --- | --- | --- |
| `public` | 인증 사용자 전체 | `boi.editor` |
| `team/{team}` | identity teams에 포함 | `boi.editor` and team membership |
| `private/{employee}` | 본인 또는 `boi.admin` | 본인 and `boi.editor` |

Action과 workflow 실행은 별도 role을 요구한다.

- `boi.workflow_runner`: Event/Workflow start.
- `boi.action_invoker`: user-facing Action invoke.
- `boi.promoter`: private BoI를 team/public draft로 승격 요청.
- `boi.admin`: 전체 관리와 break-glass 운영.

# HCP Role Mapping

BoI Wiki는 두 가지 HCP 응답을 모두 지원한다.

Employee-scoped BoI 응답:

```json
{"employee_id":"100001","teams":["aix-tf","platform"],"roles":["boi.viewer","boi.editor"],"projects":["boi-wiki"]}
```

Langflow-Hynix project roles 응답:

```json
{"response":{"managers":["100001"],"deployApprovers":["100001"],"developers":["100002"]}}
```

Project roles는 BoI role로 다음처럼 변환된다.

| HCP group | BoI roles |
| --- | --- |
| `managers` | viewer, editor, promoter, workflow_runner, action_invoker, admin |
| `deployApprovers` | viewer, editor, promoter, workflow_runner, action_invoker |
| `developers` | viewer, editor, workflow_runner, action_invoker |

# Local SSO Development

```bash
docker compose -f docker-compose.yml -f docker-compose.sso-dev.yml up -d --build
```

개발 realm에는 `100001`, `100002`, `100003` 사용자가 있고 비밀번호는 모두 `password`다. `100001`은 `aix-tf`, `platform`, admin 역할을 가진다. `100002`는 `aix-tf`, `100003`은 `platform`만 가진다.

BoI Wiki는 `http://localhost:8000/auth/login`에서 Keycloak으로 이동한다. Langflow는 `langflow-hynix` SSO 이미지로 뜨며 `http://localhost:7860`에서 같은 realm을 사용한다.

SSO overlay는 Langflow-Hynix가 실제로 읽는 환경변수를 사용한다.

- `KEYCLOAK_SERVER_URL`: Langflow container에서 Keycloak으로 가는 내부 URL.
- `KEYCLOAK_EXTERNAL_SERVER_URL`: 브라우저가 접근하는 Keycloak URL.
- `KEYCLOAK_HCP_API_URL`: Mock HCP project roles endpoint.
- `KEYCLOAK_ALLOWED_EMPLOYEE`: per-employee Langflow instance 제한.
- `KEYCLOAK_SHARED_USERNAME`: SSO 사용자를 매핑할 shared Langflow user.

개발 Mock HCP는 `GET /api/permissions?employee_id=...`와 `GET /v1/projects/{project}/roles`를 모두 제공한다. BoI Wiki는 전자를 기본으로 쓰고, Langflow-Hynix는 후자를 쓴다.

# MCP and Agent Use

BoI Wiki MCP는 agent가 OKF 문서, action catalog, workflow 상태, draft queue를 다룰 때 사용하는 인터페이스다. 개발 모드에서는 tool argument로 `employee_id`를 넘길 수 있다. SSO/운영 모드에서는 caller identity를 사용해야 하며, 다른 사번을 임의로 지정하는 사용 방식은 허용하지 않는다.

# Production Defaults

- `BOI_AUTH_MODE=keycloak`
- `LANGFLOW_AUTO_LOGIN=false`
- `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=false`
- `BOI_COOKIE_SECURE=true`
- `BOI_SESSION_SECRET`, `LANGFLOW_SECRET_KEY`, `SERVICE_TOKEN`, `KEYCLOAK_CLIENT_SECRET`은 Secret Manager에서 공급한다.
- HCP 권한 API 장애 시 fail-closed로 처리한다.

# Citations

- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [Langflow connected flow guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
- [Web draft와 Git commit 정책](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
