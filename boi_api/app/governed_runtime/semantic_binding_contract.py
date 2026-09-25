"""Evidence-bound semantic candidates; no execution, approval or truth authority.

These additive runtime contracts deliberately distinguish source preservation,
discovery, proposed meaning and deterministic validation. Physical bindings stay
in the data-mapping profile; this module holds references, never SQL or rows.
"""
from __future__ import annotations

from datetime import datetime
import copy
import hashlib
import json
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Digest = Annotated[str, Field(pattern=r'^sha256:[a-f0-9]{64}$')]
Ref = Annotated[str, StringConstraints(min_length=1, pattern=r'\S')]
SemanticAuthorityBasis = Literal[
    'policy', 'master_data', 'system_of_record', 'steward_review', 'observed', 'source_reported',
]
SEMANTIC_AUTHORITY_BASES = frozenset(get_args(SemanticAuthorityBasis))
SEMANTIC_REQUIRED_CHECKS = (
    'access_snapshot_profile', 'approved_identity_or_scoped_alias',
    'kind_target_role', 'quantity_unit', 'namespace_process_time_version',
    'relationship_grain_mapping', 'source_definition_evidence_use',
    'required_closure_conflicts',
)


def semantic_digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json')
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


def _window(start: datetime | None, end: datetime | None) -> None:
    if any(value is not None and value.utcoffset() is None for value in (start, end)):
        raise ValueError('SEMANTIC_TIME_OFFSET_REQUIRED')
    if end is not None and (start is None or start >= end):
        raise ValueError('SEMANTIC_EFFECTIVE_WINDOW_INVALID')


class SourceRecordRevision(FrozenContract):
    source_system: Ref
    dataset: Ref
    namespace: Ref
    record_key: Ref
    source_revision_digest: Digest
    snapshot_digest: Digest
    artifact_ref: Ref
    artifact_digest: Digest
    captured_at: datetime
    effective_from: datetime | None
    effective_until: datetime | None
    history_coverage: Literal['current_snapshot_only', 'known_revision_history']

    @property
    def identity_digest(self) -> str:
        return semantic_digest({key: getattr(self, key) for key in (
            'source_system', 'dataset', 'namespace', 'record_key')})

    @model_validator(mode='after')
    def temporal_identity(self):
        _window(self.captured_at, None)
        _window(self.effective_from, self.effective_until)
        return self


class RevisionRef(FrozenContract):
    ref: Ref
    revision_digest: Digest


class SemanticScope(FrozenContract):
    namespace: Ref
    process_refs: tuple[Ref, ...]
    equipment_class_refs: tuple[Ref, ...]
    effective_from: datetime | None
    effective_until: datetime | None

    @model_validator(mode='after')
    def scoped_time(self):
        _window(self.effective_from, self.effective_until)
        for refs in (self.process_refs, self.equipment_class_refs):
            if len(refs) != len(set(refs)):
                raise ValueError('SEMANTIC_SCOPE_DUPLICATE')
        return self


def _descriptor_unit_schema(schema):
    # Publish the same unit-binding invariant enforced by unit_contract. Full
    # branches retain every field when providers close additionalProperties.
    declared=copy.deepcopy(schema)
    unbound=copy.deepcopy(schema)
    declared['properties']['unit_semantics']={'type':'string','const':'declared'}
    for key in ('quantity_kind_ref','unit_ref','unit_revision_digest'):
        choices=declared['properties'][key].get('anyOf',[])
        declared['properties'][key]=next(x for x in choices if x.get('type')!='null')
    unbound['properties']['unit_semantics']={'type':'string',
        'enum':['dimensionless','not_applicable','unknown']}
    for key in ('unit_ref','unit_revision_digest'):
        unbound['properties'][key]={'type':'null'}
    schema['anyOf']=[declared,unbound]


