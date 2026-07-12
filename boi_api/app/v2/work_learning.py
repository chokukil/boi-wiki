from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException

from .harness import HarnessRegistry
from .models import (
    CapabilityDefinition,
    ContextAnchor,
    ContextManifest,
    EvidenceRef,
    HarnessResult,
    KnowledgeCandidatePatchRequest,
    KnowledgeCandidatePromoteRequest,
    KnowledgeCandidateRef,
    LoopKind,
    LoopPolicy,
    LoopTriggerKind,
    LoopDelta,
    Principal,
    RiskLevel,
    TaskCompletionDesign,
    TaskMode,
    WorkAssetKind,
    WorkContextPack,
    WorkIntent,
    WorkOperation,
    WorkRunContinueRequest,
)
from .repository import KnowledgeRepository
from .search import HybridSearchService
from .store import AgentV2Store, now_iso


def _id(prefix: str, value: str = "") -> str:
    digest = hashlib.sha256((value or f"{prefix}:{now_iso()}").encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _compact(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _fingerprint(delta: LoopDelta) -> str:
    if delta.fingerprint:
        return delta.fingerprint
    value = json.dumps(
        {
            "kind": delta.kind,
            "summary": _compact(delta.summary, 600).lower(),
            "ref": delta.ref,
            "metadata": delta.metadata,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class WorkIntentEngine:
    @classmethod
    def infer(
        cls,
        question: str,
        *,
        capability_id: str,
        page_ref: str,
        task_ref: str,
        target_ref: str = "",
        operation: WorkOperation | str | None = None,
        scope: str = "auto",
    ) -> WorkIntent:
        draft_capabilities = {"business_event.plan", "sop.plan", "action.plan", "skill.plan", "knowledge.draft"}
        capability_assets = {
            "business_event.plan": WorkAssetKind.business_event,
            "sop.plan": WorkAssetKind.sop,
            "action.plan": WorkAssetKind.action,
            "skill.plan": WorkAssetKind.skill,
            "knowledge.draft": WorkAssetKind.knowledge,
            "work.inbox": WorkAssetKind.runtime,
            "cases.similar": WorkAssetKind.evidence,
        }
        asset = WorkAssetKind.task if task_ref else capability_assets.get(capability_id, WorkAssetKind.knowledge)
        if isinstance(operation, WorkOperation):
            selected_operation = operation
        else:
            try:
                selected_operation = WorkOperation(str(operation or ""))
            except ValueError:
                selected_operation = WorkOperation.create if capability_id in draft_capabilities else WorkOperation.understand
        risk = (
            RiskLevel.high
            if selected_operation in {WorkOperation.run, WorkOperation.promote, WorkOperation.complete}
            else RiskLevel.medium
            if selected_operation in {WorkOperation.connect, WorkOperation.test}
            else RiskLevel.low
        )
        outcome = {
            WorkOperation.create: "draft",
            WorkOperation.refine: "proposal",
            WorkOperation.connect: "proposal" if capability_id in draft_capabilities else "answer",
            WorkOperation.validate: "validation",
            WorkOperation.test: "preview",
            WorkOperation.run: "run_result",
            WorkOperation.complete: "completion_record",
            WorkOperation.capture: "knowledge_candidate",
            WorkOperation.promote: "promotion_request",
        }.get(selected_operation, "answer")
        operation_plan = [WorkOperation.understand]
        if selected_operation != WorkOperation.understand:
            operation_plan.append(selected_operation)
        if selected_operation in {WorkOperation.create, WorkOperation.refine, WorkOperation.connect}:
            operation_plan.append(WorkOperation.validate)
        if selected_operation == WorkOperation.run:
            operation_plan.extend([WorkOperation.validate, WorkOperation.observe])
        if selected_operation == WorkOperation.complete:
            operation_plan.extend([WorkOperation.validate, WorkOperation.capture])
        operation_plan = list(dict.fromkeys(operation_plan))
        canonical_order = {
            item: index
            for index, item in enumerate(
                (
                    WorkOperation.understand,
                    WorkOperation.compare,
                    WorkOperation.create,
                    WorkOperation.refine,
                    WorkOperation.connect,
                    WorkOperation.validate,
                    WorkOperation.test,
                    WorkOperation.run,
                    WorkOperation.observe,
                    WorkOperation.complete,
                    WorkOperation.capture,
                    WorkOperation.promote,
                )
            )
        }
        operation_plan.sort(key=lambda item: canonical_order[item])
        return WorkIntent(
            goal=question,
            asset_kind=asset,
            operation=selected_operation,
            operation_plan=operation_plan,
            target_ref=task_ref or target_ref,
            scope=scope if scope in {"auto", "current", "wiki", "selected"} else "auto",  # type: ignore[arg-type]
            desired_outcome=outcome,
            risk=risk,
            confidence=1.0,
        )


class ContextCompiler:
    def __init__(
        self,
        repository: KnowledgeRepository,
        store: AgentV2Store,
        page_context_provider: Callable[[str, str], dict[str, Any]] | None = None,
    ):
        self.repository = repository
        self.store = store
        self.page_context_provider = page_context_provider

    @staticmethod
    def _canonical_url(value: str) -> str:
        parsed = urlsplit(str(value or ""))
        return unquote(parsed.path or "/").rstrip("/") or "/"

    def page_anchor(self, principal: Principal, page_ref: str) -> ContextAnchor | None:
        path = self._canonical_url(page_ref)
        records = self.repository.authoritative_records(principal, include_drafts=True)
        if self.page_context_provider is not None:
            try:
                page_context = self.page_context_provider(page_ref, principal.employee_id) or {}
            except Exception:
                page_context = {}
            if not page_context.get("resolved"):
                return ContextAnchor(
                    ref=path,
                    kind=str(page_context.get("page_kind") or "page"),
                    title="",
                    url=page_ref,
                    source="page",
                    resolved=False,
                    context_resolution=(
                        "ontology_only"
                        if page_context.get("context_resolution") == "ontology_search_only"
                        else "none"
                    ),
                )
            candidate_refs = [
                str(page_context.get("boi_id") or ""),
                str(page_context.get("source_ref") or ""),
            ]
            candidate_urls = [str(page_context.get("url") or ""), page_ref]
            record = next(
                (
                    item
                    for item in records
                    if item.record_id in candidate_refs
                    or any(self._canonical_url(item.url) == self._canonical_url(url) for url in candidate_urls if url)
                ),
                None,
            )
            title = str(page_context.get("title") or (record.title if record else "") or "현재 화면")
            revision_seed = (
                f"{record.record_id}:{record.timestamp}:{record.status}"
                if record
                else json.dumps(page_context, ensure_ascii=False, sort_keys=True, default=str)
            )
            return ContextAnchor(
                ref=(record.record_id if record else candidate_refs[0] or path),
                kind=(record.kind if record else str(page_context.get("page_kind") or "page")),
                title=title,
                url=str(page_context.get("url") or page_ref),
                revision=hashlib.sha256(revision_seed.encode()).hexdigest()[:16],
                source="page",
                resolved=True,
                context_resolution="route",
            )
        record = None
        if path.startswith("/docs/"):
            ref = path.removeprefix("/docs/")
            record = next((item for item in records if item.record_id == ref), None)
        if record is None:
            record = next((item for item in records if self._canonical_url(item.url) == path), None)
        if record is None:
            return ContextAnchor(
                ref=path,
                kind="page",
                title="",
                url=page_ref,
                source="page",
                resolved=False,
                context_resolution="none",
            )
        revision = hashlib.sha256(f"{record.record_id}:{record.timestamp}:{record.status}".encode()).hexdigest()[:16]
        return ContextAnchor(
            ref=record.record_id,
            kind=record.kind,
            title=record.title,
            url=record.url,
            revision=revision,
            source="page",
            resolved=True,
            context_resolution="ontology_only",
        )

    def goal_anchor(self, principal: Principal, session: dict[str, Any], task_ref: str) -> ContextAnchor | None:
        if task_ref:
            return ContextAnchor(ref=task_ref, kind="task", title="진행 중 Task", source="task", resolved=True)
        artifact_id = str(session.get("active_artifact_id") or "")
        if not artifact_id:
            return None
        artifact = self.store.get("artifacts", artifact_id) or {}
        if artifact.get("employee_id") != principal.employee_id and not principal.is_admin:
            return None
        return ContextAnchor(
            ref=artifact_id,
            kind=str(artifact.get("capability_id") or "artifact"),
            title=str(artifact.get("title") or "진행 중 결과"),
            url=f"/agent?session={session.get('session_id') or ''}&artifact={artifact_id}",
            revision=str(artifact.get("revision") or 1),
            source="goal",
            resolved=True,
        )

    def compile(
        self,
        *,
        principal: Principal,
        definition: CapabilityDefinition,
        goal: str,
        page_ref: str,
        task_ref: str,
        task_mode: TaskMode,
        task: dict[str, Any],
        evidence: list[EvidenceRef],
        session: dict[str, Any],
        source_set: dict[str, Any],
        external_ai_summary: str,
        external_refs: list[str],
    ) -> WorkContextPack:
        page_anchor = self.page_anchor(principal, page_ref)
        goal_anchor = self.goal_anchor(principal, session, task_ref)
        selected = evidence[:12]
        task_exit = task.get("exit_criteria") or task.get("completion_conditions") or definition.completion_criteria
        required = task.get("required_evidence") or task.get("evidence_requirements") or []
        task_exit = [task_exit] if isinstance(task_exit, str) else list(task_exit or [])
        required = [required] if isinstance(required, str) else list(required or [])
        searchable = " ".join(
            f"{item.evidence_id} {item.title} {item.summary}".lower() for item in selected
        )
        missing = [item for item in required if str(item).lower() not in searchable]
        chunk_refs = [
            str(item.metadata.get("best_chunk", {}).get("chunk_id") or "")
            for item in selected
            if isinstance(item.metadata.get("best_chunk"), dict) and item.metadata.get("best_chunk", {}).get("chunk_id")
        ][:24]
        metadata: dict[str, Any] = {}
        if page_anchor and page_anchor.resolved:
            record = next(
                (item for item in self.repository.authoritative_records(principal, include_drafts=True) if item.record_id == page_anchor.ref),
                None,
            )
            if record:
                for key in ("workflow", "event_type", "action_key", "source_refs", "owner", "status", "tags"):
                    if record.metadata.get(key) not in (None, "", [], {}):
                        metadata[key] = record.metadata.get(key)
        playbook_items = [
            item for item in self.store.list("context_playbook_items", employee_id=principal.employee_id, limit=500)
            if str(item.get("status") or "") in {"provisional", "active"}
            and (
                not (item.get("applies_to") or {}).get("capability_ids")
                or definition.capability_id in (item.get("applies_to") or {}).get("capability_ids", [])
            )
        ][:6]
        if playbook_items:
            metadata["context_playbook"] = [
                {
                    "item_id": item.get("item_id"),
                    "description": item.get("description"),
                    "conditions": item.get("conditions") or [],
                    "source_refs": item.get("source_refs") or [],
                    "status": item.get("status"),
                }
                for item in playbook_items
            ]
        manifest = ContextManifest(
            selected_refs=[item.evidence_id for item in selected],
            excluded_refs=[str(item) for item in source_set.get("excluded") or []],
            exclusion_reasons={str(item): "user_excluded" for item in source_set.get("excluded") or []},
            pinned_refs=[str(item) for item in source_set.get("pinned") or []],
            chunk_refs=chunk_refs,
            external_refs=[_compact(item, 500) for item in external_refs],
            source_revision=self.repository.source_signature(),
            token_budget=12000,
            raw_content_in_prompt=False,
            provenance={
                item.evidence_id: {
                    "source": item.source,
                    "authority": item.authority,
                    "url": item.url,
                }
                for item in selected
            },
        )
        completion = task.get("completion_design")
        return WorkContextPack(
            context_id=_id("ctx"),
            employee_id=principal.employee_id,
            capability_id=definition.capability_id,
            goal=goal,
            page_ref=page_ref,
            task_ref=task_ref,
            workflow_ref=str(task.get("workflow_ref") or ""),
            task_mode=task_mode,
            exit_criteria=[str(item) for item in task_exit],
            required_evidence=[str(item) for item in required],
            completion_design=TaskCompletionDesign.model_validate(completion) if completion else None,
            evidence_refs=selected,
            external_ai_summary=_compact(external_ai_summary, 4000),
            page_anchor=page_anchor,
            goal_anchor=goal_anchor,
            business_context=metadata,
            evidence_summary={
                "required": [str(item) for item in required],
                "available": [item.evidence_id for item in selected],
                "missing": [str(item) for item in missing],
            },
            context_manifest=manifest,
            manifest={
                "context_recipe": definition.context_recipe,
                "evidence_policy": definition.evidence_policy,
                "work_session_id": session.get("session_id") or "",
                "large_object_policy": "reference_only",
                "raw_content_in_prompt": False,
                "context_playbook_item_ids": [str(item.get("item_id") or "") for item in playbook_items],
            },
        )


class WorkLearningService:
    FLOW = ["observe", "context", "plan_delta", "act_or_ask", "verify", "reflect", "continue_or_stop"]

    def __init__(
        self,
        *,
        store: AgentV2Store,
        repository: KnowledgeRepository,
        search: HybridSearchService,
        harnesses: HarnessRegistry,
        page_context_provider: Callable[[str, str], dict[str, Any]] | None = None,
        knowledge_change_notifier: Callable[[str, str, str], None] | None = None,
        model_profile: str = "default",
    ):
        self.store = store
        self.repository = repository
        self.search = search
        self.harnesses = harnesses
        self.contexts = ContextCompiler(repository, store, page_context_provider)
        self.knowledge_change_notifier = knowledge_change_notifier
        self.model_profile = model_profile or "default"

    def _record_harness_failures(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        context: WorkContextPack,
        results: list[HarnessResult],
        phase: str,
        terminal_cause: str = "",
    ) -> list[str]:
        record_ids: list[str] = []
        for result in results:
            if result.status != "blocked":
                continue
            blocked_checks = [item for item in result.checks if item.status == "blocked"]
            causal_stage = next((item.check_id for item in blocked_checks), "verifier.blocked")
            record_id = _id(
                "hfailure",
                f"{work_run['work_run_id']}:{result.harness_id}:{result.version}:{phase}:{causal_stage}",
            )
            record = {
                "failure_record_id": record_id,
                "employee_id": principal.employee_id,
                "work_run_id": work_run["work_run_id"],
                "harness_id": result.harness_id,
                "harness_version": result.version,
                "model_profile": self.model_profile,
                "phase": phase,
                "terminal_verifier_cause": terminal_cause or "; ".join(result.blockers),
                "causal_agent_stage": causal_stage,
                "exposed_mechanism": [item.check_id for item in blocked_checks],
                "context_id": context.context_id,
                "context_manifest": (
                    context.context_manifest.model_dump(mode="json")
                    if context.context_manifest is not None
                    else {}
                ),
                "evidence_refs": [item.evidence_id for item in context.evidence_refs],
                "artifact_refs": list(work_run.get("artifact_refs") or []),
                "reproducibility": "fixture_required",
                "scope": "recurrent_candidate" if len(blocked_checks) == 1 else "run_specific",
                "status": "open",
                "created_at": now_iso(),
            }
            self.store.put("harness_failure_records", record_id, record)
            negative_id = _id("negative", record_id)
            self.store.put(
                "negative_results",
                negative_id,
                {
                    "negative_result_id": negative_id,
                    "employee_id": principal.employee_id,
                    "kind": "harness_blocker",
                    "work_run_id": work_run["work_run_id"],
                    "failure_record_id": record_id,
                    "summary": record["terminal_verifier_cause"],
                    "source_refs": record["evidence_refs"],
                    "status": "active",
                    "created_at": now_iso(),
                },
            )
            record_ids.append(record_id)
        return record_ids

    def list_harness_failures(self, principal: Principal, *, status: str = "open") -> dict[str, Any]:
        items = [
            item for item in self.store.list("harness_failure_records", limit=1000)
            if (principal.is_admin or str(item.get("employee_id") or "") == principal.employee_id)
            and (not status or str(item.get("status") or "") == status)
        ]
        return {"count": len(items), "items": items}

    def list_context_playbook(self, principal: Principal, *, status: str = "") -> dict[str, Any]:
        items = [
            item for item in self.store.list("context_playbook_items", limit=1000)
            if (principal.is_admin or str(item.get("employee_id") or "") == principal.employee_id)
            and (not status or str(item.get("status") or "") == status)
        ]
        return {"count": len(items), "items": items}

    def create_harness_candidate(self, principal: Principal, request: Any) -> dict[str, Any]:
        definition = self.harnesses.definition(request.harness_id)
        forbidden = sorted(set(request.changes) & set(definition.immutable_boundaries))
        unsupported = sorted(set(request.changes) - set(definition.editable_surfaces) - set(definition.immutable_boundaries))
        if forbidden or unsupported:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "harness_candidate_surface_not_editable",
                    "immutable": forbidden,
                    "unsupported": unsupported,
                },
            )
        failures = [self.store.get("harness_failure_records", item) for item in request.failure_record_ids]
        if any(not item for item in failures):
            raise HTTPException(status_code=404, detail="실패 기록을 찾을 수 없습니다.")
        candidate_id = _id("hcandidate", f"{request.harness_id}:{request.model_profile}:{now_iso()}")
        candidate = {
            "candidate_id": candidate_id,
            "employee_id": principal.employee_id,
            "harness_id": request.harness_id,
            "base_version": definition.version,
            "model_profile": request.model_profile,
            "failure_record_ids": request.failure_record_ids,
            "changes": request.changes,
            "rationale": request.rationale,
            "status": "shadow_pending",
            "production_changed": False,
            "created_at": now_iso(),
        }
        return self.store.put("harness_candidates", candidate_id, candidate)

    def evaluate_harness_candidate(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        candidate = self.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        if not principal.is_admin and str(candidate.get("employee_id") or "") != principal.employee_id:
            raise HTTPException(status_code=403, detail="이 Harness 후보를 평가할 수 없습니다.")
        held_in_ok = request.held_in.get("passed") is True
        held_out_ok = request.held_out.get("passed") is True and int(request.held_out.get("regressions") or 0) == 0
        adversarial_ok = request.adversarial.get("passed", True) is True and int(request.adversarial.get("unauthorized_mutations") or 0) == 0
        eval_id = _id("heval", f"{candidate_id}:{request.fixture_revision}:{now_iso()}")
        evaluation = {
            "eval_id": eval_id,
            "candidate_id": candidate_id,
            "employee_id": principal.employee_id,
            "fixture_revision": request.fixture_revision,
            "held_in": request.held_in,
            "held_out": request.held_out,
            "adversarial": request.adversarial,
            "long_term": request.long_term,
            "qualified": held_in_ok and held_out_ok and adversarial_ok,
            "created_at": now_iso(),
        }
        self.store.put("harness_eval_runs", eval_id, evaluation)
        candidate.update(
            {
                "status": "review_required" if evaluation["qualified"] else "rejected",
                "latest_eval_id": eval_id,
                "production_changed": False,
                "updated_at": now_iso(),
            }
        )
        self.store.put("harness_candidates", candidate_id, candidate)
        return {"candidate": candidate, "evaluation": evaluation}

    @staticmethod
    def resolve_loop_policy(
        intent: WorkIntent,
        policy: LoopPolicy | dict[str, Any] | None = None,
    ) -> LoopPolicy:
        if policy is not None:
            return policy if isinstance(policy, LoopPolicy) else LoopPolicy.model_validate(policy)
        goal_based = intent.asset_kind == WorkAssetKind.task or intent.operation not in {
            WorkOperation.understand,
            WorkOperation.observe,
            WorkOperation.compare,
        }
        return LoopPolicy(
            kind=LoopKind.goal if goal_based else LoopKind.turn,
            trigger=LoopTriggerKind.user,
            task_stop="exit_criteria" if intent.asset_kind == WorkAssetKind.task else "agent_done",
            routine_stop="one_shot",
            max_runs=1,
        )

    def create_run(
        self,
        *,
        principal: Principal,
        agent_run_id: str,
        session: dict[str, Any],
        context: WorkContextPack,
        intent: WorkIntent,
        goal_plan_id: str,
        loop_policy: LoopPolicy | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        work_run_id = _id("workrun", f"{agent_run_id}:{principal.employee_id}")
        preflight_ids = [
            harness_id
            for harness_id in self.harnesses.harnesses_for(intent, intent.asset_kind.value)
            if harness_id != "learning.capture"
        ]
        preflights = [
            self.harnesses.evaluate(
                harness_id,
                phase="preflight",
                intent=intent,
                context=context,
                task_mode=context.task_mode,
            )
            for harness_id in preflight_ids
        ]
        status = "blocked" if any(item.status == "blocked" for item in preflights) else "running"
        ledger_ids = [
            self._record_evidence(
                principal=principal,
                work_run_id=work_run_id,
                evidence_id=item.evidence_id,
                kind=item.kind,
                title=item.title,
                summary=item.summary,
                source=item.source,
                authority=item.authority,
                verification="selected",
            )
            for item in context.evidence_refs
        ]
        resolved_loop_policy = self.resolve_loop_policy(intent, loop_policy)
        run = {
            "work_run_id": work_run_id,
            "agent_run_id": agent_run_id,
            "employee_id": principal.employee_id,
            "work_session_id": session.get("session_id") or "",
            "context_id": context.context_id,
            "goal_plan_id": goal_plan_id,
            "intent": intent.model_dump(mode="json"),
            "task_mode": context.task_mode.value,
            "status": status,
            "decision": "blocked" if status == "blocked" else "continue",
            "revision": 1,
            "loop": {
                "flow": self.FLOW,
                "policy": resolved_loop_policy.model_dump(mode="json"),
                "iteration_count": 0,
                "no_progress_count": 0,
                "max_iterations": resolved_loop_policy.max_iterations,
                "max_no_progress": resolved_loop_policy.max_no_progress,
                "max_tool_loops": resolved_loop_policy.max_tool_loops,
                "deltas": [],
            },
            "harness_results": [item.model_dump(mode="json") for item in preflights],
            "harness_bindings": self.harnesses.bindings(preflight_ids, self.model_profile),
            "events": [
                {"event": "work.observed", "at": now_iso()},
                {"event": "context.compiled", "context_id": context.context_id, "at": now_iso()},
                {
                    "event": "harness.preflight",
                    "status": "blocked" if status == "blocked" else "passed",
                    "harness_ids": preflight_ids,
                    "at": now_iso(),
                },
            ],
            "artifact_refs": [],
            "evidence_refs": [item.evidence_id for item in context.evidence_refs],
            "evidence_ledger_ids": ledger_ids,
            "knowledge_candidate_ids": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        for preflight in preflights:
            self.store.put(
                "harness_results",
                f"{work_run_id}:{preflight.harness_id}:preflight",
                {
                    "employee_id": principal.employee_id,
                    "work_run_id": work_run_id,
                    **preflight.model_dump(mode="json"),
                },
            )
        failure_ids = self._record_harness_failures(
            principal=principal,
            work_run=run,
            context=context,
            results=preflights,
            phase="preflight",
        )
        run["harness_failure_record_ids"] = failure_ids
        return self.store.put("work_runs", work_run_id, run)

    def _record_evidence(
        self,
        *,
        principal: Principal,
        work_run_id: str,
        evidence_id: str,
        kind: str,
        title: str,
        summary: str,
        source: str,
        authority: str,
        verification: str,
    ) -> str:
        ledger_id = _id("ledger", f"{work_run_id}:{evidence_id}:{verification}")
        self.store.put(
            "evidence_ledger",
            ledger_id,
            {
                "ledger_id": ledger_id,
                "employee_id": principal.employee_id,
                "work_run_id": work_run_id,
                "evidence_id": evidence_id,
                "kind": kind,
                "title": _compact(title, 240),
                "summary": _compact(summary, 2000),
                "source": source,
                "authority": authority,
                "verification": verification,
                "created_at": now_iso(),
            },
        )
        return ledger_id

    def finish_run(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        context: WorkContextPack,
        intent: WorkIntent,
        response_status: str,
        answer_summary: str,
        artifacts: list[dict[str, Any]],
        evidence_refs: list[str],
        job_id: str = "",
    ) -> tuple[dict[str, Any], list[KnowledgeCandidateRef]]:
        artifact = artifacts[0] if artifacts else {}
        artifact_kind = str(artifact.get("artifact_type") or artifact.get("capability_id") or intent.asset_kind.value)
        results: list[HarnessResult] = []
        for harness_id in self.harnesses.harnesses_for(intent, artifact_kind):
            if harness_id == "learning.capture":
                continue
            result = self.harnesses.evaluate(
                harness_id,
                phase="post_verify",
                intent=intent,
                context=context,
                artifact=artifact,
                task_mode=context.task_mode,
            )
            results.append(result)
            self.store.put(
                "harness_results",
                f"{work_run['work_run_id']}:{harness_id}:post_verify",
                {
                    "employee_id": principal.employee_id,
                    "work_run_id": work_run["work_run_id"],
                    **result.model_dump(mode="json"),
                },
            )
        blocked = any(item.status == "blocked" for item in results)
        delta_kind = "state_transition" if job_id else "new_artifact" if artifacts else "new_evidence" if evidence_refs else "blocker"
        delta = LoopDelta(
            kind=delta_kind,  # type: ignore[arg-type]
            summary=("심층 작업이 대기열에 등록되었습니다." if job_id else answer_summary),
            ref=job_id or str(artifact.get("artifact_id") or (evidence_refs[0] if evidence_refs else "")),
        )
        delta.fingerprint = _fingerprint(delta)
        loop = dict(work_run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
        loop["deltas"] = [*(loop.get("deltas") or []), delta.model_dump(mode="json")][-20:]
        if response_status == "failed" or blocked:
            status, decision = "blocked", "blocked"
        elif response_status == "queued":
            status, decision = "queued", "continue"
        elif intent.operation == WorkOperation.complete and not intent.needs_clarification:
            if context.task_mode == TaskMode.autopilot:
                status, decision = "waiting_signal", "continue"
            else:
                status, decision = "waiting_human", "needs_human"
        elif response_status == "needs_input" or intent.needs_clarification:
            status, decision = "waiting_human", "needs_human"
        elif artifacts and intent.operation in {WorkOperation.validate, WorkOperation.test}:
            status, decision = "completed", "complete"
        elif artifacts and artifact_kind == "mermaid_diagram":
            status, decision = "completed", "complete"
        elif artifacts:
            status, decision = "waiting_review", "needs_human"
        elif intent.operation in {WorkOperation.complete, WorkOperation.run, WorkOperation.promote}:
            status, decision = "waiting_human", "needs_human"
        else:
            status, decision = "completed", "complete"
        work_run.update(
            {
                "status": status,
                "decision": decision,
                "loop": loop,
                "artifact_refs": [str(item.get("artifact_id") or "") for item in artifacts if item.get("artifact_id")],
                "evidence_refs": list(dict.fromkeys([*work_run.get("evidence_refs", []), *evidence_refs]))[:50],
                "job_id": job_id or work_run.get("job_id") or "",
                "harness_results": [
                    *work_run.get("harness_results", []),
                    *[item.model_dump(mode="json") for item in results],
                ],
                "revision": int(work_run.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        failure_ids = self._record_harness_failures(
            principal=principal,
            work_run=work_run,
            context=context,
            results=results,
            phase="post_verify",
            terminal_cause="response_failed" if response_status == "failed" else "",
        )
        work_run["harness_failure_record_ids"] = list(
            dict.fromkeys([*work_run.get("harness_failure_record_ids", []), *failure_ids])
        )
        added_ledger_ids = [
            self._record_evidence(
                principal=principal,
                work_run_id=str(work_run["work_run_id"]),
                evidence_id=ref,
                kind="evidence",
                title=ref,
                summary=answer_summary,
                source="operation",
                authority="runtime",
                verification="used",
            )
            for ref in evidence_refs
            if ref
        ]
        work_run["evidence_ledger_ids"] = list(
            dict.fromkeys([*work_run.get("evidence_ledger_ids", []), *added_ledger_ids])
        )[:100]
        work_run.setdefault("events", []).extend(
            [
                {"event": "loop.delta", "delta": delta.model_dump(mode="json"), "at": now_iso()},
                {"event": "harness.verified", "status": "blocked" if blocked else "passed", "at": now_iso()},
                {"event": "work.waiting" if status == "waiting_review" else "work.completed" if status == "completed" else "work.updated", "status": status, "at": now_iso()},
            ]
        )
        candidates: list[KnowledgeCandidateRef] = []
        if status == "completed" and intent.operation == WorkOperation.capture:
            candidate = self._create_candidate(
                principal=principal,
                work_run=work_run,
                context=context,
                title=answer_summary,
                summary=answer_summary,
                source_refs=evidence_refs,
            )
            if candidate:
                candidates.append(candidate)
                work_run["knowledge_candidate_ids"] = [candidate.candidate_id]
                playbook_id = _id("playbook", f"{principal.employee_id}:{candidate.candidate_id}")
                self.store.put(
                    "context_playbook_items",
                    playbook_id,
                    {
                        "item_id": playbook_id,
                        "employee_id": principal.employee_id,
                        "description": answer_summary,
                        "conditions": [intent.asset_kind.value, intent.operation.value],
                        "applies_to": {
                            "capability_ids": [context.capability_id],
                            "asset_kinds": [intent.asset_kind.value],
                        },
                        "source_refs": evidence_refs,
                        "supporting_work_run_ids": [work_run["work_run_id"]],
                        "successful_run_ids": [work_run["work_run_id"]],
                        "failed_run_ids": [],
                        "freshness": {"created_at": now_iso(), "valid_until": ""},
                        "status": "provisional",
                        "visibility": "private",
                        "created_at": now_iso(),
                    },
                )
        stored = self.store.put("work_runs", str(work_run["work_run_id"]), work_run)
        if job_id:
            job = self.store.get("jobs", job_id)
            if job:
                job.update(
                    {
                        "work_run_id": work_run["work_run_id"],
                        "agent_run_id": work_run.get("agent_run_id") or "",
                        "updated_at": now_iso(),
                    }
                )
                self.store.put("jobs", job_id, job)
        return stored, candidates

    def finish_system_run(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        summary: str,
        result_ref: str,
        result_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Close a deterministic system operation without asking an LLM to self-grade it."""

        successful = result_status not in {"failed", "error", "blocked"}
        delta = LoopDelta(
            kind="state_transition" if successful else "blocker",
            summary=_compact(summary, 2000),
            ref=result_ref,
            metadata=metadata or {},
        )
        delta.fingerprint = _fingerprint(delta)
        loop = dict(work_run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
        loop["no_progress_count"] = 0
        loop["deltas"] = [*(loop.get("deltas") or []), delta.model_dump(mode="json")][-20:]
        ledger_ids = list(work_run.get("evidence_ledger_ids") or [])
        if result_ref:
            ledger_ids.append(
                self._record_evidence(
                    principal=principal,
                    work_run_id=str(work_run["work_run_id"]),
                    evidence_id=result_ref,
                    kind="runtime",
                    title=result_ref,
                    summary=summary,
                    source="system_operation",
                    authority="runtime",
                    verification="verified" if successful else "failed",
                )
            )
        work_run.update(
            {
                "status": "completed" if successful else "blocked",
                "decision": "complete" if successful else "blocked",
                "stop_reason": "" if successful else "operation_failed",
                "loop": loop,
                "evidence_ledger_ids": list(dict.fromkeys(ledger_ids))[:100],
                "revision": int(work_run.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        work_run.setdefault("events", []).extend(
            [
                {"event": "loop.delta", "delta": delta.model_dump(mode="json"), "at": now_iso()},
                {
                    "event": "work.completed" if successful else "work.blocked",
                    "status": work_run["status"],
                    "at": now_iso(),
                },
            ]
        )
        return self.store.put("work_runs", str(work_run["work_run_id"]), work_run)

    def fail_run(self, principal: Principal, work_run_id: str, message: str) -> dict[str, Any]:
        run = self.get_run(principal, work_run_id)
        delta = LoopDelta(kind="blocker", summary=_compact(message, 2000))
        delta.fingerprint = _fingerprint(delta)
        loop = dict(run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
        loop["deltas"] = [*(loop.get("deltas") or []), delta.model_dump(mode="json")][-20:]
        run.update(
            {
                "status": "blocked",
                "decision": "blocked",
                "stop_reason": "operation_failed",
                "loop": loop,
                "revision": int(run.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        run.setdefault("events", []).append(
            {"event": "work.blocked", "delta": delta.model_dump(mode="json"), "at": now_iso()}
        )
        return self.store.put("work_runs", work_run_id, run)

    def finish_deep_job(
        self,
        principal: Principal,
        *,
        work_run_id: str,
        artifact: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        run = self.get_run(principal, work_run_id)
        context_row = self.store.get("contexts", str(run.get("context_id") or "")) or {}
        context = WorkContextPack.model_validate(context_row)
        intent = WorkIntent.model_validate(run.get("intent") or {})
        evidence_refs = [
            str(item.get("evidence_id") or "")
            for item in result.get("evidence_ledger") or []
            if isinstance(item, dict) and item.get("evidence_id")
        ]
        stored, _ = self.finish_run(
            principal=principal,
            work_run=run,
            context=context,
            intent=intent,
            response_status="completed",
            answer_summary=str(result.get("title") or "심층 작업 초안이 준비되었습니다."),
            artifacts=[artifact],
            evidence_refs=evidence_refs,
        )
        return stored

    def _owned(self, principal: Principal, row: dict[str, Any] | None, label: str) -> dict[str, Any]:
        if not row:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        if row.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail=f"{label} belongs to another employee")
        return row

    def get_run(self, principal: Principal, work_run_id: str) -> dict[str, Any]:
        return self._owned(principal, self.store.get("work_runs", work_run_id), "work run")

    def view_run(self, principal: Principal, work_run_id: str) -> dict[str, Any]:
        run = dict(self.get_run(principal, work_run_id))
        ledger_ids = set(run.get("evidence_ledger_ids") or [])
        run["evidence_ledger"] = [
            item
            for item in self.store.list(
                "evidence_ledger",
                employee_id=principal.employee_id,
                limit=500,
            )
            if item.get("ledger_id") in ledger_ids and item.get("work_run_id") == work_run_id
        ]
        return run

    def list_runs(self, principal: Principal, *, limit: int = 20) -> dict[str, Any]:
        items = self.store.list("work_runs", employee_id=principal.employee_id, limit=max(1, min(limit, 100)))
        return {"count": len(items), "items": items}

    def continue_run(
        self,
        principal: Principal,
        work_run_id: str,
        request: WorkRunContinueRequest,
    ) -> tuple[dict[str, Any], list[KnowledgeCandidateRef]]:
        run = self.get_run(principal, work_run_id)
        revision = int(run.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "current_revision": revision, "work_run": run})
        if run.get("status") in {"completed", "failed", "cancelled", "stopped"}:
            raise HTTPException(status_code=409, detail=f"work run is already {run.get('status')}")
        delta = request.delta.model_copy(update={"fingerprint": _fingerprint(request.delta)})
        loop = dict(run.get("loop") or {})
        deltas = list(loop.get("deltas") or [])
        repeated = any(str(item.get("fingerprint") or "") == delta.fingerprint for item in deltas)
        no_progress = repeated or delta.kind == "no_progress"
        no_progress_count = int(loop.get("no_progress_count") or 0) + 1 if no_progress else 0
        iteration = int(loop.get("iteration_count") or 0) + 1
        loop.update(
            {
                "iteration_count": iteration,
                "no_progress_count": no_progress_count,
                "deltas": [*deltas, delta.model_dump(mode="json")][-20:],
            }
        )
        mode = TaskMode(str(run.get("task_mode") or "copilot"))
        context_row = self.store.get("contexts", str(run.get("context_id") or "")) or {}
        context = WorkContextPack.model_validate(context_row)
        intent = WorkIntent.model_validate(run.get("intent") or {})
        completion = context.completion_design
        system_checks = list(completion.checks) if completion else []
        if mode in {TaskMode.manual, TaskMode.copilot} and request.confirmation == "confirm" and delta.kind == "human_input" and not delta.ref:
            delta = delta.model_copy(update={"ref": f"human:{work_run_id}:{iteration}"})
            loop["deltas"][-1] = delta.model_dump(mode="json")
        autopilot_ready = bool(system_checks) and all(
            item.confirmation == "system"
            and item.binding is not None
            and item.binding.kind != "none"
            and bool(item.binding.ref)
            for item in system_checks
        )
        binding_refs = {
            item.binding.ref
            for item in system_checks
            if item.binding is not None and item.binding.ref
        }
        verified_binding_refs = {
            str(item)
            for item in delta.metadata.get("verified_binding_refs") or []
            if str(item).strip()
        }
        autopilot_delta_matches = bool(binding_refs) and (
            verified_binding_refs.issuperset(binding_refs)
            or (len(binding_refs) == 1 and delta.ref in binding_refs)
        )
        complete_delta = (
            delta.kind in {"human_input", "state_transition"} and request.confirmation == "confirm"
            if mode in {TaskMode.manual, TaskMode.copilot}
            else autopilot_ready
            and autopilot_delta_matches
            and delta.kind in {"action_result", "state_transition"}
        )
        standalone_action_complete = (
            intent.operation == WorkOperation.run
            and intent.asset_kind.value == "action"
            and not context.task_ref
            and delta.kind == "action_result"
            and bool(delta.ref)
        )
        if iteration >= int(loop.get("max_iterations") or 5):
            status, decision, stop_reason = "stopped", "stop", "max_iterations"
        elif no_progress_count >= int(loop.get("max_no_progress") or 1):
            status, decision, stop_reason = "stopped", "stop", "no_progress"
        elif mode == TaskMode.autopilot and delta.kind in {"action_result", "state_transition"} and not autopilot_ready:
            status, decision, stop_reason = "waiting_human", "blocked", "completion_connections_required"
        elif mode == TaskMode.autopilot and delta.kind in {"action_result", "state_transition"} and not autopilot_delta_matches:
            status, decision, stop_reason = "waiting_signal", "continue", "unrelated_system_result"
        elif delta.kind == "blocker":
            status, decision, stop_reason = "waiting_human", "needs_human", "blocker"
        elif complete_delta or standalone_action_complete:
            status, decision, stop_reason = "completed", "complete", "exit_criteria_satisfied"
        else:
            status, decision, stop_reason = "in_progress", "continue", "progress_recorded"
        run.update(
            {
                "status": status,
                "decision": decision,
                "stop_reason": stop_reason,
                "loop": loop,
                "revision": revision + 1,
                "updated_at": now_iso(),
            }
        )
        run.setdefault("events", []).append(
            {"event": "loop.delta", "delta": delta.model_dump(mode="json"), "decision": decision, "at": now_iso()}
        )
        if delta.ref:
            ledger_id = self._record_evidence(
                principal=principal,
                work_run_id=work_run_id,
                evidence_id=delta.ref,
                kind=delta.kind,
                title=delta.summary or delta.ref,
                summary=delta.summary,
                source="human" if delta.kind == "human_input" else "runtime",
                authority="confirmed" if request.confirmation == "confirm" else "runtime",
                verification="confirmed" if request.confirmation == "confirm" else "observed",
            )
            run["evidence_ledger_ids"] = list(
                dict.fromkeys([*run.get("evidence_ledger_ids", []), ledger_id])
            )[:100]
        candidates: list[KnowledgeCandidateRef] = []
        if status == "completed":
            completion_id = _id("completion", f"{work_run_id}:{revision + 1}")
            completion = {
                "completion_id": completion_id,
                "employee_id": principal.employee_id,
                "work_run_id": work_run_id,
                "context_id": context.context_id,
                "task_ref": context.task_ref,
                "workflow_ref": context.workflow_ref,
                "task_mode": mode.value,
                "decision": "complete",
                "summary": delta.summary,
                "evidence_refs": list(dict.fromkeys([*run.get("evidence_refs", []), delta.ref] if delta.ref else run.get("evidence_refs", []))),
                "evidence_ledger_ids": run.get("evidence_ledger_ids", []),
                "created_at": now_iso(),
            }
            self.store.put("completion_records", completion_id, completion)
            if self.knowledge_change_notifier is not None:
                self.knowledge_change_notifier(completion_id, principal.employee_id, "upsert")
            run["completion_record_id"] = completion_id
            should_capture = intent.operation in {WorkOperation.complete, WorkOperation.capture} or bool(
                delta.metadata.get("capture")
            )
            if should_capture:
                candidate = self._create_candidate(
                    principal=principal,
                    work_run=run,
                    context=context,
                    title=delta.summary or "완료된 업무에서 남길 내용",
                    summary=delta.summary,
                    source_refs=completion["evidence_refs"],
                )
                if candidate:
                    candidates.append(candidate)
                    run["knowledge_candidate_ids"] = [*run.get("knowledge_candidate_ids", []), candidate.candidate_id]
            pattern_candidate = self._maybe_create_manual_pattern_candidate(
                principal=principal,
                work_run=run,
                context=context,
                completion=completion,
            )
            if pattern_candidate:
                candidates.append(pattern_candidate)
                run["knowledge_candidate_ids"] = [
                    *run.get("knowledge_candidate_ids", []),
                    pattern_candidate.candidate_id,
                ]
                run.setdefault("events", []).append(
                    {
                        "event": "learning.pattern_detected",
                        "candidate_id": pattern_candidate.candidate_id,
                        "pattern_kind": "repeated_manual_work",
                        "at": now_iso(),
                    }
                )
        elif delta.kind == "blocker":
            blocker_candidate = self._maybe_create_blocker_pattern_candidate(
                principal=principal,
                work_run=run,
                context=context,
                summary=delta.summary,
            )
            if blocker_candidate:
                candidates.append(blocker_candidate)
                run["knowledge_candidate_ids"] = [
                    *run.get("knowledge_candidate_ids", []),
                    blocker_candidate.candidate_id,
                ]
                run.setdefault("events", []).append(
                    {
                        "event": "learning.pattern_detected",
                        "candidate_id": blocker_candidate.candidate_id,
                        "pattern_kind": "repeated_blocker",
                        "at": now_iso(),
                    }
                )
        stored = self.store.put("work_runs", work_run_id, run)
        return stored, candidates

    def _create_candidate(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        context: WorkContextPack,
        title: str,
        summary: str,
        source_refs: list[str],
    ) -> KnowledgeCandidateRef | None:
        clean_summary = _compact(summary, 4000)
        refs = [str(item) for item in source_refs if str(item).strip()]
        if not clean_summary or not refs:
            return None
        matches = self.search.search(clean_summary, principal, limit=5, include_history=False).items
        duplicate_refs = [item.evidence_id for item in matches if item.score >= 0.82]
        candidate_id = _id("candidate", f"{work_run['work_run_id']}:{clean_summary}")
        candidate = {
            "candidate_id": candidate_id,
            "employee_id": principal.employee_id,
            "source_work_run_id": work_run["work_run_id"],
            "source_task_ref": context.task_ref,
            "title": _compact(title, 160) or "업무에서 남길 내용",
            "summary": clean_summary,
            "reusable_lesson": clean_summary,
            "source_refs": refs[:50],
            "target_asset_ref": context.goal_anchor.ref if context.goal_anchor else context.page_anchor.ref if context.page_anchor else "",
            "visibility": "private",
            "status": "provisional",
            "novelty": {
                "checked": True,
                "duplicate_refs": duplicate_refs,
                "recommendation": "augment_existing" if duplicate_refs else "create_new",
            },
            "raw_transcript_stored": False,
            "revision": 1,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        result = self.harnesses.evaluate(
            "learning.capture",
            phase="capture",
            intent=WorkIntent.model_validate(work_run["intent"]),
            context=context,
            candidate=candidate,
            task_mode=context.task_mode,
        )
        self.store.put(
            "harness_results",
            f"{work_run['work_run_id']}:learning.capture:{candidate_id}",
            {"employee_id": principal.employee_id, "work_run_id": work_run["work_run_id"], **result.model_dump(mode="json")},
        )
        if result.status == "blocked":
            return None
        self.store.put("knowledge_candidates", candidate_id, candidate)
        try:
            index_result = self.search.index_private_candidate(candidate)
            candidate["search_index_status"] = index_result.get("status") or "unknown"
            candidate["search_chunk_ids"] = index_result.get("chunk_ids") or []
        except Exception as exc:
            candidate["search_index_status"] = f"failed:{type(exc).__name__}"
            candidate["search_chunk_ids"] = []
        self.store.put("knowledge_candidates", candidate_id, candidate)
        return KnowledgeCandidateRef(
            candidate_id=candidate_id,
            title=candidate["title"],
            status="provisional",
            url=f"/api/v2/knowledge-candidates/{candidate_id}",
        )

    def _existing_pattern_candidate(self, principal: Principal, pattern_key: str) -> bool:
        return any(
            item.get("pattern_key") == pattern_key and item.get("status") != "archived"
            for item in self.store.list(
                "knowledge_candidates",
                employee_id=principal.employee_id,
                limit=500,
            )
        )

    def _decorate_pattern_candidate(
        self,
        candidate: KnowledgeCandidateRef,
        *,
        pattern_key: str,
        pattern_kind: str,
        recommended_asset_kind: str,
        occurrences: int,
    ) -> KnowledgeCandidateRef:
        row = self.store.get("knowledge_candidates", candidate.candidate_id)
        if not row:
            return candidate
        row.update(
            {
                "candidate_kind": "work_pattern",
                "pattern_key": pattern_key,
                "pattern_kind": pattern_kind,
                "recommended_asset_kind": recommended_asset_kind,
                "occurrences": occurrences,
                "updated_at": now_iso(),
            }
        )
        self.store.put("knowledge_candidates", candidate.candidate_id, row)
        return candidate

    def _maybe_create_manual_pattern_candidate(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        context: WorkContextPack,
        completion: dict[str, Any],
    ) -> KnowledgeCandidateRef | None:
        if context.task_mode != TaskMode.manual or not context.task_ref:
            return None
        matches = [
            item
            for item in self.store.list(
                "completion_records",
                employee_id=principal.employee_id,
                limit=500,
            )
            if item.get("task_ref") == context.task_ref and item.get("task_mode") == TaskMode.manual.value
        ]
        if len(matches) < 3:
            return None
        pattern_key = f"manual:{context.task_ref}"
        if self._existing_pattern_candidate(principal, pattern_key):
            return None
        source_refs = [str(item.get("completion_id") or "") for item in matches if item.get("completion_id")]
        summary = (
            f"{context.task_ref} 업무가 Manual 방식으로 {len(matches)}회 반복 완료되었습니다. "
            "재사용 가능한 Skill 또는 안전한 Action으로 만들 수 있는지 검토할 후보입니다."
        )
        candidate = self._create_candidate(
            principal=principal,
            work_run=work_run,
            context=context,
            title="반복 Manual 업무 자동화 후보",
            summary=summary,
            source_refs=source_refs or [str(completion["completion_id"])],
        )
        if not candidate:
            return None
        return self._decorate_pattern_candidate(
            candidate,
            pattern_key=pattern_key,
            pattern_kind="repeated_manual_work",
            recommended_asset_kind="skill_or_action",
            occurrences=len(matches),
        )

    def _maybe_create_blocker_pattern_candidate(
        self,
        *,
        principal: Principal,
        work_run: dict[str, Any],
        context: WorkContextPack,
        summary: str,
    ) -> KnowledgeCandidateRef | None:
        if not context.task_ref:
            return None
        run_refs: list[str] = [str(work_run["work_run_id"])]
        occurrences = 1
        for item in self.store.list("work_runs", employee_id=principal.employee_id, limit=500):
            if item.get("work_run_id") == work_run.get("work_run_id"):
                continue
            candidate_context = self.store.get("contexts", str(item.get("context_id") or "")) or {}
            if candidate_context.get("task_ref") != context.task_ref:
                continue
            blocker_count = sum(
                1
                for delta in (item.get("loop") or {}).get("deltas") or []
                if isinstance(delta, dict) and delta.get("kind") == "blocker"
            )
            if blocker_count:
                occurrences += blocker_count
                run_refs.extend([str(item.get("work_run_id") or "")] * blocker_count)
        if occurrences < 2:
            return None
        pattern_key = f"blocker:{context.task_ref}"
        if self._existing_pattern_candidate(principal, pattern_key):
            return None
        lesson = (
            f"{context.task_ref} 업무에서 blocker가 {occurrences}회 반복되었습니다. "
            f"최근 blocker: {_compact(summary, 600)}. SOP의 예외 처리 또는 Harness의 필수 근거를 보완할 후보입니다."
        )
        candidate = self._create_candidate(
            principal=principal,
            work_run=work_run,
            context=context,
            title="반복 blocker 개선 후보",
            summary=lesson,
            source_refs=list(dict.fromkeys(ref for ref in run_refs if ref)),
        )
        if not candidate:
            return None
        return self._decorate_pattern_candidate(
            candidate,
            pattern_key=pattern_key,
            pattern_kind="repeated_blocker",
            recommended_asset_kind="sop_or_harness",
            occurrences=occurrences,
        )

    def get_candidate(self, principal: Principal, candidate_id: str) -> dict[str, Any]:
        return self._owned(principal, self.store.get("knowledge_candidates", candidate_id), "knowledge candidate")

    def list_candidates(self, principal: Principal, *, status: str = "", limit: int = 50) -> dict[str, Any]:
        items = self.store.list("knowledge_candidates", employee_id=principal.employee_id, limit=max(1, min(limit, 100)))
        if status:
            items = [item for item in items if item.get("status") == status]
        return {"count": len(items), "items": items}

    def patch_candidate(
        self,
        principal: Principal,
        candidate_id: str,
        request: KnowledgeCandidatePatchRequest,
    ) -> dict[str, Any]:
        candidate = self.get_candidate(principal, candidate_id)
        revision = int(candidate.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "current_revision": revision, "candidate": candidate})
        values = request.model_dump(exclude_unset=True)
        values.pop("expected_revision", None)
        candidate.update(values)
        candidate.update({"revision": revision + 1, "updated_at": now_iso()})
        stored = self.store.put("knowledge_candidates", candidate_id, candidate)
        if stored.get("status") == "archived":
            self.search.remove_private_candidate(stored)
            stored["search_index_status"] = "removed"
            stored["search_chunk_ids"] = []
        else:
            try:
                index_result = self.search.index_private_candidate(stored)
                stored["search_index_status"] = index_result.get("status") or "unknown"
                stored["search_chunk_ids"] = index_result.get("chunk_ids") or []
            except Exception as exc:
                stored["search_index_status"] = f"failed:{type(exc).__name__}"
        return self.store.put("knowledge_candidates", candidate_id, stored)

    def validate_candidate_promotion(
        self,
        principal: Principal,
        candidate_id: str,
    ) -> tuple[dict[str, Any], HarnessResult]:
        candidate = self.get_candidate(principal, candidate_id)
        source_run = self.store.get("work_runs", str(candidate.get("source_work_run_id") or "")) or {}
        context_row = self.store.get("contexts", str(source_run.get("context_id") or "")) or {}
        if not context_row:
            raise HTTPException(status_code=409, detail="candidate source context is unavailable")
        context = WorkContextPack.model_validate(context_row)
        source_intent = WorkIntent.model_validate(source_run.get("intent") or {})
        promotion_intent = source_intent.model_copy(
            update={
                "operation": WorkOperation.promote,
                "operation_plan": [WorkOperation.understand, WorkOperation.validate, WorkOperation.promote],
                "desired_outcome": "promotion_request",
                "risk": RiskLevel.high,
            }
        )
        harness_result = self.harnesses.evaluate(
            "learning.capture",
            phase="promote",
            intent=promotion_intent,
            context=context,
            candidate=candidate,
            task_mode=context.task_mode,
        )
        self.store.put(
            "harness_results",
            f"{source_run.get('work_run_id') or candidate_id}:learning.capture:promote:{candidate_id}",
            {
                "employee_id": principal.employee_id,
                "work_run_id": str(source_run.get("work_run_id") or ""),
                "candidate_id": candidate_id,
                **harness_result.model_dump(mode="json"),
            },
        )
        if harness_result.status == "blocked":
            raise HTTPException(
                status_code=409,
                detail={"status": "promotion_harness_failed", "harness": harness_result.model_dump(mode="json")},
            )
        return candidate, harness_result

    def promote_candidate(
        self,
        principal: Principal,
        candidate_id: str,
        request: KnowledgeCandidatePromoteRequest,
        *,
        promotion_preview: dict[str, Any] | None = None,
        plan_id: str = "",
        harness_result: HarnessResult | None = None,
    ) -> dict[str, Any]:
        candidate = self.get_candidate(principal, candidate_id)
        revision = int(candidate.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "current_revision": revision, "candidate": candidate})
        if candidate.get("status") == "archived":
            raise HTTPException(status_code=409, detail="an archived candidate cannot be promoted")
        if not request.reason.strip():
            raise HTTPException(status_code=422, detail="promotion reason is required")
        if harness_result is None:
            _, harness_result = self.validate_candidate_promotion(principal, candidate_id)
        preview = promotion_preview if isinstance(promotion_preview, dict) else {}
        preview_validation = preview.get("validation") if isinstance(preview.get("validation"), dict) else {}
        candidate.update(
            {
                "status": "promotion_requested",
                "promotion": {
                    "target_visibility": request.target_visibility,
                    "team_id": request.team_id,
                    "reason": request.reason,
                    "requested_by": principal.employee_id,
                    "requested_at": now_iso(),
                    "preview_id": str(preview.get("preview_id") or ""),
                    "preview_hash": str(preview.get("preview_hash") or ""),
                    "preview_status": str(preview.get("status") or ""),
                    "plan_id": plan_id,
                    "requires_existing_promotion_api": False,
                },
                "revision": revision + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("knowledge_candidates", candidate_id, candidate)
        return {
            "candidate_id": candidate_id,
            "status": "promotion_requested",
            "production_changed": False,
            "plan_ref": plan_id,
            "domain_preview": preview,
            "harness": harness_result.model_dump(mode="json"),
            "promotion_preview": {
                "title": candidate.get("title"),
                "body": candidate.get("reusable_lesson"),
                "source_refs": candidate.get("source_refs"),
                "target_visibility": request.target_visibility,
                "team_id": request.team_id,
                "validation": preview_validation,
            },
            "message": "기존 promotion 검증을 통과한 공유 검토 요청을 만들었습니다. 별도 확인 전에는 정본을 바꾸지 않습니다.",
        }
