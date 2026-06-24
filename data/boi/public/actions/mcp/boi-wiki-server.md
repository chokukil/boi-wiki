---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/action-spec
title: BoI Wiki MCP Server
description: BoI Wiki 문서, OKF graph, workflow, action catalog, draft tools, promotion tools를 MCP resources/tools/prompts로 노출하는 서버 명세
tags: [MCP, BoIWiki, Agent, Tooling]
timestamp: 2026-06-18T15:40:00+09:00
boi_id: boi:public:actions:mcp:boi-wiki-server
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
action_key: boi-wiki-mcp.server
connector_kind: mcp
execution_mode: agent_server
event_types: []
risk_level: low
approval_required: false
dry_run_default: true
payload_contract:
  required: []
  optional: [employee_id, query, workflow_key, trace_id, action_key]
result_contract:
  status: mcp_available
  fields: [tools, resources, prompts]
source_refs:
  - type: repo
    ref: boi_wiki_mcp/app/main.py
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: mcp-streamable-http
method: POST
url: http://boi-wiki-mcp:8200/mcp
auth:
  type: none-for-local-poc
headers:
  Content-Type: application/json
request_schema:
  type: object
  description: MCP JSON-RPC streamable HTTP request
response_schema:
  type: object
  description: MCP JSON-RPC response
example_request:
  mcp_url: ${BOI_WIKI_MCP_EXTERNAL_URL}/mcp
  tools:
    - boi_search
    - action_invoke
    - workflow_status
    - promotion_submit
    - promotion_status
example_response:
  tools: [boi_search, boi_get, actions_search, action_invoke, workflow_start, workflow_status, promotion_submit, promotion_status]
curl: "python scripts/check_boi_wiki_mcp.py --base-url ${BOI_WIKI_MCP_EXTERNAL_URL} --mcp-url ${BOI_WIKI_MCP_EXTERNAL_URL}/mcp"
action_gateway_mapping:
  invoke_url: ${ACTION_GATEWAY_EXTERNAL_URL}/api/actions/invoke
  note: Action Gateway uses /api/mcp/call bridge for mcp_tool actions.
health_check:
  type: http
  command: curl -fsS ${BOI_WIKI_MCP_EXTERNAL_URL}/health
security_notes:
  - Local PoC uses service token only for bridge compatibility endpoint.
  - Source/body draft tools do not mutate source files or create Git commits.
  - promotion_submit requires user confirmation and remote validation before publish.
mcp_server:
  name: boi-wiki-mcp
  streamable_http_url: ${BOI_WIKI_MCP_EXTERNAL_URL}/mcp
transport: streamable_http
tool_name: boi_search
input_schema:
  type: object
output_schema:
  type: object
example_tool_call:
  tool: boi_search
  arguments:
    query: SOP
    employee_id: "100001"
---

# Summary

BoI Wiki MCP 서버는 agent가 BoI Wiki와 workflow runtime을 표준 MCP로 사용할 수 있게 하는 진입점이다. API를 직접 외우지 않고 [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)을 따르면 된다.

문서에 적힌 `url: http://boi-wiki-mcp:8200/mcp`는 Docker 내부 실행 URL이다. 사람이 복사하는 등록 URL과 smoke command는 `.env`의 `BOI_WIKI_MCP_EXTERNAL_URL`을 기준으로 만든다. 로컬 개발 기본값은 `http://localhost:8200`이고, NAS/reverse proxy 배포에서는 실제 외부 URL을 `.env`나 MCP client 설정에만 둔다.

# Available Capabilities

- BoI/OKF 문서 검색과 조회
- OKF graph 조회
- multi-action catalog 탐색과 Action Gateway invoke
- SOP workflow start/status
- source/body preview, validation, apply, auto-commit 요청
- 사용자 승인 기반 Team/Public promotion submit/status
- SOP/action/Langflow 작성 prompt

# Citations

- [MCP 기반 BoI 검색 Tool 호출 예시](/public/actions/mcp/boi-search-sample.md)
- [Multi-action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
