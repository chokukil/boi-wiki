"""External-agent assetization over the existing task and source contracts."""
from typing import Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import FrozenContract, Ref, RevisionRef
from .source_envelope import ArtifactEnvelope


class KnowledgeSourceRevision(FrozenContract):
    previous_artifact_ref: Ref
    artifact_ref: Ref


class KnowledgeWorkStart(FrozenContract):
    request_text: str = Field(min_length=1, max_length=12000)
    sources: tuple[ArtifactEnvelope, ...] = Field(min_length=1, max_length=100)
    package_ids: tuple[Ref, ...] = ('common',)
    team_id: Ref | None = None
    idempotency_key: str = Field(min_length=1, max_length=240)
    # This explicitly links a new source revision; no filename identity inference.
    previous_task_ref: Ref | None = None
    source_revisions: tuple[KnowledgeSourceRevision, ...] = Field(default=(), max_length=100)


class KnowledgeWorkRead(FrozenContract):
    task_ref: Ref


class KnowledgeWorkNext(KnowledgeWorkRead):
    expected_revision: int = Field(ge=1, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=240)


class KnowledgeChange(FrozenContract):
    change_id: Ref
    operation: Literal['reuse', 'create', 'revise', 'conflict', 'unresolved']
    reason: str = Field(min_length=1, max_length=8000)
    target_revision: RevisionRef | None = None
    title: str = Field(default='', max_length=1000)
    description: str = Field(default='', max_length=8000)
    content: dict | None = None
    retain_target_content: bool = Field(default=False, strict=True,
        description='For a title/description-only revision, retain the exact authorized target content, evidence and dependencies on the server. Do not supply replacement content, evidence or dependencies.')
    evidence_spans: tuple[RevisionRef, ...] = Field(default=(), max_length=256)
    dependencies: tuple[RevisionRef, ...] = Field(default=(), max_length=100)

    @model_validator(mode='after')
    def coherent(self):
        if self.operation in ('reuse', 'revise', 'conflict') and self.target_revision is None:
            raise ValueError('KNOWLEDGE_CHANGE_TARGET_REQUIRED')
        if self.retain_target_content:
            if self.operation != 'revise' or not self.title or not self.description:
                raise ValueError('KNOWLEDGE_CHANGE_RETAIN_REQUIRES_DESCRIPTION_REVISION')
            if self.content is not None or self.evidence_spans or self.dependencies:
                raise ValueError('KNOWLEDGE_CHANGE_RETAIN_REPLACEMENT_UNEXPECTED')
            return self
        if self.operation in ('create', 'revise', 'conflict'):
            if not self.content or not self.title or not self.description or not self.evidence_spans:
                raise ValueError('KNOWLEDGE_CHANGE_CONTENT_AND_EVIDENCE_REQUIRED')
        elif self.content is not None:
            raise ValueError('KNOWLEDGE_CHANGE_CONTENT_UNEXPECTED')
        if self.operation == 'create' and self.target_revision is not None:
            raise ValueError('KNOWLEDGE_CHANGE_NEW_TARGET_UNEXPECTED')
        return self


class KnowledgeRecordOutcome(FrozenContract):
    record_locator: str
    disposition: Literal['assetized','context_only','unresolved']
    change_ids: tuple[Ref, ...] = ()
    reason: Ref


class KnowledgeRevisionScope(FrozenContract):
    # This is an external interpretation's dependency declaration, not a pass.
    basis: Literal['whole_source', 'declared_records'] = 'whole_source'
    order_sensitive: bool = True
    context_spans: tuple[RevisionRef, ...] = Field(default=(), max_length=256)


class KnowledgeRevisionImpactReview(FrozenContract):
    disposition: Literal['reviewed', 'unresolved']
    reason: Ref


class KnowledgeWorkResult(FrozenContract):
    # A provider report is not a server or independent semantic verdict.
    outcome: Literal['produced', 'failed', 'unknown', 'unresolved']
    summary: str = Field(min_length=1, max_length=12000)
    changes: tuple[KnowledgeChange, ...] = Field(default=(), max_length=100)
    existing_revisions_considered: tuple[RevisionRef, ...] = Field(default=(), max_length=100)
    unresolved: tuple[str, ...] = Field(default=(), max_length=100)
    record_outcomes: tuple[KnowledgeRecordOutcome, ...] = Field(default=(), max_length=256)
    revision_scope: KnowledgeRevisionScope = Field(default_factory=KnowledgeRevisionScope)
    revision_impact_review: KnowledgeRevisionImpactReview | None = None

    @model_validator(mode='after')
    def unique_changes(self):
        if len({v.change_id for v in self.changes}) != len(self.changes):
            raise ValueError('KNOWLEDGE_CHANGE_ID_DUPLICATE')
        if self.outcome != 'produced' and self.changes:
            raise ValueError('KNOWLEDGE_FAILED_RESULT_CANNOT_PUBLISH')
        return self


class KnowledgeWorkSubmit(KnowledgeWorkRead):
    attempt_ref: Ref
    idempotency_key: str = Field(min_length=1, max_length=240)
    result: KnowledgeWorkResult
    raw_output: str = Field(min_length=1, max_length=524288)


class KnowledgeWorkReconcile(KnowledgeWorkSubmit):
    expected_revision: int = Field(ge=1, strict=True)
    recovery_reason: str = Field(min_length=1, max_length=8000)


class KnowledgeWorkControl(KnowledgeWorkRead):
    expected_revision: int = Field(ge=1, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=8000)


class KnowledgeWorkContext(KnowledgeWorkNext):
    attempt_ref: Ref
    revisions: tuple[RevisionRef, ...] = Field(min_length=1, max_length=100)


class KnowledgeWorkOutput(KnowledgeWorkRead):
    attempt_ref: Ref
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=8192, ge=1, le=8192, strict=True)


class KnowledgeWorkRequest(FrozenContract):
    delivery_recipient: Literal["development_default"] | None = None
    operation: Literal['start', 'status', 'resume', 'next', 'context', 'output', 'submit', 'reconcile', 'retry', 'stop', 'list', 'schema', 'publication']
    request: dict = Field(default_factory=dict)
    context_view: Literal['references', 'full'] = 'references'


def result_payload(result):
    """Additive defaults must not change fingerprints of historical submissions."""
    data = result.model_dump(mode='json')
    for change in data['changes']:
        if not change['retain_target_content']:
            change.pop('retain_target_content')
    if data['revision_scope'] == KnowledgeRevisionScope().model_dump(mode='json'):
        data.pop('revision_scope')
    if data['revision_impact_review'] is None:
        data.pop('revision_impact_review')
    return data
