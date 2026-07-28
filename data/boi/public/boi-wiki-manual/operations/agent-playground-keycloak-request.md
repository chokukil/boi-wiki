---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Hub 담당자 Keycloak 등록 요청
description: BoI Wiki와 Langflow browser가 함께 사용할 단일 boi-wiki OIDC client 요청문
tags: [Manual, Operations, AgentPlayground, Keycloak, OIDC, SSO]
timestamp: 2026-07-28T18:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:agent-playground-keycloak-request
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: validation/agent-hub/keycloak-realm.json
  - type: repo
    ref: validation/agent-playground-mainline/docker-compose.yml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 전달할 요청문

아래 내용만 Agent Hub 담당자 또는 해당 Keycloak realm 운영자에게 전달한다.

```text
안녕하세요. BoI Agent Playground와 Langflow 원본 Canvas의 사내 SSO 연계를 위해
현재 Agent Hub가 사용하는 Keycloak realm에 아래 client 등록을 요청드립니다.

Client ID
- boi-wiki

설정
- Client type: Confidential
- Authorization Code Flow: 사용
- PKCE: S256 필수
- Direct Access Grant / Implicit Flow / Service Account: 사용 안 함

Redirect URI
- http://wiki.skhynix.com/auth/callback
- http://wiki.skhynix.com/builder/oauth2/callback

Web Origin
- http://wiki.skhynix.com

Post Logout Redirect URI
- http://wiki.skhynix.com/*

Claim
- empno를 String으로 발급
- empno를 ID token, access token, userinfo에 포함
- name, email 포함

회신 요청
- boi-wiki client secret
- Issuer 또는 OpenID Discovery URL

client secret은 사내 보안 전달 경로로 부탁드립니다.
기존 Agent Hub client와 Agent Hub 소스 변경은 요청하지 않습니다.
```

# 적용 원칙

- BoI API와 Langflow browser 인증 프록시는 같은 `client_id=boi-wiki`를 사용한다.
- client secret은 Secret Manager 또는 승인된 환경변수로만 주입한다.
- secret을 Git, Wiki, Caddyfile, 캡처, 일반 로그에 남기지 않는다.
- Keycloak은 신원과 `empno`를 제공하고, 실제 Wiki·Action 권한은 HCP가 결정한다.
- 별도 `langflow-browser` client나 audience mapper는 만들지 않는다.
- 기존 Agent Hub client와 Agent Hub 코드는 변경하지 않는다.

# 확인할 값

등록 후 다음 값만 비밀 전달 경로에서 확인한다.

```text
BOI_OIDC_CLIENT_ID=boi-wiki
BOI_OIDC_CLIENT_SECRET=<secret-manager reference>
BOI_OIDC_ISSUER_URL=<issuer>
BOI_OIDC_EMPLOYEE_CLAIM=empno
```

BoI callback과 Langflow callback이 모두 같은 client에 등록되고 PKCE S256이
강제되는지 확인한다.
