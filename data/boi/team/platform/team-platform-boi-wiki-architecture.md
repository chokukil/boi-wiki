---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: BoI Wiki Architecture Deep Dive
description: boi-wiki 공유 런타임의 서비스, 데이터, 권한, 이벤트, 커넥터, MCP/Langflow 연동 구조 상세 설명
tags: [BoIWiki, Architecture, Platform, EventBroker, ActionGateway, MCP, Langflow]
timestamp: 2026-06-20T18:29:45+09:00
boi_id: boi:team:platform:boi-wiki-architecture-v0.1
visibility: team
team_id: platform
classification: internal
owner: platform-team
author:
  type: agent
  agent_id: codex
acl_policy: acl:team:platform
status: reviewed
source_refs:
  - type: repo
    ref: README.md
  - type: architecture-doc
    ref: docs/CONNECTOR_AGNOSTIC_ARCHITECTURE_V0_4.md
  - type: architecture-doc
    ref: docs/V0_4_PEER_CONNECTOR_MODEL.md
  - type: architecture-doc
    ref: docs/V0_4_FULL_DOCUMENTATION_KR.md
  - type: compose
    ref: docker-compose.yml
  - type: compose
    ref: docker-compose.sso-dev.yml
  - type: code
    ref: boi_api/app/main.py
  - type: code
    ref: action_gateway/app/main.py
  - type: code
    ref: event_adapter/app/main.py
  - type: code
    ref: boi_wiki_mcp/app/main.py
  - type: catalog
    ref: data/action_catalog/actions.yaml
  - type: catalog
    ref: data/event_catalog/event_types.yaml
review:
  reviewer: platform-lead
  reviewed_at: 2026-06-20T18:29:45+09:00
  review_status: reviewed
---

# Summary

BoI Wiki는 OKF Markdown 문서를 source of truth로 삼고, Kafka Event Broker, Event Router, Action Gateway, BoI API/Web UI, BoI Wiki MCP, Langflow를 묶어 AI Native Workflow를 실행하는 공유 런타임이다.

핵심 설계는 다음 한 줄로 요약된다.

```text
Business Event -> Kafka Event Broker -> Event Router -> Action Gateway -> Peer Connector Actions -> BoI Wiki / Action Log / Next Event
```

이 구조에서 Langflow는 유일한 실행 경로가 아니다. BoI Writer, Langflow, HTTP API, Webhook, MCP bridge, Manual handoff, Event publish는 모두 Action Gateway 아래의 동등한 Peer Connector다. Event Router는 어떤 커넥터가 주 경로인지 판단하지 않고, event type을 Action Gateway로 넘긴다.

# Architecture Principles

| Principle | Meaning |
|---|---|
| Event Type first | 업무 시점은 Kafka topic이나 특정 flow id가 아니라 `event_type`으로 표현한다. |
| Peer Connector model | Langflow, API, Webhook, MCP, BoI Writer, Event Publish, Manual action은 모두 같은 catalog 모델로 등록한다. |
| Router is protocol-neutral | Event Router는 Kafka consume, audit, dispatch만 담당하고 실행 프로토콜을 모른다. |
| Gateway controls execution | URL allowlist, dry-run, approval, connector invocation, action log는 Action Gateway가 담당한다. |
| Wiki is workflow memory | SOP, 판단 근거, event-linked BoI, action spec, workflow 상태를 OKF 문서와 로그로 축적한다. |
| Markdown is source of truth | `data/boi`, `data/event_catalog`, `data/action_catalog`가 curated source이며 Web/MCP는 이를 검증 후 수정한다. |
| ACL follows identity | public/team/private visibility와 사번, 팀, role을 함께 평가한다. |

# Runtime Services

