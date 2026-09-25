"""Transactional change journal and SQL-scoped invalidation for native queries.

The journal is server-owned, stores keys rather than bodies, and rolls back with
the write. A snapshot's active XIDs and xmax bound committed changes since that
snapshot; sequence allocation/commit order is deliberately not a watermark.
This grants no source/body authority and does not cover privileged DDL bypass or
filesystem mutation. The enclosing query retains current actor/Profile checks.
"""
from .local_bundle_checks import CHECKS
from .local_knowledge_qualification import QUALIFICATIONS
from .knowledge_prepared_postgres import TABLES, PREFIX


COLLECTIONS = ('knowledge_space_entries', 'knowledge_space_heads', 'domain_asset_heads',
               'domain_knowledge_assets', 'knowledge_publication_receipts', QUALIFICATIONS, CHECKS)
JOURNAL = 'boi_knowledge_query_changes_v1'
ROW_FUNCTION = 'boi_knowledge_query_change_row_v1'
SEAL_FUNCTION = 'boi_knowledge_query_change_seal_v1'
DENY_FUNCTION = 'boi_knowledge_query_change_deny_v1'
ROW_BODY = '''
BEGIN
 IF TG_OP='UPDATE' AND OLD.item_key IS NOT DISTINCT FROM NEW.item_key
   AND OLD.employee_id IS NOT DISTINCT FROM NEW.employee_id AND OLD.payload IS NOT DISTINCT FROM NEW.payload THEN
   RETURN NULL;
 END IF;
 IF TG_OP IN ('UPDATE','DELETE') THEN
   INSERT INTO boi_knowledge_query_changes_v1(change_xid,collection,item_key,partition,subject_id)
   VALUES(pg_current_xact_id(),TG_ARGV[0],OLD.item_key,OLD.employee_id,OLD.payload->>'stable_id');
 END IF;
 IF TG_OP='INSERT' OR (TG_OP='UPDATE' AND
   (OLD.item_key IS DISTINCT FROM NEW.item_key OR OLD.employee_id IS DISTINCT FROM NEW.employee_id
     OR OLD.payload->>'stable_id' IS DISTINCT FROM NEW.payload->>'stable_id')) THEN
   INSERT INTO boi_knowledge_query_changes_v1(change_xid,collection,item_key,partition,subject_id)
   VALUES(pg_current_xact_id(),TG_ARGV[0],NEW.item_key,NEW.employee_id,NEW.payload->>'stable_id');
 END IF;
 RETURN NULL;
END
'''
SEAL_BODY = '''
BEGIN
 INSERT INTO boi_knowledge_query_changes_v1(change_xid,collection,item_key,partition,subject_id)
 VALUES(pg_current_xact_id(),'prepared_seals',NEW.store_scope||NEW.preparation,NEW.store_scope,NULL);
 RETURN NULL;
END
'''
DENY_BODY = "BEGIN RAISE EXCEPTION 'KNOWLEDGE_QUERY_CHANGE_HISTORY_OR_TRACKED_TRUNCATE_DENIED'; END"


