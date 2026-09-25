"""Current-space discovery by exact declared contract, using prepared metadata."""
import json
import re
from pathlib import Path

from .knowledge_space_sets import SETS
from .native_contract_catalog import VERSION, contract_catalog_ready
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite

_ROOT = Path(__file__).parent
_IMPLEMENTATION = semantic_digest({name: (_ROOT / name).read_text() for name in
    ('knowledge_contract_discovery.py', 'native_contract_catalog.py', 'knowledge_space_sets.py')})


class KnowledgeContractCatalog:
    def __init__(self, sets, index):
        if sets.backend is not index.backend:
            raise ValueError('KNOWLEDGE_CONTRACT_BACKEND_MISMATCH')
        self.sets, self.index, self.store = sets, index, sets.store

    def _current(self, actor, set_ref, binding, snapshot):
        if self.sets.resolve(actor_id=actor, set_ref=set_ref) != binding or self.index.changed(snapshot, binding):
            raise ValueError('KNOWLEDGE_CONTRACT_CATALOG_CHANGED')

    def _statement(self, binding, *, namespace, kind, content_contract, meaning_contract):
        relation = self.sets.backend.relation(binding)
        table = self.index.store._table('domain_knowledge_assets')
        population, population_params, filters, filter_params = [], [], [], []
        for key, value in (('namespace', namespace), ('kind', kind)):
            if value is not None:
                population.append(f"s.native_index->>'{key}'=%s"); population_params.append(value)
        for key, value in (('native_content_contract', content_contract), ('native_meaning_contract', meaning_contract)):
            if value is not None:
                # Fixed-width candidate index avoids imposing a new maximum
                # length on existing contract identifiers. Equality against the
                # full string remains mandatory even if hash keys collide.
                filters.append(f"a.{key}_key=sha256(convert_to(%s,'UTF8')) AND a.{key}=%s")
                filter_params.extend((value, value))
        population_sql, filter_sql = ' AND '.join(population) or 'TRUE', ' AND '.join(filters)
        # Contract equality is evaluated on indexed scalar columns. The full
        # population is counted in PostgreSQL for explicit missing-metadata
        # coverage, while only the requested result page enters Python.
        sql = relation.ctes + f''', documents AS (
 SELECT s.entry->>'stable_id' AS id,s.entry->'content_revision' AS revision,
        s.native_index,a.item_key,
 CASE WHEN s.native_index->>'contract_projection_wire' IS NULL
       AND s.native_index->>'contract_projection_digest' IS NULL
       AND s.native_head->>'contract_projection_wire' IS NULL
       AND s.native_head->>'contract_projection_digest' IS NULL
       AND a.native_contract_digest IS NULL AND a.native_content_contract IS NULL
       AND a.native_meaning_contract IS NULL AND a.native_content_contract_key IS NULL
       AND a.native_meaning_contract_key IS NULL THEN 'unprepared'
      WHEN a.native_contract_digest IS NOT NULL
       AND a.native_contract_digest=s.native_index->>'contract_projection_digest'
       AND a.native_contract_digest=s.native_head->>'contract_projection_digest'
       AND s.native_index->>'contract_projection_wire'=s.native_head->>'contract_projection_wire'
       THEN 'prepared'
      ELSE 'invalid' END AS state
 FROM boi_space_checked s JOIN boi_u u ON u.id=s.entry->>'stable_id'
 JOIN {table} a ON a.item_key=%s || (s.entry->'content_revision'->>'ref')
 WHERE {population_sql}
), matches AS (
 SELECT d.id,d.revision,d.native_index,a.native_content_contract AS content_contract,
        a.native_meaning_contract AS meaning_contract
 FROM {table} a JOIN documents d ON d.item_key=a.item_key
 WHERE d.state='prepared' AND {filter_sql}
)'''
        return sql, (*relation.parameters, self.sets.backend.prefix, *population_params, *filter_params)

    def search(self, *, actor_id, target, content_contract=None, meaning_contract=None,
               namespace=None, kind=None, limit=20, cursor='', purpose='model_input'):
        if (type(limit) is not int or not 1 <= limit <= 100 or not isinstance(cursor, str)
                or any(value is not None and (not isinstance(value, str) or not value.strip())
                       for value in (content_contract, meaning_contract, namespace, kind))
                or (content_contract is None and meaning_contract is None)):
            raise ValueError('KNOWLEDGE_CONTRACT_REQUEST_INVALID')
        if purpose not in ('read', 'model_input'):
            raise ValueError('KNOWLEDGE_CONTRACT_PURPOSE_INVALID')
        request = {'target': target, 'content_contract': content_contract, 'meaning_contract': meaning_contract,
                   'namespace': namespace, 'kind': kind, 'limit': limit, 'purpose': purpose,
                   'implementation': _IMPLEMENTATION}
        after = ''
        if cursor:
            if not re.fullmatch(r'contract:[0-9a-f]{64}', cursor):
                raise ValueError('KNOWLEDGE_CONTRACT_CURSOR_INVALID')
            saved = self.store.get(SETS, cursor)
            if not saved or saved.get('employee_id') != actor_id:
                raise ValueError('KNOWLEDGE_CONTRACT_CURSOR_DENIED')
            material = {k: saved[k] for k in ('request', 'set_ref', 'snapshot', 'after')}
            if 'contract:' + semantic_digest(material).split(':')[1] != cursor or material['request'] != request:
                raise ValueError('KNOWLEDGE_CONTRACT_CURSOR_CHANGED')
            set_ref, snapshot, after = saved['set_ref'], saved['snapshot'], saved['after']
        else:
            set_ref = self.sets.issue(actor_id=actor_id, target=target, purpose=purpose)['set_ref']
            snapshot = self.index.changes.snapshot()
        binding = self.sets.resolve(actor_id=actor_id, set_ref=set_ref)
        if binding['purpose'] != purpose:
            raise ValueError('KNOWLEDGE_CONTRACT_PURPOSE_INVALID')
        self._current(actor_id, set_ref, binding, snapshot)
        sql, params = self._statement(binding, namespace=namespace, kind=kind,
            content_contract=content_contract, meaning_contract=meaning_contract)
        try:
            with self.index.store._connection() as connection, connection.transaction():
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                connection.execute("SET LOCAL statement_timeout='5s'")
                contract_catalog_ready(connection, self.index.store._table('domain_knowledge_assets'))
                counts = connection.execute('WITH ' + sql + ''' SELECT
 (SELECT count(*) FROM boi_space_checked WHERE NOT valid),
 (SELECT count(*) FROM documents WHERE state='invalid'),
 (SELECT count(*) FROM documents),(SELECT count(*) FROM documents WHERE state='unprepared'),
 (SELECT count(*) FROM matches)''', params).fetchone()
                if counts[0] or counts[1]:
                    raise ValueError('KNOWLEDGE_CONTRACT_INDEX_CHANGED_OR_UNPREPARED')
                rows = connection.execute('WITH ' + sql + ''' SELECT id,revision,
 native_index->>'title',native_index->>'namespace',native_index->>'kind',
 content_contract,meaning_contract
 FROM matches WHERE id>%s ORDER BY id LIMIT %s''', (*params, after, limit + 1)).fetchall()
        except self.index.store.psycopg.Error:
            raise ValueError('KNOWLEDGE_CONTRACT_INDEX_READ_FAILED') from None
        self._current(actor_id, set_ref, binding, snapshot)
        items = [{'stable_id': r[0], 'revision': r[1], 'title': r[2], 'namespace': r[3], 'kind': r[4],
                  'content_contract': r[5], 'meaning_contract': r[6], 'target': binding['target'],
                  'read': {'tool': 'boi_knowledge_read', 'arguments': {'revision': r[1], 'view': 'asset'}}}
                 for r in rows[:limit]]
        if len(json.dumps(items, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
            raise ValueError('KNOWLEDGE_CONTRACT_PAGE_BYTE_LIMIT')
        next_cursor = None
        if len(rows) > limit:
            material = {'request': request, 'set_ref': set_ref, 'snapshot': snapshot, 'after': rows[limit-1][0]}
            next_cursor = 'contract:' + semantic_digest(material).split(':')[1]
            old = self.store.get(SETS, next_cursor); value = {**material, 'employee_id': actor_id}
            if old is not None and any(old.get(k) != v for k, v in value.items()):
                raise ValueError('KNOWLEDGE_CONTRACT_CURSOR_CHANGED')
            if not self.store.atomic_compare_and_write((AtomicWrite(SETS, next_cursor, old, old or value),)):
                raise ValueError('KNOWLEDGE_CONTRACT_CURSOR_CHANGED')
            self._current(actor_id, set_ref, binding, snapshot)
        return {'contract_version': VERSION, 'items': items, 'next_cursor': next_cursor,
                'set_ref': set_ref, 'scope': binding['target'], 'matching_documents': counts[4],
                'visible_documents': counts[2], 'unprepared_documents': counts[3],
                'metadata_coverage_complete': counts[3] == 0,
                'retrieval': 'exact_declared_contract_metadata',
                'content_contract': content_contract, 'meaning_contract': meaning_contract,
                'semantic_selection_complete': False, 'use_qualification_granted': False,
                'source_access_granted': False, 'raw_source_files': 'not_searched',
                'outside_selected_space': 'not_searched', 'legacy_outside_spaces': 'not_searched'}
