from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from ..governed_runtime.reviewed_metadata_query import (
    ReviewedQueryPrepareRequest, ReviewedQueryExecuteRequest, ReviewedQueryReadRequest,
    ReviewedQueryPageRequest, ReviewedQuestionInterpretRequest,
)
from ..governed_runtime.run_relation_mapping import RunRelationQualityPreviewRequest
from ..governed_runtime.answer_application import VerifiedAnswerQuestionRequest
from ..governed_runtime.governed_answer_delivery import AnswerExportRequest
from .auth import V2IdentityResolver, require_scope
from .native_formula import NativeFormulaRequest, preview_for_principal
from .database_source import DatabaseSourceRequest, database_source_call, DatabaseBindRequest, bind_database_query
from .native_answer_composition import NativeAnswerComposition, compose_native_answer
from .native_composition_result import NativeCompositionRead,NativePreparedComposition,NativeAuthoringComposition,compose_native_response,read_native_composition
from .native_query import (NativeQueryPrepareRequest, NativeQueryPlanRequest,
    NativeQueryExecuteRequest, NativeQueryResultRequest, NativeQueryDiagnoseEmptyRequest,
    NativeQueryRegistrationRequest,
    discover_native_queries, discover_native_query_registration_sources,
    register_native_query_source, native_query_for_principal)
from .a2ui import (
    A2UI_MESSAGE_VERSION,
    A2UI_PROTOCOL_VERSION,
    ALLOWED_COMPONENTS,
    BOI_CATALOG_ID,
    BOI_CATALOG_URL,
    COMPONENT_PROP_SCHEMAS,
    capability_catalog,
    compile_harness_review_surface,
)
from .models import (
    AgentTaskCancelRequest,
    AgentTaskClaimRequest,
    AgentTaskHeartbeatRequest,
    AgentTaskMaterializeRequest,
    AgentTaskReleaseRequest,
    AgentTaskSubmitRequest,
    AgentTaskVerifyRequest,
    AgentTurnRequest,
    BulkMigrationRunControlRequest,
    CapabilityPlanRequest,
    ContextAnchor,
    DeepJobRequest,
    DeepJobRestartRequest,
    EventRuntimeActivationRequest,
    EventRuntimeDefinitionPreviewRequest,
    EventRuntimeSignalRequest,
    HelperActivateRequest,
    HelperDraftCreateRequest,
    HelperDraftPatchRequest,
    HelperPreviewTurnRequest,
    HarnessValidateRequest,
    HarnessCandidateCreateRequest,
    HarnessCodePatchArtifactRequest,
    HarnessOfflineVerifyRequest,
    HarnessUpdatePreviewRequest,
    HarnessCandidateEvaluateRequest,
    HarnessCandidateReviewRequest,
    HarnessCandidateShadowRequest,
    HarnessVersionReleaseRequest,
    HarnessVersionRollbackRequest,
    ContextPlaybookCreateRequest,
    ContextPlaybookPatchRequest,
    KnowledgeCandidatePatchRequest,
    KnowledgeCandidatePromoteRequest,
    KnowledgeHealthScanRequest,
    GraphQueryPlan,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceRollbackRequest,
    LegacyHelperImportRequest,
    NoteFromTurnRequest,
    OntologyMigrationApproveRequest,
    OntologyMigrationMappingPatchRequest,
    OntologyMigrationReleaseRequest,
    OntologyProposalCreateRequest,
    OntologyProposalPublishRequest,
    OntologyProposalReviewRequest,
    OntologyQueryRequest,
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
    SkillInvocationPreviewRequest,
    TaskRefinePreviewRequest,
    TokenCreateRequest,
    WorkSessionCreateRequest,
    WorkSessionPatchRequest,
    WorkRunCancelRequest,
    WorkRunContinueRequest,
    WorkRoutineCreateRequest,
    WorkRoutineTriggerRequest,
)
from .service import AgentV2Service
from .domain_intake import (DomainIntakeRoute, SourceCaptureRequest, SourceProjectRequest, SourceFieldReadRequest, SourceFieldBatchReadRequest,
    DomainAssetCatalogRequest, DomainAssetReadRequest, DomainAssetCreateRequest, DefinitionSourceReadRequest,
    DomainContextPrepareRequest, DomainContextPageRequest, DomainContextAcknowledgeRequest, DomainContextRestoreRequest)
from .domain_intake import DomainPackageRequest, SourceImageReadRequest, SourceImageTranscriptionRequest
from .process_review_binding import ProcessReviewBindingRequest
from ..governed_runtime.domain_work_contract import (DomainWorkStartRequest, DomainWorkLookupRequest, DomainToolPrepareRequest,
    DomainToolReadRequest, DomainToolLookupRequest, DomainToolDispatchRequest, DomainToolInputRequest, DomainToolEvidenceRequest, DomainToolSubmitRequest, DomainWorkCompleteRequest)
from ..governed_runtime.ledger import ImmutableRecordConflict, LedgerError
from ..governed_runtime.knowledge_work_contract import KnowledgeWorkRequest
from .knowledge_supervision import KnowledgeSupervisionRequest


