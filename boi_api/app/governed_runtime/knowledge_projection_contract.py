"""Internal, typed inputs to the disposable knowledge projection.

These are adapter outputs, not public authoring or qualification requests.
Native revisions and the server's admission callback remain authoritative.
"""
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, StrictBool, StrictStr, model_serializer, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest


class ProjectionContract(FrozenContract):
    model_config = ConfigDict(hide_input_in_errors=True)


class ProjectionRevision(RevisionRef):
    @model_validator(mode='after')
    def exact_revision(self):
        if self.ref != 'KnowledgeRevision:' + self.revision_digest:
            raise ValueError('PROJECTION_KNOWLEDGE_REVISION_INVALID')
        return self


class ProjectionComponent(ProjectionContract):
    """A version-pinned definition inside one native Profile; no self hash cycle."""
    revision: ProjectionRevision
    pointer: str = Field(min_length=1, max_length=2048, pattern=r'^/')


DefinitionReference = ProjectionRevision | ProjectionComponent


def definition_key(reference: DefinitionReference):
    return reference.revision.ref + '#' + reference.pointer if isinstance(reference, ProjectionComponent) else reference.ref


class ProjectionScalar(ProjectionContract):
    kind: Literal['text', 'decimal', 'boolean', 'object']
    value: StrictStr | StrictBool

    @model_validator(mode='after')
    def exact_value(self):
        if self.kind == 'boolean':
            if type(self.value) is not bool:
                raise ValueError('PROJECTION_BOOLEAN_REQUIRED')
        elif not isinstance(self.value, str):
            raise ValueError('PROJECTION_TEXT_ENCODING_REQUIRED')
        elif len(self.value) > 32000:
            raise ValueError('PROJECTION_VALUE_LIMIT')
        elif self.kind == 'object' and not self.value.strip():
            raise ValueError('PROJECTION_OBJECT_ID_REQUIRED')
        elif self.kind == 'decimal':
            # Exact numeric collation uses decimal strings, never binary floats.
            try:
                number = Decimal(self.value)
            except InvalidOperation:
                raise ValueError('PROJECTION_DECIMAL_INVALID') from None
            if (not number.is_finite() or len(number.as_tuple().digits) > 64
                    or abs(number.as_tuple().exponent) > 1024 or len(self.value) > 128
                    or self.value.strip() != self.value or '_' in self.value):
                raise ValueError('PROJECTION_DECIMAL_INVALID')
        return self


class ProjectionPredicate(ProjectionContract):
    revision: DefinitionReference
    subject_type: DefinitionReference
    value_kind: Literal['text', 'decimal', 'boolean', 'object']
    target_type: DefinitionReference | None = None
    unit_revision: DefinitionReference | None = None
    quantity_revision: DefinitionReference | None = None
    quantity_semantics: Literal['not_applicable', 'dimensionless', 'declared', 'unknown']

    @model_validator(mode='after')
    def value_contract(self):
        if (self.value_kind == 'object') != (self.target_type is not None):
            raise ValueError('PROJECTION_RELATION_TARGET_TYPE_REQUIRED')
        if self.quantity_semantics == 'declared':
            if self.value_kind != 'decimal' or self.unit_revision is None or self.quantity_revision is None:
                raise ValueError('PROJECTION_QUANTITY_BINDING_REQUIRED')
        elif self.unit_revision is not None or self.quantity_revision is not None:
            raise ValueError('PROJECTION_UNDECLARED_QUANTITY_BINDING')
        if self.value_kind != 'decimal' and self.quantity_semantics != 'not_applicable':
            raise ValueError('PROJECTION_NONNUMERIC_QUANTITY')
        if self.value_kind == 'decimal' and self.quantity_semantics == 'not_applicable':
            raise ValueError('PROJECTION_NUMERIC_QUANTITY_REQUIRED')
        return self


class ProjectionFact(ProjectionContract):
    fact_id: Ref
    meaning_pointer: str = Field(max_length=2048)
    predicate_revision: DefinitionReference
    value: ProjectionScalar
    polarity: Literal['positive', 'negative']
    modality: Literal['asserted', 'possible', 'intended', 'required']
    # Conditions and time stay intact. Exact-value lookup is candidate retrieval;
    # the query adapter must still evaluate these under the requested context.
    qualifiers: dict[str, JsonValue] = Field(default_factory=dict)
    valid_time: dict[str, JsonValue]
    evidence_bindings: tuple[dict[str, JsonValue], ...] = Field(min_length=1, max_length=256)
    unresolved: tuple[Ref, ...] = Field(default=(), max_length=256)


