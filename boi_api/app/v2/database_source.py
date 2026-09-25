"""Approved, read-only DB pages become ordinary source artifacts, not knowledge.

No caller SQL, filesystem path, credential, domain, or semantic mapping is trusted.
The same source capture/projection services used by other inputs own all evidence.
"""
from contextlib import contextmanager
import base64
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import Field, model_validator

from ..governed_runtime.semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest
from ..governed_runtime.source_field_projection import SourceFieldProjectionService
from ..governed_runtime.sqlite_source_snapshot import sealed_sqlite_digest
from ..governed_runtime.query_source_action import QuerySourceAction, QuerySourceActionBinding


class DatabaseSource(FrozenContract):
    source_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=256)
    principals: tuple[str, ...] = Field(min_length=1)
    allowed_tables: tuple[str, ...] = Field(min_length=1, max_length=64)
    sqlite_path: str | None = None
    execution_binding: QuerySourceActionBinding | None = None

    @model_validator(mode='after')
    def backend(self):
        if (self.sqlite_path is None) == (self.execution_binding is None):
            raise ValueError('DATABASE_SOURCE_EXACT_BACKEND_REQUIRED')
        if len(set(self.allowed_tables)) != len(self.allowed_tables):
            raise ValueError('DATABASE_SOURCE_DUPLICATE_TABLE')
        return self


class DatabaseSources(FrozenContract):
    sources: tuple[DatabaseSource, ...] = Field(max_length=64)


class DatabaseSourceRequest(FrozenContract):
    source_id: str = Field(min_length=1, max_length=256)
    table: str | None = Field(default=None, min_length=1, max_length=256)
    snapshot_digest: str | None = Field(default=None, pattern=r'^sha256:[0-9a-f]{64}$')
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=100, ge=1, le=1000, strict=True)


def _registry():
    path = Path(os.environ.get('BOI_DATABASE_SOURCES_PATH', '/data/database-sources.json'))
    if not path.is_file():
        return DatabaseSources(sources=())
    value = DatabaseSources.model_validate_json(path.read_bytes())
    if len({s.source_id for s in value.sources}) != len(value.sources):
        raise ValueError('DATABASE_SOURCE_DUPLICATE_ID')
    return value


def _source(source_id, principal):
    value = next((s for s in _registry().sources
                  if s.source_id == source_id and principal in s.principals), None)
    if value is None:
        raise ValueError('DATABASE_SOURCE_NOT_AUTHORIZED')
    return value


def _quote(name):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('DATABASE_SOURCE_IDENTIFIER_INVALID')
    return '"' + name.replace('"', '""') + '"'