QUALIFICATION_ANSWER_VIEWER_CONTRACT: dict[str, Any] = {
    "feature_flag": "BOI_QUALIFICATION_ANSWER_VIEWER_ENABLED",
    "default_enabled": False,
    "canonical_product_surface": False,
    "surfaces": ("/ontology/answers", "/ontology/answers/{answer_id}"),
    "purpose": "Read-only AQ6 historical qualification inspection",
    "owner": "BoI governed-runtime qualification harness",
    "removal_condition": (
        "Remove after AQ6-R6 external-consumer review handoff and two successor "
        "qualified Releases preserve equivalent artifact inspection"
    ),
}


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

    def conditional_get(
        enabled: bool, path: str, **kwargs: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if enabled:
            return router.get(path, **kwargs)
        return lambda endpoint: endpoint

    def external_answer_payload(payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        if not service.settings.qualification_answer_viewer_enabled:
            result.pop("ui_url", None)
        return result

    async def principal(request: Request) -> Principal:
        return await identity_resolver(request)

    domain_router = APIRouter(route_class=DomainIntakeRoute)

    async def domain_intake_call(method, identity, payload):
        try:
            return await run_in_threadpool(method, identity, payload)
        except ImmutableRecordConflict:
            raise HTTPException(status_code=409, detail={'reason_code':'DOMAIN_INTAKE_REFERENCE_CORRUPT'}) from None
        except LedgerError:
            raise HTTPException(status_code=404, detail={'reason_code':'DOMAIN_INTAKE_REFERENCE_UNAVAILABLE'}) from None
        except ValueError as exc:
            from .native_answer_refusal import NativeAnswerRefusal
            if isinstance(exc, NativeAnswerRefusal):
                # Built from declared positions and closed codes only.
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
            code = str(exc)
            # Source policy and projection errors are codes, never source text.
            if not code.isascii() or not code.replace('_', '').isalnum() or len(code) > 120:
                from .native_error_diagnostics import log_redacted_failure
                log_redacted_failure(exc,getattr(method,'__name__','domain_intake'))
                code = 'DOMAIN_INTAKE_REQUEST_INVALID'
            status = 503 if code == 'DOMAIN_INTAKE_NOT_CONFIGURED' else (
                403 if any(part in code for part in ('DENIED', 'NOT_AUTHORIZED', 'PRINCIPAL_MISMATCH')) else 409)
            raise HTTPException(status_code=status, detail={'reason_code': code}) from None

    @domain_router.post('/api/v2/domain-intake/sources')
    async def domain_source_capture(payload: SourceCaptureRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.capture, identity, payload)

    from .local_bundle_transport import register_local_bundle_routes
    register_local_bundle_routes(domain_router, service=service, principal=principal, call=domain_intake_call)
    from .knowledge_set_transport import register_knowledge_set_routes
    register_knowledge_set_routes(domain_router,service=service,principal=principal,call=domain_intake_call)
    from .knowledge_query_transport import register_knowledge_query_routes
    register_knowledge_query_routes(domain_router, service=service, principal=principal, call=domain_intake_call)
    from .knowledge_qualification_transport import register_knowledge_qualification_routes
    register_knowledge_qualification_routes(domain_router,service=service,principal=principal,call=domain_intake_call)

    @domain_router.post('/api/v2/knowledge-work')
    async def knowledge_work(http_request: Request, payload: KnowledgeWorkRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read' if payload.operation in ('list', 'status', 'resume', 'schema', 'output') else 'boi.draft')
        if (payload.operation == 'publication' and payload.request.get('phase') in ('preview', 'stop', 'prepare', 'validate', 'qualify',
                'preflight', 'publish', 'publication_resume')
                and identity.auth_source != 'pat'):
            from .local_bundle_transport import same_origin
            same_origin(http_request)
        return await domain_intake_call(service.domain_intake.knowledge_work, identity, payload)

    @domain_router.post('/api/v2/knowledge-supervision')
    async def knowledge_supervision(http_request: Request, payload: KnowledgeSupervisionRequest,
            identity: Principal = Depends(principal)):
        mutation = payload.operation not in ('list', 'read', 'feedback_inbox', 'feedback_read')
        require_scope(identity, 'boi.draft' if mutation and payload.operation != 'document_feedback' else 'boi.read')
        if mutation:
            # Bearer clients do not rely on ambient browser credentials. Browser
            # writes require a custom header and, when present, an exact origin.
            from urllib.parse import urlsplit
            origin = http_request.headers.get('origin')
            actual = http_request.url
            expected_origin = (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme == 'https' else 80))
            try:
                supplied = urlsplit(origin) if origin else None
                origin_ok = supplied is None or ((supplied.scheme, supplied.hostname,
                    supplied.port or (443 if supplied.scheme == 'https' else 80)) == expected_origin
                    and not (supplied.username or supplied.password or supplied.path or supplied.query or supplied.fragment))
            except ValueError:
                origin_ok = False
            if (not origin_ok or http_request.headers.get('sec-fetch-site') == 'cross-site'
                    or (identity.auth_source != 'pat'
                        and http_request.headers.get('x-requested-with') != 'BoI-Wiki')):
                raise HTTPException(status_code=403, detail={'reason_code':'KNOWLEDGE_SUPERVISION_ORIGIN_DENIED'})
        return await domain_intake_call(service.domain_intake.knowledge_supervision, identity, payload)

    @domain_router.post('/api/v2/domain-packages')
    async def domain_packages(payload: DomainPackageRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read' if payload.operation in ('discover','read') else 'boi.draft')
        return await domain_intake_call(service.domain_intake.domain_packages, identity, payload)

    @domain_router.get('/api/v2/knowledge-bootstrap')
    async def knowledge_bootstrap(identity: Principal = Depends(principal)):
        from ..public_links import configured_public_links
        require_scope(identity, 'boi.read')
        catalog = await domain_intake_call(service.domain_intake.domain_packages, identity, DomainPackageRequest(operation='discover'))
        public_links = configured_public_links()
        return {'contract_version':'boi/knowledge-bootstrap@1', 'execution':'external_agent',
            'portal_url':public_links.url('/knowledge'), 'public_links':public_links.metadata(), 'packages':[
                {'package_id':item['package_id'],'revision':item.get('revision'),
                 **{key:item['manifest'].get(key) for key in ('display_name','description','capability_status','capability_basis')},
                 'read':{'tool':'boi_domain_packages','arguments':{'operation':'read','request':{'package_id':item['package_id']}}}}
                for item in catalog['items']],
            'hotl':catalog.get('hotl'), 'work':{'tool':'boi_knowledge_work','schema_operation':'schema'},
            'supervision':{'tool':'boi_knowledge_supervision','operations':['list','read','correct','resolve','stop',
                'document_feedback','feedback_inbox','feedback_read']},
            'source':{'capture_tool':'boi_source_capture','projection_tool':'boi_source_project','field_tool':'boi_source_field','image_tool':'boi_source_image'},
            'knowledge':{'catalog_tool':'boi_knowledge_catalog','read_tool':'boi_knowledge_read','query_default':'knowledge'},
            'authority':'Current authenticated principal and source rights; no caller-owned ACL or completion flags.',
            'instructions':'Read applicable package descriptions, choose by source meaning, then read its pinned skill. Preserve sources and start or resume one Wiki task. No Wiki model runs.'}

    from .knowledge_published_transport import register_published_document_routes
    register_published_document_routes(domain_router,service=service,principal=principal,call=domain_intake_call,
        templates=templates,shell_context_factory=shell_context_factory)

    @domain_router.get('/knowledge', response_class=HTMLResponse)
    async def knowledge_portal(http_request: Request, tab: Literal['knowledge','packages','work','inbox']='knowledge',
            q: str=Query(default='',max_length=2000), cursor: str=Query(default='',max_length=90),
            bundle_cursor: str=Query(default='',max_length=100),
            feedback_cursor: str=Query(default='',max_length=2048),
            scope: Literal['private','team','public','legacy']='private',team:str|None=Query(default=None,max_length=200),
            identity: Principal=Depends(principal)):
        from .knowledge_portal import render_knowledge_portal
        require_scope(identity, 'boi.read')
        if templates is None or shell_context_factory is None:
            raise HTTPException(status_code=503, detail={'reason_code':'KNOWLEDGE_PORTAL_TEMPLATES_UNAVAILABLE'})
        knowledge, packages, work, supervision, next_cursor, capabilities = [], [], [], [], None, None
        bundle_next_url = None
        feedback,feedback_next_url=[],None
        scope_options=[]
        text_search = None
        if tab == 'knowledge':
            from urllib.parse import urlencode
            current=service.domain_intake._current_identity(identity)
            choices=[('private',None,'나만 보기'),*[('team',t,'팀 · '+t) for t in sorted(current.teams)],
                ('public',None,'전체 공개'),('legacy',None,'이전 지식')]
            scope_options=[{'label':label,'active':scope==s and team==t,
                'url':'/knowledge?'+urlencode({'scope':s,**({'team':t} if t else {}),**({'q':q} if q else {})})} for s,t,label in choices]
            if scope!='team' and team is not None:raise HTTPException(status_code=400,detail={'reason_code':'KNOWLEDGE_SPACE_TEAM_NOT_APPLICABLE'})
            if scope=='team' and (team is None or team not in current.teams):raise HTTPException(status_code=403,detail={'reason_code':'KNOWLEDGE_SPACE_ACCESS_DENIED'})
            catalog = await domain_intake_call(service.domain_intake.catalog_for_humans, identity,
                DomainAssetCatalogRequest(query=q, cursor=cursor, limit=30, purpose='knowledge',
                    target_space=None if scope=='legacy' else {'visibility':scope,**({'team_id':team} if team else {})}))
            knowledge, next_cursor = catalog['items'], catalog['next_cursor']
            if scope != 'legacy' and q:
                text_search = {key:catalog[key] for key in ('matching_documents','visible_documents','unprepared_documents')}
            if scope!='legacy':
                knowledge=[{**row,'status':'published'} for row in knowledge]
        elif tab == 'packages':
            catalog = await domain_intake_call(service.domain_intake.domain_packages, identity,
                DomainPackageRequest(operation='discover'))
            packages = catalog.get('packages', catalog.get('items', []))
            capabilities = catalog.get('hotl')
        elif tab == 'inbox':
            from urllib.parse import urlencode
            result=await domain_intake_call(service.domain_intake.knowledge_supervision,identity,
                KnowledgeSupervisionRequest(operation='feedback_inbox',request={'after':feedback_cursor}))
            feedback=result['items']
            if result['next_after']:
                feedback_next_url='/knowledge?'+urlencode({'tab':'inbox','feedback_cursor':result['next_after']})
        else:
            catalog = await domain_intake_call(service.domain_intake.knowledge_work, identity,
                KnowledgeWorkRequest(operation='list'))
            work = catalog['items']
            supervision = [event for item in work for event in item.get('supervision', {}).get('items', [])]
            local = await domain_intake_call(service.domain_intake.knowledge_work, identity,
                KnowledgeWorkRequest(operation='publication', request={'phase':'list', 'payload':{'after_key':bundle_cursor}}))
            work = [*local['items'], *work]
            if local['next_cursor']:
                from urllib.parse import urlencode
                bundle_next_url = '/knowledge?' + urlencode({'tab':'work','bundle_cursor':local['next_cursor']})
        return render_knowledge_portal(templates, http_request, shell_context_factory, identity,
            knowledge=knowledge, packages=packages, work=work, active_tab=tab, query=q, next_cursor=next_cursor,
            package_capabilities=capabilities, supervision=supervision, bundle_next_url=bundle_next_url,
            scope=scope,team=team,scope_options=scope_options,text_search=text_search,
            feedback=feedback,feedback_next_url=feedback_next_url)

    @domain_router.post('/api/v2/domain-intake/project')
    async def domain_source_project(payload: SourceProjectRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.project, identity, payload)

    @domain_router.post('/api/v2/domain-intake/fields/read')
    async def domain_source_read_field(payload: SourceFieldReadRequest | SourceFieldBatchReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_field, identity, payload)

    @domain_router.post('/api/v2/domain-intake/images/transcribe')
    async def domain_source_transcribe_image(payload: SourceImageTranscriptionRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.transcribe_image, identity, payload)

    @domain_router.post('/api/v2/domain-intake/images/read')
    async def domain_source_read_image(payload: SourceImageReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_image, identity, payload)

    @domain_router.post('/api/v2/domain-intake/assets/catalog')
    async def domain_asset_catalog(payload: DomainAssetCatalogRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.catalog_assets, identity, payload)

    @domain_router.get('/api/v2/domain-intake/formulas/schema')
    async def domain_formula_schema(identity: Principal = Depends(principal)):
        from .native_formula import NativeFormulaRequest
        from ..governed_runtime.semantic_binding_contract import semantic_digest
        require_scope(identity,'boi.read')
        schema=NativeFormulaRequest.model_json_schema()
        return {'request_schema':schema,'schema_digest':semantic_digest(schema)}

    @domain_router.post('/api/v2/domain-intake/formulas/preview')
    async def domain_native_formula(payload: NativeFormulaRequest, identity: Principal = Depends(principal)):
        from functools import partial
        from .native_formula import preview_for_principal_scoped
        require_scope(identity, 'boi.read')
        return await domain_intake_call(partial(preview_for_principal_scoped, service.domain_intake), identity, payload)

    async def formula_result(digest,identity):
        from pydantic import TypeAdapter
        from ..governed_runtime.semantic_binding_contract import Digest
        from .native_formula import read_formula_for_principal
        require_scope(identity,'boi.read')
        try:reference=TypeAdapter(Digest).validate_python('sha256:'+digest)
        except ValueError:raise HTTPException(status_code=404,detail='FORMULA_RESULT_NOT_FOUND') from None
        return await domain_intake_call(lambda principal,payload:read_formula_for_principal(service.domain_intake,principal,payload),identity,reference)

    @domain_router.get('/api/v2/domain-intake/formulas/results/{digest}')
    async def native_formula_result(digest: str,identity: Principal=Depends(principal)):
        return await formula_result(digest,identity)

    @domain_router.get('/native-formulas/{digest}',response_class=HTMLResponse)
    async def native_formula_page(digest: str,identity: Principal=Depends(principal)):
        from .native_formula import render_formula_result
        value=await formula_result(digest,identity)
        return HTMLResponse(render_formula_result(value),headers={'Cache-Control':'private, no-store'})

    @domain_router.get('/api/v2/domain-intake/native-queries')
    async def domain_native_query_discover(identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(lambda who, _: discover_native_queries(service.domain_intake, who), identity, None)

    @domain_router.get('/api/v2/domain-intake/native-queries/source_discover')
    async def domain_database_sources(identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(lambda who, value: database_source_call(
            service.domain_intake, who, action='source_discover'), identity, None)

    @domain_router.post('/api/v2/domain-intake/native-queries/source_schema')
    async def domain_database_schema(payload: DatabaseSourceRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(lambda who, value: database_source_call(
            service.domain_intake, who, value, action='source_schema'), identity, payload)

    @domain_router.post('/api/v2/domain-intake/native-queries/source_capture')
    async def domain_database_capture(payload: DatabaseSourceRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(lambda who, value: database_source_call(
            service.domain_intake, who, value, action='source_capture'), identity, payload)

    @domain_router.post('/api/v2/domain-intake/native-queries/source_bind')
    async def domain_database_bind(payload: DatabaseBindRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(lambda who, value: bind_database_query(
            service.domain_intake, who, value), identity, payload)

    @domain_router.get('/api/v2/domain-intake/native-queries/registration-sources')
    async def domain_native_query_registration_sources(identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(
            lambda who, _: discover_native_query_registration_sources(service.domain_intake, who),
            identity, None)

    @domain_router.post('/api/v2/domain-intake/native-queries/registrations')
    async def domain_native_query_registration(payload: NativeQueryRegistrationRequest,
            identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(
            lambda who, value: register_native_query_source(service.domain_intake, who, value),
            identity, payload)

    async def native_query_call(action, payload, identity):
        from functools import partial
        require_scope(identity, 'boi.read')
        return await domain_intake_call(partial(native_query_for_principal, service.domain_intake, action=action), identity, payload)

    @domain_router.post('/api/v2/domain-intake/native-queries/prepare')
    async def domain_native_query_prepare(payload: NativeQueryPrepareRequest, identity: Principal = Depends(principal)):
        return await native_query_call('prepare', payload, identity)

    @domain_router.post('/api/v2/domain-intake/native-queries/plan')
    async def domain_native_query_plan(payload: NativeQueryPlanRequest, identity: Principal = Depends(principal)):
        return await native_query_call('plan', payload, identity)

    @domain_router.post('/api/v2/domain-intake/native-queries/execute')
    async def domain_native_query_execute(payload: NativeQueryExecuteRequest, identity: Principal = Depends(principal)):
        return await native_query_call('execute', payload, identity)

    @domain_router.post('/api/v2/domain-intake/native-queries/result')
    async def domain_native_query_result(payload: NativeQueryResultRequest, identity: Principal = Depends(principal)):
        return await native_query_call('result', payload, identity)

    @domain_router.get('/native-query-results/{digest}', response_class=HTMLResponse)
    async def domain_native_query_result_page(digest: str,
            connection_id: str = Query(min_length=1), identity: Principal = Depends(principal)):
        from .native_query_result_view import render_native_query_result
        try:
            payload = NativeQueryResultRequest(connection_id=connection_id,
                execution_ref='evidence://sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,
                detail={'reason_code':'NATIVE_QUERY_RESULT_NOT_FOUND'}) from None
        value = await native_query_call('result', payload, identity)
        return HTMLResponse(render_native_query_result(value), headers={
            'Cache-Control':'private, no-store',
            'X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; "
                "frame-ancestors 'none'; base-uri 'none'"})

    @domain_router.post('/api/v2/domain-intake/native-queries/diagnose_empty')
    async def domain_native_query_diagnose_empty(payload: NativeQueryDiagnoseEmptyRequest,
            identity: Principal = Depends(principal)):
        return await native_query_call('diagnose_empty', payload, identity)

    @domain_router.post('/api/v2/domain-intake/assets/read')
    async def domain_asset_read(payload: DomainAssetReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_asset, identity, payload)

    @domain_router.post('/api/v2/domain-intake/assets/graph')
    async def domain_knowledge_graph(payload: DomainAssetReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_knowledge_graph, identity, payload)

    @domain_router.post('/api/v2/domain-intake/assets/propose')
    async def domain_asset_propose(payload: DomainAssetCreateRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.propose_asset, identity, payload)

    @domain_router.post('/api/v2/domain-intake/process-reviews/binding')
    async def process_review_binding(payload: ProcessReviewBindingRequest,identity: Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.read_process_review_binding,identity,payload)

    @domain_router.post('/api/v2/domain-intake/process-coverage/read')
    async def domain_process_coverage(payload: DomainAssetReadRequest,identity: Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.read_process_coverage,identity,payload)

    @domain_router.get('/domain-coverage/{digest}',response_class=HTMLResponse)
    async def domain_process_coverage_page(digest: str,identity: Principal=Depends(principal)):
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        from .process_coverage_view import process_coverage_page
        require_scope(identity,'boi.read')
        try:revision=RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
        except ValueError:raise HTTPException(status_code=404,detail={'reason_code':'PROCESS_COVERAGE_NOT_FOUND'}) from None
        value=await domain_intake_call(service.domain_intake.read_process_coverage,identity,DomainAssetReadRequest(revision=revision,lane='provisional'))
        return HTMLResponse(process_coverage_page(value),headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"})

    @domain_router.post('/api/v2/domain-intake/process-results/read')
    async def domain_process_result(payload: DomainAssetReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.read_process_result,identity,payload)

    @domain_router.post('/api/v2/domain-intake/process-results/answer')
    async def domain_process_answer(payload: DomainAssetReadRequest, identity: Principal = Depends(principal)):
        from .process_citation_display import read_process_answer_or_navigation
        require_scope(identity,'boi.read')
        return await domain_intake_call(lambda principal,request: read_process_answer_or_navigation(
            service.domain_intake,principal,request,source_base_url=os.environ.get('BOI_EXTERNAL_URL')),identity,payload)

    @domain_router.get('/domain-results/{digest}',response_class=HTMLResponse)
    async def domain_process_result_page(digest: str, identity: Principal = Depends(principal)):
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        from .process_result_view import process_result_page,process_result_csp
        require_scope(identity,'boi.read')
        try:
            revision=RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,detail={'reason_code':'PROCESS_RESULT_NOT_FOUND'}) from None
        value=await domain_intake_call(service.domain_intake.read_process_result,identity,
            DomainAssetReadRequest(revision=revision,lane='provisional'))
        return HTMLResponse(process_result_page(value),headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':process_result_csp()})

    @domain_router.post('/api/v2/domain-intake/native-results/compose')
    async def domain_native_answer_compose(payload: NativeAnswerComposition | NativePreparedComposition | NativeAuthoringComposition, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        from .store_observation import observe_native_result
        return await domain_intake_call(lambda principal,request: observe_native_result(lambda: compose_native_response(
            service.domain_intake,principal,request,source_base_url=os.environ.get('BOI_EXTERNAL_URL'))),identity,payload)

    @domain_router.post('/api/v2/domain-intake/native-results/composition/read')
    async def domain_native_composition_read(payload: NativeCompositionRead, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        from .store_observation import observe_native_result
        return await domain_intake_call(lambda principal,request: observe_native_result(lambda: read_native_composition(
            service.domain_intake,principal,request)),identity,payload)

    @domain_router.get('/native-compositions/{digest}',response_class=HTMLResponse)
    async def domain_native_composition_page(digest: str, http_request: Request, identity: Principal = Depends(principal)):
        from .native_composition_result import render_composition_result
        require_scope(identity,'boi.read')
        try:request=NativeCompositionRead(composition_ref='sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,detail={'reason_code':'NATIVE_COMPOSITION_RESULT_NOT_FOUND'}) from None
        message=await domain_intake_call(lambda principal,request: read_native_composition(
            service.domain_intake,principal,request),identity,request)
        if templates is not None and shell_context_factory is not None:
            from .knowledge_portal import render_knowledge_record
            return render_knowledge_record(templates, http_request, shell_context_factory, identity,
                title='답변과 근거', fragment=render_composition_result(message, fragment=True), kind='composition')
        return HTMLResponse(render_composition_result(message),headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})

    @domain_router.post('/api/v2/domain-intake/native-results/answer')
    async def domain_native_answer(payload: DomainAssetReadRequest, identity: Principal = Depends(principal),
            view: Literal['answer','binding'] = Query(default='answer')):
        from .native_answer_delivery import read_native_answer_for_request
        require_scope(identity,'boi.read')
        return await domain_intake_call(lambda principal,request: read_native_answer_for_request(
            service.domain_intake,principal,request,source_base_url=os.environ.get('BOI_EXTERNAL_URL'),
            evidence_detail=view=='binding'),identity,payload)

    @domain_router.post('/api/v2/domain-intake/definition-sources/read')
    async def native_definition_sources_read(payload: DefinitionSourceReadRequest, identity: Principal = Depends(principal)):
        from .native_definition_sources import read_definition_sources, selected_source_model_view
        from agent_kit.python.boi_process_answer_stage import composition_model_material
        require_scope(identity,'boi.read')
        def read(principal,request):
            if request.view=='meaning_index':
                if request.meaning_pointers is not None:raise ValueError('MEANING_SELECTION_REQUIRES_SOURCE_VIEW')
                from .asset_user_views import read_meaning_index
                return read_meaning_index(service.domain_intake,principal,request.revision)
            pointers=list(request.meaning_pointers) if request.meaning_pointers is not None else None
            if pointers is not None and len(set(pointers))!=len(pointers):raise ValueError('ANSWER_MEANING_SELECTION_DUPLICATE')
            result=read_definition_sources(service.domain_intake,principal,
                DomainAssetReadRequest(revision=request.revision,lane=request.lane),
                meaning_pointer=pointers,source_base_url=os.environ.get('BOI_EXTERNAL_URL'))
            return composition_model_material(selected_source_model_view(result) if pointers is not None else result)
        return await domain_intake_call(read,identity,payload)

    @domain_router.get('/native-definitions/{digest}',response_class=HTMLResponse)
    async def native_definition_source_page(digest: str, http_request: Request, fields: str | None = Query(default=None,max_length=20000), meaning: str | None = Query(default=None,max_length=2048), source_offset: int | None = Query(default=None,ge=0), group: str | None = Query(default=None,min_length=64,max_length=64), identity: Principal = Depends(principal)):
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        from .native_definition_sources import read_definition_sources,render_definition_sources,source_selection_csp
        require_scope(identity,'boi.read')
        try:
            revision=RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,detail={'reason_code':'NATIVE_DEFINITION_NOT_FOUND'}) from None
        if sum(v is not None for v in (meaning,fields,group))>1:
            raise HTTPException(status_code=400,detail={'reason_code':'DEFINITION_SOURCE_SELECTION_AMBIGUOUS'})
        from ..governed_runtime.knowledge_published_read import PublishedDocumentRead
        from .knowledge_published_transport import published_page
        published=await domain_intake_call(lambda actor,request:service.domain_intake.published_document(
            actor,request,model_input=False,allow_legacy=True),identity,
            PublishedDocumentRead(revision=revision,meaning_pointer=meaning or None))
        if published is not None:
            if fields is not None or group is not None or source_offset is not None:
                raise HTTPException(status_code=400,detail={'reason_code':'KNOWLEDGE_DOCUMENT_EXACT_SOURCE_BINDING_REQUIRED'})
            return published_page(published,templates=templates,request=http_request,
                shell_context_factory=shell_context_factory,identity=identity)
        value=await domain_intake_call(lambda principal,payload: read_definition_sources(
            service.domain_intake,principal,payload,meaning_pointer=meaning,source_offset=source_offset,meaning_group=group),identity,
            DomainAssetReadRequest(revision=revision,lane='provisional'))
        try:
            shell = templates is not None and shell_context_factory is not None
            page=render_definition_sources(value,selected_fields=fields.split(',') if fields is not None else (), fragment=shell)
        except ValueError as error:
            raise HTTPException(status_code=400,detail={'reason_code':str(error)}) from None
        if shell:
            from .knowledge_portal import render_knowledge_record
            if value.get('asset_kind') == 'definition':
                from .knowledge_graph_view import render_knowledge_graph
                graph = await domain_intake_call(service.domain_intake.read_knowledge_graph, identity,
                    DomainAssetReadRequest(revision=revision,lane='provisional'))
                page += render_knowledge_graph(graph, '/native-definitions/' + digest)
            return render_knowledge_record(templates, http_request, shell_context_factory, identity,
                title='지식과 원문 근거', fragment=page, kind='definition')
        return HTMLResponse(page,headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':source_selection_csp()})

    @domain_router.get('/c/{reference}/{answer_index}/{citation_index}')
    async def native_composition_citation_page(reference: str, answer_index: int, citation_index: int, http_request: Request, identity: Principal=Depends(principal)):
        from .native_composition_result import read_composition_citation_view
        from .native_definition_sources import render_definition_sources,source_selection_csp
        require_scope(identity,'boi.read')
        result=await domain_intake_call(lambda principal,payload: read_composition_citation_view(
            service.domain_intake,principal,reference,answer_index,citation_index,legacy_redirect=True),identity,None)
        if 'answer_reading_scopes' not in result['view']:
            return RedirectResponse(result['source_url'],status_code=303,headers={'Cache-Control':'private, no-store'})
        if templates is not None and shell_context_factory is not None:
            from .knowledge_portal import render_knowledge_record
            return render_knowledge_record(templates, http_request, shell_context_factory, identity,
                title='인용한 원문 근거', fragment=render_definition_sources(result['view'], fragment=True), kind='source',
                return_url=result.get('answer_url'))
        return HTMLResponse(render_definition_sources(result['view']),headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':source_selection_csp()})

    @domain_router.get('/native-results/{digest}',response_class=HTMLResponse)
    async def native_answer_result_page(digest: str, identity: Principal = Depends(principal)):
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        from .native_answer_delivery import read_native_answer_page,render_native_answer
        require_scope(identity,'boi.read')
        try:
            revision=RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,detail={'reason_code':'NATIVE_RESULT_NOT_FOUND'}) from None
        value=await domain_intake_call(lambda principal,payload: read_native_answer_page(service.domain_intake,principal,payload),identity,
            DomainAssetReadRequest(revision=revision,lane='provisional'))
        return HTMLResponse(render_native_answer(value),headers={'Cache-Control':'private, no-store',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"})

    @domain_router.get('/native-results/{digest}/sources/{number}')
    async def native_answer_original_source_link(digest: str, number: int, identity: Principal=Depends(principal)):
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        from .native_answer_delivery import read_native_answer_page,native_answer_source_link
        require_scope(identity,'boi.read')
        try:
            revision=RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
        except ValueError:
            raise HTTPException(status_code=404,detail={'reason_code':'NATIVE_RESULT_NOT_FOUND'}) from None
        value=await domain_intake_call(lambda principal,payload: read_native_answer_page(service.domain_intake,principal,payload),identity,
            DomainAssetReadRequest(revision=revision,lane='provisional'))
        try:
            target=native_answer_source_link(value,number,source_base_url=os.environ.get('BOI_EXTERNAL_URL'))
        except ValueError as error:
            raise HTTPException(status_code=404,detail={'reason_code':str(error)}) from None
        return RedirectResponse(target,status_code=303,headers={'Cache-Control':'private, no-store'})

    @domain_router.post('/api/v2/domain-intake/context/prepare')
    async def domain_context_prepare(payload: DomainContextPrepareRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.prepare_context, identity, payload)

    @domain_router.post('/api/v2/domain-intake/context/page')
    async def domain_context_page(payload: DomainContextPageRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_context_page, identity, payload)

    @domain_router.post('/api/v2/domain-intake/context/acknowledge')
    async def domain_context_acknowledge(payload: DomainContextAcknowledgeRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.acknowledge_context, identity, payload)

    @domain_router.post('/api/v2/domain-intake/work/lookup')
    async def domain_work_lookup(payload: DomainWorkLookupRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.lookup_work,identity,payload)

    @domain_router.post('/api/v2/domain-intake/context/restore')
    async def domain_context_restore(payload: DomainContextRestoreRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.restore_context,identity,payload)

    @domain_router.post('/api/v2/domain-intake/work/start')
    async def domain_work_start(payload: DomainWorkStartRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        return await domain_intake_call(service.domain_intake.start_work,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/prepare')
    async def domain_tool_prepare(payload: DomainToolPrepareRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.execute.low')
        return await domain_intake_call(service.domain_intake.prepare_tool,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/read')
    async def domain_tool_read(payload: DomainToolReadRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_tool,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/lookup')
    async def domain_tool_lookup(payload: DomainToolLookupRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        return await domain_intake_call(service.domain_intake.lookup_tool,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/dispatch')
    async def domain_tool_dispatch(payload: DomainToolDispatchRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.execute.low')
        return await domain_intake_call(service.domain_intake.dispatch_tool,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/input')
    async def domain_tool_input(payload: DomainToolInputRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_tool_input,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/submit')
    async def domain_tool_submit(payload: DomainToolSubmitRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.execute.low')
        return await domain_intake_call(service.domain_intake.submit_tool,identity,payload)

    @domain_router.post('/api/v2/domain-intake/work/complete')
    async def domain_work_complete(payload: DomainWorkCompleteRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.execute.low')
        return await domain_intake_call(service.domain_intake.complete_work,identity,payload)

    @domain_router.post('/api/v2/domain-intake/tools/evidence')
    async def domain_tool_evidence(payload: DomainToolEvidenceRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await domain_intake_call(service.domain_intake.read_tool_evidence,identity,payload)

    router.include_router(domain_router)

    @router.get("/api/v2/bootstrap")
    async def bootstrap(
        page_ref: str = "",
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        public_base = os.environ.get("BOI_EXTERNAL_URL", "").rstrip("/")
        from .native_composition_result import read_composition_citation_material
        native_source=await domain_intake_call(lambda principal,payload: read_composition_citation_material(
            service.domain_intake,principal,page_ref,source_base_url=public_base),identity,None)
        if native_source is not None:
            return {'page':{'kind':'native_citation','native_source':native_source},
                'scope':'Current authorized original evidence for this exact stored citation; not new review or execution.'}
        readiness = service.readiness(identity)
        from .native_answer_delivery import native_result_revision_from_page_ref, native_page_digest, read_native_answer_for_request
        native_revision = native_result_revision_from_page_ref(page_ref, source_base_url=public_base)
        composition_ref = native_page_digest(page_ref, source_base_url=public_base, route='/native-compositions/')
        native_answer = None
        native_read_arguments = None
        if native_revision is not None:
            # The URL selects an immutable result, not authority or a new answer.
            # Reuse exactly the current reader used by boi_native_answer, including
            # its stale-dependency outcome and principal/source access checks.
            native_answer = await domain_intake_call(
                lambda principal, request: read_native_answer_for_request(
                    service.domain_intake, principal, request, source_base_url=public_base),
                identity, DomainAssetReadRequest(revision=native_revision, lane='provisional'))
            page_kind = 'native_result'
            page_context = ContextAnchor(
                ref=native_revision.ref, kind=page_kind,
                title=native_answer.get('question') or '저장 답변',
                url='/native-results/' + native_revision.revision_digest.removeprefix('sha256:'),
                revision=native_revision.revision_digest, resolved=True, context_resolution='route')
            native_read_arguments = {'revision': native_revision.model_dump(mode='json')}
        elif composition_ref is not None:
            from .native_composition_result import read_native_composition, NativeCompositionRead
            native_answer = await domain_intake_call(
                lambda principal, request: read_native_composition(service.domain_intake, principal, request),
                identity, NativeCompositionRead(composition_ref=composition_ref))
            page_kind = 'native_composition'
            page_context = ContextAnchor(
                ref=composition_ref, kind=page_kind, title=native_answer.get('question') or '저장 답변',
                url='/native-compositions/' + composition_ref.removeprefix('sha256:'),
                revision=composition_ref, resolved=True, context_resolution='route')
            native_read_arguments = {'composition_ref': composition_ref, 'view': 'answer','purpose':'recorded'}
        else:
            page_kind = service.page_kind(page_ref)
            page_context = service.learning.contexts.page_anchor(identity, page_ref)
        if (page_context and page_context.url.startswith("/")
                and not page_context.url.startswith("//")
                and urlsplit(public_base).scheme in {"http", "https"}
                and urlsplit(public_base).netloc):
            page_context.url = public_base + page_context.url
        if page_context and page_context.navigation_guidance.get("body"):
            # Bind the returned original to its own address and observed revision.
            # The caller's page_ref remains an input reference, not a citation.
            page_context.navigation_guidance["source"] = {
                "title": page_context.title,
                "url": page_context.url,
                "revision": page_context.revision,
                "content_digest": page_context.navigation_guidance.get("content_digest", ""),
            }
        if page_context and page_context.knowledge_context.get("science"):
            page_context.knowledge_context["source"] = {
                "title": page_context.title, "url": page_context.url,
                "revision": page_context.revision,
                "content_digest": page_context.knowledge_context.get("content_digest", ""),
            }
        if page_context and page_context.resolved:
            page_kind = {
                "sop": "sop",
                "workflow": "sop",
                "event": "event",
                "action": "action",
            }.get(page_context.kind, page_kind)
        starters = [] if native_answer is not None else service.starter_suggestions(identity, page_ref=page_ref, limit=8)
        harness_package = service.current_harness_package()
        search_sync_state = str(((readiness.get("search") or {}).get("index") or {}).get("sync_state") or "ready")
        readiness_state = str(readiness.get("state") or ("ready" if readiness.get("ready") else "unavailable"))
        readiness_warnings = [str(item) for item in readiness.get("warnings") or [] if str(item)]
        surface_status = {
            "state": (
                "unavailable"
                if readiness_state == "unavailable"
                else "updating"
                if search_sync_state == "syncing"
                else "degraded"
                if readiness_state == "degraded"
                else "ready"
            ),
            "message": (
                "BoI Agent의 필수 모델 또는 콘텐츠가 준비되지 않았습니다."
                if readiness_state == "unavailable"
                else "새 지식을 반영 중입니다."
                if search_sync_state == "syncing"
                else readiness_warnings[0]
                if readiness_state == "degraded" and readiness_warnings
                else ""
            ),
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
                **({'native_answer': native_answer,
                    'available_user_views': [{
                        'tool': 'boi_native_answer',
                        'arguments': native_read_arguments,
                        'purpose': 'This result was already read into page.native_answer; use its answer and exact source/result links without repeating the read.',
                        'scope': 'Current request fit, semantic support and actual final delivery remain unverified.',
                    }] if (native_answer.get('readable_text') or native_answer.get('answers')) and native_answer.get('status') != 'requires_revalidation' else []}
                   if native_answer is not None else {}),
            },
            "capabilities": service.registry.public_payload(
                principal=identity,
                readiness=readiness["dependencies"],
            ),
            "offers": [],
            "starters": [item.model_dump(mode="json") for item in starters],
            "readiness": {
                "ready": readiness["ready"],
                "core_ready": readiness["core_ready"],
                "fully_ready": readiness["fully_ready"],
                "state": readiness_state,
                "dependencies": readiness["dependencies"],
                "capabilities": readiness["capabilities"],
                "warnings": readiness_warnings,
                "surface_status": surface_status,
            },
            "harness": {
                "client_surface": "web",
                "binding": "embedded",
                "release": harness_package["release"],
                "checksum": harness_package["checksum"],
                "signature": harness_package["signature"],
                "signature_status": harness_package["signature_status"],
                "resource": "boi://harness/current",
                "client_binding": harness_package["client_bindings"]["web"],
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

    @router.post("/api/v2/skill-invocations/preview")
    async def preview_skill_invocation(
        request: SkillInvocationPreviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.preview_skill_invocation(identity, request)

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
            response = await run_in_threadpool(service.run_turn, identity, payload)
            return response.model_dump(mode="json")
        request_id = service.register_turn_request(identity, payload)

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
                    "request_id": request_id,
                },
            )
            task = asyncio.create_task(
                run_in_threadpool(
                    service.run_turn,
                    identity,
                    payload,
                    progress_sink=emit,
                )
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

    @router.post("/api/v2/agent/turns/{request_id}/cancel")
    async def cancel_agent_turn(
        request_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.cancel_turn_request(identity, request_id)

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

    @router.get("/api/v2/completion-records/{completion_id}")
    async def completion_record(
        completion_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.view_completion_record(identity, completion_id)

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

    @router.post("/api/v2/work-runs/{work_run_id}/cancel")
    async def cancel_work_run(
        work_run_id: str,
        request: WorkRunCancelRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.learning.cancel_run(identity, work_run_id, request)

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
    def reindex(identity: Principal = Depends(principal)) -> dict[str, Any]:
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
        view: str = Query(default="neighbors", min_length=1, max_length=80),
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

    @router.get("/api/v2/ontology/schema/current")
    async def current_ontology_schema(
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.ontology_schema()

    @router.get("/api/v2/ontology/projections/{projection_id}")
    async def ontology_projection(
        projection_id: str,
        subject_ref: str = Query(min_length=1),
        as_of: str = "",
        limit: int = Query(default=200, ge=1, le=500),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.project(
            identity,
            projection_id=projection_id,
            subject_ref=subject_ref,
            as_of=as_of,
            limit=limit,
        )

    @router.post("/api/v2/ontology/query")
    async def query_ontology(
        request: OntologyQueryRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.query_ontology(identity, request)

    @router.post("/api/v2/ontology/proposals")
    async def create_ontology_proposal(
        request: OntologyProposalCreateRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.create_ontology_proposal(identity, request)

    @router.get("/api/v2/ontology/proposals/{proposal_id}")
    async def get_ontology_proposal(
        proposal_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.ontology_proposal(identity, proposal_id)

    @router.post("/api/v2/ontology/proposals/{proposal_id}/review")
    async def review_ontology_proposal(
        proposal_id: str,
        request: OntologyProposalReviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.review_ontology_proposal(
            identity,
            proposal_id,
            request,
        )

    @router.post("/api/v2/ontology/proposals/{proposal_id}/publish")
    async def publish_ontology_proposal(
        proposal_id: str,
        request: OntologyProposalPublishRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.knowledge.publish_ontology_proposal(
            identity,
            proposal_id,
            request,
        )

    @router.post("/api/v2/event-runtime/definitions/preview")
    async def preview_event_runtime_definition(
        request: EventRuntimeDefinitionPreviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return await service.platform.preview_event_definition(identity, request)

    @router.post("/api/v2/event-runtime/plans/{plan_id}/activate")
    async def activate_event_runtime_definition(
        plan_id: str,
        request: EventRuntimeActivationRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return await service.platform.activate_event_definition(identity, plan_id, request)

    @router.post("/api/v2/event-runtime/signals/evaluate")
    async def evaluate_event_runtime_signal(
        request: EventRuntimeSignalRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return await service.platform.evaluate_signal(identity, request)

    @router.get("/api/v2/event-runtime/occurrences/{event_occurrence_id}")
    async def get_event_runtime_occurrence(
        event_occurrence_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.get_event_occurrence(identity, event_occurrence_id)

    @router.get("/api/v2/event-runtime/definitions/{definition_id}/detector-decisions")
    async def get_event_runtime_detector_decisions(
        definition_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.list_detector_decisions(identity, definition_id)

    @router.get("/api/v2/workflow-runs/{workflow_run_id}")
    async def get_platform_workflow_run(
        workflow_run_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.get_workflow_run(identity, workflow_run_id)

    @router.get("/api/v2/task-runs/{task_run_ref:path}")
    async def get_platform_task_run(
        task_run_ref: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.get_task_run(identity, task_run_ref)

    @router.get("/api/v2/outcomes/{outcome_ref:path}")
    async def get_platform_outcome(
        outcome_ref: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.get_outcome(identity, outcome_ref)

    @router.get("/api/v2/agent-tasks")
    async def list_external_agent_tasks(
        status: str = "",
        limit: int = Query(default=20, ge=1, le=100),
        run_id: str = "",
        cursor: str = Query(default="", max_length=100),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.list_agent_tasks(identity, status=status, limit=limit,run_id=run_id,cursor=cursor)

    @router.post("/api/v2/agent-tasks/materialize")
    async def materialize_external_agent_task(
        request: AgentTaskMaterializeRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.materialize_agent_task(identity, request)

    @router.get("/api/v2/agent-tasks/{task_package_id}")
    async def get_external_agent_task(
        task_package_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.platform.get_agent_task(identity, task_package_id)

    @router.post("/api/v2/agent-tasks/{task_package_id}/claim")
    async def claim_external_agent_task(
        task_package_id: str,
        request: AgentTaskClaimRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.claim_agent_task(identity, task_package_id, request)

    @router.post("/api/v2/agent-tasks/{task_package_id}/heartbeat")
    async def heartbeat_external_agent_task(
        task_package_id: str,
        request: AgentTaskHeartbeatRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.heartbeat_agent_task(identity, task_package_id, request)

    @router.post("/api/v2/agent-tasks/{task_package_id}/submit")
    async def submit_external_agent_task(
        task_package_id: str,
        request: AgentTaskSubmitRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.submit_agent_task(identity, task_package_id, request)

    @router.post("/api/v2/agent-tasks/{task_package_id}/verify")
    async def verify_external_agent_task(
        task_package_id: str,
        request: AgentTaskVerifyRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.verify_agent_task(identity, task_package_id, request)

    @router.post("/api/v2/agent-tasks/{task_package_id}/release")
    async def release_external_agent_task(
        task_package_id: str,
        request: AgentTaskReleaseRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.release_agent_task(identity, task_package_id, request)

    @router.post("/api/v2/agent-tasks/{task_package_id}/cancel")
    async def cancel_external_agent_task(
        task_package_id: str,
        request: AgentTaskCancelRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.execute.low")
        return service.platform.cancel_agent_task(identity, task_package_id, request)

    @router.get("/api/v2/runtime/state-digest")
    async def runtime_state_digest(
        scope: str = Query(min_length=1, max_length=120),
        task_ref: str = Query(default="", max_length=1000),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.runtime_state_digest(
            identity,
            scope=scope,
            task_ref=task_ref,
        )

    @router.get("/api/v2/knowledge-health")
    async def knowledge_health(
        refresh: bool = False,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.health(identity, refresh=refresh)

    @router.post("/api/v2/knowledge-health/scan")
    async def scan_knowledge_health(
        request: KnowledgeHealthScanRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.knowledge.scan_health(identity, request)

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

    @router.post("/api/v2/harness-code-patches")
    async def create_harness_code_patch_artifact(
        request: HarnessCodePatchArtifactRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        return service.learning.create_harness_code_patch_artifact(identity, request)

    @router.get("/api/v2/harness-code-patches")
    async def harness_code_patch_artifacts(
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.learning.list_harness_code_patch_artifacts(identity)

    @router.get("/api/v2/harness-code-patches/{patch_artifact_id}")
    async def harness_code_patch_artifact(
        patch_artifact_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        artifact = service.store.get("harness_code_patch_artifacts", patch_artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Harness patch artifact를 찾을 수 없습니다.")
        return artifact

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

    @router.get("/api/v2/harness-candidates")
    async def list_harness_candidates(
        status: str = "",
        limit: int = 50,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        if not identity.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        bounded_limit = max(1, min(int(limit), 200))
        items = service.store.list("harness_candidates", limit=1000)
        if status:
            items = [item for item in items if str(item.get("status") or "") == status]
        visible = []
        for item in items[:bounded_limit]:
            candidate_id = str(item.get("candidate_id") or "")
            visible.append(
                {
                    **item,
                    "review_url": f"/harness-candidates/{candidate_id}",
                    "surface_url": f"/api/v2/harness-candidates/{candidate_id}/surface",
                }
            )
        return {"ok": True, "items": visible, "count": len(visible)}

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

    @router.get("/api/v2/a2ui/catalogs/boi/v1")
    async def a2ui_boi_catalog(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        surfaces = service.store.list(
            "a2ui_surfaces",
            employee_id="" if identity.is_admin else identity.employee_id,
            limit=5000,
        )
        return capability_catalog(surfaces)

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

    @router.get("/api/v2/harness/current")
    async def current_harness_package(
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.current_harness_package()

    @router.get("/api/v2/harness/resources/{resource_uri:path}")
    async def harness_resource(
        resource_uri: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.harness_resource(resource_uri)

    @router.get("/api/v2/harness/bootstrap/{client}")
    async def harness_bootstrap(
        client: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.harness_bootstrap(client)

    @router.get("/api/v2/harness/local-lock")
    async def harness_local_lock(
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.harness_local_lock()

    @router.post("/api/v2/harness/local/offline/verify")
    async def harness_local_offline_verify(
        request: HarnessOfflineVerifyRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.harness_local_offline_verify(
            request.harness_lock,
            expected_checksum=request.expected_checksum,
        )

    @router.post("/api/v2/harness/local/update/preview")
    async def harness_local_update_preview(
        request: HarnessUpdatePreviewRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.harness_local_update_preview(
            request.current_lock,
            target_release=request.target_release,
        )

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

    @router.post("/api/v2/artifacts/{artifact_id}/proposals/{proposal_id}/apply")
    async def apply_artifact_proposal(
        artifact_id: str,
        proposal_id: str,
        request: ProposalApplyRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.apply_artifact_proposal(identity, artifact_id, proposal_id, request)

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
        request: Request,
        payload: CapabilityPlanRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        invocation_channel = request.headers.get(
            "x-boi-invocation-channel", "rest"
        ).strip().casefold()
        if invocation_channel not in {"ui", "rest", "mcp", "cli"}:
            raise HTTPException(status_code=400, detail="unsupported invocation channel")
        return service.create_plan(
            identity,
            capability_id,
            payload,
            invocation_channel=invocation_channel,
        ).model_dump(mode="json")

    @router.post("/api/v2/plans/{plan_id}/confirm")
    async def confirm_plan(
        plan_id: str,
        request: PlanConfirmRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return await service.confirm_plan(
            identity,
            plan_id,
            request.reason,
            expected_revision=request.expected_revision,
            plan_checksum=request.plan_checksum,
            input_fingerprint=request.input_fingerprint,
        )

    @router.post("/api/v2/deep-jobs")
    async def create_deep_job(request: DeepJobRequest, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.create_deep_job(identity, request)

    @router.get("/api/v2/deep-jobs/{job_id}")
    async def deep_job(job_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_job(identity, job_id)

    @router.get('/api/v2/ontology/migration-intake-options')
    async def ontology_migration_intake_options(identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity,'boi.read')
        return service.ontology_migration_intake_options(identity)

    @router.get("/api/v2/ontology/migration-jobs/{job_id}")
    async def ontology_migration_job(
        job_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.get_ontology_migration_job(identity, job_id)

    @router.get('/api/v2/ontology/migration-jobs/{job_id}/workbench')
    async def ontology_migration_workbench(job_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity,'boi.read')
        result=service.ontology_migration_workbench_view(identity,job_id)
        return {**result,'ui_url':f'/ontology/migrations/{job_id}'}

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/relations/quality-preview')
    async def preview_run_relation_quality(job_id: str, payload: RunRelationQualityPreviewRequest,
                                           identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity,'boi.draft')
        try:
            return await run_in_threadpool(service.preview_run_relation_quality,identity,
                run_id=job_id,**payload.model_dump(mode='json'))
        except ValueError as error:
            import re
            code=str(error)
            raise HTTPException(status_code=409,detail=code if re.fullmatch(
                r'[A-Z][A-Z0-9_]{1,120}',code) else 'RUN_RELATION_PREVIEW_REJECTED') from None

    @router.get("/api/v2/ontology/migration-jobs")
    async def ontology_migration_jobs(
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None, min_length=1, max_length=240),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.list_ontology_migration_jobs(
            identity, limit=limit, cursor=cursor
        )

    async def reviewed_query_call(call, *args, **kwargs):
        try:
            return await run_in_threadpool(call,*args,**kwargs)
        except ValueError as error:
            import re
            code=str(error)
            detail=code if re.fullmatch(r'[A-Z][A-Z0-9_]{1,120}',code) else 'REVIEWED_QUERY_REQUEST_REJECTED'
            if detail == 'REVIEWED_QUESTION_NATIVE_SUBMISSION_REQUIRED':
                raise HTTPException(status_code=409, detail={'reason_code': detail,
                    'semantic_status': 'UNDETERMINED'}) from None
            raise HTTPException(status_code=409,detail=detail) from None

    def reviewed_query_preparation(identity,job_id,digest):
        value=service._load_reviewed_query_preparation(identity,digest)
        if value['run_id']!=job_id:raise ValueError('REVIEWED_QUERY_RUN_MISMATCH')
        return value

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/prepare')
    async def prepare_reviewed_query(job_id: str, request: ReviewedQueryPrepareRequest,
                                     identity: Principal = Depends(principal)):
        require_scope(identity,'boi.draft')
        return await reviewed_query_call(service.prepare_reviewed_metadata_query,identity,
            run_id=job_id,**request.model_dump(mode='json'))

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/interpret')
    async def interpret_reviewed_question(job_id: str, request: Request,
            payload: ReviewedQuestionInterpretRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.draft')
        channel=request.headers.get('x-boi-invocation-channel','rest').strip().casefold()
        return await reviewed_query_call(service.interpret_reviewed_metadata_question,identity,
            run_id=job_id,invocation_channel=channel,**payload.model_dump(mode='json'))

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/natural/prepare')
    async def prepare_reviewed_natural_query(job_id: str, request: Request,
            payload: ReviewedQuestionInterpretRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.draft')
        channel=request.headers.get('x-boi-invocation-channel','rest').strip().casefold()
        return await reviewed_query_call(service.prepare_reviewed_metadata_natural_query,identity,
            run_id=job_id,invocation_channel=channel,**payload.model_dump(mode='json'))

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/execute')
    async def execute_reviewed_query(job_id: str, request: ReviewedQueryExecuteRequest,
                                     identity: Principal = Depends(principal)):
        require_scope(identity,'boi.draft')
        await reviewed_query_call(reviewed_query_preparation,identity,job_id,request.preparation_receipt_digest)
        result=await reviewed_query_call(service.execute_reviewed_metadata_query,identity,**request.model_dump())
        return result.model_dump(mode='json')

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/result')
    async def read_reviewed_query(job_id: str, request: ReviewedQueryReadRequest,
                                  identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        prepared=await reviewed_query_call(reviewed_query_preparation,identity,job_id,request.preparation_receipt_digest)
        result=await reviewed_query_call(service.read_reviewed_metadata_query_result,identity,
            artifact_ref=request.artifact_ref,purpose=prepared['logical_plan']['candidate_authority']['purpose'])
        if result['logical_plan_digest']!=prepared['logical_plan']['plan_digest']:
            raise HTTPException(status_code=409,detail='REVIEWED_QUERY_RESULT_PLAN_MISMATCH')
        return result

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/answer')
    async def read_reviewed_answer(job_id: str, request: ReviewedQueryReadRequest,
                                   identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        await reviewed_query_call(reviewed_query_preparation,identity,job_id,request.preparation_receipt_digest)
        return await reviewed_query_call(service.read_reviewed_metadata_query_answer,identity,**request.model_dump())

    @router.post('/api/v2/ontology/migration-jobs/{job_id}/queries/page')
    async def read_reviewed_page(job_id: str, request: ReviewedQueryPageRequest,
                                 identity: Principal = Depends(principal)):
        require_scope(identity,'boi.read')
        await reviewed_query_call(
            reviewed_query_preparation,identity,job_id,
            request.preparation_receipt_digest)
        return await reviewed_query_call(
            service.read_reviewed_metadata_query_page,identity,
            **request.model_dump())

    @router.post("/api/v2/ontology/migration-jobs/{job_id}/control")
    async def control_bulk_ontology_migration(
        job_id: str,
        request: BulkMigrationRunControlRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.control_bulk_ontology_migration(
            identity,
            job_id,
            **request.model_dump(),
        )

    @router.post("/api/v2/ontology/migration-jobs/{job_id}/approve")
    async def approve_ontology_migration(
        job_id: str,
        request: OntologyMigrationApproveRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.approve_ontology_migration_candidate(
            identity,
            job_id,
            **request.model_dump(),
            actor_role="user",
        )

    @router.post("/api/v2/ontology/migration-jobs/{job_id}/release-proposal")
    async def propose_ontology_migration_release(
        job_id: str,
        request: OntologyMigrationReleaseRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.propose_ontology_migration_release(
            identity,
            job_id,
            **request.model_dump(),
            actor_role="user",
        )

    @router.post("/api/v2/ontology/migration-jobs/{job_id}/mapping-edit")
    async def edit_ontology_migration_mapping(
        job_id: str,
        request: OntologyMigrationMappingPatchRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.edit_ontology_migration_mapping(
            identity,
            job_id,
            **request.model_dump(),
        )

    @router.post("/api/v2/deep-jobs/{job_id}/cancel")
    async def cancel_deep_job(job_id: str, identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.cancel_job(identity, job_id)

    @router.post("/api/v2/deep-jobs/{job_id}/restart")
    async def restart_deep_job(
        job_id: str,
        request: DeepJobRestartRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.draft")
        return service.restart_job(identity, job_id, request)

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

    @router.post("/api/v2/answers/questions")
    async def answer_verified_question(
        payload: VerifiedAnswerQuestionRequest,
        request: Request,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        invocation_channel = request.headers.get(
            "x-boi-invocation-channel", "rest"
        ).strip().casefold()
        return external_answer_payload(
            service.answer_verified_question(
                identity, payload, invocation_channel=invocation_channel
            )
        )

    @router.get("/api/v2/answers/{answer_id}")
    async def verified_answer_api(
        answer_id: str,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return external_answer_payload(service.get_verified_answer(identity, answer_id))

    @router.get('/api/v2/answers/{answer_id}/receipt')
    async def verified_answer_receipt(answer_id: str,
        purpose: str = Query(min_length=1, max_length=240),
        identity: Principal = Depends(principal)) -> dict[str, Any]:
        require_scope(identity, 'boi.read')
        return service.verified_answer_receipt(identity, answer_id, purpose=purpose)

    @router.get("/api/v2/answers/{answer_id}/views/{view_id}/rows")
    async def verified_answer_rows(
        answer_id: str,
        view_id: str,
        purpose: str = Query(min_length=1, max_length=240),
        page_size: int = Query(default=100, ge=1, le=1000),
        cursor: str | None = Query(default=None, min_length=1, max_length=4000),
        parent_identity: str | None = Query(default=None, max_length=4000),
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        parsed_parent_identity = None
        if parent_identity is not None:
            try:
                candidate = json.loads(parent_identity)
            except json.JSONDecodeError as error:
                raise HTTPException(
                    status_code=422, detail="ANSWER_PARENT_IDENTITY_INVALID"
                ) from error
            if not isinstance(candidate, dict):
                raise HTTPException(
                    status_code=422, detail="ANSWER_PARENT_IDENTITY_INVALID"
                )
            parsed_parent_identity = candidate
        return service.verified_answer_rows(
            identity,
            answer_id,
            view_id,
            purpose=purpose,
            page_size=page_size,
            cursor=cursor,
            parent_identity=parsed_parent_identity,
        )

    @router.post("/api/v2/answers/{answer_id}/exports")
    async def create_verified_answer_export(
        answer_id: str,
        payload: AnswerExportRequest,
        identity: Principal = Depends(principal),
    ) -> dict[str, Any]:
        require_scope(identity, "boi.read")
        return service.create_verified_answer_export(identity, answer_id, payload)

    @router.get("/api/v2/answers/{answer_id}/exports/{export_id}")
    async def get_verified_answer_export(
        answer_id: str,
        export_id: str,
        purpose: str = Query(min_length=1, max_length=240),
        identity: Principal = Depends(principal),
    ) -> Response:
        require_scope(identity, "boi.read")
        content, media_type, digest = service.get_verified_answer_export(
            identity, answer_id, export_id, purpose=purpose
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"x-boi-content-digest": digest},
        )

    if templates is not None and shell_context_factory is not None:

        @conditional_get(
            service.settings.qualification_answer_viewer_enabled,
            "/ontology/answers",
            response_class=HTMLResponse,
        )
        async def verified_answer_question_page(
            request: Request,
            identity: Principal = Depends(principal),
        ) -> HTMLResponse:
            require_scope(identity, "boi.read")
            return templates.TemplateResponse(
                "verified_answer_question.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="advanced",
                        title="검증 가능한 데이터 질문",
                        description="고정된 실행 결과에서 실제 값과 근거가 결박된 답을 만듭니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @conditional_get(
            service.settings.legacy_agent_ui_enabled,
            "/agent",
            response_class=HTMLResponse,
        )
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
                        agent_context={
                            "page_ref": str(request.query_params.get("page_ref") or ""),
                        },
                        hide_pet_agent=True,
                        mermaid_renderer_in_head=True,
                    ),
                },
            )

        @conditional_get(
            service.settings.legacy_agent_ui_enabled,
            "/helpers/new",
            response_class=HTMLResponse,
        )
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

        @conditional_get(
            service.settings.legacy_agent_ui_enabled,
            "/agent/access",
            response_class=HTMLResponse,
        )
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

        @conditional_get(
            service.settings.qualification_answer_viewer_enabled,
            "/ontology/answers/{answer_id}",
            response_class=HTMLResponse,
        )
        async def verified_answer_page(
            answer_id: str,
            request: Request,
            identity: Principal = Depends(principal),
        ) -> HTMLResponse:
            require_scope(identity, "boi.read")
            answer = service.get_verified_answer(identity, answer_id)
            return templates.TemplateResponse(
                "verified_answer.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "answer_record": answer,
                    "answer": answer["envelope"],
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="advanced",
                        title="검증 가능한 답변",
                        description="직접 답과 실제 결과를 먼저 보고 근거와 실행 receipt를 이어서 확인합니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/ontology/migrations", response_class=HTMLResponse)
        async def ontology_migrations_page(
            request: Request,
            cursor: str | None = Query(default=None, min_length=1, max_length=240),
            page_size: int = Query(default=25, ge=1, le=100),
            identity: Principal = Depends(principal),
        ) -> HTMLResponse:
            require_scope(identity, "boi.read")
            jobs = service.list_ontology_migration_jobs(
                identity, limit=page_size, cursor=cursor
            )
            return templates.TemplateResponse(
                "ontology_migrations.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "jobs": jobs["items"],
                    "migration_page": jobs,
                    "intake_options": service.ontology_migration_intake_options(identity),
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="advanced",
                        title="Ontology Migration Workbench",
                        description="Legacy source에서 Release 후보까지의 이관 상태와 예외를 검토합니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/ontology/migrations/{job_id}", response_class=HTMLResponse)
        async def ontology_migration_detail_page(
            job_id: str,
            request: Request,
            identity: Principal = Depends(principal),
        ) -> HTMLResponse:
            require_scope(identity, "boi.read")
            view = service.ontology_migration_workbench_view(identity, job_id)
            return templates.TemplateResponse(
                "ontology_migration_detail.html",
                {
                    "request": request,
                    "employee_id": identity.employee_id,
                    "view": view,
                    "shell": shell_context_factory(
                        request,
                        identity.employee_id,
                        active_nav="advanced",
                        title="Ontology Migration 검토",
                        description="입력, 후보, 결정적 검사, staging과 Release 경계를 한 run ID로 확인합니다.",
                        hide_pet_agent=True,
                    ),
                },
            )

        @router.get("/agents/builder-v2")
        async def builder_redirect() -> RedirectResponse:
            return RedirectResponse("/helpers/new", status_code=307)

    return router
