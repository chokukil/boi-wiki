"""Exact task knowledge closure shared by domain harnesses.

This module does not discover meaning, authorize sources, run agents or qualify
knowledge. A Wiki adapter must resolve each exact revision under the current
principal and policy before returning it. Profile content is opaque here: domain
AST/lint tools own its interpretation. Candidate context stays PROVISIONAL.
"""
from __future__ import annotations

import json
from typing import Callable, Literal

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest


AssetKind = Literal['source', 'definition', 'profile', 'pack', 'harness', 'skill', 'tool', 'sop']


class KnowledgeRequirement(FrozenContract):
    revision: RevisionRef
    role: Ref
    reason: Ref
    stages: tuple[Ref, ...] = Field(min_length=1)
    required: bool = True

    @model_validator(mode='after')
    def unique_stages(self):
        if len(self.stages) != len(set(self.stages)):
            raise ValueError('TASK_KNOWLEDGE_DUPLICATE_STAGE')
        return self


class TaskAssetRevision(FrozenContract):
    """Immutable transport projection of an already authorized revision.

    revision_digest identifies the storage revision; content_digest separately
    binds its complete payload. The resolver also binds the full envelope (and
    dependencies) into the context digest. Neither digest grants authority.
    JSON text keeps nested content immutable after validation.
    """
    revision: RevisionRef
    kind: AssetKind
    content_json: Ref
    content_digest: Digest
    authority: Literal['canonical', 'candidate', 'legacy_unbound']
    dependencies: tuple[KnowledgeRequirement, ...] = ()
    evidence: tuple[RevisionRef, ...] = ()
    conflicts_with: tuple[RevisionRef, ...] = ()
    supersedes: tuple[RevisionRef, ...] = ()

    @model_validator(mode='after')
    def bound_content(self):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('TASK_KNOWLEDGE_DUPLICATE_JSON_KEY')
                result[key] = value
            return result

        content = json.loads(self.content_json, object_pairs_hook=unique)
        if self.content_digest != semantic_digest(content):
            raise ValueError('TASK_KNOWLEDGE_CONTENT_DIGEST_MISMATCH')
        if isinstance(content, dict) and content.get('contract_version') == 'boi/knowledge-content@1':
            from .knowledge_content import decode_knowledge_content
            decode_knowledge_content(content)
        return self


class TaskContextSelection(FrozenContract):
    parent: RevisionRef | None
    requirement: KnowledgeRequirement
    status: Literal['selected', 'excluded', 'unavailable']
    reason_code: Ref | None = None


class TaskMeaningUse(FrozenContract):
    """Server-read scoped explanation receipt; never an independent ACL grant."""
    revision: RevisionRef
    qualification_ref: RevisionRef
    purpose: Literal['explain'] = 'explain'
    content_digest: Digest
    roots: tuple[Ref, ...] = Field(min_length=1)
    closure: tuple[Ref, ...] = Field(min_length=1)
    limitations: tuple[Ref, ...] = ()
    scope_digest: Digest


