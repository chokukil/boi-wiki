"""Minimal evidence-bound OKF/BoI domain extension, without inferred hierarchy."""
from typing import Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import FrozenContract, Ref, RevisionRef, Digest


class MeaningEvidence(FrozenContract):
    span: RevisionRef
    quote: str = Field(min_length=1, max_length=32000)
    # Filled from the verified span by the server for existing native readers.
    source_revision_digest: Digest | None = None
    field_locator: str | None = None
    span_ref: Ref | None = None


class QualifiedMeaning(FrozenContract):
    statement: Ref
    evidence: tuple[MeaningEvidence, ...] = Field(min_length=1)


class MeaningConcept(FrozenContract):
    id: Ref
    label: Ref
    kind: Literal['concept','equipment','component','process','quantity','unit','role','calculation','collection']
    definition: str | None = None
    # Explicit domain interpretation of the quantity's dimension. Optional:
    # missing information is not inferred from labels, units or other concepts.
    quantity_dimension: Ref | None = Field(default=None, exclude_if=lambda v: v is None)
    reused_definition: RevisionRef | None = None
    evidence: tuple[MeaningEvidence, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def quantity_fields(self):
        if self.quantity_dimension is not None and self.kind != 'quantity':
            raise ValueError('COMMON_MEANING_QUANTITY_KIND_REQUIRED')
        return self


class MeaningAssertion(FrozenContract):
    id: Ref
    subject: Ref
    statement: Ref
    polarity: Literal['positive','negative'] = 'positive'
    modality: Literal['asserted','possible','intended','required']
    conditions: tuple[QualifiedMeaning, ...] = ()
    exceptions: tuple[QualifiedMeaning, ...] = ()
    applicability: tuple[QualifiedMeaning, ...] = ()
    evidence: tuple[MeaningEvidence, ...] = Field(min_length=1)
    uncertainties: tuple[Ref, ...] = ()


class MeaningRelation(FrozenContract):
    id: Ref
    source: Ref
    target: Ref
    type: Literal['broader','narrower','part_of','precedes','causes','requires','supports',
                  'contradicts','depends_on','related_to','in_collection']
    conditions: tuple[QualifiedMeaning, ...] = ()
    exceptions: tuple[QualifiedMeaning, ...] = ()
    applicability: tuple[QualifiedMeaning, ...] = ()
    modality: Literal['asserted','possible','intended','required']
    uncertainties: tuple[Ref, ...] = ()
    evidence: tuple[MeaningEvidence, ...] = Field(min_length=1)


class CommonKnowledgeMeaning(FrozenContract):
    contract_version: Literal['boi/common-meaning@1'] = 'boi/common-meaning@1'
    profile: Literal['OKF-0.2+boi-profile'] = 'OKF-0.2+boi-profile'
    # Explanatory context only: never authorization, truth, or directory depth.
    context_layer: Literal['L0','L1','L2','L3','L4'] | None = None
    concepts: tuple[MeaningConcept, ...] = Field(min_length=1, max_length=200)
    assertions: tuple[MeaningAssertion, ...] = Field(default=(), max_length=500)
    relations: tuple[MeaningRelation, ...] = Field(default=(), max_length=500)
    uninterpreted: tuple[QualifiedMeaning, ...] = ()
    limitations: tuple[Ref, ...] = ()

    @model_validator(mode='after')
    def identifiers_and_relation_types(self):
        nodes = [*self.concepts, *self.assertions, *self.relations]
        ids = {n.id for n in nodes}
        if len(ids) != len(nodes):
            raise ValueError('COMMON_MEANING_ID_DUPLICATE')
        concepts = {n.id for n in self.concepts}
        targets = concepts | {n.id for n in self.assertions}
        if any(a.subject not in concepts for a in self.assertions):
            raise ValueError('COMMON_MEANING_SUBJECT_MISSING')
        if any(r.source not in targets or r.target not in targets for r in self.relations):
            raise ValueError('COMMON_MEANING_RELATION_TARGET_MISSING')
        collections = {n.id for n in self.concepts if n.kind == 'collection'}
        if any(r.type == 'in_collection' and r.target not in collections for r in self.relations):
            raise ValueError('COMMON_MEANING_COLLECTION_REQUIRED')
        return self


def validate_common_evidence(content, *, assets, authorization, sources):
    """Check exact quotation binding, without judging source fidelity or truth."""
    value = CommonKnowledgeMeaning.model_validate(content)
    source_ids = {s.artifact_ref for s in sources}
    from .ledger import RecordKind, record_digest
    from .source_envelope import byte_digest
    def walk(item):
        if isinstance(item, dict):
            if {'span', 'quote'} <= set(item):
                ref = RevisionRef.model_validate(item['span'])
                span = assets.ledger.read(ref.ref)
                if (span.kind != RecordKind.EVIDENCE_SPAN or record_digest(span.record_id) != ref.revision_digest
                    or span.payload.get('artifact_ref') not in source_ids
                    or span.payload.get('employee_id') != authorization.principal
                    or span.payload.get('policy_digest') != authorization.policy_digest):
                    raise ValueError('COMMON_MEANING_EVIDENCE_ACCESS_DENIED')
                raw = assets.objects.get(span.payload['field_object_ref'])
                if byte_digest(raw) != span.payload['content_digest'] or item['quote'] not in raw.decode('utf-8'):
                    raise ValueError('COMMON_MEANING_QUOTATION_MISMATCH')
                actual = {'source_revision_digest': span.payload['source_revision_digest'],
                          'field_locator': span.payload['field_locator'], 'span_ref': ref.ref}
                if any(item.get(k) is not None and item[k] != v for k, v in actual.items()):
                    raise ValueError('COMMON_MEANING_SPAN_BINDING_MISMATCH')
                item.update(actual)
            else:
                for child in item.values():
                    walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
    material = value.model_dump(mode='json')
    walk(material)
    for concept in value.concepts:
        if concept.reused_definition:
            assets._read_record(authorization, concept.reused_definition)
    return CommonKnowledgeMeaning.model_validate(material)


def quantity_concept_reference(reference):
    """Parse an exact native common-concept address, never a semantic match."""
    from .ledger import record_digest
    try:
        ref, pointer = reference.split('#', 1)
        parts = pointer.split('/')
        if (not ref.startswith('KnowledgeRevision:sha256:') or len(parts) != 3
                or parts[:2] != ['', 'concepts'] or not parts[2].isascii()
                or not parts[2].isdigit() or str(int(parts[2])) != parts[2]):
            raise ValueError()
        revision = RevisionRef(ref=ref, revision_digest=record_digest(ref))
        return revision, int(parts[2])
    except (AttributeError, TypeError, ValueError):
        raise ValueError('COMMON_QUANTITY_REFERENCE_INVALID') from None


def resolve_quantity_concept(content, revision, reference):
    """Consume a previously authorized exact asset; confer no review authority."""
    requested, index = quantity_concept_reference(reference)
    if RevisionRef.model_validate(revision) != requested:
        raise ValueError('COMMON_QUANTITY_REVISION_MISMATCH')
    value = CommonKnowledgeMeaning.model_validate(content)
    if index >= len(value.concepts) or value.concepts[index].kind != 'quantity':
        raise ValueError('COMMON_QUANTITY_CONCEPT_REQUIRED')
    concept = value.concepts[index]
    # An unresolved alias is not a replacement definition. Follow its explicit
    # authoritative concept instead of inventing a dimension here.
    if concept.reused_definition is not None:
        raise ValueError('COMMON_QUANTITY_ALIAS_REQUIRES_DEFINITION')
    return {'quantity_ref': reference, 'definition_revision': requested.model_dump(mode='json'),
            'concept': concept.model_dump(mode='json'), 'profile': value.profile,
            'conditions': [a.model_dump(mode='json') for a in value.assertions if a.subject == concept.id],
            'relations': [r.model_dump(mode='json') for r in value.relations if concept.id in (r.source, r.target)],
            'limitations': list(value.limitations), 'semantic_support_verified': False,
            'scientific_truth_proven': False}
