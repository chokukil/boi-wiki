---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground·Langflow SSO Caddy 적용 프롬프트
description: 사내 Caddy에서 BoI callback과 Langflow browser callback을 연결하는 작업 프롬프트
tags: [Manual, Operations, AgentPlayground, Caddy, OIDC, Langflow]
timestamp: 2026-07-28T18:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:agent-playground-caddy-sso-routing
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:agent-playground-keycloak-request
  - type: repo
    ref: validation/agent-playground-mainline/docker-compose.yml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Caddy 작업 프롬프트

실제 upstream 주소는 사내 배치에서 확인하고, 기존 Caddy 설정을 백업한 뒤 아래
프롬프트를 적용한다.

```text
현재 사내 Caddy 설정을 확인하고 BoI Wiki와 Langflow browser SSO 경로를
다음 계약에 맞게 수정해줘.

공개 주소
- BoI Wiki: http://wiki.skhynix.com
- Langflow browser: http://wiki.skhynix.com/builder
- BoI callback: http://wiki.skhynix.com/auth/callback
- Langflow callback:
  http://wiki.skhynix.com/builder/oauth2/callback

OIDC
- BoI와 Langflow 인증 프록시는 같은 client_id=boi-wiki를 사용한다.
- client secret은 환경변수나 Secret Manager에서 주입한다.
- secret을 Caddyfile, 저장소, 로그에 기록하지 않는다.

라우팅
1. /auth/callback은 BoI API로 전달한다.
2. /builder와 /builder/*는 Langflow 인증 프록시로 전달한다.
3. Langflow upstream으로 전달할 때 /builder prefix를 제거한다.
4. 외부 /builder/oauth2/callback은 인증 프록시의 /oauth2/callback으로 전달한다.
5. WebSocket과 streaming 응답을 지원한다.
6. X-Forwarded-Proto=http과 X-Forwarded-Host를 정확히 전달한다.
7. 인증 프록시의 외부 redirect URL은 다음 값 하나로 고정한다.
   http://wiki.skhynix.com/builder/oauth2/callback
8. 기존 Wiki, Action, SOP, Event Broker 및 정적 파일 경로는 변경하지 않는다.
9. LANGFLOW_DEPLOY_URL은 browser용 /builder 주소와 분리된 기존 내부 주소를 유지한다.
10. authorization code, token, cookie, client secret 및 query string을 일반
    access log에 기록하지 않는다.

검증
- 실제 OIDC 요청의 client_id가 boi-wiki인지 확인한다.
- BoI 로그인 redirect_uri는
  http://wiki.skhynix.com/auth/callback이어야 한다.
- Langflow 로그인 redirect_uri는
  http://wiki.skhynix.com/builder/oauth2/callback이어야 한다.
- BoI에 로그인한 사용자가 원본 Flow를 열면 비밀번호를 다시 입력하지 않고
  exact Langflow Canvas로 이동해야 한다.
- callback 완료 후 URL에 code, token, empno가 남지 않아야 한다.
- /playground와 Flow 링크에 employee_id query parameter가 없어야 한다.

기존 설정을 먼저 백업하고 변경 내용과 검증 결과를 남겨줘.
Langflow와 Agent Hub 소스는 수정하지 마.
```

# 경로 해석

```text
/auth/callback
→ BoI API

/builder/oauth2/callback
→ Caddy에서 /builder 제거
→ Langflow 인증 프록시 /oauth2/callback

/builder/flow/{flow_uuid}/folder/{project_uuid}
→ Caddy에서 /builder 제거
→ Langflow 인증 프록시
→ Langflow Canvas
```

브라우저 주소와 서버 API 주소를 섞지 않는다.

```text
LANGFLOW_EXTERNAL_URL=http://wiki.skhynix.com/builder
LANGFLOW_DEPLOY_URL=<Agent Hub와 Action이 /api/v1을 호출할 host-root>
```

이번 계약에는 HTTPS·인증서 도입이 포함되지 않는다.