| Service | Container | Port | Main responsibility |
|---|---|---:|---|
| BoI API / Web Wiki | `boi-api` | 8000 | 문서 검색/렌더링, Event 발행, Webhook 수신, BoI materialization, workflow start/status, source edit validation |
| Action Gateway | `boi-action-gateway` | 8100 | Action Catalog 기반 connector 실행, allowlist/approval/dry-run 통제, action log 기록 |
| Event Router | `boi-event-router` | internal | Kafka `boi.events` consume, Event Stream audit, Action Gateway dispatch, DLQ 처리 |
| Kafka | `boi-kafka` | 9094 external | 업무 event backbone |
| Kafka Init | `boi-kafka-init` | internal | `boi.events`, `boi.audit`, `boi.dead-letter` topic 생성 |
| Kafka UI | `boi-kafka-ui` | 8081 | topic/message 운영 확인 |
| BoI Wiki MCP | `boi-wiki-mcp` | 8200 | agent-facing MCP Streamable HTTP server와 Action Gateway bridge endpoint |
| Langflow | `boi-langflow` | 7860 | Agent Builder 실행 채널, BoI custom components 실행 |
| Langflow Postgres | `boi-langflow-postgres` | internal | Langflow metadata 저장 |
| Keycloak / Mock HCP | SSO overlay | 8088 / 8300 | SSO dev mode의 identity와 project permission simulation |

# Data Layout

```text
data/
  boi/
    public/              # 전체 사용자와 agent가 읽을 수 있는 SOP, manual, action spec
    team/{team_id}/      # 팀 ACL로 제한된 Team BoI
    private/{employee}/  # Web 런타임이 관리하는 사용자별 Private BoI
  event_catalog/
    event_types.yaml     # 업무 event type catalog
  action_catalog/
    actions.yaml         # 실행 가능한 connector action catalog
  events/
    events-YYYYMMDD.jsonl
  actions/
    actions-YYYYMMDD.jsonl
```

`data/boi` 아래 Markdown 문서는 YAML frontmatter와 body로 구성된다. Web UI와 MCP는 이 frontmatter를 읽어 BoI ID, visibility, title, tags, source refs, review status, event type, workflow metadata를 구성한다.

Team/Public 문서는 최소한 `source_refs`와 `review` metadata가 있어야 한다. 이 문서는 Platform 팀 문서이므로 `visibility: team`, `team_id: platform`, `acl_policy: acl:team:platform`을 사용한다.

# BoI API / Web Wiki

BoI API는 사람이 보는 Web Wiki와 agent/runtime이 호출하는 API surface를 동시에 제공한다.

| Area | Important routes | Responsibility |
|---|---|---|
| Library | `/`, `/api/boi`, `/docs/{boi_id}` | 접근 가능한 OKF Markdown 문서 검색, 렌더링, 상세 조회 |
| Graph | `/api/okf/graph`, `/api/okf/graph/doc/{boi_id}` | Markdown 링크 기반 outgoing/backlink graph 생성 |
| Source editing | `/api/source/preview`, `/api/source/apply`, `/api/docs/{boi_id}/body-preview`, `/api/docs/{boi_id}/body-apply` | frontmatter/body 검증, OKF lint, stale SHA 방지, apply 후 auto-commit |
| Event | `/api/events/publish`, `/api/events/log`, `/api/events/raw/{log_ref}`, `/api/events/audit` | 업무 event 발행, Event Stream 조회, Event Router audit mirror |
| BoI materialization | `/api/boi/materialize-event`, `/api/boi/from-event`, `/api/events/handle` | event payload를 event-linked BoI 문서로 생성 |
| Workflow | `/api/workflows/{workflow_key}/start`, `/api/workflows/{workflow_key}/status` | SOP metadata 기반 config-driven workflow 실행/상태 조회 |
| Action facade | `/api/actions/catalog`, `/api/actions/invoke`, `/api/actions/logs` | Web에서 Action Catalog와 Action Gateway를 확인/호출 |
| Inbound webhook | `/api/webhooks/{source}` | 외부 시스템 event를 BoI event로 변환해 발행 |
| Auth | `/auth/login`, `/auth/callback`, `/auth/logout`, `/api/auth/me` | dev/keycloak/trusted-header identity 처리 |

