"""Synthetic helper closure for focused MCP release validation."""
import copy


import json


import sqlite3


from types import SimpleNamespace


from tests.test_process_knowledge import sample


from tests.test_meaning_read_reuse import native_inputs


from tests.test_domain_context_service import receive


from tests.test_native_svid_scoped_review import save_native_opinion


from boi_api.app.governed_runtime.domain_asset_store import DomainAssetStore, DomainAssetCreateRequest, DomainAssetDraft


from boi_api.app.governed_runtime.domain_context_service import DomainContextService, DomainContextPrepareRequest


from boi_api.app.governed_runtime.native_profile_context import NativeProfileProjectionV2, read_native_profile_bundle


from boi_api.app.governed_runtime.semantic_query_execution import capture_sqlite_planner_catalog


from boi_api.app.v2.domain_intake import DomainIntakeService


from boi_api.app.v2.native_process_review import prepare_native_process_review


def issued_pair(sample, tmp_path, *, changed=False, capture_catalog=capture_sqlite_planner_catalog):
    _, args = native_inputs(sample)
    evidence = json.loads(args['context']['assets'][0]['content_json'])['claims'][0]['evidence']
    nodes = [dict(id='object:fixture', kind='ObjectType', definition='Synthetic object', evidence=evidence),
        dict(mapping_id='mapping:fixture', domain_ref='object:fixture',
            physical=dict(source='test', table='catalog', column='id'),
            definition='Synthetic exact mapping', conditions=['Retain this condition'], evidence=evidence)]
    store = DomainAssetStore(sample['intake'])
    contexts = DomainContextService(sample['intake'])
    intake = DomainIntakeService(sample['intake'], lambda _:sample['auth'])
    principal = SimpleNamespace(employee_id=sample['auth'].principal, teams=())
    path = tmp_path/'catalog.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE catalog (id TEXT)')
    catalog = capture_catalog(path, source_id='test', allowed_tables=('catalog',),
        captured_at='2026-09-11T00:00:00Z')

    def reading(namespace, revisions):
        roots = [dict(revision=r, role='profile_input', reason='Exact fixture dependency', stages=['prepare'])
            for r in revisions]
        prepared = contexts.prepare(authorization=sample['auth'], request=DomainContextPrepareRequest(
            sources=[sample['source']], namespace=namespace, purpose='intake', roots=roots,
            definition_reading='selected_dependencies'))
        _, ack, _ = receive(contexts, sample['auth'], sample['source'], prepared)
        return roots, ack

    def stage(namespace, value, prior=None):
        candidate = store.create(authorization=sample['auth'], request=DomainAssetCreateRequest(
            draft=DomainAssetDraft(logical_id=namespace+':definition', namespace=namespace,
                kind='definition', title='Fixture definition', description='Synthetic review plumbing',
                sources=[sample['source']], content_json=json.dumps({
                    'contract_version':'boi/native-dexa-definition@1','entries':value})),
            idempotency_key=namespace+':definition'))
        _, ack = reading(namespace, [candidate['revision']])
        prepared = prepare_native_process_review(intake, principal, definition_revision=candidate['revision'],
            knowledge_reading_ref=ack['reading_ref'], target_pointers=['/entries/0','/entries/1'])
        review = save_native_opinion(sample, store, contexts, prepared, key=namespace+'-review')
        refs = [candidate['revision'],review['revision']]+([prior['revision']] if prior else [])
        roots, ack = reading(namespace, refs)
        entries = [dict(entry_id=node.get('id') or node['mapping_id'],
            category='domain' if i == 0 else 'mapping', definition_revision=candidate['revision'],
            definition_pointer=f'/entries/{i}', payload_json=json.dumps(node), physical=node.get('physical'),
            **({'source_revision':prior['revision']} if prior and i == 1 else {}))
            for i,node in enumerate(value)]
        projection = NativeProfileProjectionV2(definition_review_revision=review['revision'],
            definition_revisions=[candidate['revision']], catalog_snapshot_digest=catalog.snapshot_digest,
            schema_digest=catalog.schema_digest, entries=entries)
        profile = store.create(authorization=sample['auth'], request=DomainAssetCreateRequest(
            draft=DomainAssetDraft(logical_id=namespace+':profile', namespace=namespace, kind='profile',
                title='Fixture profile', description='Exact mapping reuse', content_json=projection.model_dump_json(),
                sources=[sample['source']], dependencies=roots, definition_reading_ref=ack['reading_ref']),
            idempotency_key=namespace+':profile'),
            validate_reading=lambda ref,sources:contexts.validate_reading(
                authorization=sample['auth'],revision=ref,sources=sources))
        return profile, candidate, review

    base, base_definition, base_review = stage('mapping-basis', nodes)
    final_nodes = copy.deepcopy(nodes)
    if changed:
        final_nodes[1]['conditions'] = []
    final, _, review = stage('relation-assembly', final_nodes, base)
    auth, work = intake._work(principal)
    return work, auth, catalog, base, base_definition, base_review, final, review
