"""Common typed assertions, retaining domain qualifiers and source ownership."""
from datetime import datetime
from typing import Literal
from pydantic import Field, model_validator

from .filter_expression import FilterExpression, validate_filter_expression
from .knowledge_projection_contract import ProjectionContract, ProjectionComponent, ProjectionScalar
from .semantic_binding_contract import Ref,RevisionRef,SemanticDescriptor
from .formula_definition_context import FormulaDefinitionContext


class ContextPredicate(ProjectionContract):
    subject_ref: Ref
    predicate: ProjectionComponent
    operator: Literal['eq','ne','lt','lte','gt','gte']
    value: ProjectionScalar


class TypedCondition(ProjectionContract):
    statement: Ref
    atoms: tuple[ContextPredicate,...] = Field(default=(),max_length=128)
    expression: FilterExpression | None = None

    @model_validator(mode='after')
    def complete_expression(self):
        if bool(self.atoms)!=(self.expression is not None):
            raise ValueError('KNOWLEDGE_CONDITION_EXPRESSION_REQUIRED')
        if self.expression is not None:
            validate_filter_expression(self.expression,len(self.atoms))
        return self


class KnowledgeValidTime(ProjectionContract):
    state: Literal['unknown','timeless','interval']
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode='after')
    def explicit_time(self):
        if self.state=='interval':
            if self.start is None or self.start.utcoffset() is None or (self.end is not None and (
                    self.end.utcoffset() is None or self.end<=self.start)):
                raise ValueError('KNOWLEDGE_VALID_TIME_INTERVAL_INVALID')
        elif self.start is not None or self.end is not None:
            raise ValueError('KNOWLEDGE_VALID_TIME_NOT_APPLICABLE')
        return self


class TypedKnowledgeAssertion(ProjectionContract):
    id: Ref
    predicate: ProjectionComponent
    value: ProjectionScalar
    statement: Ref
    assertion_kind: Literal['source_reported','interpretation','derived','recommendation']
    polarity: Literal['positive','negative']
    modality: Literal['asserted','possible','intended','required']
    conditions: tuple[TypedCondition,...] = Field(default=(),max_length=64)
    exceptions: tuple[TypedCondition,...] = Field(default=(),max_length=64)
    applicability: tuple[TypedCondition,...] = Field(default=(),max_length=64)
    valid_time: KnowledgeValidTime
    depends_on: tuple[Ref,...] = Field(default=(),max_length=256)
    uncertainties: tuple[Ref,...] = Field(default=(),max_length=256)


class KnowledgeFormulaParameter(ProjectionContract):
    """An evidenced parameter definition, not an observed numeric value.

    The execution identity is the containing knowledge's stable ID/revision
    plus this local id. The descriptor reuses the existing Formula semantics.
    Unit and quantity definitions are separately read, checked and authorized.
    """
    id: Ref
    parameter_name: Ref
    component: Ref
    quantity: Ref
    semantic_descriptor: SemanticDescriptor
    unit_definition: RevisionRef
    quantity_definition: RevisionRef
    statement: Ref
    assertion_kind: Literal['source_reported','interpretation','derived','recommendation']
    depends_on: tuple[Ref,...] = Field(min_length=1,max_length=256)
    uncertainties: tuple[Ref,...] = Field(default=(),max_length=256)
    calculation_context: FormulaDefinitionContext | None = Field(default=None,exclude_if=lambda v:v is None)

    @model_validator(mode='after')
    def exact_definitions(self):
        descriptor=self.semantic_descriptor
        if (descriptor.unit_semantics!='declared'
                or descriptor.unit_revision_digest!=self.unit_definition.revision_digest
                or descriptor.quantity_kind_ref!=self.quantity
                or not self.quantity.startswith(self.quantity_definition.ref+'#/concepts/')
                or descriptor.value_semantics not in ('absolute','interval')):
            raise ValueError('KNOWLEDGE_FORMULA_PARAMETER_DEFINITIONS_REQUIRED')
        if len(set(self.depends_on))!=len(self.depends_on):
            raise ValueError('KNOWLEDGE_FORMULA_PARAMETER_DEPENDENCY_DUPLICATE')
        return self


class TypedKnowledgeMeaning(ProjectionContract):
    contract_version: Literal['boi/typed-knowledge-meaning@1'] = 'boi/typed-knowledge-meaning@1'
    object_type: ProjectionComponent
    assertions: tuple[TypedKnowledgeAssertion,...] = Field(default=(),max_length=2000)
    parameters: tuple[KnowledgeFormulaParameter,...] = Field(default=(),max_length=64,exclude_if=lambda v:not v)

    @model_validator(mode='after')
    def derivation_closure(self):
        graph={a.id:a.depends_on for a in self.assertions}
        if len(graph)!=len(self.assertions):
            raise ValueError('KNOWLEDGE_ASSERTION_ID_DUPLICATE')
        if any(not set(deps)<=graph.keys() for deps in graph.values()):
            raise ValueError('KNOWLEDGE_ASSERTION_DEPENDENCY_MISSING')
        if len({p.id for p in self.parameters})!=len(self.parameters):
            raise ValueError('KNOWLEDGE_FORMULA_PARAMETER_ID_DUPLICATE')
        if any(not set(p.depends_on)<=graph.keys() for p in self.parameters):
            raise ValueError('KNOWLEDGE_FORMULA_PARAMETER_DEPENDENCY_MISSING')
        visiting,done=set(),set()
        def visit(key,depth):
            if depth>128:raise ValueError('KNOWLEDGE_DERIVATION_DEPTH_LIMIT')
            if key in visiting:raise ValueError('KNOWLEDGE_DERIVATION_CYCLE')
            if key in done:return
            visiting.add(key)
            for other in graph[key]:visit(other,depth+1)
            visiting.remove(key);done.add(key)
        for key in graph:visit(key,1)
        return self
