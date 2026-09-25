"""Synthetic helper closure for focused MCP release validation."""
from __future__ import annotations


import json


import shutil


from dataclasses import replace


from pathlib import Path


from typing import Any, Iterator


import pytest


import yaml


from boi_api.app.v2.config import AgentV2Settings


from boi_api.app.v2.models import (
    AgentTaskCancelRequest,
    AgentTaskClaimRequest,
    AgentTaskHeartbeatRequest,
    AgentTaskReleaseRequest,
    AgentTaskSubmitRequest,
    AgentSurfaceContext,
    AgentTurnRequest,
    AgentTurnResponse,
    AnswerabilityReport,
    AnswerBlock,
    ArtifactRef,
    CitationRef,
    CapabilityPlanRequest,
    CapabilityState,
    ContextItemUsage,
    ContextManifest,
    ContextPlaybookCreateRequest,
    ContextPlaybookPatchRequest,
    DeepJobRequest,
    DeepJobRestartRequest,
    EvidenceLedgerEntry,
    EvidenceRef,
    EventRuntimeActivationRequest,
    EventRuntimeDefinitionPreviewRequest,
    EventRuntimeSignalRequest,
    GraphQueryDraft,
    GraphQueryPlan,
    GroundedClaim,
    HarnessCandidateCreateRequest,
    HarnessCodePatchArtifactRequest,
    HarnessCandidateEvaluateRequest,
    HarnessCandidateReviewRequest,
    HarnessCandidateShadowRequest,
    HarnessVersionReleaseRequest,
    HarnessVersionRollbackRequest,
    HarnessCheck,
    HarnessResult,
    HelperActivateRequest,
    HelperDraftCreateRequest,
    HelperDraftPatchRequest,
    HelperPreviewTurnRequest,
    KnowledgeCandidatePatchRequest,
    KnowledgeCandidatePromoteRequest,
    KnowledgeHealthScanRequest,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceRollbackRequest,
    LegacyHelperImportRequest,
    LoopDelta,
    NoteFromTurnRequest,
    OntologyProposalCreateRequest,
    OntologyProposalPublishRequest,
    OntologyProposalReviewRequest,
    OntologyProjectionBinding,
    OntologyQueryRequest,
    OperationClass,
    OfferRequest,
    PlanConfirmRequest,
    Principal,
    ProposalApplyRequest,
    RiskLevel,
    SemanticPlan,
    SemanticPlanV4,
    SemanticEvidenceRequirements,
    SemanticSubject,
    SkillArtifactActivateRequest,
    SkillArtifactTestRequest,
    SkillInvocationPreviewRequest,
    SopArtifactPatchRequest,
    SourceSetPatchRequest,
    TaskMode,
    TokenCreateRequest,
    WorkSessionCreateRequest,
    WorkSessionPatchRequest,
    WorkRunContinueRequest,
    WorkIntent,
    WorkAssetKind,
    WorkOperation,
    WorkRunCancelRequest,
    WorkRoutineCreateRequest,
    WorkRoutineTriggerRequest,
    WorkContextPack,
    UsageRecord,
)


from boi_api.app.v2.service import (
    AgentV2Service,
    CapabilityHandlerContext,
    public_grounding_status,
    truncate_markdown,
)


ROOT = Path(__file__).resolve().parents[1]


def _is_semantic_planner_schema(schema: dict[str, Any]) -> bool:
    return "semantic_plan" in set(schema.get("required") or [])


