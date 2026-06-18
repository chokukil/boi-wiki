---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: MCP Bridge 호출 예시
description: BoI Wiki MCP 서버와 tool 호출을 Action Gateway allowlist로 관리하는 connector 명세
tags:
- MCP
- Bridge
- ActionGateway
timestamp: 2026-06-17 12:16:00+09:00
boi_id: boi:public:actions:mcp:bridge-sample
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: human
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: connector.mcp.sample
connector_kind: mcp
execution_mode: gateway
event_types:
- report.requested.v1
risk_level: medium
approval_required: false
dry_run_default: true
payload_contract:
  required:
  - query
  - employee_id
  optional:
  - server
  - tool
result_contract:
  status: mcp_invoked
  fields:
  - response
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: mcp-over-http
method: POST
url: http://boi-wiki-mcp:8200/api/mcp/call
auth:
  type: header
  header: x-service-token
  value: $SERVICE_TOKEN
headers:
  Content-Type: application/json
  x-service-token: $SERVICE_TOKEN
request_schema:
  type: object
  required:
  - server
  - tool
  - arguments
  properties:
    server:
      type: object
    tool:
      type: string
    arguments:
      type: object
    event:
      type: object
    boi_id:
      type: string
    request_id:
      type: string
response_schema:
  type: object
  required:
  - ok
  - status
  properties:
    ok:
      type: boolean
    status:
      const: mcp_invoked
    request_id:
      type: string
    result:
      type: object
example_request:
  server:
    name: boi-wiki-mcp
  tool: search_boi
  arguments:
    query: Kafka
    employee_id: '100001'
    allowed_visibility:
    - public
    - team
    - private
example_response:
  ok: true
  status: mcp_invoked
  tool: search_boi
  count: 1
  results:
  - title: Platform Team Kafka Event Broker SOP
curl: 'curl -X POST ''http://boi-wiki-mcp:8200/api/mcp/call'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'' -d ''{"server":{"name":"boi-wiki-mcp"},"tool":"search_boi","arguments":{"query":"Kafka","employee_id":"100001"},"request_id":"act-mcp-bridge"}'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: connector.mcp.sample
  catalog_type: mcp_bridge
  doc_ref: boi:public:actions:mcp:bridge-sample
health_check:
  type: http
  command: curl -fsS 'http://boi-wiki-mcp:8200/health'
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
mcp_server:
  name: boi-wiki-mcp
tool_name: search_boi
transport: http_bridge
input_schema:
  type: object
  required:
  - server
  - tool
  - arguments
  properties:
    server:
      type: object
    tool:
      type: string
    arguments:
      type: object
    event:
      type: object
    boi_id:
      type: string
    request_id:
      type: string
output_schema:
  type: object
  required:
  - ok
  - status
  properties:
    ok:
      type: boolean
    status:
      const: mcp_invoked
    request_id:
      type: string
    result:
      type: object
example_tool_call:
  server:
    name: boi-wiki-mcp
  tool: search_boi
  arguments:
    query: Kafka
    employee_id: '100001'
    allowed_visibility:
    - public
    - team
    - private
---

# Usage

BoI Wiki MCP 서버가 실행 중이면 Action Gateway에서 이 connector를 호출할 수 있다.
