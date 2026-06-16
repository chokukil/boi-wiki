# BoI PoC Kit v0.4 Connector-Agnostic Architecture

## 1. Design Correction

v0.4 removes the assumption that one connector is the primary path and another connector is a secondary path. The correct model is:

```text
Event Broker -> Event Router -> Action Gateway -> Connector Actions
```

Every invocation method is a first-class connector action:

- BoI Writer Connector
- Langflow Webhook Connector
- HTTP API Connector
- Generic Webhook Connector
- MCP bridge Connector
- Future Connector

## 2. Why This Matters

The purpose of the PoC is not to force work through Langflow only. Langflow is one Agent Builder execution channel. The PoC must also support system APIs, webhooks, MCP-style tool interfaces, and future integration styles.

This matches the target operating model:

```text
SOP / Business Event
  -> Event Type
  -> Connector Actions
  -> BoI evidence/result
  -> Next Event
  -> Human/Agent decision
```

## 3. Event Router Responsibility

The Event Router consumes Kafka events and asks Action Gateway which connector actions are registered for the event type. It then invokes those connector actions in catalog order.

The router does not know or care whether the target is Langflow, API, Webhook, BoI Writer, MCP bridge, or a future protocol.

## 4. Action Gateway Responsibility

Action Gateway is the protocol abstraction layer. It validates action catalog entries, enforces host allowlists and approval rules, invokes connectors, and writes action logs.

Supported v0.4 connector action types:

| Type | Description |
|---|---|
| `boi_materialize` | Create a BoI document from an event |
| `langflow_webhook` | Call Langflow Webhook endpoint |
| `http` / `api` | Call REST-style API |
| `webhook` / `internal_webhook` | Call generic webhook |
| `mcp_tool` | Call an MCP bridge when configured |
| `boi_event` | Publish a next event to Kafka |
| `mock_api` | PoC-visible API simulation |

## 5. BoI Writer Connector

BoI Writer is an explicit connector action. It materializes event context into OKF-style BoI documents. It is not a secondary route.

Endpoint:

```text
POST /api/boi/materialize-event
```

Legacy compatibility endpoint:

```text
POST /api/events/handle
```

Both are first-class materialization endpoints in v0.4.

## 6. MCP Extension Point

The v0.4 package includes an `mcp_tool` connector type. In the PoC it records a planned invocation unless `MCP_BRIDGE_URL` is configured.

The intended production pattern is:

```text
Action Gateway -> Internal MCP bridge -> MCP Server -> Tool/Resource/Prompt
```

The MCP bridge should handle session initialization, authentication, transport details, tool discovery, and tool invocation. The Event Router should not be rewritten when MCP is introduced.

## 7. SOP Workflow Pattern

Example: Equipment anomaly SOP

```text
equipment.alarm.raised.v1
  -> BoI Writer Connector creates boi/sop-instance
  -> API Connector requests trend/raw data
  -> Event Publish Connector emits root_cause.analysis.requested.v1
  -> BoI Writer Connector creates boi/analysis
  -> API/Webhook Connector requests maintenance guide
  -> Event Publish Connector emits corrective_action.requested.v1
  -> BoI Writer Connector creates boi/action
  -> High-risk actions require human approval
```

## 8. Migration Principle

When a new invocation method appears, add a new connector type or bridge inside Action Gateway. Do not change the Event Broker, Event Router, BoI Wiki, or SOP model.

