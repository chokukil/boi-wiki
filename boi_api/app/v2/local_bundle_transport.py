"""Browser confirmation and binary upload boundaries for external local bundles."""
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..auth import AuthError, SESSION_COOKIE_NAME, identity_from_session_token
from ..governed_runtime.local_bundle_contract import LocalBundleConfirmRequest, LocalBundleChallengeRequest
from ..governed_runtime.local_bundle_service import VerifiedWebSession
from ..governed_runtime.local_bundle_upload import LocalBundleUpload
from ..governed_runtime.source_envelope import byte_digest
from .auth import require_scope
from .models import Principal


def same_origin(request):
    origin = request.headers.get('origin')
    actual = request.url
    try:
        supplied = urlsplit(origin or '')
        expected = (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme == 'https' else 80))
        valid = ((supplied.scheme, supplied.hostname, supplied.port or (443 if supplied.scheme == 'https' else 80))
            == expected and not (supplied.username or supplied.password or supplied.path or supplied.query or supplied.fragment))
    except ValueError:
        valid = False
    if (not valid or request.headers.get('x-requested-with') != 'BoI-Wiki'
            or request.headers.get('sec-fetch-site') == 'cross-site'):
        raise HTTPException(status_code=403, detail={'reason_code':'LOCAL_BUNDLE_ORIGIN_DENIED'})


