"""Stored context delivery/admission; domain reasoning runs outside Wiki."""
from __future__ import annotations
from .diagnostic_timing import stage_timing

import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from pydantic import Field

from .domain_asset_store import DomainAssetStore, source_manifest_digest
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest
from .task_context_reading import prepare_task_context_pages, context_head_fence_revisions, TaskContextPage
from .task_knowledge import KnowledgeRequirement, KnowledgeUnavailable, TaskAssetRevision, TaskKnowledgeContext, resolve_task_knowledge


_CONTEXT_DECODING = ContextVar('context_structural_decoding', default=None)
_CANONICAL_SCOPE_READING = ContextVar('canonical_scope_reading', default=None)
_CANONICAL_PROFILE_SCOPE = ContextVar('canonical_profile_scope', default=None)
_CONTEXT_READING_VALIDATION = ContextVar('context_reading_validation', default=None)
_DEFINITION_SCOPE_READING = ContextVar('definition_scope_reading', default=None)


@contextmanager
def request_context_decoding():
    """Bounded structural-only reuse; no current authorization is retained."""
    token = _CONTEXT_DECODING.set({})
    canonical_token = _CANONICAL_SCOPE_READING.set({})
    canonical_profile_token = _CANONICAL_PROFILE_SCOPE.set({})
    validation_token = _CONTEXT_READING_VALIDATION.set({})
    definition_scope_token = _DEFINITION_SCOPE_READING.set({})
    try:
        yield
    finally:
        _DEFINITION_SCOPE_READING.reset(definition_scope_token)
        _CONTEXT_READING_VALIDATION.reset(validation_token)
        _CANONICAL_PROFILE_SCOPE.reset(canonical_profile_token)
        _CANONICAL_SCOPE_READING.reset(canonical_token)
        _CONTEXT_DECODING.reset(token)


@stage_timing('context_structural_decode')
def _decode_context(raw):
    return TaskKnowledgeContext.model_validate_json(raw)


def decode_context(raw):
    # The caller reads and verifies current object bytes before this helper,
    # then rechecks all current sources, assets, heads and scope afterwards.
    cache = _CONTEXT_DECODING.get()
    if cache is not None and raw in cache:
        return cache[raw].model_copy(deep=True)
    result = _decode_context(raw)
    if cache is not None and len(raw) <= 2 * 1024 * 1024:
        if len(cache) >= 16 or sum(map(len, cache)) + len(raw) > 2 * 1024 * 1024:
            cache.clear()
        cache[raw] = result.model_copy(deep=True)
    return result


class DomainContextPrepareRequest(FrozenContract):
    sources: tuple[ArtifactEnvelope, ...] = Field(min_length=1,max_length=100)
    namespace: Ref
    purpose: Ref
    roots: tuple[KnowledgeRequirement, ...] = ()
    stages: tuple[Ref, ...] = Field(default=('extract','match','plan','explain'),min_length=1)
    tool_use: Literal['execution', 'provenance_only', 'selected_stage'] = 'execution'
    definition_reading: Literal['all', 'selected_dependencies'] = 'all'
    package_selection: dict | None = None


class DomainContextPageRequest(FrozenContract):
    context_ref: RevisionRef
    expected_context_digest: Digest
    page_index: int = Field(default=0,ge=0,strict=True)
    page_batch_size: int = Field(default=1,ge=1,le=8,strict=True)


class DomainContextAcknowledgeRequest(FrozenContract):
    context_ref: RevisionRef
    expected_context_digest: Digest
    page_digests: tuple[Digest, ...] = Field(min_length=1)


class DomainContextRestoreRequest(FrozenContract):
    reading_ref: RevisionRef
    sources: tuple[ArtifactEnvelope, ...] = Field(min_length=1,max_length=100)


