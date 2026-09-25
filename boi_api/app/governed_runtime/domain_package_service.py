"""Immutable package versions and bounded HOTL adoption in the existing ledger.

This is a projection of shipped kit resources and ordinary provisional pack
assets, not another skill registry or a platform release mechanism. Semantic
work is external. Only configured, signed reference evaluations qualify here;
their result is not a claim of general semantic correctness.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import json
from pathlib import Path

from agent_kit.package_contract import RESOURCE_CONTRACT, dependency_order, shipped_entries

from ..v2.atomic_store_contract import AtomicWrite
from .domain_asset_store import DomainAssetStore
from .domain_package_contract import DomainPackageManifest, DomainPackageObservation, DomainPackagePolicy
from .domain_work_contract import DomainToolEvidenceRequest, DomainToolReport
from .domain_work_service import DomainWorkService
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import byte_digest
from .tool_execution_contract import SignedToolExecution, ToolInvocation, verify_tool_execution


def _wire(value):
    return value.model_dump(mode='json') if hasattr(value, 'model_dump') else value


def _ref(value):
    return RevisionRef.model_validate(value)


class DomainPackageService:
    CONTRACT = 'boi/domain-package-event@1'
    BUILTIN = 'boi/shipped-domain-package@1'

    def __init__(self, source_intake, *, catalog=None, policies=(), trusted_executors=(), clock=None):
        self.intake = source_intake
        self.store, self.ledger, self.objects = source_intake.store, source_intake.ledger, source_intake.objects
        self.assets = DomainAssetStore(source_intake)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.trusted_executors = tuple(trusted_executors)
        self.policies = {}
        for value in policies:
            policy = DomainPackagePolicy.model_validate(value)
            if policy.team_id in self.policies:
                raise ValueError('DOMAIN_PACKAGE_POLICY_AMBIGUOUS')
            self.policies[policy.team_id] = policy
        self.repo_root = Path(__file__).resolve().parents[3]
        self.catalog_path = Path(catalog) if catalog is not None else self.repo_root / 'agent_kit/package.json'

    def _scope(self, authorization, principal_teams, team_id=None, *, mutation=False):
        self.intake._policy(authorization)
        if mutation and not {'store', 'derive', 'model_input'} <= set(authorization.allowed_uses):
            raise ValueError('DOMAIN_PACKAGE_MUTATION_NOT_AUTHORIZED')
        if team_id is not None:
            if not isinstance(team_id, str) or team_id not in set(principal_teams):
                raise ValueError('DOMAIN_PACKAGE_TEAM_ACCESS_DENIED')
            return 'team:' + team_id
        return 'private:' + authorization.principal

    @staticmethod
    def _key(kind, *parts):
        return 'domain-package-' + kind + ':' + semantic_digest(parts)

    def _row(self, kind, *parts):
        return self.store.get('agent_task_idempotency', self._key(kind, *parts))

    def _record(self, revision, *, event=None):
        revision = _ref(revision)
        record = self.ledger.read(revision.ref)
        if record_digest(record.record_id) != revision.revision_digest:
            raise ValueError('DOMAIN_PACKAGE_REVISION_MISMATCH')
        if event is not None and (record.kind != RecordKind.RUN or
                record.payload.get('contract_version') != self.CONTRACT or record.payload.get('event') != event):
            raise ValueError('DOMAIN_PACKAGE_EVENT_CONTRACT_INVALID')
        return record

    def _reserve(self, authorization, operation, request, idempotency_key):
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240:
            raise ValueError('DOMAIN_PACKAGE_IDEMPOTENCY_KEY_INVALID')
        key = self._key('operation', authorization.principal, operation, idempotency_key)
        digest = semantic_digest(request)
        row = self.store.get('agent_task_idempotency', key)
        if row is None:
            row = {'contract_version': self.CONTRACT, 'employee_id': authorization.principal,
                'operation': operation, 'fingerprint': digest, 'occurred_at': self.clock().isoformat(), 'state': 'reserved'}
            if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_idempotency', key, None, row),)):
                row = self.store.get('agent_task_idempotency', key)
            else:
                row = self.store.get('agent_task_idempotency', key)
        if row is None or row.get('fingerprint') != digest:
            raise ValueError('DOMAIN_PACKAGE_IDEMPOTENCY_CONFLICT')
        return key, row

    def _event(self, authorization, operation, request, idempotency_key, *, payload, writes=(), response=None):
        key, reservation = self._reserve(authorization, operation, request, idempotency_key)
        if reservation['state'] == 'published':
            return {**reservation['response'], 'replayed': True}
        material = {
            'contract_version': self.CONTRACT, 'event': operation,
            'employee_id': authorization.principal, 'policy_digest': authorization.policy_digest,
            **payload,
        }
        plan_digest = semantic_digest(material)
        if reservation.get('plan_digest') is None:
            planned = {**reservation, 'plan_digest': plan_digest}
            if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_idempotency', key, reservation, planned),)):
                raise ValueError('DOMAIN_PACKAGE_PUBLICATION_CONFLICT')
            reservation = self.store.get('agent_task_idempotency', key)
        if reservation.get('plan_digest') != plan_digest:
            raise ValueError('DOMAIN_PACKAGE_PUBLICATION_RECOVERY_REQUIRED')
        record = self.ledger.append(RecordKind.RUN, material,
            authority='executor', occurred_at=reservation['occurred_at'])
        revision = self.assets._ref(record).model_dump(mode='json')
        result = {'revision': revision, **(response or {}), 'replayed': False}
        extra = writes(revision) if callable(writes) else writes
        publication = {'contract_version': self.CONTRACT, 'record_payload_digest': semantic_digest(record.payload),
            'revision': revision, 'event': operation}
        event_key = self._key('event', revision)
        existing = self.store.get('task_runs', event_key)
        done = {**reservation, 'state': 'published', 'response': result}
        if not self.store.atomic_compare_and_write((
            AtomicWrite('agent_task_idempotency', key, reservation, done),
            AtomicWrite('task_runs', event_key, existing, publication), *extra,
        )):
            replay = self.store.get('agent_task_idempotency', key)
            if replay and replay.get('state') == 'published' and replay.get('fingerprint') == reservation['fingerprint']:
                return {**replay['response'], 'replayed': True}
            raise ValueError('DOMAIN_PACKAGE_PUBLICATION_CONFLICT')
        return result

    def _published_event(self, revision, event):
        record = self._record(revision, event=event)
        row = self.store.get('task_runs', self._key('event', _wire(_ref(revision))))
        if not row or row.get('record_payload_digest') != semantic_digest(record.payload):
            raise ValueError('DOMAIN_PACKAGE_EVENT_NOT_PUBLISHED')
        return record.payload

    def _builtin_entries(self, package_ids=None, *, catalog=None, cache=None):
        if catalog is None:
            if not self.catalog_path.is_file():
                return []
            catalog = json.loads(self.catalog_path.read_text(encoding='utf-8'))
        if package_ids is not None and not set(package_ids) <= {entry['id'] for entry in catalog['domain_packages']}:
            raise ValueError('DOMAIN_PACKAGE_NOT_FOUND')
        return shipped_entries(catalog, self.repo_root / 'agent_kit', package_ids, cache=cache)

    def _builtin(self, package_id, *, publish=False, entry=None):
        if entry is None:
            entry = next((item for item in self._builtin_entries([package_id]) if item['id'] == package_id), None)
        if entry is None or entry['id'] != package_id:
            raise ValueError('DOMAIN_PACKAGE_NOT_FOUND')
        digest = semantic_digest(entry)
        key = self._key('builtin', digest)
        saved = self.store.get('agent_task_idempotency', key)
        if not publish:
            return {'package_id': package_id, 'revision': saved.get('revision') if saved else None,
                'manifest': entry, 'manifest_digest': digest, 'origin': 'shipped'}
        if saved is None:
            saved = {'occurred_at': self.clock().isoformat(), 'manifest_digest': digest}
            if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_idempotency', key, None, saved),)):
                saved = self.store.get('agent_task_idempotency', key)
            else:
                saved = self.store.get('agent_task_idempotency', key)
        if saved.get('revision') is None:
            # Preserve executable-free guidance bytes, not just pointers into a
            # mutable checkout. Historical task pins can read the exact kit.
            for resource_path, expected_digest in entry['resource_digests'].items():
                raw = (self.repo_root / resource_path).read_bytes()
                if byte_digest(raw) != expected_digest or self.objects.put(raw) != expected_digest:
                    raise ValueError('DOMAIN_PACKAGE_SHIPPED_RESOURCE_CHANGED')
            content = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            content_ref = self.objects.put(content.encode())
            record = self.ledger.append(RecordKind.KNOWLEDGE_REVISION, {
                'contract_version': self.BUILTIN, 'kind': 'pack', 'status': 'candidate',
                'manifest': entry, 'manifest_digest': digest, 'content_object_ref': content_ref,
                'execution_mode': 'external_agent_skill',
            }, authority='migration_service', occurred_at=saved['occurred_at'])
            revision = self.assets._ref(record).model_dump(mode='json')
            new = {**saved, 'revision': revision}
            if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_idempotency', key, saved, new),)):
                new = self.store.get('agent_task_idempotency', key)
            saved = new
        return {'package_id': package_id, 'revision': saved['revision'], 'manifest': entry,
            'manifest_digest': digest, 'origin': 'shipped'}

    def _policy(self, team_id):
        policy = self.policies.get(team_id)
        if policy is None:
            raise ValueError('DOMAIN_PACKAGE_HOTL_POLICY_UNAVAILABLE')
        now = self.clock()
        available = {release.revision for trust in self.trusted_executors
            if not trust.revoked and trust.valid_from <= now < trust.valid_until
            and trust.executor_id in policy.evaluator_executor_ids for release in trust.releases}
        if not set(policy.evaluator_tool_revisions) <= available:
            raise ValueError('DOMAIN_PACKAGE_TRUSTED_EVALUATOR_UNAVAILABLE')
        return policy

    def discover(self, *, authorization, principal_teams=(), team_id=None):
        scope = self._scope(authorization, principal_teams, team_id)
        items = [self._builtin(item['id'], entry=item) for item in self._builtin_entries()]
        for row in self.store.list('agent_task_idempotency', limit=10000):
            if row.get('record_type') == 'domain_package_binding' and row.get('scope_key') == scope and row.get('adoption_revision'):
                item = self.read(authorization=authorization, principal_teams=principal_teams,
                    package_id=row['package_id'], team_id=team_id)
                items = [value for value in items if value['package_id'] != row['package_id']]
                items.append(item)
        try:
            policy = self._policy(team_id)
            hotl = {'available': True, 'qualification_scope': policy.qualification_scope, 'human_approval_required': False}
        except ValueError as exc:
            hotl = {'available': False, 'reason_code': str(exc), 'semantic_quality': 'not_evaluated'}
        return {'scope_key': scope, 'team_id': team_id, 'items': items, 'hotl': hotl,
            'contracts': {'manifest': DomainPackageManifest.model_json_schema(),
                'evaluator_observation': DomainPackageObservation.model_json_schema(),
                'policy_authority': 'server_configuration',
                'assessment_inputs': 'Returned by create_candidate; use the exact bytes and input names.'}}

    def freeze_policy(self, *, authorization, principal_teams=(), team_id, idempotency_key):
        scope = self._scope(authorization, principal_teams, team_id, mutation=True)
        policy = self._policy(team_id)
        row = self._row('policy', scope)
        frozen = policy.model_dump(mode='json')
        request = {'scope_key': scope, 'policy': frozen}
        key, reservation = self._reserve(authorization, 'policy_frozen', request, idempotency_key)
        if reservation['state'] == 'published':
            return {**reservation['response'], 'replayed': True}
        if row and row.get('policy_digest') == semantic_digest(frozen):
            existing = self._published_event(row['policy_revision'], 'policy_frozen')
            if existing.get('authorization_policy_digest') == authorization.policy_digest:
                response = {'revision': row['policy_revision'], 'policy': frozen,
                    'semantic_quality': 'not_evaluated', 'replayed': True}
                if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_idempotency', key, reservation,
                        {**reservation, 'state': 'published', 'response': response}),
                        self._policy_fence(scope, row['policy_revision']))):
                    raise ValueError('DOMAIN_PACKAGE_PUBLICATION_CONFLICT')
                return response
        def writes(revision):
            return (AtomicWrite('agent_task_idempotency', self._key('policy', scope), row,
                {'scope_key': scope, 'policy_revision': revision, 'policy_digest': semantic_digest(frozen)}),)
        return self._event(authorization, 'policy_frozen', request, idempotency_key,
            payload={**request, 'authorization_policy_digest': authorization.policy_digest}, writes=writes,
            response={'policy': frozen, 'semantic_quality': 'not_evaluated'})

    def _frozen_policy(self, authorization, team_id, revision):
        body = self._published_event(revision, 'policy_frozen')
        configured = self._policy(team_id)
        if (body.get('scope_key') != 'team:' + team_id or body.get('authorization_policy_digest') != authorization.policy_digest
                or body['policy'] != configured.model_dump(mode='json')):
            raise ValueError('DOMAIN_PACKAGE_POLICY_STALE')
        row = self._row('policy', 'team:' + team_id)
        if not row or row['policy_revision'] != _wire(_ref(revision)):
            raise ValueError('DOMAIN_PACKAGE_POLICY_STALE')
        return configured

    def _policy_fence(self, scope_key, revision):
        key = self._key('policy', scope_key)
        row = self.store.get('agent_task_idempotency', key)
        if not row or row.get('policy_revision') != _wire(_ref(revision)):
            raise ValueError('DOMAIN_PACKAGE_POLICY_STALE')
        return AtomicWrite('agent_task_idempotency', key, row, row)

    def _shared_asset(self, authorization, team_id, revision, *, _source_cache=None):
        """Exact package-only sharing; ordinary owner source reads remain strict."""
        revision = _ref(revision)
        record = self._record(revision)
        body = record.payload
        row = self.store.get('domain_knowledge_assets', record.record_id)
        if (record.kind != RecordKind.KNOWLEDGE_REVISION or body.get('contract_version') != self.assets.CONTRACT
                or body.get('status') != 'candidate' or body.get('policy_digest') != authorization.policy_digest
                or not row or row.get('record_payload_digest') != semantic_digest(body)):
            raise ValueError('DOMAIN_PACKAGE_SHARED_ASSET_DENIED')
        if not {'derive', 'model_input'} <= set(authorization.allowed_uses) or not body.get('sources'):
            raise ValueError('DOMAIN_PACKAGE_SHARED_ASSET_USE_DENIED')
        for source in body['sources']:
            source_key = (source['artifact_ref'], source['digest'], source['role'], body['employee_id'])
            if _source_cache is not None and source_key in _source_cache:
                continue
            artifact = self.ledger.read(source['artifact_ref'])
            value = artifact.payload
            rights = self.ledger.read(value['rights_record_ref'])
            r = rights.payload
            if (artifact.kind != RecordKind.SOURCE_ARTIFACT or rights.kind != RecordKind.SOURCE_RIGHTS_RECORD
                    or value.get('owner') != body['employee_id'] or r.get('principal') != body['employee_id']
                    or r.get('policy_digest') != authorization.policy_digest or value.get('policy_digest') != authorization.policy_digest
                    or r.get('visibility') != 'team' or r.get('team_id') != team_id
                    or not {'derive', 'model_input', 'org_share'} <= set(r.get('allowed_uses', ()))
                    or r.get('content_digest') != source['digest'] or value.get('content_digest') != source['digest']
                    or value.get('role') != source['role'] or r.get('source_capture_ref') != value.get('source_capture_ref')):
                raise ValueError('DOMAIN_PACKAGE_SOURCE_NOT_TEAM_SHAREABLE')
            def verify(raw):
                if byte_digest(raw) != source['digest']:
                    raise ValueError('DOMAIN_PACKAGE_SOURCE_NOT_TEAM_SHAREABLE')
                return len(raw)
            project = getattr(self.objects, 'project_verified', None)
            if project:
                project(value['object_ref'], version='source-integrity@1:' + source['digest'], derive=verify)
            else:
                verify(self.objects.get(value['object_ref']))
            if _source_cache is not None:
                _source_cache.add(source_key)
        return record, self.assets._asset(record, revision, self.objects.get(body['content_object_ref']))

    def _pack(self, authorization, team_id, revision, *, policy=None):
        source_cache = set()
        record, asset = self._shared_asset(authorization, team_id, revision, _source_cache=source_cache)
        if asset.kind != 'pack':
            raise ValueError('DOMAIN_PACKAGE_PACK_ASSET_REQUIRED')
        manifest = DomainPackageManifest.model_validate_json(asset.content_json)
        direct = {dep.revision for dep in asset.dependencies}
        if not set(manifest.members) <= direct:
            raise ValueError('DOMAIN_PACKAGE_MEMBER_DEPENDENCY_REQUIRED')
        closure = {}
        pending = list(direct)
        while pending:
            ref = pending.pop()
            if ref in closure:
                continue
            if len(closure) >= 100:
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_LIMIT')
            _, member = self._shared_asset(authorization, team_id, ref, _source_cache=source_cache)
            closure[ref] = member
            pending.extend(dep.revision for dep in member.dependencies)
        if policy is not None:
            if (not set(manifest.supported_operations) <= set(policy.allowed_operations)
                    or not set(manifest.content_contracts) <= set(policy.allowed_content_contracts)):
                raise ValueError('DOMAIN_PACKAGE_CAPABILITY_EXPANSION_DENIED')
            from .domain_work_contract import DomainHarnessContract
            for member in closure.values():
                if member.kind == 'tool' and member.revision not in policy.allowed_tool_revisions:
                    raise ValueError('DOMAIN_PACKAGE_EXECUTABLE_CAPABILITY_DENIED')
                if member.kind == 'harness':
                    harness = DomainHarnessContract.model_validate_json(member.content_json)
                    if any(tool.tool_revision not in policy.allowed_tool_revisions
                            for stage in harness.stages for tool in stage.tools):
                        raise ValueError('DOMAIN_PACKAGE_EXECUTABLE_CAPABILITY_DENIED')
        return record, asset, manifest, closure

    def create_candidate(self, *, authorization, principal_teams=(), team_id, policy_revision,
            package_revision, idempotency_key):
        scope = self._scope(authorization, principal_teams, team_id, mutation=True)
        policy_ref, package_ref = _ref(policy_revision), _ref(package_revision)
        policy = self._frozen_policy(authorization, team_id, policy_ref)
        record, _, manifest, _ = self._pack(authorization, team_id, package_ref, policy=policy)
        if record.payload['employee_id'] != authorization.principal:
            raise ValueError('DOMAIN_PACKAGE_CANDIDATE_OWNER_REQUIRED')
        if any(authorization.principal == producer for producer in policy.evaluator_executor_ids):
            raise ValueError('DOMAIN_PACKAGE_INDEPENDENT_PRODUCER_REQUIRED')
        request = {'scope_key': scope, 'team_id': team_id, 'policy_revision': _wire(policy_ref),
            'package_revision': _wire(package_ref)}
        identity_key = self._key('candidate_identity', request)
        existing = self.store.get('agent_task_idempotency', identity_key)
        if existing:
            operation_key, reservation = self._reserve(authorization, 'candidate_created', request, idempotency_key)
            self._published_event(existing['candidate_revision'], 'candidate_created')
            # Identical content under identical criteria is the same candidate;
            # a fresh idempotency key cannot discard failed/unknown evaluations.
            if reservation['state'] != 'published' and not self.store.atomic_compare_and_write((
                    AtomicWrite('agent_task_idempotency', operation_key, reservation,
                        {**reservation, 'state': 'published', 'response': existing['response']}),)):
                raise ValueError('DOMAIN_PACKAGE_PUBLICATION_CONFLICT')
            return self._candidate_response({**existing['response'], 'replayed': True}, policy)
        def writes(revision):
            key = self._key('candidate', revision)
            return (AtomicWrite('agent_task_idempotency', key, None, {'record_type': 'domain_package_candidate',
                **request, 'candidate_revision': revision, 'package_id': manifest.id, 'state': 'candidate',
                'evaluation_revision': None, 'trial_revision': None}), self._policy_fence(scope, policy_ref),
                AtomicWrite('agent_task_idempotency', identity_key, None, {'candidate_revision': revision,
                    'response': {'revision': revision, 'package_id': manifest.id, 'state': 'candidate',
                        'policy_revision': _wire(policy_ref), 'package_revision': _wire(package_ref),
                        'human_approval_required': False}}))
        result = self._event(authorization, 'candidate_created', request, idempotency_key,
            payload={**request, 'package_id': manifest.id, 'manifest_digest': semantic_digest(manifest),
                'qualification_scope': policy.qualification_scope}, writes=writes,
            response={'package_id': manifest.id, 'state': 'candidate', 'policy_revision': _wire(policy_ref),
                'package_revision': _wire(package_ref), 'human_approval_required': False})
        return self._candidate_response(result, policy)

    @staticmethod
    def assessment_input(candidate_revision, policy_revision, phase, *, name='package_assessment'):
        if phase not in ('evaluation', 'trial'):
            raise ValueError('DOMAIN_PACKAGE_ASSESSMENT_PHASE_INVALID')
        material = {'contract_version': 'boi/domain-package-assessment-request@1',
            'candidate_revision': _wire(_ref(candidate_revision)), 'policy_revision': _wire(_ref(policy_revision)), 'phase': phase}
        return {'kind': 'proposal', 'name': name,
            'content_json': json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}

    def _candidate_response(self, result, policy):
        return {**result, 'assessment_inputs': {phase: self.assessment_input(result['revision'], result['policy_revision'],
            phase, name=policy.binding_input_name) for phase in ('evaluation', 'trial')}}

    def _binding_digest(self, candidate, policy, phase):
        return byte_digest(self.assessment_input(candidate['candidate_revision'], candidate['policy_revision'], phase,
            name=policy.binding_input_name)['content_json'].encode())

    def _evaluation_inventory(self, authorization, candidate, policy, phase):
        inventory = self._evaluation_inventory_state(authorization.principal, candidate, policy, phase)
        if inventory['pending']:
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_OUTCOME_UNKNOWN')
        return {_ref(item['execution_ref']) for item in inventory['executions']}

    def _evaluation_inventory_state(self, owner, candidate, policy, phase):
        expected_binding = self._binding_digest(candidate, policy, phase)
        executions, pending, seen, after, count = [], [], set(), '', 0
        while True:
            rows = self.store.list_key_page('domain_tool_invocations', employee_id=owner,
                after_key=after, limit=100)
            for item in rows:
                row = item['value']
                count += 1
                if count > 10000:
                    raise ValueError('DOMAIN_PACKAGE_EVALUATION_INVENTORY_LIMIT')
                if 'invocation' not in row:
                    continue
                invocation = ToolInvocation.model_validate(row['invocation'])
                if (invocation.invocation_id in seen or invocation.tool.revision not in policy.evaluator_tool_revisions
                        or not any(i.name == policy.binding_input_name and i.content_digest == expected_binding for i in invocation.inputs)):
                    continue
                seen.add(invocation.invocation_id)
                publication = self.store.get('domain_tool_receipts', invocation.invocation_id)
                if not publication or not publication.get('revision'):
                    pending.append(invocation.invocation_id)
                else:
                    executions.append({'invocation_id': invocation.invocation_id, 'execution_ref': _wire(_ref(publication['revision'])),
                        'receipt_digest': publication.get('receipt_digest'), 'owner': publication.get('employee_id')})
            if len(rows) < 100:
                return {'executions': sorted(executions, key=lambda item: item['invocation_id']), 'pending': sorted(pending)}
            after = rows[-1]['key']

    def _candidate(self, authorization, principal_teams, revision):
        body = self._published_event(revision, 'candidate_created')
        self._scope(authorization, principal_teams, body['team_id'], mutation=True)
        policy = self._frozen_policy(authorization, body['team_id'], body['policy_revision'])
        self._pack(authorization, body['team_id'], body['package_revision'], policy=policy)
        if self._withdrawn(body['scope_key'], body['package_revision']):
            raise ValueError('DOMAIN_PACKAGE_WITHDRAWN')
        row = self._row('candidate', _wire(_ref(revision)))
        if not row:
            raise ValueError('DOMAIN_PACKAGE_CANDIDATE_NOT_PUBLISHED')
        return body, policy, row

    def _verified_observation(self, authorization, principal_teams, execution_ref, candidate, policy, phase):
        service = DomainWorkService(self.intake, principal_teams=principal_teams,
            trusted_executors=self.trusted_executors, clock=self.clock, packages=self)
        result = service.read_evidence(authorization=authorization,
            request=DomainToolEvidenceRequest(execution_ref=_ref(execution_ref)))
        return self._check_observation(result, authorization.principal, execution_ref, candidate, policy, phase)

    def _check_observation(self, result, expected_owner, execution_ref, candidate, policy, phase):
        signed = SignedToolExecution.model_validate(result['execution']['signed_execution'])
        invocation = signed.body.invocation
        row = self.store.get('domain_tool_invocations', invocation.invocation_id)
        if not row or row.get('employee_id') != expected_owner:
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_NOT_PROTECTED')
        expected = ToolInvocation.model_validate(row['invocation'])
        raw = result['output_json'].encode()
        verified = verify_tool_execution(receipt=signed, expected=expected, output_bytes=raw,
            trusted_executors=self.trusted_executors, at=self.clock())
        if (verified.outcome != 'completed' or signed.body.executor_id not in policy.evaluator_executor_ids
                or signed.body.executor_id == candidate['employee_id']
                or invocation.tool.revision not in policy.evaluator_tool_revisions):
            raise ValueError('DOMAIN_PACKAGE_INDEPENDENT_EVALUATION_REQUIRED')
        report = DomainToolReport.model_validate_json(raw)
        observation = DomainPackageObservation.model_validate(report.result)
        if (observation.candidate_revision != _ref(candidate['candidate_revision'])
                or observation.policy_revision != _ref(candidate['policy_revision']) or observation.phase != phase):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_BINDING_MISMATCH')
        if not any(i.name == policy.binding_input_name and i.content_digest == self._binding_digest(candidate, policy, phase)
                for i in invocation.inputs):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_REQUEST_INPUT_REQUIRED')
        cases = {c.case_id: c for c in policy.cases if c.phase == phase}
        case = cases.get(observation.case_id)
        if case is None or not any(i.name == case.input_name and i.content_digest == case.input_digest for i in invocation.inputs):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_INPUT_MISMATCH')
        # Candidate content must actually have been delivered in the protected
        # invocation. A signed producer label or a caller's passed=True is not enough.
        candidate_ref = _ref(candidate['package_revision'])
        candidate_record = self._record(candidate_ref)
        if not any(i.revision == candidate_ref and i.content_digest == candidate_record.payload['content_object_ref']
                for i in invocation.inputs):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_CANDIDATE_INPUT_REQUIRED')
        result_matches = semantic_digest(observation.result) == case.expected_result_digest
        check_states = {check.status for check in report.checks}
        outcome = ('unknown' if 'unknown' in check_states else
            'pass' if result_matches and check_states == {'pass'} else 'fail')
        return {'execution_ref': _wire(_ref(execution_ref)), 'execution_digest': byte_digest(raw),
            'invocation_id': invocation.invocation_id, 'run_id': invocation.run_id,
            'producer_id': signed.body.executor_id, 'case_id': case.case_id,
            'started_at': signed.body.started_at.isoformat(), 'finished_at': signed.body.finished_at.isoformat(),
            'input_digest': case.input_digest, 'actual_result_digest': semantic_digest(observation.result),
            'expected_result_digest': case.expected_result_digest,
            'outcome': outcome}

    def _monitor_observation(self, execution_ref, candidate, policy, phase):
        """Server-only package verification, never a general private-result reader.

        References come exclusively from the protected invocation inventory for
        this adopted candidate's frozen assessment binding. The caller has already
        proved current team package access. Only check metadata/digests leave this
        method; source and result read APIs retain their original owner checks.
        """
        record = self._record(execution_ref)
        body = record.payload
        if (record.kind != RecordKind.RUN or body.get('contract_version') != 'boi/domain-tool-evidence@1'
                or body.get('employee_id') != candidate['employee_id'] or body.get('policy_digest') != candidate['policy_digest']):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_NOT_PROTECTED')
        signed = SignedToolExecution.model_validate(body['signed_execution'])
        invocation = signed.body.invocation
        row = self.store.get('domain_tool_invocations', invocation.invocation_id)
        publication = self.store.get('domain_tool_receipts', invocation.invocation_id)
        task = self.store.get('agent_task_packages', invocation.task_revision.ref)
        if (not row or row.get('employee_id') != candidate['employee_id']
                or row.get('invocation') != _wire(invocation)
                or invocation.principal_id != candidate['employee_id'] or invocation.policy_digest != candidate['policy_digest']
                or not publication or publication.get('employee_id') != candidate['employee_id']
                or publication.get('revision') != _wire(_ref(execution_ref))
                or not task or task.get('employee_id') != candidate['employee_id']
                or task.get('task_contract_checksum') != invocation.task_revision.revision_digest
                or semantic_digest(task.get('domain_execution_contract')) != invocation.task_revision.revision_digest
                or task['domain_execution_contract'].get('reading_ref') != _wire(invocation.reading_ref)
                or task['domain_execution_contract'].get('context_ref') != _wire(invocation.context_ref)
                or task['domain_execution_contract'].get('context_digest') != invocation.context_digest
                or task['domain_execution_contract'].get('source_manifest_digest') != invocation.source_manifest_digest
                or not any(i.name == policy.binding_input_name and i.content_digest == self._binding_digest(candidate, policy, phase)
                    for i in invocation.inputs)):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_NOT_PROTECTED')
        raw = self.objects.get(body['output_object_ref'])
        if byte_digest(raw) != signed.body.output_content_digest:
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_CONTENT_DRIFT')
        return self._check_observation({'execution': body, 'output_json': raw.decode('utf-8')},
            candidate['employee_id'], execution_ref, candidate, policy, phase)

    def _monitor_state(self, candidate, policy):
        now = self.clock()
        trust = sorted(({**_wire(item), 'active_now': not item.revoked and item.valid_from <= now < item.valid_until}
            for item in self.trusted_executors if item.executor_id in policy.evaluator_executor_ids),
            key=lambda item: (item['executor_id'], item['key_id']))
        inventories = {phase: self._evaluation_inventory_state(candidate['employee_id'], candidate, policy, phase)
            for phase in ('evaluation', 'trial')}
        for inventory in inventories.values():
            if len(inventory['executions']) + len(inventory['pending']) > 1000:
                raise ValueError('DOMAIN_PACKAGE_MONITOR_INVENTORY_LIMIT')
            for item in inventory['executions']:
                record = self._record(item['execution_ref'])
                if (record.kind != RecordKind.RUN or record.payload.get('contract_version') != 'boi/domain-tool-evidence@1'
                        or record.payload.get('employee_id') != candidate['employee_id']):
                    raise ValueError('DOMAIN_PACKAGE_EVALUATION_NOT_PROTECTED')
                object_ref = record.payload['output_object_ref']
                def verify(raw):
                    if byte_digest(raw) != object_ref:
                        raise ValueError('DOMAIN_PACKAGE_EVALUATION_CONTENT_DRIFT')
                    return len(raw)
                project = getattr(self.objects, 'project_verified', None)
                if project:
                    project(object_ref, version='domain-package-monitor-bytes@1', derive=verify)
                else:
                    verify(self.objects.get(object_ref))
        return {'policy_revision': candidate['policy_revision'], 'policy_digest': semantic_digest(policy),
            'trust_digest': semantic_digest(trust), 'inventories': inventories}

    def _assess(self, phase, *, authorization, principal_teams=(), candidate_revision, execution_refs, idempotency_key):
        candidate_ref = _ref(candidate_revision)
        body, policy, state = self._candidate(authorization, principal_teams, candidate_ref)
        body = {**body, 'candidate_revision': _wire(candidate_ref)}
        refs = tuple(_ref(ref) for ref in execution_refs)
        request = {'candidate_revision': _wire(candidate_ref), 'execution_refs': [_wire(ref) for ref in refs]}
        _, replay = self._reserve(authorization, phase, request, idempotency_key)
        if replay['state'] == 'published':
            return {**replay['response'], 'replayed': True}
        if not refs or len(refs) > policy.max_trial_runs or len(set(refs)) != len(refs):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_RUN_COUNT_INVALID')
        if phase == 'trial' and (not state.get('evaluation_revision') or state['state'] not in ('evaluated', 'trial_failed', 'trial_passed')):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_REQUIRED_BEFORE_TRIAL')
        if phase == 'evaluation' and state['state'] not in ('candidate', 'evaluation_failed', 'evaluated'):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_STATE_INVALID')
        if set(refs) != self._evaluation_inventory(authorization, body, policy, phase):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_INVENTORY_INCOMPLETE')
        observations = [self._verified_observation(authorization, principal_teams, ref, body, policy, phase) for ref in refs]
        if len({o['run_id'] for o in observations}) != len(observations):
            raise ValueError('DOMAIN_PACKAGE_DISTINCT_RUNS_REQUIRED')
        if phase == 'trial':
            evaluated_at = datetime.fromisoformat(self._record(state['evaluation_revision'], event='evaluation').occurred_at)
            if any(datetime.fromisoformat(item['started_at']) < evaluated_at for item in observations):
                raise ValueError('DOMAIN_PACKAGE_TRIAL_STARTED_BEFORE_EVALUATION')
        required = {c.case_id for c in policy.cases if c.phase == phase}
        passed = (required == {o['case_id'] for o in observations} and all(o['outcome'] == 'pass' for o in observations)
            and (phase != 'trial' or len(observations) >= policy.min_trial_runs))
        status = ('evaluated' if phase == 'evaluation' else 'trial_passed') if passed else phase + '_failed'
        def writes(revision):
            updated = {**state, 'state': status, phase + '_revision': revision}
            return (AtomicWrite('agent_task_idempotency', self._key('candidate', _wire(candidate_ref)), state, updated),
                self._policy_fence(body['scope_key'], body['policy_revision']))
        return self._event(authorization, phase, request, idempotency_key,
            payload={**request, 'scope_key': body['scope_key'], 'package_revision': body['package_revision'],
                'policy_revision': body['policy_revision'], 'observations': observations, 'outcome': 'pass' if passed else 'fail',
                'qualification_scope': policy.qualification_scope, 'semantic_quality': 'not_evaluated',
                'exception_group': None if passed else self._key('exception', body['scope_key'], body['package_id'], phase),
                'impact': {'package_id': body['package_id'], 'package_revision': body['package_revision']}},
            writes=writes, response={'state': status, 'outcome': 'pass' if passed else 'fail',
                'qualification_scope': policy.qualification_scope, 'semantic_quality': 'not_evaluated'})

    def evaluate(self, **kwargs):
        return self._assess('evaluation', **kwargs)

    def trial(self, **kwargs):
        return self._assess('trial', **kwargs)

    def adopt(self, *, authorization, principal_teams=(), candidate_revision, idempotency_key):
        candidate_ref = _ref(candidate_revision)
        body, policy, state = self._candidate(authorization, principal_teams, candidate_ref)
        request = {'candidate_revision': _wire(candidate_ref)}
        # Replay before checking a state advanced by this exact published operation.
        _, replay = self._reserve(authorization, 'adopted', request, idempotency_key)
        if replay['state'] == 'published':
            return {**replay['response'], 'replayed': True}
        if state['state'] != 'trial_passed':
            raise ValueError('DOMAIN_PACKAGE_TRIAL_REQUIRED_BEFORE_ADOPTION')
        phases = []
        for phase in ('evaluation', 'trial'):
            outcome = self._published_event(state[phase + '_revision'], phase)
            if outcome.get('outcome') != 'pass' or outcome['candidate_revision'] != _wire(candidate_ref):
                raise ValueError('DOMAIN_PACKAGE_QUALIFICATION_INVALID')
            # Fresh protected reads and current trust prevent revoked evidence
            # from becoming authority through an old persisted passed result.
            observations = [self._verified_observation(authorization, principal_teams, ref,
                {**body, 'candidate_revision': _wire(candidate_ref)}, policy, phase) for ref in outcome['execution_refs']]
            if {_ref(ref) for ref in outcome['execution_refs']} != self._evaluation_inventory(authorization,
                    {**body, 'candidate_revision': _wire(candidate_ref)}, policy, phase):
                raise ValueError('DOMAIN_PACKAGE_EVALUATION_INVENTORY_CHANGED')
            if observations != outcome['observations']:
                raise ValueError('DOMAIN_PACKAGE_QUALIFICATION_CHANGED')
            phases.append(outcome)
        if {o['run_id'] for o in phases[0]['observations']} & {o['run_id'] for o in phases[1]['observations']}:
            raise ValueError('DOMAIN_PACKAGE_TRIAL_RUN_REUSE_DENIED')
        key = self._key('binding', body['scope_key'], body['package_id'])
        previous = self.store.get('agent_task_idempotency', key)
        monitor_state = self._monitor_state({**body, 'candidate_revision': _wire(candidate_ref)}, policy)
        for phase, result in zip(('evaluation', 'trial'), phases):
            inventory = monitor_state['inventories'][phase]
            if inventory['pending'] or {_ref(item['execution_ref']) for item in inventory['executions']} != {
                    _ref(ref) for ref in result['execution_refs']}:
                raise ValueError('DOMAIN_PACKAGE_EVALUATION_INVENTORY_CHANGED')
        payload = {**request, 'scope_key': body['scope_key'], 'team_id': body['team_id'], 'package_id': body['package_id'],
            'package_revision': body['package_revision'], 'policy_revision': body['policy_revision'],
            'evaluation_revision': state['evaluation_revision'], 'trial_revision': state['trial_revision'],
            'previous_adoption': previous.get('adoption_revision') if previous else None,
            'qualification_scope': policy.qualification_scope, 'semantic_quality': 'not_evaluated',
            'monitor_state_digest': semantic_digest(monitor_state),
            'platform_release_changed': False, 'human_approval_required': False}
        withdrawal_key = self._key('withdrawal', body['scope_key'], body['package_revision'])
        def writes(revision):
            return (
                AtomicWrite('agent_task_idempotency', key, previous, {'record_type': 'domain_package_binding',
                    'scope_key': body['scope_key'], 'package_id': body['package_id'], 'adoption_revision': revision}),
                AtomicWrite('agent_task_idempotency', self._key('adoption', body['scope_key'], body['package_revision']),
                    self._row('adoption', body['scope_key'], body['package_revision']), {'adoption_revision': revision}),
                AtomicWrite('agent_task_idempotency', self._key('candidate', _wire(candidate_ref)), state, {**state, 'state': 'adopted'}),
                AtomicWrite('agent_task_idempotency', withdrawal_key, None, {'withdrawn': False}),
                self._policy_fence(body['scope_key'], body['policy_revision']),
                AtomicWrite('agent_task_idempotency', self._key('monitor', body['scope_key'], _wire(candidate_ref)), None,
                    {'proof_revision': revision, 'proof_kind': 'adopted', 'state': monitor_state,
                        'state_digest': semantic_digest(monitor_state), 'outcome': 'pass',
                        'reason_code': 'DOMAIN_PACKAGE_REFERENCE_CHECKS_UNCHANGED',
                        'observations': {phase: result['observations'] for phase, result in zip(('evaluation', 'trial'), phases)}}),
            )
        return self._event(authorization, 'adopted', request, idempotency_key, payload=payload, writes=writes,
            response={'state': 'adopted', 'package_id': body['package_id'], 'package_revision': body['package_revision'],
                'qualification_scope': policy.qualification_scope, 'semantic_quality': 'not_evaluated'})

    def _withdrawn(self, scope, revision):
        row = self._row('withdrawal', scope, _wire(_ref(revision)))
        return bool(row and row.get('withdrawn'))

    def _affected_work_refs(self, authorization, scope, revision):
        refs, after = [], ''
        while True:
            rows = self.store.list_key_page('agent_task_packages', employee_id=authorization.principal,
                after_key=after, limit=100)
            for item in rows:
                body = item['value']
                selection = body.get('package_selection') or {}
                if selection.get('scope_key') == scope and any(p.get('revision') == revision for p in selection.get('packages', ())):
                    refs.append(item['key'])
            if len(rows) < 100:
                return refs
            after = rows[-1]['key']

    def observe(self, *, authorization, principal_teams=(), candidate_revision, execution_refs=(), idempotency_key):
        """An external monitor submits real evidence; server policy acts on it.

        No model or periodic scheduler runs here. Failed reference results and
        revoked server bindings automatically withdraw the exact adopted version.
        Pending executions remain unknown and are never dispatched again.
        """
        candidate_ref = _ref(candidate_revision)
        body = self._published_event(candidate_ref, 'candidate_created')
        self._scope(authorization, principal_teams, body['team_id'], mutation=True)
        if not self._row('adoption', body['scope_key'], body['package_revision']):
            raise ValueError('DOMAIN_PACKAGE_ADOPTION_REQUIRED_FOR_OBSERVATION')
        refs = tuple(_ref(ref) for ref in execution_refs)
        if len(refs) > 100 or len(set(refs)) != len(refs):
            raise ValueError('DOMAIN_PACKAGE_EVALUATION_RUN_COUNT_INVALID')
        request = {'candidate_revision': _wire(candidate_ref), 'execution_refs': [_wire(ref) for ref in refs]}
        _, reservation = self._reserve(authorization, 'observed', request, idempotency_key)
        if reservation['state'] == 'published':
            result = {**reservation['response'], 'replayed': True}
        else:
            observations, outcome, reason = [], 'unknown', 'DOMAIN_PACKAGE_REFERENCE_RESULT_UNKNOWN'
            try:
                policy = self._frozen_policy(authorization, body['team_id'], body['policy_revision'])
                self._pack(authorization, body['team_id'], body['package_revision'], policy=policy)
            except ValueError as exc:
                if str(exc) not in ('DOMAIN_PACKAGE_POLICY_STALE', 'DOMAIN_PACKAGE_HOTL_POLICY_UNAVAILABLE',
                        'DOMAIN_PACKAGE_TRUSTED_EVALUATOR_UNAVAILABLE', 'DOMAIN_PACKAGE_CAPABILITY_EXPANSION_DENIED',
                        'DOMAIN_PACKAGE_EXECUTABLE_CAPABILITY_DENIED', 'DOMAIN_PACKAGE_SOURCE_NOT_TEAM_SHAREABLE'):
                    raise
                outcome, reason = 'fail', str(exc)
            else:
                candidate = {**body, 'candidate_revision': _wire(candidate_ref)}
                try:
                    inventory = self._evaluation_inventory(authorization, candidate, policy, 'evaluation')
                except ValueError as exc:
                    if str(exc) != 'DOMAIN_PACKAGE_EVALUATION_OUTCOME_UNKNOWN':
                        raise
                    reason = str(exc)
                else:
                    if set(refs) != inventory:
                        raise ValueError('DOMAIN_PACKAGE_EVALUATION_INVENTORY_INCOMPLETE')
                    observations = [self._verified_observation(authorization, principal_teams, ref, candidate, policy, 'evaluation') for ref in refs]
                    required = {case.case_id for case in policy.cases if case.phase == 'evaluation'}
                    if any(item['outcome'] == 'fail' for item in observations):
                        outcome, reason = 'fail', 'DOMAIN_PACKAGE_REFERENCE_REGRESSION'
                    elif observations and required == {item['case_id'] for item in observations} and all(item['outcome'] == 'pass' for item in observations):
                        outcome, reason = 'pass', 'DOMAIN_PACKAGE_REFERENCE_CHECKS_UNCHANGED'
            impact = {'package_revision': body['package_revision'],
                'affected_work_refs': self._affected_work_refs(authorization, body['scope_key'], body['package_revision']),
                'work_ref_scope': 'caller_visible_only', 'historical_results': 'requires_revalidation' if outcome == 'fail' else 'preserved'}
            result = self._event(authorization, 'observed', request, idempotency_key,
                payload={**request, 'scope_key': body['scope_key'], 'package_id': body['package_id'],
                    'package_revision': body['package_revision'], 'policy_revision': body['policy_revision'],
                    'observations': observations, 'outcome': outcome, 'reason_code': reason,
                    'qualification_scope': 'reference_checks', 'semantic_quality': 'not_evaluated', 'impact': impact,
                    'exception_group': None if outcome == 'pass' else self._key('exception', body['scope_key'], body['package_id'], 'observation')},
                response={'outcome': outcome, 'reason_code': reason, 'impact': impact, 'semantic_quality': 'not_evaluated'})
        if result['outcome'] == 'fail':
            # An acknowledgement lost between the two publications resumes only
            # this exact withdrawal. It never repeats an external evaluation.
            withdrawal = self.withdraw(authorization=authorization, principal_teams=principal_teams,
                team_id=body['team_id'], package_revision=body['package_revision'], reason=result['reason_code'],
                idempotency_key='observe:' + semantic_digest([authorization.principal, idempotency_key]))
            return {**result, 'automatic_action': 'withdrawn', 'withdrawal': withdrawal}
        return {**result, 'automatic_action': 'none', 'external_retry_authorized': False}

    def withdraw(self, *, authorization, principal_teams=(), team_id, package_revision, reason, idempotency_key):
        scope = self._scope(authorization, principal_teams, team_id, mutation=True)
        revision = _wire(_ref(package_revision))
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError('DOMAIN_PACKAGE_WITHDRAWAL_REASON_REQUIRED')
        adopted = self._row('adoption', scope, revision)
        if not adopted:
            raise ValueError('DOMAIN_PACKAGE_ADOPTION_NOT_FOUND')
        original = self._published_event(adopted['adoption_revision'], 'adopted')
        binding_key = self._key('binding', scope, original['package_id'])
        binding = self.store.get('agent_task_idempotency', binding_key)
        old_fence = self._row('withdrawal', scope, revision)
        request = {'scope_key': scope, 'package_revision': revision, 'reason': reason}
        _, replay = self._reserve(authorization, 'withdrawn', request, idempotency_key)
        if replay['state'] == 'published':
            return {**replay['response'], 'replayed': True}
        current = binding.get('adoption_revision') if binding else None
        rollback = current
        rollback_exclusions = []
        if current and self._published_event(current, 'adopted')['package_revision'] == revision:
            rollback = original['previous_adoption']
            while rollback:
                previous = self._published_event(rollback, 'adopted')
                if not self._withdrawn(scope, previous['package_revision']):
                    try:
                        previous_policy = self._frozen_policy(authorization, team_id, previous['policy_revision'])
                        self._pack(authorization, team_id, previous['package_revision'], policy=previous_policy)
                    except ValueError as exc:
                        rollback_exclusions.append({'adoption_revision': rollback, 'reason_code': str(exc)})
                    else:
                        break
                else:
                    rollback_exclusions.append({'adoption_revision': rollback, 'reason_code': 'DOMAIN_PACKAGE_WITHDRAWN'})
                rollback = previous['previous_adoption']
        def writes(event_ref):
            result = [AtomicWrite('agent_task_idempotency', self._key('withdrawal', scope, revision), old_fence,
                {'withdrawn': True, 'withdrawal_revision': event_ref})]
            if binding is not None:
                result.append(AtomicWrite('agent_task_idempotency', binding_key, binding, {**binding, 'adoption_revision': rollback}))
            return tuple(result)
        return self._event(authorization, 'withdrawn', request, idempotency_key,
            payload={**request, 'package_id': original['package_id'], 'withdrawn_adoption': adopted['adoption_revision'],
                'rollback_adoption': rollback, 'rollback_exclusions': rollback_exclusions,
                'exception_group': self._key('exception', scope, original['package_id'], 'withdrawal'),
                'impact': {'pinned_revision': revision, 'inflight_next_step': 'blocked',
                    'affected_work_refs': self._affected_work_refs(authorization, scope, revision),
                    'work_ref_scope': 'caller_visible_only',
                    'prior_results': 'historical_requires_revalidation', 'new_work': 'uses_exact_previous_valid_adoption'},
                'platform_release_changed': False}, writes=writes,
            response={'state': 'withdrawn', 'rollback_adoption': rollback, 'inflight_next_step': 'blocked'})

    def read(self, *, authorization, principal_teams=(), package_id, revision=None, team_id=None, resource_path=None,
            _historical=False, _shipped_entry=None):
        if resource_path is not None:
            package = self.read(authorization=authorization, principal_teams=principal_teams,
                package_id=package_id, revision=revision, team_id=team_id)
            resources = package['manifest'].get('resource_digests', {})
            if not isinstance(resource_path, str) or resource_path not in resources:
                raise ValueError('DOMAIN_PACKAGE_RESOURCE_NOT_BOUND')
            digest = resources[resource_path]
            if package['revision'] is None:
                raw = (self.repo_root / resource_path).read_bytes()
            else:
                raw = self.objects.get(digest)
            if byte_digest(raw) != digest:
                raise ValueError('DOMAIN_PACKAGE_RESOURCE_CONTENT_DRIFT')
            return {'package_id': package_id, 'revision': package['revision'], 'resource_path': resource_path,
                'content_digest': digest, 'content_b64': base64.b64encode(raw).decode(),
                'execution_authorized': False, 'role': 'external_agent_guidance'}
        scope = self._scope(authorization, principal_teams, team_id)
        adoption = None
        if revision is not None:
            ref = _ref(revision)
            record = self._record(ref)
            if record.payload.get('contract_version') == self.BUILTIN:
                body = record.payload
                if body['manifest']['id'] != package_id or semantic_digest(body['manifest']) != body['manifest_digest']:
                    raise ValueError('DOMAIN_PACKAGE_REVISION_MISMATCH')
                if byte_digest(self.objects.get(body['content_object_ref'])) != body['content_object_ref']:
                    raise ValueError('DOMAIN_PACKAGE_CONTENT_DRIFT')
                return {'package_id': package_id, 'revision': _wire(ref), 'manifest': body['manifest'],
                    'manifest_digest': body['manifest_digest'], 'origin': 'shipped'}
            row = self._row('adoption', scope, _wire(ref))
            adoption = row.get('adoption_revision') if row else None
            if not adoption:
                raise ValueError('DOMAIN_PACKAGE_REVISION_NOT_ADOPTED')
        else:
            row = self._row('binding', scope, package_id)
            adoption = row.get('adoption_revision') if row else None
            if not adoption:
                return self._builtin(package_id, publish=False,
                    entry=_shipped_entry(package_id) if _shipped_entry is not None else None)
        body = self._published_event(adoption, 'adopted')
        if (body['scope_key'] != scope or body['package_id'] != package_id
                or (self._withdrawn(scope, body['package_revision']) and not (_historical and revision is not None))):
            raise ValueError('DOMAIN_PACKAGE_WITHDRAWN_OR_SCOPE_DENIED')
        _, _, manifest, closure = self._pack(authorization, team_id, body['package_revision'])
        return {'package_id': package_id, 'revision': body['package_revision'], 'manifest': _wire(manifest),
            'manifest_digest': semantic_digest(manifest), 'origin': 'team_adoption', 'adoption_revision': adoption,
            'member_revisions': [_wire(ref) for ref in sorted(closure, key=lambda ref: ref.ref)],
            'execution_mode': 'external_agent_skill_and_bound_members',
            'qualification_scope': body['qualification_scope'], 'semantic_quality': 'not_evaluated'}

    def _checked_monitor(self, scope, candidate_ref):
        row = self._row('monitor', scope, _wire(_ref(candidate_ref)))
        if not row:
            return None
        proof = self._published_event(row['proof_revision'], row['proof_kind'])
        if row['state_digest'] != semantic_digest(row['state']):
            raise ValueError('DOMAIN_PACKAGE_MONITOR_PROJECTION_CHANGED')
        if row['proof_kind'] == 'adopted':
            expected = {phase: self._published_event(proof[phase + '_revision'], phase)['observations']
                for phase in ('evaluation', 'trial')}
            valid = (proof.get('monitor_state_digest') == row['state_digest'] and row['outcome'] == 'pass'
                and row['reason_code'] == 'DOMAIN_PACKAGE_REFERENCE_CHECKS_UNCHANGED' and expected == row['observations'])
        elif row['proof_kind'] == 'automatically_observed':
            valid = all(proof.get(key) == row.get(key) for key in ('state_digest', 'observations', 'outcome', 'reason_code'))
        else:
            valid = False
        if not valid or proof.get('candidate_revision') != _wire(_ref(candidate_ref)) or proof.get('scope_key') != scope:
            raise ValueError('DOMAIN_PACKAGE_MONITOR_PROJECTION_CHANGED')
        return row

    def _admission_monitor(self, authorization, principal_teams, adoption_revision):
        adoption = self._published_event(adoption_revision, 'adopted')
        self._scope(authorization, principal_teams, adoption['team_id'], mutation=True)
        candidate = {**self._published_event(adoption['candidate_revision'], 'candidate_created'),
            'candidate_revision': adoption['candidate_revision']}
        # A caller's narrower/different access policy cannot revoke a package
        # for its whole team. Only server policy/trust changes trigger withdrawal.
        if candidate['policy_digest'] != authorization.policy_digest:
            raise ValueError('DOMAIN_PACKAGE_SHARED_ASSET_DENIED')
        previous = self._checked_monitor(adoption['scope_key'], adoption['candidate_revision'])
        try:
            policy = self._frozen_policy(authorization, adoption['team_id'], adoption['policy_revision'])
            self._pack(authorization, adoption['team_id'], adoption['package_revision'], policy=policy)
        except ValueError as exc:
            if str(exc) not in ('DOMAIN_PACKAGE_POLICY_STALE', 'DOMAIN_PACKAGE_HOTL_POLICY_UNAVAILABLE',
                    'DOMAIN_PACKAGE_TRUSTED_EVALUATOR_UNAVAILABLE', 'DOMAIN_PACKAGE_CAPABILITY_EXPANSION_DENIED',
                    'DOMAIN_PACKAGE_EXECUTABLE_CAPABILITY_DENIED', 'DOMAIN_PACKAGE_SOURCE_NOT_TEAM_SHAREABLE'):
                raise
            reason, outcome = str(exc), 'fail'
            state = {'binding_failure': reason, 'configured_policy': _wire(self.policies.get(adoption['team_id'])),
                'trust_digest': semantic_digest([_wire(item) for item in self.trusted_executors])}
            observations = previous['observations'] if previous else {'evaluation': [], 'trial': []}
        else:
            state = self._monitor_state(candidate, policy)
            reason, outcome = 'DOMAIN_PACKAGE_REFERENCE_CHECKS_UNCHANGED', 'pass'
            observations = previous['observations'] if previous else {'evaluation': [], 'trial': []}
            if previous is None or previous['state_digest'] != semantic_digest(state):
                trust_changed = previous is None or previous['state'].get('trust_digest') != state['trust_digest']
                budget, updated = 100, {}
                for phase in ('evaluation', 'trial'):
                    known = {_ref(item['execution_ref']): item for item in observations[phase]}
                    inventory = state['inventories'][phase]
                    current_refs = {_ref(item['execution_ref']) for item in inventory['executions']}
                    if len(current_refs) > 1000:
                        raise ValueError('DOMAIN_PACKAGE_MONITOR_INVENTORY_LIMIT')
                    if not set(known) <= current_refs:
                        raise ValueError('DOMAIN_PACKAGE_MONITOR_EVIDENCE_DISAPPEARED')
                    updated[phase] = []
                    for ref in sorted(current_refs, key=lambda item: item.ref):
                        if ref in known and not trust_changed:
                            observation = known[ref]
                        else:
                            budget -= 1
                            if budget < 0:
                                raise ValueError('DOMAIN_PACKAGE_MONITOR_VERIFICATION_LIMIT')
                            try:
                                observation = self._monitor_observation(ref, candidate, policy, phase)
                            except ValueError as exc:
                                if str(exc) not in ('TOOL_EXECUTOR_UNKNOWN_OR_AMBIGUOUS', 'TOOL_EXECUTOR_TRUST_NOT_CURRENT',
                                        'TOOL_EXECUTOR_RELEASE_NOT_AUTHORIZED'):
                                    raise
                                outcome, reason = 'fail', str(exc)
                                break
                        updated[phase].append(observation)
                    if outcome == 'fail':
                        break
                if outcome != 'fail':
                    observations = updated
                    flat = [item for values in observations.values() for item in values]
                    if any(item['outcome'] == 'fail' for item in flat):
                        outcome, reason = 'fail', 'DOMAIN_PACKAGE_REFERENCE_REGRESSION'
                    elif any(item['outcome'] == 'unknown' for item in flat) or any(
                            inventory['pending'] for inventory in state['inventories'].values()):
                        outcome, reason = 'unknown', 'DOMAIN_PACKAGE_EVALUATION_OUTCOME_UNKNOWN'
        digest = semantic_digest(state)
        if previous is not None and previous['state_digest'] == digest:
            proof_revision, outcome, reason = previous['proof_revision'], previous['outcome'], previous['reason_code']
        else:
            request = {'candidate_revision': adoption['candidate_revision'], 'state_digest': digest}
            def writes(revision):
                return (AtomicWrite('agent_task_idempotency', self._key('monitor', adoption['scope_key'], adoption['candidate_revision']),
                    previous, {'proof_revision': revision, 'proof_kind': 'automatically_observed', 'state': state,
                        'state_digest': digest, 'observations': observations, 'outcome': outcome, 'reason_code': reason}),)
            result = self._event(authorization, 'automatically_observed', request,
                'admission:' + semantic_digest([adoption['candidate_revision'], digest]),
                payload={**request, 'scope_key': adoption['scope_key'], 'package_id': adoption['package_id'],
                    'package_revision': adoption['package_revision'], 'policy_revision': adoption['policy_revision'],
                    'observations': observations, 'outcome': outcome, 'reason_code': reason,
                    'qualification_scope': 'reference_checks', 'semantic_quality': 'not_evaluated',
                    'exception_group': None if outcome == 'pass' else self._key('exception', adoption['scope_key'], adoption['package_id'], 'observation')},
                writes=writes, response={'outcome': outcome, 'reason_code': reason})
            proof_revision = result['revision']
        if outcome == 'fail':
            self.withdraw(authorization=authorization, principal_teams=principal_teams, team_id=adoption['team_id'],
                package_revision=adoption['package_revision'], reason=reason,
                idempotency_key='admission-withdraw:' + semantic_digest(proof_revision))
        return {'package_id': adoption['package_id'], 'package_revision': adoption['package_revision'],
            'outcome': outcome, 'reason_code': reason, 'observation_revision': proof_revision,
            'external_retry_authorized': False}

    def _monitor_before_selection(self, authorization, principal_teams, scope, package_id, explicit_revision):
        notes = []
        for _ in range(20):
            if explicit_revision is not None:
                row = self._row('adoption', scope, _wire(_ref(explicit_revision)))
            else:
                row = self._row('binding', scope, package_id)
            if not row or not row.get('adoption_revision'):
                return notes
            adoption = self._published_event(row['adoption_revision'], 'adopted')
            if adoption['scope_key'] != scope or adoption['package_id'] != package_id:
                raise ValueError('DOMAIN_PACKAGE_WITHDRAWN_OR_SCOPE_DENIED')
            if self._withdrawn(scope, adoption['package_revision']):
                raise ValueError('DOMAIN_PACKAGE_WITHDRAWN')
            observed = self._admission_monitor(authorization, principal_teams, row['adoption_revision'])
            if observed['outcome'] != 'pass':
                notes.append(observed)
            if observed['outcome'] != 'fail' or explicit_revision is not None:
                return notes
            # Follow only the exact previous adoption chosen by the existing
            # atomic rollback path, and check it before selecting new work.
        raise ValueError('DOMAIN_PACKAGE_ROLLBACK_CHAIN_LIMIT')

    @staticmethod
    def _validate_dependencies(packages, *, historical=False):
        index = {item['package_id']: item for item in packages}
        if not packages or len(index) != len(packages) or len(packages) > 20:
            raise ValueError('DOMAIN_PACKAGE_SELECTION_INVALID')
        # Pre-contract task snapshots did not include the declared closure.
        # Keep their immutable historical contract; all new selections resolve it.
        entries = []
        for item in packages:
            entry = item['manifest']
            if historical and entry.get('resource_contract') != RESOURCE_CONTRACT:
                entry = {**entry, 'dependencies': [], 'dependency_versions': {}}
            entries.append(entry)
        dependency_order(entries)
        for item in packages:
            manifest = item['manifest']
            if manifest.get('resource_contract') != RESOURCE_CONTRACT:
                continue
            expected = manifest.get('dependency_manifest_digests', {})
            if set(expected) != set(manifest.get('dependencies', ())):
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_BINDING_INVALID')
            for identity, digest in expected.items():
                if identity not in index or index[identity]['manifest_digest'] != digest:
                    raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_BINDING_MISMATCH')

    def resolve_for_work(self, *, authorization, principal_teams=(), package_ids=(), package_revisions=(), team_id=None):
        scope = self._scope(authorization, principal_teams, team_id)
        ids = tuple(package_ids) or ('common',)
        if len(ids) > 20 or len(set(ids)) != len(ids):
            raise ValueError('DOMAIN_PACKAGE_SELECTION_INVALID')
        revisions = dict(package_revisions) if isinstance(package_revisions, dict) else {
            item['package_id']: item['revision'] for item in package_revisions}
        notes, selected, active = [], {}, set()
        catalog, built = None, {}

        def shipped(identity):
            nonlocal catalog
            if catalog is None:
                catalog = json.loads(self.catalog_path.read_text(encoding='utf-8'))
            if identity not in built:
                self._builtin_entries([identity], catalog=catalog, cache=built)
            return built[identity]

        def visit(identity, expected_digest=None):
            if identity in active:
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_CYCLE')
            if identity in selected:
                if expected_digest is not None and selected[identity]['manifest_digest'] != expected_digest:
                    raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_BINDING_MISMATCH')
                return
            if len(selected) >= 20:
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_LIMIT')
            revision = revisions.get(identity)
            if revision is None and expected_digest is not None:
                saved = self._row('builtin', expected_digest)
                revision = saved.get('revision') if saved else None
            if team_id is not None:
                notes.extend(self._monitor_before_selection(authorization, principal_teams, scope, identity, revision))
            item = self.read(authorization=authorization, principal_teams=principal_teams, package_id=identity,
                revision=revision, team_id=team_id, _shipped_entry=shipped)
            if expected_digest is not None and item['manifest_digest'] != expected_digest:
                raise ValueError('DOMAIN_PACKAGE_DEPENDENCY_BINDING_MISMATCH')
            selected[identity] = item
            active.add(identity)
            manifest = item['manifest']
            for dependency in manifest.get('dependencies', ()):
                visit(dependency, manifest.get('dependency_manifest_digests', {}).get(dependency))
            active.remove(identity)

        for identity in ids:
            visit(identity)
        if not set(revisions) <= set(selected):
            raise ValueError('DOMAIN_PACKAGE_SELECTION_REVISION_INVALID')
        self._validate_dependencies(list(selected.values()))
        # Validate the complete closure before publishing. Publish captured
        # manifests, never a later reread of the mutable catalog. Dependencies
        # precede consumers so a returned historical root has recoverable pins.
        for entry in dependency_order([item['manifest'] for item in selected.values()]):
            item = selected[entry['id']]
            if item['revision'] is None:
                selected[entry['id']] = self._builtin(entry['id'], publish=True, entry=entry)
        selection = {'scope_key': scope, 'team_id': team_id, 'packages': list(selected.values())}
        return {**selection, 'selection_digest': semantic_digest(selection), **({'admission_observations': notes} if notes else {})}

    def validate_selection(self, *, authorization, principal_teams=(), selection, require_current=True):
        scope = self._scope(authorization, principal_teams, selection.get('team_id'))
        material = {key: selection[key] for key in ('scope_key', 'team_id', 'packages')}
        if selection.get('selection_digest') != semantic_digest(material) or material['scope_key'] != scope:
            raise ValueError('DOMAIN_PACKAGE_SELECTION_BINDING_MISMATCH')
        for snapshot in material['packages']:
            if snapshot.get('revision') is None:
                raise ValueError('DOMAIN_PACKAGE_SELECTION_BINDING_MISMATCH')
            current = self.read(authorization=authorization, principal_teams=principal_teams,
                team_id=material['team_id'], package_id=snapshot['package_id'], revision=snapshot['revision'],
                _historical=not require_current)
            if current != snapshot:
                raise ValueError('DOMAIN_PACKAGE_SELECTION_CHANGED')
        self._validate_dependencies(material['packages'], historical=True)
        return selection

    def selection_fences(self, *, authorization, principal_teams=(), selection):
        self.validate_selection(authorization=authorization, principal_teams=principal_teams, selection=selection)
        writes = []
        for package in selection['packages']:
            if package['origin'] != 'team_adoption':
                continue
            # A long source preparation may outlive the initial selection read.
            # Reconcile at the existing final admission fence too; this never
            # dispatches an evaluator or resets a task's attempt budget.
            observed = self._admission_monitor(authorization, principal_teams, package['adoption_revision'])
            if observed['outcome'] == 'fail':
                raise ValueError('DOMAIN_PACKAGE_WITHDRAWN')
            adoption = self._published_event(package['adoption_revision'], 'adopted')
            monitor_key = self._key('monitor', selection['scope_key'], adoption['candidate_revision'])
            monitor = self._checked_monitor(selection['scope_key'], adoption['candidate_revision'])
            writes.append(AtomicWrite('agent_task_idempotency', monitor_key, monitor, monitor))
            key = self._key('withdrawal', selection['scope_key'], package['revision'])
            row = self.store.get('agent_task_idempotency', key)
            if not row or row.get('withdrawn'):
                raise ValueError('DOMAIN_PACKAGE_WITHDRAWN')
            writes.append(AtomicWrite('agent_task_idempotency', key, row, row))
        return tuple(writes)

    def resolve_bound_assets(self, *, authorization, principal_teams=(), selection, require_current=True):
        self.validate_selection(authorization=authorization, principal_teams=principal_teams, selection=selection,
            require_current=require_current)
        result = {}
        for package in selection['packages']:
            if package['origin'] != 'team_adoption':
                continue
            _, _, _, closure = self._pack(authorization, selection['team_id'], package['revision'])
            result.update(closure)
        return result

    def read_bound_asset(self, *, authorization, principal_teams=(), selection, revision, require_current=True):
        members = self.resolve_bound_assets(authorization=authorization, principal_teams=principal_teams,
            selection=selection, require_current=require_current)
        ref = _ref(revision)
        if ref not in members:
            raise ValueError('DOMAIN_PACKAGE_MEMBER_NOT_BOUND')
        return members[ref]
