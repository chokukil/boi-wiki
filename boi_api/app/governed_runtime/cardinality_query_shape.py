"""Strict contracts for cardinality-aware query shapes and quality evidence.

These models are profile/runtime boundaries, not a query-shape solver.  They
make relationship meaning, result grain, and observed data quality explicit so
that the C2 solver can choose a safe shape without treating cardinality itself
as a failure condition.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer
from .directional_quality_scope import DirectionalQualityScope
from .stored_row_association import StoredRowSemantics, StoredRowAssociationScope


Sha256Digest = str
Cardinality = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many", "stored_row_association"]
OrphanPolicy = Literal[
    "BLOCK", "INCLUDE_UNMATCHED", "EXCLUDE_WITH_DISCLOSURE", "QUARANTINE"
]


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


class PhysicalKeyContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    left_mapping_refs: tuple[str, ...]
    right_mapping_refs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_key_arity(self) -> "PhysicalKeyContract":
        if not self.left_mapping_refs or not self.right_mapping_refs:
            raise ValueError("PHYSICAL_KEYS_REQUIRED")
        if any(not item.strip() for item in (*self.left_mapping_refs, *self.right_mapping_refs)):
            raise ValueError("PHYSICAL_KEY_REF_INVALID")
        if len(self.left_mapping_refs) != len(self.right_mapping_refs):
            raise ValueError("PHYSICAL_KEY_ARITY_MISMATCH")
        return self


class TemporalValidityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["none", "point_in_time", "interval"]
    valid_from_property_ref: str | None
    valid_to_property_ref: str | None

    @model_validator(mode="after")
    def validate_temporal_fields(self) -> "TemporalValidityContract":
        if self.mode == "none" and (
            self.valid_from_property_ref is not None
            or self.valid_to_property_ref is not None
        ):
            raise ValueError("TEMPORAL_FIELDS_FORBIDDEN")
        if self.mode == "point_in_time" and not self.valid_from_property_ref:
            raise ValueError("TEMPORAL_POINT_PROPERTY_REQUIRED")
        if self.mode == "interval" and (
            not self.valid_from_property_ref or not self.valid_to_property_ref
        ):
            raise ValueError("TEMPORAL_INTERVAL_PROPERTIES_REQUIRED")
        return self


class FanoutContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_min: int = Field(ge=0)
    observed_p50: float = Field(ge=0)
    observed_p95: float = Field(ge=0)
    observed_max: int = Field(ge=0)
    budget_per_parent: int = Field(gt=0)
    budget_action: Literal["BLOCK", "TRUNCATE_WITH_DISCLOSURE", "REQUIRE_AGGREGATE"]

    @model_validator(mode="after")
    def validate_distribution(self) -> "FanoutContract":
        if not (
            self.observed_min
            <= self.observed_p50
            <= self.observed_p95
            <= self.observed_max
        ):
            raise ValueError("FANOUT_DISTRIBUTION_INVALID")
        return self


class RelationshipContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str
    left_endpoint_ref: str
    right_endpoint_ref: str
    direction: Literal["left_to_right", "right_to_left", "bidirectional"]
    semantic_name: str
    cardinality: Cardinality
    stored_row_semantics: StoredRowSemantics | None = Field(default=None, exclude_if=lambda v:v is None)
    optionality: Literal["required", "optional"]
    physical_keys: PhysicalKeyContract
    relationship_identity_ref: str | None
    temporal_validity: TemporalValidityContract
    null_policy: Literal["BLOCK", "ALLOW", "EXCLUDE_WITH_DISCLOSURE", "QUARANTINE"]
    orphan_policy: OrphanPolicy
    duplicate_policy: Literal[
        "BLOCK",
        "PRESERVE",
        "DISTINCT_BY_RELATIONSHIP_IDENTITY",
        "PRESERVE_DISTINCT_CHILDREN",
    ]
    fanout: FanoutContract
    acl_propagation: Literal["INTERSECTION", "ROOT_ONLY", "RELATIONSHIP_POLICY"]
    schema_snapshot_digest: Sha256Digest

    @field_validator(
        "contract_id",
        "left_endpoint_ref",
        "right_endpoint_ref",
        "semantic_name",
    )
    @classmethod
    def require_nonempty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NONEMPTY_STRING_REQUIRED")
        return value

    @field_validator("schema_snapshot_digest")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("SCHEMA_SNAPSHOT_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def validate_relationship_identity(self) -> "RelationshipContract":
        if self.cardinality == "stored_row_association":
            if (self.stored_row_semantics is None or self.acl_propagation != "INTERSECTION"
                or self.duplicate_policy != "PRESERVE" or self.orphan_policy != "INCLUDE_UNMATCHED"
                or self.null_policy != "ALLOW" or self.relationship_identity_ref is not None
                or self.temporal_validity.mode != "none" or self.fanout.budget_action != "BLOCK"
                or self.left_endpoint_ref == self.right_endpoint_ref):
                raise ValueError("STORED_ROW_ASSOCIATION_SEMANTICS_REQUIRED")
        elif self.stored_row_semantics is not None:
            raise ValueError("STORED_ROW_SEMANTICS_FORBIDDEN_FOR_ENTITY_RELATION")
        if self.cardinality == "many_to_many" and not (
            self.relationship_identity_ref and self.relationship_identity_ref.strip()
        ):
            raise ValueError("RELATIONSHIP_IDENTITY_REQUIRED")
        return self

    @property
    def contract_digest(self) -> str:
        return _digest(self)


class AggregationSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reducer: Literal["count_rows", "count", "count_distinct", "sum", "average", "min", "max", "ratio"]
    target_ref: str
    output_grain: tuple[str, ...]

    @model_validator(mode="after")
    def validate_output_grain(self) -> "AggregationSemantics":
        if not self.output_grain:
            raise ValueError("AGGREGATION_GRAIN_REQUIRED")
        return self


class ScalarAggregationSemantics(BaseModel):
    """Global aggregation has one output row, including on empty input.

    count_rows counts input records; count counts non-null property values.
    This does not assert that record count equals a business entity count.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["GLOBAL"]
    reducer: Literal["count_rows", "count", "count_distinct", "sum", "average", "min", "max"]
    target_ref: str = Field(min_length=1)
    output_grain: tuple[str, ...] = Field(max_length=0)


class OrderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    deterministic: bool
    keys: tuple[str, ...]

    @model_validator(mode="after")
    def validate_order_keys(self) -> "OrderPolicy":
        if self.deterministic and not self.keys:
            raise ValueError("ORDER_KEYS_REQUIRED")
        return self


class LimitPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["NONE", "EXPLICIT", "PER_PARENT"]
    maximum_rows: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_limit(self) -> "LimitPolicy":
        if self.kind == "NONE" and self.maximum_rows is not None:
            raise ValueError("LIMIT_VALUE_FORBIDDEN")
        if self.kind != "NONE" and self.maximum_rows is None:
            raise ValueError("LIMIT_VALUE_REQUIRED")
        return self


class ResultShapeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "ScalarAggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    root_object_ref: str
    exact_grain: tuple[str, ...]
    relationship_refs: tuple[str, ...]
    collection_semantics: str | None
    aggregation_semantics: AggregationSemantics | ScalarAggregationSemantics | None
    null_policy: Literal["BLOCK", "PRESERVE", "EXCLUDE_WITH_DISCLOSURE"]
    duplicate_policy: Literal[
        "BLOCK", "PRESERVE", "DISTINCT_BY_GRAIN", "APPROVED_FANOUT"
    ]
    order_policy: OrderPolicy
    limit_policy: LimitPolicy
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED", "QUALITY_SIDECAR_REQUIRED", "PROVISIONAL_SNAPSHOT"
    ]
    fanout_semantics: str | None

    @field_validator("contract_id", "root_object_ref")
    @classmethod
    def require_nonempty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NONEMPTY_STRING_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_shape_semantics(self) -> "ResultShapeContract":
        if not self.exact_grain and self.shape != "ScalarAggregate":
            raise ValueError("EXACT_GRAIN_REQUIRED")
        if len(self.exact_grain) != len(set(self.exact_grain)):
            raise ValueError("EXACT_GRAIN_DUPLICATE")
        if any(not item.strip() for item in self.exact_grain):
            raise ValueError("EXACT_GRAIN_INVALID")
        if len(self.relationship_refs) != len(set(self.relationship_refs)):
            raise ValueError("RELATIONSHIP_REF_DUPLICATE")
        if self.shape == "NestedCollection" and not (
            self.collection_semantics and self.collection_semantics.strip()
        ):
            raise ValueError("COLLECTION_SEMANTICS_REQUIRED")
        if self.shape == "ScalarAggregate":
            if self.exact_grain or not isinstance(self.aggregation_semantics, ScalarAggregationSemantics):
                raise ValueError("SCALAR_GLOBAL_AGGREGATION_REQUIRED")
            # Initial capability is one source object, without fanout or implicit
            # input-row elimination. Explicit predicates remain separate.
            if self.relationship_refs or self.collection_semantics or self.fanout_semantics:
                raise ValueError("SCALAR_RELATIONSHIP_CAPABILITY_UNAVAILABLE")
            if self.null_policy != "PRESERVE" or self.duplicate_policy != "PRESERVE":
                raise ValueError("SCALAR_INPUT_ROWS_MUST_BE_PRESERVED")
            if self.limit_policy.kind != "EXPLICIT" or self.limit_policy.maximum_rows != 1:
                raise ValueError("SCALAR_SINGLE_OUTPUT_ROW_REQUIRED")
            if self.order_policy.keys:
                raise ValueError("SCALAR_ORDER_KEYS_FORBIDDEN")
            if self.aggregation_semantics.reducer == "count_rows" and self.aggregation_semantics.target_ref != self.root_object_ref:
                raise ValueError("SCALAR_ROW_COUNT_ROOT_REQUIRED")
        if self.shape == "Aggregate" and not isinstance(self.aggregation_semantics, AggregationSemantics):
            raise ValueError("AGGREGATION_SEMANTICS_REQUIRED")
        if self.shape not in {"Aggregate", "ScalarAggregate"} and self.aggregation_semantics is not None:
            raise ValueError("AGGREGATION_SEMANTICS_FORBIDDEN")
        return self

    @property
    def contract_digest(self) -> str:
        return _digest(self)


class ObservedFanoutDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_min: int = Field(ge=0)
    observed_p50: float = Field(ge=0)
    observed_p95: float = Field(ge=0)
    observed_max: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_distribution(self) -> "ObservedFanoutDistribution":
        if not (
            self.observed_min
            <= self.observed_p50
            <= self.observed_p95
            <= self.observed_max
        ):
            raise ValueError("FANOUT_DISTRIBUTION_INVALID")
        return self


class DataQualityReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    relationship_contract_digest: Sha256Digest
    schema_snapshot_digest: Sha256Digest
    scanned_rows: int = Field(ge=0)
    matched_rows: int = Field(ge=0)
    unmatched_rows: int = Field(ge=0)
    null_fk_rows: int = Field(ge=0)
    orphan_rows: int = Field(ge=0)
    duplicate_key_rows: int = Field(ge=0)
    fanout_distribution: ObservedFanoutDistribution
    excluded_rows: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    applied_orphan_policy: OrphanPolicy
    evidence_ref: str
    evidence_digest: Sha256Digest
    directional_scope: DirectionalQualityScope | StoredRowAssociationScope | None = None

    @model_serializer(mode="wrap")
    def preserve_v1_history(self, handler):
        value = handler(self)
        if self.directional_scope is None:
            value.pop("directional_scope", None)
        return value

    @field_validator(
        "relationship_contract_digest", "schema_snapshot_digest", "evidence_digest"
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("DIGEST_INVALID")
        return value

    @field_validator("receipt_id", "evidence_ref")
    @classmethod
    def require_nonempty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NONEMPTY_STRING_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "DataQualityReceipt":
        if self.matched_rows + self.unmatched_rows != self.scanned_rows:
            raise ValueError("QUALITY_PARTITION_INVALID")
        if self.null_fk_rows + self.orphan_rows > self.unmatched_rows:
            raise ValueError("QUALITY_UNMATCHED_BREAKDOWN_INVALID")
        if self.excluded_rows > self.scanned_rows:
            raise ValueError("QUALITY_EXCLUDED_ROWS_INVALID")
        expected = self.matched_rows / self.scanned_rows if self.scanned_rows else 1.0
        if abs(self.coverage_ratio - expected) > 1e-12:
            raise ValueError("QUALITY_COVERAGE_INVALID")
        if self.directional_scope and self.evidence_digest != _digest(self.model_dump(mode="json",exclude={"evidence_digest"})):
            raise ValueError("QUALITY_DIRECTIONAL_EVIDENCE_DIGEST_INVALID")
        return self

    @property
    def receipt_digest(self) -> str:
        return _digest(self)


class ContractReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED"]
    reason_codes: tuple[str, ...]
    relationship_contract_digests: tuple[str, ...]
    result_shape_contract_digest: str
    quality_receipt_digests: tuple[str, ...]
    readiness_digest: str


def validate_directional_quality_closure(relationship, receipts):
    """v2 mapping requires exactly the orientations its relationship authorizes."""
    expected = ({relationship.left_endpoint_ref} if relationship.direction=='left_to_right' else
                {relationship.right_endpoint_ref} if relationship.direction=='right_to_left' else
                {relationship.left_endpoint_ref,relationship.right_endpoint_ref})
    roots=[]
    for receipt in receipts:
        scope=receipt.directional_scope
        if scope is None:
            raise ValueError('DIRECTIONAL_QUALITY_SCOPE_REQUIRED')
        roots.append(scope.root_endpoint_ref)
        if isinstance(scope, StoredRowAssociationScope):
            root_refs=(relationship.physical_keys.left_mapping_refs if scope.root_endpoint_ref==relationship.left_endpoint_ref else relationship.physical_keys.right_mapping_refs)
            target_refs=(relationship.physical_keys.right_mapping_refs if scope.root_endpoint_ref==relationship.left_endpoint_ref else relationship.physical_keys.left_mapping_refs)
            if (scope.budget_per_root!=relationship.fanout.budget_per_parent
                or scope.root_mapping_refs!=root_refs or scope.target_mapping_refs!=target_refs):
                raise ValueError("STORED_ROW_QUALITY_CONTRACT_MISMATCH")
        if (receipt.relationship_contract_digest!=relationship.contract_digest
            or receipt.schema_snapshot_digest!=relationship.schema_snapshot_digest
            or receipt.applied_orphan_policy!=relationship.orphan_policy
            or scope.acl_propagation!=relationship.acl_propagation
            or CardinalityAwareQueryShapeSolver._traversable_neighbor(scope.root_endpoint_ref,relationship)!=scope.target_endpoint_ref
            or CardinalityAwareQueryShapeSolver._effective_cardinality(scope.root_endpoint_ref,relationship)!=scope.effective_cardinality):
            raise ValueError('DIRECTIONAL_QUALITY_CONTRACT_MISMATCH')
    if len(roots)!=len(set(roots)) or set(roots)!=expected:
        raise ValueError('DIRECTIONAL_QUALITY_CLOSURE_INCOMPLETE_OR_DUPLICATE')
    if len({(q.directional_scope.source_snapshot_digest,q.directional_scope.mapping_closure_digest,
             q.directional_scope.evaluator_code_digest) for q in receipts})!=1:
        raise ValueError('DIRECTIONAL_QUALITY_SNAPSHOT_CLOSURE_MISMATCH')


class QueryShapeRequest(BaseModel):
    """Resolved semantic request presented to the deterministic C2 solver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root_object_ref: str
    relationship_refs: tuple[str, ...]
    target_object_refs: tuple[str, ...] = ()
    max_relationship_hops: int = Field(default=3, ge=1, le=5)
    requested_shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "ScalarAggregate",
        "FlatRelation",
        "AttestedComputation",
    ] | None
    exact_grain: tuple[str, ...]
    aggregation_reducer: Literal[
        "count_rows", "count", "count_distinct", "sum", "average", "min", "max", "ratio"
    ] | None
    prior_clarifications: int = Field(ge=0, le=1)
    active_schema_snapshot_digest: Sha256Digest

    @model_validator(mode="after")
    def validate_request(self) -> "QueryShapeRequest":
        if not self.root_object_ref.strip():
            raise ValueError("ROOT_OBJECT_REQUIRED")
        if len(self.relationship_refs) != len(set(self.relationship_refs)):
            raise ValueError("RELATIONSHIP_REF_DUPLICATE")
        if len(self.target_object_refs) != len(set(self.target_object_refs)):
            raise ValueError("TARGET_OBJECT_REF_DUPLICATE")
        if self.relationship_refs and self.target_object_refs:
            raise ValueError("EXPLICIT_AND_DISCOVERED_RELATIONSHIPS_CONFLICT")
        if len(self.exact_grain) != len(set(self.exact_grain)):
            raise ValueError("EXACT_GRAIN_DUPLICATE")
        if not _is_sha256(self.active_schema_snapshot_digest):
            raise ValueError("SCHEMA_SNAPSHOT_DIGEST_INVALID")
        return self

    @property
    def request_digest(self) -> str:
        return _digest(self)


class ShapeSolverOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"]
    reason_codes: tuple[str, ...]
    clarification_count: int
    selected_shape: ResultShapeContract | None
    bound_relationships: tuple[RelationshipContract, ...]
    quality_receipts: tuple[DataQualityReceipt, ...]
    request_digest: str
    contract_readiness_digest: str | None
    binding_digest: str
    outcome_digest: str


class CardinalityAwareQueryShapeSolver:
    """Bind a request to approved shape contracts without authoring policy.

    The solver selects only exact contracts supplied by an active Release.  It
    never invents a reducer, orphan policy, duplicate policy, or grain.
    """

    SOLVER_ID = "boi.cardinality-aware-query-shape-solver@0.1.0"

    @staticmethod
    def _outcome(
        *,
        status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"],
        reasons: tuple[str, ...],
        request: QueryShapeRequest,
        relationships: tuple[RelationshipContract, ...],
        quality_receipts: tuple[DataQualityReceipt, ...],
        selected_shape: ResultShapeContract | None = None,
        readiness_digest: str | None = None,
    ) -> ShapeSolverOutcome:
        binding_values = {
            "solver_id": CardinalityAwareQueryShapeSolver.SOLVER_ID,
            "request_digest": request.request_digest,
            "relationship_contract_digests": tuple(
                item.contract_digest for item in relationships
            ),
            "quality_receipt_digests": tuple(
                item.receipt_digest for item in quality_receipts
            ),
            "result_shape_contract_digest": (
                selected_shape.contract_digest if selected_shape else None
            ),
            "contract_readiness_digest": readiness_digest,
        }
        binding_digest = _digest(binding_values)
        values = {
            "status": status,
            "reason_codes": reasons,
            "clarification_count": 1 if status == "CLARIFICATION_REQUIRED" else 0,
            "selected_shape": selected_shape,
            "bound_relationships": relationships,
            "quality_receipts": quality_receipts,
            "request_digest": request.request_digest,
            "contract_readiness_digest": readiness_digest,
            "binding_digest": binding_digest,
        }
        digest_values = {
            **values,
            "selected_shape": (
                selected_shape.model_dump(mode="json") if selected_shape else None
            ),
            "bound_relationships": tuple(
                item.model_dump(mode="json") for item in relationships
            ),
            "quality_receipts": tuple(
                item.model_dump(mode="json") for item in quality_receipts
            ),
        }
        return ShapeSolverOutcome(**values, outcome_digest=_digest(digest_values))

    @staticmethod
    def _effective_cardinality(
        root_object_ref: str, relationship: RelationshipContract
    ) -> Cardinality:
        if root_object_ref == relationship.left_endpoint_ref:
            return relationship.cardinality
        return {
            "one_to_one": "one_to_one",
            "one_to_many": "many_to_one",
            "many_to_one": "one_to_many",
            "many_to_many": "many_to_many",
            "stored_row_association": "stored_row_association",
        }[relationship.cardinality]

    @classmethod
    def _default_shape(
        cls, root_object_ref: str, relationships: tuple[RelationshipContract, ...]
    ) -> str:
        parents = cls._traversal_parent_refs(root_object_ref, relationships)
        cardinalities = {
            cls._effective_cardinality(parents[item.contract_id], item)
            for item in relationships
        }
        if not relationships:
            return "ObjectSet"
        if "many_to_many" in cardinalities:
            return "LinkedObjectSet"
        if "one_to_many" in cardinalities:
            return "NestedCollection"
        return "FlatRelation"

    @staticmethod
    def _traversal_parent_refs(
        root_object_ref: str,
        relationships: tuple[RelationshipContract, ...],
    ) -> dict[str, str]:
        reached = {root_object_ref}
        pending = {item.contract_id: item for item in relationships}
        parents: dict[str, str] = {}
        while pending:
            progressed = False
            for relationship_ref in tuple(pending):
                relationship = pending[relationship_ref]
                left_reached = relationship.left_endpoint_ref in reached
                right_reached = relationship.right_endpoint_ref in reached
                if left_reached == right_reached:
                    continue
                parent = (
                    relationship.left_endpoint_ref
                    if left_reached
                    else relationship.right_endpoint_ref
                )
                child = (
                    relationship.right_endpoint_ref
                    if left_reached
                    else relationship.left_endpoint_ref
                )
                parents[relationship_ref] = parent
                reached.add(child)
                pending.pop(relationship_ref)
                progressed = True
            if not progressed:
                raise ValueError("RELATIONSHIP_TREE_DISCONNECTED_OR_CYCLIC")
        return parents

    @staticmethod
    def _traversable_neighbor(
        node: str, relationship: RelationshipContract
    ) -> str | None:
        if (
            node == relationship.left_endpoint_ref
            and relationship.direction in {"left_to_right", "bidirectional"}
        ):
            return relationship.right_endpoint_ref
        if (
            node == relationship.right_endpoint_ref
            and relationship.direction in {"right_to_left", "bidirectional"}
        ):
            return relationship.left_endpoint_ref
        return None

    def _discover_relationships(
        self,
        request: QueryShapeRequest,
        relationships: tuple[RelationshipContract, ...],
    ) -> tuple[
        Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"],
        tuple[str, ...],
        str | None,
    ]:
        selected: list[str] = []
        max_search_hops = max(len(relationships), request.max_relationship_hops)
        for target in request.target_object_refs:
            if target == request.root_object_ref:
                continue
            queue: list[tuple[str, tuple[str, ...], frozenset[str]]] = [
                (request.root_object_ref, (), frozenset({request.root_object_ref}))
            ]
            paths: list[tuple[str, ...]] = []
            shortest: int | None = None
            while queue:
                node, path, visited = queue.pop(0)
                if len(path) >= max_search_hops or (
                    shortest is not None and len(path) >= shortest
                ):
                    continue
                for relationship in sorted(
                    relationships, key=lambda item: item.contract_id
                ):
                    neighbor = self._traversable_neighbor(node, relationship)
                    if neighbor is None or neighbor in visited:
                        continue
                    candidate = (*path, relationship.contract_id)
                    if neighbor == target:
                        shortest = len(candidate) if shortest is None else shortest
                        if len(candidate) == shortest:
                            paths.append(candidate)
                    elif shortest is None or len(candidate) < shortest:
                        queue.append((neighbor, candidate, visited | {neighbor}))
            unique_paths = tuple(dict.fromkeys(paths))
            if not unique_paths:
                return "BLOCKED", (), "RELATIONSHIP_PATH_NOT_DECLARED"
            if shortest is not None and shortest > request.max_relationship_hops:
                return "BLOCKED", (), "RELATIONSHIP_HOP_BUDGET_EXCEEDED"
            if len(unique_paths) > 1:
                return (
                    "CLARIFICATION_REQUIRED"
                    if request.prior_clarifications == 0
                    else "BLOCKED",
                    (),
                    "AMBIGUOUS_RELATIONSHIP_PATH"
                    if request.prior_clarifications == 0
                    else "AMBIGUOUS_RELATIONSHIP_PATH_AFTER_CLARIFICATION",
                )
            for relationship_ref in unique_paths[0]:
                if relationship_ref not in selected:
                    selected.append(relationship_ref)
        return "READY", tuple(selected), None

    def solve(
        self,
        request: QueryShapeRequest,
        *,
        relationships: tuple[RelationshipContract, ...],
        result_shapes: tuple[ResultShapeContract, ...],
        quality_receipts: tuple[DataQualityReceipt, ...],
    ) -> ShapeSolverOutcome:
        relationship_by_id = {item.contract_id: item for item in relationships}
        if len(relationship_by_id) != len(relationships):
            return self._outcome(
                status="BLOCKED",
                reasons=("DUPLICATE_RELATIONSHIP_CONTRACT",),
                request=request,
                relationships=(),
                quality_receipts=(),
            )
        selected_refs = request.relationship_refs
        if request.target_object_refs:
            path_status, selected_refs, path_reason = self._discover_relationships(
                request, relationships
            )
            if path_status != "READY":
                return self._outcome(
                    status=path_status,
                    reasons=(path_reason,) if path_reason else (),
                    request=request,
                    relationships=(),
                    quality_receipts=(),
                )
        missing = tuple(
            item for item in selected_refs if item not in relationship_by_id
        )
        if missing:
            return self._outcome(
                status="BLOCKED",
                reasons=("RELATIONSHIP_CONTRACT_NOT_FOUND",),
                request=request,
                relationships=(),
                quality_receipts=(),
            )
        selected_relationships = tuple(
            relationship_by_id[item] for item in selected_refs
        )
        if not request.target_object_refs and any(
            request.root_object_ref
            not in {item.left_endpoint_ref, item.right_endpoint_ref}
            for item in selected_relationships
        ):
            return self._outcome(
                status="BLOCKED",
                reasons=("RELATIONSHIP_ROOT_MISMATCH",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        if not request.target_object_refs and any(
            (item.direction == "left_to_right" and request.root_object_ref != item.left_endpoint_ref)
            or (item.direction == "right_to_left" and request.root_object_ref != item.right_endpoint_ref)
            for item in selected_relationships
        ):
            return self._outcome(
                status="BLOCKED",
                reasons=("RELATIONSHIP_DIRECTION_NOT_TRAVERSABLE",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        if any(
            item.schema_snapshot_digest != request.active_schema_snapshot_digest
            for item in selected_relationships
        ):
            return self._outcome(
                status="BLOCKED",
                reasons=("RELATIONSHIP_SCHEMA_SNAPSHOT_STALE",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )

        desired_shape = request.requested_shape or (
            "Aggregate"
            if request.aggregation_reducer is not None
            else self._default_shape(
                request.root_object_ref, selected_relationships
            )
        )
        if desired_shape in {"Aggregate", "ScalarAggregate"} and request.aggregation_reducer is None:
            return self._outcome(
                status="BLOCKED",
                reasons=("AGGREGATION_REDUCER_REQUIRED",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        requested_relationships = set(selected_refs)
        shape_candidates = tuple(
            item
            for item in result_shapes
            if item.root_object_ref == request.root_object_ref
            and set(item.relationship_refs) == requested_relationships
            and len(item.relationship_refs) == len(selected_refs)
            and item.shape == desired_shape
        )
        if not shape_candidates:
            return self._outcome(
                status="BLOCKED",
                reasons=("APPROVED_RESULT_SHAPE_NOT_FOUND",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        grain_candidates = tuple(
            item for item in shape_candidates
            if not request.exact_grain or item.exact_grain == request.exact_grain
        )
        if not grain_candidates:
            return self._outcome(
                status="BLOCKED",
                reasons=("RESULT_GRAIN_NOT_APPROVED",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        candidates = tuple(
            item for item in grain_candidates
            if desired_shape not in {"Aggregate", "ScalarAggregate"}
            or (
                item.aggregation_semantics is not None
                and item.aggregation_semantics.reducer == request.aggregation_reducer
                and (
                    not request.exact_grain
                    or item.aggregation_semantics.output_grain == request.exact_grain
                )
            )
        )
        if not candidates:
            return self._outcome(
                status="BLOCKED",
                reasons=("AGGREGATION_REDUCER_NOT_APPROVED",),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )
        if len(candidates) > 1:
            reason = (
                "AMBIGUOUS_RESULT_SHAPE"
                if request.prior_clarifications == 0
                else "AMBIGUOUS_RESULT_SHAPE_AFTER_CLARIFICATION"
            )
            return self._outcome(
                status=(
                    "CLARIFICATION_REQUIRED"
                    if request.prior_clarifications == 0
                    else "BLOCKED"
                ),
                reasons=(reason,),
                request=request,
                relationships=selected_relationships,
                quality_receipts=(),
            )

        selected_shape = candidates[0]
        traversal_parents = self._traversal_parent_refs(request.root_object_ref, selected_relationships)
        selected_quality_list = []
        for relationship in selected_relationships:
            available = [q for q in quality_receipts if q.relationship_contract_digest == relationship.contract_digest]
            scoped = [q for q in available if q.directional_scope and
                      q.directional_scope.root_endpoint_ref == traversal_parents[relationship.contract_id]]
            # Historical singleton is retained; ambiguous/missing scoped evidence
            # proceeds to fail-closed readiness, never first-match selection.
            mixed_history = scoped and any(q.directional_scope is None for q in available)
            selected_quality_list.extend(scoped if scoped and not mixed_history else available)
        selected_quality = tuple(selected_quality_list)
        readiness = assess_contract_readiness(
            relationships=selected_relationships,
            result_shape=selected_shape,
            quality_receipts=selected_quality,
        )
        if readiness.status == "BLOCKED":
            return self._outcome(
                status="BLOCKED",
                reasons=readiness.reason_codes,
                request=request,
                relationships=selected_relationships,
                quality_receipts=selected_quality,
                selected_shape=selected_shape,
                readiness_digest=readiness.readiness_digest,
            )
        if desired_shape == "FlatRelation":
            traversal_parents = self._traversal_parent_refs(
                request.root_object_ref, selected_relationships
            )
            for relationship, quality in zip(selected_relationships, selected_quality):
                if (
                    self._effective_cardinality(
                        traversal_parents[relationship.contract_id], relationship
                    )
                    == "many_to_one"
                    and quality.duplicate_key_rows
                ):
                    return self._outcome(
                        status="BLOCKED",
                        reasons=("PARENT_KEY_NOT_UNIQUE",),
                        request=request,
                        relationships=selected_relationships,
                        quality_receipts=selected_quality,
                        selected_shape=selected_shape,
                        readiness_digest=readiness.readiness_digest,
                    )
        return self._outcome(
            status="READY",
            reasons=(),
            request=request,
            relationships=selected_relationships,
            quality_receipts=selected_quality,
            selected_shape=selected_shape,
            readiness_digest=readiness.readiness_digest,
        )


def assess_contract_readiness(
    *,
    relationships: tuple[RelationshipContract, ...],
    result_shape: ResultShapeContract,
    quality_receipts: tuple[DataQualityReceipt, ...],
) -> ContractReadiness:
    """Validate cross-contract readiness without choosing or compiling a plan."""

    reasons: list[str] = []
    by_id = {item.contract_id: item for item in relationships}
    if len(by_id) != len(relationships):
        reasons.append("DUPLICATE_RELATIONSHIP_CONTRACT")
    for relationship_ref in result_shape.relationship_refs:
        if relationship_ref not in by_id:
            reasons.append("RESULT_SHAPE_RELATIONSHIP_MISSING")

    selected = tuple(
        by_id[item]
        for item in result_shape.relationship_refs
        if item in by_id
    )
    bags = tuple(item for item in selected if item.cardinality == "stored_row_association")
    if bags and (len(selected) != 1 or result_shape.shape != "FlatRelation"
                 or result_shape.duplicate_policy != "PRESERVE" or result_shape.null_policy != "PRESERVE"):
        reasons.append("STORED_ROW_RESULT_SHAPE_UNSUPPORTED")
    sibling_many = tuple(
        item for item in selected if item.cardinality == "one_to_many"
    )
    if result_shape.shape == "FlatRelation" and len(sibling_many) >= 2:
        if len(result_shape.exact_grain) < 1 + len(sibling_many):
            reasons.append("SIBLING_MANY_COMPOSITE_GRAIN_REQUIRED")
        if not (result_shape.fanout_semantics and result_shape.fanout_semantics.strip()):
            reasons.append("SIBLING_MANY_FANOUT_SEMANTICS_REQUIRED")
        if result_shape.duplicate_policy != "APPROVED_FANOUT":
            reasons.append("SIBLING_MANY_DUPLICATE_POLICY_NOT_APPROVED")

    quality_by_relationship_digest = {
        item.relationship_contract_digest: item for item in quality_receipts
    }
    if len(quality_by_relationship_digest) != len(quality_receipts):
        reasons.append("DUPLICATE_DATA_QUALITY_RECEIPT")
    traversal_parents = {}
    if any(item.directional_scope for item in quality_receipts):
        try:
            traversal_parents = CardinalityAwareQueryShapeSolver._traversal_parent_refs(result_shape.root_object_ref, selected)
        except ValueError:
            reasons.append("QUALITY_TRAVERSAL_TREE_INVALID")
    for relationship in selected:
        receipt = quality_by_relationship_digest.get(relationship.contract_digest)
        if receipt is None:
            reasons.append("DATA_QUALITY_RECEIPT_MISSING")
            continue
        if receipt.applied_orphan_policy != relationship.orphan_policy:
            reasons.append("QUALITY_ORPHAN_POLICY_MISMATCH")
        if receipt.schema_snapshot_digest != relationship.schema_snapshot_digest:
            reasons.append("QUALITY_SCHEMA_SNAPSHOT_MISMATCH")
        if relationship.cardinality == "stored_row_association" and not isinstance(receipt.directional_scope, StoredRowAssociationScope):
            reasons.append("STORED_ROW_QUALITY_SCOPE_REQUIRED")
        if relationship.cardinality != "stored_row_association" and isinstance(receipt.directional_scope, StoredRowAssociationScope):
            reasons.append("ENTITY_RELATION_REQUIRES_ENTITY_QUALITY")
        if receipt.directional_scope:
            scope = receipt.directional_scope
            if isinstance(scope, StoredRowAssociationScope):
                root_refs=(relationship.physical_keys.left_mapping_refs if scope.root_endpoint_ref==relationship.left_endpoint_ref else relationship.physical_keys.right_mapping_refs)
                target_refs=(relationship.physical_keys.right_mapping_refs if scope.root_endpoint_ref==relationship.left_endpoint_ref else relationship.physical_keys.left_mapping_refs)
                if (scope.budget_per_root!=relationship.fanout.budget_per_parent
                    or scope.root_mapping_refs!=root_refs or scope.target_mapping_refs!=target_refs):
                    reasons.append("STORED_ROW_QUALITY_CONTRACT_MISMATCH")
            root = traversal_parents.get(relationship.contract_id)
            if root != scope.root_endpoint_ref:
                reasons.append("QUALITY_TRAVERSAL_ROOT_MISMATCH")
            if {scope.root_endpoint_ref,scope.target_endpoint_ref} != {relationship.left_endpoint_ref,relationship.right_endpoint_ref}:
                reasons.append("QUALITY_RELATIONSHIP_ENDPOINT_MISMATCH")
            elif (root is not None and (
                CardinalityAwareQueryShapeSolver._effective_cardinality(root,relationship) != scope.effective_cardinality
                or CardinalityAwareQueryShapeSolver._traversable_neighbor(root,relationship) != scope.target_endpoint_ref)):
                reasons.append("QUALITY_TRAVERSAL_DIRECTION_MISMATCH")
            if scope.acl_propagation != relationship.acl_propagation:
                reasons.append("QUALITY_ACL_PROPAGATION_MISMATCH")
            if isinstance(scope, DirectionalQualityScope):
                if scope.unique_endpoint_null_key_rows:
                    reasons.append("QUALITY_UNIQUE_ENDPOINT_NULL_KEY")
                if receipt.duplicate_key_rows:
                    reasons.append("QUALITY_UNIQUE_ENDPOINT_NOT_UNIQUE")
        if receipt.orphan_rows and relationship.orphan_policy == "BLOCK":
            reasons.append("QUALITY_ORPHANS_BLOCKED")
        if receipt.null_fk_rows and relationship.null_policy == "BLOCK":
            reasons.append("QUALITY_NULL_FK_BLOCKED")
        if receipt.duplicate_key_rows and relationship.duplicate_policy == "BLOCK":
            reasons.append("QUALITY_DUPLICATE_KEYS_BLOCKED")
        if (
            receipt.fanout_distribution.observed_max
            > relationship.fanout.budget_per_parent
            and relationship.fanout.budget_action == "BLOCK"
        ):
            reasons.append("FANOUT_BUDGET_EXCEEDED")
        excluded_null_or_orphan = receipt.null_fk_rows + receipt.orphan_rows
        if (
            relationship.orphan_policy in {"EXCLUDE_WITH_DISCLOSURE", "QUARANTINE"}
            and receipt.excluded_rows < excluded_null_or_orphan
        ):
            reasons.append("QUALITY_EXCLUSION_DISCLOSURE_INVALID")
        if (
            relationship.orphan_policy == "INCLUDE_UNMATCHED"
            and receipt.excluded_rows != 0
        ):
            reasons.append("QUALITY_INCLUDE_UNMATCHED_EXCLUSION_INVALID")

    ordered_reasons = tuple(dict.fromkeys(reasons))
    values = {
        "status": "BLOCKED" if ordered_reasons else "READY",
        "reason_codes": ordered_reasons,
        "relationship_contract_digests": tuple(
            item.contract_digest for item in relationships
        ),
        "result_shape_contract_digest": result_shape.contract_digest,
        "quality_receipt_digests": tuple(
            item.receipt_digest for item in quality_receipts
        ),
    }
    return ContractReadiness(**values, readiness_digest=_digest(values))


__all__ = [
    "CardinalityAwareQueryShapeSolver",
    "ContractReadiness",
    "DataQualityReceipt",
    "QueryShapeRequest",
    "RelationshipContract",
    "ResultShapeContract",
    "ShapeSolverOutcome",
    "assess_contract_readiness",
]
