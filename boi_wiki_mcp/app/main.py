import json
import os
from html import escape
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.responses import JSONResponse

BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_EMPLOYEE_ID = os.getenv("DEFAULT_EMPLOYEE_ID", "100001")
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100").rstrip("/")

DEFAULT_PUBLIC_BASE_URL = "http://localhost:8200"
MCP_TOOL_CAPABILITIES = [
    {"name": "boi_search", "description": "Search accessible BoI OKF documents by query, folder, event type, visibility, or BoI type."},
    {"name": "boi_get", "description": "Return one accessible BoI document by BoI ID or OKF path."},
    {"name": "okf_graph_doc", "description": "Return outgoing links and backlinks for a BoI document."},
    {"name": "actions_search", "description": "Search API, webhook, MCP, Langflow, manual, event broker, and BoI writer actions."},
    {"name": "action_get", "description": "Return one action catalog entry and its public action spec reference."},
    {"name": "action_invoke", "description": "Invoke an allowlisted Action Gateway action with approval policy preserved."},
    {"name": "workflow_start", "description": "Start a config-driven workflow from SOP metadata."},
    {"name": "workflow_status", "description": "Return workflow status for a trace."},
    {"name": "source_preview", "description": "Preview and validate a proposed Markdown/YAML source edit before applying it."},
    {"name": "source_apply", "description": "Apply a user-confirmed validated source edit and auto-commit it."},
    {"name": "doc_body_preview", "description": "Preview and validate a proposed BoI document body edit before applying it."},
    {"name": "doc_body_apply", "description": "Apply a user-confirmed validated BoI document body edit and auto-commit it."},
    {"name": "promotion_submit", "description": "Submit a user-confirmed Team/Public promotion candidate for synchronous validation and immediate publish."},
    {"name": "promotion_status", "description": "Return promotion publish, validation, HOTL, and commit status."},
]
MCP_RESOURCE_TEMPLATE_CAPABILITIES = [
    {"uri": "boi://docs/{boi_id}", "description": "Single BoI document as JSON text."},
    {"uri": "boi://folders/{folder}", "description": "BoI search results scoped to an OKF folder."},
    {"uri": "boi://actions/{action_key}", "description": "Single action catalog entry."},
    {"uri": "boi://workflows/{workflow_key}/status/{trace_id}", "description": "Workflow status for a trace."},
]
MCP_PROMPT_CAPABILITIES = [
    {"name": "create_sop_from_source", "description": "Create a BoI SOP from source material after checking existing wiki context."},
    {"name": "connect_sop_to_workflow", "description": "Connect SOP stages to event types, actions, manual handoffs, and generated BoI flow."},
    {"name": "author_action_spec", "description": "Author executable API/webhook/MCP/Langflow/manual action specs."},
    {"name": "build_langflow_boi_flow", "description": "Build a connected Langflow BoI workflow using shared components."},
    {"name": "validate_and_apply_edit", "description": "Validate source/body edits before applying and committing them."},
]
MCP_CAPABILITIES = {
    "tools": len(MCP_TOOL_CAPABILITIES),
    "resources": 0,
    "resource_templates": len(MCP_RESOURCE_TEMPLATE_CAPABILITIES),
    "prompts": len(MCP_PROMPT_CAPABILITIES),
}


