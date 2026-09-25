"""Registered structural readers for exact OKF definition contracts.

These declarations are readable dependencies, not typed fact populations or
source opinions. Formula still needs its parameter qualification and unit review.
"""
from typing import Literal

from pydantic import Field, JsonValue

from .common_knowledge_contract import CommonKnowledgeMeaning
from .formula_preview import UnitDefinition
from .knowledge_profile import KnowledgeProfileDeclaration, KnowledgeProfileRegistry, ObjectTypeDeclaration
from .knowledge_projection_contract import ProjectionRevision, ProjectionComponent
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import FrozenContract, Ref, RevisionRef
from .source_envelope import byte_digest


TYPED = 'boi/typed-knowledge-meaning@1'
UNIT = 'boi/native-unit-interpretation@1'
COMMON = 'boi/common-meaning@1'
DEFINITION_CAPABILITIES = {UNIT:'unit_definition_structure', COMMON:'common_definition_structure'}
BASE_CAPABILITIES = frozenset({'native_revision_and_required_references', 'okf_content_contract',
    'body_and_source_addresses', 'profile_bindings_and_levels'})


class PublishedUnitMeaning(FrozenContract):
    contract_version: Literal['boi/native-unit-interpretation@1']
    unit_definition: dict[str, JsonValue]
    reference_unit: Ref
    limitations: tuple[Ref, ...] = Field(default=(), max_length=256)


def definition_capability(content):
    contract = content.meaning.get('contract_version') if content is not None else None
    return 'typed_profile_projection' if contract == TYPED else DEFINITION_CAPABILITIES.get(contract)


def required_definition_capabilities(content, *, qualified_use=False):
    capability = definition_capability(content)
    if qualified_use and capability != 'typed_profile_projection':
        raise ValueError('KNOWLEDGE_DEFINITION_QUALIFIED_USE_ADAPTER_REQUIRED')
    # Unknown meanings retain their ordinary reader but cannot acquire this
    # publication admission by naming a client-selected successful capability.
    return BASE_CAPABILITIES | {capability or 'registered_definition_adapter'}


def _covers(binding, pointer):
    return binding.meaning_pointer == '' or pointer == binding.meaning_pointer or pointer.startswith(binding.meaning_pointer+'/')


