from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

try:  # LangGraph is installed in the runtime image; tests can still run without it.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback is exercised when dependency is absent.
    END = "__end__"
    START = "__start__"
    StateGraph = None

LANGGRAPH_AVAILABLE = StateGraph is not None


JsonDict = dict[str, Any]


@dataclass
class NativeAgentConfig:
    max_tool_loops: int = 5
    tool_timeout_seconds: float = 8.0
    build_revision: str = "unknown"
    llm_enabled: bool = False


@dataclass
class NativeAgentTools:
    ontology_search: Callable[[str, str, int], JsonDict]
    boi_get: Callable[[str], JsonDict | None]
    event_type_lookup: Callable[[str], JsonDict | None]
    action_spec_lookup: Callable[[str], JsonDict | None]
    workflow_status: Callable[[str, str], JsonDict | None]
    trace_context_lookup: Callable[[str], JsonDict]
    dictionary_resolve: Callable[[str], JsonDict]
    memory_recall: Callable[[str, int], JsonDict]
    agent_inbox: Callable[[int], JsonDict]
    llm_json: Callable[[str, JsonDict], JsonDict | None] | None = None


@dataclass
class ToolTraceItem:
    tool: str
    status: str
    elapsed_ms: int
    summary: str = ""
    args: JsonDict = field(default_factory=dict)
    result: JsonDict | list[Any] | None = None


