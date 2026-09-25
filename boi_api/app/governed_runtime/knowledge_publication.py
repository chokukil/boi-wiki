"""Internal cross-store publication coordinator; not a public admission endpoint.

Native staging/admission must supply current confirmation, qualification and ACL
fences and the exact native head writes. No default approval or materializer exists.
The CAS publication pointer is authoritative; a SQLite prepared row alone is not.
"""
from dataclasses import dataclass
import time
from typing import Callable

from boi_api.app.v2.atomic_store_contract import AtomicWrite, prepare_atomic_writes, is_atomic_read_fence
from .knowledge_projection_contract import ProjectionPublication
from .knowledge_projection_store import ProjectionSnapshot
from .semantic_binding_contract import semantic_digest


SCOPES = 'knowledge_publication_scopes'
MANIFESTS = 'knowledge_publication_manifests'
OUTBOX = 'knowledge_projection_outbox'
RECEIPTS = 'knowledge_publication_receipts'
OWN_COLLECTIONS = {SCOPES, MANIFESTS, OUTBOX, RECEIPTS}


def empty_publication_scope(scope_id):
    return {'scope_id': scope_id, 'last_generation': 0, 'fence': 0,
        'visible': {'generation': 0, 'manifest_digest': None}, 'active_operation': None}


@dataclass(frozen=True)
class PublicationHandle:
    scope_id: str
    operation_id: str
    writer_id: str
    token: int
    generation: int


@dataclass(frozen=True)
class PublicationAdmission:
    """Server-created current state fences and, at commit, native public writes."""
    fences: tuple[AtomicWrite, ...]
    public_writes: tuple[AtomicWrite, ...] = ()


class PublicationOutcomeUnknown(RuntimeError):
    """Reconcile this operation; do not submit a replacement publication."""


