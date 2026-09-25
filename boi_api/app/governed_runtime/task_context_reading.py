"""Lossless bounded delivery of pinned task context to external consumers.

Delivery receipts establish complete bytes reaching the consumer, not model
comprehension, semantic use, scientific truth, approval or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest
from .task_knowledge import (KnowledgeRequirement, TaskAssetRevision, TaskKnowledgeContext,
    resolve_task_knowledge)


def _bytes_digest(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


class TaskContextPage(FrozenContract):
    contract_version: Literal['boi/task-context-page@1'] = 'boi/task-context-page@1'
    context_digest: Digest
    layout_digest: Digest
    index: int = Field(ge=0)
    page_count: int = Field(ge=1)
    chunk_text: str = Field(min_length=1)
    chunk_digest: Digest

    @model_validator(mode='after')
    def page_integrity(self):
        if self.index >= self.page_count or self.chunk_digest != _bytes_digest(self.chunk_text.encode('utf-8')):
            raise ValueError('TASK_CONTEXT_PAGE_CORRUPT')
        return self


class TaskContextDelivery(FrozenContract):
    contract_version: Literal['boi/task-context-delivery@1'] = 'boi/task-context-delivery@1'
    context_digest: Digest
    layout_digest: Digest
    principal_id: Ref
    policy_digest: Digest
    purpose: Ref
    source_manifest_digest: Digest
    page_digests: tuple[Digest, ...] = Field(min_length=1)
    delivered_revisions: tuple[RevisionRef, ...]
    status: Literal['DELIVERED_TO_CONSUMER'] = 'DELIVERED_TO_CONSUMER'
    comprehension_proven: Literal[False] = False
    semantic_equivalence_decided: Literal[False] = False
    approved: Literal[False] = False


@dataclass(frozen=True)
class DeliveredTaskContext:
    context: TaskKnowledgeContext
    receipt: TaskContextDelivery

    @property
    def receipt_digest(self):
        return semantic_digest(self.receipt)


def context_head_fence_revisions(context, *, preparation_version):
    """Current roots may retain immutable historical dependencies.

    Legacy preparation keeps its original all-heads admission semantics. In v2
    current namespace definitions and explicit roots must still be current;
    their exact dependency closure is read and ACL-checked at pinned revisions.
    """
    if preparation_version=='boi/prepared-domain-context@1':
        return frozenset(a.revision for a in context.assets)
    if preparation_version in ('boi/prepared-domain-context@2','boi/prepared-domain-context@3'):
        return frozenset(s.requirement.revision for s in context.selections
            if s.status=='selected' and s.parent is None)
    raise ValueError('DOMAIN_CONTEXT_PREPARATION_VERSION_UNSUPPORTED')


def prepare_task_context_pages(context: TaskKnowledgeContext, *, max_payload_bytes: int = 8192) -> tuple[TaskContextPage, ...]:
    """Bound chunk bytes, excluding the small page transport envelope.

    UTF-8 codepoints survive page boundaries; a consumer must assemble all pages
    before interpreting JSON. Page preparation itself produces no read receipt.
    """
    if isinstance(max_payload_bytes, bool) or not isinstance(max_payload_bytes, int) or not 256 <= max_payload_bytes <= 65536:
        raise ValueError('TASK_CONTEXT_PAGE_SIZE_INVALID')
    context = TaskKnowledgeContext.model_validate(context.model_dump(mode='json'))
    raw = context.model_dump_json().encode('utf-8')
    chunks = []
    start = 0
    while start < len(raw):
        end = min(len(raw), start + max_payload_bytes)
        # UTF-8 continuation bytes begin 10xxxxxx. Do not split a codepoint.
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        chunks.append(raw[start:end].decode('utf-8'))
        start = end
    digests = tuple(_bytes_digest(chunk.encode('utf-8')) for chunk in chunks)
    layout = semantic_digest({'context_digest': context.context_digest, 'page_digests': digests})
    return tuple(TaskContextPage(context_digest=context.context_digest, layout_digest=layout,
        index=index, page_count=len(chunks), chunk_text=chunk, chunk_digest=digests[index])
        for index, chunk in enumerate(chunks))


def receive_task_context(pages: tuple[TaskContextPage, ...], *, expected_context_digest: str,
        principal_id: str, policy_digest: str, purpose: str, source_manifest_digest: str) -> DeliveredTaskContext:
    """Consumer-side assembly pinned to the task's expected source and access.

    These expected values come from the authorized task, not from the first page.
    Server admission must verify its own stored receipt; accepting this model
    alone would only verify a caller's self-report.
    """
    if not pages:
        raise ValueError('TASK_CONTEXT_PAGES_MISSING')
    pages = tuple(TaskContextPage.model_validate(p.model_dump(mode='json')) for p in pages)
    if any(p.context_digest != expected_context_digest or p.page_count != len(pages)
            or p.index != i or p.layout_digest != pages[0].layout_digest for i, p in enumerate(pages)):
        raise ValueError('TASK_CONTEXT_PAGE_SEQUENCE_MISMATCH')
    digests = tuple(p.chunk_digest for p in pages)
    layout = semantic_digest({'context_digest': expected_context_digest, 'page_digests': digests})
    if layout != pages[0].layout_digest:
        raise ValueError('TASK_CONTEXT_PAGE_LAYOUT_MISMATCH')
    context = TaskKnowledgeContext.model_validate_json(''.join(p.chunk_text for p in pages))
    if context.context_digest != expected_context_digest:
        raise ValueError('TASK_CONTEXT_UNEXPECTED_DIGEST')
    if (context.principal_id, context.policy_digest, context.purpose, context.source_manifest_digest) != (
            principal_id, policy_digest, purpose, source_manifest_digest):
        raise ValueError('TASK_CONTEXT_ACCESS_SOURCE_OR_PURPOSE_MISMATCH')
    return DeliveredTaskContext(context, TaskContextDelivery(context_digest=context.context_digest,
        layout_digest=layout, principal_id=principal_id, policy_digest=policy_digest, purpose=purpose,
        source_manifest_digest=source_manifest_digest, page_digests=digests,
        delivered_revisions=tuple(a.revision for a in context.assets)))


def require_delivered_stage(delivered: DeliveredTaskContext, *, stage: str) -> tuple[TaskAssetRevision, ...]:
    """Gate a stage on its required context, leaving independent stages usable."""
    context = TaskKnowledgeContext.model_validate(delivered.context.model_dump(mode='json'))
    receipt = TaskContextDelivery.model_validate(delivered.receipt.model_dump(mode='json'))
    if (receipt.context_digest != context.context_digest or receipt.principal_id != context.principal_id
            or receipt.policy_digest != context.policy_digest or receipt.purpose != context.purpose
            or receipt.source_manifest_digest != context.source_manifest_digest
            or receipt.delivered_revisions != tuple(a.revision for a in context.assets)):
        raise ValueError('TASK_CONTEXT_DELIVERY_BINDING_MISMATCH')
    requested = [s for s in context.selections if stage in s.requirement.stages]
    if not requested:
        raise ValueError('TASK_CONTEXT_STAGE_UNDECLARED')
    if any(s.status == 'unavailable' for s in requested):
        raise ValueError('TASK_CONTEXT_REQUIRED_STAGE_INPUT_UNAVAILABLE')
    selected = {s.requirement.revision for s in requested if s.status == 'selected'}
    # Include full dependencies of the stage's selected assets even when those
    # dependencies were declared for an additional later stage.
    changed = True
    while changed:
        extra = {dep.revision for a in context.assets if a.revision in selected
            for dep in a.dependencies if any(b.revision == dep.revision for b in context.assets)} - selected
        changed = bool(extra)
        selected.update(extra)
    return tuple(a for a in context.assets if a.revision in selected)


def active_definition_task_context(*, definitions, principal_id: str, policy_digest: str,
        source_manifest_digest: str, source_namespace: str, purpose: str,
        stages: tuple[str, ...] = ('extract', 'match', 'plan', 'explain')) -> TaskKnowledgeContext:
    """Read-only adapter for the existing authorized active-definition loader.

    The service supplies a freshly resolved ActiveDefinitionSnapshot; no API
    should accept it as a client authority assertion. This preserves the exact
    full lookup as a runtime pack projection, without writing a Pack or Release.
    General domain harnesses can use other authorized revision readers directly.
    """
    from .semantic_profile_loader import ActiveDefinitionSnapshot
    from .semantic_definition_reading import read_existing_definitions

    definitions = ActiveDefinitionSnapshot.model_validate(definitions.model_dump(mode='json'))
    if semantic_digest(definitions.model_dump(mode='json', exclude={'snapshot_digest'})) != definitions.snapshot_digest:
        raise ValueError('ACTIVE_DEFINITION_SNAPSHOT_DRIFT')
    if definitions.lookup.namespace != source_namespace:
        raise ValueError('SOURCE_DEFINITION_NAMESPACE_MISMATCH')
    reading = read_existing_definitions(principal_id=principal_id, policy_digest=policy_digest,
        lookup=definitions.lookup, entries=definitions.entries, source_manifest_digest=source_manifest_digest,
        for_model=False)
    assets = {}
    deps = []
    for entry, definition in zip(sorted(definitions.entries, key=lambda e: e.entry_id), reading.model_definitions):
        revision = RevisionRef(ref=entry.entry_id, revision_digest=entry.revision_digest)
        assets[revision] = TaskAssetRevision(revision=revision, kind='definition',
            content_json=json.dumps(definition, ensure_ascii=False), content_digest=semantic_digest(definition),
            authority='canonical')
        deps.append(KnowledgeRequirement(revision=revision, role='existing_definition',
            reason='Complete authorized definition scope before interpretation', stages=stages))
    pack_content = {'definition_reading_receipt': reading.receipt, 'definition_reading_digest': reading.receipt_digest,
        'snapshot_digest': definitions.snapshot_digest, 'active_release_digest': definitions.active_release_digest}
    pack_ref = RevisionRef(ref='definition-lookup:' + semantic_digest(definitions.lookup),
        revision_digest=definitions.snapshot_digest)
    assets[pack_ref] = TaskAssetRevision(revision=pack_ref, kind='pack', authority='canonical',
        content_json=json.dumps(pack_content, ensure_ascii=False), content_digest=semantic_digest(pack_content),
        dependencies=tuple(deps))
    return resolve_task_knowledge(principal_id=principal_id, policy_digest=policy_digest, purpose=purpose,
        source_manifest_digest=source_manifest_digest,
        roots=(KnowledgeRequirement(revision=pack_ref, role='definition_lookup_scope',
            reason='Pinned existing knowledge without truncation or global absence claims', stages=stages),),
        read_authorized_revision=assets.__getitem__, lane='canonical', available_tools=frozenset())
