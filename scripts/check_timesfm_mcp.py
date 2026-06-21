from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.sse import sse_client


def jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [jsonable(v) for v in value]
    return value


def fixture_payload() -> dict[str, Any]:
    return {
        "series": [
            {"timestamp": "2026-06-22T09:00:00+09:00", "value": 101.2},
            {"timestamp": "2026-06-22T10:00:00+09:00", "value": 102.4},
            {"timestamp": "2026-06-22T11:00:00+09:00", "value": 104.1},
            {"timestamp": "2026-06-22T12:00:00+09:00", "value": 103.8},
        ],
        "horizon": 3,
        "frequency": "H",
        "target_column": "value",
        "confidence_level": 0.9,
        "context": {"business_reason": "TimesFM MCP smoke forecast"},
    }


async def probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.url:
        return 2, {"ok": False, "status": "missing_url", "message": "Provide --url or TIMESFM_MCP_URL."}

    try:
        async with sse_client(
            args.url,
            timeout=args.timeout,
            sse_read_timeout=args.sse_read_timeout,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                tools = [jsonable(tool) for tool in tools_response.tools]
                tool_names = [str(tool.get("name") or "") for tool in tools]
                result: dict[str, Any] = {
                    "ok": True,
                    "status": "connected",
                    "url": args.url,
                    "tool_count": len(tools),
                    "tools": tools,
                }
                if args.call_fixture:
                    if args.tool_name not in tool_names:
                        result.update(
                            {
                                "ok": False,
                                "status": "tool_not_found",
                                "tool_name": args.tool_name,
                                "available_tools": tool_names,
                            }
                        )
                        return 3, result
                    call_result = await session.call_tool(args.tool_name, fixture_payload())
                    result["call"] = {
                        "tool_name": args.tool_name,
                        "arguments": fixture_payload(),
                        "result": jsonable(call_result),
                    }
                return 0, result
    except Exception as exc:
        return 1, {"ok": False, "status": "connection_failed", "url": args.url, "error": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a TimesFM MCP SSE endpoint.")
    parser.add_argument("--url", default=os.getenv("TIMESFM_MCP_URL", ""), help="TimesFM MCP SSE URL.")
    parser.add_argument("--tool-name", default="forecast", help="Tool name to call for --call-fixture.")
    parser.add_argument("--list-tools", action="store_true", help="Print available tools.")
    parser.add_argument("--call-fixture", action="store_true", help="Call the forecast tool with a tiny fixture payload.")
    parser.add_argument("--summary", action="store_true", help="Print a compact human-readable summary.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sse-read-timeout", type=float, default=20.0)
    args = parser.parse_args()

    code, result = anyio.run(probe, args)
    if args.summary:
        print(f"status={result.get('status')} ok={result.get('ok')} url={result.get('url') or ''}")
        if "tool_count" in result:
            print(f"tool_count={result.get('tool_count')}")
        if args.list_tools and result.get("tools"):
            for tool in result["tools"]:
                print(f"- {tool.get('name')}: {tool.get('description') or ''}")
        if result.get("call"):
            print(f"call_tool={result['call']['tool_name']} ok=true")
        if result.get("error"):
            print(f"error={result['error']}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
