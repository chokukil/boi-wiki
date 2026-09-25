"""Small agent-side MCP adapters for the existing Wiki client and executor.

The operator supplies the authenticated client and registered executor. No
model, domain routing, trust registration or signing API is exposed. Transient
reading/stage handles are conveniences; Wiki revalidates every work/write.
"""
from __future__ import annotations

import asyncio
import copy
import json

from .boi_mcp_server import BoiLocalMCPServer
from pydantic import Field

from agent_kit.python.boi_mcp_stage import run_mcp_stage, read_completed_stage
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest,RevisionRef
from boi_api.app.governed_runtime.ledger import record_digest
from boi_api.app.governed_runtime.domain_context_service import DomainContextPrepareRequest
from boi_api.app.governed_runtime.domain_work_contract import WorkInput, DomainRequestStageBudget
from boi_api.app.governed_runtime.source_envelope import ArtifactEnvelope
from boi_api.app.governed_runtime.task_knowledge import KnowledgeRequirement,AssetKind


class EvidenceSpanReference(RevisionRef):
    """Reference syntax only. Wiki still verifies source, owner and policy."""
    ref: str = Field(pattern=r'^EvidenceSpan:sha256:[0-9a-f]{64}$',
        description='An actual original-source EvidenceSpan record. Run receipts are separate and cannot be supplied here.')


async def pin_request_budget(client, *, namespace, request_id, request_text, sources, max_stage_attempts):
    """Operator setup before an agent session; no authority or signing endpoint."""
    contract = DomainRequestStageBudget(request_text=request_text, max_stage_attempts=max_stage_attempts)
    saved = await client.propose_asset({'namespace':namespace, 'logical_id':request_id, 'kind':'pack',
        'title':'Request stage budget', 'description':'Pinned execution bound; no semantic qualification.',
        'sources':sources, 'content_json':contract.model_dump_json()}, idempotency_key=request_id+':budget')
    return saved['revision']


