# BoI PoC Kit v0.4 전체 문서

## 0. 문서 목적

이 문서는 `boi-poc-kit-v0.4`를 사내 PoC 환경으로 이관하고, Docker Compose 기반으로 실제 실행·검증하기 위한 전체 설명서다. v0.4의 핵심은 **Langflow를 유일한 실행 경로로 두지 않고, BoI Writer, Langflow, API, Webhook, MCP, 향후 신규 프로토콜을 모두 동등한 Connector로 다루는 구조**다.

v0.4에서는 `fallback` 개념을 사용하지 않는다. BoI API는 Langflow가 없을 때 쓰는 보조 경로가 아니라, 업무 Event를 조직 지식으로 자산화하는 **BoI Writer Connector**다. Langflow 역시 여러 실행 채널 중 하나다. API, Webhook, MCP도 동일한 Action Gateway 아래에서 동등하게 호출된다.

---

## 1. v0.4 핵심 요약

### 1.1 한 문장 정의

> **Event Broker가 업무 Event를 전달하고, Event Router가 이를 Action Gateway로 넘기며, Action Gateway가 BoI Writer, Langflow, API, Webhook, MCP 등 동등한 Connector를 실행하고, BoI Wiki가 SOP·판단 근거·실행 결과를 조직 지식으로 축적하는 AI Native Workflow PoC다.**

### 1.2 설계 철학

```text
실행 채널은 바뀔 수 있다.
하지만 Event Type과 BoI Wiki는 유지된다.
```

구성원이 Langflow로 Agent를 만들 수도 있고, 기존 시스템 API를 호출할 수도 있으며, Webhook으로 외부 시스템을 깨울 수도 있다. 향후 MCP 기반 Tool/Resource/Prompt 호출이 들어와도 Event Broker, Event Type Catalog, BoI Wiki 모델은 그대로 유지된다.

### 1.3 v0.3 대비 가장 큰 변경점

| 항목 | v0.3 | v0.4 |
|---|---|---|
| 실행 모델 | Langflow 우선처럼 보일 수 있음 | 모든 실행 대상이 Peer Connector |
| BoI API 역할 | 보조 경로처럼 표현될 여지 있음 | BoI Writer Connector, 1급 실행 채널 |
| Event Adapter | 일부 실행 채널 선택 로직 보유 | Event Router로 단순화 |
| 실행 제어 | Adapter 내부 분기 | Action Gateway + Action Catalog |
| 확장 방식 | Flow ID / API 분기 중심 | Connector Type 추가 중심 |
| MCP | 향후 고려 | Action Gateway의 Extension Point로 명시 |
| 문서 표현 | fallback 가능성 존재 | fallback 표현 제거 |

---

## 2. 전체 아키텍처

### 2.1 논리 구조

```text
[Business Event Producer]
- 사람
- Agent
- Langflow Flow
- 사내 업무 시스템
- 외부 Webhook
- API Client
        │
        │ 업무 Event 발행
        ▼
[Kafka Event Broker]
- boi.events
- boi.audit
- boi.dead-letter
        │
        ▼
[Event Router]
- Kafka event consume
- 이벤트 상태 audit
- Action Gateway dispatch 호출
        │
        ▼
[Action Gateway]
- Action Catalog 조회
- Connector별 실행
- allowlist / approval / dry-run 통제
- action log 기록
        │
        ├─ BoI Writer Connector
        ├─ Langflow Webhook Connector
        ├─ HTTP API Connector
        ├─ Generic Webhook Connector
        ├─ Event Publish Connector
        ├─ MCP Bridge Connector
        └─ Future Connector
        │
        ▼
[BoI Wiki / Action Logs / Next Events]
- SOP
- Event-linked BoI
- Private / Team / Public 문서
- Event Stream
- Action 실행 이력
```

### 2.2 서비스 구성

| 서비스 | 컨테이너 | 포트 | 역할 |
|---|---|---:|---|
| BoI API / Web Wiki | `boi-api` | 8000 | BoI Wiki Web UI, BoI API, Event 발행, Webhook 수신, Event Stream |
| Action Gateway | `boi-action-gateway` | 8100 | Connector Action 실행 허브 |
| Event Router | `boi-event-router` | - | Kafka Event를 Action Gateway로 dispatch |
| Kafka | `boi-kafka` | 9094 | 실제 Event Broker |
| Kafka Init | `boi-kafka-init` | - | Topic 생성 |
| Kafka UI | `boi-kafka-ui` | 8081 | Kafka Topic/Message 확인 |
| Langflow | `boi-langflow` | 7860 | Agent Flow Builder 및 Langflow Webhook 실행 채널 |
| Langflow Postgres | `boi-langflow-postgres` | - | Langflow 영속 저장소 |

### 2.3 주요 URL

| 화면/서비스 | URL |
|---|---|
| BoI Wiki | `http://localhost:8000/?employee_id=100001` |
| BoI 문서 목록 API | `http://localhost:8000/api/boi?employee_id=100001` |
| Event Type Catalog | `http://localhost:8000/event-types?employee_id=100001` |
| Event Stream | `http://localhost:8000/events?employee_id=100001` |
| Action Catalog 화면 | `http://localhost:8000/actions?employee_id=100001` |
| BoI API Docs | `http://localhost:8000/docs` |
| Action Gateway API Docs | `http://localhost:8100/docs` |
| Action Gateway Logs | `http://localhost:8100/api/actions/logs` |
| Kafka UI | `http://localhost:8081` |
| Langflow | `http://localhost:7860` |