@contextmanager
def _open(source, principal):
    if source.execution_binding:
        action = QuerySourceAction(source.execution_binding, principal=principal)
        schema = action.capture_schema(allowed_tables=source.allowed_tables)
        tables = [{'name': t.name, 'columns': [
            {'name': c.name, 'type': c.data_type, 'nullable': c.nullable}
            for c in t.columns], 'foreign_keys': [], 'relationship_status': 'not_inferred'}
            for t in schema.tables]
        yield action, source.execution_binding.source_revision, tables
        # Fresh gateway metadata response validates its pinned source/schema revision.
        action.capture_schema(allowed_tables=source.allowed_tables)
        return
    path = Path(source.sqlite_path).resolve(strict=True)
    before = sealed_sqlite_digest(path, error_prefix='DATABASE_')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        available = {r['name'] for r in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")}
        if not set(source.allowed_tables) <= available:
            raise ValueError('DATABASE_SOURCE_TABLE_UNAVAILABLE')
        tables = []
        for name in source.allowed_tables:
            columns = [dict(r) for r in connection.execute('PRAGMA table_info('+_quote(name)+')')]
            keys = [dict(r) for r in connection.execute('PRAGMA foreign_key_list('+_quote(name)+')')]
            # Do not reveal names of objects outside the granted table scope.
            keys = [r for r in keys if r['table'] in source.allowed_tables]
            tables.append({'name': name, 'columns': columns, 'foreign_keys': keys,
                           'relationship_status': 'declared_structure_not_business_identity'})
        yield connection, before, tables
        if sealed_sqlite_digest(path, error_prefix='DATABASE_') != before:
            raise ValueError('DATABASE_SOURCE_SNAPSHOT_CHANGED')
    finally:
        connection.close()


def _planner_catalog(source, principal, snapshot):
    from ..governed_runtime.semantic_query_execution import capture_sqlite_planner_catalog
    # Content-addressed observation marker, not an invented wall-clock timestamp.
    # The same sealed snapshot must yield the catalog reviewed by the author.
    kwargs={'allowed_tables':source.allowed_tables,'captured_at':'snapshot:'+snapshot}
    if source.execution_binding:
        return QuerySourceAction(source.execution_binding,principal=principal).capture_planner_catalog(**kwargs)
    return capture_sqlite_planner_catalog(Path(source.sqlite_path),source_id=source.source_id,**kwargs)


def _json_value(value):
    if isinstance(value, bytes):
        return {'storage_class': 'blob', 'hex': value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('DATABASE_SOURCE_NONFINITE_VALUE')
    return value


def database_source_call(intake, principal, request=None, *, action):
    authorization = intake._authorization(principal)
    if not {'derive', 'model_input'} <= set(authorization.allowed_uses):
        raise ValueError('DATABASE_SOURCE_READ_NOT_AUTHORIZED')
    if action == 'source_discover':
        return {'sources': [{'source_id': s.source_id, 'title': s.title,
                             'tables': list(s.allowed_tables)} for s in _registry().sources
                            if authorization.principal in s.principals],
                'read_only': True, 'semantic_status': 'not_prepared'}
    request = DatabaseSourceRequest.model_validate(request)
    source = _source(request.source_id, authorization.principal)
    if action not in ('source_schema', 'source_capture'):
        raise ValueError('DATABASE_SOURCE_ACTION_INVALID')
    if action == 'source_capture' and request.table not in source.allowed_tables:
        raise ValueError('DATABASE_SOURCE_TABLE_NOT_AUTHORIZED')
    if action == 'source_capture' and not request.snapshot_digest:
        raise ValueError('DATABASE_SOURCE_SNAPSHOT_REQUIRED')
    with _open(source, authorization.principal) as (db, snapshot, tables):
        if request.snapshot_digest and request.snapshot_digest != snapshot:
            raise ValueError('DATABASE_SOURCE_SNAPSHOT_CHANGED')
        if action == 'source_schema':
            result = {'contract_version': 'boi/database-source-schema@1',
                      'source_id': source.source_id, 'snapshot_digest': snapshot,
                      'tables': tables, 'read_only': True,
                      'planner_catalog':_planner_catalog(source,authorization.principal,snapshot).model_dump(mode='json')}
        else:
            table = next(t for t in tables if t['name'] == request.table)
            names = [c['name'] for c in table['columns']]
            if not names:
                raise ValueError('DATABASE_SOURCE_COLUMNS_REQUIRED')
            columns = ', '.join(_quote(n) for n in names)
            # A sealed snapshot plus value ordering preserves duplicate occurrences.
            # No DISTINCT and no inference that a physical row is a business entity.
            sql = 'SELECT '+columns+' FROM '+_quote(request.table)+' ORDER BY '+columns+' LIMIT ? OFFSET ?'
            fetch_limit=min(request.limit+1,source.execution_binding.max_rows) if source.execution_binding else request.limit+1
            rows = db.execute(sql, (fetch_limit, request.offset)).fetchall()
            values = [{n: _json_value(r[n]) for n in names} for r in rows]
            count = min(request.limit, len(values))
            while True:
                page = {'contract_version': 'boi/database-source-page@1',
                        'source_id': source.source_id, 'snapshot_digest': snapshot,
                        'table': request.table, 'schema': table, 'offset': request.offset,
                        'identity_basis': 'snapshot_row_ordinal',
                        'rows': [{'ordinal': request.offset+i, 'values': row}
                                 for i, row in enumerate(values[:count])]}
                raw = json.dumps(page, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
                if len(raw) <= 65536:
                    break
                if count <= 1:
                    raise ValueError('DATABASE_SOURCE_ROW_TOO_LARGE')
                count = max(1, count // 2)
            result = {'page': page, 'raw': raw, 'next_offset':
                      request.offset+count if len(values) > count or (source.execution_binding and len(values)==fetch_limit) else None}
    # Fence configuration, principal policy and source bytes before capture/return.
    if _source(source.source_id, authorization.principal) != source \
            or intake._authorization(principal) != authorization:
        raise ValueError('DATABASE_SOURCE_AUTHORIZATION_CHANGED')
    if action == 'source_schema':
        return result
    artifact = intake.source_intake.capture(authorization=authorization,
        envelope={'kind': 'inline_source', 'role': 'authoritative_document',
                  'media_type': 'application/json',
                  'content_b64': base64.b64encode(result['raw']).decode()},
        idempotency_key='database-page:'+semantic_digest(result['page']))
    reference = {k: artifact[k] for k in ('artifact_ref', 'digest', 'role')}
    reference['kind'] = 'artifact_ref'
    projector = SourceFieldProjectionService(intake.source_intake)
    manifest = projector.project(authorization=authorization, reference=reference)
    field_refs = [f['span_ref'] for f in manifest['fields']
                  if f['field_locator'].startswith('/rows/') and '/values/' in f['field_locator']]
    fields = []
    for start in range(0, len(field_refs), 128):
        fields.extend(projector.read_selected_fields(authorization=authorization,
            reference=reference, manifest_ref=manifest['manifest_ref'],
            span_refs=field_refs[start:start+128])['fields'])
    records = []
    for i, row in enumerate(result['page']['rows']):
        prefix = '/rows/%d/values/' % i
        own = []
        for field in fields:
            if not field['field_locator'].startswith(prefix):
                continue
            key = field['field_locator'][len(prefix):]
            column = key.split('/')[0].replace('~1', '/').replace('~0', '~')
            own.append({**field, 'structural_metadata': {
                'database_source': source.source_id, 'database_table': request.table,
                'database_column': column, 'database_value_path': key,
                'database_snapshot': snapshot, 'database_ordinal': row['ordinal']}})
        records.append({'record_locator': semantic_digest([source.source_id, snapshot,
            request.table, row['ordinal']]), 'fields': own, 'source': reference})
    return {'contract_version': 'boi/database-source-capture@1',
            'source_id': source.source_id, 'snapshot_digest': request.snapshot_digest,
            'table': request.table, 'offset': request.offset,
            'record_count': len(result['page']['rows']), 'next_offset': result['next_offset'],
            'source': reference, 'manifest': manifest,
            'records': records, 'source_bytes_b64':base64.b64encode(result['raw']).decode(),
            'semantic_status': 'not_prepared', 'publication_committed': False}


class DatabaseBindRequest(FrozenContract):
    source_id: str
    snapshot_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    profile_revision: RevisionRef
    review_revision: RevisionRef

DATABASE_BINDINGS = 'database_native_bindings'


def bind_database_query(intake, principal, request):
    """Connect an admitted physical Profile to an approved source, never infer it."""
    from .native_query import NativeQueryConnection, NativeReadScope, NativeQueryHost
    from ..governed_runtime.semantic_query_planner import PlanningPolicy
    request=DatabaseBindRequest.model_validate(request)
    auth,work=intake._work(principal)
    source=_source(request.source_id,auth.principal)
    if not {'derive','model_input'}<=set(auth.allowed_uses):
        raise ValueError('DATABASE_SOURCE_READ_NOT_AUTHORIZED')
    with _open(source,auth.principal) as (_,snapshot,_tables):
        if snapshot!=request.snapshot_digest:raise ValueError('DATABASE_SOURCE_SNAPSHOT_CHANGED')
        catalog=_planner_catalog(source,auth.principal,snapshot)
    identity=semantic_digest([auth.principal,request.model_dump(mode='json')])
    connection_id='database-'+identity[7:31]
    connection=NativeQueryConnection(connection_id=connection_id,title=source.title,
        sqlite_path=source.sqlite_path,execution_binding=source.execution_binding,catalog=catalog,
        profile_revision=request.profile_revision,review_revision=request.review_revision,
        scope=NativeReadScope(principal=auth.principal,
            operation='bounded_read_only_action_sqlite' if source.execution_binding else 'bounded_read_only_native_sqlite',
            source_snapshot_digest=snapshot,allowed_sources=(source.execution_binding.source_id if source.execution_binding else source.source_id,),
            allowed_tables=source.allowed_tables,max_output_rows=1000,max_scan_rows=9999,
            request_text_digest=identity,request_source='database-source-binding',production_authorized=False),
        planning_policy=PlanningPolicy(policy_id='database-bounded-read',allowed_relationship_authorities=('source',),
            allowed_join_kinds=('INNER','LEFT'),max_physical_sources=1,max_scan_tables=len(source.allowed_tables),
            cross_database_allowed=False,max_estimated_rows=9999,max_result_rows=1000,timeout_seconds=30,required_dialect='sqlite'),
        storage_root=str(Path(os.environ.get('BOI_DATABASE_QUERY_STORAGE','/data/database-query'))/identity[7:]))
    host=NativeQueryHost(work,auth,connection)
    host._read_bundle()  # Existing authority, source, Profile and physical-binding gates.
    if _source(source.source_id,auth.principal)!=source or intake._authorization(principal)!=auth:
        raise ValueError('DATABASE_SOURCE_AUTHORIZATION_CHANGED')
    key=connection_id
    prior=intake.source_intake.store.get(DATABASE_BINDINGS,key)
    if prior is None:
        from .atomic_store_contract import AtomicWrite
        row={'employee_id':auth.principal,'source_id':source.source_id,
            'source_config_digest':semantic_digest(source),'connection':connection.model_dump(mode='json')}
        if not intake.source_intake.store.atomic_compare_and_write((AtomicWrite(DATABASE_BINDINGS,key,None,row),)):
            prior=intake.source_intake.store.get(DATABASE_BINDINGS,key)
            if prior!=row:raise ValueError('DATABASE_SOURCE_BINDING_CHANGED')
    return {'connection_id':connection_id,'source_id':source.source_id,
        'profile_revision':request.profile_revision.model_dump(mode='json'),
        'review_revision':request.review_revision.model_dump(mode='json'),
        'source_snapshot_digest':snapshot,'registration_status':'already_registered' if prior else 'registered',
        'query_execution_status':'not_run'}


def database_query_connections(intake, authorization):
    from .native_query import NativeQueryConnection
    result=[];snapshots={}
    source_intake=getattr(intake,'source_intake',None)
    if source_intake is None:return ()
    for row in source_intake.store.list(DATABASE_BINDINGS,employee_id=authorization.principal,limit=10000):
        if row['connection']['scope']['principal']!=authorization.principal:continue
        try:source=_source(row['source_id'],authorization.principal)
        except ValueError:continue
        if semantic_digest(source)!=row['source_config_digest']:continue
        if source.source_id not in snapshots:
            with _open(source,authorization.principal) as (_,snapshot,_tables):
                snapshots[source.source_id]=snapshot
        if snapshots[source.source_id]!=row['connection']['scope']['source_snapshot_digest']:continue
        result.append(NativeQueryConnection.model_validate(row['connection']))
    return tuple(result)
