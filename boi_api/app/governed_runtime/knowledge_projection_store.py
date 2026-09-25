"""Disposable, generation-bound SQLite index. No ACL or semantic authority.

Only the publication service chooses visible generations and authorizes readers.
All writes, including undo, take a namespace fencing token inside BEGIN IMMEDIATE.
The original native ledger and objects remain the source for rebuilding this file.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from .knowledge_projection_contract import ProjectionBatch, ProjectionPublication, ProjectionScalar, definition_key
from .semantic_binding_contract import semantic_digest


SCHEMA_VERSION = 1


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class ProjectionSnapshot:
    scope_id: str
    generation: int
    manifest_digest: str | None


SCHEMA = """
CREATE TABLE namespace_guards(scope TEXT PRIMARY KEY, token INTEGER NOT NULL);
CREATE TABLE projection_generations(
 scope TEXT NOT NULL, generation INTEGER NOT NULL, base_generation INTEGER NOT NULL,
 manifest_digest TEXT NOT NULL, operation_id TEXT NOT NULL, batch_digest TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('prepared','committed','aborted')),
 receipt TEXT NOT NULL, PRIMARY KEY(scope,generation), UNIQUE(scope,manifest_digest));
CREATE TABLE object_versions(
 id INTEGER PRIMARY KEY, scope TEXT NOT NULL, stable_id TEXT NOT NULL,
 generation_from INTEGER NOT NULL, generation_until INTEGER,
 object_type TEXT NOT NULL, revision TEXT NOT NULL, readiness TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(scope,stable_id,generation_from));
CREATE INDEX objects_identity ON object_versions(scope,stable_id,generation_from,generation_until);
CREATE INDEX objects_type ON object_versions(scope,object_type,generation_from,generation_until,stable_id);
CREATE INDEX objects_revision ON object_versions(scope,revision);
CREATE INDEX objects_coverage ON object_versions(scope,readiness,generation_from,generation_until);
CREATE TABLE predicate_definitions(scope TEXT NOT NULL, revision TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(scope,revision));
CREATE TABLE assertions(
 id INTEGER PRIMARY KEY, object_id INTEGER NOT NULL REFERENCES object_versions(id) ON DELETE CASCADE,
 scope TEXT NOT NULL, fact_id TEXT NOT NULL, predicate TEXT NOT NULL, kind TEXT NOT NULL,
 text_value TEXT, decimal_value TEXT COLLATE BOI_DECIMAL, boolean_value INTEGER,
 polarity TEXT NOT NULL, modality TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(object_id,fact_id));
