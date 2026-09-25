"""Record external work and authenticated tool evidence in the existing Wiki stores.

No model, tool executable, broker consumer or workflow scheduler runs here.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json

from .domain_asset_store import DomainAssetStore, source_manifest_digest
from .domain_context_service import DomainContextService
from .domain_work_contract import (DomainHarnessContract, DomainToolReport, DomainWorkStartRequest,
    DomainToolPrepareRequest, DomainToolReadRequest, DomainToolInputRequest, DomainToolSubmitRequest,
    DomainToolEvidenceRequest, DomainWorkCompleteRequest, SourceWorkInput, AssetWorkInput, ProjectionWorkInput, ProposedWorkInput)
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import byte_digest
from .tool_execution_contract import ToolInvocation, ToolInputArtifact, verify_tool_execution


class DomainWorkService:
    CONTRACT = 'boi/domain-work-stage@1'

    def __init__(self, source_intake, *, principal_teams=(), trusted_executors=(), clock=None, packages=None):
        self.intake = source_intake
        self.assets = DomainAssetStore(source_intake)
        self.store, self.ledger, self.objects = source_intake.store, source_intake.ledger, source_intake.objects
        self.clock = clock or (lambda:datetime.now(timezone.utc))
        self.trusted_executors = tuple(trusted_executors)
        self.releases = {}
        for trust in self.trusted_executors:
            if not trust.revoked and trust.valid_from <= self.clock() < trust.valid_until:
                for release in trust.releases:
                    prior = self.releases.get(release.revision)
                    if prior is not None and prior != release:
                        raise ValueError('DOMAIN_TOOL_RELEASE_REGISTRY_AMBIGUOUS')
                    self.releases[release.revision] = release
        self.contexts = DomainContextService(source_intake,principal_teams=principal_teams,
            available_tools=frozenset(self.releases), packages=packages)

    def _mutation(self, authorization):
        self.intake._policy(authorization)
        if not {'store','derive','model_input'} <= set(authorization.allowed_uses):
            raise ValueError('DOMAIN_WORK_MUTATION_NOT_AUTHORIZED')

    def _context(self, authorization, contract, *, require_current=True):
        if contract.get('request_revision'):
            self.assets._read_record(authorization, RevisionRef.model_validate(contract['request_revision']))
        context = self.contexts.validate_reading(authorization=authorization,
            revision=RevisionRef.model_validate(contract['reading_ref']),sources=contract['sources'],require_current=require_current)
        if context.context_digest != contract['context_digest']:
            raise ValueError('DOMAIN_WORK_CONTEXT_CHANGED')
        reading = self.ledger.read(contract['reading_ref']['ref'])
        prepared = self.ledger.read(reading.payload['context_ref']['ref'])
        if contract.get('package_selection') != prepared.payload.get('package_selection'):
            raise ValueError('DOMAIN_WORK_PACKAGE_SELECTION_CHANGED')
        for item in contract['inputs']:
            if item['kind']=='knowledge_reading':
                self.contexts.validate_reading(authorization=authorization,revision=RevisionRef.model_validate(item['reading_ref']),
                    sources=contract['sources'],require_current=require_current)
        return context

    def _context_fences(self, authorization, contract):
        from ..v2.atomic_store_contract import AtomicWrite
        self._context(authorization,contract)
        readings=[contract['reading_ref'],*[item['reading_ref'] for item in contract['inputs']
            if item['kind']=='knowledge_reading']]
        fences={}
        from .task_context_reading import context_head_fence_revisions
        for revision in readings:
            reading=self.ledger.read(revision['ref'])
            prepared=self.ledger.read(reading.payload['context_ref']['ref'])
            context=self.contexts.validate_reading(authorization=authorization,
                revision=RevisionRef.model_validate(revision),sources=contract['sources'])
            selection = prepared.payload.get('package_selection')
            shared = self.contexts.shared_assets(authorization, selection)
            for fence in self.contexts.package_fences(authorization, selection):
                fences[(fence.collection, fence.key)] = fence
            scope_key,scope_row=self.assets.definition_catalog_state(authorization,prepared.payload['namespace'])
            fences[('domain_asset_catalogs',scope_key)]=AtomicWrite('domain_asset_catalogs',scope_key,scope_row,scope_row or {
                'employee_id':authorization.principal,'namespace':prepared.payload['namespace'],'epoch':0})
            current_heads=context_head_fence_revisions(context,preparation_version=prepared.payload['contract_version'])
            for asset in context.assets:
                if asset.authority != 'candidate' or asset.revision not in current_heads or asset.revision in shared:
                    continue
                record,_=self.assets._read_record(authorization,asset.revision)
                key='domain-asset-head:'+semantic_digest([authorization.principal,record.payload['namespace'],record.payload['logical_id']])
                head=self.store.get('domain_asset_heads',key)
                if not head or head['revision']!=asset.revision.model_dump(mode='json'):
                    raise ValueError('DOMAIN_WORK_CONTEXT_REVISION_CHANGED')
                fences[('domain_asset_heads',key)]=AtomicWrite('domain_asset_heads',key,head,head)
        return tuple(fences.values())

    def _package(self, authorization, task_id, *, lease_id=None, expected_revision=None, require_current=True):
        self.intake._policy(authorization)
        package = self.store.get('agent_task_packages',task_id)
        if not package or package.get('employee_id') != authorization.principal:
            raise ValueError('DOMAIN_WORK_ACCESS_DENIED')
        contract = package.get('domain_execution_contract')
        if (not isinstance(contract,dict) or contract.get('contract_version') != self.CONTRACT
                or semantic_digest(contract) != package.get('task_contract_checksum')):
            raise ValueError('DOMAIN_WORK_CONTRACT_INVALID')
        if expected_revision is not None and package['revision'] != expected_revision:
            raise ValueError('DOMAIN_WORK_REVISION_CONFLICT')
        if lease_id is not None:
            lease = package.get('lease') or {}
            if (package.get('status') not in ('claimed','running') or package.get('claimed_by') != authorization.principal
                    or lease.get('lease_id') != lease_id):
                raise ValueError('DOMAIN_WORK_ACTIVE_LEASE_REQUIRED')
            if datetime.fromisoformat(lease['expires_at']) <= self.clock():
                raise ValueError('DOMAIN_WORK_LEASE_EXPIRED')
        self._context(authorization,contract,require_current=require_current)
        return package

    def _input(self, authorization, spec, contract, context, *, task_revision=None):
        if spec['kind']=='knowledge_reading':
            reading_ref=RevisionRef.model_validate(spec['reading_ref'])
            knowledge=self.contexts.validate_reading(authorization=authorization,revision=reading_ref,sources=contract['sources'])
            from .tool_execution_contract import execution_json_bytes
            return reading_ref,execution_json_bytes({'reading_ref':reading_ref.model_dump(mode='json'),
                'context':knowledge.model_dump(mode='json')})
        if spec['kind']=='source_projection_bundle':
            from .domain_work_contract import ProjectionBundleWorkInput
            from .tool_execution_contract import execution_json_bytes
            item=ProjectionBundleWorkInput.model_validate(spec)
            if source_manifest_digest([p.source for p in item.projections])!=source_manifest_digest(contract['sources']):
                raise ValueError('DOMAIN_WORK_PROJECTION_BUNDLE_SOURCE_COVERAGE_MISMATCH')
            values=[]
            for projection in sorted(item.projections,key=lambda p:p.source.artifact_ref):
                _,raw=self._input(authorization,{'kind':'source_projection','name':item.name,
                    **projection.model_dump(mode='json')},contract,context,task_revision=task_revision)
                values.append(json.loads(raw))
            return task_revision,execution_json_bytes(values)
        if spec['kind'] == 'proposal':
            item=ProposedWorkInput.model_validate(spec)
            # The containing immutable task contract is this input's storage
            # revision. Named input/content digests distinguish its members.
            # start() validates before storage; prepare() supplies the revision.
            return task_revision,item.content_json.encode('utf-8')
        if spec['kind'] == 'source_projection':
            from .source_field_projection import SourceFieldProjectionService
            item = ProjectionWorkInput.model_validate(spec)
            source = item.source.model_dump(mode='json')
            if source not in contract['sources']:
                raise ValueError('DOMAIN_WORK_INPUT_SOURCE_OUTSIDE_TASK')
            self.assets.authorize_sources(authorization,(item.source,),model_input=True)
            manifest = self.ledger.read(item.manifest_revision.ref)
            body = manifest.payload
            if (manifest.kind != RecordKind.RUN or record_digest(manifest.record_id) != item.manifest_revision.revision_digest
                    or body.get('contract_version') != SourceFieldProjectionService.CONTRACT
                    or body.get('artifact_ref') != item.source.artifact_ref
                    or body.get('source_revision_digest') != item.source.digest
                    or body.get('employee_id') != authorization.principal or body.get('policy_digest') != authorization.policy_digest):
                raise ValueError('DOMAIN_WORK_PROJECTION_BINDING_DENIED')
            fields = []
            reader = SourceFieldProjectionService(self.intake)
            for field in body['fields']:
                offset, parts = 0, []
                while True:
                    page = reader.read_field(authorization=authorization,reference=source,span_ref=field['span_ref'],offset=offset,limit=8192)
                    parts.append(page['text'])
                    if page['next_offset'] is None:
                        break
                    offset = page['next_offset']
                text = ''.join(parts)
                if byte_digest(text.encode('utf-8')) != field['content_digest']:
                    raise ValueError('DOMAIN_WORK_PROJECTION_CONTENT_DRIFT')
                fields.append({**field,'text':text})
            from .tool_execution_contract import execution_json_bytes
            return item.manifest_revision, execution_json_bytes({'manifest':body,'source':source,'fields':fields})
        if spec['kind'] == 'source':
            source = SourceWorkInput.model_validate(spec).source
            if source.model_dump(mode='json') not in contract['sources']:
                raise ValueError('DOMAIN_WORK_INPUT_SOURCE_OUTSIDE_TASK')
            raw = self.intake.resolve_bytes(authorization=authorization,reference=source.model_dump(mode='json'))
            return RevisionRef(ref=source.artifact_ref,revision_digest=record_digest(source.artifact_ref)), raw
        entry = AssetWorkInput.model_validate(spec)
        selected = next((a for a in context.assets if a.revision == entry.revision),None)
        if selected is None:
            raise ValueError('DOMAIN_WORK_INPUT_REVISION_NOT_READ')
        return entry.revision, selected.content_json.encode('utf-8')

    def lookup_work(self, *, authorization, request):
        self.intake._policy(authorization)
        key='domain-task:'+semantic_digest([authorization.principal,request.idempotency_key])
        if self.store.get('agent_task_packages',key) is None:
            return {'found':False,'status':'PROVISIONAL'}
        return {'found':True,'package':self._package(authorization,key,require_current=False),'status':'PROVISIONAL'}

    def _request_budget_write(self, authorization, request, task_id, fingerprint):
        """Reserve a task in the existing task-idempotency store atomically.

        A new host/session cannot reset the request's counter, and a new pack
        revision cannot silently increase a previously admitted request limit.
        """
        from ..v2.atomic_store_contract import AtomicWrite
        from .domain_work_contract import DomainRequestStageBudget
        if request.request_revision is None:
            return ()  # Historical callers keep their exact contract/fingerprint.
        record, asset = self.assets._read_record(authorization, request.request_revision)
        if asset.kind != 'pack':
            raise ValueError('DOMAIN_WORK_REQUEST_BUDGET_PACK_REQUIRED')
        budget = DomainRequestStageBudget.model_validate_json(asset.content_json)
        source_refs = {semantic_digest(s) for s in record.payload['sources']}
        if any(semantic_digest(s.model_dump(mode='json')) not in source_refs for s in request.sources):
            raise ValueError('DOMAIN_WORK_REQUEST_SOURCE_OUTSIDE_BUDGET')
        key = 'domain-request-budget:' + semantic_digest([
            authorization.principal, record.payload['namespace'], record.payload['logical_id']])
        old = self.store.get('agent_task_idempotency', key)
        scope = {'contract_version':'boi/request-stage-budget-state@1',
            'employee_id':authorization.principal, 'request_revision':request.request_revision.model_dump(mode='json'),
            'policy_digest':authorization.policy_digest, 'max_stage_attempts':budget.max_stage_attempts}
        if old and any(old.get(k) != v for k, v in scope.items()):
            raise ValueError('DOMAIN_WORK_REQUEST_BUDGET_CHANGED')
        attempts = (old or {}).get('attempts', [])
        if any(a['task_package_id'] == task_id for a in attempts):
            raise ValueError('DOMAIN_WORK_REQUEST_TASK_PUBLICATION_INCOMPLETE')
        if len(attempts) >= budget.max_stage_attempts:
            raise ValueError('DOMAIN_WORK_REQUEST_STAGE_BUDGET_EXHAUSTED')
        return (AtomicWrite('agent_task_idempotency', key, old, {**scope, 'attempts':[*attempts, {
            'task_package_id':task_id, 'start_fingerprint':fingerprint}]}),)

    def start(self, *, authorization, request: DomainWorkStartRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        self._mutation(authorization)
        request = DomainWorkStartRequest.model_validate(request.model_dump(mode='python'))
        self.assets.authorize_sources(authorization,request.sources,model_input=True)
        key = 'domain-task:' + semantic_digest([authorization.principal,request.idempotency_key])
        wire_request = request.model_dump(mode='json')
        if request.request_revision is None:
            wire_request.pop('request_revision')
        fingerprint = semantic_digest(wire_request)
        existing = self.store.get('agent_task_packages',key)
        if existing:
            if existing.get('start_fingerprint') != fingerprint:
                raise ValueError('DOMAIN_WORK_IDEMPOTENCY_CONFLICT')
            return {**self._package(authorization,key,require_current=False),'replayed':True}
        context = self.contexts.validate_reading(authorization=authorization,revision=request.reading_ref,sources=request.sources)
        reading = self.ledger.read(request.reading_ref.ref)
        prepared = self.ledger.read(reading.payload['context_ref']['ref'])
        if prepared.payload.get('tool_use','execution') not in ('execution','selected_stage'):
            raise ValueError('DOMAIN_WORK_EXECUTION_CONTEXT_REQUIRED')
        harness = next((a for a in context.assets if a.revision == request.harness_revision and a.kind == 'harness'),None)
        if harness is None:
            raise ValueError('DOMAIN_WORK_HARNESS_NOT_READ')
        definition = DomainHarnessContract.model_validate_json(harness.content_json)
        stage = next((s for s in definition.stages if s.stage_id == request.stage_id),None)
        if stage is None:
            raise ValueError('DOMAIN_WORK_STAGE_UNDECLARED')
        selected = {a.revision:a for a in context.assets}
        for tool in stage.tools:
            if tool.tool_revision not in self.releases or tool.tool_revision not in selected or selected[tool.tool_revision].kind != 'tool':
                raise ValueError('DOMAIN_WORK_TOOL_NOT_AVAILABLE_IN_CONTEXT')
            if tool.input_kinds:
                actual={i.name:i.kind for i in request.inputs}
                actual['context']='context'
                if any(actual.get(name)!=kind for name,kind in tool.input_kinds.items()):
                    raise ValueError('DOMAIN_WORK_INPUT_ORIGIN_MISMATCH')
            # A candidate harness must not weaken a registered tool's origin
            # requirements. The tool asset revision is pinned by the trusted
            # executor release, unlike a new caller-authored harness.
            pinned_origins=json.loads(selected[tool.tool_revision].content_json).get('input_kinds')
            if pinned_origins is not None:
                from .domain_work_contract import StageToolRequirement
                declared=StageToolRequirement(tool_revision=tool.tool_revision,input_names=tool.input_names,
                    input_kinds=pinned_origins,checks=tool.checks)
                if not declared.input_kinds:raise ValueError('DOMAIN_TOOL_INPUT_ORIGINS_EMPTY')
                actual={i.name:i.kind for i in request.inputs};actual['context']='context'
                if any(actual.get(name)!=kind for name,kind in declared.input_kinds.items()):
                    raise ValueError('DOMAIN_WORK_PINNED_TOOL_INPUT_ORIGIN_MISMATCH')
        names = {name for t in stage.tools for name in t.input_names} - {'context'}
        if names != {i.name for i in request.inputs} or len(request.inputs) != len(names):
            raise ValueError('DOMAIN_WORK_INPUT_SET_MISMATCH')
        selection = prepared.payload.get('package_selection')
        shared = self.contexts.shared_assets(authorization, selection)
        if prepared.payload['namespace'] != definition.namespace and request.harness_revision not in shared:
            raise ValueError('DOMAIN_WORK_NAMESPACE_DEFINITION_SCOPE_MISMATCH')
        contract = {'contract_version':self.CONTRACT,'namespace':prepared.payload['namespace'],'harness_revision':request.harness_revision.model_dump(mode='json'),
            'stage':stage.model_dump(mode='json'),'sources':[s.model_dump(mode='json') for s in request.sources],
            'source_manifest_digest':source_manifest_digest(request.sources),'reading_ref':request.reading_ref.model_dump(mode='json'),
            'context_ref':reading.payload['context_ref'],'context_digest':context.context_digest,
            'policy_digest':authorization.policy_digest,'inputs':[i.model_dump(mode='json') for i in request.inputs]}
        if selection is not None:
            contract['package_selection'] = selection
            contract['harness_namespace'] = definition.namespace
        if request.request_revision is not None:
            contract['request_revision'] = request.request_revision.model_dump(mode='json')
        for spec in contract['inputs']:
            self._input(authorization,spec,contract,context)
        now = self.clock().isoformat()
        package = {'task_package_id':key,'employee_id':authorization.principal,'task_id':stage.stage_id,
            'task_run_id':'domain-task-run:'+semantic_digest(key),
            'task_ref':request.harness_revision.ref+'#'+stage.stage_id,'workflow_ref':request.harness_revision.ref,
            'goal':stage.purpose,'instructions':stage.instructions,'domain_execution_contract':contract,
            'task_contract_checksum':semantic_digest(contract),'start_fingerprint':fingerprint,
            'status':'available','current_state':'available','display_status':'PROVISIONAL',
            'executor_binding':'agent_claim','approval_required':False,'canonical_projection_eligible':False,
            'revision':1,'lease':{},'created_at':now,'updated_at':now,'state_history':[{'state':'available','at':now}]}
        task_run = {'task_run_id':package['task_run_id'],'task_package_id':key,'employee_id':authorization.principal,
            'task_ref':package['task_ref'],'workflow_ref':package['workflow_ref'],'goal':stage.purpose,
            'status':'available','current_state':'available','task_package_revision':1,'revision':1,
            'source':'domain_work_stage','display_status':'PROVISIONAL','context_ref':contract['context_ref'],
            'harness_revision':contract['harness_revision'],'created_at':now,'updated_at':now}
        for _ in range(3):
            # Budget and task are one CAS transaction. Conflicting admissions
            # may re-read state, but never dispatch or repeat external work.
            budget_writes = self._request_budget_write(authorization, request, key, fingerprint)
            if self.store.atomic_compare_and_write((AtomicWrite('agent_task_packages',key,None,package),
                    AtomicWrite('task_runs',package['task_run_id'],None,task_run),*budget_writes,
                    *self._context_fences(authorization,contract))):
                return {**package,'replayed':False}
            winner = self.store.get('agent_task_packages', key)
            if winner:
                if winner.get('start_fingerprint') != fingerprint:
                    raise ValueError('DOMAIN_WORK_IDEMPOTENCY_CONFLICT')
                return {**self._package(authorization,key,require_current=False),'replayed':True}
        raise ValueError('DOMAIN_WORK_PUBLICATION_CONFLICT')

    def prepare(self, *, authorization, request: DomainToolPrepareRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        self._mutation(authorization)
        package = self._package(authorization,request.task_package_id,lease_id=request.lease_id)
        contract = package['domain_execution_contract']
        key = 'tool-invocation:' + semantic_digest([authorization.principal,request.task_package_id,request.idempotency_key])
        fingerprint = semantic_digest(request.model_dump(mode='json'))
        stored = self.store.get('domain_tool_invocations',key)
        if stored:
            if stored['request_fingerprint'] != fingerprint:
                raise ValueError('DOMAIN_TOOL_IDEMPOTENCY_CONFLICT')
            return {**self.read(authorization=authorization,request=DomainToolReadRequest(invocation_id=key)),'replayed':True}
        if package['revision'] != request.expected_revision:
            raise ValueError('DOMAIN_WORK_REVISION_CONFLICT')
        requirement = next((t for t in contract['stage']['tools'] if t['tool_revision'] == request.tool_revision.model_dump(mode='json')),None)
        if requirement is None or request.tool_revision not in self.releases:
            raise ValueError('DOMAIN_WORK_TOOL_NOT_AUTHORIZED')
        context = self._context(authorization,contract)
        inputs, objects = [], {}
        selected=next(a for a in context.assets if a.revision==request.tool_revision)
        single_attempt=json.loads(selected.content_json).get('dispatch_policy')=='single_attempt'
        slot_key='tool-dispatch-slot:'+semantic_digest([authorization.principal,request.task_package_id,request.tool_revision.model_dump(mode='json')])
        slot=self.store.get('domain_tool_invocations',slot_key) if single_attempt else None
        if slot:
            previous=self.store.get('domain_tool_invocations',slot['invocation_id'])
            if not previous:raise ValueError('DOMAIN_TOOL_DISPATCH_SLOT_UNAVAILABLE')
            if previous.get('dispatch') or self.store.get('domain_tool_receipts',slot['invocation_id']):
                raise ValueError('DOMAIN_TOOL_PRIOR_DISPATCH_REQUIRES_RECONCILIATION')
            if previous['invocation']['lease_id']==request.lease_id:
                raise ValueError('DOMAIN_TOOL_ALREADY_PREPARED_FOR_LEASE')
        for name in requirement['input_names']:
            if name == 'context':
                revision, raw = RevisionRef.model_validate(contract['context_ref']), context.model_dump_json().encode('utf-8')
            else:
                spec = next(s for s in contract['inputs'] if s['name'] == name)
                revision, raw = self._input(authorization,spec,contract,context,
                    task_revision=RevisionRef(ref=request.task_package_id,revision_digest=package['task_contract_checksum']))
            inputs.append(ToolInputArtifact(name=name,revision=revision,content_digest=byte_digest(raw)))
            objects[name] = self.objects.put(raw)
        invocation = ToolInvocation(invocation_id=key,principal_id=authorization.principal,
            task_revision=RevisionRef(ref=request.task_package_id,revision_digest=package['task_contract_checksum']),
            run_id=package['work_run_id'],lease_id=request.lease_id,context_ref=contract['context_ref'],context_digest=context.context_digest,
            reading_ref=contract['reading_ref'],policy_digest=authorization.policy_digest,source_manifest_digest=context.source_manifest_digest,
            tool=self.releases[request.tool_revision],inputs=tuple(inputs),authorized_at=self.clock(),
            expires_at=datetime.fromisoformat(package['lease']['expires_at']))
        row = {'employee_id':authorization.principal,'request_fingerprint':fingerprint,'invocation':invocation.model_dump(mode='json'),
            'dispatch_policy':'single_attempt' if single_attempt else 'legacy',
            'input_objects':objects,'task_contract_checksum':package['task_contract_checksum']}
        slot_writes=() if not single_attempt else (AtomicWrite('domain_tool_invocations',slot_key,slot,
            {'employee_id':authorization.principal,'task_package_id':request.task_package_id,
                'tool_revision':request.tool_revision.model_dump(mode='json'),'invocation_id':key,
                'previous_invocations':[*((slot or {}).get('previous_invocations',[])),*([slot['invocation_id']] if slot else [])]}),)
        writes = (AtomicWrite('agent_task_packages',request.task_package_id,package,package),
            AtomicWrite('domain_tool_invocations',key,None,row),*slot_writes,*self._context_fences(authorization,contract))
        if not self.store.atomic_compare_and_write(writes):
            raise ValueError('DOMAIN_TOOL_INVOCATION_PUBLICATION_CONFLICT')
        return {'invocation':row['invocation'],'status':'PROVISIONAL','replayed':False}

    def _invocation(self, authorization, invocation_id):
        row = self.store.get('domain_tool_invocations',invocation_id)
        if not row or row.get('employee_id') != authorization.principal or 'invocation' not in row:
            raise ValueError('DOMAIN_TOOL_INVOCATION_ACCESS_DENIED')
        invocation = ToolInvocation.model_validate(row['invocation'])
        package = self._package(authorization,invocation.task_revision.ref,lease_id=invocation.lease_id)
        if (package['task_contract_checksum'] != invocation.task_revision.revision_digest
                or package['work_run_id'] != invocation.run_id or invocation.policy_digest != authorization.policy_digest
                or invocation.expires_at <= self.clock()):
            raise ValueError('DOMAIN_TOOL_INVOCATION_STALE')
        return row, invocation, package

    def read(self, *, authorization, request: DomainToolReadRequest):
        _, invocation, _ = self._invocation(authorization,request.invocation_id)
        return {'invocation':invocation.model_dump(mode='json'),'status':'PROVISIONAL'}

    def lookup(self, *, authorization, request):
        """Look up one declared tool slot without claiming or executing work."""
        package=self._package(authorization,request.task_package_id,require_current=False)
        if request.tool_revision.model_dump(mode='json') not in [t['tool_revision'] for t in package['domain_execution_contract']['stage']['tools']]:
            raise ValueError('DOMAIN_WORK_TOOL_NOT_AUTHORIZED')
        key='tool-dispatch-slot:'+semantic_digest([authorization.principal,request.task_package_id,request.tool_revision.model_dump(mode='json')])
        slot=self.store.get('domain_tool_invocations',key)
        if not slot and package['status']=='completed':
            # Older deterministic tools predate dispatch slots. Recover their
            # admitted output from the immutable completion, never rerun them.
            completion=self.ledger.read(package['completion_record_ref'])
            body=completion.payload
            if (completion.kind!=RecordKind.RUN or body.get('contract_version')!='boi/domain-stage-completion@1'
                    or body.get('employee_id')!=authorization.principal
                    or body.get('task_package_id')!=request.task_package_id
                    or body.get('task_contract')!=package['domain_execution_contract']):
                raise ValueError('DOMAIN_WORK_COMPLETION_BINDING_INVALID')
            found=[]
            for ref in body['execution_refs']:
                evidence=self.read_evidence(authorization=authorization,request=DomainToolEvidenceRequest(execution_ref=ref))
                invocation=evidence['execution']['signed_execution']['body']['invocation']
                if invocation['task_revision']['ref']!=request.task_package_id:raise ValueError('DOMAIN_WORK_COMPLETION_TASK_MISMATCH')
                if invocation['tool']['revision']==request.tool_revision.model_dump(mode='json'):found.append(ref)
            if len(found)!=1:raise ValueError('DOMAIN_WORK_COMPLETION_TOOL_EVIDENCE_MISSING')
            return {'state':'receipt_recorded','execution_ref':found[0],'status':'PROVISIONAL','acquired':False,
                'historical_completion_projection':True,'new_execution':False}
        if not slot:return {'state':'not_prepared','status':'PROVISIONAL','acquired':False}
        row=self.store.get('domain_tool_invocations',slot['invocation_id'])
        if not row or row.get('employee_id')!=authorization.principal:
            raise ValueError('DOMAIN_TOOL_DISPATCH_SLOT_UNAVAILABLE')
        receipt=self.store.get('domain_tool_receipts',slot['invocation_id'])
        invocation=ToolInvocation.model_validate(row['invocation'])
        if invocation.task_revision.ref!=request.task_package_id or invocation.task_revision.revision_digest!=package['task_contract_checksum']:
            raise ValueError('DOMAIN_TOOL_DISPATCH_SLOT_BINDING_MISMATCH')
        state='receipt_recorded' if receipt else 'prepared'
        if row.get('dispatch') and not receipt:
            state='in_flight' if invocation.expires_at>self.clock() and invocation.lease_id==package.get('lease',{}).get('lease_id') else 'external_result_unknown'
        return {'state':state,'invocation':invocation.model_dump(mode='json'),'dispatch':row.get('dispatch'),
            'execution_ref':receipt['revision'] if receipt else None,'previous_invocations':slot.get('previous_invocations',[]),
            'status':'PROVISIONAL','acquired':False}

    def dispatch(self, *, authorization, request):
        """Atomic one-time execution gate on the existing invocation row.

        Lost responses or a worker dying after acquisition leave an unknown
        external outcome. Repeating this call never grants execution twice.
        """
        from ..v2.atomic_store_contract import AtomicWrite
        self._mutation(authorization)
        row,invocation,package=self._invocation(authorization,request.invocation_id)
        if row.get('dispatch_policy')!='single_attempt':raise ValueError('DOMAIN_TOOL_DISPATCH_POLICY_REQUIRED')
        if row.get('dispatch') or self.store.get('domain_tool_receipts',request.invocation_id):
            return {'acquired':False,'state':'already_dispatched','invocation_id':request.invocation_id,'status':'PROVISIONAL'}
        dispatch={'at':self.clock().isoformat(),'lease_id':invocation.lease_id,'run_id':invocation.run_id,
            'task_contract_checksum':package['task_contract_checksum']}
        acquired=self.store.atomic_compare_and_write((AtomicWrite('domain_tool_invocations',request.invocation_id,row,{**row,'dispatch':dispatch}),
            AtomicWrite('agent_task_packages',package['task_package_id'],package,package),
            *self._context_fences(authorization,package['domain_execution_contract'])))
        return {'acquired':acquired,'state':'dispatch_acquired' if acquired else 'dispatch_conflict',
            'invocation_id':request.invocation_id,'status':'PROVISIONAL'}

    def read_input(self, *, authorization, request: DomainToolInputRequest):
        published=self.store.get('domain_tool_receipts',request.invocation_id)
        if published:
            # Audit/review of admitted bytes survives completion and lease
            # expiry, just like read_evidence. This does not authorize execution.
            evidence=self.read_evidence(authorization=authorization,
                request=DomainToolEvidenceRequest(execution_ref=published['revision']))
            invocation=ToolInvocation.model_validate(evidence['execution']['signed_execution']['body']['invocation'])
            row=self.store.get('domain_tool_invocations',request.invocation_id)
            if (invocation.invocation_id!=request.invocation_id or not row
                    or row.get('employee_id')!=authorization.principal
                    or row.get('invocation')!=invocation.model_dump(mode='json')):
                raise ValueError('DOMAIN_TOOL_HISTORICAL_INPUT_BINDING_MISMATCH')
        else:
            row, invocation, _ = self._invocation(authorization,request.invocation_id)
        artifact = next((i for i in invocation.inputs if i.name == request.name),None)
        if artifact is None:
            raise ValueError('DOMAIN_TOOL_INPUT_UNDECLARED')
        raw = self.objects.get(row['input_objects'][request.name])
        if byte_digest(raw) != artifact.content_digest:
            raise ValueError('DOMAIN_TOOL_INPUT_CONTENT_DRIFT')
        return {'input':artifact.model_dump(mode='json'),'content_b64':base64.b64encode(raw).decode('ascii'),
            'invocation_id':invocation.invocation_id,'status':'PROVISIONAL'}

    def submit(self, *, authorization, request: DomainToolSubmitRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        self._mutation(authorization)
        invocation_row, invocation, package = self._invocation(authorization,request.receipt.body.invocation.invocation_id)
        if invocation_row.get('dispatch_policy')=='single_attempt' and not invocation_row.get('dispatch'):
            raise ValueError('DOMAIN_TOOL_DISPATCH_NOT_ACQUIRED')
        try:
            output = base64.b64decode(request.output_b64,validate=True)
        except ValueError:
            raise ValueError('DOMAIN_TOOL_OUTPUT_ENCODING_INVALID') from None
        verified = verify_tool_execution(receipt=request.receipt,expected=invocation,output_bytes=output,
            trusted_executors=self.trusted_executors,at=self.clock())
        # Authentication is retained for failed runs as well. Completion checks
        # are inspected only for a completed, typed domain tool report.
        report = DomainToolReport.model_validate_json(output) if verified.outcome == 'completed' else None
        payload = {'contract_version':'boi/domain-tool-evidence@1','employee_id':authorization.principal,
            'policy_digest':authorization.policy_digest,'signed_execution':request.receipt.model_dump(mode='json'),
            'verification':verified.model_dump(mode='json'),'output_object_ref':self.objects.put(output),
            'report':report.model_dump(mode='json') if report else None,'status':'PROVISIONAL','task_complete':False}
        record = self.ledger.append(RecordKind.RUN,payload,authority='executor',occurred_at=request.receipt.body.finished_at.isoformat())
        ref = DomainAssetStore._ref(record).model_dump(mode='json')
        prior = self.store.get('domain_tool_receipts',invocation.invocation_id)
        row = {'employee_id':authorization.principal,'revision':ref,'receipt_digest':verified.receipt_digest}
        if prior and prior != {**row,**({'updated_at':prior['updated_at']} if 'updated_at' in prior else {})}:
            raise ValueError('DOMAIN_TOOL_RECEIPT_REPLAY_CONFLICT')
        if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_packages',package['task_package_id'],package,package),
                AtomicWrite('domain_tool_receipts',invocation.invocation_id,prior,row),
                *self._context_fences(authorization,package['domain_execution_contract']))):
            raise ValueError('DOMAIN_TOOL_RECEIPT_PUBLICATION_CONFLICT')
        return {'execution_ref':ref,'verification':verified.model_dump(mode='json'),'status':'PROVISIONAL','replayed':prior is not None}

    def read_evidence(self, *, authorization, request: DomainToolEvidenceRequest):
        record = self.ledger.read(request.execution_ref.ref)
        body = record.payload
        if (record.kind != RecordKind.RUN or record_digest(record.record_id) != request.execution_ref.revision_digest
                or body.get('contract_version') != 'boi/domain-tool-evidence@1'
                or body.get('employee_id') != authorization.principal or body.get('policy_digest') != authorization.policy_digest):
            raise ValueError('DOMAIN_TOOL_EVIDENCE_ACCESS_DENIED')
        from .tool_execution_contract import SignedToolExecution
        signed = SignedToolExecution.model_validate(body['signed_execution'])
        invocation = signed.body.invocation
        # Reading a completed run does not require an active lease and cannot
        # execute it again. Current source/context access is still required.
        self._package(authorization,invocation.task_revision.ref,require_current=False)
        published = self.store.get('domain_tool_receipts',invocation.invocation_id)
        if not published or published['revision'] != request.execution_ref.model_dump(mode='json'):
            raise ValueError('DOMAIN_TOOL_EVIDENCE_NOT_PUBLISHED')
        raw = self.objects.get(body['output_object_ref'])
        if byte_digest(raw) != signed.body.output_content_digest:
            raise ValueError('DOMAIN_TOOL_EVIDENCE_CONTENT_DRIFT')
        return {'execution_ref':request.execution_ref.model_dump(mode='json'),'execution':body,
            'output_json':raw.decode('utf-8'),'status':'PROVISIONAL','current_domain_verdict':'not_evaluated'}

    def complete(self, *, authorization, request: DomainWorkCompleteRequest):
        from ..v2.atomic_store_contract import AtomicWrite
        self._mutation(authorization)
        key = 'domain-complete:' + semantic_digest([authorization.principal,request.task_package_id,request.idempotency_key])
        fingerprint = semantic_digest(request.model_dump(mode='json'))
        replay = self.store.get('domain_work_completions',key)
        package = self._package(authorization,request.task_package_id,require_current=not bool(replay))
        if replay:
            if replay['request_fingerprint'] != fingerprint:
                raise ValueError('DOMAIN_WORK_IDEMPOTENCY_CONFLICT')
            return {**replay['response'],'replayed':True}
        package = self._package(authorization,request.task_package_id,lease_id=request.lease_id,expected_revision=request.expected_revision)
        contract = package['domain_execution_contract']
        reports = {}
        for ref in request.execution_refs:
            record = self.ledger.read(ref.ref)
            body = record.payload
            if record.kind != RecordKind.RUN or record_digest(record.record_id) != ref.revision_digest or body.get('contract_version') != 'boi/domain-tool-evidence@1':
                raise ValueError('DOMAIN_WORK_EXECUTION_REFERENCE_INVALID')
            from .tool_execution_contract import SignedToolExecution
            signed = SignedToolExecution.model_validate(body['signed_execution'])
            _, invocation, _ = self._invocation(authorization,signed.body.invocation.invocation_id)
            publication = self.store.get('domain_tool_receipts',invocation.invocation_id)
            if not publication or publication['revision'] != ref.model_dump(mode='json'):
                raise ValueError('DOMAIN_WORK_EXECUTION_NOT_PUBLISHED')
            if invocation.task_revision.ref != request.task_package_id or invocation.lease_id != request.lease_id:
                raise ValueError('DOMAIN_WORK_EXECUTION_TASK_MISMATCH')
            output = self.objects.get(body['output_object_ref'])
            verified = verify_tool_execution(receipt=signed,expected=invocation,output_bytes=output,
                trusted_executors=self.trusted_executors,at=self.clock())
            if verified.outcome != 'completed' or invocation.tool.revision in reports:
                raise ValueError('DOMAIN_WORK_EXECUTION_FAILED_OR_DUPLICATE')
            reports[invocation.tool.revision] = DomainToolReport.model_validate_json(output)
        required = {RevisionRef.model_validate(t['tool_revision']) for t in contract['stage']['tools']}
        if set(reports) != required:
            raise ValueError('DOMAIN_WORK_REQUIRED_EXECUTION_MISSING')
        for requirement in contract['stage']['tools']:
            checks = {c.check_id:c for c in reports[RevisionRef.model_validate(requirement['tool_revision'])].checks}
            if any(c['check_id'] not in checks or checks[c['check_id']].status not in c['accepted_statuses'] for c in requirement['checks']):
                raise ValueError('DOMAIN_WORK_REQUIRED_CHECK_UNSATISFIED')
        body = {'contract_version':'boi/domain-stage-completion@1','employee_id':authorization.principal,
            'task_package_id':request.task_package_id,'work_run_id':package['work_run_id'],'task_contract':contract,
            'execution_refs':[r.model_dump(mode='json') for r in request.execution_refs], 'summary':request.summary,
            'request_fingerprint':fingerprint,'status':'PROVISIONAL','completed_scope':'declared_harness_stage_checks',
            'domain_verdict':'not_evaluated','approved':False,'canonical_projection_eligible':False}
        # Stable timestamp permits exact recovery after a failed index write.
        completion = self.ledger.append(RecordKind.RUN,body,authority='migration_service',occurred_at=package['lease']['claimed_at'])
        result = {**package,'revision':package['revision']+1,'status':'completed','current_state':'completed',
            'completion_record_ref':completion.record_id,'display_status':'PROVISIONAL',
            'state_history':[*package.get('state_history',[]),{'state':'completed','at':self.clock().isoformat()}]}
        response = {**result,'completion_scope':'declared_harness_stage_checks','domain_verdict':'not_evaluated','replayed':False}
        row = {'employee_id':authorization.principal,'request_fingerprint':fingerprint,'response':response}
        task_run = self.store.get('task_runs',package['task_run_id'])
        if not task_run:
            raise ValueError('DOMAIN_WORK_TASK_RUN_MISSING')
        updated_run = {**task_run,'status':'completed','current_state':'completed',
            'revision':task_run['revision']+1,'task_package_revision':result['revision'],
            'completion_record_ref':completion.record_id,'updated_at':self.clock().isoformat()}
        if not self.store.atomic_compare_and_write((AtomicWrite('agent_task_packages',request.task_package_id,package,result),
                AtomicWrite('task_runs',package['task_run_id'],task_run,updated_run),
                AtomicWrite('domain_work_completions',key,None,row),*self._context_fences(authorization,contract))):
            raise ValueError('DOMAIN_WORK_COMPLETION_PUBLICATION_CONFLICT')
        return response
