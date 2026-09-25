"""Prepared typed assertions -> PostgreSQL evidence sets.

Internal compiler only. Its server relations must be a single currently
authorized snapshot: boi_u, boi_facts, boi_clauses, boi_condition_atoms,
boi_condition_steps and boi_qualified. The last relation must contain current
per-use qualification; neither the query nor preparation creates that grant.
No source body/ledger is copied into the query, and count builds no trace rows.
"""
from dataclasses import dataclass, replace

from .knowledge_evidence_set_sql import compile_evidence_set_sql
from .knowledge_projection_contract import ProjectionFact, ProjectionRevision, definition_key
from .knowledge_query import KnowledgeEvidenceQuery
from .knowledge_statement_contract import REPORTED_STATEMENT_EXISTS
from .semantic_binding_contract import semantic_digest
from .typed_knowledge_meaning import KnowledgeValidTime, TypedCondition


def scalar_columns(value):
    return (value.kind, value.value if value.kind in ('text', 'object') else None,
            value.value if value.kind == 'decimal' else None,
            value.value if value.kind == 'boolean' else None)


@dataclass(frozen=True)
class PreparedAssertion:
    fact: tuple
    clauses: tuple
    atoms: tuple
    steps: tuple


def prepare_assertion(*, stable_id, revision, object_type, fact, registry):
    """Bounded ingestion adapter; retain native payload separately as the source.

    Conditions become indexed atoms and a bounded postfix program. This avoids
    exponential DNF expansion and never pre-evaluates a hypothetical context.
    """
    revision = ProjectionRevision.model_validate(revision.model_dump(mode='json'))
    fact = ProjectionFact.model_validate(fact.model_dump(mode='json'))
    if not isinstance(stable_id, str) or not stable_id.strip():
        raise ValueError('KNOWLEDGE_SET_PREPARED_ID_REQUIRED')
    declaration, predicate = registry.predicate(fact.predicate_revision)
    if predicate.subject_type != object_type or predicate.value_kind != fact.value.kind:
        raise ValueError('KNOWLEDGE_SET_PREPARED_TYPE_MISMATCH')
    valid = KnowledgeValidTime.model_validate(fact.valid_time)
    key = semantic_digest([stable_id, revision.model_dump(mode='json'), fact.meaning_pointer, semantic_digest(fact)])
    qualifiers = fact.qualifiers
    supported_adapter = (qualifiers.get('contract_version') == 'boi/typed-assertion-qualifiers@1'
                         and qualifiers.get('assertion_kind') == 'source_reported')
    clauses, atoms, steps = [], [], []
    for group in ('conditions', 'applicability', 'exceptions'):
        if not isinstance(qualifiers.get(group, []), list) or len(qualifiers.get(group, [])) > 64:
            raise ValueError('KNOWLEDGE_SET_PREPARED_CONDITION_LIMIT')
        for raw in qualifiers.get(group, ()):
            clause = TypedCondition.model_validate(raw)
            index = len(clauses)
            program = []
            def visit(node):
                for child in node.arguments:
                    visit(child)
                program.append((key, index, len(program), node.operator,
                                len(node.arguments), node.filter_index))
            if clause.expression is not None:
                visit(clause.expression)
            clauses.append((key, index, group, len(program)))
            steps.extend(program)
            for ai, atom in enumerate(clause.atoms):
                declared, typed = registry.predicate(atom.predicate)
                known = (atom.operator in declared.allowed_operators and atom.value.kind == typed.value_kind
                         and declared.quantity_semantics != 'unknown' and declared.value_semantics != 'unknown')
                atoms.append((key, index, ai, atom.subject_ref, definition_key(atom.predicate),
                              atom.operator, *scalar_columns(atom.value), known))
    row = (key, stable_id, revision.ref, definition_key(object_type), definition_key(fact.predicate_revision),
           *scalar_columns(fact.value), fact.polarity, fact.modality, valid.state, valid.start, valid.end,
           semantic_digest(fact.valid_time), bool(set(fact.unresolved) - {'valid_time_unknown'}),
           supported_adapter, semantic_digest(fact), fact.meaning_pointer)
    return PreparedAssertion(row, tuple(clauses), tuple(atoms), tuple(steps))


