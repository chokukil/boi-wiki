"""Current edit authority for a same-identity content or Profile correction.

Authored differences are audit information, not a semantic verdict. The normal
native checks, scoped qualifications and publication transaction still apply.
"""
from .knowledge_space_contract import NativeKnowledgeIdentity
from .local_bundle_contract import LocalBundleChange
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite


def correction_basis(assets, auth, change, target):
    change = LocalBundleChange.model_validate(change)
    if change.operation != 'revise' or change.correction is None:
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_INTENT_REQUIRED')
    if not callable(assets.space_access):
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_EDIT_AUTHORITY_REQUIRED')
    access, record = assets.space_access(change.previous_revision, 'edit')
    identity = NativeKnowledgeIdentity(identity_creator=record.payload['employee_id'],
        namespace=record.payload['namespace'], logical_id=record.payload['logical_id'])
    if (access.actor_id != auth.principal or access.identity != identity
            or (identity.namespace, identity.logical_id) != (change.namespace, change.logical_id)
            or access.content_revision != change.previous_revision):
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_IDENTITY_MISMATCH')
    # Foreign-editor projection publication still needs the creator/editor
    # adapter. Fail explicitly instead of creating another user's copy.
    if identity.identity_creator != auth.principal:
        raise ValueError('KNOWLEDGE_CONTENT_SHARED_EDITOR_ADAPTER_REQUIRED')
    from .knowledge_space_store import HEADS, KnowledgeSpacePolicy
    head = assets.store.get(HEADS, identity.stable_id)
    expected = change.correction.expected_policy_revision
    if (access.policy_revision != expected or not head
            or head['policy_revision'] != expected.model_dump(mode='json')
            or head['content_revision'] != change.previous_revision.model_dump(mode='json')):
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_BASIS_CHANGED')
    policy_record = assets.ledger.read(expected.ref)
    if semantic_digest(policy_record.payload) != head['policy_payload_digest']:
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_POLICY_CHANGED')
    policy = KnowledgeSpacePolicy.model_validate(policy_record.payload)
    target_wire = target.model_dump(mode='json') if hasattr(target, 'model_dump') else target
    if len(policy.targets) != 1 or policy.targets[0].model_dump(mode='json') != target_wire:
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_PRESERVE_SPACE_REQUIRED')
    if len(policy.visible_history) >= 256:
        raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_HISTORY_CAPACITY')
    from .knowledge_document_feedback import correction_feedback_rows
    correction_feedback_rows(assets, auth, change, policy)
    return policy, record, AtomicWrite(HEADS, identity.stable_id, head, head)


def correction_source_closure(policy, previous_record, record, *, content=None, read_span=None):
    """Preserve definition sources and admit evidence-bound source additions.

    Both records must already have passed their current authorized readers.
    A caller's change kind cannot turn a definition correction into a schema
    revision. Source admission, immutable history and atomic head fences still
    apply to Profile revisions; old dependents keep their exact Profile refs.
    """
    previous, current = previous_record.payload, record.payload
    if previous['kind'] != current['kind']:
        raise ValueError('DOMAIN_ASSET_KIND_CHANGE_REQUIRES_NEW_IDENTITY')
    if current['kind'] == 'profile':
        return current['source_manifest_digest']
    error = 'KNOWLEDGE_CONTENT_CORRECTION_PRESERVE_SOURCE_REQUIRED'
    if previous['source_manifest_digest'] != policy.source_closure_digest:
        raise ValueError(error)
    if current['sources'] == previous['sources']:
        if current['source_manifest_digest'] != policy.source_closure_digest:
            raise ValueError(error)
        return current['source_manifest_digest']
    # Exact envelopes preserve the original artifact, bytes and role together.
    # A source version must add an artifact, never replace a retained envelope.
    sources = current['sources']
    if (any(source not in sources for source in previous['sources'])
            or len({source['artifact_ref'] for source in sources}) != len(sources)):
        raise ValueError(error)
    added = [source for source in sources if source not in previous['sources']]
    if not added or content is None or not callable(read_span):
        raise ValueError(error)
    # Native checks already validate exact spans, quotes and current source
    # rights. This additional gate forbids unused source attachments. It is
    # not a semantic judgment that a new source justifies a changed assertion.
    bound = {read_span(binding.span.ref).payload['artifact_ref']
             for binding in content.evidence_bindings}
    if any(source['artifact_ref'] not in bound for source in added):
        raise ValueError(error)
    return current['source_manifest_digest']