class AgentMcpHost:
    def __init__(self, client, *, principal_id, policy_digest, execute, max_stage_attempts=2,
                 request_revision=None, max_host_executions=20, execution_journal_dir=None):
        if not 1 <= max_stage_attempts <= 20 or not 1 <= max_host_executions <= 100:
            raise ValueError('AGENT_HOST_SAMPLE_STAGE_BUDGET_INVALID')
        self.client, self.execute = client, execute
        self.principal_id, self.policy_digest = principal_id, policy_digest
        self.max_stage_attempts = max_stage_attempts
        self.request_revision = request_revision
        self.execution_journal_dir = execution_journal_dir
        self.max_host_executions = max_host_executions
        self.host_execution_reservations = 0
        self.readings, self.stages, self.attempts = {}, {}, {}
        self.lock = asyncio.Lock()

    async def read_source(self, source):
        manifest = await self.client.project(source)
        fields = [{**field, 'text':(await self.client.read_complete_field(source, field))['text']}
                  for field in manifest['fields']]
        return {'source':source, 'manifest':manifest, 'fields':fields,
                'projection_reference':{'source':source, 'manifest_revision':{
                    'ref':manifest['manifest_ref'], 'revision_digest':record_digest(manifest['manifest_ref'])}}}

    async def read_context(self, request):
        reading = await self.client.read_task_knowledge(request,
            principal_id=self.principal_id, policy_digest=self.policy_digest)
        self.readings[semantic_digest(reading['reading_ref'])] = copy.deepcopy(reading)
        return reading

    async def read_harness(self, *, harness_revision, sources, purpose, stage_id=None):
        """Construct stage roots from the selected Wiki contract, not guesses."""
        from boi_api.app.governed_runtime.domain_work_contract import DomainHarnessContract
        asset=await self.client.read_asset(harness_revision)
        if asset['asset']['kind']!='harness':raise ValueError('AGENT_HOST_HARNESS_KIND_REQUIRED')
        contract=DomainHarnessContract.model_validate_json(asset['asset']['content_json'])
        stages=[s.stage_id for s in contract.stages if stage_id is None or s.stage_id==stage_id]
        if not stages:raise ValueError('AGENT_HOST_DECLARED_STAGE_REQUIRED')
        reading=await self.read_context({'sources':sources,'namespace':contract.namespace,'purpose':purpose,
            'stages':stages,'tool_use':'selected_stage','roots':[{'revision':harness_revision,'role':'harness',
                'reason':'Agent-selected exact harness and declared stage dependencies.','stages':stages}]})
        return {**reading,'selected_harness_revision':harness_revision,
            'declared_stages':[s.model_dump(mode='json') for s in contract.stages if s.stage_id in stages],
            'caller_inputs_by_stage':{s.stage_id:[{'name':name,'kind':tool.input_kinds.get(name)}
                for tool in s.tools for name in tool.input_names if name!='context']
                for s in contract.stages if s.stage_id in stages},
            'server_supplied_inputs':{'context':'Wiki resolves this from reading_ref. Omit context from inputs.'},
            'new_execution':False,'stage_roots_origin':'Exact Wiki harness contract, no inferred domain routing.'}

    async def run_stage(self, *, reading_ref, harness_revision, stage_id, sources, inputs, idempotency_key):
        if any(i['name']=='context' for i in inputs):
            raise ValueError('AGENT_HOST_CONTEXT_IS_SERVER_SUPPLIED_OMIT_FROM_INPUTS')
        # Serialize the local convenience handle; admission/lease/idempotency
        # remain Wiki-owned. Unknown interrupted attempts are not auto-retried.
        request = dict(reading_ref=reading_ref, harness_revision=harness_revision,
                       stage_id=stage_id, sources=sources, inputs=inputs)
        digest = semantic_digest(request)
        async with self.lock:
            current = await self.client.call('boi_domain_work', {'action':'lookup',
                'request':{'idempotency_key':idempotency_key}})
            if current.get('found'):
                contract = current['package']['domain_execution_contract']
                saved = {k:contract[k] for k in ('reading_ref','harness_revision','sources','inputs')}
                saved['stage_id'] = contract['stage']['stage_id']
                if saved != request or (self.request_revision is not None
                        and contract.get('request_revision') != self.request_revision):
                    raise ValueError('AGENT_HOST_IDEMPOTENCY_CONFLICT')
                return await self.restore_stage(stage_key=idempotency_key)
            if self.request_revision is None:
                raise ValueError('AGENT_HOST_REQUEST_BUDGET_REQUIRED')
            pinned = await self.client.read_asset(self.request_revision)
            budget = DomainRequestStageBudget.model_validate_json(pinned['asset']['content_json'])
            if pinned['asset']['kind'] != 'pack' or budget.max_stage_attempts != self.max_stage_attempts:
                raise ValueError('AGENT_HOST_REQUEST_BUDGET_MISMATCH')
            reading = await self.client.restore_task_knowledge(reading_ref=reading_ref, sources=sources,
                principal_id=self.principal_id, policy_digest=self.policy_digest)
            self.readings[semantic_digest(reading_ref)] = copy.deepcopy(reading)
            if self.host_execution_reservations >= self.max_host_executions:
                raise ValueError('AGENT_HOST_EXECUTION_CIRCUIT_BREAKER')
            self.host_execution_reservations += 1
            self.attempts[idempotency_key] = digest
            result = await run_mcp_stage(self.client, reading=reading,
                harness_revision=harness_revision, stage_id=stage_id, sources=sources,
                inputs=inputs, execute=self.execute, idempotency_key=idempotency_key,
                request_revision=self.request_revision,execution_journal_dir=self.execution_journal_dir)
            result={**result,'stage_key':idempotency_key}
            self.stages[idempotency_key] = copy.deepcopy({'request':request, 'result':result})
            return result

    async def restore_stage(self, *, stage_key):
        """Read the authoritative task and admitted outputs with no local handle."""
        current = await self.client.call('boi_domain_work', {'action':'lookup',
            'request':{'idempotency_key':stage_key}})
        if not current.get('found'):
            raise ValueError('AGENT_HOST_PRIOR_TASK_UNAVAILABLE')
        package = current['package']; contract = package['domain_execution_contract']
        request = {k:contract[k] for k in ('reading_ref','harness_revision','sources','inputs')}
        request['stage_id'] = contract['stage']['stage_id']
        if package['status'] == 'completed':
            result = await read_completed_stage(self.client, package)
        else:
            slots = [await self.client.call('boi_tool_execution', {'action':'lookup','request':{
                'task_package_id':package['task_package_id'], 'tool_revision':t['tool_revision']}})
                for t in contract['stage']['tools']]
            result = {'status':'previous_attempt_incomplete','package':package,'executions':[],
                'tool_states':slots,'new_execution':False,'new_receipt_created':False}
        result.update(stage_key=stage_key)
        self.stages[stage_key] = copy.deepcopy({'request':request,'result':result})
        return result

    async def publish_stage(self, *, stage_key, output_index, namespace, logical_id, title,
                            description, kind, dependencies, evidence_spans, idempotency_key):
        if any(not str(ref.get('ref','')).startswith('EvidenceSpan:sha256:') for ref in evidence_spans):
            raise ValueError('AGENT_HOST_EVIDENCE_SPAN_REF_REQUIRED_RECEIPTS_ARE_SEPARATE')
        restored = await self.restore_stage(stage_key=stage_key)
        if restored['status'] != 'already_completed':
            raise ValueError('AGENT_HOST_WIKI_STAGE_NOT_COMPLETED')
        stage = self.stages[stage_key]
        outputs = stage['result']['executions']
        if isinstance(output_index, bool) or not 0 <= output_index < len(outputs):
            raise ValueError('AGENT_HOST_STAGE_OUTPUT_INDEX_INVALID')
        # Copy the actual admitted deterministic result, never an agent's
        # replacement "passed" report. This does not assert meaning is true.
        output = outputs[output_index]
        admitted = await self.client.call('boi_tool_execution', {'action':'evidence',
            'request':{'execution_ref':output['admission']['execution_ref']}})
        if admitted.get('execution_ref') != output['admission']['execution_ref']:
            raise ValueError('AGENT_HOST_EXECUTION_EVIDENCE_MISMATCH')
        observed = json.loads(admitted['output_json'])
        if observed != output['output']:
            raise ValueError('AGENT_HOST_EXECUTION_OUTPUT_MISMATCH')
        if not any(d.get('revision') == stage['request']['harness_revision'] for d in dependencies):
            raise ValueError('AGENT_HOST_HARNESS_DEPENDENCY_REQUIRED')
        content = copy.deepcopy(observed['result'])
        if not isinstance(content, dict):
            raise ValueError('AGENT_HOST_OBJECT_RESULT_REQUIRED')
        content.update(execution_refs=[e['admission']['execution_ref'] for e in outputs],
                       harness_revision=stage['request']['harness_revision'])
        saved = await self.client.propose_asset({'namespace':namespace, 'logical_id':logical_id,
            'title':title, 'description':description, 'kind':kind,
            'sources':stage['request']['sources'], 'content_json':json.dumps(content,ensure_ascii=False),
            'dependencies':dependencies, 'evidence_spans':evidence_spans,
            'definition_reading_ref':stage['request']['reading_ref']}, idempotency_key=idempotency_key)
        return {'asset':saved, 'stage_completed':True, 'semantic_review':'not_evaluated',
                'user_request_fulfilled':False, 'status':'PROVISIONAL',
                'reused_completed_stage':True, 'new_tool_execution':False, 'new_tool_receipt_created':False,
                'execution_refs':content['execution_refs'], 'reading_ref':stage['request']['reading_ref']}


