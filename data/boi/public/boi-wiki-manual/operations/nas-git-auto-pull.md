---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: NAS Git Auto-Pull 배포 자동화
description: NAS에서 main 브랜치 변경을 주기적으로 가져오고 필요한 경우에만 Docker Compose를 재기동하는 운영 절차
tags: [Manual, NAS, Git, DockerCompose, Deployment, Operations]
timestamp: 2026-06-20T18:45:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:nas-git-auto-pull
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
    ref: scripts/nas_auto_pull_task.sh
  - type: repo
    ref: scripts/nas_auto_pull_deploy.sh
  - type: repo
    ref: docker-compose.yml
  - type: repo
    ref: README.md
review:
  reviewer: tf-lead
  reviewed_at: 2026-06-20T18:45:00+09:00
  review_status: reviewed
---

# Summary

NAS Git Auto-Pull은 `/volume1/docker/boi-wiki/app` Git worktree가 `main` 브랜치를 주기적으로 따라오게 하는 운영 자동화다. DSM Scheduled Task가 `scripts/nas_auto_pull_task.sh`를 1분 주기로 실행하고, wrapper는 로그 rotation 후 `scripts/nas_auto_pull_deploy.sh`를 호출한다. 배포 스크립트는 fast-forward 가능한 변경만 pull한다.

문서, event catalog, action catalog 변경은 BoI Wiki runtime volume과 cache invalidation으로 반영되므로 Docker Compose 재기동을 하지 않는다. 코드, Dockerfile, compose, requirements 등 runtime 변경이 포함되면 NAS 전용 `docker-compose.nas.yml`을 생성한 뒤 compose `up -d --build`를 실행한다.

runtime 변경이 포함된 배포는 현재 Git short SHA를 `.env`의 `BOI_BUILD_REVISION`에도 반영한다. Synology Docker package의 Compose v1은 `--env-file .env` 값을 interpolation에 강하게 사용하므로, shell에서 `BOI_BUILD_REVISION`을 export하는 것만으로는 오래된 revision이 계속 컨테이너에 들어갈 수 있다. 자동 배포 스크립트는 `.env` 내용을 출력하지 않고 해당 key만 갱신한 뒤 compose를 실행한다.

Git worktree가 최신 commit으로 pull된 상태와 실제 서비스가 새 revision을 실행하는 상태는 다르다. `boi-api`는 소스 디렉터리를 container에 bind mount하지 않고 image build 결과로 실행하므로, Python/JS/CSS/Dockerfile/requirements 변경은 `docker-compose up -d --build`가 끝나야 반영된다. NAS 계정이 Git pull은 할 수 있어도 Docker daemon, root-owned `.env`, root Scheduled Task 권한이 없으면 실행 중인 외부 서비스는 이전 revision으로 남는다.

# Runtime Defaults

| Setting | Default |
|---|---|
| App path | `/volume1/docker/boi-wiki/app` |
| Remote / branch | `origin main` |
| NAS compose file | `docker-compose.nas.yml` |
| Runtime env file | `.env` |
| Lock dir | `/tmp/boi-wiki-nas-auto-pull.lock` |
| Compose binary | `/usr/local/bin/docker-compose` |
| Runtime revision verify attempts | 90 attempts, 2 seconds apart |
| Log file | `/volume1/docker/boi-wiki/deploy-logs/autopull.log` |
| Log rotation | 10 MiB, 5 archives |

Runtime code 배포 필수 권한은 다음과 같다.

| Capability | Required for | Verification |
|---|---|---|
| Git worktree write | `git fetch`, `git pull --ff-only` | `git rev-parse HEAD`가 remote `main`과 일치 |
| root-owned `.env` update | `BOI_BUILD_REVISION`, Agent LLM env 갱신 | `.env` 값을 출력하지 않고 `/api/runtime/config` revision으로 확인 |
| Docker daemon / Compose | image build, container recreate | `docker-compose ps`와 `/api/runtime/config` revision |
| root DSM Scheduled Task 또는 SSH sudo | 비대화형 compose 실행 | root task 생성/실행 또는 `sudo docker-compose` 성공 |

기본값은 환경 변수로 바꿀 수 있다.

