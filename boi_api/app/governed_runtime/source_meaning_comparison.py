"""Separate proposed source reading from proposed concept relationships.

Forward component contract. Not activated in the migration pipeline. Exact quote
binding proves provenance only, never the meaning or completeness of a reading.
"""
from typing import Literal
from pydantic import Field, StrictInt, model_validator
from .semantic_binding_contract import FrozenContract, Ref, RevisionRef, semantic_digest
from .source_envelope import byte_digest


class QuotedReading(FrozenContract):
    field_index: StrictInt = Field(ge=0)
    quote: Ref = Field(description='Exact substring occurring once in the entire selected source field. '
        'If a phrase occurs more than once, include its subject and surrounding clause until unique. '
        'This applies to every facet, including exclusions; do not omit a claim to avoid a repeated quote.')
    interpretation: Ref


class SourceAtomReading(FrozenContract):
    meaning: QuotedReading
    role: Literal['concept','entity','event','observation','measurement','setpoint',
                  'upper_limit','lower_limit','computed','rule','relationship','unknown'] = Field(
        description='Role of the source-described subject: a term or value type as such is concept; '
        'an object as such is entity. An observed measurement is measurement, even in a definition; '
        'the word value alone does not establish measurement. '
        'Keep setting, limit and calculated roles distinct. Use unknown when the source cannot establish a role.')
    unit_status: Literal['known','unknown','dimensionless','not_applicable']
    conditions: tuple[QuotedReading, ...] = Field(max_length=16)
    exclusions: tuple[QuotedReading, ...] = Field(max_length=16)
    missing_information: tuple[QuotedReading, ...] = Field(max_length=16)


class SourceReading(FrozenContract):
    contract_version: Literal['boi/source-meaning-reading@1'] = 'boi/source-meaning-reading@1'
    atoms: tuple[SourceAtomReading, ...] = Field(max_length=4)
    uncertainties: tuple[str, ...] = Field(max_length=16)
    remaining_claims: bool


class TypedSourceAtomReading(SourceAtomReading):
    contract_kind: Literal['Term','ValueType','ObjectType','PropertyDefinition','RelationType','Metric','Rule','unknown']
    kind_basis: QuotedReading


class TypedSourceReading(SourceReading):
    contract_version: Literal['boi/source-meaning-reading@2'] = 'boi/source-meaning-reading@2'
    atoms: tuple[TypedSourceAtomReading, ...] = Field(max_length=4)


class SegmentQuotedReading(QuotedReading):
    segment_index: StrictInt = Field(ge=0,description='Exact server-provided source segment index.')
    end_segment_index: StrictInt | None = Field(default=None,ge=0,
        description='Optional last segment for a contiguous range in the same field. Omit for one segment.')
    quote: Ref = Field(description='Complete selected source segment, copied by BoI; never model-authored.')


class SegmentSourceAtomReading(TypedSourceAtomReading):
    meaning: SegmentQuotedReading
    kind_basis: SegmentQuotedReading
    conditions: tuple[SegmentQuotedReading, ...] = Field(max_length=16,
        description='Applicability prerequisites such as only when/if/during. Do not repeat the definition, '
        'identity, grain or value type here merely because it is a constraint on the described structure.')
    exclusions: tuple[SegmentQuotedReading, ...] = Field(max_length=16)
    missing_information: tuple[SegmentQuotedReading, ...] = Field(max_length=16)
    time_status: Literal['not_applicable','unknown','declared'] = Field(
        description='not_applicable when source establishes no time semantics; declared for a described '
        'temporal meaning; unknown when source does not establish either. A string alone does not exclude time.')
    time_basis: SegmentQuotedReading | None = Field(
        description='Source evidence for time_status; required for not_applicable or declared. '
        'For declared, interpretation states the source temporal meaning without invented precision.')

    @model_validator(mode='after')
    def time_evidence_required(self):
        if self.time_status!='unknown' and self.time_basis is None:
            raise ValueError('SOURCE_READING_TIME_BASIS_REQUIRED')
        return self


class SegmentSourceReading(TypedSourceReading):
    contract_version: Literal['boi/source-meaning-reading@3'] = 'boi/source-meaning-reading@3'
    atoms: tuple[SegmentSourceAtomReading, ...] = Field(max_length=4)


def append_source_reading(previous, addition):
    """Append proposals, never revise previously frozen atoms or drop uncertainty."""
    value=addition.model_dump(mode='json')
    if previous is None:return addition
    if previous['contract_version']!=value['contract_version']:
        raise ValueError('SOURCE_READING_CONTINUATION_VERSION_MISMATCH')
    old=previous['atoms'];new=value['atoms']
    if any(atom in old for atom in new):
        raise ValueError('SOURCE_READING_CONTINUATION_DUPLICATE_ATOM')
    if not new and value['remaining_claims']:
        raise ValueError('SOURCE_READING_CONTINUATION_NO_PROGRESS')
    value['atoms']=[*old,*new]
    value['uncertainties']=list(dict.fromkeys([*previous['uncertainties'],*value['uncertainties']]))
    return type(addition).model_validate(value)


