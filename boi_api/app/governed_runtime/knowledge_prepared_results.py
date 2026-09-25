"""Protected native SQL results, sparse paging and current-authority reuse.

The existing repository owns durable execute-once and unknown recovery. Count
requests retain four counts only; object pages read sealed known membership and
the unchanged population complement. Source truth/access is never conferred.
"""
from datetime import datetime, timezone
import math
import json
import os
import secrets
import time
from typing import Literal

from pydantic import JsonValue

from .knowledge_evidence_set_sql import STATES
from .knowledge_prepared_queries import KnowledgePreparedQueries
from .knowledge_projection_contract import ProjectionContract, ProjectionRevision
from .knowledge_query import KnowledgeEvidenceQuery
from .knowledge_query_results import KnowledgeQueryResultService
from .knowledge_query_recovery import KnowledgeQueryRecovery
from .knowledge_saved_sets import KnowledgeSavedSets
from .protected_execution_repository import ProtectedExecutionRepository, digest
from .semantic_binding_contract import semantic_digest


PREFIX = 'protected:prepared-knowledge-query:'
CONTRACT = 'boi/protected-prepared-knowledge-execution@1'
PURPOSE = 'prepared-knowledge-evidence-query'


class SavedPreparedExecution(ProjectionContract):
    contract_version: Literal['boi/protected-prepared-knowledge-execution@1'] = CONTRACT
    execution_id: str
    actor_id: str
    set_ref: str
    query: dict[str, JsonValue]
    result: dict[str, JsonValue]
    fence: dict[str, JsonValue] | None
    storage_receipt: dict[str, JsonValue] | None
    receipt: dict[str, JsonValue]
    exploration_receipt: dict[str, JsonValue]


