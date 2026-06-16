# BoI PoC Kit v0.4 전체 문서

## 0. 문서 목적

본 문서는 **BoI PoC Kit v0.4**의 전체 구조, 실행 방법, 주요 컴포넌트, Event Broker/BoI Wiki/Action Gateway/Langflow 연동 방식, 사내 이관 시 고려사항을 정리한 실행 문서다.

v0.4의 가장 중요한 변경점은 다음이다.

> **BoI API는 fallback이 아니다.**  
> BoI Writer, Langflow, API, Webhook, MCP, 향후 신규 인터페이스는 모두 **동등한 Peer Connector / Invocation Channel**로 취급한다.

따라서 v0.4의 핵심 아키텍처는 다음과 같다.

```text
Business Event
  → Kafka Event Broker
  → Event Router
  → Action Gateway
      → BoI Writer Connector
      → Langflow Webhook Connector
      → HTTP API Connector
      → Generic Webhook Connector
      → MCP Bridge Connector
      → Event Publish Connector
      → Future Connector
  → BoI Wiki / Action Log / Event Stream / Next Event
```

---

## 1. v0.4 핵심 메시지

### 1.1 한 줄 정의

> **실행 채널은 계속 바뀔 수 있지만, Event Type과 BoI Wiki는 유지되는 AI Native Workflow Backbone이다.**

### 1.2 설계 의도

v0.4는 특정 도구나 특정 실행 방식에 종속되지 않는 구조를 목표로 한다. Langflow는 사내 Agent Builder 실행 채널 중 하나이며, API/Webhook은 기존 업무 시스템과 연결되는 실행 채널이다. MCP는 향후 Agent와 Tool/Resource/Prompt를 표준화해 연결할 확장 채널이다. BoI Writer는 업무 Event와 실행 결과를 조직 지식으로 축적하는 실행 채널이다.

즉, 어떤 방식으로 Agent나 시스템을 호출하든, 업무 흐름은 아래 원칙을 따른다.

```text
Event Type으로 업무 시점을 정의한다.
Action Catalog로 실행 채널을 등록한다.
Action Gateway가 등록된 Connector를 실행한다.
BoI Wiki가 판단 근거와 실행 결과를 조직 지식으로 축적한다.
```

### 1.3 v0.3 대비 가장 큰 수정

| v0.3에서 보일 수 있던 오해 | v0.4 수정 방향 |
|---|---|
| Langflow가 주 경로이고 BoI API는 fallback처럼 보임 | 모든 실행 대상을 Peer Connector로 재정의 |
| Event Adapter가 Langflow/BoI 중 하나를 선택하는 것처럼 보임 | Event Router는 Action Gateway에만 dispatch |
| BoI API가 보조 처리 경로처럼 보임 | BoI Writer Connector로 1급 실행 채널화 |
| API/Webhook/MCP는 후순위처럼 보임 | Action Catalog 기반 동등 실행 채널로 확장 |
| 새로운 호출 방식이 나오면 Router 수정 필요 | Action Gateway에 Connector Type만 추가 |

---

## 2. 전체 아키텍처

```text
[사람 / Agent / 업무 시스템]
  - Web BoI Wiki에서 Event 발행
  - 외부 시스템 Webhook 수신
  - Langflow Flow 실행
  - 사내 API 호출
  - MCP Tool 호출
        │
        ▼
[Kafka Event Broker]
  - boi.events
  - boi.audit
  - boi.dead-letter
        │
        ▼
[Event Router]
  - Kafka event consume
  - Event Stream audit 기록
  - Action Gateway /api/actions/dispatch 호출
        │
        ▼
[Action Gateway]
  - Action Catalog 조회
  - Connector별 정책 검증
  - Host allowlist 확인
  - 승인 필요 여부 판단
  - Connector 실행
  - Action Log 기록
        │
        ├─ BoI Writer Connector
        ├─ Langflow Webhook Connector
        ├─ HTTP/API Connector
        ├─ Generic Webhook Connector
        ├─ MCP Bridge Connector
        ├─ Event Publish Connector
        └─ Future Connector
        │
        ▼
[BoI Wiki]
  - Public SOP / 공통 문서
  - Team BoI / 팀 문서
  - Web-created Private BoI
  - Event Type Catalog
  - Event Stream
  - Action Catalog / Action Log
        │
        ▼
[사람 + Agent]
  - SOP 참조
  - 과거 판단 근거 조회
  - 업무 맥락 Lazy Loading
  - Team/Public 승격
  - 보고/조치/의사결정 활용
```

---

## 3. Docker Compose 서비스 구성

v0.4는 Docker Compose로 한 번에 기동하는 것을 목표로 한다.

