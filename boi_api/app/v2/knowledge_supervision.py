"""Durable, source-authorized correction instructions and work stop controls.

Events preserve exact targets. Resolution reports handling of an instruction;
it neither changes meaning nor verifies quality, execution, or completion.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..governed_runtime.ledger import RecordKind, record_digest
from ..governed_runtime.semantic_binding_contract import FrozenContract, Ref, RevisionRef, semantic_digest
from .atomic_store_contract import AtomicWrite


class SupervisionMutation(FrozenContract):
    task_ref: Ref
    expected_revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=8000)
    idempotency_key: str = Field(min_length=1, max_length=240)

    @model_validator(mode='after')
    def reason_required(self):
        if not self.reason.strip():
            raise ValueError('KNOWLEDGE_SUPERVISION_REASON_REQUIRED')
        return self


class CorrectionRequest(SupervisionMutation):
    unit_ids: tuple[Ref, ...] = Field(default=(), max_length=2000)
    asset_revisions: tuple[RevisionRef, ...] = Field(default=(), max_length=100)
    cause_code: Literal['source', 'interpretation', 'coverage', 'other'] = 'other'

    @model_validator(mode='after')
    def unique_targets(self):
        if len(set(self.unit_ids)) != len(self.unit_ids) or len(set(self.asset_revisions)) != len(self.asset_revisions):
            raise ValueError('KNOWLEDGE_SUPERVISION_TARGET_DUPLICATE')
        return self


class ResolutionRequest(SupervisionMutation):
    event_ref: RevisionRef


class SupervisionRead(FrozenContract):
    task_ref: Ref
    event_ref: RevisionRef | None = None


class KnowledgeSupervisionRequest(FrozenContract):
    operation: Literal['list', 'read', 'correct', 'resolve', 'stop',
        'document_feedback', 'feedback_inbox', 'feedback_read']
    request: dict


class KnowledgeSupervisionService:
    CONTRACT = 'boi/knowledge-supervision@1'
    MAX_PENDING = 100

    def __init__(self, intake, work_service):
        if work_service.intake is not intake:
            raise ValueError('KNOWLEDGE_SUPERVISION_WORK_SERVICE_MISMATCH')
        self.intake, self.work = intake, work_service
        self.store, self.ledger, self.assets = intake.store, intake.ledger, work_service.assets

    def _task(self, authorization, task_ref, *, mutate=False):
        self.work._authorize(authorization, mutate=mutate)
        return self.work._read(authorization, task_ref)

    def _cas(self, *writes):
        if not self.store.atomic_compare_and_write(writes):
            raise ValueError('KNOWLEDGE_SUPERVISION_REVISION_CONFLICT')

    def _event(self, authorization, reference, task_ref):
        ref = RevisionRef.model_validate(reference)
        row = self.store.get('task_runs', ref.ref)
        if (not row or row.get('contract_version') != self.CONTRACT or row.get('employee_id') != authorization.principal
                or row.get('policy_digest') != authorization.policy_digest or row.get('task_ref') != task_ref
                or row.get('event_ref') != ref.model_dump(mode='json')):
            raise ValueError('KNOWLEDGE_SUPERVISION_EVENT_ACCESS_DENIED')
        record = self.ledger.read(ref.ref)
        if (record.kind != RecordKind.RUN or record_digest(record.record_id) != ref.revision_digest
                or semantic_digest(record.payload) != row.get('record_payload_digest')
                or any(row.get(key) != value for key, value in record.payload.items())):
            raise ValueError('KNOWLEDGE_SUPERVISION_EVENT_INTEGRITY')
        expected = 'pending' if row['operation'] == 'correct' else 'reported_resolved' if row['operation'] == 'resolve' else 'stopped'
        if row.get('resolution_ref'):
            resolution = self.ledger.read(row['resolution_ref']['ref'])
            if resolution.payload.get('operation') != 'resolve' or resolution.payload.get('parent_event_ref') != row['event_ref']:
                raise ValueError('KNOWLEDGE_SUPERVISION_RESOLUTION_INTEGRITY')
            self._event(authorization, row['resolution_ref'], task_ref)
            expected = 'reported_resolved'
        if row['state'] != expected:
            raise ValueError('KNOWLEDGE_SUPERVISION_EVENT_STATE_INVALID')
        for revision in row['asset_revisions']:
            self.assets.read(authorization=authorization, revision=RevisionRef.model_validate(revision), lane='provisional')
        return row

    def _targets(self, authorization, task, req):
        units = {unit['unit_id']: unit for unit in task['units']}
        unit_ids = list(req.unit_ids) if req.unit_ids or req.asset_revisions else list(units)
        if not set(unit_ids) <= set(units):
            raise ValueError('KNOWLEDGE_SUPERVISION_UNIT_OUTSIDE_TASK')
        fences, assets = [], []
        task_sources = {source['artifact_ref'] for source in task['sources']}
        task_results = {item['revision']['ref'] for unit in task['units'] for item in unit.get('results', ()) if item.get('revision')}
        for ref in req.asset_revisions:
            asset = self.assets.read(authorization=authorization, revision=ref, lane='provisional')
            if ref.ref not in task_results and not task_sources.intersection(source['artifact_ref'] for source in asset['sources']):
                raise ValueError('KNOWLEDGE_SUPERVISION_ASSET_OUTSIDE_TASK')
            key = 'domain-asset-head:' + semantic_digest([authorization.principal, asset['namespace'], asset['logical_id']])
            head = self.store.get('domain_asset_heads', key)
            if not head or head['revision'] != ref.model_dump(mode='json'):
                raise ValueError('KNOWLEDGE_SUPERVISION_ASSET_REVISION_CHANGED')
            fences.append(AtomicWrite('domain_asset_heads', key, head, head))
            assets.append(ref.model_dump(mode='json'))
            if not req.unit_ids:
                evidence = {item['ref'] for item in asset['asset'].get('evidence', ())}
                linked = [unit['unit_id'] for unit in task['units']
                    if any(item.get('revision', {}).get('ref') == ref.ref for item in unit.get('results', ()))
                    or evidence.intersection(unit['span_refs'])]
                if not linked:
                    raise ValueError('KNOWLEDGE_SUPERVISION_ASSET_UNIT_SCOPE_REQUIRED')
                unit_ids.extend(unit_id for unit_id in linked if unit_id not in unit_ids)
        return unit_ids, assets, fences

    def _view(self, row, task):
        return {**{key: row[key] for key in ('event_ref', 'task_ref', 'operation', 'state', 'reason',
                    'cause_code', 'unit_ids', 'asset_revisions', 'impact', 'created_at')},
                'target_task_revision': row['target_task_revision'], 'task_revision': task['revision'],
                'resolution_ref': row.get('resolution_ref'), 'parent_event_ref': row.get('parent_event_ref'),
                'semantic_quality': 'not_evaluated', 'approval_required': False,
                'url': '/knowledge?tab=work'}

    def instructions_for_task(self, *, authorization, task_ref):
        task = self._task(authorization, task_ref)
        events = []
        for ref in task.get('supervision_event_refs', ()):
            event = self._event(authorization, ref, task_ref)
            if event['state'] == 'pending':
                events.append(self._view(event, task))
        return {'items': events, 'task_ref': task_ref, 'task_revision': task['revision'],
                'instruction_authority': 'user_correction_request',
                'read_is_resolution': False, 'approval_required': False}

    def dispatch(self, *, authorization, operation, request):
        if operation in ('list', 'read'):
            req = SupervisionRead.model_validate(request)
            task = self._task(authorization, req.task_ref)
            if operation == 'list':
                if req.event_ref is not None:
                    raise ValueError('KNOWLEDGE_SUPERVISION_LIST_EVENT_UNEXPECTED')
                return self.instructions_for_task(authorization=authorization, task_ref=req.task_ref)
            if req.event_ref is None:
                raise ValueError('KNOWLEDGE_SUPERVISION_EVENT_REQUIRED')
            return self._view(self._event(authorization, req.event_ref, req.task_ref), task)
        cls = {'correct': CorrectionRequest, 'resolve': ResolutionRequest, 'stop': SupervisionMutation}.get(operation)
        if cls is None:
            raise ValueError('KNOWLEDGE_SUPERVISION_OPERATION_INVALID')
        req = cls.model_validate(request)
        task = self._task(authorization, req.task_ref, mutate=True)
        wire = req.model_dump(mode='json')
        fingerprint = semantic_digest({'operation': operation, 'request': wire})
        key = 'knowledge-supervision-idem:' + semantic_digest([authorization.principal, operation, req.idempotency_key])
        old = self.store.get('agent_task_idempotency', key)
        if old and old['fingerprint'] != fingerprint:
            raise ValueError('KNOWLEDGE_SUPERVISION_IDEMPOTENCY_CONFLICT')
        if old and old.get('event_ref'):
            return {**self._view(self._event(authorization, old['event_ref'], req.task_ref), task), 'replayed': True}

        parent, fences = None, []
        if operation == 'resolve':
            parent = self._event(authorization, req.event_ref, req.task_ref)
            if parent['operation'] != 'correct':
                raise ValueError('KNOWLEDGE_SUPERVISION_CORRECTION_REQUIRED')
            if parent.get('resolution_ref'):
                resolved = self._event(authorization, parent['resolution_ref'], req.task_ref)
                return {**self._view(resolved, task), 'replayed': True}
            unit_ids, assets = parent['unit_ids'], parent['asset_revisions']
        elif operation == 'correct':
            unit_ids, assets, fences = self._targets(authorization, task, req)
            if len(task.get('supervision_event_refs', ())) >= self.MAX_PENDING:
                raise ValueError('KNOWLEDGE_SUPERVISION_PENDING_LIMIT')
        else:
            unit_ids, assets = [unit['unit_id'] for unit in task['units']], []
        if old is None:
            if task['revision'] != req.expected_revision:
                raise ValueError('KNOWLEDGE_SUPERVISION_REVISION_CONFLICT')
            old = {'employee_id': authorization.principal, 'fingerprint': fingerprint,
                   'created_at': self.intake.clock().isoformat(), 'event_ref': None}
            self._cas(AtomicWrite('agent_task_idempotency', key, None, old),
                      AtomicWrite('agent_task_packages', req.task_ref, task, task), *fences)
            old = self.store.get('agent_task_idempotency', key)
        if operation == 'stop':
            self.work.control(authorization=authorization, operation='stop', request={**wire, 'idempotency_key': key})
            task = self._task(authorization, req.task_ref, mutate=True)
        elif task['revision'] != req.expected_revision:
            raise ValueError('KNOWLEDGE_SUPERVISION_REVISION_CONFLICT')

        payload = {'contract_version': self.CONTRACT, 'employee_id': authorization.principal,
            'policy_digest': authorization.policy_digest, 'task_ref': req.task_ref,
            'target_task_revision': req.expected_revision, 'operation': operation, 'reason': req.reason,
            'cause_code': req.cause_code if operation == 'correct' else parent['cause_code'] if parent else 'stopped',
            'unit_ids': unit_ids, 'asset_revisions': assets,
            'parent_event_ref': req.event_ref.model_dump(mode='json') if parent else None,
            'impact': {'selected_unit_count': len(unit_ids), 'selected_asset_count': len(assets),
                       'target_scope': (parent['impact']['target_scope'] if parent else
                           'task' if operation == 'stop' or not (req.unit_ids or req.asset_revisions) else
                           'units_and_assets' if req.unit_ids and req.asset_revisions else 'units' if req.unit_ids else 'assets'),
                       'originals_preserved': True, 'budgets_reset': False,
                       'active_attempt_ref': task.get('active_attempt_ref')},
            'semantic_quality': 'not_evaluated', 'approval_required': False}
        event = self.ledger.append(RecordKind.RUN, payload, authority='executor', occurred_at=old['created_at'])
        ref = {'ref': event.record_id, 'revision_digest': record_digest(event.record_id)}
        state = 'pending' if operation == 'correct' else 'reported_resolved' if parent else 'stopped'
        row = {**payload, 'event_ref': ref, 'state': state, 'created_at': old['created_at'],
               'record_payload_digest': semantic_digest(event.payload)}
        updated = {**task}
        pending = list(task.get('supervision_event_refs', ()))
        if operation == 'correct':
            pending.append(ref)
        elif parent:
            pending = [item for item in pending if item != parent['event_ref']]
        if operation != 'stop':
            updated.update(revision=task['revision'] + 1, supervision_event_refs=pending)
        writes = [AtomicWrite('agent_task_packages', req.task_ref, task, updated),
                  AtomicWrite('task_runs', ref['ref'], None, row),
                  AtomicWrite('agent_task_idempotency', key, old, {**old, 'event_ref': ref}), *fences]
        if parent:
            writes.append(AtomicWrite('task_runs', parent['event_ref']['ref'], parent,
                          {**parent, 'state': 'reported_resolved', 'resolution_ref': ref}))
        self._cas(*writes)
        return self._view(row, updated)
