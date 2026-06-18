import json
import os
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_EMPLOYEE_ID = os.getenv("DEFAULT_EMPLOYEE_ID", "100001")
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100").rstrip("/")


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
        "draft-only editing, and SOP/action/Langflow authoring prompts."
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


@mcp.tool(name="source_create_draft")
async def source_create_draft(
    path: str,
    base_sha256: str,
    proposed_content: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP source draft",
) -> dict[str, Any]:
    """Create a draft-only source edit. This never mutates source files or commits Git changes."""
    return await api_post(
        "/api/source/drafts",
        employee_id=employee_id,
        payload={
            "path": path,
            "base_sha256": base_sha256,
            "proposed_content": proposed_content,
            "author": author,
            "note": note,
        },
    )


@mcp.tool(name="doc_body_create_draft")
async def doc_body_create_draft(
    boi_id: str,
    base_sha256: str,
    proposed_body: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP body draft",
) -> dict[str, Any]:
    """Create a draft-only body edit for a BoI document."""
    return await api_post(
        f"/api/docs/{boi_id}/body-drafts",
        employee_id=employee_id,
        payload={"base_sha256": base_sha256, "proposed_body": proposed_body, "author": author, "note": note},
    )


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
        "and draft-only source patches. Do not commit until OKF lint, tests, and smoke checks pass."
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


@mcp.prompt(name="validate_and_commit_draft")
def validate_and_commit_draft(scope: str = "BoI Wiki change") -> str:
    """Prompt for validating draft edits before applying and committing."""
    return (
        f"Validate {scope}: apply draft only after base_sha256 still matches, run source validation, OKF lint, catalog checks, "
        "secret scan, focused tests, E2E smoke when runtime-affecting, then commit with a concise message."
    )


class McpBridgeRequest(BaseModel):
    server: dict[str, Any] = Field(default_factory=dict)
    tool: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    request_id: str | None = None


app = mcp.streamable_http_app()


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "boi-wiki-mcp"})


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


app.add_route("/health", health, methods=["GET"])
app.add_route("/api/mcp/call", mcp_bridge_call, methods=["POST"])
