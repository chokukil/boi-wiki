"""Protected saved knowledge evidence results with expiring bound cursors.

Reuses the existing protected execution repository and Run ledger. Cursor expiry
does not expire the stored result. Access/qualification fences are checked on
every read; this internal service does not supply or infer those permissions.
"""
import base64
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Literal
import uuid

from pydantic import JsonValue

from .knowledge_projection_contract import ProjectionContract
from .knowledge_projection_store import ProjectionSnapshot, encoded
from .knowledge_query import KnowledgeQueryAccess, KnowledgeEvidenceQuery
from .protected_execution_repository import ProtectedExecutionRepository, digest
from .semantic_binding_contract import semantic_digest


PREFIX='protected:knowledge-query:'
BLOCK_SIZE=100


class SavedKnowledgeExecution(ProjectionContract):
    contract_version: Literal['boi/protected-knowledge-evidence-execution@1']='boi/protected-knowledge-evidence-execution@1'
    execution_id: str
    access: dict[str,JsonValue]
    query: dict[str,JsonValue]
    result: dict[str,JsonValue]
    receipt: dict[str,JsonValue]
    exploration_receipt: dict[str,JsonValue]


class KnowledgeQueryResultService:
    def __init__(self,engine,repository:ProtectedExecutionRepository,*,clock=time.time,cursor_ttl_seconds=900):
        if type(cursor_ttl_seconds) is not int or not 1<=cursor_ttl_seconds<=86400:
            raise ValueError('KNOWLEDGE_CURSOR_TTL_INVALID')
        self.engine,self.repository,self.clock=engine,repository,clock
        self.ttl=cursor_ttl_seconds
        self.root=repository.root/'knowledge-results'
        self.pages=self.root/'pages'
        self.pages.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root.chmod(0o700);self.pages.chmod(0o700)
        key=self.root/'cursor-key'
        # Creation and readers serialize on the repository's established lock.
        with repository._locked('knowledge-cursor-key'):
            if not key.exists():
                with key.open('xb') as handle:
                    handle.write(secrets.token_bytes(32));handle.flush();os.fsync(handle.fileno())
                key.chmod(0o600)
                fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(fd)
                finally:os.close(fd)
            self.key=key.read_bytes()
        if len(self.key)!=32:raise ValueError('KNOWLEDGE_CURSOR_KEY_INVALID')

    def _save_rows(self,result):
        manifests={}
        for group in ('all','supported','refuted','conflicted','unknown'):
            rows=[r for r in result['rows'] if group=='all' or r['state']==group]
            pages=[]
            for offset in range(0,len(rows),BLOCK_SIZE):
                block={'contract_version':'boi/knowledge-evidence-page-block@1','result_digest':result['result_digest'],
                    'group':group,'offset':offset,'rows':rows[offset:offset+BLOCK_SIZE]}
                block_digest=digest(block)
                self.repository._immutable(self.pages/(block_digest[7:]+'.json'),block)
                pages.append(block_digest)
            manifests[group]={'count':len(rows),'pages':pages}
        return {k:v for k,v in result.items() if k not in ('rows','protected_result_ref')}|{'row_groups':manifests}

    def execute(self,access,query,*,idempotency_key):
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=240:
            raise ValueError('KNOWLEDGE_QUERY_IDEMPOTENCY_REQUIRED')
        query=KnowledgeEvidenceQuery.model_validate(query.model_dump(mode='json'))
        admission=self.engine.authorize_access(access,'execute_before')
        request_digest=semantic_digest({'contract_version':'boi/protected-knowledge-evidence-execution@1',
            'access':asdict(access),'query':query.model_dump(mode='json'),'authority':asdict(admission)})
        def run():
            try:
                result=self.engine.execute(access,query)
            except ValueError as error:
                code=str(error)
                if (len(code)>120 or not code.startswith(('KNOWLEDGE_','PROJECTION_'))
                        or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code)):
                    code='KNOWLEDGE_QUERY_VALIDATION_FAILED'
                result={'contract_version':'boi/knowledge-evidence-result@1','execution_state':'failed',
                    'query_digest':semantic_digest(query),'access_digest':admission.access_digest,
                    'authority_digest':admission.authority_digest,'snapshot':asdict(access.snapshot),
                    'counts':None,'rows':[],'coverage':{'execution_completeness':'failed',
                        'source_interpretation_completeness':'not_established','real_world_completeness_proven':False},
                    'reason_code':code,'claim_basis':query.claim_basis,'modality':query.modality,'polarity':query.polarity,
                    'time_mode':query.time_mode,'as_of':query.model_dump(mode='json')['as_of'],
                    'scenario':[v.model_dump(mode='json') for v in query.scenario],'semantic_truth_proven':False}
                result['result_digest']=semantic_digest(result)
            if result['authority_digest']!=admission.authority_digest:
                raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
            saved=self._save_rows(result)
            receipt={'contract_version':'boi/knowledge-evidence-execution-receipt@1',
                'completed_at':datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),
                'result_digest':result['result_digest'],'saved_result_digest':digest(saved),
                'logical_plan_digest':result['query_digest'],'request_digest':request_digest,
                'access_digest':result['access_digest'],'authority_digest':result['authority_digest']}
            receipt['receipt_digest']=digest(receipt)
            return SavedKnowledgeExecution(execution_id=str(uuid.uuid4()),
                access={**asdict(access),'member_ids':list(access.member_ids)},
                query=query.model_dump(mode='json'),result=saved,receipt=receipt,exploration_receipt=receipt)
        result=self.repository.execute_once(principal=access.principal,purpose=access.purpose,
            idempotency_key=idempotency_key,request_digest=request_digest,execute=run)
        if self.engine.authorize_access(access,'execute_after')!=admission:
            raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
        return {'contract_version':'boi/knowledge-query-execution@1',
            'state':'failed' if result['result']['execution_state']=='failed' else 'stored',
            'result_ref':PREFIX+result['execution_id'],'result_digest':result['receipt']['result_digest'],
            'counts':result['result']['counts'],'coverage':result['result']['coverage'],
            'snapshot':result['result']['snapshot'],'reason_code':result['result'].get('reason_code'),
            'semantic_truth_proven':False}

    @staticmethod
    def _access(value):
        return KnowledgeQueryAccess(**{**value,'snapshot':ProjectionSnapshot(**value['snapshot']),
            'member_ids':tuple(value['member_ids'])})

    def _cursor(self,value):
        raw=base64.urlsafe_b64encode(encoded(value).encode()).decode().rstrip('=')
        return raw+'.'+hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()

    def _cursor_value(self,cursor):
        try:
            if not isinstance(cursor,str) or len(cursor)>4096:raise ValueError()
            raw,signature=cursor.split('.')
            if not hmac.compare_digest(signature,hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()):raise ValueError()
            value=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError,TypeError,UnicodeError):
            raise ValueError('KNOWLEDGE_CURSOR_INVALID') from None

    def read(self,result_ref,*,principal,purpose,group='supported',page_size=20,cursor=None):
        if (not isinstance(result_ref,str) or not result_ref.startswith(PREFIX)
                or group not in ('all','supported','refuted','conflicted','unknown')
                or type(page_size) is not int or not 1<=page_size<=100):
            raise ValueError('KNOWLEDGE_RESULT_REQUEST_INVALID')
        execution=self.repository.get(result_ref.removeprefix(PREFIX))
        if not execution or execution.get('contract_version')!='boi/protected-knowledge-evidence-execution@1':
            raise ValueError('KNOWLEDGE_RESULT_UNAVAILABLE')
        access=self._access(execution['access'])
        if (principal,purpose)!=(access.principal,access.purpose):raise ValueError('KNOWLEDGE_RESULT_ACCESS_DENIED')
        admitted=self.engine.authorize_access(access,'read_before')
        receipt=execution['receipt'];result=execution['result']
        if (admitted.authority_digest!=receipt['authority_digest'] or admitted.access_digest!=receipt['access_digest']):
            raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
        if digest(result)!=receipt['saved_result_digest'] or result['result_digest']!=receipt['result_digest']:
            raise ValueError('KNOWLEDGE_RESULT_BINDING_INVALID')
        binding={'contract_version':'boi/knowledge-result-cursor@1','result_ref':result_ref,
            'result_digest':receipt['result_digest'],'access_digest':admitted.access_digest,
            'authority_digest':admitted.authority_digest,'group':group,'page_size':page_size}
        manifest=result['row_groups'][group]
        offset=0;expires=self.clock()+self.ttl
        if cursor is not None:
            value=self._cursor_value(cursor)
            offset,expires=value.get('offset'),value.get('expires_at')
            if (value!={**binding,'offset':offset,'expires_at':expires} or type(offset) is not int
                    or offset<=0 or offset>=manifest['count'] or offset%page_size
                    or type(expires) not in (int,float)):
                raise ValueError('KNOWLEDGE_CURSOR_BINDING_INVALID')
            if self.clock()>=expires:raise ValueError('KNOWLEDGE_CURSOR_EXPIRED')
        stop=min(offset+page_size,manifest['count']);rows=[]
        for block_index in range(offset//BLOCK_SIZE,(stop+BLOCK_SIZE-1)//BLOCK_SIZE):
            block_digest=manifest['pages'][block_index]
            try:
                block=json.loads((self.pages/(block_digest[7:]+'.json')).read_bytes())
            except (OSError,ValueError):raise ValueError('KNOWLEDGE_RESULT_PAGE_UNAVAILABLE') from None
            if (digest(block)!=block_digest or block.get('result_digest')!=receipt['result_digest']
                    or block.get('group')!=group or block.get('offset')!=block_index*BLOCK_SIZE):
                raise ValueError('KNOWLEDGE_RESULT_PAGE_TAMPERED')
            rows.extend(block['rows'][max(0,offset-block['offset']):min(BLOCK_SIZE,stop-block['offset'])])
        if len(rows)!=stop-offset:raise ValueError('KNOWLEDGE_RESULT_PAGE_COUNT_MISMATCH')
        if self.engine.authorize_access(access,'read_after')!=admitted:
            raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
        next_cursor=self._cursor({**binding,'offset':stop,'expires_at':expires}) if stop<manifest['count'] else None
        failed=result['execution_state']=='failed'
        return {'contract_version':'boi/knowledge-query-page@1','execution_state':'failed' if failed else 'saved_result_read',
            'result_ref':result_ref,'result_digest':receipt['result_digest'],'snapshot':result['snapshot'],
            'counts':result['counts'],'coverage':result['coverage'],'claim_basis':result['claim_basis'],
            'modality':result['modality'],'polarity':result['polarity'],'time_mode':result['time_mode'],
            'as_of':result['as_of'],'scenario':result['scenario'],'reason_code':result.get('reason_code'),
            'group':group,'group_count':None if failed else manifest['count'],
            'rows':rows,'page_digest':digest(rows),'next_cursor':next_cursor,'cursor_expires_at':expires,
            'semantic_truth_proven':False}