```bash
APP_DIR=/volume1/docker/boi-wiki/app
REMOTE=origin
BRANCH=main
COMPOSE_FILE=docker-compose.nas.yml
ENV_FILE=.env
LOG_DIR=/volume1/docker/boi-wiki/deploy-logs
LOG_MAX_BYTES=10485760
LOG_ROTATE_KEEP=5
NAS_RUNTIME_VERIFY_ATTEMPTS=90
```

# DSM Scheduled Task

DSM Task Scheduler에서 root 권한 task를 만들고 1분 주기로 다음 명령을 실행한다. 로그 redirection은 wrapper가 처리하므로 Scheduled Task 명령에 `>>`를 붙이지 않는다.

```bash
cd /volume1/docker/boi-wiki/app && \
  /usr/bin/env bash scripts/nas_auto_pull_task.sh
```

`autopull.log`가 10 MiB 이상이면 실행 시작 전에 `autopull.log.1`로 회전한다. 기존 `.1`~`.4`는 한 칸씩 밀리고 `.5`는 삭제된다. 로그의 마지막 줄은 항상 다음 중 하나여야 한다.

| Marker | Meaning |
|---|---|
| `DEPLOY_STATUS=noop` | remote `main`과 동일해서 할 일이 없음 |
| `DEPLOY_STATUS=success` | pull과 필요한 반영 작업이 성공 |
| `DEPLOY_STATUS=blocked` | dirty tracked worktree, branch mismatch, non fast-forward 등 안전 조건 위반 |
| `DEPLOY_STATUS=failed` | 예상하지 못한 실행 오류 |

# Safety Rules

- `git pull --ff-only origin main`만 사용한다.
- DSM Scheduled Task는 1분 주기로 실행하지만 lock directory가 중복 실행을 차단한다.
- 현재 브랜치가 `main`이 아니면 중단한다.
- tracked working tree 또는 index가 dirty면 중단한다.
- untracked `.env`, `docker-compose.nas.yml`, JSONL logs, generated BoI runtime 문서는 허용한다.
- non fast-forward 상태에서는 중단하고 `git reset --hard`나 `git clean`을 실행하지 않는다.
- `.env` 내용과 `SERVICE_TOKEN`은 출력하지 않는다.
- 중복 실행은 lock directory로 차단한다.

# Smart Restart Policy

다음 변경만 있으면 compose 재기동을 건너뛴다.

```text
data/boi/**
data/event_catalog/**
data/action_catalog/**
docs/**
README.md
```

그 외 변경이 하나라도 포함되면 runtime 변경으로 보고 NAS compose를 재생성한 뒤 다음 명령을 실행한다.

```bash
sudo env PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  /usr/local/bin/docker-compose \
  -f docker-compose.nas.yml \
  --env-file .env \
  up -d --build
```

`docker-compose.nas.yml`은 Git에 commit하지 않는다. 스크립트가 `docker-compose.yml`에서 top-level `name:`을 제거하고 `service_completed_successfully`를 `service_started`로 치환해 생성한다.

Synology Docker WebAPI는 package 버전마다 기능이 다르다. `SYNO.Docker.Container`가 container start/stop/list 일부를 지원하더라도 Compose project build/recreate를 제공하지 않는 Docker package가 있다. 이 경우 DSM API만으로 Python/JS/CSS 변경을 반영할 수 없고, root Scheduled Task 또는 SSH sudo로 `docker-compose up -d --build`를 실행해야 한다.

# Runtime Revision Verification

Compose 재생성 후 스크립트는 NAS 내부에서 `/api/runtime/config`를 호출해 실행 중인 `build.revision`이 방금 pull한 Git short SHA와 같은지 확인한다.

```text
git rev-parse --short HEAD
curl -fsS http://127.0.0.1:28000/api/runtime/config
```

revision이 다르면 `DEPLOY_STATUS=failed`로 끝난다. 이 검증은 “이미지 빌드는 성공했지만 오래된 `.env` 값 때문에 앱이 이전 revision을 표시하는” 문제를 잡기 위한 필수 gate다. NAS가 cache warmup 중에는 connection reset 또는 empty reply를 낼 수 있으므로 기본 대기 시간은 90회, 2초 간격이다.

