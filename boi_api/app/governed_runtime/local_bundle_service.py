"""Confirmed local uploads over native policy/head state and the shared CAS store.

This service grants transport of an exact intent. It does not grant publication,
use qualification or install uploaded code. Received bytes remain private until
native intake/validation/publication consumes them through its own contracts.
"""
from dataclasses import dataclass
import hmac
import json
import secrets
import time
from pydantic import TypeAdapter

from .domain_asset_store import DomainAssetStore
from .local_bundle_contract import (CHUNK_BYTES, LocalBundleManifest, LocalBundlePreviewRequest,
    LocalBundleReadRequest, LocalBundleConfirmRequest, LocalPublicationRequest, LocalBundleListRequest)
from .semantic_binding_contract import Digest, RevisionRef, semantic_digest
from .knowledge_space_contract import KnowledgeSpaceTarget, KnowledgeSpaceIntentAdmission
from .local_bundle_index import read_bundle_index
from ..v2.atomic_store_contract import AtomicWrite

BUNDLES = 'knowledge_local_bundles'
CHALLENGES = 'knowledge_local_bundle_challenges'
UPLOADS = 'knowledge_local_bundle_uploads'
_DIGEST_ADAPTER = TypeAdapter(Digest)


@dataclass(frozen=True)
class VerifiedWebSession:
    """Created only by the signed browser-cookie transport, never parsed from JSON."""
    principal_id: str
    session_digest: str
    auth_source: str = ''
    actor: str = ''
    delegation_ref: str = ''


@dataclass(frozen=True)
class VerifiedHotlPrincipal:
    """Server transport/current-policy evidence; never deserialized from JSON."""
    principal_id: str
    authority_digest: str
    fences: tuple


