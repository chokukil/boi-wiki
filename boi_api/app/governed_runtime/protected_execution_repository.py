"""Durable protected execution objects; the shared Run ledger owns provenance.

Indexes are retrieval aids, not a second status ledger or canonical projection.
An interrupted dispatch is withheld rather than silently executing twice.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from .ledger import GovernedRuntimeLedger, RecordKind, sha256_id


def digest(value):
    return 'sha256:'+hashlib.sha256(encode(value)).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


class ProtectedExecutionRepository:
    def __init__(self, root: Path, ledger: GovernedRuntimeLedger):
        self.root = Path(root)
        self.ledger = ledger
        for name in ('objects', 'requests', 'executions', 'bindings', 'locks'):
            path = self.root/name
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        self.root.chmod(0o700)

    @staticmethod
    def _immutable(path, value):
        data = encode(value)
        fd, temp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ValueError('EXECUTION_IMMUTABLE_CONFLICT')
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            os.unlink(temp)

    @contextmanager
    def _locked(self, key):
        with (self.root/'locks'/key).open('a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)

    def execute_once(self, *, principal, purpose, idempotency_key, request_digest, execute):
        key = digest({'principal': principal, 'idempotency_key': idempotency_key})[7:]
        binding = {'request_digest': request_digest, 'context_digest': digest([principal, purpose])}
        with self._locked(key):
            prepared = self.root/'requests'/(key+'.prepared.json')
            completed = self.root/'requests'/(key+'.completed.json')
            if prepared.exists():
                if json.loads(prepared.read_bytes()) != binding:
                    raise ValueError('IDEMPOTENCY_CONFLICT')
                if not completed.exists():
                    raise ValueError('EXECUTION_RECOVERY_REQUIRED')
                record = self._load_index(completed)
                if record['request_digest'] != request_digest or record['context_digest'] != binding['context_digest']:
                    raise ValueError('EXECUTION_RECORD_TAMPERED')
                return record['execution']
            self._immutable(prepared, binding)
            execution = execute()
            return self._complete(completed, binding, execution.model_dump(mode='json'))

    def recover_once(self, *, principal, purpose, idempotency_key, request_digest, recover):
        """Explicitly reconcile a dispatched request using a trusted saved result.

        This never calls execute or creates a missing dispatch. The caller must
        verify its durable result and current authority; legacy unknown requests
        remain withheld without such a recovery adapter. The original prepared
        marker and any partial object/Run/index are retained.
        """
        key = digest({'principal': principal, 'idempotency_key': idempotency_key})[7:]
        binding = {'request_digest': request_digest, 'context_digest': digest([principal, purpose])}
        with self._locked(key):
            prepared = self.root/'requests'/(key+'.prepared.json')
            completed = self.root/'requests'/(key+'.completed.json')
            if not prepared.exists():
                raise ValueError('EXECUTION_DISPATCH_NOT_FOUND')
            if json.loads(prepared.read_bytes()) != binding:
                raise ValueError('IDEMPOTENCY_CONFLICT')
            if completed.exists():
                record = self._load_index(completed)
                if any(record[name] != value for name, value in binding.items()):
                    raise ValueError('EXECUTION_RECORD_TAMPERED')
                return record['execution']
            execution = recover()
            return self._complete(completed, binding, execution.model_dump(mode='json'))

    def _complete(self, completed, binding, value):
        # Called under the exact request lock. A recovered value retains its
        # original completion timestamp, so object and Run identities are stable
        # even if the earlier attempt stopped after either had been committed.
        record = {'schema': 'boi-protected-execution/v1', **binding, 'execution': value}
        object_digest = digest(record)
        self._immutable(self.root/'objects'/(object_digest[7:]+'.json'), record)
        run = self.ledger.append(RecordKind.RUN, {
            'record_type': 'durable_query_execution',
            'execution_id': value['execution_id'],
            'protected_execution_ref': 'protected:execution:'+object_digest,
            'protected_execution_digest': object_digest,
            **binding,
            'receipt_digest': value['receipt']['receipt_digest'],
            'result_digest': value['receipt']['result_digest'],
            'logical_plan_digest': value['receipt']['logical_plan_digest'],
            'result_status': 'PROVISIONAL',
        }, authority='executor', occurred_at=value['receipt']['completed_at'])
        index = {'object_digest': object_digest, 'run_record_id': run.record_id}
        self._immutable(self.root/'executions'/(value['execution_id']+'.json'), index)
        self._immutable(completed, index)
        return value

    def _load_index(self, path):
        try:
            index = json.loads(path.read_bytes())
            object_digest = index['object_digest']
            if not (object_digest.startswith('sha256:') and len(object_digest)==71
                    and all(c in '0123456789abcdef' for c in object_digest[7:])):
                raise ValueError('invalid digest')
            record = json.loads((self.root/'objects'/(object_digest[7:]+'.json')).read_bytes())
            if digest(record) != object_digest:
                raise ValueError('object hash mismatch')
            ledger_record = self.ledger.read(index['run_record_id'])
            raw_record = json.loads(ledger_record.path.read_bytes())
            envelope = {k:raw_record[k] for k in ('schema','kind','authority','occurred_at','payload')}
            if sha256_id(RecordKind.RUN, envelope) != ledger_record.record_id:
                raise ValueError('ledger hash mismatch')
            expected = ledger_record.payload
            execution = record['execution']
            receipt = execution['receipt']
            if (ledger_record.authority != 'executor' or expected['record_type'] != 'durable_query_execution'
                or expected['protected_execution_digest'] != object_digest
                or expected['execution_id'] != execution['execution_id']
                or expected['request_digest'] != record['request_digest']
                or expected['context_digest'] != record['context_digest']
                or expected['receipt_digest'] != receipt['receipt_digest']
                or digest({k:v for k,v in receipt.items() if k != 'receipt_digest'}) != receipt['receipt_digest']
                or execution['exploration_receipt'] != receipt):
                raise ValueError('chain mismatch')
            return record
        except Exception as error:
            raise ValueError('EXECUTION_RECORD_TAMPERED') from error

    def get(self, execution_id):
        try:
            if str(uuid.UUID(execution_id)) != execution_id: return None
        except (ValueError, TypeError): return None
        path = self.root/'executions'/(execution_id+'.json')
        if not path.exists(): return None
        record = self._load_index(path)
        if record['execution']['execution_id'] != execution_id:
            raise ValueError('EXECUTION_RECORD_TAMPERED')
        return record['execution']

    def store_binding(self, value):
        binding_digest = digest(value)
        self._immutable(self.root/'bindings'/(binding_digest[7:]+'.json'), value)
        return binding_digest

    def validate_bindings(self, receipt):
        for item in receipt.result_set_receipts:
            if not item.execution_artifact_ref.startswith('protected:sqlite-sql:'):
                continue  # Snapshot paging validates its own protected query envelope.
            try:
                value = json.loads((self.root/'bindings'/(item.execution_artifact_digest[7:]+'.json')).read_bytes())
                if digest(value) != item.execution_artifact_digest:
                    raise ValueError('binding mismatch')
            except Exception as error:
                raise ValueError('EXECUTION_BINDING_UNAVAILABLE_OR_TAMPERED') from error
