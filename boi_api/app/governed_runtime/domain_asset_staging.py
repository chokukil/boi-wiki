"""Private native revision preparation and exact batch publication writes.

Only a server workflow that has resolved upload/confirmation authority uses this
service. It does not confirm a bundle, qualify its semantics or expose an endpoint.
All content remains in the existing immutable ledger/object store. Normal native
readers only see revisions after the final publication CAS writes their index rows.
"""
from itertools import islice

from .domain_asset_store import DomainAssetCreateRequest, DomainAssetDraft, source_manifest_digest
from .ledger import RecordKind
from .knowledge_projection_contract import ProjectionPublication
from .semantic_binding_contract import FrozenContract, Ref, RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite, prepare_atomic_writes, atomic_json_wire


REQUESTS = 'domain_asset_staging_requests'
REVISIONS = 'domain_asset_staging_revisions'


class StagedDomainAsset(FrozenContract):
    scope_ref: Ref
    request_key: Ref
    revision: RevisionRef
    native_identity: Ref
    previous_revision: RevisionRef | None
    reused_published_revision: bool


def merge_writes(writes, fences=()):
    """Coalesce exact read fences with intended writes, never differing updates."""
    result = {}
    for write in writes:
        key = (write.collection, write.key)
        old = result.get(key)
        if old is None:
            result[key] = write
            continue
        if atomic_json_wire(old.expected) != atomic_json_wire(write.expected):
            raise ValueError('DOMAIN_ASSET_STAGING_FENCE_CONFLICT')
        if (atomic_json_wire(old.value) == atomic_json_wire(write.value)
                or atomic_json_wire(write.value) == atomic_json_wire(write.expected)):
            continue
        if atomic_json_wire(old.value) == atomic_json_wire(old.expected):
            result[key] = write
        else:
            raise ValueError('DOMAIN_ASSET_STAGING_WRITE_CONFLICT')
    for fence in fences:
        key = (fence.collection, fence.key)
        old = result.get(key)
        if old is None:
            result[key] = fence
        elif atomic_json_wire(old.expected) != atomic_json_wire(fence.expected):
            raise ValueError('DOMAIN_ASSET_STAGING_FENCE_CONFLICT')
    return prepare_atomic_writes(result.values())


