from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .auth import V2IdentityResolver, require_scope
from .a2ui import compile_harness_review_surface
from .models import (
    AgentTurnRequest,
    CapabilityPlanRequest,
    DeepJobRequest,
    HelperActivateRequest,
    HelperDraftCreateRequest,
    HelperDraftPatchRequest,
    HelperPreviewTurnRequest,
    HarnessValidateRequest,
    HarnessCandidateCreateRequest,
    HarnessCandidateEvaluateRequest,
    HarnessCandidateReviewRequest,
    HarnessCandidateShadowRequest,
    HarnessVersionReleaseRequest,
    HarnessVersionRollbackRequest,
    ContextPlaybookCreateRequest,
    ContextPlaybookPatchRequest,
    KnowledgeCandidatePatchRequest,
    KnowledgeCandidatePromoteRequest,
    GraphQueryPlan,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceRollbackRequest,
    LegacyHelperImportRequest,
    NoteFromTurnRequest,
    OfferExecuteRequest,
    OfferRequest,
    PlanConfirmRequest,
    Principal,
    ProposalApplyRequest,
    SopArtifactPatchRequest,
    SourceSetPatchRequest,
    StarterSuggestionSetRequest,
    SkillArtifactActivateRequest,
    SkillArtifactTestRequest,
    TaskRefinePreviewRequest,
    TokenCreateRequest,
    WorkSessionCreateRequest,
    WorkSessionPatchRequest,
    WorkRunContinueRequest,
    WorkRoutineCreateRequest,
    WorkRoutineTriggerRequest,
)
from .service import AgentV2Service


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def build_agent_v2_router(
    service: AgentV2Service,
    *,
    templates: Jinja2Templates | None = None,
    shell_context_factory: Callable[..., dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter()
    identity_resolver = V2IdentityResolver(service.pats)

    async def principal(request: Request) -> Principal:
        return await identity_resolver(request)

    @router.get("/api/v2/bootstrap")
    async def bootstrap(
        page_ref: str = "",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        readiness = service.readiness(identity)
        page_kind = service.page_kind(page_ref)
        page_context = service.learning.contexts.page_anchor(identity, page_ref)
        if page_context and page_context.resolved:
            page_kind = {
                "sop": "sop",
                "workflow": "sop",
                "event": "event",
                "action": "action",
            }.get(page_context.kind, page_kind)
        starters = service.starter_suggestions(identity, page_ref=page_ref, limit=8)
        search_sync_state = str(((readiness.get("search") or {}).get("index") or {}).get("sync_state") or "ready")
        surface_status = {
            "state": "updating" if search_sync_state == "syncing" else "ready",
            "message": "새 지식을 반영 중입니다." if search_sync_state == "syncing" else "",
        }
        return {
            "version": "2.0",
            "identity": {
                "employee_id": identity.employee_id,
                "display_name": identity.display_name,
                "teams": identity.teams,
                "roles": identity.roles,
                "auth_source": identity.auth_source,
            },
            "page": {
                "ref": page_ref,
                "kind": page_kind,
                "context": page_context.model_dump(mode="json") if page_context else None,
            },
            "capabilities": service.registry.public_payload(
                principal=identity,
                readiness=readiness["dependencies"],
            ),
            "offers": [],
            "starters": [item.model_dump(mode="json") for item in starters],
            "readiness": {
                "ready": readiness["ready"],
                "dependencies": readiness["dependencies"],
                "warnings": [],
                "surface_status": surface_status,
            },
            "links": {
                "workspace": "/agent",
                "helper_builder": "/helpers/new",
                "mcp": service.settings.mcp_external_url,
                "openapi": "/openapi-v2.json",
            },
        }

    @router.get("/api/v2/capabilities")
    async def capabilities(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        readiness = service.readiness(identity)
        return {
            "version": service.registry.version,
            "items": service.registry.public_payload(principal=identity, readiness=readiness["dependencies"]),
        }

    @router.post("/api/v2/starter-suggestion-sets")
    async def create_starter_suggestion_set(
        request: StarterSuggestionSetRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.create_starter_suggestion_set(identity, request)

    @router.get("/api/v2/starter-suggestion-sets/{set_id}")
    async def starter_suggestion_set(
        set_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_starter_suggestion_set(identity, set_id)

    @router.get("/api/v2/skills")
    async def skills(
        q: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_skills(identity, query=q, limit=limit)

    @router.post("/api/v2/offers")
    async def create_offers(request: OfferRequest, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        offers = service.create_offers(identity, request)
        return {"items": [item.model_dump(mode="json") for item in offers]}

    @router.post("/api/v2/offers/{offer_id}/execute")
    async def execute_offer(
        offer_id: str,
        request: OfferExecuteRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.execute_offer(identity, offer_id, request).model_dump(mode="json")

    @router.post("/api/v2/agent/turns")
    async def agent_turn(
        payload: AgentTurnRequest,
        http_request: Request,
        identity: Principal = Depends(principal),
    ) -> Any:
        require_scope(identity, "boi.read")
        if "text/event-stream" not in str(http_request.headers.get("accept") or "").lower():
            return service.run_turn(identity, payload).model_dump(mode="json")

        async def stream():
            queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def emit(event: str, event_payload: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, (event, event_payload))

            yield sse(
                "accepted",
                {
                    "stage": "accepted",
                    "message": "요청을 받았습니다.",
                },
            )
            task = asyncio.create_task(
                asyncio.to_thread(service.run_turn, identity, payload, progress_sink=emit)
            )
            while not task.done() or not queue.empty():
                try:
                    event, event_payload = await asyncio.wait_for(queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                yield sse(event, event_payload)
            try:
                response = await task
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                message = str(detail.get("message") or "요청을 처리하지 못했습니다.")
                yield sse(
                    "error",
                    {
                        "stage": "failed",
                        "message": message,
                        "status_code": exc.status_code,
                        "retryable": exc.status_code >= 500,
                    },
                )
                return
            except Exception:
                yield sse(
                    "error",
                    {
                        "stage": "failed",
                        "message": "요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
                        "status_code": 500,
                        "retryable": True,
                    },
                )
                return
            yield sse("final", response.model_dump(mode="json"))

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/api/v2/work-sessions")
    async def create_work_session(
        request: WorkSessionCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.create_work_session(identity, request)

    @router.get("/api/v2/work-sessions")
    async def list_work_sessions(
        limit: int = Query(default=20, ge=1, le=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_work_sessions(identity, limit=limit)

    @router.get("/api/v2/work-sessions/{session_id}")
    async def get_work_session(session_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.work_session_bundle(identity, session_id)

    @router.patch("/api/v2/work-sessions/{session_id}")
    async def patch_work_session(
        session_id: str,
        request: WorkSessionPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.patch_work_session(identity, session_id, request)

    @router.delete("/api/v2/work-sessions/{session_id}")
    async def delete_work_session(session_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.delete_work_session(identity, session_id)

    @router.get("/api/v2/work-sessions/{session_id}/timeline")
    async def work_session_timeline(
        session_id: str,
        limit: int = Query(default=100, ge=1, le=300),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.session_timeline(identity, session_id, limit=limit)

    @router.get("/api/v2/work-sessions/{session_id}/sources")
    async def work_session_sources(session_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_source_set(identity, session_id)

    @router.patch("/api/v2/work-sessions/{session_id}/sources")
    async def patch_work_session_sources(
        session_id: str,
        request: SourceSetPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.patch_source_set(identity, session_id, request)

    @router.get("/api/v2/citations/{citation_id}")
    async def citation(citation_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_citation(identity, citation_id)

    @router.get("/api/v2/goal-plans/{goal_plan_id}")
    async def goal_plan(goal_plan_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_goal_plan(identity, goal_plan_id)

    @router.post("/api/v2/notes/from-turn")
    async def note_from_turn(
        request: NoteFromTurnRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_note_from_turn(identity, request)

    @router.post("/api/v2/notes/{artifact_id}/use-as-source")
    async def note_use_as_source(artifact_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.use_note_as_source(identity, artifact_id)

    @router.get("/api/v2/agent/runs/{run_id}")
    async def agent_run(run_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_run(identity, run_id)

    @router.get("/api/v2/work-runs")
    async def work_runs(
        limit: int = Query(default=20, ge=1, le=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_runs(identity, limit=limit)

    @router.get("/api/v2/work-runs/{work_run_id}")
    async def work_run(work_run_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.view_run(identity, work_run_id)

    @router.get("/api/v2/work-runs/{work_run_id}/events")
    async def work_run_events(work_run_id: str, identity: Principal = Depends(principal)) -> StreamingResponse:
        require_scope(identity, "boi.read")
        run = service.learning.get_run(identity, work_run_id)

        async def stream():
            for item in run.get("events") or []:
                event = str(item.get("event") or "message")
                yield sse(event, {key: value for key, value in item.items() if key != "event"})

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @router.post("/api/v2/work-runs/{work_run_id}/continue")
    async def continue_work_run(
        work_run_id: str,
        request: WorkRunContinueRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.continue_work_run(identity, work_run_id, request)

    @router.post("/api/v2/work-routines")
    async def create_work_routine(
        request: WorkRoutineCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_work_routine(identity, request)

    @router.get("/api/v2/work-routines")
    async def list_work_routines(
        limit: int = Query(default=50, ge=1, le=100),
        surface: str = Query(default="", max_length=40),
        status: str = Query(default="", max_length=80),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_work_routines(identity, limit=limit, surface=surface, status=status)

    @router.get("/api/v2/work-routines/{routine_id}")
    async def get_work_routine(routine_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_work_routine(identity, routine_id)

    @router.post("/api/v2/work-routines/{routine_id}/trigger")
    async def trigger_work_routine(
        routine_id: str,
        request: WorkRoutineTriggerRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.trigger_work_routine(identity, routine_id, request)

    @router.post("/api/v2/work-routines/{routine_id}/cancel")
    async def cancel_work_routine(routine_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.cancel_work_routine(identity, routine_id)

    @router.get("/api/v2/agent/runs/{run_id}/events")
    async def agent_run_events(run_id: str, identity: Principal = Depends(principal)) -> StreamingResponse:
        require_scope(identity, "boi.read")
        run = service.get_run(identity, run_id)

        async def stream():
            for item in run.get("events") or []:
                event = str(item.get("event") or "message")
                yield sse(event, {key: value for key, value in item.items() if key != "event"})
            job_id = str(run.get("job_id") or "")
            if not job_id:
                return
            previous = ""
            for _ in range(120):
                job = service.get_job(identity, job_id)
                status = str(job.get("status") or "")
                if status != previous:
                    yield sse("job.progress", {"job_id": job_id, "status": status, "message": job.get("message") or ""})
                    previous = status
                if status in {"completed", "failed", "cancelled"}:
                    yield sse("job.completed" if status == "completed" else "error", job)
                    return
                await asyncio.sleep(1)
            yield sse("error", {"status": "stream_timeout", "job_id": job_id})

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @router.get("/api/v2/search")
    async def search(
        q: str = Query(min_length=1, max_length=4000),
        limit: int = Query(default=8, ge=1, le=20),
        include_history: bool = False,
        include_drafts: bool = False,
        page_ref: str = "",
        task_ref: str = "",
        kinds: list[str] = Query(default=[]),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if include_drafts:
            require_scope(identity, "boi.draft")
        return service.search.search(
            q,
            identity,
            limit=limit,
            include_history=include_history,
            include_drafts=include_drafts,
            page_ref=page_ref,
            task_ref=task_ref,
            kinds={item.strip() for value in kinds for item in value.split(",") if item.strip()} or None,
        ).model_dump(mode="json")

    @router.post("/api/v2/search/reindex")
    async def reindex(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        try:
            return service.search.reindex(identity)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.get("/api/v2/knowledge-sources")
    async def knowledge_sources(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.list_sources(identity)

    @router.post("/api/v2/knowledge-sources")
    async def create_knowledge_source(
        request: KnowledgeSourceCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.create_source(identity, request)

    @router.post("/api/v2/knowledge-sources/{source_id:path}/sync")
    async def sync_knowledge_source(
        source_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.sync_source(identity, source_id)

    @router.get("/api/v2/knowledge-source-jobs/{job_id}")
    async def knowledge_source_job(
        job_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.source_job(identity, job_id)

    @router.post("/api/v2/knowledge-source-jobs/{job_id}/cancel")
    async def cancel_knowledge_source_job(
        job_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.cancel_source_job(identity, job_id)

    @router.post("/api/v2/knowledge-source-jobs/{job_id}/retry")
    async def retry_knowledge_source_job(
        job_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.retry_source_job(identity, job_id)

    @router.post("/api/v2/knowledge-sources/{source_id:path}/rollback")
    async def rollback_knowledge_source(
        source_id: str,
        request: KnowledgeSourceRollbackRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.rollback_source_import(identity, source_id, request)

    @router.get("/api/v2/knowledge-graph/explore")
    async def explore_knowledge_graph(
        view: str = Query(default="neighbors", pattern="^(ranked|neighbors|path|workflow|impact|lineage|responsibility|timeline|compare|tour)$"),
        source_ref: str = "",
        target_ref: str = "",
        q: str = "",
        depth: int = Query(default=2, ge=1, le=6),
        limit: int = Query(default=80, ge=1, le=500),
        cursor: str = "",
        node_kinds: str = "",
        relation_kinds: str = "",
        provenance: str = "",
        direction: str = Query(default="both", pattern="^(outgoing|incoming|both)$"),
        time_from: str = "",
        time_to: str = "",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.explore(
            identity,
            view=view,
            source_ref=source_ref,
            target_ref=target_ref,
            q=q,
            depth=depth,
            limit=limit,
            cursor=cursor,
            node_kinds=[item.strip() for item in node_kinds.split(",") if item.strip()],
            relation_kinds=[item.strip() for item in relation_kinds.split(",") if item.strip()],
            provenance=[item.strip() for item in provenance.split(",") if item.strip()],
            direction=direction,
            time_from=time_from,
            time_to=time_to,
        )

    @router.get("/api/v2/knowledge-graph/nodes/{node_id:path}")
    async def knowledge_graph_node(
        node_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.node(identity, node_id)

    @router.post("/api/v2/knowledge-graph/query")
    async def query_knowledge_graph(
        request: GraphQueryPlan,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.query(identity, request)

    @router.get("/api/v2/knowledge-health")
    async def knowledge_health(
        refresh: bool = False,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.health(identity, refresh=refresh)

    @router.get("/api/v2/harness-failures")
    async def harness_failures(
        status: str = "open",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_harness_failures(identity, status=status)

    @router.get("/api/v2/harness-failure-patterns")
    async def harness_failure_patterns(
        status: str = "open",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_harness_failure_patterns(identity, status=status)

    @router.get("/api/v2/negative-results")
    async def negative_results(
        status: str = "active",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_negative_results(identity, status=status)

    @router.get("/api/v2/context-playbook")
    async def context_playbook(
        status: str = "",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_context_playbook(identity, status=status)

    @router.post("/api/v2/context-playbook")
    async def create_context_playbook_item(
        request: ContextPlaybookCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.create_context_playbook_item(identity, request)

    @router.patch("/api/v2/context-playbook/{item_id}")
    async def patch_context_playbook_item(
        item_id: str,
        request: ContextPlaybookPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.patch_context_playbook_item(identity, item_id, request)

    @router.post("/api/v2/harness-candidates")
    async def create_harness_candidate(
        request: HarnessCandidateCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        return service.learning.create_harness_candidate(identity, request)

    @router.post("/api/v2/harness-candidates/{candidate_id}/shadow")
    async def shadow_harness_candidate(
        candidate_id: str,
        request: HarnessCandidateShadowRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        return service.learning.shadow_harness_candidate(identity, candidate_id, request)

    @router.post("/api/v2/harness-candidates/{candidate_id}/evaluate")
    async def evaluate_harness_candidate(
        candidate_id: str,
        request: HarnessCandidateEvaluateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        return service.learning.evaluate_harness_candidate(identity, candidate_id, request)

    @router.post("/api/v2/harness-candidates/{candidate_id}/review")
    async def review_harness_candidate(
        candidate_id: str,
        request: HarnessCandidateReviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        return service.learning.review_harness_candidate(identity, candidate_id, request)

    @router.get("/api/v2/harness-candidates/{candidate_id}/surface")
    async def harness_candidate_surface(
        candidate_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        candidate = service.store.get("harness_candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
        pattern_ids = set(candidate.get("failure_pattern_ids") or [])
        patterns = [
            item for item in service.store.list("harness_failure_patterns", limit=1000)
            if item.get("failure_pattern_id") in pattern_ids
        ]
        shadow = service.store.get("harness_shadow_runs", str(candidate.get("latest_shadow_run_id") or ""))
        evaluation = service.store.get("harness_eval_runs", str(candidate.get("latest_eval_id") or ""))
        surface = compile_harness_review_surface(
            candidate,
            failure_patterns=patterns,
            shadow_run=shadow,
            evaluation=evaluation,
        )
        surface.update({"employee_id": identity.employee_id, "created_at": candidate.get("updated_at") or candidate.get("created_at")})
        service.store.put("a2ui_surfaces", surface["surface_id"], surface)
        return surface

    @router.post("/api/v2/harness-candidates/{candidate_id}/release")
    async def release_harness_candidate(
        candidate_id: str,
        request: HarnessVersionReleaseRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.release_harness_version(identity, candidate_id, request)

    @router.post("/api/v2/harness-candidates/{candidate_id}/rollback")
    async def rollback_harness_candidate(
        candidate_id: str,
        request: HarnessVersionRollbackRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.rollback_harness_version(identity, candidate_id, request)

    @router.get("/api/v2/knowledge-proposals")
    async def knowledge_proposals(
        status: str = "",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.proposals(identity, status=status)

    @router.post("/api/v2/knowledge-proposals/{proposal_id}/apply")
    async def apply_knowledge_proposal(
        proposal_id: str,
        request: KnowledgeProposalApplyRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.apply_proposal(identity, proposal_id, request)

    @router.get("/api/v2/knowledge-graph")
    async def knowledge_graph(
        q: str = "",
        limit: int = Query(default=120, ge=1, le=300),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge_graph(identity, query=q, limit=limit)

    @router.get("/api/v2/context/{context_id}")
    async def context(context_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_context(identity, context_id)

    @router.get("/api/v2/evaluations/{evaluation_id}")
    async def evaluation(evaluation_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_evaluation(identity, evaluation_id)

    @router.get("/api/v2/a2ui-surfaces/{surface_id}")
    async def a2ui_surface(surface_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        surface = service.store.get("a2ui_surfaces", surface_id)
        if not surface:
            raise HTTPException(status_code=404, detail="표시할 결과를 찾지 못했습니다.")
        if str(surface.get("employee_id") or "") != identity.employee_id and not identity.is_admin:
            raise HTTPException(status_code=403, detail="이 결과를 볼 권한이 없습니다.")
        return surface

    @router.get("/api/v2/usage/{usage_id}")
    async def usage(usage_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_usage_ledger(identity, usage_id)

    @router.get("/api/v2/harnesses")
    async def harnesses(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_harnesses()

    @router.post("/api/v2/harnesses/{harness_id}/validate")
    async def validate_harness(
        harness_id: str,
        request: HarnessValidateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.validate_harness(identity, harness_id, request)

    @router.get("/api/v2/knowledge-candidates")
    async def knowledge_candidates(
        status: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_candidates(identity, status=status, limit=limit)

    @router.get("/api/v2/knowledge-candidates/{candidate_id}")
    async def knowledge_candidate(candidate_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.get_candidate(identity, candidate_id)

    @router.patch("/api/v2/knowledge-candidates/{candidate_id}")
    async def patch_knowledge_candidate(
        candidate_id: str,
        request: KnowledgeCandidatePatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.patch_candidate(identity, candidate_id, request)

    @router.post("/api/v2/knowledge-candidates/{candidate_id}/promote")
    async def promote_knowledge_candidate(
        candidate_id: str,
        request: KnowledgeCandidatePromoteRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.promote_knowledge_candidate(identity, candidate_id, request)

    @router.get("/api/v2/artifacts/{artifact_id}")
    async def artifact(artifact_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_artifact(identity, artifact_id)

    @router.patch("/api/v2/artifacts/{artifact_id}/sop")
    async def patch_sop_artifact(
        artifact_id: str,
        request: SopArtifactPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.patch_sop_artifact(identity, artifact_id, request)

    @router.post("/api/v2/artifacts/{artifact_id}/tasks/{task_id}/refine-preview")
    async def refine_task_preview(
        artifact_id: str,
        task_id: str,
        request: TaskRefinePreviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.refine_task_preview(identity, artifact_id, task_id, request)

    @router.post("/api/v2/artifacts/{artifact_id}/tasks/{task_id}/proposals/{proposal_id}/apply")
    async def apply_task_proposal(
        artifact_id: str,
        task_id: str,
        proposal_id: str,
        request: ProposalApplyRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.apply_task_proposal(identity, artifact_id, task_id, proposal_id, request)

    @router.get("/api/v2/task-proposals/{proposal_id}")
    async def task_proposal(proposal_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_task_proposal(identity, proposal_id)

    @router.post("/api/v2/helper-drafts")
    async def create_helper_draft(
        request: HelperDraftCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_helper_draft(identity, request)

    @router.post("/api/v2/helper-drafts/import")
    async def import_helper_draft(
        request: LegacyHelperImportRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.import_legacy_helper_draft(identity, request)

    @router.get("/api/v2/helper-drafts/{draft_id}")
    async def get_helper_draft(draft_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_helper_draft(identity, draft_id)

    @router.patch("/api/v2/helper-drafts/{draft_id}")
    async def patch_helper_draft(
        draft_id: str,
        request: HelperDraftPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.patch_helper_draft(identity, draft_id, request)

    @router.delete("/api/v2/helper-drafts/{draft_id}")
    async def delete_helper_draft(draft_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.delete_helper_draft(identity, draft_id)

    @router.post("/api/v2/helper-drafts/{draft_id}/preview-turns")
    async def helper_preview_turn(
        draft_id: str,
        request: HelperPreviewTurnRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.helper_preview_turn(identity, draft_id, request).model_dump(mode="json")

    @router.post("/api/v2/helper-drafts/{draft_id}/activate")
    async def activate_helper(
        draft_id: str,
        request: HelperActivateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.activate_helper(identity, draft_id, request)

    @router.post("/api/v2/artifacts/{artifact_id}/skill-tests")
    async def test_skill_artifact(
        artifact_id: str,
        request: SkillArtifactTestRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.test_skill_artifact(identity, artifact_id, request)

    @router.post("/api/v2/artifacts/{artifact_id}/skill-activate")
    async def activate_skill_artifact(
        artifact_id: str,
        request: SkillArtifactActivateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.activate_skill_artifact(identity, artifact_id, request)

    @router.get("/api/v2/helpers")
    async def list_helpers(
        limit: int = Query(default=50, ge=1, le=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_helpers(identity, limit=limit)

    @router.get("/api/v2/helpers/{helper_id}")
    async def get_helper(helper_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_helper(identity, helper_id)

    @router.post("/api/v2/capabilities/{capability_id}/plan")
    async def capability_plan(
        capability_id: str,
        request: CapabilityPlanRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_plan(identity, capability_id, request).model_dump(mode="json")

    @router.post("/api/v2/plans/{plan_id}/confirm")
    async def confirm_plan(
        plan_id: str,
        request: PlanConfirmRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return await service.confirm_plan(identity, plan_id, request.reason)

    @router.post("/api/v2/deep-jobs")
    async def create_deep_job(request: DeepJobRequest, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_deep_job(identity, request)

    @router.get("/api/v2/deep-jobs/{job_id}")
    async def deep_job(job_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_job(identity, job_id)

    @router.post("/api/v2/deep-jobs/{job_id}/cancel")
    async def cancel_deep_job(job_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.cancel_job(identity, job_id)

    @router.get("/api/v2/system/readiness")
    async def readiness(
        probe_model: bool = False,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if probe_model and not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required for live model probes")
        return service.readiness(identity, probe_model=probe_model)

    @router.get("/api/v2/harness/acceptance")
    async def harness_acceptance(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required for live acceptance probes")
        return service.harness_acceptance(identity)

    @router.post("/api/v2/tokens")
    async def create_token(request: TokenCreateRequest, identity: Principal = Depends(principal)) -> dict[str, Any]:
        if identity.auth_source == "pat":
            raise HTTPException(status_code=403, detail="PATs can only be issued from an authenticated Web session")
        return service.pats.create(identity, request)

    @router.get("/api/v2/tokens")
    async def list_tokens(identity: Principal = Depends(principal)) -> dict[str, Any]:
        if identity.auth_source == "pat":
            raise HTTPException(status_code=403, detail="manage PATs from an authenticated Web session")
        return {"items": service.pats.list(identity)}

    @router.delete("/api/v2/tokens/{token_id}")
    async def revoke_token(token_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        if identity.auth_source == "pat":
            raise HTTPException(status_code=403, detail="manage PATs from an authenticated Web session")
        if not service.pats.revoke(identity, token_id):
            raise HTTPException(status_code=404, detail="token not found")
        return {"token_id": token_id, "status": "revoked"}

    if templates is not None and shell_context_factory is not None:

        @router.get("/agent", response_class=HTMLResponse)
        async def agent_workspace(request: Request, identity: Principal = Depends(principal)) -> HTMLResponse:
            return templates.TemplateResponse(
                "agent_workspace.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "mcp_url": service.settings.mcp_external_url,
                    "boi_base_url": str(request.base_url).rstrip("/"),
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="agent",
                        title="BoI Agent",
                        description="BoI Wiki 지식과 업무 흐름을 찾고, 근거가 있는 초안과 심층 작업을 이어갑니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/helpers/new", response_class=HTMLResponse)
        async def helper_builder(request: Request, identity: Principal = Depends(principal)) -> HTMLResponse:
            return templates.TemplateResponse(
                "helper_builder_v2.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="agent",
                        title="나만의 BoI Agent 만들기",
                        description="필요한 능력과 참고 자료를 선택해 먼저 시험해봅니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/agent/access", response_class=HTMLResponse)
        async def agent_access(request: Request, identity: Principal = Depends(principal)) -> HTMLResponse:
            return templates.TemplateResponse(
                "agent_access_v2.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "mcp_url": service.settings.mcp_external_url,
                    "boi_base_url": str(request.base_url).rstrip("/"),
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="agent",
                        title="외부 도구 연결",
                        description="내 권한 범위에서 Codex, Claude, API와 BoI Wiki를 연결합니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/harness-candidates/{candidate_id}", response_class=HTMLResponse)
        async def harness_candidate_review_page(
            candidate_id: str,
            request: Request,
            identity: Principal = Depends(principal),
        ) -> HTMLResponse:
            if not identity.is_admin:
                raise HTTPException(status_code=403, detail="boi.admin is required")
            candidate = service.store.get("harness_candidates", candidate_id)
            if not candidate:
                raise HTTPException(status_code=404, detail="Harness 후보를 찾을 수 없습니다.")
            pattern_ids = set(candidate.get("failure_pattern_ids") or [])
            patterns = [
                item for item in service.store.list("harness_failure_patterns", limit=1000)
                if item.get("failure_pattern_id") in pattern_ids
            ]
            shadow = service.store.get("harness_shadow_runs", str(candidate.get("latest_shadow_run_id") or ""))
            evaluation = service.store.get("harness_eval_runs", str(candidate.get("latest_eval_id") or ""))
            version = next(
                (item for item in service.store.list("harness_versions", limit=1000) if item.get("candidate_id") == candidate_id),
                {},
            )
            surface = compile_harness_review_surface(
                candidate,
                failure_patterns=patterns,
                shadow_run=shadow,
                evaluation=evaluation,
            )
            surface.update({"employee_id": identity.employee_id, "created_at": candidate.get("updated_at") or candidate.get("created_at")})
            service.store.put("a2ui_surfaces", surface["surface_id"], surface)
            return templates.TemplateResponse(
                "harness_candidate_review.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "candidate": candidate,
                    "evaluation": evaluation or {},
                    "version": version,
                    "surface": surface,
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="advanced",
                        title="업무 실행 품질 개선 검토",
                        description="반복 실패 근거와 시험 결과를 확인하고 운영 반영 여부를 결정합니다.",
                    ),
                },
            )

        @router.get("/agents/builder-v2")
        async def builder_redirect() -> RedirectResponse:
            return RedirectResponse("/helpers/new", status_code=307)

    return router
