from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import replace
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
    OpenAICompatibleGateway,
    UnavailableModelGateway,
    UsageTrackingGateway,
    _record_provider_usage,
    begin_model_usage,
    build_model_gateway,
    ensure_lmstudio_model_residency,
    finish_model_usage,
)
from boi_api.app.v2.models import (
    AgentTurnRequest,
    AgentTurnResponse,
    AnswerBlock,
    CitationRef,
    ContextPlaybookCreateRequest,
    ContextPlaybookPatchRequest,
    DeepJobRequest,
    GraphQueryDraft,
    GraphQueryPlan,
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
    SkillArtifactActivateRequest,
    SkillArtifactTestRequest,
    SopArtifactPatchRequest,
    SourceSetPatchRequest,
    TaskMode,
    TokenCreateRequest,
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
from boi_api.app.v2.repository import KnowledgeRecord, KnowledgeRepository
from boi_api.app.v2.rendering import render_agent_markdown
from boi_api.app.v2.routes import build_agent_v2_router
from boi_api.app.v2.search import chunks_for_record, diversify_ranked, graph_score, identity_score
from boi_api.app.v2.service import AgentV2Service, truncate_markdown
from boi_api.app.v2.store import PostgresAgentV2Store, now_iso
from boi_api.app.v2.worker import DeepWorkRunner, ensure_exact_evidence_ledger, latest_assistant_text
from boi_api.app.v2.work_learning import WorkIntentEngine
from boi_api.app.task_completion import normalise_task_completion


ROOT = Path(__file__).resolve().parents[1]


def test_capability_registry_rejects_unimplemented_mutation_handlers_before_turn_execution():
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    read_definition = registry.get("knowledge.search")

    assert registry.handler_supported(read_definition) is True
    assert registry.handler_supported(read_definition.model_copy(update={"operation": OperationClass.mutate})) is False


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
        grounding_status="grounded",
        context_usage={"page_anchor": {"ref": "boi:public:guide", "resolved": True}, "selected_source_count": 12},
    )
    compact = v2_service._enforce_response_budget(response)
    assert compact.work_intent is not None
    assert compact.work_intent.operation.value == "understand"
    assert compact.citations and compact.citations[0].source_ref == "boi:public:guide"
    assert compact.grounding_status == "grounded"
    assert len(json.dumps(compact.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")) <= v2_service.settings.response_budget_bytes


def test_explanatory_intent_cannot_execute_a_draft_capability(v2_service: AgentV2Service):
    explanatory = WorkIntent(
        goal="Action dry-run과 실제 실행의 차이를 알려줘",
        resolved_goal="Action dry-run과 실제 실행의 차이를 설명한다",
        operation=WorkOperation.compare,
        operation_plan=[WorkOperation.understand, WorkOperation.compare],
        asset_kind=WorkAssetKind.action,
        result_purpose="compare",
    )
    assert v2_service._guard_explanatory_capability("action.plan", explanatory) == "knowledge.search"
    assert v2_service._guard_explanatory_capability("deep.research", explanatory) == "deep.research"
    executable = explanatory.model_copy(
        update={
            "operation": WorkOperation.run,
            "operation_plan": [WorkOperation.run],
            "result_purpose": "execute",
        }
    )
    assert v2_service._guard_explanatory_capability("action.plan", executable) == "action.plan"


def test_work_view_cannot_be_misrouted_to_an_automation_capability(v2_service: AgentV2Service):
    combined = WorkIntent(
        goal="내가 하는 일이 뭐지?",
        resolved_goal="공식 역할과 현재 업무를 구분해 확인한다",
        operation=WorkOperation.understand,
        operation_plan=[WorkOperation.understand],
        asset_kind=WorkAssetKind.runtime,
        result_purpose="explain",
        work_view="combined",
    )
    current = combined.model_copy(update={"work_view": "current"})

    assert v2_service._guard_explanatory_capability("work_routine.plan", combined) == "knowledge.search"
    assert v2_service._guard_explanatory_capability("knowledge.search", current) == "work.inbox"


class FakeModel:
    provider = "test"

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
        if {"capability_id", "asset_kind", "operation", "operation_plan", "scope"} <= required:
            request = str((json.loads(prompt) if prompt.strip().startswith("{") else {}).get("request") or "")
            lowered = request.lower()
            read_request = "어떻게" in lowered or (
                any(term in lowered for term in ("찾아", "알려", "보여"))
                and not any(term in lowered for term in ("만들어", "작성해", "설계해", "정의해"))
            )
            if any(term in lowered for term in ("내 할 일", "처리해야 할 업무", "현재 업무")):
                capability_id, asset_kind, operation = "work.inbox", "runtime", "observe"
            elif any(term in lowered for term in ("task로 나눠", "task로 쪼개")):
                capability_id, asset_kind, operation = "sop.plan", "sop", "create"
            elif "업무 이벤트" in lowered and any(term in lowered for term in ("만들어", "작성해", "정의해")) and not read_request:
                capability_id, asset_kind, operation = "business_event.plan", "business_event", "create"
            elif "sop" in lowered and any(term in lowered for term in ("만들어", "작성해", "설계해")) and not any(
                term in lowered for term in ("검증", "다듬", "보완")
            ) and not read_request:
                capability_id, asset_kind, operation = "sop.plan", "sop", "create"
            elif any(term in lowered for term in ("다듬", "보완", "구체적")):
                capability_id, asset_kind, operation = "sop.plan", "sop", "refine"
            elif any(term in lowered for term in ("검증", "점검")):
                capability_id, asset_kind, operation = "sop.plan", "sop", "validate"
            elif any(term in lowered for term in ("완료해", "완료하고", "완료 처리")):
                capability_id, asset_kind, operation = "task.work", "task", "complete"
            elif "연결" in lowered and "설명" in lowered:
                capability_id, asset_kind, operation = "knowledge.search", "sop", "connect"
            else:
                capability_id, asset_kind, operation = "knowledge.search", "knowledge", "understand"
            operation_plan = ["understand"] if operation == "understand" else ["understand", operation]
            if operation in {"create", "refine", "connect", "validate"} and "validate" not in operation_plan:
                operation_plan.append("validate")
            if operation == "complete":
                operation_plan.extend(["validate", "capture"])
            return {
                "capability_id": capability_id,
                "asset_kind": asset_kind,
                "operation": operation,
                "operation_plan": list(dict.fromkeys(operation_plan)),
                "scope": "wiki" if "wiki 전체" in lowered else "auto",
                "desired_outcome": "draft" if operation == "create" else "completion_record" if operation == "complete" else "answer",
                "target_ref": "model-invented-task-ref",
                "needs_clarification": False,
                "confidence": 0.96,
                "reason": "test semantic planner",
                "result_purpose": "design" if operation in {"create", "refine"} else "execute" if operation == "run" else "explain",
                "requested_asset_kinds": [asset_kind],
                "artifact_actions": [],
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


class CountingSemanticRouteModel(FakeModel):
    def __init__(self):
        self.planner_calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "presentation_mode", "context_refs"} <= required:
            self.planner_calls += 1
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class BroadWorkQuestionReviewModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"work_view", "explicit_current_only", "reason"}:
            return {"work_view": "combined", "explicit_current_only": False, "reason": "포괄적인 역할 질문"}
        if {"capability_id", "asset_kind", "operation", "operation_plan", "scope"} <= required:
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "capability_id": "work.inbox",
                    "asset_kind": "runtime",
                    "operation": "understand",
                    "operation_plan": ["understand"],
                    "work_view": "current",
                    "resolved_goal": "현재 업무를 확인한다",
                    "result_purpose": "explain",
                    "requested_asset_kinds": ["person", "role", "task"],
                }
            )
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class MisroutedCurrentWorkReviewModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"work_view", "explicit_current_only", "reason"}:
            return {"work_view": "current", "explicit_current_only": True, "reason": "현재 업무만 요청함"}
        if {"capability_id", "asset_kind", "operation", "operation_plan", "scope"} <= required:
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "capability_id": "knowledge.search",
                    "asset_kind": "knowledge",
                    "operation": "understand",
                    "operation_plan": ["understand"],
                    "work_view": "combined",
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


class RuntimeOnlyWrongScopeReviewModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"work_view", "explicit_current_only", "reason"}:
            return {"work_view": "combined", "explicit_current_only": False, "reason": "범위를 과도하게 확장함"}
        if {"capability_id", "asset_kind", "operation", "operation_plan", "scope"} <= required:
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            planned.update(
                {
                    "capability_id": "knowledge.search",
                    "asset_kind": "runtime",
                    "operation": "understand",
                    "operation_plan": ["understand"],
                    "scope": "current",
                    "work_view": "combined",
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


class GenericRetrievalQueryModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "retrieval_query", "context_refs"} <= required:
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


class SemanticContinuationModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "continue_active_run", "continuation_kind", "user_confirmation"} <= required:
            payload = json.loads(prompt)
            active_run = (payload.get("active_work") or {}).get("work_run") or {}
            planned = super().generate_structured(system=system, prompt=prompt, schema=schema)
            if active_run.get("status") == "waiting_human":
                planned.update(
                    {
                        "asset_kind": "task",
                        "operation": "complete",
                        "operation_plan": ["understand", "validate", "complete", "capture"],
                        "desired_outcome": "completion_record",
                        "continue_active_run": True,
                        "continuation_kind": "human_input",
                        "user_confirmation": True,
                        "confidence": 0.98,
                        "reason": "the user explicitly confirmed the pending human completion checks",
                    }
                )
            else:
                planned.update(
                    {
                        "continue_active_run": False,
                        "continuation_kind": "none",
                        "user_confirmation": False,
                    }
                )
            return planned
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class TargetlessTaskLookupModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "continue_active_run", "continuation_kind", "user_confirmation"} <= required:
            return {
                "capability_id": "task.work",
                "asset_kind": "task",
                "operation": "observe",
                "operation_plan": ["understand", "observe"],
                "scope": "selected",
                "desired_outcome": "기존 Task 판단 기록 찾기",
                "target_ref": "",
                "needs_clarification": False,
                "confidence": 0.96,
                "reason": "task-related lookup",
                "continue_active_run": False,
                "continuation_kind": "none",
                "user_confirmation": False,
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class MisroutedActionRunModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "continue_active_run", "continuation_kind", "user_confirmation"} <= required:
            return {
                "capability_id": "task.work",
                "asset_kind": "task",
                "operation": "run",
                "operation_plan": ["understand", "validate", "run", "observe"],
                "scope": "selected",
                "desired_outcome": "dry-run result",
                "target_ref": "manual.review",
                "needs_clarification": False,
                "confidence": 0.91,
                "reason": "mistaken task execution route",
                "continue_active_run": False,
                "continuation_kind": "none",
                "user_confirmation": False,
            }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class RepairingSopModel(FakeModel):
    def __init__(self):
        self.calls = 0

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if "capability_id" in required:
            return super().generate_structured(system=system, prompt=prompt, schema=schema)
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