# Compose v1 Recovery

Synology Docker package의 Compose v1은 `up -d --build` 중 오래된 container id를 참조하면서 `No such container` 계열 오류를 낼 수 있다. 이때 새 컨테이너가 `Created` 상태로 남아 있으면 애플리케이션은 거의 준비된 상태지만 시작만 누락된다.

자동 배포 스크립트는 compose 실패 시 다음 서비스를 label 기준으로 조회하고, `Created` 상태 컨테이너가 있으면 직접 `docker start`로 복구한다.

```text
boi-api action-gateway event-router boi-wiki-mcp langflow
```

복구 후에도 runtime revision verification을 통과해야만 성공으로 처리한다. `Created` 컨테이너가 없거나 revision 검증이 실패하면 자동화는 실패로 남기고 수동 점검 대상으로 둔다.

# Manual Verification

NAS 내부에서 먼저 확인한다.

```bash
curl -fsS http://127.0.0.1:28000/health
curl -fsS http://127.0.0.1:28200/health
```

외부 노출도 별도로 확인한다. 내부 확인은 성공하지만 외부 확인이 실패하면 애플리케이션 장애가 아니라 방화벽, 포트 포워딩, reverse proxy 노출 문제일 수 있다.

상단 메뉴는 `BOI_EXTERNAL_URL` 또는 현재 접속 Host를 기준으로 같은 도메인의 NAS fallback 포트를 추론한다. `http://wiki.example.internal:28000`으로 BoI Wiki에 접속하면 기본 메뉴 링크는 Langflow `:27860`, Kafka UI `:28081`, Action Gateway `:28100`, MCP Status `:28200`을 가리킨다. 실제 포트 포워딩이 다르면 `.env`의 `LANGFLOW_EXTERNAL_URL`, `KAFKA_UI_EXTERNAL_URL`, `ACTION_GATEWAY_EXTERNAL_URL`, `BOI_WIKI_MCP_EXTERNAL_URL`을 명시한다.

# Troubleshooting

| Symptom | Action |
|---|---|
| `DEPLOY_STATUS=blocked` and dirty worktree | tracked 파일의 수동 수정 여부를 확인하고 필요한 변경은 commit 또는 stash 후 재실행 |
| branch mismatch | `/volume1/docker/boi-wiki/app`에서 `git branch --show-current` 확인 후 `main`으로 전환 |
| non fast-forward | NAS에 로컬 commit이 생겼는지 확인. 자동화는 destructive reset을 하지 않음 |
| compose command not found | Synology Docker package PATH와 `/usr/local/bin/docker-compose` 존재 여부 확인 |
| git pull succeeded but external revision is old | image rebuild/recreate가 안 된 상태다. `/api/runtime/config`의 `build.revision`이 Git HEAD와 다르면 배포 미완료로 처리 |
| SSH login succeeds but `sudo` fails | 현재 계정의 sudo/admin password 또는 sudo 권한을 확인. Docker daemon 접근이 막히면 runtime code 배포 불가 |
| DSM login succeeds but root task creation fails | `SYNO.Core.TaskScheduler.Root` API 노출 여부와 root task 생성 권한을 확인. 일반 TaskScheduler가 `owner=root` 생성에서 권한 오류를 반환하면 DSM API fallback 불가 |
| DSM Docker API exists but compose build unavailable | Docker API start/stop만으로는 새 image가 만들어지지 않는다. root Scheduled Task 또는 SSH sudo compose 경로로 전환 |
| runtime revision mismatch | `.env`의 `BOI_BUILD_REVISION`이 Git HEAD와 맞는지 확인하고 자동 배포 스크립트를 재실행 |
| `No such container` during compose up | 자동 스크립트가 `Created` 컨테이너를 시작하고 revision을 재검증한다. 복구 실패 시 `docker ps -a --filter label=com.docker.compose.service=boi-api`로 상태 확인 |
| external URL timeout | NAS 내부 curl이 성공하는지 먼저 확인한 뒤 router/firewall/reverse proxy 점검 |

# Citations

- [NAS SERVICE_TOKEN 운영 절차](/public/boi-wiki-manual/operations/nas-service-token-rotation.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
