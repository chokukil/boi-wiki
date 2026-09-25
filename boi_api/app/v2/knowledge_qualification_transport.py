"""Published use metadata and exact current-editor refresh through the official API."""
from fastapi import Depends, Request

from ..governed_runtime.published_knowledge_contract import PublishedQualificationRead, PublishedQualificationRefresh
from .auth import require_scope
from .local_bundle_transport import same_origin
from .models import Principal


def register_knowledge_qualification_routes(router,*,service,principal,call):
    @router.get('/api/v2/knowledge-qualifications/schema')
    async def schema(identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return {'contract_version':'boi/published-knowledge-qualification@1','requests':{
            'status':PublishedQualificationRead.model_json_schema(),'refresh':PublishedQualificationRefresh.model_json_schema()},
            'refresh_basis':'current_editor_and_explicit_source_rights',
            'new_semantic_review':'optional_explicit_native_statement_inventory_review',
            'node_opinions':'reuse_exact_preserved_source_bound_judgments',
            'statement_review_inputs':'current_native_unresolved_inventory_and_existing_source_quotations',
            'omitted_statement_review':'no_statement_grant_copied',
            'response_use':'model_input','source_model_input_required':True,
            'publication_changed':False,'unknown_check_retried':False}

    @router.post('/api/v2/knowledge-qualifications/status')
    async def status(payload:PublishedQualificationRead,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(service.domain_intake.published_qualifications,identity,payload)

    @router.post('/api/v2/knowledge-qualifications/refresh')
    async def refresh(http_request:Request,payload:PublishedQualificationRefresh,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.draft')
        if identity.auth_source!='pat':same_origin(http_request)
        return await call(service.domain_intake.published_qualifications,identity,payload)
