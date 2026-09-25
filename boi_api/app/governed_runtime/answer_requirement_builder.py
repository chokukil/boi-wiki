"""Profile-only projection and deterministic AnswerRequirement v2 builder."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .answer_contract_v2 import (
    AnswerGoalContract,
    AnswerPaginationPolicy,
    AnswerRequirementContractV2,
)
from .answer_quality import AnswerResultViewRequirement, DisplayFieldRequirement
from .semantic_profile_loader import SemanticContextBundle


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


class AnswerRequirementBuildError(ValueError):
    """The active semantic closure cannot support the requested answer."""


_DENIED_PROFILE_KEYS = {
    "golden",
    "golden_count",
    "golden_result",
    "golden_rows",
    "golden_sql",
    "raw_row",
    "raw_rows",
    "raw_sql",
    "registered_query_spec",
    "result_rows",
    "rows",
    "sql",
    "query_spec",
    "query_spec_id",
}


def _assert_oracle_free(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in _DENIED_PROFILE_KEYS:
                raise AnswerRequirementBuildError(
                    "ANSWER_PROFILE_ORACLE_INPUT_FORBIDDEN"
                )
            _assert_oracle_free(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_oracle_free(child)


class AnswerDomainDisplayProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_ref: str
    label: str
    unit: str | None
    owner_ref: str
    value_type: str
    revision_digest: str
    evidence_resources: tuple[str, ...]


class AnswerPhysicalMappingProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_ref: str
    mapping_ref: str
    data_type: str
    physical_locator_digest: str
    schema_snapshot_digest: str
    revision_digest: str
    evidence_resources: tuple[str, ...]


class AnswerProfileClosure(BaseModel):
    """The only active-profile data made visible to the answer builder."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-profile-closure/v1"] = (
        "boi-answer-profile-closure/v1"
    )
    active_release_digest: str
    source_bundle_digest: str
    catalog_snapshot_digest: str
    schema_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    acl_projection_digest: str
    domain_displays: tuple[AnswerDomainDisplayProjection, ...]
    physical_mappings: tuple[AnswerPhysicalMappingProjection, ...]
    query_payloads_exposed: Literal[0] = 0
    raw_sql_exposed: Literal[0] = 0
    result_rows_exposed: Literal[0] = 0
    golden_oracle_exposed: Literal[0] = 0
    closure_digest: str

    @model_validator(mode="after")
    def validate_closure(self) -> "AnswerProfileClosure":
        digest_fields = (
            self.active_release_digest,
            self.source_bundle_digest,
            self.catalog_snapshot_digest,
            self.schema_digest,
            self.domain_profile_digest,
            self.mapping_profile_digest,
            self.query_profile_digest,
            self.acl_projection_digest,
            self.closure_digest,
        )
        if not all(_is_digest(value) for value in digest_fields):
            raise ValueError("ANSWER_PROFILE_CLOSURE_DIGEST_INVALID")
        display_refs = tuple(item.property_ref for item in self.domain_displays)
        mapping_refs = tuple(item.property_ref for item in self.physical_mappings)
        if len(display_refs) != len(set(display_refs)):
            raise ValueError("ANSWER_DOMAIN_DISPLAY_DUPLICATE")
        if len(mapping_refs) != len(set(mapping_refs)):
            raise ValueError("ANSWER_PHYSICAL_MAPPING_DUPLICATE")
        unsigned = self.model_dump(mode="json", exclude={"closure_digest"})
        if self.closure_digest != _digest(unsigned):
            raise ValueError("ANSWER_PROFILE_CLOSURE_DIGEST_MISMATCH")
        return self


class AnswerResultSetProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    display_name: str
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    object_ref: str
    exact_grain: tuple[str, ...] = Field(min_length=1)
    property_refs: tuple[str, ...] = Field(min_length=1)
    parent_result_set_id: str | None = None
    ordering: tuple[str, ...]

    @model_validator(mode="after")
    def validate_projection(self) -> "AnswerResultSetProjection":
        for values, reason in (
            (self.exact_grain, "ANSWER_PLAN_GRAIN_DUPLICATE"),
            (self.property_refs, "ANSWER_PLAN_PROPERTY_DUPLICATE"),
            (self.ordering, "ANSWER_PLAN_ORDERING_DUPLICATE"),
        ):
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(reason)
        if not set(self.exact_grain) <= set(self.property_refs):
            raise ValueError("ANSWER_PLAN_GRAIN_NOT_PROJECTED")
        if not set(self.ordering) <= set(self.property_refs):
            raise ValueError("ANSWER_PLAN_ORDER_NOT_PROJECTED")
        return self


class AnswerPlanProjection(BaseModel):
    """Semantic plan projection with no physical SQL, rows, or oracle fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-plan-projection/v1"] = (
        "boi-answer-plan-projection/v1"
    )
    semantic_plan_digest: str
    result_shape_digest: str
    root_object: str
    relationship_refs: tuple[str, ...]
    result_sets: tuple[AnswerResultSetProjection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan_projection(self) -> "AnswerPlanProjection":
        if not _is_digest(self.semantic_plan_digest) or not _is_digest(
            self.result_shape_digest
        ):
            raise ValueError("ANSWER_PLAN_PROJECTION_DIGEST_INVALID")
        result_ids = tuple(item.result_set_id for item in self.result_sets)
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("ANSWER_PLAN_RESULT_SET_DUPLICATE")
        if len(self.relationship_refs) != len(set(self.relationship_refs)):
            raise ValueError("ANSWER_PLAN_RELATIONSHIP_DUPLICATE")
        known = set(result_ids)
        if any(
            item.parent_result_set_id is not None
            and item.parent_result_set_id not in known
            for item in self.result_sets
        ):
            raise ValueError("ANSWER_PLAN_PARENT_RESULT_MISSING")
        return self


def project_answer_profile_closure(bundle: SemanticContextBundle) -> AnswerProfileClosure:
    """Project only display/mapping facts; QuerySpec payloads are not copied."""

    if bundle.body_bytes_exposed_to_context != 0:
        raise AnswerRequirementBuildError("ANSWER_PROFILE_BODY_BYTES_FORBIDDEN")
    displays: list[AnswerDomainDisplayProjection] = []
    for entry in bundle.domain_entries:
        _assert_oracle_free(entry.payload)
        if entry.payload.get("kind") != "PropertyDefinition":
            continue
        unit_contract = entry.payload.get("unit_contract") or {}
        unit = (
            str(unit_contract["unit"])
            if unit_contract.get("applicability") == "measurement"
            and unit_contract.get("unit") is not None
            else None
        )
        displays.append(
            AnswerDomainDisplayProjection(
                property_ref=entry.entry_id,
                label=str(entry.payload.get("name") or entry.entry_id),
                unit=unit,
                owner_ref=str(entry.payload.get("owner_ref") or ""),
                value_type=str(entry.payload.get("value_type") or ""),
                revision_digest=entry.revision_digest,
                evidence_resources=entry.evidence_resources,
            )
        )
    mappings: list[AnswerPhysicalMappingProjection] = []
    for entry in bundle.mapping_entries:
        _assert_oracle_free(entry.payload)
        if entry.availability != "bound" or entry.physical is None:
            continue
        locator = entry.physical.model_dump(mode="json")
        mappings.append(
            AnswerPhysicalMappingProjection(
                property_ref=str(entry.payload["domain_ref"]),
                mapping_ref=str(entry.payload["mapping_id"]),
                data_type=str(entry.payload.get("data_type") or ""),
                physical_locator_digest=_digest(locator),
                schema_snapshot_digest=str(entry.payload["schema_snapshot_digest"]),
                revision_digest=entry.revision_digest,
                evidence_resources=entry.evidence_resources,
            )
        )
    base = {
        "schema_name": "boi-answer-profile-closure/v1",
        "active_release_digest": bundle.active_release_digest,
        "source_bundle_digest": bundle.bundle_digest,
        "catalog_snapshot_digest": bundle.catalog_snapshot_digest,
        "schema_digest": bundle.schema_digest,
        "domain_profile_digest": bundle.domain_profile_digest,
        "mapping_profile_digest": bundle.mapping_profile_digest,
        "query_profile_digest": bundle.query_profile_digest,
        "acl_projection_digest": bundle.acl_projection_digest,
        "domain_displays": [item.model_dump(mode="json") for item in displays],
        "physical_mappings": [item.model_dump(mode="json") for item in mappings],
        "query_payloads_exposed": 0,
        "raw_sql_exposed": 0,
        "result_rows_exposed": 0,
        "golden_oracle_exposed": 0,
    }
    return AnswerProfileClosure.model_validate({**base, "closure_digest": _digest(base)})


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


class GovernedAnswerRequirementBuilder:
    """Build v2 requirements from a sealed semantic-only dependency set."""

    def build(
        self,
        *,
        goal: AnswerGoalContract,
        profile_closure: AnswerProfileClosure,
        plan: AnswerPlanProjection,
    ) -> AnswerRequirementContractV2:
        if goal.active_release_digest != profile_closure.active_release_digest:
            raise AnswerRequirementBuildError("ANSWER_ACTIVE_RELEASE_MISMATCH")
        if goal.profile_closure_digest != profile_closure.closure_digest:
            raise AnswerRequirementBuildError("ANSWER_PROFILE_CLOSURE_MISMATCH")
        if goal.acl_policy_digest != profile_closure.acl_projection_digest:
            raise AnswerRequirementBuildError("ANSWER_ACL_PROJECTION_MISMATCH")
        if goal.root_object != plan.root_object:
            raise AnswerRequirementBuildError("ANSWER_ROOT_OBJECT_MISMATCH")

        result_objects = {plan.root_object, *(item.object_ref for item in plan.result_sets)}
        projected_properties = {
            property_ref
            for result_set in plan.result_sets
            for property_ref in result_set.property_refs
        }
        if not set(goal.requested_objects) <= result_objects:
            raise AnswerRequirementBuildError("ANSWER_REQUEST_NOT_PROJECTED")
        if not set(goal.requested_properties) <= projected_properties:
            raise AnswerRequirementBuildError("ANSWER_REQUEST_NOT_PROJECTED")
        if not set(goal.requested_facets) <= projected_properties:
            raise AnswerRequirementBuildError("ANSWER_FACET_NOT_PROJECTED")
        if not set(goal.requested_relations) <= set(plan.relationship_refs):
            raise AnswerRequirementBuildError("ANSWER_RELATION_NOT_PROJECTED")
        if goal.direct_summary is not None:
            result_set_ids = {item.result_set_id for item in plan.result_sets}
            summary_result_ids = {
                goal.direct_summary.root_result_set_id,
                *(
                    (goal.direct_summary.primary_result_set_id,)
                    if goal.direct_summary.primary_result_set_id
                    else ()
                ),
                *(
                    (goal.direct_summary.secondary_result_set_id,)
                    if goal.direct_summary.secondary_result_set_id
                    else ()
                ),
            }
            if not summary_result_ids <= result_set_ids:
                raise AnswerRequirementBuildError(
                    "ANSWER_DIRECT_SUMMARY_RESULT_NOT_PROJECTED"
                )
            if (
                goal.direct_summary.distinct_field_ref
                and goal.direct_summary.distinct_field_ref
                not in projected_properties
            ):
                raise AnswerRequirementBuildError(
                    "ANSWER_DIRECT_SUMMARY_FIELD_NOT_PROJECTED"
                )

        displays = {item.property_ref: item for item in profile_closure.domain_displays}
        mappings = {item.property_ref: item for item in profile_closure.physical_mappings}
        semantic_dependencies = projected_properties | {
            item.field_ref for item in (*goal.ordering, *goal.latest_tie_break)
        }
        if not semantic_dependencies <= set(displays):
            raise AnswerRequirementBuildError("ANSWER_DISPLAY_PROFILE_UNRESOLVED")
        if not semantic_dependencies <= set(mappings):
            raise AnswerRequirementBuildError("ANSWER_MAPPING_PROFILE_UNRESOLVED")

        ordered_properties = _ordered_unique(
            property_ref
            for result_set in plan.result_sets
            for property_ref in result_set.property_refs
        )
        display_fields = tuple(
            DisplayFieldRequirement(
                field_ref=property_ref,
                label=displays[property_ref].label,
                unit=displays[property_ref].unit,
            )
            for property_ref in ordered_properties
        )
        views = tuple(
            AnswerResultViewRequirement(
                result_set_id=item.result_set_id,
                display_name=item.display_name,
                parent_result_set_id=item.parent_result_set_id,
                shape=item.shape,
                exact_grain=item.exact_grain,
                ordering=item.ordering,
            )
            for item in plan.result_sets
        )
        selected_mappings = [
            mappings[property_ref].model_dump(mode="json")
            for property_ref in sorted(semantic_dependencies)
        ]
        mapping_projection_digest = _digest(selected_mappings)
        display_policy_digest = _digest(
            {
                "answer_mode": goal.answer_mode,
                "fields": [item.model_dump(mode="json") for item in display_fields],
                "views": [item.model_dump(mode="json") for item in views],
                "completeness": goal.completeness_policy,
                "preview_page_size": goal.preview_page_size,
                "quality": list(goal.required_quality_disclosures),
                "direct_summary": (
                    goal.direct_summary.model_dump(mode="json")
                    if goal.direct_summary is not None
                    else None
                ),
            }
        )
        requested_refs = _ordered_unique(
            (
                *goal.requested_objects,
                *goal.requested_properties,
                *goal.requested_metrics,
                *goal.requested_relations,
                *goal.requested_facets,
            )
        )
        aggregation_semantics = (
            "; ".join(
                f"{item.reducer}({item.input_ref or item.metric_ref})->{item.metric_ref}"
                for item in goal.aggregations
            )
            or None
        )
        presentation = {
            "object_set": "table",
            "sequence": "list",
            "latest": "table",
            "nested": "nested_collection",
            "aggregate": "aggregate",
            "relation": "relation",
        }[goal.answer_mode]
        return AnswerRequirementContractV2(
            question_digest=goal.question_digest,
            semantic_plan_digest=plan.semantic_plan_digest,
            result_shape_digest=plan.result_shape_digest,
            requested_refs=requested_refs,
            required_display_fields=display_fields,
            exact_grain=goal.exact_grain,
            grouping_semantics=goal.grouping_semantics,
            nesting_semantics=goal.nesting_semantics,
            aggregation_semantics=aggregation_semantics,
            latest_semantics=goal.latest_semantics,
            latest_ordering=tuple(
                f"{item.field_ref} {item.direction}" for item in goal.latest_tie_break
            ),
            unit_semantics=goal.unit_semantics,
            ordering=tuple(item.field_ref for item in goal.ordering),
            limit=goal.preview_page_size,
            completeness_policy=goal.completeness_policy,
            required_quality_disclosures=goal.required_quality_disclosures,
            preferred_presentation=presentation,
            result_view_requirements=views,
            acl_policy_digest=goal.acl_policy_digest,
            answer_goal_digest=goal.contract_digest,
            resolved_intent_digest=goal.resolved_intent_digest,
            active_release_digest=goal.active_release_digest,
            profile_closure_digest=goal.profile_closure_digest,
            display_policy_digest=display_policy_digest,
            mapping_projection_digest=mapping_projection_digest,
            pagination_policy=AnswerPaginationPolicy(
                mode="ANSWER_SCOPED_CURSOR" if goal.pagination_required else "NONE",
                page_size=goal.preview_page_size if goal.pagination_required else None,
                full_access_required=goal.pagination_required,
            ),
            direct_summary=goal.direct_summary,
        )


__all__ = [
    "AnswerPlanProjection",
    "AnswerProfileClosure",
    "AnswerRequirementBuildError",
    "GovernedAnswerRequirementBuilder",
    "project_answer_profile_closure",
]
