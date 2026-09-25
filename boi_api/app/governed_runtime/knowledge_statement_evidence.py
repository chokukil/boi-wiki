"""Consumption of exact, server-reviewed source-statement qualifications.

The review establishes which recorded assertions may be selected. It does not
establish that their conditions hold in the world or that the source is complete.
This module accepts a qualification only after its enclosing reader has checked
the ledger, current native/source authority, policy and mechanical check.
"""
from .knowledge_statement_contract import (
    REPORTED_STATEMENT_EXISTS, STATEMENT_SCOPE_VERSION, MODAL_STATEMENT_SCOPE_VERSION, STATEMENT_USE_PURPOSE, statement_versions,
)
from .semantic_binding_contract import semantic_digest


def current_statement_scope(payload, *, purpose=STATEMENT_USE_PURPOSE):
    """Return a bound scope, or no grant; never upgrade a legacy qualification."""
    scope = payload.get('statement_scope')
    if not isinstance(scope, dict) or 'statement_review_required' in payload:
        return None
    scope_version, review_version = statement_versions(purpose,
        modality_aware=purpose=='filter' and scope.get('contract_version')==MODAL_STATEMENT_SCOPE_VERSION)
    if (payload.get('status') != 'usable_with_limits'
            or payload.get('purpose') != purpose
            or scope.get('contract_version') != scope_version
            or scope.get('claim_basis') != REPORTED_STATEMENT_EXISTS
            or scope.get('purpose') != purpose
            or scope.get('blocked_reasons') != []
            or scope.get('world_condition_satisfaction') != 'not_evaluated'
            or scope.get('population_completeness_qualified') is not False
            or scope.get('scientific_truth_proven') is not False
            or scope.get('physical_execution_granted') is not False
            or scope.get('source_review_basis') != 'authenticated_exact_source_inventory_review'):
        return None
    for key in ('scope_digest', 'roots', 'closure'):
        if key not in payload or scope.get(key) != payload[key]:
            return None
    expected = {key: payload.get(key) for key in (
        'knowledge_revision', 'source_manifest_digest', 'assessment_byte_digest',
        'qualification_policy_digest', 'checker_release_digest')}
    if any(value is None for value in expected.values()) or scope.get('binding') != expected:
        return None
    reviewed = scope.get('reviewed_items')
    if not isinstance(reviewed, list):
        return None
    try:
        from .knowledge_use_contract import LocalStatementReview
        if [item['index'] for item in reviewed] != list(range(len(reviewed))):
            return None
        native, original_items = [item['item'] for item in reviewed], [item['original_item'] for item in reviewed]
        if (semantic_digest(native) != scope.get('inventory_digest')
                or semantic_digest(original_items) != scope.get('original_inventory_digest')
                or any(semantic_digest(item['item']) != item['native_item_digest']
                    or semantic_digest(item['original_item']) != item['original_item_digest'] for item in reviewed)):
            return None
        review = LocalStatementReview.model_validate({
            'contract_version':review_version, 'claim_basis':REPORTED_STATEMENT_EXISTS,
            'inventory_digest':scope['original_inventory_digest'],
            'items':[item['judgment'] for item in reviewed]})
        if semantic_digest(review) != scope.get('review_digest'):
            return None
        submission=payload.get('statement_review_submission')
        if submission is not None or 'review_submission_digest' in scope:
            from .published_knowledge_contract import PublishedStatementReview
            if (not isinstance(submission,dict) or semantic_digest(submission)!=scope.get('review_submission_digest')
                    or submission.get('contract_version')!='boi/published-statement-review-submission@1'
                    or submission.get('request_ref')!=payload.get('refresh_request_ref')
                    or submission.get('authenticated_principal')!=payload.get('qualified_by')
                    or submission.get('execution_attested') is not False
                    or submission.get('reviewer_relationship_verified') is not False):
                return None
            for key in ('knowledge_revision','source_manifest_digest','qualification_policy_digest','checker_release_digest'):
                if submission.get(key)!=payload.get(key):
                    return None
            submitted=PublishedStatementReview.model_validate(submission['submission'])
            if (submitted.purpose!=purpose or semantic_digest(submitted)!=submission.get('submission_digest')
                    or semantic_digest(submitted.review)!=scope.get('review_digest')):
                return None
        for item, judgment in zip(reviewed, review.items):
            if (judgment.index != item['index'] or judgment.item_digest != item['original_item_digest']
                    or not item.get('source_bindings') or item.get('disposition') == 'blocking'):
                return None
    except (KeyError, TypeError, ValueError):
        return None
    selected = scope.get('eligible_fact_bindings')
    original = payload.get('fact_bindings')
    if not isinstance(selected, list) or not isinstance(original, list):
        return None
    if any(not isinstance(item, dict) or set(item) != {'meaning_pointer', 'fact_digest'}
           or not isinstance(item['meaning_pointer'],str) or not isinstance(item['fact_digest'],str)
           or item not in original or item['meaning_pointer'] not in scope['roots'] for item in selected):
        return None
    if len({item['meaning_pointer'] for item in selected}) != len(selected):
        return None
    return scope


