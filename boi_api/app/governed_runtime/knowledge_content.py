"""One native revision for an OKF document and its declared meaning.

Validation here is structural and evidence-address checking. It does not judge
source fidelity, register a checker, or qualify a revision for execution.
Unknown extension data survives in the original content_json unchanged.
"""
from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, model_serializer, model_validator

from .okf_core import validate_okf_v02_core
from .knowledge_use_purpose import UsePurpose
from .knowledge_statement_contract import UnresolvedFacet
from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef


class ContentContract(FrozenContract):
    model_config = ConfigDict(hide_input_in_errors=True)


def meaning_pointer(value: dict, pointer: str):
    """Resolve an exact RFC 6901 address, with no labels or fuzzy fallback."""
    if pointer == '':
        return value
    if not pointer.startswith('/') or len(pointer) > 2048:
        raise ValueError('KNOWLEDGE_CONTENT_POINTER_INVALID')
    current = value
    for raw in pointer[1:].split('/'):
        index = 0
        while index < len(raw):
            if raw[index] == '~':
                if index + 1 == len(raw) or raw[index + 1] not in '01':
                    raise ValueError('KNOWLEDGE_CONTENT_POINTER_INVALID')
                index += 1
            index += 1
        key = raw.replace('~1', '/').replace('~0', '~')
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif (isinstance(current, list) and key.isascii() and key.isdigit()
              and str(int(key)) == key and int(key) < len(current)):
            current = current[int(key)]
        else:
            raise ValueError('KNOWLEDGE_CONTENT_POINTER_MISSING')
    return current


class KnowledgeDocument(ContentContract):
    frontmatter: dict[str, JsonValue]
    body: str = Field(min_length=1, max_length=512000, pattern=r'\S')

    @model_validator(mode='after')
    def compatible_core(self):
        if self.frontmatter.get('okf_version') != '0.2':
            raise ValueError('KNOWLEDGE_CONTENT_OKF_VERSION_REQUIRED')
        if not validate_okf_v02_core(self.frontmatter).ok:
            raise ValueError('KNOWLEDGE_CONTENT_OKF_CORE_INVALID')
        return self


class ProfileLevel(ContentContract):
    scheme: Ref
    version: Ref
    value: Ref


class ContentProfile(ContentContract):
    profile_id: Ref
    schema_ref: Ref
    revision: RevisionRef
    level: ProfileLevel | None = None


class BodyMeaningBinding(ContentContract):
    meaning_pointer: str = Field(max_length=2048)
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=512000)
    assertion_kind: Literal['source_reported', 'interpretation', 'derived', 'recommendation']


class ContentEvidenceBinding(ContentContract):
    meaning_pointer: str = Field(max_length=2048)
    span: RevisionRef
    source_revision_digest: Digest
    # The empty locator identifies the root of a plain text/SQL source. Exact
    # source-span binding below still applies; no synthetic field is invented.
    field_locator: str
    quote: str = Field(min_length=1, max_length=32000)
    quote_occurrence: int = Field(ge=0, strict=True)
    transformations: tuple[RevisionRef, ...] = Field(default=(), max_length=32)


class ContentUnresolvedClassification(ContentContract):
    """Authored source-scope classification; never a permission to ignore it."""
    contract_version: Literal['boi/knowledge-unresolved-classification@1','boi/knowledge-unresolved-classification@2']
    subject_pointer: str = Field(max_length=2048)
    facets: tuple[UnresolvedFacet, ...] = Field(min_length=1, max_length=6)
    provided_source_byte_digests: tuple[Digest, ...] = Field(default=(),max_length=32,
        exclude_if=lambda value:not value,
        description='For v2 source-boundary limitations, exact provided input bytes. '
        'Does not validate upstream originals or waive fidelity to these input bytes.')

    @model_validator(mode='after')
    def exact_facets(self):
        if len(set(self.facets)) != len(self.facets):
            raise ValueError('KNOWLEDGE_UNRESOLVED_FACET_DUPLICATE')
        boundary=set(self.facets)&{'upstream_source_fidelity','source_completeness'}
        if self.contract_version.endswith('@1') and (boundary or self.provided_source_byte_digests):
            raise ValueError('KNOWLEDGE_UNRESOLVED_SOURCE_BOUNDARY_VERSION_REQUIRED')
        if boundary and not self.provided_source_byte_digests:
            raise ValueError('KNOWLEDGE_UNRESOLVED_PROVIDED_SOURCE_REQUIRED')
        if len(set(self.provided_source_byte_digests))!=len(self.provided_source_byte_digests):
            raise ValueError('KNOWLEDGE_UNRESOLVED_PROVIDED_SOURCE_DUPLICATE')
        return self


class ContentUnresolved(ContentContract):
    meaning_pointer: str | None = Field(default=None, max_length=2048)
    source_spans: tuple[RevisionRef, ...] = Field(default=(), max_length=256)
    reason_code: Ref
    description: Ref
    classification: ContentUnresolvedClassification | None = None

    @model_validator(mode='after')
    def classification_preserves_subject(self):
        # A reviewed facet may change relevance to a use, but this extension
        # never narrows an existing global declaration to an unrelated node.
        if self.classification is not None and self.classification.subject_pointer != (self.meaning_pointer or ''):
            raise ValueError('KNOWLEDGE_UNRESOLVED_CLASSIFICATION_SUBJECT_CHANGED')
        return self

    @model_serializer(mode='wrap')
    def preserve_legacy_wire(self, handler):
        value = handler(self)
        if self.classification is None:
            value.pop('classification', None)
        return value


