"""Bounded resumable private transport; completed objects are not Wiki knowledge."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile

from .local_bundle_contract import CHUNK_BYTES
from .local_bundle_snapshot import with_bundle_snapshot
from .local_bundle_service import BUNDLES, UPLOADS
from .source_envelope import byte_digest
from ..v2.atomic_store_contract import AtomicWrite


class LocalBundleUpload:
    def __init__(self, service, root):
        self.service, self.root = service, Path(root)

    @staticmethod
    def expected_length(obj, offset):
        if type(offset) is not int or offset < 0 or offset % CHUNK_BYTES or offset >= obj['byte_length']:
            raise ValueError('LOCAL_BUNDLE_CHUNK_OFFSET_INVALID')
        return min(CHUNK_BYTES, obj['byte_length'] - offset)

    def _directory(self, bundle_ref, object_id):
        # Path components derive solely from a digest of validated server refs.
        key = self.service.upload_key(bundle_ref, object_id).removeprefix('bundle-upload:sha256:')
        return self.root / key[:2] / key

    @contextmanager
    def _locked(self, directory):
        for path in (self.root, directory.parent, directory):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise ValueError('LOCAL_BUNDLE_PRIVATE_STORAGE_REQUIRED')
        fd = os.open(directory / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @staticmethod
    def _sync(directory):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _file_digest(path):
        if path.is_symlink():
            raise ValueError('LOCAL_BUNDLE_PRIVATE_STORAGE_REQUIRED')
        digest = hashlib.sha256()
        length = 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(CHUNK_BYTES), b''):
                digest.update(block)
                length += len(block)
        return 'sha256:' + digest.hexdigest(), length

    def _part(self, directory, offset, raw):
        path = directory / (str(offset) + '.part')
        expected = (byte_digest(raw), len(raw))
        if path.exists():
            if self._file_digest(path) != expected:
                raise ValueError('LOCAL_BUNDLE_CHUNK_REPLAY_CONFLICT')
            return
        fd, temporary = tempfile.mkstemp(prefix='.incoming-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            self._sync(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _complete(self, directory, obj, parts):
        offsets = list(range(0, obj['byte_length'], CHUNK_BYTES))
        if set(parts) != {str(offset) for offset in offsets}:
            return False
        complete = directory / 'complete'
        expected = (obj['byte_digest'], obj['byte_length'])
        if complete.exists():
            if self._file_digest(complete) != expected:
                raise ValueError('LOCAL_BUNDLE_COMPLETED_BYTES_DRIFT')
            return True
        fd, temporary = tempfile.mkstemp(prefix='.assembling-', dir=directory)
        full_digest, full_length = hashlib.sha256(), 0
        try:
            with os.fdopen(fd, 'wb') as stream:
                for offset in offsets:
                    path = directory / (str(offset) + '.part')
                    if self._file_digest(path) != (parts[str(offset)]['byte_digest'], self.expected_length(obj, offset)):
                        raise ValueError('LOCAL_BUNDLE_PART_BYTES_DRIFT')
                    with path.open('rb') as chunk:
                        raw = chunk.read(CHUNK_BYTES)
                    stream.write(raw)
                    full_digest.update(raw)
                    full_length += len(raw)
                if ('sha256:' + full_digest.hexdigest(), full_length) != expected:
                    raise ValueError('LOCAL_BUNDLE_OBJECT_DIGEST_MISMATCH')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, complete)
            self._sync(directory)
            return True
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @with_bundle_snapshot
    def put(self, *, authorization, bundle_ref, object_id, offset, chunk_digest, raw):
        row, obj, fences = self.service.upload_context(authorization=authorization,
            bundle_ref=bundle_ref, object_id=object_id)
        if (type(raw) is not bytes or len(raw) != self.expected_length(obj, offset)
                or byte_digest(raw) != chunk_digest):
            raise ValueError('LOCAL_BUNDLE_CHUNK_DIGEST_OR_LENGTH_MISMATCH')
        directory = self._directory(bundle_ref, object_id)
        key = self.service.upload_key(bundle_ref, object_id)
        with self._locked(directory):
            # Stop/revocation/head changes that occurred while waiting for a
            # previous uploader must be seen before consuming or acknowledging.
            row, obj, fences = self.service.upload_context(authorization=authorization,
                bundle_ref=bundle_ref, object_id=object_id)
            old = self.service.upload_record(row, obj)
            parts = dict((old or {}).get('parts', {}))
            part = {'byte_digest':chunk_digest, 'byte_length':len(raw)}
            if str(offset) in parts and parts[str(offset)] != part:
                raise ValueError('LOCAL_BUNDLE_CHUNK_REPLAY_CONFLICT')
            self._part(directory, offset, raw)
            parts[str(offset)] = part
            complete = self._complete(directory, obj, parts)
            row, obj, fences = self.service.upload_context(authorization=authorization,
                bundle_ref=bundle_ref, object_id=object_id)
            value = {'employee_id':authorization.principal, 'bundle_ref':bundle_ref,
                'manifest_digest':row['manifest_digest'], 'object_id':object_id,
                'byte_digest':obj['byte_digest'], 'byte_length':obj['byte_length'],
                'parts':parts, 'complete':complete}
            # No receipt when stop or a knowledge-head transaction won the race.
            if not self.service.store.atomic_compare_and_write((*fences,
                    AtomicWrite(BUNDLES, bundle_ref, row, row), AtomicWrite(UPLOADS, key, old, value))):
                raise ValueError('LOCAL_BUNDLE_UPLOAD_STATE_CHANGED')
            return {'bundle_ref':bundle_ref, 'object_id':object_id, 'accepted_offset':offset,
                'received_bytes':sum(x['byte_length'] for x in parts.values()), 'complete':complete,
                'byte_digest':obj['byte_digest'], 'publication_committed':False}

    def verified_path(self, *, authorization, bundle_ref, object_id):
        """Internal deterministic consumer only. Never return this path to a client."""
        row, obj, _ = self.service.upload_context(authorization=authorization,
            bundle_ref=bundle_ref, object_id=object_id)
        directory = self._directory(bundle_ref, object_id)
        with self._locked(directory):
            saved = self.service.upload_record(row, obj)
            if (not saved or not saved['complete'] or saved['manifest_digest'] != row['manifest_digest']
                    or self._file_digest(directory / 'complete') != (obj['byte_digest'], obj['byte_length'])):
                raise ValueError('LOCAL_BUNDLE_COMPLETED_OBJECT_UNAVAILABLE')
            return directory / 'complete'