| 서비스 | 역할 | 기본 포트 |
|---|---|---:|
| `langflow-postgres` | Langflow metadata 저장소 | 내부 |
| `langflow` | 사내 Agent Builder 실행 채널 | `7860` |
| `kafka` | 실제 Event Broker | `9094` external |
| `kafka-init` | `boi.events`, `boi.audit`, `boi.dead-letter` topic 생성 | 내부 |
| `kafka-ui` | Kafka topic/message 확인 | `8081` |
| `boi-api` | BoI Wiki Web/API, Event 발행, BoI materialization | `8000` |
| `action-gateway` | Peer Connector 실행 허브 | `8100` |
| `event-router` | Kafka event consume 후 Action Gateway dispatch | 내부 |

### 3.1 기동 방법

```bash
cd boi-poc-kit-v0.4
cp .env.example .env
docker compose up -d --build
```

### 3.2 접속 URL

| 화면 | URL |
|---|---|
| BoI Wiki | `http://localhost:8000/?employee_id=100001` |
| Event Type Catalog | `http://localhost:8000/event-types?employee_id=100001` |
| Event Stream | `http://localhost:8000/events?employee_id=100001` |
| Action Catalog / Logs | `http://localhost:8000/actions?employee_id=100001` |
| BoI API Swagger | `http://localhost:8000/docs` |
| Action Gateway Swagger | `http://localhost:8100/docs` |
| Kafka UI | `http://localhost:8081` |
| Langflow | `http://localhost:7860` |

---

## 4. 디렉터리 구조

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
│     └─ static/style.css
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
│  ├─ event_catalog/event_types.yaml
│  ├─ action_catalog/actions.yaml
│  ├─ events/
│  └─ actions/
├─ scripts/publish_event.py
└─ docs/
   ├─ CONNECTOR_AGNOSTIC_ARCHITECTURE_V0_4.md
   ├─ MIGRATION_FROM_V0_3.md
   └─ V0_4_PEER_CONNECTOR_MODEL.md
```

---

## 5. BoI Wiki

### 5.1 역할

BoI Wiki는 사람과 Agent가 함께 접속해서 조직 지식을 활용하는 Web 기반 지식 표면이다. 단순 문서 저장소가 아니라 다음 정보를 한 화면에서 연결한다.

- Public SOP / 공통 가이드
- Team BoI 문서
- Web 또는 Langflow/API가 생성한 Private BoI
- Event Type Catalog
- Event Stream
- Action Catalog / Action Log
- Event-linked BoI 문서

### 5.2 접근 제어 모델

요청한 접근 정책은 다음과 같이 반영되어 있다.

```text
사번으로 Web BoI Wiki 접속
  → Public 문서 전체 조회
  → 본인 Team ACL에 맞는 Team 문서 조회
  → Langflow/Web/API가 올린 본인 Private 문서 조회
  → Local Agent가 로컬에만 저장한 Private 문서는 Web 미노출
```

PoC용 사번/팀 매핑은 `boi_api/app/main.py`에 임시 하드코딩되어 있다.

```text
100001 → aix-tf, platform
100002 → aix-tf
100003 → platform
```

확인 URL 예시:

```text
http://localhost:8000/?employee_id=100001
http://localhost:8000/?employee_id=100002
http://localhost:8000/?employee_id=100003
```

### 5.3 Private 정책

v0.4의 Private은 두 종류로 구분한다.

| 구분 | Web BoI Wiki 노출 여부 | 설명 |
|---|---:|---|
| Web-created Private | 노출 | Langflow/Web/API가 BoI API를 통해 올린 개인 문서 |
| Local-only Private | 미노출 | Local Agent가 개인 PC/Local Store에만 저장한 문서 |

이 구분은 중요하다. 조직 지식으로 축적 가능한 업무 맥락은 Web BoI Wiki를 통해 관리되고, 개인 로컬에만 남기는 민감하거나 실험적인 메모는 Web에 노출하지 않는다.

### 5.4 Team/Public 승격 원칙

```text
기본은 Private
공유는 명시적 요청
Team/Public는 copy-not-move
Team/Public는 draft로 생성
Reviewer 검토 후 reviewed/approved
```

Private BoI를 Team으로 “이동”하지 않는다. 원본 Private BoI는 그대로 두고, Team/Public 공유용 사본을 새로 만든다.

---

## 6. BoI 문서 모델

### 6.1 BoI = SK하이닉스형 OKF Profile

BoI는 별도 Registry가 아니라 OKF 스타일의 Markdown + YAML frontmatter 문서다. v0.4에서 BoI는 Event, SOP, 업무 맥락, 실행 결과를 조직 지식으로 materialize하는 기본 단위다.

### 6.2 기본 메타데이터 예시

```yaml
---
okf_version: "0.1"
boi_profile_version: "0.1"

type: boi/meeting
title: AIX 확산 TF 주간회의 정리
description: BoI Writer connector가 생성한 회의 Private BoI
tags: [AIX, BoIWiki, Langflow, Meeting]
timestamp: 2026-06-16T15:30:00+09:00

boi_id: boi:private:emp_100001:20260616-001
visibility: private
classification: internal
owner: "100001"
author:
  type: agent
  agent_id: boi-writer-connector
