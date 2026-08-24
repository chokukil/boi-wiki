"""Immutable runtime records and append-only audit storage for Science Verifier."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
import uuid
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from boi_api.app.science.authorization import ScienceAuthorization
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

_DOMAIN_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
_SENSITIVE_AUDIT_KEYS = {
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


class ImmutableScienceRecordError(RuntimeError):
    """A runtime identifier already names different canonical bytes."""


class ScienceProposalRecord(ScienceModel):
    proposal_id: str = Field(pattern=r"^sci-proposal:[0-9a-f-]+$")
    created_at: datetime
    created_by: str = Field(min_length=1)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    kind: ProposalKind
    payload: dict[str, Any]
    status: Literal["proposed"] = "proposed"


class ScienceProposalApproval(ScienceModel):
    approval_id: str = Field(pattern=r"^sci-approval:[0-9a-f-]+$")
    proposal_id: str = Field(pattern=r"^sci-proposal:[0-9a-f-]+$")
    approved_at: datetime
    approved_by: str = Field(min_length=1)
    domain: str = Field(pattern=_DOMAIN_PATTERN)
    proposal_kind: ProposalKind
    status: Literal["release_candidate"] = "release_candidate"


class ScienceAuditRecord(ScienceModel):
    event_id: str = Field(pattern=r"^sci-audit:[0-9a-f-]+$")
    occurred_at: datetime
    actor: str = Field(min_length=1)
    action: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    details: dict[str, Any]

    @field_validator("details")
    @classmethod
    def canonical_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        canonical_json_bytes(value)
        return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return (
        normalized in _SENSITIVE_AUDIT_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("_authorization")
        or normalized.endswith("_credential")
        or normalized.endswith("_credentials")
        or normalized.endswith("_endpoint")
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
        or normalized.endswith("_url")
    )


def _sanitize_audit_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_audit_value(item)
            for key, item in value.items()
            if not _sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_audit_value(item) for item in value]
    return value


class ScienceRuntimeStore:
    """Persist canonical records without ever modifying published bytes."""

    _process_locks_guard = threading.Lock()
    _process_locks: dict[str, threading.RLock] = {}

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        authorization: ScienceAuthorization | None = None,
    ) -> None:
        self.root = Path(root)
        self.authorization = authorization or ScienceAuthorization("admin_only")
        self._ensure_private_directory(self.root)
        for name in ("interpretations", "reports", "proposals", "proposal-approvals"):
            self._ensure_private_directory(self.root / name)
        self._lock_path = self.root / ".runtime.lock"
        self.audit_path = self.root / "audit.jsonl"
        with self._process_locks_guard:
            self._thread_lock = self._process_locks.setdefault(
                str(self.root.resolve()), threading.RLock()
            )

    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or not path.is_dir():
            raise OSError(f"Science runtime directory is not a real directory: {path}")
        os.chmod(path, 0o700)

    @contextmanager
    def _exclusive(self):
        with self._thread_lock:
            descriptor = os.open(
                self._lock_path,
                os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                os.fchmod(descriptor, 0o600)
                fcntl.flock(descriptor, fcntl.LOCK_EX)
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
        if collection not in {
            "interpretations",
            "reports",
            "proposals",
            "proposal-approvals",
        }:
            raise ValueError(f"unknown Science runtime collection: {collection}")
        return self.root / collection / self._filename(record_id)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_immutable_locked(
        self, collection: str, record_id: str, payload: ScienceModel
    ) -> tuple[bool, Path]:
        destination = self.record_path(collection, record_id)
        canonical = canonical_json_bytes(payload)
        if destination.exists():
            existing = destination.read_bytes()
            if existing != canonical:
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {record_id}"
                )
            return False, destination

        descriptor, temporary_name = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(canonical)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            os.chmod(destination, 0o600)
            self._fsync_directory(destination.parent)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise
        return True, destination

    def _write_immutable(
        self, collection: str, record_id: str, payload: ScienceModel
    ) -> tuple[bool, Path]:
        with self._exclusive():
            return self._write_immutable_locked(collection, record_id, payload)

    def _load(self, collection: str, record_id: str, model: type[ScienceModel]):
        path = self.record_path(collection, record_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(f"unknown Science runtime record: {record_id}") from exc
        record = model.model_validate(payload)
        identifier = next(
            getattr(record, field_name)
            for field_name in (
                "interpretation_id",
                "report_id",
                "proposal_id",
                "approval_id",
            )
            if hasattr(record, field_name)
        )
        if identifier != record_id:
            raise ImmutableScienceRecordError(
                f"Science runtime record identity mismatch for {record_id}"
            )
        return record

    def save_interpretation(
        self,
        record: InterpretationRecord | Mapping[str, Any],
        *,
        actor: str = "system",
    ) -> InterpretationRecord:
        interpretation = InterpretationRecord.model_validate(record)
        created, _ = self._write_immutable(
            "interpretations", interpretation.interpretation_id, interpretation
        )
        if created:
            self.append_audit(
                actor=actor,
                action="interpretation_saved",
                target_id=interpretation.interpretation_id,
                details={"document_digest": interpretation.document_digest},
            )
        return interpretation

    def load_interpretation(self, interpretation_id: str) -> InterpretationRecord:
        return self._load(
            "interpretations", interpretation_id, InterpretationRecord
        )

    def save_report(
        self,
        record: VerificationReport | Mapping[str, Any],
        *,
        actor: str = "system",
    ) -> VerificationReport:
        report = VerificationReport.model_validate(record)
        created, _ = self._write_immutable("reports", report.report_id, report)
        if created:
            self.append_audit(
                actor=actor,
                action="report_saved",
                target_id=report.report_id,
                details={
                    "document_digest": report.document_digest,
                    "report_digest": report.report_digest,
                },
            )
        return report

    def load_report(self, report_id: str) -> VerificationReport:
        return self._load("reports", report_id, VerificationReport)

    def save_proposal(
        self,
        *,
        actor: str,
        domain: str,
        kind: ProposalKind,
        payload: Mapping[str, Any],
        proposal_id: str | None = None,
    ) -> ScienceProposalRecord:
        proposal = ScienceProposalRecord(
            proposal_id=proposal_id or f"sci-proposal:{uuid.uuid4()}",
            created_at=_utc_now(),
            created_by=actor,
            domain=domain,
            kind=kind,
            payload=dict(payload),
        )
        created, _ = self._write_immutable("proposals", proposal.proposal_id, proposal)
        if created:
            self.append_audit(
                actor=actor,
                action="proposal_saved",
                target_id=proposal.proposal_id,
                details={"domain": proposal.domain, "kind": proposal.kind},
            )
        return proposal

    def load_proposal(self, proposal_id: str) -> ScienceProposalRecord:
        return self._load("proposals", proposal_id, ScienceProposalRecord)

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        actor: str,
        roles: Sequence[str],
    ) -> ScienceProposalApproval:
        with self._exclusive():
            proposal = self._load("proposals", proposal_id, ScienceProposalRecord)
            self.authorization.require_proposal_approval(
                actor=actor,
                roles=roles,
                domain=proposal.domain,
                proposed_by=proposal.created_by,
            )
            approval_id = "sci-approval:" + proposal.proposal_id.removeprefix(
                "sci-proposal:"
            )
            approval_path = self.record_path("proposal-approvals", approval_id)
            if approval_path.exists():
                existing = self._load(
                    "proposal-approvals", approval_id, ScienceProposalApproval
                )
                if existing.approved_by == actor:
                    return existing
                raise ImmutableScienceRecordError(
                    f"immutable record collision for {approval_id}"
                )
            approval = ScienceProposalApproval(
                approval_id=approval_id,
                proposal_id=proposal.proposal_id,
                approved_at=_utc_now(),
                approved_by=actor,
                domain=proposal.domain,
                proposal_kind=proposal.kind,
            )
            self._write_immutable_locked(
                "proposal-approvals", approval.approval_id, approval
            )
        self.append_audit(
            actor=actor,
            action="proposal_approved_for_release_candidate",
            target_id=proposal.proposal_id,
            details={"approval_id": approval.approval_id, "domain": proposal.domain},
        )
        return approval

    def append_audit(
        self,
        *,
        actor: str,
        action: str,
        target_id: str,
        details: Mapping[str, Any] | None = None,
    ) -> ScienceAuditRecord:
        sanitized = _sanitize_audit_value(dict(details or {}))
        event = ScienceAuditRecord(
            event_id=f"sci-audit:{uuid.uuid4()}",
            occurred_at=_utc_now(),
            actor=actor,
            action=action,
            target_id=target_id,
            details=sanitized,
        )
        row = canonical_json_bytes(event) + b"\n"
        with self._exclusive():
            descriptor = os.open(
                self.audit_path,
                os.O_CREAT
                | os.O_APPEND
                | os.O_WRONLY
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                os.fchmod(descriptor, 0o600)
                written = os.write(descriptor, row)
                if written != len(row):
                    raise OSError("short Science audit append")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._fsync_directory(self.root)
        return event