BoI API는 문서를 DB에 복제하지 않는다. `DATA_ROOT` 아래 Markdown 파일을 스캔하고 캐시하며, 파일 signature가 바뀌면 문서 캐시와 graph cache를 무효화한다.

# Access Model

권한 판단은 identity와 OKF metadata를 함께 본다.

| Visibility | Read rule | Notes |
|---|---|---|
| `public` | 인증된 사용자 전체 | SOP, manual, action spec, event type 설명에 사용한다. |
| `team` | identity의 team 목록에 `team_id`가 있어야 함 | `metadata.team_id`가 없으면 경로 `/team/{team_id}`에서 추론한다. |
| `private` | `/private/{employee_id}`와 요청 사번이 일치해야 함 | Local Private workspace는 Web Wiki가 scan하지 않는다. |

개발 모드 기본 사번 매핑은 다음과 같다.

| Employee | Teams | Roles |
|---|---|---|
| `100001` | `aix-tf`, `platform` | admin 포함 dev roles |
| `100002` | `aix-tf` | viewer/editor/promoter/workflow/action roles |
| `100003` | `platform` | viewer/editor/promoter/workflow/action roles |

운영/SSO 모드에서는 Keycloak OIDC와 HCP permission API가 identity source다. 자세한 권한 운영 기준은 [SSO and Permission Model](/public/boi-wiki-manual/security/sso-and-permissions.md)을 따른다.

# Event Broker And Event Router

Kafka는 업무 event backbone이다. 기본 topic은 [Platform Team Kafka Event Broker SOP](/team/platform/team-platform-kafka-sop.md)에 정리된 세 개다.

| Topic | Use |
|---|---|
| `boi.events` | 업무 event input |
| `boi.audit` | 처리 완료 audit |
| `boi.dead-letter` | 처리 실패 event |

Event Router의 책임은 의도적으로 좁다.

1. `boi.events`에서 event를 consume한다.
2. BoI API `/api/events/audit`로 Event Stream에 `routing` 상태를 기록한다.
3. Action Gateway `/api/actions/dispatch`를 호출한다.
4. BoI API `/api/boi/enrich-from-dispatch`로 생성된 BoI를 action 결과와 연결한다.
5. 성공 시 `boi.audit`와 Event Stream에 `processed`를 기록한다.
6. 실패 시 `boi.dead-letter`와 Event Stream에 `failed`를 기록한다.

Event Router는 Langflow, API, MCP, BoI Writer 중 무엇을 우선 실행할지 판단하지 않는다. 실행 대상과 순서는 Action Catalog의 `event_types`, `enabled`, `auto_dispatch`, `order`가 결정한다.

# Event Type Catalog

업무 시점은 `data/event_catalog/event_types.yaml`에 정의한다.

| Event Type | Workflow meaning | Default BoI type |
|---|---|---|
| `meeting.closed.v1` | 회의 종료 후 회의록/결정사항/Action Item 정리 | `boi/meeting` |
| `action.created.v1` | 담당자별 Action Item 생성 | `boi/action` |
| `report.requested.v1` | 보고 초안 생성 요청 | `boi/report` |
| `promotion.requested.v1` | Private BoI의 Team/Public 공유 요청 | `boi/reference` |
| `equipment.alarm.raised.v1` | 설비 이상 SOP 시작 | `boi/sop-instance` |
| `trend.anomaly.detected.v1` | Trend 이상으로 원인 분석 필요 | `boi/analysis` |
| `root_cause.analysis.requested.v1` | 원인 분석 Agent 실행 시점 | `boi/analysis` |
| `maintenance.guide.requested.v1` | 보전 가이드/Runbook 조회 시점 | `boi/runbook` |
| `corrective_action.requested.v1` | 담당자 조치 또는 고위험 조치 후보 생성 | `boi/action` |
| `external.webhook.received.v1` | 외부 Webhook 수신 | `boi/reference` |

