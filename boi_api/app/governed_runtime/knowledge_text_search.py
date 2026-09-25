"""Current-space lexical discovery for people and external agents.

SQL intersects a character index with current content rights. Only one result
page enters Python. A match says where text occurs, not what the text proves.
"""
import json
import re
from pathlib import Path

from .knowledge_space_sets import SETS
from .native_text_projection import COLLECTION, VERSION, normalized, text_index_ready
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite
from ..v2.repository import normalize_tokens, query_lexeme_weights

# Bind continuation to the code loaded by this process, without hashing source
# files or document bodies on each query. New deployments invalidate old cursors.
_ROOT = Path(__file__).parent
_IMPLEMENTATION = semantic_digest({name:(_ROOT / name).read_text() for name in
    ('knowledge_text_search.py','native_text_projection.py','knowledge_space_sets.py','../v2/repository.py')})


# Grammar-only English words are not evidence-bearing candidate votes. Keep
# negation, modality, ordering and comparison words; the original query remains
# unchanged for interpretation. This is neither translation nor alias inference.
_QUERY_GRAMMAR=frozenset('a an the am is are was were be been being do does did what which who whom whose how of by for to'.split())


def ranked_query_weights(query):
    return {term:weight for term,weight in query_lexeme_weights(normalized(query)).items()
        if term not in _QUERY_GRAMMAR}


