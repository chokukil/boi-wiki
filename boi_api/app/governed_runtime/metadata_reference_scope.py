"""Reference vocabulary read from supplied definitions, never from name matching.

Scope and unit references identify existing objects. A new name remains in the
proposed definition/conditions until its reference can be bound in a later step.
This vocabulary grants neither equivalence nor semantic approval.
"""


UNIT_TERM_TARGET = 'boi:semantic-target-kind:unit@1'
QUANTITY_KIND_TERM_TARGET = 'boi:semantic-target-kind:quantity-kind@1'


def reference_vocabulary(definitions):
    result = {'process_refs': set(), 'equipment_class_refs': set(),
              'quantity_kind_ref': set(), 'unit_pairs': set(), 'concept_pairs': set()}
    for entry in definitions:
        logical = entry['logical_definition']
        semantics = logical.get('semantic_contract') or {}
        scope = semantics.get('scope') or {}
        for field in ('process_refs', 'equipment_class_refs'):
            result[field].update(scope.get(field) or [])
        quantity = semantics.get('quantity_kind_ref')
        if quantity:
            result['quantity_kind_ref'].add(quantity)
        unit, revision = semantics.get('unit_ref'), semantics.get('unit_revision_digest')
        if unit and revision:
            result['unit_pairs'].add((unit, revision))
        # A Term can be the referenced unit or quantity kind itself.  Admit it
        # only through an explicit, versioned semantic target contract.  Names,
        # aliases and identifier prefixes never establish this role.
        typed_term = (
            logical.get('kind') == 'Term'
            and entry.get('concept_id') == logical.get('id')
        )
        if typed_term and semantics.get('target_kind') == UNIT_TERM_TARGET:
            result['unit_pairs'].add((logical['id'], entry['revision_digest']))
        if typed_term and semantics.get('target_kind') == QUANTITY_KIND_TERM_TARGET:
            result['quantity_kind_ref'].add(logical['id'])
        result['concept_pairs'].add((entry['concept_id'], entry['revision_digest']))
    return result


def bind_reference_schema(schema, *, namespace, definitions):
    vocabulary = reference_vocabulary(definitions)
    scope = schema['$defs']['SemanticScope']['properties']
    scope['namespace'] = {'allOf': [scope['namespace'], {'const': namespace}]}
    for field in ('process_refs', 'equipment_class_refs'):
        allowed = sorted(vocabulary[field])
        scope[field] = {'allOf': [scope[field], {'items': {'enum': allowed} if allowed else False}]}
    descriptor = schema['$defs']['SemanticDescriptor']
    descriptor.setdefault('allOf', []).extend([
        {'properties': {'quantity_kind_ref': {'enum': [None, *sorted(vocabulary['quantity_kind_ref'])]}}},
        {'anyOf': [{'properties': {'unit_ref': {'const': unit}, 'unit_revision_digest': {'const': revision}}}
                   for unit, revision in [(None, None), *sorted(vocabulary['unit_pairs'])]]},
    ])
    schema['$defs']['LogicalSemanticClaim']['properties']['proposed_concept'] = {
        'anyOf': [{'type': 'null'}, *[
            {'allOf': [{'$ref': '#/$defs/RevisionRef'},
                       {'properties': {'ref': {'const': ref}, 'revision_digest': {'const': revision}}}]}
            for ref, revision in sorted(vocabulary['concept_pairs'])]]}
    return schema


def validate_reference_scope(draft, *, namespace, definitions):
    vocabulary = reference_vocabulary(definitions)
    for candidate in draft.candidates:
        meaning = candidate.semantics
        if meaning.scope.namespace != namespace:
            raise ValueError('SEMANTIC_CLAIM_NAMESPACE_MISMATCH')
        for field in ('process_refs', 'equipment_class_refs'):
            if not set(getattr(meaning.scope, field)) <= vocabulary[field]:
                raise ValueError('SEMANTIC_SCOPE_REFERENCE_NOT_READ')
        if meaning.quantity_kind_ref and meaning.quantity_kind_ref not in vocabulary['quantity_kind_ref']:
            raise ValueError('SEMANTIC_QUANTITY_REFERENCE_NOT_READ')
        if (meaning.unit_ref, meaning.unit_revision_digest) not in {(None, None), *vocabulary['unit_pairs']}:
            raise ValueError('SEMANTIC_UNIT_REVISION_NOT_READ')
        proposal = candidate.proposed_concept
        if proposal and (proposal.ref, proposal.revision_digest) not in vocabulary['concept_pairs']:
            raise ValueError('SEMANTIC_MATCH_PROPOSAL_OUTSIDE_READ_DEFINITIONS')
