"""Profile-driven binding, relational planning, and Check-ledger validation.

This generic surface consumes only resolved logical intent plus one exact
semantic authority: either an active Release or an explicitly reviewed
definition scope. It does not contain domain routing, query templates, SQL
rendering, execution, attestation, or Release authority.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Literal
from .filter_expression import FilterExpression,validate_filter_expression,conjoin_appended_filters
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .ledger import GovernedRuntimeLedger, RecordKind
from .semantic_intent import ResolvedIntent, SemanticResolutionReceipt
from .semantic_authority import (
    SemanticAuthorityFields,
    require_active_semantic_authority,
    require_reviewed_semantic_authority,
    require_same_semantic_authority,
    semantic_authority_values,
)
from .semantic_profile_loader import LoadedProfileEntry, SemanticContextBundle
from .semantic_profile_retrieval import RetrievalReceipt
from .snapshot_result_paging import SnapshotPagingPolicy
from .physical_temporal_encoding import (
    PhysicalTemporalEncoding,
    temporal_encoding_check,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class PlannerCatalogColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    unique: bool


class PlannerCatalogTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    estimated_rows: int
    columns: tuple[PlannerCatalogColumn, ...]


class PlannerCatalogSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    backend: str
    read_only: bool
    tables: tuple[PlannerCatalogTable, ...]


class PlannerCatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_digest: str
    schema_digest: str
    capability_digest: str
    captured_at: str
    freshness_status: Literal["CURRENT", "STALE", "UNKNOWN"]
    supported_dialects: tuple[str, ...]
    supported_operators: tuple[str, ...]
    sources: tuple[PlannerCatalogSource, ...]

    def source(self, source_id: str) -> PlannerCatalogSource | None:
        return next((item for item in self.sources if item.source_id == source_id), None)

    def table(self, source_id: str, table: str) -> PlannerCatalogTable | None:
        source = self.source(source_id)
        if source is None:
            return None
        return next((item for item in source.tables if item.name == table), None)

    def column(self, source_id: str, table: str, column: str) -> PlannerCatalogColumn | None:
        found = self.table(source_id, table)
        if found is None:
            return None
        return next((item for item in found.columns if item.name == column), None)


class PlanningPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    allowed_relationship_authorities: tuple[str, ...]
    allowed_join_kinds: tuple[str, ...]
    max_physical_sources: int
    max_scan_tables: int
    cross_database_allowed: bool
    max_estimated_rows: int
    max_result_rows: int
    timeout_seconds: int
    required_dialect: str
    max_relationship_hops: int = Field(default=3, ge=1, le=5)
    paging_policy: SnapshotPagingPolicy | None = None
    nested_projection_policy: Literal['exact-v1', 'independent-subset-v1'] = 'exact-v1'

    @model_serializer(mode="wrap")
    def preserve_legacy_policy(self, handler):
        value = handler(self)
        if self.paging_policy is None:
            value.pop("paging_policy", None)
        if self.nested_projection_policy == 'exact-v1':
            value.pop('nested_projection_policy',None)
        return value

    @property
    def policy_digest(self) -> str:
        return _digest(self)


class SemanticPlanningContextError(RuntimeError):
    pass


class SemanticPlanningContext(SemanticAuthorityFields):
    """Verified, closed receipt chain for the generic planning boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    retrieval: RetrievalReceipt
    resolution: SemanticResolutionReceipt
    bundle: SemanticContextBundle
    catalog: PlannerCatalogSnapshot
    policy: PlanningPolicy
    question_digest: str
    retrieval_receipt_digest: str
    semantic_resolution_receipt_digest: str
    intent_synthesis_receipt_digest: str
    intent_model_id: str
    intent_model_digest: str
    intent_role_digest: str
    intent_prompt_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    semantic_bundle_content_digest: str
    active_release_digest: str | None
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    planning_policy_digest: str
    context_digest: str

    @property
    def resolved_intent(self) -> ResolvedIntent:
        resolved = self.resolution.resolved_intent
        if resolved is None:
            raise SemanticPlanningContextError("RESOLUTION_NOT_RESOLVED")
        return resolved

    @staticmethod
    def _receipt_digest(receipt: BaseModel) -> str:
        return _digest(receipt.model_dump(mode="json", exclude={"receipt_digest"}))

    @staticmethod
    def _entry_dependencies(entry: LoadedProfileEntry) -> set[str]:
        collected: list[object] = []
        for key in (
            "depends_on", "identity_property_ref", "properties", "property_refs",
            "logical_grain", "left_property_ref", "right_property_ref",
            "left_property_refs", "right_property_refs",
            "relationship_identity_ref", "value_type_ref", "unit_ref",
            "numerator_ref", "denominator_ref", "unit_property_ref",
            "owner_ref", "left_endpoint_ref", "right_endpoint_ref",
        ):
            if key in entry.payload:
                collected.append(entry.payload[key])
        logical_plan = entry.payload.get("logical_plan")
        if isinstance(logical_plan, dict) and "depends_on" in logical_plan:
            collected.append(logical_plan["depends_on"])
        dependencies: set[str] = set()
        for value in collected:
            if isinstance(value, str):
                dependencies.add(value)
            elif isinstance(value, list):
                dependencies.update(str(item) for item in value)
        return dependencies

    @classmethod
    def _retrieval_matches_bundle(
        cls, retrieval: RetrievalReceipt, bundle: SemanticContextBundle,
    ) -> bool:
        entries = {
            item.entry_id: item
            for item in (*bundle.domain_entries, *bundle.query_entries)
        }
        candidate_ids = [item.entry_id for item in retrieval.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            return False
        if [item.rank for item in retrieval.candidates] != list(
            range(1, len(retrieval.candidates) + 1)
        ):
            return False
        for candidate in retrieval.candidates:
            entry = entries.get(candidate.entry_id)
            if entry is None or (
                candidate.kind != str(entry.payload.get("kind") or entry.category)
                or candidate.revision_id != entry.revision_id
                or candidate.revision_digest != entry.revision_digest
                or candidate.evidence_resources != entry.evidence_resources
            ):
                return False
        selected = set(candidate_ids)
        expected_mappings = tuple(sorted(
            entry.revision_id for entry in bundle.mapping_entries
            if str(entry.payload.get("domain_ref")) in selected
        ))
        valid_edges = {
            (entry.entry_id, dependency)
            for entry in entries.values()
            for dependency in cls._entry_dependencies(entry)
            if dependency in entries
        }
        return (
            retrieval.mapping_revision_ids == expected_mappings
            and retrieval.excluded_revision_ids == bundle.excluded_revision_ids
            and retrieval.withheld_logical_ids
            == tuple(sorted(bundle.unavailable_logical_ids))
            and retrieval.retrieval_index_digest == bundle.retrieval_index_digest
            and all(
                (edge.from_entry_id, edge.to_entry_id) in valid_edges
                and edge.from_entry_id in selected
                and edge.to_entry_id in selected
                for edge in retrieval.graph_expansion_edges
            )
        )

    @classmethod
    def create(
        cls, *, retrieval: RetrievalReceipt, resolution: SemanticResolutionReceipt,
        bundle: SemanticContextBundle, catalog: PlannerCatalogSnapshot,
        policy: PlanningPolicy,
        authority_lane: Literal["active_release", "reviewed_definition"] = "active_release",
    ) -> "SemanticPlanningContext":
        if authority_lane == "active_release":
            require_active_semantic_authority(bundle)
        else:
            require_reviewed_semantic_authority(bundle)
        require_same_semantic_authority(retrieval, bundle)
        require_same_semantic_authority(resolution, bundle)
        if resolution.resolved_intent is not None:
            require_same_semantic_authority(resolution.resolved_intent, bundle)
        if cls._receipt_digest(retrieval) != retrieval.receipt_digest:
            raise SemanticPlanningContextError("RETRIEVAL_RECEIPT_DIGEST_INVALID")
        if cls._receipt_digest(resolution) != resolution.receipt_digest:
            raise SemanticPlanningContextError("RESOLUTION_RECEIPT_DIGEST_INVALID")
        if not cls._retrieval_matches_bundle(retrieval, bundle):
            raise SemanticPlanningContextError("RETRIEVAL_BUNDLE_PROJECTION_INVALID")
        if resolution.status != "RESOLVED" or resolution.resolved_intent is None:
            raise SemanticPlanningContextError("RESOLUTION_NOT_RESOLVED")
        if not bundle.purpose or bundle.purpose != bundle.purpose.strip():
            raise SemanticPlanningContextError("CONTEXT_PURPOSE_NOT_CANONICAL")
        if resolution.candidate_digest != _digest(resolution.resolved_intent.candidate):
            raise SemanticPlanningContextError("RESOLUTION_CANDIDATE_DIGEST_INVALID")
        if resolution.resolved_intent.intent_digest != resolution.candidate_digest:
            raise SemanticPlanningContextError("RESOLVED_INTENT_DIGEST_INVALID")
        if resolution.retrieval_receipt_digest != retrieval.receipt_digest:
            raise SemanticPlanningContextError("RESOLUTION_RETRIEVAL_RECEIPT_MISMATCH")
        for value, expected, code in (
            (retrieval.principal_id, bundle.principal_id, "CONTEXT_PRINCIPAL_MISMATCH"),
            (resolution.principal_id, bundle.principal_id, "CONTEXT_PRINCIPAL_MISMATCH"),
            (retrieval.purpose, bundle.purpose, "CONTEXT_PURPOSE_MISMATCH"),
            (resolution.purpose, bundle.purpose, "CONTEXT_PURPOSE_MISMATCH"),
            (retrieval.acl_projection_digest, bundle.acl_projection_digest, "CONTEXT_ACL_PROJECTION_MISMATCH"),
            (resolution.acl_projection_digest, bundle.acl_projection_digest, "CONTEXT_ACL_PROJECTION_MISMATCH"),
            (retrieval.semantic_bundle_digest, bundle.bundle_digest, "CONTEXT_BUNDLE_DIGEST_MISMATCH"),
            (resolution.semantic_bundle_digest, bundle.bundle_digest, "CONTEXT_BUNDLE_DIGEST_MISMATCH"),
            (retrieval.active_release_digest, bundle.active_release_digest, "CONTEXT_ACTIVE_RELEASE_MISMATCH"),
            (resolution.active_release_digest, bundle.active_release_digest, "CONTEXT_ACTIVE_RELEASE_MISMATCH"),
            (retrieval.domain_profile_digest, bundle.domain_profile_digest, "CONTEXT_DOMAIN_PROFILE_MISMATCH"),
            (resolution.domain_profile_digest, bundle.domain_profile_digest, "CONTEXT_DOMAIN_PROFILE_MISMATCH"),
            (retrieval.mapping_profile_digest, bundle.mapping_profile_digest, "CONTEXT_MAPPING_PROFILE_MISMATCH"),
            (resolution.mapping_profile_digest, bundle.mapping_profile_digest, "CONTEXT_MAPPING_PROFILE_MISMATCH"),
            (retrieval.query_profile_digest, bundle.query_profile_digest, "CONTEXT_QUERY_PROFILE_MISMATCH"),
            (resolution.query_profile_digest, bundle.query_profile_digest, "CONTEXT_QUERY_PROFILE_MISMATCH"),
            (retrieval.catalog_snapshot_digest, bundle.catalog_snapshot_digest, "CONTEXT_CATALOG_DIGEST_MISMATCH"),
            (resolution.catalog_snapshot_digest, bundle.catalog_snapshot_digest, "CONTEXT_CATALOG_DIGEST_MISMATCH"),
            (catalog.snapshot_digest, bundle.catalog_snapshot_digest, "CONTEXT_CATALOG_DIGEST_MISMATCH"),
            (retrieval.schema_digest, bundle.schema_digest, "CONTEXT_SCHEMA_DIGEST_MISMATCH"),
            (resolution.schema_digest, bundle.schema_digest, "CONTEXT_SCHEMA_DIGEST_MISMATCH"),
            (catalog.schema_digest, bundle.schema_digest, "CONTEXT_SCHEMA_DIGEST_MISMATCH"),
            (retrieval.capability_digest, bundle.capability_digest, "CONTEXT_CAPABILITY_DIGEST_MISMATCH"),
            (resolution.capability_digest, bundle.capability_digest, "CONTEXT_CAPABILITY_DIGEST_MISMATCH"),
            (catalog.capability_digest, bundle.capability_digest, "CONTEXT_CAPABILITY_DIGEST_MISMATCH"),
            (
                resolution.resolved_intent.active_release_digest,
                bundle.active_release_digest,
                "CONTEXT_ACTIVE_RELEASE_MISMATCH",
            ),
            (
                resolution.resolved_intent.domain_profile_digest,
                bundle.domain_profile_digest,
                "CONTEXT_DOMAIN_PROFILE_MISMATCH",
            ),
            (
                resolution.resolved_intent.query_profile_digest,
                bundle.query_profile_digest,
                "CONTEXT_QUERY_PROFILE_MISMATCH",
            ),
        ):
            if value != expected:
                raise SemanticPlanningContextError(code)
        synthesis_chain = (
            resolution.intent_synthesis_receipt_digest,
            resolution.intent_model_id,
            resolution.intent_model_digest,
            resolution.intent_role_digest,
            resolution.intent_prompt_digest,
        )
        if any(synthesis_chain) and not all(synthesis_chain):
            raise SemanticPlanningContextError(
                "INTENT_SYNTHESIS_CONTEXT_INCOMPLETE"
            )
        values = {
            "retrieval": retrieval,
            "resolution": resolution,
            "bundle": bundle,
            "catalog": catalog,
            "policy": policy,
            "question_digest": retrieval.question_digest,
            "retrieval_receipt_digest": retrieval.receipt_digest,
            "semantic_resolution_receipt_digest": resolution.receipt_digest,
            "intent_synthesis_receipt_digest": (
                resolution.intent_synthesis_receipt_digest
            ),
            "intent_model_id": resolution.intent_model_id,
            "intent_model_digest": resolution.intent_model_digest,
            "intent_role_digest": resolution.intent_role_digest,
            "intent_prompt_digest": resolution.intent_prompt_digest,
            "principal_id": bundle.principal_id,
            "purpose": bundle.purpose,
            "acl_projection_digest": bundle.acl_projection_digest,
            "semantic_bundle_digest": bundle.bundle_digest,
            "semantic_bundle_content_digest": _digest(bundle),
            **semantic_authority_values(bundle),
            "domain_profile_digest": bundle.domain_profile_digest,
            "mapping_profile_digest": bundle.mapping_profile_digest,
            "query_profile_digest": bundle.query_profile_digest,
            "catalog_snapshot_digest": catalog.snapshot_digest,
            "catalog_snapshot_content_digest": _digest(catalog),
            "schema_digest": catalog.schema_digest,
            "capability_digest": catalog.capability_digest,
            "planning_policy_digest": policy.policy_digest,
        }
        digest_values = {
            key: value for key, value in values.items()
            if key not in {"retrieval", "resolution", "bundle", "catalog", "policy"}
        }
        return cls(**values, context_digest=_digest(digest_values))


class CheckEvidenceStore:
    """Content-addressed store for safe deterministic Check projections."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, projection: object) -> tuple[str, str]:
        encoded = json.dumps(
            projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
        ref = "evidence://" + digest
        path = self.path_for(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != encoded:
            raise RuntimeError("CHECK_EVIDENCE_IMMUTABLE_CONFLICT")
        if not path.exists():
            path.write_bytes(encoded)
        return ref, digest

    def path_for(self, evidence_ref: str) -> Path:
        prefix = "evidence://sha256:"
        if not evidence_ref.startswith(prefix):
            raise ValueError("CHECK_EVIDENCE_REF_INVALID")
        digest = evidence_ref.removeprefix(prefix)
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("CHECK_EVIDENCE_REF_INVALID")
        return self.root / "sha256" / f"{digest}.json"

    def verify(self, evidence_ref: str, evidence_digest: str) -> str | None:
        try:
            path = self.path_for(evidence_ref)
        except ValueError:
            return "CHECK_EVIDENCE_REF_INVALID"
        if not path.exists():
            return "CHECK_EVIDENCE_MISSING"
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != evidence_digest or evidence_ref != "evidence://" + actual:
            return "CHECK_EVIDENCE_DIGEST_MISMATCH"
        return None


class BoundField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_id: str
    logical_revision_digest: str
    mapping_id: str
    mapping_revision_id: str
    mapping_revision_digest: str
    source_id: str
    table: str
    column: str
    logical_type: str
    mapped_type: str
    key_role: str
    unit: str | None
    temporal_encoding: PhysicalTemporalEncoding | None = Field(
        default=None, exclude_if=lambda value: value is None,
    )
    evidence_resources: tuple[str, ...]


class BoundRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str
    relation_revision_digest: str
    mapping_id: str
    mapping_revision_id: str
    mapping_revision_digest: str
    left_field: BoundField
    right_field: BoundField
    cardinality: str
    join_kind: str
    authority_basis: str
    physically_validated: bool
    traversal: Literal["left_to_right", "right_to_left"]
    evidence_resources: tuple[str, ...]


class BindingResolutionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"]
    reason_codes: tuple[str, ...]
    clarification_count: int
    field_bindings: tuple[BoundField, ...]
    semantic_dependency_bindings: tuple[tuple[str, str], ...]
    relationship_path: tuple[BoundRelationship, ...]
    source_tables: tuple[tuple[str, str], ...]
    semantic_context_digest: str
    question_digest: str
    retrieval_receipt_digest: str
    semantic_resolution_receipt_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    semantic_bundle_content_digest: str
    active_release_digest: str
    domain_profile_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    policy_digest: str
    binding_digest: str


class RelationalScan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    table: str
    alias: str


class RelationalJoin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str
    left_alias: str
    left_column: str
    right_alias: str
    right_column: str
    join_kind: str
    cardinality: str


class RelationalFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_id: str
    source_alias: str
    column: str
    operator: str
    value: str | int | float | bool | None | tuple[str | int | float | bool | None, ...]


class RelationalProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_id: str
    source_alias: str
    column: str
    output_alias: str


class RelationalAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: str
    logical_id: str
    source_alias: str | None
    column: str | None
    distinct: bool
    output_alias: str


class RelationalOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_id: str
    source_alias: str
    column: str
    direction: Literal["ASC", "DESC"]


class RelationalLatest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    partition_by: tuple[str, ...]
    ordering: tuple[RelationalOrder, ...]


class RelationalTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_id: str
    timezone: str
    start: str
    end: str
    start_inclusive: bool
    end_inclusive: bool


class RelationalMetricContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    grain: tuple[str, ...]
    inclusion: dict[str, object]
    exclusion: dict[str, object]
    time_semantics: str
    unit: str


class RelationalAst(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scans: tuple[RelationalScan, ...]
    joins: tuple[RelationalJoin, ...]
    filters: tuple[RelationalFilter, ...]
    filter_expression: FilterExpression | None = Field(default=None,exclude_if=lambda v:v is None)
    projections: tuple[str, ...]
    projection_bindings: tuple[RelationalProjection, ...]
    aggregates: tuple[RelationalAggregate, ...]
    latest: RelationalLatest | None
    time_range: RelationalTimeRange | None
    metric_contracts: tuple[RelationalMetricContract, ...]
    group_by: tuple[str, ...]
    ordering: tuple[RelationalOrder, ...]
    limit: int
    operator_sequence: tuple[str, ...]
    semantic_context_digest: str
    question_digest: str
    retrieval_receipt_digest: str
    semantic_resolution_receipt_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    semantic_bundle_content_digest: str
    intent_digest: str
    binding_digest: str
    active_release_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    policy_digest: str
    plan_digest: str


    @model_validator(mode='after')
    def validate_filter_composition(self):
        if self.filter_expression is not None:
            validate_filter_expression(self.filter_expression,len(self.filters))
        return self


class RelationalPlanOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"]
    reason_codes: tuple[str, ...]
    clarification_count: int
    plan: RelationalAst | None
    outcome_digest: str


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


class GenericBindingSolver:
    SOLVER_ID = "boi.generic-binding-solver@0.1.0"

    @staticmethod
    def _domain_by_id(bundle: SemanticContextBundle) -> dict[str, LoadedProfileEntry]:
        return {entry.entry_id: entry for entry in bundle.domain_entries}

    @classmethod
    def _required_property_ids(
        cls, resolved: ResolvedIntent, bundle: SemanticContextBundle
    ) -> tuple[str, ...]:
        candidate = resolved.candidate
        domains = cls._domain_by_id(bundle)
        values: list[str] = []
        for entity_id in candidate.entity_ids:
            entity = domains.get(entity_id)
            if entity and entity.payload.get("identity_property_ref"):
                values.append(str(entity.payload["identity_property_ref"]))
        values.extend((*candidate.dimensions, *candidate.grain, *candidate.property_ids))
        values.extend(item.property_id for item in candidate.filters)
        values.extend(item.property_id for item in candidate.ordering)
        if candidate.time_range:
            values.append(candidate.time_range.property_id)
        for logical_id in tuple(values):
            entry = domains.get(logical_id)
            contract = entry.payload.get("unit_contract") if entry else None
            if isinstance(contract, dict) and contract.get("unit_property_ref"):
                values.append(str(contract["unit_property_ref"]))
        queue = deque(item.target_id for item in candidate.aggregations)
        visited: set[str] = set()
        while queue:
            entry_id = queue.popleft()
            if entry_id in visited:
                continue
            visited.add(entry_id)
            entry = domains.get(entry_id)
            if entry is None:
                continue
            if entry.payload.get("kind") == "PropertyDefinition":
                values.append(entry_id)
            for dependency in entry.payload.get("depends_on") or ():
                queue.append(str(dependency))
        return _ordered_unique(values)

    @staticmethod
    def _unit_binding(payload: dict[str, object]) -> str | None:
        if payload.get("unit") is not None:
            return str(payload["unit"])
        if payload.get("unit_semantics") == "declared" and payload.get("unit_ref"):
            return str(payload["unit_ref"])
        contract = payload.get("unit_contract")
        if (
            isinstance(contract, dict)
            and contract.get("applicability") == "measurement"
            and contract.get("validated") is True
            and contract.get("unit_property_ref")
        ):
            return f"property-ref:{contract['unit_property_ref']}"
        return None

    @staticmethod
    def _logical_type(
        payload: dict[str, object], domains: dict[str, LoadedProfileEntry]
    ) -> str:
        direct = payload.get("value_type")
        if direct:
            return str(direct)
        value_type_ref = str(payload.get("value_type_ref") or "")
        value_type = domains.get(value_type_ref)
        if value_type is not None and value_type.payload.get("kind") == "ValueType":
            return str(value_type.payload.get("primitive_type") or "unknown")
        return "unknown"

    @staticmethod
    def _outcome(
        *, status: str, reasons: tuple[str, ...], fields: tuple[BoundField, ...],
        path: tuple[BoundRelationship, ...], source_tables: tuple[tuple[str, str], ...],
        context: SemanticPlanningContext,
        dependencies: tuple[tuple[str, str], ...] = (),
    ) -> BindingResolutionOutcome:
        bundle, catalog, policy = context.bundle, context.catalog, context.policy
        values = {
            "status": status,
            "reason_codes": reasons,
            "clarification_count": 1 if status == "CLARIFICATION_REQUIRED" else 0,
            "field_bindings": fields,
            "semantic_dependency_bindings": dependencies,
            "relationship_path": path,
            "source_tables": source_tables,
            "semantic_context_digest": context.context_digest,
            "question_digest": context.question_digest,
            "retrieval_receipt_digest": context.retrieval_receipt_digest,
            "semantic_resolution_receipt_digest": context.semantic_resolution_receipt_digest,
            "principal_id": context.principal_id,
            "purpose": context.purpose,
            "acl_projection_digest": context.acl_projection_digest,
            "semantic_bundle_digest": context.semantic_bundle_digest,
            "semantic_bundle_content_digest": context.semantic_bundle_content_digest,
            "active_release_digest": bundle.active_release_digest,
            "domain_profile_digest": bundle.domain_profile_digest,
            "catalog_snapshot_digest": catalog.snapshot_digest,
            "catalog_snapshot_content_digest": context.catalog_snapshot_content_digest,
            "schema_digest": catalog.schema_digest,
            "capability_digest": catalog.capability_digest,
            "mapping_profile_digest": bundle.mapping_profile_digest,
            "query_profile_digest": bundle.query_profile_digest,
            "policy_digest": policy.policy_digest,
        }
        serializable = {
            **values,
            "field_bindings": [item.model_dump(mode="json") for item in fields],
            "semantic_dependency_bindings": dependencies,
            "relationship_path": [item.model_dump(mode="json") for item in path],
            "solver_id": GenericBindingSolver.SOLVER_ID,
        }
        return BindingResolutionOutcome(**values, binding_digest=_digest(serializable))

    @classmethod
    def _block(
        cls, reason: str, *, context: SemanticPlanningContext,
        fields: tuple[BoundField, ...] = (),
    ) -> BindingResolutionOutcome:
        return cls._outcome(
            status="BLOCKED", reasons=(reason,), fields=fields, path=(), source_tables=(),
            context=context,
        )

    @staticmethod
    def _reverse_cardinality(cardinality: str) -> str:
        return {"many_to_one": "one_to_many", "one_to_many": "many_to_one"}.get(
            cardinality, cardinality
        )

    def resolve(
        self, context: SemanticPlanningContext,
    ) -> BindingResolutionOutcome:
        resolved = context.resolved_intent
        bundle, catalog, policy = context.bundle, context.catalog, context.policy
        if resolved.active_release_digest != bundle.active_release_digest:
            return self._block("ACTIVE_RELEASE_DIGEST_MISMATCH", context=context)
        if (
            catalog.snapshot_digest != bundle.catalog_snapshot_digest
            or catalog.schema_digest != bundle.schema_digest
            or catalog.capability_digest != bundle.capability_digest
        ):
            return self._block("CATALOG_DIGEST_MISMATCH", context=context)

        required_ids = self._required_property_ids(resolved, bundle)
        if set(required_ids) & set(bundle.unavailable_logical_ids):
            return self._block("UNBOUND_PROPERTY", context=context)
        domains = self._domain_by_id(bundle)
        mappings_by_domain: dict[str, list[LoadedProfileEntry]] = {}
        mappings_by_id = {entry.entry_id: entry for entry in bundle.mapping_entries}
        for entry in bundle.mapping_entries:
            mappings_by_domain.setdefault(str(entry.payload.get("domain_ref")), []).append(entry)

        fields: list[BoundField] = []
        for logical_id in required_ids:
            entry = domains.get(logical_id)
            if entry is None or entry.payload.get("kind") != "PropertyDefinition":
                return self._block("PROPERTY_DEFINITION_NOT_ACTIVE", context=context)
            candidates = [item for item in mappings_by_domain.get(logical_id, ()) if item.availability == "bound"]
            if not candidates:
                return self._block("UNBOUND_PROPERTY", context=context)
            if len(candidates) != 1:
                return self._block("AMBIGUOUS_PHYSICAL_BINDING", context=context)
            mapping = candidates[0]
            physical = mapping.physical
            if physical is None:
                return self._block("BOUND_MAPPING_MISSING_PHYSICAL", context=context)
            source = catalog.source(physical.source)
            if source is None:
                return self._block(
                    "MAPPING_SOURCE_NOT_IN_AUTHORIZED_CATALOG", context=context,
                )
            column = catalog.column(physical.source, physical.table, physical.column)
            if column is None:
                return self._block("MAPPING_SCHEMA_OBJECT_MISSING", context=context)
            fields.append(BoundField(
                logical_id=logical_id,
                logical_revision_digest=entry.revision_digest,
                mapping_id=mapping.entry_id,
                mapping_revision_id=mapping.revision_id,
                mapping_revision_digest=mapping.revision_digest,
                source_id=physical.source,
                table=physical.table,
                column=physical.column,
                logical_type=self._logical_type(entry.payload, domains),
                mapped_type=str(mapping.payload.get("data_type") or column.data_type),
                key_role=str(mapping.payload.get("key_role") or "none"),
                unit=self._unit_binding(entry.payload),
                temporal_encoding=mapping.payload.get("temporal_encoding"),
                evidence_resources=tuple(dict.fromkeys((*entry.evidence_resources, *mapping.evidence_resources))),
            ))

        field_tuple = tuple(fields)
        dependency_bindings: list[tuple[str, str]] = []
        for aggregation in resolved.candidate.aggregations:
            target = domains.get(aggregation.target_id)
            if target is None:
                continue
            if target.payload.get("kind") == "ObjectType" and aggregation.operator == "count":
                identity = target.payload.get("identity_property_ref")
                dependencies = (str(identity),) if identity else ()
            elif target.payload.get("kind") == "Metric":
                dependencies = tuple(str(item) for item in target.payload.get("depends_on") or ())
            else:
                continue
            bound_dependencies = tuple(
                item for item in dependencies if any(field.logical_id == item for field in fields)
            )
            if len(bound_dependencies) != 1:
                return self._block(
                    "AGGREGATE_DEPENDENCY_AMBIGUOUS", context=context, fields=field_tuple,
                )
            dependency_bindings.append((aggregation.target_id, bound_dependencies[0]))
        source_tables = _ordered_unique([f"{item.source_id}\0{item.table}" for item in fields])
        source_pairs = tuple(tuple(item.split("\0", 1)) for item in source_tables)
        physical_source_count = len({source for source, _table in source_pairs})
        if physical_source_count > policy.max_physical_sources:
            return self._block(
                "PHYSICAL_SOURCE_LIMIT_EXCEEDED", context=context, fields=field_tuple
            )
        if physical_source_count > 1 and not policy.cross_database_allowed:
            return self._block(
                "CROSS_DATABASE_QUERY_FORBIDDEN", context=context, fields=field_tuple
            )
        if len(source_pairs) > policy.max_scan_tables:
            return self._block(
                "SCAN_TABLE_LIMIT_EXCEEDED", context=context, fields=field_tuple
            )
        if len(source_pairs) <= 1:
            return self._outcome(
                status="READY", reasons=(), fields=field_tuple, path=(), source_tables=source_pairs,
                context=context,
                dependencies=tuple(dependency_bindings),
            )

        field_by_mapping = {item.mapping_id: item for item in fields}
        graph: dict[tuple[str, str], list[tuple[tuple[str, str], BoundRelationship]]] = {}
        for relation in (item for item in bundle.domain_entries if item.payload.get("kind") == "RelationType"):
            relation_mappings = [
                item for item in mappings_by_domain.get(relation.entry_id, ()) if item.availability == "bound"
            ]
            for relation_mapping in relation_mappings:
                contract = relation_mapping.payload.get("relationship_binding")
                if not isinstance(contract, dict):
                    continue
                left = field_by_mapping.get(str(contract.get("left_mapping_ref")))
                right = field_by_mapping.get(str(contract.get("right_mapping_ref")))
                if left is None or right is None:
                    left_mapping = mappings_by_id.get(str(contract.get("left_mapping_ref")))
                    right_mapping = mappings_by_id.get(str(contract.get("right_mapping_ref")))
                    if left_mapping is None or right_mapping is None:
                        continue
                    for endpoint_mapping in (left_mapping, right_mapping):
                        if endpoint_mapping.entry_id in field_by_mapping:
                            continue
                        endpoint_id = str(endpoint_mapping.payload.get("domain_ref") or "")
                        endpoint = domains.get(endpoint_id)
                        physical = endpoint_mapping.physical
                        if (
                            endpoint is None
                            or endpoint.payload.get("kind") != "PropertyDefinition"
                            or endpoint_mapping.availability != "bound"
                            or physical is None
                        ):
                            return self._block(
                                "RELATIONSHIP_ENDPOINT_UNBOUND", context=context,
                                fields=tuple(fields),
                            )
                        catalog_column = catalog.column(
                            physical.source, physical.table, physical.column
                        )
                        if catalog_column is None:
                            return self._block(
                                "RELATIONSHIP_ENDPOINT_SCHEMA_OBJECT_MISSING", context=context,
                                fields=tuple(fields),
                            )
                        endpoint_field = BoundField(
                            logical_id=endpoint_id,
                            logical_revision_digest=endpoint.revision_digest,
                            mapping_id=endpoint_mapping.entry_id,
                            mapping_revision_id=endpoint_mapping.revision_id,
                            mapping_revision_digest=endpoint_mapping.revision_digest,
                            source_id=physical.source,
                            table=physical.table,
                            column=physical.column,
                            logical_type=self._logical_type(endpoint.payload, domains),
                            mapped_type=str(
                                endpoint_mapping.payload.get("data_type")
                                or catalog_column.data_type
                            ),
                            key_role=str(endpoint_mapping.payload.get("key_role") or "none"),
                            unit=self._unit_binding(endpoint.payload),
                            temporal_encoding=endpoint_mapping.payload.get(
                                "temporal_encoding"
                            ),
                            evidence_resources=tuple(dict.fromkeys((
                                *endpoint.evidence_resources,
                                *endpoint_mapping.evidence_resources,
                            ))),
                        )
                        fields.append(endpoint_field)
                        field_by_mapping[endpoint_mapping.entry_id] = endpoint_field
                    left = field_by_mapping.get(left_mapping.entry_id)
                    right = field_by_mapping.get(right_mapping.entry_id)
                if left is None or right is None:
                    continue
                left_refs = relation.payload.get("left_property_refs") or (
                    relation.payload.get("left_property_ref"),
                )
                right_refs = relation.payload.get("right_property_refs") or (
                    relation.payload.get("right_property_ref"),
                )
                if (
                    left.logical_id not in left_refs
                    or right.logical_id not in right_refs
                ):
                    # A bundle can contain an object-backed bridge relationship
                    # whose physical bridge keys intentionally differ from the
                    # endpoint identity properties.  It is not a usable flat-join
                    # edge, but an unrelated edge must not block this query's
                    # dependency closure.  Queries that need it still fail closed
                    # with no declared join path; the multi-result binder validates
                    # the bridge contract separately.
                    continue
                authority = str(contract.get("authority_basis") or "")
                if authority not in policy.allowed_relationship_authorities:
                    return self._block("RELATIONSHIP_AUTHORITY_NOT_ALLOWED", context=context, fields=field_tuple)
                join_kind = str(contract.get("join_kind") or "")
                if join_kind not in policy.allowed_join_kinds:
                    return self._block("JOIN_KIND_NOT_ALLOWED", context=context, fields=field_tuple)
                if not bool(contract.get("physically_validated")):
                    return self._block("RELATIONSHIP_NOT_PHYSICALLY_VALIDATED", context=context, fields=field_tuple)
                cardinality = str(contract.get("cardinality") or "")
                if cardinality != relation.payload.get("cardinality"):
                    return self._block("RELATIONSHIP_CARDINALITY_MISMATCH", context=context, fields=field_tuple)
                if left.source_id != right.source_id:
                    return self._block("CROSS_SOURCE_QUERY_FORBIDDEN", context=context, fields=field_tuple)
                forward = BoundRelationship(
                    relation_id=relation.entry_id,
                    relation_revision_digest=relation.revision_digest,
                    mapping_id=relation_mapping.entry_id,
                    mapping_revision_id=relation_mapping.revision_id,
                    mapping_revision_digest=relation_mapping.revision_digest,
                    left_field=left,
                    right_field=right,
                    cardinality=cardinality,
                    join_kind=join_kind,
                    authority_basis=authority,
                    physically_validated=True,
                    traversal="left_to_right",
                    evidence_resources=tuple(dict.fromkeys((*relation.evidence_resources, *relation_mapping.evidence_resources))),
                )
                reverse = forward.model_copy(update={
                    "cardinality": self._reverse_cardinality(cardinality),
                    "traversal": "right_to_left",
                    "left_field": right,
                    "right_field": left,
                })
                left_node = (left.source_id, left.table)
                right_node = (right.source_id, right.table)
                graph.setdefault(left_node, []).append((right_node, forward))
                graph.setdefault(right_node, []).append((left_node, reverse))

        base = source_pairs[0]
        selected: list[BoundRelationship] = []
        reached = {base}
        for target in source_pairs[1:]:
            queue: deque[tuple[tuple[str, str], tuple[BoundRelationship, ...], frozenset[tuple[str, str]]]] = deque(
                [(node, (), frozenset({node})) for node in sorted(reached)]
            )
            paths: list[tuple[BoundRelationship, ...]] = []
            shortest: int | None = None
            while queue:
                node, path, visited = queue.popleft()
                if shortest is not None and len(path) >= shortest:
                    continue
                for neighbor, relationship in sorted(
                    graph.get(node, ()), key=lambda item: (item[1].relation_id, item[0])
                ):
                    if neighbor in visited:
                        continue
                    candidate_path = (*path, relationship)
                    if neighbor == target:
                        shortest = len(candidate_path) if shortest is None else shortest
                        if len(candidate_path) == shortest:
                            paths.append(candidate_path)
                    elif shortest is None or len(candidate_path) < shortest:
                        queue.append((neighbor, candidate_path, visited | {neighbor}))
            unique_paths = {
                tuple((item.relation_id, item.traversal) for item in path): path for path in paths
            }
            if not unique_paths:
                return self._block("JOIN_PATH_NOT_DECLARED", context=context, fields=field_tuple)
            if len(unique_paths) > 1:
                return self._outcome(
                    status="CLARIFICATION_REQUIRED", reasons=("AMBIGUOUS_JOIN_PATH",),
                    fields=field_tuple, path=(), source_tables=source_pairs,
                    context=context,
                    dependencies=tuple(dependency_bindings),
                )
            path = next(iter(unique_paths.values()))
            if any(item.cardinality in {"one_to_many", "many_to_many", "stored_row_association"} for item in path):
                return self._block("UNSAFE_CARDINALITY", context=context, fields=field_tuple)
            for item in path:
                if item not in selected:
                    selected.append(item)
                reached.add((item.left_field.source_id, item.left_field.table))
                reached.add((item.right_field.source_id, item.right_field.table))

        selected_source_tables: list[tuple[str, str]] = [base]
        for relationship in selected:
            if relationship.traversal == "left_to_right":
                endpoints = (
                    (relationship.left_field.source_id, relationship.left_field.table),
                    (relationship.right_field.source_id, relationship.right_field.table),
                )
            else:
                endpoints = (
                    (relationship.right_field.source_id, relationship.right_field.table),
                    (relationship.left_field.source_id, relationship.left_field.table),
                )
            for endpoint in endpoints:
                if endpoint not in selected_source_tables:
                    selected_source_tables.append(endpoint)
        for requested_source in source_pairs:
            if requested_source not in selected_source_tables:
                selected_source_tables.append(requested_source)
        if len(selected_source_tables) > policy.max_scan_tables:
            return self._block(
                "SCAN_TABLE_LIMIT_EXCEEDED", context=context, fields=tuple(fields),
            )
        return self._outcome(
            status="READY", reasons=(), fields=tuple(fields), path=tuple(selected),
            source_tables=tuple(selected_source_tables),
            context=context,
            dependencies=tuple(dependency_bindings),
        )


class GenericRelationalPlanner:
    PLANNER_ID = "boi.generic-relational-planner@0.1.0"

    @staticmethod
    def _value_compatible(logical_type: str, value: object) -> bool:
        folded = logical_type.casefold()
        if value is None:
            return False
        if folded in {"number", "float", "decimal", "real", "numeric"}:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if folded in {"integer", "int"}:
            return isinstance(value, int) and not isinstance(value, bool)
        if folded in {"boolean", "bool"}:
            return isinstance(value, bool)
        if folded in {"string", "text", "varchar", "char", "datetime", "timestamp", "date"}:
            return isinstance(value, str)
        return False

    @staticmethod
    def _metric_scope_reflected(
        inclusion: dict[str, object], exclusion: dict[str, object],
        candidate_filters: tuple[object, ...],
    ) -> bool:
        actual = {
            _digest(item.model_dump(mode="json"))
            for item in candidate_filters
            if isinstance(item, BaseModel)
        }
        inclusion_filters = inclusion.get("filters", [])
        exclusion_filters = exclusion.get("filters", [])
        if not isinstance(inclusion_filters, list) or not isinstance(exclusion_filters, list):
            return False
        if inclusion.get("mode") == "all" and inclusion_filters:
            return False
        if inclusion.get("mode") == "filters":
            if not inclusion_filters or not all(isinstance(item, dict) for item in inclusion_filters):
                return False
            if not {_digest(item) for item in inclusion_filters} <= actual:
                return False
        if exclusion.get("mode") == "none":
            return not exclusion_filters
        # The current relational AST has no explicit exclusion predicate contract.
        return False

    @staticmethod
    def _outcome(status: str, reasons: tuple[str, ...], plan: RelationalAst | None) -> RelationalPlanOutcome:
        values = {
            "status": status,
            "reason_codes": reasons,
            "clarification_count": 1 if status == "CLARIFICATION_REQUIRED" else 0,
            "plan": plan,
        }
        return RelationalPlanOutcome(
            **values,
            outcome_digest=_digest({
                **values,
                "plan": plan.model_dump(mode="json") if plan else None,
                "planner_id": GenericRelationalPlanner.PLANNER_ID,
            }),
        )

    def plan(
        self, context: SemanticPlanningContext, *, binding: BindingResolutionOutcome,
    ) -> RelationalPlanOutcome:
        resolved, policy = context.resolved_intent, context.policy
        if binding.status != "READY":
            return self._outcome(binding.status, binding.reason_codes, None)
        if (
            binding.semantic_context_digest != context.context_digest
            or binding.active_release_digest != resolved.active_release_digest
        ):
            return self._outcome("BLOCKED", ("BINDING_CONTEXT_MISMATCH",), None)
        if resolved.candidate.filter_expression is not None and (
                resolved.candidate.metric_ids
                or any(a.operator=='latest' for a in resolved.candidate.aggregations)
                or any((f.scope or 'COLLECTION_CONTENT') not in ('COLLECTION','COLLECTION_CONTENT') for f in resolved.candidate.filters)):
            return self._outcome('BLOCKED', ('RELATIONAL_FILTER_PLACEMENT_UNRESOLVED',), None)
        if any(
            item.operator not in {
                "eq", "neq", "in", "gt", "gte", "lt", "lte", "is_null",
                "is_not_null", "not_null"
            }
            for item in resolved.candidate.filters
        ):
            return self._outcome("BLOCKED", ("UNSUPPORTED_FILTER_OPERATOR",), None)
        if any(
            item.operator not in {"count", "distinct_count", "average", "latest"}
            for item in resolved.candidate.aggregations
        ):
            return self._outcome("BLOCKED", ("UNSUPPORTED_AGGREGATE_OPERATOR",), None)
        field_by_id = {item.logical_id: item for item in binding.field_bindings}
        for filter_item in resolved.candidate.filters:
            field = field_by_id.get(filter_item.property_id)
            if field is None:
                return self._outcome("BLOCKED", ("FILTER_BINDING_UNRESOLVED",), None)
            value = filter_item.value
            if filter_item.operator == "in":
                if not isinstance(value, tuple) or not value:
                    return self._outcome("BLOCKED", ("FILTER_IN_VALUES_REQUIRED",), None)
                if not all(self._value_compatible(field.logical_type, item) for item in value):
                    return self._outcome("BLOCKED", ("FILTER_VALUE_TYPE_INCOMPATIBLE",), None)
            elif filter_item.operator in {"is_null", "is_not_null", "not_null"}:
                if value is not None:
                    return self._outcome("BLOCKED", ("FILTER_NULL_OPERATOR_VALUE_INVALID",), None)
            elif isinstance(value, tuple) or not self._value_compatible(field.logical_type, value):
                return self._outcome("BLOCKED", ("FILTER_VALUE_TYPE_INCOMPATIBLE",), None)
        alias_by_table = {
            pair: f"s{index}" for index, pair in enumerate(binding.source_tables)
        }
        scans = tuple(
            RelationalScan(source_id=source, table=table, alias=alias_by_table[(source, table)])
            for source, table in binding.source_tables
        )
        joins = tuple(
            RelationalJoin(
                relation_id=item.relation_id,
                left_alias=alias_by_table[(item.left_field.source_id, item.left_field.table)],
                left_column=item.left_field.column,
                right_alias=alias_by_table[(item.right_field.source_id, item.right_field.table)],
                right_column=item.right_field.column,
                join_kind=item.join_kind,
                cardinality=item.cardinality,
            )
            for item in binding.relationship_path
        )
        candidate = resolved.candidate
        filters = tuple(
            RelationalFilter(
                logical_id=item.property_id,
                source_alias=alias_by_table[(field_by_id[item.property_id].source_id, field_by_id[item.property_id].table)],
                column=field_by_id[item.property_id].column,
                operator=item.operator,
                value=item.value,
            )
            for item in candidate.filters
        )
        relational_time_range: RelationalTimeRange | None = None
        if candidate.time_range:
            contract = candidate.time_range
            if (
                not contract.timezone
                or contract.start_inclusive is None
                or contract.end_inclusive is None
            ):
                return self._outcome(
                    "BLOCKED", ("TIME_RANGE_BOUNDARY_CONTRACT_MISSING",), None
                )
            try:
                start = datetime.fromisoformat(contract.start.replace("Z", "+00:00"))
                end = datetime.fromisoformat(contract.end.replace("Z", "+00:00"))
                zone = ZoneInfo(contract.timezone)
            except (ValueError, ZoneInfoNotFoundError):
                return self._outcome("BLOCKED", ("TIME_RANGE_INVALID",), None)
            if start.utcoffset() is None or end.utcoffset() is None:
                return self._outcome("BLOCKED", ("TIME_RANGE_TIMEZONE_MISSING",), None)
            if (
                start.astimezone(zone).utcoffset() != start.utcoffset()
                or end.astimezone(zone).utcoffset() != end.utcoffset()
            ):
                return self._outcome("BLOCKED", ("TIME_RANGE_TIMEZONE_MISMATCH",), None)
            if start > end:
                return self._outcome("BLOCKED", ("TIME_RANGE_REVERSED",), None)
            time_binding = field_by_id[candidate.time_range.property_id]
            time_alias = alias_by_table[(time_binding.source_id, time_binding.table)]
            filters = (*filters, RelationalFilter(
                logical_id=candidate.time_range.property_id,
                source_alias=time_alias,
                column=time_binding.column,
                operator="gte" if contract.start_inclusive else "gt",
                value=candidate.time_range.start,
            ), RelationalFilter(
                logical_id=candidate.time_range.property_id,
                source_alias=time_alias,
                column=time_binding.column,
                operator="lte" if contract.end_inclusive else "lt",
                value=candidate.time_range.end,
            ))
            relational_time_range = RelationalTimeRange(
                property_id=contract.property_id,
                timezone=contract.timezone,
                start=contract.start,
                end=contract.end,
                start_inclusive=contract.start_inclusive,
                end_inclusive=contract.end_inclusive,
            )
        projection_ids = _ordered_unique([*candidate.property_ids, *candidate.dimensions])
        projection_bindings = tuple(
            RelationalProjection(
                logical_id=logical_id,
                source_alias=alias_by_table[(field_by_id[logical_id].source_id, field_by_id[logical_id].table)],
                column=field_by_id[logical_id].column,
                output_alias=f"f{index}",
            )
            for index, logical_id in enumerate(projection_ids)
        )
        ordering = tuple(
            RelationalOrder(
                logical_id=item.property_id,
                source_alias=alias_by_table[(field_by_id[item.property_id].source_id, field_by_id[item.property_id].table)],
                column=field_by_id[item.property_id].column,
                direction=item.direction,
            )
            for item in candidate.ordering
        )
        aggregates: tuple[RelationalAggregate, ...] = ()
        latest: RelationalLatest | None = None
        metric_contracts: list[RelationalMetricContract] = []
        if candidate.aggregations:
            built: list[RelationalAggregate] = []
            dependencies = dict(binding.semantic_dependency_bindings)
            domain_by_id = {
                entry.entry_id: entry for entry in context.bundle.domain_entries
            }
            identity_ids = {
                str(entry.payload.get("identity_property_ref"))
                for entry in context.bundle.domain_entries
                if entry.payload.get("kind") == "ObjectType"
                and entry.payload.get("identity_property_ref")
            }
            for index, aggregate in enumerate(candidate.aggregations):
                target_entry = domain_by_id.get(aggregate.target_id)
                target = field_by_id.get(
                    dependencies.get(aggregate.target_id, aggregate.target_id)
                )
                if aggregate.operator == "latest":
                    if (
                        target is None
                        or target_entry is None
                        or target_entry.payload.get("kind") != "PropertyDefinition"
                        or GenericBindingSolver._logical_type(
                            target_entry.payload, domain_by_id
                        ).casefold()
                        not in {"datetime", "timestamp", "date"}
                        or not target_entry.payload.get("time_semantics")
                    ):
                        return self._outcome(
                            "BLOCKED", ("LATEST_TIME_TARGET_INVALID",), None
                        )
                    if not candidate.grain or len(candidate.ordering) < 2:
                        return self._outcome(
                            "BLOCKED", ("LATEST_REQUIRES_PARTITION_AND_TIE_BREAK_ORDER",), None
                        )
                    first = candidate.ordering[0]
                    if first.property_id != aggregate.target_id or first.direction != "DESC":
                        return self._outcome(
                            "BLOCKED", ("LATEST_PRIMARY_ORDER_INVALID",), None
                        )
                    tie_break_valid = False
                    for tie_break in candidate.ordering[1:]:
                        tie_field = field_by_id.get(tie_break.property_id)
                        if tie_field is None:
                            continue
                        catalog_column = context.catalog.column(
                            tie_field.source_id, tie_field.table, tie_field.column
                        )
                        if (
                            tie_break.property_id in identity_ids
                            or (
                                catalog_column is not None
                                and catalog_column.unique
                            )
                        ):
                            tie_break_valid = True
                            break
                    if not tie_break_valid:
                        return self._outcome(
                            "BLOCKED", ("LATEST_TIE_BREAK_NOT_UNIQUE",), None
                        )
                    latest = RelationalLatest(
                        target_id=aggregate.target_id,
                        partition_by=tuple(candidate.grain),
                        ordering=ordering,
                    )
                    continue
                if aggregate.operator == "distinct_count" and (
                    target is None or not candidate.grain
                ):
                    return self._outcome(
                        "BLOCKED", ("DISTINCT_COUNT_REQUIRES_GRAIN",), None
                    )
                if target is None:
                    return self._outcome(
                        "BLOCKED", ("AGGREGATE_BINDING_UNRESOLVED",), None
                    )
                if target_entry and target_entry.payload.get("kind") == "Metric":
                    metric_grain_value = target_entry.payload.get("grain")
                    metric_grain = (
                        (str(metric_grain_value),)
                        if isinstance(metric_grain_value, str)
                        else tuple(str(item) for item in metric_grain_value or ())
                    )
                    inclusion = target_entry.payload.get("inclusion")
                    exclusion = target_entry.payload.get("exclusion")
                    if (
                        metric_grain != tuple(candidate.grain)
                        or not isinstance(inclusion, dict)
                        or not isinstance(exclusion, dict)
                        or inclusion.get("mode") not in {"all", "filters"}
                        or exclusion.get("mode") not in {"none", "filters"}
                        or not target_entry.payload.get("time_semantics")
                        or not self._metric_scope_reflected(
                            inclusion, exclusion, candidate.filters
                        )
                    ):
                        return self._outcome(
                            "BLOCKED", ("METRIC_EXECUTION_CONTRACT_UNSUPPORTED",), None
                        )
                    metric_contracts.append(RelationalMetricContract(
                        metric_id=aggregate.target_id,
                        grain=metric_grain,
                        inclusion=dict(inclusion),
                        exclusion=dict(exclusion),
                        time_semantics=str(target_entry.payload["time_semantics"]),
                        unit=str(target_entry.payload.get("unit") or ""),
                    ))
                is_entity_count = (
                    aggregate.operator == "count" and aggregate.target_id in dependencies
                )
                built.append(RelationalAggregate(
                    operator=aggregate.operator,
                    logical_id=aggregate.target_id,
                    source_alias=alias_by_table[(target.source_id, target.table)],
                    column=target.column,
                    distinct=(
                        True
                        if is_entity_count or aggregate.operator == "distinct_count"
                        else aggregate.distinct
                    ),
                    output_alias=f"a{index}",
                ))
            aggregates = tuple(built)
        if aggregates and tuple(candidate.grain) != tuple(candidate.dimensions):
            return self._outcome(
                "BLOCKED", ("AGGREGATION_GRAIN_GROUP_BY_MISMATCH",), None
            )
        operators = ["scan"]
        if joins:
            operators.append("join")
        if filters or candidate.time_range:
            operators.append("filter")
        if latest:
            operators.append("latest")
        if aggregates:
            operators.append("aggregate")
        if any(item.distinct or item.operator == "distinct_count" for item in aggregates):
            operators.append("distinct")
        if candidate.dimensions and aggregates:
            operators.append("group")
        if projection_bindings:
            operators.append("project")
        if ordering:
            operators.append("order")
        operators.append("limit")
        base = {
            "scans": scans,
            "joins": joins,
            "filters": filters,
            **({'filter_expression':conjoin_appended_filters(candidate.filter_expression, len(candidate.filters), 2 if candidate.time_range else 0)} if candidate.filter_expression is not None else {}),
            "projections": projection_ids,
            "projection_bindings": projection_bindings,
            "aggregates": aggregates,
            "latest": latest,
            "time_range": relational_time_range,
            "metric_contracts": tuple(metric_contracts),
            "group_by": tuple(candidate.dimensions) if aggregates else (),
            "ordering": ordering,
            "limit": candidate.limit,
            "operator_sequence": tuple(operators),
            "semantic_context_digest": context.context_digest,
            "question_digest": context.question_digest,
            "retrieval_receipt_digest": context.retrieval_receipt_digest,
            "semantic_resolution_receipt_digest": context.semantic_resolution_receipt_digest,
            "principal_id": context.principal_id,
            "purpose": context.purpose,
            "acl_projection_digest": context.acl_projection_digest,
            "semantic_bundle_digest": context.semantic_bundle_digest,
            "semantic_bundle_content_digest": context.semantic_bundle_content_digest,
            "intent_digest": resolved.intent_digest,
            "binding_digest": binding.binding_digest,
            "active_release_digest": resolved.active_release_digest,
            "catalog_snapshot_digest": binding.catalog_snapshot_digest,
            "catalog_snapshot_content_digest": context.catalog_snapshot_content_digest,
            "schema_digest": context.schema_digest,
            "capability_digest": context.capability_digest,
            "domain_profile_digest": resolved.domain_profile_digest,
            "mapping_profile_digest": binding.mapping_profile_digest,
            "query_profile_digest": resolved.query_profile_digest,
            "policy_digest": policy.policy_digest,
        }
        serializable = {
            key: [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value]
            if isinstance(value, tuple) else (
                value.model_dump(mode="json") if isinstance(value, BaseModel) else value
            )
            for key, value in base.items()
        }
        plan = RelationalAst(**base, plan_digest=_digest({
            **serializable, "planner_id": self.PLANNER_ID,
        }))
        return self._outcome("READY", (), plan)


class SemanticPlanCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    name: str
    status: Literal["PASS", "FAIL", "PARTIAL", "SKIP", "NOT_RUN"]
    applicable: bool
    required: bool
    evidence_ref: str
    evidence_digest: str
    reason_code: str
    inputs_digest: str


class SemanticPlanValidationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "FAIL"]
    reason_codes: tuple[str, ...]
    run_id: str
    check_ids: tuple[str, ...]
    checks: tuple[SemanticPlanCheck, ...]
    required_check_count: int
    passing_required_check_count: int
    passing_check_count: int
    semantic_context_digest: str
    question_digest: str
    retrieval_receipt_digest: str
    semantic_resolution_receipt_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    semantic_bundle_content_digest: str
    plan_digest: str
    intent_digest: str
    active_release_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    policy_digest: str
    validator_digest: str
    receipt_digest: str


def reduce_required_check_statuses(
    statuses: tuple[str, ...],
) -> tuple[Literal["PASS", "FAIL"], tuple[str, ...], int]:
    """Reduce required Check states without treating absence of work as success."""

    passing_count = sum(item == "PASS" for item in statuses)
    if any(item in {"PARTIAL", "SKIP", "NOT_RUN"} for item in statuses):
        return "FAIL", ("REQUIRED_CHECK_INCOMPLETE",), passing_count
    if any(item == "FAIL" for item in statuses):
        return "FAIL", ("REQUIRED_CHECK_FAILED",), passing_count
    if passing_count != len(statuses):
        return "FAIL", ("REQUIRED_CHECK_INCOMPLETE",), passing_count
    return "PASS", (), passing_count


class SemanticPlanValidator:
    VALIDATOR_ID = "boi.semantic-plan-validator@0.1.0"
    REQUIRED_CHECKS = (
        "acl",
        "schema_existence",
        "type_compatibility",
        "key_validity",
        "join_connectivity",
        "relationship_authority",
        "cardinality_and_fanout",
        "grain",
        "unit",
        "time_semantics",
        "freshness_and_drift",
        "compiler_capability",
        "cost_row_time_bounds",
        "read_only",
        "release_and_receipt_binding",
    )

    @staticmethod
    def _compatible(left: str, right: str) -> bool:
        groups = (
            {"number", "float", "decimal", "integer", "int", "real", "numeric"},
            {"string", "text", "varchar", "char"},
            {"datetime", "timestamp", "date"},
            {"boolean", "bool"},
        )
        left_folded, right_folded = left.casefold(), right.casefold()
        return left_folded == right_folded or any(
            left_folded in group and right_folded in group for group in groups
        )

    @staticmethod
    def _binding_content_digest(binding: BindingResolutionOutcome) -> str:
        payload = binding.model_dump(mode="json", exclude={"binding_digest"})
        payload["solver_id"] = GenericBindingSolver.SOLVER_ID
        return _digest(payload)

    @staticmethod
    def _plan_content_digest(plan: RelationalAst) -> str:
        payload = plan.model_dump(mode="json", exclude={"plan_digest"})
        payload["planner_id"] = GenericRelationalPlanner.PLANNER_ID
        return _digest(payload)

    def validate(
        self, plan: RelationalAst, *, context: SemanticPlanningContext,
        binding: BindingResolutionOutcome, ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore, occurred_at: str,
    ) -> SemanticPlanValidationReceipt:
        resolved_intent = context.resolved_intent
        bundle, catalog, policy = context.bundle, context.catalog, context.policy
        run = ledger.append(
            RecordKind.RUN,
            {
                "scope": "generic_query_planning",
                "plan_digest": plan.plan_digest,
                "intent_digest": resolved_intent.intent_digest,
                "binding_digest": binding.binding_digest,
                "active_release_digest": bundle.active_release_digest,
                "catalog_snapshot_digest": catalog.snapshot_digest,
                "policy_digest": policy.policy_digest,
                "validator_digest": _digest(self.VALIDATOR_ID),
                "semantic_context_digest": context.context_digest,
                "question_digest": context.question_digest,
                "retrieval_receipt_digest": context.retrieval_receipt_digest,
                "semantic_resolution_receipt_digest": context.semantic_resolution_receipt_digest,
                "principal_id": context.principal_id,
                "purpose": context.purpose,
                "acl_projection_digest": context.acl_projection_digest,
                "semantic_bundle_digest": context.semantic_bundle_digest,
                "semantic_bundle_content_digest": context.semantic_bundle_content_digest,
                "domain_profile_digest": context.domain_profile_digest,
                "mapping_profile_digest": context.mapping_profile_digest,
                "query_profile_digest": context.query_profile_digest,
                "catalog_snapshot_content_digest": context.catalog_snapshot_content_digest,
                "schema_digest": context.schema_digest,
                "capability_digest": context.capability_digest,
            },
            authority="mapping_validator",
            occurred_at=occurred_at,
        )

        field_columns = [
            catalog.column(item.source_id, item.table, item.column) for item in binding.field_bindings
        ]
        catalog_tables = [
            catalog.table(source, table) for source, table in binding.source_tables
        ]
        domain_by_id = {entry.entry_id: entry for entry in bundle.domain_entries}
        checks: dict[str, tuple[str, str, object]] = {}
        acl_ok = (
            plan.principal_id == binding.principal_id == context.principal_id
            and plan.purpose == binding.purpose == context.purpose
            and plan.acl_projection_digest == binding.acl_projection_digest == context.acl_projection_digest
            and plan.question_digest == binding.question_digest == context.question_digest
            and plan.retrieval_receipt_digest
            == binding.retrieval_receipt_digest
            == context.retrieval_receipt_digest
            and plan.semantic_resolution_receipt_digest
            == binding.semantic_resolution_receipt_digest
            == context.semantic_resolution_receipt_digest
        )
        checks["acl"] = (
            "PASS" if acl_ok else "FAIL",
            "CHECK_PASSED" if acl_ok else "ACL_CONTEXT_CHAIN_MISMATCH",
            {
                "principal_digest": _digest(context.principal_id),
                "purpose_digest": _digest(context.purpose),
                "acl_projection_digest": context.acl_projection_digest,
                "question_digest": context.question_digest,
                "retrieval_receipt_digest": context.retrieval_receipt_digest,
                "semantic_resolution_receipt_digest": context.semantic_resolution_receipt_digest,
            },
        )
        schema_ok = (
            catalog.snapshot_digest == bundle.catalog_snapshot_digest
            and catalog.schema_digest == bundle.schema_digest
            and all(item is not None for item in field_columns)
            and all(item is not None for item in catalog_tables)
        )
        checks["schema_existence"] = (
            "PASS" if schema_ok else "FAIL",
            "CHECK_PASSED" if schema_ok else "SCHEMA_OBJECT_OR_DIGEST_MISMATCH",
            {"schema": catalog.schema_digest, "fields": [item.model_dump(mode="json") for item in binding.field_bindings]},
        )
        types_ok = all(
            column is not None
            and self._compatible(field.logical_type, field.mapped_type)
            and (
                temporal_encoding_check(
                    column.data_type, field.logical_type,
                    field.temporal_encoding,
                )['compatible']
                if field.temporal_encoding is not None else
                self._compatible(field.mapped_type, column.data_type)
            )
            for field, column in zip(binding.field_bindings, field_columns)
        )
        checks["type_compatibility"] = (
            "PASS" if types_ok else "FAIL",
            "CHECK_PASSED" if types_ok else "TYPE_INCOMPATIBLE",
            {"types": ([
                (
                    item.logical_type, item.mapped_type,
                    item.temporal_encoding.model_dump(mode='json')
                    if item.temporal_encoding is not None else None,
                ) for item in binding.field_bindings
            ] if any(item.temporal_encoding is not None
                     for item in binding.field_bindings) else [
                (item.logical_type, item.mapped_type)
                for item in binding.field_bindings
            ])},
        )
        keys_ok = True
        for relationship in binding.relationship_path:
            left = catalog.column(
                relationship.left_field.source_id,
                relationship.left_field.table,
                relationship.left_field.column,
            )
            right = catalog.column(
                relationship.right_field.source_id,
                relationship.right_field.table,
                relationship.right_field.column,
            )
            if left is None or right is None:
                keys_ok = False
            elif relationship.cardinality == "many_to_one" and not right.unique:
                keys_ok = False
            elif relationship.cardinality == "one_to_one" and not (
                left.unique and right.unique
            ):
                keys_ok = False
        checks["key_validity"] = (
            "PASS" if keys_ok else "FAIL",
            "CHECK_PASSED" if keys_ok else "JOIN_KEY_NOT_UNIQUE",
            {"relationships": [item.relation_id for item in binding.relationship_path]},
        )
        connected_tables = {binding.source_tables[0]} if binding.source_tables else set()
        for relationship in binding.relationship_path:
            connected_tables.add((relationship.left_field.source_id, relationship.left_field.table))
            connected_tables.add((relationship.right_field.source_id, relationship.right_field.table))
        connectivity_ok = connected_tables == set(binding.source_tables)
        checks["join_connectivity"] = (
            "PASS" if connectivity_ok else "FAIL",
            "CHECK_PASSED" if connectivity_ok else "JOIN_GRAPH_DISCONNECTED",
            {"sources": binding.source_tables, "relations": [item.relation_id for item in binding.relationship_path]},
        )
        authority_ok = all(
            item.authority_basis in policy.allowed_relationship_authorities
            and item.physically_validated
            for item in binding.relationship_path
        )
        checks["relationship_authority"] = (
            "PASS" if authority_ok else "FAIL",
            "CHECK_PASSED" if authority_ok else "RELATIONSHIP_AUTHORITY_INVALID",
            {"authorities": [item.authority_basis for item in binding.relationship_path]},
        )
        fanout_ok = all(
            item.cardinality not in {"one_to_many", "many_to_many", "stored_row_association"} for item in binding.relationship_path
        )
        checks["cardinality_and_fanout"] = (
            "PASS" if fanout_ok else "FAIL",
            "CHECK_PASSED" if fanout_ok else "UNSAFE_CARDINALITY",
            {"cardinalities": [item.cardinality for item in binding.relationship_path]},
        )
        bound_ids = {field.logical_id for field in binding.field_bindings}
        grain_ok = all(item in bound_ids for item in resolved_intent.candidate.grain)
        metric_contract_by_id = {item.metric_id: item for item in plan.metric_contracts}
        for metric_id in resolved_intent.candidate.metric_ids:
            metric_entry = domain_by_id.get(metric_id)
            metric_contract = metric_contract_by_id.get(metric_id)
            metric_grain_value = metric_entry.payload.get("grain") if metric_entry else None
            metric_grain = (
                (str(metric_grain_value),)
                if isinstance(metric_grain_value, str)
                else tuple(str(item) for item in metric_grain_value or ())
            )
            if metric_contract is None or metric_contract.grain != metric_grain:
                grain_ok = False
        checks["grain"] = (
            "PASS" if grain_ok else "FAIL",
            "CHECK_PASSED" if grain_ok else "GRAIN_BINDING_MISSING",
            {"grain": resolved_intent.candidate.grain},
        )
        numeric = {"number", "float", "decimal", "integer", "int", "real", "numeric"}
        numeric_fields = [
            field for field in binding.field_bindings
            if field.logical_type.casefold() in numeric
        ]
        unit_applicable = bool(numeric_fields)
        unit_ok = True
        unit_reason = "CHECK_PASSED"
        field_by_logical_id = {
            field.logical_id: field for field in binding.field_bindings
        }
        projected_ids = {
            projection.logical_id for projection in plan.projection_bindings
        }
        for field in numeric_fields:
            entry = domain_by_id.get(field.logical_id)
            contract = entry.payload.get("unit_contract") if entry else None
            if entry is not None and entry.payload.get("unit_semantics") is not None:
                unit_semantics = entry.payload.get("unit_semantics")
                unit_ref = entry.payload.get("unit_ref")
                if unit_semantics == "declared":
                    valid = bool(unit_ref) and str(unit_ref) == field.unit
                elif unit_semantics == "dimensionless":
                    valid = field.unit in {None, "1"}
                elif unit_semantics == "not_applicable":
                    valid = False
                else:
                    valid = False
                if not valid:
                    unit_ok = False
                    unit_reason = "UNIT_CONTRACT_INVALID"
                    break
                continue
            if not isinstance(contract, dict) or contract.get("applicability") == "unknown":
                unit_ok = False
                unit_reason = "UNIT_APPLICABILITY_UNKNOWN"
                break
            applicability_value = contract.get("applicability")
            validated = contract.get("validated") is True
            contract_unit = contract.get("unit")
            unit_property_ref = contract.get("unit_property_ref")
            if applicability_value == "measurement":
                if contract_unit:
                    valid = validated and contract_unit == field.unit
                elif unit_property_ref:
                    unit_field = field_by_logical_id.get(str(unit_property_ref))
                    valid = (
                        validated
                        and field.unit == f"property-ref:{unit_property_ref}"
                        and unit_field is not None
                        and unit_field.logical_type.casefold()
                        in {"string", "text", "varchar", "char"}
                        and unit_field.source_id == field.source_id
                        and unit_field.table == field.table
                        and str(unit_property_ref) in projected_ids
                    )
                else:
                    valid = False
            elif applicability_value == "dimensionless":
                valid = validated and field.unit == "1" and contract_unit == "1"
            elif applicability_value == "not_applicable":
                valid = validated and entry.payload.get("semantic_role") in {
                    "identifier", "ordinal", "count"
                }
            else:
                valid = False
            if not valid:
                unit_ok = False
                unit_reason = "UNIT_CONTRACT_INVALID"
                break
        checks["unit"] = (
            "PASS" if unit_ok else "FAIL",
            unit_reason,
            {
                "units": [
                    (
                        item.logical_id,
                        item.unit,
                        (domain_by_id[item.logical_id].payload.get("unit_contract") or {}).get(
                            "applicability"
                        ) if item.logical_id in domain_by_id else None,
                        (domain_by_id[item.logical_id].payload.get("unit_contract") or {}).get(
                            "unit_property_ref"
                        ) if item.logical_id in domain_by_id else None,
                    )
                    for item in numeric_fields
                ],
            },
        )
        time_range = resolved_intent.candidate.time_range
        time_ok = time_range is None or bool(
            domain_by_id.get(time_range.property_id)
            and domain_by_id[time_range.property_id].payload.get("time_semantics")
        )
        checks["time_semantics"] = (
            "PASS" if time_ok else "FAIL",
            "CHECK_PASSED" if time_ok else "TIME_SEMANTICS_MISSING",
            {"time_range": time_range.model_dump(mode="json") if time_range else None},
        )
        freshness_status = {
            "CURRENT": ("PASS", "CHECK_PASSED"),
            "STALE": ("FAIL", "SCHEMA_STALE"),
            "UNKNOWN": ("PARTIAL", "FRESHNESS_NOT_ESTABLISHED"),
        }[catalog.freshness_status]
        checks["freshness_and_drift"] = (
            freshness_status[0], freshness_status[1],
            {"freshness": catalog.freshness_status, "captured_at": catalog.captured_at},
        )
        compiler_ok = (
            policy.required_dialect in catalog.supported_dialects
            and set(plan.operator_sequence) <= set(catalog.supported_operators)
            and catalog.capability_digest == bundle.capability_digest
        )
        checks["compiler_capability"] = (
            "PASS" if compiler_ok else "FAIL",
            "CHECK_PASSED" if compiler_ok else "COMPILER_CAPABILITY_UNSUPPORTED",
            {"dialect": policy.required_dialect, "operators": plan.operator_sequence},
        )
        estimated_rows = sum(item.estimated_rows for item in catalog_tables if item is not None)
        cost_ok = (
            len({source for source, _table in binding.source_tables})
            <= policy.max_physical_sources
            and len(binding.source_tables) <= policy.max_scan_tables
            and estimated_rows <= policy.max_estimated_rows
            and plan.limit <= policy.max_result_rows
            and policy.timeout_seconds <= 30
        )
        checks["cost_row_time_bounds"] = (
            "PASS" if cost_ok else "FAIL",
            "CHECK_PASSED" if cost_ok else "COST_ROW_OR_TIME_BOUND_EXCEEDED",
            {"estimated_rows": estimated_rows, "limit": plan.limit, "timeout": policy.timeout_seconds},
        )
        read_only_ok = all(
            catalog.source(source) is not None and bool(catalog.source(source).read_only)
            for source, _table in binding.source_tables
        )
        checks["read_only"] = (
            "PASS" if read_only_ok else "FAIL",
            "CHECK_PASSED" if read_only_ok else "SOURCE_NOT_READ_ONLY",
            {"sources": [source for source, _table in binding.source_tables]},
        )
        receipt_binding_ok = (
            self._binding_content_digest(binding) == binding.binding_digest
            and plan.filter_expression == conjoin_appended_filters(
                resolved_intent.candidate.filter_expression,
                len(resolved_intent.candidate.filters),
                2 if resolved_intent.candidate.time_range else 0,
            )
            and self._plan_content_digest(plan) == plan.plan_digest
            and
            plan.semantic_context_digest == binding.semantic_context_digest == context.context_digest
            and plan.semantic_bundle_digest == binding.semantic_bundle_digest == context.semantic_bundle_digest
            and plan.semantic_bundle_content_digest
            == binding.semantic_bundle_content_digest
            == context.semantic_bundle_content_digest
            and plan.intent_digest == resolved_intent.intent_digest
            and plan.binding_digest == binding.binding_digest
            and plan.active_release_digest == bundle.active_release_digest
            and plan.domain_profile_digest
            == binding.domain_profile_digest
            == context.domain_profile_digest
            and plan.mapping_profile_digest
            == binding.mapping_profile_digest
            == context.mapping_profile_digest
            and plan.query_profile_digest
            == binding.query_profile_digest
            == context.query_profile_digest
            and plan.catalog_snapshot_digest
            == binding.catalog_snapshot_digest
            == context.catalog_snapshot_digest
            and plan.catalog_snapshot_content_digest
            == binding.catalog_snapshot_content_digest
            == context.catalog_snapshot_content_digest
            and plan.schema_digest == binding.schema_digest == context.schema_digest
            and plan.capability_digest
            == binding.capability_digest
            == context.capability_digest
            and plan.policy_digest == policy.policy_digest
        )
        checks["release_and_receipt_binding"] = (
            "PASS" if receipt_binding_ok else "FAIL",
            "CHECK_PASSED" if receipt_binding_ok else "PLAN_CONTEXT_BINDING_MISMATCH",
            {
                "plan": plan.plan_digest,
                "binding": binding.binding_digest,
                "context": context.context_digest,
                "release": bundle.active_release_digest,
                "domain_profile": bundle.domain_profile_digest,
                "mapping_profile": bundle.mapping_profile_digest,
                "query_profile": bundle.query_profile_digest,
                "catalog": catalog.snapshot_digest,
                "schema": catalog.schema_digest,
                "capability": catalog.capability_digest,
                "policy": policy.policy_digest,
            },
        )

        emitted: list[SemanticPlanCheck] = []
        join_applicable = bool(plan.joins)
        time_applicable = bool(
            resolved_intent.candidate.time_range or plan.latest or plan.metric_contracts
        )
        applicability = {
            "key_validity": join_applicable,
            "join_connectivity": join_applicable,
            "relationship_authority": join_applicable,
            "cardinality_and_fanout": join_applicable,
            "time_semantics": time_applicable,
            "unit": unit_applicable,
        }
        for name in self.REQUIRED_CHECKS:
            status, reason, evidence = checks[name]
            applicable = applicability.get(name, True)
            required = applicable
            if not applicable:
                status, reason = "SKIP", (
                    "NO_JOIN_IN_PLAN" if name in {
                        "key_validity", "join_connectivity", "relationship_authority",
                        "cardinality_and_fanout",
                    } else (
                        "NO_TIME_OPERATOR" if name == "time_semantics"
                        else "NO_UNIT_BEARING_FIELD"
                    )
                )
            safe_evidence = {
                "schema": "boi-check-evidence/v1",
                "run_id": run.record_id,
                "check_name": name,
                "applicable": applicable,
                "required": required,
                "status": status,
                "reason_code": reason,
                "projection": evidence,
            }
            evidence_ref, evidence_digest = evidence_store.put(safe_evidence)
            inputs_digest = _digest({
                "run_id": run.record_id,
                "name": name,
                "plan_digest": plan.plan_digest,
                "bundle_digest": bundle.bundle_digest,
                "catalog_snapshot_digest": catalog.snapshot_digest,
                "policy_digest": policy.policy_digest,
            })
            record = ledger.append(
                RecordKind.CHECK,
                {
                    "run_id": run.record_id,
                    "scope": "generic_query_planning",
                    "name": name,
                    "status": status,
                    "applicable": applicable,
                    "required": required,
                    "reason_code": reason,
                    "evidence_ref": evidence_ref,
                    "evidence_digest": evidence_digest,
                    "inputs_digest": inputs_digest,
                    "plan_digest": plan.plan_digest,
                },
                authority="mapping_validator",
                occurred_at=occurred_at,
            )
            emitted.append(SemanticPlanCheck(
                check_id=record.record_id,
                name=name,
                status=status,
                applicable=applicable,
                required=required,
                evidence_ref=evidence_ref,
                evidence_digest=evidence_digest,
                reason_code=reason,
                inputs_digest=inputs_digest,
            ))
        required = tuple(item for item in emitted if item.required)
        required_count = len(required)
        status, reason_codes, passing_count = reduce_required_check_statuses(
            tuple(item.status for item in required)
        )
        if status == "FAIL":
            reason_codes = tuple(dict.fromkeys((
                *reason_codes,
                *(item.reason_code for item in required if item.status != "PASS"),
            )))
        values = {
            "status": status,
            "reason_codes": reason_codes,
            "run_id": run.record_id,
            "check_ids": tuple(item.check_id for item in emitted),
            "checks": tuple(emitted),
            "required_check_count": required_count,
            "passing_required_check_count": passing_count,
            "passing_check_count": sum(item.status == "PASS" for item in emitted),
            "semantic_context_digest": context.context_digest,
            "question_digest": context.question_digest,
            "retrieval_receipt_digest": context.retrieval_receipt_digest,
            "semantic_resolution_receipt_digest": context.semantic_resolution_receipt_digest,
            "principal_id": context.principal_id,
            "purpose": context.purpose,
            "acl_projection_digest": context.acl_projection_digest,
            "semantic_bundle_digest": context.semantic_bundle_digest,
            "semantic_bundle_content_digest": context.semantic_bundle_content_digest,
            "plan_digest": plan.plan_digest,
            "intent_digest": resolved_intent.intent_digest,
            "active_release_digest": bundle.active_release_digest,
            "domain_profile_digest": context.domain_profile_digest,
            "mapping_profile_digest": context.mapping_profile_digest,
            "query_profile_digest": context.query_profile_digest,
            "catalog_snapshot_digest": catalog.snapshot_digest,
            "catalog_snapshot_content_digest": context.catalog_snapshot_content_digest,
            "schema_digest": context.schema_digest,
            "capability_digest": context.capability_digest,
            "policy_digest": policy.policy_digest,
            "validator_digest": _digest(self.VALIDATOR_ID),
        }
        return SemanticPlanValidationReceipt(**values, receipt_digest=_digest({
            **values,
            "checks": [item.model_dump(mode="json") for item in emitted],
        }))


class SemanticPlanVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    error_codes: tuple[str, ...]


class SemanticPlanValidationVerifier:
    def verify(
        self, receipt: SemanticPlanValidationReceipt, *, ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore,
    ) -> SemanticPlanVerification:
        errors: list[str] = []
        if _digest(receipt.model_dump(mode="json", exclude={"receipt_digest"})) != receipt.receipt_digest:
            errors.append("VALIDATION_RECEIPT_DIGEST_INVALID")
        if tuple(item.name for item in receipt.checks) != SemanticPlanValidator.REQUIRED_CHECKS:
            errors.append("VALIDATION_CHECK_SET_INCOMPLETE")
        if receipt.check_ids != tuple(item.check_id for item in receipt.checks):
            errors.append("VALIDATION_CHECK_ID_SET_MISMATCH")
        if len(receipt.check_ids) != len(set(receipt.check_ids)):
            errors.append("VALIDATION_CHECK_ID_DUPLICATE")
        required = tuple(item for item in receipt.checks if item.required)
        reduced_status, _root_reasons, passing_required = reduce_required_check_statuses(
            tuple(item.status for item in required)
        )
        if (
            receipt.required_check_count != len(required)
            or receipt.passing_required_check_count != passing_required
            or receipt.passing_check_count
            != sum(item.status == "PASS" for item in receipt.checks)
        ):
            errors.append("VALIDATION_CHECK_COUNT_MISMATCH")
        if receipt.status != reduced_status:
            errors.append("VALIDATION_STATUS_REDUCTION_MISMATCH")
        try:
            run_record = ledger.read(receipt.run_id)
        except Exception:
            errors.append("VALIDATION_RUN_LEDGER_RECORD_MISSING")
        else:
            if run_record.kind is not RecordKind.RUN:
                errors.append("VALIDATION_RUN_LEDGER_RECORD_KIND_INVALID")
            expected_run = {
                "scope": "generic_query_planning",
                "plan_digest": receipt.plan_digest,
                "intent_digest": receipt.intent_digest,
                "active_release_digest": receipt.active_release_digest,
                "catalog_snapshot_digest": receipt.catalog_snapshot_digest,
                "policy_digest": receipt.policy_digest,
                "semantic_context_digest": receipt.semantic_context_digest,
            }
            if any(
                run_record.payload.get(field) != value
                for field, value in expected_run.items()
            ):
                errors.append("VALIDATION_RUN_LEDGER_BINDING_MISMATCH")
        for check in receipt.checks:
            try:
                record = ledger.read(check.check_id)
            except Exception:
                errors.append("CHECK_LEDGER_RECORD_MISSING")
                continue
            if record.kind is not RecordKind.CHECK:
                errors.append("CHECK_LEDGER_RECORD_KIND_INVALID")
            if (
                record.payload.get("run_id") != receipt.run_id
                or record.payload.get("plan_digest") != receipt.plan_digest
            ):
                errors.append("CHECK_LEDGER_RUN_BINDING_MISMATCH")
            for field in (
                "status", "applicable", "required", "reason_code", "evidence_ref",
                "evidence_digest", "inputs_digest",
            ):
                expected = getattr(check, field)
                if record.payload.get(field) != expected:
                    errors.append("CHECK_LEDGER_BINDING_MISMATCH")
                    break
            evidence_error = evidence_store.verify(check.evidence_ref, check.evidence_digest)
            if evidence_error:
                errors.append(evidence_error)
        return SemanticPlanVerification(ok=not errors, error_codes=tuple(sorted(set(errors))))