---

## 3. Quick Start

### 3.1 사전 조건

- Docker
- Docker Compose
- 인터넷이 차단된 사내 환경이라면 필요한 image 사전 pull 또는 사내 registry mirror 필요

### 3.2 실행

```bash
cd boi-poc-kit-v0.4
cp .env.example .env

docker compose up -d --build
```

### 3.3 상태 확인

```bash
docker compose ps
```

주요 서비스가 `running` 또는 `healthy` 상태인지 확인한다.

```bash
curl http://localhost:8000/health
curl http://localhost:8100/health
```

### 3.4 종료

```bash
docker compose down
```

데이터까지 삭제하려면 다음을 사용한다.

```bash
docker compose down -v
```

---

## 4. v0.4 디렉터리 구조

```text
boi-poc-kit-v0.4/
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ boi_api/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ app/
│     ├─ main.py
│     ├─ templates/
│     │  ├─ index.html
│     │  ├─ doc.html
│     │  ├─ event_types.html
│     │  ├─ events.html
│     │  └─ actions.html
│     └─ static/
│        └─ style.css
├─ action_gateway/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ app/main.py
├─ event_adapter/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ app/main.py
├─ langflow/
│  └─ custom_components/boi/
│     ├─ boi_context_normalizer.py
│     ├─ boi_harness_loader.py
│     ├─ boi_metadata_builder.py
│     ├─ boi_policy_guard.py
│     ├─ boi_wiki_writer.py
│     ├─ boi_wiki_reader.py
│     └─ boi_action_invoker.py
├─ data/
│  ├─ boi/
│  │  ├─ public/
│  │  ├─ team/
│  │  └─ private/
│  ├─ event_catalog/
│  │  └─ event_types.yaml
│  ├─ action_catalog/
│  │  └─ actions.yaml
│  ├─ events/
│  └─ actions/
├─ scripts/
│  └─ publish_event.py
└─ docs/
   ├─ CONNECTOR_AGNOSTIC_ARCHITECTURE_V0_4.md
   ├─ MIGRATION_FROM_V0_3.md
   └─ V0_4_PEER_CONNECTOR_MODEL.md
```

---

## 5. 핵심 개념

## 5.1 Event Broker

Event Broker는 실제로 Kafka가 담당한다. Kafka는 업무 이벤트를 topic으로 전달하며, Event Router가 이를 consume한다.

PoC topic은 다음과 같다.

| Topic | 역할 |
|---|---|
| `boi.events` | 업무 Event 발행 topic |
| `boi.audit` | Event Router 처리 결과 audit topic |
| `boi.dead-letter` | Event 처리 실패 시 DLQ |

중요한 점은 Kafka topic 자체가 경영진이나 업무 사용자가 보는 업무 화면은 아니라는 점이다. 업무 사용자는 BoI Wiki의 Event Type Catalog와 Event Stream을 통해 이벤트 체계를 이해한다.

## 5.2 Event Type Catalog

Event Type Catalog는 “회사 업무에서 어떤 이벤트가 발생하는가”를 정의한다.

파일 위치:

```text
data/event_catalog/event_types.yaml
```

주요 Event Type은 다음과 같다.

| Event Type | 한글명 | 기본 BoI Type | Workflow Stage |
|---|---|---|---|
| `meeting.closed.v1` | 회의 종료 | `boi/meeting` | Staff/TF 업무 |
| `action.created.v1` | Action Item 생성 | `boi/action` | Staff/TF 업무 |
| `report.requested.v1` | 보고 요청 | `boi/report` | Staff/TF 업무 |
| `promotion.requested.v1` | BoI 승격 요청 | `boi/reference` | Knowledge Promotion |
| `equipment.alarm.raised.v1` | 설비 Alarm 발생 | `boi/sop-instance` | 이상 감지 |
| `trend.anomaly.detected.v1` | Trend 이상 감지 | `boi/analysis` | 원인 분석 |
| `root_cause.analysis.requested.v1` | 원인 분석 요청 | `boi/analysis` | 원인 분석 |
| `maintenance.guide.requested.v1` | 장비 보전 가이드 요청 | `boi/runbook` | 장비 보전 가이드 |
| `corrective_action.requested.v1` | 이상 조치 요청 | `boi/action` | 이상 조치 |
| `external.webhook.received.v1` | 외부 Webhook 수신 | `boi/reference` | Event Ingestion |

## 5.3 Action Catalog

Action Catalog는 특정 Event가 발생했을 때 어떤 Connector Action을 실행할지 정의한다.

파일 위치:

```text
data/action_catalog/actions.yaml
```

v0.4에서는 Action Catalog가 실행 채널 추상화의 중심이다. Event Router가 직접 Langflow나 BoI API를 선택하지 않는다. Event Router는 Action Gateway에 dispatch를 요청하고, Action Gateway가 Action Catalog를 기준으로 실행한다.

## 5.4 Action Gateway

Action Gateway는 Connector를 실행하는 Invocation Hub다.

주요 역할:

- Action Catalog 로드
- Event Type과 매칭되는 Action 선택
- Connector Type별 실행
- host allowlist 확인
- high-risk action dry-run / approval 통제
- action log 기록
- 실패 시 결과 반환 및 로그화

## 5.5 BoI Writer Connector