class KnowledgePublicationCoordinator:
    def __init__(self, store, projection, *, admission: Callable, materialize: Callable,
                 clock=time.time, lease_seconds=60, validate_writes=None):
        if not callable(admission) or not callable(materialize) or not 1 <= lease_seconds <= 3600:
            raise ValueError('PUBLICATION_SERVER_ADAPTER_REQUIRED')
        self.store, self.projection = store, projection
        self.admission, self.materialize = admission, materialize
        self.clock, self.lease_seconds = clock, lease_seconds
        if validate_writes is not None and not callable(validate_writes):
            raise ValueError('PUBLICATION_WRITE_BUDGET_ADAPTER_REQUIRED')
        self.validate_writes=validate_writes

    def _cas(self, writes, operation_id):
        prepared = prepare_atomic_writes(writes)
        if self.validate_writes is not None:
            self.validate_writes(prepared)
        try:
            success = self.store.atomic_compare_and_write(prepared)
        except Exception:
            # A network error after commit is indistinguishable from one before it.
            raise PublicationOutcomeUnknown('PUBLICATION_OUTCOME_UNKNOWN:' + operation_id) from None
        if not success:
            raise ValueError('PUBLICATION_STATE_CONFLICT')

    def _admit(self, manifest, phase):
        admitted = self.admission(manifest, phase)
        if not isinstance(admitted, PublicationAdmission) or not admitted.fences:
            raise ValueError('PUBLICATION_ADMISSION_FENCES_REQUIRED')
        if phase == 'reserve' and admitted.public_writes:
            raise ValueError('PUBLICATION_PREMATURE_PUBLIC_WRITES')
        if phase == 'commit' and not admitted.public_writes:
            raise ValueError('PUBLICATION_NATIVE_HEAD_WRITES_REQUIRED')
        if any(w.collection in OWN_COLLECTIONS for w in admitted.public_writes):
            raise ValueError('PUBLICATION_ADMISSION_COLLECTION_INVALID')
        if any(not is_atomic_read_fence(w) for w in admitted.fences):
            raise ValueError('PUBLICATION_ADMISSION_FENCE_INVALID')
        self._prior_proof_fences(manifest,admitted.fences)
        return admitted

    @staticmethod
    def _prior_proof_fences(manifest,fences):
        # An admission may lock a prior commit's evidence, but cannot write any
        # coordinator-owned record or lock the current operation as its proof.
        owned=[w for w in fences if w.collection in OWN_COLLECTIONS]
        if any(w.collection not in (MANIFESTS,RECEIPTS) or w.key==manifest.digest for w in owned):
            raise ValueError('PUBLICATION_ADMISSION_COLLECTION_INVALID')
        records={(w.collection,w.key):w.expected for w in owned}
        for key in {w.key for w in owned}:
            saved,receipt=records.get((MANIFESTS,key)),records.get((RECEIPTS,key))
            if not saved or not receipt:
                raise ValueError('PUBLICATION_PRIOR_COMMIT_PROOF_REQUIRED')
            prior=ProjectionPublication.model_validate(saved.get('manifest'))
            if (prior.digest!=key or prior.principal_id!=manifest.principal_id
                    or prior.policy_digest!=manifest.policy_digest
                    or prior.confirmation_ref!=manifest.confirmation_ref
                    or receipt.get('manifest_digest')!=key or receipt.get('operation_id')!=key
                    or receipt.get('scope_id')!=prior.scope_id
                    or type(receipt.get('generation')) is not int
                    or receipt['generation']<=prior.base_generation
                    or (prior.scope_id==manifest.scope_id and receipt['generation']>manifest.base_generation)):
                raise ValueError('PUBLICATION_PRIOR_COMMIT_PROOF_REQUIRED')

    def _state(self, scope):
        return self.store.get(SCOPES, scope)

    def _manifest(self, operation_id):
        record = self.store.get(MANIFESTS, operation_id)
        if record is None:
            raise ValueError('PUBLICATION_MANIFEST_UNAVAILABLE')
        manifest = ProjectionPublication.model_validate(record['manifest'])
        if manifest.digest != operation_id:
            raise ValueError('PUBLICATION_MANIFEST_BINDING_INVALID')
        return manifest

    def _owned(self, handle, *, phases):
        state = self._state(handle.scope_id)
        operation = self.store.get(OUTBOX, handle.operation_id)
        if (not state or not operation or state['active_operation'] != handle.operation_id
                or state['fence'] != handle.token or operation['token'] != handle.token
                or operation['writer_id'] != handle.writer_id or operation['scope_id'] != handle.scope_id
                or operation['generation'] != handle.generation):
            raise ValueError('PUBLICATION_STALE_WRITER')
        if operation['status'] not in phases:
            raise ValueError('PUBLICATION_PHASE_CONFLICT')
        if operation['lease_until'] <= self.clock():
            raise ValueError('PUBLICATION_LEASE_EXPIRED')
        return state, operation

    @staticmethod
    def _handle(operation):
        return PublicationHandle(operation['scope_id'], operation['operation_id'], operation['writer_id'],
                                 operation['token'], operation['generation'])

    def reserve(self, manifest, *, writer_id):
        manifest = ProjectionPublication.model_validate(manifest.model_dump(mode='json'))
        if not isinstance(writer_id, str) or not writer_id.strip():
            raise ValueError('PUBLICATION_WRITER_ID_REQUIRED')
        admitted = self._admit(manifest, 'reserve')
        operation_id = manifest.digest
        previous = self.store.get(OUTBOX, operation_id)
        if previous:
            if previous['writer_id'] != writer_id:
                raise ValueError('PUBLICATION_WRITER_BUSY')
            if previous['status'] in ('aborting', 'aborted'):
                raise ValueError('PUBLICATION_OPERATION_ABORTED')
            return self._handle(previous)
        state = self._state(manifest.scope_id)
        baseline = state or empty_publication_scope(manifest.scope_id)
        if baseline['active_operation'] is not None:
            raise ValueError('PUBLICATION_PRIOR_OPERATION_UNRESOLVED')
        if baseline['visible']['generation'] != manifest.base_generation:
            raise ValueError('PUBLICATION_BASE_GENERATION_CONFLICT')
        generation, token = baseline['last_generation'] + 1, baseline['fence'] + 1
        operation = {'operation_id': operation_id, 'scope_id': manifest.scope_id, 'generation': generation,
                     'token': token, 'writer_id': writer_id, 'lease_until': self.clock() + self.lease_seconds,
                     'status': 'reserved', 'projection_receipt': None}
        self._cas([
            AtomicWrite(SCOPES, manifest.scope_id, state, {**baseline, 'last_generation': generation,
                        'fence': token, 'active_operation': operation_id}),
            AtomicWrite(MANIFESTS, operation_id, None, {'manifest': manifest.model_dump(mode='json')}),
            AtomicWrite(OUTBOX, operation_id, None, operation), *admitted.fences,
        ], operation_id)
        # SQLite guard may lag PG after a crash. No new publication can pass the PG
        # fence in that window; successor reconciliation installs the guard first.
        self.projection.install_guard(manifest.scope_id, token)
        return self._handle(operation)

    def take_over(self, scope, operation_id, *, writer_id):
        if not isinstance(writer_id, str) or not writer_id.strip():
            raise ValueError('PUBLICATION_WRITER_ID_REQUIRED')
        state, operation = self._state(scope), self.store.get(OUTBOX, operation_id)
        if (not state or not operation or state['active_operation'] != operation_id
                or operation['scope_id'] != scope or operation['status'] == 'aborted'):
            raise ValueError('PUBLICATION_OPERATION_UNAVAILABLE')
        if operation['lease_until'] > self.clock():
            raise ValueError('PUBLICATION_WRITER_BUSY')
        token = state['fence'] + 1
        updated = {**operation, 'token': token, 'writer_id': writer_id,
                   'lease_until': self.clock() + self.lease_seconds}
        self._cas([AtomicWrite(SCOPES, scope, state, {**state, 'fence': token}),
                   AtomicWrite(OUTBOX, operation_id, operation, updated)], operation_id)
        self.projection.install_guard(scope, token)
        return self._handle(updated)

    def renew(self, handle):
        state, operation = self._owned(handle, phases=('reserved','prepared','published','aborting'))
        self._cas([AtomicWrite(SCOPES, handle.scope_id, state, state),
                   AtomicWrite(OUTBOX, handle.operation_id, operation,
                               {**operation, 'lease_until': self.clock() + self.lease_seconds})], handle.operation_id)

    def prepare(self, handle):
        state, operation = self._owned(handle, phases=('reserved','prepared'))
        self.projection.install_guard(handle.scope_id, handle.token)
        manifest = self._manifest(handle.operation_id)
        batch = self.materialize(manifest)
        receipt = self.projection.prepare(manifest, batch, generation=handle.generation,
                                          operation_id=handle.operation_id, token=handle.token)
        if operation['status'] == 'prepared':
            if operation['projection_receipt'] != receipt:
                raise ValueError('PUBLICATION_PROJECTION_RECEIPT_CONFLICT')
            return receipt
        self._cas([AtomicWrite(SCOPES, handle.scope_id, state, state),
                   AtomicWrite(OUTBOX, handle.operation_id, operation,
                               {**operation, 'status': 'prepared', 'projection_receipt': receipt})], handle.operation_id)
        return receipt

    def commit(self, handle):
        operation = self.store.get(OUTBOX, handle.operation_id)
        if operation and operation['status'] == 'published':
            return self.reconcile(handle)
        state, operation = self._owned(handle, phases=('prepared','published'))
        if operation['status'] == 'published':
            return self.reconcile(handle)
        manifest = self._manifest(handle.operation_id)
        admitted = self._admit(manifest, 'commit')
        projection = self.projection.receipt(handle.scope_id, handle.generation)
        if (not projection or projection['status'] != 'prepared' or projection['manifest_digest'] != handle.operation_id
                or projection['receipt'] != operation['projection_receipt']):
            raise ValueError('PUBLICATION_PROJECTION_NOT_READY')
        if state['visible']['generation'] != manifest.base_generation:
            raise ValueError('PUBLICATION_BASE_GENERATION_CONFLICT')
        receipt = {'operation_id': handle.operation_id, 'scope_id': handle.scope_id, 'generation': handle.generation,
                   'manifest_digest': manifest.digest, 'projection_receipt_digest': semantic_digest(projection['receipt']),
                   'application_store_durable': bool(self.store.durable), 'semantic_truth_proven': False}
        self._cas([
            AtomicWrite(SCOPES, handle.scope_id, state, {**state, 'visible': {
                'generation': handle.generation, 'manifest_digest': manifest.digest}}),
            AtomicWrite(OUTBOX, handle.operation_id, operation, {**operation, 'status': 'published'}),
            AtomicWrite(RECEIPTS, handle.operation_id, None, receipt),
            *admitted.fences, *admitted.public_writes,
        ], handle.operation_id)
        # Keep active_operation until SQLite finalization. G2 cannot skip a PG-
        # published but locally unfinished G1 during a crash/restart.
        return self.reconcile(handle)

    def reconcile(self, handle):
        operation = self.store.get(OUTBOX, handle.operation_id)
        state = self._state(handle.scope_id)
        if operation and (operation['scope_id'] != handle.scope_id or operation['generation'] != handle.generation):
            raise ValueError('PUBLICATION_HANDLE_BINDING_INVALID')
        if (operation and operation['status'] == 'published' and state
                and state['active_operation'] != handle.operation_id):
            # Already finalized; a later generation may now be active or visible.
            return self.store.get(RECEIPTS, handle.operation_id)
        if operation and operation['status'] == 'aborted' and state and state['active_operation'] != handle.operation_id:
            return {'operation_id': handle.operation_id, 'status': 'aborted', 'generation': handle.generation}
        state, operation = self._owned(handle, phases=('reserved','prepared','published','aborting'))
        self.projection.install_guard(handle.scope_id, handle.token)
        if operation['status'] == 'published':
            if state['visible'] != {'generation': handle.generation, 'manifest_digest': handle.operation_id}:
                raise ValueError('PUBLICATION_PUBLIC_POINTER_CONFLICT')
            self.projection.mark_committed(handle.scope_id, handle.generation, handle.operation_id, token=handle.token)
            self._cas([AtomicWrite(SCOPES, handle.scope_id, state, {**state, 'active_operation': None}),
                       AtomicWrite(OUTBOX, handle.operation_id, operation, operation)], handle.operation_id)
            return self.store.get(RECEIPTS, handle.operation_id)
        if operation['status'] == 'aborting':
            return self.abort(handle)
        # If SQLite committed before the prepared CAS/response, resume this exact
        # operation. No inference from an absent receipt to a fresh operation.
        return {'operation_id': handle.operation_id, 'status': operation['status'],
                'projection': self.projection.receipt(handle.scope_id, handle.generation)}

    def abort(self, handle):
        operation = self.store.get(OUTBOX, handle.operation_id)
        if operation and operation['status'] == 'aborted':
            return self.reconcile(handle)
        state, operation = self._owned(handle, phases=('reserved','prepared','aborting'))
        if state['visible']['generation'] >= handle.generation:
            raise ValueError('PUBLICATION_ALREADY_VISIBLE')
        if operation['status'] != 'aborting':
            self._cas([AtomicWrite(SCOPES, handle.scope_id, state, state),
                       AtomicWrite(OUTBOX, handle.operation_id, operation, {**operation, 'status': 'aborting'})], handle.operation_id)
            state, operation = self._owned(handle, phases=('aborting',))
        # The exact aborting CAS excludes any pending commit before touching rows.
        self.projection.install_guard(handle.scope_id, handle.token)
        manifest = self._manifest(handle.operation_id)
        self.projection.abort(handle.scope_id, handle.generation, handle.operation_id,
                              token=handle.token, base_generation=manifest.base_generation)
        self._cas([AtomicWrite(SCOPES, handle.scope_id, state, {**state, 'active_operation': None}),
                   AtomicWrite(OUTBOX, handle.operation_id, operation, {**operation, 'status': 'aborted'})], handle.operation_id)
        return {'operation_id': handle.operation_id, 'status': 'aborted', 'generation': handle.generation}

    def snapshot(self, scope):
        """Internal pointer only. Public UI/MCP must also enforce current source ACL."""
        state = self._state(scope)
        visible = state['visible'] if state else {'generation': 0, 'manifest_digest': None}
        snapshot = ProjectionSnapshot(scope, visible['generation'], visible['manifest_digest'])
        if snapshot.generation:
            row = self.projection.receipt(scope, snapshot.generation)
            receipt = self.store.get(RECEIPTS, snapshot.manifest_digest)
            if (not row or row['manifest_digest'] != snapshot.manifest_digest or row['status'] == 'aborted'
                    or not receipt or receipt['generation'] != snapshot.generation or receipt['scope_id'] != scope
                    or receipt['projection_receipt_digest'] != semantic_digest(row['receipt'])):
                raise ValueError('PUBLICATION_READ_MODEL_UNAVAILABLE')
        return snapshot
