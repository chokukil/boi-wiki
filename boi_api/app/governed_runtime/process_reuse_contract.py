"""Node-bound definition reuse proposed by external agents, never approval."""
from typing import Literal

from pydantic import Field, model_validator

from .knowledge_node_contract import KnowledgeNodeRef
from .process_knowledge_contract import ProcessKnowledgeDraft
from .semantic_binding_contract import Digest, FrozenContract, Ref


class DefinitionScopeComparison(FrozenContract):
    dimension: Literal['meaning','applicability','conditions','exceptions']
    relation: Literal['aligned','different','not_stated','unknown']
    reason: Ref


class ProcessDefinitionUse(FrozenContract):
    term_pointer: Ref = Field(description='The local proposed term to interpret, /records/{i}/terms/{j}.')
    definition_node: KnowledgeNodeRef
    relation: Literal['equivalent','narrower','broader','related','conflict','unknown']
    application: Literal['interpret_term','comparison_only']
    rationale: Ref
    scope_comparisons: tuple[DefinitionScopeComparison,...] = Field(min_length=4,max_length=4)

    @model_validator(mode='after')
    def complete_comparison(self):
        if {c.dimension for c in self.scope_comparisons}!={'meaning','applicability','conditions','exceptions'}:
            raise ValueError('PROCESS_REUSE_SCOPE_DIMENSIONS_INCOMPLETE')
        if self.application=='interpret_term' and (self.relation!='equivalent'
                or any(c.relation in ('different','unknown') for c in self.scope_comparisons)
                or next(c for c in self.scope_comparisons if c.dimension=='meaning').relation!='aligned'):
            raise ValueError('PROCESS_REUSE_UNRESOLVED_RELATION_CANNOT_INTERPRET')
        return self


class ProcessReuseProposal(FrozenContract):
    contract_version: Literal['boi/process-definition-reuse-proposal@1'] = 'boi/process-definition-reuse-proposal@1'
    context_digest: Digest
    draft: ProcessKnowledgeDraft
    definition_uses: tuple[ProcessDefinitionUse,...]

    @model_validator(mode='after')
    def one_authoritative_use_representation(self):
        if self.draft.extraction_context_digest!=self.context_digest:
            raise ValueError('PROCESS_REUSE_EXTRACTION_CONTEXT_MISMATCH')
        # The old revision-only fields are emitted mechanically as a legacy
        # projection after binding. The agent proposes node references once.
        if self.draft.definition_revisions_used or any(t.reused_definition for r in self.draft.records for t in r.terms):
            raise ValueError('PROCESS_REUSE_LEGACY_FIELDS_MUST_BE_EMPTY')
        applied=[u.term_pointer for u in self.definition_uses if u.application=='interpret_term']
        if len(set(applied))!=len(applied):
            raise ValueError('PROCESS_REUSE_AMBIGUOUS_APPLIED_DEFINITION')
        if len({(u.term_pointer,u.definition_node) for u in self.definition_uses})!=len(self.definition_uses):
            raise ValueError('PROCESS_REUSE_DUPLICATE_COMPARISON')
        return self
