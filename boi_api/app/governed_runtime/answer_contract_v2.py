"""Strict answer-goal and v2 presentation requirements.

The v1 answer requirement remains the historical reader contract.  This module
adds semantic closure without granting execution, Release, or activation
authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .answer_quality import AnswerRequirementContract


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _is_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _require_unique_text(values: tuple[str, ...], reason: str) -> None:
    if len(values) != len(set(values)) or any(not value.strip() for value in values):
        raise ValueError(reason)


def _value_matches_type(value: Any, value_type: str) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type in {"date", "datetime"}:
        return isinstance(value, str) and bool(value.strip())
    return False


class AnswerOrdering(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    direction: Literal["ASC", "DESC"]

    @field_validator("field_ref")
    @classmethod
    def require_field_ref(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ANSWER_ORDERING_FIELD_REQUIRED")
        return value


class TypedAnswerFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    operator: Literal[
        "EQ", "NE", "IN", "NOT_IN", "IS_NULL", "IS_NOT_NULL", "LT", "LTE", "GT", "GTE", "RANGE"
    ]
    value_type: Literal["string", "integer", "number", "boolean", "date", "datetime"]
    value: Any = None
    unit: str | None = None

    @model_validator(mode="after")
    def validate_filter(self) -> "TypedAnswerFilter":
        if not self.field_ref.strip():
            raise ValueError("ANSWER_FILTER_FIELD_REQUIRED")
        if self.operator in {"IS_NULL", "IS_NOT_NULL"} and self.value is not None:
            raise ValueError("NULL_FILTER_VALUE_FORBIDDEN")
        if self.operator not in {"IS_NULL", "IS_NOT_NULL"} and self.value is None:
            raise ValueError("ANSWER_FILTER_VALUE_REQUIRED")
        if self.operator in {"IN", "NOT_IN", "RANGE"} and not isinstance(
            self.value, (list, tuple)
        ):
            raise ValueError("ANSWER_FILTER_COLLECTION_REQUIRED")
        if self.operator == "RANGE" and len(self.value) != 2:
            raise ValueError("ANSWER_FILTER_RANGE_INVALID")
        values = self.value if isinstance(self.value, (list, tuple)) else (self.value,)
        if self.operator not in {"IS_NULL", "IS_NOT_NULL"} and any(
            not _value_matches_type(item, self.value_type) for item in values
        ):
            raise ValueError("ANSWER_FILTER_TYPE_MISMATCH")
        return self


class TypedAnswerParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_ref: str
    value_type: Literal["string", "integer", "number", "boolean", "date", "datetime"]
    value: Any
    unit: str | None = None

    @field_validator("parameter_ref")
    @classmethod
    def require_parameter_ref(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ANSWER_PARAMETER_REF_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_parameter_type(self) -> "TypedAnswerParameter":
        if not _value_matches_type(self.value, self.value_type):
            raise ValueError("ANSWER_PARAMETER_TYPE_MISMATCH")
        return self


class AnswerAggregation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_ref: str
    reducer: Literal["COUNT", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX"]
    input_ref: str | None = None
    output_unit: str | None = None

    @field_validator("metric_ref")
    @classmethod
    def require_metric_ref(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ANSWER_AGGREGATION_METRIC_REQUIRED")
        return value


class AnswerDirectSummaryContract(BaseModel):
    """Bounded deterministic prose semantics fixed before result rendering."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["scoped_sequence", "latest_distinct", "nested_quality"]
    root_label: str
    primary_label: str
    root_result_set_id: str
    primary_result_set_id: str | None = None
    secondary_label: str = ""
    secondary_result_set_id: str | None = None
    distinct_field_ref: str | None = None
    grain_label: str = ""
    unbound_subject_label: str = ""
    unbound_reason_label: str = ""
    orphan_reason_label: str = ""

    @model_validator(mode="after")
    def validate_summary_contract(self) -> "AnswerDirectSummaryContract":
        if not self.root_label.strip() or not self.primary_label.strip():
            raise ValueError("ANSWER_DIRECT_SUMMARY_LABEL_REQUIRED")
        if not self.root_result_set_id.strip():
            raise ValueError("ANSWER_DIRECT_SUMMARY_RESULT_REQUIRED")
        if self.mode == "latest_distinct" and (
            not self.distinct_field_ref or not self.grain_label.strip()
        ):
            raise ValueError("ANSWER_DIRECT_SUMMARY_DISTINCT_REQUIRED")
        if self.mode == "nested_quality" and (
            not self.primary_result_set_id
            or not self.secondary_label.strip()
            or not self.secondary_result_set_id
            or not self.unbound_subject_label.strip()
            or not self.unbound_reason_label.strip()
            or not self.orphan_reason_label.strip()
        ):
            raise ValueError("ANSWER_DIRECT_SUMMARY_NESTED_REQUIRED")
        return self


