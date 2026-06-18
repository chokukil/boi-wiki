# BoI PoC Kit v0.4

## Purpose

This PoC demonstrates an AI Native Workflow backbone where:

- Kafka acts as the actual Event Broker.
- Event Router consumes business events from Kafka.
- Action Gateway dispatches each event to registered connector actions.
- Connectors can be BoI Writer, Langflow Webhook, HTTP API, generic Webhook, MCP bridge, or future protocols.
- BoI Wiki stores SOPs, event-linked work context, analysis results, action drafts, and reusable organizational knowledge.

The v0.4 design intentionally removes the idea of a secondary path. BoI Writer is not a secondary path. It is a first-class connector equal to Langflow, API, Webhook, MCP, and future connector types.

```text
Business Event
  -> Kafka Event Broker
  -> Event Router
  -> Action Gateway
       -> BoI Writer Connector
       -> Langflow Webhook Connector
       -> HTTP API Connector
       -> Generic Webhook Connector
       -> MCP bridge Connector
       -> Future Connector
  -> BoI Wiki / API Results / Next Events
```

## Quick Start

```bash
cp .env.example .env
docker compose up -d --build
```

Open:

- BoI Wiki: http://localhost:8000/?employee_id=100001
- Event Types: http://localhost:8000/event-types?employee_id=100001
- Event Stream: http://localhost:8000/events?employee_id=100001
- SOPs: http://localhost:8000/sops?employee_id=100001
- Action Gateway: http://localhost:8100/docs
- Kafka UI: http://localhost:8081
- Langflow: http://localhost:7860

Default auth is `BOI_AUTH_MODE=dev`, which keeps the local `employee_id` selector/query for PoC and tests.

## SSO Dev Mode

