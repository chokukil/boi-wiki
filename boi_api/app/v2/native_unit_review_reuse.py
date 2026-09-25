"""Reuse an unchanged unit opinion with an explicitly delivered current context.

No replacement review or inferred semantic match. A namespace change remains
visible to the external agent through the existing complete reading contract.
"""
from ..governed_runtime.domain_asset_store import DomainAssetStore
from ..governed_runtime.semantic_binding_contract import RevisionRef
from ..governed_runtime.source_envelope import ArtifactEnvelope
from ..governed_runtime.native_observation import _json
from ..governed_runtime.knowledge_formula_contract import definition_meaning


def validate_current_unit_reading(work, authorization, original, *, review_revision,
        reading_ref, require_current=True):
    reading_ref = RevisionRef.model_validate(reading_ref)
    assets = getattr(work,'assets',None) or DomainAssetStore(work.intake)
    reviewed = assets.read(authorization=authorization,
        revision=RevisionRef.model_validate(review_revision), lane='provisional')
    sources = tuple(ArtifactEnvelope.model_validate(s) for s in reviewed['sources'])
    context = work.contexts.validate_reading(authorization=authorization,
        revision=reading_ref, sources=sources, require_current=require_current)
    receipt = work.intake.ledger.read(reading_ref.ref).payload
    prepared = work.intake.ledger.read(receipt['context_ref']['ref']).payload
    stored = assets.read(authorization=authorization, revision=original.revision, lane='provisional')
    if (prepared['namespace'] != stored['namespace']
            or prepared.get('definition_reading', 'all') != 'all'):
        raise ValueError('NATIVE_FORMULA_CURRENT_UNIT_SCOPE_REQUIRED')
    # Complete delivery exposes newly added unlinked definitions too. It proves
    # neither semantic comparison nor absence of contrary knowledge elsewhere.
    current = next((a for a in context.assets if a.revision == original.revision), None)
    if current != original:
        raise ValueError('NATIVE_FORMULA_CURRENT_UNIT_NOT_READ')
    unit_id = definition_meaning(_json(original.content_json))['unit_definition']['unit_id']
    for candidate in context.assets:
        value = definition_meaning(_json(candidate.content_json))
        if (candidate.revision != original.revision and isinstance(value, dict)
                and value.get('contract_version') == 'boi/native-unit-interpretation@1'
                and isinstance(value.get('unit_definition'), dict)
                and value['unit_definition'].get('unit_id') == unit_id):
            raise ValueError('NATIVE_FORMULA_CURRENT_UNIT_AMBIGUOUS')
    return {'reading_ref': reading_ref.model_dump(mode='json'),
        'context_digest': context.context_digest, 'scope': 'current_unit_namespace_and_dependencies',
        'new_semantic_review': False, 'semantic_support_verified': False}
