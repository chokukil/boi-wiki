import json
import os
from html import escape
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.responses import JSONResponse

BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_EMPLOYEE_ID = os.getenv("DEFAULT_EMPLOYEE_ID", "100001")
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100").rstrip("/")
MCP_BACKEND_TIMEOUT_SECONDS = float(os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "120"))
MCP_REQUIRE_SERVICE_TOKEN = str(os.getenv("MCP_REQUIRE_SERVICE_TOKEN", "false")).strip().lower() in {"1", "true", "yes", "on"}

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
    {"name": "boi_agent_chat", "description": "Ask the page-aware BoI Agent using ontology search, dictionary, memory, inbox context, and BoI ACL guardrails."},
    {"name": "boi_agent_suggestions", "description": "Return recommended questions for a current BoI Wiki page context."},
    {"name": "ontology_search", "description": "Search the business knowledge graph across Dictionary, SOP, Event Types, Actions, BoI docs, and runtime evidence."},
    {"name": "dictionary_resolve", "description": "Resolve business terms and aliases with private, team, then public priority."},
    {"name": "dictionary_terms", "description": "List accessible BoI dictionary terms by scope."},
    {"name": "agent_memory_search", "description": "Search private Agent Memory BoI documents for the employee."},
    {"name": "agent_inbox", "description": "Return open manual/approval/follow-up action tasks for an employee."},
    {"name": "manual_handoff_complete", "description": "Append a user-confirmed manual handoff completion row."},
    {"name": "rbac_me", "description": "Return the employee's BoI Wiki teams, roles, and permission-management capability."},
    {"name": "rbac_check", "description": "Check whether an employee has a required BoI Wiki role for a scope/resource."},
    {"name": "doc_access_check", "description": "Evaluate BoI Profile ACL/classification access for one document."},
    {"name": "rbac_audit", "description": "Return recent BoI Wiki RBAC/break-glass audit rows for permission managers."},
    {"name": "event_type_draft_create", "description": "Create a user-confirmed Event Type draft and catalog patch proposal."},
    {"name": "event_type_drafts", "description": "List visible Event Type drafts for the employee."},
    {"name": "event_type_draft_validate", "description": "Revalidate an Event Type draft before catalog apply."},
    {"name": "event_type_draft_apply", "description": "Apply a user-confirmed validated Event Type draft to the Event Type catalog."},
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
    {"uri": "boi://search/ontology/{query}", "description": "Ontology-assisted grouped search results."},
    {"uri": "boi://agent/response-schema/{version}", "description": "BoI Agent response JSON Schema for API, MCP, and Web clients."},
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
AGENT_RESPONSE_CONTRACT_VERSION = "boi-agent.response.v1"
AGENT_RESPONSE_REQUIRED_FIELDS = [
    "agent_contract_version",
    "answer_markdown",
    "display_markdown",
    "links",
    "citations",
    "artifacts",
    "execution_cards",
    "status_updates",
    "tool_trace",
    "access_summary",
    "guardrails_applied",
]
AGENT_ARTIFACT_TYPES = ["mermaid", "gap_table", "workflow_summary", "task_cards", "confirmation_required", "image"]
AGENT_RESPONSE_CONTRACT = {
    "version": AGENT_RESPONSE_CONTRACT_VERSION,
    "canonical_endpoint": "/api/agents/boi-wiki/chat",
    "stream_endpoint": "/api/agents/boi-wiki/chat/stream",
    "schema_endpoint": "/api/agents/boi-wiki/response-schema",
    "mcp_tool": "boi_agent_chat",
    "mcp_resource_template": "boi://agent/response-schema/{version}",
    "consumers": ["web_pet", "boi_wiki_mcp", "external_api"],
    "required_fields": AGENT_RESPONSE_REQUIRED_FIELDS,
    "artifact_types": AGENT_ARTIFACT_TYPES,
}
AGENT_RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://boi-wiki.local/schemas/boi-agent.response.v1.json",
    "title": "BoI Agent Response",
    "type": "object",
    "required": AGENT_RESPONSE_REQUIRED_FIELDS,
    "additionalProperties": True,
    "properties": {
        "agent_contract_version": {"const": AGENT_RESPONSE_CONTRACT_VERSION},
        "answer_markdown": {"type": "string"},
        "display_markdown": {"type": "string"},
        "answer_html": {"type": "string"},
        "links": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "citations": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "artifacts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "additionalProperties": True,
                "properties": {"type": {"enum": AGENT_ARTIFACT_TYPES}},
            },
        },
        "execution_cards": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "status_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["message"],
                "additionalProperties": True,
                "properties": {
                    "stage": {"type": "string"},
                    "message": {"type": "string"},
                    "source": {"type": "string"},
                },
            },
        },
        "tool_trace": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "coverage_report": {"type": "object", "additionalProperties": True},
        "access_summary": {"type": "object", "additionalProperties": True},
        "guardrails_applied": {"type": "array", "items": {"type": "string"}},
        "redacted_count": {"type": "integer", "minimum": 0},
        "context_summary": {"type": "object", "additionalProperties": True},
        "suggested_questions": {"type": "array", "items": {"type": "string"}},
        "route": {"type": "string"},
        "intent": {"type": "string"},
        "used_backend": {"type": "string"},
        "run_id": {"type": "string"},
    },
}
AGENT_INTERFACES = {
    "json_api": "/api/agents/boi-wiki/chat",
    "streaming_api": "/api/agents/boi-wiki/chat/stream",
    "mcp_tool": "boi_agent_chat",
    "response_contract_version": AGENT_RESPONSE_CONTRACT_VERSION,
    "streaming_protocol": "text/event-stream",
    "streaming_events": ["status", "answer_delta", "final", "error"],
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
    async with httpx.AsyncClient(timeout=MCP_BACKEND_TIMEOUT_SECONDS) as client:
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
        "ontology search, page-aware BoI Agent chat, action inbox, dictionary/memory helpers, "
        "validated source/body editing, user-confirmed promotion publishing, and SOP/action/Langflow authoring prompts. "
        "BoI API/MCP are the official external interfaces; Native BoI Agent is the production backend and direct Langflow runs are trusted/dev visual-debug paths."
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
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Invoke an allowlisted Action Gateway action. High-risk actions still require approval."""
    if dry_run is False and not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before invoking a real action")
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
            "user_confirmed": user_confirmed,
        },
    )


@mcp.tool(name="workflow_start")
async def workflow_start(
    workflow_key: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Start a config-driven workflow from SOP metadata."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before starting a workflow")
    body = dict(payload or {})
    if trace_id:
        body["trace_id"] = trace_id
    body["user_confirmed"] = user_confirmed
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


@mcp.tool(name="boi_agent_chat")
async def boi_agent_chat(
    question: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    mode: str = "auto",
    intent: str = "",
    current_url: str = "",
    selected_text: str = "",
    page_context: dict[str, Any] | None = None,
    conversation: list[dict[str, Any]] | None = None,
    save_memory: bool = True,
) -> dict[str, Any]:
    """Ask the BoI Agent through the official BoI API surface."""
    return await api_post(
        "/api/agents/boi-wiki/chat",
        employee_id=employee_id,
        payload={
            "question": question,
            "mode": mode,
            "intent": intent,
            "current_url": current_url,
            "selected_text": selected_text,
            "page_context": page_context or {},
            "conversation": conversation or [],
            "save_memory": bool(save_memory),
        },
    )


@mcp.tool(name="boi_agent_suggestions")
async def boi_agent_suggestions(
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    current_url: str = "",
    page_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return recommended BoI Agent questions for a page context."""
    return await api_post(
        "/api/agents/boi-wiki/suggestions",
        employee_id=employee_id,
        payload={"current_url": current_url, "page_context": page_context or {}},
    )


@mcp.tool(name="ontology_search")
async def ontology_search(
    query: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    scope: str = "all",
    limit: int = 8,
    current_url: str = "",
) -> dict[str, Any]:
    """Search the BoI ontology-assisted knowledge graph."""
    return await api_get(
        "/api/search/ontology",
        employee_id=employee_id,
        params={"q": query, "scope": scope, "limit": limit, "current_url": current_url},
    )


@mcp.tool(name="dictionary_resolve")
async def dictionary_resolve(query: str, employee_id: str = DEFAULT_EMPLOYEE_ID, scope: str = "all") -> dict[str, Any]:
    """Resolve dictionary terms and aliases by private, team, then public priority."""
    return await api_get("/api/dictionary/resolve", employee_id=employee_id, params={"q": query, "scope": scope})


@mcp.tool(name="dictionary_terms")
async def dictionary_terms(
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    scope: str = "all",
    query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """List accessible BoI dictionary terms."""
    return await api_get("/api/dictionary/terms", employee_id=employee_id, params={"scope": scope, "q": query, "limit": limit})


@mcp.tool(name="agent_memory_search")
async def agent_memory_search(
    query: str = "",
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    include_archived: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """Search private BoI Agent memory documents."""
    return await api_get(
        "/api/agents/boi-wiki/memory",
        employee_id=employee_id,
        params={"q": query, "include_archived": str(include_archived).lower(), "limit": limit},
    )


@mcp.tool(name="agent_inbox")
async def agent_inbox(employee_id: str = DEFAULT_EMPLOYEE_ID, status: str = "open", limit: int = 50) -> dict[str, Any]:
    """Return manual/approval/follow-up tasks for the employee."""
    return await api_get("/api/agents/boi-wiki/inbox", employee_id=employee_id, params={"status": status, "limit": limit})


@mcp.tool(name="manual_handoff_complete")
async def manual_handoff_complete(
    task_id: str,
    note: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    outcome: Literal["completed", "not_needed", "blocked"] = "completed",
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Complete a manual handoff task with explicit user confirmation."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before completing a manual handoff")
    return await api_post(
        "/api/agents/boi-wiki/manual-handoffs/complete",
        employee_id=employee_id,
        payload={"task_id": task_id, "note": note, "outcome": outcome, "user_confirmed": user_confirmed},
    )


@mcp.tool(name="rbac_me")
async def rbac_me(employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Return the employee's BoI Wiki teams, roles, and permission management capability."""
    return await api_get("/api/rbac/me", employee_id=employee_id)


@mcp.tool(name="rbac_check")
async def rbac_check(
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    required_role: str = "boi.viewer",
    scope: str = "global",
    resource: str = "",
    operation: str = "read",
    boi_id: str = "",
    action_key: str = "",
    workflow_key: str = "",
    event_type: str = "",
) -> dict[str, Any]:
    """Check whether an employee has a required BoI Wiki role for a scope/resource."""
    return await api_post(
        "/api/rbac/check",
        employee_id=employee_id,
        payload={
            "employee_id": employee_id,
            "required_role": required_role,
            "scope": scope,
            "resource": resource,
            "operation": operation,
            "boi_id": boi_id,
            "action_key": action_key,
            "workflow_key": workflow_key,
            "event_type": event_type,
        },
    )


@mcp.tool(name="doc_access_check")
async def doc_access_check(boi_id: str, employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Evaluate BoI Profile ACL/classification access for one document."""
    return await api_get(f"/api/docs/{boi_id}/access", employee_id=employee_id)


@mcp.tool(name="rbac_audit")
async def rbac_audit(employee_id: str = DEFAULT_EMPLOYEE_ID, limit: int = 100, actor: str = "", action: str = "") -> dict[str, Any]:
    """Return recent BoI Wiki RBAC/break-glass audit rows for permission managers."""
    return await api_get(
        "/api/rbac/audit",
        employee_id=employee_id,
        params={"limit": max(1, min(int(limit or 100), 500)), "actor": actor, "action": action},
    )


def event_type_draft_payload_from_args(
    *,
    event_type: str,
    name_ko: str = "",
    description: str = "",
    default_boi_type: str = "boi/event",
    default_flow_key: str = "",
    default_visibility: str = "private",
    owner: str = "",
    status: str = "draft",
    topic: str = "boi.events",
    workflow_stage: str = "",
    sop_ref: str = "",
    sop_stage_id: str = "",
    wiki_usage: str = "",
    payload_schema: dict[str, Any] | None = None,
    recommended_actions: list[str] | None = None,
    recommended_manual_actions: list[str] | None = None,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "name_ko": name_ko,
        "description": description,
        "default_boi_type": default_boi_type,
        "default_flow_key": default_flow_key,
        "default_visibility": default_visibility,
        "owner": owner,
        "status": status,
        "topic": topic,
        "workflow_stage": workflow_stage,
        "sop_ref": sop_ref,
        "sop_stage_id": sop_stage_id,
        "wiki_usage": wiki_usage,
        "payload_schema": payload_schema or {},
        "recommended_actions": recommended_actions or [],
        "recommended_manual_actions": recommended_manual_actions or [],
        "user_confirmed": user_confirmed,
    }


@mcp.tool(name="event_type_draft_create")
async def event_type_draft_create(
    event_type: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    name_ko: str = "",
    description: str = "",
    default_boi_type: str = "boi/event",
    default_flow_key: str = "",
    default_visibility: str = "private",
    owner: str = "",
    status: str = "draft",
    topic: str = "boi.events",
    workflow_stage: str = "",
    sop_ref: str = "",
    sop_stage_id: str = "",
    wiki_usage: str = "",
    payload_schema: dict[str, Any] | None = None,
    recommended_actions: list[str] | None = None,
    recommended_manual_actions: list[str] | None = None,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Create an Event Type draft. This creates a draft only and never applies the catalog patch."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before creating an Event Type draft")
    return await api_post(
        "/api/event-types/drafts",
        employee_id=employee_id,
        payload=event_type_draft_payload_from_args(
            event_type=event_type,
            name_ko=name_ko,
            description=description,
            default_boi_type=default_boi_type,
            default_flow_key=default_flow_key,
            default_visibility=default_visibility,
            owner=owner,
            status=status,
            topic=topic,
            workflow_stage=workflow_stage,
            sop_ref=sop_ref,
            sop_stage_id=sop_stage_id,
            wiki_usage=wiki_usage,
            payload_schema=payload_schema,
            recommended_actions=recommended_actions,
            recommended_manual_actions=recommended_manual_actions,
            user_confirmed=True,
        ),
    )


@mcp.tool(name="event_type_drafts")
async def event_type_drafts(employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """List visible Event Type drafts."""
    return await api_get("/api/event-types/drafts", employee_id=employee_id)


@mcp.tool(name="event_type_draft_validate")
async def event_type_draft_validate(draft_id: str, employee_id: str = DEFAULT_EMPLOYEE_ID) -> dict[str, Any]:
    """Revalidate an Event Type draft before catalog apply."""
    return await api_post(f"/api/event-types/drafts/{draft_id}/validate", employee_id=employee_id)


@mcp.tool(name="event_type_draft_apply")
async def event_type_draft_apply(
    draft_id: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
    author: str = "boi-wiki-mcp",
    note: str = "MCP Event Type draft apply",
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Apply a validated Event Type draft to the catalog with explicit user confirmation."""
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before applying an Event Type draft")
    return await api_post(
        f"/api/event-types/drafts/{draft_id}/apply",
        employee_id=employee_id,
        payload={"author": author, "note": note, "user_confirmed": True},
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
    if not user_confirmed:
        raise RuntimeError("user_confirmed=true is required before submitting a promotion")
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


@mcp.resource("boi://search/ontology/{query}")
async def ontology_search_resource(query: str) -> str:
    """Read ontology-assisted search results as JSON text."""
    return as_text(await ontology_search(query=query, employee_id=DEFAULT_EMPLOYEE_ID))


@mcp.resource("boi://agent/response-schema/{version}")
async def boi_agent_response_schema_resource(version: str) -> str:
    """Read the BoI Agent response JSON Schema as JSON text."""
    requested = str(version or "").strip()
    if requested and requested not in {"latest", AGENT_RESPONSE_CONTRACT_VERSION}:
        return as_text(
            {
                "ok": False,
                "error": "unsupported_agent_response_schema_version",
                "requested_version": requested,
                "supported_versions": ["latest", AGENT_RESPONSE_CONTRACT_VERSION],
            }
        )
    return as_text(
        {
            "ok": True,
            "agent_contract_version": AGENT_RESPONSE_CONTRACT_VERSION,
            "schema": AGENT_RESPONSE_SCHEMA,
        }
    )


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


def request_has_service_token(request: Request) -> bool:
    token = request.headers.get("x-service-token") or ""
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        token = token or authorization.split(" ", 1)[1].strip()
    return bool(token and token == SERVICE_TOKEN)


class McpServiceTokenGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if MCP_REQUIRE_SERVICE_TOKEN and request.url.path.rstrip("/") == "/mcp":
            if not request_has_service_token(request):
                return JSONResponse(
                    {
                        "detail": "MCP service token is required",
                        "accepted_headers": ["x-service-token", "Authorization: Bearer <token>"],
                    },
                    status_code=401,
                )
        return await call_next(request)


app = mcp.streamable_http_app()
app.add_middleware(McpServiceTokenGateMiddleware)


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
        "agent_interfaces": AGENT_INTERFACES,
        "agent_response_contract": AGENT_RESPONSE_CONTRACT,
        "agent_response_schema": AGENT_RESPONSE_SCHEMA,
        "mcp_auth": {
            "required": MCP_REQUIRE_SERVICE_TOKEN,
            "accepted_headers": ["x-service-token", "Authorization: Bearer <token>"],
            "bridge_always_requires_service_token": True,
        },
        "notes": [
            "Open / in a browser for this status page.",
            "Do not use a browser to validate /mcp directly; MCP clients must send Streamable HTTP Accept headers.",
            "A direct browser/curl request to /mcp may return 406 even when the server is healthy.",
            "When MCP auth is required, configure the client to send x-service-token or Authorization: Bearer with the shared service token.",
            "Static resources are intentionally empty; use resource templates and tools.",
            "BoI API/MCP are the official external Agent interfaces; Native BoI Agent is the production backend and direct Langflow run URLs are trusted/dev visual-debug only. All Agent/Search/Inbox tools use the same BoI Profile ACL and Team RBAC guardrails as the Web UI.",
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
        <dt>MCP auth</dt><dd><code>{'required' if payload["mcp_auth"]["required"] else 'not required'}</code></dd>
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
      <h2>BoI Agent Interfaces</h2>
      <dl>
        <dt>JSON API</dt><dd><code>{payload["agent_interfaces"]["json_api"]}</code></dd>
        <dt>Streaming API</dt><dd><code>{payload["agent_interfaces"]["streaming_api"]}</code></dd>
        <dt>Streaming events</dt><dd><code>{", ".join(payload["agent_interfaces"]["streaming_events"])}</code></dd>
        <dt>MCP tool</dt><dd><code>{payload["agent_interfaces"]["mcp_tool"]}</code></dd>
        <dt>Response contract</dt><dd><code>{payload["agent_response_contract"]["version"]}</code></dd>
        <dt>Response schema</dt><dd><code>{payload["agent_response_contract"]["mcp_resource_template"]}</code></dd>
      </dl>
      <p>Web Pet Agent uses the streaming API so long requests can show one-line <code>status</code> updates and incremental <code>answer_delta</code> content. MCP clients normally call <code>boi_agent_chat</code> and receive the final JSON response using the same <code>{payload["agent_response_contract"]["version"]}</code> contract.</p>
    </section>
    <section>
      <h2>Client Registration</h2>
      <p>Register <code>{payload["mcp_endpoint"]}</code> as a Streamable HTTP MCP server in Codex, Claude Desktop, or Cursor.</p>
      <p>Use <code>ontology_search</code> for knowledge graph exploration, <code>boi_search</code> for document-only search, and <code>boi_agent_chat</code> for page-aware Q&amp;A. The production BoI Agent backend is the native Agent inside BoI API; Langflow direct run URLs are trusted/dev visual-debug paths, not the public Agent API. Agent/Search/Inbox tools use BoI Profile ACL and Team RBAC guardrails.</p>
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


def bridge_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def bridge_confirmation_error(tool: str) -> JSONResponse:
    return JSONResponse({"detail": f"user_confirmed=true is required before calling {tool}"}, status_code=400)


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
    elif tool_name == "okf_graph_doc":
        result = await api_get(f"/api/okf/graph/doc/{str(args.get('boi_id') or req.boi_id or '')}", employee_id=employee_id, service_token=True)
    elif tool_name == "workflow_status":
        result = await workflow_status_impl(
            str(args.get("workflow_key") or ""),
            str(args.get("trace_id") or ""),
            employee_id=employee_id,
            service_token=True,
        )
    elif tool_name == "workflow_start":
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        workflow_key = str(args.get("workflow_key") or "")
        payload = dict(args.get("payload") or {})
        if args.get("trace_id"):
            payload["trace_id"] = str(args.get("trace_id"))
        payload["user_confirmed"] = True
        result = await api_post(f"/api/workflows/{workflow_key}/start", employee_id=employee_id, payload=payload, service_token=True)
    elif tool_name == "actions_search":
        result = await actions_search_impl(
            employee_id=employee_id,
            event_type=str(args.get("event_type") or ""),
            connector_kind=str(args.get("connector_kind") or ""),
            action_key=str(args.get("action_key") or ""),
            service_token=True,
        )
    elif tool_name == "action_get":
        result = await actions_search_impl(employee_id=employee_id, action_key=str(args.get("action_key") or ""), service_token=True)
        if not result.get("items"):
            return JSONResponse({"detail": f"Action not found: {args.get('action_key') or ''}"}, status_code=404)
        result = {"ok": True, "item": result["items"][0]}
    elif tool_name == "action_invoke":
        if bridge_bool(args.get("dry_run"), True) is False and not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            "/api/actions/invoke",
            employee_id=employee_id,
            payload={
                "action_key": str(args.get("action_key") or ""),
                "employee_id": employee_id,
                "event": args.get("event") or {},
                "payload": args.get("payload") or {},
                "boi_id": args.get("boi_id"),
                "dry_run": bridge_bool(args.get("dry_run"), True),
                "approved_by": args.get("approved_by"),
                "user_confirmed": bridge_bool(args.get("user_confirmed")),
            },
            service_token=True,
        )
    elif tool_name == "ontology_search":
        result = await api_get(
            "/api/search/ontology",
            employee_id=employee_id,
            params={
                "q": str(args.get("query") or args.get("q") or ""),
                "scope": str(args.get("scope") or "all"),
                "limit": int(args.get("limit") or 8),
                "current_url": str(args.get("current_url") or ""),
            },
            service_token=True,
        )
    elif tool_name == "boi_agent_chat":
        result = await api_post(
            "/api/agents/boi-wiki/chat",
            employee_id=employee_id,
            payload={
                "question": str(args.get("question") or ""),
                "mode": str(args.get("mode") or "auto"),
                "intent": str(args.get("intent") or ""),
                "current_url": str(args.get("current_url") or ""),
                "selected_text": str(args.get("selected_text") or ""),
                "page_context": args.get("page_context") or {},
                "conversation": args.get("conversation") or [],
                "save_memory": bridge_bool(args.get("save_memory"), True),
            },
            service_token=True,
        )
    elif tool_name == "boi_agent_suggestions":
        result = await api_post(
            "/api/agents/boi-wiki/suggestions",
            employee_id=employee_id,
            payload={"current_url": str(args.get("current_url") or ""), "page_context": args.get("page_context") or {}},
            service_token=True,
        )
    elif tool_name == "agent_inbox":
        result = await api_get(
            "/api/agents/boi-wiki/inbox",
            employee_id=employee_id,
            params={"status": str(args.get("status") or "open"), "limit": int(args.get("limit") or 50)},
            service_token=True,
        )
    elif tool_name == "rbac_me":
        result = await api_get("/api/rbac/me", employee_id=employee_id, service_token=True)
    elif tool_name == "rbac_check":
        result = await api_post(
            "/api/rbac/check",
            employee_id=employee_id,
            payload={
                "employee_id": str(args.get("target_employee_id") or args.get("employee_id") or employee_id),
                "required_role": str(args.get("required_role") or "boi.viewer"),
                "scope": str(args.get("scope") or "global"),
                "resource": str(args.get("resource") or ""),
                "operation": str(args.get("operation") or "read"),
                "boi_id": str(args.get("boi_id") or ""),
                "action_key": str(args.get("action_key") or ""),
                "workflow_key": str(args.get("workflow_key") or ""),
                "event_type": str(args.get("event_type") or ""),
            },
            service_token=True,
        )
    elif tool_name == "doc_access_check":
        result = await api_get(f"/api/docs/{str(args.get('boi_id') or req.boi_id or '')}/access", employee_id=employee_id, service_token=True)
    elif tool_name == "rbac_audit":
        result = await api_get(
            "/api/rbac/audit",
            employee_id=employee_id,
            params={
                "limit": int(args.get("limit") or 100),
                "actor": str(args.get("actor") or ""),
                "action": str(args.get("action") or ""),
            },
            service_token=True,
        )
    elif tool_name == "dictionary_resolve":
        result = await api_get(
            "/api/dictionary/resolve",
            employee_id=employee_id,
            params={"q": str(args.get("query") or args.get("q") or ""), "scope": str(args.get("scope") or "all")},
            service_token=True,
        )
    elif tool_name == "dictionary_terms":
        result = await api_get(
            "/api/dictionary/terms",
            employee_id=employee_id,
            params={"scope": str(args.get("scope") or "all"), "q": str(args.get("query") or args.get("q") or ""), "limit": int(args.get("limit") or 100)},
            service_token=True,
        )
    elif tool_name == "agent_memory_search":
        result = await api_get(
            "/api/agents/boi-wiki/memory",
            employee_id=employee_id,
            params={"q": str(args.get("query") or args.get("q") or ""), "include_archived": str(bridge_bool(args.get("include_archived"))).lower(), "limit": int(args.get("limit") or 20)},
            service_token=True,
        )
    elif tool_name == "manual_handoff_complete":
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            "/api/agents/boi-wiki/manual-handoffs/complete",
            employee_id=employee_id,
            payload={
                "task_id": str(args.get("task_id") or ""),
                "note": str(args.get("note") or ""),
                "outcome": str(args.get("outcome") or "completed"),
                "user_confirmed": True,
            },
            service_token=True,
        )
    elif tool_name in {"event_type_draft_create", "create_event_type_draft"}:
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            "/api/event-types/drafts",
            employee_id=employee_id,
            payload=event_type_draft_payload_from_args(
                event_type=str(args.get("event_type") or ""),
                name_ko=str(args.get("name_ko") or ""),
                description=str(args.get("description") or ""),
                default_boi_type=str(args.get("default_boi_type") or "boi/event"),
                default_flow_key=str(args.get("default_flow_key") or ""),
                default_visibility=str(args.get("default_visibility") or "private"),
                owner=str(args.get("owner") or ""),
                status=str(args.get("status") or "draft"),
                topic=str(args.get("topic") or "boi.events"),
                workflow_stage=str(args.get("workflow_stage") or ""),
                sop_ref=str(args.get("sop_ref") or ""),
                sop_stage_id=str(args.get("sop_stage_id") or ""),
                wiki_usage=str(args.get("wiki_usage") or ""),
                payload_schema=args.get("payload_schema") if isinstance(args.get("payload_schema"), dict) else {},
                recommended_actions=args.get("recommended_actions") if isinstance(args.get("recommended_actions"), list) else [],
                recommended_manual_actions=args.get("recommended_manual_actions") if isinstance(args.get("recommended_manual_actions"), list) else [],
                user_confirmed=True,
            ),
            service_token=True,
        )
    elif tool_name in {"event_type_drafts", "event_type_draft_list", "list_event_type_drafts"}:
        result = await api_get("/api/event-types/drafts", employee_id=employee_id, service_token=True)
    elif tool_name == "event_type_draft_validate":
        result = await api_post(
            f"/api/event-types/drafts/{str(args.get('draft_id') or '')}/validate",
            employee_id=employee_id,
            service_token=True,
        )
    elif tool_name in {"event_type_draft_apply", "apply_event_type_draft"}:
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            f"/api/event-types/drafts/{str(args.get('draft_id') or '')}/apply",
            employee_id=employee_id,
            payload={
                "author": str(args.get("author") or "boi-wiki-mcp"),
                "note": str(args.get("note") or "MCP Event Type draft apply"),
                "user_confirmed": True,
            },
            service_token=True,
        )
    elif tool_name == "source_preview":
        result = await api_post(
            "/api/source/preview",
            employee_id=employee_id,
            payload={
                "path": str(args.get("path") or ""),
                "base_sha256": args.get("base_sha256"),
                "proposed_content": str(args.get("proposed_content") or ""),
                "author": str(args.get("author") or "boi-wiki-mcp"),
                "note": str(args.get("note") or "MCP source preview"),
            },
            service_token=True,
        )
    elif tool_name == "source_apply":
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            "/api/source/apply",
            employee_id=employee_id,
            payload={
                "path": str(args.get("path") or ""),
                "base_sha256": str(args.get("base_sha256") or ""),
                "proposed_content": str(args.get("proposed_content") or ""),
                "author": str(args.get("author") or "boi-wiki-mcp"),
                "note": str(args.get("note") or "MCP validated source edit"),
            },
            service_token=True,
        )
    elif tool_name == "doc_body_preview":
        boi_id = str(args.get("boi_id") or req.boi_id or "")
        result = await api_post(
            f"/api/docs/{boi_id}/body-preview",
            employee_id=employee_id,
            payload={
                "base_sha256": args.get("base_sha256"),
                "proposed_body": str(args.get("proposed_body") or ""),
                "author": str(args.get("author") or "boi-wiki-mcp"),
                "note": str(args.get("note") or "MCP body preview"),
            },
            service_token=True,
        )
    elif tool_name == "doc_body_apply":
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        boi_id = str(args.get("boi_id") or req.boi_id or "")
        result = await api_post(
            f"/api/docs/{boi_id}/body-apply",
            employee_id=employee_id,
            payload={
                "base_sha256": str(args.get("base_sha256") or ""),
                "proposed_body": str(args.get("proposed_body") or ""),
                "author": str(args.get("author") or "boi-wiki-mcp"),
                "note": str(args.get("note") or "MCP validated body edit"),
            },
            service_token=True,
        )
    elif tool_name == "promotion_submit":
        if not bridge_bool(args.get("user_confirmed")):
            return bridge_confirmation_error(req.tool)
        result = await api_post(
            "/api/promotions/submit",
            employee_id=employee_id,
            payload={
                "target_visibility": str(args.get("target_visibility") or "team"),
                "team_id": args.get("team_id"),
                "title": str(args.get("title") or ""),
                "description": str(args.get("description") or "Promoted BoI"),
                "body": str(args.get("body") or ""),
                "boi_type": str(args.get("boi_type") or "boi/reference"),
                "classification": str(args.get("classification") or "internal"),
                "tags": args.get("tags") or [],
                "source_refs": args.get("source_refs") or [],
                "source_local_id": args.get("source_local_id"),
                "source_sha256": args.get("source_sha256"),
                "reviewer": str(args.get("reviewer") or "hotl-curator"),
                "promotion_reason": str(args.get("promotion_reason") or "User explicitly requested promotion."),
                "user_confirmed": True,
                "user_confirmed_at": args.get("user_confirmed_at"),
            },
            service_token=True,
        )
    elif tool_name == "promotion_status":
        result = await api_get(f"/api/promotions/{str(args.get('promotion_id') or '')}", employee_id=employee_id, service_token=True)
    else:
        return JSONResponse({"detail": f"unsupported MCP bridge tool: {req.tool}"}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "status": "mcp_invoked",
            "tool": req.tool,
            "request_id": req.request_id,
            "response": result,
            "result": result,
        }
    )


app.add_route("/", status_page, methods=["GET"])
app.add_route("/status", status_page, methods=["GET"])
app.add_route("/status.json", status_json, methods=["GET"])
app.add_route("/health", health, methods=["GET"])
app.add_route("/api/mcp/call", mcp_bridge_call, methods=["POST"])
