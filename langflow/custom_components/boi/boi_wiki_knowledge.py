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

    async def _credential(self) -> str:
        try:
            graph = getattr(self, "graph", None)
            context = getattr(graph, "context", {}) if graph else {}
            request_variables = context.get("request_variables") if isinstance(context, dict) else {}
            run_token = str((request_variables or {}).get("BOI_RUN_TOKEN") or "").strip()
        except Exception:
            run_token = ""
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
        combined = " ".join(
            [
                business_context,
                str(request.get("question") or ""),
                str(request.get("task_type") or ""),
            ]
        ).lower()
        if task_ref and (explicit_sop or "sop" in combined or "표준작업" in combined):
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
        task_ref = str(request.get("task_ref") or "").strip()
        page_ref = str(request.get("page_ref") or "").strip()
        context_id = str(request.get("context_id") or "").strip()
        profile = self._profile(request, business_context)
        token = await self._credential()
        endpoint = os.getenv("BOI_WIKI_MCP_URL", "http://boi-wiki-mcp:8200/mcp/v2")
        graph_results: list[dict[str, Any]] = []
        graph_errors: list[dict[str, str]] = []
        details: list[dict[str, Any]] = []
        context_pack: dict[str, Any] = {}
        async with streamablehttp_client(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                async def call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    return _decode_tool_result(await session.call_tool(tool_name, arguments))

                if context_id:
                    try:
                        context_pack = await call("boi_context", {"context_id": context_id})
                    except Exception as exc:
                        graph_errors.append({"view": "context", "reason": type(exc).__name__})
                search = await call(
                    "boi_search",
                    {
                        "query": question,
                        "include_history": True,
                        "include_drafts": False,
                        "limit": max(1, min(int(self.limit or 6), 12)),
                        "page_ref": page_ref,
                        "task_ref": task_ref,
                        "view": "ranked",
                    },
                )
                items = [item for item in search.get("items") or [] if isinstance(item, dict)]
                seeds = list(
                    dict.fromkeys(
                        [
                            *([task_ref] if task_ref else []),
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
        task_context = {
            "profile": profile,
            "task_ref": task_ref,
            "page_ref": page_ref,
            "context_id": context_id,
            "sop_ref": str(request.get("sop_ref") or ""),
            "sop_stage": str(request.get("sop_stage") or request.get("stage_ref") or ""),
            "event_ref": str(request.get("event_ref") or ""),
            "action_ref": str(request.get("action_ref") or ""),
            "prior_results": request.get("prior_results") or [],
            "required_evidence": request.get("required_evidence") or [],
            "missing_evidence": request.get("missing_evidence") or [],
        }
        if profile != "sop_task_execution":
            task_context["sop_ref"] = ""
            task_context["sop_stage"] = ""
            task_context["event_ref"] = ""
            task_context["action_ref"] = ""
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
            "search": {
                "mode": search.get("mode"),
                "degraded": search.get("degraded") or [],
                "index_manifest": search.get("index_manifest") or {},
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
