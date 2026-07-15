from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException

from ..task_completion import evaluate_evidence_requirements
from .harness import HarnessRegistry
from .models import (
    CapabilityDefinition,
    ContextAnchor,
    ContextManifest,
    EvidenceRef,
    ExitCriteriaResult,
    HarnessCheck,
    HarnessResult,
    KnowledgeCandidatePatchRequest,
    KnowledgeCandidatePromoteRequest,
    KnowledgeCandidateRef,
    LoopKind,
    LoopPolicy,
    LoopTriggerKind,
    LoopDelta,
    ProgressDelta,
    Principal,
    RiskLevel,
    TaskCompletionDesign,
    TaskMode,
    WorkAssetKind,
    WorkContextPack,
    WorkIntent,
    WorkOperation,
    WorkRunContinueRequest,
    WorkRunCheckpoint,
)
from .repository import KnowledgeRepository
from .search import HybridSearchService
from .store import AgentV2Store, now_iso


def _id(prefix: str, value: str = "") -> str:
    digest = hashlib.sha256((value or f"{prefix}:{now_iso()}").encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _compact(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _string_list(value: Any, *, limit: int = 50) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value] if value else []
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))[:limit]


def _structured_progress(delta: LoopDelta, *, sequence: int) -> ProgressDelta:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    kind_map = {
        "new_evidence": "evidence",
        "action_result": "tool_result",
        "human_input": "human_input",
        "new_artifact": "artifact",
        "state_transition": "state_transition",
        "blocker": "blocker",
        "knowledge_candidate": "artifact",
        "no_progress": "strategy_change" if metadata.get("strategy") else "blocker",
    }
    progress_kind = kind_map[delta.kind]
    entity_refs = _string_list(metadata.get("entity_refs"))
    evidence_refs = _string_list(metadata.get("evidence_refs"))
    tool_result_refs = _string_list(metadata.get("tool_result_refs"))
    artifact_refs = _string_list(metadata.get("artifact_refs"))
    if delta.ref:
        if progress_kind == "evidence":
            evidence_refs = _string_list([*evidence_refs, delta.ref])
        elif progress_kind == "tool_result":
            tool_result_refs = _string_list([*tool_result_refs, delta.ref])
        elif progress_kind == "artifact":
            artifact_refs = _string_list([*artifact_refs, delta.ref])
        elif progress_kind == "human_input":
            entity_refs = _string_list([*entity_refs, delta.ref])
    completion_changes = metadata.get("completion_changes")
    if not isinstance(completion_changes, dict):
        completion_changes = {}
    for key in ("work_record", "verified_binding_refs", "completion_state"):
        if key in metadata:
            completion_changes[key] = metadata[key]
    state_transition = metadata.get("state_transition")
    if isinstance(state_transition, dict):
        completion_changes = {**completion_changes, **state_transition}
    blocker_code = str(metadata.get("blocker_code") or ("no_progress" if delta.kind == "no_progress" else "")).strip()
    strategy = str(metadata.get("strategy") or "").strip()
    strategy_refs = _string_list(
        [
            *_string_list(metadata.get("alternate_evidence_refs")),
            *_string_list(metadata.get("alternate_tool_refs")),
            *_string_list(metadata.get("approach_refs")),
        ]
    )
    error_disposition = str(metadata.get("error_disposition") or "").strip()
    allowed_dispositions = {
        "", "transient_retry", "semantic_repair", "human_interrupt", "policy_stop", "unexpected_failure"
    }
    if error_disposition not in allowed_dispositions:
        error_disposition = "unexpected_failure"
    return ProgressDelta(
        delta_id=_id("progress", f"{sequence}:{delta.kind}:{delta.ref}:{json.dumps(metadata, sort_keys=True, default=str)}"),
        kind=progress_kind,  # type: ignore[arg-type]
        entity_refs=entity_refs,
        evidence_refs=evidence_refs,
        tool_result_refs=tool_result_refs,
        artifact_refs=artifact_refs,
        completion_changes=completion_changes,
        blocker_code=blocker_code,
        strategy=strategy,
        strategy_refs=strategy_refs,
        error_disposition=error_disposition,  # type: ignore[arg-type]
        summary=_compact(delta.summary, 2000),
    )


