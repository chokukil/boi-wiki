"""One durable builtin check on a current published revision; unknowns stay unknown."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os

from .immutable_io import publish_immutable
from .ledger import RecordKind, record_digest
from .local_bundle_checks import CHECKS
from .native_knowledge_checks import NativeKnowledgeChecks
from .native_mechanical_records import NativeMechanicalRecords
from .semantic_binding_contract import RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite


class PublishedNativeChecks(NativeMechanicalRecords):
    def __init__(self, context):
        self.context=context
        self.intake,self.store=context.spaces.intake,context.spaces.store
        self.root=self.intake.objects.root.parent/'published-native-checks'

    @contextmanager
    def _locked(self,key):
        directory=self.root/semantic_digest(key).removeprefix('sha256:')
        for path in (self.root,directory):
            path.mkdir(mode=0o700,parents=True,exist_ok=True)
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise ValueError('KNOWLEDGE_REFRESH_PRIVATE_STORAGE_REQUIRED')
        fd=os.open(directory/'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield directory
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    def _cas(self,key,before,after):
        if not self.store.atomic_compare_and_write((*self.context.fences(),AtomicWrite(CHECKS,key,before,after))):
            raise ValueError('KNOWLEDGE_REFRESH_CHECK_STATE_CHANGED')

    def execute(self, binding, release):
        key='native-mechanical-execution:'+semantic_digest(binding)
        with self._locked(key) as directory:
            self.context.fences()
            saved=self.store.get(CHECKS,key)
            if saved and saved.get('input')!=binding:
                raise ValueError('KNOWLEDGE_REFRESH_CHECK_BINDING_CHANGED')
            marker=directory/'completion.json'
            if marker.is_symlink():
                raise ValueError('KNOWLEDGE_REFRESH_PRIVATE_STORAGE_REQUIRED')
            if saved and saved['state']!='completed' and marker.exists():
                if marker.stat().st_size>65536:
                    raise ValueError('KNOWLEDGE_REFRESH_CHECK_MARKER_INVALID')
                completed=json.loads(marker.read_bytes())
                self._receipt(completed,binding)
                if completed['run_ref']!=saved['run_ref']:
                    raise ValueError('KNOWLEDGE_REFRESH_CHECK_BINDING_CHANGED')
                self._cas(key,saved,completed)
                saved=self.store.get(CHECKS,key)
            if saved:
                if saved['state']!='completed':
                    raise ValueError('KNOWLEDGE_REFRESH_CHECK_EXECUTION_UNKNOWN')
                self._current_result(self.context.read,{'object_id':binding['object_id']},key,saved,binding)
                return saved,AtomicWrite(CHECKS,key,saved,saved)
            if marker.exists():
                raise ValueError('KNOWLEDGE_REFRESH_CHECK_ORPHAN_COMPLETION')
            occurred=datetime.now(timezone.utc).isoformat()
            run=self.intake.ledger.append(RecordKind.RUN,binding,authority='executor',occurred_at=occurred)
            saved={'employee_id':self.context.actor_id,'input':binding,'state':'reserved',
                'run_ref':run.record_id,'started_at':occurred}
            self._cas(key,None,saved)
            saved=self.store.get(CHECKS,key)
            if (saved is None or saved.get('input')!=binding or saved.get('state')!='reserved'
                    or saved.get('run_ref')!=run.record_id):
                raise ValueError('KNOWLEDGE_REFRESH_CHECK_RESERVATION_CHANGED')
            runner=NativeKnowledgeChecks(read_revision=self.context.read,ledger=self.intake.ledger,
                objects=self.intake.objects,release=release)
            report=runner.run(revision=RevisionRef.model_validate(binding['target_revision']),
                confirmation_ref=binding['confirmation_ref'],intended_uses=binding['intended_uses'])
            receipt=self.intake.ledger.append(RecordKind.CHECK,{'input':binding,'run_ref':run.record_id,'report':report},
                authority='qualification_service',occurred_at=datetime.now(timezone.utc).isoformat())
            completed={**saved,'state':'completed',
                'check_ref':{'ref':receipt.record_id,'revision_digest':record_digest(receipt.record_id)},
                'payload_digest':semantic_digest(receipt.payload)}
            raw=json.dumps(completed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            if not publish_immutable(marker,raw) and marker.read_bytes()!=raw:
                raise ValueError('KNOWLEDGE_REFRESH_CHECK_COMPLETION_CONFLICT')
            self._cas(key,saved,completed)
            saved=self.store.get(CHECKS,key)
            self._current_result(self.context.read,{'object_id':binding['object_id']},key,saved,binding)
            return saved,AtomicWrite(CHECKS,key,saved,saved)
