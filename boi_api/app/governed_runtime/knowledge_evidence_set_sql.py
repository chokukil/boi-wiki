"""Four-state composition in SQL, after server-owned atomic qualification.

The enclosing compiler supplies three relations: boi_u(id),
boi_atom_support(atom,id), boi_atom_refute(atom,id). U must already be the
currently authorized population; atom relations must have the same pinned
scope/time/purpose and qualified semantics. This module grants no authority and
does not turn arbitrary property rows into qualified evidence.

Only AST-generated identifiers enter SQL. No document, vector, whole population
ID list or per-object Python evaluation is required to compute the summary.
"""
from dataclasses import dataclass

from .filter_expression import FilterExpression, validate_filter_expression


STATES = ('supported', 'refuted', 'conflicted', 'unknown')


@dataclass(frozen=True)
class EvidenceSetSql:
    ctes: tuple[str, ...]
    atom_relations: tuple[tuple[str, str], ...]

    @property
    def summary_sql(self):
        # Do not enumerate members or construct traces for an exact count.
        return 'WITH ' + ',\n'.join(self.ctes) + '\n' + ' UNION ALL '.join(
            f"SELECT '{state}' AS state, COUNT(*) AS count FROM boi_{state}"
            for state in STATES)

    def page_sql(self, *, state='all', after_key=None, limit=50, dialect):
        if state not in (*STATES, 'all'):
            raise ValueError('KNOWLEDGE_SET_STATE_INVALID')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('KNOWLEDGE_SET_PAGE_LIMIT')
        if after_key is not None and (not isinstance(after_key, str) or not 1 <= len(after_key) <= 2048):
            raise ValueError('KNOWLEDGE_SET_CURSOR_KEY_INVALID')
        if dialect not in ('sqlite', 'postgres'):
            raise ValueError('KNOWLEDGE_SET_SQL_DIALECT_INVALID')
        placeholder, collation = ('?', 'BINARY') if dialect == 'sqlite' else ('%s', '"C"')
        selected = STATES if state == 'all' else (state,)
        result = ' UNION ALL '.join(f"SELECT id, '{name}' AS state FROM boi_{name}" for name in selected)
        sql = 'WITH ' + ',\n'.join((*self.ctes, f'boi_page_members AS ({result})'))
        sql += '\nSELECT id,state FROM boi_page_members'
        parameters = []
        if after_key is not None:
            sql += f' WHERE id COLLATE {collation} > {placeholder}'
            parameters.append(after_key)
        sql += f' ORDER BY id COLLATE {collation} LIMIT {placeholder}'
        parameters.append(limit + 1)
        # The enclosing protected result service trims the extra row and binds
        # its cursor to the snapshot, query, current policy and qualification.
        return sql, tuple(parameters)


def compile_evidence_set_sql(expression, atom_count):
    if type(atom_count) is not int or not 1 <= atom_count <= 128:
        raise ValueError('KNOWLEDGE_SET_ATOM_LIMIT')
    expression = FilterExpression.model_validate(expression)
    validate_filter_expression(expression, atom_count)
    ctes = ['boi_population AS (SELECT DISTINCT id FROM boi_u)']
    atoms = []
    for index in range(atom_count):
        pair = (f'boi_a{index}_t', f'boi_a{index}_f')
        atoms.append(pair)
        for name, source in zip(pair, ('boi_atom_support', 'boi_atom_refute')):
            # Restrict every atom before NOT/set composition. A hidden object
            # in an upstream candidate relation cannot enter this population.
            ctes.append(f'{name} AS (SELECT id FROM {source} WHERE atom={index} '
                        'INTERSECT SELECT id FROM boi_population)')
    node_count = 0
    def visit(node):
        nonlocal node_count
        if node.operator == 'filter':
            return atoms[node.filter_index]
        children = [visit(child) for child in node.arguments]
        if node.operator == 'not':
            return children[0][::-1]
        pair = (f'boi_n{node_count}_t', f'boi_n{node_count}_f')
        node_count += 1
        operations = ('INTERSECT', 'UNION') if node.operator == 'and' else ('UNION', 'INTERSECT')
        for side, (name, operation) in enumerate(zip(pair, operations)):
            body = f' {operation} '.join(f'SELECT id FROM {child[side]}' for child in children)
            ctes.append(f'{name} AS ({body})')
        return pair
    support, refute = visit(expression)
    ctes.extend((
        f'boi_supported AS (SELECT id FROM {support} EXCEPT SELECT id FROM {refute})',
        f'boi_refuted AS (SELECT id FROM {refute} EXCEPT SELECT id FROM {support})',
        f'boi_conflicted AS (SELECT id FROM {support} INTERSECT SELECT id FROM {refute})',
        f'boi_known AS (SELECT id FROM {support} UNION SELECT id FROM {refute})',
        'boi_unknown AS (SELECT id FROM boi_population EXCEPT SELECT id FROM boi_known)',
    ))
    # Every original atom relation remains available for selected-object detail,
    # including conflicts masked by the final expression's state.
    return EvidenceSetSql(tuple(ctes), tuple(atoms))
