"""Persist the evaluated source contexts and atomic evidence of a statement query.

The caller supplies the actual compiled, authorized statement CTEs. This adds
provenance to that same statement; it never reruns a saved query. Atomic
counterevidence remains visible even when an OR branch masks it in the result.
"""

VERSION = 'boi/saved-statement-witnesses@1'


def witness_ctes(query, compiled):
    if not compiled.statement_query or query.operation != 'select_objects':
        raise ValueError('KNOWLEDGE_RESULT_STATEMENT_WITNESSES_REQUIRED')
    ctes, paths = [], {}
    serial = 0

    def build(node):
        nonlocal serial
        if node.operator == 'filter':
            return (compiled.evidence.atom_relations[node.filter_index], node, ())
        children = tuple(build(child) for child in node.arguments)
        if node.operator == 'not':
            return (children[0][0][::-1], node, children)
        pair = (f'boi_trace_n{serial}_t', f'boi_trace_n{serial}_f')
        serial += 1
        operations = ('INTERSECT', 'UNION') if node.operator == 'and' else ('UNION', 'INTERSECT')
        for side, operation in enumerate(operations):
            body = f' {operation} '.join(f'SELECT id FROM {child[0][side]}' for child in children)
            ctes.append(f'{pair[side]} AS ({body})')
        return pair, node, children

    tree = build(query.expression)

    def walk(tree, side, ancestors, final_side):
        pair, node, children = tree
        ancestors = (*ancestors, pair[side])
        if node.operator == 'filter':
            paths.setdefault((node.filter_index, side, final_side), []).append(ancestors)
        elif node.operator == 'not':
            walk(children[0], 1-side, ancestors, final_side)
        else:
            for child in children:
                walk(child, side, ancestors, final_side)

    walk(tree, 0, (), 0)
    walk(tree, 1, (), 1)

    def used(final_side):
        terms = []
        for (atom, side, final), alternatives in paths.items():
            if final != final_side:
                continue
            for names in alternatives:
                active = ' AND '.join(f'EXISTS (SELECT 1 FROM {name} s WHERE s.id=c.witness_id)'
                                      for name in dict.fromkeys(names))
                effect = 'support' if side == 0 else 'refute'
                terms.append(f"(c.atom={atom} AND c.effect='{effect}' AND {active})")
        return '(' + ' OR '.join(terms) + ')' if terms else 'FALSE'

    ctes.append("""boi_trace_contexts AS (
 SELECT w.*,CASE WHEN EXISTS (SELECT 1 FROM boi_statement_eval_conflicted x WHERE x.id=w.witness_id)
   THEN 'conflicted' ELSE 'supported' END AS context_state
 FROM boi_statement_witnesses w
 WHERE EXISTS (SELECT 1 FROM boi_statement_eval_supported x WHERE x.id=w.witness_id)
    OR EXISTS (SELECT 1 FROM boi_statement_eval_conflicted x WHERE x.id=w.witness_id)
), boi_trace_effects AS (
 SELECT c.*,CASE WHEN supports THEN 'support' WHEN refutes THEN 'refute'
   ELSE 'none' END AS effect FROM boi_statement_effects c
), boi_trace_details AS (
 SELECT w.object_id,w.revision,w.witness_id,w.context_digest,w.context_state,
   c.atom,c.fact_key,c.meaning_pointer,c.effect,""" + used(0) + ' AS final_support,' +
        used(1) + """ AS final_refute
 FROM boi_trace_contexts w JOIN boi_trace_effects c ON c.witness_id=w.witness_id
 WHERE c.effect<>'none'
)""")
    return tuple(ctes)