BoI Writer Connector는 업무 Event를 OKF 스타일 BoI 문서로 자산화한다. 이 Connector는 fallback이 아니다. Langflow, API, Webhook, MCP와 동등한 1급 실행 채널이다.

주요 endpoint:

```text
POST /api/boi/materialize-event
POST /api/boi/from-event
POST /api/boi/materialize-from-event
POST /api/events/handle
```

위 endpoint들은 v0.4에서 event materialization을 위한 호환 endpoint로 제공된다.

## 5.6 BoI Wiki

BoI Wiki는 사람과 Agent가 함께 활용하는 지식 표면이다.

BoI Wiki에 저장되는 것:

- Public SOP
- Team 문서
- Web/API/Langflow에서 생성한 Private BoI
- Event-linked BoI
- 회의, Action, 보고, SOP 실행 결과
- 설비 이상 대응 같은 workflow 단계별 판단 근거

Local Agent가 로컬에만 저장한 Private은 Web BoI Wiki에서 보이지 않는 것이 정상이다.

## 5.7 Langflow

Langflow는 사내 Agent Builder 실행 채널이다. v0.4에서는 Langflow가 유일한 실행 채널이 아니라, Action Gateway의 `langflow_webhook` Connector로 연결되는 여러 실행 채널 중 하나다.

Langflow에 mount되는 BoI 공통 컴포넌트:

| Component | 역할 |
|---|---|
| `BoI Context Normalizer` | Event 또는 입력을 BoI WorkContext로 정규화 |
| `BoI Harness Loader` | Agent Harness instruction 주입 |
| `BoI Metadata Builder` | BoI metadata/frontmatter 생성 |
| `BoI Policy Guard` | 저장/승격 전 정책 점검 |
| `BoI Wiki Writer` | BoI API로 문서 저장 |
| `BoI Wiki Reader` | 사번 기준 접근 가능한 BoI 조회 |
| `BoI Action Invoker` | Action Gateway의 Action 호출 |

## 5.8 MCP Extension Point

MCP는 v0.4에서 직접 완성 구현 대상은 아니지만, Action Gateway의 Connector Type으로 확장 지점을 마련했다.

의도한 구조:

```text
Event Router
  → Action Gateway
  → MCP Bridge Connector
  → Internal MCP Bridge
  → MCP Server
  → Tool / Resource / Prompt
```

새로운 프로토콜이 생기면 Event Router나 Kafka 구조를 고치지 않고 Action Gateway에 Connector Type을 추가한다.

---

## 6. 접근 제어 모델

## 6.1 Web BoI Wiki 조회 범위

사용자는 사번 기준으로 Web BoI Wiki에 접속한다.

```text
http://localhost:8000/?employee_id=100001
```

조회 범위:

| Visibility | 조회 기준 |
|---|---|
| Public | 모든 사용자 조회 가능 |
| Team | 사용자의 team membership 기준 조회 가능 |
| Private | Web/API/Langflow가 올린 본인 Private만 조회 가능 |
| Local Private | Web에서 미노출 |

## 6.2 PoC 사번/팀 예시

PoC 코드에는 임시 사용자/팀 매핑이 들어 있다.

| Employee ID | Team |
|---|---|
| `100001` | `aix-tf`, `platform` |
| `100002` | `aix-tf` |
| `100003` | `platform` |

## 6.3 Private-first 원칙

기본 저장은 Private이다. Team/Public 공유는 명시적 요청과 검토를 거쳐야 한다.

```text
Private 원본은 이동하지 않는다.
공유할 때는 Team/Public draft 사본을 새로 만든다.
```

---

## 7. Docker Compose 환경 변수

`.env.example` 주요 항목은 다음과 같다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LANGFLOW_IMAGE` | `langflowai/langflow:latest` | Langflow Docker image |
| `LANGFLOW_PORT` | `7860` | Langflow Web port |
| `LANGFLOW_API_KEY` | `dev-langflow-key-change-me` | Langflow API key |
| `LANGFLOW_AUTO_LOGIN` | `True` | PoC 편의용 자동 로그인 |
| `LANGFLOW_SUPERUSER` | `admin` | Langflow 관리자 계정 |
| `LANGFLOW_SUPERUSER_PASSWORD` | `admin` | Langflow 관리자 비밀번호 |
| `LANGFLOW_SECRET_KEY` | `Ym9pLXdpa2ktcG9jLWRldi1zZWNyZXQta2V5LTIwMjY=` | Langflow secret key |
| `BOI_API_PORT` | `8000` | BoI API / Wiki port |
| `KAFKA_EXTERNAL_PORT` | `9094` | Host에서 접근할 Kafka port |
| `KAFKA_UI_PORT` | `8081` | Kafka UI port |
| `SERVICE_TOKEN` | `dev-service-token-change-me` | 내부 API 호출 token |
| `DEFAULT_TEAM_ID` | `aix-tf` | 기본 Team ID |
| `DEMO_EMPLOYEE_ID` | `100001` | Demo 기본 사번 |
| `ACTION_GATEWAY_PORT` | `8100` | Action Gateway port |
| `ACTION_DRY_RUN_DEFAULT` | `true` | 기본 dry-run 여부 |
| `ACTION_ALLOWED_HOSTS` | `boi-api,langflow,action-gateway,localhost,127.0.0.1,mcp-bridge` | 호출 허용 host |
| `MCP_BRIDGE_URL` | empty | 향후 MCP bridge URL |
| `AUTO_ROUTE_EVENTS` | `true` | Event Router 자동 dispatch 여부 |

사내 이관 시 `LANGFLOW_API_KEY`, `SERVICE_TOKEN`, `LANGFLOW_SECRET_KEY`, 관리자 비밀번호는 반드시 교체한다.

---

## 8. 주요 API

## 8.1 BoI API / Wiki

### Health

```bash
curl http://localhost:8000/health
```

### BoI 목록 조회

```bash
curl "http://localhost:8000/api/boi?employee_id=100001"
```

필터 예시:

```bash
curl "http://localhost:8000/api/boi?employee_id=100001&event_type=equipment.alarm.raised.v1"
```

### BoI 생성

```bash
curl -X POST "http://localhost:8000/api/boi?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "type": "boi/reference",
      "title": "수동 BoI 예시",
      "description": "API로 생성한 Private BoI",
      "tags": ["manual", "poc"],
      "visibility": "private",
      "classification": "internal"
    },
    "body": "# Summary\n\n수동 생성 BoI 예시입니다."
  }'
