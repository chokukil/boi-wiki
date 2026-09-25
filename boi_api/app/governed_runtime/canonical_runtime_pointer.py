"""Atomic consumer binding for storage-version and active-Release pointers."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SURFACES = frozenset({"search", "graph", "mcp", "download"})
_RUNTIME_SURFACES = ("search", "graph", "mcp", "download", "wiki")


class CanonicalRuntimePointerError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


class CanonicalRuntimePointerStore:
    """Publish one immutable pointer pair through one atomic mutable pointer."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.generations_root = self.root / "generations"
        self.current_path = self.root / "current.json"
        self.lock_path = self.root / ".runtime-pointer.lock"
        self.rollback_root = self.root / "rollback-receipts"

    @staticmethod
    def pointer_digest(pointer: Mapping[str, Any]) -> str:
        return _digest({key: value for key, value in pointer.items() if key != "pointer_digest"})

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @classmethod
    def _validate_storage_pointer(cls, pointer: Mapping[str, Any]) -> None:
        surfaces = pointer.get("surfaces")
        version = pointer.get("version")
        revision = pointer.get("revision")
        if (
            pointer.get("schema") != "boi-okf-canonical-pointer/v1"
            or version != "0.2"
            or not isinstance(revision, str)
            or not _DIGEST.fullmatch(revision)
            or pointer.get("pointer_digest") != cls.pointer_digest(pointer)
            or not isinstance(surfaces, Mapping)
            or set(surfaces) != _SURFACES
            or any(
                not isinstance(value, Mapping)
                or value.get("version") != version
                or value.get("revision") != revision
                for value in surfaces.values()
            )
        ):
            raise CanonicalRuntimePointerError("STORAGE_VERSION_POINTER_INVALID")

    @classmethod
    def _validate_active_release_pointer(cls, pointer: Mapping[str, Any]) -> None:
        release_id = str(pointer.get("release_id") or "")
        release_digest = str(pointer.get("release_manifest_digest") or "")
        if (
            pointer.get("schema") != "boi-active-release-pointer/v1"
            or pointer.get("status") != "ACTIVE"
            or not release_id.startswith("ReleaseManifest:sha256:")
            or release_digest != "sha256:" + release_id.rsplit(":", 1)[-1]
            or not _DIGEST.fullmatch(str(pointer.get("activation_digest") or ""))
            or pointer.get("pointer_digest") != cls.pointer_digest(pointer)
        ):
            raise CanonicalRuntimePointerError("ACTIVE_RELEASE_POINTER_INVALID")

    def _generation_path(self, generation_digest: str) -> Path:
        if not _DIGEST.fullmatch(generation_digest):
            raise CanonicalRuntimePointerError("GENERATION_DIGEST_INVALID")
        return self.generations_root / generation_digest.removeprefix("sha256:") / "pointer.json"

    def _read_generation(self, generation_digest: str) -> dict[str, Any]:
        path = self._generation_path(generation_digest)
        try:
            generation = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalRuntimePointerError("GENERATION_ABSENT_OR_INVALID") from exc
        if not isinstance(generation, dict):
            raise CanonicalRuntimePointerError("GENERATION_ABSENT_OR_INVALID")
        unsigned = {key: value for key, value in generation.items() if key != "generation_digest"}
        normalized = {
            **unsigned,
            "surfaces": {surface: "SELF" for surface in _RUNTIME_SURFACES},
        }
        if generation.get("generation_digest") != _digest(normalized):
            raise CanonicalRuntimePointerError("GENERATION_DIGEST_MISMATCH")
        self._validate_storage_pointer(generation.get("storage_pointer") or {})
        self._validate_active_release_pointer(generation.get("active_release_pointer") or {})
        if generation.get("surfaces") != {
            surface: generation_digest for surface in _RUNTIME_SURFACES
        }:
            raise CanonicalRuntimePointerError("GENERATION_SURFACE_BINDING_INVALID")
        return generation

    def _current_digest(self) -> str | None:
        if not self.current_path.exists():
            return None
        try:
            current = json.loads(self.current_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalRuntimePointerError("CURRENT_POINTER_INVALID") from exc
        if not isinstance(current, dict) or set(current) != {
            "schema", "generation_digest", "pointer_digest"
        }:
            raise CanonicalRuntimePointerError("CURRENT_POINTER_INVALID")
        if (
            current.get("schema") != "boi-canonical-runtime-current/v1"
            or current.get("pointer_digest") != self.pointer_digest(current)
            or not _DIGEST.fullmatch(str(current.get("generation_digest") or ""))
        ):
            raise CanonicalRuntimePointerError("CURRENT_POINTER_INVALID")
        return str(current["generation_digest"])

    def load_current(self) -> dict[str, Any] | None:
        digest = self._current_digest()
        return self._read_generation(digest) if digest else None

    def _write_current(self, generation_digest: str) -> None:
        current: dict[str, Any] = {
            "schema": "boi-canonical-runtime-current/v1",
            "generation_digest": generation_digest,
        }
        current["pointer_digest"] = self.pointer_digest(current)
        temporary = self.root / ".current.json.tmp"
        with temporary.open("wb") as handle:
            handle.write(_canonical_json(current) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.current_path)

    def cutover(
        self,
        *,
        storage_pointer: Mapping[str, Any],
        active_release_pointer: Mapping[str, Any],
        expected_current_digest: str | None,
        authority: str,
        occurred_at: str,
    ) -> dict[str, Any]:
        if authority != "user":
            raise CanonicalRuntimePointerError("USER_AUTHORITY_REQUIRED")
        self._validate_storage_pointer(storage_pointer)
        self._validate_active_release_pointer(active_release_pointer)
        base: dict[str, Any] = {
            "schema": "boi-canonical-runtime-generation/v1",
            "authority": authority,
            "occurred_at": occurred_at,
            "storage_pointer": dict(storage_pointer),
            "active_release_pointer": dict(active_release_pointer),
        }
        # Normalize the self-reference while calculating the content address.
        generation_digest = _digest(
            {**base, "surfaces": {surface: "SELF" for surface in _RUNTIME_SURFACES}}
        )
        generation = {**base, "surfaces": {
            surface: generation_digest for surface in _RUNTIME_SURFACES
        }}
        generation["generation_digest"] = generation_digest
        with self._locked():
            if self._current_digest() != expected_current_digest:
                raise CanonicalRuntimePointerError("CURRENT_POINTER_CAS_MISMATCH")
            path = self._generation_path(generation_digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = _canonical_json(generation) + b"\n"
            if path.exists() and path.read_bytes() != payload:
                raise CanonicalRuntimePointerError("IMMUTABLE_GENERATION_CONFLICT")
            if not path.exists():
                path.write_bytes(payload)
            self._write_current(generation_digest)
        return self._read_generation(generation_digest)

    def rollback(
        self,
        *,
        target_generation_digest: str,
        expected_current_digest: str,
        authority: str,
        occurred_at: str,
        reason: str,
    ) -> dict[str, Any]:
        if authority != "user":
            raise CanonicalRuntimePointerError("USER_AUTHORITY_REQUIRED")
        if not reason.strip():
            raise CanonicalRuntimePointerError("ROLLBACK_REASON_REQUIRED")
        self._read_generation(target_generation_digest)
        with self._locked():
            current = self._current_digest()
            if current != expected_current_digest:
                raise CanonicalRuntimePointerError("CURRENT_POINTER_CAS_MISMATCH")
            base = {
                "schema": "boi-canonical-runtime-rollback/v1",
                "from_generation_digest": current,
                "to_generation_digest": target_generation_digest,
                "authority": authority,
                "occurred_at": occurred_at,
                "reason": reason,
            }
            receipt = {**base, "receipt_digest": _digest(base)}
            self.rollback_root.mkdir(parents=True, exist_ok=True)
            receipt_path = self.rollback_root / (
                receipt["receipt_digest"].removeprefix("sha256:") + ".json"
            )
            payload = _canonical_json(receipt) + b"\n"
            if receipt_path.exists() and receipt_path.read_bytes() != payload:
                raise CanonicalRuntimePointerError("ROLLBACK_RECEIPT_CONFLICT")
            if not receipt_path.exists():
                receipt_path.write_bytes(payload)
            self._write_current(target_generation_digest)
        return receipt


__all__ = ["CanonicalRuntimePointerError", "CanonicalRuntimePointerStore"]
