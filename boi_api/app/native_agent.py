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

ALLOWED_AGENT_ROUTES = {"fast", "deep", "inbox", "manual_handoff", "approval_required"}
ALLOWED_AGENT_INTENTS = {
    "search",
    "page_qa",
    "summarize",
    "diagram",
    "workflow_explain",
    "gap_check",
    "trace_reasoning",
    "inbox",
    "manual_complete",
    "approval",
    "event_publish",
    "action_invoke",
    "workflow_start",
    "event_type_draft",
    "access_denied",
}
DEEP_AGENT_INTENTS = {"diagram", "workflow_explain", "gap_check", "trace_reasoning"}
MUTATION_AGENT_INTENTS = {"manual_complete", "approval", "event_publish", "action_invoke", "workflow_start", "event_type_draft"}


def normalize_native_route(value: str, fallback: str = "fast") -> str:
    route = str(value or "").strip().lower().replace("-", "_")
    return route if route in ALLOWED_AGENT_ROUTES else fallback


def normalize_native_intent(value: str, *, fallback: str = "search") -> str:
    intent = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "lookup": "search",
        "page_summary": "summarize",
        "summary": "summarize",
        "workflow_reasoning": "trace_reasoning",
        "reasoning": "trace_reasoning",
        "manual_handoff": "manual_complete",
        "approval_required": "approval",
        "publish_event": "event_publish",
        "event": "event_publish",
        "invoke_action": "action_invoke",
        "action": "action_invoke",
        "start_workflow": "workflow_start",
    }
    intent = aliases.get(intent, intent)
    return intent if intent in ALLOWED_AGENT_INTENTS else fallback


def safety_route_override(question: str) -> str | None:
    q = str(question or "").lower()
    manual_action_terms = ("handoff 완료", "핸드오프 완료", "조치 완료", "완료 처리", "조치내용", "조치 내용", "완료 기록", "완료로 기록")
    approval_terms = ("승인", "approve", "실행해", "실행해줘", "invoke", "publish", "게시", "배포", "반영", "적용", "source_apply", "doc_body_apply")
    if any(term in q for term in manual_action_terms):
        return "manual_handoff"
    if any(term in q for term in approval_terms):
        return "approval_required"
    return None


def deterministic_native_intent(question: str, current_url: str = "") -> str:
    q = str(question or "").lower()
    if any(term in q for term in ("내 action", "내 액션", "내 할 일", "할 일", "처리해야", "inbox", "대기", "남았", "담당")):
        return "inbox"
    if (
        any(term in q for term in ("event type", "event-type", "이벤트 타입", "이벤트 정의", "신규 이벤트"))
        and any(term in q for term in ("초안", "만들", "생성", "정의", "추가", "draft", "create"))
    ):
        return "event_type_draft"
    if event_type_from_text(question) and any(term in q for term in ("이벤트 발행", "event 발행", "publish event", "이벤트를 발행", "이벤트 발생", "발행해", "발행해줘")):
        return "event_publish"
    if any(term in q for term in ("workflow 시작", "workflow 실행", "워크플로우 시작", "워크플로우 실행", "workflow start", "start workflow")):
        return "workflow_start"
    if action_key_from_text(question) and any(term in q for term in ("action 실행", "액션 실행", "action 요청", "액션 요청", "invoke", "호출", "실행해", "실행해줘")):
        return "action_invoke"
    if safety := safety_route_override(q):
        return "manual_complete" if safety == "manual_handoff" else "approval"
    if any(term in q for term in ("mermaid", "머메이드", "flowchart", "다이어그램", "도식", "프로세스 플로우", "프로세스플로우", "그려", "그려줘")):
        return "diagram"
    if any(term in q for term in ("부족", "누락", "없는지", "없나", "gap", "갭", "action spec", "액션 spec", "명세", "완성도")):
        return "gap_check"
    if any(term in q for term in ("trace", "트레이스", "workflow status", "로그", "왜", "원인", "리스크", "시뮬레이션", "추론", "판단")):
        return "trace_reasoning"
    if any(term in q for term in ("찾", "검색", "링크", "목록", "어디", "보여줘")):
        return "search"
    if any(term in q for term in ("event", "이벤트", "action", "액션", "manual handoff", "handoff", "핸드오프", "관계", "흐름", "발생하면", "뭘 해야", "어떻게 해야", "이어지는")):
        return "workflow_explain"
    if any(term in q for term in ("요약", "정리", "summary", "summarize")):
        return "summarize"
    return "page_qa" if current_url else "search"


