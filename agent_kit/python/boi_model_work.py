"""Bounded external inference using existing Wiki tasks, leases and tool receipts.

Wiki stores/admits the job. The registered external host invokes the provider;
neither its execution receipt nor a schema pass establishes semantic truth.
"""
import asyncio,base64,json,uuid,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal

from pydantic import Field,TypeAdapter
from jsonschema import validate

from agent_kit.python.boi_structured_provider import run_structured,strict_output_schema
from agent_kit.python.boi_process_response_review import recorded_provider_failure
from agent_kit.python.boi_tool_executor import ExternalToolExecutor,RegisteredReadOnlyTool
from agent_kit.python.boi_mcp_stage import submit_stage_result
from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
from boi_api.app.governed_runtime.domain_work_contract import DomainToolReport
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref,Digest,RevisionRef,semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.tool_execution_contract import ToolInvocation


class ModelWorkInput(FrozenContract):
    contract_version:Literal['boi/external-model-work-input@1']='boi/external-model-work-input@1'
    provider:Literal['codex','claude']
    prompt:Ref
    output_schema_json:Ref
    source_manifest_digest:Digest
    input_revisions:tuple[RevisionRef,...]=Field(min_length=1)
    knowledge_reading_ref:RevisionRef
    review_contract_version:Ref
    timeout_seconds:int=Field(default=900,ge=1,le=900)


class RetryModelWorkInput(ModelWorkInput):
    contract_version:Literal['boi/external-model-work-input@2']='boi/external-model-work-input@2'
    retry_of_execution:RevisionRef


class PiModelWorkInput(FrozenContract):
    """Versioned Pi variant; legacy @1/@2 codex/claude serialization is untouched."""
    contract_version:Literal['boi/external-model-work-input@3']='boi/external-model-work-input@3'
    provider:Literal['pi']
    prompt:Ref
    output_schema_json:Ref
    source_manifest_digest:Digest
    input_revisions:tuple[RevisionRef,...]=Field(min_length=1)
    knowledge_reading_ref:RevisionRef
    review_contract_version:Ref
    timeout_seconds:int=Field(default=900,ge=1,le=900)


class RetryPiModelWorkInput(PiModelWorkInput):
    contract_version:Literal['boi/external-model-work-input@4']='boi/external-model-work-input@4'
    retry_of_execution:RevisionRef


def model_work_input_schema():
    return TypeAdapter(ModelWorkInput|RetryModelWorkInput|PiModelWorkInput|RetryPiModelWorkInput).json_schema()


def parse_work_input(raw):
    return TypeAdapter(ModelWorkInput|RetryModelWorkInput|PiModelWorkInput|RetryPiModelWorkInput).validate_json(raw)


def provider_output_text(path,run):
    """Keep the exact UTF-8 output bytes bound by the provider receipt."""
    raw=Path(path).read_bytes()
    if byte_digest(raw)!=run.get('output_digest'):
        raise ValueError('MODEL_WORK_PROVIDER_OUTPUT_BYTES_CHANGED')
    return raw.decode('utf-8')


class ModelWorkUnavailable(ValueError):
    """An existing job is pending/unknown, not a failed semantic assessment."""


