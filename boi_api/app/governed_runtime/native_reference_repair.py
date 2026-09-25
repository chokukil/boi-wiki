"""Bounded reconstruction of declared references from the native ledger.

This repairs derived metadata only. Content, revision, audience and semantic/use
decisions remain unchanged. Every request has an immutable maintenance receipt;
the same request can be recovered after an uncertain transport outcome.
"""
from typing import Literal

from pydantic import Field

from ..v2.atomic_store_contract import AtomicWrite
from .knowledge_space_store import HEADS, ENTRIES, EPOCHS
from .native_reference_projection import reference_projection
from .semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest

REPAIRS = 'knowledge_reference_repairs'
VERSION = 'boi/native-reference-repair@1'


class NativeReferenceRepairRequest(FrozenContract):
    contract_version: Literal['boi/native-reference-repair-request@1'] = 'boi/native-reference-repair-request@1'
    targets: tuple[RevisionRef, ...] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=240)


class NativeReferenceRepair:
    request_model=NativeReferenceRepairRequest
    version=VERSION
    key_prefix='native-reference-repair:'
    marker='reference_repair_ref'
    digest_field='reference_projection_digest'
    coverage='declared_native_dependencies_conflicts_supersedes_only'

    def __init__(self, spaces, index):
        if spaces.store is not index.backend.authority_store:
            raise ValueError('KNOWLEDGE_REFERENCE_BACKEND_MISMATCH')
        self.spaces, self.index, self.store = spaces, index, spaces.store

    def _read(self, actor_id, revision):
        record = self.spaces.intake.ledger.read(revision.ref)
        identity = 'domain-asset-head:' + semantic_digest([record.payload.get('employee_id'),
            record.payload.get('namespace'), record.payload.get('logical_id')])
        access, record = self.spaces.authorize(actor_id=actor_id, stable_id=identity,
            revision=revision, purpose='edit')
        # A repair response consumed through MCP still obeys model-input rights.
        model_access, _ = self.spaces.authorize(actor_id=actor_id, stable_id=identity,
            revision=revision, purpose='model_input')
        policy_head, policy_ref, policy = self.spaces._policy(identity)
        if policy_ref != access.policy_revision or policy.content_revision != revision:
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_CURRENT_REVISION_REQUIRED')
        head = self.store.get('domain_asset_heads', identity)
        row = self.store.get('domain_knowledge_assets', revision.ref)
        payload_digest = semantic_digest(record.payload)
        if (not head or not row or head.get('revision') != revision.model_dump(mode='json')
                or row.get('revision') != head['revision']
                or any(v.get('record_payload_digest') != payload_digest for v in (head, row))):
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_NATIVE_BINDING_CHANGED')
        receipt = self.store.get('knowledge_publication_receipts', policy.publication_manifest_digest)
        if not receipt or receipt.get('manifest_digest') != policy.publication_manifest_digest:
            raise ValueError('KNOWLEDGE_SPACE_PUBLICATION_INCOMPLETE')
        entries = []
        for target in policy.targets:
            partition = self.spaces.partition(target, policy.identity.identity_creator)
            key = self.spaces.entry_key(partition, identity)
            entry = self.store.get(ENTRIES, key)
            if (not entry or entry.get('state') != 'active' or entry.get('employee_id') != partition
                    or entry.get('stable_id') != identity or entry.get('content_revision') != head['revision']
                    or entry.get('policy_revision') != policy_ref.model_dump(mode='json')):
                raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_MEMBERSHIP_CHANGED')
            entries.append((partition, key, entry))
        return {'identity': identity, 'revision': revision, 'authority': (access, model_access),
            'head': head, 'row': row, 'policy_head': policy_head, 'entries': entries,
            'receipt_key': policy.publication_manifest_digest, 'receipt': receipt,
            'projection': reference_projection(record)}

    def _fingerprints(self,targets):
        return self.index.fingerprints(targets)

    def _expected_fingerprint(self,state):
        return state['projection'][self.digest_field]

    def _result(self,receipt,replayed):
        return {'contract_version': self.version, 'repair_ref': receipt['repair_ref'],
            'replayed': replayed, 'state': 'completed',
            'items': [{k: item[k] for k in ('stable_id', 'revision', 'changed', 'projection_digest')}
                      for item in receipt['items']],
            'content_revised': False, 'sharing_changed': False, 'source_access_granted': False,
            'use_qualification_granted': False, 'publication_authorized': False,
            'coverage': self.coverage,
            'semantic_conflicts': 'not_evaluated', 'legacy_outside_spaces': 'not_evaluated'}

    def repair(self, *, actor_id, request):
        req = self.request_model.model_validate(request)
        targets = tuple(sorted(set(req.targets), key=lambda r: (r.ref, r.revision_digest)))
        material = {'contract_version': self.version, 'employee_id': actor_id,
            'targets': [r.model_dump(mode='json') for r in targets]}
        key = self.key_prefix + semantic_digest([actor_id, req.idempotency_key])
        old_receipt = self.store.get(REPAIRS, key)
        if old_receipt and old_receipt.get('request_digest') != semantic_digest(material):
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_REQUEST_CHANGED')
        states = [self._read(actor_id, r) for r in targets]
        fingerprints = self._fingerprints(targets)
        def ready(state):
            return (all(all(v.get(k) == expected for k, expected in state['projection'].items())
                        for v in (state['row'], state['head']))
                    and fingerprints.get(state['revision'].ref) == self._expected_fingerprint(state))
        if old_receipt:
            if not all(ready(state) for state in states):
                raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_RESULT_CHANGED')
            if ([self._read(actor_id, r) for r in targets] != states
                    or self._fingerprints(targets) != fingerprints):
                raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_AUTHORITY_CHANGED')
            return self._result(old_receipt, True)
        writes, partitions, items = {}, set(), []
        def add(collection, item_key, expected, value):
            write = AtomicWrite(collection, item_key, expected, value)
            previous = writes.get((collection, item_key))
            if previous is not None and previous != write:
                raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_BASIS_CHANGED')
            writes[collection, item_key] = write
        for state in states:
            changed = not ready(state)
            projection, identity, revision = state['projection'], state['identity'], state['revision']
            for collection, item_key, field in (('domain_asset_heads', identity, 'head'),
                    ('domain_knowledge_assets', revision.ref, 'row')):
                before = state[field]
                # The marker forces an actual index UPDATE when the projection
                # wire already matches but the database fingerprint is missing.
                after = {**before, **projection, self.marker: key} if changed else before
                add(collection, item_key, before, after)
            add(HEADS, identity, state['policy_head'], state['policy_head'])
            add('knowledge_publication_receipts', state['receipt_key'], state['receipt'], state['receipt'])
            for partition, entry_key, entry in state['entries']:
                add(ENTRIES, entry_key, entry, entry)
                if changed:
                    partitions.add(partition)
            items.append({'stable_id': identity, 'revision': revision.model_dump(mode='json'),
                'changed': changed, 'projection_digest': projection[self.digest_field],
                # Preserve the pre-repair metadata, including corrupt/missing
                # bytes, without turning it into a content revision or response.
                'previous_head': state['head'], 'previous_index': state['row'],
                'previous_database_fingerprint': fingerprints.get(revision.ref)})
        for partition in sorted(partitions):
            epoch = self.store.get(EPOCHS, partition)
            if epoch is not None and (type(epoch.get('epoch')) is not int or epoch['epoch'] < 0):
                raise ValueError('KNOWLEDGE_SET_EPOCH_INVALID')
            add(EPOCHS, partition, epoch, {'employee_id': partition, 'epoch': (epoch or {}).get('epoch', 0) + 1})
        receipt = {**material, 'repair_ref': key, 'request_digest': semantic_digest(material), 'items': items}
        # Bound preservation work before any mutation. Refuse rather than lose
        # pre-repair evidence or emit a partial successful batch.
        from ..v2.atomic_store_contract import atomic_json_wire
        if len(atomic_json_wire(receipt).encode()) > 16 * 1024 * 1024:
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_RECEIPT_BYTE_LIMIT')
        add(REPAIRS, key, None, receipt)
        if ([self._read(actor_id, r) for r in targets] != states
                or self._fingerprints(targets) != fingerprints):
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_AUTHORITY_CHANGED')
        if not self.store.atomic_compare_and_write(tuple(writes.values())):
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_BASIS_CHANGED')
        # A failed readback leaves the durable receipt available for recovery;
        # do not erase it or report an unverified successful repair.
        after = [self._read(actor_id, r) for r in targets]
        fingerprints = self._fingerprints(targets)
        if any(a['authority'] != b['authority'] or not ready(a) for a, b in zip(after, states)):
            raise ValueError('KNOWLEDGE_REFERENCE_REPAIR_READBACK_CHANGED')
        return self._result(receipt, False)