acl_policy: acl:private:100001
status: draft

event_type: meeting.closed.v1
event_label: 회의 종료
source_event:
  event_id: evt-20260616153000-abc123
  event_type: meeting.closed.v1
  occurred_at: 2026-06-16T15:30:00+09:00
source_refs:
  - type: event
    ref: evt-20260616153000-abc123
---
```

### 6.3 Body 권장 구조

```markdown
# Summary

# Context

# Key Decisions

# Action Items

# Recommended Actions

# Risks / Open Questions

# References
```

업무별로 body는 자유롭게 변형할 수 있지만, Team/Public 승격 시에는 출처와 참고 BoI를 남기는 것을 원칙으로 한다.

---

## 7. Event Broker

### 7.1 역할

Kafka는 v0.4에서 실제 Event Broker다. Kafka는 업무 이벤트를 전달하고, Event Router는 Kafka에서 event를 consume해 Action Gateway로 넘긴다.

| Topic | 역할 |
|---|---|
| `boi.events` | 업무 이벤트 입력 topic |
| `boi.audit` | 처리 성공/상태 audit topic |
| `boi.dead-letter` | 처리 실패 event 기록 |

### 7.2 Event Envelope 예시

```json
{
  "event_id": "evt-20260616153000-abc123",
  "event_type": "meeting.closed.v1",
  "event_version": "1",
  "occurred_at": "2026-06-16T15:30:00+09:00",
  "producer": "boi-api-web",
  "actor": {
    "type": "human",
    "employee_id_hash": "100001",
    "employee_id": "100001"
  },
  "visibility_hint": "private",
  "classification_hint": "internal",
  "source_refs": [
    {"type": "meeting_note", "ref": "/private/100001/meeting-notes/demo.md"}
  ],
  "target": {
    "flow_key": "boi-meeting-writer-v0.1",
    "boi_type": "boi/meeting"
  },
  "event_type_label": "회의 종료",
  "payload": {
    "title": "AIX 확산 TF 회의"
  },
  "trace_id": "trace-..."
}
```

### 7.3 이벤트 발행 방법

BoI API에서 event를 발행할 수 있다.

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"meeting.closed.v1",
    "payload":{"title":"AIX 확산 TF 업무 맥락 자산화 PoC 회의"},
    "source_refs":[{"type":"meeting_note","ref":"/private/100001/meeting-notes/demo.md"}]
  }'
```

외부 Webhook으로 event를 주입할 수도 있다.

```bash
curl -X POST "http://localhost:8000/api/webhooks/tas?employee_id=100001" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "event_type":"equipment.alarm.raised.v1",
    "payload":{
      "equipment_id":"ETCH-VM-01",
      "alarm_code":"RESPONSE_CHAIN_ABNORMAL",
      "title":"Response Chain 이상 Alarm 발생"
    }
  }'
```

---

## 8. Event Type Catalog

### 8.1 위치

```text
data/event_catalog/event_types.yaml
```

### 8.2 역할

Event Type Catalog는 Kafka topic의 기술적 정의가 아니라, 업무 이벤트의 의미를 정의하는 카탈로그다.

| Event Type | 업무명 | 기본 BoI Type | 기본 Visibility |
|---|---|---|---|
| `meeting.closed.v1` | 회의 종료 | `boi/meeting` | private |
| `action.created.v1` | Action Item 생성 | `boi/action` | private |
| `report.requested.v1` | 보고 요청 | `boi/report` | private |
| `promotion.requested.v1` | BoI 승격 요청 | `boi/reference` | team |
| `equipment.alarm.raised.v1` | 설비 Alarm 발생 | `boi/sop-instance` | private |
| `trend.anomaly.detected.v1` | Trend 이상 감지 | `boi/analysis` | private |
| `root_cause.analysis.requested.v1` | 원인 분석 요청 | `boi/analysis` | private |
| `maintenance.guide.requested.v1` | 장비 보전 가이드 요청 | `boi/runbook` | private |
| `corrective_action.requested.v1` | 이상 조치 요청 | `boi/action` | private |
| `external.webhook.received.v1` | 외부 Webhook 수신 | `boi/reference` | private |

### 8.3 화면

```text
http://localhost:8000/event-types?employee_id=100001
```

---

## 9. Event Router

### 9.1 역할

Event Router는 Kafka에서 이벤트를 읽어 Action Gateway로 전달하는 얇은 라우터다.

중요한 점은 Event Router가 어떤 Connector가 주 경로인지 판단하지 않는다는 것이다.

```text
Event Router는 Langflow, BoI Writer, API, Webhook, MCP를 모른다.
Event Router는 Action Gateway /api/actions/dispatch만 호출한다.
```

### 9.2 처리 흐름

