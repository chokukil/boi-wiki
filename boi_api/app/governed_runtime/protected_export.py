"""Persistent, fail-closed authority for protected complete-result delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_digest(value: str) -> bool:
    return (
        value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("PROTECTED_EXPORT_CLOCK_NOT_AWARE")
    return value.astimezone(timezone.utc)


class ProtectedExportGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str = Field(min_length=1)
    result_artifact_ref: str = Field(min_length=1)
    result_artifact_digest: str
    result_digest: str
    active_release_digest: str
    authorization_policy_digest: str
    acl_policy_digest: str
    principal: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    max_bytes: int = Field(ge=1, le=1_073_741_824)
    ttl_seconds: int = Field(ge=1, le=604_800)
    approval_digest: str

    @model_validator(mode="after")
    def validate_bindings(self) -> "ProtectedExportGrantRequest":
        for value in (
            self.result_artifact_digest,
            self.result_digest,
            self.active_release_digest,
            self.authorization_policy_digest,
            self.acl_policy_digest,
            self.approval_digest,
        ):
            if not _is_digest(value):
                raise ValueError("PROTECTED_EXPORT_DIGEST_INVALID")
        if self.principal != self.principal.strip() or self.purpose != self.purpose.strip():
            raise ValueError("PROTECTED_EXPORT_CONTEXT_INVALID")
        return self


class ProtectedExportEntitlement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-protected-export-entitlement/v1"]
    entitlement_id: str
    execution_id: str
    result_artifact_ref: str
    result_artifact_digest: str
    result_digest: str
    active_release_digest: str
    authorization_policy_digest: str
    acl_policy_digest: str
    principal: str
    purpose: str
    max_bytes: int
    issued_at: str
    expires_at: str
    approval_digest: str
    issued_by: str
    entitlement_digest: str


class ProtectedExportAuditReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-protected-export-audit-receipt/v1"]
    audit_sequence: int = Field(ge=1)
    entitlement_id: str
    execution_id: str
    principal: str
    purpose: str
    active_release_digest: str
    result_digest: str
    status: Literal["DELIVERED", "DENIED"]
    reason_code: str | None
    delivered_bytes: int
    occurred_at: str
    receipt_digest: str


@dataclass(frozen=True)
class ProtectedExportDelivery:
    artifact: dict[str, Any]
    receipt: ProtectedExportAuditReceipt


class ProtectedExportAuthority:
    """Content-addressed grants, revocations, and delivery audit receipts."""

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        acl_policy_resolver: Callable[[str, str], str | None],
    ) -> None:
        self.root = root
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.acl_policy_resolver = acl_policy_resolver
        self.grants_root = root / "grants"
        self.revocations_root = root / "revocations"
        self.audits_root = root / "audits"
        for directory in (self.root, self.grants_root, self.revocations_root, self.audits_root):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)

    @staticmethod
    def _hex_id(entitlement_id: str) -> str:
        prefix = "protected-export:sha256:"
        if not entitlement_id.startswith(prefix):
            raise ValueError("PROTECTED_EXPORT_ENTITLEMENT_ID_INVALID")
        value = entitlement_id.removeprefix(prefix)
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("PROTECTED_EXPORT_ENTITLEMENT_ID_INVALID")
        return value

    @staticmethod
    def _write_immutable(path: Path, payload: dict[str, Any]) -> None:
        encoded = _canonical_bytes(payload)
        if path.exists():
            if path.read_bytes() != encoded:
                raise ValueError("PROTECTED_EXPORT_IMMUTABLE_CONFLICT")
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.chmod(0o600)
        temporary.replace(path)

    def grant(
        self, request: ProtectedExportGrantRequest, *, authority: str
    ) -> ProtectedExportEntitlement:
        if authority not in {"user", "protected_export_authority"}:
            raise ValueError("PROTECTED_EXPORT_GRANT_AUTHORITY_REQUIRED")
        issued_at = _aware(self.clock())
        values = {
            "schema_name": "boi-protected-export-entitlement/v1",
            **request.model_dump(mode="json"),
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(seconds=request.ttl_seconds)).isoformat(),
            "issued_by": authority,
        }
        values.pop("ttl_seconds")
        entitlement_digest = _digest(values)
        entitlement_id = f"protected-export:{entitlement_digest}"
        payload = {
            **values,
            "entitlement_id": entitlement_id,
            "entitlement_digest": entitlement_digest,
        }
        entitlement = ProtectedExportEntitlement.model_validate(payload)
        path = self.grants_root / f"{entitlement_digest[7:]}.json"
        self._write_immutable(path, entitlement.model_dump(mode="json"))
        return entitlement

    def get(self, entitlement_id: str) -> ProtectedExportEntitlement:
        hex_id = self._hex_id(entitlement_id)
        path = self.grants_root / f"{hex_id}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entitlement = ProtectedExportEntitlement.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise ValueError("PROTECTED_EXPORT_ENTITLEMENT_NOT_FOUND") from error
        values = entitlement.model_dump(mode="json", exclude={"entitlement_id", "entitlement_digest"})
        expected = _digest(values)
        if (
            entitlement.entitlement_id != entitlement_id
            or expected != entitlement.entitlement_digest
            or expected[7:] != hex_id
        ):
            raise ValueError("PROTECTED_EXPORT_ENTITLEMENT_TAMPERED")
        return entitlement

    def revoke(
        self,
        entitlement_id: str,
        *,
        authority: str,
        reason: str,
        approval_digest: str,
    ) -> str:
        entitlement = self.get(entitlement_id)
        if authority not in {"user", "protected_export_authority"}:
            raise ValueError("PROTECTED_EXPORT_REVOCATION_AUTHORITY_REQUIRED")
        if not reason.strip() or not _is_digest(approval_digest):
            raise ValueError("PROTECTED_EXPORT_REVOCATION_INVALID")
        payload = {
            "schema_name": "boi-protected-export-revocation/v1",
            "entitlement_id": entitlement.entitlement_id,
            "entitlement_digest": entitlement.entitlement_digest,
            "authority": authority,
            "reason": reason.strip(),
            "approval_digest": approval_digest,
            "revoked_at": _aware(self.clock()).isoformat(),
        }
        revocation_digest = _digest(payload)
        record = {**payload, "revocation_digest": revocation_digest}
        path = self.revocations_root / f"{self._hex_id(entitlement_id)}.json"
        self._write_immutable(path, record)
        return revocation_digest

    def _is_revoked(self, entitlement_id: str) -> bool:
        return (self.revocations_root / f"{self._hex_id(entitlement_id)}.json").exists()

    def _audit(
        self,
        entitlement: ProtectedExportEntitlement,
        *,
        status: Literal["DELIVERED", "DENIED"],
        reason_code: str | None,
        delivered_bytes: int,
    ) -> ProtectedExportAuditReceipt:
        directory = self.audits_root / self._hex_id(entitlement.entitlement_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        with (directory / ".sequence.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            sequences = [
                int(path.name.split("-", 1)[0])
                for path in directory.glob("*.json")
                if path.name.split("-", 1)[0].isdigit()
            ]
            sequence = max(sequences, default=0) + 1
            values = {
                "schema_name": "boi-protected-export-audit-receipt/v1",
                "audit_sequence": sequence,
                "entitlement_id": entitlement.entitlement_id,
                "execution_id": entitlement.execution_id,
                "principal": entitlement.principal,
                "purpose": entitlement.purpose,
                "active_release_digest": entitlement.active_release_digest,
                "result_digest": entitlement.result_digest,
                "status": status,
                "reason_code": reason_code,
                "delivered_bytes": delivered_bytes,
                "occurred_at": _aware(self.clock()).isoformat(),
            }
            receipt = ProtectedExportAuditReceipt(
                **values, receipt_digest=_digest(values)
            )
            self._write_immutable(
                directory / f"{sequence:020d}-{receipt.receipt_digest[7:]}.json",
                receipt.model_dump(mode="json"),
            )
            return receipt

    def _deny(self, entitlement: ProtectedExportEntitlement, reason: str) -> None:
        self._audit(
            entitlement, status="DENIED", reason_code=reason, delivered_bytes=0
        )
        raise ValueError(reason)

    def export(
        self,
        entitlement_id: str,
        *,
        execution_id: str,
        principal: str,
        purpose: str,
        artifact_reader: Callable[..., dict[str, Any]],
    ) -> ProtectedExportDelivery:
        entitlement = self.get(entitlement_id)
        if execution_id != entitlement.execution_id:
            self._deny(entitlement, "PROTECTED_EXPORT_EXECUTION_MISMATCH")
        if principal != entitlement.principal or purpose != entitlement.purpose:
            self._deny(entitlement, "PROTECTED_EXPORT_CONTEXT_MISMATCH")
        if self._is_revoked(entitlement_id):
            self._deny(entitlement, "PROTECTED_EXPORT_ENTITLEMENT_REVOKED")
        if _aware(self.clock()) >= datetime.fromisoformat(entitlement.expires_at):
            self._deny(entitlement, "PROTECTED_EXPORT_ENTITLEMENT_EXPIRED")
        current_acl = self.acl_policy_resolver(principal, purpose)
        if current_acl != entitlement.acl_policy_digest:
            self._deny(entitlement, "PROTECTED_EXPORT_ACL_POLICY_STALE")
        try:
            artifact = artifact_reader(
                entitlement.result_artifact_ref,
                principal=principal,
                purpose=purpose,
            )
        except (RuntimeError, ValueError) as error:
            self._deny(entitlement, str(error).split(":", 1)[0])
        bindings = {
            "artifact_digest": entitlement.result_artifact_digest,
            "result_digest": entitlement.result_digest,
            "active_release_digest": entitlement.active_release_digest,
            "authorization_policy_digest": entitlement.authorization_policy_digest,
            "run_id": entitlement.execution_id,
        }
        if any(artifact.get(key) != value for key, value in bindings.items()):
            self._deny(entitlement, "PROTECTED_EXPORT_ARTIFACT_BINDING_MISMATCH")
        if any(item.get("paging") and len(item.get("rows", [])) < item.get("row_count", 0)
               for item in artifact.get("result_sets", [])):
            self._deny(entitlement, "PROTECTED_EXPORT_INCOMPLETE_PAGED_RESULT")
        delivered_bytes = len(_canonical_bytes(artifact))
        if delivered_bytes > entitlement.max_bytes:
            self._deny(entitlement, "PROTECTED_EXPORT_BYTE_CEILING_EXCEEDED")
        receipt = self._audit(
            entitlement,
            status="DELIVERED",
            reason_code=None,
            delivered_bytes=delivered_bytes,
        )
        return ProtectedExportDelivery(artifact=artifact, receipt=receipt)

    def audit_receipts(
        self, entitlement_id: str
    ) -> tuple[ProtectedExportAuditReceipt, ...]:
        directory = self.audits_root / self._hex_id(entitlement_id)
        if not directory.exists():
            return ()
        receipts = []
        for path in sorted(directory.glob("*.json")):
            receipt = ProtectedExportAuditReceipt.model_validate_json(path.read_text())
            values = receipt.model_dump(mode="json", exclude={"receipt_digest"})
            if _digest(values) != receipt.receipt_digest:
                raise ValueError("PROTECTED_EXPORT_AUDIT_TAMPERED")
            receipts.append(receipt)
        return tuple(receipts)


__all__ = [
    "ProtectedExportAuditReceipt",
    "ProtectedExportAuthority",
    "ProtectedExportDelivery",
    "ProtectedExportEntitlement",
    "ProtectedExportGrantRequest",
]