class RefiningSopModel(RepairingSopModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
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


class GroundedAnswerModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
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


class ApplyRelatedQuestionModel(GroundedAnswerModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        result = super().generate_structured(system=system, prompt=prompt, schema=schema)
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
    def __init__(self):
        self.planner_payloads: list[dict[str, Any]] = []

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "presentation_mode", "context_refs"} <= required:
            payload = json.loads(prompt)
            self.planner_payloads.append(payload)
            request = str(payload.get("request") or "")
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            diagram = "머메이드" in request
            return {
                "capability_id": "knowledge.search",
                "asset_kind": "knowledge",
                "operation": "connect" if diagram else "understand",
                "operation_plan": ["understand", "connect", "validate"] if diagram else ["understand"],
                "scope": "wiki",
                "desired_outcome": "BoI Wiki RAG 검색 흐름을 실제 그림으로 확인" if diagram else "검색 방식 설명",
                "resolved_goal": (
                    "직전 답변에서 설명한 BoI Wiki RAG 검색 흐름을 근거 기반 Mermaid 차트로 그려줘"
                    if diagram
                    else request
                ),
                "presentation_mode": "mermaid" if diagram else "prose",
                "context_refs": trusted_refs[:4] if diagram else [],
                "result_purpose": "explain",
                "requested_asset_kinds": ["knowledge"],
                "artifact_actions": [],
                "target_ref": "",
                "needs_clarification": False,
                "confidence": 0.99,
                "reason": "the second turn requests a visual continuation of the grounded search explanation",
                "continue_active_run": False,
                "continuation_kind": "none",
                "user_confirmation": False,
            }
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


class TransformMermaidModel(MultiTurnMermaidModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "presentation_mode", "context_refs"} <= required:
            payload = json.loads(prompt)
            trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            return {
                "capability_id": "knowledge.search",
                "asset_kind": "workflow",
                "operation": "refine",
                "operation_plan": ["understand", "refine", "validate"],
                "scope": "wiki",
                "desired_outcome": "현재 흐름을 Task와 SOP 초안으로 전환",
                "resolved_goal": str(payload.get("request") or ""),
                "presentation_mode": "mermaid",
                "context_refs": trusted_refs[:4],
                "result_purpose": "transform",
                "requested_asset_kinds": ["workflow", "task", "sop"],
                "artifact_actions": ["split_tasks", "create_sop_draft"],
                "target_ref": "",
                "needs_clarification": False,
                "confidence": 0.99,
                "reason": "the user explicitly requested artifact transformation",
                "continue_active_run": False,
                "continuation_kind": "none",
                "user_confirmation": False,
            }
        if required == {"title", "nodes", "edges"}:
            return {
                "title": "업무 흐름 전환 후보",
                "nodes": [
                    {"node_id": "start", "label": "업무 시작", "kind": "Workflow", "asset_kind": "workflow", "source_numbers": [1]},
                    {"node_id": "finish", "label": "업무 결과", "kind": "Workflow", "asset_kind": "workflow", "source_numbers": [1]},
                ],
                "edges": [
                    {"from": "start", "to": "finish", "label": "업무 진행", "source_numbers": [1]},
                ],
            }
        return GroundedAnswerModel.generate_structured(self, system=system, prompt=prompt, schema=schema)


class SplitOnlyFollowupModel(MultiTurnMermaidModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "presentation_mode", "context_refs"} <= required:
            payload = json.loads(prompt)
            request = str(payload.get("request") or "")
            if "Task로 나눠" in request:
                trusted_refs = [str(item) for item in payload.get("trusted_context_refs") or []]
                return {
                    "capability_id": "sop.plan",
                    "asset_kind": "workflow",
                    "operation": "refine",
                    "operation_plan": ["understand", "refine", "validate"],
                    "scope": "current",
                    "desired_outcome": "현재 흐름을 Task 후보로 분해",
                    "resolved_goal": "현재 흐름을 Task 후보로 분해",
                    "retrieval_query": "현재 흐름의 업무 단계",
                    "presentation_mode": "artifact",
                    "context_refs": trusted_refs[:4],
                    "result_purpose": "transform",
                    "requested_asset_kinds": ["task"],
                    "artifact_actions": ["split_tasks"],
                    "target_ref": trusted_refs[0] if trusted_refs else "",
                    "needs_clarification": False,
                    "confidence": 0.99,
                    "reason": "the user explicitly requested task splitting only",
                    "continue_active_run": False,
                    "continuation_kind": "none",
                    "user_confirmation": False,
                }
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


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
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"title", "nodes", "edges"}:
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


class AutomaticCheckModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if {"capability_id", "resolved_goal", "presentation_mode", "context_refs"} <= required:
            payload = json.loads(prompt)
            refs = [str(item) for item in payload.get("trusted_context_refs") or []]
            return {
                "capability_id": "work_routine.plan",
                "asset_kind": "knowledge",
                "operation": "create",
                "operation_plan": ["understand", "create", "validate"],
                "scope": "current",
                "desired_outcome": "automatic check preview",
                "resolved_goal": str(payload.get("request") or ""),
                "presentation_mode": "artifact",
                "context_refs": refs[:2],
                "target_ref": refs[0] if refs else "boi:public:guide",
                "needs_clarification": False,
                "confidence": 0.99,
                "reason": "the user asked for a scheduled re-check",
                "continue_active_run": False,
                "continuation_kind": "none",
                "user_confirmation": False,
            }
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


class SkillExecutionModel(FakeModel):
    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required") or [])
        if required == {"result", "evidence_refs"}:
            return {"result": "관련 근거와 evidence_refs를 확인했습니다.", "evidence_refs": []}
        return super().generate_structured(system=system, prompt=prompt, schema=schema)


class ReviewerModel(FakeModel):
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
    planner = FakeModel()
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
    assert captured["json"]["max_tokens"] == settings.model_max_output_tokens


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


