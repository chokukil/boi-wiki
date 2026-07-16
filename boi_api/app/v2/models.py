from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OperationClass(str, Enum):
    read = "read"
    draft = "draft"
    mutate = "mutate"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskMode(str, Enum):
    manual = "manual"
    copilot = "copilot"
    autopilot = "autopilot"


class WorkOperation(str, Enum):
    understand = "understand"
    create = "create"
    refine = "refine"
    compare = "compare"
    connect = "connect"
    validate = "validate"
    test = "test"
    run = "run"
    observe = "observe"
    complete = "complete"
    capture = "capture"
    promote = "promote"


class WorkAssetKind(str, Enum):
    knowledge = "knowledge"
    sop = "sop"
    workflow = "workflow"
    task = "task"
    business_event = "business_event"
    action = "action"
    skill = "skill"
    runtime = "runtime"
    evidence = "evidence"


class LoopKind(str, Enum):
    turn = "turn"
    goal = "goal"
    time = "time"
    proactive = "proactive"


class LoopTriggerKind(str, Enum):
    user = "user"
    api = "api"
    event = "event"
    schedule = "schedule"
    interval = "interval"


class LoopContract(BaseModel):
    """Planner-selected loop semantics bounded by a catalog and a versioned Harness."""

    model_config = ConfigDict(extra="forbid")

    kind: LoopKind = LoopKind.turn
    trigger: LoopTriggerKind = LoopTriggerKind.user
    task_stop: Literal["agent_done", "exit_criteria", "needs_context"] = "agent_done"
    routine_stop: Literal["one_shot", "cancelled", "max_runs", "event_resolved"] = "one_shot"
    max_iterations: int = Field(default=1, ge=1, le=20)
    max_no_progress: int = Field(default=2, ge=2, le=3)
    max_tool_loops: int = Field(default=1, ge=1, le=20)
    # These are safety ceilings, not latency targets. A turn may need one plan
    # repair and an independent evaluator, especially on a slower local model.
    max_model_calls: int = Field(default=4, ge=0, le=20)
    max_elapsed_seconds: int = Field(default=180, ge=1, le=86_400)
    # Zero delegates the input budget to the active provider profile. Positive
    # values remain available for an explicitly bounded operation or test.
    max_context_tokens: int = Field(default=0, ge=0, le=2_000_000)
    max_runs: int = Field(default=1, ge=0, le=10000)
    interval_seconds: int = Field(default=0, ge=0, le=31_536_000)
    adaptive_backoff: bool = True
    exit_criteria_refs: list[str] = Field(default_factory=list, max_length=30)
    progress_policy: Literal["structured_delta"] = "structured_delta"
    verifier_policy: str = Field(default="harness", max_length=120)
    source_fingerprint: str = Field(default="", max_length=256)
    routine_id: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_loop_shape(self) -> "LoopContract":
        if self.kind in {LoopKind.turn, LoopKind.goal} and self.trigger not in {
            LoopTriggerKind.user,
            LoopTriggerKind.api,
        }:
            raise ValueError("turn and goal loops require a user or API trigger")
        if self.kind == LoopKind.time and self.trigger not in {
            LoopTriggerKind.schedule,
            LoopTriggerKind.interval,
        }:
            raise ValueError("time loops require a schedule or interval trigger")
        if self.kind == LoopKind.proactive and self.trigger not in {
            LoopTriggerKind.event,
            LoopTriggerKind.schedule,
        }:
            raise ValueError("proactive loops require an event or schedule trigger")
        if self.kind == LoopKind.turn and (self.max_iterations != 1 or self.max_runs != 1):
            raise ValueError("turn loops execute exactly one bounded iteration")
        if self.trigger == LoopTriggerKind.interval and self.interval_seconds <= 0:
            raise ValueError("interval triggers require interval_seconds")
        return self


class LoopPolicy(LoopContract):
    """Backward-compatible request name for the LoopContract wire shape."""


class CapabilityState(str, Enum):
    ready = "ready"
    needs_input = "needs_input"
    unavailable = "unavailable"


class DraftContractDefinition(BaseModel):
    """Versioned structured-output contract referenced by catalog capabilities."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    version: str = "1.0"
    schema_: dict[str, Any] = Field(alias="schema")
    validator_plugins: list[str] = Field(default_factory=list)
    normalizer_plugins: list[str] = Field(default_factory=list)


class StarterOfferDefinition(BaseModel):
    """Declarative, grounded entry point owned by a capability definition."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str
    category: Literal[
        "current_work",
        "knowledge_relation",
        "similar_case",
        "sop_task",
        "business_event",
        "action",
        "knowledge_capture",
        "automatic_check",
    ]
    area: Literal["current_work", "knowledge", "workflow", "event_action", "learning", "automation"]
    selector: Literal[
        "current_work",
        "page_anchor",
        "recent_artifact",
        "connected_record",
        "canonical_entrypoint",
        "current_or_page",
    ]
    subject_binding: Literal["selected_record", "principal_person"] = "selected_record"
    record_kinds: list[str] = Field(default_factory=list)
    artifact_type_prefixes: list[str] = Field(default_factory=list)
    entrypoint_area: Literal[
        "", "current_work", "knowledge", "workflow", "event_action", "learning", "automation"
    ] = ""
    anchor_entrypoint_area: Literal[
        "", "current_work", "knowledge", "workflow", "event_action", "learning", "automation"
    ] = ""
    current_work_condition: Literal["any", "present", "absent"] = "any"
    include_anchor_source: bool = False
    only_when_category_empty: bool = True
    only_when_area_empty: bool = False
    use_entrypoint_copy: bool = False
    label_template: str = Field(min_length=1, max_length=240)
    prompt_template: str = Field(min_length=1, max_length=1600)
    reason_template: str = Field(min_length=1, max_length=320)
    priority: int = Field(default=100, ge=0, le=1000)
    context_basis: str = Field(default="knowledge", max_length=80)
    result_kind: Literal[
        "answer", "table", "timeline", "mermaid", "explorer", "work_form", "confirmation"
    ] = "answer"
    graph_query_kind: Literal[
        "", "neighbors", "path", "workflow", "impact", "lineage",
        "responsibility", "timeline", "compare", "tour",
    ] = ""
    fallback_to_answer: bool = False
    user_effect: Literal["read", "draft", "transform", "execute"] | None = None
    semantic_operation: WorkOperation | None = None
    work_view: Literal["none", "current", "responsibility", "combined"] | None = None

    @field_validator("offer_id")
    @classmethod
    def validate_offer_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in clean):
            raise ValueError("offer_id must be a lowercase dotted identifier")
        return clean

    @model_validator(mode="after")
    def validate_selector_contract(self) -> "StarterOfferDefinition":
        if self.selector == "canonical_entrypoint" and not self.entrypoint_area:
            raise ValueError("canonical_entrypoint selectors require entrypoint_area")
        if self.selector != "canonical_entrypoint" and self.entrypoint_area:
            raise ValueError("entrypoint_area is only valid for canonical_entrypoint selectors")
        if self.selector != "connected_record" and self.anchor_entrypoint_area:
            raise ValueError("anchor_entrypoint_area is only valid for connected_record selectors")
        if self.selector != "recent_artifact" and self.artifact_type_prefixes:
            raise ValueError("artifact_type_prefixes require a recent_artifact selector")
        if self.selector != "connected_record" and self.include_anchor_source:
            raise ValueError("include_anchor_source requires a connected_record selector")
        return self


class HelperTemplateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    name: str
    instructions: str = ""
    capability_ids: list[str] = Field(default_factory=list)


class SemanticOperationContract(BaseModel):
    """Catalog-owned meaning boundary for one semantic operation."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=1000)
    presentations: list[
        Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"]
    ] = Field(default_factory=list)
    graph_query_kinds: list[Literal[
        "neighbors", "path", "workflow", "impact", "lineage", "responsibility", "timeline", "compare", "tour"
    ]] = Field(default_factory=list)
    requires_graph: bool = False


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    version: str = "1.0"
    title: str
    description: str
    primary_asset: WorkAssetKind = WorkAssetKind.knowledge
    supported_assets: list[WorkAssetKind] = Field(default_factory=lambda: list(WorkAssetKind))
    subject_kinds: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    operation: OperationClass
    user_effects: list[Literal["read", "draft", "transform", "execute"]] = Field(default_factory=list)
    default_user_effect: Literal["read", "draft", "transform", "execute"] | None = None
    semantic_operations: list[WorkOperation] = Field(default_factory=list)
    semantic_operation_contracts: dict[WorkOperation, SemanticOperationContract] = Field(default_factory=dict)
    default_operation: WorkOperation | None = None
    operation_pipeline: list[WorkOperation] = Field(default_factory=list)
    operation_pipelines: dict[str, list[WorkOperation]] = Field(default_factory=dict)
    presentations: list[Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"]] = Field(
        default_factory=lambda: ["prose"]
    )
    default_presentation: Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"] = "prose"
    presentation_aliases: dict[
        str,
        Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"],
    ] = Field(default_factory=dict)
    graph_query_kinds: list[Literal[
        "neighbors", "path", "workflow", "impact", "lineage", "responsibility", "timeline", "compare", "tour"
    ]] = Field(default_factory=list)
    work_views: list[Literal["none", "current", "responsibility", "combined"]] = Field(
        default_factory=lambda: ["none", "current", "responsibility", "combined"]
    )
    work_view_operation_contracts: dict[
        Literal["none", "current", "responsibility", "combined"],
        list[WorkOperation],
    ] = Field(default_factory=dict)
    default_work_view: Literal["none", "current", "responsibility", "combined"] = "none"
    evidence_scopes: list[Literal["canonical", "operational", "validation"]] = Field(
        default_factory=lambda: ["canonical", "operational"]
    )
    default_evidence_scope: Literal["canonical", "operational", "validation"] = "canonical"
    topic_identity_sources: list[
        Literal["grounded_claims", "resolved_entities", "artifact"]
    ] = Field(default_factory=lambda: ["grounded_claims", "artifact"])
    harness_ids: list[str] = Field(default_factory=lambda: ["context.work"])
    subject_policy: Literal["optional", "required", "target_required"] = "optional"
    risk: RiskLevel = RiskLevel.low
    task_modes: list[TaskMode] = Field(default_factory=lambda: list(TaskMode))
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    context_recipe: list[str] = Field(default_factory=list)
    evidence_policy: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
    allowed_loop_kinds: list[LoopKind] = Field(default_factory=lambda: [LoopKind.turn])
    allowed_loop_triggers: list[LoopTriggerKind] = Field(
        default_factory=lambda: [LoopTriggerKind.user, LoopTriggerKind.api]
    )
    default_loop_contract: LoopContract = Field(default_factory=LoopContract)
    handler: str
    handler_config: dict[str, Any] = Field(default_factory=dict)
    renderer: str = "answer"
    permissions: list[str] = Field(default_factory=lambda: ["boi.viewer"])
    readiness: list[str] = Field(default_factory=list)
    offer_surfaces: list[Literal["library", "document", "inbox", "sop", "event", "action", "agent"]] = Field(
        default_factory=list
    )
    starter_offers: list[StarterOfferDefinition] = Field(default_factory=list)
    external: bool = True
    deep: bool = False

    @field_validator("capability_id")
    @classmethod
    def validate_capability_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in clean):
            raise ValueError("capability_id must be a lowercase dotted identifier")
        return clean

    @field_validator("semantic_operations")
    @classmethod
    def validate_semantic_operations(cls, value: list[WorkOperation]) -> list[WorkOperation]:
        return list(dict.fromkeys(value))

    @field_validator("operation_pipelines")
    @classmethod
    def validate_operation_pipelines(
        cls,
        value: dict[str, list[WorkOperation]],
    ) -> dict[str, list[WorkOperation]]:
        allowed = {item.value for item in WorkOperation}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown operation pipeline keys: {', '.join(unknown)}")
        return {key: list(dict.fromkeys(items)) for key, items in value.items()}

    @model_validator(mode="after")
    def validate_catalog_defaults(self) -> "CapabilityDefinition":
        if self.default_presentation not in self.presentations:
            raise ValueError("default_presentation must be declared in presentations")
        invalid_aliases = sorted(
            key for key, value in self.presentation_aliases.items()
            if not key.strip() or value not in self.presentations
        )
        if invalid_aliases:
            raise ValueError("presentation aliases must have a name and target a declared presentation")
        if self.default_work_view not in self.work_views:
            raise ValueError("default_work_view must be declared in work_views")
        undeclared_work_views = sorted(set(self.work_view_operation_contracts) - set(self.work_views))
        if undeclared_work_views:
            raise ValueError(
                "work view operation contracts target undeclared work views: "
                + ", ".join(undeclared_work_views)
            )
        undeclared_work_view_operations = sorted(
            {
                operation.value
                for operations in self.work_view_operation_contracts.values()
                for operation in operations
                if operation not in self.semantic_operations
            }
        )
        if undeclared_work_view_operations:
            raise ValueError(
                "work view operation contracts use undeclared operations: "
                + ", ".join(undeclared_work_view_operations)
            )
        if self.default_evidence_scope not in self.evidence_scopes:
            raise ValueError("default_evidence_scope must be declared in evidence_scopes")
        if self.default_user_effect is not None and self.default_user_effect not in self.user_effects:
            raise ValueError("default_user_effect must be declared in user_effects")
        if self.default_operation is not None and self.default_operation not in self.semantic_operations:
            raise ValueError("default_operation must be declared in semantic_operations")
        if self.semantic_operation_contracts:
            unknown_contracts = sorted(
                operation.value
                for operation in set(self.semantic_operation_contracts) - set(self.semantic_operations)
            )
            if unknown_contracts:
                raise ValueError(
                    "semantic operation contracts must target declared operations: "
                    + ", ".join(unknown_contracts)
                )
            undeclared_graph_queries = sorted(
                {
                    query_kind
                    for contract in self.semantic_operation_contracts.values()
                    for query_kind in contract.graph_query_kinds
                    if query_kind not in self.graph_query_kinds
                }
            )
            if undeclared_graph_queries:
                raise ValueError(
                    "semantic operation contracts use undeclared graph queries: "
                    + ", ".join(undeclared_graph_queries)
                )
            undeclared_presentations = sorted(
                {
                    presentation
                    for contract in self.semantic_operation_contracts.values()
                    for presentation in contract.presentations
                    if presentation not in self.presentations
                }
            )
            if undeclared_presentations:
                raise ValueError(
                    "semantic operation contracts use undeclared presentations: "
                    + ", ".join(undeclared_presentations)
                )
        if self.default_loop_contract.kind not in self.allowed_loop_kinds:
            raise ValueError("default loop kind must be declared in allowed_loop_kinds")
        if self.default_loop_contract.trigger not in self.allowed_loop_triggers:
            raise ValueError("default loop trigger must be declared in allowed_loop_triggers")
        for offer in self.starter_offers:
            effect = offer.user_effect or self.default_user_effect
            operation = offer.semantic_operation or self.default_operation
            work_view = offer.work_view or self.default_work_view
            presentation = (
                self.presentation_aliases.get(offer.result_kind)
                or (self.default_presentation if offer.result_kind == "answer" else offer.result_kind)
            )
            if effect not in self.user_effects:
                raise ValueError(f"starter offer {offer.offer_id} uses an undeclared user effect")
            if operation not in self.semantic_operations:
                raise ValueError(f"starter offer {offer.offer_id} uses an undeclared semantic operation")
            if work_view not in self.work_views:
                raise ValueError(f"starter offer {offer.offer_id} uses an undeclared work view")
            if presentation not in self.presentations:
                raise ValueError(f"starter offer {offer.offer_id} uses an undeclared presentation")
            if offer.graph_query_kind and offer.graph_query_kind not in self.graph_query_kinds:
                raise ValueError(f"starter offer {offer.offer_id} uses an undeclared graph query")
        return self


class Principal(BaseModel):
    employee_id: str
    display_name: str
    email: str = ""
    teams: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    auth_source: str
    token_id: str | None = None
    token_scopes: list[str] = Field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "boi.admin" in self.roles


class EvidenceRef(BaseModel):
    evidence_id: str
    kind: str
    title: str
    summary: str = ""
    url: str = ""
    source: str = "knowledge"
    authority: str = "reviewed"
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolvedSourceRef(BaseModel):
    source_ref: str
    title: str
    canonical_url: str = ""
    source_kind: str = "document"
    navigation_state: Literal["navigable", "restricted", "unresolved"] = "unresolved"


class CitationRef(BaseModel):
    citation_id: str
    source_ref: str
    chunk_id: str = ""
    title: str
    heading: str = ""
    excerpt: str = ""
    target_url: str = ""
    start_line: int = Field(default=0, ge=0)
    end_line: int = Field(default=0, ge=0)
    kind: str = "document"
    resolved_source: ResolvedSourceRef | None = None


class GroundedClaim(BaseModel):
    claim_id: str
    text: str
    claim_kind: Literal["definition", "fact", "procedure", "comparison", "relationship", "work"] = "fact"
    source_scope: Literal["canonical", "operational", "validation"] = "canonical"
    source_refs: list[str] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    support_status: Literal["supported", "partial", "unsupported", "conflicting"] = "unsupported"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    required_for_answer: bool = False


class AnswerabilityReport(BaseModel):
    status: Literal["grounded", "partial", "insufficient", "conflicting"] = "insufficient"
    answer_intent: Literal["definition", "fact", "procedure", "comparison", "relationship", "work"] = "fact"
    supported_claim_count: int = Field(default=0, ge=0)
    unsupported_claim_count: int = Field(default=0, ge=0)
    conflicting_claim_count: int = Field(default=0, ge=0)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class TurnTopicState(BaseModel):
    topic_state_ref: str
    subject: str = ""
    subjects: list[str] = Field(default_factory=list, max_length=20)
    topic_structure: Literal["single_focal", "multiple_focal", "collective"] = "single_focal"
    entities: list[str] = Field(default_factory=list, max_length=100)
    result_entities: list[str] = Field(default_factory=list, max_length=100)
    artifact_entities: list[str] = Field(default_factory=list, max_length=100)
    entity_labels: dict[str, str] = Field(default_factory=dict)
    claims: list[GroundedClaim] = Field(default_factory=list)
    used_source_refs: list[str] = Field(default_factory=list)
    active_artifact_id: str = ""
    correction_status: Literal["active", "corrected", "invalidated"] = "active"


class RelatedQuestion(BaseModel):
    question_id: str
    kind: Literal["understand", "connect", "apply"]
    label: str
    question: str
    source_refs: list[str] = Field(default_factory=list)


class StarterSuggestion(BaseModel):
    suggestion_id: str
    category: Literal[
        "current_work",
        "knowledge_relation",
        "similar_case",
        "sop_task",
        "business_event",
        "action",
        "knowledge_capture",
        "automatic_check",
    ]
    label: str = Field(max_length=160)
    prompt: str = Field(max_length=1200)
    subject_ref: str = Field(max_length=1000)
    source_refs: list[str] = Field(min_length=1, max_length=4)
    reason: str = Field(default="", max_length=240)
    priority: int = Field(default=100, ge=0, le=1000)
    area: Literal["current_work", "knowledge", "workflow", "event_action", "learning", "automation"] = "knowledge"
    featured: bool = False
    context_basis: str = Field(default="knowledge", max_length=80)
    subject_title: str = Field(default="", max_length=160)
    result_kind: Literal[
        "answer", "table", "timeline", "mermaid", "explorer", "work_form", "confirmation"
    ] = "answer"
    graph_query_kind: Literal[
        "", "neighbors", "path", "workflow", "impact", "lineage",
        "responsibility", "timeline", "compare", "tour",
    ] = ""
    capability_id: str = Field(min_length=1, max_length=120)
    user_effect: Literal["read", "draft", "transform", "execute"] = "read"
    operation: WorkOperation = WorkOperation.understand
    work_view: Literal["none", "current", "responsibility", "combined"] = "none"


class StarterSuggestionSetRequest(BaseModel):
    page_ref: str = Field(default="", max_length=1000)
    work_session_id: str = Field(default="", max_length=120)


class GoalStep(BaseModel):
    step_id: str
    capability_id: str
    label: str
    operation: Literal["read", "draft", "deep", "guarded"] = "read"
    semantic_operation: WorkOperation = WorkOperation.understand
    depends_on: list[str] = Field(default_factory=list)
    status: Literal[
        "pending",
        "running",
        "completed",
        "queued",
        "waiting_input",
        "waiting_review",
        "waiting_confirmation",
        "blocked",
        "failed",
    ] = "pending"
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class CompletionBinding(BaseModel):
    kind: Literal["none", "event", "action_result", "artifact", "data_field", "state"] = "none"
    ref: str = ""
    field: str = ""
    operator: str = ""
    value: Any = None


class CompletionCheck(BaseModel):
    check_id: str
    label: str
    confirmation: Literal["human", "system"] = "human"
    binding: CompletionBinding | None = None


class CompletionEvidence(BaseModel):
    evidence_id: str
    label: str
    source_kind: Literal[
        "boi",
        "event",
        "action_result",
        "data_artifact",
        "file",
        "human_note",
        "external_ai",
    ] = "human_note"
    ref: str = ""
    provided_by: Literal["human", "agent", "system"] = "human"
    required: bool = True


class TaskCompletionDesign(BaseModel):
    version: Literal[1] = 1
    checks: list[CompletionCheck] = Field(default_factory=list)
    evidence: list[CompletionEvidence] = Field(default_factory=list)


class ContextAnchor(BaseModel):
    ref: str = ""
    kind: str = ""
    title: str = ""
    url: str = ""
    revision: str = ""
    source: Literal["page", "goal", "pinned", "task"] = "page"
    resolved: bool = False
    context_resolution: Literal["route", "ontology_only", "none"] = "none"


class ContextItemUsage(BaseModel):
    item_ref: str
    item_kind: Literal["evidence", "playbook", "task", "page", "artifact"] = "evidence"
    provenance: str = ""
    revision: str = ""
    token_cost: int = Field(default=0, ge=0)
    selected: bool = False
    used: bool = False
    selection_reason: str = ""
    outcome_contribution: Literal[
        "none", "answer", "artifact", "decision", "completion", "blocker"
    ] = "none"
    source_refs: list[str] = Field(default_factory=list)


class ContextManifest(BaseModel):
    selected_refs: list[str] = Field(default_factory=list)
    excluded_refs: list[str] = Field(default_factory=list)
    exclusion_reasons: dict[str, str] = Field(default_factory=dict)
    pinned_refs: list[str] = Field(default_factory=list)
    chunk_refs: list[str] = Field(default_factory=list)
    external_refs: list[str] = Field(default_factory=list)
    source_revision: str = ""
    token_budget: int = Field(default=0, ge=0)
    # ``compress`` and ``isolate`` remain readable for persisted v1 manifests,
    # but new runs preserve selected items and reference large source artifacts.
    policies: list[
        Literal["write", "select", "preserve", "reference", "compress", "isolate"]
    ] = Field(
        default_factory=lambda: ["write", "select", "preserve", "reference"]
    )
    raw_content_in_prompt: bool = False
    provenance: dict[str, dict[str, str]] = Field(default_factory=dict)
    items: list[ContextItemUsage] = Field(default_factory=list)
    token_cost_total: int = Field(default=0, ge=0)
    used_refs: list[str] = Field(default_factory=list)
    budget_resolution: dict[str, Any] = Field(default_factory=dict)


class GraphQueryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    query_kind: Literal[
        "neighbors", "path", "workflow", "impact", "lineage",
        "responsibility", "timeline", "compare", "tour",
    ] = "neighbors"
    focal_mentions: list[str] = Field(default_factory=list, max_length=20)
    target_mentions: list[str] = Field(default_factory=list, max_length=20)
    node_kinds: list[str] = Field(default_factory=list, max_length=30)
    relation_kinds: list[str] = Field(default_factory=list, max_length=30)
    direction: Literal["outgoing", "incoming", "both"] = "both"
    depth: int = Field(default=2, ge=1, le=6)
    time_from: str = ""
    time_to: str = ""
    presentation: Literal["auto", "list", "table", "timeline", "mermaid", "explorer"] = "auto"


class GraphQueryFilterContract(BaseModel):
    """Catalog-owned graph filter vocabulary supplied to the semantic planner."""

    model_config = ConfigDict(extra="forbid")

    node_kinds: list[str] = Field(default_factory=list)
    relation_kinds: list[str] = Field(default_factory=list)
    filter_policy: Literal["explicit_only"] = "explicit_only"


class SemanticSubject(BaseModel):
    """A subject selected by the planner, before ACL-bounded entity resolution."""

    model_config = ConfigDict(extra="forbid")

    mention: str = Field(min_length=1, max_length=240)
    entity_ref: str = Field(default="", max_length=1000)
    entity_kind: str = Field(default="", max_length=80)
    resolution: Literal["unresolved", "resolved", "ambiguous", "missing"] = "unresolved"


class SemanticWorkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: str = Field(default="", max_length=2000)
    actions: str = Field(default="", max_length=2000)
    judgment: str = Field(default="", max_length=2000)
    result: str = Field(default="", max_length=2000)
    blocker: str = Field(default="", max_length=1000)
    next_work: str = Field(default="", max_length=1000)


class SemanticContinuation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continue_active_run: bool = False
    delta_kind: Literal["none", "human_input", "new_evidence", "blocker", "state_transition"] = "none"
    user_confirmation: bool = False
    work_record: SemanticWorkRecord = Field(default_factory=SemanticWorkRecord)


class SemanticPlan(BaseModel):
    """The model-owned meaning contract. Validators may reject it, never rewrite it."""

    model_config = ConfigDict(extra="forbid")

    schema_revision: str = "semantic-plan/v3"
    resolved_goal: str = Field(min_length=1, max_length=12000)
    retrieval_query: str = Field(
        default="",
        max_length=12000,
        description=(
            "Standalone retrieval query for an executable new or continued topic. It may be empty only when "
            "topic_action is clarify because a clarification turn does not execute retrieval."
        ),
    )
    topic_action: Literal["new", "continue", "clarify"] = Field(
        default="new",
        description=(
            "How this turn relates to verified topic state: new selects a distinct subject, continue keeps "
            "one or all uniquely identified prior subjects, and clarify is required when the current request "
            "does not uniquely identify which prior subject it means."
        ),
    )
    reference_resolution: Literal["none", "all", "specific", "ambiguous"] = Field(
        default="none",
        description=(
            "Resolution of references to prior subjects. Use none when topic_action is new; all when the request "
            "covers every prior subject; specific only when the current request uniquely identifies exactly one "
            "prior subject; ambiguous when more than one prior subject remains possible and clarification is needed."
        ),
    )
    subjects: list[SemanticSubject] = Field(default_factory=list, max_length=20)
    capability_id: str = Field(min_length=1, max_length=120)
    user_effect: Literal["read", "draft", "transform", "execute"] = "read"
    operation: WorkOperation = WorkOperation.understand
    evidence_scope: Literal["canonical", "operational", "validation"] = "canonical"
    presentation: Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"] = "prose"
    work_view: Literal["none", "current", "responsibility", "combined"] = Field(
        default="none",
        description=(
            "The workplace perspective explicitly requested by the user. current means only active assignments; "
            "responsibility means declared roles and verified recurring work; combined means both perspectives, "
            "kept as separate sections in one result; none is valid only when the requested result needs none of "
            "those workplace perspectives. Do not use none to bypass a requested workplace perspective."
        ),
    )
    graph_query: GraphQueryDraft | None = None
    context_refs: list[str] = Field(default_factory=list, max_length=100)
    target_ref: str = Field(default="", max_length=1000)
    answer_intent: Literal["definition", "fact", "procedure", "comparison", "relationship", "work"] = "fact"
    clarification_question: str = Field(default="", max_length=240)
    continuation: SemanticContinuation = Field(default_factory=SemanticContinuation)
    loop_contract: LoopContract = Field(default_factory=LoopContract)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ValidationIssue(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    field: str = Field(default="", max_length=240)
    message: str = Field(min_length=1, max_length=1000)
    severity: Literal["error", "warning"] = "error"
    repairable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class PlanValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=50)
    catalog_revision: str = ""
    planner_schema_revision: str = "semantic-plan/v3"


class TypedCommand(BaseModel):
    """An explicit UI/API/MCP command whose semantics are not reinterpreted."""

    capability_id: str = Field(min_length=1, max_length=120)
    user_effect: Literal["read", "draft", "transform", "execute"]
    operation: WorkOperation
    goal: str = Field(min_length=1, max_length=12000)
    subject_refs: list[str] = Field(default_factory=list, max_length=20)
    presentation: Literal["prose", "table", "timeline", "mermaid", "explorer", "artifact"] = "prose"
    work_view: Literal["none", "current", "responsibility", "combined"] = "none"
    graph_query: GraphQueryDraft | None = None
    input_delta: dict[str, Any] = Field(default_factory=dict)


class WorkIntent(BaseModel):
    goal: str
    resolved_goal: str = ""
    retrieval_query: str = ""
    answer_intent: Literal["definition", "fact", "procedure", "comparison", "relationship", "work"] = "fact"
    answer_source_scope: Literal["canonical", "operational", "validation"] = "canonical"
    topic_mode: Literal["new", "continue", "clarify"] = "new"
    topic_subject: str = ""
    topic_structure: Literal["single_focal", "multiple_focal", "collective"] = "single_focal"
    primary_topic_entity: str = ""
    topic_entities: list[str] = Field(default_factory=list, max_length=12)
    referenceable_topic_entities: list[str] = Field(default_factory=list, max_length=12)
    followup_reference_resolution: Literal["none", "all", "specific", "ambiguous"] = "none"
    selected_prior_topic_entities: list[str] = Field(default_factory=list, max_length=12)
    followup_semantic_change: Literal[
        "none",
        "presentation_only",
        "evidence_scope",
        "same_subject_question",
        "new_subject",
        "ambiguous_reference",
    ] = "none"
    comparison_axes: list[str] = Field(default_factory=list, max_length=6)
    comparison_focal_entities: list[str] = Field(default_factory=list, max_length=12)
    relationship_focal_entities: list[str] = Field(default_factory=list, max_length=12)
    asset_kind: WorkAssetKind = WorkAssetKind.knowledge
    operation: WorkOperation = WorkOperation.understand
    operation_plan: list[WorkOperation] = Field(default_factory=lambda: [WorkOperation.understand])
    target_ref: str = ""
    scope: Literal["auto", "current", "wiki", "selected"] = "auto"
    desired_outcome: str = "answer"
    presentation_mode: Literal["prose", "mermaid", "table", "timeline", "explorer", "artifact"] = "prose"
    work_view: Literal["none", "current", "responsibility", "combined"] = "none"
    graph_query_draft: GraphQueryDraft | None = None
    context_refs: list[str] = Field(default_factory=list, max_length=100)
    user_effect: Literal["read", "draft", "transform", "execute"] = "read"
    result_purpose: Literal["explain", "compare", "design", "transform", "execute"] = "explain"
    requested_transition: Literal["none", "draft", "transform", "execute"] = "none"
    analysis_depth: Literal["standard", "deep"] = "standard"
    requested_asset_kinds: list[WorkAssetKind] = Field(default_factory=list, max_length=9)
    harness_ids: list[str] = Field(default_factory=list, max_length=20)
    artifact_actions: list[Literal["split_tasks", "create_sop_draft"]] = Field(default_factory=list, max_length=2)
    loop_contract: LoopContract = Field(default_factory=LoopContract)
    risk: RiskLevel = RiskLevel.low
    needs_clarification: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LoopDelta(BaseModel):
    kind: Literal[
        "new_evidence",
        "action_result",
        "human_input",
        "new_artifact",
        "state_transition",
        "blocker",
        "knowledge_candidate",
        "no_progress",
    ]
    summary: str = Field(default="", max_length=2000)
    ref: str = Field(default="", max_length=1000)
    fingerprint: str = Field(default="", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProgressDelta(BaseModel):
    """Structured progress at a loop boundary; prose is never the progress key."""

    delta_id: str
    kind: Literal[
        "evidence", "tool_result", "artifact", "human_input", "state_transition", "blocker", "strategy_change"
    ]
    entity_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tool_result_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    completion_changes: dict[str, Any] = Field(default_factory=dict)
    blocker_code: str = Field(default="", max_length=120)
    strategy: str = Field(default="", max_length=1000)
    strategy_refs: list[str] = Field(default_factory=list)
    error_disposition: Literal[
        "", "transient_retry", "semantic_repair", "human_interrupt", "policy_stop", "unexpected_failure"
    ] = ""
    summary: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)


class WorkRunCheckpoint(BaseModel):
    checkpoint_id: str
    work_run_id: str
    node: Literal["observe", "context", "semantic_plan", "act", "ask", "verify", "reflect", "stop"]
    sequence: int = Field(ge=1)
    raw_state: dict[str, Any] = Field(default_factory=dict)
    catalog_revision: str = ""
    harness_revisions: dict[str, str] = Field(default_factory=dict)
    planner_schema_revision: str = "semantic-plan/v3"
    loop_position: dict[str, int] = Field(default_factory=dict)
    pending_interrupt: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class ExitCriteriaResult(BaseModel):
    satisfied: bool = False
    criteria: list[HarnessCheck] = Field(default_factory=list)
    evidence_ledger_ids: list[str] = Field(default_factory=list)
    evaluated_facts: dict[str, Any] = Field(default_factory=dict)
    stop_reason: Literal[
        "",
        "exit_criteria_satisfied",
        "needs_human",
        "policy_stop",
        "max_iterations",
        "max_tool_loops",
        "max_elapsed_seconds",
        "max_model_calls",
        "no_progress",
        "blocked",
    ] = ""


class HarnessCheck(BaseModel):
    check_id: str
    label: str
    status: Literal["passed", "warning", "blocked"]
    message: str = ""


class HarnessResult(BaseModel):
    harness_id: str
    version: str = "1.0"
    status: Literal["passed", "warning", "blocked"] = "passed"
    checks: list[HarnessCheck] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    definition_ref: str = ""
    phase: str = ""
    evaluated_facts: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    interruptible: bool = False


class HarnessFailureRecord(BaseModel):
    failure_record_id: str
    employee_id: str
    work_run_id: str
    harness_id: str
    harness_version: str
    model_profile: str
    phase: str
    component_ref: str
    causal_taxonomy_revision: str
    causal_mechanism: str
    verifier_facts: dict[str, Any] = Field(default_factory=dict)
    trace_refs: list[str] = Field(default_factory=list)
    context_id: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    catalog_revision: str = ""
    planner_schema_revision: str = ""
    source_revision: str = ""
    failure_pattern_id: str = ""
    status: Literal["open", "addressed", "dismissed"] = "open"
    created_at: datetime = Field(default_factory=utc_now)


class HarnessChangeHypothesis(BaseModel):
    editable_surface: str
    diff: dict[str, Any]
    predicted_impact: dict[str, float] = Field(min_length=1, max_length=20)
    at_risk_regressions: list[str] = Field(min_length=1, max_length=100)
    preservation_run_ids: list[str] = Field(min_length=1, max_length=100)
    expires_at: datetime
    rollback_target: str = Field(min_length=1, max_length=160)


class HarnessEvaluationReport(BaseModel):
    eval_id: str
    candidate_id: str
    shadow_run_id: str
    fixture_revision: str
    held_in: dict[str, Any]
    held_out: dict[str, Any]
    preserved: dict[str, Any]
    adversarial: dict[str, Any]
    long_term: dict[str, Any]
    predicted_impact: dict[str, float] = Field(default_factory=dict)
    actual_impact: dict[str, float] = Field(default_factory=dict)
    prediction_met: bool = False
    qualified: bool = False
    production_changed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class HarnessCandidateCreateRequest(BaseModel):
    harness_id: str = Field(min_length=1, max_length=120)
    failure_record_ids: list[str] = Field(min_length=3, max_length=50)
    model_profile: str = Field(default="default", max_length=160)
    changes: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=12, max_length=4000)
    predicted_impact: dict[str, float] = Field(min_length=1, max_length=20)
    at_risk_regressions: list[str] = Field(min_length=1, max_length=100)
    preservation_run_ids: list[str] = Field(min_length=1, max_length=100)
    expires_at: datetime
    rollback_target: str = Field(min_length=1, max_length=160)


class HarnessCandidateShadowRequest(BaseModel):
    fixture_revision: str = Field(min_length=1, max_length=160)
    held_out_limit: int = Field(default=20, ge=1, le=100)


class HarnessCandidateEvaluateRequest(BaseModel):
    shadow_run_id: str = Field(min_length=1, max_length=160)
    held_in: dict[str, Any]
    held_out: dict[str, Any]
    adversarial: dict[str, Any] = Field(default_factory=dict)
    long_term: dict[str, Any] = Field(default_factory=dict)
    fixture_revision: str = Field(min_length=1, max_length=160)


class HarnessCandidateReviewRequest(BaseModel):
    decision: Literal["approve_for_release", "hold", "reject"]
    expected_eval_id: str = Field(min_length=1, max_length=160)
    note: str = Field(min_length=4, max_length=4000)


class HarnessVersionReleaseRequest(BaseModel):
    expected_version_id: str = Field(min_length=1, max_length=160)
    note: str = Field(min_length=4, max_length=4000)
    user_confirmed: bool = False
    rehearsal: bool = False


class HarnessVersionRollbackRequest(BaseModel):
    note: str = Field(min_length=4, max_length=4000)
    user_confirmed: bool = False
    rehearsal: bool = False


class ContextPlaybookCreateRequest(BaseModel):
    description: str = Field(min_length=12, max_length=4000)
    conditions: list[str] = Field(default_factory=list, max_length=30)
    capability_ids: list[str] = Field(default_factory=list, max_length=30)
    asset_kinds: list[str] = Field(default_factory=list, max_length=30)
    task_refs: list[str] = Field(default_factory=list, max_length=30)
    team_ids: list[str] = Field(default_factory=list, max_length=30)
    model_profiles: list[str] = Field(default_factory=lambda: ["default"], max_length=20)
    source_refs: list[str] = Field(min_length=1, max_length=50)
    supporting_work_run_ids: list[str] = Field(default_factory=list, max_length=50)
    valid_until: str = Field(default="", max_length=80)
    visibility: Literal["private", "team"] = "private"


class ContextPlaybookPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    description: str | None = Field(default=None, min_length=12, max_length=4000)
    status: Literal["provisional", "active", "deprecated", "rejected"] | None = None
    valid_until: str | None = Field(default=None, max_length=80)
    deprecates_item_ids: list[str] | None = Field(default=None, max_length=30)
    review_note: str = Field(default="", max_length=4000)


class KnowledgeCandidateRef(BaseModel):
    candidate_id: str
    title: str
    status: Literal["provisional", "reviewed", "archived", "promotion_requested"] = "provisional"
    url: str = ""


class ArtifactAction(BaseModel):
    action_id: Literal["split_tasks", "create_sop_draft"]
    label: str
    action_kind: Literal["transform_artifact"] = "transform_artifact"
    state: Literal["ready", "unavailable"] = "ready"
    artifact_id: str = ""


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str
    status: Literal["draft", "provisional", "reviewed"] = "draft"
    url: str = ""
    preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[ArtifactAction] = Field(default_factory=list, max_length=3)


class WorkContextPack(BaseModel):
    context_id: str
    employee_id: str
    capability_id: str
    goal: str
    page_ref: str = ""
    task_ref: str = ""
    workflow_ref: str = ""
    task_mode: TaskMode = TaskMode.copilot
    exit_criteria: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    completion_design: TaskCompletionDesign | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    similar_case_refs: list[EvidenceRef] = Field(default_factory=list)
    external_ai_summary: str = ""
    loop_delta: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    page_anchor: ContextAnchor | None = None
    goal_anchor: ContextAnchor | None = None
    business_context: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    context_manifest: ContextManifest | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CapabilityOffer(BaseModel):
    offer_id: str
    capability_id: str
    label: str
    reason: str
    state: CapabilityState
    required_inputs: list[str] = Field(default_factory=list)
    context_fingerprint: str
    preview: str = ""
    expires_at: datetime


class OfferRequest(BaseModel):
    page_ref: str = ""
    task_ref: str = ""
    selected_text: str = Field(default="", max_length=4000)
    include_unavailable: bool = False


class OfferExecuteRequest(BaseModel):
    page_ref: str = ""
    task_ref: str = ""
    input_delta: dict[str, Any] = Field(default_factory=dict)


class AgentTurnRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None
    work_session_id: str | None = None
    helper_id: str | None = None
    page_ref: str = ""
    selected_text: str = Field(default="", max_length=4000)
    task_ref: str = ""
    offer_id: str | None = None
    suggestion_id: str | None = Field(default=None, max_length=120)
    suggestion_set_id: str | None = Field(default=None, max_length=120)
    input_delta: dict[str, Any] = Field(default_factory=dict)
    capability_id: str | None = None
    external_ai_summary: str = Field(default="", max_length=8000)
    external_artifact_refs: list[str] = Field(default_factory=list, max_length=20)
    loop_policy: LoopPolicy | None = None


class AnswerBlock(BaseModel):
    summary: str
    markdown: str
    display_html: str = ""


class NextAction(BaseModel):
    action_id: str
    label: str
    action_kind: Literal[
        "open_task_editor",
        "open_full_editor",
        "show_evidence",
        "show_sources",
        "save_note",
        "execute_capability",
        "open_artifact",
        "confirm_plan",
        "transform_artifact",
    ]
    state: Literal["ready", "unavailable"] = "ready"
    artifact_id: str = ""
    task_id: str = ""
    capability_id: str = ""
    plan_id: str = ""
    href: str = ""


class AgentTurnResponse(BaseModel):
    run_id: str
    turn_id: str
    conversation_id: str = ""
    work_session_id: str = ""
    status: Literal["completed", "needs_input", "queued", "failed"]
    capability_id: str
    answer: AnswerBlock
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    offers: list[CapabilityOffer] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list, max_length=3)
    context_ref: str = ""
    plan_ref: str = ""
    job_ref: str = ""
    error_code: str = ""
    goal_plan_ref: str = ""
    source_set_ref: str = ""
    citations: list[CitationRef] = Field(default_factory=list)
    used_source_refs: list[str] = Field(default_factory=list)
    related_questions: list[RelatedQuestion] = Field(default_factory=list, max_length=3)
    grounding_status: Literal["grounded", "partial", "insufficient", "conflicting", "no_evidence"] = "no_evidence"
    answerability: AnswerabilityReport = Field(default_factory=AnswerabilityReport)
    grounded_claims: list[GroundedClaim] = Field(default_factory=list)
    topic_state_ref: str = ""
    progress: list[dict[str, Any]] = Field(default_factory=list)
    work_run_id: str = ""
    work_intent: WorkIntent | None = None
    loop_state: dict[str, Any] = Field(default_factory=dict)
    harness_results: list[HarnessResult] = Field(default_factory=list)
    knowledge_candidates: list[KnowledgeCandidateRef] = Field(default_factory=list)
    context_usage: dict[str, Any] = Field(default_factory=dict)
    presentation_plan: dict[str, Any] = Field(default_factory=dict)
    a2ui_surface_ref: str = ""
    graph_result_ref: str = ""
    semantic_plan_ref: str = ""
    loop_contract: LoopContract = Field(default_factory=LoopContract)
    usage: dict[str, Any] = Field(default_factory=dict)
    stop_reason: str = ""


class WorkSessionCreateRequest(BaseModel):
    title: str = Field(default="", max_length=160)
    page_ref: str = Field(default="", max_length=1000)
    helper_id: str = Field(default="", max_length=120)


class WorkSessionPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=160)
    status: Literal["active", "archived"] | None = None
    pinned: bool | None = None
    active_artifact_id: str | None = Field(default=None, max_length=120)
    selected_task_id: str | None = Field(default=None, max_length=120)
    active_panel: Literal["result", "evidence", "task"] | None = None


class WorkRunContinueRequest(BaseModel):
    delta: LoopDelta
    confirmation: Literal["confirm"] | None = None
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(default="", max_length=160)


class KnowledgeSourceDefinition(BaseModel):
    source_id: str
    name: str
    source_kind: Literal["okf_markdown", "git", "data_lake", "graphify", "openkb", "codegraph", "external_cli"]
    location: str
    visibility: Literal["private", "team", "public"] = "private"
    owner: str = ""
    team_id: str = ""
    adapter: str
    sync_policy: Literal["manual", "on_change", "scheduled"] = "on_change"
    enabled: bool = True
    revision: int = 1
    checksum: str = ""
    status: Literal["ready", "pending", "syncing", "unavailable", "failed"] = "pending"
    last_sync_at: str = ""
    last_error: str = ""
    adapter_config: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source_kind: Literal["data_lake", "graphify", "openkb", "codegraph", "external_cli"]
    location: str = Field(default="", max_length=2000)
    visibility: Literal["private", "team", "public"] = "private"
    team_id: str = Field(default="", max_length=120)
    sync_policy: Literal["manual", "on_change", "scheduled"] = "manual"
    adapter_config: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceRollbackRequest(BaseModel):
    user_confirmed: bool = False
    reason: str = Field(min_length=4, max_length=2000)


class KnowledgeEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    provenance: Literal["declared", "extracted", "inferred", "human_verified", "ambiguous"]
    confidence: float = Field(ge=0.0, le=1.0)
    source_refs: list[str] = Field(default_factory=list, max_length=20)
    extractor_version: str
    source_revision: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphQueryPlan(BaseModel):
    focal_entities: list[str] = Field(min_length=1, max_length=20)
    query_kind: Literal[
        "neighbors", "path", "workflow", "impact", "lineage",
        "responsibility", "timeline", "compare", "tour",
    ] = "neighbors"
    target_entities: list[str] = Field(default_factory=list, max_length=20)
    node_kinds: list[str] = Field(default_factory=list, max_length=30)
    relation_kinds: list[str] = Field(default_factory=list, max_length=30)
    direction: Literal["outgoing", "incoming", "both"] = "both"
    depth: int = Field(default=2, ge=1, le=6)
    limit: int = Field(default=80, ge=1, le=500)
    time_from: str = ""
    time_to: str = ""
    presentation: Literal["auto", "list", "table", "timeline", "mermaid", "explorer"] = "auto"


class KnowledgePatchProposal(BaseModel):
    proposal_id: str
    finding_id: str
    kind: Literal[
        "reindex",
        "repair_link",
        "remove_stale_edge",
        "merge_duplicate",
        "resolve_contradiction",
        "add_coverage",
    ]
    title: str
    summary: str
    target_refs: list[str] = Field(default_factory=list, max_length=20)
    source_refs: list[str] = Field(default_factory=list, max_length=20)
    diff: dict[str, Any] = Field(default_factory=dict)
    deterministic: bool = False
    visibility: Literal["private", "team", "public"] = "private"
    status: Literal["proposed", "review_required", "applied", "dismissed"] = "proposed"
    revision: int = 1


class KnowledgeProposalApplyRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    confirmation: Literal["confirm"]
    reason: str = Field(default="", max_length=2000)


class KnowledgeCandidatePatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=4000)
    reusable_lesson: str | None = Field(default=None, max_length=4000)
    target_asset_ref: str | None = Field(default=None, max_length=1000)
    status: Literal["provisional", "reviewed", "archived"] | None = None


class KnowledgeCandidatePromoteRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    target_visibility: Literal["team", "public"]
    team_id: str = Field(default="", max_length=120)
    reason: str = Field(default="", max_length=2000)


class HarnessValidateRequest(BaseModel):
    phase: Literal["preflight", "validate", "preview", "test", "capture", "promote", "post_verify"] = "validate"
    context_id: str = Field(min_length=1, max_length=120)
    artifact_id: str = Field(default="", max_length=120)
    candidate_id: str = Field(default="", max_length=120)
    work_run_id: str = Field(default="", max_length=120)


class SourceSetPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    pin_refs: list[str] = Field(default_factory=list, max_length=100)
    unpin_refs: list[str] = Field(default_factory=list, max_length=100)
    exclude_refs: list[str] = Field(default_factory=list, max_length=100)
    include_refs: list[str] = Field(default_factory=list, max_length=100)
    attached_refs: list[str] | None = Field(default=None, max_length=100)


class NoteFromTurnRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=120)
    work_session_id: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=160)


class SopTaskPatch(BaseModel):
    task_id: str = Field(min_length=1, max_length=120)
    base_task: dict[str, Any] = Field(default_factory=dict)
    task: dict[str, Any] = Field(default_factory=dict)


class SopArtifactPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    task_updates: list[SopTaskPatch] = Field(default_factory=list, max_length=100)
    task_additions: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    task_deletions: list[str] = Field(default_factory=list, max_length=100)
    task_order: list[str] | None = Field(default=None, max_length=100)
    draft_fields: dict[str, Any] = Field(default_factory=dict)
    selected_task_id: str = Field(default="", max_length=120)


class TaskRefinePreviewRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    instruction: str = Field(default="종료 기준과 필요한 근거를 더 구체적으로 다듬어줘", max_length=4000)


class ProposalApplyRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class HelperDraftCreateRequest(BaseModel):
    template_id: Literal["search", "sop", "evidence", "blank"] = "blank"
    name: str = Field(default="", max_length=120)
    instructions: str = Field(default="", max_length=8000)


class LegacyHelperImportRequest(BaseModel):
    legacy_draft_id: str = Field(min_length=1, max_length=160)


class HelperDraftPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=8000)
    capability_ids: list[str] | None = Field(default=None, max_length=30)
    source_scopes: list[str] | None = Field(default=None, max_length=30)
    skill_ids: list[str] | None = Field(default=None, max_length=50)
    connector_refs: list[str] | None = Field(default=None, max_length=30)
    surfaces: list[str] | None = Field(default=None, max_length=20)
    visibility: Literal["private", "team", "public"] | None = None


class HelperPreviewTurnRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    work_session_id: str | None = None


class HelperActivateRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class SkillArtifactTestRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    scenario: str = Field(default="", max_length=4000)
    sample_input: dict[str, Any] = Field(default_factory=dict)
    expected_contains: list[str] = Field(default_factory=list, max_length=20)


class SkillArtifactActivateRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class CapabilityPlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=12000)
    page_ref: str = ""
    task_ref: str = ""
    input: dict[str, Any] = Field(default_factory=dict)


class PlanConfirmRequest(BaseModel):
    confirmation: Literal["confirm"]
    reason: str = Field(default="", max_length=2000)


class DeepJobRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=12000)
    capability_id: str | None = Field(default=None, min_length=1, max_length=120)
    page_ref: str = ""
    task_ref: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=900, ge=30, le=3600)
    pilot_mode: bool = True
    token_budget: int = Field(default=160000, ge=4000, le=200000)
    max_tool_calls: int = Field(default=5, ge=1, le=12)
    max_subagents: int = Field(default=2, ge=0, le=4)
    max_parallelism: int = Field(default=2, ge=1, le=4)


class WorkRoutineCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=12000)
    capability_id: str | None = None
    page_ref: str = Field(default="", max_length=1000)
    task_ref: str = Field(default="", max_length=1000)
    trigger: Literal["event", "schedule", "interval"]
    interval_seconds: int = Field(default=300, ge=60, le=31_536_000)
    schedule_config: dict[str, Any] = Field(default_factory=dict)
    cron: str = Field(default="", max_length=160)
    timezone: str = Field(default="Asia/Seoul", max_length=80)
    event_ref: str = Field(default="", max_length=1000)
    routine_stop: Literal["cancelled", "max_runs", "event_resolved"] = "cancelled"
    max_runs: int = Field(default=0, ge=0, le=10000)
    input: dict[str, Any] = Field(default_factory=dict)
    origin: Literal["user", "business_event", "verification"] = "user"
    surface_visibility: Literal["normal", "diagnostic"] = "normal"
    idempotency_key: str = Field(default="", max_length=256)


class WorkRoutineTriggerRequest(BaseModel):
    source_fingerprint: str = Field(default="", max_length=256)
    event_ref: str = Field(default="", max_length=1000)
    event_resolved: bool = False
    input: dict[str, Any] = Field(default_factory=dict)


class TokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[Literal["boi.read", "boi.draft", "boi.execute.low"]] = Field(
        default_factory=lambda: ["boi.read", "boi.draft"]
    )
    expires_in_days: int = Field(default=30, ge=1, le=90)


class SearchResponse(BaseModel):
    query: str
    mode: str
    items: list[EvidenceRef]
    ontology_terms: list[str] = Field(default_factory=list)
    degraded: list[str] = Field(default_factory=list)
    index_manifest: dict[str, Any] = Field(default_factory=dict)
