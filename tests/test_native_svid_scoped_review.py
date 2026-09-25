"""Synthetic helper closure for focused MCP release validation."""
from tests.test_process_knowledge import sample


from boi_api.app.governed_runtime.domain_asset_store import DomainAssetStore,DomainAssetCreateRequest,DomainAssetDraft


from boi_api.app.governed_runtime.native_definition_context import NativeDefinitionReviewV2


from boi_api.app.governed_runtime.native_observation import NativeObservation


def save_native_opinion(sample,store,contexts,prepared,*,key):
    claims=[{'target_pointer':p,'label':'supported','failure_kind':'none','reason':'Synthetic opinion only.',
        'evidence':[{'field_locator':'/description','quote':'If cold, voids may form.'}]}
        for p in prepared['scope']['target_pointers']]
    value=NativeDefinitionReviewV2(definition_revisions=[prepared['definition_revision']],
        disposition='supported_with_limits',findings=['Original source comparison only.'],
        limitations=['Retain these original limits.'],scope=prepared['scope'],
        source_assessment={'claims':claims,'fields':[],'limitations':['Not scientific truth.']})
    observation=NativeObservation(agent_session_ref='synthetic-'+key,request=prepared['request'],value_json=value.model_dump_json())
    return store.create(authorization=sample['auth'],request=DomainAssetCreateRequest(draft=DomainAssetDraft(
        logical_id='sample:'+key,namespace='sample',kind='pack',title='Scoped native opinion',description='Synthetic test',
        content_json=observation.model_dump_json(),sources=[sample['source']],
        definition_reading_ref=prepared['request']['knowledge_reading_ref'],dependencies=[{
            'revision':r,'role':'review_input','reason':'Exact input','stages':['review']} for r in prepared['request']['input_revisions']]),
        idempotency_key=key),validate_reading=lambda ref,sources:contexts.validate_reading(
            authorization=sample['auth'],revision=ref,sources=sources))
