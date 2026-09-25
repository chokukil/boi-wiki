"""Internal, current-space PostgreSQL queries over native checked preparations.

Profiles are read by exact authorized revision, bounded by query definitions.
Population, current use/check/dependency joins and four-state evaluation stay in
SQL. A transactional key journal fences relevant current-space, check, use and
dependency changes without rejecting unrelated database writes. This adapter is
not a public result/cursor grant. Operational source immutability and protected
consumers still require qualification before workload/user acceptance.
"""
from dataclasses import dataclass
from pathlib import Path

from .knowledge_assertion_set_sql import compile_assertion_sets
from .knowledge_prepared_postgres import PostgresKnowledgePreparedStore, VERSION
from .knowledge_profile import KnowledgeProfileDeclaration, KnowledgeProfileRegistry, PredicateDeclaration
from .knowledge_profile_projector import ADAPTER_REVISION
from .knowledge_projection_contract import ProjectionComponent, ProjectionRevision, definition_key
from .knowledge_query import KnowledgeEvidenceQuery
from .knowledge_statement_contract import REPORTED_STATEMENT_EXISTS, statement_support_contract
from .knowledge_query_changes import KnowledgeQueryChanges
from .knowledge_space_sets import KnowledgeSpaceSets, PostgresSpaceSetBackend
from .local_bundle_checks import CHECKS
from .local_knowledge_qualification import QUALIFICATIONS, qualification_policy
from .native_knowledge_checks import shipped_checker_release
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest


_QUERY_ROOT = Path(__file__).parent
_QUERY_FILES = ('knowledge_prepared_queries.py', 'knowledge_prepared_postgres.py', 'knowledge_query_changes.py', 'knowledge_assertion_set_sql.py',
                'knowledge_evidence_set_sql.py', 'knowledge_profile.py', 'knowledge_projection_contract.py',
                'knowledge_query.py', 'filter_expression.py', 'typed_knowledge_meaning.py',
                'knowledge_space_sets.py', 'knowledge_space_store.py', '../access_policy.py',
                'knowledge_saved_sets.py', 'knowledge_prepared_results.py', 'knowledge_saved_witness_sql.py',
                'protected_execution_repository.py',
                'knowledge_query_results.py', 'knowledge_projection_store.py', 'knowledge_query_recovery.py')
_QUERY_FILES += ('knowledge_statement_evidence.py', 'knowledge_statement_contract.py')
_QUERY_IMPLEMENTATION = {name: byte_digest((_QUERY_ROOT / name).read_bytes()) for name in _QUERY_FILES}


def query_implementation():
    if any(byte_digest((_QUERY_ROOT / name).read_bytes()) != value for name, value in _QUERY_IMPLEMENTATION.items()):
        raise ValueError('KNOWLEDGE_QUERY_LOADED_IMPLEMENTATION_STALE')
    return {'contract_version': 'boi/prepared-query-implementation@1', 'files': dict(_QUERY_IMPLEMENTATION)}


@dataclass(frozen=True)
class PreparedQuerySql:
    ctes: str
    parameters: tuple


@dataclass(frozen=True)
class PreparedQueryObservation:
    result: dict
    fence: dict


