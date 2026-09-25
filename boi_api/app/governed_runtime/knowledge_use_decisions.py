"""Exact use-decision ancestry and CAS proposals. Callers supply current authority."""
from .ledger import LedgerError, RecordKind, record_digest
from .semantic_binding_contract import RevisionRef, semantic_digest
from .knowledge_statement_contract import (REPORTED_STATEMENT_EXISTS,
    STATEMENT_SCOPE_VERSION, STATEMENT_USE_PURPOSE, statement_support_contract,
    statement_versions, traversal_support_contract, MODAL_STATEMENT_SCOPE_VERSION,
    modal_statement_support_contract)
from ..v2.atomic_store_contract import AtomicWrite


QUALIFICATIONS = 'knowledge_use_qualifications'


def decision_key(revision, purpose):
    return 'knowledge-use:' + semantic_digest([revision.model_dump(mode='json'),purpose])


def predecessor(ledger, reference, *, revision, purpose, stable_id):
    try:
        record = ledger.read(reference.ref)
    except LedgerError:
        raise ValueError('KNOWLEDGE_USE_SUPERSESSION_BINDING_MISMATCH') from None
    value = record.payload
    if (record.kind != RecordKind.KNOWLEDGE_USE_QUALIFICATION or record.authority != 'qualification_service'
            or record_digest(record.record_id) != reference.revision_digest
            or value.get('contract_version') != 'boi/knowledge-use-qualification@1'
            or value.get('knowledge_revision') != revision.model_dump(mode='json')
            or value.get('stable_id') != stable_id or value.get('purpose') != purpose):
        raise ValueError('KNOWLEDGE_USE_SUPERSESSION_BINDING_MISMATCH')
    return record


def decision_entry(record):
    value=record.payload
    return {'employee_id':value.get('qualified_by',value['provenance']['authenticated_principal']),
        'revision':value['knowledge_revision'],'purpose':value['purpose'],
        'qualification_ref':{'ref':record.record_id,'revision_digest':record_digest(record.record_id)},
        'payload_digest':semantic_digest(value),'status':value['status']}


def require_current(record, entry):
    if entry is None or {k:v for k,v in entry.items() if k != 'updated_at'} != decision_entry(record):
        raise ValueError('KNOWLEDGE_USE_SUPERSESSION_CURRENT_CHANGED')


def decision_write(store, record, *, previous=None):
    value=decision_entry(record)
    key=decision_key(RevisionRef.model_validate(value['revision']),value['purpose'])
    old=store.get(QUALIFICATIONS,key)
    identical=old is not None and {k:v for k,v in old.items() if k != 'updated_at'}==value
    if previous is not None and not identical:
        require_current(previous,old)
    elif previous is None and old is not None and not identical:
        raise ValueError('KNOWLEDGE_USE_CURRENT_DECISION_CONFLICT')
    current=old if identical else value
    return AtomicWrite(QUALIFICATIONS,key,old,current), current