class SemanticDescriptor(FrozenContract):
    model_config = ConfigDict(json_schema_extra=_descriptor_unit_schema)
    kind: Literal['Term', 'ObjectType', 'PropertyDefinition', 'RelationType', 'ValueType', 'Metric', 'Rule']
    definition: Ref
    aliases: tuple[Ref, ...]
    target_kind: Ref
    role: Literal['concept', 'entity', 'event', 'observation', 'measurement', 'setpoint', 'upper_limit', 'lower_limit', 'computed', 'rule', 'relationship']
    quantity_kind_ref: Ref | None
    unit_semantics: Literal['declared', 'dimensionless', 'not_applicable', 'unknown'] = Field(
        description='declared requires a quantity reference and a version-pinned unit definition; a source unit label alone is not this binding.')
    unit_ref: Ref | None
    unit_revision_digest: Digest | None
    value_semantics: Literal['absolute', 'interval', 'categorical', 'not_applicable', 'unknown']
    scope: SemanticScope
    conditions: tuple[Ref, ...]
    exceptions: tuple[Ref, ...]
    authority_basis: SemanticAuthorityBasis = Field(description=(
        'Declared provenance of the definition, not an authority grant. source_reported means '
        'the source describes this definition; it does not establish a physical observation, '
        'verified equipment identity, live binding, release qualification or execution permission. '
        'Reading source text does not change source_reported into observed.'))

    @model_validator(mode='after')
    def unit_contract(self):
        if self.unit_semantics == 'declared':
            if not self.unit_ref or not self.unit_revision_digest or not self.quantity_kind_ref:
                raise ValueError('SEMANTIC_UNIT_REVISION_QUANTITY_REQUIRED')
        elif self.unit_ref is not None or self.unit_revision_digest is not None:
            raise ValueError('SEMANTIC_UNDECLARED_UNIT_FORBIDDEN')
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError('SEMANTIC_ALIAS_DUPLICATE')
        # No lowercasing, prefix removal, offset or interval inference.
        return self


class EvidenceUse(FrozenContract):
    span_ref: Ref
    span_digest: Digest
    content_digest: Digest
    record_identity_digest: Digest
    source_revision_digest: Digest
    snapshot_digest: Digest
    field_pointer: Annotated[str, Field(pattern=r'^/')]
    representation: Literal['raw', 'normalized', 'translated', 'extracted']
    transformation_refs: tuple[RevisionRef, ...]
    supports_contract_digest: Digest
    supports_fields: tuple[Ref, ...] = Field(min_length=1)
    use_kind: Literal['source_presence', 'reported_description', 'declared_definition', 'policy', 'physical_observation', 'review']
    support_basis: Literal['presence_only', 'model_proposed', 'approved_structured_contract', 'human_reviewed_interpretation']
    review_receipt_ref: RevisionRef | None

    @model_validator(mode='after')
    def evidence_not_authority(self):
        if self.representation != 'raw' and not self.transformation_refs:
            raise ValueError('EVIDENCE_TRANSFORMATION_CHAIN_REQUIRED')
        if self.support_basis == 'human_reviewed_interpretation' and self.review_receipt_ref is None:
            raise ValueError('EVIDENCE_REVIEW_RECEIPT_REQUIRED')
        if len(self.supports_fields) != len(set(self.supports_fields)):
            raise ValueError('EVIDENCE_SUPPORT_FIELD_DUPLICATE')
        return self


class ConceptLookupClosure(FrozenContract):
    principal_id: Ref
    policy_digest: Digest
    namespace: Ref
    index_revision_digest: Digest
    query_scope_digest: Digest
    profile_closure_digest: Digest
    status: Literal['complete', 'partial', 'failed', 'restricted', 'unknown']
    concept_revision_digests: tuple[Digest, ...]

    @property
    def permits_absence_claim(self) -> bool:
        return self.status == 'complete'

    @model_validator(mode='after')
    def unique_revisions(self):
        if len(self.concept_revision_digests) != len(set(self.concept_revision_digests)):
            raise ValueError('LOOKUP_REVISION_DUPLICATE')
        return self


