"""Sealed sparse query memberships; counts never store per-member results.

Known states are materialized by INSERT SELECT in the database. Unknown pages
use the unchanged server population minus saved known membership; no assertion
evaluation or full unknown-ID copy is needed to read them. Authority remains in
the enclosing protected service and its current observation fence.
"""
import json
from datetime import datetime, timezone
import time

from .knowledge_evidence_set_sql import STATES
from .knowledge_prepared_postgres import wire
from .semantic_binding_contract import semantic_digest
from .knowledge_saved_witness_sql import VERSION as WITNESS_VERSION, witness_ctes


ROOT = 'boi_saved_k_'
VERSION = 'boi/sparse-knowledge-result@1'
GUARD = 'boi_saved_k_guard_v1'
GUARD_BODY = '''
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'KNOWLEDGE_SAVED_SET_IMMUTABLE'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.store_scope||NEW.execution_id,0));
 IF EXISTS(SELECT 1 FROM boi_saved_k_seals WHERE store_scope=NEW.store_scope AND execution_id=NEW.execution_id) THEN
   RAISE EXCEPTION 'KNOWLEDGE_SAVED_SET_SEALED';
 END IF;
 RETURN NEW;
END
'''


class KnowledgeSavedSets:
    def __init__(self, prepared):
        self.store, self.prefix = prepared.store, prepared.prefix
        self._initialize()

    def _initialize(self):
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/saved-knowledge-query-schema@1',0))")
            connection.execute('''CREATE TABLE IF NOT EXISTS boi_saved_k_headers(
 store_scope TEXT NOT NULL,execution_id TEXT NOT NULL,actor_id TEXT NOT NULL,query_digest TEXT NOT NULL,
 operation TEXT NOT NULL,PRIMARY KEY(store_scope,execution_id));
CREATE TABLE IF NOT EXISTS boi_saved_k_members(
 store_scope TEXT NOT NULL,execution_id TEXT NOT NULL,id TEXT NOT NULL,revision TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('supported','refuted','conflicted')),
 PRIMARY KEY(store_scope,execution_id,id),
 FOREIGN KEY(store_scope,execution_id) REFERENCES boi_saved_k_headers(store_scope,execution_id));
CREATE INDEX IF NOT EXISTS boi_saved_k_state_page ON boi_saved_k_members(store_scope,execution_id,state,id COLLATE "C");
CREATE TABLE IF NOT EXISTS boi_saved_k_seals(
 store_scope TEXT NOT NULL,execution_id TEXT NOT NULL,receipt_wire TEXT NOT NULL,receipt_digest TEXT NOT NULL,
 PRIMARY KEY(store_scope,execution_id),
 FOREIGN KEY(store_scope,execution_id) REFERENCES boi_saved_k_headers(store_scope,execution_id));
CREATE TABLE IF NOT EXISTS boi_saved_k_witnesses(
 store_scope TEXT NOT NULL,execution_id TEXT NOT NULL,id TEXT NOT NULL,
 detail_key TEXT NOT NULL,detail_wire TEXT NOT NULL,
 PRIMARY KEY(store_scope,execution_id,id,detail_key),
 FOREIGN KEY(store_scope,execution_id) REFERENCES boi_saved_k_headers(store_scope,execution_id));''')
            if connection.execute('SELECT to_regprocedure(%s)', (GUARD + '()',)).fetchone()[0] is None:
                connection.execute('CREATE FUNCTION ' + GUARD + '() RETURNS trigger LANGUAGE plpgsql AS $$' + GUARD_BODY + '$$')
            for suffix in ('headers', 'members', 'seals', 'witnesses'):
                table = ROOT + suffix
                for name, event, mode in (('boi_saved_k_immutable', 'INSERT OR UPDATE OR DELETE', 'ROW'),
                                          ('boi_saved_k_no_truncate', 'TRUNCATE', 'STATEMENT')):
                    if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
                                              (table, name)).fetchone():
                        connection.execute(f'CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH {mode} '
                                           f'EXECUTE FUNCTION {GUARD}()')
            self._ready(connection)

    def _ready(self, connection):
        function = connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',
                                      (GUARD + '()',)).fetchone()
        if function != (GUARD_BODY, 'v', False):
            raise ValueError('KNOWLEDGE_SAVED_SET_GUARD_UNAVAILABLE')
        expected = [(ROOT + suffix, name, kind) for suffix in ('headers', 'members', 'seals', 'witnesses')
                    for name, kind in (('boi_saved_k_immutable', 31), ('boi_saved_k_no_truncate', 34))]
        values = ','.join(['(%s::regclass,%s::text,%s::int)'] * len(expected))
        row = connection.execute('WITH expected(rel,name,kind) AS (VALUES ' + values + ') '
            "SELECT bool_and(COALESCE(t.tgenabled IN ('O','A') AND t.tgtype=e.kind AND t.tgfoid=%s::regprocedure "
            "AND t.tgqual IS NULL AND t.tgargs=''::bytea,FALSE)) FROM expected e LEFT JOIN pg_trigger t "
            'ON t.tgrelid=e.rel AND t.tgname=e.name', (*[v for item in expected for v in item], GUARD + '()')).fetchone()
        if row != (True,):
            raise ValueError('KNOWLEDGE_SAVED_SET_GUARD_UNAVAILABLE')

    def materialize(self, *, execution_id, actor_id, query, relation, compiled, page=None,
                    recovery_binding=None, clock=time.time):
        if page is not None:
            raise ValueError('KNOWLEDGE_SAVED_SET_INITIAL_PAGE_UNSUPPORTED')
        if recovery_binding is not None and (not isinstance(recovery_binding, str)
                or len(recovery_binding) != 71 or not recovery_binding.startswith('sha256:')
                or any(c not in '0123456789abcdef' for c in recovery_binding[7:])):
            raise ValueError('KNOWLEDGE_SAVED_SET_RECOVERY_BINDING_INVALID')
        counts = ' UNION ALL '.join(f"SELECT '{state}' AS state,COUNT(*) AS count FROM boi_{state}" for state in STATES)
        ctes = [relation.ctes, *compiled.evidence.ctes]
        parameters = [*relation.parameters, *compiled.parameters]
        if query.operation == 'select_objects':
            known = ' UNION ALL '.join(f"SELECT id,'{state}' AS state FROM boi_{state}" for state in STATES[:-1])
            ctes.append('boi_save_known AS (INSERT INTO boi_saved_k_members '
                'SELECT DISTINCT %s::text,%s::text,k.id,p.revision,k.state FROM (' + known + ') k '
                'JOIN boi_prepared p ON p.stable_id=k.id RETURNING id)')
            parameters.extend((self.prefix, execution_id))
            inserted = '(SELECT COUNT(*) FROM boi_save_known)'
        else:
            inserted = '0'
        keep_witnesses = compiled.statement_query and query.operation == 'select_objects'
        witness_count = '0'
        if keep_witnesses:
            ctes.extend(witness_ctes(query, compiled))
            ctes.append('boi_save_witnesses AS (INSERT INTO boi_saved_k_witnesses '
                'SELECT %s::text,%s::text,d.object_id,'
                'jsonb_build_array(d.witness_id,d.atom,d.fact_key)::text,row_to_json(d)::text '
                'FROM boi_trace_details d RETURNING id)')
            parameters.extend((self.prefix, execution_id))
            witness_count = '(SELECT COUNT(*) FROM boi_save_witnesses)'
        ctes.append('boi_save_counts AS (' + counts + ')')
        statement = ('WITH RECURSIVE ' + ',\n'.join(ctes) + ' SELECT pg_current_snapshot()::text,'
            '(SELECT row_to_json(c) FROM boi_coverage c),(SELECT json_agg(r) FROM boi_save_counts r),'
            + inserted + ',' + witness_count)
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            self._ready(connection)
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (self.prefix + execution_id,))
            connection.execute('INSERT INTO boi_saved_k_headers VALUES(%s,%s,%s,%s,%s)',
                               (self.prefix, execution_id, actor_id, semantic_digest(query), query.operation))
            snapshot, coverage, rows, member_count, detail_count = connection.execute(statement, tuple(parameters)).fetchone()
            counted = {row['state']: int(row['count']) for row in rows}
            expected = sum(counted[state] for state in STATES[:-1]) if query.operation == 'select_objects' else 0
            if member_count != expected:
                raise ValueError('KNOWLEDGE_SAVED_SET_COUNT_MISMATCH')
            receipt = {'contract_version': VERSION, 'store_scope': self.prefix, 'execution_id': execution_id,
                'actor_id': actor_id, 'query_digest': semantic_digest(query), 'operation': query.operation,
                'counts': counted, 'coverage': coverage, 'statement_snapshot': snapshot,
                'stored_member_count': int(member_count), 'unknown_members_materialized': False}
            if keep_witnesses:
                receipt['statement_witnesses'] = {'contract_version':WITNESS_VERSION,
                    'stored_detail_count':int(detail_count), 'statement_digest':semantic_digest(statement),
                    'query_reexecution':False}
            if recovery_binding is not None:
                receipt.update(recovery_binding=recovery_binding,
                    completed_at=datetime.fromtimestamp(clock(), timezone.utc).isoformat())
            connection.execute('INSERT INTO boi_saved_k_seals VALUES(%s,%s,%s,%s)',
                (self.prefix, execution_id, wire(receipt), semantic_digest(receipt)))
        return snapshot, coverage, rows

    def witnesses(self, *, execution_id, object_id, limit, after_key=None):
        """Read immutable trace rows; the caller revalidates result authority."""
        if (not isinstance(object_id, str) or not 1 <= len(object_id) <= 2048
                or type(limit) is not int or not 1 <= limit <= 100
                or (after_key is not None and (not isinstance(after_key, str) or not 1 <= len(after_key) <= 4096))):
            raise ValueError('KNOWLEDGE_RESULT_WITNESS_PAGE_INVALID')
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            self._ready(connection)
            member = connection.execute('SELECT revision,state FROM boi_saved_k_members '
                'WHERE store_scope=%s AND execution_id=%s AND id=%s',
                (self.prefix, execution_id, object_id)).fetchone()
            if member is None:
                raise ValueError('KNOWLEDGE_RESULT_WITNESS_MEMBER_REQUIRED')
            sql = 'SELECT detail_key,detail_wire FROM boi_saved_k_witnesses '
            sql += 'WHERE store_scope=%s AND execution_id=%s AND id=%s'
            parameters = [self.prefix, execution_id, object_id]
            if after_key is not None:
                sql += ' AND detail_key COLLATE "C">%s'
                parameters.append(after_key)
            sql += ' ORDER BY detail_key COLLATE "C" LIMIT %s'
            parameters.append(limit+1)
            rows = [{'detail_key':key, **json.loads(raw)} for key, raw in connection.execute(sql, parameters).fetchall()]
            if any(row['object_id'] != object_id or row['revision'] != member[0] for row in rows):
                raise ValueError('KNOWLEDGE_RESULT_WITNESS_BINDING_INVALID')
            return rows

    def receipt(self, execution_id):
        with self.store._connection() as connection:
            self._ready(connection)
            row = connection.execute('SELECT s.receipt_wire,s.receipt_digest,h.actor_id,h.query_digest,h.operation '
                'FROM boi_saved_k_seals s JOIN boi_saved_k_headers h USING(store_scope,execution_id) '
                'WHERE store_scope=%s AND execution_id=%s', (self.prefix, execution_id)).fetchone()
        if row is None:
            raise ValueError('KNOWLEDGE_SAVED_SET_UNAVAILABLE')
        value = json.loads(row[0])
        if (semantic_digest(value) != row[1] or value.get('contract_version') != VERSION
                or value.get('store_scope') != self.prefix or value.get('execution_id') != execution_id
                or (value.get('actor_id'), value.get('query_digest'), value.get('operation')) != row[2:]):
            raise ValueError('KNOWLEDGE_SAVED_SET_RECEIPT_CHANGED')
        return value

    def page(self, *, execution_id, group, limit, after_key, relation=None, query=None):
        if group not in (*STATES, 'all', 'reported') or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('KNOWLEDGE_RESULT_PAGE_INVALID')
        if after_key is not None and (not isinstance(after_key, str) or not 1 <= len(after_key) <= 2048):
            raise ValueError('KNOWLEDGE_RESULT_PAGE_INVALID')
        parameters = []
        if group in ('unknown', 'all'):
            if relation is None or query is None:
                raise ValueError('KNOWLEDGE_RESULT_POPULATION_REQUIRED')
            sql = 'WITH RECURSIVE ' + relation.ctes + ', saved_population AS ('
            sql += 'SELECT DISTINCT p.stable_id AS id,p.revision FROM boi_prepared p JOIN boi_u u ON u.id=p.stable_id), '
            sql += "saved_page AS (SELECT u.id,u.revision,COALESCE(m.state,'unknown') AS state FROM saved_population u "
            sql += 'LEFT JOIN boi_saved_k_members m ON m.store_scope=%s AND m.execution_id=%s AND m.id=u.id'
            if group == 'unknown': sql += ' WHERE m.id IS NULL'
            sql += ') SELECT id,revision,state FROM saved_page'
            parameters.extend((*relation.parameters, self.prefix, execution_id))
        else:
            sql = 'SELECT id,revision,state FROM boi_saved_k_members WHERE store_scope=%s AND execution_id=%s AND '
            if group == 'reported':
                sql += 'state IN (%s,%s)'
                parameters.extend((self.prefix, execution_id, 'supported', 'conflicted'))
            else:
                sql += 'state=%s'
                parameters.extend((self.prefix, execution_id, group))
        if after_key is not None:
            sql += (' WHERE' if group in ('unknown', 'all') else ' AND') + ' id COLLATE "C">%s'
            parameters.append(after_key)
        sql += ' ORDER BY id COLLATE "C" LIMIT %s'
        parameters.append(limit + 1)
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            self._ready(connection)
            return [{'id': row[0], 'revision': row[1], 'state': row[2]}
                    for row in connection.execute(sql, tuple(parameters)).fetchall()]