class ContentCheckerRequirement(ContentContract):
    checker_revision: RevisionRef
    capability: Ref
    required_meaning_pointers: tuple[str, ...] = Field(min_length=1, max_length=256)


class ContentUseContract(ContentContract):
    purpose: UsePurpose
    required_meaning_pointers: tuple[str, ...] = Field(min_length=1, max_length=256)
    prerequisites: tuple[Ref, ...] = Field(default=(), max_length=256)
    checker_requirements: tuple[ContentCheckerRequirement, ...] = Field(default=(), max_length=64)


class KnowledgeContent(ContentContract):
    contract_version: Literal['boi/knowledge-content@1'] = 'boi/knowledge-content@1'
    document: KnowledgeDocument
    profiles: tuple[ContentProfile, ...] = Field(min_length=1, max_length=64)
    # Each profile owns its meaning schema. This shared envelope preserves it;
    # interpretation and typed query eligibility require registered adapters.
    meaning: dict[str, JsonValue] = Field(min_length=1)
    body_bindings: tuple[BodyMeaningBinding, ...] = Field(min_length=1, max_length=1000)
    evidence_bindings: tuple[ContentEvidenceBinding, ...] = Field(min_length=1, max_length=1000)
    unresolved: tuple[ContentUnresolved, ...] = Field(default=(), max_length=1000)
    use_contracts: tuple[ContentUseContract, ...] = Field(default=(), max_length=64)
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def declared_links(self):
        if len({p.profile_id for p in self.profiles}) != len(self.profiles):
            raise ValueError('KNOWLEDGE_CONTENT_PROFILE_DUPLICATE')
        if len({u.purpose for u in self.use_contracts}) != len(self.use_contracts):
            raise ValueError('KNOWLEDGE_CONTENT_PURPOSE_DUPLICATE')
        pointers = []
        for binding in self.body_bindings:
            if (not binding.start < binding.end <= len(self.document.body)
                    or self.document.body[binding.start:binding.end] != binding.quote):
                raise ValueError('KNOWLEDGE_CONTENT_BODY_BINDING_MISMATCH')
            pointers.append(binding.meaning_pointer)
        pointers.extend(b.meaning_pointer for b in self.evidence_bindings)
        pointers.extend(u.meaning_pointer for u in self.unresolved if u.meaning_pointer is not None)
        for use in self.use_contracts:
            pointers.extend(use.required_meaning_pointers)
            for checker in use.checker_requirements:
                pointers.extend(checker.required_meaning_pointers)
        for pointer in pointers:
            meaning_pointer(self.meaning, pointer)
        return self


def decode_knowledge_content(value: object) -> KnowledgeContent | None:
    """Recognize only this version. Other native contents keep their own reader."""
    if not isinstance(value, dict) or value.get('contract_version') != 'boi/knowledge-content@1':
        return None
    return KnowledgeContent.model_validate(value)


def validate_content_envelope(content, *, draft, ledger, objects):
    """Called after the existing current source/owner/span/dependency checks.

    Inner references must be covered by that outer authorization closure.
    Exact quotation occurrence is mechanical evidence, never semantic approval.
    """
    content = decode_knowledge_content(content)
    if content is None:
        return
    spans = set(draft.evidence_spans)
    dependencies = {d.revision for d in draft.dependencies if d.required}
    required = {p.revision for p in content.profiles}
    for use in content.use_contracts:
        required.update(c.checker_revision for c in use.checker_requirements)
    for binding in content.evidence_bindings:
        required.update(binding.transformations)
    if not required <= dependencies:
        raise ValueError('KNOWLEDGE_CONTENT_DEPENDENCY_NOT_BOUND')
    if any(ref not in spans for item in content.unresolved for ref in item.source_spans):
        raise ValueError('KNOWLEDGE_CONTENT_UNRESOLVED_SPAN_NOT_BOUND')
    from .source_envelope import byte_digest
    for binding in content.evidence_bindings:
        if binding.span not in spans:
            raise ValueError('KNOWLEDGE_CONTENT_SPAN_NOT_BOUND')
        record = ledger.read(binding.span.ref)
        payload = record.payload
        if (payload.get('source_revision_digest') != binding.source_revision_digest
                or payload.get('field_locator') != binding.field_locator):
            raise ValueError('KNOWLEDGE_CONTENT_SOURCE_BINDING_MISMATCH')
        raw = objects.get(payload['field_object_ref'])
        if byte_digest(raw) != payload['content_digest']:
            raise ValueError('KNOWLEDGE_CONTENT_SOURCE_BYTES_CHANGED')
        text = raw.decode('utf-8')
        start = -1
        for _ in range(binding.quote_occurrence + 1):
            start = text.find(binding.quote, start + 1)
            if start == -1:
                raise ValueError('KNOWLEDGE_CONTENT_QUOTE_OCCURRENCE_MISSING')