def _comparison(left, right, operator):
    # Aliases/operator are compiler constants. All request values are parameters.
    comparisons = []
    for kind, column in (('text', 'text_value'), ('object', 'text_value'),
                         ('decimal', 'decimal_value'), ('boolean', 'boolean_value')):
        kinds = f"{left}.kind='{kind}' AND {right}.kind='{kind}'"
        operations = ('eq', 'ne', 'lt', 'lte', 'gt', 'gte') if kind == 'decimal' else ('eq', 'ne')
        cases = ' '.join(f"WHEN '{op}' THEN {left}.{column} {symbol} {right}.{column}"
                        for op, symbol in (('eq', '='), ('ne', '<>'), ('lt', '<'), ('lte', '<='), ('gt', '>'), ('gte', '>='))
                        if op in operations)
        comparisons.append(f"WHEN {kinds} THEN CASE {operator} {cases} END")
    return 'CASE ' + ' '.join(comparisons) + ' END'


@dataclass(frozen=True)
class AssertionSetSql:
    ctes: tuple
    parameters: tuple
    evidence: object
    statement_query: bool = False

    @property
    def summary_sql(self):
        return self.evidence.summary_sql.replace('WITH ', 'WITH RECURSIVE ', 1)

    def page_sql(self, **kwargs):
        sql, parameters = self.evidence.page_sql(dialect='postgres', **kwargs)
        if self.statement_query:
            # LIMIT is evaluated even when a selected state has zero rows.
            # Therefore negative-only oversized contexts cannot return an
            # apparently successful empty supported page.
            body, limit = sql.rsplit(' LIMIT ', 1)
            sql = body + ' LIMIT (' + limit + ' + 0 * (SELECT allowed FROM boi_statement_budget))'
        return sql.replace('WITH ', 'WITH RECURSIVE ', 1), self.parameters + parameters


