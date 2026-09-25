"""Append-only authority ledger and user-controlled active Release pointer."""

from __future__ import annotations

import fcntl
import copy
from collections import OrderedDict
from contextvars import ContextVar
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Iterator, Mapping

from .immutable_io import publish_immutable, replace_durable
from .diagnostic_timing import stage_timing

from .qualification_contract import (
    QualificationContractError,
    validate_qualification_receipt_payload,
)


class RecordKind(str, Enum):
    SOURCE_ARTIFACT = "SourceArtifact"
    EVIDENCE_SPAN = "EvidenceSpan"
    KNOWLEDGE_REVISION = "KnowledgeRevision"
    RUN = "Run"
    CHECK = "Check"
    VERDICT = "Verdict"
    PROMOTION_CANDIDATE = "PromotionCandidate"
    QUALIFICATION_RECEIPT = "QualificationReceipt"
    RELEASE_MANIFEST = "ReleaseManifest"
    ACTIVATION_EVENT = "ActivationEvent"
    ROLLBACK_RECEIPT = "RollbackReceipt"
    SOURCE_RIGHTS_RECORD = "SourceRightsRecord"
    KNOWLEDGE_SPACE_POLICY = "KnowledgeSpacePolicy"
    KNOWLEDGE_USE_QUALIFICATION = "KnowledgeUseQualification"
    LICENSE_RECEIPT = "LicenseReceipt"


AUTHORITY_BY_KIND = {
    RecordKind.SOURCE_ARTIFACT: frozenset({"intake_service"}),
    RecordKind.EVIDENCE_SPAN: frozenset({"intake_service", "evidence_service"}),
    RecordKind.KNOWLEDGE_REVISION: frozenset({"agent", "migration_service"}),
    RecordKind.RUN: frozenset(
        {"executor", "science_evaluator", "query_attester", "mapping_validator", "migration_service"}
    ),
    RecordKind.CHECK: frozenset(
        {"science_evaluator", "query_attester", "mapping_validator", "qualification_service"}
    ),
    RecordKind.VERDICT: frozenset({"science_evaluator", "query_attester"}),
    RecordKind.PROMOTION_CANDIDATE: frozenset({"promotion_service", "migration_service"}),
    RecordKind.QUALIFICATION_RECEIPT: frozenset({"qualification_service"}),
    RecordKind.RELEASE_MANIFEST: frozenset({"release_service"}),
    RecordKind.ACTIVATION_EVENT: frozenset({"user"}),
    RecordKind.ROLLBACK_RECEIPT: frozenset({"user"}),
    RecordKind.SOURCE_RIGHTS_RECORD: frozenset({"rights_service"}),
    RecordKind.KNOWLEDGE_SPACE_POLICY: frozenset({"rights_service"}),
    RecordKind.KNOWLEDGE_USE_QUALIFICATION: frozenset({"qualification_service"}),
    RecordKind.LICENSE_RECEIPT: frozenset({"rights_service"}),
}


class LedgerError(RuntimeError):
    pass


class AuthorityViolation(LedgerError):
    pass


class ImmutableRecordConflict(LedgerError):
    pass


class PointerCASConflict(LedgerError):
    pass


@dataclass(frozen=True)
class LedgerRecord:
    record_id: str
    kind: RecordKind
    authority: str
    occurred_at: str
    payload: dict[str, Any]
    path: Path


@dataclass(frozen=True)
class LedgerIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class LedgerVerification:
    errors: tuple[LedgerIssue, ...] = ()
    record_count: int = 0
    event_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_id(kind: RecordKind, envelope: Mapping[str, Any]) -> str:
    return f"{kind.value}:sha256:{hashlib.sha256(canonical_json(envelope)).hexdigest()}"


def record_digest(record_id: str) -> str:
    """Project a typed ledger id to the canonical digest used by runtime surfaces."""

    _kind, algorithm, digest = record_id.split(":", 2)
    return f"{algorithm}:{digest}"


_READ_DECODING = ContextVar('ledger_verified_decoding', default=None)

