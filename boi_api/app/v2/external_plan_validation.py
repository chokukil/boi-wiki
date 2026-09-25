"""Read-only compilation of explicit plans; never grants execution or discourse truth."""
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from fastapi import HTTPException
from .models import SemanticPlanV4
from .semantic_kernel import SemanticPlanningError

class ExternalPlanValidation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    semantic_plan: SemanticPlanV4
    reference_scope: list[str]=Field(default_factory=list,max_length=32)
    selected_refs: list[str]=Field(default_factory=list,max_length=32)

def validate_external_plan(runtime,resolve,capability_id,question,value):
    try:submission=ExternalPlanValidation.model_validate(value)
    except ValidationError:raise HTTPException(422,detail={'reason_code':'STRUCTURED_PLAN_INVALID'}) from None
    scope=set(submission.reference_scope);selected=set(submission.selected_refs)
    if not selected<=scope:raise HTTPException(422,detail={'reason_code':'STRUCTURED_SELECTION_OUTSIDE_SCOPE'})
    refs=scope|{x.entity_ref for x in submission.semantic_plan.subjects if x.resolution=='resolved'}
    records={}
    for ref in sorted(refs):
        record=resolve(ref)
        if record is None or record.record_id!=ref:raise HTTPException(403,detail={'reason_code':'STRUCTURED_REFERENCE_NOT_VISIBLE'})
        records[ref]=record
    state={'question':question,'trusted_targets':{r:r for r in records},'trusted_entity_kinds':{r:x.kind for r,x in records.items()},'selected_subject_refs':submission.selected_refs,'conversation_context':{'topic_state':{'subjects':submission.reference_scope,'entities':submission.reference_scope}},'knowledge_hints':[]}
    try:
        compiled,report=runtime._validate_v4_envelope(state,{'semantic_plan':submission.semantic_plan.model_dump(mode='json')})
    except SemanticPlanningError as error:
        raise HTTPException(409,detail={'reason_code':error.code,'message':str(error),'execution_authority_granted':False,'automatic_retry':False}) from None
    if compiled.capability_id!=capability_id:raise HTTPException(409,detail={'reason_code':'STRUCTURED_CAPABILITY_MISMATCH'})
    return {'valid':True,'validation':report,'semantic_plan':compiled.semantic_plan.model_dump(mode='json'),'capability_id':compiled.capability_id,'model_calls':0,'execution_authority_granted':False,'semantic_truth_proven':False,'reference_scope_basis':'caller_declared_acl_checked_scope_not_verified_conversation_history'}