```text
Kafka boi.events consume
  → BoI Wiki Event Stream에 routing 기록
  → Action Gateway /api/actions/dispatch 호출
  → 결과를 boi.audit topic에 기록
  → BoI Wiki Event Stream에 processed 기록
  → 실패 시 boi.dead-letter에 기록
```

### 9.3 환경 변수

```env
AUTO_ROUTE_EVENTS=true
ACTION_GATEWAY_URL=http://action-gateway:8100
ACTION_GATEWAY_SERVICE_TOKEN=dev-service-token-change-me
```

---

## 10. Action Gateway

### 10.1 역할

Action Gateway는 v0.4의 핵심 실행 허브다. Event Type별로 등록된 Connector Action을 조회하고, 정책을 확인한 뒤 실행한다.

Action Gateway가 담당하는 일은 다음과 같다.

- Action Catalog 로딩
- Event Type에 맞는 Action 선택
- Host allowlist 확인
- 승인 필요 여부 확인
- dry-run 처리
- Connector 실행
- 결과/오류 Action Log 기록
- 필요 시 다음 Event publish

### 10.2 API

| Endpoint | 설명 |
|---|---|
| `GET /health` | 상태 확인 |
| `GET /api/actions` | 활성화된 Action 목록 |
| `GET /api/actions/logs` | Action 실행 로그 |
| `POST /api/actions/invoke` | 특정 Action 수동 실행 |
| `POST /api/actions/dispatch` | Event Type 기준 등록 Action 자동 실행 |

### 10.3 Dispatch 예시

```bash
curl -X POST "http://localhost:8100/api/actions/dispatch" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "employee_id":"100001",
    "event":{
      "event_id":"evt-manual-001",
      "event_type":"meeting.closed.v1",
      "payload":{"title":"수동 Dispatch 테스트"},
      "actor":{"employee_id":"100001"}
    },
    "payload":{"title":"수동 Dispatch 테스트"}
  }'
```

---

## 11. Action Catalog

### 11.1 위치

```text
data/action_catalog/actions.yaml
```

### 11.2 Connector Type

| Connector Type | 목적 | v0.4 상태 |
|---|---|---|
| `boi_materialize` | Event를 Event-linked BoI 문서로 축적 | 구현 |
| `langflow_webhook` | Langflow Flow 실행 | 구현, Flow ID 필요 |
| `http` / `api` | REST 스타일 내부 API 호출 | 구현 |
| `webhook` / `internal_webhook` | Generic Webhook 호출 | 구현 |
| `mock_api` | PoC-visible 시스템/API 호출 시뮬레이션 | 구현 |
| `event_publish` / `boi_event` | 다음 업무 Event 발행 | 구현 |
| `mcp_tool` / `mcp_bridge` | MCP 서버의 Tool/Resource/Prompt 연결 | Extension point |

### 11.3 BoI Writer Connector

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

이 Connector는 모든 Event를 Event-linked BoI로 materialize할 수 있다. 이것은 Langflow가 없을 때 사용하는 fallback이 아니라, Event와 실행 결과를 조직 지식으로 남기는 1급 Connector다.

### 11.4 Langflow Connector 예시

```yaml
- action_key: langflow.meeting_writer.sample
  name_ko: Langflow 회의 BoI Writer Flow 호출 예시
  type: langflow_webhook
  enabled: false
  event_types: [meeting.closed.v1]
  flow_id: ${payload.langflow_flow_id}
  risk_level: low
  approval_required: false
```

Langflow Flow ID가 준비되면 `enabled: true`로 바꾸고 `flow_id`를 설정한다.

### 11.5 MCP Connector 예시

```yaml
- action_key: mcp.boi_search.sample
  name_ko: MCP 기반 BoI 검색 Tool 호출 예시
  type: mcp_tool
  enabled: false
  event_types: [report.requested.v1, maintenance.guide.requested.v1]
  tool_name: boi.search
  arguments:
    query: ${payload.query}
    employee_id: ${employee_id}
    allowed_visibility: [public, team, private]
```

v0.4에서 MCP는 Extension point다. 실제 사내 MCP Bridge가 준비되면 `MCP_BRIDGE_URL`을 설정하고 Connector를 활성화한다.

---

## 12. BoI Writer Connector

### 12.1 역할

BoI Writer Connector는 Event를 BoI Wiki 문서로 materialize한다. Event가 발생했다는 사실만 로그에 남기는 것이 아니라, 해당 Event의 업무 맥락, payload, source event, recommended actions, SOP reference를 BoI 문서로 남긴다.

### 12.2 Endpoint

대표 endpoint:

```text
POST /api/boi/materialize-event
```

호환 endpoint:

```text
POST /api/boi/from-event
POST /api/boi/materialize-from-event
POST /api/events/handle
```

### 12.3 업무별 BoI 생성 로직

