"""Deterministic exception-only routing for ontology migration candidates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttentionSignals:
    existing_concept_match_count: int
    unresolved_lineage_count: int
    unresolved_mapping_count: int
    missing_key_count: int
    duplicate_key_count: int
    fanout_detected: bool
    cardinality_mismatch: bool
    type_conflict: bool
    unit_conflict: bool
    value_type_conflict: bool
    unsupported_dialect: bool
    cross_database: bool
    breaking_change: bool
    schema_drift: bool
    source_hash_drift: bool
    golden_failed: bool
    release_requested: bool
    rollback_requested: bool
    hard_blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationRoutingDecision:
    route: str
    target_state: str
    attention_reasons: tuple[str, ...]
    blockers: tuple[str, ...]


def route_migration_candidate(signals: AttentionSignals) -> MigrationRoutingDecision:
    counts = {
        "existing_concept_match_count": signals.existing_concept_match_count,
        "unresolved_lineage_count": signals.unresolved_lineage_count,
        "unresolved_mapping_count": signals.unresolved_mapping_count,
        "missing_key_count": signals.missing_key_count,
        "duplicate_key_count": signals.duplicate_key_count,
    }
    negative = sorted(name for name, value in counts.items() if value < 0)
    if negative:
        raise ValueError("NEGATIVE_SIGNAL_COUNT:" + ",".join(negative))

    reasons: list[str] = []
    if signals.existing_concept_match_count > 1:
        reasons.append("MULTIPLE_EXISTING_CONCEPT_MATCHES")
    if signals.unresolved_lineage_count:
        reasons.append("UNRESOLVED_LINEAGE")
    if signals.unresolved_mapping_count:
        reasons.append("UNRESOLVED_MAPPING")
    if signals.missing_key_count:
        reasons.append("MISSING_KEY")
    if signals.duplicate_key_count:
        reasons.append("DUPLICATE_KEY")

    boolean_reasons = (
        (signals.fanout_detected, "FANOUT_DETECTED"),
        (signals.cardinality_mismatch, "CARDINALITY_MISMATCH"),
        (signals.type_conflict, "TYPE_CONFLICT"),
        (signals.unit_conflict, "UNIT_CONFLICT"),
        (signals.value_type_conflict, "VALUE_TYPE_CONFLICT"),
        (signals.unsupported_dialect, "UNSUPPORTED_DIALECT"),
        (signals.cross_database, "CROSS_DATABASE"),
        (signals.breaking_change, "ACTIVE_ASSET_BREAKING_CHANGE"),
        (signals.schema_drift, "SCHEMA_DRIFT"),
        (signals.source_hash_drift, "SOURCE_HASH_DRIFT"),
        (signals.golden_failed, "GOLDEN_FAILED"),
        (signals.release_requested, "RELEASE_REQUESTED"),
        (signals.rollback_requested, "ROLLBACK_REQUESTED"),
    )
    reasons.extend(reason for present, reason in boolean_reasons if present)
    attention_reasons = tuple(dict.fromkeys(reasons))
    blockers = tuple(dict.fromkeys(item for item in signals.hard_blockers if item))

    if blockers:
        return MigrationRoutingDecision(
            route="blocked",
            target_state="blocked",
            attention_reasons=attention_reasons,
            blockers=blockers,
        )
    if attention_reasons:
        return MigrationRoutingDecision(
            route="attention",
            target_state="attention_required",
            attention_reasons=attention_reasons,
            blockers=(),
        )
    return MigrationRoutingDecision(
        route="auto_progress",
        target_state="approval_ready",
        attention_reasons=(),
        blockers=(),
    )