class LocalBundleService:
    def __init__(self, intake, *, clock=time.time, current_authorizer=None, space_authorizer=None, space_access=None,
            publication_factory=None, impact_factory=None, hotl_authorizer=None, validate_reading=None, shared_reading_binding=None, delivery_authorizer=None):
        self.intake, self.store, self.clock = intake, intake.store, clock
        self.current_authorizer = current_authorizer
        self.space_authorizer = space_authorizer
        self.publication_factory = publication_factory
        self.impact_factory = impact_factory
        self.delivery_authorizer = delivery_authorizer
        self.hotl_authorizer = hotl_authorizer
        self.validate_reading, self.shared_reading_binding = validate_reading, shared_reading_binding
        self.assets = DomainAssetStore(intake, space_access=space_access)

    def _policy(self, auth):
        policy = self.intake._policy(auth)
        if self.current_authorizer is not None and self.intake._policy(self.current_authorizer()) != policy:
            raise ValueError('LOCAL_BUNDLE_POLICY_CHANGED')
        if not {'store', 'derive'} <= set(auth.allowed_uses):
            raise ValueError('LOCAL_BUNDLE_NOT_AUTHORIZED')
        return policy

    def _space(self, auth, target):
        if self.space_authorizer is None:
            raise ValueError('LOCAL_BUNDLE_SPACE_AUTHORITY_UNAVAILABLE')
        admitted = self.space_authorizer(target)
        if (not isinstance(admitted, KnowledgeSpaceIntentAdmission)
                or admitted.principal_id != auth.principal or admitted.target != target):
            raise ValueError('LOCAL_BUNDLE_SPACE_NOT_AUTHORIZED')
        return {'target':target.model_dump(mode='json'), 'authority_digest':admitted.authority_digest,
            'audience':admitted.audience, 'owner':auth.principal, 'membership_committed':False}

    def _delivery(self, auth, selector):
        if selector is None:
            return None
        if not callable(self.delivery_authorizer):
            raise ValueError('DELIVERY_RECIPIENT_AUTHORITY_REQUIRED')
        destination = self.delivery_authorizer(selector)
        if (destination.get('owner') != auth.principal
                or destination.get('recipient') != selector
                or destination.get('target_space') != {'visibility':'private','team_id':None}):
            raise ValueError('DELIVERY_RECIPIENT_DESTINATION_MISMATCH')
        return destination

    def _head_key(self, auth, change):
        return 'domain-asset-head:' + semantic_digest([auth.principal, change.namespace, change.logical_id])

    def _basis(self, auth, manifest, *, verify_head_access=True, include_preview_rows=True):
        self.assets.authorize_sources(auth, manifest.existing_sources, metadata_only=True)
        for revision in manifest.existing_revisions:
            self.assets._record_metadata(auth, revision, model_input=False, metadata_only=True)
        heads, catalogs, rows, fences = [], [], [], []
        current_heads = read_bundle_index(self.store, 'domain_asset_heads',
            (self._head_key(auth, change) for change in manifest.changes))
        for change in manifest.changes:
            if change.correction is not None and include_preview_rows:
                from .knowledge_content_correction import correction_basis
                _, _, fence = correction_basis(self.assets, auth, change, manifest.target_space)
                fences.append(fence)
            key = self._head_key(auth, change)
            head = current_heads.get(key)
            current = RevisionRef.model_validate(head['revision']) if head else None
            if current and verify_head_access:
                record = self.assets._record_metadata(auth, current, model_input=False, metadata_only=True)
                if (record.payload['namespace'], record.payload['logical_id']) != (change.namespace, change.logical_id):
                    raise ValueError('LOCAL_BUNDLE_CURRENT_IDENTITY_MISMATCH')
            heads.append({'key':key, 'revision':current.model_dump(mode='json') if current else None})
            # Absent heads are covered by a catalog fence, not a fabricated head.
            if head is not None:
                fences.append(AtomicWrite('domain_asset_heads', key, head, head))
            if include_preview_rows:
                rows.append({**change.model_dump(mode='json'), 'current_revision':heads[-1]['revision'],
                             'head_conflict':current != change.previous_revision,
                             'current_title':head.get('title') if head else None})
        for namespace in sorted({x.namespace for x in manifest.changes}):
            key = self.assets.catalog_key(auth, namespace)
            row = self.store.get('domain_asset_catalogs', key)
            catalogs.append({'key':key, 'namespace':namespace, 'epoch':(row or {}).get('epoch', 0)})
            fences.append(AtomicWrite('domain_asset_catalogs', key, row, row or {
                'employee_id':auth.principal, 'namespace':namespace, 'epoch':0}))
        return {'heads':heads, 'catalogs':catalogs}, rows, tuple(fences)

    def preview(self, *, authorization, request):
        from .publication_capacity import initial_publication_capacity
        req = LocalBundlePreviewRequest.model_validate(request)
        manifest = req.manifest
        wire = manifest.model_dump(mode='json')
        if len(json.dumps(wire, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
            raise ValueError('LOCAL_BUNDLE_MANIFEST_BYTE_LIMIT')
        policy = self._policy(authorization)
        sharing = self._space(authorization, manifest.target_space)
        delivery = self._delivery(authorization, manifest.delivery_recipient)
        reference = 'local-bundle:' + semantic_digest([authorization.principal, req.idempotency_key])
        existing = self.store.get(BUNDLES, reference)
        if existing:
            row = self._read(authorization, reference)
            if row['manifest_digest'] != manifest.digest:
                raise ValueError('LOCAL_BUNDLE_IDEMPOTENCY_CONFLICT')
            return self.view(authorization=authorization, bundle_ref=reference)
        basis, changes, fences = self._basis(authorization, manifest)
        preview = {'manifest_digest':manifest.digest, 'policy':policy, 'basis':basis,
            'changes':changes, 'total_bytes':sum(x.byte_length for x in manifest.objects),
            'object_count':len(manifest.objects), 'sharing':sharing,
            'impact':{'head_conflicts':sum(x['head_conflict'] for x in changes),
                'semantic_conflicts':'not_evaluated', 'dependent_knowledge':'not_evaluated'},
            'validation':{'uploaded_checks':'external_evidence_only', 'server_checks':'pending_upload',
                          'query_qualification':'not_granted'},
            'publication_capacity':initial_publication_capacity(manifest.changes),
            'intent':'validate_then_publish_exact_bundle', 'source_bytes_received':False}
        if delivery is not None:
            preview['delivery_destination'] = delivery
        if manifest.publication_layout is not None:
            from .local_publication_plan import plan_publication_units
            plan=plan_publication_units(manifest)
            preview['publication_plan']=plan
            preview['publication_capacity']={**preview['publication_capacity'],
                'status':'atomic_unit_plan_required' if plan['blocked'] else 'unit_plan_prepared_exact_preflight_required',
                'atomic_unit_planner_available':True,'unit_count':len(plan['units'])}
        row = {'contract_version':'boi/local-bundle@1', 'bundle_ref':reference,
            'employee_id':authorization.principal, 'policy':policy, 'manifest':wire,
            'manifest_digest':manifest.digest, 'preview':preview, 'preview_digest':semantic_digest(preview),
            'state':'awaiting_confirmation', 'created_at':self.clock(), 'confirmation':None}
        if not self.store.atomic_compare_and_write((*fences, AtomicWrite(BUNDLES, reference, None, row))):
            recovered = self.store.get(BUNDLES, reference)
            if recovered and recovered.get('manifest_digest') == manifest.digest:
                return self.view(authorization=authorization, bundle_ref=reference)
            raise ValueError('LOCAL_BUNDLE_PREVIEW_BASIS_CHANGED')
        return self.view(authorization=authorization, bundle_ref=reference)

    def _read(self, auth, bundle_ref):
        from .local_bundle_snapshot import read_bundle_snapshot, verified_bundle_binding
        LocalBundleReadRequest(bundle_ref=bundle_ref)
        policy = self._policy(auth)
        row, binding_verified = read_bundle_snapshot(self, auth, bundle_ref)
        if not row or row.get('employee_id') != auth.principal:
            raise ValueError('LOCAL_BUNDLE_ACCESS_DENIED')
        delivery = self._delivery(auth, row['manifest'].get('delivery_recipient'))
        if delivery != row['preview'].get('delivery_destination'):
            raise ValueError('DELIVERY_RECIPIENT_DESTINATION_CHANGED')
        if row.get('policy') != policy:
            raise ValueError('LOCAL_BUNDLE_POLICY_CHANGED')
        if self._space(auth, KnowledgeSpaceTarget.model_validate(row['manifest']['target_space'])) != row['preview']['sharing']:
            raise ValueError('LOCAL_BUNDLE_SPACE_POLICY_CHANGED')
        if not binding_verified and (semantic_digest(row['manifest']) != row['manifest_digest']
                or semantic_digest(row['preview']) != row['preview_digest']
                or row['preview']['manifest_digest'] != row['manifest_digest'] or row['preview']['policy'] != policy):
            raise ValueError('LOCAL_BUNDLE_RECORD_BINDING_MISMATCH')
        verified_bundle_binding(self, row)
        if self._is_hotl(row):
            proof = row['confirmation']
            expected = {'principal_id':auth.principal, 'manifest_digest':row['manifest_digest'],
                'preview_digest':row['preview_digest'], 'policy_digest':auth.policy_digest,
                'auth_source':'pat', 'human_confirmation_observed':False}
            if any(proof.get(key) != value for key, value in expected.items()):
                raise ValueError('LOCAL_BUNDLE_HOTL_RECORD_BINDING_MISMATCH')
            _DIGEST_ADAPTER.validate_python(proof.get('authority_basis_digest'))
            self._hotl_authority(auth, row)
        return row

    @staticmethod
    def _is_hotl(row):
        return (row.get('confirmation') or {}).get('mechanism') == 'authenticated_hotl_admission'

    def _hotl_authority(self, auth, row):
        if not callable(self.hotl_authorizer):
            raise ValueError('LOCAL_BUNDLE_HOTL_AUTHORITY_REQUIRED')
        proof = self.hotl_authorizer()
        if (not isinstance(proof, VerifiedHotlPrincipal) or proof.principal_id != auth.principal
                or not {'store', 'derive', 'model_input'} <= set(auth.allowed_uses)):
            raise ValueError('LOCAL_BUNDLE_HOTL_NOT_AUTHORIZED')
        _DIGEST_ADAPTER.validate_python(proof.authority_digest)
        from .local_bundle_snapshot import bundle_manifest
        manifest = bundle_manifest(self, row)
        self.assets.authorize_sources(auth, manifest.existing_sources, model_input=True, metadata_only=True)
        refs = {*manifest.existing_revisions,
            *(c.previous_revision for c in manifest.changes if c.previous_revision is not None)}
        for revision in refs:
            self.assets._record_metadata(auth, revision, model_input=True, metadata_only=True)
        return proof

    def _current_basis(self, auth, row):
        from .local_publication_state import effective_bundle_basis
        from .local_bundle_snapshot import bundle_manifest
        # Progress compares already-confirmed head identifiers, without reading
        # every previously published body/source/policy again. The preview and
        # each actual target/dependency read still authorize its content.
        basis, _, fences = self._basis(auth, bundle_manifest(self,row),verify_head_access=False,include_preview_rows=False)
        if basis != effective_bundle_basis(self.store,row):
            raise ValueError('LOCAL_BUNDLE_PREVIEW_BASIS_CHANGED')
        if self._is_hotl(row):
            fences = (*fences, *self._hotl_authority(auth, row).fences)
        return fences

    def view(self, *, authorization, bundle_ref):
        row = self._read(authorization, bundle_ref)
        basis_current = True
        try:
            self._current_basis(authorization, row)
        except ValueError as exc:
            if str(exc) != 'LOCAL_BUNDLE_PREVIEW_BASIS_CHANGED':
                raise
            basis_current = False
        uploads = []
        upload_records = self.upload_records(row)
        for obj in row['manifest']['objects']:
            item = upload_records[obj['object_id']]
            uploads.append({'object_id':obj['object_id'], 'byte_length':obj['byte_length'],
                'received_bytes':sum(part['byte_length'] for part in (item or {}).get('parts', {}).values()),
                'received_offsets':sorted(int(k) for k in (item or {}).get('parts', {})),
                'complete':bool((item or {}).get('complete', False))})
        uploaded = all(x['complete'] for x in uploads)
        result = {'contract_version':row['contract_version'], 'bundle_ref':bundle_ref,
            'manifest':row['manifest'], 'manifest_digest':row['manifest_digest'],
            'preview':row['preview'], 'preview_digest':row['preview_digest'],
            'state':('uploaded_requires_validation' if row['state'] == 'receiving' and uploaded else row['state']),
            'basis_current':basis_current, 'confirmation_recorded':row['confirmation'] is not None and not self._is_hotl(row),
            'admission_recorded':self._is_hotl(row),
            'confirmation_context':self.confirmation_context(row),
            'impact_review_required':self.impact_factory is not None and row['confirmation'] is None,
            'confirmed_impact_ref':(row['confirmation'] or {}).get('impact_ref'),
            'uploads':uploads, 'upload_limits':{'chunk_bytes':CHUNK_BYTES, 'parallel_requests':4},
            'confirmation_url':'/knowledge/local-bundles/' + bundle_ref.removeprefix('local-bundle:sha256:'),
            'publication_committed':False, 'query_ready':False}
        from .local_publication_state import unit_progress,publication_status
        progress=unit_progress(self.store,row)
        if progress is not None:
            result['publication_progress']=progress
            result['publication_committed']=progress['publication_committed']
            result['state']=publication_status(result['state'],progress)
        return result

    def hotl_impact(self, *, authorization, request):
        from .local_bundle_contract import LocalBundleHotlImpactRequest
        req = LocalBundleHotlImpactRequest.model_validate(request)
        row = self._read(authorization, req.bundle_ref)
        self._hotl_authority(authorization, row)
        if row['preview_digest'] != req.preview_digest:
            raise ValueError('LOCAL_BUNDLE_HOTL_BINDING_MISMATCH')
        if self.impact_factory is None:
            return {'bundle_ref':req.bundle_ref, 'preview_digest':req.preview_digest,
                'impact_ref':None, 'coverage':'reference_backend_unavailable', 'publication_authorized':False}
        return self.impact_factory(self).prepare(authorization=authorization,
            bundle_ref=req.bundle_ref, preview_digest=req.preview_digest, purpose='model_input')

    def admit(self, *, authorization, request):
        """Admit exact bytes under existing authenticated write rights, without human consent fiction."""
        from .local_bundle_contract import LocalBundleHotlAdmitRequest
        from .domain_asset_staging import merge_writes
        req = LocalBundleHotlAdmitRequest.model_validate(request)
        row = self._read(authorization, req.bundle_ref)
        actor = self._hotl_authority(authorization, row)
        if req.manifest_digest != row['manifest_digest'] or req.preview_digest != row['preview_digest']:
            raise ValueError('LOCAL_BUNDLE_HOTL_BINDING_MISMATCH')
        prior = row.get('confirmation')
        if prior is not None:
            if not self._is_hotl(row) or prior.get('impact_ref') != req.impact_ref:
                raise ValueError('LOCAL_BUNDLE_HOTL_ADMISSION_CONFLICT')
            if row['state'] != 'receiving':
                raise ValueError('LOCAL_BUNDLE_HOTL_ADMISSION_CLOSED')
            self._current_basis(authorization, row)
            self._impact_fences(authorization, row, req.impact_ref)
            return self.view(authorization=authorization, bundle_ref=req.bundle_ref)
        if row['state'] != 'awaiting_confirmation':
            raise ValueError('LOCAL_BUNDLE_HOTL_ADMISSION_CLOSED')
        if row['preview']['impact']['head_conflicts']:
            raise ValueError('LOCAL_BUNDLE_HEAD_CONFLICT_REQUIRES_NEW_PREVIEW')
        self._require_possible_capacity(row)
        if self.impact_factory is not None:
            impact = self.impact_factory(self)
            review = impact._read(authorization, row, req.impact_ref)
            if review.get('purpose') != 'model_input':
                raise ValueError('LOCAL_BUNDLE_HOTL_MODEL_INPUT_IMPACT_REQUIRED')
        elif any(c['operation'] != 'create' for c in row['manifest']['changes']):
            raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_REQUIRED')
        fences = (*self._current_basis(authorization, row),
            *self._impact_fences(authorization, row, req.impact_ref), *actor.fences)
        proof = {'mechanism':'authenticated_hotl_admission', 'principal_id':authorization.principal,
            'auth_source':'pat', 'actor':authorization.principal, 'participation':'authenticated_hotl',
            'human_confirmation_observed':False, 'authority_basis_digest':actor.authority_digest,
            'manifest_digest':req.manifest_digest, 'preview_digest':req.preview_digest,
            'policy_digest':authorization.policy_digest, 'impact_ref':req.impact_ref}
        # Keep the historical envelope/receipt binding for downstream consumers;
        # its mechanism identifies admission and never claims a signed web event.
        value = {**row, 'state':'receiving', 'confirmation':proof, 'confirmed_at':self.clock()}
        if not self.store.atomic_compare_and_write(merge_writes(
                (AtomicWrite(BUNDLES, req.bundle_ref, row, value),), fences)):
            recovered = self._read(authorization, req.bundle_ref)
            if recovered.get('confirmation') != proof or recovered['state'] != 'receiving':
                raise ValueError('LOCAL_BUNDLE_HOTL_STATE_CHANGED')
        fresh = self._read(authorization, req.bundle_ref)
        if fresh.get('confirmation') != proof:
            raise ValueError('LOCAL_BUNDLE_HOTL_STATE_CHANGED')
        self._current_basis(authorization, fresh)
        self._impact_fences(authorization, fresh, req.impact_ref)
        return self.view(authorization=authorization, bundle_ref=req.bundle_ref)

    def _impact_fences(self, auth, row, impact_ref):
        if self.impact_factory is None:
            if impact_ref is not None:
                raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_UNAVAILABLE')
            return ()
        return self.impact_factory(self).confirmation_fences(authorization=auth,row=row,impact_ref=impact_ref)

    def challenge(self, *, authorization, bundle_ref, session, impact_ref=None):
        self._web(authorization, session)
        row = self._read(authorization, bundle_ref)
        if row['state'] != 'awaiting_confirmation':
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_NOT_PENDING')
        fences=self._current_basis(authorization, row)
        impact_fences=self._impact_fences(authorization,row,impact_ref)
        if row['preview']['impact']['head_conflicts']:
            raise ValueError('LOCAL_BUNDLE_HEAD_CONFLICT_REQUIRES_NEW_PREVIEW')
        self._require_possible_capacity(row)
        nonce = secrets.token_urlsafe(32)
        key = self._challenge_key(bundle_ref, session)
        old = self.store.get(CHALLENGES, key)
        value = {'employee_id':authorization.principal, 'bundle_ref':bundle_ref,
            'session_digest':session.session_digest, 'nonce_digest':semantic_digest(nonce),
            'preview_digest':row['preview_digest'], 'expires_at':self.clock() + 900}
        if impact_ref is not None:
            value['impact_ref']=impact_ref
        from .domain_asset_staging import merge_writes
        if not self.store.atomic_compare_and_write(merge_writes((AtomicWrite(CHALLENGES,key,old,value),
                AtomicWrite(BUNDLES,bundle_ref,row,row)),(*fences,*impact_fences))):
            raise ValueError('LOCAL_BUNDLE_CHALLENGE_CONFLICT')
        self._impact_fences(authorization,row,impact_ref)
        return {'nonce':nonce, 'expires_at':value['expires_at'], 'preview_digest':row['preview_digest'],
                'manifest_digest':row['manifest_digest'],**({'impact_ref':impact_ref} if impact_ref is not None else {})}

    def comparison_baseline(self, *, authorization, bundle_ref, object_id, preview_digest):
        """Read one authorized current body, bound to the immutable preview.

        Local proposed bytes never enter this read. This is not an influence
        analysis, source read grant, or semantic acceptance of either version.
        Re-read authority and heads after object I/O, including for absent heads.
        """
        row = self._read(authorization, bundle_ref)
        if _DIGEST_ADAPTER.validate_python(preview_digest) != row['preview_digest']:
            raise ValueError('LOCAL_BUNDLE_COMPARISON_BINDING_MISMATCH')
        self._current_basis(authorization, row)
        change = next((c for c in row['preview']['changes'] if c['object_id'] == object_id), None)
        if change is None:
            raise ValueError('LOCAL_BUNDLE_OBJECT_NOT_AUTHORIZED')
        current = change['current_revision']
        head_key = 'domain-asset-head:' + semantic_digest([
            authorization.principal, change['namespace'], change['logical_id']])
        def exact_head():
            head = self.store.get('domain_asset_heads', head_key)
            if (head or {}).get('revision') != current:
                raise ValueError('LOCAL_BUNDLE_PREVIEW_BASIS_CHANGED')
        exact_head()
        result = {'contract_version':'boi/local-bundle-comparison@1',
            'bundle_ref':bundle_ref, 'manifest_digest':row['manifest_digest'],
            'preview_digest':row['preview_digest'], 'object_id':object_id,
            'current_revision':current, 'current':None,
            'local_bytes_received':False, 'source_access_granted':False,
            'semantic_conflicts':'not_evaluated', 'dependent_knowledge':'not_evaluated'}
        if current:
            revision = RevisionRef.model_validate(current)
            record = self.assets._record_metadata(authorization, revision, model_input=False, metadata_only=True)
            raw = self.intake.objects.get(record.payload['content_object_ref'])
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError('LOCAL_BUNDLE_COMPARISON_BYTE_LIMIT')
            asset = self.assets._asset(record, revision, raw)
            # Content permission permits the document's declared references;
            # it does not fetch sources or linked bodies on the actor's behalf.
            result['current'] = {'title':record.payload['title'],
                'description':record.payload['description'], 'kind':record.payload['kind'],
                'content_json':asset.content_json,
                'content_byte_digest':record.payload['content_object_ref']}
            self.assets._record_metadata(authorization, revision, model_input=False, metadata_only=True)
        fresh = self._read(authorization, bundle_ref)
        self._current_basis(authorization, fresh)
        exact_head()
        if fresh['preview_digest'] != row['preview_digest']:
            raise ValueError('LOCAL_BUNDLE_COMPARISON_BINDING_MISMATCH')
        return result

    @staticmethod
    def confirmation_context(row):
        proof = row.get('confirmation') or {}
        return {key:proof[key] for key in ('mechanism', 'auth_source', 'actor', 'delegation_ref', 'participation',
            'human_confirmation_observed') if key in proof}

    @staticmethod
    def _web(auth, session):
        if (not isinstance(session, VerifiedWebSession) or session.principal_id != auth.principal
                or len(session.session_digest) != 71 or not session.session_digest.startswith('sha256:')):
            raise ValueError('LOCAL_BUNDLE_WEB_SESSION_NOT_AUTHORIZED')

    @staticmethod
    def _challenge_key(bundle_ref, session):
        return 'bundle-challenge:' + semantic_digest([bundle_ref, session.session_digest])

    @staticmethod
    def _require_possible_capacity(row):
        from .publication_capacity import initial_publication_capacity
        manifest=LocalBundleManifest.model_validate(row['manifest'])
        if manifest.publication_layout is not None:
            from .local_publication_plan import plan_publication_units
            plan=plan_publication_units(manifest)
            if plan!=row['preview'].get('publication_plan'):
                raise ValueError('LOCAL_BUNDLE_PUBLICATION_PLAN_CHANGED')
            if plan['blocked']:
                raise ValueError('LOCAL_BUNDLE_ATOMIC_UNIT_PLAN_REQUIRED')
            return
        capacity = initial_publication_capacity(manifest.changes)
        if capacity['status'] == 'atomic_unit_plan_required':
            raise ValueError('LOCAL_BUNDLE_ATOMIC_UNIT_PLAN_REQUIRED')

    def confirm(self, *, authorization, request, session):
        self._web(authorization, session)
        req = LocalBundleConfirmRequest.model_validate(request)
        row = self._read(authorization, req.bundle_ref)
        if req.manifest_digest != row['manifest_digest'] or req.preview_digest != row['preview_digest']:
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_BINDING_MISMATCH')
        key = self._challenge_key(req.bundle_ref, session)
        challenge = self.store.get(CHALLENGES, key)
        if (not challenge or challenge['session_digest'] != session.session_digest
                or challenge['preview_digest'] != req.preview_digest
                or challenge.get('impact_ref') != req.impact_ref
                or not hmac.compare_digest(challenge['nonce_digest'], semantic_digest(req.nonce))):
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_NONCE_DENIED')
        proof = {'mechanism':'signed_web_session_explicit_confirmation',
            'principal_id':authorization.principal, 'session_digest':session.session_digest,
            'nonce_digest':challenge['nonce_digest'], 'manifest_digest':req.manifest_digest,
            'preview_digest':req.preview_digest, 'policy_digest':authorization.policy_digest}
        if session.auth_source == 'dev_session':
            if row['manifest']['target_space']['visibility'] != 'private':
                raise ValueError('LOCAL_BUNDLE_DEV_PRIVATE_ONLY')
            proof.update(auth_source=session.auth_source, actor=session.actor or authorization.principal,
                delegation_ref=session.delegation_ref,
                participation='delegated_development' if session.delegation_ref else 'development_session')
        if req.impact_ref is not None:
            proof['impact_ref']=req.impact_ref
        if row['state'] == 'receiving' and row['confirmation'] == proof:
            return self.view(authorization=authorization, bundle_ref=req.bundle_ref)
        if row['state'] != 'awaiting_confirmation' or challenge['expires_at'] < self.clock():
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_EXPIRED_OR_CLOSED')
        if row['preview']['impact']['head_conflicts']:
            raise ValueError('LOCAL_BUNDLE_HEAD_CONFLICT_REQUIRES_NEW_PREVIEW')
        self._require_possible_capacity(row)
        fences = self._current_basis(authorization, row)
        impact_fences=self._impact_fences(authorization,row,req.impact_ref)
        value = {**row, 'state':'receiving', 'confirmation':proof, 'confirmed_at':self.clock()}
        from .domain_asset_staging import merge_writes
        if not self.store.atomic_compare_and_write(merge_writes((
                AtomicWrite(CHALLENGES, key, challenge, challenge),
                AtomicWrite(BUNDLES, req.bundle_ref, row, value)),(*fences,*impact_fences))):
            raise ValueError('LOCAL_BUNDLE_CONFIRMATION_STATE_CHANGED')
        return self.view(authorization=authorization, bundle_ref=req.bundle_ref)

    def upload_context(self, *, authorization, bundle_ref, object_id):
        row = self._read(authorization, bundle_ref)
        if row['state'] != 'receiving' or row['confirmation'] is None:
            raise ValueError('LOCAL_BUNDLE_UPLOAD_NOT_AUTHORIZED')
        fences = self._current_basis(authorization, row)
        obj = next((x for x in row['manifest']['objects'] if x['object_id'] == object_id), None)
        if obj is None:
            raise ValueError('LOCAL_BUNDLE_UPLOAD_OBJECT_NOT_AUTHORIZED')
        return row, obj, fences

    @staticmethod
    def upload_key(bundle_ref, object_id):
        return 'bundle-upload:' + semantic_digest([bundle_ref, object_id])

    def upload_record(self, row, obj):
        item = self.store.get(UPLOADS, self.upload_key(row['bundle_ref'], obj['object_id']))
        return self._upload_record(row, obj, item)

    def upload_records(self, row):
        objects = row['manifest']['objects']
        rows = read_bundle_index(self.store, UPLOADS,
            (self.upload_key(row['bundle_ref'], obj['object_id']) for obj in objects))
        return {obj['object_id']:self._upload_record(row, obj,
            rows.get(self.upload_key(row['bundle_ref'], obj['object_id']))) for obj in objects}

    @staticmethod
    def _upload_record(row, obj, item):
        if item is None:
            return None
        expected = {'employee_id':row['employee_id'], 'bundle_ref':row['bundle_ref'],
            'manifest_digest':row['manifest_digest'], 'object_id':obj['object_id'],
            'byte_digest':obj['byte_digest'], 'byte_length':obj['byte_length']}
        if any(item.get(key) != value for key, value in expected.items()):
            raise ValueError('LOCAL_BUNDLE_UPLOAD_RECEIPT_BINDING_MISMATCH')
        try:
            parts = item['parts']
            if not isinstance(parts, dict) or type(item['complete']) is not bool:
                raise ValueError()
            for key, value in parts.items():
                offset = int(key)
                if (str(offset) != key or offset < 0 or offset >= obj['byte_length'] or offset % CHUNK_BYTES
                        or type(value['byte_length']) is not int
                        or value['byte_length'] != min(CHUNK_BYTES, obj['byte_length']-offset)):
                    raise ValueError()
                _DIGEST_ADAPTER.validate_python(value['byte_digest'])
            if item['complete'] and set(parts) != {str(x) for x in range(0,obj['byte_length'],CHUNK_BYTES)}:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError('LOCAL_BUNDLE_UPLOAD_RECEIPT_INVALID') from None
        return item

    def stop(self, *, authorization, bundle_ref):
        row = self._read(authorization, bundle_ref)
        if row['state'] == 'stopped':
            return self.view(authorization=authorization, bundle_ref=bundle_ref)
        value = {**row, 'state':'stopped', 'stopped_at':self.clock()}
        if not self.store.atomic_compare_and_write((AtomicWrite(BUNDLES, bundle_ref, row, value),)):
            raise ValueError('LOCAL_BUNDLE_STOP_STATE_CHANGED')
        return self.view(authorization=authorization, bundle_ref=bundle_ref)

    def list_bundles(self, *, authorization, request):
        from .local_publication_state import unit_progress,publication_status
        req = LocalBundleListRequest.model_validate(request)
        self._policy(authorization)
        page = self.store.list_key_page(BUNDLES, employee_id=authorization.principal,
            after_key=req.after_key, limit=req.limit + 1)
        items = []
        for entry in page[:req.limit]:
            try:
                row = self._read(authorization, entry['key'])
            except ValueError as exc:
                if str(exc) in ('LOCAL_BUNDLE_POLICY_CHANGED', 'LOCAL_BUNDLE_SPACE_POLICY_CHANGED',
                        'KNOWLEDGE_SPACE_WRITE_NOT_AUTHORIZED', 'KNOWLEDGE_SPACE_SHARING_NOT_AUTHORIZED',
                        'KNOWLEDGE_SPACE_TEAM_NOT_AUTHORIZED'):
                    continue
                raise
            progress=unit_progress(self.store,row)
            status=publication_status(row['state'],progress)
            next_action={'published':'게시된 지식과 사용할 수 있는 범위를 확인합니다.',
                'publication_partial':'게시된 지식과 남은 단위를 확인합니다.',
                'publication_in_progress':'같은 게시 작업의 진행 상태를 확인합니다.',
                'publication_needs_attention':'중단된 단위와 이미 게시된 지식을 확인합니다.'}.get(
                    status,'변경 비교와 파일 전송 상태를 확인합니다.')
            items.append({'contract_version':row['contract_version'], 'bundle_ref':row['bundle_ref'],
                'title':row['manifest']['title'], 'description':row['manifest']['description'],
                'status':status, 'kind':'로컬에서 준비한 자료',
                'url':'/knowledge/local-bundles/' + row['bundle_ref'].split(':')[-1],
                'next_action':next_action,
                'target_space':row['manifest']['target_space'],
                'publication_committed':bool(progress and progress['publication_committed'])})
        return {'items':items, 'next_cursor':page[req.limit-1]['key'] if len(page)>req.limit else None,
                'total_count':None, 'scope':'current_actor_authorized_upload_intents'}

    def dispatch(self, *, authorization, request):
        from .local_bundle_contract import (LocalBundlePrepareRequest, LocalBundleValidateRequest, LocalBundleQualifyRequest,
            LocalBundleUnitRequest, LocalBundlePublishRequest)
        req = LocalPublicationRequest.model_validate(request)
        if req.phase == 'schema':
            from .knowledge_use_contract import LocalKnowledgeAssessment
            from .local_bundle_contract import LocalBundleAssessmentReadRequest
            from .local_bundle_contract import LocalBundleHotlImpactRequest, LocalBundleHotlAdmitRequest
            self._policy(authorization)
            if req.payload:
                raise ValueError('LOCAL_BUNDLE_SCHEMA_PAYLOAD_UNEXPECTED')
            return {'contract_version':req.contract_version, 'schemas':{
                'preview':LocalBundlePreviewRequest.model_json_schema(),
                'impact':LocalBundleHotlImpactRequest.model_json_schema(),
                'admit':LocalBundleHotlAdmitRequest.model_json_schema(),
                'list':LocalBundleListRequest.model_json_schema(),
                'prepare':LocalBundlePrepareRequest.model_json_schema(),
                'validate':LocalBundleValidateRequest.model_json_schema(),
                'qualify':LocalBundleQualifyRequest.model_json_schema(),
                'qualification_status':LocalBundleAssessmentReadRequest.model_json_schema(),
                'preflight':LocalBundleUnitRequest.model_json_schema(),
                'publish':LocalBundlePublishRequest.model_json_schema(),
                'publication_resume':LocalBundlePublishRequest.model_json_schema(),
                'local_assessment':LocalKnowledgeAssessment.model_json_schema(),
                'status':LocalBundleReadRequest.model_json_schema(), 'stop':LocalBundleReadRequest.model_json_schema()},
                'native_proposal':{'contract_version':'boi/local-native-draft@1',
                    'draft':'DomainAssetDraft metadata excluding content_json',
                    'content':'boi/knowledge-content@1 for definition, boi/knowledge-profile@1 for profile, or boi/native-agent-observation@1 for explicitly declared nonexecutable native-definition-review pack',
                    'references':'Only exact manifest-declared JSON pointers are rewritten',
                    'completion':'Native preparation does not grant publication or use qualification'},
                'confirmation':'signed_wiki_browser_session', 'publication':'requires_server_validation',
                'hotl_admission':'current_authenticated_pat_write_rights_and_model_input_impact',
                'source_bytes_before_admission':False, 'source_bytes_before_confirmation':False}
        if req.phase == 'impact':
            return self.hotl_impact(authorization=authorization, request=req.payload)
        if req.phase == 'admit':
            return self.admit(authorization=authorization, request=req.payload)
        if req.phase == 'preview':
            return self.preview(authorization=authorization, request=req.payload)
        if req.phase == 'list':
            return self.list_bundles(authorization=authorization, request=req.payload)
        if req.phase in ('preflight','publish','publication_resume'):
            if not callable(self.publication_factory):
                raise ValueError('LOCAL_PUBLICATION_SERVER_ADAPTER_UNAVAILABLE')
            cls = LocalBundleUnitRequest if req.phase == 'preflight' else LocalBundlePublishRequest
            request = cls.model_validate(req.payload)
            from .local_bundle_import import LocalBundleImport
            from .local_bundle_upload import LocalBundleUpload
            importer = LocalBundleImport(LocalBundleUpload(self, self.intake.objects.root.parent / 'local-bundle-uploads'),
                validate_reading=self.validate_reading, shared_reading_binding=self.shared_reading_binding)
            bridge = self.publication_factory(importer)
            method = bridge.resume if req.phase == 'publication_resume' else getattr(bridge,req.phase)
            return method(authorization=authorization,**request.model_dump())
        if req.phase in ('prepare','validate','qualify','qualification_status'):
            from .local_bundle_contract import LocalBundleAssessmentReadRequest
            from .local_bundle_import import LocalBundleImport
            from .local_bundle_upload import LocalBundleUpload
            cls = {'prepare':LocalBundlePrepareRequest,'validate':LocalBundleValidateRequest,
                'qualify':LocalBundleQualifyRequest,'qualification_status':LocalBundleAssessmentReadRequest}[req.phase]
            request = cls.model_validate(req.payload)
            upload = LocalBundleUpload(self, self.intake.objects.root.parent / 'local-bundle-uploads')
            importer = LocalBundleImport(upload, validate_reading=self.validate_reading,
                shared_reading_binding=self.shared_reading_binding)
            if req.phase == 'qualification_status':
                from .local_knowledge_qualification import LocalKnowledgeQualification
                return LocalKnowledgeQualification(importer,prepare_queries=False).current(authorization=authorization,
                    bundle_ref=request.bundle_ref,assessment_object_id=request.assessment_object_id)
            if req.phase == 'qualify':
                from .local_knowledge_qualification import LocalKnowledgeQualification
                return LocalKnowledgeQualification(importer).qualify(authorization=authorization,
                    bundle_ref=request.bundle_ref,assessment_object_id=request.assessment_object_id,
                    supersedes=request.supersedes)
            if req.phase == 'validate':
                from .local_bundle_checks import LocalBundleChecks
                return LocalBundleChecks(importer).validate(authorization=authorization,
                    bundle_ref=request.bundle_ref, limit=request.limit, object_id=request.object_id)
            return importer.prepare(authorization=authorization,
                bundle_ref=request.bundle_ref, limit=request.limit)
        read = LocalBundleReadRequest.model_validate(req.payload)
        return getattr(self, 'view' if req.phase == 'status' else 'stop')(
            authorization=authorization, bundle_ref=read.bundle_ref)
