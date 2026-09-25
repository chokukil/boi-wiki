"""Deterministic semantic result-shape synthesis with no physical identifiers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer
from .snapshot_result_paging import SnapshotPagingPolicy
from .latest_selection_contract import BoundLatestSelection, bind_latest_selection
from .filter_expression import FilterExpression,validate_filter_expression

from .cardinality_profile_binding import ProfileBoundShapeSelection
from .cardinality_query_shape import RelationshipContract
from .semantic_authority import (
    SemanticAuthorityFields,
    require_same_semantic_authority,
    semantic_authority_values,
)
from .semantic_query_planner import SemanticPlanningContext


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _slug(value: str) -> str:
    value = value.split(":", 1)[-1]
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").casefold()
    if not value:
        raise ValueError("SEMANTIC_OUTPUT_NAME_EMPTY")
    return value


class SemanticProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_ref: str
    output_name: str


class SemanticAggregation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reducer: Literal["count_rows", "count", "count_distinct", "sum", "average", "min", "max"]
    target_ref: str
    output_name: str


class SemanticParameterSpec(BaseModel):
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


class SemanticFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_ref: str
    operator: Literal[
        "eq", "neq", "gt", "gte", "lt", "lte", "in", "is_null", "not_null"
    ]
    parameter_name: str | None


class SemanticExistenceHop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_object_ref: str
    child_object_ref: str
    parent_property_ref: str
    child_property_ref: str
    relationship_ref: str


class SemanticExistenceConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filter_object_ref: str
    hops: tuple[SemanticExistenceHop, ...] = Field(min_length=1)
    filters: tuple[SemanticFilter, ...] = Field(min_length=1)
    polarity: Literal["PRESENT", "ABSENT"] = "PRESENT"

    @model_serializer(mode="wrap")
    def preserve_positive_existence_shape(self, handler):
        value=handler(self)
        if self.polarity == "PRESENT":value.pop("polarity",None)
        return value


class SemanticParentLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_result_set_id: str
    parent_property_refs: tuple[str, ...]
    child_property_refs: tuple[str, ...]
    relationship_ref: str


class SemanticRelationshipTraversal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_ref: str
    parent_object_ref: str
    child_object_ref: str


class SemanticLatest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partition_by: tuple[str, ...] = Field(min_length=1)
    ordering: tuple[str, ...] = Field(min_length=2)
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = Field(min_length=2)
    selection_contract: BoundLatestSelection | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_latest(self, handler):
        value = handler(self)
        if self.selection_contract is None:
            value.pop("selection_contract", None)
        return value

    @model_validator(mode="after")
    def validate_ordering(self) -> "SemanticLatest":
        if len(self.ordering) != len(self.ordering_directions):
            raise ValueError("LATEST_ORDER_DIRECTION_ARITY_MISMATCH")
        return self


class SemanticResultSetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    role: Literal["ROOT", "CHILD", "RELATIONSHIP", "AGGREGATE", "SCALAR"]
    object_ref: str
    projections: tuple[SemanticProjection, ...]
    aggregations: tuple[SemanticAggregation, ...] = ()
    filters: tuple[SemanticFilter, ...] = ()
    filter_expression: FilterExpression | None = Field(default=None,exclude_if=lambda v:v is None)
    existence_constraints: tuple[SemanticExistenceConstraint, ...] = ()
    exact_grain: tuple[str, ...]
    parent_link: SemanticParentLink | None
    latest: SemanticLatest | None = None
    ordering: tuple[str, ...]
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED", "QUALITY_SIDECAR_REQUIRED", "PROVISIONAL_SNAPSHOT"
    ]
    coverage_semantics: Literal[
        "SPARSE_ONLY", "ROOT_COMPLETE_ZERO_FILL", "UNKNOWN_NOT_ZERO"
    ] = "SPARSE_ONLY"
    result_row_limit: int = Field(gt=0, le=100_000)
    ordering_directions: tuple[Literal["ASC", "DESC"], ...] = ()
    row_limit_policy: Literal["FAIL_IF_EXCEEDED", "TRUNCATE", "SNAPSHOT_PAGED"] = "FAIL_IF_EXCEEDED"
    paging_policy: SnapshotPagingPolicy | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_semantic_plan(self, handler):
        value = handler(self)
        if self.paging_policy is None:
            value.pop("paging_policy", None)
        return value

    @model_validator(mode="after")
    def validate_semantic_plan(self) -> "SemanticResultSetPlan":
        if self.filter_expression is not None:
            validate_filter_expression(self.filter_expression,len(self.filters))
            if self.latest is not None:raise ValueError('NESTED_FILTER_LATEST_PLACEMENT_UNRESOLVED')
        if self.role == "SCALAR":
            if (self.projections or self.exact_grain or self.ordering or self.ordering_directions
                or self.parent_link or self.latest or self.existence_constraints
                or self.paging_policy or self.coverage_semantics != "SPARSE_ONLY"
                or self.result_row_limit != 1 or self.row_limit_policy != "FAIL_IF_EXCEEDED"
                or not self.aggregations):
                raise ValueError("SEMANTIC_SCALAR_CONTRACT_INVALID")
            return self
        property_refs = {item.property_ref for item in self.projections}
        if not self.projections or not set(self.exact_grain) <= property_refs:
            raise ValueError("SEMANTIC_GRAIN_NOT_PROJECTED")
        if not set(self.ordering) <= property_refs:
            raise ValueError("SEMANTIC_ORDER_NOT_PROJECTED")
        if self.ordering_directions and len(self.ordering_directions) != len(
            self.ordering
        ):
            raise ValueError("SEMANTIC_ORDER_DIRECTION_ARITY_MISMATCH")
        if self.role == "ROOT" and self.parent_link is not None:
            raise ValueError("SEMANTIC_ROOT_PARENT_FORBIDDEN")
        if self.role != "ROOT" and self.existence_constraints:
            raise ValueError("SEMANTIC_EXISTENCE_CONSTRAINT_ROOT_ONLY")
        if self.role not in {"ROOT", "AGGREGATE"} and self.parent_link is None:
            raise ValueError("SEMANTIC_NON_ROOT_PARENT_REQUIRED")
        if self.role == "AGGREGATE" and not self.aggregations:
            raise ValueError("SEMANTIC_AGGREGATION_REQUIRED")
        if self.latest is not None:
            if self.role == "AGGREGATE" or self.aggregations:
                raise ValueError("SEMANTIC_LATEST_AGGREGATION_CONFLICT")
            latest_refs = {*self.latest.partition_by, *self.latest.ordering}
            if not latest_refs <= property_refs:
                raise ValueError("SEMANTIC_LATEST_PROPERTY_NOT_PROJECTED")
            if tuple(self.exact_grain) != tuple(self.latest.partition_by):
                raise ValueError("SEMANTIC_LATEST_GRAIN_MISMATCH")
        return self


class GenericLogicalResultShapePlan(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal[
        "boi-generic-result-shape-plan/v1",
        "boi-generic-result-shape-plan/v2",
        "boi-generic-result-shape-plan/v3",
        "boi-generic-result-shape-plan/v4",
    ] = (
        "boi-generic-result-shape-plan/v1"
    )
    shape_selection_receipt_digest: str
    resolved_intent_digest: str
    active_release_digest: str | None
    result_sets: tuple[SemanticResultSetPlan, ...]
    parameter_specs: tuple[SemanticParameterSpec, ...]
    source_qualifier_parameters: dict = Field(default_factory=dict, exclude_if=lambda v: not v)
    source_qualifier_receipt: dict | None = Field(default=None, exclude_if=lambda v: v is None)
    plan_digest: str

    @model_validator(mode="after")
    def authority_matches_revision(self):
        reviewed = self.reviewed_definition_authority is not None
        if reviewed != (self.schema_name in {
            "boi-generic-result-shape-plan/v3",
            "boi-generic-result-shape-plan/v4",
        }):
            raise ValueError("GENERIC_SHAPE_PLAN_AUTHORITY_REVISION_MISMATCH")
        paging = any(item.paging_policy for item in self.result_sets)
        if paging != (self.schema_name in {
            "boi-generic-result-shape-plan/v2",
            "boi-generic-result-shape-plan/v4",
        }):
            raise ValueError("GENERIC_SHAPE_PLAN_PAGING_REVISION_MISMATCH")
        return self


class GenericResultShapePlanner:
    """Create logical result sets from resolved ontology contracts only."""

    @staticmethod
    def _property_output_name(property_ref: str) -> str:
        return _slug(property_ref)

    @staticmethod
    def _result_set_id(object_ref: str, role: str, *, suffix: str = "") -> str:
        tail = f":{suffix}" if suffix else ""
        return f"result:{_slug(object_ref)}:{role.casefold()}{tail}"

    @staticmethod
    def order_relationship_tree(
        root_object_ref: str,
        relationships: tuple[RelationshipContract, ...],
    ) -> tuple[SemanticRelationshipTraversal, ...]:
        reached = {root_object_ref}
        pending = {item.contract_id: item for item in relationships}
        if len(pending) != len(relationships):
            raise ValueError("RELATIONSHIP_TREE_DUPLICATE")
        traversals: list[SemanticRelationshipTraversal] = []
        while pending:
            progressed = False
            for relationship_ref in sorted(tuple(pending)):
                relationship = pending[relationship_ref]
                left_reached = relationship.left_endpoint_ref in reached
                right_reached = relationship.right_endpoint_ref in reached
                if left_reached == right_reached:
                    continue
                if left_reached:
                    if relationship.direction not in {
                        "left_to_right",
                        "bidirectional",
                    }:
                        raise ValueError("RELATIONSHIP_TREE_DIRECTION_INVALID")
                    parent = relationship.left_endpoint_ref
                    child = relationship.right_endpoint_ref
                else:
                    if relationship.direction not in {
                        "right_to_left",
                        "bidirectional",
                    }:
                        raise ValueError("RELATIONSHIP_TREE_DIRECTION_INVALID")
                    parent = relationship.right_endpoint_ref
                    child = relationship.left_endpoint_ref
                traversals.append(
                    SemanticRelationshipTraversal(
                        relationship_ref=relationship_ref,
                        parent_object_ref=parent,
                        child_object_ref=child,
                    )
                )
                reached.add(child)
                pending.pop(relationship_ref)
                progressed = True
            if not progressed:
                raise ValueError("RELATIONSHIP_TREE_DISCONNECTED_OR_CYCLIC")
        return tuple(traversals)

    def plan(
        self,
        context: SemanticPlanningContext,
        *,
        shape_selection: ProfileBoundShapeSelection,
    ) -> GenericLogicalResultShapePlan:
        reviewed_authority = getattr(context, 'reviewed_definition_authority', None)
        profile_contracts = getattr(shape_selection, 'profile_contracts', None)
        if profile_contracts is not None:
            require_same_semantic_authority(context, profile_contracts)
        elif reviewed_authority is not None:
            raise ValueError("SHAPE_SELECTION_SEMANTIC_AUTHORITY_MISSING")
        if (getattr(shape_selection, 'reviewed_definition_authority', None)
                != reviewed_authority):
            raise ValueError("SHAPE_SELECTION_SEMANTIC_AUTHORITY_MISMATCH")
        selected = shape_selection.solver_outcome.selected_shape
        if selected is None:
            raise ValueError("SELECTED_RESULT_SHAPE_MISSING")
        candidate = context.resolved_intent.candidate
        domains = {
            item.entry_id: item.payload for item in context.bundle.domain_entries
        }
        relationships = {
            item.contract_id: item
            for item in shape_selection.solver_outcome.bound_relationships
        }
        try:
            selected_relationships = tuple(
                relationships[item] for item in selected.relationship_refs
            )
        except KeyError as error:
            raise ValueError("SELECTED_RELATIONSHIP_NOT_BOUND") from error
        bag_mode = any(r.cardinality == "stored_row_association" for r in selected_relationships)
        if bag_mode and (len(selected_relationships)!=1 or selected.shape!="FlatRelation" or candidate.aggregations):
            raise ValueError("STORED_ROW_RESULT_SHAPE_UNSUPPORTED")
        traversals = self.order_relationship_tree(
            selected.root_object_ref, selected_relationships
        )
        relationship_keys_by_object: dict[str, list[str]] = {}
        for relationship in selected_relationships:
            relation_domain = domains.get(relationship.contract_id, {})
            left_values = relation_domain.get("left_property_refs") or (
                relation_domain.get("left_property_ref"),
            )
            right_values = relation_domain.get("right_property_refs") or (
                relation_domain.get("right_property_ref"),
            )
            if len(left_values) != 1 or len(right_values) != 1:
                raise ValueError("RELATIONSHIP_LOGICAL_KEY_ARITY_UNSUPPORTED")
            left_property = str(left_values[0] or "")
            right_property = str(right_values[0] or "")
            if not left_property or not right_property:
                raise ValueError("RELATIONSHIP_SEMANTIC_KEYS_REQUIRED")
            relationship_keys_by_object.setdefault(
                relationship.left_endpoint_ref, []
            ).append(left_property)
            relationship_keys_by_object.setdefault(
                relationship.right_endpoint_ref, []
            ).append(right_property)

        parameter_specs: list[SemanticParameterSpec] = []
        filters_by_object: dict[str, list[SemanticFilter]] = {}
        existence_filters_by_object: dict[str, list[SemanticFilter]] = {}
        absence_filters_by_object: dict[str, list[SemanticFilter]] = {}
        filter_expressions_by_object={}
        if candidate.filter_expression is not None:
            owners={str(domains.get(item.property_id,{}).get('owner_ref') or '') for item in candidate.filters}
            if (len(owners)!=1 or '' in owners or candidate.time_range is not None
                    or any((item.scope or 'COLLECTION_CONTENT') not in ('COLLECTION','COLLECTION_CONTENT') for item in candidate.filters)):
                raise ValueError('NESTED_FILTER_SCOPE_UNRESOLVED')
            # One collection retains the original filter order and indices.
            # Cross-collection/existence and time predicates need explicit
            # placement semantics; distributing OR/NOT would change meaning.
            filter_expressions_by_object[next(iter(owners))]=candidate.filter_expression
        for index, intent_filter in enumerate(candidate.filters):
            owner_ref = str(
                domains.get(intent_filter.property_id, {}).get("owner_ref") or ""
            )
            if not owner_ref:
                raise ValueError("FILTER_PROPERTY_OWNER_REQUIRED")
            value = intent_filter.value
            parameter_name: str | None = None
            if intent_filter.operator in {"is_null", "not_null"}:
                if value is not None:
                    raise ValueError("NULL_FILTER_VALUE_FORBIDDEN")
                parameter_type = ""
            else:
                parameter_name = f"filter_{index}"
            scalar_type = (
                "boolean"
                if isinstance(value, bool)
                else "integer"
                if isinstance(value, int)
                else "number"
                if isinstance(value, float)
                else "string"
                if isinstance(value, str)
                else ""
            )
            if (
                intent_filter.operator not in {"is_null", "not_null"}
                and isinstance(value, tuple)
                and value
            ):
                item_types = {
                    "boolean"
                    if isinstance(item, bool)
                    else "integer"
                    if isinstance(item, int)
                    else "number"
                    if isinstance(item, float)
                    else "string"
                    if isinstance(item, str)
                    else ""
                    for item in value
                }
                parameter_type = (
                    f"{next(iter(item_types))}_list"
                    if len(item_types) == 1 and "" not in item_types
                    else ""
                )
            elif intent_filter.operator not in {"is_null", "not_null"}:
                parameter_type = scalar_type
            if (
                intent_filter.operator not in {"is_null", "not_null"}
                and not parameter_type
            ):
                raise ValueError("FILTER_PARAMETER_TYPE_UNSUPPORTED")
            if parameter_name is not None:
                parameter_specs.append(
                    SemanticParameterSpec(name=parameter_name, type=parameter_type)
                )
            semantic_filter = SemanticFilter(
                property_ref=intent_filter.property_id,
                operator=intent_filter.operator,
                parameter_name=parameter_name,
            )
            filter_scope = intent_filter.scope or "COLLECTION_CONTENT"
            # The selected root is already the row whose existence is being
            # tested. Its predicate applies directly, with no relationship hop.
            if owner_ref == selected.root_object_ref or filter_scope in {
                "COLLECTION_CONTENT",
                "COLLECTION",
                "ROOT_AND_COLLECTION",
                "ROOT_ABSENCE",
            }:
                filters_by_object.setdefault(owner_ref, []).append(semantic_filter)
            if (owner_ref != selected.root_object_ref
                    and filter_scope in {"ROOT_EXISTENCE", "ROOT_AND_COLLECTION"}):
                existence_filters_by_object.setdefault(owner_ref, []).append(
                    semantic_filter
                )
            if owner_ref != selected.root_object_ref and filter_scope == "ROOT_ABSENCE":
                absence_filters_by_object.setdefault(owner_ref, []).append(semantic_filter)
        if set(existence_filters_by_object) & set(absence_filters_by_object):
            raise ValueError('MIXED_RELATION_EXISTENCE_POLARITY_UNSUPPORTED')
        if absence_filters_by_object and selected.shape != 'NestedCollection':
            raise ValueError('ROOT_ABSENCE_NESTED_RELATION_REQUIRED')
        if any(item.scope == 'ROOT_ABSENCE' and
                domains.get(item.property_id,{}).get('owner_ref')==selected.root_object_ref
                for item in candidate.filters):
            raise ValueError('ROOT_ABSENCE_REQUIRES_RELATED_PROPERTY')
        if candidate.time_range is not None:
            time_range = candidate.time_range
            owner_ref = str(
                domains.get(time_range.property_id, {}).get("owner_ref") or ""
            )
            if not owner_ref:
                raise ValueError("TIME_PROPERTY_OWNER_REQUIRED")
            parameter_specs.extend(
                (
                    SemanticParameterSpec(name="time_start", type="string"),
                    SemanticParameterSpec(name="time_end", type="string"),
                )
            )
            filters_by_object.setdefault(owner_ref, []).extend(
                (
                    SemanticFilter(
                        property_ref=time_range.property_id,
                        operator="gte"
                        if time_range.start_inclusive is not False
                        else "gt",
                        parameter_name="time_start",
                    ),
                    SemanticFilter(
                        property_ref=time_range.property_id,
                        operator="lte"
                        if time_range.end_inclusive is not False
                        else "lt",
                        parameter_name="time_end",
                    ),
                )
            )

        from .profile_relation_qualifiers import bind_required_relation_qualifiers
        source_filters, source_specs, source_values, source_receipt = bind_required_relation_qualifiers(
            bundle=context.bundle, root_ref=selected.root_object_ref, traversals=traversals,
            existence_owners=set(existence_filters_by_object) | set(absence_filters_by_object))
        if source_filters:
            if selected.root_object_ref in filter_expressions_by_object:
                raise ValueError('RELATION_QUALIFIER_BOOLEAN_PLACEMENT_UNSUPPORTED')
            filters_by_object.setdefault(selected.root_object_ref, []).extend(
                SemanticFilter.model_validate(item) for item in source_filters)
            parameter_specs.extend(SemanticParameterSpec.model_validate(item) for item in source_specs)

        def identity(object_ref: str) -> str:
            value = str(domains.get(object_ref, {}).get("identity_property_ref") or "")
            if not value:
                raise ValueError("OBJECT_IDENTITY_PROPERTY_REQUIRED")
            return value

        def properties(object_ref: str) -> tuple[str, ...]:
            requested = tuple(
                property_ref
                for property_ref in candidate.property_ids
                if domains.get(property_ref, {}).get("owner_ref") == object_ref
            )
            identity_ref = identity(object_ref)
            return tuple(
                dict.fromkeys(
                    (
                        identity_ref,
                        *relationship_keys_by_object.get(object_ref, ()),
                        *requested,
                    )
                )
            )

        def projections(
            property_refs: tuple[str, ...],
        ) -> tuple[SemanticProjection, ...]:
            return tuple(
                SemanticProjection(
                    property_ref=item,
                    output_name=self._property_output_name(item),
                )
                for item in property_refs
            )

        def latest_for(object_ref: str) -> SemanticLatest | None:
            found = tuple(
                item
                for item in candidate.aggregations
                if item.operator == "latest" and item.scope_object_id == object_ref
            )
            if not found:
                return None
            latest = found[0]
            ordering = tuple(
                item
                for item in candidate.ordering
                if domains.get(item.property_id, {}).get("owner_ref") == object_ref
            )
            if candidate.intent_contract_version == "scoped-result-intent-v4" or domains.get(object_ref, {}).get("versioning"):
                bound = bind_latest_selection(
                    domain_entries=list(domains.values()),
                    contracts=[value for entry in context.bundle.query_entries for value in entry.payload.get("latest_selection_contracts", ())],
                    scope_object_ref=object_ref, partition_by=latest.partition_by,
                    recency_property_ref=latest.target_id,
                    ordering=tuple((item.property_id, item.direction) for item in ordering),
                )
                return SemanticLatest(partition_by=bound.partition_by, ordering=bound.ordering,
                    ordering_directions=bound.ordering_directions, selection_contract=bound)
            if (
                not ordering
                or ordering[0].property_id != latest.target_id
                or ordering[0].direction != "DESC"
            ):
                raise ValueError("LATEST_PRIMARY_ORDER_INVALID")
            if identity(object_ref) not in {item.property_id for item in ordering[1:]}:
                raise ValueError("LATEST_TIE_BREAK_NOT_UNIQUE")
            return SemanticLatest(
                partition_by=latest.partition_by,
                ordering=tuple(item.property_id for item in ordering),
                ordering_directions=tuple(item.direction for item in ordering),
            )

        root_ref = selected.root_object_ref
        if selected.shape == "ScalarAggregate":
            if (candidate.grain or candidate.dimensions or candidate.property_ids
                or candidate.metric_ids or candidate.ordering or len(candidate.aggregations) != 1
                or tuple(candidate.entity_ids) != (root_ref,) or existence_filters_by_object
                or absence_filters_by_object
                or set(filters_by_object) - {root_ref}):
                raise ValueError("SCALAR_INTENT_SCOPE_UNSUPPORTED")
            aggregation = candidate.aggregations[0]
            contract = selected.aggregation_semantics
            reducer = ("count_distinct" if aggregation.operator == "distinct_count"
                       or aggregation.operator == "count" and aggregation.distinct
                       else aggregation.operator)
            if (reducer != contract.reducer or aggregation.target_id != contract.target_ref
                or aggregation.partition_by or aggregation.group_by
                or aggregation.scope_object_id not in {None, root_ref}
                or reducer == "count_rows" and aggregation.distinct):
                raise ValueError("SCALAR_AGGREGATION_CONTRACT_MISMATCH")
            # The identity property anchors the physical table for count_rows;
            # its values are never counted, deduplicated, or asserted non-null.
            anchor = identity(root_ref) if reducer == "count_rows" else aggregation.target_id
            if domains.get(anchor, {}).get("owner_ref") != root_ref:
                raise ValueError("SCALAR_AGGREGATION_OWNER_MISMATCH")
            scalar = SemanticResultSetPlan(
                result_set_id=self._result_set_id(root_ref, "SCALAR"), role="SCALAR",
                object_ref=root_ref, projections=(), exact_grain=(), parent_link=None,
                ordering=(), aggregations=(SemanticAggregation(reducer=reducer,
                    target_ref=anchor, output_name="aggregate_value"),),
                filters=tuple(filters_by_object.get(root_ref, ())),
                filter_expression=filter_expressions_by_object.get(root_ref),
                completeness_policy=selected.completeness_policy, result_row_limit=1,
            )
            values = dict(shape_selection_receipt_digest=shape_selection.receipt_digest,
                resolved_intent_digest=context.resolved_intent.intent_digest,
                **semantic_authority_values(context if hasattr(context, 'active_release_digest') else context.bundle),
                result_sets=(scalar.model_dump(mode="json"),),
                parameter_specs=tuple(item.model_dump(mode="json") for item in parameter_specs))
            return GenericLogicalResultShapePlan(
                schema_name="boi-generic-result-shape-plan/v3" if reviewed_authority is not None
                    else "boi-generic-result-shape-plan/v1", **values, plan_digest=_digest(values))
        if selected.shape == "Aggregate":
            # A root grouped aggregate is a complete, bounded result in its own
            # right. Never reinterpret extra projected properties or a global
            # reducer as implicit grouping keys.
            if (traversals or tuple(candidate.entity_ids) != (root_ref,)
                or len(candidate.aggregations) != 1 or candidate.metric_ids
                or len(candidate.grain) != len(set(candidate.grain))
                or tuple(candidate.grain) != selected.exact_grain
                or tuple(candidate.dimensions) != selected.exact_grain
                or set(filters_by_object) - {root_ref}
                or existence_filters_by_object or absence_filters_by_object
                or candidate.quality_requests):
                raise ValueError("ROOT_AGGREGATE_SCOPE_UNSUPPORTED")
            aggregation = candidate.aggregations[0]
            contract = selected.aggregation_semantics
            reducer = ("count_distinct" if aggregation.operator == "distinct_count"
                or aggregation.operator == "count" and aggregation.distinct
                else aggregation.operator)
            if (contract is None or aggregation.scope_object_id != root_ref
                or aggregation.partition_by or tuple(aggregation.group_by) != selected.exact_grain
                or aggregation.target_id != contract.target_ref
                or reducer != contract.reducer):
                raise ValueError("ROOT_AGGREGATE_CONTRACT_MISMATCH")
            if (not selected.exact_grain
                or any(domains.get(ref, {}).get("owner_ref") != root_ref
                    for ref in selected.exact_grain)
                or (reducer == "count_rows" and aggregation.target_id != root_ref)
                or (reducer != "count_rows" and
                    domains.get(aggregation.target_id, {}).get("owner_ref") != root_ref)):
                raise ValueError("ROOT_AGGREGATE_OWNER_MISMATCH")
            permitted_properties = set(selected.exact_grain) | {
                aggregation.target_id, *(item.property_id for item in candidate.filters)}
            if candidate.time_range is not None:
                permitted_properties.add(candidate.time_range.property_id)
            if not set(candidate.property_ids) <= permitted_properties:
                raise ValueError("ROOT_AGGREGATE_EXTRA_PROJECTION_UNSUPPORTED")
            order_keys = tuple(selected.order_policy.keys)
            if (not selected.order_policy.deterministic
                or order_keys != selected.exact_grain
                or tuple(item.property_id for item in candidate.ordering) != order_keys
                or any(item.direction != "ASC" for item in candidate.ordering)):
                raise ValueError("ROOT_AGGREGATE_ORDER_MISMATCH")
            # Count rows through a reviewed identity column only as a table
            # anchor. The physical reducer remains COUNT(*), including rows
            # whose identity value is unexpectedly NULL.
            target_ref=identity(root_ref) if reducer == "count_rows" else aggregation.target_id
            grouped = SemanticResultSetPlan(
                result_set_id=self._result_set_id(root_ref, "AGGREGATE"),
                role="AGGREGATE", object_ref=root_ref,
                projections=projections(selected.exact_grain),
                aggregations=(SemanticAggregation(reducer=reducer,
                    target_ref=target_ref, output_name="aggregate_value"),),
                filters=tuple(filters_by_object.get(root_ref, ())),
                filter_expression=filter_expressions_by_object.get(root_ref),
                exact_grain=selected.exact_grain, parent_link=None,
                ordering=order_keys,
                ordering_directions=tuple("ASC" for _ in order_keys),
                completeness_policy=selected.completeness_policy,
                result_row_limit=min(candidate.limit, context.policy.max_result_rows,
                    selected.limit_policy.maximum_rows, 1000),
                row_limit_policy="FAIL_IF_EXCEEDED")
            values = dict(shape_selection_receipt_digest=shape_selection.receipt_digest,
                resolved_intent_digest=context.resolved_intent.intent_digest,
                **semantic_authority_values(context if hasattr(context, 'active_release_digest') else context.bundle),
                result_sets=(grouped.model_dump(mode="json"),),
                parameter_specs=tuple(item.model_dump(mode="json") for item in parameter_specs))
            return GenericLogicalResultShapePlan(
                schema_name="boi-generic-result-shape-plan/v3" if reviewed_authority is not None
                    else "boi-generic-result-shape-plan/v1", **values,
                plan_digest=_digest(values))
        root_identity = identity(root_ref)
        root_id = self._result_set_id(root_ref, "ROOT")
        root_latest = latest_for(root_ref)
        root_grain = (
            root_latest.partition_by if root_latest else
            tuple(ref for ref in selected.exact_grain if domains.get(ref,{}).get("owner_ref")==root_ref) if bag_mode else
            selected.exact_grain if selected.shape == "ObjectSet" else
            (root_identity,)
        )
        # A source identity declaration need not be the selected stored-row
        # grain. Preserve the reviewed tuple, including its order, without
        # asserting uniqueness or deduplicating equal rows.
        if selected.shape == "ObjectSet" and any(
            domains.get(ref, {}).get("owner_ref") != root_ref
            for ref in root_grain
        ):
            raise ValueError("OBJECTSET_GRAIN_OWNER_MISMATCH")
        root_properties = tuple(
            dict.fromkeys(
                (
                    *properties(root_ref),
                    *root_grain,
                    *(root_latest.partition_by if root_latest else ()),
                    *(root_latest.ordering if root_latest else ()),
                )
            )
        )
        root_requested_ordering = tuple(
            item
            for item in candidate.ordering
            if domains.get(item.property_id, {}).get("owner_ref") == root_ref
        )
        root_ordering = tuple(
            dict.fromkeys(
                (*[item.property_id for item in root_requested_ordering], root_identity)
            )
        )
        root_ordering_direction_by_ref = {
            item.property_id: item.direction for item in root_requested_ordering
        }
        result_sets: list[SemanticResultSetPlan] = [
            SemanticResultSetPlan(
                result_set_id=root_id,
                role="ROOT",
                object_ref=root_ref,
                projections=projections(root_properties),
                filters=tuple(filters_by_object.get(root_ref, ())),
                filter_expression=filter_expressions_by_object.get(root_ref),
                exact_grain=root_grain,
                parent_link=None,
                latest=root_latest,
                ordering=root_ordering,
                completeness_policy=(
                    selected.completeness_policy
                    if selected.shape == "ObjectSet" else "COMPLETE"
                ),
                result_row_limit=min(
                    candidate.limit, context.policy.max_result_rows, 1000
                ),
                ordering_directions=tuple(
                    root_ordering_direction_by_ref.get(item, "ASC")
                    for item in root_ordering
                ),
                row_limit_policy="TRUNCATE",
            )
        ]
        result_id_by_object = {root_ref: root_id}

        root_existence_constraints: list[SemanticExistenceConstraint] = []
        existence_hop_by_child: dict[str, SemanticExistenceHop] = {}
        for traversal in traversals:
            relationship_ref = traversal.relationship_ref
            relationship = relationships[relationship_ref]
            relation_domain = domains.get(relationship_ref, {})
            parent_ref = traversal.parent_object_ref
            child_ref = traversal.child_object_ref
            if relationship.left_endpoint_ref == parent_ref:
                parent_values = relation_domain.get("left_property_refs") or (
                    relation_domain.get("left_property_ref"),
                )
                child_values = relation_domain.get("right_property_refs") or (
                    relation_domain.get("right_property_ref"),
                )
            else:
                parent_values = relation_domain.get("right_property_refs") or (
                    relation_domain.get("right_property_ref"),
                )
                child_values = relation_domain.get("left_property_refs") or (
                    relation_domain.get("left_property_ref"),
                )
            parent_refs = tuple(str(item or "") for item in parent_values)
            child_refs = tuple(str(item or "") for item in child_values)
            if len(parent_refs) != 1 or len(child_refs) != 1:
                raise ValueError("RELATIONSHIP_LOGICAL_KEY_ARITY_UNSUPPORTED")
            parent_property, child_property = parent_refs[0], child_refs[0]
            if not parent_property or not child_property:
                raise ValueError("RELATIONSHIP_SEMANTIC_KEYS_REQUIRED")
            existence_hop_by_child[child_ref] = SemanticExistenceHop(
                parent_object_ref=parent_ref,
                child_object_ref=child_ref,
                parent_property_ref=parent_property,
                child_property_ref=child_property,
                relationship_ref=relationship_ref,
            )
            child_identity = identity(child_ref)
            child_latest = latest_for(child_ref)
            child_properties = tuple(
                dict.fromkeys(
                    (
                        child_identity,
                        child_property,
                        *properties(child_ref),
                        *(child_latest.partition_by if child_latest else ()),
                        *(child_latest.ordering if child_latest else ()),
                    )
                )
            )
            child_id = self._result_set_id(child_ref, "CHILD")
            parent_id = result_id_by_object.get(parent_ref)
            if parent_id is None:
                raise ValueError("RELATIONSHIP_PARENT_RESULT_NOT_EMITTED")
            parent_link = SemanticParentLink(
                parent_result_set_id=parent_id,
                parent_property_refs=(parent_property,),
                child_property_refs=(child_property,),
                relationship_ref=relationship_ref,
            )
            child_requested_ordering = tuple(
                item
                for item in candidate.ordering
                if domains.get(item.property_id, {}).get("owner_ref") == child_ref
            )
            child_ordering = tuple(
                dict.fromkeys(
                    (
                        child_property,
                        *[item.property_id for item in child_requested_ordering],
                        child_identity,
                    )
                )
            )
            child_ordering_direction_by_ref = {
                item.property_id: item.direction for item in child_requested_ordering
            }
            result_sets.append(
                SemanticResultSetPlan(
                    result_set_id=child_id,
                    role="CHILD",
                    object_ref=child_ref,
                    projections=projections(child_properties),
                    filters=tuple(filters_by_object.get(child_ref, ())),
                    filter_expression=filter_expressions_by_object.get(child_ref),
                    exact_grain=(
                        child_latest.partition_by if child_latest else
                        tuple(ref for ref in selected.exact_grain if domains.get(ref,{}).get("owner_ref")==child_ref) if bag_mode else (child_identity,)
                    ),
                    parent_link=parent_link,
                    latest=child_latest,
                    ordering=child_ordering,
                    completeness_policy=selected.completeness_policy,
                    result_row_limit=context.policy.max_result_rows,
                    ordering_directions=tuple(
                        child_ordering_direction_by_ref.get(item, "ASC")
                        for item in child_ordering
                    ),
                )
            )
            result_id_by_object[child_ref] = child_id

            omit_child = (candidate.intent_contract_version == 'scoped-result-intent-v4'
                          and child_ref not in (candidate.rowset_object_ids or ()))
            if (omit_child or candidate.intent_contract_version == 'scoped-aggregate-v3'
                and child_ref not in candidate.entity_ids
                and not any(domains.get(ref,{}).get('owner_ref')==child_ref for ref in candidate.property_ids)):
                # Reducer input is not an implicitly requested raw collection.
                # Descendant traversal through this object still requires a
                # separate bounded intermediate-key contract.
                if any(t.parent_object_ref==child_ref for t in traversals):
                    raise ValueError('AGGREGATE_INTERMEDIATE_KEY_CONTRACT_REQUIRED')
                result_sets.pop()
                result_id_by_object.pop(child_ref)

            child_aggregations = tuple(
                aggregation
                for aggregation in candidate.aggregations
                if (domains.get(aggregation.target_id, {}).get("owner_ref") == child_ref
                    or candidate.intent_contract_version in {'scoped-aggregate-v3', 'scoped-result-intent-v4'}
                    and aggregation.scope_object_id == child_ref)
                and aggregation.operator != "latest"
            )
            semantic_aggregations: list[SemanticAggregation] = []
            for aggregation in child_aggregations:
                target_ref = aggregation.target_id
                entity_count = domains.get(target_ref,{}).get('kind') == 'ObjectType'
                if entity_count:
                    if aggregation.operator not in {'count','distinct_count','count_rows'}:
                        raise ValueError('AGGREGATE_OBJECT_REDUCER_INVALID')
                    # For row count this property anchors the source table;
                    # its NULLs or repeated values do not change the count.
                    target_ref = identity(target_ref)
                reducer = (
                    "count_distinct"
                    if entity_count and aggregation.operator != "count_rows" or aggregation.operator == "distinct_count" or aggregation.operator == "count" and aggregation.distinct
                    else aggregation.operator
                )
                if reducer not in {
                    "count_rows",
                    "count",
                    "count_distinct",
                    "sum",
                    "average",
                    "min",
                    "max",
                }:
                    raise ValueError("AGGREGATION_OPERATOR_UNSUPPORTED")
                output_name = (
                    f"{_slug(child_ref).split('_')[-1]}_{aggregation.operator}"
                    if len(child_aggregations) == 1
                    else f"{_slug(aggregation.target_id)}_{aggregation.operator}"
                )
                semantic_aggregations.append(
                    SemanticAggregation(
                        reducer=reducer,
                        target_ref=target_ref,
                        output_name=output_name,
                    )
                )
            if semantic_aggregations:
                result_sets.append(
                    SemanticResultSetPlan(
                        result_set_id=self._result_set_id(child_ref, "AGGREGATE"),
                        role="AGGREGATE",
                        object_ref=child_ref,
                        projections=projections((child_property,)),
                        aggregations=tuple(semantic_aggregations),
                        filters=tuple(filters_by_object.get(child_ref, ())),
                        filter_expression=filter_expressions_by_object.get(child_ref),
                        exact_grain=(child_property,),
                        parent_link=parent_link,
                        ordering=(child_property,),
                        completeness_policy=selected.completeness_policy,
                        coverage_semantics="ROOT_COMPLETE_ZERO_FILL",
                        result_row_limit=min(context.policy.max_result_rows, 1000),
                    )
                )

        for owner_ref, owner_filters, polarity in (
            *((ref,filters,'PRESENT') for ref,filters in existence_filters_by_object.items()),
            *((ref,filters,'ABSENT') for ref,filters in absence_filters_by_object.items()),
        ):
            reverse_hops: list[SemanticExistenceHop] = []
            current_ref = owner_ref
            while current_ref != root_ref:
                hop = existence_hop_by_child.get(current_ref)
                if hop is None:
                    raise ValueError("FILTER_ROOT_EXISTENCE_PATH_NOT_UNIQUE")
                reverse_hops.append(hop)
                current_ref = hop.parent_object_ref
            root_existence_constraints.append(
                SemanticExistenceConstraint(
                    filter_object_ref=owner_ref,
                    hops=tuple(reversed(reverse_hops)),
                    filters=tuple(owner_filters),
                    polarity=polarity,
                )
            )
        result_sets[0] = result_sets[0].model_copy(
            update={"existence_constraints": tuple(root_existence_constraints)}
        )

        # Stored-row associations require a complete bounded pair population.
        # The later bag-mode block applies FAIL_IF_EXCEEDED to both endpoints;
        # inheriting generic snapshot paging here makes every such plan fail.
        if context.policy.paging_policy is not None and not bag_mode:
            parent_ids = {item.parent_link.parent_result_set_id for item in result_sets if item.parent_link}
            root_full_scope = (
                len(result_sets) == 1
                and result_sets[0].role == "ROOT"
                and result_sets[0].result_row_limit
                == min(context.policy.max_result_rows, 1000)
            )
            result_sets = [item.model_copy(update={
                "paging_policy": context.policy.paging_policy,
                "row_limit_policy": "SNAPSHOT_PAGED",
                "result_row_limit": min(context.policy.max_result_rows, 1000),
            }) if (
                item.result_set_id not in parent_ids
                and (item.role == "CHILD" or (
                    item.role == "ROOT" and root_full_scope
                ))
            ) else item for item in result_sets]
        if bag_mode:
            if len(result_sets)!=2 or any(item.latest or item.aggregations or item.paging_policy for item in result_sets):
                raise ValueError("STORED_ROW_EXECUTION_FEATURE_UNSUPPORTED")
            root, target = result_sets
            if target.existence_constraints or any(
                len(constraint.hops) != 1
                or constraint.hops[0].parent_object_ref != root.object_ref
                or constraint.hops[0].child_object_ref != target.object_ref
                or constraint.filter_object_ref != target.object_ref
                or target.parent_link is None
                or constraint.hops[0].relationship_ref != target.parent_link.relationship_ref
                for constraint in root.existence_constraints
            ):
                raise ValueError("STORED_ROW_EXISTENCE_SCOPE_UNSUPPORTED")
            if any(not item.exact_grain for item in result_sets):
                raise ValueError("STORED_ROW_ENDPOINT_GRAIN_REQUIRED")
            ceiling=selected.limit_policy.maximum_rows
            if ceiling is None:
                raise ValueError("STORED_ROW_OUTPUT_BUDGET_REQUIRED")
            result_sets=[item.model_copy(update={"row_limit_policy":"FAIL_IF_EXCEEDED",
                "result_row_limit":min(item.result_row_limit,ceiling),
                "completeness_policy":"COMPLETE"}) for item in result_sets]
        values = {
            "shape_selection_receipt_digest": shape_selection.receipt_digest,
            "resolved_intent_digest": context.resolved_intent.intent_digest,
            **semantic_authority_values(
                context if hasattr(context, 'active_release_digest')
                else context.bundle
            ),
            "result_sets": tuple(item.model_dump(mode="json") for item in result_sets),
            "parameter_specs": tuple(
                item.model_dump(mode="json") for item in parameter_specs
            ),
        }
        if source_receipt is not None:
            values.update(source_qualifier_receipt=source_receipt)
            if source_values:
                values.update(source_qualifier_parameters=source_values)
        return GenericLogicalResultShapePlan(
            schema_name=(
                "boi-generic-result-shape-plan/v4"
                if reviewed_authority is not None
                and any(item.paging_policy for item in result_sets)
                else "boi-generic-result-shape-plan/v3"
                if reviewed_authority is not None
                else "boi-generic-result-shape-plan/v2"
                if any(item.paging_policy for item in result_sets)
                else "boi-generic-result-shape-plan/v1"
            ),
            **values,
            plan_digest=_digest(values),
        )


__all__ = [
    "GenericLogicalResultShapePlan",
    "GenericResultShapePlanner",
    "SemanticAggregation",
    "SemanticFilter",
    "SemanticExistenceConstraint",
    "SemanticExistenceHop",
    "SemanticLatest",
    "SemanticParentLink",
    "SemanticParameterSpec",
    "SemanticProjection",
    "SemanticRelationshipTraversal",
    "SemanticResultSetPlan",
]
