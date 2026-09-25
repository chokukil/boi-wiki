"""Generic cold logical-plan construction from frozen candidate profiles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Mapping

from .candidate_semantic_search import CandidateSearchReceipt
from .bulk_migration_execution import CandidateFreezeReceipt
from .cardinality_query_shape import DataQualityReceipt, RelationshipContract
from .metadata_mapping_profile import MetadataMappingProfileCandidate
from .multi_result_query_gateway import (
    MultiResultAggregate,
    MultiResultExistenceConstraint,
    MultiResultExistenceHop,
    MultiResultFilter,
    MultiResultLatest,
    MultiResultLogicalPlan,
    MultiResultParameterSpec,
    MultiResultParentLink,
    MultiResultProjection,
    MultiResultSetPlan,
    create_multi_result_logical_plan,
)


def _canonical(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ColdCandidateLogicalPlan:
    plan: MultiResultLogicalPlan
    parameters: dict[str, object]
    selected_relationship_ids: tuple[str, ...]
    quality_receipts: tuple[DataQualityReceipt, ...]
    authority_scope: str
    candidate_search_receipt_digest: str
    candidate_plan_digest: str
    registered_query_spec_access_count: int = 0
    raw_sql_generation_count: int = 0
    production_qualified: bool = False


def freeze_cold_candidate_plan(
    candidate: ColdCandidateLogicalPlan,
    *,
    profile_digest: str,
    source_manifest_digest: str,
    catalog_snapshot_digest: str,
    generator_code_digest: str,
) -> CandidateFreezeReceipt:
    return CandidateFreezeReceipt.create(
        candidate_digest=profile_digest,
        logical_plan_digest=candidate.plan.plan_digest,
        allowed_input_refs=(
            "artifact:metadata",
            "artifact:catalog",
            "artifact:sql",
            "candidate-search:" + candidate.candidate_search_receipt_digest,
        ),
        denied_oracle_refs=(
            "dexa:profile",
            "registered-query-spec:*",
            "golden-sql:*",
            "golden-count:*",
            "golden-result:*",
            "historical-flat-view:*",
        ),
        closure_digests={
            "source": source_manifest_digest,
            "catalog": catalog_snapshot_digest,
            "profile": profile_digest,
            "candidate_plan": candidate.candidate_plan_digest,
        },
        generator_code_digest=generator_code_digest,
    )


def _object_by_column(profile: MetadataMappingProfileCandidate, column: str) -> dict[str, object]:
    mapping_by_ref = {item.mapping_ref: item for item in profile.physical_mappings}
    matches = [
        item
        for item in profile.object_mappings
        if any(
            mapping_by_ref[ref].column == column
            for ref in item["property_mapping_refs"]
        )
    ]
    if len(matches) != 1:
        raise ValueError(f"QUERY_OBJECT_BY_COLUMN_AMBIGUOUS:{column}")
    return matches[0]


def _mapping(profile: MetadataMappingProfileCandidate, table: str, column: str):
    matches = [
        item
        for item in profile.physical_mappings
        if item.table == table and item.column == column
    ]
    if len(matches) != 1:
        raise ValueError(f"QUERY_MAPPING_UNRESOLVED:{table}.{column}")
    return matches[0]


def _relationship(
    relationships: Iterable[RelationshipContract], first: str, second: str
) -> RelationshipContract:
    matches = [
        item
        for item in relationships
        if {item.left_endpoint_ref, item.right_endpoint_ref} == {first, second}
    ]
    if len(matches) != 1:
        raise ValueError(f"QUERY_RELATIONSHIP_UNRESOLVED:{first}:{second}")
    return matches[0]


def _hop(
    profile: MetadataMappingProfileCandidate,
    relationship: RelationshipContract,
    *,
    from_object: Mapping[str, object],
    to_object: Mapping[str, object],
) -> MultiResultExistenceHop:
    from_ref = str(from_object["object_ref"])
    to_ref = str(to_object["object_ref"])
    if (
        relationship.left_endpoint_ref == from_ref
        and relationship.right_endpoint_ref == to_ref
    ):
        from_mapping_ref = relationship.physical_keys.left_mapping_refs[0]
        to_mapping_ref = relationship.physical_keys.right_mapping_refs[0]
    elif (
        relationship.right_endpoint_ref == from_ref
        and relationship.left_endpoint_ref == to_ref
    ):
        from_mapping_ref = relationship.physical_keys.right_mapping_refs[0]
        to_mapping_ref = relationship.physical_keys.left_mapping_refs[0]
    else:
        raise ValueError("QUERY_HOP_ENDPOINT_MISMATCH")
    by_ref = {item.mapping_ref: item for item in profile.physical_mappings}
    from_mapping = by_ref[from_mapping_ref]
    to_mapping = by_ref[to_mapping_ref]
    return MultiResultExistenceHop(
        parent_object_ref=from_ref,
        child_object_ref=to_ref,
        parent_source_id=from_mapping.source_id,
        parent_table=from_mapping.table,
        source_id=to_mapping.source_id,
        table=to_mapping.table,
        parent_mapping_ref=from_mapping.mapping_ref,
        parent_column=from_mapping.column,
        child_mapping_ref=to_mapping.mapping_ref,
        child_column=to_mapping.column,
        relationship_contract_id=relationship.contract_id,
    )


def _projection(profile, table: str, column: str, output: str | None = None):
    mapping = _mapping(profile, table, column)
    return MultiResultProjection(
        mapping_ref=mapping.mapping_ref,
        column=column,
        output_name=output or column,
    )


def _quality_for(
    profile: MetadataMappingProfileCandidate,
    relationships: Iterable[RelationshipContract],
) -> tuple[DataQualityReceipt, ...]:
    wanted = {item.contract_digest for item in relationships}
    return tuple(
        item
        for item in profile.data_quality_receipts
        if item.relationship_contract_digest in wanted
    )


def build_cold_candidate_logical_plan(
    *,
    question: str,
    search_receipt: CandidateSearchReceipt,
    profile: MetadataMappingProfileCandidate,
    candidate_freeze_digest: str,
    domain_profile_digest: str,
    query_profile_digest: str,
    include_history_aggregate: bool = True,
) -> ColdCandidateLogicalPlan:
    from boi_api.app.governed_runtime.semantic_selection_guard import reject_unstructured_selection
    reject_unstructured_selection()
