"""Typed unresolved scopes and their origin, without semantic inference.

Exact node addresses determine relevance. Codes remain explanatory data;
subtracting code sets would lose global declarations or generated conflicts.
"""
from dataclasses import dataclass
from decimal import Decimal

from .knowledge_content import meaning_pointer
from .knowledge_unresolved_contract import (overlaps, unresolved_review_item,
    unresolved_inventory_digest, unresolved_evidence_bindings)
from .knowledge_projection_contract import definition_key
from .knowledge_statement_contract import (BLOCKING_STATEMENT_FACETS,
    REPORTED_STATEMENT_EXISTS, STATEMENT_SCOPE_VERSION, STATEMENT_USE_PURPOSE,
    TRAVERSAL_REVIEW_VERSION, MODAL_STATEMENT_REVIEW_VERSION, statement_versions)
from .semantic_binding_contract import semantic_digest


@dataclass(frozen=True)
class TypedUnresolvedScopes:
    global_items: tuple
    scoped_items: tuple

    def relevant(self, pointers):
        return self.global_items + tuple(item for item in self.scoped_items
            if any(overlaps(item.meaning_pointer,pointer) for pointer in pointers))

    def fact_markers(self, pointer):
        # An authored code named valid_time_unknown must not be mistaken for
        # the engine diagnostic which source-declared queries can tolerate.
        return tuple(dict.fromkeys('content_unresolved:'+item.reason_code
            for item in self.scoped_items if overlaps(item.meaning_pointer,pointer)))


def typed_unresolved_scopes(content):
    """Only registered assertion/parameter addresses have a local use scope."""
    if content.meaning.get('contract_version') != 'boi/typed-knowledge-meaning@1':
        raise ValueError('KNOWLEDGE_UNRESOLVED_TYPED_CONTRACT_REQUIRED')
    global_items, scoped_items = [], []
    for item in content.unresolved:
        pointer=item.meaning_pointer
        if pointer is not None:
            meaning_pointer(content.meaning,pointer)
        # Existing pointer validation enforces real paths and canonical array
        # indexes. Type/schema and unfamiliar metadata remain global.
        parts=pointer.split('/') if pointer else []
        local=len(parts)>=2 and parts[1] in ('assertions','parameters')
        (scoped_items if local else global_items).append(item)
    return TypedUnresolvedScopes(tuple(global_items),tuple(scoped_items))


def typed_use_unresolved(content, scope, projected, purpose):
    """Check full selected nodes and their exact transitive dependency closure.

Formula's existing definition policy allows unknown validity time: observation
time comes from its explicit preview inputs. Authored unknowns and uncertainties
never receive that exception, even when they reuse an engine diagnostic code.
"""
    declarations=typed_unresolved_scopes(content)
    declared=bool(declarations.relevant(scope['closure']))
    if projected is None:
        return declared,False
    if any(obj.unresolved for obj in projected.objects):
        return declared,True
    if any(node.get('uncertainties') for node in scope['nodes'].values()):
        return declared,True
    allow_unknown_time=False
    if purpose=='formula_input':
        from .knowledge_formula_contract import formula_scope_reasons
        allow_unknown_time=not formula_scope_reasons(scope)
    for obj in projected.objects:
        for fact in obj.facts:
            if fact.meaning_pointer not in scope['nodes'] or not fact.unresolved:
                continue
            node=scope['nodes'][fact.meaning_pointer]
            if (allow_unknown_time and node.get('valid_time',{}).get('state')=='unknown'
                    and all(code=='valid_time_unknown' for code in fact.unresolved)):
                continue
            return declared,True
    return declared,False


