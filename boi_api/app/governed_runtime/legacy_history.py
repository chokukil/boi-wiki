"""Strict compatibility gate for preserved artifacts outside active Releases."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTRACT = "boi-legacy-history-migration/v1"
_ALLOWED_SURFACES = frozenset(
    {
        "legacy_history_list",
        "legacy_history_get",
        "legacy_history_download",
    }
)
_ALLOWED_STATUSES = {"IN_PROGRESS", "QUALIFIED"}


@dataclass(frozen=True)
class LegacyHistoryReceipt:
    migration_id: str
    source_inventory_digest: str
    status: str
    allowed_surfaces: frozenset[str]
    unresolved_assets: int
    minimum_qualified_successor_releases: int


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def load_legacy_history_receipt(path: Path) -> LegacyHistoryReceipt | None:
    """Load only an exact, closed-schema migration receipt.

    A malformed or expanded receipt disables the compatibility lane. This is
    intentional: adding a surface must be a reviewed contract change.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {
        "contract",
        "migration_id",
        "source_inventory_digest",
        "status",
        "allowed_surfaces",
        "exit_condition",
    }:
        return None
    migration_id = str(payload.get("migration_id") or "").strip()
    digest = str(payload.get("source_inventory_digest") or "")
    status = str(payload.get("status") or "")
    surfaces = payload.get("allowed_surfaces")
    exit_condition = payload.get("exit_condition")
    if (
        payload.get("contract") != _CONTRACT
        or not migration_id
        or not _DIGEST.fullmatch(digest)
        or status not in _ALLOWED_STATUSES
        or not isinstance(surfaces, list)
        or frozenset(str(item) for item in surfaces) != _ALLOWED_SURFACES
        or len(surfaces) != len(_ALLOWED_SURFACES)
        or not isinstance(exit_condition, dict)
        or set(exit_condition) != {"unresolved_assets", "minimum_qualified_successor_releases"}
    ):
        return None
    unresolved = _non_negative_int(exit_condition.get("unresolved_assets"))
    successors = _non_negative_int(exit_condition.get("minimum_qualified_successor_releases"))
    if unresolved is None or successors is None or successors < 2:
        return None
    return LegacyHistoryReceipt(
        migration_id=migration_id,
        source_inventory_digest=digest,
        status=status,
        allowed_surfaces=_ALLOWED_SURFACES,
        unresolved_assets=unresolved,
        minimum_qualified_successor_releases=successors,
    )


def legacy_history_lane_ready(enabled: bool, receipt: LegacyHistoryReceipt | None) -> bool:
    """Require both the explicit feature flag and a strict migration receipt."""

    return bool(enabled and receipt is not None)
