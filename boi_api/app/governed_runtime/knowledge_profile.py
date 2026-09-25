"""Data-declared native knowledge Profiles and deterministic type checks.

Profiles supply semantics; these checks do not infer them from words. Registries
are assembled from authorized, version-pinned native assets by the caller. Merely
constructing a registry does not adopt a pack or grant a use qualification.
"""
from decimal import Decimal
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from .knowledge_content import meaning_pointer
from .knowledge_projection_contract import (
    ProjectionContract, ProjectionRevision, ProjectionComponent, ProjectionScalar,
    ProjectionPredicate, DefinitionReference,
)
from .semantic_binding_contract import Ref, semantic_digest


class MetadataConstraint(ProjectionContract):
    pointer: str = Field(min_length=1, max_length=2048, pattern=r'^/')
    value_kind: Literal['text', 'decimal', 'integer', 'boolean', 'object', 'array']
    required: bool
    allowed_values: tuple[JsonValue, ...] = Field(default=(), max_length=256)
    minimum: str | None = None
    maximum: str | None = None

    @model_validator(mode='after')
    def numeric_bounds(self):
        if any(v is not None for v in (self.minimum,self.maximum)):
            if self.value_kind not in ('decimal','integer'):
                raise ValueError('KNOWLEDGE_PROFILE_NUMERIC_BOUND_TYPE')
            for value in (self.minimum,self.maximum):
                if value is not None:
                    ProjectionScalar(kind='decimal',value=value)
            if self.minimum is not None and self.maximum is not None and Decimal(self.minimum)>Decimal(self.maximum):
                raise ValueError('KNOWLEDGE_PROFILE_BOUND_ORDER')
        return self


class ObjectTypeDeclaration(ProjectionContract):
    kind: Literal['object_type'] = 'object_type'
    id: Ref
    label: Ref
    description: Ref
    metadata_constraints: tuple[MetadataConstraint, ...] = Field(default=(), max_length=256)


class LocalType(ProjectionContract):
    component_id: Ref


TypeLink = LocalType | ProjectionComponent


class PredicateDeclaration(ProjectionContract):
    kind: Literal['predicate'] = 'predicate'
    id: Ref
    label: Ref
    description: Ref
    subject_type: TypeLink
    value_kind: Literal['text','decimal','boolean','object']
    target_type: TypeLink | None = None
    role: Ref
    quantity_semantics: Literal['not_applicable','dimensionless','declared','unknown']
    quantity_revision: DefinitionReference | None = None
    unit_revision: DefinitionReference | None = None
    value_semantics: Literal['not_applicable','absolute','interval','unknown']
    cardinality: Literal['one','many']
    allowed_operators: tuple[Literal['eq','ne','lt','lte','gt','gte'], ...] = Field(min_length=1,max_length=6)

    @model_validator(mode='after')
    def typed_operations(self):
        if len(set(self.allowed_operators))!=len(self.allowed_operators):
            raise ValueError('KNOWLEDGE_PROFILE_OPERATOR_DUPLICATE')
        if self.value_kind!='decimal' and set(self.allowed_operators)-{'eq','ne'}:
            raise ValueError('KNOWLEDGE_PROFILE_OPERATOR_TYPE')
        if (self.value_kind=='decimal') == (self.value_semantics=='not_applicable'):
            raise ValueError('KNOWLEDGE_PROFILE_VALUE_SEMANTICS_REQUIRED')
        return self


class ProfileLevelScheme(ProjectionContract):
    scheme: Ref
    version: Ref
    values: tuple[Ref,...] = Field(min_length=1,max_length=256)


class KnowledgeProfileDeclaration(ProjectionContract):
    contract_version: Literal['boi/knowledge-profile@1'] = 'boi/knowledge-profile@1'
    profile_id: Ref
    schema_ref: Ref
    label: Ref
    description: Ref
    level_scheme: ProfileLevelScheme | None = None
    components: tuple[ObjectTypeDeclaration | PredicateDeclaration,...] = Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def identities(self):
        if len({c.id for c in self.components})!=len(self.components):
            raise ValueError('KNOWLEDGE_PROFILE_COMPONENT_DUPLICATE')
        return self


