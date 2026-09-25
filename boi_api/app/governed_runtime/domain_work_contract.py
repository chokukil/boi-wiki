"""External domain work stages, not a Wiki workflow interpreter or scheduler."""
from typing import Annotated, Literal
import json

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef
from .source_envelope import ArtifactEnvelope
from .tool_execution_contract import SignedToolExecution


CheckStatus = Literal['pass','fail','unknown','not_applicable']


class RequiredToolCheck(FrozenContract):
    check_id: Ref
    accepted_statuses: tuple[CheckStatus, ...] = Field(min_length=1)


class StageToolRequirement(FrozenContract):
    tool_revision: RevisionRef
    input_names: tuple[Ref, ...] = Field(min_length=1)
    input_kinds: dict[Ref,Literal['source','asset','source_projection','source_projection_bundle','proposal','context','knowledge_reading']] = Field(default_factory=dict,
        description='Origin of every named input, including server-supplied context. Empty is legacy unspecified; it is not trusted source-origin qualification.')
    checks: tuple[RequiredToolCheck, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def no_duplicates(self):
        if len(set(self.input_names)) != len(self.input_names) or len({c.check_id for c in self.checks}) != len(self.checks):
            raise ValueError('DOMAIN_STAGE_TOOL_REQUIREMENT_AMBIGUOUS')
        if self.input_kinds and (set(self.input_kinds)!=set(self.input_names)
                or any((name=='context')!=(kind=='context') for name,kind in self.input_kinds.items())):
            raise ValueError('DOMAIN_STAGE_INPUT_ORIGINS_INCOMPLETE')
        return self


class DomainHarnessStage(FrozenContract):
    stage_id: Ref
    purpose: Ref
    instructions: Ref
    tools: tuple[StageToolRequirement, ...] = Field(min_length=1,max_length=20)

    @model_validator(mode='after')
    def no_duplicates(self):
        if len({t.tool_revision for t in self.tools}) != len(self.tools):
            raise ValueError('DOMAIN_STAGE_TOOL_DUPLICATE')
        return self


class DomainHarnessContract(FrozenContract):
    contract_version: Literal['boi/domain-harness@1'] = 'boi/domain-harness@1'
    namespace: Ref
    title: Ref
    purpose: Ref
    stages: tuple[DomainHarnessStage, ...] = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def no_duplicates(self):
        if len({s.stage_id for s in self.stages}) != len(self.stages):
            raise ValueError('DOMAIN_HARNESS_STAGE_DUPLICATE')
        return self


class SourceWorkInput(FrozenContract):
    kind: Literal['source'] = 'source'
    name: Ref
    source: ArtifactEnvelope


class AssetWorkInput(FrozenContract):
    kind: Literal['asset'] = 'asset'
    name: Ref
    revision: RevisionRef


class ProjectionWorkInput(FrozenContract):
    kind: Literal['source_projection'] = 'source_projection'
    name: Ref
    source: ArtifactEnvelope
    manifest_revision: RevisionRef


class ProjectionReference(FrozenContract):
    source: ArtifactEnvelope
    manifest_revision: RevisionRef


class ProjectionBundleWorkInput(FrozenContract):
    kind: Literal['source_projection_bundle'] = 'source_projection_bundle'
    name: Ref
    projections: tuple[ProjectionReference,...] = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def unique_sources(self):
        if len({p.source.artifact_ref for p in self.projections})!=len(self.projections):
            raise ValueError('DOMAIN_WORK_PROJECTION_BUNDLE_DUPLICATE_SOURCE')
        return self


class ProposedWorkInput(FrozenContract):
    """Untrusted generated JSON pinned in the task contract, not a definition.

    Requiring a new extraction to already belong to the context it was derived
    from would create a digest cycle. This input retains that context unchanged.
    """
    kind: Literal['proposal'] = 'proposal'
    name: Ref
    content_json: str = Field(min_length=1,max_length=131072)

    @model_validator(mode='after')
    def valid_json(self):
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('DOMAIN_WORK_PROPOSAL_DUPLICATE_KEY')
                result[key]=value
            return result
        def invalid(value):raise ValueError('DOMAIN_WORK_PROPOSAL_NONFINITE_NUMBER')
        json.loads(self.content_json,object_pairs_hook=unique,parse_constant=invalid)
        return self


class KnowledgeReadingWorkInput(FrozenContract):
    kind: Literal['knowledge_reading']='knowledge_reading'
    name: Ref
    reading_ref: RevisionRef


WorkInput = Annotated[SourceWorkInput | AssetWorkInput | ProjectionWorkInput | ProjectionBundleWorkInput | ProposedWorkInput | KnowledgeReadingWorkInput,Field(discriminator='kind')]


class DomainRequestStageBudget(FrozenContract):
    """Operator-pinned request scope, stored as a Wiki pack before work starts.

    This counts admitted stage tasks, not provider calls or semantic success.
    Exact inputs, revisions and review contracts remain in each task contract.
    """
    contract_version: Literal['boi/request-stage-budget@1'] = 'boi/request-stage-budget@1'
    request_text: Ref
    max_stage_attempts: int = Field(ge=1, le=20, strict=True)


class DomainWorkStartRequest(FrozenContract):
    harness_revision: RevisionRef
    stage_id: Ref
    sources: tuple[ArtifactEnvelope, ...] = Field(min_length=1,max_length=100)
    reading_ref: RevisionRef
    inputs: tuple[WorkInput, ...] = Field(max_length=100)
    idempotency_key: str = Field(min_length=1,max_length=240)
    request_revision: RevisionRef | None = None


class DomainWorkLookupRequest(FrozenContract):
    idempotency_key: str = Field(min_length=1,max_length=240)


class DomainToolPrepareRequest(FrozenContract):
    task_package_id: Ref
    expected_revision: int = Field(ge=1,strict=True)
    lease_id: Ref
    tool_revision: RevisionRef
    idempotency_key: str = Field(min_length=1,max_length=240)


class DomainToolReadRequest(FrozenContract):
    invocation_id: Ref


class DomainToolLookupRequest(FrozenContract):
    task_package_id: Ref
    tool_revision: RevisionRef


class DomainToolDispatchRequest(DomainToolReadRequest):
    """Acquire once; retrying a delivered or lost response never grants again."""


class DomainToolInputRequest(DomainToolReadRequest):
    name: Ref


class DomainToolEvidenceRequest(FrozenContract):
    execution_ref: RevisionRef


class DomainToolSubmitRequest(FrozenContract):
    receipt: SignedToolExecution
    output_b64: str = Field(max_length=1_048_576)


class ToolCheckObservation(FrozenContract):
    check_id: Ref
    status: CheckStatus
    subject_ref: Ref
    reason_code: Ref
    evidence_refs: tuple[Ref, ...] = ()


class DomainToolReport(FrozenContract):
    contract_version: Literal['boi/domain-tool-report@1'] = 'boi/domain-tool-report@1'
    checks: tuple[ToolCheckObservation, ...] = Field(min_length=1)
    result: dict

    @model_validator(mode='after')
    def no_duplicates(self):
        if len({c.check_id for c in self.checks}) != len(self.checks):
            raise ValueError('DOMAIN_TOOL_CHECK_DUPLICATE')
        return self


class DomainWorkCompleteRequest(FrozenContract):
    task_package_id: Ref
    expected_revision: int = Field(ge=1,strict=True)
    lease_id: Ref
    execution_refs: tuple[RevisionRef, ...] = Field(min_length=1,max_length=20)
    summary: Ref
    idempotency_key: str = Field(min_length=1,max_length=240)
