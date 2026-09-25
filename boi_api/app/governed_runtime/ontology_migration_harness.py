"""Deterministic ontology migration lifecycle with separated approval/release."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json


class HarnessStateError(RuntimeError):
    pass


class HarnessAuthorityError(PermissionError):
    pass


_STATES = (
    "captured",
    "inventoried",
    "parsed",
    "physically_validated",
    "semantically_drafted",
    "deterministic_checked",
    "attention_required",
    "approval_ready",
    "approved",
    "released",
    "withheld",
    "blocked",
    "superseded",
    "rolled_back",
)

_TRANSITIONS = {
    "captured": {"inventoried", "blocked"},
    "inventoried": {"parsed", "blocked"},
    "parsed": {"physically_validated", "blocked"},
    "physically_validated": {"semantically_drafted", "blocked"},
    "semantically_drafted": {"deterministic_checked", "blocked"},
    "deterministic_checked": {"attention_required", "approval_ready", "blocked"},
    "attention_required": {"deterministic_checked", "withheld", "blocked"},
    "approval_ready": {"approved", "withheld", "blocked"},
    "approved": {"released", "withheld", "blocked"},
    "released": {"superseded", "rolled_back"},
    "withheld": {"semantically_drafted", "blocked"},
    "blocked": set(),
    "superseded": set(),
    "rolled_back": set(),
}


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


@dataclass(frozen=True)
class MigrationEvent:
    sequence: int
    from_state: str
    to_state: str
    actor_role: str
    candidate_digest: str
    qualification_receipt_id: str | None
    event_digest: str
    pipeline_contract_id: str = ''


@dataclass(frozen=True)
class MigrationRecord:
    migration_id: str
    source_manifest_digest: str
    candidate_digest: str
    current_state: str
    events: tuple[MigrationEvent, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        migration_id: str,
        source_manifest_digest: str,
        candidate_digest: str,
    ) -> "MigrationRecord":
        return cls(
            migration_id=migration_id,
            source_manifest_digest=source_manifest_digest,
            candidate_digest=candidate_digest,
            current_state="captured",
        )

    @property
    def approved(self) -> bool:
        return any(event.to_state == "approved" for event in self.events)

    @property
    def released(self) -> bool:
        return any(event.to_state == "released" for event in self.events)


class MigrationHarness:
    def __init__(self, record: MigrationRecord, *, pipeline_contract_id: str = '') -> None:
        if record.current_state not in _STATES:
            raise HarnessStateError(f"UNKNOWN_STATE:{record.current_state}")
        self.record = record
        self.pipeline_contract_id = pipeline_contract_id

    @staticmethod
    def allowed_states() -> tuple[str, ...]:
        return _STATES

    def transition(
        self,
        to_state: str,
        *,
        actor_role: str,
        qualification_receipt_id: str | None = None,
        expected_candidate_digest: str | None = None,
    ) -> MigrationRecord:
        from_state = self.record.current_state
        metadata_semantics = (self.pipeline_contract_id == 'boi/semantic-metadata-pipeline@1.0.0'
            and from_state == 'parsed' and to_state == 'semantically_drafted')
        if to_state not in _TRANSITIONS.get(from_state, set()) and not metadata_semantics:
            raise HarnessStateError(f"INVALID_TRANSITION:{from_state}->{to_state}")
        if to_state == "approved" and actor_role not in {"semantic_reviewer", "user"}:
            raise HarnessAuthorityError("APPROVAL_AUTHORITY_REQUIRED")
        if to_state == "released":
            if actor_role not in {"release_approver", "user"}:
                raise HarnessAuthorityError("RELEASE_AUTHORITY_REQUIRED")
            if not qualification_receipt_id:
                raise HarnessStateError("QUALIFICATION_RECEIPT_REQUIRED")
            if expected_candidate_digest != self.record.candidate_digest:
                raise HarnessStateError("CANDIDATE_DIGEST_MISMATCH")

        sequence = len(self.record.events) + 1
        event_payload = {
            "sequence": sequence,
            "migration_id": self.record.migration_id,
            "from_state": from_state,
            "to_state": to_state,
            "actor_role": actor_role,
            "candidate_digest": self.record.candidate_digest,
            "qualification_receipt_id": qualification_receipt_id,
        }
        if self.pipeline_contract_id:
            event_payload['pipeline_contract_id'] = self.pipeline_contract_id
        event = MigrationEvent(
            sequence=sequence,
            from_state=from_state,
            to_state=to_state,
            actor_role=actor_role,
            candidate_digest=self.record.candidate_digest,
            qualification_receipt_id=qualification_receipt_id,
            event_digest=_digest(event_payload),
            pipeline_contract_id=self.pipeline_contract_id,
        )
        self.record = replace(
            self.record,
            current_state=to_state,
            events=(*self.record.events, event),
        )
        return self.record
