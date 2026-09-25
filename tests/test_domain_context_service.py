"""Synthetic helper closure for focused MCP release validation."""
from boi_api.app.governed_runtime.domain_asset_store import DomainAssetCreateRequest, source_manifest_digest


from boi_api.app.governed_runtime.domain_context_service import (
    DomainContextService, DomainContextPrepareRequest, DomainContextPageRequest, DomainContextAcknowledgeRequest,
    request_context_decoding, same_canonical_definition_scope,
)


from boi_api.app.governed_runtime.task_context_reading import TaskContextPage, receive_task_context


def prepare(service, auth, source, **kwargs):
    return service.prepare(authorization=auth,request=DomainContextPrepareRequest(
        sources=(source,),namespace='sample',purpose='intake',**kwargs))


def page_request(prepared, index=0):
    return DomainContextPageRequest(context_ref=prepared['context_ref'],
        expected_context_digest=prepared['context_digest'],page_index=index)


def receive(service, auth, source, prepared):
    pages = tuple(TaskContextPage.model_validate(service.read_page(authorization=auth,
        request=page_request(prepared,i))['page']) for i in range(prepared['page_count']))
    delivered = receive_task_context(pages,expected_context_digest=prepared['context_digest'],
        principal_id=auth.principal,policy_digest=auth.policy_digest,purpose='intake',
        source_manifest_digest=source_manifest_digest((source,)))
    request = DomainContextAcknowledgeRequest(context_ref=prepared['context_ref'],
        expected_context_digest=prepared['context_digest'],page_digests=tuple(p.chunk_digest for p in pages))
    return delivered, service.acknowledge(authorization=auth,request=request), request
