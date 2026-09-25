"""Real issued Profile authority is required for new DB connection binding."""
import json
from types import SimpleNamespace

import pytest

from tests.test_process_knowledge import sample
from tests.test_native_mapping_profile_reuse import issued_pair
from boi_api.app.v2.database_source import bind_database_query, database_source_call, DATABASE_BINDINGS
from boi_api.app.v2.domain_intake import DomainIntakeService
from boi_api.app.v2.native_query import discover_native_queries, NativeQueryHost
from boi_api.app.governed_runtime.semantic_query_execution import capture_sqlite_planner_catalog
from boi_api.app.governed_runtime.sqlite_source_snapshot import sealed_sqlite_digest


def test_admitted_profile_binds_same_discovered_snapshot_and_reuses_registration(sample,tmp_path,monkeypatch):
    def capture(path,**kwargs):
        kwargs['captured_at']='snapshot:'+sealed_sqlite_digest(path)
        return capture_sqlite_planner_catalog(path,**kwargs)
    work,auth,catalog,base,definition,review0,profile,review=issued_pair(sample,tmp_path,capture_catalog=capture)
    intake=DomainIntakeService(sample['intake'],lambda _:auth)
    principal=SimpleNamespace(employee_id=auth.principal,teams=(),roles=('boi.editor',),token_id=None)
    registry=tmp_path/'registry.json'
    registry.write_text(json.dumps({'sources':[{'source_id':'test','title':'Generated catalog',
        'principals':[auth.principal],'allowed_tables':['catalog'],'sqlite_path':str(tmp_path/'catalog.sqlite3')}]}))
    monkeypatch.setenv('BOI_DATABASE_SOURCES_PATH',str(registry))
    monkeypatch.setenv('BOI_DATABASE_QUERY_STORAGE',str(tmp_path/'query'))
    monkeypatch.setenv('BOI_NATIVE_QUERY_CONFIG_PATH',str(tmp_path/'absent.json'))
    monkeypatch.setenv('BOI_NATIVE_QUERY_REGISTRATION_CATALOG_PATH',str(tmp_path/'absent-registration.json'))
    schema=database_source_call(intake,principal,{'source_id':'test'},action='source_schema')
    assert schema['planner_catalog']==catalog.model_dump(mode='json')
    request={'source_id':'test','snapshot_digest':schema['snapshot_digest'],
        'profile_revision':profile['revision'],'review_revision':review['revision']}
    result=bind_database_query(intake,principal,request)
    assert result['registration_status']=='registered'
    again=bind_database_query(intake,principal,request)
    assert again['connection_id']==result['connection_id'] and again['registration_status']=='already_registered'
    discovered=discover_native_queries(intake,principal)
    assert discovered['connections'][0]['connection_id']==result['connection_id']
    assert 'sqlite_path' not in str(discovered)
    assert len(sample['intake'].store.list(DATABASE_BINDINGS))==1
    with pytest.raises(ValueError):
        bind_database_query(intake,principal,{**request,'review_revision':definition['revision']})
    registry.write_text('{"sources":[]}')
    with pytest.raises(ValueError,match='NOT_CONFIGURED'):
        discover_native_queries(intake,principal)