def build_agent_host_mcp(host):
    mcp = BoiLocalMCPServer('boi-agent-executor')

    @mcp.tool()
    async def boi_agent_read_source(source: ArtifactEnvelope) -> dict:
        """Read all exact fields through Wiki MCP. Returns original text and projection references."""
        return await host.read_source(source.model_dump(mode='json'))

    @mcp.tool()
    async def boi_agent_read_harness(harness_revision: RevisionRef, sources: list[ArtifactEnvelope],
                                    purpose: str, stage_id: str | None = None) -> dict:
        """After choosing a harness from Wiki catalog, read its full profile/skill/definition context and acknowledge it. The actual stored harness supplies its namespace, nonempty stage roots and exact dependencies; you need not invent them. Omit stage_id to read all its declared stages. Returns reading_ref, full context and declared_stages for run_stage. This only reads; it does not execute or grant authority."""
        return await host.read_harness(harness_revision=harness_revision.model_dump(mode='json'),
            sources=[s.model_dump(mode='json') for s in sources],purpose=purpose,stage_id=stage_id)

    @mcp.tool()
    async def boi_agent_read_context(request: DomainContextPrepareRequest) -> dict:
        """Advanced explicit context read. For a catalog-selected harness prefer read_harness, which reads its stages/dependencies for you. Each explicit root needs nonempty declared stages; catalog titles alone do not supply those. Do not guess contracts."""
        return await host.read_context(request.model_dump(mode='json'))

    @mcp.tool()
    async def boi_agent_run_stage(reading_ref: RevisionRef, harness_revision: RevisionRef, stage_id: str,
                                 sources: list[ArtifactEnvelope], inputs: list[WorkInput], idempotency_key: str) -> dict:
        """Run your selected, previously read harness stage via Wiki tasks/leases and the registered external executor. Supply only caller_inputs_by_stage from read_harness. Omit the reserved context input: Wiki resolves it from reading_ref. Wiki enforces this request's pinned stage budget across restarts. A prior incomplete attempt is observed, never blindly rerun. No semantic review is implied."""
        return await host.run_stage(reading_ref=reading_ref.model_dump(mode='json'), harness_revision=harness_revision.model_dump(mode='json'),
            stage_id=stage_id, sources=[v.model_dump(mode='json') for v in sources],
            inputs=[v.model_dump(mode='json') for v in inputs], idempotency_key=idempotency_key)

    @mcp.tool()
    async def boi_agent_restore_stage(stage_key: str) -> dict:
        """Read a prior Wiki task and admitted outputs after reconnection or restart. Use its exact stage_key (idempotency key). Does not rerun tools or create a receipt. A completed stage can be published; an unknown external result must be reconciled."""
        return await host.restore_stage(stage_key=stage_key)

    @mcp.tool()
    async def boi_agent_publish_stage(stage_key: str, output_index: int, namespace: str,
            logical_id: str, title: str, description: str, kind: AssetKind, dependencies: list[KnowledgeRequirement],
            evidence_spans: list[EvidenceSpanReference], idempotency_key: str) -> dict:
        """Store the actual admitted tool result as a Wiki candidate. stage_key is the EXACT stage_key returned by boi_agent_run_stage (its idempotency_key), NOT a stage name, task ID or receipt. Supply exact read dependencies. evidence_spans accepts only actual EvidenceSpan records, never Run receipts; use [] when the result has no span references. Existing execution_refs and reading_ref are preserved automatically and do not belong in evidence_spans. Publication does not complete semantic review or the whole user request."""
        return await host.publish_stage(stage_key=stage_key, output_index=output_index,
            namespace=namespace, logical_id=logical_id, title=title, description=description,
            kind=kind, dependencies=[v.model_dump(mode='json') for v in dependencies],
            evidence_spans=[v.model_dump(mode='json') for v in evidence_spans], idempotency_key=idempotency_key)

    return mcp
