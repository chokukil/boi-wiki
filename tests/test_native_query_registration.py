"""Recipient-owned native-query registration never accepts caller source authority."""
import asyncio
import importlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from boi_api.app.v2 import native_query
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.semantic_query_planner import PlanningPolicy
from boi_api.app.governed_runtime.sqlite_source_snapshot import sealed_sqlite_digest
from tests.test_native_profile_context import material


def registered_fixture(tmp_path, monkeypatch, *, allowed_uses=('derive',)):
    source = tmp_path / 'source.sqlite'
    source.unlink(missing_ok=True)
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE records (id INTEGER)')
        db.executemany('INSERT INTO records VALUES (?)', [(1,), (2,)])
    authority, _, catalog, _ = material(tmp_path)
    auth = SimpleNamespace(principal=authority.principal, allowed_uses=allowed_uses)
    work = SimpleNamespace(current_knowledge_authorization=lambda: auth)
    intake = SimpleNamespace(_work=lambda actor: (auth, work))
    scope = dict(
        principal='native-query-registration-owner',
        operation='bounded_read_only_native_sqlite',
        source_snapshot_digest=sealed_sqlite_digest(source),
        allowed_sources=['dexa-mes-route-sample'],
        allowed_tables=['records'],
        max_output_rows=10,
        max_scan_rows=20,
        request_text_digest=semantic_digest('trusted registration template'),
        request_source='fixture:server-approved-template',
        production_authorized=False,
    )
    connection = native_query.NativeQueryConnection(
        connection_id='server-template-only',
        title='DEXA MES Route sample',
        sqlite_path=str(source),
        catalog=catalog,
        review_revision=authority.review_revision,
        profile_revision=authority.review_revision,
        scope=scope,
        planning_policy=PlanningPolicy(
            policy_id='fixture', allowed_relationship_authorities=('source',),
            allowed_join_kinds=('INNER',), max_physical_sources=1,
            max_scan_tables=4, cross_database_allowed=False,
            max_estimated_rows=100, max_result_rows=10,
            timeout_seconds=5, required_dialect='sqlite'),
        storage_root=str(tmp_path / 'private-host-records'),
    )
    catalog_path = tmp_path / 'registration-catalog.json'
    catalog_path.write_text(json.dumps({'sources': [{
        'source_id': 'dexa-mes-route-sample',
        'connection': connection.model_dump(mode='json'),
    }]}))
    host_path = tmp_path / 'host.json'
    host_path.write_text(json.dumps({'connections': []}))
    state_path = tmp_path / 'registrations.json'
    monkeypatch.setenv('BOI_NATIVE_QUERY_CONFIG_PATH', str(host_path))
    monkeypatch.setenv('BOI_NATIVE_QUERY_REGISTRATION_CATALOG_PATH', str(catalog_path))
    monkeypatch.setenv('BOI_NATIVE_QUERY_REGISTRATION_STORE_PATH', str(state_path))
    return intake, auth, source, state_path


def test_recipient_registers_only_server_approved_source_and_gets_private_connection(tmp_path, monkeypatch):
    intake, auth, source, state_path = registered_fixture(tmp_path, monkeypatch)
    offers = native_query.discover_native_query_registration_sources(intake, object())
    assert offers['sources'] == [{
        'source_id': 'dexa-mes-route-sample',
        'title': 'DEXA MES Route sample',
        'already_registered': False,
        'registration_scope': 'private_recipient_only',
    }]
    assert str(source) not in json.dumps(offers)

    registered = native_query.register_native_query_source(
        intake, object(), {'source_id': 'dexa-mes-route-sample'})
    assert registered['registration_status'] == 'registered'
    assert registered['registration_scope'] == 'private_recipient_only'
    assert str(source) not in json.dumps(registered)
    assert state_path.is_file()

    repeat = native_query.register_native_query_source(
        intake, object(), {'source_id': 'dexa-mes-route-sample'})
    assert repeat['registration_status'] == 'already_registered'
    authorization, _, connections = native_query.configured_native_queries(intake, object())
    assert authorization is auth and len(connections) == 1
    assert connections[0].scope.principal == auth.principal
    assert connections[0].connection_id == registered['connection_id']
    assert connections[0].sqlite_path == str(source)
    wire = json.dumps(native_query.discover_native_queries(intake, object()))
    assert str(source) not in wire and auth.principal not in wire


def test_registration_rechecks_source_use_and_current_snapshot(tmp_path, monkeypatch):
    intake, _, source, _ = registered_fixture(tmp_path, monkeypatch, allowed_uses=('store',))
    with pytest.raises(ValueError, match='NATIVE_QUERY_REGISTRATION_SOURCE_USE_DENIED'):
        native_query.discover_native_query_registration_sources(intake, object())

    intake, _, source, _ = registered_fixture(tmp_path, monkeypatch)
    native_query.register_native_query_source(intake, object(), {'source_id': 'dexa-mes-route-sample'})
    with sqlite3.connect(source) as db:
        db.execute('INSERT INTO records VALUES (3)')
    with pytest.raises(ValueError, match='NATIVE_QUERY_SOURCE_CHANGED'):
        native_query.register_native_query_source(intake, object(), {'source_id': 'dexa-mes-route-sample'})


def test_registration_request_rejects_source_paths_principals_sql_and_unapproved_sources(tmp_path, monkeypatch):
    intake, _, _, _ = registered_fixture(tmp_path, monkeypatch)
    for field in ('sqlite_path', 'principal', 'sql', 'execution_binding'):
        with pytest.raises(ValueError):
            native_query.NativeQueryRegistrationRequest.model_validate({
                'source_id': 'dexa-mes-route-sample', field: 'injected'})
    with pytest.raises(ValueError, match='NATIVE_QUERY_REGISTRATION_SOURCE_NOT_APPROVED'):
        native_query.register_native_query_source(intake, object(), {'source_id': 'not-approved'})


def test_mcp_registration_actions_use_dedicated_official_routes(monkeypatch):
    try:
        module = importlib.import_module('boi_wiki_mcp.app.v2')
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith('mcp.'):
            pytest.skip('installed MCP SDK surface is unavailable in this test interpreter')
        raise
    calls = []

    async def get(path, params=None):
        calls.append(('get', path, params))
        return {'sources': []}

    async def post(path, body):
        calls.append(('post', path, body))
        return {'connection_id': 'native-reg-fixture', 'registration_status': 'registered'}

    monkeypatch.setattr(module, 'v2_api_get', get)
    monkeypatch.setattr(module, 'v2_api_post', post)
    assert asyncio.run(module.boi_native_query('registration_discover')) == {'sources': []}
    registered = asyncio.run(module.boi_native_query('register', {
        'source_id': 'dexa-mes-route-sample'}))
    assert registered['registration_status'] == 'registered'
    assert calls == [
        ('get', '/api/v2/domain-intake/native-queries/registration-sources', None),
        ('post', '/api/v2/domain-intake/native-queries/registrations',
         {'source_id': 'dexa-mes-route-sample'}),
    ]
