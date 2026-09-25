"""Closed multi-result logical plan and protected Gateway contracts.

The module contains no domain routing and accepts no SQL text.  C3 extends it
from a deterministic logical plan into protected compilation and execution.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .result_canonicalization import normalize_result_rows
from .protected_execution_repository import ProtectedExecutionRepository
from .sqlite_source_snapshot import sealed_sqlite_digest
import time
from typing import Any, Callable, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator, model_serializer
from .semantic_authority import NativeReviewedDefinitionAuthority, NativeProcessReviewAuthority
from .semantic_binding_contract import RevisionRef
from .filter_expression import FilterExpression,validate_filter_expression,compose_filter_sql

from .cardinality_query_shape import DataQualityReceipt, RelationshipContract
from .latest_execution_quality import LatestExecutionPolicy, WithLatestQuality, audit_latest_input
from .latest_time_order import register_latest_time_functions
from .physical_temporal_encoding import PhysicalTemporalEncoding
from .temporal_sql_comparison import temporal_expression, temporal_parameter, policy_for_mapping
from .temporal_sql_comparison import selection_policies_for_mapping
from .temporal_predicate_quality import audit_temporal_predicate, audit_mapping_temporal_input
from .snapshot_result_paging import (
    CompiledPageQuery, SnapshotPagingPolicy, SnapshotPageAccess,
    SnapshotResultPager, WithSnapshotPageAccess,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha256(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(item in "0123456789abcdef" for item in value[7:])
    )


class MultiResultProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_ref: str
    column: str
    output_name: str

    @field_validator("mapping_ref", "column", "output_name")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("PROJECTION_FIELD_INVALID")
        return value


class MultiResultAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reducer: Literal["count_rows", "count", "count_distinct", "sum", "average", "min", "max"]
    mapping_ref: str
    column: str
    output_name: str

    @field_validator("mapping_ref", "column", "output_name")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("AGGREGATE_FIELD_INVALID")
        return value


class MultiResultParentLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_result_set_id: str
    parent_key_outputs: tuple[str, ...]
    child_key_outputs: tuple[str, ...]
    relationship_contract_id: str

    @model_validator(mode="after")
    def validate_keys(self) -> "MultiResultParentLink":
        if not self.parent_key_outputs or not self.child_key_outputs:
            raise ValueError("PARENT_CHILD_KEYS_REQUIRED")
        if len(self.parent_key_outputs) != len(self.child_key_outputs):
            raise ValueError("PARENT_CHILD_KEY_ARITY_MISMATCH")
        return self


class MultiResultParameterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: Literal[
        "string",
        "integer",
        "number",
        "boolean",
        "string_list",
        "integer_list",
        "number_list",
        "boolean_list",
    ]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("PARAMETER_NAME_REQUIRED")
        return value


class MultiResultFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_ref: str
    operator: Literal[
        "eq", "neq", "gt", "gte", "lt", "lte", "in", "is_null", "not_null"
    ]
    parameter_name: str | None

    @model_validator(mode="after")
    def validate_parameter(self) -> "MultiResultFilter":
        if self.operator in {"is_null", "not_null"}:
            if self.parameter_name is not None:
                raise ValueError("NULL_FILTER_PARAMETER_FORBIDDEN")
        elif not self.parameter_name:
            raise ValueError("FILTER_PARAMETER_REQUIRED")
        return self


class MultiResultExistenceHop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_object_ref: str
    child_object_ref: str
    parent_source_id: str
    parent_table: str
    source_id: str
    table: str
    parent_mapping_ref: str
    parent_column: str
    child_mapping_ref: str
    child_column: str
    relationship_contract_id: str


class MultiResultExistenceConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filter_object_ref: str
    hops: tuple[MultiResultExistenceHop, ...] = Field(min_length=1)
    filters: tuple[MultiResultFilter, ...] = Field(min_length=1)
    polarity: Literal["PRESENT", "ABSENT"] = "PRESENT"

    @model_serializer(mode="wrap")
    def preserve_positive_existence_shape(self, handler):
        value=handler(self)
        if self.polarity == "PRESENT":value.pop("polarity",None)
        return value


class MultiResultLatest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partition_by: tuple[str, ...] = Field(min_length=1)
    ordering: tuple[str, ...] = Field(min_length=2)
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = Field(min_length=2)
    selection_policy: LatestExecutionPolicy | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_latest(self, handler):
        value = handler(self)
        if self.selection_policy is None:
            value.pop("selection_policy", None)
        return value

    @model_validator(mode="after")
    def validate_ordering(self) -> "MultiResultLatest":
        if len(self.ordering) != len(self.ordering_directions):
            raise ValueError("LATEST_ORDER_DIRECTION_ARITY_MISMATCH")
        if self.selection_policy and (self.selection_policy.version_identity_output not in self.ordering[1:] or self.ordering_directions[0] != "DESC"):
            raise ValueError("LATEST_POLICY_ORDER_INVALID")
        return self


class MultiResultSetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    role: Literal["ROOT", "CHILD", "RELATIONSHIP", "AGGREGATE", "SCALAR"]
    object_ref: str
    source_id: str
    table: str
    projections: tuple[MultiResultProjection, ...]
    aggregations: tuple[MultiResultAggregate, ...] = ()
    exact_grain: tuple[str, ...]
    filters: tuple[MultiResultFilter, ...]
    filter_expression: FilterExpression | None = Field(default=None,exclude_if=lambda v:v is None)
    existence_constraints: tuple[MultiResultExistenceConstraint, ...] = ()
    parent_link: MultiResultParentLink | None
    latest: MultiResultLatest | None = None
    ordering: tuple[str, ...]
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED", "QUALITY_SIDECAR_REQUIRED", "PROVISIONAL_SNAPSHOT"
    ]
    coverage_semantics: Literal[
        "SPARSE_ONLY", "ROOT_COMPLETE_ZERO_FILL", "UNKNOWN_NOT_ZERO"
    ] = "SPARSE_ONLY"
    zero_fill_aggregate_outputs: tuple[str, ...] = ()
    result_row_limit: int = Field(gt=0, le=100_000)
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = ()
    row_limit_policy: Literal["FAIL_IF_EXCEEDED", "TRUNCATE", "SNAPSHOT_PAGED"] = "FAIL_IF_EXCEEDED"
    paging_policy: SnapshotPagingPolicy | None = None

    @model_serializer(mode="wrap")
    def omit_absent_paging_policy(self, handler):
        result = handler(self)
        if self.paging_policy is None:
            result.pop("paging_policy", None)
        return result

    @model_validator(mode="after")
    def validate_result_set(self) -> "MultiResultSetPlan":
        if self.filter_expression is not None:
            validate_filter_expression(self.filter_expression,len(self.filters))
            if self.latest is not None:raise ValueError('NESTED_FILTER_LATEST_PLACEMENT_UNRESOLVED')
        if self.role == "SCALAR":
            if self.projections or self.exact_grain or self.ordering or self.ordering_directions:
                raise ValueError("SCALAR_GROUPING_OR_PROJECTION_FORBIDDEN")
            if self.result_row_limit != 1 or self.row_limit_policy != "FAIL_IF_EXCEEDED":
                raise ValueError("SCALAR_SINGLE_OUTPUT_ROW_REQUIRED")
            if self.paging_policy is not None or self.latest is not None or self.existence_constraints:
                raise ValueError("SCALAR_SELECTION_CAPABILITY_UNAVAILABLE")
            if self.coverage_semantics != "SPARSE_ONLY" or self.zero_fill_aggregate_outputs:
                raise ValueError("SCALAR_PARENT_COVERAGE_FORBIDDEN")
        if (self.row_limit_policy == "SNAPSHOT_PAGED") != (self.paging_policy is not None):
            raise ValueError("PAGING_POLICY_REQUIRED_OR_FORBIDDEN")
        if self.paging_policy is not None:
            if self.result_row_limit > 1000 or self.paging_policy.page_size > self.result_row_limit:
                raise ValueError("PAGING_ROW_BUDGET_EXCEEDED")
            if not set(self.exact_grain) <= set(self.ordering):
                raise ValueError("PAGING_TOTAL_ORDER_REQUIRED")
            if self.coverage_semantics == "ROOT_COMPLETE_ZERO_FILL":
                raise ValueError("PAGING_ZERO_FILL_CAPABILITY_UNAVAILABLE")
        if not self.result_set_id.strip() or not self.object_ref.strip():
            raise ValueError("RESULT_SET_IDENTITY_REQUIRED")
        if not self.projections and self.role != "SCALAR":
            raise ValueError("PROJECTIONS_REQUIRED")
        outputs = tuple(item.output_name for item in self.projections) + tuple(
            item.output_name for item in self.aggregations
        )
        projection_mappings = tuple(item.mapping_ref for item in self.projections)
        if len(outputs) != len(set(outputs)) or len(projection_mappings) != len(
            set(projection_mappings)
        ):
            raise ValueError("PROJECTION_DUPLICATE")
        if not self.exact_grain and self.role != "SCALAR":
            raise ValueError("EXACT_GRAIN_REQUIRED")
        if not set(self.exact_grain) <= set(outputs):
            raise ValueError("EXACT_GRAIN_NOT_PROJECTED")
        if not set(self.ordering) <= set(outputs):
            raise ValueError("ORDER_FIELD_NOT_PROJECTED")
        if self.ordering_directions and len(self.ordering_directions) != len(
            self.ordering
        ):
            raise ValueError("ORDER_DIRECTION_ARITY_MISMATCH")
        if self.role in {"AGGREGATE", "SCALAR"} and not self.aggregations:
            raise ValueError("AGGREGATION_REQUIRED")
        if self.role not in {"AGGREGATE", "SCALAR"} and self.aggregations:
            raise ValueError("AGGREGATION_FORBIDDEN")
        if self.role in {"ROOT", "SCALAR"} or self.role == "AGGREGATE" and self.parent_link is None:
            if self.parent_link is not None:
                raise ValueError("ROOT_PARENT_LINK_FORBIDDEN")
            if self.result_row_limit > 1000:
                raise ValueError("ROOT_INLINE_ROW_LIMIT_EXCEEDED")
        elif self.parent_link is None:
            raise ValueError("NON_ROOT_PARENT_LINK_REQUIRED")
        if self.role != "ROOT" and self.existence_constraints:
            raise ValueError("EXISTENCE_CONSTRAINT_ROOT_ONLY")
        aggregate_outputs = {item.output_name for item in self.aggregations}
        if self.coverage_semantics == "ROOT_COMPLETE_ZERO_FILL":
            if self.role != "AGGREGATE" or self.parent_link is None:
                raise ValueError("ZERO_FILL_AGGREGATE_PARENT_REQUIRED")
            if (
                not self.zero_fill_aggregate_outputs
                or not set(self.zero_fill_aggregate_outputs) <= aggregate_outputs
            ):
                raise ValueError("ZERO_FILL_OUTPUTS_INVALID")
            projection_outputs = {item.output_name for item in self.projections}
            if projection_outputs != set(self.parent_link.child_key_outputs):
                raise ValueError("ZERO_FILL_GRAIN_PROJECTION_INVALID")
        elif self.zero_fill_aggregate_outputs:
            raise ValueError("ZERO_FILL_OUTPUTS_FORBIDDEN")
        if self.latest is not None:
            if self.role == "AGGREGATE" or self.aggregations:
                raise ValueError("LATEST_AGGREGATION_CONFLICT")
            if not {*self.latest.partition_by, *self.latest.ordering} <= set(outputs):
                raise ValueError("LATEST_OUTPUT_NOT_PROJECTED")
            if tuple(self.exact_grain) != tuple(self.latest.partition_by):
                raise ValueError("LATEST_GRAIN_MISMATCH")
        return self


class ReviewedQueryAuthority(BaseModel):
    """Explicit exploratory provenance; a digest alone grants no execution access."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal[
        'boi/reviewed-query-authority@1',
        'boi/reviewed-query-authority@2',
    ]
    principal: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    manifest_digest: str
    preview_digest: str
    interpretation_receipt_digest: str
    semantic_context_digest: str
    mapping_input_digest: str
    intent_digest: str
    freeze_receipt_digest: str
    question_digest: str | None = Field(default=None, exclude_if=lambda value: value is None)
    question_interpretation_receipt_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    reviewed_definition_authority_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    semantic_planning_context_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    shape_selection_receipt_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    semantic_plan_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    physical_binding_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    planning_policy_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    qualifier_application_receipt_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def exact_digests(self):
        values = self.model_dump(mode='json')
        if any(not _sha256(value) for key,value in values.items()
               if key.endswith('_digest')):
            raise ValueError('REVIEWED_QUERY_AUTHORITY_DIGEST_INVALID')
        forward = (
            self.question_digest,
            self.question_interpretation_receipt_digest,
            self.reviewed_definition_authority_digest,
            self.semantic_planning_context_digest,
            self.shape_selection_receipt_digest,
            self.semantic_plan_digest,
            self.physical_binding_digest,
            self.planning_policy_digest,
            self.qualifier_application_receipt_digest,
        )
        if (self.contract_version == 'boi/reviewed-query-authority@2') != all(forward):
            raise ValueError('REVIEWED_QUERY_AUTHORITY_REVISION_FIELDS_INVALID')
        if self.contract_version == 'boi/reviewed-query-authority@1' and any(forward):
            raise ValueError('REVIEWED_QUERY_AUTHORITY_REVISION_FIELDS_INVALID')
        return self


