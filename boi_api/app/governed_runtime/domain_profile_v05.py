"""Explicit semantic evidence/reuse declarations; only active closure is authority.

This revision does not migrate or reinterpret 0.4 documents. Draft declarations
are not approval. Runtime may consume them only from the exact qualified active
revision, with current source policy and independently resolved field evidence.
Physical bindings and execution contracts remain separate profiles.
"""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter, model_validator
from . import domain_profile_v04 as v04
from .semantic_binding_contract import (
    FrozenContract, Ref, Digest, RevisionRef, EvidenceUse, SemanticDescriptor, semantic_digest,
)


class SemanticReuseDeclaration(FrozenContract):
    declaration_id: Ref
    identity_basis: Literal['approved_stable_identity', 'approved_scoped_alias']
    identity_ref: Ref
    policy_digest: Digest
    source_system: Ref
    dataset: Ref
    namespace: Ref
    source_profile_digest: Digest
    semantic_input_digest: Digest
    source_semantics: SemanticDescriptor
    field_indices: tuple[int, ...] = Field(min_length=1, max_length=32)
    allowed_evidence_content_digests: tuple[Digest, ...] = Field(min_length=1)
    required_dependency_refs: tuple[RevisionRef, ...]
    allow_scope_specialization: bool
    source_validity_policy: Literal['metadata_revision_only', 'must_be_contained']

    @model_validator(mode='after')
    def exact_source_contract(self):
        if (any(index<0 for index in self.field_indices)
            or len(set(self.field_indices))!=len(self.field_indices)
            or self.source_semantics.scope.namespace!=self.namespace):
            raise ValueError('SEMANTIC_REUSE_SOURCE_CONTRACT_INVALID')
        return self


class SemanticAuthorityEntry(FrozenContract):
    semantic_evidence_uses: tuple[EvidenceUse, ...]
    semantic_reuse_declarations: tuple[SemanticReuseDeclaration, ...]

    @model_validator(mode='after')
    def declared_support(self):
        expected=semantic_digest(self.semantic_contract)
        if any(use.supports_contract_digest!=expected or use.support_basis not in {
            'approved_structured_contract','human_reviewed_interpretation'}
            for use in self.semantic_evidence_uses):
            raise ValueError('DOMAIN_SEMANTIC_EVIDENCE_JUSTIFICATION_INVALID')
        if self.semantic_reuse_declarations and not self.semantic_evidence_uses:
            raise ValueError('DOMAIN_SEMANTIC_REUSE_EVIDENCE_REQUIRED')
        supported={field for use in self.semantic_evidence_uses for field in use.supports_fields}
        if self.semantic_reuse_declarations and not {
            'definition','role','quantity_kind_ref','unit_ref','scope','conditions','exceptions'}<=supported:
            raise ValueError('DOMAIN_SEMANTIC_REUSE_FIELD_SUPPORT_REQUIRED')
        ids=[item.declaration_id for item in self.semantic_reuse_declarations]
        if len(set(ids))!=len(ids):
            raise ValueError('DOMAIN_SEMANTIC_REUSE_DECLARATION_DUPLICATE')
        if any(item.namespace!=self.semantic_contract.scope.namespace for item in self.semantic_reuse_declarations):
            raise ValueError('DOMAIN_SEMANTIC_REUSE_NAMESPACE_MISMATCH')
        return self


class TermEntry(SemanticAuthorityEntry,v04.TermEntry): pass
class ObjectTypeEntry(SemanticAuthorityEntry,v04.ObjectTypeEntry): pass
class PropertyDefinitionEntry(SemanticAuthorityEntry,v04.PropertyDefinitionEntry): pass
class RelationTypeEntry(SemanticAuthorityEntry,v04.RelationTypeEntry): pass
class ValueTypeEntry(SemanticAuthorityEntry,v04.ValueTypeEntry): pass
class MetricEntry(SemanticAuthorityEntry,v04.MetricEntry): pass
class RuleEntry(SemanticAuthorityEntry,v04.RuleEntry): pass


_ADAPTER=TypeAdapter(Annotated[Union[TermEntry,ObjectTypeEntry,PropertyDefinitionEntry,
    RelationTypeEntry,ValueTypeEntry,MetricEntry,RuleEntry],Field(discriminator='kind')])


def validate_domain_profile_entry(value: object):
    return _ADAPTER.validate_python(value)


def domain_profile_json_schema():
    return _ADAPTER.json_schema()
