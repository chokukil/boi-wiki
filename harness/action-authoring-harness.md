# Action Authoring Harness

Use this harness whenever an agent creates or changes an executable action.

Required common fields:

- `action_key`
- `connector_kind`
- `type`
- `execution_mode`
- `doc_ref`
- `event_types`
- `risk_level`
- `approval_required`
- `auto_dispatch`
- `owner`

Connector-specific fields:

- API/Webhook: `method`, `url`, `auth`, `headers`, `request_schema`, `response_schema`, `example_request`, `example_response`, `curl`, `health_check`.
- MCP: `mcp_server`, `tool_name`, `transport`, `input_schema`, `output_schema`, `example_tool_call`.
- Langflow: `flow_name`, `endpoint_name`, `run_url`, `required_components`, `input_value_template`, `result_boi_policy`.
- Manual: `manual_task`, `assignee_role`, `checklist`, `completion_contract`, `approval_policy`.
- Event Broker: `emits_event_type`, `event_body_template`, `trace_policy`.

Defaults for new actions:

- `enabled: false`
- `auto_dispatch: false`
- `dry_run_default: true`

High-risk actions must include `requires_manual_action`, and the referenced manual action must exist before the system action can be enabled.
