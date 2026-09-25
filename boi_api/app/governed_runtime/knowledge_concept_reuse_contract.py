"""Addresses for reviewed native concept reuse, not a new identity registry."""
from typing import Literal
from pydantic import Field, JsonValue, model_validator
from .knowledge_projection_contract import ProjectionContract, ProjectionComponent, ProjectionRevision


class ConceptReuseSelection(ProjectionContract):
    filter_index: int = Field(ge=0,le=127,strict=True)
    definition_revision: ProjectionRevision
    review_revision: ProjectionRevision
    target_definition: ProjectionRevision


class ConceptReuseContext(ProjectionContract):
    source_query: dict[str,JsonValue]
    selections: tuple[ConceptReuseSelection,...] = Field(min_length=1,max_length=128)

    @model_validator(mode='after')
    def one_selection_per_filter(self):
        if len({s.filter_index for s in self.selections}) != len(self.selections):
            raise ValueError('KNOWLEDGE_REUSE_FILTER_SELECTION_AMBIGUOUS')
        if self.source_query.get('reuse_context') is not None:
            raise ValueError('KNOWLEDGE_REUSE_NESTED_CONTEXT_DENIED')
        return self


class ScopedConceptReuseLink(ProjectionContract):
    concept_pointer: str = Field(pattern=r'^/concepts/[0-9]+$',max_length=2048)
    assertion_pointer: str = Field(pattern=r'^/assertions/[0-9]+$',max_length=2048)
    source: ProjectionComponent
    predicate: ProjectionComponent
    literal: str = Field(min_length=1,max_length=32000)


class ScopedConceptReuseDeclaration(ProjectionContract):
    contract_version: Literal['boi/scoped-concept-reuse@1']='boi/scoped-concept-reuse@1'
    relation_kind: Literal['concept_reuse']='concept_reuse'
    support_basis: Literal['reviewed_interpretation']='reviewed_interpretation'
    links: tuple[ScopedConceptReuseLink,...] = Field(min_length=1,max_length=128)
