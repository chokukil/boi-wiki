"""Server-issued space populations without a materialized member ID tuple.

This is content audience selection, not per-fact semantic/use qualification.
The prepared policy wire is written with native publication; old or inconsistent
indexes block a complete set instead of silently excluding unprepared entries.
"""
from dataclasses import dataclass
import json
import uuid
from typing import Literal

from pydantic import Field

from ..access_policy import CLASSIFICATION_POLICY_VERSION, knowledge_access_policy
from ..v2.atomic_store_contract import AtomicWrite
from ..v2.store import PostgresAgentV2Store
from .knowledge_space_contract import KnowledgeSpaceTarget
from .knowledge_space_store import KnowledgeSpaceStore, EPOCHS
from .semantic_binding_contract import FrozenContract, semantic_digest


SETS = 'knowledge_query_sets'


class KnowledgeSetRead(FrozenContract):
    set_ref: str = Field(pattern=r'^knowledge-set:sha256:[0-9a-f]{64}$')


class KnowledgeSetCreate(FrozenContract):
    target: KnowledgeSpaceTarget = Field(default_factory=KnowledgeSpaceTarget)
    purpose: Literal['read','model_input','cite','export'] = 'model_input'


@dataclass(frozen=True)
class SpaceSetRelation:
    ctes: str
    parameters: tuple


class PostgresSpaceSetBackend:
    """Trusted server store adapter. Prefix only supports isolated store instances.

    Neither SQL, store selection nor prefix is accepted from a query request.
    """
    def __init__(self, store, *, key_prefix='', authority_store=None):
        if not isinstance(store, PostgresAgentV2Store) or not isinstance(key_prefix,str):
            raise ValueError('KNOWLEDGE_SET_POSTGRES_STORE_REQUIRED')
        self.store, self.prefix = store, key_prefix
        self.authority_store=store if authority_store is None else authority_store

    def relation(self, binding):
        table = self.store._table
        # JSON values originate in the pinned policy wire, never in a request's
        # ACL assertion. Live head/revision/receipt equality guards stale rows.
        sql = f"""boi_space_candidates AS (
 SELECT e.payload AS entry,e.employee_id AS partition,h.payload AS head,n.payload AS native_head,
        a.payload AS native_index,r.payload AS receipt,
        (h.payload->>'query_policy_wire')::jsonb AS policy,
        ('sha256:' || encode(sha256(convert_to(h.payload->>'query_policy_wire','UTF8')),'hex')) AS wire_digest
 FROM {table('knowledge_space_entries')} e
 LEFT JOIN {table('knowledge_space_heads')} h ON h.item_key=%s || (e.payload->>'stable_id')
 LEFT JOIN {table('domain_asset_heads')} n ON n.item_key=%s || (e.payload->>'stable_id')
 LEFT JOIN {table('domain_knowledge_assets')} a ON a.item_key=%s || (e.payload->'content_revision'->>'ref')
 LEFT JOIN {table('knowledge_publication_receipts')} r
   ON r.item_key=%s || ((h.payload->>'query_policy_wire')::jsonb->>'publication_manifest_digest')
 WHERE e.employee_id=%s AND left(e.item_key,%s)=%s AND e.payload->>'state'='active'
), boi_space_checked AS (
 SELECT *, COALESCE(
   head->>'state'='active' AND policy->>'state'='active'
   AND entry->>'employee_id'=partition
   AND policy->>'contract_version'='boi/knowledge-space-policy@1'
   AND wire_digest=head->>'policy_payload_digest'
   AND entry->'policy_revision'=head->'policy_revision'
   AND entry->'content_revision'=head->'content_revision'
   AND policy->'content_revision'=head->'content_revision'
   AND native_head->'revision'=head->'content_revision'
   AND native_index->>'record_payload_digest'=head->>'query_native_payload_digest'
   AND receipt->>'manifest_digest'=policy->>'publication_manifest_digest'
   AND policy->>'source_policy_digest'=%s
   AND policy->'targets' @> %s::jsonb
   AND policy->'identity'->>'identity_creator'=head->>'employee_id'
   AND native_index->>'employee_id'=head->>'employee_id'
   AND native_index->>'namespace'=policy->'identity'->>'namespace'
   AND native_index->>'logical_id'=policy->'identity'->>'logical_id'
   AND head->>'query_native_policy_digest'=policy->>'source_policy_digest'
   AND head->>'query_source_manifest_digest'=policy->>'source_closure_digest'
   AND (%s <> 'private' OR policy->'identity'->>'identity_creator'=%s), FALSE) AS valid
 FROM boi_space_candidates
), boi_u AS (
 SELECT DISTINCT entry->>'stable_id' AS id FROM boi_space_checked
 WHERE valid AND policy->>'classification'=ANY(%s)
   AND policy->'allowed_content_uses' ? %s
)"""
        parameters=(self.prefix,self.prefix,self.prefix,self.prefix,binding['partition'],len(self.prefix),self.prefix,
            binding['source_policy_digest'],json.dumps([binding['target']],ensure_ascii=False),
            binding['target']['visibility'],binding['principal'],
            list(binding['allowed_classifications']),binding['purpose'])
        return SpaceSetRelation(sql,parameters)

    def summary(self, binding):
        relation=self.relation(binding)
        try:
            with self.store._connection() as connection:
                with connection.transaction():
                    connection.execute("SET LOCAL statement_timeout = '5s'")
                    row=connection.execute('WITH '+relation.ctes+
                        ' SELECT (SELECT COUNT(*) FROM boi_u),'
                        ' (SELECT COUNT(*) FROM boi_space_checked WHERE NOT valid)',relation.parameters).fetchone()
        except self.store.psycopg.Error:
            raise ValueError('KNOWLEDGE_SET_INDEX_READ_FAILED') from None
        if row[1]:
            raise ValueError('KNOWLEDGE_SET_INDEX_UNPREPARED_OR_CHANGED')
        return int(row[0])


