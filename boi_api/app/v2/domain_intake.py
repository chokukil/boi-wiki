"""MCP/REST/UI intake facade over the existing source ledger; no internal agent."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute


from ..governed_runtime.semantic_binding_contract import FrozenContract, Ref, RevisionRef
from ..governed_runtime.source_field_read_contract import SourceFieldBatchReadRequest
from ..governed_runtime.domain_asset_store import DomainAssetStore, DomainAssetCreateRequest
from ..governed_runtime.domain_context_service import (DomainContextService, DomainContextPrepareRequest,
    DomainContextPageRequest, DomainContextAcknowledgeRequest, DomainContextRestoreRequest)
from ..governed_runtime.task_knowledge import AssetKind
from ..governed_runtime.domain_work_service import DomainWorkService
from ..governed_runtime.domain_work_contract import (DomainWorkStartRequest, DomainWorkLookupRequest, DomainToolPrepareRequest,
    DomainToolReadRequest, DomainToolLookupRequest, DomainToolDispatchRequest, DomainToolInputRequest, DomainToolEvidenceRequest, DomainToolSubmitRequest, DomainWorkCompleteRequest)
from ..governed_runtime.source_envelope import ArtifactEnvelope, SourceEnvelope
from ..governed_runtime.source_field_projection import SourceFieldProjectionService
from ..governed_runtime.knowledge_space_contract import KnowledgeSpaceTarget


from ..governed_runtime.source_image_read import SourceImageReadRequest, SourceImageReadService
from ..governed_runtime.source_image_transcription import SourceImageTranscriptionRequest


SAFE_INTENT_VALIDATION_RULES=frozenset({
    'QUALITY_MEASURE_DUPLICATE','ROWSET_MEMBERSHIP_REQUIRED',
    'ROWSET_MEMBERSHIP_INVALID','ROWSET_REVISION_REQUIRED',
    'QUALITY_INTENT_REVISION_REQUIRED','AGGREGATE_SCOPE_REVISION_REQUIRED',
    'ROOT_ABSENCE_REVISION_REQUIRED',
    'LATEST_GROUP_BY_FORBIDDEN','MIXED_LATEST_REDUCER_CONTRACT_REQUIRED',
})


def _token_expires_at(value):
    """Parse the token store's ISO UTC spelling on the supported Python runtimes."""
    raw = str(value or '')
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    expires = datetime.fromisoformat(raw)
    return expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires


class SourceCaptureRequest(FrozenContract):
    delivery_recipient: Literal["development_default"] | None = None
    source: SourceEnvelope
    idempotency_key: Annotated[str, Field(min_length=1, max_length=240)]


class DomainIntakeRoute(APIRoute):
    """Keep Pydantic's rejected raw source input out of transport responses."""
    def get_route_handler(self):
        original = super().get_route_handler()
        known={'body','query','path','header','cookie'}
        def properties(value):
            if not isinstance(value,dict):return
            known.update(value.get('properties',{}))
            for child in value.values():
                if isinstance(child,dict):properties(child)
                elif isinstance(child,list):
                    for item in child:properties(item)
        annotation=getattr(getattr(self.body_field,'field_info',None),'annotation',None)
        if hasattr(annotation,'model_json_schema'):properties(annotation.model_json_schema())
        for kind in ('query_params','path_params','header_params','cookie_params'):
            known.update(p.name for p in getattr(self.dependant,kind,()))
        async def redacted(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                # Return schema locations/codes only. Pydantic's message, input,
                # context and unknown dynamic keys can contain original data.
                errors=[]
                for error in exc.errors():
                    safe={'loc':[part if type(part) is int or part in known else '<unexpected_field>'
                        for part in error['loc']], 'type':error['type']}
                    reason=(str((error.get('ctx') or {}).get('error'))
                        if error.get('type')=='value_error' else None)
                    if reason in SAFE_INTENT_VALIDATION_RULES:safe['rule_code']=reason
                    errors.append(safe)
                raise HTTPException(status_code=422, detail={'reason_code':'DOMAIN_INTAKE_REQUEST_INVALID',
                    'validation_stage':'request_schema','validation_errors':errors}) from None
        return redacted


class SourceProjectRequest(FrozenContract):
    reference: ArtifactEnvelope
    manifest_ref: Ref | None = None


class SourceFieldReadRequest(SourceProjectRequest):
    span_ref: Ref
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=4096, ge=1, le=8192, strict=True)


class DomainAssetReadRequest(FrozenContract):
    revision: RevisionRef
    lane: Literal['provisional']
    view: Literal['asset','auto'] = 'asset'
    source_field_refs: tuple[Ref, ...] = Field(default=(), max_length=256)


class DefinitionSourceReadRequest(FrozenContract):
    revision: RevisionRef
    lane: Literal['provisional']
    view: Literal['asset','meaning_index'] = 'asset'
    meaning_pointers: tuple[Annotated[str, Field(max_length=2048)], ...] | None = Field(default=None,min_length=1,max_length=128)


from ..governed_runtime.catalog_meaning_properties import MeaningPropertyQuery
from .catalog_response_view import catalog_response_view
from .store_connections import request_store_connections


class DomainAssetCatalogRequest(FrozenContract):
    text_match_mode: Literal['all_terms','ranked_candidates'] = 'all_terms'
    include_meaning_values: bool = Field(default=True, strict=True)
    target_space: KnowledgeSpaceTarget | None = None
    meaning_query: tuple[MeaningPropertyQuery, ...] = Field(default=(), max_length=8)
    prepare_index: bool = Field(default=False, strict=True)
    query: str = Field(default='',max_length=2000)
    namespace: Ref | None = None
    kind: AssetKind | None = None
    cursor: str = Field(default='', max_length=90)
    limit: int = Field(default=20, ge=1, le=100, strict=True)
    reviewed_definition: RevisionRef | None = None
    content_contract: Ref | None = None
    meaning_contract: Ref | None = None
    purpose: Literal['auto','knowledge','history','capability','all'] = 'auto'


class DomainPackageRequest(FrozenContract):
    operation: Literal['discover','read','freeze_policy','create_candidate','evaluate','trial','adopt','observe','withdraw']
    request: dict = Field(default_factory=dict)