class KnowledgePreparedQueries:
    def __init__(self, spaces, prepared, *, changes=None):
        if not isinstance(prepared, PostgresKnowledgePreparedStore):
            raise ValueError('KNOWLEDGE_PREPARED_QUERY_BACKEND_REQUIRED')
        self.prepared = prepared
        self.sets = KnowledgeSpaceSets(spaces, PostgresSpaceSetBackend(prepared.store,
            key_prefix=prepared.prefix, authority_store=prepared.authority_store))
        self.spaces, self.store = spaces, prepared.store
        if changes is not None and (not isinstance(changes, KnowledgeQueryChanges)
                or changes.store is not prepared.store or changes.prefix != prepared.prefix):
            raise ValueError('KNOWLEDGE_QUERY_CURRENT_CHANGE_BACKEND_REQUIRED')
        self.changes = changes if changes is not None else KnowledgeQueryChanges(prepared)

    def _audiences(self, actor_id):
        actor = self.spaces._actor(actor_id)
        targets = [{'visibility': 'private'}, {'visibility': 'public'},
                   *({'visibility': 'team', 'team_id': team} for team in sorted(set(actor.teams)))]
        return tuple(self.sets._context(actor_id, target, 'model_input')[0] for target in targets)

    def _profiles(self, actor_id, query):
        pending = [query.object_type, *(p.predicate for p in query.predicates),
                   *(s.predicate for s in query.scenario)]
        profiles, accesses, visited = {}, {}, set()
        while pending:
            component = pending.pop()
            if component in visited:
                continue
            visited.add(component)
            ref = component.revision
            if ref not in profiles:
                if len(profiles) >= 128:
                    raise ValueError('KNOWLEDGE_PROFILE_REGISTRY_BOUND')
                index = self.spaces.store.get('domain_knowledge_assets', ref.ref)
                if not index or index.get('kind') != 'profile':
                    raise ValueError('KNOWLEDGE_QUERY_PROFILE_UNAVAILABLE')
                stable_id = 'domain-asset-head:' + semantic_digest([
                    index['employee_id'], index['namespace'], index['logical_id']])
                access, _, asset = self.spaces.read(actor_id=actor_id, stable_id=stable_id,
                    revision=ref.model_dump(mode='json'), purpose='model_input')
                if asset.kind != 'profile' or asset.revision.model_dump(mode='json') != ref.model_dump(mode='json'):
                    raise ValueError('KNOWLEDGE_QUERY_PROFILE_BINDING_CHANGED')
                profiles[ref] = KnowledgeProfileDeclaration.model_validate_json(asset.content_json)
                accesses[ref] = access
            components = {f'/components/{i}': value for i, value in enumerate(profiles[ref].components)}
            declaration = components.get(component.pointer)
            if declaration is None:
                raise ValueError('KNOWLEDGE_PROFILE_COMPONENT_KIND')
            if isinstance(declaration, PredicateDeclaration):
                pending.extend(link for link in (declaration.subject_type, declaration.target_type)
                               if isinstance(link, ProjectionComponent))
        return KnowledgeProfileRegistry(profiles), accesses

    def _relation(self, binding, audiences, query, policy, release):
        ctes, parameters, allowed = [], [], []
        statement_query = query.claim_basis == REPORTED_STATEMENT_EXISTS
        grant_table = 'statement_grants' if statement_query else 'use_facts'
        grant_basis = ('k.has_statement_scope' if statement_query else 'NOT k.has_statement_scope') + ' AND NOT k.has_review_required_marker'
        for number, context in enumerate((binding, *audiences)):
            relation = self.sets.backend.relation(context)
            # Names are internal compiler constants, never user data or SQL.
            suffix = str(number)
            sql = relation.ctes.replace('boi_space_candidates', 'boi_candidates_' + suffix)
            sql = sql.replace('boi_space_checked', 'boi_checked_' + suffix).replace('boi_u', 'boi_audience_' + suffix)
            ctes.append(sql)
            parameters.extend(relation.parameters)
            if number:
                allowed.append(f'SELECT c.* FROM boi_checked_{suffix} c JOIN boi_audience_{suffix} u '
                               "ON u.id=c.entry->>'stable_id'")
        ctes.append('boi_dependency_audiences AS (' + ' UNION ALL '.join(allowed) + ')')
        ctes.append("""boi_content AS MATERIALIZED (
 SELECT c.* FROM boi_checked_0 c JOIN boi_audience_0 u ON u.id=c.entry->>'stable_id'
), boi_prepared AS MATERIALIZED (
 SELECT o.store_scope,o.preparation,o.stable_id,o.revision,o.object_type
 FROM boi_prepared_k_objects o JOIN boi_content c ON c.entry->>'stable_id'=o.stable_id
 JOIN boi_prepared_k_seals s USING(store_scope,preparation)
 WHERE o.store_scope=%s AND s.contract_version=%s AND o.adapter_revision=%s
   AND o.revision=c.head->'content_revision'->>'ref'
   AND o.native_payload_digest=c.native_index->>'record_payload_digest'
   AND o.source_manifest_digest=c.head->>'query_source_manifest_digest'
   AND o.source_policy_digest=c.head->>'query_native_policy_digest'
), boi_u AS (SELECT DISTINCT stable_id AS id FROM boi_prepared WHERE object_type=%s)
""")
        parameters.extend((self.prepared.prefix, VERSION, ADAPTER_REVISION, definition_key(query.object_type)))
        table = self.store._table
        ctes.append(f"""boi_uses_checked AS MATERIALIZED (
 SELECT k.store_scope,k.preparation,k.purpose,k.status,k.qualification_ref,k.qualification_key,
 k.qualification_wire::jsonb ? 'statement_scope' AS has_statement_scope,
 k.qualification_wire::jsonb ? 'statement_review_required' AS has_review_required_marker,
 q.payload IS NOT NULL AS entry_present,
 CASE WHEN q.payload->'qualification_ref'->>'ref'=k.qualification_ref
 THEN COALESCE((q.payload-'updated_at')=k.entry_wire::jsonb
   AND k.policy_digest=%s AND k.checker_release_digest=%s
   AND ch.payload=k.check_entry_wire::jsonb AND ch.payload->>'state'='completed'
   AND NOT EXISTS (SELECT 1 FROM boi_prepared_k_identity_targets t
     WHERE t.store_scope=k.store_scope AND t.preparation=k.preparation AND NOT EXISTS (
       SELECT 1 FROM boi_dependency_audiences a
       WHERE a.entry->>'stable_id'=t.stable_id
         AND a.policy->'content_revision'->>'ref'=t.revision
         AND a.policy->'content_revision'->>'revision_digest'=t.revision_digest
     ))
   AND NOT EXISTS (SELECT 1 FROM boi_prepared_k_dependencies d
     WHERE d.store_scope=k.store_scope AND d.preparation=k.preparation AND NOT EXISTS (
       SELECT 1 FROM boi_dependency_audiences a JOIN {table('domain_knowledge_assets')} n
         ON n.item_key=%s || d.revision
       WHERE a.entry->>'stable_id'=d.stable_id
         AND (a.policy->'content_revision'->>'ref'=d.revision OR EXISTS (
           SELECT 1 FROM jsonb_array_elements(a.policy->'visible_history') h WHERE h->>'ref'=d.revision))
         AND n.payload->>'record_payload_digest'=d.native_payload_digest
         AND n.payload->>'employee_id'=a.policy->'identity'->>'identity_creator'
         AND n.payload->>'namespace'=a.policy->'identity'->>'namespace'
         AND n.payload->>'logical_id'=a.policy->'identity'->>'logical_id'
         AND d.policy_digest=a.policy->>'source_policy_digest'
         AND (a.policy->'content_revision'->>'ref'<>d.revision
              OR d.source_manifest_digest=a.policy->>'source_closure_digest')
     )), FALSE) ELSE FALSE END AS valid
 FROM boi_prepared_k_uses k JOIN boi_prepared o USING(store_scope,preparation)
 LEFT JOIN {table(QUALIFICATIONS)} q ON q.item_key=%s || k.qualification_key
 LEFT JOIN {table(CHECKS)} ch ON ch.item_key=%s || k.check_key
 WHERE o.object_type=%s AND k.purpose=%s
), boi_qualified AS (
 SELECT DISTINCT f.fact_key,o.revision,f.fact_digest,k.purpose,k.qualification_ref
 FROM boi_uses_checked k JOIN boi_prepared_k_{grant_table} f USING(store_scope,preparation,purpose)
 JOIN boi_prepared o USING(store_scope,preparation)
 WHERE k.valid AND k.status='usable_with_limits' AND {grant_basis}
), boi_current_prepared AS (
 SELECT DISTINCT o.* FROM boi_prepared o JOIN boi_uses_checked k USING(store_scope,preparation)
 WHERE k.valid
)""")
        parameters.extend((policy, release, self.prepared.prefix, self.prepared.prefix, self.prepared.prefix,
                           definition_key(query.object_type), 'aggregate' if query.operation == 'count' else 'filter'))
        columns = {
            'facts': 'fact_key,id,revision,object_type,predicate,kind,text_value,decimal_value,boolean_value,'
                     'polarity,modality,time_state,start_at,end_at,time_scope,unresolved,adapter_valid,fact_digest,meaning_pointer',
            'clauses': 'fact_key,clause_index,group_kind,program_length',
            'atoms': 'fact_key,clause_index,atom_index,subject_ref,predicate,op,kind,text_value,decimal_value,boolean_value,known',
            'steps': 'fact_key,clause_index,step,op,arity,atom_index',
        }
        if statement_query:
            columns['statement_contexts'] = ('fact_key,revision,fact_digest,context_digest,'
                'owner_scope_digest,time_scope,unconditional,context_wire')
        for source, names in columns.items():
            target = {'atoms': 'condition_atoms', 'steps': 'condition_steps'}.get(source, source)
            selected = ','.join('f.' + column for column in names.split(','))
            ctes.append(f'boi_{target} AS (SELECT DISTINCT {selected} FROM boi_prepared_k_{source} f '
                        'JOIN boi_current_prepared o USING(store_scope,preparation) JOIN boi_u u ON u.id=o.stable_id)')
        statement_coverage = """,
 (SELECT COUNT(*) FROM boi_u u WHERE NOT EXISTS (
    SELECT 1 FROM boi_statement_contexts c JOIN boi_facts f USING(fact_key,revision,fact_digest)
    WHERE f.id=u.id)) AS members_without_statement_preparation""" if statement_query else ''
        ctes.append("""boi_coverage AS (SELECT
 (SELECT COUNT(*) FROM boi_audience_0) AS content_members,
 (SELECT COUNT(*) FROM boi_u) AS typed_population_members,
 (SELECT COUNT(*) FROM boi_content c WHERE c.native_index->>'kind' IN ('source','definition')
    AND NOT EXISTS (SELECT 1 FROM boi_prepared o WHERE o.stable_id=c.entry->>'stable_id')) AS unprepared_content_members,
 (SELECT COUNT(*) FROM boi_u u WHERE NOT EXISTS (SELECT 1 FROM boi_qualified k
    JOIN boi_prepared o ON o.revision=k.revision WHERE o.stable_id=u.id)) AS members_without_qualified_roots,
 (SELECT COUNT(*) FROM boi_checked_0 WHERE NOT valid) AS invalid_population_rows,
 (SELECT COUNT(DISTINCT k.qualification_key) FROM boi_uses_checked k
    WHERE k.entry_present AND NOT EXISTS (SELECT 1 FROM boi_uses_checked current_use
      WHERE current_use.qualification_key=k.qualification_key AND current_use.valid)) AS invalid_use_rows
""" + statement_coverage + ')')
        return PreparedQuerySql(',\n'.join(ctes), tuple(parameters))

    def _snapshot(self):
        return self.changes.snapshot()

    @staticmethod
    def _audience_authority(audiences):
        # A dependency's membership is fenced by exact journal keys. An unrelated
        # addition in another audience must not invalidate this query's result.
        return tuple({key: value for key, value in context.items() if key != 'epoch'} for context in audiences)

    def _read(self, relation, compiled, *, page):
        # Coverage and selected output are from one MVCC statement snapshot.
        if page is None:
            sql, parameters = compiled.summary_sql, compiled.parameters
        else:
            sql, parameters = compiled.page_sql(**page)
        statement = ('WITH RECURSIVE ' + relation.ctes + ', boi_output AS (' + sql +
                     ') SELECT pg_current_snapshot()::text, '
                     '(SELECT row_to_json(c) FROM boi_coverage c), '
                     "COALESCE((SELECT json_agg(r) FROM boi_output r),'[]'::json)")
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5s'")
            return connection.execute(statement, relation.parameters + parameters).fetchone()

    def execute(self, *, actor_id, set_ref, query, page=None):
        return self.observe(actor_id=actor_id, set_ref=set_ref, query=query, page=page).result

    def observe(self, *, actor_id, set_ref, query, page=None, materialize=None):
        """Internal capture for the protected repository; no caller SQL adapter."""
        query = KnowledgeEvidenceQuery.model_validate(query.model_dump(mode='json') if hasattr(query, 'model_dump') else query)
        if page is not None and query.operation != 'select_objects':
            raise ValueError('KNOWLEDGE_QUERY_COUNT_PAGE_NOT_ALLOWED')
        start = self._snapshot()
        binding = self.sets.resolve(actor_id=actor_id, set_ref=set_ref)
        if binding['purpose'] != 'model_input':
            raise ValueError('KNOWLEDGE_QUERY_MODEL_INPUT_SET_REQUIRED')
        audiences = self._audiences(actor_id)
        registry, profiles = self._profiles(actor_id, query)
        policy, release = semantic_digest(qualification_policy()), semantic_digest(shipped_checker_release())
        implementation = query_implementation()
        compiled = compile_assertion_sets(query, registry=registry)
        relation = self._relation(binding, audiences, query, policy, release)
        fence = {'contract_version': 'boi/prepared-knowledge-fence@1', 'actor_id': actor_id, 'set_ref': set_ref,
            'query_digest': semantic_digest(query), 'binding': binding, 'snapshot': start,
            'purpose': 'aggregate' if query.operation == 'count' else 'filter',
            'audiences': list(self._audience_authority(audiences)), 'qualification_policy_digest': policy,
            'checker_release_digest': release, 'query_implementation': implementation,
            'profiles': [{'revision': ref.model_dump(mode='json'), 'stable_id': access.identity.stable_id,
                          'authority_digest': access.authority_digest} for ref, access in profiles.items()]}
        if query.claim_basis == REPORTED_STATEMENT_EXISTS:
            from .knowledge_statement_contract import query_statement_support_contract
            fence['statement_consumption'] = query_statement_support_contract(query)
            fence['evidence_details'] = 'exact_revision_source_document; server witness detail endpoint pending'
        try:
            if materialize is None:
                _, coverage, output = self._read(relation, compiled, page=page)
            else:
                _, coverage, output = materialize(relation, compiled, page=page, fence=fence)
        except self.store.psycopg.Error as error:
            if (getattr(error, 'sqlstate', None) == '22P02'
                    and 'KNOWLEDGE_STATEMENT_CONTEXT_BUDGET_EXCEEDED:' in str(error)):
                # The SQL statement raises before any count/page can return;
                # a saved-set transaction also rolls back its partial writes.
                raise ValueError('KNOWLEDGE_STATEMENT_CONTEXT_BUDGET_EXCEEDED') from None
            if materialize is not None:
                # A write/commit transport failure may leave a sealed result.
                # Preserve the repository's unknown marker; do not label it as
                # a known validation failure or automatically execute again.
                raise
            raise ValueError('KNOWLEDGE_PREPARED_QUERY_READ_FAILED') from None
        return self.finish_observation(actor_id=actor_id, fence=fence, coverage=coverage, output=output, page=page)

    def finish_observation(self, *, actor_id, fence, coverage, output, page=None):
        """Complete a SQL observation or its dispatch-bound saved receipt."""
        if coverage['invalid_population_rows']:
            raise ValueError('KNOWLEDGE_SET_INDEX_UNPREPARED_OR_CHANGED')
        if coverage['invalid_use_rows']:
            raise ValueError('KNOWLEDGE_QUERY_USE_OR_DEPENDENCY_CHANGED')
        self.revalidate(actor_id=actor_id, fence=fence)
        coverage = {key: value for key, value in coverage.items() if not key.startswith('invalid_')}
        result = {'contract_version': 'boi/prepared-knowledge-query-internal@1', 'set_ref': fence['set_ref'],
            'query_digest': fence['query_digest'], 'coverage': coverage, 'rows': output,
            'output_kind': 'bounded_page_plus_one' if page is not None else 'evidence_state_counts',
            'member_ids_materialized': False, 'profile_revisions_read': len(fence['profiles']),
            'population_completeness_qualified': False, 'source_access_granted': False,
            'protected_result_granted': False, 'authority_fence': 'transactional_relevant_key_changes'}
        if 'statement_consumption' in fence:
            result['statement_consumption'] = fence['statement_consumption']
            result['evidence_details'] = fence['evidence_details']
        return PreparedQueryObservation(result, fence)

    def revalidate(self, *, actor_id, fence):
        """Check a repository-verified observation without rerunning its query."""
        return self._revalidate(actor_id=actor_id, fence=fence, historical=False)

    def authorize_stored(self, *, actor_id, fence):
        """Authorize historical evidence, without granting current query use.

        Legacy unknown pages use the unchanged population complement. Therefore
        source/native/membership/authority changes still fail closed. Only
        mutable use/check/preparation decisions may differ from the observation.
        Their historical values remain bound by the protected execution receipt.
        """
        return self._revalidate(actor_id=actor_id, fence=fence, historical=True)

    def _revalidate(self, *, actor_id, fence, historical):
        if fence.get('contract_version') != 'boi/prepared-knowledge-fence@1' or fence.get('actor_id') != actor_id:
            raise ValueError('KNOWLEDGE_RESULT_ACCESS_DENIED')
        if not historical and (fence['query_implementation'] != query_implementation()
                or fence['qualification_policy_digest'] != semantic_digest(qualification_policy())
                or fence['checker_release_digest'] != semantic_digest(shipped_checker_release())):
            raise ValueError('KNOWLEDGE_QUERY_IMPLEMENTATION_OR_POLICY_CHANGED')
        binding = self.sets.resolve(actor_id=actor_id, set_ref=fence['set_ref'])
        if (binding != fence['binding'] or list(self._audience_authority(self._audiences(actor_id))) != fence['audiences']):
            raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
        profiles = {}
        if not 1 <= len(fence['profiles']) <= 128:
            raise ValueError('KNOWLEDGE_QUERY_PROFILE_FENCE_INVALID')
        for before in fence['profiles']:
            ref = ProjectionRevision.model_validate(before['revision'])
            after, _ = self.spaces.authorize(actor_id=actor_id, stable_id=before['stable_id'],
                revision=ref.model_dump(mode='json'), purpose='model_input')
            if before['authority_digest'] != after.authority_digest:
                raise ValueError('KNOWLEDGE_QUERY_PROFILE_AUTHORITY_CHANGED')
            profiles[ref] = after
        if not self.changes.unchanged(fence['snapshot'], binding=binding, profiles=profiles,
                                      purpose=fence['purpose'], historical=historical):
            raise ValueError('KNOWLEDGE_QUERY_RELEVANT_DATA_CHANGED_DURING_READ')
        return binding