def _statement_projection_reasons(content, scope, projection, registry):
    """Reconstruct generated blockers instead of subtracting authored codes.

Authored uncertainties can use the same text as engine diagnostics; retaining
their origin prevents a reviewed facet from erasing a generated conflict.
"""
    if projection is None or registry is None:
        return ['KNOWLEDGE_STATEMENT_SERVER_PROJECTION_REQUIRED']
    declarations = typed_unresolved_scopes(content)
    reasons = []
    if projection.metadata.get('declared_unresolved', []) != [
            item.model_dump(mode='json') for item in content.unresolved]:
        reasons.append('KNOWLEDGE_STATEMENT_PROJECTED_INVENTORY_CHANGED')
    for pointer, node in scope['nodes'].items():
        if node.get('uncertainties'):
            reasons.append('KNOWLEDGE_STATEMENT_SELECTED_NODE_UNCERTAINTY')
    functional = {}
    for fact in projection.facts:
        declaration, _ = registry.predicate(fact.predicate_revision)
        if declaration.cardinality == 'one' and fact.polarity == 'positive' and fact.modality == 'asserted':
            qualifiers = fact.qualifiers
            key = semantic_digest([definition_key(fact.predicate_revision),
                qualifiers.get('conditions', []), qualifiers.get('exceptions', []),
                qualifiers.get('applicability', []), fact.valid_time])
            value = fact.value
            functional.setdefault(key, set()).add((value.kind,
                Decimal(value.value) if value.kind == 'decimal' else value.value))
        if fact.meaning_pointer not in scope['nodes']:
            continue
        node = scope['nodes'][fact.meaning_pointer]
        permitted = set(declarations.fact_markers(fact.meaning_pointer))
        if node.get('valid_time', {}).get('state') == 'unknown':
            permitted.add('valid_time_unknown')
        # A faithfully reported opaque condition remains part of the complete
        # statement context. Existence does not require compiling it into SAT.
        # Only markers generated at exact evidenced clause addresses qualify;
        # authored uncertainties are independently blocked above.
        for group in ('conditions', 'exceptions', 'applicability'):
            for index, clause in enumerate(node.get(group, [])):
                pointer = f'{fact.meaning_pointer}/{group}/{index}'
                if (clause.get('expression') is None and any(
                        binding.meaning_pointer == pointer for binding in content.evidence_bindings)):
                    permitted.add('uncompiled_qualifier:' + pointer)
        if set(fact.unresolved) - permitted:
            reasons.append('KNOWLEDGE_STATEMENT_SELECTED_GENERATED_UNKNOWN')
    generated_conflict = any(len(values) > 1 for values in functional.values())
    if generated_conflict:
        reasons.append('KNOWLEDGE_STATEMENT_GENERATED_CARDINALITY_CONFLICT')
    expected_object_codes = {item.reason_code for item in declarations.global_items}
    if generated_conflict:
        expected_object_codes.add('single_cardinality_has_competing_values')
    if set(projection.unresolved) - expected_object_codes:
        reasons.append('KNOWLEDGE_STATEMENT_GENERATED_OBJECT_UNKNOWN')
    return list(dict.fromkeys(reasons))