```

### BoI 승격

```bash
curl -X POST "http://localhost:8000/api/boi/{BOI_ID}/promote?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "target_visibility": "team",
    "team_id": "aix-tf",
    "reviewer": "tf-lead",
    "promotion_reason": "PoC demo explicit promotion"
  }'
```

### Event 발행

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "meeting.closed.v1",
    "payload": {"title": "AIX 확산 TF 주간회의"},
    "source_refs": [{"type": "meeting_note", "ref": "/private/100001/meeting-notes/demo.md"}]
  }'
```

### 외부 Webhook 수신

```bash
curl -X POST "http://localhost:8000/api/webhooks/demo-system?employee_id=100001" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "event_type": "external.webhook.received.v1",
    "payload": {"title": "외부 시스템 Webhook 테스트"},
    "source_refs": [{"type": "webhook", "ref": "demo-system"}]
  }'
```

### Event Type 조회

```bash
curl http://localhost:8000/api/event-types
```

### Event Stream 조회

```bash
curl http://localhost:8000/api/events/log
```

### Event audit 기록

내부 서비스용 endpoint다.

```bash
curl -X POST "http://localhost:8000/api/events/audit" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "status": "processed",
    "event": {"event_id": "evt-demo", "event_type": "meeting.closed.v1"},
    "result": {"ok": true}
  }'
```

### Event를 BoI로 Materialize

BoI Writer Connector가 호출하는 endpoint다.

```bash
curl -X POST "http://localhost:8000/api/boi/materialize-event" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "event_id": "evt-demo-001",
    "event_type": "meeting.closed.v1",
    "event_version": "1",
    "occurred_at": "2026-06-16T15:00:00+09:00",
    "producer": "manual-test",
    "actor": {"type": "human", "employee_id": "100001"},
    "visibility_hint": "private",
    "classification_hint": "internal",
    "source_refs": [{"type": "manual", "ref": "curl"}],
    "payload": {"title": "Materialize Event 테스트"},
    "trace_id": "trace-demo-001"
  }'
```

---

## 8.2 Action Gateway API

### Health

```bash
curl http://localhost:8100/health
```

### Action 목록

```bash
curl http://localhost:8100/api/actions
```

### Action log 조회

```bash
curl http://localhost:8100/api/actions/logs
```

### 특정 Action invoke

```bash
curl -X POST "http://localhost:8100/api/actions/invoke" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "action_key": "sop.equipment.request_trend_history",
    "employee_id": "100001",
    "event": {"event_type": "equipment.alarm.raised.v1", "event_id": "evt-manual"},
    "payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001"}
  }'
```

### Event dispatch

```bash
curl -X POST "http://localhost:8100/api/actions/dispatch" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "employee_id": "100001",
    "event": {
      "event_id": "evt-dispatch-demo",
      "event_type": "equipment.alarm.raised.v1",
      "payload": {
        "title": "설비 Alarm 발생",
        "equipment_id": "ETCH-VM-01",
        "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
        "owner": "100001"
      }
    },
    "payload": {
      "equipment_id": "ETCH-VM-01",
      "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
      "owner": "100001"
    }
  }'
```

---

## 9. Connector Type 상세

## 9.1 `boi_materialize`

업무 Event를 BoI 문서로 자산화한다.

예시:

```yaml
- action_key: boi.materialize_event
  name_ko: Event를 BoI로 자산화
  type: boi_materialize
  enabled: true
  event_types: ["*"]
  risk_level: low
  approval_required: false
  dry_run_default: false
```

특징:

- 모든 Event Type에 적용 가능
- Event-linked BoI 생성
- Private-first 정책 반영
- `source_event`, `event_type`, `event_label` 메타데이터 포함

## 9.2 `langflow_webhook`

Langflow Webhook Flow를 호출한다.

```yaml
- action_key: langflow.boi.reference_flow
  type: langflow_webhook
  enabled: false
  auto_dispatch: false
  event_types: [meeting.closed.v1, action.created.v1, report.requested.v1]
  flow_id: replace-with-langflow-flow-id
  body:
    event: ${event}
    payload: ${payload}
```

활성화하려면:

1. Langflow에서 Flow 생성
2. Webhook endpoint 확인
3. `flow_id` 입력
4. `enabled: true` 및 필요 시 `auto_dispatch: true` 설정

