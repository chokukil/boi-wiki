"""Explicit semantic context authority, independent of execution permission.

These values are assembled by an authorized service. Constructing or hashing a
context grants no access, review, canonical status or Gateway permission.
"""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef


class ReviewedDefinitionAuthority(FrozenContract):
    contract_version: Literal['boi/reviewed-definition-authority@1'] = 'boi/reviewed-definition-authority@1'
    principal: Ref
    purpose: Ref
    run_id: Ref
    shard_id: Ref
    manifest_digest: Digest
    preview_digest: Digest
    interpretation_receipt_digest: Digest
    input_context_digest: Digest
    domain_candidate_closure_digest: Digest
    definition_index_digest: Digest
    mapping_input_digest: Digest
    quality_receipt_digest: Digest
    acl_policy_digest: Digest


class NativeReviewedDefinitionAuthority(FrozenContract):
    """Current Wiki-native evidence binding; no bulk-run or inference claims."""
    contract_version: Literal['boi/native-reviewed-definition-authority@1'] = 'boi/native-reviewed-definition-authority@1'
    principal: Ref
    purpose: Ref
    definition_revisions: tuple[RevisionRef, ...] = Field(min_length=1)
    review_revision: RevisionRef
    knowledge_reading_ref: RevisionRef
    definition_context_digest: Digest
    source_manifest_digest: Digest
    acl_policy_digest: Digest
    reviewer_relationship: Literal['same_session'] = 'same_session'
    session_identity_verified: Literal[False] = False
    execution_attested: Literal[False] = False
    execution_authority_granted: Literal[False] = False
    semantic_truth_proven: Literal[False] = False


class NativeProcessReviewAuthority(NativeReviewedDefinitionAuthority):
    """Source support for exact selected nodes and their preserved dependencies."""
    contract_version: Literal['boi/native-process-review-authority@1'] = 'boi/native-process-review-authority@1'
    reviewer_relationship: Literal['unknown'] = 'unknown'
    node_review_scope: Literal['selected_nodes'] = 'selected_nodes'
    selected_target_pointers: tuple[str, ...] = Field(default=(), exclude_if=lambda v: not v)
    dependency_target_pointers: tuple[str, ...] = Field(default=(), exclude_if=lambda v: not v)


DefinitionAuthority = ReviewedDefinitionAuthority | NativeReviewedDefinitionAuthority | NativeProcessReviewAuthority


class SemanticAuthorityFields(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    reviewed_definition_authority: DefinitionAuthority | None = Field(
        default=None, exclude_if=lambda value: value is None)

    @model_validator(mode='after')
    def exclusive_semantic_authority(self):
        release = getattr(self, 'active_release_digest', None)
        if self.reviewed_definition_authority is None:
            if not isinstance(release, str):
                raise ValueError('SEMANTIC_ACTIVE_RELEASE_OR_REVIEW_REQUIRED')
        elif release is not None:
            raise ValueError('SEMANTIC_REVIEW_CANNOT_CLAIM_ACTIVE_RELEASE')
        return self


def semantic_authority_values(value):
    authority = getattr(value, 'reviewed_definition_authority', None)
    return {'active_release_digest':getattr(value, 'active_release_digest', None),
        **({'reviewed_definition_authority':authority.model_dump(mode='json')}
            if authority is not None else {})}


def require_same_semantic_authority(left, right):
    if (getattr(left, 'active_release_digest', None)
            != getattr(right, 'active_release_digest', None)
            or getattr(left, 'reviewed_definition_authority', None)
            != getattr(right, 'reviewed_definition_authority', None)):
        raise ValueError('SEMANTIC_AUTHORITY_CHAIN_MISMATCH')


def require_active_semantic_authority(value):
    if (getattr(value, 'reviewed_definition_authority', None) is not None
            or getattr(value, 'active_release_digest', None) is None):
        raise ValueError('CANONICAL_ACTIVE_RELEASE_REQUIRED')


def require_reviewed_semantic_authority(value):
    if (getattr(value, 'reviewed_definition_authority', None) is None
            or getattr(value, 'active_release_digest', None) is not None):
        raise ValueError('REVIEWED_DEFINITION_AUTHORITY_REQUIRED')