class TaskKnowledgeContext(FrozenContract):
    contract_version: Literal['boi/task-knowledge-context@1'] = 'boi/task-knowledge-context@1'
    principal_id: Ref
    policy_digest: Digest
    purpose: Ref
    source_manifest_digest: Digest
    lane: Literal['canonical', 'provisional']
    assets: tuple[TaskAssetRevision, ...]
    selections: tuple[TaskContextSelection, ...]
    meaning_uses: tuple[TaskMeaningUse, ...] = Field(default=(), exclude_if=lambda v:not v)
    dependency_completeness: Literal['complete', 'incomplete']
    # Successful structural resolution is not source fidelity or task readiness.
    source_fidelity: Literal['not_evaluated'] = 'not_evaluated'
    domain_verdict: Literal['not_evaluated'] = 'not_evaluated'
    task_readiness: Literal['not_evaluated'] = 'not_evaluated'
    display_status: Literal['CANONICAL_CONTEXT', 'PROVISIONAL']
    context_digest: Digest

    @model_validator(mode='after')
    def integrity(self):
        refs = {asset.revision.ref for asset in self.assets}
        if len(refs) != len(self.assets):
            raise ValueError('TASK_CONTEXT_REVISION_CONFLICT')
        if self.context_digest != semantic_digest(self.model_dump(mode='json', exclude={'context_digest'})):
            raise ValueError('TASK_CONTEXT_DIGEST_MISMATCH')
        if self.lane == 'canonical' and any(a.authority != 'canonical' for a in self.assets):
            raise ValueError('TASK_CONTEXT_CANONICAL_AUTHORITY_REQUIRED')
        if self.display_status != ('PROVISIONAL' if self.lane == 'provisional' else 'CANONICAL_CONTEXT'):
            raise ValueError('TASK_CONTEXT_DISPLAY_AUTHORITY_MISMATCH')
        missing = any(s.status == 'unavailable' for s in self.selections)
        if self.dependency_completeness != ('incomplete' if missing else 'complete'):
            raise ValueError('TASK_CONTEXT_COMPLETENESS_MISMATCH')
        revisions = {asset.revision for asset in self.assets}
        if len({u.revision for u in self.meaning_uses}) != len(self.meaning_uses):
            raise ValueError('TASK_MEANING_USE_DUPLICATE')
        for use in self.meaning_uses:
            asset = next((a for a in self.assets if a.revision == use.revision), None)
            if (asset is None or asset.kind != 'definition' or asset.content_digest != use.content_digest
                    or len(set(use.roots)) != len(use.roots) or len(set(use.closure)) != len(use.closure)
                    or not set(use.roots) <= set(use.closure)):
                raise ValueError('TASK_MEANING_USE_UNBOUND')
        for selection in self.selections:
            if selection.parent is not None and selection.parent not in revisions:
                raise ValueError('TASK_CONTEXT_PARENT_MISSING')
            if selection.status == 'selected':
                if selection.requirement.revision not in revisions or selection.reason_code is not None:
                    raise ValueError('TASK_CONTEXT_SELECTION_UNBOUND')
            elif (selection.reason_code is None
                    or (selection.status == 'unavailable') != selection.requirement.required):
                raise ValueError('TASK_CONTEXT_FAILURE_MISCLASSIFIED')
        for asset in self.assets:
            if not any(s.status == 'selected' and s.requirement.revision == asset.revision for s in self.selections):
                raise ValueError('TASK_CONTEXT_UNSELECTED_ASSET')
            for dep in asset.dependencies:
                if not any(s.parent == asset.revision and s.requirement == dep
                        and (s.status == 'selected' or not dep.required) for s in self.selections):
                    raise ValueError('TASK_CONTEXT_DEPENDENCY_UNACCOUNTED')
        return self


class KnowledgeUnavailable(ValueError):
    """Safe reason from the authorized reader; no restricted payload in errors."""
    CODES = frozenset({'MISSING', 'ACCESS_DENIED', 'POLICY_STALE', 'REVISION_MISMATCH',
        'TOOL_UNAVAILABLE', 'CYCLE', 'REVISION_CONFLICT', 'DECLARED_CONFLICT',
        'SUPERSEDES_CONFLICT', 'AUTHORITY_NOT_ALLOWED', 'CONTENT_INVALID'})

    def __init__(self, code: str):
        if code not in self.CODES:
            raise ValueError('TASK_KNOWLEDGE_UNKNOWN_FAILURE_CODE')
        self.code = code
        super().__init__('TASK_KNOWLEDGE_' + code)


# The reader closes over authenticated principal/policy. A caller-provided
# payload or an unrestricted filesystem reader is not a canonical catalog.
AuthorizedRevisionReader = Callable[[RevisionRef], TaskAssetRevision]