## 9.3 `api` / `http`

사내 REST API를 호출한다.

예시:

```yaml
- action_key: fab.eqp.get_alarm_context
  type: api
  enabled: true
  event_types: [equipment.alarm.raised.v1]
  method: POST
  url: http://tas.internal/api/alarm-context
  body:
    equipment_id: ${payload.equipment_id}
    alarm_code: ${payload.alarm_code}
```

사내 이관 시 TAS, HyVIS, 설비, 품질, 승인, 알림 API를 이 방식으로 연결한다.

## 9.4 `webhook` / `internal_webhook`

범용 Webhook을 호출한다.

예시:

```yaml
- action_key: notify.team.webhook
  type: webhook
  enabled: true
  event_types: [corrective_action.requested.v1]
  method: POST
  url: http://notification.internal/webhook/action-requested
  body:
    event: ${event}
    payload: ${payload}
```

## 9.5 `event_publish`

다음 업무 Event를 Kafka에 발행한다.

예시:

```yaml
- action_key: sop.equipment.create_root_cause_event
  type: event_publish
  enabled: true
  event_types: [equipment.alarm.raised.v1]
  body:
    event_type: root_cause.analysis.requested.v1
    payload:
      title: 원인 분석 요청 - ${payload.equipment_id}
      equipment_id: ${payload.equipment_id}
```

이 Connector가 AI Native Workflow의 단계 전이를 만든다.

## 9.6 `mock_api`

PoC에서 사내 시스템 API를 시뮬레이션하기 위한 Connector다.

예시:

```yaml
- action_key: sop.equipment.request_trend_history
  type: mock_api
  enabled: true
  event_types: [equipment.alarm.raised.v1]
  mock_response:
    trend_status: anomaly_detected
    message: Trend와 이력 데이터를 확인했습니다.
```

사내 이관 시 실제 API Connector로 교체한다.

## 9.7 `mcp_tool` / `mcp_bridge`

MCP Bridge를 통해 MCP Server의 Tool/Resource/Prompt를 호출하는 확장 지점이다.

예시:

```yaml
- action_key: connector.mcp.sample
  type: mcp_bridge
  enabled: false
  event_types: [report.requested.v1]
  url: http://mcp-bridge:8200/api/mcp/call
  server:
    name: boi-wiki-mcp
  tool: search_boi
  arguments:
    query: ${payload.query}
    employee_id: ${employee_id}
```

사내 MCP Bridge가 준비되면 `MCP_BRIDGE_URL`과 action entry를 설정해 연결한다.

---

## 10. SOP 기반 AI Native Workflow

## 10.1 목표

첨부 SOP 사례처럼 실제 현장 업무는 이상 감지, 원인 분석, 장비 보전 가이드, 이상 조치 등 여러 판단·시스템·Agent 단계로 이루어진다. v0.4는 이 SOP를 실행 가능한 Event-driven Workflow로 표현한다.

```text
SOP 문서
  → Event Type 정의
  → Action Catalog 실행
  → BoI 결과 축적
  → 다음 Event 발행
  → 업무 단계 전개
```

## 10.2 설비 이상 대응 Workflow

```text
equipment.alarm.raised.v1
  → BoI Writer Connector
  → Trend / Raw Data API Connector
  → root_cause.analysis.requested.v1 발행
  → BoI Writer Connector
  → Maintenance Guide API/Webhook Connector
  → corrective_action.requested.v1 발행
  → BoI Writer Connector
  → 고위험 Action은 approval-required / dry-run
```

## 10.3 Workflow 단계

| 단계 | Event | 실행 Connector | 생성/활용 BoI |
|---|---|---|---|
| 이상 감지 | `equipment.alarm.raised.v1` | BoI Writer, Trend/Raw mock API, Event Publish | `boi/sop-instance` |
| 원인 분석 | `root_cause.analysis.requested.v1` | BoI Writer, Raw Data mock API | `boi/analysis` |
| 보전 가이드 | `maintenance.guide.requested.v1` | BoI Writer, Maintenance Guide mock API | `boi/runbook` |
| 이상 조치 | `corrective_action.requested.v1` | BoI Writer, Notification mock API, High-risk dry-run | `boi/action` |

## 10.4 Workflow 실행 명령

현재 v0.4 패키지에는 `equipment.alarm.raised.v1` 이벤트를 직접 발행해 workflow를 시작한다.

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "equipment.alarm.raised.v1",
    "payload": {
      "title": "Response Chain 이상 Alarm 발생",
      "equipment_id": "ETCH-VM-01",
      "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
      "lot_id": "LOT-001",
      "wafer_id": "WF-001",
      "owner": "100001"
    },
    "source_refs": [
      {"type": "sop", "ref": "boi:public:sop:equipment-abnormal-response"}
    ]
  }'
```

확인 화면:

```text
http://localhost:8000/events?employee_id=100001
http://localhost:8000/?employee_id=100001&event_type=equipment.alarm.raised.v1
http://localhost:8100/api/actions/logs
http://localhost:8081
```

---

## 11. BoI 문서 모델

## 11.1 BoI Markdown 구조

BoI 문서는 Markdown body와 YAML frontmatter를 가진다.

예시:

```markdown
---
type: boi/analysis
title: 원인 분석 요청 - ETCH-VM-01
description: 설비 Alarm 이후 원인 분석을 위한 Event-linked BoI
tags: [BoI, Event, SOP, AI-Native-Workflow]
timestamp: 2026-06-16T15:30:00+09:00