Event Type Catalog는 Event Broker의 Kafka topic보다 업무 친화적인 layer다. Kafka topic은 transport이고, `event_type`은 업무 의미다.

# Action Gateway

Action Gateway는 connector abstraction layer다. `data/action_catalog/actions.yaml`을 읽어 event type별 자동 실행 action을 정렬하고 실행한다.

Dispatch 흐름은 다음과 같다.

1. `/api/actions/dispatch`가 `event.event_type`을 받는다.
2. `actions_for_event(event_type)`가 `enabled: true`, `auto_dispatch: true`, event type match인 action을 고른다.
3. `order`와 `action_key` 기준으로 실행 순서를 정한다.
4. 각 action마다 template 변수 `${event.*}`, `${payload.*}`, `${employee_id}`, `${prior_results_json}`를 렌더링한다.
5. connector type별로 BoI API, Langflow, HTTP API, Webhook, MCP bridge, Event publish, Manual task를 실행한다.
6. 결과와 error를 `data/actions/actions-YYYYMMDD.jsonl`에 기록한다.
7. materialized BoI가 생기면 후속 action에 `boi_id`로 전달한다.

지원 connector type은 다음과 같다.

| Type | Connector kind | Runtime behavior |
|---|---|---|
| `boi_materialize` | `boi_writer` | BoI API `/api/boi/materialize-event` 호출 |
| `api`, `http` | `api` | allowlisted REST endpoint 호출 |
| `webhook`, `internal_webhook` | `webhook` | generic webhook 호출 또는 inbound webhook spec |
| `langflow_webhook` | `langflow` | Langflow webhook endpoint 호출 |
| `langflow_run` | `langflow` | Langflow flow list에서 조건에 맞는 최신 flow resolve 후 `/api/v1/run/{flow}` 호출 |
| `event_publish`, `boi_event` | `event_broker` | BoI API `/api/events/publish`를 통해 다음 Kafka event 발행 |
| `mcp_tool`, `mcp_bridge` | `mcp` | MCP bridge endpoint로 tool invocation 위임 |
| `manual_task` | `manual` | 사람이 해야 할 handoff/checklist를 action result로 기록 |
| `mock_api` | `mock` | PoC용 mock response |

고위험 action은 `approval_required: true`와 `requires_manual_action`을 사용한다. 승인자가 없으면 Gateway는 실제 실행 대신 `approval_required` 결과를 반환하고 action log에 남긴다.

# BoI Writer Connector

BoI Writer는 fallback이 아니다. Event를 조직 지식으로 자산화하는 1급 connector다.

`boi.materialize_event` action은 모든 event type에 대해 기본 `order: 10`으로 등록되어 있다. 이 action은 Event Router가 받은 event를 BoI API로 전달하고, BoI API는 event type에 맞는 `boi/meeting`, `boi/action`, `boi/report`, `boi/sop-instance`, `boi/analysis`, `boi/runbook`, `boi/reference` 문서를 생성한다.

결과적으로 같은 event에서 다음 일이 동시에 일어날 수 있다.

- BoI Writer가 event-linked Private BoI를 만든다.
- API connector가 Trend/Raw Data를 조회한다.
- Langflow connector가 분석 초안을 만든다.
- Event Publish connector가 다음 stage event를 발행한다.
- Manual connector가 사람이 검토할 handoff를 남긴다.

# SOP Workflow Model

SOP는 단순 문서가 아니라 workflow metadata를 포함할 수 있다. [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)는 대표 예시다.

SOP frontmatter의 `workflow` 블록은 다음 구조를 가진다.

```yaml
workflow:
  workflow_key: equipment-anomaly
  stages:
    - id: detect
      entry_event: equipment.alarm.raised.v1
      emits_event: root_cause.analysis.requested.v1
      automated_actions:
        - sop.equipment.request_trend_history
        - sop.equipment.request_raw_data
      manual_actions:
        - manual.equipment.confirm_alarm_context
```