class AnswerGoalContract(BaseModel):
    """Question-local answer semantics fixed before physical execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-goal/v1"] = "boi-answer-goal/v1"
    question_digest: str
    resolved_intent_digest: str
    answer_mode: Literal[
        "object_set", "sequence", "latest", "nested", "aggregate", "relation"
    ]
    root_object: str
    requested_objects: tuple[str, ...]
    requested_properties: tuple[str, ...]
    requested_metrics: tuple[str, ...]
    requested_relations: tuple[str, ...]
    requested_facets: tuple[str, ...]
    typed_filters: tuple[TypedAnswerFilter, ...]
    typed_parameters: tuple[TypedAnswerParameter, ...]
    exact_grain: tuple[str, ...] = Field(min_length=1)
    grouping_semantics: str | None
    nesting_semantics: str | None
    aggregations: tuple[AnswerAggregation, ...]
    ordering: tuple[AnswerOrdering, ...]
    latest_semantics: str | None
    latest_tie_break: tuple[AnswerOrdering, ...]
    unit_semantics: str | None
    time_semantics: str | None
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED_WITH_FULL_ACCESS", "QUALITY_SIDECAR_REQUIRED"
    ]
    preview_page_size: int | None = Field(default=None, gt=0, le=1000)
    pagination_required: bool
    required_quality_disclosures: tuple[
        Literal["null", "orphan", "unbound", "duplicate", "truncation", "freshness"], ...
    ]
    direct_summary: AnswerDirectSummaryContract | None = None
    active_release_digest: str
    profile_closure_digest: str
    acl_policy_digest: str

    @field_validator(
        "question_digest",
        "resolved_intent_digest",
        "active_release_digest",
        "profile_closure_digest",
        "acl_policy_digest",
    )
    @classmethod
    def require_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_GOAL_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def validate_semantic_closure(self) -> "AnswerGoalContract":
        if not self.root_object.strip():
            raise ValueError("ANSWER_GOAL_ROOT_REQUIRED")
        if not any(
            (
                self.requested_objects,
                self.requested_properties,
                self.requested_metrics,
                self.requested_relations,
            )
        ):
            raise ValueError("ANSWER_GOAL_REQUEST_REQUIRED")
        for values, reason in (
            (self.requested_objects, "ANSWER_GOAL_OBJECT_DUPLICATE"),
            (self.requested_properties, "ANSWER_GOAL_PROPERTY_DUPLICATE"),
            (self.requested_metrics, "ANSWER_GOAL_METRIC_DUPLICATE"),
            (self.requested_relations, "ANSWER_GOAL_RELATION_DUPLICATE"),
            (self.requested_facets, "ANSWER_GOAL_FACET_DUPLICATE"),
            (self.exact_grain, "ANSWER_GOAL_GRAIN_DUPLICATE"),
            (self.required_quality_disclosures, "ANSWER_GOAL_DISCLOSURE_DUPLICATE"),
        ):
            _require_unique_text(values, reason)
        ordering_fields = tuple(item.field_ref for item in self.ordering)
        latest_fields = tuple(item.field_ref for item in self.latest_tie_break)
        parameter_refs = tuple(item.parameter_ref for item in self.typed_parameters)
        _require_unique_text(ordering_fields, "ANSWER_GOAL_ORDERING_DUPLICATE")
        _require_unique_text(latest_fields, "ANSWER_GOAL_LATEST_TIE_BREAK_DUPLICATE")
        _require_unique_text(parameter_refs, "ANSWER_GOAL_PARAMETER_DUPLICATE")

        if self.answer_mode == "sequence":
            if not self.ordering:
                raise ValueError("SEQUENCE_ORDERING_REQUIRED")
            if not self.requested_facets:
                raise ValueError("SEQUENCE_DISPLAY_FACET_REQUIRED")
        if self.answer_mode == "latest" and (
            not self.latest_semantics or not self.latest_tie_break
        ):
            raise ValueError("LATEST_TIE_BREAK_REQUIRED")
        if self.answer_mode == "nested" and not self.nesting_semantics:
            raise ValueError("NESTED_SEMANTICS_REQUIRED")
        if self.answer_mode == "aggregate" and not self.aggregations:
            raise ValueError("AGGREGATION_SEMANTICS_REQUIRED")
        if self.completeness_policy == "BOUNDED_WITH_FULL_ACCESS":
            if not self.pagination_required:
                raise ValueError("FULL_ACCESS_PAGINATION_REQUIRED")
            if self.preview_page_size is None:
                raise ValueError("FULL_ACCESS_PREVIEW_REQUIRED")
            if "truncation" not in self.required_quality_disclosures:
                raise ValueError("FULL_ACCESS_TRUNCATION_DISCLOSURE_REQUIRED")
        return self

    @property
    def contract_digest(self) -> str:
        return _digest(self)


class AnswerPaginationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["NONE", "ANSWER_SCOPED_CURSOR"]
    page_size: int | None = Field(default=None, gt=0, le=1000)
    full_access_required: bool

    @model_validator(mode="after")
    def validate_policy(self) -> "AnswerPaginationPolicy":
        if self.full_access_required and (
            self.mode != "ANSWER_SCOPED_CURSOR" or self.page_size is None
        ):
            raise ValueError("ANSWER_PAGINATION_CLOSURE_REQUIRED")
        if self.mode == "NONE" and self.page_size is not None:
            raise ValueError("ANSWER_PAGINATION_PAGE_SIZE_FORBIDDEN")
        return self


class AnswerRequirementContractV2(AnswerRequirementContract):
    """V1 presentation fidelity plus active semantic and access bindings."""

    schema_name: Literal["boi-answer-requirement/v2"] = "boi-answer-requirement/v2"
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED_WITH_FULL_ACCESS", "QUALITY_SIDECAR_REQUIRED"
    ]
    required_quality_disclosures: tuple[
        Literal["null", "orphan", "unbound", "duplicate", "truncation", "freshness"], ...
    ]
    answer_goal_digest: str
    resolved_intent_digest: str
    active_release_digest: str
    profile_closure_digest: str
    display_policy_digest: str
    mapping_projection_digest: str
    pagination_policy: AnswerPaginationPolicy
    direct_summary: AnswerDirectSummaryContract | None = None

    @field_validator(
        "answer_goal_digest",
        "resolved_intent_digest",
        "active_release_digest",
        "profile_closure_digest",
        "display_policy_digest",
        "mapping_projection_digest",
    )
    @classmethod
    def require_v2_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_REQUIREMENT_V2_DIGEST_INVALID")
        return value

    @field_validator("latest_ordering")
    @classmethod
    def require_directional_latest_ordering(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if any(
            len(value.rsplit(" ", 1)) != 2
            or value.rsplit(" ", 1)[1] not in {"ASC", "DESC"}
            or not value.rsplit(" ", 1)[0].strip()
            for value in values
        ):
            raise ValueError("ANSWER_REQUIREMENT_V2_LATEST_ORDERING_INVALID")
        return values

    @model_validator(mode="after")
    def validate_v2_pagination_closure(self) -> "AnswerRequirementContractV2":
        bounded = self.completeness_policy == "BOUNDED_WITH_FULL_ACCESS"
        if bounded and not self.pagination_policy.full_access_required:
            raise ValueError("ANSWER_REQUIREMENT_V2_PAGINATION_MISMATCH")
        if bounded and "truncation" not in self.required_quality_disclosures:
            raise ValueError("ANSWER_REQUIREMENT_V2_TRUNCATION_DISCLOSURE_REQUIRED")
        if self.latest_semantics and not self.latest_ordering:
            raise ValueError("ANSWER_REQUIREMENT_V2_LATEST_ORDERING_REQUIRED")
        return self


class AnswerRequirementMigrationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-requirement-migration-receipt/v1"] = (
        "boi-answer-requirement-migration-receipt/v1"
    )
    source_schema: Literal["boi-answer-requirement/v1"]
    target_schema: Literal["boi-answer-requirement/v2"]
    source_contract_digest: str
    target_contract_digest: str
    answer_goal_digest: str
    migration_code_digest: str
    preserved_semantics_digest: str
    source_overwritten: Literal[False] = False
    authorizes_release: Literal[False] = False
    authorizes_activation: Literal[False] = False

    @field_validator(
        "source_contract_digest",
        "target_contract_digest",
        "answer_goal_digest",
        "migration_code_digest",
        "preserved_semantics_digest",
    )
    @classmethod
    def require_receipt_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_MIGRATION_DIGEST_INVALID")
        return value

    @property
    def receipt_digest(self) -> str:
        return _digest(self)


def read_answer_requirement_history(
    payload: Mapping[str, Any],
) -> AnswerRequirementContract | AnswerRequirementContractV2:
    """Read historical v1 or current v2 without an implicit migration."""

    schema_name = payload.get("schema_name", "boi-answer-requirement/v1")
    if schema_name == "boi-answer-requirement/v1":
        return AnswerRequirementContract.model_validate(dict(payload))
    if schema_name == "boi-answer-requirement/v2":
        return AnswerRequirementContractV2.model_validate(dict(payload))
    raise ValueError("ANSWER_REQUIREMENT_SCHEMA_UNSUPPORTED")


def migrate_answer_requirement_v1(
    *,
    source: Mapping[str, Any],
    answer_goal: AnswerGoalContract,
    display_policy_digest: str,
    mapping_projection_digest: str,
    migration_code_digest: str,
) -> tuple[AnswerRequirementContractV2, AnswerRequirementMigrationReceipt]:
    """Create a v2 sibling and a non-authoritative receipt; never mutate v1."""

    historical = AnswerRequirementContract.model_validate(dict(source))
    if historical.question_digest != answer_goal.question_digest:
        raise ValueError("ANSWER_MIGRATION_QUESTION_MISMATCH")
    if historical.acl_policy_digest != answer_goal.acl_policy_digest:
        raise ValueError("ANSWER_MIGRATION_ACL_MISMATCH")
    if historical.exact_grain != answer_goal.exact_grain:
        raise ValueError("ANSWER_MIGRATION_GRAIN_MISMATCH")
    for value in (
        display_policy_digest,
        mapping_projection_digest,
        migration_code_digest,
    ):
        if not _is_digest(value):
            raise ValueError("ANSWER_MIGRATION_DIGEST_INVALID")

    pagination_required = historical.completeness_policy == "BOUNDED_WITH_FULL_ARTIFACT"
    target_payload = historical.model_dump(mode="json")
    if target_payload["completeness_policy"] == "BOUNDED_WITH_FULL_ARTIFACT":
        target_payload["completeness_policy"] = "BOUNDED_WITH_FULL_ACCESS"
    target_payload.update(
        {
            "schema_name": "boi-answer-requirement/v2",
            "answer_goal_digest": answer_goal.contract_digest,
            "resolved_intent_digest": answer_goal.resolved_intent_digest,
            "active_release_digest": answer_goal.active_release_digest,
            "profile_closure_digest": answer_goal.profile_closure_digest,
            "display_policy_digest": display_policy_digest,
            "mapping_projection_digest": mapping_projection_digest,
            "latest_ordering": [
                f"{item.field_ref} {item.direction}"
                for item in answer_goal.latest_tie_break
            ],
            "pagination_policy": {
                "mode": "ANSWER_SCOPED_CURSOR" if pagination_required else "NONE",
                "page_size": answer_goal.preview_page_size if pagination_required else None,
                "full_access_required": pagination_required,
            },
        }
    )
    target = AnswerRequirementContractV2.model_validate(target_payload)
    preserved_semantics = {
        key: historical.model_dump(mode="json")[key]
        for key in type(historical).model_fields
        if key != "schema_name"
    }
    receipt = AnswerRequirementMigrationReceipt(
        source_schema=historical.schema_name,
        target_schema=target.schema_name,
        source_contract_digest=historical.contract_digest,
        target_contract_digest=target.contract_digest,
        answer_goal_digest=answer_goal.contract_digest,
        migration_code_digest=migration_code_digest,
        preserved_semantics_digest=_digest(preserved_semantics),
    )
    return target, receipt


__all__ = [
    "AnswerAggregation",
    "AnswerGoalContract",
    "AnswerOrdering",
    "AnswerPaginationPolicy",
    "AnswerRequirementContractV2",
    "AnswerRequirementMigrationReceipt",
    "TypedAnswerFilter",
    "TypedAnswerParameter",
    "migrate_answer_requirement_v1",
    "read_answer_requirement_history",
]