def compile_assertion_sets(query, *, registry):
    """Compile the existing logical contract, without caller SQL/physical plans.

    Condition NULL below means absent hypothetical scenario information, not
    refuting knowledge. Applicable qualified facts feed the four-state kernel.
    Current qualifiers, publication generations and result protection belong to
    the enclosing server adapter and must not be bypassed to use this compiler.
    """
    query = KnowledgeEvidenceQuery.model_validate(query.model_dump(mode='json'))
    values, parameters = [], []
    for index, test in enumerate(query.predicates):
        declaration, predicate = registry.predicate(test.predicate)
        if (predicate.value_kind != test.value.kind or predicate.subject_type != query.object_type
                or test.operator not in declaration.allowed_operators):
            raise ValueError('KNOWLEDGE_QUERY_PREDICATE_NOT_ALLOWED')
        values.append('(%s::int,%s::text,%s::text,%s::text,%s::numeric,%s::boolean,%s::text,%s::text,%s::boolean,%s::text)')
        parameters.extend((index, definition_key(test.predicate), *scalar_columns(test.value), test.operator,
                           declaration.cardinality, declaration.quantity_semantics != 'unknown'
                           and declaration.value_semantics != 'unknown', test.report_polarity or query.polarity))
    ctes = ['boi_tests(atom,predicate,kind,text_value,decimal_value,boolean_value,op,cardinality,known,report_polarity) AS (VALUES '
            + ','.join(values) + ')']
    scoped=[(i,v) for i,t in enumerate(query.predicates) for v in t.source_scope]
    source_rows=[]
    for i,v in scoped:
        source_rows.append('(%s::int,%s::text,%s::text)')
        parameters.extend((i,v.revision.ref,v.meaning_pointer))
    source_sql='VALUES '+','.join(source_rows) if scoped else 'SELECT NULL::int,NULL::text,NULL::text WHERE FALSE'
    ctes.append('boi_test_sources(atom,revision,meaning_pointer) AS ('+source_sql+')')
    if query.claim_basis == REPORTED_STATEMENT_EXISTS:
        return _compile_statement_sets(query, ctes=ctes, parameters=parameters)
    scenarios = []
    for item in query.scenario:
        declaration, predicate = registry.predicate(item.predicate)
        if predicate.value_kind != item.value.kind:
            raise ValueError('KNOWLEDGE_QUERY_VALUE_TYPE_MISMATCH')
        scenarios.append('(%s::text,%s::text,%s::text,%s::text,%s::numeric,%s::boolean)')
        parameters.extend((item.subject_ref, definition_key(item.predicate), *scalar_columns(item.value)))
    scenario_sql = ('VALUES ' + ','.join(scenarios)) if scenarios else (
        'SELECT NULL::text,NULL::text,NULL::text,NULL::text,NULL::numeric,NULL::boolean WHERE FALSE')
    ctes.append('boi_scenarios(subject_ref,predicate,kind,text_value,decimal_value,boolean_value) AS (' + scenario_sql + ')')
    ctes.append('boi_query_context(object_type,purpose,modality,polarity,time_mode,as_of) AS '
                '(VALUES (%s::text,%s::text,%s::text,%s::text,%s::text,%s::timestamptz))')
    parameters.extend((definition_key(query.object_type), 'aggregate' if query.operation == 'count' else 'filter',
                       query.modality, query.polarity, query.time_mode, query.as_of))
    # Restrict the interpreter before evaluating conditions; unrelated objects,
    # predicates, revisions and unusable facts never enter the recursive work.
    ctes.append("""boi_selected_facts AS MATERIALIZED (
 SELECT f.* FROM boi_facts f CROSS JOIN boi_query_context q
 WHERE EXISTS (SELECT 1 FROM boi_u u WHERE u.id=f.id)
   AND EXISTS (SELECT 1 FROM boi_tests t WHERE t.predicate=f.predicate AND t.kind=f.kind AND t.known)
   AND EXISTS (SELECT 1 FROM boi_qualified k WHERE k.fact_key=f.fact_key AND k.revision=f.revision
       AND k.fact_digest=f.fact_digest AND k.purpose=q.purpose)
   AND f.object_type=q.object_type AND f.modality=q.modality AND f.adapter_valid AND NOT f.unresolved
   AND (q.time_mode='source_declared' OR f.time_state='timeless' OR
       (f.time_state='interval' AND f.start_at<=q.as_of AND (f.end_at IS NULL OR q.as_of<f.end_at)))
)""")
    ctes.append('boi_condition_values AS MATERIALIZED (SELECT a.fact_key,a.clause_index,a.atom_index, '
                + 'CASE WHEN a.known THEN ' + _comparison('s', 'a', 'a.op') + ' END AS value '
                + 'FROM boi_condition_atoms a JOIN boi_selected_facts f ON f.fact_key=a.fact_key '
                + 'LEFT JOIN boi_scenarios s ON s.subject_ref=a.subject_ref AND s.predicate=a.predicate)')
    # One step per checked AST node, using a bounded boolean stack. SQL bool_and
    # ignores NULL, so three-valued logic must explicitly inspect NULL presence.
    ctes.append("""boi_condition_eval(fact_key,clause_index,step,stack) AS (
 SELECT c.fact_key,c.clause_index,0,ARRAY[]::boolean[]
 FROM boi_clauses c JOIN boi_selected_facts f ON f.fact_key=c.fact_key
 UNION ALL
 SELECT e.fact_key,e.clause_index,e.step+1,
   e.stack[1:cardinality(e.stack)-p.arity] || ARRAY[CASE p.op
     WHEN 'filter' THEN a.value WHEN 'not' THEN NOT e.stack[cardinality(e.stack)]
     WHEN 'and' THEN CASE WHEN vals.has_false THEN FALSE WHEN vals.has_null THEN NULL ELSE TRUE END
     WHEN 'or' THEN CASE WHEN vals.has_true THEN TRUE WHEN vals.has_null THEN NULL ELSE FALSE END END]
 FROM boi_condition_eval e JOIN boi_condition_steps p
   ON p.fact_key=e.fact_key AND p.clause_index=e.clause_index AND p.step=e.step
 LEFT JOIN boi_condition_values a ON a.fact_key=p.fact_key AND a.clause_index=p.clause_index AND a.atom_index=p.atom_index
 CROSS JOIN LATERAL (SELECT bool_or(v IS FALSE) AS has_false, bool_or(v IS TRUE) AS has_true,
                    bool_or(v IS NULL) AS has_null
   FROM unnest(e.stack[cardinality(e.stack)-p.arity+1:cardinality(e.stack)]) AS v) vals
 WHERE e.step<256
)""")
    ctes.append("""boi_clause_results AS (
 SELECT c.fact_key,c.clause_index,c.group_kind,
   CASE WHEN c.program_length>0 AND cardinality(e.stack)=1 THEN e.stack[1] END AS value
 FROM boi_clauses c JOIN boi_selected_facts f ON f.fact_key=c.fact_key
 LEFT JOIN boi_condition_eval e ON e.fact_key=c.fact_key AND e.clause_index=c.clause_index AND e.step=c.program_length
), boi_applicable_facts AS (
 SELECT f.* FROM boi_selected_facts f WHERE NOT EXISTS (
 SELECT 1 FROM boi_clause_results c WHERE c.fact_key=f.fact_key AND
   (c.value IS NULL OR (c.group_kind='exceptions' AND c.value) OR (c.group_kind<>'exceptions' AND NOT c.value)))
)""")
    ctes.append('boi_comparisons AS (SELECT f.*,t.atom,t.op,t.cardinality,q.polarity AS query_polarity,q.time_mode, '
                + _comparison('f', 't', "'eq'") + ' AS equal, '
                + _comparison('f', 't', "CASE WHEN t.op='ne' THEN 'eq' ELSE t.op END") + ' AS matched '
                + 'FROM boi_applicable_facts f JOIN boi_tests t ON t.predicate=f.predicate AND t.kind=f.kind '
                + 'CROSS JOIN boi_query_context q WHERE t.known AND (NOT EXISTS (SELECT 1 FROM boi_test_sources z WHERE z.atom=t.atom) OR EXISTS (SELECT 1 FROM boi_test_sources z WHERE z.atom=t.atom AND z.revision=f.revision AND z.meaning_pointer=f.meaning_pointer)))')
    ctes.append("""boi_fact_pairs AS (
 SELECT *, CASE WHEN modality<>'asserted' THEN polarity=query_polarity AND
                    CASE WHEN polarity='positive' THEN matched ELSE op IN ('eq','ne') AND equal END
                ELSE polarity='positive' AND matched END AS support,
           CASE WHEN modality<>'asserted' THEN FALSE
                WHEN polarity='negative' THEN op IN ('eq','ne') AND equal
                ELSE NOT matched AND cardinality='one' END AS refute
 FROM boi_comparisons
), boi_swapped_pairs AS (
 SELECT *, CASE WHEN ((modality='asserted' AND query_polarity='negative') <> (op='ne'))
                     THEN refute ELSE support END AS t,
           CASE WHEN ((modality='asserted' AND query_polarity='negative') <> (op='ne'))
                     THEN support ELSE refute END AS f
 FROM boi_fact_pairs
), boi_atom_scopes AS (
 SELECT atom,id,bool_or(t) AS t,bool_or(f) AS f,
        COUNT(DISTINCT CASE WHEN time_mode='source_declared' THEN time_scope ELSE 'at' END) AS periods
 FROM boi_swapped_pairs WHERE t OR f GROUP BY atom,id
), boi_atom_support AS (
 SELECT atom,id FROM boi_atom_scopes WHERE t AND NOT (t AND f AND periods>1)
), boi_atom_refute AS (
 SELECT atom,id FROM boi_atom_scopes WHERE f AND NOT (t AND f AND periods>1)
)""")
    evidence = compile_evidence_set_sql(query.expression, len(query.predicates))
    evidence = replace(evidence, ctes=tuple(ctes) + evidence.ctes)
    return AssertionSetSql(tuple(ctes), tuple(parameters), evidence)


