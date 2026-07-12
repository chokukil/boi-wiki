from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class LoopPolicy(BaseModel):
    """Execution limits and stop conditions, independent of semantic intent routing."""

    kind: LoopKind = LoopKind.turn
    trigger: LoopTriggerKind = LoopTriggerKind.user
    task_stop: Literal["agent_done", "exit_criteria", "needs_context"] = "agent_done"
    routine_stop: Literal["one_shot", "cancelled", "max_runs", "event_resolved"] = "one_shot"
    max_iterations: int = Field(default=5, ge=1, le=20)
    max_no_progress: int = Field(default=1, ge=1, le=3)
    max_tool_loops: int = Field(default=5, ge=1, le=20)
    max_runs: int = Field(default=1, ge=0, le=10000)
    interval_seconds: int = Field(default=0, ge=0, le=31_536_000)
    adaptive_backoff: bool = True
    source_fingerprint: str = Field(default="", max_length=256)
    routine_id: str = Field(default="", max_length=120)


class CapabilityState(str, Enum):
    ready = "ready"
    needs_input = "needs_input"
    unavailable = "unavailable"


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    version: str = "1.0"
    title: str
    description: str
    primary_asset: WorkAssetKind = WorkAssetKind.knowledge
    supported_assets: list[WorkAssetKind] = Field(default_factory=lambda: list(WorkAssetKind))
    examples: list[str] = Field(default_factory=list)
    operation: OperationClass
    risk: RiskLevel = RiskLevel.low
    task_modes: list[TaskMode] = Field(default_factory=lambda: list(TaskMode))
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    context_recipe: list[str] = Field(default_factory=list)
    evidence_policy: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
    handler: str
    renderer: str = "answer"
    permissions: list[str] = Field(default_factory=lambda: ["boi.viewer"])
    readiness: list[str] = Field(default_factory=list)
    external: bool = True
    deep: bool = False

    @field_validator("capability_id")
    @classmethod
    def validate_capability_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in clean):
            raise ValueError("capability_id must be a lowercase dotted identifier")
        return clean


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


class StarterSuggestionSetRequest(BaseModel):
    page_ref: str = Field(default="", max_length=1000)
    work_session_id: str = Field(default="", max_length=120)


class GoalStep(BaseModel):
    step_id: str
    capability_id: str
    label: str
    operation: Literal["read", "draft", "deep", "guarded"] = "read"
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


class ContextManifest(BaseModel):
    selected_refs: list[str] = Field(default_factory=list, max_length=12)
    excluded_refs: list[str] = Field(default_factory=list, max_length=100)
    exclusion_reasons: dict[str, str] = Field(default_factory=dict)
    pinned_refs: list[str] = Field(default_factory=list, max_length=100)
    chunk_refs: list[str] = Field(default_factory=list, max_length=24)
    external_refs: list[str] = Field(default_factory=list, max_length=20)
    source_revision: str = ""
    token_budget: int = Field(default=0, ge=0)
    policies: list[Literal["write", "select", "compress", "isolate"]] = Field(
        default_factory=lambda: ["write", "select", "compress", "isolate"]
    )
    raw_content_in_prompt: bool = False
    provenance: dict[str, dict[str, str]] = Field(default_factory=dict)


class GraphQueryDraft(BaseModel):
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


class WorkIntent(BaseModel):
    goal: str
    resolved_goal: str = ""
    retrieval_query: str = ""
    asset_kind: WorkAssetKind = WorkAssetKind.knowledge
    operation: WorkOperation = WorkOperation.understand
    operation_plan: list[WorkOperation] = Field(default_factory=lambda: [WorkOperation.understand])
    target_ref: str = ""
    scope: Literal["auto", "current", "wiki", "selected"] = "auto"
    desired_outcome: str = "answer"
    presentation_mode: Literal["prose", "mermaid", "table", "timeline", "explorer", "artifact"] = "prose"
    work_view: Literal["none", "current", "responsibility", "combined"] = "none"
    graph_query_draft: GraphQueryDraft | None = None
    context_refs: list[str] = Field(default_factory=list, max_length=20)
    result_purpose: Literal["explain", "compare", "design", "transform", "execute"] = "explain"
    requested_asset_kinds: list[WorkAssetKind] = Field(default_factory=list, max_length=9)
    artifact_actions: list[Literal["split_tasks", "create_sop_draft"]] = Field(default_factory=list, max_length=2)
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
    related_questions: list[RelatedQuestion] = Field(default_factory=list, max_length=3)
    grounding_status: Literal["grounded", "partial", "no_evidence"] = "no_evidence"
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


class KnowledgeSourceDefinition(BaseModel):
    source_id: str
    name: str
    source_kind: Literal["okf_markdown", "git", "data_lake", "graphify", "codegraph", "external_cli"]
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
    source_kind: Literal["data_lake", "graphify", "codegraph", "external_cli"]
    location: str = Field(default="", max_length=2000)
    visibility: Literal["private", "team", "public"] = "private"
    team_id: str = Field(default="", max_length=120)
    sync_policy: Literal["manual", "on_change", "scheduled"] = "manual"
    adapter_config: dict[str, Any] = Field(default_factory=dict)


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
    capability_id: str = "deep.research"
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