def test_gpt55_is_blocked_from_normal_runtime_and_falls_back_to_the_local_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOI_GPT55_TEST_MODE", "false")
    monkeypatch.setenv("BOI_V2_MODEL_PROVIDER", "openai_responses")
    monkeypatch.setenv("BOI_V2_MODEL_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("BOI_V2_MODEL_API_KEY", "test-external-key")
    monkeypatch.setenv("BOI_V2_MODEL", "gpt-5.5")
    monkeypatch.setenv("BOI_DEEPAGENTS_MODEL", "gpt-5.5")
    monkeypatch.setenv("BOI_LLM_BASE_URL", "http://lmstudio.example:1234/v1")
    monkeypatch.setenv("BOI_LLM_API_KEY", "not-needed")
    monkeypatch.setenv("BOI_LLM_MODEL", "google/gemma-local")
    monkeypatch.setenv("BOI_AGENT_LLM_MODEL", "google/gemma-local")

    settings = AgentV2Settings.from_environment(repo_root=ROOT)

    assert settings.model_provider == "openai_compatible"
    assert settings.model_base_url == "http://lmstudio.example:1234/v1"
    assert settings.model_name == "google/gemma-local"
    assert settings.deep_model == "google/gemma-local"
    assert settings.model_route == "local_fallback"
    assert settings.gpt55_test_mode is False


def test_gpt55_can_only_be_selected_in_explicit_test_mode(monkeypatch: pytest.MonkeyPatch):
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
    question_route = v2_service.quick_agent.route("SOP와 업무 이벤트가 어떻게 연결돼?", page_kind="sop", model=v2_service.model)
    draft_route = v2_service.quick_agent.route("업무 이벤트 정의 초안을 만들어줘", page_kind="event", model=v2_service.model)
    search_route = v2_service.quick_agent.route("업무 이벤트 정의 만들기 자료를 찾아줘", page_kind="event", model=v2_service.model)
    how_to_route = v2_service.quick_agent.route("업무 이벤트 정의는 어떻게 만들어?", page_kind="event", model=v2_service.model)
    ambiguous_noun_route = v2_service.quick_agent.route("업무 이벤트 정의 초안", page_kind="event", model=v2_service.model)
    search_then_draft = v2_service.quick_agent.route("관련 자료를 찾아 SOP 초안을 만들어줘", page_kind="sop", model=v2_service.model)
    inbox_route = v2_service.quick_agent.route("현재 내 할 일을 보여줘", page_kind="library", model=v2_service.model)
    natural_inbox_route = v2_service.quick_agent.route(
        "내가 지금 처리해야 할 업무와 다음에 확인할 내용을 보여줘",
        page_kind="library",
        model=v2_service.model,
    )
    active_sop_followup = v2_service.quick_agent.route(
        "이 초안의 Task 완료 항목을 다듬어줘",
        page_kind="agent",
        active_capability="sop.plan",
        model=v2_service.model,
    )
    knowledge_to_tasks = v2_service.quick_agent.route(
        "이걸 Task로 나눠줘",
        page_kind="agent",
        active_capability="knowledge.draft",
        model=v2_service.model,
    )

    assert question_route["engine"] == "langgraph"
    assert question_route["capability_id"] == "knowledge.search"
    assert question_route["source"] == "llm_structured"
    assert question_route["reason"] == "test semantic planner"
    assert draft_route["capability_id"] == "business_event.plan"
    assert search_route["capability_id"] == "knowledge.search"
    assert search_route["reason"] == "test semantic planner"
    assert how_to_route["capability_id"] == "knowledge.search"
    assert ambiguous_noun_route["capability_id"] == "knowledge.search"
    assert search_then_draft["capability_id"] == "sop.plan"
    assert inbox_route["capability_id"] == "work.inbox"
    assert natural_inbox_route["capability_id"] == "work.inbox"
    assert active_sop_followup["capability_id"] == "sop.plan"
    assert active_sop_followup["reason"] == "test semantic planner"
    assert knowledge_to_tasks["capability_id"] == "sop.plan"
    assert v2_service.quick_agent.route("Alarm 대응 SOP 만들어", page_kind="sop", model=v2_service.model)["capability_id"] == "sop.plan"


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


def test_targetless_task_lookup_is_normalized_to_wiki_search_by_capability_contract(
    v2_service: AgentV2Service,
):
    route = v2_service.quick_agent.route(
        "단면검사 Task에서 이전에 확인한 판단 기록을 찾아줘",
        page_kind="library",
        model=TargetlessTaskLookupModel(),
    )

    assert route["source"] == "llm_structured"
    assert route["capability_id"] == "knowledge.search"
    assert route["work_intent"]["asset_kind"] == "task"
    assert route["work_intent"]["operation"] == "understand"
    assert route["trace"][-1] == "validate:task_lookup_to_search"


def test_registered_action_target_keeps_a_run_on_the_action_capability_contract(
    v2_service: AgentV2Service,
):
    route = v2_service.quick_agent.route(
        "manual.review Action을 case_id A-100으로 dry-run 실행해줘.",
        page_kind="action",
        trusted_targets={"action_key": "manual.review"},
        model=MisroutedActionRunModel(),
    )

    assert route["source"] == "llm_structured"
    assert route["capability_id"] == "action.plan"
    assert route["work_intent"]["asset_kind"] == "action"
    assert route["work_intent"]["operation"] == "run"
    assert route["work_intent"]["target_ref"] == "manual.review"
    assert route["trace"][-1] == "validate:trusted_action_target"


def test_natural_language_router_never_uses_keyword_draft_guessing_when_the_intent_model_is_unavailable(
    v2_service: AgentV2Service,
):
    unavailable = UnavailableModelGateway("planner unavailable")

    route = v2_service.quick_agent.route(
        "설비 Alarm 대응 SOP를 만들고 Action까지 실행해줘",
        page_kind="sop",
        model=unavailable,
    )

    assert route["capability_id"] == "knowledge.search"
    assert route["source"] == "safe_fallback"
    assert route["reason"] == "intent_model_unavailable"
    assert route["work_intent"]["operation"] == "understand"
    assert route["work_intent"]["needs_clarification"] is True


def test_explaining_cross_asset_connections_does_not_run_an_authoring_harness(
    v2_service: AgentV2Service,
    principal: Principal,
):
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 SOP의 관련 업무 이벤트와 Action을 Wiki 전체에서 연결해 설명해줘.",
            page_ref="/docs/boi%3Apublic%3Asop%3Amanual?employee_id=100001",
        ),
    )

    assert response.capability_id == "knowledge.search"
    assert response.work_intent is not None
    assert response.work_intent.asset_kind.value == "sop"
    assert response.work_intent.operation.value == "connect"
    assert response.work_intent.desired_outcome == "answer"
    assert [item.harness_id for item in response.harness_results] == ["context.work"]
    assert response.loop_state["status"] == "completed"


