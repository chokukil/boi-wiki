"""Synthetic helper closure for focused MCP release validation."""
import json


from types import SimpleNamespace


from boi_api.app.governed_runtime.native_definition_context import (
    NativeDefinitionReview, read_native_definition_authority,
)


from boi_api.app.governed_runtime.native_observation import NativeObservation, NativeObservationInput


from boi_api.app.governed_runtime.domain_context_service import DomainContextService


from boi_api.app.governed_runtime.domain_asset_store import DomainAssetCreateRequest, source_manifest_digest


from tests.test_domain_asset_store import setup_assets, draft, create


from tests.test_domain_context_service import prepare, receive


def binding(tmp_path, *, disposition='supported_with_limits'):
    store, auth, source = setup_assets(tmp_path)
    target = create(store, auth, draft(source))['revision']
    contexts = DomainContextService(store.intake)
    _, reading, _ = receive(contexts, auth, source, prepare(contexts, auth, source))
    value = NativeDefinitionReview(definition_revisions=[target],
        disposition=disposition, findings=['Source condition retained'],
        limitations=['Same-session opinion; no independent verifier.'])
    request = NativeObservationInput(prompt='Compare definition and source without granting execution.',
        output_schema_json=json.dumps(NativeDefinitionReview.model_json_schema()),
        source_manifest_digest=source_manifest_digest([source]), input_revisions=[target],
        knowledge_reading_ref=reading['reading_ref'], review_contract_version=value.contract_version)
    observation = NativeObservation(agent_session_ref='synthetic-native-session',
        request=request, value_json=value.model_dump_json())
    proposal = draft(source, definition_reading_ref=reading['reading_ref'],
        dependencies=[{'revision':target,'role':'definition','reason':'Reviewed source definition','stages':['review']}]).model_copy(
            update={'logical_id':'sample:definition-review','kind':'pack','content_json':observation.model_dump_json()})
    saved = store.create(authorization=auth,request=DomainAssetCreateRequest(draft=proposal,idempotency_key='review'),
        validate_reading=lambda ref,sources:contexts.validate_reading(authorization=auth,revision=ref,sources=sources))
    return SimpleNamespace(intake=store.intake,contexts=contexts), auth, saved['revision'], target
