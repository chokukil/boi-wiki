from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import uuid
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import HTTPException

from ..task_completion import normalise_task_completion
from .auth import PatService
from .a2ui import compile_surface, presentation_plan
from .capabilities import CapabilityRegistry
from .config import AgentV2Settings, deep_subagent_budget_limit
from .domain import DomainServiceGateway
from .entity_resolver import AmbiguousEntityError, EntityResolver
from .evaluation import IndependentArtifactEvaluator
from .harness import HarnessRegistry
from .knowledge_system import LivingKnowledgeService
from .model_gateway import (
    ModelGateway,
    begin_model_usage,
    build_model_gateway,
    ensure_lmstudio_model_residency,
    finish_model_usage,
    lmstudio_model_residency_state,
)
from .models import (
    AgentTurnRequest,
    AgentTurnResponse,
    AnswerBlock,
    ArtifactRef,
    ArtifactAction,
    CapabilityDefinition,
    CapabilityOffer,
    CapabilityPlanRequest,
    CapabilityState,
    CitationRef,
    ContextManifest,
    DeepJobRequest,
    EvidenceRef,
    GoalStep,
    GraphQueryDraft,
    GraphQueryPlan,
    HarnessValidateRequest,
    HarnessResult,
    HelperActivateRequest,
    HelperDraftCreateRequest,
    HelperDraftPatchRequest,
    HelperPreviewTurnRequest,
    LegacyHelperImportRequest,
    KnowledgeCandidateRef,
    KnowledgeCandidatePromoteRequest,
    LoopKind,
    LoopPolicy,
    LoopTriggerKind,
    LoopDelta,
    NextAction,
    NoteFromTurnRequest,
    OfferExecuteRequest,
    OfferRequest,
    OperationClass,
    Principal,
    ProposalApplyRequest,
    RelatedQuestion,
    ResolvedSourceRef,
    RiskLevel,
    SourceSetPatchRequest,
    StarterSuggestion,
    StarterSuggestionSetRequest,
    SkillArtifactActivateRequest,
    SkillArtifactTestRequest,
    SopArtifactPatchRequest,
    TaskMode,
    TaskCompletionDesign,
    TaskRefinePreviewRequest,
    WorkSessionCreateRequest,
    WorkSessionPatchRequest,
    WorkRunContinueRequest,
    WorkRoutineCreateRequest,
    WorkRoutineTriggerRequest,
    WorkAssetKind,
    WorkContextPack,
    WorkIntent,
    WorkOperation,
)
from .policy import TaskPolicy
from .quick_agent import QuickAgentRuntime
from .repository import KnowledgeRecord, KnowledgeRepository
from .rendering import render_agent_markdown
from .search import SEARCH_INDEX_SCHEMA_VERSION, HybridSearchService, best_chunk_for_query
from .store import AgentV2Store, build_store, now_iso
from .work_learning import WorkIntentEngine, WorkLearningService


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def compact_text(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def truncate_markdown(value: str, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    head = text[: max(1, limit - 3)]
    minimum = max(120, int(limit * 0.55))
    boundaries = [head.rfind("\n\n"), head.rfind("\n- "), head.rfind("\n")]
    cut = max((item for item in boundaries if item >= minimum), default=-1)
    if cut < 0:
        cut = head.rfind(" ")
    candidate = head[:cut if cut > 0 else len(head)].rstrip()
    if candidate.count("```") % 2:
        candidate = candidate[: candidate.rfind("```")].rstrip()
    if candidate.rfind("[") > candidate.rfind(")"):
        candidate = candidate[: candidate.rfind("[")].rstrip()
    return f"{candidate}\n\n…" if candidate else "…"


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


COMPLETION_DESIGN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "checks", "evidence"],
    "properties": {
        "version": {"const": 1},
        "checks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["label", "confirmation"],
                "properties": {
                    "check_id": {"type": "string"},
                    "label": {"type": "string"},
                    "confirmation": {"type": "string", "enum": ["human", "system"]},
                    "binding": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["none", "event", "action_result", "artifact", "data_field", "state"],
                            },
                            "ref": {"type": "string"},
                            "field": {"type": "string"},
                            "operator": {"type": "string"},
                            "value": {},
                        },
                    },
                },
            },
        },
        "evidence": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["label", "source_kind", "provided_by", "required"],
                "properties": {
                    "evidence_id": {"type": "string"},
                    "label": {"type": "string"},
                    "source_kind": {
                        "type": "string",
                        "enum": ["boi", "event", "action_result", "data_artifact", "file", "human_note", "external_ai"],
                    },
                    "ref": {"type": "string"},
                    "provided_by": {"type": "string", "enum": ["human", "agent", "system"]},
                    "required": {"type": "boolean"},
                },
            },
        },
    },
}


MERMAID_GRAPH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "nodes", "edges"],
    "properties": {
        "title": {"type": "string"},
        "nodes": {
            "type": "array",
            "minItems": 2,
            "maxItems": 14,
            "items": {
                "type": "object",
                "required": ["node_id", "label", "kind", "asset_kind", "source_numbers"],
                "properties": {
                    "node_id": {"type": "string"},
                    "label": {"type": "string"},
                    "kind": {"type": "string"},
                    "asset_kind": {
                        "type": "string",
                        "enum": [item.value for item in WorkAssetKind],
                    },
                    "source_numbers": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "integer"},
                    },
                },
            },
        },
        "edges": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "required": ["from", "to", "label", "source_numbers"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "label": {"type": "string"},
                    "source_numbers": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "integer"},
                    },
                },
            },
        },
        "related_questions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["kind", "label", "question", "source_numbers"],
                "properties": {
                    "kind": {"type": "string", "enum": ["understand", "connect", "apply"]},
                    "label": {"type": "string"},
                    "question": {"type": "string"},
                    "source_numbers": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
    },
}


DRAFT_SCHEMAS: dict[str, dict[str, Any]] = {
    "business_event.plan": {
        "type": "object",
        "required": ["title", "source_kind", "trigger_mode", "target_event_type", "conditions"],
        "properties": {
            "title": {"type": "string"},
            "source_kind": {"type": "string"},
            "trigger_mode": {"type": "string"},
            "target_event_type": {"type": "string"},
            "conditions": {"type": "object"},
            "fingerprint_fields": {"type": "array", "items": {"type": "string"}},
            "workflow_ref": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
        },
    },
    "sop.plan": {
        "type": "object",
        "required": ["title", "goal", "tasks", "mermaid"],
        "properties": {
            "title": {"type": "string"},
            "goal": {"type": "string"},
            "tasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "purpose", "execution_mode", "exit_criteria", "required_evidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "purpose": {"type": "string"},
                        "execution_mode": {"type": "string", "enum": ["manual", "copilot", "autopilot"]},
                        "exit_criteria": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "required_evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "completion_design": COMPLETION_DESIGN_SCHEMA,
                    },
                },
            },
            "mermaid": {"type": "string"},
            "gaps": {"type": "array", "items": {"type": "string"}},
        },
    },
    "action.plan": {
        "type": "object",
        "required": ["title", "connector", "inputs", "output_contract", "risk", "preview_only"],
        "properties": {
            "title": {"type": "string"},
            "connector": {"type": "string"},
            "inputs": {"type": "object"},
            "output_contract": {"type": "object"},
            "risk": {"type": "string"},
            "preview_only": {"type": "boolean"},
        },
    },
    "skill.plan": {
        "type": "object",
        "required": ["skill_id", "title", "description", "input_schema", "output_schema", "permissions", "tests"],
        "properties": {
            "skill_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "permissions": {"type": "array", "items": {"type": "string"}},
            "tests": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "sample_input", "expected_contains"],
                    "properties": {
                        "name": {"type": "string"},
                        "sample_input": {"type": "object"},
                        "expected_contains": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "available_actions": {"type": "array", "items": {"type": "string"}},
        },
    },
    "knowledge.draft": {
        "type": "object",
        "required": ["title", "summary", "body", "source_refs", "status"],
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "body": {"type": "string"},
            "source_refs": {"type": "array", "items": {"type": "string"}},
            "status": {"const": "provisional"},
        },
    },
    "work_routine.plan": {
        "type": "object",
        "required": [
            "title",
            "goal",
            "trigger",
            "schedule_description",
            "calendar",
            "routine_stop",
            "completion_condition",
        ],
        "properties": {
            "title": {"type": "string"},
            "goal": {"type": "string"},
            "trigger": {"type": "string", "enum": ["event", "schedule", "interval"]},
            "schedule_description": {"type": "string"},
            "calendar": {
                "type": "object",
                "required": ["minutes", "hours", "days_of_month", "months", "weekdays"],
                "properties": {
                    "minutes": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 59}},
                    "hours": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 23}},
                    "days_of_month": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 31}},
                    "months": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 12}},
                    "weekdays": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 6}},
                },
            },
            "interval_seconds": {"type": "integer", "minimum": 60, "maximum": 31536000},
            "cron": {"type": "string"},
            "timezone": {"type": "string"},
            "event_ref": {"type": "string"},
            "routine_stop": {"type": "string", "enum": ["cancelled", "max_runs", "event_resolved"]},
            "max_runs": {"type": "integer", "minimum": 0, "maximum": 10000},
            "completion_condition": {"type": "string"},
            "target_ref": {"type": "string"},
        },
    },
}


