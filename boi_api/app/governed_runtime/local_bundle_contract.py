"""Metadata-only intent for locally prepared data. No source bytes or ACL grants.

The manifest describes proposed data, never installs a pack/checker or certifies
semantic truth. Original object digests stay separate from later native refs.
"""
from typing import Annotated, Literal

from pydantic import Field, model_serializer, model_validator

from .semantic_binding_contract import Digest, FrozenContract, RevisionRef, semantic_digest
from .source_envelope import ArtifactEnvelope
from .task_knowledge import AssetKind
from .knowledge_space_contract import KnowledgeSpaceTarget
from .knowledge_use_purpose import UsePurpose

CHUNK_BYTES = 4 * 1024 * 1024
MAX_OBJECT_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024 * 1024
LocalId = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')]
Label = Annotated[str, Field(min_length=1, max_length=1000)]


class LocalBundleObject(FrozenContract):
    object_id: LocalId
    purpose: Literal['raw_source', 'native_proposal', 'check_evidence']
    display_name: Label
    byte_digest: Digest
    byte_length: int = Field(ge=1, le=MAX_OBJECT_BYTES, strict=True)
    media_type: str = Field(min_length=1, max_length=160)
    source_role: Literal['sql', 'corporate_metadata', 'schema', 'authoritative_document'] | None = None

    @model_validator(mode='after')
    def role_matches(self):
        if (self.purpose == 'raw_source') != (self.source_role is not None):
            raise ValueError('LOCAL_BUNDLE_SOURCE_ROLE_REQUIRED')
        if self.purpose != 'raw_source' and (self.media_type != 'application/json'
                or self.byte_length > 16 * 1024 * 1024):
            raise ValueError('LOCAL_BUNDLE_PROPOSAL_FORMAT_INVALID')
        return self


class LocalKnowledgeCorrection(FrozenContract):
    """Authored explanation bound to the exact content and sharing policy."""
    expected_policy_revision: RevisionRef
    reason: str = Field(min_length=1, max_length=4000)
    source_difference: str = Field(min_length=1, max_length=8000)
    feedback_refs: tuple[RevisionRef, ...] = Field(default=(), max_length=100)

    @model_validator(mode='after')
    def unique_feedback(self):
        if len(set(self.feedback_refs)) != len(self.feedback_refs):
            raise ValueError('KNOWLEDGE_CORRECTION_DUPLICATE_FEEDBACK')
        return self

    @model_serializer(mode='wrap')
    def preserve_existing_wire(self, handler):
        value = handler(self)
        if not self.feedback_refs:
            value.pop('feedback_refs', None)
        return value


class LocalBundleChange(FrozenContract):
    object_id: LocalId
    namespace: Label
    logical_id: Label
    kind: AssetKind
    title: Label
    summary: str = Field(min_length=1, max_length=4000)
    operation: Literal['create', 'revise']
    previous_revision: RevisionRef | None = None
    correction: LocalKnowledgeCorrection | None = None
    observation_contract: Literal["boi/native-definition-review@1"] | None = None

    @model_serializer(mode='wrap')
    def preserve_existing_wire(self, handler):
        value = handler(self)
        if self.correction is None:
            value.pop('correction', None)
        if self.observation_contract is None:
            value.pop('observation_contract', None)
        return value

    @model_validator(mode='after')
    def basis_matches(self):
        if (self.operation == 'revise') != (self.previous_revision is not None):
            raise ValueError('LOCAL_BUNDLE_CHANGE_BASIS_REQUIRED')
        if self.correction is not None and self.operation != 'revise':
            raise ValueError('LOCAL_BUNDLE_CORRECTION_REQUIRES_PREVIOUS_REVISION')
        # Uploading data must not install executable tools or external-agent skills.
        if self.observation_contract is not None and self.kind != 'pack':
            raise ValueError('LOCAL_BUNDLE_REVIEW_PACK_REQUIRED')
        if self.kind not in ('definition', 'profile') and not (self.kind == 'pack' and self.observation_contract):
            raise ValueError('LOCAL_BUNDLE_EXECUTABLE_ADOPTION_NOT_SUPPORTED')
        return self


class LocalReferenceBinding(FrozenContract):
    """Only declared JSON pointer positions may be rewritten during native import."""
    object_id: LocalId
    pointer: str = Field(pattern=r'^/', max_length=2048)
    placeholder: str = Field(min_length=1, max_length=160)
    target_object_id: LocalId
    kind: Literal['artifact_envelope', 'knowledge_revision', 'knowledge_identity', 'source_span', 'source_revision_digest']
    field_locator: str | None = Field(default=None, max_length=4096)

    @model_validator(mode='after')
    def locator_matches(self):
        if (self.kind in ('source_span', 'source_revision_digest')) != (self.field_locator is not None):
            raise ValueError('LOCAL_BUNDLE_FIELD_LOCATOR_REQUIRED')
        return self


