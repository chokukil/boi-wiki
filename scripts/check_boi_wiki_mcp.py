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


async def check_protocol(url: str) -> dict[str, int]:
    async with streamablehttp_client(url) as (read_stream, write_stream, _session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            resource_templates = await session.list_resource_templates()
            prompts = await session.list_prompts()
    return {
        "tools": len(tools.tools),
        "resources": len(resources.resources),
        "resource_templates": len(resource_templates.resourceTemplates),
        "prompts": len(prompts.prompts),
    }


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


async def main_async(args: argparse.Namespace) -> int:
    protocol = await check_protocol(args.mcp_url)
    bridge = await check_bridge(args.base_url, args.service_token, args.query)
    ok = protocol["tools"] >= 1 and protocol["resource_templates"] >= 1 and protocol["prompts"] >= 1 and bridge.get("ok") is True
    if args.summary:
        result = {
            "ok": ok,
            "protocol": protocol,
            "bridge": {
                "ok": bridge.get("ok"),
                "status": bridge.get("status"),
                "tool": bridge.get("tool"),
                "request_id": bridge.get("request_id"),
            },
        }
    else:
        result = {"ok": ok, "protocol": protocol, "bridge": bridge}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check BoI Wiki MCP protocol and bridge endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8200", help="BoI Wiki MCP service base URL.")
    parser.add_argument("--mcp-url", default="http://localhost:8200/mcp", help="Streamable HTTP MCP URL.")
    parser.add_argument("--service-token", default="dev-service-token-change-me")
    parser.add_argument("--query", default="SOP")
    parser.add_argument("--summary", action="store_true", help="Print only the verification summary.")
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except Exception as exc:
        print(f"BoI Wiki MCP check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
