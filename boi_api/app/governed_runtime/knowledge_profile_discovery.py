"""Current authorized Profile component candidates, without reading all bodies."""
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from .knowledge_projection_contract import ProjectionComponent
from .knowledge_space_sets import KnowledgeSetRead,SETS
from .native_profile_catalog import META,COMPONENTS,VERSION,tokens,profile_catalog_ready
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest
from ..v2.atomic_store_contract import AtomicWrite

_ROOT=Path(__file__).parent
_IMPLEMENTATION={name:byte_digest((_ROOT/name).read_bytes()) for name in (
    'knowledge_profile_discovery.py','native_profile_catalog.py','knowledge_space_sets.py')}


def discovery_implementation():
    if any(byte_digest((_ROOT/name).read_bytes())!=digest for name,digest in _IMPLEMENTATION.items()):
        raise ValueError('KNOWLEDGE_PROFILE_LOADED_IMPLEMENTATION_STALE')
    return dict(_IMPLEMENTATION)


class ProfileDiscoveryRequest(KnowledgeSetRead):
    query: str = Field(default='',max_length=2000)
    kind: Literal['object_type','predicate'] | None = None
    role: str | None = Field(default=None,min_length=1,max_length=2000)
    value_kind: Literal['text','decimal','boolean','object'] | None = None
    subject_type: ProjectionComponent | None = None
    operator: Literal['eq','ne','lt','lte','gt','gte'] | None = None
    limit: int = Field(default=20,ge=1,le=50,strict=True)
    cursor: str | None = Field(default=None,pattern=r'^knowledge-profile-cursor:sha256:[0-9a-f]{64}$')