def test_empty_current_work_is_a_valid_result_instead_of_a_context_failure(
    v2_service: AgentV2Service,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(v2_service.repository, "current_work", lambda _principal, limit=50: [])

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
    assert [item.status for item in response.harness_results] == ["passed"]


def test_current_work_scope_review_corrects_an_initial_relationship_overreach(
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

    assert response.capability_id == "work.inbox"
    assert response.work_intent and response.work_intent.work_view == "current"
    assert response.graph_result_ref == ""
    assert response.artifact_refs == []


def test_current_runtime_contract_prevents_a_scope_reviewer_from_adding_role_graphs(
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

    assert response.capability_id == "work.inbox"
    assert response.work_intent and response.work_intent.work_view == "current"
    assert response.graph_result_ref == ""
    assert response.artifact_refs == []


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
    assert response.used_source_refs == [item.source_ref for item in response.citations]
    assert "지금 처리할 업무" in response.answer.markdown


def test_completion_design_wording_does_not_become_a_task_completion_operation(
    v2_service: AgentV2Service,
):
    question = "기존 SOP를 재사용하고 Task별 완료된 모습과 확인할 자료를 넣은 SOP 초안을 만들어줘."
    route = v2_service.quick_agent.route(question, page_kind="sop", model=v2_service.model)
    intent = WorkIntentEngine.infer(
        question,
        capability_id=route["capability_id"],
        page_ref="/docs/boi%3Apublic%3Asop%3Amanual?employee_id=100001",
        task_ref="",
        target_ref="boi:public:sop:manual",
    )

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
    assert response.work_intent and response.work_intent.scope == "wiki"
    context = v2_service.get_context(principal, response.context_ref)
    assert context["context_manifest"]["selected_refs"][0] == "boi:public:guide"


def test_multiturn_visual_followup_resolves_the_prior_subject_and_creates_grounded_mermaid(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = MultiTurnMermaidModel()
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
    assert second.artifact_refs[0].artifact_type == "mermaid_diagram"
    artifact = v2_service.get_artifact(principal, second.artifact_refs[0].artifact_id)
    assert artifact["draft"]["mermaid"].startswith("flowchart TD")
    assert len(artifact["draft"]["nodes"]) == 3
    assert len(artifact["draft"]["edges"]) == 2
    assert all(item["source_refs"] for item in artifact["draft"]["nodes"])
    assert all(item["source_refs"] for item in artifact["draft"]["edges"])
    assert "<br/>" not in artifact["draft"]["mermaid"]
    assert artifact["actions"] == []
    assert second.artifact_refs[0].actions == []
    assert "Task 또는 SOP" not in second.answer.markdown
    timeline = v2_service.session_timeline(principal, first.work_session_id)["items"]
    assert timeline[-2]["display_text"] == "머메이드 차트로 그려줘"
    assert timeline[-1]["artifact_refs"][0]["artifact_id"] == artifact["artifact_id"]
    assert model.planner_payloads[-1]["conversation_context"]["recent_messages"]


def test_mermaid_conversion_actions_require_explicit_transform_intent(
    v2_service: AgentV2Service,
    principal: Principal,
):
    model = TransformMermaidModel()
    v2_service.model = model
    v2_service.search.model = model

    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(
            question="이 근거 흐름을 Task로 나누고 SOP 초안으로 이어갈 수 있게 준비해줘",
            page_ref="/docs/boi%3Apublic%3Aguide",
        ),
    )

    assert response.work_intent is not None
    assert response.work_intent.result_purpose == "transform"
    assert response.work_intent.artifact_actions == ["split_tasks", "create_sop_draft"]
    assert [item.action_id for item in response.artifact_refs[0].actions] == [
        "split_tasks",
        "create_sop_draft",
    ]
    artifact = v2_service.get_artifact(principal, response.artifact_refs[0].artifact_id)
    assert [item["action_id"] for item in artifact["actions"]] == ["split_tasks", "create_sop_draft"]


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
    assert second.work_intent.artifact_actions == ["split_tasks"]
    assert second.plan_ref == ""
    assert [item.artifact_type for item in second.artifact_refs] == ["workflow_draft"]
    artifact = v2_service.get_artifact(principal, second.artifact_refs[0].artifact_id)
    assert artifact["capability_id"] == "workflow.transform"
    assert len(artifact["draft"]["tasks"]) == 2
    assert artifact["domain"]["domain_kind"] == "mermaid_workflow_draft"
    assert "SOP 초안을 만들" in second.answer.markdown
    assert not v2_service.store.list("plans", employee_id=principal.employee_id, limit=100)


def test_mermaid_regenerates_when_nodes_exceed_the_planner_asset_scope(
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
    assert model.graph_calls == 2
    assert artifact["generation_attempts"] == 2
    assert {item["asset_kind"] for item in artifact["draft"]["nodes"]} == {"knowledge"}
    assert artifact["actions"] == []


def test_mermaid_validation_failure_keeps_internal_scope_details_out_of_the_ui(
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
    work_run = v2_service.store.get("work_runs", response.work_run_id)

    assert response.status == "needs_input"
    assert response.artifact_refs == []
    assert "직접 연결된 근거" in response.answer.markdown
    assert "workflow" not in response.answer.markdown.lower()
    assert work_run and work_run["diagnostics"][-1]["kind"] == "mermaid_validation"
    assert "workflow" in work_run["diagnostics"][-1]["detail"]


def test_mermaid_regenerates_schema_shaped_labels_as_user_facing_language(
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
    visible_labels = [item["label"] for item in artifact["draft"]["nodes"]]
    visible_labels.extend(item["label"] for item in artifact["draft"]["edges"])
    assert model.graph_calls == 2
    assert artifact["generation_attempts"] == 2
    assert all("_" not in item for item in visible_labels)


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
    assert "BoI Wiki 운영 가이드" in response.work_intent.retrieval_query


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
        item.result_kind in {"answer", "work_form", "confirmation"} or item.graph_query_kind
        for item in starters
    )
    assert all(item.subject_ref and item.source_refs for item in starters)
    assert all(item.subject_ref in item.source_refs for item in starters)
    assert all(item.suggestion_id.startswith("suggestion_") for item in starters)
    assert not {item.category for item in starters}.intersection({"sop_task", "business_event", "action"})


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
    route = {
        "capability_id": "knowledge.search",
        "source": "llm_structured",
        "reason": "업무 관계 조회",
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
    assert response.answer.markdown.count("어느 대상을 볼까요?") == 1
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
    assert v2_service.list_work_routines(principal, surface="pet", status="actionable")["count"] == 0
    assert response.next_actions[0].action_kind == "confirm_plan"

    confirmed = asyncio.run(v2_service.confirm_plan(principal, response.plan_ref, "표시된 일정을 확인함"))

    assert confirmed["production_changed"] is True
    assert confirmed["domain_result"]["routine_id"].startswith("routine_")
    visible = v2_service.list_work_routines(principal, surface="pet", status="actionable")
    assert visible["count"] == 1
    assert visible["items"][0]["cron"] == "0 9 * * *"
    assert visible["items"][0]["origin"] == "user"
    assert visible["items"][0]["surface_visibility"] == "normal"


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


def test_work_run_requires_human_completion_and_reuses_the_result_as_private_knowledge(
    v2_service: AgentV2Service,
    principal: Principal,
):
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
        "retrieve",
        "validate",
        "complete",
        "capture",
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
    assert waiting["status"] == "waiting_human"

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


def test_full_learning_cycle_promotes_reindexes_and_reuses_authoritative_knowledge_in_new_session(
    v2_service: AgentV2Service,
    principal: Principal,
):
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


def test_work_loop_stops_the_first_no_progress_delta(
    v2_service: AgentV2Service,
    principal: Principal,
):
    response = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="사람 검토 Task를 완료해줘", task_ref="review-task"),
    )
    work_run = v2_service.learning.get_run(principal, response.work_run_id)
    stopped, _ = v2_service.learning.continue_run(
        principal,
        response.work_run_id,
        WorkRunContinueRequest(
            expected_revision=work_run["revision"],
            delta=LoopDelta(kind="no_progress", summary="같은 질문과 같은 결과"),
        ),
    )

    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "no_progress"


def test_work_run_records_turn_and_goal_loop_policies(
    v2_service: AgentV2Service,
    principal: Principal,
):
    read_turn = v2_service.run_turn(
        principal,
        AgentTurnRequest(question="BoI Wiki 운영 가이드를 알려줘"),
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
    assert graph_score(record, {"단면검사"}, "/agent", "") == 0.0
    assert graph_score(record, {"단면검사"}, record.url, "") == 0.5


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


def test_search_is_acl_aware_excludes_drafts_and_stays_compact(v2_service: AgentV2Service, principal: Principal):
    result = v2_service.search.search("BoI Wiki 운영 가이드", principal, limit=8)
    ids = [item.evidence_id for item in result.items]
    assert ids[0] == "boi:public:guide"
    assert "boi:public:skill:smoke" not in ids
    assert "boi:private:100002:secret" not in ids
    response = v2_service.run_turn(principal, AgentTurnRequest(question="BoI Wiki 운영 가이드 찾아줘"))
    assert response.capability_id == "knowledge.search"
    assert response.answer.summary.startswith("검토된 근거 기준으로")
    assert len(json.dumps(response.model_dump(mode="json"), ensure_ascii=False).encode()) <= 8192
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

    assert response.answer.summary.startswith("초안은 검토 후 게시")
    assert "업무 지식과 실행 근거를 연결합니다." in response.answer.markdown
    assert "### 다음 점검 항목" in response.answer.markdown
    assert f"/api/v2/citations/{response.citations[0].citation_id}" in response.answer.markdown
    assert "source_numbers" not in response.answer.markdown


def test_source_set_pin_exclude_and_private_note_stay_in_one_session(
    v2_service: AgentV2Service,
    principal: Principal,
):
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
    assert note["artifact"]["capability_id"] == "knowledge.note"
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

    class EmbeddingModel(FakeModel):
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
    class EmbeddingModel(FakeModel):
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
    fake = FakeModel()
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
    model = FakeModel()
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
    waiting = v2_service.learning.get_run(principal, response.work_run_id)
    assert waiting["status"] == "waiting_human"
    waiting_goal = v2_service.get_goal_plan(principal, response.goal_plan_ref)
    waiting_steps = {item["step_id"]: item["status"] for item in waiting_goal["steps"]}
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
    fake = FakeModel()
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
            "exit_criteria": ["equipment.alarm.raised.v1 유형의 이벤트가 SOP 시작 트리거로 식별됨"],
            "required_evidence": ["boi:public:event-types:equipment.alarm.raised.v1"],
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

    assert expanded_job["subagent_budget_limit"] == 2
    assert expanded_job["max_subagents"] == 2
    assert expanded_job["max_parallelism"] == 2
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
    ("query_kind", "expected_presentation"),
    [
        ("neighbors", {"list", "explorer"}),
        ("workflow", {"mermaid", "explorer"}),
        ("impact", {"list", "explorer"}),
        ("lineage", {"mermaid", "explorer"}),
        ("responsibility", {"list", "explorer"}),
        ("timeline", {"timeline"}),
        ("compare", {"list", "explorer"}),
        ("tour", {"list", "explorer"}),
    ],
)
def test_universal_graph_query_kinds_keep_acl_provenance_and_auto_presentation(
    v2_service: AgentV2Service,
    principal: Principal,
    query_kind: str,
    expected_presentation: set[str],
):
    v2_service.knowledge.compile_graph(principal)
    result = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(
            focal_entities=["boi:public:sop:manual"],
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

    lineage = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="lineage", direction="both", depth=3),
    )
    assert {edge["relation"] for edge in lineage["edges"]} <= {
        "evidence", "requires_evidence", "derived_from", "produces", "results_in",
        "generated_from", "completed_by", "performed_by", "supersedes", "links_to",
    }
    assert lineage["lineage_refs"] == sorted(lineage["lineage_refs"])

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

    tour = v2_service.knowledge.query(
        principal,
        GraphQueryPlan(focal_entities=[focal], query_kind="tour", depth=3),
    )
    assert [item["order"] for item in tour["tour_steps"]] == list(range(1, len(tour["tour_steps"]) + 1))


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
        output = cwd / "graphify-out"
        output.mkdir(parents=True, exist_ok=True)
        (output / "graph.json").write_text(
            json.dumps({"nodes": [{"id": "service", "name": "BoI Service"}], "edges": []}),
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
    assert job["manifest"]["validation_report"]["node_count"] == 1
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

    def fake_run(command, *, cwd, timeout_seconds):
        if "add" in command:
            wiki = cwd / "wiki"
            (wiki / "concepts").mkdir(parents=True, exist_ok=True)
            (wiki / "index.md").write_text("# Navigation", encoding="utf-8")
            (wiki / "log.md").write_text("# Log", encoding="utf-8")
            (wiki / "concepts" / "alarm.md").write_text("# Alarm 판단\n\nTrend 범위를 먼저 맞춥니다.", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(v2_service.knowledge, "_run_adapter_command", fake_run)
    source = v2_service.knowledge.create_source(
        admin,
        KnowledgeSourceCreateRequest(name="OpenKB live CLI", source_kind="openkb", location=str(source_file)),
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
    assert retried["status"] == "completed"
    assert retried["attempt"] == 2


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
                failure_record_ids=[failure_id],
                changes={"acl": {"allow_all": True}},
                rationale="반복 실패를 해결하려는 후보지만 권한 경계는 바꿀 수 없습니다.",
            ),
        )

    assert getattr(caught.value, "status_code", None) == 400
    assert "acl" in caught.value.detail["immutable"]


def test_harness_candidate_requires_held_out_and_human_review_before_any_production_change(
    v2_service: AgentV2Service,
    principal: Principal,
):
    failure_id = "hfailure-retrieval"
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
    candidate = v2_service.learning.create_harness_candidate(
        principal,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=[failure_id],
            model_profile=v2_service.learning.model_profile,
            changes={"retrieval_policy": {"authority_weight": 1.2}},
            rationale="권위 있는 업무 근거가 반복적으로 누락되는 실패를 줄이기 위한 제한된 후보입니다.",
        ),
    )

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

    candidate = v2_service.learning.create_harness_candidate(
        principal,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=[failure_id],
            model_profile=v2_service.learning.model_profile,
            changes={"retrieval_policy": {"authority_weight": 1.1}},
            rationale="같은 실패군을 대상으로 held-out 회귀 없이 개선되는지 다시 검증하는 후보입니다.",
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
    for suffix in ("one", "two"):
        v2_service.learning._record_harness_failures(
            principal=principal,
            work_run={"work_run_id": f"work-run-{suffix}", "artifact_refs": []},
            context=context,
            results=[result],
            phase="preflight",
        )
    patterns = v2_service.learning.list_harness_failure_patterns(principal)["items"]
    assert len(patterns) == 1
    assert patterns[0]["occurrence_count"] == 2
    assert set(patterns[0]["work_run_ids"]) == {"work-run-one", "work-run-two"}


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
    assert continuation["status"] == "stopped"
    negatives = [v2_service.store.get("negative_results", item) for item in continuation["negative_result_ids"]]
    assert any(item and item["kind"] == "no_progress" for item in negatives)


def test_harness_improvement_relations_are_compiled_into_admin_ontology(
    v2_service: AgentV2Service,
    principal: Principal,
):
    admin = principal.model_copy(update={"roles": [*principal.roles, "boi.admin"]})
    pattern_id = "hpattern-ontology"
    failure_id = "hfailure-ontology"
    v2_service.store.put(
        "harness_failure_patterns",
        pattern_id,
        {"failure_pattern_id": pattern_id, "summary": "근거 누락 반복", "status": "open", "occurrence_count": 2},
    )
    v2_service.store.put(
        "harness_failure_records",
        failure_id,
        {
            "failure_record_id": failure_id,
            "failure_pattern_id": pattern_id,
            "employee_id": admin.employee_id,
            "harness_id": "context.work",
            "causal_agent_stage": "context.evidence",
            "status": "open",
        },
    )
    candidate = v2_service.learning.create_harness_candidate(
        admin,
        HarnessCandidateCreateRequest(
            harness_id="context.work",
            failure_record_ids=[failure_id],
            changes={"retrieval_policy": {"authority_weight": 1.1}},
            rationale="반복되는 근거 누락을 줄이기 위한 제한된 검색 정책 시험입니다.",
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
