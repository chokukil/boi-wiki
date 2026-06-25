#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import functools
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
import urllib.request as urllib_request

try:
    import httpx
except Exception:  # pragma: no cover - exercised by no-optional-deps test.
    httpx = None

try:
    from jsonschema import validate
except Exception:  # pragma: no cover - exercised by no-optional-deps test.
    validate = None

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except Exception:  # pragma: no cover - agent-contract-only can run without MCP client libs.
    ClientSession = None
    streamablehttp_client = None

EXPECTED_PROTOCOL = {"tools": 32, "resource_templates": 11, "prompts": 5}


def mcp_auth_headers(service_token: str = "") -> dict[str, str]:
    token = str(service_token or "").strip()
    if not token:
        return {}
    return {
        "x-service-token": token,
        "Authorization": f"Bearer {token}",
    }


def dotenv_value(path: str | os.PathLike[str], key: str) -> str:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"dotenv file not found: {target}")
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        return value.strip()
    return ""


def resolve_service_token(args: argparse.Namespace) -> str:
    direct = str(getattr(args, "service_token", "") or "").strip()
    if direct:
        return direct
    env_name = str(getattr(args, "service_token_env", "") or "").strip()
    if env_name:
        token = str(os.getenv(env_name, "") or "").strip()
        if token:
            return token
    dotenv_path = str(getattr(args, "service_token_dotenv", "") or "").strip()
    if dotenv_path:
        token = dotenv_value(dotenv_path, "SERVICE_TOKEN")
        if token:
            return token
    return str(os.getenv("SERVICE_TOKEN", "") or "").strip()


def attr_any(item: object, *names: str) -> str:
    for name in names:
        value = getattr(item, name, None)
        if value is not None:
            return str(value)
    return str(item)


async def check_protocol(url: str, include_details: bool = False, service_token: str = "") -> dict:
    try:
        return await check_protocol_mcp_client(url, include_details=include_details, service_token=service_token)
    except Exception as exc:
        try:
            direct = await check_protocol_stateless_json(url, include_details=include_details, service_token=service_token)
        except httpx.HTTPStatusError as direct_exc:
            if direct_exc.response.status_code == 401 and not str(service_token or "").strip():
                return {
                    "tools": 0,
                    "resources": 0,
                    "resource_templates": 0,
                    "prompts": 0,
                    "status": "auth_required",
                    "auth_required": True,
                    "transport_mode": "unauthorized",
                    "client_warning": f"{type(exc).__name__}: {exc}",
                    "message": "MCP endpoint requires a service token; rerun with --service-token, --service-token-env, or --service-token-dotenv and optionally --require-bridge.",
                }
            raise
        direct["client_warning"] = f"{type(exc).__name__}: {exc}"
        direct["transport_mode"] = "stateless_json_rpc"
        return direct


