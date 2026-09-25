"""Indexed space policies over native content, committed with publication.

Policy records/membership indexes own no document bytes. Reading a shared
document never impersonates its author or grants its underlying source/results.
Use qualification is a separate requirement, including for Private knowledge.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from copy import deepcopy
import json
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from ..access_policy import knowledge_access_policy
from ..v2.atomic_store_contract import AtomicWrite
from .domain_asset_store import DomainAssetStore
from .ledger import RecordKind, record_digest
from .local_bundle_import import LocalBundleImport
from .local_bundle_contract import LocalBundleManifest, LocalKnowledgeCorrection
from .knowledge_projection_contract import ProjectionPublication
from .knowledge_space_contract import NativeKnowledgeIdentity, KnowledgeSpaceTarget, admit_space_intent
from .semantic_binding_contract import Digest, FrozenContract, RevisionRef, semantic_digest

HEADS = 'knowledge_space_heads'
ENTRIES = 'knowledge_space_entries'
EPOCHS = 'knowledge_space_epochs'


class KnowledgeSpacePolicy(FrozenContract):
    contract_version: Literal['boi/knowledge-space-policy@1'] = 'boi/knowledge-space-policy@1'
    identity: NativeKnowledgeIdentity
    content_revision: RevisionRef
    visible_history: tuple[RevisionRef, ...] = Field(default=(), max_length=256)
    targets: tuple[KnowledgeSpaceTarget, ...] = Field(min_length=1, max_length=32)
    classification: Literal['internal', 'confidential', 'restricted']
    allowed_content_uses: tuple[Literal['read','model_input','cite','export'], ...] = Field(min_length=1,max_length=4)
    source_closure_digest: Digest
    source_policy_digest: Digest
    changed_by: str = Field(min_length=1)
    confirmation_ref: str = Field(min_length=1)
    publication_manifest_digest: Digest
    previous_policy: RevisionRef | None = None
    state: Literal['active', 'revoked'] = 'active'
    content_correction: LocalKnowledgeCorrection | None = None

    @model_serializer(mode='wrap')
    def preserve_existing_wire(self, handler):
        value = handler(self)
        if self.content_correction is None:
            value.pop('content_correction', None)
        return value

    @model_validator(mode='after')
    def unique_scopes(self):
        if len(set(self.targets)) != len(self.targets) or len(set(self.visible_history)) != len(self.visible_history):
            raise ValueError('KNOWLEDGE_SPACE_DUPLICATE_SCOPE_OR_HISTORY')
        if self.content_revision in self.visible_history:
            raise ValueError('KNOWLEDGE_SPACE_CURRENT_REVISION_IN_HISTORY')
        if len(set(self.allowed_content_uses)) != len(self.allowed_content_uses):
            raise ValueError('KNOWLEDGE_SPACE_DUPLICATE_USE')
        return self


@dataclass(frozen=True)
class KnowledgeSpaceAccess:
    actor_id: str
    identity: NativeKnowledgeIdentity
    content_revision: RevisionRef
    policy_revision: RevisionRef
    authority_digest: str
    purpose: str
    source_access_granted: bool = False
    use_qualification_granted: bool = False


class KnowledgeSpaceStore:
    def __init__(self, intake, *, current_principal, current_source_policy):
        if not callable(current_principal) or not callable(current_source_policy):
            raise ValueError('KNOWLEDGE_SPACE_CURRENT_AUTHORITY_REQUIRED')
        self.intake, self.store = intake, intake.store
        self.current_principal, self.current_source_policy = current_principal, current_source_policy

    @staticmethod
    def partition(target, owner):
        target = KnowledgeSpaceTarget.model_validate(target)
        return 'knowledge-space:' + semantic_digest([target.visibility,
            owner if target.visibility == 'private' else target.team_id])

    @staticmethod
    def entry_key(partition, stable_id):
        return 'knowledge-space-entry:' + semantic_digest([partition, stable_id])

    @staticmethod
    def _metadata(policy, target):
        return {'visibility':target.visibility, 'owner':policy.identity.identity_creator,
            'team_id':target.team_id, 'classification':policy.classification,
            'acl_policy':{'private':'acl:private:'+policy.identity.identity_creator,
                'team':'acl:team:'+str(target.team_id), 'public':'acl:public'}[target.visibility]}

    def _actor(self, expected_id):
        actor = self.current_principal()
        if not actor or not actor.employee_id or actor.employee_id != expected_id:
            raise ValueError('KNOWLEDGE_SPACE_PRINCIPAL_MISMATCH')
        return deepcopy(actor)

    def _policy(self, stable_id):
        head = self.store.get(HEADS, stable_id)
        if not head:
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        revision = RevisionRef.model_validate(head['policy_revision'])
        record = self.intake.ledger.read(revision.ref)
        if (record.kind != RecordKind.KNOWLEDGE_SPACE_POLICY or record_digest(record.record_id) != revision.revision_digest
                or semantic_digest(record.payload) != head.get('policy_payload_digest')):
            raise ValueError('KNOWLEDGE_SPACE_POLICY_BINDING_MISMATCH')
        policy = KnowledgeSpacePolicy.model_validate(record.payload)
        if 'query_policy_wire' in head and head['query_policy_wire'] != json.dumps(
                record.payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False):
            raise ValueError('KNOWLEDGE_SPACE_QUERY_POLICY_BINDING_MISMATCH')
        if (policy.identity.stable_id != stable_id or head.get('content_revision') != policy.content_revision.model_dump(mode='json')
                or head.get('state') != policy.state):
            raise ValueError('KNOWLEDGE_SPACE_POLICY_BINDING_MISMATCH')
        return head, revision, policy

    def _native(self, policy, revision):
        # This uses published index integrity, not author authorization disguised
        # as the caller. Space policy supplies content audience, separately.
        record = self.intake.ledger.read(revision.ref)
        value = record.payload
        index = self.store.get('domain_knowledge_assets', revision.ref)
        native_head = self.store.get('domain_asset_heads',policy.identity.stable_id)
        if (record.kind != RecordKind.KNOWLEDGE_REVISION or value.get('contract_version') != DomainAssetStore.CONTRACT
                or value.get('status') != 'candidate'
                or record_digest(record.record_id) != revision.revision_digest or not index
                or not native_head or native_head.get('revision') != policy.content_revision.model_dump(mode='json')
                or index.get('record_payload_digest') != semantic_digest(value)
                or value.get('policy_digest') != policy.source_policy_digest
                or (value.get('employee_id'),value.get('namespace'),value.get('logical_id')) != (
                    policy.identity.identity_creator,policy.identity.namespace,policy.identity.logical_id)):
            raise ValueError('KNOWLEDGE_SPACE_NATIVE_REVISION_BINDING_MISMATCH')
        if revision == policy.content_revision and value.get('source_manifest_digest') != policy.source_closure_digest:
            raise ValueError('KNOWLEDGE_SPACE_SOURCE_CLOSURE_MISMATCH')
        receipt = self.store.get('knowledge_publication_receipts', policy.publication_manifest_digest)
        if not receipt or receipt.get('manifest_digest') != policy.publication_manifest_digest:
            raise ValueError('KNOWLEDGE_SPACE_PUBLICATION_INCOMPLETE')
        return record

    def authorize(self, *, actor_id, stable_id, revision=None, purpose='read', target=None):
        capabilities = {'metadata':'can_read', 'read':'can_read', 'model_input':'can_use_in_agent_context',
            'cite':'can_cite', 'export':'can_export', 'edit':'can_edit', 'share':'can_promote'}
        if purpose not in capabilities:
            raise ValueError('KNOWLEDGE_SPACE_PURPOSE_UNSUPPORTED')
        actor = self._actor(actor_id)
        head, policy_ref, policy = self._policy(stable_id)
        if policy.state != 'active':
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        if purpose in ('read','model_input','cite','export') and purpose not in policy.allowed_content_uses:
            raise ValueError('KNOWLEDGE_SPACE_CONTENT_USE_NOT_AUTHORIZED')
        requested = RevisionRef.model_validate(revision) if revision is not None else policy.content_revision
        if requested not in (policy.content_revision, *policy.visible_history):
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        if self.current_source_policy() != policy.source_policy_digest:
            raise ValueError('KNOWLEDGE_SPACE_SOURCE_POLICY_CHANGED')
        selected = KnowledgeSpaceTarget.model_validate(target) if target is not None else None
        decisions = [knowledge_access_policy(self._metadata(policy, scope), identity_owner=policy.identity.identity_creator,
            employee_id=actor.employee_id, teams=actor.teams, roles=actor.roles)
            for scope in policy.targets if selected is None or scope == selected]
        allowed = [d for d in decisions if getattr(d, capabilities[purpose]) and (
            purpose == 'metadata' or 'body' not in d.redactions)]
        if not allowed:
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        record = self._native(policy, requested)
        # Permission changes while reading are observable without re-indexing.
        fresh = self._actor(actor_id)
        if (self.store.get(HEADS, stable_id) != head or sorted(fresh.roles) != sorted(actor.roles)
                or sorted(fresh.teams) != sorted(actor.teams) or self.current_source_policy() != policy.source_policy_digest):
            raise ValueError('KNOWLEDGE_SPACE_AUTHORITY_CHANGED')
        access = KnowledgeSpaceAccess(actor_id, policy.identity, requested, policy_ref,
            semantic_digest({'actor':actor_id,'teams':sorted(actor.teams),'roles':sorted(actor.roles),
                'policy':policy_ref.model_dump(mode='json'),'source_policy':policy.source_policy_digest,
                'revision':requested.model_dump(mode='json'),'purpose':purpose,
                'target':selected.model_dump(mode='json') if selected is not None else None}), purpose)
        return access, record

    def read(self, *, actor_id, stable_id, revision=None, purpose='read', target=None):
        if purpose == 'metadata':
            raise ValueError('KNOWLEDGE_SPACE_BODY_PURPOSE_REQUIRED')
        access, record = self.authorize(actor_id=actor_id, stable_id=stable_id, revision=revision, purpose=purpose, target=target)
        asset = DomainAssetStore._asset(record, access.content_revision,
            self.intake.objects.get(record.payload['content_object_ref']))
        after, _ = self.authorize(actor_id=actor_id, stable_id=stable_id, revision=access.content_revision, purpose=purpose, target=target)
        if after != access:
            raise ValueError('KNOWLEDGE_SPACE_AUTHORITY_CHANGED')
        return access, record, asset

    def list(self, *, actor_id, target, after_key='', expected_epoch=None, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100 or not isinstance(after_key,str) or len(after_key)>2048:
            raise ValueError('KNOWLEDGE_SPACE_PAGE_INVALID')
        actor = self._actor(actor_id)
        target = KnowledgeSpaceTarget.model_validate(target)
        if target.visibility == 'team' and target.team_id not in actor.teams:
            raise ValueError('KNOWLEDGE_SPACE_ACCESS_DENIED')
        partition = self.partition(target, actor_id)
        source_policy = self.current_source_policy()
        epoch = self.store.get(EPOCHS, partition)
        if after_key and (type(expected_epoch) is not int or expected_epoch != (epoch or {}).get('epoch',0)):
            raise ValueError('KNOWLEDGE_SPACE_CURSOR_STALE')
        page = self.store.list_key_page(ENTRIES, employee_id=partition, after_key=after_key, limit=limit+1)
        items = []
        for entry in page[:limit]:
            value = entry['value']
            if value.get('state') != 'active':
                continue
            try:
                access, record = self.authorize(actor_id=actor_id, stable_id=value['stable_id'], target=target, purpose='metadata')
            except ValueError as error:
                if str(error) == 'KNOWLEDGE_SPACE_ACCESS_DENIED':
                    continue
                raise
            if (access.policy_revision.model_dump(mode='json') != value.get('policy_revision')
                    or access.content_revision.model_dump(mode='json') != value.get('content_revision')):
                raise ValueError('KNOWLEDGE_SPACE_INDEX_STALE')
            items.append({'stable_id':access.identity.stable_id, 'revision':access.content_revision.model_dump(mode='json'),
                'policy_revision':access.policy_revision.model_dump(mode='json'),
                'title':record.payload['title'], 'namespace':record.payload['namespace'],
                'kind':record.payload['kind'], 'target':target.model_dump(mode='json')})
        fresh = self._actor(actor_id)
        if (epoch != self.store.get(EPOCHS, partition) or sorted(fresh.roles) != sorted(actor.roles)
                or sorted(fresh.teams) != sorted(actor.teams) or self.current_source_policy() != source_policy):
            raise ValueError('KNOWLEDGE_SPACE_AUTHORITY_CHANGED')
        return {'items':items, 'next_after_key':page[limit-1]['key'] if len(page)>limit else None,
            'policy_epoch':(epoch or {}).get('epoch',0), 'total_count':None,
            'source_access_granted':False, 'use_qualification_granted':False}

    def initial_publication_writes(self, *, importer, authorization, bundle_ref, manifest, classification='internal',unit_id=None):
        """Native publication callback only; no endpoint commits these writes alone.

        Actual confirmed-upload/import closure is checked here. The coordinator's
        enclosing admission must additionally require registered use checks and
        semantic/dependency impact. This method never manufactures those results.
        """
        if not isinstance(importer, LocalBundleImport) or importer.intake is not self.intake:
            raise ValueError('KNOWLEDGE_SPACE_NATIVE_IMPORT_REQUIRED')
        manifest = ProjectionPublication.model_validate(manifest.model_dump(mode='json'))
        actor = self._actor(authorization.principal)
        row, fences = importer._context(authorization, bundle_ref)
        # Reject the combined native + space lower bound before appending N
        # private policies. Exact final admission must still count every fence.
        importer.service._require_possible_capacity(row)
        if (manifest.confirmation_ref != importer.scope(row) or manifest.principal_id != actor.employee_id
                or manifest.policy_digest != authorization.policy_digest or self.current_source_policy() != authorization.policy_digest):
            raise ValueError('KNOWLEDGE_SPACE_PUBLICATION_BINDING_MISMATCH')
        target = KnowledgeSpaceTarget.model_validate(row['manifest']['target_space'])
        admit_space_intent(actor, target)
        if target.visibility != 'private' and 'org_share' not in authorization.allowed_uses:
            raise ValueError('KNOWLEDGE_SPACE_DERIVED_SHARING_NOT_AUTHORIZED')
        status = importer.status(authorization=authorization, bundle_ref=bundle_ref)
        if status['state'] != 'native_prepared_requires_qualification':
            raise ValueError('KNOWLEDGE_SPACE_NATIVE_PREPARATION_REQUIRED')
        changes = {c.object_id:c for c in LocalBundleManifest.model_validate(row['manifest']).changes}
        if unit_id is not None:
            plan=row['preview'].get('publication_plan')
            unit=next((u for u in (plan or {}).get('units',[]) if u['unit_id']==unit_id),None)
            if unit is None:
                raise ValueError('KNOWLEDGE_SPACE_CONFIRMED_UNIT_REQUIRED')
            changes={key:changes[key] for key in unit['object_ids']}
        elif row['preview'].get('publication_plan'):
            raise ValueError('KNOWLEDGE_SPACE_CONFIRMED_UNIT_REQUIRED')
        handles = [importer._saved(row, key)['result']['staged'] for key in changes]
        handle_changes = {h['native_identity']: changes[key] for key, h in zip(changes, handles)}
        if (len(manifest.changes) != len(handles) or any(c.operation != 'upsert' for c in manifest.changes)
                or {c.stable_id:(c.revision.ref,c.revision.revision_digest) for c in manifest.changes} != {
                    h['native_identity']:(h['revision']['ref'],h['revision']['revision_digest']) for h in handles}):
            raise ValueError('KNOWLEDGE_SPACE_PUBLICATION_CLOSURE_MISMATCH')
        writes, partitions = [], set()
        occurred = datetime.fromtimestamp(row['confirmed_at'],timezone.utc).isoformat()
        for handle in handles:
            revision = RevisionRef.model_validate(handle['revision'])
            record, asset = importer.stage.read(authorization=authorization, scope_ref=manifest.confirmation_ref,
                revision=revision, model_input=False)
            identity = NativeKnowledgeIdentity(identity_creator=record.payload['employee_id'],
                namespace=record.payload['namespace'],logical_id=record.payload['logical_id'])
            old_head = self.store.get(HEADS, identity.stable_id)
            change = handle_changes[identity.stable_id]
            if change.operation == 'revise':
                from .knowledge_content_correction import correction_basis, correction_source_closure
                previous, previous_record, fence = correction_basis(importer.service.assets,
                    authorization, change, target)
                fences = (*fences, fence)
                from .knowledge_content import decode_knowledge_content
                content = decode_knowledge_content(json.loads(asset.content_json)) if asset.kind == 'definition' else None
                source_closure = correction_source_closure(previous, previous_record, record,
                    content=content, read_span=importer.intake.ledger.read)
                if revision == previous.content_revision:
                    raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_CONTENT_CHANGE_REQUIRED')
                if len(previous.visible_history) >= 256:
                    raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_HISTORY_CAPACITY')
                policy = KnowledgeSpacePolicy(**{**previous.model_dump(mode='json'),
                    'content_revision':revision, 'visible_history':(*previous.visible_history, previous.content_revision),
                    'source_closure_digest':source_closure,
                    'previous_policy':change.correction.expected_policy_revision,
                    'content_correction':change.correction, 'changed_by':actor.employee_id,
                    'confirmation_ref':manifest.confirmation_ref, 'publication_manifest_digest':manifest.digest})
            else:
                if old_head is not None:
                    raise ValueError('KNOWLEDGE_SPACE_EXISTING_POLICY_REQUIRES_CHANGE_INTENT')
                policy = KnowledgeSpacePolicy(identity=identity,content_revision=revision,targets=(target,),
                    classification=classification,source_closure_digest=record.payload['source_manifest_digest'],
                    allowed_content_uses=('read','export',*[use for use in ('model_input','cite') if use in authorization.allowed_uses]),
                    source_policy_digest=authorization.policy_digest,changed_by=actor.employee_id,
                    confirmation_ref=manifest.confirmation_ref,publication_manifest_digest=manifest.digest)
            policy_record = self.intake.ledger.append(RecordKind.KNOWLEDGE_SPACE_POLICY,policy.model_dump(mode='json'),
                authority='rights_service',occurred_at=occurred)
            policy_ref = RevisionRef(ref=policy_record.record_id,revision_digest=record_digest(policy_record.record_id))
            if change.operation == 'revise':
                from .knowledge_document_feedback import COLLECTION, correction_feedback_rows
                for feedback_ref, feedback in correction_feedback_rows(importer.service.assets, authorization, change, previous):
                    writes.append(AtomicWrite(COLLECTION, feedback_ref.ref, feedback, {**feedback,
                        'resolution':{'revision':revision.model_dump(mode='json'),
                            'policy_revision':policy_ref.model_dump(mode='json')}}))
            head = {'employee_id':identity.identity_creator,'policy_revision':policy_ref.model_dump(mode='json'),
                'policy_payload_digest':semantic_digest(policy_record.payload),'content_revision':revision.model_dump(mode='json'),
                'state':'active',
                # Prepared in the same native/policy/receipt transaction. SQL
                # readers bind this exact wire to the current policy digest.
                'query_policy_wire':json.dumps(policy_record.payload,ensure_ascii=False,sort_keys=True,
                                              separators=(',',':'),allow_nan=False),
                'query_native_payload_digest':semantic_digest(record.payload),
                'query_native_policy_digest':record.payload['policy_digest'],
                'query_source_manifest_digest':record.payload['source_manifest_digest']}
            writes.append(AtomicWrite(HEADS,identity.stable_id,old_head,head))
            partition = self.partition(target,identity.identity_creator)
            partitions.add(partition)
            key = self.entry_key(partition,identity.stable_id)
            old = self.store.get(ENTRIES,key)
            if old is not None and change.operation == 'create':
                raise ValueError('KNOWLEDGE_SPACE_ORPHAN_INDEX')
            if change.operation == 'revise' and (old is None
                    or old['policy_revision'] != change.correction.expected_policy_revision.model_dump(mode='json')
                    or old['content_revision'] != change.previous_revision.model_dump(mode='json')):
                raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_MEMBERSHIP_CHANGED')
            writes.append(AtomicWrite(ENTRIES,key,old,{'employee_id':partition,'stable_id':identity.stable_id,
                'policy_revision':policy_ref.model_dump(mode='json'),'content_revision':revision.model_dump(mode='json'),'state':'active'}))
        for partition in sorted(partitions):
            old = self.store.get(EPOCHS,partition)
            writes.append(AtomicWrite(EPOCHS,partition,old,{'employee_id':partition,'epoch':(old or {}).get('epoch',0)+1}))
        return tuple(fences), tuple(writes)
