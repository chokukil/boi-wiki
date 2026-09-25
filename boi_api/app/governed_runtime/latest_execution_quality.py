"""Scalar-only preselection audit over the same read-only SQLite transaction."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer

from .latest_selection_contract import digest
from .snapshot_result_paging import WithSnapshotPageAccess
from .latest_time_order import TimeOrdering
from .temporal_predicate_quality import TemporalPredicateQualityReceipt, MappingTemporalQualityReceipt


class LatestExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    versioning_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    version_identity_output: str = Field(min_length=1)
    null_time_policy: Literal["BLOCK", "EXCLUDE_WITH_DISCLOSURE"]
    null_business_key_policy: Literal["BLOCK"]
    time_ordering: TimeOrdering


class LatestDataQualityReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["boi/latest-data-quality@1"] = "boi/latest-data-quality@1"
    result_set_id: str
    contract_digest: str
    versioning_digest: str
    source_snapshot_digest: str
    input_scope_digest: str
    scanned_rows: int = Field(ge=0)
    null_time_rows: int = Field(ge=0)
    null_business_key_rows: int = Field(ge=0)
    null_version_rows: int = Field(ge=0)
    duplicate_version_rows: int = Field(ge=0)
    invalid_time_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    applied_null_time_policy: Literal["BLOCK", "EXCLUDE_WITH_DISCLOSURE"]
    applied_time_ordering: TimeOrdering
    receipt_digest: str

    @model_validator(mode="after")
    def validate_receipt(self):
        if digest(self.model_dump(mode="json", exclude={"receipt_digest"})) != self.receipt_digest:
            raise ValueError("LATEST_QUALITY_DIGEST_INVALID")
        if any(value > self.scanned_rows for value in (self.null_time_rows, self.null_business_key_rows, self.null_version_rows, self.duplicate_version_rows, self.invalid_time_rows, self.excluded_rows)):
            raise ValueError("LATEST_QUALITY_COUNT_INVALID")
        return self


class LatestDataQualityReceiptV2(LatestDataQualityReceipt):
    """Source quality before temporal selection; v1 remains byte-preserved history."""
    contract_version: Literal["boi/latest-data-quality@2"] = "boi/latest-data-quality@2"
    audit_phase: Literal["AUTHORIZED_NON_TEMPORAL_SCOPE_BEFORE_TIME_FILTER"]
    selection_scope_digest: str


class WithLatestQuality(WithSnapshotPageAccess):
    temporal_predicate_quality: tuple[TemporalPredicateQualityReceipt | MappingTemporalQualityReceipt, ...] = ()
    latest_quality: LatestDataQualityReceiptV2 | LatestDataQualityReceipt | None = None
    latest_policy: LatestExecutionPolicy | None = None

    @model_validator(mode="after")
    def bind_quality_policy(self):
        if (self.latest_quality is None) != (self.latest_policy is None):
            raise ValueError("LATEST_POLICY_QUALITY_CLOSURE_REQUIRED")
        if self.latest_quality and (
            self.latest_quality.contract_digest != self.latest_policy.contract_digest
            or self.latest_quality.versioning_digest != self.latest_policy.versioning_digest
            or self.latest_quality.applied_null_time_policy != self.latest_policy.null_time_policy
            or self.latest_quality.applied_time_ordering != self.latest_policy.time_ordering
        ):
            raise ValueError("LATEST_POLICY_QUALITY_MISMATCH")
        return self

    @model_serializer(mode="wrap")
    def omit_absent_extensions(self, handler):
        result = handler(self)
        if not self.temporal_predicate_quality:
            result.pop("temporal_predicate_quality", None)
        if self.paging is None:
            result.pop("paging", None)
        if self.latest_quality is None:
            result.pop("latest_quality", None)
        if self.latest_policy is None:
            result.pop("latest_policy", None)
        return result


def audit_latest_input(connection, *, result_set_id, latest, aliases, from_sql, where_sql, bindings, source_snapshot_digest,
                       pre_temporal_where_sql=None):
    policy = latest.selection_policy
    if policy is None:
        return None, None
    def quote(value):
        if not value or "\x00" in value:
            raise ValueError("LATEST_IDENTIFIER_INVALID")
        return '"' + value.replace('"', '""') + '"'
    timestamp = quote(aliases[latest.ordering[0]])
    identity = quote(aliases[policy.version_identity_output])
    key_null = " OR ".join(f"{quote(aliases[key])} IS NULL" for key in latest.partition_by)
    sql = (f"SELECT COUNT(*), COALESCE(SUM({timestamp} IS NULL),0), "
           f"COALESCE(SUM({key_null}),0), COALESCE(SUM({identity} IS NULL),0), "
           f"COUNT({identity}) - COUNT(DISTINCT {identity}), "
           f"COALESCE(SUM({timestamp} IS NOT NULL AND boi_latest_time_key({timestamp}, '{policy.time_ordering}') IS NULL),0) "
           f"FROM {from_sql}{where_sql if pre_temporal_where_sql is None else pre_temporal_where_sql}")
    scanned, null_time, null_key, null_version, duplicates, invalid_time = tuple(connection.execute(sql, bindings).fetchone())
    if null_key:
        raise ValueError("LATEST_NULL_BUSINESS_KEY_BLOCKED")
    if null_version:
        raise ValueError("LATEST_VERSION_IDENTITY_NULL")
    if duplicates:
        raise ValueError("LATEST_VERSION_IDENTITY_NOT_UNIQUE")
    if invalid_time:
        raise ValueError("LATEST_TIME_FORMAT_POLICY_MISMATCH")
    if null_time and policy.null_time_policy == "BLOCK":
        raise ValueError("LATEST_NULL_TIME_BLOCKED")
    values = dict(contract_version="boi/latest-data-quality@1", result_set_id=result_set_id,
        contract_digest=policy.contract_digest, versioning_digest=policy.versioning_digest,
        source_snapshot_digest=source_snapshot_digest, input_scope_digest=digest({"sql": sql, "bindings": bindings}),
        scanned_rows=scanned, null_time_rows=null_time, null_business_key_rows=null_key,
        null_version_rows=null_version, duplicate_version_rows=duplicates,
        invalid_time_rows=invalid_time, excluded_rows=null_time, applied_null_time_policy=policy.null_time_policy,
        applied_time_ordering=policy.time_ordering)
    receipt_type = LatestDataQualityReceipt
    if pre_temporal_where_sql is not None:
        receipt_type = LatestDataQualityReceiptV2
        values.update(contract_version="boi/latest-data-quality@2",
            audit_phase="AUTHORIZED_NON_TEMPORAL_SCOPE_BEFORE_TIME_FILTER",
            selection_scope_digest=digest({"from":from_sql,"where":where_sql,"bindings":bindings}))
    return receipt_type(**values, receipt_digest=digest(values)), (f"{timestamp} IS NOT NULL" if null_time else None)