class _PlannerEnvelope(dict[str, Any]):
    _semantic_aliases = {
        "topic_mode": "topic_action",
        "presentation_mode": "presentation",
        "graph_query_draft": "graph_query",
    }
    _continuation_aliases = {
        "continue_active_run": "continue_active_run",
        "continuation_kind": "delta_kind",
        "user_confirmation": "user_confirmation",
    }

    def _semantic_key(self, key: str) -> str:
        return self._semantic_aliases.get(key, key)

    def __setitem__(self, key: str, value: Any) -> None:
        semantic_key = self._semantic_key(key)
        if semantic_key in SemanticPlan.model_fields:
            dict.__getitem__(self, "semantic_plan")[semantic_key] = value
            return
        continuation_key = self._continuation_aliases.get(key)
        if continuation_key:
            dict.__getitem__(self, "continuation")[continuation_key] = value
            return
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> Any:
        semantic_key = self._semantic_key(key)
        if semantic_key in SemanticPlan.model_fields:
            return dict.__getitem__(self, "semantic_plan")[semantic_key]
        continuation_key = self._continuation_aliases.get(key)
        if continuation_key:
            return dict.__getitem__(self, "continuation")[continuation_key]
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def update(self, other: Any = None, /, **kwargs: Any) -> None:
        values = dict(other or {})
        values.update(kwargs)
        for key, value in values.items():
            self[key] = value


def _planner_envelope(plan: dict[str, Any]) -> _PlannerEnvelope:
    return _PlannerEnvelope(
        {
            "semantic_plan": dict(plan),
            "grounded_answer": {
                "summary": "",
                "summary_source_refs": [],
                "claims": [],
                "unresolved_claims": [],
                "outcomes": [],
                "related_questions": [],
            },
            "continuation": {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
            },
        }
    )


