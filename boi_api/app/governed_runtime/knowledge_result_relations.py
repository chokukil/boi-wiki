"""Bounded relational image of a recorded selection into a recorded population.

Selection evidence and edge evidence remain separate. This read neither reruns
the selection SQL nor infers world applicability or negative target facts.
"""
import json
from time import monotonic
from typing import Literal
from types import SimpleNamespace

from pydantic import Field

from .knowledge_relation_traversal import KnowledgeTraversalRequest
from .semantic_binding_contract import FrozenContract, RevisionRef
from .knowledge_projection_contract import ProjectionComponent
from .knowledge_query import KnowledgeEvidenceQuery


class KnowledgeResultRelationsRequest(FrozenContract):
    contract_version: Literal['boi/knowledge-result-relations@1'] = 'boi/knowledge-result-relations@1'
    source_result_ref: str = Field(pattern=r'^protected:prepared-knowledge-query:[0-9a-f-]{36}$')
    target_population_result_ref: str = Field(pattern=r'^protected:prepared-knowledge-query:[0-9a-f-]{36}$')
    predicate: ProjectionComponent
    target_selection: Literal['population', 'reported'] = Field(
        default='population', exclude_if=lambda value: value == 'population')


class KnowledgeResultRelations:
    """Reuse the protected-result and traversal authorities; never accept IDs."""
    def __init__(self, results, traversal):
        self.results, self.traversal = results, traversal

    def read(self, *, actor_id, request):
        req = KnowledgeResultRelationsRequest.model_validate(request)
        started, traversal_requests = monotonic(), []

        def budget():
            if monotonic() - started > 30:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_TIME_BUDGET_EXCEEDED')

        def load(reference, group):
            value = self.results._load(reference, actor_id)
            if (value['result']['execution_state'] != 'stored'
                    or value['query']['operation'] != 'select_objects'):
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_STORED_SELECTION_REQUIRED')
            if group == 'reported' and value['query']['claim_basis'] != 'reported_statement_exists':
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_SOURCE_REPORT_REQUIRED')
            # Historical readability alone cannot authorize a new composition.
            self.results._checked(value, actor_id)
            page = self.results.page(reference, actor_id=actor_id, group=group, page_size=100)
            if page['next_cursor'] is not None or page['group_count'] > 100:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_POPULATION_LIMIT_EXCEEDED')
            budget()
            return value, page

        source, selected = load(req.source_result_ref, 'reported')
        target, population = load(req.target_population_result_ref, 'all')
        source_query = KnowledgeEvidenceQuery.model_validate(source['query'])
        target_query = KnowledgeEvidenceQuery.model_validate(target['query'])
        if req.target_selection == 'reported' and target_query.claim_basis != 'reported_statement_exists':
            raise ValueError('KNOWLEDGE_RESULT_RELATIONS_TARGET_REPORT_REQUIRED')
        registry, profile_accesses = self.results.queries._profiles(actor_id, SimpleNamespace(
            object_type=source_query.object_type,
            predicates=(SimpleNamespace(predicate=req.predicate),), scenario=()))
        declaration, predicate = registry.predicate(req.predicate)
        if (predicate.value_kind != 'object' or declaration.value_semantics == 'unknown'
                or predicate.subject_type != source_query.object_type
                or predicate.target_type != target_query.object_type):
            raise ValueError('KNOWLEDGE_RESULT_RELATIONS_PREDICATE_TYPE_MISMATCH')
        target_rows = {row['id']: row for row in population['rows']}
        if len(target_rows) != population['group_count']:
            raise ValueError('KNOWLEDGE_RESULT_RELATIONS_POPULATION_MISMATCH')
        paths, traversals, outside, unresolved = [], [], [], []
        for row in selected['rows']:
            budget()
            revision = RevisionRef(ref=row['revision'],
                revision_digest=row['revision'].removeprefix('KnowledgeRevision:'))
            traversal_request = KnowledgeTraversalRequest(start_revision=revision,
                predicates=(req.predicate,), max_depth=1, max_nodes=100, max_edges=100)
            graph = self.traversal.read(actor_id=actor_id, request=traversal_request)
            traversal_requests.append(traversal_request)
            graph_index = len(traversals)
            traversals.append(graph)
            if sum(len(json.dumps(g, ensure_ascii=False).encode()) for g in traversals) > 1024 * 1024:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_OUTPUT_BUDGET_EXCEEDED')
            if graph['blocked'] or graph['boundaries']:
                unresolved.append({'source_id': row['id'], 'traversal_index': graph_index,
                    'blocked': graph['blocked'], 'boundaries': graph['boundaries']})
            for edge_index, edge in enumerate(graph['edges']):
                if not edge['continuation']:
                    continue
                if edge['source'] != row['id'] or edge['source_revision']['ref'] != row['revision']:
                    raise ValueError('KNOWLEDGE_RESULT_RELATIONS_SOURCE_BINDING_CHANGED')
                destination = target_rows.get(edge['target'])
                if destination is None:
                    outside.append({'source_id':row['id'], 'traversal_index':graph_index,
                        'edge_index':edge_index, 'reason':'outside_requested_target_population'})
                    continue
                if destination['revision'] != edge['target_revision']['ref']:
                    raise ValueError('KNOWLEDGE_RESULT_RELATIONS_TARGET_REVISION_CHANGED')
                paths.append({'source_id':row['id'], 'source_revision':row['revision'],
                    'source_report_state':row['state'], 'source_witness_read':row['witness_read'],
                    'target_id':destination['id'], 'target_revision':destination['revision'],
                    'traversal_index':graph_index, 'edge_index':edge_index,
                    'condition_composition':'not_evaluated'})
            if sum(len(g['edges']) for g in traversals) > 256:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_EDGE_LIMIT_EXCEEDED')
        rows = []
        for identity, row in target_rows.items():
            indexes = [i for i, path in enumerate(paths) if path['target_id'] == identity]
            rows.append({'id':identity, 'revision':row['revision'],
                'state':'reported_link_found' if indexes else 'no_selected_reported_link',
                'path_indexes':indexes, 'document_read':row['document_read']})
        linked = sum(bool(row['path_indexes']) for row in rows)
        result = {'contract_version':'boi/knowledge-result-relations-result@1',
            'request':req.model_dump(mode='json'), 'status':'partial' if unresolved else 'completed',
            'source_result_digest':selected['result_digest'],
            'target_population_result_digest':population['result_digest'],
            'source_counts':selected['counts'], 'source_coverage':selected['coverage'],
            'target_population_counts':population['counts'], 'target_population_coverage':population['coverage'],
            'selected_source_count':len(selected['rows']), 'target_population_count':len(rows),
            'linked_target_count':linked, 'no_selected_link_count':len(rows)-linked,
            'rows':rows, 'paths':paths, 'traversals':traversals,
            'outside_target_population':outside, 'unresolved_relations':unresolved,
            'query_reexecuted':False, 'result_persisted':False,
            'semantics':{'selection':'reported_group_including_conflicted',
                'target_population':'all_rows_of_exact_target_result_regardless_of_its_filter_state',
                'relation':'one_authored_positive_edge_with_separate_current_traverse_qualification',
                'no_selected_reported_link':'no_link_from_selected_reports_not_physical_absence',
                'conflicts':'source_report_state_retained_per_path',
                'conditions':'source_selection_and_edge_context_retained_separately_without_world_composition'},
            'population_completeness_qualified':False, 'scientific_truth_proven':False}
        if req.target_selection == 'reported':
            target_selected = 0
            for row in rows:
                original = target_rows[row['id']]
                reported = original['state'] in ('supported', 'conflicted')
                witness = original.get('witness_read') if reported else None
                if reported and witness is None:
                    raise ValueError('KNOWLEDGE_RESULT_RELATIONS_TARGET_WITNESS_REQUIRED')
                target_selected += int(reported)
                row.update(target_report_state=original['state'], target_witness_read=witness,
                    intersection_member=bool(row['path_indexes']) and reported)
            result['intersection'] = {
                'contract_version':'boi/knowledge-relation-report-intersection@1',
                'target_selection':'reported_including_conflicted',
                'target_selected_count':target_selected,
                'member_count':sum(row['intersection_member'] for row in rows),
                'basis':'exact_current_target_identity_and_revision_in_both_report_sets',
                'nonmember':'no_joint_report_witness_not_negative_or_physical_absence',
                'conditions':'source_selection_edge_and_target_report_contexts_remain_separate',
                'same_world_condition_satisfaction':'not_evaluated',
                'conflicts':'target_report_state_and_each_path_source_report_state_preserved'}
        if len(json.dumps(result, ensure_ascii=False).encode()) > 2 * 1024 * 1024:
            raise ValueError('KNOWLEDGE_RESULT_RELATIONS_OUTPUT_BUDGET_EXCEEDED')
        # Reuse the complete public traversal authority/source fences. A second
        # bounded relation read must reproduce each earlier graph exactly;
        # no original selection SQL is executed by either pass.
        for traversal_request, graph in zip(traversal_requests, traversals):
            budget()
            current = self.traversal.read(actor_id=actor_id, request=traversal_request)
            if current != graph:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_GRAPH_CHANGED')
        self.results._checked(source, actor_id)
        self.results._checked(target, actor_id)
        for revision, before in profile_accesses.items():
            current, _ = self.results.queries.spaces.authorize(actor_id=actor_id,
                stable_id=before.identity.stable_id, revision=revision.model_dump(mode='json'), purpose='model_input')
            if current != before:
                raise ValueError('KNOWLEDGE_RESULT_RELATIONS_PROFILE_AUTHORITY_CHANGED')
        budget()
        return result
