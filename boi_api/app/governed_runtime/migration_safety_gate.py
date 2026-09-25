"""Fail-closed deterministic gate for ontology migration candidates."""

from __future__ import annotations

from dataclasses import dataclass


_CHECK_STATUSES = frozenset({"pass", "fail", "flag", "partial", "skip", "not_run"})
_LINEAGE_CLASSES = frozenset({"direct", "computed", "multi_source", "unresolved"})


@dataclass(frozen=True)
class CheckOutcome:
    check_id: str
    status: str
    required: bool

    def __post_init__(self) -> None:
        if self.status not in _CHECK_STATUSES:
            raise ValueError(f"INVALID_CHECK_STATUS:{self.status}")


@dataclass(frozen=True)
class MigrationSafetyInputs:
    checks: tuple[CheckOutcome, ...]
    lineage_classifications: tuple[str, ...]
    execution_origin: str
    explicit_remap_approval: bool
    remap_performed: bool
    unresolved_link_count: int
    raw_rows_in_model_context: bool
    atomic_persistence: bool
    schema_drift: bool
    confidence: float | None = None


@dataclass(frozen=True)
class MigrationSafetyVerdict:
    approval_ready: bool
    blockers: tuple[str, ...]
    confidence_used_for_verdict: bool = False


def evaluate_migration_safety(inputs: MigrationSafetyInputs) -> MigrationSafetyVerdict:
    blockers: list[str] = []
    for check in inputs.checks:
        if check.required and check.status != "pass":
            blockers.append(f"REQUIRED_CHECK_{check.status.upper()}:{check.check_id}")
        elif check.status in {"fail", "flag", "partial"}:
            blockers.append(f"CHECK_{check.status.upper()}:{check.check_id}")

    unknown_lineage = sorted(set(inputs.lineage_classifications) - _LINEAGE_CLASSES)
    if unknown_lineage:
        blockers.append("INVALID_LINEAGE_CLASSIFICATION:" + ",".join(unknown_lineage))
    if "unresolved" in inputs.lineage_classifications:
        blockers.append("UNRESOLVED_LINEAGE")

    if inputs.execution_origin != "deterministic_compiler":
        blockers.append("UNTRUSTED_SQL_EXECUTION_ORIGIN")
    if inputs.remap_performed and not inputs.explicit_remap_approval:
        blockers.append("SILENT_REMAP_FORBIDDEN")
    if inputs.unresolved_link_count > 0:
        blockers.append("UNRESOLVED_LINKS_PRESENT")
    if inputs.raw_rows_in_model_context:
        blockers.append("RAW_ROWS_IN_MODEL_CONTEXT")
    if not inputs.atomic_persistence:
        blockers.append("ATOMIC_PERSISTENCE_REQUIRED")
    if inputs.schema_drift:
        blockers.append("SCHEMA_DRIFT")

    return MigrationSafetyVerdict(
        approval_ready=not blockers,
        blockers=tuple(blockers),
        confidence_used_for_verdict=False,
    )
