from __future__ import annotations

import contextvars
import json
import os
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
try:
    from mcp.server.streamable_http import TransportSecuritySettings
except Exception:  # pragma: no cover - compatibility with older MCP releases.
    TransportSecuritySettings = None  # type: ignore[assignment]
from starlette.middleware.base import BaseHTTPMiddleware


BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000").rstrip("/")
MCP_BACKEND_TIMEOUT_SECONDS = float(os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "120") or "120")
MCP_V2_REQUIRE_PAT = os.getenv("MCP_V2_REQUIRE_PAT", "true").strip().lower() in {"1", "true", "yes", "on"}
BOI_API_PAT = os.getenv("BOI_API_PAT", "").strip()
_request_bearer: contextvars.ContextVar[str] = contextvars.ContextVar("boi_mcp_v2_bearer", default="")


def _split_env(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _external_host_patterns() -> list[str]:
    parsed = urlsplit(os.getenv("BOI_WIKI_MCP_EXTERNAL_URL", "http://localhost:8200"))
    host = parsed.netloc or parsed.path
    if not host:
        return []
    hostname = parsed.hostname or ""
    patterns = [host]
    if hostname and host != hostname:
        patterns.append(f"{hostname}:*")
    return patterns


def _transport_security():
    if TransportSecuritySettings is None:
        return None
    if os.getenv("MCP_DNS_REBINDING_PROTECTION", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts = _split_env(os.getenv("MCP_ALLOWED_HOSTS", "")) or [
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "testserver",
        "testserver:*",
        "boi-wiki-mcp:*",
        *_external_host_patterns(),
    ]
    origins = _split_env(os.getenv("MCP_ALLOWED_ORIGINS", ""))
    if not origins:
        origins = [origin for host in hosts for origin in (f"http://{host}", f"https://{host}")]
    return TransportSecuritySettings(allowed_hosts=list(dict.fromkeys(hosts)), allowed_origins=list(dict.fromkeys(origins)))


MCP_V2_TOOLS = [
    {"name": "boi_bootstrap", "description": "Discover available BoI capabilities and current readiness."},
    {"name": "boi_agent", "description": "Ask naturally; BoI Agent routes search, analysis, drafts, and deep work automatically."},
    {"name": "boi_search", "description": "Search ACL-visible BoI knowledge or inspect neighbors, paths, impact, and guided tours."},
    {"name": "boi_get", "description": "Fetch a run, context, artifact, job, citation, GoalPlan, Source Set, or evidence reference."},
    {"name": "boi_my_work", "description": "List current work without mixing in history seed rows."},
    {"name": "boi_context", "description": "Fetch a compact WorkContextPack by reference."},
    {"name": "boi_plan", "description": "Create a private Business Event, SOP, Action, Skill, or knowledge draft."},
    {"name": "boi_confirm", "description": "Confirm review of one plan; production mutation remains separately guarded."},
    {"name": "boi_job_status", "description": "Read DeepAgents job status and draft result references."},
    {"name": "boi_tools_search", "description": "Progressively discover available capabilities instead of loading every schema."},
]


def _token() -> str:
    return _request_bearer.get() or BOI_API_PAT


async def v2_api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=MCP_BACKEND_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{BOI_API_URL}{path}", params=params or {}, headers=headers)
    return _decode(response)


async def v2_api_post(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=MCP_BACKEND_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{BOI_API_URL}{path}", json=payload or {}, headers=headers)
    return _decode(response)


def _decode(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except Exception:
        body = {"text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(json.dumps({"status_code": response.status_code, "body": body}, ensure_ascii=False))
    return body if isinstance(body, dict) else {"value": body}


mcp_v2 = FastMCP(
    "BoI Wiki v2",
    instructions=(
        "Use boi_agent for natural requests; it automatically selects search, analysis, draft, or deep work. "
        "Use boi_search/boi_get for deterministic evidence lookup, boi_plan for deterministic private drafts, "
        "and boi_confirm only after explicit user approval. "
        "Never infer or pass an employee_id; the bearer PAT determines identity and ACL."
    ),
    streamable_http_path="/mcp/v2",
    stateless_http=True,
    json_response=True,
    transport_security=_transport_security(),
)


@mcp_v2.tool(name="boi_bootstrap")
async def boi_bootstrap(page_ref: str = "") -> dict[str, Any]:
    """Discover capabilities, readiness, and next offers for a page."""
    return await v2_api_get("/api/v2/bootstrap", {"page_ref": page_ref})


@mcp_v2.tool(name="boi_agent")
async def boi_agent(
    question: str = "",
    page_ref: str = "",
    task_ref: str = "",
    conversation_id: str = "",
    work_session_id: str = "",
    capability_id: str = "",
    external_ai_summary: str = "",
    external_artifact_refs: list[str] | None = None,
    work_run_id: str = "",
    delta_kind: str = "",
    delta_summary: str = "",
    delta_ref: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Ask naturally, or continue a WorkRun with one explicit progress delta."""
    if work_run_id:
        if not delta_kind or not delta_summary:
            raise ValueError("delta_kind and delta_summary are required when continuing a WorkRun")
        run = await v2_api_get(f"/api/v2/work-runs/{quote(work_run_id, safe='')}")
        return await v2_api_post(
            f"/api/v2/work-runs/{quote(work_run_id, safe='')}/continue",
            {
                "expected_revision": int(run.get("revision") or 1),
                "confirmation": "confirm" if confirm else None,
                "delta": {
                    "kind": delta_kind,
                    "summary": delta_summary,
                    "ref": delta_ref,
                },
            },
        )
    payload: dict[str, Any] = {
        "question": question,
        "page_ref": page_ref,
        "task_ref": task_ref,
        "conversation_id": conversation_id or None,
        "work_session_id": work_session_id or None,
        "external_ai_summary": external_ai_summary,
        "external_artifact_refs": external_artifact_refs or [],
    }
    if capability_id:
        payload["capability_id"] = capability_id
    return await v2_api_post(
        "/api/v2/agent/turns",
        payload,
    )


@mcp_v2.tool(name="boi_search")
async def boi_search(
    query: str = "",
    include_history: bool = False,
    include_drafts: bool = False,
    limit: int = 8,
    page_ref: str = "",
    task_ref: str = "",
    view: str = "ranked",
    source_ref: str = "",
    target_ref: str = "",
    depth: int = 2,
) -> dict[str, Any]:
    """Search ranked knowledge or inspect neighbors, a path, impact, or a learning tour."""
    if view not in {"ranked", "neighbors", "path", "impact", "tour"}:
        raise ValueError("view must be ranked, neighbors, path, impact, or tour")
    if view != "ranked":
        return await v2_api_get(
            "/api/v2/knowledge-graph/explore",
            {
                "view": view,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "q": query,
                "depth": max(1, min(depth, 6)),
                "limit": max(1, min(limit, 300)),
            },
        )
    if not query.strip():
        raise ValueError("query is required for ranked search")
    return await v2_api_get(
        "/api/v2/search",
        {
            "q": query,
            "include_history": include_history,
            "include_drafts": include_drafts,
            "limit": max(1, min(limit, 20)),
            "page_ref": page_ref,
            "task_ref": task_ref,
        },
    )


@mcp_v2.tool(name="boi_get")
async def boi_get(ref: str) -> dict[str, Any]:
    """Fetch one v2 reference, including WorkRun and verified knowledge candidates."""
    clean = ref.strip()
    if clean.startswith("run_"):
        return await v2_api_get(f"/api/v2/agent/runs/{quote(clean, safe='')}")
    if clean.startswith("ctx_"):
        return await v2_api_get(f"/api/v2/context/{quote(clean, safe='')}")
    if clean.startswith("workrun_"):
        return await v2_api_get(f"/api/v2/work-runs/{quote(clean, safe='')}")
    if clean.startswith("candidate_"):
        return await v2_api_get(f"/api/v2/knowledge-candidates/{quote(clean, safe='')}")
    if clean.startswith("artifact_"):
        return await v2_api_get(f"/api/v2/artifacts/{quote(clean, safe='')}")
    if clean.startswith("job_"):
        return await v2_api_get(f"/api/v2/deep-jobs/{quote(clean, safe='')}")
    if clean.startswith("cite_"):
        return await v2_api_get(f"/api/v2/citations/{quote(clean, safe='')}")
    if clean.startswith("goal_"):
        return await v2_api_get(f"/api/v2/goal-plans/{quote(clean, safe='')}")
    if clean.startswith("sources_ws_"):
        session_id = clean.removeprefix("sources_")
        return await v2_api_get(f"/api/v2/work-sessions/{quote(session_id, safe='')}/sources")
    result = await v2_api_get("/api/v2/search", {"q": clean, "include_history": True, "limit": 8})
    exact = next((item for item in result.get("items") or [] if item.get("evidence_id") == clean), None)
    return {"ref": clean, "item": exact, "matches": result.get("items") or []}


@mcp_v2.tool(name="boi_my_work")
async def boi_my_work() -> dict[str, Any]:
    """Return only active current work; seed history is excluded by contract."""
    return await v2_api_post(
        "/api/v2/agent/turns",
        {"question": "현재 내가 처리할 업무를 보여줘", "capability_id": "work.inbox"},
    )


@mcp_v2.tool(name="boi_context")
async def boi_context(context_id: str) -> dict[str, Any]:
    """Read a compact WorkContextPack by context_id."""
    return await v2_api_get(f"/api/v2/context/{quote(context_id, safe='')}")


@mcp_v2.tool(name="boi_plan")
async def boi_plan(
    capability_id: str,
    goal: str,
    page_ref: str = "",
    task_ref: str = "",
    input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a private draft through an explicit draft capability."""
    return await v2_api_post(
        f"/api/v2/capabilities/{quote(capability_id, safe='')}/plan",
        {"goal": goal, "page_ref": page_ref, "task_ref": task_ref, "input": input or {}},
    )


@mcp_v2.tool(name="boi_confirm")
async def boi_confirm(plan_id: str, reason: str = "User explicitly confirmed the reviewed draft") -> dict[str, Any]:
    """Confirm plan review. This does not bypass downstream publication or Action guardrails."""
    return await v2_api_post(
        f"/api/v2/plans/{quote(plan_id, safe='')}/confirm",
        {"confirmation": "confirm", "reason": reason},
    )


@mcp_v2.tool(name="boi_job_status")
async def boi_job_status(job_id: str) -> dict[str, Any]:
    """Read a DeepAgents job without waiting for the whole job in one tool call."""
    return await v2_api_get(f"/api/v2/deep-jobs/{quote(job_id, safe='')}")


@mcp_v2.tool(name="boi_tools_search")
async def boi_tools_search(query: str = "") -> dict[str, Any]:
    """Discover capability contracts progressively."""
    result = await v2_api_get("/api/v2/capabilities")
    terms = {term.lower() for term in query.split() if term.strip()}
    items = result.get("items") or []
    if terms:
        items = [
            item
            for item in items
            if terms
            & {
                token.lower()
                for token in f"{item.get('capability_id','')} {item.get('title','')} {item.get('description','')}".split()
            }
        ]
    return {"version": result.get("version"), "count": len(items), "items": items}


@mcp_v2.resource("boi://v2/bootstrap")
async def bootstrap_resource() -> str:
    """Compact external-agent bootstrap document."""
    return json.dumps(await boi_bootstrap(), ensure_ascii=False, indent=2)


@mcp_v2.resource("boi://v2/capabilities")
async def capabilities_resource() -> str:
    """Capability registry visible to the authenticated user."""
    return json.dumps(await v2_api_get("/api/v2/capabilities"), ensure_ascii=False, indent=2)


class McpV2AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        authorization = request.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        token = bearer.strip() if scheme.lower() == "bearer" else ""
        if request.url.path.rstrip("/") == "/mcp/v2" and MCP_V2_REQUIRE_PAT:
            if not (token.startswith("boi_pat_") or BOI_API_PAT.startswith("boi_pat_")):
                return JSONResponse(
                    {"detail": "BoI personal access token is required", "accepted_header": "Authorization: Bearer boi_pat_..."},
                    status_code=401,
                )
        context_token = _request_bearer.set(token)
        try:
            return await call_next(request)
        finally:
            _request_bearer.reset(context_token)
