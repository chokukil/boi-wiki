#!/usr/bin/env python3
"""Portable official SDK2 transport; no repository imports, models or retries."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

import httpx2
from mcp import ClientSession, MCPError
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, ListToolsResult, PaginatedRequestParams


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



class BoiMcpToolError(ValueError):
    def __init__(self, reason_code=None, *, recovery=None):
        super().__init__('BOI_MCP_TOOL_ERROR_RECEIVED')
        self.reason_code = reason_code
        self.recovery = recovery


def tool_reason(result, name):
    """Expose a bounded operational code, never arbitrary server/source text."""
    value = result.structured_content
    candidates = []
    if isinstance(value, dict):
        candidates.append(value.get('reason_code'))
        if isinstance(value.get('detail'), dict):
            candidates.append(value['detail'].get('reason_code'))
    texts = [block.text for block in result.content if block.type == 'text']
    if len(texts) == 1:
        prefix = "Error calling tool '" + name + "': "
        candidates.append(texts[0].removeprefix(prefix))
    for candidate in candidates:
        if isinstance(candidate, str) and re.fullmatch(r'[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+', candidate) and len(candidate) <= 160:
            return candidate
    return None


class BoiMcpClient:
    def __init__(self, session):
        self.session = session

    async def call(self, name, arguments):
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            raise ValueError('BOI_MCP_REQUEST_INVALID')
        try:
            result = await self.session.call_tool(name, arguments)
        except MCPError:
            raise ValueError('BOI_MCP_PROTOCOL_UNKNOWN_READ_STATUS') from None
        if not isinstance(result, CallToolResult):
            raise ValueError('BOI_MCP_RESPONSE_UNKNOWN_READ_STATUS')
        if result.is_error:
            reason=tool_reason(result, name)
            detail=result.structured_content
            status=detail.get('status_code') if isinstance(detail,dict) else None
            if reason in CONCEPT_RECOVERY_ACTIONS and status != 409:reason=None
            raise BoiMcpToolError(reason,recovery=concept_recovery(status,reason))
        value = result.structured_content
        if value is None:
            texts = [block.text for block in result.content if block.type == 'text']
            if len(texts) != 1:
                raise ValueError('BOI_MCP_RESPONSE_UNKNOWN_READ_STATUS')
            value = json.loads(texts[0])
        if not isinstance(value, dict):
            raise ValueError('BOI_MCP_RESPONSE_UNKNOWN_READ_STATUS')
        return value

    async def describe_tool(self, name):
        cursor = None
        seen = set()
        while True:
            try:
                result = await self.session.list_tools(params=PaginatedRequestParams(cursor=cursor) if cursor is not None else None)
            except MCPError:
                raise ValueError('BOI_MCP_PROTOCOL_UNKNOWN_READ_STATUS') from None
            if not isinstance(result, ListToolsResult):
                raise ValueError('BOI_MCP_RESPONSE_UNKNOWN_READ_STATUS')
            for tool in result.tools:
                if tool.name == name:
                    return {'operation': 'describe_tool', 'tool': tool.model_dump(mode='json', by_alias=True, exclude_none=True)}
            cursor = result.next_cursor
            if cursor is None:
                raise BoiMcpToolError('BOI_MCP_TOOL_NOT_DISCOVERED')
            if cursor in seen:
                raise ValueError('BOI_MCP_DISCOVERY_CURSOR_REPEATED')
            seen.add(cursor)

    async def knowledge_work(self, operation, request=None):
        return await self.call('boi_knowledge_work', {
            'operation': operation, 'request': {} if request is None else request})


@asynccontextmanager
async def connect(url, token, *, read_timeout_seconds=45):
    parsed = urlsplit(url)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('BOI_MCP_URL_INVALID')
    if not token.startswith('boi_pat_') or '\n' in token or '\r' in token:
        raise ValueError('BOI_PAT_REQUIRED')
    if not 0 < read_timeout_seconds <= 60:
        raise ValueError('BOI_MCP_TIMEOUT_INVALID')
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + token},
            timeout=httpx2.Timeout(45, read=60), follow_redirects=False, trust_env=False) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=float(read_timeout_seconds)) as session:
                try:
                    await session.initialize()
                except MCPError:
                    raise ValueError('BOI_MCP_CONNECTION_FAILED') from None
                yield BoiMcpClient(session)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('BOI_MCP_URL'))
    parser.add_argument('--token-env', default='BOI_PAT')
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--tool')
    operation.add_argument('--describe-tool', help='Read the named tool inputSchema via official MCP tools/list; does not call the tool')
    parser.add_argument('--request-file', type=Path)
    parser.add_argument('--state-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.tool) != bool(args.request_file):
        parser.error('--request-file is required only with --tool')
    journal = None
    record = {}
    try:
        request = json.loads(args.request_file.read_text()) if args.tool else {'name': args.describe_tool}
        if not isinstance(request, dict):
            raise ValueError('BOI_MCP_REQUEST_INVALID')
        raw = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        record = {'tool': args.tool, 'request': request,
                  'operation': 'call_tool' if args.tool else 'describe_tool',
                  'request_digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
                  'status': 'prepared', 'automatic_retry': False}
        args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        journal = args.state_dir / (uuid.uuid4().hex + '.json')
        with journal.open('x') as stream:
            os.chmod(journal, 0o600)
            json.dump(record, stream, ensure_ascii=False, indent=2)

        async def run():
            async with connect(args.url or '', os.environ.get(args.token_env, '')) as client:
                # Catch received errors inside the SDK task group so cleanup
                # cannot wrap them in a transport-style exception group.
                try:
                    return (await client.call(args.tool, request) if args.tool
                            else await client.describe_tool(args.describe_tool))
                except BoiMcpToolError as error:
                    return error
        result = asyncio.run(run())
        if isinstance(result, BoiMcpToolError):
            raise result
        record.update(status='response_received', response=result)
        journal.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BoiMcpToolError as error:
        record.update(status='tool_error_received', reason_code=error.reason_code, recovery=error.recovery,
                      execution_state='not_inferred_from_tool_error', automatic_retry=False,
                      next_action='inspect_reason_and_current_contract; read_current_status_before_mutation_redelivery')
        if journal is not None:
            journal.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        import sys
        print(json.dumps({'error': str(error), 'reason_code': error.reason_code,
                          'status': record['status'], 'next_action': record['next_action'], 'recovery':error.recovery}), file=sys.stderr)
        return 1
    except Exception:
        # A connection/protocol error or a lost acknowledgement is not rollback.
        # The retained exact request and a new status read drive recovery.
        record.update(status='outcome_unknown', automatic_retry=False,
                      next_action='read_current_status_before_redelivery')
        if journal is not None:
            try:
                journal.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            except OSError:
                pass
        import sys
        print(json.dumps({'error': 'BOI_MCP_FAILED_READ_STATUS_BEFORE_REDELIVERY'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