BoI API는 이 metadata를 읽어 workflow registry를 구성하고 `/api/workflows/{workflow_key}/start`, `/api/workflows/{workflow_key}/status`에서 stage, event, action result, generated BoI, manual handoff를 연결해 보여준다.

# MCP Architecture

BoI Wiki MCP는 agent-facing 표준 인터페이스다. agent가 BoI API route를 직접 외우지 않고도 BoI 문서, action, workflow, source edit, promotion을 사용할 수 있게 한다.

| Endpoint | Use |
|---|---|
| `http://localhost:8200/` | 사람이 보는 MCP status page |
| `http://localhost:8200/mcp` | MCP Streamable HTTP endpoint |
| `http://localhost:8200/api/mcp/call` | Action Gateway bridge 호환 endpoint |
| `http://localhost:8200/health` | health/status JSON |

노출 capability는 다음 범주다.

| Category | Examples |
|---|---|
| Search/read | `boi_search`, `boi_get`, `okf_graph_doc` |
| Action | `actions_search`, `action_get`, `action_invoke` |
| Workflow | `workflow_start`, `workflow_status` |
| Validated editing | `source_preview`, `source_apply`, `doc_body_preview`, `doc_body_apply` |
| Promotion | `promotion_submit`, `promotion_status` |
| Resource templates | `boi://docs/{boi_id}`, `boi://actions/{action_key}`, `boi://workflows/{workflow_key}/status/{trace_id}` |
| Prompts | `create_sop_from_source`, `author_action_spec`, `build_langflow_boi_flow` |

MCP registration and troubleshooting are documented in [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md).

# Langflow Integration

Langflow는 Agent Builder 실행 채널이며, BoI custom components가 repo에 포함되어 있다.

| Component | Responsibility |
|---|---|
| `BoIContextNormalizer` | Event payload, run input message, manual input을 공통 WorkContext로 정규화 |
| `BoIHarnessLoader` | BoI agent harness rule을 flow에 주입 |
| `BoIWikiReader` | BoI API `/api/boi`를 호출해 권한 내 문서 검색 |
| `BoIMetadataBuilder` | OKF/SK hynix BoI frontmatter 생성 |
| `BoIPolicyGuard` | metadata 필수값, visibility, Team/Public source/reviewer guardrail 검증 |
| `BoIWikiWriter` | BoI API `/api/boi`로 문서 작성 |
| `BoIActionInvoker` | Action Gateway `/api/actions/invoke`로 allowlisted action 호출 |
| `BoIResultComposer` | LLM 분석, validation, write result, action result를 최종 message로 합성 |

Langflow action은 catalog에서 `langflow_run` 또는 `langflow_webhook`으로 등록된다. 현재 `langflow_run` action은 flow name, required model, required marker로 최신 flow를 resolve하고, OpenAI-compatible Gemma LLM endpoint를 사용하도록 구성되어 있다.

Langflow 연결 가이드는 [Langflow connected flow guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)를 따른다.

# Source Editing And Promotion

Web/MCP source edit는 직접 파일을 쓰기 전에 검증한다.

1. 대상 파일의 `base_sha256`을 확인해 stale edit를 막는다.
2. Markdown/YAML 문법과 OKF metadata를 검증한다.
3. `data/boi` 후보 tree에서 OKF lint, strict link, strict media 검증을 수행한다.
4. 검증 실패 시 원본 파일은 바꾸지 않고 fix suggestion을 반환한다.
5. 검증 성공 시 파일을 적용하고 post-apply validation을 다시 수행한다.
6. 성공하면 해당 파일만 Git commit한다.
7. post-apply validation 또는 commit 실패 시 원본을 rollback한다.

