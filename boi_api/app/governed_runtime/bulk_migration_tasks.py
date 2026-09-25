"""Lease controls for the existing bulk TaskPackage, shared by every channel.

Control uses the existing agent-task states; Skill check/Harness state stays in
the original stage fields. A submitted worker output is untrusted candidate data,
never an evaluator result, approval, SQL execution or Release.
"""
from datetime import datetime, timedelta, timezone
from dataclasses import asdict, dataclass
from .bulk_migration import AgentV2StoreBulkMigrationRepository, BulkMigrationPolicyError, _digest, stage_receipt_contract_valid
from .bulk_migration_transaction import MigrationWriteSet
from .bulk_migration_execution import (
    P0_B3_PIPELINE_V2, SEMANTIC_METADATA_PIPELINE_V1, INTAKE_CHECKPOINT_PIPELINE_V1, _safe_value,
)
from .semantic_binding_contract import FrozenContract, Digest
from pydantic import model_validator
from typing import Literal

EXECUTOR_LEASE_SECONDS=1800


class BoundedStageProposal(FrozenContract):
    contract_version: Literal['boi/bounded-stage-proposal@1']
    input_digest: Digest
    output: dict
    output_digest: Digest

    @model_validator(mode='after')
    def exact_output(self):
        _safe_value(self.output)
        if _digest(self.output)!=self.output_digest:raise ValueError('BULK_WORKER_OUTPUT_DIGEST_MISMATCH')
        return self


