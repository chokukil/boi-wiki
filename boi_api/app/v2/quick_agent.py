from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .capabilities import CapabilityRegistry
from .models import (
    GroundedClaim,
    PlanValidationReport,
    SemanticPlan,
    TypedCommand,
    ValidationIssue,
    WorkOperation,
)
from .semantic_kernel import (
    PLANNER_SCHEMA_REVISION,
    PlanCompiler,
    PlanValidator,
    SemanticPlanningError,
    parse_semantic_plan,
    semantic_plan_schema,
)


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
    context_token_budget: int
    trusted_targets: dict[str, str]
    selected_subject_refs: list[str]
    requested_user_effect: str
    requested_operation: str
    requested_result_kind: str
    requested_graph_query_kind: str
    requested_work_view: str
    model: Any
    capability_id: str
    semantic_plan: dict[str, Any]
    plan_validation: dict[str, Any]
    planner_repair: dict[str, Any]
    work_intent: dict[str, Any]
    continuation: dict[str, Any]
    grounded_answer: dict[str, Any] | None
    grounded_answer_diagnostics: dict[str, Any]
    route_source: str
    route_reason: str
    planner_error: str
    clarification_question: str
    trace: list[str]


class QuickAgentRuntime:
    """Gemma-owned semantic planning with pure validation and one repair attempt."""

    engine = "langgraph"

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
        self.validator = PlanValidator(registry)
        self.compiler = PlanCompiler(registry, self.validator)
        graph = StateGraph(QuickAgentState)
        graph.add_node("normalize", self._normalize)
        graph.add_node("semantic_plan", self._plan)
        graph.add_edge(START, "normalize")
        graph.add_edge("normalize", "semantic_plan")
        graph.add_edge("semantic_plan", END)
        self._graph = graph.compile()

    @staticmethod
    def _normalize(state: QuickAgentState) -> dict[str, Any]:
        question = " ".join(str(state.get("question") or "").split()).strip()
        if not question:
            raise SemanticPlanningError("planner_invalid", "A non-empty request is required.")
        return {"question": question, "trace": ["observe", "normalize"]}

    def _capability_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "capability_id": item.capability_id,
                "title": item.title,
                "description": item.description,
                "primary_asset": item.primary_asset.value,
                "supported_assets": [asset.value for asset in item.supported_assets],
                "user_effects": list(item.user_effects),
                "semantic_operations": [operation.value for operation in item.semantic_operations],
                "semantic_operation_contracts": {
                    operation.value: contract.model_dump(mode="json")
                    for operation, contract in item.semantic_operation_contracts.items()
                },
                "default_operation": item.default_operation.value if item.default_operation else "",
                "presentations": list(item.presentations),
                "default_presentation": item.default_presentation,
                "presentation_aliases": dict(item.presentation_aliases),
                "graph_query_kinds": list(item.graph_query_kinds),
                "work_views": list(item.work_views),
                "work_view_operation_contracts": {
                    work_view: [operation.value for operation in operations]
                    for work_view, operations in item.work_view_operation_contracts.items()
                },
                "default_work_view": item.default_work_view,
                "evidence_scopes": list(item.evidence_scopes),
                "default_evidence_scope": item.default_evidence_scope,
                "allowed_loop_kinds": [kind.value for kind in item.allowed_loop_kinds],
                "allowed_loop_triggers": [trigger.value for trigger in item.allowed_loop_triggers],
                "default_loop_contract": item.default_loop_contract.model_dump(mode="json"),
                "subject_policy": item.subject_policy,
                "examples": list(item.examples),
                "deep": item.deep,
            }
            for item in self.registry.all()
        ]

    @staticmethod
    def _grounded_answer_schema(*, hint_count: int = 0) -> dict[str, Any]:
        schema = {
            "type": "object",
            "required": ["summary", "summary_source_refs", "claims", "outcomes", "related_questions"],
            "properties": {
                "summary": {"type": "string"},
                "summary_source_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "claim_id",
                            "text",
                            "claim_kind",
                            "source_scope",
                            "source_refs",
                            "supporting_chunk_ids",
                            "required_for_answer",
                        ],
                        "properties": {
                            "claim_id": {"type": "string", "maxLength": 80},
                            "text": {"type": "string"},
                            "claim_kind": {
                                "type": "string",
                                "enum": ["definition", "fact", "procedure", "comparison", "relationship", "work"],
                            },
                            "source_scope": {
                                "type": "string",
                                "enum": ["canonical", "operational", "validation"],
                            },
                            "source_refs": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string"},
                            },
                            "supporting_chunk_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string"},
                            },
                            "required_for_answer": {"type": "boolean"},
                        },
                    },
                },
                "outcomes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "maxLength": 160},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "source_refs": {
                                            "type": "array",
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
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["understand", "connect", "apply"]},
                            "label": {"type": "string", "maxLength": 160},
                            "question": {"type": "string", "maxLength": 1000},
                            "source_refs": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        if hint_count > 0:
            source_keys = [f"S{index}" for index in range(1, hint_count + 1)]
            chunk_keys = [f"C{index}" for index in range(1, hint_count + 1)]
            properties = schema["properties"]
            properties["summary_source_refs"]["items"]["enum"] = source_keys
            claim_properties = properties["claims"]["items"]["properties"]
            claim_properties["source_refs"]["items"]["enum"] = source_keys
            claim_properties["supporting_chunk_ids"]["items"]["enum"] = chunk_keys
            outcome_ref_items = (
                properties["outcomes"]["items"]["properties"]["items"]["items"]["properties"]
                ["source_refs"]["items"]
            )
            outcome_ref_items["enum"] = source_keys
            related_ref_items = (
                properties["related_questions"]["items"]["properties"]["source_refs"]["items"]
            )
            related_ref_items["enum"] = source_keys
        return schema

    def _planner_schema(self, state: QuickAgentState | None = None) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["semantic_plan", "grounded_answer"],
            "properties": {
                "semantic_plan": semantic_plan_schema(
                    self.registry,
                    trusted_context_refs=self._trusted_refs(state) if state is not None else [],
                    prior_topic_entities=self._prior_entities(state) if state is not None else [],
                    active_work_run=bool(state and state.get("active_work_run")),
                ),
                "grounded_answer": self._grounded_answer_schema(
                    hint_count=len(state.get("knowledge_hints") or []) if state is not None else 0,
                ),
            },
            "additionalProperties": False,
        }

    @staticmethod
    def _trusted_refs(state: QuickAgentState) -> list[str]:
        conversation = state.get("conversation_context") or {}
        active_artifact = conversation.get("active_artifact") if isinstance(conversation, dict) else {}
        topic_state = conversation.get("topic_state") if isinstance(conversation, dict) else {}
        active_work_run = state.get("active_work_run") or {}
        values = [
            *[
                str(item)
                for item in (conversation.get("recent_source_refs") or [])
                if str(item).strip()
            ],
            *[
                str(item.get("ref") or "")
                for item in (state.get("knowledge_hints") or [])
                if isinstance(item, dict) and str(item.get("ref") or "").strip()
            ],
        ]
        if isinstance(topic_state, dict):
            values.extend(str(item) for item in (topic_state.get("entities") or []) if str(item).strip())
        if isinstance(active_work_run, dict) and str(active_work_run.get("task_ref") or "").strip():
            values.append(str(active_work_run["task_ref"]))
        if isinstance(active_artifact, dict) and active_artifact.get("artifact_id"):
            values.append(str(active_artifact["artifact_id"]))
        if state.get("page_ref"):
            values.append(str(state["page_ref"]))
        if state.get("task_ref"):
            values.append(str(state["task_ref"]))
        values.extend(str(item) for item in (state.get("trusted_targets") or {}).values() if str(item).strip())
        return list(dict.fromkeys(item for item in values if item))[:500]

    @staticmethod
    def _prior_entities(state: QuickAgentState) -> list[str]:
        conversation = state.get("conversation_context") or {}
        topic = conversation.get("topic_state") if isinstance(conversation, dict) else {}
        active_artifact = conversation.get("active_artifact") if isinstance(conversation, dict) else {}
        values = [str(item) for item in (topic.get("entities") or []) if str(item).strip()] if isinstance(topic, dict) else []
        if isinstance(topic, dict) and str(topic.get("active_artifact_id") or "").strip():
            values.append(str(topic["active_artifact_id"]))
        if isinstance(active_artifact, dict) and str(active_artifact.get("artifact_id") or "").strip():
            values.append(str(active_artifact["artifact_id"]))
        return list(dict.fromkeys(values))

    def _typed_plan(self, state: QuickAgentState, capability_id: str, source: str) -> dict[str, Any]:
        definition = self.registry.get(capability_id)
        requested_operation = str(state.get("requested_operation") or "").strip()
        if requested_operation and requested_operation not in {item.value for item in definition.semantic_operations}:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The requested operation is not declared by the selected capability.",
            )
        operation = WorkOperation(requested_operation) if requested_operation else definition.default_operation
        if operation is None:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The capability catalog does not declare a default operation for this typed command.",
            )
        requested_effect = str(state.get("requested_user_effect") or "").strip()
        if requested_effect and requested_effect not in definition.user_effects:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The requested user effect is not declared by the selected capability.",
            )
        user_effect = requested_effect or definition.default_user_effect
        if user_effect is None:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The capability catalog does not declare a default user effect for this typed command.",
            )
        requested_presentation = str(state.get("requested_result_kind") or "").strip()
        presentation = (
            definition.presentation_aliases.get(requested_presentation, requested_presentation)
            if requested_presentation
            else definition.default_presentation
        )
        if presentation not in definition.presentations:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The requested presentation is not declared by the selected capability.",
            )
        subject_refs = list(
            dict.fromkeys(
                item
                for item in [
                    str(state.get("task_ref") or ""),
                    *[str(value) for value in (state.get("selected_subject_refs") or [])],
                ]
                if item
            )
        )
        graph_kind = str(state.get("requested_graph_query_kind") or "")
        requested_work_view = str(state.get("requested_work_view") or "").strip()
        work_view = requested_work_view or definition.default_work_view
        if work_view not in definition.work_views:
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The requested work view is not declared by the selected capability.",
            )
        graph_query = None
        if graph_kind:
            if graph_kind not in definition.graph_query_kinds:
                raise SemanticPlanningError(
                    "typed_command_invalid",
                    "The requested graph query is not declared by the selected capability.",
                )
            graph_query = {
                "enabled": True,
                "query_kind": graph_kind,
                "focal_mentions": subject_refs,
                "target_mentions": [],
                "node_kinds": [],
                "relation_kinds": [],
                "direction": "both",
                "depth": 2,
                "time_from": "",
                "time_to": "",
                "presentation": presentation if presentation in {"table", "timeline", "mermaid", "explorer"} else "auto",
            }
        compiled = self.compiler.compile_typed_command(
            TypedCommand(
                capability_id=capability_id,
                user_effect=user_effect,
                operation=operation,
                goal=str(state.get("question") or ""),
                subject_refs=subject_refs,
                presentation=presentation,
                work_view=work_view,
                graph_query=graph_query,
            ),
            trusted_context_refs=set(self._trusted_refs(state)),
        )
        return {
            "capability_id": compiled.capability_id,
            "semantic_plan": compiled.semantic_plan.model_dump(mode="json"),
            "plan_validation": self.validator.validate(
                compiled.semantic_plan,
                trusted_context_refs=set(self._trusted_refs(state)),
            ).model_dump(mode="json"),
            "work_intent": compiled.work_intent.model_dump(mode="json"),
            "continuation": {"continue_active_run": False, "delta_kind": "none", "user_confirmation": False},
            "grounded_answer": None,
            "route_source": source,
            "route_reason": "typed_command",
            "trace": [*(state.get("trace") or []), "semantic_plan:typed", "validate:passed", "compile"],
        }

    @staticmethod
    def _planner_system(*, repair: bool = False) -> str:
        base = (
            "You are the BoI Semantic Planner. Determine meaning, subject, workplace purpose, effect, operation, "
            "evidence scope, graph query, and presentation from the full request and verified topic state. "
            "Choose only contracts supplied in capability_catalog. Do not route by isolated words. Do not invent "
            "entity refs, source refs, permissions, or current state. Resolve entity refs only from trusted_entities "
            "and trusted_context_refs. The current page is a soft anchor, not a search "
            "boundary. A follow-up must be rewritten as a standalone resolved_goal and retrieval_query while preserving "
            "the verified prior subject; a clearly new topic must not inherit it. If two subjects remain equally likely, "
            "use topic_action=clarify and ask one short question. Return a read effect for explanation, inspection, "
            "comparison, or visualization; draft/transform/execute only when the user explicitly requests that effect. "
            "When verified_command_constraints are present, preserve their requested result form and graph query kind "
            "if the selected capability declares them; otherwise return a plan that validation can reject and repair. "
            "Graph node, relation, and time filters narrow real data: leave them empty unless the user explicitly "
            "asked for that exact restriction, and choose filter values only from graph_query_filter_contract. "
            "Use only internal_wiki_hints, operational_runtime_hints, and validation_hints for grounded claims. "
            "Use validation_hints only when semantic_plan.evidence_scope is validation. Every factual claim must cite "
            "the exact source_key and chunk_key that directly support it. If direct support is absent, omit the claim and "
            "return an empty grounded_answer. Set required_for_answer=true only when omitting that claim would make the "
            "answer materially wrong or unusable; supporting context and optional detail must set it to false. External "
            "knowledge is not evidence. Do not add an unrequested SOP, Task, "
            "Event, Action, graph, or follow-up action. semantic_plan is the sole meaning contract; grounded_answer "
            "may express factual claims but must not change the selected meaning. Select loop_contract only from the "
            "capability contract. Use turn for one bounded response and goal only when the catalog supplies verifiable "
            "exit criteria. Do not create time or proactive loops from ordinary chat. Use conversation_turns to resolve "
            "discourse and follow-up references, but inherit factual content only from supported grounded_claims and "
            "verified_topic_state. State every SemanticPlan field explicitly. Choose the capability for the requested "
            "outcome of this turn, not merely the capability used by the prior turn. topic_action=continue is valid only when "
            "verified_topic_state contains at least one verified entity; without that state use new for a resolved "
            "subject or clarify for genuine ambiguity. Use topic_action=continue whenever the "
            "request refers to, re-expresses, or changes only the presentation of a verified prior subject; use new "
            "only for a distinct subject. A drill-down, selection from a prior result, added comparison subject, or "
            "additional view of prior work is a continuation: retain at least one verified prior entity and add every "
            "newly resolved entity without duplicates. When a request explicitly names multiple subjects, resolve and "
            "preserve each ACL-visible subject rather than collapsing them into one. verified_topic_state.subjects is "
            "the complete prior semantic subject set; its singular subject field is only a display label. If multiple "
            "prior subjects remain "
            "equally plausible and the request does not distinguish one, set reference_resolution=ambiguous and clarify "
            "instead of choosing arbitrarily. For a continuation, set reference_resolution=specific only when exactly "
            "one prior subject is selected, or all when every prior subject is selected. New topics use none. "
            "Select work_view from the requested workplace perspective before choosing operation. When a non-none "
            "work_view is requested, choose only an operation declared by that capability's "
            "work_view_operation_contracts; do not bypass the requested perspective by returning work_view=none. "
            "If the selected semantic_operation_contract declares no graph_query_kinds, set graph_query.enabled=false. "
            "Never select a graph traversal that is absent from the selected semantic operation contract. "
            "retrieval_query must be a standalone, meaningful search request, never a "
            "placeholder or serialized null. When active_work.work_run is empty, do not supply continuation work "
            "details; the default continuation is inactive and empty."
        )
        if repair:
            return base + (
                " This is the single repair attempt. Preserve the user's request. Correct only the reported validation "
                "issues using the supplied catalog; do not choose a fallback capability or reduce the requested effect."
            )
        return base

    @staticmethod
    def _clarification_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["clarification_question"],
            "properties": {
                "clarification_question": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 240,
                }
            },
        }

    def clarify_ambiguous_subject(
        self,
        *,
        model: Any,
        original_request: str,
        semantic_plan: SemanticPlan,
        mention: str,
        candidates: list[dict[str, str]],
    ) -> str:
        """Ask the planner to phrase one clarification from ACL-visible candidates."""

        readiness = model.readiness() if model is not None and hasattr(model, "readiness") else {}
        if not readiness.get("generation"):
            raise SemanticPlanningError("planner_unavailable", "The local semantic planner is unavailable.")
        try:
            result = model.generate_structured(
                system=(
                    "You are the BoI Semantic Planner. The validated request reached entity resolution and one "
                    "subject mention maps to multiple ACL-visible candidates. Write exactly one short clarification "
                    "question that preserves the original request and asks the user to select the intended subject. "
                    "Do not add facts, recommendations, or a fallback operation."
                ),
                prompt=json.dumps(
                    {
                        "request": original_request,
                        "resolved_goal": semantic_plan.resolved_goal,
                        "ambiguous_mention": mention,
                        "candidates": candidates[:10],
                    },
                    ensure_ascii=False,
                ),
                schema=self._clarification_schema(),
            )
        except Exception as exc:
            if isinstance(exc, SemanticPlanningError):
                raise
            raise SemanticPlanningError(
                "planner_invalid",
                f"The planner could not phrase an entity clarification: {type(exc).__name__}: {exc}",
            ) from exc
        question = str((result or {}).get("clarification_question") or "").strip()
        if not question:
            raise SemanticPlanningError(
                "planner_invalid",
                "The planner returned an empty entity clarification.",
            )
        return question

    def _planner_payload(
        self,
        state: QuickAgentState,
        *,
        invalid_output: dict[str, Any] | None = None,
        validation_issues: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        hints = [item for item in (state.get("knowledge_hints") or []) if isinstance(item, dict)]
        conversation = state.get("conversation_context") or {}
        conversation_turns = [
            item
            for item in (
                conversation.get("recent_messages")
                if isinstance(conversation, dict)
                else []
            ) or []
            if isinstance(item, dict)
        ]
        context_token_budget = max(0, int(state.get("context_token_budget") or 0))
        if context_token_budget:
            fixed_payload = {
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
                "verified_topic_state": conversation.get("topic_state") or {},
                "trusted_context_refs": self._trusted_refs(state),
                "trusted_entities": dict(state.get("trusted_targets") or {}),
                "capability_catalog": self._capability_catalog(),
                "invalid_output": invalid_output or {},
                "validation_issues": validation_issues or [],
            }
            fixed_text = json.dumps(
                {
                    "system": self._planner_system(repair=bool(invalid_output or validation_issues)),
                    "schema": self._planner_schema(state),
                    "payload": fixed_payload,
                },
                ensure_ascii=False,
                default=str,
            )
            remaining_tokens = max(
                0,
                context_token_budget - (len(fixed_text.encode("utf-8")) + 3) // 4,
            )

            def item_tokens(item: Any) -> int:
                return max(
                    1,
                    (len(json.dumps(item, ensure_ascii=False, default=str).encode("utf-8")) + 3) // 4,
                )

            selected_turns: list[dict[str, Any]] = []
            latest_turns = conversation_turns[-2:]
            for item in latest_turns:
                cost = item_tokens(item)
                if cost <= remaining_tokens:
                    selected_turns.append(item)
                    remaining_tokens -= cost

            selected_hints: list[dict[str, Any]] = []
            for item in hints:
                cost = item_tokens(item)
                if cost > remaining_tokens:
                    continue
                selected_hints.append(item)
                remaining_tokens -= cost

            older_selected: list[dict[str, Any]] = []
            for item in reversed(conversation_turns[:-2]):
                cost = item_tokens(item)
                if cost > remaining_tokens:
                    continue
                older_selected.append(item)
                remaining_tokens -= cost
            conversation_turns = [*reversed(older_selected), *selected_turns]
            hints = selected_hints
        planner_hints = [
            {**item, "source_key": f"S{index}", "chunk_key": f"C{index}"}
            for index, item in enumerate(hints, start=1)
        ]
        return {
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
            "verified_topic_state": conversation.get("topic_state") if isinstance(conversation, dict) else {},
            "conversation_turns": conversation_turns,
            "trusted_context_refs": self._trusted_refs(state),
            "trusted_entities": dict(state.get("trusted_targets") or {}),
            "verified_command_constraints": {
                "presentation": str(state.get("requested_result_kind") or ""),
                "graph_query_kind": str(state.get("requested_graph_query_kind") or ""),
                "work_view": str(state.get("requested_work_view") or ""),
            },
            "internal_wiki_hints": [item for item in planner_hints if item.get("answer_scope") == "canonical"],
            "operational_runtime_hints": [item for item in planner_hints if item.get("answer_scope") == "operational"],
            "validation_hints": [item for item in planner_hints if item.get("answer_scope") == "validation"],
            "capability_catalog_revision": self.registry.version,
            "capability_catalog": self._capability_catalog(),
            "graph_query_filter_contract": self.registry.graph_query_filter_contract.model_dump(mode="json"),
            "planner_schema_revision": PLANNER_SCHEMA_REVISION,
            "invalid_output": invalid_output or {},
            "validation_issues": validation_issues or [],
        }

    @staticmethod
    def _reference_assessment_schema(prior_refs: list[str]) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "selected_ref", "clarification_question"],
            "properties": {
                "status": {"type": "string", "enum": ["justified", "ambiguous"]},
                "selected_ref": {"type": "string", "enum": ["", *prior_refs]},
                "clarification_question": {"type": "string", "maxLength": 240},
            },
        }

    def _validate_specific_reference_semantics(
        self,
        *,
        state: QuickAgentState,
        model: Any,
        plan: SemanticPlan,
    ) -> None:
        prior_refs = self._prior_entities(state)
        if not (
            len(prior_refs) > 1
            and plan.topic_action == "continue"
            and plan.reference_resolution == "specific"
        ):
            return

        selected_refs = [
            item.entity_ref
            for item in plan.subjects
            if item.resolution == "resolved" and item.entity_ref in prior_refs
        ]
        if len(selected_refs) != 1:
            return

        titles = {
            str(item.get("ref") or ""): str(item.get("title") or item.get("label") or "")
            for item in (state.get("knowledge_hints") or [])
            if isinstance(item, dict) and str(item.get("ref") or "")
        }
        candidates = [
            {"ref": ref, "title": titles.get(ref) or ref}
            for ref in prior_refs
        ]
        try:
            assessment = model.generate_structured(
                system=(
                    "You are an independent discourse-reference evaluator. Decide only whether the current request "
                    "uniquely identifies the planner-selected prior subject from the supplied complete candidate set. "
                    "Do not use outside knowledge and do not answer the request. Return justified only when the current "
                    "request itself distinguishes that one candidate; if another candidate remains equally possible, "
                    "return ambiguous and one short clarification question."
                ),
                prompt=json.dumps(
                    {
                        "request": state.get("question") or "",
                        "prior_subjects": candidates,
                        "planner_selected_ref": selected_refs[0],
                    },
                    ensure_ascii=False,
                ),
                schema=self._reference_assessment_schema(prior_refs),
            )
        except Exception as exc:
            raise SemanticPlanningError(
                "planner_invalid",
                f"Reference evaluation failed: {type(exc).__name__}: {exc}",
            ) from exc

        status = str((assessment or {}).get("status") or "")
        selected_ref = str((assessment or {}).get("selected_ref") or "")
        if status == "justified" and selected_ref == selected_refs[0]:
            return

        issue = ValidationIssue(
            code="topic.specific_reference_not_justified",
            field="reference_resolution",
            message="An independent semantic evaluation found that the request does not uniquely select one prior subject.",
            details={"prior": prior_refs, "planner_selected": selected_refs[0]},
        )
        raise SemanticPlanningError(
            "planner_invalid",
            "Semantic plan failed reference evaluation.",
            report=PlanValidationReport(
                valid=False,
                issues=[issue],
                catalog_revision=self.registry.version,
                planner_schema_revision=PLANNER_SCHEMA_REVISION,
            ),
            clarification_question=str((assessment or {}).get("clarification_question") or ""),
        )

    def _validate_envelope(
        self,
        state: QuickAgentState,
        envelope: dict[str, Any],
        *,
        model: Any,
    ) -> tuple[SemanticPlan, dict[str, Any]]:
        raw_plan = dict(envelope.get("semantic_plan") or {}) if isinstance(envelope.get("semantic_plan"), dict) else {}
        legacy_continuation = envelope.get("continuation")
        if "continuation" not in raw_plan and isinstance(legacy_continuation, dict):
            raw_plan["continuation"] = legacy_continuation
        plan = parse_semantic_plan(raw_plan)
        report = self.validator.validate(
            plan,
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        )
        if not report.valid:
            raise SemanticPlanningError(
                "planner_invalid",
                "Semantic plan failed validation.",
                report=report,
                clarification_question=plan.clarification_question,
            )
        self._validate_specific_reference_semantics(state=state, model=model, plan=plan)
        return plan, report.model_dump(mode="json")

    @staticmethod
    def _resolve_grounded_answer(
        envelope: dict[str, Any],
        plan: SemanticPlan,
        hints: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        raw = envelope.get("grounded_answer") if isinstance(envelope.get("grounded_answer"), dict) else {}
        by_source_key = {f"S{index}": item for index, item in enumerate(hints, start=1)}
        by_chunk_key = {f"C{index}": item for index, item in enumerate(hints, start=1)}
        by_ref = {str(item.get("ref") or ""): item for item in hints if str(item.get("ref") or "")}
        by_chunk = {str(item.get("chunk_id") or ""): item for item in hints if str(item.get("chunk_id") or "")}

        def source_ref(value: Any) -> str:
            key = str(value or "")
            item = by_source_key.get(key) or by_ref.get(key)
            return str(item.get("ref") or "") if item else ""

        def chunk_ref(value: Any) -> str:
            key = str(value or "")
            item = by_chunk_key.get(key) or by_chunk.get(key)
            return str(item.get("chunk_id") or "") if item else ""

        def refs_match_plan_scope(refs: list[str], chunks: list[str] | None = None) -> bool:
            source_items = [by_ref.get(ref) for ref in refs]
            chunk_items = [by_chunk.get(chunk) for chunk in (chunks or [])]
            return bool(refs) and all(
                isinstance(item, dict)
                and str(item.get("answer_scope") or "canonical") == plan.evidence_scope
                for item in [*source_items, *chunk_items]
            )

        claims: list[dict[str, Any]] = []
        unsupported_claims: list[dict[str, Any]] = []
        rejected = 0
        for raw_claim in raw.get("claims") or []:
            if not isinstance(raw_claim, dict):
                continue
            refs = list(dict.fromkeys(filter(None, (source_ref(item) for item in raw_claim.get("source_refs") or []))))
            chunks = list(dict.fromkeys(filter(None, (chunk_ref(item) for item in raw_claim.get("supporting_chunk_ids") or []))))
            chunk_sources = {
                str((by_chunk.get(chunk) or {}).get("ref") or "")
                for chunk in chunks
                if by_chunk.get(chunk)
            }
            directly_bounded = bool(refs and chunks and chunk_sources and chunk_sources.issubset(set(refs)))
            scope = str(raw_claim.get("source_scope") or plan.evidence_scope)
            scope_matches = scope == plan.evidence_scope and refs_match_plan_scope(refs, chunks)
            if directly_bounded and scope_matches:
                claims.append(
                    GroundedClaim(
                        claim_id=str(raw_claim.get("claim_id") or f"claim-{len(claims) + 1}"),
                        text=str(raw_claim.get("text") or "").strip(),
                        claim_kind=str(raw_claim.get("claim_kind") or plan.answer_intent),
                        source_scope=scope,
                        source_refs=refs,
                        supporting_chunk_ids=chunks,
                        required_for_answer=bool(raw_claim.get("required_for_answer")),
                    ).model_dump(mode="json")
                )
            else:
                rejected += 1
                text = str(raw_claim.get("text") or "").strip()
                if text:
                    unsupported_claims.append(
                        GroundedClaim(
                            claim_id=str(raw_claim.get("claim_id") or f"claim-rejected-{rejected}"),
                            text=text,
                            claim_kind=str(raw_claim.get("claim_kind") or plan.answer_intent),
                            source_scope=(
                                scope
                                if scope in {"canonical", "operational", "validation"}
                                else plan.evidence_scope
                            ),
                            source_refs=refs,
                            supporting_chunk_ids=chunks,
                            support_status="unsupported",
                            required_for_answer=bool(raw_claim.get("required_for_answer")),
                        ).model_dump(mode="json")
                    )

        summary = str(raw.get("summary") or "").strip()
        summary_refs = list(dict.fromkeys(filter(None, (source_ref(item) for item in raw.get("summary_source_refs") or []))))
        accepted_claim_refs = {
            str(ref)
            for claim in claims
            for ref in claim.get("source_refs") or []
            if str(ref)
        }
        summary_grounded = (
            bool(summary_refs)
            and set(summary_refs).issubset(accepted_claim_refs)
            and refs_match_plan_scope(summary_refs)
        )
        if not claims:
            if unsupported_claims:
                return (
                    {
                        "answer_intent": plan.answer_intent,
                        "summary": summary,
                        "summary_source_refs": summary_refs,
                        "claims": [*claims, *unsupported_claims],
                        "outcomes": [],
                        "related_questions": [],
                    },
                    {
                        "accepted": False,
                        "accepted_claims": len(claims),
                        "rejected_claims": rejected,
                    },
                )
            return None, {"accepted": False, "accepted_claims": len(claims), "rejected_claims": rejected}

        # The rendered answer is claim-driven. If the model's separate summary
        # cites a broader source set than its validated claims, derive the
        # summary from the first accepted claim instead of discarding every
        # otherwise grounded claim or trusting an unverified summary sentence.
        if not summary or not summary_grounded:
            summary = str(claims[0].get("text") or "").strip()
            summary_refs = list(claims[0].get("source_refs") or [])

        outcomes: list[dict[str, Any]] = []
        for outcome in raw.get("outcomes") or []:
            if not isinstance(outcome, dict):
                continue
            items = []
            for raw_item in outcome.get("items") or []:
                if not isinstance(raw_item, dict):
                    continue
                refs = list(dict.fromkeys(filter(None, (source_ref(item) for item in raw_item.get("source_refs") or []))))
                if (
                    refs
                    and set(refs).issubset(accepted_claim_refs)
                    and refs_match_plan_scope(refs)
                    and str(raw_item.get("text") or "").strip()
                ):
                    items.append({"text": str(raw_item["text"]), "source_refs": refs})
            if items and str(outcome.get("title") or "").strip():
                outcomes.append({"title": str(outcome["title"])[:160], "items": items})

        related = []
        for item in (raw.get("related_questions") or [])[:3]:
            if not isinstance(item, dict):
                continue
            refs = list(dict.fromkeys(filter(None, (source_ref(ref) for ref in item.get("source_refs") or []))))
            if (
                refs
                and set(refs).issubset(accepted_claim_refs)
                and refs_match_plan_scope(refs)
                and item.get("kind") in {"understand", "connect", "apply"}
                and item.get("label")
                and item.get("question")
            ):
                related.append(
                    {
                        "kind": item["kind"],
                        "label": str(item["label"])[:160],
                        "question": str(item["question"])[:1000],
                        "source_refs": refs,
                    }
                )
        return (
            {
                "answer_intent": plan.answer_intent,
                "summary": summary,
                "summary_source_refs": summary_refs,
                "claims": [*claims, *unsupported_claims],
                "outcomes": outcomes,
                "related_questions": related,
            },
            {"accepted": True, "accepted_claims": len(claims), "rejected_claims": rejected},
        )

    def _repair_grounded_answer(
        self,
        *,
        model: Any,
        state: QuickAgentState,
        plan: SemanticPlan,
        hints: list[dict[str, Any]],
        diagnostics: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Retry claim construction once without allowing the validated plan to change."""

        matching_hints = [
            item
            for item in hints
            if str(item.get("answer_scope") or "canonical") == plan.evidence_scope
        ]
        scoped_hints = [
            {**item, "source_key": f"S{index}", "chunk_key": f"C{index}"}
            for index, item in enumerate(matching_hints, start=1)
        ]
        if not scoped_hints or plan.user_effect != "read":
            return None, {**diagnostics, "repair": "not_applicable"}
        try:
            repaired = model.generate_structured(
                system=(
                    "You repair only the grounded answer for an already validated BoI SemanticPlan. Do not change "
                    "the plan, topic, capability, operation, effect, scope, or presentation. Use only the supplied "
                    "internal hints. Every factual claim must cite the exact source_key and chunk_key that directly "
                    "entail it. Omit unsupported claims and never use external or model-memory facts. Set "
                    "required_for_answer=true only when omitting the claim would make the answer materially wrong or "
                    "unusable; supporting context and optional detail must set it to false. Return only the requested "
                    "grounded answer schema."
                ),
                prompt=json.dumps(
                    {
                        "request": state.get("question") or "",
                        "validated_semantic_plan": plan.model_dump(mode="json"),
                        "internal_hints": scoped_hints,
                        "prior_grounding_diagnostics": diagnostics,
                    },
                    ensure_ascii=False,
                ),
                schema=self._grounded_answer_schema(hint_count=len(scoped_hints)),
            )
            grounded_answer, repaired_diagnostics = self._resolve_grounded_answer(
                {"grounded_answer": repaired},
                plan,
                scoped_hints,
            )
            return grounded_answer, {
                **repaired_diagnostics,
                "repair": "accepted" if grounded_answer is not None else "insufficient",
            }
        except Exception as exc:
            return None, {
                **diagnostics,
                "repair": "failed",
                "repair_failure": type(exc).__name__,
            }

    def _plan(self, state: QuickAgentState) -> dict[str, Any]:
        offered = str(state.get("offered_capability") or "").strip()
        explicit = str(state.get("explicit_capability") or "").strip()
        if offered:
            return self._typed_plan(state, offered, "offer_id")
        if explicit:
            return self._typed_plan(state, explicit, "explicit")

        model = state.get("model")
        readiness = model.readiness() if model is not None and hasattr(model, "readiness") else {}
        if not readiness.get("generation"):
            raise SemanticPlanningError("planner_unavailable", "The local semantic planner is unavailable.")

        envelope: dict[str, Any] = {}
        first_error: SemanticPlanningError | None = None
        planner_repair: dict[str, Any] = {"attempted": False, "reason": ""}
        try:
            envelope = model.generate_structured(
                system=self._planner_system(),
                prompt=json.dumps(self._planner_payload(state), ensure_ascii=False),
                schema=self._planner_schema(state),
            )
            plan, report = self._validate_envelope(state, envelope, model=model)
        except Exception as exc:
            first_error = exc if isinstance(exc, SemanticPlanningError) else SemanticPlanningError(
                "planner_invalid", f"{type(exc).__name__}: {exc}"
            )
            planner_repair = {
                "attempted": True,
                "reason": first_error.code,
                "issues": (
                    [item.model_dump(mode="json") for item in first_error.report.issues]
                    if first_error.report
                    else [{"code": first_error.code, "message": str(first_error)}]
                ),
            }
            try:
                repaired = model.generate_structured(
                    system=self._planner_system(repair=True),
                    prompt=json.dumps(
                        self._planner_payload(
                            state,
                            invalid_output=envelope,
                            validation_issues=(
                                [item.model_dump(mode="json") for item in first_error.report.issues]
                                if first_error.report
                                else [{"code": first_error.code, "message": str(first_error)}]
                            ),
                        ),
                        ensure_ascii=False,
                    ),
                    schema=self._planner_schema(state),
                )
                envelope = repaired
                plan, report = self._validate_envelope(state, envelope, model=model)
            except Exception as repair_exc:
                error = repair_exc if isinstance(repair_exc, SemanticPlanningError) else SemanticPlanningError(
                    "planner_invalid", f"{type(repair_exc).__name__}: {repair_exc}"
                )
                clarification = error.clarification_question or (first_error.clarification_question if first_error else "")
                raise SemanticPlanningError(
                    error.code,
                    str(error),
                    report=error.report or (first_error.report if first_error else None),
                    clarification_question=clarification,
                ) from repair_exc

        compiled = self.compiler.compile(
            plan,
            original_question=str(state.get("question") or ""),
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        )
        hints = [item for item in (state.get("knowledge_hints") or []) if isinstance(item, dict)]
        grounded_answer, diagnostics = self._resolve_grounded_answer(envelope, plan, hints)
        # A validated graph query is answered from the ACL-bounded graph
        # DomainResult and grounded again by the graph service. Repairing a
        # planner-authored prose answer here adds another model call whose
        # output is never used. Keep the one-shot repair for non-graph reads,
        # where the planner answer is the actual domain result.
        graph_result_is_authoritative = bool(plan.graph_query and plan.graph_query.enabled)
        if grounded_answer is None and not graph_result_is_authoritative:
            grounded_answer, diagnostics = self._repair_grounded_answer(
                model=model,
                state=state,
                plan=plan,
                hints=hints,
                diagnostics=diagnostics,
            )
        elif grounded_answer is None:
            diagnostics = {**diagnostics, "repair": "deferred_to_graph_result"}
        continuation = plan.continuation.model_dump(mode="json")
        return {
            "capability_id": compiled.capability_id,
            "semantic_plan": plan.model_dump(mode="json"),
            "plan_validation": report,
            "planner_repair": planner_repair,
            "work_intent": compiled.work_intent.model_dump(mode="json"),
            "continuation": continuation,
            "grounded_answer": grounded_answer,
            "grounded_answer_diagnostics": diagnostics,
            "clarification_question": plan.clarification_question,
            "route_source": "llm_structured",
            "route_reason": "semantic_plan_validated",
            "trace": [
                *(state.get("trace") or []),
                "semantic_plan:llm",
                *(["semantic_plan:repair"] if planner_repair["attempted"] else []),
                "validate:passed",
                *(
                    ["grounded_answer:graph_result"]
                    if diagnostics.get("repair") == "deferred_to_graph_result"
                    else ["grounded_answer:repair"]
                    if diagnostics.get("repair")
                    else []
                ),
                "compile",
            ],
        }

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
        selected_subject_refs: list[str] | None = None,
        requested_user_effect: str = "",
        requested_operation: str = "",
        requested_result_kind: str = "",
        requested_graph_query_kind: str = "",
        requested_work_view: str = "",
        context_token_budget: int = 0,
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
                "knowledge_hints": list(knowledge_hints or []),
                "context_token_budget": max(0, int(context_token_budget or 0)),
                "trusted_targets": dict(trusted_targets or {}),
                "selected_subject_refs": list(selected_subject_refs or [])[:20],
                "requested_user_effect": requested_user_effect,
                "requested_operation": requested_operation,
                "requested_result_kind": requested_result_kind,
                "requested_graph_query_kind": requested_graph_query_kind,
                "requested_work_view": requested_work_view,
                "model": model,
            }
        )
        return {
            "engine": self.engine,
            "capability_id": result["capability_id"],
            "semantic_plan": result["semantic_plan"],
            "plan_validation": result["plan_validation"],
            "planner_repair": result.get("planner_repair") or {"attempted": False, "reason": ""},
            "work_intent": result["work_intent"],
            "continuation": result.get("continuation") or {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
            },
            "grounded_answer": result.get("grounded_answer"),
            "grounded_answer_diagnostics": result.get("grounded_answer_diagnostics") or {},
            "clarification_question": result.get("clarification_question") or "",
            "source": result.get("route_source") or "llm_structured",
            "reason": result.get("route_reason") or "semantic_plan_validated",
            "planner_error": result.get("planner_error") or "",
            "trace": result.get("trace") or [],
        }
