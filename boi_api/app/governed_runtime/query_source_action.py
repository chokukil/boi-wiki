"""Server-owned source binding through the registered Action Gateway.

The planner/compiler owns SQL. This adapter owns transport and verifies the
source revision on each API transaction; it never opens a database file.
"""
import json
import hashlib
import math
import os
from pathlib import Path
from typing import Literal
import uuid

import httpx
from pydantic import Field
from .semantic_binding_contract import FrozenContract, Ref, Digest, semantic_digest


class QuerySourceActionBinding(FrozenContract):
    contract_version: Literal['boi/query-source-action@1'] = 'boi/query-source-action@1'
    source_id: Ref
    description: Ref
    action_key: Ref
    action_revision: Digest
    dialect: Literal['sqlite']
    response_contract: Literal['dexa/sqlite-result@1']
    source_revision: Digest
    schema_revision: Digest
    metadata_operation: Ref = 'metadata'
    query_operation: Ref = 'query'
    max_rows: int = Field(ge=1, le=1000, strict=True)
    timeout_seconds: float = Field(gt=0, le=30)
    source_freshness: Literal['unknown'] = 'unknown'
    source_authority: Literal['unknown'] = 'unknown'


def decode_sqlite_cell(cell):
    """Decode the declared lossless SQLite cell wire contract, fail closed."""
    if cell is None or type(cell) is str:
        return cell
    if type(cell) is int and abs(cell) <= 9007199254740991:
        return cell
    if type(cell) is not dict or set(cell) != {'type', 'value'} or type(cell['value']) is not str:
        raise ValueError('QUERY_SOURCE_CELL_ENCODING_INVALID')
    tag, text = cell['type'], cell['value']
    try:
        if tag == 'real':
            value = float.fromhex(text)
            if not math.isfinite(value) or value.hex() != text:
                raise ValueError()
            return value
        if tag == 'int64':
            value = int(text)
            if str(value) != text or not -(2**63) <= value < 2**63:
                raise ValueError()
            return value
    except (ValueError, OverflowError):
        raise ValueError('QUERY_SOURCE_CELL_ENCODING_INVALID') from None
    raise ValueError('QUERY_SOURCE_CELL_ENCODING_UNSUPPORTED')


class ApiRow(dict):
    # SQLite rows iterate values, while dict(row) uses keys. Preserve both
    # compiler conventions without inventing a local SQLite mirror.
    def __iter__(self):
        return iter(self.values())

    def __getitem__(self, key):
        return tuple(self.values())[key] if type(key) is int else super().__getitem__(key)