def check_readable_definition(content, *, record, asset, read_revision, ledger, objects):
    """Check typed declarations, complete addresses and exact nested references.

    No word matching supplies a unit, dimension, conversion or scientific fact.
    The Profile explicitly names this meaning schema, on an exact dependency.
    """
    contract = content.meaning.get('contract_version')
    if contract not in DEFINITION_CAPABILITIES:
        raise ValueError('KNOWLEDGE_DEFINITION_ADAPTER_UNAVAILABLE')
    if content.use_contracts:
        raise ValueError('KNOWLEDGE_DEFINITION_READ_ONLY_USE_CONTRACT_REQUIRED')
    bindings = [b for b in content.profiles if b.schema_ref == contract]
    if len(bindings) != 1:
        raise ValueError('KNOWLEDGE_DEFINITION_PROFILE_SCHEMA_REQUIRED')
    binding = bindings[0]
    required = {d.revision for d in asset.dependencies if d.required}
    if binding.revision not in required:
        raise ValueError('KNOWLEDGE_DEFINITION_PROFILE_DEPENDENCY_REQUIRED')
    _, profile_asset = read_revision(binding.revision)
    if profile_asset.kind != 'profile':
        raise ValueError('KNOWLEDGE_DEFINITION_PROFILE_KIND_REQUIRED')
    profile = KnowledgeProfileDeclaration.model_validate_json(profile_asset.content_json)
    if (profile.profile_id, profile.schema_ref) != (binding.profile_id, contract):
        raise ValueError('KNOWLEDGE_DEFINITION_PROFILE_BINDING_CHANGED')
    types = [i for i,c in enumerate(profile.components) if isinstance(c,ObjectTypeDeclaration)]
    if len(types) != 1:
        raise ValueError('KNOWLEDGE_DEFINITION_DOCUMENT_TYPE_REQUIRED')
    revision = ProjectionRevision.model_validate(binding.revision.model_dump(mode='json'))
    registry = KnowledgeProfileRegistry({revision:profile})
    registry.validate_metadata(ProjectionComponent(revision=revision,pointer=f'/components/{types[0]}'),
        content.document.frontmatter)

    def addresses(pointer):
        if not any(_covers(b,pointer) for b in content.body_bindings):
            raise ValueError('KNOWLEDGE_DEFINITION_BODY_ADDRESS_REQUIRED')
        if not any(_covers(b,pointer) for b in content.evidence_bindings):
            raise ValueError('KNOWLEDGE_DEFINITION_EVIDENCE_ADDRESS_REQUIRED')

    if contract == UNIT:
        value = PublishedUnitMeaning.model_validate(content.meaning)
        if 'revision' in value.unit_definition:
            raise ValueError('KNOWLEDGE_DEFINITION_UNIT_SELF_REVISION_FORBIDDEN')
        unit = UnitDefinition.model_validate({**value.unit_definition,'revision':asset.revision})
        # A declaration of the reference itself must be exactly its identity.
        # Distinct units may use affine conversion; no named-unit special cases.
        if unit.unit_id == value.reference_unit and (unit.scale != unit.scale_denominator or unit.offset != 0):
            raise ValueError('KNOWLEDGE_DEFINITION_REFERENCE_IDENTITY_CONFLICT')
        for field in value.unit_definition:
            addresses('/unit_definition/'+field)
        addresses('/reference_unit')
        for i in range(len(value.limitations)):
            addresses(f'/limitations/{i}')
        return

    meaning = CommonKnowledgeMeaning.model_validate(content.meaning)
    for i in range(len(meaning.limitations)):
        addresses(f'/limitations/{i}')
    source_ids = {s['artifact_ref'] for s in record.payload['sources']}
    span_refs = {RevisionRef.model_validate(s) for s in record.payload['evidence_spans']}

    def evidence(item, node_pointer):
        span = ledger.read(item.span.ref)
        payload = span.payload
        if (item.span not in span_refs or span.kind != RecordKind.EVIDENCE_SPAN
                or record_digest(span.record_id) != item.span.revision_digest
                or payload.get('artifact_ref') not in source_ids):
            raise ValueError('KNOWLEDGE_DEFINITION_EVIDENCE_SCOPE_MISMATCH')
        outer = [b for b in content.evidence_bindings if _covers(b,node_pointer) and b.span == item.span]
        if not outer:
            raise ValueError('KNOWLEDGE_DEFINITION_NESTED_EVIDENCE_NOT_BOUND')
        actual = {'source_revision_digest':payload.get('source_revision_digest'),
            'field_locator':payload.get('field_locator'),'span_ref':item.span.ref}
        if any(getattr(item,k) is not None and getattr(item,k) != v for k,v in actual.items()):
            raise ValueError('KNOWLEDGE_DEFINITION_EVIDENCE_BINDING_CHANGED')
        if any(b.source_revision_digest != actual['source_revision_digest'] or b.field_locator != actual['field_locator'] for b in outer):
            raise ValueError('KNOWLEDGE_DEFINITION_EVIDENCE_BINDING_CHANGED')
        raw = objects.get(payload['field_object_ref'])
        if byte_digest(raw) != payload['content_digest'] or item.quote not in raw.decode('utf-8'):
            raise ValueError('KNOWLEDGE_DEFINITION_QUOTATION_MISMATCH')

    for group in ('concepts','assertions','relations','uninterpreted'):
        for i,node in enumerate(getattr(meaning,group)):
            pointer=f'/{group}/{i}'
            addresses(pointer)
            for item in node.evidence:evidence(item,pointer)
            for qualifier in ('conditions','exceptions','applicability'):
                for j,qualified in enumerate(getattr(node,qualifier,())):
                    target=pointer+f'/{qualifier}/{j}'
                    addresses(target)
                    for item in qualified.evidence:evidence(item,target)
            reused=getattr(node,'reused_definition',None)
            if reused is not None:
                if reused not in required:
                    raise ValueError('KNOWLEDGE_DEFINITION_REUSED_DEPENDENCY_REQUIRED')
                _,target=read_revision(reused)
                if target.kind != 'definition':
                    raise ValueError('KNOWLEDGE_DEFINITION_REUSED_KIND_REQUIRED')
