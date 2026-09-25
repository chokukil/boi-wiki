"""S1: storage identity, content revision and space policy are separate axes."""
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, RevisionRef, semantic_digest


class KnowledgeSpaceTarget(FrozenContract):
    """A requested destination; caller-provided scope is never an ACL grant."""
    visibility: Literal['private', 'team', 'public'] = 'private'
    team_id: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode='after')
    def team_required(self):
        if (self.visibility == 'team') != (self.team_id is not None):
            raise ValueError('KNOWLEDGE_SPACE_TEAM_BINDING_INVALID')
        return self


class NativeKnowledgeIdentity(FrozenContract):
    """Preserve the historical identity creator when a different actor edits."""
    identity_creator: str = Field(min_length=1, max_length=1000)
    namespace: str = Field(min_length=1, max_length=1000)
    logical_id: str = Field(min_length=1, max_length=1000)

    @property
    def stable_id(self):
        return 'domain-asset-head:' + semantic_digest([self.identity_creator, self.namespace, self.logical_id])


class KnowledgeSpaceMembership(FrozenContract):
    """A server-persisted policy revision must be admitted before this is usable.

    The shape alone has no authority. Multiple memberships can reference one
    unchanged native content revision; it never contains copied source content.
    """
    contract_version: Literal['boi/knowledge-space-membership@1'] = 'boi/knowledge-space-membership@1'
    identity: NativeKnowledgeIdentity
    content_revision: RevisionRef
    target: KnowledgeSpaceTarget
    policy_revision: RevisionRef
    source_closure_digest: Digest
    changed_by: str = Field(min_length=1, max_length=1000)
    state: Literal['active', 'revoked']


@dataclass(frozen=True)
class KnowledgeSpaceIntentAdmission:
    """Server-owned permission to submit this intent, not a membership or use grant."""
    principal_id: str
    target: KnowledgeSpaceTarget
    authority_digest: str
    audience: str


def admit_space_intent(principal, target):
    """Reuse product role/team semantics, without inventing file system paths.

    Existing file promotion requires boi.promoter; Team additionally requires
    actual membership (or the product's admin authority). Public is the product
    public audience, not a permission to publish onto the anonymous Internet.
    Actual content/source sharing remains the publication admission's job.
    """
    target = KnowledgeSpaceTarget.model_validate(target)
    roles, teams = set(principal.roles), set(principal.teams)
    admin = 'boi.admin' in roles
    if not principal.employee_id or not (admin or 'boi.editor' in roles):
        raise ValueError('KNOWLEDGE_SPACE_WRITE_NOT_AUTHORIZED')
    if target.visibility != 'private' and not (admin or 'boi.promoter' in roles):
        raise ValueError('KNOWLEDGE_SPACE_SHARING_NOT_AUTHORIZED')
    if target.visibility == 'team' and target.team_id not in teams and not admin:
        raise ValueError('KNOWLEDGE_SPACE_TEAM_NOT_AUTHORIZED')
    basis = {'contract_version':'boi/knowledge-space-intent-authority@1', 'principal':principal.employee_id,
             'roles':sorted(roles), 'teams':sorted(teams), 'target':target.model_dump(mode='json')}
    audience = {'private':'identity_owner', 'team':'current_team_members', 'public':'existing_product_public_policy'}[target.visibility]
    return KnowledgeSpaceIntentAdmission(principal.employee_id, target, semantic_digest(basis), audience)
