#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EXPECTED_PROTOCOL = {"tools": 10, "resource_templates": 4, "prompts": 5}


def attr_any(item: object, *names: str) -> str:
    for name in names:
        value = getattr(item, name, None)
        if value is not None:
            return str(value)
    return str(item)


async def check_protocol(url: str, include_details: bool = False) -> dict:
    async with streamablehttp_client(url) as (read_stream, write_stream, _session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            resource_templates = await session.list_resource_templates()
            prompts = await session.list_prompts()
    result = {
        "tools": len(tools.tools),
        "resources": len(resources.resources),
        "resource_templates": len(resource_templates.resourceTemplates),
        "prompts": len(prompts.prompts),
    }
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
    protocol = await check_protocol(args.mcp_url, include_details=include_details)
    bridge = await check_bridge(args.base_url, args.service_token, args.query)
    ok = (
        protocol["tools"] >= EXPECTED_PROTOCOL["tools"]
        and protocol["resource_templates"] >= EXPECTED_PROTOCOL["resource_templates"]
        and protocol["prompts"] >= EXPECTED_PROTOCOL["prompts"]
        and bridge.get("ok") is True
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
            "verify_tools": ["boi_search", "boi_get", "workflow_status", "action_invoke"],
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
    parser.add_argument("--service-token", default="dev-service-token-change-me")
    parser.add_argument("--query", default="SOP")
    parser.add_argument("--summary", action="store_true", help="Print only the verification summary.")
    parser.add_argument("--details", action="store_true", help="Include tool, resource template, and prompt names.")
    parser.add_argument("--client-checklist", action="store_true", help="Include Codex, Claude Desktop, and Cursor registration checklist.")
    parser.add_argument("--full-bridge", action="store_true", help="Include the full bridge response payload.")
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except Exception as exc:
        print(f"BoI Wiki MCP check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
