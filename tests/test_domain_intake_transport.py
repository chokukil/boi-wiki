"""Synthetic helper closure for focused MCP release validation."""
from dataclasses import replace


from datetime import datetime, timezone


from fastapi import FastAPI


from fastapi.testclient import TestClient


import pytest


from boi_api.app.governed_runtime.source_intake import IntakeAuthorization, SourceIntakeService


from boi_api.app.governed_runtime.ledger import GovernedRuntimeLedger


from boi_api.app.governed_runtime.release_rebuild import KnowledgeObjectStore


from boi_api.app.v2.domain_intake import DomainIntakeService


from boi_api.app.v2.models import TokenCreateRequest


from boi_api.app.v2.routes import build_agent_v2_router


from tests.test_agent_v2 import v2_service, principal


@pytest.fixture()
def transport(v2_service, principal, tmp_path, monkeypatch):
    # The default delivery recipient in this synthetic transport is its owner.
    monkeypatch.setenv('BOI_AUTH_MODE', 'dev')
    monkeypatch.setenv('DEMO_EMPLOYEE_ID', principal.employee_id)
    source = SourceIntakeService(store=v2_service.store, ledger=GovernedRuntimeLedger(tmp_path/'source-ledger'),
        objects=KnowledgeObjectStore(tmp_path/'source-objects'), clock=lambda:datetime(2026,9,5,tzinfo=timezone.utc))
    auth = IntakeAuthorization(principal.employee_id, 'sha256:'+'a'*64, ('store','derive','model_input'))
    v2_service.domain_intake = DomainIntakeService(source, lambda identity:replace(auth, principal=identity.employee_id),
        current_token_provider=lambda token_id:v2_service.store.get('tokens', token_id))
    def no_internal_agent(*args, **kwargs):
        raise AssertionError('Domain source intake must not invoke the Wiki internal agent')
    monkeypatch.setattr(v2_service, 'run_turn', no_internal_agent)
    app = FastAPI()
    app.include_router(build_agent_v2_router(v2_service))
    token = v2_service.pats.create(principal,
        TokenCreateRequest(name='domain-intake-test', scopes=['boi.read','boi.draft']))['token']
    client = TestClient(app, headers={'Authorization':'Bearer '+token})
    return client, source, v2_service
