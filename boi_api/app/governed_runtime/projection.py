"""Active-Release filter for governed Search, Graph, MCP, and download views."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Literal


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ActiveReleasePointer:
    release_id: str
    release_manifest_digest: str
    activation_digest: str


@dataclass(frozen=True)
class ProjectionDecision:
    visible: bool
    reason: str


def active_release_pointer_path(runtime_root: Path) -> Path:
    return runtime_root / "governed-runtime" / "active-release.json"


def load_active_release_pointer(runtime_root: Path) -> ActiveReleasePointer | None:
    """Read a strict pointer; malformed or non-active data is equivalent to absent."""

    path = active_release_pointer_path(runtime_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "ACTIVE":
        return None
    release_id = str(payload.get("release_id") or "")
    manifest_digest = str(payload.get("release_manifest_digest") or "")
    activation_digest = str(payload.get("activation_digest") or "")
    if not release_id or not _DIGEST.fullmatch(manifest_digest) or not _DIGEST.fullmatch(activation_digest):
        return None
    return ActiveReleasePointer(release_id, manifest_digest, activation_digest)


def _governance(record: dict[str, Any]) -> dict[str, Any]:
    nested = record.get("governance")
    if isinstance(nested, dict) and nested:
        return nested
    keys = ("knowledge_revision_id", "release_id", "release_manifest_digest")
    return {key: record.get(key) for key in keys if record.get(key) is not None}


def evaluate_release_projection(
    record: dict[str, Any],
    pointer: ActiveReleasePointer | None,
    *,
    lane: Literal["canonical", "intake", "legacy_history"] = "canonical",
) -> ProjectionDecision:
    """Apply an explicit projection lane without weakening canonical visibility.

    ``canonical`` is the only lane consumed by Search, Graph, MCP, and the
    standard artifact download routes. ``intake`` exists only for candidate
    management before Release qualification. ``legacy_history`` is an
    explicitly gated compatibility lane for preserved, unbound artifacts.
    """

    governance = _governance(record)
    if not governance:
        if lane == "intake":
            return ProjectionDecision(True, "intake_unbound_candidate")
        if lane == "legacy_history":
            return ProjectionDecision(True, "legacy_history_lane")
        return ProjectionDecision(False, "legacy_unbound_canonical_excluded")
    revision_id = str(governance.get("knowledge_revision_id") or "")
    release_id = str(governance.get("release_id") or "")
    manifest_digest = str(governance.get("release_manifest_digest") or "")
    if not revision_id or not release_id or not _DIGEST.fullmatch(manifest_digest):
        return ProjectionDecision(False, "malformed_release_binding")
    if lane == "legacy_history":
        return ProjectionDecision(False, "governed_record_not_legacy")
    if lane == "intake":
        return ProjectionDecision(True, "intake_governed_candidate")
    if pointer is None:
        return ProjectionDecision(False, "active_release_pointer_missing")
    if release_id != pointer.release_id or manifest_digest != pointer.release_manifest_digest:
        return ProjectionDecision(False, "release_binding_mismatch")
    return ProjectionDecision(True, "active_release_match")