boi_id: boi:private:100001:20260616-001
visibility: private
classification: internal
owner: 100001
acl_policy: acl:private:100001
status: draft

event_type: root_cause.analysis.requested.v1
event_label: 원인 분석 요청
source_event:
  event_id: evt-20260616-abcdef
  event_type: root_cause.analysis.requested.v1
  occurred_at: 2026-06-16T15:30:00+09:00
source_refs:
  - type: event
    ref: evt-20260616-abcdef
---

# Summary

...

# Context

...

# Action Items

...

# References

...
```

## 11.2 필수 메타데이터

| 필드 | 설명 |
|---|---|
| `type` | BoI 종류 |
| `title` | 제목 |
| `description` | 설명 |
| `tags` | 검색/분류 태그 |
| `timestamp` | 생성/갱신 시각 |
| `boi_id` | BoI 고유 ID |
| `visibility` | `private`, `team`, `public` |
| `classification` | 보안 등급 |
| `owner` | 책임자 또는 소유자 |
| `acl_policy` | 접근 정책 |
| `status` | `draft`, `reviewed`, `approved` 등 |
| `event_type` | 연결 Event Type |
| `source_event` | 원천 Event 정보 |
| `source_refs` | 근거/출처 |

## 11.3 Private → Team/Public 승격

승격 원칙:

```text
자동 공유 금지
명시적 요청 필요
Private 원본 유지
공유용 BoI 사본 생성
Team/Public는 draft로 시작
Reviewer 검토 필요
```

---

## 12. Langflow BoI 공통 컴포넌트

## 12.1 Langflow mount

Docker Compose에서 custom component directory가 Langflow 컨테이너에 mount된다.

```yaml
volumes:
  - ./langflow/custom_components:/app/custom_components:ro
```

환경 변수:

```env
LANGFLOW_COMPONENTS_PATH=/app/custom_components
```

## 12.2 Reference Flow 예시

### Event 기반 BoI 생성 Flow

```text
Webhook
  → BoI Context Normalizer
  → BoI Harness Loader
  → BoI Metadata Builder
  → LLM / Prompt Template
  → BoI Policy Guard
  → BoI Wiki Writer
```

### Action Gateway 호출 Flow

```text
Input / Event
  → BoI Context Normalizer
  → BoI Harness Loader
  → BoI Action Invoker
  → Action Gateway /api/actions/invoke
  → Action Log / BoI / Next Event
```

Langflow Flow는 필요할 때 Action Catalog의 `langflow_webhook` Connector로 연결한다. Flow ID를 `data/action_catalog/actions.yaml`에 등록하면 Event Router가 Action Gateway를 통해 호출한다.

---

## 13. Event Router 동작 방식

Event Router는 Kafka `boi.events`를 consume한다.

동작 순서:

```text
1. Kafka event consume
2. BoI API /api/events/audit에 routing 상태 기록
3. Action Gateway /api/actions/dispatch 호출
4. 처리 결과를 Kafka boi.audit에 기록
5. BoI API /api/events/audit에 processed 상태 기록
6. 실패 시 boi.dead-letter에 기록
```

Event Router는 어떤 Connector가 실행되는지 판단하지 않는다. 판단과 실행은 Action Gateway가 Action Catalog를 기준으로 수행한다.

환경 변수:

```env
AUTO_ROUTE_EVENTS=true
```

`false`로 설정하면 Kafka Event를 consume하더라도 Action Gateway dispatch는 수행하지 않는다.

---

## 14. Action Gateway 실행 정책

## 14.1 Host allowlist

`ACTION_ALLOWED_HOSTS`에 등록된 host만 호출할 수 있다.

```env
ACTION_ALLOWED_HOSTS=boi-api,langflow,action-gateway,localhost,127.0.0.1,mcp-bridge
```

사내 API를 붙일 때는 해당 internal host를 allowlist에 추가해야 한다.

## 14.2 Dry-run

기본 설정:

```env
ACTION_DRY_RUN_DEFAULT=true
```

고위험 Action은 승인 전 dry-run만 허용한다.

예시:

```yaml
- action_key: sop.equipment.block_process_progress
  risk_level: high
  approval_required: true
```

## 14.3 Approval-required

`approval_required: true`인 Action은 실제 조치가 아니라 승인 필요 상태로 기록한다. PoC에서는 고위험 설비/공정 변경 Action이 이 정책을 따른다.

## 14.4 Action Log

Action 실행 결과는 `data/actions/`에 JSONL 형태로 남는다.

조회:

```bash
curl http://localhost:8100/api/actions/logs
```

---

## 15. Demo Scenario

## 15.1 기본 Staff/TF 업무 Event

회의 종료 Event 발행:

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "meeting.closed.v1",
    "payload": {"title": "AIX 확산 TF v0.4 설계 회의"},
    "source_refs": [{"type": "meeting_note", "ref": "/private/100001/meeting-notes/v04.md"}]
  }'
```

확인:

```text
BoI Wiki:    http://localhost:8000/?employee_id=100001&event_type=meeting.closed.v1
Event Stream: http://localhost:8000/events?employee_id=100001
Action Logs:  http://localhost:8100/api/actions/logs
Kafka UI:     http://localhost:8081
```