def route_for_native_intent(intent: str) -> str:
    if intent in DEEP_AGENT_INTENTS:
        return "deep"
    if intent == "inbox":
        return "inbox"
    if intent == "manual_complete":
        return "manual_handoff"
    if intent == "approval":
        return "approval_required"
    if intent in {"event_publish", "action_invoke", "workflow_start"}:
        return "approval_required"
    if intent == "event_type_draft":
        return "approval_required"
    return "fast"


def native_rule_route(request: JsonDict, reason: str = "native_rules") -> JsonDict:
    deterministic = deterministic_native_intent(str(request.get("question") or ""), str(request.get("current_url") or ""))
    requested_intent = normalize_native_intent(str(request.get("intent") or ""), fallback=deterministic) if request.get("intent") else deterministic
    requested_mode = str(request.get("mode") or "auto")
    route = route_for_native_intent(requested_intent)
    if requested_mode == "fast" and route not in {"manual_handoff", "approval_required"}:
        route = "fast"
    elif requested_mode == "deep":
        route = "deep"
    return finalize_native_route(request, {"route": route, "intent": requested_intent, "reason": reason, "router_backend": "native_rules"})


def finalize_native_route(request: JsonDict, candidate: JsonDict | None) -> JsonDict:
    question = str(request.get("question") or "")
    current_url = str(request.get("current_url") or "")
    deterministic = deterministic_native_intent(question, current_url)
    route = normalize_native_route(str((candidate or {}).get("route") or ""), fallback=route_for_native_intent(deterministic))
    intent = normalize_native_intent(str((candidate or {}).get("intent") or ""), fallback=deterministic)
    if deterministic in DEEP_AGENT_INTENTS and route != "deep":
        route = "deep"
        intent = deterministic
    if intent in {"event_publish", "action_invoke", "workflow_start", "event_type_draft"}:
        route = "approval_required"
    elif override := safety_route_override(question):
        route = override
        intent = "manual_complete" if override == "manual_handoff" else "approval"
    elif intent in MUTATION_AGENT_INTENTS:
        route = route_for_native_intent(intent)
    elif (candidate or {}).get("requires_mutation") and route not in {"manual_handoff", "approval_required"}:
        route = "approval_required"
        intent = "approval"
    confidence = (candidate or {}).get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else (1.0 if (candidate or {}).get("router_backend") == "request_hint" else 0.82)
    except (TypeError, ValueError):
        confidence_value = 0.82
    return {
        "route": route,
        "intent": intent,
        "confidence": confidence_value,
        "reason": str((candidate or {}).get("reason") or "native classification"),
        "requires_mutation": route in {"manual_handoff", "approval_required"},
        "requires_deep_reasoning": route == "deep",
        # Compatibility field for older clients. Deep is native reasoning now, not Langflow.
        "requires_langflow": False,
        "router_backend": str((candidate or {}).get("router_backend") or "native_rules"),
    }


