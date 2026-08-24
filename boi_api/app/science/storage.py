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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
    ScienceRolesResolver,
)
from boi_api.app.science.digests import canonical_json_bytes
from boi_api.app.science.models import (
    InterpretationRecord,
    ScienceModel,
    VerificationReport,
)
from boi_api.app.science.safety import (
    ScienceSensitivePersistenceError,
    reject_sensitive_persistence as _reject_sensitive_scalars,
)


ProposalKind = Literal[
    "term_alias",
    "term_meaning",
    "interpretation_hint",
    "concept_link",
    "ambiguity_pattern",
]
RecordAuditAction = Literal[
    "interpretation_saved",
    "report_saved",
    "proposal_saved",
    "proposal_approved_for_release_candidate",
]
StandaloneAuditAction = Literal["standalone_note_recorded"]
AuditAction = RecordAuditAction | StandaloneAuditAction
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
_TRUSTED_ACTOR_RE = re.compile(r"^(?:[0-9]{1,32}|svc:[a-z0-9][a-z0-9._-]{0,127})$")
_INTERPRETATION_ID_RE = re.compile(r"^sci-interpretation:[A-Za-z0-9][A-Za-z0-9._-]*$")
_REPORT_ID_RE = re.compile(r"^sci-report:[A-Za-z0-9][A-Za-z0-9._-]*$")
_TEMPORARY_NAME_RE = re.compile(r"^\.[0-9a-f]{64}\.[0-9a-f]{32}\.tmp$")
_UUID_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_RECORD_AUDIT_ACTIONS = {
    "interpretation_saved",
    "report_saved",
    "proposal_saved",
    "proposal_approved_for_release_candidate",
}


class ImmutableScienceRecordError(RuntimeError):
    """A runtime identifier already names different canonical bytes."""


class UnsafeScienceRuntimePathError(RuntimeError):
    """A runtime path changed identity or is not a private owned file."""


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


class ScienceApprovalAuthoritySnapshot(ScienceModel):
    approved_by: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    authority_role: str = Field(min_length=1)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    proposal_id: str = Field(pattern=rf"^sci-proposal:{_UUID_PATTERN}$")
    proposal_kind: ProposalKind
    proposed_by: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)

    @model_validator(mode="after")
    def authority_is_exact(self) -> "ScienceApprovalAuthoritySnapshot":
        expected_power_role = f"science.power_user:{self.domain}"
        if self.authority_role not in {"science.admin", expected_power_role}:
            raise ValueError("Science approval authority role does not match domain")
        if (
            self.authority_role == expected_power_role
            and self.approved_by == self.proposed_by
        ):
            raise ValueError(
                "Science approval authority snapshot forbids self-approval"
            )
        return self


class ScienceProposalApproval(ScienceModel):
    approval_id: str = Field(pattern=rf"^sci-approval:{_UUID_PATTERN}$")
    proposal_id: str = Field(pattern=rf"^sci-proposal:{_UUID_PATTERN}$")
    approved_at: datetime
    approved_by: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    proposal_kind: ProposalKind
    authority_snapshot: ScienceApprovalAuthoritySnapshot
    status: Literal["release_candidate"] = "release_candidate"


class InterpretationSavedAuditDetails(ScienceModel):
    document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ReportSavedAuditDetails(ScienceModel):
    document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    report_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ProposalSavedAuditDetails(ScienceModel):
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    kind: ProposalKind


class ProposalApprovedAuditDetails(ScienceModel):
    approval_id: str = Field(pattern=rf"^sci-approval:{_UUID_PATTERN}$")
    domain: str = Field(pattern=_DOMAIN_PATTERN)


class StandaloneNoteAuditDetails(ScienceModel):
    note_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