class NativeQueryAuthority(BaseModel):
    """Native candidate provenance; only a current host resolver grants execution.

    No bulk manifest or active release is implied by native source understanding.
    The request authorization binds the host's user-authorized read-only scope.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["boi/native-query-authority@1"]
    principal: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    # Preserve the discriminator and selected/dependency pointers when a
    # scoped review crosses JSON and protected-result storage boundaries.
    definition_authority: NativeReviewedDefinitionAuthority | NativeProcessReviewAuthority
    profile_revision: RevisionRef
    planning_outcome_digest: str
    source_snapshot_digest: str
    parameter_digest: str
    request_authorization_digest: str

    @model_validator(mode="after")
    def exact_native_scope(self):
        if self.principal != self.definition_authority.principal:
            raise ValueError("NATIVE_QUERY_PRINCIPAL_MISMATCH")
        if any(not _sha256(getattr(self, key)) for key in (
            "planning_outcome_digest", "source_snapshot_digest", "parameter_digest",
            "request_authorization_digest")):
            raise ValueError("NATIVE_QUERY_SCOPE_DIGEST_INVALID")
        return self


QueryAuthority = ReviewedQueryAuthority | NativeQueryAuthority


def _query_authority(value):
    return TypeAdapter(QueryAuthority).validate_python(value)


class ReviewedQueryAccess(BaseModel):
    """Server resolver must re-read frozen plan, parameters and current source/ACL."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    authority: QueryAuthority
    logical_plan_digest: str
    parameter_digest: str

    @model_validator(mode="after")
    def exact_digests(self):
        if not _sha256(self.logical_plan_digest) or not _sha256(self.parameter_digest):
            raise ValueError('REVIEWED_QUERY_ACCESS_DIGEST_INVALID')
        if isinstance(self.authority, NativeQueryAuthority) and self.parameter_digest != self.authority.parameter_digest:
            raise ValueError("NATIVE_QUERY_PARAMETERS_CHANGED")
        return self


class ReviewedQueryPagingAccess(ReviewedQueryAccess):
    """Server-only page access checked before count, after count, and per read."""

    paging_phase: Literal["COUNT_PRECHECK", "COUNT_RESULT", "PAGE_READ"]
    result_set_id: str = Field(min_length=1)
    paging_policy_digest: str
    page_size: int = Field(ge=1, le=1000)
    total_row_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def exact_paging_scope(self):
        if not _sha256(self.paging_policy_digest):
            raise ValueError("REVIEWED_QUERY_PAGING_POLICY_DIGEST_INVALID")
        if (self.paging_phase == "COUNT_PRECHECK") != (
            self.total_row_count is None
        ):
            raise ValueError("REVIEWED_QUERY_PAGING_COUNT_PHASE_INVALID")
        return self


class _PlanAuthorityFields(BaseModel):
    active_release_digest: str | None
    candidate_authority: QueryAuthority | None = None

    @model_serializer(mode="wrap")
    def preserve_historical_wire(self, handler):
        value=handler(self)
        if self.candidate_authority is None:
            value.pop('candidate_authority',None)
        return value

    @model_validator(mode="after")
    def exact_authority_lane(self):
        forward=self.schema_name.endswith(('/v3', '/v4'))
        if forward:
            if self.active_release_digest is not None or self.candidate_authority is None:
                raise ValueError('REVIEWED_QUERY_AUTHORITY_REQUIRED_WITHOUT_ACTIVE_RELEASE')
        elif self.active_release_digest is None or self.candidate_authority is not None:
            raise ValueError('HISTORICAL_QUERY_AUTHORITY_CONTRACT_REQUIRED')
        return self