class BulkMigrationTaskService:
    def __init__(self, store, *, clock=None):
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _load(self, store, principal, task_id):
        task = store.get('bulk_migration_task_packages', task_id)
        if not task or task.get('employee_id') != principal:
            raise BulkMigrationPolicyError('BULK_TASK_ACCESS_DENIED')
        repository = AgentV2StoreBulkMigrationRepository(store)
        run = repository.get(task['run_id'])
        if not run or run.principal != principal:
            raise BulkMigrationPolicyError('BULK_TASK_RUN_ACCESS_DENIED')
        project = store.get('bulk_migration_projects',run.project_id)
        if not project or project.get('employee_id') != principal:
            raise BulkMigrationPolicyError('BULK_TASK_PROJECT_ACCESS_DENIED')
        manifest = repository.manifest_payload(run)
        if task.get('skill_id') not in manifest.get('requested_skill_stages', ()):
            raise BulkMigrationPolicyError('BULK_TASK_SKILL_CLOSURE_INVALID')
        shard = next((item for item in run.shards if item.shard_id == task.get('shard_id')), None)
        if shard is None or task.get('input_fingerprint') != _digest({
            'shard_input_fingerprint':shard.input_fingerprint,
            'skill_id':task['skill_id'],'manifest_digest':run.manifest_digest}):
            raise BulkMigrationPolicyError('BULK_TASK_INPUT_FINGERPRINT_STALE')
        return task, run, manifest, shard

    def _status(self, task, run):
        if task.get('state') == 'pass':
            return 'completed'
        if run.control_state == 'cancelled':
            return 'cancelled'
        executor=task.get('executor_lease') or {}
        if executor and datetime.fromisoformat(executor['expires_at'])>self.clock():return 'running'
        status = task.get('task_status', 'available')
        lease = task.get('lease') or {}
        if status in {'claimed','running'}:
            try:
                expiry = datetime.fromisoformat(lease['expires_at'])
                if expiry.tzinfo is None:raise ValueError()
            except (ValueError,KeyError,TypeError) as error:
                raise BulkMigrationPolicyError('BULK_TASK_LEASE_RECORD_INVALID') from error
            if expiry <= self.clock():
                return 'expired'
        return status

    def reserve_execution(self, principal, run_id, shard_id):
        """Reserve the existing TaskPackages, not a second worker/run ledger.

        A live external worker lease defers this shard without cancelling it.
        The atomic reservation is also the final-write fence, so a stale worker,
        cancellation or another executor cannot publish qualified stage results.
        """
        buffer=MigrationWriteSet(self.store)
        repository=AgentV2StoreBulkMigrationRepository(buffer)
        run=repository.get(run_id)
        if not run or run.principal!=principal:raise BulkMigrationPolicyError('BULK_TASK_RUN_ACCESS_DENIED')
        shard=next((s for s in run.shards if s.shard_id==shard_id),None)
        if not shard or shard.state!='queued' or run.control_state not in {'queued','running','failed'}:
            raise BulkMigrationPolicyError('BULK_TASK_RUN_NOT_EXECUTABLE')
        manifest=repository.manifest_payload(run);tasks={};now=self.clock()
        for skill in manifest['requested_skill_stages']:
            task_id=f"taskpkg:{shard_id.split(':',1)[-1]}:{skill}"
            task,_,_,_=self._load(buffer,principal,task_id)
            status=self._status(task,run)
            if status in {'claimed','running','cancelled'}:return None
            lease=task.get('executor_lease') or {}
            if lease and datetime.fromisoformat(lease['expires_at'])>now:return None
            tasks[skill]={k:v for k,v in task.items() if k!='updated_at'}
        lease_id='execution:'+_digest({'run_id':run_id,'shard_id':shard_id,
            'task_snapshot':tasks,'at':now.isoformat()})
        reserved={}
        for skill,task in tasks.items():
            reserved[skill]={**task,'expected_revision':int(task.get('expected_revision') or 1)+1,
                'executor_lease':{'lease_id':lease_id,'expires_at':(now+timedelta(seconds=EXECUTOR_LEASE_SECONDS)).isoformat(),
                    'manifest_digest':run.manifest_digest,'shard_input_fingerprint':shard.input_fingerprint,
                    'retry_count':shard.retry_count}}
            buffer.put('bulk_migration_task_packages',task['task_package_id'],reserved[skill])
        reservation={'receipt_kind':'TaskExecutionReservation','contract_version':'boi/task-execution-reservation@1',
            'employee_id':principal,'run_id':run_id,'shard_id':shard_id,'manifest_digest':run.manifest_digest,
            'lease_id':lease_id,'recorded_at':now.isoformat(),
            'task_snapshot_digest':_digest(reserved),'production_changed':False,'active_transition':False}
        ref=_digest(reservation)
        buffer.put('bulk_migration_receipts',ref,{**reservation,'receipt_digest':ref})
        fences=tuple(key for key,value in buffer.before.items() if value is not None)
        if not self.store.atomic_compare_and_write(buffer.writes(fences=fences)):return None
        return BulkTaskExecution(self,principal,run_id,shard_id,run.manifest_digest,reserved)

    def view(self, principal, task_id):
        task,run,manifest,shard = self._load(self.store,principal,task_id)
        # Never emit a stored untrusted worker body or source bytes to discovery.
        value = {k:v for k,v in task.items() if k not in {'submission','updated_at'}}
        return {**value,'resource_kind':'bulk_migration_task_package',
            'status':self._status(task,run),'revision':int(task.get('expected_revision') or 1),
            'stage_check_status':task.get('state','queued'),
            'candidate_state':shard.candidate_state,'manifest_digest':run.manifest_digest,
            'ui_url':run.ui_url,'classification':'PROVISIONAL',
            'allowed_skills':[task['skill_id']],'allowed_connectors':[],
            'execution_authority':'bounded_candidate_submission',
            'submission_contract':BoundedStageProposal.model_json_schema(),
            'forbidden_actions':['sql_compile','db_execute','attestation','verdict',
                                 'approval','release','activation'],
            'production_changed':False,'active_transition':False}

    def _dependencies(self, buffer, task, run, manifest, shard):
        contracts = {c.contract_id:c for c in (P0_B3_PIPELINE_V2,SEMANTIC_METADATA_PIPELINE_V1,
                                               INTAKE_CHECKPOINT_PIPELINE_V1)}
        contract = contracts.get(manifest.get('pipeline_contract_id'))
        stages = tuple(manifest.get('requested_skill_stages') or ())
        if contract:
            dependencies = contract.dependencies.get(task['skill_id'], ())
        elif manifest.get('pipeline_contract_id') == 'boi/legacy-bulk-pipeline@0.1.0':
            dependencies = stages[:stages.index(task['skill_id'])]
        else:
            raise BulkMigrationPolicyError('BULK_TASK_PIPELINE_CONTRACT_UNSUPPORTED')
        for stage in dependencies:
            ref = shard.stage_receipt_refs.get(stage)
            receipt = buffer.get('bulk_migration_stage_results',ref) if ref else None
            body = {k:v for k,v in (receipt or {}).items() if k not in {'updated_at','stage_receipt_digest'}}
            if (not receipt or _digest(body) != ref or receipt.get('status') != 'pass'
                or not stage_receipt_contract_valid(receipt)
                or receipt.get('skill_id') != stage or shard.stage_states.get(stage) != 'pass'
                or any(not receipt.get(key) for key in ('evidence_digest','input_digest','output_digest'))
                or receipt.get('run_id') != run.run_id or receipt.get('shard_id') != shard.shard_id
                or receipt.get('employee_id') != run.principal
                or receipt.get('attempt_digest') != shard.last_attempt_digest):
                raise BulkMigrationPolicyError('BULK_TASK_DEPENDENCY_NOT_PASS')

    def control(self, principal, task_id, operation, request):
        if operation not in {'claim','heartbeat','submit','release','cancel'}:
            raise BulkMigrationPolicyError('BULK_TASK_CONTROL_UNSUPPORTED')
        buffer = MigrationWriteSet(self.store)
        task,run,manifest,shard = self._load(buffer,principal,task_id)
        revision = int(task.get('expected_revision') or 1)
        parameters = request.model_dump(mode='json')
        fingerprint = _digest({'operation':operation,'input_fingerprint':task['input_fingerprint'],
                               'request':parameters})
        replay_key = None
        if parameters.get('idempotency_key'):
            replay_key = 'bulk-task:' + _digest({'task':task_id,'operation':operation,
                                               'key':parameters['idempotency_key']})
            old = buffer.get('agent_task_idempotency',replay_key)
            if old:
                if old.get('employee_id') != principal or old.get('input_fingerprint') != fingerprint:
                    raise BulkMigrationPolicyError('BULK_TASK_IDEMPOTENCY_CONFLICT')
                return {**old['response'],'replayed':True,'current_task_status':self._status(task,run)}
        if request.expected_revision != revision:
            raise BulkMigrationPolicyError('BULK_TASK_REVISION_CONFLICT')
        executor_lease=task.get('executor_lease') or {}
        if executor_lease and datetime.fromisoformat(executor_lease['expires_at'])>self.clock():
            raise BulkMigrationPolicyError('BULK_TASK_EXECUTOR_LEASE_ACTIVE')
        if run.control_state not in {'queued','running'} or shard.state in {'completed','failed'}:
            raise BulkMigrationPolicyError('BULK_TASK_RUN_NOT_EXECUTABLE')
        status = self._status(task,run)
        now = self.clock()
        updated = {**task,'control_contract_version':'boi/bulk-task-control@0.2.0',
                   'expected_revision':revision+1}
        if operation == 'claim':
            if status not in {'available','released','expired'}:
                raise BulkMigrationPolicyError('BULK_TASK_NOT_AVAILABLE')
            self._dependencies(buffer,task,run,manifest,shard)
            updated.update(task_status='claimed',lease={
                'lease_id':'lease:'+_digest({'task':task_id,'revision':revision,'request':fingerprint}),
                'claimed_at':now.isoformat(),'heartbeat_at':now.isoformat(),
                'expires_at':(now+timedelta(seconds=request.lease_seconds)).isoformat()})
        elif operation == 'cancel':
            if status == 'completed':
                raise BulkMigrationPolicyError('BULK_TASK_ALREADY_COMPLETED')
            updated.update(task_status='cancelled',stop_reason='USER_CANCELLED')
        else:
            lease = task.get('lease') or {}
            if status not in {'claimed','running'} or lease.get('lease_id') != request.lease_id:
                raise BulkMigrationPolicyError('BULK_TASK_LEASE_INVALID_OR_EXPIRED')
            if operation == 'heartbeat':
                updated.update(task_status='running',lease={**lease,'heartbeat_at':now.isoformat(),
                    'expires_at':(now+timedelta(seconds=request.extend_seconds)).isoformat()})
            elif operation == 'release':
                updated.update(task_status='released',lease={})
            else:
                from .semantic_inference_cache import canonical
                if len(canonical(request.result)) > 11264:
                    raise BulkMigrationPolicyError('BULK_TASK_SUBMISSION_BYTE_LIMIT')
                _safe_value(request.result)
                allowed = set(run.evidence_refs) | {source['artifact_ref'] for source in manifest['source_artifacts']}
                if not request.evidence_refs or set(request.evidence_refs) - allowed:
                    raise BulkMigrationPolicyError('BULK_TASK_EVIDENCE_CLOSURE_INVALID')
                submission = {'output':request.result,'evidence_refs':request.evidence_refs,
                    'input_fingerprint':task['input_fingerprint'],'manifest_digest':run.manifest_digest,
                    'skill_id':task['skill_id'],'classification':'PROVISIONAL'}
                updated.update(task_status='harness_verifying',submission=submission,
                    submission_digest=_digest(submission))
                preserved={'receipt_kind':'TaskSubmissionRecord','contract_version':'boi/task-submission@1',
                    'employee_id':principal,'run_id':run.run_id,'shard_id':shard.shard_id,
                    'task_package_id':task_id,'submission':submission,
                    'submission_digest':updated['submission_digest'],'production_changed':False,'active_transition':False}
                ref='task-submission:'+_digest(preserved)
                previous=buffer.get('bulk_migration_receipts',ref)
                if previous and {k:v for k,v in previous.items() if k!='updated_at'}!=preserved:
                    raise BulkMigrationPolicyError('BULK_WORKER_SUBMISSION_HISTORY_DRIFT')
                buffer.put('bulk_migration_receipts',ref,preserved)
                updated['submission_record_ref']=ref
        # A worker's control operation never changes stage check/evidence or Harness state.
        receipt_body = {'receipt_kind':'TaskControlReceipt',
            'contract_version':'boi/bulk-task-control-receipt@0.2.0',
            'employee_id':principal,'run_id':run.run_id,'shard_id':shard.shard_id,
            'task_package_id':task_id,'operation':operation,'input_fingerprint':fingerprint,
            'before_revision':revision,'after_revision':revision+1,
            'before_digest':_digest({k:v for k,v in task.items() if k!='updated_at'}),
            'after_digest':_digest({k:v for k,v in updated.items() if k!='updated_at'}),
            'recorded_at':now.isoformat(),'classification':'PROVISIONAL',
            'stage_check_status':task.get('state','queued'),
            'production_changed':False,'active_transition':False}
        receipt_digest = _digest(receipt_body)
        if buffer.get('bulk_migration_receipts',receipt_digest) is not None:
            raise BulkMigrationPolicyError('BULK_TASK_CONTROL_RECEIPT_CONFLICT')
        buffer.put('bulk_migration_receipts',receipt_digest,{**receipt_body,'receipt_digest':receipt_digest})
        updated['last_control_receipt_digest'] = receipt_digest
        buffer.put('bulk_migration_task_packages',task_id,updated)
        response = BulkMigrationTaskService(buffer,clock=self.clock).view(principal,task_id)
        response['replayed'] = False
        if replay_key:
            buffer.put('agent_task_idempotency',replay_key,{'employee_id':principal,
                'task_package_id':task_id,'operation':operation,'input_fingerprint':fingerprint,
                'response':response})
        fences = tuple(key for key,value in buffer.before.items() if value is not None)
        if not self.store.atomic_compare_and_write(buffer.writes(fences=fences)):
            raise BulkMigrationPolicyError('BULK_TASK_REVISION_CONFLICT')
        return response