def statement_unresolved_decision(content, scope, *, review, original_unresolved,
        evidence_validator, projection, registry):
    """Server qualification helper, not a caller-provided ignore mechanism.

The caller must already verify authenticated assessment bytes, full input DAG,
native revision, current source authority and mechanical checks. The callback
must verify each quotation against current exact source bytes and return server
evidence receipts. This function does not persist or grant authority itself.
"""
    from .knowledge_use_contract import LocalStatementReview
    review = LocalStatementReview.model_validate(
        review.model_dump(mode='json') if hasattr(review, 'model_dump') else review)
    if not callable(evidence_validator):
        raise ValueError('KNOWLEDGE_STATEMENT_SOURCE_REVIEW_VALIDATOR_REQUIRED')
    original = [unresolved_review_item(item) for item in original_unresolved]
    native = [unresolved_review_item(item) for item in content.unresolved]
    if (review.inventory_digest != semantic_digest(original)
            or len(native) != len(original)
            or {item.index for item in review.items} != set(range(len(original)))):
        raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_FULL_INVENTORY_REQUIRED')
    judgments = {item.index:item for item in review.items}
    relevant = typed_unresolved_scopes(content).relevant(scope['closure'])
    blocked, limitations, reviewed = [], [], []
    for index, (old, current, item) in enumerate(zip(original, native, content.unresolved)):
        judgment = judgments[index]
        if judgment.item_digest != semantic_digest(old):
            raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_ITEM_CHANGED')
        # Only declared source reference tokens may be replaced by the importer;
        # classification cannot alter the original subject or explanation.
        if {k:v for k,v in old.items() if k != 'source_spans'} != {
                k:v for k,v in current.items() if k != 'source_spans'}:
            raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_NATIVE_ITEM_CHANGED')
        receipts = evidence_validator(item, judgment)
        if not isinstance(receipts, list) or not receipts or any(
                not isinstance(r, dict) or not {'quote','span','field_digest','source_revision_digest'} <= r.keys()
                for r in receipts):
            raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_SOURCE_EVIDENCE_REQUIRED')
        selected = item in relevant
        supported = judgment.label == 'supported'
        classification = item.classification
        if selected and not supported:
            blocked.append('KNOWLEDGE_STATEMENT_CLASSIFICATION_NOT_SUPPORTED')
        if selected and classification is None:
            blocked.append('KNOWLEDGE_STATEMENT_UNCLASSIFIED_UNRESOLVED')
        facets = set(classification.facets) if classification is not None else set()
        if facets & {'upstream_source_fidelity','source_completeness'}:
            # Bind the declared boundary to the authenticated review's exact
            # source bytes. Never turn unverified OCR originals into verified
            # input fidelity, or accept an unrelated cited source as the basis.
            source_bytes={r['quote'].get('source_byte_digest') for r in receipts}
            if set(classification.provided_source_byte_digests)!=source_bytes:
                raise ValueError('KNOWLEDGE_STATEMENT_PROVIDED_SOURCE_BOUNDARY_MISMATCH')
        blocking = selected and bool(facets & BLOCKING_STATEMENT_FACETS)
        if blocking:
            blocked.append('KNOWLEDGE_STATEMENT_SOURCE_SCOPE_UNRESOLVED')
        disposition = ('outside_selected_closure' if not selected else
            'blocking' if blocking or not supported or classification is None else 'limitation')
        entry = {'index':index, 'original_item_digest':semantic_digest(old),
            'native_item_digest':semantic_digest(current), 'original_item':old,
            'item':current, 'judgment':judgment.model_dump(mode='json'),
            'source_bindings':receipts, 'disposition':disposition}
        reviewed.append(entry)
        if disposition == 'limitation':
            limitations.append(entry)
    blocked.extend(_statement_projection_reasons(content, scope, projection, registry))
    blocked = list(dict.fromkeys(blocked))
    purpose = 'traverse' if review.contract_version == TRAVERSAL_REVIEW_VERSION else STATEMENT_USE_PURPOSE
    return {'contract_version':statement_versions(purpose,
                modality_aware=review.contract_version==MODAL_STATEMENT_REVIEW_VERSION)[0],
        'claim_basis':REPORTED_STATEMENT_EXISTS, 'purpose':purpose,
        'scope_digest':scope['scope_digest'], 'roots':list(scope['roots']),
        'closure':list(scope['closure']), 'inventory_digest':semantic_digest(native),
        'original_inventory_digest':semantic_digest(original),
        'review_digest':semantic_digest(review), 'reviewed_items':reviewed,
        'blocked_reasons':blocked, 'limitations':limitations,
        'eligible_fact_bindings':[{'meaning_pointer':fact.meaning_pointer,
            'fact_digest':semantic_digest(fact)} for fact in projection.facts
            if fact.meaning_pointer in scope['roots']] if not blocked else [],
        'world_condition_satisfaction':'not_evaluated',
        'population_completeness_qualified':False,
        'scientific_truth_proven':False, 'physical_execution_granted':False,
        'source_review_basis':'authenticated_exact_source_inventory_review'}
