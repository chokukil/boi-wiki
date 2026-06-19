# BoI Wiki

BoI Wiki is an OKF-based AI Native Workflow knowledge/runtime system.

This repository is the shared runtime:

- BoI Wiki Web UI and BoI API
- Kafka Event Broker and Event Router
- Action Gateway for API, Webhook, MCP, Langflow, Manual, Event Broker, and BoI Writer actions
- BoI Wiki MCP server for agents
- Langflow reference flows and BoI custom component integration
- OKF Markdown source documents, action catalog, event catalog, and runtime smoke tests

For personal Local Private work, use the separate lightweight workspace repository:

```text
/home/chokukil/boi-wiki-local
```

`boi-wiki-local` is intentionally not a Web runtime. It is a local OKF Markdown workspace plus Codex/Claude/Cursor harness files.

## Purpose

This PoC demonstrates an AI Native Workflow backbone where:

- Kafka acts as the actual Event Broker.
- Event Router consumes business events from Kafka.
- Action Gateway dispatches each event to registered connector actions.
- Connectors can be BoI Writer, Langflow Webhook, HTTP API, generic Webhook, MCP bridge, or future protocols.
- BoI Wiki stores SOPs, event-linked work context, analysis results, action drafts, reusable organizational knowledge, and draft-only edits that are applied by agents after validation.

The current design intentionally removes the idea of a secondary path. BoI Writer is not a secondary path. It is a first-class connector equal to Langflow, API, Webhook, MCP, and future connector types.

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
- BoI Wiki MCP status: http://localhost:8200/
- BoI Wiki MCP Streamable HTTP: http://localhost:8200/mcp
- Kafka UI: http://localhost:8081
- Langflow: http://localhost:7860

Default auth is `BOI_AUTH_MODE=dev`, which keeps the local `employee_id` selector/query for PoC and tests.

## Repository Split

| Repo | Role | Audience |
|---|---|---|
| `/home/chokukil/boi-wiki` | Shared runtime, source of truth, Web/MCP/API services, test suite | Developers, operators, shared Wiki agents |
| `/home/chokukil/boi-wiki-local` | Local Private OKF workspace and agent harness | General users using Codex, Claude, Cursor |

Shared Web Private and Local Private are different.

- Web Private is stored under this runtime's `DATA_ROOT` and is visible only to the authenticated employee in Web BoI Wiki.
- Local Private is stored in `boi-wiki-local` on the user's PC and is not scanned by this Web BoI Wiki.
- Local Private sharing requires explicit user confirmation and creates only a remote draft. Final source changes still require shared repo validation and commit.

## BoI Wiki MCP

BoI Wiki MCP lets Codex, Claude Desktop, Cursor, Langflow, and custom agents use BoI Wiki through one MCP server instead of memorizing REST routes.

- Human status page: http://localhost:8200/
- MCP Streamable HTTP endpoint: http://localhost:8200/mcp
- Bridge compatibility endpoint: http://localhost:8200/api/mcp/call
- Manual: http://localhost:8000/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp?employee_id=100001

Do not validate MCP by opening `/mcp` directly in a browser. A direct browser or plain curl request can return `406 Not Acceptable` because it is missing MCP Streamable HTTP headers. Use the status page or the smoke check:

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --summary
```

For Codex, Claude Desktop, or Cursor registration details:

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --details \
  --client-checklist
```

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
- Local Private agent harness: http://localhost:8000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001
- Web draft editing: http://localhost:8000/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001

Web source edits are draft-only. `Save Draft` does not change the original Markdown/YAML and does not create a Git commit. An agent must validate, apply, test, and commit the draft separately.

## BoI Wiki Local

Use BoI Wiki Local when a general user wants a personal Local Private workspace without installing Python, Docker, Git, or MCP.

The local repository path created in this environment is:

```text
/home/chokukil/boi-wiki-local
```

In a user environment, the intended install experience is simple: give the `boi-wiki-local` repo URL to an agent and say:

```text
이 repo 설치해줘.
이 폴더를 BoI Wiki Local로 써줘.
이 회의 내용을 BoI로 정리해줘.
```

Local Private documents stay under the user's local workspace and are not scanned by this Web BoI Wiki `DATA_ROOT`. Remote sharing requires an explicit user confirmation and creates only a shared BoI Wiki draft; final source changes still require agent validation, tests, and Git commit in this shared runtime repo.

Manuals:

- Local Private overview: http://localhost:8000/docs/boi:public:boi-wiki-manual:local-private:overview?employee_id=100001
- Local Private harness: http://localhost:8000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001

## Validation

Shared repo validation:

```bash
python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links
pytest tests -q -s
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
```

Local users are not expected to run these commands. In `boi-wiki-local`, the agent harness performs Level 0 self-checks and runs `check.sh` or `check.ps1` when possible.

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

Supported connector action types:

| Type | Meaning |
|---|---|
| `boi_materialize` | Create a BoI document from a business event |
| `langflow_webhook` | Call a Langflow Webhook Flow |
| `http` / `api` | Call a REST-style internal API |
| `webhook` / `internal_webhook` | Call a generic webhook |
| `mcp_tool` | Invoke an MCP tool through the BoI Wiki MCP bridge or configured MCP-compatible endpoint |
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
| MCP bridge/server | Internal MCP bridge/server and approved MCP endpoints |
| Dry-run high-risk actions | Human approval and change-management workflow |

## Security Defaults

- Webhook/API calls require service token or API key.
- User identity comes from Keycloak/HCP in SSO mode; query `employee_id` is development-only.
- Action Gateway uses allowlisted hosts.
- High-risk actions are approval-required.
- Private BoI is scoped to employee ID.
- Team/Public promotion is copy-not-move.
- Team/Public BoI starts as draft.
