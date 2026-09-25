"""Synthetic helper closure for focused MCP release validation."""
import json


from boi_api.app.governed_runtime.domain_asset_store import DomainAssetCreateRequest, DomainAssetDraft, DomainAssetStore


from tests.test_source_field_projection import captured


def setup_assets(tmp_path):
    source, auth, reference, _ = captured(tmp_path,b'{"definition":"Source statement with a condition"}')
    return DomainAssetStore(source), auth, {'kind':'artifact_ref',**{k:reference[k] for k in ('artifact_ref','digest','role')}}


def draft(reference, **overrides):
    return DomainAssetDraft(logical_id='sample:definition',namespace='sample',title='Sample definition',
        description='Unqualified interpretation of a supplied source',kind='definition',
        content_json=json.dumps({'definition':'A proposed reading','condition':'Only in the stated case'}),
        sources=(reference,),**overrides)


def create(store, auth, proposal, key='create'):
    return store.create(authorization=auth,request=DomainAssetCreateRequest(draft=proposal,idempotency_key=key))