# A locked append may reuse an exact previously verified prefix and verify only
# newly appended event lines. Byte equality still detects edits to any earlier
# event. Bound the retained decoded chain to one modest ledger per process.
_CHECKED_EVENT_CHAIN_CACHE = OrderedDict()
_CHECKED_EVENT_CHAIN_CACHE_LOCK = RLock()
_CHECKED_EVENT_CHAIN_CACHE_MAX_BYTES = 64 * 1024 * 1024


@contextmanager
def request_ledger_decoding():
    """Reuse verified decoding and opted-in audits within one query action.

    Record reads always inspect current bytes. An opted-in active release audit
    rechecks the current event fingerprint and every selected record. Policy
    and active pointer checks remain fresh. Decoded records are bounded to
    1024 records / 8 MiB and mutable results never alias the saved decoding.
    """
    state = {'records': {}, 'bytes': 0, 'verifications': {}, 'active_verifications': {},
             'checked_event_prefixes': {}}
    token = _READ_DECODING.set(state)
    try:
        yield
    finally:
        _READ_DECODING.reset(token)


class GovernedRuntimeLedger:
    """Filesystem reference ledger.

    Records are content addressed.  ``events.jsonl`` supplies append order and a
    hash chain.  The active pointer is mutable only through user activation or
    rollback methods and is guarded by compare-and-swap.
    """

    SCHEMA = "boi-governed-ledger/v1"

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.records_root = self.root / "records"
        self.events_path = self.root / "events.jsonl"
        self.pointer_path = self.root / "active-release.json"
        self.lock_path = self.root / ".ledger.lock"
        self.records_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _record_path(self, record_id: str) -> Path:
        try:
            kind_text, algorithm, digest = record_id.split(":", 2)
            kind = RecordKind(kind_text)
        except (ValueError, KeyError) as exc:
            raise LedgerError(f"invalid record id: {record_id}") from exc
        if algorithm != "sha256" or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise LedgerError(f"invalid record digest: {record_id}")
        return self.records_root / kind.value / f"{digest}.json"

    def append(
        self,
        kind: RecordKind,
        payload: Mapping[str, Any],
        *,
        authority: str,
        occurred_at: str,
    ) -> LedgerRecord:
        if kind in {RecordKind.ACTIVATION_EVENT, RecordKind.ROLLBACK_RECEIPT}:
            raise AuthorityViolation(f"{kind.value} must be created through the active-pointer transaction")
        with self._locked():
            return self._append_locked(kind, payload, authority=authority, occurred_at=occurred_at)

    def _append_locked(
        self,
        kind: RecordKind,
        payload: Mapping[str, Any],
        *,
        authority: str,
        occurred_at: str,
        pointer_transaction: bool = False,
    ) -> LedgerRecord:
        self._validate_authority(kind, payload, authority, pointer_transaction=pointer_transaction)
        prefix = self.events_path.read_bytes() if self.events_path.exists() else b""
        checked_events = (self._checked_events_locked(prefix=prefix), prefix)
        envelope = {
            "schema": self.SCHEMA,
            "kind": kind.value,
            "authority": authority,
            "occurred_at": occurred_at,
            "payload": dict(payload),
        }
        record_id = sha256_id(kind, envelope)
        path = self._record_path(record_id)
        stored = {"record_id": record_id, **envelope}
        stored_bytes = canonical_json(stored) + b"\n"
        if path.exists():
            if path.read_bytes() != stored_bytes:
                raise ImmutableRecordConflict(f"immutable record bytes conflict: {record_id}")
            self._append_event_locked(record_id, kind, occurred_at, checked_events)
            return self._to_record(stored, path)

        publish_immutable(path, stored_bytes)
        if path.read_bytes() != stored_bytes:
            raise ImmutableRecordConflict(f"immutable record bytes conflict: {record_id}")
        self._append_event_locked(record_id, kind, occurred_at, checked_events)
        return self._to_record(stored, path)

    @stage_timing('immutable_ledger_append_batch')
    def append_batch(
        self, kind: RecordKind, payloads: Iterable[Mapping[str, Any]], *, authority: str, occurred_at: str,
    ) -> tuple[LedgerRecord, ...]:
        """Persist <=100 records and one event-log successor under the existing lock.

        This is a recoverable filesystem batch, not a cross-database transaction.
        An IO failure may leave immutable records without events. No success is
        returned until all events are durable; exact retry repairs only missing
        events. Callers keep their outbox incomplete until this method returns.
        """
        if kind in {RecordKind.ACTIVATION_EVENT, RecordKind.ROLLBACK_RECEIPT}:
            raise AuthorityViolation("active-pointer records require pointer transaction")
        bounded = []
        for payload in payloads:
            if len(bounded) >= 100:
                raise LedgerError("LEDGER_BATCH_LIMIT_EXCEEDED")
            bounded.append(dict(payload))
        if not bounded:
            raise LedgerError("LEDGER_BATCH_EMPTY")
        with self._locked():
            prefix = self.events_path.read_bytes() if self.events_path.exists() else b""
            checked_events = (self._checked_events_locked(prefix=prefix), prefix)
            prepared = []
            for payload in bounded:
                self._validate_authority(kind, payload, authority, pointer_transaction=False)
                envelope = {"schema": self.SCHEMA, "kind": kind.value, "authority": authority,
                            "occurred_at": occurred_at, "payload": payload}
                record_id = sha256_id(kind, envelope)
                path = self._record_path(record_id)
                stored = {"record_id": record_id, **envelope}
                raw = canonical_json(stored) + b"\n"
                if path.exists() and path.read_bytes() != raw:
                    raise ImmutableRecordConflict(f"immutable record bytes conflict: {record_id}")
                prepared.append((stored, path, raw))
            for stored, path, raw in prepared:
                if not path.exists():
                    publish_immutable(path, raw)
                if path.read_bytes() != raw:
                    raise ImmutableRecordConflict(f"immutable record bytes conflict: {stored['record_id']}")
            records = tuple(self._to_record(stored, path) for stored, path, raw in prepared)
            self._append_events_locked(records, checked_events=checked_events)
            return records

    def _validate_authority(
        self,
        kind: RecordKind,
        payload: Mapping[str, Any],
        authority: str,
        *,
        pointer_transaction: bool,
    ) -> None:
        if authority not in AUTHORITY_BY_KIND[kind]:
            raise AuthorityViolation(f"{authority} cannot create {kind.value}")
        if kind in {RecordKind.ACTIVATION_EVENT, RecordKind.ROLLBACK_RECEIPT} and not pointer_transaction:
            raise AuthorityViolation(f"{kind.value} requires pointer transaction")
        if kind is RecordKind.KNOWLEDGE_REVISION and authority == "agent" and payload.get("status") != "candidate":
            raise AuthorityViolation("agent can create candidate KnowledgeRevision only")
        if kind is RecordKind.VERDICT:
            expected_scope = "science" if authority == "science_evaluator" else "query"
            if payload.get("scope") != expected_scope:
                raise AuthorityViolation(f"{authority} can issue {expected_scope} Verdict only")
        if kind is RecordKind.RELEASE_MANIFEST:
            receipt_id = payload.get("qualification_receipt_id")
            if not isinstance(receipt_id, str):
                raise AuthorityViolation("ReleaseManifest requires qualification_receipt_id")
            receipt = self.read(receipt_id)
            if receipt.kind is not RecordKind.QUALIFICATION_RECEIPT:
                raise AuthorityViolation("ReleaseManifest requires a qualification receipt")
            try:
                validate_qualification_receipt_payload(receipt.payload)
            except QualificationContractError as exc:
                raise AuthorityViolation(
                    f"ReleaseManifest requires exact QualificationContract: {exc}"
                ) from exc
            if list(receipt.payload.get("revision_ids") or []) != list(payload.get("revision_ids") or []):
                raise AuthorityViolation("ReleaseManifest revisions must exactly match qualification receipt")

    def _append_event_locked(self, record_id: str, kind: RecordKind, occurred_at: str,
                             checked_events=None) -> None:
        record = self.read(record_id)
        if record.kind != kind or record.occurred_at != occurred_at:
            raise LedgerError("EVENT_RECORD_BINDING_MISMATCH")
        self._append_events_locked((record,), checked_events=checked_events)

    @stage_timing('immutable_ledger_event_chain_check')
    def _checked_events_locked(self, *, prefix: bytes | None = None) -> list[dict[str, Any]]:
        # The caller holds the ledger lock. Append callers may supply bytes
        # read under that lock; the append fence compares those exact bytes
        # with the current file before any event is committed or returned.
        # Rewritten historical bytes still force a full traversal.
        if prefix is None:
            prefix = self.events_path.read_bytes() if self.events_path.exists() else b""
        state = _READ_DECODING.get()
        cache = state['checked_event_prefixes'] if state is not None else None
        key = str(self.root.resolve())
        prior = cache.get(key) if cache is not None else None
        if prior is not None and prefix == prior[0]:
            return prior[1]
        with _CHECKED_EVENT_CHAIN_CACHE_LOCK:
            shared = _CHECKED_EVENT_CHAIN_CACHE.get(key)
            if shared is not None and prefix.startswith(shared[0]):
                _CHECKED_EVENT_CHAIN_CACHE.move_to_end(key)
            else:
                shared = None
        try:
            if prefix and not prefix.endswith(b"\n"):
                raise LedgerError("EVENT_LOG_BOUNDARY_INVALID")
            events = list(shared[1]) if shared is not None else []
            previous = events[-1]['event_digest'] if events else None
            seen = set(shared[2]) if shared is not None else set()
            suffix = prefix[len(shared[0]):] if shared is not None else prefix
            for line in suffix.decode('utf-8').splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                index = len(events) + 1
                body = {key: event.get(key) for key in
                        ("sequence", "previous_event_digest", "record_id", "kind", "occurred_at")}
                expected = "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()
                self._record_path(event['record_id'])
                if (event.get('sequence') != index or event.get('previous_event_digest') != previous
                    or event.get('event_digest') != expected or event['record_id'] in seen
                    or event['record_id'].split(':', 1)[0] != event.get('kind')):
                    raise LedgerError("EVENT_CHAIN_INTEGRITY_FAILED")
                previous = expected
                seen.add(event['record_id'])
                events.append(event)
            if cache is not None:
                if len(prefix) <= 64 * 1024 * 1024:
                    cache[key] = (prefix, events)
                else:
                    cache.pop(key, None)
            with _CHECKED_EVENT_CHAIN_CACHE_LOCK:
                if len(prefix) <= _CHECKED_EVENT_CHAIN_CACHE_MAX_BYTES:
                    _CHECKED_EVENT_CHAIN_CACHE.clear()
                    _CHECKED_EVENT_CHAIN_CACHE[key] = (prefix, tuple(events), frozenset(seen))
                else:
                    _CHECKED_EVENT_CHAIN_CACHE.pop(key, None)
            return events
        except LedgerError:
            if cache is not None:
                cache.pop(key, None)
            with _CHECKED_EVENT_CHAIN_CACHE_LOCK:
                _CHECKED_EVENT_CHAIN_CACHE.pop(key, None)
            raise
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            if cache is not None:
                cache.pop(key, None)
            with _CHECKED_EVENT_CHAIN_CACHE_LOCK:
                _CHECKED_EVENT_CHAIN_CACHE.pop(key, None)
            raise LedgerError("EVENT_CHAIN_PARSE_FAILED") from exc

    @stage_timing('immutable_ledger_event_append')
    def _append_events_locked(self, records: Iterable[LedgerRecord], *, checked_events=None) -> None:
        if checked_events is None:
            events = self._checked_events_locked()
            prefix = None
        else:
            # The caller holds the same exclusive lock throughout validation,
            # immutable publication and this append. Reuse no state across
            # calls, and reject even an out-of-lock change to the exact bytes.
            events, checked_prefix = checked_events
            current_prefix = self.events_path.read_bytes() if self.events_path.exists() else b""
            if current_prefix != checked_prefix:
                raise LedgerError("EVENT_LOG_CHANGED_DURING_APPEND")
            prefix = current_prefix
        by_record = {event['record_id']: event for event in events}
        additions = []
        previous = events[-1]["event_digest"] if events else None
        for record in records:
            old = by_record.get(record.record_id)
            if old is not None:
                if old['kind'] != record.kind.value or old['occurred_at'] != record.occurred_at:
                    raise LedgerError("EVENT_RECORD_BINDING_MISMATCH")
                continue
            body = {"sequence": len(events) + len(additions) + 1, "previous_event_digest": previous,
                    "record_id": record.record_id, "kind": record.kind.value, "occurred_at": record.occurred_at}
            event = {**body, "event_digest": "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()}
            additions.append(event)
            by_record[record.record_id] = event
            previous = event['event_digest']
        if additions:
            if prefix is None:
                prefix = self.events_path.read_bytes() if self.events_path.exists() else b""
            # Old event bytes remain an exact prefix; no historical reserialization.
            replace_durable(self.events_path, prefix + b"".join(canonical_json(event) + b"\n" for event in additions))

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    @stage_timing('immutable_ledger_read')
    def read(self, record_id: str) -> LedgerRecord:
        path = self._record_path(record_id)
        if not path.exists():
            raise LedgerError(f"record not found: {record_id}")
        # Read the current file on EVERY call, including cache hits. Equality
        # is over actual bytes, not mtime/stat or a cached permission decision.
        raw = path.read_bytes()
        state = _READ_DECODING.get()
        key = (self.SCHEMA, record_id)
        previous = state['records'].get(key) if state is not None else None
        if previous is not None and previous[0] == raw:
            return self._to_record(copy.deepcopy(previous[1]), path)
        stored = self._decode_verified(raw, record_id)
        if state is not None and len(raw) <= 8 * 1024 * 1024:
            if previous is not None:
                state['bytes'] -= len(previous[0])
                del state['records'][key]
            if len(state['records']) >= 1024 or state['bytes'] + len(raw) > 8 * 1024 * 1024:
                state['records'].clear()
                state['bytes'] = 0
            state['records'][key] = (raw, copy.deepcopy(stored))
            state['bytes'] += len(raw)
        return self._to_record(stored, path)

    @stage_timing('immutable_ledger_decode')
    def _decode_verified(self, raw, record_id):
        try:
            stored = json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ImmutableRecordConflict(f"record is not valid canonical JSON: {record_id}") from exc
        try:
            envelope = {key: stored[key] for key in ("schema", "kind", "authority", "occurred_at", "payload")}
            if (stored.get("record_id") != record_id or stored['schema'] != self.SCHEMA
                or sha256_id(RecordKind(stored['kind']), envelope) != record_id
                or not isinstance(stored['payload'], dict)):
                raise ValueError("envelope mismatch")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ImmutableRecordConflict(f"record digest mismatch: {record_id}") from exc
        return stored

    @staticmethod
    def _to_record(stored: Mapping[str, Any], path: Path) -> LedgerRecord:
        return LedgerRecord(
            record_id=str(stored["record_id"]),
            kind=RecordKind(stored["kind"]),
            authority=str(stored["authority"]),
            occurred_at=str(stored["occurred_at"]),
            payload=dict(stored["payload"]),
            path=path,
        )

    def active_pointer(self) -> dict[str, Any] | None:
        if not self.pointer_path.exists():
            return None
        return json.loads(self.pointer_path.read_text(encoding="utf-8"))

    def _validate_release_binding(self, release_id: str, qualification_receipt_id: str) -> LedgerRecord:
        release = self.read(release_id)
        if release.kind is not RecordKind.RELEASE_MANIFEST:
            raise AuthorityViolation("active pointer target must be a ReleaseManifest")
        if release.payload.get("qualification_receipt_id") != qualification_receipt_id:
            raise AuthorityViolation("activation receipt does not match ReleaseManifest")
        receipt = self.read(qualification_receipt_id)
        if receipt.kind is not RecordKind.QUALIFICATION_RECEIPT:
            raise AuthorityViolation("activation requires a qualification receipt")
        try:
            validate_qualification_receipt_payload(receipt.payload)
        except QualificationContractError as exc:
            raise AuthorityViolation(f"activation requires exact QualificationContract: {exc}") from exc
        return release

    def _check_cas(self, expected_current: str | None) -> dict[str, Any] | None:
        current = self.active_pointer()
        current_release = current.get("release_id") if current else None
        if current_release != expected_current:
            raise PointerCASConflict(f"active Release changed: expected {expected_current!r}, found {current_release!r}")
        return current

    def _write_pointer_locked(self, pointer: Mapping[str, Any]) -> None:
        temporary = self.root / ".active-release.json.tmp"
        with temporary.open("wb") as handle:
            handle.write(canonical_json(pointer) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.pointer_path)

    def activate_release(
        self,
        release_id: str,
        *,
        qualification_receipt_id: str,
        expected_current: str | None,
        authority: str,
        occurred_at: str,
    ) -> LedgerRecord:
        if authority != "user":
            raise AuthorityViolation("only user authority can activate a Release")
        with self._locked():
            self._validate_release_binding(release_id, qualification_receipt_id)
            current = self._check_cas(expected_current)
            event = self._append_locked(
                RecordKind.ACTIVATION_EVENT,
                {
                    "from_release_id": current.get("release_id") if current else None,
                    "to_release_id": release_id,
                    "qualification_receipt_id": qualification_receipt_id,
                },
                authority=authority,
                occurred_at=occurred_at,
                pointer_transaction=True,
            )
            pointer = {
                "schema": "boi-active-release-pointer/v1",
                "status": "ACTIVE",
                "release_id": release_id,
                "release_manifest_digest": record_digest(release_id),
                "qualification_receipt_id": qualification_receipt_id,
                "activation_event_id": event.record_id,
                "activation_digest": record_digest(event.record_id),
                "updated_at": occurred_at,
            }
            pointer["pointer_digest"] = "sha256:" + hashlib.sha256(canonical_json(pointer)).hexdigest()
            self._write_pointer_locked(pointer)
            return event

    def rollback_release(
        self,
        release_id: str,
        *,
        qualification_receipt_id: str,
        expected_current: str,
        authority: str,
        occurred_at: str,
        reason: str,
    ) -> LedgerRecord:
        if authority != "user":
            raise AuthorityViolation("only user authority can roll back a Release")
        if not reason.strip():
            raise AuthorityViolation("rollback reason is required")
        with self._locked():
            self._validate_release_binding(release_id, qualification_receipt_id)
            current = self._check_cas(expected_current)
            event = self._append_locked(
                RecordKind.ROLLBACK_RECEIPT,
                {
                    "from_release_id": current["release_id"],
                    "to_release_id": release_id,
                    "qualification_receipt_id": qualification_receipt_id,
                    "reason": reason,
                },
                authority=authority,
                occurred_at=occurred_at,
                pointer_transaction=True,
            )
            pointer = {
                "schema": "boi-active-release-pointer/v1",
                "status": "ACTIVE",
                "release_id": release_id,
                "release_manifest_digest": record_digest(release_id),
                "qualification_receipt_id": qualification_receipt_id,
                "rollback_receipt_id": event.record_id,
                "activation_digest": record_digest(event.record_id),
                "updated_at": occurred_at,
            }
            pointer["pointer_digest"] = "sha256:" + hashlib.sha256(canonical_json(pointer)).hexdigest()
            self._write_pointer_locked(pointer)
            return event

    def verify(self, *, reuse_request_audit: bool = False) -> LedgerVerification:
        """Verify the complete ledger, optionally once per synchronous request.

        The opt-in cache is only for callers that also read every selected
        content-addressed record through ``read`` and fence the active pointer
        before and after their operation.  ``read`` still verifies the current
        bytes of each selected record.  The default remains a fresh complete
        audit, including when called twice inside one request scope.

        Scanning file metadata to decide whether an audit can be reused is not
        useful here: this ledger can contain tens of thousands of immutable
        records, so that scan costs almost as much as verification itself.
        """
        state = _READ_DECODING.get()
        cache = state.get('verifications') if state is not None and reuse_request_audit else None
        key = str(self.root.resolve())
        if cache is not None and key in cache:
            return cache[key]
        errors: list[LedgerIssue] = []
        record_ids: set[str] = set()
        for path in sorted(self.records_root.glob("*/*.json")):
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                kind = RecordKind(stored["kind"])
                envelope = {key: stored[key] for key in ("schema", "kind", "authority", "occurred_at", "payload")}
                expected_id = sha256_id(kind, envelope)
                if stored.get("record_id") != expected_id or path != self._record_path(expected_id):
                    errors.append(LedgerIssue("RECORD_DIGEST_MISMATCH", str(path)))
                else:
                    record_ids.add(expected_id)
            except Exception:
                errors.append(LedgerIssue("RECORD_DIGEST_MISMATCH", str(path)))

        try:
            events = self._read_events()
        except Exception:
            result = LedgerVerification(
                errors=tuple(errors + [LedgerIssue("EVENT_PARSE_ERROR", str(self.events_path))]),
                record_count=len(record_ids),
                event_count=0,
            )
            if cache is not None:
                cache[key] = result
            return result
        previous = None
        event_record_ids: set[str] = set()
        for index, event in enumerate(events, start=1):
            base = {key: event.get(key) for key in ("sequence", "previous_event_digest", "record_id", "kind", "occurred_at")}
            expected_digest = "sha256:" + hashlib.sha256(canonical_json(base)).hexdigest()
            if (
                event.get("sequence") != index
                or event.get("previous_event_digest") != previous
                or event.get("event_digest") != expected_digest
            ):
                errors.append(LedgerIssue("EVENT_DIGEST_MISMATCH", f"sequence {index}"))
            previous = event.get("event_digest")
            event_record_ids.add(str(event.get("record_id")))
        for missing in sorted(event_record_ids - record_ids):
            errors.append(LedgerIssue("EVENT_RECORD_MISSING", missing))
        for unchained in sorted(record_ids - event_record_ids):
            errors.append(LedgerIssue("RECORD_EVENT_MISSING", unchained))

        if self.pointer_path.exists():
            try:
                pointer = self.active_pointer() or {}
                supplied = pointer.pop("pointer_digest")
                expected = "sha256:" + hashlib.sha256(canonical_json(pointer)).hexdigest()
                if supplied != expected or pointer.get("release_id") not in record_ids:
                    errors.append(LedgerIssue("ACTIVE_POINTER_INVALID", str(self.pointer_path)))
            except Exception:
                errors.append(LedgerIssue("ACTIVE_POINTER_INVALID", str(self.pointer_path)))
        result = LedgerVerification(tuple(errors), len(record_ids), len(events))
        if cache is not None:
            cache[key] = result
        return result

    def verify_active_release(self, pointer: Mapping[str, Any] | None = None, *,
                              reuse_request_audit: bool = False) -> LedgerVerification:
        """Verify the complete event chain and the active release's closed record set.

        Online profile reads do not depend on inactive historical record bodies.
        They do depend on the unbroken event history, the user pointer action,
        the exact qualification receipt and every revision named by the active
        manifest.  Selected records are still read through ``read`` afterwards,
        so their current bytes and content addresses are checked again.

        Optional request-local reuse fingerprints the current event-file bytes
        and rereads every selected content-addressed record before returning a
        previous successful verification. A changed digest falls through to
        the full audit. No result crosses a synchronous request boundary.

        The full ``verify`` audit remains the ledger-wide maintenance check.  It
        additionally detects missing or unchained inactive record bodies and is
        deliberately not placed on every user query.
        """
        supplied = dict(pointer if pointer is not None else (self.active_pointer() or {}))
        state = _READ_DECODING.get()
        cache = state['active_verifications'] if state is not None and reuse_request_audit else None
        errors: list[LedgerIssue] = []
        try:
            pointer_digest = supplied.pop("pointer_digest")
            expected_pointer = "sha256:" + hashlib.sha256(canonical_json(supplied)).hexdigest()
            if (pointer_digest != expected_pointer
                    or supplied.get("schema") != "boi-active-release-pointer/v1"
                    or supplied.get("status") != "ACTIVE"):
                raise ValueError("pointer")
            release_id = str(supplied["release_id"])
            receipt_id = str(supplied["qualification_receipt_id"])
            if (supplied.get("release_manifest_digest") != record_digest(release_id)):
                raise ValueError("release digest")
            event_id = supplied.get("activation_event_id") or supplied.get("rollback_receipt_id")
            if (not isinstance(event_id, str)
                    or supplied.get("activation_digest") != record_digest(event_id)):
                raise ValueError("activation digest")
        except Exception:
            return LedgerVerification((LedgerIssue("ACTIVE_POINTER_INVALID", str(self.pointer_path)),), 0, 0)

        cache_key = (str(self.root.resolve()), pointer_digest)
        cached = cache.get(cache_key) if cache is not None else None
        if cached is not None:
            event_fingerprint, selected_records, previous_result = cached
            try:
                if self._event_file_fingerprint() == event_fingerprint:
                    for selected_id in selected_records:
                        self.read(selected_id)
                    return previous_result
            except Exception:
                pass
            cache.pop(cache_key, None)

        event_fingerprint_before = self._event_file_fingerprint() if cache is not None else None
        try:
            events = self._checked_events_locked()
        except Exception:
            return LedgerVerification((LedgerIssue("EVENT_CHAIN_INVALID", str(self.events_path)),), 0, 0)
        event_ids = {str(event.get("record_id")) for event in events}
        selected_ids = {release_id, receipt_id, event_id}
        try:
            release = self.read(release_id)
            receipt = self.read(receipt_id)
            event = self.read(event_id)
            if (release.kind is not RecordKind.RELEASE_MANIFEST
                    or receipt.kind is not RecordKind.QUALIFICATION_RECEIPT
                    or event.kind not in (RecordKind.ACTIVATION_EVENT, RecordKind.ROLLBACK_RECEIPT)
                    or event.authority != "user"):
                raise ValueError("record kind")
            validate_qualification_receipt_payload(receipt.payload)
            revisions = list(release.payload.get("revision_ids") or [])
            if (release.payload.get("qualification_receipt_id") != receipt_id
                    or revisions != list(receipt.payload.get("revision_ids") or [])
                    or event.payload.get("to_release_id") != release_id
                    or event.payload.get("qualification_receipt_id") != receipt_id):
                raise ValueError("release binding")
            selected_ids.update(revisions)
            if not selected_ids <= event_ids:
                raise ValueError("event membership")
            if any(self.read(revision_id).kind is not RecordKind.KNOWLEDGE_REVISION
                    for revision_id in revisions):
                raise ValueError("release revision kind")
        except Exception:
            errors.append(LedgerIssue("ACTIVE_RELEASE_BINDING_INVALID", release_id))
        result = LedgerVerification(tuple(errors), len(selected_ids), len(events))
        if cache is not None and result.ok:
            event_fingerprint_after = self._event_file_fingerprint()
            if event_fingerprint_after == event_fingerprint_before:
                if len(cache) >= 4:
                    cache.clear()
                cache[cache_key] = (event_fingerprint_after, tuple(sorted(selected_ids)), result)
        return result

    def _event_file_fingerprint(self) -> tuple[int, str]:
        """Hash the actual event bytes in bounded memory, ignoring file metadata."""
        digest = hashlib.sha256()
        size = 0
        if self.events_path.exists():
            with self.events_path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    size += len(chunk)
                    digest.update(chunk)
        return size, digest.hexdigest()
