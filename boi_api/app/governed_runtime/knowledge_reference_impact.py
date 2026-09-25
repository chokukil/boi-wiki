"""Current-space incoming declarations with indexed SQL and fenced pages.

No source bytes, whole member-ID list, inferred relationships, or semantic
conflict verdict. Missing legacy projections remain explicit uncovered content.
"""
import json

from pydantic import Field

from ..v2.atomic_store_contract import AtomicWrite
from .knowledge_space_sets import KnowledgeSetRead, KnowledgeSpaceSets, SETS
from .native_reference_projection import VERSION, reference_index_ready
from .semantic_binding_contract import RevisionRef, semantic_digest


class KnowledgeIncomingRead(KnowledgeSetRead):
    targets: tuple[RevisionRef, ...] = Field(min_length=1,max_length=500)
    limit: int = Field(default=20,ge=1,le=100,strict=True)
    cursor: str | None = Field(default=None,pattern=r'^knowledge-reference-cursor:sha256:[0-9a-f]{64}$')


class PostgresReferenceIndex:
    def __init__(self, backend, changes):
        if changes.store is not backend.store or changes.prefix != backend.prefix:
            raise ValueError('KNOWLEDGE_REFERENCE_BACKEND_MISMATCH')
        self.backend, self.changes, self.store = backend, changes, backend.store
        with self.store._connection() as connection:
            reference_index_ready(connection,self.store._table('domain_knowledge_assets'))

    def fingerprints(self, revisions):
        if not 1 <= len(revisions) <= 20:
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_COUNT_INVALID')
        keys = [self.backend.prefix + r.ref for r in revisions]
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            reference_index_ready(connection, self.store._table('domain_knowledge_assets'))
            rows = connection.execute(f'SELECT item_key,native_reference_digest FROM '
                f"{self.store._table('domain_knowledge_assets')} WHERE item_key=ANY(%s)", (keys,)).fetchall()
        return {key[len(self.backend.prefix):]: digest for key, digest in rows}

    def statement(self, binding, targets):
        relation = self.backend.relation(binding)
        table, prefix = self.store._table('domain_knowledge_assets'), self.backend.prefix
        conditions = ' OR '.join(["(a.payload->>'reference_projection_wire')::jsonb @> %s::jsonb"] * len(targets)) or 'FALSE'
        matches = tuple(json.dumps({'edges':[{'target':t.model_dump(mode='json')}]}) for t in targets)
        sql = relation.ctes + f''', ref_members AS (
 SELECT DISTINCT u.id,c.entry->'content_revision' AS revision,c.native_index,c.native_head,
        a.native_reference_digest,(a.payload->>'reference_projection_wire')::jsonb AS projection
 FROM boi_u u JOIN boi_space_checked c ON c.entry->>'stable_id'=u.id
 JOIN {table} a ON a.item_key=%s || (c.entry->'content_revision'->>'ref')
), ref_checked AS (
 SELECT *, CASE
 WHEN native_head->>'reference_projection_digest' IS NULL AND projection IS NULL THEN 'unprepared'
 WHEN projection->>'contract_version'=%s
   AND projection->>'record_payload_digest'=native_index->>'record_payload_digest'
   AND native_reference_digest=native_head->>'reference_projection_digest'
   AND native_reference_digest=native_index->>'reference_projection_digest'
   AND jsonb_typeof(projection->'edges')='array' THEN 'prepared'
 ELSE 'invalid' END AS preparation_state
 FROM ref_members
), ref_candidates AS (
 SELECT a.item_key FROM {table} a WHERE ({conditions}) AND left(a.item_key,%s)=%s
), incoming AS (
 SELECT r.* FROM ref_checked r JOIN ref_candidates c ON c.item_key=%s || (r.revision->>'ref')
 WHERE r.preparation_state='prepared'
)'''
        return sql, (*relation.parameters,prefix,VERSION,*matches,len(prefix),prefix,prefix)

    def summary(self, binding, targets):
        sql, params = self.statement(binding,targets)
        try:
            with self.store._connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '5s'")
                reference_index_ready(connection,self.store._table('domain_knowledge_assets'))
                counts = connection.execute('WITH '+sql+''' SELECT
 (SELECT count(*) FROM boi_space_checked WHERE NOT valid),
 (SELECT count(*) FROM ref_checked WHERE preparation_state='invalid'),
 (SELECT count(*) FROM ref_checked WHERE preparation_state='unprepared'),
 (SELECT count(*) FROM ref_checked),(SELECT count(*) FROM incoming)''',params).fetchone()
        except self.store.psycopg.Error:
            raise ValueError('KNOWLEDGE_REFERENCE_INDEX_READ_FAILED') from None
        if counts[0] or counts[1]:
            raise ValueError('KNOWLEDGE_REFERENCE_INDEX_UNPREPARED_OR_CHANGED')
        return {'visible_members':counts[3], 'unprepared_visible_members':counts[2],
            'matching_visible_members':counts[4]}

    def changed(self, snapshot, binding, *, own_events=()):
        table, prefix = self.store._table, self.backend.prefix
        # A newly added, removed, or moved member produces a partition event.
        # Edits to current visible indexes/heads are checked by indexed keys;
        # unrelated tenant history is not materialized or handed to Python.
        sql = f'''WITH allowed AS (
 SELECT * FROM jsonb_to_recordset(%s::jsonb) AS a(receipt text,collection text,key text)
), own_receipts AS (
 SELECT c.item_key,c.change_xid FROM boi_knowledge_query_changes_v1 c
 WHERE c.collection='knowledge_publication_receipts'
   AND c.item_key IN (SELECT %s || receipt FROM allowed)
   AND (SELECT count(*) FROM boi_knowledge_query_changes_v1 r
        WHERE r.collection=c.collection AND r.item_key=c.item_key)=1
), members AS (
 SELECT payload->>'stable_id' AS id,payload->'content_revision'->>'ref' AS revision
 FROM {table('knowledge_space_entries')} WHERE employee_id=%s AND left(item_key,%s)=%s
)
SELECT EXISTS(SELECT 1 FROM boi_knowledge_query_changes_v1 c WHERE
 (c.change_xid>=pg_snapshot_xmax(%s::pg_snapshot) OR c.change_xid IN (SELECT pg_snapshot_xip(%s::pg_snapshot))) AND (
 (c.collection='knowledge_space_entries' AND c.partition=%s AND left(c.item_key,%s)=%s) OR
 (c.collection IN ('knowledge_space_heads','domain_asset_heads') AND c.item_key IN (SELECT %s || id FROM members)) OR
 (c.collection='domain_knowledge_assets' AND c.item_key IN (SELECT %s || revision FROM members)) OR
 (c.collection='knowledge_publication_receipts' AND c.item_key IN (
   SELECT %s || ((h.payload->>'query_policy_wire')::jsonb->>'publication_manifest_digest')
   FROM {table('knowledge_space_heads')} h JOIN members m ON h.item_key=%s || m.id))
 ) AND NOT EXISTS(SELECT 1 FROM allowed a JOIN own_receipts r ON r.item_key=%s || a.receipt
   WHERE r.change_xid=c.change_xid AND a.collection=c.collection AND %s || a.key=c.item_key))'''
        params=(json.dumps(own_events),prefix,binding['partition'],len(prefix),prefix,snapshot,snapshot,
            binding['partition'],len(prefix),prefix,prefix,prefix,prefix,prefix,prefix,prefix)
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            self.changes._ready(connection)
            reference_index_ready(connection,self.store._table('domain_knowledge_assets'))
            return connection.execute(sql,params).fetchone()[0]

    def page(self, binding, targets, after_id, limit):
        sql, params = self.statement(binding,targets)
        requested = json.dumps([t.model_dump(mode='json') for t in targets])
        try:
            with self.store._connection() as connection, connection.transaction():
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                connection.execute("SET LOCAL statement_timeout = '5s'")
                counts = connection.execute('WITH '+sql+''' SELECT
 (SELECT count(*) FROM boi_space_checked WHERE NOT valid),
 (SELECT count(*) FROM ref_checked WHERE preparation_state='invalid'),
 (SELECT count(*) FROM ref_checked WHERE preparation_state='unprepared'),
 (SELECT count(*) FROM ref_checked),(SELECT count(*) FROM incoming)''',params).fetchone()
                if counts[0] or counts[1]:
                    raise ValueError('KNOWLEDGE_REFERENCE_INDEX_UNPREPARED_OR_CHANGED')
                rows = connection.execute('WITH '+sql+''' SELECT id,revision,native_index->>'title',
 (SELECT jsonb_agg(e) FROM jsonb_array_elements(projection->'edges') e
   WHERE e->'target' IN (SELECT value FROM jsonb_array_elements(%s::jsonb)))
 FROM incoming WHERE id>%s ORDER BY id LIMIT %s''',(*params,requested,after_id,limit+1)).fetchall()
        except self.store.psycopg.Error:
            raise ValueError('KNOWLEDGE_REFERENCE_INDEX_READ_FAILED') from None
        result = {'items':[{'stable_id':r[0],'revision':r[1],'title':r[2],'declared_references':r[3]} for r in rows[:limit]],
            'next_after_id':rows[limit-1][0] if len(rows)>limit else None,
            'visible_members':counts[3], 'unprepared_visible_members':counts[2], 'matching_visible_members':counts[4]}
        if len(json.dumps(result,ensure_ascii=False).encode()) > 4*1024*1024:
            raise ValueError('KNOWLEDGE_REFERENCE_PAGE_BYTE_LIMIT')
        return result