| Event | 생성 BoI Type | 생성 내용 |
|---|---|---|
| `meeting.closed.v1` | `boi/meeting` | 회의 Summary, 결정사항, Action Item |
| `action.created.v1` | `boi/action` | Action Owner, Due, Required Output |
| `report.requested.v1` | `boi/report` | 권한 있는 BoI Lazy Loading 기반 보고 초안 |
| 설비/SOP 관련 Event | Event Catalog의 `default_boi_type` | SOP 단계, payload, recommended actions, references |
| 기타 Event | `boi/reference` | Generic Event BoI |

---

## 13. Langflow BoI 공통 컴포넌트

### 13.1 목적

Langflow는 사내 Agent Builder 실행 채널이다. v0.4는 Langflow에 BoI 공통 컴포넌트를 포함하여, 구성원이 Agent Flow를 만들 때 BoI Wiki와 Action Gateway를 쉽게 연결할 수 있도록 한다.

### 13.2 컴포넌트 목록

| Component | 역할 |
|---|---|
| `boi_context_normalizer.py` | Webhook/Event/User input을 BoI WorkContext로 정규화 |
| `boi_harness_loader.py` | Agent Harness instruction 주입 |
| `boi_metadata_builder.py` | OKF/SK BoI YAML frontmatter 생성 |
| `boi_policy_guard.py` | 저장/공유 전 정책 점검 |
| `boi_wiki_writer.py` | BoI API로 문서 저장 |
| `boi_wiki_reader.py` | 사번 기준 접근 가능한 BoI 조회 |
| `boi_action_invoker.py` | Action Gateway의 Action 호출 |

### 13.3 Reference Flow 예시

```text
Webhook / Chat Input
  → BoI Context Normalizer
  → BoI Harness Loader
  → BoI Metadata Builder
  → LLM / Prompt Template
  → BoI Policy Guard
  → BoI Wiki Writer
  → BoI Action Invoker optional
```

### 13.4 Langflow가 필수 경로가 아닌 이유

Langflow는 중요한 실행 채널이지만 유일한 경로는 아니다. 같은 Event에 대해 BoI Writer, API, Webhook, MCP가 동시에 실행될 수 있다.

```text
Event가 발생하면:
  - BoI Writer가 업무 맥락을 저장하고
  - Langflow가 Agent Flow를 실행하고
  - API/Webhook이 시스템 데이터를 가져오고
  - MCP가 Tool/Resource를 호출하고
  - 필요하면 다음 Event를 발행한다.
```

---

## 14. API/Webhook/MCP 호환 구조

### 14.1 API/Webhook을 1급 Event Producer로 사용

외부 시스템은 `/api/webhooks/{source}`로 event를 주입할 수 있다. 이 endpoint는 수신 payload를 business event로 변환해 Kafka `boi.events`에 발행한다.

```text
External System
  → POST /api/webhooks/{source}
  → Kafka boi.events
  → Event Router
  → Action Gateway
```

### 14.2 API/Webhook을 1급 Connector로 사용

Action Catalog에 `api`, `http`, `webhook`, `internal_webhook` 타입을 등록하면 Action Gateway가 해당 URL을 호출한다. 호출 대상은 `ACTION_ALLOWED_HOSTS`로 통제된다.

### 14.3 MCP 확장 방식

MCP는 Event Router가 직접 알 필요가 없다. Action Gateway 뒤쪽에 MCP Bridge를 붙인다.

```text
Event Router
  → Action Gateway
  → MCP Bridge
  → MCP Server
  → Tool / Resource / Prompt
```

사내 MCP Bridge가 준비되면 다음을 구현한다.

- MCP server registry
- Tool discovery
- Authentication / authorization
- Session / transport 처리
- Tool invocation
- 결과 BoI 기록

---

## 15. SOP 기반 설비 이상 대응 AI Native Workflow

### 15.1 목적

첨부 SOP 사례는 이상 감지, 원인 분석, 장비 보전 가이드, 이상 조치로 이어지는 업무 흐름이다. v0.4는 이를 문서형 SOP가 아니라 Event-driven AI Native Workflow로 전환하는 것을 검증한다.

### 15.2 Workflow 단계

```text
equipment.alarm.raised.v1
  → BoI Writer Connector: boi/sop-instance 생성
  → mock_api: Trend / Raw Data 확인
  → event_publish: root_cause.analysis.requested.v1 발행

root_cause.analysis.requested.v1
  → BoI Writer Connector: boi/analysis 생성
  → mock_api: Raw / Source Data 확인
  → mock_api: 장비 보전 가이드 요청

maintenance.guide.requested.v1
  → BoI Writer Connector: boi/runbook 생성
  → mock_api: 보전 가이드 반환

corrective_action.requested.v1
  → BoI Writer Connector: boi/action 생성
  → mock_api: 담당자 알림
  → high-risk mock_api: 공정 진행 금지 요청 dry-run
  → high-risk mock_api: Spec / Rule 변경 요청 dry-run
```

### 15.3 SOP 테스트 명령

