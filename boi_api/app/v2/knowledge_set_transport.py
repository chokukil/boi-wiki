"""Authenticated content population references; no caller-supplied ACL or SQL."""
from fastapi import Depends
from fastapi.responses import JSONResponse

from ..governed_runtime.knowledge_space_sets import KnowledgeSetCreate,KnowledgeSetRead
from ..governed_runtime.knowledge_reference_impact import KnowledgeIncomingRead
from ..governed_runtime.native_reference_repair import NativeReferenceRepairRequest
from ..governed_runtime.native_contract_repair import NativeContractRepairRequest
from .auth import require_scope
from .models import Principal


def register_knowledge_set_routes(router, *, service,principal,call):
    @router.post('/api/v2/knowledge-sets')
    async def create(payload:KnowledgeSetCreate,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(service.domain_intake.knowledge_sets,identity,payload)

    @router.post('/api/v2/knowledge-sets/read')
    async def read(payload:KnowledgeSetRead,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return await call(service.domain_intake.knowledge_sets,identity,payload)

    @router.post('/api/v2/knowledge-sets/incoming')
    async def incoming(payload:KnowledgeIncomingRead,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_sets,identity,payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-sets/repair-references')
    async def repair(payload:NativeReferenceRepairRequest | NativeContractRepairRequest,identity:Principal=Depends(principal)):
        require_scope(identity,'boi.draft')
        require_scope(identity,'boi.read')
        return JSONResponse(await call(service.domain_intake.repair_references,identity,payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