class ConceptRelationshipProposal(FrozenContract):
    atom_index: StrictInt = Field(ge=0)
    target: RevisionRef
    relationship: Literal['equivalent','identifier_for','related','broader','narrower','not_equivalent','unknown']
    explanation: Ref


class MeaningComparison(FrozenContract):
    contract_version: Literal['boi/source-meaning-comparison@1'] = 'boi/source-meaning-comparison@1'
    relationships: tuple[ConceptRelationshipProposal, ...] = Field(max_length=16)
    uncertainties: tuple[str, ...] = Field(max_length=16)


def bind_source_reading(reading, payload):
    fields = [field for span in payload['evidence_spans'] for field in span['fields']]
    from .source_segment_catalog import source_segment_catalog,select_source_segment
    catalog=source_segment_catalog(payload) if isinstance(reading,SegmentSourceReading) else None
    uses = []
    for atom_index, atom in enumerate(reading.atoms):
        groups = {'meaning': (atom.meaning,), 'conditions': atom.conditions,
                  'exclusions': atom.exclusions, 'missing_information': atom.missing_information}
        if isinstance(atom,TypedSourceAtomReading):groups['kind_basis']=(atom.kind_basis,)
        if isinstance(atom,SegmentSourceAtomReading) and atom.time_basis is not None:
            groups['time_basis']=(atom.time_basis,)
        for facet, claims in groups.items():
            for claim_index, claim in enumerate(claims):
                if claim.field_index >= len(fields):
                    raise ValueError('SOURCE_READING_FIELD_OUTSIDE_INPUT')
                source = fields[claim.field_index]['text']
                if catalog is not None:
                    segment=select_source_segment(payload,catalog,claim.segment_index,claim.end_segment_index)
                    if claim.field_index!=segment['field_index'] or claim.quote!=segment['text']:
                        raise ValueError('SOURCE_READING_SEGMENT_DRIFT')
                    start_byte,end_byte=segment['start_byte'],segment['end_byte']
                else:
                    if source.count(claim.quote) != 1:
                        raise ValueError('SOURCE_READING_QUOTE_NOT_UNIQUE_EXACT')
                    start=source.index(claim.quote)
                    start_byte,end_byte=len(source[:start].encode()),len(source[:start+len(claim.quote)].encode())
                uses.append({'atom_index': atom_index, 'facet': facet, 'claim_index': claim_index,
                    'field_index': claim.field_index, 'field_digest': byte_digest(source.encode()),
                    'start_byte':start_byte,'end_byte':end_byte,
                    **({'segment_index':claim.segment_index,'end_segment_index':segment['end_segment_index'],
                        'segment_digest':semantic_digest(segment)} if catalog is not None else {}),
                    'interpretation_digest': semantic_digest(claim.interpretation)})
    body = {'contract_version': 'boi/bound-source-reading@2' if catalog is not None else 'boi/bound-source-reading@1',
        **({'source_segment_catalog_digest':catalog['catalog_digest']} if catalog is not None else {}),
        'input_digest': semantic_digest(payload), 'reading': reading.model_dump(mode='json'),
        'quote_bindings': uses, 'semantic_validated': False, 'canonical': False}
    return {**body, 'receipt_digest': semantic_digest(body)}


def bind_comparison(comparison, source_receipt, payload, *, expected_reading_digest):
    body = {key: value for key, value in source_receipt.items() if key != 'receipt_digest'}
    if (source_receipt['receipt_digest'] != expected_reading_digest or
        semantic_digest(body) != source_receipt['receipt_digest'] or
        body['input_digest'] != semantic_digest(payload)):
        raise ValueError('SOURCE_READING_RECEIPT_DRIFT')
    # Recheck the exact source bindings; a caller cannot substitute an edited reading.
    models={'boi/source-meaning-reading@1':SourceReading,'boi/source-meaning-reading@2':TypedSourceReading,
            'boi/source-meaning-reading@3':SegmentSourceReading}
    model=models.get(body['reading'].get('contract_version'),SourceReading)
    expected = bind_source_reading(model.model_validate(body['reading']), payload)
    if expected != source_receipt:
        raise ValueError('SOURCE_READING_RECEIPT_DRIFT')
    known = {(d['concept_id'], d['revision_digest']) for d in payload['existing_definitions']}
    seen = set()
    for proposal in comparison.relationships:
        if proposal.atom_index >= len(body['reading']['atoms']):
            raise ValueError('COMPARISON_ATOM_OUTSIDE_READING')
        target = (proposal.target.ref, proposal.target.revision_digest)
        if target not in known:
            raise ValueError('COMPARISON_TARGET_NOT_READ')
        key = (proposal.atom_index, *target)
        if key in seen:
            raise ValueError('COMPARISON_DUPLICATE_TARGET')
        seen.add(key)
    value = {'contract_version': 'boi/bound-meaning-comparison@1',
        'source_reading_receipt_digest': source_receipt['receipt_digest'],
        'comparison': comparison.model_dump(mode='json'), 'semantic_validated': False, 'canonical': False}
    return {**value, 'receipt_digest': semantic_digest(value)}