def same_canonical_definition_scope(known, current, *, known_canonical=(), current_canonical=()):
    """Ignore release-envelope churn only when the authorized semantic slice is identical.

    Active release and reading receipt digests include unrelated namespaces.  The
    namespace/purpose lookup digest and every other scope field remain binding;
    selected canonical assets are revalidated separately by ``_load``.
    """
    if known == current:return True
    if not isinstance(known,dict) or not isinstance(current,dict):return False
    volatile={'active_release_digest','reading_receipt_digest'}
    if ({k:v for k,v in known.items() if k not in volatile}
            == {k:v for k,v in current.items() if k not in volatile}):return True
    # A context prepared before the first active release had no canonical
    # definitions.  Activating an unrelated release must not invalidate it when
    # this exact namespace/purpose slice is still empty on both sides.
    return (known.get('status')=='unavailable_no_active_release'
        and current.get('status')=='complete_authorized_namespace'
        and not tuple(known_canonical) and not tuple(current_canonical))


class DomainContextService:
    CONTRACT = 'boi/prepared-domain-context@3'
    DELIVERY = 'boi/acknowledged-domain-context@1'

    def __init__(self, source_intake, *, principal_teams=(), available_tools=frozenset(), packages=None):
        self.intake = source_intake
        self.assets = DomainAssetStore(source_intake)
        self.ledger, self.store, self.objects = source_intake.ledger, source_intake.store, source_intake.objects
        self.principal_teams = tuple(sorted(set(principal_teams)))
        self.available_tools = available_tools
        self.packages = packages

    def shared_assets(self, authorization, selection, *, require_current=True):
        if selection is None:
            return {}
        if self.packages is None:
            raise ValueError('DOMAIN_CONTEXT_PACKAGE_RESOLVER_UNAVAILABLE')
        return self.packages.resolve_bound_assets(authorization=authorization, principal_teams=self.principal_teams,
            selection=selection, require_current=require_current)

    def package_fences(self, authorization, selection):
        if selection is None:
            return ()
        if self.packages is None:
            raise ValueError('DOMAIN_CONTEXT_PACKAGE_RESOLVER_UNAVAILABLE')
        return self.packages.selection_fences(authorization=authorization, principal_teams=self.principal_teams, selection=selection)

    def _canonical_definitions(self, authorization, namespace, purpose, source_digest):
        """Use the established loader; never promote a candidate into this map."""
        active_pointer=self.ledger.active_pointer()
        if active_pointer is None:
            return {}, {'status':'unavailable_no_active_release','absence_proven':False}
        cache=_CANONICAL_SCOPE_READING.get()
        key=(authorization.principal,authorization.policy_digest,self.principal_teams,
            namespace,purpose,source_digest,semantic_digest(active_pointer))
        if cache is not None and key in cache:
            assets,scope=cache[key]
            return dict(assets),dict(scope)
        from .semantic_profile_loader import ActiveReleaseProfileLoader, ProfilePrincipal
        from .semantic_definition_reading import read_existing_definitions
        profile_cache = _CANONICAL_PROFILE_SCOPE.get()
        profile_key = (
            authorization.principal, authorization.policy_digest,
            self.principal_teams, namespace, purpose,
            semantic_digest(active_pointer),
        )
        if profile_cache is not None and profile_key in profile_cache:
            snapshot = profile_cache[profile_key]
        else:
            from ..v2.native_formula_timing import timed_call
            snapshot = timed_call(
                'canonical_profile_scope_read',
                ActiveReleaseProfileLoader(self.ledger,self.objects).load_definition_scope,
                principal=ProfilePrincipal(
                    principal_id=authorization.principal,
                    team_ids=self.principal_teams),
                namespace=namespace, purpose=purpose,
                policy_digest=authorization.policy_digest,
                at=self.intake.clock())
            if profile_cache is not None:
                if len(profile_cache) >= 32:
                    profile_cache.clear()
                profile_cache[profile_key] = snapshot
        reading = read_existing_definitions(principal_id=authorization.principal,policy_digest=authorization.policy_digest,
            lookup=snapshot.lookup,entries=snapshot.entries,source_manifest_digest=source_digest,for_model=False)
        assets = {}
        for definition in reading.model_definitions:
            revision = RevisionRef(ref=definition['concept_id'],revision_digest=definition['revision_digest'])
            assets[revision] = TaskAssetRevision(revision=revision,kind='definition',authority='canonical',
                content_json=json.dumps(definition,ensure_ascii=False),content_digest=semantic_digest(definition))
        scope={'status':'complete_authorized_namespace','absence_proven':False,
            'lookup_digest':semantic_digest(snapshot.lookup),'active_release_digest':snapshot.active_release_digest,
            'reading_receipt_digest':reading.receipt_digest}
        if cache is not None:
            if len(cache)>=32:cache.clear()
            cache[key]=(dict(assets),dict(scope))
        return assets,scope

    def _definition_scope(self, authorization, namespace):
        """Read one authorized candidate inventory snapshot per API action."""
        cache = _DEFINITION_SCOPE_READING.get()
        key = (authorization.principal, authorization.policy_digest, namespace)
        if cache is not None and key in cache:
            # definition_scope returns a read-only inventory projection. Callers
            # only compare revisions, digests and inverse postings.
            return cache[key]
        from .catalog_search_index import definition_scope
        from ..v2.native_formula_timing import timed_call
        inventory = timed_call(
            'definition_scope_read', definition_scope,
            self.assets, authorization, namespace)
        if cache is not None:
            if len(cache) >= 32:
                cache.clear()
            cache[key] = inventory
        return inventory

    def prepare(self, *, authorization, request: DomainContextPrepareRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        self.assets.authorize_sources(authorization,request.sources,model_input=True)
        shared = self.shared_assets(authorization, request.package_selection)
        canonical, canonical_scope = self._canonical_definitions(authorization,request.namespace,request.purpose,
            source_manifest_digest(request.sources))
        inventory = self._definition_scope(authorization, request.namespace)
        definitions = list(inventory['revisions'].values())
        required = []
        already = set()
        # Discovery remains complete and freshness-bound. Reading every discovered
        # definition is separate from resolving explicitly selected dependencies.
        refs = ([RevisionRef.model_validate(d['revision']) for d in definitions] + list(canonical)
            if request.definition_reading == 'all' else [])
        for revision in refs:
            if revision not in already:
                required.append(KnowledgeRequirement(revision=revision,role='existing_definition',
                    reason='Read the current authorized namespace before proposing meaning',stages=request.stages))
                already.add(revision)
        # In full-reading mode an optional caller root cannot weaken the required
        # namespace reading. Selected mode retains each asset's declared closure.
        required.extend(request.roots)
        candidate_reader = self.assets.reader(authorization)
        read_assets={}
        def reader(revision):
            if revision not in read_assets:
                read_assets[revision]=(canonical[revision] if revision in canonical else
                    shared[revision] if revision in shared else candidate_reader(revision))
            return read_assets[revision]
        from .task_source_navigation import defer_workbook_inventory
        def defer_source_inventory(parent, requirement):
            return defer_workbook_inventory(reader, parent, requirement)
        def resolve(requirements):
            return resolve_task_knowledge(principal_id=authorization.principal,policy_digest=authorization.policy_digest,
                purpose=request.purpose,source_manifest_digest=source_manifest_digest(request.sources),roots=tuple(requirements),
                read_authorized_revision=reader,lane='provisional',available_tools=self.available_tools,
                require_available_tools=request.tool_use=='execution',
                **({'defer_optional_requirement':defer_source_inventory}
                   if request.definition_reading=='selected_dependencies' else {}))
        context=resolve(required)
        if request.definition_reading=='selected_dependencies':
            selected={asset.revision for asset in context.assets}
            outgoing={ref for asset in context.assets for ref in (*asset.conflicts_with,*asset.supersedes)}
            required_refs={req.revision for req in required if req.required}
            related=[]
            for item in definitions:
                revision=RevisionRef.model_validate(item['revision'])
                if revision in selected or revision in required_refs:continue
                relations=item['declared_relations']
                incoming={RevisionRef.model_validate(ref) for name in ('conflicts_with','supersedes') for ref in relations[name]}
                if revision in outgoing or incoming & selected:
                    related.append(KnowledgeRequirement(revision=revision,role='declared_conflict_candidate',
                        reason='An exact declared conflict or supersession concerns the selected context. '
                            'If unavailable here, this revision remains addressable through the protected asset reader.',
                        stages=request.stages))
            if related:
                # Reuse the same resolver and request-local authorized assets.
                # A conflicting branch stays explicitly unavailable, including
                # its exact revision; it is never silently treated as irrelevant.
                context=resolve([*required,*related])
        pages = prepare_task_context_pages(context)
        raw = context.model_dump_json().encode('utf-8')
        body = {'contract_version':self.CONTRACT,'employee_id':authorization.principal,
            'policy_digest':authorization.policy_digest,'principal_teams':list(self.principal_teams),
            'namespace':request.namespace,'purpose':request.purpose,'sources':[s.model_dump(mode='json') for s in request.sources],
            'context_digest':context.context_digest,'context_object_ref':self.objects.put(raw),
            'source_manifest_digest':context.source_manifest_digest,'canonical_scope':canonical_scope,
            'provisional_definition_scope_digest':inventory['inventory_digest'],'page_count':len(pages),
            'provisional_inventory_digest':inventory['inventory_digest'],
            'provisional_definition_revisions':[d['revision'] for d in definitions],
            'page_digests':[p.chunk_digest for p in pages],'layout_digest':pages[0].layout_digest,
            'status':'PROVISIONAL','canonical_projection_eligible':False,
            'tool_use':request.tool_use}
        # Preserve historical default preparation/receipt bytes. Explicit partial
        # reading binds its scope to the same immutable preparation and receipt.
        reading_scope = {} if request.definition_reading == 'all' else {
            'definition_reading':request.definition_reading,
            'namespace_definition_content_complete':False}
        body.update(reading_scope)
        if request.package_selection is not None:
            body['package_selection'] = request.package_selection
        # Same exact context preparation reuses its first publication timestamp.
        key = 'context-preparation:' + semantic_digest(body)
        row = self.store.get('domain_context_deliveries',key)
        if row is None:
            proposed = {'employee_id':authorization.principal,'body_digest':semantic_digest(body),
                'occurred_at':self.intake.clock().isoformat()}
            self.store.atomic_compare_and_write((AtomicWrite('domain_context_deliveries',key,None,proposed),
                *self.package_fences(authorization, request.package_selection)))
            row = self.store.get('domain_context_deliveries',key)
        if row is None or row.get('body_digest') != semantic_digest(body):
            raise ValueError('DOMAIN_CONTEXT_PREPARATION_CONFLICT')
        record = self.ledger.append(RecordKind.RUN,body,authority='migration_service',occurred_at=row['occurred_at'])
        return {'context_ref':DomainAssetStore._ref(record).model_dump(mode='json'),
            'context_digest':context.context_digest,'page_count':len(pages),
            'page_batch_limit':8,
            'principal_id':authorization.principal,'policy_digest':authorization.policy_digest,
            'namespace':request.namespace,'purpose':request.purpose,'source_manifest_digest':context.source_manifest_digest,
            'canonical_projection_eligible':False,
            'dependency_completeness':context.dependency_completeness,'canonical_scope':canonical_scope,
            'provisional_scope_status':'complete','status':'PROVISIONAL','reading_status':'not_acknowledged',
            'tool_use':request.tool_use, **reading_scope}

    def _same_unused_definition_inputs(self, authorization, old_ref, current_ref):
        """Unused content may change; sources and asset-level relations stay pinned.

        Used only after a saved answer positively establishes source-only use.
        Internal meaning (including its conditions/relations) is not consumed in
        that path. This does not approve the new definition or admit a new task.
        """
        old_record, old = self.assets._read_record(authorization, old_ref)
        current_record, current = self.assets._read_record(authorization, current_ref)
        omitted = {'revision', 'content_json', 'content_digest'}
        return (old.kind == current.kind == 'definition'
            and all(old_record.payload[key] == current_record.payload[key]
                    for key in ('namespace', 'logical_id', 'sources'))
            and old.model_dump(mode='json', exclude=omitted) == current.model_dump(mode='json', exclude=omitted))

    def _same_unused_definition_inventory(self, authorization, known, current):
        # New or removed candidates still invalidate discovery scope, even when
        # no meaning was used. Only existing identities may change content.
        def identities(refs):
            result = {}
            for ref in refs:
                record, _ = self.assets._read_record(authorization, ref)
                key = (record.payload['namespace'], record.payload['logical_id'])
                if key in result:return None
                result[key] = ref
            return result
        old_ids, current_ids = identities(known), identities(current)
        return (old_ids is not None and current_ids is not None and old_ids.keys() == current_ids.keys()
            and all(old_ids[key] == current_ids[key]
                    or self._same_unused_definition_inputs(authorization, old_ids[key], current_ids[key])
                    for key in old_ids))

    def _load(self, authorization, revision, expected_digest, *, require_current=True,
            _source_only_saved_answer=False, _exact_metadata_successors=False):
        self.intake._policy(authorization)
        record = self.ledger.read(revision.ref)
        body = record.payload
        if (record.kind != RecordKind.RUN or record_digest(record.record_id) != revision.revision_digest
                or body.get('contract_version') not in ('boi/prepared-domain-context@1','boi/prepared-domain-context@2',self.CONTRACT)
                or body.get('employee_id') != authorization.principal or body.get('policy_digest') != authorization.policy_digest
                or body.get('principal_teams') != list(self.principal_teams)
                or body.get('context_digest') != expected_digest):
            raise ValueError('DOMAIN_CONTEXT_ACCESS_OR_BINDING_DENIED')
        sources = tuple(ArtifactEnvelope.model_validate(s) for s in body['sources'])
        self.assets.authorize_sources(authorization,sources,model_input=True)
        shared = self.shared_assets(authorization, body.get('package_selection'), require_current=require_current)
        raw = self.objects.get(body['context_object_ref'])
        if byte_digest(raw) != body['context_object_ref']:
            raise ValueError('DOMAIN_CONTEXT_CONTENT_DRIFT')
        context = decode_context(raw)
        if context.context_digest != expected_digest or context.source_manifest_digest != source_manifest_digest(sources):
            raise ValueError('DOMAIN_CONTEXT_CONTENT_DRIFT')
        canonical, scope = self._canonical_definitions(authorization,body['namespace'],body['purpose'],
            context.source_manifest_digest)
        saved_canonical=(asset.revision for asset in context.assets if asset.authority=='canonical')
        if not same_canonical_definition_scope(body['canonical_scope'],scope,
                known_canonical=saved_canonical,current_canonical=canonical):
            raise ValueError('DOMAIN_CONTEXT_CANONICAL_DEFINITIONS_CHANGED')
        current_heads=context_head_fence_revisions(context,preparation_version=body['contract_version'])
        metadata_successors = {}
        for asset in context.assets:
            if (require_current and body.get('tool_use','execution')=='execution'
                    and asset.kind == 'tool' and asset.revision not in self.available_tools):
                raise ValueError('DOMAIN_CONTEXT_REQUIRED_TOOL_UNAVAILABLE')
            if asset.authority == 'canonical':
                current = canonical.get(asset.revision)
            elif asset.revision in shared:
                # An adopted immutable member is pinned by its package fence,
                # not by a private head belonging to the harness's author.
                current = shared[asset.revision]
            else:
                stored, current = self.assets._read_record(authorization,asset.revision)
                head_key = 'domain-asset-head:' + semantic_digest([authorization.principal,stored.payload['namespace'],stored.payload['logical_id']])
                head = self.store.get('domain_asset_heads',head_key)
                if require_current and asset.revision in current_heads and (not head or head['revision'] != asset.revision.model_dump(mode='json')):
                    from .metadata_revision import same_metadata_lineage
                    from .ledger import LedgerError
                    try:
                        metadata_unchanged = (_exact_metadata_successors and head and asset.kind == 'definition'
                            and same_metadata_lineage(self.assets, authorization, asset.revision,
                                RevisionRef.model_validate(head['revision'])))
                    except LedgerError as exc:
                        raise ValueError('DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED') from exc
                    if not (metadata_unchanged or (_source_only_saved_answer and head and asset.kind == 'definition'
                            and self._same_unused_definition_inputs(authorization, asset.revision,
                                RevisionRef.model_validate(head['revision'])))):
                        raise ValueError('DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED')
                    if metadata_unchanged:
                        metadata_successors[asset.revision] = RevisionRef.model_validate(head['revision'])
            if current != asset:
                raise ValueError('DOMAIN_CONTEXT_SELECTED_CONTENT_CHANGED')
        if require_current:
            # Rechecking only selected heads misses definitions added after an
            # empty/partial namespace reading. Compare the exact current set;
            # unrelated packs or assets in another namespace do not invalidate it.
            if 'provisional_definition_revisions' in body:
                known = {RevisionRef.model_validate(r) for r in body['provisional_definition_revisions']}
            else:
                known = {a.revision for a in context.assets if a.kind=='definition' and a.authority=='candidate'
                    and self.assets._read_record(authorization,a.revision)[0].payload['namespace']==body['namespace']
                    and any(s.requirement.revision==a.revision and s.requirement.role=='existing_definition'
                        for s in context.selections)}
            selected_reading=body.get('definition_reading')=='selected_dependencies'
            inventory = self._definition_scope(authorization, body['namespace'])
            known_digest = body.get('provisional_inventory_digest') or semantic_digest([
                ref.model_dump(mode='json') for ref in sorted(known, key=lambda ref: ref.ref)])
            inventory_unchanged = inventory['inventory_digest'] == known_digest
            selected_unchanged=False
            if selected_reading and not inventory_unchanged:
                selected={a.revision for a in context.assets}
                outgoing={ref for a in context.assets for ref in (*a.conflicts_with,*a.supersedes)}
                # This is a selected dependency reading, explicitly NOT a
                # complete namespace meaning/absence assessment. Pin consumed
                # namespace definitions and detect newly declared neighboring
                # conflicts/supersessions without invalidating on unrelated
                # additions. Discovery/absence callers retain the full fence.
                # Recorded meanings stay on their exact revisions. A verified
                # metadata successor only supplies the current head fence; it
                # does not replace the original context or review input.
                current_selected={metadata_successors.get(ref,ref) for ref in selected & known}
                # Exact inverse postings find newly declared neighbors without
                # visiting every unrelated current definition. Selected head
                # and immutable content checks above remain authoritative.
                neighbor_keys = {ref.ref for ref in outgoing if ref.ref in inventory['revisions']}
                for target in selected | current_selected:
                    neighbor_keys.update(inventory['incoming'].get(target.ref, ()))
                neighbors = [inventory['revisions'][key] for key in neighbor_keys]
                selected_unchanged=(all(inventory['revisions'].get(ref.ref, {}).get('revision')
                    == ref.model_dump(mode='json') for ref in current_selected) and not any(
                    ref not in known and ref not in metadata_successors.values()
                    and (ref in outgoing or refs & (selected | current_selected))
                    for item in neighbors
                    for ref in (RevisionRef.model_validate(item['revision']),)
                    for refs in ({RevisionRef.model_validate(r) for values in item['declared_relations'].values()
                                  for r in values},)))
            metadata_unchanged = False
            current_refs = None
            if not inventory_unchanged and not selected_unchanged:
                # Complete-scope compatibility needs the whole changed set.
                # It is never substituted for selected dependency discovery.
                current_refs = {RevisionRef.model_validate(item['revision'])
                                for item in inventory['revisions'].values()}
            if _exact_metadata_successors and current_refs is not None:
                from .metadata_revision import metadata_predecessors
                # Bijection of the complete recorded inventory: additions,
                # removals and unlinked new conflicts still invalidate it.
                mapped = {ref: ({ref} if ref in known else
                               set(metadata_predecessors(self.assets, authorization, ref)) & known)
                          for ref in current_refs}
                metadata_unchanged = (len(current_refs) == len(known)
                    and all(len(refs) == 1 for refs in mapped.values())
                    and set().union(set(), *mapped.values()) == known)
            if not inventory_unchanged and not selected_unchanged and not metadata_unchanged and not (_source_only_saved_answer
                    and self._same_unused_definition_inventory(authorization, known, current_refs)):
                raise ValueError('DOMAIN_CONTEXT_DEFINITION_SCOPE_CHANGED')
        # Only immutable page assembly is reused. The checks above still run
        # against current permissions, source bytes, heads and discovery scope.
        def page_projection(raw):
            pinned = TaskKnowledgeContext.model_validate_json(raw)
            return [p.model_dump(mode='json') for p in prepare_task_context_pages(pinned)]
        project = getattr(self.objects, 'project_verified', None)
        pages = (tuple(TaskContextPage.model_validate(p) for p in project(
            body['context_object_ref'], version='task-context-pages@1:utf8-8192', derive=page_projection))
            if project is not None else prepare_task_context_pages(context))
        if [p.chunk_digest for p in pages] != body['page_digests'] or pages[0].layout_digest != body['layout_digest']:
            raise ValueError('DOMAIN_CONTEXT_PAGE_LAYOUT_CHANGED')
        return record, context, pages

    def read_page(self, *, authorization, request: DomainContextPageRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        record, context, pages = self._load(authorization,request.context_ref,request.expected_context_digest)
        if request.page_index >= len(pages):
            raise ValueError('DOMAIN_CONTEXT_PAGE_OUTSIDE_RANGE')
        end = min(request.page_index + request.page_batch_size, len(pages))
        key = 'context-delivery:' + record.record_id
        for _ in range(8):
            row = self.store.get('domain_context_deliveries',key)
            served = set((row or {}).get('served_pages',()))
            served.update(range(request.page_index, end))
            value = {**(row or {}),'employee_id':authorization.principal,'context_ref':request.context_ref.model_dump(mode='json'),
                'context_digest':context.context_digest,'policy_digest':authorization.policy_digest,'served_pages':sorted(served)}
            if self.store.atomic_compare_and_write((AtomicWrite('domain_context_deliveries',key,row,value),
                    *self.package_fences(authorization, record.payload.get('package_selection')))):
                break
        else:
            raise ValueError('DOMAIN_CONTEXT_DELIVERY_CONFLICT')
        # One current authorization/freshness check covers exactly this bounded
        # response. Serving is not an acknowledgement of client receipt.
        payload = ({'page':pages[request.page_index].model_dump(mode='json')}
            if request.page_batch_size == 1 else
            {'pages':[p.model_dump(mode='json') for p in pages[request.page_index:end]]})
        return {**payload,
            'next_page':end if end < len(pages) else None,
            'status':'PROVISIONAL','reading_status':'page_served','comprehension_proven':False}

    def acknowledge(self, *, authorization, request: DomainContextAcknowledgeRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        record, context, pages = self._load(authorization,request.context_ref,request.expected_context_digest)
        row = self.store.get('domain_context_deliveries','context-delivery:'+record.record_id)
        if (not row or row.get('policy_digest') != authorization.policy_digest
                or row.get('served_pages') != list(range(len(pages)))
                or request.page_digests != tuple(p.chunk_digest for p in pages)):
            raise ValueError('DOMAIN_CONTEXT_COMPLETE_DELIVERY_REQUIRED')
        if record.payload.get('package_selection') is not None and not self.store.atomic_compare_and_write((
                AtomicWrite('domain_context_deliveries', 'context-delivery:' + record.record_id, row, row),
                *self.package_fences(authorization, record.payload['package_selection']))):
            raise ValueError('DOMAIN_CONTEXT_PACKAGE_CHANGED')
        body = {'contract_version':self.DELIVERY,'employee_id':authorization.principal,
            'policy_digest':authorization.policy_digest,'context_ref':request.context_ref.model_dump(mode='json'),
            'context_digest':context.context_digest,'source_manifest_digest':context.source_manifest_digest,
            'page_digests':list(request.page_digests),'delivered_revisions':[a.revision.model_dump(mode='json') for a in context.assets],
            'status':'acknowledged_complete','comprehension_proven':False,'semantic_equivalence_decided':False,
            'canonical_scope':record.payload['canonical_scope'],'approved':False,'canonical_projection_eligible':False}
        if 'definition_reading' in record.payload:
            body.update({key:record.payload[key] for key in
                ('definition_reading','namespace_definition_content_complete')})
        receipt = self.ledger.append(RecordKind.RUN,body,authority='migration_service',occurred_at=record.occurred_at)
        return {'reading_ref':DomainAssetStore._ref(receipt).model_dump(mode='json'), **body}

    @stage_timing('context_reading_validation')
    def validate_reading(self, *, authorization, revision: RevisionRef, sources, require_current=True,
            _source_only_saved_answer=False, _exact_metadata_successors=False):
        """Validate admission by default; historical reads keep ACL/content checks.

        require_current=False is for reading already published evidence only.
        It cannot authorize a new task, execution, candidate or completion.
        The private saved-answer option is computed by the independent answer
        reader after validating its original review and bound positive evidence.
        It is not exposed by context requests and does not waive current checks.
        """
        revision = RevisionRef.model_validate(revision)
        sources = tuple(ArtifactEnvelope.model_validate(item) for item in sources)
        cache = _CONTEXT_READING_VALIDATION.get()
        cache_key = (
            authorization.principal,
            authorization.policy_digest,
            revision.ref,
            revision.revision_digest,
            source_manifest_digest(sources),
            require_current,
            _source_only_saved_answer,
            _exact_metadata_successors,
        )
        if cache is not None and cache_key in cache:
            # Recheck caller authority and source access on every use. Only the
            # repeated immutable context/head validation is shared inside this
            # one synchronous request; no decision survives the request scope.
            self.intake._policy(authorization)
            self.assets.authorize_sources(authorization, sources, model_input=True)
            return cache[cache_key]
        record = self.ledger.read(revision.ref)
        body = record.payload
        if (record.kind != RecordKind.RUN or record_digest(record.record_id) != revision.revision_digest
                or body.get('contract_version') != self.DELIVERY or body.get('status') != 'acknowledged_complete'
                or body.get('employee_id') != authorization.principal or body.get('policy_digest') != authorization.policy_digest
                or body.get('source_manifest_digest') != source_manifest_digest(sources)):
            raise ValueError('DOMAIN_CONTEXT_READING_BINDING_DENIED')
        _, context, _ = self._load(authorization,RevisionRef.model_validate(body['context_ref']),body['context_digest'],
            require_current=require_current, _source_only_saved_answer=_source_only_saved_answer,
            _exact_metadata_successors=_exact_metadata_successors)
        if context.dependency_completeness != 'complete':
            raise ValueError('DOMAIN_CONTEXT_REQUIRED_DEPENDENCY_UNAVAILABLE')
        if cache is not None:
            if len(cache) >= 64:
                cache.clear()
            cache[cache_key] = context
        return context

    def restore(self, *, authorization, request: DomainContextRestoreRequest):
        """Read acknowledged bytes with current access checks, without a new receipt.

        Restoring historical knowledge cannot authorize new work. Start/prepare
        and candidate publication still apply their current dependency fences.
        """
        context=self.validate_reading(authorization=authorization,revision=request.reading_ref,
            sources=request.sources,require_current=False)
        acknowledgement={'reading_ref':request.reading_ref.model_dump(mode='json'),
            **self.ledger.read(request.reading_ref.ref).payload}
        return {'context':context.model_dump(mode='json'),'acknowledgement':acknowledgement,
            'reading_ref':request.reading_ref.model_dump(mode='json'),'status':'PROVISIONAL',
            'historical_read':True,'new_receipt_created':False,'new_execution_authorized':False}
