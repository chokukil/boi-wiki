"""Authoritative, fail-closed lifecycle mutation for Science Releases.

The manager changes lifecycle metadata only.  It never approves scientific
content, manufactures holdout results, or issues a verification verdict.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from boi_api.app.auth import AuthIdentity
from boi_api.app.okf import split_frontmatter
from boi_api.app.science.catalog import (
    _release_manifest_digest,
    release_decision_material_digest,
)
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceOperationalError
from boi_api.app.science.models import ReleaseSelection


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class CatalogFactory(Protocol):
    def __call__(self, boi_root: Path) -> Any: ...


class CapabilityValidator(Protocol):
    def __call__(
        self,
        *,
        catalog: Any,
        release_id: str,
        release_digest: str,
        decision_material_digest: str,
        operation: Literal["activate"],
    ) -> Any: ...


class ReleaseActivationAuthority(BaseModel):
    """Closed G5/G6 authority bound to one frozen candidate Release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["science-release-activation-authority/0.1"]
    release_id: str = Field(min_length=1)
    release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_material_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    holdout_manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    holdout_result_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    channel_parity_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    channel_parity_status: Literal["passed"]
    qualification_status: Literal["passed"]
    authority_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_authority_digest(self) -> "ReleaseActivationAuthority":
        expected = sha256_digest(
            self.model_dump(mode="json", exclude={"authority_digest"})
        )
        if self.authority_digest != expected:
            raise ValueError("activation authority digest is not exact")
        return self