class LocalPublicationLayout(FrozenContract):
    """Declared indivisible changes; the server plans dependencies before consent."""
    mode: Literal['dependency_units'] = 'dependency_units'
    maximum_unit_changes: int = Field(default=50,ge=1,le=100,strict=True)
    co_publish_groups: tuple[tuple[LocalId,...],...] = Field(default=(),max_length=500)


class LocalBundleManifest(FrozenContract):
    delivery_recipient: Literal["development_default"] | None = None
    contract_version: Literal['boi/local-bundle-manifest@1','boi/local-bundle-manifest@2'] = 'boi/local-bundle-manifest@1'
    publication_layout: LocalPublicationLayout | None = None
    title: Label
    description: str = Field(min_length=1, max_length=8000)
    target_space: KnowledgeSpaceTarget = Field(default_factory=KnowledgeSpaceTarget)
    objects: tuple[LocalBundleObject, ...] = Field(min_length=1, max_length=1100)
    changes: tuple[LocalBundleChange, ...] = Field(min_length=1, max_length=500)
    references: tuple[LocalReferenceBinding, ...] = Field(default=(), max_length=10000)
    existing_sources: tuple[ArtifactEnvelope, ...] = Field(default=(), max_length=100)
    existing_revisions: tuple[RevisionRef, ...] = Field(default=(), max_length=500)
    # Content access and scoped meaning uses are distinct. Older manifests keep
    # their exact bytes: `read` never silently opts into `explain`, and `compute`
    # never opts into Formula input. A local assessment must name its purpose
    # here explicitly before the exact manifest can be confirmed.
    intended_uses: tuple[Literal['read', 'compute'] | UsePurpose, ...] = Field(min_length=1, max_length=8)
    unresolved: tuple[Label, ...] = Field(default=(), max_length=100)

    @property
    def digest(self):
        return semantic_digest(self)

    @model_validator(mode='after')
    def bounded_closed_manifest(self):
        if self.delivery_recipient is not None:
            if self.target_space.visibility != 'private':
                raise ValueError('DELIVERY_RECIPIENT_PRIVATE_DESTINATION_REQUIRED')
            if any(change.operation != 'create' or change.previous_revision is not None for change in self.changes):
                raise ValueError('DELIVERY_RECIPIENT_NEW_OUTPUT_ONLY')
        if self.contract_version.endswith('@1') and self.publication_layout is not None:
            raise ValueError('LOCAL_BUNDLE_LAYOUT_REQUIRES_V2')
        if self.contract_version.endswith('@2') and self.publication_layout is None:
            raise ValueError('LOCAL_BUNDLE_PUBLICATION_LAYOUT_REQUIRED')
        objects = {item.object_id: item for item in self.objects}
        if len(objects) != len(self.objects) or sum(x.byte_length for x in self.objects) > MAX_BUNDLE_BYTES:
            raise ValueError('LOCAL_BUNDLE_OBJECT_SET_INVALID')
        if len([x for x in self.objects if x.purpose == 'raw_source']) + len(self.existing_sources) > 100:
            raise ValueError('LOCAL_BUNDLE_SOURCE_COUNT_LIMIT')
        if not self.existing_sources and not any(x.purpose == 'raw_source' for x in self.objects):
            raise ValueError('LOCAL_BUNDLE_SOURCE_REQUIRED')
        if (len({(x.namespace, x.logical_id) for x in self.changes}) != len(self.changes)
                or len({x.namespace for x in self.changes}) > 32
                or {x.object_id for x in self.changes} != {
                    x.object_id for x in self.objects if x.purpose == 'native_proposal'}
                or len({x.object_id for x in self.changes}) != len(self.changes)):
            raise ValueError('LOCAL_BUNDLE_CHANGE_SET_INVALID')
        if len(set(self.intended_uses)) != len(self.intended_uses):
            raise ValueError('LOCAL_BUNDLE_DUPLICATE_USE')
        if self.publication_layout:
            members=set()
            for group in self.publication_layout.co_publish_groups:
                if not 1<=len(group)<=500 or len(set(group))!=len(group):
                    raise ValueError('LOCAL_BUNDLE_ATOMIC_GROUP_INVALID')
                if any(x not in {c.object_id for c in self.changes} or x in members for x in group):
                    raise ValueError('LOCAL_BUNDLE_ATOMIC_GROUP_MEMBERS_INVALID')
                members.update(group)
        if len({(x.object_id, x.pointer) for x in self.references}) != len(self.references):
            raise ValueError('LOCAL_BUNDLE_DUPLICATE_REFERENCE_POSITION')
        dependencies = {x.object_id: set() for x in self.changes}
        for binding in self.references:
            target = objects.get(binding.target_object_id)
            if binding.object_id not in dependencies or target is None:
                raise ValueError('LOCAL_BUNDLE_REFERENCE_OBJECT_UNKNOWN')
            if binding.kind == 'knowledge_identity' and self.contract_version.endswith('@1'):
                raise ValueError('LOCAL_BUNDLE_IDENTITY_REFERENCE_REQUIRES_V2')
            expected = 'native_proposal' if binding.kind in ('knowledge_revision','knowledge_identity') else 'raw_source'
            if target.purpose != expected:
                raise ValueError('LOCAL_BUNDLE_REFERENCE_KIND_MISMATCH')
            if binding.kind == 'knowledge_revision':
                dependencies[binding.object_id].add(binding.target_object_id)
        # This is the import dependency DAG, not the domain relationship graph.
        done = set()
        while len(done) < len(dependencies):
            ready = {key for key, deps in dependencies.items() if key not in done and deps <= done}
            if not ready:
                raise ValueError('LOCAL_BUNDLE_REFERENCE_DEPENDENCY_CYCLE')
            done.update(ready)
        return self

    @model_serializer(mode='wrap')
    def preserve_v1_bytes(self, handler):
        value=handler(self)
        if self.delivery_recipient is None:
            value.pop('delivery_recipient', None)
        if self.contract_version.endswith('@1'):
            value.pop('publication_layout',None)
        return value