@dataclass
class BulkTaskExecution:
    service: BulkMigrationTaskService
    principal: str
    run_id: str
    shard_id: str
    manifest_digest: str
    tasks: dict
    final_write_validator: object = None

    def validate_into(self,store):
        run=AgentV2StoreBulkMigrationRepository(store).get(self.run_id)
        if (not run or run.principal!=self.principal or run.manifest_digest!=self.manifest_digest
            or run.control_state not in {'queued','running','failed'}):
            raise BulkMigrationPolicyError('BULK_TASK_EXECUTION_RUN_STALE')
        shard=next((s for s in run.shards if s.shard_id==self.shard_id),None)
        if not shard or shard.state!='queued':raise BulkMigrationPolicyError('BULK_TASK_EXECUTION_SHARD_STALE')
        for task in self.tasks.values():
            actual=store.get('bulk_migration_task_packages',task['task_package_id'])
            if not actual or {k:v for k,v in actual.items() if k!='updated_at'}!=task:
                raise BulkMigrationPolicyError('BULK_TASK_EXECUTION_REVISION_CONFLICT')
            lease=task['executor_lease']
            if (datetime.fromisoformat(lease['expires_at'])<=self.service.clock()
                or lease['retry_count']!=shard.retry_count or lease['shard_input_fingerprint']!=shard.input_fingerprint):
                raise BulkMigrationPolicyError('BULK_TASK_EXECUTION_LEASE_EXPIRED')

    def before_stage(self,skill_id):
        # Renew only the exact held task snapshot; do not resurrect a cancelled,
        # expired or re-claimed execution. Each transformation stays bounded.
        buffer=MigrationWriteSet(self.service.store)
        self.validate_into(buffer)
        renewed={}
        for skill,task in self.tasks.items():
            renewed[skill]={**task,'executor_lease':{**task['executor_lease'],
                'expires_at':(self.service.clock()+timedelta(seconds=EXECUTOR_LEASE_SECONDS)).isoformat()}}
            buffer.put('bulk_migration_task_packages',task['task_package_id'],renewed[skill])
        fences=tuple(key for key,value in buffer.before.items() if value is not None)
        if not self.service.store.atomic_compare_and_write(buffer.writes(fences=fences)):
            raise BulkMigrationPolicyError('BULK_TASK_EXECUTION_REVISION_CONFLICT')
        self.tasks=renewed
        return bool(self.tasks[skill_id].get('submission'))

    def verify_result(self,result):
        """A worker body is consumed only when the actual evaluator agrees.

        No field from the worker selects status/evidence or replaces a failed
        evaluator. Model-stage verification may only replay frozen inference.
        """
        self.validate_into(self.service.store)
        task=self.tasks[result.skill_id];submission=task.get('submission')
        if submission is None:return result
        reason=None;proposal=submission.get('output') or {}
        if not isinstance(proposal,dict):proposal={}
        try:BoundedStageProposal.model_validate(proposal)
        except (ValueError,TypeError):reason='BULK_WORKER_OUTPUT_CONTRACT_REQUIRED'
        preserved=(self.service.store.get('bulk_migration_receipts',task['submission_record_ref'])
            if task.get('submission_record_ref') else None)
        preserved={k:v for k,v in (preserved or {}).items() if k!='updated_at'}
        if (task.get('submission_digest')!=_digest(submission)
            or submission.get('manifest_digest')!=self.manifest_digest
            or submission.get('input_fingerprint')!=task['input_fingerprint']
            or submission.get('skill_id')!=result.skill_id
            or task.get('submission_record_ref')!='task-submission:'+_digest(preserved)
            or preserved.get('submission')!=submission):
            reason='BULK_WORKER_SUBMISSION_CLOSURE_STALE'
        elif (set(proposal)!={'contract_version','input_digest','output','output_digest'}
            or proposal.get('contract_version')!='boi/bounded-stage-proposal@1'):
            reason='BULK_WORKER_OUTPUT_CONTRACT_REQUIRED'
        elif proposal['input_digest']!=result.input_digest:
            reason='BULK_WORKER_STAGE_INPUT_STALE'
        elif (proposal['output_digest']!=_digest(proposal['output']) or proposal['output_digest']!=result.output_digest
            or _digest(proposal['output'])!=_digest(result.output)):
            reason='BULK_WORKER_OUTPUT_MISMATCH'
        body={'contract_version':'boi/task-submission-verification@1','principal':self.principal,
            'run_id':self.run_id,'shard_id':self.shard_id,'manifest_digest':self.manifest_digest,
            'task_package_id':task['task_package_id'],'input_fingerprint':task['input_fingerprint'],
            'submission_digest':task['submission_digest'],'stage_input_digest':result.input_digest,
            'submission_record_ref':task.get('submission_record_ref'),
            'evaluated_output_digest':result.output_digest,'evaluated_status':result.status,
            'evaluated_reason_codes':list(result.reason_codes),
            'verification_status':'fail' if reason else 'pass','reason_codes':[reason] if reason else [],
            'production_changed':False,'active_transition':False}
        # Different worker transport/lease times do not alter semantic output.
        verification={**body,'verification_digest':_digest(body)}
        from .bulk_migration_execution import SubmittedMigrationStageResult
        values=asdict(result)
        if reason:values.update(status='blocked',output=None,output_digest='',reason_codes=(reason,),
            evidence_digest=_digest({'verification_digest':verification['verification_digest']}))
        return SubmittedMigrationStageResult(**values,worker_verification=verification)

    def finish_into(self,store,results):
        by_skill={item['skill_id']:item for item in results}
        for skill,before in self.tasks.items():
            task=store.get('bulk_migration_task_packages',before['task_package_id'])
            value={**task,'executor_lease':None}
            verification=by_skill.get(skill,{}).get('worker_verification')
            if verification:
                if verification['submission_digest']!=before.get('submission_digest'):
                    raise BulkMigrationPolicyError('BULK_WORKER_SUBMISSION_CLOSURE_STALE')
                value.update(task_status='completed' if verification['verification_status']=='pass' and by_skill[skill]['status']=='pass'
                    else 'blocked',submission_verification_digest=verification['verification_digest'])
            store.put('bulk_migration_task_packages',before['task_package_id'],value)
        material={'receipt_kind':'TaskExecutionCompletionReceipt','contract_version':'boi/task-execution-completion@1',
            'employee_id':self.principal,'run_id':self.run_id,'shard_id':self.shard_id,
            'manifest_digest':self.manifest_digest,
            'lease_id':next(iter(self.tasks.values()))['executor_lease']['lease_id'],
            'submitted_verification_digests':[r['worker_verification']['verification_digest']
                for r in results if r.get('worker_verification')],
            'stage_result_digest':_digest(list(results)),
            'production_changed':False,'active_transition':False}
        ref=_digest(material)
        store.put('bulk_migration_receipts',ref,{**material,'receipt_digest':ref})