_AUDIT_DETAIL_MODELS: dict[str, type[ScienceModel]] = {
    "interpretation_saved": InterpretationSavedAuditDetails,
    "report_saved": ReportSavedAuditDetails,
    "proposal_saved": ProposalSavedAuditDetails,
    "proposal_approved_for_release_candidate": ProposalApprovedAuditDetails,
    "standalone_note_recorded": StandaloneNoteAuditDetails,
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
        _reject_sensitive_scalars(
            self.model_dump(mode="json", exclude_none=False), path="audit"
        )
        if not _TRUSTED_ACTOR_RE.fullmatch(self.actor):
            raise ValueError("Science audit actor is not a trusted typed identity")
        if self.action == "interpretation_saved":
            target_matches = _INTERPRETATION_ID_RE.fullmatch(self.target_id)
        elif self.action == "report_saved":
            target_matches = _REPORT_ID_RE.fullmatch(self.target_id)
        elif self.action in {
            "proposal_saved",
            "proposal_approved_for_release_candidate",
        }:
            target_matches = re.fullmatch(
                rf"sci-proposal:{_UUID_PATTERN}", self.target_id
            )
        else:
            target_matches = re.fullmatch(rf"sci-note:{_UUID_PATTERN}", self.target_id)
        if not target_matches:
            raise ValueError(
                f"Science audit target is invalid for action {self.action}"
            )
        return self


class ScienceTransactionJournal(ScienceModel):
    transaction_kind: Literal["record"] = "record"
    transaction_id: str = Field(pattern=rf"^sci-transaction:{_UUID_PATTERN}$")
    prepared_at: datetime
    collection: CollectionName
    record_id: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    actor_id: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    record: dict[str, Any]
    audit: ScienceAuditRecord


class ScienceAuditTransactionJournal(ScienceModel):
    transaction_kind: Literal["audit_only"] = "audit_only"
    transaction_id: str = Field(pattern=rf"^sci-transaction:{_UUID_PATTERN}$")
    prepared_at: datetime
    actor_id: str = Field(min_length=1, pattern=_RUNTIME_ID_PATTERN)
    audit: ScienceAuditRecord


ScienceJournal = ScienceTransactionJournal | ScienceAuditTransactionJournal


@dataclass(frozen=True)
class _RecoveryPlanItem:
    journal: ScienceJournal
    record: ScienceModel | None
    record_bytes: bytes | None
    audit_row: bytes


class _RecordPublicationError(RuntimeError):
    def __init__(self, *, published: bool, cause: BaseException):
        super().__init__(str(cause))
        self.published = published
        self.cause = cause


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        self._verify_directory_fd(self._root_fd, label="runtime root")
        try:
            root_metadata = os.lstat(self.root)
        except FileNotFoundError as exc:
            raise UnsafeScienceRuntimePathError(
                "Science runtime root disappeared"
            ) from exc
        if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(
            root_metadata.st_mode
        ):
            raise UnsafeScienceRuntimePathError(
                "Science runtime root directory changed"
            )
        if root_metadata.st_uid != os.geteuid():
            raise UnsafeScienceRuntimePathError(
                "Science runtime root has the wrong owner"
            )
        if stat.S_IMODE(root_metadata.st_mode) & 0o077:
            raise UnsafeScienceRuntimePathError("Science runtime root is not private")
        if (
            root_metadata.st_dev,
            root_metadata.st_ino,
        ) != self._root_identity:
            raise UnsafeScienceRuntimePathError(
                "Science runtime root directory changed"
            )
        for collection, descriptor in self._dir_fds.items():
            self._verify_directory_fd(descriptor, label=f"{collection} directory")
            try:
                current = os.stat(
                    collection, dir_fd=self._root_fd, follow_symlinks=False
                )
            except FileNotFoundError as exc:
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory changed or disappeared"
                ) from exc
            pinned = os.fstat(descriptor)
            if not stat.S_ISDIR(current.st_mode) or stat.S_ISLNK(current.st_mode):
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory changed"
                )
            if current.st_uid != os.geteuid():
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory has the wrong owner"
                )
            if stat.S_IMODE(current.st_mode) & 0o077:
                raise UnsafeScienceRuntimePathError(
                    f"Science {collection} directory is not private"
                )
            if (
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
        temporary = f".{destination.removesuffix('.json')}.{uuid.uuid4().hex}.tmp"
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
        identifier_field = {
            "interpretations": "interpretation_id",
            "reports": "report_id",
            "proposals": "proposal_id",
            "proposal-approvals": "approval_id",
            "transactions": "transaction_id",
        }[collection]
        identifier = getattr(record, identifier_field)
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

    @staticmethod
    def _record_model(collection: CollectionName) -> type[ScienceModel]:
        return {
            "interpretations": InterpretationRecord,
            "reports": VerificationReport,
            "proposals": ScienceProposalRecord,
            "proposal-approvals": ScienceProposalApproval,
        }[collection]

    @staticmethod
    def _record_identifier(collection: CollectionName, record: ScienceModel) -> str:
        field_name = {
            "interpretations": "interpretation_id",
            "reports": "report_id",
            "proposals": "proposal_id",
            "proposal-approvals": "approval_id",
        }[collection]
        return str(getattr(record, field_name))

    @staticmethod
    def _expected_audit_contract(
        collection: CollectionName,
        record: ScienceModel,
        *,
        actor_id: str,
    ) -> tuple[AuditAction, str, dict[str, Any], str]:
        if collection == "interpretations":
            interpretation = InterpretationRecord.model_validate(record)
            return (
                "interpretation_saved",
                interpretation.interpretation_id,
                {"document_digest": interpretation.document_digest},
                actor_id,
            )
        if collection == "reports":
            report = VerificationReport.model_validate(record)
            return (
                "report_saved",
                report.report_id,
                {
                    "document_digest": report.document_digest,
                    "report_digest": report.report_digest,
                },
                report.created_by,
            )
        if collection == "proposals":
            proposal = ScienceProposalRecord.model_validate(record)
            return (
                "proposal_saved",
                proposal.proposal_id,
                {"domain": proposal.domain, "kind": proposal.kind},
                proposal.created_by,
            )
        approval = ScienceProposalApproval.model_validate(record)
        return (
            "proposal_approved_for_release_candidate",
            approval.proposal_id,
            {"approval_id": approval.approval_id, "domain": approval.domain},
            approval.approved_by,
        )

    def _validate_journal_semantics(
        self, journal: ScienceTransactionJournal
    ) -> ScienceModel:
        record = self._record_model(journal.collection).model_validate(journal.record)
        embedded_id = self._record_identifier(journal.collection, record)
        if embedded_id != journal.record_id:
            raise ImmutableScienceRecordError(
                "Science transaction record identity does not match record_id"
            )
        expected_action, expected_target, expected_details, expected_actor = (
            self._expected_audit_contract(
                journal.collection, record, actor_id=journal.actor_id
            )
        )
        actual = journal.audit
        if journal.actor_id != actual.actor or expected_actor != actual.actor:
            raise ImmutableScienceRecordError(
                "Science transaction audit actor linkage mismatch"
            )
        if (
            actual.action != expected_action
            or actual.target_id != expected_target
            or actual.details != expected_details
        ):
            raise ImmutableScienceRecordError(
                "Science transaction audit contract does not match its record"
            )
        return record

    @staticmethod
    def _validate_audit_journal_semantics(
        journal: ScienceAuditTransactionJournal,
    ) -> None:
        if journal.audit.action != "standalone_note_recorded":
            raise ImmutableScienceRecordError(
                "Record-mutation audit actions require an immutable record transaction"
            )
        if journal.actor_id != journal.audit.actor:
            raise ImmutableScienceRecordError(
                "Science audit-only transaction actor linkage mismatch"
            )

    @staticmethod
    def _validate_approval_dependency(
        approval: ScienceProposalApproval,
        proposal: ScienceProposalRecord,
    ) -> None:
        derived_approval_id = "sci-approval:" + proposal.proposal_id.removeprefix(
            "sci-proposal:"
        )
        snapshot = approval.authority_snapshot
        if (
            approval.approval_id != derived_approval_id
            or approval.proposal_id != proposal.proposal_id
            or approval.domain != proposal.domain
            or approval.proposal_kind != proposal.kind
            or snapshot.approved_by != approval.approved_by
            or snapshot.domain != proposal.domain
            or snapshot.proposal_id != proposal.proposal_id
            or snapshot.proposal_kind != proposal.kind
            or snapshot.proposed_by != proposal.created_by
        ):
            raise ImmutableScienceRecordError(
                "Science approval and proposal dependency linkage mismatch"
            )

    def _audit_content_locked(self) -> bytes:
        try:
            descriptor = self._open_existing(
                self._root_fd, "audit.jsonl", label="Science audit"
            )
        except FileNotFoundError:
            return b""
        try:
            return self._read_all(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _audit_rows_from_complete_content(
        content: bytes,
    ) -> dict[str, bytes]:
        if content and not content.endswith(b"\n"):
            raise ImmutableScienceRecordError(
                "Science audit contains a partial JSONL row"
            )
        rows: dict[str, bytes] = {}
        for line_number, row in enumerate(content.splitlines(keepends=True), start=1):
            if row == b"\n":
                raise ImmutableScienceRecordError(
                    f"Science audit row {line_number} is empty"
                )
            try:
                payload = json.loads(row[:-1].decode("utf-8"))
                event = ScienceAuditRecord.model_validate(payload)
            except ScienceSensitivePersistenceError:
                raise
            except (UnicodeDecodeError, ValueError, TypeError) as exc:
                raise ImmutableScienceRecordError(
                    f"Science audit row {line_number} is invalid JSON or schema"
                ) from exc
            canonical_row = canonical_json_bytes(event) + b"\n"
            if canonical_row != row:
                raise ImmutableScienceRecordError(
                    f"Science audit row {line_number} is not canonical"
                )
            if event.event_id in rows:
                raise ImmutableScienceRecordError(
                    f"Science audit contains duplicate event ID {event.event_id}"
                )
            rows[event.event_id] = canonical_row
        return rows

    def _append_audit_event_locked(self, event: ScienceAuditRecord) -> None:
        validated = ScienceAuditRecord.model_validate(
            event.model_dump(mode="json", exclude_none=False)
        )
        row = canonical_json_bytes(validated) + b"\n"
        existing_rows = self._audit_rows_from_complete_content(
            self._audit_content_locked()
        )
        if validated.event_id in existing_rows:
            if existing_rows[validated.event_id] == row:
                return
            raise ImmutableScienceRecordError(
                f"Science audit event ID collision for {validated.event_id}"
            )
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

    def _scan_transaction_entries_locked(
        self,
    ) -> tuple[list[str], dict[str, list[str]]]:
        journals: list[str] = []
        temporary: dict[str, list[str]] = {
            collection: [] for collection in _COLLECTIONS
        }
        for collection in _COLLECTIONS:
            for name in sorted(os.listdir(self._dir_fds[collection])):
                if _TEMPORARY_NAME_RE.fullmatch(name):
                    descriptor = self._open_existing(
                        self._dir_fds[collection],
                        name,
                        label=f"Science {collection} temporary residue",
                    )
                    os.close(descriptor)
                    temporary[collection].append(name)
                    continue
                if collection == "transactions":
                    if not name.endswith(".json"):
                        raise UnsafeScienceRuntimePathError(
                            f"unexpected Science transaction entry: {name}"
                        )
                    journals.append(name)
        return journals, temporary

    def _transaction_journals_locked(
        self, names: list[str] | None = None
    ) -> list[_RecoveryPlanItem]:
        if names is None:
            names, _ = self._scan_transaction_entries_locked()
        items: list[_RecoveryPlanItem] = []
        for name in names:
            descriptor = self._open_existing(
                self._dir_fds["transactions"],
                name,
                label="Science transaction journal",
            )
            try:
                canonical = self._read_all(descriptor)
            finally:
                os.close(descriptor)
            try:
                payload = json.loads(canonical.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Science journal root must be an object")
                transaction_kind = payload.get("transaction_kind", "record")
                if transaction_kind == "record":
                    journal: ScienceJournal = ScienceTransactionJournal.model_validate(
                        payload
                    )
                elif transaction_kind == "audit_only":
                    journal = ScienceAuditTransactionJournal.model_validate(payload)
                else:
                    raise ValueError("unknown Science transaction kind")
            except ScienceSensitivePersistenceError:
                raise
            except (UnicodeDecodeError, ValueError, TypeError) as exc:
                raise ImmutableScienceRecordError(
                    "Science transaction journal is invalid"
                ) from exc
            if name != self._filename(journal.transaction_id):
                raise ImmutableScienceRecordError(
                    "Science transaction journal filename mismatch"
                )
            if canonical_json_bytes(journal) != canonical:
                raise ImmutableScienceRecordError(
                    "Science transaction journal is not canonical"
                )
            if isinstance(journal, ScienceTransactionJournal):
                record = self._validate_journal_semantics(journal)
                record_bytes: bytes | None = canonical_json_bytes(record)
            else:
                self._validate_audit_journal_semantics(journal)
                record = None
                record_bytes = None
            items.append(
                _RecoveryPlanItem(
                    journal=journal,
                    record=record,
                    record_bytes=record_bytes,
                    audit_row=canonical_json_bytes(journal.audit) + b"\n",
                )
            )
        return items

    def _remove_temporary_residues_locked(
        self, temporary: dict[str, list[str]]
    ) -> None:
        for collection, names in temporary.items():
            if not names:
                continue
            for name in names:
                os.unlink(name, dir_fd=self._dir_fds[collection])
            os.fsync(self._dir_fds[collection])

    def _truncate_audit_locked(self, length: int) -> None:
        descriptor = os.open(
            "audit.jsonl",
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=self._root_fd,
        )
        try:
            self._verify_regular_fd(descriptor, label="Science audit")
            os.ftruncate(descriptor, length)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _prepare_recovery_locked(
        self,
    ) -> tuple[list[_RecoveryPlanItem], dict[str, bytes]]:
        names, temporary = self._scan_transaction_entries_locked()
        plan = self._transaction_journals_locked(names)
        audit_content = self._audit_content_locked()
        complete_content = audit_content
        truncate_to: int | None = None
        if audit_content and not audit_content.endswith(b"\n"):
            last_newline = audit_content.rfind(b"\n")
            truncate_to = last_newline + 1
            complete_content = audit_content[:truncate_to]
            partial = audit_content[truncate_to:]
            candidates = {
                item.audit_row for item in plan if item.audit_row.startswith(partial)
            }
            if len(candidates) != 1:
                raise ImmutableScienceRecordError(
                    "Science audit partial row is not bound to one pending journal"
                )
        rows = self._audit_rows_from_complete_content(complete_content)
        self._validate_global_recovery_plan_locked(plan, rows)
        self._remove_temporary_residues_locked(temporary)
        if truncate_to is not None:
            self._truncate_audit_locked(truncate_to)
        return plan, rows

    def _validate_global_recovery_plan_locked(
        self,
        plan: list[_RecoveryPlanItem],
        audit_rows: dict[str, bytes],
    ) -> None:
        record_targets: set[tuple[CollectionName, str]] = set()
        journal_event_ids: set[str] = set()
        planned_note_targets: set[str] = set()
        ledger_note_targets = {
            event.target_id: event_id
            for event_id, row in audit_rows.items()
            if (event := ScienceAuditRecord.model_validate_json(row[:-1])).action
            == "standalone_note_recorded"
        }

        for item in plan:
            journal = item.journal
            event_id = journal.audit.event_id
            if event_id in journal_event_ids:
                raise ImmutableScienceRecordError(
                    f"Science recovery plan has duplicate journal event ID {event_id}"
                )
            journal_event_ids.add(event_id)
            existing_row = audit_rows.get(event_id)
            if existing_row is not None and existing_row != item.audit_row:
                raise ImmutableScienceRecordError(
                    f"Science audit event ID collision for {event_id}"
                )
            if journal.audit.action == "standalone_note_recorded":
                note_target = journal.audit.target_id
                if note_target in planned_note_targets:
                    raise ImmutableScienceRecordError(
                        "Science recovery plan has a duplicate standalone note target"
                    )
                planned_note_targets.add(note_target)
                ledger_event_id = ledger_note_targets.get(note_target)
                if ledger_event_id is not None and ledger_event_id != event_id:
                    raise ImmutableScienceRecordError(
                        "Science standalone note target already exists"
                    )

            if not isinstance(journal, ScienceTransactionJournal):
                continue
            target = (journal.collection, journal.record_id)
            if target in record_targets:
                raise ImmutableScienceRecordError(
                    "Science recovery plan has a duplicate record target"
                )
            record_targets.add(target)
            if item.record_bytes is None:
                raise ImmutableScienceRecordError(
                    "Science record transaction has no canonical record bytes"
                )
            existing = self._existing_bytes_locked(
                journal.collection, journal.record_id
            )
            if existing is not None and existing != item.record_bytes:
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {journal.record_id}"
                )

        for item in plan:
            journal = item.journal
            if not isinstance(journal, ScienceTransactionJournal):
                continue
            if journal.collection != "proposal-approvals":
                continue
            approval = ScienceProposalApproval.model_validate(item.record)
            try:
                proposal = self._load_locked(
                    "proposals", approval.proposal_id, ScienceProposalRecord
                )
            except KeyError as exc:
                raise ImmutableScienceRecordError(
                    "Science approval proposal dependency is missing"
                ) from exc
            self._validate_approval_dependency(approval, proposal)

    def _recover_pending_transactions_locked(
        self, *, record_id: str | None = None
    ) -> int:
        plan, audit_rows = self._prepare_recovery_locked()
        recovered = 0
        for item in plan:
            journal = item.journal
            if (
                isinstance(journal, ScienceTransactionJournal)
                and record_id is not None
                and journal.record_id != record_id
            ):
                continue
            if isinstance(journal, ScienceTransactionJournal):
                if item.record_bytes is None:
                    raise ImmutableScienceRecordError(
                        "Science record transaction has no canonical record bytes"
                    )
                existing = self._existing_bytes_locked(
                    journal.collection, journal.record_id
                )
                if existing is None:
                    try:
                        self._publish_bytes_locked(
                            journal.collection, journal.record_id, item.record_bytes
                        )
                    except _RecordPublicationError as exc:
                        raise ScienceTransactionPendingError(
                            journal.transaction_id,
                            journal.record_id,
                            record_published=exc.published,
                            audit_pending=True,
                            cause=exc.cause,
                        ) from exc
                pending_record_id = journal.record_id
                record_published = True
            else:
                pending_record_id = journal.audit.event_id
                record_published = False
            existing_row = audit_rows.get(journal.audit.event_id)
            if existing_row is None:
                try:
                    self._append_audit_event_locked(journal.audit)
                    audit_rows[journal.audit.event_id] = item.audit_row
                except BaseException as exc:
                    raise ScienceTransactionPendingError(
                        journal.transaction_id,
                        pending_record_id,
                        record_published=record_published,
                        audit_pending=True,
                        cause=exc,
                    ) from exc
            try:
                self._remove_record_locked("transactions", journal.transaction_id)
            except BaseException as exc:
                raise ScienceTransactionPendingError(
                    journal.transaction_id,
                    pending_record_id,
                    record_published=record_published,
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
            actor_id=audit.actor,
            record=record.model_dump(mode="json", exclude_none=False),
            audit=audit,
        )
        self._validate_journal_semantics(journal)
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
                try:
                    self._remove_record_locked("transactions", transaction_id)
                except BaseException as cleanup_error:
                    raise ScienceTransactionPendingError(
                        transaction_id,
                        record_id,
                        record_published=False,
                        audit_pending=True,
                        cause=cleanup_error,
                    ) from cleanup_error
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
                audit_pending=False,
                cause=exc,
            ) from exc
        return True

    def _commit_audit_only_locked(self, audit: ScienceAuditRecord) -> None:
        self._recover_pending_transactions_locked()
        transaction_id = f"sci-transaction:{uuid.uuid4()}"
        journal = ScienceAuditTransactionJournal(
            transaction_id=transaction_id,
            prepared_at=_utc_now(),
            actor_id=audit.actor,
            audit=audit,
        )
        self._validate_audit_journal_semantics(journal)
        item = _RecoveryPlanItem(
            journal=journal,
            record=None,
            record_bytes=None,
            audit_row=canonical_json_bytes(audit) + b"\n",
        )
        audit_rows = self._audit_rows_from_complete_content(
            self._audit_content_locked()
        )
        self._validate_global_recovery_plan_locked([item], audit_rows)
        try:
            self._publish_bytes_locked(
                "transactions", transaction_id, canonical_json_bytes(journal)
            )
        except _RecordPublicationError as exc:
            if exc.published:
                try:
                    self._remove_record_locked("transactions", transaction_id)
                except BaseException as cleanup_error:
                    raise ScienceTransactionPendingError(
                        transaction_id,
                        audit.event_id,
                        record_published=False,
                        audit_pending=True,
                        cause=cleanup_error,
                    ) from cleanup_error
            raise exc.cause

        try:
            self._append_audit_event_locked(audit)
        except BaseException as exc:
            raise ScienceTransactionPendingError(
                transaction_id,
                audit.event_id,
                record_published=False,
                audit_pending=True,
                cause=exc,
            ) from exc

        try:
            self._remove_record_locked("transactions", transaction_id)
        except BaseException as exc:
            raise ScienceTransactionPendingError(
                transaction_id,
                audit.event_id,
                record_published=False,
                audit_pending=False,
                cause=exc,
            ) from exc

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
            authority_role = self.authorization.require_proposal_approval(
                identity=identity,
                roles_for=self._roles_for,
                domain=proposal.domain,
                proposed_by=proposal.created_by,
            )
            approval_id = "sci-approval:" + proposal.proposal_id.removeprefix(
                "sci-proposal:"
            )
            self._recover_pending_transactions_locked(record_id=approval_id)
            if (
                self._existing_bytes_locked("proposal-approvals", approval_id)
                is not None
            ):
                approval = self._load_locked(
                    "proposal-approvals", approval_id, ScienceProposalApproval
                )
                self._validate_approval_dependency(approval, proposal)
                if (
                    approval.approval_id == approval_id
                    and approval.proposal_id == proposal.proposal_id
                    and approval.domain == proposal.domain
                    and approval.proposal_kind == proposal.kind
                    and approval.approved_by == identity.employee_id
                ):
                    return approval
                raise ImmutableScienceRecordError(
                    f"Science approval linkage collision for {approval_id}"
                )
            approval = ScienceProposalApproval(
                approval_id=approval_id,
                proposal_id=proposal.proposal_id,
                approved_at=_utc_now(),
                approved_by=identity.employee_id,
                domain=proposal.domain,
                proposal_kind=proposal.kind,
                authority_snapshot=ScienceApprovalAuthoritySnapshot(
                    approved_by=identity.employee_id,
                    authority_role=authority_role,
                    domain=proposal.domain,
                    proposal_id=proposal.proposal_id,
                    proposal_kind=proposal.kind,
                    proposed_by=proposal.created_by,
                ),
            )
            self._validate_approval_dependency(approval, proposal)
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
        if action in _RECORD_AUDIT_ACTIONS:
            raise ScienceAuthorizationError(
                "Record-mutation audit actions are internal to immutable transactions"
            )
        event = self._new_audit_event(
            identity=identity,
            action=action,
            target_id=target_id,
            details=details,
        )
        self.authorization.require_admin(
            identity,
            roles_for=self._roles_for,
        )
        with self._exclusive():
            self._commit_audit_only_locked(event)
        return event

    def pending_transaction_ids(self) -> list[str]:
        with self._exclusive():
            return [
                item.journal.transaction_id
                for item in self._transaction_journals_locked()
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
