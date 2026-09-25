"""Human Wiki pages and model-purpose API reads use the same published revision."""
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from ..governed_runtime.knowledge_published_read import PublishedDocumentRead, PublishedSourceRead
from ..governed_runtime.semantic_binding_contract import RevisionRef
from .recipient_delivery_access import RecipientAccessRequest, check_recipient_access
from .auth import require_scope
from .models import Principal
from .knowledge_published_view import render_published_document, render_published_source, FEEDBACK_SCRIPT


def unavailable_page(error,*,templates,request,shell_context_factory,identity,source=False):
    from .knowledge_published_view import render_published_unavailable
    from .knowledge_portal import render_knowledge_record,portal_csp
    fragment=render_published_unavailable(source=source,status=error.status_code)
    if templates is not None and shell_context_factory is not None:
        response=render_knowledge_record(templates,request,shell_context_factory,identity,
            title='열람 상태',fragment=fragment,kind='source' if source else 'definition')
        response.status_code=error.status_code
        return response
    return HTMLResponse(fragment,status_code=error.status_code,
        headers={'Cache-Control':'private, no-store','Content-Security-Policy':portal_csp(fragment)})


def published_page(value,*,templates,request,shell_context_factory,identity,source=False):
    from .knowledge_portal import render_knowledge_record,portal_csp
    fragment=render_published_source(value) if source else render_published_document(value)+FEEDBACK_SCRIPT
    title='인용한 원문 확인' if source else value['title']
    if templates is not None and shell_context_factory is not None:
        return render_knowledge_record(templates,request,shell_context_factory,identity,
            title=title,fragment=fragment,kind='source' if source else 'definition',connect=not source)
    return HTMLResponse('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>BoI Wiki</title><body>'+fragment+'</body></html>',
        headers={'Cache-Control':'private, no-store','Content-Security-Policy':portal_csp(fragment,connect=not source)})


def revision_from_digest(digest):
    try:return RevisionRef(ref='KnowledgeRevision:sha256:'+digest,revision_digest='sha256:'+digest)
    except ValueError:raise HTTPException(status_code=404,detail={'reason_code':'KNOWLEDGE_DOCUMENT_NOT_FOUND'}) from None


def register_published_document_routes(router,*,service,principal,call,templates,shell_context_factory):
    @router.post('/api/v2/delivery/recipient-access')
    async def recipient_access_read(payload:RecipientAccessRequest,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(lambda actor,request:check_recipient_access(service.domain_intake,actor,request),identity,payload)

    @router.post('/api/v2/knowledge-documents/read')
    async def read(payload:PublishedDocumentRead,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(service.domain_intake.published_document,identity,payload)

    @router.post('/api/v2/knowledge-documents/source')
    async def source(payload:PublishedSourceRead,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(service.domain_intake.published_document,identity,payload)

    @router.get('/knowledge/records/{digest}',response_class=HTMLResponse)
    async def document(digest:str,http_request:Request,identity:Principal=Depends(principal),
            meaning:str|None=Query(default=None,min_length=1,max_length=2048),claim_offset:int=Query(default=0,ge=0)):
        require_scope(identity,'boi.read')
        req=PublishedDocumentRead(revision=revision_from_digest(digest),meaning_pointer=meaning,claim_offset=claim_offset,include_sources=True)
        try:
            try:value=await call(lambda actor,request:service.domain_intake.published_document(actor,request,model_input=False),identity,req)
            except HTTPException as error:
                # Optional source display must not withhold an independently shared
                # document. Retry only the body read, under its own current gate.
                reason=error.detail.get('reason_code') if isinstance(error.detail,dict) else None
                if reason not in {'KNOWLEDGE_SOURCE_ACCESS_DENIED','KNOWLEDGE_SOURCE_CITE_NOT_AUTHORIZED',
                        'KNOWLEDGE_SOURCE_BUNDLE_LIMIT_REQUIRES_NARROWER_SELECTION','KNOWLEDGE_DOCUMENT_CONTENT_UNSUPPORTED'}:raise
                value=await call(lambda actor,request:service.domain_intake.published_document(actor,request,model_input=False),
                    identity,req.model_copy(update={'include_sources':False}))
        except HTTPException as error:
            return unavailable_page(error,templates=templates,request=http_request,
                shell_context_factory=shell_context_factory,identity=identity)
        return published_page(value,templates=templates,request=http_request,shell_context_factory=shell_context_factory,identity=identity)

    @router.get('/knowledge/records/{digest}/sources/{binding_index}',response_class=HTMLResponse)
    async def source_page(digest:str,binding_index:int,http_request:Request,identity:Principal=Depends(principal),
            offset:int|None=Query(default=None,ge=0),limit:int=Query(default=4096,ge=1,le=8192)):
        require_scope(identity,'boi.read')
        try:req=PublishedSourceRead(revision=revision_from_digest(digest),binding_index=binding_index,offset=offset,limit=limit)
        except ValueError:raise HTTPException(status_code=400,detail={'reason_code':'KNOWLEDGE_SOURCE_SELECTION_INVALID'}) from None
        try:value=await call(lambda actor,request:service.domain_intake.published_document(actor,request,model_input=False),identity,req)
        except HTTPException as error:
            return unavailable_page(error,templates=templates,request=http_request,
                shell_context_factory=shell_context_factory,identity=identity,source=True)
        return published_page(value,templates=templates,request=http_request,shell_context_factory=shell_context_factory,identity=identity,source=True)
