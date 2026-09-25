"""Bind active-Release profile entries to the cardinality-aware C2 solver."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .cardinality_query_shape import (
    CardinalityAwareQueryShapeSolver,
    DataQualityReceipt,
    QueryShapeRequest,
    RelationshipContract,
    ResultShapeContract,
    ShapeSolverOutcome,
    validate_directional_quality_closure,
)
from .semantic_profile_loader import LoadedProfileEntry, SemanticContextBundle
from .semantic_authority import (
    DefinitionAuthority,
    SemanticAuthorityFields,
    semantic_authority_values,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class CardinalityProfileBindingError(RuntimeError):
    pass


class ContractProfileSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_kind: Literal["relationship", "data_quality", "result_shape"]
    contract_id: str
    entry_id: str
    revision_id: str
    revision_digest: str
    evidence_resources: tuple[str, ...]


class CardinalityProfileContracts(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    active_release_digest: str | None
    semantic_bundle_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    catalog_snapshot_digest: str
    capability_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    schema_digest: str
    relationships: tuple[RelationshipContract, ...]
    result_shapes: tuple[ResultShapeContract, ...]
    quality_receipts: tuple[DataQualityReceipt, ...]
    sources: tuple[ContractProfileSource, ...]
    binding_digest: str


class ProfileBoundShapeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"]
    profile_contracts: CardinalityProfileContracts
    solver_outcome: ShapeSolverOutcome
    receipt_digest: str
    projection_receipt: dict | None = None
    reviewed_definition_authority: DefinitionAuthority | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_serializer(mode='wrap')
    def preserve_original(self, handler):
        value=handler(self)
        if self.projection_receipt is None: value.pop('projection_receipt',None)
        return value

    @model_validator(mode="after")
    def exact_reviewed_authority(self):
        if self.reviewed_definition_authority != self.profile_contracts.reviewed_definition_authority:
            raise ValueError("SHAPE_SELECTION_SEMANTIC_AUTHORITY_MISMATCH")
        return self


def _source(
    *, kind: Literal["relationship", "data_quality", "result_shape"],
    contract_id: str,
    entry: LoadedProfileEntry,
) -> ContractProfileSource:
    return ContractProfileSource(
        contract_kind=kind,
        contract_id=contract_id,
        entry_id=entry.entry_id,
        revision_id=entry.revision_id,
        revision_digest=entry.revision_digest,
        evidence_resources=entry.evidence_resources,
    )


def bind_cardinality_profile_contracts(
    bundle: SemanticContextBundle,
) -> CardinalityProfileContracts:
    """Extract only strict contracts from the exact ACL-projected bundle."""

    domain_ids = {item.entry_id for item in bundle.domain_entries}
    mapping_by_id = {
        str(item.payload.get("mapping_id") or item.entry_id): item
        for item in bundle.mapping_entries
    }
    relationships: list[RelationshipContract] = []
    shapes: list[ResultShapeContract] = []
    qualities: list[DataQualityReceipt] = []
    sources: list[ContractProfileSource] = []

    for entry in bundle.mapping_entries:
        raw_relationship = entry.payload.get("relationship_contract")
        raw_quality = entry.payload.get("data_quality_receipt")
        directional_quality = entry.payload.get("directional_quality_receipts")
        if raw_relationship is None and raw_quality is None and directional_quality is None:
            continue
        if raw_relationship is None or (raw_quality is None and directional_quality is None):
            raise CardinalityProfileBindingError("RELATIONSHIP_QUALITY_PAIR_REQUIRED")
        relationship = RelationshipContract.model_validate(raw_relationship)
        if directional_quality is not None:
            if raw_quality is not None or not isinstance(directional_quality,list):
                raise CardinalityProfileBindingError("DIRECTIONAL_QUALITY_CONTRACT_INVALID")
            entry_qualities = tuple(DataQualityReceipt.model_validate(item) for item in directional_quality)
            try:
                validate_directional_quality_closure(relationship, entry_qualities)
            except ValueError as error:
                raise CardinalityProfileBindingError(str(error)) from error
        else:
            entry_qualities = (DataQualityReceipt.model_validate(raw_quality),)
            if relationship.cardinality == "stored_row_association":
                try:
                    validate_directional_quality_closure(relationship, entry_qualities)
                except ValueError as error:
                    raise CardinalityProfileBindingError(str(error)) from error
        if entry.availability != "bound" or entry.physical is None:
            raise CardinalityProfileBindingError("PHYSICAL_RELATIONSHIP_MAPPING_NOT_BOUND")
        if entry.payload.get("domain_ref") != relationship.contract_id:
            raise CardinalityProfileBindingError("RELATIONSHIP_DOMAIN_REF_MISMATCH")
        if relationship.contract_id not in domain_ids:
            raise CardinalityProfileBindingError("RELATIONSHIP_DOMAIN_ENTRY_NOT_FOUND")
        if any(quality.relationship_contract_digest != relationship.contract_digest for quality in entry_qualities):
            raise CardinalityProfileBindingError("QUALITY_RELATIONSHIP_DIGEST_MISMATCH")
        physical_closure = []
        for mapping_ref in (
            *relationship.physical_keys.left_mapping_refs,
            *relationship.physical_keys.right_mapping_refs,
        ):
            key_mapping = mapping_by_id.get(mapping_ref)
            if (
                key_mapping is None
                or key_mapping.availability != "bound"
                or key_mapping.physical is None
            ):
                raise CardinalityProfileBindingError("PHYSICAL_KEY_MAPPING_NOT_BOUND")
            physical_closure.append({"mapping_ref":mapping_ref,"source_id":key_mapping.physical.source,
                "table":key_mapping.physical.table,"column":key_mapping.physical.column,
                "revision_digest":key_mapping.revision_digest})
        if any(quality.directional_scope is not None and (directional_quality is not None or relationship.cardinality == "stored_row_association")
            and quality.directional_scope.mapping_closure_digest != _digest(physical_closure) for quality in entry_qualities):
            raise CardinalityProfileBindingError("QUALITY_MAPPING_CLOSURE_MISMATCH")
        relationships.append(relationship)
        qualities.extend(entry_qualities)
        sources.append(_source(kind="relationship", contract_id=relationship.contract_id, entry=entry))
        sources.extend(_source(kind="data_quality", contract_id=quality.receipt_id, entry=entry) for quality in entry_qualities)

    for entry in bundle.query_entries:
        raw_shape = entry.payload.get("result_shape_contract")
        if raw_shape is None:
            continue
        shape = ResultShapeContract.model_validate(raw_shape)
        shapes.append(shape)
        sources.append(_source(kind="result_shape", contract_id=shape.contract_id, entry=entry))

    relationship_ids = [item.contract_id for item in relationships]
    shape_ids = [item.contract_id for item in shapes]
    quality_ids = [item.receipt_id for item in qualities]
    if len(relationship_ids) != len(set(relationship_ids)):
        raise CardinalityProfileBindingError("DUPLICATE_RELATIONSHIP_CONTRACT")
    if len(shape_ids) != len(set(shape_ids)):
        raise CardinalityProfileBindingError("DUPLICATE_RESULT_SHAPE_CONTRACT")
    if len(quality_ids) != len(set(quality_ids)):
        raise CardinalityProfileBindingError("DUPLICATE_DATA_QUALITY_RECEIPT")

    values = {
        **semantic_authority_values(bundle),
        "semantic_bundle_digest": bundle.bundle_digest,
        "principal_id": bundle.principal_id,
        "purpose": bundle.purpose,
        "acl_projection_digest": bundle.acl_projection_digest,
        "catalog_snapshot_digest": bundle.catalog_snapshot_digest,
        "capability_digest": bundle.capability_digest,
        "domain_profile_digest": bundle.domain_profile_digest,
        "mapping_profile_digest": bundle.mapping_profile_digest,
        "query_profile_digest": bundle.query_profile_digest,
        "schema_digest": bundle.schema_digest,
        "relationship_contract_digests": tuple(item.contract_digest for item in relationships),
        "result_shape_contract_digests": tuple(item.contract_digest for item in shapes),
        "data_quality_receipt_digests": tuple(item.receipt_digest for item in qualities),
        "sources": tuple(item.model_dump(mode="json") for item in sources),
    }
    return CardinalityProfileContracts(
        **semantic_authority_values(bundle),
        semantic_bundle_digest=bundle.bundle_digest,
        principal_id=bundle.principal_id,
        purpose=bundle.purpose,
        acl_projection_digest=bundle.acl_projection_digest,
        catalog_snapshot_digest=bundle.catalog_snapshot_digest,
        capability_digest=bundle.capability_digest,
        domain_profile_digest=bundle.domain_profile_digest,
        mapping_profile_digest=bundle.mapping_profile_digest,
        query_profile_digest=bundle.query_profile_digest,
        schema_digest=bundle.schema_digest,
        relationships=tuple(relationships),
        result_shapes=tuple(shapes),
        quality_receipts=tuple(qualities),
        sources=tuple(sources),
        binding_digest=_digest(values),
    )


def solve_profile_bound_query_shape(
    request: QueryShapeRequest,
    *,
    bundle: SemanticContextBundle,
    projection_policy: Literal['exact-v1','independent-subset-v1'] = 'exact-v1',
) -> ProfileBoundShapeSelection:
    contracts = bind_cardinality_profile_contracts(bundle)
    if request.active_schema_snapshot_digest != contracts.schema_digest:
        raise CardinalityProfileBindingError("REQUEST_BUNDLE_SCHEMA_DIGEST_MISMATCH")
    outcome = CardinalityAwareQueryShapeSolver().solve(
        request,
        relationships=contracts.relationships,
        result_shapes=contracts.result_shapes,
        quality_receipts=contracts.quality_receipts,
    )
    projection_receipt = None
    if (projection_policy == 'independent-subset-v1'
        and outcome.reason_codes == ('APPROVED_RESULT_SHAPE_NOT_FOUND',)):
        refs=tuple(item.contract_id for item in outcome.bound_relationships)
        # Only branch omission from a nested, non-aggregate contract at the same
        # root/grain. No joins, identities, policies or capabilities are invented.
        bases=[item for item in contracts.result_shapes
               if item.shape=='NestedCollection' and item.aggregation_semantics is None
               and item.root_object_ref==request.root_object_ref and item.exact_grain==request.exact_grain
               and refs and set(refs)<set(item.relationship_refs)]
        derived=[ResultShapeContract.model_validate({**base.model_dump(mode='json'),
            'contract_id':'derived:nested-subset:'+_digest({'base':base.contract_digest,'refs':refs})[7:],
            'relationship_refs':refs}) for base in bases]
        if derived:
            outcome=CardinalityAwareQueryShapeSolver().solve(request, relationships=contracts.relationships,
                result_shapes=tuple(derived),quality_receipts=contracts.quality_receipts)
            if outcome.status=='READY':
                base=bases[derived.index(outcome.selected_shape)]
                proof={'contract':'boi/independent-nested-subset@1','status':'PASS','source_shape_digest':base.contract_digest,
                    'derived_shape_digest':outcome.selected_shape.contract_digest,
                    'retained_relationships':refs,'omitted_relationships':tuple(sorted(set(base.relationship_refs)-set(refs))),
                    'profile_binding_digest':contracts.binding_digest,'schema_digest':contracts.schema_digest,
                    'policy':projection_policy,
                    'evidence_digest':_digest({'binding':contracts.binding_digest,'base':base.contract_digest,
                        'relationships':[r.contract_digest for r in outcome.bound_relationships]}),
                    'scope':'exploratory plan derivation; not a new canonical profile'}
                projection_receipt={**proof,'receipt_digest':_digest(proof)}
    values = {
        "status": outcome.status,
        "profile_contract_binding_digest": contracts.binding_digest,
        "solver_outcome_digest": outcome.outcome_digest,
        **semantic_authority_values(contracts),
        "principal_id": contracts.principal_id,
        "purpose": contracts.purpose,
        "acl_projection_digest": contracts.acl_projection_digest,
        "catalog_snapshot_digest": contracts.catalog_snapshot_digest,
        "capability_digest": contracts.capability_digest,
        "domain_profile_digest": contracts.domain_profile_digest,
        "mapping_profile_digest": contracts.mapping_profile_digest,
        "query_profile_digest": contracts.query_profile_digest,
        "schema_digest": contracts.schema_digest,
        **({'projection_receipt_digest':projection_receipt['receipt_digest']} if projection_receipt else {}),
    }
    return ProfileBoundShapeSelection(
        status=outcome.status,
        profile_contracts=contracts,
        solver_outcome=outcome,
        receipt_digest=_digest(values),
        projection_receipt=projection_receipt,
        reviewed_definition_authority=contracts.reviewed_definition_authority,
    )


__all__ = [
    "CardinalityProfileBindingError",
    "CardinalityProfileContracts",
    "ContractProfileSource",
    "ProfileBoundShapeSelection",
    "bind_cardinality_profile_contracts",
    "solve_profile_bound_query_shape",
]