class KnowledgeReferenceImpact:
    def __init__(self, sets, index):
        if not isinstance(sets,KnowledgeSpaceSets) or index.backend is not sets.backend:
            raise ValueError('KNOWLEDGE_REFERENCE_CURRENT_SPACE_REQUIRED')
        self.sets,self.index,self.store=sets,index,sets.store

    def _targets(self, actor_id, targets, purpose):
        authorities=[]
        for target in targets:
            record=self.sets.spaces.intake.ledger.read(target.ref)
            stable_id='domain-asset-head:'+semantic_digest([record.payload.get('employee_id'),
                record.payload.get('namespace'),record.payload.get('logical_id')])
            access,_=self.sets.spaces.authorize(actor_id=actor_id,stable_id=stable_id,revision=target,purpose=purpose)
            authorities.append(access.authority_digest)
        return semantic_digest(authorities)

    def read(self, *, actor_id, request):
        req=KnowledgeIncomingRead.model_validate(request)
        targets=tuple(sorted(set(req.targets),key=lambda t:(t.ref,t.revision_digest)))
        binding=self.sets.resolve(actor_id=actor_id,set_ref=req.set_ref)
        target_authority=self._targets(actor_id,targets,binding['purpose'])
        basis={'set_ref':req.set_ref,'binding':binding,'targets':[t.model_dump(mode='json') for t in targets],
            'target_authority':target_authority,'limit':req.limit}
        after_id=''
        if req.cursor:
            row=self.store.get(SETS,req.cursor)
            if not row or row.get('employee_id')!=actor_id:
                raise ValueError('KNOWLEDGE_REFERENCE_CURSOR_ACCESS_DENIED')
            material={k:row[k] for k in ('basis','snapshot','after_id','contract_version')}
            if 'knowledge-reference-cursor:'+semantic_digest(material)!=req.cursor or row['basis']!=basis:
                raise ValueError('KNOWLEDGE_REFERENCE_CURSOR_CHANGED')
            snapshot,after_id=row['snapshot'],row['after_id']
        else:
            snapshot=self.index.changes.snapshot()
        if self.index.changed(snapshot,binding):
            raise ValueError('KNOWLEDGE_REFERENCE_SNAPSHOT_CHANGED')
        result=self.index.page(binding,targets,after_id,req.limit)
        if (self.sets.resolve(actor_id=actor_id,set_ref=req.set_ref)!=binding
                or self._targets(actor_id,targets,binding['purpose'])!=target_authority
                or self.index.changed(snapshot,binding)):
            raise ValueError('KNOWLEDGE_REFERENCE_SNAPSHOT_CHANGED')
        next_cursor=None
        if result['next_after_id']:
            material={'contract_version':'boi/knowledge-reference-cursor@1','basis':basis,
                'snapshot':snapshot,'after_id':result['next_after_id']}
            next_cursor='knowledge-reference-cursor:'+semantic_digest(material)
            row={**material,'employee_id':actor_id}
            old=self.store.get(SETS,next_cursor)
            if old is not None and any(old.get(k)!=v for k,v in row.items()):
                raise ValueError('KNOWLEDGE_REFERENCE_CURSOR_CHANGED')
            if not self.store.atomic_compare_and_write((AtomicWrite(SETS,next_cursor,old,old or row),)):
                raise ValueError('KNOWLEDGE_REFERENCE_CURSOR_CHANGED')
            if (self.sets.resolve(actor_id=actor_id,set_ref=req.set_ref)!=binding
                    or self._targets(actor_id,targets,binding['purpose'])!=target_authority
                    or self.index.changed(snapshot,binding)):
                raise ValueError('KNOWLEDGE_REFERENCE_SNAPSHOT_CHANGED')
        return {'contract_version':'boi/knowledge-reference-impact@1','set_ref':req.set_ref,
            **{k:v for k,v in result.items() if k!='next_after_id'},'next_cursor':next_cursor,
            'scope':binding['target'],'basis_digest':semantic_digest(basis),'snapshot':snapshot,
            'population_kind':'published_native_space_members',
            'legacy_outside_spaces':'not_evaluated',
            'coverage':'declared_native_dependencies_conflicts_supersedes_only',
            'semantic_conflicts':'not_evaluated','outside_scope':'not_evaluated',
            'undeclared_related_candidates':'not_evaluated','transitive_impact':'not_evaluated',
            'source_access_granted':False,'use_qualification_granted':False,'publication_authorized':False}