RelationKind = Literal['synonym', 'related', 'broader', 'narrower', 'concept_reuse', 'target_identity']


class SemanticBindingCandidate(FrozenContract):
    contract_version: Literal['boi/semantic-binding@0.1.0']
    candidate_id: Ref
    source_record: SourceRecordRevision
    target_identity_ref: Ref
    source_semantics: SemanticDescriptor
    relation_kind: RelationKind
    concept_ref: Ref
    concept_revision_digest: Digest
    evidence_uses: tuple[EvidenceUse, ...] = Field(min_length=1)
    dependency_refs: tuple[RevisionRef, ...]
    approved_rule_ref: RevisionRef | None

    @model_validator(mode='after')
    def field_evidence_closure(self):
        if self.source_semantics.scope.namespace != self.source_record.namespace:
            raise ValueError('SEMANTIC_SOURCE_NAMESPACE_MISMATCH')
        for use in self.evidence_uses:
            if (use.record_identity_digest != self.source_record.identity_digest
                or use.source_revision_digest != self.source_record.source_revision_digest
                or use.snapshot_digest != self.source_record.snapshot_digest
                or use.supports_contract_digest != semantic_digest(self.source_semantics)):
                raise ValueError('SEMANTIC_SOURCE_EVIDENCE_CLOSURE_MISMATCH')
        if len({item.ref for item in self.dependency_refs}) != len(self.dependency_refs):
            raise ValueError('SEMANTIC_DEPENDENCY_DUPLICATE')
        return self


class SemanticBindingCheck(FrozenContract):
    check_id: Literal[
        'access_snapshot_profile', 'approved_identity_or_scoped_alias',
        'kind_target_role', 'quantity_unit', 'namespace_process_time_version',
        'relationship_grain_mapping', 'source_definition_evidence_use',
        'required_closure_conflicts',
    ]
    status: Literal['pass', 'fail', 'flag', 'partial', 'skip', 'not_run']
    evidence_digest: Digest | None
    reason_codes: tuple[Ref, ...]

    @model_validator(mode='after')
    def pass_requires_evidence(self):
        if self.status == 'pass' and (self.evidence_digest is None or self.reason_codes):
            raise ValueError('SEMANTIC_PASS_EVIDENCE_REQUIRED')
        return self


class SemanticBindingValidation(FrozenContract):
    contract_version: Literal['boi/semantic-binding-validation@0.1.0']
    candidate_digest: Digest
    principal_id: Ref
    policy_digest: Digest
    validator_code_digest: Digest
    lookup_closure_digest: Digest
    dependency_closure_digest: Digest
    checks: tuple[SemanticBindingCheck, ...]
    status: Literal['VALIDATED', 'ATTENTION_REQUIRED', 'BLOCKED']
    reason_codes: tuple[Ref, ...]
    semantic_truth_proven: Literal[False] = False
    approved: Literal[False] = False
    receipt_digest: Digest

    @model_validator(mode='after')
    def required_check_closure(self):
        if tuple(check.check_id for check in self.checks) != SEMANTIC_REQUIRED_CHECKS:
            raise ValueError('SEMANTIC_REQUIRED_CHECK_CLOSURE_INVALID')
        all_pass = all(check.status == 'pass' for check in self.checks)
        if (self.status == 'VALIDATED') != all_pass:
            raise ValueError('SEMANTIC_REQUIRED_CHECK_NOT_PASSED')
        reasons = tuple(dict.fromkeys(reason for check in self.checks for reason in check.reason_codes))
        if reasons != self.reason_codes:
            raise ValueError('SEMANTIC_REASON_CLOSURE_MISMATCH')
        if self.receipt_digest != semantic_digest(self.model_dump(mode='json', exclude={'receipt_digest'})):
            raise ValueError('SEMANTIC_RECEIPT_DIGEST_MISMATCH')
        return self