@dataclass
class NativeAgentConfig:
    max_tool_loops: int = 5
    tool_timeout_seconds: float = 8.0
    build_revision: str = "unknown"
    llm_enabled: bool = False
    progress_callback: Callable[[JsonDict], None] | None = None


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
        request = state.get("request") or {}
        route = state.get("route") or {}
        if not route.get("route"):
            route = self._classify_route_inside_graph(request, state)
        else:
            route = finalize_native_route(request, route)
        state["route"] = route
        state["intent"] = str(route.get("intent") or "search")
        state["route_name"] = str(route.get("route") or "fast")
        state["question"] = str(request.get("question") or "")
        return state

    def _classify_route_inside_graph(self, request: JsonDict, state: JsonDict) -> JsonDict:
        if self.config.llm_enabled and self.tools.llm_json and str(request.get("mode") or "auto") == "auto":
            payload = {
                "request": request,
                "deterministic_intent": deterministic_native_intent(str(request.get("question") or ""), str(request.get("current_url") or "")),
                "allowed_routes": sorted(ALLOWED_AGENT_ROUTES),
                "allowed_intents": sorted(ALLOWED_AGENT_INTENTS),
            }
            routed = self._call_tool(
                "route_classifier",
                {"backend": "llm_first"},
                lambda: self.tools.llm_json("route", payload) if self.tools.llm_json else None,
                state,
            )
            if isinstance(routed, dict) and routed.get("route"):
                return finalize_native_route(request, routed)
        return native_rule_route(request)

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
        if intent in {"diagram", "workflow_explain", "gap_check"}:
            target_boi_id = str(page_context.get("boi_id") or "")
            if not target_boi_id:
                target_boi_id = best_boi_ref_from_search(state.get("search") or {}, prefer_sop=True)
            if target_boi_id:
                planned.append({"tool": "boi_get", "args": {"boi_id": target_boi_id}})
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
        if rows:
            lines.append(markdown_table(rows, ["stage", "events", "actions", "manual_actions", "next_stage"]))
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
            confirmation = confirmation_payload_for_state(state)
            state["answer_markdown"] = (
                confirmation["answer_markdown"]
            )
            state["artifacts"] = [
                {
                    "type": "confirmation_required",
                    "title": confirmation["title"],
                    "data": confirmation["data"],
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
        self._emit_progress({"stage": "tool_start", "tool": name, "args": compact_tool_args(args), "message": tool_progress_message(name, "start")})
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
        self._emit_progress(
            {
                "stage": "tool_done",
                "tool": name,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "summary": summary,
                "message": tool_progress_message(name, status, summary=summary),
            }
        )
        return result

    def _emit_progress(self, payload: JsonDict) -> None:
        callback = self.config.progress_callback
        if not callback:
            return
        try:
            callback(payload)
        except Exception:
            return


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


def compact_tool_args(args: JsonDict) -> JsonDict:
    compact: JsonDict = {}
    for key, value in (args or {}).items():
        if key in {"query", "boi_id", "trace_id", "workflow_key", "action_key", "event_type", "scope", "limit"}:
            compact[key] = compact_text(str(value), 120) if isinstance(value, str) else value
    return compact


def tool_progress_message(tool: str, status: str, *, summary: str = "") -> str:
    labels = {
        "ontology_search": "관련 BoI 지식",
        "boi_get": "BoI 문서",
        "action_spec_lookup": "Action 명세",
        "trace_context_lookup": "Trace 근거",
        "workflow_status": "Workflow 상태",
        "dictionary_resolve": "업무 용어",
        "memory_recall": "Private memory",
        "agent_inbox": "내 Action",
        "route_classifier": "질문 유형",
    }
    label = labels.get(tool, "필요한 근거")
    if status == "start":
        return f"{label}을 확인하고 있습니다."
    if status == "ok":
        detail = f" ({summary})" if summary else ""
        return f"{label} 확인을 마쳤습니다{detail}."
    if status == "empty":
        return f"{label}에서 바로 쓸 수 있는 결과를 찾지 못했습니다."
    if status == "failed":
        return f"{label} 확인 중 오류가 발생했습니다."
    return f"{label} 상태를 확인했습니다."


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


def best_boi_ref_from_search(search: JsonDict, *, prefer_sop: bool = False) -> str:
    matches = [
        item
        for item in (search.get("best_matches") or [])
        if isinstance(item, dict) and str(item.get("kind") or "") == "boi" and (item.get("boi_id") or item.get("uri"))
    ]
    if prefer_sop:
        for item in matches:
            if str(item.get("type") or "") == "boi/sop":
                return str(item.get("boi_id") or item.get("uri") or "")
    return str((matches[0] or {}).get("boi_id") or (matches[0] or {}).get("uri") or "") if matches else ""


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
        "events": "Event",
        "actions": "Action",
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
        access = item.get("access") if isinstance(item.get("access"), dict) else {}
        if access.get("can_cite") is False:
            continue
        url = str(item.get("url") or "")
        if url:
            links.append({"label": item_label(item), "url": url, "kind": str(item.get("kind") or "search")})
    return links


def links_from_doc_and_search(doc: JsonDict, search: JsonDict) -> list[JsonDict]:
    links = []
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    access = doc.get("access") if isinstance(doc.get("access"), dict) else {}
    if metadata and metadata.get("boi_id") and access.get("can_cite") is not False:
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
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    title = str(page_context.get("title") or doc_title((state.get("tool_results") or {}).get("current_doc") or {}, "현재 문서"))
    stage_count = int(page_context.get("stage_count") or 0)
    action_count = int(page_context.get("workflow_action_count") or 0)
    manual_count = int(page_context.get("workflow_manual_action_count") or 0)
    if intent == "diagram":
        return [
            f"{title}의 Action {action_count}개와 Manual Handoff {manual_count}개 중 부족한 명세를 점검해줘.",
            "이 Event가 발생하면 뭘 해야 해?",
        ]
    if intent == "gap_check":
        return ["누락된 Action Spec 초안을 만들어줘.", f"{title}를 Mermaid로 다시 보여줘."]
    if intent == "inbox":
        return ["가장 먼저 처리할 일을 알려줘.", "승인 대기 건만 보여줘."]
    if stage_count:
        return [
            f"{title}를 Mermaid 프로세스 플로우로 보여줘.",
            f"{title}의 Event, Action, Manual Handoff 관계를 요약해줘.",
            "부족한 Action Spec이 있는지 찾아줘.",
        ]
    return ["이 내용을 Mermaid로 보여줘.", "관련 Action과 Event를 요약해줘.", "부족한 명세가 있는지 찾아줘."]


def confirmation_payload_for_state(state: JsonDict) -> JsonDict:
    intent = str(state.get("intent") or "")
    route_name = str(state.get("route_name") or "")
    question = str(state.get("question") or "")
    if intent == "event_type_draft":
        payload = event_type_draft_payload_from_state(state)
        if payload:
            return {
                "title": "신규 Event Type 초안 확인",
                "answer_markdown": "신규 Event Type은 바로 catalog에 반영하지 않고 draft로 만든 뒤 검증합니다. 아래 카드에서 내용을 확인하고 명시적으로 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "event_type_draft",
                    "payload": payload,
                    "title": "신규 Event Type 초안 확인",
                    "message": "Event Type draft를 만들고 validation 결과를 확인합니다. catalog 적용은 별도 검토와 승인 후 진행됩니다.",
                    "primary_label": "Event Type 초안 만들기",
                },
            }
        return {
            "title": "신규 Event Type 초안 확인",
            "answer_markdown": "Event Type 초안을 만들려면 `domain.event.requested.v1` 같은 versioned event_type 이름이 필요합니다.",
            "data": {
                "route": route_name,
                "intent": intent,
                "title": "Event Type 이름 필요",
                "message": "예: `quality.forecast.requested.v1` 신규 Event Type 초안 만들어줘.",
                "primary_label": "Event Type 이름을 포함해 다시 요청",
            },
        }
    if intent == "event_publish":
        payload = event_publish_payload_from_state(state)
        if payload:
            return {
                "title": "Event 발행 확인",
                "answer_markdown": "Event Broker에 새 Event를 발행하려면 먼저 내용을 확인해야 합니다. 아래 카드에서 Event Type과 payload를 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "event_publish",
                    "payload": payload,
                    "title": "Event 발행 확인",
                    "message": "Event 발행은 workflow를 진행시키고 BoI 생성/action dispatch로 이어질 수 있습니다.",
                    "primary_label": "Event 발행하기",
                },
            }
        return missing_execution_payload("Event Type 필요", "예: `equipment.alarm.raised.v1` 이벤트를 발행해줘.", route_name, intent)
    if intent == "workflow_start":
        payload = workflow_start_payload_from_state(state)
        if payload:
            workflow_key = str(payload.get("workflow_key") or "")
            return {
                "title": "Workflow 시작 확인",
                "answer_markdown": "SOP 기반 Workflow를 시작하려면 먼저 시작 Event payload를 확인해야 합니다. 아래 카드에서 workflow와 payload를 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "workflow_start",
                    "payload": payload,
                    "title": "Workflow 시작 확인",
                    "message": f"`{workflow_key}` workflow의 entry event를 발행합니다.",
                    "primary_label": "Workflow 시작하기",
                },
            }
        return missing_execution_payload("Workflow Key 필요", "예: `equipment-anomaly` workflow를 시작해줘.", route_name, intent)
    if intent == "action_invoke":
        payload = action_invoke_payload_from_state(state)
        if payload:
            action_key = str(payload.get("action_key") or "")
            return {
                "title": "Action 요청 실행 확인",
                "answer_markdown": "Action Gateway 요청은 allow-list와 권한 검증을 거쳐 실행됩니다. 아래 카드에서 action과 payload를 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "action_invoke",
                    "payload": payload,
                    "title": "Action 요청 실행 확인",
                    "message": f"`{action_key}` action을 Action Gateway로 요청합니다.",
                    "primary_label": "Action 요청 실행",
                },
            }
        return missing_execution_payload("Action Key 필요", "예: `sop.equipment.request_raw_data` action을 실행해줘.", route_name, intent)
    return {
        "title": "확인 필요",
        "answer_markdown": "이 요청은 상태 변경 또는 승인 절차가 필요합니다. Agent가 바로 실행하지 않고 확인 카드와 승인 API를 통해 처리해야 합니다.",
        "data": {
            "route": route_name,
            "intent": intent,
            "message": "명시 승인 후에만 실행할 수 있습니다.",
        },
    }


