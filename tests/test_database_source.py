"""Generated DBs only: capture, evidence, resume, correction and access fences."""
from dataclasses import replace
import json
import sqlite3
from types import SimpleNamespace

import pytest

from boi_api.app.v2.database_source import database_source_call
from agent_kit.python.boi_profile_intake_router import database_profile_inventory
from tests.test_governed_source_intake import setup


@pytest.fixture
def db_source(tmp_path, monkeypatch):
    path = tmp_path/'source.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE knowledge (code TEXT, description TEXT, minimum REAL, unit TEXT)')
        db.executemany('INSERT INTO knowledge VALUES (?,?,?,?)', [
            ('A', 'Rinse the cover; inspect only when cool.', None, ''),
            ('B', 'Supply pressure, not the requested pressure.', 0, 'kPa'),
            ('B', 'Supply pressure, not the requested pressure.', 0, 'kPa')])
        db.execute('CREATE TABLE restricted (secret TEXT)')
    registry = tmp_path/'sources.json'
    registry.write_text(json.dumps({'sources':[{'source_id':'sample', 'title':'Generated DB',
        'principals':['owner'], 'allowed_tables':['knowledge'], 'sqlite_path':str(path)}]}))
    monkeypatch.setenv('BOI_DATABASE_SOURCES_PATH',str(registry))
    source, auth = setup(tmp_path/'store')
    auth = replace(auth, allowed_uses=(*auth.allowed_uses, 'model_input'))
    intake = SimpleNamespace(source_intake=source, _authorization=lambda p: replace(auth, principal=p))
    return intake, path, registry


def invoke(fixture, action, request=None, principal='owner'):
    return database_source_call(fixture[0], principal, request, action=action)


def test_capture_pages_preserves_duplicates_null_empty_zero_and_exact_evidence(db_source):
    discovered=invoke(db_source,'source_discover')
    assert discovered['sources'][0]['tables']==['knowledge']
    assert 'sqlite_path' not in str(discovered)
    schema=invoke(db_source,'source_schema',{'source_id':'sample'})
    request={'source_id':'sample','table':'knowledge','snapshot_digest':schema['snapshot_digest'],'limit':2}
    first=invoke(db_source,'source_capture',request)
    ledger=db_source[0].source_intake.ledger.events_path.read_bytes()
    assert invoke(db_source,'source_capture',request)==first
    assert db_source[0].source_intake.ledger.events_path.read_bytes()==ledger
    second=invoke(db_source,'source_capture',{**request,'offset':first['next_offset']})
    assert first['record_count']==2 and second['record_count']==1 and second['next_offset'] is None
    fields=first['records'][0]['fields']
    assert {f['structural_metadata']['database_column']:f['field_state'] for f in fields}['minimum']=='null'
    assert {f['structural_metadata']['database_column']:f['field_state'] for f in fields}['unit']=='empty'
    records=first['records']+second['records']
    features, rows=database_profile_inventory(records)
    assert len(features)==4 and len(rows)==3
    assert rows[1]['__source_record_locator__']!=rows[2]['__source_record_locator__']
    assert rows[1][features[0].source_path]==rows[2][features[0].source_path]
    assert first['publication_committed'] is False


def test_unauthorized_table_principal_paths_and_stale_snapshot_are_rejected(db_source):
    assert invoke(db_source,'source_discover',principal='other')['sources']==[]
    with pytest.raises(ValueError,match='NOT_AUTHORIZED'):
        invoke(db_source,'source_schema',{'source_id':'sample'},principal='other')
    schema=invoke(db_source,'source_schema',{'source_id':'sample'})
    request={'source_id':'sample','snapshot_digest':schema['snapshot_digest'],'table':'restricted'}
    with pytest.raises(ValueError,match='TABLE_NOT_AUTHORIZED'):
        invoke(db_source,'source_capture',request)
    with pytest.raises(ValueError):
        invoke(db_source,'source_schema',{'source_id':'sample','sqlite_path':str(db_source[1])})
    request['table']='knowledge'
    old=invoke(db_source,'source_capture',request)
    with sqlite3.connect(db_source[1]) as db:
        db.execute("UPDATE knowledge SET description='Inspect when warm.' WHERE code='A'")
    with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):
        invoke(db_source,'source_capture',request)
    schema=invoke(db_source,'source_schema',{'source_id':'sample'})
    new=invoke(db_source,'source_capture',{**request,'snapshot_digest':schema['snapshot_digest']})
    assert new['source']!=old['source']
    assert old['source']['artifact_ref'] in db_source[0].source_intake.ledger.events_path.read_text()
    with pytest.raises(ValueError,match='MIXED_SNAPSHOT'):
        database_profile_inventory([old['records'][0],new['records'][0]])


def test_scope_revocation_before_capture_returns_no_data(db_source, monkeypatch):
    from boi_api.app.v2 import database_source as module
    original=module._open
    from contextlib import contextmanager
    @contextmanager
    def revoke(*args):
        with original(*args) as value:
            yield value
        db_source[2].write_text('{"sources":[]}')
    monkeypatch.setattr(module,'_open',revoke)
    with pytest.raises(ValueError,match='NOT_AUTHORIZED'):
        invoke(db_source,'source_schema',{'source_id':'sample'})
