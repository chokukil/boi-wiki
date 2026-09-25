"""Adapt exact authorized published evidence to the existing answer binder.

The selected whole fields are not the complete original artifact or admitted
meanings. No source text, span, right or parser result is manufactured here.
"""
from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
from ..governed_runtime.knowledge_published_sources import PublishedSourceFields
from ..governed_runtime.semantic_binding_contract import RevisionRef


def closure_binds(pointer, closure):
    # The binder's rule: a binding on a closure node or beneath it.
    return any(pointer == p or pointer.startswith(p + '/') for p in closure)


def read_published_original_fields(work, principal, authorization, owners, source, *, extra_refs=(),
        meaning_closures=None):
    reader = PublishedKnowledgeReader(work.knowledge_spaces,
        current_authorization=work.current_knowledge_authorization)
    selected = {}
    revisions = []
    selections = []
    checked_readers = []
    for owner in owners:
        revision = RevisionRef.model_validate(owner['revision'])
        access, native, content = reader._read(principal.employee_id, revision, 'model_input')
        fields = PublishedSourceFields(reader, actor_id=principal.employee_id,
            revision=revision, access=access, native=native, content=content, model_input=True)
        indices = [i for i, binding in enumerate(content.evidence_bindings)
                   if binding.source_revision_digest == source['digest']]
        closure = (meaning_closures or {}).get(revision)
        if closure is not None:
            # An explicit meaning selection reads only its own closure's
            # bindings. Revisions without an entry keep the whole document.
            indices = [i for i in indices if closure_binds(content.evidence_bindings[i].meaning_pointer, closure)]
            selections.append({'revision': revision.model_dump(mode='json'), 'meaning_pointers': sorted(closure)})
        # Keep the normal bounded published reader's field/character limits.
        bundle = fields.bundle(indices, url='')
        for value in bundle['fields']:
            binding, metadata, text, _ = fields.read(value['bindings'][0]['binding_index'])
            if not any(saved == source for saved, _, _ in fields.sources.values()):
                raise ValueError('PUBLISHED_ORIGINAL_SOURCE_MEMBERSHIP_MISMATCH')
            field = {'span_ref': binding.span.ref, **{k: metadata[k] for k in (
                'field_locator', 'record_locator', 'field_state', 'value_kind',
                'presence_basis', 'content_digest', 'character_count')}, 'text': text}
            if 'structural_metadata' in metadata:
                field['structural_metadata'] = metadata['structural_metadata']
            previous = selected.setdefault(binding.span.ref, field)
            if previous != field:
                raise ValueError('PUBLISHED_ORIGINAL_FIELD_CONFLICT')
        checked_readers.append(fields)
        revisions.append(revision.model_dump(mode='json'))
    if not selected or not set(extra_refs).issubset(selected):
        raise ValueError('PUBLISHED_ORIGINAL_FIELD_OUTSIDE_BINDING_SCOPE')
    values = sorted(selected.values(), key=lambda f: (f['field_locator'], f['span_ref']))
    if len(values) > 32 or sum(len(f['text']) for f in values) > 65536:
        raise ValueError('KNOWLEDGE_SOURCE_BUNDLE_LIMIT_REQUIRES_NARROWER_SELECTION')
    if len({f['field_locator'] for f in values}) != len(values):
        raise ValueError('PUBLISHED_ORIGINAL_FIELD_LOCATOR_AMBIGUOUS')
    manifest = {'contract_version': 'boi/published-original-selection@1',
        'source_revision_digest': source['digest'], 'employee_id': authorization.principal,
        'policy_digest': authorization.policy_digest,
        'projection_scope': 'selected_published_evidence_fields',
        'definition_revisions': revisions, 'field_count': len(values),
        'fields': [{k: v for k, v in f.items() if k != 'text'} for f in values],
        'complete_original_artifact': False, 'meaning_reuse': False}
    # A narrowed reading is a different reading identity than the whole document.
    if selections:
        manifest['meaning_selections'] = selections
    for fields in checked_readers:
        fields.fence()
    return {'source': source, 'manifest': manifest, 'fields': values}