## 15.2 설비 이상 대응 SOP Event

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "equipment.alarm.raised.v1",
    "payload": {
      "title": "Response Chain 이상 Alarm 발생",
      "equipment_id": "ETCH-VM-01",
      "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
      "lot_id": "LOT-001",
      "wafer_id": "WF-001",
      "owner": "100001"
    },
    "source_refs": [
      {"type": "sop", "ref": "boi:public:sop:equipment-abnormal-response"}
    ]
  }'
```

기대 결과:

- Event Stream에 `equipment.alarm.raised.v1` 처리 이력 표시
- `boi.materialize_event`가 Event-linked Private BoI 생성
- Trend/Raw Data mock action log 생성
- `root_cause.analysis.requested.v1` 같은 다음 Event 발행 가능
- High-risk 조치는 approval-required 또는 dry-run으로만 기록

---

## 16. 사내 이관 가이드

## 16.1 교체 대상

| PoC 구성 | 사내 이관 대상 |
|---|---|
| 하드코딩된 사용자/팀 매핑 | SSO/IAM/HR 조직정보 |
| 파일 기반 BoI Wiki | 사내 Wiki/Git/SharePoint/문서 저장소 |
| Mock API | TAS, HyVIS, 설비, 품질, 승인, 알림 API |
| 개발용 API key/token | Secret Manager / Vault |
| Docker bridge network | 사내 Kubernetes 또는 표준 컨테이너 플랫폼 |
| 단순 검색 | 권한 기반 검색 + Vector/RAG |
| 단순 Reviewer field | 실제 결재/검토 workflow |
| 비활성 MCP 예시 | 승인된 MCP Bridge/Server |

## 16.2 Langflow 이관

- 기존 사내 Langflow에 BoI custom components 배포
- `ACTION_GATEWAY_URL`, `SERVICE_TOKEN` 설정
- BoI Action Invoker로 Action Gateway 호출 검증
- Reference Flow를 template으로 등록
- Flow ID를 Action Catalog의 `langflow_webhook` action에 등록

## 16.3 API/Webhook 이관

사내 API 연결 시 Action Catalog에 API Connector를 추가한다.

```yaml
- action_key: tas.trend.lookup
  type: api
  enabled: true
  auto_dispatch: true
  event_types: [equipment.alarm.raised.v1]
  method: POST
  url: http://tas.internal/api/trend
  headers:
    Authorization: Bearer ${secret.tas_token}
  body:
    equipment_id: ${payload.equipment_id}
    alarm_code: ${payload.alarm_code}
```

## 16.4 MCP 이관

- 사내 MCP Bridge 구축
- MCP Server allowlist 정의
- Tool discovery / session / auth 정책 수립
- Action Catalog에 `mcp_bridge` 또는 `mcp_tool` action 등록
- 결과를 BoI로 materialize하도록 후속 action 구성

---

## 17. 보안·통제 기준

| 영역 | PoC 기준 | 사내 이관 시 강화 |
|---|---|---|
| 인증 | service token, Langflow API key | SSO, mTLS, Secret Manager |
| 접근 제어 | 사번/팀 임시 매핑 | IAM/HR 조직정보 연계 |
| Private | 본인 Private만 Web 노출 | Local Private / Web Private 명확 분리 |
| Team/Public | draft, reviewer 필드 | 실제 승인 workflow |
| 외부 호출 | host allowlist | 네트워크 정책, egress control |
| 고위험 Action | dry-run / approval-required | 변경관리/결재 연계 |
| 로그 | JSONL | 감사 로그 플랫폼/SIEM |
| 민감정보 | PoC 수준 경고/마스킹 확장 필요 | DLP/보안 게이트웨이 연계 |

---

## 18. 테스트 체크리스트

## 18.1 기동 테스트

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8100/health
```

통과 기준:

- `boi-api` 정상
- `action-gateway` 정상
- `event-router` running
- Kafka topic 생성 완료
- Langflow 접속 가능

## 18.2 BoI 접근 제어 테스트

테스트 URL:

```text
http://localhost:8000/?employee_id=100001
http://localhost:8000/?employee_id=100002
http://localhost:8000/?employee_id=100003
```

통과 기준:

- Public 문서는 모두 보임
- Team 문서는 team membership 기준으로 다르게 보임
- Private 문서는 본인 것만 보임