Team/Public promotion은 source/body edit와 별도 경로다. 사용자 preview 승인이 있어야 하며, promotion candidate는 `source_refs`, reviewer, user confirmation, HOTL metadata를 포함해 즉시 게시된다. 관련 운영 기준은 [Web edit와 Git commit 정책](/public/boi-wiki-manual/operations/draft-and-git-policy.md)과 [BoI Agent Harness Overview](/public/harness/overview.md)을 따른다.

# Deployment Modes

| Mode | Command | Purpose |
|---|---|---|
| Local dev | `docker compose up -d --build` | dev auth, query `employee_id`, local Kafka/Langflow/MCP/API |
| SSO dev | `docker compose -f docker-compose.yml -f docker-compose.sso-dev.yml up -d --build` | Keycloak/HCP style auth path 검증 |
| NAS / external URL | `.env`의 `BOI_EXTERNAL_URL`, `*_EXTERNAL_URL` 설정 | 외부 노출 URL과 Docker internal URL 분리 |

중요한 운영 원칙은 내부 service URL과 외부 사용자 URL을 분리하는 것이다. `actions.yaml`의 `http://boi-api:8000`, `http://langflow:7860`, `http://boi-wiki-mcp:8200` 같은 값은 container network 내부 호출용이므로 외부 도메인으로 바꾸지 않는다.

# Validation Checklist

변경 후 최소 검증은 다음 순서가 적합하다.

```bash
python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
pytest tests -q -s
```

Langflow flow나 SOP runtime을 바꾸는 경우에는 다음도 추가한다.

```bash
python scripts/audit_langflow_flows.py
python scripts/run_equipment_sop_poc.py
```

# Extension Guide

새 연동 방식을 추가할 때는 Event Router를 수정하지 않는 것이 원칙이다.

| Need | Preferred change |
|---|---|
| 새 사내 API 호출 | `data/action_catalog/actions.yaml`에 `type: api` action 추가 |
| 새 webhook 실행 | `type: webhook` 또는 `internal_webhook` action 추가 |
| 새 MCP tool 호출 | `type: mcp_tool` action과 bridge 설정 추가 |
| 새 Agent Builder flow | `type: langflow_run` 또는 `langflow_webhook` action 추가 |
| 새 업무 시점 | `data/event_catalog/event_types.yaml`에 event type 추가 |
| 새 SOP workflow | Public/Team SOP frontmatter에 `workflow.stages` 추가 |
| 새 지식 문서 | OKF frontmatter를 가진 Markdown 문서를 `data/boi` 아래 추가 |

Action spec 작성 기준은 [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)와 [Public Action Library](/public/actions/overview.md)를 따른다.

# Operational Risks

| Risk | Control |
|---|---|
| Langflow를 주 경로로 오해 | 모든 문서와 catalog에서 Peer Connector 모델을 유지한다. |
| Router에 protocol-specific logic이 늘어남 | 새 실행 방식은 Action Gateway connector type 또는 bridge로 추가한다. |
| Team/Public 문서의 출처 불명확 | `source_refs`, `review`, HOTL metadata를 필수로 유지한다. |
| 고위험 action 자동 실행 | `approval_required`, `requires_manual_action`, dry-run default를 유지한다. |
| 내부 URL을 외부 URL로 변경 | Docker service URL과 external URL env를 분리한다. |
| MCP `/mcp`를 브라우저로 검증 | status page 또는 `scripts/check_boi_wiki_mcp.py`를 사용한다. |
| Local Private 유출 | Web Wiki는 `boi-wiki-local` workspace를 scan하지 않는다. 공유는 promotion path만 사용한다. |

# Related Wiki Pages

- [Platform Team Kafka Event Broker SOP](/team/platform/team-platform-kafka-sop.md)
- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [SSO and Permission Model](/public/boi-wiki-manual/security/sso-and-permissions.md)
- [BoI Agent Harness Overview](/public/harness/overview.md)
- [Public Action Library](/public/actions/overview.md)