class LocalBundlePreviewRequest(FrozenContract):
    contract_version: Literal['boi/local-publication@1'] = 'boi/local-publication@1'
    manifest: LocalBundleManifest
    idempotency_key: str = Field(min_length=1, max_length=240)


class LocalBundleReadRequest(FrozenContract):
    bundle_ref: str = Field(pattern=r'^local-bundle:sha256:[0-9a-f]{64}$')


class LocalBundleChallengeRequest(LocalBundleReadRequest):
    impact_ref: str | None = Field(default=None,pattern=r'^local-bundle-impact:sha256:[0-9a-f]{64}$')


class LocalBundleListRequest(FrozenContract):
    after_key: str = Field(default='', pattern=r'^(|local-bundle:sha256:[0-9a-f]{64})$')
    limit: int = Field(default=20, ge=1, le=100, strict=True)


class LocalBundleConfirmRequest(LocalBundleChallengeRequest):
    manifest_digest: Digest
    preview_digest: Digest
    nonce: str = Field(min_length=32, max_length=160)


class LocalBundleHotlImpactRequest(LocalBundleReadRequest):
    preview_digest: Digest


class LocalBundleHotlAdmitRequest(LocalBundleHotlImpactRequest):
    manifest_digest: Digest
    impact_ref: str | None = Field(default=None, pattern=r'^local-bundle-impact:sha256:[0-9a-f]{64}$')


class LocalPublicationRequest(FrozenContract):
    contract_version: Literal['boi/local-publication@1'] = 'boi/local-publication@1'
    phase: Literal['preview', 'status', 'stop', 'schema', 'list', 'prepare', 'validate', 'qualify', 'qualification_status',
        'preflight', 'publish', 'publication_resume', 'impact', 'admit']
    payload: dict = Field(default_factory=dict)


class LocalBundlePrepareRequest(LocalBundleReadRequest):
    limit: int = Field(default=1, ge=1, le=10, strict=True)


class LocalBundleUnitRequest(LocalBundleReadRequest):
    unit_id: str = Field(min_length=1, max_length=240)


class LocalBundlePublishRequest(LocalBundleUnitRequest):
    publication_digest: Digest


class LocalBundleValidateRequest(LocalBundlePrepareRequest):
    object_id: LocalId | None = None


class LocalUseSupersession(FrozenContract):
    """An exact predecessor, not permission to overwrite any current decision."""
    purpose: Literal['explain', 'compare', 'filter', 'aggregate', 'formula_input', 'traverse']
    qualification_ref: RevisionRef
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode='after')
    def reason_required(self):
        if not self.reason.strip():
            raise ValueError('KNOWLEDGE_USE_SUPERSESSION_REASON_REQUIRED')
        return self


class LocalBundleAssessmentReadRequest(LocalBundleReadRequest):
    assessment_object_id: LocalId


class LocalBundleQualifyRequest(LocalBundleAssessmentReadRequest):
    supersedes: tuple[LocalUseSupersession, ...] = Field(default=(), max_length=6)

    @model_validator(mode='after')
    def unique_predecessors(self):
        if len({item.purpose for item in self.supersedes}) != len(self.supersedes):
            raise ValueError('KNOWLEDGE_USE_SUPERSESSION_DUPLICATE_PURPOSE')
        return self