class KnowledgeTextSearch:
    def __init__(self,sets,index):
        if sets.backend is not index.backend:
            raise ValueError('KNOWLEDGE_TEXT_BACKEND_MISMATCH')
        self.sets,self.index,self.store=sets,index,sets.store

    def _current(self,actor,set_ref,binding,snapshot):
        if self.sets.resolve(actor_id=actor,set_ref=set_ref)!=binding or self.index.changed(snapshot,binding):
            raise ValueError('KNOWLEDGE_TEXT_SEARCH_CHANGED')

    def search(self,*,actor_id,target,query,limit=20,cursor='',namespace=None,kind=None,purpose='model_input',text_match_mode='all_terms'):
        if not isinstance(query,str) or len(query)>2000 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('KNOWLEDGE_TEXT_SEARCH_REQUEST_INVALID')
        if text_match_mode not in ('all_terms','ranked_candidates'):
            raise ValueError('KNOWLEDGE_TEXT_MATCH_MODE_INVALID')
        weights=(ranked_query_weights(query) if text_match_mode=='ranked_candidates'
            else {t:1.0 for t in set(re.findall(r'[^\W_]+',normalized(query)))})
        terms=sorted(weights)
        if not terms or len(terms)>64:
            raise ValueError('KNOWLEDGE_TEXT_SEARCH_TERMS_REQUIRED')
        if purpose not in ('read','model_input'):
            raise ValueError('KNOWLEDGE_TEXT_SEARCH_PURPOSE_INVALID')
        request={'target':target,'query':query,'namespace':namespace,'kind':kind,'limit':limit,
                 'purpose':purpose,'implementation':_IMPLEMENTATION,'text_match_mode':text_match_mode}
        after='';after_score=None
        if cursor:
            if not re.fullmatch(r'text:[0-9a-f]{64}',cursor):raise ValueError('KNOWLEDGE_TEXT_CURSOR_INVALID')
            saved=self.store.get(SETS,cursor)
            if not saved or saved.get('employee_id')!=actor_id:raise ValueError('KNOWLEDGE_TEXT_CURSOR_DENIED')
            material={k:saved[k] for k in ('request','set_ref','snapshot','after','after_score')}
            if 'text:'+semantic_digest(material).split(':')[1]!=cursor or material['request']!=request:
                raise ValueError('KNOWLEDGE_TEXT_CURSOR_CHANGED')
            set_ref,snapshot,after=saved['set_ref'],saved['snapshot'],saved['after']
            after_score=saved['after_score']
        else:
            set_ref=self.sets.issue(actor_id=actor_id,target=target,purpose=purpose)['set_ref']
            snapshot=self.index.changes.snapshot()
        binding=self.sets.resolve(actor_id=actor_id,set_ref=set_ref)
        if binding['purpose']!=purpose:raise ValueError('KNOWLEDGE_TEXT_SEARCH_PURPOSE_INVALID')
        self._current(actor_id,set_ref,binding,snapshot)
        relation=self.sets.backend.relation(binding)
        table=self.index.store._table(COLLECTION)
        # Existing lexical normalization supplies candidate words, not aliases.
        # Rank partial matches by visible-space term rarity; unmatched query
        # words stay explicit so another target/role cannot be silently affirmed.
        query_terms=[{'term':term,'weight':weights[term],
            'grams':sorted({term[i:i+min(3,len(term))]
                for i in range(len(term)-min(3,len(term))+1)})} for term in terms]
        filters=[];extra=[]
        for key,value in (('namespace',namespace),('kind',kind)):
            if value is not None:filters.append(f"c.native_index->>'{key}'=%s");extra.append(value)
        where=' AND '.join(filters) or 'TRUE'
        complete_terms=('' if text_match_mode=='ranked_candidates' else ' HAVING count(*)='+str(len(terms)))
        sql=relation.ctes+f''', documents AS (
 SELECT c.entry->>'stable_id' AS id,c.entry->'content_revision' AS revision,
        c.native_index,p.item_key,
 CASE WHEN c.native_index->>'text_projection_digest' IS NULL
       AND c.native_head->>'text_projection_digest' IS NULL AND p.item_key IS NULL THEN 'unprepared'
      WHEN p.text_digest IS NOT NULL AND p.text_digest=c.native_index->>'text_projection_digest'
       AND p.text_digest=c.native_head->>'text_projection_digest' THEN 'prepared'
      ELSE 'invalid' END AS state
 FROM boi_space_checked c JOIN boi_u u ON u.id=c.entry->>'stable_id'
 LEFT JOIN {table} p ON p.item_key=%s || (c.entry->'content_revision'->>'ref')
 WHERE {where}
), query_terms AS (
 SELECT * FROM jsonb_to_recordset(%s::jsonb) AS t(term text,weight double precision,grams jsonb)
), hits AS (
 SELECT d.id,t.term,t.weight,
        CASE WHEN strpos(lower(d.native_index->>'title'),t.term)>0 THEN 2.0 ELSE 1.0 END AS field_weight
 FROM query_terms t CROSS JOIN {table} p JOIN documents d ON d.item_key=p.item_key
 WHERE d.state='prepared' AND p.text_grams @> t.grams AND strpos(p.text_normalized,t.term)>0
), frequencies AS (
 SELECT term,count(*) AS df FROM hits GROUP BY term
), scored AS (
 SELECT h.id,sum(h.weight*h.field_weight*(1+ln(1+(1.0+(SELECT count(*) FROM documents))/(1+f.df)))) AS score,
        array_agg(h.term ORDER BY h.term) AS matched_terms
 FROM hits h JOIN frequencies f USING(term) GROUP BY h.id{complete_terms}
), matches AS (
 SELECT d.id,d.revision,d.native_index,d.item_key,s.score,s.matched_terms
 FROM documents d JOIN scored s USING(id)
)'''
        params=(*relation.parameters,self.sets.backend.prefix,*extra,json.dumps(query_terms))
        try:
            with self.index.store._connection() as connection,connection.transaction():
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                connection.execute("SET LOCAL statement_timeout='5s'")
                text_index_ready(connection,table)
                counts=connection.execute('WITH '+sql+''' SELECT
 (SELECT count(*) FROM boi_space_checked WHERE NOT valid),
 (SELECT count(*) FROM documents WHERE state='invalid'),
 (SELECT count(*) FROM documents),(SELECT count(*) FROM documents WHERE state='unprepared'),
 (SELECT count(*) FROM matches)''',params).fetchone()
                if counts[0] or counts[1]:raise ValueError('KNOWLEDGE_TEXT_INDEX_CHANGED_OR_UNPREPARED')
                rows=connection.execute('WITH '+sql+f''', page AS (
 SELECT * FROM matches WHERE (%s::double precision IS NULL OR score<%s OR (score=%s AND id>%s)) ORDER BY score DESC,id LIMIT %s)
 SELECT d.id,d.revision,d.native_index->>'title',d.native_index->>'namespace',d.native_index->>'kind',
 ((p.payload->>'wire')::jsonb)->>'body',((p.payload->>'wire')::jsonb)->>'description',
 ((p.payload->>'wire')::jsonb)->>'representation',d.score,d.matched_terms
 FROM page d JOIN {table} p ON p.item_key=d.item_key ORDER BY d.score DESC,d.id''',(*params,after_score,after_score,after_score,after,limit+1)).fetchall()
        except self.index.store.psycopg.Error:
            raise ValueError('KNOWLEDGE_TEXT_INDEX_READ_FAILED') from None
        self._current(actor_id,set_ref,binding,snapshot)
        items=[]
        for row in rows[:limit]:
            body=row[5] or row[6]
            # This excerpt is a navigation hint, not a citation or answer.
            # Keep original spelling; expanded Unicode casefold offsets cannot
            # safely be applied as source-character offsets.
            position=next((i for i in range(0,len(body),240)
                           if any(t in normalized(body[i:i+480]) for t in terms)),0)
            snippet=body[position:position+480]
            items.append({'stable_id':row[0],'revision':row[1],'title':row[2],'namespace':row[3],
                          'kind':row[4],'description':row[6],'snippet':snippet,
                          'body_representation':row[7],'target':binding['target'],
                          'retrieval_score':row[8],'matched_query_terms':row[9],
                          'unmatched_query_terms':sorted(set(terms)-set(row[9])),
                          'fact_established':False})
        next_cursor=None
        if len(rows)>limit:
            material={'request':request,'set_ref':set_ref,'snapshot':snapshot,'after':rows[limit-1][0],'after_score':rows[limit-1][8]}
            next_cursor='text:'+semantic_digest(material).split(':')[1]
            old=self.store.get(SETS,next_cursor);value={**material,'employee_id':actor_id}
            if old is not None and any(old.get(k)!=v for k,v in value.items()):
                raise ValueError('KNOWLEDGE_TEXT_CURSOR_CHANGED')
            if not self.store.atomic_compare_and_write((AtomicWrite(SETS,next_cursor,old,old or value),)):
                raise ValueError('KNOWLEDGE_TEXT_CURSOR_CHANGED')
            self._current(actor_id,set_ref,binding,snapshot)
        return {'contract_version':VERSION,'items':items,'next_cursor':next_cursor,'scope':binding['target'],
                'matching_documents':counts[4],'visible_documents':counts[2],'unprepared_documents':counts[3],
                'retrieval':'ranked_literal_candidates' if text_match_mode=='ranked_candidates' else 'normalized_literal_substrings','query_terms':terms,
                'text_match_mode':text_match_mode,
                'ignored_query_grammar':(sorted(set(query_lexeme_weights(normalized(query)))&_QUERY_GRAMMAR)
                    if text_match_mode=='ranked_candidates' else []),
                'candidate_matching':('partial literal overlap; not target, role or alias equivalence'
                    if text_match_mode=='ranked_candidates' else 'all literal terms; not semantic equivalence'),
                'semantic_selection_complete':False,'use_qualification_granted':False,'source_access_granted':False,
                'raw_source_files':'not_searched','outside_selected_space':'not_searched'}
