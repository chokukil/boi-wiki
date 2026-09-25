"""Strict inactive candidate packages for profile-driven multi-result queries."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
import yaml

from .cardinality_query_shape import RelationshipContract, ResultShapeContract
from .multi_result_query_gateway import (
    AuthorizedPhysicalMapping,
    MultiResultSetPlan,
)


def _sha256(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(item in "0123456789abcdef" for item in value[7:])
    )


class MultiResultHistoricalOracle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_ref: str
    status: Literal["historical_only"]
    row_count: int
    nonnull_child_count: int
    independent_identity_present: bool
    promotion_eligible: Literal[False]


class MultiResultCandidatePackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-multi-result-profile-candidate/v1"]
    package_id: str
    status: Literal["candidate"]
    qualification_status: Literal["not_run"]
    release_id: None
    active_pointer_transition: Literal[False]
    canonical_projection_eligible: Literal[False]
    source_id: str
    source_snapshot_digest: str
    schema_digest: str
    allowed_tables: tuple[str, ...]
    relationship_contracts: tuple[RelationshipContract, ...]
    result_shape_contract: ResultShapeContract
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    result_sets: tuple[MultiResultSetPlan, ...]
    quality_measurement: Literal["runtime_deterministic"]
    historical_oracle: MultiResultHistoricalOracle

    @field_validator("source_snapshot_digest", "schema_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("CANDIDATE_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def validate_candidate(self) -> "MultiResultCandidatePackage":
        if not self.package_id.strip() or not self.source_id.strip():
            raise ValueError("CANDIDATE_IDENTITY_REQUIRED")
        if not self.allowed_tables or len(self.allowed_tables) != len(set(self.allowed_tables)):
            raise ValueError("CANDIDATE_ALLOWED_TABLES_INVALID")
        relationship_ids = tuple(
            item.contract_id for item in self.relationship_contracts
        )
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("CANDIDATE_RELATIONSHIP_DUPLICATE")
        if set(self.result_shape_contract.relationship_refs) != set(relationship_ids):
            raise ValueError("CANDIDATE_RESULT_SHAPE_RELATIONSHIP_MISMATCH")
        if any(
            item.schema_snapshot_digest != self.schema_digest
            for item in self.relationship_contracts
        ):
            raise ValueError("CANDIDATE_RELATIONSHIP_SCHEMA_MISMATCH")
        if not self.result_sets or self.result_sets[0].role != "ROOT":
            raise ValueError("CANDIDATE_ROOT_RESULT_REQUIRED")
        if self.result_sets[0].object_ref != self.result_shape_contract.root_object_ref:
            raise ValueError("CANDIDATE_ROOT_OBJECT_MISMATCH")
        mappings = {item.mapping_ref: item for item in self.physical_mappings}
        if len(mappings) != len(self.physical_mappings):
            raise ValueError("CANDIDATE_MAPPING_DUPLICATE")
        if any(item.source_id != self.source_id for item in self.physical_mappings):
            raise ValueError("CANDIDATE_MAPPING_SOURCE_MISMATCH")
        for relationship in self.relationship_contracts:
            for mapping_ref in (
                *relationship.physical_keys.left_mapping_refs,
                *relationship.physical_keys.right_mapping_refs,
            ):
                if mapping_ref not in mappings:
                    raise ValueError("CANDIDATE_RELATIONSHIP_MAPPING_MISSING")
        for result_set in self.result_sets:
            if result_set.source_id != self.source_id:
                raise ValueError("CANDIDATE_RESULT_SOURCE_MISMATCH")
            if result_set.table not in self.allowed_tables:
                raise ValueError("CANDIDATE_RESULT_TABLE_NOT_ALLOWED")
            for projection in (*result_set.projections, *result_set.aggregations):
                mapping = mappings.get(projection.mapping_ref)
                if (
                    mapping is None
                    or mapping.table != result_set.table
                    or mapping.column != projection.column
                ):
                    raise ValueError("CANDIDATE_RESULT_MAPPING_MISMATCH")
            if (
                result_set.parent_link is not None
                and result_set.parent_link.relationship_contract_id
                not in relationship_ids
            ):
                raise ValueError("CANDIDATE_PARENT_RELATIONSHIP_MISMATCH")
        return self


def load_multi_result_candidate_package(path: Path) -> MultiResultCandidatePackage:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MULTI_RESULT_CANDIDATE_DOCUMENT_INVALID")
    return MultiResultCandidatePackage.model_validate(raw)


__all__ = [
    "MultiResultCandidatePackage",
    "MultiResultHistoricalOracle",
    "load_multi_result_candidate_package",
]