class McpModelWorker:
    def __init__(self,client,*,runtime,installation,sources,input_revisions,review_contract_version,
            job_root,provider_run=run_structured):
        self.client=client;self.runtime=runtime;self.installation=installation;self.sources=sources
        self.input_revisions=input_revisions;self.review_contract_version=review_contract_version
        self.root=Path(job_root);self.root.mkdir(parents=True,exist_ok=True)
        self.provider_run=provider_run;self.loop=asyncio.get_running_loop();self.worker_id=uuid.uuid4().hex
        self.events=[];self._record_lock=threading.Lock()

    def infer(self,**kwargs):
        """Adapter for the existing synchronous provider seam; no new engine."""
        return asyncio.run_coroutine_threadsafe(self.run(**kwargs),self.loop).result()

    def record(self,event):
        with self._record_lock:
            self.events.append(event)
            (self.root/('worker-'+self.worker_id+'.json')).write_text(json.dumps(self.events,ensure_ascii=False,indent=2))

    async def run(self,*,provider,prompt,schema,output_dir,knowledge_reading_ref,timeout_seconds=900,input_revisions=None,retry_of_execution=None):
        work_input=PiModelWorkInput if provider=='pi' else ModelWorkInput
        data=work_input(provider=provider,prompt=prompt,output_schema_json=json.dumps(strict_output_schema(schema),ensure_ascii=False),
            source_manifest_digest=source_manifest_digest(self.sources),input_revisions=self.input_revisions if input_revisions is None else input_revisions,
            knowledge_reading_ref=knowledge_reading_ref,
            review_contract_version=self.review_contract_version,timeout_seconds=timeout_seconds).model_dump(mode='json')
        if retry_of_execution is not None:
            await self.authorize_retry(data,retry_of_execution)
            retry_input=RetryPiModelWorkInput if provider=='pi' else RetryModelWorkInput
            data=retry_input(**{**data,'contract_version':'boi/external-model-work-input@4'
                if provider=='pi' else 'boi/external-model-work-input@2'},
                retry_of_execution=retry_of_execution).model_dump(mode='json')
        key='model-work:'+semantic_digest(data);out=Path(output_dir)
        installed=self.installation;client=self.client
        known=await client.call('boi_domain_work',{'action':'lookup','request':{'idempotency_key':key}})
        if known['found']:
            package=known['package'];contract=package['domain_execution_contract']
            proposal=next(i for i in contract['inputs'] if i['kind']=='proposal' and i['name']=='request')
            knowledge=next(i for i in contract['inputs'] if i['kind']=='knowledge_reading')
            if (json.loads(proposal['content_json'])!=data or knowledge['reading_ref']!=knowledge_reading_ref
                    or source_manifest_digest(contract['sources'])!=data['source_manifest_digest']):
                raise ValueError('MODEL_WORK_STORED_REQUEST_CHANGED')
        else:
            reading=await client.read_task_knowledge({'namespace':installed['namespace'],'sources':self.sources,
                'purpose':'Execute a bounded structured model observation','roots':[
                    {'revision':installed['harness_revision'],'role':'model_observation_harness',
                     'reason':'Read the declared output and single-attempt execution contract.','stages':['observe']}]},
                principal_id=self.runtime['principal'].employee_id,policy_digest=self.runtime['authorization'].policy_digest)
            package=await client.call('boi_domain_work',{'action':'start','request':{'harness_revision':installed['harness_revision'],
                'stage_id':'observe','sources':self.sources,'reading_ref':reading['reading_ref'],
                'inputs':[{'kind':'proposal','name':'request','content_json':json.dumps(data,ensure_ascii=False)},
                    {'kind':'knowledge_reading','name':'knowledge','reading_ref':knowledge_reading_ref}],
                'idempotency_key':key}})
        task=package['task_package_id']
        declared_tool=package['domain_execution_contract']['stage']['tools'][0]['tool_revision']
        lookup_request={'task_package_id':task,'tool_revision':declared_tool}
        async def finish_stage(report,execution_ref):
            current=await client.call('boi_tasks',{'task_package_id':task})
            if report['checks'][0]['status']=='pass' and current['status']!='completed':
                try:
                    current=await client.call('boi_domain_work',{'action':'complete','request':{
                        'task_package_id':task,'expected_revision':current['revision'],'lease_id':current['lease']['lease_id'],
                        'execution_refs':[execution_ref],
                        'summary':'Structured provider output recorded; semantic answer correctness is assessed separately.',
                        'idempotency_key':key+':complete'}})
                except ValueError as exc:
                    self.record({'job_key':key,'task':task,'state':'stage_completion_unresolved',
                        'diagnostic':str(exc),'new_model_dispatch':False})
                    current=await client.call('boi_tasks',{'task_package_id':task})
            return current['status']
        slot=await client.call('boi_tool_execution',{'action':'lookup','request':lookup_request})
        if slot['state']=='receipt_recorded':
            evidence=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':slot['execution_ref']}})
            if evidence['execution']['signed_execution']['body']['outcome']!='completed':
                self.record({'job_key':key,'task':task,'state':'known_executor_failure',
                    'execution_ref':slot['execution_ref'],'new_model_dispatch':False})
                raise ValueError('MODEL_WORK_EXECUTOR_FAILED')
            report=json.loads(evidence['output_json']);self.record({'job_key':key,'task':task,'state':'replayed_observation',
                'execution_ref':slot['execution_ref'],'new_model_dispatch':False})
            stage_status=await finish_stage(report,slot['execution_ref'])
            return self.deliver(report,data,out,slot['execution_ref'],replayed=True,stage_status=stage_status)
        if slot['state'] in ('in_flight','external_result_unknown'):
            self.record({'job_key':key,'task':task,'state':slot['state'],'new_model_dispatch':False})
            raise ModelWorkUnavailable('MODEL_WORK_'+slot['state'].upper())
        if declared_tool!=installed['tool_revision']:
            raise ModelWorkUnavailable('MODEL_WORK_EXECUTION_RELEASE_CHANGED')
        # Reading the existing task observes expiry using the existing service.
        package=await client.call('boi_tasks',{'task_package_id':task})
        if package['status'] not in ('available','released','expired','waiting_agent'):
            self.record({'job_key':key,'task':task,'state':'owned_by_worker','new_model_dispatch':False})
            raise ModelWorkUnavailable('MODEL_WORK_OWNED_BY_WORKER')
        try:
            claimed=await client.call('boi_task_claim',{'task_package_id':task,'expected_revision':package['revision'],
                'idempotency_key':key+':'+self.worker_id,'lease_seconds':3600})
        except ValueError as exc:
            self.record({'job_key':key,'task':task,'state':'claim_not_acquired','new_model_dispatch':False})
            raise ModelWorkUnavailable('MODEL_WORK_CLAIM_NOT_ACQUIRED') from exc
        binding={'task_package_id':task,'expected_revision':claimed['revision'],'lease_id':claimed['lease']['lease_id']}
        prepared=await client.call('boi_tool_execution',{'action':'prepare','request':{**binding,
            'tool_revision':installed['tool_revision'],'idempotency_key':key+':'+claimed['lease']['lease_id']}})
        invocation=ToolInvocation.model_validate(prepared['invocation']);material={}
        for artifact in invocation.inputs:
            item=await client.call('boi_tool_execution',{'action':'input','request':{'invocation_id':invocation.invocation_id,'name':artifact.name}})
            raw=base64.b64decode(item['content_b64'],validate=True)
            if item['input']!=artifact.model_dump(mode='json') or byte_digest(raw)!=artifact.content_digest:
                raise ValueError('MODEL_WORK_INPUT_BINDING_MISMATCH')
            material[artifact.name]=raw
        async def authorize(identity):
            found=await client.call('boi_tool_execution',{'action':'read','request':{'invocation_id':identity}})
            return ToolInvocation.model_validate(found['invocation'])
        async def dispatch(identity):
            grant=await client.call('boi_tool_execution',{'action':'dispatch','request':{'invocation_id':identity}})
            self.record({'job_key':key,'task':task,'invocation_id':identity,'state':grant['state'],
                'dispatch_permission_acquired':grant['acquired'],'new_model_dispatch':False,'input_digest':semantic_digest(data)})
            return grant['acquired']
        def sync(method,*args):return asyncio.run_coroutine_threadsafe(method(*args),self.loop).result(timeout=45)
        def validate_input(inputs):
            request=parse_work_input(inputs['request'])
            context=json.loads(inputs['context'])
            knowledge=json.loads(inputs['knowledge'])
            if request.source_manifest_digest!=context['source_manifest_digest'] or request.model_dump(mode='json')!=data:
                raise ValueError('MODEL_WORK_SOURCE_OR_REQUEST_CHANGED')
            if (knowledge['reading_ref']!=request.knowledge_reading_ref.model_dump(mode='json')
                    or knowledge['context']['source_manifest_digest']!=request.source_manifest_digest
                    or any(r.model_dump(mode='json') not in [a['revision'] for a in knowledge['context']['assets']]
                        for r in request.input_revisions)):
                raise ValueError('MODEL_WORK_KNOWLEDGE_NOT_READ')
            def local_refs(node):
                if isinstance(node,dict):
                    if '$ref' in node and not node['$ref'].startswith('#'):
                        raise ValueError('MODEL_WORK_EXTERNAL_SCHEMA_REFERENCE_DENIED')
                    for value in node.values():local_refs(value)
                elif isinstance(node,list):
                    for value in node:local_refs(value)
            local_refs(json.loads(request.output_schema_json))
        def execute(inputs):
            request=parse_work_input(inputs['request'])
            self.record({'job_key':key,'task':task,'invocation_id':invocation.invocation_id,
                'state':'provider_started','new_model_dispatch':True})
            try:
                value,run=self.provider_run(provider=request.provider,prompt=request.prompt,schema=json.loads(request.output_schema_json),
                    output_dir=out,timeout_seconds=request.timeout_seconds)
                validate(value,json.loads(request.output_schema_json));status='pass'
                value_json=provider_output_text(out/'output.json',run)
            except ValueError as exc:
                run=recorded_provider_failure(out,exc);value_json=None;status='unknown' if run['status']=='timed_out' else 'fail'
            return {'contract_version':'boi/domain-tool-report@1','checks':[{'check_id':'structured_provider_output',
                'status':status,'subject_ref':invocation.invocation_id,'reason_code':'MODEL_OBSERVATION_NOT_SEMANTIC_VERDICT'}],
                'result':{'contract_version':'boi/model-observation@1','input_digest':semantic_digest(data),
                    'provider_run':run,'value_json':value_json,'semantic_truth_proven':False}}
        release=installed['release']
        registered=RegisteredReadOnlyTool(release,installed['measure_implementation'],installed['measure_environment'],
            validate_input,execute,lambda value:DomainToolReport.model_validate(value))
        executor=ExternalToolExecutor(executor_id=installed['executor_id'],key_id=installed['key_id'],signing_key=installed['signing_key'],
            registry={release.revision:registered},authorize_invocation=lambda identity:sync(authorize,identity),
            claim_dispatch=lambda identity:sync(dispatch,identity),clock=lambda:datetime.now(timezone.utc),
            clock_wait_seconds=3,clock_wait_observer=lambda event:self.record({'job_key':key,'state':'clock_wait',**event}))
        result=await asyncio.to_thread(executor.execute,invocation,material)
        submitted=await submit_stage_result(client,invocation,result,journal_dir=out/'signed-executions')
        report=json.loads(result.output_bytes)
        if result.receipt.body.outcome!='completed':raise ValueError('MODEL_WORK_EXECUTOR_FAILED')
        stage_status=await finish_stage(report,submitted['execution_ref'])
        self.record({'job_key':key,'task':task,'state':'observation_recorded','execution_ref':submitted['execution_ref'],
            'new_model_dispatch':False,'provider_status':report['result']['provider_run']['status']})
        return self.deliver(report,data,out,submitted['execution_ref'],replayed=False,stage_status=stage_status)

    async def authorize_retry(self,data,execution_ref):
        """One explicit retry of a known failure, with identical semantic input.

        This is an opt-in host call, never an automatic fallback. The receipt
        remains failed; the retry obtains its own task, claim, dispatch and
        receipt. Unknown/successful outcomes and retry chains are excluded.
        """
        evidence=await self.client.call('boi_tool_execution',{'action':'evidence',
            'request':{'execution_ref':execution_ref}})
        body=evidence['execution']['signed_execution']['body']
        if body['outcome']!='completed':raise ValueError('MODEL_WORK_RETRY_KNOWN_PROVIDER_FAILURE_REQUIRED')
        report=json.loads(evidence['output_json']);observation=report['result']
        if (observation.get('contract_version')!='boi/model-observation@1' or
                observation['provider_run']['status']!='failed' or observation['value_json'] is not None):
            raise ValueError('MODEL_WORK_RETRY_KNOWN_PROVIDER_FAILURE_REQUIRED')
        task=await self.client.call('boi_tasks',{'task_package_id':body['invocation']['task_revision']['ref']})
        prior=next(i for i in task['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='request')
        raw=json.loads(prior['content_json'])
        if raw.get('retry_of_execution') is not None:raise ValueError('MODEL_WORK_RETRY_BUDGET_EXHAUSTED')
        if semantic_digest(raw)!=observation['input_digest'] or raw!=data:
            raise ValueError('MODEL_WORK_RETRY_EXACT_INPUT_REQUIRED')
        self.record({'state':'explicit_retry_authorized_for_known_failure','prior_execution_ref':execution_ref,
            'task':task['task_package_id'],'input_digest':semantic_digest(data),'new_model_dispatch':False})

    @staticmethod
    def deliver(report,data,out,execution_ref,*,replayed,stage_status):
        observation=report['result']
        if observation['contract_version']!='boi/model-observation@1' or observation['input_digest']!=semantic_digest(data):
            raise ValueError('MODEL_WORK_OBSERVATION_INPUT_MISMATCH')
        run=observation['provider_run']
        if replayed:
            out.mkdir(parents=True,exist_ok=False)
            (out/'prompt.txt').write_text(data['prompt'])
            (out/'schema.json').write_text(json.dumps(json.loads(data['output_schema_json']),ensure_ascii=False,indent=2))
            (out/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2))
            if observation['value_json'] is not None:(out/'output.json').write_bytes(observation['value_json'].encode('utf-8'))
        (out/'wiki-model-work.json').write_text(json.dumps({'execution_ref':execution_ref,'observation_replayed':replayed,
            'new_model_dispatch':not replayed,'model_review_completed':run['status']=='completed',
            'wiki_task_status':stage_status,'declared_stage_completed':stage_status=='completed',
            'semantic_truth_proven':False},ensure_ascii=False,indent=2))
        if run['status']!='completed':raise ValueError('STRUCTURED_PROVIDER_'+run['status'].upper())
        value=json.loads(observation['value_json']);validate(value,json.loads(data['output_schema_json']))
        return value,{**run,'wiki_execution_ref':execution_ref,'observation_replayed':replayed,'new_model_dispatch':not replayed,
            'wiki_task_status':stage_status,'declared_stage_completed':stage_status=='completed'}