def _compile_statement_sets(query, *, ctes, parameters):
    """Evaluate the AST per exact source context, then project witnesses.

    boi_qualified contains only current, sealed statement-scope grants on this
    path. Native condition text is retained by boi_statement_contexts, not
    evaluated as a real-world scenario. A negative report in another context
    never refutes the existence of a supported report. Exact source owner sets
    and native revisions must match before unconditional evidence is shared.
    """
    ctes = list(ctes)
    parameters = list(parameters)
    ctes.append("""boi_statement_selected AS MATERIALIZED (
 SELECT f.*,c.context_digest,c.owner_scope_digest,c.unconditional
 FROM boi_facts f JOIN boi_statement_contexts c
   ON c.fact_key=f.fact_key AND c.revision=f.revision AND c.fact_digest=f.fact_digest
     AND c.time_scope=f.time_scope
 WHERE EXISTS (SELECT 1 FROM boi_u u WHERE u.id=f.id)
   AND EXISTS (SELECT 1 FROM boi_tests t WHERE t.predicate=f.predicate AND t.kind=f.kind AND t.known)
   AND EXISTS (SELECT 1 FROM boi_qualified k WHERE k.fact_key=f.fact_key AND k.revision=f.revision
     AND k.fact_digest=f.fact_digest AND k.purpose='filter')
   AND f.object_type=%s AND f.modality=%s AND f.adapter_valid
), boi_statement_witnesses AS (
 SELECT DISTINCT jsonb_build_array(id,revision,context_digest)::text AS witness_id,
   id AS object_id,revision,context_digest,owner_scope_digest,time_scope
 FROM boi_statement_selected
), boi_statement_budget AS MATERIALIZED (
 SELECT COALESCE(MIN(CAST(CASE WHEN contexts>256
   THEN 'KNOWLEDGE_STATEMENT_CONTEXT_BUDGET_EXCEEDED:' || object_id ELSE '1' END AS integer)),1) AS allowed
 FROM (SELECT object_id,COUNT(*) AS contexts FROM boi_statement_witnesses GROUP BY object_id) counted
), boi_statement_population AS (
 SELECT u.id FROM boi_u u CROSS JOIN boi_statement_budget b WHERE b.allowed=1
), boi_statement_comparisons AS (
 SELECT w.witness_id,f.fact_key,f.meaning_pointer,f.polarity,f.modality,t.atom,t.cardinality,t.report_polarity,t.op,
""" + _comparison('f', 't', "'eq'") + ' AS equal, ' + _comparison('f','t','t.op') + """ AS matched
 FROM boi_statement_witnesses w JOIN boi_statement_selected f
   ON f.id=w.object_id AND f.revision=w.revision AND f.owner_scope_digest=w.owner_scope_digest
     AND f.time_scope=w.time_scope AND (f.context_digest=w.context_digest OR f.unconditional)
 JOIN boi_tests t ON t.predicate=f.predicate AND t.kind=f.kind
 WHERE t.known AND (NOT EXISTS (SELECT 1 FROM boi_test_sources z WHERE z.atom=t.atom) OR EXISTS (SELECT 1 FROM boi_test_sources z WHERE z.atom=t.atom AND z.revision=f.revision AND z.meaning_pointer=f.meaning_pointer))
), boi_statement_effects AS (
 SELECT c.*,CASE WHEN op='eq' THEN (polarity=report_polarity AND equal)
     ELSE polarity='positive' AND matched END AS supports,
   CASE WHEN op='eq' THEN ((polarity<>report_polarity AND equal) OR (report_polarity='positive'
     AND polarity='positive' AND NOT equal AND cardinality='one' AND modality='asserted'))
     ELSE polarity='positive' AND NOT matched AND cardinality='one' END AS refutes
 FROM boi_statement_comparisons c
), boi_statement_eval_u AS (
 SELECT w.witness_id AS id FROM boi_statement_witnesses w
 JOIN boi_statement_population p ON p.id=w.object_id),
boi_statement_eval_atom_support AS (
 SELECT DISTINCT atom,witness_id AS id FROM boi_statement_effects WHERE supports
), boi_statement_eval_atom_refute AS (
 SELECT DISTINCT atom,witness_id AS id FROM boi_statement_effects WHERE refutes
)""")
    parameters.extend((definition_key(query.object_type),query.modality))
    # Reuse the four-state kernel on witness IDs. Renaming applies only to
    # compiler-owned identifiers, never request data or source expressions.
    kernel = compile_evidence_set_sql(query.expression, len(query.predicates))
    prefix = 'boi_statement_eval_'
    ctes.extend(sql.replace('boi_', prefix) for sql in kernel.ctes)
    ctes.extend((
        """boi_statement_matches AS (
 SELECT DISTINCT w.object_id AS id FROM boi_statement_witnesses w JOIN (
   SELECT id FROM boi_statement_eval_supported UNION SELECT id FROM boi_statement_eval_conflicted
 ) matched ON matched.id=w.witness_id)""",
        """boi_conflicted AS (
 SELECT DISTINCT w.object_id AS id FROM boi_statement_witnesses w
 JOIN boi_statement_eval_conflicted c ON c.id=w.witness_id)""",
        'boi_supported AS (SELECT id FROM boi_statement_matches EXCEPT SELECT id FROM boi_conflicted)',
        'boi_refuted AS (SELECT id FROM boi_u WHERE FALSE)',
        'boi_known AS (SELECT id FROM boi_statement_matches)',
        'boi_unknown AS (SELECT id FROM boi_statement_population EXCEPT SELECT id FROM boi_statement_matches)',
    ))
    evidence = replace(kernel, ctes=tuple(ctes), atom_relations=tuple(
        tuple(name.replace('boi_', prefix) for name in pair) for pair in kernel.atom_relations))
    return AssertionSetSql(tuple(ctes), tuple(parameters), evidence, statement_query=True)