def statement_fact_grants(payload, *, purpose=STATEMENT_USE_PURPOSE):
    """Prepared and in-memory consumers use the same bound fact inventory."""
    scope = current_statement_scope(payload, purpose=purpose)
    if scope is None:
        return {}, None
    return ({item['meaning_pointer']: item['fact_digest']
             for item in scope['eligible_fact_bindings']}, semantic_digest(scope))


def reported_statement_context(fact):
    """Exact reported context, without inferring equivalent words or conditions.

    Consumers must additionally bind the native revision. A field-set owner is
    deliberately conservative: overlapping fields do not establish a shared
    process scope. Unknown time here is a source annotation, not simultaneity.
    """
    from .typed_knowledge_meaning import TypedCondition, KnowledgeValidTime
    owners = set()
    for binding in fact.evidence_bindings:
        source, locator = binding.get('source_revision_digest'), binding.get('field_locator')
        if not isinstance(source, str) or not isinstance(locator, str):
            raise ValueError('KNOWLEDGE_STATEMENT_SOURCE_OWNER_REQUIRED')
        owners.add((source, locator))
    if not owners:
        raise ValueError('KNOWLEDGE_STATEMENT_SOURCE_OWNER_REQUIRED')
    source_owners = [{'source_revision_digest': source, 'field_locator': locator}
                     for source, locator in sorted(owners)]
    context = {'source_owners': source_owners}
    for group in ('conditions', 'exceptions', 'applicability'):
        raw = fact.qualifiers.get(group, [])
        if not isinstance(raw, list) or len(raw) > 64:
            raise ValueError('KNOWLEDGE_STATEMENT_CONTEXT_INVALID')
        for clause in raw:
            TypedCondition.model_validate(clause)
        context[group] = raw
    dependencies = fact.qualifiers.get('depends_on', [])
    if (not isinstance(dependencies, list) or len(dependencies) > 256
            or any(not isinstance(item, str) or not item for item in dependencies)):
        raise ValueError('KNOWLEDGE_STATEMENT_CONTEXT_INVALID')
    KnowledgeValidTime.model_validate(fact.valid_time)
    context.update(valid_time=fact.valid_time, depends_on=dependencies)
    return {'context_digest': semantic_digest(context),
            'owner_scope_digest': semantic_digest(source_owners),
            'time_scope': semantic_digest(fact.valid_time),
            'unconditional': not any(context[group] for group in
                ('conditions', 'exceptions', 'applicability', 'depends_on')),
            'context': context}


