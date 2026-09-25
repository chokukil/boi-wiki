"""Published OKF parameters through the existing Formula execution boundary."""
import json

from ..governed_runtime.knowledge_content import decode_knowledge_content
from ..governed_runtime.knowledge_formula_contract import check_parameter_definitions,formula_scope_reasons,CAPABILITY
from ..governed_runtime.knowledge_profile_projector import native_identity
from ..governed_runtime.knowledge_source_access import KnowledgeSourceAccess
from ..governed_runtime.knowledge_use_contract import typed_use_closure
from ..governed_runtime.knowledge_use_reader import KnowledgeUseReader
from ..governed_runtime.semantic_binding_contract import RevisionRef,semantic_digest
from ..governed_runtime.svid_contract import CandidateParameter,KnowledgeParameterIdentity,ParameterSelection,resolve_parameter
from ..governed_runtime.typed_knowledge_meaning import TypedKnowledgeMeaning


def read_knowledge_parameter(work,authorization,*,selection,qualification_revision,require_current=True):
    selected=ParameterSelection.model_validate(selection)
    if not isinstance(selected.identity,KnowledgeParameterIdentity):
        raise ValueError('KNOWLEDGE_FORMULA_IDENTITY_REQUIRED')
    if selected.semantic_role is None:
        raise ValueError('KNOWLEDGE_FORMULA_EXPLICIT_ROLE_REQUIRED')
    spaces=getattr(work,'knowledge_spaces',None)
    current_authorization=getattr(work,'current_knowledge_authorization',None)
    if spaces is None or not callable(current_authorization):
        raise ValueError('KNOWLEDGE_FORMULA_CURRENT_SPACE_REQUIRED')
    reader=KnowledgeUseReader(spaces)
    sources=KnowledgeSourceAccess(spaces,current_authorization=current_authorization)
    actor=authorization.principal
    if current_authorization()!=authorization:raise ValueError('KNOWLEDGE_FORMULA_AUTHORITY_CHANGED')
    observed={};source_refs={}
    def read(revision):
        allowed,native=reader._access(actor,revision)
        access,record,asset=spaces.read(actor_id=actor,stable_id=allowed.identity.stable_id,
            revision=revision,purpose='model_input')
        if native.record_id!=record.record_id or allowed!=access:
            raise ValueError('KNOWLEDGE_FORMULA_AUTHORITY_CHANGED')
        if revision in observed and observed[revision]!=access:
            raise ValueError('KNOWLEDGE_FORMULA_AUTHORITY_CHANGED')
        observed[revision]=access
        for source in record.payload['sources']:
            _,receipt=sources.read(actor_id=actor,source=source,model_input=True)
            key=source['artifact_ref']
            if key in source_refs and source_refs[key]!=receipt:
                raise ValueError('KNOWLEDGE_FORMULA_SOURCE_CHANGED')
            source_refs[key]=receipt
        return record,asset
    record,asset=read(selected.revision)
    if native_identity(record)!=selected.identity.knowledge_id:
        raise ValueError('KNOWLEDGE_FORMULA_IDENTITY_MISMATCH')
    if require_current:
        head,_=spaces.authorize(actor_id=actor,stable_id=selected.identity.knowledge_id,purpose='model_input')
        if head.content_revision!=selected.revision:
            raise ValueError('KNOWLEDGE_FORMULA_CURRENT_REVISION_REQUIRED')
    content=decode_knowledge_content(json.loads(asset.content_json))
    if content is None:raise ValueError('KNOWLEDGE_FORMULA_CONTENT_REQUIRED')
    meaning=TypedKnowledgeMeaning.model_validate(content.meaning)
    matches=[(i,p) for i,p in enumerate(meaning.parameters) if p.id==selected.identity.parameter_id]
    if len(matches)!=1:raise ValueError('KNOWLEDGE_FORMULA_PARAMETER_NOT_FOUND')
    index,parameter=matches[0];pointer=f'/parameters/{index}'
    contract=next((u for u in content.use_contracts if u.purpose=='formula_input'),None)
    if contract is None:raise ValueError('KNOWLEDGE_FORMULA_USE_CONTRACT_REQUIRED')
    scope=typed_use_closure(content,contract)
    if pointer not in scope['roots'] or formula_scope_reasons(scope):
        raise ValueError('KNOWLEDGE_FORMULA_SCOPE_NOT_SUPPORTED')
    options={} if require_current else {'recorded_reference':qualification_revision}
    qualified,before=reader._current(actor,selected.revision,'formula_input',**options)
    if qualified is None:raise ValueError('KNOWLEDGE_FORMULA_QUALIFICATION_REQUIRED')
    value,reference=qualified
    if (reference!=qualification_revision or value['status']!='usable_with_limits'
            or value['scope_digest']!=scope['scope_digest'] or value['roots']!=list(scope['roots'])
            or value['closure']!=list(scope['closure']) or value.get('reasons')):
        raise ValueError('KNOWLEDGE_FORMULA_QUALIFICATION_CHANGED')
    assessed={n['pointer']:n for n in value['assessed_nodes']}
    if set(assessed)!=set(scope['nodes']) or any(assessed[p]['native_value_digest']!=semantic_digest(node)
            or assessed[p]['judgment']['label']!='supported' for p,node in scope['nodes'].items()):
        raise ValueError('KNOWLEDGE_FORMULA_NODE_QUALIFICATION_CHANGED')
    from ..governed_runtime.formula_definition_context import resolve_calculation_context,SCOPE_VERSION,BASIS
    calculation_context=resolve_calculation_context(scope,pointer)
    if calculation_context is not None:
        declared=value.get('formula_scope',{})
        if (declared.get('contract_version')!=SCOPE_VERSION or declared.get('claim_basis')!=BASIS
                or declared.get('scope_digest')!=scope['scope_digest'] or declared.get('blocked_reasons')
                or declared.get('contexts',{}).get(pointer)!=calculation_context
                or declared.get('binding',{}).get('knowledge_revision')!=selected.revision.model_dump(mode='json')):
            raise ValueError('KNOWLEDGE_FORMULA_CONTEXT_QUALIFICATION_CHANGED')
    report=reader.ledger.read(value['mechanical_check_ref']['ref']).payload['report']
    if not any(c['capability']==CAPABILITY and c['outcome']=='satisfied' for c in report['checks']):
        raise ValueError('KNOWLEDGE_FORMULA_REGISTERED_CHECK_REQUIRED')
    unit,quantity=check_parameter_definitions(parameter,asset,read)
    descriptor=parameter.semantic_descriptor
    candidate=CandidateParameter(identity=selected.identity,revision=selected.revision,
        component=parameter.component,quantity=parameter.quantity,unit=unit.unit_id,
        parameter_name=parameter.parameter_name,semantic_descriptor=descriptor,semantic_role=descriptor.role,
        source_locator=None,binding_status='unverified')
    result=resolve_parameter((candidate,),selected)
    for dependency in report['native_inputs']:read(RevisionRef.model_validate(dependency['revision']))
    _,after=reader._current(actor,selected.revision,'formula_input',**options)
    if before!=after or current_authorization()!=authorization:
        raise ValueError('KNOWLEDGE_FORMULA_AUTHORITY_CHANGED')
    for revision in tuple(observed):read(revision)
    return {**result,'definition_content':parameter.model_dump(mode='json'),
        'knowledge_qualification':{'reference':reference.model_dump(mode='json'),'meaning_pointer':pointer,
            'scope_digest':value['scope_digest'],'purpose':'formula_input','status':value['status']},
        'quantity_definition_resolution':quantity,'required_unit_definition':unit.model_dump(mode='json'),
        **({'calculation_context':calculation_context,
            'reviewed_source_limits':value['formula_scope']['reviewed_items']} if calculation_context is not None else {}),
        'limitations':value['limitations'],'evidence_bindings':[b.model_dump(mode='json') for b in content.evidence_bindings
            if any(b.meaning_pointer==p or b.meaning_pointer.startswith(p+'/') for p in scope['closure'])],
        'semantic_truth_proven':False,'live_execution_ready':False}
