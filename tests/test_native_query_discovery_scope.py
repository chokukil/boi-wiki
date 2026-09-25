"""Discovery offers authorized selection context, never execution authority."""
import json
from types import SimpleNamespace
from boi_api.app.v2 import native_query
from tests.test_native_profile_context import material
from boi_api.app.governed_runtime.semantic_query_planner import PlanningPolicy


def test_discovery_exposes_only_configured_principal_scope_and_no_host_paths(tmp_path,monkeypatch):
    authority,context,catalog,projection=material(tmp_path)
    principal=authority.principal
    connections=[]
    for key,owner in [('alpha',principal),('beta',principal),('hidden','someone-else')]:
        source_revision='sha256:'+('a' if key=='alpha' else 'b')*64
        connections.append(dict(connection_id=key,title='Synthetic '+key,
            execution_binding=dict(source_id=key,description='Synthetic source '+key,action_key='action-'+key,
                action_revision='sha256:'+'c'*64,dialect='sqlite',response_contract='dexa/sqlite-result@1',
                source_revision=source_revision,schema_revision='sha256:'+'d'*64,max_rows=10,timeout_seconds=5),
            catalog=catalog.model_dump(mode='json'),review_revision=authority.review_revision.model_dump(mode='json'),
            profile_revision=authority.review_revision.model_dump(mode='json'),
            scope=dict(principal=owner,operation='bounded_read_only_action_sqlite',source_snapshot_digest=source_revision,
                allowed_sources=[key],allowed_tables=['sample'],max_output_rows=10,max_scan_rows=100,
                request_text_digest='sha256:'+'a'*64,request_source='fixture:explicit',production_authorized=False),
            planning_policy=PlanningPolicy(policy_id='fixture',allowed_relationship_authorities=('source',),allowed_join_kinds=('INNER',),max_physical_sources=1,max_scan_tables=4,cross_database_allowed=False,max_estimated_rows=100,max_result_rows=10,timeout_seconds=5,required_dialect='sqlite').model_dump(mode='json'),storage_root='/private-do-not-return/'+key))
    config=tmp_path/'connections.json';config.write_text(json.dumps({'connections':connections}));monkeypatch.setenv('BOI_NATIVE_QUERY_CONFIG_PATH',str(config))
    intake=SimpleNamespace(_work=lambda actor:(SimpleNamespace(principal=principal),object()))
    out=native_query.discover_native_queries(intake,object())
    assert {x['connection_id'] for x in out['connections']}=={'alpha','beta'}
    for item in out['connections']:
        selection=item['selection_context']
        assert selection['allowed_sources']==[item['connection_id']]
        assert selection['allowed_tables']==['sample']
        assert selection['max_output_rows']==10 and selection['max_scan_rows']==100
        assert selection['scope_basis']=='configured_candidate_requires_current_prepare'
        assert selection['execution_authority_granted'] is False
    wire=json.dumps(out)
    assert 'private-do-not-return' not in wire and 'someone-else' not in wire and 'hidden' not in wire
    assert out['query_execution_status']=='not_run'