v0.4에서는 `/api/workflows/demo/...` 전용 endpoint보다 Event 발행 방식으로 실행하는 것을 권장한다.

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"equipment.alarm.raised.v1",
    "payload":{
      "equipment_id":"ETCH-VM-01",
      "alarm_code":"RESPONSE_CHAIN_ABNORMAL",
      "title":"Response Chain 이상 Alarm 발생",
      "lot_id":"LOT-001",
      "wafer_id":"WF-01",
      "owner":"100001"
    },
    "source_refs":[{"type":"sop","ref":"boi:public:sop:equipment-abnormal-response"}]
  }'
```

확인 화면:

```text
Event Stream:
http://localhost:8000/events?employee_id=100001

Event-linked BoI:
http://localhost:8000/?employee_id=100001&event_type=equipment.alarm.raised.v1

Action Logs:
http://localhost:8100/api/actions/logs

Action Catalog UI:
http://localhost:8000/actions?employee_id=100001
```

### 15.4 고위험 Action 처리 원칙

공정 진행 금지, Spec/Rule 변경 같은 Action은 high-risk로 분류한다. v0.4 PoC에서는 승인 전 자동 실행하지 않고 dry-run 또는 approval-required 상태로 기록한다.

```text
고위험 Action은 자동 실행하지 않는다.
Action Gateway가 approval_required를 확인한다.
승인 정보가 없으면 dry-run 또는 blocked 상태로 기록한다.
실행 후보와 근거는 BoI Wiki에 남긴다.
```

---

## 16. 주요 API 요약

### 16.1 BoI API

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/health` | 상태 확인 |
| `GET` | `/` | BoI Wiki Web |
| `GET` | `/docs/{boi_id}` | BoI 상세 |
| `GET` | `/api/boi` | 접근 가능한 BoI 목록 |
| `POST` | `/api/boi` | BoI 직접 생성 |
| `POST` | `/api/boi/{boi_id}/promote` | Team/Public 승격 |
| `POST` | `/api/events/publish` | Kafka event 발행 |
| `POST` | `/api/webhooks/{source}` | 외부 Webhook 수신 후 Event 발행 |
| `POST` | `/api/boi/materialize-event` | Event를 BoI로 materialize |
| `GET` | `/event-types` | Event Type Catalog Web |
| `GET` | `/events` | Event Stream Web |
| `GET` | `/api/event-types` | Event Type API |
| `GET` | `/api/events/log` | Event Log API |
| `POST` | `/api/events/audit` | Event 처리 상태 기록 |
| `GET` | `/actions` | Action Catalog/Log Web |
| `GET` | `/api/actions/catalog` | Action Catalog API |
| `GET` | `/api/actions/logs` | Action Log API |
| `POST` | `/api/actions/invoke` | Action Gateway proxy 호출 |
| `GET` | `/api/users` | PoC 사용자/팀 매핑 |

### 16.2 Action Gateway API

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/health` | 상태 확인 |
| `GET` | `/api/actions` | 활성 Action 목록 |
| `GET` | `/api/actions/logs` | Action 실행 로그 |
| `POST` | `/api/actions/invoke` | 특정 Action 실행 |
| `POST` | `/api/actions/dispatch` | Event Type 기준 등록 Action 실행 |

---

## 17. 로그와 데이터 위치

| 데이터 | 위치 |
|---|---|
| BoI 문서 | `data/boi/` |
| Public BoI | `data/boi/public/` |
| Team BoI | `data/boi/team/{team_id}/` |
| Private BoI | `data/boi/private/{employee_id}/` |
| Event Type Catalog | `data/event_catalog/event_types.yaml` |
| Event Stream JSONL | `data/events/events-YYYYMMDD.jsonl` |
| Action Catalog | `data/action_catalog/actions.yaml` |
| Action Log JSONL | `data/actions/actions-YYYYMMDD.jsonl` |
| Langflow Custom Components | `langflow/custom_components/boi/` |
| Langflow DB | Docker volume `langflow-postgres-data` |
| Kafka data | Docker volume `kafka-data` |

---

## 18. 테스트 시나리오

### 18.1 기본 기동 테스트

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8100/health
```

통과 기준:

- `boi-api`, `action-gateway`, `kafka`, `event-router`, `langflow`가 정상 실행
- `boi-api`와 `action-gateway` health가 `ok`

### 18.2 회의 Event → BoI 생성

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"meeting.closed.v1",
    "payload":{"title":"AIX 확산 TF v0.4 검증 회의"},
    "source_refs":[{"type":"meeting_note","ref":"/private/100001/meeting-notes/v04.md"}]
  }'
```

확인:

```text
http://localhost:8000/events?employee_id=100001
http://localhost:8000/?employee_id=100001&event_type=meeting.closed.v1
http://localhost:8100/api/actions/logs
```

통과 기준:

- Event Stream에 `published`, `routing`, `processed` 상태 기록
- Private BoI 생성
- Action Log에 `boi.materialize_event` 실행 기록

### 18.3 외부 Webhook → Event → BoI 생성

```bash
curl -X POST "http://localhost:8000/api/webhooks/demo-source?employee_id=100001" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "event_type":"external.webhook.received.v1",
    "payload":{"title":"외부 Webhook 수신 테스트", "message":"hello"}
  }'