def evaluate_reported_statements(query, facts, *, registry, uses, revision, check_budget=lambda: None):
    """Compose the full AST inside each exact context before object existence.

    A report of not-P is retained as counterevidence within its context, never
    used as proof that a report of P does not exist in another context.
    """
    from dataclasses import asdict
    from .knowledge_evidence_logic import EvidenceAtom, evaluate_evidence_expression
    from .knowledge_query import compare_values
    from .knowledge_statement_contract import QUERY_V2, QUERY_V3, QUERY_V4
    if query.contract_version not in (QUERY_V2,QUERY_V3,QUERY_V4) or query.claim_basis != REPORTED_STATEMENT_EXISTS:
        raise ValueError('KNOWLEDGE_QUERY_STATEMENT_VERSION_REQUIRED')
    selected, contexts, traces = [], {}, []
    tested = {test.predicate for test in query.predicates}
    for fact in facts:
        if fact.predicate_revision not in tested:
            continue
        check_budget()
        use = uses.get(fact.meaning_pointer)
        grant = (use is not None and use.knowledge_revision.ref == revision
                 and use.fact_digest == semantic_digest(fact) and use.purpose == STATEMENT_USE_PURPOSE
                 and use.statement_scope_digest is not None)
        adapter = (fact.qualifiers.get('contract_version') == 'boi/typed-assertion-qualifiers@1'
                   and fact.qualifiers.get('assertion_kind') == 'source_reported' and fact.modality == query.modality)
        trace = {'fact_ref': revision + '#' + fact.meaning_pointer,
                 'applicability': 'recorded_context' if grant and adapter else 'unknown',
                 'reasons': [] if grant and adapter else [
                     'report_modality_mismatch' if grant and fact.modality!=query.modality
                     else 'statement_use_qualification_missing_or_changed'],
                 'fact': fact.model_dump(mode='json'),
                 'qualification_refs': [ref.model_dump(mode='json') for ref in use.qualification_refs] if use else [],
                 'statement_scope_digest': use.statement_scope_digest if use else None,
                 'world_condition_satisfaction': 'not_evaluated'}
        traces.append(trace)
        if not grant or not adapter:
            continue
        context = reported_statement_context(fact)
        trace['context_digest'] = context['context_digest']
        contexts[context['context_digest']] = context
        selected.append((fact, context, trace['fact_ref']))
        if len(contexts) > 256:
            raise ValueError('KNOWLEDGE_STATEMENT_CONTEXT_BUDGET_EXCEEDED')
    evaluated = []
    for digest, context in sorted(contexts.items()):
        check_budget()
        compatible = [(fact, ref) for fact, own, ref in selected
                      if own['context_digest'] == digest or (own['unconditional']
                          and own['owner_scope_digest'] == context['owner_scope_digest']
                          and own['time_scope'] == context['time_scope'])]
        atoms = []
        for index, test in enumerate(query.predicates):
            declaration, _ = registry.predicate(test.predicate)
            support, refute = [], []
            known = declaration.quantity_semantics != 'unknown' and declaration.value_semantics != 'unknown'
            for fact, ref in compatible:
                if fact.predicate_revision != test.predicate or not known or not test.includes_source(revision,fact.meaning_pointer):
                    continue
                equal = compare_values(fact.value, test.value, 'eq')
                requested = test.report_polarity or query.polarity
                if test.operator != 'eq':
                    # Negative point reports do not specify an interval. Only
                    # a positively reported scalar can witness its comparison.
                    if fact.polarity == 'positive':
                        if compare_values(fact.value,test.value,test.operator):support.append(ref)
                        elif declaration.cardinality=='one':refute.append(ref)
                    continue
                if fact.polarity == requested and equal:
                    support.append(ref)
                elif (fact.polarity != requested and equal) or (
                        requested == 'positive' and fact.polarity == 'positive'
                        and not equal and declaration.cardinality == 'one' and fact.modality=='asserted'):
                    refute.append(ref)
            atoms.append(EvidenceAtom(str(index), tuple(dict.fromkeys(support)), tuple(dict.fromkeys(refute)),
                () if support or refute else ('no_qualified_statement_in_compatible_source_context',)))
        result = evaluate_evidence_expression(query.expression, atoms)
        evaluated.append({**context, 'state': result.state,
                          'atoms': [asdict(atom) for atom in atoms],
                          'conflict_atom_ids': list(result.conflict_atom_ids),
                          'unknown_atom_ids': list(result.unknown_atom_ids)})
    witnesses = [item['context_digest'] for item in evaluated if item['state'] in ('supported', 'conflicted')]
    state = ('conflicted' if any(item['state'] == 'conflicted' for item in evaluated) else
             'supported' if witnesses else 'unknown')
    return {'state': state, 'has_reported_witness': bool(witnesses), 'atoms': [],
            'source_context_witnesses': witnesses, 'source_contexts': evaluated,
            'countercontexts': [item['context_digest'] for item in evaluated if item['state'] in ('refuted', 'conflicted')],
            'traces': traces, 'world_condition_satisfaction': 'not_evaluated',
            'reasons': [] if witnesses else ['no_complete_qualified_statement_witness'],
            'context_compatibility': 'exact_source_fields_and_declared_context_only',
            'time_compatibility': 'same_source_annotation_not_world_simultaneity'}
