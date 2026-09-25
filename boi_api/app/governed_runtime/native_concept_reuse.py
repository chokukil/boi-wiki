"""Current native definition reviews feed the existing exact query engine.

A reviewed interpretation narrows source comparisons. It never qualifies those
source facts, upgrades a Private definition to ACTIVE, or equates dictionary terms.
"""
from .semantic_binding_contract import RevisionRef
from .knowledge_content import KnowledgeContent, meaning_pointer
from .common_knowledge_contract import CommonKnowledgeMeaning
from .typed_knowledge_meaning import TypedKnowledgeAssertion
from .native_definition_context import read_native_definition_authority
from .native_observation import _json
from .knowledge_concept_reuse_contract import ConceptReuseContext, ScopedConceptReuseDeclaration
from .knowledge_concept_reuse import compile_scoped_reuse
from .knowledge_query import KnowledgeEvidenceQuery


def _content(asset):
    return KnowledgeContent.model_validate(_json(asset.content_json))


def require_current_reuse_revision(work, authorization, revision):
    # A current reading permits historical transitive dependencies, and review
    # opinions themselves can have newer heads. Reuse requires these exact heads.
    from .knowledge_profile_projector import native_identity
    revision = RevisionRef.model_validate(revision.model_dump(mode="json"))
    record, asset = work.assets._read_record(authorization, revision)
    stable = native_identity(record)
    head = work.assets.store.get('domain_asset_heads', stable)
    if not head or head.get('revision') != revision.model_dump(mode='json'):
        raise ValueError('KNOWLEDGE_REUSE_REVISION_NOT_CURRENT')
    # Published membership has a separate current policy/content head. Native
    # review packs without space publication retain their ordinary source ACL.
    spaces = getattr(work, 'knowledge_spaces', None)
    if spaces is not None and spaces.store.get('knowledge_space_heads', stable):
        access, _ = spaces.authorize(actor_id=authorization.principal,stable_id=stable,purpose='model_input')
        if access.content_revision.model_dump(mode='json') != revision.model_dump(mode='json'):
            raise ValueError('KNOWLEDGE_REUSE_PUBLISHED_REVISION_NOT_CURRENT')
    if work.assets.store.get('domain_asset_heads', stable) != head:
        raise ValueError('KNOWLEDGE_REUSE_REVISION_CHANGED_DURING_READ')
    return asset


def reviewed_literals(work, authorization, selection):
    require_current_reuse_revision(work,authorization,selection.review_revision)
    authority, context = read_native_definition_authority(
        work, authorization, selection.review_revision.model_dump(mode="json"), require_current=True)
    ref = RevisionRef.model_validate(selection.definition_revision.model_dump(mode='json'))
    if ref not in authority.definition_revisions:
        raise ValueError('KNOWLEDGE_REUSE_DEFINITION_NOT_REVIEWED')
    assets = {a.revision.ref:a for a in context.assets}
    def exact(revision):
        asset = assets.get(revision.ref)
        if asset is None or asset.revision.revision_digest != revision.revision_digest:
            raise ValueError('KNOWLEDGE_REUSE_READING_CLOSURE_MISSING')
        current = require_current_reuse_revision(work,authorization,revision)
        if current.content_json != asset.content_json:
            raise ValueError('KNOWLEDGE_REUSE_CONTENT_CHANGED_DURING_READ')
        return asset
    definition = _content(exact(selection.definition_revision))
    meaning = CommonKnowledgeMeaning.model_validate(definition.meaning)
    declaration = ScopedConceptReuseDeclaration.model_validate(
        definition.extensions.get('scoped_concept_reuse'))
    target = CommonKnowledgeMeaning.model_validate(_content(exact(selection.target_definition)).meaning)
    if len(target.concepts)!=1 or target.concepts[0].reused_definition is not None:
        raise ValueError('KNOWLEDGE_REUSE_TARGET_CONCEPT_AMBIGUOUS')
    selected = []
    raw_meaning = meaning.model_dump(mode='json')
    for link in declaration.links:
        concept = meaning_pointer(raw_meaning,link.concept_pointer)
        if concept.get('reused_definition') != selection.target_definition.model_dump(mode='json'):
            continue
        assertion = meaning_pointer(raw_meaning,link.assertion_pointer)
        if (concept['label'] != link.literal or assertion['subject'] != concept['id']
                or assertion['polarity']!='positive' or assertion['modality']!='asserted'
                or assertion['uncertainties'] or assertion['conditions'] or assertion['exceptions']
                or assertion['applicability']):
            raise ValueError('KNOWLEDGE_REUSE_INTERPRETATION_SCOPE_UNSUPPORTED')
        if not any(b.meaning_pointer==link.assertion_pointer and b.assertion_kind=='interpretation'
                   for b in definition.body_bindings):
            raise ValueError('KNOWLEDGE_REUSE_INTERPRETATION_BINDING_REQUIRED')
        source = _content(exact(link.source.revision))
        source_assertion = TypedKnowledgeAssertion.model_validate(
            meaning_pointer(source.meaning,link.source.pointer))
        if (source_assertion.assertion_kind!='source_reported'
                or source_assertion.predicate!=link.predicate
                or source_assertion.value.kind!='text'
                or source_assertion.value.value!=link.literal):
            raise ValueError('KNOWLEDGE_REUSE_EXACT_SOURCE_MISMATCH')
        # Exact original evidence must support this scoped interpretation, not
        # just another paragraph in the same document or an alias label.
        source_spans = {b.span.ref for b in source.evidence_bindings
                        if b.meaning_pointer==link.source.pointer}
        relation_spans = {b.span.ref for b in definition.evidence_bindings
                          if b.meaning_pointer==link.assertion_pointer}
        assertion_spans = {e['span']['ref'] for e in assertion['evidence']}
        if not source_spans or not relation_spans or not assertion_spans or not (
                relation_spans <= source_spans and assertion_spans <= relation_spans):
            raise ValueError('KNOWLEDGE_REUSE_SOURCE_EVIDENCE_MISMATCH')
        selected.append({'predicate':link.predicate.model_dump(mode='json'),
            'value':source_assertion.value.model_dump(mode='json'),
            'source':{'revision':link.source.revision.model_dump(mode='json'),
                      'meaning_pointer':link.source.pointer}})
    if not selected:
        raise ValueError('KNOWLEDGE_REUSE_TARGET_NOT_DECLARED')
    require_current_reuse_revision(work,authorization,selection.review_revision)
    return selected


def prepare_concept_query(work, authorization, context):
    context = ConceptReuseContext.model_validate(context)
    original = KnowledgeEvidenceQuery.model_validate(context.source_query)
    if original.reuse_context is not None:
        raise ValueError('KNOWLEDGE_REUSE_NESTED_CONTEXT_DENIED')
    selected = {s.filter_index:reviewed_literals(work,authorization,s) for s in context.selections}
    compiled = compile_scoped_reuse(original,selected)
    return compiled.model_copy(update={'reuse_context':context})


def validate_concept_query(work, authorization, query):
    query = KnowledgeEvidenceQuery.model_validate(query)
    if query.reuse_context is None:
        return
    expected = prepare_concept_query(work,authorization,query.reuse_context)
    if expected != query:
        raise ValueError('KNOWLEDGE_REUSE_COMPILED_QUERY_MISMATCH')
