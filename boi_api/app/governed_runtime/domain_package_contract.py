"""Declarative team packages; these contracts cannot authorize executable code."""
from typing import Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef


class DomainPackageManifest(FrozenContract):
    contract_version: Literal['boi/domain-package@1'] = 'boi/domain-package@1'
    id: str = Field(min_length=1, max_length=120, pattern=r'^[a-z][a-z0-9._-]*$')
    display_name: Ref
    description: Ref
    version: Ref
    instructions: str = Field(default='', max_length=64000)
    supported_operations: tuple[Ref, ...] = ()
    content_contracts: tuple[Ref, ...] = ()
    members: tuple[RevisionRef, ...] = Field(default=(), max_length=100)


class DomainPackageCase(FrozenContract):
    case_id: Ref
    phase: Literal['evaluation', 'trial']
    input_name: Ref
    input_digest: Digest
    expected_result_digest: Digest


class DomainPackagePolicy(FrozenContract):
    """Loaded by server configuration, never accepted as a candidate request."""
    contract_version: Literal['boi/domain-package-policy@1'] = 'boi/domain-package-policy@1'
    team_id: Ref
    version: Ref
    qualification_scope: Literal['reference_checks'] = 'reference_checks'
    allowed_operations: tuple[Ref, ...] = ()
    allowed_content_contracts: tuple[Ref, ...] = ()
    allowed_tool_revisions: tuple[RevisionRef, ...] = ()
    evaluator_executor_ids: tuple[Ref, ...] = Field(min_length=1)
    evaluator_tool_revisions: tuple[RevisionRef, ...] = Field(min_length=1)
    binding_input_name: Ref = 'package_assessment'
    cases: tuple[DomainPackageCase, ...] = Field(min_length=2, max_length=100)
    min_trial_runs: int = Field(default=3, ge=1, le=100)
    max_trial_runs: int = Field(default=20, ge=1, le=100)
    immutable_boundaries: tuple[str, ...] = (
        'authorization', 'source_rights', 'evaluator', 'criteria', 'executable_capabilities',
        'platform_release', 'deployment',
    )

    @model_validator(mode='after')
    def complete_phases(self):
        if {c.phase for c in self.cases} != {'evaluation', 'trial'}:
            raise ValueError('DOMAIN_PACKAGE_POLICY_PHASES_REQUIRED')
        if len({(c.phase, c.case_id) for c in self.cases}) != len(self.cases):
            raise ValueError('DOMAIN_PACKAGE_POLICY_DUPLICATE_CASE')
        if self.min_trial_runs > self.max_trial_runs:
            raise ValueError('DOMAIN_PACKAGE_POLICY_TRIAL_RANGE')
        if self.immutable_boundaries != type(self).model_fields['immutable_boundaries'].default:
            raise ValueError('DOMAIN_PACKAGE_POLICY_BOUNDARIES_IMMUTABLE')
        return self


class DomainPackageObservation(FrozenContract):
    """Signed evaluator output; the server derives pass/fail from result content."""
    contract_version: Literal['boi/domain-package-observation@1'] = 'boi/domain-package-observation@1'
    candidate_revision: RevisionRef
    policy_revision: RevisionRef
    phase: Literal['evaluation', 'trial']
    case_id: Ref
    result: dict
