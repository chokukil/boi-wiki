"""Compile previously reviewed concept reuse into exact source-scoped comparisons.

No label normalization, dictionary matching, new authority or source-fact rewrite.
The enclosing reader must validate current reviewed definitions and source links.
"""
from pydantic import Field
from .knowledge_projection_contract import ProjectionContract, ProjectionComponent, ProjectionScalar
from .knowledge_query import KnowledgeEvidenceQuery, KnowledgeSourceScope
from .filter_expression import FilterExpression
from .semantic_binding_contract import semantic_digest


class ScopedReuseLiteral(ProjectionContract):
    predicate: ProjectionComponent
    value: ProjectionScalar
    source: KnowledgeSourceScope


def compile_scoped_reuse(query, selected):
    query = KnowledgeEvidenceQuery.model_validate(query)
    if not selected:
        return query
    if not set(selected) <= set(range(len(query.predicates))):
        raise ValueError('KNOWLEDGE_REUSE_FILTER_SELECTION_INVALID')
    predicates = []
    replacements = {}
    for index, test in enumerate(query.predicates):
        if index not in selected:
            replacements[index] = FilterExpression(operator='filter',filter_index=len(predicates))
            predicates.append(test)
            continue
        if test.operator != 'eq' or test.value.kind != 'text':
            raise ValueError('KNOWLEDGE_REUSE_EXACT_TEXT_COMPARISON_REQUIRED')
        raw = selected[index]
        if not 1 <= len(raw) <= 128:
            raise ValueError('KNOWLEDGE_REUSE_BOUNDED_SCOPE_REQUIRED')
        links = [ScopedReuseLiteral.model_validate(link) for link in raw]
        addresses = {}
        for link in links:
            key = (link.source.revision.ref,link.source.meaning_pointer)
            if key in addresses and addresses[key] != (link.predicate,link.value):
                raise ValueError('KNOWLEDGE_REUSE_SOURCE_ADDRESS_CONFLICT')
            addresses[key] = (link.predicate,link.value)
        if not any(link.value == test.value for link in links):
            raise ValueError('KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED')
        links = [link for link in links if link.predicate == test.predicate and (
            not test.source_scope or link.source in test.source_scope)]
        if not links:
            raise ValueError('KNOWLEDGE_REUSE_ROLE_OR_SOURCE_SCOPE_EMPTY')
        # Stable exact ordering makes spelling-only requests compile identically.
        links = sorted({semantic_digest(link):link for link in links}.values(),
                       key=lambda link:(link.source.revision.ref,link.source.meaning_pointer))
        leaves = []
        for link in links:
            leaves.append(FilterExpression(operator='filter',filter_index=len(predicates)))
            predicates.append(test.model_copy(update={'value':link.value,'source_scope':(link.source,)}))
        replacements[index] = leaves[0] if len(leaves)==1 else FilterExpression(operator='or',arguments=tuple(leaves))
    def rewrite(node):
        if node.operator == 'filter':
            return replacements[node.filter_index]
        return node.model_copy(update={'arguments':tuple(rewrite(child) for child in node.arguments)})
    # Revalidate size, exact expression coverage and existing query semantics.
    return KnowledgeEvidenceQuery.model_validate({
        **query.model_dump(mode='json'),
        'predicates':[item.model_dump(mode='json') for item in predicates],
        'expression':rewrite(query.expression).model_dump(mode='json')})
