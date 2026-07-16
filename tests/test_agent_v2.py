from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boi_api.app.v2.config import AgentV2Settings
from boi_api.app.v2.capabilities import CapabilityRegistry
from boi_api.app.v2.domain import DomainServiceGateway
from boi_api.app.v2.entity_resolver import AmbiguousEntityError, EntityResolver
from boi_api.app.v2.evaluation import IndependentArtifactEvaluator
from boi_api.app.v2.model_gateway import (
    ConcurrencyLimitedGenerationGateway,
    OpenAICompatibleGateway,
    UnavailableModelGateway,
    UsageTrackingGateway,
    _record_provider_usage,
    begin_model_usage,
    build_model_gateway,
    ensure_lmstudio_model_residency,
    finish_model_usage,
    inspect_model_runtime_profile,
    require_lmstudio_models_preloaded,
    resolve_context_budget,
    update_model_usage_limits,
)
from boi_api.app.v2.models import (
    AgentTurnRequest,
    AgentTurnResponse,
    AnswerabilityReport,
    AnswerBlock,
    ArtifactRef,
    CitationRef,
    ContextItemUsage,
    ContextManifest,
    ContextPlaybookCreateRequest,
    ContextPlaybookPatchRequest,
    DeepJobRequest,
    EvidenceRef,
    GraphQueryDraft,
    GraphQueryPlan,
    GroundedClaim,
    HarnessCandidateCreateRequest,
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
    KnowledgeCandidatePromoteRequest,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceRollbackRequest,
    LegacyHelperImportRequest,
    LoopDelta,
    NoteFromTurnRequest,
    OperationClass,
    OfferRequest,
    Principal,
    RiskLevel,
    SemanticPlan,
    SemanticSubject,
    SkillArtifactActivateRequest,
    SkillArtifactTestRequest,
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
    WorkRoutineCreateRequest,
    WorkRoutineTriggerRequest,
    WorkContextPack,
)
from boi_api.app.v2.policy import TaskPolicy
from boi_api.app.v2.quick_agent import QuickAgentRuntime
from boi_api.app.v2.repository import KnowledgeRecord, KnowledgeRepository
from boi_api.app.v2.rendering import render_agent_markdown
from boi_api.app.v2.routes import build_agent_v2_router
from boi_api.app.v2.search import (
    chunks_for_record,
    context_anchor_score,
    diversify_ranked,
    graph_score,
    identity_score,
    lexical_score,
)
from boi_api.app.v2.service import AgentV2Service, truncate_markdown
from boi_api.app.v2.semantic_kernel import PlanCompiler, PlanValidator, SemanticPlanningError
from boi_api.app.v2.store import PostgresAgentV2Store, now_iso
from boi_api.app.v2.worker import (
    DeepWorkRunner,
    build_deep_context_brief,
    ensure_exact_evidence_ledger,
    latest_assistant_text,
)
from boi_api.app.task_completion import normalise_task_completion


ROOT = Path(__file__).resolve().parents[1]


def _catalog_loop_contract(capability_id: str):
    """Use the production catalog contract in planner fixtures.

    Semantic validity belongs to the catalog, so tests should not duplicate
    capability-to-loop routing rules in Python.
    """
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    return registry.get(capability_id).default_loop_contract.model_copy(deep=True)


def test_capability_registry_rejects_unimplemented_mutation_handlers_before_turn_execution():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    read_definition = registry.get("knowledge.search")

    assert registry.handler_supported(read_definition) is True
    assert registry.handler_supported(read_definition.model_copy(update={"handler": "missing_plugin"})) is False


def test_versioned_loop_contracts_leave_capacity_for_repair_and_fresh_evaluation():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    turn = registry.get("knowledge.search").default_loop_contract
    goal = registry.get("task.work").default_loop_contract

    assert turn.max_context_tokens == 0
    assert turn.max_model_calls >= 4
    assert turn.max_elapsed_seconds >= 180
    assert goal.max_context_tokens == 0
    assert goal.max_model_calls >= turn.max_model_calls
    assert goal.max_elapsed_seconds >= turn.max_elapsed_seconds


def test_semantic_planner_schema_bounds_internal_refs_to_acl_visible_context():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    runtime = QuickAgentRuntime(registry=registry)
    schema = runtime._planner_schema(
        {
            "conversation_context": {"recent_source_refs": ["boi:public:guide"]},
            "knowledge_hints": [{"ref": "boi:team:runbook"}],
            "trusted_targets": {"person": "person:100001"},
        }
    )
    plan_properties = schema["properties"]["semantic_plan"]["properties"]
    subject_properties = plan_properties["subjects"]["items"]["properties"]

    assert subject_properties["entity_ref"]["enum"] == [
        "",
        "boi:public:guide",
        "boi:team:runbook",
        "person:100001",
    ]
    assert plan_properties["target_ref"]["enum"] == subject_properties["entity_ref"]["enum"]
    assert plan_properties["context_refs"]["items"]["enum"] == subject_properties["entity_ref"]["enum"][1:]
    assert "concept" in subject_properties["entity_kind"]["enum"]
    assert "topic_action" in schema["properties"]["semantic_plan"]["required"]
    assert "reference_resolution" in schema["properties"]["semantic_plan"]["required"]
    assert "uniquely identifies exactly one" in plan_properties["reference_resolution"]["description"]
    assert plan_properties["reference_resolution"]["enum"] == ["none"]
    assert "current assignments as separate sections" in plan_properties["work_view"]["description"]
    assert "presentation" in schema["properties"]["semantic_plan"]["required"]
    assert "continuation" not in schema["properties"]["semantic_plan"]["required"]
    assert set(subject_properties) == set(plan_properties["subjects"]["items"]["required"])
    answer_properties = schema["properties"]["grounded_answer"]["properties"]
    claim_properties = answer_properties["claims"]["items"]["properties"]
    assert claim_properties["source_refs"]["minItems"] == 1
    assert claim_properties["source_refs"]["items"]["enum"] == ["S1"]
    assert claim_properties["supporting_chunk_ids"]["items"]["enum"] == ["C1"]

    graph_schema = plan_properties["graph_query"]["anyOf"][0]["properties"]
    graph_contract = registry.graph_query_filter_contract
    assert graph_schema["node_kinds"]["items"]["enum"] == graph_contract.node_kinds
    assert graph_schema["relation_kinds"]["items"]["enum"] == graph_contract.relation_kinds
    assert "neighbors" not in graph_schema["relation_kinds"]["items"]["enum"]

    continued_schema = runtime._planner_schema(
        {
            "conversation_context": {
                "topic_state": {"entities": ["boi:public:a", "boi:public:b"]},
            },
        }
    )
    continued_resolution = continued_schema["properties"]["semantic_plan"]["properties"][
        "reference_resolution"
    ]
    assert continued_resolution["enum"] == ["none", "all", "specific", "ambiguous"]

    search_contract = next(
        item for item in runtime._capability_catalog() if item["capability_id"] == "knowledge.search"
    )
    assert search_contract["work_view_operation_contracts"]["combined"] == ["connect", "validate"]

    cases_contract = next(
        item for item in runtime._capability_catalog() if item["capability_id"] == "cases.similar"
    )
    assert cases_contract["semantic_operation_contracts"]["compare"]["graph_query_kinds"] == []
    assert "compare" not in cases_contract["graph_query_kinds"]


class _ReferenceAssessmentModel:
    def __init__(self, status: str):
        self.status = status

    def generate_structured(self, *, prompt: str, schema: dict[str, Any], **_: Any) -> dict[str, Any]:
        payload = json.loads(prompt)
        assert len(payload["prior_subjects"]) == 2
        selected_ref = payload["planner_selected_ref"]
        return {
            "status": self.status,
            "selected_ref": selected_ref if self.status == "justified" else "",
            "clarification_question": "어느 항목을 말씀하시나요?" if self.status == "ambiguous" else "",
        }


def test_specific_reference_uses_independent_semantic_evaluation_for_multiple_prior_subjects():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    runtime = QuickAgentRuntime(registry=registry)
    refs = ["boi:public:concept:a", "boi:public:concept:b"]
    state = {
        "question": "선택한 항목의 실제 사용 부분을 보여줘.",
        "conversation_context": {"topic_state": {"entities": refs}},
        "knowledge_hints": [
            {"ref": refs[0], "title": "개념 A"},
            {"ref": refs[1], "title": "개념 B"},
        ],
    }
    plan = SemanticPlan(
        resolved_goal="선택한 개념의 실제 사용 범위를 확인한다",
        retrieval_query="선택한 개념 실제 사용 범위",
        topic_action="continue",
        reference_resolution="specific",
        subjects=[
            SemanticSubject(
                mention="개념 A",
                entity_ref=refs[0],
                entity_kind="concept",
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        presentation="prose",
        context_refs=[refs[0]],
        target_ref=refs[0],
    )
    envelope = {"semantic_plan": plan.model_dump(mode="json")}

    with pytest.raises(SemanticPlanningError) as ambiguous:
        runtime._validate_envelope(
            state,
            envelope,
            model=_ReferenceAssessmentModel("ambiguous"),
        )
    assert ambiguous.value.report is not None
    assert {item.code for item in ambiguous.value.report.issues} == {
        "topic.specific_reference_not_justified"
    }

    validated, report = runtime._validate_envelope(
        state,
        envelope,
        model=_ReferenceAssessmentModel("justified"),
    )
    assert validated.reference_resolution == "specific"
    assert report["valid"] is True


def test_plan_validator_rejects_graph_filters_outside_the_catalog_contract_without_rewriting():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    validator = PlanValidator(registry)
    plan = SemanticPlan(
        resolved_goal="검증된 업무 관계를 탐색한다",
        retrieval_query="업무 관계",
        capability_id="knowledge.connect",
        user_effect="read",
        operation="connect",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="neighbors",
            focal_mentions=["boi:public:guide"],
            relation_kinds=["neighbors"],
            presentation="explorer",
        ),
        confidence=1.0,
    )

    report = validator.validate(plan)

    assert report.valid is False
    assert {item.code for item in report.issues} >= {"graph.relation_kind_unknown"}
    assert plan.graph_query is not None
    assert plan.graph_query.relation_kinds == ["neighbors"]


def test_postgres_store_registers_every_helper_builder_collection():
    assert PostgresAgentV2Store.COLLECTION_TABLES["helper_drafts"] == "agent_helper_drafts"
    assert PostgresAgentV2Store.COLLECTION_TABLES["helpers"] == "agent_helpers"
    assert PostgresAgentV2Store.COLLECTION_TABLES["skills"] == "agent_skills"
    assert PostgresAgentV2Store.COLLECTION_TABLES["semantic_routes"] == "agent_semantic_routes"
    assert PostgresAgentV2Store.COLLECTION_TABLES["starter_suggestion_sets"] == "agent_starter_suggestion_sets"
    assert PostgresAgentV2Store.COLLECTION_TABLES["user_work_profiles"] == "agent_user_work_profiles"
    assert PostgresAgentV2Store.COLLECTION_TABLES["a2ui_surfaces"] == "agent_a2ui_surfaces"
    assert PostgresAgentV2Store.COLLECTION_TABLES["knowledge_source_jobs"] == "knowledge_source_jobs"


def test_response_budget_preserves_minimal_intent_citation_and_truthful_grounding(v2_service: AgentV2Service):
    response = AgentTurnResponse(
        run_id="run-budget",
        turn_id="turn-budget",
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="업무 맥락 설명", markdown=("업무 맥락과 판단 근거를 설명합니다. " * 500) + "\n\n[1](/api/v2/citations/cite_budget)"),
        citations=[
            CitationRef(
                citation_id="cite_budget",
                source_ref="boi:public:guide",
                title="운영 가이드",
                excerpt="근거 " * 500,
            )
        ],
        work_intent=WorkIntent(
            goal="현재 문서의 판단 기준 설명",
            resolved_goal="현재 운영 가이드의 업무 맥락 판단 기준을 설명한다",
        ),
        artifact_refs=[
            ArtifactRef(
                artifact_id="artifact-budget",
                artifact_type="ontology_graph",
                title="업무 관계",
                preview="관계 미리보기 " * 500,
                metadata={"revision": 1, "presentation": "timeline", "source_refs": ["boi:public:guide"] * 50},
            )
        ],
        grounding_status="grounded",
        answerability=AnswerabilityReport(
            status="grounded",
            answer_intent="fact",
            supported_claim_count=1,
        ),
        grounded_claims=[
            GroundedClaim(
                claim_id="claim-budget",
                text="운영 가이드는 업무 맥락과 판단 근거를 설명합니다.",
                source_refs=["boi:public:guide"],
                supporting_chunk_ids=["boi:public:guide#body-0"],
                support_status="supported",
                confidence=1.0,
                required_for_answer=True,
            )
        ],
        semantic_plan_ref="semantic-plan-budget",
        topic_state_ref="topic-state-budget",
        a2ui_surface_ref="surface-budget",
        graph_result_ref="graph-budget",
        context_usage={"page_anchor": {"ref": "boi:public:guide", "resolved": True}, "selected_source_count": 12},
    )
    compact = v2_service._enforce_response_budget(response)
    assert compact.work_intent is not None
    assert compact.work_intent.operation.value == "understand"
    assert compact.citations and compact.citations[0].source_ref == "boi:public:guide"
    assert compact.artifact_refs[0].metadata["presentation"] == "timeline"
    assert compact.grounding_status == "grounded"
    assert compact.semantic_plan_ref == "semantic-plan-budget"
    assert compact.topic_state_ref == "topic-state-budget"
    assert compact.a2ui_surface_ref == "surface-budget"
    assert compact.graph_result_ref == "graph-budget"
    assert len(json.dumps(compact.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")) <= v2_service.settings.response_budget_bytes


def test_plan_validator_rejects_effect_operation_conflicts_without_rewriting_the_plan():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    validator = PlanValidator(registry)
    plan = SemanticPlan(
        resolved_goal="Action 실행 요청 초안을 만든다",
        retrieval_query="Action 실행 계약",
        capability_id="action.plan",
        user_effect="read",
        operation="create",
        confidence=1.0,
    )

    report = validator.validate(plan)

    assert report.valid is False
    assert {item.code for item in report.issues} >= {"effect.operation_conflict"}
    assert plan.capability_id == "action.plan"
    assert plan.operation == WorkOperation.create


def test_planner_read_purpose_cannot_compile_to_a_draft_operation(v2_service: AgentV2Service):
    class InconsistentDraftModel(ScriptedPlanner):
        def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            value = super().generate_structured(system=system, prompt=prompt, schema=schema)
            required = set(schema.get("required") or [])
            if "semantic_plan" in required:
                value["semantic_plan"].update(
                    {
                        "capability_id": "business_event.plan",
                        "operation": "create",
                        "answer_intent": "procedure",
                    }
                )
            return value

    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service.quick_agent.route(
            "업무 기준을 설명해줘",
            page_kind="event",
            model=InconsistentDraftModel(),
        )

    assert exc_info.value.code == "planner_invalid"
    assert exc_info.value.report is not None
    assert {item.code for item in exc_info.value.report.issues} >= {"effect.operation_conflict"}


def test_plan_compiler_preserves_a_valid_capability_operation_effect_and_subject():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    compiler = PlanCompiler(registry)
    plan = SemanticPlan(
        resolved_goal="현재 사용자에게 배정된 업무를 확인한다",
        retrieval_query="현재 사용자 배정 업무",
        capability_id="work.inbox",
        user_effect="read",
        operation="observe",
        work_view="current",
        confidence=1.0,
    )

    compiled = compiler.compile(plan, original_question="지금 처리할 업무만 보여줘")

    assert compiled.capability_id == "work.inbox"
    assert compiled.work_intent.operation == WorkOperation.observe
    assert compiled.work_intent.work_view == "current"


def test_catalog_only_read_capability_executes_without_service_routing_change(
    v2_service: AgentV2Service,
    principal: Principal,
):
    catalog_path = v2_service.registry.catalog_path
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    template = next(
        item for item in catalog["capabilities"] if item["handler"] == "grounded_read"
    )
    catalog["capabilities"].append(
        {
            **template,
            "capability_id": "test.unseen_asset",
            "title": "테스트용 미지 자산 읽기",
            "description": "카탈로그만으로 추가되는 내부 지식 읽기 자산",
            "examples": [],
            "starter_offers": [],
        }
    )
    catalog_path.write_text(
        yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    v2_service.registry.reload()

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 운영 가이드의 검토 기준을 설명해줘",
            capability_id="test.unseen_asset",
        ),
    )

    assert response.capability_id == "test.unseen_asset"
    assert response.error_code == ""
    assert response.work_intent is not None
    assert response.work_intent.operation == WorkOperation.understand


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_disposition"),
    [
        (
            SemanticPlanningError("planner_unavailable", "planner offline"),
            "failed",
            "transient_retry",
        ),
        (
            SemanticPlanningError("planner_invalid", "repair failed"),
            "failed",
            "semantic_repair",
        ),
        (
            SemanticPlanningError(
                "planner_invalid",
                "ambiguous subject",
                clarification_question="어느 업무를 말씀하시는지 선택해주세요.",
            ),
            "needs_input",
            "human_interrupt",
        ),
    ],
)
def test_planning_failures_preserve_typed_error_disposition(
    v2_service: AgentV2Service,
    principal: Principal,
    error: SemanticPlanningError,
    expected_status: str,
    expected_disposition: str,
):
    session = v2_service.create_work_session(
        principal,
        WorkSessionCreateRequest(title="계획 오류 분류"),
    )
    response = v2_service._planning_failure_response(
        principal=principal,
        session=session,
        request=AgentTurnRequest(question="업무 요청"),
        run_id="run-planning-disposition",
        turn_id="turn-planning-disposition",
        error=error,
    )

    assert response.status == expected_status
    assert response.stop_reason == expected_disposition
    stored = v2_service.store.get("runs", response.run_id)
    assert stored["error_disposition"] == expected_disposition


def test_plan_validator_rejects_work_run_continuation_outside_the_semantic_contract_context():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    validator = PlanValidator(registry)
    plan = SemanticPlan.model_validate(
        {
            **_task_completion_plan("review-task"),
            "topic_action": "continue",
            "reference_resolution": "specific",
            "subjects": [
                {
                    "mention": "진행 중 Task",
                    "entity_ref": "review-task",
                    "entity_kind": "task",
                    "resolution": "resolved",
                }
            ],
            "continuation": {
                "continue_active_run": True,
                "delta_kind": "human_input",
                "user_confirmation": True,
                "work_record": {"observations": "자료를 확인했습니다."},
            },
        }
    )

    report = validator.validate(
        plan,
        trusted_context_refs={"review-task"},
        prior_topic_entities=["review-task"],
        active_work_run=False,
    )

    assert report.valid is False
    assert "continuation.active_run_missing" in {item.code for item in report.issues}


def test_work_run_continuation_never_rewrites_an_invalid_delta_to_human_input(
    v2_service: AgentV2Service,
    principal: Principal,
):
    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service._continue_active_work_from_turn(
            principal=principal,
            request=AgentTurnRequest(question="계속 진행해줘"),
            session={"session_id": "session-invalid-continuation"},
            active_work_run={"work_run_id": "workrun-invalid-continuation"},
            route={
                "semantic_plan": {
                    "resolved_goal": "기존 업무를 이어간다",
                    "retrieval_query": "기존 업무 진행 상태",
                    "topic_action": "continue",
                    "reference_resolution": "specific",
                    "capability_id": "task.work",
                    "user_effect": "execute",
                    "operation": "complete",
                    "continuation": {
                        "continue_active_run": True,
                        "delta_kind": "none",
                    },
                }
            },
            run_id="run-invalid-continuation",
            turn_id="turn-invalid-continuation",
        )

    assert exc_info.value.code == "planner_invalid"


def _is_semantic_planner_schema(schema: dict[str, Any]) -> bool:
    return "semantic_plan" in set(schema.get("required") or [])


def _has_verified_topic_state(payload: dict[str, Any]) -> bool:
    topic_state = payload.get("verified_topic_state")
    if not isinstance(topic_state, dict):
        return False
    return bool(
        topic_state.get("topic_state_ref")
        or topic_state.get("entities")
        or topic_state.get("claims")
    )


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


class EmptyThenGroundedRepairModel(ScriptedPlanner):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if _is_semantic_planner_schema(schema):
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="Work Learning Loop의 내부 정의를 설명한다",
                    retrieval_query="Work Learning Loop 내부 정의",
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="understand",
                    evidence_scope="canonical",
                    presentation="prose",
                    answer_intent="definition",
                    confidence=1.0,
                ).model_dump(mode="json")
            )
        if set(schema.get("required") or []) == {
            "summary",
            "summary_source_refs",
            "claims",
            "outcomes",
            "related_questions",
        }:
            return {
                "summary": "Work Learning Loop는 검증된 결과를 다음 업무에 재사용하는 순환입니다.",
                "summary_source_refs": ["S1"],
                "claims": [
                    {
                        "claim_id": "loop-definition",
                        "text": "Work Learning Loop는 검증된 결과를 다음 업무에 재사용하는 순환입니다.",
                        "claim_kind": "definition",
                        "source_scope": "canonical",
                        "source_refs": ["S1"],
                        "supporting_chunk_ids": ["C1"],
                        "required_for_answer": True,
                    }
                ],
                "outcomes": [],
                "related_questions": [],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class EmptyGraphAnswerModel(EmptyThenGroundedRepairModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if _is_semantic_planner_schema(schema):
            self.calls += 1
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="Work Learning Loop의 검증된 연결 관계를 탐색한다",
                    retrieval_query="Work Learning Loop 검증된 연결 관계",
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="connect",
                    evidence_scope="canonical",
                    presentation="explorer",
                    answer_intent="relationship",
                    graph_query=GraphQueryDraft(
                        enabled=True,
                        query_kind="neighbors",
                        focal_mentions=["Work Learning Loop"],
                        direction="both",
                        depth=1,
                        presentation="explorer",
                    ),
                    confidence=1.0,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


def test_empty_grounded_answer_repairs_once_without_changing_the_validated_plan(
    v2_service: AgentV2Service,
):
    model = EmptyThenGroundedRepairModel()
    route = v2_service.quick_agent.route(
        "Work Learning Loop를 내부 문서로 설명해줘",
        page_kind="library",
        knowledge_hints=[
            {
                "ref": "boi:public:work-learning-loop",
                "title": "Work Learning Loop",
                "chunk_id": "chunk-loop",
                "chunk_text": "Work Learning Loop는 검증된 결과를 다음 업무에 재사용하는 순환입니다.",
                "answer_scope": "canonical",
            }
        ],
        model=model,
    )

    assert model.calls == 2
    assert route["semantic_plan"]["resolved_goal"] == "Work Learning Loop의 내부 정의를 설명한다"
    assert route["grounded_answer_diagnostics"]["repair"] == "accepted"
    assert route["grounded_answer"]["claims"][0]["source_refs"] == [
        "boi:public:work-learning-loop"
    ]
    assert "grounded_answer:repair" in route["trace"]


def test_graph_query_does_not_repair_an_unused_planner_answer(
    v2_service: AgentV2Service,
):
    model = EmptyGraphAnswerModel()
    route = v2_service.quick_agent.route(
        "Work Learning Loop의 연결 관계를 탐색해줘",
        page_kind="library",
        knowledge_hints=[
            {
                "ref": "boi:public:work-learning-loop",
                "title": "Work Learning Loop",
                "chunk_id": "chunk-loop",
                "chunk_text": "Work Learning Loop는 검증된 결과를 다음 업무에 재사용하는 순환입니다.",
                "answer_scope": "canonical",
            }
        ],
        model=model,
    )

    assert model.calls == 1
    assert route["grounded_answer"] is None
    assert route["grounded_answer_diagnostics"]["repair"] == "deferred_to_graph_result"
    assert "grounded_answer:graph_result" in route["trace"]
    assert "grounded_answer:repair" not in route["trace"]


def test_semantic_plan_repair_records_only_validation_diagnostics(
    v2_service: AgentV2Service,
):
    invalid = SemanticPlan(
        resolved_goal="검증된 관계를 탐색한다",
        retrieval_query="검증된 관계",
        capability_id="knowledge.search",
        user_effect="execute",
        operation="understand",
        evidence_scope="canonical",
        presentation="prose",
        confidence=1.0,
    ).model_dump(mode="json")
    valid = SemanticPlan(
        resolved_goal="검증된 관계를 탐색한다",
        retrieval_query="검증된 관계",
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="canonical",
        presentation="prose",
        confidence=1.0,
    ).model_dump(mode="json")
    model = ScriptedPlanner([invalid, valid])

    route = v2_service.quick_agent.route(
        "검증된 관계를 탐색해줘",
        page_kind="library",
        model=model,
    )

    assert route["planner_repair"]["attempted"] is True
    assert route["planner_repair"]["reason"] == "planner_invalid"
    assert route["planner_repair"]["issues"]
    assert "semantic_plan:repair" in route["trace"]
    assert route["semantic_plan"]["user_effect"] == "read"


def _task_completion_plan(task_ref: str) -> dict[str, Any]:
    return SemanticPlan(
        resolved_goal=f"{task_ref} 업무의 근거와 수행 기록을 검증해 완료한다",
        retrieval_query=f"{task_ref} 완료 조건 근거 수행 기록",
        capability_id="task.work",
        user_effect="execute",
        operation="complete",
        evidence_scope="operational",
        presentation="artifact",
        work_view="current",
        context_refs=[task_ref],
        target_ref=task_ref,
        answer_intent="work",
        loop_contract=_catalog_loop_contract("task.work"),
        confidence=1.0,
    ).model_dump(mode="json")


def _knowledge_read_plan(query: str) -> dict[str, Any]:
    return SemanticPlan(
        resolved_goal=query,
        retrieval_query=query,
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="canonical",
        presentation="prose",
        answer_intent="fact",
        confidence=1.0,
    ).model_dump(mode="json")


class CountingSemanticRouteModel(ScriptedPlanner):
    def __init__(self):
        self.planner_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            self.planner_calls += 1
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class BroadWorkQuestionReviewModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            person_ref = next(
                (str(item) for item in payload.get("trusted_context_refs") or [] if str(item).startswith("person:")),
                "",
            )
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="공식 역할과 검증된 업무 관계, 현재 처리할 업무를 구분해 설명한다",
                    retrieval_query="공식 역할 검증된 업무 관계 현재 처리할 업무",
                    subjects=[
                        SemanticSubject(
                            mention="현재 사용자",
                            entity_ref=person_ref,
                            entity_kind="person",
                            resolution="resolved" if person_ref else "unresolved",
                        )
                    ] if person_ref else [],
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="connect",
                    evidence_scope="operational",
                    presentation="table",
                    work_view="combined",
                    graph_query=GraphQueryDraft(
                        enabled=True,
                        query_kind="responsibility",
                        focal_mentions=[person_ref] if person_ref else [],
                        presentation="table",
                    ),
                    context_refs=[person_ref] if person_ref else [],
                    confidence=1.0,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class MisroutedCurrentWorkReviewModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "capability_id": "knowledge.search",
                    "asset_kind": "knowledge",
                    "operation": "understand",
                    "operation_plan": ["understand"],
                    "work_view": "current",
                    "current_scope_explicit": True,
                    "graph_query_draft": {
                        "enabled": True,
                        "query_kind": "responsibility",
                        "focal_mentions": ["현재 사용자"],
                        "presentation": "table",
                    },
                }
            )
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class RuntimeOnlyWrongScopeReviewModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "capability_id": "knowledge.search",
                    "asset_kind": "runtime",
                    "operation": "connect",
                    "operation_plan": ["connect"],
                    "scope": "current",
                    "work_view": "combined",
                    "current_scope_explicit": False,
                    "requested_asset_kinds": ["task", "evidence"],
                    "graph_query_draft": {
                        "enabled": True,
                        "query_kind": "responsibility",
                        "focal_mentions": ["현재 사용자"],
                        "presentation": "table",
                    },
                }
            )
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class KnowledgeCurrentScopeContradictionModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            planned.update(
                {
                    "capability_id": "knowledge.search",
                    "asset_kind": "knowledge",
                    "operation": "understand",
                    "scope": "current",
                    "work_view": "current",
                    "current_scope_explicit": True,
                    "requested_asset_kinds": ["knowledge"],
                    "presentation_mode": "mermaid",
                }
            )
        return planned


class GenericRetrievalQueryModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            planned.update(
                {
                    "resolved_goal": "현재 문서의 구조와 관계를 설명",
                    "retrieval_query": "구조와 관계 설명",
                    "context_refs": trusted_refs[:1],
                }
            )
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class SemanticContinuationModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            active_run = (payload.get("active_work") or {}).get("work_run") or {}
            task_ref = str(
                active_run.get("task_ref")
                or (payload.get("active_work") or {}).get("task_ref")
                or next(
                    (
                        item
                        for item in payload.get("trusted_context_refs") or []
                        if str(item).startswith(("task:", "review-task", "auto-task"))
                    ),
                    "",
                )
            )
            plan = SemanticPlan(
                resolved_goal=f"{task_ref} 업무의 근거와 수행 기록을 검증해 완료한다",
                retrieval_query=f"{task_ref} 완료 조건 근거 수행 기록",
                topic_action="continue" if active_run.get("status") == "waiting_human" else "new",
                reference_resolution="specific" if active_run.get("status") == "waiting_human" else "none",
                subjects=[
                    SemanticSubject(
                        mention="진행 중인 Task",
                        entity_ref=task_ref,
                        entity_kind="task",
                        resolution="resolved",
                    )
                ],
                capability_id="task.work",
                user_effect="execute",
                operation="complete",
                evidence_scope="operational",
                presentation="artifact",
                work_view="current",
                context_refs=[task_ref],
                target_ref=task_ref,
                answer_intent="work",
                loop_contract=_catalog_loop_contract("task.work"),
                confidence=0.98,
            )
            planned = _planner_envelope(plan.model_dump(mode="json"))
            if active_run.get("status") == "waiting_human":
                planned["continuation"] = {
                    "continue_active_run": True,
                    "delta_kind": "human_input",
                    "user_confirmation": True,
                    "work_record": {
                        "observations": "필수 자료와 예외 사항을 직접 검토했습니다.",
                        "judgment": "검토 기준을 충족한다고 판단했습니다.",
                        "result": "판단과 결과를 검토 기록에 남겼습니다.",
                    },
                }
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class TargetlessTaskLookupModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="단면검사 Task의 이전 판단 기록을 찾는다",
                    retrieval_query="단면검사 Task 이전 판단 기록",
                    capability_id="task.work",
                    user_effect="read",
                    operation="observe",
                    evidence_scope="operational",
                    presentation="prose",
                    loop_contract=_catalog_loop_contract("task.work"),
                    confidence=0.96,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class MisroutedActionRunModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="manual.review Action을 dry-run 한다",
                    retrieval_query="manual.review Action 계약",
                    subjects=[
                        {
                            "mention": "manual.review",
                            "entity_ref": "manual.review",
                            "entity_kind": "action",
                            "resolution": "resolved",
                        }
                    ],
                    capability_id="task.work",
                    user_effect="execute",
                    operation="run",
                    evidence_scope="operational",
                    presentation="artifact",
                    target_ref="manual.review",
                    confidence=0.91,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class RepairingSopModel(ScriptedPlanner):
    def __init__(self):
        self.calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="검증할 근거와 완료 조건이 명확한 SOP 초안을 만든다",
                    retrieval_query="SOP 근거 완료 조건 업무 단계",
                    capability_id="sop.plan",
                    user_effect="draft",
                    operation="create",
                    evidence_scope="canonical",
                    presentation="artifact",
                    answer_intent="work",
                    loop_contract=_catalog_loop_contract("sop.plan"),
                    confidence=1.0,
                ).model_dump(mode="json")
            )
        self.calls += 1
        task = {
            "name": "근거 확인",
            "purpose": "판단에 필요한 근거를 확인합니다.",
            "execution_mode": "copilot",
            "exit_criteria": [] if self.calls == 1 else ["필수 근거가 확인됨"],
            "required_evidence": ["검토 문서"],
        }
        return {
            "title": "근거 확인 SOP",
            "goal": "근거 기반 판단",
            "tasks": [task],
            "mermaid": 'flowchart LR\n  A["근거 확인"] --> B["판단"]',
            "gaps": [],
        }


class PlannerPrefilledSopModel(RepairingSopModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "resolved_goal": "검증된 근거로 업무 판단을 완료하는 SOP 초안을 만든다",
                    "retrieval_query": "업무 판단 SOP 근거와 완료 조건",
                    "capability_id": "sop.plan",
                    "user_effect": "draft",
                    "operation": "create",
                    "presentation_mode": "artifact",
                    "answer_intent": "work",
                }
            )
            planned["sop_draft"] = {
                "title": "근거 확인 SOP",
                "goal": "검증된 근거로 업무 판단을 완료합니다.",
                "tasks": [
                    {
                        "name": "근거 확인",
                        "purpose": "판단에 필요한 자료와 담당자 확인 내용을 검토합니다.",
                        "execution_mode": "copilot",
                        "exit_criteria": ["필수 근거와 담당자 판단이 기록되었어요"],
                        "required_evidence": ["검토 문서", "담당자 판단 기록"],
                    }
                ],
                "gaps": [],
            }
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


def test_sop_draft_ignores_planner_authored_payload_and_uses_the_draft_contract(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = PlannerPrefilledSopModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="플래너 선행 근거 확인 SOP 초안을 새로 만들어줘"),
    )
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)

    assert model.calls == 2
    assert artifact["generation_attempts"] == 2
    assert artifact["draft"]["tasks"][0]["exit_criteria"] == ["필수 근거가 확인되었어요"]
    assert artifact["draft"]["tasks"][0]["completion_design"]["checks"][0]["confirmation"] == "human"
    assert artifact["draft"]["mermaid"].startswith("flowchart TD")


def test_private_draft_returns_after_deterministic_validation_without_blocking_model_review(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model

    def fail_if_reviewed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("private draft must not wait for an independent model review")

    v2_service.evaluator.evaluate = fail_if_reviewed  # type: ignore[method-assign]
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 초안을 만들어줘", capability_id="sop.plan"),
    )
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)

    assert artifact["independent_review"]["status"] == "not_requested"
    assert response.artifact_refs[0].metadata["review_status"] == "not_requested"


def test_planner_grounded_summary_does_not_require_an_optional_outcome_section(
    v2_service: AgentV2Service,
    principal: Principal,
):
    evidence = [
        EvidenceRef(
            evidence_id="boi:public:guide",
            kind="document",
            title="업무 관계 가이드",
            summary="관계 근거와 원문을 함께 확인합니다.",
            url="/docs/boi:public:guide",
        )
    ]
    citations = [
        CitationRef(
            citation_id="cite-guide",
            source_ref="boi:public:guide",
            title="업무 관계 가이드",
            excerpt="관계 근거와 원문을 함께 확인합니다.",
        )
    ]
    v2_service.store.put(
        "work_sessions",
        "session-summary",
        {"session_id": "session-summary", "employee_id": principal.employee_id, "status": "active"},
    )

    rendered = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-summary"},
        {
            "summary": "관계를 선택하면 검증된 근거와 원문을 함께 확인할 수 있습니다.",
            "summary_source_refs": ["boi:public:guide"],
            "outcomes": [],
            "related_questions": [],
        },
        evidence,
        citations,
    )

    assert rendered is not None
    answer, related = rendered
    assert "cite-guide" in answer.markdown
    assert "업무 관계 가이드" in answer.markdown
    assert related == []


def test_grounded_answer_rejects_validation_evidence_relabelled_as_canonical(
    v2_service: AgentV2Service,
):
    plan = SemanticPlan(
        resolved_goal="내부 A2UI 정의를 설명한다",
        retrieval_query="A2UI 정의",
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="canonical",
        presentation="prose",
        confidence=1.0,
    )
    answer, diagnostics = v2_service.quick_agent._resolve_grounded_answer(
        {
            "grounded_answer": {
                "summary": "A2UI 정의라고 주장합니다.",
                "summary_source_refs": ["S1"],
                "claims": [
                    {
                        "claim_id": "claim-wrong-scope",
                        "text": "A2UI 정의라고 주장합니다.",
                        "source_scope": "canonical",
                        "source_refs": ["S1"],
                        "supporting_chunk_ids": ["C1"],
                    }
                ],
            }
        },
        plan,
        [
            {
                "ref": "boi:team:validation:a2ui",
                "chunk_id": "boi:team:validation:a2ui#body-0",
                "answer_scope": "validation",
            }
        ],
    )

    assert answer is not None
    assert diagnostics["accepted"] is False
    assert diagnostics["accepted_claims"] == 0
    assert answer["claims"][0]["support_status"] == "unsupported"


class RefiningSopModel(RepairingSopModel):
    def __init__(self):
        super().__init__()
        self.semantic_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            self.semantic_calls += 1
            payload = json.loads(prompt)
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            target_ref = next((item for item in trusted_refs if item.startswith("artifact_")), "")
            operation = "refine" if self.semantic_calls == 1 else "validate"
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal=(
                        "선택한 SOP 초안의 완료 항목과 확인할 자료를 구체화한다"
                        if operation == "refine"
                        else "선택한 SOP 초안의 완료 조건과 근거 계약을 검증한다"
                    ),
                    retrieval_query="SOP 초안 완료 조건 근거 계약",
                    topic_action="continue",
                    reference_resolution="specific",
                    subjects=[
                        SemanticSubject(
                            mention="선택한 SOP 초안",
                            entity_ref=target_ref,
                            entity_kind="sop",
                            resolution="resolved",
                        )
                    ],
                    capability_id="sop.plan",
                    user_effect="draft",
                    operation=operation,
                    evidence_scope="canonical",
                    presentation="artifact",
                    context_refs=[target_ref],
                    target_ref=target_ref,
                    answer_intent="work",
                    loop_contract=_catalog_loop_contract("sop.plan"),
                    confidence=1.0,
                ).model_dump(mode="json")
            )
        if "completion_design" in required:
            return {
                "name": "근거 확인",
                "purpose": "판단에 필요한 근거와 예외를 확인합니다.",
                "execution_mode": "copilot",
                "exit_criteria": ["근거와 예외 검토가 기록되었어요"],
                "required_evidence": ["검토 문서", "담당자 판단 기록"],
                "completion_design": {
                    "version": 1,
                    "checks": [
                        {
                            "check_id": "review-complete",
                            "label": "근거와 예외 검토가 기록되었어요",
                            "confirmation": "human",
                            "binding": {"kind": "none", "ref": ""},
                        }
                    ],
                    "evidence": [
                        {
                            "evidence_id": "review-document",
                            "label": "검토 문서와 담당자 판단 기록",
                            "source_kind": "human_note",
                            "ref": "",
                            "provided_by": "human",
                            "required": True,
                        }
                    ],
                },
                "outputs": ["판단 기록"],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class GroundedAnswerModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            hints = [
                item
                for item in [
                    *(payload.get("internal_wiki_hints") or []),
                    *(payload.get("operational_runtime_hints") or []),
                ]
                if isinstance(item, dict)
            ]
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            if hints:
                source_ref = str(hints[0].get("source_key") or hints[0].get("ref") or "")
                entity_ref = str(hints[0].get("ref") or "")
                chunk_id = str(hints[0].get("chunk_key") or hints[0].get("chunk_id") or "")
                planned.update(
                    {
                        "answer_intent": "procedure",
                        "topic_mode": "new",
                        "subjects": [
                            {
                                "mention": str(hints[0].get("title") or "BoI Wiki 운영 가이드 게시 기준"),
                                "entity_ref": entity_ref,
                                "entity_kind": "knowledge",
                                "resolution": "resolved",
                            }
                        ] if entity_ref else [],
                        "context_refs": [entity_ref] if entity_ref else [],
                        "target_ref": entity_ref,
                        "grounded_answer": {
                            "summary": "업무 지식과 실행 근거를 연결하고, 초안은 검토 후 게시합니다.",
                            "summary_source_refs": [source_ref],
                            "claims": [
                                {
                                    "claim_id": "claim-guide-evidence",
                                    "text": "업무 지식과 실행 근거를 연결합니다.",
                                    "claim_kind": "procedure",
                                    "source_refs": [source_ref],
                                    "supporting_chunk_ids": [chunk_id],
                                },
                                {
                                    "claim_id": "claim-guide-publish",
                                    "text": "초안은 검토 후 게시합니다.",
                                    "claim_kind": "procedure",
                                    "source_refs": [source_ref],
                                    "supporting_chunk_ids": [chunk_id],
                                },
                            ],
                            "outcomes": [],
                            "related_questions": [
                                {
                                    "kind": "understand",
                                    "label": "게시 근거 더 보기",
                                    "question": "게시 전에 확인할 근거를 더 자세히 보여줘.",
                                    "source_refs": [source_ref],
                                }
                            ],
                        },
                    }
                )
            return planned
        if required == {"summary", "outcomes"}:
            return {
                "summary": "초안은 검토 후 게시하며, 업무 지식과 실행 근거를 함께 연결합니다.",
                "outcomes": [
                    {
                        "title": "핵심 기준",
                        "items": [
                            {
                                "text": "업무 지식과 실행 근거를 연결합니다.",
                                "source_numbers": [1],
                            }
                        ],
                    },
                    {
                        "title": "다음 점검 항목",
                        "items": [
                            {
                                "text": "초안이 검토된 근거를 사용했는지 확인합니다.",
                                "source_numbers": [1],
                            }
                        ],
                    },
                ],
                "related_questions": [
                    {
                        "kind": "understand",
                        "label": "근거가 된 기준 더 보기",
                        "question": "이 답변에서 사용한 핵심 기준을 근거별로 더 설명해줘.",
                        "source_numbers": [1],
                    }
                ],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class CombinedPlannerAnswerModel(GroundedAnswerModel):
    def __init__(
        self,
        *,
        invalid_ref: bool = False,
        use_source_key: bool = False,
        presentation_mode: str = "prose",
        omit_grounded_answer: bool = False,
    ):
        self.invalid_ref = invalid_ref
        self.use_source_key = use_source_key
        self.presentation_mode = presentation_mode
        self.omit_grounded_answer = omit_grounded_answer
        self.planner_calls = 0
        self.answer_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            self.planner_calls += 1
            payload = json.loads(prompt)
            hints = [
                item
                for item in [
                    *(payload.get("internal_wiki_hints") or []),
                    *(payload.get("operational_runtime_hints") or []),
                ]
                if isinstance(item, dict)
            ]
            selected = next(
                (item for item in hints if str(item.get("ref") or "") == "boi:public:guide"),
                hints[0],
            )
            source_ref = "boi:public:not-retrieved" if self.invalid_ref else str(
                selected["source_key"] if self.use_source_key else selected["ref"]
            )
            chunk_id = str(selected["chunk_key"] if self.use_source_key else selected["chunk_id"])
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "resolved_goal": str(payload.get("request") or ""),
                    "retrieval_query": str(payload.get("request") or ""),
                    "presentation_mode": self.presentation_mode,
                    "work_view": "none",
                    "answer_intent": "procedure",
                    "topic_mode": "new",
                    "topic_subject": "BoI Wiki 운영 가이드 게시 기준",
                    "grounded_answer": {
                        "summary": "검토된 운영 가이드를 기준으로 게시와 근거 확인 절차를 설명합니다.",
                        "summary_source_refs": [source_ref],
                        "claims": [
                            {
                                "claim_id": "claim-publish-review",
                                "text": "초안은 검토 후 게시합니다.",
                                "claim_kind": "procedure",
                                "source_refs": [source_ref],
                                "supporting_chunk_ids": [chunk_id],
                            }
                        ],
                        "outcomes": [
                            {
                                "title": "확인 결과",
                                "items": [
                                    {
                                        "text": "검토된 근거를 확인한 뒤 게시합니다.",
                                        "source_refs": [source_ref],
                                    }
                                ],
                            }
                        ],
                        "related_questions": [
                            {
                                "kind": "understand",
                                "label": "게시 근거 더 보기",
                                "question": "게시 전에 확인할 근거를 더 자세히 보여줘.",
                                "source_refs": [source_ref],
                            }
                        ],
                    },
                }
            )
            if self.omit_grounded_answer:
                planned["grounded_answer"] = {
                    "summary": "",
                    "summary_source_refs": [],
                    "claims": [],
                    "outcomes": [],
                    "related_questions": [],
                }
            return planned
        if required == {"summary", "outcomes"}:
            self.answer_calls += 1
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class A2UIReliabilityModel(ScriptedPlanner):
    def __init__(self):
        self.planner_payloads: list[dict[str, Any]] = []

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            self.planner_payloads.append(payload)
            hints = [
                item
                for item in [
                    *(payload.get("internal_wiki_hints") or []),
                    *(payload.get("operational_runtime_hints") or []),
                ]
                if isinstance(item, dict)
            ]
            followup = _has_verified_topic_state(payload)
            selected = next(
                (
                    item
                    for item in hints
                    if (
                        str(item.get("ref") or "") == "runtime:a2ui-capability-catalog"
                        if followup
                        else "a2ui-and-dynamic-results" in str(item.get("ref") or "")
                    )
                ),
                hints[0],
            )
            source_ref = str(selected.get("source_key") or selected.get("ref") or "")
            chunk_id = str(selected.get("chunk_key") or selected.get("chunk_id") or "")
            prior_topic = payload.get("verified_topic_state") or {}
            prior_entities = [str(item) for item in prior_topic.get("entities") or [] if str(item)]
            topic_subject = str(prior_topic.get("subject") or "A2UI와 BoI 동적 결과 화면")
            if followup:
                claim_text = "boi-a2ui/v1 catalog에는 Answer, CitationList, DataTable, Timeline, MermaidArtifact, OntologyExplorer가 등록되어 있습니다."
                answer_intent = "fact"
                topic_mode = "continue"
                resolved_goal = f"{topic_subject}: 실제 등록 component와 사용 현황을 보여준다"
                retrieval_query = f"{topic_subject}: 실제 등록 component와 사용 현황"
            else:
                claim_text = "A2UI는 Agent가 만든 결과의 선언적인 화면 구조와 데이터를 신뢰된 client component가 렌더링하도록 전달하는 표현 계약입니다."
                answer_intent = "definition"
                topic_mode = "new"
                topic_subject = "A2UI와 BoI 동적 결과 화면"
                resolved_goal = "A2UI와 BoI 동적 결과 화면의 내부 canonical 정의를 설명한다"
                retrieval_query = "A2UI와 BoI 동적 결과 화면 정의"
            entity_ref = str(selected.get("ref") or "")
            subject_rows = []
            if followup:
                subject_rows.extend(
                    {
                        "mention": topic_subject,
                        "entity_ref": ref,
                        "entity_kind": "knowledge",
                        "resolution": "resolved",
                    }
                    for ref in prior_entities
                )
            if entity_ref and entity_ref not in {str(item.get("entity_ref") or "") for item in subject_rows}:
                subject_rows.append(
                    {
                        "mention": "BoI 동적 결과 component registry" if followup else topic_subject,
                        "entity_ref": entity_ref,
                        "entity_kind": "runtime_catalog" if followup else "knowledge",
                        "resolution": "resolved",
                    }
                )
            planned = _planner_envelope(
                SemanticPlan(
                    resolved_goal=resolved_goal,
                    retrieval_query=retrieval_query,
                    topic_action=topic_mode,
                    reference_resolution="all" if followup else "none",
                    subjects=subject_rows,
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="understand",
                    evidence_scope="operational" if followup else "canonical",
                    presentation="prose",
                    answer_intent=answer_intent,
                    context_refs=[str(item.get("entity_ref") or "") for item in subject_rows],
                    target_ref=entity_ref,
                    confidence=0.99,
                ).model_dump(mode="json")
            )
            planned["grounded_answer"] = {
                    "summary": claim_text,
                    "summary_source_refs": [source_ref],
                    "claims": [
                        {
                                "claim_id": "claim-a2ui-runtime" if followup else "claim-a2ui-definition",
                                "text": claim_text,
                                "claim_kind": answer_intent,
                                "source_scope": "operational" if followup else "canonical",
                                "source_refs": [source_ref],
                            "supporting_chunk_ids": [chunk_id],
                        }
                    ],
                    "outcomes": [],
                    "related_questions": [],
            }
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class A2UIOmittedProvenanceModel(A2UIReliabilityModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            if _has_verified_topic_state(payload):
                answer = planned.get("grounded_answer") or {}
                answer["summary_source_refs"] = []
                for claim in answer.get("claims") or []:
                    claim["source_refs"] = []
                    claim["supporting_chunk_ids"] = ["model-omitted-provenance"]
        return planned


class A2UIMismatchedChunkModel(A2UIReliabilityModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            if _has_verified_topic_state(payload):
                for claim in (planned.get("grounded_answer") or {}).get("claims") or []:
                    claim["supporting_chunk_ids"] = ["C1"]
        return planned


class UnknownConceptModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="ZQX-99 내부 약어의 검증된 정의를 확인한다",
                    retrieval_query="ZQX-99 내부 약어 정의",
                    capability_id="knowledge.search",
                    user_effect="read",
                    operation="understand",
                    evidence_scope="canonical",
                    presentation="prose",
                    answer_intent="definition",
                    confidence=0.99,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class MalformedContinuationModel(A2UIReliabilityModel):
    def __init__(self):
        super().__init__()
        self.followup_attempts = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(prompt) if prompt.strip().startswith("{") else {}
        result = super().generate_structured(system=system, prompt=prompt, schema=schema)
        if (
            _is_semantic_planner_schema(schema)
            and _has_verified_topic_state(payload)
        ):
            self.followup_attempts += 1
            if not payload.get("validation_issues"):
                result["resolved_goal"] = "실제 등록 component와 사용 현황을 보여준다"
                result["retrieval_query"] = "실제 등록 component와 사용 현황"
                result["subjects"] = []
        return result


class ExplicitNewTopicModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        result = super().generate_structured(system=system, prompt=prompt, schema=schema)
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            hints = [
                item
                for item in [
                    *(payload.get("internal_wiki_hints") or []),
                    *(payload.get("operational_runtime_hints") or []),
                ]
                if isinstance(item, dict)
            ]
            entity_ref = str(hints[0].get("ref") or "") if hints else ""
            result.update(
                {
                    "resolved_goal": "Action dry-run과 실제 실행의 차이를 설명한다",
                    "retrieval_query": "Action dry-run 실제 실행 차이",
                    "answer_intent": "comparison",
                    "topic_mode": "new",
                    "subjects": [
                        {
                            "mention": "Action dry-run과 실제 실행",
                            "entity_ref": entity_ref,
                            "entity_kind": "knowledge",
                            "resolution": "resolved",
                        }
                    ] if entity_ref else [
                        {
                            "mention": "Action dry-run과 실제 실행",
                            "entity_kind": "knowledge",
                            "resolution": "unresolved",
                        }
                    ],
                    "context_refs": [entity_ref] if entity_ref else [],
                    "target_ref": entity_ref,
                    "grounded_answer": {
                        "summary": "",
                        "summary_source_refs": [],
                        "claims": [],
                        "outcomes": [],
                        "related_questions": [],
                    },
                }
            )
        return result


class ApplyRelatedQuestionModel(GroundedAnswerModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        result = super().generate_structured(system=system, prompt=prompt, schema=schema)
        if _is_semantic_planner_schema(schema):
            answer = result.get("grounded_answer") if isinstance(result, dict) else None
            refs = list(answer.get("summary_source_refs") or []) if isinstance(answer, dict) else []
            if isinstance(answer, dict):
                answer["related_questions"] = [
                    {
                        "kind": "apply",
                        "label": "현재 업무에 적용",
                        "question": "이 기준을 현재 업무에 적용하려면 무엇을 해야 하나요?",
                        "source_refs": refs,
                    }
                ]
        if set(schema.get("required") or []) == {"summary", "outcomes"}:
            result["related_questions"] = [
                {
                    "kind": "apply",
                    "label": "현재 업무에 적용",
                    "question": "이 기준을 현재 업무에 적용하려면 무엇을 해야 하나요?",
                    "source_numbers": [1],
                }
            ]
        return result


class MultiTurnMermaidModel(GroundedAnswerModel):
    def __init__(self, presentations: list[str] | None = None):
        self.planner_payloads: list[dict[str, Any]] = []
        self.presentations = list(presentations or ["mermaid"])

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            self.planner_payloads.append(payload)
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            requested_presentation = self.presentations.pop(0) if self.presentations else "mermaid"
            diagram = requested_presentation == "mermaid"
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            prior_topic = payload.get("verified_topic_state") or {}
            prior_entities = [str(item) for item in prior_topic.get("entities") or []]
            hints = [
                item
                for item in [
                    *(payload.get("internal_wiki_hints") or []),
                    *(payload.get("operational_runtime_hints") or []),
                ]
                if isinstance(item, dict)
            ]
            subject_ref = next((item for item in prior_entities if item in trusted_refs), "")
            if not subject_ref:
                subject_ref = next(
                    (str(item.get("ref") or "") for item in hints if str(item.get("ref") or "") in trusted_refs),
                    "",
                )
            topic_action = "continue" if prior_entities and subject_ref in prior_entities else "new"
            if diagram:
                planned.update(
                    {
                        "capability_id": "knowledge.search",
                        "user_effect": "read",
                        "operation": "connect",
                        "resolved_goal": (
                            f"직전 답변에서 설명한 대상을 이어서 {payload.get('request') or '관계 그림으로 보여준다'}"
                            if topic_action == "continue"
                            else str(payload.get("request") or "검증된 관계를 Mermaid로 보여준다")
                        ),
                        "retrieval_query": str(payload.get("request") or "검증된 관계 흐름"),
                        "presentation_mode": "mermaid",
                        "topic_mode": topic_action,
                        "reference_resolution": "specific" if topic_action == "continue" else "none",
                        "subjects": [
                            {
                                "mention": str(prior_topic.get("subject") or "검증된 지식 관계"),
                                "entity_ref": subject_ref,
                                "entity_kind": "knowledge",
                                "resolution": "resolved",
                            }
                        ] if subject_ref else [],
                        "context_refs": [subject_ref] if subject_ref else [],
                        "target_ref": subject_ref,
                        "graph_query_draft": {
                            "enabled": True,
                            "query_kind": "neighbors",
                            "focal_mentions": [subject_ref] if subject_ref else [],
                            "presentation": "mermaid",
                        },
                        "confidence": 0.99,
                    }
                )
            else:
                planned.update(
                    {
                        "resolved_goal": str(payload.get("request") or "검증된 지식을 설명한다"),
                        "retrieval_query": str(payload.get("request") or "검증된 지식"),
                        "capability_id": "knowledge.search",
                        "user_effect": "read",
                        "operation": "understand",
                        "presentation_mode": "prose",
                        "topic_mode": "new",
                        "subjects": [
                            {
                                "mention": "검증된 지식",
                                "entity_ref": subject_ref,
                                "entity_kind": "knowledge",
                                "resolution": "resolved",
                            }
                        ] if subject_ref else [],
                        "context_refs": [subject_ref] if subject_ref else [],
                        "target_ref": subject_ref,
                        "confidence": 0.99,
                    }
                )
            if diagram:
                planned["grounded_answer"] = {
                    "summary": "",
                    "summary_source_refs": [],
                    "claims": [],
                    "outcomes": [],
                    "related_questions": [],
                }
            return planned
        if required == {"title", "nodes", "edges"}:
            return {
                "title": "BoI Wiki 근거 검색 흐름",
                "nodes": [
                    {"node_id": "context", "label": "업무 맥락 구성", "kind": "Context", "asset_kind": "knowledge", "source_numbers": [1]},
                    {"node_id": "search", "label": "관련 지식 탐색", "kind": "Hybrid Search", "asset_kind": "knowledge", "source_numbers": [1]},
                    {"node_id": "answer", "label": "근거 있는 답변", "kind": "BoI Agent", "asset_kind": "knowledge", "source_numbers": [1]},
                ],
                "edges": [
                    {"from": "context", "to": "search", "label": "검색 기준", "source_numbers": [1]},
                    {"from": "search", "to": "answer", "label": "인용 근거", "source_numbers": [1]},
                ],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class SplitOnlyFollowupModel(MultiTurnMermaidModel):
    def __init__(self):
        super().__init__(["mermaid"])
        self.semantic_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if set(schema.get("required") or []) == {
            "status",
            "selected_ref",
            "clarification_question",
        }:
            payload = json.loads(prompt)
            return {
                "status": "justified",
                "selected_ref": payload["planner_selected_ref"],
                "clarification_question": "",
            }
        if _is_semantic_planner_schema(schema):
            self.semantic_calls += 1
            if self.semantic_calls == 1:
                return super().generate_structured(system=system, prompt=prompt, schema=schema)
            payload = json.loads(prompt)
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            artifact_ref = next((item for item in trusted_refs if item.startswith("artifact_")), "")
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal="선택한 흐름을 실행 가능한 Task 후보로 나눈다",
                    retrieval_query="선택한 흐름의 업무 단계",
                    topic_action="continue",
                    reference_resolution="specific",
                    subjects=[
                        SemanticSubject(
                            mention="선택한 흐름",
                            entity_ref=artifact_ref,
                            entity_kind="artifact",
                            resolution="resolved",
                        )
                    ],
                    capability_id="workflow.transform",
                    user_effect="transform",
                    operation="refine",
                    evidence_scope="canonical",
                    presentation="artifact",
                    context_refs=[artifact_ref],
                    target_ref=artifact_ref,
                    answer_intent="work",
                    loop_contract=_catalog_loop_contract("workflow.transform"),
                    confidence=0.99,
                ).model_dump(mode="json")
            )
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class InboxBiasedMermaidModel(MultiTurnMermaidModel):
    """Models a planner that keeps the verified prior subject despite an Inbox page anchor."""


class RepairingScopedMermaidModel(MultiTurnMermaidModel):
    def __init__(self):
        super().__init__()
        self.graph_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"title", "nodes", "edges"}:
            self.graph_calls += 1
            if self.graph_calls == 1:
                return {
                    "title": "범위를 벗어난 흐름",
                    "nodes": [
                        {"node_id": "task", "label": "무관한 Task", "kind": "Task", "asset_kind": "task", "source_numbers": [1]},
                        {"node_id": "sop", "label": "무관한 SOP", "kind": "SOP", "asset_kind": "sop", "source_numbers": [1]},
                    ],
                    "edges": [{"from": "task", "to": "sop", "label": "임의 연결", "source_numbers": [1]}],
                }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class AlwaysOutOfScopeMermaidModel(MultiTurnMermaidModel):
    def __init__(self):
        super().__init__()
        self.graph_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"title", "nodes", "edges"}:
            self.graph_calls += 1
            return {
                "title": "범위를 벗어난 그림",
                "nodes": [
                    {"node_id": "workflow", "label": "무관한 흐름", "kind": "Workflow", "asset_kind": "workflow", "source_numbers": [1]},
                    {"node_id": "task", "label": "무관한 작업", "kind": "Task", "asset_kind": "task", "source_numbers": [1]},
                ],
                "edges": [{"from": "workflow", "to": "task", "label": "임의 연결", "source_numbers": [1]}],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class RepairingReadableMermaidModel(MultiTurnMermaidModel):
    def __init__(self):
        super().__init__()
        self.graph_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"title", "nodes", "edges"}:
            self.graph_calls += 1
            if self.graph_calls == 1:
                return {
                    "title": "용어 관계",
                    "nodes": [
                        {
                            "node_id": "term",
                            "label": "업무 용어",
                            "kind": "knowledge",
                            "asset_kind": "knowledge",
                            "source_numbers": [1],
                        },
                        {
                            "node_id": "mapping",
                            "label": "maps_to_sop",
                            "kind": "knowledge",
                            "asset_kind": "knowledge",
                            "source_numbers": [1],
                        },
                    ],
                    "edges": [
                        {"from": "term", "to": "mapping", "label": "uses_metadata", "source_numbers": [1]},
                    ],
                }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class AutomaticCheckModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if _is_semantic_planner_schema(schema):
            payload = json.loads(prompt)
            refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            target_ref = refs[0] if refs else "boi:public:guide"
            return _planner_envelope(
                SemanticPlan(
                    resolved_goal=str(payload.get("request") or ""),
                    retrieval_query=str(payload.get("request") or ""),
                    subjects=[
                        SemanticSubject(
                            mention=target_ref,
                            entity_ref=target_ref,
                            entity_kind="knowledge",
                            resolution="resolved",
                        )
                    ],
                    capability_id="work_routine.plan",
                    user_effect="draft",
                    operation="create",
                    evidence_scope="operational",
                    presentation="artifact",
                    context_refs=refs[:2],
                    target_ref=target_ref,
                    confidence=0.99,
                ).model_dump(mode="json")
            )
        if required == {
            "title",
            "goal",
            "trigger",
            "schedule_description",
            "calendar",
            "routine_stop",
            "completion_condition",
        }:
            return {
                "title": "BoI Wiki 운영 기준 매일 확인",
                "goal": "운영 기준의 변경과 새 보완 항목을 확인합니다.",
                "trigger": "schedule",
                "schedule_description": "매일 오전 9시",
                "calendar": {
                    "minutes": [0],
                    "hours": [9],
                    "days_of_month": [],
                    "months": [],
                    "weekdays": [],
                },
                "cron": "",
                "timezone": "Asia/Seoul",
                "event_ref": "",
                "routine_stop": "cancelled",
                "max_runs": 0,
                "completion_condition": "담당자가 더 이상 확인할 필요가 없다고 정할 때",
                "target_ref": "boi:public:guide",
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class SkillExecutionModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"result", "evidence_refs"}:
            return {"result": "관련 근거와 evidence_refs를 확인했습니다.", "evidence_refs": []}
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class ReviewerModel(ScriptedPlanner):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"status", "summary", "criteria", "findings"}:
            return {
                "status": "needs_revision",
                "summary": "완료 조건의 근거 연결을 보완해야 합니다.",
                "criteria": [
                    {
                        "criterion": "근거 추적 가능성",
                        "status": "warning",
                        "evidence_refs": ["boi:public:guide", "not-retrieved"],
                    }
                ],
                "findings": [
                    {
                        "severity": "warning",
                        "message": "완료 조건에 사용할 근거를 명시하세요.",
                        "evidence_refs": ["boi:public:guide"],
                    }
                ],
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class ActualUsageModel(ReviewerModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        result = super().generate_structured(system=system, prompt=prompt, schema=schema)
        _record_provider_usage("structured", {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168})
        return result


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
        database_dsn="",
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


def test_home_offers_are_typed_and_not_document_specific(v2_service: AgentV2Service, principal: Principal):
    offers = v2_service.create_offers(principal, OfferRequest(page_ref="/"))
    assert {item.capability_id for item in offers} == {"knowledge.search", "work.inbox", "cases.similar"}
    assert all(item.offer_id.startswith("offer_") for item in offers)
    assert all(item.capability_id not in {"knowledge.draft", "sop.plan"} for item in offers)
    assert next(item for item in offers if item.capability_id == "knowledge.search").state.value == "needs_input"


def test_final_operator_guide_is_treated_as_the_library_home(v2_service: AgentV2Service, principal: Principal):
    offers = v2_service.create_offers(
        principal,
        OfferRequest(page_ref="/docs/boi:public:boi-wiki-manual:guide:final-operator-guide"),
    )
    assert {item.capability_id for item in offers} == {"knowledge.search", "work.inbox", "cases.similar"}


def test_generation_concurrency_limit_serializes_structured_calls():
    lock = threading.Lock()
    release = threading.Event()
    first_entered = threading.Event()
    active = 0
    peak = 0

    class BlockingGateway:
        provider = "test"

        @staticmethod
        def readiness() -> dict[str, Any]:
            return {"generation": True}

        @staticmethod
        def preflight() -> dict[str, Any]:
            return {"ok": True}

        def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                first_entered.set()
            assert release.wait(2)
            with lock:
                active -= 1
            return {"prompt": prompt}

        @staticmethod
        def stream_text(*, system: str, prompt: str) -> Iterator[str]:
            yield prompt

        @staticmethod
        def embed(texts: list[str]) -> list[list[float]]:
            return [[1.0] for _ in texts]

    gateway = ConcurrencyLimitedGenerationGateway(
        BlockingGateway(),
        max_concurrency=1,
        queue_timeout_seconds=2,
    )
    results: list[dict[str, Any]] = []

    def invoke(prompt: str) -> None:
        results.append(gateway.generate_structured(system="", prompt=prompt, schema={}))

    first = threading.Thread(target=invoke, args=("first",))
    second = threading.Thread(target=invoke, args=("second",))
    first.start()
    assert first_entered.wait(1)
    second.start()
    time.sleep(0.05)
    assert peak == 1
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert peak == 1
    assert {item["prompt"] for item in results} == {"first", "second"}
    assert gateway.readiness()["generation_concurrency"]["max_concurrency"] == 1


def test_anthropic_generation_can_use_an_independent_openai_compatible_embedding_adapter():
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="anthropic",
        model_base_url="https://api.anthropic.example/v1",
        model_api_key="real-anthropic-secret",
        model_name="claude-test",
        embedding_provider="openai_compatible",
        embedding_base_url="https://embeddings.example/v1",
        embedding_api_key="",
        embedding_model="embedding-test",
    )

    readiness = build_model_gateway(settings).readiness()

    assert readiness["generation"] is True
    assert readiness["embeddings"] is True
    assert readiness["provider"] == "anthropic"
    assert readiness["embedding_provider"] == "openai_compatible"


def test_openai_compatible_generation_uses_lmstudio_json_schema_contract(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    class FakeResponse:
        is_success = True

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            }

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        captured.update({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.post", fake_post)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_api_key="not-needed",
        model_name="google/gemma-local",
    )
    schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}

    result = OpenAICompatibleGateway(settings).generate_structured(
        system="Return valid JSON.",
        prompt="Confirm readiness.",
        schema=schema,
    )

    assert result == {"ok": True}
    assert captured["url"] == "http://lmstudio.example:1234/v1/chat/completions"
    assert captured["json"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "boi_v2_response", "strict": False, "schema": schema},
    }
    assert captured["json"]["messages"][1]["content"] == "Confirm readiness."
    assert captured["json"]["temperature"] == 0
    assert captured["json"]["max_tokens"] == settings.model_max_output_tokens


def test_openai_compatible_generation_negotiates_structural_schema_when_full_schema_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, *, status_code: int, payload: dict[str, Any] | None = None):
            self.status_code = status_code
            self.is_success = status_code < 400
            self._payload = payload or {}
            self.text = '{"error":"structured transport rejected"}'

        def json(self) -> dict[str, Any]:
            return self._payload

    responses = [
        FakeResponse(status_code=400),
        FakeResponse(
            status_code=200,
            payload={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        ),
        FakeResponse(
            status_code=200,
            payload={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        ),
    ]

    def fake_post(_url: str, **kwargs: Any) -> FakeResponse:
        payloads.append(kwargs["json"])
        return responses.pop(0)

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.post", fake_post)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_api_key="not-needed",
        model_name="google/gemma-local",
    )
    schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
    gateway = OpenAICompatibleGateway(settings)

    assert gateway.generate_structured(system="Return valid JSON.", prompt="Confirm.", schema=schema) == {"ok": True}
    assert payloads[0]["response_format"]["type"] == "json_schema"
    assert payloads[1]["response_format"]["type"] == "json_schema"
    assert payloads[1]["response_format"]["json_schema"]["schema"] == schema

    assert gateway.generate_structured(system="Return valid JSON.", prompt="Confirm again.", schema=schema) == {"ok": True}
    assert payloads[2]["response_format"]["type"] == "json_schema"


def test_openai_compatible_generation_uses_text_only_after_structural_schema_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, *, status_code: int, payload: dict[str, Any] | None = None):
            self.status_code = status_code
            self.is_success = status_code < 400
            self._payload = payload or {}
            self.text = '{"error":"structured transport rejected"}'

        def json(self) -> dict[str, Any]:
            return self._payload

    responses = [
        FakeResponse(status_code=400),
        FakeResponse(status_code=422),
        FakeResponse(
            status_code=200,
            payload={
                "choices": [{"message": {"content": '{"item": {"ok": true}}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
            },
        ),
    ]

    def fake_post(_url: str, **kwargs: Any) -> FakeResponse:
        payloads.append(kwargs["json"])
        return responses.pop(0)

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.post", fake_post)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_api_key="not-needed",
        model_name="google/gemma-local",
    )
    schema = {
        "type": "object",
        "title": "Annotated response",
        "required": ["item"],
        "properties": {
            "item": {
                "type": "object",
                "title": "Nested item",
                "properties": {"ok": {"type": "boolean", "default": False}},
            }
        },
    }
    gateway = OpenAICompatibleGateway(settings)

    assert gateway.generate_structured(system="Return valid JSON.", prompt="Confirm.", schema=schema) == {
        "item": {"ok": True}
    }
    projected = payloads[1]["response_format"]["json_schema"]["schema"]
    assert projected == {
        "type": "object",
        "required": ["item"],
        "properties": {
            "item": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
            }
        },
    }
    assert payloads[2]["response_format"] == {"type": "text"}
    assert json.dumps(schema, ensure_ascii=False, separators=(",", ":")) in payloads[2]["messages"][0]["content"]


def test_lmstudio_residency_reports_missing_models_without_loading_or_unloading(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, dict[str, Any]]] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, Any], status_code: int = 200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs: Any):
            calls.append(("CLIENT", "", kwargs))

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **kwargs: Any) -> FakeResponse:
            calls.append(("GET", url, kwargs))
            if "/api/v1/models" not in url:
                return FakeResponse(
                    {"data": [{"id": "google/gemma-local"}, {"id": "text-embedding-bge-m3"}]}
                )
            return FakeResponse(
                {
                    "models": [
                        {"key": model, "loaded_instances": []}
                        for model in ("google/gemma-local", "text-embedding-bge-m3")
                    ]
                }
            )

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            calls.append(("POST", url, kwargs))
            raise AssertionError("BoI Wiki must not call LM Studio load or unload endpoints")

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.Client", FakeClient)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_name="google/gemma-local",
        embedding_provider="openai_compatible",
        embedding_base_url="http://lmstudio.example:1234/v1",
        embedding_model="text-embedding-bge-m3",
        lmstudio_require_preloaded_models=True,
        lmstudio_native_base_url="",
    )

    result = ensure_lmstudio_model_residency(settings)

    assert result["ready"] is False
    assert result["status"] == "missing"
    assert result["loaded_models"] == []
    assert result["missing_models"] == ["google/gemma-local", "text-embedding-bge-m3"]
    assert result["load_requests"] == []
    assert result["unload_requests"] == 0
    assert all(method != "POST" for method, _, _ in calls)


def test_lmstudio_residency_does_not_reload_models_that_are_already_loaded(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        @staticmethod
        def raise_for_status() -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self.payload

    class FakeClient:
        def __init__(self, **_kwargs: Any):
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"GET {url}")
            if "/api/v1/models" in url:
                return FakeResponse(
                    {
                        "models": [
                            {"key": "google/gemma-local", "loaded_instances": [{"id": "gemma"}]},
                            {"key": "text-embedding-bge-m3", "loaded_instances": [{"id": "embedding"}]},
                        ]
                    }
                )
            return FakeResponse(
                {"data": [{"id": "google/gemma-local"}, {"id": "text-embedding-bge-m3"}]}
            )

        def post(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"POST {url}")
            return FakeResponse({})

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.Client", FakeClient)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_name="google/gemma-local",
        embedding_provider="openai_compatible",
        embedding_base_url="http://lmstudio.example:1234/v1",
        embedding_model="text-embedding-bge-m3",
        lmstudio_require_preloaded_models=True,
        lmstudio_native_base_url="",
    )

    result = ensure_lmstudio_model_residency(settings)

    assert result["ready"] is True
    assert result["jit_loading_detected"] is False
    assert result["manual_models"] == ["google/gemma-local", "text-embedding-bge-m3"]
    assert result["load_requests"] == []
    assert all(not call.startswith("POST") for call in calls)


def test_lmstudio_generation_stays_ready_when_only_embedding_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        @staticmethod
        def raise_for_status() -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self.payload

    class FakeClient:
        def __init__(self, **_kwargs: Any):
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"GET {url}")
            if "/api/v1/models" in url:
                return FakeResponse(
                    {
                        "models": [
                            {
                                "key": "google/gemma-local",
                                "loaded_instances": [{"id": "gemma", "remaining_ttl_seconds": None}],
                            },
                            {"key": "text-embedding-bge-m3", "loaded_instances": []},
                        ]
                    }
                )
            return FakeResponse(
                {"data": [{"id": "google/gemma-local"}, {"id": "text-embedding-bge-m3"}]}
            )

        def post(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"POST {url}")
            raise AssertionError("model mutation is forbidden")

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.Client", FakeClient)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_name="google/gemma-local",
        embedding_provider="openai_compatible",
        embedding_base_url="http://lmstudio.example:1234/v1",
        embedding_model="text-embedding-bge-m3",
        lmstudio_require_preloaded_models=True,
        lmstudio_native_base_url="",
    )

    result = ensure_lmstudio_model_residency(settings)

    assert result["ready"] is False
    assert result["generation_ready"] is True
    assert result["embedding_ready"] is False
    require_lmstudio_models_preloaded(settings, required_models=[settings.model_name])
    with pytest.raises(RuntimeError, match="text-embedding-bge-m3"):
        require_lmstudio_models_preloaded(settings, required_models=[settings.embedding_model])
    assert all(not call.startswith("POST") for call in calls)


def test_lmstudio_residency_allows_manual_models_when_jit_is_enabled_for_other_models(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self.payload

    class FakeClient:
        def __init__(self, **_kwargs: Any):
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> FakeResponse:
            if "/api/v1/models" in url:
                return FakeResponse(
                    {
                        "models": [
                            {"key": "google/gemma-local", "loaded_instances": [{"id": "gemma"}]},
                            {"key": "text-embedding-bge-m3", "loaded_instances": [{"id": "embedding"}]},
                            {"key": "other/downloaded-model", "loaded_instances": []},
                        ]
                    }
                )
            return FakeResponse(
                {
                    "data": [
                        {"id": "google/gemma-local"},
                        {"id": "text-embedding-bge-m3"},
                        {"id": "other/downloaded-model"},
                    ]
                }
            )

        def post(self, _url: str, **_kwargs: Any) -> FakeResponse:
            raise AssertionError("model mutation is forbidden")

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.Client", FakeClient)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_name="google/gemma-local",
        embedding_provider="openai_compatible",
        embedding_base_url="http://lmstudio.example:1234/v1",
        embedding_model="text-embedding-bge-m3",
        lmstudio_require_preloaded_models=True,
        lmstudio_native_base_url="",
    )

    result = ensure_lmstudio_model_residency(settings)

    assert result["ready"] is True
    assert result["status"] == "ready_with_jit_enabled"
    assert result["jit_loading_detected"] is True
    assert result["manual_models"] == ["google/gemma-local", "text-embedding-bge-m3"]
    assert result["load_requests"] == []
    assert result["unload_requests"] == 0


def test_lmstudio_residency_rejects_jit_ttl_instances_without_mutating_them(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        @staticmethod
        def raise_for_status() -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self.payload

    class FakeClient:
        def __init__(self, **_kwargs: Any):
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"GET {url}")
            if "/api/v1/models" in url:
                return FakeResponse(
                    {
                        "models": [
                            {
                                "key": model,
                                "loaded_instances": [{"id": model, "remaining_ttl_seconds": 3600}],
                            }
                            for model in ("google/gemma-local", "text-embedding-bge-m3")
                        ]
                    }
                )
            return FakeResponse(
                {"data": [{"id": "google/gemma-local"}, {"id": "text-embedding-bge-m3"}]}
            )

        def post(self, url: str, **_kwargs: Any) -> FakeResponse:
            calls.append(f"POST {url}")
            raise AssertionError("model mutation is forbidden")

    monkeypatch.setattr("boi_api.app.v2.model_gateway.httpx.Client", FakeClient)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    settings = replace(
        base,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_name="google/gemma-local",
        embedding_provider="openai_compatible",
        embedding_base_url="http://lmstudio.example:1234/v1",
        embedding_model="text-embedding-bge-m3",
        lmstudio_require_preloaded_models=True,
        lmstudio_native_base_url="",
    )

    result = ensure_lmstudio_model_residency(settings)

    assert result["ready"] is False
    assert result["status"] == "jit_only"
    assert result["manual_models"] == []
    assert result["jit_models"] == ["google/gemma-local", "text-embedding-bge-m3"]
    assert all(not call.startswith("POST") for call in calls)


@pytest.mark.parametrize("model_name", ["gpt-5.5", "gpt-5.6", "managed-reasoning-model"])
def test_explicit_v2_model_is_never_rewritten_from_its_name(
    monkeypatch: pytest.MonkeyPatch,
    model_name: str,
):
    monkeypatch.setenv("BOI_GPT55_TEST_MODE", "false")
    monkeypatch.setenv("BOI_V2_MODEL_PROVIDER", "openai_responses")
    monkeypatch.setenv("BOI_V2_MODEL_BASE_URL", "https://llm-gateway.example.internal/v1")
    monkeypatch.setenv("BOI_V2_MODEL_API_KEY", "test-external-key")
    monkeypatch.setenv("BOI_V2_MODEL", model_name)
    monkeypatch.setenv("BOI_DEEPAGENTS_MODEL", model_name)
    monkeypatch.setenv("BOI_LLM_BASE_URL", "http://lmstudio.example:1234/v1")
    monkeypatch.setenv("BOI_LLM_API_KEY", "not-needed")
    monkeypatch.setenv("BOI_LLM_MODEL", "google/gemma-local")
    monkeypatch.setenv("BOI_AGENT_LLM_MODEL", "google/gemma-local")

    settings = AgentV2Settings.from_environment(repo_root=ROOT)

    assert settings.model_provider == "openai_responses"
    assert settings.model_base_url == "https://llm-gateway.example.internal/v1"
    assert settings.model_name == model_name
    assert settings.deep_model == model_name
    assert settings.model_route == "configured"
    assert settings.gpt55_test_mode is False


def test_explicit_external_judge_mode_preserves_the_configured_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOI_GPT55_TEST_MODE", "true")
    monkeypatch.setenv("BOI_V2_MODEL_PROVIDER", "openai_responses")
    monkeypatch.setenv("BOI_V2_MODEL_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("BOI_V2_MODEL_API_KEY", "test-external-key")
    monkeypatch.setenv("BOI_V2_MODEL", "gpt-5.5")
    monkeypatch.setenv("BOI_DEEPAGENTS_MODEL", "gpt-5.5")

    settings = AgentV2Settings.from_environment(repo_root=ROOT)

    assert settings.model_provider == "openai_responses"
    assert settings.model_name == "gpt-5.5"
    assert settings.deep_model == "gpt-5.5"
    assert settings.model_route == "configured"
    assert settings.gpt55_test_mode is True


def test_context_budget_uses_runtime_capacity_without_model_name_rules():
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    local = replace(
        base,
        model_provider="openai_compatible",
        model_name="any-local-model",
        model_context_window_tokens=0,
        model_max_output_tokens=8_192,
        model_context_reserve_tokens=8_192,
        lmstudio_require_preloaded_models=False,
        model_base_url="",
    )
    local_resolution = resolve_context_budget(
        local,
        requested_tokens=0,
        residency_state={"generation_context_window": 51_200},
    )

    managed = replace(
        local,
        model_provider="openai_responses",
        model_name="managed-reasoning-model",
        model_context_window_tokens=262_144,
    )
    managed_profile = inspect_model_runtime_profile(managed)
    managed_resolution = resolve_context_budget(managed, requested_tokens=0)
    explicitly_bounded = resolve_context_budget(managed, requested_tokens=160_000)

    assert local_resolution.effective_tokens == 34_816
    assert local_resolution.requested_tokens == 0
    assert local_resolution.profile_source == "provider_runtime"
    assert managed_profile.context_window_tokens == 262_144
    assert managed_profile.source == "deployment_config"
    assert managed_resolution.effective_tokens == 245_760
    assert managed_resolution.requested_tokens == 0
    assert explicitly_bounded.effective_tokens == 160_000


def test_normal_runtime_does_not_inherit_openai_credentials(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "BOI_V2_MODEL_BASE_URL",
        "BOI_V2_MODEL_API_KEY",
        "BOI_V2_MODEL",
        "BOI_LLM_BASE_URL",
        "BOI_LLM_API_KEY",
        "BOI_LLM_MODEL",
        "BOI_AGENT_LLM_MODEL",
        "BOI_DEEPAGENTS_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BOI_GPT55_TEST_MODE", "false")
    monkeypatch.setenv("OPENAI_API_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("OPENAI_API_MODEL", "gpt-5.5")

    settings = AgentV2Settings.from_environment(repo_root=ROOT)

    assert settings.model_base_url == ""
    assert settings.model_api_key == ""
    assert settings.model_name == ""
    assert settings.gpt55_test_mode is False


def test_source_signature_is_stable_across_host_and_container_mount_paths(tmp_path: Path):
    first_root = tmp_path / "host" / "boi"
    second_root = tmp_path / "container" / "boi"
    _write_markdown(
        first_root / "public" / "shared.md",
        {"boi_id": "boi:public:shared", "title": "공유 지식", "visibility": "public", "status": "reviewed"},
        "같은 정본은 설치 경로가 달라도 같은 검색 revision을 가져야 합니다.",
    )
    second_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(first_root, second_root, copy_function=shutil.copy2)
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    empty = tmp_path / "empty"
    common = {
        "event_catalog_root": empty,
        "action_catalog_root": empty,
        "workflow_catalog_root": empty,
        "action_skill_catalog_root": empty,
    }

    host = KnowledgeRepository(replace(base, content_root=first_root, **common))
    container = KnowledgeRepository(replace(base, content_root=second_root, **common))

    assert host.source_signature() == container.source_signature()


def test_deprecated_knowledge_is_excluded_from_default_searchable_records(
    tmp_path: Path,
    principal: Principal,
):
    content_root = tmp_path / "boi"
    _write_markdown(
        content_root / "public" / "current.md",
        {
            "boi_id": "boi:public:current-guide",
            "title": "현재 BoI Agent 가이드",
            "visibility": "public",
            "status": "reviewed",
        },
        "현재 사용자가 따라야 하는 가이드입니다.",
    )
    _write_markdown(
        content_root / "public" / "legacy.md",
        {
            "boi_id": "boi:public:legacy-guide",
            "title": "이전 BoI Agent 가이드",
            "visibility": "public",
            "status": "deprecated",
        },
        "감사와 이력 확인을 위해 보존한 이전 가이드입니다.",
    )
    navigation_index = content_root / "public" / "index.md"
    navigation_index.write_text(
        "# 공개 폴더 안내\n\nINDEX_NAVIGATION_SENTINEL은 검색 근거가 아닙니다.\n",
        encoding="utf-8",
    )
    (content_root / "public" / "log.md").write_text(
        "# 변경 기록\n\nLOG_NAVIGATION_SENTINEL은 검색 근거가 아닙니다.\n",
        encoding="utf-8",
    )
    base = AgentV2Settings.from_environment(repo_root=ROOT)
    empty = tmp_path / "empty"
    repository = KnowledgeRepository(
        replace(
            base,
            content_root=content_root,
            event_catalog_root=empty,
            action_catalog_root=empty,
            workflow_catalog_root=empty,
            action_skill_catalog_root=empty,
        )
    )

    default_ids = {item.record_id for item in repository.authoritative_records(principal)}
    diagnostic_ids = {
        item.record_id
        for item in repository.authoritative_records(principal, include_drafts=True)
    }

    assert default_ids == {"boi:public:current-guide"}
    assert diagnostic_ids == {"boi:public:current-guide", "boi:public:legacy-guide"}
    signature_before = repository.source_signature()
    navigation_index.write_text("# 공개 폴더 안내\n\n탐색 링크만 바뀌었습니다.\n", encoding="utf-8")
    repository.invalidate_source_cache()
    assert repository.source_signature() == signature_before


def test_quick_agent_uses_structured_llm_planning_and_defaults_ambiguous_sop_questions_to_search(
    v2_service: AgentV2Service,
):
    def planned(
        capability_id: str,
        *,
        effect: str = "read",
        operation: str = "understand",
        presentation: str = "prose",
        work_view: str = "none",
    ) -> dict[str, Any]:
        return SemanticPlan(
            resolved_goal=f"{capability_id} 계약으로 요청을 처리한다",
            retrieval_query=capability_id,
            capability_id=capability_id,
            user_effect=effect,  # type: ignore[arg-type]
            operation=operation,  # type: ignore[arg-type]
            evidence_scope="canonical",
            presentation=presentation,  # type: ignore[arg-type]
            work_view=work_view,  # type: ignore[arg-type]
            loop_contract=_catalog_loop_contract(capability_id),
            confidence=1.0,
        ).model_dump(mode="json")

    model = ScriptedPlanner(
        plans=[
            planned("knowledge.search", operation="connect"),
            planned("business_event.plan", effect="draft", operation="create", presentation="artifact"),
            planned("knowledge.search"),
            planned("knowledge.search"),
            planned("knowledge.search"),
            planned("sop.plan", effect="draft", operation="create", presentation="artifact"),
            planned("work.inbox", operation="observe", work_view="current"),
            planned("work.inbox", operation="observe", work_view="current"),
            planned("sop.plan", effect="transform", operation="refine", presentation="artifact"),
            planned("sop.plan", effect="transform", operation="create", presentation="artifact"),
            planned("sop.plan", effect="draft", operation="create", presentation="artifact"),
        ]
    )
    question_route = v2_service.quick_agent.route("SOP와 업무 이벤트가 어떻게 연결돼?", page_kind="sop", model=model)
    draft_route = v2_service.quick_agent.route("업무 이벤트 정의 초안을 만들어줘", page_kind="event", model=model)
    search_route = v2_service.quick_agent.route("업무 이벤트 정의 만들기 자료를 찾아줘", page_kind="event", model=model)
    how_to_route = v2_service.quick_agent.route("업무 이벤트 정의는 어떻게 만들어?", page_kind="event", model=model)
    ambiguous_noun_route = v2_service.quick_agent.route("업무 이벤트 정의 초안", page_kind="event", model=model)
    search_then_draft = v2_service.quick_agent.route("관련 자료를 찾아 SOP 초안을 만들어줘", page_kind="sop", model=model)
    inbox_route = v2_service.quick_agent.route("현재 내 할 일을 보여줘", page_kind="library", model=model)
    natural_inbox_route = v2_service.quick_agent.route(
        "내가 지금 처리해야 할 업무와 다음에 확인할 내용을 보여줘",
        page_kind="library",
        model=model,
    )
    active_sop_followup = v2_service.quick_agent.route(
        "이 초안의 Task 완료 항목을 다듬어줘",
        page_kind="agent",
        active_capability="sop.plan",
        model=model,
    )
    knowledge_to_tasks = v2_service.quick_agent.route(
        "이걸 Task로 나눠줘",
        page_kind="agent",
        active_capability="knowledge.draft",
        model=model,
    )

    assert question_route["engine"] == "langgraph"
    assert question_route["capability_id"] == "knowledge.search"
    assert question_route["source"] == "llm_structured"
    assert question_route["reason"] == "semantic_plan_validated"
    assert draft_route["capability_id"] == "business_event.plan"
    assert search_route["capability_id"] == "knowledge.search"
    assert search_route["reason"] == "semantic_plan_validated"
    assert how_to_route["capability_id"] == "knowledge.search"
    assert ambiguous_noun_route["capability_id"] == "knowledge.search"
    assert search_then_draft["capability_id"] == "sop.plan"
    assert inbox_route["capability_id"] == "work.inbox"
    assert natural_inbox_route["capability_id"] == "work.inbox"
    assert active_sop_followup["capability_id"] == "sop.plan"
    assert active_sop_followup["reason"] == "semantic_plan_validated"
    assert knowledge_to_tasks["capability_id"] == "sop.plan"
    assert v2_service.quick_agent.route("Alarm 대응 SOP 만들어", page_kind="sop", model=model)["capability_id"] == "sop.plan"


def test_identical_cross_interface_turns_reuse_the_same_semantic_route_and_evidence(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CountingSemanticRouteModel()
    v2_service.model = model
    v2_service.search.model = model
    request = {
        "question": "BoI Wiki 운영 가이드의 게시 기준과 확인 근거를 알려줘.",
        "page_ref": "/docs/boi:public:guide",
    }

    first = v2_service.run_turn(principal, AgentTurnRequest(**request))
    second = v2_service.run_turn(principal, AgentTurnRequest(**request))
    first_context = v2_service.store.get("contexts", first.context_ref) or {}
    second_context = v2_service.store.get("contexts", second.context_ref) or {}

    assert model.planner_calls == 1
    assert first.work_intent == second.work_intent
    assert [item["evidence_id"] for item in first_context["evidence_refs"]] == [
        item["evidence_id"] for item in second_context["evidence_refs"]
    ]


def test_targetless_task_plan_is_rejected_instead_of_rewritten_as_search(
    v2_service: AgentV2Service,
):
    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service.quick_agent.route(
            "단면검사 Task에서 이전에 확인한 판단 기록을 찾아줘",
            page_kind="library",
            model=TargetlessTaskLookupModel(),
        )

    assert exc_info.value.code == "planner_invalid"
    assert exc_info.value.report is not None
    assert {item.code for item in exc_info.value.report.issues} == {"subject.target_required"}


def test_action_subject_on_task_capability_is_rejected_instead_of_remapped(
    v2_service: AgentV2Service,
):
    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service.quick_agent.route(
            "manual.review Action을 case_id A-100으로 dry-run 실행해줘.",
            page_kind="action",
            trusted_targets={"action_key": "manual.review"},
            model=MisroutedActionRunModel(),
        )

    assert exc_info.value.code == "planner_invalid"
    assert exc_info.value.report is not None
    assert "subject.kind_not_supported" in {item.code for item in exc_info.value.report.issues}


def test_natural_language_router_never_uses_keyword_draft_guessing_when_the_intent_model_is_unavailable(
    v2_service: AgentV2Service,
):
    unavailable = UnavailableModelGateway("planner unavailable")

    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service.quick_agent.route(
            "설비 Alarm 대응 SOP를 만들고 Action까지 실행해줘",
            page_kind="sop",
            model=unavailable,
        )

    assert exc_info.value.code == "planner_unavailable"


def test_explaining_cross_asset_connections_does_not_run_an_authoring_harness(
    v2_service: AgentV2Service,
    principal: Principal,
):
    source_ref = "boi:public:sop:manual"
    model = ScriptedPlanner(
        plans=[
            SemanticPlan(
                resolved_goal="선택한 SOP와 관련 업무 이벤트 및 Action의 검증된 연결을 설명한다",
                retrieval_query="SOP 업무 이벤트 Action 연결",
                subjects=[
                    SemanticSubject(
                        mention="사람 검토 SOP",
                        entity_ref=source_ref,
                        entity_kind="sop",
                        resolution="resolved",
                    )
                ],
                capability_id="knowledge.search",
                user_effect="read",
                operation="connect",
                evidence_scope="canonical",
                presentation="prose",
                context_refs=[source_ref],
                target_ref=source_ref,
                confidence=1.0,
            ).model_dump(mode="json")
        ]
    )
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 SOP의 관련 업무 이벤트와 Action을 Wiki 전체에서 연결해 설명해줘.",
            page_ref="/docs/boi%3Apublic%3Asop%3Amanual?employee_id=100001",
        ),
    )

    assert response.capability_id == "knowledge.search"
    assert response.work_intent is not None
    assert response.work_intent.asset_kind.value == "knowledge"
    assert response.work_intent.operation.value == "connect"
    assert response.work_intent.desired_outcome == "search_results"
    assert [item.harness_id for item in response.harness_results] == ["context.work"]
    assert response.loop_state["status"] == "completed"


def test_empty_current_work_is_a_valid_result_instead_of_a_context_failure(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])
    model = ScriptedPlanner(
        plans=[
            SemanticPlan(
                resolved_goal="현재 처리할 업무와 다음 확인 내용을 조회한다",
                retrieval_query="현재 처리할 업무",
                capability_id="work.inbox",
                user_effect="read",
                operation="observe",
                evidence_scope="operational",
                presentation="prose",
                work_view="current",
                confidence=1.0,
            ).model_dump(mode="json")
        ]
    )
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="내가 지금 처리해야 할 업무와 다음에 확인할 내용을 보여줘.",
            page_ref="/",
        ),
    )

    assert response.capability_id == "work.inbox"
    assert response.answer.summary.startswith("현재 처리할 Inbox 업무가 없습니다")
    assert response.loop_state["status"] == "completed"
    assert [item.status for item in response.harness_results] == ["warning"]


def test_current_work_projection_emits_chunk_bound_operational_claims(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner(
        plans=[
            SemanticPlan(
                resolved_goal="현재 처리할 업무를 조회한다",
                retrieval_query="현재 처리할 업무",
                capability_id="work.inbox",
                user_effect="read",
                operation="observe",
                evidence_scope="operational",
                presentation="prose",
                work_view="current",
                confidence=1.0,
            ).model_dump(mode="json")
        ]
    )
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="지금 처리할 업무만 보여줘", page_ref="/inbox"),
    )

    assert response.answerability.status == "grounded"
    assert response.grounded_claims
    assert all(item.source_scope == "operational" for item in response.grounded_claims)
    assert all(item.support_status == "supported" for item in response.grounded_claims)
    assert all(item.supporting_chunk_ids for item in response.grounded_claims)
    assert response.used_source_refs == [item.source_ref for item in response.citations]


def test_invalid_current_work_plan_is_not_rewritten_to_another_capability(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = MisroutedCurrentWorkReviewModel()
    v2_service.model = model
    v2_service.search.model = model
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="내가 지금 처리해야 할 업무와 먼저 확인할 근거를 보여줘.", page_ref="/inbox"),
    )

    assert response.capability_id == "semantic.planner"
    assert response.error_code == "planner_invalid"
    assert response.work_intent is None
    assert response.graph_result_ref == ""
    assert response.artifact_refs == []


def test_valid_planner_semantics_are_not_rewritten_by_question_text(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = RuntimeOnlyWrongScopeReviewModel()
    v2_service.model = model
    v2_service.search.model = model
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="내가 지금 처리해야 할 업무와 먼저 확인할 근거를 보여줘.", page_ref="/inbox"),
    )

    assert response.capability_id == "knowledge.search"
    assert response.work_intent and response.work_intent.work_view == "combined"


def test_current_work_view_rejects_a_knowledge_only_result_contract(v2_service: AgentV2Service):
    with pytest.raises(SemanticPlanningError) as exc_info:
        v2_service.quick_agent.route(
            "업무 학습 순환을 그림으로 보여줘",
            page_kind="document",
            model=KnowledgeCurrentScopeContradictionModel(),
        )

    assert exc_info.value.code == "planner_invalid"
    assert exc_info.value.report is not None
    assert any(
        item.code == "capability.work_view_not_allowed"
        for item in exc_info.value.report.issues
    )


def test_broad_work_question_is_semantically_reviewed_as_roles_plus_current_work(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = BroadWorkQuestionReviewModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="내가 하는 일이 뭐지?", page_ref="/"),
    )

    assert response.capability_id == "knowledge.search"
    assert response.work_intent and response.work_intent.work_view == "combined"
    assert response.graph_result_ref
    assert any(item.artifact_type == "ontology_graph" for item in response.artifact_refs)
    assert response.citations
    assert response.answerability.status == "grounded"
    assert response.grounded_claims
    assert all(item.support_status == "supported" for item in response.grounded_claims)
    assert all(item.supporting_chunk_ids for item in response.grounded_claims)
    assert any(item.claim_kind == "relationship" for item in response.grounded_claims)
    assert any(item.claim_kind == "work" for item in response.grounded_claims)
    assert response.used_source_refs == [item.source_ref for item in response.citations]
    context = v2_service.get_context(principal, response.context_ref)
    selected_refs = {
        item["evidence_id"]
        for item in context["evidence_refs"]
    }
    assert set(response.used_source_refs).issubset(selected_refs)
    assert set(response.used_source_refs).issubset(
        set(context["context_manifest"]["selected_refs"])
    )
    assert "지금 처리할 업무" in response.answer.markdown
    session = v2_service.store.get("work_sessions", response.work_session_id)
    assert session is not None
    assert "person:100001" in session["topic_state"]["entities"]
    assert "현재 사용자" not in session["topic_state"]["entities"]


def test_explorer_presentation_builds_graph_without_explicit_draft(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    source_ref = "boi:public:guide"
    semantic_plan = SemanticPlan(
        resolved_goal="종합 가이드 중심 관계 탐색 화면을 제공한다",
        retrieval_query="종합 가이드 직접 연결 업무 관계",
        subjects=[
            SemanticSubject(
                mention="종합 가이드",
                entity_ref=source_ref,
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="canonical",
        presentation="explorer",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="neighbors",
            focal_mentions=[source_ref],
            presentation="explorer",
        ),
        context_refs=[source_ref],
        target_ref=source_ref,
        answer_intent="relationship",
        confidence=1.0,
    )
    route = {
        "capability_id": "knowledge.search",
        "source": "llm_structured",
        "reason": "관계 탐색 화면 요청",
        "semantic_plan": semantic_plan.model_dump(mode="json"),
        "work_intent": WorkIntent(
            goal="종합 가이드와 직접 연결된 업무 관계를 탐색한다",
            resolved_goal="종합 가이드 중심 관계 탐색 화면을 제공한다",
            asset_kind=WorkAssetKind.knowledge,
            # The planner may classify a one-document request as understand
            # while still correctly choosing an interactive relationship view.
            # Explorer is only valid when the server can ground a graph plan.
            operation=WorkOperation.understand,
            operation_plan=[WorkOperation.understand],
            context_refs=[source_ref],
            target_ref=source_ref,
            presentation_mode="explorer",
            graph_query_draft=GraphQueryDraft(
                enabled=True,
                query_kind="neighbors",
                focal_mentions=[source_ref],
                presentation="explorer",
            ),
            result_purpose="explain",
            confidence=1.0,
        ).model_dump(mode="json"),
    }
    monkeypatch.setattr(v2_service, "_semantic_route", lambda *_args, **_kwargs: route)

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="종합 가이드와 직접 연결된 업무 관계를 탐색해줘"),
    )

    assert response.work_intent and response.work_intent.graph_query_draft
    assert response.work_intent.graph_query_draft.presentation == "explorer"
    assert response.graph_result_ref
    assert any(item.artifact_type == "ontology_graph" for item in response.artifact_refs)


def test_read_only_mermaid_uses_grounded_graph_before_a_second_model_call(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    source_ref = "boi:public:guide"
    semantic_plan = SemanticPlan(
        resolved_goal="종합 가이드의 검증된 관계를 Mermaid로 보여준다",
        retrieval_query="종합 가이드 검증된 업무 관계",
        subjects=[
            SemanticSubject(
                mention="종합 가이드",
                entity_ref=source_ref,
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="canonical",
        presentation="mermaid",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="neighbors",
            focal_mentions=[source_ref],
            presentation="mermaid",
        ),
        context_refs=[source_ref],
        target_ref=source_ref,
        answer_intent="relationship",
        confidence=1.0,
    )
    route = {
        "capability_id": "knowledge.search",
        "source": "llm_structured",
        "reason": "근거 관계를 흐름 그림으로 설명",
        "semantic_plan": semantic_plan.model_dump(mode="json"),
        "work_intent": WorkIntent(
            goal="종합 가이드와 연결된 업무 관계를 그림으로 설명한다",
            resolved_goal="종합 가이드의 검증된 관계를 Mermaid로 보여준다",
            asset_kind=WorkAssetKind.knowledge,
            operation=WorkOperation.understand,
            operation_plan=[WorkOperation.understand],
            context_refs=[source_ref],
            target_ref=source_ref,
            presentation_mode="mermaid",
            graph_query_draft=GraphQueryDraft(
                enabled=True,
                query_kind="neighbors",
                focal_mentions=[source_ref],
                presentation="mermaid",
            ),
            result_purpose="explain",
            confidence=1.0,
        ).model_dump(mode="json"),
    }
    monkeypatch.setattr(v2_service, "_semantic_route", lambda *_args, **_kwargs: route)
    monkeypatch.setattr(
        v2_service,
        "_mermaid_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("second model diagram call")),
    )

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="종합 가이드와 연결된 업무 관계를 흐름 그림으로 보여줘"),
    )

    assert response.work_intent and response.work_intent.graph_query_draft
    assert response.work_intent.graph_query_draft.presentation == "mermaid"
    assert response.graph_result_ref
    assert response.artifact_refs[0].artifact_type == "mermaid_diagram"
    assert response.artifact_refs[0].metadata["presentation"] == "mermaid"
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    assert artifact["draft"]["presentation"] == "mermaid"
    assert artifact["draft"]["edges"]


def test_bounded_mermaid_expands_from_one_focal_when_retrieval_has_many_sources():
    plan = GraphQueryPlan(
        focal_entities=["doc:a", "doc:unrelated"],
        query_kind="neighbors",
        presentation="mermaid",
    )
    nodes = [
        {"node_id": "doc:a", "payload": {"source_refs": ["doc:a"]}},
        {"node_id": "doc:b", "payload": {"source_refs": ["doc:b"]}},
        {"node_id": "doc:unrelated", "payload": {"source_refs": ["doc:unrelated"]}},
    ]
    edges = [
        {
            "edge_id": "edge:a-b",
            "source_id": "doc:a",
            "target_id": "doc:b",
            "payload": {"source_refs": ["doc:a", "doc:b"]},
        }
    ]

    selected_nodes, selected_edges = AgentV2Service._bounded_mermaid_graph(plan, nodes, edges)

    assert {item["node_id"] for item in selected_nodes} == {"doc:a", "doc:b"}
    assert [item["edge_id"] for item in selected_edges] == ["edge:a-b"]


def test_completion_design_wording_does_not_become_a_task_completion_operation(
    v2_service: AgentV2Service,
):
    question = "기존 SOP를 재사용하고 Task별 완료된 모습과 확인할 자료를 넣은 SOP 초안을 만들어줘."
    plan = SemanticPlan(
        resolved_goal="기존 SOP를 재사용해 완료 조건과 근거가 있는 SOP 초안을 만든다",
        retrieval_query="기존 SOP 완료 조건 근거",
        capability_id="sop.plan",
        user_effect="draft",
        operation="create",
        context_refs=["boi:public:sop:manual"],
        target_ref="boi:public:sop:manual",
        loop_contract=_catalog_loop_contract("sop.plan"),
        confidence=1.0,
    )
    route = v2_service.quick_agent.route(
        question,
        page_kind="sop",
        trusted_targets={"sop_ref": "boi:public:sop:manual"},
        model=ScriptedPlanner([plan.model_dump(mode="json")]),
    )
    intent = WorkIntent.model_validate(route["work_intent"])

    assert route["capability_id"] == "sop.plan"
    assert [item.value for item in intent.operation_plan] == [
        "understand",
        "create",
        "validate",
    ]


def test_current_page_is_a_wiki_wide_search_anchor_even_when_the_url_is_encoded(
    v2_service: AgentV2Service,
    principal: Principal,
):
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 문서의 판단 기준과 연결된 지식을 Wiki 전체에서 알려줘",
            page_ref="/docs/boi%3Apublic%3Aguide?employee_id=100001",
        ),
    )

    assert response.context_usage["page_anchor"]["ref"] == "boi:public:guide"
    assert response.context_usage["page_anchor"]["resolved"] is True
    assert response.evidence_refs[0].evidence_id == "boi:public:guide"
    assert response.work_intent and response.work_intent.scope == "auto"
    context = v2_service.get_context(principal, response.context_ref)
    assert context["context_manifest"]["selected_refs"][0] == "boi:public:guide"


def test_current_page_only_boosts_results_that_are_relevant_to_the_question(
    v2_service: AgentV2Service,
    principal: Principal,
):
    response = v2_service.search.search(
        "단면검사의 정의",
        principal,
        limit=8,
        page_ref="/docs/boi%3Apublic%3Aguide",
        answer_scopes={"canonical", "operational"},
    )

    refs = [item.evidence_id for item in response.items]
    assert "boi:public:dictionary:cross-section-inspection" in refs
    assert "boi:public:guide" not in refs


def test_resolved_current_page_is_a_primary_planner_hint_without_limiting_wiki_search(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    def semantic_route(_principal: Principal, route_input: dict[str, Any]) -> dict[str, Any]:
        captured.update(route_input)
        semantic_plan = SemanticPlan(
            resolved_goal=route_input["question"],
            retrieval_query="현재 문서 관련 기준 Wiki 전체",
            capability_id="knowledge.search",
            user_effect="read",
            operation="understand",
            evidence_scope="canonical",
            presentation="prose",
            answer_intent="procedure",
            confidence=1.0,
        )
        return {
            "capability_id": "knowledge.search",
            "source": "llm_structured",
            "reason": "현재 문서와 Wiki 전체를 함께 이해",
            "semantic_plan": semantic_plan.model_dump(mode="json"),
            "work_intent": WorkIntent(
                goal=route_input["question"],
                resolved_goal=route_input["question"],
                asset_kind=WorkAssetKind.knowledge,
                operation=WorkOperation.understand,
                operation_plan=[WorkOperation.understand],
                scope="wiki",
                presentation_mode="prose",
                result_purpose="explain",
                confidence=1.0,
            ).model_dump(mode="json"),
        }

    monkeypatch.setattr(v2_service, "_semantic_route", semantic_route)

    v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 문서를 출발점으로 관련 기준을 Wiki 전체에서 설명해줘",
            page_ref="/docs/boi%3Apublic%3Aguide?employee_id=100001",
        ),
    )

    hints = captured["knowledge_hints"]
    assert hints[0]["ref"] == "boi:public:guide"
    assert hints[0]["is_primary"] is True
    assert any(item["ref"] != "boi:public:guide" for item in hints)


def test_multiturn_visual_followup_resolves_the_prior_subject_and_creates_grounded_mermaid(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = MultiTurnMermaidModel(["prose", "mermaid"])
    v2_service.model = model
    v2_service.search.model = model
    first = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki의 RAG 검색 방식과 근거 연결 흐름을 설명해줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="머메이드 차트로 그려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
            work_session_id=first.work_session_id,
        ),
    )

    assert second.work_intent is not None
    assert second.work_intent.presentation_mode == "mermaid"
    assert "직전 답변" in second.work_intent.resolved_goal
    assert "머메이드 차트로 그려줘" in second.work_intent.resolved_goal
    assert "boi:public:guide" in second.work_intent.context_refs
    assert second.context_usage["resolved_goal"] == second.work_intent.resolved_goal
    assert second.context_usage["presentation_mode"] == "mermaid"
    assert second.work_intent.graph_query_draft is not None
    assert second.work_intent.graph_query_draft.query_kind == "neighbors"
    assert second.work_intent.graph_query_draft.presentation == "mermaid"
    assert "boi:public:guide" in second.work_intent.graph_query_draft.focal_mentions
    assert set(second.work_intent.graph_query_draft.focal_mentions) == set(second.work_intent.context_refs)
    assert second.artifact_refs[0].artifact_type == "mermaid_diagram"
    artifact = v2_service.get_artifact(principal, second.artifact_refs[0].artifact_id)
    assert artifact["draft"]["presentation"] == "mermaid"
    assert artifact["draft"]["mermaid"].startswith("flowchart")
    assert 1 <= len(artifact["draft"]["nodes"]) <= 10
    assert 1 <= len(artifact["draft"]["edges"]) <= 14
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["nodes"])
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["edges"])
    assert artifact["actions"] == []
    assert second.artifact_refs[0].actions == []
    assert "Task 또는 SOP" not in second.answer.markdown
    assert second.grounding_status == "grounded"
    assert second.answerability.status == "grounded"
    assert second.grounded_claims
    assert all(item.claim_kind == "relationship" for item in second.grounded_claims)
    assert all(item.support_status == "supported" for item in second.grounded_claims)
    assert set(second.used_source_refs) == set(artifact["draft"]["source_refs"])
    assert {item.source_ref for item in second.citations} == set(artifact["draft"]["source_refs"])
    assert all(item.citation_id in second.answer.markdown for item in second.citations)
    timeline = v2_service.session_timeline(principal, first.work_session_id)["items"]
    assert timeline[-2]["display_text"] == "머메이드 차트로 그려줘"
    assert timeline[-1]["artifact_refs"][0]["artifact_id"] == artifact["artifact_id"]
    assert model.planner_payloads[-1]["verified_topic_state"]["entities"]


def test_multiturn_visual_followup_uses_prior_citations_even_when_planner_prefers_inbox(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = InboxBiasedMermaidModel(["prose", "mermaid"])
    v2_service.model = model
    v2_service.search.model = model
    first = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki의 RAG 검색 방식과 근거 연결 흐름을 설명해줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="방금 설명한 관계만 머메이드로 보여줘",
            page_ref="/inbox",
            work_session_id=first.work_session_id,
        ),
    )

    assert second.capability_id == "knowledge.search"
    assert second.work_intent is not None
    assert second.work_intent.operation == WorkOperation.connect
    assert second.work_intent.work_view == "none"
    assert second.work_intent.context_refs
    assert second.grounding_status == "grounded"
    assert second.artifact_refs[0].artifact_type == "mermaid_diagram"


def test_read_only_mermaid_does_not_invent_transform_actions(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = MultiTurnMermaidModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 근거 흐름을 설명용 Mermaid로 보여줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert response.work_intent is not None
    assert response.work_intent.result_purpose == "explain"
    assert response.work_intent.artifact_actions == []
    assert response.artifact_refs[0].actions == []
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    assert artifact["actions"] == []


def test_task_split_followup_creates_workflow_draft_without_creating_an_sop_draft(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = SplitOnlyFollowupModel()
    v2_service.model = model
    v2_service.search.model = model
    domain_calls: list[dict[str, Any]] = []

    def split_handler(_principal: Principal, payload: dict[str, Any]) -> dict[str, Any]:
        domain_calls.append(payload)
        return {
            "ok": True,
            "domain_kind": "mermaid_workflow_draft",
            "domain_ref": "workflow-draft-1",
            "production_changed": False,
            "draft": {
                "draft_id": "workflow-draft-1",
                "title": payload["title"],
                "workflow_tasks": [
                    {
                        "task_id": "task-1",
                        "source_node": "N1",
                        "name": "업무 맥락 확인",
                        "execution_mode": "manual",
                        "exit_criteria": ["업무 맥락이 확인되었어요"],
                    },
                    {
                        "task_id": "task-2",
                        "source_node": "N2",
                        "name": "관련 지식 확인",
                        "execution_mode": "copilot",
                        "exit_criteria": ["관련 지식과 근거가 정리되었어요"],
                    },
                ],
                "workflow_edges": [{"source": "N1", "target": "N2"}],
                "candidate_links": {},
            },
        }

    v2_service.domain_services = DomainServiceGateway(
        {"mermaid.workflow_draft.create": split_handler}
    )
    first = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 근거 검색 흐름을 머메이드 차트로 그려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )
    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 흐름을 Task로 나눠줘.",
            page_ref="/docs/boi%3Apublic%3Aguide",
            work_session_id=first.work_session_id,
        ),
    )

    assert domain_calls and domain_calls[0]["source_artifact_id"] == first.artifact_refs[0].artifact_id
    assert second.work_intent is not None
    assert second.work_intent.artifact_actions == []
    assert second.plan_ref == ""
    assert [item.artifact_type for item in second.artifact_refs] == ["workflow_draft"]
    artifact = v2_service.get_artifact(principal, second.artifact_refs[0].artifact_id)
    assert artifact["capability_id"] == "workflow.transform"
    assert len(artifact["draft"]["tasks"]) == 2
    assert artifact["domain"]["domain_kind"] == "mermaid_workflow_draft"
    assert "SOP 초안을 만들" in second.answer.markdown
    assert not v2_service.store.list("plans", employee_id=principal.employee_id, limit=100)


def test_grounded_mermaid_uses_the_deterministic_graph_compiler_without_an_extra_model_call(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingScopedMermaidModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 근거 검색 흐름을 머메이드 차트로 그려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    assert model.graph_calls == 0
    assert artifact["artifact_type"] == "mermaid_diagram"
    assert artifact["draft"]["presentation"] == "mermaid"
    assert len(artifact["draft"]["nodes"]) <= 10
    assert len(artifact["draft"]["edges"]) <= 14
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["nodes"])
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["edges"])
    assert artifact["actions"] == []
    assert response.grounding_status == "grounded"
    assert response.grounded_claims


def test_grounded_mermaid_ignores_untrusted_model_graph_shapes(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = AlwaysOutOfScopeMermaidModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 근거 검색 관계만 머메이드 차트로 그려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)

    assert response.status == "completed"
    assert model.graph_calls == 0
    assert artifact["artifact_type"] == "mermaid_diagram"
    assert artifact["draft"]["presentation"] == "mermaid"
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["nodes"])
    assert all((item.get("payload") or {}).get("source_refs") for item in artifact["draft"]["edges"])


def test_grounded_mermaid_uses_catalog_titles_instead_of_model_schema_labels(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingReadableMermaidModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 근거 검색 흐름을 머메이드 차트로 그려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    visible_titles = [str((item.get("payload") or {}).get("title") or "") for item in artifact["draft"]["nodes"]]
    assert model.graph_calls == 0
    assert artifact["draft"]["presentation"] == "mermaid"
    assert all(title and title != str(item.get("node_id") or "") for title, item in zip(visible_titles, artifact["draft"]["nodes"]))


def test_mermaid_uses_sideways_layout_for_a_wide_fan_out(
    v2_service: AgentV2Service,
):
    citation = CitationRef(citation_id="cite-layout", source_ref="boi:public:guide", title="가이드")
    graph = v2_service._normalise_mermaid_graph(
        {
            "title": "업무 관계",
            "nodes": [
                {"node_id": "root", "label": "기준", "asset_kind": "knowledge", "source_numbers": [1]},
                *[
                    {"node_id": f"child-{index}", "label": f"관계 {index}", "asset_kind": "knowledge", "source_numbers": [1]}
                    for index in range(1, 5)
                ],
            ],
            "edges": [
                {"from": "root", "to": f"child-{index}", "label": "이어짐", "source_numbers": [1]}
                for index in range(1, 5)
            ],
        },
        [citation],
        focal_refs=["boi:public:guide"],
        allowed_asset_kinds={"knowledge"},
    )

    assert graph["mermaid"].startswith("flowchart LR")
    assert "<br/>" not in graph["mermaid"]


def test_starter_selection_uses_the_server_grounded_prompt_and_context(
    v2_service: AgentV2Service,
    principal: Principal,
):
    starter = next(
        item
        for item in v2_service.starter_suggestions(
            principal,
            page_ref="/docs/boi%3Apublic%3Aguide",
            limit=8,
        )
        if item.category == "knowledge_relation"
    )

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="클라이언트에서 바뀐 문장",
            suggestion_id=starter.suggestion_id,
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    timeline = v2_service.session_timeline(principal, response.work_session_id)["items"]
    assert timeline[-2]["display_text"] == starter.prompt
    assert response.work_intent is not None
    assert starter.subject_ref in response.work_intent.context_refs
    assert response.context_usage["timings_ms"]["total"] >= 0
    assert response.context_usage["timings_ms"]["a2ui"] >= 0
    stored_run = v2_service.store.get("runs", response.run_id)
    assert stored_run and stored_run["timings_ms"] == response.context_usage["timings_ms"]


def test_retrieval_query_keeps_the_title_of_each_planner_selected_context(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GenericRetrievalQueryModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="현재 문서의 구조와 관계를 설명해줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert response.work_intent is not None
    assert response.work_intent.context_refs == ["boi:public:guide"]
    assert response.work_intent.retrieval_query == "구조와 관계 설명"


def test_contextual_starters_are_grounded_in_real_accessible_subjects(
    v2_service: AgentV2Service,
    principal: Principal,
):
    starters = v2_service.starter_suggestions(
        principal,
        page_ref="/docs/boi%3Apublic%3Aguide",
        limit=8,
    )

    assert 1 <= len(starters) <= 8
    assert starters[0].category == "current_work"
    assert starters[0].label == "내 역할과 지금 맡은 일을 한눈에 보기"
    assert starters[0].result_kind == "table"
    assert starters[0].graph_query_kind == "responsibility"
    assert all(
        item.result_kind
        in {"answer", "table", "timeline", "mermaid", "explorer", "work_form", "confirmation"}
        for item in starters
    )
    similar_case = next(item for item in starters if item.category == "similar_case")
    assert similar_case.result_kind == "table"
    assert similar_case.graph_query_kind == ""
    assert all(item.subject_ref and item.source_refs for item in starters)
    assert all(
        item.subject_ref in item.source_refs or item.subject_ref.startswith("person:")
        for item in starters
    )
    assert all(item.suggestion_id.startswith("suggestion_") for item in starters)
    assert not {item.category for item in starters}.intersection({"sop_task", "business_event", "action"})


def test_dynamic_starter_falls_back_when_graph_is_not_meaningful(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        v2_service.knowledge,
        "query",
        lambda *_args, **_kwargs: {
            "ok": False,
            "meaningful": False,
            "nodes": [{"node_id": "boi:public:guide"}],
            "edges": [{"source_id": "boi:public:guide", "target_id": "boi:public:guide"}],
        },
    )

    starters = v2_service.starter_suggestions(
        principal,
        page_ref="/docs/boi%3Apublic%3Aguide",
        limit=18,
    )
    relationship_starters = [
        item
        for item in starters
        if item.subject_ref == "boi:public:guide" and item.area == "knowledge"
    ]

    assert relationship_starters
    assert all(item.result_kind == "answer" for item in relationship_starters)
    assert all(item.graph_query_kind == "" for item in relationship_starters)


def test_catalog_keeps_distinct_explorer_table_and_timeline_starters_with_recent_artifact(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])
    _write_markdown(
        v2_service.settings.content_root / "public" / "learning-loop.md",
        {
            "type": "boi/manual",
            "title": "업무 결과 재사용 가이드",
            "boi_id": "boi:public:learning-loop",
            "visibility": "public",
            "status": "reviewed",
            "agent_entrypoint_areas": ["learning"],
        },
        "검증된 업무 결과와 근거를 다음 업무 맥락에 재사용합니다.",
    )
    v2_service.repository.invalidate_source_cache()
    monkeypatch.setattr(
        v2_service.knowledge,
        "query",
        lambda *_args, **_kwargs: {
            "ok": True,
            "meaningful": True,
            "nodes": [
                {"node_id": "boi:public:guide"},
                {"node_id": "boi:public:related"},
            ],
            "edges": [
                {
                    "source_id": "boi:public:guide",
                    "target_id": "boi:public:related",
                    "relation": "guides",
                }
            ],
        },
    )
    v2_service.store.put(
        "artifacts",
        "artifact_recent_starter",
        {
            "artifact_id": "artifact_recent_starter",
            "employee_id": principal.employee_id,
            "artifact_type": "knowledge_candidate",
            "title": "최근 검토 결과",
        },
    )
    v2_service.store.put(
        "work_sessions",
        "session_recent_starter",
        {
            "session_id": "session_recent_starter",
            "employee_id": principal.employee_id,
            "active_artifact_id": "artifact_recent_starter",
        },
    )

    starters = v2_service.starter_suggestions(
        principal,
        page_ref="/docs/boi%3Apublic%3Aguide",
        limit=18,
    )
    offered_result_kinds = {item.result_kind for item in starters}

    assert {"explorer", "table", "timeline"}.issubset(offered_result_kinds)
    assert any(item.area == "learning" and item.result_kind == "work_form" for item in starters)
    assert any(item.area == "learning" and item.result_kind == "timeline" for item in starters)


def test_runtime_work_is_compiled_into_person_responsibility_graph(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    result = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["person:100001"],
            query_kind="responsibility",
            depth=2,
            presentation="table",
        ),
    )

    assert any(item["node_id"] == "person:100001" for item in result["nodes"])
    assert any(item["relation"] == "assigned_to" for item in result["edges"])
    assert any((item.get("payload") or {}).get("title") == "현재 근거 검토" for item in result["nodes"])


def test_entity_resolver_handles_people_teams_assets_and_only_asks_for_real_ambiguity(
    v2_service: AgentV2Service,
    principal: Principal,
):
    colleague_a = Principal(
        employee_id="100002", display_name="동일 이름", teams=["aix-tf"],
        roles=["boi.viewer"], auth_source="test",
    )
    colleague_b = Principal(
        employee_id="100003", display_name="동일 이름", teams=["aix-tf"],
        roles=["boi.viewer"], auth_source="test",
    )
    outsider = Principal(
        employee_id="200001", display_name="다른 조직 사용자", teams=["other-team"],
        roles=["boi.viewer"], auth_source="test",
    )
    resolver = EntityResolver(lambda: [principal, colleague_a, colleague_b, outsider])
    records = v2_service.repository.authoritative_records(principal)

    assert resolver.resolve_one("100002", principal=principal, records=records) == "person:100002"
    assert resolver.resolve_one("aix-tf", principal=principal, records=records) == "team:aix-tf"
    assert resolver.resolve_one("다른 조직 사용자", principal=principal, records=records) == ""
    assert resolver.resolve_one("BoI Wiki 운영 가이드", principal=principal, records=records) == "boi:public:guide"
    with pytest.raises(AmbiguousEntityError) as exc:
        resolver.resolve_one("동일 이름", principal=principal, records=records)
    assert {item.entity_id for item in exc.value.candidates} == {"person:100002", "person:100003"}


def test_directory_graph_keeps_shared_team_people_and_hides_other_teams(
    v2_service: AgentV2Service,
    principal: Principal,
):
    colleague = Principal(
        employee_id="100002", display_name="같은 팀 구성원", teams=["aix-tf"],
        roles=["boi.viewer"], auth_source="test",
    )
    outsider = Principal(
        employee_id="200001", display_name="다른 팀 구성원", teams=["other-team"],
        roles=["boi.viewer"], auth_source="test",
    )
    v2_service.knowledge.directory_provider = lambda: [principal, colleague, outsider]

    manifest = v2_service.knowledge.compile_graph(principal)
    shared = v2_service.store.ontology_neighbors(
        ["person:100002"], depth=1, limit=20,
        employee_id=principal.employee_id, team_ids=principal.teams,
    )
    hidden = v2_service.store.ontology_neighbors(
        ["person:200001"], depth=1, limit=20,
        employee_id=principal.employee_id, team_ids=principal.teams,
    )

    assert manifest["directory_signature"]
    assert any(item["node_id"] == "person:100002" for item in shared["nodes"])
    assert not any(item["node_id"] == "person:200001" for item in hidden["nodes"])


def test_directory_signature_uses_authoritative_identity_not_request_roles(
    v2_service: AgentV2Service,
    principal: Principal,
):
    directory_identity = principal.model_copy(
        update={"roles": ["boi.viewer"], "auth_source": "directory"}
    )
    request_identity = principal.model_copy(
        update={"roles": ["boi.viewer", "boi.admin"], "auth_source": "acceptance_fixture"}
    )
    v2_service.knowledge.directory_provider = lambda: [directory_identity]

    assert v2_service.knowledge.directory_signature(request_identity) == (
        v2_service.knowledge.directory_signature(directory_identity)
    )
    resolved = v2_service.knowledge.directory_principals(request_identity)
    assert len([item for item in resolved if item.employee_id == principal.employee_id]) == 1
    assert next(item for item in resolved if item.employee_id == principal.employee_id).roles == ["boi.viewer"]


def test_agent_returns_one_clarification_when_graph_entity_name_is_ambiguous(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    people = [
        Principal(
            employee_id=employee_id, display_name="동일 이름", teams=["aix-tf"],
            roles=["boi.viewer"], auth_source="test",
        )
        for employee_id in ("100002", "100003")
    ]
    v2_service.entity_resolver = EntityResolver(lambda: [principal, *people])
    v2_service.model = ScriptedPlanner(
        clarifications=["어느 동일 이름 구성원의 업무 관계를 확인할까요?"]
    )
    semantic_plan = SemanticPlan(
        resolved_goal="동일 이름의 검증된 업무 관계를 조회한다",
        retrieval_query="동일 이름 업무 관계",
        subjects=[SemanticSubject(mention="동일 이름", resolution="unresolved")],
        capability_id="knowledge.search",
        user_effect="read",
        operation="understand",
        evidence_scope="operational",
        presentation="table",
        work_view="responsibility",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="responsibility",
            focal_mentions=["동일 이름"],
            presentation="table",
        ),
        answer_intent="relationship",
        confidence=0.95,
    )
    route = {
        "capability_id": "knowledge.search",
        "source": "llm_structured",
        "reason": "업무 관계 조회",
        "semantic_plan": semantic_plan.model_dump(mode="json"),
        "work_intent": WorkIntent(
            goal="동일 이름의 업무 관계를 보여줘",
            resolved_goal="동일 이름의 검증된 업무 관계를 조회한다",
            asset_kind=WorkAssetKind.runtime,
            operation=WorkOperation.understand,
            operation_plan=[WorkOperation.understand],
            result_purpose="explain",
            work_view="responsibility",
            graph_query_draft=GraphQueryDraft(
                enabled=True,
                query_kind="responsibility",
                focal_mentions=["동일 이름"],
                presentation="table",
            ),
            confidence=0.95,
        ).model_dump(mode="json"),
    }
    monkeypatch.setattr(v2_service, "_semantic_route", lambda *_args, **_kwargs: route)

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="동일 이름의 업무 관계를 보여줘"),
    )

    assert response.status == "needs_input"
    assert response.work_intent and response.work_intent.needs_clarification is True
    assert response.answer.markdown.count("?") == 1
    assert "어느 동일 이름 구성원의 업무 관계를 확인할까요?" in response.answer.markdown
    assert "100002" in response.answer.markdown and "100003" in response.answer.markdown


def test_contextual_starters_offer_asset_kinds_only_for_direct_ontology_neighbors(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.store.replace_ontology(
        [
            {
                "node_id": "boi:public:guide",
                "node_type": "document",
                "payload": {"visibility": "public", "title": "BoI Wiki 운영 가이드"},
            },
            {
                "node_id": "boi:public:sop:manual",
                "node_type": "sop",
                "payload": {"visibility": "public", "title": "사람 검토 SOP"},
            },
        ],
        [
            {
                "edge_id": "guide-sop",
                "source_id": "boi:public:guide",
                "target_id": "boi:public:sop:manual",
                "relation": "uses_sop",
                "payload": {},
            }
        ],
    )

    starters = v2_service.starter_suggestions(
        principal,
        page_ref="/docs/boi%3Apublic%3Aguide",
        limit=8,
    )
    sop_starter = next(item for item in starters if item.category == "sop_task")

    assert sop_starter.subject_ref == "boi:public:sop:manual"
    assert sop_starter.source_refs == ["boi:public:sop:manual", "boi:public:guide"]
    assert "BoI Wiki 운영 가이드" in sop_starter.label
    assert not {item.category for item in starters}.intersection({"business_event", "action"})


def test_contextual_starters_do_not_invent_my_work_when_inbox_is_empty(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])
    starters = v2_service.starter_suggestions(principal, page_ref="/", limit=8)

    assert starters
    assert all(item.category != "current_work" for item in starters)
    assert all("내 업무" not in item.label and "내 업무" not in item.prompt for item in starters)
    assert all(item.source_refs for item in starters)


def test_catalog_only_capability_can_add_a_grounded_starter_offer(
    v2_service: AgentV2Service,
    principal: Principal,
    tmp_path: Path,
):
    source_catalog = yaml.safe_load(
        (ROOT / "data" / "agent_catalog" / "capabilities-v2.yaml").read_text(encoding="utf-8")
    )
    template = next(item for item in source_catalog["capabilities"] if item["handler"] == "grounded_read")
    capability = {
        **template,
        "capability_id": "test.catalog-starter",
        "title": "Catalog Starter",
        "description": "서비스 분기 없이 추가되는 테스트 capability",
        "examples": [],
        "starter_offers": [
            {
                "offer_id": "test.catalog-starter.entrypoint",
                "category": "knowledge_relation",
                "area": "knowledge",
                "selector": "canonical_entrypoint",
                "entrypoint_area": "knowledge",
                "only_when_category_empty": False,
                "label_template": "{subject_title}에서 Catalog 기능 시작하기",
                "prompt_template": "{subject_title}을 근거로 Catalog 기능을 실행해줘.",
                "reason_template": "Catalog 선언으로 제공됩니다.",
                "priority": 0,
                "result_kind": "answer",
            }
        ],
    }
    source_catalog["capabilities"] = [*source_catalog["capabilities"], capability]
    catalog_path = tmp_path / "catalog-only" / "capabilities-v2.yaml"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        yaml.safe_dump(source_catalog, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (catalog_path.parent / "draft-contracts-v2.yaml").write_text(
        (ROOT / "data" / "agent_catalog" / "draft-contracts-v2.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    v2_service.registry = CapabilityRegistry(catalog_path)

    starter = next(
        item
        for item in v2_service.starter_suggestions(principal, page_ref="/", limit=18)
        if item.capability_id == "test.catalog-starter"
    )

    assert starter.subject_ref == "boi:public:guide"
    assert starter.label == "BoI Wiki 운영 가이드에서 Catalog 기능 시작하기"
    assert starter.prompt == "BoI Wiki 운영 가이드을 근거로 Catalog 기능을 실행해줘."


def test_starter_refinement_can_rank_but_cannot_rewrite_catalog_semantics(
    v2_service: AgentV2Service,
    principal: Principal,
):
    source = [
        item.model_dump(mode="json")
        for item in v2_service.starter_suggestions(
            principal,
            page_ref="/docs/boi%3Apublic%3Aguide",
            limit=2,
        )
    ]
    set_id = "starterset_rank_only"
    v2_service.store.put(
        "starter_suggestion_sets",
        set_id,
        {
            "set_id": set_id,
            "employee_id": principal.employee_id,
            "state": "updating",
            "items": source,
        },
    )

    class RewritingRanker(ScriptedPlanner):
        def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            return {
                "items": [
                    {
                        "suggestion_id": item["suggestion_id"],
                        "label": "모델이 바꾼 제목",
                        "prompt": "모델이 바꾼 의미",
                        "capability_id": "unknown.rewrite",
                    }
                    for item in reversed(source)
                ]
            }

    v2_service.model = RewritingRanker()
    v2_service._refine_starter_suggestion_set(set_id, principal, source)

    stored = v2_service.store.get("starter_suggestion_sets", set_id)
    assert stored is not None
    assert [item["suggestion_id"] for item in stored["items"]] == [
        item["suggestion_id"] for item in reversed(source)
    ]
    originals = {item["suggestion_id"]: item for item in source}
    for item in stored["items"]:
        original = originals[item["suggestion_id"]]
        assert item["label"] == original["label"]
        assert item["prompt"] == original["prompt"]
        assert item["capability_id"] == original["capability_id"]


def test_automatic_check_is_previewed_then_created_only_after_confirmation(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = AutomaticCheckModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 운영 기준이 바뀌는지 매일 오전 9시에 다시 확인해줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert response.capability_id == "work_routine.plan"
    assert response.plan_ref.startswith("plan_")
    assert response.artifact_refs[0].artifact_type == "work_routine_draft"
    surface = v2_service.store.get("a2ui_surfaces", response.a2ui_surface_ref)
    assert surface is not None
    assert any(item["component"] == "Confirmation" for item in surface["components"])
    assert not any(item.artifact_type == "ontology_graph" for item in response.artifact_refs)
    assert v2_service.list_work_routines(principal, surface="pet", status="actionable")["count"] == 0
    assert response.next_actions[0].action_kind == "confirm_plan"

    confirmed = asyncio.run(v2_service.confirm_plan(principal, response.plan_ref, "표시된 일정을 확인함"))
    replayed = asyncio.run(v2_service.confirm_plan(principal, response.plan_ref, "표시된 일정을 확인함"))

    assert confirmed["production_changed"] is True
    assert replayed["replayed"] is True
    assert replayed["domain_result"] == confirmed["domain_result"]
    assert confirmed["domain_result"]["routine_id"].startswith("routine_")
    visible = v2_service.list_work_routines(principal, surface="pet", status="actionable")
    assert visible["count"] == 1
    assert visible["items"][0]["cron"] == "0 9 * * *"
    assert visible["items"][0]["origin"] == "user"
    assert visible["items"][0]["surface_visibility"] == "normal"


def test_grounded_confirmation_starter_routes_to_a_preview_without_mutation(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = AutomaticCheckModel()
    v2_service.model = model
    v2_service.search.model = model
    starter = next(
        item
        for item in v2_service.starter_suggestions(
            principal,
            page_ref="/docs/boi%3Apublic%3Aguide",
            limit=8,
        )
        if item.result_kind == "confirmation"
    )

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="클라이언트가 바꾼 문장",
            suggestion_id=starter.suggestion_id,
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert response.capability_id == "work_routine.plan"
    assert response.plan_ref.startswith("plan_")
    assert response.work_intent is not None
    assert starter.subject_ref in response.work_intent.context_refs
    assert response.artifact_refs[0].artifact_type == "work_routine_draft"
    surface = v2_service.store.get("a2ui_surfaces", response.a2ui_surface_ref)
    assert surface is not None
    assert any(item["component"] == "Confirmation" for item in surface["components"])
    assert v2_service.list_work_routines(principal, surface="pet", status="actionable")["count"] == 0


def test_work_routine_calendar_is_compiled_without_trusting_model_cron():
    assert AgentV2Service._compile_calendar_cron(
        {
            "minutes": [30],
            "hours": [8, 17],
            "days_of_month": [],
            "months": [],
            "weekdays": [1, 3, 5],
        }
    ) == "30 8,17 * * 1,3,5"

    with pytest.raises(RuntimeError, match="시각"):
        AgentV2Service._compile_calendar_cron(
            {
                "minutes": [],
                "hours": [],
                "days_of_month": [],
                "months": [],
                "weekdays": [],
            }
        )


def test_work_routine_stop_discards_inconsistent_optional_model_policy():
    missing_count = {"trigger": "schedule", "routine_stop": "max_runs", "max_runs": 0}
    AgentV2Service._normalise_routine_stop(missing_count)
    assert missing_count == {"trigger": "schedule", "routine_stop": "cancelled", "max_runs": 0}

    mismatched_event = {"trigger": "schedule", "routine_stop": "event_resolved", "max_runs": 0}
    AgentV2Service._normalise_routine_stop(mismatched_event)
    assert mismatched_event["routine_stop"] == "cancelled"

    valid_count = {"trigger": "schedule", "routine_stop": "max_runs", "max_runs": 3}
    AgentV2Service._normalise_routine_stop(valid_count)
    assert valid_count["routine_stop"] == "max_runs"


def test_pet_routine_filter_excludes_diagnostics_and_terminal_history(
    v2_service: AgentV2Service,
    principal: Principal,
):
    visible = v2_service.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="운영 기준 확인",
            goal="운영 기준 변경을 확인합니다.",
            trigger="interval",
            interval_seconds=3600,
        ),
    )
    v2_service.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="검증용 자동 확인",
            goal="테스트 상태를 확인합니다.",
            trigger="interval",
            interval_seconds=3600,
            origin="verification",
            surface_visibility="diagnostic",
        ),
    )
    terminal = v2_service.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="끝난 확인",
            goal="한 번 확인합니다.",
            trigger="interval",
            interval_seconds=3600,
        ),
    )
    terminal["status"] = "completed"
    v2_service.store.put("work_routines", terminal["routine_id"], terminal)

    actionable = v2_service.list_work_routines(principal, surface="pet", status="actionable")

    assert [item["routine_id"] for item in actionable["items"]] == [visible["routine_id"]]


def test_work_routine_creation_is_idempotent_for_the_same_confirmed_effect(
    v2_service: AgentV2Service,
    principal: Principal,
):
    request = WorkRoutineCreateRequest(
        title="동일 계획 자동 확인",
        goal="같은 확인 계획을 한 번만 활성화합니다.",
        trigger="interval",
        interval_seconds=3600,
        idempotency_key="plan:stable-confirmation",
    )

    first = v2_service.create_work_routine(principal, request)
    second = v2_service.create_work_routine(principal, request)

    assert first["routine_id"] == second["routine_id"]
    assert first["idempotency_key"] == "plan:stable-confirmation"
    matches = [
        item
        for item in v2_service.store.list("work_routines", employee_id=principal.employee_id, limit=100)
        if item.get("idempotency_key") == "plan:stable-confirmation"
    ]
    assert len(matches) == 1


def test_work_run_requires_human_completion_and_reuses_the_result_as_private_knowledge(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.model = ScriptedPlanner([_task_completion_plan("review-task")])
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="사람 검토 Task를 완료하고 결과를 지식으로 남겨줘",
            task_ref="review-task",
        ),
    )
    work_run = v2_service.learning.get_run(principal, response.work_run_id)

    assert response.capability_id == "task.work"
    assert response.status == "needs_input"
    assert "완료 확인" in response.answer.summary
    assert response.work_intent is not None
    assert [item.value for item in response.work_intent.operation_plan] == [
        "understand",
        "validate",
        "complete",
        "capture",
    ]
    goal_plan = v2_service.get_goal_plan(principal, response.goal_plan_ref)
    assert goal_plan["operation_plan"] == ["understand", "validate", "complete", "capture"]
    assert [item["step_id"] for item in goal_plan["steps"]] == [
        "understand_1",
        "validate_2",
        "complete_3",
        "capture_4",
    ]
    assert work_run["status"] == "waiting_human"
    assert work_run["decision"] == "needs_human"
    assert any(item["harness_id"] == "task.runtime" for item in work_run["harness_results"])

    continuation = v2_service.continue_work_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=work_run["revision"],
            confirmation="confirm",
            delta=LoopDelta(
                kind="human_input",
                summary="필수 근거를 확인했고 판단과 예외 사항을 검토 기록에 남겼습니다.",
                ref="boi:public:sop:manual",
                metadata={
                    "work_record": {
                        "observations": "필수 근거와 예외 사항을 확인했습니다.",
                        "judgment": "검토 기준을 충족한다고 판단했습니다.",
                        "result": "사람 검토를 완료했습니다.",
                    },
                    "completion_state": "completed",
                },
            ),
        ),
    )
    completed = continuation["work_run"]
    candidates = continuation["knowledge_candidates"]

    assert completed["status"] == "completed"
    assert completed["completion_record_id"].startswith("completion_")
    ledger = v2_service.learning.view_run(principal, response.work_run_id)["evidence_ledger"]
    assert any(item["verification"] == "confirmed" for item in ledger)
    assert len(candidates) == 1
    candidate_id = candidates[0]["candidate_id"]
    candidate = v2_service.learning.get_candidate(principal, candidate_id)
    assert candidate["status"] == "provisional"
    assert candidate["raw_transcript_stored"] is False
    reused = v2_service.search.search("예외 사항 검토 기록", principal, limit=8)
    assert candidate_id in {item.evidence_id for item in reused.items}
    timeline = v2_service.session_timeline(principal, response.work_session_id)["items"]
    assert timeline[-1]["work_run_id"] == response.work_run_id
    assert timeline[-1]["loop_state"]["status"] == "completed"


def test_natural_language_confirmation_semantically_continues_the_same_work_run(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = SemanticContinuationModel()
    v2_service.model = model
    v2_service.search.model = model
    started = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="사람 검토 Task를 완료하고 결과를 지식으로 남겨줘",
            task_ref="review-task",
        ),
    )
    waiting = v2_service.learning.get_run(principal, started.work_run_id)
    assert waiting["status"] == "waiting_human", waiting

    continued = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="필수 자료를 직접 검토했고 예외 판단과 결과를 검토 기록에 남겼습니다.",
            work_session_id=started.work_session_id,
        ),
    )

    assert continued.work_run_id == started.work_run_id
    assert continued.loop_state["status"] == "completed"
    assert continued.context_usage["semantic_continuation"] is True
    assert continued.knowledge_candidates
    assert len(v2_service.learning.list_runs(principal, limit=20)["items"]) == 1
    timeline = v2_service.session_timeline(principal, started.work_session_id)["items"]
    assert [item["role"] for item in timeline] == ["user", "assistant", "user", "assistant"]
    assert timeline[-1]["work_run_id"] == started.work_run_id
    assert timeline[-1]["loop_state"]["status"] == "completed"


def test_pet_client_never_classifies_confirmation_with_phrase_rules():
    script = (ROOT / "boi_api" / "app" / "static" / "agent_workspace_v2.js").read_text(encoding="utf-8")
    assert "confirmsWaitingWork" not in script
    assert "/work-runs/${encodeURIComponent(state.workRunId)}/continue" not in script
    assert 'fetch("/api/v2/agent/turns"' in script
    assert '"Accept": "text/event-stream"' in script
    switch_session = script[script.index("async function switchSession"):script.index("async function newSession")]
    assert "state.starterSet = null" in switch_session
    assert "state.starterSetLoading = false" in switch_session
    assert "state.starterSetPromise = null" in switch_session
    assert "state.starterSetPolls = 0" in switch_session
    render_empty = script[script.index("function renderEmpty"):script.index("function renderStarters")]
    assert "ensureStarterSet().catch" in render_empty
    new_session = script[script.index("async function newSession"):script.index("function pendingDb")]
    assert "새 작업을 준비하고 있습니다." in new_session
    assert "const previousSessionId = state.sessionId;" in new_session
    assert "state.sessionId = previousSessionId;" in new_session
    assert "await ensureStarterSet();" in new_session
    assert "if (state.starterSetPromise) return state.starterSetPromise;" in script
    assert "button.disabled = state.busy || !state.initialized;" in script
    assert "more.disabled = state.busy || !state.initialized;" in script
    assert "state.starterSetEpoch += 1;" in switch_session
    assert "epoch !== state.starterSetEpoch" in script
    assert 'root.dataset.agentReady = "true";' in script
    assert "busy || !state.initialized" in script


def test_full_learning_cycle_promotes_reindexes_and_reuses_authoritative_knowledge_in_new_session(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner(
        [
            _task_completion_plan("review-task"),
            _knowledge_read_plan("예외 사항 검토 문서 담당자 판단 기록"),
        ]
    )
    v2_service.model = model
    v2_service.search.model = model
    completed_turn = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="사람 검토 Task를 완료하고 예외 사항 판단을 지식으로 남겨줘",
            task_ref="review-task",
        ),
    )
    run = v2_service.learning.get_run(principal, completed_turn.work_run_id)
    completion = v2_service.continue_work_run(
        principal,
        completed_turn.work_run_id,
        WorkRunContinueRequest(
            expected_revision=run["revision"],
            confirmation="confirm",
                delta=LoopDelta(
                    kind="human_input",
                    summary="예외 사항은 검토 문서와 담당자 판단 기록을 함께 확인해야 한다고 확정했습니다.",
                    ref="boi:public:sop:manual",
                    metadata={
                        "work_record": {
                            "observations": "검토 문서와 담당자 판단 기록을 확인했습니다.",
                            "judgment": "두 근거를 함께 확인해야 한다고 판단했습니다.",
                            "result": "예외 사항 검토 기준을 확정했습니다.",
                        }
                    },
                ),
        ),
    )
    candidate_id = completion["knowledge_candidates"][0]["candidate_id"]
    candidate = v2_service.learning.get_candidate(principal, candidate_id)
    target_boi_id = "boi:team:aix-tf:learned:exception-review"

    def preview(_principal, payload):
        return {
            "ok": True,
            "status": "preview",
            "preview_id": "preview-learning-cycle",
            "preview_hash": payload["source_sha256"],
            "validation": {"ok": True, "errors": [], "warnings": []},
            "production_changed": False,
        }

    def publish(_principal, payload):
        path = v2_service.settings.content_root / "team" / "aix-tf" / "learned" / "exception-review.md"
        _write_markdown(
            path,
            {
                "boi_id": target_boi_id,
                "boi_type": "boi/reference",
                "title": payload["title"],
                "description": payload["description"],
                "owner": principal.employee_id,
                "visibility": "team",
                "team_id": "aix-tf",
                "classification": "internal",
                "status": "published",
                "source_refs": payload["source_refs"],
                "tags": payload["tags"],
            },
            payload["body"],
        )
        return {
            "status": "published",
            "promotion_id": "promotion-learning-cycle",
            "target_boi_id": target_boi_id,
            "target": {"metadata": {"boi_id": target_boi_id}},
            "production_changed": True,
        }

    v2_service.domain_services = DomainServiceGateway(
        {
            "knowledge.promotion.preview": preview,
            "knowledge.promotion.submit": publish,
        }
    )
    requested = v2_service.promote_knowledge_candidate(
        principal,
        candidate_id,
        KnowledgeCandidatePromoteRequest(
            expected_revision=candidate["revision"],
            target_visibility="team",
            team_id="aix-tf",
            reason="다음 검토 업무에서 같은 예외 판단 기준을 재사용하기 위해 공유합니다.",
        ),
    )
    confirmed = asyncio.run(
        v2_service.confirm_plan(
            principal,
            requested["plan_ref"],
            "근거와 재사용 범위를 확인했습니다.",
        )
    )

    promoted = v2_service.learning.get_candidate(principal, candidate_id)
    assert confirmed["production_changed"] is True
    assert confirmed["domain_result"]["index_refresh"]["status"] == "lexical_ready"
    assert promoted["status"] == "reviewed"
    assert promoted["target_asset_ref"] == target_boi_id

    reused = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="예외 사항 검토에서 어떤 자료와 판단 기록을 함께 확인해야 해?"),
    )
    assert reused.work_session_id != completed_turn.work_session_id
    assert target_boi_id in {item.evidence_id for item in reused.evidence_refs}


def test_work_loop_requires_a_strategy_change_then_stops_on_repeated_no_progress(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.model = ScriptedPlanner([_task_completion_plan("review-task")])
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="사람 검토 Task를 완료해줘", task_ref="review-task"),
    )
    work_run = v2_service.learning.get_run(principal, response.work_run_id)
    waiting, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=work_run["revision"],
            delta=LoopDelta(kind="no_progress", summary="같은 질문과 같은 결과"),
        ),
    )

    assert waiting["status"] == "waiting_human"
    assert waiting["stop_reason"] == "strategy_change_required"

    stopped, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=waiting["revision"],
            delta=LoopDelta(kind="no_progress", summary="새 근거나 결과가 여전히 없습니다."),
        ),
    )

    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "no_progress"


def test_transient_loop_failure_is_durable_retryable_and_idempotently_resumable(
    v2_service: AgentV2Service,
    principal: Principal,
):
    context = WorkContextPack(
        context_id="context-transient-retry",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="내부 운영 기준을 확인한다",
    )
    v2_service.store.put("contexts", context.context_id, context.model_dump(mode="json"))
    run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-run-transient-retry",
        session={"session_id": "session-transient-retry"},
        context=context,
        intent=WorkIntent(
            goal="내부 운영 기준을 확인한다",
            resolved_goal="내부 운영 기준을 확인한다",
            operation=WorkOperation.understand,
            harness_ids=["context.work"],
            loop_contract=_catalog_loop_contract("task.work"),
        ),
        goal_plan_id="goal-transient-retry",
        catalog_revision=v2_service.registry.version,
    )
    retryable = v2_service.learning.fail_run(
        principal,
        run["work_run_id"],
        "일시적인 내부 도구 응답 실패",
        disposition="transient_retry",
    )

    assert retryable["status"] == "in_progress"
    assert retryable["decision"] == "continue"
    assert retryable["stop_reason"] == "transient_retry"
    checkpoint_nodes = [
        v2_service.store.get("work_run_checkpoints", item)["node"]
        for item in retryable["checkpoint_ids"]
    ]
    assert checkpoint_nodes[-2:] == ["verify", "reflect"]

    request = WorkRunContinueRequest(
        expected_revision=retryable["revision"],
        idempotency_key="retry-result-once",
        delta=LoopDelta(
            kind="new_evidence",
            ref="boi:public:guide",
            summary="재시도에서 검증된 내부 근거를 확보했습니다.",
        ),
    )
    resumed, _ = v2_service.learning.continue_run(principal, run["work_run_id"], request)
    replayed, _ = v2_service.learning.continue_run(principal, run["work_run_id"], request)

    assert resumed["status"] == "in_progress"
    assert replayed["revision"] == resumed["revision"]
    assert replayed["loop"]["idempotency_keys"].count("retry-result-once") == 1


def test_policy_stop_is_terminal_and_records_a_stop_checkpoint(
    v2_service: AgentV2Service,
    principal: Principal,
):
    run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-run-policy-stop",
        session={"session_id": "session-policy-stop"},
        context=WorkContextPack(
            context_id="context-policy-stop",
            employee_id=principal.employee_id,
            capability_id="knowledge.search",
            goal="허용되지 않은 실행을 중단한다",
        ),
        intent=WorkIntent(
            goal="허용되지 않은 실행을 중단한다",
            resolved_goal="허용되지 않은 실행을 중단한다",
            operation=WorkOperation.understand,
            harness_ids=["context.work"],
        ),
        goal_plan_id="goal-policy-stop",
        catalog_revision=v2_service.registry.version,
    )
    stopped = v2_service.learning.fail_run(
        principal,
        run["work_run_id"],
        "정책상 실행할 수 없습니다.",
        disposition="policy_stop",
    )

    assert stopped["status"] == "stopped"
    assert stopped["decision"] == "stop"
    assert stopped["stop_reason"] == "policy_stop"
    last_checkpoint = v2_service.store.get(
        "work_run_checkpoints",
        stopped["checkpoint_ids"][-1],
    )
    assert last_checkpoint["node"] == "stop"


def test_work_loop_enforces_declared_tool_loop_cap(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.model = ScriptedPlanner([_task_completion_plan("review-task")])
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="사람 검토 Task를 진행해줘", task_ref="review-task"),
    )
    run = v2_service.learning.get_run(principal, response.work_run_id)
    run["loop"]["max_tool_loops"] = 1
    run["loop"]["policy"]["max_tool_loops"] = 1
    v2_service.store.put("work_runs", response.work_run_id, run)

    stopped, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=run["revision"],
            delta=LoopDelta(
                kind="action_result",
                ref="tool-result-without-exit-evidence",
                summary="도구 결과는 받았지만 완료 조건은 충족하지 못했습니다.",
                metadata={"tool_result_refs": ["tool-result-without-exit-evidence"]},
            ),
        ),
    )

    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "max_tool_loops"
    assert stopped["loop"]["tool_loop_count"] == 1
    assert stopped["exit_criteria_result"]["stop_reason"] == "max_tool_loops"


def test_work_run_records_turn_and_goal_loop_policies(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner([_task_completion_plan("review-task")])
    v2_service.model = model
    v2_service.search.model = model
    read_turn = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드를 알려줘", capability_id="knowledge.search"),
    )
    task_turn = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="사람 검토 Task를 완료해줘", task_ref="review-task"),
    )

    read_policy = v2_service.learning.get_run(principal, read_turn.work_run_id)["loop"]["policy"]
    task_policy = v2_service.learning.get_run(principal, task_turn.work_run_id)["loop"]["policy"]

    assert read_policy["kind"] == "turn"
    assert read_policy["trigger"] == "user"
    assert read_policy["task_stop"] == "agent_done"
    assert task_policy["kind"] == "goal"
    assert task_policy["task_stop"] == "exit_criteria"


def test_event_work_routine_uses_proactive_policy_and_suppresses_unchanged_trigger(
    v2_service: AgentV2Service,
    principal: Principal,
):
    routine = v2_service.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="운영 가이드 변경 확인",
            goal="BoI Wiki 운영 가이드의 변경 사항을 확인해줘",
            capability_id="knowledge.search",
            trigger="event",
            event_ref="wiki.document.changed.v1",
            routine_stop="event_resolved",
        ),
    )

    queued = v2_service.enqueue_work_routine_trigger(
        routine["routine_id"],
        WorkRoutineTriggerRequest(
            source_fingerprint="revision-42",
            event_ref="wiki.document.changed.v1",
        ),
        source_ref="business-event-definition:wiki-change",
    )
    processed = v2_service.run_due_work_routines(limit=1)
    first = processed[0]
    work_run = v2_service.learning.get_run(principal, first["work_run_id"])
    duplicate = v2_service.trigger_work_routine(
        principal,
        routine["routine_id"],
        WorkRoutineTriggerRequest(
            source_fingerprint="revision-42",
            event_ref="wiki.document.changed.v1",
        ),
    )

    assert work_run["loop"]["policy"]["kind"] == "proactive"
    assert work_run["loop"]["policy"]["trigger"] == "event"
    assert work_run["loop"]["policy"]["routine_id"] == routine["routine_id"]
    assert v2_service.store.get("routine_triggers", queued["trigger_id"])["status"] == "completed"
    assert duplicate["status"] == "skipped_no_change"
    stored = v2_service.get_work_routine(principal, routine["routine_id"])
    assert stored["run_count"] == 1
    assert stored["no_change_count"] == 1


def test_due_time_routine_stops_at_configured_max_runs(
    v2_service: AgentV2Service,
    principal: Principal,
):
    routine = v2_service.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="주기적 운영 기준 확인",
            goal="BoI Wiki 운영 가이드의 기준을 확인해줘",
            capability_id="knowledge.search",
            trigger="interval",
            interval_seconds=60,
            routine_stop="max_runs",
            max_runs=1,
        ),
    )
    routine["next_run_at"] = "2020-01-01T00:00:00+00:00"
    v2_service.store.put("work_routines", routine["routine_id"], routine)

    results = v2_service.run_due_work_routines(limit=1)

    assert len(results) == 1
    assert results[0]["status"] == "completed"
    stored = v2_service.get_work_routine(principal, routine["routine_id"])
    assert stored["status"] == "completed"
    assert stored["run_count"] == 1
    work_run = v2_service.learning.get_run(principal, results[0]["work_run_id"])
    assert work_run["loop"]["policy"]["kind"] == "time"
    assert work_run["loop"]["policy"]["trigger"] == "interval"


def test_scheduled_business_event_routine_executes_system_target_without_agent_routing(
    v2_service: AgentV2Service,
    principal: Principal,
):
    calls: list[dict] = []

    def execute_target(routine, request, identity):
        calls.append({"routine": routine, "request": request, "employee_id": identity.employee_id})
        return {
            "decision": "published",
            "reason": "예약 기준을 통과해 업무 이벤트를 발행했습니다.",
            "event": {"event_id": "evt-scheduled-001", "event_type": "inspection.requested.v1"},
        }

    v2_service.routine_target_executor = execute_target
    routine = v2_service.create_business_event_schedule_routine(
        principal,
        definition_id="bed-scheduled-inspection",
        title="주간 설비 점검",
        target_event_type="inspection.requested.v1",
        schedule_config={
            "repeat_type": "weekly",
            "time": "09:00",
            "weekdays": ["MON"],
            "timezone": "Asia/Seoul",
        },
    )
    routine["next_run_at"] = "2020-01-01T00:00:00+00:00"
    v2_service.store.put("work_routines", routine["routine_id"], routine)

    results = v2_service.run_due_work_routines(limit=1)

    assert len(results) == 1
    assert calls and calls[0]["employee_id"] == principal.employee_id
    assert calls[0]["routine"]["target_kind"] == "business_event"
    assert results[0]["target_result"]["decision"] == "published"
    work_run = v2_service.learning.get_run(principal, results[0]["work_run_id"])
    assert work_run["status"] == "completed"
    assert work_run["intent"]["asset_kind"] == "business_event"
    assert work_run["loop"]["policy"]["trigger"] == "schedule"
    assert work_run["loop"]["deltas"][-1]["ref"] == "evt-scheduled-001"


def test_once_scheduled_business_event_retries_a_transient_system_failure(
    v2_service: AgentV2Service,
    principal: Principal,
):
    attempts = 0

    def execute_target(_routine, _request, _identity):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary broker failure")
        return {
            "decision": "published",
            "reason": "재시도에서 업무 이벤트를 발행했습니다.",
            "event": {"event_id": "evt-scheduled-retry", "event_type": "inspection.requested.v1"},
        }

    v2_service.routine_target_executor = execute_target
    routine = v2_service.create_business_event_schedule_routine(
        principal,
        definition_id="bed-scheduled-retry",
        title="1회 점검",
        target_event_type="inspection.requested.v1",
        schedule_config={
            "repeat_type": "once",
            "once_at": "2099-01-01T00:00:00+09:00",
            "timezone": "Asia/Seoul",
        },
    )
    routine["next_run_at"] = "2020-01-01T00:00:00+00:00"
    v2_service.store.put("work_routines", routine["routine_id"], routine)

    assert v2_service.run_due_work_routines(limit=1) == []
    retrying = v2_service.get_work_routine(principal, routine["routine_id"])
    assert retrying["status"] == "active"
    assert retrying["failure_count"] == 1
    assert retrying["next_run_at"]
    assert retrying["run_history"][-1]["status"] == "retry_scheduled"

    retrying["next_run_at"] = "2020-01-01T00:00:00+00:00"
    v2_service.store.put("work_routines", routine["routine_id"], retrying)
    result = v2_service.run_due_work_routines(limit=1)

    assert result[0]["status"] == "completed"
    completed = v2_service.get_work_routine(principal, routine["routine_id"])
    assert completed["failure_count"] == 0
    assert completed["last_error"] == ""


def test_independent_review_uses_fresh_context_and_only_keeps_retrieved_evidence(
    v2_service: AgentV2Service,
    principal: Principal,
):
    evaluator = IndependentArtifactEvaluator(v2_service.store, ReviewerModel(), enabled=True)

    result = evaluator.evaluate(
        principal,
        artifact_kind="sop_draft",
        goal="근거 확인 SOP를 검토해줘",
        artifact={"title": "근거 확인 SOP", "tasks": [{"name": "근거 확인"}]},
        evidence=[{"evidence_id": "boi:public:guide", "title": "BoI Wiki 운영 가이드"}],
        rubric=["완료 조건과 근거가 연결되어야 한다"],
    )

    assert result["status"] == "needs_revision"
    assert result["review_context"] == "fresh"
    assert result["authoritative_for_completion"] is False
    assert result["criteria"][0]["evidence_refs"] == ["boi:public:guide"]


def test_independent_review_cannot_pass_without_a_real_evidence_reference(
    v2_service: AgentV2Service,
    principal: Principal,
):
    class PassWithoutEvidenceModel(ReviewerModel):
        def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "pass",
                "summary": "모든 기준을 충족했습니다.",
                "criteria": [
                    {"criterion": "근거 추적 가능성", "status": "pass", "evidence_refs": []},
                ],
                "findings": [],
            }

    evaluator = IndependentArtifactEvaluator(v2_service.store, PassWithoutEvidenceModel(), enabled=True)

    result = evaluator.evaluate(
        principal,
        artifact_kind="deep_work_draft",
        goal="근거 기반 초안을 검토해줘",
        artifact={"title": "초안", "body": "근거를 확인했습니다."},
        evidence=[{"evidence_id": "boi:public:guide", "title": "BoI Wiki 운영 가이드"}],
        rubric=["핵심 주장이 근거로 추적 가능해야 한다"],
        require_evidence_refs=True,
    )

    assert result["status"] == "needs_revision"
    assert result["findings"][-1]["severity"] == "blocking"
    assert result["evidence_reference_required"] is True


def test_independent_review_receives_every_selected_evidence_item_without_string_slicing(
    v2_service: AgentV2Service,
    principal: Principal,
):
    class CapturingReviewer(ReviewerModel):
        prompt = ""

        def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
            self.prompt = prompt
            return super().generate_structured(system=system, prompt=prompt, schema=schema)

    reviewer = CapturingReviewer()
    evaluator = IndependentArtifactEvaluator(v2_service.store, reviewer, enabled=True)
    evidence = [
        {
            "evidence_id": f"boi:public:evidence:{index}",
            "title": f"근거 {index}",
            "summary": ("충분한 원문 맥락 " * 120) + f"EVALUATOR_TAIL_{index}",
        }
        for index in range(20)
    ]

    evaluator.evaluate(
        principal,
        artifact_kind="sop_draft",
        goal="모든 선택 근거를 사용해 초안을 검토한다",
        artifact={"title": "검토 초안", "body": "본문"},
        evidence=evidence,
        rubric=["선택된 근거가 빠짐없이 전달되어야 한다"],
    )

    assert "boi:public:evidence:19" in reviewer.prompt
    assert "EVALUATOR_TAIL_19" in reviewer.prompt


def test_model_usage_scope_tracks_calls_and_blocks_the_next_over_budget_call():
    gateway = UsageTrackingGateway(ReviewerModel())
    token = begin_model_usage("usage-test", 10000)
    gateway.generate_structured(
        system="Review independently.",
        prompt="Review this draft.",
        schema={
            "type": "object",
            "required": ["status", "summary", "criteria", "findings"],
        },
    )
    usage = finish_model_usage(token)

    assert usage["model_calls"] == 1
    assert usage["total_tokens_estimate"] > 0
    assert usage["remaining_tokens_estimate"] < usage["token_budget"]

    tiny_token = begin_model_usage("usage-over-budget", 1)
    with pytest.raises(RuntimeError, match="token budget"):
        gateway.generate_structured(
            system="Long system instruction",
            prompt="Long request that cannot fit",
            schema={"type": "object"},
        )
    finish_model_usage(tiny_token)


def test_model_usage_scope_enforces_semantic_plan_call_and_elapsed_budgets(
    monkeypatch: pytest.MonkeyPatch,
):
    gateway = UsageTrackingGateway(ReviewerModel())
    clock = [100.0]
    monkeypatch.setattr("boi_api.app.v2.model_gateway.time.perf_counter", lambda: clock[0])
    token = begin_model_usage(
        "usage-loop-contract",
        10_000,
        max_model_calls=5,
        max_elapsed_seconds=30,
    )
    gateway.generate_structured(
        system="Plan once.",
        prompt="Create a structured plan.",
        schema={
            "type": "object",
            "required": ["status", "summary", "criteria", "findings"],
        },
    )
    update_model_usage_limits(max_model_calls=1, max_elapsed_seconds=1)
    with pytest.raises(RuntimeError, match="model call budget"):
        gateway.generate_structured(
            system="Do not exceed the contract.",
            prompt="A second model call is not allowed.",
            schema={
                "type": "object",
                "required": ["status", "summary", "criteria", "findings"],
            },
        )
    clock[0] = 102.0
    with pytest.raises(RuntimeError, match="elapsed-time budget"):
        gateway.embed(["elapsed budget also bounds model-backed retrieval"])
    usage = finish_model_usage(token)

    assert usage["max_model_calls"] == 1
    assert usage["max_elapsed_seconds"] == 1


def test_model_usage_scope_prefers_provider_actual_usage_when_available():
    gateway = UsageTrackingGateway(ActualUsageModel())
    token = begin_model_usage("actual-usage-test", 1000)
    gateway.generate_structured(
        system="Review independently.",
        prompt="Review this draft.",
        schema={"type": "object", "required": ["status", "summary", "criteria", "findings"]},
    )
    usage = finish_model_usage(token)

    assert usage["accounting"] == "actual"
    assert usage["input_tokens"] == 123
    assert usage["output_tokens"] == 45
    assert usage["total_tokens"] == 168


def test_repeated_manual_completion_becomes_a_skill_or_action_candidate(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner([_task_completion_plan("review-task") for _ in range(3)])
    v2_service.model = model
    v2_service.search.model = model
    pattern_candidate = None
    for index in range(3):
        response = v2_service.run_turn(
            principal,
            AgentTurnRequest(question="반복 Manual Task를 완료하고 결과를 남겨줘", task_ref="review-task"),
        )
        run = v2_service.learning.get_run(principal, response.work_run_id)
        continuation = v2_service.continue_work_run(
            principal,
            response.work_run_id,
            WorkRunContinueRequest(
                expected_revision=run["revision"],
                confirmation="confirm",
                    delta=LoopDelta(
                        kind="human_input",
                        summary=f"{index + 1}번째 수행 결과와 판단 근거를 확인했습니다.",
                        ref=f"boi:private:100001:manual-result-{index + 1}",
                        metadata={
                            "work_record": {
                                "observations": f"{index + 1}번째 수행 자료를 확인했습니다.",
                                "judgment": "반복 업무 기준을 충족한다고 판단했습니다.",
                                "result": f"{index + 1}번째 수행 결과를 기록했습니다.",
                            }
                        },
                    ),
            ),
        )
        for item in continuation["knowledge_candidates"]:
            row = v2_service.learning.get_candidate(principal, item["candidate_id"])
            if row.get("pattern_kind") == "repeated_manual_work":
                pattern_candidate = row

    assert pattern_candidate is not None
    assert pattern_candidate["recommended_asset_kind"] == "skill_or_action"
    assert pattern_candidate["occurrences"] == 3
    assert len(pattern_candidate["source_refs"]) == 3


def test_repeated_blocker_becomes_an_sop_or_harness_improvement_candidate(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner([_task_completion_plan("review-task") for _ in range(2)])
    v2_service.model = model
    v2_service.search.model = model
    pattern_candidate = None
    for index in range(2):
        response = v2_service.run_turn(
            principal,
            AgentTurnRequest(question="사람 검토 Task를 완료해줘", task_ref="review-task"),
        )
        run = v2_service.learning.get_run(principal, response.work_run_id)
        continuation = v2_service.continue_work_run(
            principal,
            response.work_run_id,
            WorkRunContinueRequest(
                expected_revision=run["revision"],
                delta=LoopDelta(
                    kind="blocker",
                    summary=f"{index + 1}번째 수행에서도 검토 기준 문서가 부족합니다.",
                ),
            ),
        )
        for item in continuation["knowledge_candidates"]:
            row = v2_service.learning.get_candidate(principal, item["candidate_id"])
            if row.get("pattern_kind") == "repeated_blocker":
                pattern_candidate = row

    assert pattern_candidate is not None
    assert pattern_candidate["recommended_asset_kind"] == "sop_or_harness"
    assert pattern_candidate["occurrences"] == 2
    assert pattern_candidate["source_refs"]


def test_autopilot_only_completes_from_its_bound_system_result(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ScriptedPlanner([_task_completion_plan("auto-task")])
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="자동 Task를 완료해줘", task_ref="auto-task"),
    )
    waiting = v2_service.learning.get_run(principal, response.work_run_id)
    assert waiting["status"] == "waiting_signal"

    unrelated, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=waiting["revision"],
            delta=LoopDelta(
                kind="action_result",
                summary="관련 없는 Action 실행 결과가 도착했습니다.",
                ref="action:unrelated",
            ),
        ),
    )
    assert unrelated["status"] == "waiting_signal"
    assert unrelated["stop_reason"] == "unrelated_system_result"

    completed, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=unrelated["revision"],
            delta=LoopDelta(
                kind="state_transition",
                summary="연결된 설비 Alarm 접수 결과가 확인되었습니다.",
                ref="equipment.alarm.accepted.v1",
            ),
        ),
    )
    assert completed["status"] == "completed"
    assert completed["stop_reason"] == "exit_criteria_satisfied"


def test_generic_agent_route_does_not_become_graph_context():
    record = KnowledgeRecord(
        record_id="boi:private:100001:case",
        kind="case",
        title="Agent 처리 사례",
        description="Agent가 처리한 과거 사례",
        text="agent workspace result",
        url="/docs/boi:private:100001:case",
        source="wiki",
        authority="reviewed",
        status="reviewed",
    )
    assert graph_score(record, {"단면검사"}) == 0.0
    assert context_anchor_score(record, "/agent", "") == 0.0
    assert context_anchor_score(record, record.url, "") == 0.5


def test_search_diversifies_duplicate_titles_before_filling_remaining_slots():
    def item(record_id: str, title: str, score: float):
        record = KnowledgeRecord(
            record_id=record_id,
            kind="case",
            title=title,
            description="",
            text="",
            url=f"/docs/{record_id}",
            source="wiki",
            authority="reviewed",
            status="reviewed",
        )
        return (score, record, {})

    ranked = [
        item("case:1", "같은 조치 필요", 0.9),
        item("case:2", "같은 조치 필요", 0.8),
        item("event:1", "판단 요청", 0.7),
        item("action:1", "판단 실행", 0.6),
    ]
    result = diversify_ranked(ranked, 3)
    assert [entry[1].record_id for entry in result] == ["case:1", "event:1", "action:1"]


def test_search_identity_prefers_an_exact_dictionary_term_over_a_loose_title_match():
    dictionary = KnowledgeRecord(
        record_id="boi:public:dictionary:cross-section-inspection",
        kind="dictionary",
        title="Cross-section Inspection",
        description="",
        text="",
        url="/docs/boi:public:dictionary:cross-section-inspection",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        metadata={"term": "단면검사", "aliases": ["Cross-section Inspection"]},
    )
    case = KnowledgeRecord(
        record_id="case:cross-section",
        kind="case",
        title="단면검사 필요 여부 판단 조치 필요 11건",
        description="",
        text="",
        url="/cases/cross-section",
        source="history",
        authority="reviewed",
        status="reviewed",
    )
    query_tokens = {"단면검사"}

    assert identity_score(dictionary, query_tokens) == 1.0
    assert identity_score(dictionary, query_tokens) > identity_score(case, query_tokens)


def test_search_lexical_score_treats_a_canonical_alias_as_user_facing_identity():
    canonical = KnowledgeRecord(
        record_id="boi:public:manual:overview",
        kind="manual",
        title="BoI Wiki 한눈에 보기",
        description="검토된 사용자 안내",
        text="업무 맥락과 실행 결과를 연결합니다.",
        url="/docs/boi:public:manual:overview",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        metadata={"aliases": ["BoI Agent로 무엇을 할 수 있나"]},
    )
    loose = KnowledgeRecord(
        record_id="boi:public:manual:deployment",
        kind="manual",
        title="BoI Agent 배포 안내",
        description="검토된 사용자 안내",
        text="업무 맥락과 실행 결과를 연결합니다.",
        url="/docs/boi:public:manual:deployment",
        source="wiki",
        authority="reviewed",
        status="reviewed",
    )
    query_tokens = {"boi", "agent", "무엇", "수"}

    assert lexical_score(query_tokens, canonical, query_tokens) > lexical_score(query_tokens, loose, query_tokens)


def test_search_is_acl_aware_excludes_drafts_and_stays_compact(v2_service: AgentV2Service, principal: Principal):
    result = v2_service.search.search("BoI Wiki 운영 가이드", principal, limit=8)
    ids = [item.evidence_id for item in result.items]
    assert ids[0] == "boi:public:guide"
    assert "boi:public:skill:smoke" not in ids
    assert "boi:private:100002:secret" not in ids
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드 찾아줘"))
    assert response.capability_id == "knowledge.search"
    assert response.answerability.status == "grounded"
    assert response.answer.summary.startswith("업무 지식과 실행 근거")
    assert len(json.dumps(response.model_dump(mode="json"), ensure_ascii=False).encode()) <= v2_service.settings.response_budget_bytes
    rendered_citation_ids = set(
        re.findall(r"/api/v2/citations/(cite_[A-Za-z0-9]+)", response.answer.markdown)
    )
    returned_citation_ids = {item.citation_id for item in response.citations}
    assert rendered_citation_ids == returned_citation_ids
    assert response.used_source_refs == list(
        dict.fromkeys(item.source_ref for item in response.citations if item.source_ref)
    )
    source_set = v2_service.get_source_set(principal, response.work_session_id)
    used = [item["source_ref"] for item in source_set["groups"]["used"]]
    assert used == response.used_source_refs


def test_markdown_budget_truncation_never_leaves_a_partial_link_or_code_fence():
    markdown = (
        "결론입니다.\n\n"
        + ("근거를 설명하는 문장입니다. " * 20)
        + "\n\n### 사용한 지식\n"
        + "- [첫 번째 지식](/docs/boi%3Apublic%3Afirst)\n"
        + "- [두 번째 지식](/docs/boi%3Apublic%3Asecond-and-very-long-path)\n"
        + "```json\n{\"raw\": true}\n```"
    )

    compacted = truncate_markdown(markdown, 360)

    assert compacted.endswith("…")
    assert compacted.rfind("[") <= compacted.rfind(")")
    assert compacted.count("```") % 2 == 0


def test_heading_chunks_keep_exact_source_lines_and_stable_ids():
    record = KnowledgeRecord(
        record_id="boi:public:chunk-test",
        kind="document",
        title="Chunk Test",
        description="",
        text="# 판단 기준\n" + ("Alarm 근거를 확인합니다. " * 75) + "\n## 조치\n" + ("조치 결과를 기록합니다. " * 70),
        url="/docs/boi:public:chunk-test",
        source="wiki",
        authority="reviewed",
        status="reviewed",
    )

    first = chunks_for_record(record)
    second = chunks_for_record(record)

    assert len(first) >= 2
    assert [item["chunk_id"] for item in first] == [item["chunk_id"] for item in second]
    assert all(item["record_id"] == record.record_id for item in first)
    assert all(item["start_line"] <= item["end_line"] for item in first)
    assert {item["heading"] for item in first} >= {"판단 기준", "조치"}


def test_turn_returns_verified_citations_goal_plan_and_source_set(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준을 알려줘"))

    assert response.capability_id == "knowledge.search"
    assert response.goal_plan_ref.startswith("goal_")
    assert response.source_set_ref == f"sources_{response.work_session_id}"
    assert response.grounding_status == "grounded"
    assert response.citations
    assert response.related_questions
    assert all(f"/api/v2/citations/{item.citation_id}" in response.answer.markdown for item in response.citations[:1])
    assert all(item.resolved_source is not None for item in response.citations)
    assert all(item.resolved_source.navigation_state == "navigable" for item in response.citations if item.resolved_source)
    assert all(item.resolved_source.canonical_url for item in response.citations if item.resolved_source)

    citation = v2_service.get_citation(principal, response.citations[0].citation_id)
    assert citation["source_ref"] in {item.evidence_id for item in response.evidence_refs}
    assert citation["excerpt"]
    assert citation["resolved_source"]["navigation_state"] == "navigable"
    assert citation["start_line"] <= citation["end_line"]

    goal = v2_service.get_goal_plan(principal, response.goal_plan_ref)
    assert goal["status"] == "completed"
    assert goal["route_source"] != "explicit"
    assert all(item["status"] == "completed" for item in goal["steps"])

    source_set = v2_service.get_source_set(principal, response.work_session_id)
    assert response.citations[0].source_ref in source_set["auto_selected"]
    assert source_set["groups"]["used"]


def test_unrelated_inbox_work_does_not_enable_apply_question_on_a_document_answer(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = ApplyRelatedQuestionModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 운영 가이드의 게시 기준을 알려줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert v2_service.repository.current_work(principal, limit=1)
    assert response.related_questions == []


def test_grounded_answer_model_can_only_render_server_verified_citations(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준을 알려줘"))

    assert response.answer.summary.startswith("업무 지식과 실행 근거")
    assert "업무 지식과 실행 근거를 연결합니다." in response.answer.markdown
    assert "초안은 검토 후 게시합니다." in response.answer.markdown
    assert f"/api/v2/citations/{response.citations[0].citation_id}" in response.answer.markdown
    assert "source_numbers" not in response.answer.markdown


def test_read_only_grounded_answer_reuses_the_planner_call_when_refs_are_verified(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CombinedPlannerAnswerModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준을 알려줘"),
    )

    assert model.planner_calls == 1
    assert model.answer_calls == 0
    assert response.answer.summary == "초안은 검토 후 게시합니다."
    assert response.related_questions
    assert all(item.source_refs for item in response.related_questions)
    assert f"/api/v2/citations/{response.citations[0].citation_id}" in response.answer.markdown


def test_read_only_grounded_answer_resolves_short_planner_source_keys(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CombinedPlannerAnswerModel(use_source_key=True)
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준을 알려줘"),
    )

    assert model.planner_calls == 1
    assert model.answer_calls == 0
    assert response.used_source_refs
    assert all(not item.startswith("S") for item in response.used_source_refs)
    assert response.citations[0].source_ref in response.used_source_refs


def test_read_only_table_reuses_the_grounded_planner_answer(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CombinedPlannerAnswerModel(use_source_key=True, presentation_mode="table")
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="게시 전에 확인할 근거를 표로 보여줘"),
    )

    assert model.planner_calls == 1
    assert model.answer_calls == 0
    assert response.work_intent is not None
    assert response.work_intent.presentation_mode == "table"
    assert response.used_source_refs
    assert response.graph_result_ref
    assert response.artifact_refs[0].artifact_type == "ontology_graph"
    assert response.artifact_refs[0].metadata["presentation"] == "table"
    assert "DataTable" in response.presentation_plan["components"]
    surface = v2_service.store.get("a2ui_surfaces", response.a2ui_surface_ref)
    assert surface is not None
    assert any(item["component"] == "DataTable" for item in surface["components"])


def test_read_only_table_stops_when_the_planner_omits_claim_level_support(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CombinedPlannerAnswerModel(
        presentation_mode="table",
        omit_grounded_answer=True,
    )
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="게시 전에 실제 확인할 근거를 표로 구분해줘"),
    )

    assert model.planner_calls == 1
    assert model.answer_calls == 0
    assert response.work_intent is not None
    assert response.work_intent.presentation_mode == "table"
    assert response.answer.summary == "확인된 근거가 없습니다."
    assert response.answerability.status == "insufficient"
    assert response.used_source_refs == []
    assert response.citations == []
    assert response.grounded_claims == []
    assert response.artifact_refs == []


def test_claim_selected_evidence_survives_the_bounded_context_window():
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:item:{index}",
            kind="document",
            title=f"문서 {index}",
            summary="검증된 내부 문서",
            url=f"/docs/boi:public:item:{index}",
        )
        for index in range(12)
    ]
    evidence.append(
        EvidenceRef(
            evidence_id="runtime:selected-claim-source",
            kind="runtime",
            title="선택된 운영 근거",
            summary="Planner claim이 직접 선택한 운영 근거",
            url="/api/runtime/source",
        )
    )

    bounded = AgentV2Service._prioritize_evidence(
        evidence,
        {"runtime:selected-claim-source"},
        limit=12,
    )

    assert bounded[0].evidence_id == "runtime:selected-claim-source"
    assert len(bounded) == 12


def test_planner_answer_with_an_unretrieved_ref_stops_without_a_second_model_call(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = CombinedPlannerAnswerModel(invalid_ref=True)
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준을 알려줘"),
    )

    assert model.planner_calls == 1
    assert model.answer_calls == 0
    assert response.answerability.status == "insufficient"
    assert response.grounded_claims[0].support_status == "unsupported"
    assert response.answer.summary == "확인된 근거가 없습니다."


def _install_a2ui_reliability_documents(service: AgentV2Service) -> None:
    root = service.settings.content_root
    _write_markdown(
        root / "public" / "a2ui-canonical.md",
        {
            "type": "boi/reference",
            "title": "A2UI와 BoI 동적 결과 화면",
            "description": "A2UI 내부 canonical 정의와 BoI catalog의 역할",
            "boi_id": "boi:public:boi-wiki-manual:agent:a2ui-and-dynamic-results",
            "visibility": "public",
            "status": "reviewed",
            "answer_scope": "canonical",
        },
        (
            "A2UI는 Agent가 만든 결과의 선언적인 화면 구조와 데이터를 신뢰된 client component가 "
            "렌더링하도록 전달하는 표현 계약입니다.\n\n"
            "boi-a2ui/v1은 BoI Wiki가 허용한 component와 입력 규칙을 모은 내부 catalog입니다."
        ),
    )
    _write_markdown(
        root / "team" / "validation" / "a2ui-validation.md",
        {
            "type": "boi/validation-report",
            "title": "A2UI Acceptance 결과",
            "description": "과거 검증 결과",
            "boi_id": "boi:team:platform:validation:a2ui",
            "visibility": "team",
            "team_id": "aix-tf",
            "status": "reviewed",
            "answer_scope": "validation",
        },
        "A2UI는 Acceptance 2UI 재검증 framework라는 과거 오답을 포함합니다.",
    )
    service.repository.invalidate_source_cache()


def test_default_answer_scope_excludes_validation_generated_and_navigation_sources(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)

    result = v2_service.search.search(
        "a2ui 가 뭐니",
        principal,
        limit=8,
        answer_scopes={"canonical", "operational"},
    )

    refs = [item.evidence_id for item in result.items]
    assert "boi:public:boi-wiki-manual:agent:a2ui-and-dynamic-results" in refs[:3]
    assert "boi:team:platform:validation:a2ui" not in refs
    assert all(item.metadata.get("answer_scope") in {"canonical", "operational"} for item in result.items)


def test_a2ui_definition_and_followup_use_canonical_claims_then_live_registry(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = A2UIReliabilityModel()
    v2_service.model = model
    v2_service.search.model = model

    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))
    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="실제로 사용된 부분 보여줄래",
            work_session_id=first.work_session_id,
        ),
    )

    assert first.answerability.status == "grounded"
    assert first.grounded_claims[0].claim_kind == "definition"
    assert "선언적인 화면 구조와 데이터" in first.answer.markdown
    assert "Acceptance 2UI" not in first.answer.markdown
    assert first.used_source_refs == ["boi:public:boi-wiki-manual:agent:a2ui-and-dynamic-results"]
    assert second.answerability.status == "grounded", {
        "claims": [item.model_dump(mode="json") for item in second.grounded_claims],
        "citations": [item.model_dump(mode="json") for item in second.citations],
        "evidence": [item.model_dump(mode="json") for item in second.evidence_refs],
        "intent": second.work_intent.model_dump(mode="json") if second.work_intent else {},
        "hints": model.planner_payloads[1].get("wiki_hybrid_hints"),
    }
    assert second.work_intent is not None and second.work_intent.topic_mode == "continue"
    assert "A2UI와 BoI 동적 결과 화면" in second.work_intent.resolved_goal
    assert second.used_source_refs == ["runtime:a2ui-capability-catalog"]
    assert "OntologyExplorer" in second.answer.markdown
    assert "Acceptance 2UI" not in second.answer.markdown
    assert model.planner_payloads[1]["verified_topic_state"]["claims"]


def test_followup_rejects_a_claim_when_the_model_omits_provenance(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = A2UIOmittedProvenanceModel()
    v2_service.model = model
    v2_service.search.model = model

    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))
    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="실제로 사용된 부분 보여줄래",
            work_session_id=first.work_session_id,
        ),
    )

    assert second.answerability.status == "insufficient"
    assert second.used_source_refs == []
    assert second.grounded_claims
    assert all(claim.support_status == "unsupported" for claim in second.grounded_claims)


def test_followup_rejects_a_claim_when_the_model_selects_a_mismatched_chunk(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = A2UIMismatchedChunkModel()
    v2_service.model = model
    v2_service.search.model = model

    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))
    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="실제로 사용된 부분 보여줄래",
            work_session_id=first.work_session_id,
        ),
    )

    assert second.answerability.status == "insufficient"
    assert second.used_source_refs == []
    assert second.grounded_claims
    assert all(claim.support_status == "unsupported" for claim in second.grounded_claims)


def test_session_followup_context_keeps_only_verified_claims_and_used_citations(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = A2UIReliabilityModel()
    v2_service.model = model
    v2_service.search.model = model
    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))
    session = v2_service.store.get("work_sessions", first.work_session_id)

    context = v2_service._session_context(principal, session)

    assistant = next(item for item in reversed(context["recent_messages"]) if item["role"] == "assistant")
    assert assistant["source_refs"] == first.used_source_refs
    assert assistant["grounded_claims"]
    assert all(item["support_status"] == "supported" for item in assistant["grounded_claims"])
    assert context["topic_state"]["used_source_refs"] == first.used_source_refs
    assert set(first.used_source_refs).issubset(set(context["topic_state"]["entities"]))
    assert context["topic_state"]["subjects"] == first.work_intent.topic_entities


def test_acl_verified_domain_entities_establish_a_multi_subject_topic_without_prose_claims(
    v2_service: AgentV2Service,
    principal: Principal,
):
    session = v2_service.create_work_session(
        principal,
        WorkSessionCreateRequest(title="유사 사례 비교"),
    )
    intent = WorkIntent(
        goal="두 사례를 비교한다",
        resolved_goal="검증된 두 사례를 비교한다",
        topic_mode="new",
        topic_subject="검증된 사례",
        topic_structure="multiple_focal",
        topic_entities=["첫 사례", "둘째 사례"],
        referenceable_topic_entities=["case:one", "case:two"],
        operation=WorkOperation.compare,
        user_effect="read",
    )
    response = AgentTurnResponse(
        run_id="run-domain-topic",
        turn_id="turn-domain-topic",
        conversation_id=str(session["conversation_id"]),
        work_session_id=str(session["session_id"]),
        status="completed",
        capability_id="cases.similar",
        answer=AnswerBlock(summary="비교 결과", markdown="비교 결과"),
        work_intent=intent,
        answerability=AnswerabilityReport(status="insufficient"),
        topic_state_ref="topic:domain-entities",
    )

    v2_service._finish_work_session(
        principal,
        session,
        response,
        "두 사례를 비교해줘",
    )

    stored = v2_service.store.get("work_sessions", str(session["session_id"]))
    assert stored["topic_state"]["subjects"] == ["첫 사례", "둘째 사례"]
    assert stored["topic_state"]["topic_structure"] == "multiple_focal"
    assert stored["topic_state"]["entities"] == ["case:one", "case:two"]


def test_unclaimed_entities_do_not_establish_topic_without_catalog_permission(
    v2_service: AgentV2Service,
    principal: Principal,
):
    session = v2_service.create_work_session(
        principal,
        WorkSessionCreateRequest(title="문서 후보"),
    )
    intent = WorkIntent(
        goal="후보 문서를 설명한다",
        resolved_goal="후보 문서를 설명한다",
        topic_mode="new",
        topic_subject="후보 문서",
        topic_entities=["후보 문서"],
        referenceable_topic_entities=["boi:public:unrelated"],
        operation=WorkOperation.understand,
        user_effect="read",
    )
    response = AgentTurnResponse(
        run_id="run-unclaimed-topic",
        turn_id="turn-unclaimed-topic",
        conversation_id=str(session["conversation_id"]),
        work_session_id=str(session["session_id"]),
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="근거 부족", markdown="확인된 근거가 없습니다."),
        work_intent=intent,
        answerability=AnswerabilityReport(status="insufficient"),
        topic_state_ref="topic:unclaimed-entity",
    )

    v2_service._finish_work_session(
        principal,
        session,
        response,
        "후보 문서를 설명해줘",
    )

    stored = v2_service.store.get("work_sessions", str(session["session_id"]))
    assert stored["topic_state"] == {}


def test_session_context_preserves_complete_turns_and_evidence(
    v2_service: AgentV2Service,
    principal: Principal,
):
    session = v2_service.create_work_session(
        principal,
        WorkSessionCreateRequest(title="원문 보존 대화"),
    )
    full_answer = "검증된 업무 설명\n" + ("완전한 문맥을 보존합니다. " * 700)
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:evidence:{index}",
            kind="document",
            title=f"근거 {index}",
            summary=f"근거 {index}의 전체 요약 " + ("내용 " * 80),
            url=f"/docs/boi:public:evidence:{index}",
        )
        for index in range(20)
    ]
    v2_service._append_session_message(
        principal,
        str(session["session_id"]),
        role="assistant",
        display_text=full_answer,
        evidence_refs=evidence,
        used_source_refs=[item.evidence_id for item in evidence],
    )

    context = v2_service._session_context(principal, session)

    assert context["recent_messages"][0]["text"] == full_answer
    assert context["recent_messages"][0]["source_refs"] == [
        item.evidence_id for item in evidence
    ]
    assert context["recent_source_refs"] == [item.evidence_id for item in evidence]


def test_planner_payload_uses_complete_turns_and_ranked_chunks_within_provider_capacity(
    v2_service: AgentV2Service,
):
    conversation_turns = [
        {"role": "user", "text": "이전 질문 " + ("원문 " * 900), "source_refs": []},
        {
            "role": "assistant",
            "text": "이전 답변 " + ("검증 내용 " * 900),
            "source_refs": ["boi:public:source:0"],
            "grounded_claims": [],
        },
    ]
    hints = [
        {
            "ref": f"boi:public:source:{index}",
            "title": f"정본 {index}",
            "kind": "document",
            "summary": f"정본 {index} 요약 " + ("설명 " * 100),
            "answer_scope": "canonical",
            "chunk_id": f"chunk-{index}",
            "chunk_text": f"chunk-{index} 전체 본문 " + ("근거 문장 " * 250),
        }
        for index in range(20)
    ]

    payload = v2_service.quick_agent._planner_payload(
        {
            "question": "후속 질문",
            "conversation_context": {
                "recent_messages": conversation_turns,
                "topic_state": {},
                "recent_source_refs": [],
            },
            "knowledge_hints": hints,
            "context_token_budget": 200_000,
        }
    )

    assert payload["conversation_turns"] == conversation_turns
    assert len(payload["internal_wiki_hints"]) == len(hints)
    assert payload["internal_wiki_hints"][-1]["chunk_text"] == hints[-1]["chunk_text"]


def test_planner_payload_excludes_an_oversized_turn_instead_of_truncating_it(
    v2_service: AgentV2Service,
):
    oversized_turn = {
        "role": "assistant",
        "text": "절대 일부만 전달하지 않습니다. " * 20_000,
        "source_refs": ["boi:public:prior"],
        "grounded_claims": [],
    }
    hint = {
        "ref": "boi:public:current",
        "title": "현재 질문 정본",
        "kind": "document",
        "summary": "현재 질문을 직접 설명합니다.",
        "answer_scope": "canonical",
        "chunk_id": "chunk-current",
        "chunk_text": "현재 질문을 직접 뒷받침하는 완전한 근거 문장입니다.",
    }

    payload = v2_service.quick_agent._planner_payload(
        {
            "question": "현재 질문",
            "conversation_context": {
                "recent_messages": [oversized_turn],
                "topic_state": {},
                "recent_source_refs": [],
            },
            "knowledge_hints": [hint],
            "context_token_budget": 60_000,
        }
    )

    assert payload["conversation_turns"] == []
    assert payload["internal_wiki_hints"][0]["chunk_text"] == hint["chunk_text"]


def test_claim_chunk_mismatch_is_insufficient_even_when_the_source_was_retrieved(
    v2_service: AgentV2Service,
    principal: Principal,
):
    evidence = [
        EvidenceRef(
            evidence_id="boi:public:guide",
            kind="document",
            title="운영 가이드",
            summary="초안은 검토 후 게시합니다.",
            url="/docs/boi:public:guide",
        )
    ]
    citations = [
        CitationRef(
            citation_id="cite-claim-mismatch",
            source_ref="boi:public:guide",
            chunk_id="chunk-real",
            title="운영 가이드",
            excerpt="초안은 검토 후 게시합니다.",
        )
    ]
    result = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-claim-mismatch"},
        {
            "answer_intent": "fact",
            "claims": [
                {
                    "claim_id": "claim-mismatch",
                    "text": "초안은 검토 후 게시합니다.",
                    "claim_kind": "fact",
                    "source_refs": ["boi:public:guide"],
                    "supporting_chunk_ids": ["chunk-other"],
                }
            ],
        },
        evidence,
        citations,
        include_report=True,
    )

    answer, _related, claims, report = result
    assert answer is None
    assert report.status == "insufficient"
    assert claims[0].support_status == "unsupported"


def test_server_grounding_rejects_claim_scope_that_differs_from_semantic_plan(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    record = KnowledgeRecord(
        record_id="boi:team:validation:semantic-kernel",
        kind="document",
        title="Semantic Kernel 검증 기록",
        description="검증 실행 결과입니다.",
        text="# 검증 기록\n\n이 문장은 validation 범위의 실행 결과입니다.",
        url="/docs/boi:team:validation:semantic-kernel",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        visibility="team",
        metadata={"answer_scope": "validation"},
    )
    chunk = chunks_for_record(record)[0]
    monkeypatch.setattr(
        v2_service,
        "_record_for_ref",
        lambda _principal, ref: record if ref == record.record_id else None,
    )
    intent = WorkIntent(
        goal="Semantic Kernel을 설명해줘",
        resolved_goal="Semantic Kernel의 canonical 정의를 설명한다",
        answer_source_scope="canonical",
        operation=WorkOperation.understand,
    )

    answer, _related, claims, report = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-scope-boundary"},
        {
            "answer_intent": "definition",
            "claims": [
                {
                    "claim_id": "claim-validation-only",
                    "text": "이 문장은 validation 범위의 실행 결과입니다.",
                    "claim_kind": "definition",
                    "source_scope": "validation",
                    "source_refs": [record.record_id],
                    "supporting_chunk_ids": [chunk["chunk_id"]],
                    "required_for_answer": True,
                }
            ],
        },
        [
            EvidenceRef(
                evidence_id=record.record_id,
                kind=record.kind,
                title=record.title,
                summary=record.description,
                url=record.url,
            )
        ],
        [
            CitationRef(
                citation_id="cite-scope-boundary",
                source_ref=record.record_id,
                chunk_id=str(chunk["chunk_id"]),
                title=record.title,
                excerpt=str(chunk["content"]),
            )
        ],
        include_report=True,
        intent=intent,
    )

    assert answer is None
    assert report.status == "insufficient"
    assert claims[0].support_status == "unsupported"


class ConflictingSensitiveClaimModel(ScriptedPlanner):
    provider = "lmstudio-test"

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if set(schema.get("required") or []) == {"verdicts"}:
            claim_id = json.loads(prompt)["claims"][0]["claim_id"]
            return {
                "verdicts": [
                    {"claim_id": claim_id, "support_status": "conflicting", "confidence": 0.99}
                ]
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class UnexpectedOperationalVerifierModel(ScriptedPlanner):
    provider = "lmstudio"

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if set(schema.get("required") or []) == {"verdicts"}:
            raise AssertionError("reviewed runtime claims must not invoke a second semantic verifier")
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class UnexpectedCanonicalFactVerifierModel(ScriptedPlanner):
    provider = "lmstudio-test"

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if set(schema.get("required") or []) == {"verdicts"}:
            raise AssertionError("a directly bound high-confidence fact must not invoke a second semantic verifier")
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class CountingParaphraseVerifierModel(ScriptedPlanner):
    provider = "lmstudio-test"

    def __init__(self):
        super().__init__()
        self.verdict_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if set(schema.get("required") or []) == {"verdicts"}:
            self.verdict_calls += 1
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


def test_high_confidence_canonical_fact_skips_risk_adaptive_semantic_verifier(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = UnexpectedCanonicalFactVerifierModel()
    v2_service.model = model
    canonical_record = KnowledgeRecord(
        record_id="boi:public:fact",
        kind="document",
        title="업무 사실",
        description="검토된 내부 사실",
        text="# 업무 사실\n\n현재 승인 단계는 담당자 검토입니다.",
        url="/docs/boi:public:fact",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        visibility="public",
        metadata={"answer_scope": "canonical"},
    )
    chunk = chunks_for_record(canonical_record)[0]
    monkeypatch.setattr(
        v2_service,
        "_record_for_ref",
        lambda _principal, ref: canonical_record if ref == canonical_record.record_id else None,
    )
    monkeypatch.setattr(v2_service, "_model_related_questions", lambda *_args, **_kwargs: [])
    evidence = [
        EvidenceRef(
            evidence_id=canonical_record.record_id,
            kind="document",
            title=canonical_record.title,
            summary=canonical_record.description,
            url=canonical_record.url,
        )
    ]
    citations = [
        CitationRef(
            citation_id="cite-canonical-fact",
            source_ref=canonical_record.record_id,
            chunk_id=str(chunk["chunk_id"]),
            title=canonical_record.title,
            excerpt=str(chunk["content"]),
        )
    ]

    answer, _related, claims, report = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-canonical-fact"},
        {
            "answer_intent": "fact",
            "claims": [
                {
                    "claim_id": "claim-canonical-fact",
                    "text": "현재 승인 단계는 담당자 검토입니다.",
                    "claim_kind": "fact",
                    "source_refs": [canonical_record.record_id],
                    "supporting_chunk_ids": [chunk["chunk_id"]],
                }
            ],
        },
        evidence,
        citations,
        include_report=True,
    )

    assert answer is not None
    assert report.status == "grounded"
    assert claims[0].support_status == "supported"


def test_paraphrased_fact_uses_fresh_context_support_evaluator(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = CountingParaphraseVerifierModel()
    v2_service.model = model
    canonical_record = KnowledgeRecord(
        record_id="boi:public:fact-paraphrase",
        kind="document",
        title="업무 사실",
        description="검토된 내부 사실",
        text="# 업무 사실\n\n담당자가 초안을 검토한 다음 승인 여부를 결정합니다.",
        url="/docs/boi:public:fact-paraphrase",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        visibility="public",
        metadata={"answer_scope": "canonical"},
    )
    chunk = chunks_for_record(canonical_record)[0]
    monkeypatch.setattr(
        v2_service,
        "_record_for_ref",
        lambda _principal, ref: canonical_record if ref == canonical_record.record_id else None,
    )
    monkeypatch.setattr(v2_service, "_model_related_questions", lambda *_args, **_kwargs: [])

    answer, _related, claims, report = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-paraphrase-fact"},
        {
            "answer_intent": "fact",
            "claims": [
                {
                    "claim_id": "claim-paraphrase-fact",
                    "text": "승인은 담당자의 초안 검토 뒤에 결정됩니다.",
                    "claim_kind": "fact",
                    "source_scope": "canonical",
                    "source_refs": [canonical_record.record_id],
                    "supporting_chunk_ids": [chunk["chunk_id"]],
                }
            ],
        },
        [
            EvidenceRef(
                evidence_id=canonical_record.record_id,
                kind=canonical_record.kind,
                title=canonical_record.title,
                summary=canonical_record.description,
                url=canonical_record.url,
            )
        ],
        [
            CitationRef(
                citation_id="cite-paraphrase-fact",
                source_ref=canonical_record.record_id,
                chunk_id=str(chunk["chunk_id"]),
                title=canonical_record.title,
                excerpt=str(chunk["content"]),
            )
        ],
        include_report=True,
    )

    assert model.verdict_calls == 1
    assert answer is not None
    assert report.status == "grounded"
    assert claims[0].support_status == "supported"


def test_reviewed_runtime_number_uses_exact_chunk_validation_without_second_model_call(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = UnexpectedOperationalVerifierModel()
    v2_service.model = model
    runtime_record = KnowledgeRecord(
        record_id="runtime:test-metrics",
        kind="runtime",
        title="현재 component 사용 현황",
        description="검증된 내부 runtime projection",
        text="현재 생성된 surface: 12건\n현재 등록 component Answer: 실제 surface 관측 10건",
        url="/api/v2/test-metrics",
        source="runtime",
        authority="reviewed",
        status="reviewed",
        visibility="private",
        owner=principal.employee_id,
        metadata={"answer_scope": "operational"},
    )
    chunk = chunks_for_record(runtime_record)[0]
    monkeypatch.setattr(
        v2_service,
        "_record_for_ref",
        lambda _principal, ref: runtime_record if ref == runtime_record.record_id else None,
    )
    monkeypatch.setattr(v2_service, "_model_related_questions", lambda *_args, **_kwargs: [])
    evidence = [
        EvidenceRef(
            evidence_id=runtime_record.record_id,
            kind="runtime",
            title=runtime_record.title,
            summary=runtime_record.description,
            url=runtime_record.url,
        )
    ]
    citations = [
        CitationRef(
            citation_id="cite-runtime-metrics",
            source_ref=runtime_record.record_id,
            chunk_id=str(chunk["chunk_id"]),
            title=runtime_record.title,
            excerpt=str(chunk["content"]),
        )
    ]

    answer, _related, claims, report = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-runtime-metrics"},
        {
            "answer_intent": "fact",
            "claims": [
                {
                    "claim_id": "claim-runtime-count",
                    "text": "현재 생성된 surface는 12건입니다.",
                    "claim_kind": "fact",
                    "source_scope": "operational",
                    "source_refs": [runtime_record.record_id],
                    "supporting_chunk_ids": [chunk["chunk_id"]],
                }
            ],
        },
        evidence,
        citations,
        include_report=True,
    )

    assert answer is not None
    assert report.status == "grounded"
    assert claims[0].support_status == "supported"


def test_sensitive_definition_conflict_stops_the_answer(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model = ConflictingSensitiveClaimModel()
    v2_service.model = model
    canonical_record = KnowledgeRecord(
        record_id="boi:public:a2ui",
        kind="document",
        title="A2UI 내부 정의",
        description="A2UI는 선언적 화면 표현 계약입니다.",
        text="# A2UI 내부 정의\n\nA2UI는 선언적 화면 표현 계약입니다.",
        url="/docs/boi:public:a2ui",
        source="wiki",
        authority="reviewed",
        status="reviewed",
        visibility="public",
        metadata={"answer_scope": "canonical"},
    )
    original_record_for_ref = v2_service._record_for_ref
    monkeypatch.setattr(
        v2_service,
        "_record_for_ref",
        lambda active_principal, ref: canonical_record
        if ref == canonical_record.record_id
        else original_record_for_ref(active_principal, ref),
    )
    evidence = [
        EvidenceRef(
            evidence_id="boi:public:a2ui",
            kind="document",
            title="A2UI 내부 정의",
            summary="A2UI는 선언적 화면 표현 계약입니다.",
            url="/docs/boi:public:a2ui",
        )
    ]
    citations = [
        CitationRef(
            citation_id="cite-a2ui-conflict",
            source_ref="boi:public:a2ui",
            chunk_id="chunk-a2ui",
            title="A2UI 내부 정의",
            excerpt="A2UI는 선언적 화면 표현 계약입니다.",
        )
    ]
    answer, _related, claims, report = v2_service._grounded_answer_from_plan(
        principal,
        {"session_id": "session-a2ui-conflict"},
        {
            "answer_intent": "definition",
            "claims": [
                {
                    "claim_id": "claim-a2ui",
                    "text": "A2UI는 선언적 화면 표현 계약입니다.",
                    "claim_kind": "definition",
                    "source_refs": ["boi:public:a2ui"],
                    "supporting_chunk_ids": ["chunk-a2ui"],
                }
            ],
        },
        evidence,
        citations,
        include_report=True,
    )

    assert answer is None
    assert report.status == "conflicting"
    assert report.conflicting_claim_count == 1
    assert claims[0].support_status == "conflicting"


def test_a2ui_capability_catalog_reports_live_registry_and_observed_surfaces(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    app = FastAPI()
    app.include_router(build_agent_v2_router(v2_service))

    with TestClient(app) as client:
        turn = client.post("/api/v2/agent/turns", json={"question": "BoI Wiki 운영 가이드 찾아줘"})
        assert turn.status_code == 200
        catalog = client.get("/api/v2/a2ui/catalogs/boi/v1")

    assert catalog.status_code == 200
    payload = catalog.json()
    assert payload["compatibility_id"] == "boi-a2ui/v1"
    assert payload["surface_count"] >= 1
    component_by_name = {item["name"]: item for item in payload["components"]}
    assert {"Answer", "CitationList", "OntologyExplorer", "WorkRecordForm"} <= set(component_by_name)
    assert component_by_name["Answer"]["observed_surface_count"] >= 1
    runtime_record = v2_service.search.runtime_record("runtime:a2ui-capability-catalog", principal)
    assert runtime_record is not None
    assert "현재 실제 surface 관측이 가장 많은 component: Answer" in runtime_record.text


def test_unknown_internal_concept_returns_insufficient_instead_of_model_memory(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = UnknownConceptModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="Wiki에 없는 ZQX-99 내부 약어의 뜻을 알려줘"),
    )

    assert response.answerability.status == "insufficient"
    assert response.grounded_claims == []
    assert response.answer.summary == "확인된 근거가 없습니다."
    assert "ZQX-99" not in response.answer.markdown
    session = v2_service.store.get("work_sessions", response.work_session_id)
    assert not session.get("topic_state")


def test_followup_without_prior_subject_uses_verified_topic_identity_without_a_second_model_call(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = MalformedContinuationModel()
    v2_service.model = model
    v2_service.search.model = model
    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))

    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="실제로 사용된 부분 보여줄래", work_session_id=first.work_session_id),
    )

    assert model.followup_attempts == 2
    assert second.answerability.status == "grounded"
    assert second.work_intent is not None
    assert "A2UI와 BoI 동적 결과 화면" in second.work_intent.resolved_goal
    assert "A2UI와 BoI 동적 결과 화면" in second.work_intent.retrieval_query


def test_explicit_new_topic_does_not_inherit_the_previous_subject(v2_service: AgentV2Service):
    route = v2_service.quick_agent.route(
        "새 주제로 Action dry-run과 실제 실행의 차이를 알려줘",
        page_kind="action",
        conversation_context={
            "topic_state": {
                "subject": "A2UI와 BoI 동적 결과 화면",
                "claims": [],
                "used_source_refs": ["boi:public:a2ui"],
            }
        },
        knowledge_hints=[
            {
                "ref": "boi:public:action-guide",
                "title": "Action 실행 가이드",
                "chunk_id": "chunk-action",
                "chunk_text": "Action은 dry-run 검증 후 확인을 거쳐 실제 실행합니다.",
            }
        ],
        model=ExplicitNewTopicModel(),
    )

    intent = route["work_intent"]
    assert intent["topic_mode"] == "new"
    assert intent["topic_subject"] == "Action dry-run과 실제 실행"
    assert "A2UI" not in intent["resolved_goal"]
    assert "A2UI" not in intent["retrieval_query"]


def test_conflicting_followup_invalidates_prior_topic_and_records_correction(
    v2_service: AgentV2Service,
    principal: Principal,
):
    _install_a2ui_reliability_documents(v2_service)
    model = A2UIReliabilityModel()
    v2_service.model = model
    v2_service.search.model = model
    first = v2_service.run_turn(principal, AgentTurnRequest(question="a2ui 가 뭐니"))
    session = v2_service.store.get("work_sessions", first.work_session_id)
    conflicting_claim = first.grounded_claims[0].model_copy(update={"support_status": "conflicting"})
    conflicting = first.model_copy(
        deep=True,
        update={
            "run_id": "run-conflicting-correction",
            "turn_id": "turn-conflicting-correction",
            "topic_state_ref": "topic:conflicting-correction",
            "grounded_claims": [conflicting_claim],
            "answerability": AnswerabilityReport(
                status="conflicting",
                answer_intent="definition",
                conflicting_claim_count=1,
                conflicts=[conflicting_claim.text],
            ),
        },
    )
    conflicting.work_intent = first.work_intent.model_copy(update={"topic_mode": "continue"})

    v2_service._finish_work_session(principal, session, conflicting, "방금 정의를 다시 확인해줘")

    stored = v2_service.store.get("work_sessions", first.work_session_id)
    assert stored["topic_state"]["correction_status"] == "invalidated"
    assert stored["topic_state"]["invalidated_by_run_id"] == "run-conflicting-correction"
    assert stored["topic_corrections"][-1]["reason"] == "conflicting_internal_evidence"


def test_source_set_pin_exclude_and_private_note_stay_in_one_session(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드 찾아줘"))
    source_set = v2_service.get_source_set(principal, response.work_session_id)
    source_ref = response.citations[0].source_ref

    pinned = v2_service.patch_source_set(
        principal,
        response.work_session_id,
        SourceSetPatchRequest(expected_revision=source_set["revision"], pin_refs=[source_ref]),
    )
    assert source_ref in pinned["pinned"]

    note = v2_service.create_note_from_turn(
        principal,
        NoteFromTurnRequest(run_id=response.run_id, work_session_id=response.work_session_id),
    )
    assert note["artifact"]["artifact_type"] == "knowledge_note"
    assert note["artifact"]["capability_id"] == response.capability_id
    assert note["artifact"]["status"] == "provisional"
    assert note["artifact"]["artifact_id"] in note["source_set"]["pinned"]

    latest = note["source_set"]
    excluded = v2_service.patch_source_set(
        principal,
        response.work_session_id,
        SourceSetPatchRequest(expected_revision=latest["revision"], exclude_refs=[source_ref]),
    )
    assert source_ref in excluded["excluded"]
    assert source_ref not in excluded["pinned"]


def test_source_set_preserves_every_claim_supported_used_source(
    v2_service: AgentV2Service,
    principal: Principal,
):
    session = v2_service.create_work_session(
        principal,
        WorkSessionCreateRequest(title="전체 사용 근거 보존"),
    )
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:test:used-source-{index}",
            kind="boi",
            title=f"사용 근거 {index}",
            summary=f"검증된 claim {index}을 직접 뒷받침합니다.",
        )
        for index in range(1, 21)
    ]
    refs = [item.evidence_id for item in evidence]

    v2_service._update_auto_sources(
        principal,
        session["session_id"],
        evidence,
        [],
        used_refs=refs,
    )

    source_set = v2_service.get_source_set(principal, session["session_id"])
    assert source_set["auto_selected"] == refs
    assert [item["source_ref"] for item in source_set["groups"]["used"]] == refs


def test_context_outcome_and_grounded_table_preserve_all_verified_provenance(
    v2_service: AgentV2Service,
    principal: Principal,
):
    refs = [f"boi:public:test:provenance-{index}" for index in range(1, 121)]
    context = WorkContextPack(
        context_id="context-complete-provenance",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="검증에 사용한 모든 근거를 보존한다",
        context_manifest=ContextManifest(
            selected_refs=refs,
            items=[
                ContextItemUsage(
                    item_ref=ref,
                    selected=True,
                    source_refs=[ref],
                )
                for ref in refs
            ],
        ),
    )
    run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-complete-provenance",
        session={"session_id": "session-complete-provenance"},
        context=context,
        intent=WorkIntent(
            goal=context.goal,
            resolved_goal=context.goal,
            operation=WorkOperation.understand,
            harness_ids=["context.work"],
        ),
        goal_plan_id="goal-complete-provenance",
        catalog_revision=v2_service.registry.version,
    )

    v2_service.learning._record_context_outcome(
        context=context,
        work_run=run,
        used_source_refs=refs,
        outcome="answer",
    )

    stored = WorkContextPack.model_validate(v2_service.store.get("contexts", context.context_id))
    assert stored.context_manifest is not None
    assert stored.context_manifest.used_refs == sorted(refs)
    assert all(item.used for item in stored.context_manifest.items)

    claims = [
        GroundedClaim(
            claim_id=f"claim-{index}",
            text=f"검증된 사실 {index}",
            source_refs=[ref],
            supporting_chunk_ids=[f"chunk-{index}"],
            support_status="supported",
            confidence=1.0,
        )
        for index, ref in enumerate(refs[:20], start=1)
    ]
    artifact = v2_service._grounded_claims_table_artifact(
        principal,
        session={"session_id": "session-complete-provenance"},
        claims=claims,
        work_run_id=run["work_run_id"],
        capability_id="knowledge.search",
    )

    assert artifact is not None
    stored_artifact = v2_service.store.get("artifacts", artifact.artifact_id)
    assert stored_artifact["draft"]["source_refs"] == refs[:20]
    assert len([item for item in stored_artifact["draft"]["nodes"] if item["node_kind"] == "grounded_claim"]) == 20


def test_dictionary_alias_gets_ontology_authority_in_search(v2_service: AgentV2Service, principal: Principal):
    result = v2_service.search.search("단면검사", principal, limit=3)
    assert result.items[0].evidence_id == "boi:public:dictionary:cross-section-inspection"


def test_knowledge_graph_reads_the_stored_ontology_instead_of_rebuilding_a_shallow_graph(
    v2_service: AgentV2Service,
    principal: Principal,
):
    task_id = "task:guide-review"
    v2_service.store.replace_ontology(
        [
            {
                "node_id": "boi:public:guide",
                "node_type": "document",
                "payload": {"title": "BoI Wiki 운영 가이드", "visibility": "public"},
            },
            {
                "node_id": task_id,
                "node_type": "task",
                "payload": {"title": "운영 기준 검토", "visibility": "public"},
            },
        ],
        [
            {
                "edge_id": "edge:guide-task",
                "source_id": "boi:public:guide",
                "target_id": task_id,
                "relation": "has_task",
                "payload": {},
            }
        ],
    )

    graph = v2_service.knowledge_graph(principal, query="BoI Wiki 운영 가이드")
    assert graph["mode"] == "stored_ontology"
    assert {item["id"] for item in graph["nodes"]} == {"boi:public:guide", task_id}
    assert graph["edges"][0]["relation"] == "has_task"


def test_readiness_rejects_an_old_search_index_schema(v2_service: AgentV2Service, principal: Principal):
    v2_service.store.put(
        "manifests",
        "search",
        {
            "record_count": 1,
            "source_signature": v2_service.repository.source_signature(),
            "index_schema_version": "1.0",
            "status": "ready",
        },
    )
    readiness = v2_service.readiness(principal)
    assert readiness["dependencies"]["search_index"] is False


def test_readiness_reports_generation_and_embedding_residency_independently(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    v2_service.settings = replace(v2_service.settings, lmstudio_require_preloaded_models=True)
    residency = {
        **v2_service.model_residency,
        "ready": False,
        "generation_ready": True,
        "embedding_ready": False,
        "manual_models": [v2_service.settings.model_name],
        "missing_models": [v2_service.settings.embedding_model],
    }

    def inspect_residency() -> dict[str, Any]:
        v2_service.model_residency = dict(residency)
        return dict(residency)

    monkeypatch.setattr(v2_service, "inspect_model_residency", inspect_residency)

    readiness = v2_service.readiness(principal)

    assert readiness["dependencies"]["model"] is True
    assert readiness["dependencies"]["embedding"] is False


def test_readiness_exposes_the_runtime_of_the_worker_it_actually_accepts(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.store.heartbeat(
        "deep-worker-test",
        {
            "version": "2.0",
            "deepagents": True,
            "model_adapter": True,
            "openai_adapter": True,
            "anthropic_adapter": False,
        },
    )

    readiness = v2_service.readiness(principal)

    assert readiness["dependencies"]["deep_worker"] is True
    assert readiness["worker"]["worker_id"] == "deep-worker-test"
    assert readiness["worker"]["runtime"] == {
        "version": "2.0",
        "deepagents": True,
        "model_adapter": True,
        "openai_adapter": True,
        "anthropic_adapter": False,
    }


def test_builder_lists_existing_acl_visible_skills(v2_service: AgentV2Service, principal: Principal):
    result = v2_service.list_skills(principal, query="근거")
    assert result["count"] == 1
    assert result["items"][0]["skill_id"] == "boi:public:skill:evidence-validation"


def test_conversation_id_stays_stable_across_turns(v2_service: AgentV2Service, principal: Principal):
    first = v2_service.run_turn(principal, AgentTurnRequest(question="운영 가이드 찾아줘"))
    second = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="관련 문서도 찾아줘", conversation_id=first.conversation_id),
    )
    assert first.conversation_id.startswith("ws_")
    assert first.work_session_id == first.conversation_id
    assert second.conversation_id == first.conversation_id
    timeline = v2_service.session_timeline(principal, first.work_session_id)["items"]
    assert [item["role"] for item in timeline] == ["user", "assistant", "user", "assistant"]
    context = v2_service.get_context(principal, second.context_ref)
    assert context["manifest"]["conversation"]["recent_messages"][0]["text"] == "운영 가이드 찾아줘"


def test_work_session_patch_requires_revision_and_preserves_private_state(
    v2_service: AgentV2Service,
    principal: Principal,
):
    response = v2_service.run_turn(principal, AgentTurnRequest(question="운영 가이드 찾아줘"))
    session = v2_service.get_work_session(principal, response.work_session_id)
    updated = v2_service.patch_work_session(
        principal,
        response.work_session_id,
        WorkSessionPatchRequest(expected_revision=session["revision"], pinned=True, active_panel="evidence"),
    )
    assert updated["pinned"] is True
    assert updated["active_panel"] == "evidence"
    with pytest.raises(Exception) as exc_info:
        v2_service.patch_work_session(
            principal,
            response.work_session_id,
            WorkSessionPatchRequest(expected_revision=session["revision"], title="stale"),
        )
    assert getattr(exc_info.value, "status_code", None) == 409
    deleted = v2_service.delete_work_session(principal, response.work_session_id)
    assert deleted["status"] == "deleted"
    with pytest.raises(Exception) as missing:
        v2_service.get_work_session(principal, response.work_session_id)
    assert getattr(missing.value, "status_code", None) == 404


def test_sop_artifact_merges_different_fields_and_conflicts_on_the_same_field(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 초안을 만들어줘", capability_id="sop.plan"),
    )
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    original = artifact["draft"]["tasks"][0]
    task_id = original["task_id"]

    first = v2_service.patch_sop_artifact(
        principal,
        artifact["artifact_id"],
        SopArtifactPatchRequest(
            expected_revision=1,
            task_updates=[{"task_id": task_id, "base_task": original, "task": {**original, "purpose": "검토 근거를 확정합니다."}}],
            selected_task_id=task_id,
        ),
    )
    merged = v2_service.patch_sop_artifact(
        principal,
        artifact["artifact_id"],
        SopArtifactPatchRequest(
            expected_revision=1,
            task_updates=[{"task_id": task_id, "base_task": original, "task": {**original, "exit_criteria": ["근거와 판단이 기록됨"]}}],
            selected_task_id=task_id,
        ),
    )
    task = merged["draft"]["tasks"][0]
    assert first["revision"] == 2
    assert merged["revision"] == 3
    assert task["purpose"] == "검토 근거를 확정합니다."
    assert task["exit_criteria"] == ["근거와 판단이 기록되었어요"]
    assert task["completion_design"]["checks"][0]["label"] == "근거와 판단이 기록되었어요"
    assert "근거 확인" in merged["draft"]["mermaid"]

    with pytest.raises(Exception) as exc_info:
        v2_service.patch_sop_artifact(
            principal,
            artifact["artifact_id"],
            SopArtifactPatchRequest(
                expected_revision=1,
                task_updates=[{"task_id": task_id, "base_task": original, "task": {**original, "purpose": "서로 다른 목적"}}],
            ),
        )
    assert getattr(exc_info.value, "status_code", None) == 409
    assert getattr(exc_info.value, "detail", {}).get("status") == "field_conflict"


def test_helper_definition_is_structured_and_preview_uses_a_real_work_session(
    v2_service: AgentV2Service,
    principal: Principal,
):
    helper = v2_service.create_helper_draft(principal, HelperDraftCreateRequest(template_id="search"))
    helper = v2_service.patch_helper_draft(
        principal,
        helper["draft_id"],
        HelperDraftPatchRequest(
            expected_revision=helper["revision"],
            instructions="검토된 문서 근거를 링크와 함께 보여줘.",
            source_scopes=["boi", "sop"],
            skill_ids=["boi:public:skill:evidence-validation"],
        ),
    )
    preview = v2_service.helper_preview_turn(
        principal,
        helper["draft_id"],
        HelperPreviewTurnRequest(question="BoI Wiki 운영 가이드 찾아줘"),
    )
    assert helper["instructions"].startswith("검토된 문서")
    assert helper["source_scopes"] == ["boi", "sop"]
    assert helper["skill_ids"] == ["boi:public:skill:evidence-validation"]
    assert preview.capability_id == "knowledge.search"
    assert preview.work_session_id.startswith("ws_")
    assert v2_service.session_timeline(principal, preview.work_session_id)["count"] == 2


def test_sop_helper_preview_uses_semantic_router_and_returns_editable_artifact(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model
    helper = v2_service.create_helper_draft(principal, HelperDraftCreateRequest(template_id="sop"))

    preview = v2_service.helper_preview_turn(
        principal,
        helper["draft_id"],
        HelperPreviewTurnRequest(question="근거 검토 업무를 Task 3개짜리 SOP 초안으로 만들어줘"),
    )

    assert preview.capability_id == "sop.plan"
    assert preview.work_intent.operation.value == "create"
    assert preview.artifact_refs[0].artifact_type == "sop_draft"
    assert preview.artifact_refs[0].status == "draft"


def test_skill_creator_requires_executable_test_before_private_activation_and_helper_use(
    v2_service: AgentV2Service,
    principal: Principal,
):
    created = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="업무 근거를 확인하는 Skill 초안을 만들어줘",
            capability_id="skill.plan",
        ),
    )
    artifact_id = created.artifact_refs[0].artifact_id
    artifact = v2_service.get_artifact(principal, artifact_id)
    with pytest.raises(Exception) as exc_info:
        v2_service.activate_skill_artifact(
            principal,
            artifact_id,
            SkillArtifactActivateRequest(expected_revision=artifact["revision"]),
        )
    assert getattr(exc_info.value, "status_code", None) == 422

    v2_service.model = SkillExecutionModel()
    v2_service.search.model = v2_service.model
    tested = v2_service.test_skill_artifact(
        principal,
        artifact_id,
        SkillArtifactTestRequest(
            expected_revision=artifact["revision"],
            scenario="현재 업무와 관련된 검토 근거를 찾아줘",
            expected_contains=["evidence_refs"],
        ),
    )
    assert tested["status"] == "passed"
    assert tested["harness"]["status"] == "passed"

    skill = v2_service.activate_skill_artifact(
        principal,
        artifact_id,
        SkillArtifactActivateRequest(expected_revision=artifact["revision"]),
    )
    assert skill["status"] == "active"
    assert skill["verification"]["latest_test_id"] == tested["test_id"]
    assert any(item["skill_id"] == skill["skill_id"] for item in v2_service.list_skills(principal)["items"])

    helper = v2_service.create_helper_draft(principal, HelperDraftCreateRequest(template_id="search"))
    helper = v2_service.patch_helper_draft(
        principal,
        helper["draft_id"],
        HelperDraftPatchRequest(
            expected_revision=helper["revision"],
            instructions="검증된 Skill과 Wiki 근거만 사용해 답해줘.",
            skill_ids=[skill["skill_id"]],
        ),
    )
    activated = v2_service.activate_helper(
        principal,
        helper["draft_id"],
        HelperActivateRequest(expected_revision=helper["revision"]),
    )
    assert activated["skill_ids"] == [skill["skill_id"]]


def test_legacy_helper_draft_is_lazily_imported_once(v2_service: AgentV2Service, principal: Principal):
    legacy_id = "agent-draft-legacy-test"
    path = v2_service.settings.runtime_root / "agents" / "drafts" / f"{legacy_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "draft_id": legacy_id,
                "title": "기존 설비 도우미",
                "prompt": "설비 이상 근거를 찾아줘.",
                "created_by": principal.employee_id,
                "capabilities": ["search", "diagram"],
                "reference_sources": ["boi_docs", "sops"],
                "skills": ["boi:public:skill:evidence-validation"],
                "helper_surfaces": ["agent", "task"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    first = v2_service.import_legacy_helper_draft(principal, LegacyHelperImportRequest(legacy_draft_id=legacy_id))
    second = v2_service.import_legacy_helper_draft(principal, LegacyHelperImportRequest(legacy_draft_id=legacy_id))
    assert first["draft_id"] == second["draft_id"]
    assert first["name"] == "기존 설비 도우미"
    assert first["capability_ids"] == ["knowledge.search", "sop.plan"]
    assert first["source_scopes"] == ["boi", "sop"]
    assert v2_service.delete_helper_draft(principal, first["draft_id"])["status"] == "deleted"


def test_semantic_search_passes_private_team_and_admin_acl_to_pgvector(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    class EmbeddingModel(ScriptedPlanner):
        def readiness(self) -> dict[str, Any]:
            return {**super().readiness(), "embeddings": True, "embedding_model": "test-embedding"}

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3] for _ in texts]

    def vector_search(_embedding, **kwargs):
        captured.update(kwargs)
        return []

    v2_service.search.model = EmbeddingModel()
    monkeypatch.setattr(v2_service.store, "health", lambda: {"ready": True, "mode": "postgres", "durable": True})
    monkeypatch.setattr(v2_service.store, "vector_search", vector_search)
    v2_service.search.search("Alarm", principal)

    assert captured["employee_id"] == principal.employee_id
    assert captured["team_ids"] == principal.teams
    assert captured["include_all"] is False


def test_incremental_index_replaces_stale_chunks_and_reconcile_marks_fresh(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    class EmbeddingModel(ScriptedPlanner):
        def readiness(self) -> dict[str, Any]:
            return {
                **super().readiness(),
                "embeddings": True,
                "embedding_model": "test-embedding",
                "embedding_provider": "test",
            }

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr(
        v2_service.store,
        "health",
        lambda: {
            "ready": True,
            "mode": "postgres",
            "durable": True,
            "search_documents": len(v2_service.store.list("search_documents", limit=100_000)),
            "search_chunks": len(v2_service.store.list("search_chunks", limit=100_000)),
        },
    )
    v2_service.search.model = EmbeddingModel()
    path = v2_service.settings.content_root / "public" / "incremental.md"
    metadata = {
        "type": "boi/manual",
        "title": "증분 색인 문서",
        "boi_id": "boi:public:incremental",
        "visibility": "public",
        "status": "reviewed",
    }
    _write_markdown(path, metadata, "첫 번째 내용입니다. " * 180)
    first = v2_service.search.index_records(
        principal,
        ["boi:public:incremental"],
        finalize_manifest=False,
    )
    first_chunks = {
        item["chunk_id"]
        for item in v2_service.store.list("search_chunks", limit=100_000)
        if item.get("record_id") == "boi:public:incremental"
    }

    _write_markdown(path, metadata, "완전히 바뀐 두 번째 내용입니다. " * 180)
    second = v2_service.search.index_records(
        principal,
        ["boi:public:incremental"],
        finalize_manifest=False,
    )
    second_chunks = {
        item["chunk_id"]
        for item in v2_service.store.list("search_chunks", limit=100_000)
        if item.get("record_id") == "boi:public:incremental"
    }

    assert first["status"] == second["status"] == "indexed"
    assert first_chunks
    assert second_chunks
    assert first_chunks.isdisjoint(second_chunks)
    assert v2_service.store.get("manifests", "search")["sync_state"] == "syncing"

    reconciled = v2_service.search.reconcile(principal)
    manifest = v2_service.store.get("manifests", "search")
    assert reconciled["status"] == "ready"
    assert manifest["sync_state"] == "ready"
    assert manifest["source_signature"] == v2_service.repository.source_signature()


def test_seed_history_is_similar_case_but_never_current_work(v2_service: AgentV2Service, principal: Principal):
    current = v2_service.repository.current_work(principal)
    assert [item.record_id for item in current] == ["active_action:active-work-1"]
    similar = v2_service.search.similar_cases("과거 Alarm 조치", principal)
    assert any(item.source == "history_seed" for item in similar.items)
    inbox = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="내 할 일", capability_id="work.inbox"),
    )
    assert {item.evidence_id for item in inbox.evidence_refs} == {"active_action:active-work-1"}


def test_model_dependent_capabilities_are_unavailable_without_fake_success(v2_service: AgentV2Service, principal: Principal):
    unavailable = UnavailableModelGateway("test generation unavailable")
    v2_service.model = unavailable
    v2_service.search.model = unavailable
    with pytest.raises(Exception) as exc_info:
        v2_service.run_turn(
            principal,
            AgentTurnRequest(question="업무 도우미를 만들어줘", capability_id="skill.plan"),
        )
    assert getattr(exc_info.value, "status_code", None) == 503
    assert "capability_unavailable" in str(getattr(exc_info.value, "detail", ""))


def test_skill_plan_creates_private_draft_only(v2_service: AgentV2Service, principal: Principal):
    fake = ScriptedPlanner()
    v2_service.model = fake
    v2_service.search.model = fake
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거와 종료 기준을 찾는 업무 도우미를 만들어줘", capability_id="skill.plan"),
    )
    assert response.status == "completed"
    assert response.artifact_refs[0].status == "draft"
    plan = v2_service.store.get("plans", response.plan_ref)
    assert plan and plan["status"] == "draft"
    assert "게시" not in response.answer.summary or "게시하거나 실행하지 않았습니다" in response.answer.summary


def test_sop_draft_uses_one_model_repair_and_requires_task_exit_criteria(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 초안을 만들어줘", capability_id="sop.plan"),
    )
    artifact = v2_service.store.get("artifacts", response.artifact_refs[0].artifact_id)

    assert model.calls == 2
    assert artifact["generation_attempts"] == 2
    assert artifact["draft"]["tasks"][0]["exit_criteria"] == ["필수 근거가 확인되었어요"]
    assert artifact["draft"]["tasks"][0]["completion_design"]["checks"][0]["confirmation"] == "human"
    assert artifact["draft"]["mermaid"].startswith("flowchart TD")
    assert "```mermaid" not in response.answer.markdown
    assert "결과 영역" in response.answer.markdown
    assert {item.harness_id for item in response.harness_results} >= {"context.work", "sop.authoring"}


def test_large_sop_response_can_compact_context_without_losing_run_usage(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model
    v2_service.settings = replace(v2_service.settings, response_budget_bytes=4096)

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 초안을 만들어줘", capability_id="sop.plan"),
    )

    stored_run = v2_service.store.get("runs", response.run_id)
    work_run = v2_service.store.get("work_runs", response.work_run_id)
    assert response.artifact_refs
    assert stored_run["usage_ref"].startswith("usage_")
    assert stored_run["usage"]["usage_ref"] == stored_run["usage_ref"]
    assert work_run["usage"]["usage_ref"] == stored_run["usage_ref"]
    assert len(json.dumps(response.model_dump(mode="json"), ensure_ascii=False).encode()) <= 4096


def test_response_budget_never_detaches_related_questions_from_their_sources(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    v2_service.settings = replace(v2_service.settings, response_budget_bytes=4096)

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드의 게시 기준과 확인 근거를 자세히 알려줘"),
    )

    assert all(item.source_refs for item in response.related_questions)
    assert len(json.dumps(response.model_dump(mode="json"), ensure_ascii=False).encode()) <= 4096


def test_sop_draft_and_confirmation_use_the_injected_domain_service_and_same_work_run(
    v2_service: AgentV2Service,
    principal: Principal,
):
    calls: list[tuple[str, dict[str, Any]]] = []

    def create_domain_draft(_principal: Principal, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(("create", payload))
        return {
            "domain_kind": "sop_registration",
            "domain_label": "SOP 등록",
            "domain_ref": "sop-registration-domain-1",
            "status": "validated",
            "validation": {"valid": True, "errors": [], "warnings": []},
            "confirm_operation": "sop.draft.publish_request",
            "production_changed": False,
        }

    def publish_request(_principal: Principal, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(("publish", payload))
        return {
            "domain_kind": "sop_registration",
            "domain_ref": payload["domain_ref"],
            "draft_id": payload["domain_ref"],
            "status": "publish_requested",
            "message": "게시 검토 대기",
            "production_changed": False,
        }

    v2_service.domain_services = DomainServiceGateway(
        {
            "sop.draft.create": create_domain_draft,
            "sop.draft.publish_request": publish_request,
        }
    )
    model = RepairingSopModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 초안을 만들어줘", capability_id="sop.plan"),
    )
    artifact = v2_service.store.get("artifacts", response.artifact_refs[0].artifact_id)
    plan = v2_service.store.get("plans", response.plan_ref)

    assert artifact["domain"]["domain_ref"] == "sop-registration-domain-1"
    assert plan["domain_ref"] == "sop-registration-domain-1"
    assert plan["work_run_id"] == response.work_run_id
    assert calls[0][0] == "create"
    assert calls[0][1]["draft"]["tasks"][0]["completion_design"]["checks"]

    confirmed = asyncio.run(v2_service.confirm_plan(principal, response.plan_ref, "Task와 근거를 검토했습니다."))

    assert calls[-1][0] == "publish"
    assert confirmed["domain_result"]["status"] == "publish_requested"
    assert confirmed["work_run_id"] == response.work_run_id
    assert confirmed["work_run_status"] == "completed"
    assert confirmed["production_changed"] is False


def test_confirmed_action_plan_records_the_real_domain_result_as_loop_progress(
    v2_service: AgentV2Service,
    principal: Principal,
):
    async def invoke_action(_principal: Principal, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "request_id": "action-request-1",
            "status": "completed",
            "message": f"{payload['action_key']} dry-run 완료",
            "production_changed": False,
        }

    v2_service.domain_services = DomainServiceGateway({"action.invoke": invoke_action})
    model = ScriptedPlanner()
    v2_service.model = model
    v2_service.search.model = model
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="근거 확인 Action을 실행해줘",
            capability_id="action.plan",
            page_ref="/docs/boi%3Apublic%3Aguide",
            input_delta={
                "operation": "run",
                "action_key": "manual.review",
                "payload": {"case_id": "A-1"},
                "dry_run": True,
            },
        ),
    )

    assert response.plan_ref
    assert response.work_intent is not None
    assert response.work_intent.operation == WorkOperation.run
    assert response.work_intent.operation_plan == [
        WorkOperation.understand,
        WorkOperation.validate,
        WorkOperation.run,
        WorkOperation.observe,
    ]
    waiting = v2_service.learning.get_run(principal, response.work_run_id)
    assert waiting["status"] == "waiting_human"
    waiting_goal = v2_service.get_goal_plan(principal, response.goal_plan_ref)
    waiting_steps = {item["semantic_operation"]: item["status"] for item in waiting_goal["steps"]}
    assert waiting_goal["status"] == "waiting_confirmation"
    assert waiting_steps["run"] == "waiting_confirmation"
    assert waiting_steps["observe"] == "pending"

    confirmed = asyncio.run(v2_service.confirm_plan(principal, response.plan_ref, "dry-run 입력을 확인했습니다."))
    progressed = v2_service.learning.get_run(principal, response.work_run_id)

    assert confirmed["domain_result"]["request_id"] == "action-request-1"
    assert confirmed["work_run_status"] == "completed"
    assert confirmed["goal_plan_status"] == "completed"
    assert progressed["loop"]["deltas"][-1]["kind"] == "action_result"
    assert progressed["loop"]["deltas"][-1]["ref"] == "action-request-1"


def test_natural_followup_refines_the_existing_task_as_a_preview_and_validates_the_same_artifact(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = RefiningSopModel()
    v2_service.model = model
    v2_service.search.model = model
    created = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="근거 확인 SOP 만들어", capability_id="sop.plan"),
    )
    artifact_id = created.artifact_refs[0].artifact_id
    artifact_count = len(v2_service.store.list("artifacts", employee_id=principal.employee_id))

    refined = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 Task의 완료 항목과 확인할 자료를 더 구체적으로 다듬어줘",
            work_session_id=created.work_session_id,
        ),
    )

    assert refined.capability_id == "sop.plan"
    assert refined.work_intent and refined.work_intent.operation.value == "refine"
    assert refined.artifact_refs[0].artifact_id == artifact_id
    assert refined.artifact_refs[0].metadata["proposal_id"].startswith("proposal_")
    assert len(v2_service.store.list("artifacts", employee_id=principal.employee_id)) == artifact_count
    assert v2_service.store.get("artifacts", artifact_id)["revision"] == 1

    validated = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="이 SOP 초안을 검증해줘", work_session_id=created.work_session_id),
    )
    assert validated.work_intent and validated.work_intent.operation.value == "validate"
    assert validated.artifact_refs[0].artifact_id == artifact_id
    assert validated.loop_state["status"] == "completed"


def test_manual_task_cannot_create_ai_draft(v2_service: AgentV2Service, principal: Principal):
    fake = ScriptedPlanner()
    v2_service.model = fake
    v2_service.search.model = fake
    with pytest.raises(Exception) as exc_info:
        v2_service.run_turn(
            principal,
            AgentTurnRequest(
                question="Skill 초안을 만들어줘",
                capability_id="skill.plan",
                task_ref="review-task",
            ),
        )
    assert getattr(exc_info.value, "status_code", None) in {403, 503}


def test_work_context_uses_task_exit_criteria_and_external_references(v2_service: AgentV2Service, principal: Principal):
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="사람 검토 SOP를 찾아줘",
            capability_id="knowledge.search",
            task_ref="review-task",
            external_ai_summary="별도 AI가 기존 근거 두 건을 비교했으며 최종 판단은 아직 하지 않았다.",
            external_artifact_refs=["minio://boi/context/report-1"],
        ),
    )
    context = v2_service.get_context(principal, response.context_ref)
    assert context["task_mode"] == "manual"
    assert context["workflow_ref"] == "boi:public:sop:manual"
    assert context["exit_criteria"] == ["사람이 필수 근거를 확인하고 판단을 기록한다"]
    assert context["required_evidence"] == ["review_note"]
    assert context["completion_design"]["evidence"][0]["label"] == "담당자 검토 기록"
    assert context["external_ai_summary"].startswith("별도 AI")
    assert context["manifest"]["external_artifact_refs"] == ["minio://boi/context/report-1"]
    assert context["manifest"]["raw_content_in_prompt"] is False


def test_task_completion_hides_technical_refs_and_requires_real_autopilot_bindings():
    lookup = {
        "equipment.alarm.raised.v1": "설비 Alarm 발생",
        "boi:public:event-types:equipment.alarm.raised.v1": "설비 Alarm 발생",
        "boi:public:dictionary:alarm": "Alarm",
    }
    ready = normalise_task_completion(
        {
            "execution_mode": "autopilot",
            "exit_criteria": ["설비 Alarm 발생 접수가 확인되어 업무를 시작할 수 있어요"],
            "completion_design": {
                "version": 1,
                "checks": [
                    {
                        "check_id": "alarm-received",
                        "label": "설비 Alarm 발생 접수가 확인되어 업무를 시작할 수 있어요",
                        "confirmation": "system",
                        "binding": {
                            "kind": "event",
                            "ref": "equipment.alarm.raised.v1",
                        },
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "alarm-event",
                        "label": "설비 Alarm 발생",
                        "source_kind": "event",
                        "ref": "boi:public:event-types:equipment.alarm.raised.v1",
                        "provided_by": "system",
                        "required": True,
                    }
                ],
            },
        },
        label_lookup=lookup,
    )
    check = ready["completion_design"]["checks"][0]
    evidence = ready["completion_design"]["evidence"][0]
    assert check["label"] == "설비 Alarm 발생 접수가 확인되어 업무를 시작할 수 있어요"
    assert "equipment.alarm.raised.v1" not in check["label"]
    assert check["binding"]["kind"] == "event"
    assert evidence["label"] == "설비 Alarm 발생"
    assert ready["required_evidence"] == ["boi:public:event-types:equipment.alarm.raised.v1"]
    assert ready["completion_readiness"]["status"] == "ready"

    blocked = normalise_task_completion(
        {
            "execution_mode": "autopilot",
            "exit_criteria": ["담당자가 결과를 눈으로 확인했어요"],
            "required_evidence": ["담당자 메모"],
        }
    )
    assert blocked["completion_readiness"]["status"] == "needs_connection"
    assert blocked["completion_readiness"]["automation_ready"] is False


def test_legacy_sop_completion_is_hydrated_without_mutating_until_first_save(
    v2_service: AgentV2Service,
    principal: Principal,
):
    artifact_id = "artifact_legacy_completion"
    task_id = "task_legacy_alarm"
    v2_service.store.put(
        "artifacts",
        artifact_id,
        {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": "sop.plan",
            "status": "draft",
            "title": "Legacy Alarm SOP",
            "revision": 1,
            "draft": {
                "title": "Legacy Alarm SOP",
                "goal": "Alarm 대응",
                "tasks": [
                    {
                        "task_id": task_id,
                        "name": "Alarm 접수",
                        "purpose": "업무 이벤트를 접수한다.",
                        "execution_mode": "autopilot",
                        "exit_criteria": ["equipment.alarm.raised.v1 유형의 이벤트가 SOP 시작 트리거로 식별됨"],
                        "required_evidence": ["boi:public:event-types:equipment.alarm.raised.v1"],
                    }
                ],
                "mermaid": 'flowchart TD\n  T1["Alarm 접수"]',
            },
        },
    )

    hydrated = v2_service.get_artifact(principal, artifact_id)
    task = hydrated["draft"]["tasks"][0]

    assert "completion_design" not in v2_service.store.get("artifacts", artifact_id)["draft"]["tasks"][0]
    assert "equipment.alarm.raised.v1" not in task["completion_design"]["checks"][0]["label"]
    assert task["required_evidence"] == ["boi:public:event-types:equipment.alarm.raised.v1"]

    saved = v2_service.patch_sop_artifact(
        principal,
        artifact_id,
        SopArtifactPatchRequest(
            expected_revision=1,
            task_updates=[{"task_id": task_id, "base_task": task, "task": task}],
            selected_task_id=task_id,
        ),
    )

    assert saved["revision"] == 2
    assert v2_service.store.get("artifacts", artifact_id)["draft"]["tasks"][0]["completion_design"]["version"] == 1


def test_task_policy_requires_confirmation_for_medium_mutation(v2_service: AgentV2Service, principal: Principal):
    definition = v2_service.registry.get("action.plan").model_copy(
        update={"operation": "mutate", "risk": RiskLevel.medium}
    )
    decision = TaskPolicy(v2_service.repository).evaluate(
        definition,
        principal=principal,
        task_ref="",
        confirmed=False,
    )
    assert decision.mode == TaskMode.copilot
    assert decision.allowed is False
    assert decision.confirmation_required is True


def test_task_policy_projects_legacy_sop_stage_into_the_shared_completion_contract(
    v2_service: AgentV2Service,
    principal: Principal,
):
    path = v2_service.settings.content_root / "public" / "sop" / "runtime-task-contract.md"
    _write_markdown(
        path,
        {
            "boi_id": "boi:public:sop:runtime-task-contract",
            "boi_type": "boi/sop",
            "title": "Runtime Task Contract",
            "visibility": "public",
            "status": "reviewed",
            "workflow": {
                "stages": [
                    {
                        "id": "manual-review",
                        "name": "담당자 판단",
                        "execution_mode": "manual",
                        "evidence_refs": ["Trend 그래프", "담당자 메모"],
                        "outputs": ["판단 기록"],
                        "manual_actions": ["manual.review"],
                    },
                    {
                        "id": "automatic-check",
                        "name": "상태 확인",
                        "execution_mode": "autopilot",
                        "evidence_refs": ["system.status"],
                        "outputs": ["status.checked.v1"],
                        "emits_event": "status.checked.v1",
                    },
                ]
            },
        },
        "# Runtime Task Contract",
    )
    v2_service.repository.invalidate_source_cache()
    policy = TaskPolicy(v2_service.repository, v2_service.store)

    manual = policy.resolve_task(principal, "manual-review")
    automatic = policy.resolve_task(principal, "automatic-check")

    assert manual["required_evidence"] == ["Trend 그래프", "담당자 메모"]
    assert manual["completion_design"]["checks"][0]["confirmation"] == "human"
    assert manual["completion_design"]["evidence"][0]["provided_by"] == "human"
    assert automatic["completion_design"]["checks"][0]["confirmation"] == "system"
    assert automatic["completion_design"]["checks"][0]["binding"] == {
        "kind": "event",
        "ref": "status.checked.v1",
    }


def test_pat_is_shown_once_scoped_and_revocable(v2_service: AgentV2Service, principal: Principal):
    created = v2_service.pats.create(principal, TokenCreateRequest(name="Codex", scopes=["boi.read", "boi.draft"]))
    assert created["token"].startswith("boi_pat_")
    listed = v2_service.pats.list(principal)
    assert listed[0]["token_id"] == created["token_id"]
    assert "token" not in listed[0]
    assert "token_hash" not in listed[0]
    authenticated = v2_service.pats.authenticate(created["token"])
    assert authenticated and authenticated.employee_id == principal.employee_id
    assert v2_service.pats.revoke(principal, created["token_id"])
    assert v2_service.pats.authenticate(created["token"]) is None


def test_pat_fails_closed_when_current_rbac_cannot_be_resolved(v2_service: AgentV2Service, principal: Principal):
    created = v2_service.pats.create(principal, TokenCreateRequest(name="Claude", scopes=["boi.read"]))

    def unavailable_identity(_employee_id: str):
        raise RuntimeError("identity provider unavailable")

    v2_service.pats.identity_provider = unavailable_identity
    assert v2_service.pats.authenticate(created["token"]) is None


def test_deep_job_can_be_cancelled_without_creating_an_artifact(v2_service: AgentV2Service, principal: Principal):
    job_id = "job_cancel_test"
    v2_service.store.put(
        "jobs",
        job_id,
        {"job_id": job_id, "employee_id": principal.employee_id, "status": "queued"},
    )

    result = v2_service.cancel_job(principal, job_id)

    assert result == {"job_id": job_id, "status": "cancelled"}
    assert v2_service.store.get("jobs", job_id)["status"] == "cancelled"
    assert v2_service.store.list("artifacts", employee_id=principal.employee_id) == []


def test_deep_worker_uses_the_latest_non_empty_assistant_synthesis():
    messages = [
        {"role": "assistant", "content": "근거 evidence_id를 포함한 최종 합성"},
        {"role": "tool", "content": "검색 결과"},
        {"role": "assistant", "content": ""},
    ]

    assert latest_assistant_text(messages) == "근거 evidence_id를 포함한 최종 합성"


def test_deep_worker_appends_only_acl_verified_exact_evidence_ids():
    ledger = {
        "boi:public:guide": {
            "evidence_id": "boi:public:guide",
            "title": "BoI Wiki 운영 가이드",
            "url": "/docs/boi:public:guide",
        }
    }

    rendered = ensure_exact_evidence_ledger("번호형 근거를 사용한 심층 초안", ledger)

    assert "`boi:public:guide` - BoI Wiki 운영 가이드" in rendered
    assert ensure_exact_evidence_ledger(rendered, ledger) == rendered


def test_deep_worker_preserves_the_complete_selected_context_and_evidence_ledger():
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:deep:{index}",
            kind="document",
            title=f"심층 근거 {index}",
            summary=("긴 근거 맥락 " * 120) + f"DEEP_TAIL_{index}",
            url=f"/docs/boi:public:deep:{index}",
            metadata={"best_chunk": {"chunk_id": f"chunk-{index}", "text": f"CHUNK_TAIL_{index}"}},
        )
        for index in range(20)
    ]
    context = WorkContextPack(
        context_id="context-complete-deep",
        employee_id="100001",
        capability_id="knowledge.deep",
        goal="선택된 모든 근거를 종합한다",
        evidence_refs=evidence,
        external_ai_summary=("외부 요약 " * 500) + "EXTERNAL_DEEP_TAIL",
    )

    brief = build_deep_context_brief(context)
    ledger = {
        item.evidence_id: {"title": item.title, "url": item.url}
        for item in evidence
    }
    rendered = ensure_exact_evidence_ledger("심층 초안", ledger)

    assert len(brief["selected_evidence"]) == 20
    assert brief["selected_evidence"][-1]["summary"].endswith("DEEP_TAIL_19")
    assert brief["selected_evidence"][-1]["metadata"]["best_chunk"]["text"] == "CHUNK_TAIL_19"
    assert brief["external_ai_summary"].endswith("EXTERNAL_DEEP_TAIL")
    assert "`boi:public:deep:19`" in rendered


def test_draft_prompt_preserves_all_session_tasks_instructions_and_selected_evidence(
    v2_service: AgentV2Service,
):
    definition = v2_service.registry.get("sop.plan")
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:draft:{index}",
            kind="document",
            title=f"초안 근거 {index}",
            summary=("초안 원문 맥락 " * 120) + f"DRAFT_TAIL_{index}",
            url=f"/docs/boi:public:draft:{index}",
        )
        for index in range(20)
    ]
    request = AgentTurnRequest(
        question="근거를 모두 반영해 SOP 초안을 만들어줘",
        external_ai_summary=("외부 검토 요약 " * 500) + "EXTERNAL_DRAFT_TAIL",
        input_delta={
            "_resolved_goal": "전체 근거와 대화 맥락을 보존한 SOP 초안을 만든다",
            "_helper_instructions": ("도우미 지침 " * 600) + "HELPER_DRAFT_TAIL",
            "_work_session_context": {
                "summary": ("세션 요약 " * 200) + "SESSION_DRAFT_TAIL",
                "recent_messages": [
                    {"role": "user", "text": f"MESSAGE_{index}", "source_refs": [f"source:{index}"]}
                    for index in range(20)
                ],
                "active_artifact": {
                    "artifact_id": "artifact-complete",
                    "tasks": [
                        {"name": f"TASK_{index}", "purpose": ("목적 " * 100) + f"TASK_TAIL_{index}"}
                        for index in range(10)
                    ],
                },
            },
        },
    )

    _system, prompt, _schema = v2_service._draft_prompt(definition, request, evidence)

    for marker in (
        "boi:public:draft:19",
        "DRAFT_TAIL_19",
        "MESSAGE_19",
        "source:19",
        "TASK_TAIL_9",
        "SESSION_DRAFT_TAIL",
        "EXTERNAL_DRAFT_TAIL",
        "HELPER_DRAFT_TAIL",
    ):
        assert marker in prompt


def test_deep_job_pilot_clamps_isolated_subagents_and_parallelism(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        v2_service,
        "readiness",
        lambda *_args, **_kwargs: {
            "ready": True,
            "dependencies": {
                "content": True,
                "postgres": True,
                "model": True,
                "embedding": True,
                "search_index": True,
                "deep_worker": True,
                "pat": True,
            },
            "warnings": [],
        },
    )
    created = v2_service.create_deep_job(
        principal,
        DeepJobRequest(
            goal="운영 기준과 관련 SOP를 심층 비교해줘",
            pilot_mode=True,
            token_budget=24000,
            max_tool_calls=12,
            max_subagents=4,
            max_parallelism=4,
        ),
    )
    job = v2_service.get_job(principal, created["job_id"])

    assert job["max_tool_calls"] == 5
    assert job["requested_max_subagents"] == 4
    assert job["subagent_budget_limit"] == 0
    assert job["max_subagents"] == 0
    assert job["max_parallelism"] == 1
    assert job["subagent_policy"] == "disabled_by_token_budget"
    assert job["independent_review_required"] is True

    expanded = v2_service.create_deep_job(
        principal,
        DeepJobRequest(
            goal="운영 기준을 서로 독립된 관점으로 심층 비교해줘",
            input={"require_subagent": True},
            pilot_mode=False,
            token_budget=160000,
            max_tool_calls=6,
            max_subagents=4,
            max_parallelism=4,
        ),
    )
    expanded_job = v2_service.get_job(principal, expanded["job_id"])

    assert expanded_job["subagent_budget_limit"] == 4
    assert expanded_job["max_subagents"] == 4
    assert expanded_job["max_parallelism"] == 4
    assert expanded_job["max_input_tokens"] == 160000 // 6
    assert expanded_job["subagent_policy"] == "enabled"
    assert expanded_job["require_subagent"] is True


def test_deep_worker_uses_the_same_local_reasoning_policy_as_the_pet(
    v2_service: AgentV2Service,
):
    v2_service.settings = replace(
        v2_service.settings,
        model_provider="openai_compatible",
        model_base_url="http://lmstudio.example:1234/v1",
        model_api_key="not-needed",
        model_name="google/gemma-local",
        deep_model="google/gemma-local",
        model_reasoning_effort="none",
        model_max_output_tokens=4096,
        deep_max_input_tokens=12000,
    )

    adapter = DeepWorkRunner(v2_service)._deep_model_adapter()

    assert adapter.model_name == "google/gemma-local"
    assert adapter.reasoning_effort == "none"
    assert adapter.max_tokens == 4096
    if hasattr(adapter, "profile"):
        assert adapter.profile["max_input_tokens"] == 12000
    assert str(adapter.openai_api_base) == "http://lmstudio.example:1234/v1"


def test_deep_worker_finishes_the_same_work_run_with_a_draft_and_evidence(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    turn = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드 찾아줘"))
    work_run = v2_service.learning.get_run(principal, turn.work_run_id)
    work_run.update({"status": "queued", "decision": "continue", "revision": work_run["revision"] + 1})
    v2_service.store.put("work_runs", turn.work_run_id, work_run)
    job_id = "job_work_learning_test"
    v2_service.store.put(
        "jobs",
        job_id,
        {
            "job_id": job_id,
            "employee_id": principal.employee_id,
            "principal_roles": principal.roles,
            "principal_teams": principal.teams,
            "capability_id": "deep.research",
            "goal": "운영 기준 심층 분석",
            "context_id": turn.context_ref,
            "work_session_id": turn.work_session_id,
            "work_run_id": turn.work_run_id,
            "status": "queued",
        },
    )
    runner = DeepWorkRunner(v2_service)
    monkeypatch.setattr(
        runner,
        "_execute",
        lambda _job: {
            "title": "운영 기준 심층 분석",
            "body": "근거를 바탕으로 작성한 검토용 초안",
            "status": "draft",
            "usage": {"usage_id": "usage_deep_test", "total_tokens": 3210},
            "evidence_ledger": [
                {"evidence_id": "boi:public:guide", "title": "BoI Wiki 운영 가이드", "url": "/docs/boi:public:guide"}
            ],
        },
    )

    assert runner.run_once() is True
    job = v2_service.store.get("jobs", job_id)
    finished = v2_service.learning.view_run(principal, turn.work_run_id)
    assert job and job["status"] == "completed"
    assert job["artifact_id"].startswith("artifact_")
    assert job["usage_ref"] == "usage_deep_test"
    assert finished["status"] == "waiting_review"
    assert "boi:public:guide" in finished["evidence_refs"]


def test_v2_api_ignores_employee_query_and_exposes_workspace(v2_service: AgentV2Service):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    app = FastAPI()
    app.include_router(build_agent_v2_router(v2_service))
    with TestClient(app) as client:
        bootstrap = client.get("/api/v2/bootstrap?employee_id=100003&page_ref=/")
        assert bootstrap.status_code == 200
        assert bootstrap.json()["identity"]["employee_id"] == "100001"
        assert bootstrap.json()["readiness"]["warnings"] == []
        assert "index" not in bootstrap.json()["readiness"]["surface_status"]["message"].lower()
        anchored = client.get(
            "/api/v2/bootstrap",
            params={"page_ref": "/docs/boi%3Apublic%3Aguide?employee_id=100001"},
        )
        assert anchored.json()["page"]["context"]["ref"] == "boi:public:guide"
        result = client.post("/api/v2/agent/turns", json={"question": "BoI Wiki 운영 가이드 찾아줘"})
        assert result.status_code == 200
        turn = result.json()
        assert turn["capability_id"] == "knowledge.search"
        assert turn["citations"]
        assert turn["related_questions"]
        assert turn["work_run_id"].startswith("workrun_")
        work_run = client.get(f"/api/v2/work-runs/{turn['work_run_id']}")
        assert work_run.status_code == 200
        assert work_run.json()["evidence_ledger"]
        harnesses = client.get("/api/v2/harnesses").json()["items"]
        assert {item["harness_id"] for item in harnesses} >= {
            "context.work",
            "task.runtime",
            "sop.authoring",
            "business-event.definition",
            "action.authoring",
            "skill.authoring",
            "learning.capture",
        }
        assert client.get(f"/api/v2/citations/{turn['citations'][0]['citation_id']}").status_code == 200
        assert client.get(f"/api/v2/goal-plans/{turn['goal_plan_ref']}").json()["status"] == "completed"
        sources = client.get(f"/api/v2/work-sessions/{turn['work_session_id']}/sources")
        assert sources.status_code == 200
        source_payload = sources.json()
        pinned = client.patch(
            f"/api/v2/work-sessions/{turn['work_session_id']}/sources",
            json={"expected_revision": source_payload["revision"], "pin_refs": [turn["citations"][0]["source_ref"]]},
        )
        assert pinned.status_code == 200
        note = client.post(
            "/api/v2/notes/from-turn",
            json={"run_id": turn["run_id"], "work_session_id": turn["work_session_id"]},
        )
        assert note.status_code == 200
        assert note.json()["artifact"]["status"] == "provisional"
        use_note = client.post(
            f"/api/v2/notes/{note.json()['artifact']['artifact_id']}/use-as-source",
        )
        assert use_note.status_code == 200
        assert note.json()["artifact"]["artifact_id"] in use_note.json()["source_set"]["pinned"]
        filtered = client.get("/api/v2/search", params=[("q", "BoI Wiki 운영 가이드"), ("kinds", "document")])
        assert filtered.status_code == 200
        assert filtered.json()["items"]
        assert {item["kind"] for item in filtered.json()["items"]} == {"document"}


def test_agent_answer_html_is_server_rendered_and_escapes_raw_markup():
    rendered = render_agent_markdown(
        "## 확인 결과\n\n<script>alert(1)</script> **안전한 답변**\n\n"
        "- [근거](/api/v2/citations/cite_1)\n"
        "- [위험](javascript:alert(2))"
    )

    assert '<div class="agent-answer-markdown">' in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert '<a href="/api/v2/citations/cite_1">근거</a>' in rendered
    assert "javascript:" not in rendered


def test_agent_turn_sse_reports_real_phases_and_preserves_final_contract(
    v2_service: AgentV2Service,
):
    model = GroundedAnswerModel()
    v2_service.model = model
    v2_service.search.model = model
    app = FastAPI()
    app.include_router(build_agent_v2_router(v2_service))

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v2/agent/turns",
            headers={"Accept": "text/event-stream"},
            json={"question": "BoI Wiki 운영 가이드 찾아줘"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            blocks = "\n".join(response.iter_lines()).split("\n\n")

    events: list[tuple[str, dict[str, Any]]] = []
    for block in blocks:
        if not block.strip():
            continue
        event = next((line[6:].strip() for line in block.splitlines() if line.startswith("event:")), "")
        data = next((line[5:].strip() for line in block.splitlines() if line.startswith("data:")), "{}")
        events.append((event, json.loads(data)))

    assert [event for event, _payload in events] == [
        "accepted",
        "progress",
        "progress",
        "progress",
        "progress",
        "final",
    ]
    assert [payload.get("stage") for event, payload in events if event == "progress"] == [
        "context",
        "retrieval",
        "judgment",
        "composing",
    ]
    final = events[-1][1]
    assert final["capability_id"] == "knowledge.search"
    assert final["citations"]
    assert final["answer"]["display_html"].startswith('<div class="agent-answer-markdown">')
    timeline = [
        item
        for item in v2_service.store.list("session_messages", employee_id="100001", limit=100)
        if item.get("session_id") == final["work_session_id"]
    ]
    assistant_message = next(item for item in timeline if item.get("role") == "assistant")
    assert assistant_message["display_html"].startswith('<div class="agent-answer-markdown">')
    assert v2_service.store.get("user_work_profiles", "100001")["source_revision"]


def test_living_knowledge_sources_data_artifacts_graph_and_review_boundary(
    v2_service: AgentV2Service,
    principal: Principal,
):
    metadata_root = v2_service.settings.runtime_root / "data-lake-artifacts" / "metadata"
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "trend-profile.json").write_text(
        json.dumps(
            {
                "artifact_id": "trend-profile",
                "filename": "etch-trend.csv",
                "visibility": "private",
                "owner_employee_id": principal.employee_id,
                "sha256": "abc123",
                "size_bytes": 100000,
                "profile": {
                    "summary": "ETCH 설비 압력 Trend의 이상 구간 요약",
                    "sample_rows": [{"equipment": "ETCH-01", "pressure": 91.2}],
                    "raw": "원문 전문은 검색 색인에 들어가면 안 됩니다.",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_markdown(
        v2_service.settings.content_root / "public" / "broken-link.md",
        {
            "type": "boi/manual",
            "title": "연결 점검 가이드",
            "boi_id": "boi:public:broken-link",
            "visibility": "public",
            "status": "reviewed",
        },
        "[사라진 문서](/docs/boi:public:missing-reference)\n\n"
        "[동적 자료](/api/data-lake/artifacts/trend-profile)",
    )
    v2_service.repository.invalidate_source_cache()

    sources = v2_service.knowledge.list_sources(principal)
    assert {item["source_id"] for item in sources["items"]} >= {
        "source:okf",
        "source:git",
        "source:data-lake",
    }
    sync = v2_service.knowledge.sync_source(principal, "source:okf")
    assert sync["source"]["status"] == "ready"
    assert sync["graph"]["nodes"] > 0
    assert sync["graph"]["edges"] > 0

    result = v2_service.search.search("ETCH 설비 압력 Trend 이상", principal, limit=8)
    data_record = next(item for item in result.items if item.kind == "data_artifact")
    assert data_record.evidence_id == "data_artifact:trend-profile"
    stored_record = next(
        item
        for item in v2_service.repository.authoritative_records(principal)
        if item.record_id == "data_artifact:trend-profile"
    )
    assert "원문 전문은 검색 색인에 들어가면 안 됩니다." not in stored_record.text
    assert "ETCH 설비 압력 Trend의 이상 구간 요약" in stored_record.text

    graph = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:public:sop:manual",
        depth=2,
        limit=50,
    )
    task_edge = next(edge for edge in graph["edges"] if edge["relation"] == "has_task")
    assert task_edge["payload"]["provenance"] == "extracted"
    assert task_edge["payload"]["extractor_version"].startswith("boi-knowledge-compiler/")
    path = v2_service.knowledge.explore(
        principal,
        view="path",
        source_ref="boi:public:sop:manual",
        target_ref=task_edge["target_id"],
        depth=3,
        limit=50,
    )
    assert path["path_refs"] == ["boi:public:sop:manual", task_edge["target_id"]]
    assert all(isinstance(item, dict) and item.get("payload", {}).get("title") for item in path["nodes"])

    health = v2_service.knowledge.health(principal, refresh=True)
    broken = next(item for item in health["items"] if item["kind"] == "broken_link")
    assert "missing-reference" in broken["summary"]
    assert all("/api/data-lake/" not in item["summary"] for item in health["items"])
    proposal = next(
        item
        for item in v2_service.knowledge.proposals(principal)["items"]
        if item["finding_id"] == broken["finding_id"]
    )
    before = (v2_service.settings.content_root / "public" / "broken-link.md").read_text(encoding="utf-8")
    applied = v2_service.knowledge.apply_proposal(
        principal,
        proposal["proposal_id"],
        KnowledgeProposalApplyRequest(
            expected_revision=proposal["revision"],
            confirmation="confirm",
            reason="담당자 검토 요청",
        ),
    )
    after = (v2_service.settings.content_root / "public" / "broken-link.md").read_text(encoding="utf-8")
    assert applied["status"] == "review_required"
    assert applied["source_of_truth_changed"] is False
    assert after == before


def test_living_knowledge_compiles_all_acl_nodes_but_never_exposes_another_users_private_graph(
    v2_service: AgentV2Service,
    principal: Principal,
):
    compiled = v2_service.knowledge.compile_graph(principal)
    assert compiled["nodes"] >= 6
    assert compiled["sync_mode"] == "incremental_upsert"
    own = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:private:100001:alarm-note",
        depth=1,
        limit=20,
    )
    hidden = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:private:100002:secret",
        depth=1,
        limit=20,
    )
    assert any(item["node_id"] == "boi:private:100001:alarm-note" for item in own["nodes"])
    assert not hidden["nodes"]
    assert not hidden["edges"]
    query = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["boi:public:sop:manual"],
            query_kind="workflow",
            depth=2,
            presentation="auto",
        ),
    )
    assert query["ok"] is True
    assert query["query_plan"]["query_kind"] == "workflow"
    assert query["presentation"] in {"mermaid", "list", "explorer"}
    assert all((edge.get("payload") or {}).get("provenance") for edge in query["edges"])
    semantic_edges = {
        (edge["source_id"], edge["relation"], edge["target_id"])
        for edge in query["edges"]
    }
    assert len(semantic_edges) == len(query["edges"])


def test_repeated_work_relation_requires_three_distinct_verified_completions_within_180_days(
    v2_service: AgentV2Service,
    principal: Principal,
):
    recent = now_iso()
    task_ref = "quality-review"
    for index in range(2):
        completion_id = f"completion-repeat-{index}"
        v2_service.store.put(
            "completion_records",
            completion_id,
            {
                "completion_id": completion_id,
                "employee_id": principal.employee_id,
                "work_run_id": f"work-run-repeat-{index}",
                "task_ref": task_ref,
                "decision": "complete",
                "created_at": recent,
            },
        )
    v2_service.store.put(
        "completion_records",
        "completion-repeat-old",
        {
            "completion_id": "completion-repeat-old",
            "employee_id": principal.employee_id,
            "work_run_id": "work-run-repeat-old",
            "task_ref": task_ref,
            "decision": "complete",
            "created_at": "2025-01-01T00:00:00+00:00",
        },
    )

    v2_service.knowledge.compile_graph(principal)
    before = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref=f"task:{task_ref}",
        depth=1,
        limit=20,
    )
    assert not any(edge["relation"] == "repeated_performer" for edge in before["edges"])
    assert v2_service.store.list("work_role_profiles", employee_id=principal.employee_id, limit=20) == []

    completion_id = "completion-repeat-2"
    v2_service.store.put(
        "completion_records",
        completion_id,
        {
            "completion_id": completion_id,
            "employee_id": principal.employee_id,
            "work_run_id": "work-run-repeat-2",
            "task_ref": task_ref,
            "decision": "complete",
            "created_at": recent,
        },
    )
    v2_service.knowledge.compile_graph(principal)
    after = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref=f"task:{task_ref}",
        depth=1,
        limit=20,
    )
    repeated = next(edge for edge in after["edges"] if edge["relation"] == "repeated_performer")
    assert repeated["payload"]["provenance"] == "human_verified"
    assert repeated["payload"]["metadata"]["completion_count"] == 3
    profile = v2_service.store.list("work_role_profiles", employee_id=principal.employee_id, limit=20)[0]
    assert profile["completion_count"] == 3
    assert profile["window_days"] == 180


@pytest.mark.parametrize(
    ("query_kind", "focal_entities", "expected_presentation"),
    [
        ("neighbors", ["boi:public:sop:manual"], {"list", "explorer"}),
        ("workflow", ["boi:public:sop:manual"], {"mermaid", "explorer"}),
        ("impact", ["boi:public:sop:manual"], {"list", "explorer"}),
        ("responsibility", ["person:100001"], {"list", "explorer"}),
        ("compare", ["boi:public:sop:manual", "boi:public:guide"], {"table"}),
        ("tour", ["boi:public:sop:manual"], {"list", "explorer"}),
    ],
)
def test_universal_graph_query_kinds_keep_acl_provenance_and_auto_presentation(
    v2_service: AgentV2Service,
    principal: Principal,
    query_kind: str,
    focal_entities: list[str],
    expected_presentation: set[str],
):
    v2_service.knowledge.compile_graph(principal)
    result = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=focal_entities,
            query_kind=query_kind,
            depth=2,
            presentation="auto",
        ),
    )
    assert result["ok"] is True
    assert result["query_plan"]["query_kind"] == query_kind
    assert result["presentation"] in expected_presentation
    assert all((edge.get("payload") or {}).get("provenance") for edge in result["edges"])
    assert all("boi:private:100002" not in str(node.get("node_id")) for node in result["nodes"])


def test_graph_compiler_includes_only_explicit_relation_bearing_drafts(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    graph = v2_service.store.ontology_neighbors(
        ["boi:public:guide:related-draft"],
        depth=1,
        limit=20,
        employee_id=principal.employee_id,
        team_ids=principal.teams,
        include_all=principal.is_admin,
    )
    node_by_id = {item["node_id"]: item for item in graph["nodes"]}

    assert node_by_id["boi:public:guide:related-draft"]["payload"]["status"] == "draft"
    assert node_by_id["boi:public:guide:related-draft"]["payload"]["reviewed"] is False
    assert any(edge["relation"] == "guides" for edge in graph["edges"])
    assert "boi:public:skill:smoke" not in node_by_id
    searchable = {
        item.record_id for item in v2_service.repository.authoritative_records(principal)
    }
    assert "boi:public:guide:related-draft" not in searchable


def test_relation_required_graph_query_does_not_report_empty_success(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    result = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["boi:public:dictionary:cross-section-inspection"],
            query_kind="responsibility",
            depth=2,
        ),
    )

    assert result["ok"] is False
    assert result["meaningful"] is False
    assert result["edges"] == []
    assert result["empty_reason"]


def test_agent_does_not_publish_an_empty_relationship_artifact(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    source_ref = "boi:public:dictionary:cross-section-inspection"
    semantic_plan = SemanticPlan(
        resolved_goal="단면검사 개념과 직접 연결된 담당 관계를 확인한다",
        retrieval_query="단면검사 담당 관계",
        subjects=[
            SemanticSubject(
                mention="단면검사",
                entity_ref=source_ref,
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation="connect",
        evidence_scope="canonical",
        presentation="explorer",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="responsibility",
            focal_mentions=[source_ref],
            presentation="explorer",
        ),
        context_refs=[source_ref],
        target_ref=source_ref,
        answer_intent="relationship",
        confidence=1.0,
    )
    route = {
        "capability_id": "knowledge.search",
        "source": "scripted_planner",
        "reason": "근거 없는 관계 결과 차단",
        "semantic_plan": semantic_plan.model_dump(mode="json"),
        "work_intent": WorkIntent(
            goal="직접 연결된 담당 관계를 확인한다",
            resolved_goal="단면검사 개념과 직접 연결된 담당 관계를 확인한다",
            asset_kind=WorkAssetKind.knowledge,
            operation=WorkOperation.connect,
            operation_plan=[WorkOperation.connect],
            context_refs=[source_ref],
            target_ref=source_ref,
            presentation_mode="explorer",
            graph_query_draft=GraphQueryDraft(
                enabled=True,
                query_kind="responsibility",
                focal_mentions=[source_ref],
                presentation="explorer",
            ),
            result_purpose="explain",
            confidence=1.0,
        ).model_dump(mode="json"),
    }
    monkeypatch.setattr(v2_service, "_semantic_route", lambda *_args, **_kwargs: route)

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="이 개념의 담당 관계를 그래프로 보여줘"),
    )

    assert response.graph_result_ref == ""
    assert not any(item.artifact_type == "ontology_graph" for item in response.artifact_refs)
    assert response.answerability.status != "grounded" or response.grounded_claims


def test_graph_query_kinds_have_distinct_semantic_contracts(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    focal = "boi:public:sop:manual"

    workflow = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="workflow", depth=3),
    )
    assert {edge["relation"] for edge in workflow["edges"]} <= {
        "has_task", "part_of_workflow", "uses_sop", "uses_event", "uses_action",
        "uses_skill", "requires_evidence", "produces", "results_in", "triggered_by",
        "next_task", "precedes",
    }

    impact = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="impact", depth=3),
    )
    assert impact["downstream_refs"] == sorted(impact["downstream_refs"])
    assert all(impact["depth_by_ref"].get(ref, 0) > 0 for ref in impact["downstream_refs"])

    v2_service.store.upsert_ontology(
        [
            {
                "node_id": "completion:manual-review",
                "node_type": "completion_record",
                "payload": {
                    "title": "사람 검토 완료 기록",
                    "visibility": "public",
                    "observed_at": "2026-07-12T00:00:00+00:00",
                },
            }
        ],
        [
            {
                "edge_id": "edge:manual-lineage",
                "source_id": "completion:manual-review",
                "target_id": focal,
                "relation": "derived_from",
                "payload": {
                    "provenance": "human_verified",
                    "source_refs": [focal],
                    "visibility": "public",
                },
            }
        ],
    )

    lineage = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="lineage", direction="both", depth=3),
    )
    assert {edge["relation"] for edge in lineage["edges"]} <= {
        "evidence", "requires_evidence", "derived_from", "produces", "results_in",
        "generated_from", "completed_by", "performed_by", "supersedes", "links_to",
    }
    assert lineage["lineage_refs"] == sorted(lineage["lineage_refs"])
    assert lineage["meaningful"] is True

    compared = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=[focal, "boi:public:guide"],
            query_kind="compare",
            depth=1,
        ),
    )
    assert set(compared["groups"]) == {focal, "boi:public:guide"}
    assert set(compared["comparison"]) == {
        "common_relations", "common_node_refs", "unique_relations", "unique_node_refs",
    }
    assert compared["presentation"] == "table"

    tour = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="tour", depth=3),
    )
    assert [item["order"] for item in tour["tour_steps"]] == list(range(1, len(tour["tour_steps"]) + 1))


def test_graph_query_cache_uses_context_fingerprint_without_sharing_acl(
    v2_service: AgentV2Service,
    principal: Principal,
):
    plan = GraphQueryPlan(
        focal_entities=["boi:public:sop:manual"],
        query_kind="neighbors",
        depth=2,
        presentation="auto",
    )
    first = v2_service.knowledge.query(principal, plan)
    cached_rows = v2_service.store.list(
        "knowledge_graph_queries",
        employee_id=principal.employee_id,
        limit=20,
    )
    second = v2_service.knowledge.query(principal, plan)

    assert cached_rows
    assert cached_rows[0]["context_fingerprint"]
    assert first == second
    assert all("boi:private:100002" not in str(node.get("node_id")) for node in second["nodes"])


def test_graphify_adapter_imports_provenance_graph_without_changing_canonical_files(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    staging = v2_service.settings.runtime_root / "knowledge-adapters" / "graphify-test"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "api", "type": "service", "name": "BoI API", "path": "boi_api/app/main.py"},
                    {"id": "store", "type": "class", "name": "Agent Store", "path": "boi_api/app/v2/store.py"},
                ],
                "edges": [
                    {"source": "api", "target": "store", "relation": "depends_on", "provenance": "extracted"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    canonical = v2_service.settings.content_root / "public" / "guide.md"
    before = canonical.read_text(encoding="utf-8")
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="Graphify test export",
            source_kind="graphify",
            location=str(staging),
        ),
    )

    result = v2_service.knowledge.sync_source(admin, source["source_id"])
    job = result["job"]
    deadline = time.monotonic() + 3
    while job["status"] not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = v2_service.knowledge.source_job(admin, job["job_id"])

    assert job["status"] == "completed"
    assert job["stage"] == "import" and job["progress"] == 100
    assert job["attempt"] == 1
    assert job["manifest"]["validation_report"] == {
        "valid": True,
        "node_count": 2,
        "edge_count": 1,
        "canonical_changed": False,
    }
    graph = v2_service.store.ontology_neighbors(
        job["manifest"]["node_ids"][:1],
        depth=1,
        limit=10,
        employee_id=principal.employee_id,
        team_ids=principal.teams,
        include_all=True,
    )
    assert graph["edges"][0]["payload"]["provenance"] == "extracted"
    assert canonical.read_text(encoding="utf-8") == before
    assert v2_service.knowledge.source_job(admin, job["job_id"])["status"] == "completed"
    rolled_back = v2_service.knowledge.rollback_source_import(
        admin,
        source["source_id"],
        KnowledgeSourceRollbackRequest(user_confirmed=True, reason="격리 import rollback 검증"),
    )
    assert rolled_back["removed_nodes"] == 2
    assert v2_service.store.get("knowledge_source_manifests", source["source_id"]) is None


def test_openkb_adapter_creates_private_review_candidates_without_writing_okf(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    staging = v2_service.settings.runtime_root / "knowledge-adapters" / "openkb-test"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "manifest.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "id": "alarm-check",
                        "title": "Alarm 확인 순서 후보",
                        "summary": "Trend와 Raw Data의 시간 범위를 먼저 맞춥니다.",
                        "deterministic": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="OpenKB test manifest",
            source_kind="openkb",
            location=str(staging),
        ),
    )

    result = v2_service.knowledge.sync_source(admin, source["source_id"])
    job = result["job"]
    deadline = time.monotonic() + 3
    while job["status"] not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = v2_service.knowledge.source_job(admin, job["job_id"])
    manifest = job["manifest"]
    candidate = v2_service.store.get("knowledge_candidates", manifest["candidate_ids"][0])

    assert job["status"] == "completed"
    assert manifest["validation_report"]["canonical_changed"] is False
    assert manifest["validation_report"]["review_required"] is True
    assert candidate["visibility"] == "private"
    assert candidate["status"] == "proposed"
    assert candidate["provenance"] == "inferred"


def test_graphify_adapter_executes_cli_when_export_is_not_prebuilt(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    monkeypatch.setenv("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "1")
    monkeypatch.setattr("boi_api.app.v2.knowledge_system.shutil.which", lambda name: f"/tools/{name}")

    def fake_run(command, *, cwd, timeout_seconds):
        assert command[1:3] == ["extract", str(v2_service.settings.content_root)]
        assert "--code-only" in command and "--no-cluster" in command
        assert command[command.index("--out") + 1] == str(cwd)
        output = cwd / "graphify-out"
        output.mkdir(parents=True, exist_ok=True)
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "nodes": [
                        {"id": "service", "name": "BoI Service"},
                        {"id": "gateway", "name": "Gateway"},
                    ],
                    "links": [
                        {
                            "source": "service",
                            "target": "gateway",
                            "relation": "calls",
                            "confidence": "EXTRACTED",
                            "confidence_score": 1.0,
                            "source_file": "service.py",
                            "source_location": "L10",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(v2_service.knowledge, "_run_adapter_command", fake_run)
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="Graphify live CLI",
            source_kind="graphify",
            location=str(v2_service.settings.content_root),
        ),
    )
    job = v2_service.knowledge.sync_source(admin, source["source_id"])["job"]
    deadline = time.monotonic() + 3
    while job["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = v2_service.knowledge.source_job(admin, job["job_id"])
    assert job["status"] == "completed"
    assert job["manifest"]["validation_report"]["node_count"] == 2
    assert job["manifest"]["validation_report"]["edge_count"] == 1
    imported = v2_service.store.ontology_neighbors(
        [job["manifest"]["node_ids"][0]],
        depth=1,
        limit=10,
        employee_id=admin.employee_id,
        team_ids=admin.teams,
        include_all=True,
    )
    imported_edge = imported["edges"][0]
    assert imported_edge["payload"]["provenance"] == "extracted"
    assert imported_edge["payload"]["confidence"] == 1.0
    assert job["checkpoint"]["stage"] == "validate"


def test_openkb_adapter_executes_cli_and_excludes_navigation_pages(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    monkeypatch.setenv("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "1")
    monkeypatch.setattr("boi_api.app.v2.knowledge_system.shutil.which", lambda name: f"/tools/{name}")
    source_file = v2_service.settings.runtime_root / "knowledge-adapters" / "input.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"fixture")

    def fake_run(command, *, cwd, timeout_seconds, input_text=None, extra_env=None):
        if "init" in command:
            assert "--model" in command
            assert "--language" in command
            assert input_text == "\n"
        if "add" in command:
            assert extra_env and extra_env["BOI_OPENKB_COMPAT_GATEWAY"] == "1"
            wiki = cwd / "wiki"
            (wiki / "concepts").mkdir(parents=True, exist_ok=True)
            (wiki / "index.md").write_text("# Navigation", encoding="utf-8")
            (wiki / "log.md").write_text("# Log", encoding="utf-8")
            (wiki / "concepts" / "alarm.md").write_text("# Alarm 판단\n\nTrend 범위를 먼저 맞춥니다.", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(v2_service.knowledge, "_run_adapter_command", fake_run)
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="OpenKB live CLI",
            source_kind="openkb",
            location=str(source_file),
            adapter_config={"model": "openai/local-fixture", "language": "ko"},
        ),
    )
    job = v2_service.knowledge.sync_source(admin, source["source_id"])["job"]
    deadline = time.monotonic() + 3
    while job["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = v2_service.knowledge.source_job(admin, job["job_id"])
    assert job["status"] == "completed"
    candidates = [v2_service.store.get("knowledge_candidates", item) for item in job["manifest"]["candidate_ids"]]
    assert [item["title"] for item in candidates] == ["Alarm 판단"]
    assert all(item["review_state"] == "review_required" for item in candidates)


def test_knowledge_source_job_is_async_and_can_be_cancelled(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    staging = v2_service.settings.runtime_root / "knowledge-adapters" / "cancel-test"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "graph.json").write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(name="Cancelable adapter", source_kind="graphify", location=str(staging)),
    )
    entered = threading.Event()

    def slow_import(_principal, _source, *, job_id, started, timeout_seconds):
        entered.set()
        while True:
            v2_service.knowledge._assert_adapter_job_active(job_id, started, timeout_seconds)
            time.sleep(0.01)

    monkeypatch.setattr(v2_service.knowledge, "_import_graphify", slow_import)
    started = time.perf_counter()
    queued = v2_service.knowledge.sync_source(admin, source["source_id"])["job"]

    assert time.perf_counter() - started < 0.2
    assert queued["status"] in {"queued", "running"}
    assert entered.wait(1)
    v2_service.knowledge.cancel_source_job(admin, queued["job_id"])
    deadline = time.monotonic() + 2
    job = v2_service.knowledge.source_job(admin, queued["job_id"])
    while job["status"] != "cancelled" and time.monotonic() < deadline:
        time.sleep(0.01)
        job = v2_service.knowledge.source_job(admin, queued["job_id"])

    assert job["status"] == "cancelled"


def test_failed_adapter_job_retries_from_the_durable_queue(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    staging = v2_service.settings.runtime_root / "knowledge-adapters" / "retry-test"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "graph.json").write_text('{"nodes":[{"id":"retry","name":"Retry node"}],"edges":[]}', encoding="utf-8")
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(name="Retry adapter", source_kind="graphify", location=str(staging)),
    )
    job_id = "source-job-retry"
    v2_service.store.put(
        "knowledge_source_jobs",
        job_id,
        {
            "job_id": job_id,
            "source_id": source["source_id"],
            "employee_id": admin.employee_id,
            "status": "failed",
            "stage": "failed",
            "attempt": 1,
            "retryable": True,
            "created_at": now_iso(),
        },
    )
    retried = v2_service.knowledge.retry_source_job(admin, job_id)
    deadline = time.monotonic() + 3
    while retried["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        retried = v2_service.knowledge.source_job(admin, job_id)
    assert retried["status"] == "completed", retried.get("error")
    assert retried["attempt"] == 2


def test_adapter_subprocess_timeout_is_recorded_without_escaping_the_worker(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="Timeout adapter",
            source_kind="openkb",
            location=str(v2_service.settings.runtime_root / "knowledge-adapters" / "timeout.txt"),
            adapter_config={"model": "openai/local-fixture"},
        ),
    )
    job_id = "source-job-timeout"
    v2_service.store.put(
        "knowledge_source_jobs",
        job_id,
        {
            "job_id": job_id,
            "source_id": source["source_id"],
            "employee_id": admin.employee_id,
            "status": "queued",
            "attempt": 1,
        },
    )
    monkeypatch.setattr(
        v2_service.knowledge,
        "_import_openkb",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(["openkb", "init"], 60)
        ),
    )

    v2_service.knowledge._run_adapter_job(admin, source, job_id)

    failed = v2_service.knowledge.source_job(admin, job_id)
    assert failed["status"] == "failed"
    assert failed["retryable"] is True
    assert "timed out" in failed["error"]


def test_adapter_validation_failure_cannot_be_reported_as_completed(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(
            name="Empty adapter result",
            source_kind="openkb",
            location=str(v2_service.settings.runtime_root / "knowledge-adapters" / "empty.txt"),
            adapter_config={"model": "openai/local-fixture"},
        ),
    )
    job_id = "source-job-empty-result"
    v2_service.store.put(
        "knowledge_source_jobs",
        job_id,
        {
            "job_id": job_id,
            "source_id": source["source_id"],
            "employee_id": admin.employee_id,
            "status": "queued",
            "attempt": 1,
        },
    )
    monkeypatch.setattr(
        v2_service.knowledge,
        "_import_openkb",
        lambda *_args, **_kwargs: {
            "source_revision": "empty",
            "validation_report": {"valid": False, "candidate_count": 0},
        },
    )

    v2_service.knowledge._run_adapter_job(admin, source, job_id)

    failed = v2_service.knowledge.source_job(admin, job_id)
    assert failed["status"] == "failed"
    assert failed["error"] == "adapter_validation_failed"


def test_adapter_running_job_is_requeued_after_restart(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    staging = v2_service.settings.runtime_root / "knowledge-adapters" / "restart-test"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "graph.json").write_text('{"nodes":[{"id":"restart","name":"Restart node"}],"edges":[]}', encoding="utf-8")
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(name="Restart adapter", source_kind="graphify", location=str(staging)),
    )
    job_id = "source-job-restart"
    v2_service.store.put(
        "knowledge_source_jobs",
        job_id,
        {
            "job_id": job_id,
            "source_id": source["source_id"],
            "employee_id": admin.employee_id,
            "status": "running",
            "stage": "extract",
            "attempt": 1,
            "created_at": now_iso(),
        },
    )
    assert v2_service.knowledge._resume_adapter_jobs() is True
    v2_service.knowledge._ensure_adapter_worker()
    recovered = v2_service.knowledge.source_job(admin, job_id)
    assert recovered["status"] in {"queued", "running", "completed"}
    assert recovered["recovered_after_restart"] is True
    v2_service.knowledge._adapter_worker_event.set()
    deadline = time.monotonic() + 3
    while recovered["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        recovered = v2_service.knowledge.source_job(admin, job_id)
    assert recovered["status"] == "completed"


def test_responsibility_graph_does_not_expand_through_a_shared_team_to_other_people(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    result = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=[f"person:{principal.employee_id}"],
            query_kind="responsibility",
            depth=2,
            presentation="table",
        ),
    )
    assert result["edges"]
    assert all(
        f"person:{principal.employee_id}" in {edge["source_id"], edge["target_id"]}
        for edge in result["edges"]
    )
    assert not any(
        node["node_type"] == "person" and node["node_id"] != f"person:{principal.employee_id}"
        for node in result["nodes"]
    )


def test_graph_path_and_temporal_filter_are_parameterized_and_deterministic(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    neighbors = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:public:sop:manual",
        depth=2,
        limit=50,
    )
    target = next(edge["target_id"] for edge in neighbors["edges"] if edge["relation"] == "has_task")
    path = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["boi:public:sop:manual"],
            target_entities=[target],
            query_kind="path",
            depth=3,
            presentation="auto",
        ),
    )
    assert path["path_refs"] == ["boi:public:sop:manual", target]

    v2_service.store.upsert_ontology(
        [
            {"node_id": "runtime:old", "node_type": "runtime", "payload": {"title": "이전 실행", "visibility": "public", "observed_at": "2025-01-01T00:00:00+00:00"}},
            {"node_id": "runtime:new", "node_type": "runtime", "payload": {"title": "최근 실행", "visibility": "public", "observed_at": "2026-07-12T00:00:00+00:00"}},
        ],
        [{"edge_id": "edge:runtime-time", "source_id": "runtime:old", "target_id": "runtime:new", "relation": "next", "payload": {"provenance": "extracted", "visibility": "public"}}],
    )
    timeline = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["runtime:old", "runtime:new"],
            query_kind="timeline",
            depth=1,
            time_from="2026-01-01T00:00:00+00:00",
            time_to="2026-12-31T23:59:59+00:00",
        ),
    )
    assert [node["node_id"] for node in timeline["nodes"]] == ["runtime:new"]
    assert timeline["presentation"] == "timeline"
    assert [item["node_ref"] for item in timeline["timeline"]] == ["runtime:new"]
    assert timeline["timeline"][0]["occurred_at"] == "2026-07-12T00:00:00+00:00"


def test_graph_explorer_node_and_filters_are_acl_checked_and_parameterized(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.knowledge.compile_graph(principal)
    base = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:public:sop:manual",
        depth=2,
        limit=80,
    )
    assert base["nodes"] and base["edges"]
    relation = str(base["edges"][0]["relation"])
    provenance = str((base["edges"][0].get("payload") or {}).get("provenance") or "")
    filtered = v2_service.knowledge.explore(
        principal,
        view="neighbors",
        source_ref="boi:public:sop:manual",
        depth=4,
        limit=80,
        relation_kinds=[relation],
        provenance=[provenance],
    )
    assert filtered["edges"]
    assert {item["relation"] for item in filtered["edges"]} == {relation}
    assert {
        str((item.get("payload") or {}).get("provenance") or "")
        for item in filtered["edges"]
    } == {provenance}
    node = v2_service.knowledge.node(principal, "boi:public:sop:manual")
    assert node["node"]["node_id"] == "boi:public:sop:manual"
    assert node["relation_count"] == len(node["edges"])


def test_graph_node_api_returns_the_same_acl_visible_node(v2_service: AgentV2Service):
    app = FastAPI()
    app.include_router(build_agent_v2_router(v2_service))
    v2_service.knowledge.compile_graph(
        Principal(
            employee_id="100001",
            display_name="Test User",
            teams=["aix-tf"],
            roles=["boi.viewer"],
            auth_source="test",
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/v2/knowledge-graph/nodes/boi:public:sop:manual")
    assert response.status_code == 200
    assert response.json()["node"]["node_id"] == "boi:public:sop:manual"


def test_harness_never_reports_full_acceptance_when_dependencies_are_missing(v2_service: AgentV2Service, principal: Principal):
    result = v2_service.harness_acceptance(principal)
    assert result["core_accepted"] is True
    assert result["full_accepted"] is False
    assert result["full_checks"]["postgres_pgvector_ready"] is False
    assert result["full_checks"]["real_embedding_ready"] is False
    assert result["full_checks"]["deep_worker_ready"] is False


def test_postgres_registry_includes_all_harness_improvement_collections():
    from boi_api.app.v2.store import PostgresAgentV2Store

    assert {
        "harness_failure_patterns",
        "harness_shadow_runs",
        "harness_versions",
        "harness_active_versions",
        "harness_release_audits",
    } <= set(PostgresAgentV2Store.COLLECTION_TABLES)


def test_postgres_registry_includes_graph_query_cache_collection():
    from boi_api.app.v2.store import PostgresAgentV2Store

    assert PostgresAgentV2Store.COLLECTION_TABLES["knowledge_graph_queries"] == "knowledge_graph_queries"


def _record_recurrent_harness_failures(
    service: AgentV2Service,
    principal: Principal,
    *,
    context: WorkContextPack,
    prefix: str,
) -> list[str]:
    result = HarnessResult(
        harness_id="context.work",
        version=service.harnesses.definition("context.work").version,
        status="blocked",
        checks=[
            HarnessCheck(
                check_id="context.evidence",
                label="근거",
                status="blocked",
                message="검증된 근거가 없습니다.",
            )
        ],
        blockers=["검증된 근거가 없습니다."],
        evaluated_facts={"evidence_count": 0},
    )
    failure_ids: list[str] = []
    for index in range(3):
        work_run_id = f"{prefix}-failure-{index + 1}"
        failure_ids.extend(
            service.learning._record_harness_failures(
                principal=principal,
                work_run={
                    "work_run_id": work_run_id,
                    "artifact_refs": [],
                    "checkpoint_ids": [f"checkpoint-{work_run_id}"],
                    "contract_revisions": {
                        "capability_catalog": service.registry.version,
                        "planner_schema": "semantic-plan/v3",
                    },
                },
                context=context,
                results=[result],
                phase="preflight",
            )
        )
    return failure_ids


def _harness_hypothesis_fields(
    service: AgentV2Service,
    *,
    preservation_run_ids: list[str],
) -> dict[str, Any]:
    return {
        "predicted_impact": {"grounded_recall": 0.0},
        "at_risk_regressions": ["existing_grounded_read"],
        "preservation_run_ids": preservation_run_ids,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "rollback_target": service.harnesses.definition("context.work").version,
    }


def test_harness_candidate_cannot_change_immutable_safety_boundaries(
    v2_service: AgentV2Service,
    principal: Principal,
):
    failure_id = "hfailure-immutable"
    v2_service.store.put(
        "harness_failure_records",
        failure_id,
        {
            "failure_record_id": failure_id,
            "employee_id": principal.employee_id,
            "harness_id": "context.work",
            "causal_agent_stage": "context.evidence",
            "status": "open",
        },
    )

    with pytest.raises(Exception) as caught:
        v2_service.learning.create_harness_candidate(
            principal,
            HarnessCandidateCreateRequest(
                harness_id="context.work",
                failure_record_ids=[failure_id, failure_id, failure_id],
                changes={"acl": {"allow_all": True}},
                rationale="반복 실패를 해결하려는 후보지만 권한 경계는 바꿀 수 없습니다.",
                **_harness_hypothesis_fields(
                    v2_service,
                    preservation_run_ids=["not-evaluated"],
                ),
            ),
        )

    assert getattr(caught.value, "status_code", None) == 400
    assert "acl" in caught.value.detail["immutable"]


def test_harness_candidate_rejects_a_surface_without_a_runtime_applier(
    v2_service: AgentV2Service,
    principal: Principal,
):
    failure_id = "hfailure-inert-surface"
    v2_service.store.put(
        "harness_failure_records",
        failure_id,
        {
            "failure_record_id": failure_id,
            "employee_id": principal.employee_id,
            "harness_id": "context.work",
            "causal_agent_stage": "context.evidence",
            "status": "open",
        },
    )

    with pytest.raises(Exception) as caught:
        v2_service.learning.create_harness_candidate(
            principal,
            HarnessCandidateCreateRequest(
                harness_id="context.work",
                failure_record_ids=[failure_id, failure_id, failure_id],
                changes={"planner_instruction": "항상 다른 기능으로 바꾼다"},
                rationale="실행기가 없는 변경은 검토 완료처럼 저장하지 않아야 합니다.",
                **_harness_hypothesis_fields(
                    v2_service,
                    preservation_run_ids=["not-evaluated"],
                ),
            ),
        )

    assert getattr(caught.value, "status_code", None) == 400
    assert caught.value.detail["unsupported"] == ["planner_instruction"]


def test_active_retrieval_harness_policy_is_consumed_and_pinned_by_the_turn(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    model_profile = v2_service.learning.model_profile
    v2_service.store.put(
        "harness_active_versions",
        f"context.work:{model_profile}",
        {
            "harness_version_id": "hversion-runtime-policy",
            "harness_id": "context.work",
            "model_profile": model_profile,
            "changes": {"retrieval_policy": {"authority_weight": 1.4}},
        },
    )
    observed: list[dict[str, float]] = []
    original_search = v2_service.search.search

    def recording_search(*args: Any, **kwargs: Any):
        observed.append(dict(kwargs.get("ranking_policy") or {}))
        return original_search(*args, **kwargs)

    monkeypatch.setattr(v2_service.search, "search", recording_search)
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="BoI Wiki 운영 가이드의 검토 기준을 설명해줘",
            capability_id="knowledge.search",
        ),
    )

    assert observed and all(item.get("authority_weight") == 1.4 for item in observed)
    work_run = v2_service.learning.get_run(principal, response.work_run_id)
    binding = next(
        item for item in work_run["harness_bindings"] if item["harness_id"] == "context.work"
    )
    assert binding["version"] == "hversion-runtime-policy"
    assert binding["active_changes"]["retrieval_policy"]["authority_weight"] == 1.4


def test_active_context_playbook_policy_reorders_only_existing_reviewed_items(
    v2_service: AgentV2Service,
    principal: Principal,
):
    first = v2_service.learning.create_context_playbook_item(
        principal,
        ContextPlaybookCreateRequest(
            description="현재 Task와 직접 연결된 검토 근거를 먼저 확인합니다.",
            capability_ids=["knowledge.search"],
            source_refs=["boi:public:boi-wiki-manual:guide:final-operator-guide"],
        ),
    )
    second = v2_service.learning.create_context_playbook_item(
        principal,
        ContextPlaybookCreateRequest(
            description="최근 완료 기록의 근거와 현재 판단 조건을 비교합니다.",
            capability_ids=["knowledge.search"],
            source_refs=["boi:public:boi-wiki-manual:agent:using-boi-agent"],
        ),
    )
    for item in (first, second):
        v2_service.learning.patch_context_playbook_item(
            principal,
            item["item_id"],
            ContextPlaybookPatchRequest(
                expected_revision=1,
                status="active",
                review_note="격리된 실행에서 근거 범위와 적용 조건을 확인했습니다.",
            ),
        )
    model_profile = v2_service.learning.model_profile
    v2_service.store.put(
        "harness_active_versions",
        f"context.work:{model_profile}",
        {
            "harness_version_id": "hversion-context-playbook-policy",
            "harness_id": "context.work",
            "model_profile": model_profile,
            "changes": {
                "context_playbook": {
                    "item_ids": [second["item_id"]],
                    "order": "prepend",
                    "max_items": 1,
                }
            },
        },
    )
    context = v2_service.learning.contexts.compile(
        principal=principal,
        definition=v2_service.registry.get("knowledge.search"),
        goal="현재 판단 근거 확인",
        page_ref="",
        task_ref="",
        task_mode=TaskMode.copilot,
        task={},
        evidence=[],
        session={},
        source_set={},
        external_ai_summary="",
        external_refs=[],
        model_profile=model_profile,
    )

    assert context.manifest["context_playbook_item_ids"] == [second["item_id"]]


def test_harness_candidate_requires_three_distinct_work_runs(
    v2_service: AgentV2Service,
    principal: Principal,
):
    context = WorkContextPack(
        context_id="context-harness-distinct-runs",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="반복 실패 원인을 검토한다",
    )
    failure_ids = _record_recurrent_harness_failures(
        v2_service,
        principal,
        context=context,
        prefix="distinct-run",
    )
    duplicate = v2_service.store.get("harness_failure_records", failure_ids[-1])
    duplicate["work_run_id"] = "distinct-run-failure-1"
    v2_service.store.put("harness_failure_records", failure_ids[-1], duplicate)
    preservation_run_id = "work-run-distinct-preservation"
    v2_service.store.put(
        "work_runs",
        preservation_run_id,
        {"work_run_id": preservation_run_id, "employee_id": principal.employee_id, "status": "completed"},
    )

    with pytest.raises(Exception) as caught:
        v2_service.learning.create_harness_candidate(
            principal,
            HarnessCandidateCreateRequest(
                harness_id="context.work",
                failure_record_ids=failure_ids,
                model_profile=v2_service.learning.model_profile,
                changes={"retrieval_policy": {"authority_weight": 1.1}},
                rationale="서로 다른 실행에서 같은 실패가 확인된 경우에만 개선 후보를 생성합니다.",
                **_harness_hypothesis_fields(
                    v2_service,
                    preservation_run_ids=[preservation_run_id],
                ),
            ),
        )

    assert getattr(caught.value, "status_code", None) == 409
    assert caught.value.detail["code"] == "harness_candidate_recurrence_required"


def test_harness_candidate_requires_held_out_and_human_review_before_any_production_change(
    v2_service: AgentV2Service,
    principal: Principal,
):
    baseline_context = WorkContextPack(
        context_id="context-harness-held-out",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="기존 검증 동작을 보존한다",
        evidence_refs=[
            EvidenceRef(
                evidence_id="boi:public:guide",
                kind="boi",
                title="검증된 운영 가이드",
                summary="기존 검증 동작을 보존하기 위한 reviewed 근거입니다.",
                url="/docs/boi:public:guide",
                authority="reviewed",
            )
        ],
        context_manifest=ContextManifest(
            selected_refs=["boi:public:guide"],
            chunk_refs=["chunk:boi:public:guide:1"],
            source_revision="fixture-held-out-v1",
            provenance={
                "boi:public:guide": {
                    "source_ref": "boi:public:guide",
                    "revision": "fixture-held-out-v1",
                }
            },
        ),
    )
    v2_service.store.put(
        "contexts",
        baseline_context.context_id,
        baseline_context.model_dump(mode="json"),
    )
    baseline_run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-run-harness-held-out",
        session={"session_id": "session-harness-held-out"},
        context=baseline_context,
        intent=WorkIntent(
            goal="기존 검증 동작을 보존한다",
            resolved_goal="기존 검증 동작을 보존한다",
            operation=WorkOperation.validate,
            harness_ids=["context.work"],
        ),
        goal_plan_id="goal-harness-held-out",
        catalog_revision=v2_service.registry.version,
    )
    baseline_run, _ = v2_service.learning.finish_run(
        principal=principal,
        work_run=baseline_run,
        context=baseline_context,
        intent=WorkIntent(
            goal="기존 검증 동작을 보존한다",
            resolved_goal="기존 검증 동작을 보존한다",
            operation=WorkOperation.validate,
            harness_ids=["context.work"],
        ),
        response_status="completed",
        answer_summary="기존 검증 동작이 완료되었습니다.",
        artifacts=[{"artifact_id": "artifact-held-out", "artifact_type": "data_table"}],
        evidence_refs=["boi:public:guide"],
    )
    assert baseline_run["status"] == "completed"

    failure_ids = _record_recurrent_harness_failures(
        v2_service,
        principal,
        context=baseline_context,
        prefix="held-out",
    )
    candidate = v2_service.learning.create_harness_candidate(
        principal,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=failure_ids,
            model_profile=v2_service.learning.model_profile,
            changes={"retrieval_policy": {"authority_weight": 1.2}},
            rationale="권위 있는 업무 근거가 반복적으로 누락되는 실패를 줄이기 위한 제한된 후보입니다.",
            **_harness_hypothesis_fields(
                v2_service,
                preservation_run_ids=[baseline_run["work_run_id"]],
            ),
        ),
    )

    assert candidate["predicted_impact"] == {"grounded_recall": 0.0}
    assert candidate["at_risk_regressions"] == ["existing_grounded_read"]
    assert candidate["preservation_run_ids"] == [baseline_run["work_run_id"]]
    assert candidate["rollback_target"] == v2_service.harnesses.definition("context.work").version
    assert datetime.fromisoformat(candidate["expires_at"]) > datetime.now(timezone.utc)

    rejected_shadow = v2_service.learning.shadow_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateShadowRequest(fixture_revision="fixture-held-out-v1"),
    )
    rejected = v2_service.learning.evaluate_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateEvaluateRequest(
            shadow_run_id=rejected_shadow["shadow_run"]["shadow_run_id"],
            held_in={"passed": True},
            held_out={"passed": False, "regressions": 1},
            adversarial={"passed": True, "unauthorized_mutations": 0},
            fixture_revision="fixture-held-out-v1",
        ),
    )
    assert rejected["candidate"]["status"] == "rejected"
    assert rejected["candidate"]["production_changed"] is False
    rejected_record = v2_service.store.get("harness_candidates", candidate["candidate_id"])
    assert rejected_record["status"] == "rejected"
    assert rejected_record["latest_eval_id"] == rejected["evaluation"]["eval_id"]
    with pytest.raises(Exception) as rejected_release:
        v2_service.learning.release_harness_version(
            principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]}),
            candidate["candidate_id"],
            HarnessVersionReleaseRequest(
                expected_version_id="not-approved",
                note="회귀가 확인된 후보는 배포할 수 없어야 합니다.",
                user_confirmed=True,
            ),
        )
    assert getattr(rejected_release.value, "status_code", None) == 404
    assert rejected_release.value.detail == "배포할 Harness 버전을 찾을 수 없습니다."

    candidate = v2_service.learning.create_harness_candidate(
        principal,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=failure_ids,
            model_profile=v2_service.learning.model_profile,
            changes={
                "retrieval_policy": {"authority_weight": 1.1},
                    "loop_policy": {
                    "max_iterations": 3,
                    "max_no_progress": 2,
                    "max_tool_loops": 4,
                },
            },
            rationale="같은 실패군을 대상으로 held-out 회귀 없이 개선되는지 다시 검증하는 후보입니다.",
            **_harness_hypothesis_fields(
                v2_service,
                preservation_run_ids=[baseline_run["work_run_id"]],
            ),
        ),
    )
    qualified_shadow = v2_service.learning.shadow_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateShadowRequest(fixture_revision="fixture-held-out-v2"),
    )
    qualified = v2_service.learning.evaluate_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateEvaluateRequest(
            shadow_run_id=qualified_shadow["shadow_run"]["shadow_run_id"],
            held_in={"passed": True},
            held_out={"passed": True, "regressions": 0},
            adversarial={"passed": True, "unauthorized_mutations": 0},
            long_term={"passed": True, "regressions": 0, "knowledge_health": "stable"},
            fixture_revision="fixture-held-out-v2",
        ),
    )
    assert qualified["candidate"]["status"] == "review_required"
    assert qualified["candidate"]["production_changed"] is False
    assert qualified["evaluation"]["server_observations"]["held_out_work_run_ids"] == [
        baseline_run["work_run_id"]
    ]
    reviewed = v2_service.learning.review_harness_candidate(
        principal,
        candidate["candidate_id"],
        HarnessCandidateReviewRequest(
            decision="approve_for_release",
            expected_eval_id=qualified["evaluation"]["eval_id"],
            note="회귀와 안전 기준을 통과했으므로 수동 배포 검토 대상으로 승인합니다.",
        ),
    )
    version = v2_service.store.get("harness_versions", reviewed["harness_version_id"])
    assert reviewed["production_changed"] is False
    assert version["status"] == "approved_not_deployed"
    assert version["production_changed"] is False

    release_principal = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    rehearsal = v2_service.learning.release_harness_version(
        release_principal,
        candidate["candidate_id"],
        HarnessVersionReleaseRequest(
            expected_version_id=reviewed["harness_version_id"],
            note="운영 반영 전 rollback 대상과 활성 binding을 연습합니다.",
            user_confirmed=True,
            rehearsal=True,
        ),
    )
    assert rehearsal["production_changed"] is False
    assert v2_service.store.list("harness_active_versions", limit=10) == []

    released = v2_service.learning.release_harness_version(
        release_principal,
        candidate["candidate_id"],
        HarnessVersionReleaseRequest(
            expected_version_id=reviewed["harness_version_id"],
            note="검증된 후보를 운영 binding에 반영합니다.",
            user_confirmed=True,
        ),
    )
    assert released["production_changed"] is True
    binding = v2_service.learning.effective_harness_bindings(["context.work"])[0]
    assert binding["version"] == reviewed["harness_version_id"]
    assert binding["release_state"] == "active_reviewed_version"
    assert binding["active_changes"]["loop_policy"]["max_iterations"] == 3

    pinned_run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-run-pinned-harness",
        session={"session_id": "session-pinned-harness"},
        context=WorkContextPack(
            context_id="context-pinned-harness",
            employee_id=principal.employee_id,
            capability_id="knowledge.search",
            goal="검증된 운영 기준을 이해한다",
        ),
        intent=WorkIntent(
            goal="검증된 운영 기준을 이해한다",
            resolved_goal="검증된 운영 기준을 이해한다",
            operation=WorkOperation.understand,
            harness_ids=["context.work"],
        ),
        goal_plan_id="goal-plan-pinned-harness",
        catalog_revision=v2_service.registry.version,
    )
    assert pinned_run["loop"]["max_iterations"] == 1
    assert pinned_run["loop"]["policy"]["kind"] == "turn"
    assert pinned_run["loop"]["max_tool_loops"] == 1
    assert pinned_run["loop"]["max_no_progress"] == 2
    assert pinned_run["harness_bindings"][0]["version"] == reviewed["harness_version_id"]

    rolled_back = v2_service.learning.rollback_harness_version(
        release_principal,
        candidate["candidate_id"],
        HarnessVersionRollbackRequest(
            note="운영 rehearsal를 마치고 내장 기준 버전으로 되돌립니다.",
            user_confirmed=True,
        ),
    )
    assert rolled_back["production_changed"] is True
    assert v2_service.store.list("harness_active_versions", limit=10) == []
    assert pinned_run["harness_bindings"][0]["version"] == reviewed["harness_version_id"]
    restored_binding = v2_service.learning.effective_harness_bindings(["context.work"])[0]
    assert restored_binding["version"] == v2_service.learning.harnesses.definition("context.work").version
    assert restored_binding["release_state"] == "catalog_version"


def test_blocked_harness_creates_causal_failure_and_negative_result(
    v2_service: AgentV2Service,
    principal: Principal,
):
    context = WorkContextPack(
        context_id="ctx-causal-failure",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="현재 문서의 근거를 확인한다",
    )
    run = {
        "work_run_id": "work-run-causal-failure",
        "artifact_refs": [],
    }
    result = HarnessResult(
        harness_id="context.work",
        version="1.1",
        status="blocked",
        checks=[
            HarnessCheck(
                check_id="context.evidence",
                label="사용할 근거",
                status="blocked",
                message="검증된 근거가 없습니다.",
            )
        ],
        blockers=["검증된 근거가 없습니다."],
    )

    failure_ids = v2_service.learning._record_harness_failures(
        principal=principal,
        work_run=run,
        context=context,
        results=[result],
        phase="preflight",
    )

    assert len(failure_ids) == 1
    failure = v2_service.store.get("harness_failure_records", failure_ids[0])
    assert failure["terminal_verifier_cause"] == "검증된 근거가 없습니다."
    assert failure["causal_agent_stage"] == "context.evidence"
    assert failure["model_profile"]
    negatives = v2_service.store.list("negative_results", limit=10)
    assert any(item["failure_record_id"] == failure_ids[0] for item in negatives)


def test_same_causal_harness_failure_is_grouped_as_a_recurrent_pattern(
    v2_service: AgentV2Service,
    principal: Principal,
):
    context = WorkContextPack(
        context_id="ctx-recurrent-failure",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="검증된 업무 근거를 찾는다",
    )
    result = HarnessResult(
        harness_id="context.work",
        version="1.1",
        status="blocked",
        checks=[HarnessCheck(check_id="context.evidence", label="근거", status="blocked", message="근거 없음")],
        blockers=["검증된 근거가 없습니다."],
    )
    for suffix in ("one", "two", "three"):
        v2_service.learning._record_harness_failures(
            principal=principal,
            work_run={"work_run_id": f"work-run-{suffix}", "artifact_refs": []},
            context=context,
            results=[result],
            phase="preflight",
        )
    patterns = v2_service.learning.list_harness_failure_patterns(principal)["items"]
    assert len(patterns) == 1
    assert patterns[0]["occurrence_count"] == 3
    assert patterns[0]["candidate_eligible"] is True
    assert set(patterns[0]["work_run_ids"]) == {
        "work-run-one",
        "work-run-two",
        "work-run-three",
    }


def test_context_playbook_is_deduplicated_versioned_and_model_scoped(
    v2_service: AgentV2Service,
    principal: Principal,
):
    request = ContextPlaybookCreateRequest(
        description="공식 운영 가이드를 먼저 확인하고 현재 Task의 근거와 충돌 여부를 비교합니다.",
        capability_ids=["knowledge.search"],
        model_profiles=["gemma-local"],
        source_refs=["boi:public:boi-wiki-manual:guide:final-operator-guide"],
    )
    item = v2_service.learning.create_context_playbook_item(principal, request)
    with pytest.raises(Exception) as caught:
        v2_service.learning.create_context_playbook_item(principal, request)
    assert getattr(caught.value, "status_code", None) == 409
    active = v2_service.learning.patch_context_playbook_item(
        principal,
        item["item_id"],
        ContextPlaybookPatchRequest(
            expected_revision=1,
            status="active",
            review_note="개인 실행에서 검증된 맥락 항목으로 활성화합니다.",
        ),
    )
    assert active["revision"] == 2
    definition = v2_service.registry.get("knowledge.search")
    included = v2_service.learning.contexts.compile(
        principal=principal,
        definition=definition,
        goal="운영 기준 확인",
        page_ref="",
        task_ref="",
        task_mode=TaskMode.copilot,
        task={},
        evidence=[],
        session={},
        source_set={},
        external_ai_summary="",
        external_refs=[],
        model_profile="gemma-local",
    )
    excluded = v2_service.learning.contexts.compile(
        principal=principal,
        definition=definition,
        goal="운영 기준 확인",
        page_ref="",
        task_ref="",
        task_mode=TaskMode.copilot,
        task={},
        evidence=[],
        session={},
        source_set={},
        external_ai_summary="",
        external_refs=[],
        model_profile="another-model",
    )
    assert included.manifest["context_playbook_item_ids"] == [item["item_id"]]
    assert excluded.manifest["context_playbook_item_ids"] == []


def test_context_manifest_tracks_item_budget_use_and_outcome_contribution(
    v2_service: AgentV2Service,
    principal: Principal,
):
    evidence = [
        EvidenceRef(
            evidence_id=f"boi:public:context-budget-{index}",
            kind="boi",
            title=f"검증 근거 {index}",
            summary=("근거 본문 " * 900) + str(index),
            source="wiki",
            authority="reviewed",
            metadata={
                "revision": f"revision-{index}",
                "best_chunk": {"chunk_id": f"chunk-{index}", "text": "상세 근거 " * 900},
            },
        )
        for index in range(3)
    ]
    context = v2_service.learning.contexts.compile(
        principal=principal,
        definition=v2_service.registry.get("knowledge.search"),
        goal="가용 문맥 전체에서 직접 근거를 설명한다",
        page_ref="",
        task_ref="",
        task_mode=TaskMode.copilot,
        task={},
        evidence=evidence,
        session={},
        source_set={},
        external_ai_summary="검토자가 남긴 요약을 원형 그대로 유지합니다.",
        external_refs=["artifact:complete-source-reference"],
        context_token_budget=50_000,
    )
    v2_service.store.put("contexts", context.context_id, context.model_dump(mode="json"))

    assert context.context_manifest is not None
    assert context.context_manifest.token_cost_total <= context.context_manifest.token_budget
    assert all(item.selected for item in context.context_manifest.items)
    assert context.context_manifest.selected_refs == [item.evidence_id for item in evidence]
    assert "compress" not in context.context_manifest.policies
    assert context.evidence_refs[0].summary == evidence[0].summary
    assert context.evidence_refs[0].metadata["best_chunk"]["text"] == evidence[0].metadata["best_chunk"]["text"]
    assert context.external_ai_summary == "검토자가 남긴 요약을 원형 그대로 유지합니다."
    assert context.context_manifest.external_refs == ["artifact:complete-source-reference"]

    intent = WorkIntent(
        goal="가용 문맥 전체에서 직접 근거를 설명한다",
        resolved_goal="가용 문맥 전체에서 직접 근거를 설명한다",
        operation=WorkOperation.understand,
        harness_ids=["context.work"],
    )
    run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-context-budget",
        session={"session_id": "session-context-budget"},
        context=context,
        intent=intent,
        goal_plan_id="goal-context-budget",
        catalog_revision=v2_service.registry.version,
    )
    stored_run, _ = v2_service.learning.finish_run(
        principal=principal,
        work_run=run,
        context=context,
        intent=intent,
        response_status="completed",
        answer_summary="첫 번째 검증 근거가 요청을 직접 뒷받침합니다.",
        artifacts=[],
        evidence_refs=[evidence[0].evidence_id],
    )
    stored_context = WorkContextPack.model_validate(
        v2_service.store.get("contexts", context.context_id)
    )
    first_item = next(
        item
        for item in stored_context.context_manifest.items
        if item.item_ref == evidence[0].evidence_id
    )

    assert stored_run["context_usage"]["used_item_count"] == 1
    assert first_item.used is True
    assert first_item.outcome_contribution == "answer"


def test_context_capacity_excludes_whole_ranked_items_without_lossy_truncation(
    v2_service: AgentV2Service,
    principal: Principal,
):
    compact_evidence = EvidenceRef(
        evidence_id="boi:public:capacity-small",
        kind="boi",
        title="짧은 직접 근거",
        summary="짧은 근거 본문 " * 30,
        source="wiki",
        authority="reviewed",
        metadata={"best_chunk": {"chunk_id": "chunk-small", "text": "확인 내용 " * 30}},
    )
    large_summary = "손실 없이 보존해야 하는 긴 근거 " * 900
    large_chunk = "원문 chunk 전체를 보존합니다 " * 900
    large_evidence = EvidenceRef(
        evidence_id="boi:public:capacity-large",
        kind="boi",
        title="긴 직접 근거",
        summary=large_summary,
        source="wiki",
        authority="reviewed",
        metadata={"best_chunk": {"chunk_id": "chunk-large", "text": large_chunk}},
    )

    context = v2_service.learning.contexts.compile(
        principal=principal,
        definition=v2_service.registry.get("knowledge.search"),
        goal="provider 물리 용량 안에서 근거를 선택한다",
        page_ref="",
        task_ref="",
        task_mode=TaskMode.copilot,
        task={},
        evidence=[compact_evidence, large_evidence],
        session={},
        source_set={},
        external_ai_summary="",
        external_refs=[],
        context_token_budget=1_000,
    )

    assert [item.evidence_id for item in context.evidence_refs] == [compact_evidence.evidence_id]
    assert context.evidence_refs[0].summary == compact_evidence.summary
    assert context.context_manifest is not None
    excluded = next(
        item for item in context.context_manifest.items if item.item_ref == large_evidence.evidence_id
    )
    assert excluded.selected is False
    assert excluded.selection_reason == "provider_context_capacity"
    assert large_evidence.summary == large_summary
    assert large_evidence.metadata["best_chunk"]["text"] == large_chunk


def test_team_playbook_is_not_injected_before_review(
    v2_service: AgentV2Service,
    principal: Principal,
):
    teammate = principal.model_copy(update={"employee_id": "100002", "display_name": "Teammate"})
    item = v2_service.learning.create_context_playbook_item(
        principal,
        ContextPlaybookCreateRequest(
            description="팀 운영 판단에서는 검토된 공식 절차와 최근 완료 기록을 함께 비교합니다.",
            capability_ids=["knowledge.search"],
            team_ids=["aix-tf"],
            source_refs=["boi:public:boi-wiki-manual:guide:final-operator-guide"],
            visibility="team",
        ),
    )
    definition = v2_service.registry.get("knowledge.search")

    def compile_for(identity: Principal) -> WorkContextPack:
        return v2_service.learning.contexts.compile(
            principal=identity,
            definition=definition,
            goal="팀 운영 기준 확인",
            page_ref="",
            task_ref="",
            task_mode=TaskMode.copilot,
            task={},
            evidence=[],
            session={},
            source_set={},
            external_ai_summary="",
            external_refs=[],
            model_profile="default",
        )

    assert compile_for(teammate).manifest["context_playbook_item_ids"] == []
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    v2_service.learning.patch_context_playbook_item(
        admin,
        item["item_id"],
        ContextPlaybookPatchRequest(
            expected_revision=1,
            status="active",
            review_note="팀 공유에 사용할 근거와 범위를 검토했습니다.",
        ),
    )
    assert compile_for(teammate).manifest["context_playbook_item_ids"] == [item["item_id"]]


def test_no_progress_is_preserved_as_a_negative_result(
    v2_service: AgentV2Service,
    principal: Principal,
):
    v2_service.model = ScriptedPlanner([_task_completion_plan("negative-loop-task")])
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="사람 검토 Task를 진행해줘", task_ref="negative-loop-task"),
    )
    run = v2_service.learning.get_run(principal, response.work_run_id)
    run.update({"status": "in_progress", "decision": "continue", "stop_reason": "progress_recorded"})
    v2_service.store.put("work_runs", response.work_run_id, run)
    continuation = v2_service.continue_work_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=run["revision"],
            delta=LoopDelta(kind="no_progress", summary="새 근거나 상태 변화가 없습니다."),
        ),
    )["work_run"]
    assert continuation["status"] == "waiting_human"
    assert continuation["stop_reason"] == "strategy_change_required"

    stopped = v2_service.continue_work_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=continuation["revision"],
            delta=LoopDelta(kind="no_progress", summary="전략을 바꿀 새 근거나 도구도 없습니다."),
        ),
    )["work_run"]
    assert stopped["status"] == "stopped"
    negatives = [v2_service.store.get("negative_results", item) for item in stopped["negative_result_ids"]]
    assert any(item and item["kind"] == "no_progress" for item in negatives)


def test_continue_run_stops_before_mutation_when_elapsed_budget_is_exhausted(
    v2_service: AgentV2Service,
    principal: Principal,
):
    context = WorkContextPack(
        context_id="context-loop-elapsed-budget",
        employee_id=principal.employee_id,
        capability_id="knowledge.search",
        goal="시간 예산 안에서만 업무를 진행한다",
    )
    v2_service.store.put("contexts", context.context_id, context.model_dump(mode="json"))
    run = v2_service.learning.create_run(
        principal=principal,
        agent_run_id="agent-loop-elapsed-budget",
        session={"session_id": "session-loop-elapsed-budget"},
        context=context,
        intent=WorkIntent(
            goal="시간 예산 안에서만 업무를 진행한다",
            resolved_goal="시간 예산 안에서만 업무를 진행한다",
            operation=WorkOperation.understand,
            harness_ids=["context.work"],
        ),
        goal_plan_id="goal-loop-elapsed-budget",
        catalog_revision=v2_service.registry.version,
    )
    run["loop"]["started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    run["loop"]["max_elapsed_seconds"] = 1
    v2_service.store.put("work_runs", run["work_run_id"], run)

    stopped, candidates = v2_service.learning.continue_run(
        principal,
        run["work_run_id"],
        WorkRunContinueRequest(
            expected_revision=run["revision"],
            idempotency_key="elapsed-budget-must-not-apply",
            delta=LoopDelta(
                kind="new_evidence",
                ref="boi:public:must-not-be-recorded",
                summary="시간 예산 뒤에는 이 근거를 적용하면 안 됩니다.",
            ),
        ),
    )

    assert candidates == []
    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "max_elapsed_seconds"
    assert "elapsed-budget-must-not-apply" not in stopped["loop"]["idempotency_keys"]


def test_harness_improvement_relations_are_compiled_into_admin_ontology(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    preservation_run_id = "work-run-harness-ontology-preserved"
    v2_service.store.put(
        "work_runs",
        preservation_run_id,
        {"work_run_id": preservation_run_id, "status": "completed"},
    )
    failure_ids = _record_recurrent_harness_failures(
        v2_service,
        admin,
        context=WorkContextPack(
            context_id="context-harness-ontology",
            employee_id=admin.employee_id,
            capability_id="knowledge.search",
            goal="근거 누락 개선 후보를 검증한다",
        ),
        prefix="ontology",
    )
    pattern_id = str(
        v2_service.store.get("harness_failure_records", failure_ids[0])["failure_pattern_id"]
    )
    candidate = v2_service.learning.create_harness_candidate(
        admin,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=failure_ids,
            changes={"retrieval_policy": {"authority_weight": 1.1}},
            rationale="반복되는 근거 누락을 줄이기 위한 제한된 검색 정책 시험입니다.",
            **_harness_hypothesis_fields(
                v2_service,
                preservation_run_ids=[preservation_run_id],
            ),
        ),
    )
    v2_service.knowledge.compile_graph(admin)
    graph = v2_service.store.ontology_neighbors(
        [candidate["candidate_id"]],
        depth=1,
        limit=20,
        employee_id=admin.employee_id,
        team_ids=admin.teams,
        include_all=True,
    )
    assert any(item["node_id"] == pattern_id for item in graph["nodes"])
    assert any(item["relation"] == "addresses_failure" for item in graph["edges"])


def test_mcp_v2_exposes_exactly_ten_progressive_tools(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_V2_REQUIRE_PAT", "false")
    from boi_wiki_mcp.app import v2 as mcp_v2

    tools = asyncio.run(mcp_v2.mcp_v2.list_tools())
    assert [item.name for item in tools] == [item["name"] for item in mcp_v2.MCP_V2_TOOLS]
    assert len(tools) == 10


def test_mcp_agent_proxy_does_not_send_employee_id(monkeypatch: pytest.MonkeyPatch):
    from boi_wiki_mcp.app import v2 as mcp_v2

    captured: dict[str, Any] = {}

    async def fake_post(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.update({"path": path, "payload": payload or {}})
        return {"run_id": "run_1", "capability_id": "knowledge.search"}

    monkeypatch.setattr(mcp_v2, "v2_api_post", fake_post)
    result = asyncio.run(mcp_v2.boi_agent("가이드 찾아줘", work_session_id="ws_existing"))
    assert result["run_id"] == "run_1"
    assert captured["path"] == "/api/v2/agent/turns"
    assert "employee_id" not in captured["payload"]
    assert "capability_id" not in captured["payload"]
    assert captured["payload"]["work_session_id"] == "ws_existing"


def test_mcp_boi_search_reuses_the_same_tool_for_graph_views(monkeypatch: pytest.MonkeyPatch):
    from boi_wiki_mcp.app import v2 as mcp_v2

    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.update({"path": path, "params": params or {}})
        return {"view": "path", "nodes": ["a", "b"], "edges": []}

    monkeypatch.setattr(mcp_v2, "v2_api_get", fake_get)
    result = asyncio.run(
        mcp_v2.boi_search(
            view="path",
            source_ref="boi:public:a",
            target_ref="boi:public:b",
            depth=4,
        )
    )

    assert result["view"] == "path"
    assert captured["path"] == "/api/v2/knowledge-graph/explore"
    assert captured["params"]["source_ref"] == "boi:public:a"
    assert captured["params"]["target_ref"] == "boi:public:b"


def test_mcp_agent_continues_the_same_work_run_with_an_explicit_delta(monkeypatch: pytest.MonkeyPatch):
    from boi_wiki_mcp.app import v2 as mcp_v2

    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["get"] = path
        return {"work_run_id": "workrun_1", "revision": 3}

    async def fake_post(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        captured.update({"post": path, "payload": payload or {}})
        return {"work_run": {"work_run_id": "workrun_1", "status": "completed"}}

    monkeypatch.setattr(mcp_v2, "v2_api_get", fake_get)
    monkeypatch.setattr(mcp_v2, "v2_api_post", fake_post)
    result = asyncio.run(
        mcp_v2.boi_agent(
            "",
            work_run_id="workrun_1",
            delta_kind="human_input",
            delta_summary="담당자가 근거와 결과를 확인했습니다.",
            confirm=True,
        )
    )

    assert result["work_run"]["status"] == "completed"
    assert captured["get"] == "/api/v2/work-runs/workrun_1"
    assert captured["post"] == "/api/v2/work-runs/workrun_1/continue"
    assert captured["payload"]["expected_revision"] == 3
    assert captured["payload"]["confirmation"] == "confirm"


def test_compose_has_separate_pgvector_and_worker():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["boi-postgres"]["image"].startswith("pgvector/pgvector:")
    assert services["boi-agent-worker"]["depends_on"]["boi-postgres"]["condition"] == "service_healthy"
    assert services["boi-api"]["environment"]["BOI_AGENT_V2_DATABASE_URL"].startswith("postgresql://")


def test_agent_kit_uses_bootstrap_and_never_embeds_a_token():
    files = [
        ROOT / "agent_kit" / "codex" / "SKILL.md",
        ROOT / "agent_kit" / "claude" / "SKILL.md",
        ROOT / "agent_kit" / "python" / "boi_v2_client.py",
        ROOT / "agent_kit" / "typescript" / "boi-v2-client.ts",
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "boi_bootstrap" in contents
    assert "/api/v2/knowledge-graph/explore" in contents
    assert all(view in contents for view in ("neighbors", "path", "impact", "tour"))
    assert "boi_pat_..." not in contents
    assert "sk-proj-" not in contents


def test_grounded_answer_contract_preserves_all_model_supported_claims_and_outcomes():
    schema = QuickAgentRuntime._grounded_answer_schema()
    assert "maxItems" not in schema["properties"]["claims"]
    assert "maxLength" not in schema["properties"]["summary"]
    assert "maxItems" not in schema["properties"]["outcomes"]

    long_tail = "마지막 근거의 세부 판단과 예외 조건 " + ("전체 보존 " * 400)
    hints = [
        {
            "ref": f"boi:public:test:source-{index}",
            "chunk_id": f"chunk-{index}",
            "answer_scope": "canonical",
        }
        for index in range(1, 21)
    ]
    claims = [
        {
            "claim_id": f"claim-{index}",
            "text": long_tail if index == 20 else f"검증된 사실 {index}",
            "claim_kind": "fact",
            "source_scope": "canonical",
            "source_refs": [f"S{index}"],
            "supporting_chunk_ids": [f"C{index}"],
            "required_for_answer": index == 20,
        }
        for index in range(1, 21)
    ]
    envelope = {
        "grounded_answer": {
            "summary": long_tail,
            "summary_source_refs": [f"S{index}" for index in range(1, 21)],
            "claims": claims,
            "outcomes": [
                {
                    "title": f"결과 묶음 {group}",
                    "items": [
                        {"text": f"결과 {group}-{item}", "source_refs": [f"S{item}"]}
                        for item in range(1, 11)
                    ],
                }
                for group in range(1, 7)
            ],
            "related_questions": [],
        }
    }
    plan = SemanticPlan(
        resolved_goal="검증된 근거 전체를 빠짐없이 설명한다",
        retrieval_query="검증된 근거 전체",
        capability_id="knowledge.search",
        evidence_scope="canonical",
    )

    answer, diagnostics = QuickAgentRuntime._resolve_grounded_answer(envelope, plan, hints)

    assert diagnostics == {"accepted": True, "accepted_claims": 20, "rejected_claims": 0}
    assert answer is not None
    assert len(answer["claims"]) == 20
    assert len(answer["outcomes"]) == 6
    assert all(len(outcome["items"]) == 10 for outcome in answer["outcomes"])
    assert answer["summary"] == long_tail.strip()
    assert answer["claims"][-1]["text"] == long_tail.strip()


def test_grounded_answer_uses_a_validated_claim_when_summary_has_an_unbound_extra_source():
    hints = [
        {"ref": "boi:public:loop", "chunk_id": "chunk-loop", "answer_scope": "canonical"},
        {"ref": "boi:public:extra", "chunk_id": "chunk-extra", "answer_scope": "canonical"},
    ]
    envelope = {
        "grounded_answer": {
            "summary": "검증된 claim보다 더 넓은 별도 요약",
            "summary_source_refs": ["S1", "S2"],
            "claims": [
                {
                    "claim_id": "loop-definition",
                    "text": "Work Learning Loop는 검증된 결과를 다음 업무에 재사용하는 순환입니다.",
                    "claim_kind": "definition",
                    "source_scope": "canonical",
                    "source_refs": ["S1"],
                    "supporting_chunk_ids": ["C1"],
                    "required_for_answer": True,
                }
            ],
            "outcomes": [],
            "related_questions": [],
        }
    }
    plan = SemanticPlan(
        resolved_goal="Work Learning Loop를 설명한다",
        retrieval_query="Work Learning Loop",
        capability_id="knowledge.search",
        evidence_scope="canonical",
    )

    answer, diagnostics = QuickAgentRuntime._resolve_grounded_answer(envelope, plan, hints)

    assert diagnostics == {"accepted": True, "accepted_claims": 1, "rejected_claims": 0}
    assert answer is not None
    assert answer["summary"] == answer["claims"][0]["text"]
    assert answer["summary_source_refs"] == ["boi:public:loop"]