def resolve_task_knowledge(*, principal_id: str, policy_digest: str, purpose: str,
        source_manifest_digest: str, roots: tuple[KnowledgeRequirement, ...],
        read_authorized_revision: AuthorizedRevisionReader,
        lane: Literal['canonical', 'provisional'], available_tools: frozenset[RevisionRef],
        require_available_tools: bool = True,
        defer_optional_requirement: Callable[[RevisionRef,KnowledgeRequirement],bool]|None=None) -> TaskKnowledgeContext:
    """Resolve required closure first, then optional branches transactionally.

    A broken optional branch never poisons a usable required closure. Required
    failures remain explicit, allowing independent clear work to continue.
    Revision conflicts never select a latest version or silently substitute one.
    Cycles concern contract dependencies, not ordinary domain relationships.
    """
    selected: dict[str, TaskAssetRevision] = {}
    selections: list[TaskContextSelection] = []
    pending_optional: list[tuple[RevisionRef | None, KnowledgeRequirement]] = []

    def visit(req, parent, assets, records, optional, path):
        ref = req.revision
        if ref.ref in path:
            raise KnowledgeUnavailable('CYCLE')
        # Optional branches resume outside the recursive required path. Detect
        # an edge back to an ancestor in the already selected graph as well.
        pending, seen = [ref], set()
        while parent is not None and pending:
            node = pending.pop()
            if node == parent:
                raise KnowledgeUnavailable('CYCLE')
            if node not in seen:
                seen.add(node)
                pending.extend(s.requirement.revision for s in (*selections, *records)
                    if s.status == 'selected' and s.parent == node)
        previous = assets.get(ref.ref)
        if previous is not None:
            if previous.revision != ref:
                raise KnowledgeUnavailable('REVISION_CONFLICT')
            records.append(TaskContextSelection(parent=parent, requirement=req, status='selected'))
            return
        asset = read_authorized_revision(ref)
        try:
            # Revalidate even model_copy/model_construct data from an adapter.
            asset = TaskAssetRevision.model_validate(asset.model_dump(mode='json'))
        except ValueError as exc:
            raise KnowledgeUnavailable('CONTENT_INVALID') from exc
        if asset.revision != ref:
            raise KnowledgeUnavailable('REVISION_MISMATCH')
        if asset.authority == 'legacy_unbound' or (lane == 'canonical' and asset.authority != 'canonical'):
            raise KnowledgeUnavailable('AUTHORITY_NOT_ALLOWED')
        if require_available_tools and asset.kind == 'tool' and ref not in available_tools:
            raise KnowledgeUnavailable('TOOL_UNAVAILABLE')
        for other in assets.values():
            if ref in other.conflicts_with or other.revision in asset.conflicts_with:
                raise KnowledgeUnavailable('DECLARED_CONFLICT')
            if ref in other.supersedes or other.revision in asset.supersedes:
                raise KnowledgeUnavailable('SUPERSEDES_CONFLICT')
        assets[ref.ref] = asset
        records.append(TaskContextSelection(parent=parent, requirement=req, status='selected'))
        for dep in asset.dependencies:
            if dep.required:
                visit(dep, ref, assets, records, optional, (*path, ref.ref))
            else:
                optional.append((ref, dep))

    def attempt(parent, req):
        trial_assets, trial_records, trial_optional = dict(selected), [], []
        try:
            visit(req, parent, trial_assets, trial_records, trial_optional, ())
        except KnowledgeUnavailable as exc:
            selections.append(TaskContextSelection(parent=parent, requirement=req,
                status='unavailable' if req.required else 'excluded', reason_code=exc.code))
        else:
            selected.update(trial_assets)
            selections.extend(trial_records)
            pending_optional.extend(trial_optional)

    # Preserve caller priority between optional alternatives; never let optional
    # requests preempt required roots. This order is bound into the manifest.
    for req in roots:
        if req.required:
            attempt(None, req)
        else:
            pending_optional.append((None, req))
    index = 0
    seen_optional = set()
    while index < len(pending_optional):
        parent, req = pending_optional[index]
        index += 1
        key = semantic_digest({'parent': parent.model_dump(mode='json') if parent else None,
            'requirement': req.model_dump(mode='json')})
        if key not in seen_optional:
            seen_optional.add(key)
            # Optional source navigation can remain an exact, unconsumed
            # reference. Required dependencies and explicit roots are never
            # weakened. The authorized service, not a caller/model, chooses it.
            if parent is not None and req.revision.ref not in selected and defer_optional_requirement is not None:
                try:deferred=defer_optional_requirement(parent,req)
                except KnowledgeUnavailable as exc:
                    selections.append(TaskContextSelection(parent=parent,requirement=req,
                        status='excluded',reason_code=exc.code))
                    continue
                if deferred:
                    selections.append(TaskContextSelection(parent=parent,requirement=req,
                        status='excluded',reason_code='SOURCE_INVENTORY_DEFERRED_TO_SCOPED_READ'))
                    continue
            attempt(parent, req)

    body = dict(contract_version='boi/task-knowledge-context@1', principal_id=principal_id,
        policy_digest=policy_digest, purpose=purpose, source_manifest_digest=source_manifest_digest,
        lane=lane, assets=tuple(sorted(selected.values(), key=lambda a: a.revision.ref)),
        selections=tuple(selections),
        dependency_completeness='incomplete' if any(s.status == 'unavailable' for s in selections) else 'complete',
        source_fidelity='not_evaluated', domain_verdict='not_evaluated', task_readiness='not_evaluated',
        display_status='PROVISIONAL' if lane == 'provisional' else 'CANONICAL_CONTEXT')
    # Pydantic converts nested models before the digest, keeping wire and local
    # representations equivalent without teaching each domain the other's AST.
    wire = {**body, 'assets': [a.model_dump(mode='json') for a in body['assets']],
        'selections': [s.model_dump(mode='json') for s in selections]}
    return TaskKnowledgeContext.model_validate({**wire, 'context_digest': semantic_digest(wire)})


def affected_task_assets(context: TaskKnowledgeContext, changed: tuple[RevisionRef, ...]) -> tuple[RevisionRef, ...]:
    """Conservative exact-revision reverse closure, preserving unrelated assets.

    ACL/tool/source changes represented outside asset revisions require the
    caller to invalidate their bound context (policy/source manifest) as well.
    """
    affected = set(changed)
    while True:
        new = {asset.revision for asset in context.assets
            if any(dep.revision in affected for dep in asset.dependencies)
            or any(ref in affected for ref in asset.evidence)} - affected
        if not new:
            break
        affected.update(new)
    return tuple(asset.revision for asset in context.assets if asset.revision in affected)