class KnowledgeProfileDiscovery:
    def __init__(self,sets,index):
        if sets.backend is not index.backend:
            raise ValueError('KNOWLEDGE_PROFILE_DISCOVERY_BACKEND_MISMATCH')
        self.sets,self.index,self.store=sets,index,sets.store

    def _statement(self,binding,request,terms):
        relation=self.sets.backend.relation(binding)
        prefix=self.sets.backend.prefix
        native=self.index.store._table('domain_knowledge_assets')
        predicates,params=[],[]
        for name in ('kind','role','value_kind'):
            value=getattr(request,name)
            if value is not None:
                predicates.append(f'c.{name}=%s');params.append(value)
        if terms:predicates.append('c.tokens && %s::text[]');params.append(terms)
        if request.subject_type is not None:
            predicates.append('c.subject_type=%s::jsonb');params.append(request.subject_type.model_dump_json())
        if request.operator is not None:
            predicates.append("c.component->'declaration'->'allowed_operators' ? %s");params.append(request.operator)
        conditions=' AND '.join(predicates) or 'TRUE'
        sql=relation.ctes+f''', profiles AS (
 SELECT s.entry->>'stable_id' AS stable_id,s.entry->'content_revision' AS revision,
        a.item_key AS asset_key,m.info,m.component_count,
 CASE
 WHEN s.native_index->>'profile_component_state'='unsupported_contract'
   AND s.native_head->>'profile_component_state'='unsupported_contract' AND m.asset_key IS NULL
   AND a.native_profile_digest IS NULL THEN 'unsupported'
 WHEN s.native_index->>'profile_components_wire' IS NULL
   AND s.native_index->>'profile_components_digest' IS NULL
   AND s.native_head->>'profile_components_digest' IS NULL
   AND s.native_index->>'profile_component_state' IS NULL
   AND s.native_head->>'profile_component_state' IS NULL AND m.asset_key IS NULL
   AND a.native_profile_digest IS NULL THEN 'unprepared'
 WHEN s.native_index->>'profile_component_state'='prepared'
   AND s.native_head->>'profile_component_state'='prepared'
   AND m.digest=a.native_profile_digest
   AND m.digest=s.native_index->>'profile_components_digest'
   AND m.digest=s.native_head->>'profile_components_digest'
   AND m.revision=s.entry->'content_revision'
   AND m.payload_digest=s.native_index->>'record_payload_digest'
   AND m.info->>'contract_version'='boi/knowledge-profile@1' THEN 'prepared'
 ELSE 'invalid' END AS state
 FROM boi_space_checked s JOIN boi_u u ON u.id=s.entry->>'stable_id'
 JOIN {native} a ON a.item_key=%s || (s.entry->'content_revision'->>'ref')
 LEFT JOIN {META} m ON m.asset_key=a.item_key
 WHERE s.native_index->>'kind'='profile'
), matches AS (
 SELECT p.stable_id,p.revision,p.info,c.position,c.component
 FROM {COMPONENTS} c JOIN profiles p ON p.asset_key=c.asset_key
 WHERE p.state='prepared' AND {conditions}
)'''
        return sql,(*relation.parameters,prefix,*params)

    def _current(self,actor,ref,binding,snapshot):
        if self.sets.resolve(actor_id=actor,set_ref=ref)!=binding or self.index.changed(snapshot,binding):
            raise ValueError('KNOWLEDGE_PROFILE_DISCOVERY_CHANGED')

    def read(self,*,actor_id,request):
        implementation=discovery_implementation()
        req=ProfileDiscoveryRequest.model_validate(request)
        terms=tokens(req.query)
        if len(terms)>64:raise ValueError('KNOWLEDGE_PROFILE_QUERY_TOKEN_LIMIT')
        binding=self.sets.resolve(actor_id=actor_id,set_ref=req.set_ref)
        if binding['purpose']!='model_input':
            raise ValueError('KNOWLEDGE_PROFILE_MODEL_INPUT_NOT_AUTHORIZED')
        basis={'request':req.model_dump(mode='json',exclude={'cursor'}),'binding':binding,
            'contract_version':VERSION,'implementation':implementation}
        after_id,after_position='',-1
        if req.cursor:
            row=self.store.get(SETS,req.cursor)
            if not row or row.get('employee_id')!=actor_id:
                raise ValueError('KNOWLEDGE_PROFILE_CURSOR_DENIED')
            material={k:row[k] for k in ('basis','snapshot','after_id','after_position')}
            if 'knowledge-profile-cursor:'+semantic_digest(material)!=req.cursor or row['basis']!=basis:
                raise ValueError('KNOWLEDGE_PROFILE_CURSOR_CHANGED')
            snapshot,after_id,after_position=row['snapshot'],row['after_id'],row['after_position']
        else:snapshot=self.index.changes.snapshot()
        self._current(actor_id,req.set_ref,binding,snapshot)
        sql,params=self._statement(binding,req,terms)
        with self.index.store._connection() as connection,connection.transaction():
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            connection.execute("SET LOCAL statement_timeout='5s'")
            profile_catalog_ready(connection,self.index.store._table('domain_knowledge_assets'))
            counts=connection.execute('WITH '+sql+''' SELECT
 (SELECT count(*) FROM boi_space_checked WHERE NOT valid),
 (SELECT count(*) FROM profiles WHERE state='invalid'),
 (SELECT count(*) FROM profiles),(SELECT count(*) FROM profiles WHERE state='unprepared'),
 (SELECT count(*) FROM profiles WHERE state='unsupported'),(SELECT count(*) FROM matches)''',params).fetchone()
            if counts[0] or counts[1]:raise ValueError('KNOWLEDGE_PROFILE_INDEX_CHANGED_OR_UNPREPARED')
            rows=connection.execute('WITH '+sql+''' SELECT stable_id,revision,info,position,component
 FROM matches WHERE (stable_id,position)>(%s,%s) ORDER BY stable_id,position LIMIT %s''',
                (*params,after_id,after_position,req.limit+1)).fetchall()
        self._current(actor_id,req.set_ref,binding,snapshot)
        items=[{'profile_stable_id':r[0],'profile_revision':r[1],'profile':r[2],**r[4],
            'read':{'tool':'boi_knowledge_read','arguments':{'revision':r[1],'view':'asset'}}} for r in rows[:req.limit]]
        if len(json.dumps(items,ensure_ascii=False).encode())>4*1024*1024:
            raise ValueError('KNOWLEDGE_PROFILE_CANDIDATE_BYTE_LIMIT')
        cursor=None
        if len(rows)>req.limit:
            material={'basis':basis,'snapshot':snapshot,'after_id':rows[req.limit-1][0],
                'after_position':rows[req.limit-1][3]}
            cursor='knowledge-profile-cursor:'+semantic_digest(material)
            old=self.store.get(SETS,cursor);value={**material,'employee_id':actor_id}
            if old is not None and any(old.get(k)!=v for k,v in value.items()):
                raise ValueError('KNOWLEDGE_PROFILE_CURSOR_CHANGED')
            if not self.store.atomic_compare_and_write((AtomicWrite(SETS,cursor,old,old or value),)):
                raise ValueError('KNOWLEDGE_PROFILE_CURSOR_CHANGED')
            self._current(actor_id,req.set_ref,binding,snapshot)
        if discovery_implementation()!=implementation:
            raise ValueError('KNOWLEDGE_PROFILE_LOADED_IMPLEMENTATION_STALE')
        return {'contract_version':VERSION,'set_ref':req.set_ref,'scope':binding['target'],
            'items':items,'next_cursor':cursor,'matching_components':counts[5],
            'visible_profiles':counts[2],'unprepared_profiles':counts[3],'unsupported_profiles':counts[4],
            'population_kind':'published_native_profile_components','retrieval':'lexical_overlap_and_declared_filters',
            'query_tokens':terms,'semantic_selection_complete':False,'use_qualification_granted':False,
            'source_access_granted':False,'fact_population_complete':False,
            'outside_selected_space':'not_searched','legacy_outside_spaces':'not_searched',
            'next_step':'Select exact component references using domain context; execute rechecks Profile and fact qualification.'}
