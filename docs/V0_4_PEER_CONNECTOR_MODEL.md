# BoI PoC Kit v0.4 — Peer Connector Invocation Model

## 1. 변경 배경

v0.3 문서와 일부 코드 표현은 Langflow와 BoI API 사이에 주 경로/보조 경로가 있는 것처럼 보일 여지가 있었다. 이 표현은 의도와 다르다. 목표는 Event Broker가 업무 이벤트를 받아 Langflow, HTTP API, Webhook, BoI Writer, MCP, 그리고 향후 등장할 신규 인터페이스를 모두 동등한 실행 채널로 다룰 수 있게 하는 것이다.

따라서 v0.4에서는 모든 실행 대상을 **Peer Connector / Invocation Channel**로 정리한다.

## 2. 핵심 원칙

```text
Event Broker = 업무 이벤트를 전달하는 Trigger Backbone
Action Gateway = 실행 채널을 표준화하고 통제하는 Invocation Hub
BoI Writer = 이벤트와 실행 결과를 조직 지식으로 축적하는 Connector
BoI Wiki = 사람과 Agent가 함께 활용하는 Workflow Memory
Langflow / API / Webhook / MCP = 동등하게 붙일 수 있는 실행 채널
```

## 3. 실행 구조

```text
업무 Event
  ↓
Kafka Event Broker
  ↓
Event Router
  ↓
Action Gateway Dispatch
  ├─ BoI Writer Connector
  ├─ Langflow Webhook Connector
  ├─ HTTP API Connector
  ├─ Generic Webhook Connector
  ├─ Event Publish Connector
  ├─ MCP Tool Connector
  └─ Future Connector
  ↓
BoI Wiki / Action Log / Event Stream
```

## 4. Connector Type

| Connector Type | 목적 | PoC 상태 |
|---|---|---|
| `boi_materialize` | Event를 Event-linked BoI 문서로 축적 | 구현 |
| `api` / `http` | 사내 시스템 API 호출 | 구현 |
| `webhook` / `webhook` | Generic webhook 호출 | 구현 |
| `langflow_webhook` | Langflow Flow 실행 | 구현, Flow ID 필요 |
| `event_publish` | 다음 업무 이벤트 발행 | 구현 |
| `mcp_tool` / `mcp_tool` | MCP 서버의 tool/resource/prompt 연결 | Extension point |

## 5. 왜 BoI Writer도 Connector인가

BoI Writer는 Langflow가 없을 때 쓰는 대체 경로가 아니다. Event Broker에서 발생한 업무 이벤트를 조직 지식으로 materialize하는 독립 실행 채널이다. 예를 들어 `meeting.closed.v1` 이벤트가 발생하면 Langflow Flow가 실행될 수도 있고, API/Webhook이 호출될 수도 있으며, 동시에 BoI Writer가 회의 맥락을 Private BoI로 축적할 수 있다.

즉, 실시간 실행은 각 Connector가 담당하고, 재사용 가능한 업무 기억은 BoI Wiki에 축적된다.

## 6. 설정 위치

Action Catalog:

```text
data/action_catalog/actions.yaml
```

Event Type Catalog:

```text
data/event_catalog/event_types.yaml
```

Event Router 환경 변수:

```env
DISPATCH_EVENTS=true
```

Action Gateway 환경 변수:

```env
ACTION_DRY_RUN_DEFAULT=true
ACTION_ALLOWED_HOSTS=boi-api,langflow,action-gateway,localhost,127.0.0.1
MCP_BRIDGE_URL=
```

## 7. 사내 이관 방향

사내 이관 시에는 Connector Type을 추가하면 된다. Event Broker, BoI Wiki, Action Gateway의 핵심 모델은 바꾸지 않는다.

예시:

```yaml
- action_key: fab.eqp.get_alarm_context
  type: api
  event_types: [equipment.alarm.raised.v1]
  url: http://quality-system.internal/api/alarm-context
  method: POST

- action_key: agent.root_cause.langflow
  type: langflow_webhook
  event_types: [root_cause.analysis.requested.v1]
  flow_id: ${payload.flow_id}

- action_key: boi.search.mcp
  type: mcp_tool
  event_types: [report.requested.v1]
  tool_name: boi.search
  arguments:
    query: ${payload.query}
    employee_id: ${employee_id}
```

## 8. v0.4 수정 요약

- 주 경로/보조 경로를 암시하는 환경 변수 제거
- Event Adapter를 `Event Router`로 재정의
- Event Router는 Action Gateway의 `/api/actions/dispatch`만 호출
- BoI 문서 생성은 `boi_materialize` Connector로 처리
- Langflow, API, Webhook, Event Publish, MCP는 모두 Action Catalog에 등록 가능한 Peer Connector로 정리
- 모든 실행 대상을 Peer Connector로 명명