async def api_get(
    path: str,
    *,
    employee_id: str | None = None,
    params: dict[str, Any] | None = None,
    service_token: bool = False,
) -> dict[str, Any]:
    query = dict(params or {})
    query.setdefault("employee_id", employee_id or DEFAULT_EMPLOYEE_ID)
    headers = {"x-service-token": SERVICE_TOKEN} if service_token else {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BOI_API_URL}{path}", params=query, headers=headers)
    try:
        body: Any = resp.json()
    except Exception:
        body = {"text": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(json.dumps({"status_code": resp.status_code, "body": body}, ensure_ascii=False))
    return body if isinstance(body, dict) else {"value": body}


async def api_post(
    path: str,
    *,
    employee_id: str | None = None,
    payload: dict[str, Any] | None = None,
    service_token: bool = False,
) -> dict[str, Any]:
    params = {"employee_id": employee_id or DEFAULT_EMPLOYEE_ID}
    headers = {"x-service-token": SERVICE_TOKEN} if service_token else {}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{BOI_API_URL}{path}", params=params, headers=headers, json=payload or {})
    try:
        body: Any = resp.json()
    except Exception:
        body = {"text": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(json.dumps({"status_code": resp.status_code, "body": body}, ensure_ascii=False))
    return body if isinstance(body, dict) else {"value": body}


def as_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


mcp = FastMCP(
    "boi-wiki-mcp",
    instructions=(
        "BoI Wiki MCP exposes OKF BoI documents, action catalog specs, workflow status, "
        "validated source/body editing, user-confirmed promotion publishing, and SOP/action/Langflow authoring prompts."
    ),
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)


@mcp.tool(name="boi_search")
async def boi_search(
    query: str = "",
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    folder: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> dict[str, Any]:
    """Search accessible BoI OKF documents."""
    return await boi_search_impl(query, employee_id, folder, event_type, visibility, boi_type)


async def boi_search_impl(
    query: str = "",
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    folder: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
    service_token: bool = False,
) -> dict[str, Any]:
    return await api_get(
        "/api/boi",
        employee_id=employee_id,
        params={"q": query, "folder": folder, "event_type": event_type, "visibility": visibility, "boi_type": boi_type},
        service_token=service_token,
    )


@mcp.tool(name="boi_get")
async def boi_get(boi_id: str, employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Return a single accessible BoI document by BoI ID or OKF path."""
    return await boi_get_impl(boi_id, employee_id)


async def boi_get_impl(boi_id: str, employee_id: str = DEFAULT_EMPLOYEE_ID, service_token: bool = False) -> dict[str, Any]:
    docs = await boi_search_impl(query="", employee_id=employee_id, service_token=service_token)
    for item in docs.get("items", []):
        metadata = item.get("metadata") or {}
        candidates = {str(metadata.get("boi_id") or ""), str(item.get("uri") or "").strip("/")}
        if boi_id in candidates or boi_id.strip("/") in candidates:
            return {"ok": True, "item": item}
    raise RuntimeError(f"BoI not found or not accessible: {boi_id}")


@mcp.tool(name="okf_graph_doc")
async def okf_graph_doc(boi_id: str, employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Return outgoing links and backlinks for a BoI document."""
    return await api_get(f"/api/okf/graph/doc/{boi_id}", employee_id=employee_id)


@mcp.tool(name="actions_search")
async def actions_search(
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    event_type: str = "",
    connector_kind: str = "",
    action_key: str = "",
) -> dict[str, Any]:
    """Search executable action catalog entries across API, webhook, MCP, Langflow, manual, event broker, and BoI writer connectors."""
    return await actions_search_impl(employee_id, event_type, connector_kind, action_key)


async def actions_search_impl(
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    event_type: str = "",
    connector_kind: str = "",
    action_key: str = "",
    service_token: bool = False,
) -> dict[str, Any]:
    body = await api_get("/api/actions/catalog", employee_id=employee_id, params={"event_type": event_type}, service_token=service_token)
    items = body.get("items", [])
    if connector_kind:
        items = [item for item in items if item.get("connector_kind") == connector_kind]
    if action_key:
        items = [item for item in items if item.get("action_key") == action_key]
    return {"count": len(items), "items": items}


@mcp.tool(name="action_get")
async def action_get(action_key: str, employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Return one action catalog entry and its public action spec reference."""
    body = await actions_search(employee_id=employee_id, action_key=action_key)
    if not body["items"]:
        raise RuntimeError(f"Action not found: {action_key}")
    return {"ok": True, "item": body["items"][0]}


@mcp.tool(name="action_invoke")
async def action_invoke(
    action_key: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    event: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    boi_id: str | None = None,
    dry_run: bool | None = True,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Invoke an allowlisted Action Gateway action. High-risk actions still require approval."""
    return await api_post(
        "/api/actions/invoke",
        employee_id=employee_id,
        payload={
            "action_key": action_key,
            "employee_id": employee_id,
            "event": event or {},
            "payload": payload or {},
            "boi_id": boi_id,
            "dry_run": dry_run,
            "approved_by": approved_by,
        },
    )


@mcp.tool(name="workflow_start")
async def workflow_start(
    workflow_key: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Start a config-driven workflow from SOP metadata."""
    body = dict(payload or {})
    if trace_id:
        body["trace_id"] = trace_id
    return await api_post(f"/api/workflows/{workflow_key}/start", employee_id=employee_id, payload=body)


@mcp.tool(name="workflow_status")
async def workflow_status(
    workflow_key: str,
    trace_id: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    graph_scope: Literal["trace", "global"] = "trace",
) -> dict[str, Any]:
    """Return workflow status for a trace."""
    return await workflow_status_impl(workflow_key, trace_id, employee_id, graph_scope)


async def workflow_status_impl(
    workflow_key: str,
    trace_id: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    graph_scope: Literal["trace", "global"] = "trace",
    service_token: bool = False,
) -> dict[str, Any]:
    return await api_get(
        f"/api/workflows/{workflow_key}/status",
        employee_id=employee_id,
        params={"trace_id": trace_id, "format": "json", "graph_scope": graph_scope},
        service_token=service_token,
    )


@mcp.tool(name="source_preview")
async def source_preview(
    path: str,
    proposed_content: str,
    base_sha256: str | None = None,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP source preview",
) -> dict[str, Any]:
    """Preview and validate a proposed source edit. This does not mutate source files."""
    return await api_post(
        "/api/source/preview",
        employee_id=employee_id,
        payload={
            "path": path,
            "base_sha256": base_sha256,
            "proposed_content": proposed_content,
            "author": author,
            "note": note,
        },
    )


@mcp.tool(name="source_apply")
async def source_apply(
    path: str,
    base_sha256: str,
    proposed_content: str,
    user_confirmed: bool,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP validated source edit",
) -> dict[str, Any]:
    """Apply a user-confirmed source edit after validation and auto-commit."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before applying a source edit")
    return await api_post(
        "/api/source/apply",
        employee_id=employee_id,
        payload={
            "path": path,
            "base_sha256": base_sha256,
            "proposed_content": proposed_content,
            "author": author,
            "note": note,
        },
    )


@mcp.tool(name="doc_body_preview")
async def doc_body_preview(
    boi_id: str,
    proposed_body: str,
    base_sha256: str | None = None,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP body preview",
) -> dict[str, Any]:
    """Preview and validate a proposed BoI document body edit."""
    return await api_post(
        f"/api/docs/{boi_id}/body-preview",
        employee_id=employee_id,
        payload={"base_sha256": base_sha256, "proposed_body": proposed_body, "author": author, "note": note},
    )


@mcp.tool(name="doc_body_apply")
async def doc_body_apply(
    boi_id: str,
    base_sha256: str,
    proposed_body: str,
    user_confirmed: bool,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP validated body edit",
) -> dict[str, Any]:
    """Apply a user-confirmed BoI document body edit after validation and auto-commit."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before applying a body edit")
    return await api_post(
        f"/api/docs/{boi_id}/body-apply",
        employee_id=employee_id,
        payload={"base_sha256": base_sha256, "proposed_body": proposed_body, "author": author, "note": note},
    )


@mcp.tool(name="promotion_submit")
async def promotion_submit(
    title: str,
    body: str,
    source_refs: list[dict[str, Any]],
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    target_visibility: Literal["team", "public"] = "team",
    team_id: str | None = None,
    description: str = "Promoted BoI",
    boi_type: str = "boi/reference",
    classification: str = "internal",
    tags: list[str] | None = None,
    source_local_id: str | None = None,
    source_sha256: str | None = None,
    reviewer: str = "hotl-curator",
    promotion_reason: str = "User explicitly requested promotion.",
    user_confirmed: bool = False,
    user_confirmed_at: str | None = None,
) -> dict[str, Any]:
    """Submit a user-confirmed Team/Public promotion candidate for validation and immediate publish."""
    return await api_post(
        "/api/promotions/submit",
        employee_id=employee_id,
        payload={
            "target_visibility": target_visibility,
            "team_id": team_id,
            "title": title,
            "description": description,
            "body": body,
            "boi_type": boi_type,
            "classification": classification,
            "tags": tags or [],
            "source_refs": source_refs,
            "source_local_id": source_local_id,
            "source_sha256": source_sha256,
            "reviewer": reviewer,
            "promotion_reason": promotion_reason,
            "user_confirmed": user_confirmed,
            "user_confirmed_at": user_confirmed_at,
        },
    )


@mcp.tool(name="promotion_status")
async def promotion_status(
    promotion_id: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
) -> dict[str, Any]:
    """Return promotion publish, validation, HOTL, and commit status."""
    return await api_get(f"/api/promotions/{promotion_id}", employee_id=employee_id)


@mcp.resource("boi://docs/{boi_id}")
async def boi_doc_resource(boi_id: str) -> str:
    """Read one BoI document as JSON text."""
    return as_text(await boi_get(boi_id, DEFAULT_EMPLOYEE_ID))


@mcp.resource("boi://folders/{folder}")
async def boi_folder_resource(folder: str) -> str:
    """Read a folder listing as JSON text."""
    return as_text(await boi_search(employee_id=DEFAULT_EMPLOYEE_ID, folder=folder))


@mcp.resource("boi://actions/{action_key}")
async def action_resource(action_key: str) -> str:
    """Read an action catalog entry as JSON text."""
    return as_text(await action_get(action_key, DEFAULT_EMPLOYEE_ID))


@mcp.resource("boi://workflows/{workflow_key}/status/{trace_id}")
async def workflow_status_resource(workflow_key: str, trace_id: str) -> str:
    """Read workflow status as JSON text."""
    return as_text(await workflow_status(workflow_key, trace_id, DEFAULT_EMPLOYEE_ID))


@mcp.prompt(name="create_sop_from_source")
def create_sop_from_source(domain: str = "", target_visibility: str = "private") -> str:
    """Prompt for converting user-provided SOP images/docs into BoI Wiki OKF workflow packages."""
    return (
        "Use BoI Wiki MCP resources before writing. Search existing SOPs, event types, actions, manuals, and harness docs. "
        f"Create a {target_visibility} BoI SOP package for domain '{domain}'. Include SOP frontmatter, workflow.stages, "
        "event type docs, action specs for API/Webhook/MCP/Langflow/Manual/Event Broker as needed, citations, OKF links, "
        "and validated source edits. For Team/Public publication use promotion_submit only after user preview approval."
    )


@mcp.prompt(name="connect_sop_to_workflow")
def connect_sop_to_workflow(workflow_key: str) -> str:
    """Prompt for connecting an SOP to the config-driven workflow runtime."""
    return (
        f"Connect SOP workflow '{workflow_key}' to BoI Wiki runtime. Verify workflow.stages, event catalog entries, "
        "action catalog mappings, manual approvals, Langflow only if needed, workflow_start/status routes, and generated BoI links."
    )


@mcp.prompt(name="author_action_spec")
def author_action_spec(connector_kind: str) -> str:
    """Prompt for authoring executable action specs."""
    return (
        f"Author a connector_kind={connector_kind} action package. Include public action-spec BoI doc, catalog draft, "
        "request/response schemas, examples, approval policy, security notes, health check, and tests. "
        "Support API, webhook, MCP, Langflow, manual, event_broker, and boi_writer patterns."
    )


@mcp.prompt(name="build_langflow_boi_flow")
def build_langflow_boi_flow(flow_purpose: str = "stage analysis") -> str:
    """Prompt for building a connected Langflow workflow using BoI components."""
    return (
        f"Build or update a connected Langflow BoI flow for {flow_purpose}. Use BoIContextNormalizer, "
        "BoIHarnessLoader/BoIWikiReader, LLM, BoIMetadataBuilder/BoIPolicyGuard when writing is required, "
        "and BoIActionInvoker only for allowlisted actions. Audit disconnected nodes and duplicate flows."
    )


@mcp.prompt(name="validate_and_apply_edit")
def validate_and_apply_edit(scope: str = "BoI Wiki change") -> str:
    """Prompt for validating source/body edits before applying and committing."""
    return (
        f"Validate {scope}: apply only after base_sha256 still matches and user confirmation is explicit. Run source validation, "
        "OKF lint, catalog checks, secret scan, focused tests, E2E smoke when runtime-affecting, then commit with a concise message."
    )


class McpBridgeRequest(BaseModel):
    server: dict[str, Any] = Field(default_factory=dict)
    tool: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    request_id: str | None = None


app = mcp.streamable_http_app()


def first_forwarded_value(value: str | None) -> str:
    return str(value or "").split(",", 1)[0].strip()


def public_base_url(request: Request | None = None) -> str:
    configured = str(os.getenv("BOI_WIKI_MCP_EXTERNAL_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    if request is None:
        return DEFAULT_PUBLIC_BASE_URL
    proto = first_forwarded_value(request.headers.get("x-forwarded-proto")) or request.url.scheme
    host = first_forwarded_value(request.headers.get("x-forwarded-host")) or first_forwarded_value(request.headers.get("host"))
    if not host:
        host = request.url.netloc
    forwarded_port = first_forwarded_value(request.headers.get("x-forwarded-port"))
    if forwarded_port and ":" not in host:
        host = f"{host}:{forwarded_port}"
    return f"{proto}://{host}".rstrip("/")


def status_payload(request: Request | None = None) -> dict[str, Any]:
    base_url = public_base_url(request)
    return {
        "status": "ok",
        "service": "boi-wiki-mcp",
        "public_base_url": base_url,
        "mcp_endpoint": f"{base_url}/mcp",
        "bridge_endpoint": f"{base_url}/api/mcp/call",
        "health_endpoint": f"{base_url}/health",
        "protocol": "MCP Streamable HTTP",
        "capabilities": MCP_CAPABILITIES,
        "capability_lists": {
            "tools": MCP_TOOL_CAPABILITIES,
            "resources": [],
            "resource_templates": MCP_RESOURCE_TEMPLATE_CAPABILITIES,
            "prompts": MCP_PROMPT_CAPABILITIES,
        },
        "notes": [
            "Open / in a browser for this status page.",
            "Do not use a browser to validate /mcp directly; MCP clients must send Streamable HTTP Accept headers.",
            "A direct browser/curl request to /mcp may return 406 even when the server is healthy.",
            "Static resources are intentionally empty; use resource templates and tools.",
        ],
    }


async def status_page(request: Request) -> HTMLResponse:
    payload = status_payload(request)
    capabilities = payload["capabilities"]
    capability_lists = payload["capability_lists"]

    def render_items(items: list[dict[str, str]], key: str) -> str:
        if not items:
            return "<p class=\"muted\">No static resources are exposed. Use resource templates and tools.</p>"
        rows = []
        for item in items:
            name = escape(str(item.get(key) or item.get("name") or ""))
            description = escape(str(item.get("description") or ""))
            rows.append(f"<li><code>{name}</code><span>{description}</span></li>")
        return "<ul class=\"capability-list\">" + "".join(rows) + "</ul>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BoI Wiki MCP Status</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f6f8fb; color: #172033; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 40px 24px; }}
    section {{ background: #fff; border: 1px solid #d9e1ec; border-radius: 8px; padding: 20px; margin: 16px 0; }}
    h1 {{ margin-top: 0; }}
    code {{ background: #eef3f9; border: 1px solid #d5dfeb; border-radius: 4px; padding: 2px 6px; overflow-wrap: anywhere; word-break: break-word; }}
    dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 8px 16px; }}
    dt {{ font-weight: 700; }}
    .capability-list {{ list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 8px; }}
    .capability-list li {{ display: grid; grid-template-columns: minmax(260px, 38%) minmax(0, 1fr); gap: 10px; align-items: start; padding: 8px 0; border-top: 1px solid #eef2f7; }}
    .capability-list span {{ min-width: 0; }}
    .muted {{ color: #607086; }}
    .ok {{ color: #047857; font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <h1>BoI Wiki MCP</h1>
    <p class="ok">Status: ok</p>
    <section>
      <h2>Endpoints</h2>
      <dl>
        <dt>MCP Streamable HTTP</dt><dd><code>{payload["mcp_endpoint"]}</code></dd>
        <dt>Bridge endpoint</dt><dd><code>{payload["bridge_endpoint"]}</code></dd>
        <dt>Health check</dt><dd><code>{payload["health_endpoint"]}</code></dd>
      </dl>
    </section>
    <section>
      <h2>Capabilities</h2>
      <dl>
        <dt>Tools</dt><dd>{capabilities["tools"]}</dd>
        <dt>Resources</dt><dd>{capabilities["resources"]}</dd>
        <dt>Resource templates</dt><dd>{capabilities["resource_templates"]}</dd>
        <dt>Prompts</dt><dd>{capabilities["prompts"]}</dd>
      </dl>
      <h3>Tools</h3>
      {render_items(capability_lists["tools"], "name")}
      <h3>Resource templates</h3>
      {render_items(capability_lists["resource_templates"], "uri")}
      <h3>Prompts</h3>
      {render_items(capability_lists["prompts"], "name")}
    </section>
    <section>
      <h2>Client Registration</h2>
      <p>Register <code>{payload["mcp_endpoint"]}</code> as a Streamable HTTP MCP server in Codex, Claude Desktop, or Cursor.</p>
      <p>Opening <code>/mcp</code> directly in a browser is not a valid MCP check. It can return <code>406</code> because the client did not send the required MCP Accept headers.</p>
    </section>
  </main>
</body>
</html>
"""
    return HTMLResponse(html)


async def health(request: Request) -> JSONResponse:
    return JSONResponse(status_payload(request))


async def status_json(request: Request) -> JSONResponse:
    return JSONResponse(status_payload(request))



def parse_bridge_request(data: Any) -> McpBridgeRequest:
    if hasattr(McpBridgeRequest, "model_validate"):
        return McpBridgeRequest.model_validate(data)
    return McpBridgeRequest.parse_obj(data)


async def mcp_bridge_call(request: Request) -> JSONResponse:
    if request.headers.get("x-service-token") != SERVICE_TOKEN:
        return JSONResponse({"detail": "invalid service token"}, status_code=401)
    try:
        req = parse_bridge_request(await request.json())
    except (json.JSONDecodeError, ValidationError) as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)
    tool_name = (req.tool or "").replace(".", "_").replace("-", "_")
    args = dict(req.arguments or {})
    employee_id = str(args.get("employee_id") or DEFAULT_EMPLOYEE_ID)
    if tool_name in {"boi_search", "search_boi", "boi_search_sample"}:
        result = await boi_search_impl(query=str(args.get("query") or ""), employee_id=employee_id, service_token=True)
    elif tool_name == "boi_get":
        result = await boi_get_impl(str(args.get("boi_id") or req.boi_id or ""), employee_id=employee_id, service_token=True)
    elif tool_name == "workflow_status":
        result = await workflow_status_impl(
            str(args.get("workflow_key") or ""),
            str(args.get("trace_id") or ""),
            employee_id=employee_id,
            service_token=True,
        )
    elif tool_name == "actions_search":
        result = await actions_search_impl(employee_id=employee_id, connector_kind=str(args.get("connector_kind") or ""), service_token=True)
    else:
        return JSONResponse({"detail": f"unsupported MCP bridge tool: {req.tool}"}, status_code=400)
    return JSONResponse(
        {"ok": True, "status": "mcp_invoked", "tool": req.tool, "request_id": req.request_id, "response": result}
    )


app.add_route("/", status_page, methods=["GET"])
app.add_route("/status", status_page, methods=["GET"])
app.add_route("/status.json", status_json, methods=["GET"])
app.add_route("/health", health, methods=["GET"])
app.add_route("/api/mcp/call", mcp_bridge_call, methods=["POST"])
