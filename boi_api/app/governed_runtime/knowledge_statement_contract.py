"""Registered source-statement consumption semantics; no caller authority.

These names distinguish a report's existence from satisfaction of its conditions
in the world. Classification still requires an exact authenticated source review.
"""
from typing import Literal

QUERY_V2 = 'boi/knowledge-evidence-query@2'
QUERY_V3 = 'boi/knowledge-evidence-query@3'
QUERY_V4 = 'boi/knowledge-evidence-query@4'
REPORTED_STATEMENT_EXISTS = 'reported_statement_exists'
STATEMENT_USE_PURPOSE = 'filter'
STATEMENT_SCOPE_VERSION = 'boi/reported-statement-scope@1'
MODAL_STATEMENT_SCOPE_VERSION = 'boi/reported-statement-scope@2'
MODAL_STATEMENT_REVIEW_VERSION = 'boi/source-statement-review@2'
TRAVERSAL_SCOPE_VERSION = 'boi/reported-relation-scope@1'
TRAVERSAL_REVIEW_VERSION = 'boi/source-relation-review@1'


def statement_versions(purpose, *, modality_aware=False):
    if purpose == 'filter':
        if modality_aware:
            return MODAL_STATEMENT_SCOPE_VERSION, MODAL_STATEMENT_REVIEW_VERSION
        return STATEMENT_SCOPE_VERSION, 'boi/source-statement-review@1'
    if purpose == 'traverse':
        return TRAVERSAL_SCOPE_VERSION, TRAVERSAL_REVIEW_VERSION
    raise ValueError('KNOWLEDGE_STATEMENT_PURPOSE_UNREGISTERED')


def modal_statement_support_contract():
    return {
        'contract_version':'boi/reported-modal-statement-qualification@1',
        'review_contract_version':MODAL_STATEMENT_REVIEW_VERSION,
        'scope_contract_version':MODAL_STATEMENT_SCOPE_VERSION,
        'purpose':'filter', 'claim_basis':REPORTED_STATEMENT_EXISTS,
        'modalities':['asserted','possible','intended','required'],
        'modality_conversion':False,
        'scope':'exact_reviewed_assertion_with_original_modality_polarity_and_context',
        'world_condition_satisfaction':'not_evaluated',
        'scientific_truth_granted':False, 'physical_execution_granted':False,
    }


def traversal_support_contract():
    return {
        'contract_version': 'boi/reported-relation-support@1',
        'claim_basis': REPORTED_STATEMENT_EXISTS, 'purpose': 'traverse',
        'review_contract_version': TRAVERSAL_REVIEW_VERSION,
        'scope_contract_version': TRAVERSAL_SCOPE_VERSION,
        'direction': 'authored_subject_to_object',
        'traversed_polarity': 'positive', 'modality': 'asserted',
        'negative_relations': 'retain_without_continuation',
        'assertion_kind': 'source_reported',
        'target_resolution': 'exact_stable_identity_current_authorized_revision',
        'target_type': 'exact_profile_component',
        'classification_basis': 'authenticated_exact_source_inventory_review',
        'conditions': 'preserve_per_edge_without_world_evaluation_or_path_composition',
        'source_access': 'separately_authorized_at_each_step_and_final_fence',
        'causal_inference': False, 'adjacency_inferred': False,
        'population_completeness_granted': False, 'scientific_truth_granted': False,
        'physical_execution_granted': False,
    }

UnresolvedFacet = Literal[
    'source_fidelity', 'source_context_identity', 'current_applicability',
    'physical_binding', 'population_coverage', 'independent_scientific_validation',
    'upstream_source_fidelity', 'source_completeness',
]
BLOCKING_STATEMENT_FACETS = frozenset(('source_fidelity', 'source_context_identity'))
LIMITING_STATEMENT_FACETS = frozenset((
    'current_applicability', 'physical_binding', 'population_coverage',
    'independent_scientific_validation',
    'upstream_source_fidelity', 'source_completeness',
))


def statement_support_contract():
    """Return a fresh registration value suitable for a policy digest."""
    return {
        'contract_version': 'boi/reported-statement-support@2',
        'query_contract_version': QUERY_V2,
        'claim_basis': REPORTED_STATEMENT_EXISTS,
        'purpose': STATEMENT_USE_PURPOSE,
        'operation': 'select_objects', 'time_mode': 'source_declared',
        'modality': 'asserted', 'query_polarities': ['positive', 'negative'],
        'predicate_report_polarity': 'explicit_override_or_inherit_query_polarity',
        'negative_support': 'explicit_negative_report_of_equal_value_only',
        'negative_refutation': 'explicit_positive_report_of_equal_value_only',
        'absence_or_other_value_implies_negative_report': False,
        'predicate_operators': ['eq'],
        'expression_operators': ['filter', 'and', 'or'],
        'assertion_kind': 'source_reported',
        'blocking_facets': sorted(BLOCKING_STATEMENT_FACETS),
        'limiting_facets': sorted(LIMITING_STATEMENT_FACETS),
        'classification_basis': 'authenticated_exact_source_inventory_review',
        'legacy_unclassified_relevant_items': 'blocking',
        'world_condition_satisfaction': 'not_evaluated',
        'opaque_qualifiers': 'preserve_exact_source_bound_context',
        'statement_evaluation': {
            'order': 'four_state_ast_per_context_then_object_existence',
            'context_components': ['source_owner_field_set', 'conditions', 'applicability',
                'exceptions', 'valid_time', 'depends_on'],
            'context_equivalence': 'exact_source_and_raw_context_only',
            'supported': 'requested_signed_ast_witness_without_root_refutation_in_that_witness',
            'conflicted': 'requested_signed_ast_witness_with_root_refutation_in_that_witness',
            'unknown': 'no_requested_signed_ast_witness',
            'outer_refuted_emitted': False,
            'discovery_states': ['supported', 'conflicted'],
            'requested_report_existence_preserved_when_conflicted': True,
            'opposite_reports_in_other_contexts': 'preserve_countercontexts_without_refuting_existence',
            'unconditional_lift': {
                'same': ['source_owner_field_set', 'valid_time'],
                'empty': ['conditions', 'applicability', 'exceptions', 'depends_on'],
            },
            'world_time_proof': False,
            'semantic_equivalence_inferred': False,
        },
        'population_completeness_granted': False,
        'scientific_truth_granted': False, 'physical_execution_granted': False,
    }


def query_statement_support_contract(query):
    """Versioned query consumption metadata; existing review policy stays exact."""
    value=statement_support_contract()
    if query.contract_version in (QUERY_V3,QUERY_V4):
        value.update(contract_version='boi/reported-statement-support@3',
            query_contract_version=QUERY_V3,operation=query.operation,
            predicate_operators=['eq','lt','lte','gt','gte'],
            comparison_basis='positive_source_declared_decimal_in_exact_profile_unit',
            count_grain=query.count_grain,
            deduplication='stable_source_object_identity_within_saved_snapshot',
            negative_numeric_report_implies_interval=False)
    if query.contract_version==QUERY_V4:
        value.update(contract_version='boi/reported-statement-support@4',
            query_contract_version=QUERY_V4,modality=query.modality,
            supported_modalities=['asserted','possible','intended','required'],
            predicate_operators=['eq','lt','lte','gt','gte'] if query.modality=='asserted' else ['eq'],
            modality_matching='exact_per_query_without_conversion',
            different_modalities='separate_queries_preserving_each_report_witness',
            functional_refutation='asserted_reports_only',
            modal_statement_qualification=modal_statement_support_contract())
    return value