def source_opinion_reasons(policy, purpose, contract, scope, judgments, *, mechanical_report=None,
        statement_scope=None,formula_scope=None):
    reasons=[]
    if purpose not in policy['purposes']:
        reasons.append('REGISTERED_PURPOSE_ADAPTER_REQUIRED')
    if purpose=='aggregate':
        reasons.append('SOURCE_POPULATION_COVERAGE_QUALIFICATION_REQUIRED')
    if purpose == 'traverse':
        if statement_scope is None:
            reasons.append('KNOWLEDGE_TRAVERSAL_EXPLICIT_SOURCE_REVIEW_REQUIRED')
        if any(scope['nodes'][pointer].get('value', {}).get('kind') != 'object'
                for pointer in scope['roots']):
            reasons.append('KNOWLEDGE_TRAVERSAL_OBJECT_RELATION_ROOT_REQUIRED')
    if purpose=='formula_input':
        from .knowledge_formula_contract import CAPABILITY,formula_scope_reasons
        reasons.extend(formula_scope_reasons(scope))
        if not mechanical_report or not any(c['capability']==CAPABILITY and c['outcome']=='satisfied'
                for c in mechanical_report.get('checks',[])):
            reasons.append('FORMULA_REGISTERED_DEFINITION_CHECK_REQUIRED')
        if mechanical_report:
            use=next((u for u in mechanical_report.get('use_results',[]) if u['purpose']==purpose),None)
            rechecked={'SELECTED_SCOPE_HAS_UNRESOLVED_INFORMATION','SELECTED_TYPED_SCOPE_HAS_UNRESOLVED_INFORMATION'}
            acceptable=(use is not None and (use['status']=='mechanical_checks_complete' or
                formula_scope is not None and use['status']=='requires_qualification'
                and not (set(use.get('reasons',[]))-rechecked)))
            if not acceptable:
                reasons.append('FORMULA_SELECTED_MEANING_CHECKS_INCOMPLETE')
        if any(node.get('calculation_context') is not None for node in scope['nodes'].values()) and formula_scope is None:
            reasons.append('FORMULA_EXPLICIT_CONTEXT_REVIEW_REQUIRED')
    if formula_scope is not None:
        from .formula_definition_context import formula_context_support_contract,SCOPE_VERSION,BASIS
        if (purpose!='formula_input' or policy.get('formula_consumption')!=formula_context_support_contract()
                or formula_scope.get('contract_version')!=SCOPE_VERSION or formula_scope.get('claim_basis')!=BASIS
                or formula_scope.get('purpose')!=purpose or formula_scope.get('scope_digest')!=scope['scope_digest']
                or formula_scope.get('roots')!=list(scope['roots']) or formula_scope.get('closure')!=list(scope['closure'])):
            reasons.append('FORMULA_REGISTERED_CONTEXT_REVIEW_REQUIRED')
        reasons.extend(formula_scope.get('blocked_reasons',[]))
    if contract.prerequisites or contract.checker_requirements:
        reasons.append('REGISTERED_DOMAIN_OBLIGATIONS_REQUIRED')
    for pointer,node in scope['nodes'].items():
        if judgments[pointer].label!='supported':
            reasons.append('SOURCE_OPINION_DOES_NOT_SUPPORT_SELECTED_CLOSURE')
        interpreted_parameter=(formula_scope is not None and purpose=='formula_input'
            and pointer.startswith('/parameters/') and node.get('calculation_context') is not None
            and node['assertion_kind']=='interpretation')
        if node['assertion_kind']!=policy['assertion_kind'] and not interpreted_parameter:
            reasons.append('REGISTERED_DERIVATION_OR_INTERPRETATION_REQUIRED')
    if statement_scope is not None:
        registered = purpose in ('filter', 'traverse')
        modal = purpose=='filter' and statement_scope.get('contract_version')==MODAL_STATEMENT_SCOPE_VERSION
        policy_key = 'traversal_consumption' if purpose == 'traverse' else 'statement_consumption'
        expected_contract = traversal_support_contract() if purpose == 'traverse' else statement_support_contract()
        if (not registered
                or policy.get(policy_key) != expected_contract
                or (modal and policy.get('modal_statement_consumption')!=modal_statement_support_contract())
                or statement_scope.get('contract_version') != (statement_versions(purpose,modality_aware=modal)[0] if registered else None)
                or statement_scope.get('claim_basis') != REPORTED_STATEMENT_EXISTS
                or statement_scope.get('purpose') != purpose
                or statement_scope.get('scope_digest') != scope['scope_digest']
                or statement_scope.get('roots') != list(scope['roots'])
                or statement_scope.get('closure') != list(scope['closure'])):
            reasons.append('REGISTERED_STATEMENT_CONSUMPTION_REQUIRED')
        allowed_modalities = ('asserted','possible','intended','required') if modal else ('asserted',)
        if any(node.get('modality') not in allowed_modalities or not pointer.startswith('/assertions/')
                for pointer,node in scope['nodes'].items()):
            reasons.append('KNOWLEDGE_STATEMENT_ASSERTED_SOURCE_SCOPE_REQUIRED')
        reasons.extend(statement_scope.get('blocked_reasons', []))
        use=next((u for u in (mechanical_report or {}).get('use_results', [])
            if u['purpose'] == purpose), None)
        # These two summaries are re-evaluated from the full reviewed inventory
        # and generated-origin checks. No other mechanical obligation is waived.
        reevaluated={'SELECTED_SCOPE_HAS_UNRESOLVED_INFORMATION',
            'SELECTED_TYPED_SCOPE_HAS_UNRESOLVED_INFORMATION'}
        if (use is None or use.get('status') not in {'mechanical_checks_complete','requires_qualification'}
                or set(use.get('reasons', [])) - reevaluated):
            reasons.append('KNOWLEDGE_STATEMENT_SELECTED_MEANING_CHECKS_INCOMPLETE')
    return list(dict.fromkeys(reasons))
