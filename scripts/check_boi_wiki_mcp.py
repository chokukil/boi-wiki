#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EXPECTED_PROTOCOL = {"tools": 32, "resource_templates": 6, "prompts": 5}


def mcp_auth_headers(service_token: str = "") -> dict[str, str]:
    token = str(service_token or "").strip()
    if not token:
        return {}
    return {
        "x-service-token": token,
        "Authorization": f"Bearer {token}",
    }


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
                    "message": "MCP endpoint requires a service token; rerun with --service-token and optionally --require-bridge.",
                }
            raise
        direct["client_warning"] = f"{type(exc).__name__}: {exc}"
        direct["transport_mode"] = "stateless_json_rpc"
        return direct


async def check_protocol_mcp_client(url: str, include_details: bool = False, service_token: str = "") -> dict:
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


async def main_async(args: argparse.Namespace) -> int:
    include_details = bool(args.details or args.client_checklist)
    service_token = str(args.service_token or "").strip()
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
    parser.add_argument("--service-token", default=os.getenv("SERVICE_TOKEN", ""))
    parser.add_argument("--query", default="SOP")
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
