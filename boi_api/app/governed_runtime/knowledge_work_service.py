"""Durable external-agent assetization, using the existing task/run store.

This service prepares work and preserves submissions. It does not execute a
model, infer domain identity, or turn a caller's assessment into approval.
"""
from collections import Counter
import json

from .domain_asset_store import DomainAssetCreateRequest, DomainAssetDraft, DomainAssetStore, source_manifest_digest
from .knowledge_work_contract import (
    KnowledgeWorkStart, KnowledgeWorkRead, KnowledgeWorkNext, KnowledgeWorkSubmit,
    KnowledgeWorkControl, KnowledgeWorkResult, KnowledgeWorkReconcile, KnowledgeWorkContext, KnowledgeWorkOutput, result_payload,
)
from .ledger import RecordKind, record_digest, LedgerError
from . import knowledge_work_budget as work_budget
from .knowledge_work_revision import prepare_revision
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest
from .source_field_projection import SourceFieldProjectionService
from .task_knowledge import KnowledgeRequirement
from ..v2.atomic_store_contract import AtomicWrite


class KnowledgeWorkService:
    CONTRACT = 'boi/knowledge-work@1'
    MAX_ATTEMPTS_PER_UNIT = 3
    RECORDS_PER_UNIT = 8

    def __init__(self, intake, *, packages, principal_teams=()):
        self.intake, self.packages = intake, packages
        self.teams = tuple(principal_teams)
        self.store, self.ledger, self.objects = intake.store, intake.ledger, intake.objects
        self.assets = DomainAssetStore(intake)

    def _authorize(self, auth, *, mutate=False):
        self.intake._policy(auth)
        uses = {'derive', 'model_input'} | ({'store'} if mutate else set())
        if not uses <= set(auth.allowed_uses):
            raise ValueError('KNOWLEDGE_WORK_NOT_AUTHORIZED')

    def _read(self, auth, task_ref):
        self._authorize(auth)
        row = self.store.get('agent_task_packages', task_ref)
        if not row or row.get('employee_id') != auth.principal or row.get('contract_version') != self.CONTRACT:
            raise ValueError('KNOWLEDGE_WORK_ACCESS_DENIED')
        if row['policy_digest'] != auth.policy_digest:
            raise ValueError('KNOWLEDGE_WORK_POLICY_CHANGED')
        self.assets.authorize_sources(auth, tuple(ArtifactEnvelope.model_validate(s) for s in row['sources']), model_input=True, metadata_only=True)
        return row

    def _valid_selection(self, auth, row):
        self.packages.validate_selection(authorization=auth, principal_teams=self.teams, selection=row['package_selection'])

    def _selection_fences(self, auth, row):
        return self.packages.selection_fences(authorization=auth, principal_teams=self.teams, selection=row['package_selection'])

    def _cas(self, *writes):
        if not self.store.atomic_compare_and_write(writes):
            raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')

    @staticmethod
    def _ref(row):
        return RevisionRef(ref=row.record_id, revision_digest=record_digest(row.record_id)).model_dump(mode='json')

    def _view(self, row):
        units = row['units']
        counts = Counter(u['status'] for u in units)
        results = [r for u in units for r in u.get('results', [])]
        unresolved = [dict(unit_id=u['unit_id'], status=u['status'], reason=u.get('summary', ''))
                      for u in units if u['status'] in ('failed', 'unknown', 'unresolved') or u.get('unresolved')
                      or any(r['disposition'] == 'unresolved' for r in u.get('record_outcomes', []))]
        return {
            'task_ref': row['task_package_id'], 'revision': row['revision'],
            'contract_version': self.CONTRACT, 'title': row['request_text'], 'status': row['status'],
            'namespace': row['namespace'], 'package_selection': row['package_selection'],
            'sources': row['sources'], 'previous_task_ref': row.get('previous_task_ref'),
            'coverage': {'source_preserved': True, 'source_field_count': row['source_field_count'],
                         'unit_count': len(units), 'unit_states': dict(counts),
                         'asset_reference_count': len(results), 'semantic_review': 'not_verified',
                         'scientific_truth': 'not_established', 'computation_admission': 'requires_native_execution_checks'},
            'attempts_used': len({ref for ref in [*row.get('prior_attempt_refs', []),
                *(ref for u in units for ref in u.get('attempt_refs', []))] if not ref.startswith('knowledge-recovery:')}),
            'source_delta': row.get('source_delta'),
            'max_attempts_per_unit': row['max_attempts_per_unit'],
            'active_attempt_ref': row.get('active_attempt_ref'),
            'units': [{**{k: u[k] for k in ('unit_id', 'status', 'attempts', 'attempt_refs', 'source_ref', 'record_locators', 'record_outcomes', 'results', 'record_lineage', 'carried_from', 'carry_basis',
                'original_evidence_rewritten', 'previous_unit_refs', 'revision_impact', 'revision_impact_review') if k in u},
                'budget_remaining': min(max(0, row['max_attempts_per_unit'] - u['attempts']),
                    work_budget.remaining(self, row['employee_id'], row['task_package_id'], u))} for u in units],
            'result_refs': results, 'exceptions': unresolved,
            'next_action': ('Recover the exact reserved attempt; do not rerun the model.' if row.get('active_attempt_ref')
                            else 'Connect an external agent and call next with this revision.' if row['status'] == 'waiting_external_agent'
                            else 'Read results and unresolved coverage; stored outputs do not establish semantic approval.'),
            'url': '/knowledge?tab=work', 'durable': bool(self.store.durable),
        }

    def _units(self, auth, sources, previous=None):
        units, field_count = [], 0
        projector = SourceFieldProjectionService(self.intake)
        for source in sources:
            old = next((u for u in (previous or {}).get('units', []) if u['source_ref'] == source), None)
            if old:
                projector.select_manifest_fields(authorization=auth, reference=source,
                    manifest_ref=old['manifest_ref'], span_refs=[])
                manifest = {'manifest_ref': old['manifest_ref'], **self.ledger.read(old['manifest_ref']).payload}
            else:
                manifest = projector.project(authorization=auth, reference=source)
            grouped = {}
            for field in manifest['fields']:
                grouped.setdefault(field['record_locator'], []).append(field['span_ref'])
            entries = list(grouped.items())
            field_count += len(manifest['fields'])
            for offset in range(0, len(entries), self.RECORDS_PER_UNIT):
                selected = entries[offset:offset + self.RECORDS_PER_UNIT]
                spans = [s for _, refs in selected for s in refs]
                units.append({'unit_id': semantic_digest([source, spans]), 'source_ref': source,
                              'manifest_ref': manifest['manifest_ref'],
                              'record_locators': [key for key, _ in selected], 'span_refs': spans,
                              'status': 'pending', 'attempts': 0, 'results': []})
        if not units or len(units) > 2000:
            raise ValueError('KNOWLEDGE_WORK_SOURCE_UNIT_LIMIT')
        return units, field_count

    def start(self, *, authorization, request):
        req = KnowledgeWorkStart.model_validate(request)
        self._authorize(authorization, mutate=True)
        sources = [s.model_dump(mode='json') for s in req.sources]
        self.assets.authorize_sources(authorization, req.sources, model_input=True)
        idem = 'knowledge-start:' + semantic_digest([authorization.principal, req.idempotency_key])
        material = req.model_dump(mode='json', exclude={'idempotency_key'})
        if not material['source_revisions']:
            material.pop('source_revisions')
        fingerprint = semantic_digest(material)
        reservation = self.store.get('agent_task_idempotency', idem)
        if reservation:
            if reservation['fingerprint'] != fingerprint:
                raise ValueError('KNOWLEDGE_WORK_IDEMPOTENCY_CONFLICT')
            return {**self._view(self._read(authorization, reservation['task_ref'])), 'replayed': True}
        previous = self._read(authorization, req.previous_task_ref) if req.previous_task_ref else None
        if previous and (previous.get('active_attempt_ref') or any(u['status'] == 'unknown' for u in previous['units'])):
            raise ValueError('KNOWLEDGE_WORK_PREVIOUS_REQUIRES_RECONCILIATION')
        if req.source_revisions and previous is None:
            raise ValueError('KNOWLEDGE_WORK_SOURCE_REVISION_PARENT_REQUIRED')
        selection = self.packages.resolve_for_work(authorization=authorization, principal_teams=self.teams,
                                                   package_ids=req.package_ids, team_id=req.team_id)
        scope = selection['scope_key']
        # Exact requests and pinned packages deduplicate across hosts and keys.
        task_ref = 'knowledge-work:' + semantic_digest([authorization.principal, fingerprint, selection['selection_digest']])
        prior = self.store.get('agent_task_packages', task_ref)
        if prior is None:
            units, field_count = self._units(authorization, sources, previous)
            reusable = bool(previous and previous['request_text'] == req.request_text
                and previous['package_selection']['selection_digest'] == selection['selection_digest']
                and previous['scope_key'] == scope)
            delta, fences = None, ()
            if previous:
                units, delta = prepare_revision(self, authorization, previous, units, req.source_revisions,
                    semantics_compatible=reusable)
                if len(units) > 2000:
                    raise ValueError('KNOWLEDGE_WORK_SOURCE_UNIT_LIMIT')
                fences = (AtomicWrite('agent_task_packages', req.previous_task_ref, previous, previous),
                    *work_budget.inherit(self, authorization, previous, previous['units']),
                    *self._current_dependency_fences(authorization, [RevisionRef.model_validate(r['revision'])
                        for u in units if u['status'] == 'produced' for r in u['results'] if r.get('revision')]))
                change = self.ledger.append(RecordKind.RUN, {
                    **delta, 'employee_id': authorization.principal, 'policy_digest': authorization.policy_digest,
                    'task_ref': task_ref, 'previous_task_revision': previous['revision'],
                    'package_selection_digest': selection['selection_digest']},
                    authority='migration_service', occurred_at=self.intake.clock().isoformat())
                delta = {**delta, 'revision': self._ref(change)}
            prior_attempts = list(dict.fromkeys([*(previous or {}).get('prior_attempt_refs', []),
                *(ref for u in (previous or {}).get('units', []) for ref in u.get('attempt_refs', []))]))
            prior = {'contract_version': self.CONTRACT, 'task_package_id': task_ref,
                     'employee_id': authorization.principal, 'policy_digest': authorization.policy_digest,
                     'scope_key': scope, 'namespace': 'workspace:' + semantic_digest([authorization.principal, scope]).removeprefix('sha256:'),
                     'request_text': req.request_text, 'sources': sources, 'package_selection': selection,
                     'previous_task_ref': req.previous_task_ref, 'units': units, 'source_field_count': field_count,
                     'source_delta': delta, 'prior_attempt_refs': prior_attempts,
                     'max_attempts_per_unit': min(self.MAX_ATTEMPTS_PER_UNIT,
                         (previous or {}).get('max_attempts_per_unit', self.MAX_ATTEMPTS_PER_UNIT)), 'revision': 1,
                     'status': 'waiting_external_agent' if any(u['status']=='pending' for u in units) else 'outputs_recorded', 'active_attempt_ref': None,
                     'created_at': self.intake.clock().isoformat(), 'approval_required': False,
                     'canonical_projection_eligible': False}
            self._cas(AtomicWrite('agent_task_packages', task_ref, None, prior),
                      AtomicWrite('agent_task_idempotency', idem, None, {'employee_id': authorization.principal, 'fingerprint': fingerprint, 'task_ref': task_ref}),
                      *fences, *self.packages.selection_fences(authorization=authorization, principal_teams=self.teams, selection=selection))
        else:
            self._read(authorization, task_ref)
            self._cas(AtomicWrite('agent_task_idempotency', idem, None, {'employee_id': authorization.principal, 'fingerprint': fingerprint, 'task_ref': task_ref}))
        return self._view(self._read(authorization, task_ref))

    def _validate_revision_scope(self, auth, row, attempt, result):
        if attempt.get('revision_impact') and result.outcome == 'produced' and result.revision_impact_review is None:
            raise ValueError('KNOWLEDGE_WORK_REVISION_IMPACT_REVIEW_REQUIRED')
        for ref in result.revision_scope.context_spans:
            span = self.ledger.read(ref.ref)
            source = next((s for s in row['sources'] if s['artifact_ref'] == span.payload.get('artifact_ref')), None)
            if (span.kind != RecordKind.EVIDENCE_SPAN or record_digest(span.record_id) != ref.revision_digest
                    or source is None or span.payload.get('source_revision_digest') != source['digest']
                    or span.payload.get('employee_id') != auth.principal or span.payload.get('policy_digest') != auth.policy_digest):
                raise ValueError('KNOWLEDGE_WORK_REVISION_CONTEXT_DENIED')

    def _outputs_current(self, auth, results):
        pending = [RevisionRef.model_validate(r['revision']) for r in results if r.get('revision')]
        seen = set()
        while pending:
            revision = pending.pop()
            if revision in seen:
                continue
            if len(seen) >= 10000:
                return False
            seen.add(revision)
            try:
                record, asset = self.assets._read_record(auth, revision)
            except (ValueError, LedgerError, OSError):
                # Missing or newly inaccessible dependencies prevent reuse of
                # this unit; they do not prove absence or invalidate other units.
                return False
            key = 'domain-asset-head:' + semantic_digest([auth.principal, record.payload['namespace'], record.payload['logical_id']])
            if (self.store.get('domain_asset_heads', key) or {}).get('revision') != revision.model_dump(mode='json'):
                return False
            pending.extend(d.revision for d in asset.dependencies)
        return True

    def status(self, *, authorization, request):
        req = KnowledgeWorkRead.model_validate(request)
        row = self._read(authorization, req.task_ref)
        result = self._view(row)
        from .catalog_search_index import readiness
        result['search_readiness'] = readiness(self.assets, authorization,
            [RevisionRef.model_validate(item['revision']) for unit in row['units']
             for item in unit.get('results', ()) if item.get('revision')])
        from ..v2.knowledge_supervision import KnowledgeSupervisionService
        result['supervision'] = KnowledgeSupervisionService(self.intake, self).instructions_for_task(
            authorization=authorization, task_ref=req.task_ref)
        if row.get('active_attempt_ref'):
            attempt = self.store.get('task_runs', row['active_attempt_ref'])
            if attempt and attempt.get('employee_id') == authorization.principal:
                result['active_attempt'] = attempt
        return result

    def _correction_unit(self, authorization, row):
        """Select an unattempted user correction without resetting source work.

        Reading or attempting an instruction does not resolve it. The external
        agent may report handling through the exact supervision event later.
        """
        if row.get('active_attempt_ref') or row['status'] == 'stopped':
            return None, {}
        from ..v2.knowledge_supervision import KnowledgeSupervisionService
        instructions = KnowledgeSupervisionService(self.intake, self).instructions_for_task(
            authorization=authorization, task_ref=row['task_package_id'])['items']
        by_unit = {}
        for index, unit in enumerate(row['units']):
            applicable = [event for event in instructions if unit['unit_id'] in event['unit_ids']]
            if applicable:
                by_unit[index] = applicable
        unknown, exhausted = False, False
        for index, events in by_unit.items():
            unit = row['units'][index]
            attempted = unit.get('supervision_attempted_refs', ())
            if not any(event['event_ref'] not in attempted for event in events):
                continue
            if unit['status'] == 'unknown':
                unknown = True
                continue
            if (unit['attempts'] >= row['max_attempts_per_unit'] or
                    work_budget.remaining(self, authorization.principal, row['task_package_id'], unit) <= 0):
                exhausted = True
                continue
            if unit['status'] in ('pending', 'produced', 'failed', 'unresolved'):
                return index, by_unit
        if row['status'] != 'waiting_external_agent':
            if unknown:
                raise ValueError('KNOWLEDGE_WORK_UNKNOWN_REQUIRES_RECONCILIATION')
            if exhausted:
                raise ValueError('KNOWLEDGE_WORK_BUDGET_EXHAUSTED')
        return None, by_unit

    def next(self, *, authorization, request):
        req = KnowledgeWorkNext.model_validate(request)
        self._authorize(authorization, mutate=True)
        row = self._read(authorization, req.task_ref)
        self._valid_selection(authorization, row)
        # Before revision checks, reconcile the exact prior admission. Repeated
        # next never starts another provider run, including on a new host.
        if row.get('active_attempt_ref'):
            return self.status(authorization=authorization, request={'task_ref': req.task_ref})
        idem = 'knowledge-next:' + semantic_digest([authorization.principal, req.task_ref, req.idempotency_key])
        prior = self.store.get('agent_task_idempotency', idem)
        if prior:
            return {**self._view(row), 'previous_attempt': self.store.get('task_runs', prior['attempt_ref']), 'replayed': True}
        if req.expected_revision != row['revision']:
            raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')
        correction_index, correction_instructions = self._correction_unit(authorization, row)
        if row['status'] != 'waiting_external_agent' and correction_index is None:
            raise ValueError('KNOWLEDGE_WORK_NOT_READY')
        retry_index = next((i for i, u in enumerate(row['units'])
                            if u['status'] == 'pending' and u.get('retry_requested_revision')), None)
        index = correction_index if correction_index is not None else retry_index
        if index is None:
            index = next((i for i, u in enumerate(row['units']) if u['status'] == 'pending'), None)
        if index is None:
            return self._view(row)
        unit = row['units'][index]
        if (unit['attempts'] >= row['max_attempts_per_unit'] or
                work_budget.remaining(self, authorization.principal, req.task_ref, unit) <= 0):
            raise ValueError('KNOWLEDGE_WORK_BUDGET_EXHAUSTED')
        candidates = self.assets.catalog(authorization=authorization, namespace=None, kind='definition',
                                         query=row['request_text'][:2000], limit=20)
        # Discovery is not semantic selection. Only exact correction/prior
        # result references are read before the external agent chooses others.
        context_roots = []
        corrections = correction_instructions.get(index, [])
        previous_results = list({semantic_digest(r): r for r in [*unit.get('results', []), *unit.get('previous_unit_results', [])]}.values())
        exact = [ref for event in corrections for ref in event['asset_revisions']]
        exact.extend(item['revision'] for item in previous_results if item.get('revision'))
        if exact:
            indexed = set()
            for ref in exact:
                self.assets._read_record(authorization, RevisionRef.model_validate(ref))
                if ref['ref'] not in indexed:
                    context_roots.insert(0, {'revision': ref, 'discovery_basis': 'exact_correction_target'})
                    indexed.add(ref['ref'])
        context = self._resolve_context(authorization, unit['source_ref'],
            tuple(KnowledgeRequirement(revision=RevisionRef.model_validate(item['revision']), role='definition',
                reason='Exact correction or prior result', stages=('assetization',)) for item in context_roots))
        # Old attempts retain their protected context and are returned unchanged.
        attempt_ref = 'knowledge-attempt:' + semantic_digest([req.task_ref, unit['unit_id'], unit['attempts'] + 1])
        attempt = {'contract_version': 'boi/knowledge-attempt@1', 'run_id': attempt_ref,
                   'employee_id': authorization.principal, 'task_ref': req.task_ref, 'unit_id': unit['unit_id'],
                   'package_selection': row['package_selection'], 'state': 'awaiting_external_result',
                   'namespace': row['namespace'], 'source_ref': unit['source_ref'],
                   'manifest_ref': unit['manifest_ref'], 'source_span_refs': unit['span_refs'],
                   'record_locators': unit['record_locators'], 'existing_knowledge': candidates,
                   'correction_instructions': corrections,
                   'previous_unit_results': previous_results,
                   'previous_unit_refs': unit.get('previous_unit_refs', []),
                   'record_lineage': unit.get('record_lineage', []),
                   'revision_impact': unit.get('revision_impact'),
                   'prior_record_outcomes': unit.get('record_outcomes', []),
                   'interpretation_context': context.model_dump(mode='json'),
                   'result_schema': KnowledgeWorkResult.model_json_schema(),
                   'instructions': ('Read the pinned package skills and exact source fields, including headers and correction context. '
                       'Discovery candidates are references, not selected context. Read appropriate candidates and add their exact revisions with context before context-bound authoring. '
                       'Search existing knowledge, compare applicability, and reuse or revise exact references. '
                       'Create only missing meanings, preserve conditions, conflicts and unknowns. '
                       'Submit the structured result and original external output. No passed flag is accepted. '
                       'Use boi_source_field for paged source text and boi_knowledge_catalog/read for additional candidates. '
                       'An empty candidate search does not prove absence; neither row numbers nor names prove identity.'),
                   'created_at': self.intake.clock().isoformat()}
        updated = json.loads(json.dumps(row))
        if unit['attempts']:
            updated['units'][index].setdefault('history', []).append({key: unit[key] for key in (
                'status', 'attempts', 'results', 'summary', 'record_outcomes', 'submission_ref', 'unresolved') if key in unit})
        if corrections:
            attempted = updated['units'][index].setdefault('supervision_attempted_refs', [])
            attempted.extend(event['event_ref'] for event in corrections if event['event_ref'] not in attempted)
        updated['units'][index].update(status='awaiting_external_result', attempts=unit['attempts'] + 1)
        updated['units'][index].pop('retry_requested_revision', None)
        updated['units'][index].setdefault('attempt_refs', []).append(attempt_ref)
        updated.update(revision=row['revision'] + 1, active_attempt_ref=attempt_ref, status='waiting_external_agent')
        self._cas(AtomicWrite('agent_task_packages', req.task_ref, row, updated),
                  AtomicWrite('task_runs', attempt_ref, None, attempt),
                  AtomicWrite('agent_task_idempotency', idem, None, {'employee_id': authorization.principal, 'attempt_ref': attempt_ref}),
                  *work_budget.reserve(self, authorization, req.task_ref, unit, attempt_ref),
                  *self._selection_fences(authorization, row))
        return self.status(authorization=authorization, request={'task_ref': req.task_ref})

    def output(self, *, authorization, request):
        req = KnowledgeWorkOutput.model_validate(request)
        row = self._read(authorization, req.task_ref)
        attempt = self.store.get('task_runs', req.attempt_ref)
        if not attempt or attempt.get('employee_id') != authorization.principal or attempt.get('task_ref') != req.task_ref:
            raise ValueError('KNOWLEDGE_WORK_ATTEMPT_ACCESS_DENIED')
        raw = self.objects.get(attempt['raw_output_digest']).decode('utf-8') if attempt.get('raw_output_digest') else ''
        if raw and byte_digest(raw.encode('utf-8')) != attempt['raw_output_digest']:
            raise ValueError('KNOWLEDGE_WORK_OUTPUT_CONTENT_DRIFT')
        end = min(len(raw), req.offset + req.limit)
        return {'task_ref':row['task_package_id'], 'attempt_ref':req.attempt_ref, 'state':attempt['state'],
                'result':attempt.get('result'), 'published_results':attempt.get('published_results', []),
                'validation_error':attempt.get('validation_error'), 'raw_output_digest':attempt.get('raw_output_digest'),
                'text':raw[req.offset:end], 'offset':req.offset, 'next_offset':end if end<len(raw) else None,
                'character_count':len(raw), 'offset_basis':'unicode_codepoints'}

    def _resolve_context(self, auth, source, roots):
        from .task_knowledge import resolve_task_knowledge
        from .task_source_navigation import defer_workbook_inventory
        cache = {}
        def read(ref):
            if ref not in cache:
                cache[ref] = self.assets._read_record(auth, ref)[1]
            return cache[ref]
        return resolve_task_knowledge(principal_id=auth.principal, policy_digest=auth.policy_digest,
            purpose='knowledge_assetization', source_manifest_digest=semantic_digest([source]), roots=roots,
            read_authorized_revision=read, lane='provisional', available_tools=frozenset(),
            require_available_tools=False,
            defer_optional_requirement=lambda parent, req: defer_workbook_inventory(read, parent, req))

    def context(self, *, authorization, request):
        req = KnowledgeWorkContext.model_validate(request)
        self._authorize(authorization, mutate=True)
        row = self._read(authorization, req.task_ref)
        self._valid_selection(authorization, row)
        attempt = self.store.get('task_runs', req.attempt_ref)
        if not attempt or attempt.get('employee_id') != authorization.principal or row.get('active_attempt_ref') != req.attempt_ref:
            raise ValueError('KNOWLEDGE_WORK_ATTEMPT_ACCESS_DENIED')
        key = 'knowledge-context:' + semantic_digest([authorization.principal, req.task_ref, req.idempotency_key])
        fingerprint = semantic_digest(req.model_dump(mode='json'))
        prior = self.store.get('agent_task_idempotency', key)
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise ValueError('KNOWLEDGE_WORK_IDEMPOTENCY_CONFLICT')
            return {**self.status(authorization=authorization, request={'task_ref':req.task_ref}), 'replayed':True}
        if attempt.get('submission_digest') or row['status'] == 'stopped':
            raise ValueError('KNOWLEDGE_WORK_CONTEXT_ALREADY_PINNED')
        if row['revision'] != req.expected_revision:
            raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')
        roots = {RevisionRef.model_validate(s['requirement']['revision']): KnowledgeRequirement.model_validate(s['requirement'])
            for s in attempt['interpretation_context']['selections'] if s['parent'] is None}
        roots.update({ref: KnowledgeRequirement(revision=ref, role='definition',
            reason='Explicit additional comparison context', stages=('assetization',)) for ref in req.revisions})
        if len(roots)>100:
            raise ValueError('KNOWLEDGE_WORK_CONTEXT_LIMIT')
        resolved = self._resolve_context(authorization, attempt['source_ref'],
            tuple(roots[r] for r in sorted(roots, key=lambda r:r.ref)))
        old_context = attempt['interpretation_context']
        old_ref = self.objects.put(json.dumps(old_context, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())
        history = [*attempt.get('context_history', []),
                   {'context_digest': old_context['context_digest'], 'object_ref': old_ref, 'task_revision': row['revision']}]
        updated = {**attempt, 'interpretation_context': resolved.model_dump(mode='json'), 'context_history': history}
        self._cas(AtomicWrite('task_runs', req.attempt_ref, attempt, updated),
                  AtomicWrite('agent_task_packages', req.task_ref, row, {**row,'revision':row['revision'] + 1}),
                  AtomicWrite('agent_task_idempotency', key, None, {'employee_id':authorization.principal,'fingerprint':fingerprint}),
                  *self._selection_fences(authorization, row))
        return self.status(authorization=authorization, request={'task_ref':req.task_ref})

    def _expand_retained_change(self, auth, row, change):
        """Expand an exact immutable target, before ordinary domain admission.

        This saves client copying; it does not select meanings or waive current
        source, record, comparison, dependency or publication checks.
        """
        if not change.retain_target_content:
            return change
        target, asset = self.assets._read_record(auth, change.target_revision)
        if source_manifest_digest(target.payload['sources']) != source_manifest_digest(row['sources']):
            raise ValueError('KNOWLEDGE_WORK_RETAIN_SOURCE_MISMATCH')
        content = json.loads(asset.content_json)
        evidence = asset.evidence
        if not evidence and content.get('contract_version') in ('boi/bound-process-meaning@1', 'boi/bound-process-meaning@2'):
            from .knowledge_work_admission import _quoted_spans
            evidence = tuple(RevisionRef(ref=ref, revision_digest=record_digest(ref))
                             for ref in sorted(_quoted_spans(content)))
        return change.model_copy(update={'retain_target_content': False, 'content': content,
            'evidence_spans': evidence, 'dependencies': tuple(d.revision for d in asset.dependencies)})

    def _prepare_change(self, auth, row, attempt, change, binding_checks=None):
        from .knowledge_work_admission import validate_change_evidence
        target = None
        original_asset = None
        if change.target_revision:
            target, original_asset = self.assets._read_record(auth, change.target_revision)
        for dep in change.dependencies:
            self.assets._read_record(auth, dep)
        if change.operation == 'reuse':
            validate_change_evidence(ledger=self.ledger, authorization=auth, work=row,
                                     attempt=attempt, change=change)
            return {'operation': 'reuse', 'revision': change.target_revision.model_dump(mode='json'), 'reason': change.reason}
        if change.operation == 'unresolved':
            return {'operation': 'unresolved', 'reason': change.reason}
        content = change.content
        original_content = json.loads(original_asset.content_json) if original_asset is not None else None
        original_evidence = set(original_asset.evidence) if original_asset is not None else set()
        if (original_content is not None and not original_evidence
                and original_content.get('contract_version') in ('boi/bound-process-meaning@1', 'boi/bound-process-meaning@2')):
            # Older process assets kept exact spans inside the bound content,
            # with an empty envelope list. Read that immutable binding rather
            # than requiring a new extraction or trusting added caller spans.
            from .knowledge_work_admission import _quoted_spans
            from .ledger import record_digest
            original_evidence = {RevisionRef(ref=ref, revision_digest=record_digest(ref))
                                 for ref in _quoted_spans(original_content)}
        # Equality is a byte-independent comparison of the submitted old JSON,
        # not a semantic-equivalence judgment. Domain binders still validate it.
        metadata_only = bool(change.operation == 'revise' and original_asset is not None
            and content == original_content
            and set(change.evidence_spans) == original_evidence
            and set(change.dependencies) <= {d.revision for d in original_asset.dependencies}
            and source_manifest_digest(target.payload['sources']) == source_manifest_digest(row['sources']))
        supported = {c for p in row['package_selection']['packages'] for c in p['manifest'].get('content_contracts', [])}
        preserved_process_binding = (metadata_only and 'boi/process-meaning@1' in supported
            and content.get('contract_version') in ('boi/bound-process-meaning@1', 'boi/bound-process-meaning@2'))
        # A process package already consumes its binder's stored output. An
        # exact metadata-only revision retains that output and its provenance;
        # clients still cannot create or edit a purported bound payload.
        if content.get('contract_version') not in supported and not preserved_process_binding:
            raise ValueError('KNOWLEDGE_WORK_CONTENT_CONTRACT_UNSUPPORTED')
        if preserved_process_binding:
            from .source_field_compatibility import read_compatible_revision_fields
            # Keep the original bound spans. Parser/runtime revisions can give
            # unchanged fields new span IDs; prove their full structural and
            # source equality under current rights before record admission.
            compatible = read_compatible_revision_fields(SourceFieldProjectionService(self.intake),
                authorization=auth, reference=attempt['source_ref'], manifest_ref=attempt['manifest_ref'],
                span_refs=[ref.ref for ref in change.evidence_spans])
            binding_checks = binding_checks if binding_checks is not None else {}
            binding_checks['source_projection_compatibility'] = compatible['source_projection_compatibility']
        referenced = set(change.dependencies)
        if content.get('contract_version') == 'boi/process-meaning@1':
            from agent_kit.python.boi_process_lint import bind_process_meaning
            projector = SourceFieldProjectionService(self.intake)
            source = attempt['source_ref']
            restored = projector.restore_manifest(authorization=auth, reference=source, manifest_ref=attempt['manifest_ref'])
            manifest = restored['manifest']
            fields = []
            for field in manifest['fields']:
                span = self.ledger.read(field['span_ref'])
                raw = self.objects.get(span.payload['field_object_ref'])
                if byte_digest(raw) != field['content_digest']:
                    raise ValueError('KNOWLEDGE_WORK_SOURCE_CONTENT_DRIFT')
                fields.append({**field, 'text': raw.decode('utf-8')})
            content = bind_process_meaning(content, evidence={'source':source,'manifest':manifest,'fields':fields},
                extraction_context=attempt['interpretation_context'], version=2)
            referenced.update(RevisionRef.model_validate(r) for r in content['draft'].get('definition_revisions_used', []))
        sources = tuple(ArtifactEnvelope.model_validate(s) for s in row['sources'])
        bound_dependencies = None
        if content.get('contract_version') == 'boi/svid-native-interpretation@1':
            from .knowledge_svid_binding import bind_work_svid
            operation_key = 'domain-asset-request:' + semantic_digest([
                auth.principal, semantic_digest([attempt['run_id'], change.change_id])])
            committed = (self.store.get('domain_asset_idempotency', operation_key) or {}).get('response')
            binding_change = (change.model_copy(update={'dependencies': tuple(d.revision for d in original_asset.dependencies)})
                              if metadata_only else change)
            binding_checks = binding_checks if binding_checks is not None else {}
            bound_dependencies = []
            content = bind_work_svid(content, intake=self.intake, authorization=auth, work=row, attempt=attempt,
                                    change=binding_change, publication_recovery=bool(committed),
                                    preserve_metadata_content=metadata_only, binding_checks=binding_checks,
                                    binding_dependencies=bound_dependencies)
        if content.get('contract_version') == 'boi/common-meaning@1':
            from .common_knowledge_contract import validate_common_evidence
            content = validate_common_evidence(content, assets=self.assets, authorization=auth, sources=sources).model_dump(mode='json')
            referenced.update(RevisionRef.model_validate(c['reused_definition']) for c in content['concepts'] if c.get('reused_definition'))
        validate_change_evidence(ledger=self.ledger, authorization=auth, work=row,
                                 attempt=attempt, change=change, content=content,
                                 span_equivalence=(binding_checks or {}).get('source_projection_compatibility', {}).get('span_equivalence'))
        compared = {RevisionRef.model_validate(r) for r in attempt.get('result', {}).get('existing_revisions_considered', [])}
        if not referenced <= compared:
            raise ValueError('KNOWLEDGE_WORK_DEPENDENCY_COMPARISON_REQUIRED')
        for revision in referenced:
            self.assets._read_record(auth, revision)
        if content.get('canonical_projection_eligible') is True or content.get('live_execution_ready') is True:
            raise ValueError('KNOWLEDGE_WORK_CALLER_AUTHORITY_NOT_ACCEPTED')
        # Existing shared packages never confer access to another user's target.
        namespace = target.payload['namespace'] if change.operation == 'revise' else row['namespace']
        logical_id = target.payload['logical_id'] if change.operation == 'revise' else (
            'meaning:' + semantic_digest([row['task_package_id'], attempt['unit_id'], change.change_id]).removeprefix('sha256:'))
        draft = DomainAssetDraft(logical_id=logical_id, namespace=namespace, title=change.title,
                                 description=change.description, kind='definition',
                                 content_json=json.dumps(content, ensure_ascii=False), sources=sources,
                                 evidence_spans=change.evidence_spans,
                                 dependencies=tuple(KnowledgeRequirement(revision=r, role='definition', reason=change.reason, stages=('assetization',))
                                     for r in sorted(referenced, key=lambda r:r.ref)),
                                 previous_revision=change.target_revision if change.operation == 'revise' else None,
                                 conflicts_with=(change.target_revision,) if change.operation == 'conflict' else ())
        if bound_dependencies is not None:
            # Domain validators return the requirements they actually consumed.
            # Preserve prior roles/stages and retain the typed unit obligation;
            # a list of generic caller references cannot replace either one.
            requirements = tuple(KnowledgeRequirement.model_validate(d) for d in bound_dependencies)
            represented = {d.revision for d in requirements}
            draft = draft.model_copy(update={'dependencies': requirements + tuple(
                d for d in draft.dependencies if d.revision not in represented)})
            if original_asset is not None:
                draft = draft.model_copy(update={'conflicts_with': original_asset.conflicts_with,
                                                 'supersedes': original_asset.supersedes})
        if metadata_only:
            draft = draft.model_copy(update={
                'evidence_spans': original_asset.evidence,
                'dependencies': original_asset.dependencies,
                'conflicts_with': original_asset.conflicts_with,
                'supersedes': original_asset.supersedes})
        # Source ownership, exact revisions, quoted spans and primary records
        # were checked together before constructing this publication draft.
        if target is not None and change.operation == 'revise':
            key = 'domain-asset-head:' + semantic_digest([auth.principal, target.payload['namespace'], target.payload['logical_id']])
            operation_key = 'domain-asset-request:' + semantic_digest([auth.principal, semantic_digest([attempt['run_id'], change.change_id])])
            recovered = self.store.get('domain_asset_idempotency', operation_key) or {}
            if not recovered.get('response') and (self.store.get('domain_asset_heads', key) or {}).get('revision') != change.target_revision.model_dump(mode='json'):
                raise ValueError('DOMAIN_ASSET_PREVIOUS_REVISION_CONFLICT')
        return draft

    def _current_dependency_fences(self, auth, revisions):
        """Bind current-use admission to exact heads, including transitive inputs.

        Historical reads still use the ordinary authorized immutable reader.
        These fences apply only when admitting new use or completing work.
        """
        pending, seen, fences = list(revisions), set(), []
        while pending:
            revision = pending.pop()
            if revision in seen:
                continue
            if len(seen) >= 10000:
                raise ValueError('KNOWLEDGE_WORK_DEPENDENCY_LIMIT')
            seen.add(revision)
            record, asset = self.assets._read_record(auth, revision)
            key = 'domain-asset-head:' + semantic_digest([
                auth.principal, record.payload['namespace'], record.payload['logical_id']])
            head = self.store.get('domain_asset_heads', key)
            if not head or head['revision'] != revision.model_dump(mode='json'):
                raise ValueError('KNOWLEDGE_WORK_DEPENDENCY_REVISION_CHANGED')
            fences.append(AtomicWrite('domain_asset_heads', key, head, head))
            pending.extend(dependency.revision for dependency in asset.dependencies)
        return tuple(fences)

    def _change_dependency_fences(self, auth, attempt, change, draft):
        if isinstance(draft, DomainAssetDraft):
            # An uncertain prior publication is restored through its original
            # idempotency identity. Its own revision may have superseded the
            # previous head; it must not be mistaken for a fresh publication.
            key = 'domain-asset-request:' + semantic_digest([
                auth.principal, semantic_digest([attempt['run_id'], change.change_id])])
            if (self.store.get('domain_asset_idempotency', key) or {}).get('response'):
                return ()
            refs = [dependency.revision for dependency in draft.dependencies]
        else:
            refs = list(change.dependencies)
        if change.target_revision is not None:
            refs.append(change.target_revision)
        return self._current_dependency_fences(auth, refs)

    def _save_change(self, auth, row, attempt, change, draft, dependency_fences=()):
        if not isinstance(draft, DomainAssetDraft):
            self._cas(AtomicWrite('agent_task_packages', row['task_package_id'], row, row),
                      *dependency_fences)
            return draft
        saved = self.assets.create(authorization=auth, request=DomainAssetCreateRequest(
            draft=draft, idempotency_key=semantic_digest([attempt['run_id'], change.change_id])),
            publication_fences=(AtomicWrite('agent_task_packages', row['task_package_id'], row, row),
                                *dependency_fences,
                                *self._selection_fences(auth, row)))
        from .catalog_search_index import readiness
        current_search = readiness(self.assets, auth, [RevisionRef.model_validate(saved['revision'])])['items'][0]
        return {'operation': change.operation, 'revision': saved['revision'], 'reason': change.reason,
                'projection_status': saved.get('projection_status', {'state': 'unavailable'}),
                'search_readiness_at_publication': current_search,
                'use_conditions': {'searchable': current_search['state'] == 'prepared',
                                   'searchable_basis': 'publication_time_index_observation; see status.search_readiness for current state',
                                   'explanation': 'source_bounded_candidate',
                                   'semantic_review': 'not_verified', 'computation': 'requires_native_checks'}}

    def _failed_submission(self, auth, row, attempt, error, *, partial_results=()):
        code = str(error)
        if not code.isascii() or not code.replace('_', '').isalnum() or len(code) > 120:
            code = 'KNOWLEDGE_WORK_RESULT_SCHEMA_INVALID'
        latest = self._read(auth, row['task_package_id'])
        if latest.get('active_attempt_ref') != attempt['run_id']:
            raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')
        failed = json.loads(json.dumps(latest))
        unit = next(u for u in failed['units'] if u['unit_id'] == attempt['unit_id'])
        unit.update(status='failed', summary=code, results=list(partial_results))
        status = 'stopped' if latest['status']=='stopped' else ('waiting_external_agent' if any(u['status']=='pending' for u in failed['units']) else 'needs_attention')
        failed.update(revision=latest['revision'] + 1, active_attempt_ref=None, status=status)
        invalid = {**attempt, 'state':'validation_failed', 'validation_error':code, 'published_results':list(partial_results)}
        self._cas(AtomicWrite('agent_task_packages', row['task_package_id'], latest, failed),
                  AtomicWrite('task_runs', attempt['run_id'], attempt, invalid))
        return {**self._view(failed), 'validation_error':code, 'failed_attempt_ref':attempt['run_id']}

    @staticmethod
    def _validate_accounting(attempt, result):
        if result.outcome != 'produced':
            return
        records = result.record_outcomes
        if len({r.record_locator for r in records}) != len(records) or {r.record_locator for r in records} != set(attempt['record_locators']):
            raise ValueError('KNOWLEDGE_WORK_RECORD_ACCOUNTING_INCOMPLETE')
        changes = {c.change_id for c in result.changes}
        unresolved = {c.change_id for c in result.changes if c.operation == 'unresolved'}
        used = set()
        for record in records:
            if not set(record.change_ids) <= changes:
                raise ValueError('KNOWLEDGE_WORK_RECORD_CHANGE_UNKNOWN')
            if record.disposition == 'assetized' and not record.change_ids:
                raise ValueError('KNOWLEDGE_WORK_RECORD_CHANGE_REQUIRED')
            if record.disposition == 'assetized' and set(record.change_ids) & unresolved:
                raise ValueError('KNOWLEDGE_WORK_UNRESOLVED_RECORD_NOT_ASSETIZED')
            used.update(record.change_ids)
        if used != changes:
            raise ValueError('KNOWLEDGE_WORK_CHANGE_RECORD_UNBOUND')

    def reconcile(self, *, authorization, request):
        req = KnowledgeWorkReconcile.model_validate(request)
        self._authorize(authorization, mutate=True)
        row = self._read(authorization, req.task_ref)
        self._valid_selection(authorization, row)
        old = self.store.get('task_runs', req.attempt_ref)
        if not old or old.get('task_ref') != req.task_ref or old.get('employee_id') != authorization.principal:
            raise ValueError('KNOWLEDGE_WORK_ATTEMPT_ACCESS_DENIED')
        if (old.get('result') or {}).get('outcome') != 'unknown':
            raise ValueError('KNOWLEDGE_WORK_RECONCILIATION_REQUIRES_UNKNOWN')
        identity = 'knowledge-recovery:' + semantic_digest([req.attempt_ref, req.idempotency_key])
        recovery_material = req.model_dump(mode='json')
        recovery_material['result'] = result_payload(req.result)
        fingerprint = semantic_digest(recovery_material)
        recovered = self.store.get('task_runs', identity)
        if recovered is not None:
            if recovered.get('recovery_digest') != fingerprint:
                raise ValueError('KNOWLEDGE_WORK_IDEMPOTENCY_CONFLICT')
        else:
            if req.expected_revision != row['revision'] or row.get('active_attempt_ref'):
                raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')
            if row['status'] == 'stopped':
                raise ValueError('KNOWLEDGE_WORK_STOPPED')
            updated = json.loads(json.dumps(row))
            unit = next(u for u in updated['units'] if u['unit_id'] == old['unit_id'])
            if unit['status'] != 'unknown':
                raise ValueError('KNOWLEDGE_WORK_RECONCILIATION_REQUIRES_UNKNOWN')
            if unit.get('reconciliations', 0) >= row['max_attempts_per_unit']:
                raise ValueError('KNOWLEDGE_WORK_BUDGET_EXHAUSTED')
            unit.update(status='awaiting_external_result', reconciliations=unit.get('reconciliations', 0) + 1)
            unit.setdefault('attempt_refs', []).append(identity)
            recovered = {k:v for k,v in old.items() if k not in ('submission_digest','submission_ref','result','raw_output_digest','published_results','updated_at')}
            recovered.update(run_id=identity, state='awaiting_external_result', recovered_from=req.attempt_ref,
                             recovery_digest=fingerprint, recovery_reason=req.recovery_reason)
            updated.update(active_attempt_ref=identity, revision=row['revision'] + 1)
            self._cas(AtomicWrite('agent_task_packages', req.task_ref, row, updated),
                      AtomicWrite('task_runs', identity, None, recovered), *self._selection_fences(authorization, row))
        submission = req.model_dump(mode='json', exclude={'expected_revision','recovery_reason'})
        return self.submit(authorization=authorization, request={**submission, 'attempt_ref':identity})

    def submit(self, *, authorization, request):
        req = KnowledgeWorkSubmit.model_validate(request)
        self._authorize(authorization, mutate=True)
        row = self._read(authorization, req.task_ref)
        attempt = self.store.get('task_runs', req.attempt_ref)
        if not attempt or attempt.get('employee_id') != authorization.principal or attempt.get('task_ref') != req.task_ref:
            raise ValueError('KNOWLEDGE_WORK_ATTEMPT_ACCESS_DENIED')
        fingerprint = semantic_digest({'result': result_payload(req.result), 'raw_output': req.raw_output})
        if attempt.get('submission_digest'):
            if attempt['submission_digest'] != fingerprint:
                raise ValueError('KNOWLEDGE_WORK_SUBMISSION_CONFLICT')
            if attempt['state'] == 'validation_failed':
                return {**self._view(row), 'replayed':True, 'validation_error':attempt['validation_error'], 'failed_attempt_ref':req.attempt_ref}
            if attempt['state'] == 'submitted':
                return {**self._view(row), 'replayed': True, 'submission_ref': attempt['submission_ref']}
        if row.get('active_attempt_ref') != req.attempt_ref:
            raise ValueError('KNOWLEDGE_WORK_ATTEMPT_NOT_ACTIVE')
        if row['status'] == 'stopped':
            raise ValueError('KNOWLEDGE_WORK_STOPPED')
        self._valid_selection(authorization, row)
        # Reserve the exact original output before any asset publication. A lost
        # response can only replay this body, never regenerate a different one.
        if not attempt.get('submission_digest'):
            self.objects.put(req.raw_output.encode('utf-8'))
            updated = {**attempt, 'state': 'submitting', 'submission_digest': fingerprint,
                       'result': result_payload(req.result), 'raw_output_digest': byte_digest(req.raw_output.encode('utf-8'))}
            self._cas(AtomicWrite('task_runs', req.attempt_ref, attempt, updated),
                      AtomicWrite('agent_task_packages', req.task_ref, row, row))
            attempt = self.store.get('task_runs', req.attempt_ref)
        try:
            self._validate_accounting(attempt, req.result)
            self._validate_revision_scope(authorization, row, attempt, req.result)
            for revision in req.result.existing_revisions_considered:
                self.assets._read_record(authorization, revision)
            prepared = []
            for change in req.result.changes:
                if change.target_revision and change.target_revision not in req.result.existing_revisions_considered:
                    raise ValueError('KNOWLEDGE_WORK_COMPARISON_REQUIRED')
                checks = {}
                change = self._expand_retained_change(authorization, row, change)
                draft = self._prepare_change(authorization, row, attempt, change, binding_checks=checks)
                prepared.append((change, draft, self._change_dependency_fences(authorization, attempt, change, draft), checks))
        except ValueError as exc:
            return self._failed_submission(authorization, row, attempt, exc)
        results = []
        try:
            for change, draft, fences, checks in prepared:
                saved = self._save_change(authorization, row, attempt, change, draft, fences)
                results.append({**saved, **({'binding_checks': checks} if checks else {})})
                saved_attempt = {**attempt, 'published_results': results}
                self._cas(AtomicWrite('task_runs', req.attempt_ref, attempt, saved_attempt))
                attempt = self.store.get('task_runs', req.attempt_ref)
            completion_fences = self._current_dependency_fences(authorization,
                [RevisionRef.model_validate(result['revision']) for result in results if result.get('revision')])
        except ValueError as exc:
            # Only a known contract rejection is repairable. Connection loss,
            # storage failure and uncertain commit retain the submitting state.
            return self._failed_submission(authorization, row, attempt, exc, partial_results=results)
        receipt = self.ledger.append(RecordKind.RUN, {
            'contract_version': 'boi/knowledge-work-submission@1', 'employee_id': authorization.principal,
            'policy_digest': authorization.policy_digest, 'task_ref': req.task_ref,
            'attempt_ref': req.attempt_ref, 'source_refs': row['sources'], 'package_selection': row['package_selection'],
            'submission_digest': fingerprint, 'raw_output_digest': attempt['raw_output_digest'],
            'result': result_payload(req.result), 'published_results': results,
            'semantic_verdict': 'not_verified'}, authority='executor', occurred_at=attempt['created_at'])
        updated = json.loads(json.dumps(row))
        unit = next(u for u in updated['units'] if u['unit_id'] == attempt['unit_id'])
        unit.update(status=req.result.outcome, summary=req.result.summary, results=results,
                    unresolved=list(req.result.unresolved), submission_ref=self._ref(receipt),
                    record_outcomes=[r.model_dump(mode='json') for r in req.result.record_outcomes],
                    revision_scope=req.result.revision_scope.model_dump(mode='json'),
                    revision_impact_review=req.result.revision_impact_review.model_dump(mode='json') if req.result.revision_impact_review else None,
                    revision_dependency_spans=list(dict.fromkeys([*attempt['source_span_refs'],
                        *(ref.ref for ref in req.result.revision_scope.context_spans),
                        *(ref.ref for change, _, _, _ in prepared for ref in change.evidence_spans)])))
        if req.result.revision_impact_review and req.result.revision_impact_review.disposition == 'unresolved':
            unit['unresolved'].append(req.result.revision_impact_review.reason)
        updated.update(revision=row['revision'] + 1, active_attempt_ref=None)
        pending = any(u['status'] == 'pending' for u in updated['units'])
        exceptions = any(u['status'] in ('failed', 'unknown', 'unresolved') or u.get('unresolved') or
                         any(r['disposition']=='unresolved' for r in u.get('record_outcomes', [])) for u in updated['units'])
        updated['status'] = 'waiting_external_agent' if pending else 'needs_attention' if exceptions else 'outputs_recorded'
        completed = {**attempt, 'state': 'submitted', 'submission_ref': self._ref(receipt), 'published_results': results}
        self._cas(AtomicWrite('agent_task_packages', req.task_ref, row, updated),
                  AtomicWrite('task_runs', req.attempt_ref, attempt, completed),
                  *completion_fences,
                  *self._selection_fences(authorization, row))
        return {**self._view(updated), 'submission_ref': self._ref(receipt)}

    def control(self, *, authorization, request, operation):
        req = KnowledgeWorkControl.model_validate(request)
        self._authorize(authorization, mutate=True)
        row = self._read(authorization, req.task_ref)
        idem = 'knowledge-control:' + semantic_digest([authorization.principal, req.task_ref, req.idempotency_key])
        fingerprint = semantic_digest([operation, req.model_dump(mode='json')])
        old = self.store.get('agent_task_idempotency', idem)
        if old:
            if old['fingerprint'] != fingerprint:
                raise ValueError('KNOWLEDGE_WORK_IDEMPOTENCY_CONFLICT')
            return self._view(row)
        if req.expected_revision != row['revision']:
            raise ValueError('KNOWLEDGE_WORK_REVISION_CONFLICT')
        updated = json.loads(json.dumps(row))
        if operation == 'stop':
            updated['status'] = 'stopped'
        else:
            self._valid_selection(authorization, row)
            if row.get('active_attempt_ref') or any(u['status'] == 'unknown' for u in row['units']):
                raise ValueError('KNOWLEDGE_WORK_UNKNOWN_REQUIRES_RECONCILIATION')
            eligible = [u for u in updated['units'] if u['status'] in ('failed', 'unresolved') or
                        (u['status'] == 'produced' and (u.get('unresolved') or
                         any(r['disposition'] == 'unresolved' for r in u.get('record_outcomes', []))))]
            if not eligible:
                raise ValueError('KNOWLEDGE_WORK_NO_RETRYABLE_UNIT')
            for u in eligible:
                if (u['attempts'] >= row['max_attempts_per_unit'] or
                        work_budget.remaining(self, authorization.principal, req.task_ref, u) <= 0):
                    raise ValueError('KNOWLEDGE_WORK_BUDGET_EXHAUSTED')
                u.update(status='pending', retry_requested_revision=row['revision'] + 1)
            updated['status'] = 'waiting_external_agent'
        updated['revision'] += 1
        updated.setdefault('control_history', []).append({'operation': operation, 'reason': req.reason,
                                                          'revision': updated['revision']})
        self._cas(AtomicWrite('agent_task_packages', req.task_ref, row, updated),
                  AtomicWrite('agent_task_idempotency', idem, None, {'employee_id': authorization.principal, 'fingerprint': fingerprint}))
        return self._view(updated)

    def dispatch(self, *, authorization, operation, request):
        if operation == 'schema':
            self._authorize(authorization)
            return {'contract_version': self.CONTRACT, 'schemas': {name: cls.model_json_schema() for name, cls in (
                ('start', KnowledgeWorkStart), ('next', KnowledgeWorkNext), ('submit', KnowledgeWorkSubmit),
                ('status', KnowledgeWorkRead), ('retry', KnowledgeWorkControl), ('stop', KnowledgeWorkControl), ('reconcile', KnowledgeWorkReconcile),
                ('context', KnowledgeWorkContext), ('output', KnowledgeWorkOutput))},
                'content_schemas': self._content_schemas()}
        if operation == 'list':
            self._authorize(authorization)
            if request:
                raise ValueError('KNOWLEDGE_WORK_LIST_ARGUMENTS_INVALID')
            values, after = [], ''
            while True:
                page = self.store.list_key_page('agent_task_packages', employee_id=authorization.principal, after_key=after, limit=100)
                for item in page:
                    row = item['value']
                    if row.get('contract_version') == self.CONTRACT:
                        values.append(self.status(authorization=authorization, request={'task_ref':row['task_package_id']}))
                if len(page) < 100:
                    break
                after = page[-1]['key']
            return {'items': values, 'total_count': len(values)}
        if operation in ('retry', 'stop'):
            return self.control(authorization=authorization, operation=operation, request=request)
        method = {'start': self.start, 'status': self.status, 'resume': self.status, 'next': self.next, 'submit': self.submit,
                  'reconcile':self.reconcile, 'context':self.context, 'output':self.output}.get(operation)
        if method is None:
            raise ValueError('KNOWLEDGE_WORK_OPERATION_INVALID')
        return method(authorization=authorization, request=request)

    @staticmethod
    def _content_schemas():
        from .common_knowledge_contract import CommonKnowledgeMeaning
        from .process_knowledge_contract import ProcessKnowledgeDraft
        return {'boi/common-meaning@1':CommonKnowledgeMeaning.model_json_schema(),
                'boi/process-meaning@1':ProcessKnowledgeDraft.model_json_schema()}
