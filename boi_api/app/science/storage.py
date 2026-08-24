"""Identity-bound, durable runtime storage for Science Verifier."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import threading
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceRolesResolver,
)
from boi_api.app.science.digests import canonical_json_bytes
from boi_api.app.science.models import (
    InterpretationRecord,
    ScienceModel,
    VerificationReport,
)


ProposalKind = Literal[
    "term_alias",
    "term_meaning",
    "interpretation_hint",
    "concept_link",
    "ambiguity_pattern",
]
AuditAction = Literal[
    "interpretation_saved",
    "report_saved",
    "proposal_saved",
    "proposal_approved_for_release_candidate",
]
CollectionName = Literal[
    "interpretations",
    "reports",
    "proposals",
    "proposal-approvals",
]

_COLLECTIONS: tuple[str, ...] = (
    "interpretations",
    "reports",
    "proposals",
    "proposal-approvals",
    "transactions",
)
_DOMAIN_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
_RUNTIME_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@#-]*$"
_UUID_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "base_url",
    "credential",
    "credentials",
    "endpoint",
    "password",
    "secret",
    "token",
    "url",
}
_SENSITIVE_SCALAR_PATTERNS = (
    re.compile(r"(?i)\b(?:https?|wss?)://"),
    re.compile(r"(?i)\b(?:bearer|basic)(?:\s|[-_:])+[^\s]+"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|authorization|base[_-]?url|credential|"
        r"endpoint|password|secret|token)\s*[:=]"
    ),
)


class ImmutableScienceRecordError(RuntimeError):
    """A runtime identifier already names different canonical bytes."""


class UnsafeScienceRuntimePathError(RuntimeError):
    """A runtime path changed identity or is not a private owned file."""


class ScienceSensitivePersistenceError(ValueError):
    """A secret or service endpoint reached a non-secret persistence boundary."""


class ScienceTransactionPendingError(RuntimeError):
    """A durable journal must reconcile a visible or possibly visible mutation."""

    def __init__(
        self,
        transaction_id: str,
        record_id: str,
        *,
        record_published: bool,
        audit_pending: bool,
        cause: BaseException,
    ) -> None:
        state = "published" if record_published else "prepared"
        audit_state = "audit pending" if audit_pending else "audit recorded"
        super().__init__(
            f"Science transaction {transaction_id} is {state}, {audit_state}: {cause}"
        )
        self.transaction_id = transaction_id
        self.record_id = record_id
        self.record_published = record_published
        self.audit_pending = audit_pending


class ScienceProposalRecord(ScienceModel):
    proposal_id: str = Field(pattern=rf"^sci-proposal:{_UUID_PATTERN}$")
    created_at: datetime
    created_by: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    kind: ProposalKind
    payload: dict[str, Any]
    status: Literal["proposed"] = "proposed"


class ScienceProposalApproval(ScienceModel):
    approval_id: str = Field(pattern=rf"^sci-approval:{_UUID_PATTERN}$")
    proposal_id: str = Field(pattern=rf"^sci-proposal:{_UUID_PATTERN}$")
    approved_at: datetime
    approved_by: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    proposal_kind: ProposalKind
    status: Literal["release_candidate"] = "release_candidate"


class InterpretationSavedAuditDetails(ScienceModel):
    document_digest: str = Field(min_length=1)


class ReportSavedAuditDetails(ScienceModel):
    document_digest: str = Field(min_length=1)
    report_digest: str = Field(min_length=1)


class ProposalSavedAuditDetails(ScienceModel):
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    kind: ProposalKind


class ProposalApprovedAuditDetails(ScienceModel):
    approval_id: str = Field(pattern=rf"^sci-approval:{_UUID_PATTERN}$")
    domain: str = Field(pattern=_DOMAIN_PATTERN)


_AUDIT_DETAIL_MODELS: dict[str, type[ScienceModel]] = {
    "interpretation_saved": InterpretationSavedAuditDetails,
    "report_saved": ReportSavedAuditDetails,
    "proposal_saved": ProposalSavedAuditDetails,
    "proposal_approved_for_release_candidate": ProposalApprovedAuditDetails,
}


class ScienceAuditRecord(ScienceModel):
    event_id: str = Field(pattern=rf"^sci-audit:{_UUID_PATTERN}$")
    occurred_at: datetime
    actor: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    action: AuditAction
    target_id: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    details: dict[str, Any]

    @model_validator(mode="after")
    def action_specific_details(self) -> "ScienceAuditRecord":
        detail_model = _AUDIT_DETAIL_MODELS[self.action]
        validated = detail_model.model_validate(self.details)
        self.details = validated.model_dump(mode="json", exclude_none=False)
        return self


class ScienceTransactionJournal(ScienceModel):
    transaction_id: str = Field(pattern=rf"^sci-transaction:{_UUID_PATTERN}$")
    prepared_at: datetime
    collection: CollectionName
    record_id: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    record: dict[str, Any]
    audit: ScienceAuditRecord


class _RecordPublicationError(RuntimeError):
    def __init__(self, *, published: bool, cause: BaseException):
        super().__init__(str(cause))
        self.published = published
        self.cause = cause


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_key(key: object) -> str:
    raw = str(key).strip().replace("-", "_")
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw)
    return snake.lower()


def _sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return normalized in _SENSITIVE_KEYS or any(
        normalized.endswith(f"_{suffix}") for suffix in _SENSITIVE_KEYS
    )


def _reject_sensitive_scalars(value: Any, *, path: str = "value") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _sensitive_key(key):
                raise ScienceSensitivePersistenceError(
                    f"sensitive field is forbidden at {path}.{key}"
                )
            _reject_sensitive_scalars(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_sensitive_scalars(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and any(
        pattern.search(value) for pattern in _SENSITIVE_SCALAR_PATTERNS
    ):
        raise ScienceSensitivePersistenceError(
            f"credential or endpoint scalar is forbidden at {path}"
        )


class ScienceRuntimeStore:
    """Persist identity-bound records through one journaled record+audit protocol."""

    _process_locks_guard = threading.Lock()
    _process_locks: dict[str, threading.RLock] = {}

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        authorization: ScienceAuthorization,
        roles_for: ScienceRolesResolver,
    ) -> None:
        self.root = Path(root)
        self.authorization = authorization
        self._roles_for = roles_for
        self._closed = False
        self._initialize_root()
        self._root_fd = os.open(
            self.root,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        self._verify_directory_fd(self._root_fd, label="runtime root")
        root_stat = os.fstat(self._root_fd)
        self._root_identity = (root_stat.st_dev, root_stat.st_ino)
        self._dir_fds: dict[str, int] = {}
        for collection in _COLLECTIONS:
            self._ensure_collection(collection)
            descriptor = os.open(
                collection,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=self._root_fd,
            )
            self._verify_directory_fd(descriptor, label=f"{collection} directory")
            self._dir_fds[collection] = descriptor
        self._lock_name = ".runtime.lock"
        self.audit_path = self.root / "audit.jsonl"
        with self._process_locks_guard:
            self._thread_lock = self._process_locks.setdefault(
                str(self.root.resolve()), threading.RLock()
            )
        self.recover_pending_transactions()

    def _initialize_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = os.lstat(self.root)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise UnsafeScienceRuntimePathError(
                f"Science runtime root is not a safe directory: {self.root}"
            )
        if metadata.st_uid != os.geteuid():
            raise UnsafeScienceRuntimePathError(
                "Science runtime root is not owned by the current process user"
            )
        os.chmod(self.root, 0o700)

    def _ensure_collection(self, collection: str) -> None:
        try:
            os.mkdir(collection, mode=0o700, dir_fd=self._root_fd)
        except FileExistsError:
            pass
        metadata = os.stat(collection, dir_fd=self._root_fd, follow_symlinks=False)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise UnsafeScienceRuntimePathError(
                f"Science {collection} path is not a safe directory"
            )
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UnsafeScienceRuntimePathError(
                f"Science {collection} directory must be owned and private"
            )

    @staticmethod
    def _verify_directory_fd(descriptor: int, *, label: str) -> None:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeScienceRuntimePathError(f"{label} is not a directory")
        if metadata.st_uid != os.geteuid():
            raise UnsafeScienceRuntimePathError(f"{label} has the wrong owner")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UnsafeScienceRuntimePathError(f"{label} is not private")

    @staticmethod
    def _verify_regular_fd(descriptor: int, *, label: str) -> None:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise UnsafeScienceRuntimePathError(f"{label} is not a safe regular file")
        if metadata.st_uid != os.geteuid():
            raise UnsafeScienceRuntimePathError(f"{label} has the wrong owner")
        mode = stat.S_IMODE(metadata.st_mode)
        if mode & 0o077 or not mode & 0o400:
            raise UnsafeScienceRuntimePathError(f"{label} must use a private mode")

    def _verify_bindings(self) -> None:
        try:
            root_metadata = os.lstat(self.root)
        except FileNotFoundError as exc:
            raise UnsafeScienceRuntimePathError(
                "Science runtime root disappeared"
            ) from exc
        if (
            stat.S_ISLNK(root_metadata.st_mode)
            or (
                root_metadata.st_dev,
                root_metadata.st_ino,
            )
            != self._root_identity
        ):
            raise UnsafeScienceRuntimePathError(
                "Science runtime root directory changed"
            )
        for collection, descriptor in self._dir_fds.items():
            try:
                current = os.stat(
                    collection, dir_fd=self._root_fd, follow_symlinks=False
                )
            except FileNotFoundError as exc:
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory changed or disappeared"
                ) from exc
            pinned = os.fstat(descriptor)
            if not stat.S_ISDIR(current.st_mode) or (
                current.st_dev,
                current.st_ino,
            ) != (pinned.st_dev, pinned.st_ino):
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory changed"
                )

    @contextmanager
    def _exclusive(self):
        if self._closed:
            raise RuntimeError("Science runtime store is closed")
        with self._thread_lock:
            self._verify_bindings()
            try:
                descriptor = os.open(
                    self._lock_name,
                    os.O_CREAT
                    | os.O_RDWR
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    0o600,
                    dir_fd=self._root_fd,
                )
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.EISDIR}:
                    raise UnsafeScienceRuntimePathError(
                        "Science runtime lock is a symbolic link or directory"
                    ) from exc
                raise
            try:
                self._verify_regular_fd(descriptor, label="Science runtime lock")
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._verify_bindings()
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    @staticmethod
    def _filename(record_id: str) -> str:
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("Science runtime record ID must be nonempty")
        return hashlib.sha256(record_id.encode("utf-8")).hexdigest() + ".json"

    def record_path(self, collection: str, record_id: str) -> Path:
        if collection not in _COLLECTIONS:
            raise ValueError(f"unknown Science runtime collection: {collection}")
        return self.root / collection / self._filename(record_id)

    def _open_existing(self, directory_fd: int, name: str, *, label: str) -> int:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            raise
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.EISDIR}:
                raise UnsafeScienceRuntimePathError(
                    f"{label} is a symbolic link or not a safe regular file"
                ) from exc
            raise
        try:
            self._verify_regular_fd(descriptor, label=label)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    @staticmethod
    def _read_all(descriptor: int) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)

    @staticmethod
    def _write_all(descriptor: int, data: bytes) -> None:
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("short Science runtime write")
            written += count

    def _existing_bytes_locked(self, collection: str, record_id: str) -> bytes | None:
        name = self._filename(record_id)
        try:
            descriptor = self._open_existing(
                self._dir_fds[collection], name, label=f"Science record {record_id}"
            )
        except FileNotFoundError:
            return None
        try:
            return self._read_all(descriptor)
        finally:
            os.close(descriptor)

    def _publish_bytes_locked(
        self, collection: str, record_id: str, canonical: bytes
    ) -> bool:
        existing = self._existing_bytes_locked(collection, record_id)
        if existing is not None:
            if existing != canonical:
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {record_id}"
                )
            return False

        directory_fd = self._dir_fds[collection]
        destination = self._filename(record_id)
        temporary = f".{destination}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary,
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=directory_fd,
        )
        published = False
        try:
            self._write_all(descriptor, canonical)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            try:
                os.replace(
                    temporary,
                    destination,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                published = True
                os.fsync(directory_fd)
            except BaseException as exc:
                try:
                    visible = self._existing_bytes_locked(collection, record_id)
                except BaseException as inspection_error:
                    raise _RecordPublicationError(
                        published=True,
                        cause=inspection_error,
                    ) from exc
                if visible is not None:
                    if visible != canonical:
                        raise ImmutableScienceRecordError(
                            f"immutable record collision for {record_id}"
                        ) from exc
                    published = True
                raise _RecordPublicationError(published=published, cause=exc) from exc
        except _RecordPublicationError:
            raise
        except BaseException as exc:
            raise _RecordPublicationError(published=published, cause=exc) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        return True

    def _remove_record_locked(self, collection: str, record_id: str) -> None:
        try:
            os.unlink(self._filename(record_id), dir_fd=self._dir_fds[collection])
        except FileNotFoundError:
            return
        os.fsync(self._dir_fds[collection])

    def _load_locked(self, collection: str, record_id: str, model: type[ScienceModel]):
        canonical = self._existing_bytes_locked(collection, record_id)
        if canonical is None:
            raise KeyError(f"unknown Science runtime record: {record_id}")
        payload = json.loads(canonical.decode("utf-8"))
        record = model.model_validate(payload)
        identifier = next(
            getattr(record, field_name)
            for field_name in (
                "interpretation_id",
                "report_id",
                "proposal_id",
                "approval_id",
                "transaction_id",
            )
            if hasattr(record, field_name)
        )
        if identifier != record_id:
            raise ImmutableScienceRecordError(
                f"Science runtime record identity mismatch for {record_id}"
            )
        if canonical_json_bytes(record) != canonical:
            raise ImmutableScienceRecordError(
                f"Science runtime record is not canonical for {record_id}"
            )
        return record

    def _load(self, collection: str, record_id: str, model: type[ScienceModel]):
        with self._exclusive():
            return self._load_locked(collection, record_id, model)

    def _new_audit_event(
        self,
        *,
        identity: AuthIdentity,
        action: AuditAction,
        target_id: str,
        details: Mapping[str, Any],
    ) -> ScienceAuditRecord:
        raw = {
            "actor": identity.employee_id,
            "action": action,
            "target_id": target_id,
            "details": dict(details),
        }
        _reject_sensitive_scalars(raw, path="audit")
        return ScienceAuditRecord(
            event_id=f"sci-audit:{uuid.uuid4()}",
            occurred_at=_utc_now(),
            **raw,
        )

    def _open_audit_locked(self) -> tuple[int, bool]:
        flags = (
            os.O_RDWR
            | os.O_APPEND
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        created = False
        try:
            descriptor = os.open(
                "audit.jsonl",
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=self._root_fd,
            )
            created = True
        except FileExistsError:
            try:
                descriptor = os.open("audit.jsonl", flags, dir_fd=self._root_fd)
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.EISDIR}:
                    raise UnsafeScienceRuntimePathError(
                        "Science audit is a symbolic link or directory"
                    ) from exc
                raise
        self._verify_regular_fd(descriptor, label="Science audit")
        return descriptor, created

    def _append_audit_event_locked(self, event: ScienceAuditRecord) -> None:
        row = canonical_json_bytes(event) + b"\n"
        descriptor, created = self._open_audit_locked()
        prior_eof = os.lseek(descriptor, 0, os.SEEK_END)
        try:
            self._write_all(descriptor, row)
            os.fsync(descriptor)
            if created:
                os.fsync(self._root_fd)
        except BaseException:
            try:
                os.ftruncate(descriptor, prior_eof)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            raise
        os.close(descriptor)

    def _audit_event_exists_locked(self, event_id: str) -> bool:
        try:
            descriptor = self._open_existing(
                self._root_fd, "audit.jsonl", label="Science audit"
            )
        except FileNotFoundError:
            return False
        try:
            content = self._read_all(descriptor)
        finally:
            os.close(descriptor)
        if content and not content.endswith(b"\n"):
            raise ImmutableScienceRecordError(
                "Science audit contains a partial JSONL row"
            )
        for raw_line in content.splitlines():
            event = ScienceAuditRecord.model_validate(json.loads(raw_line))
            if event.event_id == event_id:
                return True
        return False

    def _transaction_journals_locked(self) -> list[ScienceTransactionJournal]:
        journals: list[ScienceTransactionJournal] = []
        for name in sorted(os.listdir(self._dir_fds["transactions"])):
            if not name.endswith(".json"):
                raise UnsafeScienceRuntimePathError(
                    f"unexpected Science transaction entry: {name}"
                )
            descriptor = self._open_existing(
                self._dir_fds["transactions"],
                name,
                label="Science transaction journal",
            )
            try:
                canonical = self._read_all(descriptor)
            finally:
                os.close(descriptor)
            journal = ScienceTransactionJournal.model_validate_json(canonical)
            if name != self._filename(journal.transaction_id):
                raise ImmutableScienceRecordError(
                    "Science transaction journal filename mismatch"
                )
            if canonical_json_bytes(journal) != canonical:
                raise ImmutableScienceRecordError(
                    "Science transaction journal is not canonical"
                )
            journals.append(journal)
        return journals

    def _recover_pending_transactions_locked(
        self, *, record_id: str | None = None
    ) -> int:
        model_by_collection: dict[str, type[ScienceModel]] = {
            "interpretations": InterpretationRecord,
            "reports": VerificationReport,
            "proposals": ScienceProposalRecord,
            "proposal-approvals": ScienceProposalApproval,
        }
        recovered = 0
        for journal in self._transaction_journals_locked():
            if record_id is not None and journal.record_id != record_id:
                continue
            record = model_by_collection[journal.collection].model_validate(
                journal.record
            )
            record_bytes = canonical_json_bytes(record)
            existing = self._existing_bytes_locked(
                journal.collection, journal.record_id
            )
            if existing is None:
                try:
                    self._publish_bytes_locked(
                        journal.collection, journal.record_id, record_bytes
                    )
                except _RecordPublicationError as exc:
                    raise ScienceTransactionPendingError(
                        journal.transaction_id,
                        journal.record_id,
                        record_published=exc.published,
                        audit_pending=True,
                        cause=exc.cause,
                    ) from exc
            elif existing != record_bytes:
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {journal.record_id}"
                )
            if not self._audit_event_exists_locked(journal.audit.event_id):
                try:
                    self._append_audit_event_locked(journal.audit)
                except BaseException as exc:
                    raise ScienceTransactionPendingError(
                        journal.transaction_id,
                        journal.record_id,
                        record_published=True,
                        audit_pending=True,
                        cause=exc,
                    ) from exc
            try:
                self._remove_record_locked("transactions", journal.transaction_id)
            except BaseException as exc:
                raise ScienceTransactionPendingError(
                    journal.transaction_id,
                    journal.record_id,
                    record_published=True,
                    audit_pending=False,
                    cause=exc,
                ) from exc
            recovered += 1
        return recovered

    def _commit_record_locked(
        self,
        *,
        collection: CollectionName,
        record_id: str,
        record: ScienceModel,
        audit: ScienceAuditRecord,
    ) -> bool:
        self._recover_pending_transactions_locked(record_id=record_id)
        record_bytes = canonical_json_bytes(record)
        existing = self._existing_bytes_locked(collection, record_id)
        if existing is not None:
            if existing != record_bytes:
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {record_id}"
                )
            return False

        transaction_id = f"sci-transaction:{uuid.uuid4()}"
        journal = ScienceTransactionJournal(
            transaction_id=transaction_id,
            prepared_at=_utc_now(),
            collection=collection,
            record_id=record_id,
            record=record.model_dump(mode="json", exclude_none=False),
            audit=audit,
        )
        try:
            self._publish_bytes_locked(
                "transactions", transaction_id, canonical_json_bytes(journal)
            )
        except _RecordPublicationError as exc:
            if exc.published:
                try:
                    self._remove_record_locked("transactions", transaction_id)
                except BaseException:
                    raise ScienceTransactionPendingError(
                        transaction_id,
                        record_id,
                        record_published=False,
                        audit_pending=True,
                        cause=exc.cause,
                    ) from exc
            raise exc.cause

        try:
            self._publish_bytes_locked(collection, record_id, record_bytes)
        except _RecordPublicationError as exc:
            if not exc.published:
                self._remove_record_locked("transactions", transaction_id)
                raise exc.cause
            raise ScienceTransactionPendingError(
                transaction_id,
                record_id,
                record_published=True,
                audit_pending=True,
                cause=exc.cause,
            ) from exc

        try:
            self._append_audit_event_locked(audit)
        except BaseException as exc:
            raise ScienceTransactionPendingError(
                transaction_id,
                record_id,
                record_published=True,
                audit_pending=True,
                cause=exc,
            ) from exc

        try:
            self._remove_record_locked("transactions", transaction_id)
        except BaseException as exc:
            raise ScienceTransactionPendingError(
                transaction_id,
                record_id,
                record_published=True,
                audit_pending=not self._audit_event_exists_locked(audit.event_id),
                cause=exc,
            ) from exc
        return True

    def save_interpretation(
        self,
        record: InterpretationRecord | Mapping[str, Any],
        *,
        identity: AuthIdentity,
    ) -> InterpretationRecord:
        interpretation = InterpretationRecord.model_validate(record)
        audit = self._new_audit_event(
            identity=identity,
            action="interpretation_saved",
            target_id=interpretation.interpretation_id,
            details={"document_digest": interpretation.document_digest},
        )
        with self._exclusive():
            self._commit_record_locked(
                collection="interpretations",
                record_id=interpretation.interpretation_id,
                record=interpretation,
                audit=audit,
            )
        return interpretation

    def load_interpretation(self, interpretation_id: str) -> InterpretationRecord:
        return self._load("interpretations", interpretation_id, InterpretationRecord)

    def save_report(
        self,
        record: VerificationReport | Mapping[str, Any],
        *,
        identity: AuthIdentity,
    ) -> VerificationReport:
        report = VerificationReport.model_validate(record)
        audit = self._new_audit_event(
            identity=identity,
            action="report_saved",
            target_id=report.report_id,
            details={
                "document_digest": report.document_digest,
                "report_digest": report.report_digest,
            },
        )
        with self._exclusive():
            self._commit_record_locked(
                collection="reports",
                record_id=report.report_id,
                record=report,
                audit=audit,
            )
        return report

    def load_report(self, report_id: str) -> VerificationReport:
        return self._load("reports", report_id, VerificationReport)

    def save_proposal(
        self,
        *,
        identity: AuthIdentity,
        domain: str,
        kind: ProposalKind,
        payload: Mapping[str, Any],
    ) -> ScienceProposalRecord:
        proposal = ScienceProposalRecord(
            proposal_id=f"sci-proposal:{uuid.uuid4()}",
            created_at=_utc_now(),
            created_by=identity.employee_id,
            domain=domain,
            kind=kind,
            payload=dict(payload),
        )
        audit = self._new_audit_event(
            identity=identity,
            action="proposal_saved",
            target_id=proposal.proposal_id,
            details={"domain": proposal.domain, "kind": proposal.kind},
        )
        with self._exclusive():
            self._commit_record_locked(
                collection="proposals",
                record_id=proposal.proposal_id,
                record=proposal,
                audit=audit,
            )
        return proposal

    def load_proposal(self, proposal_id: str) -> ScienceProposalRecord:
        return self._load("proposals", proposal_id, ScienceProposalRecord)

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        identity: AuthIdentity,
    ) -> ScienceProposalApproval:
        with self._exclusive():
            proposal = self._load_locked(
                "proposals", proposal_id, ScienceProposalRecord
            )
            self.authorization.require_proposal_approval(
                identity=identity,
                roles_for=self._roles_for,
                domain=proposal.domain,
                proposed_by=proposal.created_by,
            )
            approval_id = "sci-approval:" + proposal.proposal_id.removeprefix(
                "sci-proposal:"
            )
            existing = self._existing_bytes_locked("proposal-approvals", approval_id)
            if existing is not None:
                approval = ScienceProposalApproval.model_validate_json(existing)
                if approval.approved_by == identity.employee_id:
                    return approval
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {approval_id}"
                )
            approval = ScienceProposalApproval(
                approval_id=approval_id,
                proposal_id=proposal.proposal_id,
                approved_at=_utc_now(),
                approved_by=identity.employee_id,
                domain=proposal.domain,
                proposal_kind=proposal.kind,
            )
            audit = self._new_audit_event(
                identity=identity,
                action="proposal_approved_for_release_candidate",
                target_id=proposal.proposal_id,
                details={
                    "approval_id": approval.approval_id,
                    "domain": proposal.domain,
                },
            )
            self._commit_record_locked(
                collection="proposal-approvals",
                record_id=approval.approval_id,
                record=approval,
                audit=audit,
            )
        return approval

    def append_audit(
        self,
        *,
        identity: AuthIdentity,
        action: AuditAction,
        target_id: str,
        details: Mapping[str, Any],
    ) -> ScienceAuditRecord:
        event = self._new_audit_event(
            identity=identity,
            action=action,
            target_id=target_id,
            details=details,
        )
        with self._exclusive():
            self._append_audit_event_locked(event)
        return event

    def pending_transaction_ids(self) -> list[str]:
        with self._exclusive():
            return [
                journal.transaction_id
                for journal in self._transaction_journals_locked()
            ]

    def recover_pending_transactions(self) -> int:
        if self._closed:
            raise RuntimeError("Science runtime store is closed")
        with self._exclusive():
            return self._recover_pending_transactions_locked()

    def close(self) -> None:
        if self._closed:
            return
        for descriptor in self._dir_fds.values():
            os.close(descriptor)
        os.close(self._root_fd)
        self._closed = True

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass
