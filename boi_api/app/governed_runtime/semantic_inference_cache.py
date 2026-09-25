"""Shared frozen semantic inference cache, with no semantic-pass authority."""
from dataclasses import dataclass
from typing import Literal
import hashlib,json
from pydantic import Field
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Digest,Ref,semantic_digest
from boi_api.app.governed_runtime.local_model_routing import LocalModelRunIdentity,LocalModelPolicy,decide_pi_execution
from boi_api.app.governed_runtime.bulk_migration_execution import _safe_value
from boi_api.app.v2.atomic_store_contract import AtomicWrite


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()
def digest_bytes(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


class SemanticInferenceRequest(FrozenContract):
    contract_version:Literal['boi/semantic-inference-request@1']='boi/semantic-inference-request@1'
    principal_id:Ref
    acl_policy_digest:Digest
    namespace:Ref
    source_profile_digest:Digest
    semantic_input_digest:Digest
    definition_closure_digest:Digest
    output_contract_digest:Digest
    skill_id:Literal['domain-ontology-draft','existing-concept-match']
    model_id:Ref
    model_digest:Digest
    role_digest:Digest
    prompt_digest:Digest
    input_digest:Digest
    input_bytes:int=Field(ge=1,le=11264)
    atomic_unit_count:int=Field(ge=1,le=4)

    @property
    def cache_key(self):return semantic_digest(self)


class SemanticInferenceRequestV2(SemanticInferenceRequest):
    """Same <=11 KiB source payload plus explicitly accounted protocol overhead.

    Wire includes the versioned role/tool schema, not more source or raw rows.
    The complete HTTP JSON is also bounded; old request/cache identity is intact.
    """
    contract_version:Literal['boi/semantic-inference-request@2']='boi/semantic-inference-request@2'
    wire_contract_version:Literal['boi/metadata-model-wire@1']='boi/metadata-model-wire@1'
    wire_request_digest:Digest
    wire_input_bytes:int=Field(ge=1,le=36864)


class QueryIntentInferenceRequest(SemanticInferenceRequest):
    """Forward query use of the same frozen-candidate store and claim protocol."""
    contract_version:Literal['boi/semantic-inference-request@3']='boi/semantic-inference-request@3'
    skill_id:Literal['query-intent']='query-intent'
    atomic_unit_count:int=Field(ge=1,le=64)


class InferenceAttemptContext(FrozenContract):
    run_ref:Ref
    shard_ref:Ref
    unresolved_reason:Ref
    evidence_span_refs:tuple[Ref,...]=Field(min_length=1)
    evidence_closure_digest:Digest
    channel:Literal['ui','mcp','rest','cli']


@dataclass(frozen=True)
class FrozenInferenceResult:
    status:str
    output:dict|None
    reason_code:str|None
    cache_key:str
    outcome_digest:str|None
    invocation_count:int
    cache_hit_count:int
    input_bytes:int
    # Successful inference is merely a frozen proposal, not semantic validation.
    semantic_qualified:bool=False


class FrozenSemanticInferenceCache:
    def __init__(self,store):self.store=store

    def _get(self,collection,key):return self.store.get(collection,key)

    def _immutable(self,collection,key,value):
        existing=self._get(collection,key)
        if existing:
            if {k:v for k,v in existing.items() if k!='updated_at'}!=value:
                raise ValueError('SEMANTIC_CACHE_IMMUTABLE_RECORD_DRIFT')
            return
        if not self.store.atomic_compare_and_write((AtomicWrite(collection,key,None,value),)):
            existing=self._get(collection,key)
            if not existing or {k:v for k,v in existing.items() if k!='updated_at'}!=value:
                raise ValueError('SEMANTIC_CACHE_IMMUTABLE_RECORD_DRIFT')

    @staticmethod
    def _verify_outcome(outcome,request,output_model):
        if outcome.get('request_digest')!=request.cache_key or outcome.get('employee_id')!=request.principal_id:
            raise ValueError('SEMANTIC_CACHE_INPUT_OR_OWNER_DRIFT')
        payload={key:value for key,value in outcome.items() if key not in {'outcome_digest','updated_at'}}
        if semantic_digest(payload)!=outcome.get('outcome_digest'):
            raise ValueError('SEMANTIC_CACHE_OUTCOME_DIGEST_DRIFT')
        if outcome['status']=='PROVISIONAL':
            if len(canonical(outcome['output']))>11264:
                raise ValueError('SEMANTIC_OUTPUT_SCOPE_SHARD_REQUIRED')
            if semantic_digest(outcome['output'])!=outcome['output_digest']:
                raise ValueError('SEMANTIC_CACHE_OUTPUT_DIGEST_DRIFT')
            _safe_value(outcome['output'])
            if output_model.model_validate(outcome['output']).model_dump(mode='json')!=outcome['output']:
                raise ValueError('SEMANTIC_CACHE_OUTPUT_CONTRACT_DRIFT')
        elif outcome['status']!='BLOCKED':
            raise ValueError('SEMANTIC_CACHE_OUTCOME_STATUS_INVALID')

    def run_frozen(self,*,request,attempt,payload,identity,policy,invoke,output_model,deterministically_resolved=False,allow_inference=True,
                   model_request=None):
        model={'boi/semantic-inference-request@1':SemanticInferenceRequest,
            'boi/semantic-inference-request@2':SemanticInferenceRequestV2,
            'boi/semantic-inference-request@3':QueryIntentInferenceRequest}.get(request.contract_version)
        if model is None:raise ValueError('SEMANTIC_INFERENCE_REQUEST_VERSION_UNSUPPORTED')
        request=model.model_validate(request.model_dump(mode='json'))
        attempt=InferenceAttemptContext.model_validate(attempt.model_dump(mode='json'))
        if deterministically_resolved:raise ValueError('RESOLVED_SEMANTIC_INPUT_MUST_NOT_INVOKE_PI')
        if (output_model.model_config.get('extra')!='forbid'
            or request.output_contract_digest!=semantic_digest(output_model.model_json_schema())):
            raise ValueError('SEMANTIC_OUTPUT_SCHEMA_BINDING_MISMATCH')
        _safe_value(payload)
        encoded=canonical(payload)
        if request.input_digest!=digest_bytes(encoded) or request.input_bytes!=len(encoded):
            raise ValueError('SEMANTIC_INFERENCE_INPUT_BINDING_MISMATCH')
        if isinstance(request,SemanticInferenceRequestV2):
            if (not isinstance(model_request,dict) or semantic_digest(model_request)!=request.wire_request_digest
                or len(canonical(model_request))!=request.wire_input_bytes):
                raise ValueError('SEMANTIC_MODEL_WIRE_BINDING_MISMATCH')
        elif model_request is not None:
            raise ValueError('SEMANTIC_MODEL_WIRE_CONTRACT_REQUIRED')
        counted_bytes=request.wire_input_bytes if isinstance(request,SemanticInferenceRequestV2) else request.input_bytes
        key=request.cache_key
        slot=self._get('bulk_migration_semantic_cache',key)
        outcome=self._get('bulk_migration_semantic_cache_receipts',key)
        if outcome:
            self._verify_outcome(outcome,request,output_model)
            if not slot or slot.get('request_digest')!=key or slot.get('employee_id')!=request.principal_id:
                raise ValueError('SEMANTIC_CACHE_SLOT_UNBOUND')
            invocation=self._get('bulk_migration_model_invocations',key)
            if (slot.get('request')!=request.model_dump(mode='json') or not invocation
                or invocation.get('request')!=slot['request']
                or semantic_digest(invocation.get('attempt'))!=slot.get('attempt_digest')):
                raise ValueError('SEMANTIC_CACHE_INVOCATION_BINDING_DRIFT')
            # Recovery of a saved outcome is deterministic, never a new inference.
            if slot['state']=='reserved':
                self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_semantic_cache',key,slot,
                    {**slot,'state':'completed','outcome_digest':outcome['outcome_digest']}),))
                slot=self._get('bulk_migration_semantic_cache',key)
            if slot.get('outcome_digest')!=outcome['outcome_digest']:
                raise ValueError('SEMANTIC_CACHE_SLOT_OUTCOME_DRIFT')
            access={'request_digest':key,'employee_id':request.principal_id,'attempt':attempt.model_dump(mode='json'),
                    'outcome_digest':outcome['outcome_digest'],'event_kind':'cache_access','invocation_count':0}
            self._immutable('bulk_migration_semantic_cache_access',semantic_digest(access),access)
            return FrozenInferenceResult(outcome['status'],outcome['output'],outcome['reason_code'],key,
                outcome['outcome_digest'],0,1 if outcome['status']=='PROVISIONAL' else 0,counted_bytes)
        if slot:
            return FrozenInferenceResult('BLOCKED',None,'INFERENCE_PENDING_OR_OUTCOME_UNCERTAIN',key,None,0,0,counted_bytes)
        if not allow_inference:
            return FrozenInferenceResult('BLOCKED',None,'WORKER_FROZEN_INFERENCE_REQUIRED',key,None,0,0,counted_bytes)
        health=decide_pi_execution(identity,policy)
        if health.status!='READY' or any(getattr(identity,k)!=getattr(request,k) for k in ('model_id','model_digest','role_digest','prompt_digest')):
            return FrozenInferenceResult('BLOCKED',None,'SEMANTIC_MODEL_IDENTITY_NOT_READY',key,None,0,0,counted_bytes)
        stamp={'request_digest':key,'employee_id':request.principal_id,'state':'reserved',
               'request':request.model_dump(mode='json'),'attempt_digest':semantic_digest(attempt),'outcome_digest':None}
        invocation={'request_digest':key,'employee_id':request.principal_id,'event_kind':'inference_request',
                    'request':request.model_dump(mode='json'),'attempt':attempt.model_dump(mode='json'),
                    'invocation_count':1}
        won=self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_semantic_cache',key,None,stamp),
            AtomicWrite('bulk_migration_model_invocations',key,None,invocation)))
        if not won:
            return FrozenInferenceResult('BLOCKED',None,'INFERENCE_ALREADY_CLAIMED',key,None,0,0,counted_bytes)
        claimed=self._get('bulk_migration_semantic_cache',key)
        try:
            output=output_model.model_validate(invoke(payload)).model_dump(mode='json');_safe_value(output)
            if len(canonical(output))>11264:raise ValueError('SEMANTIC_OUTPUT_SCOPE_SHARD_REQUIRED')
            status='PROVISIONAL';reason=None;output_digest=semantic_digest(output)
        except Exception:
            # No raw prompt/output/exception body goes into the failure receipt.
            output=None;output_digest=None;status='BLOCKED';reason='LOCAL_MODEL_OR_OUTPUT_CONTRACT_FAILED'
        outcome={'request_digest':key,'employee_id':request.principal_id,'status':status,
                 'output':output,'output_digest':output_digest,'reason_code':reason,
                 'invocation_count':1,'semantic_qualified':False}
        outcome['outcome_digest']=semantic_digest(outcome)
        # Preserve the immutable outcome before updating the mutable cache slot.
        # A crash here is repaired above without another model invocation.
        self._immutable('bulk_migration_semantic_cache_receipts',key,outcome)
        current=self._get('bulk_migration_semantic_cache',key)
        # A concurrent reader may have repaired the saved-outcome boundary.
        # Accept only the exact claimed slot plus the identical frozen outcome.
        completed={**claimed,'state':'completed','outcome_digest':outcome['outcome_digest']}
        if current==completed:
            return FrozenInferenceResult(status,output,reason,key,outcome['outcome_digest'],1,0,counted_bytes)
        if current!=claimed or not self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_semantic_cache',key,claimed,
            completed),)):
            if self._get('bulk_migration_semantic_cache',key)==completed:
                return FrozenInferenceResult(status,output,reason,key,outcome['outcome_digest'],1,0,counted_bytes)
            return FrozenInferenceResult('BLOCKED',None,'CACHE_OUTCOME_SAVED_NOT_BOUND',key,outcome['outcome_digest'],1,0,counted_bytes)
        return FrozenInferenceResult(status,output,reason,key,outcome['outcome_digest'],1,0,counted_bytes)
