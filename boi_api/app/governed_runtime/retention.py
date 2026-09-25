"""Fail-closed retention policy for frozen legacy knowledge assets."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Literal


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_digest(value: str, field: str) -> None:
    if not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a canonical sha256 digest")


@dataclass(frozen=True)
class AssetRetentionRecord:
    """A baseline asset that remains preserved unless separately reviewed."""

    asset_digest: str
    baseline_manifest_digest: str
    minimum_qualified_successors: int = 2

    def __post_init__(self) -> None:
        _require_digest(self.asset_digest, "asset_digest")
        _require_digest(self.baseline_manifest_digest, "baseline_manifest_digest")
        if self.minimum_qualified_successors < 2:
            raise ValueError("minimum_qualified_successors must be at least two")


@dataclass(frozen=True)
class QualifiedReleaseReceipt:
    """Digest-bound proof that one distinct successor Release qualified."""

    release_id: str
    qualification_digest: str

    def __post_init__(self) -> None:
        if not self.release_id.strip():
            raise ValueError("release_id must not be empty")
        _require_digest(self.qualification_digest, "qualification_digest")


@dataclass(frozen=True)
class RetentionException:
    """A review request, not deletion authority.

    The exception must bind the exact asset and baseline plus independently
    recoverable approval and recovery manifests.  Even a valid exception only
    makes the asset reviewable; this module exposes no delete operation.
    """

    asset_digest: str
    baseline_manifest_digest: str
    approval_digest: str
    recovery_manifest_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.asset_digest, "asset_digest")
        _require_digest(self.baseline_manifest_digest, "baseline_manifest_digest")
        _require_digest(self.approval_digest, "approval_digest")
        _require_digest(self.recovery_manifest_digest, "recovery_manifest_digest")


@dataclass(frozen=True)
class RetentionDecision:
    decision: Literal["PRESERVE", "REVIEWABLE"]
    reason: str
    qualified_successor_count: int
    requires_explicit_exception: bool
    authorizes_deletion: Literal[False] = False


def evaluate_retention(
    record: AssetRetentionRecord,
    qualified_releases: Iterable[QualifiedReleaseReceipt],
    exception: RetentionException | None = None,
) -> RetentionDecision:
    """Evaluate retention without mutating or deleting an asset."""

    successors = {receipt.release_id for receipt in qualified_releases}
    count = len(successors)

    if exception is None:
        return RetentionDecision(
            decision="PRESERVE",
            reason="explicit_retention_exception_required",
            qualified_successor_count=count,
            requires_explicit_exception=True,
        )

    if (
        exception.asset_digest != record.asset_digest
        or exception.baseline_manifest_digest != record.baseline_manifest_digest
    ):
        raise ValueError("retention exception must bind the exact asset and baseline")

    if count < record.minimum_qualified_successors:
        return RetentionDecision(
            decision="PRESERVE",
            reason="qualified_successor_floor_not_met",
            qualified_successor_count=count,
            requires_explicit_exception=True,
        )

    return RetentionDecision(
        decision="REVIEWABLE",
        reason="exact_exception_and_successor_floor_satisfied",
        qualified_successor_count=count,
        requires_explicit_exception=False,
    )