async def check_protocol_mcp_client(url: str, include_details: bool = False, service_token: str = "") -> dict:
    if ClientSession is None or streamablehttp_client is None:
        raise RuntimeError("MCP client dependencies are unavailable; install mcp or use --agent-contract-only for AgentResponse checks")
    tools = resources = resource_templates = prompts = None
    close_warning = ""
    try:
        async with streamablehttp_client(url, headers=mcp_auth_headers(service_token)) as (read_stream, write_stream, _session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                resources = await session.list_resources()
                resource_templates = await session.list_resource_templates()
                prompts = await session.list_prompts()
    except Exception as exc:
        if tools is None or resources is None or resource_templates is None or prompts is None:
            raise
        # Some streamable HTTP deployments close the POST writer as soon as the
        # read side has delivered all protocol lists. Treat that as a transport
        # close warning only after the authoritative MCP lists were collected.
        close_warning = f"{type(exc).__name__}: {exc}"
    result = {
        "tools": len(tools.tools),
        "resources": len(resources.resources),
        "resource_templates": len(resource_templates.resourceTemplates),
        "prompts": len(prompts.prompts),
    }
    if close_warning:
        result["close_warning"] = close_warning
    if include_details:
        result.update(
            {
                "tool_names": [attr_any(tool, "name") for tool in tools.tools],
                "resource_uris": [attr_any(resource, "uri") for resource in resources.resources],
                "resource_template_uris": [
                    attr_any(template, "uriTemplate", "uri_template") for template in resource_templates.resourceTemplates
                ],
                "prompt_names": [attr_any(prompt, "name") for prompt in prompts.prompts],
            }
        )
    return result


async def check_protocol_stateless_json(url: str, include_details: bool = False, service_token: str = "") -> dict:
    if httpx is None:
        raise RuntimeError("httpx is unavailable; install httpx or use --agent-contract-only for AgentResponse checks")
    async with httpx.AsyncClient(timeout=30) as client:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **mcp_auth_headers(service_token),
        }

        async def rpc(method: str, request_id: int, params: dict | None = None) -> dict:
            response = await client.post(
                url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
            )
            response.raise_for_status()
            body = response.json()
            if body.get("error"):
                raise RuntimeError(json.dumps(body["error"], ensure_ascii=False))
            result = body.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(f"invalid JSON-RPC result for {method}")
            return result

        await rpc(
            "initialize",
            1,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "check-boi-wiki-mcp", "version": "1.0"},
            },
        )
        tools = await rpc("tools/list", 2)
        resource_templates = await rpc("resources/templates/list", 3)
        prompts = await rpc("prompts/list", 4)

    tool_items = list(tools.get("tools") or [])
    template_items = list(resource_templates.get("resourceTemplates") or [])
    prompt_items = list(prompts.get("prompts") or [])
    result = {
        "tools": len(tool_items),
        "resources": 0,
        "resource_templates": len(template_items),
        "prompts": len(prompt_items),
    }
    if include_details:
        result.update(
            {
                "tool_names": [str(item.get("name") or "") for item in tool_items],
                "resource_uris": [],
                "resource_template_uris": [str(item.get("uriTemplate") or item.get("uri") or "") for item in template_items],
                "prompt_names": [str(item.get("name") or "") for item in prompt_items],
            }
        )
    return result


async def check_bridge(base_url: str, service_token: str, query: str) -> dict:
    if httpx is None:
        raise RuntimeError("httpx is unavailable; install httpx or use --agent-contract-only for AgentResponse checks")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/api/mcp/call",
            headers={"x-service-token": service_token},
            json={
                "server": {"name": "boi-wiki-mcp"},
                "tool": "boi.search",
                "arguments": {"query": query, "employee_id": "100001"},
                "request_id": "check-boi-wiki-mcp",
            },
        )
    resp.raise_for_status()
    return resp.json()


def bridge_summary(bridge: dict) -> dict:
    return {
        "ok": bridge.get("ok"),
        "status": bridge.get("status"),
        "tool": bridge.get("tool"),
        "request_id": bridge.get("request_id"),
    }


