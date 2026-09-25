"""Versioned definition reuse with explicitly accounted scope facets.

Selections and semantic alignment are agent proposals. Presence/absence in the
selected representation is derived from references, never from the prose reason.
"""
from typing import Literal

from pydantic import Field,model_validator

from .knowledge_node_contract import KnowledgeNodeRef
from .process_knowledge_contract import ProcessKnowledgeDraft
from .process_reuse_contract import DefinitionScopeComparison,ProcessDefinitionUse,ProcessReuseProposal
from .semantic_binding_contract import Digest,FrozenContract,Ref


class ScopeFacetDecision(FrozenContract):
    target_pointer: Ref = Field(description='Exact pointer from the record scope inventory. Account for each inventory facet once.')
    disposition: Literal['applies','not_applicable','unresolved']
    reason: Ref = Field(description='Explain why this source-bound facet does or does not constrain this particular definition use.')


class ScopeFacetComparison(FrozenContract):
    dimension: Literal['applicability','conditions','exceptions']
    local: tuple[ScopeFacetDecision,...]
    definition: tuple[ScopeFacetDecision,...]
    alignment: Literal['aligned','different','unknown'] | None = Field(description='Null only when neither side selects a facet and none is unresolved. Otherwise compare the selected scope; unknown when any facet is unresolved. Presence is derived from the selections, not claimed separately.')
    reason: Ref

    @model_validator(mode='after')
    def reference_alignment(self):
        for side in (self.local,self.definition):
            if len({f.target_pointer for f in side})!=len(side):raise ValueError('PROCESS_REUSE_SCOPE_FACET_DUPLICATE')
        unresolved=any(f.disposition=='unresolved' for f in (*self.local,*self.definition))
        present=[any(f.disposition=='applies' for f in side) for side in (self.local,self.definition)]
        if unresolved:
            if self.alignment!='unknown':raise ValueError('PROCESS_REUSE_SCOPE_UNRESOLVED_REQUIRES_UNKNOWN')
        elif not any(present):
            if self.alignment is not None:raise ValueError('PROCESS_REUSE_SCOPE_EMPTY_REQUIRES_NULL_ALIGNMENT')
        elif self.alignment is None:
            raise ValueError('PROCESS_REUSE_SCOPE_PRESENT_REQUIRES_ALIGNMENT')
        elif self.alignment=='aligned' and not all(present):
            raise ValueError('PROCESS_REUSE_SCOPE_ALIGNED_REQUIRES_BOTH_SIDES')
        return self

    def projection(self):
        return DefinitionScopeComparison(dimension=self.dimension,
            relation=self.alignment or 'not_stated',reason=self.reason)


class MeaningAlignment(FrozenContract):
    relation: Literal['aligned','different','unknown']
    reason: Ref


class ProcessDefinitionUseV2(FrozenContract):
    contract_version: Literal['boi/process-definition-use@2'] = 'boi/process-definition-use@2'
    term_pointer: Ref
    definition_node: KnowledgeNodeRef
    relation: Literal['equivalent','narrower','broader','related','conflict','unknown'] = Field(description='Semantic relation of the local term meaning to the referenced definition, in that direction. This is proposed meaning, not a lint verdict.')
    application: Literal['interpret_term','comparison_only'] = Field(description='interpret_term requires relation=equivalent, meaning_alignment=aligned, and every scope dimension aligned or empty (null). Any different or unknown meaning/scope requires comparison_only; this preserves the comparison without treating it as an interpreting definition.')
    rationale: Ref
    meaning_alignment: MeaningAlignment
    scope_assessments: tuple[ScopeFacetComparison,...] = Field(min_length=3,max_length=3,
        description='Exactly one entry each for applicability, conditions and exceptions, even for an empty dimension. Account for every facet in each selected record, with explicit not_applicable when it does not constrain this term. Neither side applies and none unresolved: alignment=null. Only one side applies: cannot be aligned. Any unresolved facet: alignment=unknown.')

    @model_validator(mode='after')
    def complete_scope(self):
        if {s.dimension for s in self.scope_assessments}!={'applicability','conditions','exceptions'}:
            raise ValueError('PROCESS_REUSE_SCOPE_DIMENSIONS_INCOMPLETE')
        self.legacy_projection()  # Preserve the unresolved application guard.
        return self

    def legacy_projection(self):
        return ProcessDefinitionUse(term_pointer=self.term_pointer,definition_node=self.definition_node,
            relation=self.relation,application=self.application,rationale=self.rationale,
            scope_comparisons=(DefinitionScopeComparison(dimension='meaning',**self.meaning_alignment.model_dump()),
                *(s.projection() for s in self.scope_assessments)))


class ProcessReuseProposalV2(FrozenContract):
    contract_version: Literal['boi/process-definition-reuse-proposal@2'] = 'boi/process-definition-reuse-proposal@2'
    context_digest: Digest
    draft: ProcessKnowledgeDraft
    definition_uses: tuple[ProcessDefinitionUseV2,...]

    @model_validator(mode='after')
    def one_authoritative_representation(self):
        self.legacy_projection()  # The old write invariants still apply.
        return self

    def legacy_projection(self):
        return ProcessReuseProposal(context_digest=self.context_digest,draft=self.draft,
            definition_uses=tuple(u.legacy_projection() for u in self.definition_uses))
