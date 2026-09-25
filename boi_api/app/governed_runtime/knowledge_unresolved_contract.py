"""Portable unresolved inventory and exact evidence scope; no qualification service."""
from .knowledge_content import ContentUnresolvedClassification
from .semantic_binding_contract import semantic_digest


def overlaps(left, right):
    return (left == right or left == '' or right == ''
        or left.startswith(right + '/') or right.startswith(left + '/'))


def unresolved_review_item(item):
    """Canonical inventory entry, including original source refs and wording.

Original local source references may still be importer tokens. They are not
resolved here; native replacement is separately checked by the importer.
"""
    value = item.model_dump(mode='json') if hasattr(item, 'model_dump') else item
    result = {'meaning_pointer':value.get('meaning_pointer'),
        'source_spans':value.get('source_spans', []),
        'reason_code':value['reason_code'], 'description':value['description']}
    if value.get('classification') is not None:
        result['classification'] = ContentUnresolvedClassification.model_validate(
            value['classification']).model_dump(mode='json')
    return result


def unresolved_inventory_digest(items):
    return semantic_digest([unresolved_review_item(item) for item in items])


def unresolved_evidence_bindings(content, item):
    """Full node context, or explicitly authored exact spans; no word matching."""
    pointer=item.meaning_pointer or ''
    parts=pointer.split('/')
    if len(parts)>=3 and parts[1] in ('assertions','parameters'):
        pointer='/'.join(parts[:3])
    bindings=[binding for binding in content.evidence_bindings
              if overlaps(pointer,binding.meaning_pointer)]
    if item.source_spans:
        required=set(item.source_spans)
        bindings=[binding for binding in bindings if binding.span in required]
        if {binding.span for binding in bindings}!=required:
            raise ValueError('KNOWLEDGE_STATEMENT_UNRESOLVED_SOURCE_CLOSURE_MISSING')
    return bindings
