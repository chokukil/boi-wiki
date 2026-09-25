"""Additive semantic descriptor revision; draft validation is not qualification."""
from typing import Annotated, Union

from pydantic import BaseModel, TypeAdapter, Field, model_validator

from . import domain_profile_v02 as v02
from . import domain_profile_v03 as v03
from .semantic_binding_contract import SemanticDescriptor


class SemanticContractEntry(BaseModel):
    semantic_contract: SemanticDescriptor

    @model_validator(mode='after')
    def consistent_declarations(self):
        semantic = self.semantic_contract
        if semantic.kind != self.kind or semantic.authority_basis != self.authority_basis:
            raise ValueError('DOMAIN_SEMANTIC_KIND_AUTHORITY_MISMATCH')
        if self.kind == 'Term' and semantic.definition != self.definition:
            raise ValueError('DOMAIN_SEMANTIC_DEFINITION_MISMATCH')
        if set(semantic.aliases) != set(self.aliases):
            raise ValueError('DOMAIN_SEMANTIC_ALIAS_MISMATCH')
        if hasattr(self, 'unit_semantics') and self.unit_semantics != semantic.unit_semantics:
            raise ValueError('DOMAIN_SEMANTIC_UNIT_MISMATCH')
        if hasattr(self, 'unit_ref') and self.unit_ref != semantic.unit_ref:
            raise ValueError('DOMAIN_SEMANTIC_UNIT_REF_MISMATCH')
        return self


class TermEntry(SemanticContractEntry, v02.TermEntry): pass
class ObjectTypeEntry(SemanticContractEntry, v03.ObjectTypeEntry): pass
class PropertyDefinitionEntry(SemanticContractEntry, v02.PropertyDefinitionEntry): pass
class RelationTypeEntry(SemanticContractEntry, v02.RelationTypeEntry): pass
class ValueTypeEntry(SemanticContractEntry, v02.ValueTypeEntry): pass
class MetricEntry(SemanticContractEntry, v02.MetricEntry): pass
class RuleEntry(SemanticContractEntry, v02.RuleEntry): pass


DomainEntryUnion = Annotated[Union[
    TermEntry, ObjectTypeEntry, PropertyDefinitionEntry, RelationTypeEntry,
    ValueTypeEntry, MetricEntry, RuleEntry,
], Field(discriminator='kind')]
_ADAPTER = TypeAdapter(DomainEntryUnion)


def validate_domain_profile_entry(value: object):
    return _ADAPTER.validate_python(value)


def domain_profile_json_schema():
    return _ADAPTER.json_schema()
