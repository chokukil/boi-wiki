# Migration from v0.3 to v0.4

## What Changed

v0.3 wording implied BoI API was a secondary execution path when Langflow was not configured. v0.4 removes that mental model.

## New Model

```text
Event Broker -> Event Router -> Action Gateway -> Connector Actions
```

BoI Materializer, Langflow, API, Webhook, MCP bridge, event publishing, and future protocols are all first-class connector actions.

## Removed

- Flow-ID-first routing logic inside Event Adapter
- Secondary-path wording
- Event Adapter direct Langflow-or-BoI branching

## Added

- Event Router catalog-driven dispatch
- `boi_materialize` connector action
- `langflow_webhook` connector action type
- `mcp_tool` connector action type
- `/api/boi/materialize-from-event`
- Connector-agnostic documentation

## Required Config Change

Use:

```env
DISPATCH_EVENTS=true
MCP_BRIDGE_URL=
```

Event routing is now controlled by `data/action_catalog/actions.yaml`, not by hard-coded Flow ID priority.