class MultiResultLogicalPlan(_PlanAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal[
        "boi-multi-result-logical-plan/v1",
        "boi-multi-result-logical-plan/v2",
        "boi-multi-result-logical-plan/v3",
        "boi-multi-result-logical-plan/v4",
    ] = (
        "boi-multi-result-logical-plan/v1"
    )
    shape_solver_outcome_digest: str
    profile_contract_binding_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    schema_digest: str
    result_sets: tuple[MultiResultSetPlan, ...]
    parameter_specs: tuple[MultiResultParameterSpec, ...]
    quality_receipt_digests: tuple[str, ...]
    plan_digest: str

    @model_validator(mode="after")
    def version_matches_paging(self):
        paging = any(item.paging_policy for item in self.result_sets)
        if paging != (self.schema_name in {
            "boi-multi-result-logical-plan/v2",
            "boi-multi-result-logical-plan/v4",
        }):
            raise ValueError("PAGING_PLAN_REVISION_REQUIRED")
        return self


class AuthorizedPhysicalMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_ref: str
    source_id: str
    table: str
    column: str
    revision_digest: str
    temporal_encoding: PhysicalTemporalEncoding | None = Field(
        default=None, exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def validate_mapping(self) -> "AuthorizedPhysicalMapping":
        if any(
            not value.strip() or "\x00" in value
            for value in (self.mapping_ref, self.source_id, self.table, self.column)
        ):
            raise ValueError("AUTHORIZED_MAPPING_FIELD_INVALID")
        if not _sha256(self.revision_digest):
            raise ValueError("AUTHORIZED_MAPPING_REVISION_DIGEST_INVALID")
        return self


class MultiResultPlanAuthorityReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "FAIL"]
    error_codes: tuple[str, ...]
    plan_digest: str
    physical_mapping_set_digest: str
    selected_relationship_set_digest: str
    checked_projection_count: int
    checked_filter_count: int
    receipt_digest: str


class MultiResultSqliteColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    data_type: str
    nullable: bool
    primary_key: bool


class MultiResultSqliteTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    columns: tuple[MultiResultSqliteColumn, ...]


class MultiResultSqliteSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_tables: tuple[str, ...]
    tables: tuple[MultiResultSqliteTable, ...]
    schema_digest: str
    source_snapshot_digest: str

    def table(self, name: str) -> MultiResultSqliteTable | None:
        return next((item for item in self.tables if item.name == name), None)


class MultiResultExploratoryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["exploratory"]
    logical_plan: MultiResultLogicalPlan
    validation_receipt: MultiResultPlanAuthorityReceipt
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    selected_relationship_ids: tuple[str, ...]
    quality_receipts: tuple[DataQualityReceipt, ...]
    parameters: dict[str, Any]
    principal: str
    purpose: str
    idempotency_key: str
    inline_row_limit: int = Field(ge=1, le=1000)
    timeout_seconds: int = Field(ge=1, le=30)

    @model_validator(mode="after")
    def validate_receipt_chain(self) -> "MultiResultExploratoryExecutionRequest":
        if not self.principal.strip() or not self.purpose.strip():
            raise ValueError("GATEWAY_AUTHORIZATION_CONTEXT_REQUIRED")
        if not self.idempotency_key.strip():
            raise ValueError("IDEMPOTENCY_KEY_REQUIRED")
        expected_plan_digest = _digest(
            self.logical_plan.model_dump(mode="json", exclude={"plan_digest"})
        )
        if expected_plan_digest != self.logical_plan.plan_digest:
            raise ValueError("MULTI_RESULT_PLAN_DIGEST_INVALID")
        expected_validation = validate_multi_result_plan_authority(
            self.logical_plan,
            physical_mappings=self.physical_mappings,
            selected_relationship_ids=self.selected_relationship_ids,
        )
        if (
            self.validation_receipt.status != "PASS"
            or self.validation_receipt != expected_validation
        ):
            raise ValueError("MULTI_RESULT_VALIDATION_RECEIPT_INVALID")
        quality_digests = tuple(item.receipt_digest for item in self.quality_receipts)
        if quality_digests != self.logical_plan.quality_receipt_digests:
            raise ValueError("MULTI_RESULT_QUALITY_RECEIPT_MISMATCH")
        if any(
            item.schema_snapshot_digest != self.logical_plan.schema_digest
            for item in self.quality_receipts
        ):
            raise ValueError("MULTI_RESULT_QUALITY_SCHEMA_MISMATCH")
        specs = {item.name: item for item in self.logical_plan.parameter_specs}
        if len(specs) != len(self.logical_plan.parameter_specs):
            raise ValueError("MULTI_RESULT_PARAMETER_SPEC_DUPLICATE")
        if set(self.parameters) != set(specs):
            raise ValueError("MULTI_RESULT_PARAMETER_SET_MISMATCH")
        for name, spec in specs.items():
            value = self.parameters[name]
            valid = (
                (spec.type == "string" and isinstance(value, str))
                or (
                    spec.type == "integer"
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                )
                or (
                    spec.type == "number"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                )
                or (spec.type == "boolean" and isinstance(value, bool))
                or (
                    spec.type.endswith("_list")
                    and isinstance(value, (list, tuple))
                    and bool(value)
                    and all(
                        (spec.type == "string_list" and isinstance(item, str))
                        or (
                            spec.type == "integer_list"
                            and isinstance(item, int)
                            and not isinstance(item, bool)
                        )
                        or (
                            spec.type == "number_list"
                            and isinstance(item, (int, float))
                            and not isinstance(item, bool)
                        )
                        or (spec.type == "boolean_list" and isinstance(item, bool))
                        for item in value
                    )
                )
            )
            if not valid:
                raise ValueError("MULTI_RESULT_PARAMETER_TYPE_MISMATCH")
        return self


class MultiResultSetResult(WithLatestQuality):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    result_set_id: str
    role: Literal["ROOT", "CHILD", "RELATIONSHIP", "AGGREGATE", "SCALAR"]
    object_ref: str
    exact_grain: tuple[str, ...]
    parent_link: MultiResultParentLink | None
    completeness_policy: str
    coverage_semantics: str
    coverage_missing_parent_count: int
    coverage_zero_filled_count: int
    rows: tuple[dict[str, Any], ...]
    returned_row_count: int
    row_count: int
    truncated: bool
    result_schema: tuple[tuple[str, str], ...]
    result_schema_digest: str
    result_digest: str


from .stored_row_association import StoredRowAssociationScope, OccurrenceAssociation, build_occurrence_association


class MultiResultQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    result_sets: tuple[MultiResultSetResult, ...]
    quality_sidecars: tuple[DataQualityReceipt, ...]
    occurrence_associations: tuple[OccurrenceAssociation,...] = Field(default=(),exclude_if=lambda v:not v)
    result_digest: str


class MultiResultSetExecutionReceipt(WithLatestQuality):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    result_set_id: str
    exact_grain: tuple[str, ...]
    parent_result_set_id: str | None
    execution_artifact_ref: str
    execution_artifact_digest: str
    result_schema_digest: str
    row_count: int
    returned_row_count: int
    truncated: bool
    coverage_semantics: str
    coverage_missing_parent_count: int
    coverage_zero_filled_count: int
    result_digest: str
    dry_run_digest: str


class MultiResultGatewayReceipt(_PlanAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal[
        "boi-multi-result-exploration-receipt/v1",
        "boi-multi-result-exploration-receipt/v2",
        "boi-multi-result-exploration-receipt/v3",
        "boi-multi-result-exploration-receipt/v4",
    ] = (
        "boi-multi-result-exploration-receipt/v1"
    )
    run_id: str
    result_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    logical_plan_digest: str
    validation_receipt_digest: str
    shape_solver_outcome_digest: str
    profile_contract_binding_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    schema_digest: str
    physical_schema_digest: str
    compiler_digest: str
    parameter_digest: str
    authorization_policy_digest: str
    source_snapshot_digest: str
    quality_receipt_digests: tuple[str, ...]
    result_set_receipts: tuple[MultiResultSetExecutionReceipt, ...]
    result_digest: str
    result_artifact_ref: str
    result_artifact_digest: str
    started_at: str
    completed_at: str
    executed_sql: None = None
    receipt_digest: str

    @model_validator(mode="after")
    def version_matches_paging(self):
        paging = any(item.paging is not None for item in self.result_set_receipts)
        if paging != (self.schema_name in {
            "boi-multi-result-exploration-receipt/v2",
            "boi-multi-result-exploration-receipt/v4",
        }):
            raise ValueError("PAGING_RECEIPT_REVISION_REQUIRED")
        return self

class MultiResultQueryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    lane: Literal["exploratory"] = "exploratory"
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    result_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    result: MultiResultQueryResult
    receipt: MultiResultGatewayReceipt
    attestation: None = None
    exploration_receipt: MultiResultGatewayReceipt


def create_multi_result_logical_plan(
    *,
    shape_solver_outcome_digest: str,
    profile_contract_binding_digest: str,
    active_release_digest: str | None,
    domain_profile_digest: str,
    mapping_profile_digest: str,
    query_profile_digest: str,
    schema_digest: str,
    result_sets: tuple[MultiResultSetPlan, ...],
    parameter_specs: tuple[MultiResultParameterSpec, ...],
    quality_receipt_digests: tuple[str, ...],
    candidate_authority: QueryAuthority | None = None,
) -> MultiResultLogicalPlan:
    digests = (
        shape_solver_outcome_digest,
        profile_contract_binding_digest,
        *((active_release_digest,) if candidate_authority is None else ()),
        domain_profile_digest,
        mapping_profile_digest,
        query_profile_digest,
        schema_digest,
        *quality_receipt_digests,
    )
    if any(not _sha256(item) for item in digests):
        raise ValueError("MULTI_RESULT_DIGEST_INVALID")
    if not result_sets or result_sets[0].role not in {"ROOT", "SCALAR", "AGGREGATE"}:
        raise ValueError("ROOT_RESULT_SET_REQUIRED")
    if result_sets[0].parent_link is not None:
        raise ValueError("ROOT_PARENT_LINK_FORBIDDEN")
    if result_sets[0].role == "SCALAR" and len(result_sets) != 1:
        raise ValueError("SCALAR_STANDALONE_RESULT_REQUIRED")
    if result_sets[0].role == "AGGREGATE" and len(result_sets) != 1:
        raise ValueError("ROOT_AGGREGATE_STANDALONE_RESULT_REQUIRED")
    by_id = {item.result_set_id: item for item in result_sets}
    if len(by_id) != len(result_sets):
        raise ValueError("DUPLICATE_RESULT_SET_ID")
    if sum(item.parent_link is None for item in result_sets) != 1:
        raise ValueError("EXACTLY_ONE_ROOT_RESULT_SET_REQUIRED")
    parameter_names = tuple(item.name for item in parameter_specs)
    if len(parameter_names) != len(set(parameter_names)):
        raise ValueError("MULTI_RESULT_PARAMETER_SPEC_DUPLICATE")
    seen: set[str] = set()
    for result_set in result_sets:
        if any(
            item.parameter_name is not None
            and item.parameter_name not in parameter_names
            for item in result_set.filters
        ):
            raise ValueError("FILTER_PARAMETER_NOT_DECLARED")
        if any(
            item.parameter_name is not None
            and item.parameter_name not in parameter_names
            for constraint in result_set.existence_constraints
            for item in constraint.filters
        ):
            raise ValueError("EXISTENCE_FILTER_PARAMETER_NOT_DECLARED")
        if result_set.parent_link is not None:
            parent = by_id.get(result_set.parent_link.parent_result_set_id)
            if parent is None or parent.result_set_id not in seen:
                raise ValueError("PARENT_RESULT_SET_ORDER_INVALID")
            parent_outputs = {item.output_name for item in parent.projections}
            child_outputs = {item.output_name for item in result_set.projections}
            if not set(result_set.parent_link.parent_key_outputs) <= parent_outputs:
                raise ValueError("PARENT_LINK_KEY_NOT_PROJECTED")
            if not set(result_set.parent_link.child_key_outputs) <= child_outputs:
                raise ValueError("CHILD_LINK_KEY_NOT_PROJECTED")
        seen.add(result_set.result_set_id)
    values = {
        "schema_name": ("boi-multi-result-logical-plan/v2" if any(item.paging_policy for item in result_sets)
                        else "boi-multi-result-logical-plan/v1"),
        "shape_solver_outcome_digest": shape_solver_outcome_digest,
        "profile_contract_binding_digest": profile_contract_binding_digest,
        "active_release_digest": active_release_digest,
        "domain_profile_digest": domain_profile_digest,
        "mapping_profile_digest": mapping_profile_digest,
        "query_profile_digest": query_profile_digest,
        "schema_digest": schema_digest,
        "result_sets": tuple(item.model_dump(mode="json") for item in result_sets),
        "parameter_specs": tuple(
            item.model_dump(mode="json") for item in parameter_specs
        ),
        "quality_receipt_digests": quality_receipt_digests,
    }
    if candidate_authority is not None:
        candidate_authority=_query_authority(candidate_authority.model_dump(mode='json'))
        values.update(schema_name=(
                'boi-multi-result-logical-plan/v4'
                if any(item.paging_policy for item in result_sets)
                else 'boi-multi-result-logical-plan/v3'
            ),
            candidate_authority=candidate_authority.model_dump(mode='json'))
    return MultiResultLogicalPlan(
        **{
            key: value
            for key, value in values.items()
            if key not in {"result_sets", "parameter_specs"}
        },
        result_sets=result_sets,
        parameter_specs=parameter_specs,
        plan_digest=_digest(values),
    )


def validate_multi_result_plan_authority(
    plan: MultiResultLogicalPlan,
    *,
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...],
    selected_relationship_ids: tuple[str, ...],
) -> MultiResultPlanAuthorityReceipt:
    errors: list[str] = []
    expected_plan_digest = _digest(
        plan.model_dump(mode="json", exclude={"plan_digest"})
    )
    if expected_plan_digest != plan.plan_digest:
        errors.append("MULTI_RESULT_PLAN_DIGEST_INVALID")
    by_ref = {item.mapping_ref: item for item in physical_mappings}
    if len(by_ref) != len(physical_mappings):
        errors.append("DUPLICATE_AUTHORIZED_MAPPING")
    checked = 0
    checked_filters = 0
    for result_set in plan.result_sets:
        for projection in (*result_set.projections, *result_set.aggregations):
            checked += 1
            mapping = by_ref.get(projection.mapping_ref)
            if (
                mapping is None
                or mapping.source_id != result_set.source_id
                or mapping.table != result_set.table
                or mapping.column != projection.column
            ):
                errors.append("PROJECTION_MAPPING_MISMATCH")
        for filter_item in result_set.filters:
            checked_filters += 1
            mapping = by_ref.get(filter_item.mapping_ref)
            if (
                mapping is None
                or mapping.source_id != result_set.source_id
                or mapping.table != result_set.table
            ):
                errors.append("FILTER_MAPPING_MISMATCH")
        for constraint in result_set.existence_constraints:
            previous_source = result_set.source_id
            previous_table = result_set.table
            for hop in constraint.hops:
                checked += 2
                parent_mapping = by_ref.get(hop.parent_mapping_ref)
                child_mapping = by_ref.get(hop.child_mapping_ref)
                if (
                    hop.parent_source_id != previous_source
                    or hop.parent_table != previous_table
                    or parent_mapping is None
                    or parent_mapping.source_id != hop.parent_source_id
                    or parent_mapping.table != hop.parent_table
                    or parent_mapping.column != hop.parent_column
                ):
                    errors.append("EXISTENCE_PARENT_MAPPING_MISMATCH")
                if (
                    child_mapping is None
                    or child_mapping.source_id != hop.source_id
                    or child_mapping.table != hop.table
                    or child_mapping.column != hop.child_column
                ):
                    errors.append("EXISTENCE_CHILD_MAPPING_MISMATCH")
                if hop.relationship_contract_id not in selected_relationship_ids:
                    errors.append("EXISTENCE_RELATIONSHIP_NOT_SELECTED")
                previous_source = hop.source_id
                previous_table = hop.table
            for filter_item in constraint.filters:
                checked_filters += 1
                mapping = by_ref.get(filter_item.mapping_ref)
                if (
                    mapping is None
                    or mapping.source_id != previous_source
                    or mapping.table != previous_table
                ):
                    errors.append("EXISTENCE_FILTER_MAPPING_MISMATCH")
        if (
            result_set.parent_link is not None
            and result_set.parent_link.relationship_contract_id
            not in selected_relationship_ids
        ):
            errors.append("PARENT_RELATIONSHIP_NOT_SELECTED")
    ordered_errors = tuple(dict.fromkeys(errors))
    mapping_values = tuple(
        item.model_dump(mode="json")
        for item in sorted(physical_mappings, key=lambda item: item.mapping_ref)
    )
    values = {
        "status": "FAIL" if ordered_errors else "PASS",
        "error_codes": ordered_errors,
        "plan_digest": plan.plan_digest,
        "physical_mapping_set_digest": _digest(mapping_values),
        "selected_relationship_set_digest": _digest(
            tuple(sorted(selected_relationship_ids))
        ),
        "checked_projection_count": checked,
        "checked_filter_count": checked_filters,
    }
    return MultiResultPlanAuthorityReceipt(**values, receipt_digest=_digest(values))


def capture_multi_result_sqlite_schema(
    path: Path, *, allowed_tables: tuple[str, ...]
) -> MultiResultSqliteSchema:
    if not allowed_tables or len(allowed_tables) != len(set(allowed_tables)):
        raise ValueError("AUTHORIZED_TABLE_SET_INVALID")
    path = path.resolve(strict=True)
    source_digest = sealed_sqlite_digest(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        available = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        if not set(allowed_tables) <= available:
            raise ValueError("AUTHORIZED_TABLE_NOT_FOUND")
        tables: list[MultiResultSqliteTable] = []
        for table_name in sorted(allowed_tables):
            quoted = table_name.replace('"', '""')
            rows = connection.execute(f'PRAGMA table_info("{quoted}")').fetchall()
            tables.append(
                MultiResultSqliteTable(
                    name=table_name,
                    columns=tuple(
                        MultiResultSqliteColumn(
                            name=str(row[1]),
                            data_type=str(row[2]).casefold(),
                            nullable=not bool(row[3]) and not bool(row[5]),
                            primary_key=bool(row[5]),
                        )
                        for row in rows
                    ),
                )
            )
        if sealed_sqlite_digest(path) != source_digest:
            raise ValueError("SOURCE_SNAPSHOT_DRIFT")
    finally:
        connection.close()
    if sealed_sqlite_digest(path) != source_digest:
        raise ValueError("SOURCE_SNAPSHOT_DRIFT")
    schema_values = tuple(item.model_dump(mode="json") for item in tables)
    return MultiResultSqliteSchema(
        allowed_tables=tuple(sorted(allowed_tables)),
        tables=tuple(tables),
        schema_digest=_digest(schema_values),
        source_snapshot_digest=source_digest,
    )


def _nearest_rank(values: tuple[int, ...], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(percentile * len(ordered)) - 1)])


