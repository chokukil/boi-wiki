"""Host result lifecycle with real protected SQLite and synthetic authority."""
from types import SimpleNamespace
import pytest
from boi_api.app.v2 import native_query
from boi_api.app.governed_runtime.semantic_query_planner import CheckEvidenceStore
from tests.test_native_result_reuse import setup


def test_execute_and_result_read_preserve_rows_and_do_not_reexecute(tmp_path,monkeypatch):
    assert hasattr(native_query.NativeQueryHost,'execute'), 'Native host execution is missing'
    gateway,request,current=setup(tmp_path)
    req=request('count_rows')
    host=object.__new__(native_query.NativeQueryHost)
    host.authorization=SimpleNamespace(principal=req.principal)
    host.connection=SimpleNamespace(connection_id='registered')
    host.connection_digest='sha256:'+'a'*64
    host.records=native_query.NativeQueryRecordStore(CheckEvidenceStore(tmp_path/'records'))
    host.timings={}
    host._connection=lambda r: None if r.connection_id=='registered' else (_ for _ in ()).throw(ValueError('bad connection'))
    host._gateway_for_plan=lambda ref,key:(gateway,req)
    monkeypatch.setenv('BOI_EXTERNAL_URL','https://wiki.example')
    result=native_query.NativeQueryHost.execute(host,dict(connection_id='registered',plan_ref='evidence://sha256:'+'b'*64,idempotency_key='count_rows'))
    assert result['execution']['result']['result_sets'][0]['rows']==[{'answer':3}]
    def forbidden(*args,**kwargs):raise AssertionError('Reading a result reexecuted its business query')
    monkeypatch.setattr(gateway,'create',forbidden)
    reused=native_query.NativeQueryHost.result(host,dict(connection_id='registered',execution_ref=result['execution_ref']))
    assert reused['artifact']['result_sets'][0]['rows']==[{'answer':3}]
    assert reused['result_url']==('https://wiki.example/native-query-results/'
        +result['execution_ref'].removeprefix('evidence://sha256:')+'?connection_id=registered')
    assert reused['display_sets'][0]['columns']==[{'output_name':'answer','label':'count_rows(id)'}]
    from boi_api.app.v2.native_query_result_view import render_native_query_result
    assert 'count_rows(id)' in render_native_query_result(reused)
    assert reused['business_query_executed'] is False
    current['allowed']=False
    with pytest.raises(ValueError,match='CURRENT_SCOPE_REVOKED'):
        native_query.NativeQueryHost.result(host,dict(connection_id='registered',execution_ref=result['execution_ref']))
    assert host.timings['sql_and_result_storage']['calls'] == 1
    assert host.timings['protected_result_read']['calls'] == 2
    assert host.timings['protected_result_read']['failures'] == 1