class ApiCursor:
    def __init__(self, columns, rows, *, sqlite_types_preserved=False):
        self.sqlite_types_preserved = sqlite_types_preserved
        names = [c['name'] for c in columns]
        if len(names) != len(set(names)) or any(len(r) != len(names) for r in rows):
            raise ValueError('QUERY_SOURCE_RESULT_COLUMNS_INVALID')
        self.rows = [ApiRow(zip(names, r)) for r in rows]

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class QuerySourceAction:
    def __init__(self, binding, *, principal, transport=None, evidence_sink=None):
        self.binding = QuerySourceActionBinding.model_validate(binding)
        self.principal = principal
        self.transport = transport
        self.evidence_sink = evidence_sink
        self.receipts = []

    def _send(self, request):
        url = os.environ.get('ACTION_GATEWAY_URL', '').rstrip('/')
        token_path = os.environ.get('ACTION_GATEWAY_TOKEN_FILE')
        token = (Path(token_path).read_text().strip() if token_path else
            os.environ.get('ACTION_GATEWAY_SERVICE_TOKEN') or os.environ.get('BOI_API_SERVICE_TOKEN'))
        if not url or not token:
            raise ValueError('QUERY_SOURCE_GATEWAY_NOT_CONFIGURED')
        try:
            with httpx.Client(timeout=self.binding.timeout_seconds, follow_redirects=False) as client:
                with client.stream('POST', url+'/api/actions/invoke',
                    headers={'x-service-token': token}, json=request) as response:
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if len(raw)+len(chunk)>2*1024*1024:
                            raise ValueError('QUERY_SOURCE_RESPONSE_SIZE_LIMIT')
                        raw.extend(chunk)
                    value = json.loads(raw)
                    if response.status_code != 200:
                        # Only these declared Gateway diagnostics are safe to
                        # expose. Arbitrary remote error text can contain data.
                        code = value.get('detail') if isinstance(value,dict) else None
                        safe = {'ACTION_REVISION_CHANGED','ACTION_OPERATION_UNSUPPORTED',
                            'ACTION_TRANSPORT_TIMEOUT_OUTCOME_UNKNOWN','ACTION_TRANSPORT_FAILED_OUTCOME_UNKNOWN',
                            'ACTION_INPUT_SCHEMA_INVALID','ACTION_SERVICE_CREDENTIAL_UNAVAILABLE',
                            'ACTION_RESPONSE_SIZE_LIMIT','ACTION_ENDPOINT_NOT_ALLOWED'}
                        raise ValueError(code if code in safe else 'QUERY_SOURCE_GATEWAY_FAILED')
                    return value
        except (httpx.HTTPError, json.JSONDecodeError):
            raise ValueError('QUERY_SOURCE_TRANSPORT_OUTCOME_UNKNOWN') from None

    def call(self, operation, **payload):
        b = self.binding
        request = {'action_key':b.action_key, 'expected_action_revision':b.action_revision,
            'employee_id':self.principal, 'dry_run':False,
            'idempotency_key':str(uuid.uuid4()),
            'payload':{'operation':operation, 'source_id':b.source_id, **payload}}
        attempt = {'contract_version':'boi/query-source-attempt@1', 'principal':self.principal,
            'source_binding':b.model_dump(mode='json'), 'request':request}
        if self.evidence_sink:
            self.evidence_sink({**attempt,'status':'dispatching'})
        try:
            result = (self.transport or self._send)(request)
        except ValueError as exc:
            # Keep an interrupted/failed Action dispatch durable, separately
            # from the whole business execution's prepared marker.
            code=str(exc)
            known_rejected={'ACTION_REVISION_CHANGED','ACTION_OPERATION_UNSUPPORTED',
                'ACTION_INPUT_SCHEMA_INVALID','ACTION_SERVICE_CREDENTIAL_UNAVAILABLE','ACTION_ENDPOINT_NOT_ALLOWED'}
            if self.evidence_sink:
                self.evidence_sink({**attempt, 'status':'rejected' if code in known_rejected else 'unknown',
                    'reason_code':code if code in known_rejected else 'QUERY_SOURCE_TRANSPORT_OUTCOME_UNKNOWN'})
            raise
        if (result.get('action_key') != b.action_key or result.get('action_revision') != b.action_revision
            or result.get('request_id') != request['idempotency_key']
            or result.get('operation') != operation or result.get('read_only') is not True):
            raise ValueError('QUERY_SOURCE_ACTION_RESPONSE_MISMATCH')
        response = result.get('response', {})
        if result.get('response_digest') != semantic_digest(response):
            raise ValueError('QUERY_SOURCE_RESPONSE_DIGEST_MISMATCH')
        # The API authentication middleware rejects before the query envelope.
        # Recognize only its exact public denial, after Gateway/digest checks.
        authentication_denied = (result.get('http_status') == 401 and result.get('ok') is False
            and response == {'status':'denied','error':{'code':'AUTHENTICATION_REQUIRED'}})
        if response.get('contract_version') != b.response_contract and not authentication_denied:
            raise ValueError('QUERY_SOURCE_RESPONSE_CONTRACT_MISMATCH')
        record = {'contract_version':'boi/query-source-call@1',
            'source_binding':b.model_dump(mode='json'), 'principal':self.principal,
            'request':request, 'response':result}
        receipt = {k:result.get(k) for k in ('request_id','action_key','action_revision',
            'query_id','query_status','http_status','response_digest')}
        if self.evidence_sink:
            receipt['protected_call_ref']='protected:query-source-call:'+self.evidence_sink(record)
        self.receipts.append(receipt)
        if authentication_denied:
            raise ValueError('QUERY_SOURCE_API_AUTHENTICATION_REQUIRED')
        if response.get('status') != 'success' or result.get('ok') is not True:
            code = (response.get('error') or {}).get('code')
            known = {'QUERY_TIMEOUT','SOURCE_NOT_AUTHORIZED','SOURCE_UNAVAILABLE','SOURCE_REVISION_CHANGED',
                'SCHEMA_REVISION_CHANGED','READ_ONLY_QUERY_REQUIRED','SQLITE_ERROR','SQLITE_AUTH',
                'SQLITE_BUSY','CONCURRENCY_LIMIT','INVALID_REQUEST','QUERY_EXECUTION_ERROR'}
            raise ValueError('QUERY_SOURCE_'+code if code in known else 'QUERY_SOURCE_API_FAILED')
        source = response.get('source', {})
        if (source.get('source_id') != b.source_id or source.get('source_revision') != b.source_revision
            or source.get('schema_revision') != b.schema_revision or source.get('dialect') != b.dialect):
            raise ValueError('QUERY_SOURCE_REVISION_CHANGED')
        return response

    def capture_schema(self, *, allowed_tables):
        from .multi_result_query_gateway import MultiResultSqliteSchema, MultiResultSqliteTable, MultiResultSqliteColumn, _digest
        value = self.call(self.binding.metadata_operation)
        schema = value.get('schema')
        # The API schema contract uses JSON ASCII escaping, independently of
        # BoI's UTF-8 canonical object digest. Preserve that declared encoding.
        api_digest = 'sha256:'+hashlib.sha256(json.dumps(schema,sort_keys=True,
            separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        if not isinstance(schema, list) or api_digest != self.binding.schema_revision:
            raise ValueError('QUERY_SOURCE_SCHEMA_DIGEST_MISMATCH')
        available = {t['name']:t for t in schema}
        if len(available) != len(schema) or not allowed_tables or not set(allowed_tables)<=available.keys():
            raise ValueError('NATIVE_QUERY_TABLE_UNAVAILABLE')
        tables = tuple(MultiResultSqliteTable(name=name, columns=tuple(MultiResultSqliteColumn(
            # Ordinary SQLite TEXT PRIMARY KEY columns can contain NULL. Keep
            # the declared NOT NULL flag; prove actual key quality separately.
            name=c['name'], data_type=c['type'].casefold(), nullable=not c['not_null'],
            primary_key=bool(c['pk'])) for c in available[name]['columns'] if c['hidden']==0))
            for name in sorted(allowed_tables))
        return MultiResultSqliteSchema(allowed_tables=tuple(sorted(allowed_tables)),tables=tables,
            schema_digest=_digest(tuple(t.model_dump(mode='json') for t in tables)),
            source_snapshot_digest=self.binding.source_revision)

    def execute(self, sql, params=()):
        value = self.call(self.binding.query_operation, sql=sql, params=params,
            limit=self.binding.max_rows, expected_source_revision=self.binding.source_revision,
            expected_schema_revision=self.binding.schema_revision)
        if value.get('truncated') is not False:
            raise ValueError('QUERY_SOURCE_RESULT_TRUNCATED')
        rows, columns = value.get('rows'), value.get('columns')
        if not isinstance(rows,list) or not isinstance(columns,list) or value.get('returned_count')!=len(rows):
            raise ValueError('QUERY_SOURCE_RESULT_SHAPE_INVALID')
        typed = value.get('cell_encoding') == 'sqlite_typed_json_v2'
        if typed:
            rows = [[decode_sqlite_cell(c) for c in row] for row in rows]
        elif any(isinstance(c,(dict,list)) for row in rows for c in row):
            raise ValueError('QUERY_SOURCE_CELL_ENCODING_UNSUPPORTED')
        return ApiCursor(columns, rows, sqlite_types_preserved=typed)

    def capture_planner_catalog(self, *, allowed_tables, captured_at):
        """Project pinned API metadata conservatively; never inspect a local DB.

        The API does not report secondary indexes or rowid-alias flags. Only a
        single declared primary key is marked unique, and nullability follows
        the reported NOT NULL flag. Actual key integrity is measured separately.
        CURRENT describes this metadata read, not the business data's age.
        """
        from .semantic_query_execution import _sqlite_type, _SUPPORTED_OPERATORS
        from .semantic_query_planner import (
            PlannerCatalogColumn, PlannerCatalogTable, PlannerCatalogSource,
            PlannerCatalogSnapshot,
        )
        schema = self.capture_schema(allowed_tables=allowed_tables)
        tables = []
        for table in schema.tables:
            primary = [column.name for column in table.columns if column.primary_key]
            count = self.execute('SELECT COUNT(*) AS row_count FROM "'+
                table.name.replace('"', '""')+'"').fetchone()['row_count']
            if type(count) is not int or count < 0:
                raise ValueError('QUERY_SOURCE_COUNT_INVALID')
            tables.append(PlannerCatalogTable(name=table.name, estimated_rows=count,
                columns=tuple(PlannerCatalogColumn(name=column.name,
                    data_type=_sqlite_type(column.data_type), nullable=column.nullable,
                    primary_key=column.primary_key,
                    unique=len(primary) == 1 and column.name == primary[0])
                    for column in table.columns)))
        source = PlannerCatalogSource(source_id=self.binding.source_id,
            backend='sqlite', read_only=True, tables=tuple(tables))
        values = dict(schema_digest=semantic_digest({
            'source_id':source.source_id, 'tables':[{'name':table.name,
                'columns':[column.model_dump(mode='json') for column in table.columns]}
                for table in tables]}),
            capability_digest=semantic_digest({'backend':'sqlite', 'dialects':['sqlite'],
                'operators':list(_SUPPORTED_OPERATORS), 'read_only':True}),
            captured_at=captured_at, freshness_status='CURRENT',
            supported_dialects=('sqlite',), supported_operators=_SUPPORTED_OPERATORS,
            sources=(source,))
        return PlannerCatalogSnapshot(snapshot_digest=semantic_digest({**values,
            'sources':[source.model_dump(mode='json')]}), **values)

    def check_scope_binding(self, scope, *, principal):
        """Check the immutable request binding without dispatching a source read."""
        if principal != scope.principal:
            raise ValueError('NATIVE_QUERY_PRINCIPAL_MISMATCH')
        if (scope.source_snapshot_digest != self.binding.source_revision
            or tuple(scope.allowed_sources)!=(self.binding.source_id,)):
            raise ValueError('NATIVE_QUERY_SOURCE_CHANGED')

    def check_scope(self, scope, *, principal):
        self.check_scope_binding(scope, principal=principal)
        total = 0
        # Every query response verifies the pinned source and schema revisions.
        # The count query also fails if any scoped table disappeared, so a
        # separate metadata dispatch here adds no current-scope guarantee.
        # Bounded scalar subqueries avoid one request per table and SQLite's
        # compound-SELECT limit.
        for offset in range(0, len(scope.allowed_tables), 100):
            tables = scope.allowed_tables[offset:offset + 100]
            terms = ['(SELECT COUNT(*) FROM "' + name.replace('"', '""') + '")'
                for name in tables]
            count = self.execute('SELECT ' + ' + '.join(terms) + ' AS row_count').fetchone()['row_count']
            if type(count) is not int or count<0:
                raise ValueError('QUERY_SOURCE_COUNT_INVALID')
            total+=count
            if total>scope.max_scan_rows:
                raise ValueError('NATIVE_QUERY_SCAN_BUDGET_EXCEEDED')

    def open_session(self, progress):
        return PinnedApiSession(self, progress)


class PinnedApiSession:
    """Each statement has its own API transaction pinned to the same revision.

    This is deliberately not advertised as one remote database transaction.
    A changed source aborts the composed result. No automatic retries/fallback.
    """
    def __init__(self, source, progress):
        self.source, self.progress = source, progress

    def execute(self, sql, parameters=()):
        if self.progress():
            raise ValueError('QUERY_SOURCE_EXECUTION_INTERRUPTED')
        return self.source.execute(sql, parameters)

    def commit(self):
        pass  # Each API response already completed its pinned read transaction.

    def close(self):
        pass  # No client database or long-lived API transaction to close.