class KnowledgePreparedResults:
    def __init__(self, queries, repository, *, clock=time.time, cursor_ttl_seconds=900, saved_sets=None, definition_reuse_validator=None):
        if (not isinstance(queries, KnowledgePreparedQueries) or not isinstance(repository, ProtectedExecutionRepository)
                or repository.ledger is not queries.spaces.intake.ledger):
            raise ValueError('KNOWLEDGE_RESULT_CURRENT_BACKEND_REQUIRED')
        if type(cursor_ttl_seconds) is not int or not 1 <= cursor_ttl_seconds <= 86400:
            raise ValueError('KNOWLEDGE_CURSOR_TTL_INVALID')
        self.queries, self.repository = queries, repository
        self.definition_reuse_validator = definition_reuse_validator
        if saved_sets is not None and (not isinstance(saved_sets, KnowledgeSavedSets)
                or saved_sets.store is not queries.prepared.store or saved_sets.prefix != queries.prepared.prefix):
            raise ValueError('KNOWLEDGE_RESULT_CURRENT_BACKEND_REQUIRED')
        self.saved = saved_sets if saved_sets is not None else KnowledgeSavedSets(queries.prepared)
        self.clock, self.ttl = clock, cursor_ttl_seconds
        root = repository.root / 'prepared-knowledge-results'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        key = root / 'cursor-key'
        with repository._locked('prepared-knowledge-cursor-key'):
            if not key.exists():
                with key.open('xb') as handle:
                    handle.write(secrets.token_bytes(32)); handle.flush(); os.fsync(handle.fileno())
                key.chmod(0o600)
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(fd)
                finally: os.close(fd)
            self.key = key.read_bytes()
        if len(self.key) != 32:
            raise ValueError('KNOWLEDGE_CURSOR_KEY_INVALID')
        self.recovery = KnowledgeQueryRecovery(repository)

    # Reuse the established canonical HMAC wire and bounded signature parser;
    # this class owns a separate key and a different, result-bound cursor shape.
    _cursor = KnowledgeQueryResultService._cursor
    _cursor_value = KnowledgeQueryResultService._cursor_value

    def _check_definition_reuse(self, query):
        query = KnowledgeEvidenceQuery.model_validate(query)
        if query.reuse_context is not None:
            if not callable(self.definition_reuse_validator):
                raise ValueError('KNOWLEDGE_REUSE_CURRENT_READER_REQUIRED')
            self.definition_reuse_validator(query)

    def _request(self, *, actor_id, set_ref, query, idempotency_key):
        self.queries.spaces._actor(actor_id)
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240:
            raise ValueError('KNOWLEDGE_QUERY_IDEMPOTENCY_REQUIRED')
        query = KnowledgeEvidenceQuery.model_validate(query.model_dump(mode='json') if hasattr(query, 'model_dump') else query)
        self._check_definition_reuse(query)
        request_digest = semantic_digest({'contract_version': CONTRACT, 'actor_id': actor_id,
                                         'set_ref': set_ref, 'query': query.model_dump(mode='json')})
        internal_key = PURPOSE + ':' + idempotency_key
        binding = self.recovery.binding(actor_id=actor_id, set_ref=set_ref, query_digest=semantic_digest(query),
                                        request_digest=request_digest, idempotency_key=internal_key)
        return query, request_digest, internal_key, binding

    @staticmethod
    def _stored_result(observation):
        result = {key: value for key, value in observation.result.items() if key != 'rows'}
        return {**result, 'execution_state': 'stored',
            'counts': {r['state']: r['count'] for r in observation.result['rows']}, 'semantic_truth_proven': False}

    @staticmethod
    def _failure_result(reason, query):
        if (not isinstance(reason, str) or len(reason) > 120 or not reason.startswith(('KNOWLEDGE_', 'PROJECTION_'))
                or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in reason)):
            reason = 'KNOWLEDGE_QUERY_VALIDATION_FAILED'
        return {'execution_state': 'failed', 'query_digest': semantic_digest(query), 'counts': None,
            'coverage': None, 'reason_code': reason, 'semantic_truth_proven': False,
            'population_completeness_qualified': False, 'source_access_granted': False}

    @staticmethod
    def _execution(dispatch, query, result, fence, storage, completed_at):
        if storage and storage.get('statement_witnesses'):
            result = {**result, 'evidence_details':'saved_statement_witnesses; exact source reads require current source authority'}
        receipt = {'contract_version': 'boi/prepared-knowledge-execution-receipt@1',
            'completed_at': completed_at, 'logical_plan_digest': semantic_digest(query),
            'request_digest': dispatch['request_digest'], 'result_digest': digest(result),
            'fence_digest': digest(fence), 'storage_receipt_digest': digest(storage)}
        receipt['receipt_digest'] = digest(receipt)
        return SavedPreparedExecution(execution_id=dispatch['execution_id'], actor_id=dispatch['actor_id'],
            set_ref=dispatch['set_ref'], query=query.model_dump(mode='json'), result=result,
            fence=fence, storage_receipt=storage, receipt=receipt, exploration_receipt=receipt)

    def execute(self, *, actor_id, set_ref, query, idempotency_key):
        query, request_digest, internal_key, binding = self._request(actor_id=actor_id, set_ref=set_ref,
                                                                  query=query, idempotency_key=idempotency_key)
        def run():
            dispatch = self.recovery.begin(binding)
            fence, storage = None, None
            def materialize(relation, compiled, *, page, fence):
                recovery_binding = self.recovery.bind_intent(dispatch, fence)
                return self.saved.materialize(execution_id=dispatch['execution_id'], actor_id=actor_id,
                    query=query, relation=relation, compiled=compiled, page=page,
                    recovery_binding=recovery_binding, clock=self.clock)
            try:
                observation = self.queries.observe(actor_id=actor_id, set_ref=set_ref, query=query,
                                                   materialize=materialize)
                storage = self.saved.receipt(dispatch['execution_id'])
                fence = observation.fence
                result = self._stored_result(observation)
                completed_at = storage['completed_at']
            except ValueError as error:
                result = self._failure_result(str(error), query)
                fence, storage = None, None
                completed_at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
            return self.recovery.seal_result(dispatch, self._execution(dispatch, query, result, fence, storage, completed_at))
        value = self.repository.execute_once(principal=actor_id, purpose=PURPOSE,
            idempotency_key=internal_key, request_digest=request_digest, execute=run)
        self._checked(value, actor_id)
        return self._summary(value)

    def recover(self, *, actor_id, set_ref, query, idempotency_key):
        query, request_digest, internal_key, binding = self._request(actor_id=actor_id, set_ref=set_ref,
                                                                  query=query, idempotency_key=idempotency_key)
        def restore():
            dispatch = self.recovery.dispatch(binding)
            candidate = self.recovery.result(dispatch)
            if candidate is not None and candidate.get('result', {}).get('execution_state') == 'failed':
                result = self._failure_result(candidate['result'].get('reason_code'), query)
                recovered = self._execution(dispatch, query, result, None, None, candidate['receipt']['completed_at'])
            else:
                intent = self.recovery.intent(dispatch)
                storage = self.saved.receipt(dispatch['execution_id'])
                fence = intent['fence']
                if (storage.get('recovery_binding') != digest(intent) or storage['query_digest'] != binding['query_digest']
                        or storage['actor_id'] != actor_id or storage['operation'] != query.operation
                        or fence.get('actor_id') != actor_id or fence.get('set_ref') != set_ref
                        or fence.get('query_digest') != binding['query_digest'] or not storage.get('completed_at')):
                    raise ValueError('KNOWLEDGE_QUERY_RECOVERY_BINDING_INVALID')
                observed = self.queries.finish_observation(actor_id=actor_id, fence=fence, coverage=storage['coverage'],
                    output=[{'state': state, 'count': storage['counts'][state]} for state in STATES])
                recovered = self._execution(dispatch, query, self._stored_result(observed), fence, storage, storage['completed_at'])
            if candidate is not None and candidate != recovered.model_dump(mode='json'):
                raise ValueError('KNOWLEDGE_QUERY_RECOVERY_RESULT_CHANGED')
            self._checked(recovered.model_dump(mode='json'), actor_id)
            return self.recovery.seal_result(dispatch, recovered)
        value = self.repository.recover_once(principal=actor_id, purpose=PURPOSE,
            idempotency_key=internal_key, request_digest=request_digest, recover=restore)
        self._checked(value, actor_id)
        return self._summary(value)

    def _checked(self, value, actor_id, *, historical=False):
        self.queries.spaces._actor(actor_id)
        if value.get('contract_version') != CONTRACT or value.get('actor_id') != actor_id:
            raise ValueError('KNOWLEDGE_RESULT_ACCESS_DENIED')
        receipt = value['receipt']
        if (receipt.get('receipt_digest') != digest({k: v for k, v in receipt.items() if k != 'receipt_digest'})
                or value['exploration_receipt'] != receipt
                or digest(value['result']) != receipt['result_digest'] or digest(value['fence']) != receipt['fence_digest']
                or digest(value['storage_receipt']) != receipt['storage_receipt_digest']
                or semantic_digest(value['query']) != receipt['logical_plan_digest']):
            raise ValueError('KNOWLEDGE_RESULT_BINDING_INVALID')
        self._check_definition_reuse(value['query'])
        if value['result']['execution_state'] == 'failed':
            if value['fence'] is not None or value['storage_receipt'] is not None or value['result']['counts'] is not None:
                raise ValueError('KNOWLEDGE_RESULT_BINDING_INVALID')
            return
        fence = value['fence']
        if (not fence or fence['query_digest'] != receipt['logical_plan_digest'] or fence['set_ref'] != value['set_ref']
                or value['result']['counts'] != value['storage_receipt']['counts']):
            raise ValueError('KNOWLEDGE_RESULT_BINDING_INVALID')
        check = self.queries.authorize_stored if historical else self.queries.revalidate
        check(actor_id=actor_id, fence=fence)
        if self.saved.receipt(value['execution_id']) != value['storage_receipt']:
            raise ValueError('KNOWLEDGE_RESULT_STORAGE_CHANGED')
        check(actor_id=actor_id, fence=fence)

    def _load(self, result_ref, actor_id):
        self.queries.spaces._actor(actor_id)
        if not isinstance(result_ref, str) or not result_ref.startswith(PREFIX):
            raise ValueError('KNOWLEDGE_RESULT_UNAVAILABLE')
        value = self.repository.get(result_ref.removeprefix(PREFIX))
        if value is None:
            raise ValueError('KNOWLEDGE_RESULT_UNAVAILABLE')
        self._checked(value, actor_id, historical=True)
        return value

    def witnesses(self, result_ref, *, actor_id, object_id, page_size=20, cursor=None):
        value = self._load(result_ref, actor_id)
        if type(page_size) is not int or not 1 <= page_size <= 50:
            raise ValueError('KNOWLEDGE_RESULT_WITNESS_PAGE_INVALID')
        storage = value.get('storage_receipt') or {}
        extension = storage.get('statement_witnesses')
        if not extension:
            raise ValueError('KNOWLEDGE_RESULT_WITNESSES_NOT_RECORDED')
        binding = {'contract_version':extension['contract_version'], 'result_ref':result_ref,
            'result_digest':value['receipt']['result_digest'], 'actor_id':actor_id,
            'fence_digest':value['receipt']['fence_digest'], 'object_id':object_id, 'page_size':page_size}
        after, expires = None, self.clock()+self.ttl
        if cursor is not None:
            item = self._cursor_value(cursor)
            after, expires = item.get('after_key'), item.get('expires_at')
            if (item != {**binding, 'after_key':after, 'expires_at':expires}
                    or not isinstance(after, str) or not 1 <= len(after) <= 4096
                    or type(expires) not in (int, float) or not math.isfinite(expires)):
                raise ValueError('KNOWLEDGE_CURSOR_BINDING_INVALID')
            if self.clock() >= expires:
                raise ValueError('KNOWLEDGE_CURSOR_EXPIRED')
        rows = self.saved.witnesses(execution_id=value['execution_id'], object_id=object_id,
            limit=page_size, after_key=after)
        more, rows = len(rows)>page_size, rows[:page_size]
        pointers = list(dict.fromkeys(row['meaning_pointer'] for row in rows))
        read = None
        if rows:
            revision = ProjectionRevision(ref=rows[0]['revision'],
                revision_digest=rows[0]['revision'].removeprefix('KnowledgeRevision:'))
            read = {'revision':revision.model_dump(mode='json'), 'view':'document',
                'document_options':{'meaning_pointers':pointers, 'include_sources':True}}
        self._checked(value, actor_id, historical=True)
        next_cursor = (self._cursor({**binding, 'after_key':rows[-1]['detail_key'], 'expires_at':expires})
            if more else None)
        return {**binding, 'rows':rows, 'expression':value['query']['expression'],
            'predicates':value['query']['predicates'], 'document_read':read,
            'next_cursor':next_cursor, 'cursor_expires_at':expires, 'query_reexecuted':False,
            'result_basis':'recorded_observation', 'current_use_qualification_granted':False,
            'scope':'matched source contexts; atomic effect and final AST contribution are distinct',
            'source_access_granted':False, 'semantic_truth_proven':False}

    @staticmethod
    def _summary(value):
        result = value['result']
        return {'contract_version': 'boi/prepared-knowledge-result@1', 'state': result['execution_state'],
            'result_ref': PREFIX + value['execution_id'], 'result_digest': value['receipt']['result_digest'],
            'query': value['query'],
            'counts': result['counts'], 'coverage': result['coverage'], 'reason_code': result.get('reason_code'),
            **({'statement_consumption':result['statement_consumption']}
               if 'statement_consumption' in result else {}),
            **({'evidence_details':result['evidence_details']}
               if 'evidence_details' in result else {}),
            'completed_at': value['receipt']['completed_at'], 'source_access_granted': False,
            'result_basis':'recorded_observation', 'current_use_qualification_granted':False,
            'population_completeness_qualified': False, 'semantic_truth_proven': False}

    def summary(self, result_ref, *, actor_id):
        return self._summary(self._load(result_ref, actor_id))

    def page(self, result_ref, *, actor_id, group=None, page_size=20, cursor=None,
            include_witnesses=False):
        if type(include_witnesses) is not bool:
            raise ValueError('KNOWLEDGE_RESULT_BUNDLE_FLAG_INVALID')
        if include_witnesses and (type(page_size) is not int or not 1 <= page_size <= 20):
            raise ValueError('KNOWLEDGE_RESULT_BUNDLE_PAGE_LIMIT')
        page=self._page(result_ref,actor_id=actor_id,group=group,page_size=page_size,cursor=cursor)
        if not include_witnesses:
            return page
        # Compose the same protected reads, never their authorization decisions.
        # A late failure withholds the entire response. Cursors remain explicit.
        bundle={**page,'witness_pages':[]}
        def check_size():
            if len(json.dumps(bundle,ensure_ascii=False).encode('utf-8')) > 2*1024*1024:
                raise ValueError('KNOWLEDGE_RESULT_BUNDLE_BYTES_LIMIT')
        check_size()
        for row in page['rows']:
            if 'witness_read' in row:
                bundle['witness_pages'].append(self.witnesses(result_ref,
                    actor_id=actor_id,object_id=row['id'],page_size=20))
                check_size()
        self._load(result_ref,actor_id)
        return bundle

    def _page(self, result_ref, *, actor_id, group=None, page_size=20, cursor=None):
        if group not in (*STATES, 'all', 'reported', None) or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('KNOWLEDGE_RESULT_PAGE_INVALID')
        value = self._load(result_ref, actor_id)
        summary = self._summary(value)
        if value['result']['execution_state'] == 'failed':
            return {**summary, 'rows': [], 'next_cursor': None, 'group_count': None}
        query = KnowledgeEvidenceQuery.model_validate(value['query'])
        if group is None:
            group = 'reported' if query.claim_basis == 'reported_statement_exists' else 'supported'
        if group == 'reported' and query.claim_basis != 'reported_statement_exists':
            raise ValueError('KNOWLEDGE_RESULT_PAGE_INVALID')
        if query.operation in ('count','count_reported_objects'):
            raise ValueError('KNOWLEDGE_RESULT_COUNT_HAS_NO_OBJECT_PAGE')
        fence = value['fence']
        binding = {'contract_version': 'boi/prepared-knowledge-cursor@1', 'result_ref': result_ref,
            'result_digest': summary['result_digest'], 'actor_id': actor_id,
            'fence_digest': value['receipt']['fence_digest'], 'group': group, 'page_size': page_size}
        group_count = (sum(summary['counts'].values()) if group == 'all' else
            sum(summary['counts'][state] for state in ('supported','conflicted')) if group == 'reported' else
            summary['counts'][group])
        offset, after, expires = 0, None, self.clock() + self.ttl
        if cursor is not None:
            item = self._cursor_value(cursor)
            offset, after, expires = item.get('offset'), item.get('after_key'), item.get('expires_at')
            if (item != {**binding, 'offset': offset, 'after_key': after, 'expires_at': expires}
                    or type(offset) is not int or not 0 < offset < group_count or offset % page_size
                    or not isinstance(after, str) or not 1 <= len(after) <= 2048
                    or type(expires) not in (int, float) or not math.isfinite(expires)):
                raise ValueError('KNOWLEDGE_CURSOR_BINDING_INVALID')
            if self.clock() >= expires:
                raise ValueError('KNOWLEDGE_CURSOR_EXPIRED')
        relation = None
        if group in ('all', 'unknown'):
            relation = self.queries._relation(fence['binding'], self.queries._audiences(actor_id), query,
                fence['qualification_policy_digest'], fence['checker_release_digest'])
        rows = self.saved.page(execution_id=value['execution_id'], group=group, limit=page_size,
                              after_key=after, relation=relation, query=query)
        expected = min(page_size, group_count - offset)
        if len(rows) != expected + (1 if group_count - offset > page_size else 0):
            raise ValueError('KNOWLEDGE_RESULT_PAGE_COUNT_MISMATCH')
        rows = rows[:page_size]
        rows = [{**row, 'knowledge_read': {'revision': ProjectionRevision(ref=row['revision'],
                    revision_digest=row['revision'].removeprefix('KnowledgeRevision:')).model_dump(mode='json'),
                    'lane': 'provisional', 'view': 'asset'}} for row in rows]
        rows=[{**row,'document_read':{'revision':row['knowledge_read']['revision'],'view':'document'},
            'document_url':'/knowledge/records/'+row['knowledge_read']['revision']['revision_digest'].removeprefix('sha256:')}
            for row in rows]
        if query.claim_basis == 'reported_statement_exists':
            rows = [{**row, 'has_reported_witness':row['state'] in ('supported','conflicted'),
                'document_read':{**row['document_read'], 'document_options':{'include_sources':True,'claim_limit':50}},
                'statement_detail_scope':'exact_native_source_document; SQL witness detail is not materialized in this page'}
                for row in rows]
            if (value.get('storage_receipt') or {}).get('statement_witnesses'):
                rows = [{**row, 'statement_detail_scope':'saved_statement_witnesses',
                    'witness_read':{'result_ref':result_ref, 'object_id':row['id'], 'page_size':20}}
                    if row['has_reported_witness'] else row for row in rows]
        self.queries.authorize_stored(actor_id=actor_id, fence=fence)
        next_cursor = None
        if offset + len(rows) < group_count:
            next_cursor = self._cursor({**binding, 'offset': offset + len(rows), 'after_key': rows[-1]['id'], 'expires_at': expires})
        return {**summary, 'group': group, 'group_count': group_count, 'rows': rows, 'page_digest': digest(rows),
            'next_cursor': next_cursor, 'cursor_expires_at': expires,
            'claim_basis': query.claim_basis, 'modality': query.modality, 'polarity': query.polarity,
            'time_mode': query.time_mode, 'as_of': query.model_dump(mode='json')['as_of'],
            'scenario': [v.model_dump(mode='json') for v in query.scenario]}