class ScriptedPlanner:
    provider = "test"

    def __init__(
        self,
        plans: list[dict[str, Any]] | None = None,
        *,
        clarifications: list[str] | None = None,
    ):
        self.plans = [dict(item) for item in (plans or [])]
        self.clarifications = list(clarifications or [])

    def readiness(self) -> dict[str, Any]:
        return {
            "configured": True,
            "generation": True,
            "streaming": True,
            "embeddings": False,
            "provider": self.provider,
            "model": "test-model",
            "embedding_model": "",
        }

    def preflight(self) -> dict[str, Any]:
        return {**self.readiness(), "ok": True}

    def evaluate_semantic_plan(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {"status": "aligned", "issues": [], "clarification_question": ""}

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            plans = getattr(self, "plans", [])
            semantic_plan = plans.pop(0) if plans else SemanticPlan(
                    resolved_goal="검증된 내부 지식을 근거로 요청을 이해한다",
                    retrieval_query="검증된 내부 지식",
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="understand",
                    evidence_scope="canonical",
                    presentation="prose",
                    confidence=1.0,
                ).model_dump(mode="json")
            return _planner_envelope(semantic_plan)
        if required == {"clarification_question"}:
            clarifications = getattr(self, "clarifications", [])
            if not clarifications:
                raise AssertionError("no scripted clarification was supplied")
            return {"clarification_question": clarifications.pop(0)}
        if required == {"status", "issues", "clarification_question"}:
            return {
                "status": "aligned",
                "issues": [],
                "clarification_question": "",
            }
        if required == {"verdicts"}:
            claims = [item for item in json.loads(prompt).get("claims") or [] if isinstance(item, dict)]
            return {
                "verdicts": [
                    {
                        "claim_id": str(item.get("claim_id") or ""),
                        "support_status": "supported",
                        "confidence": 1.0,
                    }
                    for item in claims
                ]
            }
        if "skill_id" in required:
            return {
                "skill_id": "operations.evidence-helper",
                "title": "업무 근거 도우미",
                "description": "관련 근거와 종료 기준을 찾습니다.",
                "invocation_mode": "guide_only",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "permissions": ["boi.viewer"],
                "tests": [
                    {
                        "name": "find evidence",
                        "sample_input": {"request": "업무 근거를 찾아줘"},
                        "expected_contains": ["evidence_refs"],
                    }
                ],
                "available_actions": [],
            }
        raise AssertionError(f"unexpected schema: {required}")

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        yield "test"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("test embedding intentionally unavailable")


def _write_markdown(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body,
        encoding="utf-8",
    )


@pytest.fixture()
def v2_service(tmp_path: Path) -> AgentV2Service:
    content = tmp_path / "boi"
    runtime = tmp_path / "runtime"
    seed = tmp_path / "seed"
    catalog = tmp_path / "agent_catalog"
    catalog.mkdir()
    shutil.copy(ROOT / "data" / "agent_catalog" / "capabilities-v2.yaml", catalog / "capabilities-v2.yaml")
    shutil.copy(ROOT / "data" / "agent_catalog" / "draft-contracts-v2.yaml", catalog / "draft-contracts-v2.yaml")
    shutil.copy(ROOT / "data" / "agent_catalog" / "harnesses-v2.yaml", catalog / "harnesses-v2.yaml")

    _write_markdown(
        content / "public" / "guide.md",
        {
            "type": "boi/manual",
            "title": "BoI Wiki 운영 가이드",
            "description": "문서, SOP, Event와 Action을 연결하는 검토된 운영 기준",
            "boi_id": "boi:public:guide",
            "visibility": "public",
            "status": "reviewed",
            "timestamp": "2026-07-01T00:00:00+09:00",
            "agent_entrypoint_areas": ["knowledge"],
            "agent_entrypoint_prompts": {
                "knowledge": {
                    "label": "BoI Wiki 운영 가이드부터 살펴보기",
                    "prompt": "BoI Wiki 운영 가이드의 핵심과 실제 연결 관계를 근거와 함께 설명해줘.",
                    "reason": "검토된 공용 지식에서 시작합니다.",
                }
            },
        },
        "업무 지식과 실행 근거를 연결하고, 초안은 검토 후 게시합니다.",
    )
    _write_markdown(
        content / "public" / "manual-task.md",
        {
            "type": "boi/sop",
            "title": "사람 검토 SOP",
            "boi_id": "boi:public:sop:manual",
            "visibility": "public",
            "status": "reviewed",
            "tasks": [
                {
                    "task_id": "review-task",
                    "execution_mode": "manual",
                    "exit_criteria": ["사람이 필수 근거를 확인하고 판단을 기록한다"],
                    "required_evidence": ["review_note"],
                },
                {
                    "task_id": "auto-task",
                    "execution_mode": "autopilot",
                    "exit_criteria": ["설비 Alarm 접수 결과가 확인되었어요"],
                    "required_evidence": ["equipment.alarm.accepted.v1"],
                    "completion_design": {
                        "version": 1,
                        "checks": [
                            {
                                "check_id": "alarm-accepted",
                                "label": "설비 Alarm 접수 결과가 확인되었어요",
                                "confirmation": "system",
                                "binding": {
                                    "kind": "event",
                                    "ref": "equipment.alarm.accepted.v1",
                                },
                            }
                        ],
                        "evidence": [
                            {
                                "evidence_id": "alarm-event",
                                "label": "설비 Alarm 접수 결과",
                                "source_kind": "event",
                                "ref": "equipment.alarm.accepted.v1",
                                "provided_by": "system",
                                "required": True,
                            }
                        ],
                    },
                },
            ],
        },
        "사람이 근거를 검토합니다.",
    )
    _write_markdown(
        content / "public" / "dictionary-cross-section.md",
        {
            "type": "boi/dictionary-term",
            "title": "Cross Section Inspection",
            "boi_id": "boi:public:dictionary:cross-section-inspection",
            "visibility": "public",
            "status": "reviewed",
            "aliases": ["단면검사", "단면 검사"],
            "related_terms": ["Inspection"],
        },
        "제품 단면을 관찰해 결함을 판단하는 검사입니다.",
    )
    _write_markdown(
        content / "public" / "evidence-skill.md",
        {
            "type": "boi/skill",
            "title": "근거 검증 Skill",
            "description": "필수 근거와 종료 기준을 점검합니다.",
            "boi_id": "boi:public:skill:evidence-validation",
            "visibility": "public",
            "status": "reviewed",
        },
        "근거 누락을 확인합니다.",
    )
    _write_markdown(
        content / "public" / "smoke-draft.md",
        {
            "type": "boi/skill",
            "title": "Smoke Skill Draft",
            "boi_id": "boi:public:skill:smoke",
            "visibility": "public",
            "status": "draft",
        },
        "이 문서는 기본 검색 결과에 나오면 안 됩니다.",
    )
    _write_markdown(
        content / "public" / "related-draft.md",
        {
            "type": "boi/manual",
            "title": "검증 중 관계 가이드",
            "boi_id": "boi:public:guide:related-draft",
            "visibility": "public",
            "status": "draft",
            "relationships": [
                {
                    "relation": "guides",
                    "target": "boi:public:guide",
                    "label": "검증 중인 안내 관계",
                }
            ],
        },
        "검증이 끝나기 전에는 검색 정본으로 사용하지 않습니다.",
    )
    _write_markdown(
        content / "private" / "100001" / "note.md",
        {
            "type": "boi/reference",
            "title": "내 Alarm 검토 메모",
            "boi_id": "boi:private:100001:alarm-note",
            "visibility": "private",
            "owner": "100001",
            "status": "reviewed",
        },
        "Alarm 대응 시 종료 기준과 근거를 확인합니다.",
    )
    _write_markdown(
        content / "private" / "100002" / "secret.md",
        {
            "type": "boi/reference",
            "title": "다른 사람 비공개 메모",
            "boi_id": "boi:private:100002:secret",
            "visibility": "private",
            "owner": "100002",
            "status": "reviewed",
        },
        "보이면 안 되는 내용",
    )

    for root, key, filename in (
        (tmp_path / "events_catalog", "event_types", "event_types.yaml"),
        (tmp_path / "actions_catalog", "actions", "actions.yaml"),
        (tmp_path / "workflow_catalog", "workflows", "workflows.yaml"),
        (tmp_path / "skill_catalog", "action_skills", "skills.yaml"),
    ):
        root.mkdir()
        (root / filename).write_text(yaml.safe_dump({key: []}), encoding="utf-8")

    (runtime / "actions").mkdir(parents=True)
    (runtime / "actions" / "actions-20260710.jsonl").write_text(
        json.dumps(
            {
                "request_id": "active-work-1",
                "employee_id": "100001",
                "action_key": "manual.review",
                "title": "현재 근거 검토",
                "status": "pending_confirmation",
                "summary": "현재 처리해야 하는 업무",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (seed / "actions").mkdir(parents=True)
    (seed / "actions" / "actions-20260601.jsonl").write_text(
        json.dumps(
            {
                "request_id": "history-work-1",
                "employee_id": "100001",
                "action_key": "manual.review",
                "title": "과거 Alarm 조치 사례",
                "status": "completed",
                "summary": "과거 근거 검토와 조치 결과",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        content_root=content,
        runtime_root=runtime,
        history_seed_root=seed,
        agent_catalog_root=catalog,
        event_catalog_root=tmp_path / "events_catalog",
        action_catalog_root=tmp_path / "actions_catalog",
        workflow_catalog_root=tmp_path / "workflow_catalog",
        action_skill_catalog_root=tmp_path / "skill_catalog",
        database_dsn=__import__("os").environ.get("BOI_RELEASE_TEST_PG_DSN", ""),
        require_postgres=False,
        model_api_key="",
        model_name="",
        embedding_model="",
        pat_hash_secret="test-pat-secret",
        independent_review=False,
    )
    service = AgentV2Service(settings)
    planner = ScriptedPlanner()
    service.model = planner
    service.search.model = planner
    # Production local-full builds the versioned Ontology read model through
    # the explicit/background reconcile path. Unit tests that exercise graph,
    # starter, and Person projections must model that ready-state precondition
    # now that a user query is forbidden from rebuilding the graph itself.
    service.knowledge.compile_graph(
        Principal(
            employee_id="100001",
            display_name="Test User",
            teams=["aix-tf"],
            roles=[
                "boi.viewer",
                "boi.editor",
                "boi.workflow_runner",
                "boi.action_invoker",
            ],
            auth_source="test",
            token_scopes=["boi.read", "boi.draft", "boi.execute.low"],
        )
    )
    return service


@pytest.fixture()
def principal() -> Principal:
    return Principal(
        employee_id="100001",
        display_name="Test User",
        teams=["aix-tf"],
        roles=["boi.viewer", "boi.editor", "boi.workflow_runner", "boi.action_invoker"],
        auth_source="test",
        token_scopes=["boi.read", "boi.draft", "boi.execute.low"],
    )