class KnowledgeProfileRegistry:
    """Exact native revisions supplied by an authorized package/profile reader."""
    def __init__(self, profiles):
        if not profiles or len(profiles)>128:
            raise ValueError('KNOWLEDGE_PROFILE_REGISTRY_BOUND')
        self.profiles = {ProjectionRevision.model_validate(ref.model_dump(mode='json')):
            KnowledgeProfileDeclaration.model_validate(value.model_dump(mode='json') if hasattr(value,'model_dump') else value)
            for ref,value in profiles.items()}

    def component(self, reference, expected):
        reference=ProjectionComponent.model_validate(reference.model_dump(mode='json'))
        profile=self.profiles.get(reference.revision)
        if profile is None:
            raise ValueError('KNOWLEDGE_PROFILE_REVISION_UNAVAILABLE')
        # Only complete component addresses are executable definitions. A pointer
        # to a nested label or another object with similar values is not a type.
        pointers={f'/components/{i}':component for i,component in enumerate(profile.components)}
        component=pointers.get(reference.pointer)
        if not isinstance(component,expected):
            raise ValueError('KNOWLEDGE_PROFILE_COMPONENT_KIND')
        return component

    def type_reference(self, owner, link):
        if isinstance(link,ProjectionComponent):
            self.component(link,ObjectTypeDeclaration)
            return link
        profile=self.profiles[owner]
        indices=[i for i,c in enumerate(profile.components) if c.id==link.component_id and isinstance(c,ObjectTypeDeclaration)]
        if len(indices)!=1:
            raise ValueError('KNOWLEDGE_PROFILE_SUBJECT_TYPE_UNAVAILABLE')
        return ProjectionComponent(revision=owner,pointer=f'/components/{indices[0]}')

    def predicate(self, reference):
        declaration=self.component(reference,PredicateDeclaration)
        subject=self.type_reference(reference.revision,declaration.subject_type)
        target=self.type_reference(reference.revision,declaration.target_type) if declaration.target_type is not None else None
        return declaration,ProjectionPredicate(revision=reference,subject_type=subject,
            value_kind=declaration.value_kind,target_type=target,unit_revision=declaration.unit_revision,
            quantity_revision=declaration.quantity_revision,quantity_semantics=declaration.quantity_semantics)

    def validate_metadata(self, object_type, metadata):
        declaration=self.component(object_type,ObjectTypeDeclaration)
        checked=[]
        for constraint in declaration.metadata_constraints:
            try:
                value=meaning_pointer(metadata,constraint.pointer)
            except ValueError as error:
                if str(error)!='KNOWLEDGE_CONTENT_POINTER_MISSING' or constraint.required:
                    raise ValueError('KNOWLEDGE_PROFILE_METADATA_REQUIRED') from None
                continue
            kind=constraint.value_kind
            types={'text':str,'integer':int,'boolean':bool,'object':dict,'array':list,'decimal':str}
            if type(value) is not types[kind]:
                raise ValueError('KNOWLEDGE_PROFILE_METADATA_TYPE')
            if kind=='decimal':ProjectionScalar(kind='decimal',value=value)
            if constraint.allowed_values and not any(semantic_digest(value)==semantic_digest(allowed) for allowed in constraint.allowed_values):
                raise ValueError('KNOWLEDGE_PROFILE_METADATA_ENUM')
            if constraint.minimum is not None and Decimal(value)<Decimal(constraint.minimum):
                raise ValueError('KNOWLEDGE_PROFILE_METADATA_MINIMUM')
            if constraint.maximum is not None and Decimal(value)>Decimal(constraint.maximum):
                raise ValueError('KNOWLEDGE_PROFILE_METADATA_MAXIMUM')
            checked.append(constraint.pointer)
        return tuple(checked)
