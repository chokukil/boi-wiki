---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: NAS SERVICE_TOKEN 운영 절차
description: NAS PoC에서 단일 SERVICE_TOKEN을 유지하고 짧은 maintenance restart로 rotation하는 운영 기준
tags: [Manual, NAS, ServiceToken, DockerCompose, Operations]
timestamp: 2026-06-20T00:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:nas-service-token-rotation
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
    ref: docker-compose.yml
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

NAS PoC는 무중단 dual-token rotation을 구현하지 않는다. 추측 어려운 단일 `SERVICE_TOKEN`을 NAS `.env`에 유지하고, 변경이 필요하면 관련 서비스를 같은 compose 사이클에서 강제 재생성한다.

# Scope

`SERVICE_TOKEN`은 user login token이 아니라 내부 trusted service 간 shared secret이다. 다음 서비스가 같은 값을 봐야 한다.

- `boi-api`
- `action-gateway`
- `event-router`
- `boi-wiki-mcp`
- `langflow`

`boi-wiki-mcp`는 두 경로에서 이 token을 사용한다. `/api/mcp/call` bridge는 항상 `x-service-token`을 요구한다. `/mcp` Streamable HTTP endpoint는 `MCP_REQUIRE_SERVICE_TOKEN=true`일 때 `x-service-token` 또는 `Authorization: Bearer <token>`을 요구한다. NAS처럼 외부에서 접근 가능한 endpoint는 `MCP_REQUIRE_SERVICE_TOKEN=true`가 권장값이다.

# Rotation Flow

1. NAS app path `/volume1/docker/boi-wiki/app`에서 `.env`를 백업한다.
2. `openssl rand -hex 32` 또는 `/dev/urandom` fallback으로 새 token을 만든다.
3. `.env`의 `SERVICE_TOKEN` 값만 교체한다. 값은 stdout, Git, chat, README에 남기지 않는다.
4. `docker-compose.nas.yml`과 `--env-file .env`를 사용해 관련 서비스를 강제 재생성한다.

```bash
sudo env PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  /usr/local/bin/docker-compose \
  -f docker-compose.nas.yml \
  --env-file .env \
  up -d --force-recreate boi-api action-gateway event-router boi-wiki-mcp langflow
```

# Verification

- NAS 내부 `curl http://127.0.0.1:28000/`
- NAS 내부 `curl http://127.0.0.1:28200/health`
- 외부 `curl http://boi-wiki.example:28000/`
- 외부 `curl http://boi-wiki-mcp.example:28200/`
- MCP protocol tools/resource templates/prompts 확인
- 실제 token을 환경 변수로만 넘겨 `/mcp` protocol과 bridge check 확인
- token 없이 `/mcp`가 401을 반환해야 한다. 단, `MCP_REQUIRE_SERVICE_TOKEN=false`인 로컬 개발 환경에서는 200일 수 있다.
- 잘못된 token은 `/api/mcp/call`에서 401을 반환해야 한다.

protected MCP와 bridge를 같이 확인하는 명령은 다음 형식이다. token 값은 shell history나 log에 남기지 않는다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://boi-wiki-mcp.example:28200 \
  --mcp-url http://boi-wiki-mcp.example:28200/mcp \
  --service-token "$SERVICE_TOKEN" \
  --require-bridge \
  --summary
```

# Non Goals

- PoC 단계에서 무중단 dual-token rotation을 구현하지 않는다.
- runtime `.env`나 token 값을 Git에 넣지 않는다.
- 기본 개발용 token을 NAS 외부 공개 환경에서 사용하지 않는다.

# Citations

- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [SSO and Permission Model](/public/boi-wiki-manual/security/sso-and-permissions.md)