class _AuthorityRegistryEntry(BaseModel):
    """One externally provisioned, digest-closed G5/G6 authority record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str = Field(min_length=1)
    frozen_release_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_material_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    component_digests: dict[str, str]
    holdout_manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    holdout_result_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rule_freeze_commit: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    channel_parity_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    channels: tuple[Literal["Web", "REST", "MCP", "Markdown", "PDF"], ...]
    channel_parity_status: Literal["passed"]
    qualification_status: Literal["passed"]
    record_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_record(self) -> "_AuthorityRegistryEntry":
        if self.channels != ("Web", "REST", "MCP", "Markdown", "PDF"):
            raise ValueError("authority registry requires exact channel parity")
        if not self.component_digests or any(
            not isinstance(ref, str)
            or not ref.strip()
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
            for ref, digest in self.component_digests.items()
        ):
            raise ValueError("authority registry component digests are invalid")
        expected = sha256_digest(
            self.model_dump(mode="json", exclude={"record_digest"})
        )
        if self.record_digest != expected:
            raise ValueError("authority registry record digest is not exact")
        return self


class _AuthorityRegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["science-release-authority-registry/0.1"]
    entries: tuple[_AuthorityRegistryEntry, ...]
    registry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_registry(self) -> "_AuthorityRegistryFile":
        keys = [
            (item.release_id, item.frozen_release_content_hash)
            for item in self.entries
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("authority registry contains duplicate entries")
        expected = sha256_digest(
            self.model_dump(mode="json", exclude={"registry_digest"})
        )
        if self.registry_digest != expected:
            raise ValueError("authority registry digest is not exact")
        return self


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class ScienceAuthorityRegistry:
    """Read-only adapter for externally provisioned private G5/G6 authority."""

    FILE_NAME = "science-release-authority-registry.json"

    def __init__(self, authority_root: Path) -> None:
        self.authority_root = Path(authority_root).absolute()
        self.path = self.authority_root / self.FILE_NAME

    def _load(self) -> _AuthorityRegistryFile:
        try:
            self._assert_private_directory(
                self.authority_root.parent, "authority runtime root"
            )
            self._assert_private_directory(self.authority_root, "authority root")
            root_descriptor = os.open(
                self.authority_root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | os.O_CLOEXEC,
            )
            try:
                descriptor = os.open(
                    self.FILE_NAME,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_CLOEXEC,
                    dir_fd=root_descriptor,
                )
                try:
                    file_stat = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(file_stat.st_mode)
                        or file_stat.st_uid != os.getuid()
                        or file_stat.st_mode & 0o077
                    ):
                        raise ValueError("authority registry is not private")
                    raw = os.read(descriptor, 4 * 1024 * 1024 + 1)
                finally:
                    os.close(descriptor)
            finally:
                os.close(root_descriptor)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("authority registry exceeds its size limit")
            parsed = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys
            )
            return _AuthorityRegistryFile.model_validate(parsed)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError(
                "trusted Science authority registry is unavailable or invalid"
            ) from exc

    @staticmethod
    def _assert_private_directory(path: Path, label: str) -> None:
        if path.is_symlink():
            raise ValueError(f"{label} must not be a symlink")
        resolved = path.resolve(strict=True)
        if resolved != path.absolute():
            raise ValueError(f"{label} contains a symlink")
        directory_stat = resolved.stat()
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.getuid()
            or directory_stat.st_mode & 0o077
        ):
            raise ValueError(f"{label} is not private")

    def _entry(
        self, release_id: str, frozen_release_content_hash: str
    ) -> _AuthorityRegistryEntry | None:
        registry = self._load()
        matches = [
            item
            for item in registry.entries
            if item.release_id == release_id
            and item.frozen_release_content_hash == frozen_release_content_hash
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise ScienceOperationalError(
                "trusted Science authority registry is ambiguous"
            )
        return matches[0]

    def trusted_holdout_resolver(
        self, query: Mapping[str, str]
    ) -> dict[str, str] | None:
        if set(query) != {"release_id", "frozen_release_content_hash"}:
            raise ScienceOperationalError(
                "trusted Science authority registry query is invalid"
            )
        release_id = query.get("release_id")
        frozen = query.get("frozen_release_content_hash")
        if (
            not isinstance(release_id, str)
            or not release_id.strip()
            or not isinstance(frozen, str)
            or not _SHA256_RE.fullmatch(frozen)
        ):
            raise ScienceOperationalError(
                "trusted Science authority registry query is invalid"
            )
        entry = self._entry(release_id, frozen)
        if entry is None:
            return None
        return {
            "release_id": entry.release_id,
            "frozen_release_content_hash": entry.frozen_release_content_hash,
            "manifest_digest": entry.holdout_manifest_digest,
            "rule_freeze_commit": entry.rule_freeze_commit,
        }

    def validate_activation_authority(
        self,
        *,
        catalog: Any,
        release_id: str,
        release_digest: str,
        decision_material_digest: str,
        operation: Literal["activate"],
    ) -> ReleaseActivationAuthority:
        if operation != "activate":
            raise ScienceOperationalError(
                "trusted Science authority registry operation is invalid"
            )
        entry = self._entry(release_id, release_digest)
        if entry is None:
            raise ScienceOperationalError(
                "trusted Science authority registry has no exact Release entry"
            )
        try:
            release = catalog.resolve_release(release_id)
            holdout = catalog.resolve_independent_holdout_qualification(release)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError(
                "trusted Science authority registry cannot validate G5"
            ) from exc
        release_status = getattr(release, "status", None)
        exact_release_binding = (
            getattr(release, "content_hash", None) == release_digest
            if release_status == "release_candidate"
            else getattr(release, "frozen_release_content_hash", None)
            == release_digest
        )
        if (
            not exact_release_binding
            or entry.decision_material_digest != decision_material_digest
            or dict(getattr(release, "component_digests", {}))
            != entry.component_digests
            or not isinstance(holdout, Mapping)
            or holdout.get("qualification_gate") != "G5"
            or holdout.get("object_digest") != entry.holdout_manifest_digest
            or holdout.get("result_digest") != entry.holdout_result_digest
        ):
            raise ScienceOperationalError(
                "trusted Science authority registry does not match exact G5/G6 material"
            )
        payload = {
            "schema_version": "science-release-activation-authority/0.1",
            "release_id": entry.release_id,
            "release_digest": entry.frozen_release_content_hash,
            "decision_material_digest": entry.decision_material_digest,
            "holdout_manifest_digest": entry.holdout_manifest_digest,
            "holdout_result_digest": entry.holdout_result_digest,
            "channel_parity_digest": entry.channel_parity_digest,
            "channel_parity_status": entry.channel_parity_status,
            "qualification_status": entry.qualification_status,
        }
        return ReleaseActivationAuthority(
            **payload,
            authority_digest=sha256_digest(payload),
        )


class ReleaseMutationResult(BaseModel):
    """Audit-safe result of one exact lifecycle operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["science-release-mutation-result/0.1"] = (
        "science-release-mutation-result/0.1"
    )
    operation: Literal["activate", "withdraw"]
    release_id: str
    status: Literal["active", "withdrawn"]
    input_release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    resulting_release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_material_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    actor_id: str
    occurred_at: str
    idempotent: bool


