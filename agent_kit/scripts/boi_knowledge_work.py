#!/usr/bin/env python3
"""Portable native Wiki task client. Python standard library; no repo imports.

This adapter transports externally authored work. It never dispatches a model,
selects domain meanings, signs execution receipts, or retries an unknown request.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

OPERATIONS = ('start', 'status', 'next', 'context', 'output', 'submit', 'reconcile', 'resume', 'schema', 'list', 'retry', 'stop', 'publication')
TASK_PATH = '/api/v2/knowledge-work'
SOURCE_PATH = '/api/v2/domain-intake/sources'
SUPERVISION_PATH = '/api/v2/knowledge-supervision'
SUPERVISION_OPERATIONS = ('list', 'read', 'correct', 'resolve', 'stop',
    'document_feedback', 'feedback_inbox', 'feedback_read')
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
INLINE_TYPES = {'text/plain', 'text/csv', 'application/json', 'application/yaml', 'application/sql'}
READ_TOOLS = {
    'boi_source_project': '/api/v2/domain-intake/project',
    'boi_source_field': '/api/v2/domain-intake/fields/read',
    'boi_source_image': '/api/v2/domain-intake/images/read',
    'boi_knowledge_catalog': '/api/v2/domain-intake/assets/catalog',
    'boi_knowledge_read': '/api/v2/domain-intake/assets/read',
    'boi_domain_packages': '/api/v2/domain-packages',
}


class WorkError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


class KnowledgeWorkClient:
    def __init__(self, base_url, token, *, timeout=60, state_dir=None, opener=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise WorkError('BOI_WORK_BASE_URL_INVALID')
        if not token or '\n' in token or '\r' in token:
            raise WorkError('BOI_WORK_TOKEN_REQUIRED')
        if not 0 < timeout <= 60:
            raise WorkError('BOI_WORK_TIMEOUT_INVALID')
        self.base_url = base_url.rstrip('/')
        self.token, self.timeout = token, timeout
        self.state_dir = Path(state_dir) if state_dir is not None else None
        self.opener = opener or build_opener(NoRedirect())

    def _post(self, path, payload, *, source_digest=None):
        raw = json_bytes(payload)
        record = {'endpoint': path, 'request_digest': digest(raw), 'status': 'prepared'}
        if source_digest is None:
            record['request'] = payload
        else:
            record['source_digest'] = source_digest
            record['idempotency_key'] = payload['idempotency_key']
        return self._request(path, raw, method='POST', headers={'Content-Type': 'application/json'}, record=record)

    def _request(self, path, raw, *, method, headers, record):
        journal = None
        if self.state_dir is not None:
            self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            journal = self.state_dir / (uuid.uuid4().hex + '.json')
            with journal.open('x', encoding='utf-8') as stream:
                os.chmod(journal, 0o600)
                json.dump(record, stream, ensure_ascii=False, indent=2)
        request = Request(self.base_url + path, data=raw, method=method, headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json', **headers})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024:
                    raise WorkError('BOI_WORK_RESPONSE_TOO_LARGE')
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise WorkError('BOI_WORK_RESPONSE_INVALID')
            record.update(status='response_received', response=result)
            return result
        except HTTPError as error:
            # Do not expose server bodies, request contents or credential-bearing URLs.
            record.update(status='http_error', http_status=error.code,
                          execution_outcome='inspect_current_task')
            try:
                detail = json.loads(error.read(65536)).get('detail', {})
                reason = detail.get('reason_code') if isinstance(detail, dict) else None
                if (isinstance(reason, str) and 0 < len(reason) <= 120
                        and all(char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for char in reason)):
                    record['reason_code'] = reason
            except (ValueError, AttributeError, OSError):
                pass
            raise WorkError('BOI_WORK_HTTP_' + str(error.code)) from None
        except (URLError, TimeoutError, OSError):
            record.update(status='transport_unknown', execution_outcome='inspect_current_task')
            raise WorkError('BOI_WORK_TRANSPORT_UNKNOWN_READ_STATUS_BEFORE_REDELIVERY') from None
        except (ValueError, UnicodeError) as error:
            record.update(status='response_unusable', execution_outcome='inspect_current_task')
            code = str(error) if isinstance(error, WorkError) else 'BOI_WORK_RESPONSE_INVALID'
            raise WorkError(code) from None
        finally:
            if journal is not None:
                try:
                    with journal.open('w', encoding='utf-8') as stream:
                        json.dump(record, stream, ensure_ascii=False, indent=2)
                except OSError:
                    raise WorkError('BOI_WORK_JOURNAL_WRITE_FAILED_READ_STATUS_BEFORE_REDELIVERY') from None

    def work(self, operation, request, *, context_view="references"):
        if operation not in OPERATIONS or not isinstance(request, dict):
            raise WorkError('BOI_WORK_OPERATION_INVALID')
        if (operation not in ('start', 'schema', 'list', 'publication')
                and (not isinstance(request.get('task_ref'), str) or not request['task_ref'].strip())):
            raise WorkError('BOI_WORK_TASK_REF_REQUIRED')
        # Server owns the versioned input schema and authorization; do not fabricate defaults.
        if context_view not in ('references', 'full'):
            raise WorkError('BOI_WORK_CONTEXT_VIEW_INVALID')
        return self._post(TASK_PATH, {'operation': operation, 'request': request,
            **({'context_view': 'full'} if context_view == 'full' else {})})

    def publication(self, phase, payload):
        if not isinstance(phase, str) or not phase or not isinstance(payload, dict):
            raise WorkError('BOI_PUBLICATION_REQUEST_INVALID')
        return self.work('publication', {'phase': phase, 'payload': payload})

    def put_chunk(self, path, raw, *, bundle_ref, object_id, offset):
        if (not isinstance(bundle_ref, str) or not re.fullmatch(r'local-bundle:sha256:[a-f0-9]{64}', bundle_ref)
                or not isinstance(object_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', object_id)
                or type(offset) is not int or offset < 0 or type(raw) is not bytes or not raw):
            raise WorkError('BOI_BUNDLE_CHUNK_ARGUMENTS_INVALID')
        expected_path = ('/api/v2/local-bundles/' + bundle_ref.removeprefix('local-bundle:sha256:')
                         + '/objects/' + object_id + '?offset=' + str(offset))
        if path != expected_path:
            raise WorkError('BOI_BUNDLE_CHUNK_PATH_MISMATCH')
        chunk_digest = digest(raw)
        return self._request(path, raw, method='PUT', headers={
            'Content-Type': 'application/octet-stream', 'Content-Length': str(len(raw)),
            'X-Boi-Chunk-Digest': chunk_digest}, record={
                'endpoint': path, 'status': 'prepared', 'bundle_ref': bundle_ref,
                'object_id': object_id, 'offset': offset, 'byte_length': len(raw),
                'chunk_digest': chunk_digest})

    def upload_bundle(self, archive, bundle_ref):
        # Explicit sibling import works in isolated Python without a checkout.
        import importlib.util
        spec = importlib.util.spec_from_file_location('boi_bundle_upload', Path(__file__).with_name('boi_bundle_upload.py'))
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        try:
            return helper.upload_bundle(self, archive, bundle_ref)
        except helper.UploadError as error:
            raise WorkError(str(error)) from None

    def read_tool(self, tool, request):
        """Exact read transport for HTTP hosts; tool names never select domain meaning."""
        if tool not in READ_TOOLS or not isinstance(request, dict):
            raise WorkError('BOI_WORK_READ_TOOL_INVALID')
        if tool == 'boi_domain_packages' and request.get('operation') not in ('discover', 'read'):
            raise WorkError('BOI_WORK_PACKAGE_READ_OPERATION_REQUIRED')
        return self._post(READ_TOOLS[tool], request)

    def supervise(self, operation, request):
        """Transport an explicit user correction; no reading resolves it."""
        if operation not in SUPERVISION_OPERATIONS or not isinstance(request, dict):
            raise WorkError('BOI_WORK_SUPERVISION_OPERATION_INVALID')
        if operation in ('list','read','correct','resolve','stop') and (
                not isinstance(request.get('task_ref'), str) or not request['task_ref'].strip()):
            raise WorkError('BOI_WORK_TASK_REF_REQUIRED')
        return self._post(SUPERVISION_PATH, {'operation': operation, 'request': request})

    def capture_file(self, path, *, media_type, role, idempotency_key):
        if not idempotency_key:
            raise WorkError('BOI_SOURCE_IDEMPOTENCY_KEY_REQUIRED')
        if media_type != XLSX and media_type not in INLINE_TYPES:
            raise WorkError('BOI_SOURCE_USE_REGISTERED_CONNECTOR')
        limit = 16 * 1024 * 1024 if media_type == XLSX else 65536
        with Path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
        if not raw or len(raw) > limit:
            raise WorkError('BOI_SOURCE_SIZE_OUTSIDE_CONTRACT')
        expected = digest(raw)
        value = self._post(SOURCE_PATH, {'source': {
            'kind': 'file_source' if media_type == XLSX else 'inline_source',
            'media_type': media_type, 'role': role,
            'content_b64': base64.b64encode(raw).decode('ascii')},
            'idempotency_key': idempotency_key}, source_digest=expected)
        if (value.get('digest') != expected or value.get('role') != role
                or not isinstance(value.get('artifact_ref'), str)):
            raise WorkError('BOI_CAPTURE_SOURCE_BINDING_MISMATCH')
        return {'kind': 'artifact_ref', **{key: value[key] for key in ('artifact_ref', 'digest', 'role')}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=(*OPERATIONS, 'capture', 'read', 'supervision', 'upload'))
    parser.add_argument('--action', choices=SUPERVISION_OPERATIONS, help='Required only for supervision')
    parser.add_argument('--base-url', default=os.environ.get('BOI_BASE_URL'))
    parser.add_argument('--token-env', default='BOI_PAT', help='Environment variable name, never the secret value')
    parser.add_argument('--request-file', type=Path, help='Exact request JSON supplied by the current task schema')
    parser.add_argument('--archive', type=Path, help='Exact admitted .boi-bundle.zip; upload only')
    parser.add_argument('--bundle-ref', help='Existing server bundle reference; upload only')
    parser.add_argument('--task-ref')
    parser.add_argument('--context-view', choices=('references','full'), default='references')
    parser.add_argument('--tool', choices=tuple(READ_TOOLS))
    parser.add_argument('--request-text')
    parser.add_argument('--sources-file', type=Path, help='JSON array of captured ArtifactEnvelope references')
    parser.add_argument('--package', action='append', dest='package_ids')
    parser.add_argument('--team-id')
    parser.add_argument('--idempotency-key')
    parser.add_argument('--expected-revision', type=int)
    parser.add_argument('--attempt-ref')
    parser.add_argument('--previous-task-ref')
    parser.add_argument('--reason')
    parser.add_argument('--recovery-reason')
    parser.add_argument('--result-file', type=Path)
    parser.add_argument('--raw-output-file', type=Path)
    parser.add_argument('--source-file', type=Path)
    parser.add_argument('--media-type')
    parser.add_argument('--role', default='corporate_metadata')
    parser.add_argument('--state-dir', type=Path, default=Path(os.environ.get(
        'BOI_WORK_STATE_DIR', str(Path.home() / '.local' / 'state' / 'boi-wiki'))))
    args = parser.parse_args(argv)
    try:
        if not args.base_url:
            raise WorkError('BOI_WORK_BASE_URL_REQUIRED')
        if (args.operation == 'supervision') != (args.action is not None):
            raise WorkError('BOI_WORK_SUPERVISION_ACTION_REQUIRED_OR_UNEXPECTED')
        client = KnowledgeWorkClient(args.base_url, os.environ.get(args.token_env), state_dir=args.state_dir)
        if args.operation == 'upload':
            if (args.archive is None or not args.bundle_ref or args.request_file or args.task_ref
                    or args.source_file or args.result_file or args.raw_output_file):
                raise WorkError('BOI_BUNDLE_UPLOAD_ARGUMENTS_REQUIRED')
            value = client.upload_bundle(args.archive, args.bundle_ref)
        elif args.archive is not None or args.bundle_ref is not None:
            raise WorkError('BOI_BUNDLE_UPLOAD_ARGUMENTS_UNEXPECTED')
        elif args.operation == 'capture':
            if not args.source_file or not args.media_type:
                raise WorkError('BOI_CAPTURE_FILE_AND_MEDIA_TYPE_REQUIRED')
            value = client.capture_file(args.source_file, media_type=args.media_type,
                                        role=args.role, idempotency_key=args.idempotency_key)
        else:
            request = json.loads(args.request_file.read_text()) if args.request_file else {}
            if not isinstance(request, dict):
                raise WorkError('BOI_WORK_REQUEST_OBJECT_REQUIRED')
            for key in ('task_ref', 'request_text', 'package_ids', 'team_id', 'idempotency_key',
                        'expected_revision', 'attempt_ref', 'previous_task_ref', 'reason', 'recovery_reason'):
                val = getattr(args, key)
                if val is not None:
                    if key in request and request[key] != val:
                        raise WorkError('BOI_WORK_REQUEST_ARGUMENT_CONFLICT')
                    request[key] = val
            for key, path in (('sources', args.sources_file), ('result', args.result_file)):
                if path is not None:
                    if key in request:
                        raise WorkError('BOI_WORK_REQUEST_ARGUMENT_CONFLICT')
                    request[key] = json.loads(path.read_text())
            if args.raw_output_file is not None:
                if 'raw_output' in request:
                    raise WorkError('BOI_WORK_REQUEST_ARGUMENT_CONFLICT')
                request['raw_output'] = args.raw_output_file.read_text()
            value = (client.read_tool(args.tool, request) if args.operation == 'read'
                     else client.supervise(args.action, request) if args.operation == 'supervision'
                     else client.work(args.operation, request, context_view=args.context_view))
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (WorkError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, WorkError) else 'BOI_WORK_LOCAL_INPUT_INVALID'
        print(json.dumps({'error': code}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
