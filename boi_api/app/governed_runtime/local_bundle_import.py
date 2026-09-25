"""Resumable deterministic native preparation of confirmed uploaded bundles.

No LLM, publication, qualification, membership grant or public native head is
created here. Immutable receipts bind original bytes, exact replacements and
native revisions. Current authority and the confirmed basis fence each receipt.
"""
from datetime import datetime, timezone
import json

from .domain_asset_staging import DomainAssetStaging, StagedDomainAsset
from .domain_asset_store import DomainAssetCreateRequest
from .ledger import RecordKind, record_digest
from .local_bundle_contract import LocalBundleManifest
from .local_bundle_json import LocalJsonDocument
from .local_bundle_index import read_bundle_index
from .local_bundle_snapshot import with_bundle_snapshot
from .local_bundle_service import BUNDLES, UPLOADS
from .local_bundle_upload import LocalBundleUpload
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import byte_digest
from .source_field_projection import SourceFieldProjectionService
from ..v2.atomic_store_contract import AtomicWrite

IMPORTS = 'knowledge_local_bundle_imports'
CONTRACT = 'boi/local-bundle-native-import-item@1'
TRANSFORM = 'boi/local-native-reference-import@1'


class LocalBundleImport:
    def __init__(self, upload, *, validate_reading=None, shared_reading_binding=None):
        if not isinstance(upload, LocalBundleUpload):
            raise ValueError('LOCAL_BUNDLE_IMPORT_UPLOAD_SERVICE_REQUIRED')
        self.upload, self.service = upload, upload.service
        self.intake, self.store = self.service.intake, self.service.store
        self.stage = DomainAssetStaging(self.service.assets)
        self.fields = SourceFieldProjectionService(self.intake)
        self.validate_reading, self.shared_reading_binding = validate_reading, shared_reading_binding

    def _context(self, auth, bundle_ref):
        row = self.service._read(auth, bundle_ref)
        if row['state'] != 'receiving' or not row['confirmation']:
            raise ValueError('LOCAL_BUNDLE_IMPORT_NOT_AUTHORIZED')
        fences = list(self.service._current_basis(auth, row))
        fences.append(AtomicWrite(BUNDLES, bundle_ref, row, row))
        for receipt in self.service.upload_records(row).values():
            if not receipt or not receipt['complete']:
                raise ValueError('LOCAL_BUNDLE_IMPORT_COMPLETE_UPLOAD_REQUIRED')
        # Do not bind every chunk receipt in one CAS: immutable completed objects
        # are verified when consumed, and each receipt binds its own upload row.
        return row, tuple(fences)

    @staticmethod
    def _key(bundle_ref, object_id):
        return 'bundle-native-import:' + semantic_digest([bundle_ref, object_id])

    @staticmethod
    def scope(row):
        return 'local-confirmation:' + semantic_digest([row['bundle_ref'], row['confirmation']])

    def _binding(self, row, object_id):
        return {'contract_version':CONTRACT, 'transform_revision':TRANSFORM,
            'employee_id':row['employee_id'], 'policy_digest':row['policy']['policy_digest'],
            'bundle_ref':row['bundle_ref'], 'manifest_digest':row['manifest_digest'],
            'preview_digest':row['preview_digest'], 'confirmation_ref':self.scope(row), 'object_id':object_id}

    def _saved(self, row, object_id):
        item = self.store.get(IMPORTS, self._key(row['bundle_ref'], object_id))
        if item is None:
            return None
        record = self.intake.ledger.read(item['receipt_ref'])
        if (record.kind != RecordKind.RUN or item.get('payload_digest') != semantic_digest(record.payload)
                or any(record.payload.get(k) != v for k, v in self._binding(row, object_id).items())):
            raise ValueError('LOCAL_BUNDLE_IMPORT_RECEIPT_BINDING_MISMATCH')
        return {'receipt_ref':record.record_id, **record.payload}

    def _save(self, auth, row, object_id, result):
        fresh, fences = self._context(auth, row['bundle_ref'])
        if fresh != row:
            raise ValueError('LOCAL_BUNDLE_IMPORT_STATE_CHANGED')
        obj = next((o for o in row['manifest']['objects'] if o['object_id'] == object_id), None)
        if obj:
            upload_receipt = self.service.upload_record(row, obj)
            fences = (*fences, AtomicWrite(UPLOADS, self.service.upload_key(row['bundle_ref'], object_id),
                                           upload_receipt, upload_receipt))
        payload = {**self._binding(row, object_id), 'result':result}
        occurred = datetime.fromtimestamp(row['confirmed_at'], timezone.utc).isoformat()
        record = self.intake.ledger.append(RecordKind.RUN, payload,
            authority='migration_service', occurred_at=occurred)
        key = self._key(row['bundle_ref'], object_id)
        old = self.store.get(IMPORTS, key)
        core = {'employee_id':auth.principal, 'receipt_ref':record.record_id,
                'payload_digest':semantic_digest(payload)}
        if old is not None and any(old.get(k) != v for k,v in core.items()):
            raise ValueError('LOCAL_BUNDLE_IMPORT_RECEIPT_CONFLICT')
        summary = {'binding_digest':semantic_digest(self._binding(row,object_id)),
            'kind':'source' if 'source' in result else 'native' if 'staged' in result else 'evidence' if 'authority' in result else 'preflight'}
        if 'staged' in result:
            summary['staged'] = result['staged']
        value = {**(old or {}),**core,'summary':summary}
        if not self.store.atomic_compare_and_write((*fences, AtomicWrite(IMPORTS, key, old, value))):
            raise ValueError('LOCAL_BUNDLE_IMPORT_STATE_CHANGED')
        self._context(auth, row['bundle_ref'])
        return self._saved(row, object_id)

    def _summary(self, row, object_id):
        """Indexed preparation progress; not a source-byte verification result."""
        return self._summaries(row,(object_id,))[object_id]

    def _summaries(self, row, object_ids):
        object_ids=tuple(object_ids)
        items=read_bundle_index(self.store,IMPORTS,
            (self._key(row['bundle_ref'],object_id) for object_id in object_ids))
        return {object_id:self._summary_item(row,object_id,
            items.get(self._key(row['bundle_ref'],object_id))) for object_id in object_ids}

    def _summary_item(self, row, object_id, item):
        if item is None:
            return None
        if item.get('employee_id') != row['employee_id']:
            raise ValueError('LOCAL_BUNDLE_IMPORT_RECEIPT_BINDING_MISMATCH')
        summary = item.get('summary')
        if summary is None:
            # Preserve older receipts. They have no compact summary, so verify
            # their immutable receipt once; no source/native body is read here.
            saved = self._saved(row,object_id)
            return {'receipt_ref':saved['receipt_ref'],'legacy_receipt_read':True}
        if summary.get('binding_digest') != semantic_digest(self._binding(row,object_id)):
            raise ValueError('LOCAL_BUNDLE_IMPORT_RECEIPT_BINDING_MISMATCH')
        return {'receipt_ref':item['receipt_ref'],'legacy_receipt_read':False,
            **({'staged':summary['staged']} if 'staged' in summary else {})}

    def _raw(self, auth, row, obj):
        path = self.upload.verified_path(authorization=auth, bundle_ref=row['bundle_ref'], object_id=obj.object_id)
        with path.open('rb') as stream:
            raw = stream.read(obj.byte_length + 1)
        if len(raw) != obj.byte_length or byte_digest(raw) != obj.byte_digest:
            raise ValueError('LOCAL_BUNDLE_IMPORT_BYTES_DRIFT')
        self._context(auth, row['bundle_ref'])
        return raw

    @staticmethod
    def _document(raw, bindings, change):
        document = LocalJsonDocument(raw, (b.pointer for b in bindings))
        value = document.value
        if (not isinstance(value, dict) or set(value) != {'contract_version', 'draft', 'content'}
                or value['contract_version'] != 'boi/local-native-draft@1'
                or not isinstance(value['draft'], dict) or 'content_json' in value['draft']
                or not isinstance(value['content'], dict)):
            raise ValueError('LOCAL_BUNDLE_NATIVE_DRAFT_FORMAT_REQUIRED')
        draft = value['draft']
        expected = {k:getattr(change, k) for k in ('namespace','logical_id','kind','title')}
        expected['previous_revision'] = change.previous_revision.model_dump(mode='json') if change.previous_revision else None
        if any(draft.get(k) != v for k, v in expected.items()):
            raise ValueError('LOCAL_BUNDLE_NATIVE_DRAFT_PREVIEW_MISMATCH')
        expected_contract = ('boi/native-agent-observation@1' if change.observation_contract else
            'boi/knowledge-profile@1' if change.kind == 'profile' else 'boi/knowledge-content@1')
        if value['content'].get('contract_version') != expected_contract:
            raise ValueError('LOCAL_BUNDLE_NATIVE_CONTENT_CONTRACT_REQUIRED')
        document.check_bindings(bindings)
        return document

    def _source(self, auth, row, obj, bindings):
        source = self.intake.capture_uploaded(authorization=auth, upload=self.upload,
            bundle_ref=row['bundle_ref'], object_id=obj.object_id)
        envelope = {'kind':'artifact_ref', **{k:source[k] for k in ('artifact_ref','digest','role')}}
        locators = {b.field_locator for b in bindings if b.kind in {'source_span','source_revision_digest'}}
        selected, manifest_ref = {}, None
        if locators:
            if obj.media_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and obj.byte_length > 16*1024*1024:
                raise ValueError('LOCAL_BUNDLE_FIELD_PROJECTION_BYTE_LIMIT')
            manifest = self.fields.project(authorization=auth, reference=envelope, max_fields=100000)
            manifest_ref = manifest['manifest_ref']
            for field in manifest['fields']:
                if field['field_locator'] in locators:
                    selected[field['field_locator']] = {
                        'span':{'ref':field['span_ref'], 'revision_digest':record_digest(field['span_ref'])},
                        'source_revision_digest':manifest['source_revision_digest']}
            if set(selected) != locators:
                raise ValueError('LOCAL_BUNDLE_SOURCE_FIELD_NOT_FOUND')
        return {'source':envelope, 'original_object_ref':obj.byte_digest,
                'field_manifest_ref':manifest_ref, 'fields':selected}

    @with_bundle_snapshot
    def prepare(self, *, authorization, bundle_ref, limit=1):
        """At most ten preflight/materialization steps; resume exact prior work."""
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError('LOCAL_BUNDLE_IMPORT_STEP_LIMIT')
        self._context(authorization, bundle_ref)
        # Same local immutable upload root means all service workers share this
        # lock. The private reserved id cannot collide with a manifest LocalId.
        directory = self.upload._directory(bundle_ref, ':native-import-lock:')
        with self.upload._locked(directory):
            row, _ = self._context(authorization, bundle_ref)
            manifest = LocalBundleManifest.model_validate(row['manifest'])
            objects = {o.object_id:o for o in manifest.objects}
            changes = {c.object_id:c for c in manifest.changes}
            bindings = {o.object_id:tuple(b for b in manifest.references if b.object_id == o.object_id) for o in manifest.objects}
            remaining = limit
            if self._saved(row, ':preflight:') is None:
                # Preflight is durable bounded work too. Completing one input
                # does not authorize source capture until every proposal passed.
                preflights = self._summaries(row,(':preflight:' + c.object_id for c in manifest.changes))
                for change in manifest.changes:
                    preflight_id = ':preflight:' + change.object_id
                    if preflights[preflight_id] is not None:
                        continue
                    if remaining == 0:
                        return self.status(authorization=authorization,bundle_ref=bundle_ref)
                    raw = self._raw(authorization, row, objects[change.object_id])
                    self._document(raw, bindings[change.object_id], change)
                    self._save(authorization,row,preflight_id,{'proposal_object_id':change.object_id,
                        'byte_digest':objects[change.object_id].byte_digest,'byte_length':len(raw),
                        'proposal_format':'boi/local-native-draft@1'})
                    remaining -= 1
                self._save(authorization, row, ':preflight:', {'proposal_format':'boi/local-native-draft@1'})
            saved = self._summaries(row,(o.object_id for o in manifest.objects))
            count = 0
            while count < remaining and any(s is None for s in saved.values()):
                # Raw/check objects precede the already validated import DAG.
                ready = [o for o in manifest.objects if saved[o.object_id] is None and (
                    o.purpose != 'native_proposal' or all(saved[b.target_object_id] is not None
                        for b in bindings[o.object_id] if b.kind!='knowledge_identity'))]
                ready.sort(key=lambda o:o.purpose == 'native_proposal')
                if not ready:
                    raise ValueError('LOCAL_BUNDLE_IMPORT_DEPENDENCY_UNAVAILABLE')
                obj = ready[0]
                self._context(authorization, bundle_ref)
                if obj.purpose == 'raw_source':
                    result = self._source(authorization, row, obj,
                        [b for b in manifest.references if b.target_object_id == obj.object_id])
                else:
                    raw = self._raw(authorization, row, obj)
                    original_ref = self.intake.objects.put(raw)
                    if obj.purpose == 'check_evidence':
                        # Evidence transport is never an adopted server check.
                        LocalJsonDocument(raw, require_content=False)
                        result = {'original_object_ref':original_ref, 'authority':'external_evidence_only'}
                    else:
                        result = self._proposal(authorization, row, manifest, obj, raw, bindings[obj.object_id],
                                                changes[obj.object_id], saved)
                        result['original_object_ref'] = original_ref
                saved[obj.object_id] = self._save(authorization, row, obj.object_id, result)
                count += 1
            self._context(authorization, bundle_ref)
            return self.status(authorization=authorization, bundle_ref=bundle_ref)

    def _proposal(self, auth, row, manifest, obj, raw, bindings, change, saved):
        document = self._document(raw, bindings, change)
        # Load only the explicit source/Profile mapping dependencies of this
        # proposal. Preparing the Nth document must not read N previous bodies
        # and their raw sources again just to build an allowed-reference set.
        referenced = {object_id:self._saved(row,object_id) for object_id in {
            b.target_object_id for b in bindings if b.kind!='knowledge_identity'}}
        changes = {c.object_id:c for c in manifest.changes}
        def resolve(binding):
            if binding.kind == 'knowledge_identity':
                # Identity is server-owned and independent of content revision.
                # This matches staging exactly, including later head CAS checks.
                # It grants no equivalence, target access or physical identity.
                return self.stage._head_key(auth,changes[binding.target_object_id])
            item = referenced[binding.target_object_id]['result']
            if binding.kind == 'artifact_envelope':
                return item['source']
            if binding.kind == 'knowledge_revision':
                return item['staged']['revision']
            field = item['fields'][binding.field_locator]
            return field['span'] if binding.kind == 'source_span' else field['source_revision_digest']
        value, content_json, replacements = document.rewrite(bindings, resolve)
        request = DomainAssetCreateRequest(draft={**value['draft'], 'content_json':content_json},
            idempotency_key='local-object:' + semantic_digest([row['bundle_ref'], obj.object_id]))
        draft = request.draft
        for key in ('namespace','logical_id','kind','title','previous_revision'):
            if getattr(draft, key) != getattr(change, key):
                raise ValueError('LOCAL_BUNDLE_NATIVE_DRAFT_PREVIEW_MISMATCH')
        allowed_sources = {semantic_digest(s) for s in manifest.existing_sources}
        allowed_revisions = set(manifest.existing_revisions)
        for item in referenced.values():
            if item is None:
                continue
            result = item['result']
            if 'source' in result:
                allowed_sources.add(semantic_digest(result['source']))
            if 'staged' in result:
                handle = StagedDomainAsset.model_validate(result['staged'])
                allowed_revisions.add(handle.revision)
        if any(semantic_digest(s) not in allowed_sources for s in draft.sources):
            raise ValueError('LOCAL_BUNDLE_UNDECLARED_SOURCE')
        refs = (*[d.revision for d in draft.dependencies], *draft.conflicts_with, *draft.supersedes)
        if any(ref not in allowed_revisions for ref in refs):
            raise ValueError('LOCAL_BUNDLE_UNDECLARED_REVISION')
        if change.kind == 'profile':
            from .knowledge_profile import KnowledgeProfileDeclaration
            KnowledgeProfileDeclaration.model_validate(json.loads(content_json))
        self._context(auth, row['bundle_ref'])
        handle = self.stage.stage(authorization=auth, scope_ref=self.scope(row), request=request,
            validate_reading=self.validate_reading, shared_reading_binding=self.shared_reading_binding)
        return {'staged':handle.model_dump(mode='json'), 'replacements':replacements,
            'content_object_ref':byte_digest(content_json.encode('utf-8')),
            'structural_validation':'native_draft_and_evidence_checks', 'semantic_status':'not_evaluated'}

    def status(self, *, authorization, bundle_ref, verify_bytes=False):
        row, _ = self._context(authorization, bundle_ref)
        items = []
        summaries = self._summaries(row,(
            *[obj['object_id'] for obj in row['manifest']['objects']],
            ':preflight:', *[':preflight:' + c['object_id'] for c in row['manifest']['changes']]))
        for obj in row['manifest']['objects']:
            saved = self._saved(row, obj['object_id']) if verify_bytes else summaries[obj['object_id']]
            if verify_bytes and saved and 'source' in saved['result']:
                self.intake.resolve_bytes(authorization=authorization, reference=saved['result']['source'])
            if verify_bytes and saved and 'staged' in saved['result']:
                handle = StagedDomainAsset.model_validate(saved['result']['staged'])
                self.stage.read(authorization=authorization, scope_ref=self.scope(row), revision=handle.revision, model_input=False)
            items.append({'object_id':obj['object_id'], 'prepared':saved is not None,
                          'receipt_ref':saved['receipt_ref'] if saved else None})
        self._context(authorization, bundle_ref)
        preflight_complete = summaries[':preflight:'] is not None
        preflight_checked = (len(row['manifest']['changes']) if preflight_complete else
            sum(summaries[':preflight:' + c['object_id']] is not None for c in row['manifest']['changes']))
        return {'bundle_ref':bundle_ref, 'confirmation_ref':self.scope(row), 'items':items,
            'preflight':{'complete':preflight_complete,'checked':preflight_checked,'total':len(row['manifest']['changes'])},
            'verification':'current_bytes_checked' if verify_bytes else 'recorded_preparation_progress',
            'state':'native_preflight_partial' if not preflight_complete else
                    'native_prepared_requires_qualification' if all(i['prepared'] for i in items) else 'native_preparation_partial',
            'publication_committed':False, 'query_ready':False, 'semantic_status':'not_evaluated'}
