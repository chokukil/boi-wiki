from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from lfx.custom import Component
from lfx.io import DataInput, DropdownInput, Output, StrInput
from lfx.schema import Data
from lfx.schema.message import Message
from lfx.utils.secrets import unwrap_secret_value


SECRET_VALUE = re.compile(r"(?:boi_(?:pat|run)_[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{16,})")


def _decode_tool_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", "")
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    return {}


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_VALUE.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items() if str(key).lower() not in {"api_key", "pat", "token", "service_token"}}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class BoIWikiSave(Component):
    display_name = "Wiki에 지식 저장하기"
    description = "Agent 결과를 미리 보거나 현재 사용자의 private Wiki 초안으로만 저장합니다."
    icon = "save"
    name = "BoIWikiSave"

    inputs = [
        DataInput(name="agent_result", display_name="Agent 결과", required=True),
        StrInput(name="title", display_name="제목", value="Agent Playground 개인 초안"),
        DropdownInput(
            name="save_mode",
            display_name="저장 방식",
            options=["preview", "private_draft"],
            value="preview",
        ),
        StrInput(name="flow_id", display_name="Flow ID", value="boi-wiki-agent-loop", advanced=True),
    ]
    outputs = [
        Output(name="save_result", display_name="저장 결과", method="save"),
        Output(name="message", display_name="최종 출력", method="build_message"),
    ]

    def _request_variables(self) -> dict[str, Any]:
        try:
            graph = getattr(self, "graph", None)
            context = getattr(graph, "context", {}) if graph else {}
            request_variables = context.get("request_variables") if isinstance(context, dict) else {}
        except Exception:
            request_variables = {}
        return request_variables if isinstance(request_variables, dict) else {}

    async def _credential(self) -> str:
        run_token = str(self._request_variables().get("BOI_RUN_TOKEN") or "").strip()
        if run_token:
            return run_token
        try:
            value = await self.get_variables("BOI_WIKI_PAT", "value")
        except (TypeError, ValueError):
            value = ""
        raw_value = unwrap_secret_value(value)
        if str(raw_value or "").strip():
            return str(raw_value).strip()
        raise ValueError("BoI 지식 연결이 없습니다. Agent Playground 온보딩을 먼저 완료하세요.")

    async def _mcp_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {await self._credential()}"}
        variables = self._request_variables()
        for variable, header in {
            "BOI_ACTION_KEY": "X-BOI-Action-Key",
            "BOI_DEPLOYMENT_ID": "X-BOI-Deployment-ID",
            "BOI_ENDPOINT_ID": "X-BOI-Endpoint-ID",
            "BOI_PROJECT_ID": "X-BOI-Project-ID",
            "BOI_FLOW_ID": "X-BOI-Flow-ID",
            "BOI_TRACE_ID": "X-BOI-Trace-ID",
            "BOI_EXECUTION_ID": "X-BOI-Execution-ID",
        }.items():
            value = str(variables.get(variable) or "").strip()
            if value:
                headers[header] = value
        return headers

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        endpoint = os.getenv("BOI_WIKI_MCP_URL", "http://boi-wiki-mcp:8200/mcp/v2")
        async with streamablehttp_client(
            endpoint,
            headers=await self._mcp_headers(),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
        return _decode_tool_result(result)

    def _agent_payload(self) -> dict[str, Any]:
        return _redact(dict(getattr(self.agent_result, "data", {}) or {}))

    async def _result(self) -> dict[str, Any]:
        payload = self._agent_payload()
        cache_key = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        if (
            getattr(self, "_boi_save_cache_key", "") == cache_key
            and isinstance(getattr(self, "_boi_save_cache", None), dict)
        ):
            return dict(self._boi_save_cache)
        sources = [item for item in payload.get("source_references") or [] if isinstance(item, dict)]
        ontology_relationships = [
            item
            for item in payload.get("ontology_relationships") or []
            if isinstance(item, dict)
        ]
        requested_mode = "private_draft" if payload.get("save_mode") == "private_draft" else "preview"
        requested_title = str(payload.get("title") or self.title or "Agent Playground 개인 초안").strip()
        agent_provenance = (
            payload.get("provenance")
            if isinstance(payload.get("provenance"), dict)
            else {}
        )
        model_trace = (
            agent_provenance.get("model_agent")
            if isinstance(agent_provenance.get("model_agent"), dict)
            else payload.get("model_trace")
            if isinstance(payload.get("model_trace"), dict)
            else {}
        )
        trace = {
            "flow_id": str(self.flow_id or "boi-wiki-agent-loop"),
            "trace_id": str(payload.get("trace_id") or ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_references": sources,
            "ontology_relationships": ontology_relationships,
            "knowledge_provenance": agent_provenance,
            "task_context": payload.get("task_context") if isinstance(payload.get("task_context"), dict) else {},
            "agent_slot": payload.get("agent_slot") or "",
        }
        if model_trace:
            trace["model_agent"] = model_trace
        candidate = {
            "status": "preview",
            "mode": "preview",
            "title": requested_title,
            "answer": str(payload.get("answer") or ""),
            "source_references": sources,
            "ontology_relationships": ontology_relationships,
            "task_context": payload.get("task_context") if isinstance(payload.get("task_context"), dict) else {},
            "grounding_status": payload.get("grounding_status") or "unknown",
            "draft_reference": "",
            "wiki_url": "",
            "provenance": trace,
            "production_changed": False,
        }
        if requested_mode != "private_draft":
            self._boi_save_cache_key = cache_key
            self._boi_save_cache = dict(candidate)
            return candidate
        endpoint = os.getenv("BOI_WIKI_MCP_URL", "http://boi-wiki-mcp:8200/mcp/v2")
        async with streamablehttp_client(
            endpoint,
            headers=await self._mcp_headers(),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                async def call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    return _decode_tool_result(await session.call_tool(tool_name, arguments))

                plan = await call(
                    "boi_plan",
                    {
                        "capability_id": "knowledge.draft",
                        "goal": f"{candidate['title']}\n\n{candidate['answer']}",
                        "page_ref": "/playground",
                        "input": {
                            "structured_private_draft": True,
                            "title": candidate["title"],
                            "body": candidate["answer"],
                            "summary": candidate["answer"][:500],
                            "source_refs": sources,
                            "ontology_relationships": ontology_relationships,
                            "task_context": candidate["task_context"],
                            "visibility": "private",
                            "provenance": trace,
                        },
                    },
                )
                plan_id = str(plan.get("plan_id") or plan.get("plan_ref") or "")
                if not plan_id:
                    for item in plan.get("offers") or []:
                        if isinstance(item, dict) and item.get("plan_id"):
                            plan_id = str(item["plan_id"])
                            break
                if not plan_id:
                    raise ValueError("BoI knowledge.draft plan did not return a plan_id")
                confirmed = await call(
                    "boi_confirm",
                    {
                        "plan_id": plan_id,
                        "reason": "Agent Playground에서 private_draft 저장 방식을 명시적으로 선택했습니다.",
                    },
                )
        draft_reference = str(
            confirmed.get("domain_ref")
            or confirmed.get("artifact_id")
            or confirmed.get("candidate_id")
            or plan.get("draft_reference")
            or plan_id
        )
        result = _redact(
            {
                **candidate,
                "status": "saved",
                "mode": "private_draft",
                "draft_reference": draft_reference,
                "wiki_url": str(
                    confirmed.get("wiki_url")
                    or confirmed.get("url")
                    or plan.get("wiki_url")
                    or ""
                ),
                "provenance": {**trace, "plan_id": plan_id},
                "production_changed": True,
                "confirmation": confirmed,
            }
        )
        self._boi_save_cache_key = cache_key
        self._boi_save_cache = dict(result)
        return result

    async def save(self) -> Data:
        return Data(data=await self._result())

    async def build_message(self) -> Message:
        result = await self._result()
        text = str(result.get("answer") or "")
        if result.get("mode") == "private_draft":
            text += f"\n\n개인 Wiki 초안: {result.get('draft_reference') or '저장됨'}"
        else:
            text += "\n\n미리보기만 수행했습니다. Wiki는 변경하지 않았습니다."
        return Message(text=text.strip(), data=result)