def _progress_signature(delta: ProgressDelta) -> str:
    """Hash only durable domain changes; prose cannot manufacture progress."""

    value = json.dumps(
        {
            "kind": delta.kind,
            "entity_refs": sorted(delta.entity_refs),
            "evidence_refs": sorted(delta.evidence_refs),
            "tool_result_refs": sorted(delta.tool_result_refs),
            "artifact_refs": sorted(delta.artifact_refs),
            "completion_changes": delta.completion_changes,
            "blocker_code": delta.blocker_code,
            "strategy_refs": sorted(delta.strategy_refs),
            "error_disposition": delta.error_disposition,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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

    def goal_anchor(
        self,
        principal: Principal,
        session: dict[str, Any],
        task_ref: str,
        *,
        subject_ref: str = "",
        subject_title: str = "",
    ) -> ContextAnchor | None:
        if task_ref:
            return ContextAnchor(ref=task_ref, kind="task", title="진행 중 Task", source="task", resolved=True)
        if subject_ref:
            return ContextAnchor(
                ref=subject_ref,
                kind=subject_ref.partition(":")[0] or "subject",
                title=subject_title or subject_ref,
                source="goal",
                resolved=True,
                context_resolution="ontology_only",
            )
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
        subject_ref: str = "",
        subject_title: str = "",
        model_profile: str = "default",
    ) -> WorkContextPack:
        page_anchor = self.page_anchor(principal, page_ref)
        goal_anchor = self.goal_anchor(
            principal,
            session,
            task_ref,
            subject_ref=subject_ref,
            subject_title=subject_title,
        )
        selected = evidence[:12]
        task_exit = task.get("exit_criteria") or task.get("completion_conditions") or definition.completion_criteria
        required = task.get("required_evidence") or task.get("evidence_requirements") or []
        task_exit = [task_exit] if isinstance(task_exit, str) else list(task_exit or [])
        required = [required] if isinstance(required, str) else list(required or [])
        available_evidence_refs = {item.evidence_id for item in selected if item.evidence_id}
        for item in selected:
            for key in ("satisfies_evidence_refs", "requirement_refs"):
                values = item.metadata.get(key) if isinstance(item.metadata, dict) else None
                available_evidence_refs.update(_string_list(values, limit=100))
        missing = [item for item in required if str(item).strip() not in available_evidence_refs]
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
        now = datetime.now(timezone.utc)
        playbook_items: list[dict[str, Any]] = []
        for item in self.store.list("context_playbook_items", limit=1000):
            visibility = str(item.get("visibility") or "private")
            owner_visible = str(item.get("employee_id") or "") == principal.employee_id
            team_visible = visibility == "team" and bool(set(item.get("team_ids") or []) & set(principal.teams))
            if not (owner_visible or team_visible):
                continue
            item_status = str(item.get("status") or "")
            if item_status not in {"provisional", "active"}:
                continue
            if item_status == "provisional" and not owner_visible:
                continue
            valid_until = str((item.get("freshness") or {}).get("valid_until") or "")
            if valid_until:
                try:
                    expires = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if expires <= now:
                        continue
                except ValueError:
                    continue
            profiles = [str(value) for value in item.get("model_profiles") or ["default"]]
            if "default" not in profiles and model_profile not in profiles:
                continue
            applies_to = item.get("applies_to") if isinstance(item.get("applies_to"), dict) else {}
            if applies_to.get("capability_ids") and definition.capability_id not in applies_to["capability_ids"]:
                continue
            if applies_to.get("task_refs") and task_ref not in applies_to["task_refs"]:
                continue
            playbook_items.append(item)
        playbook_items.sort(
            key=lambda item: (
                str(item.get("status") or "") == "active",
                len(item.get("successful_run_ids") or []) - len(item.get("failed_run_ids") or []),
                str(item.get("updated_at") or item.get("created_at") or ""),
            ),
            reverse=True,
        )
        playbook_items = playbook_items[:6]
        if playbook_items:
            metadata["context_playbook"] = [
                {
                    "item_id": item.get("item_id"),
                    "description": item.get("description"),
                    "conditions": item.get("conditions") or [],
                    "source_refs": item.get("source_refs") or [],
                    "status": item.get("status"),
                    "revision": item.get("revision") or 1,
                    "model_profiles": item.get("model_profiles") or ["default"],
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
                "available": sorted(available_evidence_refs),
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
    FLOW = ["observe", "context", "semantic_plan", "act_or_ask", "verify", "reflect", "continue_or_stop"]

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

    def _append_checkpoint(
        self,
        run: dict[str, Any],
        *,
        node: str,
        raw_state: dict[str, Any],
        idempotency_key: str = "",
    ) -> WorkRunCheckpoint:
        checkpoint_ids = list(run.get("checkpoint_ids") or [])
        sequence = len(checkpoint_ids) + 1
        bindings = run.get("harness_bindings") or []
        harness_revisions = {
            str(item.get("harness_id") or ""): str(item.get("version") or "")
            for item in bindings
            if isinstance(item, dict) and item.get("harness_id")
        }
        revisions = run.get("contract_revisions") if isinstance(run.get("contract_revisions"), dict) else {}
        checkpoint = WorkRunCheckpoint(
            checkpoint_id=_id("checkpoint", f"{run['work_run_id']}:{sequence}:{node}"),
            work_run_id=str(run["work_run_id"]),
            node=node,  # type: ignore[arg-type]
            sequence=sequence,
            raw_state=raw_state,
            catalog_revision=str(revisions.get("capability_catalog") or ""),
            harness_revisions=harness_revisions,
            planner_schema_revision=str(revisions.get("planner_schema") or "semantic-plan/v2"),
            idempotency_key=idempotency_key,
        )
        self.store.put(
            "work_run_checkpoints",
            checkpoint.checkpoint_id,
            {
                "employee_id": run.get("employee_id") or "",
                **checkpoint.model_dump(mode="json"),
            },
        )
        run["checkpoint_ids"] = [*checkpoint_ids, checkpoint.checkpoint_id][-100:]
        run.setdefault("events", []).append(
            {
                "event": "work.checkpoint",
                "checkpoint_id": checkpoint.checkpoint_id,
                "node": checkpoint.node,
                "sequence": checkpoint.sequence,
                "at": now_iso(),
            }
        )
        return checkpoint

    @staticmethod
    def _valid_strategy_change(progress: ProgressDelta) -> bool:
        return bool(progress.strategy and progress.strategy_refs)

    def _append_progress(
        self,
        run: dict[str, Any],
        delta: LoopDelta,
    ) -> tuple[LoopDelta, ProgressDelta, bool, bool]:
        loop = run.setdefault("loop", {})
        progress_rows = list(loop.get("progress_deltas") or [])
        progress = _structured_progress(delta, sequence=len(progress_rows) + 1)
        signature = _progress_signature(progress)
        delta = delta.model_copy(update={"fingerprint": signature})
        state = loop.get("progress_state") if isinstance(loop.get("progress_state"), dict) else {}
        known_entities = set(_string_list(state.get("entity_refs"), limit=500))
        known_evidence = set(_string_list(state.get("evidence_refs"), limit=500))
        known_tools = set(_string_list(state.get("tool_result_refs"), limit=500))
        known_artifacts = set(_string_list(state.get("artifact_refs"), limit=500))
        known_blockers = set(_string_list(state.get("blocker_codes"), limit=200))
        known_completion = state.get("completion") if isinstance(state.get("completion"), dict) else {}
        completion_changed = any(known_completion.get(key) != value for key, value in progress.completion_changes.items())
        domain_progress = any(
            (
                set(progress.entity_refs) - known_entities,
                set(progress.evidence_refs) - known_evidence,
                set(progress.tool_result_refs) - known_tools,
                set(progress.artifact_refs) - known_artifacts,
                ({progress.blocker_code} - known_blockers) if progress.blocker_code and progress.blocker_code != "no_progress" else set(),
            )
        ) or completion_changed
        if delta.kind == "no_progress" or progress.kind == "strategy_change":
            domain_progress = False
        payload = progress.model_dump(mode="json")
        payload["signature"] = signature
        payload["domain_progress"] = domain_progress
        loop["progress_deltas"] = [*progress_rows, payload][-50:]
        loop["deltas"] = [*(loop.get("deltas") or []), delta.model_dump(mode="json")][-50:]
        if domain_progress:
            loop["progress_state"] = {
                "entity_refs": sorted(known_entities | set(progress.entity_refs)),
                "evidence_refs": sorted(known_evidence | set(progress.evidence_refs)),
                "tool_result_refs": sorted(known_tools | set(progress.tool_result_refs)),
                "artifact_refs": sorted(known_artifacts | set(progress.artifact_refs)),
                "blocker_codes": sorted(known_blockers | ({progress.blocker_code} if progress.blocker_code else set())),
                "completion": {**known_completion, **progress.completion_changes},
            }
        repeated = any(str(item.get("signature") or "") == signature for item in progress_rows)
        return delta, progress, domain_progress, repeated

    @staticmethod
    def _exit_result(
        *,
        context: WorkContextPack,
        mode: TaskMode,
        progress: ProgressDelta,
        confirmation: str | None,
        evidence_ledger_ids: list[str],
        standalone_action: bool = False,
        standalone_domain_confirmation: bool = False,
    ) -> ExitCriteriaResult:
        metadata_record = progress.completion_changes.get("work_record")
        work_record = metadata_record if isinstance(metadata_record, dict) else {}
        record_fields = ("observations", "actions", "judgment", "result")
        recorded_fields = [name for name in record_fields if str(work_record.get(name) or "").strip()]
        valid_record = len(recorded_fields) >= 2 and bool({"judgment", "result"} & set(recorded_fields))
        work_record_ref = str(work_record.get("work_record_ref") or "").strip()
        completion = context.completion_design
        checks = list(completion.checks) if completion else []
        binding_refs = {
            item.binding.ref
            for item in checks
            if item.binding is not None and item.binding.ref
        }
        verified_bindings = set(_string_list(progress.completion_changes.get("verified_binding_refs"), limit=100))
        completion_evidence = [
            item.model_dump(mode="python")
            for item in (completion.evidence if completion else [])
            if item.required
        ]
        if not completion_evidence:
            completion_evidence = [
                {
                    "evidence_id": str(item),
                    "label": str(item),
                    "ref": str(item),
                    "source_kind": "human_note",
                    "required": True,
                }
                for item in context.required_evidence
                if str(item).strip()
            ]
        available_evidence_refs = set(_string_list(context.evidence_summary.get("available"), limit=100))
        available_evidence_refs.update(progress.evidence_refs)
        available_evidence_refs.update(progress.tool_result_refs)
        record_evidence_refs = _string_list(work_record.get("evidence_refs"), limit=100)
        if work_record_ref:
            record_evidence_refs = _string_list([*record_evidence_refs, work_record_ref], limit=100)
        available_evidence_refs.update(record_evidence_refs)
        linked_refs_by_requirement = {
            str(requirement_id): record_evidence_refs
            for requirement_id in _string_list(work_record.get("satisfied_evidence_ids"), limit=100)
        }
        human_note_requirements = [
            str(item.get("evidence_id") or "").strip()
            for item in completion_evidence
            if str(item.get("source_kind") or "") == "human_note"
            and str(item.get("provided_by") or "human") == "human"
            and bool(item.get("required", True))
            and str(item.get("evidence_id") or "").strip()
        ]
        if (
            valid_record
            and confirmation == "confirm"
            and work_record_ref
            and len(human_note_requirements) == 1
        ):
            requirement_id = human_note_requirements[0]
            linked_refs_by_requirement[requirement_id] = _string_list(
                [*linked_refs_by_requirement.get(requirement_id, []), work_record_ref],
                limit=100,
            )
        evidence_status = evaluate_evidence_requirements(
            completion_evidence,
            available_refs=available_evidence_refs,
            linked_refs_by_requirement=linked_refs_by_requirement,
        )
        task_requires_evidence = bool(evidence_status["required_ids"])
        required_evidence_ready = not evidence_status["missing_ids"]
        has_ledger = bool(evidence_ledger_ids)
        criteria: list[HarnessCheck] = []
        if standalone_action:
            criteria.append(
                HarnessCheck(
                    check_id="exit.action-result",
                    label="검증된 Action 결과",
                    status="passed" if bool(progress.tool_result_refs) else "blocked",
                    message="검증된 Action 결과가 없습니다." if not progress.tool_result_refs else "",
                )
            )
        elif standalone_domain_confirmation:
            domain_status = str(progress.completion_changes.get("domain_result_status") or "").strip().lower()
            accepted_status = bool(domain_status) and domain_status not in {
                "failed",
                "rejected",
                "cancelled",
                "error",
            }
            criteria.extend(
                [
                    HarnessCheck(
                        check_id="exit.domain-outcome",
                        label="업무 서비스 결과",
                        status="passed" if accepted_status else "blocked",
                        message="확인된 업무 서비스 결과가 없습니다." if not accepted_status else "",
                    ),
                    HarnessCheck(
                        check_id="exit.human-confirmation",
                        label="담당자 최종 확인",
                        status="passed" if confirmation == "confirm" else "blocked",
                        message="담당자의 최종 확인이 필요합니다." if confirmation != "confirm" else "",
                    ),
                ]
            )
        elif mode in {TaskMode.manual, TaskMode.copilot}:
            criteria.extend(
                [
                    HarnessCheck(
                        check_id="exit.work-record",
                        label="업무 수행 기록",
                        status="passed" if valid_record else "blocked",
                        message="확인한 내용, 수행 조치, 판단 또는 결과가 포함된 업무 기록이 필요합니다." if not valid_record else "",
                    ),
                    HarnessCheck(
                        check_id="exit.human-confirmation",
                        label="담당자 최종 확인",
                        status="passed" if confirmation == "confirm" else "blocked",
                        message="담당자의 최종 확인이 필요합니다." if confirmation != "confirm" else "",
                    ),
                ]
            )
        else:
            system_ready = bool(binding_refs) and verified_bindings.issuperset(binding_refs)
            criteria.append(
                HarnessCheck(
                    check_id="exit.system-bindings",
                    label="시스템 완료 조건",
                    status="passed" if system_ready and bool(progress.tool_result_refs) else "blocked",
                    message="허용된 Action 결과와 시스템 완료 조건이 모두 검증되어야 합니다."
                    if not (system_ready and bool(progress.tool_result_refs))
                    else "",
                )
            )
        if task_requires_evidence:
            criteria.append(
                HarnessCheck(
                    check_id="exit.required-evidence",
                    label="필수 확인 자료",
                    status="passed" if required_evidence_ready else "blocked",
                    message=(
                        "필수 확인 자료가 실제 근거와 연결되지 않았습니다: "
                        + ", ".join(evidence_status["missing_ids"])
                    )
                    if not required_evidence_ready
                    else "",
                )
            )
        if task_requires_evidence or context.task_ref or standalone_action or standalone_domain_confirmation:
            criteria.append(
                HarnessCheck(
                    check_id="exit.evidence-ledger",
                    label="검증 근거 기록",
                    status="passed" if has_ledger else "blocked",
                    message="검증된 Evidence Ledger가 없습니다." if not has_ledger else "",
                )
            )
        satisfied = bool(criteria) and all(item.status == "passed" for item in criteria)
        return ExitCriteriaResult(
            satisfied=satisfied,
            criteria=criteria,
            evidence_ledger_ids=evidence_ledger_ids,
            evaluated_facts={
                "task_mode": mode.value,
                "work_record_fields": recorded_fields,
                "required_binding_refs": sorted(binding_refs),
                "verified_binding_refs": sorted(verified_bindings),
                "task_requires_evidence": task_requires_evidence,
                "required_evidence_ids": evidence_status["required_ids"],
                "satisfied_evidence_ids": evidence_status["satisfied_ids"],
                "missing_evidence_ids": evidence_status["missing_ids"],
                "evidence_satisfied_by": evidence_status["satisfied_by"],
                "standalone_domain_confirmation": standalone_domain_confirmation,
                "domain_result_status": str(progress.completion_changes.get("domain_result_status") or ""),
            },
            stop_reason="exit_criteria_satisfied" if satisfied else "needs_human",
        )

    def _notify_operational_change(self, record_id: str, employee_id: str) -> None:
        if self.knowledge_change_notifier is not None and record_id:
            self.knowledge_change_notifier(record_id, employee_id, "upsert")

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
                "loop_deltas": list((work_run.get("loop") or {}).get("deltas") or [])[-10:],
                "runtime_events": list(work_run.get("events") or [])[-10:],
                "tool_action_results": [
                    item
                    for item in (work_run.get("loop") or {}).get("deltas") or []
                    if isinstance(item, dict) and item.get("kind") in {"action_result", "state_transition", "blocker"}
                ][-10:],
                "user_corrections": [
                    item
                    for item in (work_run.get("loop") or {}).get("deltas") or []
                    if isinstance(item, dict) and item.get("kind") == "human_input"
                ][-10:],
                "reproducibility": "fixture_required",
                "scope": "recurrent_candidate" if len(blocked_checks) == 1 else "run_specific",
                "status": "open",
                "created_at": now_iso(),
            }
            pattern_seed = {
                "harness_id": result.harness_id,
                "phase": phase,
                "causal_stage": causal_stage,
                "mechanisms": sorted(record["exposed_mechanism"]),
                "cause": _compact(record["terminal_verifier_cause"], 300).casefold(),
            }
            pattern_id = _id(
                "hpattern",
                json.dumps(pattern_seed, ensure_ascii=False, sort_keys=True),
            )
            record["failure_pattern_id"] = pattern_id
            self.store.put("harness_failure_records", record_id, record)
            pattern = self.store.get("harness_failure_patterns", pattern_id) or {
                "failure_pattern_id": pattern_id,
                "harness_id": result.harness_id,
                "phase": phase,
                "causal_agent_stage": causal_stage,
                "exposed_mechanism": record["exposed_mechanism"],
                "summary": record["terminal_verifier_cause"],
                "failure_record_ids": [],
                "work_run_ids": [],
                "model_profiles": [],
                "first_seen_at": now_iso(),
                "status": "open",
            }
            pattern.update(
                {
                    "failure_record_ids": list(dict.fromkeys([*pattern.get("failure_record_ids", []), record_id]))[-200:],
                    "work_run_ids": list(dict.fromkeys([*pattern.get("work_run_ids", []), work_run["work_run_id"]]))[-200:],
                    "model_profiles": list(dict.fromkeys([*pattern.get("model_profiles", []), self.model_profile])),
                    "occurrence_count": int(pattern.get("occurrence_count") or 0) + 1,
                    "last_seen_at": now_iso(),
                }
            )
            self.store.put("harness_failure_patterns", pattern_id, pattern)
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
                    "failure_pattern_id": pattern_id,
                    "summary": record["terminal_verifier_cause"],
                    "source_refs": record["evidence_refs"],
                    "status": "active",
                    "created_at": now_iso(),
                },
            )
            self._notify_operational_change(pattern_id, principal.employee_id)
            record_ids.append(record_id)
        return record_ids

    def _record_negative_result(
        self,
        *,
        principal: Principal,
        kind: str,
        summary: str,
        work_run_id: str = "",
        source_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "kind": kind,
            "summary": _compact(summary, 2000),
            "work_run_id": work_run_id,
            "source_refs": list(dict.fromkeys(source_refs or []))[:50],
            "metadata": metadata or {},
        }
        negative_id = _id(
            "negative",
            f"{principal.employee_id}:{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}",
        )
        row = {
            "negative_result_id": negative_id,
            "employee_id": principal.employee_id,
            **payload,
            "status": "active",
            "created_at": now_iso(),
        }
        self.store.put("negative_results", negative_id, row)
        self._notify_operational_change(negative_id, principal.employee_id)
        return negative_id

    def list_harness_failures(self, principal: Principal, *, status: str = "open") -> dict[str, Any]:
        items = [
            item for item in self.store.list("harness_failure_records", limit=1000)
            if (principal.is_admin or str(item.get("employee_id") or "") == principal.employee_id)
            and (not status or str(item.get("status") or "") == status)
        ]
        return {"count": len(items), "items": items}

    def list_harness_failure_patterns(self, principal: Principal, *, status: str = "open") -> dict[str, Any]:
        visible_failure_ids = {
            str(item.get("failure_record_id") or "")
            for item in self.list_harness_failures(principal, status="")["items"]
        }
        items = [
            item for item in self.store.list("harness_failure_patterns", limit=1000)
            if (not status or str(item.get("status") or "") == status)
            and bool(set(item.get("failure_record_ids") or []) & visible_failure_ids)
        ]
        return {"count": len(items), "items": items}

    def list_negative_results(self, principal: Principal, *, status: str = "active") -> dict[str, Any]:
        items = [
            item for item in self.store.list("negative_results", limit=1000)
            if (principal.is_admin or str(item.get("employee_id") or "") == principal.employee_id)
            and (not status or str(item.get("status") or "") == status)
        ]
        return {"count": len(items), "items": items}

    def list_context_playbook(self, principal: Principal, *, status: str = "") -> dict[str, Any]:
        items = [
            item for item in self.store.list("context_playbook_items", limit=1000)
            if (
                principal.is_admin
                or str(item.get("employee_id") or "") == principal.employee_id
                or (
                    str(item.get("visibility") or "") == "team"
                    and bool(set(item.get("team_ids") or []) & set(principal.teams))
                )
            )
            and (not status or str(item.get("status") or "") == status)
        ]
        return {"count": len(items), "items": items}

    @staticmethod
    def _playbook_fingerprint(description: str, applies_to: dict[str, Any], model_profiles: list[str]) -> str:
        payload = {
            "description": _compact(description, 4000).casefold(),
            "applies_to": applies_to,
            "model_profiles": sorted(set(model_profiles or ["default"])),
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def create_context_playbook_item(self, principal: Principal, request: Any) -> dict[str, Any]:
        if request.visibility == "team" and not principal.teams and not principal.is_admin:
            raise HTTPException(status_code=403, detail="팀 Playbook 항목을 만들 권한이 없습니다.")
        if request.visibility == "team" and not principal.is_admin and not set(request.team_ids or principal.teams).issubset(set(principal.teams)):
            raise HTTPException(status_code=403, detail="소속되지 않은 팀의 Playbook 항목을 만들 수 없습니다.")
        for run_id in request.supporting_work_run_ids:
            run = self.store.get("work_runs", run_id)
            if not run or (not principal.is_admin and str(run.get("employee_id") or "") != principal.employee_id):
                raise HTTPException(status_code=404, detail="근거 WorkRun을 찾을 수 없습니다.")
        applies_to = {
            "capability_ids": list(dict.fromkeys(request.capability_ids)),
            "asset_kinds": list(dict.fromkeys(request.asset_kinds)),
            "task_refs": list(dict.fromkeys(request.task_refs)),
        }
        profiles = list(dict.fromkeys(request.model_profiles or ["default"]))
        fingerprint = self._playbook_fingerprint(request.description, applies_to, profiles)
        duplicate = next(
            (
                item for item in self.store.list("context_playbook_items", limit=1000)
                if item.get("fingerprint") == fingerprint
                and str(item.get("status") or "") not in {"deprecated", "rejected"}
                and (principal.is_admin or str(item.get("employee_id") or "") == principal.employee_id)
            ),
            None,
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail={"code": "context_playbook_duplicate", "existing_item_id": duplicate.get("item_id")},
            )
        item_id = _id("playbook", f"{principal.employee_id}:{fingerprint}")
        item = {
            "item_id": item_id,
            "employee_id": principal.employee_id,
            "description": _compact(request.description, 4000),
            "conditions": list(dict.fromkeys(_compact(item, 240) for item in request.conditions if _compact(item, 240))),
            "applies_to": applies_to,
            "team_ids": list(dict.fromkeys(request.team_ids or (principal.teams if request.visibility == "team" else []))),
            "model_profiles": profiles,
            "source_refs": list(dict.fromkeys(request.source_refs)),
            "supporting_work_run_ids": list(dict.fromkeys(request.supporting_work_run_ids)),
            "successful_run_ids": [],
            "failed_run_ids": [],
            "freshness": {"created_at": now_iso(), "valid_until": request.valid_until},
            "status": "provisional",
            "visibility": request.visibility,
            "fingerprint": fingerprint,
            "revision": 1,
            "deprecates_item_ids": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        stored = self.store.put("context_playbook_items", item_id, item)
        self._notify_operational_change(item_id, principal.employee_id)
        return stored

    def patch_context_playbook_item(self, principal: Principal, item_id: str, request: Any) -> dict[str, Any]:
        item = self.store.get("context_playbook_items", item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Context Playbook 항목을 찾을 수 없습니다.")
        if not principal.is_admin and str(item.get("employee_id") or "") != principal.employee_id:
            raise HTTPException(status_code=403, detail="이 Context Playbook 항목을 수정할 수 없습니다.")
        revision = int(item.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"code": "revision_conflict", "current_revision": revision})
        if request.status == "active" and not item.get("source_refs"):
            raise HTTPException(status_code=422, detail="출처 없는 Playbook 항목은 활성화할 수 없습니다.")
        if request.status == "active" and item.get("visibility") == "team" and not principal.is_admin:
            raise HTTPException(status_code=403, detail="팀 Playbook 활성화는 검토 권한이 필요합니다.")
        if request.description is not None:
            item["description"] = _compact(request.description, 4000)
        if request.valid_until is not None:
            item.setdefault("freshness", {})["valid_until"] = request.valid_until
        if request.status is not None:
            item["status"] = request.status
        if request.deprecates_item_ids is not None:
            for old_id in request.deprecates_item_ids:
                old = self.store.get("context_playbook_items", old_id)
                if not old:
                    raise HTTPException(status_code=404, detail=f"대체할 Playbook 항목을 찾을 수 없습니다: {old_id}")
                if not principal.is_admin and str(old.get("employee_id") or "") != principal.employee_id:
                    raise HTTPException(status_code=403, detail="다른 사용자의 Playbook 항목을 대체할 수 없습니다.")
                old.update({"status": "deprecated", "superseded_by": item_id, "updated_at": now_iso()})
                self.store.put("context_playbook_items", old_id, old)
            item["deprecates_item_ids"] = list(dict.fromkeys(request.deprecates_item_ids))
        item.update(
            {
                "review_note": _compact(request.review_note, 4000),
                "reviewed_by": principal.employee_id if request.status in {"active", "rejected"} else item.get("reviewed_by") or "",
                "revision": revision + 1,
                "updated_at": now_iso(),
            }
        )
        item["fingerprint"] = self._playbook_fingerprint(
            str(item.get("description") or ""),
            item.get("applies_to") or {},
            item.get("model_profiles") or ["default"],
        )
        duplicate = next(
            (
                row for row in self.store.list("context_playbook_items", limit=1000)
                if row.get("item_id") != item_id
                and row.get("fingerprint") == item["fingerprint"]
                and str(row.get("status") or "") not in {"deprecated", "rejected"}
                and (principal.is_admin or str(row.get("employee_id") or "") == principal.employee_id)
            ),
            None,
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail={"code": "context_playbook_duplicate", "existing_item_id": duplicate.get("item_id")},
            )
        stored = self.store.put("context_playbook_items", item_id, item)
        self._notify_operational_change(item_id, principal.employee_id)
        return stored

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
        self._validate_executable_harness_changes(request.changes)
        failures = [self.store.get("harness_failure_records", item) for item in request.failure_record_ids]
        if any(not item for item in failures):
            raise HTTPException(status_code=404, detail="실패 기록을 찾을 수 없습니다.")
        if not principal.is_admin and any(str(item.get("employee_id") or "") != principal.employee_id for item in failures if item):
            raise HTTPException(status_code=403, detail="다른 사용자의 실패 기록으로 후보를 만들 수 없습니다.")
        pattern_ids = list(
            dict.fromkeys(str(item.get("failure_pattern_id") or "") for item in failures if item and item.get("failure_pattern_id"))
        )
        recurrent = any(
            int((self.store.get("harness_failure_patterns", pattern_id) or {}).get("occurrence_count") or 0) >= 2
            for pattern_id in pattern_ids
        )
        candidate_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "harness_id": request.harness_id,
                    "base_version": definition.version,
                    "model_profile": request.model_profile,
                    "changes": request.changes,
                    "failure_pattern_ids": pattern_ids,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        candidate_id = _id("hcandidate", f"{request.harness_id}:{request.model_profile}:{now_iso()}")
        candidate = {
            "candidate_id": candidate_id,
            "employee_id": principal.employee_id,
            "harness_id": request.harness_id,
            "base_version": definition.version,
            "model_profile": request.model_profile,
            "failure_record_ids": request.failure_record_ids,
            "failure_pattern_ids": pattern_ids,
            "recurrent_pattern": recurrent,
            "changes": request.changes,
            "rationale": request.rationale,
            "status": "shadow_pending",
            "production_changed": False,
            "candidate_fingerprint": candidate_fingerprint,
            "created_at": now_iso(),
        }
        stored = self.store.put("harness_candidates", candidate_id, candidate)
        self._notify_operational_change(candidate_id, principal.employee_id)
        return stored

    @staticmethod
    def _candidate_addressable_stages(changes: dict[str, Any]) -> set[str]:
        prefixes: set[str] = set()
        if "retrieval_policy" in changes:
            prefixes.update({"context", "knowledge", "task.evidence"})
        if "loop_budget" in changes:
            prefixes.update({"loop", "task"})
        return prefixes

    @staticmethod
    def _validate_executable_harness_changes(changes: dict[str, Any]) -> None:
        retrieval = changes.get("retrieval_policy")
        if retrieval is not None:
            if not isinstance(retrieval, dict):
                raise HTTPException(status_code=400, detail={"code": "invalid_retrieval_policy"})
            allowed = {
                "lexical_weight", "semantic_weight", "graph_weight", "ontology_weight",
                "authority_weight", "recency_weight", "identity_weight", "context_anchor_weight",
            }
            unknown = sorted(set(retrieval) - allowed)
            invalid = sorted(
                key
                for key, value in retrieval.items()
                if isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.25 <= float(value) <= 2.0
            )
            if unknown or invalid:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_retrieval_policy",
                        "unsupported": unknown,
                        "out_of_range": invalid,
                    },
                )
        loop_budget = changes.get("loop_budget")
        if loop_budget is not None:
            if not isinstance(loop_budget, dict):
                raise HTTPException(status_code=400, detail={"code": "invalid_loop_budget"})
            allowed = {"max_iterations", "max_no_progress", "max_tool_loops"}
            unknown = sorted(set(loop_budget) - allowed)
            try:
                valid = (
                    1 <= int(loop_budget.get("max_iterations") or 5) <= 5
                    and int(loop_budget.get("max_no_progress") or 2) == 2
                    and 1 <= int(loop_budget.get("max_tool_loops") or 5) <= 5
                )
            except (TypeError, ValueError):
                valid = False
            if unknown or not valid:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "invalid_loop_budget", "unsupported": unknown},
                )

    def shadow_harness_candidate(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        candidate = self.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        if not principal.is_admin and str(candidate.get("employee_id") or "") != principal.employee_id:
            raise HTTPException(status_code=403, detail="이 Harness 후보를 시험할 수 없습니다.")
        definition = self.harnesses.definition(str(candidate.get("harness_id") or ""))
        forbidden = sorted(set(candidate.get("changes") or {}) & set(definition.immutable_boundaries))
        addressable = self._candidate_addressable_stages(candidate.get("changes") or {})
        failure_rows = [
            self.store.get("harness_failure_records", item) or {}
            for item in candidate.get("failure_record_ids") or []
        ]
        unresolved = [
            str(row.get("failure_record_id") or "")
            for row in failure_rows
            if str(row.get("causal_agent_stage") or "").split(".", 1)[0] not in addressable
        ]
        successful_runs = []
        for run in self.store.list("work_runs", limit=2000):
            if str(run.get("status") or "") != "completed":
                continue
            bindings = [item for item in run.get("harness_bindings") or [] if isinstance(item, dict)]
            if not any(
                item.get("harness_id") == candidate.get("harness_id")
                and item.get("model_profile") == candidate.get("model_profile")
                for item in bindings
            ):
                continue
            successful_runs.append(
                {
                    "work_run_id": run.get("work_run_id"),
                    "intent": run.get("intent"),
                    "harness_bindings": bindings,
                    "stop_reason": run.get("stop_reason") or "completed",
                }
            )
            if len(successful_runs) >= request.held_out_limit:
                break
        loop_change = (candidate.get("changes") or {}).get("loop_budget")
        bounded_loop = True
        if isinstance(loop_change, dict):
            bounded_loop = (
                1 <= int(loop_change.get("max_iterations") or 5) <= 5
                and int(loop_change.get("max_no_progress") or 2) == 2
                and 1 <= int(loop_change.get("max_tool_loops") or 5) <= 5
            )
        preflight_passed = not forbidden and not unresolved and bounded_loop and bool(failure_rows)
        shadow_run_id = _id("hshadow", f"{candidate_id}:{request.fixture_revision}:{now_iso()}")
        shadow = {
            "shadow_run_id": shadow_run_id,
            "candidate_id": candidate_id,
            "employee_id": principal.employee_id,
            "candidate_fingerprint": candidate.get("candidate_fingerprint"),
            "fixture_revision": request.fixture_revision,
            "status": "preflight_passed" if preflight_passed else "preflight_failed",
            "held_in_failure_record_ids": [str(item.get("failure_record_id") or "") for item in failure_rows],
            "unaddressed_failure_record_ids": unresolved,
            "held_out_preservation_runs": successful_runs,
            "adversarial": {
                "immutable_changes": forbidden,
                "bounded_loop": bounded_loop,
                "permission_layer_outside_candidate": True,
            },
            "production_changed": False,
            "created_at": now_iso(),
        }
        self.store.put("harness_shadow_runs", shadow_run_id, shadow)
        candidate.update(
            {
                "status": "shadow_ready" if preflight_passed else "shadow_preflight_failed",
                "latest_shadow_run_id": shadow_run_id,
                "updated_at": now_iso(),
            }
        )
        self.store.put("harness_candidates", candidate_id, candidate)
        self._notify_operational_change(candidate_id, principal.employee_id)
        return {"candidate": candidate, "shadow_run": shadow}

    def evaluate_harness_candidate(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        candidate = self.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        if not principal.is_admin and str(candidate.get("employee_id") or "") != principal.employee_id:
            raise HTTPException(status_code=403, detail="이 Harness 후보를 평가할 수 없습니다.")
        shadow = self.store.get("harness_shadow_runs", request.shadow_run_id)
        if not shadow or shadow.get("candidate_id") != candidate_id:
            raise HTTPException(status_code=409, detail="이 후보의 서버 shadow preflight가 필요합니다.")
        if shadow.get("status") != "preflight_passed":
            raise HTTPException(status_code=409, detail="서버 shadow preflight를 통과하지 못했습니다.")
        if shadow.get("candidate_fingerprint") != candidate.get("candidate_fingerprint"):
            raise HTTPException(status_code=409, detail="후보가 shadow preflight 이후 변경되었습니다.")
        if request.fixture_revision != shadow.get("fixture_revision"):
            raise HTTPException(status_code=409, detail="shadow와 평가 fixture revision이 다릅니다.")
        held_in_records = [
            self.store.get("harness_failure_records", str(item))
            for item in shadow.get("held_in_failure_record_ids") or []
        ]
        preservation_ids = [
            str(item.get("work_run_id") or "")
            for item in shadow.get("held_out_preservation_runs") or []
            if isinstance(item, dict) and item.get("work_run_id")
        ]
        preservation_runs = [self.store.get("work_runs", item) for item in preservation_ids]
        held_in_server_ok = bool(held_in_records) and all(held_in_records) and not shadow.get("unaddressed_failure_record_ids")
        held_out_server_ok = (
            bool(preservation_runs)
            and all(item and str(item.get("status") or "") == "completed" for item in preservation_runs)
        )
        shadow_adversarial = shadow.get("adversarial") if isinstance(shadow.get("adversarial"), dict) else {}
        adversarial_server_ok = (
            not shadow_adversarial.get("immutable_changes")
            and bool(shadow_adversarial.get("bounded_loop"))
            and bool(shadow_adversarial.get("permission_layer_outside_candidate"))
        )
        held_in_ok = request.held_in.get("passed") is True and held_in_server_ok
        held_out_ok = (
            request.held_out.get("passed") is True
            and int(request.held_out.get("regressions") or 0) == 0
            and held_out_server_ok
        )
        adversarial_ok = (
            request.adversarial.get("passed", True) is True
            and int(request.adversarial.get("unauthorized_mutations") or 0) == 0
            and adversarial_server_ok
        )
        long_term_ok = request.long_term.get("passed") is True and int(request.long_term.get("regressions") or 0) == 0
        metric_deltas = request.held_out.get("metric_deltas") if isinstance(request.held_out.get("metric_deltas"), dict) else {}
        regressed_metrics = sorted(
            key for key, value in metric_deltas.items() if isinstance(value, (int, float)) and float(value) < 0
        )
        eval_id = _id("heval", f"{candidate_id}:{request.fixture_revision}:{now_iso()}")
        evaluation = {
            "eval_id": eval_id,
            "candidate_id": candidate_id,
            "shadow_run_id": request.shadow_run_id,
            "employee_id": principal.employee_id,
            "fixture_revision": request.fixture_revision,
            "held_in": request.held_in,
            "held_out": request.held_out,
            "adversarial": request.adversarial,
            "long_term": request.long_term,
            "server_observations": {
                "held_in_failure_record_ids": [
                    str(item.get("failure_record_id") or "")
                    for item in held_in_records
                    if item
                ],
                "held_out_work_run_ids": preservation_ids,
                "held_in_verified": held_in_server_ok,
                "held_out_verified": held_out_server_ok,
                "adversarial_boundaries_verified": adversarial_server_ok,
            },
            "pareto": {
                "metric_deltas": metric_deltas,
                "regressed_metrics": regressed_metrics,
                "no_regression": not regressed_metrics,
            },
            "qualified": held_in_ok and held_out_ok and adversarial_ok and long_term_ok and not regressed_metrics,
            "production_changed": False,
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
        self._notify_operational_change(candidate_id, principal.employee_id)
        if not evaluation["qualified"]:
            self._record_negative_result(
                principal=principal,
                kind="rejected_harness_candidate",
                summary="Harness 후보가 held-in·held-out·adversarial·장기 기준 중 하나를 통과하지 못했습니다.",
                source_refs=[candidate_id, eval_id],
                metadata={"candidate_id": candidate_id, "eval_id": eval_id, "pareto": evaluation["pareto"]},
            )
        return {"candidate": candidate, "evaluation": evaluation}

    def review_harness_candidate(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        candidate = self.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        evaluation = self.store.get("harness_eval_runs", request.expected_eval_id)
        if not evaluation or evaluation.get("candidate_id") != candidate_id:
            raise HTTPException(status_code=409, detail="검토할 평가 결과가 현재 후보와 일치하지 않습니다.")
        if request.decision == "approve_for_release" and not evaluation.get("qualified"):
            raise HTTPException(status_code=409, detail="합격하지 않은 후보는 release 검토 승인할 수 없습니다.")
        status = {
            "approve_for_release": "approved_for_manual_release",
            "hold": "held",
            "reject": "rejected",
        }[request.decision]
        candidate.update(
            {
                "status": status,
                "review": {
                    "decision": request.decision,
                    "note": _compact(request.note, 4000),
                    "reviewed_by": principal.employee_id,
                    "reviewed_at": now_iso(),
                    "eval_id": request.expected_eval_id,
                },
                "production_changed": False,
                "updated_at": now_iso(),
            }
        )
        self.store.put("harness_candidates", candidate_id, candidate)
        version_id = ""
        if request.decision == "approve_for_release":
            version_id = _id("hversion", f"{candidate_id}:{request.expected_eval_id}")
            self.store.put(
                "harness_versions",
                version_id,
                {
                    "harness_version_id": version_id,
                    "harness_id": candidate.get("harness_id"),
                    "base_version": candidate.get("base_version"),
                    "model_profile": candidate.get("model_profile"),
                    "changes": candidate.get("changes"),
                    "candidate_id": candidate_id,
                    "eval_id": request.expected_eval_id,
                    "status": "approved_not_deployed",
                    "production_changed": False,
                    "rollback_version": candidate.get("base_version"),
                    "created_at": now_iso(),
                },
            )
        elif request.decision == "reject":
            self._record_negative_result(
                principal=principal,
                kind="review_rejected_harness_candidate",
                summary=request.note,
                source_refs=[candidate_id, request.expected_eval_id],
                metadata={"candidate_id": candidate_id, "eval_id": request.expected_eval_id},
            )
        self._notify_operational_change(version_id or candidate_id, principal.employee_id)
        return {"candidate": candidate, "harness_version_id": version_id, "production_changed": False}

    def release_harness_version(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        candidate = self.store.get("harness_candidates", candidate_id)
        version = self.store.get("harness_versions", request.expected_version_id)
        if not candidate or not version or version.get("candidate_id") != candidate_id:
            raise HTTPException(status_code=404, detail="배포할 Harness 버전을 찾을 수 없습니다.")
        if candidate.get("status") != "approved_for_manual_release" or version.get("status") != "approved_not_deployed":
            raise HTTPException(status_code=409, detail="사람 검토를 통과한 대기 버전만 배포할 수 있습니다.")
        if not request.user_confirmed:
            raise HTTPException(status_code=400, detail="Harness 버전 배포를 확인해주세요.")
        active_key = f"{version.get('harness_id')}:{version.get('model_profile') or 'default'}"
        previous = self.store.get("harness_active_versions", active_key) or {}
        audit_id = _id("haudit", f"release:{candidate_id}:{now_iso()}")
        result = {
            "operation": "release",
            "candidate_id": candidate_id,
            "harness_version_id": request.expected_version_id,
            "previous_version": previous.get("harness_version_id") or version.get("rollback_version"),
            "rehearsal": bool(request.rehearsal),
            "production_changed": not request.rehearsal,
            "note": _compact(request.note, 4000),
            "actor_employee_id": principal.employee_id,
            "created_at": now_iso(),
        }
        self.store.put("harness_release_audits", audit_id, {"audit_id": audit_id, **result})
        if request.rehearsal:
            return result
        self.store.put(
            "harness_active_versions",
            active_key,
            {
                "active_key": active_key,
                "harness_id": version.get("harness_id"),
                "model_profile": version.get("model_profile") or "default",
                "harness_version_id": request.expected_version_id,
                "changes": version.get("changes") or {},
                "previous_version": result["previous_version"],
                "activated_by": principal.employee_id,
                "activated_at": now_iso(),
            },
        )
        version.update({"status": "active", "production_changed": True, "activated_at": now_iso()})
        candidate.update({"status": "released", "production_changed": True, "updated_at": now_iso()})
        self.store.put("harness_versions", request.expected_version_id, version)
        self.store.put("harness_candidates", candidate_id, candidate)
        self._notify_operational_change(request.expected_version_id, principal.employee_id)
        return result

    def rollback_harness_version(self, principal: Principal, candidate_id: str, request: Any) -> dict[str, Any]:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        candidate = self.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        version = next(
            (item for item in self.store.list("harness_versions", limit=1000) if item.get("candidate_id") == candidate_id and item.get("status") == "active"),
            None,
        )
        if not version:
            raise HTTPException(status_code=409, detail="현재 활성화된 Harness 후보 버전이 없습니다.")
        if not request.user_confirmed:
            raise HTTPException(status_code=400, detail="Harness 버전 되돌리기를 확인해주세요.")
        active_key = f"{version.get('harness_id')}:{version.get('model_profile') or 'default'}"
        audit_id = _id("haudit", f"rollback:{candidate_id}:{now_iso()}")
        result = {
            "operation": "rollback",
            "candidate_id": candidate_id,
            "harness_version_id": version.get("harness_version_id"),
            "rollback_version": version.get("rollback_version"),
            "rehearsal": bool(request.rehearsal),
            "production_changed": not request.rehearsal,
            "note": _compact(request.note, 4000),
            "actor_employee_id": principal.employee_id,
            "created_at": now_iso(),
        }
        self.store.put("harness_release_audits", audit_id, {"audit_id": audit_id, **result})
        if request.rehearsal:
            return result
        self.store.delete("harness_active_versions", active_key)
        version.update({"status": "rolled_back", "production_changed": False, "rolled_back_at": now_iso()})
        candidate.update({"status": "rolled_back", "production_changed": False, "updated_at": now_iso()})
        self.store.put("harness_versions", str(version["harness_version_id"]), version)
        self.store.put("harness_candidates", candidate_id, candidate)
        self._notify_operational_change(str(version["harness_version_id"]), principal.employee_id)
        return result

    def effective_harness_bindings(self, harness_ids: list[str]) -> list[dict[str, Any]]:
        bindings = self.harnesses.bindings(harness_ids, self.model_profile)
        for binding in bindings:
            active_key = f"{binding.get('harness_id')}:{self.model_profile}"
            active = self.store.get("harness_active_versions", active_key)
            if active:
                binding.update(
                    {
                        "version": active.get("harness_version_id"),
                        "active_changes": active.get("changes") or {},
                        "release_state": "active_reviewed_version",
                    }
                )
        return bindings

    @staticmethod
    def retrieval_policy(bindings: list[dict[str, Any]]) -> dict[str, float]:
        policy: dict[str, float] = {}
        for binding in bindings:
            changes = binding.get("active_changes") if isinstance(binding, dict) else {}
            retrieval = changes.get("retrieval_policy") if isinstance(changes, dict) else None
            if not isinstance(retrieval, dict):
                continue
            for key, value in retrieval.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    policy[str(key)] = float(value)
        return policy

    @staticmethod
    def _binding_for(
        bindings: list[dict[str, Any]],
        harness_id: str,
    ) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in bindings
                if isinstance(item, dict) and str(item.get("harness_id") or "") == harness_id
            ),
            None,
        )

    @staticmethod
    def _pinned_harness_ids(
        bindings: list[dict[str, Any]],
        *,
        operation: str,
        phase: str,
    ) -> list[str]:
        selected: list[str] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            definition = binding.get("definition") if isinstance(binding.get("definition"), dict) else {}
            phases = {str(item) for item in definition.get("phases") or []}
            operations = {str(item) for item in definition.get("operations") or []}
            harness_id = str(binding.get("harness_id") or "")
            if harness_id and (not phases or phase in phases) and (not operations or operation in operations):
                selected.append(harness_id)
        return list(dict.fromkeys(selected))

    @staticmethod
    def _apply_pinned_loop_budget(
        policy: LoopPolicy,
        bindings: list[dict[str, Any]],
    ) -> LoopPolicy:
        budgets = [
            changes.get("loop_budget")
            for item in bindings
            if isinstance(item, dict)
            for changes in [item.get("active_changes") if isinstance(item.get("active_changes"), dict) else {}]
            if isinstance(changes.get("loop_budget"), dict)
        ]
        if not budgets:
            return policy
        max_iterations = min(
            [policy.max_iterations, *[int(item.get("max_iterations") or policy.max_iterations) for item in budgets]]
        )
        max_tool_loops = min(
            [policy.max_tool_loops, *[int(item.get("max_tool_loops") or policy.max_tool_loops) for item in budgets]]
        )
        max_no_progress = min(
            [policy.max_no_progress, *[int(item.get("max_no_progress") or policy.max_no_progress) for item in budgets]]
        )
        return policy.model_copy(
            update={
                "max_iterations": max(1, min(5, max_iterations)),
                "max_tool_loops": max(1, min(5, max_tool_loops)),
                # The loop contract stops after the second consecutive
                # no-progress result. Reviewed candidates may tighten work and
                # tool budgets, but cannot weaken this invariant.
                "max_no_progress": 2,
            }
        )

    @staticmethod
    def resolve_loop_policy(
        intent: WorkIntent,
        policy: LoopPolicy | dict[str, Any] | None = None,
    ) -> LoopPolicy:
        selected = policy if policy is not None else intent.loop_contract
        if isinstance(selected, LoopPolicy):
            return selected
        if hasattr(selected, "model_dump"):
            selected = selected.model_dump(mode="json")
        return LoopPolicy.model_validate(selected)

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
        catalog_revision: str = "",
        planner_schema_revision: str = "semantic-plan/v2",
        semantic_plan_ref: str = "",
        pinned_harness_bindings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        work_run_id = _id("workrun", f"{agent_run_id}:{principal.employee_id}")
        all_harness_ids = self.harnesses.harnesses_for(
            intent,
            intent.asset_kind.value,
        )
        effective_bindings = self.effective_harness_bindings(all_harness_ids)
        pinned_by_id = {
            str(item.get("harness_id") or ""): item
            for item in (pinned_harness_bindings or [])
            if isinstance(item, dict) and item.get("harness_id")
        }
        harness_bindings = [
            pinned_by_id.get(str(item.get("harness_id") or ""), item)
            for item in effective_bindings
        ]
        preflight_ids = self._pinned_harness_ids(
            harness_bindings,
            operation=intent.operation.value,
            phase="preflight",
        )
        preflights = [
            self.harnesses.evaluate(
                harness_id,
                phase="preflight",
                intent=intent,
                context=context,
                task_mode=context.task_mode,
                binding=self._binding_for(harness_bindings, harness_id),
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
        resolved_loop_policy = self._apply_pinned_loop_budget(
            self.resolve_loop_policy(intent, loop_policy),
            harness_bindings,
        )
        run = {
            "work_run_id": work_run_id,
            "agent_run_id": agent_run_id,
            "employee_id": principal.employee_id,
            "work_session_id": session.get("session_id") or "",
            "context_id": context.context_id,
            "goal_plan_id": goal_plan_id,
            "semantic_plan_ref": semantic_plan_ref,
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
                "tool_loop_count": 0,
                "deltas": [],
                "progress_deltas": [],
                "progress_state": {
                    "entity_refs": [],
                    "evidence_refs": [item.evidence_id for item in context.evidence_refs],
                    "tool_result_refs": [],
                    "artifact_refs": [],
                    "blocker_codes": [],
                    "completion": {},
                },
                "idempotency_keys": [],
            },
            "harness_results": [item.model_dump(mode="json") for item in preflights],
            "harness_bindings": harness_bindings,
            "contract_revisions": {
                "capability_catalog": catalog_revision,
                "harness_catalog": self.harnesses.version,
                "planner_schema": planner_schema_revision,
            },
            "checkpoint_ids": [],
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
        self._append_checkpoint(
            run,
            node="observe",
            raw_state={
                "agent_run_id": agent_run_id,
                "session_id": session.get("session_id") or "",
                "task_mode": context.task_mode.value,
                "loop_policy": resolved_loop_policy.model_dump(mode="json"),
            },
        )
        self._append_checkpoint(
            run,
            node="context",
            raw_state={
                "context_id": context.context_id,
                "task_ref": context.task_ref,
                "workflow_ref": context.workflow_ref,
                "evidence_refs": [item.evidence_id for item in context.evidence_refs],
                "context_manifest": context.context_manifest.model_dump(mode="json")
                if context.context_manifest
                else {},
            },
        )
        self._append_checkpoint(
            run,
            node="semantic_plan",
            raw_state={
                "semantic_plan_ref": semantic_plan_ref,
                "goal_plan_id": goal_plan_id,
                "intent": intent.model_dump(mode="json"),
            },
        )
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
        artifact_kind = str(artifact.get("artifact_type") or artifact.get("kind") or "")
        results: list[HarnessResult] = []
        pinned_bindings = [
            item
            for item in work_run.get("harness_bindings") or []
            if isinstance(item, dict)
        ]
        post_verify_ids = self._pinned_harness_ids(
            pinned_bindings,
            operation=intent.operation.value,
            phase="post_verify",
        )
        for harness_id in post_verify_ids:
            result = self.harnesses.evaluate(
                harness_id,
                phase="post_verify",
                intent=intent,
                context=context,
                artifact=artifact,
                task_mode=context.task_mode,
                binding=self._binding_for(pinned_bindings, harness_id),
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
        if job_id:
            delta_kind = "state_transition"
        elif artifacts:
            delta_kind = "new_artifact"
        elif evidence_refs:
            delta_kind = "new_evidence"
        elif blocked or response_status in {"failed", "blocked"}:
            delta_kind = "blocker"
        else:
            # Waiting for Task input is a normal state transition, not a blocker.
            delta_kind = "state_transition"
        delta = LoopDelta(
            kind=delta_kind,  # type: ignore[arg-type]
            summary=("심층 작업이 대기열에 등록되었습니다." if job_id else answer_summary),
            ref=job_id or str(artifact.get("artifact_id") or (evidence_refs[0] if evidence_refs else "")),
            metadata={
                "evidence_refs": evidence_refs,
                "artifact_refs": [str(item.get("artifact_id") or "") for item in artifacts if item.get("artifact_id")],
                "completion_changes": {"response_status": response_status},
                "blocker_code": "harness_blocked" if blocked else "response_failed" if response_status == "failed" else "",
                "error_disposition": "policy_stop" if blocked else "unexpected_failure" if response_status == "failed" else "",
            },
        )
        loop = dict(work_run.get("loop") or {})
        work_run["loop"] = loop
        delta, progress_delta, _, _ = self._append_progress(work_run, delta)
        loop = dict(work_run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
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
        ledger_ids = list(
            dict.fromkeys([*work_run.get("evidence_ledger_ids", []), *added_ledger_ids])
        )[:100]
        eligible_complete = False
        if response_status == "failed" or blocked:
            status, decision, stop_reason = "blocked", "blocked", "policy_stop" if blocked else "unexpected_failure"
        elif response_status == "queued":
            status, decision, stop_reason = "queued", "continue", ""
        elif intent.operation == WorkOperation.complete and not intent.needs_clarification:
            if context.task_mode == TaskMode.autopilot:
                status, decision, stop_reason = "waiting_signal", "continue", "needs_human"
            else:
                status, decision, stop_reason = "waiting_human", "needs_human", "needs_human"
        elif response_status == "needs_input" or intent.needs_clarification:
            status, decision, stop_reason = "waiting_human", "needs_human", "needs_human"
        elif context.task_ref and intent.asset_kind == WorkAssetKind.task:
            if context.task_mode == TaskMode.autopilot:
                status, decision, stop_reason = "waiting_signal", "continue", "needs_human"
            else:
                status, decision, stop_reason = "waiting_human", "needs_human", "needs_human"
        elif artifacts and intent.operation in {WorkOperation.validate, WorkOperation.test}:
            eligible_complete = True
            status, decision, stop_reason = "completed", "complete", "exit_criteria_satisfied"
        elif artifacts and artifact_kind in {
            "mermaid_diagram",
            "ontology_graph",
            "knowledge_graph",
            "data_table",
            "timeline",
        }:
            eligible_complete = True
            status, decision, stop_reason = "completed", "complete", "exit_criteria_satisfied"
        elif artifacts:
            status, decision, stop_reason = "waiting_review", "needs_human", "needs_human"
        elif intent.operation in {
            WorkOperation.complete,
            WorkOperation.test,
            WorkOperation.run,
            WorkOperation.promote,
        }:
            status, decision, stop_reason = "waiting_human", "needs_human", "needs_human"
        else:
            eligible_complete = True
            status, decision, stop_reason = "completed", "complete", "exit_criteria_satisfied"
        exit_checks = [
            HarnessCheck(
                check_id="exit.operation-outcome",
                label="업무 결과",
                status="passed" if eligible_complete else "blocked",
                message="검토, 사람 입력 또는 실행 결과가 더 필요합니다." if not eligible_complete else "",
            ),
            HarnessCheck(
                check_id="exit.harness",
                label="Harness 검증",
                status="passed" if not blocked and response_status != "failed" else "blocked",
                message="Harness 또는 실행 결과 검증을 통과하지 못했습니다."
                if blocked or response_status == "failed"
                else "",
            ),
        ]
        if evidence_refs:
            exit_checks.append(
                HarnessCheck(
                    check_id="exit.evidence-ledger",
                    label="사용 근거 기록",
                    status="passed" if ledger_ids else "blocked",
                    message="사용한 근거가 Evidence Ledger에 기록되지 않았습니다." if not ledger_ids else "",
                )
            )
        exit_result = ExitCriteriaResult(
            satisfied=bool(exit_checks) and all(item.status == "passed" for item in exit_checks),
            criteria=exit_checks,
            evidence_ledger_ids=ledger_ids,
            evaluated_facts={
                "response_status": response_status,
                "artifact_count": len(artifacts),
                "evidence_count": len(evidence_refs),
                "harness_blocked": blocked,
            },
            stop_reason="exit_criteria_satisfied" if eligible_complete and not blocked else "needs_human",
        )
        if status == "completed" and not exit_result.satisfied:
            status, decision, stop_reason = "waiting_human", "needs_human", "needs_human"
        work_run.update(
            {
                "status": status,
                "decision": decision,
                "stop_reason": stop_reason,
                "loop": loop,
                "artifact_refs": [str(item.get("artifact_id") or "") for item in artifacts if item.get("artifact_id")],
                "evidence_refs": list(dict.fromkeys([*work_run.get("evidence_refs", []), *evidence_refs]))[:50],
                "job_id": job_id or work_run.get("job_id") or "",
                "harness_results": [
                    *work_run.get("harness_results", []),
                    *[item.model_dump(mode="json") for item in results],
                ],
                "evidence_ledger_ids": ledger_ids,
                "exit_criteria_result": exit_result.model_dump(mode="json"),
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
        self._append_checkpoint(
            work_run,
            node="act",
            raw_state={
                "progress_delta": progress_delta.model_dump(mode="json"),
                "artifact_refs": work_run.get("artifact_refs") or [],
                "job_id": job_id,
            },
        )
        self._append_checkpoint(
            work_run,
            node="verify",
            raw_state={
                "harness_results": [item.model_dump(mode="json") for item in results],
                "exit_criteria": exit_result.model_dump(mode="json"),
            },
        )
        self._append_checkpoint(
            work_run,
            node="reflect",
            raw_state={"status": status, "decision": decision, "stop_reason": stop_reason},
        )
        if status in {"completed", "blocked"}:
            self._append_checkpoint(
                work_run,
                node="stop",
                raw_state={"status": status, "decision": decision, "exit_criteria": exit_result.model_dump(mode="json")},
            )
        elif status in {"waiting_human", "waiting_review", "waiting_signal"}:
            self._append_checkpoint(
                work_run,
                node="ask",
                raw_state={"status": status, "decision": decision, "stop_reason": stop_reason},
            )
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
                playbook_applies_to = {
                    "capability_ids": [context.capability_id],
                    "asset_kinds": [intent.asset_kind.value],
                    "task_refs": [context.task_ref] if context.task_ref else [],
                }
                self.store.put(
                    "context_playbook_items",
                    playbook_id,
                    {
                        "item_id": playbook_id,
                        "employee_id": principal.employee_id,
                        "description": answer_summary,
                        "conditions": [intent.asset_kind.value, intent.operation.value],
                        "applies_to": {
                            **playbook_applies_to,
                        },
                        "team_ids": [],
                        "model_profiles": [self.model_profile],
                        "source_refs": evidence_refs,
                        "supporting_work_run_ids": [work_run["work_run_id"]],
                        "successful_run_ids": [work_run["work_run_id"]],
                        "failed_run_ids": [],
                        "freshness": {"created_at": now_iso(), "valid_until": ""},
                        "status": "provisional",
                        "visibility": "private",
                        "fingerprint": self._playbook_fingerprint(
                            answer_summary,
                            playbook_applies_to,
                            [self.model_profile],
                        ),
                        "revision": 1,
                        "deprecates_item_ids": [],
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
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
            kind="action_result" if successful else "blocker",
            summary=_compact(summary, 2000),
            ref=result_ref,
            metadata={
                **(metadata or {}),
                "tool_result_refs": [result_ref] if successful and result_ref else [],
                "completion_changes": {"result_status": result_status},
                "blocker_code": "system_operation_failed" if not successful else "",
                "error_disposition": "unexpected_failure" if not successful else "",
            },
        )
        loop = dict(work_run.get("loop") or {})
        work_run["loop"] = loop
        delta, progress_delta, _, _ = self._append_progress(work_run, delta)
        loop = dict(work_run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
        loop["no_progress_count"] = 0
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
        exit_result = ExitCriteriaResult(
            satisfied=successful and bool(result_ref) and bool(ledger_ids),
            criteria=[
                HarnessCheck(
                    check_id="exit.system-result",
                    label="시스템 실행 결과",
                    status="passed" if successful and bool(result_ref) else "blocked",
                    message="검증 가능한 시스템 실행 결과가 없습니다." if not (successful and result_ref) else "",
                ),
                HarnessCheck(
                    check_id="exit.evidence-ledger",
                    label="실행 근거 기록",
                    status="passed" if bool(ledger_ids) else "blocked",
                    message="시스템 실행 결과가 Evidence Ledger에 기록되지 않았습니다." if not ledger_ids else "",
                ),
            ],
            evidence_ledger_ids=ledger_ids,
            evaluated_facts={"result_status": result_status, "result_ref": result_ref},
            stop_reason="exit_criteria_satisfied" if successful and result_ref and ledger_ids else "blocked",
        )
        successful = successful and exit_result.satisfied
        work_run.update(
            {
                "status": "completed" if successful else "blocked",
                "decision": "complete" if successful else "blocked",
                "stop_reason": "exit_criteria_satisfied" if successful else "unexpected_failure",
                "loop": loop,
                "evidence_ledger_ids": list(dict.fromkeys(ledger_ids))[:100],
                "exit_criteria_result": exit_result.model_dump(mode="json"),
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
        self._append_checkpoint(
            work_run,
            node="act",
            raw_state={"progress_delta": progress_delta.model_dump(mode="json")},
        )
        self._append_checkpoint(
            work_run,
            node="verify",
            raw_state={"exit_criteria": exit_result.model_dump(mode="json")},
        )
        self._append_checkpoint(
            work_run,
            node="reflect",
            raw_state={"status": work_run["status"], "decision": work_run["decision"]},
        )
        self._append_checkpoint(
            work_run,
            node="stop",
            raw_state={"status": work_run["status"], "exit_criteria": exit_result.model_dump(mode="json")},
        )
        if not successful:
            negative_id = self._record_negative_result(
                principal=principal,
                kind="failed_system_operation",
                summary=summary,
                work_run_id=str(work_run["work_run_id"]),
                source_refs=[result_ref] if result_ref else [],
                metadata={"result_status": result_status, **(metadata or {})},
            )
            work_run["negative_result_ids"] = list(
                dict.fromkeys([*work_run.get("negative_result_ids", []), negative_id])
            )
        return self.store.put("work_runs", str(work_run["work_run_id"]), work_run)

    def fail_run(
        self,
        principal: Principal,
        work_run_id: str,
        message: str,
        *,
        disposition: str = "unexpected_failure",
    ) -> dict[str, Any]:
        run = self.get_run(principal, work_run_id)
        allowed = {"transient_retry", "semantic_repair", "human_interrupt", "policy_stop", "unexpected_failure"}
        disposition = disposition if disposition in allowed else "unexpected_failure"
        delta = LoopDelta(
            kind="blocker",
            summary=_compact(message, 2000),
            metadata={"blocker_code": disposition, "error_disposition": disposition},
        )
        loop = dict(run.get("loop") or {})
        run["loop"] = loop
        delta, progress_delta, _, _ = self._append_progress(run, delta)
        loop = dict(run.get("loop") or {})
        loop["iteration_count"] = int(loop.get("iteration_count") or 0) + 1
        if disposition in {"transient_retry", "semantic_repair"}:
            status, decision, stop_reason = "in_progress", "continue", disposition
        elif disposition == "human_interrupt":
            status, decision, stop_reason = "waiting_human", "needs_human", disposition
        elif disposition == "policy_stop":
            status, decision, stop_reason = "stopped", "stop", disposition
        else:
            status, decision, stop_reason = "blocked", "blocked", "unexpected_failure"
        if (
            disposition in {"transient_retry", "semantic_repair"}
            and int(loop.get("iteration_count") or 0) >= int(loop.get("max_iterations") or 5)
        ):
            status, decision, stop_reason = "stopped", "stop", "max_iterations"
            disposition = "policy_stop"
        run.update(
            {
                "status": status,
                "decision": decision,
                "stop_reason": stop_reason,
                "error_disposition": disposition,
                "loop": loop,
                "revision": int(run.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        run.setdefault("events", []).append(
            {
                "event": (
                    "work.retryable"
                    if status == "in_progress"
                    else "work.interrupted"
                    if status == "waiting_human"
                    else "work.stopped"
                    if status == "stopped"
                    else "work.blocked"
                ),
                "delta": delta.model_dump(mode="json"),
                "at": now_iso(),
            }
        )
        self._append_checkpoint(
            run,
            node="verify",
            raw_state={"progress_delta": progress_delta.model_dump(mode="json"), "error_disposition": disposition},
        )
        self._append_checkpoint(
            run,
            node="reflect",
            raw_state={"status": status, "decision": decision, "error_disposition": disposition},
        )
        if status in {"stopped", "blocked"}:
            self._append_checkpoint(
                run,
                node="stop",
                raw_state={"status": status, "error_disposition": disposition},
            )
        negative_id = self._record_negative_result(
            principal=principal,
            kind="failed_work_run",
            summary=message,
            work_run_id=work_run_id,
            source_refs=list(run.get("evidence_refs") or []),
            metadata={"stop_reason": disposition},
        )
        run["negative_result_ids"] = list(dict.fromkeys([*run.get("negative_result_ids", []), negative_id]))
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
        checkpoint_ids = set(run.get("checkpoint_ids") or [])
        run["checkpoints"] = sorted(
            [
                item
                for item in self.store.list(
                    "work_run_checkpoints",
                    employee_id=principal.employee_id,
                    limit=500,
                )
                if item.get("checkpoint_id") in checkpoint_ids and item.get("work_run_id") == work_run_id
            ],
            key=lambda item: int(item.get("sequence") or 0),
        )
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
        existing_loop = run.get("loop") if isinstance(run.get("loop"), dict) else {}
        if request.idempotency_key and request.idempotency_key in set(existing_loop.get("idempotency_keys") or []):
            return run, []
        revision = int(run.get("revision") or 1)
        if request.expected_revision != revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "current_revision": revision, "work_run": run})
        if run.get("status") in {"completed", "failed", "cancelled", "stopped"}:
            raise HTTPException(status_code=409, detail=f"work run is already {run.get('status')}")
        mode = TaskMode(str(run.get("task_mode") or "copilot"))
        context_row = self.store.get("contexts", str(run.get("context_id") or "")) or {}
        context = WorkContextPack.model_validate(context_row)
        intent = WorkIntent.model_validate(run.get("intent") or {})
        delta = request.delta
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        if mode == TaskMode.autopilot and delta.kind in {"action_result", "state_transition"} and delta.ref:
            binding_refs = {
                item.binding.ref
                for item in (context.completion_design.checks if context.completion_design else [])
                if item.binding is not None and item.binding.ref
            }
            if delta.ref in binding_refs:
                metadata = {
                    **metadata,
                    "verified_binding_refs": _string_list(
                        [*_string_list(metadata.get("verified_binding_refs")), delta.ref]
                    ),
                    "tool_result_refs": _string_list(
                        [*_string_list(metadata.get("tool_result_refs")), delta.ref]
                    ),
                }
                delta = delta.model_copy(update={"metadata": metadata})
        work_record = metadata.get("work_record") if isinstance(metadata.get("work_record"), dict) else {}
        if work_record:
            record_payload = json.dumps(work_record, ensure_ascii=False, sort_keys=True, default=str)
            work_record_ref = str(work_record.get("work_record_ref") or "").strip() or _id(
                "workrecord",
                f"{work_run_id}:{revision}:{record_payload}",
            )
            work_record = {**work_record, "work_record_ref": work_record_ref}
            metadata = {
                **metadata,
                "work_record": work_record,
                "evidence_refs": _string_list(
                    [*_string_list(metadata.get("evidence_refs")), work_record_ref],
                    limit=100,
                ),
            }
            delta = delta.model_copy(
                update={
                    "ref": delta.ref or work_record_ref,
                    "metadata": metadata,
                }
            )
        loop = dict(run.get("loop") or {})
        run["loop"] = loop
        delta, progress_delta, domain_progress, repeated = self._append_progress(run, delta)
        loop = dict(run.get("loop") or {})
        valid_strategy_change = self._valid_strategy_change(progress_delta)
        previous_no_progress = int(loop.get("no_progress_count") or 0)
        strategy_change_used = bool(loop.get("strategy_change_used"))
        if domain_progress:
            no_progress_count = 0
            strategy_change_used = False
        elif valid_strategy_change and not strategy_change_used:
            no_progress_count = max(1, previous_no_progress)
            strategy_change_used = True
        else:
            no_progress_count = previous_no_progress + 1
        iteration = int(loop.get("iteration_count") or 0) + 1
        tool_loop_count = int(loop.get("tool_loop_count") or 0)
        if delta.kind == "action_result" or progress_delta.tool_result_refs:
            tool_loop_count += 1
        loop.update(
            {
                "iteration_count": iteration,
                "tool_loop_count": tool_loop_count,
                "no_progress_count": no_progress_count,
                "strategy_change_used": strategy_change_used,
                "idempotency_keys": list(
                    dict.fromkeys([*(loop.get("idempotency_keys") or []), request.idempotency_key])
                )[-100:]
                if request.idempotency_key
                else list(loop.get("idempotency_keys") or []),
            }
        )
        standalone_action_complete = (
            intent.operation in {WorkOperation.test, WorkOperation.run}
            and intent.asset_kind.value == "action"
            and not context.task_ref
            and delta.kind == "action_result"
            and bool(delta.ref)
        )
        standalone_domain_confirmation = (
            not context.task_ref
            and request.confirmation == "confirm"
            and delta.kind == "human_input"
            and bool(delta.ref)
            and bool(str(metadata.get("domain_operation") or "").strip())
            and bool(str(metadata.get("domain_result_status") or "").strip())
        )
        ledger_refs = list(
            dict.fromkeys(
                [
                    *progress_delta.evidence_refs,
                    *progress_delta.tool_result_refs,
                    *progress_delta.artifact_refs,
                    *([delta.ref] if delta.kind == "human_input" and delta.ref else []),
                ]
            )
        )
        ledger_ids = list(run.get("evidence_ledger_ids") or [])
        for ref in ledger_refs:
            ledger_ids.append(
                self._record_evidence(
                    principal=principal,
                    work_run_id=work_run_id,
                    evidence_id=ref,
                    kind=delta.kind,
                    title=delta.summary or ref,
                    summary=delta.summary,
                    source="human" if delta.kind == "human_input" else "runtime",
                    authority="confirmed" if request.confirmation == "confirm" else "runtime",
                    verification="confirmed" if request.confirmation == "confirm" else "observed",
                )
            )
        ledger_ids = list(dict.fromkeys(ledger_ids))[:100]
        completion_attempt = standalone_action_complete or standalone_domain_confirmation or (
            request.confirmation == "confirm" and delta.kind in {"human_input", "state_transition"}
        ) or (mode == TaskMode.autopilot and delta.kind in {"action_result", "state_transition"})
        exit_result = self._exit_result(
            context=context,
            mode=mode,
            progress=progress_delta,
            confirmation=request.confirmation,
            evidence_ledger_ids=ledger_ids,
            standalone_action=standalone_action_complete,
            standalone_domain_confirmation=standalone_domain_confirmation,
        ) if completion_attempt else ExitCriteriaResult(
            satisfied=False,
            evidence_ledger_ids=ledger_ids,
            evaluated_facts={"completion_attempt": False, "task_mode": mode.value},
            stop_reason="needs_human",
        )
        if exit_result.satisfied:
            status, decision, stop_reason = "completed", "complete", "exit_criteria_satisfied"
        elif tool_loop_count >= int(loop.get("max_tool_loops") or 5):
            status, decision, stop_reason = "stopped", "stop", "max_tool_loops"
            exit_result.stop_reason = "max_tool_loops"
        elif iteration >= int(loop.get("max_iterations") or 5):
            status, decision, stop_reason = "stopped", "stop", "max_iterations"
            exit_result.stop_reason = "max_iterations"
        elif no_progress_count >= int(loop.get("max_no_progress") or 2):
            status, decision, stop_reason = "stopped", "stop", "no_progress"
            exit_result.stop_reason = "no_progress"
        elif completion_attempt:
            if mode == TaskMode.autopilot:
                required_bindings = set(exit_result.evaluated_facts.get("required_binding_refs") or [])
                verified_bindings = set(exit_result.evaluated_facts.get("verified_binding_refs") or [])
                stop_reason = (
                    "unrelated_system_result"
                    if required_bindings and not required_bindings.intersection(verified_bindings)
                    else "exit_criteria_not_met"
                )
                status, decision = "waiting_signal", "continue"
            else:
                status, decision, stop_reason = "waiting_human", "needs_human", "exit_criteria_not_met"
        elif delta.kind == "blocker":
            disposition = progress_delta.error_disposition
            if disposition in {"transient_retry", "semantic_repair"}:
                status, decision, stop_reason = "in_progress", "continue", disposition
            elif disposition == "policy_stop":
                status, decision, stop_reason = "stopped", "stop", disposition
            elif disposition == "unexpected_failure":
                status, decision, stop_reason = "blocked", "blocked", disposition
            else:
                status, decision, stop_reason = "waiting_human", "needs_human", "human_interrupt"
            exit_result.stop_reason = "policy_stop" if disposition == "policy_stop" else "blocked"
        elif not domain_progress and valid_strategy_change:
            status, decision, stop_reason = "in_progress", "continue", "strategy_changed"
        elif not domain_progress:
            status, decision, stop_reason = "waiting_human", "needs_human", "strategy_change_required"
        else:
            status, decision, stop_reason = "in_progress", "continue", "progress_recorded"
        run.update(
            {
                "status": status,
                "decision": decision,
                "stop_reason": stop_reason,
                "loop": loop,
                "evidence_ledger_ids": ledger_ids,
                "exit_criteria_result": exit_result.model_dump(mode="json"),
                "revision": revision + 1,
                "updated_at": now_iso(),
            }
        )
        run.setdefault("events", []).append(
            {
                "event": "loop.delta",
                "delta": delta.model_dump(mode="json"),
                "progress_delta": progress_delta.model_dump(mode="json"),
                "decision": decision,
                "at": now_iso(),
            }
        )
        self._append_checkpoint(
            run,
            node="act" if delta.kind not in {"human_input", "blocker"} else "ask",
            raw_state={
                "progress_delta": progress_delta.model_dump(mode="json"),
                "confirmation": request.confirmation or "",
            },
            idempotency_key=request.idempotency_key,
        )
        self._append_checkpoint(
            run,
            node="verify",
            raw_state={
                "exit_criteria": exit_result.model_dump(mode="json"),
                "domain_progress": domain_progress,
                "repeated": repeated,
            },
            idempotency_key=request.idempotency_key,
        )
        self._append_checkpoint(
            run,
            node="reflect",
            raw_state={
                "status": status,
                "decision": decision,
                "stop_reason": stop_reason,
                "no_progress_count": no_progress_count,
                "tool_loop_count": tool_loop_count,
            },
            idempotency_key=request.idempotency_key,
        )
        if status in {"completed", "stopped"}:
            self._append_checkpoint(
                run,
                node="stop",
                raw_state={"status": status, "exit_criteria": exit_result.model_dump(mode="json")},
                idempotency_key=request.idempotency_key,
            )
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
                "evidence_refs": list(
                    dict.fromkeys(
                        [
                            *run.get("evidence_refs", []),
                            *progress_delta.evidence_refs,
                            *progress_delta.tool_result_refs,
                            *progress_delta.artifact_refs,
                            *([delta.ref] if delta.ref else []),
                        ]
                    )
                ),
                "evidence_ledger_ids": run.get("evidence_ledger_ids", []),
                "exit_criteria_result": exit_result.model_dump(mode="json"),
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
        if stop_reason in {"no_progress", "max_iterations"}:
            negative_id = self._record_negative_result(
                principal=principal,
                kind=stop_reason,
                summary=delta.summary or (
                    "새 근거나 상태 변화 없이 같은 시도가 반복되어 작업을 중단했습니다."
                    if stop_reason == "no_progress"
                    else "허용된 반복 횟수 안에 완료 조건을 충족하지 못했습니다."
                ),
                work_run_id=work_run_id,
                source_refs=[delta.ref] if delta.ref else [],
                metadata={
                    "iteration_count": iteration,
                    "no_progress_count": no_progress_count,
                    "delta_fingerprint": delta.fingerprint,
                    "harness_bindings": run.get("harness_bindings") or [],
                },
            )
            run["negative_result_ids"] = list(
                dict.fromkeys([*run.get("negative_result_ids", []), negative_id])
            )
        elif delta.kind == "blocker":
            negative_id = self._record_negative_result(
                principal=principal,
                kind="work_blocker",
                summary=delta.summary or "업무 진행을 막는 조건이 기록되었습니다.",
                work_run_id=work_run_id,
                source_refs=[delta.ref] if delta.ref else [],
                metadata={
                    "iteration_count": iteration,
                    "blocker_metadata": delta.metadata,
                    "harness_bindings": run.get("harness_bindings") or [],
                },
            )
            run["negative_result_ids"] = list(
                dict.fromkeys([*run.get("negative_result_ids", []), negative_id])
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
            binding=self._binding_for(
                [item for item in work_run.get("harness_bindings") or [] if isinstance(item, dict)],
                "learning.capture",
            ),
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
        for item in self.store.list("negative_results", employee_id=principal.employee_id, limit=500):
            if item.get("kind") != "work_blocker":
                continue
            source_run_id = str(item.get("work_run_id") or "")
            if not source_run_id or source_run_id == work_run.get("work_run_id"):
                continue
            source_run = self.store.get("work_runs", source_run_id) or {}
            candidate_context = self.store.get("contexts", str(source_run.get("context_id") or "")) or {}
            if candidate_context.get("task_ref") != context.task_ref:
                continue
            occurrences += 1
            run_refs.append(str(item.get("negative_result_id") or source_run_id))
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
            binding=self._binding_for(
                [item for item in source_run.get("harness_bindings") or [] if isinstance(item, dict)],
                "learning.capture",
            ),
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
