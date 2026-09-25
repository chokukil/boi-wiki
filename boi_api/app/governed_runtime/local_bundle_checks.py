"""Confirmed native preparation -> durable server mechanical-check evidence.

Execution reservations survive failures. A saved completion can reconcile a
missing database acknowledgement; an unknown execution is never rerun here.
The external uploaded check file cannot supply this server's result.
"""
from datetime import datetime, timezone
import json

from .domain_asset_staging import StagedDomainAsset
from .immutable_io import publish_immutable
from .ledger import RecordKind, record_digest
from .local_bundle_import import LocalBundleImport
from .local_bundle_index import read_bundle_index
from .native_knowledge_checks import NativeKnowledgeChecks, shipped_checker_release
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite


CHECKS = 'knowledge_native_check_executions'


from .native_mechanical_records import NativeMechanicalRecords


class LocalBundleChecks(NativeMechanicalRecords):
    def __init__(self, importer):
        if not isinstance(importer, LocalBundleImport):
            raise ValueError('LOCAL_CHECK_NATIVE_IMPORT_REQUIRED')
        self.importer = importer
        self.store, self.intake = importer.store, importer.intake

    def _input(self, row, object_id, handle, release):
        return {'contract_version':'boi/native-mechanical-input@1',
            'employee_id':row['employee_id'], 'policy_digest':row['policy']['policy_digest'],
            'bundle_ref':row['bundle_ref'], 'manifest_digest':row['manifest_digest'],
            'confirmation_ref':self.importer.scope(row), 'object_id':object_id,
            'target_revision':handle.revision.model_dump(mode='json'),
            'intended_uses':row['manifest']['intended_uses'], 'checker_release_digest':semantic_digest(release)}

    def _context(self, auth, bundle_ref):
        row, fences = self.importer._context(auth, bundle_ref)
        # All local mapping is complete before checking. A check cannot turn an
        # incomplete bundle or unresolved local reference into a passing input.
        for summary in self.importer._summaries(row,(obj['object_id'] for obj in row['manifest']['objects'])).values():
            if summary is None:
                raise ValueError('LOCAL_CHECK_NATIVE_PREPARATION_REQUIRED')
        return row, fences

    def _handles(self, row):
        """Compact selection metadata; exact mappings are verified when read."""
        summaries=self.importer._summaries(row,(c['object_id'] for c in row['manifest']['changes']))
        handles={}
        for object_id,summary in summaries.items():
            if summary is None:
                raise ValueError('LOCAL_CHECK_NATIVE_PREPARATION_REQUIRED')
            staged=summary.get('staged')
            if staged is None:
                # Older imports remain readable without rewriting history.
                staged=self.importer._saved(row,object_id)['result']['staged']
            handle=StagedDomainAsset.model_validate(staged)
            if handle.scope_ref!=self.importer.scope(row):
                raise ValueError('LOCAL_CHECK_NATIVE_MAPPING_CHANGED')
            handles[object_id]=handle
        return handles

    def _reader(self, auth, row, handles=None):
        """Read only selected mapping receipts, target bytes and dependencies."""
        handles=self._handles(row) if handles is None else handles
        included={handle.revision:object_id for object_id,handle in handles.items()}
        if len(included)!=len(handles):
            raise ValueError('LOCAL_CHECK_NATIVE_MAPPING_CHANGED')
        from .semantic_binding_contract import RevisionRef
        allowed = {RevisionRef.model_validate(r) for r in row['manifest']['existing_revisions']}
        def read(ref):
            if ref in included:
                object_id=included[ref]
                saved=self.importer._saved(row,object_id)
                if (saved is None or StagedDomainAsset.model_validate(saved['result']['staged'])!=handles[object_id]):
                    raise ValueError('LOCAL_CHECK_NATIVE_MAPPING_CHANGED')
                return self.importer.stage.read(authorization=auth,scope_ref=self.importer.scope(row),revision=ref,model_input=False)
            if ref not in allowed:
                raise ValueError('LOCAL_CHECK_REFERENCE_OUTSIDE_CONFIRMED_BUNDLE')
            return self.importer.service.assets._read_record(auth,ref,model_input=False)
        identities={handle.native_identity:handle.revision for handle in handles.values()}
        if len(identities)!=len(handles):raise ValueError('LOCAL_CHECK_IDENTITY_MAPPING_CHANGED')
        external={}
        def resolve_identity(stable_id):
            if stable_id in identities:return identities[stable_id]
            from .knowledge_space_store import HEADS
            from .knowledge_profile_projector import native_identity
            head=self.store.get(HEADS,stable_id)
            if not head:raise ValueError('LOCAL_CHECK_IDENTITY_OUTSIDE_CONFIRMED_BUNDLE')
            revision=RevisionRef.model_validate(head['content_revision'])
            if revision not in allowed:raise ValueError('LOCAL_CHECK_IDENTITY_OUTSIDE_CONFIRMED_BUNDLE')
            record,_=read(revision)
            if native_identity(record)!=stable_id:raise ValueError('LOCAL_CHECK_IDENTITY_MAPPING_CHANGED')
            # The confirmed exact target must still be current and readable.
            # An existing readable historical revision is not the current type.
            state={(HEADS,stable_id):head,
                ('domain_asset_heads',stable_id):self.store.get('domain_asset_heads',stable_id),
                ('domain_knowledge_assets',revision.ref):self.store.get('domain_knowledge_assets',revision.ref)}
            if self.store.get(HEADS,stable_id)!=head or (stable_id in external and external[stable_id]!=state):
                raise ValueError('LOCAL_CHECK_IDENTITY_TARGET_CHANGED')
            external[stable_id]=state
            return revision
        def identity_fences():
            for stable_id in tuple(external):resolve_identity(stable_id)
            return tuple(AtomicWrite(collection,key,value,value) for state in external.values()
                for (collection,key),value in state.items())
        read.resolve_identity=resolve_identity
        read.identity_fences=identity_fences
        return read

    def _cas(self, auth, row, key, before, after):
        current, fences = self._context(auth,row['bundle_ref'])
        if current != row:
            raise ValueError('LOCAL_CHECK_CURRENT_CONTEXT_CHANGED')
        if not self.store.atomic_compare_and_write((*fences,AtomicWrite(CHECKS,key,before,after))):
            raise ValueError('LOCAL_CHECK_EXECUTION_STATE_CHANGED')

    def _one(self, auth, row, change, release, read_revision):
        imported = self.importer._saved(row,change['object_id'])
        handle = StagedDomainAsset.model_validate(imported['result']['staged'])
        binding = self._input(row,change['object_id'],handle,release)
        key = 'native-mechanical-execution:' + semantic_digest(binding)
        directory = self.importer.upload._directory(row['bundle_ref'],key)
        with self.importer.upload._locked(directory):
            self._context(auth,row['bundle_ref'])
            # Reuse is still a current exact authorized read, never a receipt-only
            # shortcut around withdrawn source access or damaged source bytes.
            read_revision(handle.revision)
            saved = self.store.get(CHECKS,key)
            if saved and saved.get('input') != binding:
                raise ValueError('LOCAL_CHECK_EXECUTION_BINDING_MISMATCH')
            marker = directory / 'completion.json'
            if marker.is_symlink():
                raise ValueError('LOCAL_CHECK_COMPLETION_STORAGE_INVALID')
            if saved and saved['state'] == 'completed':
                return self._current_result(read_revision,change,key,saved,binding)
            if saved and marker.exists():
                if marker.stat().st_size > 65536:
                    raise ValueError('LOCAL_CHECK_COMPLETION_STORAGE_INVALID')
                completed = json.loads(marker.read_bytes())
                self._receipt(completed,binding)
                if completed['run_ref'] != saved['run_ref']:
                    raise ValueError('LOCAL_CHECK_EXECUTION_BINDING_MISMATCH')
                self._cas(auth,row,key,saved,completed)
                return self._current_result(read_revision,change,key,completed,binding)
            if saved:
                return {'object_id':change['object_id'],'execution_ref':key,'state':'execution_unknown',
                    'run_ref':saved['run_ref'], 'retry_performed':False, 'query_ready':False}
            if marker.exists():
                raise ValueError('LOCAL_CHECK_ORPHAN_COMPLETION_REQUIRES_RECONCILIATION')
            occurred = datetime.now(timezone.utc).isoformat()
            run = self.intake.ledger.append(RecordKind.RUN,binding,authority='executor',occurred_at=occurred)
            saved = {'employee_id':auth.principal,'input':binding,'state':'reserved','run_ref':run.record_id,'started_at':occurred}
            self._cas(auth,row,key,None,saved)
            saved = self.store.get(CHECKS,key)
            if not saved or saved.get('input') != binding or saved.get('state') != 'reserved' or saved.get('run_ref') != run.record_id:
                raise ValueError('LOCAL_CHECK_EXECUTION_STATE_CHANGED')
            runner = NativeKnowledgeChecks(read_revision=read_revision,
                ledger=self.intake.ledger,objects=self.intake.objects,release=release)
            report = runner.run(revision=handle.revision,confirmation_ref=self.importer.scope(row),
                intended_uses=row['manifest']['intended_uses'])
            receipt = self.intake.ledger.append(RecordKind.CHECK,{'input':binding,'run_ref':run.record_id,'report':report},
                authority='qualification_service',occurred_at=datetime.now(timezone.utc).isoformat())
            completed = {**saved,'state':'completed','check_ref':{'ref':receipt.record_id,'revision_digest':record_digest(receipt.record_id)},
                         'payload_digest':semantic_digest(receipt.payload)}
            raw = json.dumps(completed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            if not publish_immutable(marker,raw) and marker.read_bytes() != raw:
                raise ValueError('LOCAL_CHECK_COMPLETION_CONFLICT')
            self._cas(auth,row,key,saved,completed)
            return self._current_result(read_revision,change,key,completed,binding)

    def validate(self, *, authorization, bundle_ref, limit=1, object_id=None):
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError('LOCAL_CHECK_STEP_LIMIT')
        row, _ = self._context(authorization,bundle_ref)
        handles = self._handles(row)
        read_revision = self._reader(authorization,row,handles)
        release = shipped_checker_release()
        changes = row['manifest']['changes']
        if object_id is not None:
            changes = [c for c in changes if c['object_id'] == object_id]
            if not changes:
                raise ValueError('LOCAL_CHECK_OBJECT_UNAVAILABLE')
        results, reused, unknowns, remaining, counts = [], [], [], 0, {}
        response_limit = limit
        recoveries = limit
        bindings = {c['object_id']:self._input(row,c['object_id'],handles[c['object_id']],release) for c in changes}
        keys = {object_id:'native-mechanical-execution:' + semantic_digest(binding) for object_id,binding in bindings.items()}
        executions = read_bundle_index(self.store,CHECKS,keys.values())
        for change in changes:
            binding = bindings[change['object_id']]
            key = keys[change['object_id']]
            saved = executions.get(key)
            if saved and saved.get('input') != binding:
                raise ValueError('LOCAL_CHECK_EXECUTION_BINDING_MISMATCH')
            if saved and saved.get('state') not in ('reserved','completed'):
                raise ValueError('LOCAL_CHECK_EXECUTION_STATE_CHANGED')
            if saved and saved['state'] == 'completed':
                if saved.get('input') != binding:
                    raise ValueError('LOCAL_CHECK_EXECUTION_BINDING_MISMATCH')
                if len(reused) < response_limit:
                    reused.append((change,key,saved,binding))
                # This counts stored completion records only, never passing
                # results. Full reports and current native/source bytes are
                # revalidated for the bounded items actually returned below.
                counts['recorded'] = counts.get('recorded',0) + 1
                continue
            elif saved and not (self.importer.upload._directory(row['bundle_ref'],key) / 'completion.json').exists():
                # A missing completion is an unknown execution, not queued work.
                # Do not consume the budget or reread all its source bytes on
                # every batch poll. This builtin has no dependency on another
                # check's result; it checks its own native dependencies. Any use
                # qualification still requires that target's completed check.
                counts['execution_unknown'] = counts.get('execution_unknown',0) + 1
                if len(unknowns) < response_limit:
                    unknowns.append({'object_id':change['object_id'],'execution_ref':key,'state':'execution_unknown',
                        'run_ref':saved['run_ref'],'retry_performed':False,'query_ready':False})
                continue
            elif (saved and recoveries) or (not saved and limit):
                result = self._one(authorization,row,change,release,read_revision)
                if result['state'] == 'execution_unknown':
                    if len(unknowns) < response_limit:
                        unknowns.append(result)
                else:
                    if len(results) < response_limit:
                        results.append(result)
                    if saved:
                        recoveries -= 1
                    else:
                        limit -= 1
            else:
                remaining += 1
                continue
            state = 'recorded' if result['state'] == 'completed' else result['state']
            counts[state] = counts.get(state,0) + 1
        for change,key,saved,binding in reused[:response_limit-len(results)]:
            results.append(self._current_result(read_revision,change,key,saved,binding))
        if object_id is not None and not results:
            results = unknowns[:response_limit]
        self._context(authorization,bundle_ref)
        if release != shipped_checker_release():
            raise ValueError('NATIVE_CHECK_RELEASE_CHANGED')
        return {'bundle_ref':bundle_ref,'confirmation_ref':self.importer.scope(row),
            'items':results,'remaining':remaining,'execution_record_counts':counts,
            'unknown_items':unknowns,'unknown_items_truncated':counts.get('execution_unknown',0) > len(unknowns),
            'item_details':'Select object_id to read any exact item again without re-executing it.',
            'state':'mechanical_execution_unknown' if counts.get('execution_unknown') else
                    'mechanical_checks_recorded_requires_qualification' if not remaining else 'mechanical_checks_partial',
            'publication_committed':False,'query_ready':False,'semantic_status':'not_evaluated'}