## 18.3 Event → Action Gateway dispatch 테스트

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{"event_type":"meeting.closed.v1","payload":{"title":"Dispatch test"}}'
```

통과 기준:

- Event Stream에 `published`, `routing`, `processed` 상태 기록
- Action Log에 `boi.materialize_event` 실행 기록
- BoI Wiki에 Event-linked BoI 생성

## 18.4 No-fallback 표현 테스트

코드/문서 내에서 다음 표현이 남아있지 않은지 확인한다.

```bash
grep -Rni "fallback\|secondary path\|backup" .
```

통과 기준:

- 설계 문서와 README에 fallback/보조경로 표현이 남지 않아야 함
- 단, 과거 migration 설명에서 “제거했다”는 설명 용례만 허용 가능

## 18.5 High-risk Action 테스트

`corrective_action.requested.v1` 이벤트 발행 후 확인한다.

통과 기준:

- `sop.equipment.block_process_progress`는 실제 실행이 아니라 approval-required 또는 dry-run 기록
- Action Log에 risk_level/high, approval_required true가 남음

---

## 19. Known Issues / 주의사항

| 항목 | 내용 |
|---|---|
| PoC용 사용자/팀 매핑 | 코드 내 임시 구현이며 사내 이관 시 IAM/HR 연동 필요 |
| 파일 기반 저장소 | 동시성/대용량 검색/권한 감사에는 한계 있음 |
| Mock API | 실제 TAS/HyVIS/설비 시스템 연동 전까지는 동작 시뮬레이션 수준 |
| MCP | Bridge endpoint 미설정 시 실제 MCP 호출은 수행하지 않음 |
| Langflow Flow | 기본 패키지는 custom component 제공이며, 실제 Flow는 사내 Langflow에서 구성 필요 |
| Dry-run 기본값 | PoC 안전을 위해 dry-run 기본값이 true |
| 보안 토큰 | `.env.example`의 개발용 token은 반드시 변경 필요 |
| Docker image pull | 사내망에서는 registry/proxy 정책에 따라 image source 조정 필요 |

---

## 20. v0.5 제안 과제

| 우선순위 | 과제 | 설명 |
|---:|---|---|
| P0 | 사내 IAM/SSO 연동 | 사번/팀/Role 기반 접근 제어 실제화 |
| P0 | BoI 저장소 결정 | Git/SharePoint/Wiki/DB 중 사내 운영 표준 결정 |
| P0 | Langflow Reference Flow export | 회의/Action/보고/SOP Flow를 실제 Langflow 템플릿으로 제공 |
| P1 | MCP Bridge Prototype | BoI 검색/작성 MCP tool PoC |
| P1 | Vector/RAG 검색 | BoI Reader를 권한 기반 semantic search로 확장 |
| P1 | Promotion Workflow | Team/Public 승격 검토를 실제 승인 workflow로 연결 |
| P1 | Action Policy Engine | risk level, approval, dry-run, host allowlist를 정책 엔진화 |
| P2 | Event Graph View | Event → Action → BoI → Next Event 관계 시각화 |
| P2 | SOP Authoring UI | SOP를 Event Type + Action Catalog로 저작하는 Web UI |
| P2 | Audit Dashboard | Event/Action/BoI 생성·조회·승격 감사 화면 |

---

## 21. 경영진 보고용 한 장 메시지

```text
이번 PoC는 Langflow Agent 하나를 만드는 프로젝트가 아니다.

업무 Event를 Event Broker로 받고,
Action Gateway가 BoI Writer, Langflow, API, Webhook, MCP를 동등한 Connector로 실행하며,
BoI Wiki가 SOP와 판단 근거, 실행 결과를 조직 지식으로 축적하는 구조를 검증한다.

이를 통해 SOP는 사람이 읽는 문서를 넘어,
AI와 시스템이 함께 실행하고 기억하는 AI Native Workflow가 된다.
```

핵심 문구:

> **실행 채널은 계속 바뀔 수 있지만, Event Type과 BoI Wiki는 유지되는 구조다.**

---

## 22. 부록: 기본 Demo 순서

1. Docker Compose 기동
2. BoI Wiki 접속
3. Event Type Catalog 확인
4. Action Catalog 확인
5. `meeting.closed.v1` Event 발행
6. Event Stream 확인
7. BoI Wiki에서 Event-linked BoI 확인
8. `equipment.alarm.raised.v1` Event 발행
9. Action Gateway Logs 확인
10. Kafka UI에서 topic message 확인
11. Private → Team 승격 API 테스트
12. Langflow 접속 후 BoI custom components 확인
13. Action Catalog에서 Langflow connector 활성화 방법 설명
14. MCP connector는 extension point로 설명

---

## 23. 부록: 주요 파일 빠른 참조

| 파일 | 설명 |
|---|---|
| `docker-compose.yml` | 전체 PoC 서비스 기동 정의 |
| `.env.example` | 환경 변수 예시 |
| `boi_api/app/main.py` | BoI Wiki/API/Event 발행/Webhook 수신/Event materialize |
| `action_gateway/app/main.py` | Connector Action 실행 허브 |
| `event_adapter/app/main.py` | Kafka Event Router |
| `data/event_catalog/event_types.yaml` | Event Type Catalog |
| `data/action_catalog/actions.yaml` | Action Connector Catalog |
| `data/boi/public/` | Public SOP/문서 seed |
| `data/boi/team/` | Team 문서 seed |
| `data/boi/private/` | Web Private 문서 seed |
| `data/events/` | Event Stream JSONL |
| `data/actions/` | Action Log JSONL |
| `langflow/custom_components/boi/` | Langflow BoI 공통 컴포넌트 |

---

## 24. 최종 정리

v0.4는 `fallback` 구조가 아니다. v0.4의 핵심은 **Peer Connector Invocation Model**이다.

```text
BoI Writer도 Connector다.
Langflow도 Connector다.
API도 Connector다.
Webhook도 Connector다.
MCP도 Connector다.
미래의 새로운 호출 방식도 Connector다.

Event Broker는 이들을 깨우고,
Action Gateway는 이들을 통제하며,
BoI Wiki는 결과를 조직 지식으로 축적한다.
```

이 구조를 통해 구성원과 Agent는 BoI Wiki에 접속하는 것만으로 SOP, 업무 문서, 회의/Action/보고 맥락, 설비 이상 대응 이력 등을 활용할 수 있다. 실시간 실행이 필요할 때는 Event Broker를 통해 적절한 Connector가 호출된다.