class ScienceReleaseManager:
    """Mutate only lifecycle fields after exact external authority is proven."""

    def __init__(
        self,
        *,
        boi_root: Path,
        lock_root: Path,
        catalog_factory: CatalogFactory,
        capability_validator: CapabilityValidator,
        roles_for: Callable[[str], Sequence[str]],
        clock: Callable[[], datetime],
        reload_callback: Callable[[Any], None],
    ) -> None:
        self.boi_root = Path(boi_root).resolve()
        self.science_root = self.boi_root / "public" / "science"
        self._lock_root = Path(lock_root).absolute()
        self._catalog_factory = catalog_factory
        self._capability_validator = capability_validator
        self._roles_for = roles_for
        self._clock = clock
        self._reload_callback = reload_callback
        lock_identity = hashlib.sha256(
            str(self.boi_root).encode("utf-8")
        ).hexdigest()
        self._lock_path = self._lock_root / (
            f"boi-science-release-manager-{lock_identity}.lock"
        )

    def activate(
        self,
        *,
        release_id: str,
        release_digest: str,
        request_digest: str,
        idempotency_key: str,
        identity: AuthIdentity,
    ) -> ReleaseMutationResult:
        return self._mutate(
            operation="activate",
            release_id=release_id,
            release_digest=release_digest,
            request_digest=request_digest,
            idempotency_key=idempotency_key,
            identity=identity,
        )

    def withdraw(
        self,
        *,
        release_id: str,
        release_digest: str,
        request_digest: str,
        idempotency_key: str,
        identity: AuthIdentity,
    ) -> ReleaseMutationResult:
        return self._mutate(
            operation="withdraw",
            release_id=release_id,
            release_digest=release_digest,
            request_digest=request_digest,
            idempotency_key=idempotency_key,
            identity=identity,
        )

    def _mutate(
        self,
        *,
        operation: Literal["activate", "withdraw"],
        release_id: str,
        release_digest: str,
        request_digest: str,
        idempotency_key: str,
        identity: AuthIdentity,
    ) -> ReleaseMutationResult:
        actor_id = self._require_admin(identity)
        self._validate_digests(
            operation=operation,
            release_id=release_id,
            release_digest=release_digest,
            request_digest=request_digest,
        )
        idempotency_digest = self._idempotency_digest(idempotency_key)
        now = self._trusted_now()

        lock_descriptor = self._open_private_lock()
        with os.fdopen(lock_descriptor, "a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                existing = self._idempotent_result(
                    operation=operation,
                    release_id=release_id,
                    release_digest=release_digest,
                    request_digest=request_digest,
                    idempotency_digest=idempotency_digest,
                    actor_id=actor_id,
                )
                if existing is not None:
                    return existing
                return self._mutate_locked(
                    operation=operation,
                    release_id=release_id,
                    release_digest=release_digest,
                    request_digest=request_digest,
                    idempotency_digest=idempotency_digest,
                    actor_id=actor_id,
                    now=now,
                )
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _mutate_locked(
        self,
        *,
        operation: Literal["activate", "withdraw"],
        release_id: str,
        release_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor_id: str,
        now: datetime,
    ) -> ReleaseMutationResult:
        catalog = self._build_catalog(self.boi_root)
        resolved = self._resolve_release(catalog, release_id)
        if getattr(resolved, "content_hash", None) != release_digest:
            raise ScienceOperationalError("stored Release digest does not match request")

        release_path, metadata, body, original = self._release_document(release_id)
        self._assert_preapproved(metadata, actor_id=actor_id)
        decision_digest = self._decision_digest(resolved)
        authority: ReleaseActivationAuthority | None = None
        frozen_digest = release_digest

        if operation == "activate":
            if getattr(resolved, "status", None) != "release_candidate":
                raise ScienceOperationalError(
                    "only an inactive Release candidate can be activated"
                )
            authority = self._activation_authority(
                catalog=catalog,
                release_id=release_id,
                release_digest=release_digest,
                decision_digest=decision_digest,
            )
        else:
            self._assert_current_operational_release(catalog, release_id)
            frozen_digest = getattr(resolved, "frozen_release_content_hash", None)
            if not isinstance(frozen_digest, str) or not _SHA256_RE.fullmatch(
                frozen_digest
            ):
                raise ScienceOperationalError(
                    "active Release has no frozen candidate digest"
                )

        mutated = self._lifecycle_metadata(
            metadata,
            operation=operation,
            release_id=release_id,
            release_digest=release_digest,
            frozen_digest=frozen_digest,
            decision_digest=decision_digest,
            request_digest=request_digest,
            idempotency_digest=idempotency_digest,
            authority_digest=(authority.authority_digest if authority else None),
            actor_id=actor_id,
            now=now,
            body=body,
        )
        staged_bytes = self._render_release(mutated, body, original)
        staged_catalog, staged_resolved = self._validate_staged(
            release_path=release_path,
            release_id=release_id,
            operation=operation,
            release_digest=release_digest,
            frozen_digest=frozen_digest,
            decision_digest=decision_digest,
            authority=authority,
            staged_bytes=staged_bytes,
        )
        resulting_digest = str(getattr(staged_resolved, "content_hash", ""))
        if not _SHA256_RE.fullmatch(resulting_digest):
            raise ScienceOperationalError(
                "staged Release has no exact resulting content digest"
            )

        self._publish_with_rollback(
            release_path=release_path,
            original=original,
            staged_bytes=staged_bytes,
            release_id=release_id,
            operation=operation,
            release_digest=release_digest,
            frozen_digest=frozen_digest,
            decision_digest=decision_digest,
            authority=authority,
        )
        return ReleaseMutationResult(
            operation=operation,
            release_id=release_id,
            status="active" if operation == "activate" else "withdrawn",
            input_release_digest=release_digest,
            resulting_release_digest=resulting_digest,
            decision_material_digest=decision_digest,
            request_digest=request_digest,
            idempotency_key_digest=idempotency_digest,
            authority_digest=(authority.authority_digest if authority else None),
            actor_id=actor_id,
            occurred_at=now.isoformat(),
            idempotent=False,
        )

    def _require_admin(self, identity: AuthIdentity) -> str:
        employee_id = getattr(identity, "employee_id", None)
        if not isinstance(employee_id, str) or not employee_id.strip():
            raise ScienceOperationalError("trusted human Admin identity is required")
        try:
            roles = {
                role for role in self._roles_for(employee_id) if isinstance(role, str)
            }
        except Exception as exc:
            raise ScienceOperationalError(
                "trusted science.admin role resolution failed"
            ) from exc
        if "science.admin" not in roles:
            raise ScienceOperationalError("trusted science.admin role is required")
        return employee_id.strip()

    def _open_private_lock(self) -> int:
        """Open one owned, non-symlink lock in the injected private runtime root."""

        try:
            ScienceAuthorityRegistry._assert_private_directory(
                self._lock_root.parent, "lock runtime root"
            )
            if self._lock_root.exists() and self._lock_root.is_symlink():
                raise ValueError("lock root must not be a symlink")
            self._lock_root.mkdir(exist_ok=True, mode=0o700)
            ScienceAuthorityRegistry._assert_private_directory(
                self._lock_root, "lock root"
            )
            root_descriptor = os.open(
                self._lock_root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | os.O_CLOEXEC,
            )
            try:
                descriptor = os.open(
                    self._lock_path.name,
                    os.O_RDWR
                    | os.O_CREAT
                    | getattr(os, "O_NOFOLLOW", 0)
                    | os.O_CLOEXEC,
                    0o600,
                    dir_fd=root_descriptor,
                )
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_uid != os.getuid()
                    or opened.st_mode & 0o077
                ):
                    os.close(descriptor)
                    raise ValueError("lock file is not private")
                return descriptor
            finally:
                os.close(root_descriptor)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError(
                "private Science Release mutation lock is unavailable"
            ) from exc

    @staticmethod
    def _validate_digests(
        *,
        operation: str,
        release_id: str,
        release_digest: str,
        request_digest: str,
    ) -> None:
        if not isinstance(release_id, str) or not release_id.strip():
            raise ScienceOperationalError("Release ID is required")
        if not isinstance(release_digest, str) or not _SHA256_RE.fullmatch(
            release_digest
        ):
            raise ScienceOperationalError("Release digest is invalid")
        expected = sha256_digest(
            {
                "operation": operation,
                "release_id": release_id,
                "release_digest": release_digest,
            }
        )
        if request_digest != expected:
            raise ScienceOperationalError("Release request digest is not exact")

    @staticmethod
    def _idempotency_digest(value: str) -> str:
        if not isinstance(value, str) or not 8 <= len(value) <= 256:
            raise ScienceOperationalError("Release idempotency key is malformed")
        return sha256_digest(value)

    def _trusted_now(self) -> datetime:
        try:
            now = self._clock()
        except Exception as exc:
            raise ScienceOperationalError("trusted Science clock failed") from exc
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ScienceOperationalError(
                "trusted Science clock must return an aware datetime"
            )
        return now

    def _build_catalog(self, root: Path) -> Any:
        try:
            return self._catalog_factory(Path(root))
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError("Science Catalog validation failed") from exc

    @staticmethod
    def _resolve_release(catalog: Any, release_id: str) -> Any:
        try:
            return catalog.resolve_release(release_id)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError("Release resolution failed closed") from exc

    @staticmethod
    def _decision_digest(release: Any) -> str:
        stored = getattr(release, "decision_material_digest", None)
        try:
            actual = release_decision_material_digest(release)
        except Exception:
            actual = stored
        if not isinstance(actual, str) or not _SHA256_RE.fullmatch(actual):
            raise ScienceOperationalError(
                "Release has no exact decision material digest"
            )
        if stored is not None and stored != actual:
            raise ScienceOperationalError("Release decision material digest drifted")
        return actual

    def _activation_authority(
        self,
        *,
        catalog: Any,
        release_id: str,
        release_digest: str,
        decision_digest: str,
    ) -> ReleaseActivationAuthority:
        try:
            raw = self._capability_validator(
                catalog=catalog,
                release_id=release_id,
                release_digest=release_digest,
                decision_material_digest=decision_digest,
                operation="activate",
            )
            authority = ReleaseActivationAuthority.model_validate(raw)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError(
                "trusted activation authority is unavailable"
            ) from exc
        if (
            authority.release_id != release_id
            or authority.release_digest != release_digest
            or authority.decision_material_digest != decision_digest
        ):
            raise ScienceOperationalError(
                "activation authority does not match exact Release decision material"
            )
        return authority

    @staticmethod
    def _assert_preapproved(metadata: Mapping[str, Any], *, actor_id: str) -> None:
        science = metadata.get("science")
        review = metadata.get("review")
        if (
            metadata.get("status") != "approved"
            or not isinstance(review, Mapping)
            or review.get("review_status") != "approved"
            or not isinstance(review.get("authorized_review_events"), list)
            or not review.get("authorized_review_events")
            or not isinstance(science, Mapping)
            or science.get("release_eligibility") != "active_release_eligible"
        ):
            raise ScienceOperationalError(
                "Release must be already Admin-approved and activation-eligible"
            )
        author = metadata.get("author")
        if (
            isinstance(author, Mapping)
            and author.get("type") == "human"
            and author.get("user_id") == actor_id
        ):
            raise ScienceOperationalError("Release author self-activation is forbidden")

    def _assert_current_operational_release(self, catalog: Any, release_id: str) -> None:
        try:
            active = catalog.active_release()
            if getattr(active, "release_id", None) != release_id:
                raise ScienceOperationalError(
                    "withdrawal target is not the authoritative active Release"
                )
            release_set = catalog.resolve_release_set(
                ReleaseSelection(foundation=release_id)
            )
            catalog.resolve_operational_rule_set(release_set)
        except Exception as exc:
            if isinstance(exc, ScienceOperationalError):
                raise
            raise ScienceOperationalError(
                "active Release authority is unavailable for withdrawal"
            ) from exc

    @staticmethod
    def _lifecycle_metadata(
        metadata: Mapping[str, Any],
        *,
        operation: Literal["activate", "withdraw"],
        release_id: str,
        release_digest: str,
        frozen_digest: str,
        decision_digest: str,
        request_digest: str,
        idempotency_digest: str,
        authority_digest: str | None,
        actor_id: str,
        now: datetime,
        body: str,
    ) -> dict[str, Any]:
        mutated = deepcopy(dict(metadata))
        science = mutated.get("science")
        if not isinstance(science, dict):
            raise ScienceOperationalError("Release science metadata is invalid")
        science["frozen_release_content_hash"] = (
            release_digest if operation == "activate" else frozen_digest
        )
        science["decision_material_digest"] = decision_digest
        science["status"] = "active" if operation == "activate" else "withdrawn"
        science["active"] = operation == "activate"

        activation = mutated.get("activation")
        if not isinstance(activation, dict):
            activation = {
                "activation_status": "inactive",
                "authorized_activation_events": [],
            }
            mutated["activation"] = activation
        events = activation.get("authorized_activation_events")
        if not isinstance(events, list):
            raise ScienceOperationalError("Release activation audit is malformed")
        event: dict[str, Any] = {
            "decision": "activated" if operation == "activate" else "withdrawn",
            "operation": operation,
            "actor": {"type": "human", "user_id": actor_id},
            "occurred_at": now.isoformat(),
            "release_id": release_id,
            "release_digest": release_digest,
            "decision_material_digest": decision_digest,
            "request_digest": request_digest,
            "idempotency_key_digest": idempotency_digest,
        }
        if authority_digest is not None:
            event["authority_digest"] = authority_digest
        events.append(event)
        activation["activation_status"] = (
            "active" if operation == "activate" else "withdrawn"
        )
        science["content_hash"] = _release_manifest_digest(mutated, body)
        return mutated

    def _release_document(
        self, release_id: str
    ) -> tuple[Path, dict[str, Any], str, bytes]:
        release_root = (self.science_root / "releases").resolve()
        if not release_root.is_dir():
            raise ScienceOperationalError("Science Release root is unavailable")
        matches: list[tuple[Path, dict[str, Any], str, bytes]] = []
        for path in sorted(release_root.glob("*.md")):
            resolved = path.resolve()
            if not resolved.is_relative_to(release_root):
                raise ScienceOperationalError("Science Release path escapes its root")
            try:
                original = path.read_bytes()
                metadata, body = split_frontmatter(original.decode("utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise ScienceOperationalError("Science Release is unreadable") from exc
            science = metadata.get("science")
            if isinstance(science, Mapping) and science.get("release_id") == release_id:
                matches.append((resolved, metadata, body, original))
        if len(matches) != 1:
            raise ScienceOperationalError("exactly one stored Science Release is required")
        return matches[0]

    @staticmethod
    def _render_release(
        metadata: dict[str, Any], body: str, original: bytes
    ) -> bytes:
        # Keep JSON-frontmatter repositories readable; YAML fixtures remain YAML.
        original_text = original.decode("utf-8")
        frontmatter = original_text.split("---", 2)[1].lstrip()
        if frontmatter.startswith("{"):
            serialized = json.dumps(metadata, ensure_ascii=False, indent=2)
        else:
            serialized = yaml.safe_dump(
                metadata, sort_keys=False, allow_unicode=True
            ).rstrip()
        return f"---\n{serialized}\n---{body}".encode("utf-8")

    def _validate_staged(
        self,
        *,
        release_path: Path,
        release_id: str,
        operation: Literal["activate", "withdraw"],
        release_digest: str,
        frozen_digest: str,
        decision_digest: str,
        authority: ReleaseActivationAuthority | None,
        staged_bytes: bytes,
    ) -> tuple[Any, Any]:
        with tempfile.TemporaryDirectory(prefix="boi-science-release-stage-") as raw:
            staged_root = Path(raw) / "boi"
            staged_science = staged_root / "public" / "science"
            shutil.copytree(self.science_root, staged_science)
            relative = release_path.relative_to(self.science_root)
            staged_path = staged_science / relative
            staged_path.write_bytes(staged_bytes)
            catalog = self._build_catalog(staged_root)
            resolved = self._resolve_release(catalog, release_id)
            self._assert_staged_identity(
                catalog=catalog,
                resolved=resolved,
                operation=operation,
                release_id=release_id,
                release_digest=release_digest,
                frozen_digest=frozen_digest,
                decision_digest=decision_digest,
                authority=authority,
            )
            return catalog, resolved

    def _assert_staged_identity(
        self,
        *,
        catalog: Any,
        resolved: Any,
        operation: Literal["activate", "withdraw"],
        release_id: str,
        release_digest: str,
        frozen_digest: str,
        decision_digest: str,
        authority: ReleaseActivationAuthority | None,
    ) -> None:
        if getattr(resolved, "release_id", None) != release_id:
            raise ScienceOperationalError("staged Release identity changed")
        if getattr(resolved, "status", None) != (
            "active" if operation == "activate" else "withdrawn"
        ):
            raise ScienceOperationalError("staged Release lifecycle is invalid")
        if getattr(resolved, "frozen_release_content_hash", None) != frozen_digest:
            raise ScienceOperationalError("staged Release lost its frozen candidate digest")
        if self._decision_digest(resolved) != decision_digest:
            raise ScienceOperationalError("staged Release decision material drifted")
        if operation == "activate":
            self._assert_current_operational_release(catalog, release_id)
            checked = self._activation_authority(
                catalog=catalog,
                release_id=release_id,
                release_digest=release_digest,
                decision_digest=decision_digest,
            )
            if authority is None or checked.authority_digest != authority.authority_digest:
                raise ScienceOperationalError(
                    "activation authority changed during staged validation"
                )

    def _publish_with_rollback(
        self,
        *,
        release_path: Path,
        original: bytes,
        staged_bytes: bytes,
        release_id: str,
        operation: Literal["activate", "withdraw"],
        release_digest: str,
        frozen_digest: str,
        decision_digest: str,
        authority: ReleaseActivationAuthority | None,
    ) -> None:
        self._atomic_replace(release_path, staged_bytes)
        try:
            published_catalog = self._build_catalog(self.boi_root)
            published = self._resolve_release(published_catalog, release_id)
            self._assert_staged_identity(
                catalog=published_catalog,
                resolved=published,
                operation=operation,
                release_id=release_id,
                release_digest=release_digest,
                frozen_digest=frozen_digest,
                decision_digest=decision_digest,
                authority=authority,
            )
            self._reload_callback(published_catalog)
        except Exception as publish_error:
            try:
                self._atomic_replace(release_path, original)
                restored_catalog = self._build_catalog(self.boi_root)
                self._reload_callback(restored_catalog)
            except Exception as rollback_error:
                raise ScienceOperationalError(
                    "Science Release publish failed and rollback could not be verified"
                ) from rollback_error
            raise ScienceOperationalError(
                "Science Release publish failed closed and was rolled back"
            ) from publish_error

    @staticmethod
    def _atomic_replace(path: Path, content: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, path.stat().st_mode)
            os.replace(temporary_path, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _idempotent_result(
        self,
        *,
        operation: Literal["activate", "withdraw"],
        release_id: str,
        release_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor_id: str,
    ) -> ReleaseMutationResult | None:
        matches: list[
            tuple[dict[str, Any], str, Mapping[str, Any], int]
        ] = []
        release_root = self.science_root / "releases"
        if not release_root.is_dir():
            return None
        for path in sorted(release_root.glob("*.md")):
            try:
                metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise ScienceOperationalError("Science Release audit is unreadable") from exc
            activation = metadata.get("activation")
            events = (
                activation.get("authorized_activation_events")
                if isinstance(activation, Mapping)
                else None
            )
            if not isinstance(events, list):
                continue
            for event_index, event in enumerate(events):
                if (
                    isinstance(event, Mapping)
                    and event.get("idempotency_key_digest") == idempotency_digest
                ):
                    matches.append((metadata, body, event, event_index))
        if not matches:
            return None
        if len(matches) != 1:
            raise ScienceOperationalError("Release idempotency key is ambiguous")
        metadata, body, event, event_index = matches[0]
        actor = event.get("actor")
        exact = (
            event.get("operation") == operation
            and event.get("release_id") == release_id
            and event.get("release_digest") == release_digest
            and event.get("request_digest") == request_digest
            and isinstance(actor, Mapping)
            and actor.get("type") == "human"
            and actor.get("user_id") == actor_id
        )
        if not exact:
            raise ScienceOperationalError(
                "Release idempotency key is already bound to another operation"
            )
        science = metadata.get("science")
        if not isinstance(science, Mapping):
            raise ScienceOperationalError("stored idempotent Release result is invalid")
        resulting = self._historical_resulting_digest(
            metadata, body=body, event_index=event_index
        )
        decision = event.get("decision_material_digest")
        occurred_at = event.get("occurred_at")
        if (
            not isinstance(resulting, str)
            or not _SHA256_RE.fullmatch(resulting)
            or not isinstance(decision, str)
            or not _SHA256_RE.fullmatch(decision)
            or not isinstance(occurred_at, str)
        ):
            raise ScienceOperationalError("stored idempotent Release result is invalid")
        authority_digest = event.get("authority_digest")
        if authority_digest is not None and (
            not isinstance(authority_digest, str)
            or not _SHA256_RE.fullmatch(authority_digest)
        ):
            raise ScienceOperationalError("stored idempotent Release authority is invalid")
        return ReleaseMutationResult(
            operation=operation,
            release_id=release_id,
            status="active" if operation == "activate" else "withdrawn",
            input_release_digest=release_digest,
            resulting_release_digest=resulting,
            decision_material_digest=decision,
            request_digest=request_digest,
            idempotency_key_digest=idempotency_digest,
            authority_digest=authority_digest,
            actor_id=actor_id,
            occurred_at=occurred_at,
            idempotent=True,
        )

    @staticmethod
    def _historical_resulting_digest(
        metadata: Mapping[str, Any], *, body: str, event_index: int
    ) -> str:
        """Rebuild the exact lifecycle snapshot produced by a prior event."""

        historical = deepcopy(dict(metadata))
        activation = historical.get("activation")
        science = historical.get("science")
        if not isinstance(activation, dict) or not isinstance(science, dict):
            raise ScienceOperationalError("stored Release lifecycle history is invalid")
        events = activation.get("authorized_activation_events")
        if not isinstance(events, list) or not 0 <= event_index < len(events):
            raise ScienceOperationalError("stored Release lifecycle history is invalid")
        historical_events = deepcopy(events[: event_index + 1])
        event = historical_events[-1]
        if not isinstance(event, Mapping):
            raise ScienceOperationalError("stored Release lifecycle history is invalid")
        operation = event.get("operation")
        if operation not in {"activate", "withdraw"}:
            raise ScienceOperationalError("stored Release lifecycle history is invalid")
        activation["authorized_activation_events"] = historical_events
        activation["activation_status"] = (
            "active" if operation == "activate" else "withdrawn"
        )
        science["status"] = "active" if operation == "activate" else "withdrawn"
        science["active"] = operation == "activate"
        return _release_manifest_digest(historical, body)
