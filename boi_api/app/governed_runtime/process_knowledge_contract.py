"""Process meaning profile: evidence-linked atomic assertions, not query metadata.

The model proposes meaning. This schema/lint verifies structure and exact source
binding; semantic fidelity and scientific correctness require separate evidence.
"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef


class ProcessQuotation(FrozenContract):
    field_locator: str = Field(description='Exact field_locator from the source projection, not a term or assertion ID.')
    quote: str = Field(min_length=1,description='Exact unchanged nonempty substring of this source field, including punctuation and whitespace. A formatting span may consist only of whitespace; never append an explanation to the quoted text.')
    occurrence: int = Field(default=0,ge=0,strict=True,
        description='Zero-based matching occurrence of quote within that field: 0 is the first occurrence, 1 the second. Use 0 when the quote appears only once.')


class ProcessTerm(FrozenContract):
    term_id: Ref = Field(description='An identifier local to this record, used by process_ref, subject_ref and object_refs.')
    label: Ref
    category: Literal['process','material','region','equipment','stage','quantity','defect','method','chemical','other']
    proposed_definition: str | None = Field(default=None,description='Preserve an explicit source-stated name expansion, naming equivalence or definition here with supporting evidence. Do not leave a source-provided definition only inside a label or quotation. Null means no supported definition is proposed, not that the source contains none. Never invent an expansion.')
    reused_definition: RevisionRef | None = None
    evidence: tuple[ProcessQuotation, ...] = Field(min_length=1)


class ProcessCondition(FrozenContract):
    """A source-stated condition; all qualifiers keep their own evidence."""
    statement: Ref
    evidence: tuple[ProcessQuotation, ...] = Field(min_length=1)


class ProcessAssertion(FrozenContract):
    assertion_id: Ref
    subject_ref: Ref = Field(description='The term_id of a term in this same process record, never a source locator.')
    predicate: Ref
    object_text: Ref
    object_refs: tuple[Ref, ...] = Field(default=(),description='Optional term_id references in the same record.')
    statement: Ref
    category: Literal['action','purpose','sequence','control','conditional_effect','applicability','definition','equipment','chemistry','observation']
    polarity: Literal['positive','negative']
    modality: Literal['asserted','possible','intended','required']
    conditions: tuple[ProcessCondition, ...] = ()
    exceptions: tuple[ProcessCondition, ...] = ()
    applicability: tuple[ProcessCondition, ...] = ()
    depends_on: tuple[Ref, ...] = Field(default=(),description='Assertion IDs in this record on which this assertion logically depends; must form an acyclic graph, not process-order edges.')
    evidence: tuple[ProcessQuotation, ...] = Field(min_length=1)
    uncertainties: tuple[Ref, ...] = ()


class UninterpretedProcessSpan(FrozenContract):
    evidence: ProcessQuotation
    reason: Ref


class ProcessRecordMeaning(FrozenContract):
    process_ref: Ref = Field(description='The term_id of this record\'s root process term in terms. This is not a source JSON pointer.')
    source_description_fields: tuple[str, ...] = Field(min_length=1,
        description='Exact source projection field_locator values containing this process description. Account for all their substantive text.')
    terms: tuple[ProcessTerm, ...] = Field(min_length=1)
    assertions: tuple[ProcessAssertion, ...] = Field(min_length=1)
    uninterpreted: tuple[UninterpretedProcessSpan, ...] = ()

    @model_validator(mode='after')
    def graph_integrity(self):
        terms = {t.term_id for t in self.terms}
        claims = {c.assertion_id for c in self.assertions}
        if len(terms) != len(self.terms) or len(claims) != len(self.assertions) or terms & claims:
            raise ValueError('PROCESS_IDENTITY_AMBIGUOUS')
        if self.process_ref not in terms:
            raise ValueError('PROCESS_ROOT_TERM_MISSING')
        if len(set(self.source_description_fields)) != len(self.source_description_fields):
            raise ValueError('PROCESS_DESCRIPTION_FIELD_DUPLICATE')
        graph = {c.assertion_id:c.depends_on for c in self.assertions}
        for claim in self.assertions:
            if claim.subject_ref not in terms or not set(claim.object_refs) <= terms or not set(claim.depends_on) <= claims:
                raise ValueError('PROCESS_ASSERTION_REFERENCE_MISSING')
        visiting, done = set(), set()
        def walk(key):
            if key in visiting:
                raise ValueError('PROCESS_DERIVATION_CYCLE')
            if key not in done:
                visiting.add(key)
                for parent in graph[key]:walk(parent)
                visiting.remove(key)
                done.add(key)
        for key in graph:walk(key)
        return self


class ProcessKnowledgeDraft(FrozenContract):
    contract_version: Literal['boi/process-meaning@1'] = 'boi/process-meaning@1'
    source_revision_digest: Digest
    extraction_context_digest: Digest
    definition_revisions_used: tuple[RevisionRef, ...] = ()
    records: tuple[ProcessRecordMeaning, ...] = Field(min_length=1)
    limitations: tuple[Ref, ...] = ()

    @model_validator(mode='after')
    def unique_records(self):
        if len({r.process_ref for r in self.records}) != len(self.records):
            raise ValueError('PROCESS_RECORD_IDENTITY_DUPLICATE')
        if len(set(self.definition_revisions_used)) != len(self.definition_revisions_used):
            raise ValueError('PROCESS_REUSED_DEFINITION_DUPLICATE')
        return self
