"""Authenticated source inventory review for conditional Formula definitions."""
from .semantic_binding_contract import semantic_digest
from .formula_definition_context import SCOPE_VERSION,BASIS,resolve_calculation_context


def formula_unresolved_decision(content, scope, *, review, original_unresolved,
        evidence_validator, projection, registry):
    """Qualify exact complete inventory; source-fidelity/identity still block.

    The enclosing importer independently checks native bytes, full opinion DAG,
    quotations and authority. This result is not accepted from a request.
    """
    from .knowledge_use_contract import LocalFormulaReview
    from .knowledge_unresolved_scope import (unresolved_review_item, typed_unresolved_scopes,
        _statement_projection_reasons)
    from .knowledge_statement_contract import BLOCKING_STATEMENT_FACETS
    review=LocalFormulaReview.model_validate(review.model_dump(mode='json'))
    original=[unresolved_review_item(v) for v in original_unresolved]
    native=[unresolved_review_item(v) for v in content.unresolved]
    if (review.inventory_digest!=semantic_digest(original) or len(original)!=len(native)
            or {v.index for v in review.items}!=set(range(len(original)))):
        raise ValueError('FORMULA_REVIEW_FULL_INVENTORY_REQUIRED')
    relevant=typed_unresolved_scopes(content).relevant(scope['closure'])
    judgments={v.index:v for v in review.items}
    blocked,entries=[],[]
    for index,(old,current,item) in enumerate(zip(original,native,content.unresolved)):
        judgment=judgments[index]
        if (judgment.item_digest!=semantic_digest(old)
                or {k:v for k,v in old.items() if k!='source_spans'} !=
                   {k:v for k,v in current.items() if k!='source_spans'}):
            raise ValueError('FORMULA_REVIEW_NATIVE_ITEM_CHANGED')
        receipts=evidence_validator(item,judgment)
        if not isinstance(receipts,list) or not receipts or any(
                not isinstance(v,dict) or not {'quote','span','field_digest','source_revision_digest'}<=v.keys()
                for v in receipts):
            raise ValueError('FORMULA_REVIEW_SOURCE_EVIDENCE_REQUIRED')
        selected=item in relevant
        classification=item.classification
        blocking=selected and (judgment.label!='supported' or classification is None
            or bool(set(classification.facets)&BLOCKING_STATEMENT_FACETS))
        if blocking:blocked.append('FORMULA_REVIEW_SOURCE_SCOPE_UNRESOLVED')
        entries.append({'index':index,'original_item':old,'item':current,
            'judgment':judgment.model_dump(mode='json'),'source_bindings':receipts,
            'disposition':'blocking' if blocking else 'limitation' if selected else 'outside_selected_closure'})
    # Preserve generated conflict checks. Parameter obligations are checked by
    # resolve_calculation_context; they are not source assertion unknowns.
    assertion_scope={**scope,'nodes':{p:v for p,v in scope['nodes'].items() if p.startswith('/assertions/')}}
    blocked.extend(_statement_projection_reasons(content,assertion_scope,projection,registry))
    contexts={}
    for pointer in scope['roots']:
        if not pointer.startswith('/parameters/'):
            blocked.append('FORMULA_PARAMETER_ROOT_REQUIRED');continue
        try:
            contexts[pointer]=resolve_calculation_context(scope,pointer)
        except ValueError as exc:
            blocked.append(str(exc))
        if contexts.get(pointer) is None:
            blocked.append('FORMULA_REVIEW_EXPLICIT_CONTEXT_REQUIRED')
    return {'contract_version':SCOPE_VERSION,'claim_basis':BASIS,'purpose':'formula_input',
        'scope_digest':scope['scope_digest'],'roots':list(scope['roots']),'closure':list(scope['closure']),
        'inventory_digest':semantic_digest(native),'review_digest':semantic_digest(review),
        'reviewed_items':entries,'contexts':contexts,'blocked_reasons':list(dict.fromkeys(blocked)),
        'world_applicability':'not_verified','source_unknowns_resolved':False,
        'scientific_truth_proven':False,'physical_execution_granted':False}