class ProjectionObject(ProjectionContract):
    stable_id: Ref
    object_type: DefinitionReference
    knowledge_revision: ProjectionRevision
    content_digest: Digest
    adapter_revision: Ref
    title: str = Field(min_length=1, max_length=2000)
    body: str = Field(max_length=512000)
    source_record_locator: Ref
    readiness: Literal['unprepared', 'interpreted', 'source_bound', 'query_ready']
    unresolved: tuple[Ref, ...] = Field(default=(), max_length=256)
    facts: tuple[ProjectionFact, ...] = Field(default=(), max_length=2000)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_facts(self):
        if len({f.fact_id for f in self.facts}) != len(self.facts):
            raise ValueError('PROJECTION_FACT_ID_DUPLICATE')
        if self.readiness == 'unprepared' and self.facts:
            raise ValueError('PROJECTION_UNPREPARED_FACTS_UNEXPECTED')
        return self


class PublicationChange(ProjectionContract):
    stable_id: Ref
    operation: Literal['upsert', 'delete']
    previous_revision: ProjectionRevision | None
    revision: ProjectionRevision | None

    @model_validator(mode='after')
    def change_shape(self):
        if (self.operation == 'upsert') != (self.revision is not None):
            raise ValueError('PROJECTION_CHANGE_REVISION_INVALID')
        if self.operation == 'delete' and self.previous_revision is None:
            raise ValueError('PROJECTION_DELETE_PREVIOUS_REQUIRED')
        return self


class ProjectionPublication(ProjectionContract):
    contract_version: Literal['boi/knowledge-projection-publication@1', 'boi/knowledge-projection-publication@2'] = 'boi/knowledge-projection-publication@1'
    projection_mode: Literal['incremental', 'bootstrap'] | None = None
    scope_id: Ref
    principal_id: Ref
    base_generation: int = Field(ge=0, strict=True)
    policy_digest: Digest
    confirmation_ref: Ref
    source_manifest_digest: Digest
    adapter_revision: Ref
    changes: tuple[PublicationChange, ...] = Field(min_length=1, max_length=500)
    qualification_refs: tuple[RevisionRef, ...] = Field(default=(), max_length=1000)

    @model_validator(mode='after')
    def unique_changes(self):
        if self.contract_version.endswith('@1') and self.projection_mode is not None:
            raise ValueError('PROJECTION_MODE_REQUIRES_V2')
        if self.contract_version.endswith('@2') and self.projection_mode is None:
            raise ValueError('PROJECTION_MODE_REQUIRED')
        if self.projection_mode == 'bootstrap' and self.base_generation != 0:
            raise ValueError('PROJECTION_BOOTSTRAP_BASE_INVALID')
        if len({c.stable_id for c in self.changes}) != len(self.changes):
            raise ValueError('PROJECTION_CHANGE_DUPLICATE')
        return self

    @property
    def digest(self):
        # Preserve every previously recorded v1 operation digest during decoding.
        return semantic_digest(self.model_dump(mode='json'))

    @model_serializer(mode='wrap')
    def original_v1_wire(self, handler):
        value = handler(self)
        if self.contract_version.endswith('@1'):
            value.pop('projection_mode', None)
        return value


class ProjectionBatch(ProjectionContract):
    manifest_digest: Digest
    objects: tuple[ProjectionObject, ...] = Field(default=(), max_length=500)
    predicates: tuple[ProjectionPredicate, ...] = Field(default=(), max_length=1000)

    @model_validator(mode='after')
    def declarations(self):
        if len({o.stable_id for o in self.objects}) != len(self.objects):
            raise ValueError('PROJECTION_OBJECT_DUPLICATE')
        definitions = {p.revision: p for p in self.predicates}
        if len(definitions) != len(self.predicates):
            raise ValueError('PROJECTION_PREDICATE_DUPLICATE')
        if sum(len(o.facts) for o in self.objects) > 100000:
            raise ValueError('PROJECTION_BATCH_FACT_LIMIT')
        for obj in self.objects:
            for fact in obj.facts:
                predicate = definitions.get(fact.predicate_revision)
                if predicate is None:
                    raise ValueError('PROJECTION_PREDICATE_MISSING')
                if predicate.subject_type != obj.object_type or predicate.value_kind != fact.value.kind:
                    raise ValueError('PROJECTION_PREDICATE_TYPE_MISMATCH')
        return self

    def validate_manifest(self, manifest: ProjectionPublication):
        if self.manifest_digest != manifest.digest:
            raise ValueError('PROJECTION_MANIFEST_MISMATCH')
        expected = {c.stable_id: c.revision for c in manifest.changes if c.operation == 'upsert'}
        if {o.stable_id: o.knowledge_revision for o in self.objects} != expected:
            raise ValueError('PROJECTION_OBJECT_SET_MISMATCH')
        if any(o.adapter_revision != manifest.adapter_revision for o in self.objects):
            raise ValueError('PROJECTION_ADAPTER_MISMATCH')