class AgentV2Service:
    SEMANTIC_ROUTE_CACHE_VERSION = "5"
    SEMANTIC_ROUTE_CACHE_TTL_SECONDS = 900
    STARTER_SUGGESTION_VERSION = "2"

    def __init__(
        self,
        settings: AgentV2Settings,
        *,
        identity_provider: Callable[[str], Principal] | None = None,
        domain_services: DomainServiceGateway | None = None,
        routine_target_executor: Callable[[dict[str, Any], WorkRoutineTriggerRequest, Principal], dict[str, Any]] | None = None,
        page_context_provider: Callable[[str, str], dict[str, Any]] | None = None,
        directory_provider: Callable[[], list[Principal]] | None = None,
    ):
        self.settings = settings
        self.store: AgentV2Store = build_store(settings)
        self.repository = KnowledgeRepository(settings)
        self.registry = CapabilityRegistry(settings.agent_catalog_root / "capabilities-v2.yaml")
        self.model: ModelGateway = build_model_gateway(settings)
        self.model_residency = lmstudio_model_residency_state(settings)
        self.search = HybridSearchService(self.repository, self.store, self.model)
        self.policy = TaskPolicy(self.repository, self.store)
        self.quick_agent = QuickAgentRuntime(self.registry)
        self.entity_resolver = EntityResolver(directory_provider)
        self.pats = PatService(self.store, settings.pat_hash_secret, identity_provider=identity_provider)
        self.harnesses = HarnessRegistry()
        self.evaluator = IndependentArtifactEvaluator(
            self.store,
            self.model,
            enabled=settings.independent_review,
        )
        self.domain_services = domain_services or DomainServiceGateway()
        self.routine_target_executor = routine_target_executor
        self.learning = WorkLearningService(
            store=self.store,
            repository=self.repository,
            search=self.search,
            harnesses=self.harnesses,
            page_context_provider=page_context_provider,
        )
        self.knowledge = LivingKnowledgeService(
            settings=self.settings,
            repository=self.repository,
            store=self.store,
            search=self.search,
            directory_provider=directory_provider,
        )

    def ensure_model_residency(self) -> dict[str, Any]:
        self.model_residency = ensure_lmstudio_model_residency(self.settings)
        return dict(self.model_residency)

    def _semantic_route_cache_key(self, principal: Principal, route_input: dict[str, Any]) -> str:
        model_state = self.model.readiness()
        payload = {
            "version": self.SEMANTIC_ROUTE_CACHE_VERSION,
            "employee_id": principal.employee_id,
            "team_ids": sorted(principal.teams),
            "roles": sorted(principal.roles),
            "is_admin": principal.is_admin,
            "model": {
                "provider": model_state.get("provider") or "",
                "name": model_state.get("model") or "",
            },
            "route_input": route_input,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return "semantic_route_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _semantic_route(
        self,
        principal: Principal,
        route_input: dict[str, Any],
    ) -> dict[str, Any]:
        cache_key = self._semantic_route_cache_key(principal, route_input)
        cached = self.store.get("semantic_routes", cache_key) or {}
        try:
            cache_valid = (
                cached.get("cache_version") == self.SEMANTIC_ROUTE_CACHE_VERSION
                and parse_time(str(cached.get("expires_at") or "")) > datetime.now(timezone.utc)
                and isinstance(cached.get("route"), dict)
            )
        except (TypeError, ValueError):
            cache_valid = False
        if cache_valid:
            return copy.deepcopy(cached["route"])

        route = self.quick_agent.route(**route_input, model=self.model)
        if route.get("source") == "llm_structured":
            self.store.put(
                "semantic_routes",
                cache_key,
                {
                    "cache_key": cache_key,
                    "cache_version": self.SEMANTIC_ROUTE_CACHE_VERSION,
                    "employee_id": principal.employee_id,
                    "route": copy.deepcopy(route),
                    "created_at": now_iso(),
                    "expires_at": (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=self.SEMANTIC_ROUTE_CACHE_TTL_SECONDS)
                    ).isoformat(),
                },
            )
        return route

    @staticmethod
    def _owns(principal: Principal, row: dict[str, Any]) -> bool:
        return str(row.get("employee_id") or "") == principal.employee_id or principal.is_admin

    def _require_owned(self, principal: Principal, row: dict[str, Any] | None, label: str) -> dict[str, Any]:
        if not row:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        if not self._owns(principal, row):
            raise HTTPException(status_code=403, detail=f"{label} belongs to another employee")
        return row

    def _completion_label_lookup(self, principal: Principal) -> dict[str, str]:
        lookup: dict[str, str] = {}
        identity_fields = (
            "boi_id",
            "event_type",
            "action_key",
            "workflow_definition_key",
            "skill_key",
            "term",
        )
        for record in self.repository.authoritative_records(principal, include_drafts=True):
            title = str(record.title or record.record_id).strip()
            if not title:
                continue
            lookup[record.record_id] = title
            for field in identity_fields:
                value = str(record.metadata.get(field) or "").strip()
                if value:
                    lookup[value] = title
                    if field == "event_type":
                        lookup[f"event:{value}"] = title
                        lookup[f"boi:public:event-types:{value}"] = title
                    elif field == "action_key":
                        lookup[f"action:{value}"] = title
                    elif field == "workflow_definition_key":
                        lookup[f"workflow:{value}"] = title
                        lookup[f"boi:public:workflows:{value}"] = title
                    elif field == "skill_key":
                        lookup[f"skill:{value}"] = title
            if ":" in record.record_id:
                suffix = record.record_id.split(":", 1)[1]
                if suffix:
                    lookup.setdefault(suffix, title)
        return lookup

    def _delete_expired_work_sessions(self, principal: Principal) -> None:
        now = datetime.now(timezone.utc)
        for session in self.store.list("work_sessions", employee_id=principal.employee_id, limit=500):
            if session.get("pinned") or session.get("status") == "archived":
                continue
            try:
                expired = parse_time(str(session.get("expires_at") or "")) <= now
            except (TypeError, ValueError):
                expired = False
            if not expired:
                continue
            session_id = str(session.get("session_id") or "")
            self.store.delete("work_sessions", session_id)
            for message in self.store.list("session_messages", employee_id=principal.employee_id, limit=5000):
                if message.get("session_id") == session_id:
                    self.store.delete("session_messages", str(message.get("message_id") or ""))

    def create_work_session(
        self,
        principal: Principal,
        request: WorkSessionCreateRequest | None = None,
    ) -> dict[str, Any]:
        self._delete_expired_work_sessions(principal)
        request = request or WorkSessionCreateRequest()
        session_id = new_id("ws")
        created_at = now_iso()
        session = {
            "session_id": session_id,
            "employee_id": principal.employee_id,
            "title": compact_text(request.title, 160) or "새 업무",
            "status": "active",
            "conversation_id": session_id,
            "conversation_summary": "",
            "active_artifact_id": "",
            "active_goal_plan_id": "",
            "source_set_id": self._source_set_id(session_id),
            "selected_task_id": "",
            "active_panel": "result",
            "page_ref": compact_text(request.page_ref, 1000),
            "helper_id": compact_text(request.helper_id, 120),
            "revision": 1,
            "pinned": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": created_at,
            "updated_at": created_at,
        }
        stored = self.store.put("work_sessions", session_id, session)
        self._ensure_source_set(principal, session_id)
        return stored

    def list_work_sessions(self, principal: Principal, *, limit: int = 20) -> dict[str, Any]:
        self._delete_expired_work_sessions(principal)
        items = self.store.list("work_sessions", employee_id=principal.employee_id, limit=max(1, min(limit, 100)))
        return {"count": len(items), "items": items}

    def starter_suggestions(
        self,
        principal: Principal,
        *,
        page_ref: str = "",
        limit: int = 8,
    ) -> list[StarterSuggestion]:
        """Build grounded entry points from work the principal can actually access."""

        suggestions: list[StarterSuggestion] = []
        used_categories: set[str] = set()
        area_counts: dict[str, int] = {}
        seen_suggestions: set[str] = set()
        area_for_category = {
            "current_work": "current_work",
            "knowledge_relation": "knowledge",
            "similar_case": "knowledge",
            "sop_task": "workflow",
            "business_event": "event_action",
            "action": "event_action",
            "knowledge_capture": "learning",
            "automatic_check": "automation",
        }

        def add(
            category: str,
            *,
            label: str,
            prompt: str,
            subject_ref: str,
            source_refs: list[str],
            reason: str,
            priority: int,
            area: str = "",
            context_basis: str = "",
            result_kind: str = "answer",
            graph_query_kind: str = "",
            fallback_to_answer: bool = False,
        ) -> None:
            refs = list(dict.fromkeys(str(item).strip() for item in source_refs if str(item).strip()))[:4]
            subject = str(subject_ref or "").strip()
            if not subject or not refs:
                return
            if graph_query_kind and result_kind in {"table", "timeline", "mermaid", "explorer"}:
                graph_subject = f"person:{principal.employee_id}" if graph_query_kind == "responsibility" else subject
                try:
                    graph_result = self.knowledge.query(
                        principal,
                        GraphQueryPlan(
                            focal_entities=[graph_subject],
                            query_kind=graph_query_kind,  # type: ignore[arg-type]
                            direction="both",
                            depth=2,
                            limit=24,
                            presentation=result_kind,  # type: ignore[arg-type]
                        ),
                    )
                except Exception:
                    graph_result = {}
                if not graph_result.get("edges"):
                    if not fallback_to_answer:
                        return
                    result_kind = "answer"
                    graph_query_kind = ""
            digest = hashlib.sha256(f"{category}:{subject}:{prompt}".encode("utf-8")).hexdigest()[:16]
            if digest in seen_suggestions:
                return
            resolved_area = area or area_for_category.get(category, "knowledge")
            subject_record = self._record_for_ref(principal, subject)
            suggestions.append(
                StarterSuggestion(
                    suggestion_id=f"suggestion_{digest}",
                    category=category,  # type: ignore[arg-type]
                    label=compact_text(label, 160),
                    prompt=compact_text(prompt, 1200),
                    subject_ref=subject,
                    source_refs=refs,
                    reason=compact_text(reason, 240),
                    priority=priority,
                    area=resolved_area,  # type: ignore[arg-type]
                    context_basis=context_basis or ("current_work" if category == "current_work" else "knowledge"),
                    subject_title=compact_text(str((subject_record.title if subject_record else "") or label), 160),
                    result_kind=result_kind,  # type: ignore[arg-type]
                    graph_query_kind=graph_query_kind,  # type: ignore[arg-type]
                )
            )
            seen_suggestions.add(digest)
            used_categories.add(category)
            area_counts[resolved_area] = area_counts.get(resolved_area, 0) + 1

        records = [
            item
            for item in self.repository.authoritative_records(principal)
            if item.authority in {"reviewed", "published"} and item.visibility in {"public", "team"}
        ]
        records_by_id = {item.record_id: item for item in records}

        def directly_connected_records(seed_refs: list[str]) -> list[KnowledgeRecord]:
            seeds = list(dict.fromkeys(str(item).strip() for item in seed_refs if str(item).strip()))
            if not seeds:
                return []
            candidate_refs: list[str] = []
            for seed in seeds:
                record = records_by_id.get(seed)
                if not record:
                    continue
                for key in ("source_refs", "related", "related_terms", "linked_boi_ids", "backlinks"):
                    value = record.metadata.get(key)
                    values = value if isinstance(value, list) else [value] if value else []
                    for candidate in values:
                        ref = str(
                            candidate.get("ref") or candidate.get("boi_id") or ""
                            if isinstance(candidate, dict)
                            else candidate or ""
                        ).strip()
                        resolved = self._record_for_ref(principal, ref) if ref else None
                        if resolved:
                            candidate_refs.append(str(resolved.record_id))
            try:
                graph = self.store.ontology_neighbors(
                    seeds,
                    depth=1,
                    limit=24,
                    employee_id=principal.employee_id,
                    team_ids=principal.teams,
                    include_all=principal.is_admin,
                )
                for edge in graph.get("edges") or []:
                    source_id = str(edge.get("source_id") or "")
                    target_id = str(edge.get("target_id") or "")
                    if source_id in seeds and target_id not in seeds:
                        candidate_refs.append(target_id)
                    elif target_id in seeds and source_id not in seeds:
                        candidate_refs.append(source_id)
            except Exception:
                pass
            return [
                records_by_id[ref]
                for ref in dict.fromkeys(candidate_refs)
                if ref in records_by_id and ref not in seeds
            ]

        current_work = self.repository.current_work(principal, limit=3)
        current = current_work[0] if current_work else None
        if current:
            add(
                "current_work",
                label="내 역할과 지금 맡은 일을 한눈에 보기",
                prompt=(
                    "내 공식 역할과 검증된 업무 관계를 현재 Inbox 업무와 구분해서 보여줘. "
                    f"지금은 '{current.title}'을 포함해 먼저 확인할 일을 표로 정리해줘."
                ),
                subject_ref=current.record_id,
                source_refs=[current.record_id],
                reason="현재 처리할 업무가 있습니다.",
                priority=10,
                result_kind="table",
                graph_query_kind="responsibility",
            )
            add(
                "similar_case",
                label=f"'{current.title}'와 비슷한 사례 보기",
                prompt=f"'{current.title}'와 업무 맥락과 결과가 비슷한 과거 사례를 근거와 함께 비교해줘.",
                subject_ref=current.record_id,
                source_refs=[current.record_id],
                reason="현재 업무에 참고할 과거 결과를 찾습니다.",
                priority=30,
                result_kind="table",
                graph_query_kind="compare",
                fallback_to_answer=True,
            )

        page_anchor = self.learning.contexts.page_anchor(principal, page_ref)
        if page_anchor and page_anchor.resolved:
            page_record = self._record_for_ref(principal, page_anchor.ref)
        else:
            page_record = None
        if page_anchor and page_anchor.resolved and page_record:
            page_neighbors = directly_connected_records([page_anchor.ref])
            related_refs = [item.record_id for item in page_neighbors]
            page_source_refs = list(dict.fromkeys([page_anchor.ref, *related_refs]))[:4]
            add(
                "knowledge_relation",
                label=f"{page_anchor.title}의 핵심과 연결 관계 보기",
                prompt=(
                    f"현재 보고 있는 {page_anchor.title}의 핵심을 설명하고, "
                    "Wiki 전체에서 실제로 연결된 내용만 근거와 함께 보여줘."
                ),
                subject_ref=page_anchor.ref,
                source_refs=page_source_refs,
                reason="현재 화면을 출발점으로 Wiki 전체의 관계를 살펴봅니다.",
                priority=20,
                result_kind="mermaid",
                graph_query_kind="neighbors",
                fallback_to_answer=True,
            )
            if not current:
                add(
                    "similar_case",
                    label=f"{page_anchor.title}와 닮은 사례 보기",
                    prompt=f"{page_anchor.title}와 관련된 실제 처리 사례와 결과를 찾아 차이점을 비교해줘.",
                    subject_ref=page_anchor.ref,
                    source_refs=[page_anchor.ref],
                    reason="현재 화면과 관련된 과거 처리 결과를 찾습니다.",
                    priority=35,
                    result_kind="table",
                    graph_query_kind="compare",
                    fallback_to_answer=True,
                )

        recent_artifact: dict[str, Any] | None = None
        for work_session in self.store.list("work_sessions", employee_id=principal.employee_id, limit=10):
            artifact_id = str(work_session.get("active_artifact_id") or "")
            artifact = self.store.get("artifacts", artifact_id) if artifact_id else None
            if artifact and self._owns(principal, artifact):
                recent_artifact = artifact
                break
        if recent_artifact:
            artifact_ref = str(recent_artifact["artifact_id"])
            artifact_title = str(recent_artifact.get("title") or "최근 작업 결과")
            if str(recent_artifact.get("artifact_type") or "").startswith("sop"):
                add(
                    "sop_task",
                    label=f"'{artifact_title}' Task 이어서 다듬기",
                    prompt=f"최근 만든 '{artifact_title}'을 열어 Task별 목적, 완료된 모습과 확인할 자료를 함께 다듬어줘.",
                    subject_ref=artifact_ref,
                    source_refs=[artifact_ref],
                    reason="최근 저장한 SOP 초안을 이어서 작업합니다.",
                    priority=25,
                    result_kind="work_form",
                    graph_query_kind="workflow",
                )
            add(
                "knowledge_capture",
                label=f"'{artifact_title}'에서 재사용할 내용 남기기",
                prompt=f"최근 작업한 '{artifact_title}'에서 다음 업무에도 재사용할 판단과 근거만 private 지식 후보로 정리해줘.",
                subject_ref=artifact_ref,
                source_refs=[artifact_ref],
                reason="최근 결과에서 재사용 가치가 있는 내용을 남깁니다.",
                priority=70,
                result_kind="timeline",
                graph_query_kind="lineage",
            )

        suggestion_anchor = page_record
        if "knowledge_relation" not in used_categories:
            record = next(
                (
                    item
                    for item in records
                    if "knowledge" in (item.metadata.get("agent_entrypoint_areas") or [])
                ),
                next((item for item in records if str(item.metadata.get("type") or "") == "boi/manual"), None),
            )
            if record:
                suggestion_anchor = record
                add(
                    "knowledge_relation",
                    label=f"{record.title}부터 BoI Wiki 살펴보기",
                    prompt=f"검토된 지식 {record.title}의 핵심과 실제로 연결된 내용을 Wiki 전체 근거로 설명해줘.",
                    subject_ref=record.record_id,
                    source_refs=[record.record_id],
                    reason="현재 맥락이 없어 검토된 공용 지식에서 시작합니다.",
                    priority=40,
                    result_kind="explorer",
                    graph_query_kind="neighbors",
                    fallback_to_answer=True,
                )

        connected_records = directly_connected_records([suggestion_anchor.record_id]) if suggestion_anchor else []
        if suggestion_anchor and "sop_task" not in used_categories:
            record = next((item for item in connected_records if item.kind in {"sop", "workflow"}), None)
            if record:
                add(
                    "sop_task",
                    label=f"{suggestion_anchor.title}와 연결된 '{record.title}' 보기",
                    prompt=(
                        f"'{suggestion_anchor.title}'과 '{record.title}'이 실제로 어떻게 연결되는지, "
                        "업무 흐름과 근거를 쉽게 설명해줘."
                    ),
                    subject_ref=record.record_id,
                    source_refs=[record.record_id, suggestion_anchor.record_id],
                    reason="현재 맥락과 직접 연결된 검토된 업무 흐름입니다.",
                    priority=50,
                    result_kind="mermaid",
                    graph_query_kind="workflow",
                )
        event_record = next((item for item in connected_records if item.kind == "event"), None)
        if event_record:
            add(
                "business_event",
                label=f"{suggestion_anchor.title}와 연결된 '{event_record.title}' 보기",
                prompt=(
                    f"'{suggestion_anchor.title}'과 업무 이벤트 '{event_record.title}'의 실제 연결 관계와 "
                    "발생 조건, 이어지는 결과를 근거와 함께 보여줘."
                ),
                subject_ref=event_record.record_id,
                source_refs=[event_record.record_id, suggestion_anchor.record_id],
                reason="현재 맥락과 직접 연결된 검토된 업무 이벤트입니다.",
                priority=60,
                result_kind="explorer",
                graph_query_kind="impact",
            )
        action_record = next((item for item in connected_records if item.kind == "action"), None)
        if action_record:
            add(
                "action",
                label=f"{suggestion_anchor.title}와 연결된 '{action_record.title}' 보기",
                prompt=(
                    f"'{suggestion_anchor.title}'에서 Action '{action_record.title}'을 어디에 사용하는지, "
                    "입력과 결과 및 실행 전 확인할 근거를 설명해줘."
                ),
                subject_ref=action_record.record_id,
                source_refs=[action_record.record_id, suggestion_anchor.record_id],
                reason="현재 맥락과 직접 연결된 검토된 Action입니다.",
                priority=65,
                result_kind="confirmation",
                graph_query_kind="impact",
            )

        automatic_subject = current or (
            self._record_for_ref(principal, page_anchor.ref)
            if page_anchor and page_anchor.resolved
            else None
        )
        if automatic_subject:
            add(
                "automatic_check",
                label=f"'{automatic_subject.title}' 다시 확인하도록 계획하기",
                prompt=(
                    f"'{automatic_subject.title}'을 정해진 시간이나 상태 변화에 따라 다시 확인하는 "
                    "자동 확인 계획을 먼저 보여줘. 만들기 전에는 내 확인을 받아줘."
                ),
                subject_ref=automatic_subject.record_id,
                source_refs=[automatic_subject.record_id],
                reason="현재 대상의 변화를 놓치지 않도록 확인 계획을 만듭니다.",
                priority=80,
                result_kind="confirmation",
                graph_query_kind="timeline",
            )

        entrypoint_categories = {
            "current_work": "knowledge_relation",
            "knowledge": "knowledge_relation",
            "workflow": "sop_task",
            "event_action": "business_event",
            "learning": "knowledge_capture",
            "automation": "automatic_check",
        }
        entrypoint_priorities = {
            "current_work": 90,
            "knowledge": 91,
            "workflow": 92,
            "event_action": 93,
            "learning": 94,
            "automation": 95,
        }
        entrypoint_results = {
            "current_work": ("table", "responsibility"),
            "knowledge": ("explorer", "neighbors"),
            "workflow": ("mermaid", "workflow"),
            "event_action": ("explorer", "impact"),
            "learning": ("timeline", "lineage"),
            "automation": ("confirmation", "timeline"),
        }
        for area, category in entrypoint_categories.items():
            if area_counts.get(area):
                continue
            record = next(
                (
                    item
                    for item in records
                    if area in (item.metadata.get("agent_entrypoint_areas") or [])
                ),
                None,
            )
            if not record:
                continue
            prompts = record.metadata.get("agent_entrypoint_prompts") or {}
            prompt_spec = prompts.get(area) if isinstance(prompts, dict) else None
            if isinstance(prompt_spec, dict):
                entry_label = str(prompt_spec.get("label") or record.title)
                entry_prompt = str(prompt_spec.get("prompt") or f"'{record.title}'을 바탕으로 이 업무 영역에서 할 수 있는 일을 근거와 함께 설명해줘.")
                entry_reason = str(prompt_spec.get("reason") or "검토된 시작 지식에서 살펴봅니다.")
            else:
                entry_label = f"{record.title}에서 시작하기"
                entry_prompt = f"검토된 지식 '{record.title}'을 바탕으로 이 업무 영역에서 할 수 있는 일을 근거와 함께 설명해줘."
                entry_reason = "검토된 시작 지식에서 살펴봅니다."
            add(
                category,
                label=entry_label,
                prompt=entry_prompt,
                subject_ref=record.record_id,
                source_refs=[record.record_id],
                reason=entry_reason,
                priority=entrypoint_priorities[area],
                area=area,
                context_basis="canonical_entrypoint",
                result_kind=entrypoint_results[area][0],
                graph_query_kind=entrypoint_results[area][1],
                fallback_to_answer=True,
            )

        suggestions.sort(key=lambda item: (item.priority, item.label))
        for index, item in enumerate(suggestions):
            item.featured = index < 4
        return suggestions[: max(1, min(limit, 18))]

    def create_starter_suggestion_set(
        self,
        principal: Principal,
        request: StarterSuggestionSetRequest,
    ) -> dict[str, Any]:
        starters = self.starter_suggestions(principal, page_ref=request.page_ref, limit=18)
        source = [item.model_dump(mode="json") for item in starters]
        fingerprint_payload = {
            "version": self.STARTER_SUGGESTION_VERSION,
            "employee_id": principal.employee_id,
            "teams": principal.teams,
            "page_ref": request.page_ref,
            "work_session_id": request.work_session_id,
            "source_revision": self.repository.source_signature(),
            "starters": [(item["suggestion_id"], item["subject_ref"], item["priority"]) for item in source],
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")).hexdigest()
        set_id = f"starterset_{fingerprint[:24]}"
        existing = self.store.get("starter_suggestion_sets", set_id)
        if existing and existing.get("employee_id") == principal.employee_id:
            return existing
        created = {
            "set_id": set_id,
            "employee_id": principal.employee_id,
            "page_ref": request.page_ref,
            "work_session_id": request.work_session_id,
            "context_fingerprint": fingerprint,
            "state": "updating" if source else "ready",
            "items": source,
            "refined": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        stored = self.store.put("starter_suggestion_sets", set_id, created)
        if source:
            threading.Thread(
                target=self._refine_starter_suggestion_set,
                args=(set_id, principal, source),
                name=f"boi-starter-refine-{set_id[-8:]}",
                daemon=True,
            ).start()
        return stored

    def _refine_starter_suggestion_set(
        self,
        set_id: str,
        principal: Principal,
        source: list[dict[str, Any]],
    ) -> None:
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "suggestion_id": {"type": "string"},
                            "label": {"type": "string"},
                            "prompt": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["suggestion_id", "label", "prompt", "reason"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }
        try:
            generated = self.model.generate_structured(
                system=(
                    "You rank and rewrite grounded BoI Agent starter questions in concise Korean. "
                    "Preserve suggestion_id and business meaning. Never invent a source, subject, capability, or current task. "
                    "Prefer personal current work, then page context, recent work, team knowledge, and reviewed public entrypoints."
                ),
                prompt=json.dumps(
                    {
                        "identity": {"teams": principal.teams, "roles": principal.roles},
                        "instructions": "Return the useful items in best order. Keep at least one item per available area.",
                        "candidates": [
                            {key: item.get(key) for key in ("suggestion_id", "area", "label", "prompt", "reason", "subject_title", "context_basis")}
                            for item in source
                        ],
                    },
                    ensure_ascii=False,
                ),
                schema=schema,
            )
            allowed = {str(item.get("suggestion_id")): item for item in source}
            refined: list[dict[str, Any]] = []
            used: set[str] = set()
            for row in generated.get("items") or []:
                suggestion_id = str(row.get("suggestion_id") or "")
                original = allowed.get(suggestion_id)
                if not original or suggestion_id in used:
                    continue
                refined.append(
                    {
                        **original,
                        "label": compact_text(str(row.get("label") or original.get("label") or ""), 160),
                        "prompt": compact_text(str(row.get("prompt") or original.get("prompt") or ""), 1200),
                        "reason": compact_text(str(row.get("reason") or original.get("reason") or ""), 240),
                    }
                )
                used.add(suggestion_id)
            refined.extend(item for item in source if str(item.get("suggestion_id")) not in used)
            for index, item in enumerate(refined):
                item["featured"] = index < 4
            current = self.store.get("starter_suggestion_sets", set_id) or {}
            if current.get("employee_id") != principal.employee_id:
                return
            self.store.put(
                "starter_suggestion_sets",
                set_id,
                {**current, "state": "ready", "items": refined, "refined": True, "updated_at": now_iso()},
            )
        except Exception:
            current = self.store.get("starter_suggestion_sets", set_id) or {}
            if current.get("employee_id") == principal.employee_id:
                self.store.put(
                    "starter_suggestion_sets",
                    set_id,
                    {**current, "state": "ready", "refined": False, "updated_at": now_iso()},
                )

    def get_starter_suggestion_set(self, principal: Principal, set_id: str) -> dict[str, Any]:
        item = self.store.get("starter_suggestion_sets", set_id)
        if not item or item.get("employee_id") != principal.employee_id:
            raise HTTPException(status_code=404, detail="starter suggestion set not found")
        return item

    def user_work_profile(self, principal: Principal) -> dict[str, Any]:
        """Build the small, replaceable read model used for contextual turns."""

        current_work = self.repository.current_work(principal, limit=5)
        sessions = self.store.list("work_sessions", employee_id=principal.employee_id, limit=12)
        sessions = [item for item in sessions if str(item.get("status") or "active") == "active"][:6]
        recent_artifacts: list[dict[str, Any]] = []
        used_sources: list[str] = []
        for session in sessions:
            artifact_id = str(session.get("active_artifact_id") or "")
            artifact = self.store.get("artifacts", artifact_id) if artifact_id else None
            if artifact and self._owns(principal, artifact):
                recent_artifacts.append(
                    {
                        "artifact_id": artifact_id,
                        "title": compact_text(str(artifact.get("title") or ""), 160),
                        "artifact_type": str(artifact.get("artifact_type") or ""),
                        "status": str(artifact.get("status") or "draft"),
                        "updated_at": str(artifact.get("updated_at") or artifact.get("created_at") or ""),
                    }
                )
            source_set = self.store.get("source_sets", self._source_set_id(str(session.get("session_id") or "")))
            if source_set:
                used_sources.extend(str(ref) for ref in source_set.get("auto_selected") or [] if str(ref))
                used_sources.extend(str(ref) for ref in source_set.get("pinned") or [] if str(ref))
        profile = {
            "profile_id": f"work-profile:{principal.employee_id}",
            "employee_id": principal.employee_id,
            "teams": list(principal.teams),
            "current_work": [
                {
                    "ref": item.record_id,
                    "title": compact_text(item.title, 160),
                    "status": item.status,
                    "url": item.url,
                }
                for item in current_work
            ],
            "recent_sessions": [
                {
                    "session_id": str(item.get("session_id") or ""),
                    "title": compact_text(str(item.get("title") or ""), 120),
                    "active_artifact_id": str(item.get("active_artifact_id") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                }
                for item in sessions
            ],
            "recent_artifacts": recent_artifacts[:6],
            "recently_used_source_refs": list(dict.fromkeys(used_sources))[:16],
            "source_revision": self.repository.source_signature(),
            "updated_at": now_iso(),
        }
        return self.store.put("user_work_profiles", principal.employee_id, profile)

    def _apply_starter_suggestion(self, principal: Principal, request: AgentTurnRequest) -> None:
        suggestion_id = str(request.suggestion_id or "").strip()
        if not suggestion_id:
            return
        suggestion = None
        suggestion_set_id = str(request.suggestion_set_id or "").strip()
        if suggestion_set_id:
            stored_set = self.store.get("starter_suggestion_sets", suggestion_set_id) or {}
            if stored_set.get("employee_id") == principal.employee_id:
                stored_item = next(
                    (item for item in stored_set.get("items") or [] if item.get("suggestion_id") == suggestion_id),
                    None,
                )
                if stored_item:
                    try:
                        suggestion = StarterSuggestion.model_validate(stored_item)
                    except Exception:
                        suggestion = None
        if suggestion is None:
            suggestion = next(
                (
                    item
                    for item in self.starter_suggestions(principal, page_ref=request.page_ref, limit=18)
                    if item.suggestion_id == suggestion_id
                ),
                None,
            )
        if suggestion is None:
            request.input_delta["_starter_suggestion_status"] = "stale"
            return
        request.question = suggestion.prompt
        request.input_delta.update(
            {
                "_starter_suggestion_status": "resolved",
                "_starter_suggestion_id": suggestion.suggestion_id,
                "_starter_subject_ref": suggestion.subject_ref,
                "_starter_source_refs": list(suggestion.source_refs),
                "_starter_result_kind": suggestion.result_kind,
                "_starter_graph_query_kind": suggestion.graph_query_kind,
            }
        )

    def get_work_session(self, principal: Principal, session_id: str) -> dict[str, Any]:
        return self._require_owned(principal, self.store.get("work_sessions", session_id), "work session")

    @staticmethod
    def _source_set_id(session_id: str) -> str:
        return f"sources_{session_id}"

    def _ensure_source_set(self, principal: Principal, session_id: str) -> dict[str, Any]:
        self.get_work_session(principal, session_id)
        source_set_id = self._source_set_id(session_id)
        existing = self.store.get("source_sets", source_set_id)
        if existing:
            return self._require_owned(principal, existing, "source set")
        created = {
            "source_set_id": source_set_id,
            "work_session_id": session_id,
            "employee_id": principal.employee_id,
            "auto_selected": [],
            "related": [],
            "pinned": [],
            "excluded": [],
            "attached": [],
            "snapshot_revision": self.repository.source_signature(),
            "revision": 1,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        return self.store.put("source_sets", source_set_id, created)

    def _source_item(self, principal: Principal, ref: str, *, state: str) -> dict[str, Any]:
        clean = str(ref or "").strip()
        records = self.repository.authoritative_records(principal, include_drafts=True)
        records.extend(self.repository.history_records(principal, include_seed=True))
        record = next((item for item in records if item.record_id == clean), None)
        if record:
            return {
                "source_ref": record.record_id,
                "title": record.title,
                "kind": record.kind,
                "summary": compact_text(record.description or record.text, 240),
                "url": record.url,
                "authority": record.authority,
                "state": state,
            }
        if clean.startswith("artifact_"):
            artifact = self.store.get("artifacts", clean) or {}
            if artifact and self._owns(principal, artifact):
                return {
                    "source_ref": clean,
                    "title": str(artifact.get("title") or "private 지식 노트"),
                    "kind": "note",
                    "summary": compact_text(str((artifact.get("draft") or {}).get("body") or artifact.get("preview") or ""), 240),
                    "url": f"/agent?session={artifact.get('work_session_id') or ''}&artifact={clean}",
                    "authority": "provisional",
                    "state": state,
                }
        return {
            "source_ref": clean,
            "title": clean,
            "kind": "external",
            "summary": "연결된 외부 참고 자료",
            "url": clean if clean.startswith(("http://", "https://", "/")) else "",
            "authority": "unreviewed",
            "state": state,
        }

    def get_source_set(self, principal: Principal, session_id: str) -> dict[str, Any]:
        source_set = self._ensure_source_set(principal, session_id)
        groups = {
            "used": [self._source_item(principal, ref, state="used") for ref in source_set.get("auto_selected") or []],
            "related": [self._source_item(principal, ref, state="related") for ref in source_set.get("related") or []],
            "pinned": [self._source_item(principal, ref, state="pinned") for ref in source_set.get("pinned") or []],
            "attached": [self._source_item(principal, ref, state="attached") for ref in source_set.get("attached") or []],
        }
        return {**source_set, "groups": groups}

    def patch_source_set(
        self,
        principal: Principal,
        session_id: str,
        request: SourceSetPatchRequest,
    ) -> dict[str, Any]:
        source_set = self._ensure_source_set(principal, session_id)
        current_revision = int(source_set.get("revision") or 1)
        if request.expected_revision != current_revision:
            raise HTTPException(
                status_code=409,
                detail={"status": "revision_conflict", "current_revision": current_revision, "source_set": self.get_source_set(principal, session_id)},
            )
        pinned = list(dict.fromkeys(str(item) for item in source_set.get("pinned") or [] if str(item).strip()))
        excluded = list(dict.fromkeys(str(item) for item in source_set.get("excluded") or [] if str(item).strip()))
        for ref in request.pin_refs:
            if ref not in pinned:
                pinned.append(ref)
            if ref in excluded:
                excluded.remove(ref)
        for ref in request.unpin_refs:
            if ref in pinned:
                pinned.remove(ref)
        for ref in request.exclude_refs:
            if ref not in excluded:
                excluded.append(ref)
            if ref in pinned:
                pinned.remove(ref)
        for ref in request.include_refs:
            if ref in excluded:
                excluded.remove(ref)
        source_set.update(
            {
                "pinned": pinned[:100],
                "excluded": excluded[:100],
                "auto_selected": [
                    ref for ref in source_set.get("auto_selected") or [] if ref not in set(excluded)
                ][:12],
                "related": [
                    ref for ref in source_set.get("related") or [] if ref not in set(excluded)
                ][:12],
                "attached": (
                    list(dict.fromkeys(str(item) for item in request.attached_refs if str(item).strip()))[:100]
                    if request.attached_refs is not None
                    else source_set.get("attached") or []
                ),
                "revision": current_revision + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("source_sets", str(source_set["source_set_id"]), source_set)
        return self.get_source_set(principal, session_id)

    def _update_auto_sources(
        self,
        principal: Principal,
        session_id: str,
        evidence: list[EvidenceRef],
        attached_refs: list[str],
        *,
        used_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        source_set = self._ensure_source_set(principal, session_id)
        excluded = {str(item) for item in source_set.get("excluded") or []}
        available_refs = [item.evidence_id for item in evidence if item.evidence_id not in excluded]
        used = [ref for ref in (used_refs or available_refs) if ref in available_refs]
        auto_selected = list(dict.fromkeys(used))[:12]
        related = [ref for ref in available_refs if ref not in set(auto_selected)][:12]
        attached = list(source_set.get("attached") or [])
        for ref in attached_refs:
            if ref and ref not in attached:
                attached.append(ref)
        source_set.update(
            {
                "auto_selected": auto_selected,
                "related": related,
                "attached": attached[:100],
                "snapshot_revision": self.repository.source_signature(),
                "revision": int(source_set.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("source_sets", str(source_set["source_set_id"]), source_set)
        return source_set

    def patch_work_session(
        self,
        principal: Principal,
        session_id: str,
        request: WorkSessionPatchRequest,
    ) -> dict[str, Any]:
        session = self.get_work_session(principal, session_id)
        current_revision = int(session.get("revision") or 1)
        if request.expected_revision != current_revision:
            raise HTTPException(
                status_code=409,
                detail={"status": "revision_conflict", "current_revision": current_revision, "session": session},
            )
        values = request.model_dump(exclude_unset=True)
        values.pop("expected_revision", None)
        for key, value in values.items():
            session[key] = value
        session.update(
            {
                "revision": current_revision + 1,
                "updated_at": now_iso(),
                "expires_at": (
                    session.get("expires_at")
                    if session.get("pinned")
                    else (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                ),
            }
        )
        return self.store.put("work_sessions", session_id, session)

    def continue_work_run(
        self,
        principal: Principal,
        work_run_id: str,
        request: WorkRunContinueRequest,
    ) -> dict[str, Any]:
        run, candidates = self.learning.continue_run(principal, work_run_id, request)
        messages = {
            "completed": "완료된 모습과 확인할 근거가 충족되어 업무를 완료했습니다.",
            "waiting_human": "추가 확인이나 담당자 입력이 필요합니다.",
            "waiting_signal": "연결된 시스템의 확인 결과를 기다리고 있습니다.",
            "in_progress": "새로운 근거를 반영해 업무를 이어갑니다.",
            "stopped": "진전 없는 반복을 막기 위해 멈췄습니다. 다른 근거나 담당자 확인이 필요합니다.",
            "blocked": "업무를 이어가기 전에 보완할 항목이 있습니다.",
        }
        message = messages.get(str(run.get("status") or ""), "업무 진행 상태를 갱신했습니다.")
        session_id = str(run.get("work_session_id") or "")
        if session_id:
            session = self.store.get("work_sessions", session_id)
            if session and self._owns(principal, session):
                agent_run = self.store.get("runs", str(run.get("agent_run_id") or "")) or {}
                capability_id = str(agent_run.get("capability_id") or "knowledge.search")
                self._append_session_message(
                    principal,
                    session_id,
                    role="user",
                    display_text=request.delta.summary,
                    run_id=str(run.get("agent_run_id") or ""),
                    capability_id=capability_id,
                    work_run_id=work_run_id,
                )
                loop_state = {
                    "iteration_count": (run.get("loop") or {}).get("iteration_count") or 0,
                    "decision": run.get("decision") or "",
                    "status": run.get("status") or "",
                    "revision": run.get("revision") or 1,
                }
                self._append_session_message(
                    principal,
                    session_id,
                    role="assistant",
                    display_text=message,
                    run_id=str(run.get("agent_run_id") or ""),
                    capability_id=capability_id,
                    work_run_id=work_run_id,
                    loop_state=loop_state,
                    knowledge_candidates=candidates,
                )
                session.update(
                    {
                        "active_work_run_id": work_run_id,
                        "revision": int(session.get("revision") or 1) + 1,
                        "updated_at": now_iso(),
                    }
                )
                self.store.put("work_sessions", session_id, session)
        return {
            "work_run": run,
            "message": message,
            "knowledge_candidates": [item.model_dump(mode="json") for item in candidates],
        }

    def session_timeline(self, principal: Principal, session_id: str, *, limit: int = 100) -> dict[str, Any]:
        self.get_work_session(principal, session_id)
        items = [
            item
            for item in self.store.list("session_messages", employee_id=principal.employee_id, limit=5000)
            if item.get("session_id") == session_id
        ]
        items.sort(key=lambda item: str(item.get("created_at") or ""))
        items = items[-max(1, min(limit, 300)) :]
        items = [
            {
                **item,
                "display_html": (
                    str(item.get("display_html") or "")
                    or render_agent_markdown(str(item.get("display_text") or ""))
                ),
            }
            if item.get("role") == "assistant"
            else item
            for item in items
        ]
        return {"count": len(items), "items": items}

    def work_session_bundle(self, principal: Principal, session_id: str) -> dict[str, Any]:
        session = self.get_work_session(principal, session_id)
        artifact = None
        if session.get("active_artifact_id"):
            try:
                artifact = self.get_artifact(principal, str(session["active_artifact_id"]))
            except HTTPException:
                artifact = None
        return {
            "session": session,
            "timeline": self.session_timeline(principal, session_id)["items"],
            "active_artifact": artifact,
            "source_set": self.get_source_set(principal, session_id),
        }

    def delete_work_session(self, principal: Principal, session_id: str) -> dict[str, Any]:
        self.get_work_session(principal, session_id)
        deleted_messages = 0
        deleted_artifacts = 0
        for message in self.store.list("session_messages", employee_id=principal.employee_id, limit=5000):
            if message.get("session_id") == session_id:
                deleted_messages += int(self.store.delete("session_messages", str(message.get("message_id") or "")))
        for artifact in self.store.list("artifacts", employee_id=principal.employee_id, limit=5000):
            if artifact.get("work_session_id") != session_id or artifact.get("status") not in {"draft", "provisional"}:
                continue
            artifact_id = str(artifact.get("artifact_id") or "")
            deleted_artifacts += int(self.store.delete("artifacts", artifact_id))
            for revision in self.store.list("artifact_revisions", employee_id=principal.employee_id, limit=5000):
                if revision.get("artifact_id") == artifact_id:
                    self.store.delete("artifact_revisions", str(revision.get("revision_id") or ""))
        self.store.delete("work_sessions", session_id)
        self.store.delete("source_sets", self._source_set_id(session_id))
        return {
            "session_id": session_id,
            "status": "deleted",
            "deleted_messages": deleted_messages,
            "deleted_draft_artifacts": deleted_artifacts,
        }

    def _append_session_message(
        self,
        principal: Principal,
        session_id: str,
        *,
        role: str,
        display_text: str,
        run_id: str = "",
        capability_id: str = "",
        evidence_refs: list[EvidenceRef] | None = None,
        artifact_refs: list[ArtifactRef] | None = None,
        next_actions: list[NextAction] | None = None,
        citations: list[CitationRef] | None = None,
        related_questions: list[RelatedQuestion] | None = None,
        goal_plan_ref: str = "",
        source_set_ref: str = "",
        work_run_id: str = "",
        loop_state: dict[str, Any] | None = None,
        harness_results: list[HarnessResult] | None = None,
        knowledge_candidates: list[KnowledgeCandidateRef] | None = None,
    ) -> dict[str, Any]:
        message_id = new_id("msg")
        limit = 4000 if role == "user" else 8000
        payload = {
            "message_id": message_id,
            "session_id": session_id,
            "employee_id": principal.employee_id,
            "role": role,
            "display_text": (
                str(display_text or "")[:limit]
                if role == "user"
                else truncate_markdown(str(display_text or ""), limit)
            ),
            "display_html": render_agent_markdown(str(display_text or "")) if role == "assistant" else "",
            "run_id": run_id,
            "capability_id": capability_id,
            "evidence_refs": [
                {
                    "evidence_id": item.evidence_id,
                    "kind": item.kind,
                    "title": item.title,
                    "summary": compact_text(item.summary, 240),
                    "url": item.url,
                    "source": item.source,
                    "score": item.score,
                }
                for item in (evidence_refs or [])[:8]
            ],
            "artifact_refs": [item.model_dump(mode="json") for item in (artifact_refs or [])[:3]],
            "next_actions": [item.model_dump(mode="json") for item in (next_actions or [])[:3]],
            "citations": [item.model_dump(mode="json") for item in (citations or [])[:8]],
            "related_questions": [item.model_dump(mode="json") for item in (related_questions or [])[:3]],
            "goal_plan_ref": goal_plan_ref,
            "source_set_ref": source_set_ref,
            "work_run_id": work_run_id,
            "loop_state": loop_state or {},
            "harness_results": [item.model_dump(mode="json") for item in (harness_results or [])],
            "knowledge_candidates": [item.model_dump(mode="json") for item in (knowledge_candidates or [])],
            "created_at": now_iso(),
        }
        return self.store.put("session_messages", message_id, payload)

    def _session_context(self, principal: Principal, session: dict[str, Any]) -> dict[str, Any]:
        timeline = self.session_timeline(principal, str(session["session_id"]), limit=100)["items"]
        recent = timeline[-6:]
        older = timeline[:-6]
        summary = str(session.get("conversation_summary") or "")
        if older:
            fragments = [
                f"{item.get('role')}: {compact_text(str(item.get('display_text') or ''), 220)}"
                for item in older[-12:]
            ]
            summary = compact_text(" ".join([summary, *fragments]), 2000)
        artifact_outline: dict[str, Any] = {}
        artifact_id = str(session.get("active_artifact_id") or "")
        if artifact_id:
            artifact = self.store.get("artifacts", artifact_id) or {}
            draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
            artifact_outline = {
                "artifact_id": artifact_id,
                "title": artifact.get("title") or "",
                "capability_id": artifact.get("capability_id") or "",
                "revision": artifact.get("revision") or 1,
                "tasks": [
                    {
                        "task_id": item.get("task_id") or "",
                        "name": compact_text(str(item.get("name") or ""), 120),
                        "purpose": compact_text(str(item.get("purpose") or ""), 240),
                        "exit_criteria": item.get("exit_criteria") or [],
                    }
                    for item in (draft.get("tasks") or [])[:20]
                    if isinstance(item, dict)
                ],
            }
        recent_source_refs = list(
            dict.fromkeys(
                [
                    *[
                        str(ref)
                        for item in recent
                        for ref in [
                            *[
                                evidence.get("evidence_id")
                                for evidence in item.get("evidence_refs") or []
                                if isinstance(evidence, dict)
                            ],
                            *[
                                citation.get("source_ref")
                                for citation in item.get("citations") or []
                                if isinstance(citation, dict)
                            ],
                            *[
                                artifact.get("artifact_id")
                                for artifact in item.get("artifact_refs") or []
                                if isinstance(artifact, dict)
                            ],
                        ]
                        if str(ref or "").strip()
                    ],
                    *([artifact_id] if artifact_id else []),
                ]
            )
        )[:24]
        return {
            "summary": summary,
            "recent_messages": [
                {
                    "role": item.get("role"),
                    "text": compact_text(str(item.get("display_text") or ""), 1000),
                    "source_refs": [
                        str(evidence.get("evidence_id") or "")
                        for evidence in item.get("evidence_refs") or []
                        if isinstance(evidence, dict) and evidence.get("evidence_id")
                    ][:8],
                    "artifact_refs": [
                        str(artifact.get("artifact_id") or "")
                        for artifact in item.get("artifact_refs") or []
                        if isinstance(artifact, dict) and artifact.get("artifact_id")
                    ][:3],
                }
                for item in recent
            ],
            "recent_source_refs": recent_source_refs,
            "active_artifact": artifact_outline,
        }

    def _active_session_task(self, principal: Principal, session: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(session.get("active_artifact_id") or "")
        task_id = str(session.get("selected_task_id") or "")
        if not artifact_id:
            return {}
        artifact = self.store.get("artifacts", artifact_id) or {}
        if not artifact or not self._owns(principal, artifact):
            return {}
        draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
        tasks = [item for item in draft.get("tasks") or [] if isinstance(item, dict)]
        return next((item for item in tasks if item.get("task_id") == task_id), None) or (tasks[0] if tasks else {})

    def _record_for_ref(self, principal: Principal, ref: str) -> Any | None:
        records = self.repository.authoritative_records(principal, include_drafts=True)
        records.extend(self.repository.history_records(principal, include_seed=True))
        record = next((item for item in records if item.record_id == ref), None)
        if record:
            return record
        if not ref.startswith("candidate_"):
            return None
        candidate = self.store.get("knowledge_candidates", ref)
        if not candidate or candidate.get("status") not in {"provisional", "reviewed"}:
            return None
        if candidate.get("employee_id") != principal.employee_id and not principal.is_admin:
            return None
        return KnowledgeRecord(
            record_id=ref,
            kind="knowledge",
            title=str(candidate.get("title") or "업무에서 남긴 내용"),
            description=str(candidate.get("summary") or ""),
            text=str(candidate.get("reusable_lesson") or candidate.get("summary") or ""),
            url=f"/api/v2/knowledge-candidates/{ref}",
            source="knowledge_candidate",
            authority="reviewed" if candidate.get("status") == "reviewed" else "provisional",
            status=str(candidate.get("status") or "provisional"),
            visibility="private",
            owner=str(candidate.get("employee_id") or ""),
            timestamp=str(candidate.get("updated_at") or candidate.get("created_at") or ""),
            metadata={"source_refs": candidate.get("source_refs") or []},
        )

    @staticmethod
    def _evidence_from_record(record: Any, *, score: float = 1.0) -> EvidenceRef:
        return EvidenceRef(
            evidence_id=record.record_id,
            kind=record.kind,
            title=record.title,
            summary=record.description or compact_text(record.text, 360),
            url=record.url,
            source=record.source,
            authority=record.authority,
            score=score,
            metadata={"status": record.status},
        )

    def _apply_source_set(
        self,
        principal: Principal,
        session_id: str,
        evidence: list[EvidenceRef],
        *,
        page_ref: str,
        context_refs: list[str] | None = None,
    ) -> list[EvidenceRef]:
        source_set = self._ensure_source_set(principal, session_id)
        excluded = {str(item) for item in source_set.get("excluded") or []}
        selected = [item for item in evidence if item.evidence_id not in excluded]
        seen = {item.evidence_id for item in selected}

        records = self.repository.authoritative_records(principal, include_drafts=True)
        page_anchor = self.learning.contexts.page_anchor(principal, page_ref)
        page_record = next(
            (item for item in records if page_anchor and page_anchor.resolved and item.record_id == page_anchor.ref),
            None,
        )
        ordered_refs = [str(item) for item in (context_refs or []) if str(item).strip()]
        if page_record:
            ordered_refs.append(page_record.record_id)
        ordered_refs.extend(str(item) for item in source_set.get("pinned") or [])
        ordered_refs = list(dict.fromkeys(ordered_refs))
        priority: list[EvidenceRef] = []
        for ref in ordered_refs:
            if not ref or ref in excluded:
                continue
            existing = next((item for item in selected if item.evidence_id == ref), None)
            if existing:
                selected.remove(existing)
                priority.append(existing)
                continue
            record = self._record_for_ref(principal, ref)
            if record:
                priority.append(self._evidence_from_record(record, score=1.0))
                seen.add(ref)
                continue
            artifact = self.store.get("artifacts", ref) if ref.startswith("artifact_") else None
            if artifact and self._owns(principal, artifact):
                body = str((artifact.get("draft") or {}).get("body") or artifact.get("preview") or "")
                priority.append(
                    EvidenceRef(
                        evidence_id=ref,
                        kind="note",
                        title=str(artifact.get("title") or "private 지식 노트"),
                        summary=compact_text(body, 360),
                        url=f"/agent?session={session_id}&artifact={ref}",
                        source="private_note",
                        authority="provisional",
                        score=1.0,
                    ),
                )
                seen.add(ref)
        return [*priority, *selected][:12]

    def _citations_for_evidence(
        self,
        principal: Principal,
        session_id: str,
        query: str,
        evidence: list[EvidenceRef],
    ) -> list[CitationRef]:
        citations: list[CitationRef] = []
        for item in evidence[:8]:
            record = self._record_for_ref(principal, item.evidence_id)
            if record:
                chunk = item.metadata.get("best_chunk") if isinstance(item.metadata.get("best_chunk"), dict) else {}
                if not chunk or str(chunk.get("record_id") or "") != record.record_id:
                    chunk = best_chunk_for_query(record, query)
                excerpt = compact_text(str(chunk.get("content") or record.description or record.text), 520)
                chunk_id = str(chunk.get("chunk_id") or "")
                heading = str(chunk.get("heading") or "")
                start_line = int(chunk.get("start_line") or 0)
                end_line = int(chunk.get("end_line") or start_line)
                target = record.url
                kind = record.kind
                title = record.title
            else:
                artifact = self.store.get("artifacts", item.evidence_id) if item.evidence_id.startswith("artifact_") else None
                if not artifact or not self._owns(principal, artifact):
                    continue
                body = str((artifact.get("draft") or {}).get("body") or artifact.get("preview") or "")
                excerpt = compact_text(body, 520)
                chunk_id = ""
                heading = ""
                start_line = 1
                end_line = max(1, len(body.splitlines()))
                target = f"/agent?session={session_id}&artifact={item.evidence_id}"
                kind = "note"
                title = str(artifact.get("title") or item.title)
            citation_id = new_id("cite")
            separator = "&" if "?" in target else "?"
            citation = CitationRef(
                citation_id=citation_id,
                source_ref=item.evidence_id,
                chunk_id=chunk_id,
                title=title,
                heading=heading,
                excerpt=excerpt,
                target_url=f"{target}{separator}citation={citation_id}" if target else "",
                start_line=start_line,
                end_line=end_line,
                kind=kind,
                resolved_source=ResolvedSourceRef(
                    source_ref=item.evidence_id,
                    title=title,
                    canonical_url=target,
                    source_kind=kind,
                    navigation_state="navigable" if target else "unresolved",
                ),
            )
            self.store.put(
                "citations",
                citation_id,
                {
                    **citation.model_dump(mode="json"),
                    "employee_id": principal.employee_id,
                    "work_session_id": session_id,
                    "created_at": now_iso(),
                },
            )
            citations.append(citation)
        return citations

    def get_citation(self, principal: Principal, citation_id: str) -> dict[str, Any]:
        citation = self._require_owned(principal, self.store.get("citations", citation_id), "citation")
        source_ref = str(citation.get("source_ref") or "")
        if source_ref.startswith("artifact_"):
            artifact = self.store.get("artifacts", source_ref)
            if not artifact or not self._owns(principal, artifact):
                raise HTTPException(status_code=403, detail="citation source is no longer accessible")
        elif not self._record_for_ref(principal, source_ref):
            raise HTTPException(status_code=403, detail="citation source is no longer accessible")
        return citation

    def _model_related_questions(
        self,
        principal: Principal,
        session: dict[str, Any],
        raw_questions: Any,
        citations: list[CitationRef],
    ) -> list[RelatedQuestion]:
        citation_order = list(citations[:8])
        if not citation_order or not isinstance(raw_questions, list):
            return []
        recent = {
            compact_text(str(item.get("display_text") or ""), 300).lower()
            for item in self.session_timeline(principal, str(session["session_id"]), limit=6).get("items") or []
        }
        has_work_context = bool(
            session.get("active_artifact_id")
            or session.get("active_work_run_id")
            or session.get("selected_task_id")
        )
        result: list[RelatedQuestion] = []
        for item in raw_questions[:3]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "understand")
            if kind not in {"understand", "connect", "apply"} or (kind == "apply" and not has_work_context):
                continue
            label = compact_text(str(item.get("label") or ""), 120)
            question = compact_text(str(item.get("question") or ""), 600)
            numbers = list(
                dict.fromkeys(
                    int(number)
                    for number in item.get("source_numbers") or []
                    if isinstance(number, int) and 1 <= number <= len(citation_order)
                )
            )
            if not label or not question or not numbers or question.lower() in recent:
                continue
            result.append(
                RelatedQuestion(
                    question_id=new_id("question"),
                    kind=kind,  # type: ignore[arg-type]
                    label=label,
                    question=question,
                    source_refs=list(dict.fromkeys(citation_order[number - 1].source_ref for number in numbers)),
                )
            )
        return result

    def _create_goal_plan(
        self,
        principal: Principal,
        session: dict[str, Any],
        question: str,
        definition: CapabilityDefinition,
        route: dict[str, Any],
        intent: WorkIntent,
    ) -> dict[str, Any]:
        steps: list[GoalStep] = []
        if definition.capability_id == "work.inbox":
            steps.append(GoalStep(step_id="current_work", capability_id="work.inbox", label="현재 업무 확인"))
        elif definition.deep:
            steps.append(GoalStep(step_id="retrieve", capability_id="knowledge.search", label="관련 지식과 업무 맥락 확인"))
            steps.append(
                GoalStep(
                    step_id="deep_research",
                    capability_id="deep.research",
                    label="관련 지식 심층 조사",
                    operation="deep",
                    depends_on=["retrieve"],
                )
            )
        else:
            steps.append(GoalStep(step_id="retrieve", capability_id="knowledge.search", label="관련 지식과 업무 맥락 확인"))
            operation_steps: dict[WorkOperation, tuple[str, str, str, str]] = {
                WorkOperation.compare: ("compare", "cases.similar", "관련 지식과 과거 사례 비교", "read"),
                WorkOperation.create: ("create", definition.capability_id, definition.title, "draft"),
                WorkOperation.refine: ("refine", definition.capability_id, "현재 결과 다듬기", "draft"),
                WorkOperation.connect: ("connect", definition.capability_id, "업무 흐름과 실행 연결 확인", "draft"),
                WorkOperation.validate: ("validate", "harness.validate", "완료 조건과 근거 검증", "read"),
                WorkOperation.test: ("test", "harness.test", "적용 전 시험", "read"),
                WorkOperation.run: ("run", definition.capability_id, "확인 후 업무 실행", "guarded"),
                WorkOperation.observe: ("observe", "runtime.observe", "실행 결과와 상태 확인", "read"),
                WorkOperation.complete: ("complete", "task.complete", "완료된 모습과 근거 확인", "guarded"),
                WorkOperation.capture: ("capture", "learning.capture", "이번 업무에서 남길 내용 정리", "draft"),
                WorkOperation.promote: ("promote", "knowledge.promote", "공유 검토 요청", "guarded"),
            }
            for operation in intent.operation_plan:
                if operation == WorkOperation.understand:
                    continue
                step_id, capability_id, label, step_operation = operation_steps[operation]
                steps.append(
                    GoalStep(
                        step_id=step_id,
                        capability_id=capability_id,
                        label=label,
                        operation=step_operation,  # type: ignore[arg-type]
                        depends_on=[steps[-1].step_id],
                    )
                )
            if intent.operation_plan == [WorkOperation.understand]:
                steps.append(
                    GoalStep(
                        step_id="answer",
                        capability_id="knowledge.answer",
                        label="근거를 바탕으로 답변",
                        depends_on=["retrieve"],
                    )
                )
        route_class = "deep" if definition.deep else "workflow" if len(steps) > 2 or intent.operation != WorkOperation.understand else "quick"
        goal_plan_id = new_id("goal")
        plan = {
            "goal_plan_id": goal_plan_id,
            "employee_id": principal.employee_id,
            "work_session_id": session["session_id"],
            "interpreted_goal": question,
            "route_class": route_class,
            "confidence": intent.confidence,
            "route_source": route.get("source") or "auto",
            "assumptions": [],
            "asset_kind": intent.asset_kind.value,
            "operation_plan": [item.value for item in intent.operation_plan],
            "desired_outcome": intent.desired_outcome,
            "steps": [item.model_dump(mode="json") for item in steps],
            "status": "planned",
            "revision": 1,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        return self.store.put("goal_plans", goal_plan_id, plan)

    def _finish_goal_plan(
        self,
        goal_plan: dict[str, Any],
        *,
        evidence: list[EvidenceRef],
        artifacts: list[ArtifactRef],
        queued: bool,
        response_status: str,
        plan_ref: str,
        intent: WorkIntent,
        work_run: dict[str, Any],
    ) -> dict[str, Any]:
        harness_blocked = any(
            isinstance(item, dict) and item.get("status") == "blocked"
            for item in work_run.get("harness_results") or []
        )
        work_status = str(work_run.get("status") or "")
        candidate_ready = bool(work_run.get("knowledge_candidate_ids"))
        steps = []
        for item in goal_plan.get("steps") or []:
            step = dict(item)
            step_id = str(step.get("step_id") or "")
            if step_id in {"retrieve", "current_work"}:
                step_status = "blocked" if work_status == "blocked" and not evidence else "completed"
            elif queued and step.get("operation") == "deep":
                step_status = "queued"
            elif step_id == "answer":
                step_status = "completed" if response_status == "completed" else "waiting_input"
            elif step_id == "validate" and intent.operation in {
                WorkOperation.create,
                WorkOperation.refine,
                WorkOperation.connect,
                WorkOperation.validate,
                WorkOperation.test,
                WorkOperation.run,
                WorkOperation.complete,
            }:
                step_status = "blocked" if harness_blocked else "completed"
            elif step_id == "capture":
                step_status = "completed" if candidate_ready else "pending"
            elif step_id == intent.operation.value:
                if response_status == "failed":
                    step_status = "failed"
                elif response_status == "needs_input":
                    step_status = "waiting_input"
                elif plan_ref and intent.operation in {WorkOperation.run, WorkOperation.promote}:
                    step_status = "waiting_confirmation"
                elif work_status == "waiting_review" and intent.operation in {WorkOperation.refine, WorkOperation.connect}:
                    step_status = "waiting_review"
                else:
                    step_status = "completed"
            else:
                step_status = "pending"
            step["status"] = step_status
            step["evidence_refs"] = [value.evidence_id for value in evidence[:12]]
            step["artifact_refs"] = [value.artifact_id for value in artifacts[:3]]
            steps.append(step)
        statuses = {str(item.get("status") or "pending") for item in steps}
        if "failed" in statuses:
            plan_status = "failed"
        elif "blocked" in statuses:
            plan_status = "blocked"
        elif "waiting_input" in statuses:
            plan_status = "waiting_input"
        elif "waiting_confirmation" in statuses:
            plan_status = "waiting_confirmation"
        elif "waiting_review" in statuses:
            plan_status = "waiting_review"
        elif "queued" in statuses:
            plan_status = "queued"
        elif "pending" in statuses or "running" in statuses:
            plan_status = "running"
        else:
            plan_status = "completed"
        goal_plan.update(
            {
                "steps": steps,
                "status": plan_status,
                "revision": int(goal_plan.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        return self.store.put("goal_plans", str(goal_plan["goal_plan_id"]), goal_plan)

    def get_goal_plan(self, principal: Principal, goal_plan_id: str) -> dict[str, Any]:
        return self._require_owned(principal, self.store.get("goal_plans", goal_plan_id), "goal plan")

    def _advance_goal_plan_after_domain_result(
        self,
        principal: Principal,
        *,
        work_run_id: str,
        domain_operation: str,
    ) -> dict[str, Any]:
        if not work_run_id:
            return {}
        run = self.learning.get_run(principal, work_run_id)
        goal_plan_id = str(run.get("goal_plan_id") or "")
        if not goal_plan_id:
            return {}
        goal_plan = self.get_goal_plan(principal, goal_plan_id)
        completed_steps = {
            "action.invoke": {"run", "observe"},
            "knowledge.promotion.submit": {"promote"},
            "sop.draft.publish_request": {"create", "validate"},
            "action.draft.publish_request": {"create", "validate"},
        }.get(domain_operation, set())
        if not completed_steps:
            return goal_plan
        steps = []
        for raw in goal_plan.get("steps") or []:
            step = dict(raw)
            if step.get("step_id") in completed_steps:
                step["status"] = "completed"
            steps.append(step)
        statuses = {str(item.get("status") or "pending") for item in steps}
        goal_plan.update(
            {
                "steps": steps,
                "status": "completed" if statuses <= {"completed"} else "running",
                "revision": int(goal_plan.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        return self.store.put("goal_plans", goal_plan_id, goal_plan)

    def readiness(self, principal: Principal, *, probe_model: bool = False) -> dict[str, Any]:
        store_state = self.store.health()
        if self.settings.lmstudio_require_preloaded_models:
            self.ensure_model_residency()
        model_state = self.model.preflight() if probe_model else self.model.readiness()
        heartbeats = self.store.list("worker_heartbeats", limit=20)
        worker_ready = False
        latest_worker = ""
        latest_worker_row: dict[str, Any] = {}
        ready_worker_row: dict[str, Any] = {}
        for item in heartbeats:
            seen_at = str(item.get("last_seen_at") or "")
            if seen_at >= latest_worker:
                latest_worker = seen_at
                latest_worker_row = item
            try:
                age = datetime.now(timezone.utc) - parse_time(seen_at)
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                if (
                    age.total_seconds() <= self.settings.worker_stale_seconds
                    and metadata.get("deepagents") is True
                    and metadata.get("model_adapter") is True
                ):
                    worker_ready = True
                    if seen_at >= str(ready_worker_row.get("last_seen_at") or ""):
                        ready_worker_row = item
            except (ValueError, TypeError):
                continue
        reported_worker = ready_worker_row or latest_worker_row
        reported_worker_metadata = (
            reported_worker.get("metadata")
            if isinstance(reported_worker.get("metadata"), dict)
            else {}
        )
        content_ready = self.repository.content_ready()
        search_stats = self.repository.stats(principal)
        index_manifest = self.store.get("manifests", "search") or {}
        knowledge_graph_manifest = self.store.get("manifests", "knowledge_graph") or {}
        knowledge_sources = self.knowledge.list_sources(principal).get("items") or []
        index_expected = bool(model_state.get("embeddings"))
        index_fresh = bool(
            index_manifest
            and int(index_manifest.get("record_count") or 0) > 0
            and int(index_manifest.get("chunk_count") or 0) > 0
            and index_manifest.get("index_schema_version") == SEARCH_INDEX_SCHEMA_VERSION
            and index_manifest.get("status") == "ready"
            and index_manifest.get("source_signature") == self.repository.source_signature()
            and int(store_state.get("search_documents") or index_manifest.get("record_count") or 0)
            == int(index_manifest.get("record_count") or 0)
            and int(store_state.get("search_chunks") or index_manifest.get("chunk_count") or 0)
            == int(index_manifest.get("chunk_count") or 0)
        )
        index_sync_state = (
            "ready"
            if index_fresh
            else "syncing"
            if str(index_manifest.get("sync_state") or index_manifest.get("status") or "") in {"syncing", "building"}
            else "degraded"
        )
        residency_ready = (
            not self.settings.lmstudio_require_preloaded_models
            or self.model_residency.get("ready") is True
        )
        dependencies = {
            "content": content_ready,
            "postgres": bool(store_state.get("ready") and store_state.get("durable")),
            "model": bool(model_state.get("generation"))
            and residency_ready
            and (not probe_model or bool(model_state.get("ok"))),
            "embedding": bool(model_state.get("embeddings")) and residency_ready,
            "search_index": index_fresh,
            "deep_worker": worker_ready,
            "pat": self.pats.available,
        }
        capability_states: dict[str, str] = {}
        for definition in self.registry.all():
            state, _, _ = self.registry.state_for(
                definition,
                principal=principal,
                readiness=dependencies,
                task_mode=TaskMode.copilot,
                supplied_input={"query": "probe", "goal": "probe"},
            )
            capability_states[definition.capability_id] = state.value
        required_dependencies = ["content"]
        if self.settings.require_postgres:
            required_dependencies.append("postgres")
        ready = all(dependencies[item] for item in required_dependencies)
        return {
            "version": "2.0",
            "enabled": self.settings.enabled,
            "default": self.settings.default_enabled,
            "ready": ready,
            "dependencies": dependencies,
            "store": store_state,
            "model": model_state,
            "model_residency": dict(self.model_residency),
            "model_policy": {
                "route": self.settings.model_route,
                "gpt55_test_only": True,
                "gpt55_test_mode": self.settings.gpt55_test_mode,
            },
            "worker": {
                "ready": worker_ready,
                "worker_id": reported_worker.get("worker_id") or "",
                "latest_heartbeat": latest_worker,
                "runtime": {
                    key: reported_worker_metadata.get(key)
                    for key in (
                        "version",
                        "deepagents",
                        "model_adapter",
                        "openai_adapter",
                        "anthropic_adapter",
                    )
                    if key in reported_worker_metadata
                },
            },
            "quick_agent": {"ready": True, "engine": self.quick_agent.engine},
            "search": {
                **search_stats,
                "index": {
                    "expected": index_expected,
                    "fresh": index_fresh,
                    "sync_state": index_sync_state,
                    "current_source_signature": self.repository.source_signature(),
                    "target_source_signature": str(index_manifest.get("target_source_signature") or ""),
                    "pending_changes": int(index_manifest.get("pending_changes") or 0),
                    "last_success_at": str(index_manifest.get("last_sync_success_at") or index_manifest.get("indexed_at") or ""),
                    "manifest": index_manifest,
                    "stored_documents": int(store_state.get("search_documents") or 0),
                },
            },
            "knowledge": {
                "source_count": len(knowledge_sources),
                "sources_ready": sum(1 for item in knowledge_sources if item.get("status") == "ready"),
                "graph": knowledge_graph_manifest,
                "open_health_findings": len(
                    self.store.list(
                        "knowledge_health_findings",
                        employee_id=principal.employee_id,
                        limit=1000,
                    )
                ),
            },
            "capabilities": capability_states,
            "warnings": [
                message
                for condition, message in (
                    (not store_state.get("durable"), "Agent 상태가 memory mode이며 재시작 시 사라집니다."),
                    (not model_state.get("generation"), "초안과 심층 작업 모델이 준비되지 않았습니다."),
                    (not model_state.get("embeddings"), "semantic 검색이 비활성화되어 lexical/ontology 검색만 사용합니다."),
                    (
                        self.settings.lmstudio_require_preloaded_models and not residency_ready,
                        "로컬 LM Studio의 자동 모델 전환이 켜져 있거나 두 모델이 수동 상주 상태가 아니어서 추론 호출을 차단했습니다.",
                    ),
                    (index_expected and not index_fresh, "검색 index가 없거나 지식 정본보다 오래되었습니다."),
                    (not worker_ready, "DeepAgents worker가 연결되지 않았습니다."),
                    (self.store.durable and not self.pats.production_ready, "운영 PAT hash secret이 설정되지 않았습니다."),
                )
                if condition
            ],
        }

    def _mcp_v2_status(self) -> dict[str, Any]:
        endpoint = self.settings.mcp_external_url
        base_url = endpoint[: -len("/mcp/v2")] if endpoint.endswith("/mcp/v2") else endpoint.rstrip("/")
        status_url = base_url + "/status.json"
        try:
            request = urllib.request.Request(status_url, headers={"accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.5) as response:  # noqa: S310 - configured service URL
                payload = json.loads(response.read().decode("utf-8"))
            ready = bool(
                payload.get("status") == "ok"
                and int((payload.get("capabilities") or {}).get("tools") or 0) == 10
                and str(payload.get("mcp_endpoint") or "").endswith("/mcp/v2")
            )
            return {"ready": ready, "status_url": status_url, "tools": (payload.get("capabilities") or {}).get("tools")}
        except Exception as exc:
            return {"ready": False, "status_url": status_url, "error": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    def page_kind(page_ref: str) -> str:
        path = (page_ref or "/").split("?", 1)[0]
        if path in {"", "/"}:
            return "library"
        if path.endswith("/boi:public:boi-wiki-manual:guide:final-operator-guide"):
            return "library"
        if path.startswith("/docs/"):
            return "document"
        if path.startswith("/inbox"):
            return "inbox"
        if path.startswith("/sops") or path.startswith("/workflows"):
            return "sop"
        if path.startswith("/events") or path.startswith("/event-types"):
            return "event"
        if path.startswith("/actions"):
            return "action"
        if path.startswith("/agent"):
            return "agent"
        return "library"

    @staticmethod
    def context_fingerprint(principal: Principal, request: OfferRequest) -> str:
        value = json.dumps(
            {
                "employee_id": principal.employee_id,
                "page_ref": request.page_ref.split("#", 1)[0],
                "task_ref": request.task_ref,
                "selected_text": compact_text(request.selected_text, 500),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _offer_candidates(self, page_kind: str) -> list[str]:
        return {
            "library": ["knowledge.search", "work.inbox", "cases.similar"],
            "document": ["knowledge.search", "cases.similar", "knowledge.draft"],
            "inbox": ["work.inbox", "cases.similar", "knowledge.draft"],
            "sop": ["knowledge.search", "sop.plan", "action.plan"],
            "event": ["knowledge.search", "business_event.plan", "cases.similar"],
            "action": ["knowledge.search", "action.plan", "cases.similar"],
            "agent": ["knowledge.search", "deep.research", "skill.plan"],
        }.get(page_kind, ["knowledge.search"])

    def create_offers(self, principal: Principal, request: OfferRequest) -> list[CapabilityOffer]:
        for existing in self.store.list("offers", employee_id=principal.employee_id, limit=500):
            try:
                expired = parse_time(str(existing.get("expires_at") or "")) <= datetime.now(timezone.utc)
            except (ValueError, TypeError):
                expired = True
            if expired and existing.get("offer_id"):
                self.store.delete("offers", str(existing["offer_id"]))
        readiness = self.readiness(principal)["dependencies"]
        fingerprint = self.context_fingerprint(principal, request)
        task_mode = self.policy.resolve_mode(principal, request.task_ref)
        supplied = {
            "query": request.selected_text,
            "goal": request.selected_text,
        }
        offers: list[CapabilityOffer] = []
        for capability_id in self._offer_candidates(self.page_kind(request.page_ref)):
            definition = self.registry.get(capability_id)
            state, missing, state_reason = self.registry.state_for(
                definition,
                principal=principal,
                readiness=readiness,
                task_mode=task_mode,
                supplied_input=supplied,
            )
            if state == CapabilityState.unavailable and not request.include_unavailable:
                continue
            offer = CapabilityOffer(
                offer_id=new_id("offer"),
                capability_id=capability_id,
                label=definition.title,
                reason=state_reason if state != CapabilityState.ready else definition.description,
                state=state,
                required_inputs=missing,
                context_fingerprint=fingerprint,
                preview=compact_text(request.selected_text, 180),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.settings.offer_ttl_seconds),
            )
            self.store.put(
                "offers",
                offer.offer_id,
                {
                    **offer.model_dump(mode="json"),
                    "employee_id": principal.employee_id,
                    "page_ref": request.page_ref,
                    "task_ref": request.task_ref,
                    "selected_text": request.selected_text,
                    "created_at": now_iso(),
                },
            )
            offers.append(offer)
        return offers

    def _load_offer(self, principal: Principal, offer_id: str) -> dict[str, Any]:
        offer = self.store.get("offers", offer_id)
        if not offer:
            raise HTTPException(status_code=404, detail="offer not found")
        if offer.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="offer belongs to another employee")
        try:
            if parse_time(str(offer.get("expires_at") or "")) <= datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="offer expired; refresh recommendations")
        except ValueError as exc:
            raise HTTPException(status_code=410, detail="offer is invalid") from exc
        return offer

    def execute_offer(
        self,
        principal: Principal,
        offer_id: str,
        request: OfferExecuteRequest,
    ) -> AgentTurnResponse:
        offer = self._load_offer(principal, offer_id)
        fingerprint = self.context_fingerprint(
            principal,
            OfferRequest(
                page_ref=request.page_ref or str(offer.get("page_ref") or ""),
                task_ref=request.task_ref or str(offer.get("task_ref") or ""),
                selected_text=str(offer.get("selected_text") or ""),
            ),
        )
        if fingerprint != offer.get("context_fingerprint"):
            raise HTTPException(status_code=409, detail="page or Task context changed; refresh recommendations")
        capability_id = str(offer.get("capability_id") or "knowledge.search")
        goal = str(request.input_delta.get("goal") or request.input_delta.get("query") or offer.get("selected_text") or "").strip()
        if not goal and capability_id == "work.inbox":
            goal = "현재 내가 처리할 업무를 보여줘"
        if not goal:
            return self._needs_input_response(
                capability_id,
                ["goal"],
                "무엇을 확인하거나 만들지 적어주세요.",
            )
        return self.run_turn(
            principal,
            AgentTurnRequest(
                question=goal,
                page_ref=request.page_ref or str(offer.get("page_ref") or ""),
                task_ref=request.task_ref or str(offer.get("task_ref") or ""),
                offer_id=offer_id,
                input_delta=request.input_delta,
                capability_id=str(offer.get("capability_id") or ""),
            ),
        )

    def _needs_input_response(
        self,
        capability_id: str,
        fields: list[str],
        message: str,
        *,
        work_session_id: str = "",
    ) -> AgentTurnResponse:
        return AgentTurnResponse(
            run_id=new_id("run"),
            turn_id=new_id("turn"),
            conversation_id=work_session_id,
            work_session_id=work_session_id,
            status="needs_input",
            capability_id=capability_id,
            answer=AnswerBlock(summary=message, markdown=message),
            offers=[],
            error_code="needs_input:" + ",".join(fields),
        )

    def _resolve_turn_session(self, principal: Principal, request: AgentTurnRequest) -> dict[str, Any]:
        session_id = str(request.work_session_id or "")
        if not session_id and str(request.conversation_id or "").startswith("ws_"):
            session_id = str(request.conversation_id)
        if session_id:
            session = self.get_work_session(principal, session_id)
        else:
            session = self.create_work_session(
                principal,
                WorkSessionCreateRequest(
                    title=compact_text(request.question, 80),
                    page_ref=request.page_ref,
                    helper_id=request.helper_id or "",
                ),
            )
        request.work_session_id = str(session["session_id"])
        request.conversation_id = str(session["conversation_id"])
        request.input_delta = {
            **request.input_delta,
            "_work_session_context": self._session_context(principal, session),
        }
        return session

    def _context(
        self,
        principal: Principal,
        definition: CapabilityDefinition,
        request: AgentTurnRequest,
        evidence: list[EvidenceRef],
        task_mode: TaskMode,
        *,
        session: dict[str, Any],
        source_set: dict[str, Any],
        resolved_goal: str = "",
        task_override: dict[str, Any] | None = None,
    ) -> WorkContextPack:
        task = normalise_task_completion(
            task_override or self.policy.resolve_task(principal, request.task_ref),
            label_lookup=self._completion_label_lookup(principal),
        )
        context = self.learning.contexts.compile(
            principal=principal,
            definition=definition,
            goal=resolved_goal or request.question,
            page_ref=request.page_ref,
            task_ref=request.task_ref,
            task_mode=task_mode,
            task=task,
            evidence=evidence,
            session=session,
            source_set=source_set,
            external_ai_summary=request.external_ai_summary,
            external_refs=request.external_artifact_refs,
        )
        context.manifest.update(
            {
                "evidence_count": len(context.evidence_refs),
                "minio_enabled": bool(self.settings.minio_endpoint),
                "external_artifact_refs": [compact_text(item, 500) for item in request.external_artifact_refs],
                "source_set_ref": self._source_set_id(str(request.work_session_id or "")) if request.work_session_id else "",
                "conversation": request.input_delta.get("_work_session_context") or {},
                "helper_id": request.helper_id or "",
            }
        )
        self.store.put("contexts", context.context_id, context.model_dump(mode="json"))
        return context

    @staticmethod
    def _search_answer(
        query: str,
        evidence: list[EvidenceRef],
        *,
        citations: list[CitationRef] | None = None,
        empty_label: str = "관련 자료",
    ) -> AnswerBlock:
        if not evidence:
            message = f"'{compact_text(query, 80)}'에 해당하는 {empty_label}를 찾지 못했습니다. 검색 범위나 업무 용어를 더 구체적으로 적어주세요."
            return AnswerBlock(summary=message, markdown=message)
        direct_parts = [compact_text(item.summary, 220) for item in evidence[:2] if item.summary]
        direct = " ".join(dict.fromkeys(direct_parts))
        summary = (
            f"검토된 근거 기준으로 {direct}"
            if direct
            else f"{len(evidence)}개의 관련 근거를 찾았습니다. 가장 관련성이 높은 항목은 '{evidence[0].title}'입니다."
        )
        citation_by_source = {
            item.source_ref: (index + 1, item)
            for index, item in enumerate((citations or [])[:4])
        }
        first_citation = citation_by_source.get(evidence[0].evidence_id)
        if first_citation:
            index, citation = first_citation
            summary += f" [{index}](/api/v2/citations/{citation.citation_id})"
        lines = [summary, "", "### 관련 근거"]
        for item in evidence[:4]:
            link = f"[{item.title}]({item.url})" if item.url else item.title
            marker = ""
            if item.evidence_id in citation_by_source:
                index, citation = citation_by_source[item.evidence_id]
                marker = f" [{index}](/api/v2/citations/{citation.citation_id})"
            lines.append(f"- {link}{marker}: {item.summary or item.kind}")
        return AnswerBlock(summary=summary, markdown="\n".join(lines))

    def _grounded_search_answer(
        self,
        principal: Principal,
        session: dict[str, Any],
        query: str,
        evidence: list[EvidenceRef],
        citations: list[CitationRef],
        *,
        empty_label: str = "관련 자료",
        guidance: str = "",
        desired_outcome: str = "",
        primary_source_ref: str = "",
    ) -> tuple[AnswerBlock, list[RelatedQuestion]]:
        fallback = self._search_answer(query, evidence, citations=citations, empty_label=empty_label)
        if not evidence or not citations or not self.model.readiness().get("generation"):
            return fallback, []
        citation_by_source = {item.source_ref: item for item in citations}
        grounded_sources = [item for item in evidence if item.evidence_id in citation_by_source][:4]
        if not grounded_sources:
            return fallback, []
        source_payload = []
        citation_order: list[CitationRef] = []
        for item in grounded_sources:
            citation = citation_by_source[item.evidence_id]
            citation_order.append(citation)
            source_payload.append(
                {
                    "number": len(source_payload) + 1,
                    "title": item.title,
                    "kind": item.kind,
                    "heading": citation.heading,
                    "excerpt": compact_text(citation.excerpt, 620),
                    "is_primary": item.evidence_id == primary_source_ref,
                }
            )
        schema = {
            "type": "object",
            "required": ["summary", "outcomes"],
            "properties": {
                "summary": {"type": "string"},
                "outcomes": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": ["title", "items"],
                        "properties": {
                            "title": {"type": "string"},
                            "items": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "required": ["text", "source_numbers"],
                                    "properties": {
                                        "text": {"type": "string"},
                                        "source_numbers": {
                                            "type": "array",
                                            "items": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "related_questions": MERMAID_GRAPH_SCHEMA["properties"]["related_questions"],
            },
        }
        try:
            generated = self.model.generate_structured(
                system=(
                    "You answer workplace questions in concise Korean using only the supplied BoI Wiki excerpts. "
                    "Do not add general model knowledge. Put the conclusion first. Every factual point must cite "
                    "one or more supplied source numbers. Split the user's request into distinct requested outcomes "
                    "and return one section for each outcome; do not silently omit a requested deliverable. "
                    "When one retrieved source has is_primary=true, make that source the focal subject, cite it in "
                    "the summary and at least one outcome item, and use the other sources only to clarify its directly "
                    "related context. Do not replace the focal document with a tangential dictionary term. "
                    "If evidence is insufficient, say exactly what is missing in that outcome. "
                    "Suggest at most three short follow-up questions only when directly supported by the supplied sources. "
                    "Do not steer an explanation toward SOP, Task, Event, or Action unless the request and evidence require it. "
                    "Write user-facing text in natural Korean. Do not expose file names, storage identifiers, or raw "
                    "snake_case schema fields unless the user explicitly requested the technical schema. "
                    + (f"Follow this verified helper guidance when it does not conflict with evidence: {compact_text(guidance, 5000)}" if guidance else "")
                ),
                prompt=(
                    f"Question: {query}\n"
                    f"Requested result: {desired_outcome or query}\n"
                    f"Retrieved sources: {json.dumps(source_payload, ensure_ascii=False)}\n"
                    "Return a short direct summary, at most three outcome sections with no more than six total items, "
                    "and optional grounded related_questions."
                ),
                schema=schema,
            )
            def clean_generated_text(value: Any, limit: int) -> str:
                text = compact_text(str(value or ""), limit)
                text = re.sub(r"\s*\[(?:\d+(?:\s*,\s*\d+)*)\]", "", text)
                text = re.sub(r"\s*\(\s*출처\s*\d+(?:\s*,\s*\d+)*\s*\)", "", text)
                return text.strip()

            summary = clean_generated_text(generated.get("summary"), 620)
            rendered_sections: list[tuple[str, list[str]]] = []
            first_valid_numbers: list[int] = []
            used_source_numbers: set[int] = set()
            remaining_items = 6
            for raw_outcome in (generated.get("outcomes") or [])[:3]:
                if not isinstance(raw_outcome, dict) or remaining_items <= 0:
                    continue
                title = clean_generated_text(raw_outcome.get("title"), 90) or "확인 결과"
                rendered_items: list[str] = []
                for raw in (raw_outcome.get("items") or [])[: min(4, remaining_items)]:
                    if not isinstance(raw, dict):
                        continue
                    text = clean_generated_text(raw.get("text"), 380)
                    numbers = list(
                        dict.fromkeys(
                            int(number)
                            for number in raw.get("source_numbers") or []
                            if isinstance(number, int) and 1 <= number <= len(citation_order)
                        )
                    )
                    if not text or not numbers:
                        continue
                    used_source_numbers.update(numbers)
                    if not first_valid_numbers:
                        first_valid_numbers = numbers
                    markers = " ".join(
                        f"[{number}](/api/v2/citations/{citation_order[number - 1].citation_id})"
                        for number in numbers
                    )
                    rendered_items.append(f"- {text} {markers}")
                    remaining_items -= 1
                if not rendered_items:
                    continue
                rendered_sections.append((title, rendered_items))
            if not summary or not rendered_sections:
                return fallback, []
            primary_number = next(
                (
                    index
                    for index, item in enumerate(grounded_sources, start=1)
                    if item.evidence_id == primary_source_ref
                ),
                0,
            )
            if primary_number and primary_number not in used_source_numbers:
                return fallback, []
            summary_numbers = list(
                dict.fromkeys([*([primary_number] if primary_number else []), *(first_valid_numbers or [1])])
            )
            summary_markers = " ".join(
                f"[{number}](/api/v2/citations/{citation_order[number - 1].citation_id})"
                for number in summary_numbers
            )
            lines = [f"{summary} {summary_markers}"]
            for title, items in rendered_sections:
                lines.extend(["", f"### {title}", *items])
            lines.extend(["", "### 사용한 지식"])
            for number, (item, citation) in enumerate(zip(grounded_sources, citation_order), start=1):
                link = f"[{item.title}]({item.url})" if item.url else item.title
                lines.append(
                    f"- {link} [{number}](/api/v2/citations/{citation.citation_id})"
                    + (f" · {citation.heading}" if citation.heading else "")
                )
            related = self._model_related_questions(
                principal,
                session,
                generated.get("related_questions"),
                citation_order,
            )
            return AnswerBlock(summary=summary, markdown="\n".join(lines)), related
        except Exception:
            return fallback, []

    @staticmethod
    def _diagram_label(value: Any, limit: int) -> str:
        text = compact_text(str(value or ""), limit)
        text = re.sub(
            r"\([^)]*\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b[^)]*\)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"[\[\]{}<>`\\]", " ", text)
        return re.sub(r"\s+", " ", text).replace('"', "'").strip()

    @staticmethod
    def _diagram_label_is_user_facing(value: str) -> bool:
        """Reject schema-shaped labels while allowing ordinary names such as API or BoI."""
        return not re.search(r"(?i)\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", value)

    @staticmethod
    def _diagram_asset_kind(value: Any, citations: list[CitationRef], numbers: list[int]) -> str:
        clean = str(value or "").strip()
        supported = {item.value for item in WorkAssetKind}
        if clean in supported:
            return clean
        source_kinds = [citations[number - 1].kind for number in numbers if 1 <= number <= len(citations)]
        mappings = {
            "sop": "sop",
            "workflow": "workflow",
            "task": "task",
            "event": "business_event",
            "business_event": "business_event",
            "action": "action",
            "skill": "skill",
            "runtime": "runtime",
            "case": "evidence",
            "evidence": "evidence",
        }
        return next((mappings[item] for item in source_kinds if item in mappings), "knowledge")

    @staticmethod
    def _evidence_asset_kind(kind: str) -> str:
        return {
            "sop": "sop",
            "workflow": "workflow",
            "task": "task",
            "event": "business_event",
            "business_event": "business_event",
            "action": "action",
            "skill": "skill",
            "runtime": "runtime",
            "case": "evidence",
            "evidence": "evidence",
        }.get(str(kind or "").strip(), "knowledge")

    @staticmethod
    def _artifact_actions_for_intent(intent: WorkIntent, artifact_id: str) -> list[ArtifactAction]:
        if intent.result_purpose not in {"design", "transform"} or intent.operation not in {
            WorkOperation.create,
            WorkOperation.refine,
        }:
            return []
        requested_kinds = {item.value for item in intent.requested_asset_kinds}
        labels = {
            "split_tasks": "Task로 나누기",
            "create_sop_draft": "SOP 초안으로 저장",
        }
        actions: list[ArtifactAction] = []
        for action_id in intent.artifact_actions:
            if action_id == "split_tasks" and not requested_kinds.intersection({"task", "workflow", "sop"}):
                continue
            if action_id == "create_sop_draft" and "sop" not in requested_kinds:
                continue
            actions.append(
                ArtifactAction(
                    action_id=action_id,
                    label=labels[action_id],
                    artifact_id=artifact_id,
                )
            )
        return actions

    def _normalise_mermaid_graph(
        self,
        raw_graph: dict[str, Any],
        citations: list[CitationRef],
        *,
        focal_refs: list[str] | None = None,
        allowed_asset_kinds: set[str] | None = None,
    ) -> dict[str, Any]:
        if not citations:
            raise RuntimeError("흐름 그림을 뒷받침할 인용 근거가 없습니다.")
        constraint_errors: list[str] = []
        for item in (raw_graph.get("nodes") or [])[:14]:
            if not isinstance(item, dict):
                continue
            raw_label = self._diagram_label(item.get("label"), 80)
            raw_asset_kind = str(item.get("asset_kind") or "").strip()
            if raw_label and not self._diagram_label_is_user_facing(raw_label):
                constraint_errors.append(f"스키마형 노드 라벨 '{raw_label}'")
            if allowed_asset_kinds and raw_asset_kind and raw_asset_kind not in allowed_asset_kinds:
                constraint_errors.append(f"허용되지 않은 노드 자산 종류 '{raw_asset_kind}'")
        for item in (raw_graph.get("edges") or [])[:20]:
            if not isinstance(item, dict):
                continue
            raw_label = self._diagram_label(item.get("label"), 48)
            if raw_label and not self._diagram_label_is_user_facing(raw_label):
                constraint_errors.append(f"스키마형 연결 라벨 '{raw_label}'")
        if constraint_errors:
            raise RuntimeError("; ".join(dict.fromkeys(constraint_errors))[:900])
        nodes: list[dict[str, Any]] = []
        model_ids: dict[str, str] = {}
        for item in (raw_graph.get("nodes") or [])[:14]:
            if not isinstance(item, dict):
                continue
            original_id = str(item.get("node_id") or "").strip()
            label = self._diagram_label(item.get("label"), 80)
            numbers = list(
                dict.fromkeys(
                    int(number)
                    for number in item.get("source_numbers") or []
                    if isinstance(number, int) and 1 <= number <= len(citations)
                )
            )
            if not original_id or original_id in model_ids or not label or not numbers:
                continue
            if not self._diagram_label_is_user_facing(label):
                raise RuntimeError("일반 사용자가 이해하기 어려운 스키마 필드명이 노드에 포함되었습니다.")
            asset_kind = self._diagram_asset_kind(item.get("asset_kind"), citations, numbers)
            if allowed_asset_kinds and asset_kind not in allowed_asset_kinds:
                raise RuntimeError(f"요청 범위에 없는 자산 종류가 포함되었습니다: {asset_kind}")
            node_id = f"N{len(nodes) + 1}"
            model_ids[original_id] = node_id
            source_refs = list(dict.fromkeys(citations[number - 1].source_ref for number in numbers))
            nodes.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "kind": self._diagram_label(item.get("kind") or "업무", 32),
                    "asset_kind": asset_kind,
                    "source_refs": source_refs,
                }
            )
        if len(nodes) < 2:
            raise RuntimeError("근거가 확인된 흐름 단계가 2개 이상 필요합니다.")

        edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for item in (raw_graph.get("edges") or [])[:20]:
            if not isinstance(item, dict):
                continue
            source_id = model_ids.get(str(item.get("from") or "").strip(), "")
            target_id = model_ids.get(str(item.get("to") or "").strip(), "")
            label = self._diagram_label(item.get("label") or "이어짐", 48)
            numbers = list(
                dict.fromkeys(
                    int(number)
                    for number in item.get("source_numbers") or []
                    if isinstance(number, int) and 1 <= number <= len(citations)
                )
            )
            signature = (source_id, target_id, label)
            if not source_id or not target_id or source_id == target_id or not numbers or signature in seen_edges:
                continue
            if not self._diagram_label_is_user_facing(label):
                raise RuntimeError("일반 사용자가 이해하기 어려운 스키마 필드명이 연결 설명에 포함되었습니다.")
            seen_edges.add(signature)
            edges.append(
                {
                    "from": source_id,
                    "to": target_id,
                    "label": label,
                    "source_refs": list(dict.fromkeys(citations[number - 1].source_ref for number in numbers)),
                }
            )
        if not edges:
            raise RuntimeError("근거가 확인된 단계 사이의 연결 관계가 필요합니다.")

        adjacency: dict[str, set[str]] = {item["node_id"]: set() for item in nodes}
        for item in edges:
            adjacency[item["from"]].add(item["to"])
            adjacency[item["to"]].add(item["from"])
        available_sources = {item.source_ref for item in citations}
        expected_focal = set(focal_refs or []).intersection(available_sources)
        starting_nodes = [
            item["node_id"]
            for item in nodes
            if expected_focal.intersection(item.get("source_refs") or [])
        ]
        if expected_focal and not starting_nodes:
            raise RuntimeError("현재 질문의 대상이 흐름 그림에 포함되지 않았습니다.")
        start = starting_nodes[0] if starting_nodes else nodes[0]["node_id"]
        visited: set[str] = set()
        pending = [start]
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            pending.extend(adjacency.get(node_id, set()) - visited)
        if len(visited) != len(nodes):
            raise RuntimeError("질문의 대상과 직접 이어지지 않는 별도 흐름이 포함되었습니다.")

        title = self._diagram_label(raw_graph.get("title") or "업무 흐름", 120) or "업무 흐름"
        source_refs = list(
            dict.fromkeys(
                ref
                for item in [*nodes, *edges]
                for ref in item.get("source_refs") or []
                if ref
            )
        )
        outgoing_counts: dict[str, int] = {}
        for item in edges:
            outgoing_counts[item["from"]] = outgoing_counts.get(item["from"], 0) + 1
        direction = "LR" if max(outgoing_counts.values(), default=0) >= 3 else "TD"
        lines = [f"flowchart {direction}"]
        for item in nodes:
            lines.append(f'  {item["node_id"]}["{item["label"]}"]')
        for item in edges:
            lines.append(f'  {item["from"]} -->|"{item["label"]}"| {item["to"]}')
        return {
            "title": title,
            "nodes": nodes,
            "edges": edges,
            "source_refs": source_refs,
            "mermaid": "\n".join(lines),
        }

    def _mermaid_artifact(
        self,
        principal: Principal,
        *,
        request: AgentTurnRequest,
        session: dict[str, Any],
        intent: WorkIntent,
        evidence: list[EvidenceRef],
        citations: list[CitationRef],
        work_run_id: str,
    ) -> tuple[AnswerBlock, ArtifactRef, list[RelatedQuestion]]:
        if not self.model.readiness().get("generation"):
            raise RuntimeError("흐름 그림을 만들 모델이 준비되지 않았습니다.")
        citation_by_source = {item.source_ref: item for item in citations}
        allowed_asset_kinds = {item.value for item in intent.requested_asset_kinds} or {intent.asset_kind.value}
        focal_refs = list(dict.fromkeys([*intent.context_refs, intent.target_ref]))
        candidates = [
            item
            for item in evidence
            if item.evidence_id in citation_by_source
        ]
        top_score = max((float(item.score or 0.0) for item in candidates), default=0.0)
        grounded = [
            item
            for item in candidates
            if not top_score
            or float(item.score or 0.0) >= top_score * 0.55
            or item.evidence_id in focal_refs
        ][:6]
        diagram_citations = [citation_by_source[item.evidence_id] for item in grounded]
        if not diagram_citations:
            raise RuntimeError("흐름 그림을 만들 확인 가능한 Wiki 근거가 없습니다.")
        source_payload = [
            {
                "number": index + 1,
                "source_ref": citation.source_ref,
                "title": item.title,
                "kind": item.kind,
                "heading": citation.heading,
                "excerpt": compact_text(citation.excerpt or item.summary, 900),
            }
            for index, (item, citation) in enumerate(zip(grounded, diagram_citations))
        ]
        system = (
            "You create a grounded workplace relationship graph in Korean. Use only the supplied source excerpts. "
            "Return structured nodes and directed edges, never raw Mermaid. Every node and edge must cite at least one "
            "source number that directly supports it. Keep labels short and useful to a general employee. Do not invent "
            "a system, step, dependency, or sequence that the evidence does not support. Classify every node with one "
            "allowed asset_kind. asset_kind is a strict scope tag, not a free-form description: every node must use exactly "
            "one value from the supplied Allowed asset kinds list. Keep the graph focused on the resolved request and focal "
            "sources. Do not expand into SOP, "
            "Task, Event, or Action unless those asset kinds are explicitly allowed. Return optional related questions only "
            "when their source numbers directly support them. Write the title and every visible label in natural Korean. "
            "Never expose file names, storage identifiers, snake_case schema fields, or raw relation keys; explain their "
            "meaning in ordinary workplace language unless the user explicitly requested the technical schema."
        )
        prompt = (
            f"Resolved request: {intent.resolved_goal or request.question}\n"
            f"Result purpose: {intent.result_purpose}\n"
            f"Allowed asset kinds: {json.dumps(sorted(allowed_asset_kinds), ensure_ascii=False)}\n"
            f"Focal source refs: {json.dumps(focal_refs, ensure_ascii=False)}\n"
            f"Recent work context: {json.dumps(request.input_delta.get('_work_session_context') or {}, ensure_ascii=False)}\n"
            f"Sources: {json.dumps(source_payload, ensure_ascii=False)}\n"
            "Create a readable flow with at most 14 nodes and 20 edges."
        )
        validation_error = ""
        graph: dict[str, Any] = {}
        for attempt in range(2):
            repair_prompt = prompt
            if validation_error:
                repair_prompt += (
                    f"\nThe prior graph failed deterministic validation: {validation_error}. "
                    "Regenerate the whole graph once. Remove any node outside the resolved request, use only the exact "
                    f"allowed asset_kind values {json.dumps(sorted(allowed_asset_kinds), ensure_ascii=False)}, and replace "
                    "schema-shaped visible labels with ordinary Korean descriptions. Do not repeat the invalid value."
                )
            raw_graph = self.model.generate_structured(
                system=system,
                prompt=repair_prompt,
                schema=MERMAID_GRAPH_SCHEMA,
            )
            try:
                graph = self._normalise_mermaid_graph(
                    raw_graph,
                    diagram_citations,
                    focal_refs=focal_refs,
                    allowed_asset_kinds=allowed_asset_kinds,
                )
                break
            except RuntimeError as exc:
                validation_error = str(exc)
                if attempt == 1:
                    raise

        artifact_id = new_id("artifact")
        title = graph["title"]
        actions = self._artifact_actions_for_intent(intent, artifact_id)
        payload = {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": "knowledge.search",
            "artifact_type": "mermaid_diagram",
            "status": "provisional",
            "title": title,
            "draft": graph,
            "work_session_id": str(session["session_id"]),
            "work_run_id": work_run_id,
            "revision": 1,
            "evidence_ledger": [
                {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "url": item.url,
                }
                for item in grounded
            ],
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "generation_attempts": 2 if validation_error else 1,
            "actions": [item.model_dump(mode="json") for item in actions],
        }
        self.store.put("artifacts", artifact_id, payload)
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type="mermaid_diagram",
            title=title,
            status="provisional",
            url=f"/agent?session={session['session_id']}&artifact={artifact_id}",
            preview="흐름 그림",
            metadata={
                "capability_id": "knowledge.search",
                "revision": 1,
                "node_count": len(graph["nodes"]),
                "edge_count": len(graph["edges"]),
                "source_refs": graph["source_refs"],
            },
            actions=actions,
        )
        answer = AnswerBlock(
            summary=f"'{title}' 흐름 그림을 만들었습니다.",
            markdown=(
                f"### {title}\n\n검토된 Wiki 근거 {len(graph['source_refs'])}개를 바탕으로 실제 흐름 그림을 만들었습니다. "
                "결과 영역에서 질문과 직접 연결된 관계와 원문 근거를 확인할 수 있습니다. "
                + " ".join(
                    f"[{index}](/api/v2/citations/{citation.citation_id})"
                    for index, citation in enumerate(diagram_citations[:2], start=1)
                )
            ),
        )
        related = self._model_related_questions(
            principal,
            session,
            raw_graph.get("related_questions"),
            diagram_citations,
        )
        return answer, artifact, related

    def _split_mermaid_artifact_into_tasks(
        self,
        principal: Principal,
        *,
        source_artifact: dict[str, Any],
        session: dict[str, Any],
        work_run_id: str,
        page_ref: str,
    ) -> tuple[AnswerBlock, ArtifactRef]:
        if not self.domain_services.supports("mermaid.workflow_draft.create"):
            raise RuntimeError("Task 후보 변환 서비스가 준비되지 않았습니다.")
        source_draft = source_artifact.get("draft") if isinstance(source_artifact.get("draft"), dict) else {}
        mermaid_source = str(source_draft.get("mermaid") or "").strip()
        if not mermaid_source:
            raise RuntimeError("Task로 나눌 흐름 그림 원문이 없습니다.")
        source_title = str(source_artifact.get("title") or "업무 흐름").strip()
        result = self.domain_services.execute(
            "mermaid.workflow_draft.create",
            principal,
            {
                "title": f"{source_title} Task 후보",
                "mermaid_source": mermaid_source,
                "current_url": page_ref,
                "note": "BoI Agent에서 사용자가 명시적으로 Task 분해를 요청함",
                "source_artifact_id": str(source_artifact.get("artifact_id") or ""),
                "work_session_id": str(session.get("session_id") or ""),
            },
        )
        domain_draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        raw_tasks = [item for item in domain_draft.get("workflow_tasks") or [] if isinstance(item, dict)]
        if not raw_tasks:
            raise RuntimeError("흐름에서 확인 가능한 Task 후보를 찾지 못했습니다.")
        tasks = [
            self._normalise_sop_task(
                {
                    **item,
                    "purpose": str(item.get("purpose") or ""),
                    "required_evidence": item.get("required_evidence") or [],
                    "outputs": item.get("outputs") or [],
                },
                index,
                principal=principal,
            )
            for index, item in enumerate(raw_tasks[:20])
        ]
        artifact_id = new_id("artifact")
        title = str(domain_draft.get("title") or f"{source_title} Task 후보")
        draft = {
            "title": title,
            "goal": "기존 흐름을 실행 가능한 Task 후보로 나눈 나만의 초안",
            "tasks": tasks,
            "workflow_edges": domain_draft.get("workflow_edges") or [],
            "candidate_links": domain_draft.get("candidate_links") or {},
            "mermaid": self._mermaid_from_tasks(tasks),
            "source_artifact_id": str(source_artifact.get("artifact_id") or ""),
            "source_mermaid": mermaid_source,
            "domain_ref": str(result.get("domain_ref") or domain_draft.get("draft_id") or ""),
        }
        evidence_ledger = [
            item
            for item in source_artifact.get("evidence_ledger") or []
            if isinstance(item, dict)
        ]
        payload = {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": "workflow.transform",
            "artifact_type": "workflow_draft",
            "status": "draft",
            "title": title,
            "draft": draft,
            "work_session_id": str(session.get("session_id") or ""),
            "work_run_id": work_run_id,
            "revision": 1,
            "evidence_ledger": evidence_ledger,
            "domain": result,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("artifacts", artifact_id, payload)
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type="workflow_draft",
            title=title,
            status="draft",
            url=f"/agent?session={session['session_id']}&artifact={artifact_id}",
            preview=f"Task 후보 {len(tasks)}개",
            metadata={
                "capability_id": "workflow.transform",
                "revision": 1,
                "task_count": len(tasks),
                "source_artifact_id": str(source_artifact.get("artifact_id") or ""),
                "domain_ref": draft["domain_ref"],
            },
            actions=[],
        )
        answer = AnswerBlock(
            summary=f"'{source_title}'을 Task 후보 {len(tasks)}개로 나눴습니다.",
            markdown=(
                f"### {title}\n\n기존 흐름과 근거를 유지한 나만 보는 Task 후보입니다. "
                "아직 SOP 초안을 만들거나 게시하지 않았습니다. 결과 영역에서 Task 이름과 완료 항목을 확인하세요."
            ),
        )
        return answer, artifact

    def _work_routine_plan(
        self,
        principal: Principal,
        *,
        request: AgentTurnRequest,
        session: dict[str, Any],
        intent: WorkIntent,
        evidence: list[EvidenceRef],
        work_run_id: str,
    ) -> tuple[AnswerBlock, ArtifactRef, str]:
        if not self.model.readiness().get("generation"):
            raise RuntimeError("자동 확인 계획을 만들 모델이 준비되지 않았습니다.")
        source_refs = list(dict.fromkeys([*intent.context_refs, *[item.evidence_id for item in evidence[:6]]]))[:8]
        source_payload = [
            {
                "source_ref": item.evidence_id,
                "title": item.title,
                "kind": item.kind,
                "summary": compact_text(item.summary, 500),
            }
            for item in evidence[:6]
        ]
        system = (
            "You design one safe recurring workplace check in Korean. Interpret the request semantically and return "
            "a preview only. Choose event when a known business state or event should trigger the check, schedule for "
            "calendar-based timing, and interval only for elapsed-time polling. Do not invent an event reference. Use a "
            "calendar object for schedule requests: minutes and hours are required integer arrays; days_of_month, "
            "months, and weekdays use empty arrays to mean every value. Use weekday 0 for Sunday through 6 for "
            "Saturday. Leave cron empty because the server compiles it. State a clear stopping condition in ordinary "
            "workplace language. Use max_runs only when the user explicitly gave a finite run count and always provide "
            "that positive count; otherwise use cancelled. Use event_resolved only with an event trigger. The routine "
            "will not be created until the user confirms the plan."
        )
        prompt = (
            f"Resolved request: {intent.resolved_goal or request.question}\n"
            f"Current page: {request.page_ref or '-'}\n"
            f"Trusted context refs: {json.dumps(intent.context_refs, ensure_ascii=False)}\n"
            f"Available sources: {json.dumps(source_payload, ensure_ascii=False)}\n"
            "Create one minimal automatic-check preview."
        )
        validation_error = ""
        draft: dict[str, Any] = {}
        for attempt in range(2):
            repair_prompt = prompt
            if validation_error:
                repair_prompt += f"\nThe prior preview failed validation: {validation_error}. Regenerate it."
            draft = self.model.generate_structured(
                system=system,
                prompt=repair_prompt,
                schema=DRAFT_SCHEMAS["work_routine.plan"],
            )
            try:
                self._validate_draft("work_routine.plan", draft)
                trigger = str(draft.get("trigger") or "")
                if trigger == "schedule":
                    draft["cron"] = self._compile_calendar_cron(draft.get("calendar"))
                    if not croniter.is_valid(str(draft["cron"])):
                        raise RuntimeError("일정에 유효한 반복 시간이 필요합니다.")
                if trigger == "event" and not str(draft.get("event_ref") or "").strip():
                    raise RuntimeError("상태 변화로 확인하려면 연결할 업무 이벤트가 필요합니다.")
                self._normalise_routine_stop(draft)
                break
            except (RuntimeError, TypeError, ValueError) as exc:
                validation_error = str(exc)
                if attempt == 1:
                    raise RuntimeError(validation_error) from exc

        trigger = str(draft.get("trigger") or "interval")
        routine_request = WorkRoutineCreateRequest(
            title=compact_text(str(draft.get("title") or "자동 확인"), 160),
            goal=compact_text(str(draft.get("goal") or intent.resolved_goal or request.question), 12000),
            capability_id="knowledge.search",
            page_ref=request.page_ref,
            task_ref=request.task_ref,
            trigger=trigger,  # type: ignore[arg-type]
            interval_seconds=max(60, int(draft.get("interval_seconds") or 300)),
            cron=str(draft.get("cron") or "").strip(),
            timezone=compact_text(str(draft.get("timezone") or "Asia/Seoul"), 80),
            event_ref=compact_text(str(draft.get("event_ref") or ""), 1000),
            routine_stop=str(draft.get("routine_stop") or "cancelled"),  # type: ignore[arg-type]
            max_runs=max(0, int(draft.get("max_runs") or 0)),
            input={
                "source_refs": source_refs,
                "completion_condition": compact_text(str(draft.get("completion_condition") or ""), 2000),
                "schedule_description": compact_text(str(draft.get("schedule_description") or ""), 500),
                "target_ref": compact_text(str(draft.get("target_ref") or intent.target_ref or ""), 1000),
            },
            origin="user",
            surface_visibility="normal",
        )
        draft.update(
            {
                "title": routine_request.title,
                "goal": routine_request.goal,
                "source_refs": source_refs,
                "confirmation_required": True,
            }
        )
        artifact_id = new_id("artifact")
        plan_id = new_id("plan")
        now = now_iso()
        self.store.put(
            "artifacts",
            artifact_id,
            {
                "artifact_id": artifact_id,
                "employee_id": principal.employee_id,
                "capability_id": "work_routine.plan",
                "artifact_type": "work_routine_draft",
                "status": "draft",
                "title": routine_request.title,
                "draft": draft,
                "work_session_id": str(session["session_id"]),
                "work_run_id": work_run_id,
                "revision": 1,
                "evidence_ledger": [
                    {"evidence_id": item.evidence_id, "title": item.title, "url": item.url}
                    for item in evidence[:6]
                ],
                "created_at": now,
                "updated_at": now,
            },
        )
        self.store.put(
            "plans",
            plan_id,
            {
                "plan_id": plan_id,
                "employee_id": principal.employee_id,
                "capability_id": "work_routine.plan",
                "artifact_id": artifact_id,
                "status": "draft",
                "risk": "medium",
                "domain_operation": "work_routine.create",
                "domain_payload": routine_request.model_dump(mode="json"),
                "domain_validation": {"valid": True, "errors": [], "warnings": []},
                "production_changed": False,
                "work_run_id": work_run_id,
                "created_at": now,
            },
        )
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type="work_routine_draft",
            title=routine_request.title,
            status="draft",
            url=f"/agent?session={session['session_id']}&artifact={artifact_id}",
            preview=str(draft.get("schedule_description") or "자동 확인 계획"),
            metadata={"plan_id": plan_id, "capability_id": "work_routine.plan", "revision": 1},
        )
        answer = AnswerBlock(
            summary=f"'{routine_request.title}' 자동 확인 계획을 준비했습니다.",
            markdown="\n".join(
                [
                    f"### {routine_request.title}",
                    f"- 목적: {routine_request.goal}",
                    f"- 다시 확인: {draft.get('schedule_description')}",
                    f"- 끝내는 기준: {draft.get('completion_condition')}",
                    "",
                    "아직 자동 확인을 만들지 않았습니다. 계획을 확인한 뒤 활성화할 수 있습니다.",
                ]
            ),
        )
        return answer, artifact, plan_id

    @staticmethod
    def _compile_calendar_cron(value: Any) -> str:
        if not isinstance(value, dict):
            raise RuntimeError("일정의 시각과 반복 주기가 필요합니다.")

        def field(name: str, minimum: int, maximum: int, *, required: bool = False) -> str:
            raw = value.get(name)
            if not isinstance(raw, list):
                raise RuntimeError("일정 값은 시·분·요일 단위로 정리되어야 합니다.")
            numbers = sorted(
                {
                    int(item)
                    for item in raw
                    if isinstance(item, int) and not isinstance(item, bool) and minimum <= item <= maximum
                }
            )
            if required and not numbers:
                raise RuntimeError("일정에 확인할 시각이 필요합니다.")
            return ",".join(str(item) for item in numbers) if numbers else "*"

        return " ".join(
            [
                field("minutes", 0, 59, required=True),
                field("hours", 0, 23, required=True),
                field("days_of_month", 1, 31),
                field("months", 1, 12),
                field("weekdays", 0, 6),
            ]
        )

    @staticmethod
    def _normalise_routine_stop(draft: dict[str, Any]) -> None:
        stop = str(draft.get("routine_stop") or "cancelled")
        trigger = str(draft.get("trigger") or "")
        try:
            max_runs = int(draft.get("max_runs") or 0)
        except (TypeError, ValueError):
            max_runs = 0
        if (stop == "max_runs" and max_runs < 1) or (stop == "event_resolved" and trigger != "event"):
            draft["routine_stop"] = "cancelled"
            draft["max_runs"] = 0

    @staticmethod
    def _inbox_answer(items: list[EvidenceRef]) -> AnswerBlock:
        if not items:
            message = "현재 처리할 Inbox 업무가 없습니다. 과거 seed 이력은 현재 업무에 포함하지 않았습니다."
            return AnswerBlock(summary=message, markdown=message)
        lines = [f"현재 처리할 업무가 {len(items)}건 있습니다.", ""]
        for item in items:
            lines.append(f"- [{item.title}]({item.url}): {item.summary or item.metadata.get('status', '확인 필요')}")
        return AnswerBlock(summary=lines[0], markdown="\n".join(lines))

    def _graph_plan_for_intent(self, principal: Principal, intent: WorkIntent) -> GraphQueryPlan | None:
        draft = intent.graph_query_draft
        if not draft or not draft.enabled:
            return None
        records = self.repository.authoritative_records(principal, include_drafts=True)
        records.extend(self.repository.history_records(principal, include_seed=False))
        focal_entities = self.entity_resolver.resolve_many(
            draft.focal_mentions,
            principal=principal,
            records=records,
        )
        if not focal_entities and intent.work_view in {"responsibility", "combined"}:
            focal_entities.append(f"person:{principal.employee_id}")
        if not focal_entities and intent.target_ref:
            focal_entities.append(intent.target_ref)
        if not focal_entities:
            return None

        target_entities = self.entity_resolver.resolve_many(
            draft.target_mentions,
            principal=principal,
            records=records,
        )
        return GraphQueryPlan(
            focal_entities=list(dict.fromkeys(focal_entities))[:20],
            target_entities=list(dict.fromkeys(target_entities))[:20],
            query_kind=draft.query_kind,
            node_kinds=draft.node_kinds,
            relation_kinds=draft.relation_kinds,
            direction=draft.direction,
            depth=draft.depth,
            limit=80,
            time_from=draft.time_from,
            time_to=draft.time_to,
            presentation=draft.presentation,
        )

    def _graph_result_artifact(
        self,
        principal: Principal,
        *,
        session: dict[str, Any],
        intent: WorkIntent,
        current_work: list[EvidenceRef],
        work_run_id: str,
    ) -> tuple[AnswerBlock, ArtifactRef, list[EvidenceRef]] | None:
        plan = self._graph_plan_for_intent(principal, intent)
        if not plan:
            return None
        result = self.knowledge.query(principal, plan)
        nodes = [item for item in result.get("nodes") or [] if isinstance(item, dict)]
        edges = [item for item in result.get("edges") or [] if isinstance(item, dict)]
        if not nodes:
            return None
        node_lookup = {str(item.get("node_id") or ""): item for item in nodes}
        relation_labels = {
            "assigned_to": "현재 담당",
            "reviewed_by": "검토 담당",
            "performed_by": "수행 기록",
            "completed_by": "검증 완료",
            "repeated_performer": "반복 수행",
            "related_team": "관련 조직",
            "has_task": "포함 Task",
            "uses_sop": "관련 SOP",
            "uses_event": "관련 업무 이벤트",
            "uses_action": "관련 Action",
            "requires_evidence": "확인할 근거",
            "member_of": "소속 조직",
            "has_role": "공식 역할",
            "evidence": "근거 연결",
            "links_to": "지식 연결",
        }
        relation_lines: list[str] = []
        source_refs: list[str] = []
        for edge in edges[:24]:
            source_id = str(edge.get("source_id") or "")
            target_id = str(edge.get("target_id") or "")
            source = node_lookup.get(source_id) or {}
            target = node_lookup.get(target_id) or {}
            source_payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
            target_payload = target.get("payload") if isinstance(target.get("payload"), dict) else {}
            source_title = str(source_payload.get("title") or source_id)
            target_title = str(target_payload.get("title") or target_id)
            relation = str(edge.get("relation") or "related")
            relation_lines.append(f"- {source_title} — {relation_labels.get(relation, relation)} → {target_title}")
            payload = edge.get("payload") if isinstance(edge.get("payload"), dict) else {}
            source_refs.extend(str(item) for item in payload.get("source_refs") or [] if str(item))
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if metadata.get("source_ref"):
                source_refs.append(str(metadata["source_ref"]))
        source_refs.extend(
            str((item.get("payload") or {}).get("source_ref") or "")
            for item in nodes
            if isinstance(item.get("payload"), dict)
        )
        source_refs = list(dict.fromkeys(item for item in source_refs if item))[:40]

        lines = ["### 확인된 업무 관계"]
        lines.extend(relation_lines[:12] or ["- 검증된 업무 관계가 아직 없습니다."])
        if intent.work_view == "combined":
            lines.extend(["", "### 지금 처리할 업무"])
            lines.extend(
                f"- [{item.title}]({item.url}){f': {item.summary}' if item.summary else ''}"
                for item in current_work[:8]
            )
            if not current_work:
                lines.append("- 현재 처리할 Inbox 업무가 없습니다.")
        summary = (
            f"확인 가능한 업무 관계 {len(edges)}건과 현재 업무 {len(current_work)}건을 구분해 정리했습니다."
            if intent.work_view == "combined"
            else f"확인 가능한 업무 관계 {len(edges)}건을 정리했습니다."
        )
        artifact_id = new_id("artifact")
        title = "업무 역할과 연결 관계" if intent.work_view in {"responsibility", "combined"} else "지식 연결 관계"
        stored = {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": "knowledge.search",
            "artifact_type": "ontology_graph",
            "status": "provisional",
            "title": title,
            "draft": {
                "query_plan": result.get("query_plan") or plan.model_dump(mode="json"),
                "presentation": result.get("presentation") or "list",
                "nodes": nodes,
                "edges": edges,
                "source_refs": source_refs,
            },
            "work_session_id": str(session["session_id"]),
            "work_run_id": work_run_id,
            "revision": 1,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("artifacts", artifact_id, stored)
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type="ontology_graph",
            title=title,
            status="provisional",
            url=f"/agent?session={session['session_id']}&artifact={artifact_id}",
            preview=summary,
            metadata={
                "capability_id": "knowledge.search",
                "revision": 1,
                "presentation": stored["draft"]["presentation"],
                "node_count": len(nodes),
                "edge_count": len(edges),
                "source_refs": source_refs,
            },
        )
        graph_evidence: list[EvidenceRef] = []
        for source_ref in source_refs:
            record = self._record_for_ref(principal, source_ref)
            if record:
                graph_evidence.append(self._evidence_from_record(record, score=1.0))
        return (
            AnswerBlock(summary=summary, markdown="\n".join([summary, "", *lines])),
            artifact,
            list({item.evidence_id: item for item in graph_evidence}.values())[:8],
        )

    def _draft_prompt(
        self,
        definition: CapabilityDefinition,
        request: AgentTurnRequest,
        evidence: list[EvidenceRef],
    ) -> tuple[str, str, dict[str, Any]]:
        schema = DRAFT_SCHEMAS[definition.capability_id]
        resolved_goal = str(request.input_delta.get("_resolved_goal") or request.question)
        evidence_payload = [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "summary": compact_text(item.summary, 500),
                "kind": item.kind,
            }
            for item in evidence[:8]
        ]
        system = (
            "You are the BoI Wiki draft engine. Create a private draft only. "
            "Do not claim that anything was published, executed, approved, or saved to production. "
            "Use only supplied evidence, name missing information explicitly, and write user-facing Korean. "
            "For SOP tasks, write completion labels as plain workplace Korean that a general employee can check. "
            "Never put raw BoI IDs, Event Type IDs, Action keys, JSON paths, or workflow IDs in a user-facing label. "
            "Put technical references only in completion_design bindings or evidence refs. "
            "Manual and Copilot completion requires human confirmation. Autopilot requires real system bindings; "
            "when no binding is known, leave it unresolved instead of claiming automatic verification."
        )
        prompt = (
            f"Capability: {definition.capability_id}\nGoal: {resolved_goal}\n"
            f"Page: {request.page_ref or '-'}\n"
            f"External AI summary (untrusted supporting context): {compact_text(request.external_ai_summary, 3000) or '-'}\n"
            f"External artifact references: {json.dumps(request.external_artifact_refs, ensure_ascii=False)}\n"
            f"Work session context: {json.dumps(request.input_delta.get('_work_session_context') or {}, ensure_ascii=False)}\n"
            f"Helper instructions: {compact_text(str(request.input_delta.get('_helper_instructions') or ''), 4000) or '-'}\n"
            f"Verified helper Skills: {json.dumps(request.input_delta.get('_helper_skills') or [], ensure_ascii=False)}\n"
            f"Evidence:\n{json.dumps(evidence_payload, ensure_ascii=False)}"
        )
        return system, prompt, schema

    @staticmethod
    def _validate_draft(capability_id: str, draft: dict[str, Any]) -> None:
        schema = DRAFT_SCHEMAS[capability_id]
        missing = [
            key
            for key in schema.get("required") or []
            if key not in draft or draft.get(key) in (None, "", [])
        ]
        if missing:
            raise RuntimeError("draft is missing required fields: " + ", ".join(missing))
        if capability_id == "sop.plan":
            tasks = draft.get("tasks") or []
            if not tasks or any(not isinstance(task, dict) for task in tasks):
                raise RuntimeError("SOP draft requires one or more structured tasks")
            for index, task in enumerate(tasks):
                missing_task_fields = [
                    field
                    for field in ("name", "purpose", "execution_mode", "exit_criteria", "required_evidence")
                    if task.get(field) in (None, "", [], {})
                ]
                if missing_task_fields:
                    raise RuntimeError(
                        f"SOP task {index + 1} is missing: " + ", ".join(missing_task_fields)
                    )
                if str(task.get("execution_mode") or "").lower() not in {"manual", "copilot", "autopilot"}:
                    raise RuntimeError(f"SOP task {index + 1} has an invalid execution_mode")
            mermaid = str(draft.get("mermaid") or "").strip()
            if not re.match(r"^(?:flowchart|graph)\s+", mermaid, flags=re.IGNORECASE):
                raise RuntimeError("SOP draft mermaid must start with flowchart or graph")
        if capability_id == "action.plan" and draft.get("preview_only") is not True:
            raise RuntimeError("Action draft must remain preview_only")
        if capability_id == "skill.plan":
            tests = [item for item in draft.get("tests") or [] if isinstance(item, dict)]
            if not tests or any(
                not isinstance(item.get("sample_input"), dict)
                or not isinstance(item.get("expected_contains"), list)
                or not item.get("expected_contains")
                for item in tests
            ):
                raise RuntimeError("Skill draft requires a runnable sample_input and expected_contains test")
        if capability_id == "knowledge.draft" and draft.get("status") != "provisional":
            raise RuntimeError("knowledge draft must remain provisional")

    def _normalise_sop_task(
        self,
        task: dict[str, Any],
        index: int,
        *,
        principal: Principal | None = None,
    ) -> dict[str, Any]:
        normalised = dict(task)
        normalised["task_id"] = str(task.get("task_id") or new_id("task"))
        task_name = str(task.get("name") or f"Task {index + 1}").strip()
        normalised["name"] = re.sub(r"^\d+[.)]\s*", "", task_name) or f"Task {index + 1}"
        normalised["purpose"] = str(task.get("purpose") or task.get("goal") or "").strip()
        mode = str(task.get("execution_mode") or task.get("mode") or "copilot").lower()
        normalised["execution_mode"] = mode if mode in {"manual", "copilot", "autopilot"} else "copilot"
        for field in (
            "exit_criteria",
            "required_evidence",
            "outputs",
            "action_refs",
            "event_refs",
            "skill_refs",
            "verification",
            "fallback",
        ):
            value = task.get(field) or []
            if isinstance(value, str):
                value = [item.strip() for item in re.split(r"[\n,]", value) if item.strip()]
            normalised[field] = [str(item) for item in value if str(item).strip()]
        normalised["tat"] = str(task.get("tat") or task.get("target_tat") or "")
        label_lookup = self._completion_label_lookup(principal) if principal is not None else {}
        normalised = normalise_task_completion(normalised, label_lookup=label_lookup)
        normalised["completion_design"] = TaskCompletionDesign.model_validate(
            normalised.get("completion_design")
        ).model_dump(mode="json", exclude_none=True)
        return normalised

    @staticmethod
    def _mermaid_from_tasks(tasks: list[dict[str, Any]]) -> str:
        lines = ["flowchart TD"]
        if not tasks:
            lines.append('  empty["Task를 추가하세요"]')
            return "\n".join(lines)
        for index, task in enumerate(tasks):
            node_id = f"T{index + 1}"
            name = str(task.get("name") or f"Task {index + 1}").replace('"', "'").replace("\n", " ")[:80]
            mode = str(task.get("execution_mode") or "copilot").capitalize()
            lines.append(f'  {node_id}["{index + 1}. {name}<br/>{mode}"]')
            if index:
                lines.append(f"  T{index} --> {node_id}")
        return "\n".join(lines)

    def _normalise_sop_draft(self, draft: dict[str, Any], *, principal: Principal | None = None) -> dict[str, Any]:
        normalised = dict(draft)
        tasks = [
            self._normalise_sop_task(item, index, principal=principal)
            for index, item in enumerate(draft.get("tasks") or [])
            if isinstance(item, dict)
        ]
        normalised["tasks"] = tasks
        normalised["mermaid"] = self._mermaid_from_tasks(tasks)
        normalised.setdefault("gaps", [])
        return normalised

    def _draft(
        self,
        principal: Principal,
        definition: CapabilityDefinition,
        request: AgentTurnRequest,
        evidence: list[EvidenceRef],
        *,
        work_run_id: str = "",
    ) -> tuple[AnswerBlock, ArtifactRef, str]:
        system, prompt, schema = self._draft_prompt(definition, request, evidence)
        validation_error = ""
        draft: dict[str, Any] = {}
        for attempt in range(2):
            repair_prompt = prompt
            if validation_error:
                repair_prompt += (
                    "\nThe previous draft was rejected by deterministic validation: "
                    f"{validation_error}. Regenerate the entire object and satisfy every required field."
                )
            draft = self.model.generate_structured(system=system, prompt=repair_prompt, schema=schema)
            try:
                self._validate_draft(definition.capability_id, draft)
                break
            except RuntimeError as exc:
                validation_error = str(exc)
                if attempt == 1:
                    raise
        if definition.capability_id == "sop.plan":
            draft = self._normalise_sop_draft(draft, principal=principal)
        title = str(draft.get("title") or definition.title).strip()
        title = re.sub(r"^\[(?:비공개\s*초안|private\s*draft)\]\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"^(?:비공개\s*(?:SOP\s*)?초안|private\s*draft)\s*[:：-]\s*", "", title, flags=re.IGNORECASE)
        title = title or definition.title
        draft["title"] = title
        self.evaluator.model = self.model
        independent_review = self.evaluator.evaluate(
            principal,
            artifact_kind=str(definition.output_schema.get("type") or "draft"),
            goal=request.question,
            artifact=draft,
            evidence=[item.model_dump(mode="json") for item in evidence[:12]],
            rubric=[
                "요청한 업무 목표를 실제로 충족하는가",
                "중요한 판단과 제안이 제공된 근거로 추적 가능한가",
                "현재 업무 맥락과 직접 관련된 근거를 사용하고 무관한 자산을 끌어오지 않았는가",
                "사용자가 요청하지 않은 SOP, Event, Action 또는 실행 작업으로 과도하게 전환하지 않았는가",
                "누락 정보와 불확실성을 성공처럼 표현하지 않았는가",
                *definition.completion_criteria,
            ],
            work_run_id=work_run_id,
            require_evidence_refs=True,
        )
        artifact_id = new_id("artifact")
        plan_id = new_id("plan")
        domain_operation = {
            "sop.plan": "sop.draft.create",
            "business_event.plan": "business_event.draft.create",
            "action.plan": "action.draft.create",
            "skill.plan": "skill.draft.create",
        }.get(definition.capability_id, "")
        domain_result: dict[str, Any] = {}
        if domain_operation and self.domain_services.supports(domain_operation):
            domain_result = self.domain_services.execute(
                domain_operation,
                principal,
                {
                    "artifact_id": artifact_id,
                    "plan_id": plan_id,
                    "capability_id": definition.capability_id,
                    "goal": request.question,
                    "page_ref": request.page_ref,
                    "task_ref": request.task_ref,
                    "work_session_id": request.work_session_id or "",
                    "draft": copy.deepcopy(draft),
                    "evidence_refs": [item.model_dump(mode="json") for item in evidence[:12]],
                },
            )
        artifact_type = str(definition.output_schema.get("type") or "draft")
        artifact_status = "provisional" if definition.capability_id == "knowledge.draft" else "draft"
        payload = {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": definition.capability_id,
            "artifact_type": artifact_type,
            "status": artifact_status,
            "title": title,
            "draft": draft,
            "work_session_id": request.work_session_id or "",
            "revision": 1,
            "evidence_ledger": [
                {"evidence_id": item.evidence_id, "title": item.title, "url": item.url}
                for item in evidence
            ],
            "domain": domain_result,
            "independent_review": independent_review,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "generation_attempts": 2 if validation_error else 1,
        }
        self.store.put("artifacts", artifact_id, payload)
        self.store.put(
            "plans",
            plan_id,
            {
                "plan_id": plan_id,
                "employee_id": principal.employee_id,
                "capability_id": definition.capability_id,
                "artifact_id": artifact_id,
                "status": "draft",
                "risk": definition.risk.value,
                "domain_operation": str(domain_result.get("confirm_operation") or ""),
                "domain_ref": str(domain_result.get("domain_ref") or ""),
                "domain_kind": str(domain_result.get("domain_kind") or ""),
                "domain_validation": domain_result.get("validation") or {},
                "evaluation_ref": str(independent_review.get("evaluation_id") or ""),
                "review_status": str(independent_review.get("status") or "unavailable"),
                "production_changed": False,
                "work_run_id": work_run_id,
                "created_at": now_iso(),
            },
        )
        preview = json.dumps(draft, ensure_ascii=False, indent=2)[:1800]
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            status=artifact_status,  # type: ignore[arg-type]
            url=(
                f"/agent?session={request.work_session_id}&artifact={artifact_id}"
                if request.work_session_id
                else f"/agent?artifact={artifact_id}"
            ),
            preview=preview,
            metadata={
                "plan_id": plan_id,
                "capability_id": definition.capability_id,
                "mermaid": str(draft.get("mermaid") or "") if definition.capability_id == "sop.plan" else "",
                "revision": 1,
                "task_count": len(draft.get("tasks") or []) if definition.capability_id == "sop.plan" else 0,
                "domain_ref": str(domain_result.get("domain_ref") or ""),
                "domain_kind": str(domain_result.get("domain_kind") or ""),
                "domain_status": str(domain_result.get("status") or ""),
                "evaluation_ref": str(independent_review.get("evaluation_id") or ""),
                "review_status": str(independent_review.get("status") or "unavailable"),
            },
        )
        task_summary = ""
        if definition.capability_id == "sop.plan":
            task_summary = f"\n\nTask {len(draft.get('tasks') or [])}개와 각 Task의 종료 기준·필수 근거를 결과 영역에 정리했습니다."
        review_summary = ""
        if independent_review.get("status") == "needs_revision":
            review_summary = "\n\n별도 검토에서 보완할 점이 확인되었습니다. 결과 영역의 검토 내용을 반영한 뒤 게시를 요청하세요."
        answer = AnswerBlock(
            summary=f"'{title}' 개인 초안을 만들었습니다. 아직 게시하거나 실행하지 않았습니다.",
            markdown=(
                f"### {title}\n\n개인 초안입니다. 근거와 누락 항목을 확인한 뒤 다음 단계를 선택하세요."
                f"{task_summary}"
                f"{review_summary}"
                + (
                    f"\n\n기존 {domain_result.get('domain_label') or '업무'} 초안 `{domain_result.get('domain_ref')}`과 연결했습니다."
                    if domain_result.get("domain_ref")
                    else ""
                )
            ),
        )
        return answer, artifact, plan_id

    def _queue_deep_job(
        self,
        principal: Principal,
        definition: CapabilityDefinition,
        request: AgentTurnRequest,
        context: WorkContextPack,
        *,
        work_session_id: str,
    ) -> str:
        job_id = new_id("job")
        pilot_mode = bool(request.input_delta.get("pilot_mode", True))
        requested_tools = int(request.input_delta.get("max_tool_calls") or 5)
        max_tool_calls = max(1, min(requested_tools, 5 if pilot_mode else 12))
        requested_budget = int(request.input_delta.get("token_budget") or self.settings.deep_token_budget)
        token_budget = max(4000, min(requested_budget, 160000 if pilot_mode else 200000))
        requested_subagents = int(request.input_delta.get("max_subagents") if request.input_delta.get("max_subagents") is not None else 2)
        subagent_budget_limit = deep_subagent_budget_limit(
            token_budget,
            self.settings.deep_max_input_tokens,
            hard_limit=2 if pilot_mode else 4,
        )
        max_subagents = max(0, min(requested_subagents, 2 if pilot_mode else 4, subagent_budget_limit))
        require_subagent = bool(request.input_delta.get("require_subagent", False))
        if require_subagent and max_subagents < 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    "격리 검증을 요청하려면 token_budget을 최소 "
                    f"{self.settings.deep_max_input_tokens * 4}로 늘리고 max_subagents를 1 이상으로 설정해주세요."
                ),
            )
        requested_parallelism = int(request.input_delta.get("max_parallelism") or 2)
        max_parallelism = max(1, min(requested_parallelism, max(1, max_subagents), 2 if pilot_mode else 4))
        self.store.put(
            "jobs",
            job_id,
            {
                "job_id": job_id,
                "employee_id": principal.employee_id,
                "principal_roles": list(principal.roles),
                "principal_teams": list(principal.teams),
                "capability_id": definition.capability_id,
                "goal": str(request.input_delta.get("_resolved_goal") or request.question),
                "context_id": context.context_id,
                "work_session_id": work_session_id,
                "status": "queued",
                "attempt": 0,
                "max_attempts": 2,
                "pilot_mode": pilot_mode,
                "max_tool_calls": max_tool_calls,
                "requested_max_subagents": requested_subagents,
                "subagent_budget_limit": subagent_budget_limit,
                "max_subagents": max_subagents,
                "max_parallelism": max_parallelism,
                "subagent_policy": (
                    "enabled"
                    if max_subagents
                    else "disabled_by_token_budget"
                    if requested_subagents
                    else "disabled_by_request"
                ),
                "require_subagent": require_subagent,
                "token_budget": token_budget,
                "independent_review_required": True,
                "timeout_seconds": max(30, min(int(request.input_delta.get("timeout_seconds") or 900), 3600)),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(30, min(int(request.input_delta.get("timeout_seconds") or 900), 3600)))).isoformat(),
                "created_at": now_iso(),
            },
        )
        return job_id

    def _next_actions(
        self,
        *,
        work_session_id: str,
        artifacts: list[ArtifactRef],
        evidence: list[EvidenceRef],
        plan_ref: str = "",
    ) -> list[NextAction]:
        actions: list[NextAction] = []
        artifact = artifacts[0] if artifacts else None
        if artifact and artifact.metadata.get("capability_id") == "work_routine.plan" and plan_ref:
            actions.append(
                NextAction(
                    action_id="confirm_automatic_check",
                    label="확인하고 자동 확인 만들기",
                    action_kind="confirm_plan",
                    artifact_id=artifact.artifact_id,
                    plan_id=plan_ref,
                )
            )
        elif artifact and artifact.metadata.get("capability_id") == "sop.plan":
            actions.extend(
                [
                    NextAction(
                        action_id="task_refine",
                        label="Task 다듬기",
                        action_kind="open_task_editor",
                        artifact_id=artifact.artifact_id,
                    ),
                    NextAction(
                        action_id="sop_full_edit",
                        label="전체 SOP 편집",
                        action_kind="open_full_editor",
                        artifact_id=artifact.artifact_id,
                        href=(
                            f"/sops/new?work_session_id={work_session_id}"
                            f"&artifact_id={artifact.artifact_id}"
                            f"&return_to=/agent?session={work_session_id}"
                        ),
                    ),
                ]
            )
        elif artifact and artifact.artifact_type == "mermaid_diagram":
            actions.append(
                NextAction(
                    action_id="open_diagram",
                    label="흐름 그림 보기",
                    action_kind="open_artifact",
                    artifact_id=artifact.artifact_id,
                    href=f"/agent?session={work_session_id}&artifact={artifact.artifact_id}",
                )
            )
        elif artifact:
            actions.append(
                NextAction(
                    action_id="open_artifact",
                    label="초안 확인",
                    action_kind="open_artifact",
                    artifact_id=artifact.artifact_id,
                    href=f"/agent?session={work_session_id}&artifact={artifact.artifact_id}",
                )
            )
        if evidence and not artifact:
            actions.append(
                NextAction(
                    action_id="save_note",
                    label="노트로 저장",
                    action_kind="save_note",
                )
            )
        if evidence:
            actions.append(
                NextAction(
                    action_id="show_sources",
                    label="사용한 지식",
                    action_kind="show_sources",
                )
            )
        return actions[:3]

    def _active_session_work_run(self, principal: Principal, session: dict[str, Any]) -> dict[str, Any] | None:
        work_run_id = str(session.get("active_work_run_id") or "")
        if not work_run_id:
            return None
        work_run = self.store.get("work_runs", work_run_id)
        if not work_run or not self._owns(principal, work_run):
            return None
        if str(work_run.get("status") or "") in {"completed", "failed", "cancelled", "stopped"}:
            return None
        return work_run

    def _active_work_run_for_planner(self, work_run: dict[str, Any] | None) -> dict[str, Any]:
        if not work_run:
            return {}
        intent = work_run.get("intent") if isinstance(work_run.get("intent"), dict) else {}
        context = self.store.get("contexts", str(work_run.get("context_id") or "")) or {}
        completion = context.get("completion_design") if isinstance(context.get("completion_design"), dict) else {}
        last_delta = (work_run.get("loop") or {}).get("deltas") or []
        return {
            "work_run_id": str(work_run.get("work_run_id") or ""),
            "status": str(work_run.get("status") or ""),
            "decision": str(work_run.get("decision") or ""),
            "task_mode": str(work_run.get("task_mode") or ""),
            "goal": compact_text(str(intent.get("goal") or ""), 500),
            "asset_kind": str(intent.get("asset_kind") or ""),
            "operation": str(intent.get("operation") or ""),
            "stop_reason": str(work_run.get("stop_reason") or ""),
            "task_ref": str(context.get("task_ref") or ""),
            "completion_items": [
                str(item.get("label") or "")
                for item in (completion.get("checks") or [])[:8]
                if isinstance(item, dict) and item.get("label")
            ],
            "required_evidence": [
                str(item.get("label") or "")
                for item in (completion.get("evidence") or [])[:8]
                if isinstance(item, dict) and item.get("label") and item.get("required", True)
            ],
            "last_progress": compact_text(str((last_delta[-1] if last_delta else {}).get("summary") or ""), 500),
        }

    @staticmethod
    def _guard_explanatory_capability(capability_id: str, intent: WorkIntent) -> str:
        read_operations = {WorkOperation.understand, WorkOperation.compare, WorkOperation.connect, WorkOperation.observe}
        draft_capabilities = {"business_event.plan", "sop.plan", "action.plan", "skill.plan", "knowledge.draft"}
        if intent.operation in read_operations and intent.result_purpose in {"explain", "compare"}:
            if intent.work_view == "current":
                return "work.inbox"
            if intent.work_view in {"responsibility", "combined"}:
                return "knowledge.search"
        if intent.result_purpose in {"explain", "compare"} and intent.operation in read_operations:
            if capability_id in {*draft_capabilities, "work_routine.plan"}:
                return "knowledge.search"
        return capability_id

    def _continue_active_work_from_turn(
        self,
        *,
        principal: Principal,
        request: AgentTurnRequest,
        session: dict[str, Any],
        active_work_run: dict[str, Any],
        route: dict[str, Any],
        run_id: str,
        turn_id: str,
    ) -> AgentTurnResponse:
        continuation = route.get("continuation") if isinstance(route.get("continuation"), dict) else {}
        delta_kind = str(continuation.get("delta_kind") or "human_input")
        if delta_kind not in {"human_input", "new_evidence", "blocker", "state_transition"}:
            delta_kind = "human_input"
        external_refs = [str(item).strip() for item in request.external_artifact_refs if str(item).strip()]
        delta_ref = external_refs[0] if external_refs else ""
        if not delta_ref and delta_kind in {"new_evidence", "state_transition"}:
            digest = hashlib.sha256(request.question.encode("utf-8")).hexdigest()[:16]
            delta_ref = f"human:{active_work_run['work_run_id']}:{digest}"
        user_confirmation = bool(continuation.get("user_confirmation", False)) and delta_kind == "human_input"
        continued, candidates = self.learning.continue_run(
            principal,
            str(active_work_run["work_run_id"]),
            WorkRunContinueRequest(
                expected_revision=int(active_work_run.get("revision") or 1),
                confirmation="confirm" if user_confirmation else None,
                delta=LoopDelta(
                    kind=delta_kind,  # type: ignore[arg-type]
                    summary=compact_text(request.question, 2000),
                    ref=delta_ref,
                    metadata={
                        "semantic_continuation": True,
                        "external_ai_summary_present": bool(request.external_ai_summary.strip()),
                        "external_artifact_ref_count": len(external_refs),
                    },
                ),
            ),
        )
        context_row = self.store.get("contexts", str(continued.get("context_id") or "")) or {}
        agent_run = self.store.get("runs", str(continued.get("agent_run_id") or "")) or {}
        capability_id = str(agent_run.get("capability_id") or context_row.get("capability_id") or "knowledge.search")
        view = self.learning.view_run(principal, str(continued["work_run_id"]))
        evidence = [
            EvidenceRef(
                evidence_id=str(item.get("evidence_id") or item.get("ledger_id") or ""),
                kind=str(item.get("kind") or "evidence"),
                title=str(item.get("title") or "확인 근거"),
                summary=str(item.get("summary") or ""),
                source=str(item.get("source") or "work_run"),
                authority=str(item.get("authority") or "runtime"),
            )
            for item in (view.get("evidence_ledger") or [])[-8:]
            if item.get("evidence_id") or item.get("ledger_id")
        ]
        artifacts: list[ArtifactRef] = []
        for artifact_id in list(continued.get("artifact_refs") or [])[:3]:
            row = self.store.get("artifacts", str(artifact_id)) or {}
            if not row or not self._owns(principal, row):
                continue
            artifact_status = str(row.get("status") or "draft")
            if artifact_status not in {"draft", "provisional", "reviewed"}:
                artifact_status = "draft"
            artifacts.append(
                ArtifactRef(
                    artifact_id=str(row.get("artifact_id") or artifact_id),
                    artifact_type=str(row.get("artifact_type") or row.get("capability_id") or "draft"),
                    title=str(row.get("title") or "작업 결과"),
                    status=artifact_status,  # type: ignore[arg-type]
                    url=f"/agent?session={session['session_id']}&artifact={artifact_id}",
                    metadata={
                        "capability_id": str(row.get("capability_id") or ""),
                        "revision": int(row.get("revision") or 1),
                    },
                )
            )
        status_value = str(continued.get("status") or "in_progress")
        messages = {
            "completed": "완료된 모습과 확인할 자료가 충족되어 업무를 완료했습니다.",
            "waiting_human": "담당자가 확인하거나 보완할 내용이 남아 있습니다.",
            "waiting_signal": "연결된 시스템의 확인 결과를 기다리고 있습니다.",
            "in_progress": "새로운 내용을 반영해 같은 업무를 이어갑니다.",
            "blocked": "업무를 이어가기 전에 보완할 항목이 있습니다.",
            "queued": "같은 업무에서 필요한 확인을 계속 진행하고 있습니다.",
        }
        message = messages.get(status_value, "업무 진행 상태를 갱신했습니다.")
        response_status = (
            "completed"
            if status_value == "completed"
            else "queued"
            if status_value in {"queued", "in_progress", "waiting_signal"}
            else "needs_input"
        )
        loop_state = {
            "iteration_count": int((continued.get("loop") or {}).get("iteration_count") or 0),
            "decision": str(continued.get("decision") or ""),
            "status": status_value,
            "revision": int(continued.get("revision") or 1),
        }
        page_anchor = self.learning.contexts.page_anchor(principal, request.page_ref)
        response = AgentTurnResponse(
            run_id=run_id,
            turn_id=turn_id,
            conversation_id=str(session.get("conversation_id") or session["session_id"]),
            work_session_id=str(session["session_id"]),
            status=response_status,  # type: ignore[arg-type]
            capability_id=capability_id,
            answer=AnswerBlock(summary=message, markdown=message),
            evidence_refs=evidence,
            artifact_refs=artifacts,
            next_actions=self._next_actions(
                work_session_id=str(session["session_id"]),
                artifacts=artifacts,
                evidence=evidence,
            ),
            context_ref=str(continued.get("context_id") or ""),
            goal_plan_ref=str(continued.get("goal_plan_id") or ""),
            source_set_ref=self._source_set_id(str(session["session_id"])),
            grounding_status="grounded" if evidence else "no_evidence",
            progress=[{"status": status_value, "label": message}],
            work_run_id=str(continued["work_run_id"]),
            work_intent=WorkIntent.model_validate(route.get("work_intent") or continued.get("intent") or {}),
            loop_state=loop_state,
            harness_results=[HarnessResult.model_validate(item) for item in continued.get("harness_results") or []],
            knowledge_candidates=candidates,
            context_usage={
                "semantic_continuation": True,
                "planner_source": str(route.get("source") or ""),
                "page_anchor": page_anchor.model_dump(mode="json") if page_anchor else None,
            },
        )
        self.store.put(
            "runs",
            run_id,
            {
                "run_id": run_id,
                "turn_id": turn_id,
                "employee_id": principal.employee_id,
                "work_session_id": session["session_id"],
                "work_run_id": continued["work_run_id"],
                "capability_id": capability_id,
                "status": response.status,
                "semantic_continuation": True,
                "created_at": now_iso(),
            },
        )
        self._finish_work_session(principal, session, response, request.question)
        return response

    def _finish_work_session(
        self,
        principal: Principal,
        session: dict[str, Any],
        response: AgentTurnResponse,
        question: str,
    ) -> None:
        session_id = str(session["session_id"])
        self._append_session_message(
            principal,
            session_id,
            role="user",
            display_text=question,
            run_id=response.run_id,
            capability_id=response.capability_id,
        )
        self._append_session_message(
            principal,
            session_id,
            role="assistant",
            display_text=response.answer.markdown,
            run_id=response.run_id,
            capability_id=response.capability_id,
            evidence_refs=response.evidence_refs,
            artifact_refs=response.artifact_refs,
            next_actions=response.next_actions,
            citations=response.citations,
            related_questions=response.related_questions,
            goal_plan_ref=response.goal_plan_ref,
            source_set_ref=response.source_set_ref,
            work_run_id=response.work_run_id,
            loop_state=response.loop_state,
            harness_results=response.harness_results,
            knowledge_candidates=response.knowledge_candidates,
        )
        if response.artifact_refs:
            session["active_artifact_id"] = response.artifact_refs[0].artifact_id
            session["title"] = compact_text(response.artifact_refs[0].title, 120) or session.get("title") or "새 업무"
        elif session.get("title") in {"", "새 업무"}:
            session["title"] = compact_text(question, 80) or "새 업무"
        session.update(
            {
                "last_run_id": response.run_id,
                "last_capability_id": response.capability_id,
                "active_work_run_id": response.work_run_id,
                "active_goal_plan_id": response.goal_plan_ref,
                "source_set_id": response.source_set_ref,
                "revision": int(session.get("revision") or 1) + 1,
                "updated_at": now_iso(),
                "expires_at": (
                    session.get("expires_at")
                    if session.get("pinned")
                    else (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                ),
            }
        )
        context = self._session_context(principal, session)
        session["conversation_summary"] = context["summary"]
        self.store.put("work_sessions", session_id, session)

    @staticmethod
    def _emit_turn_progress(
        sink: Callable[[str, dict[str, Any]], None] | None,
        stage: str,
        message: str,
        **payload: Any,
    ) -> None:
        if sink is None:
            return
        try:
            sink("progress", {"stage": stage, "message": message, **payload})
        except Exception:
            return

    def run_turn(
        self,
        principal: Principal,
        request: AgentTurnRequest,
        *,
        progress_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentTurnResponse:
        usage_id = new_id("usage")
        usage_token = begin_model_usage(usage_id, self.settings.run_token_budget)
        try:
            response = self._run_turn(principal, request, progress_sink=progress_sink)
        except Exception:
            usage = finish_model_usage(usage_token)
            self.store.put(
                "usage_ledgers",
                usage_id,
                {
                    "usage_id": usage_id,
                    "employee_id": principal.employee_id,
                    "status": "failed",
                    **usage,
                    "created_at": now_iso(),
                },
            )
            raise
        usage = finish_model_usage(usage_token)
        if usage.get("token_budget") and int(usage.get("total_tokens") or usage.get("total_tokens_estimate") or 0) > int(usage["token_budget"]):
            self.store.put(
                "usage_ledgers",
                usage_id,
                {
                    "usage_id": usage_id,
                    "employee_id": principal.employee_id,
                    "run_id": response.run_id,
                    "work_run_id": response.work_run_id,
                    "capability_id": response.capability_id,
                    "status": "budget_exceeded",
                    **usage,
                    "created_at": now_iso(),
                },
            )
            raise RuntimeError("model token budget exceeded after provider usage accounting")
        usage_row = self.store.put(
            "usage_ledgers",
            usage_id,
            {
                "usage_id": usage_id,
                "employee_id": principal.employee_id,
                "run_id": response.run_id,
                "work_run_id": response.work_run_id,
                "capability_id": response.capability_id,
                "status": response.status,
                **usage,
                "created_at": now_iso(),
            },
        )
        model_usage = {
            "usage_ref": usage_id,
            "accounting": usage_row.get("accounting") or "estimated",
            "total_tokens": usage_row.get("total_tokens") or usage_row.get("total_tokens_estimate") or 0,
            "total_tokens_estimate": usage_row.get("total_tokens_estimate") or 0,
            "token_budget": usage_row.get("token_budget") or self.settings.run_token_budget,
            "remaining_tokens_estimate": usage_row.get("remaining_tokens_estimate") or 0,
            "model_calls": usage_row.get("model_calls") or 0,
            "embedding_calls": usage_row.get("embedding_calls") or 0,
        }
        response.context_usage["model_usage"] = model_usage
        response = self._enforce_response_budget(response)
        stored_run = self.store.get("runs", response.run_id)
        if stored_run:
            stored_run["usage_ref"] = usage_id
            stored_run["usage"] = model_usage
            stored_run["response"] = response.model_dump(mode="json")
            self.store.put("runs", response.run_id, stored_run)
        if response.work_run_id:
            work_run = self.store.get("work_runs", response.work_run_id)
            if work_run:
                work_run["usage_refs"] = list(dict.fromkeys([*work_run.get("usage_refs", []), usage_id]))[-20:]
                work_run["usage"] = model_usage
                self.store.put("work_runs", response.work_run_id, work_run)
        return response

    def _run_turn(
        self,
        principal: Principal,
        request: AgentTurnRequest,
        *,
        progress_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentTurnResponse:
        run_id = new_id("run")
        turn_id = new_id("turn")
        self._apply_starter_suggestion(principal, request)
        session = self._resolve_turn_session(principal, request)
        self._emit_turn_progress(
            progress_sink,
            "context",
            "현재 화면과 이어진 업무 맥락을 확인하고 있습니다.",
            work_session_id=str(session["session_id"]),
        )
        offer_capability = ""
        if request.offer_id:
            offer = self._load_offer(principal, request.offer_id)
            offer_capability = str(offer.get("capability_id") or "")
            if request.capability_id and request.capability_id != offer_capability:
                raise HTTPException(status_code=409, detail="offer capability does not match request")
        active_session_artifact = self.store.get("artifacts", str(session.get("active_artifact_id") or "")) or {}
        active_capability = (
            str(active_session_artifact.get("capability_id") or "")
            if active_session_artifact and self._owns(principal, active_session_artifact)
            else ""
        )
        active_work_run = self._active_session_work_run(principal, session)
        page_anchor_for_route = self.learning.contexts.page_anchor(principal, request.page_ref)
        planner_search = None
        self._emit_turn_progress(
            progress_sink,
            "retrieval",
            "Wiki 전체에서 관련 지식과 업무 이력을 찾고 있습니다.",
        )
        try:
            planner_search = self.search.search(
                request.question,
                principal,
                limit=12,
                include_history=False,
                page_ref=request.page_ref,
                task_ref=request.task_ref,
            )
            planner_hints = [
                {
                    "ref": item.evidence_id,
                    "title": item.title,
                    "kind": item.kind,
                    "summary": compact_text(item.summary, 180),
                    "authority": item.authority,
                    "source": item.source,
                }
                for item in planner_search.items[:6]
            ]
        except Exception:
            planner_hints = []
        try:
            route_input = {
                "question": request.question,
                "page_kind": self.page_kind(request.page_ref),
                "page_ref": request.page_ref,
                "page_title": (
                    page_anchor_for_route.title
                    if page_anchor_for_route and page_anchor_for_route.resolved
                    else ""
                ),
                "explicit_capability": request.capability_id or "",
                "offered_capability": offer_capability,
                "active_capability": active_capability,
                "active_artifact_title": str(active_session_artifact.get("title") or ""),
                "active_work_run": self._active_work_run_for_planner(active_work_run),
                "task_ref": request.task_ref,
                "conversation_summary": str(session.get("conversation_summary") or ""),
                "conversation_context": (
                    request.input_delta.get("_work_session_context")
                    if isinstance(request.input_delta.get("_work_session_context"), dict)
                    else {}
                ),
                "knowledge_hints": planner_hints,
                "trusted_targets": {
                    "action_key": str(request.input_delta.get("action_key") or "").strip(),
                },
                "requested_operation": str(request.input_delta.get("operation") or ""),
                "requested_result_kind": str(request.input_delta.get("_starter_result_kind") or ""),
                "requested_graph_query_kind": str(request.input_delta.get("_starter_graph_query_kind") or ""),
            }
            route = self._semantic_route(principal, route_input)
            capability_id = str(route["capability_id"])
            definition = self.registry.get(capability_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if request.helper_id:
            helper = self.get_helper(principal, request.helper_id)
            allowed = list(helper.get("capability_ids") or ["knowledge.search"])
            if capability_id not in allowed:
                fallback = "knowledge.search" if "knowledge.search" in allowed else allowed[0]
                capability_id = fallback
                definition = self.registry.get(capability_id)
                route = {**route, "capability_id": capability_id, "source": "helper_allowlist"}
            request.input_delta.setdefault("_helper_instructions", str(helper.get("instructions") or ""))
            request.input_delta.setdefault("_helper_source_scopes", helper.get("source_scopes") or [])
            request.input_delta.setdefault("_helper_skill_ids", helper.get("skill_ids") or [])
            helper_skills, missing_skills = self._skill_contracts(
                principal,
                list(helper.get("skill_ids") or []),
                require_active=helper.get("status") == "active",
            )
            if missing_skills:
                raise HTTPException(status_code=422, detail={"status": "skill_unavailable", "skill_ids": missing_skills})
            request.input_delta.setdefault("_helper_skills", helper_skills)
        continuation = route.get("continuation") if isinstance(route.get("continuation"), dict) else {}
        self._emit_turn_progress(
            progress_sink,
            "judgment",
            "요청 의도와 확인할 근거를 함께 판단하고 있습니다.",
            capability_id=capability_id,
        )
        if (
            active_work_run
            and route.get("source") == "llm_structured"
            and bool(continuation.get("continue_active_run"))
            and float((route.get("work_intent") or {}).get("confidence") or 0.0) >= 0.75
        ):
            return self._continue_active_work_from_turn(
                principal=principal,
                request=request,
                session=session,
                active_work_run=active_work_run,
                route=route,
                run_id=run_id,
                turn_id=turn_id,
            )
        source_set = self._ensure_source_set(principal, str(session["session_id"]))
        preliminary_intent = WorkIntent.model_validate(route.get("work_intent") or {})
        guarded_capability = self._guard_explanatory_capability(capability_id, preliminary_intent)
        if guarded_capability != capability_id:
            capability_id = guarded_capability
            definition = self.registry.get(capability_id)
            route = {
                **route,
                "capability_id": capability_id,
                "source": f"{route.get('source') or 'semantic'}:explanatory_guard",
            }
        starter_refs = [str(item) for item in request.input_delta.get("_starter_source_refs") or [] if str(item)]
        if starter_refs:
            result_kind = str(request.input_delta.get("_starter_result_kind") or "")
            graph_query_kind = str(request.input_delta.get("_starter_graph_query_kind") or "")
            presentation = {
                "table": "table",
                "timeline": "timeline",
                "mermaid": "mermaid",
                "explorer": "explorer",
            }.get(result_kind, preliminary_intent.presentation_mode)
            graph_draft = preliminary_intent.graph_query_draft
            if graph_query_kind:
                graph_draft = GraphQueryDraft(
                    enabled=True,
                    query_kind=graph_query_kind,  # type: ignore[arg-type]
                    focal_mentions=(
                        ["현재 사용자"]
                        if graph_query_kind == "responsibility"
                        else [str(request.input_delta.get("_starter_subject_ref") or starter_refs[0])]
                    ),
                    presentation=presentation if presentation in {"auto", "list", "table", "timeline", "mermaid", "explorer"} else "auto",  # type: ignore[arg-type]
                )
            preliminary_intent = preliminary_intent.model_copy(
                update={
                    "context_refs": list(dict.fromkeys([*starter_refs, *preliminary_intent.context_refs]))[:20],
                    "target_ref": str(request.input_delta.get("_starter_subject_ref") or preliminary_intent.target_ref),
                    "presentation_mode": presentation,
                    "graph_query_draft": graph_draft,
                    "work_view": "combined" if graph_query_kind == "responsibility" else preliminary_intent.work_view,
                }
            )
        resolved_goal = compact_text(preliminary_intent.resolved_goal or request.question, 12000)
        retrieval_goal = compact_text(preliminary_intent.retrieval_query or resolved_goal, 12000)
        retrieval_subjects: list[str] = []
        for context_ref in preliminary_intent.context_refs[:4]:
            record = self._record_for_ref(principal, context_ref)
            title = compact_text(str(getattr(record, "title", "") or ""), 240) if record else ""
            if title and title.casefold() not in retrieval_goal.casefold():
                retrieval_subjects.append(title)
        if retrieval_subjects:
            retrieval_goal = compact_text(
                f"{retrieval_goal}\n확인할 대상: {', '.join(dict.fromkeys(retrieval_subjects))}",
                12000,
            )
        preliminary_intent = preliminary_intent.model_copy(
            update={"resolved_goal": resolved_goal, "retrieval_query": retrieval_goal}
        )
        request.input_delta["_resolved_goal"] = resolved_goal
        request.input_delta["_retrieval_query"] = retrieval_goal
        goal_plan = self._create_goal_plan(
            principal,
            session,
            resolved_goal,
            definition,
            route,
            preliminary_intent,
        )
        active_session_task = self._active_session_task(principal, session)
        active_mode = str(active_session_task.get("execution_mode") or active_session_task.get("mode") or "").lower()
        task_mode = (
            TaskMode(active_mode)
            if active_mode in {item.value for item in TaskMode}
            else self.policy.resolve_mode(principal, request.task_ref)
        )
        dependencies = self.readiness(principal)["dependencies"]
        supplied = {"query": resolved_goal, "goal": resolved_goal, **request.input_delta}
        state, missing, reason = self.registry.state_for(
            definition,
            principal=principal,
            readiness=dependencies,
            task_mode=task_mode,
            supplied_input=supplied,
        )
        if state == CapabilityState.unavailable:
            raise HTTPException(
                status_code=503 if any(not dependencies.get(name, False) for name in definition.readiness) else 403,
                detail={"status": "capability_unavailable", "capability_id": capability_id, "message": reason},
            )
        if state == CapabilityState.needs_input:
            response = self._needs_input_response(
                capability_id,
                missing,
                reason,
                work_session_id=str(session["session_id"]),
            )
            response.goal_plan_ref = str(goal_plan["goal_plan_id"])
            response.source_set_ref = str(source_set["source_set_id"])
            self._finish_work_session(principal, session, response, request.question)
            return response
        decision = self.policy.evaluate(definition, principal=principal, task_ref=request.task_ref)
        self.policy.enforce(decision)

        retrieval_query = retrieval_goal
        session_context = request.input_delta.get("_work_session_context")
        active_artifact = session_context.get("active_artifact") if isinstance(session_context, dict) else {}
        active_artifact_id_for_context = str(active_artifact.get("artifact_id") or "") if isinstance(active_artifact, dict) else ""
        if (
            isinstance(active_artifact, dict)
            and active_artifact.get("title")
            and (
                preliminary_intent.target_ref == active_artifact_id_for_context
                or preliminary_intent.scope == "current"
                or preliminary_intent.operation
                in {WorkOperation.refine, WorkOperation.validate, WorkOperation.test}
            )
        ):
            task_names = " ".join(
                str(item.get("name") or "")
                for item in (active_artifact.get("tasks") or [])[:8]
                if isinstance(item, dict)
            )
            retrieval_query = f"{resolved_goal}\n활성 결과: {active_artifact.get('title')} {task_names}".strip()
        include_history = capability_id == "cases.similar" or bool(request.input_delta.get("include_history", False))
        if capability_id == "work.inbox":
            work = self.repository.current_work(principal)
            evidence = [
                EvidenceRef(
                    evidence_id=item.record_id,
                    kind="task",
                    title=item.title,
                    summary=item.description,
                    url=item.url,
                    source="runtime",
                    authority="runtime",
                    metadata={"status": item.status},
                )
                for item in work
            ]
            current_work_evidence = list(evidence)
        else:
            if planner_search is not None and retrieval_query == request.question and not include_history:
                search_result = planner_search
            else:
                search_result = self.search.search(
                    retrieval_query,
                    principal,
                    limit=12,
                    include_history=include_history,
                    page_ref=request.page_ref,
                    task_ref=request.task_ref,
                    kinds={"case"} if capability_id == "cases.similar" else None,
                )
            evidence = search_result.items
            current_work_evidence = []
        if preliminary_intent.work_view == "combined" and not current_work_evidence:
            current_work_evidence = [
                EvidenceRef(
                    evidence_id=item.record_id,
                    kind="task",
                    title=item.title,
                    summary=item.description,
                    url=item.url,
                    source="runtime",
                    authority="runtime",
                    metadata={"status": item.status},
                )
                for item in self.repository.current_work(principal)
            ]
        if capability_id != "work.inbox":
            evidence = self._apply_source_set(
                principal,
                str(session["session_id"]),
                evidence,
                page_ref=request.page_ref,
                context_refs=preliminary_intent.context_refs,
            )
        if preliminary_intent.work_view == "combined":
            evidence = list(
                {
                    item.evidence_id: item
                    for item in [*evidence, *current_work_evidence]
                }.values()
            )[:24]
        citations = self._citations_for_evidence(
            principal,
            str(session["session_id"]),
            retrieval_query,
            evidence,
        )
        context = self._context(
            principal,
            definition,
            request,
            evidence,
            task_mode,
            session=session,
            source_set=source_set,
            resolved_goal=resolved_goal,
            task_override=active_session_task,
        )
        context.business_context["user_work_profile"] = self.user_work_profile(principal)
        self.store.put("contexts", context.context_id, context.model_dump(mode="json"))
        resolved_target = (
            request.task_ref
            or (context.goal_anchor.ref if context.goal_anchor and context.goal_anchor.resolved else "")
            or (context.page_anchor.ref if context.page_anchor and context.page_anchor.resolved else "")
            or preliminary_intent.target_ref
        )
        intent = preliminary_intent.model_copy(update={"target_ref": resolved_target})
        requested_action_key = str(request.input_delta.get("action_key") or "").strip()
        if requested_action_key:
            context.business_context["action_key"] = requested_action_key
            if intent.asset_kind.value == "action":
                intent.target_ref = f"action:{requested_action_key}"
            self.store.put("contexts", context.context_id, context.model_dump(mode="json"))
        work_run = self.learning.create_run(
            principal=principal,
            agent_run_id=run_id,
            session=session,
            context=context,
            intent=intent,
            goal_plan_id=str(goal_plan["goal_plan_id"]),
            loop_policy=(
                request.loop_policy
                or request.input_delta.get("_loop_policy")
                or request.input_delta.get("loop_policy")
            ),
        )
        artifacts: list[ArtifactRef] = []
        generated_related_questions: list[RelatedQuestion] = []
        plan_ref = ""
        job_ref = ""
        status: str = "completed"
        active_artifact_row = None
        active_artifact_id = str(session.get("active_artifact_id") or "")
        if active_artifact_id:
            candidate_artifact = self.store.get("artifacts", active_artifact_id)
            if candidate_artifact and self._owns(principal, candidate_artifact):
                active_artifact_row = candidate_artifact
        graph_clarification = ""
        graph_result_bundle = None
        try:
            graph_result_bundle = (
                self._graph_result_artifact(
                    principal,
                    session=session,
                    intent=intent,
                    current_work=current_work_evidence,
                    work_run_id=str(work_run["work_run_id"]),
                )
                if intent.graph_query_draft and intent.graph_query_draft.enabled
                else None
            )
        except AmbiguousEntityError as exc:
            candidate_labels = ", ".join(item.label for item in exc.candidates[:5])
            graph_clarification = f"'{exc.mention}'에 해당하는 대상이 여러 개입니다: {candidate_labels}. 어느 대상을 볼까요?"
            intent = intent.model_copy(update={"needs_clarification": True})
            work_run["intent"] = intent.model_dump(mode="json")
            work_run["status"] = "waiting_input"
            self.store.put("work_runs", str(work_run["work_run_id"]), work_run)

        if graph_clarification:
            status = "needs_input"
            citations = []
            answer = AnswerBlock(
                summary="확인할 대상이 여러 개입니다.",
                markdown=graph_clarification,
            )
        elif work_run.get("status") == "blocked":
            status = "needs_input"
            citations = []
            answer = AnswerBlock(
                summary="현재 업무 맥락을 먼저 확인해야 합니다.",
                markdown=(
                    "현재 화면이나 대상 업무를 안전하게 확인하지 못했습니다. "
                    "대상 문서나 Task를 지정하면 Wiki 전체의 관련 지식과 함께 다시 확인하겠습니다."
                ),
            )
        elif (
            active_artifact_row
            and active_artifact_row.get("artifact_type") == "mermaid_diagram"
            and intent.result_purpose == "transform"
            and "split_tasks" in intent.artifact_actions
            and "create_sop_draft" not in intent.artifact_actions
        ):
            try:
                answer, workflow_artifact = self._split_mermaid_artifact_into_tasks(
                    principal,
                    source_artifact=active_artifact_row,
                    session=session,
                    work_run_id=str(work_run["work_run_id"]),
                    page_ref=request.page_ref,
                )
                artifacts.append(workflow_artifact)
            except RuntimeError:
                status = "needs_input"
                answer = AnswerBlock(
                    summary="흐름을 Task로 나누지 못했습니다.",
                    markdown=(
                        "현재 흐름에서 확인 가능한 Task 후보를 만들지 못했습니다. "
                        "Task로 나눌 흐름 그림을 다시 선택하거나 필요한 단계를 조금 더 설명해주세요."
                    ),
                )
        elif active_artifact_row and intent.operation in {WorkOperation.validate, WorkOperation.test}:
            domain_test: dict[str, Any] = {}
            artifact_domain = (
                active_artifact_row.get("domain")
                if isinstance(active_artifact_row.get("domain"), dict)
                else {}
            )
            if (
                intent.operation == WorkOperation.test
                and artifact_domain.get("domain_kind") == "business_event_definition"
                and artifact_domain.get("domain_ref")
                and self.domain_services.supports("business_event.draft.test")
            ):
                domain_test = self.domain_services.execute(
                    "business_event.draft.test",
                    principal,
                    {
                        "domain_ref": str(artifact_domain.get("domain_ref") or ""),
                        "sample_signal": (
                            request.input_delta.get("sample_signal")
                            if isinstance(request.input_delta.get("sample_signal"), dict)
                            else (active_artifact_row.get("draft") or {}).get("sample_signal") or {}
                        ),
                        "artifact_id": str(active_artifact_row.get("artifact_id") or ""),
                        "work_session_id": str(session.get("session_id") or ""),
                    },
                )
                active_artifact_row["domain_test"] = domain_test
                active_artifact_row["updated_at"] = now_iso()
                self.store.put("artifacts", str(active_artifact_row["artifact_id"]), active_artifact_row)
            try:
                artifact_type = str(
                    self.registry.get(str(active_artifact_row.get("capability_id") or "knowledge.search")).output_schema.get("type")
                    or "draft"
                )
            except KeyError:
                artifact_type = "knowledge_draft"
            preview_results = [
                self.harnesses.evaluate(
                    harness_id,
                    phase="test" if intent.operation == WorkOperation.test else "validate",
                    intent=intent,
                    context=context,
                    artifact=active_artifact_row,
                    task_mode=context.task_mode,
                )
                for harness_id in self.harnesses.harnesses_for(intent, artifact_type)
                if harness_id != "context.work"
            ]
            blockers = [message for item in preview_results for message in item.blockers]
            artifacts.append(
                ArtifactRef(
                    artifact_id=str(active_artifact_row["artifact_id"]),
                    artifact_type=artifact_type,
                    title=str(active_artifact_row.get("title") or "작업 초안"),
                    status=str(active_artifact_row.get("status") or "draft"),  # type: ignore[arg-type]
                    url=f"/agent?session={session['session_id']}&artifact={active_artifact_row['artifact_id']}",
                    metadata={
                        "capability_id": active_artifact_row.get("capability_id") or "",
                        "revision": active_artifact_row.get("revision") or 1,
                        "domain_test": domain_test,
                    },
                )
            )
            if blockers:
                status = "needs_input"
                answer = AnswerBlock(
                    summary=f"보완할 항목이 {len(blockers)}개 있습니다.",
                    markdown="### 보완 필요\n\n" + "\n".join(f"- {item}" for item in blockers[:8]),
                )
            else:
                if domain_test:
                    decision = domain_test.get("decision") if isinstance(domain_test.get("decision"), dict) else {}
                    answer = AnswerBlock(
                        summary=str(domain_test.get("message") or "샘플 판단을 완료했습니다."),
                        markdown=(
                            "### 샘플 판단 결과\n\n"
                            f"- 결과: {decision.get('decision') or '확인 필요'}\n"
                            f"- 이유: {decision.get('reason') or domain_test.get('message') or '-'}\n\n"
                            "실제 업무 이벤트를 발행하지 않았고 판단 상태도 변경하지 않았습니다."
                        ),
                    )
                else:
                    answer = AnswerBlock(
                        summary="현재 초안이 업무 품질 기준을 통과했습니다.",
                        markdown="현재 초안의 업무 맥락, 완료 항목, 근거와 실행 안전 기준을 확인했습니다.",
                    )
        elif (
            active_artifact_row
            and active_artifact_row.get("capability_id") == "sop.plan"
            and intent.operation == WorkOperation.refine
        ):
            draft = active_artifact_row.get("draft") if isinstance(active_artifact_row.get("draft"), dict) else {}
            tasks = [item for item in draft.get("tasks") or [] if isinstance(item, dict)]
            selected_task_id = str(session.get("selected_task_id") or "")
            task = next((item for item in tasks if item.get("task_id") == selected_task_id), None) or (tasks[0] if tasks else None)
            if not task:
                status = "needs_input"
                answer = AnswerBlock(
                    summary="다듬을 Task가 필요합니다.",
                    markdown="SOP에 Task를 추가하거나 다듬을 Task를 선택해주세요.",
                )
            else:
                if context.task_mode == TaskMode.manual:
                    status = "needs_input"
                    answer = AnswerBlock(
                        summary="이 Task는 사람이 직접 다듬는 방식입니다.",
                        markdown="현재 내용을 직접 편집하거나, AI 변경 제안이 필요하면 수행 방식을 Copilot으로 바꿔주세요.",
                    )
                else:
                    proposal = self.refine_task_preview(
                        principal,
                        str(active_artifact_row["artifact_id"]),
                        str(task["task_id"]),
                        TaskRefinePreviewRequest(
                            expected_revision=int(active_artifact_row.get("revision") or 1),
                            instruction=request.question,
                        ),
                    )
                    artifacts.append(
                        ArtifactRef(
                            artifact_id=str(active_artifact_row["artifact_id"]),
                            artifact_type="sop_draft",
                            title=str(active_artifact_row.get("title") or "SOP 초안"),
                            status="draft",
                            url=f"/agent?session={session['session_id']}&artifact={active_artifact_row['artifact_id']}",
                            metadata={
                                "capability_id": "sop.plan",
                                "revision": active_artifact_row.get("revision") or 1,
                                "proposal_id": proposal["proposal_id"],
                                "task_id": task["task_id"],
                            },
                        )
                    )
                    answer = AnswerBlock(
                        summary=f"'{task.get('name') or 'Task'}'의 변경 제안을 준비했습니다.",
                        markdown="기존 업무 목적은 유지했습니다. 변경 전·후를 확인하고 적용할 내용만 선택하세요.",
                    )
        elif intent.operation in {WorkOperation.run, WorkOperation.promote}:
            target_ref = intent.target_ref or active_artifact_id or (context.page_anchor.ref if context.page_anchor else "")
            action_key = str(
                request.input_delta.get("action_key")
                or context.business_context.get("action_key")
                or (target_ref.removeprefix("action:") if target_ref.startswith("action:") else "")
            ).strip()
            domain_operation = ""
            domain_payload: dict[str, Any] = {}
            if intent.operation == WorkOperation.run and action_key:
                domain_operation = "action.invoke"
                domain_payload = {
                    "action_key": action_key,
                    "payload": request.input_delta.get("payload")
                    if isinstance(request.input_delta.get("payload"), dict)
                    else {},
                    "event": request.input_delta.get("event")
                    if isinstance(request.input_delta.get("event"), dict)
                    else {},
                    "boi_id": str(request.input_delta.get("boi_id") or ""),
                    "dry_run": bool(request.input_delta.get("dry_run", True)),
                    "idempotency_key": str(request.input_delta.get("idempotency_key") or new_id("agent-plan")),
                }
            if intent.operation == WorkOperation.run and not domain_operation:
                status = "needs_input"
                answer = AnswerBlock(
                    summary="실행할 Action을 먼저 확인해야 합니다.",
                    markdown="Action 이름이나 연결된 Task를 지정하면 입력값과 예상 결과를 확인하는 실행 계획을 만들겠습니다.",
                )
            else:
                plan_ref = new_id("plan")
                self.store.put(
                    "plans",
                    plan_ref,
                    {
                        "plan_id": plan_ref,
                        "employee_id": principal.employee_id,
                        "capability_id": capability_id,
                        "operation": intent.operation.value,
                        "target_ref": target_ref,
                        "status": "draft",
                        "risk": intent.risk.value,
                        "production_changed": False,
                        "work_run_id": work_run["work_run_id"],
                        "domain_operation": domain_operation,
                        "domain_payload": domain_payload,
                        "created_at": now_iso(),
                    },
                )
                answer = AnswerBlock(
                    summary="실행 전에 확인할 계획을 준비했습니다.",
                    markdown="대상, 입력값, 예상 결과와 위험도를 확인한 뒤 승인해야 기존 업무 API의 실행 단계로 이어집니다. 아직 실행하거나 게시하지 않았습니다.",
                )
        elif graph_result_bundle is not None:
            answer, graph_artifact, graph_evidence = graph_result_bundle
            artifacts.append(graph_artifact)
            evidence = graph_evidence or evidence
            citations = self._citations_for_evidence(
                principal,
                str(session["session_id"]),
                resolved_goal,
                graph_evidence,
            )
            if citations:
                markers = " ".join(
                    f"[{index}](/api/v2/citations/{item.citation_id})"
                    for index, item in enumerate(citations[:4], start=1)
                )
                answer.markdown = f"{answer.markdown}\n\n관계 근거 {markers}"
        elif intent.presentation_mode == "mermaid" and capability_id in {"knowledge.search", "cases.similar"}:
            try:
                answer, diagram_artifact, generated_related_questions = self._mermaid_artifact(
                    principal,
                    request=request,
                    session=session,
                    intent=intent,
                    evidence=evidence,
                    citations=citations,
                    work_run_id=str(work_run["work_run_id"]),
                )
                artifacts.append(diagram_artifact)
            except RuntimeError as exc:
                status = "needs_input"
                work_run["diagnostics"] = [
                    *[item for item in work_run.get("diagnostics") or [] if isinstance(item, dict)],
                    {
                        "kind": "mermaid_validation",
                        "detail": compact_text(str(exc), 1000),
                        "created_at": now_iso(),
                    },
                ][-10:]
                self.store.put("work_runs", str(work_run["work_run_id"]), work_run)
                answer = AnswerBlock(
                    summary="흐름 그림을 만들지 못했습니다.",
                    markdown=(
                        "### 흐름 그림 생성 실패\n\n"
                        "질문의 대상과 직접 연결된 근거만으로는 검증 가능한 흐름 그림을 구성하지 못했습니다. "
                        "확인할 대상이나 관계를 조금 더 구체적으로 지정하면 다시 만들 수 있습니다."
                    ),
                )
        elif capability_id == "work_routine.plan":
            try:
                answer, routine_artifact, plan_ref = self._work_routine_plan(
                    principal,
                    request=request,
                    session=session,
                    intent=intent,
                    evidence=evidence,
                    work_run_id=str(work_run["work_run_id"]),
                )
                artifacts.append(routine_artifact)
            except RuntimeError as exc:
                status = "needs_input"
                answer = AnswerBlock(
                    summary="자동 확인 계획을 만들려면 정보가 더 필요합니다.",
                    markdown=f"{compact_text(str(exc), 500)} 시간이나 상태 조건을 조금 더 구체적으로 알려주세요.",
                )
        elif capability_id == "task.work":
            completion_checks = [item.label for item in (context.completion_design.checks if context.completion_design else [])]
            completion_evidence = [item.label for item in (context.completion_design.evidence if context.completion_design else []) if item.required]
            completion_checks = completion_checks or list(context.exit_criteria)
            completion_evidence = completion_evidence or list(context.required_evidence)
            task_title = (
                context.goal_anchor.title
                if context.goal_anchor and context.goal_anchor.title not in {"", "진행 중 Task"}
                else request.task_ref or "현재 Task"
            )
            if intent.operation == WorkOperation.complete:
                status = "needs_input"
                lines = [
                    f"'{task_title}'의 완료 여부는 담당자 또는 연결된 시스템의 확인이 있어야 확정됩니다.",
                    "",
                    "### 완료된 모습",
                    *([f"- {item}" for item in completion_checks] or ["- 이 Task의 완료된 모습을 먼저 정해주세요."]),
                    "",
                    "### 확인할 자료",
                    *([f"- {item}" for item in completion_evidence] or ["- 확인할 자료를 먼저 정해주세요."]),
                    "",
                    (
                        "직접 확인한 내용과 판단 기록을 남기면 같은 업무에서 완료 여부를 다시 평가합니다."
                        if context.task_mode in {TaskMode.manual, TaskMode.copilot}
                        else "연결된 Event·Action·데이터 결과가 확인될 때만 자동 완료됩니다."
                    ),
                ]
                answer = AnswerBlock(
                    summary=f"'{task_title}'의 완료 확인을 기다리고 있습니다.",
                    markdown="\n".join(lines),
                )
            else:
                answer = AnswerBlock(
                    summary=f"'{task_title}'의 현재 업무 맥락과 확인 항목을 정리했습니다.",
                    markdown="\n".join(
                        [
                            f"### {task_title}",
                            f"- 수행 방식: {context.task_mode.value}",
                            *[f"- 완료된 모습: {item}" for item in completion_checks],
                            *[f"- 확인할 자료: {item}" for item in completion_evidence],
                        ]
                    ),
                )
        elif capability_id == "knowledge.search":
            helper_guidance = "\n".join(
                [
                    str(request.input_delta.get("_helper_instructions") or ""),
                    *[
                        f"{item.get('title')}: {item.get('description')}"
                        for item in request.input_delta.get("_helper_skills") or []
                        if isinstance(item, dict)
                    ],
                ]
            ).strip()
            answer, generated_related_questions = self._grounded_search_answer(
                principal,
                session,
                resolved_goal,
                evidence,
                citations,
                guidance=helper_guidance,
                desired_outcome=intent.desired_outcome,
                primary_source_ref=(
                    context.page_anchor.ref
                    if context.page_anchor and context.page_anchor.resolved
                    else ""
                ),
            )
            if route.get("source") == "safe_fallback":
                status = "needs_input"
                protected_local_models = (
                    self.settings.lmstudio_require_preloaded_models
                    and self.model_residency.get("ready") is not True
                )
                answer = AnswerBlock(
                    summary=(
                        "로컬 AI 모델의 교대 재로딩을 막고 관련 지식만 확인했습니다."
                        if protected_local_models
                        else "요청의 업무 동작을 안전하게 판단하지 못해 관련 지식만 확인했습니다."
                    ),
                    markdown=(
                        (
                            "LM Studio에서 필요한 생성·임베딩 모델의 수동 상주 상태를 확인하지 못해 "
                            "교대 로딩을 막기 위해 AI 답변 생성을 중단했습니다. 두 모델을 TTL 없이 "
                            "직접 로드한 뒤 다시 시도해주세요.\n\n"
                            if protected_local_models
                            else "의도 판단 모델이 준비되지 않았거나 구조화된 판단을 검증하지 못했습니다. "
                            "초안 생성이나 실행은 추측하지 않았습니다.\n\n"
                        )
                        + answer.markdown
                    ),
                )
        elif capability_id == "cases.similar":
            answer, generated_related_questions = self._grounded_search_answer(
                principal,
                session,
                resolved_goal,
                evidence,
                citations,
                empty_label="유사 사례",
                desired_outcome=intent.desired_outcome,
                guidance="\n".join(
                    [
                        str(request.input_delta.get("_helper_instructions") or ""),
                        *[
                            f"{item.get('title')}: {item.get('description')}"
                            for item in request.input_delta.get("_helper_skills") or []
                            if isinstance(item, dict)
                        ],
                    ]
                ).strip(),
                primary_source_ref=(
                    context.page_anchor.ref
                    if context.page_anchor and context.page_anchor.resolved
                    else ""
                ),
            )
        elif capability_id == "work.inbox":
            answer = self._inbox_answer(current_work_evidence)
        elif definition.deep:
            job_ref = self._queue_deep_job(
                principal,
                definition,
                request,
                context,
                work_session_id=str(session["session_id"]),
            )
            status = "queued"
            answer = AnswerBlock(
                summary="심층 작업을 시작했습니다. 결과는 검토 가능한 draft로만 생성됩니다.",
                markdown=f"심층 작업 `{job_ref}`을 시작했습니다. 작업공간에서 진행 상태와 근거를 확인할 수 있습니다.",
            )
        elif definition.operation == OperationClass.draft:
            try:
                answer, artifact, plan_ref = self._draft(
                    principal,
                    definition,
                    request,
                    evidence,
                    work_run_id=str(work_run["work_run_id"]),
                )
                artifacts.append(artifact)
            except Exception as exc:
                self.learning.fail_run(
                    principal,
                    str(work_run["work_run_id"]),
                    f"{definition.title} 작업 실패: {type(exc).__name__}",
                )
                failure = {
                    "status": "draft_generation_failed",
                    "capability_id": capability_id,
                    "message": f"{type(exc).__name__}: {exc}",
                    "run_id": run_id,
                }
                self.store.put(
                    "runs",
                    run_id,
                    {
                        "run_id": run_id,
                        "employee_id": principal.employee_id,
                        "conversation_id": str(session["conversation_id"]),
                        "work_session_id": str(session["session_id"]),
                        "capability_id": capability_id,
                        "status": "failed",
                        "context_id": context.context_id,
                        "routing": route,
                        "events": [
                            {"event": "accepted", "run_id": run_id},
                            {"event": "capability.selected", "capability_id": capability_id},
                            {"event": "error", **failure},
                        ],
                        "error": failure,
                        "created_at": now_iso(),
                    },
                )
                self.store.put(
                    "turns",
                    turn_id,
                    {
                        "turn_id": turn_id,
                        "run_id": run_id,
                        "employee_id": principal.employee_id,
                        "question_hash": hashlib.sha256(request.question.encode("utf-8")).hexdigest(),
                        "capability_id": capability_id,
                        "status": "failed",
                        "created_at": now_iso(),
                    },
                )
                failure_response = AgentTurnResponse(
                    run_id=run_id,
                    turn_id=turn_id,
                    conversation_id=str(session["conversation_id"]),
                    work_session_id=str(session["session_id"]),
                    status="failed",
                    capability_id=capability_id,
                    answer=AnswerBlock(
                        summary="초안을 만들지 못했습니다.",
                        markdown="초안을 만들지 못했습니다. 입력과 모델 준비 상태를 확인해주세요.",
                    ),
                    context_ref=context.context_id,
                    error_code="draft_generation_failed",
                    goal_plan_ref=str(goal_plan["goal_plan_id"]),
                    source_set_ref=str(source_set["source_set_id"]),
                    citations=citations,
                    grounding_status="partial" if citations else "no_evidence",
                )
                goal_plan.update({"status": "failed", "updated_at": now_iso()})
                self.store.put("goal_plans", str(goal_plan["goal_plan_id"]), goal_plan)
                self._finish_work_session(principal, session, failure_response, request.question)
                raise HTTPException(
                    status_code=502,
                    detail=failure,
                ) from exc
        else:
            raise HTTPException(status_code=501, detail="mutation capability handler is not implemented")

        if citations and capability_id not in {"knowledge.search", "cases.similar"}:
            markers = " ".join(
                f"[{index}](/api/v2/citations/{item.citation_id})"
                for index, item in enumerate(citations[:4], start=1)
            )
            answer.markdown = f"{answer.markdown}\n\n사용한 지식 {markers}"

        self._emit_turn_progress(
            progress_sink,
            "composing",
            "근거와 검증 결과를 바탕으로 답변을 정리하고 있습니다.",
            citation_count=len(citations),
            artifact_count=len(artifacts),
        )

        context.artifact_refs = artifacts
        context.loop_delta = {
            "kind": "job_queued" if job_ref else "artifact_created" if artifacts else "evidence_selected",
            "evidence_ids": [item.evidence_id for item in evidence],
            "artifact_ids": [item.artifact_id for item in artifacts],
            "job_id": job_ref,
        }
        context.manifest.update({"plan_id": plan_ref, "job_id": job_ref})
        self.store.put("contexts", context.context_id, context.model_dump(mode="json"))

        source_set = self._update_auto_sources(
            principal,
            str(session["session_id"]),
            evidence,
            request.external_artifact_refs,
            used_refs=[item.source_ref for item in citations],
        )
        related_questions = generated_related_questions
        artifact_payloads = [
            value
            for item in artifacts
            if (value := self.store.get("artifacts", item.artifact_id)) is not None
        ]
        work_run, knowledge_candidates = self.learning.finish_run(
            principal=principal,
            work_run=work_run,
            context=context,
            intent=intent,
            response_status=status,
            answer_summary=answer.summary,
            artifacts=artifact_payloads,
            evidence_refs=[item.source_ref for item in citations],
            job_id=job_ref,
        )
        harness_results = [HarnessResult.model_validate(raw) for raw in work_run.get("harness_results") or []]
        goal_plan = self._finish_goal_plan(
            goal_plan,
            evidence=evidence,
            artifacts=artifacts,
            queued=bool(job_ref),
            response_status=status,
            plan_ref=plan_ref,
            intent=intent,
            work_run=work_run,
        )
        progress = [
            {
                "step_id": item.get("step_id"),
                "label": item.get("label"),
                "status": item.get("status"),
            }
            for item in goal_plan.get("steps") or []
        ]

        response = AgentTurnResponse(
            run_id=run_id,
            turn_id=turn_id,
            conversation_id=str(session["conversation_id"]),
            work_session_id=str(session["session_id"]),
            status=status,  # type: ignore[arg-type]
            capability_id=capability_id,
            answer=answer,
            evidence_refs=evidence,
            artifact_refs=artifacts,
            offers=[],
            next_actions=self._next_actions(
                work_session_id=str(session["session_id"]),
                artifacts=artifacts,
                evidence=evidence,
                plan_ref=plan_ref,
            ),
            context_ref=context.context_id,
            plan_ref=plan_ref,
            job_ref=job_ref,
            goal_plan_ref=str(goal_plan["goal_plan_id"]),
            source_set_ref=str(source_set["source_set_id"]),
            citations=citations,
            related_questions=related_questions,
            grounding_status=("grounded" if citations or graph_result_bundle is not None else "no_evidence"),
            progress=progress,
            work_run_id=str(work_run["work_run_id"]),
            work_intent=intent,
            graph_result_ref=next(
                (item.artifact_id for item in artifacts if item.artifact_type == "ontology_graph"),
                "",
            ),
            loop_state={
                "flow": (work_run.get("loop") or {}).get("flow") or [],
                "policy": (work_run.get("loop") or {}).get("policy") or {},
                "iteration_count": (work_run.get("loop") or {}).get("iteration_count") or 0,
                "decision": work_run.get("decision") or "",
                "status": work_run.get("status") or "",
                "revision": work_run.get("revision") or 1,
            },
            harness_results=harness_results,
            knowledge_candidates=knowledge_candidates,
            context_usage={
                "page_anchor": context.page_anchor.model_dump(mode="json") if context.page_anchor else None,
                "goal_anchor": context.goal_anchor.model_dump(mode="json") if context.goal_anchor else None,
                "resolved_goal": intent.resolved_goal,
                "presentation_mode": intent.presentation_mode,
                "context_refs": list(intent.context_refs),
                "selected_source_count": len(context.evidence_refs),
                "missing_evidence": (context.evidence_summary or {}).get("missing") or [],
                "raw_content_in_prompt": False,
            },
        )
        response.presentation_plan = presentation_plan(response)
        try:
            a2ui_surface = compile_surface(response)
        except (TypeError, ValueError):
            a2ui_surface = {}
        if a2ui_surface:
            response.a2ui_surface_ref = str(a2ui_surface["surface_id"])
            a2ui_surface["employee_id"] = principal.employee_id
            self.store.put("a2ui_surfaces", response.a2ui_surface_ref, a2ui_surface)
            for artifact in artifacts:
                stored_artifact = self.store.get("artifacts", artifact.artifact_id)
                if not stored_artifact or not self._owns(principal, stored_artifact):
                    continue
                stored_artifact["a2ui_surface_ref"] = response.a2ui_surface_ref
                self.store.put("artifacts", artifact.artifact_id, stored_artifact)
                artifact.metadata["a2ui_surface_ref"] = response.a2ui_surface_ref
        response = self._enforce_response_budget(response)
        run_payload = {
            "run_id": run_id,
            "employee_id": principal.employee_id,
            "conversation_id": str(session["conversation_id"]),
            "work_session_id": str(session["session_id"]),
            "capability_id": capability_id,
            "status": status,
            "context_id": context.context_id,
            "plan_id": plan_ref,
            "job_id": job_ref,
            "goal_plan_id": goal_plan["goal_plan_id"],
            "source_set_id": source_set["source_set_id"],
            "work_run_id": work_run["work_run_id"],
            "events": [
                {"event": "accepted", "run_id": run_id},
                {
                    "event": "sources.selected",
                    "source_set_ref": source_set["source_set_id"],
                    "source_count": len(evidence),
                },
                {
                    "event": "goal.interpreted",
                    "goal_plan_ref": goal_plan["goal_plan_id"],
                    "route_class": goal_plan["route_class"],
                },
                {
                    "event": "capability.selected",
                    "capability_id": capability_id,
                    "route_source": route["source"],
                },
                {"event": "evidence.found", "evidence_count": len(evidence)},
                *(
                    [{"event": "citation.ready", "citation_count": len(citations)}]
                    if citations
                    else []
                ),
                *(
                    [{"event": "artifact.created", "artifact_ids": [item.artifact_id for item in artifacts]}]
                    if artifacts
                    else []
                ),
                *(
                    [{"event": "a2ui.surface", "surface_ref": response.a2ui_surface_ref}]
                    if response.a2ui_surface_ref
                    else []
                ),
                {"event": "final", "status": status},
            ],
            "response": response.model_dump(mode="json"),
            "routing": route,
            "resolved_goal": intent.resolved_goal,
            "presentation_mode": intent.presentation_mode,
            "context_refs": list(intent.context_refs),
            "created_at": now_iso(),
        }
        self.store.put("runs", run_id, run_payload)
        self.store.put(
            "turns",
            turn_id,
            {
                "turn_id": turn_id,
                "run_id": run_id,
                "employee_id": principal.employee_id,
                "question_hash": hashlib.sha256(request.question.encode("utf-8")).hexdigest(),
                "capability_id": capability_id,
                "route_source": route["source"],
                "resolved_goal": intent.resolved_goal,
                "presentation_mode": intent.presentation_mode,
                "context_refs": list(intent.context_refs),
                "evidence_ids": [item.evidence_id for item in evidence],
                "status": status,
                "created_at": now_iso(),
            },
        )
        self._finish_work_session(principal, session, response, request.question)
        return response

    def _enforce_response_budget(self, response: AgentTurnResponse) -> AgentTurnResponse:
        citation_link_pattern = re.compile(
            r"\s*\[\d+\]\(/api/v2/citations/(cite_[A-Za-z0-9]+)\)"
        )

        def keep_rendered_citations() -> None:
            rendered_ids = list(
                dict.fromkeys(
                    re.findall(
                        r"/api/v2/citations/(cite_[A-Za-z0-9]+)",
                        response.answer.markdown,
                    )
                )
            )
            if not rendered_ids:
                if not response.citations:
                    return
                primary = response.citations[0]
                response.answer.markdown = (
                    response.answer.markdown.rstrip()
                    + f"\n\n[근거](/api/v2/citations/{primary.citation_id})"
                )
                rendered_ids = [primary.citation_id]
            by_id = {item.citation_id: item for item in response.citations}
            response.citations = [by_id[item_id] for item_id in rendered_ids if item_id in by_id]

        include_display_html = True

        def refresh_display_html() -> None:
            response.answer.display_html = render_agent_markdown(response.answer.markdown) if include_display_html else ""

        def ensure_primary_citation() -> None:
            if not response.citations or "/api/v2/citations/" in response.answer.markdown:
                return
            citation = response.citations[0]
            response.answer.markdown = (
                response.answer.markdown.rstrip()
                + f"\n\n[근거](/api/v2/citations/{citation.citation_id})"
            )

        def response_size() -> int:
            return len(
                json.dumps(
                    response.model_dump(mode="json"),
                    ensure_ascii=False,
                ).encode("utf-8")
            )

        refresh_display_html()
        keep_rendered_citations()
        latest_harnesses: dict[str, HarnessResult] = {}
        for item in response.harness_results:
            latest_harnesses[item.harness_id] = item
        response.harness_results = [
            item.model_copy(
                update={
                    "checks": [check for check in item.checks if check.status != "passed"][:4],
                    "blockers": item.blockers[:4],
                }
            )
            for item in latest_harnesses.values()
        ]
        response.loop_state = {
            key: response.loop_state.get(key)
            for key in ("iteration_count", "decision", "status", "revision")
            if key in response.loop_state
        }
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= self.settings.response_budget_bytes:
            return response
        include_display_html = False
        refresh_display_html()
        response.evidence_refs = [
            item.model_copy(update={"summary": compact_text(item.summary, 120), "metadata": {}})
            for item in response.evidence_refs[:4]
        ]
        response.citations = [
            item.model_copy(update={"excerpt": compact_text(item.excerpt, 160)})
            for item in response.citations[:4]
        ]
        response.related_questions = [
            item.model_copy(update={"source_refs": item.source_refs[:1]})
            for item in response.related_questions[:3]
        ]
        response.answer.markdown = truncate_markdown(response.answer.markdown, 2200)
        for artifact in response.artifact_refs:
            artifact.preview = artifact.preview[:600]
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.settings.response_budget_bytes:
            response.evidence_refs = [
                item.model_copy(update={"summary": compact_text(item.summary, 80)})
                for item in response.evidence_refs[:2]
            ]
            response.citations = [
                item.model_copy(update={"excerpt": compact_text(item.excerpt, 90)})
                for item in response.citations
            ]
            response.related_questions = [
                item.model_copy(update={"source_refs": item.source_refs[:1]})
                for item in response.related_questions[:2]
                if item.source_refs
            ]
            response.answer.markdown = truncate_markdown(response.answer.markdown, 1800)
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.settings.response_budget_bytes:
            response.evidence_refs = [
                item.model_copy(update={"summary": compact_text(item.summary, 60), "metadata": {}})
                for item in response.evidence_refs[:1]
            ]
            response.citations = [item.model_copy(update={"excerpt": ""}) for item in response.citations[:4]]
            response.related_questions = [
                item.model_copy(update={"source_refs": item.source_refs[:1]})
                for item in response.related_questions[:1]
                if item.source_refs
            ]
            response.progress = []
            response.answer.markdown = truncate_markdown(response.answer.markdown, 1500)
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.settings.response_budget_bytes:
            response.answer.summary = compact_text(response.answer.summary, 420)
            response.answer.markdown = truncate_markdown(response.answer.markdown, 1200)
            response.next_actions = response.next_actions[:2]
            response.related_questions = [
                item.model_copy(update={"source_refs": item.source_refs[:1]})
                for item in response.related_questions[:1]
                if item.source_refs
            ]
            anchor = response.context_usage.get("page_anchor") if isinstance(response.context_usage, dict) else None
            response.context_usage = {
                "page_anchor": {
                    key: anchor.get(key)
                    for key in ("ref", "kind", "title", "resolved")
                    if isinstance(anchor, dict) and key in anchor
                }
                if isinstance(anchor, dict)
                else None,
                "selected_source_count": response.context_usage.get("selected_source_count", 0)
                if isinstance(response.context_usage, dict)
                else 0,
            }
            for artifact in response.artifact_refs:
                artifact.preview = ""
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.settings.response_budget_bytes:
            primary_citation_id = response.citations[0].citation_id if response.citations else ""
            response.answer.markdown = citation_link_pattern.sub(
                lambda match: match.group(0) if match.group(1) == primary_citation_id else "",
                truncate_markdown(response.answer.markdown, 900),
            )
            response.citations = [item.model_copy(update={"excerpt": ""}) for item in response.citations[:1]]
            response.evidence_refs = [
                item.model_copy(update={"summary": "", "metadata": {}})
                for item in response.evidence_refs[:1]
            ]
            response.related_questions = []
            response.progress = []
            response.next_actions = response.next_actions[:1]
            response.harness_results = [item for item in response.harness_results if item.status != "passed"][:1]
            if response.work_intent:
                response.work_intent = response.work_intent.model_copy(
                    update={
                        "goal": compact_text(response.work_intent.goal, 120),
                        "operation_plan": [response.work_intent.operation],
                        "target_ref": compact_text(response.work_intent.target_ref, 120),
                        "desired_outcome": compact_text(response.work_intent.desired_outcome, 120),
                    }
                )
            for artifact in response.artifact_refs:
                artifact.preview = ""
                artifact.metadata = {
                    key: artifact.metadata[key]
                    for key in ("revision", "task_count")
                    if key in artifact.metadata
                }
        payload = response.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.settings.response_budget_bytes:
            response.answer.markdown = truncate_markdown(response.answer.markdown, 700)
            response.citations = [item.model_copy(update={"excerpt": ""}) for item in response.citations[:1]]
            response.evidence_refs = [
                item.model_copy(update={"summary": "", "metadata": {}})
                for item in response.evidence_refs[:1]
            ]
            response.harness_results = []
            response.presentation_plan = {}
            response.progress = []
            response.context_usage = {
                "page_anchor": response.context_usage.get("page_anchor")
                if isinstance(response.context_usage, dict)
                else None,
                "selected_source_count": response.context_usage.get("selected_source_count", 0)
                if isinstance(response.context_usage, dict)
                else 0,
            }
            for artifact in response.artifact_refs:
                artifact.metadata = {}
            ensure_primary_citation()
        keep_rendered_citations()
        refresh_display_html()
        budget = self.settings.response_budget_bytes
        if response_size() > budget:
            response.context_ref = ""
            response.goal_plan_ref = ""
            response.source_set_ref = ""
            response.progress = []
            response.offers = []
            response.next_actions = response.next_actions[:1]
            response.knowledge_candidates = response.knowledge_candidates[:1]
            response.answer.summary = compact_text(response.answer.summary, 240)
            refresh_display_html()
        while response_size() > budget and len(response.answer.markdown) > 240:
            excess = response_size() - budget
            target = max(240, len(response.answer.markdown) - max(80, excess // 2 + 32))
            response.answer.markdown = truncate_markdown(response.answer.markdown, target)
            ensure_primary_citation()
            keep_rendered_citations()
            refresh_display_html()
        if response_size() > budget:
            response.related_questions = response.related_questions[:1]
            response.next_actions = []
            response.knowledge_candidates = []
            response.plan_ref = ""
            response.job_ref = ""
            refresh_display_html()
        response.grounding_status = "grounded" if response.citations or response.graph_result_ref else "no_evidence"
        if response_size() > budget:
            response.related_questions = []
            response.artifact_refs = [
                item.model_copy(update={"preview": "", "metadata": {}})
                for item in response.artifact_refs[:1]
            ]
            response.answer.summary = compact_text(response.answer.summary, 120)
            response.answer.markdown = truncate_markdown(response.answer.markdown, 240)
            ensure_primary_citation()
            keep_rendered_citations()
            refresh_display_html()
        if response_size() > budget:
            response.answer.display_html = ""
        response.grounding_status = "grounded" if response.citations or response.graph_result_ref else "no_evidence"
        return response

    def get_run(self, principal: Principal, run_id: str) -> dict[str, Any]:
        run = self.store.get("runs", run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        if run.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="run belongs to another employee")
        return run

    def create_note_from_turn(self, principal: Principal, request: NoteFromTurnRequest) -> dict[str, Any]:
        run = self.get_run(principal, request.run_id)
        session = self.get_work_session(principal, request.work_session_id)
        if str(run.get("work_session_id") or "") != request.work_session_id:
            raise HTTPException(status_code=409, detail="run does not belong to this work session")
        response = run.get("response") if isinstance(run.get("response"), dict) else {}
        answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
        body = str(answer.get("markdown") or answer.get("summary") or "").strip()
        if not body:
            raise HTTPException(status_code=409, detail="the selected turn has no answer to save")
        artifact_id = new_id("artifact")
        title = compact_text(request.title or str(answer.get("summary") or "업무 지식 노트"), 160)
        citation_refs = [str(item.get("citation_id") or "") for item in response.get("citations") or [] if item.get("citation_id")]
        source_refs = [str(item.get("evidence_id") or "") for item in response.get("evidence_refs") or [] if item.get("evidence_id")]
        artifact = {
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "capability_id": "knowledge.note",
            "status": "provisional",
            "title": title or "업무 지식 노트",
            "draft": {
                "title": title or "업무 지식 노트",
                "body": body,
                "source_refs": source_refs,
                "citation_refs": citation_refs,
            },
            "work_session_id": request.work_session_id,
            "revision": 1,
            "evidence_ledger": response.get("evidence_refs") or [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("artifacts", artifact_id, artifact)
        source_set = self._ensure_source_set(principal, request.work_session_id)
        pinned = list(source_set.get("pinned") or [])
        if artifact_id not in pinned:
            pinned.append(artifact_id)
        source_set.update(
            {
                "pinned": pinned[:100],
                "revision": int(source_set.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("source_sets", str(source_set["source_set_id"]), source_set)
        session.update(
            {
                "active_artifact_id": artifact_id,
                "revision": int(session.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("work_sessions", request.work_session_id, session)
        return {"artifact": self.get_artifact(principal, artifact_id), "source_set": self.get_source_set(principal, request.work_session_id)}

    def use_note_as_source(self, principal: Principal, artifact_id: str) -> dict[str, Any]:
        artifact = self.get_artifact(principal, artifact_id)
        if artifact.get("capability_id") != "knowledge.note":
            raise HTTPException(status_code=409, detail="only a private knowledge note can be used as a source")
        session_id = str(artifact.get("work_session_id") or "")
        source_set = self._ensure_source_set(principal, session_id)
        pinned = list(source_set.get("pinned") or [])
        if artifact_id not in pinned:
            pinned.append(artifact_id)
            source_set.update(
                {
                    "pinned": pinned[:100],
                    "revision": int(source_set.get("revision") or 1) + 1,
                    "updated_at": now_iso(),
                }
            )
            self.store.put("source_sets", str(source_set["source_set_id"]), source_set)
        return {"artifact_id": artifact_id, "status": "source_ready", "source_set": self.get_source_set(principal, session_id)}

    def get_context(self, principal: Principal, context_id: str) -> dict[str, Any]:
        context = self.store.get("contexts", context_id)
        if not context:
            raise HTTPException(status_code=404, detail="context not found")
        if context.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="context belongs to another employee")
        return context

    def get_evaluation(self, principal: Principal, evaluation_id: str) -> dict[str, Any]:
        return self._require_owned(
            principal,
            self.store.get("evaluations", evaluation_id),
            "evaluation",
        )

    def get_usage_ledger(self, principal: Principal, usage_id: str) -> dict[str, Any]:
        return self._require_owned(
            principal,
            self.store.get("usage_ledgers", usage_id),
            "usage ledger",
        )

    def list_harnesses(self) -> dict[str, Any]:
        items = self.harnesses.definitions()
        return {"version": "1.0", "count": len(items), "items": items}

    def validate_harness(
        self,
        principal: Principal,
        harness_id: str,
        request: HarnessValidateRequest,
    ) -> dict[str, Any]:
        context = WorkContextPack.model_validate(self.get_context(principal, request.context_id))
        run = self.learning.get_run(principal, request.work_run_id) if request.work_run_id else None
        intent = (
            WorkIntentEngine.infer(
                context.goal,
                capability_id=context.capability_id,
                page_ref=context.page_ref,
                task_ref=context.task_ref,
                target_ref=(context.page_anchor.ref if context.page_anchor else ""),
                operation=WorkOperation.validate,
            )
            if run is None
            else WorkIntent.model_validate(run.get("intent") or {})
        )
        artifact = self.get_artifact(principal, request.artifact_id) if request.artifact_id else None
        candidate = self.learning.get_candidate(principal, request.candidate_id) if request.candidate_id else None
        try:
            result = self.harnesses.evaluate(
                harness_id,
                phase=request.phase,
                intent=intent,
                context=context,
                artifact=artifact,
                candidate=candidate,
                task_mode=context.task_mode,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown harness: {harness_id}") from exc
        result_id = f"{request.work_run_id or context.context_id}:{harness_id}:{request.phase}"
        self.store.put(
            "harness_results",
            result_id,
            {
                "employee_id": principal.employee_id,
                "work_run_id": request.work_run_id,
                "context_id": context.context_id,
                **result.model_dump(mode="json"),
            },
        )
        return result.model_dump(mode="json")

    def create_plan(
        self,
        principal: Principal,
        capability_id: str,
        request: CapabilityPlanRequest,
    ) -> AgentTurnResponse:
        return self.run_turn(
            principal,
            AgentTurnRequest(
                question=request.goal,
                page_ref=request.page_ref,
                task_ref=request.task_ref,
                input_delta=request.input,
                capability_id=capability_id,
            ),
        )

    def promote_knowledge_candidate(
        self,
        principal: Principal,
        candidate_id: str,
        request: KnowledgeCandidatePromoteRequest,
    ) -> dict[str, Any]:
        candidate, harness_result = self.learning.validate_candidate_promotion(principal, candidate_id)
        body = "# Summary\n\n" + str(candidate.get("reusable_lesson") or candidate.get("summary") or "").strip()
        source_refs = [
            {"type": "boi-agent-v2-evidence", "ref": str(ref)}
            for ref in candidate.get("source_refs") or []
            if str(ref).strip()
        ]
        domain_payload = {
            "candidate_id": candidate_id,
            "title": str(candidate.get("title") or "업무 지식 개선 후보"),
            "description": str(candidate.get("summary") or "업무 수행 결과에서 검증된 재사용 지식"),
            "body": body,
            "boi_type": "boi/reference",
            "classification": "internal",
            "tags": ["work-learning", "knowledge-candidate"],
            "source_refs": source_refs,
            "source_local_id": candidate_id,
            "source_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "target_visibility": request.target_visibility,
            "team_id": request.team_id,
            "reviewer": "hotl-curator",
            "promotion_reason": request.reason.strip(),
        }
        try:
            preview = self.domain_services.execute(
                "knowledge.promotion.preview",
                principal,
                domain_payload,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        domain_validation = {
            "valid": bool(preview.get("ok") and validation.get("ok", True)),
            "errors": list(validation.get("errors") or []),
            "warnings": list(validation.get("warnings") or []),
        }
        plan_id = new_id("plan")
        plan = {
            "plan_id": plan_id,
            "employee_id": principal.employee_id,
            "capability_id": "knowledge.draft",
            "status": "draft",
            "candidate_id": candidate_id,
            "artifact_id": "",
            "work_run_id": str(candidate.get("source_work_run_id") or ""),
            "domain_operation": "knowledge.promotion.submit",
            "domain_payload": domain_payload,
            "domain_ref": str(preview.get("preview_id") or ""),
            "domain_kind": "knowledge_promotion",
            "domain_validation": domain_validation,
            "production_changed": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("plans", plan_id, plan)
        result = self.learning.promote_candidate(
            principal,
            candidate_id,
            request,
            promotion_preview=preview,
            plan_id=plan_id,
            harness_result=harness_result,
        )
        return {**result, "domain_validation": domain_validation}

    async def confirm_plan(self, principal: Principal, plan_id: str, reason: str) -> dict[str, Any]:
        plan = self.store.get("plans", plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="plan not found")
        if plan.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="plan belongs to another employee")
        if plan.get("status") != "draft":
            raise HTTPException(status_code=409, detail="only a draft plan can be confirmed")
        if not reason.strip():
            raise HTTPException(status_code=422, detail="confirmation reason is required")
        validation = plan.get("domain_validation") if isinstance(plan.get("domain_validation"), dict) else {}
        if validation and validation.get("valid") is False:
            raise HTTPException(
                status_code=409,
                detail={"status": "domain_validation_failed", "validation": validation},
            )
        domain_operation = str(plan.get("domain_operation") or "")
        if domain_operation == "action.invoke" and principal.token_id and "boi.execute.low" not in principal.token_scopes:
            raise HTTPException(status_code=403, detail="boi.execute.low scope is required")
        domain_result: dict[str, Any] = {}
        if domain_operation == "work_routine.create":
            routine = self.create_work_routine(
                principal,
                WorkRoutineCreateRequest.model_validate(plan.get("domain_payload") or {}),
            )
            domain_result = {
                "status": "active",
                "routine_id": routine["routine_id"],
                "next_run_at": routine.get("next_run_at") or "",
                "production_changed": True,
            }
        elif domain_operation:
            try:
                domain_result = await self.domain_services.execute_async(
                    domain_operation,
                    principal,
                    {
                        **(plan.get("domain_payload") if isinstance(plan.get("domain_payload"), dict) else {}),
                        "domain_ref": str(plan.get("domain_ref") or ""),
                        "plan_id": plan_id,
                        "reason": reason.strip(),
                    },
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        plan.update(
            {
                "status": "confirmed",
                "confirmed_at": now_iso(),
                "confirmed_by": principal.employee_id,
                "confirmation_reason": reason,
                "domain_result": domain_result,
                "production_changed": bool(domain_result.get("production_changed", False)),
            }
        )
        self.store.put("plans", plan_id, plan)
        candidate_id = str(plan.get("candidate_id") or "")
        if candidate_id and domain_operation == "knowledge.promotion.submit" and domain_result.get("status") == "published":
            candidate = self.learning.get_candidate(principal, candidate_id)
            target_asset_ref = str(
                domain_result.get("target_boi_id")
                or (domain_result.get("target") or {}).get("metadata", {}).get("boi_id")
                or candidate.get("target_asset_ref")
                or ""
            )
            candidate.update(
                {
                    "status": "reviewed",
                    "visibility": str((plan.get("domain_payload") or {}).get("target_visibility") or "team"),
                    "target_asset_ref": target_asset_ref,
                    "promotion": {
                        **(candidate.get("promotion") if isinstance(candidate.get("promotion"), dict) else {}),
                        "status": "published",
                        "promotion_id": str(domain_result.get("promotion_id") or ""),
                        "published_at": now_iso(),
                        "confirmed_by": principal.employee_id,
                    },
                    "revision": int(candidate.get("revision") or 1) + 1,
                    "updated_at": now_iso(),
                }
            )
            self.store.put("knowledge_candidates", candidate_id, candidate)
            try:
                index_refresh = self.search.index_records(principal, [target_asset_ref]) if target_asset_ref else {"status": "target_missing"}
            except Exception as exc:
                index_refresh = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
            domain_result["index_refresh"] = index_refresh
            plan["domain_result"] = domain_result
            self.store.put("plans", plan_id, plan)
        work_run_id = str(plan.get("work_run_id") or "")
        work_run: dict[str, Any] = {}
        knowledge_candidates: list[KnowledgeCandidateRef] = []
        if work_run_id:
            current = self.learning.get_run(principal, work_run_id)
            work_run = current
            if current.get("status") not in {"completed", "failed", "cancelled", "stopped"}:
                result_ref = str(
                    domain_result.get("request_id")
                    or domain_result.get("draft_id")
                    or domain_result.get("domain_ref")
                    or plan.get("domain_ref")
                    or plan_id
                )
                delta_kind = "action_result" if domain_operation == "action.invoke" else "human_input"
                work_run, knowledge_candidates = self.learning.continue_run(
                    principal,
                    work_run_id,
                    WorkRunContinueRequest(
                        expected_revision=int(current.get("revision") or 1),
                        confirmation="confirm" if delta_kind == "human_input" else None,
                        delta=LoopDelta(
                            kind=delta_kind,  # type: ignore[arg-type]
                            summary=(
                                str(domain_result.get("message") or domain_result.get("status") or "Action 결과를 확인했습니다.")
                                if domain_operation == "action.invoke"
                                else "초안 검토를 확인하고 기존 업무 서비스의 다음 단계로 전달했습니다."
                            ),
                            ref=result_ref,
                            metadata={"plan_id": plan_id, "domain_operation": domain_operation},
                        ),
                    ),
                )
        goal_plan = self._advance_goal_plan_after_domain_result(
            principal,
            work_run_id=work_run_id,
            domain_operation=domain_operation,
        )
        return {
            "plan_id": plan_id,
            "status": "confirmed",
            "artifact_id": plan.get("artifact_id") or "",
            "domain_result": domain_result,
            "production_changed": bool(domain_result.get("production_changed", False)),
            "work_run_id": work_run_id,
            "work_run_status": work_run.get("status") or "",
            "goal_plan_ref": str(goal_plan.get("goal_plan_id") or ""),
            "goal_plan_status": str(goal_plan.get("status") or ""),
            "knowledge_candidates": [item.model_dump(mode="json") for item in knowledge_candidates],
            "message": (
                "확인한 계획을 기존 업무 서비스로 실행하고 결과를 WorkRun에 기록했습니다."
                if domain_operation == "action.invoke"
                else "자동 확인을 활성화했습니다. 다음 확인 조건과 최근 결과는 BoI Agent에서 볼 수 있습니다."
                if domain_operation == "work_routine.create"
                else "초안 검토를 확인하고 기존 업무 서비스의 게시 요청 단계로 전달했습니다."
                if domain_operation
                else "초안 검토를 확인했습니다. 실제 게시나 실행은 해당 업무 API의 별도 확인을 거칩니다."
            ),
        }

    def create_deep_job(self, principal: Principal, request: DeepJobRequest) -> dict[str, Any]:
        response = self.run_turn(
            principal,
            AgentTurnRequest(
                question=request.goal,
                page_ref=request.page_ref,
                task_ref=request.task_ref,
                input_delta={
                    **request.input,
                    "timeout_seconds": request.timeout_seconds,
                    "pilot_mode": request.pilot_mode,
                    "token_budget": request.token_budget,
                    "max_tool_calls": request.max_tool_calls,
                    "max_subagents": request.max_subagents,
                    "max_parallelism": request.max_parallelism,
                },
                capability_id=request.capability_id,
            ),
        )
        return {"job_id": response.job_ref, "run_id": response.run_id, "status": response.status}

    @staticmethod
    def _routine_next_run(interval_seconds: int, no_change_count: int, adaptive_backoff: bool) -> str:
        factor = min(8, 2 ** max(0, no_change_count)) if adaptive_backoff else 1
        return (datetime.now(timezone.utc) + timedelta(seconds=max(60, interval_seconds) * factor)).isoformat()

    @staticmethod
    def _routine_failure_retry_at(failure_count: int) -> str:
        delay_seconds = min(300, 15 * (2 ** max(0, failure_count - 1)))
        return (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()

    @staticmethod
    def _cron_from_routine_schedule(schedule: dict[str, Any]) -> str:
        repeat_type = str(schedule.get("repeat_type") or "").strip().lower()
        time_value = str(schedule.get("time") or "09:00")
        try:
            hour, minute = [int(value) for value in time_value.split(":", 1)]
        except (TypeError, ValueError):
            hour, minute = 9, 0
        hour = min(23, max(0, hour))
        minute = min(59, max(0, minute))
        if repeat_type == "daily":
            return f"{minute} {hour} * * *"
        if repeat_type == "weekly":
            allowed = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
            weekdays = [str(item).upper() for item in schedule.get("weekdays") or [] if str(item).upper() in allowed]
            return f"{minute} {hour} * * {','.join(weekdays or ['MON'])}"
        if repeat_type == "monthly":
            try:
                month_day = min(31, max(1, int(schedule.get("month_day") or 1)))
            except (TypeError, ValueError):
                month_day = 1
            return f"{minute} {hour} {month_day} * *"
        return ""

    def _routine_next_run_for(
        self,
        routine: dict[str, Any],
        *,
        no_change_count: int = 0,
        base: datetime | None = None,
    ) -> str:
        policy = LoopPolicy.model_validate(routine.get("loop_policy") or {})
        if policy.trigger != LoopTriggerKind.schedule:
            return self._routine_next_run(policy.interval_seconds, no_change_count, policy.adaptive_backoff)
        schedule = routine.get("schedule_config") if isinstance(routine.get("schedule_config"), dict) else {}
        timezone_name = str(routine.get("timezone") or schedule.get("timezone") or "Asia/Seoul")
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = timezone.utc
        base_utc = base or datetime.now(timezone.utc)
        if base_utc.tzinfo is None:
            base_utc = base_utc.replace(tzinfo=timezone.utc)
        local_base = base_utc.astimezone(local_tz)
        if str(schedule.get("repeat_type") or "").lower() == "once":
            once_at = str(schedule.get("once_at") or "").strip()
            if not once_at:
                return ""
            try:
                parsed = datetime.fromisoformat(once_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=local_tz)
                return parsed.astimezone(timezone.utc).isoformat() if parsed > local_base else ""
            except ValueError:
                return ""
        expression = str(routine.get("cron") or "").strip() or self._cron_from_routine_schedule(schedule)
        if not expression:
            return self._routine_next_run(policy.interval_seconds, no_change_count, policy.adaptive_backoff)
        try:
            next_local = croniter(expression, local_base).get_next(datetime)
        except (KeyError, TypeError, ValueError):
            return ""
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=local_tz)
        return next_local.astimezone(timezone.utc).isoformat()

    def create_work_routine(
        self,
        principal: Principal,
        request: WorkRoutineCreateRequest,
    ) -> dict[str, Any]:
        routine_id = new_id("routine")
        trigger = LoopTriggerKind(request.trigger)
        loop_kind = LoopKind.proactive if trigger == LoopTriggerKind.event else LoopKind.time
        if request.routine_stop == "max_runs" and request.max_runs < 1:
            raise HTTPException(status_code=422, detail="max_runs must be at least 1 when routine_stop is max_runs")
        now = now_iso()
        row = {
            "routine_id": routine_id,
            "employee_id": principal.employee_id,
            "principal_roles": list(principal.roles),
            "principal_teams": list(principal.teams),
            "title": request.title,
            "goal": request.goal,
            "capability_id": request.capability_id or "",
            "page_ref": request.page_ref,
            "task_ref": request.task_ref,
            "input": copy.deepcopy(request.input),
            "event_ref": request.event_ref,
            "target_kind": "agent_turn",
            "target_ref": "",
            "schedule_config": copy.deepcopy(request.schedule_config),
            "cron": request.cron.strip(),
            "timezone": request.timezone or str(request.schedule_config.get("timezone") or "Asia/Seoul"),
            "status": "active",
            "loop_policy": LoopPolicy(
                kind=loop_kind,
                trigger=trigger,
                task_stop="exit_criteria" if request.task_ref else "agent_done",
                routine_stop=request.routine_stop,
                max_runs=request.max_runs,
                interval_seconds=request.interval_seconds,
                adaptive_backoff=True,
                routine_id=routine_id,
            ).model_dump(mode="json"),
            "run_count": 0,
            "failure_count": 0,
            "max_failure_attempts": 3,
            "no_change_count": 0,
            "last_source_fingerprint": "",
            "last_result_fingerprint": "",
            "next_run_at": "",
            "run_history": [],
            "origin": request.origin,
            "surface_visibility": request.surface_visibility,
            "created_at": now,
            "updated_at": now,
        }
        if trigger in {LoopTriggerKind.schedule, LoopTriggerKind.interval}:
            row["next_run_at"] = self._routine_next_run_for(row)
        return self.store.put("work_routines", routine_id, row)

    def create_business_event_schedule_routine(
        self,
        principal: Principal,
        *,
        definition_id: str,
        title: str,
        target_event_type: str,
        schedule_config: dict[str, Any],
        cron: str = "",
        timezone_name: str = "Asia/Seoul",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        repeat_type = str(schedule_config.get("repeat_type") or "").lower()
        routine = self.create_work_routine(
            principal,
            WorkRoutineCreateRequest(
                title=title,
                goal=f"정해진 일정에 {title} 신호를 평가합니다.",
                trigger="schedule",
                schedule_config=schedule_config,
                cron=cron,
                timezone=timezone_name,
                event_ref=target_event_type,
                routine_stop="max_runs" if repeat_type == "once" else "cancelled",
                max_runs=1 if repeat_type == "once" else 0,
                input=payload or {},
                origin="business_event",
                surface_visibility="normal",
            ),
        )
        routine.update(
            {
                "target_kind": "business_event",
                "target_ref": definition_id,
                "managed_by": f"business-event-definition:{definition_id}",
                "updated_at": now_iso(),
            }
        )
        return self.store.put("work_routines", str(routine["routine_id"]), routine)

    def get_work_routine(self, principal: Principal, routine_id: str) -> dict[str, Any]:
        return self._require_owned(principal, self.store.get("work_routines", routine_id), "work routine")

    def list_work_routines(
        self,
        principal: Principal,
        *,
        limit: int = 50,
        surface: str = "",
        status: str = "",
    ) -> dict[str, Any]:
        items = self.store.list(
            "work_routines",
            employee_id=principal.employee_id,
            limit=100,
        )
        if surface == "pet":
            items = [item for item in items if str(item.get("surface_visibility") or "normal") != "diagnostic"]
        if status == "actionable":
            items = [item for item in items if str(item.get("status") or "") in {"active", "failed"}]
        elif status:
            allowed = {item.strip() for item in status.split(",") if item.strip()}
            items = [item for item in items if str(item.get("status") or "") in allowed]
        selected = items[: max(1, min(limit, 100))]
        return {"count": len(selected), "total": len(items), "items": selected}

    def _execute_system_routine_target(
        self,
        principal: Principal,
        routine: dict[str, Any],
        request: WorkRoutineTriggerRequest,
        policy: LoopPolicy,
    ) -> dict[str, Any]:
        if self.routine_target_executor is None:
            raise RuntimeError("scheduled system target executor is unavailable")
        target_kind = str(routine.get("target_kind") or "")
        target_ref = str(routine.get("target_ref") or "")
        context_id = new_id("context")
        evidence_ref = f"{target_kind}:{target_ref}" if target_ref else target_kind
        context = WorkContextPack(
            context_id=context_id,
            employee_id=principal.employee_id,
            capability_id="business_event.plan" if target_kind == "business_event" else "knowledge.search",
            goal=str(routine.get("goal") or routine.get("title") or "예약 업무 실행"),
            page_ref=str(routine.get("page_ref") or ""),
            task_ref=str(routine.get("task_ref") or ""),
            task_mode=TaskMode.autopilot,
            evidence_refs=[
                EvidenceRef(
                    evidence_id=evidence_ref,
                    kind="event" if target_kind == "business_event" else "runtime",
                    title=str(routine.get("title") or target_ref or "예약 업무"),
                    summary="활성화된 예약 정의와 실행 시각을 시스템이 확인했습니다.",
                    source="runtime",
                    authority="runtime",
                )
            ],
            business_context={
                "routine_id": routine.get("routine_id"),
                "target_kind": target_kind,
                "target_ref": target_ref,
                "trigger": policy.trigger.value,
            },
            context_manifest=ContextManifest(
                selected_refs=[evidence_ref],
                source_revision=str(routine.get("updated_at") or ""),
                raw_content_in_prompt=False,
                provenance={evidence_ref: {"source": "runtime", "authority": "runtime"}},
            ),
        )
        self.store.put("contexts", context_id, context.model_dump(mode="json"))
        run_id = new_id("run")
        intent = WorkIntent(
            goal=context.goal,
            asset_kind=WorkAssetKind.business_event,
            operation=WorkOperation.run,
            operation_plan=[WorkOperation.observe, WorkOperation.run, WorkOperation.complete],
            target_ref=target_ref,
            desired_outcome="verified_system_result",
            risk=RiskLevel.low,
            confidence=1.0,
        )
        work_run = self.learning.create_run(
            principal=principal,
            agent_run_id=run_id,
            session={"session_id": ""},
            context=context,
            intent=intent,
            goal_plan_id="",
            loop_policy=policy,
        )
        if work_run.get("status") == "blocked":
            raise RuntimeError("scheduled system target failed Harness preflight")
        try:
            result = self.routine_target_executor(routine, request, principal)
        except Exception as exc:
            self.learning.fail_run(principal, str(work_run["work_run_id"]), str(exc))
            raise
        result_status = str(result.get("decision") or result.get("status") or "completed")
        event = result.get("event") if isinstance(result.get("event"), dict) else {}
        result_ref = str(event.get("event_id") or result.get("confirmation_id") or target_ref or routine.get("routine_id") or "")
        summary = str(result.get("reason") or result.get("message") or f"예약 업무 결과: {result_status}")
        completed_run = self.learning.finish_system_run(
            principal=principal,
            work_run=work_run,
            summary=summary,
            result_ref=result_ref,
            result_status=result_status,
            metadata={
                "routine_id": routine.get("routine_id"),
                "target_kind": target_kind,
                "target_ref": target_ref,
                "decision": result_status,
            },
        )
        run_status = "failed" if completed_run.get("status") == "blocked" else "completed"
        self.store.put(
            "runs",
            run_id,
            {
                "run_id": run_id,
                "employee_id": principal.employee_id,
                "capability_id": context.capability_id,
                "status": run_status,
                "context_id": context_id,
                "work_run_id": completed_run["work_run_id"],
                "events": [
                    {"event": "accepted", "run_id": run_id},
                    {"event": "system.target.completed", "target_kind": target_kind, "status": result_status},
                    {"event": "final", "status": run_status},
                ],
                "response": {"status": result_status, "summary": summary, "result_ref": result_ref},
                "created_at": now_iso(),
            },
        )
        return {
            "run_id": run_id,
            "work_run_id": str(completed_run["work_run_id"]),
            "status": run_status,
            "summary": summary,
            "evidence_ids": [result_ref] if result_ref else [],
            "artifact_ids": [],
            "target_result": result,
        }

    def trigger_work_routine(
        self,
        principal: Principal,
        routine_id: str,
        request: WorkRoutineTriggerRequest,
    ) -> dict[str, Any]:
        routine = self.get_work_routine(principal, routine_id)
        if routine.get("status") != "active":
            raise HTTPException(status_code=409, detail=f"work routine is {routine.get('status')}")
        configured_event = str(routine.get("event_ref") or "")
        if configured_event and request.event_ref and configured_event != request.event_ref:
            raise HTTPException(status_code=409, detail="event does not match this work routine")
        policy = LoopPolicy.model_validate(routine.get("loop_policy") or {})
        source_fingerprint = str(request.source_fingerprint or "")
        if source_fingerprint and source_fingerprint == str(routine.get("last_source_fingerprint") or ""):
            no_change_count = int(routine.get("no_change_count") or 0) + 1
            routine.update(
                {
                    "no_change_count": no_change_count,
                    "next_run_at": self._routine_next_run_for(
                        routine,
                        no_change_count=no_change_count,
                    )
                    if policy.trigger in {LoopTriggerKind.schedule, LoopTriggerKind.interval}
                    else "",
                    "updated_at": now_iso(),
                }
            )
            routine.setdefault("run_history", []).append(
                {
                    "status": "skipped_no_change",
                    "source_fingerprint": source_fingerprint,
                    "at": now_iso(),
                }
            )
            routine["run_history"] = routine["run_history"][-20:]
            self.store.put("work_routines", routine_id, routine)
            return {
                "routine_id": routine_id,
                "status": "skipped_no_change",
                "next_run_at": routine.get("next_run_at") or "",
            }

        policy = policy.model_copy(update={"source_fingerprint": source_fingerprint, "routine_id": routine_id})
        input_delta = {
            **(routine.get("input") or {}),
            **request.input,
            "_routine_id": routine_id,
            "_trigger_kind": policy.trigger.value,
            "_event_ref": request.event_ref or configured_event,
        }
        if str(routine.get("target_kind") or "agent_turn") == "agent_turn":
            response = self.run_turn(
                principal,
                AgentTurnRequest(
                    question=str(routine.get("goal") or ""),
                    page_ref=str(routine.get("page_ref") or ""),
                    task_ref=str(routine.get("task_ref") or ""),
                    capability_id=str(routine.get("capability_id") or "") or None,
                    input_delta=input_delta,
                    loop_policy=policy,
                ),
            )
            execution = {
                "run_id": response.run_id,
                "work_run_id": response.work_run_id,
                "status": response.status,
                "summary": response.answer.summary,
                "evidence_ids": [item.evidence_id for item in response.evidence_refs],
                "artifact_ids": [item.artifact_id for item in response.artifact_refs],
                "target_result": {},
            }
        else:
            execution = self._execute_system_routine_target(principal, routine, request, policy)
        result_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "status": execution["status"],
                    "answer": execution["summary"],
                    "evidence": execution["evidence_ids"],
                    "artifacts": execution["artifact_ids"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        repeated_result = result_fingerprint == str(routine.get("last_result_fingerprint") or "")
        no_change_count = int(routine.get("no_change_count") or 0) + 1 if repeated_result else 0
        run_count = int(routine.get("run_count") or 0) + 1
        stop_for_count = policy.routine_stop == "max_runs" and policy.max_runs > 0 and run_count >= policy.max_runs
        stop_for_event = policy.routine_stop == "event_resolved" and request.event_resolved
        status = "completed" if stop_for_count or stop_for_event else "active"
        routine.update(
            {
                "status": status,
                "run_count": run_count,
                "failure_count": 0,
                "last_error": "",
                "no_change_count": no_change_count,
                "last_source_fingerprint": source_fingerprint,
                "last_result_fingerprint": result_fingerprint,
                "last_run_id": execution["run_id"],
                "last_work_run_id": execution["work_run_id"],
                "last_status": execution["status"],
                "last_result_summary": execution["summary"],
                "next_run_at": (
                    self._routine_next_run_for(routine, no_change_count=no_change_count)
                    if status == "active" and policy.trigger in {LoopTriggerKind.schedule, LoopTriggerKind.interval}
                    else ""
                ),
                "updated_at": now_iso(),
            }
        )
        routine.setdefault("run_history", []).append(
            {
                "run_id": execution["run_id"],
                "work_run_id": execution["work_run_id"],
                "status": execution["status"],
                "source_fingerprint": source_fingerprint,
                "result_fingerprint": result_fingerprint,
                "repeated_result": repeated_result,
                "at": now_iso(),
            }
        )
        routine["run_history"] = routine["run_history"][-20:]
        self.store.put("work_routines", routine_id, routine)
        return {
            "routine_id": routine_id,
            "status": status,
            "run_id": execution["run_id"],
            "work_run_id": execution["work_run_id"],
            "result_status": execution["status"],
            "target_result": execution.get("target_result") or {},
            "repeated_result": repeated_result,
            "next_run_at": routine.get("next_run_at") or "",
        }

    def cancel_work_routine(self, principal: Principal, routine_id: str) -> dict[str, Any]:
        routine = self.get_work_routine(principal, routine_id)
        if routine.get("status") != "active":
            raise HTTPException(status_code=409, detail=f"work routine is already {routine.get('status')}")
        routine.update(
            {
                "status": "cancelled",
                "next_run_at": "",
                "cancelled_at": now_iso(),
                "cancelled_by": principal.employee_id,
                "updated_at": now_iso(),
            }
        )
        self.store.put("work_routines", routine_id, routine)
        return {"routine_id": routine_id, "status": "cancelled"}

    def enqueue_work_routine_trigger(
        self,
        routine_id: str,
        request: WorkRoutineTriggerRequest,
        *,
        source_ref: str = "",
    ) -> dict[str, Any]:
        routine = self.store.get("work_routines", routine_id)
        if not routine:
            raise HTTPException(status_code=404, detail="work routine not found")
        if routine.get("status") != "active":
            raise HTTPException(status_code=409, detail=f"work routine is {routine.get('status')}")
        trigger_id = new_id("routine-trigger")
        row = {
            "trigger_id": trigger_id,
            "routine_id": routine_id,
            "employee_id": str(routine.get("employee_id") or ""),
            "status": "queued",
            "attempt": 0,
            "max_attempts": 3,
            "source_ref": source_ref,
            "request": request.model_dump(mode="json"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("routine_triggers", trigger_id, row)
        return {"trigger_id": trigger_id, "routine_id": routine_id, "status": "queued"}

    def run_due_work_routines(self, *, limit: int = 2) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 10))
        results: list[dict[str, Any]] = []
        queued_triggers = [
            item
            for item in self.store.list("routine_triggers", limit=1000)
            if item.get("status") == "queued"
        ]
        selected_triggers = queued_triggers[:limit]
        for trigger in selected_triggers:
            routine = self.store.get("work_routines", str(trigger.get("routine_id") or "")) or {}
            identity = Principal(
                employee_id=str(routine.get("employee_id") or trigger.get("employee_id") or ""),
                display_name=str(routine.get("employee_id") or trigger.get("employee_id") or ""),
                roles=[str(item) for item in routine.get("principal_roles") or []],
                teams=[str(item) for item in routine.get("principal_teams") or []],
                auth_source="work_routine_trigger",
            )
            try:
                result = self.trigger_work_routine(
                    identity,
                    str(trigger.get("routine_id") or ""),
                    WorkRoutineTriggerRequest.model_validate(trigger.get("request") or {}),
                )
                trigger.update({"status": "completed", "result": result, "completed_at": now_iso(), "updated_at": now_iso()})
                self.store.put("routine_triggers", str(trigger.get("trigger_id") or ""), trigger)
                results.append(result)
            except Exception as exc:
                attempt = int(trigger.get("attempt") or 0) + 1
                retry = attempt < int(trigger.get("max_attempts") or 3)
                trigger.update(
                    {
                        "status": "queued" if retry else "failed",
                        "attempt": attempt,
                        "error": f"{type(exc).__name__}: {exc}",
                        "updated_at": now_iso(),
                    }
                )
                self.store.put("routine_triggers", str(trigger.get("trigger_id") or ""), trigger)
        remaining = limit - len(selected_triggers)
        if remaining <= 0:
            return results
        now = datetime.now(timezone.utc)
        due = []
        for routine in self.store.list("work_routines", limit=1000):
            if routine.get("status") != "active" or not routine.get("next_run_at"):
                continue
            try:
                if parse_time(str(routine["next_run_at"])) <= now:
                    due.append(routine)
            except (TypeError, ValueError):
                continue
        for routine in due[:remaining]:
            identity = Principal(
                employee_id=str(routine.get("employee_id") or ""),
                display_name=str(routine.get("employee_id") or ""),
                roles=[str(item) for item in routine.get("principal_roles") or []],
                teams=[str(item) for item in routine.get("principal_teams") or []],
                auth_source="work_routine",
            )
            try:
                results.append(
                    self.trigger_work_routine(
                        identity,
                        str(routine.get("routine_id") or ""),
                        WorkRoutineTriggerRequest(),
                    )
                )
            except Exception as exc:
                failure_count = int(routine.get("failure_count") or 0) + 1
                max_attempts = max(1, int(routine.get("max_failure_attempts") or 3))
                error = f"{type(exc).__name__}: {exc}"
                routine["failure_count"] = failure_count
                routine["last_error"] = error
                routine["status"] = "failed" if failure_count >= max_attempts else "active"
                routine["next_run_at"] = (
                    "" if routine["status"] == "failed" else self._routine_failure_retry_at(failure_count)
                )
                routine["updated_at"] = now_iso()
                routine.setdefault("run_history", []).append(
                    {
                        "status": "retry_scheduled" if routine["status"] == "active" else "failed",
                        "attempt": failure_count,
                        "error": error,
                        "at": now_iso(),
                    }
                )
                routine["run_history"] = routine["run_history"][-20:]
                self.store.put("work_routines", str(routine.get("routine_id") or ""), routine)
        return results

    def get_job(self, principal: Principal, job_id: str) -> dict[str, Any]:
        job = self.store.get("jobs", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="job belongs to another employee")
        return job

    def cancel_job(self, principal: Principal, job_id: str) -> dict[str, Any]:
        job = self.get_job(principal, job_id)
        status = str(job.get("status") or "")
        if status in {"completed", "failed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"job is already {status}")
        job.update(
            {
                "status": "cancelled",
                "cancelled_at": now_iso(),
                "cancelled_by": principal.employee_id,
                "message": "사용자가 심층 작업을 취소했습니다.",
            }
        )
        self.store.put("jobs", job_id, job)
        return {"job_id": job_id, "status": "cancelled"}

    def get_artifact(self, principal: Principal, artifact_id: str) -> dict[str, Any]:
        artifact = self.store.get("artifacts", artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found")
        if artifact.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="artifact belongs to another employee")
        hydrated = copy.deepcopy(artifact)
        hydrated.setdefault("actions", [])
        if hydrated.get("capability_id") == "sop.plan" and isinstance(hydrated.get("draft"), dict):
            hydrated["draft"] = self._normalise_sop_draft(hydrated["draft"], principal=principal)
        return hydrated

    def patch_sop_artifact(
        self,
        principal: Principal,
        artifact_id: str,
        request: SopArtifactPatchRequest,
    ) -> dict[str, Any]:
        artifact = self.get_artifact(principal, artifact_id)
        if artifact.get("capability_id") != "sop.plan":
            raise HTTPException(status_code=409, detail="only SOP artifacts can be edited here")
        current_revision = int(artifact.get("revision") or 1)
        draft = copy.deepcopy(artifact.get("draft") or {})
        tasks = [copy.deepcopy(item) for item in (draft.get("tasks") or []) if isinstance(item, dict)]
        by_id = {str(item.get("task_id") or ""): item for item in tasks}
        conflicts: list[dict[str, Any]] = []

        for update in request.task_updates:
            current = by_id.get(update.task_id)
            if current is None:
                conflicts.append({"task_id": update.task_id, "fields": ["task_deleted"], "current": None})
                continue
            submitted = {**update.task, "task_id": update.task_id}
            base = update.base_task or {}
            if request.expected_revision != current_revision:
                changed_fields = {
                    key
                    for key in submitted
                    if key != "task_id" and submitted.get(key) != base.get(key)
                }
                field_conflicts = [
                    key
                    for key in changed_fields
                    if current.get(key) != base.get(key) and current.get(key) != submitted.get(key)
                ]
                if field_conflicts:
                    conflicts.append(
                        {
                            "task_id": update.task_id,
                            "fields": field_conflicts,
                            "base": {key: base.get(key) for key in field_conflicts},
                            "current": {key: current.get(key) for key in field_conflicts},
                            "submitted": {key: submitted.get(key) for key in field_conflicts},
                        }
                    )
                    continue
                for key in changed_fields:
                    current[key] = submitted.get(key)
            else:
                current.update(submitted)

        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "field_conflict",
                    "artifact_id": artifact_id,
                    "current_revision": current_revision,
                    "conflicts": conflicts,
                    "artifact": artifact,
                },
            )

        deleted = set(request.task_deletions)
        tasks = [item for item in tasks if str(item.get("task_id") or "") not in deleted]
        for index, addition in enumerate(request.task_additions, start=len(tasks)):
            tasks.append(self._normalise_sop_task(addition, index, principal=principal))
        if request.task_order is not None:
            order = {task_id: index for index, task_id in enumerate(request.task_order)}
            fallback_order = {str(item.get("task_id") or ""): index for index, item in enumerate(tasks)}
            tasks.sort(
                key=lambda item: order.get(
                    str(item.get("task_id") or ""),
                    len(order) + fallback_order.get(str(item.get("task_id") or ""), 0),
                )
            )
        tasks = [self._normalise_sop_task(item, index, principal=principal) for index, item in enumerate(tasks)]

        allowed_fields = {"title", "goal", "gaps", "description", "scope", "start_event"}
        for key, value in request.draft_fields.items():
            if key in allowed_fields:
                draft[key] = value
        draft["tasks"] = tasks
        draft["mermaid"] = self._mermaid_from_tasks(tasks)

        self.store.put(
            "artifact_revisions",
            f"{artifact_id}:{current_revision}",
            {
                "revision_id": f"{artifact_id}:{current_revision}",
                "artifact_id": artifact_id,
                "employee_id": principal.employee_id,
                "revision": current_revision,
                "draft": artifact.get("draft") or {},
                "created_at": now_iso(),
            },
        )
        artifact.update(
            {
                "draft": draft,
                "title": str(draft.get("title") or artifact.get("title") or "SOP 초안"),
                "revision": current_revision + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("artifacts", artifact_id, artifact)
        session_id = str(artifact.get("work_session_id") or "")
        if session_id:
            session = self.store.get("work_sessions", session_id)
            if session and self._owns(principal, session):
                session.update(
                    {
                        "active_artifact_id": artifact_id,
                        "title": artifact.get("title") or session.get("title") or "새 업무",
                        "selected_task_id": request.selected_task_id or session.get("selected_task_id") or "",
                        "active_panel": "task" if request.selected_task_id else session.get("active_panel") or "result",
                        "revision": int(session.get("revision") or 1) + 1,
                        "updated_at": now_iso(),
                    }
                )
                self.store.put("work_sessions", session_id, session)
        return artifact

    def refine_task_preview(
        self,
        principal: Principal,
        artifact_id: str,
        task_id: str,
        request: TaskRefinePreviewRequest,
    ) -> dict[str, Any]:
        artifact = self.get_artifact(principal, artifact_id)
        if artifact.get("capability_id") != "sop.plan":
            raise HTTPException(status_code=409, detail="only SOP tasks can be refined")
        revision = int(artifact.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(
                status_code=409,
                detail={"status": "revision_conflict", "current_revision": revision, "artifact": artifact},
            )
        current = next(
            (item for item in (artifact.get("draft") or {}).get("tasks") or [] if item.get("task_id") == task_id),
            None,
        )
        if not current:
            raise HTTPException(status_code=404, detail="task not found")
        schema = {
            "type": "object",
            "required": [
                "name",
                "purpose",
                "execution_mode",
                "exit_criteria",
                "required_evidence",
                "completion_design",
                "outputs",
            ],
            "properties": {
                "name": {"type": "string"},
                "purpose": {"type": "string"},
                "execution_mode": {"type": "string", "enum": ["manual", "copilot", "autopilot"]},
                "exit_criteria": {"type": "array", "items": {"type": "string"}},
                "required_evidence": {"type": "array", "items": {"type": "string"}},
                "completion_design": COMPLETION_DESIGN_SCHEMA,
                "outputs": {"type": "array", "items": {"type": "string"}},
            },
        }
        try:
            refined = self.model.generate_structured(
                system=(
                    "You refine exactly one SOP Task. Preserve its business intent and return Korean structured fields. "
                    "Write completion checks and evidence labels in plain workplace Korean for a general employee. "
                    "Never expose BoI IDs, Event Type IDs, Action keys, workflow IDs, or JSON paths in labels. "
                    "Place validated technical references only in completion_design refs and bindings. "
                    "Manual and Copilot checks require a human confirmation. Autopilot checks require real system bindings; "
                    "leave bindings empty when they are unknown. Do not create or execute Actions."
                ),
                prompt=(
                    f"Instruction: {request.instruction}\n"
                    f"Current task: {json.dumps(current, ensure_ascii=False)}\n"
                    f"SOP goal: {compact_text(str((artifact.get('draft') or {}).get('goal') or ''), 1000)}"
                ),
                schema=schema,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "refine_unavailable", "message": f"{type(exc).__name__}: {exc}"},
            ) from exc
        after = self._normalise_sop_task(
            {**current, **refined, "task_id": task_id},
            0,
            principal=principal,
        )
        changed = [key for key in after if after.get(key) != current.get(key)]
        proposal_id = new_id("proposal")
        proposal = {
            "proposal_id": proposal_id,
            "employee_id": principal.employee_id,
            "artifact_id": artifact_id,
            "task_id": task_id,
            "base_revision": revision,
            "before": current,
            "after": after,
            "changed_fields": changed,
            "status": "preview",
            "created_at": now_iso(),
        }
        self.store.put("evaluations", proposal_id, proposal)
        return proposal

    def apply_task_proposal(
        self,
        principal: Principal,
        artifact_id: str,
        task_id: str,
        proposal_id: str,
        request: ProposalApplyRequest,
    ) -> dict[str, Any]:
        proposal = self._require_owned(principal, self.store.get("evaluations", proposal_id), "proposal")
        if proposal.get("artifact_id") != artifact_id or proposal.get("task_id") != task_id:
            raise HTTPException(status_code=409, detail="proposal does not match this Task")
        if proposal.get("status") != "preview":
            raise HTTPException(status_code=409, detail="proposal was already applied")
        result = self.patch_sop_artifact(
            principal,
            artifact_id,
            SopArtifactPatchRequest(
                expected_revision=request.expected_revision,
                task_updates=[
                    {
                        "task_id": task_id,
                        "base_task": proposal.get("before") or {},
                        "task": proposal.get("after") or {},
                    }
                ],
                selected_task_id=task_id,
            ),
        )
        proposal.update({"status": "applied", "applied_at": now_iso()})
        self.store.put("evaluations", proposal_id, proposal)
        return result

    def get_task_proposal(self, principal: Principal, proposal_id: str) -> dict[str, Any]:
        return self._require_owned(principal, self.store.get("evaluations", proposal_id), "proposal")

    @staticmethod
    def _helper_template(template_id: str) -> dict[str, Any]:
        templates = {
            "search": {
                "name": "자료 찾기 도우미",
                "instructions": "질문과 관련된 검토된 BoI 자료를 먼저 찾고, 근거 링크와 함께 간결하게 답합니다.",
                "capability_ids": ["knowledge.search", "cases.similar"],
            },
            "sop": {
                "name": "SOP 설계 도우미",
                "instructions": "업무 목표를 Task로 나누고 각 Task의 목적, 종료 기준, 필요한 근거를 구체화합니다.",
                "capability_ids": ["knowledge.search", "sop.plan", "action.plan", "business_event.plan"],
            },
            "evidence": {
                "name": "근거 검증 도우미",
                "instructions": "주장의 근거를 BoI Wiki와 유사 사례에서 확인하고, 부족한 근거와 다음 확인 항목을 구분합니다.",
                "capability_ids": ["knowledge.search", "cases.similar", "knowledge.draft"],
            },
            "blank": {"name": "새 BoI Agent", "instructions": "", "capability_ids": ["knowledge.search"]},
        }
        return copy.deepcopy(templates.get(template_id, templates["blank"]))

    def create_helper_draft(self, principal: Principal, request: HelperDraftCreateRequest) -> dict[str, Any]:
        seed = self._helper_template(request.template_id)
        draft_id = new_id("helper_draft")
        created_at = now_iso()
        payload = {
            "draft_id": draft_id,
            "employee_id": principal.employee_id,
            "name": compact_text(request.name, 120) or seed["name"],
            "instructions": request.instructions.strip() or seed["instructions"],
            "capability_ids": seed["capability_ids"],
            "source_scopes": ["boi", "sop", "event", "action", "history"],
            "skill_ids": [],
            "connector_refs": [],
            "surfaces": ["agent"],
            "visibility": "private",
            "status": "draft",
            "revision": 1,
            "created_at": created_at,
            "updated_at": created_at,
        }
        return self.store.put("helper_drafts", draft_id, payload)

    def import_legacy_helper_draft(
        self,
        principal: Principal,
        request: LegacyHelperImportRequest,
    ) -> dict[str, Any]:
        legacy_id = request.legacy_draft_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", legacy_id):
            raise HTTPException(status_code=400, detail="invalid legacy draft id")
        for existing in self.store.list("helper_drafts", employee_id=principal.employee_id, limit=500):
            if existing.get("legacy_source_id") == legacy_id:
                return existing
        path = self.settings.runtime_root / "agents" / "drafts" / f"{legacy_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="legacy helper draft not found")
        try:
            legacy = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="legacy helper draft is unreadable") from exc
        owner = str(legacy.get("created_by") or principal.employee_id)
        if owner != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="legacy helper draft belongs to another employee")
        capability_map = {
            "search": "knowledge.search",
            "summarize": "knowledge.search",
            "validate": "cases.similar",
            "diagram": "sop.plan",
            "draft": "knowledge.draft",
            "request_action": "action.plan",
            "sop": "sop.plan",
            "event": "business_event.plan",
        }
        raw_capabilities = legacy.get("capabilities") if isinstance(legacy.get("capabilities"), list) else []
        capability_ids = []
        known = {item.capability_id for item in self.registry.all()}
        for value in raw_capabilities:
            candidate = str(value or "")
            mapped = capability_map.get(candidate, candidate)
            if mapped in known and mapped not in capability_ids:
                capability_ids.append(mapped)
        if "knowledge.search" not in capability_ids:
            capability_ids.insert(0, "knowledge.search")
        references = legacy.get("reference_sources") if isinstance(legacy.get("reference_sources"), list) else []
        source_map = {
            "boi_docs": "boi",
            "sops": "sop",
            "events_actions": "event",
            "similar_cases": "history",
        }
        source_scopes = list(dict.fromkeys(source_map.get(str(value), str(value)) for value in references if value))
        connectors = []
        for value in [*(legacy.get("connection_presets") or []), *(legacy.get("mcp_servers") or [])]:
            clean = str(value or "").strip()
            if clean and clean not in connectors:
                connectors.append(clean)
        draft = self.create_helper_draft(
            principal,
            HelperDraftCreateRequest(
                template_id="blank",
                name=str(legacy.get("title") or "기존 BoI Agent"),
                instructions=str(legacy.get("prompt") or ""),
            ),
        )
        draft.update(
            {
                "capability_ids": capability_ids,
                "source_scopes": source_scopes or ["boi", "sop", "event", "action", "history"],
                "skill_ids": [str(value) for value in (legacy.get("skills") or []) if str(value).strip()],
                "connector_refs": connectors,
                "surfaces": [str(value) for value in (legacy.get("helper_surfaces") or ["agent"]) if str(value).strip()],
                "legacy_source_id": legacy_id,
                "legacy_imported_at": now_iso(),
            }
        )
        return self.store.put("helper_drafts", str(draft["draft_id"]), draft)

    def get_helper_draft(self, principal: Principal, draft_id: str) -> dict[str, Any]:
        return self._require_owned(principal, self.store.get("helper_drafts", draft_id), "helper draft")

    def delete_helper_draft(self, principal: Principal, draft_id: str) -> dict[str, Any]:
        draft = self.get_helper_draft(principal, draft_id)
        if draft.get("status") == "activated":
            raise HTTPException(status_code=409, detail="activated helpers must be archived from the helper catalog")
        self.store.delete("helper_drafts", draft_id)
        return {"draft_id": draft_id, "status": "deleted"}

    def patch_helper_draft(
        self,
        principal: Principal,
        draft_id: str,
        request: HelperDraftPatchRequest,
    ) -> dict[str, Any]:
        draft = self.get_helper_draft(principal, draft_id)
        revision = int(draft.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(
                status_code=409,
                detail={"status": "revision_conflict", "current_revision": revision, "helper": draft},
            )
        values = request.model_dump(exclude_unset=True)
        values.pop("expected_revision", None)
        draft.update(values)
        draft.update({"revision": revision + 1, "updated_at": now_iso()})
        return self.store.put("helper_drafts", draft_id, draft)

    def _skill_contracts(
        self,
        principal: Principal,
        skill_ids: list[str],
        *,
        require_active: bool = False,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        authoritative = {
            record.record_id: record
            for record in self.repository.authoritative_records(principal)
            if record.kind == "skill"
        }
        contracts: list[dict[str, Any]] = []
        missing: list[str] = []
        for skill_id in list(dict.fromkeys(str(item) for item in skill_ids if str(item).strip())):
            stored = self.store.get("skills", skill_id)
            if stored and self._owns(principal, stored) and (not require_active or stored.get("status") == "active"):
                contracts.append(
                    {
                        "skill_id": skill_id,
                        "title": str(stored.get("title") or skill_id),
                        "description": str(stored.get("description") or ""),
                        "input_schema": stored.get("input_schema") or {},
                        "output_schema": stored.get("output_schema") or {},
                        "permissions": stored.get("permissions") or [],
                        "available_actions": stored.get("available_actions") or [],
                        "authority": "private_verified",
                    }
                )
                continue
            record = authoritative.get(skill_id)
            if record:
                contracts.append(
                    {
                        "skill_id": skill_id,
                        "title": record.title,
                        "description": record.description,
                        "input_schema": record.metadata.get("input_schema") or {},
                        "output_schema": record.metadata.get("output_schema") or {},
                        "permissions": record.metadata.get("permissions") or [],
                        "available_actions": record.metadata.get("available_actions") or [],
                        "authority": record.authority,
                    }
                )
                continue
            missing.append(skill_id)
        return contracts, missing

    @staticmethod
    def _schema_required_missing(schema: dict[str, Any], value: dict[str, Any]) -> list[str]:
        return [str(field) for field in schema.get("required") or [] if field not in value]

    def test_skill_artifact(
        self,
        principal: Principal,
        artifact_id: str,
        request: SkillArtifactTestRequest,
    ) -> dict[str, Any]:
        artifact = self.get_artifact(principal, artifact_id)
        if artifact.get("capability_id") != "skill.plan":
            raise HTTPException(status_code=409, detail="only Skill draft artifacts can be tested")
        revision = int(artifact.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "artifact": artifact})
        draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
        input_schema = draft.get("input_schema") if isinstance(draft.get("input_schema"), dict) else {}
        default_test = next((item for item in draft.get("tests") or [] if isinstance(item, dict)), {})
        sample_input = copy.deepcopy(default_test.get("sample_input") if isinstance(default_test.get("sample_input"), dict) else {})
        sample_input.update(request.sample_input)
        if request.scenario:
            sample_input["user_scenario"] = request.scenario
        output_schema = copy.deepcopy(draft.get("output_schema") if isinstance(draft.get("output_schema"), dict) else {})
        if output_schema.get("type") != "object":
            output_schema = {"type": "object", "properties": {}}
        output_schema.setdefault("properties", {})
        if not output_schema["properties"]:
            output_schema["properties"] = {
                "result": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            }
            output_schema["required"] = ["result", "evidence_refs"]
        expected_contains = [compact_text(item, 240) for item in request.expected_contains if str(item).strip()]
        if not expected_contains:
            expected_contains = [
                compact_text(str(value), 240)
                for test in draft.get("tests") or []
                if isinstance(test, dict)
                for value in (test.get("expected_contains") or [test.get("expected")])
                if str(value or "").strip()
            ][:10]
        query = " ".join(
            [
                str(draft.get("title") or ""),
                str(draft.get("description") or ""),
                json.dumps(sample_input, ensure_ascii=False, default=str),
            ]
        ).strip()
        evidence = self.search.search(query, principal, limit=6, include_history=False).items if query else []
        retrieved_ids = {item.evidence_id for item in evidence}
        generated: dict[str, Any] = {}
        generation_error = ""
        try:
            generated = self.model.generate_structured(
                system=(
                    "You are testing one private BoI Skill draft. Follow only the supplied Skill contract and evidence. "
                    "Do not mutate production, call external systems, or invent evidence IDs. Return only the requested JSON output."
                ),
                prompt=json.dumps(
                    {
                        "skill": {
                            "title": draft.get("title"),
                            "description": draft.get("description"),
                            "available_actions": draft.get("available_actions") or [],
                        },
                        "sample_input": sample_input,
                        "evidence": [
                            {"evidence_id": item.evidence_id, "title": item.title, "summary": compact_text(item.summary, 600)}
                            for item in evidence
                        ],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                schema=output_schema,
            )
        except Exception as exc:
            generation_error = f"{type(exc).__name__}: {exc}"
        missing_input = self._schema_required_missing(input_schema, sample_input)
        missing_output = self._schema_required_missing(output_schema, generated)
        output_text = json.dumps(generated, ensure_ascii=False, default=str).lower()
        missing_expectations = [item for item in expected_contains if item.lower() not in output_text]
        output_evidence = {
            str(item)
            for item in generated.get("evidence_refs") or []
            if isinstance(generated, dict) and str(item).strip()
        }
        unknown_evidence = sorted(output_evidence - retrieved_ids)
        allowed_actions = {
            record.record_id
            for record in self.repository.authoritative_records(principal)
            if record.kind == "action"
        }
        for record in self.repository.authoritative_records(principal):
            if record.kind == "action" and record.metadata.get("action_key"):
                allowed_actions.add(str(record.metadata["action_key"]))
        unknown_actions = [
            str(item)
            for item in draft.get("available_actions") or []
            if str(item).strip() and str(item) not in allowed_actions
        ]
        elevated_permissions = [
            str(item)
            for item in draft.get("permissions") or []
            if str(item) == "boi.admin" and not principal.is_admin
        ]
        checks = [
            {"check_id": "skill.input", "passed": not missing_input, "message": "" if not missing_input else "필수 시험 입력이 없습니다: " + ", ".join(missing_input)},
            {"check_id": "skill.output", "passed": not generation_error and not missing_output, "message": generation_error or ("결과 필드가 없습니다: " + ", ".join(missing_output) if missing_output else "")},
            {"check_id": "skill.expectation", "passed": not missing_expectations, "message": "" if not missing_expectations else "기대 결과에서 확인되지 않았습니다: " + ", ".join(missing_expectations)},
            {"check_id": "skill.evidence", "passed": not unknown_evidence, "message": "" if not unknown_evidence else "검색하지 않은 근거를 결과가 참조했습니다."},
            {"check_id": "skill.actions", "passed": not unknown_actions, "message": "" if not unknown_actions else "등록되지 않은 Action 연결이 있습니다: " + ", ".join(unknown_actions)},
            {"check_id": "skill.permissions", "passed": not elevated_permissions, "message": "" if not elevated_permissions else "현재 사용자가 부여할 수 없는 권한이 있습니다."},
        ]
        preliminary_status = "passed" if all(item["passed"] for item in checks) else "failed"
        test_id = new_id("skilltest")
        context = WorkContextPack(
            context_id=new_id("context"),
            employee_id=principal.employee_id,
            capability_id="skill.plan",
            goal=str(draft.get("description") or draft.get("title") or "Skill 시험"),
            task_mode=TaskMode.copilot,
            evidence_refs=evidence,
            context_manifest=ContextManifest(
                selected_refs=[item.evidence_id for item in evidence[:12]],
                raw_content_in_prompt=False,
            ),
        )
        harness = self.harnesses.evaluate(
            "skill.authoring",
            phase="test",
            intent=WorkIntent(
                goal=context.goal,
                asset_kind=WorkAssetKind.skill,
                operation=WorkOperation.test,
                target_ref=artifact_id,
                confidence=1.0,
            ),
            context=context,
            artifact={"draft": draft, "test_result": {"status": preliminary_status}},
            task_mode=TaskMode.copilot,
        )
        status = "passed" if preliminary_status == "passed" and harness.status != "blocked" else "failed"
        result = {
            "test_id": test_id,
            "artifact_id": artifact_id,
            "employee_id": principal.employee_id,
            "tested_revision": revision,
            "status": status,
            "sample_input": sample_input,
            "scenario": request.scenario,
            "expected_contains": expected_contains,
            "output": generated,
            "evidence_refs": sorted(output_evidence),
            "checks": checks,
            "harness": harness.model_dump(mode="json"),
            "created_at": now_iso(),
        }
        self.store.put("skill_test_runs", test_id, result)
        artifact["verification"] = {
            "status": status,
            "latest_test_id": test_id,
            "tested_revision": revision,
            "tested_at": now_iso(),
        }
        artifact["updated_at"] = now_iso()
        self.store.put("artifacts", artifact_id, artifact)
        return result

    def activate_skill_artifact(
        self,
        principal: Principal,
        artifact_id: str,
        request: SkillArtifactActivateRequest,
    ) -> dict[str, Any]:
        artifact = self.get_artifact(principal, artifact_id)
        if artifact.get("capability_id") != "skill.plan":
            raise HTTPException(status_code=409, detail="only Skill draft artifacts can be activated")
        revision = int(artifact.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "artifact": artifact})
        verification = artifact.get("verification") if isinstance(artifact.get("verification"), dict) else {}
        if verification.get("status") != "passed" or int(verification.get("tested_revision") or 0) != revision:
            raise HTTPException(status_code=422, detail="현재 Skill 초안을 먼저 시험하고 통과해야 합니다.")
        draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
        slug = re.sub(r"[^a-z0-9._-]+", "-", str(draft.get("skill_id") or draft.get("title") or "skill").lower()).strip("-")
        skill_id = f"private:{principal.employee_id}:{slug or artifact_id}"
        skill = {
            "skill_id": skill_id,
            "employee_id": principal.employee_id,
            "title": str(draft.get("title") or artifact.get("title") or "업무 능력"),
            "description": str(draft.get("description") or ""),
            "input_schema": draft.get("input_schema") or {},
            "output_schema": draft.get("output_schema") or {},
            "permissions": draft.get("permissions") or [],
            "available_actions": draft.get("available_actions") or [],
            "source_artifact_id": artifact_id,
            "source_revision": revision,
            "verification": verification,
            "visibility": "private",
            "status": "active",
            "activated_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("skills", skill_id, skill)
        artifact["skill_activation"] = {"skill_id": skill_id, "status": "active", "activated_at": now_iso()}
        artifact["updated_at"] = now_iso()
        self.store.put("artifacts", artifact_id, artifact)
        return skill

    def helper_preview_turn(
        self,
        principal: Principal,
        draft_id: str,
        request: HelperPreviewTurnRequest,
    ) -> AgentTurnResponse:
        helper = self.get_helper_draft(principal, draft_id)
        skill_contracts, missing_skills = self._skill_contracts(
            principal,
            list(helper.get("skill_ids") or []),
            require_active=False,
        )
        if missing_skills:
            raise HTTPException(status_code=422, detail={"status": "skill_unavailable", "skill_ids": missing_skills})
        return self.run_turn(
            principal,
            AgentTurnRequest(
                question=request.question,
                work_session_id=request.work_session_id,
                page_ref="/helpers/new",
                helper_id=draft_id,
                input_delta={
                    "_helper_instructions": helper.get("instructions") or "",
                    "_helper_source_scopes": helper.get("source_scopes") or [],
                    "_helper_skill_ids": helper.get("skill_ids") or [],
                    "_helper_skills": skill_contracts,
                    "preview_only": True,
                },
            ),
        )

    def activate_helper(
        self,
        principal: Principal,
        draft_id: str,
        request: HelperActivateRequest,
    ) -> dict[str, Any]:
        draft = self.get_helper_draft(principal, draft_id)
        revision = int(draft.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "helper": draft})
        if not str(draft.get("name") or "").strip() or not str(draft.get("instructions") or "").strip():
            raise HTTPException(status_code=422, detail="name and instructions are required")
        _, missing_skills = self._skill_contracts(
            principal,
            list(draft.get("skill_ids") or []),
            require_active=True,
        )
        if missing_skills:
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "skill_verification_required",
                    "message": "연결한 업무 능력을 먼저 시험하고 사용 가능 상태로 만들어주세요.",
                    "skill_ids": missing_skills,
                },
            )
        helper_id = new_id("helper")
        helper = {
            **draft,
            "helper_id": helper_id,
            "source_draft_id": draft_id,
            "status": "active",
            "revision": 1,
            "activated_at": now_iso(),
        }
        helper.pop("draft_id", None)
        self.store.put("helpers", helper_id, helper)
        draft.update({"status": "activated", "helper_id": helper_id, "revision": revision + 1, "updated_at": now_iso()})
        self.store.put("helper_drafts", draft_id, draft)
        return helper

    def list_helpers(self, principal: Principal, *, limit: int = 50) -> dict[str, Any]:
        items = self.store.list("helpers", employee_id=principal.employee_id, limit=max(1, min(limit, 100)))
        return {"count": len(items), "items": items}

    def get_helper(self, principal: Principal, helper_id: str) -> dict[str, Any]:
        helper = self.store.get("helpers", helper_id) or self.store.get("helper_drafts", helper_id)
        return self._require_owned(principal, helper, "helper")

    def list_skills(self, principal: Principal, *, query: str = "", limit: int = 50) -> dict[str, Any]:
        clean_query = query.strip().lower()
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for skill in self.store.list("skills", employee_id=principal.employee_id, limit=500):
            if skill.get("status") != "active":
                continue
            skill_id = str(skill.get("skill_id") or "")
            haystack = f"{skill.get('title') or ''} {skill.get('description') or ''}".lower()
            if not skill_id or (clean_query and clean_query not in haystack):
                continue
            seen.add(skill_id)
            items.append(
                {
                    "skill_id": skill_id,
                    "title": str(skill.get("title") or skill_id),
                    "description": str(skill.get("description") or ""),
                    "url": f"/agent?artifact={skill.get('source_artifact_id') or ''}",
                    "source": "private_verified",
                    "authority": "private_verified",
                    "verification": skill.get("verification") or {},
                }
            )
        for record in self.repository.authoritative_records(principal):
            if record.kind != "skill" or record.record_id in seen:
                continue
            haystack = f"{record.title} {record.description} {record.text[:2000]}".lower()
            if clean_query and clean_query not in haystack:
                continue
            seen.add(record.record_id)
            items.append(
                {
                    "skill_id": record.record_id,
                    "title": record.title,
                    "description": record.description,
                    "url": record.url,
                    "source": record.source,
                    "authority": record.authority,
                }
            )
        items.sort(key=lambda item: (item["title"].lower(), item["skill_id"]))
        return {"count": len(items[:limit]), "items": items[:limit]}

    def knowledge_graph(self, principal: Principal, *, query: str = "", limit: int = 120) -> dict[str, Any]:
        records = self.repository.authoritative_records(principal)
        seed_ids: list[str]
        if query:
            matched = self.search.search(query, principal, limit=min(limit, 20)).items
            seed_ids = [item.evidence_id for item in matched[:8]]
            ids = set(seed_ids)
            records = [item for item in records if item.record_id in ids]
        else:
            seed_ids = [item.record_id for item in records[:12]]
        graph = self.store.ontology_neighbors(
            seed_ids,
            depth=2,
            limit=max(1, min(limit, 300)),
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        if graph.get("nodes"):
            nodes = [
                {
                    "id": item.get("node_id"),
                    "kind": item.get("node_type") or "knowledge",
                    "label": (item.get("payload") or {}).get("title")
                    or (item.get("payload") or {}).get("label")
                    or item.get("node_id"),
                    "url": (item.get("payload") or {}).get("url") or "",
                    "authority": (item.get("payload") or {}).get("authority") or "",
                    "metadata": item.get("payload") or {},
                }
                for item in graph.get("nodes") or []
            ]
            edges = [
                {
                    "id": item.get("edge_id"),
                    "source": item.get("source_id"),
                    "target": item.get("target_id"),
                    "relation": item.get("relation") or "related",
                    "depth": item.get("depth") or 1,
                }
                for item in graph.get("edges") or []
            ]
            return {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "nodes": nodes,
                "edges": edges,
                "mode": "stored_ontology",
                "seed_ids": seed_ids,
            }
        records = records[: max(1, min(limit, 300))]
        record_ids = {item.record_id for item in records}
        nodes = [
            {
                "id": item.record_id,
                "kind": item.kind,
                "label": item.title,
                "url": item.url,
                "authority": item.authority,
            }
            for item in records
        ]
        edges: list[dict[str, str]] = []
        relation_fields = {
            "sop_ref": "uses_sop",
            "sop_refs": "uses_sop",
            "action_refs": "uses_action",
            "event_type": "uses_event",
            "event_types": "uses_event",
            "related": "related",
            "source_refs": "evidence",
        }
        for record in records:
            for field, relation in relation_fields.items():
                raw = record.metadata.get(field)
                values = raw if isinstance(raw, list) else [raw] if raw else []
                for value in values:
                    if isinstance(value, dict):
                        target = str(value.get("ref") or value.get("boi_id") or "")
                    else:
                        target = str(value or "")
                    if not target:
                        continue
                    candidates = [target, f"action:{target}", f"event:{target}", f"workflow:{target}"]
                    resolved = next((candidate for candidate in candidates if candidate in record_ids), "")
                    if resolved:
                        edges.append(
                            {
                                "id": hashlib.sha1(f"{record.record_id}:{relation}:{resolved}".encode()).hexdigest()[:16],
                                "source": record.record_id,
                                "target": resolved,
                                "relation": relation,
                            }
                        )
        return {"node_count": len(nodes), "edge_count": len(edges), "nodes": nodes, "edges": edges}

    def harness_acceptance(self, principal: Principal) -> dict[str, Any]:
        readiness = self.readiness(principal, probe_model=True)
        mcp_status = self._mcp_v2_status()
        home_offers = self.create_offers(principal, OfferRequest(page_ref="/", include_unavailable=True))
        current_ids = {item.record_id for item in self.repository.current_work(principal, limit=500)}
        seed_ids = {
            item.record_id
            for item in self.repository.history_records(principal, include_seed=True)
            if item.source == "history_seed"
        }
        capability_ids = {item.capability_id for item in self.registry.all()}
        expected = {
            "knowledge.search",
            "work.inbox",
            "task.work",
            "cases.similar",
            "business_event.plan",
            "sop.plan",
            "action.plan",
            "skill.plan",
            "knowledge.draft",
            "work_routine.plan",
            "deep.research",
        }
        core_checks = {
            "content_ready": bool(readiness["dependencies"]["content"]),
            "capability_catalog_exact": capability_ids == expected,
            "home_offers_are_typed": bool(home_offers)
            and all(item.offer_id.startswith("offer_") and item.capability_id in expected for item in home_offers),
            "home_not_misclassified_as_document": all(
                item.capability_id not in {"knowledge.draft", "sop.plan", "business_event.plan"} for item in home_offers
            ),
            "history_seed_excluded_from_current_work": not bool(current_ids & seed_ids),
            "compact_response_budget": self.settings.response_budget_bytes <= 8192,
            "pat_available": bool(readiness["dependencies"]["pat"]),
        }
        full_checks = {
            **core_checks,
            "postgres_pgvector_ready": bool(readiness["dependencies"]["postgres"]),
            "generation_model_ready": bool(readiness["dependencies"]["model"]),
            "real_embedding_ready": bool(readiness["dependencies"]["embedding"]),
            "search_index_fresh": bool(readiness["dependencies"]["search_index"]),
            "deep_worker_ready": bool(readiness["dependencies"]["deep_worker"]),
            "mcp_v2_ready": bool(mcp_status["ready"]),
            "production_pat_secret": bool(self.pats.production_ready),
        }
        return {
            "version": "2.0",
            "core_accepted": all(core_checks.values()),
            "full_accepted": all(full_checks.values()),
            "core_checks": core_checks,
            "full_checks": full_checks,
            "readiness": readiness,
            "mcp": mcp_status,
        }


def build_agent_v2_service(
    settings: AgentV2Settings,
    *,
    identity_provider: Callable[[str], Principal] | None = None,
    domain_services: DomainServiceGateway | None = None,
    routine_target_executor: Callable[[dict[str, Any], WorkRoutineTriggerRequest, Principal], dict[str, Any]] | None = None,
    page_context_provider: Callable[[str, str], dict[str, Any]] | None = None,
    directory_provider: Callable[[], list[Principal]] | None = None,
) -> AgentV2Service:
    return AgentV2Service(
        settings,
        identity_provider=identity_provider,
        domain_services=domain_services,
        routine_target_executor=routine_target_executor,
        page_context_provider=page_context_provider,
        directory_provider=directory_provider,
    )