```

통과 기준:

- Webhook이 business event로 변환되어 Kafka에 발행
- Event Router가 Action Gateway에 dispatch
- Generic Private BoI 생성

### 18.4 Action Gateway 직접 호출

```bash
curl -X POST "http://localhost:8100/api/actions/invoke" \
  -H "Content-Type: application/json" \
  -H "x-service-token: dev-service-token-change-me" \
  -d '{
    "action_key":"boi.materialize_event",
    "employee_id":"100001",
    "event":{
      "event_id":"evt-direct-test-001",
      "event_type":"action.created.v1",
      "payload":{"title":"Action Gateway 직접 호출 테스트"},
      "actor":{"employee_id":"100001"}
    },
    "payload":{"title":"Action Gateway 직접 호출 테스트"}
  }'
```

통과 기준:

- Action Gateway가 BoI Writer Connector를 직접 호출
- `boi/action` 문서 생성
- Action Log 기록

### 18.5 SOP Workflow 테스트

```bash
curl -X POST "http://localhost:8000/api/events/publish?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"equipment.alarm.raised.v1",
    "payload":{
      "equipment_id":"ETCH-VM-01",
      "alarm_code":"RESPONSE_CHAIN_ABNORMAL",
      "title":"Response Chain 이상 Alarm 발생",
      "lot_id":"LOT-001",
      "wafer_id":"WF-01",
      "owner":"100001"
    }
  }'