class DomainIntakeService:
    def __init__(self, source_intake, authorizer, *, tool_trust_provider=None, identity_provider=None,
                 space_set_backend_factory=None, current_token_provider=None):
        from threading import Lock
        self.space_set_backend_factory=space_set_backend_factory
        self._knowledge_query_lock = Lock()
        self._knowledge_query_backend = None
        self.source_intake = source_intake
        self.authorizer = authorizer
        self.tool_trust_provider = tool_trust_provider or (lambda:())
        self.identity_provider = identity_provider
        self.current_token_provider = current_token_provider
        import os
        from ..governed_runtime.domain_package_policy_config import load_domain_package_policies
        self.domain_package_policies = load_domain_package_policies(os.environ.get('BOI_DOMAIN_PACKAGE_POLICY_FILE', ''))

    def _packages(self):
        from ..governed_runtime.domain_package_service import DomainPackageService
        if self.source_intake is None:
            raise ValueError('DOMAIN_INTAKE_NOT_CONFIGURED')
        return DomainPackageService(self.source_intake, policies=self.domain_package_policies,
                                    trusted_executors=self.tool_trust_provider())

    def knowledge_work(self, principal, request):
        from ..governed_runtime.knowledge_work_contract import KnowledgeWorkRequest
        from ..governed_runtime.knowledge_work_service import KnowledgeWorkService
        req = KnowledgeWorkRequest.model_validate(request)
        authorization = self._authorization(principal)
        if req.operation == 'publication':
            # Keep every source/authority/CAS check and its own transaction;
            # only reuse idle connections within this synchronous request.
            with request_store_connections():
                publication_request = req.request
                if req.delivery_recipient is not None:
                    from .recipient_write_destination import require_recipient_destination
                    require_recipient_destination(principal, authorization, req.delivery_recipient)
                    if req.request.get('phase') == 'preview':
                        import copy
                        publication_request = copy.deepcopy(req.request)
                        manifest = publication_request.setdefault('payload', {}).setdefault('manifest', {})
                        if manifest.get('delivery_recipient', req.delivery_recipient) != req.delivery_recipient:
                            raise ValueError('DELIVERY_RECIPIENT_DESTINATION_MISMATCH')
                        manifest['delivery_recipient'] = req.delivery_recipient
                service, authorization, _ = self.local_bundles(principal)
                return service.dispatch(authorization=authorization, request=publication_request)
        if req.delivery_recipient is not None:
            raise ValueError('DELIVERY_RECIPIENT_PUBLICATION_REQUIRED')
        service = KnowledgeWorkService(self.source_intake, packages=self._packages(), principal_teams=principal.teams)
        # Candidate discovery reads the actor's published-space revisions too;
        # give it the same space reader _work() uses, or every such hit is denied.
        if callable(self.source_intake.current_source_policy):
            spaces = self._space_reader(principal)
            def current_asset_access(revision, purpose):
                from ..governed_runtime.knowledge_profile_projector import native_identity
                record = self.source_intake.ledger.read(revision.ref)
                return spaces.authorize(actor_id=principal.employee_id, stable_id=native_identity(record),
                    revision=revision, purpose=purpose)
            service.assets.space_access = current_asset_access
        result = service.dispatch(authorization=authorization, operation=req.operation, request=req.request)
        from ..governed_runtime.knowledge_work_view import project_work_response
        return project_work_response(result, full=req.context_view == 'full',
            authorize_revision=lambda ref: service.assets._record_metadata(authorization, ref, metadata_only=True))

    def local_bundles(self, principal):
        from ..governed_runtime.local_bundle_service import LocalBundleService, VerifiedHotlPrincipal
        from ..governed_runtime.knowledge_space_contract import admit_space_intent
        def current_actor():
            if self.identity_provider is None:
                return principal
            fresh = self.identity_provider(principal.employee_id)
            if fresh is None or fresh.employee_id != principal.employee_id:
                raise ValueError('KNOWLEDGE_SPACE_PRINCIPAL_MISMATCH')
            return principal.model_copy(update={
                'teams':sorted(set(principal.teams) & set(fresh.teams)),
                'roles':sorted(set(principal.roles) & set(fresh.roles))})
        authorization = self._authorization(current_actor())
        def hotl_authorization():
            # This principal originated at the authenticated HTTP boundary.
            # No caller approval boolean, actor, token or scope is accepted.
            from ..governed_runtime.semantic_binding_contract import semantic_digest
            from .atomic_store_contract import AtomicWrite
            actor = current_actor()
            if (actor.auth_source != 'pat' or not actor.token_id
                    or not callable(self.current_token_provider)):
                raise ValueError('LOCAL_BUNDLE_HOTL_AUTHENTICATED_PAT_REQUIRED')
            token = self.current_token_provider(actor.token_id)
            if (not token or token.get('employee_id') != actor.employee_id or token.get('revoked_at')
                    or not {'boi.draft', 'boi.execute.low'} <= set(actor.token_scopes)
                    or not {'boi.draft', 'boi.execute.low'} <= set(token.get('scopes') or ())
                    or not {'boi.admin', 'boi.editor'} & set(actor.roles)
                    or not {'boi.admin', 'boi.workflow_runner', 'boi.action_invoker'} & set(actor.roles)):
                raise ValueError('LOCAL_BUNDLE_HOTL_NOT_AUTHORIZED')
            try:
                expires = _token_expires_at(token.get('expires_at'))
                if expires <= self.source_intake.clock():
                    raise ValueError('expired')
            except (TypeError, ValueError):
                raise ValueError('LOCAL_BUNDLE_HOTL_NOT_AUTHORIZED') from None
            # Fence the exact token record from the same authority store used
            # by this product's PAT transport, including mid-request revocation.
            if self.source_intake.store.get('tokens', actor.token_id) != token:
                raise ValueError('LOCAL_BUNDLE_HOTL_AUTHORITY_STORE_REQUIRED')
            current_auth = self._authorization(actor)
            if self.source_intake._policy(current_auth) != self.source_intake._policy(authorization):
                raise ValueError('LOCAL_BUNDLE_POLICY_CHANGED')
            binding = {'principal':actor.employee_id, 'roles':sorted(set(actor.roles)),
                'teams':sorted(set(actor.teams)), 'token_id':actor.token_id,
                'scopes':sorted(set(actor.token_scopes) & set(token.get('scopes') or ())),
                'policy':self.source_intake._policy(current_auth)}
            return VerifiedHotlPrincipal(actor.employee_id, semantic_digest(binding),
                (AtomicWrite('tokens', actor.token_id, token, token),))
        def current_space_access(revision,purpose):
            from ..governed_runtime.semantic_binding_contract import semantic_digest
            record=self.source_intake.ledger.read(revision.ref)
            stable_id='domain-asset-head:'+semantic_digest([record.payload.get('employee_id'),
                record.payload.get('namespace'),record.payload.get('logical_id')])
            return self._space_reader(principal).authorize(actor_id=principal.employee_id,
                stable_id=stable_id,revision=revision,purpose=purpose)
        def publication(importer):
            from ..governed_runtime.local_publication_bridge import LocalPublicationBridge
            from ..governed_runtime.knowledge_projection_store import KnowledgeProjectionStore
            # Service-owned durable derived storage; no caller path or uploader
            # mount is part of the public contract. The native ledger is the SOT.
            with self._knowledge_query_lock:
                projection = getattr(self, '_local_publication_projection', None)
                if projection is None:
                    projection = KnowledgeProjectionStore(self.source_intake.objects.root.parent /
                        'knowledge-publication' / 'projection.sqlite3')
                    self._local_publication_projection = projection
            return LocalPublicationBridge(importer, self._space_reader(principal), projection)
        def impact(bundle):
            from ..governed_runtime.local_bundle_impact import LocalBundleImpact
            _,sets,index=self._reference_services(principal)
            return LocalBundleImpact(bundle,sets,index)
        from .store import PostgresAgentV2Store
        indexed_impact = bool(self.space_set_backend_factory or isinstance(self.source_intake.store,PostgresAgentV2Store))
        def validate_bundle_reading(revision, sources):
            current_auth, work = self._work(current_actor())
            return work.contexts.validate_reading(authorization=current_auth, revision=revision, sources=sources)
        def shared_bundle_reading(prepared):
            current_auth, work = self._work(current_actor())
            selection = prepared.payload.get('package_selection')
            return (frozenset(work.contexts.shared_assets(current_auth, selection)),
                work.contexts.package_fences(current_auth, selection))
        def delivery_destination(selector):
            from .recipient_write_destination import require_recipient_destination
            actor = current_actor()
            return require_recipient_destination(actor, self._authorization(actor), selector)
        service = LocalBundleService(self.source_intake,
            delivery_authorizer=delivery_destination,
            current_authorizer=lambda: self._authorization(current_actor()),
            space_authorizer=lambda target: admit_space_intent(current_actor(), target),
            space_access=current_space_access, publication_factory=publication,
            impact_factory=impact if indexed_impact else None, hotl_authorizer=hotl_authorization,
            validate_reading=validate_bundle_reading, shared_reading_binding=shared_bundle_reading)
        root = self.source_intake.objects.root.parent / 'local-bundle-uploads'
        return service, authorization, root

    def knowledge_sets(self,principal,request):
        from ..governed_runtime.knowledge_space_sets import (
            KnowledgeSpaceSets,PostgresSpaceSetBackend,KnowledgeSetCreate,KnowledgeSetRead)
        from ..governed_runtime.knowledge_reference_impact import KnowledgeIncomingRead
        if isinstance(request,KnowledgeIncomingRead):
            return self.incoming_references(principal,request)
        spaces=self._space_reader(principal)
        backend=(self.space_set_backend_factory(spaces.store) if self.space_set_backend_factory
                 else PostgresSpaceSetBackend(spaces.store))
        sets=KnowledgeSpaceSets(spaces,backend)
        if isinstance(request,KnowledgeSetCreate):
            return sets.issue(actor_id=principal.employee_id,target=request.target,purpose=request.purpose)
        if isinstance(request,KnowledgeSetRead):
            return sets.summary(actor_id=principal.employee_id,set_ref=request.set_ref)
        raise ValueError('KNOWLEDGE_SET_REQUEST_REQUIRED')

    def _reference_services(self, principal):
        from ..governed_runtime.knowledge_reference_impact import PostgresReferenceIndex
        from ..governed_runtime.knowledge_space_sets import KnowledgeSpaceSets,PostgresSpaceSetBackend
        spaces=self._space_reader(principal)
        prepared,changes=self._prepared_backend(spaces)[2:4]
        with self._knowledge_query_lock:
            index=getattr(self,'_native_reference_index',None)
            if index is None or index.changes is not changes:
                backend=PostgresSpaceSetBackend(prepared.store,key_prefix=prepared.prefix,authority_store=prepared.authority_store)
                index=PostgresReferenceIndex(backend,changes)
                self._native_reference_index=index
        return spaces,KnowledgeSpaceSets(spaces,index.backend),index

    def repair_references(self, principal, request):
        from ..governed_runtime.native_reference_repair import NativeReferenceRepair
        from ..governed_runtime.native_contract_repair import NativeContractRepair, NativeContractRepairRequest
        spaces,_,index=self._reference_services(principal)
        repair = NativeContractRepair if isinstance(request, NativeContractRepairRequest) else NativeReferenceRepair
        return repair(spaces,index).repair(actor_id=principal.employee_id,
            request=request.model_dump(mode='json'))

    def incoming_references(self, principal, request):
        from ..governed_runtime.knowledge_reference_impact import KnowledgeReferenceImpact
        _,sets,index=self._reference_services(principal)
        # The agent-facing API cannot use a human-read-only population to bypass
        # model-input permission. The browser's internal preview can read as a human.
        if sets.resolve(actor_id=principal.employee_id,set_ref=request.set_ref)['purpose']!='model_input':
            raise ValueError('KNOWLEDGE_REFERENCE_MODEL_INPUT_NOT_AUTHORIZED')
        return KnowledgeReferenceImpact(sets,index).read(actor_id=principal.employee_id,request=request.model_dump(mode='json'))

    def profile_candidates(self, principal, request):
        from ..governed_runtime.knowledge_profile_discovery import KnowledgeProfileDiscovery
        _,sets,index=self._reference_services(principal)
        return KnowledgeProfileDiscovery(sets,index).read(actor_id=principal.employee_id,
            request=request.model_dump(mode='json'))

    def repair_profiles(self, principal, request):
        from ..governed_runtime.native_profile_repair import NativeProfileRepair
        spaces,_,index=self._reference_services(principal)
        return NativeProfileRepair(spaces,index).repair(actor_id=principal.employee_id,
            request=request.model_dump(mode='json'))

    def knowledge_queries(self, principal, request):
        from ..governed_runtime.knowledge_prepared_queries import KnowledgePreparedQueries
        from ..governed_runtime.knowledge_prepared_results import KnowledgePreparedResults
        from .knowledge_query_transport import (KnowledgeQueryExecute, KnowledgeQueryRecover,
            KnowledgeQuerySummary, KnowledgeQueryPage, KnowledgeQueryWitnesses)
        from ..governed_runtime.knowledge_concept_reuse_contract import ConceptReuseContext
        from ..governed_runtime.native_concept_reuse import prepare_concept_query, validate_concept_query
        def reuse_work():
            authorization, work = self._work(principal)
            if not callable(getattr(work, 'current_knowledge_authorization', None)):
                raise ValueError('KNOWLEDGE_REUSE_CURRENT_READER_REQUIRED')
            if work.current_knowledge_authorization() != authorization:
                raise ValueError('KNOWLEDGE_REUSE_CURRENT_AUTHORIZATION_CHANGED')
            return authorization, work
        if isinstance(request, ConceptReuseContext):
            authorization, work = reuse_work()
            query = prepare_concept_query(work, authorization, request)
            return {'query':query.model_dump(mode='json'), 'semantic_truth_proven':False,
                'fact_qualification_granted':False, 'scope':'exact reviewed source assertions only'}
        def validate_reuse(query):
            authorization, work = reuse_work()
            validate_concept_query(work, authorization, query)
        spaces = self._space_reader(principal)
        from ..governed_runtime.knowledge_relation_traversal import KnowledgeRelationTraversal, KnowledgeTraversalRequest
        if isinstance(request, KnowledgeTraversalRequest):
            from ..public_links import configured_public_links
            with request_store_connections():
                return KnowledgeRelationTraversal(spaces,
                    current_authorization=lambda:self._authorization(principal),
                    public_links=configured_public_links()).read(
                        actor_id=principal.employee_id, request=request.model_dump(mode='json'))
        cached = self._prepared_backend(spaces)
        _, _, prepared, changes, saved, repository = cached
        service = KnowledgePreparedResults(KnowledgePreparedQueries(spaces, prepared, changes=changes),
                                           repository, saved_sets=saved, definition_reuse_validator=validate_reuse)
        from ..governed_runtime.knowledge_report_intersection import KnowledgeReportIntersection, KnowledgeReportIntersectionRequest
        if isinstance(request, KnowledgeReportIntersectionRequest):
            with request_store_connections():
                return KnowledgeReportIntersection(service).read(
                    actor_id=principal.employee_id, request=request.model_dump(mode='json'))
        from ..governed_runtime.knowledge_result_relations import KnowledgeResultRelations, KnowledgeResultRelationsRequest
        if isinstance(request, KnowledgeResultRelationsRequest):
            from ..public_links import configured_public_links
            with request_store_connections():
                return KnowledgeResultRelations(service, KnowledgeRelationTraversal(spaces,
                    current_authorization=lambda:self._authorization(principal),
                    public_links=configured_public_links())).read(
                        actor_id=principal.employee_id, request=request.model_dump(mode='json'))
        if isinstance(request, KnowledgeQueryRecover):
            return service.recover(actor_id=principal.employee_id, **request.model_dump(mode='json'))
        if isinstance(request, KnowledgeQueryExecute):
            return service.execute(actor_id=principal.employee_id, **request.model_dump(mode='json'))
        if isinstance(request, KnowledgeQueryPage):
            with request_store_connections():
                return service.page(actor_id=principal.employee_id, **request.model_dump(mode='json'))
        if isinstance(request, KnowledgeQueryWitnesses):
            return service.witnesses(actor_id=principal.employee_id, **request.model_dump(mode='json'))
        if isinstance(request, KnowledgeQuerySummary):
            return service.summary(actor_id=principal.employee_id, **request.model_dump(mode='json'))
        raise ValueError('KNOWLEDGE_QUERY_REQUEST_REQUIRED')

    def _prepared_backend(self, spaces):
        from ..governed_runtime.knowledge_prepared_postgres import PostgresKnowledgePreparedStore
        from ..governed_runtime.knowledge_query_changes import KnowledgeQueryChanges
        from ..governed_runtime.knowledge_saved_sets import KnowledgeSavedSets
        from ..governed_runtime.knowledge_space_sets import PostgresSpaceSetBackend
        from ..governed_runtime.protected_execution_repository import ProtectedExecutionRepository
        # Cache server storage/schema handles, never actors, rights or results.
        # Each request binds its own token and freshly resolved current identity.
        with self._knowledge_query_lock:
            cached = self._knowledge_query_backend
            if (cached is None or cached[0] is not self.source_intake
                    or cached[1] is not self.space_set_backend_factory):
                backend = (self.space_set_backend_factory(spaces.store) if self.space_set_backend_factory
                           else PostgresSpaceSetBackend(spaces.store))
                prepared = PostgresKnowledgePreparedStore(backend.store, key_prefix=backend.prefix,
                                                         authority_store=backend.authority_store)
                changes, saved = KnowledgeQueryChanges(prepared), KnowledgeSavedSets(prepared)
                repository = ProtectedExecutionRepository(
                    self.source_intake.objects.root.parent / 'knowledge-query-executions', self.source_intake.ledger)
                cached = (self.source_intake, self.space_set_backend_factory, prepared, changes, saved, repository)
                self._knowledge_query_backend = cached
        return cached

    def published_qualifications(self, principal, request):
        from ..governed_runtime.published_knowledge_qualification import PublishedKnowledgeQualification
        from ..governed_runtime.published_knowledge_contract import PublishedQualificationRefresh
        from .store import PostgresAgentV2Store
        spaces = self._space_reader(principal)
        prepared = (self._prepared_backend(spaces)[2] if isinstance(request, PublishedQualificationRefresh)
            and (self.space_set_backend_factory or isinstance(spaces.store,PostgresAgentV2Store)) else None)
        service = PublishedKnowledgeQualification(spaces,
            current_authorization=lambda: self._authorization(spaces._actor(principal.employee_id)),prepared_store=prepared)
        method = service.refresh if isinstance(request, PublishedQualificationRefresh) else service.current
        return method(actor_id=principal.employee_id,request=request.model_dump(mode='json'))

    def published_document(self, principal, request, *, model_input=True, allow_legacy=False):
        from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader, PublishedSourceRead
        from ..public_links import configured_public_links
        if allow_legacy:
            from ..governed_runtime.knowledge_space_store import HEADS
            from ..governed_runtime.semantic_binding_contract import semantic_digest
            index=self.source_intake.store.get('domain_knowledge_assets',request.revision.ref)
            if index is None or not self.source_intake.store.get(HEADS,'domain-asset-head:'+semantic_digest(
                    [index['employee_id'],index['namespace'],index['logical_id']])):return None
        spaces=self._space_reader(principal)
        reader=PublishedKnowledgeReader(spaces,
            current_authorization=lambda:self._authorization(spaces._actor(principal.employee_id)),
            public_links=configured_public_links())
        if allow_legacy and not reader.is_published(request.revision):return None
        try:
            method=reader.source if isinstance(request,PublishedSourceRead) else reader.read
            # Keep every fresh source/use/authority read and transaction boundary;
            # reuse only idle connections during this synchronous document read.
            with request_store_connections():
                return method(actor_id=principal.employee_id,request=request.model_dump(mode='json'),model_input=model_input)
        except ValueError as error:
            if allow_legacy and str(error)=='KNOWLEDGE_DOCUMENT_CONTENT_UNSUPPORTED':return None
            raise

    def _space_reader(self, principal):
        from ..governed_runtime.knowledge_space_store import KnowledgeSpaceStore
        if self.source_intake is None:
            raise ValueError('DOMAIN_INTAKE_NOT_CONFIGURED')
        return KnowledgeSpaceStore(self.source_intake,current_principal=lambda:self._current_identity(principal),
            current_source_policy=self.source_intake.current_source_policy)

    def _current_identity(self, principal):
        if self.identity_provider is None:return principal
        fresh=self.identity_provider(principal.employee_id)
        if fresh is None or fresh.employee_id!=principal.employee_id:
            raise ValueError('KNOWLEDGE_SPACE_PRINCIPAL_MISMATCH')
        return principal.model_copy(update={
            'teams':sorted(set(principal.teams)&set(fresh.teams)),
            'roles':sorted(set(principal.roles)&set(fresh.roles))})

    def knowledge_supervision(self, principal, request):
        from .knowledge_supervision import KnowledgeSupervisionService, KnowledgeSupervisionRequest
        from ..governed_runtime.knowledge_work_service import KnowledgeWorkService
        req = KnowledgeSupervisionRequest.model_validate(request)
        if req.operation in ('document_feedback','feedback_inbox','feedback_read'):
            from ..governed_runtime.knowledge_document_feedback import PublishedKnowledgeFeedback
            feedback=PublishedKnowledgeFeedback(self._space_reader(principal))
            method={'document_feedback':feedback.submit,'feedback_inbox':feedback.inbox,'feedback_read':feedback.read}[req.operation]
            return method(actor_id=principal.employee_id,request=req.request)
        work = KnowledgeWorkService(self.source_intake, packages=self._packages(), principal_teams=principal.teams)
        return KnowledgeSupervisionService(self.source_intake, work).dispatch(
            authorization=self._authorization(principal), operation=req.operation, request=req.request)

    def domain_packages(self, principal, request):
        req = DomainPackageRequest.model_validate(request)
        allowed = {
            'discover': {'team_id'}, 'read': {'package_id','revision','team_id','resource_path'},
            'freeze_policy': {'team_id','idempotency_key'},
            'create_candidate': {'team_id','policy_revision','package_revision','idempotency_key'},
            'evaluate': {'candidate_revision','execution_refs','idempotency_key'},
            'trial': {'candidate_revision','execution_refs','idempotency_key'},
            'adopt': {'candidate_revision','idempotency_key'},
            'observe': {'candidate_revision','execution_refs','idempotency_key'},
            'withdraw': {'team_id','package_revision','reason','idempotency_key'},
        }
        if not set(req.request) <= allowed[req.operation]:
            raise ValueError('DOMAIN_PACKAGE_REQUEST_FIELDS_INVALID')
        try:
            return getattr(self._packages(), req.operation)(authorization=self._authorization(principal),
                principal_teams=principal.teams, **req.request)
        except TypeError:
            raise ValueError('DOMAIN_PACKAGE_REQUEST_INVALID') from None

    def _work(self, principal):
        # The context keeps its original authority. Later fences may reject a
        # changed actor, but must not silently update teams used by its readers.
        from copy import deepcopy
        principal = deepcopy(principal)
        authorization = self._authorization(principal)
        work = DomainWorkService(self.source_intake,principal_teams=principal.teams,
            trusted_executors=self.tool_trust_provider(), packages=self._packages())
        # Historical native-only installations have no published-space policy.
        # Keep that path; Wiki parameters explicitly require a configured reader.
        if not callable(self.source_intake.current_source_policy):return authorization,work
        work.knowledge_spaces=self._space_reader(principal)
        def identity_scope(actor):
            return (actor.employee_id, tuple(sorted(set(actor.roles))),
                tuple(sorted(set(actor.teams))), actor.token_id,
                tuple(sorted(set(actor.token_scopes))))
        original_identity = identity_scope(principal)
        def current_authorization():
            current = self._current_identity(principal)
            if principal.token_id:
                # Employee-directory identities do not carry PAT scopes. Read
                # the same token record that authenticated this request instead.
                if not callable(self.current_token_provider):
                    raise ValueError('DOMAIN_CONTEXT_CURRENT_TOKEN_PROVIDER_REQUIRED')
                token = self.current_token_provider(principal.token_id)
                if (not token or token.get('employee_id') != principal.employee_id
                        or token.get('revoked_at')):
                    raise ValueError('DOMAIN_CONTEXT_TOKEN_ACCESS_DENIED')
                try:
                    expires_at = _token_expires_at(token.get('expires_at'))
                    if expires_at <= self.source_intake.clock():
                        raise ValueError('expired')
                except (TypeError, ValueError):
                    raise ValueError('DOMAIN_CONTEXT_TOKEN_ACCESS_DENIED') from None
                current = current.model_copy(update={'token_scopes':list(token.get('scopes') or ())})
            if identity_scope(current) != original_identity:
                raise ValueError('DOMAIN_CONTEXT_IDENTITY_CHANGED')
            return self._authorization(current)
        work.current_knowledge_authorization=current_authorization
        def current_asset_access(revision,purpose):
            from ..governed_runtime.knowledge_profile_projector import native_identity
            record=self.source_intake.ledger.read(revision.ref)
            return work.knowledge_spaces.authorize(actor_id=principal.employee_id,stable_id=native_identity(record),
                revision=revision,purpose=purpose)
        work.assets.space_access=current_asset_access
        work.contexts.assets.space_access=current_asset_access
        return authorization, work

    def _authorization(self, principal):
        if self.source_intake is None or self.authorizer is None:
            raise ValueError('DOMAIN_INTAKE_NOT_CONFIGURED')
        authorization = self.authorizer(principal)
        if authorization.principal != principal.employee_id:
            raise ValueError('DOMAIN_INTAKE_PRINCIPAL_MISMATCH')
        return authorization

    def capture(self, principal, request: SourceCaptureRequest):
        authorization = self._authorization(principal)
        destination = None
        if request.delivery_recipient is not None:
            from .recipient_write_destination import require_recipient_destination
            destination = require_recipient_destination(principal, authorization, request.delivery_recipient)
        result = self.source_intake.capture(authorization=authorization,
            envelope=request.source, idempotency_key=request.idempotency_key)
        return {**result, 'delivery_destination':destination} if destination else result

    def project(self, principal, request: SourceProjectRequest):
        authorization = self._authorization(principal)
        projector=SourceFieldProjectionService(self.source_intake)
        reference=request.reference.model_dump(mode='json')
        if request.manifest_ref is not None:
            return projector.restore_manifest(authorization=authorization,reference=reference,
                manifest_ref=request.manifest_ref)['manifest']
        return projector.project(authorization=authorization,reference=reference)

    def read_field(self, principal, request: SourceFieldReadRequest | SourceFieldBatchReadRequest):
        authorization = self._authorization(principal)
        if isinstance(request, SourceFieldBatchReadRequest):
            return SourceFieldProjectionService(self.source_intake).read_batch(
                authorization=authorization, request=request)
        return SourceFieldProjectionService(self.source_intake).read_field(authorization=authorization,
            reference=request.reference.model_dump(mode='json'), span_ref=request.span_ref,
            offset=request.offset, limit=request.limit)

    def transcribe_image(self, principal, request: SourceImageTranscriptionRequest):
        return SourceImageReadService(self.source_intake).transcribe(
            authorization=self._authorization(principal), request=request)

    def read_image(self, principal, request: SourceImageReadRequest):
        return SourceImageReadService(self.source_intake).read(
            authorization=self._authorization(principal), request=request)

    def catalog_assets(self, principal, request: DomainAssetCatalogRequest):
        # Enter inside the synchronous service call so the connection owner is
        # its worker thread. Reuse connections, never rows or authorization;
        # each store operation retains its existing transaction boundary.
        with request_store_connections():
            return catalog_response_view(self._catalog_assets(principal, request, content_purpose='model_input'),
                include_meaning_values=request.include_meaning_values)

    def catalog_for_humans(self, principal, request: DomainAssetCatalogRequest):
        with request_store_connections():
            return catalog_response_view(self._catalog_assets(principal, request, content_purpose='read'),
                include_meaning_values=request.include_meaning_values)

    def _catalog_assets(self, principal, request, *, content_purpose):
        if request.target_space is not None:
            if request.content_contract is not None or request.meaning_contract is not None:
                if (request.query or request.meaning_query or request.prepare_index
                        or request.reviewed_definition is not None or request.purpose not in ('auto','knowledge','all')):
                    raise ValueError('KNOWLEDGE_CONTRACT_FILTER_COMBINATION_UNSUPPORTED')
                from ..governed_runtime.knowledge_contract_discovery import KnowledgeContractCatalog
                _, sets, index = self._reference_services(principal)
                return KnowledgeContractCatalog(sets,index).search(actor_id=principal.employee_id,
                    target=request.target_space.model_dump(mode='json'), namespace=request.namespace,
                    kind=request.kind, content_contract=request.content_contract, meaning_contract=request.meaning_contract,
                    limit=request.limit, cursor=request.cursor, purpose=content_purpose)
            if (request.prepare_index or request.meaning_query or request.reviewed_definition is not None
                    or request.content_contract is not None or request.purpose not in ('auto','knowledge','all')):
                raise ValueError('KNOWLEDGE_SPACE_INDEX_OPERATION_UNSUPPORTED')
            if request.query:
                from ..governed_runtime.knowledge_text_search import KnowledgeTextSearch
                _, sets, index = self._reference_services(principal)
                return KnowledgeTextSearch(sets, index).search(actor_id=principal.employee_id,
                    target=request.target_space.model_dump(mode='json'), query=request.query,
                    namespace=request.namespace, kind=request.kind, limit=request.limit,
                    cursor=request.cursor, purpose=content_purpose, text_match_mode=request.text_match_mode)
            after_key=''
            expected_epoch=None
            if request.cursor:
                import re
                match=re.fullmatch(r'([0-9a-f]{64}):([0-9]{1,20})',request.cursor)
                if not match:raise ValueError('KNOWLEDGE_SPACE_CURSOR_INVALID')
                after_key='knowledge-space-entry:sha256:'+match[1]
                expected_epoch=int(match[2])
            result=self._space_reader(principal).list(actor_id=principal.employee_id,target=request.target_space,
                after_key=after_key,expected_epoch=expected_epoch,limit=request.limit)
            result['items']=[x for x in result['items'] if (request.namespace is None or x['namespace']==request.namespace)
                             and (request.kind is None or x['kind']==request.kind)]
            next_key=result.pop('next_after_key')
            result['next_cursor']=(next_key.removeprefix('knowledge-space-entry:sha256:')+':'+str(result['policy_epoch'])) if next_key else None
            result['scope']='current_authenticated_knowledge_space'
            return result
        if request.meaning_contract is not None:
            raise ValueError('KNOWLEDGE_MEANING_CONTRACT_TARGET_SPACE_REQUIRED')
        authorization, work = self._work(principal)
        if request.prepare_index:
            if request.query or request.meaning_query or request.cursor or request.reviewed_definition is not None:
                raise ValueError('DOMAIN_SEARCH_PREPARATION_SEPARATE_FROM_QUERY')
            return work.assets.prepare_search(authorization=authorization, namespace=request.namespace)
        return work.assets.catalog(authorization=authorization,
            namespace=request.namespace, kind=request.kind, cursor=request.cursor, limit=request.limit,
            purpose=request.purpose,
            **({'meaning_query': request.meaning_query} if request.meaning_query else {}),
            reviewed_definition=request.reviewed_definition,
            **({'query':request.query} if request.query else {}),
            **({'content_contract':request.content_contract} if request.content_contract is not None else {}))

    def read_asset(self, principal, request: DomainAssetReadRequest):
        from ..governed_runtime.knowledge_space_store import HEADS
        from ..governed_runtime.semantic_binding_contract import semantic_digest
        if self.source_intake is None:
            raise ValueError('DOMAIN_INTAKE_NOT_CONFIGURED')
        record=self.source_intake.ledger.read(request.revision.ref)
        stable_id='domain-asset-head:'+semantic_digest([record.payload.get('employee_id'),
            record.payload.get('namespace'),record.payload.get('logical_id')])
        if self.source_intake.store.get(HEADS,stable_id) is not None:
            if request.source_field_refs:
                raise ValueError('SOURCE_FIELD_SELECTION_REQUIRES_SEPARATE_SOURCE_AUTHORIZATION')
            access,record,asset=self._space_reader(principal).read(actor_id=principal.employee_id,
                stable_id=stable_id,revision=request.revision,purpose='model_input')
            return {'revision':asset.revision.model_dump(mode='json'),'asset':asset.model_dump(mode='json'),
                'logical_id':record.payload['logical_id'],'namespace':record.payload['namespace'],
                'title':record.payload['title'],'description':record.payload['description'],
                'sources':record.payload['sources'],'previous_revision':record.payload['previous_revision'],
                'definition_reading_ref':record.payload['definition_reading_ref'],
                'knowledge_reading_status':record.payload['knowledge_reading_status'],
                'space_policy_revision':access.policy_revision.model_dump(mode='json'),
                'stable_id':stable_id,'actor_id':access.actor_id,'source_access_granted':False,
                'publication_state':'published','use_qualification_granted':False,
                'document_read':{'revision':asset.revision.model_dump(mode='json'),'view':'document'},
                'status':'PROVISIONAL','canonical_projection_eligible':False}
        authorization = self._authorization(principal)
        result = DomainAssetStore(self.source_intake).read(authorization=authorization,
            revision=request.revision, lane=request.lane)
        from .asset_user_views import available_user_views
        views=available_user_views(result)
        if views:result['available_user_views']=views
        if getattr(request,'view','asset')=='auto' and not request.source_field_refs:
            from .asset_user_views import native_review_record_view
            projection=native_review_record_view(self,principal,result)
            if projection is not None:return projection
        if result['asset']['kind'] == 'source':
            import os
            from urllib.parse import urlsplit
            from .native_definition_sources import source_field_links
            origin = os.environ.get('BOI_EXTERNAL_URL', '').rstrip('/')
            parsed = urlsplit(origin)
            base = origin if parsed.scheme in ('http', 'https') and parsed.netloc else ''
            url = base + '/native-definitions/' + result['revision']['revision_digest'].removeprefix('sha256:')
            from ..governed_runtime.native_observation import _json
            content = _json(result['asset']['content_json'])
            if isinstance(content, dict) and content.get('contract_version') in (
                    'boi/workbook-source-records@1', 'boi/workbook-source-index@1'):
                return self._read_workbook_source(result, authorization, request, content, url)
            projected = []
            for source in result['sources']:
                manifest = SourceFieldProjectionService(self.source_intake).project(
                    authorization=authorization, reference=source)
                projected.append({'source': source, 'fields': manifest['fields']})
            result['source_field_links'] = source_field_links(projected, url)
        if getattr(request, 'source_field_refs', ()):
            raise ValueError('SOURCE_FIELD_SELECTION_REQUIRES_WORKBOOK_ASSET')
        return result

    def read_knowledge_graph(self, principal, request: DomainAssetReadRequest):
        import json
        from ..governed_runtime.knowledge_space_store import HEADS
        from ..governed_runtime.semantic_binding_contract import semantic_digest
        from ..governed_runtime.knowledge_graph_projection import project_knowledge_graph
        # Published content has its own current sharing policy. Use the same
        # model-input body reader as asset/document reads, not the legacy owner
        # adapter without a space-authority callback.
        if self.source_intake is None:
            raise ValueError('DOMAIN_INTAKE_NOT_CONFIGURED')
        native = self.source_intake.ledger.read(request.revision.ref)
        stable_id = 'domain-asset-head:' + semantic_digest([
            native.payload.get('employee_id'), native.payload.get('namespace'), native.payload.get('logical_id')])
        if self.source_intake.store.get(HEADS, stable_id) is not None:
            spaces = self._space_reader(principal)
            access, record, asset = spaces.read(actor_id=principal.employee_id,
                stable_id=stable_id, revision=request.revision, purpose='model_input')
            if asset.kind != 'definition':
                raise ValueError('KNOWLEDGE_GRAPH_DEFINITION_REQUIRED')
            graph = project_knowledge_graph(logical_id=record.payload['logical_id'],
                namespace=record.payload['namespace'], revision=request.revision.model_dump(mode='json'),
                content=json.loads(asset.content_json))
            current, _ = spaces.authorize(actor_id=principal.employee_id,
                stable_id=stable_id, revision=request.revision, purpose='model_input')
            if current != access:
                raise ValueError('KNOWLEDGE_GRAPH_AUTHORITY_CHANGED')
            return {**graph, 'dependencies':record.payload['dependencies'],
                'conflicts_with':record.payload['conflicts_with'], 'supersedes':record.payload['supersedes'],
                'dependency_validity':'requires_current_authorized_resolution',
                'stable_id':stable_id, 'actor_id':access.actor_id,
                'policy_revision':access.policy_revision.model_dump(mode='json'),
                'publication_state':'published', 'source_access_granted':False,
                'use_qualification_granted':False}
        return DomainAssetStore(self.source_intake).graph(authorization=self._authorization(principal), revision=request.revision)

    def _read_workbook_source(self, result, authorization, request, content, url):
        from .native_definition_sources import source_field_links
        if len(result['sources']) != 1:
            raise ValueError('WORKBOOK_SOURCE_IDENTITY_AMBIGUOUS')
        source = result['sources'][0]
        declared = [item['ref'] for item in result['asset'].get('evidence', [])]
        extra = list(getattr(request, 'source_field_refs', ()))
        projector = SourceFieldProjectionService(self.source_intake)
        selected = projector.select_manifest_fields(authorization=authorization,
            reference=source, manifest_ref=content['manifest_ref'], span_refs=[*declared, *extra])
        result['source_field_links'] = source_field_links([{'source': source, 'fields': selected['fields']}], url)
        for link in result['source_field_links']:
            if link['span_ref'] not in declared:
                page_offset=selected['field_offsets'][link['span_ref']]//100*100
                base,anchor=link['url'].split('#',1)
                link['url']=base+'?source_offset='+str(page_offset)+'#'+anchor
        result['source_read_scope'] = {'source': source, 'manifest_ref': selected['manifest_ref'],
            'total_field_count': selected['field_count'], 'linked_field_count': len(selected['fields']),
            'selection_basis': 'asset_evidence_and_explicit_context_references',
            'complete_source_read': False, 'url': url,
            'range_read_tool': 'boi_source_field'}
        # Extra context is requested explicitly by the harness from its grounded
        # header/annotation bindings. Do not echo source cells already in content.
        additional = [ref for ref in dict.fromkeys(extra) if ref not in declared]
        if additional:
            result['source_field_context'] = [projector.read_field(authorization=authorization,
                reference=source, span_ref=ref, limit=8192) for ref in additional]
        return result

    def read_process_coverage(self,principal,request: DomainAssetReadRequest):
        from .process_coverage import read_process_coverage
        return read_process_coverage(self,principal,request)

    def read_process_result(self, principal, request: DomainAssetReadRequest):
        from .process_result import read_process_result
        return read_process_result(self,principal,request)

    def read_process_review_binding(self,principal,request):
        from .process_review_binding import read_process_review_binding
        return read_process_review_binding(self,principal,request)

    def propose_asset(self, principal, request: DomainAssetCreateRequest):
        authorization, work = self._work(principal)
        context = work.contexts
        def shared_binding(prepared):
            selection = prepared.payload.get('package_selection')
            return (frozenset(context.shared_assets(authorization, selection)),
                context.package_fences(authorization, selection))
        return work.assets.create(authorization=authorization, request=request,
            validate_reading=lambda revision,sources:context.validate_reading(
                authorization=authorization, revision=revision, sources=sources),
            shared_reading_binding=shared_binding)

    def prepare_context(self, principal, request: DomainContextPrepareRequest):
        authorization, work = self._work(principal)
        return work.contexts.prepare(
            authorization=authorization, request=request)

    def read_context_page(self, principal, request: DomainContextPageRequest):
        authorization, work = self._work(principal)
        return work.contexts.read_page(
            authorization=authorization, request=request)

    def acknowledge_context(self, principal, request: DomainContextAcknowledgeRequest):
        authorization, work = self._work(principal)
        return work.contexts.acknowledge(
            authorization=authorization, request=request)

    def restore_context(self, principal, request):
        authorization, work = self._work(principal)
        return work.contexts.restore(authorization=authorization,request=request)

    def start_work(self, principal, request: DomainWorkStartRequest):
        authorization, work = self._work(principal)
        return work.start(authorization=authorization,request=request)

    def lookup_work(self, principal, request: DomainWorkLookupRequest):
        authorization,work=self._work(principal)
        return work.lookup_work(authorization=authorization,request=request)

    def prepare_tool(self, principal, request: DomainToolPrepareRequest):
        authorization, work = self._work(principal)
        return work.prepare(authorization=authorization,request=request)

    def read_tool(self, principal, request: DomainToolReadRequest):
        authorization, work = self._work(principal)
        return work.read(authorization=authorization,request=request)

    def lookup_tool(self, principal, request: DomainToolLookupRequest):
        authorization,work=self._work(principal)
        return work.lookup(authorization=authorization,request=request)

    def dispatch_tool(self, principal, request: DomainToolDispatchRequest):
        authorization,work=self._work(principal)
        return work.dispatch(authorization=authorization,request=request)

    def read_tool_input(self, principal, request: DomainToolInputRequest):
        authorization, work = self._work(principal)
        return work.read_input(authorization=authorization,request=request)

    def submit_tool(self, principal, request: DomainToolSubmitRequest):
        authorization, work = self._work(principal)
        return work.submit(authorization=authorization,request=request)

    def complete_work(self, principal, request: DomainWorkCompleteRequest):
        authorization, work = self._work(principal)
        return work.complete(authorization=authorization,request=request)

    def read_tool_evidence(self, principal, request: DomainToolEvidenceRequest):
        authorization, work = self._work(principal)
        return work.read_evidence(authorization=authorization,request=request)
