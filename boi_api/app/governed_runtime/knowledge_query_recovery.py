"""Private request/SQL bindings for recovery, not a second execution ledger.

Records are written only under the protected repository's exact request lock.
An intent digest is sealed in the same PostgreSQL transaction as query results.
Recovery follows that exact ID; it never searches for a similar prior query.
"""
import json
import uuid

from .protected_execution_repository import digest


class KnowledgeQueryRecovery:
    def __init__(self, repository):
        self.repository = repository
        self.root = repository.root / 'prepared-knowledge-results' / 'dispatches'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    @staticmethod
    def binding(*, actor_id, set_ref, query_digest, request_digest, idempotency_key):
        return {'contract_version': 'boi/prepared-knowledge-dispatch@1',
            'request_key': digest({'principal': actor_id, 'idempotency_key': idempotency_key})[7:],
            'actor_id': actor_id, 'set_ref': set_ref, 'query_digest': query_digest, 'request_digest': request_digest}

    def _path(self, binding, kind):
        key = binding['request_key']
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('KNOWLEDGE_QUERY_RECOVERY_BINDING_INVALID')
        return self.root / (key + '.' + kind + '.json')

    def _read(self, binding, kind):
        try:
            return json.loads(self._path(binding, kind).read_bytes())
        except (OSError, ValueError):
            raise ValueError('KNOWLEDGE_QUERY_RECOVERY_RECORD_UNAVAILABLE') from None

    def begin(self, binding):
        value = {**binding, 'execution_id': str(uuid.uuid4())}
        self.repository._immutable(self._path(binding, 'dispatch'), value)
        return value

    def dispatch(self, binding):
        value = self._read(binding, 'dispatch')
        try:
            identity = value['execution_id']
            valid = str(uuid.UUID(identity)) == identity and value == {**binding, 'execution_id': identity}
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError('KNOWLEDGE_QUERY_RECOVERY_BINDING_INVALID')
        return value

    def bind_intent(self, dispatch, fence):
        value = {'contract_version': 'boi/prepared-knowledge-query-intent@1', 'dispatch': dispatch, 'fence': fence}
        self.repository._immutable(self._path(dispatch, 'intent'), value)
        return digest(value)

    def intent(self, dispatch):
        value = self._read(dispatch, 'intent')
        if (not isinstance(value, dict) or set(value) != {'contract_version', 'dispatch', 'fence'}
                or value['contract_version'] != 'boi/prepared-knowledge-query-intent@1' or value['dispatch'] != dispatch
                or not isinstance(value['fence'], dict)):
            raise ValueError('KNOWLEDGE_QUERY_RECOVERY_BINDING_INVALID')
        return value

    def seal_result(self, dispatch, execution):
        value = execution.model_dump(mode='json')
        record = {'dispatch': dispatch, 'execution': value, 'execution_digest': digest(value)}
        self.repository._immutable(self._path(dispatch, 'result'), record)
        return execution

    def result(self, dispatch):
        path = self._path(dispatch, 'result')
        if not path.exists():
            return None
        value = self._read(dispatch, 'result')
        if (not isinstance(value, dict) or set(value) != {'dispatch', 'execution', 'execution_digest'}
                or value['dispatch'] != dispatch or digest(value['execution']) != value['execution_digest']):
            raise ValueError('KNOWLEDGE_QUERY_RECOVERY_RESULT_CHANGED')
        return value['execution']