```

통과 기준:

- 설비 Alarm Event가 BoI로 materialize
- Trend/Raw Data mock Action 로그 기록
- root cause 분석 요청 Event publish Action 실행
- 고위험 Action은 승인 필요 또는 dry-run으로 기록

---

## 19. 보안·통제 기준

### 19.1 인증

| 대상 | PoC 방식 | 사내 이관 방향 |
|---|---|---|
| Langflow API | `LANGFLOW_API_KEY` | Secret Manager / SSO / API Gateway |
| BoI API service endpoint | `x-service-token` | Service Account / mTLS / Gateway |
| Action Gateway | `x-service-token` | Service Account / mTLS / Gateway |
| Webhook ingest | `x-service-token` | Signed webhook / allowlist / WAF |

### 19.2 Host Allowlist

Action Gateway는 외부 호출 대상 host를 allowlist로 제한한다.

```env
ACTION_ALLOWED_HOSTS=boi-api,langflow,action-gateway,localhost,127.0.0.1,mcp-bridge
```

사내 이관 시에는 TAS, HyVIS, 문서 시스템, 승인 시스템, 알림 시스템 등 승인된 내부 도메인만 추가한다.

### 19.3 고위험 Action

```yaml
risk_level: high
approval_required: true
```

고위험 Action은 자동 실행하지 않고, 승인 정보가 없으면 dry-run 또는 blocked 상태로 남긴다.

### 19.4 Private/Team/Public

- Private은 사번 기준으로 격리한다.
- Team은 팀 ACL 기준으로 조회한다.
- Public은 전사 공통 조회용이다.
- Team/Public 승격은 copy-not-move 방식이다.
- Team/Public BoI는 draft 상태로 생성하고 reviewer 검토를 거친다.

---

## 20. 사내 이관 체크리스트

| PoC 구현 | 사내 이관 시 교체/확장 |
|---|---|
| 하드코딩 사용자/팀 매핑 | SSO/IAM/HR 조직정보 연동 |
| 파일 기반 BoI 저장소 | 사내 Wiki/Git/SharePoint/문서 저장소 |
| JSONL Event/Action log | 사내 로그 플랫폼 / DB / Observability |
| Dev API key | Secret Manager / Vault |
| Mock API | TAS, HyVIS, 설비, 승인, 알림, 문서 API |
| MCP Extension point | 사내 MCP Bridge / MCP Server |
| Docker Compose 단일 노드 | 사내 K8s / VM / 플랫폼 표준 |
| Langflow auto login | SSO 연동 및 권한 통제 |
| ACTION_ALLOWED_HOSTS | 사내 API Gateway/Service Mesh 정책 |
| high-risk dry-run | 승인/변경관리 workflow 연계 |

---

## 21. 운영 관점 역할 정의

| 역할 | 책임 |
|---|---|
| AIX 확산 TF PO | PoC 범위, 우선순위, 경영진 보고 |
| Technical Lead | Event/Action/BoI/Langflow 아키텍처 총괄 |
| BoI Wiki Owner | BoI Profile, Public/Team/Private 운영 기준 |
| Action Catalog Owner | Connector 등록, 위험도, 승인 필요 여부 관리 |
| Event Catalog Owner | Event Type 정의, 버전 관리, 업무 의미 정리 |
| Langflow Builder | Agent Flow 작성, BoI 공통 컴포넌트 적용 |
| Security Reviewer | Webhook/API/Private/Team/Public 통제 검토 |
| Pilot User | 실제 업무 Event 발행, BoI 활용, 피드백 |
| Reviewer | Team/Public 승격 문서 검토 |

---

## 22. Known Issues / 정합성 점검 필요 항목

v0.4는 PoC 실행 패키지이므로 사내 이관 전 아래 항목은 점검해야 한다.

| 항목 | 현재 상태 | 조치 방향 |
|---|---|---|
| 사용자/팀 ACL | 코드 하드코딩 | SSO/IAM 연동 |
| BoI 저장소 | 파일 기반 Markdown | 사내 저장소 연동 |
| 검색 | 단순 file scan | 권한 기반 검색/RAG/Vector index |
| MCP | Extension point | MCP Bridge 구현 필요 |
| Langflow Flow | Custom Components 제공 | 실제 Reference Flow export/import 추가 필요 |
| Event chain | 일부 event_publish 가능 | 업무별 chain 명시 고도화 |
| 고위험 Action | dry-run/approval-required | 실제 승인 시스템 연계 |
| Observability | JSONL 로그 | OpenTelemetry/사내 로그 플랫폼 연동 |
| 보안 | dev token | Secret Manager/mTLS/API Gateway 적용 |

---

## 23. v0.5 제안 사항

v0.5에서 추가하면 좋은 항목은 다음이다.

1. **Reference Flow Export**  
   Langflow에서 바로 import 가능한 `meeting.closed`, `report.requested`, `equipment.alarm.raised` Flow JSON 제공.

2. **BoI Search / RAG API**  
   권한 기반 BoI 검색, event_type 필터, tag 필터, source_event lineage 검색.

3. **MCP Bridge Prototype**  
   `boi.search`, `boi.read`, `boi.promote`, `event.publish`, `action.invoke` Tool 제공.

4. **Approval Workflow Prototype**  
   high-risk Action 실행 전 승인 요청/승인/반려 상태 관리.

5. **SOP Visualizer**  
   Event Type → Action → BoI → Next Event 흐름을 Web에서 graph 형태로 표시.

6. **Team/Public Promotion UI**  
   Private BoI 상세 화면에서 직접 Team/Public draft 생성 및 reviewer 지정.

7. **Enterprise Connector Registry**  
   사내 API/Webhook/MCP connector 등록·검증·승인 관리.

8. **Audit Dashboard**  
   이벤트 처리량, BoI 생성량, Action 실행량, 오류, 권한 위반 시도, high-risk dry-run 현황 표시.

---

## 24. 경영진 보고용 요약

### 24.1 v0.4 핵심 메시지

> **Event Broker가 업무 흐름을 깨우고, Action Gateway가 Langflow/API/Webhook/MCP/BoI Writer를 동등하게 실행하며, BoI Wiki가 판단 근거와 실행 결과를 조직 지식으로 축적한다.**

### 24.2 왜 중요한가

- Langflow 하나에 종속되지 않는다.
- API/Webhook/MCP 등 미래 실행 채널을 유연하게 붙일 수 있다.
- SOP를 사람이 보는 문서에서 AI와 시스템이 실행할 수 있는 Workflow로 전환한다.
- Agent나 사람이 BoI Wiki에 접속하는 것만으로 SOP, 과거 판단 근거, 팀/전사 문서를 활용할 수 있다.
- 개인 업무 맥락은 Private에서 시작하고, 명시적 요청과 검토를 거쳐 Team/Public 조직 지식으로 승격된다.

### 24.3 한 장 그림

```text
회장: 우리 일을 정의하고 조직을 이해하는 AI 필요
        ↓
CEO: AI는 판단과 실행을 연결해야 함
        ↓
AIX 확산 TF: 1인 1 Agent를 조직 지식으로 축적하는 업무 맥락 자산화
        ↓
v0.4 PoC:
Event Broker + Event Router + Action Gateway + Peer Connector + BoI Wiki
        ↓
SOP / 회의 / Action / 보고 / 이상 대응 업무를 AI Native Workflow로 실행
```

---

## 25. 최종 정리

v0.4의 핵심은 fallback 제거가 아니다. 더 정확히는 **실행 채널 추상화**다.

```text
BoI Writer는 fallback이 아니다.
Langflow는 유일한 주 경로가 아니다.
API/Webhook/MCP는 부가 기능이 아니다.
모든 실행 대상은 Action Gateway에서 관리되는 Peer Connector다.
```

따라서 앞으로 신규 시스템이나 신규 Agent 방식이 등장해도 Event Broker, Event Type, BoI Wiki, SOP 모델은 유지된다. 새로운 방식은 Action Gateway에 Connector로 추가하면 된다.

> **업무 Event는 유지되고, 실행 Connector는 교체 가능하며, 조직 지식은 BoI Wiki에 축적된다.**

