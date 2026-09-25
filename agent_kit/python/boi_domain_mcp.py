"""Provider-neutral MCP client for source intake and evidence reading.

No domain inference, hidden SQL, Wiki agent delegation or canonical writes.
The caller supplies domain reasoning after reading current Wiki contracts.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx2
from mcp import ClientSession, MCPError
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult


def _digest(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


TOOL_EXECUTION_ERROR_CODES = frozenset({
    'DOMAIN_CONTEXT_REQUIRED_TOOL_UNAVAILABLE','DOMAIN_WORK_ACTIVE_LEASE_REQUIRED',
    'DOMAIN_INTAKE_REQUEST_INVALID','DOMAIN_TOOL_INVOCATION_ACCESS_DENIED',
    'DOMAIN_TOOL_INVOCATION_STALE','DOMAIN_TOOL_DISPATCH_NOT_ACQUIRED',
    'DOMAIN_TOOL_RECEIPT_REPLAY_CONFLICT','DOMAIN_TOOL_RECEIPT_PUBLICATION_CONFLICT',
    'TOOL_EXECUTION_INVOCATION_BINDING_MISMATCH','TOOL_EXECUTION_FINISHED_IN_FUTURE',
    'TOOL_EXECUTOR_UNKNOWN_OR_AMBIGUOUS','TOOL_EXECUTOR_TRUST_NOT_CURRENT',
    'TOOL_EXECUTOR_RELEASE_NOT_AUTHORIZED','TOOL_EXECUTION_SIGNATURE_INVALID',
    'TOOL_EXECUTION_OUTPUT_BINDING_MISMATCH',
})


DOMAIN_WORK_ERROR_CODES = frozenset({
    'DOMAIN_WORK_REQUEST_STAGE_BUDGET_EXHAUSTED', 'DOMAIN_WORK_REQUEST_BUDGET_CHANGED',
    'DOMAIN_WORK_REQUEST_SOURCE_OUTSIDE_BUDGET',
})


DOMAIN_CONTEXT_ERROR_CODES = frozenset({
    'DOMAIN_CONTEXT_PREPARATION_CONFLICT','DOMAIN_CONTEXT_ACCESS_OR_BINDING_DENIED',
    'DOMAIN_CONTEXT_CONTENT_DRIFT','DOMAIN_CONTEXT_CANONICAL_DEFINITIONS_CHANGED',
    'DOMAIN_CONTEXT_REQUIRED_TOOL_UNAVAILABLE','DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED',
    'DOMAIN_CONTEXT_SELECTED_CONTENT_CHANGED','DOMAIN_CONTEXT_DEFINITION_SCOPE_RESTRICTED',
    'DOMAIN_CONTEXT_DEFINITION_SCOPE_CHANGED','DOMAIN_CONTEXT_PAGE_LAYOUT_CHANGED',
    'DOMAIN_CONTEXT_PAGE_OUTSIDE_RANGE','DOMAIN_CONTEXT_DELIVERY_CONFLICT',
    'DOMAIN_CONTEXT_COMPLETE_DELIVERY_REQUIRED',
})


KNOWLEDGE_SET_ERROR_CODES = frozenset({
    'KNOWLEDGE_SET_ACCESS_DENIED','KNOWLEDGE_SET_AUTHORITY_CHANGED',
    'KNOWLEDGE_SPACE_ACCESS_DENIED','KNOWLEDGE_SET_INDEX_UNPREPARED_OR_CHANGED',
    'KNOWLEDGE_SET_INDEX_READ_FAILED',
})
CONCEPT_RECOVERY_ACTIONS = {
    'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED': 'discover_reviewed_spelling',
    'KNOWLEDGE_REUSE_ROLE_OR_SOURCE_SCOPE_EMPTY': 'inspect_role_and_source_scope',
}


def concept_recovery(status, reason):
    """Only authorized conflict categories; never copy server prose or candidates."""
    if status != 409 or not isinstance(reason, str) or reason not in CONCEPT_RECOVERY_ACTIONS:
        return None
    return {'action': CONCEPT_RECOVERY_ACTIONS[reason],
        'automatic_substitution': False, 'fact_established': False,
        'guidance': ('Read the current reviewed spelling and its source scope; do not invent an alias.'
            if reason == 'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED' else
            'Compare the requested relation and source scope with the reviewed evidence; do not change either silently.'),
        'user_explanation': ('이 표현을 선택한 검토 범위의 개념에 연결하지 못했습니다. 확인된 표기를 찾아보거나 뜻을 확인해야 합니다.'
            if reason == 'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED' else
            '선택한 근거 범위에서 요청한 관계를 확인하지 못했습니다. 관계와 원천 범위를 확인해야 합니다.'),
        'presentation': 'Explain the relevant limitation in ordinary language; do not display internal reason or HTTP codes. Keep independently supported answer parts.'}


SAFE_ERROR_CODES = (frozenset(CONCEPT_RECOVERY_ACTIONS) | TOOL_EXECUTION_ERROR_CODES | DOMAIN_WORK_ERROR_CODES |
                    DOMAIN_CONTEXT_ERROR_CODES | KNOWLEDGE_SET_ERROR_CODES | frozenset({
                        'DOMAIN_SEARCH_INDEX_NOT_PREPARED',
                        'KNOWLEDGE_CONTRACT_FILTER_COMBINATION_UNSUPPORTED',
                        'KNOWLEDGE_SOURCE_BUNDLE_LIMIT_REQUIRES_NARROWER_SELECTION',
                    }))


def _recovery_refs(value):
    result={}
    invocation=value.get('invocation_id')
    if isinstance(invocation,str) and re.fullmatch(r'tool-invocation:sha256:[a-f0-9]{64}',invocation):
        result['invocation_id']=invocation
    execution=value.get('execution_ref')
    if (isinstance(execution,dict) and set(execution)=={'ref','revision_digest'}
            and isinstance(execution['ref'],str) and re.fullmatch(r'Run:sha256:[a-f0-9]{64}',execution['ref'])
            and isinstance(execution['revision_digest'],str) and re.fullmatch(r'sha256:[a-f0-9]{64}',execution['revision_digest'])):
        result['execution_ref']=dict(execution)
    return result


def _safe_error_diagnostic(content, *, tool_name: str) -> str:
    """Extract a safe diagnostic category from MCP error content.

    Only extracts HTTP status code and reason_code from structured API errors.
    Never includes request/response bodies which may contain private source arguments.
    Returns empty string if the content does not match the expected structure.
    """
    try:
        texts = [block.text for block in content if block.type == 'text']
        if len(texts) != 1:
            return ''
        # FastMCP Tool.run wraps exceptions using this exact protocol prefix.
        # Do not scan arbitrary error prose for embedded JSON.
        payload = texts[0]
        prefix = 'Error executing tool ' + tool_name + ': '
        if payload.startswith(prefix):
            payload = payload[len(prefix):]
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            return ''
        status = parsed.get('status_code')
        body = parsed.get('body')
        detail = body.get('detail') if isinstance(body, dict) else None
        reason = detail.get('reason_code') if isinstance(detail, dict) else None
        if isinstance(reason,str) and reason in CONCEPT_RECOVERY_ACTIONS and status != 409:reason=None
        parts = []
        if isinstance(status, int) and not isinstance(status, bool) and 400 <= status <= 599:
            parts.append('http_' + str(status))
        if isinstance(reason, str) and reason in SAFE_ERROR_CODES:
            parts.append(reason)
        return ':'.join(parts)
    except (ValueError, TypeError, KeyError, AttributeError):
        return ''


class BoiDomainMcpClient:
    def __init__(self, session):
        self.session = session

    async def knowledge_work(self, operation, request=None):
        """Use the current server task schema; no local namespace or model routing."""
        return await self.call('boi_knowledge_work', {
            'operation': operation, 'request': {} if request is None else request})

    async def read_domain_packages(self, *, package_id=None, revision=None, team_id=None):
        """Discover/read server package snapshots, without changing team adoption."""
        request = {key: value for key, value in (
            ('package_id', package_id), ('revision', revision), ('team_id', team_id)) if value is not None}
        return await self.call('boi_domain_packages', {
            'operation': 'read' if package_id is not None or revision is not None else 'discover',
            'request': request})

    async def read_saved_answer_evidence(self, delivery):
        """Explicit evidence inspection only; normal answer delivery needs no call."""
        from .boi_final_source_review import validate_saved_answer_evidence
        revision=delivery.get('delivery_revision')
        if (delivery.get('evidence_read',{}).get('tool')!='boi_native_answer'
                or delivery['evidence_read'].get('arguments')!={'revision':revision,'view':'binding'}):
            raise ValueError('NATIVE_FINAL_EVIDENCE_DELIVERY_MISMATCH')
        detail=await self.call('boi_native_answer',{'revision':revision,'view':'binding'})
        return validate_saved_answer_evidence(delivery,detail)

    async def prepare_process_review(self, candidate_revision, *, knowledge_reading_ref,
            target_pointers=None,field_locators=(),prior_review_revision=None):
        """Process or native SVID roots, expanded by Wiki; no model/write here.

        The historical tool name is shared. Native definitions retain their
        schema and selected record/annotation source scope.
        """
        return await self.call('boi_process_review_binding',{'candidate_revision':candidate_revision,
            'preparation':{'knowledge_reading_ref':knowledge_reading_ref,'target_pointers':target_pointers,
                'field_locators':list(field_locators),'prior_review_revision':prior_review_revision}})

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.session.call_tool(name, arguments)
        except MCPError as error:
            # A protocol/connection failure does not prove rollback. No retry.
            code=error.error.code
            category='REQUEST_TIMEOUT' if code == -32001 else 'PROTOCOL_ERROR'
            raise ValueError('BOI_MCP_PROTOCOL_FAILED:'+name+':'+category) from None
        if not isinstance(result,CallToolResult):
            raise ValueError('BOI_MCP_STRUCTURED_RESPONSE_REQUIRED')
        if result.is_error:
            structured=result.structured_content
            if structured is None:
                texts=[block.text for block in result.content if block.type=='text']
                if len(texts)==1:
                    try:structured=json.loads(texts[0])
                    except (ValueError,TypeError):pass
            if isinstance(structured,dict) and structured.get('contract_version')=='boi/mcp-error@1':
                status=structured.get('status_code')
                reason=structured.get('reason_code')
                if isinstance(reason,str) and reason in CONCEPT_RECOVERY_ACTIONS and status != 409:reason=None
                parts=[]
                if type(status) is int and 400<=status<=599:parts.append('http_'+str(status))
                if isinstance(reason,str) and reason in SAFE_ERROR_CODES:
                    parts.append(reason)
                error=ValueError('BOI_MCP_TOOL_FAILED:'+name+(':'+':'.join(parts) if parts else ''))
                error.diagnostic={'kind':structured.get('kind') if structured.get('kind') in ('authorization','backend') else 'backend',
                    'operation_outcome':'not_established','automatic_retry':False,
                    **({'status_code':status} if type(status) is int and 400<=status<=599 else {}),
                    **({'reason_code':reason} if isinstance(reason,str) and reason in SAFE_ERROR_CODES else {})}
                if isinstance(reason,str) and reason in SAFE_ERROR_CODES:
                    error.diagnostic.update(_recovery_refs(structured))
                recovery=concept_recovery(status,reason)
                if recovery:error.diagnostic['recovery']=recovery
                raise error
            # Tool errors can include private source arguments. Preserve the
            # failed operation identity and safe diagnostic category, not an
            # unfiltered exception transcript.
            diagnostic = _safe_error_diagnostic(result.content, tool_name=name)
            if diagnostic:
                raise ValueError('BOI_MCP_TOOL_FAILED:' + name + ':' + diagnostic)
            raise ValueError('BOI_MCP_TOOL_FAILED:' + name)
        if isinstance(result.structured_content, dict):
            value=result.structured_content
        else:
            text = [block.text for block in result.content if block.type == 'text']
            if len(text) != 1:
                raise ValueError('BOI_MCP_STRUCTURED_RESPONSE_REQUIRED')
            value = json.loads(text[0])
        if not isinstance(value, dict):
            raise ValueError('BOI_MCP_STRUCTURED_RESPONSE_REQUIRED')
        if value.get('contract_version')=='boi/tool-execution-error@1':
            error=value.get('error'); code=error.get('reason_code') if isinstance(error,dict) else None
            if name=='boi_tool_execution' and isinstance(code,str) and code in TOOL_EXECUTION_ERROR_CODES:
                failure=ValueError(code)
                failure.diagnostic={'reason_code':code,**_recovery_refs(error),
                    'operation_outcome':'not_established','automatic_retry':False}
                raise failure
            raise ValueError('BOI_MCP_TOOL_FAILED:'+name)
        if value.get('contract_version')=='boi/domain-work-error@1':
            error=value.get('error'); code=error.get('reason_code') if isinstance(error,dict) else None
            if isinstance(code,str) and code in {'DOMAIN_WORK_REQUEST_STAGE_BUDGET_EXHAUSTED','DOMAIN_WORK_REQUEST_BUDGET_CHANGED',
                    'DOMAIN_WORK_REQUEST_SOURCE_OUTSIDE_BUDGET'}:
                failure=ValueError(code)
                failure.diagnostic={'reason_code':code,**_recovery_refs(error),
                    'operation_outcome':'not_established','automatic_retry':False}
                raise failure
            raise ValueError('BOI_MCP_TOOL_FAILED:'+name)
        return value

    async def capture(self, raw: bytes, *, media_type: str, role: str, idempotency_key: str):
        if not raw or len(raw) > 65536:
            raise ValueError('BOI_INLINE_SOURCE_LIMIT_USE_REGISTERED_CONNECTOR')
        response = await self.call('boi_source_capture', {'source':{'kind':'inline_source', 'role':role,
            'media_type':media_type, 'content_b64':base64.b64encode(raw).decode('ascii')},
            'idempotency_key':idempotency_key})
        if response.get('digest') != _digest(raw) or response.get('role') != role:
            raise ValueError('BOI_CAPTURE_SOURCE_BINDING_MISMATCH')
        return {'kind':'artifact_ref', **{key:response[key] for key in ('artifact_ref','digest','role')}}

    async def capture_file(self, path, *, role: str, idempotency_key: str):
        """Read supplied workbook bytes on the host; never synthesize a file body."""
        from boi_api.app.governed_runtime.source_envelope import FileSourceEnvelope
        raw=Path(path).read_bytes()
        envelope={'kind':'file_source','role':role,'display_name':Path(path).name,
            'media_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'content_b64':base64.b64encode(raw).decode('ascii')}
        FileSourceEnvelope.model_validate(envelope).source_bytes()
        response=await self.call('boi_source_capture',{'source':envelope,'idempotency_key':idempotency_key})
        if response.get('digest')!=_digest(raw) or response.get('role')!=role:
            raise ValueError('BOI_CAPTURE_SOURCE_BINDING_MISMATCH')
        return {'kind':'artifact_ref',**{k:response[k] for k in ('artifact_ref','digest','role')}}

    async def project(self, reference, *, manifest_ref=None):
        manifest = await self.call('boi_source_project', {'reference':reference,
            **({'manifest_ref':manifest_ref} if manifest_ref is not None else {})})
        if (manifest.get('artifact_ref') != reference['artifact_ref']
                or manifest.get('source_revision_digest') != reference['digest']
                or manifest.get('source_role') != reference['role']
                or manifest.get('status') != 'PROVISIONAL'
                or manifest.get('canonical_projection_eligible') is not False
                or (manifest_ref is not None and manifest.get('manifest_ref')!=manifest_ref)):
            raise ValueError('BOI_PROJECTION_SOURCE_BINDING_MISMATCH')
        return manifest

    async def read_complete_field(self, reference, field, *, page_characters: int = 4096):
        """Complete-field delivery check, independent of domain interpretation."""
        offset, parts, binding = 0, [], None
        while True:
            page = await self.call('boi_source_field', {'reference':reference,
                'span_ref':field['span_ref'], 'offset':offset, 'limit':page_characters})
            text = page.get('text')
            if not isinstance(text, str):
                raise ValueError('BOI_FIELD_TEXT_REQUIRED')
            stable = {key:page.get(key) for key in ('artifact_ref','source_revision_digest','snapshot_digest',
                'source_role','policy_digest','employee_id','rights_record_ref','parser_digest',
                'field_locator','record_locator','field_state','value_kind','presence_basis',
                'content_digest','character_count','span_ref','status','offset_basis')}
            if binding is None:
                binding = stable
            if (stable != binding or page.get('artifact_ref') != reference['artifact_ref']
                    or page.get('source_revision_digest') != reference['digest']
                    or page.get('source_role') != reference['role']
                    or page.get('span_ref') != field['span_ref']
                    or page.get('content_digest') != field['content_digest']
                    or any(page.get(key) != field[key] for key in ('field_locator','record_locator',
                        'field_state','value_kind','presence_basis','character_count'))
                    or page.get('offset') != offset or page.get('end') != offset + len(text)
                    or page.get('offset_basis') != 'decoded_unicode_codepoints'
                    or page.get('status') != 'PROVISIONAL'):
                raise ValueError('BOI_FIELD_PAGE_BINDING_MISMATCH')
            parts.append(text)
            next_offset = page.get('next_offset')
            if next_offset is None:
                break
            if (isinstance(next_offset, bool) or not isinstance(next_offset, int)
                    or next_offset != page['end'] or next_offset <= offset
                    or next_offset >= field['character_count']):
                raise ValueError('BOI_FIELD_PAGE_PROGRESS_INVALID')
            offset = next_offset
        result = ''.join(parts)
        if len(result) != field['character_count'] or _digest(result.encode('utf-8')) != field['content_digest']:
            raise ValueError('BOI_FIELD_INCOMPLETE_OR_CORRUPT')
        return {'text':result, 'delivery':{**binding, 'page_count':len(parts),
            'status':'DELIVERED_TO_CONSUMER', 'semantic_status':'not_evaluated', 'comprehension_proven':False}}

    async def catalog_assets(self, *, namespace: str | None = None, kind: str | None = None, reviewed_definition: dict | None = None, content_contract: str | None = None, query: str = ''):
        items, cursor, snapshot = [], '', None
        while True:
            page = await self.call('boi_knowledge_catalog', {'namespace':namespace,'kind':kind,'cursor':cursor,
                **({'query':query} if query else {}),
                **({'content_contract':content_contract} if content_contract is not None else {}),
                **({'reviewed_definition':reviewed_definition} if reviewed_definition is not None else {})})
            if reviewed_definition is not None and page.get('reviewed_definition')!=reviewed_definition:
                raise ValueError('BOI_KNOWLEDGE_CATALOG_BINDING_MISMATCH')
            if query and page.get('query')!=query.strip():
                raise ValueError('BOI_KNOWLEDGE_CATALOG_BINDING_MISMATCH')
            if content_contract is not None and (page.get('content_contract')!=content_contract
                    or any(item.get('content_contract')!=content_contract for item in page.get('items',[]))):
                raise ValueError('BOI_KNOWLEDGE_CATALOG_BINDING_MISMATCH')
            if page.get('status') != 'PROVISIONAL' or page.get('scope_status') != 'complete':
                raise ValueError('BOI_KNOWLEDGE_CATALOG_SCOPE_INCOMPLETE')
            if snapshot is None:
                snapshot = page['snapshot_digest']
            if page['snapshot_digest'] != snapshot or any((namespace is not None and item.get('namespace') != namespace)
                    or item.get('canonical_projection_eligible') is not False for item in page['items']):
                raise ValueError('BOI_KNOWLEDGE_CATALOG_BINDING_MISMATCH')
            items.extend(page['items'])
            next_cursor = page.get('next_cursor')
            if next_cursor is None:
                break
            if next_cursor == cursor or not page['items']:
                raise ValueError('BOI_KNOWLEDGE_CATALOG_PROGRESS_INVALID')
            cursor = next_cursor
        if len(items) != page['total_count'] or len({(item['namespace'],item['logical_id']) for item in items}) != len(items):
            raise ValueError('BOI_KNOWLEDGE_CATALOG_INCOMPLETE')
        return {**page,'items':items,'next_cursor':None}

    async def read_meaning_index(self, revision):
        """Candidates include exact recorded_judgments when unambiguous.

        The current preparation still admits their use. Consumers needing the
        original review order can use restore_review_meaning_selection_view;
        this projection never requires a second source or review read.
        """
        return await self.call('boi_knowledge_read', {'revision':revision,'view':'meaning_index'})

    async def read_meaning_sources(self, revision, *, meaning_pointers):
        return await self.call('boi_knowledge_read', {'revision':revision,'view':'definition_sources',
            'meaning_pointers':list(meaning_pointers)})

    async def read_asset(self, revision, *, source_field_refs=()):
        from boi_api.app.governed_runtime.task_knowledge import TaskAssetRevision
        result = await self.call('boi_knowledge_read', {'revision':revision,'lane':'provisional','view':'asset',
            **({'source_field_refs':list(source_field_refs)} if source_field_refs else {})})
        asset = TaskAssetRevision.model_validate(result['asset'])
        if (result.get('revision') != revision or asset.revision.model_dump(mode='json') != revision
                or asset.authority != 'candidate' or result.get('status') != 'PROVISIONAL'
                or result.get('canonical_projection_eligible') is not False):
            raise ValueError('BOI_KNOWLEDGE_REVISION_BINDING_MISMATCH')
        return result

    async def profile_intake_material(self, *, domain: str | None = None):
        """Read current authorized Profile bodies and server package admissions.

        The package policy limits availability. The model still has to compare
        semantic coverage and cannot treat admission as identity.
        """
        from .boi_profile_intake_router import (available_profile_catalog_from_package_admissions,
            available_profiles_from_package_admissions)
        # Resolve package admissions first, then read only their exact namespaces.
        # A principal may correctly receive ``restricted`` for a global owned
        # catalog because unrelated assets are hidden. That must not prevent a
        # complete read of every explicitly admitted Profile namespace.
        packages=await self.read_domain_packages()
        entries=[item.get('manifest') for item in packages.get('items') or []
                 if isinstance(item,dict) and isinstance(item.get('manifest'),dict)]
        if domain is not None:
            from agent_kit.package_contract import dependency_order
            relevant=dependency_order(entries,[domain])
        else:
            relevant=entries
        namespaces=sorted({item.get('namespace') for package in relevant
            for item in package.get('profile_admissions') or ()
            if isinstance(item,dict) and isinstance(item.get('namespace'),str)})
        if not namespaces:
            raise ValueError('PROFILE_ROUTE_PACKAGE_ADMISSIONS_EMPTY')
        pages=[await self.catalog_assets(namespace=namespace,kind='profile')
               for namespace in namespaces]
        from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
        catalog={'items':[item for page in pages for item in page['items']],
            'snapshot_digest':semantic_digest(
                [{'namespace':namespace,'snapshot_digest':page['snapshot_digest']}
                 for namespace,page in zip(namespaces,pages)]),
            'scope_status':'complete'}
        assets=[]
        for item in catalog['items']:
            revision=item.get('revision') or item.get('content_revision')
            if not isinstance(revision,dict):
                raise ValueError('PROFILE_ROUTE_CATALOG_REVISION_REQUIRED')
            read=await self.read_asset(revision)
            asset=read['asset']
            try:declaration=json.loads(asset['content_json'])
            except (ValueError,TypeError) as exc:
                raise ValueError('PROFILE_ROUTE_DECLARATION_JSON_REQUIRED') from exc
            assets.append({'revision':revision,'namespace':asset['namespace'],
                'logical_id':asset['logical_id'],'declaration':declaration})
        # Shipped package Profiles are visible through the package contract even
        # when another principal owns the matching provisional Profile asset.
        # If both are visible their bodies must agree exactly.
        keyed={(item['namespace'],item['declaration'].get('profile_id')):item for item in assets}
        for package in relevant:
            for item in package.get('profile_declarations') or ():
                declaration=item['declaration'];key=(item['namespace'],item['profile_id'])
                digest=semantic_digest(declaration)
                embedded={'revision':{'ref':'KnowledgeRevision:'+digest,'revision_digest':digest},
                    'namespace':item['namespace'],
                    'logical_id':'package-profile:'+package['id']+':'+item['profile_id'],
                    'declaration':declaration}
                prior=keyed.get(key)
                if prior is not None:
                    if semantic_digest(prior['declaration'])!=digest:
                        raise ValueError('PROFILE_ROUTE_PROFILE_PACKAGE_DRIFT')
                    continue
                assets.append(embedded);keyed[key]=embedded
        if domain is None:
            available,receipt=available_profile_catalog_from_package_admissions(
                profile_assets=assets,package_catalog=entries)
        else:
            available,receipt=available_profiles_from_package_admissions(
                profile_assets=assets,package_catalog=entries,domain=domain)
        return {'profiles':[item.model_dump(mode='json') for item in available],
            'admission':receipt,'catalog_snapshot_digest':catalog.get('snapshot_digest'),
            'profile_catalog_scope_status':catalog.get('scope_status'),
            'package_scope_key':packages.get('scope_key')}

    async def propose_asset(self, draft, *, idempotency_key: str):
        from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
        result = await self.call('boi_knowledge_propose', {'draft':draft,'idempotency_key':idempotency_key})
        if (result.get('logical_id') != draft['logical_id'] or result.get('namespace') != draft['namespace']
                or result.get('source_manifest_digest') != source_manifest_digest(draft['sources'])
                or result.get('status') != 'PROVISIONAL' or result.get('semantic_status') != 'not_evaluated'
                or result.get('canonical_projection_eligible') is not False):
            raise ValueError('BOI_KNOWLEDGE_PROPOSAL_BINDING_MISMATCH')
        return result

    async def restore_task_knowledge(self, reading_ref, sources, *, principal_id, policy_digest):
        from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext
        from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
        value=await self.call('boi_task_knowledge_restore',{'reading_ref':reading_ref,'sources':sources})
        context=TaskKnowledgeContext.model_validate(value['context'])
        ack=value['acknowledgement']
        expected={'reading_ref':reading_ref,'employee_id':principal_id,'policy_digest':policy_digest,
            'context_digest':context.context_digest,'source_manifest_digest':source_manifest_digest(sources),
            'status':'acknowledged_complete','approved':False,'canonical_projection_eligible':False}
        if (any(ack.get(k)!=v for k,v in expected.items()) or value.get('reading_ref')!=reading_ref
                or value.get('new_receipt_created') is not False or value.get('new_execution_authorized') is not False
                or context.principal_id!=principal_id or context.policy_digest!=policy_digest
                or context.source_manifest_digest!=expected['source_manifest_digest']):
            raise ValueError('BOI_TASK_KNOWLEDGE_RESTORE_MISMATCH')
        return value

    async def read_task_knowledge(self, request, *, principal_id: str, policy_digest: str):
        """Complete context delivery and server acknowledgement over any MCP host.

        Expected identity/policy come from the authorized task or source record,
        not from the first unverified page. The return value is still unqualified.
        """
        from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
        from boi_api.app.governed_runtime.task_context_reading import TaskContextPage, receive_task_context
        prepared = await self.call('boi_task_knowledge_prepare', request)
        source_digest = source_manifest_digest(request['sources'])
        if (prepared.get('principal_id') != principal_id or prepared.get('policy_digest') != policy_digest
                or prepared.get('namespace') != request['namespace'] or prepared.get('purpose') != request['purpose']
                or prepared.get('source_manifest_digest') != source_digest
                or prepared.get('status') != 'PROVISIONAL' or prepared.get('canonical_projection_eligible') is not False):
            raise ValueError('BOI_TASK_KNOWLEDGE_PREPARATION_MISMATCH')
        if prepared.get('tool_use','execution') != request.get('tool_use','execution'):
            raise ValueError('BOI_TASK_KNOWLEDGE_TOOL_USE_MISMATCH')
        reading_mode = request.get('definition_reading','all')
        if (prepared.get('definition_reading','all') != reading_mode
                or (reading_mode == 'selected_dependencies'
                    and prepared.get('namespace_definition_content_complete') is not False)):
            raise ValueError('BOI_TASK_KNOWLEDGE_READING_SCOPE_MISMATCH')
        page_count = prepared.get('page_count')
        if isinstance(page_count,bool) or not isinstance(page_count,int) or page_count < 1:
            raise ValueError('BOI_TASK_KNOWLEDGE_PAGE_COUNT_INVALID')
        pages = []
        binding = {'context_ref':prepared['context_ref'],'expected_context_digest':prepared['context_digest']}
        batch_limit = prepared.get('page_batch_limit', 1)
        if isinstance(batch_limit, bool) or not isinstance(batch_limit, int) or not 1 <= batch_limit <= 8:
            raise ValueError('BOI_TASK_KNOWLEDGE_BATCH_LIMIT_INVALID')
        for index in range(0, page_count, batch_limit):
            count = min(batch_limit, page_count - index)
            result = await self.call('boi_task_knowledge_page', {**binding,'page_index':index,
                **({'page_batch_size':count} if count > 1 else {})})
            end = index + count
            if (result.get('next_page') != (end if end < page_count else None)
                    or result.get('status') != 'PROVISIONAL'):
                raise ValueError('BOI_TASK_KNOWLEDGE_PAGE_SEQUENCE_INVALID')
            chunks = result.get('pages') if count > 1 else [result.get('page')]
            if not isinstance(chunks, list) or len(chunks) != count:
                raise ValueError('BOI_TASK_KNOWLEDGE_PAGE_SEQUENCE_INVALID')
            pages.extend(TaskContextPage.model_validate(chunk) for chunk in chunks)
        delivered = receive_task_context(tuple(pages),expected_context_digest=prepared['context_digest'],
            principal_id=principal_id,policy_digest=policy_digest,purpose=request['purpose'],
            source_manifest_digest=source_digest)
        acknowledged = await self.call('boi_task_knowledge_ack', {**binding,
            'page_digests':[p.chunk_digest for p in pages]})
        expected = {'contract_version':'boi/acknowledged-domain-context@1', 'employee_id':principal_id,
            'policy_digest':policy_digest,'context_ref':prepared['context_ref'],
            'context_digest':prepared['context_digest'],'source_manifest_digest':source_digest,
            'page_digests':[p.chunk_digest for p in pages],
            'delivered_revisions':[a.revision.model_dump(mode='json') for a in delivered.context.assets],
            'status':'acknowledged_complete','comprehension_proven':False,'semantic_equivalence_decided':False,
            'canonical_scope':prepared['canonical_scope'],'approved':False,'canonical_projection_eligible':False}
        if 'definition_reading' in prepared:
            expected.update({key:prepared[key] for key in
                ('definition_reading','namespace_definition_content_complete')})
        if any(acknowledged.get(key) != value for key,value in expected.items()) or not acknowledged.get('reading_ref'):
            raise ValueError('BOI_TASK_KNOWLEDGE_ACKNOWLEDGEMENT_MISMATCH')
        return {'context':delivered.context.model_dump(mode='json'),
            'delivery':delivered.receipt.model_dump(mode='json'),'acknowledgement':acknowledged,
            'reading_ref':acknowledged['reading_ref'],'status':'PROVISIONAL'}


@asynccontextmanager
async def connect(url: str, token: str, *, read_timeout_seconds: float = 45):
    if not token.startswith('boi_pat_'):
        raise ValueError('BOI_PAT_REQUIRED')
    async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token},
            timeout=httpx2.Timeout(45, read=max(60,read_timeout_seconds)), follow_redirects=False) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=float(read_timeout_seconds)) as session:
                try:
                    await session.initialize()
                except MCPError:
                    raise ValueError('BOI_MCP_CONNECTION_FAILED:PROTOCOL_ERROR') from None
                yield BoiDomainMcpClient(session)


async def _main(args):
    async with connect(args.mcp_url, os.getenv('BOI_PAT', '')) as client:
        if args.command == 'capture':
            raw = Path(args.path).read_bytes()
            reference = await client.capture(raw, media_type=args.media_type, role=args.role,
                idempotency_key=args.idempotency_key)
            result = {'reference':reference, 'projection':await client.project(reference)}
        elif args.command == 'read-field':
            material = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
            field = next(f for f in material['projection']['fields'] if f['span_ref'] == args.span_ref)
            result = await client.read_complete_field(material['reference'], field)
        elif args.command == 'catalog':
            result = await client.catalog_assets(namespace=args.namespace,kind=args.kind)
        elif args.command == 'read-asset':
            result = await client.read_asset(json.loads(Path(args.reference).read_text(encoding='utf-8')))
        elif args.command == 'propose':
            result = await client.propose_asset(json.loads(Path(args.draft).read_text(encoding='utf-8')),
                idempotency_key=args.idempotency_key)
        else:
            result = await client.read_task_knowledge(json.loads(Path(args.request).read_text(encoding='utf-8')),
                principal_id=args.principal_id,policy_digest=args.policy_digest)
        # stdout is an explicit consumer output, not an audit or logging sink.
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description='BoI source intake over MCP; output stays PROVISIONAL.')
    parser.add_argument('--mcp-url', default=os.getenv('BOI_MCP_URL', 'http://localhost:8200/mcp/v2'))
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('path')
    capture.add_argument('--media-type', required=True, choices=['application/json','application/yaml','text/csv','text/plain','application/sql'])
    capture.add_argument('--role', default='corporate_metadata', choices=['corporate_metadata','authoritative_document','schema','sql'])
    capture.add_argument('--idempotency-key', required=True)
    read = sub.add_parser('read-field')
    read.add_argument('manifest')
    read.add_argument('span_ref')
    catalog = sub.add_parser('catalog')
    catalog.add_argument('namespace')
    catalog.add_argument('--kind')
    asset = sub.add_parser('read-asset')
    asset.add_argument('reference')
    propose = sub.add_parser('propose')
    propose.add_argument('draft')
    propose.add_argument('--idempotency-key',required=True)
    context = sub.add_parser('read-context')
    context.add_argument('request')
    context.add_argument('--principal-id',required=True)
    context.add_argument('--policy-digest',required=True)
    asyncio.run(_main(parser.parse_args()))


if __name__ == '__main__':
    main()
