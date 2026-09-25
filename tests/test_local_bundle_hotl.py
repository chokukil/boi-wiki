"""Synthetic helper closure for focused MCP release validation."""
from boi_api.app.v2.models import TokenCreateRequest


from tests.test_domain_intake_transport import transport, v2_service, principal


def hotl_client(transport, principal):
    client, source, service = transport
    issued = service.pats.create(principal, TokenCreateRequest(name='synthetic-hotl',
        scopes=['boi.read', 'boi.draft', 'boi.execute.low']))
    client.headers['Authorization'] = 'Bearer ' + issued['token']
    return client, source, service, issued['token_id']


def admission(value, **updates):
    return {key:value[key] for key in ('bundle_ref', 'manifest_digest', 'preview_digest')} | updates