class KnowledgeSpaceSets:
    def __init__(self, spaces, backend):
        if (not isinstance(spaces,KnowledgeSpaceStore) or not isinstance(backend,PostgresSpaceSetBackend)
                or spaces.store is not backend.authority_store):
            raise ValueError('KNOWLEDGE_SET_CURRENT_SPACE_BACKEND_REQUIRED')
        self.spaces,self.backend,self.store=spaces,backend,spaces.store

    def _context(self,actor_id,target,purpose):
        if purpose not in ('read','model_input','cite','export'):
            raise ValueError('KNOWLEDGE_SET_PURPOSE_UNSUPPORTED')
        actor=self.spaces._actor(actor_id)
        target=KnowledgeSpaceTarget.model_validate(target)
        if target.visibility=='team' and target.team_id not in actor.teams:
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        partition=self.spaces.partition(target,actor_id)
        epoch=self.store.get(EPOCHS,partition)
        if epoch is not None and (type(epoch.get('epoch')) is not int or epoch['epoch']<0):
            raise ValueError('KNOWLEDGE_SET_EPOCH_INVALID')
        allowed=[]
        capability={'read':'can_read','model_input':'can_use_in_agent_context',
                    'cite':'can_cite','export':'can_export'}[purpose]
        for classification in ('internal','confidential','restricted'):
            metadata={'visibility':target.visibility,'team_id':target.team_id,'owner':actor_id,
                'classification':classification,'acl_policy':{
                    'private':'acl:private:'+actor_id,'team':'acl:team:'+str(target.team_id),'public':'acl:public'}[target.visibility]}
            decision=knowledge_access_policy(metadata,identity_owner=actor_id,employee_id=actor_id,
                teams=actor.teams,roles=actor.roles)
            if getattr(decision,capability) and 'body' not in decision.redactions:
                allowed.append(classification)
        return {'principal':actor_id,'roles':sorted(actor.roles),'teams':sorted(actor.teams),
            'target':target.model_dump(mode='json'),'partition':partition,'epoch':(epoch or {}).get('epoch',0),
            'source_policy_digest':self.spaces.current_source_policy(),'purpose':purpose,
            'allowed_classifications':allowed,'classification_policy_version':CLASSIFICATION_POLICY_VERSION},epoch

    def issue(self, *, actor_id,target,purpose='read'):
        binding,epoch=self._context(actor_id,target,purpose)
        count=self.backend.summary(binding)
        if self._context(actor_id,target,purpose)[0]!=binding:
            raise ValueError('KNOWLEDGE_SET_AUTHORITY_CHANGED')
        material={'contract_version':'boi/knowledge-space-set@1','binding':binding,'nonce':uuid.uuid4().hex}
        reference='knowledge-set:'+semantic_digest(material)
        row={**material,'employee_id':actor_id}
        fence=epoch or {'employee_id':binding['partition'],'epoch':0}
        if not self.store.atomic_compare_and_write((AtomicWrite(EPOCHS,binding['partition'],epoch,fence),
                AtomicWrite(SETS,reference,None,row))):
            raise ValueError('KNOWLEDGE_SET_ISSUE_STATE_CHANGED')
        self.resolve(actor_id=actor_id,set_ref=reference)
        return {'set_ref':reference,'target':binding['target'],'purpose':purpose,'population_members':count,
            'membership_epoch':binding['epoch'],'member_ids_materialized':False,
            'population_kind':'published_native_content',
            'use_qualification_granted':False,'source_access_granted':False}

    def resolve(self, *, actor_id,set_ref):
        KnowledgeSetRead(set_ref=set_ref)
        row=self.store.get(SETS,set_ref)
        if not row or row.get('employee_id')!=actor_id:
            raise ValueError('KNOWLEDGE_SET_ACCESS_DENIED')
        material={k:row[k] for k in ('contract_version','binding','nonce')}
        if 'knowledge-set:'+semantic_digest(material)!=set_ref:
            raise ValueError('KNOWLEDGE_SET_RECORD_CHANGED')
        old=row['binding']
        current,_=self._context(actor_id,old['target'],old['purpose'])
        if current!=old:
            raise ValueError('KNOWLEDGE_SET_AUTHORITY_CHANGED')
        return current

    def summary(self, *, actor_id,set_ref):
        binding=self.resolve(actor_id=actor_id,set_ref=set_ref)
        count=self.backend.summary(binding)
        if self.resolve(actor_id=actor_id,set_ref=set_ref)!=binding:
            raise ValueError('KNOWLEDGE_SET_AUTHORITY_CHANGED')
        return {'set_ref':set_ref,'population_members':count,'member_ids_materialized':False,
                'population_kind':'published_native_content',
                'use_qualification_granted':False,'source_access_granted':False}
