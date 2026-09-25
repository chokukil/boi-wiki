from __future__ import annotations

import copy
import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .capabilities import CapabilityRegistry
from .models import (
    GraphQueryDraft,
    GroundedClaim,
    PlanValidationReport,
    SemanticPlan,
    SemanticPlanV4,
    SemanticEvidenceRequirements,
    SemanticSubject,
    TypedCommand,
    ValidationIssue,
    WorkAssetKind,
    WorkOperation,
)
from .model_gateway import ModelBudgetExceeded, remaining_model_input_budget
from .repository import KnowledgeRepository
from .semantic_kernel import (
    PLANNER_SCHEMA_REVISION,
    PlanCompiler,
    PlanValidator,
    SemanticPlanningError,
    parse_semantic_plan,
    parse_semantic_plan_v4,
    semantic_plan_schema,
    semantic_plan_v4_schema,
)


PLANNER_CONTEXT_TOKEN_LIMIT = 4_000
PLANNER_SUBJECT_HINT_LIMIT = 12


class QuickAgentState(TypedDict, total=False):
    question: str
    page_kind: str
    page_ref: str
    page_title: str
    explicit_capability: str
    offered_capability: str
    active_capability: str
    active_artifact_title: str
    active_artifact_input: dict[str, str]
    active_work_run: dict[str, Any]
    task_ref: str
    conversation_summary: str
    conversation_context: dict[str, Any]
    source_policy_context: dict[str, Any]
    current_selection: dict[str, Any]
    knowledge_hints: list[dict[str, Any]]
    context_token_budget: int
    trusted_targets: dict[str, str]
    trusted_entity_kinds: dict[str, str]
    selected_subject_refs: list[str]
    verified_typed_command_source: str
    requested_user_effect: str
    requested_operation: str
    requested_result_kind: str
    requested_graph_query_kind: str
    requested_graph_node_kinds: list[str]
    requested_graph_relation_kinds: list[str]
    requested_work_view: str
    model: Any
    capability_id: str
    semantic_plan: dict[str, Any]
    semantic_plan_v4: dict[str, Any]
    execution_plan: dict[str, Any]
    catalog_compile: dict[str, Any]
    planner_context_manifest: dict[str, Any]
    plan_validation: dict[str, Any]
    planner_repair: dict[str, Any]
    work_intent: dict[str, Any]
    continuation: dict[str, Any]
    grounded_answer: dict[str, Any] | None
    grounded_answer_diagnostics: dict[str, Any]
    defer_grounded_answer: bool
    route_source: str
    route_reason: str
    planner_error: str
    clarification_question: str
    safe_stop_after_repair: bool
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
                "subject_kinds": list(item.subject_kinds),
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

    def _semantic_contract(self) -> dict[str, Any]:
        """Planner-visible meaning vocabulary without runtime/capability choices."""

        definitions = self.registry.all()
        return {
            "schema_revision": PLANNER_SCHEMA_REVISION,
            "operations": sorted(
                {operation.value for item in definitions for operation in item.semantic_operations}
            ),
            "subject_kinds": sorted(
                {
                    kind
                    for item in definitions
                    for kind in [*item.subject_kinds, *item.semantic_compile.preferred_subject_kinds]
                    if kind
                }
            ),
            "result_asset_kinds": [item.value for item in WorkAssetKind],
            "presentations": ["prose", "table", "timeline", "mermaid", "explorer", "artifact"],
            "evidence_scopes": ["canonical", "operational", "validation"],
            "evidence_modes": sorted(
                {
                    mode
                    for item in definitions
                    for mode in item.semantic_compile.evidence_modes
                    if mode
                }
            ),
            "work_perspectives": ["current", "responsibility"],
            "field_meanings": {
                "operations": {
                    "understand": "Explain or retrieve subjects independently.",
                    "compare": "Contrast two or more subjects, their differences, and criteria.",
                    "connect": "Traverse verified relations, paths, lineage, or impact.",
                    "validate": "Check a claim or result against evidence and provenance.",
                    "observe": "Report operational state without mutation.",
                    "create": "Create a new private editable draft.",
                    "refine": "Revise or decompose an existing draft or artifact.",
                    "test": "Test an existing target or definition with sample input.",
                    "run": "Invoke an approved execution after confirmation.",
                    "complete": "Prepare or record Task completion against its contract.",
                    "capture": "Capture verified results as private provisional knowledge.",
                    "promote": "Request reviewed promotion to broader scope.",
                },
                "result_asset_kind": (
                    "The domain asset the user wants produced or transformed. Use null for reads and runtime "
                    "execution results; use sop, workflow, task, business_event, action, skill, knowledge, or evidence "
                    "only when that output is explicitly requested."
                ),
                "work_perspectives": {
                    "none": (
                        "Use [] outside explicit active-assignment or official-responsibility questions, including "
                        "selected Task/page/Event context and Person outcome or Agent/System usage lineage."
                    ),
                    "current": (
                        "Active assigned work only, backed by current_work or execution_evidence; not recency, "
                        "current content, or the currently selected Task/page/Event/artifact."
                    ),
                    "responsibility": (
                        "Only an explicitly requested official or declared role/responsibility; never infer it from "
                        "Person/Org membership, an official WorkRun record, activity, outcomes, or tool usage."
                    ),
                },
                "presentation_intent": {
                    "selection_rule": (
                        "Preserve the user's explicitly requested primary result form exactly. When an explanation "
                        "and a structured form are both requested, select the structured form; prose may accompany it."
                    ),
                    "prose": "A narrative answer when no more specific primary result form was requested.",
                    "table": "A row-and-column comparison or structured record view.",
                    "timeline": "A time-ordered sequence of verified events or states.",
                    "mermaid": "A Mermaid visualization of verified relationships or flow.",
                    "explorer": "An interactive ontology relationship exploration.",
                    "artifact": "An editable private draft or transformation preview.",
                },
                "loop_intent": {
                    "turn": "One bounded answer or visualization.",
                    "goal": "Explicit durable work toward completion.",
                    "time": "Explicit scheduled or interval work.",
                    "proactive": "Registered Event or schedule driven work.",
                },
                "user_effect": {
                    "read": "Return information or visualization without mutation.",
                    "draft": "Create a private draft or verified knowledge candidate.",
                    "transform": "Create an editable private preview from a verified input.",
                    "execute": "Prepare or run an existing target; runtime confirmation gates mutation.",
                },
                "evidence_modes": {
                    "authoritative_knowledge": "Reviewed definitions and canonical facts.",
                    "current_work": "Active assignment records only.",
                    "historical_cases": "Completed or historical cases.",
                    "relationship_provenance": "Verified graph relations.",
                    "execution_evidence": "Action, Task, Workflow, or WorkRun proof.",
                    "private_learning": "ACL-visible private provisional knowledge.",
                },
                "authority_scope": {
                    "any": "No organizational authority level required.",
                    "person": "Person-authorized or broader approved source.",
                    "team": "Team-authorized or broader approved source.",
                    "org": "Org-authorized or company-approved source.",
                    "company": "Company-authorized canonical source only.",
                },
            },
            "mutation_intents": [
                "none", "private_draft", "transform_preview", "execute", "activate", "promote"
            ],
            "loop_intents": ["turn", "goal", "time", "proactive"],
        }

    def _planner_semantic_contract(self) -> dict[str, Any]:
        """Return schema-owned vocabulary without duplicating prose rules.

        The system prompt and JSON schema already carry the field meanings.
        Repeating the full explanatory dictionary can consume the bounded
        planner context on a continuation and evict its focal source identity.
        """

        contract = self._semantic_contract()
        return {
            key: value
            for key, value in contract.items()
            if key != "field_meanings"
        }

    @staticmethod
    def _grounded_answer_schema(*, hint_count: int = 0) -> dict[str, Any]:
        schema = {
            "title": "BoIGroundedAnswer",
            "x-boi-call-type": "answer",
            "type": "object",
            "required": [
                "summary",
                "summary_source_refs",
                "claims",
                "unresolved_claims",
                "outcomes",
                "related_questions",
            ],
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
                            "text": {
                                "type": "string",
                                "description": (
                                    "One exact contiguous source statement or one table whose literal cells are "
                                    "copied from the cited source table. Do not combine, paraphrase, or infer facts."
                                ),
                            },
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
                "unresolved_claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["text", "claim_kind", "source_scope", "required_for_answer"],
                        "properties": {
                            "text": {"type": "string"},
                            "claim_kind": {
                                "type": "string",
                                "enum": ["definition", "fact", "procedure", "comparison", "relationship", "work"],
                            },
                            "source_scope": {
                                "type": "string",
                                "enum": ["canonical", "operational", "validation"],
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

    @staticmethod
    def _verified_semantic_constraints(state: QuickAgentState | None) -> dict[str, Any]:
        if state is None:
            return {}
        constraints: dict[str, Any] = {}
        effect = str(state.get("requested_user_effect") or "").strip()
        operation = str(state.get("requested_operation") or "").strip()
        presentation = str(state.get("requested_result_kind") or "").strip()
        work_view = str(state.get("requested_work_view") or "").strip()
        if effect in {"read", "draft", "transform", "execute"}:
            constraints["user_effect"] = effect
            constraints["mutation_intent"] = {
                "read": "none",
                "draft": "private_draft",
                "transform": "transform_preview",
                "execute": "execute",
            }[effect]
            if effect != "read":
                constraints["loop_intent"] = "goal"
        if operation in {item.value for item in WorkOperation}:
            constraints["operation"] = operation
            if operation in {"test", "run", "complete", "capture"}:
                constraints["evidence_modes"] = ["execution_evidence"]
                constraints["evidence_scopes"] = ["operational"]
            if operation == "complete" and effect == "execute":
                # Completion is a reviewable Task execution preview. The
                # structured operation/effect owns this default, while an
                # explicit typed presentation below can still override it.
                constraints["presentation_intent"] = "artifact"
        if presentation in {"prose", "table", "timeline", "mermaid", "explorer", "artifact"}:
            constraints["presentation_intent"] = presentation
        perspectives = {
            "current": ["current"],
            "responsibility": ["responsibility"],
            "combined": ["current", "responsibility"],
        }.get(work_view)
        if perspectives is not None:
            constraints["work_perspectives"] = perspectives
        subject_refs = [
            str(item)
            for item in state.get("selected_subject_refs") or []
            if str(item).strip()
        ]
        if subject_refs:
            constraints["subject_refs"] = list(dict.fromkeys(subject_refs))
        return constraints

    def _planner_schema(
        self,
        state: QuickAgentState | None = None,
        *,
        validation_issues: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        plan_schema = semantic_plan_v4_schema(
            self.registry,
            trusted_context_refs=self._trusted_refs(state) if state is not None else [],
            prior_topic_entities=self._prior_entities(state) if state is not None else [],
            prior_focal_entities=self._prior_focal_entities(state) if state is not None else [],
            active_work_run=bool(state and state.get("active_work_run")),
        )
        constraints = self._verified_semantic_constraints(state)
        properties = plan_schema.get("properties") or {}
        for field in (
            "user_effect",
            "operation",
            "presentation_intent",
            "mutation_intent",
            "loop_intent",
        ):
            value = constraints.get(field)
            if value:
                properties.setdefault(field, {})["enum"] = [value]
        if "work_perspectives" in constraints:
            properties.setdefault("work_perspectives", {})["const"] = constraints[
                "work_perspectives"
            ]
            properties.setdefault("work_perspectives", {})["minItems"] = len(
                constraints["work_perspectives"]
            )
            properties.setdefault("work_perspectives", {})["maxItems"] = len(
                constraints["work_perspectives"]
            )
        evidence_properties = (
            properties.setdefault("evidence_requirements", {}).setdefault(
                "properties", {}
            )
        )
        if "evidence_modes" in constraints:
            evidence_properties.setdefault("modes", {})["const"] = constraints[
                "evidence_modes"
            ]
        if "evidence_scopes" in constraints:
            evidence_properties.setdefault("scopes", {})["const"] = constraints[
                "evidence_scopes"
            ]
        transform_destination_issue = next(
            (
                item
                for item in (validation_issues or [])
                if isinstance(item, dict)
                and str(item.get("code") or "")
                == "semantic.transform_destination_matches_input"
            ),
            None,
        )
        if transform_destination_issue is not None:
            details = (
                transform_destination_issue.get("details")
                if isinstance(transform_destination_issue.get("details"), dict)
                else {}
            )
            active_input_kind = str(details.get("active_input_kind") or "").strip()
            allowed_destinations = [
                item.value
                for item in WorkAssetKind
                if item.value != active_input_kind
            ]
            if active_input_kind and len(allowed_destinations) < len(WorkAssetKind):
                destination_schema = properties.setdefault("result_asset_kind", {})
                description = str(destination_schema.get("description") or "")
                properties["result_asset_kind"] = {
                    "type": "string",
                    "enum": allowed_destinations,
                    "description": description,
                }
        graph_focal_issue = next(
            (
                item
                for item in (validation_issues or [])
                if isinstance(item, dict)
                and str(item.get("code") or "")
                == "graph.focal_subject_missing"
            ),
            None,
        )
        if graph_focal_issue is not None:
            # SemanticPlanV4 owns subjects while the Catalog owns the graph
            # recipe.  A relation recipe compiled from an empty subject set
            # cannot execute, and merely repeating the same unconstrained
            # schema lets the one permitted repair return the same invalid
            # meaning.  Require one semantic subject only for this typed
            # repair error.  The existing ACL-bounded entity-ref enum still
            # prevents the planner from inventing an internal identity.
            properties.setdefault("subjects", {})["minItems"] = 1
        new_topic_prior_subject_issue = next(
            (
                item
                for item in (validation_issues or [])
                if isinstance(item, dict)
                and str(item.get("code") or "")
                == "topic.new_reuses_prior_subject"
            ),
            None,
        )
        if new_topic_prior_subject_issue is not None:
            # The first plan already established that the discourse action is
            # ``new``; its contradiction was resolving every subject to the
            # old focal set.  Keep that model-owned meaning fixed for the one
            # repair and remove only those stale identities from the bounded
            # subject vocabulary.  The planner can still name an unresolved
            # concept (entity_ref="") or choose another ACL-visible identity;
            # retrieval performs the actual entity resolution afterward.
            details = (
                new_topic_prior_subject_issue.get("details")
                if isinstance(new_topic_prior_subject_issue.get("details"), dict)
                else {}
            )
            stale_focal_refs = {
                str(item)
                for item in details.get("prior_focal_entities") or []
                if str(item)
            }
            properties.setdefault("topic_action", {})["enum"] = ["new"]
            properties.setdefault("reference_resolution", {})["enum"] = ["none"]
            subjects_schema = properties.setdefault("subjects", {})
            subjects_schema["minItems"] = 1
            subject_properties = (
                subjects_schema.setdefault("items", {}).setdefault(
                    "properties", {}
                )
            )
            entity_ref_schema = subject_properties.setdefault("entity_ref", {})
            allowed_refs = [
                str(item)
                for item in entity_ref_schema.get("enum") or []
                if not str(item) or str(item) not in stale_focal_refs
            ]
            entity_ref_schema["enum"] = list(dict.fromkeys(allowed_refs or [""]))
        return {
            "title": "BoISemanticPlanV4",
            "x-boi-call-type": "planner",
            "x-boi-max-output-tokens": 1_024,
            "type": "object",
            "required": ["semantic_plan"],
            "properties": {
                "semantic_plan": plan_schema,
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
        values: list[str] = []
        if isinstance(topic, dict):
            structured_values = [
                *(topic.get("subjects") or []),
                *(topic.get("result_entities") or []),
                *(topic.get("artifact_entities") or []),
            ]
            source_values = structured_values if structured_values else topic.get("entities") or []
            values.extend(str(item) for item in source_values if str(item).strip())
        if isinstance(active_artifact, dict) and str(active_artifact.get("artifact_id") or "").strip():
            values.append(str(active_artifact["artifact_id"]))
        return list(dict.fromkeys(values))

    @staticmethod
    def _prior_focal_entities(state: QuickAgentState) -> list[str]:
        conversation = state.get("conversation_context") or {}
        topic = conversation.get("topic_state") if isinstance(conversation, dict) else {}
        if not isinstance(topic, dict):
            return []
        subjects = [str(item) for item in topic.get("subjects") or [] if str(item).strip()]
        if subjects:
            return list(dict.fromkeys(subjects))
        return list(
            dict.fromkeys(
                str(item)
                for item in topic.get("entities") or []
                if str(item).strip()
            )
        )

    @staticmethod
    def _available_compile_context(state: QuickAgentState) -> set[str]:
        conversation = state.get("conversation_context") or {}
        active_artifact = (
            conversation.get("active_artifact")
            if isinstance(conversation, dict)
            else {}
        )
        available = (
            {"active_artifact"}
            if isinstance(active_artifact, dict)
            and str(active_artifact.get("artifact_id") or "").strip()
            else set()
        )
        topic_state = (
            conversation.get("topic_state")
            if isinstance(conversation, dict)
            and isinstance(conversation.get("topic_state"), dict)
            else {}
        )
        origin_capability_id = str(
            topic_state.get("origin_capability_id") or ""
        ).strip()
        if origin_capability_id:
            available.add(f"capability:{origin_capability_id}")
        return available

    @classmethod
    def _normalise_new_creation_subjects(
        cls,
        state: QuickAgentState,
        plan: SemanticPlan,
    ) -> SemanticPlan:
        if not (
            plan.topic_action == "new"
            and plan.operation == WorkOperation.create
            and plan.user_effect in {"draft", "transform"}
        ):
            return plan
        prior_refs = set(cls._prior_entities(state))
        if not prior_refs:
            return plan
        changed = False
        subjects = []
        for subject in plan.subjects:
            if subject.entity_ref and subject.entity_ref in prior_refs:
                subjects.append(
                    subject.model_copy(
                        update={"entity_ref": "", "resolution": "unresolved"}
                    )
                )
                changed = True
            else:
                subjects.append(subject)
        if not changed:
            return plan
        return plan.model_copy(update={"subjects": subjects})

    @staticmethod
    def _identity_tokens(value: str) -> list[str]:
        return [
            item.casefold()
            for item in re.findall(
                r"[A-Za-z][A-Za-z0-9._-]*|[0-9]+|[가-힣]+",
                value or "",
            )
            if len(item) > 1
        ]

    @classmethod
    def _identity_score(cls, mention: str, label: str) -> int:
        raise SemanticPlanningError("REFERENCE_SEMANTICS_UNRESOLVED", "Label overlap cannot establish reference identity.")

    @classmethod
    def _visible_identity_score(cls, mention: str, ref: str, title: str) -> int:
        raise SemanticPlanningError("REFERENCE_SEMANTICS_UNRESOLVED", "A visible label cannot establish selected reference identity.")

    @classmethod
    def _visible_identity_tokens(
        cls,
        ref: str,
        title: str,
    ) -> set[str]:
        ref_alias = " ".join(
            item
            for item in re.split(r"[:/._-]+", ref or "")
            if item
        )
        return {
            *cls._identity_tokens(title),
            *cls._identity_tokens(ref_alias),
        }

    @classmethod
    def _normalise_v4_subject_identities(
        cls,
        state: QuickAgentState,
        plan: SemanticPlanV4,
    ) -> tuple[SemanticPlanV4, dict[str, Any]]:
        """Check declared kinds without replacing refs by label similarity."""
        kinds = {str(x.get("ref")): str(x.get("kind")) for x in state.get("knowledge_hints") or [] if isinstance(x, dict) and x.get("ref") and x.get("kind")}
        kinds.update(state.get("trusted_entity_kinds") or {})
        for subject in plan.subjects:
            if subject.resolution == "resolved" and subject.entity_ref in kinds and subject.entity_kind != kinds[subject.entity_ref]:
                raise SemanticPlanningError("STRUCTURED_REFERENCE_TYPE_MISMATCH", "Submitted reference kind differs from the current visible specification.")
        return plan, {"status": "unchanged", "changes": [], "policy": "submitted_refs_only"}

    def _normalise_v4_safe_contract_consistency(
        self,
        state: QuickAgentState,
        plan: SemanticPlanV4,
    ) -> tuple[SemanticPlanV4, dict[str, Any]]:
        """Validate explicit constraints; never infer or repair submitted meaning."""
        constraints = self._verified_semantic_constraints(state)
        for field, expected in constraints.items():
            if field == "subject_refs":
                actual = [x.entity_ref for x in plan.subjects if x.resolution == "resolved"]
                if set(actual) != set(expected):
                    raise SemanticPlanningError("STRUCTURED_PLAN_CONSTRAINT_MISMATCH", "Submitted subjects differ from the verified structured selection.")
                continue
            if field in {"evidence_modes", "evidence_scopes"}:
                actual = getattr(plan.evidence_requirements, "modes" if field == "evidence_modes" else "scopes")
            else:
                actual = getattr(plan, field)
            actual = actual.value if isinstance(actual, WorkOperation) else actual
            if actual != expected:
                raise SemanticPlanningError("STRUCTURED_PLAN_CONSTRAINT_MISMATCH", f"Submitted {field} conflicts with the verified structured request.")
        return plan, {"status": "unchanged", "changes": [], "policy": "submitted_plan_only"}

    @classmethod
    def _specific_prior_selection_is_verified(
        cls,
        state: QuickAgentState,
        plan: SemanticPlanV4,
        inherited: set[str],
        focal_refs: list[str],
    ) -> bool:
        """Only explicit structured selection can attest this shortcut."""
        selected = set(state.get("selected_subject_refs") or [])
        return plan.reference_resolution == "specific" and len(inherited) == 1 and inherited == selected

    def _raise_v4_structural_ambiguity(
        self,
        state: QuickAgentState,
        plan: SemanticPlanV4,
    ) -> None:
        """Turn an unresolved multi-focal continuation into a human interrupt."""

        focal_refs = self._prior_focal_entities(state)
        if len(focal_refs) < 2 or plan.topic_action not in {"continue", "new"}:
            return
        prior_set = set(self._prior_entities(state))
        inherited = {
            item.entity_ref
            for item in plan.subjects
            if item.resolution == "resolved" and item.entity_ref in prior_set
        }
        if plan.topic_action == "new":
            resolved_refs = {
                item.entity_ref
                for item in plan.subjects
                if item.resolution == "resolved" and item.entity_ref
            }
            inherited_focal_refs = resolved_refs.intersection(focal_refs)
            # A genuinely new subject is model-owned meaning.  Only intercept
            # the contradictory shape that selects previous focal identities
            # without any independently resolved new subject.  This keeps the
            # decision structural and ACL-bound; no request wording, capability,
            # or extra model review is used.
            # Prior result entities are deliberately not old focal identities:
            # promoting a result node to the next active topic is the normal
            # relationship-exploration flow.  Comparing with every prior
            # entity incorrectly rejected that flow as a stale-topic repair.
            if not inherited_focal_refs or resolved_refs - set(focal_refs):
                return
            full_prior_focal_set_reused = set(focal_refs).issubset(resolved_refs)
            if not full_prior_focal_set_reused and not self._specific_prior_selection_is_verified(
                state,
                plan,
                inherited_focal_refs,
                focal_refs,
            ):
                # A generic or otherwise unverified singular reference cannot
                # become a correction merely because the planner labelled it
                # `new`. Keep the user interrupt and verified choices used by
                # an equivalent `continue` plan.
                pass
            else:
                # A plan that declares a new topic but verifiably resolves only
                # to the old focal identities is internally contradictory. It
                # needs the one permitted planner repair, not a false choice
                # between identities the user already selected.
                issue = ValidationIssue(
                    code="topic.new_reuses_prior_subject",
                    field="subjects",
                    message="A new topic must identify a subject outside the prior focal set.",
                    details={"prior_focal_entities": list(focal_refs)},
                )
                raise SemanticPlanningError(
                    "planner_invalid",
                    "The new-topic plan reused only prior focal subjects.",
                    report=PlanValidationReport(
                        valid=False,
                        issues=[issue],
                        catalog_revision=self.registry.version,
                        planner_schema_revision=PLANNER_SCHEMA_REVISION,
                    ),
                )
        if plan.reference_resolution == "all" and set(focal_refs).issubset(inherited):
            return
        if self._specific_prior_selection_is_verified(
            state,
            plan,
            inherited,
            focal_refs,
        ):
            return
        conversation = state.get("conversation_context") or {}
        topic = conversation.get("topic_state") if isinstance(conversation, dict) else {}
        labels = topic.get("entity_labels") if isinstance(topic, dict) else {}
        choices = [
            {
                "entity_ref": ref,
                "label": str((labels or {}).get(ref) or ref),
            }
            for ref in focal_refs
        ]
        question = str(plan.clarification_question or "").strip()
        if not question:
            choice_text = "\n".join(f"- {item['label']}" for item in choices[:10])
            question = "어느 대상을 말씀하시는지 선택해주세요."
            if choice_text:
                question = f"{question}\n\n{choice_text}"
        issue = ValidationIssue(
            code="topic.ambiguous_singular_reference",
            field="reference_resolution",
            message="The request retained multiple focal subjects without a verified selection.",
            details={"candidates": choices},
        )
        raise SemanticPlanningError(
            "planner_invalid",
            "The follow-up reference needs clarification.",
            report=PlanValidationReport(
                valid=False,
                issues=[issue],
                catalog_revision=self.registry.version,
                planner_schema_revision=PLANNER_SCHEMA_REVISION,
            ),
            clarification_question=question,
        )

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
        conversation_context = (
            state.get("conversation_context")
            if isinstance(state.get("conversation_context"), dict)
            else {}
        )
        active_artifact = (
            conversation_context.get("active_artifact")
            if isinstance(conversation_context.get("active_artifact"), dict)
            else {}
        )
        active_artifact_ref = str(active_artifact.get("artifact_id") or "").strip()
        artifact_target_operations = {
            WorkOperation.refine,
            WorkOperation.validate,
            WorkOperation.test,
            WorkOperation.run,
            WorkOperation.promote,
        }
        subject_refs = list(
            dict.fromkeys(
                item
                for item in [
                    str(state.get("task_ref") or ""),
                    *[str(value) for value in (state.get("selected_subject_refs") or [])],
                    *(
                        [active_artifact_ref]
                        if active_artifact_ref
                        and (
                            operation in artifact_target_operations
                            or user_effect == "transform"
                        )
                        else []
                    ),
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
        prior_entities = self._prior_entities(state)
        selected_prior_refs = [
            ref for ref in subject_refs if ref in set(prior_entities)
        ]
        if selected_prior_refs:
            compatibility_plan = compiled.semantic_plan.model_copy(
                update={
                    "topic_action": "continue",
                    "reference_resolution": (
                        "specific" if len(selected_prior_refs) == 1 else "all"
                    ),
                }
            )
            compiled = self.compiler.compile(
                compatibility_plan,
                original_question=str(state.get("question") or ""),
                trusted_context_refs=set(self._trusted_refs(state)),
                prior_topic_entities=prior_entities,
                prior_focal_entities=self._prior_focal_entities(state),
                active_work_run=bool(state.get("active_work_run")),
            )
        compiled_v4 = self.compiler.compile_v4(
            parse_semantic_plan_v4(compiled.semantic_plan.model_dump(mode="json")),
            original_question=str(state.get("question") or ""),
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        )
        validation = self.compiler.validate_v4(
            compiled_v4.semantic_plan,
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        ).model_dump(mode="json")
        validation["catalog_compile"] = {
            "status": "compiled",
            "capability_id": compiled_v4.capability_id,
            "execution_plan_revision": compiled_v4.execution_plan.schema_revision,
            "compatibility_source": "semantic-plan/v3",
        }
        return {
            "capability_id": compiled_v4.capability_id,
            "semantic_plan": compiled_v4.compatibility_plan.model_dump(mode="json"),
            "semantic_plan_v4": compiled_v4.semantic_plan.model_dump(mode="json"),
            "execution_plan": compiled_v4.execution_plan.model_dump(mode="json"),
            "catalog_compile": {
                "status": "compiled",
                "policy": "capability_catalog_v4",
                "execution_plan_revision": compiled_v4.execution_plan.schema_revision,
                "capability_id": compiled_v4.capability_id,
            },
            "planner_context_manifest": {
                "schema_revision": "planner-context-manifest/v1",
                "selected_source_refs": [],
                "excluded_source_refs": [],
                "exclusion_reasons": {},
                "whole_item_selection": True,
                "model_call": "typed_command_bypass",
            },
            "plan_validation": validation,
            "work_intent": compiled_v4.work_intent.model_dump(mode="json"),
            "continuation": {"continue_active_run": False, "delta_kind": "none", "user_confirmation": False},
            "grounded_answer": None,
            "grounded_answer_diagnostics": {"repair": "typed_command_domain_result"},
            "safe_stop_after_repair": False,
            "route_source": source,
            "route_reason": "typed_command",
            "trace": [*(state.get("trace") or []), "semantic_plan:typed", "validate:passed", "compile"],
        }

    def _verified_context_plan(
        self,
        state: QuickAgentState,
        source: str,
    ) -> dict[str, Any]:
        """Compile a complete, server-verified typed target without a model call.

        The caller has already proved that the structured target is the same
        ACL-visible entity carried by the active surface. This method does not
        choose a capability from a route table: it materializes only the
        verified meaning fields and lets the V4 Catalog compiler select the
        unique compatible capability, pipeline, evidence policy, and approval
        contract.
        """

        constraints = self._verified_semantic_constraints(state)
        effect = str(constraints.get("user_effect") or "").strip()
        operation_value = str(constraints.get("operation") or "").strip()
        subject_refs = [
            str(item)
            for item in constraints.get("subject_refs") or []
            if str(item).strip()
        ]
        trusted_kinds = {
            str(ref): str(kind)
            for ref, kind in (state.get("trusted_entity_kinds") or {}).items()
            if str(ref).strip() and str(kind).strip()
        }
        trusted_refs = set(self._trusted_refs(state))
        if (
            effect not in {"read", "draft", "transform", "execute"}
            or operation_value not in {item.value for item in WorkOperation}
            or not subject_refs
            or any(ref not in trusted_refs or not trusted_kinds.get(ref) for ref in subject_refs)
        ):
            raise SemanticPlanningError(
                "typed_command_invalid",
                "The verified surface command is missing a typed effect, operation, or target.",
            )
        presentation = str(constraints.get("presentation_intent") or "").strip()
        if presentation not in {
            "prose",
            "table",
            "timeline",
            "mermaid",
            "explorer",
            "artifact",
        }:
            presentation = "prose" if effect == "read" else "artifact"
        mutation_intent = str(constraints.get("mutation_intent") or "none")
        loop_intent = str(constraints.get("loop_intent") or "turn")
        evidence_modes = list(
            constraints.get("evidence_modes") or ["authoritative_knowledge"]
        )
        evidence_scopes = list(constraints.get("evidence_scopes") or ["canonical"])
        goal = str(state.get("question") or "").strip()
        plan = SemanticPlanV4(
            resolved_goal=goal,
            retrieval_query=goal,
            topic_action="new",
            reference_resolution="none",
            subjects=[
                SemanticSubject(
                    mention=ref,
                    entity_ref=ref,
                    entity_kind=trusted_kinds[ref],
                    resolution="resolved",
                )
                for ref in subject_refs
            ],
            user_effect=effect,
            operation=WorkOperation(operation_value),
            work_perspectives=list(constraints.get("work_perspectives") or []),
            presentation_intent=presentation,
            evidence_requirements=SemanticEvidenceRequirements(
                scopes=evidence_scopes,
                modes=evidence_modes,
            ),
            mutation_intent=mutation_intent,
            loop_intent=loop_intent,
            confidence=1.0,
        )
        plan, meaning_normalization = self._normalise_v4_safe_contract_consistency(
            state,
            plan,
        )
        plan, identity_resolution = self._normalise_v4_subject_identities(
            state,
            plan,
        )
        compiled = self.compiler.compile_v4(
            plan,
            original_question=goal,
            trusted_context_refs=trusted_refs,
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
            available_context=self._available_compile_context(state),
        )
        validation = self.compiler.validate_v4(
            compiled.semantic_plan,
            trusted_context_refs=trusted_refs,
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        ).model_dump(mode="json")
        validation["catalog_compile"] = {
            "status": "compiled",
            "capability_id": compiled.capability_id,
            "execution_plan_revision": compiled.execution_plan.schema_revision,
            "compatibility_source": "verified_typed_context",
        }
        validation["identity_resolution"] = identity_resolution
        validation["meaning_normalization"] = meaning_normalization
        return {
            "capability_id": compiled.capability_id,
            "semantic_plan": compiled.compatibility_plan.model_dump(mode="json"),
            "semantic_plan_v4": compiled.semantic_plan.model_dump(mode="json"),
            "execution_plan": compiled.execution_plan.model_dump(mode="json"),
            "catalog_compile": {
                "status": "compiled",
                "policy": "capability_catalog_v4",
                "execution_plan_revision": compiled.execution_plan.schema_revision,
                "capability_id": compiled.capability_id,
            },
            "planner_context_manifest": {
                "schema_revision": "planner-context-manifest/v1",
                "selected_source_refs": [],
                "excluded_source_refs": [],
                "exclusion_reasons": {},
                "trusted_target_refs": subject_refs,
                "whole_item_selection": True,
                "model_call": "verified_typed_context_bypass",
            },
            "plan_validation": validation,
            "planner_repair": {"attempted": False, "reason": ""},
            "work_intent": compiled.work_intent.model_dump(mode="json"),
            "continuation": compiled.semantic_plan.continuation_delta.model_dump(mode="json"),
            "grounded_answer": None,
            "grounded_answer_diagnostics": {
                "repair": "typed_command_domain_result"
            },
            "safe_stop_after_repair": False,
            "route_source": source,
            "route_reason": "verified_typed_context",
            "trace": [
                *(state.get("trace") or []),
                "semantic_plan:verified_typed_context",
                "validate:passed",
                "catalog:compiled",
                "compile",
            ],
        }

    @staticmethod
    def _planner_system(*, repair: bool = False) -> str:
        base = (
            "You are the BoI Semantic Planner. Return one SemanticPlanV4 object and state every schema field. "
            "Use the JSON schema descriptions and enum values for field meanings. Decide meaning only: complete resolved_goal, standalone "
            "retrieval_query, subjects, desired result asset, discourse, effect, operation, perspectives, presentation, evidence, mutation, "
            "and loop intent. Never choose capability, handler, connector, tool, work_view, graph recipe, readiness, "
            "approval, or budgets; the Catalog compiler owns runtime choices. Never route from isolated keywords.\n"
            "Trust: resolve refs only from trusted_entities or trusted_context_refs. Never invent refs, permissions, "
            "assignments, roles, authority, or state. External knowledge is not business evidence. Keep every named "
            "subject once and in user order. Each subject.mention must be only the exact concise entity or concept "
            "label named by the user, never the full question, an instruction, or a paraphrased goal. "
            "current_selection is an exact server-verified selection from its "
            "source_ref; treat that source as explicit context and preserve it as a resolved subject unless the "
            "request explicitly replaces or excludes it.\n"
            "Discourse: use verified_topic_state and conversation_turns only for reference resolution. Follow-ups must "
            "still produce standalone goals and queries. Corrections/new topics invalidate incompatible prior subjects. "
            "When the user explicitly replaces a prior subject with a named correction, set topic_action=new and "
            "reference_resolution=none, retain the corrected turn's requested operation for the replacement subject, "
            "and do not ask the user which information they want about that already named replacement. "
            "specific means one verified selected subject; all means every focal subject; ambiguous means the user must "
            "choose and requires one short clarification_question.\n"
            "A pending source_policy user change changes admissible evidence, not the active topic. When the request "
            "keeps the verified focal subject, preserve topic_action=continue and rebuild the answer only from "
            "non-excluded sources. Never use an excluded source as evidence.\n"
            "Effects: information and visualization are read+none. A new editable definition is draft+create+private_draft. "
            "Converting selected evidence, an answer/result, or an artifact is transform+create/refine+transform_preview. "
            "An Action dry-run/execution preview is execute+test+execute; Task completion preview is execute+complete+execute. "
            "Inspecting an existing Action's inputs, effects, risks, or execution plan as a prerequisite to explicit "
            "confirmation or proceeding is also an Action execution preview, even when the user does not say dry-run. "
            "A request that only asks what the Action is or how its contract works remains read+understand. "
            "These are previews before runtime confirmation. test needs an existing Action or event/detector definition "
            "with sample input. Verified private provisional capture is draft+capture+private_draft. Activation and "
            "promotion require explicit requests. Artifact transforms are operations, not WorkRun progress.\n"
            "Result asset: active_artifact_input identifies the current input artifact and its typed kind; never "
            "treat that input kind as the requested output by default. Set result_asset_kind to the explicitly "
            "requested output domain (for example sop for an "
            "SOP draft, task when decomposing into Tasks, or business_event for an Event definition). It describes "
            "the destination result, not the input subjects, and never names a capability. An active artifact is an "
            "input: do not copy its kind by default. If an active SOP is decomposed into executable Tasks, keep the "
            "SOP as the resolved subject and set the result to task. Use null for reads and runtime execution.\n"
            "Operations and presentation: compare contrasts subjects; connect traverses verified relations and owns "
            "relationship paths, sequences, Mermaid, Timeline, and Explorer; validate checks evidence/provenance/usage; "
            "understand explains subjects independently without a relationship traversal. Presentation is part of the "
            "user's requested meaning: preserve an explicitly requested primary form exactly. When the request asks for "
            "both explanation and one structured form, select that structured form because prose can accompany it. A "
            "relationship or flow visualization is read+connect with the requested visualization presentation; never "
            "downgrade it to prose merely because resolved_goal also describes an explanation.\n"
            "Work/evidence: current is only active assignment; responsibility is only official responsibility; retain both "
            "when both are requested. Current time/content/latest and the currently selected Task, page, Event, or artifact "
            "identify context but never imply a current-work perspective. Outcome lineage and Agent/System usage are "
            "execution_evidence and never imply responsibility. Perspective examples: a Person's Task history, outcomes, "
            "WorkRun provenance, Agents, Systems, or usage records use []; a selected Task's triggering Event and Actions "
            "use []; active assigned work uses [current]; declared role or official responsibility uses [responsibility]; "
            "a request for both active assignment and official responsibility uses [current, responsibility]. Use current_work only "
            "for assignments, historical_cases for prior cases, relationship_provenance for graph relations, "
            "execution_evidence for verified Task/Action/WorkRun outcomes and Agent/System usage, and "
            "authoritative_knowledge for reviewed facts. authority_scope follows the requested organizational claim "
            "(person/team/org/company), otherwise any; visibility is not authority. as_of is empty unless the user supplied "
            "an explicit ISO-8601 value.\n"
            "Loops: ordinary answers, comparisons, cases, Mermaid and Explorer are turn. Active Task checkpoint/remaining "
            "work is goal without authorizing mutation. Other goal/time/proactive loops require explicit durable work. "
            "continue_active_run only records supplied progress, evidence, blocker, transition, or human input when no new "
            "artifact operation is requested."
        )
        if repair:
            return base + (
                " This is the only repair attempt. Preserve the complete request and correct only the reported V4 "
                "meaning fields. Do not add runtime fields, choose a capability, reduce the requested effect, or use "
                "clarification to escape a contract error."
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

    @staticmethod
    def _plan_fidelity_schema() -> dict[str, Any]:
        """Schema for an independent meaning-preservation review.

        The reviewer does not route or repair a plan. It only identifies
        semantic decisions that fail to preserve the complete user request.
        """

        fields = [
            "resolved_goal",
            "retrieval_query",
            "topic_action",
            "reference_resolution",
            "subjects",
            "capability_id",
            "user_effect",
            "operation",
            "evidence_scope",
            "presentation",
            "work_view",
            "graph_query",
            "answer_intent",
        ]
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "issues", "clarification_question"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["aligned", "misaligned", "ambiguous"],
                },
                "issues": {
                    "type": "array",
                    "maxItems": 12,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["field", "message"],
                        "properties": {
                            "field": {"type": "string", "enum": fields},
                            "message": {"type": "string", "maxLength": 500},
                        },
                    },
                },
                "clarification_question": {"type": "string", "maxLength": 240},
            },
        }

    def _validate_plan_fidelity(
        self,
        *,
        state: QuickAgentState,
        model: Any,
        plan: SemanticPlan,
    ) -> None:
        """Use a fresh model context to verify that the plan kept the request.

        This deliberately performs no Python interpretation of the question.
        The model owns the semantic judgment, while Python validates the
        bounded verdict and turns any issue into the existing one-shot repair
        path.
        """

        conversation = state.get("conversation_context") or {}
        conversation = conversation if isinstance(conversation, dict) else {}
        recent_messages = [
            item
            for item in (conversation.get("recent_messages") or [])[-6:]
            if isinstance(item, dict)
        ]
        selected_definition = next(
            (
                item
                for item in self._capability_catalog()
                if item.get("capability_id") == plan.capability_id
            ),
            {},
        )
        system = (
            "You are an independent semantic-plan fidelity evaluator. Compare the complete current request, "
            "verified conversation topic, and recent turns with the proposed SemanticPlan. Judge whether every "
            "requested subject, workplace perspective, user effect, operation, evidence scope, and result form "
            "is preserved. Use the supplied Capability Catalog contract as the only operation vocabulary. "
            "The work_view meanings are: current=active assignments only, responsibility=declared roles and "
            "verified recurring work only, combined=both perspectives kept distinct, none=no workplace "
            "perspective requested. A requested relationship traversal must not be reduced to a plain factual "
            "explanation, and a requested read must not become a mutation. Do not answer the request, retrieve "
            "facts, choose a replacement plan, or use keyword matching. Topic continuity is a semantic decision: "
            "when a follow-up keeps the verified focal subject and asks for another view, representation, time "
            "perspective, or relationship over that subject, topic_action must remain continue. topic_action may "
            "be new only when the request introduces a genuinely distinct subject; a deictic or pronominal "
            "reference must not be converted into a fresh synthetic topic. verified_topic_state.subjects is the "
            "complete authoritative focal set. When it contains multiple focal subjects, a reference that does not "
            "semantically distinguish one subject or explicitly select the whole set is genuinely ambiguous; a plan "
            "that silently selects one or all is not aligned. Supporting result_entities and artifact_entities do not "
            "become focal merely because they are present, but the request may explicitly select a prior result, "
            "artifact, relationship set, or ordered item. Return aligned only when the proposed "
            "plan preserves the complete meaning. Return misaligned with the affected plan fields when it omits "
            "or changes meaning. Return ambiguous only when the user genuinely has to choose between equally "
            "plausible subjects, with one short clarification question."
        )
        prompt = json.dumps(
            {
                "request": state.get("question") or "",
                "recent_turns": recent_messages,
                "verified_topic_state": conversation.get("topic_state") or {},
                "proposed_semantic_plan": plan.model_dump(mode="json"),
                "selected_capability_contract": selected_definition,
            },
            ensure_ascii=False,
        )
        try:
            scripted_evaluator = getattr(model, "evaluate_semantic_plan", None)
            assessment = (
                scripted_evaluator(system=system, prompt=prompt, schema=self._plan_fidelity_schema())
                if callable(scripted_evaluator)
                else model.generate_structured(
                    system=system,
                    prompt=prompt,
                    schema=self._plan_fidelity_schema(),
                )
            )
        except Exception as exc:
            raise SemanticPlanningError(
                "planner_invalid",
                f"Semantic-plan fidelity evaluation failed: {type(exc).__name__}: {exc}",
            ) from exc

        status = str((assessment or {}).get("status") or "")
        if status == "aligned":
            return

        raw_issues = [
            item
            for item in (assessment or {}).get("issues") or []
            if isinstance(item, dict)
        ]
        issues = [
            ValidationIssue(
                code="semantic.fidelity_mismatch",
                field=str(item.get("field") or "resolved_goal"),
                message=str(item.get("message") or "The plan did not preserve the complete request."),
                details={"assessment_status": status},
            )
            for item in raw_issues[:12]
        ]
        if not issues:
            issues = [
                ValidationIssue(
                    code=(
                        "semantic.request_ambiguous"
                        if status == "ambiguous"
                        else "semantic.fidelity_mismatch"
                    ),
                    field="resolved_goal",
                    message=(
                        "The request needs one clarification before it can be planned."
                        if status == "ambiguous"
                        else "The plan did not preserve the complete request."
                    ),
                    details={"assessment_status": status},
                )
            ]
        raise SemanticPlanningError(
            "planner_invalid",
            "Semantic plan failed independent fidelity evaluation.",
            report=PlanValidationReport(
                valid=False,
                issues=issues,
                catalog_revision=self.registry.version,
                planner_schema_revision=PLANNER_SCHEMA_REVISION,
            ),
            clarification_question=(
                str((assessment or {}).get("clarification_question") or "")
                if status == "ambiguous"
                else ""
            ),
        )

    @staticmethod
    def _requested_work_view(plan: SemanticPlan) -> str:
        perspectives = list(plan.work_perspectives)
        perspective_set = set(perspectives)
        if len(perspectives) != len(perspective_set):
            return ""
        return (
            "combined"
            if perspective_set == {"current", "responsibility"}
            else "current"
            if perspective_set == {"current"}
            else "responsibility"
            if perspective_set == {"responsibility"}
            else "none"
        )

    def _compile_work_view_contract(
        self,
        *,
        plan: SemanticPlan,
        requested_work_view: str,
    ) -> SemanticPlan:
        """Compile model-owned work perspectives through one deterministic Catalog contract."""

        candidates: list[tuple[Any, WorkOperation]] = []
        for definition in self.registry.all():
            if requested_work_view not in definition.work_views:
                continue
            if plan.user_effect not in definition.user_effects:
                continue
            if plan.presentation not in definition.presentations:
                continue
            if plan.evidence_scope not in definition.evidence_scopes:
                continue

            declared_operations = list(
                definition.work_view_operation_contracts.get(requested_work_view) or []
            )
            if not declared_operations:
                if definition.default_work_view != requested_work_view:
                    continue
                declared_operations = list(definition.semantic_operations)
            compatible_operations: list[WorkOperation] = []
            for operation in declared_operations:
                contract = definition.semantic_operation_contracts.get(operation)
                if (
                    contract is not None
                    and contract.presentations
                    and plan.presentation not in contract.presentations
                ):
                    continue
                if requested_work_view in {"responsibility", "combined"} and (
                    contract is None or "responsibility" not in contract.graph_query_kinds
                ):
                    continue
                compatible_operations.append(operation)
            if not compatible_operations:
                continue

            preferred = (
                plan.operation
                if plan.capability_id == definition.capability_id
                and plan.operation in compatible_operations
                else definition.default_operation
                if definition.default_operation in compatible_operations
                else compatible_operations[0]
            )
            candidates.append((definition, preferred))

        if len(candidates) != 1:
            issue = ValidationIssue(
                code="semantic.work_view_contract_ambiguous",
                field="work_view",
                message="The Catalog does not identify exactly one executable contract for the reviewed work view.",
                details={
                    "work_view": requested_work_view,
                    "candidates": [definition.capability_id for definition, _ in candidates],
                },
            )
            raise SemanticPlanningError(
                "planner_invalid",
                "Reviewed work view could not be compiled through one Catalog contract.",
                report=PlanValidationReport(
                    valid=False,
                    issues=[issue],
                    catalog_revision=self.registry.version,
                    planner_schema_revision=PLANNER_SCHEMA_REVISION,
                ),
            )

        definition, operation = candidates[0]
        graph_query = None
        if requested_work_view in {"responsibility", "combined"}:
            focal_mentions = list(
                dict.fromkeys(
                    [
                        *[
                            subject.entity_ref
                            for subject in plan.subjects
                            if subject.entity_ref
                        ],
                        *([plan.target_ref] if plan.target_ref else []),
                    ]
                )
            )
            if not focal_mentions:
                focal_mentions = list(
                    dict.fromkeys(
                        subject.mention
                        for subject in plan.subjects
                        if subject.mention
                    )
                )
            if not focal_mentions:
                issue = ValidationIssue(
                    code="graph.focal_subject_missing",
                    field="graph_query.focal_mentions",
                    message="A reviewed responsibility view requires one selected semantic subject.",
                )
                raise SemanticPlanningError(
                    "planner_invalid",
                    "Reviewed responsibility view has no selected subject.",
                    report=PlanValidationReport(
                        valid=False,
                        issues=[issue],
                        catalog_revision=self.registry.version,
                        planner_schema_revision=PLANNER_SCHEMA_REVISION,
                    ),
                )
            graph_presentation = (
                plan.presentation
                if plan.presentation in {"table", "timeline", "mermaid", "explorer"}
                else "auto"
            )
            graph_query = GraphQueryDraft(
                enabled=True,
                query_kind="responsibility",
                focal_mentions=focal_mentions[:20],
                target_mentions=[],
                node_kinds=[],
                relation_kinds=[],
                direction="both",
                depth=2,
                presentation=graph_presentation,
            )

        return parse_semantic_plan(
            {
                **plan.model_dump(mode="json"),
                "capability_id": definition.capability_id,
                "operation": operation.value,
                "work_perspectives": (
                    ["current", "responsibility"]
                    if requested_work_view == "combined"
                    else [requested_work_view]
                    if requested_work_view in {"current", "responsibility"}
                    else []
                ),
                "work_view": requested_work_view,
                "graph_query": graph_query.model_dump(mode="json") if graph_query else None,
                "loop_contract": definition.default_loop_contract.model_dump(mode="json"),
            }
        )

    def _compile_planned_work_view(
        self,
        *,
        plan: SemanticPlan,
    ) -> tuple[SemanticPlan, dict[str, Any]]:
        requested_work_view = self._requested_work_view(plan)
        if not requested_work_view or requested_work_view == "none":
            return plan, {"attempted": False, "work_view": requested_work_view or "invalid"}
        original_payload = plan.model_dump(mode="json")
        compiled_plan = self._compile_work_view_contract(
            plan=plan,
            requested_work_view=requested_work_view,
        )
        compiled_payload = compiled_plan.model_dump(mode="json")
        changed_fields = sorted(
            field
            for field in SemanticPlan.model_fields
            if original_payload.get(field) != compiled_payload.get(field)
        )
        return compiled_plan, {
            "attempted": True,
            "policy": "catalog_work_view_contract",
            "status": "corrected" if changed_fields else "aligned",
            "work_view": requested_work_view,
            "changed_fields": changed_fields,
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
        all_hints = [
            {
                key: item.get(key)
                for key in ("ref", "title", "kind", "answer_scope", "authority", "is_primary")
                if item.get(key) is not None
            }
            for item in (state.get("knowledge_hints") or [])
            if isinstance(item, dict)
        ]
        hints = all_hints[:PLANNER_SUBJECT_HINT_LIMIT]
        hint_limit_excluded_refs = {
            str(item.get("ref") or "")
            for item in all_hints[PLANNER_SUBJECT_HINT_LIMIT:]
            if str(item.get("ref") or "")
        }
        conversation = state.get("conversation_context") or {}
        verified_topic_state = self._planner_topic_state(conversation)
        conversation_turns = [
            item
            for item in (
                conversation.get("recent_messages")
                if isinstance(conversation, dict)
                else []
            ) or []
            if isinstance(item, dict)
        ]
        all_hint_refs = [
            str(item.get("ref") or "")
            for item in all_hints
            if str(item.get("ref") or "")
        ]
        original_turn_count = len(conversation_turns)
        verified_command_constraints = self._verified_semantic_constraints(state)
        # Semantic planning receives metadata, not source bodies. Keep the
        # planner slice bounded so the request-wide 16k input contract leaves
        # room for the one answer call.
        context_token_budget = min(
            PLANNER_CONTEXT_TOKEN_LIMIT,
            max(
                1,
                int(
                    state.get("context_token_budget")
                    or PLANNER_CONTEXT_TOKEN_LIMIT
                ),
            ),
        )
        if context_token_budget:
            fixed_payload = {
                "request": state.get("question") or "",
                "current_page": {
                    "kind": state.get("page_kind") or "library",
                    "ref": state.get("page_ref") or "",
                    "title": state.get("page_title") or "",
                },
                "current_selection": state.get("current_selection") or {},
                "source_policy": state.get("source_policy_context") or {},
                "active_work": {
                    "title": state.get("active_artifact_title") or "",
                    "input_artifact": state.get("active_artifact_input") or {},
                    "task_ref": state.get("task_ref") or "",
                    "work_run": state.get("active_work_run") or {},
                },
                "verified_topic_state": verified_topic_state,
                "trusted_context_refs": self._trusted_refs(state),
                "trusted_entities": dict(state.get("trusted_targets") or {}),
                "trusted_entity_kinds": dict(state.get("trusted_entity_kinds") or {}),
                "verified_command_constraints": verified_command_constraints,
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
            selected_hints: list[dict[str, Any]] = []
            identity_reservation_overflow_tokens = 0
            # Reserve one whole, highest-ranked source metadata item before a
            # long prior turn. Without a source identity the planner cannot
            # bind the subject, while the raw source body is already excluded.
            # The reservation remains subject to the hard input budget: an
            # item that does not fit is excluded in full.
            if hints:
                first_hint_cost = item_tokens(hints[0])
                if first_hint_cost <= remaining_tokens:
                    selected_hints.append(hints[0])
                    remaining_tokens -= first_hint_cost
            latest_turns = conversation_turns[-2:]
            for item in latest_turns:
                cost = item_tokens(item)
                if cost <= remaining_tokens:
                    selected_turns.append(item)
                    remaining_tokens -= cost

            for item in hints[len(selected_hints):]:
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
        selected_hint_refs = [
            str(item.get("ref") or "") for item in hints if str(item.get("ref") or "")
        ]
        excluded_hint_refs = [
            ref for ref in all_hint_refs if ref not in set(selected_hint_refs)
        ]
        return {
            "request": state.get("question") or "",
            "current_page": {
                "kind": state.get("page_kind") or "library",
                "ref": state.get("page_ref") or "",
                "title": state.get("page_title") or "",
            },
            "current_selection": state.get("current_selection") or {},
            "source_policy": state.get("source_policy_context") or {},
            "active_work": {
                "title": state.get("active_artifact_title") or "",
                "input_artifact": state.get("active_artifact_input") or {},
                "task_ref": state.get("task_ref") or "",
                "work_run": state.get("active_work_run") or {},
            },
            "verified_topic_state": verified_topic_state,
            "conversation_turns": conversation_turns,
            "trusted_context_refs": self._trusted_refs(state),
            "trusted_entities": dict(state.get("trusted_targets") or {}),
            "trusted_entity_kinds": dict(state.get("trusted_entity_kinds") or {}),
            "verified_command_constraints": verified_command_constraints,
            "visible_subject_hints": planner_hints,
            "catalog_revision": self.registry.version,
            "planner_schema_revision": PLANNER_SCHEMA_REVISION,
            "invalid_output": invalid_output or {},
            "validation_issues": validation_issues or [],
            "_context_manifest": {
                "schema_revision": "planner-context-manifest/v1",
                "selected_source_refs": selected_hint_refs,
                "excluded_source_refs": excluded_hint_refs,
                "exclusion_reasons": {
                    ref: (
                        "planner_hint_limit"
                        if ref in hint_limit_excluded_refs
                        else "planner_input_budget"
                    )
                    for ref in excluded_hint_refs
                },
                "selected_turn_count": len(conversation_turns),
                "excluded_turn_count": original_turn_count - len(conversation_turns),
                "token_budget": context_token_budget,
                "identity_reservation_overflow_tokens": (
                    identity_reservation_overflow_tokens
                ),
                "whole_item_selection": True,
                "raw_source_content": bool(
                    (state.get("current_selection") or {}).get("text")
                ),
                "explicit_user_selection": bool(
                    (state.get("current_selection") or {}).get("text")
                ),
            },
        }

    @staticmethod
    def _planner_topic_state(conversation: Any) -> dict[str, Any]:
        raw = conversation.get("topic_state") if isinstance(conversation, dict) else {}
        if not isinstance(raw, dict):
            return {}
        if not any(
            raw.get(key)
            for key in (
                "topic_state_ref",
                "subject",
                "subjects",
                "result_entities",
                "artifact_entities",
                "entities",
                "claims",
                "used_source_refs",
                "active_artifact_id",
            )
        ):
            return {}
        subjects = [str(item) for item in raw.get("subjects") or [] if str(item)][:12]
        results = [str(item) for item in raw.get("result_entities") or [] if str(item)][:12]
        artifacts = [str(item) for item in raw.get("artifact_entities") or [] if str(item)][:8]
        entities = list(dict.fromkeys([*subjects, *results, *artifacts]))
        labels = raw.get("entity_labels") if isinstance(raw.get("entity_labels"), dict) else {}
        # The semantic planner needs the verified claim bindings to know that
        # a previous answer was grounded, but it must not receive the claim
        # bodies again.  Source text belongs to the later answer call.  Keeping
        # only typed identity/provenance fields prevents a continuation from
        # evicting its highest-ranked source hint under the 4k planner slice.
        claims = [
            {
                key: copy.deepcopy(item.get(key))
                for key in (
                    "claim_id",
                    "claim_kind",
                    "source_scope",
                    "source_refs",
                    "supporting_chunk_ids",
                    "support_status",
                    "required_for_answer",
                )
                if item.get(key) is not None
            }
            for item in raw.get("claims") or []
            if isinstance(item, dict)
        ][:12]
        used_source_refs = [str(item) for item in raw.get("used_source_refs") or [] if str(item)][:12]
        return {
            "topic_state_ref": str(raw.get("topic_state_ref") or ""),
            "subject": str(raw.get("subject") or ""),
            "subjects": subjects,
            "result_entities": results,
            "result_count": len(raw.get("result_entities") or []),
            "result_entities_truncated": len(raw.get("result_entities") or []) > len(results),
            "artifact_entities": artifacts,
            "entities": entities,
            "entity_labels": {
                ref: str(labels.get(ref) or ref)
                for ref in entities
            },
            "topic_structure": raw.get("topic_structure") or "single_focal",
            "topic_primary_subject_count": int(
                raw.get("topic_primary_subject_count") or 0
            ),
            "ordinal_reference_scope": str(
                raw.get("ordinal_reference_scope") or "auto"
            ),
            "origin_capability_id": str(raw.get("origin_capability_id") or ""),
            "operation": str(raw.get("operation") or ""),
            "answer_intent": str(raw.get("answer_intent") or ""),
            "answer_source_scope": str(raw.get("answer_source_scope") or ""),
            "claims": claims,
            "claim_count": len(raw.get("claims") or []),
            "claims_truncated": len(raw.get("claims") or []) > len(claims),
            "used_source_refs": used_source_refs,
            "active_artifact_id": str(raw.get("active_artifact_id") or ""),
            "correction_status": str(raw.get("correction_status") or "active"),
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
        self._validate_collective_reference_semantics(state=state, model=model, plan=plan)

    def _validate_collective_reference_semantics(
        self,
        *,
        state: QuickAgentState,
        model: Any,
        plan: SemanticPlan,
    ) -> None:
        """Require explicit reference scope; no singular/collective keyword gate."""
        prior = set(self._prior_entities(state))
        if plan.topic_action != "continue" or len(prior) < 2:
            return
        inherited = {x.entity_ref for x in plan.subjects if x.resolution == "resolved" and x.entity_ref in prior}
        selected = set(state.get("selected_subject_refs") or [])
        if inherited and selected == inherited and selected <= prior:
            return
        raise SemanticPlanningError("REFERENCE_SEMANTICS_UNRESOLVED", "의미 판단 불가: 복수의 이전 대상 중 선택을 입증하는 구조화된 참조가 필요합니다.")

    @staticmethod
    def _resolve_ordinal_request_text(question: str, selected_label: str) -> str:
        """Keep the exact request; never substitute an ordinal by regex."""
        return question

    @staticmethod
    def _ordinal_reference_index(text: str) -> int | None:
        """Natural-language ordinals are agent-owned meaning, not local authority."""
        return None

    def _validate_envelope(
        self,
        state: QuickAgentState,
        envelope: dict[str, Any],
        *,
        model: Any,
        allow_model_evaluations: bool = True,
    ) -> tuple[SemanticPlan, dict[str, Any]]:
        raw_plan = dict(envelope.get("semantic_plan") or {}) if isinstance(envelope.get("semantic_plan"), dict) else {}
        legacy_continuation = envelope.get("continuation")
        if "continuation" not in raw_plan and isinstance(legacy_continuation, dict):
            raw_plan["continuation"] = legacy_continuation
        plan = self._normalise_new_creation_subjects(
            state,
            parse_semantic_plan(raw_plan),
        )
        # Multi-focal singular anaphora is a user decision regardless of which
        # candidate set the planner happened to encode. Detect it before field
        # validation so an incomplete all/specific selection cannot turn a
        # clear needs-input outcome into a generic planner failure.
        self._validate_collective_reference_semantics(
            state=state,
            model=model,
            plan=plan,
        )
        self._validate_requested_graph_filters(state, plan)
        report = self.validator.validate(
            plan,
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        )
        if not report.valid:
            raise SemanticPlanningError(
                "planner_invalid",
                "Semantic plan failed validation.",
                report=report,
                clarification_question=plan.clarification_question,
            )
        # A production gateway must not turn a second, variable semantic
        # judgment into a planner failure after the catalog validator has
        # accepted the plan. Explicit review gateways and injected test
        # evaluators can still opt into the independent fidelity check by
        # exposing evaluate_semantic_plan().
        fidelity_evaluator = getattr(model, "evaluate_semantic_plan", None)
        fidelity_reviewed = allow_model_evaluations and callable(fidelity_evaluator)
        if fidelity_reviewed:
            self._validate_plan_fidelity(state=state, model=model, plan=plan)
        if allow_model_evaluations:
            self._validate_specific_reference_semantics(state=state, model=model, plan=plan)
        payload = report.model_dump(mode="json")
        payload["fidelity_review"] = "independent" if fidelity_reviewed else "catalog_contract"
        return plan, payload

    def _validate_v4_envelope(
        self,
        state: QuickAgentState,
        envelope: dict[str, Any],
    ) -> tuple[Any, dict[str, Any]]:
        raw_plan = (
            dict(envelope.get("semantic_plan") or {})
            if isinstance(envelope.get("semantic_plan"), dict)
            else {}
        )
        parsed = parse_semantic_plan_v4(raw_plan)
        self._validate_collective_reference_semantics(state=state, model=None, plan=parsed.plan)
        normalised_plan, identity_resolution = self._normalise_v4_subject_identities(
            state,
            parsed.plan,
        )
        normalised_plan, meaning_normalization = self._normalise_v4_safe_contract_consistency(
            state,
            normalised_plan,
        )
        post_consistency_plan, post_consistency_identity = (
            self._normalise_v4_subject_identities(state, normalised_plan)
        )
        if post_consistency_plan != normalised_plan:
            normalised_plan = post_consistency_plan
            identity_resolution = {
                "status": "resolved",
                "changes": [
                    *list(identity_resolution.get("changes") or []),
                    *list(post_consistency_identity.get("changes") or []),
                ],
            }
        active_artifact_input = (
            state.get("active_artifact_input")
            if isinstance(state.get("active_artifact_input"), dict)
            else {}
        )
        active_artifact_ref = str(
            active_artifact_input.get("ref") or ""
        ).strip()
        active_artifact_kind = str(
            (state.get("trusted_entity_kinds") or {}).get(active_artifact_ref)
            or ""
        ).strip()
        active_artifact_is_subject = any(
            subject.resolution == "resolved"
            and subject.entity_ref == active_artifact_ref
            for subject in normalised_plan.subjects
        )
        if (
            normalised_plan.user_effect == "transform"
            and active_artifact_ref
            and active_artifact_kind
            and active_artifact_is_subject
            and normalised_plan.result_asset_kind is not None
            and normalised_plan.result_asset_kind.value == active_artifact_kind
        ):
            # Transform is the cross-asset preview contract. Same-kind editing
            # remains draft+refine. Rejecting this redundant input/output pair
            # lets the one permitted planner repair select the requested
            # destination without a keyword router or a second capability
            # reviewer.
            issue = ValidationIssue(
                code="semantic.transform_destination_matches_input",
                field="result_asset_kind",
                message=(
                    "A transform destination must differ from the active input asset. "
                    "Use draft+refine for same-kind editing, or set result_asset_kind "
                    "to the distinct output domain requested by the user."
                ),
                details={
                    "active_input_ref": active_artifact_ref,
                    "active_input_kind": active_artifact_kind,
                    "invalid_result_asset_kind": normalised_plan.result_asset_kind.value,
                },
            )
            raise SemanticPlanningError(
                "planner_invalid",
                "Semantic transform has no distinct destination asset.",
                report=PlanValidationReport(
                    valid=False,
                    issues=[issue],
                    catalog_revision=self.registry.version,
                    planner_schema_revision=PLANNER_SCHEMA_REVISION,
                ),
            )
        self._raise_v4_structural_ambiguity(state, normalised_plan)
        parsed = parsed.__class__(
            plan=normalised_plan,
            compatibility=parsed.compatibility,
        )
        compiled = self.compiler.compile_v4(
            parsed,
            original_question=str(state.get("question") or ""),
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
            available_context=self._available_compile_context(state),
        )
        # All checks after V4 planning are deterministic. In particular, a
        # valid plan never triggers a second work-view, capability, or discourse
        # model review.
        report = self.compiler.validate_v4(
            compiled.semantic_plan,
            trusted_context_refs=set(self._trusted_refs(state)),
            prior_topic_entities=self._prior_entities(state),
            prior_focal_entities=self._prior_focal_entities(state),
            active_work_run=bool(state.get("active_work_run")),
        ).model_dump(mode="json")
        report["catalog_compile"] = {
            "status": "compiled",
            "capability_id": compiled.capability_id,
            "execution_plan_revision": compiled.execution_plan.schema_revision,
            "compatibility_source": parsed.compatibility.get("source_schema_revision") or "",
        }
        report["fidelity_review"] = "catalog_contract"
        report["identity_resolution"] = identity_resolution
        report["meaning_normalization"] = meaning_normalization
        return compiled, report

    def _validate_requested_graph_filters(
        self,
        state: QuickAgentState,
        plan: SemanticPlan,
    ) -> None:
        graph = plan.graph_query
        if graph is None or not graph.enabled:
            return
        allowed_nodes = set(state.get("requested_graph_node_kinds") or [])
        allowed_relations = set(state.get("requested_graph_relation_kinds") or [])
        unexpected_nodes = sorted(set(graph.node_kinds) - allowed_nodes)
        unexpected_relations = sorted(set(graph.relation_kinds) - allowed_relations)
        issues: list[ValidationIssue] = []
        if unexpected_nodes:
            issues.append(
                ValidationIssue(
                    code="graph.node_filter_not_requested",
                    field="graph_query.node_kinds",
                    message="Graph node filters must come from verified command constraints.",
                    details={"unexpected": unexpected_nodes, "allowed": sorted(allowed_nodes)},
                )
            )
        if unexpected_relations:
            issues.append(
                ValidationIssue(
                    code="graph.relation_filter_not_requested",
                    field="graph_query.relation_kinds",
                    message="Graph relation filters must come from verified command constraints.",
                    details={
                        "unexpected": unexpected_relations,
                        "allowed": sorted(allowed_relations),
                    },
                )
            )
        if issues:
            raise SemanticPlanningError(
                "planner_invalid",
                "Semantic plan added an unrequested graph filter.",
                report=PlanValidationReport(
                    valid=False,
                    issues=issues,
                    catalog_revision=self.registry.version,
                    planner_schema_revision=PLANNER_SCHEMA_REVISION,
                ),
            )

    @staticmethod
    def _resolve_grounded_answer(
        envelope: dict[str, Any],
        plan: SemanticPlan,
        hints: list[dict[str, Any]],
        evidence_requirements: SemanticEvidenceRequirements | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        evidence_requirements = evidence_requirements or SemanticEvidenceRequirements()
        allowed_evidence_scopes = {
            str(scope)
            for scope in evidence_requirements.scopes
            if str(scope) in {"canonical", "operational", "validation"}
        } or {plan.evidence_scope}
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
                and str(item.get("answer_scope") or "canonical")
                in allowed_evidence_scopes
                for item in [*source_items, *chunk_items]
            )

        def bound_scope(refs: list[str], chunks: list[str]) -> str:
            """Derive claim scope from trusted source metadata, never model labels."""

            items = [by_ref.get(ref) for ref in refs]
            items.extend(by_chunk.get(chunk) for chunk in chunks)
            if not items or any(not isinstance(item, dict) for item in items):
                return ""
            scopes = {
                str(item.get("answer_scope") or "canonical")
                for item in items
                if isinstance(item, dict)
            }
            return next(iter(scopes)) if len(scopes) == 1 else ""

        normalized_scope_claims = 0

        def resolution_diagnostics(
            *, accepted: bool, accepted_claims: int, rejected_claims: int
        ) -> dict[str, Any]:
            diagnostics = {
                "accepted": accepted,
                "accepted_claims": accepted_claims,
                "rejected_claims": rejected_claims,
            }
            if normalized_scope_claims:
                diagnostics["normalized_scope_claims"] = normalized_scope_claims
            return diagnostics

        claims: list[dict[str, Any]] = []
        unsupported_claims: list[dict[str, Any]] = [
            GroundedClaim(
                claim_id=f"claim-unresolved-{index}",
                text=str(item.get("text") or "").strip(),
                claim_kind=str(item.get("claim_kind") or plan.answer_intent),
                source_scope=str(item.get("source_scope") or plan.evidence_scope),
                source_refs=[],
                supporting_chunk_ids=[],
                support_status="unsupported",
                required_for_answer=bool(item.get("required_for_answer", True)),
            ).model_dump(mode="json")
            for index, item in enumerate(raw.get("unresolved_claims") or [], start=1)
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
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
            raw_scope = str(raw_claim.get("source_scope") or plan.evidence_scope)
            scope = bound_scope(refs, chunks)
            if scope and scope != raw_scope:
                normalized_scope_claims += 1
            scope_matches = scope in allowed_evidence_scopes and refs_match_plan_scope(refs, chunks)
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
                                scope if scope in allowed_evidence_scopes else plan.evidence_scope
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
                    resolution_diagnostics(
                        accepted=False,
                        accepted_claims=len(claims),
                        rejected_claims=rejected,
                    ),
                )
            return None, resolution_diagnostics(
                accepted=False,
                accepted_claims=len(claims),
                rejected_claims=rejected,
            )

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
            resolution_diagnostics(
                accepted=True,
                accepted_claims=len(claims),
                rejected_claims=rejected,
            ),
        )

    def _repair_grounded_answer(
        self,
        *,
        model: Any,
        state: QuickAgentState,
        plan: SemanticPlan,
        evidence_requirements: SemanticEvidenceRequirements,
        hints: list[dict[str, Any]],
        diagnostics: dict[str, Any],
        answer_input_token_limit: int = 12_000,
        max_answer_sources: int = 100,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        # No lexical source-ranking repair may replace explicit evidence selection.
        return None, {"status": "blocked", "reason_code": "REFERENCE_SEMANTICS_UNRESOLVED", "automatic_retry": False}

    @staticmethod
    def _is_genuine_clarification_error(error: SemanticPlanningError) -> bool:
        if not error.clarification_question or error.report is None:
            return False
        ambiguity_codes = {
            "semantic.request_ambiguous",
            "topic.ambiguous_singular_reference",
        }
        return any(item.code in ambiguity_codes for item in error.report.issues)

    @classmethod
    def _terminal_clarification(cls, error: SemanticPlanningError) -> str:
        if cls._is_genuine_clarification_error(error):
            return error.clarification_question
        if error.clarification_question and error.report is not None and any(
            item.code == "topic.specific_reference_not_justified"
            for item in error.report.issues
        ):
            return error.clarification_question
        return ""

    def _plan(self, state: QuickAgentState) -> dict[str, Any]:
        offered = str(state.get("offered_capability") or "").strip()
        explicit = str(state.get("explicit_capability") or "").strip()
        if offered:
            return self._typed_plan(state, offered, "offer_id")
        if explicit:
            return self._typed_plan(state, explicit, "explicit")
        verified_typed_source = str(
            state.get("verified_typed_command_source") or ""
        ).strip()
        if verified_typed_source:
            return self._verified_context_plan(state, verified_typed_source)

        model = state.get("model")
        readiness = model.readiness() if model is not None and hasattr(model, "readiness") else {}
        if not readiness.get("generation"):
            raise SemanticPlanningError("planner_unavailable", "The local semantic planner is unavailable.")

        envelope: dict[str, Any] = {}
        first_error: SemanticPlanningError | None = None
        planner_repair: dict[str, Any] = {"attempted": False, "reason": ""}
        planner_context_manifest: dict[str, Any] = {}
        compiled: Any = None
        try:
            planner_payload = self._planner_payload(state)
            planner_context_manifest = dict(planner_payload.pop("_context_manifest", {}) or {})
            envelope = model.generate_structured(
                system=self._planner_system(),
                prompt=json.dumps(planner_payload, ensure_ascii=False),
                schema=self._planner_schema(state),
            )
            compiled, report = self._validate_v4_envelope(state, envelope)
        except ModelBudgetExceeded as exc:
            raise SemanticPlanningError(
                (
                    "planner_timeout"
                    if exc.budget_kind == "elapsed_time"
                    else "planner_budget_exceeded"
                ),
                str(exc),
            ) from exc
        except Exception as exc:
            first_error = exc if isinstance(exc, SemanticPlanningError) else SemanticPlanningError(
                "planner_invalid", f"{type(exc).__name__}: {exc}"
            )
            if first_error.code == "REFERENCE_SEMANTICS_UNRESOLVED":
                raise first_error
            if self._is_genuine_clarification_error(first_error):
                # Genuine ambiguity is a user decision, not a malformed plan
                # that another model pass should guess away.
                raise first_error
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
                repair_payload = self._planner_payload(
                    state,
                    invalid_output=envelope,
                    validation_issues=(
                        [item.model_dump(mode="json") for item in first_error.report.issues]
                        if first_error.report
                        else [{"code": first_error.code, "message": str(first_error)}]
                    ),
                )
                repair_context_manifest = dict(
                    repair_payload.pop("_context_manifest", {}) or {}
                )
                planner_context_manifest = {
                    **repair_context_manifest,
                    "attempts": [planner_context_manifest, repair_context_manifest],
                }
                repair_issues = (
                    [item.model_dump(mode="json") for item in first_error.report.issues]
                    if first_error.report
                    else [{"code": first_error.code, "message": str(first_error)}]
                )
                repaired = model.generate_structured(
                    system=self._planner_system(repair=True),
                    prompt=json.dumps(repair_payload, ensure_ascii=False),
                    schema=self._planner_schema(
                        state,
                        validation_issues=repair_issues,
                    ),
                )
                raw_repaired_plan = (
                    dict(repaired.get("semantic_plan") or {})
                    if isinstance(repaired, dict)
                    and isinstance(repaired.get("semantic_plan"), dict)
                    else {}
                )
                envelope = repaired
                compiled, report = self._validate_v4_envelope(state, envelope)
            except ModelBudgetExceeded as repair_exc:
                raise SemanticPlanningError(
                    (
                        "planner_timeout"
                        if repair_exc.budget_kind == "elapsed_time"
                        else "planner_budget_exceeded"
                    ),
                    str(repair_exc),
                    report=first_error.report if first_error else None,
                ) from repair_exc
            except Exception as repair_exc:
                error = repair_exc if isinstance(repair_exc, SemanticPlanningError) else SemanticPlanningError(
                    "planner_invalid", f"{type(repair_exc).__name__}: {repair_exc}"
                )
                clarification = self._terminal_clarification(error) or (
                    self._terminal_clarification(first_error) if first_error else ""
                )
                raise SemanticPlanningError(
                    error.code,
                    str(error),
                    report=error.report or (first_error.report if first_error else None),
                    clarification_question=clarification,
                ) from repair_exc

        if compiled is None:
            raise SemanticPlanningError("planner_invalid", "SemanticPlanV4 was not compiled.")
        plan_v4: SemanticPlanV4 = compiled.semantic_plan
        plan: SemanticPlan = compiled.compatibility_plan
        catalog_compile = {
            "status": "compiled",
            "policy": "capability_catalog_v4",
            "execution_plan_revision": compiled.execution_plan.schema_revision,
            "capability_id": compiled.capability_id,
        }
        hints = [item for item in (state.get("knowledge_hints") or []) if isinstance(item, dict)]
        grounded_answer, diagnostics = self._resolve_grounded_answer(
            envelope,
            plan,
            hints,
            plan_v4.evidence_requirements,
        )
        # A validated graph query is answered from the ACL-bounded graph
        # DomainResult and grounded again by the graph service. Repairing a
        # planner-authored prose answer here adds another model call whose
        # output is never used. Keep the one-shot repair for non-graph reads,
        # where the planner answer is the actual domain result.
        selected_definition = self.registry.get(compiled.capability_id)
        domain_result_is_authoritative = bool(
            (plan.graph_query and plan.graph_query.enabled)
            or selected_definition.handler != "grounded_read"
        )
        if (
            grounded_answer is None
            and not domain_result_is_authoritative
            and not planner_repair["attempted"]
            and plan_v4.topic_action != "clarify"
            and not bool(state.get("defer_grounded_answer"))
        ):
            grounded_answer, diagnostics = self._repair_grounded_answer(
                model=model,
                state=state,
                plan=plan,
                evidence_requirements=plan_v4.evidence_requirements,
                hints=hints,
                diagnostics=diagnostics,
                answer_input_token_limit=int(
                    selected_definition.handler_config.get("answer_input_tokens") or 12_000
                ),
                max_answer_sources=int(
                    selected_definition.handler_config.get("max_answer_sources") or 100
                ),
            )
        elif grounded_answer is None:
            diagnostics = {
                **diagnostics,
                "repair": (
                    "skipped_after_planner_repair"
                    if planner_repair["attempted"]
                    else
                    "deferred_to_graph_result"
                    if plan.graph_query and plan.graph_query.enabled
                    else "deferred_to_domain_result"
                ),
            }
        continuation = plan_v4.continuation_delta.model_dump(mode="json")
        return {
            "capability_id": compiled.capability_id,
            "semantic_plan": plan.model_dump(mode="json"),
            "semantic_plan_v4": plan_v4.model_dump(mode="json"),
            "execution_plan": compiled.execution_plan.model_dump(mode="json"),
            "catalog_compile": catalog_compile,
            "planner_context_manifest": planner_context_manifest,
            "plan_validation": report,
            "planner_repair": planner_repair,
            "work_intent": compiled.work_intent.model_dump(mode="json"),
            "continuation": continuation,
            "grounded_answer": grounded_answer,
            "grounded_answer_diagnostics": diagnostics,
            "clarification_question": plan_v4.clarification_question,
            # A single repaired plan that passes the same V4 validator and
            # Catalog compiler is executable. Only a failed repair stops; the
            # exception path above already handles that without falling back
            # to an arbitrary capability.
            "safe_stop_after_repair": False,
            "route_source": "llm_structured",
            "route_reason": "semantic_plan_validated",
            "trace": [
                *(state.get("trace") or []),
                "semantic_plan:llm",
                *(["semantic_plan:repair"] if planner_repair["attempted"] else []),
                "validate:passed",
                "catalog:compiled",
                *(
                    ["grounded_answer:graph_result"]
                    if diagnostics.get("repair") == "deferred_to_graph_result"
                    else ["grounded_answer:domain_result"]
                    if diagnostics.get("repair") == "deferred_to_domain_result"
                    else ["grounded_answer:repair"]
                    if diagnostics.get("repair")
                    else []
                ),
                "compile",
            ],
        }

    def ground_answer(
        self,
        *,
        question: str,
        semantic_plan: SemanticPlan,
        evidence_requirements: SemanticEvidenceRequirements,
        hints: list[dict[str, Any]],
        current_selection: dict[str, Any] | None = None,
        model: Any,
        answer_input_token_limit: int,
        max_answer_sources: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Generate one answer after Catalog retrieval has finalized evidence.

        The planner sees source identities only.  This method is the sole
        synchronous answer call and receives ACL/policy/citation-bound chunks
        selected from the compiled ExecutionPlan.  It cannot alter meaning or
        trigger a capability re-route.
        """

        return self._repair_grounded_answer(
            model=model,
            state={
                "question": question,
                "current_selection": dict(current_selection or {}),
            },
            plan=semantic_plan,
            evidence_requirements=evidence_requirements,
            hints=hints,
            diagnostics={"repair": "deferred_until_catalog_evidence"},
            answer_input_token_limit=answer_input_token_limit,
            max_answer_sources=max_answer_sources,
        )

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
        active_artifact_input: dict[str, str] | None = None,
        active_work_run: dict[str, Any] | None = None,
        task_ref: str = "",
        conversation_summary: str = "",
        conversation_context: dict[str, Any] | None = None,
        source_policy_context: dict[str, Any] | None = None,
        current_selection: dict[str, Any] | None = None,
        knowledge_hints: list[dict[str, Any]] | None = None,
        trusted_targets: dict[str, str] | None = None,
        trusted_entity_kinds: dict[str, str] | None = None,
        selected_subject_refs: list[str] | None = None,
        verified_typed_command_source: str = "",
        requested_user_effect: str = "",
        requested_operation: str = "",
        requested_result_kind: str = "",
        requested_graph_query_kind: str = "",
        requested_graph_node_kinds: list[str] | None = None,
        requested_graph_relation_kinds: list[str] | None = None,
        requested_work_view: str = "",
        defer_grounded_answer: bool = False,
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
                "active_artifact_input": dict(active_artifact_input or {}),
                "active_work_run": dict(active_work_run or {}),
                "task_ref": task_ref,
                "conversation_summary": conversation_summary,
                "conversation_context": dict(conversation_context or {}),
                "source_policy_context": dict(source_policy_context or {}),
                "current_selection": dict(current_selection or {}),
                "knowledge_hints": list(knowledge_hints or []),
                "context_token_budget": max(0, int(context_token_budget or 0)),
                "trusted_targets": dict(trusted_targets or {}),
                "trusted_entity_kinds": dict(trusted_entity_kinds or {}),
                "selected_subject_refs": list(selected_subject_refs or [])[:20],
                "verified_typed_command_source": verified_typed_command_source,
                "requested_user_effect": requested_user_effect,
                "requested_operation": requested_operation,
                "requested_result_kind": requested_result_kind,
                "requested_graph_query_kind": requested_graph_query_kind,
                "requested_graph_node_kinds": list(requested_graph_node_kinds or []),
                "requested_graph_relation_kinds": list(requested_graph_relation_kinds or []),
                "requested_work_view": requested_work_view,
                "defer_grounded_answer": bool(defer_grounded_answer),
                "model": model,
            }
        )
        return {
            "engine": self.engine,
            "capability_id": result["capability_id"],
            "semantic_plan": result["semantic_plan"],
            "semantic_plan_v4": result.get("semantic_plan_v4") or {},
            "execution_plan": result.get("execution_plan") or {},
            "catalog_compile": result.get("catalog_compile") or {},
            "planner_context_manifest": result.get("planner_context_manifest") or {},
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
            "safe_stop_after_repair": bool(result.get("safe_stop_after_repair")),
            "source": result.get("route_source") or "llm_structured",
            "reason": result.get("route_reason") or "semantic_plan_validated",
            "planner_error": result.get("planner_error") or "",
            "trace": result.get("trace") or [],
        }