To exercise the SK hynix-style Keycloak/HCP path locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.sso-dev.yml up -d --build
```

Open:

- BoI Wiki SSO login: http://localhost:8000/auth/login
- Keycloak dev realm: http://localhost:8088
- Langflow Hynix SSO UI: http://localhost:7860

The dev realm seeds users `100001`, `100002`, and `100003` with password `password`. `100001` has both `aix-tf` and `platform` teams plus admin roles. `100002` has only `aix-tf`; `100003` has only `platform`.

In `BOI_AUTH_MODE=keycloak`, `employee_id` query spoofing is rejected. Internal Event Router, Action Gateway, and MCP bridge calls must use `x-service-token` plus the target actor `employee_id`.

The SSO dev overlay is aligned with the `langflow-hynix` Keycloak/HCP model:

- Langflow reads `KEYCLOAK_HCP_API_URL`, `KEYCLOAK_ALLOWED_EMPLOYEE`, `KEYCLOAK_EMPLOYEE_CLAIM`, and `KEYCLOAK_SHARED_USERNAME`.
- BoI Wiki accepts the same `KEYCLOAK_*` aliases while keeping `BOI_*` names for Wiki-specific settings.
- Mock HCP exposes both `GET /api/permissions?employee_id=...` for BoI Wiki and `GET /v1/projects/{project}/roles` for Langflow-Hynix.
- Workflow start, action invoke, draft write, and promotion are role-gated by `boi.workflow_runner`, `boi.action_invoker`, `boi.editor`, and `boi.promoter`.

## Using the BoI Harness

The harness documents define how Codex, Claude, Langflow, and custom agents should create or change curated BoI Wiki knowledge.

- Repo source: `harness/README.md`
- BoI Wiki entry: http://localhost:8000/docs/boi:public:harness:overview?employee_id=100001
- SOP authoring: http://localhost:8000/docs/boi:public:harness:sop-authoring-harness?employee_id=100001
- Action authoring: http://localhost:8000/docs/boi:public:harness:action-authoring-harness?employee_id=100001
- Web draft editing: http://localhost:8000/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001

Web source edits are draft-only. `Save Draft` does not change the original Markdown/YAML and does not create a Git commit. An agent must validate, apply, test, and commit the draft separately.

## Key Concepts

### Event Broker

Kafka transports business events such as:

- `meeting.closed.v1`
- `action.created.v1`
- `report.requested.v1`
- `promotion.requested.v1`
- `equipment.alarm.raised.v1`
- `trend.anomaly.detected.v1`
- `root_cause.analysis.requested.v1`
- `maintenance.guide.requested.v1`
- `corrective_action.requested.v1`

### Event Router

The Event Router is protocol-agnostic. It does not decide that Langflow is primary or BoI API is secondary. It reads the event type and dispatches to registered connector actions through Action Gateway.

### Action Gateway

Action Gateway is the connector abstraction layer. Connector actions are defined in:

```text
data/action_catalog/actions.yaml
```

Supported connector action types in v0.4:

| Type | Meaning |
|---|---|
| `boi_materialize` | Create a BoI document from a business event |
| `langflow_webhook` | Call a Langflow Webhook Flow |
| `http` / `api` | Call a REST-style internal API |
| `webhook` / `internal_webhook` | Call a generic webhook |
| `mcp_tool` | Invoke an MCP tool through a future internal MCP bridge |
| `boi_event` | Publish a next business event into Kafka |
| `mock_api` | PoC-visible system/API call result |

### BoI Wiki

BoI Wiki is the human and agent-facing knowledge surface. It shows:

- Public SOPs and common documents
- Team BoI documents based on employee/team ACL
- Web-created Private BoI documents for the current employee
- Event Type Catalog
- Event Stream
- Event-linked BoI documents

Local-only Private BoI created by a local agent is intentionally not shown in the Web BoI Wiki.

## Demo: Equipment Anomaly SOP Workflow

Start the SOP workflow:

```bash
curl -X POST "http://localhost:8000/api/workflows/demo/equipment-anomaly/start?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{"equipment_id":"ETCH-VM-01","alarm_code":"RESPONSE_CHAIN_ABNORMAL","title":"Response Chain 이상 Alarm 발생"}'
```

Then check:

- Event Stream: http://localhost:8000/events?employee_id=100001
- Event-linked BoI: http://localhost:8000/?employee_id=100001&event_type=equipment.alarm.raised.v1
- Action logs: http://localhost:8100/api/actions/logs

## Connector Configuration Example

```yaml
- action_key: boi.materialize_event
  type: boi_materialize
  enabled: true
  event_types: ["*"]
  risk_level: low
  approval_required: false
  dry_run_default: false

- action_key: langflow.meeting_writer.sample
  type: langflow_webhook
  enabled: false
  event_types: [meeting.closed.v1]
  flow_id: ${payload.langflow_flow_id}
  risk_level: low
  approval_required: false

- action_key: mcp.boi_search.sample
  type: mcp_tool
  enabled: false
  event_types: [report.requested.v1]
  tool_name: boi.search
  arguments:
    query: ${payload.query}
    employee_id: ${employee_id}
```

## Intranet Migration Notes

Replace PoC pieces with enterprise services:

| PoC | Intranet Target |
|---|---|
| Hardcoded employee/team map | SSO/IAM/HR organization data |
| File-based BoI Wiki | Internal document/Wiki/Git/SharePoint store |
| Mock APIs | TAS, HyVIS, equipment, approval, notification APIs |
| Development keys | Secret Manager |
| `BOI_AUTH_MODE=dev` | Keycloak SSO + HCP permission API |
| MCP planned connector | Internal MCP bridge/server once approved |
| Dry-run high-risk actions | Human approval and change-management workflow |

## Security Defaults

- Webhook/API calls require service token or API key.
- User identity comes from Keycloak/HCP in SSO mode; query `employee_id` is development-only.
- Action Gateway uses allowlisted hosts.
- High-risk actions are approval-required.
- Private BoI is scoped to employee ID.
- Team/Public promotion is copy-not-move.
- Team/Public BoI starts as draft.
