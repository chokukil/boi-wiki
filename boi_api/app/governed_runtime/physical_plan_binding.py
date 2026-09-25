"""Bind a semantic result-shape plan to active Mapping profile revisions."""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field

from .generic_result_shape_planner import GenericLogicalResultShapePlan
from .multi_result_query_gateway import (
    AuthorizedPhysicalMapping,
    MultiResultAggregate,
    MultiResultExistenceConstraint,
    MultiResultExistenceHop,
    MultiResultFilter,
    MultiResultLatest,
    MultiResultParentLink,
    MultiResultProjection,
    MultiResultSetPlan,
)
from .semantic_profile_loader import SemanticContextBundle
from .semantic_authority import DefinitionAuthority, require_same_semantic_authority


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class PhysicalPlanBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_plan_digest: str
    mapping_profile_digest: str
    schema_digest: str
    result_sets: tuple[MultiResultSetPlan, ...]
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    reviewed_definition_authority: DefinitionAuthority | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    binding_digest: str


class PhysicalPlanBinder:
    """Resolve only query-local logical properties through Mapping revisions."""

    def bind(
        self,
        plan: GenericLogicalResultShapePlan,
        *,
        bundle: SemanticContextBundle,
    ) -> PhysicalPlanBinding:
        require_same_semantic_authority(plan, bundle)
        by_domain: dict[str, object] = {}
        for entry in bundle.mapping_entries:
            domain_ref = str(entry.payload.get("domain_ref") or "")
            if not domain_ref or entry.payload.get("data_type") == "relationship":
                continue
            if domain_ref in by_domain:
                raise ValueError("PHYSICAL_PROPERTY_MAPPING_NOT_UNIQUE")
            by_domain[domain_ref] = entry

        required = (
            {
                projection.property_ref
                for result_set in plan.result_sets
                for projection in result_set.projections
            }
            | {
                aggregation.target_ref
                for result_set in plan.result_sets
                for aggregation in result_set.aggregations
            }
            | {
                item.property_ref
                for result_set in plan.result_sets
                for item in result_set.filters
            }
            | {
                item
                for result_set in plan.result_sets
                if result_set.latest is not None
                for item in (
                    *result_set.latest.partition_by,
                    *result_set.latest.ordering,
                )
            }
            | {
                property_ref
                for result_set in plan.result_sets
                for constraint in result_set.existence_constraints
                for property_ref in (
                    *(
                        value
                        for hop in constraint.hops
                        for value in (
                            hop.parent_property_ref,
                            hop.child_property_ref,
                        )
                    ),
                    *(item.property_ref for item in constraint.filters),
                )
            }
        )
        mappings: dict[str, AuthorizedPhysicalMapping] = {}
        mapping_for_property: dict[str, AuthorizedPhysicalMapping] = {}
        for property_ref in sorted(required):
            entry = by_domain.get(property_ref)
            if entry is None or entry.availability != "bound" or entry.physical is None:
                raise ValueError("QUERY_LOCAL_MAPPING_NOT_BOUND")
            mapping_ref = str(entry.payload.get("mapping_id") or entry.entry_id)
            physical = AuthorizedPhysicalMapping(
                mapping_ref=mapping_ref,
                source_id=entry.physical.source,
                table=entry.physical.table,
                column=entry.physical.column,
                revision_digest=entry.revision_digest,
                temporal_encoding=entry.payload.get("temporal_encoding"),
            )
            mappings[mapping_ref] = physical
            mapping_for_property[property_ref] = physical

        mapping_entry_by_id = {
            str(entry.payload.get("mapping_id") or entry.entry_id): entry
            for entry in bundle.mapping_entries
        }
        domain_by_id = {entry.entry_id: entry for entry in bundle.domain_entries}
        relationship_contracts = {
            str(entry.payload["relationship_contract"]["contract_id"]):
            entry.payload["relationship_contract"]
            for entry in bundle.mapping_entries
            if isinstance(entry.payload.get("relationship_contract"), dict)
        }

        def authorized(mapping_ref: str) -> AuthorizedPhysicalMapping:
            existing = mappings.get(mapping_ref)
            if existing is not None:
                return existing
            entry = mapping_entry_by_id.get(mapping_ref)
            if (
                entry is None
                or entry.availability != "bound"
                or entry.physical is None
            ):
                raise ValueError("QUERY_LOCAL_MAPPING_NOT_BOUND")
            value = AuthorizedPhysicalMapping(
                mapping_ref=mapping_ref,
                source_id=entry.physical.source,
                table=entry.physical.table,
                column=entry.physical.column,
                revision_digest=entry.revision_digest,
                temporal_encoding=entry.payload.get("temporal_encoding"),
            )
            mappings[mapping_ref] = value
            domain_ref = str(entry.payload.get("domain_ref") or "")
            if domain_ref:
                mapping_for_property.setdefault(domain_ref, value)
            return value

        def output_name(logical_ref: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]+", "_", logical_ref).strip("_").casefold()

        output_names = {
            result_set.result_set_id: {
                projection.property_ref: projection.output_name
                for projection in result_set.projections
            }
            for result_set in plan.result_sets
        }
        physical_sets: list[MultiResultSetPlan] = []
        for result_set in plan.result_sets:
            result_mappings = tuple(
                mapping_for_property[item.property_ref]
                for item in result_set.projections
            )
            source_tables = {(item.source_id, item.table) for item in result_mappings}
            if result_set.role == "SCALAR":
                source_tables = {
                    (mapping_for_property[item.target_ref].source_id,
                     mapping_for_property[item.target_ref].table)
                    for item in result_set.aggregations
                } | {
                    (mapping_for_property[item.property_ref].source_id,
                     mapping_for_property[item.property_ref].table)
                    for item in result_set.filters
                }
            if len(source_tables) != 1:
                raise ValueError("RESULT_SET_PHYSICAL_SOURCE_NOT_UNIQUE")
            source_id, table = next(iter(source_tables))
            parent_link = None
            many_to_many_contract: dict[str, object] | None = None
            if result_set.parent_link is not None:
                candidate_contract = relationship_contracts.get(
                    result_set.parent_link.relationship_ref
                )
                if candidate_contract is not None and (
                    candidate_contract.get("cardinality") == "many_to_many"
                ):
                    many_to_many_contract = candidate_contract
                parent_names = output_names[result_set.parent_link.parent_result_set_id]
                child_names = output_names[result_set.result_set_id]
                parent_link = MultiResultParentLink(
                    parent_result_set_id=result_set.parent_link.parent_result_set_id,
                    parent_key_outputs=tuple(
                        parent_names[item]
                        for item in result_set.parent_link.parent_property_refs
                    ),
                    child_key_outputs=tuple(
                        child_names[item]
                        for item in result_set.parent_link.child_property_refs
                    ),
                    relationship_contract_id=result_set.parent_link.relationship_ref,
                )

            if many_to_many_contract is not None and parent_link is not None:
                relationship_ref = result_set.parent_link.relationship_ref
                parent_result = next(
                    item for item in plan.result_sets
                    if item.result_set_id == result_set.parent_link.parent_result_set_id
                )
                left_endpoint = str(many_to_many_contract["left_endpoint_ref"])
                right_endpoint = str(many_to_many_contract["right_endpoint_ref"])
                physical_keys = dict(many_to_many_contract["physical_keys"])
                if parent_result.object_ref == left_endpoint:
                    bridge_parent_refs = tuple(physical_keys["left_mapping_refs"])
                    bridge_child_refs = tuple(physical_keys["right_mapping_refs"])
                elif parent_result.object_ref == right_endpoint:
                    bridge_parent_refs = tuple(physical_keys["right_mapping_refs"])
                    bridge_child_refs = tuple(physical_keys["left_mapping_refs"])
                else:
                    raise ValueError("MANY_TO_MANY_PARENT_ENDPOINT_MISMATCH")
                if len(bridge_parent_refs) != 1 or len(bridge_child_refs) != 1:
                    raise ValueError("MANY_TO_MANY_BRIDGE_KEY_ARITY_UNSUPPORTED")
                bridge_object_ref = str(
                    many_to_many_contract.get("relationship_identity_ref") or ""
                )
                bridge_domain = domain_by_id.get(bridge_object_ref)
                bridge_identity_ref = (
                    str(bridge_domain.payload.get("identity_property_ref") or "")
                    if bridge_domain is not None else ""
                )
                if not bridge_identity_ref:
                    raise ValueError("MANY_TO_MANY_BRIDGE_IDENTITY_REQUIRED")
                bridge_identity_mapping = mapping_for_property.get(bridge_identity_ref)
                if bridge_identity_mapping is None:
                    bridge_identity_mapping = authorized(
                        str(next(
                            entry.payload.get("mapping_id") or entry.entry_id
                            for entry in bundle.mapping_entries
                            if entry.payload.get("domain_ref") == bridge_identity_ref
                        ))
                    )
                bridge_parent_mapping = authorized(str(bridge_parent_refs[0]))
                bridge_child_mapping = authorized(str(bridge_child_refs[0]))
                bridge_tables = {
                    (item.source_id, item.table)
                    for item in (
                        bridge_identity_mapping,
                        bridge_parent_mapping,
                        bridge_child_mapping,
                    )
                }
                if len(bridge_tables) != 1:
                    raise ValueError("MANY_TO_MANY_BRIDGE_SOURCE_NOT_UNIQUE")
                bridge_source, bridge_table = next(iter(bridge_tables))
                bridge_id_output = output_name(bridge_identity_ref)
                bridge_parent_output = output_name(
                    str(mapping_entry_by_id[str(bridge_parent_refs[0])].payload["domain_ref"])
                )
                bridge_child_output = output_name(
                    str(mapping_entry_by_id[str(bridge_child_refs[0])].payload["domain_ref"])
                )
                bridge_result_id = f"result:{output_name(bridge_object_ref)}:relationship"
                physical_sets.append(MultiResultSetPlan(
                    result_set_id=bridge_result_id,
                    role="RELATIONSHIP",
                    object_ref=bridge_object_ref,
                    source_id=bridge_source,
                    table=bridge_table,
                    projections=(
                        MultiResultProjection(
                            mapping_ref=bridge_identity_mapping.mapping_ref,
                            column=bridge_identity_mapping.column,
                            output_name=bridge_id_output,
                        ),
                        MultiResultProjection(
                            mapping_ref=bridge_parent_mapping.mapping_ref,
                            column=bridge_parent_mapping.column,
                            output_name=bridge_parent_output,
                        ),
                        MultiResultProjection(
                            mapping_ref=bridge_child_mapping.mapping_ref,
                            column=bridge_child_mapping.column,
                            output_name=bridge_child_output,
                        ),
                    ),
                    exact_grain=(bridge_id_output,),
                    filters=(),
                    parent_link=MultiResultParentLink(
                        parent_result_set_id=parent_link.parent_result_set_id,
                        parent_key_outputs=parent_link.parent_key_outputs,
                        child_key_outputs=(bridge_parent_output,),
                        relationship_contract_id=relationship_ref,
                    ),
                    ordering=(bridge_id_output,),
                    completeness_policy=result_set.completeness_policy,
                    coverage_semantics="SPARSE_ONLY",
                    result_row_limit=result_set.result_row_limit,
                ))
                parent_link = MultiResultParentLink(
                    parent_result_set_id=bridge_result_id,
                    parent_key_outputs=(bridge_child_output,),
                    child_key_outputs=parent_link.child_key_outputs,
                    relationship_contract_id=relationship_ref,
                )
            aggregates = tuple(
                MultiResultAggregate(
                    reducer=item.reducer,
                    mapping_ref=mapping_for_property[item.target_ref].mapping_ref,
                    column=mapping_for_property[item.target_ref].column,
                    output_name=item.output_name,
                )
                for item in result_set.aggregations
            )
            projection_outputs = output_names[result_set.result_set_id]
            physical_sets.append(
                MultiResultSetPlan(
                    result_set_id=result_set.result_set_id,
                    role=result_set.role,
                    object_ref=result_set.object_ref,
                    source_id=source_id,
                    table=table,
                    projections=tuple(
                        MultiResultProjection(
                            mapping_ref=mapping.mapping_ref,
                            column=mapping.column,
                            output_name=projection.output_name,
                        )
                        for projection, mapping in zip(
                            result_set.projections, result_mappings
                        )
                    ),
                    aggregations=aggregates,
                    filter_expression=result_set.filter_expression,
                    filters=tuple(
                        MultiResultFilter(
                            mapping_ref=mapping_for_property[
                                item.property_ref
                            ].mapping_ref,
                            operator=item.operator,
                            parameter_name=item.parameter_name,
                        )
                        for item in result_set.filters
                    ),
                    existence_constraints=tuple(
                        MultiResultExistenceConstraint(
                            filter_object_ref=constraint.filter_object_ref,
                            polarity=constraint.polarity,
                            hops=tuple(
                                MultiResultExistenceHop(
                                    parent_object_ref=hop.parent_object_ref,
                                    child_object_ref=hop.child_object_ref,
                                    parent_source_id=mapping_for_property[
                                        hop.parent_property_ref
                                    ].source_id,
                                    parent_table=mapping_for_property[
                                        hop.parent_property_ref
                                    ].table,
                                    source_id=mapping_for_property[
                                        hop.child_property_ref
                                    ].source_id,
                                    table=mapping_for_property[
                                        hop.child_property_ref
                                    ].table,
                                    parent_mapping_ref=mapping_for_property[
                                        hop.parent_property_ref
                                    ].mapping_ref,
                                    parent_column=mapping_for_property[
                                        hop.parent_property_ref
                                    ].column,
                                    child_mapping_ref=mapping_for_property[
                                        hop.child_property_ref
                                    ].mapping_ref,
                                    child_column=mapping_for_property[
                                        hop.child_property_ref
                                    ].column,
                                    relationship_contract_id=hop.relationship_ref,
                                )
                                for hop in constraint.hops
                            ),
                            filters=tuple(
                                MultiResultFilter(
                                    mapping_ref=mapping_for_property[
                                        item.property_ref
                                    ].mapping_ref,
                                    operator=item.operator,
                                    parameter_name=item.parameter_name,
                                )
                                for item in constraint.filters
                            ),
                        )
                        for constraint in result_set.existence_constraints
                    ),
                    exact_grain=tuple(
                        projection_outputs[item] for item in result_set.exact_grain
                    ),
                    parent_link=parent_link,
                    latest=(
                        MultiResultLatest(
                            partition_by=tuple(
                                projection_outputs[item]
                                for item in result_set.latest.partition_by
                            ),
                            ordering=tuple(
                                projection_outputs[item]
                                for item in result_set.latest.ordering
                            ),
                            ordering_directions=result_set.latest.ordering_directions,
                            selection_policy=(
                                {
                                    "contract_digest": result_set.latest.selection_contract.contract_digest,
                                    "versioning_digest": result_set.latest.selection_contract.versioning_digest,
                                    "version_identity_output": projection_outputs[result_set.latest.selection_contract.version_identity_ref],
                                    "null_time_policy": result_set.latest.selection_contract.null_time_policy,
                                    "null_business_key_policy": result_set.latest.selection_contract.null_business_key_policy,
                                    "time_ordering": result_set.latest.selection_contract.time_ordering,
                                } if result_set.latest.selection_contract is not None else None
                            ),
                        )
                        if result_set.latest is not None
                        else None
                    ),
                    ordering=tuple(
                        projection_outputs[item] for item in result_set.ordering
                    ),
                    completeness_policy=result_set.completeness_policy,
                    coverage_semantics=result_set.coverage_semantics,
                    zero_fill_aggregate_outputs=tuple(
                        item.output_name for item in aggregates
                    )
                    if result_set.coverage_semantics == "ROOT_COMPLETE_ZERO_FILL"
                    else (),
                    result_row_limit=result_set.result_row_limit,
                    ordering_directions=result_set.ordering_directions,
                    row_limit_policy=result_set.row_limit_policy,
                    paging_policy=result_set.paging_policy,
                )
            )

        values = {
            "semantic_plan_digest": plan.plan_digest,
            "mapping_profile_digest": bundle.mapping_profile_digest,
            "schema_digest": bundle.schema_digest,
            "result_sets": tuple(
                item.model_dump(mode="json") for item in physical_sets
            ),
            "physical_mappings": tuple(
                item.model_dump(mode="json") for item in mappings.values()
            ),
            **({"reviewed_definition_authority":
                    plan.reviewed_definition_authority.model_dump(mode="json")}
                if plan.reviewed_definition_authority is not None else {}),
        }
        return PhysicalPlanBinding(
            semantic_plan_digest=plan.plan_digest,
            mapping_profile_digest=bundle.mapping_profile_digest,
            schema_digest=bundle.schema_digest,
            result_sets=tuple(physical_sets),
            physical_mappings=tuple(mappings.values()),
            reviewed_definition_authority=plan.reviewed_definition_authority,
            binding_digest=_digest(values),
        )


__all__ = ["PhysicalPlanBinder", "PhysicalPlanBinding"]
