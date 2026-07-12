from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .capabilities import CapabilityRegistry
from .models import WorkOperation


class QuickAgentState(TypedDict, total=False):
    question: str
    page_kind: str
    page_ref: str
    page_title: str
    explicit_capability: str
    offered_capability: str
    active_capability: str
    active_artifact_title: str
    active_work_run: dict[str, Any]
    task_ref: str
    conversation_summary: str
    conversation_context: dict[str, Any]
    knowledge_hints: list[dict[str, Any]]
    trusted_targets: dict[str, str]
    requested_operation: str
    model: Any
    capability_id: str
    work_intent: dict[str, Any]
    continuation: dict[str, Any]
    route_source: str
    route_reason: str
    planner_error: str
    trace: list[str]


class QuickAgentRuntime:
    """LLM-planned LangGraph router with a read-only failure boundary.

    Natural-language routing is generated from the capability registry and the
    active BoI work context. Explicit capability and operation fields remain a
    deterministic API contract for external automation. If structured planning
    is unavailable or invalid, the router returns read-only knowledge search;
    it never guesses a draft or mutation from keyword rules.
    """

    engine = "langgraph"
    _operations = tuple(item.value for item in WorkOperation)
    _asset_kinds = (
        "knowledge",
        "sop",
        "workflow",
        "task",
        "business_event",
        "action",
        "skill",
        "runtime",
        "evidence",
    )
    _result_purposes = ("explain", "compare", "design", "transform", "execute")
    _artifact_actions = ("split_tasks", "create_sop_draft")

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
        graph = StateGraph(QuickAgentState)
        graph.add_node("normalize", self._normalize)
        graph.add_node("plan", self._plan)
        graph.add_node("validate", self._validate)
        graph.add_edge(START, "normalize")
        graph.add_edge("normalize", "plan")
        graph.add_edge("plan", "validate")
        graph.add_edge("validate", END)
        self._graph = graph.compile()

    @staticmethod
    def _normalize(state: QuickAgentState) -> dict[str, Any]:
        question = re.sub(r"\s+", " ", str(state.get("question") or "")).strip()
        return {"question": question, "trace": ["normalize"]}

    @classmethod
    def _operation_plan(cls, operation: str, proposed: list[Any] | None = None) -> list[str]:
        values = [str(item) for item in proposed or [] if str(item) in cls._operations]
        if operation not in cls._operations:
            operation = "understand"
        if operation not in values:
            values.append(operation)
        if values != ["understand"] and "understand" not in values:
            values.insert(0, "understand")
        if operation in {"create", "refine"} and "validate" not in values:
            values.append("validate")
        if operation == "run":
            if "validate" not in values:
                run_index = values.index("run")
                values.insert(run_index, "validate")
            if "observe" not in values:
                values.append("observe")
        if operation == "complete":
            if "validate" not in values:
                complete_index = values.index("complete")
                values.insert(complete_index, "validate")
            if "capture" not in values:
                values.append("capture")
        if operation == "connect":
            values = [value for value in values if value in {"understand", "connect"}]
            if "understand" not in values:
                values.insert(0, "understand")
            if "connect" not in values:
                values.append("connect")
        values = list(dict.fromkeys(values))
        order = {
            value: index
            for index, value in enumerate(
                (
                    "understand",
                    "compare",
                    "create",
                    "refine",
                    "connect",
                    "validate",
                    "test",
                    "run",
                    "observe",
                    "complete",
                    "capture",
                    "promote",
                )
            )
        }
        return sorted(values, key=lambda value: order[value])

    def _capability_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "capability_id": item.capability_id,
                "title": item.title,
                "description": item.description,
                "primary_asset": item.primary_asset.value,
                "supported_assets": [asset.value for asset in item.supported_assets],
                "operation_class": item.operation.value,
                "risk": item.risk.value,
                "deep": item.deep,
            }
            for item in self.registry.all()
        ]

    def _planner_schema(self) -> dict[str, Any]:
        capability_ids = [item.capability_id for item in self.registry.all()]
        return {
            "type": "object",
            "required": [
                "capability_id",
                "asset_kind",
                "operation",
                "operation_plan",
                "scope",
                "desired_outcome",
                "resolved_goal",
                "retrieval_query",
                "presentation_mode",
                "context_refs",
                "result_purpose",
                "requested_asset_kinds",
                "artifact_actions",
                "needs_clarification",
                "confidence",
                "reason",
                "continue_active_run",
                "continuation_kind",
                "user_confirmation",
            ],
            "properties": {
                "capability_id": {"type": "string", "enum": capability_ids},
                "asset_kind": {"type": "string", "enum": list(self._asset_kinds)},
                "operation": {"type": "string", "enum": list(self._operations)},
                "operation_plan": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "enum": list(self._operations)},
                },
                "scope": {"type": "string", "enum": ["auto", "current", "wiki", "selected"]},
                "desired_outcome": {"type": "string"},
                "resolved_goal": {
                    "type": "string",
                    "description": "A standalone workplace request that resolves pronouns and short follow-ups from trusted conversation context.",
                },
                "retrieval_query": {
                    "type": "string",
                    "description": "The semantic subject to retrieve, excluding output format instructions, transformation commands, and negative constraints.",
                },
                "presentation_mode": {
                    "type": "string",
                    "enum": ["prose", "mermaid", "table", "artifact"],
                },
                "context_refs": {
                    "type": "array",
                    "maxItems": 20,
                    "items": {"type": "string"},
                    "description": "Only trusted source or artifact refs supplied in the planning prompt.",
                },
                "result_purpose": {"type": "string", "enum": list(self._result_purposes)},
                "requested_asset_kinds": {
                    "type": "array",
                    "maxItems": len(self._asset_kinds),
                    "items": {"type": "string", "enum": list(self._asset_kinds)},
                },
                "artifact_actions": {
                    "type": "array",
                    "maxItems": len(self._artifact_actions),
                    "items": {"type": "string", "enum": list(self._artifact_actions)},
                },
                "target_ref": {"type": "string"},
                "needs_clarification": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reason": {"type": "string"},
                "continue_active_run": {
                    "type": "boolean",
                    "description": "True only when this message advances the active non-terminal WorkRun rather than starting another goal.",
                },
                "continuation_kind": {
                    "type": "string",
                    "enum": ["none", "human_input", "new_evidence", "blocker", "state_transition"],
                    "description": "Use human_input when a person reports review or completion; use new_evidence only when evidence is supplied without confirming completion.",
                },
                "user_confirmation": {
                    "type": "boolean",
                    "description": "True only when the user explicitly reports that a person reviewed the pending completion items and recorded the result.",
                },
            },
        }

    def _explicit_plan(self, state: QuickAgentState, capability_id: str, source: str) -> dict[str, Any]:
        definition = self.registry.get(capability_id)
        requested = str(state.get("requested_operation") or "").strip()
        operation = requested if requested in self._operations else (
            "create" if definition.operation.value == "draft" else "understand"
        )
        asset_kind = definition.primary_asset.value
        return {
            "capability_id": capability_id,
            "work_intent": {
                "goal": str(state.get("question") or ""),
                "resolved_goal": str(state.get("question") or ""),
                "retrieval_query": str(state.get("question") or ""),
                "asset_kind": asset_kind,
                "operation": operation,
                "operation_plan": self._operation_plan(operation),
                "target_ref": str(state.get("task_ref") or state.get("page_ref") or ""),
                "scope": "auto",
                "desired_outcome": "draft" if operation == "create" else "run_result" if operation == "run" else "answer",
                "presentation_mode": "prose",
                "context_refs": [],
                "result_purpose": "design" if operation in {"create", "refine"} else "execute" if operation == "run" else "explain",
                "requested_asset_kinds": [asset_kind],
                "artifact_actions": [],
                "risk": "high" if operation in {"run", "complete", "promote"} else "low",
                "needs_clarification": False,
                "confidence": 1.0,
            },
            "route_source": source,
            "route_reason": "deterministic_external_contract",
            "continuation": {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
            },
            "trace": [*(state.get("trace") or []), f"plan:{source}"],
        }

    def _safe_search(self, state: QuickAgentState, reason: str, error: str = "") -> dict[str, Any]:
        return {
            "capability_id": "knowledge.search",
            "work_intent": {
                "goal": str(state.get("question") or ""),
                "resolved_goal": str(state.get("question") or ""),
                "retrieval_query": str(state.get("question") or ""),
                "asset_kind": "knowledge",
                "operation": "understand",
                "operation_plan": ["understand"],
                "target_ref": str(state.get("task_ref") or state.get("page_ref") or ""),
                "scope": "auto",
                "desired_outcome": "answer",
                "presentation_mode": "prose",
                "context_refs": [],
                "result_purpose": "explain",
                "requested_asset_kinds": ["knowledge"],
                "artifact_actions": [],
                "risk": "low",
                "needs_clarification": True,
                "confidence": 0.0,
            },
            "route_source": "safe_fallback",
            "route_reason": reason,
            "continuation": {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
            },
            "planner_error": error[:500],
            "trace": [*(state.get("trace") or []), "plan:safe_search"],
        }

    def _plan(self, state: QuickAgentState) -> dict[str, Any]:
        offered = str(state.get("offered_capability") or "").strip()
        explicit = str(state.get("explicit_capability") or "").strip()
        if offered:
            return self._explicit_plan(state, offered, "offer_id")
        if explicit:
            return self._explicit_plan(state, explicit, "explicit")

        model = state.get("model")
        readiness = model.readiness() if model is not None and hasattr(model, "readiness") else {}
        if not readiness.get("generation"):
            return self._safe_search(state, "intent_model_unavailable")
        conversation_context = dict(state.get("conversation_context") or {})
        trusted_context_refs = list(
            dict.fromkeys(
                [
                    *[
                        str(item)
                        for item in conversation_context.get("recent_source_refs") or []
                        if str(item).strip()
                    ],
                    *[
                        str(item.get("ref") or "")
                        for item in (state.get("knowledge_hints") or [])
                        if str(item.get("ref") or "").strip()
                    ],
                    *(
                        [str(conversation_context.get("active_artifact", {}).get("artifact_id") or "")]
                        if isinstance(conversation_context.get("active_artifact"), dict)
                        and conversation_context.get("active_artifact", {}).get("artifact_id")
                        else []
                    ),
                ]
            )
        )[:24]
        system = (
            "You are the BoI Wiki work-intent planner. Understand the user's workplace goal semantically; "
            "do not classify by isolated keywords. Decide which registered capability should handle the turn and "
            "produce a typed WorkIntent. The current page and active artifact are important anchors, never hard search "
            "boundaries. Use the accessible Wiki as a whole when related knowledge is needed. A request may combine "
            "understand, compare, create, refine, connect, validate, test, run, observe, complete, capture, and promote. "
            "Only choose run, complete, or promote when the user actually asks for that operation. Questions about how "
            "to create something are understand, not create. Existing drafts should be refined, validated, or tested in "
            "place when the user refers to them. Prefer a quick capability for ordinary answers, current-page explanation, "
            "relationship explanation, and focused past-case comparison. Choose a deep capability only when the requested "
            "deliverable genuinely needs a durable multi-source research draft, delegated investigation, or long-running work; "
            "the presence of several related Wiki sources alone does not make work deep. Use the dedicated similar-case "
            "capability for focused historical comparison. Operation describes the user's requested business action, not the "
            "safety mechanism around it: invoking a registered Action is run even when dry-run is requested, while test only "
            "checks an artifact, definition, sample, or configuration without invoking that Action. If one missing target "
            "prevents correct work, set needs_clarification. When an active WorkRun is waiting, decide semantically whether "
            "the new message continues that same work. Set continue_active_run only when the message actually supplies new "
            "evidence, reports a blocker, reports a state change, or clearly answers the pending completion request. Set "
            "user_confirmation only when the user explicitly says that a person reviewed the required evidence or completion "
            "items; a vague acknowledgement or request to keep going is not confirmation. Never infer a system confirmation "
            "from natural language. If the message starts a different goal, do not continue the active run. "
            "Use task.work for observing, performing, completing, or capturing the result of a specific Task. Use work.inbox "
            "only to list the user's currently assigned work; never use it to perform or complete a Task. A question that "
            "finds or explains knowledge about Tasks without a concrete task_ref or active WorkRun is knowledge.search, not "
            "task.work. For a Manual or "
            "Copilot WorkRun, a message that explicitly reports personal review of the listed completion items and records "
            "the result is human_input with user_confirmation=true, even when it also contains new evidence. "
            "Choose the primary operation from the requested deliverable, not from incidental supporting words. Use "
            "understand when the user wants the meaning, criteria, or summary of one focal document or item, even when the "
            "answer should use related Wiki knowledge. Use connect only when the relationships, dependencies, or flow among "
            "multiple assets are themselves the requested deliverable. For example, explaining one document's decision "
            "criteria with related knowledge is understand; explaining how an SOP, business event, Action, and result BoI "
            "link together is connect. Connect is read-only relationship understanding; changing an asset or adding a real "
            "connection must be create or refine. A trusted action_key identifies a registered Action target: invoking it, including a "
            "dry-run, belongs to action.plan with operation run, never task.work. "
            "Resolve short follow-ups into a standalone resolved_goal using only the supplied recent messages, active "
            "artifact, current page, and trusted source refs. Preserve the user's intended subject across turns for "
            "requests such as 'draw that flow', 'split it into Tasks', or 'use the evidence just shown'. Do not carry the "
            "previous subject when the user clearly starts another goal. If two prior subjects are equally plausible, set "
            "needs_clarification instead of guessing. Set presentation_mode=mermaid when the requested deliverable is an "
            "actual flow or Mermaid diagram, including a visual follow-up to the previous answer. Mermaid means a rendered "
            "diagram artifact, not a prose description of a flow. A request to explain or summarize a flow remains prose "
            "unless the user semantically asks to draw, visualize, diagram, chart, or render it. Use table only when a table "
            "itself is requested. Set result_purpose=explain for answers and read-only diagrams, compare for comparisons, "
            "design for a new draft, transform when converting an existing result into another asset, and execute for guarded "
            "execution. Choose requested_asset_kinds semantically from the actual requested result; never add SOP, Task, Event, "
            "or Action merely because they exist in the Wiki. artifact_actions must be empty for explain or compare. Include "
            "split_tasks only when the user explicitly asks to turn a grounded flow into Tasks, and create_sop_draft only when "
            "the user explicitly asks to turn it into an SOP draft. "
            "Return retrieval_query as the standalone semantic subject to search for. Keep the subject, named assets, and "
            "requested relationships, but exclude presentation instructions such as drawing or table formatting, exclude "
            "transformation commands, and exclude negative constraints about what not to create. resolved_goal still keeps "
            "the full requested outcome; retrieval_query is only for finding the right evidence. Put only "
            "Write resolved_goal and retrieval_query in the same language as the user's request, preserving the user's "
            "business terms and named assets rather than translating them into generic English. "
            "refs that appear in trusted_context_refs into context_refs; never invent a source or artifact ref. "
            "Return JSON matching the schema and never invent a capability ID."
        )
        prompt = json.dumps(
            {
                "request": state.get("question") or "",
                "current_page": {
                    "kind": state.get("page_kind") or "library",
                    "ref": state.get("page_ref") or "",
                    "title": state.get("page_title") or "",
                },
                "active_work": {
                    "capability_id": state.get("active_capability") or "",
                    "title": state.get("active_artifact_title") or "",
                    "task_ref": state.get("task_ref") or "",
                    "work_run": state.get("active_work_run") or {},
                },
                "conversation_summary": str(state.get("conversation_summary") or "")[:2000],
                "conversation_context": conversation_context,
                "trusted_context_refs": trusted_context_refs,
                "wiki_hybrid_hints": list(state.get("knowledge_hints") or [])[:8],
                "trusted_targets": dict(state.get("trusted_targets") or {}),
                "operation_contracts": {
                    "understand": "explain the meaning, criteria, or summary of one focal item; related sources may support the answer without changing this into connect",
                    "compare": "compare sources, alternatives, or cases when comparison itself is the requested outcome",
                    "create": "create a new private draft",
                    "refine": "improve an existing artifact in place through a proposal",
                    "connect": "make the relationships, dependencies, or flow among multiple named assets the primary result; use desired_outcome=answer for read-only explanation",
                    "validate": "evaluate an existing artifact against its Harness",
                    "test": "validate or preview an artifact, definition, sample, or configuration without invoking a registered Action",
                    "run": "invoke a registered Action, including dry-run invocation, through the applicable confirmation policy",
                    "observe": "inspect current runtime work or a running Task without completing it",
                    "complete": "evaluate and record Task completion",
                    "capture": "create an evidence-backed private knowledge candidate",
                    "promote": "request Team/Public promotion through confirmation",
                },
                "capabilities": self._capability_catalog(),
            },
            ensure_ascii=False,
        )
        try:
            planned = model.generate_structured(system=system, prompt=prompt, schema=self._planner_schema())
            capability_id = str(planned.get("capability_id") or "")
            definition = self.registry.get(capability_id)
            operation = str(planned.get("operation") or "understand")
            if operation not in self._operations:
                raise ValueError("planner returned an unsupported operation")
            asset_kind = str(planned.get("asset_kind") or "knowledge")
            if asset_kind not in self._asset_kinds:
                raise ValueError("planner returned an unsupported asset kind")
            supported_assets = {item.value for item in definition.supported_assets}
            if asset_kind not in supported_assets:
                asset_kind = definition.primary_asset.value
            resolved_goal = str(planned.get("resolved_goal") or state.get("question") or "").strip()
            if not resolved_goal:
                resolved_goal = str(state.get("question") or "")
            retrieval_query = str(planned.get("retrieval_query") or resolved_goal).strip()
            if not retrieval_query:
                retrieval_query = resolved_goal
            original_question = str(state.get("question") or "").strip()
            if re.search(r"[가-힣]", original_question) and not re.search(r"[가-힣]", resolved_goal):
                resolved_goal = f"{original_question}\n{resolved_goal}".strip()
            if re.search(r"[가-힣]", original_question) and not re.search(r"[가-힣]", retrieval_query):
                retrieval_query = f"{original_question}\n{retrieval_query}".strip()
            presentation_mode = str(planned.get("presentation_mode") or "prose")
            if presentation_mode not in {"prose", "mermaid", "table", "artifact"}:
                presentation_mode = "prose"
            result_purpose = str(planned.get("result_purpose") or "explain")
            if result_purpose not in self._result_purposes:
                result_purpose = "explain"
            requested_asset_kinds = list(
                dict.fromkeys(
                    str(item)
                    for item in planned.get("requested_asset_kinds") or []
                    if str(item) in self._asset_kinds
                )
            )[: len(self._asset_kinds)]
            if not requested_asset_kinds:
                requested_asset_kinds = [asset_kind]
            artifact_actions = list(
                dict.fromkeys(
                    str(item)
                    for item in planned.get("artifact_actions") or []
                    if str(item) in self._artifact_actions
                )
            )[: len(self._artifact_actions)]
            if result_purpose not in {"design", "transform"} or operation not in {"create", "refine"}:
                artifact_actions = []
            trusted_ref_set = set(trusted_context_refs)
            context_refs = list(
                dict.fromkeys(
                    str(item)
                    for item in planned.get("context_refs") or []
                    if str(item) in trusted_ref_set
                )
            )[:20]
            work_intent = {
                "goal": str(state.get("question") or ""),
                "resolved_goal": resolved_goal[:12000],
                "retrieval_query": retrieval_query[:12000],
                "asset_kind": asset_kind,
                "operation": operation,
                "operation_plan": self._operation_plan(operation, planned.get("operation_plan")),
                "target_ref": str(planned.get("target_ref") or state.get("task_ref") or state.get("page_ref") or ""),
                "scope": str(planned.get("scope") or "auto"),
                "desired_outcome": str(planned.get("desired_outcome") or "answer"),
                "presentation_mode": presentation_mode,
                "context_refs": context_refs,
                "result_purpose": result_purpose,
                "requested_asset_kinds": requested_asset_kinds,
                "artifact_actions": artifact_actions,
                "risk": "high" if operation in {"run", "complete", "promote"} else "medium" if operation == "test" else "low",
                "needs_clarification": bool(planned.get("needs_clarification", False)),
                "confidence": max(0.0, min(float(planned.get("confidence") or 0.0), 1.0)),
            }
            continuation_kind = str(planned.get("continuation_kind") or "none")
            if continuation_kind not in {"none", "human_input", "new_evidence", "blocker", "state_transition"}:
                continuation_kind = "none"
            continue_active_run = bool(planned.get("continue_active_run", False)) and bool(state.get("active_work_run"))
            if not continue_active_run:
                continuation_kind = "none"
            return {
                "capability_id": capability_id,
                "work_intent": work_intent,
                "continuation": {
                    "continue_active_run": continue_active_run,
                    "delta_kind": continuation_kind,
                    "user_confirmation": bool(planned.get("user_confirmation", False)) if continue_active_run else False,
                },
                "route_source": "llm_structured",
                "route_reason": str(planned.get("reason") or "semantic_work_intent"),
                "trace": [*(state.get("trace") or []), "plan:llm_structured"],
            }
        except Exception as exc:
            return self._safe_search(state, "intent_model_invalid", f"{type(exc).__name__}: {exc}")

    def _validate(self, state: QuickAgentState) -> dict[str, Any]:
        capability_id = str(state.get("capability_id") or "knowledge.search")
        self.registry.get(capability_id)
        intent = dict(state.get("work_intent") or {})
        if not intent.get("goal") or intent.get("operation") not in self._operations:
            raise ValueError("router produced an invalid WorkIntent")
        updates: dict[str, Any] = {"trace": [*(state.get("trace") or []), "validate"]}
        operation = str(intent.get("operation") or "")
        trusted_task_target = str(state.get("task_ref") or "").strip()
        trusted_targets = state.get("trusted_targets") or {}
        trusted_action_target = str(trusted_targets.get("action_key") or "").strip()
        if operation == "run" and trusted_action_target and capability_id != "action.plan":
            intent.update(
                {
                    "asset_kind": "action",
                    "target_ref": trusted_action_target,
                }
            )
            capability_id = "action.plan"
            updates.update(
                {
                    "capability_id": capability_id,
                    "work_intent": intent,
                    "route_reason": f"{state.get('route_reason') or 'semantic_work_intent'}:trusted_action_target",
                    "trace": [*(state.get("trace") or []), "validate:trusted_action_target"],
                }
            )
        if (
            capability_id == "task.work"
            and operation in {"understand", "compare", "connect", "observe"}
            and not trusted_task_target
            and not state.get("active_work_run")
        ):
            intent.update(
                {
                    "asset_kind": "task",
                    "operation": "understand",
                    "operation_plan": ["understand"],
                    "scope": "wiki" if intent.get("scope") == "wiki" else "auto",
                    "risk": "low",
                }
            )
            updates.update(
                {
                    "capability_id": "knowledge.search",
                    "work_intent": intent,
                    "route_reason": f"{state.get('route_reason') or 'semantic_work_intent'}:task_lookup_without_target",
                    "trace": [*(state.get("trace") or []), "validate:task_lookup_to_search"],
                }
            )
        return updates

    def route(
        self,
        question: str,
        *,
        page_kind: str,
        page_ref: str = "",
        page_title: str = "",
        explicit_capability: str = "",
        offered_capability: str = "",
        active_capability: str = "",
        active_artifact_title: str = "",
        active_work_run: dict[str, Any] | None = None,
        task_ref: str = "",
        conversation_summary: str = "",
        conversation_context: dict[str, Any] | None = None,
        knowledge_hints: list[dict[str, Any]] | None = None,
        trusted_targets: dict[str, str] | None = None,
        requested_operation: str = "",
        model: Any = None,
    ) -> dict[str, Any]:
        result = self._graph.invoke(
            {
                "question": question,
                "page_kind": page_kind,
                "page_ref": page_ref,
                "page_title": page_title,
                "explicit_capability": explicit_capability,
                "offered_capability": offered_capability,
                "active_capability": active_capability,
                "active_artifact_title": active_artifact_title,
                "active_work_run": dict(active_work_run or {}),
                "task_ref": task_ref,
                "conversation_summary": conversation_summary,
                "conversation_context": dict(conversation_context or {}),
                "knowledge_hints": list(knowledge_hints or [])[:8],
                "trusted_targets": dict(trusted_targets or {}),
                "requested_operation": requested_operation,
                "model": model,
            }
        )
        return {
            "engine": self.engine,
            "capability_id": result["capability_id"],
            "work_intent": result["work_intent"],
            "continuation": result.get("continuation") or {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
            },
            "source": result.get("route_source") or "",
            "reason": result.get("route_reason") or "",
            "planner_error": result.get("planner_error") or "",
            "trace": result.get("trace") or [],
        }