def profile_sqlite_relationship_quality(
    path: Path,
    *,
    schema: MultiResultSqliteSchema,
    relationship: RelationshipContract,
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...],
    root_endpoint_ref: str,
    evidence_ref: str,
) -> DataQualityReceipt:
    """Measure a declared relationship without exposing rows or accepting SQL."""

    path = path.resolve(strict=True)
    current = capture_multi_result_sqlite_schema(
        path, allowed_tables=schema.allowed_tables
    )
    if current.schema_digest != schema.schema_digest:
        raise ValueError("SCHEMA_DRIFT")
    if current.source_snapshot_digest != schema.source_snapshot_digest:
        raise ValueError("SOURCE_SNAPSHOT_DRIFT")
    if relationship.schema_snapshot_digest != schema.schema_digest:
        raise ValueError("RELATIONSHIP_SCHEMA_MISMATCH")
    if relationship.cardinality == "many_to_many":
        raise ValueError("RELATIONSHIP_BRIDGE_PROFILE_REQUIRED")
    if root_endpoint_ref == relationship.left_endpoint_ref:
        parent_refs = relationship.physical_keys.left_mapping_refs
        child_refs = relationship.physical_keys.right_mapping_refs
    elif root_endpoint_ref == relationship.right_endpoint_ref:
        parent_refs = relationship.physical_keys.right_mapping_refs
        child_refs = relationship.physical_keys.left_mapping_refs
    else:
        raise ValueError("RELATIONSHIP_ROOT_ENDPOINT_MISMATCH")

    by_ref = {item.mapping_ref: item for item in physical_mappings}
    if len(by_ref) != len(physical_mappings):
        raise ValueError("DUPLICATE_AUTHORIZED_MAPPING")
    try:
        parent = tuple(by_ref[item] for item in parent_refs)
        child = tuple(by_ref[item] for item in child_refs)
    except KeyError as exc:
        raise ValueError("RELATIONSHIP_PHYSICAL_KEY_NOT_AUTHORIZED") from exc
    sources = {item.source_id for item in (*parent, *child)}
    parent_tables = {item.table for item in parent}
    child_tables = {item.table for item in child}
    if len(sources) != 1:
        raise ValueError("RELATIONSHIP_CROSS_SOURCE_FORBIDDEN")
    if len(parent_tables) != 1 or len(child_tables) != 1:
        raise ValueError("RELATIONSHIP_KEY_TABLE_AMBIGUOUS")
    parent_table = next(iter(parent_tables))
    child_table = next(iter(child_tables))
    for mapping in (*parent, *child):
        table = current.table(mapping.table)
        if table is None or mapping.column not in {item.name for item in table.columns}:
            raise ValueError("RELATIONSHIP_PHYSICAL_KEY_NOT_FOUND")

    parent_sql = ", ".join(_identifier(item.column) for item in parent)
    child_sql = ", ".join(_identifier(item.column) for item in child)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        parent_keys = tuple(
            tuple(row)
            for row in connection.execute(
                f"SELECT {parent_sql} FROM {_identifier(parent_table)}"
            )
        )
        child_keys = tuple(
            tuple(row)
            for row in connection.execute(
                f"SELECT {child_sql} FROM {_identifier(child_table)}"
            )
        )
    finally:
        connection.close()

    if sealed_sqlite_digest(path) != current.source_snapshot_digest:
        raise ValueError("SOURCE_SNAPSHOT_DRIFT")

    parent_counts: dict[tuple[Any, ...], int] = {}
    for key in parent_keys:
        parent_counts[key] = parent_counts.get(key, 0) + 1
    child_counts: dict[tuple[Any, ...], int] = {}
    null_fk_rows = 0
    orphan_rows = 0
    matched_rows = 0
    for key in child_keys:
        if any(value is None for value in key):
            null_fk_rows += 1
        elif key not in parent_counts:
            orphan_rows += 1
        else:
            matched_rows += 1
            child_counts[key] = child_counts.get(key, 0) + 1
    scanned_rows = len(child_keys)
    unmatched_rows = null_fk_rows + orphan_rows
    fanouts = tuple(child_counts.get(key, 0) for key in parent_counts)
    observed_min = min(fanouts, default=0)
    observed_max = max(fanouts, default=0)
    duplicate_key_rows = sum(max(0, count - 1) for count in parent_counts.values())
    excluded_rows = (
        unmatched_rows
        if relationship.orphan_policy in {"EXCLUDE_WITH_DISCLOSURE", "QUARANTINE"}
        else 0
    )
    evidence = {
        "relationship_contract_digest": relationship.contract_digest,
        "schema_snapshot_digest": schema.schema_digest,
        "source_snapshot_digest": schema.source_snapshot_digest,
        "parent_table_digest": _digest(parent_table),
        "child_table_digest": _digest(child_table),
        "scanned_rows": scanned_rows,
        "matched_rows": matched_rows,
        "unmatched_rows": unmatched_rows,
        "null_fk_rows": null_fk_rows,
        "orphan_rows": orphan_rows,
        "duplicate_key_rows": duplicate_key_rows,
        "fanout": {
            "observed_min": observed_min,
            "observed_p50": _nearest_rank(fanouts, 0.50),
            "observed_p95": _nearest_rank(fanouts, 0.95),
            "observed_max": observed_max,
        },
        "excluded_rows": excluded_rows,
        "applied_orphan_policy": relationship.orphan_policy,
    }
    return DataQualityReceipt(
        receipt_id=(
            f"quality:{relationship.contract_id}:{schema.source_snapshot_digest[7:19]}"
        ),
        relationship_contract_digest=relationship.contract_digest,
        schema_snapshot_digest=schema.schema_digest,
        scanned_rows=scanned_rows,
        matched_rows=matched_rows,
        unmatched_rows=unmatched_rows,
        null_fk_rows=null_fk_rows,
        orphan_rows=orphan_rows,
        duplicate_key_rows=duplicate_key_rows,
        fanout_distribution=evidence["fanout"],
        excluded_rows=excluded_rows,
        coverage_ratio=matched_rows / scanned_rows if scanned_rows else 1.0,
        applied_orphan_policy=relationship.orphan_policy,
        evidence_ref=evidence_ref,
        evidence_digest=_digest(evidence),
    )


def _identifier(value: str) -> str:
    if not value or "\x00" in value:
        raise ValueError("SQLITE_IDENTIFIER_INVALID")
    return '"' + value.replace('"', '""') + '"'


def _aggregate_expression(aggregate: MultiResultAggregate) -> str:
    """Compile a closed reducer, retaining mapping admission in the gateway.

    For count_rows the mapping is a validated source/table anchor, not a value
    whose nullability or uniqueness changes the count.
    """
    if aggregate.reducer == "count_rows":
        return "COUNT(*)"
    column = _identifier(aggregate.column)
    if aggregate.reducer == "count_distinct":
        return f"COUNT(DISTINCT {column})"
    function = {"count": "COUNT", "sum": "SUM", "average": "AVG",
                "min": "MIN", "max": "MAX"}[aggregate.reducer]
    return f"{function}({column})"


def _binding_token(value: str) -> str:
    token = "".join(
        character if character.isascii() and character.isalnum() else "_"
        for character in value
    )
    if not token:
        raise ValueError("SQLITE_BINDING_TOKEN_INVALID")
    return token


def _result_type(declared_type: str) -> str:
    folded = declared_type.casefold()
    if "int" in folded:
        return "integer"
    if any(item in folded for item in ("char", "clob", "text")):
        return "string"
    if any(item in folded for item in ("real", "floa", "doub", "dec", "num")):
        return "number"
    if "bool" in folded:
        return "boolean"
    if any(item in folded for item in ("date", "time")):
        return "datetime"
    return folded or "blob"