class NativeBoiAgent:
    """Native BoI Agent runtime.

    The graph is intentionally deterministic around tool execution. The LLM can
    influence planning/composition through JSON, but all tool dispatch and safety
    boundaries are controlled in Python.
    """

    def __init__(self, tools: NativeAgentTools, config: NativeAgentConfig | None = None) -> None:
        self.tools = tools
        self.config = config or NativeAgentConfig()

    def run(self, request: JsonDict, route: JsonDict, context_pack: JsonDict) -> JsonDict:
        state: JsonDict = {
            "run_id": f"boi-agent-run-{uuid.uuid4().hex[:12]}",
            "request": request,
            "route": route,
            "context_pack": context_pack,
            "page_context": context_pack.get("page_context") or {},
            "search": context_pack.get("ontology_search_seed") or {},
            "tool_trace": [],
            "tool_results": {},
            "artifacts": [],
            "links": [],
            "citations": [],
            "coverage_report": {},
            "answer_markdown": "",
            "access_summary": context_pack.get("access_summary") or {},
            "guardrails_applied": [],
        }
        if StateGraph is not None:
            return self._run_langgraph(state)
        return self._run_sequential(state)

    def _run_sequential(self, state: JsonDict) -> JsonDict:
        for node in (
            self._classify_intent,
            self._resolve_page_context,
            self._access_policy_gate,
            self._retrieve_ontology,
            self._plan_tools,
            self._execute_tools_loop,
            self._evaluate_coverage,
            self._compose_answer,
            self._verify_acl_and_artifacts,
            self._safety_gate,
        ):
            state = node(state)
        return self._response(state)

    def _run_langgraph(self, state: JsonDict) -> JsonDict:
        try:
            graph = StateGraph(dict)
            graph.add_node("classify_intent", self._classify_intent)
            graph.add_node("resolve_page_context", self._resolve_page_context)
            graph.add_node("access_policy_gate", self._access_policy_gate)
            graph.add_node("retrieve_ontology", self._retrieve_ontology)
            graph.add_node("plan_tools", self._plan_tools)
            graph.add_node("execute_tools_loop", self._execute_tools_loop)
            graph.add_node("evaluate_coverage", self._evaluate_coverage)
            graph.add_node("compose_answer", self._compose_answer)
            graph.add_node("verify_acl_and_artifacts", self._verify_acl_and_artifacts)
            graph.add_node("safety_gate", self._safety_gate)
            graph.add_edge(START, "classify_intent")
            graph.add_edge("classify_intent", "resolve_page_context")
            graph.add_edge("resolve_page_context", "access_policy_gate")
            graph.add_edge("access_policy_gate", "retrieve_ontology")
            graph.add_edge("retrieve_ontology", "plan_tools")
            graph.add_edge("plan_tools", "execute_tools_loop")
            graph.add_edge("execute_tools_loop", "evaluate_coverage")
            graph.add_edge("evaluate_coverage", "compose_answer")
            graph.add_edge("compose_answer", "verify_acl_and_artifacts")
            graph.add_edge("verify_acl_and_artifacts", "safety_gate")
            graph.add_edge("safety_gate", END)
            compiled = graph.compile()
            final_state = compiled.invoke(state)
            final_state["langgraph_available"] = True
            return self._response(final_state)
        except Exception as exc:  # pragma: no cover - depends on installed LangGraph version.
            state["langgraph_available"] = False
            state["langgraph_error"] = repr(exc)
            return self._run_sequential(state)

    def _classify_intent(self, state: JsonDict) -> JsonDict:
        route = state.get("route") or {}
        request = state.get("request") or {}
        state["intent"] = str(route.get("intent") or request.get("intent") or "search")
        state["route_name"] = str(route.get("route") or "fast")
        state["question"] = str(request.get("question") or "")
        return state

    def _resolve_page_context(self, state: JsonDict) -> JsonDict:
        page_context = state.get("page_context") or {}
        boi_id = str(page_context.get("boi_id") or page_context.get("sop_ref") or "")
        if boi_id and "current_doc" not in state.get("tool_results", {}):
            doc = self._call_tool("boi_get", {"boi_id": boi_id}, lambda: self.tools.boi_get(boi_id), state)
            if doc:
                state.setdefault("tool_results", {})["current_doc"] = doc
        return state

    def _access_policy_gate(self, state: JsonDict) -> JsonDict:
        state.setdefault("guardrails_applied", []).append("acl_policy")
        access = state.get("access_summary") if isinstance(state.get("access_summary"), dict) else {}
        if access and access.get("can_read") is False:
            state["route_name"] = "approval_required"
            state["intent"] = "access_denied"
            state["answer_markdown"] = "현재 권한으로 이 BoI를 Agent 컨텍스트에 사용할 수 없습니다."
            state["stop_reason"] = "access_denied"
        if access and access.get("can_use_in_agent_context") is False:
            state.setdefault("guardrails_applied", []).append("classification_redaction")
        return state

    def _retrieve_ontology(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            return state
        search = state.get("search") or {}
        if not search.get("ok"):
            query = state.get("question") or ""
            search = self._call_tool("ontology_search", {"query": query, "scope": "all"}, lambda: self.tools.ontology_search(query, "all", 8), state) or {}
        state["search"] = search
        state.setdefault("tool_results", {})["ontology_search"] = search
        return state

    def _plan_tools(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            state["planned_tools"] = []
            return state
        intent = state.get("intent")
        page_context = state.get("page_context") or {}
        planned: list[JsonDict] = []
        if intent in {"diagram", "workflow_explain", "gap_check"} and page_context.get("boi_id"):
            planned.append({"tool": "boi_get", "args": {"boi_id": page_context["boi_id"]}})
        if intent == "trace_reasoning" and page_context.get("trace_id"):
            planned.append({"tool": "trace_context_lookup", "args": {"trace_id": page_context["trace_id"]}})
            if page_context.get("workflow_key"):
                planned.append({"tool": "workflow_status", "args": {"workflow_key": page_context["workflow_key"], "trace_id": page_context["trace_id"]}})
        if intent == "inbox":
            planned.append({"tool": "agent_inbox", "args": {"limit": 10}})
        if state.get("question"):
            planned.append({"tool": "dictionary_resolve", "args": {"query": state["question"]}})
            planned.append({"tool": "memory_recall", "args": {"query": state["question"], "limit": 5}})
        state["planned_tools"] = planned[: self.config.max_tool_loops]
        return state

    def _execute_tools_loop(self, state: JsonDict) -> JsonDict:
        results = state.setdefault("tool_results", {})
        for item in state.get("planned_tools") or []:
            tool = item.get("tool")
            args = item.get("args") or {}
            if tool == "boi_get":
                boi_id = str(args.get("boi_id") or "")
                result = self._call_tool(tool, args, lambda boi_id=boi_id: self.tools.boi_get(boi_id), state)
                if result:
                    results["current_doc"] = result
            elif tool == "trace_context_lookup":
                trace_id = str(args.get("trace_id") or "")
                results["trace_context"] = self._call_tool(tool, args, lambda trace_id=trace_id: self.tools.trace_context_lookup(trace_id), state)
            elif tool == "workflow_status":
                workflow_key = str(args.get("workflow_key") or "")
                trace_id = str(args.get("trace_id") or "")
                results["workflow_status"] = self._call_tool(tool, args, lambda workflow_key=workflow_key, trace_id=trace_id: self.tools.workflow_status(workflow_key, trace_id), state)
            elif tool == "agent_inbox":
                limit = int(args.get("limit") or 10)
                results["agent_inbox"] = self._call_tool(tool, args, lambda limit=limit: self.tools.agent_inbox(limit), state)
            elif tool == "dictionary_resolve":
                query = str(args.get("query") or "")
                results["dictionary"] = self._call_tool(tool, args, lambda query=query: self.tools.dictionary_resolve(query), state)
            elif tool == "memory_recall":
                query = str(args.get("query") or "")
                limit = int(args.get("limit") or 5)
                results["memory"] = self._call_tool(tool, args, lambda query=query, limit=limit: self.tools.memory_recall(query, limit), state)
        self._expand_action_specs_from_doc(state)
        return state

    def _expand_action_specs_from_doc(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc")
        metadata = doc.get("metadata") if isinstance(doc, dict) else {}
        workflow = metadata.get("workflow") if isinstance(metadata, dict) else {}
        actions: list[str] = []
        for stage in (workflow or {}).get("stages") or []:
            for key in stage.get("automated_actions") or []:
                if key not in actions:
                    actions.append(str(key))
            for key in stage.get("manual_actions") or []:
                if key not in actions:
                    actions.append(str(key))
        looked_up: list[JsonDict] = []
        for action_key in actions[:12]:
            result = self._call_tool("action_spec_lookup", {"action_key": action_key}, lambda action_key=action_key: self.tools.action_spec_lookup(action_key), state)
            if result:
                looked_up.append(result)
        if looked_up:
            state.setdefault("tool_results", {})["action_specs"] = looked_up

    def _evaluate_coverage(self, state: JsonDict) -> JsonDict:
        intent = state.get("intent")
        results = state.get("tool_results") or {}
        checks = {
            "page_context": bool((state.get("page_context") or {}).get("resolved")),
            "ontology_search": bool((state.get("search") or {}).get("best_matches")),
            "current_doc": bool(results.get("current_doc")),
            "action_specs": bool(results.get("action_specs")),
            "trace_context": bool(results.get("trace_context") or results.get("workflow_status")),
        }
        required = ["ontology_search"]
        if intent in {"diagram", "workflow_explain", "gap_check"}:
            required.append("current_doc")
        if intent == "gap_check":
            required.append("action_specs")
        if intent == "trace_reasoning":
            required.append("trace_context")
        covered = [key for key in required if checks.get(key)]
        state["coverage_report"] = {
            "required": required,
            "covered": covered,
            "missing": [key for key in required if key not in covered],
            "coverage_score": round(len(covered) / len(required), 2) if required else 1.0,
        }
        return state

    def _compose_answer(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            return state
        intent = state.get("intent")
        if intent == "diagram":
            self._compose_diagram_answer(state)
        elif intent == "gap_check":
            self._compose_gap_answer(state)
        elif intent == "workflow_explain":
            self._compose_workflow_answer(state)
        elif intent == "trace_reasoning":
            self._compose_trace_answer(state)
        elif intent == "inbox":
            self._compose_inbox_answer(state)
        else:
            self._compose_search_answer(state)
        return state

    def _compose_diagram_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        mermaid = workflow_mermaid(doc)
        mapping_rows = workflow_summary_rows(doc)
        state["artifacts"] = [{"type": "mermaid", "title": "SOP workflow", "source": mermaid}]
        title = doc_title(doc, "현재 SOP")
        state["answer_markdown"] = (
            f"## {title} 프로세스 플로우\n\n"
            "SOP metadata의 stage, event, action, manual handoff를 기준으로 그렸습니다. "
            "다이어그램은 읽기 쉽게 단계와 항목 개수 중심으로 줄이고, 전체 원본 매핑은 아래 표에 남겼습니다.\n\n"
            f"```mermaid\n{mermaid}\n```\n"
            "\n## Source Mapping\n\n"
            + markdown_table(mapping_rows, ["stage", "events", "actions", "manual_actions", "next_stage"])
        )
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {})
        state["citations"] = state["links"][:5]

    def _compose_gap_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        specs = (state.get("tool_results") or {}).get("action_specs") or []
        rows = action_gap_rows(doc, specs)
        state["artifacts"] = [{"type": "gap_table", "data": rows}]
        lines = [f"## {doc_title(doc, '현재 SOP')} Action Spec 점검", "", "| Action | 상태 | 근거 |", "|---|---|---|"]
        for row in rows:
            lines.append(f"| `{row['action_key']}` | {row['status_label']} | {row['evidence']} |")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {})
        state["citations"] = state["links"][:5]

    def _compose_workflow_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        rows = workflow_summary_rows(doc)
        state["artifacts"] = [{"type": "workflow_summary", "data": rows}]
        lines = [f"## {doc_title(doc, 'BoI Workflow')} 관계 요약", ""]
        for row in rows:
            lines.append(
                f"- **{row['stage']}**: Event `{row['events']}` → Action `{row['actions']}` → Manual `{row['manual_actions']}` → Next `{row['next_stage']}`"
            )
        if not rows:
            lines.append("현재 문서에서 workflow metadata를 찾지 못했습니다. 연결된 SOP/Event/Action 문서를 더 확인해야 합니다.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {})
        state["citations"] = state["links"][:5]

    def _compose_trace_answer(self, state: JsonDict) -> None:
        workflow = (state.get("tool_results") or {}).get("workflow_status") or {}
        trace = (state.get("tool_results") or {}).get("trace_context") or {}
        lines = ["## Trace 실행 상태 요약", ""]
        if workflow:
            lines.append(f"- Workflow: `{workflow.get('workflow_key') or workflow.get('workflow') or '-'}`")
            lines.append(f"- Event count: {len(workflow.get('events') or [])}")
            lines.append(f"- Action count: {len(workflow.get('actions') or [])}")
            lines.append(f"- Manual handoff count: {len(workflow.get('manual_handoffs') or [])}")
        elif trace:
            lines.append(f"- Trace events: {len(trace.get('events') or [])}")
            lines.append(f"- Trace actions: {len(trace.get('actions') or [])}")
        else:
            lines.append("현재 trace context를 찾지 못했습니다. Workflow Status나 Event Stream 링크로 trace를 확인해야 합니다.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = trace_links(workflow, trace)
        state["citations"] = state["links"][:5]

    def _compose_inbox_answer(self, state: JsonDict) -> None:
        inbox = (state.get("tool_results") or {}).get("agent_inbox") or {}
        items = inbox.get("items") or []
        lines = [f"현재 처리할 업무는 {len(items)}건입니다.", ""]
        cards = []
        for item in items[:10]:
            display = item.get("display") if isinstance(item.get("display"), dict) else {}
            title = display.get("title") or item.get("action_key") or "업무 확인"
            status = display.get("status_label") or item.get("status") or "확인 필요"
            next_action = display.get("next_action") or "Workflow/Raw를 확인하세요."
            url = display.get("primary_url") or item.get("workflow_url") or item.get("raw_url") or ""
            title_md = f"[{title}]({url})" if url else f"**{title}**"
            lines.append(f"- {status}: {title_md} - {next_action}")
            cards.append(display or item)
        state["answer_markdown"] = "\n".join(lines).strip()
        state["artifacts"] = [{"type": "task_cards", "data": cards}]
        state["links"] = [
            {"label": str(item.get("action_key") or item.get("request_id") or "Inbox"), "url": str(item.get("workflow_url") or item.get("raw_url") or ""), "kind": "inbox"}
            for item in items
            if item.get("workflow_url") or item.get("raw_url")
        ]
        state["citations"] = []

    def _compose_search_answer(self, state: JsonDict) -> None:
        search = state.get("search") or {}
        page = state.get("page_context") or {}
        lines = []
        if page.get("resolved"):
            lines.append(f"현재 화면 **{page.get('title') or page.get('page_kind')}** 기준으로 관련 지식을 찾았습니다.")
        else:
            lines.append("BoI Wiki ontology search 기준으로 관련 지식을 찾았습니다.")
        expansion = search.get("query_expansion") or []
        if expansion:
            lines.append("해석한 업무 용어: " + ", ".join(f"`{term}`" for term in expansion[:6]))
        matches = search.get("best_matches") or []
        for item in matches[:5]:
            label = item_label(item)
            url = str(item.get("url") or "")
            desc = compact_text(str(item.get("description") or item.get("match_reason") or ""), 140)
            lines.append(f"- [{label}]({url}) - {desc}" if url else f"- **{label}** - {desc}")
        if not matches:
            lines.append("직접 연결된 결과를 찾지 못했습니다. 더 구체적인 SOP, Event, Action 이름으로 다시 물어보세요.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = links_from_search(search)
        state["citations"] = state["links"][:5]

    def _verify_acl_and_artifacts(self, state: JsonDict) -> JsonDict:
        seen: set[str] = set()
        links = []
        for link in state.get("links") or []:
            url = str(link.get("url") or link.get("href") or "")
            label = str(link.get("label") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({"label": label or url, "url": url, "kind": str(link.get("kind") or "reference")})
        state["links"] = links[:12]
        state["citations"] = [item for item in state.get("citations") or [] if item.get("url") or item.get("ref")][:8]
        state.setdefault("guardrails_applied", []).append("artifact_link_acl")
        return state

    def _safety_gate(self, state: JsonDict) -> JsonDict:
        route_name = state.get("route_name")
        if route_name in {"manual_handoff", "approval_required"}:
            state["answer_markdown"] = (
                "이 요청은 상태 변경 또는 승인 절차가 필요합니다. Agent가 바로 실행하지 않고 확인 카드와 승인 API를 통해 처리해야 합니다."
            )
            state["artifacts"] = [
                {
                    "type": "confirmation_required",
                    "data": {
                        "route": route_name,
                        "intent": state.get("intent"),
                        "message": "명시 승인 후에만 실행할 수 있습니다.",
                    },
                }
            ]
        return state

    def _response(self, state: JsonDict) -> JsonDict:
        route = state.get("route") or {}
        return {
            "ok": True,
            "run_id": state.get("run_id"),
            "answer_markdown": state.get("answer_markdown") or "",
            "links": state.get("links") or [],
            "citations": state.get("citations") or [],
            "suggested_questions": suggested_questions_for_state(state),
            "artifacts": state.get("artifacts") or [],
            "context_summary": {
                "route": state.get("route_name"),
                "intent": state.get("intent"),
                "router_backend": route.get("router_backend"),
                "router_confidence": route.get("confidence"),
                "used_backend": "native_langgraph",
                "page_context": state.get("page_context") or {},
                "langgraph_available": bool(state.get("langgraph_available")),
            },
            "route": state.get("route_name"),
            "intent": state.get("intent"),
            "router_backend": route.get("router_backend"),
            "router_confidence": route.get("confidence"),
            "used_backend": "native_langgraph",
            "tool_trace": [item.__dict__ for item in state.get("tool_trace") or []],
            "coverage_report": state.get("coverage_report") or {},
            "deployment_revision": self.config.build_revision,
            "access_summary": state.get("access_summary") or {},
            "guardrails_applied": state.get("guardrails_applied") or [],
            "redacted_count": len((state.get("access_summary") or {}).get("redactions") or []),
        }

    def _call_tool(self, name: str, args: JsonDict, fn: Callable[[], Any], state: JsonDict) -> Any:
        started = time.perf_counter()
        try:
            result = fn()
            status = "ok" if result else "empty"
            summary = summarize_tool_result(result)
        except Exception as exc:  # pragma: no cover - defensive guard for runtime tools.
            result = {"error": repr(exc)}
            status = "failed"
            summary = repr(exc)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        state.setdefault("tool_trace", []).append(ToolTraceItem(tool=name, status=status, elapsed_ms=elapsed_ms, summary=summary, args=args, result=compact_tool_result(result)))
        return result


def summarize_tool_result(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("title"):
            return str(result["title"])
        if result.get("count") is not None:
            return f"count={result.get('count')}"
        if result.get("best_matches") is not None:
            return f"best_matches={len(result.get('best_matches') or [])}"
    if isinstance(result, list):
        return f"items={len(result)}"
    return "ok" if result else "empty"


def compact_tool_result(result: Any) -> Any:
    if isinstance(result, dict):
        keys = ("ok", "title", "boi_id", "event_type", "action_key", "count", "status", "workflow_key", "trace_id")
        compact = {key: result.get(key) for key in keys if key in result}
        if result.get("best_matches") is not None:
            compact["best_matches"] = [item_label(item) for item in (result.get("best_matches") or [])[:5]]
        return compact or {"keys": sorted(result.keys())[:12]}
    if isinstance(result, list):
        return {"items": len(result)}
    return result


def compact_text(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def item_label(item: JsonDict) -> str:
    return str(item.get("title") or item.get("term") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or item.get("uri") or "결과")


def doc_title(doc: JsonDict, fallback: str) -> str:
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    return str((metadata or {}).get("title") or doc.get("title") or fallback)


def workflow_stages(doc: JsonDict) -> list[JsonDict]:
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    workflow = (metadata or {}).get("workflow") if isinstance(metadata, dict) else {}
    stages = workflow.get("stages") if isinstance(workflow, dict) else []
    return [stage for stage in stages if isinstance(stage, dict)]


def workflow_mermaid(doc: JsonDict) -> str:
    stages = workflow_stages(doc)
    if not stages:
        return 'flowchart TD\n  current["현재 문서"] --> missing["workflow metadata 확인 필요"]'
    lines = ["flowchart TD"]
    for index, stage in enumerate(stages, start=1):
        node = f"s{index}"
        label = mermaid_label(str(stage.get("name") or stage.get("id") or f"Stage {index}"))
        lines.append(f'  {node}["{label}"]')
        events = stage.get("event_types") or ([stage.get("entry_event")] if stage.get("entry_event") else [])
        automated_actions = stage.get("automated_actions") or []
        manual_actions = stage.get("manual_actions") or []
        if events:
            event_label = "Event" if len(events) == 1 else f"Events ({len(events)})"
            lines.append(f'  e{index}["{event_label}"] --> {node}')
        if automated_actions:
            action_label = "Automated Action" if len(automated_actions) == 1 else f"Automated Actions ({len(automated_actions)})"
            lines.append(f'  {node} --> a{index}["{action_label}"]')
        if manual_actions:
            manual_label = "Manual Handoff" if len(manual_actions) == 1 else f"Manual Handoffs ({len(manual_actions)})"
            lines.append(f'  {node} --> m{index}["{manual_label}"]')
        if index < len(stages):
            lines.append(f"  {node} --> s{index + 1}")
    return "\n".join(lines)


def mermaid_label(value: str, limit: int = 34) -> str:
    text = re.sub(r"[\r\n\t]+", " ", value or "").strip().replace('"', "'")
    return text[: limit - 1] + "…" if len(text) > limit else text


def workflow_summary_rows(doc: JsonDict) -> list[JsonDict]:
    rows = []
    for stage in workflow_stages(doc):
        events = stage.get("event_types") or ([stage.get("entry_event")] if stage.get("entry_event") else [])
        rows.append(
            {
                "stage": str(stage.get("name") or stage.get("id") or ""),
                "events": ", ".join(str(item) for item in events if item),
                "actions": ", ".join(str(item) for item in stage.get("automated_actions") or []),
                "manual_actions": ", ".join(str(item) for item in stage.get("manual_actions") or []),
                "next_stage": str(stage.get("next_stage") or stage.get("emits_event") or "완료"),
            }
        )
    return rows


def markdown_table(rows: list[JsonDict], columns: list[str]) -> str:
    if not rows:
        return "_No workflow mapping available._\n"
    labels = {
        "stage": "Stage",
        "events": "Events",
        "actions": "Automated Actions",
        "manual_actions": "Manual Handoff",
        "next_stage": "Next",
    }
    header = "| " + " | ".join(labels.get(column, column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = []
        for column in columns:
            values.append(markdown_cell(str(row.get(column) or "-")))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body]) + "\n"


def markdown_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "\\|")).strip() or "-"


def action_gap_rows(doc: JsonDict, specs: list[JsonDict]) -> list[JsonDict]:
    found: dict[str, JsonDict] = {}
    for spec in specs:
        item = spec.get("item") if isinstance(spec.get("item"), dict) else spec
        key = str((item or {}).get("action_key") or "")
        if key:
            found[key] = spec
    keys: list[str] = []
    for stage in workflow_stages(doc):
        for key in (stage.get("automated_actions") or []) + (stage.get("manual_actions") or []):
            if str(key) not in keys:
                keys.append(str(key))
    rows = []
    for key in keys:
        spec = found.get(key)
        doc_ref = str(((spec or {}).get("item") or spec or {}).get("doc_ref") or "")
        rows.append(
            {
                "action_key": key,
                "status_label": "명세 있음" if spec and doc_ref else "보강 필요",
                "evidence": doc_ref or "catalog/doc_ref 또는 executable spec 확인 필요",
            }
        )
    return rows or [{"action_key": "-", "status_label": "workflow action 없음", "evidence": "SOP workflow metadata 보강 필요"}]


def links_from_search(search: JsonDict) -> list[JsonDict]:
    links = []
    for item in search.get("best_matches") or []:
        url = str(item.get("url") or "")
        if url:
            links.append({"label": item_label(item), "url": url, "kind": str(item.get("kind") or "search")})
    return links


def links_from_doc_and_search(doc: JsonDict, search: JsonDict) -> list[JsonDict]:
    links = []
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    if metadata and metadata.get("boi_id"):
        links.append({"label": str(metadata.get("title") or metadata.get("boi_id")), "url": str(doc.get("url") or ""), "kind": "current_doc"})
    links.extend(links_from_search(search))
    return links


def trace_links(workflow: JsonDict, trace: JsonDict) -> list[JsonDict]:
    links = []
    for doc in (workflow.get("generated_docs") if isinstance(workflow, dict) else []) or []:
        url = str(doc.get("url") or "")
        if url:
            links.append({"label": str(doc.get("title") or doc.get("boi_id") or "Generated BoI"), "url": url, "kind": "generated_boi"})
    for row in (trace.get("actions") if isinstance(trace, dict) else []) or []:
        url = str(row.get("raw_url") or "")
        if url:
            links.append({"label": str(row.get("action_key") or row.get("request_id") or "Action Raw"), "url": url, "kind": "action_raw"})
    return links


def suggested_questions_for_state(state: JsonDict) -> list[str]:
    intent = state.get("intent")
    if intent == "diagram":
        return ["이 SOP의 Action Spec 누락을 점검해줘.", "이 Event가 발생하면 뭘 해야 해?"]
    if intent == "gap_check":
        return ["누락된 Action Spec 초안을 만들어줘.", "이 workflow를 Mermaid로 보여줘."]
    if intent == "inbox":
        return ["가장 먼저 처리할 일을 알려줘.", "승인 대기 건만 보여줘."]
    return ["이 내용을 Mermaid로 보여줘.", "관련 Action과 Event를 요약해줘.", "부족한 명세가 있는지 찾아줘."]
