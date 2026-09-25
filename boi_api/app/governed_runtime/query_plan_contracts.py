"""Domain-neutral contracts shared by governed planners and query gateways.

The canonical profile-driven query path may import this module. It therefore
contains data contracts only: no question-family routing, registered QuerySpec
lookup, DEXA fixtures, SQL rendering, database access, or execution effects.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class JoinAuthority(str, Enum):
    schema_defined = "schema_defined"
    steward_verified = "steward_verified"
    usage_observed = "usage_observed"
    llm_inferred = "llm_inferred"


class CatalogColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    data_type: str
    nullable: bool
    primary_key: bool


class CatalogTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    columns: tuple[CatalogColumn, ...]


class CatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal: str
    purpose: str
    active_release_digest: str
    schema_digest: str
    allowed_tables: tuple[str, ...]
    tables: tuple[CatalogTable, ...]
    raw_rows: tuple[dict[str, Any], ...] = ()

    @property
    def snapshot_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))

    def column_exists(self, table_name: str, column_name: str) -> bool:
        return any(
            table.name == table_name
            and any(column.name == column_name for column in table.columns)
            for table in self.tables
        )


class IntentFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property: str
    operator: Literal["eq", "in", "gte", "lte"]
    value: str | int | float


class AnalyticIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    entities: tuple[str, ...]
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[IntentFilter, ...]
    time_range: tuple[str, str] | None
    grain: tuple[str, ...]
    ordering: tuple[str, ...]
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = ()
    limit: int
    unresolved_terms: tuple[str, ...]
    semantic_ambiguities: tuple[str, ...]

    @property
    def intent_digest(self) -> str:
        payload = self.model_dump(mode="json")
        if not self.ordering_directions:
            payload.pop("ordering_directions", None)
        return _digest(payload)

    @property
    def semantic_digest(self) -> str:
        payload = self.model_dump(mode="json", exclude={"question"})
        if not self.ordering_directions:
            payload.pop("ordering_directions", None)
        return _digest(payload)


class PhysicalField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_name: str
    table: str
    column: str
    evidence_refs: tuple[str, ...]


class JoinContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one"]
    optionality: Literal["required", "optional"]
    validity_window: tuple[str, str] | None
    authority_basis: JoinAuthority
    evidence_refs: tuple[str, ...]
    physically_validated: bool


class DomainQueryContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    fields: tuple[PhysicalField, ...]
    joins: tuple[JoinContract, ...]

    @property
    def profile_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))

    def field(self, logical_name: str) -> PhysicalField:
        for item in self.fields:
            if item.logical_name == logical_name:
                return item
        raise KeyError(logical_name)


class SourceSetCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tables: tuple[str, ...]
    columns: tuple[str, ...]
    joins: tuple[JoinContract, ...]
    selection_reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    active_release_digest: str
    catalog_snapshot_digest: str

    @property
    def source_set_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class AggregateBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    function: Literal["count", "average"]
    field: PhysicalField | None
    alias: str


class LatestByBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partition_by: tuple[PhysicalField, ...]
    ordering: tuple[PhysicalField, ...]
    ordering_directions: tuple[Literal["ASC", "DESC"], ...]


class LogicalQueryPlanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_spec_id: None = None
    operators: tuple[
        Literal[
            "scan",
            "join",
            "filter",
            "aggregate",
            "latest",
            "project",
            "order",
            "limit",
        ],
        ...,
    ]
    tables: tuple[str, ...]
    joins: tuple[JoinContract, ...]
    filters: tuple[IntentFilter, ...]
    filter_bindings: tuple[PhysicalField, ...]
    projections: tuple[PhysicalField, ...]
    aggregates: tuple[AggregateBinding, ...] = ()
    latest_by: LatestByBinding | None = None
    ordering: tuple[PhysicalField, ...]
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = ()
    limit: int
    intent_digest: str
    source_set_digest: str
    domain_profile_digest: str
    catalog_snapshot_digest: str
    policy_digest: str

    @property
    def plan_digest(self) -> str:
        payload = self.model_dump(mode="json")
        if not self.aggregates:
            payload.pop("aggregates", None)
        if self.latest_by is None:
            payload.pop("latest_by", None)
        if not self.ordering_directions:
            payload.pop("ordering_directions", None)
        return _digest(payload)


class PlanValidationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "FAIL"]
    error_codes: tuple[str, ...]
    acl_checked: bool
    schema_checked: bool
    key_type_checked: bool
    join_connectivity_checked: bool
    cardinality_checked: bool
    grain_checked: bool
    unit_checked: bool
    time_checked: bool
    cost_checked: bool
    compiler_capability_checked: bool
    intent_digest: str
    plan_digest: str
    active_release_digest: str
    catalog_snapshot_digest: str
    policy_digest: str

    @property
    def receipt_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))