CREATE INDEX property_text ON assertions(scope,predicate,kind,text_value,polarity,object_id);
CREATE INDEX property_decimal ON assertions(scope,predicate,kind,decimal_value COLLATE BOI_DECIMAL,polarity,object_id);
CREATE INDEX property_boolean ON assertions(scope,predicate,kind,boolean_value,polarity,object_id);
CREATE INDEX relation_reverse ON assertions(scope,kind,text_value,predicate,object_id);
CREATE INDEX object_assertions ON assertions(object_id);
CREATE TABLE evidence_bindings(assertion_id INTEGER NOT NULL REFERENCES assertions(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(assertion_id,ordinal));
CREATE TABLE projection_undo(scope TEXT NOT NULL, generation INTEGER NOT NULL,
 object_id INTEGER NOT NULL, expected_payload TEXT NOT NULL,
 PRIMARY KEY(scope,generation,object_id));
CREATE TABLE projection_events(id INTEGER PRIMARY KEY, scope TEXT NOT NULL, generation INTEGER NOT NULL,
 event TEXT NOT NULL, token INTEGER NOT NULL, receipt TEXT NOT NULL);
CREATE VIRTUAL TABLE object_fts USING fts5(title,body,content='object_versions',content_rowid='id');
CREATE TRIGGER objects_insert AFTER INSERT ON object_versions BEGIN
 INSERT INTO object_fts(rowid,title,body) VALUES(new.id,new.title,new.body); END;
CREATE TRIGGER objects_delete AFTER DELETE ON object_versions BEGIN
 INSERT INTO object_fts(object_fts,rowid,title,body) VALUES('delete',old.id,old.title,old.body); END;
PRAGMA user_version=1;
"""


class KnowledgeProjectionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version == 0:
                # A nonempty unversioned file is not implicitly ours to migrate.
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                    raise ValueError('PROJECTION_SCHEMA_UNKNOWN')
                db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nCOMMIT;')
            elif version != SCHEMA_VERSION:
                raise ValueError('PROJECTION_SCHEMA_UNSUPPORTED')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.create_collation('BOI_DECIMAL', lambda a, b: (Decimal(a) > Decimal(b)) - (Decimal(a) < Decimal(b)))
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self, scope, token):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                guard = db.execute('SELECT token FROM namespace_guards WHERE scope=?', (scope,)).fetchone()
                if guard is None or type(token) is not int or guard['token'] != token:
                    raise ValueError('PROJECTION_STALE_WRITER')
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def install_guard(self, scope, token):
        if type(token) is not int or token < 1:
            raise ValueError('PROJECTION_FENCE_INVALID')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                current = db.execute('SELECT token FROM namespace_guards WHERE scope=?', (scope,)).fetchone()
                if current and current['token'] > token:
                    raise ValueError('PROJECTION_STALE_WRITER')
                db.execute('INSERT INTO namespace_guards VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET token=excluded.token',
                           (scope, token))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _generation(db, scope, generation):
        return db.execute('SELECT * FROM projection_generations WHERE scope=? AND generation=?', (scope, generation)).fetchone()

    def receipt(self, scope, generation):
        with self.connection() as db:
            row = self._generation(db, scope, generation)
            return None if row is None else {**dict(row), 'receipt': json.loads(row['receipt'])}

    def prepare(self, manifest, batch, *, generation, operation_id, token):
        # Revalidate at the write boundary, including mutated nested JSON values.
        manifest = ProjectionPublication.model_validate(manifest.model_dump(mode='json'))
        batch = ProjectionBatch.model_validate(batch.model_dump(mode='json'))
        batch.validate_manifest(manifest)
        if type(generation) is not int or generation <= manifest.base_generation:
            raise ValueError('PROJECTION_GENERATION_INVALID')
        scope, batch_digest = manifest.scope_id, semantic_digest(batch)
        with self.transaction(scope, token) as db:
            existing = self._generation(db, scope, generation)
            if existing:
                if (existing['manifest_digest'] != manifest.digest or existing['batch_digest'] != batch_digest
                        or existing['operation_id'] != operation_id or existing['status'] == 'aborted'):
                    raise ValueError('PROJECTION_GENERATION_CONFLICT')
                return json.loads(existing['receipt'])
            pending = db.execute("SELECT 1 FROM projection_generations WHERE scope=? AND status='prepared'", (scope,)).fetchone()
            latest = db.execute("SELECT MAX(generation) FROM projection_generations WHERE scope=? AND status='committed'", (scope,)).fetchone()[0] or 0
            maximum = db.execute('SELECT MAX(generation) FROM projection_generations WHERE scope=?', (scope,)).fetchone()[0] or 0
            if pending or latest != manifest.base_generation or generation <= maximum:
                raise ValueError('PROJECTION_PRIOR_GENERATION_UNRESOLVED')
            for predicate in batch.predicates:
                payload = encoded(predicate.model_dump(mode='json'))
                previous = db.execute('SELECT payload FROM predicate_definitions WHERE scope=? AND revision=?',
                                      (scope, definition_key(predicate.revision))).fetchone()
                if previous and previous['payload'] != payload:
                    raise ValueError('PROJECTION_PREDICATE_REVISION_CONFLICT')
                db.execute('INSERT OR IGNORE INTO predicate_definitions VALUES(?,?,?)', (scope, definition_key(predicate.revision), payload))
            for change in manifest.changes:
                previous = db.execute('SELECT * FROM object_versions WHERE scope=? AND stable_id=? AND generation_until IS NULL',
                                      (scope, change.stable_id)).fetchone()
                expected = (change.previous_revision.ref if change.previous_revision else None) if manifest.projection_mode != 'bootstrap' else None
                if (previous['revision'] if previous else None) != expected:
                    raise ValueError('PROJECTION_PREVIOUS_REVISION_CONFLICT')
                if previous:
                    db.execute('INSERT INTO projection_undo VALUES(?,?,?,?)', (scope, generation, previous['id'], previous['payload']))
                    db.execute('UPDATE object_versions SET generation_until=? WHERE id=? AND generation_until IS NULL',
                               (generation, previous['id']))
            object_ids = []
            for obj in batch.objects:
                payload = encoded(obj.model_dump(mode='json'))
                prior_revision = db.execute("SELECT payload FROM object_versions WHERE scope=? AND revision=? AND json_extract(payload,'$.adapter_revision')=? LIMIT 1",
                                            (scope, obj.knowledge_revision.ref, obj.adapter_revision)).fetchone()
                if prior_revision and prior_revision['payload'] != payload:
                    raise ValueError('PROJECTION_OBJECT_REVISION_CONFLICT')
                cursor = db.execute('INSERT INTO object_versions(scope,stable_id,generation_from,object_type,revision,readiness,title,body,payload) VALUES(?,?,?,?,?,?,?,?,?)',
                                    (scope, obj.stable_id, generation, definition_key(obj.object_type), obj.knowledge_revision.ref,
                                     obj.readiness, obj.title, obj.body, payload))
                object_id = cursor.lastrowid
                object_ids.append(object_id)
                for fact in obj.facts:
                    value, kind = fact.value.value, fact.value.kind
                    cursor = db.execute('INSERT INTO assertions(object_id,scope,fact_id,predicate,kind,text_value,decimal_value,boolean_value,polarity,modality,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (object_id, scope, fact.fact_id, definition_key(fact.predicate_revision), kind,
                         value if kind in ('text','object') else None, value if kind == 'decimal' else None,
                         int(value) if kind == 'boolean' else None, fact.polarity, fact.modality,
                         encoded(fact.model_dump(mode='json'))))
                    for ordinal, evidence in enumerate(fact.evidence_bindings):
                        db.execute('INSERT INTO evidence_bindings VALUES(?,?,?)', (cursor.lastrowid, ordinal, encoded(evidence)))
            receipt = {'schema_version': SCHEMA_VERSION, 'manifest_digest': manifest.digest, 'batch_digest': batch_digest,
                       'scope_id': scope, 'generation': generation, 'base_generation': manifest.base_generation,
                       'object_ids': object_ids, 'upserts': len(batch.objects),
                       'deletes': sum(c.operation == 'delete' for c in manifest.changes),
                       'assertions': sum(len(o.facts) for o in batch.objects), 'semantic_truth_proven': False}
            # Both inverse rows and this completion receipt commit with the index rows.
            db.execute('INSERT INTO projection_generations VALUES(?,?,?,?,?,?,?,?)',
                       (scope, generation, manifest.base_generation, manifest.digest, operation_id, batch_digest, 'prepared', encoded(receipt)))
            db.execute('INSERT INTO projection_events(scope,generation,event,token,receipt) VALUES(?,?,?,?,?)',
                       (scope, generation, 'prepared', token, encoded(receipt)))
            return receipt

    def mark_committed(self, scope, generation, manifest_digest, *, token):
        with self.transaction(scope, token) as db:
            row = self._generation(db, scope, generation)
            if not row or row['manifest_digest'] != manifest_digest or row['status'] == 'aborted':
                raise ValueError('PROJECTION_GENERATION_UNAVAILABLE')
            if row['status'] == 'committed':
                return
            db.execute("UPDATE projection_generations SET status='committed' WHERE scope=? AND generation=?", (scope, generation))
            db.execute('INSERT INTO projection_events(scope,generation,event,token,receipt) VALUES(?,?,?,?,?)',
                       (scope, generation, 'committed', token, row['receipt']))

    def abort(self, scope, generation, manifest_digest, *, token, base_generation=0):
        """Caller must have authoritatively fenced this operation as aborting first."""
        with self.transaction(scope, token) as db:
            row = self._generation(db, scope, generation)
            if row is None:
                # A projector can have passed its PG ownership check just before
                # abort began. Persist a tombstone so that late SQLite prepare
                # cannot resurrect this now-aborted operation with the same token.
                receipt = {'scope_id': scope, 'generation': generation, 'manifest_digest': manifest_digest,
                           'prepared': False, 'reason': 'aborted_before_projection'}
                db.execute('INSERT INTO projection_generations VALUES(?,?,?,?,?,?,?,?)',
                           (scope, generation, base_generation, manifest_digest, manifest_digest,
                            semantic_digest(receipt), 'aborted', encoded(receipt)))
                db.execute('INSERT INTO projection_events(scope,generation,event,token,receipt) VALUES(?,?,?,?,?)',
                           (scope, generation, 'aborted', token, encoded(receipt)))
                return
            if row['manifest_digest'] != manifest_digest or row['status'] == 'committed':
                raise ValueError('PROJECTION_ABORT_CONFLICT')
            if row['status'] == 'aborted':
                return
            receipt = json.loads(row['receipt'])
            new_rows = db.execute('SELECT id,generation_until FROM object_versions WHERE scope=? AND generation_from=?', (scope, generation)).fetchall()
            if sorted(r['id'] for r in new_rows) != sorted(receipt['object_ids']) or any(r['generation_until'] is not None for r in new_rows):
                raise ValueError('PROJECTION_UNDO_STATE_CONFLICT')
            old_rows = db.execute('SELECT * FROM projection_undo WHERE scope=? AND generation=?', (scope, generation)).fetchall()
            for old in old_rows:
                current = db.execute('SELECT payload,generation_until FROM object_versions WHERE id=?', (old['object_id'],)).fetchone()
                if current is None or current['generation_until'] != generation or current['payload'] != old['expected_payload']:
                    raise ValueError('PROJECTION_UNDO_STATE_CONFLICT')
            db.execute('DELETE FROM object_versions WHERE scope=? AND generation_from=?', (scope, generation))
            for old in old_rows:
                db.execute('UPDATE object_versions SET generation_until=NULL WHERE id=?', (old['object_id'],))
            db.execute("UPDATE projection_generations SET status='aborted' WHERE scope=? AND generation=?", (scope, generation))
            db.execute('INSERT INTO projection_events(scope,generation,event,token,receipt) VALUES(?,?,?,?,?)',
                       (scope, generation, 'aborted', token, row['receipt']))

    def _assert_snapshot(self, db, snapshot):
        if snapshot.generation == 0 and snapshot.manifest_digest is None:
            return
        row = self._generation(db, snapshot.scope_id, snapshot.generation)
        if not row or row['manifest_digest'] != snapshot.manifest_digest or row['status'] not in ('prepared','committed'):
            raise ValueError('PROJECTION_SNAPSHOT_UNAVAILABLE')

    @staticmethod
    def _interval(snapshot):
        return (snapshot.scope_id, snapshot.generation, snapshot.generation)

    def read_objects(self, snapshot, stable_ids):
        ids = tuple(stable_ids)
        if not ids or len(ids) > 500:
            raise ValueError('PROJECTION_READ_BOUND_REQUIRED')
        with self.connection() as db:
            self._assert_snapshot(db, snapshot)
            placeholders = ','.join('?' for _ in ids)
            rows = db.execute('SELECT payload FROM object_versions WHERE scope=? AND generation_from<=? AND (generation_until IS NULL OR generation_until>?) '
                              f'AND stable_id IN ({placeholders}) ORDER BY stable_id', (*self._interval(snapshot), *ids)).fetchall()
            return [json.loads(r['payload']) for r in rows]

    def exact_candidates(self, snapshot, *, predicate_ref, value, operator='eq', polarity='positive', limit=100, explain=False):
        """Indexed value hits, including conditions, uncertainty and negative evidence.

        No inferred missing=false, unit conversion, applicability or full-set answer.
        The logical query executor must consume/evaluate the returned assertion.
        """
        value = ProjectionScalar.model_validate(value.model_dump(mode='json'))
        if operator not in ('eq','lt','lte','gt','gte') or (value.kind != 'decimal' and operator != 'eq'):
            raise ValueError('PROJECTION_COMPARISON_UNSUPPORTED')
        if type(limit) is not int or not 1 <= limit <= 500 or polarity not in ('positive','negative'):
            raise ValueError('PROJECTION_READ_BOUND_REQUIRED')
        columns = {'text': 'text_value', 'object': 'text_value', 'decimal': 'decimal_value', 'boolean': 'boolean_value'}
        operators = {'eq': '=', 'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>='}
        column, comparison = columns[value.kind], operators[operator]
        collation = ' COLLATE BOI_DECIMAL' if value.kind == 'decimal' else ''
        sql = f'''SELECT o.stable_id,o.revision,a.payload FROM assertions a JOIN object_versions o ON o.id=a.object_id
            WHERE a.scope=? AND a.predicate=? AND a.kind=? AND a.{column}{collation} {comparison} ? AND a.polarity=?
            AND o.generation_from<=? AND (o.generation_until IS NULL OR o.generation_until>?)
            ORDER BY o.stable_id,a.fact_id LIMIT ?'''
        args = (snapshot.scope_id, predicate_ref, value.kind, int(value.value) if value.kind == 'boolean' else value.value,
                polarity, snapshot.generation, snapshot.generation, limit + 1)
        with self.connection() as db:
            self._assert_snapshot(db, snapshot)
            if explain:
                return [r['detail'] for r in db.execute('EXPLAIN QUERY PLAN ' + sql, args)]
            rows = db.execute(sql, args).fetchall()
            return {'candidates': [{'stable_id': r['stable_id'], 'revision': r['revision'], 'assertion': json.loads(r['payload'])} for r in rows[:limit]],
                    'has_more': len(rows) > limit, 'semantic_filter_satisfied': False}

    def lexical_candidates(self, snapshot, phrase, *, limit=100):
        if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 1000 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('PROJECTION_LEXICAL_BOUND_REQUIRED')
        # An exact FTS phrase, not a caller-supplied FTS operator expression.
        match = '"' + phrase.replace('"', '""') + '"'
        with self.connection() as db:
            self._assert_snapshot(db, snapshot)
            rows = db.execute('''SELECT o.stable_id,o.revision,o.title,bm25(object_fts) AS score
                FROM object_fts JOIN object_versions o ON o.id=object_fts.rowid WHERE object_fts MATCH ?
                AND o.scope=? AND o.generation_from<=? AND (o.generation_until IS NULL OR o.generation_until>?)
                ORDER BY score,o.stable_id LIMIT ?''', (match, *self._interval(snapshot), limit + 1)).fetchall()
            return {'candidates': [dict(r) for r in rows[:limit]], 'has_more': len(rows) > limit, 'semantic_filter_satisfied': False}

    def coverage(self, snapshot):
        with self.connection() as db:
            self._assert_snapshot(db, snapshot)
            return dict(db.execute('''SELECT readiness,COUNT(*) FROM object_versions WHERE scope=?
                AND generation_from<=? AND (generation_until IS NULL OR generation_until>?) GROUP BY readiness''', self._interval(snapshot)))

    def query_inputs(self, snapshot, *, stable_ids, predicate_refs, fact_limit=10000):
        """Bounded internal query inputs without reading document/body JSON.

        The enclosing query service supplies an authorized population/snapshot.
        Read both polarities and every value of the requested predicates: value
        hits alone would omit contrary evidence and confuse absence with false.
        """
        ids,predicates=tuple(stable_ids),tuple(predicate_refs)
        if (not ids or len(ids)>500 or len(set(ids))!=len(ids) or not predicates or len(predicates)>128
                or len(set(predicates))!=len(predicates) or type(fact_limit) is not int or not 1<=fact_limit<=100000):
            raise ValueError('PROJECTION_QUERY_INPUT_BOUND_REQUIRED')
        with self.connection() as db:
            db.execute('BEGIN')
            self._assert_snapshot(db,snapshot)
            rows=db.execute('SELECT id,stable_id,object_type,revision,readiness,title FROM object_versions '
                'WHERE scope=? AND generation_from<=? AND (generation_until IS NULL OR generation_until>?) '
                'AND stable_id IN ('+','.join('?' for _ in ids)+') ORDER BY stable_id',
                (*self._interval(snapshot),*ids)).fetchall()
            objects={r['stable_id']:{'stable_id':r['stable_id'],'object_type':r['object_type'],
                'revision':r['revision'],'readiness':r['readiness'],'title':r['title'],'facts':[]} for r in rows}
            if len(objects)!=len(rows):raise ValueError('PROJECTION_QUERY_GENERATION_OVERLAP')
            if rows:
                by_id={r['id']:r['stable_id'] for r in rows}
                facts=db.execute('SELECT object_id,payload FROM assertions WHERE object_id IN ('+
                    ','.join('?' for _ in by_id)+') AND predicate IN ('+','.join('?' for _ in predicates)+
                    ') ORDER BY object_id,fact_id LIMIT ?',(*by_id,*predicates,fact_limit+1)).fetchall()
                if len(facts)>fact_limit:raise ValueError('PROJECTION_QUERY_FACT_BUDGET_EXCEEDED')
                for row in facts:objects[by_id[row['object_id']]]['facts'].append(json.loads(row['payload']))
            return objects