def verified_session(request, identity):
    same_origin(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if request.headers.get('authorization') or identity.auth_source == 'pat' or not token:
        raise HTTPException(status_code=403, detail={'reason_code':'LOCAL_BUNDLE_WEB_SESSION_NOT_AUTHORIZED'})
    try:
        signed = identity_from_session_token(token)
    except AuthError:
        raise HTTPException(status_code=403, detail={'reason_code':'LOCAL_BUNDLE_WEB_SESSION_NOT_AUTHORIZED'}) from None
    if (signed.employee_id != identity.employee_id
            or signed.auth_source not in ('session', 'keycloak', 'trusted_header', 'dev_session')
            or not {'boi.admin', 'boi.editor'} & set(signed.roles) & set(identity.roles)):
        raise HTTPException(status_code=403, detail={'reason_code':'LOCAL_BUNDLE_WEB_SESSION_NOT_AUTHORIZED'})
    return VerifiedWebSession(identity.employee_id, byte_digest(token.encode()),
        auth_source=signed.auth_source, actor=signed.session_actor, delegation_ref=signed.delegation_ref)


def register_local_bundle_routes(router, *, service, principal, call):
    def bundles(identity):
        return service.domain_intake.local_bundles(identity)

    @router.get('/api/v2/local-bundles/{digest}/changes/{object_id}/baseline')
    async def comparison_baseline(digest: str, object_id: str, preview_digest: str,
            identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        def read(owner, _):
            bundle, auth, _ = bundles(owner)
            return bundle.comparison_baseline(authorization=auth, bundle_ref='local-bundle:sha256:' + digest,
                object_id=object_id, preview_digest=preview_digest)
        value = await call(read, identity, None)
        return JSONResponse(value, headers={'Cache-Control':'no-store', 'Referrer-Policy':'same-origin',
            'X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/local-bundles/challenge')
    async def challenge(http_request: Request, payload: LocalBundleChallengeRequest,
            identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        session = verified_session(http_request, identity)
        def invoke(owner, req):
            bundle, auth, _ = bundles(owner)
            return bundle.challenge(authorization=auth, bundle_ref=req.bundle_ref, session=session,impact_ref=req.impact_ref)
        return await call(invoke, identity, payload)

    @router.get('/api/v2/local-bundles/{digest}/impact')
    async def impact(digest:str,preview_digest:str,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        # Human preview is cookie-authenticated. A PAT must use model_input
        # policies through the existing agent-facing incoming-reference API.
        if identity.auth_source=='pat':
            raise HTTPException(status_code=403,detail={'reason_code':'LOCAL_BUNDLE_IMPACT_BROWSER_REQUIRED'})
        def read(owner,_):
            bundle,auth,_=bundles(owner)
            if bundle.impact_factory is None:
                raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_UNAVAILABLE')
            return bundle.impact_factory(bundle).prepare(authorization=auth,
                bundle_ref='local-bundle:sha256:'+digest,preview_digest=preview_digest)
        return JSONResponse(await call(read,identity,None),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.get('/api/v2/local-bundles/{digest}/impact/page')
    async def impact_page(digest:str,impact_ref:str,scope_index:int=Query(ge=0,le=255),
            cursor:str|None=Query(default=None,max_length=120),identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        if identity.auth_source=='pat':
            raise HTTPException(status_code=403,detail={'reason_code':'LOCAL_BUNDLE_IMPACT_BROWSER_REQUIRED'})
        def read(owner,_):
            bundle,auth,_=bundles(owner)
            if bundle.impact_factory is None:
                raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_UNAVAILABLE')
            return bundle.impact_factory(bundle).page(authorization=auth,bundle_ref='local-bundle:sha256:'+digest,
                impact_ref=impact_ref,scope_index=scope_index,cursor=cursor)
        return JSONResponse(await call(read,identity,None),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/local-bundles/confirm')
    async def confirm(http_request: Request, payload: LocalBundleConfirmRequest,
            identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        session = verified_session(http_request, identity)
        def invoke(owner, req):
            bundle, auth, _ = bundles(owner)
            return bundle.confirm(authorization=auth, request=req, session=session)
        return await call(invoke, identity, payload)

    @router.put('/api/v2/local-bundles/{digest}/objects/{object_id}')
    async def upload(http_request: Request, digest: str, object_id: str,
            offset: int = Query(ge=0), identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.draft')
        if identity.auth_source != 'pat':
            same_origin(http_request)
        bundle_ref = 'local-bundle:sha256:' + digest
        def preflight(owner, _):
            bundle, auth, _ = bundles(owner)
            _, obj, _ = bundle.upload_context(authorization=auth, bundle_ref=bundle_ref, object_id=object_id)
            return LocalBundleUpload.expected_length(obj, offset)
        # Authorization and exact expected size precede consumption of the body.
        expected = await call(preflight, identity, None)
        if (http_request.headers.get('content-type', '').split(';')[0] != 'application/octet-stream'
                or http_request.headers.get('content-encoding') not in (None, 'identity')
                or http_request.headers.get('content-length') != str(expected)):
            raise HTTPException(status_code=422, detail={'reason_code':'LOCAL_BUNDLE_CHUNK_HEADERS_INVALID'})
        raw = bytearray()
        async for block in http_request.stream():
            if len(raw) + len(block) > expected:
                raise HTTPException(status_code=413, detail={'reason_code':'LOCAL_BUNDLE_CHUNK_BYTE_LIMIT'})
            raw.extend(block)
        chunk_digest = http_request.headers.get('x-boi-chunk-digest', '')
        def receive(owner, _):
            bundle, auth, root = bundles(owner)
            return LocalBundleUpload(bundle, root).put(authorization=auth, bundle_ref=bundle_ref,
                object_id=object_id, offset=offset, chunk_digest=chunk_digest, raw=bytes(raw))
        return await call(receive, identity, None)

    @router.get('/knowledge/local-bundles/{digest}', response_class=HTMLResponse)
    async def confirmation_page(digest: str, identity: Principal = Depends(principal)):
        from .local_bundle_view import render_bundle_confirmation
        from .knowledge_portal import portal_csp
        require_scope(identity, 'boi.read')
        def read(owner, _):
            bundle, auth, _ = bundles(owner)
            return bundle.view(authorization=auth, bundle_ref='local-bundle:sha256:' + digest)
        value = await call(read, identity, None)
        if identity.auth_source == 'dev_session':
            from ..dev_browser_auth import configured_identity
            session = configured_identity()
            value = {**value, 'confirmation_session_context':{
                'auth_source':session.auth_source, 'actor':session.session_actor or session.employee_id,
                'delegation_ref':session.delegation_ref}}
        content = render_bundle_confirmation(value)
        return HTMLResponse(content, headers={
            'Cache-Control':'no-store', 'Referrer-Policy':'same-origin', 'X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':portal_csp(content, connect=True)})
