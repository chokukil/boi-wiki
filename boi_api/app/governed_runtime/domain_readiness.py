"""Deterministic D0-D5 domain readiness calculation.

The caller supplies observed contract counts and digests.  It cannot supply a
readiness grade; the highest contiguous satisfied stage is derived here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainReadinessInputs:
    vocabulary_terms: int = 0
    aliases: int = 0
    definitions: int = 0
    object_types: int = 0
    property_definitions: int = 0
    value_types: int = 0
    relations: int = 0
    rules: int = 0
    metrics: int = 0
    applicability_scopes: int = 0
    physical_mappings: int = 0
    physical_mapping_checks_passed: int = 0
    schema_snapshot_digest: str | None = None
    logical_query_specs: int = 0
    safe_executions: int = 0
    execution_receipts: int = 0
    deterministic_attestations: int = 0


@dataclass(frozen=True)
class DomainReadinessReport:
    level: str
    achieved: tuple[str, ...]
    blockers: tuple[str, ...]
    release_ready: bool


def _nonnegative(inputs: DomainReadinessInputs) -> None:
    for field_name, value in inputs.__dict__.items():
        if isinstance(value, int) and value < 0:
            raise ValueError(f"NEGATIVE_READINESS_COUNT:{field_name}")


def compute_domain_readiness(inputs: DomainReadinessInputs) -> DomainReadinessReport:
    _nonnegative(inputs)

    stages = (
        (
            "D0",
            inputs.vocabulary_terms > 0
            and inputs.aliases > 0
            and inputs.definitions >= inputs.vocabulary_terms,
            "D0_VOCABULARY_INCOMPLETE",
        ),
        (
            "D1",
            inputs.object_types > 0
            and inputs.property_definitions > 0
            and inputs.value_types > 0,
            "D1_SEMANTIC_CONTRACT_INCOMPLETE",
        ),
        (
            "D2",
            inputs.relations > 0
            and inputs.rules > 0
            and inputs.metrics > 0
            and inputs.applicability_scopes
            >= inputs.relations + inputs.rules + inputs.metrics,
            "D2_DOMAIN_LOGIC_INCOMPLETE",
        ),
        (
            "D3",
            inputs.physical_mappings > 0
            and inputs.physical_mapping_checks_passed == inputs.physical_mappings
            and bool(inputs.schema_snapshot_digest),
            "D3_MAPPING_CHECKS_INCOMPLETE",
        ),
        (
            "D4",
            inputs.logical_query_specs > 0
            and inputs.safe_executions >= inputs.logical_query_specs,
            "D4_SAFE_EXECUTION_REQUIRED",
        ),
        (
            "D5",
            inputs.execution_receipts >= inputs.logical_query_specs > 0
            and inputs.deterministic_attestations >= inputs.execution_receipts,
            "D5_ATTESTATION_REQUIRED",
        ),
    )

    achieved: list[str] = []
    blockers: list[str] = []
    contiguous = True
    for stage, satisfied, blocker in stages:
        if contiguous and satisfied:
            achieved.append(stage)
        else:
            contiguous = False
            blockers.append(blocker)

    level = achieved[-1] if achieved else "D0"
    return DomainReadinessReport(
        level=level,
        achieved=tuple(achieved),
        blockers=tuple(blockers),
        release_ready=achieved == [stage for stage, _, _ in stages],
    )