class DomainAssetStaging:
    def __init__(self, assets):
        self.assets, self.store = assets, assets.store

    @staticmethod
    def _revision_key(authorization, scope_ref, revision):
        return 'domain-staged-revision:' + semantic_digest([authorization.principal, scope_ref, revision.model_dump(mode='json')])

    @staticmethod
    def _head_key(authorization, draft):
        return 'domain-asset-head:' + semantic_digest([authorization.principal, draft.namespace, draft.logical_id])

    def _index(self, authorization, scope_ref, revision):
        index = self.store.get(REVISIONS, self._revision_key(authorization, scope_ref, revision))
        if (not index or index.get('employee_id') != authorization.principal
                or index.get('policy_digest') != authorization.policy_digest
                or index.get('scope_ref') != scope_ref or index.get('revision') != revision.model_dump(mode='json')):
            raise ValueError('DOMAIN_ASSET_STAGED_REVISION_UNAVAILABLE')
        return index

    def read(self, *, authorization, scope_ref, revision, model_input=True):
        """Private exact-scope read, reusing native owner/source/bytes checks."""
        revision = RevisionRef.model_validate(revision.model_dump(mode='json'))
        index = self._index(authorization, scope_ref, revision)
        record = self.assets._record_metadata(authorization, revision, model_input=model_input,
            publication=index, staged_scope_ref=scope_ref)
        asset = self.assets._asset(record, revision, self.assets.objects.get(record.payload['content_object_ref']))
        return record, asset

    def _resolve(self, authorization, scope_ref, revision, *, included=None):
        publication = self.store.get('domain_knowledge_assets', revision.ref)
        if publication is not None:
            return self.assets._read_record(authorization, revision)
        if included is not None and revision not in included:
            raise ValueError('DOMAIN_ASSET_STAGED_DEPENDENCY_NOT_IN_BATCH')
        return self.read(authorization=authorization, scope_ref=scope_ref, revision=revision)

    @staticmethod
    def _draft(record, asset):
        values = {key: record.payload[key] for key in DomainAssetDraft.model_fields
                  if key != 'content_json' and key in record.payload}
        return DomainAssetDraft(content_json=asset.content_json, **values)

    @staticmethod
    def _review_reading(draft, validate_reading):
        if draft.kind != 'pack':
            return
        from .local_native_review import parse_review_draft, validate_review_reading
        parse_review_draft(draft)
        if validate_reading is None:
            raise ValueError('DOMAIN_ASSET_READING_RESOLVER_REQUIRED')
        validate_review_reading(draft, validate_reading(draft.definition_reading_ref, draft.sources))

    def stage(self, *, authorization, scope_ref, request, validate_reading=None, shared_reading_binding=None):
        if not isinstance(scope_ref, str) or not scope_ref.strip() or len(scope_ref) > 2048:
            raise ValueError('DOMAIN_ASSET_STAGING_SCOPE_REQUIRED')
        request = DomainAssetCreateRequest.model_validate(request.model_dump(mode='json'))
        draft = request.draft
        material, fingerprint = self.assets._draft_material(authorization, draft)
        key = 'domain-stage-request:' + semantic_digest([authorization.principal, scope_ref, request.idempotency_key])
        reserved = self.store.get(REQUESTS, key)
        if reserved and reserved.get('fingerprint') != fingerprint:
            raise ValueError('DOMAIN_ASSET_STAGING_IDEMPOTENCY_CONFLICT')
        # Reading a persisted result does not re-run the old context selection.
        # Publication separately revalidates current reading/heads/authorization.
        if reserved and reserved.get('result'):
            result = StagedDomainAsset.model_validate(reserved['result'])
            self.read(authorization=authorization, scope_ref=scope_ref, revision=result.revision, model_input=False)
            return result
        self._review_reading(draft, validate_reading)
        self.assets._validate_draft_references(authorization, draft, validate_reading=validate_reading,
            shared_reading_binding=shared_reading_binding,
            reference_resolver=lambda ref: self._resolve(authorization, scope_ref, ref))
        head_key = self._head_key(authorization, draft)
        head = self.store.get('domain_asset_heads', head_key)
        current = RevisionRef.model_validate(head['revision']) if head else None
        reused = bool(head and head.get('fingerprint') == fingerprint)
        if not reused and current != draft.previous_revision:
            raise ValueError('DOMAIN_ASSET_PREVIOUS_REVISION_CONFLICT')
        if current:
            previous, _ = self.assets._read_record(authorization, current, model_input=False)
            if previous.payload['kind'] != draft.kind:
                raise ValueError('DOMAIN_ASSET_KIND_CHANGE_REQUIRES_NEW_IDENTITY')
        if reserved is None:
            value = {'scope_ref':scope_ref, 'employee_id':authorization.principal,
                     'policy_digest':authorization.policy_digest, 'fingerprint':fingerprint,
                     'occurred_at':self.assets.intake.clock().isoformat(), 'result':None,
                     'base_revision':current.model_dump(mode='json') if current else None,
                     'reused_published_revision':reused}
            self.store.atomic_compare_and_write((AtomicWrite(REQUESTS, key, None, value),))
            reserved = self.store.get(REQUESTS, key)
        if not reserved or reserved.get('fingerprint') != fingerprint:
            raise ValueError('DOMAIN_ASSET_STAGING_IDEMPOTENCY_CONFLICT')
        if reserved.get('result'):
            result = StagedDomainAsset.model_validate(reserved['result'])
            self.read(authorization=authorization, scope_ref=scope_ref, revision=result.revision, model_input=False)
            return result
        if reserved['base_revision'] != (current.model_dump(mode='json') if current else None):
            raise ValueError('DOMAIN_ASSET_STAGING_BASE_CHANGED')
        self.assets.objects.put(draft.content_json.encode('utf-8'))
        if reused:
            record = previous
        else:
            record = self.assets.ledger.append(RecordKind.KNOWLEDGE_REVISION, material,
                authority='agent', occurred_at=reserved['occurred_at'])
        revision = self.assets._ref(record)
        result = StagedDomainAsset(scope_ref=scope_ref, request_key=key, revision=revision,
            native_identity=head_key, previous_revision=current, reused_published_revision=reused)
        index_key = self._revision_key(authorization, scope_ref, revision)
        index = self.store.get(REVISIONS, index_key)
        row = {'scope_ref':scope_ref, 'employee_id':authorization.principal, 'policy_digest':authorization.policy_digest,
               'revision':revision.model_dump(mode='json'), 'record_payload_digest':semantic_digest(record.payload)}
        if index and any(index.get(k) != value for k, value in row.items()):
            raise ValueError('DOMAIN_ASSET_STAGING_REVISION_CONFLICT')
        writes = [AtomicWrite(REQUESTS, key, reserved, {**reserved, 'result':result.model_dump(mode='json')})]
        writes.append(AtomicWrite(REVISIONS, index_key, index, index or row))
        if not self.store.atomic_compare_and_write(writes):
            recovered = self.store.get(REQUESTS, key)
            if not recovered or recovered.get('result') != result.model_dump(mode='json'):
                raise ValueError('DOMAIN_ASSET_STAGING_WRITE_CONFLICT')
        return result

    def publication_writes(self, *, authorization, manifest, staged, validate_reading=None, shared_reading_binding=None):
        """Exact native writes to add to the coordinator's final public CAS.

        Admission must additionally bind confirmed intent, registered qualifications,
        current policy and membership. These writes alone do not grant those rights.
        """
        manifest = ProjectionPublication.model_validate(manifest.model_dump(mode='json'))
        handles = tuple(islice(iter(staged), 501))
        if not handles or len(handles) > 500:
            raise ValueError('DOMAIN_ASSET_STAGING_BATCH_LIMIT')
        handles = tuple(StagedDomainAsset.model_validate(h.model_dump(mode='json')) for h in handles)
        if manifest.principal_id != authorization.principal or manifest.policy_digest != authorization.policy_digest:
            raise ValueError('DOMAIN_ASSET_STAGING_MANIFEST_AUTHORITY_MISMATCH')
        if any(h.scope_ref != manifest.confirmation_ref for h in handles):
            raise ValueError('DOMAIN_ASSET_STAGING_CONFIRMATION_SCOPE_MISMATCH')
        if len({h.native_identity for h in handles}) != len(handles):
            raise ValueError('DOMAIN_ASSET_DUPLICATE_BATCH_HEAD')
        def wire(ref):
            return ref.model_dump(mode='json') if ref else None
        expected = {c.stable_id: (wire(c.previous_revision), wire(c.revision)) for c in manifest.changes if c.operation == 'upsert'}
        if (len(expected) != len(manifest.changes) or expected != {
                h.native_identity:(wire(h.previous_revision), wire(h.revision)) for h in handles}):
            raise ValueError('DOMAIN_ASSET_STAGING_MANIFEST_SET_MISMATCH')
        included = frozenset(h.revision for h in handles)
        writes, changes, sources, fences, namespaces = [], [], {}, [], set()
        for handle in handles:
            reservation = self.store.get(REQUESTS, handle.request_key)
            if not reservation or reservation.get('result') != handle.model_dump(mode='json'):
                raise ValueError('DOMAIN_ASSET_STAGING_HANDLE_MISMATCH')
            record, asset = self.read(authorization=authorization, scope_ref=handle.scope_ref,
                                      revision=handle.revision, model_input=False)
            draft = self._draft(record, asset)
            namespaces.add(draft.namespace)
            material, fingerprint = self.assets._draft_material(authorization, draft)
            if fingerprint != reservation['fingerprint'] or semantic_digest(record.payload) != fingerprint:
                raise ValueError('DOMAIN_ASSET_STAGING_CONTENT_DRIFT')
            if self._head_key(authorization, draft) != handle.native_identity:
                raise ValueError('DOMAIN_ASSET_STAGING_IDENTITY_MISMATCH')
            self._review_reading(draft, validate_reading)
            reading = self.assets._validate_draft_references(authorization, draft,
                validate_reading=validate_reading, shared_reading_binding=shared_reading_binding,
                reference_resolver=lambda ref: self._resolve(authorization, handle.scope_ref, ref, included=included))
            for source in draft.sources:
                old = sources.get(source.artifact_ref)
                if old is not None and old != source:
                    raise ValueError('DOMAIN_ASSET_STAGING_SOURCE_CONFLICT')
                sources[source.artifact_ref] = source
            head = self.store.get('domain_asset_heads', handle.native_identity)
            current = RevisionRef.model_validate(head['revision']) if head else None
            if current != handle.previous_revision:
                raise ValueError('DOMAIN_ASSET_STAGING_PREVIEW_CHANGED')
            _, row = self.assets._publication_metadata(draft, material, fingerprint, record)
            prior = self.store.get('domain_knowledge_assets', handle.revision.ref)
            if prior is not None:
                from .native_contract_catalog import preserve_contract_preparation
                row = preserve_contract_preparation(row, prior)
            writes.append(AtomicWrite('domain_asset_heads', handle.native_identity, head,
                                      head if handle.reused_published_revision else row))
            if prior is not None and prior.get('record_payload_digest') != row['record_payload_digest']:
                raise ValueError('DOMAIN_ASSET_PROJECTION_DRIFT')
            writes.append(AtomicWrite('domain_knowledge_assets', handle.revision.ref, prior, prior or row))
            if prior is None:
                writes.append(self.assets._text_projection_write(draft,record))
            writes.append(AtomicWrite(REQUESTS, handle.request_key, reservation, reservation))
            if not handle.reused_published_revision or manifest.projection_mode == 'bootstrap':
                changes.append((draft.namespace, handle.native_identity, draft.kind))
            fences.extend(reading)
        if source_manifest_digest(sources.values()) != manifest.source_manifest_digest:
            raise ValueError('DOMAIN_ASSET_STAGING_SOURCE_MANIFEST_MISMATCH')
        if manifest.base_generation == 0:
            # Initial migration is a closed native namespace population, including
            # unprepared/unknown rows. No JSON document scan occurs on query reads.
            expected_heads = {h.native_identity for h in handles}
            for namespace in namespaces:
                key = self.assets.catalog_key(authorization, namespace)
                row = self.store.get('domain_asset_catalogs', key)
                fences.append(AtomicWrite('domain_asset_catalogs', key, row, row or {
                    'employee_id':authorization.principal, 'namespace':namespace, 'epoch':0}))
            after, scanned = '', 0
            while True:
                page = self.store.list_key_page('domain_asset_heads', employee_id=authorization.principal,
                                               after_key=after, limit=100)
                for item in page:
                    if item['value']['namespace'] in namespaces and item['key'] not in expected_heads:
                        raise ValueError('DOMAIN_ASSET_BOOTSTRAP_POPULATION_INCOMPLETE')
                if not page or len(page) < 100:
                    break
                after = page[-1]['key']
                scanned += len(page)
                if scanned >= 50000:
                    raise ValueError('DOMAIN_ASSET_BOOTSTRAP_SCAN_BOUND_EXCEEDED')
            if any(h.previous_revision is not None for h in handles) and manifest.projection_mode != 'bootstrap':
                raise ValueError('DOMAIN_ASSET_BOOTSTRAP_MODE_REQUIRED')
        writes.extend(self.assets._catalog_update_writes(authorization, changes, generation_scope_id=manifest.scope_id))
        return merge_writes(writes, fences)