def minimal_json_schema_validate(instance: object, schema: dict, path: str = "$") -> None:
    if not isinstance(schema, dict):
        return
    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(instance, dict):
        raise RuntimeError(f"{path} must be an object")
    if expected_type == "array" and not isinstance(instance, list):
        raise RuntimeError(f"{path} must be an array")
    if expected_type == "string" and not isinstance(instance, str):
        raise RuntimeError(f"{path} must be a string")
    if expected_type == "boolean" and not isinstance(instance, bool):
        raise RuntimeError(f"{path} must be a boolean")
    if expected_type == "integer" and not isinstance(instance, int):
        raise RuntimeError(f"{path} must be an integer")
    if "const" in schema and instance != schema.get("const"):
        raise RuntimeError(f"{path} must equal {schema.get('const')!r}")
    if isinstance(instance, dict):
        for key in schema.get("required") or []:
            if key not in instance:
                raise RuntimeError(f"{path}.{key} is required")
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for key, child_schema in properties.items():
            if key in instance:
                minimal_json_schema_validate(instance[key], child_schema, f"{path}.{key}")
    if isinstance(instance, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(instance):
            minimal_json_schema_validate(item, schema["items"], f"{path}[{index}]")


def validate_agent_response(response: dict, schema: dict) -> None:
    if validate is not None:
        validate(instance=response, schema=schema)
        return
    minimal_json_schema_validate(response, schema)


REQUIRED_EXECUTION_CARD_FIELDS = {
    "contract_version",
    "operation",
    "requires_confirmation",
    "user_confirmed_required",
    "required_role",
    "permission",
}


def execution_card_required_fields(schema: dict) -> list[str]:
    return (
        schema.get("properties", {})
        .get("execution_cards", {})
        .get("items", {})
        .get("required", [])
    )


def validate_agent_response_schema_contract(schema: dict) -> None:
    if not isinstance(schema, dict):
        raise RuntimeError("BoI Agent response-schema endpoint did not return a JSON schema")
    required = set(execution_card_required_fields(schema))
    missing = sorted(REQUIRED_EXECUTION_CARD_FIELDS - required)
    if missing:
        raise RuntimeError(
            "execution_cards schema must require "
            + ", ".join(sorted(REQUIRED_EXECUTION_CARD_FIELDS))
            + f"; missing: {', '.join(missing)}"
        )


def agent_response_summary(response: dict, schema: dict) -> dict:
    validate_agent_response_schema_contract(schema)
    validate_agent_response(response, schema)
    return {
        "schema_valid": True,
        "contract_version": response.get("agent_contract_version"),
        "route": response.get("route"),
        "intent": response.get("intent"),
        "used_backend": response.get("used_backend"),
        "artifact_count": len(response.get("artifacts") or []),
        "execution_card_count": len(response.get("execution_cards") or []),
        "status_update_count": len(response.get("status_updates") or []),
        "tool_trace_count": len(response.get("tool_trace") or []),
    }


def mcp_status_schema_summary(status_payload: dict, api_schema: dict) -> dict:
    mcp_schema = status_payload.get("agent_response_schema")
    if not isinstance(mcp_schema, dict):
        raise RuntimeError("MCP status endpoint did not expose agent_response_schema")
    validate_agent_response_schema_contract(api_schema)
    validate_agent_response_schema_contract(mcp_schema)
    if mcp_schema != api_schema:
        raise RuntimeError("MCP status AgentResponse schema does not match BoI API schema")
    return {
        "schema_valid": True,
        "matches_api_schema": True,
        "contract_version": (
            mcp_schema.get("properties", {})
            .get("agent_contract_version", {})
            .get("const")
        ),
        "required_fields": mcp_schema.get("required") or [],
        "execution_card_required": execution_card_required_fields(mcp_schema),
    }


def urllib_json_request(method: str, url: str, *, headers: dict | None = None, params: dict | None = None, payload: dict | None = None, timeout: int = 60) -> dict:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib_request.Request(full_url, data=body, headers=request_headers, method=method.upper())
    with urllib_request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


async def run_blocking(func, *args, **kwargs):
    if hasattr(asyncio, "to_thread"):
        return await asyncio.to_thread(func, *args, **kwargs)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


async def check_agent_contract(
    boi_api_url: str,
    mcp_base_url: str,
    employee_id: str,
    service_token: str = "",
    question: str = "SOP 찾아줘",
    current_url: str = "/",
) -> dict:
    api_base = boi_api_url.rstrip("/")
    mcp_base = mcp_base_url.rstrip("/")
    if httpx is None:
        schema_payload = await run_blocking(
            urllib_json_request,
            "GET",
            f"{api_base}/api/agents/boi-wiki/response-schema",
        )
        schema = schema_payload.get("schema")
        if not isinstance(schema, dict):
            raise RuntimeError("BoI Agent response-schema endpoint did not return a JSON schema")
        mcp_status = await run_blocking(
            urllib_json_request,
            "GET",
            f"{mcp_base}/health",
        )
        chat_payload = {
            "question": question,
            "mode": "fast",
            "intent": "search",
            "current_url": current_url,
            "save_memory": False,
        }
        rest_chat = await run_blocking(
            urllib_json_request,
            "POST",
            f"{api_base}/api/agents/boi-wiki/chat",
            params={"employee_id": employee_id},
            payload=chat_payload,
        )
        result = {
            "ok": True,
            "schema": {
                "version": schema_payload.get("agent_contract_version"),
                "required_fields": schema.get("required") or [],
                "execution_card_required": (
                    schema.get("properties", {})
                    .get("execution_cards", {})
                    .get("items", {})
                    .get("required", [])
                ),
            },
            "mcp_status_schema": mcp_status_schema_summary(mcp_status, schema),
            "rest_chat": agent_response_summary(rest_chat, schema),
            "mcp_bridge_chat": {
                "schema_valid": None,
                "status": "skipped",
                "reason": "service token not provided",
            },
        }
        if service_token:
            bridge_payload = await run_blocking(
                urllib_json_request,
                "POST",
                f"{mcp_base}/api/mcp/call",
                headers={"x-service-token": service_token},
                payload={
                    "server": {"name": "boi-wiki-mcp"},
                    "tool": "boi_agent_chat",
                    "arguments": {
                        "question": question,
                        "employee_id": employee_id,
                        "mode": "fast",
                        "intent": "search",
                        "current_url": current_url,
                        "save_memory": False,
                    },
                    "request_id": "check-boi-agent-contract",
                },
            )
            bridge_result = bridge_payload.get("result")
            if not isinstance(bridge_result, dict):
                raise RuntimeError("MCP bridge boi_agent_chat did not return a JSON object result")
            result["mcp_bridge_chat"] = agent_response_summary(bridge_result, schema)
        return result
    async with httpx.AsyncClient(timeout=60) as client:
        schema_response = await client.get(f"{api_base}/api/agents/boi-wiki/response-schema")
        schema_response.raise_for_status()
        schema_payload = schema_response.json()
        schema = schema_payload.get("schema")
        if not isinstance(schema, dict):
            raise RuntimeError("BoI Agent response-schema endpoint did not return a JSON schema")
        mcp_status_response = await client.get(f"{mcp_base}/health")
        mcp_status_response.raise_for_status()
        mcp_status = mcp_status_response.json()

        chat_payload = {
            "question": question,
            "mode": "fast",
            "intent": "search",
            "current_url": current_url,
            "save_memory": False,
        }
        rest_response = await client.post(
            f"{api_base}/api/agents/boi-wiki/chat",
            params={"employee_id": employee_id},
            json=chat_payload,
        )
        rest_response.raise_for_status()
        rest_chat = rest_response.json()
        result = {
            "ok": True,
            "schema": {
                "version": schema_payload.get("agent_contract_version"),
                "required_fields": schema.get("required") or [],
                "execution_card_required": (
                    schema.get("properties", {})
                    .get("execution_cards", {})
                    .get("items", {})
                    .get("required", [])
                ),
            },
            "mcp_status_schema": mcp_status_schema_summary(mcp_status, schema),
            "rest_chat": agent_response_summary(rest_chat, schema),
            "mcp_bridge_chat": {
                "schema_valid": None,
                "status": "skipped",
                "reason": "service token not provided",
            },
        }
        if service_token:
            bridge_response = await client.post(
                f"{mcp_base}/api/mcp/call",
                headers={"x-service-token": service_token},
                json={
                    "server": {"name": "boi-wiki-mcp"},
                    "tool": "boi_agent_chat",
                    "arguments": {
                        "question": question,
                        "employee_id": employee_id,
                        "mode": "fast",
                        "intent": "search",
                        "current_url": current_url,
                        "save_memory": False,
                    },
                    "request_id": "check-boi-agent-contract",
                },
            )
            bridge_response.raise_for_status()
            bridge_payload = bridge_response.json()
            bridge_result = bridge_payload.get("result")
            if not isinstance(bridge_result, dict):
                raise RuntimeError("MCP bridge boi_agent_chat did not return a JSON object result")
            result["mcp_bridge_chat"] = agent_response_summary(bridge_result, schema)
        return result


async def main_async(args: argparse.Namespace) -> int:
    service_token = resolve_service_token(args)
    if getattr(args, "agent_contract_only", False):
        agent_contract = await check_agent_contract(
            boi_api_url=args.boi_api_url,
            mcp_base_url=args.base_url,
            employee_id=args.employee_id,
            service_token=service_token,
            question=args.agent_question,
            current_url=args.agent_current_url,
        )
        ok = bool(agent_contract.get("ok"))
        if bool(getattr(args, "require_bridge", False)):
            ok = ok and agent_contract.get("mcp_bridge_chat", {}).get("schema_valid") is True
        print(json.dumps({"ok": ok, "agent_contract": agent_contract}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    include_details = bool(args.details or args.client_checklist)
    protocol = await check_protocol(args.mcp_url, include_details=include_details, service_token=service_token)
    require_bridge = bool(getattr(args, "require_bridge", False))
    if service_token:
        bridge = await check_bridge(args.base_url, service_token, args.query)
    else:
        bridge = {
            "ok": None,
            "status": "skipped",
            "tool": "boi.search",
            "request_id": "check-boi-wiki-mcp",
            "reason": "service token not provided; authenticated bridge check skipped",
        }
    ok = (
        protocol["tools"] >= EXPECTED_PROTOCOL["tools"]
        and protocol["resource_templates"] >= EXPECTED_PROTOCOL["resource_templates"]
        and protocol["prompts"] >= EXPECTED_PROTOCOL["prompts"]
        and (bridge.get("ok") is True or (bridge.get("status") == "skipped" and not require_bridge))
    )
    if args.summary:
        result = {
            "ok": ok,
            "protocol": protocol,
            "bridge": bridge_summary(bridge),
        }
    else:
        bridge_result = bridge if args.full_bridge or not include_details else bridge_summary(bridge)
        result = {"ok": ok, "protocol": protocol, "bridge": bridge_result}
    if getattr(args, "agent_contract", False):
        agent_contract = await check_agent_contract(
            boi_api_url=args.boi_api_url,
            mcp_base_url=args.base_url,
            employee_id=args.employee_id,
            service_token=service_token,
            question=args.agent_question,
            current_url=args.agent_current_url,
        )
        result["agent_contract"] = agent_contract
        ok = ok and bool(agent_contract.get("ok"))
        result["ok"] = ok
    if args.client_checklist:
        client_entry = {
            "name": "boi-wiki-mcp",
            "transport": "Streamable HTTP",
            "url": args.mcp_url,
            "verify_tools": [
                "boi_search",
                "boi_get",
                "workflow_status",
                "boi_agent_chat",
                "boi_agent_capabilities",
                "boi_agent_approve",
                "boi_agent_suggestions",
                "ontology_search",
                "dictionary_resolve",
                "dictionary_terms",
                "agent_memory_search",
                "agent_inbox",
                "manual_handoff_complete",
                "event_type_draft_create",
                "event_type_drafts",
                "event_type_draft_validate",
                "event_type_draft_apply",
                "action_invoke",
                "source_preview",
                "source_apply",
                "doc_body_preview",
                "doc_body_apply",
                "promotion_submit",
                "promotion_status",
            ],
        }
        result["client_registration"] = {
            "Codex": client_entry,
            "Claude Desktop": client_entry,
            "Cursor": client_entry,
            "browser_note": "A direct browser request to /mcp may return 406; use an MCP client or this script.",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check BoI Wiki MCP protocol and bridge endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8200", help="BoI Wiki MCP service base URL.")
    parser.add_argument("--mcp-url", default="http://localhost:8200/mcp", help="Streamable HTTP MCP URL.")
    parser.add_argument("--service-token", default="", help="Service token value. Prefer --service-token-env or --service-token-dotenv on shared hosts.")
    parser.add_argument("--service-token-env", default="", help="Read the service token from this environment variable name.")
    parser.add_argument("--service-token-dotenv", default="", help="Read SERVICE_TOKEN from a dotenv file without printing it.")
    parser.add_argument("--query", default="SOP")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--boi-api-url", default=os.getenv("BOI_EXTERNAL_URL", "http://localhost:8000"), help="BoI API base URL for AgentResponse contract checks.")
    parser.add_argument("--agent-contract", action="store_true", help="Validate REST and optional MCP bridge boi_agent_chat responses against the canonical AgentResponse schema.")
    parser.add_argument("--agent-contract-only", action="store_true", help="Run only AgentResponse contract checks. This mode can run with stdlib-only Python on NAS hosts.")
    parser.add_argument("--agent-question", default="SOP 찾아줘")
    parser.add_argument("--agent-current-url", default="/sops")
    parser.add_argument("--summary", action="store_true", help="Print only the verification summary.")
    parser.add_argument("--details", action="store_true", help="Include tool, resource template, and prompt names.")
    parser.add_argument("--client-checklist", action="store_true", help="Include Codex, Claude Desktop, and Cursor registration checklist.")
    parser.add_argument("--full-bridge", action="store_true", help="Include the full bridge response payload.")
    parser.add_argument("--require-bridge", action="store_true", help="Fail when the authenticated bridge check is skipped or unsuccessful.")
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except Exception as exc:
        print(f"BoI Wiki MCP check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