class KnowledgeQueryChanges:
    def __init__(self, prepared):
        self.store, self.prefix = prepared.store, prepared.prefix
        self.functions = {ROW_FUNCTION: ROW_BODY, SEAL_FUNCTION: SEAL_BODY, DENY_FUNCTION: DENY_BODY}
        self.triggers = []
        for collection in COLLECTIONS:
            table = self.store._table(collection)
            self.triggers.extend(((table, 'boi_query_change_row_v1', ROW_FUNCTION, 29, collection),
                                  (table, 'boi_query_no_truncate_v1', DENY_FUNCTION, 34, '')))
        self.triggers.extend((('boi_prepared_k_seals', 'boi_query_change_seal_v1', SEAL_FUNCTION, 5, ''),
                              (JOURNAL, 'boi_query_history_immutable_v1', DENY_FUNCTION, 27, ''),
                              (JOURNAL, 'boi_query_no_truncate_v1', DENY_FUNCTION, 34, '')))
        self.triggers.extend((PREFIX + name, 'boi_query_no_truncate_v1', DENY_FUNCTION, 34, '') for name in TABLES)
        self._initialize()

    def _initialize(self):
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/query-change-schema@1',0))")
            connection.execute('CREATE TABLE IF NOT EXISTS ' + JOURNAL + '('
                'event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,change_xid xid8 NOT NULL,'
                'collection TEXT NOT NULL,item_key TEXT NOT NULL,partition TEXT,subject_id TEXT)')
            connection.execute('CREATE INDEX IF NOT EXISTS boi_query_changes_xid_v1 ON ' + JOURNAL + '(change_xid)')
            connection.execute('CREATE INDEX IF NOT EXISTS boi_query_changes_key_v1 ON ' + JOURNAL + '(collection,item_key,change_xid)')
            connection.execute('CREATE INDEX IF NOT EXISTS boi_query_changes_partition_v1 ON ' + JOURNAL + '(collection,partition,change_xid)')
            connection.execute('CREATE INDEX IF NOT EXISTS boi_query_changes_subject_v1 ON ' + JOURNAL + '(collection,subject_id,change_xid)')
            for name, body in self.functions.items():
                if connection.execute('SELECT to_regprocedure(%s)', (name + '()',)).fetchone()[0] is None:
                    connection.execute('CREATE FUNCTION ' + name + '() RETURNS trigger LANGUAGE plpgsql AS $$' + body + '$$')
            for table, name, function, kind, argument in self.triggers:
                if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
                                          (table, name)).fetchone():
                    event = {29: 'AFTER INSERT OR UPDATE OR DELETE', 34: 'BEFORE TRUNCATE',
                             5: 'AFTER INSERT', 27: 'BEFORE UPDATE OR DELETE'}[kind]
                    mode = 'STATEMENT' if kind == 34 else 'ROW'
                    # Collection, relation and function names are fixed server constants.
                    args = "'" + argument + "'" if argument else ''
                    connection.execute(f'CREATE TRIGGER {name} {event} ON {table} FOR EACH {mode} '
                                       f'EXECUTE FUNCTION {function}({args})')
            self._ready(connection)

    def _ready(self, connection):
        for name, body in self.functions.items():
            row = connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',
                                     (name + '()',)).fetchone()
            if row != (body, 'v', False):
                raise ValueError('KNOWLEDGE_QUERY_CHANGE_TRACKING_UNAVAILABLE')
        values = ','.join(['(%s::regclass,%s::text,%s::regprocedure,%s::int,%s::bytea)'] * len(self.triggers))
        parameters = tuple(value for table, name, function, kind, argument in self.triggers
                           for value in (table, name, function + '()', kind,
                                         (argument + '\x00').encode() if argument else b''))
        valid = connection.execute('WITH expected(rel,name,func,kind,args) AS (VALUES ' + values + ') '
            "SELECT bool_and(COALESCE(t.tgenabled IN ('O','A') AND t.tgfoid=e.func AND t.tgtype=e.kind "
            'AND t.tgargs=e.args AND t.tgqual IS NULL AND NOT t.tgisinternal,FALSE)) '
            'FROM expected e LEFT JOIN pg_trigger t ON t.tgrelid=e.rel AND t.tgname=e.name', parameters).fetchone()[0]
        if not valid:
            raise ValueError('KNOWLEDGE_QUERY_CHANGE_TRACKING_UNAVAILABLE')

    def snapshot(self):
        with self.store._connection() as connection:
            self._ready(connection)
            return connection.execute('SELECT pg_current_snapshot()::text').fetchone()[0]

    def statement(self, snapshot, *, binding, profiles, purpose, historical=False):
        """Internal server SQL, also inspectable by the deployment qualifier."""
        if purpose not in ('filter', 'aggregate') or type(historical) is not bool:
            raise ValueError('KNOWLEDGE_QUERY_CHANGE_PURPOSE_INVALID')
        table, prefix = self.store._table, self.prefix
        profile_ids = [access.identity.stable_id for access in profiles.values()]
        profile_refs = [ref.ref for ref in profiles]
        # Current membership is sufficient to locate the query's keys: removing
        # a member itself emits a partition event, so it cannot hide its removal
        # by disappearing from this post-read relation. New members are covered
        # regardless of whether a prior result used them or had any hits.
        sql = f'''WITH members AS MATERIALIZED (
 SELECT payload->>'stable_id' AS id,payload->'content_revision'->>'ref' AS revision
 FROM {table('knowledge_space_entries')} WHERE employee_id=%s AND left(item_key,%s)=%s
), preparations AS MATERIALIZED (
 SELECT o.store_scope,o.preparation FROM boi_prepared_k_objects o JOIN members m
 ON o.stable_id=m.id AND o.revision=m.revision WHERE o.store_scope=%s
), dependencies AS MATERIALIZED (
 SELECT d.stable_id,d.revision FROM boi_prepared_k_dependencies d JOIN preparations p USING(store_scope,preparation)
), native_ids AS (
 SELECT id FROM members UNION SELECT stable_id FROM dependencies UNION SELECT unnest(%s::text[])
), native_refs AS (
 SELECT revision FROM members UNION SELECT revision FROM dependencies UNION SELECT unnest(%s::text[])
), uses AS MATERIALIZED (
 SELECT k.qualification_key,k.check_key FROM boi_prepared_k_uses k
 JOIN preparations p USING(store_scope,preparation) WHERE k.purpose=%s
)
'''
        # Keep each indexed key/partition condition next to its temporal test.
        # Materializing all later changes first scans unrelated tenant history
        # and may spill even when this population has no changed dependencies.
        conditions = [
            ("c.collection='knowledge_space_entries' AND left(c.item_key,%s)=%s AND c.partition=%s",
             (len(prefix), prefix, binding['partition'])),
            ("c.collection='knowledge_space_entries' AND left(c.item_key,%s)=%s "
             'AND c.subject_id IN (SELECT id FROM native_ids)', (len(prefix), prefix)),
            ("c.collection IN ('knowledge_space_heads','domain_asset_heads') "
             'AND c.item_key IN (SELECT %s || id FROM native_ids)', (prefix,)),
            ("c.collection='domain_knowledge_assets' AND c.item_key IN (SELECT %s || revision FROM native_refs)", (prefix,)),
            (f'''c.collection='knowledge_publication_receipts' AND c.item_key IN (
   SELECT %s || ((h.payload->>'query_policy_wire')::jsonb->>'publication_manifest_digest')
   FROM {table('knowledge_space_heads')} h JOIN native_ids i ON h.item_key=%s || i.id)''', (prefix, prefix)),
        ]
        if not historical:
            conditions.extend([
                ('c.collection=%s AND c.item_key IN (SELECT %s || qualification_key FROM uses)', (QUALIFICATIONS, prefix)),
                ('c.collection=%s AND c.item_key IN (SELECT %s || check_key FROM uses)', (CHECKS, prefix)),
                ("c.collection='prepared_seals' AND c.item_key IN (SELECT store_scope || preparation FROM preparations)", ()),
            ])
        recent = '(c.change_xid>=pg_snapshot_xmax(%s::pg_snapshot) OR '
        recent += 'c.change_xid IN (SELECT pg_snapshot_xip(%s::pg_snapshot)))'
        branches, parameters = [], [binding['partition'], len(prefix), prefix, prefix, profile_ids, profile_refs, purpose]
        for condition, values in conditions:
            branches.append(f'SELECT 1 FROM {JOURNAL} c WHERE ({condition}) AND {recent}')
            parameters.extend((*values, snapshot, snapshot))
        return sql + 'SELECT NOT EXISTS (' + ' UNION ALL '.join(branches) + ')', tuple(parameters)

    def unchanged(self, snapshot, *, binding, profiles, purpose, historical=False):
        sql, parameters = self.statement(snapshot, binding=binding, profiles=profiles, purpose=purpose,
                                         historical=historical)
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            self._ready(connection)
            return bool(connection.execute(sql, parameters).fetchone()[0])