def missing_execution_payload(title: str, message: str, route_name: str, intent: str) -> JsonDict:
    return {
        "title": title,
        "answer_markdown": "실행 요청을 만들려면 필수 식별자가 필요합니다. Agent가 임의로 추정해 실행하지 않습니다.",
        "data": {
            "route": route_name,
            "intent": intent,
            "title": title,
            "message": message,
            "primary_label": "필수 정보를 추가해 다시 요청",
        },
    }


def event_type_from_text(value: str) -> str:
    match = re.search(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\.v\d+)\b", str(value or ""))
    return match.group(1) if match else ""


def action_key_from_text(value: str) -> str:
    candidates = re.findall(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,})\b", str(value or ""))
    for candidate in candidates:
        if not re.search(r"\.v\d+$", candidate):
            return candidate
    return ""


def execution_source_refs(state: JsonDict) -> list[JsonDict]:
    current_url = str(state.get("current_url") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    refs: list[JsonDict] = []
    if page_context.get("boi_id"):
        refs.append({"type": "boi", "ref": str(page_context.get("boi_id"))})
    if page_context.get("sop_ref"):
        refs.append({"type": "sop", "ref": str(page_context.get("sop_ref"))})
    if current_url:
        refs.append({"type": "boi-agent-page", "ref": current_url})
    return refs


def event_publish_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    event_type = event_type_from_text(question) or str(page_context.get("event_type") or "")
    if not event_type:
        return {}
    return {
        "event_type": event_type,
        "payload": {
            "title": compact_text(question, 100) or event_type,
            "summary": compact_text(question, 400),
        },
        "source_refs": execution_source_refs(state),
        "trace_id": str(page_context.get("trace_id") or "") or None,
    }


def workflow_start_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    workflow_key = str(page_context.get("workflow_key") or "")
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    metadata = current_doc.get("metadata") if isinstance(current_doc.get("metadata"), dict) else {}
    workflow = metadata.get("workflow") if isinstance(metadata.get("workflow"), dict) else {}
    workflow_key = workflow_key or str(workflow.get("workflow_key") or "")
    if not workflow_key:
        match = re.search(r"`?([a-z][a-z0-9_-]*(?:-[a-z0-9_]+)+)`?\s*(?:workflow|워크플로우)", question, flags=re.IGNORECASE)
        workflow_key = match.group(1) if match else ""
    if not workflow_key:
        return {}
    return {
        "workflow_key": workflow_key,
        "payload": {
            "title": compact_text(question, 100) or workflow_key,
            "summary": compact_text(question, 400),
            "workflow": workflow_key,
        },
        "source_refs": execution_source_refs(state),
    }


def action_invoke_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    search = state.get("search") if isinstance(state.get("search"), dict) else {}
    action_key = action_key_from_text(question) or str(page_context.get("action_key") or "")
    if not action_key:
        groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
        for item in groups.get("actions") or []:
            if isinstance(item, dict) and item.get("action_key"):
                action_key = str(item["action_key"])
                break
    if not action_key:
        return {}
    event_type = event_type_from_text(question) or str(page_context.get("event_type") or "")
    return {
        "action_key": action_key,
        "event": {
            "event_type": event_type,
            "trace_id": str(page_context.get("trace_id") or ""),
            "payload": {"title": compact_text(question, 100), "summary": compact_text(question, 400)},
            "source_refs": execution_source_refs(state),
        },
        "payload": {"title": compact_text(question, 100), "summary": compact_text(question, 400)},
    }


def event_type_draft_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    event_type = event_type_from_text(question)
    if not event_type:
        return {}
    search = state.get("search") if isinstance(state.get("search"), dict) else {}
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    sop_ref = event_type_draft_sop_ref(page_context, tool_results, search)
    related_event = event_type_draft_related_event(search)
    workflow_stage = event_type_draft_workflow_stage(question, related_event)
    action_keys = event_type_draft_recommended_actions(search)
    return {
        "event_type": event_type,
        "name_ko": event_type_draft_name(question, event_type),
        "description": compact_text(question, 260),
        "owner": "",
        "topic": event_type_draft_topic(event_type, related_event),
        "workflow_stage": workflow_stage,
        "sop_ref": sop_ref,
        "payload_schema": event_type_draft_payload_schema(question),
        "recommended_actions": action_keys,
    }


def event_type_draft_name(question: str, event_type: str) -> str:
    before = question.split(event_type, 1)[0]
    before = re.sub(r"(신규|새로운|event type|이벤트 타입|이벤트|초안|만들어줘|만들|생성|정의|추가)", " ", before, flags=re.IGNORECASE)
    before = re.sub(r"\s+", " ", before).strip(" .,:;/-")
    korean_chunks = re.findall(r"[가-힣A-Za-z0-9·\-/ ]+", before)
    name = " ".join(chunk.strip() for chunk in korean_chunks if chunk.strip()).strip()
    if name:
        return compact_text(name, 60)
    parts = event_type.rsplit(".v", 1)[0].split(".")
    return " ".join(part.replace("_", " ").title() for part in parts[-2:])


def event_type_draft_topic(event_type: str, related_event: JsonDict | None = None) -> str:
    if isinstance(related_event, dict) and related_event.get("topic"):
        return str(related_event.get("topic"))
    parts = event_type.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


def event_type_draft_payload_schema(question: str) -> JsonDict:
    properties: JsonDict = {
        "title": {"type": "string", "description": "업무 화면에 표시할 이벤트 제목"},
        "summary": {"type": "string", "description": "이벤트 발생 맥락 요약"},
    }
    if re.search(r"사번|담당|owner|작업자", question, re.IGNORECASE):
        properties["owner_employee_id"] = {"type": "string", "pattern": "^\\d{7}$", "description": "담당자 7자리 사번"}
    if re.search(r"설비|장비|equipment", question, re.IGNORECASE):
        properties["equipment_id"] = {"type": "string", "description": "대상 설비 또는 장비 ID"}
    return {"type": "object", "properties": properties, "required": ["title"]}


def event_type_draft_sop_ref(page_context: JsonDict, tool_results: JsonDict, search: JsonDict) -> str:
    for value in (page_context.get("sop_ref"),):
        if value:
            return str(value)
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    metadata = current_doc.get("metadata") if isinstance(current_doc.get("metadata"), dict) else {}
    if metadata.get("type") == "boi/sop" and metadata.get("boi_id"):
        return str(metadata.get("boi_id"))
    if page_context.get("page_kind") == "doc" and page_context.get("boi_id") and "sop" in str(page_context.get("boi_id")):
        return str(page_context.get("boi_id"))
    knowledge = search.get("knowledge_panel") if isinstance(search.get("knowledge_panel"), dict) else {}
    for item in knowledge.get("top_sop") or []:
        if isinstance(item, dict) and item.get("boi_id"):
            return str(item.get("boi_id"))
    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    for item in groups.get("sop") or []:
        if isinstance(item, dict) and item.get("boi_id"):
            return str(item.get("boi_id"))
    for item in search.get("best_matches") or []:
        if isinstance(item, dict) and item.get("type") == "boi/sop" and item.get("boi_id"):
            return str(item.get("boi_id"))
    return ""


def event_type_draft_related_event(search: JsonDict) -> JsonDict | None:
    knowledge = search.get("knowledge_panel") if isinstance(search.get("knowledge_panel"), dict) else {}
    for item in knowledge.get("top_event_type") or []:
        if isinstance(item, dict):
            return item
    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    for item in groups.get("event_types") or []:
        if isinstance(item, dict):
            return item
    return None


def event_type_draft_workflow_stage(question: str, related_event: JsonDict | None = None) -> str:
    stage_terms = ("이상 감지", "원인 분석", "보전 가이드", "이상 조치", "Map View 확인", "단면검사", "결과 확인")
    for term in stage_terms:
        if term in question:
            return term
    if isinstance(related_event, dict) and related_event.get("workflow_stage"):
        return str(related_event.get("workflow_stage"))
    if re.search(r"완료|completed|조치", question, re.IGNORECASE):
        return "이상 조치"
    if re.search(r"요청|requested|분석", question, re.IGNORECASE):
        return "원인 분석"
    return ""


def event_type_draft_recommended_actions(search: JsonDict) -> list[str]:
    action_keys: list[str] = []
    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    candidates = list(groups.get("actions") or []) + list(search.get("best_matches") or [])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        action_key = str(item.get("action_key") or "")
        if action_key and action_key not in action_keys:
            action_keys.append(action_key)
        if len(action_keys) >= 3:
            break
    return action_keys
