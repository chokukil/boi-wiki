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
    grounded_answer: dict[str, Any] | None
    grounded_answer_diagnostics: dict[str, Any]
    sop_draft: dict[str, Any] | None
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
                "description": str(item.description)[:180],
                "primary_asset": item.primary_asset.value,
                "operation_class": item.operation.value,
                "deep": item.deep,
            }
            for item in self.registry.all()
        ]

    def _planner_schema(self, *, include_continuation: bool = False) -> dict[str, Any]:
        capability_ids = [item.capability_id for item in self.registry.all()]
        schema = {
            "type": "object",
            "required": [
                "capability_id",
                "asset_kind",
                "operation",
                "presentation_mode",
                "grounded_answer",
                "sop_draft",
            ],
            "properties": {
                "capability_id": {"type": "string", "enum": capability_ids},
                "asset_kind": {"type": "string", "enum": list(self._asset_kinds)},
                "operation": {
                    "type": "string",
                    "enum": list(self._operations),
                    "description": (
                        "Semantic work operation. Use connect for relationships, dependencies, paths, or flow between "
                        "multiple assets even when the user asks to explain them; understand is for one focal item."
                    ),
                },
                "operation_plan": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "enum": list(self._operations)},
                },
                "scope": {"type": "string", "enum": ["auto", "current", "wiki", "selected"]},
                "desired_outcome": {"type": "string", "maxLength": 240},
                "resolved_goal": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "A standalone workplace request that resolves pronouns and short follow-ups from trusted conversation context.",
                },
                "retrieval_query": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "The semantic subject to retrieve, excluding output format instructions, transformation commands, and negative constraints.",
                },
                "presentation_mode": {
                    "type": "string",
                    "enum": ["prose", "mermaid", "table", "timeline", "explorer", "artifact"],
                },
                "work_view": {
                    "type": "string",
                    "enum": ["none", "current", "responsibility", "combined"],
                },
                "current_scope_explicit": {
                    "type": "boolean",
                    "description": (
                        "True only when the user explicitly limits the requested result to active Inbox or current work."
                    ),
                },
                "graph_query_draft": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "query_kind": {"type": "string", "enum": [
                            "neighbors", "path", "workflow", "impact", "lineage",
                            "responsibility", "timeline", "compare", "tour"
                        ]},
                        "focal_mentions": {"type": "array", "maxItems": 20, "items": {"type": "string"}},
                        "target_mentions": {"type": "array", "maxItems": 20, "items": {"type": "string"}},
                        "node_kinds": {"type": "array", "maxItems": 30, "items": {"type": "string"}},
                        "relation_kinds": {"type": "array", "maxItems": 30, "items": {"type": "string"}},
                        "direction": {"type": "string", "enum": ["outgoing", "incoming", "both"]},
                        "depth": {"type": "integer", "minimum": 1, "maximum": 6},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                        "presentation": {"type": "string", "enum": ["auto", "list", "table", "timeline", "mermaid", "explorer"]},
                    },
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
                "reason": {"type": "string", "maxLength": 120},
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
                "grounded_answer": {
                    "type": "object",
                    "required": ["summary", "summary_source_refs", "outcomes", "related_questions"],
                    "description": (
                        "For an ordinary read-only prose or table knowledge.search or cases.similar question, the grounded answer produced in "
                        "this planning call. Every source_refs value must be a source_key from wiki_hybrid_hints. "
                        "The server resolves those short keys to verified source refs. Return an "
                        "empty fields for every other operation or when the hints are insufficient. The server "
                        "validates the complete prose shape before using it."
                    ),
                    "properties": {
                        "summary": {"type": "string", "maxLength": 420},
                        "summary_source_refs": {
                            "type": "array",
                            "maxItems": 4,
                            "items": {"type": "string"},
                            "description": "For a non-empty summary, one or more exact short source_key values such as S1.",
                        },
                        "outcomes": {
                            "type": "array",
                            "maxItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string", "maxLength": 90},
                                    "items": {
                                        "type": "array",
                                        "maxItems": 3,
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "text": {"type": "string", "maxLength": 300},
                                                "source_refs": {
                                                    "type": "array",
                                                    "maxItems": 4,
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "related_questions": {
                            "type": "array",
                            "maxItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string", "enum": ["understand", "connect", "apply"]},
                                    "label": {"type": "string", "maxLength": 120},
                                    "question": {"type": "string", "maxLength": 600},
                                    "source_refs": {
                                        "type": "array",
                                        "maxItems": 4,
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
                "sop_draft": {
                    "type": "object",
                    "required": ["title", "goal", "tasks", "gaps"],
                    "description": (
                        "For sop.plan create or refine, produce the private SOP outline in this same semantic call. "
                        "For every other capability return title='', goal='', tasks=[], gaps=[]."
                    ),
                    "properties": {
                        "title": {"type": "string", "maxLength": 100},
                        "goal": {"type": "string", "maxLength": 240},
                        "tasks": {
                            "type": "array",
                            "maxItems": 6,
                            "items": {
                                "type": "object",
                                "required": [
                                    "name", "purpose", "execution_mode", "exit_criteria", "required_evidence"
                                ],
                                "properties": {
                                    "name": {"type": "string", "maxLength": 90},
                                    "purpose": {"type": "string", "maxLength": 180},
                                    "execution_mode": {
                                        "type": "string",
                                        "enum": ["manual", "copilot", "autopilot"],
                                    },
                                    "exit_criteria": {
                                        "type": "array",
                                        "maxItems": 2,
                                        "items": {"type": "string", "maxLength": 160},
                                    },
                                    "required_evidence": {
                                        "type": "array",
                                        "maxItems": 2,
                                        "items": {"type": "string", "maxLength": 160},
                                    },
                                },
                            },
                        },
                        "gaps": {
                            "type": "array",
                            "maxItems": 4,
                            "items": {"type": "string", "maxLength": 160},
                        },
                    },
                },
            },
        }
        for derived_field in ("operation_plan", "desired_outcome", "reason"):
            if derived_field in schema["required"]:
                schema["required"].remove(derived_field)
            schema["properties"].pop(derived_field, None)
        if not include_continuation:
            for continuation_field in (
                "continue_active_run",
                "continuation_kind",
                "user_confirmation",
            ):
                if continuation_field in schema["required"]:
                    schema["required"].remove(continuation_field)
                schema["properties"].pop(continuation_field, None)
        return schema

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
                "work_view": "current" if capability_id == "work.inbox" else "none",
                "graph_query_draft": None,
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
                "work_view": "none",
                "graph_query_draft": None,
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
        knowledge_hints = [
            item
            for item in (state.get("knowledge_hints") or [])[:6]
            if isinstance(item, dict) and str(item.get("ref") or "").strip()
        ]
        planner_hints = [
            {**item, "source_key": f"S{index}"}
            for index, item in enumerate(knowledge_hints, start=1)
        ]
        system = (
            "You are the BoI Wiki work-intent planner. Interpret the complete workplace goal semantically, never by isolated "
            "keywords, and return the schema exactly. The current page and active artifact are anchors, not search boundaries; "
            "use the accessible Wiki as a whole. Choose only a registered capability.\n"
            "Operations: understand explains one focal item; compare contrasts items or cases; connect explains relationships, "
            "dependencies, paths, or flow between two or more assets and is read-only. When the requested result is how assets "
            "connect, choose connect even when the user also says explain. create makes a new private draft; refine changes an "
            "existing artifact through a proposal; "
            "validate checks an artifact; test checks or dry-runs without production mutation; run invokes a registered Action; "
            "observe inspects runtime work; complete evaluates a specific Task; capture makes an evidence-backed private candidate; "
            "promote requests reviewed sharing. Choose run, complete, or promote only when explicitly requested. A how-to question "
            "is understand. Existing artifacts should be refined, validated, or tested in place.\n"
            "Use quick capabilities for ordinary answers and focused relationships or cases. Use cases.similar for focused case "
            "comparison. Use deep.research only for a durable multi-source investigation or long-running draft. Use task.work only "
            "for a concrete task_ref or active WorkRun; work.inbox only lists current assignments; Task knowledge lookup is "
            "knowledge.search. A trusted action_key invoked even as dry-run is action.plan/run.\n"
            "For work_view, current means only active Inbox, responsibility means stable roles or who-does-what, and combined "
            "separates verified responsibility from current assignments. Broad questions about what a person does are combined. "
            "Set current_scope_explicit=true only when the user explicitly limits the result to current/active Inbox and does not "
            "ask for roles or responsibility. For responsibility or combined, enable a responsibility graph focused on the named "
            "person/team and include person, team, or role in requested_asset_kinds. combined must also include runtime or task. "
            "First-person means the authenticated person.\n"
            "Continue an active WorkRun only for new evidence, human input, blocker, or state transition that advances the same "
            "goal. A new goal does not continue it. user_confirmation is true only after explicit human review of required evidence "
            "or completion items; acknowledgement is not confirmation. Ask one clarification only when a missing or ambiguous "
            "target blocks correct work.\n"
            "Resolve short follow-ups into standalone resolved_goal using only recent messages, active artifact/page, and trusted "
            "refs. Preserve the prior subject for follow-ups, but drop it for a clearly new topic. retrieval_query keeps the named "
            "subject and relationship while removing display, transform, and negative-constraint instructions. Keep both fields in "
            "the user's language. context_refs may contain only trusted_context_refs.\n"
            "Choose presentation_mode by requested result: prose for explanation, table for comparison or compact structured data, "
            "timeline for temporal history, mermaid for an actual requested diagram, explorer for a larger relationship set, and "
            "artifact for an editable deliverable. Explorer requires an enabled graph query with a focal subject. A flow mentioned "
            "in prose is not automatically a diagram. result_purpose is explain, compare, design, transform, or execute. Never add "
            "SOP, Task, Event, or Action incidentally. artifact_actions is empty for explain/compare; split_tasks and "
            "create_sop_draft require an explicit conversion request. Never invent refs, targets, capability IDs, confirmation, or "
            "permissions. For an ordinary read-only prose or table question routed to knowledge.search or cases.similar, "
            "grounded_answer MUST be a non-empty answer produced in this same call from the supplied wiki_hybrid_hints. Include "
            "only claims supported by those hints and copy their short source_key values (for example S1) into every "
            "source_refs field. Keep the conclusion short, use one section with no more than three outcome "
            "items, and suggest no more than one related question. Omit "
            "the content for drafts, mutations, current/combined work views, diagrams, or insufficient hints by returning "
            "grounded_answer with summary='', summary_source_refs=[], outcomes=[], and related_questions=[]. Never return a "
            "non-empty summary without at least one exact source_key in summary_source_refs. For sop.plan create or refine, "
            "fill sop_draft from the resolved goal, conversation, and supplied Wiki hints in the same call. Keep it to 3-5 "
            "workplace Tasks with observable completion criteria and actual evidence labels. This is a private preview, not a "
            "published SOP. For every other route return the required empty sop_draft shape.\n"
            "Semantic examples: explaining the core of one guide is knowledge.search + understand; explaining how SOP, Event, "
            "Action, people, evidence, or outcomes connect is knowledge.search + connect; comparing a few known cases is "
            "cases.similar + compare; an explicit deep, durable investigation across multiple SOPs or sources is deep.research "
            "+ compare. These examples clarify meaning only; still resolve the actual request and available context."
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
                "wiki_hybrid_hints": planner_hints,
                "trusted_targets": dict(state.get("trusted_targets") or {}),
                "requested_result_kind": str(state.get("requested_result_kind") or ""),
                "requested_graph_query_kind": str(state.get("requested_graph_query_kind") or ""),
                "capabilities": self._capability_catalog(),
            },
            ensure_ascii=False,
        )
        try:
            planned = model.generate_structured(
                system=system,
                prompt=prompt,
                schema=self._planner_schema(include_continuation=bool(state.get("active_work_run"))),
            )
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
            if original_question and original_question not in resolved_goal:
                resolved_goal = f"{resolved_goal}\n사용자 요청: {original_question}".strip()
            if re.search(r"[가-힣]", original_question) and not re.search(r"[가-힣]", resolved_goal):
                resolved_goal = original_question
            if re.search(r"[가-힣]", original_question) and not re.search(r"[가-힣]", retrieval_query):
                retrieval_query = original_question
            presentation_mode = str(planned.get("presentation_mode") or "prose")
            if presentation_mode not in {"prose", "mermaid", "table", "timeline", "explorer", "artifact"}:
                presentation_mode = "prose"
            work_view = str(planned.get("work_view") or ("current" if capability_id == "work.inbox" else "none"))
            if work_view not in {"none", "current", "responsibility", "combined"}:
                work_view = "none"
            current_scope_explicit = bool(planned.get("current_scope_explicit", False))
            if work_view == "current" and not current_scope_explicit:
                work_view = "combined"
            planned_asset_kinds = {
                str(item).strip()
                for item in planned.get("requested_asset_kinds") or []
                if str(item).strip()
            }
            responsibility_asset_kinds = {"person", "team", "role"}
            current_work_asset_kinds = {"runtime", "task", "evidence"}
            planned_graph = planned.get("graph_query_draft")
            has_responsibility_graph = (
                isinstance(planned_graph, dict)
                and bool(planned_graph.get("enabled"))
                and str(planned_graph.get("query_kind") or "") == "responsibility"
            )
            if current_scope_explicit and planned_asset_kinds.intersection(responsibility_asset_kinds):
                # The planner cannot simultaneously limit the result to Inbox
                # work and request stable Person/Team/Role relationships.
                # Resolve that typed contract contradiction without inspecting
                # the user's wording a second time.
                work_view = "combined"
            if work_view == "current" and not planned_asset_kinds.intersection(current_work_asset_kinds):
                # A current Inbox view cannot satisfy a request whose typed
                # result contains no runtime, Task, or evidence asset.
                work_view = "none"
            if (
                work_view in {"responsibility", "combined"}
                and not planned_asset_kinds.intersection(responsibility_asset_kinds)
                and not has_responsibility_graph
            ):
                # Responsibility views require a typed person/organization
                # result or an explicit responsibility traversal.
                work_view = "none"
            if (
                asset_kind == "runtime"
                and str(planned.get("scope") or "") == "current"
                and operation in {"understand", "observe"}
                and planned_asset_kinds.intersection({"task", "evidence", "runtime"})
                and not planned_asset_kinds.intersection(responsibility_asset_kinds)
            ):
                # Validate the model's own typed intent. A current runtime view
                # that asks only for Tasks/evidence must not be broadened into
                # stable Person/Role responsibility relationships.
                work_view = "current"
            if work_view == "current":
                capability_id = "work.inbox"
                definition = self.registry.get(capability_id)
                asset_kind = "runtime"
                if operation not in {"understand", "observe"}:
                    operation = "observe"
            elif work_view in {"responsibility", "combined"}:
                capability_id = "knowledge.search"
                definition = self.registry.get(capability_id)
            raw_graph = planned.get("graph_query_draft") if isinstance(planned.get("graph_query_draft"), dict) else None
            if work_view == "current":
                raw_graph = None
            graph_query_draft = None
            if raw_graph and bool(raw_graph.get("enabled")):
                query_kind = str(raw_graph.get("query_kind") or "neighbors")
                if query_kind not in {"neighbors", "path", "workflow", "impact", "lineage", "responsibility", "timeline", "compare", "tour"}:
                    query_kind = "neighbors"
                graph_query_draft = {
                    "enabled": True,
                    "query_kind": query_kind,
                    "focal_mentions": [str(item)[:200] for item in raw_graph.get("focal_mentions") or [] if str(item).strip()][:20],
                    "target_mentions": [str(item)[:200] for item in raw_graph.get("target_mentions") or [] if str(item).strip()][:20],
                    "node_kinds": [str(item)[:80] for item in raw_graph.get("node_kinds") or [] if str(item).strip()][:30],
                    "relation_kinds": [str(item)[:80] for item in raw_graph.get("relation_kinds") or [] if str(item).strip()][:30],
                    "direction": str(raw_graph.get("direction") or "both") if str(raw_graph.get("direction") or "both") in {"outgoing", "incoming", "both"} else "both",
                    "depth": max(1, min(int(raw_graph.get("depth") or 2), 6)),
                    "time_from": str(raw_graph.get("time_from") or "")[:80],
                    "time_to": str(raw_graph.get("time_to") or "")[:80],
                    "presentation": str(raw_graph.get("presentation") or "auto") if str(raw_graph.get("presentation") or "auto") in {"auto", "list", "table", "timeline", "mermaid", "explorer"} else "auto",
                }
            if work_view in {"responsibility", "combined"} and graph_query_draft is None:
                graph_query_draft = {
                    "enabled": True,
                    "query_kind": "responsibility",
                    "focal_mentions": ["현재 사용자"],
                    "target_mentions": [],
                    "node_kinds": [],
                    "relation_kinds": [],
                    "direction": "both",
                    "depth": 2,
                    "time_from": "",
                    "time_to": "",
                    "presentation": "auto",
                }
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
            hint_refs = list(dict.fromkeys(
                str(item.get("ref") or "")
                for item in (state.get("knowledge_hints") or [])
                if isinstance(item, dict) and str(item.get("ref") or "").strip()
            ))
            hint_ref_set = set(hint_refs)
            hint_key_to_ref = {
                str(item.get("source_key") or ""): str(item.get("ref") or "")
                for item in planner_hints
                if str(item.get("source_key") or "") and str(item.get("ref") or "")
            }

            def resolve_hint_ref(value: Any) -> str:
                candidate = str(value or "").strip()
                if candidate in hint_ref_set:
                    return candidate
                return hint_key_to_ref.get(candidate, "")

            def resolved_hint_refs(values: Any) -> list[str]:
                return list(
                    dict.fromkeys(
                        resolved
                        for item in (values or [])
                        if (resolved := resolve_hint_ref(item))
                    )
                )[:4]

            grounded_answer = None
            summary_refs: list[str] = []
            raw_grounded_answer = planned.get("grounded_answer")
            if (
                capability_id in {"knowledge.search", "cases.similar"}
                and operation in {"understand", "compare", "connect"}
                and presentation_mode in {"prose", "table"}
                and work_view == "none"
                and isinstance(raw_grounded_answer, dict)
                and hint_ref_set
            ):
                summary = str(raw_grounded_answer.get("summary") or "").strip()[:420]
                summary_refs = resolved_hint_refs(raw_grounded_answer.get("summary_source_refs"))
                outcomes: list[dict[str, Any]] = []
                item_count = 0
                for raw_outcome in (raw_grounded_answer.get("outcomes") or [])[:1]:
                    if not isinstance(raw_outcome, dict) or item_count >= 3:
                        continue
                    items: list[dict[str, Any]] = []
                    for raw_item in (raw_outcome.get("items") or [])[:3]:
                        if not isinstance(raw_item, dict) or item_count >= 3:
                            continue
                        text = str(raw_item.get("text") or "").strip()[:300]
                        refs = resolved_hint_refs(raw_item.get("source_refs"))
                        if text and refs:
                            items.append({"text": text, "source_refs": refs})
                            item_count += 1
                    title = str(raw_outcome.get("title") or "").strip()[:90]
                    if title and items:
                        outcomes.append({"title": title, "items": items})
                related_questions: list[dict[str, Any]] = []
                for raw_question in (raw_grounded_answer.get("related_questions") or [])[:1]:
                    if not isinstance(raw_question, dict):
                        continue
                    refs = resolved_hint_refs(raw_question.get("source_refs"))
                    kind = str(raw_question.get("kind") or "understand")
                    label = str(raw_question.get("label") or "").strip()[:120]
                    question = str(raw_question.get("question") or "").strip()[:600]
                    if kind in {"understand", "connect", "apply"} and label and question and refs:
                        related_questions.append(
                            {"kind": kind, "label": label, "question": question, "source_refs": refs}
                        )
                if summary and summary_refs:
                    grounded_answer = {
                        "summary": summary,
                        "summary_source_refs": summary_refs,
                        "outcomes": outcomes,
                        "related_questions": related_questions,
                    }
            grounded_answer_diagnostics = {
                "raw_present": isinstance(raw_grounded_answer, dict) and bool(raw_grounded_answer),
                "raw_summary_chars": len(str((raw_grounded_answer or {}).get("summary") or ""))
                if isinstance(raw_grounded_answer, dict)
                else 0,
                "raw_summary_ref_count": len((raw_grounded_answer or {}).get("summary_source_refs") or [])
                if isinstance(raw_grounded_answer, dict)
                else 0,
                "raw_summary_refs": [
                    str(item)[:120]
                    for item in ((raw_grounded_answer or {}).get("summary_source_refs") or [])[:4]
                ]
                if isinstance(raw_grounded_answer, dict)
                else [],
                "resolved_summary_ref_count": len(summary_refs),
                "accepted": grounded_answer is not None,
            }
            sop_draft = None
            raw_sop_draft = planned.get("sop_draft")
            if (
                capability_id == "sop.plan"
                and operation in {"create", "refine"}
                and isinstance(raw_sop_draft, dict)
            ):
                sop_tasks: list[dict[str, Any]] = []
                for raw_task in (raw_sop_draft.get("tasks") or [])[:6]:
                    if not isinstance(raw_task, dict):
                        continue
                    task = {
                        "name": str(raw_task.get("name") or "").strip()[:90],
                        "purpose": str(raw_task.get("purpose") or "").strip()[:180],
                        "execution_mode": str(raw_task.get("execution_mode") or "").strip().lower(),
                        "exit_criteria": [
                            str(item).strip()[:160]
                            for item in (raw_task.get("exit_criteria") or [])[:2]
                            if str(item).strip()
                        ],
                        "required_evidence": [
                            str(item).strip()[:160]
                            for item in (raw_task.get("required_evidence") or [])[:2]
                            if str(item).strip()
                        ],
                    }
                    if (
                        task["name"]
                        and task["purpose"]
                        and task["execution_mode"] in {"manual", "copilot", "autopilot"}
                        and task["exit_criteria"]
                        and task["required_evidence"]
                    ):
                        sop_tasks.append(task)
                sop_title = str(raw_sop_draft.get("title") or "").strip()[:100]
                sop_goal = str(raw_sop_draft.get("goal") or "").strip()[:240]
                if sop_title and sop_goal and sop_tasks:
                    sop_draft = {
                        "title": sop_title,
                        "goal": sop_goal,
                        "tasks": sop_tasks,
                        "gaps": [
                            str(item).strip()[:160]
                            for item in (raw_sop_draft.get("gaps") or [])[:4]
                            if str(item).strip()
                        ],
                    }
            trusted_ref_set = set(trusted_context_refs)
            context_refs = list(
                dict.fromkeys(
                    str(item)
                    for item in planned.get("context_refs") or []
                    if str(item) in trusted_ref_set
                )
            )[:20]
            explorer_focal_refs = context_refs or hint_refs[:1]
            if presentation_mode == "explorer" and graph_query_draft is None and explorer_focal_refs:
                # The model has already selected an interactive relationship
                # result. Complete an omitted traversal contract only from
                # ACL-visible refs; do not reinterpret request wording here.
                graph_query_draft = {
                    "enabled": True,
                    "query_kind": "neighbors",
                    "focal_mentions": explorer_focal_refs[:1],
                    "target_mentions": [],
                    "node_kinds": [],
                    "relation_kinds": [],
                    "direction": "both",
                    "depth": 2,
                    "time_from": "",
                    "time_to": "",
                    "presentation": "explorer",
                }
            desired_outcome = {
                "run": "run_result",
                "test": "run_result",
                "complete": "completion_record",
                "capture": "knowledge_candidate",
                "promote": "promotion_request",
                "create": "draft",
                "refine": "draft",
                "validate": "validation_result",
            }.get(operation, "answer")
            work_intent = {
                "goal": str(state.get("question") or ""),
                "resolved_goal": resolved_goal[:12000],
                "retrieval_query": retrieval_query[:12000],
                "asset_kind": asset_kind,
                "operation": operation,
                "operation_plan": self._operation_plan(operation),
                "target_ref": str(planned.get("target_ref") or state.get("task_ref") or state.get("page_ref") or ""),
                "scope": str(planned.get("scope") or "auto"),
                "desired_outcome": desired_outcome,
                "presentation_mode": presentation_mode,
                "work_view": work_view,
                "graph_query_draft": graph_query_draft,
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
                "route_reason": "semantic_work_intent",
                "grounded_answer": grounded_answer,
                "grounded_answer_diagnostics": grounded_answer_diagnostics,
                "sop_draft": sop_draft,
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
        requested_result_kind: str = "",
        requested_graph_query_kind: str = "",
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
                "requested_result_kind": requested_result_kind,
                "requested_graph_query_kind": requested_graph_query_kind,
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
            "grounded_answer": result.get("grounded_answer"),
            "grounded_answer_diagnostics": result.get("grounded_answer_diagnostics") or {},
            "sop_draft": result.get("sop_draft"),
            "trace": result.get("trace") or [],
        }