class MultiResultSqliteGateway:
    COMPILER_ID = "boi.multi-result-sqlite-compiler@0.1.0"

    def __init__(
        self,
        path: Path | None,
        *,
        schema: MultiResultSqliteSchema,
        result_artifact_root: Path,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        cancellation_probe: Callable[[str], bool] | None = None,
        contract_schema_digest: str | None = None,
        snapshot_pager: SnapshotResultPager | None = None,
        execution_repository: ProtectedExecutionRepository | None = None,
        reviewed_authority_resolver: Callable[[ReviewedQueryAccess], ReviewedQueryAuthority] | None = None,
        source_adapter=None,
    ) -> None:
        # A later alias retarget cannot switch a previously authorized source.
        if (path is None) == (source_adapter is None):
            raise ValueError('QUERY_GATEWAY_EXACT_SOURCE_REQUIRED')
        self.path = path.resolve(strict=True) if path is not None else None
        self.source_adapter = source_adapter
        self.schema = schema
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic
        self.cancellation_probe = cancellation_probe
        self.contract_schema_digest = contract_schema_digest or schema.schema_digest
        self.result_artifact_root = result_artifact_root
        self.snapshot_pager = snapshot_pager
        self.execution_repository = execution_repository
        self.reviewed_authority_resolver = reviewed_authority_resolver
        self._reviewed_scope = ContextVar("reviewed_gateway_authority", default=None)
        self._idempotency: dict[str, tuple[str, MultiResultQueryExecution]] = {}

    def _capture_schema(self):
        if self.source_adapter is not None:
            return self.source_adapter.capture_schema(allowed_tables=self.schema.allowed_tables)
        return capture_multi_result_sqlite_schema(self.path, allowed_tables=self.schema.allowed_tables)

    def _check_snapshot(self, expected):
        actual = (self._capture_schema().source_snapshot_digest if self.source_adapter is not None
            else sealed_sqlite_digest(self.path))
        if actual != expected:
            raise ValueError('SOURCE_SNAPSHOT_DRIFT')

    def _open_session(self, progress, snapshot):
        if self.source_adapter is not None:
            return self.source_adapter.open_session(progress)
        connection = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True)
        try:
            connection.row_factory = sqlite3.Row
            register_latest_time_functions(connection)
            connection.set_progress_handler(progress, 100)
            connection.execute('PRAGMA query_only = ON')
            connection.execute('BEGIN')
            connection.execute('SELECT COUNT(*) FROM sqlite_master').fetchone()
            self._check_snapshot(snapshot)
            return connection
        except BaseException:
            connection.close()
            raise

    @staticmethod
    def _authorization_digest(*, principal: str, purpose: str) -> str:
        return _digest(
            {
                "principal": principal,
                "purpose": purpose,
                "lane": "exploratory",
                "policy": "boi.multi-result-query-policy@0.1.0",
            }
        )

    def read_result_artifact(
        self, artifact_ref: str, *, principal: str, purpose: str
    ) -> dict[str, Any]:
        prefix = "protected:multi-result:sha256:"
        if not artifact_ref.startswith(prefix):
            raise ValueError("RESULT_ARTIFACT_REF_INVALID")
        hex_digest = artifact_ref.removeprefix(prefix)
        if len(hex_digest) != 64 or any(
            c not in "0123456789abcdef" for c in hex_digest
        ):
            raise ValueError("RESULT_ARTIFACT_REF_INVALID")
        path = self.result_artifact_root / f"{hex_digest}.json"
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("RESULT_ARTIFACT_UNAVAILABLE") from error
        embedded = artifact.get("artifact_digest")
        payload = {
            key: value for key, value in artifact.items() if key != "artifact_digest"
        }
        expected = _digest(payload)
        if embedded != expected or expected != f"sha256:{hex_digest}":
            raise ValueError("RESULT_ARTIFACT_TAMPERED")
        if artifact.get("authorization_policy_digest") != self._authorization_digest(
            principal=principal, purpose=purpose
        ):
            raise ValueError("RESULT_ARTIFACT_ACCESS_DENIED")
        if artifact.get('schema_name') in {
            'boi-protected-multi-result-artifact/v3',
            'boi-protected-multi-result-artifact/v4',
        }:
            authority=_query_authority(artifact['candidate_authority'])
            self._resolve_reviewed_access(ReviewedQueryAccess(authority=authority,
                logical_plan_digest=artifact['logical_plan_digest'],parameter_digest=artifact['parameter_digest']),
                principal=principal,purpose=purpose)
        return artifact

    @staticmethod
    def _request_digest(request: MultiResultExploratoryExecutionRequest) -> str:
        return _digest(request.model_dump(mode="json", exclude={"idempotency_key"}))

    def _progress(
        self, request: MultiResultExploratoryExecutionRequest, started_tick: float
    ) -> tuple[Callable[[], int], dict[str, bool]]:
        state = {"cancelled": False, "timed_out": False}

        def progress() -> int:
            if self.cancellation_probe is not None and self.cancellation_probe(
                request.idempotency_key
            ):
                state["cancelled"] = True
                return 1
            if self.monotonic() - started_tick > request.timeout_seconds:
                state["timed_out"] = True
                return 1
            return 0

        return progress, state

    @staticmethod
    def _raise_interrupted(state: dict[str, bool]) -> None:
        if state["cancelled"]:
            raise ValueError("QUERY_CANCELLED")
        if state["timed_out"]:
            raise ValueError("QUERY_TIMEOUT")

    @contextmanager
    def reviewed_access_scope(self, resolver):
        """Server-only request scope; concurrent callers never replace each other's resolver."""
        token=self._reviewed_scope.set(resolver)
        try:
            if self.snapshot_pager is None:
                yield
            else:
                with self.snapshot_pager.reviewed_access_scope(
                    self._resolve_reviewed_paging_access
                ):
                    yield
        finally:
            self._reviewed_scope.reset(token)

    def _resolve_reviewed_paging_access(self, principal, purpose, binding):
        authority = _query_authority(
            binding.get("candidate_authority")
        )
        access = ReviewedQueryPagingAccess(
            authority=authority,
            logical_plan_digest=binding["logical_plan_digest"],
            parameter_digest=binding["reviewed_parameter_digest"],
            paging_phase=binding["paging_phase"],
            result_set_id=binding["result_set_id"],
            paging_policy_digest=binding["policy_digest"],
            page_size=binding["paging_page_size"],
            total_row_count=binding.get("paging_total_row_count"),
        )
        self._resolve_reviewed_access(
            access, principal=principal, purpose=purpose
        )

    def _resolve_reviewed_access(self,access,*,principal,purpose):
        authority=access.authority
        resolver=self._reviewed_scope.get() or self.reviewed_authority_resolver
        if (authority.principal!=principal or authority.purpose!=purpose
            or resolver is None):
            raise ValueError('REVIEWED_QUERY_EXECUTION_NOT_AUTHORIZED')
        current=resolver(access)
        if not isinstance(current,(ReviewedQueryAuthority, NativeQueryAuthority)) or current!=authority:
            raise ValueError('REVIEWED_QUERY_AUTHORITY_STALE')

    def _check_reviewed_authority(self,request):
        authority=request.logical_plan.candidate_authority
        if authority is not None:
            self._resolve_reviewed_access(ReviewedQueryAccess(authority=authority,
                logical_plan_digest=request.logical_plan.plan_digest,parameter_digest=_digest(request.parameters)),
                principal=request.principal,purpose=request.purpose)

    def create(
        self, request: MultiResultExploratoryExecutionRequest
    ) -> MultiResultQueryExecution:
        request=MultiResultExploratoryExecutionRequest.model_validate(request.model_dump(mode="python"))
        self._check_reviewed_authority(request)
        if self.execution_repository is not None:
            request = MultiResultExploratoryExecutionRequest.model_validate(request.model_dump(mode='python'))
            value = self.execution_repository.execute_once(principal=request.principal, purpose=request.purpose,
                idempotency_key=request.idempotency_key, request_digest=self._request_digest(request),
                execute=lambda: self._create_unpersisted(request))
            return MultiResultQueryExecution.model_validate(value)
        return self._create_unpersisted(request)

    def _create_unpersisted(
        self, request: MultiResultExploratoryExecutionRequest
    ) -> MultiResultQueryExecution:
        request = MultiResultExploratoryExecutionRequest.model_validate(
            request.model_dump(mode="python")
        )
        self._check_reviewed_authority(request)
        current = self._capture_schema()
        native_authority = request.logical_plan.candidate_authority
        if isinstance(native_authority, NativeQueryAuthority) and current.source_snapshot_digest != native_authority.source_snapshot_digest:
            raise ValueError("NATIVE_QUERY_SOURCE_SNAPSHOT_CHANGED")
        if current.schema_digest != self.schema.schema_digest:
            raise ValueError("SCHEMA_DRIFT")
        if request.logical_plan.schema_digest != self.contract_schema_digest:
            raise ValueError("MULTI_RESULT_CONTRACT_SCHEMA_MISMATCH")
        if current.source_snapshot_digest != self.schema.source_snapshot_digest:
            raise ValueError("SOURCE_SNAPSHOT_DRIFT")
        if any(item.directional_scope and item.directional_scope.source_snapshot_digest != current.source_snapshot_digest
               for item in request.quality_receipts):
            raise ValueError("QUALITY_SOURCE_SNAPSHOT_DRIFT")
        bag_scopes = tuple(q.directional_scope for q in request.quality_receipts
            if isinstance(q.directional_scope,StoredRowAssociationScope))
        bag_targets = {q.target_endpoint_ref for q in bag_scopes}
        bag_existence_roots: set[str] = set()
        if bag_scopes:
            sets=request.logical_plan.result_sets
            if len(bag_scopes)!=1 or len(sets)!=2:
                raise ValueError("STORED_ROW_RESULT_SHAPE_UNSUPPORTED")
            if any(s.latest or s.aggregations or s.paging_policy
                   or s.row_limit_policy!="FAIL_IF_EXCEEDED" for s in sets):
                raise ValueError("STORED_ROW_EXECUTION_FEATURE_UNSUPPORTED")
        for scope in bag_scopes:
            roots=[s for s in request.logical_plan.result_sets if s.object_ref==scope.root_endpoint_ref]
            targets=[s for s in request.logical_plan.result_sets if s.object_ref==scope.target_endpoint_ref]
            if len(roots)!=1 or len(targets)!=1:
                raise ValueError("STORED_ROW_RESULT_ENDPOINT_MISMATCH")
            root,target=roots[0],targets[0]
            link=target.parent_link
            if link is None or link.parent_result_set_id!=root.result_set_id:
                raise ValueError("STORED_ROW_RESULT_LINK_REQUIRED")
            root_outputs={p.output_name:p.mapping_ref for p in root.projections}
            target_outputs={p.output_name:p.mapping_ref for p in target.projections}
            if (tuple(root_outputs[k] for k in link.parent_key_outputs)!=scope.root_mapping_refs
                or tuple(target_outputs[k] for k in link.child_key_outputs)!=scope.target_mapping_refs):
                raise ValueError("STORED_ROW_RESULT_KEY_MAPPING_MISMATCH")
            if target.existence_constraints:
                raise ValueError("STORED_ROW_EXISTENCE_SCOPE_UNSUPPORTED")
            if root.existence_constraints:
                if len(scope.root_mapping_refs)!=1 or len(root.existence_constraints)!=1:
                    raise ValueError("STORED_ROW_EXISTENCE_SCOPE_UNSUPPORTED")
                constraint=root.existence_constraints[0]
                if len(constraint.hops)!=1:
                    raise ValueError("STORED_ROW_EXISTENCE_SCOPE_UNSUPPORTED")
                hop=constraint.hops[0]
                if (constraint.filter_object_ref!=target.object_ref
                    or hop.parent_object_ref!=root.object_ref
                    or hop.child_object_ref!=target.object_ref
                    or hop.parent_source_id!=root.source_id
                    or hop.source_id!=target.source_id
                    or hop.parent_table!=root.table
                    or hop.table!=target.table
                    or hop.parent_mapping_ref!=scope.root_mapping_refs[0]
                    or hop.child_mapping_ref!=scope.target_mapping_refs[0]
                    or hop.relationship_contract_id!=link.relationship_contract_id):
                    raise ValueError("STORED_ROW_EXISTENCE_SCOPE_MISMATCH")
                bag_existence_roots.add(root.result_set_id)
        request_digest = self._request_digest(request)
        memory_key = (_digest([request.principal, request.idempotency_key])
                      if self.execution_repository is not None else request.idempotency_key)
        prior = self._idempotency.get(memory_key)
        if prior is not None:
            if prior[0] != request_digest:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return prior[1]

        result_sources = {item.source_id for item in request.logical_plan.result_sets}
        if len(result_sources) != 1:
            raise ValueError("MULTI_RESULT_CROSS_SOURCE_FORBIDDEN")
        authorized_sources = {item.source_id for item in request.physical_mappings}
        if not result_sources <= authorized_sources:
            raise ValueError("RESULT_SET_SOURCE_NOT_AUTHORIZED")
        for result_set in request.logical_plan.result_sets:
            if result_set.paging_policy is not None and self.snapshot_pager is None:
                raise ValueError("SNAPSHOT_PAGING_CAPABILITY_UNAVAILABLE")
            table = current.table(result_set.table)
            if table is None:
                raise ValueError("RESULT_SET_SOURCE_NOT_AUTHORIZED")
            columns = {item.name for item in table.columns}
            if any(
                item.column not in columns
                for item in (*result_set.projections, *result_set.aggregations)
            ):
                raise ValueError("RESULT_SET_COLUMN_NOT_AUTHORIZED")

        started_at = self.clock().isoformat()
        started_tick = self.monotonic()
        progress, interruption = self._progress(request, started_tick)
        if progress():
            self._raise_interrupted(interruption)
        run_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"boi-multi-result:{request.idempotency_key}:{request_digest}",
            )
        )
        compiler_identity: Any = self.COMPILER_ID
        latest_compilation = any(
            item.latest and item.latest.selection_policy
            for item in request.logical_plan.result_sets
        )
        temporal_compilation = any(
            item.temporal_encoding is not None
            for item in request.physical_mappings
        )
        nested_filter_compilation=any(item.filter_expression is not None for item in request.logical_plan.result_sets)
        if latest_compilation or temporal_compilation or nested_filter_compilation or bag_existence_roots:
            compiler_files = [
                "multi_result_query_gateway.py", "latest_execution_quality.py",
                "latest_time_order.py", "temporal_sql_comparison.py",
                "snapshot_result_paging.py", "temporal_predicate_quality.py",
                "sqlite_source_snapshot.py",
            ]
            if temporal_compilation:
                compiler_files.append("physical_temporal_encoding.py")
            if nested_filter_compilation:
                compiler_files.append('filter_expression.py')
            if bag_existence_roots:
                compiler_files.append('stored_row_association.py')
            compiler_identity = {
                "compiler": (
                    'boi.multi-result-sqlite-compiler@0.8.0' if bag_existence_roots else
                    'boi.multi-result-sqlite-compiler@0.7.0' if temporal_compilation else
                    'boi.multi-result-sqlite-compiler@0.6.0' if nested_filter_compilation else
                    "boi.multi-result-sqlite-compiler@0.4.0"
                ),
                "code": {
                    name: "sha256:" + hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                    for name in compiler_files
                },
            }
        compiler_digest = _digest(compiler_identity)
        results: list[MultiResultSetResult] = []
        receipts: list[MultiResultSetExecutionReceipt] = []
        result_rows_by_id: dict[str, tuple[dict[str, Any], ...]] = {}
        association_rows_by_id: dict[str, tuple[dict[str, Any], ...]] = {}
        remaining_inline_rows = request.inline_row_limit
        remaining_result_sets = len(request.logical_plan.result_sets)
        connection = self._open_session(progress, current.source_snapshot_digest)
        try:
            for result_set in request.logical_plan.result_sets:
                aliases = {
                    item.output_name: item.column for item in result_set.projections
                }
                projection_parts = [
                    f"{_identifier(item.column)} AS {_identifier(item.output_name)}"
                    for item in result_set.projections
                ]
                for aggregate in result_set.aggregations:
                    expression = _aggregate_expression(aggregate)
                    projection_parts.append(
                        f"{expression} AS {_identifier(aggregate.output_name)}"
                    )
                projection_sql = ", ".join(projection_parts)
                order_directions = result_set.ordering_directions or tuple(
                    "ASC" for _ in result_set.ordering
                )
                physical_by_ref = {
                    item.mapping_ref: item for item in request.physical_mappings
                }
                projected_mappings = {
                    item.output_name: physical_by_ref[item.mapping_ref]
                    for item in result_set.projections
                }
                temporal_order_policies = {
                    output: policy
                    for output, mapping in projected_mappings.items()
                    if output in result_set.ordering
                    if (policy := policy_for_mapping(
                        mapping, request.logical_plan.result_sets
                    )) is not None
                }
                order_sql = ", ".join(
                    (
                        temporal_expression(_identifier(aliases[item]), temporal_order_policies[item])
                        if item in temporal_order_policies else _identifier(aliases[item])
                        if item in aliases
                        else _identifier(item)
                    )
                    + f" {direction}"
                    for item, direction in zip(
                        result_set.ordering, order_directions, strict=True
                    )
                )
                comparison = {
                    "eq": "=",
                    "neq": "!=",
                    "gt": ">",
                    "gte": ">=",
                    "lt": "<",
                    "lte": "<=",
                }
                bindings: dict[str, Any] = {}
                filters: list[str] = []
                own_temporal_filters: set[str] = set()
                direct_temporal_filters: set[str] = set()
                preselection_exists: dict[str,str] = {}
                predicate_audit_specs: list[dict] = []
                for index, filter_item in enumerate(result_set.filters):
                    mapping = physical_by_ref[filter_item.mapping_ref]
                    temporal_policy = policy_for_mapping(mapping, request.logical_plan.result_sets)
                    column_sql = (temporal_expression(_identifier(mapping.column), temporal_policy)
                        if temporal_policy else _identifier(mapping.column))
                    binding_name = (
                        f"p_{_binding_token(result_set.result_set_id)}_{index}"
                    )
                    if filter_item.operator in {"is_null", "not_null"}:
                        filters.append(
                            f"{_identifier(mapping.column)} IS "
                            + (
                                "NULL"
                                if filter_item.operator == "is_null"
                                else "NOT NULL"
                            )
                        )
                    elif filter_item.operator == "in":
                        value = request.parameters[filter_item.parameter_name]
                        names: list[str] = []
                        for value_index, item in enumerate(value):
                            item_name = f"{binding_name}_{value_index}"
                            names.append(f":{item_name}")
                            bindings[item_name] = temporal_parameter(item, temporal_policy) if temporal_policy else item
                        filters.append(
                            f"{column_sql} IN ({', '.join(names)})"
                        )
                    else:
                        value = request.parameters[filter_item.parameter_name]
                        bindings[binding_name] = temporal_parameter(value, temporal_policy) if temporal_policy else value
                        filters.append(
                            f"{column_sql} {comparison[filter_item.operator]} :{binding_name}"
                        )
                    if temporal_policy:
                        direct_temporal_filters.add(filters[-1])
                    if temporal_policy and result_set.latest and mapping.column == aliases[result_set.latest.ordering[0]]:
                        own_temporal_filters.add(filters[-1])
                if result_set.filter_expression is not None:
                    if direct_temporal_filters:
                        raise ValueError('NESTED_FILTER_TEMPORAL_AUDIT_UNRESOLVED')
                    filters=[compose_filter_sql(result_set.filter_expression,filters)]
                for constraint_index, constraint in enumerate(
                    result_set.existence_constraints
                ):
                    hops = constraint.hops
                    aliases_for_hops = tuple(
                        _identifier(f"__boi_exists_{constraint_index}_{index}")
                        for index in range(len(hops))
                    )
                    first_hop = hops[0]
                    child_key = f"{aliases_for_hops[0]}.{_identifier(first_hop.child_column)}"
                    parent_key = f"{_identifier(result_set.table)}.{_identifier(first_hop.parent_column)}"
                    child_conditions = [(
                        f"typeof({child_key}) = typeof({parent_key}) AND "
                        f"{child_key} COLLATE BINARY = {parent_key} COLLATE BINARY"
                        if result_set.result_set_id in bag_existence_roots else
                        f"{child_key} = {parent_key}"
                    )]
                    joins: list[str] = []
                    for hop_index, hop in enumerate(hops[1:], start=1):
                        joins.append(
                            f" JOIN {_identifier(hop.table)} AS "
                            f"{aliases_for_hops[hop_index]} ON "
                            f"{aliases_for_hops[hop_index]}."
                            f"{_identifier(hop.child_column)} = "
                            f"{aliases_for_hops[hop_index - 1]}."
                            f"{_identifier(hop.parent_column)}"
                        )
                    filter_alias = aliases_for_hops[-1]
                    non_temporal_child_filters = []
                    temporal_targets = {}
                    for filter_index, filter_item in enumerate(constraint.filters):
                        mapping = physical_by_ref[filter_item.mapping_ref]
                        column_sql = f"{filter_alias}.{_identifier(mapping.column)}"
                        temporal_policy = policy_for_mapping(mapping, request.logical_plan.result_sets)
                        if temporal_policy:
                            for policy in selection_policies_for_mapping(mapping, request.logical_plan.result_sets):
                                temporal_targets[(mapping.mapping_ref,policy)] = (mapping,policy)
                        if temporal_policy and filter_item.operator not in {"is_null", "not_null"}:
                            column_sql = temporal_expression(column_sql, temporal_policy)
                        binding_name = f"x_{_binding_token(result_set.result_set_id)}_{constraint_index}_{filter_index}"
                        if filter_item.operator in {"is_null", "not_null"}:
                            child_conditions.append(
                                f"{column_sql} IS "
                                + (
                                    "NULL"
                                    if filter_item.operator == "is_null"
                                    else "NOT NULL"
                                )
                            )
                        elif filter_item.operator == "in":
                            value = request.parameters[filter_item.parameter_name]
                            names: list[str] = []
                            for value_index, item in enumerate(value):
                                item_name = f"{binding_name}_{value_index}"
                                names.append(f":{item_name}")
                                bindings[item_name] = temporal_parameter(item, temporal_policy) if temporal_policy else item
                            child_conditions.append(
                                f"{column_sql} IN ({', '.join(names)})"
                            )
                        else:
                            value = request.parameters[filter_item.parameter_name]
                            bindings[binding_name] = temporal_parameter(value, temporal_policy) if temporal_policy else value
                            child_conditions.append(
                                f"{column_sql} {comparison[filter_item.operator]} :{binding_name}"
                            )
                        if not temporal_policy:
                            non_temporal_child_filters.append(child_conditions[-1])
                    existence_prefix=("NOT EXISTS" if constraint.polarity == "ABSENT" else "EXISTS")
                    filters.append(
                        existence_prefix + " (SELECT 1 FROM "
                        f"{_identifier(first_hop.table)} AS {aliases_for_hops[0]}"
                        + "".join(joins)
                        + " WHERE "
                        + " AND ".join(child_conditions)
                        + ")"
                    )
                    preselection_exists[filters[-1]] = (
                        "1=1" if constraint.polarity == "ABSENT" else
                        "EXISTS (SELECT 1 FROM "
                        f"{_identifier(first_hop.table)} AS {aliases_for_hops[0]}"
                        + "".join(joins) + " WHERE "
                        + " AND ".join([child_conditions[0],*non_temporal_child_filters]) + ")"
                    )
                    for mapping,policy in temporal_targets.values():
                        predicate_audit_specs.append(dict(result_set_id=result_set.result_set_id,
                            constraint_index=constraint_index,constraint=constraint,hop_aliases=aliases_for_hops,
                            root_table=result_set.table,non_temporal_predicates=non_temporal_child_filters,
                            mapping=mapping,policy=policy,source_snapshot_digest=current.source_snapshot_digest))
                if result_set.parent_link is not None and result_set.object_ref not in bag_targets:
                    parent_rows = result_rows_by_id[
                        result_set.parent_link.parent_result_set_id
                    ]
                    child_columns = tuple(
                        aliases[item]
                        for item in result_set.parent_link.child_key_outputs
                    )
                    parent_keys = tuple(
                        dict.fromkeys(
                            tuple(
                                row[item]
                                for item in result_set.parent_link.parent_key_outputs
                            )
                            for row in parent_rows
                            if all(
                                row[item] is not None
                                for item in result_set.parent_link.parent_key_outputs
                            )
                        )
                    )
                    if not parent_keys:
                        filters.append("0 = 1")
                    elif len(child_columns) == 1:
                        names = []
                        for index, key in enumerate(parent_keys):
                            name = f"link_{_binding_token(result_set.result_set_id)}_{index}"
                            names.append(f":{name}")
                            bindings[name] = key[0]
                        filters.append(
                            f"{_identifier(child_columns[0])} IN ({', '.join(names)})"
                        )
                    else:
                        rows_sql = []
                        for row_index, key in enumerate(parent_keys):
                            names = []
                            for key_index, value in enumerate(key):
                                name = f"link_{_binding_token(result_set.result_set_id)}_{row_index}_{key_index}"
                                names.append(f":{name}")
                                bindings[name] = value
                            rows_sql.append(f"({', '.join(names)})")
                        filters.append(
                            f"({', '.join(_identifier(item) for item in child_columns)}) IN ({', '.join(rows_sql)})"
                        )
                group_sql = ", ".join(
                    _identifier(item.column) for item in result_set.projections
                )
                from_sql = _identifier(result_set.table)
                where_sql = f" WHERE {' AND '.join(filters)}" if filters else ""
                root_audit_filters = [preselection_exists.get(item,item) for item in filters if item not in direct_temporal_filters]
                root_preselection_where = " WHERE " + " AND ".join(root_audit_filters) if root_audit_filters else ""
                temporal_predicate_quality = tuple(audit_temporal_predicate(connection,
                    root_preselection_where=root_preselection_where,bindings=bindings,**spec)
                    for spec in predicate_audit_specs)
                temporal_mapping_refs = {item.mapping_ref for item in result_set.filters}
                temporal_mapping_refs.update(item.mapping_ref for item in result_set.projections
                    if item.output_name in result_set.ordering)
                temporal_predicate_quality += tuple(audit_mapping_temporal_input(connection,
                    result_set_id=result_set.result_set_id, table=result_set.table,
                    preselection_where=root_preselection_where, bindings=bindings,
                    mapping=physical_by_ref[ref], source_snapshot_digest=current.source_snapshot_digest)
                    for ref in sorted(temporal_mapping_refs)
                    if physical_by_ref[ref].temporal_encoding is not None)
                latest_quality = None
                if result_set.latest is not None:
                    audit_filters = [item for item in filters if item not in own_temporal_filters]
                    audit_where_sql = " WHERE " + " AND ".join(audit_filters) if audit_filters else ""
                    latest_quality, non_null_filter = audit_latest_input(connection,
                        result_set_id=result_set.result_set_id, latest=result_set.latest,
                        aliases=aliases, from_sql=from_sql, where_sql=where_sql, bindings=bindings,
                        source_snapshot_digest=current.source_snapshot_digest,
                        pre_temporal_where_sql=audit_where_sql if result_set.latest.selection_policy else None)
                    if non_null_filter:
                        filters.append(non_null_filter)
                        where_sql = " WHERE " + " AND ".join(filters)
                    partition_sql = ", ".join(
                        _identifier(aliases[item])
                        for item in result_set.latest.partition_by
                    )
                    latest_order_sql = ", ".join(
                        (temporal_expression(_identifier(aliases[item]), result_set.latest.selection_policy.time_ordering) + f" {direction}"
                         if result_set.latest.selection_policy and item == result_set.latest.ordering[0]
                         else f"{_identifier(aliases[item])} {direction}")
                        for item, direction in zip(
                            result_set.latest.ordering,
                            result_set.latest.ordering_directions,
                            strict=True,
                        )
                    )
                    ranked = (
                        "SELECT *, ROW_NUMBER() OVER (PARTITION BY "
                        f"{partition_sql} ORDER BY {latest_order_sql}) AS __boi_latest_rank "
                        f"FROM {from_sql}{where_sql}"
                    )
                    from_sql = f"({ranked})"
                    where_sql = " WHERE __boi_latest_rank = 1"
                unbounded_sql = (
                    f"SELECT {projection_sql} FROM {from_sql}{where_sql}"
                    + (f" GROUP BY {group_sql}" if result_set.aggregations and result_set.role != "SCALAR" else "")
                )
                sql = (
                    unbounded_sql
                    + (f" ORDER BY {order_sql}" if order_sql else "")
                    + " LIMIT "
                    + str(
                        result_set.result_row_limit
                        if result_set.row_limit_policy == "TRUNCATE"
                        else result_set.result_row_limit + 1
                    )
                )
                compiled_binding = {"compiler": compiler_identity,
                    "result_set_id": result_set.result_set_id, "sql": sql}
                if isinstance(compiler_identity, dict):
                    # Protected compiler bytes contain actual normalized parameters;
                    # public execution receipts still bind the original typed input.
                    compiled_binding.update(parameters=bindings,
                        original_parameter_digest=_digest(request.parameters))
                compiled_sql_digest = _digest(compiled_binding)
                if self.execution_repository is not None:
                    stored_digest = self.execution_repository.store_binding(compiled_binding)
                    if stored_digest != compiled_sql_digest:
                        raise ValueError('EXECUTION_BINDING_DIGEST_MISMATCH')
                dry_run = tuple(
                    tuple(row)
                    for row in connection.execute(
                        f"EXPLAIN QUERY PLAN {sql}", bindings
                    ).fetchall()
                )
                paging = None
                if result_set.paging_policy is not None:
                    # Only this deterministic compiler can hand SQL to the pager.
                    # A page-bearing request never materializes the entire child
                    # collection and never counts its first page as completeness.
                    assert self.snapshot_pager is not None
                    page_policy = result_set.paging_policy
                    allocation = remaining_inline_rows // remaining_result_sets
                    if page_policy.page_size > allocation:
                        raise ValueError("PAGING_INLINE_BUDGET_EXCEEDED")
                    table_contract = current.table(result_set.table)
                    declared_types = {item.name: _result_type(item.data_type) for item in table_contract.columns}
                    page_schema = tuple((item.output_name, declared_types[item.column]) for item in result_set.projections) + tuple(
                        (item.output_name, "integer" if item.reducer in {"count_rows", "count", "count_distinct"} else "number") for item in result_set.aggregations)
                    prepared = self.snapshot_pager.prepare(
                        query=CompiledPageQuery(sql=unbounded_sql, parameters=bindings,
                            allowed_tables=current.allowed_tables, exact_grain=result_set.exact_grain,
                            ordering=result_set.ordering,
                            ordering_directions=result_set.ordering_directions or tuple("ASC" for _ in result_set.ordering),
                            result_schema=page_schema, compiler_digest=compiler_digest,
                            temporal_order_policies=tuple(sorted(temporal_order_policies.items()))),
                        policy=page_policy, principal=request.principal, purpose=request.purpose,
                        run_id=run_id, result_set_id=result_set.result_set_id,
                        source_snapshot_digest=current.source_snapshot_digest,
                        schema_digest=request.logical_plan.schema_digest,
                        logical_plan_digest=request.logical_plan.plan_digest,
                        active_release_digest=request.logical_plan.active_release_digest,
                        query_profile_digest=request.logical_plan.query_profile_digest,
                        domain_profile_digest=request.logical_plan.domain_profile_digest,
                        mapping_profile_digest=request.logical_plan.mapping_profile_digest,
                        authorization_policy_digest=self._authorization_digest(principal=request.principal, purpose=request.purpose),
                        candidate_authority=(
                            request.logical_plan.candidate_authority.model_dump(mode="json")
                            if request.logical_plan.candidate_authority is not None
                            else None
                        ),
                        reviewed_parameter_digest=(
                            _digest(request.parameters)
                            if request.logical_plan.candidate_authority is not None
                            else None
                        ),
                    )
                    page = self.snapshot_pager.read_page(prepared["paging_ref"], principal=request.principal, purpose=request.purpose)
                    rows = tuple(page["rows"])
                    paging = SnapshotPageAccess(
                        paging_ref=prepared["paging_ref"], policy_digest=prepared["policy_digest"],
                        count_receipt_digest=prepared["count_receipt_digest"], page_receipt_digest=page["receipt_digest"],
                        page_result_digest=page["page_result_digest"], total_row_count=prepared["total_row_count"],
                        returned_row_count=len(rows), page_size=prepared["page_size"],
                        expires_at=prepared["expires_at"], next_cursor=page["next_cursor"])
                    # Descendants cannot be silently limited to a parent's first
                    # page. A later subquery-root paging revision can support it.
                    if paging.total_row_count > len(rows) and any(
                        item.parent_link and item.parent_link.parent_result_set_id == result_set.result_set_id
                        for item in request.logical_plan.result_sets):
                        raise ValueError("PAGING_PARENT_DEPENDENCY_INCOMPLETE")
                else:
                    cursor = connection.execute(sql, bindings)
                    if bag_scopes and self.source_adapter is not None and not getattr(cursor, "sqlite_types_preserved", False):
                        raise ValueError("STORED_ROW_SOURCE_CELL_TYPES_REQUIRED")
                    rows = tuple(dict(row) for row in cursor.fetchall())
                if (
                    result_set.row_limit_policy == "FAIL_IF_EXCEEDED"
                    and len(rows) > result_set.result_row_limit
                ):
                    raise ValueError("RESULT_SET_ROW_LIMIT_EXCEEDED")
                missing_parent_count = 0
                zero_filled_count = 0
                if result_set.parent_link is not None and paging is not None:
                    parent_rows = result_rows_by_id[result_set.parent_link.parent_result_set_id]
                    parent_keys = {tuple(row[key] for key in result_set.parent_link.parent_key_outputs) for row in parent_rows}
                    link_outputs = ", ".join(_identifier(key) for key in result_set.parent_link.child_key_outputs)
                    # Link keys only, bounded by the already-selected parent set;
                    # the first child page cannot prove parent coverage.
                    observed_keys = {tuple(row) for row in connection.execute(
                        f"SELECT DISTINCT {link_outputs} FROM ({unbounded_sql}) LIMIT {len(parent_keys) + 1}", bindings
                    ).fetchall()}
                    if len(observed_keys) > len(parent_keys):
                        raise ValueError("PAGING_PARENT_CLOSURE_MISMATCH")
                    missing_parent_count = len(parent_keys - observed_keys)
                if result_set.parent_link is not None and paging is None:
                    parent_rows = result_rows_by_id[
                        result_set.parent_link.parent_result_set_id
                    ]
                    parent_keys = tuple(
                        dict.fromkeys(
                            tuple(
                                row[item]
                                for item in result_set.parent_link.parent_key_outputs
                            )
                            for row in parent_rows
                        )
                    )
                    observed_keys = {
                        tuple(
                            row[item]
                            for item in result_set.parent_link.child_key_outputs
                        )
                        for row in rows
                    }
                    missing_keys = tuple(
                        key for key in parent_keys if key not in observed_keys
                    )
                    missing_parent_count = len(missing_keys)
                    if result_set.coverage_semantics == "ROOT_COMPLETE_ZERO_FILL":
                        synthesized = tuple(
                            {
                                **dict(
                                    zip(
                                        result_set.parent_link.child_key_outputs,
                                        key,
                                        strict=True,
                                    )
                                ),
                                **{
                                    output: 0
                                    for output in result_set.zero_fill_aggregate_outputs
                                },
                            }
                            for key in missing_keys
                        )
                        rows = rows + synthesized
                        zero_filled_count = len(synthesized)
                        if result_set.ordering:
                            rows = tuple(
                                sorted(
                                    rows,
                                    key=lambda row: tuple(
                                        (row[item] is None, row[item])
                                        for item in result_set.ordering
                                    ),
                                )
                            )
                        if len(rows) > result_set.result_row_limit:
                            raise ValueError("RESULT_SET_ROW_LIMIT_EXCEEDED")
                table_contract = current.table(result_set.table)
                if table_contract is None:
                    raise ValueError("RESULT_SET_SOURCE_NOT_AUTHORIZED")
                declared_types = {
                    item.name: _result_type(item.data_type)
                    for item in table_contract.columns
                }
                schema = tuple(
                    (item.output_name, declared_types[item.column])
                    for item in result_set.projections
                ) + tuple(
                    (
                        item.output_name,
                        "integer"
                        if item.reducer in {"count_rows", "count", "count_distinct"}
                        else "number",
                    )
                    for item in result_set.aggregations
                )
                # Relationship equality consumes original SQLite cells, never display rounding.
                association_rows_by_id[result_set.result_set_id] = rows
                normalized_rows = normalize_result_rows(rows)  # Retain finite-value validation.
                # A stored occurrence must deliver the same cells used by typed equality.
                # Legacy analytical display canonicalization is not a bag value contract.
                if not bag_scopes:
                    rows = normalized_rows
                result_digest = prepared["query_result_digest"] if paging is not None else _digest(rows)
                result_rows_by_id[result_set.result_set_id] = rows
                allocation = (
                    remaining_inline_rows // remaining_result_sets
                    if remaining_result_sets
                    else 0
                )
                inline_rows = rows[:allocation]
                remaining_inline_rows -= len(inline_rows)
                remaining_result_sets -= 1
                parent_id = (
                    result_set.parent_link.parent_result_set_id
                    if result_set.parent_link
                    else None
                )
                result = MultiResultSetResult(
                    run_id=run_id,
                    result_set_id=result_set.result_set_id,
                    role=result_set.role,
                    object_ref=result_set.object_ref,
                    exact_grain=result_set.exact_grain,
                    parent_link=result_set.parent_link,
                    completeness_policy=result_set.completeness_policy,
                    coverage_semantics=result_set.coverage_semantics,
                    coverage_missing_parent_count=missing_parent_count,
                    coverage_zero_filled_count=zero_filled_count,
                    rows=inline_rows,
                    returned_row_count=len(inline_rows),
                    row_count=paging.total_row_count if paging else len(rows),
                    truncated=len(inline_rows) < (paging.total_row_count if paging else len(rows)),
                    result_schema=schema,
                    result_schema_digest=_digest(schema),
                    result_digest=result_digest,
                    paging=paging,
                    latest_quality=latest_quality,
                    temporal_predicate_quality=temporal_predicate_quality,
                    latest_policy=result_set.latest.selection_policy if result_set.latest else None,
                )
                results.append(result)
                receipts.append(
                    MultiResultSetExecutionReceipt(
                        run_id=run_id,
                        result_set_id=result_set.result_set_id,
                        exact_grain=result_set.exact_grain,
                        parent_result_set_id=parent_id,
                        execution_artifact_ref=(page["compiled_page_ref"] if paging else
                            f"protected:sqlite-sql:{compiled_sql_digest}"),
                        execution_artifact_digest=page["compiled_page_digest"] if paging else compiled_sql_digest,
                        result_schema_digest=result.result_schema_digest,
                        row_count=result.row_count,
                        returned_row_count=result.returned_row_count,
                        truncated=result.truncated,
                        coverage_semantics=result.coverage_semantics,
                        coverage_missing_parent_count=(
                            result.coverage_missing_parent_count
                        ),
                        coverage_zero_filled_count=(result.coverage_zero_filled_count),
                        result_digest=result.result_digest,
                        dry_run_digest=page["dry_run_digest"] if paging else _digest(dry_run),
                        paging=paging,
                        latest_quality=latest_quality,
                        temporal_predicate_quality=temporal_predicate_quality,
                        latest_policy=result.latest_policy,
                    )
                )
            self._check_snapshot(current.source_snapshot_digest)
            connection.commit()
        except sqlite3.OperationalError as exc:
            self._raise_interrupted(interruption)
            raise ValueError("MULTI_RESULT_SQLITE_EXECUTION_FAILED") from exc
        finally:
            connection.close()
        self._check_snapshot(current.source_snapshot_digest)
        if progress():
            self._raise_interrupted(interruption)

        associations=[]
        for scope in bag_scopes:
            roots=[s for s in request.logical_plan.result_sets if s.object_ref==scope.root_endpoint_ref]
            targets=[s for s in request.logical_plan.result_sets if s.object_ref==scope.target_endpoint_ref]
            if len(roots)!=1 or len(targets)!=1:
                raise ValueError("STORED_ROW_RESULT_ENDPOINT_MISMATCH")
            root,target=roots[0],targets[0]
            link=target.parent_link
            if link is None or link.parent_result_set_id!=root.result_set_id:
                raise ValueError("STORED_ROW_RESULT_LINK_REQUIRED")
            root_outputs={p.output_name:p.mapping_ref for p in root.projections}
            target_outputs={p.output_name:p.mapping_ref for p in target.projections}
            if (tuple(root_outputs[k] for k in link.parent_key_outputs)!=scope.root_mapping_refs
                or tuple(target_outputs[k] for k in link.child_key_outputs)!=scope.target_mapping_refs):
                raise ValueError("STORED_ROW_RESULT_KEY_MAPPING_MISMATCH")
            associations.append(build_occurrence_association(run_id=run_id,
                relationship_ref=link.relationship_contract_id,
                root_result_set_id=root.result_set_id,target_result_set_id=target.result_set_id,
                roots=association_rows_by_id[root.result_set_id],targets=association_rows_by_id[target.result_set_id],
                root_keys=link.parent_key_outputs,target_keys=link.child_key_outputs,
                max_pairs=min(root.result_row_limit,target.result_row_limit),
                max_fanout=scope.budget_per_root,progress=progress))
        if associations:
            self._check_snapshot(current.source_snapshot_digest)
            if progress():
                self._raise_interrupted(interruption)
        self._check_reviewed_authority(request)
        completed_at = self.clock().isoformat()
        result_values = tuple(
            {
                "result_set_id": item.result_set_id,
                "row_count": item.row_count,
                "result_schema_digest": item.result_schema_digest,
                "result_digest": item.result_digest,
                **({"latest_quality_digest": item.latest_quality.receipt_digest} if item.latest_quality else {}),
                **({"temporal_predicate_quality_digests":tuple(q.receipt_digest for q in item.temporal_predicate_quality)} if item.temporal_predicate_quality else {}),
            }
            for item in results
        )
        combined_result_digest = _digest(
            {
                "result_sets": result_values,
                "quality_receipt_digests": request.logical_plan.quality_receipt_digests,
                **({"occurrence_associations":[a.model_dump(mode="json") for a in associations]} if associations else {}),
            }
        )
        result = MultiResultQueryResult(
            run_id=run_id,
            result_sets=tuple(results),
            quality_sidecars=request.quality_receipts,
            occurrence_associations=tuple(associations),
            result_digest=combined_result_digest,
        )
        authorization_policy_digest = self._authorization_digest(
            principal=request.principal, purpose=request.purpose
        )
        artifact_payload = {
            "schema_name": ("boi-protected-multi-result-artifact/v2" if any(item.paging for item in results) else "boi-protected-multi-result-artifact/v1"),
            "run_id": run_id,
            **({"occurrence_associations":[a.model_dump(mode="json") for a in associations]} if associations else {}),
            "logical_plan_digest": request.logical_plan.plan_digest,
            "active_release_digest": request.logical_plan.active_release_digest,
            "schema_digest": request.logical_plan.schema_digest,
            "physical_schema_digest": current.schema_digest,
            "source_snapshot_digest": current.source_snapshot_digest,
            "authorization_policy_digest": authorization_policy_digest,
            "quality_receipt_digests": request.logical_plan.quality_receipt_digests,
            "result_digest": combined_result_digest,
            "result_sets": tuple(
                {
                    "result_set_id": result_set.result_set_id,
                    "exact_grain": result_set.exact_grain,
                    "coverage_semantics": result_set.coverage_semantics,
                    "coverage_missing_parent_count": result_set.coverage_missing_parent_count,
                    "coverage_zero_filled_count": result_set.coverage_zero_filled_count,
                    "result_schema": result_set.result_schema,
                    "result_schema_digest": result_set.result_schema_digest,
                    "row_count": result_set.row_count,
                    "result_digest": result_set.result_digest,
                    "rows": result_rows_by_id[result_set.result_set_id],
                    **({"paging": result_set.paging.model_dump(mode="json")} if result_set.paging else {}),
                    **({"latest_quality": result_set.latest_quality.model_dump(mode="json"),
                        "latest_policy": result_set.latest_policy.model_dump(mode="json")} if result_set.latest_quality else {}),
                    **({"temporal_predicate_quality":[q.model_dump(mode="json") for q in result_set.temporal_predicate_quality]} if result_set.temporal_predicate_quality else {}),
                }
                for result_set in results
            ),
        }
        self._check_reviewed_authority(request)
        if self.source_adapter is not None:
            artifact_payload['source_execution'] = {
                'binding':self.source_adapter.binding.model_dump(mode='json'),
                'calls':tuple(self.source_adapter.receipts),
                'consistency':'each API read transaction checked against one pinned source revision'}
        if request.logical_plan.candidate_authority is not None:
            artifact_payload.update(schema_name=(
                    'boi-protected-multi-result-artifact/v4'
                    if any(item.paging for item in results)
                    else 'boi-protected-multi-result-artifact/v3'
                ),parameter_digest=_digest(request.parameters),
                candidate_authority=request.logical_plan.candidate_authority.model_dump(mode='json'))
        result_artifact_digest = _digest(artifact_payload)
        result_artifact_ref = f"protected:multi-result:{result_artifact_digest}"
        artifact = {
            **artifact_payload,
            "artifact_digest": result_artifact_digest,
        }
        self.result_artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.result_artifact_root.chmod(0o700)
        artifact_path = self.result_artifact_root / f"{result_artifact_digest[7:]}.json"
        encoded = json.dumps(
            artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if artifact_path.exists():
            if artifact_path.read_text(encoding="utf-8") != encoded:
                raise ValueError("RESULT_ARTIFACT_CONTENT_ADDRESS_CONFLICT")
        else:
            temporary = artifact_path.with_suffix(".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(artifact_path)
        receipt_values = {
            "schema_name": ("boi-multi-result-exploration-receipt/v2" if any(item.paging for item in results) else "boi-multi-result-exploration-receipt/v1"),
            "run_id": run_id,
            "result_status": "PROVISIONAL",
            "logical_plan_digest": request.logical_plan.plan_digest,
            "validation_receipt_digest": request.validation_receipt.receipt_digest,
            "shape_solver_outcome_digest": request.logical_plan.shape_solver_outcome_digest,
            "profile_contract_binding_digest": request.logical_plan.profile_contract_binding_digest,
            "active_release_digest": request.logical_plan.active_release_digest,
            "domain_profile_digest": request.logical_plan.domain_profile_digest,
            "mapping_profile_digest": request.logical_plan.mapping_profile_digest,
            "query_profile_digest": request.logical_plan.query_profile_digest,
            "schema_digest": request.logical_plan.schema_digest,
            "physical_schema_digest": current.schema_digest,
            "compiler_digest": compiler_digest,
            "parameter_digest": _digest(request.parameters),
            "authorization_policy_digest": authorization_policy_digest,
            "source_snapshot_digest": current.source_snapshot_digest,
            "quality_receipt_digests": request.logical_plan.quality_receipt_digests,
            "result_set_receipts": tuple(
                item.model_dump(mode="json") for item in receipts
            ),
            "result_digest": combined_result_digest,
            "result_artifact_ref": result_artifact_ref,
            "result_artifact_digest": result_artifact_digest,
            "started_at": started_at,
            "completed_at": completed_at,
            "executed_sql": None,
        }
        if request.logical_plan.candidate_authority is not None:
            receipt_values.update(schema_name=(
                    'boi-multi-result-exploration-receipt/v4'
                    if any(item.paging for item in results)
                    else 'boi-multi-result-exploration-receipt/v3'
                ),
                candidate_authority=request.logical_plan.candidate_authority.model_dump(mode='json'))
        receipt = MultiResultGatewayReceipt(
            **{
                key: value
                for key, value in receipt_values.items()
                if key != "result_set_receipts"
            },
            result_set_receipts=tuple(receipts),
            receipt_digest=_digest(receipt_values),
        )
        execution = MultiResultQueryExecution(
            execution_id=run_id,
            result=result,
            receipt=receipt,
            exploration_receipt=receipt,
        )
        self._idempotency[memory_key] = (request_digest, execution)
        return execution

    def get(self, execution_id: str) -> MultiResultQueryExecution | None:
        if self.execution_repository is not None:
            value = self.execution_repository.get(execution_id)
            if value is None:
                return None
            execution = MultiResultQueryExecution.model_validate(value)
            self.execution_repository.validate_bindings(execution.receipt)
            return execution
        for _, execution in self._idempotency.values():
            if execution.execution_id == execution_id:
                return execution
        return None


__all__ = [
    "ReviewedQueryAuthority",
    "ReviewedQueryAccess",
    "AuthorizedPhysicalMapping",
    "MultiResultAggregate",
    "MultiResultLogicalPlan",
    "MultiResultExploratoryExecutionRequest",
    "MultiResultExistenceConstraint",
    "MultiResultExistenceHop",
    "MultiResultFilter",
    "MultiResultGatewayReceipt",
    "MultiResultParentLink",
    "MultiResultParameterSpec",
    "MultiResultPlanAuthorityReceipt",
    "MultiResultProjection",
    "MultiResultSetPlan",
    "MultiResultSqliteGateway",
    "MultiResultSqliteSchema",
    "MultiResultQueryExecution",
    "capture_multi_result_sqlite_schema",
    "create_multi_result_logical_plan",
    "profile_sqlite_relationship_quality",
    "validate_multi_result_plan_authority",
]
