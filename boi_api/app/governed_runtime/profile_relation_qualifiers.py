"""Bind reviewed relation applicability without changing optional rowsets.

Only a root-owned predicate on a required existence path can currently be
conjoined with root filters. Other placements fail closed; a relation condition
is neither a user filter nor permission to discard unrelated root records.
"""
from .semantic_binding_contract import semantic_digest
from .semantic_qualifier import entry_qualifiers


def _clauses(payload):
    semantics = payload.get('semantic_contract') or {}
    # Native projections preserve arbitrary source fields. An unbound source
    # condition must not disappear merely because it used the older spelling.
    for facet in ('conditions', 'exceptions'):
        if payload.get(facet) and payload[facet] != semantics.get(facet):
            raise ValueError('RELATION_QUALIFIER_UNRESOLVED')
    try:
        return entry_qualifiers(payload)
    except ValueError as error:
        reason = 'CONTEXT_REQUIRED' if str(error).endswith('CONTEXT_REQUIRED') else 'UNRESOLVED'
        raise ValueError('RELATION_QUALIFIER_' + reason) from error


def bind_required_relation_qualifiers(*, bundle, root_ref, traversals, existence_owners):
    """Return logical predicates, exact typed parameters and source clause refs."""
    entries = {entry.entry_id: entry for entry in bundle.domain_entries}
    incoming = {step.child_object_ref: step for step in traversals}
    required = set()
    for owner in existence_owners:
        while owner != root_ref:
            step = incoming.get(owner)
            if step is None:
                raise ValueError('RELATION_QUALIFIER_EXISTENCE_PATH_UNRESOLVED')
            required.add(step.relationship_ref)
            owner = step.parent_object_ref
    filters, specs, parameters, qualified, dependencies = [], [], {}, [], {}

    def remember(ref):
        entry = entries[ref]
        dependencies[ref] = {'entry_ref': ref, 'revision_id': entry.revision_id,
            'revision_digest': entry.revision_digest, 'payload_digest': semantic_digest(entry.payload)}

    for step in traversals:
        entry = entries.get(step.relationship_ref)
        if entry is None:
            raise ValueError('RELATION_QUALIFIER_DEFINITION_MISSING')
        clauses = _clauses(entry.payload)
        if not clauses:
            continue
        remember(step.relationship_ref)
        for clause in clauses:
            qualified.append({'entry_ref': step.relationship_ref,
                'qualifier': clause.model_dump(mode='json')})
            for predicate in clause.predicates:
                prop_entry = entries.get(predicate.property_ref)
                if prop_entry is None or prop_entry.payload.get('kind') != 'PropertyDefinition':
                    raise ValueError('RELATION_QUALIFIER_PROPERTY_NOT_BOUND')
                prop = prop_entry.payload
                if (prop.get('owner_ref') != root_ref or step.relationship_ref not in required
                        or root_ref not in (step.parent_object_ref, step.child_object_ref)):
                    raise ValueError('RELATION_QUALIFIER_PLACEMENT_UNSUPPORTED')
                # A predicate's own applicability cannot add an unexamined
                # second condition. Annotations are retained in its digest.
                if any(q.predicates for q in _clauses(prop)):
                    raise ValueError('RELATION_QUALIFIER_PROPERTY_CONTEXT_UNSUPPORTED')
                remember(predicate.property_ref)
                if prop.get('value_type_ref'):
                    value_entry = entries.get(prop['value_type_ref'])
                    if value_entry is None:
                        raise ValueError('RELATION_QUALIFIER_VALUE_TYPE_MISMATCH')
                    if any(q.predicates for q in _clauses(value_entry.payload)):
                        raise ValueError('RELATION_QUALIFIER_PROPERTY_CONTEXT_UNSUPPORTED')
                    primitive = value_entry.payload.get('primitive_type')
                    remember(prop['value_type_ref'])
                else:
                    primitive = prop.get('value_type')
                if primitive != predicate.value_type:
                    raise ValueError('RELATION_QUALIFIER_VALUE_TYPE_MISMATCH')
                semantic = prop.get('semantic_contract') or {}
                if semantic:
                    unit_known = semantic.get('unit_semantics') in {'declared', 'dimensionless', 'not_applicable'}
                    unit_ref, unit_digest = semantic.get('unit_ref'), semantic.get('unit_revision_digest')
                else:
                    unit_known = (prop.get('unit_contract') or {}).get('applicability') == 'not_applicable'
                    unit_ref = unit_digest = None
                if (not unit_known or (unit_ref, unit_digest) != (predicate.unit_ref, predicate.unit_revision_digest)
                        or predicate.value_type in {'string', 'boolean'} and predicate.unit_ref):
                    raise ValueError('RELATION_QUALIFIER_UNIT_MISMATCH')
                name = None
                if predicate.operator not in {'is_null', 'not_null'}:
                    name = f'source_qualifier_{len(specs)}'
                    plural = predicate.operator == 'in'
                    specs.append({'name': name, 'type': predicate.value_type + ('_list' if plural else '')})
                    parameters[name] = list(predicate.values) if plural else predicate.values[0]
                filters.append({'property_ref': predicate.property_ref, 'operator': predicate.operator,
                    'parameter_name': name})
    if not qualified:
        return (), (), {}, None
    body = {'contract_version': 'boi/required-relation-qualifiers@1',
        'placement': 'root_owned_predicate_on_required_existence_path',
        'root_object_ref': root_ref, 'required_relationship_refs': sorted(required),
        'definition_revisions': [dependencies[key] for key in sorted(dependencies)],
        'qualified_clauses': qualified, 'filters': filters, 'parameter_specs': specs,
        'parameters': parameters, 'semantic_validated': False, 'execution_authority_granted': False}
    return tuple(filters), tuple(specs), parameters, {**body, 'receipt_digest': semantic_digest(body)}
