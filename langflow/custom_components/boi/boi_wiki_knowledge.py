from __future__ import annotations

import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from lfx.custom import Component
from lfx.io import IntInput, MessageInput, MultilineInput, Output
from lfx.schema import Data
from lfx.schema.message import Message
from lfx.utils.secrets import unwrap_secret_value


def _decode_tool_result(result: Any) -> dict[str, Any]:
    if bool(
        getattr(result, "isError", False)
        or getattr(result, "is_error", False)
    ):
        detail = " ".join(
            str(getattr(item, "text", "") or "").strip()
            for item in getattr(result, "content", []) or []
            if str(getattr(item, "text", "") or "").strip()
        )
        raise RuntimeError(detail or "BoI Wiki MCP tool call failed")
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


class BoIWikiKnowledge(Component):
    display_name = "Wiki에서 지식 가져오기"
    description = "Task·SOP 맥락을 자동 판별하고 ACL 내 Wiki 문서와 검증된 Ontology 관계를 함께 가져옵니다."
    icon = "book-open"
    name = "BoIWikiKnowledge"

    inputs = [
        MessageInput(name="question", display_name="질문", required=True),
        MultilineInput(name="business_context", display_name="업무 맥락", required=False),
        IntInput(name="limit", display_name="검색 개수", value=6, advanced=True),
    ]
    outputs = [
        Output(name="knowledge", display_name="근거가 포함된 지식", method="load_knowledge"),
        Output(name="agent_context", display_name="Agent 문맥", method="build_agent_context"),
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

    def _request_payload(self) -> dict[str, Any]:
        value = self.question
        if hasattr(value, "text"):
            value = value.text
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return {"question": text}
        if not isinstance(decoded, dict):
            return {"question": text}
        return decoded

    @staticmethod
    def _profile(request: dict[str, Any], business_context: str) -> str:
        task_ref = str(request.get("task_ref") or "").strip()
        page_ref = str(request.get("page_ref") or "").strip()
        explicit_sop = any(
            str(request.get(key) or "").strip()
            for key in ("sop_ref", "sop_stage", "stage_ref", "event_ref", "action_ref")
        )
        if task_ref and explicit_sop:
            return "sop_task_execution"
        if task_ref:
            return "task_execution"
        if page_ref or str(request.get("context_id") or "").strip():
            return "wiki_context"
        return "knowledge_lookup"

    @staticmethod
    def _grounded_edges(graph: dict[str, Any], *, view: str, seed: str) -> list[dict[str, Any]]:
        grounded: list[dict[str, Any]] = []
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            payload = edge.get("payload") if isinstance(edge.get("payload"), dict) else {}
            provenance = str(payload.get("provenance") or "")
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            source_refs = [
                str(item)
                for item in payload.get("source_refs") or []
                if str(item).strip()
            ]
            if metadata.get("source_ref"):
                source_refs.append(str(metadata["source_ref"]))
            source_refs = list(dict.fromkeys(source_refs))
            if provenance in {"", "inferred", "ambiguous"} or not source_refs:
                continue
            grounded.append(
                {
                    "edge_id": str(edge.get("edge_id") or ""),
                    "source_id": str(edge.get("source_id") or ""),
                    "target_id": str(edge.get("target_id") or ""),
                    "relation": str(edge.get("user_label") or payload.get("user_label") or edge.get("relation") or ""),
                    "provenance": provenance,
                    "source_refs": source_refs,
                    "view": view,
                    "seed": seed,
                }
            )
        return grounded

    async def _payload(self) -> dict[str, Any]:
        request = self._request_payload()
        cache_key = json.dumps(request, ensure_ascii=False, sort_keys=True, default=str)
        if (
            getattr(self, "_boi_payload_cache_key", "") == cache_key
            and isinstance(getattr(self, "_boi_payload_cache", None), dict)
        ):
            return dict(self._boi_payload_cache)
        question = str(request.get("question") or "").strip()
        if not question:
            raise ValueError("질문이 필요합니다.")
        business_context = str(request.get("business_context") or self.business_context or "").strip()
        task_anchor = (
            request.get("task_anchor")
            if isinstance(request.get("task_anchor"), dict)
            else {}
        )
        task_ref = str(
            task_anchor.get("task_id")
            or request.get("task_ref")
            or ""
        ).strip()
        page_ref = str(request.get("page_ref") or "").strip()
        context_id = str(request.get("context_id") or "").strip()
        profile = self._profile(request, business_context)
        endpoint = os.getenv("BOI_WIKI_MCP_URL", "http://boi-wiki-mcp:8200/mcp/v2")
        graph_results: list[dict[str, Any]] = []
        graph_errors: list[dict[str, str]] = []
        details: list[dict[str, Any]] = []
        context_pack: dict[str, Any] = {}
        async with streamablehttp_client(
            endpoint,
            headers=await self._mcp_headers(),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                async def call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    return _decode_tool_result(await session.call_tool(tool_name, arguments))

                search = await call(
                    "boi_search",
                    {
                        "query": question,
                        "include_history": True,
                        "include_drafts": False,
                        "limit": max(1, min(int(self.limit or 6), 12)),
                        "page_ref": page_ref,
                        "task_ref": task_ref,
                        "trace_id": str(
                            task_anchor.get("trace_id")
                            or request.get("trace_id")
                            or ""
                        ),
                        "event_id": str(
                            task_anchor.get("event_id")
                            or request.get("event_id")
                            or ""
                        ),
                        "action_key": str(
                            task_anchor.get("action_key")
                            or request.get("action_ref")
                            or ""
                        ),
                        "view": "ranked",
                    },
                )
                context_pack = (
                    search.get("context_pack")
                    if isinstance(search.get("context_pack"), dict)
                    else {}
                )
                profile = str(
                    context_pack.get("context_profile")
                    or search.get("context_profile")
                    or profile
                )
                items = [item for item in search.get("items") or [] if isinstance(item, dict)]
                resolved_task_seed = str(
                    (
                        context_pack.get("task")
                        if isinstance(context_pack.get("task"), dict)
                        else {}
                    ).get("task_id")
                    or task_ref
                ).strip()
                seeds = list(
                    dict.fromkeys(
                        [
                            *([resolved_task_seed] if resolved_task_seed else []),
                            *(
                                [str(request.get("sop_ref") or "").strip()]
                                if str(request.get("sop_ref") or "").strip()
                                else []
                            ),
                            *([page_ref] if page_ref else []),
                            *[
                                str(item.get("evidence_id") or item.get("ref") or "")
                                for item in items
                                if str(item.get("evidence_id") or item.get("ref") or "")
                            ],
                        ]
                    )
                )[:3]
                views = {
                    "sop_task_execution": ["workflow", "responsibility", "lineage", "impact"],
                    "task_execution": ["responsibility", "lineage", "impact"],
                    "wiki_context": ["neighbors", "lineage"],
                    "knowledge_lookup": ["neighbors"],
                }[profile]
                for seed_index, seed in enumerate(seeds):
                    selected_views = views if seed_index == 0 else views[:1]
                    for view in selected_views:
                        try:
                            graph = await call(
                                "boi_search",
                                {
                                    "query": question,
                                    "view": view,
                                    "source_ref": seed,
                                    "depth": 2,
                                    "limit": 40,
                                },
                            )
                            graph_results.append({"seed": seed, "view": view, **graph})
                        except Exception as exc:
                            graph_errors.append({"seed": seed, "view": view, "reason": type(exc).__name__})
                for item in items[:4]:
                    ref = str(item.get("evidence_id") or item.get("ref") or "").strip()
                    if not ref:
                        continue
                    try:
                        details.append(await call("boi_get", {"ref": ref}))
                    except Exception:
                        continue
        source_references = [
            {
                "ref": str(item.get("evidence_id") or item.get("ref") or ""),
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "source": str(item.get("source") or item.get("authority") or ""),
            }
            for item in items
        ]
        ontology_relationships: list[dict[str, Any]] = []
        for graph in graph_results:
            ontology_relationships.extend(
                self._grounded_edges(
                    graph,
                    view=str(graph.get("view") or ""),
                    seed=str(graph.get("seed") or ""),
                )
            )
        ontology_relationships = list(
            {
                (
                    item["source_id"],
                    item["relation"],
                    item["target_id"],
                    tuple(item["source_refs"]),
                ): item
                for item in ontology_relationships
            }.values()
        )[:40]
        denied_count = int(search.get("excluded_count") or search.get("permission_excluded_count") or 0)
        if items and ontology_relationships:
            grounding_status = "grounded_with_ontology"
        elif items:
            grounding_status = "grounded_document_fallback"
        elif ontology_relationships:
            grounding_status = "grounded_ontology_only"
        else:
            grounding_status = "no_accessible_evidence"
        resolved_task = (
            context_pack.get("task")
            if isinstance(context_pack.get("task"), dict)
            else {}
        )
        resolved_stage = (
            context_pack.get("sop_stage")
            if isinstance(context_pack.get("sop_stage"), dict)
            else {}
        )
        trace_context = (
            context_pack.get("trace_context")
            if isinstance(context_pack.get("trace_context"), dict)
            else {}
        )
        trace_events = [
            item
            for item in trace_context.get("events") or []
            if isinstance(item, dict)
        ]
        task_context = {
            "profile": profile,
            "task_ref": task_ref or str(resolved_task.get("task_id") or ""),
            "resolved_task_id": str(resolved_task.get("task_id") or ""),
            "page_ref": page_ref,
            "context_id": str(context_pack.get("context_id") or context_id),
            "sop_ref": str(resolved_stage.get("sop_ref") or ""),
            "sop_stage": str(resolved_stage.get("sop_stage_id") or ""),
            "workflow_definition_key": str(
                resolved_stage.get("workflow_definition_key") or ""
            ),
            "event_ref": str(
                (trace_events[-1].get("event_id") if trace_events else "")
                or resolved_task.get("event_type")
                or ""
            ),
            "action_ref": str(resolved_task.get("action_key") or ""),
            "prior_results": context_pack.get("stage_history_summary") or [],
            "required_evidence": context_pack.get("required_evidence") or [],
            "missing_evidence": (
                (context_pack.get("evidence_summary") or {}).get("missing_raw")
                if isinstance(context_pack.get("evidence_summary"), dict)
                else []
            ) or [],
        }
        context_lines = [
            f"Context profile: {profile}",
            f"질문: {question}",
            f"업무 맥락: {business_context}",
            "",
            "BoI Wiki 근거:",
        ]
        for index, item in enumerate(items, start=1):
            context_lines.append(
                f"{index}. {item.get('title') or item.get('evidence_id')} — "
                f"{item.get('summary') or item.get('description') or item.get('text') or ''}"
            )
        if ontology_relationships:
            context_lines.extend(["", "검증된 Ontology 관계:"])
            for relation in ontology_relationships[:12]:
                context_lines.append(
                    f"- {relation['source_id']} — {relation['relation']} → {relation['target_id']} "
                    f"(근거: {', '.join(relation['source_refs'])})"
                )
        elif graph_results:
            context_lines.extend(["", "검증 가능한 provenance가 없어 문서 근거로 대체했습니다."])
        payload = {
            "question": question,
            "business_context": business_context,
            "context_profile": profile,
            "task_context": task_context,
            "save_mode": "private_draft" if request.get("save_mode") == "private_draft" else "preview",
            "title": str(request.get("title") or "Agent Playground 개인 초안").strip(),
            "trace_id": str(request.get("trace_id") or "").strip(),
            "context": "\n".join(context_lines).strip(),
            "document_ids": [item["ref"] for item in source_references if item["ref"]],
            "source_references": source_references,
            "ontology_relationships": ontology_relationships,
            "grounding_status": grounding_status,
            "permission_excluded_count": denied_count,
            "retrieval": {
                "strategy": search.get("retrieval_strategy") or "ontology_hybrid",
                "ontology_terms": search.get("ontology_terms") or [],
                "document_fallback": bool(items and not ontology_relationships),
            },
            "ontology": {
                "attempted": bool(graph_results or graph_errors),
                "grounded_relationship_count": len(ontology_relationships),
                "degraded": graph_errors,
                "document_fallback": bool(items and not ontology_relationships),
            },
            "context_pack": context_pack,
            "details": details,
            "provenance": {
                "document_refs": [item["ref"] for item in source_references if item["ref"]],
                "ontology_source_refs": list(
                    dict.fromkeys(
                        ref
                        for relation in ontology_relationships
                        for ref in relation["source_refs"]
                    )
                ),
            },
        }
        self._boi_payload_cache_key = cache_key
        self._boi_payload_cache = dict(payload)
        return payload

    async def load_knowledge(self) -> Data:
        return Data(data=await self._payload())

    async def build_agent_context(self) -> Message:
        payload = await self._payload()
        return Message(text=payload["context"], data=payload)
