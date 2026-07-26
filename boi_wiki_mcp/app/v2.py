import contextvars
import json
import os
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
MCP_BACKEND_TIMEOUT_SECONDS = float(os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "120") or "120")
MCP_V2_REQUIRE_PAT = os.getenv("MCP_V2_REQUIRE_PAT", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_request_bearer: contextvars.ContextVar[str] = contextvars.ContextVar(
    "boi_mcp_v2_bearer",
    default="",
)
_request_audience: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "boi_mcp_v2_audience",
    default={},
)
AUDIENCE_HEADERS = (
    "X-BOI-Action-Key",
    "X-BOI-Deployment-ID",
    "X-BOI-Endpoint-ID",
    "X-BOI-Project-ID",
    "X-BOI-Flow-ID",
    "X-BOI-Trace-ID",
    "X-BOI-Execution-ID",
)


MCP_V2_TOOLS = [
    {
        "name": "boi_search",
        "description": (
            "Compatibility facade for ACL-visible Task Context and Ontology-first "
            "hybrid retrieval, with Wiki documents used as grounded fallback."
        ),
    },
    {
        "name": "boi_get",
        "description": "Fetch one ACL-visible BoI document by stable reference.",
    },
    {
        "name": "boi_plan",
        "description": "Preview a knowledge.draft plan without changing Wiki content.",
    },
    {
        "name": "boi_confirm",
        "description": "Confirm one owned plan and write only a caller-private Wiki draft.",
    },
]


def _bearer() -> str:
    return _request_bearer.get()


def _headers() -> dict[str, str]:
    token = _bearer()
    headers = {"x-service-token": SERVICE_TOKEN}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers.update(_request_audience.get())
    return headers


def _decode(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except Exception:
        body = {"text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(
            json.dumps(
                {"status_code": response.status_code, "body": body},
                ensure_ascii=False,
            )
        )
    return body if isinstance(body, dict) else {"value": body}


async def internal_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=MCP_BACKEND_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{BOI_API_URL}{path}",
            params=params,
            headers=_headers(),
        )
    return _decode(response)


async def internal_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=MCP_BACKEND_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{BOI_API_URL}{path}",
            json=payload,
            headers=_headers(),
        )
    return _decode(response)


async def boi_search(
    query: str = "",
    include_history: bool = False,
    include_drafts: bool = False,
    limit: int = 8,
    page_ref: str = "",
    task_ref: str = "",
    trace_id: str = "",
    event_id: str = "",
    action_key: str = "",
    view: str = "ranked",
    source_ref: str = "",
    target_ref: str = "",
    depth: int = 2,
) -> dict[str, Any]:
    """Resolve Task Context and Ontology-first evidence with Wiki fallback."""

    supported_views = {
        "ranked",
        "neighbors",
        "path",
        "workflow",
        "impact",
        "lineage",
        "responsibility",
        "timeline",
        "compare",
        "tour",
    }
    if view not in supported_views:
        raise ValueError(f"view must be one of: {', '.join(sorted(supported_views))}")
    if view == "ranked" and not query.strip():
        raise ValueError("query is required for ranked search")
    return await internal_get(
        "/internal/agent-playground/wiki/search",
        {
            "q": query,
            "view": view,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "page_ref": page_ref,
            "task_ref": task_ref,
            "trace_id": trace_id,
            "event_id": event_id,
            "action_key": action_key,
            "limit": max(1, min(int(limit), 300)),
            "depth": max(1, min(int(depth), 6)),
            "include_history": include_history,
            "include_drafts": include_drafts,
        },
    )


async def boi_get(ref: str) -> dict[str, Any]:
    """Fetch one ACL-visible BoI reference."""

    return await internal_get(
        "/internal/agent-playground/wiki/get",
        {"ref": ref},
    )


async def boi_plan(
    capability_id: str,
    goal: str,
    page_ref: str = "",
    task_ref: str = "",
    input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview a caller-private knowledge draft."""

    return await internal_post(
        "/internal/agent-playground/wiki/plans",
        {
            "capability_id": capability_id,
            "goal": goal,
            "page_ref": page_ref,
            "task_ref": task_ref,
            "input": input or {},
        },
    )


async def boi_confirm(
    plan_id: str,
    reason: str = "User explicitly confirmed the private draft",
) -> dict[str, Any]:
    """Confirm one owned knowledge draft plan."""

    return await internal_post(
        f"/internal/agent-playground/wiki/plans/{quote(plan_id, safe='')}/confirm",
        {"reason": reason},
    )


def create_mcp_v2() -> FastMCP:
    """Build a fresh single-use FastMCP transport for one Starlette app."""

    server = FastMCP(
        "BoI Wiki Agent Playground",
        instructions=(
            "The bearer PAT or one-run token determines the user and Wiki ACL. "
            "Never send employee_id. Use boi_search and boi_get for grounded reads; "
            "boi_plan plus boi_confirm only for an explicit private_draft request."
        ),
        streamable_http_path="/mcp/v2",
        stateless_http=True,
        json_response=True,
    )
    server.tool(name="boi_search")(boi_search)
    server.tool(name="boi_get")(boi_get)
    server.tool(name="boi_plan")(boi_plan)
    server.tool(name="boi_confirm")(boi_confirm)
    return server


class McpV2AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        authorization = request.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        token = bearer.strip() if scheme.lower() == "bearer" else ""
        if request.url.path.rstrip("/") == "/mcp/v2" and MCP_V2_REQUIRE_PAT:
            if not token.startswith(("boi_pat_", "boi_run_")):
                return JSONResponse(
                    {
                        "detail": "BoI PAT or Action run token is required",
                        "accepted_header": "Authorization: Bearer boi_pat_... | boi_run_...",
                    },
                    status_code=401,
                )
        context_token = _request_bearer.set(token)
        audience_token = _request_audience.set(
            {
                header: value
                for header in AUDIENCE_HEADERS
                if (value := request.headers.get(header))
            }
        )
        try:
            return await call_next(request)
        finally:
            _request_audience.reset(audience_token)
            _request_bearer.reset(context_token)
