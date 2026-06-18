# Action Authoring Harness

Use this harness whenever an agent creates or changes an executable action. Langflow is one connector kind, not the default connector.

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
- BoI Writer: `materialization_policy`, `metadata_policy`, `enrichment_policy`.

Defaults for new actions:

- `enabled: false`
- `auto_dispatch: false`
- `dry_run_default: true`

High-risk actions must include `requires_manual_action`, and the referenced manual action must exist before the system action can be enabled.

Authoring workflow:

1. Search existing action specs via `boi-wiki-mcp` `actions_search`.
2. Choose the narrowest connector that can actually perform the work.
3. Write or update the public action-spec BoI document.
4. Draft the catalog patch.
5. Add connector-specific tests and runtime smoke evidence.
6. Keep secrets out of public docs and logs.
