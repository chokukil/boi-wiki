"""Domain-neutral, value-grounded output of the canonical query runtime."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer
from .directional_quality_scope import DirectionalQualityScope
from .stored_row_association import StoredRowAssociationScope, OccurrenceAssociation
from .answer_meaning_context import AnswerMeaningContext, build_answer_meaning_context

from .cardinality_query_shape import DataQualityReceipt, ResultShapeContract
from .multi_result_query_gateway import (
    MultiResultLogicalPlan,
    MultiResultQueryExecution,
    MultiResultSetPlan,
    MultiResultSetResult,
)
from .query_answerability import QueryAnswerabilityReceipt
from .snapshot_result_paging import WithSnapshotPageAccess
from .latest_execution_quality import WithLatestQuality
from .query_gateway import QueryExecution
from .semantic_query_planner import (
    BindingResolutionOutcome,
    RelationalAst,
    SemanticPlanningContext,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _is_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _semantic_projection(value: object) -> dict[str, Any]:
    """Remove run-local provenance while retaining the governed answer meaning."""

    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)  # type: ignore[arg-type]
    )
    payload.pop("artifact_semantic_digest", None)
    execution = dict(payload["execution"])
    transient_evidence = {
        str(execution.get("execution_receipt_ref") or ""),
        str(execution.get("attestation_ref") or ""),
    }
    for key in (
        "execution_id",
        "execution_receipt_ref",
        "execution_receipt_digest",
        "attestation_ref",
    ):
        execution.pop(key, None)
    payload["execution"] = execution
    payload["evidence_refs"] = [
        item for item in payload.get("evidence_refs", []) if item not in transient_evidence
    ]
    payload.pop("resource_access_receipt_digest", None)
    payload.pop("resource_freeze_receipt_digest", None)
    result_sets = []
    for result_set in payload.get("result_sets", []):
        semantic_result = dict(result_set)
        semantic_result.pop("protected_artifact_ref", None)
        if semantic_result.get("paging"):
            paging = dict(semantic_result["paging"])
            for field in ("paging_ref", "page_receipt_digest", "expires_at", "next_cursor", "count_receipt_digest"):
                paging.pop(field, None)
            semantic_result["paging"] = paging
        result_sets.append(semantic_result)
    payload["result_sets"] = result_sets
    return payload


class ArtifactOrdering(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    output_name: str
    direction: Literal["ASC", "DESC"]


class ArtifactAggregation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    output_name: str
    reducer: Literal["count_rows", "count", "count_distinct", "sum", "average", "min", "max", "ratio"]
    unit: str | None


class ArtifactField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    output_name: str
    label: str
    value_type: str
    unit: str | None
    mapping_ref: str
    mapping_revision_digest: str
    evidence_refs: tuple[str, ...]

    @field_validator("mapping_revision_digest")
    @classmethod
    def require_mapping_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_ARTIFACT_MAPPING_DIGEST_INVALID")
        return value


class ArtifactRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identity: tuple[tuple[str, str], ...]
    occurrence_ref: tuple[str,str,int] | None = Field(default=None,exclude_if=lambda v:v is None)
    values: dict[str, Any]


class ArtifactParentLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_result_set_id: str
    relationship_contract_id: str
    parent_key_outputs: tuple[str, ...]
    child_key_outputs: tuple[str, ...]


class ArtifactResultSet(WithLatestQuality):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    role: Literal["ROOT", "CHILD", "RELATIONSHIP", "AGGREGATE", "SCALAR"]
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
        "ScalarAggregate",
    ]
    object_ref: str
    # An empty grain is the exact, zero-dimensional grain of one global
    # aggregate row.  Every object-backed result remains identity-bearing.
    exact_grain: tuple[str, ...]
    row_identity_outputs: tuple[str, ...]
    identity_semantics: Literal["RESULT_SNAPSHOT_ORDINAL"] | None = Field(default=None,exclude_if=lambda v:v is None)
    parent_link: ArtifactParentLink | None
    fields: tuple[ArtifactField, ...] = Field(min_length=1)
    rows: tuple[ArtifactRow, ...]
    ordering: tuple[ArtifactOrdering, ...]
    latest_ordering: tuple[ArtifactOrdering, ...]
    aggregations: tuple[ArtifactAggregation, ...]
    completeness_policy: str
    coverage_semantics: str
    coverage_missing_parent_count: int = Field(ge=0)
    coverage_zero_filled_count: int = Field(ge=0)
    total_row_count: int = Field(ge=0)
    preview_row_count: int = Field(ge=0)
    truncated: bool
    protected_artifact_ref: str | None
    result_digest: str

    @model_validator(mode="after")
    def validate_result_set(self) -> "ArtifactResultSet":
        if self.paging and (self.paging.total_row_count != self.total_row_count or
                            self.paging.returned_row_count != self.preview_row_count):
            raise ValueError("ANSWER_ARTIFACT_PAGING_COUNT_MISMATCH")
        if not _is_digest(self.result_digest):
            raise ValueError("ANSWER_ARTIFACT_RESULT_DIGEST_INVALID")
        if self.preview_row_count != len(self.rows):
            raise ValueError("ANSWER_ARTIFACT_PREVIEW_COUNT_INVALID")
        if self.preview_row_count > self.total_row_count:
            raise ValueError("ANSWER_ARTIFACT_TOTAL_COUNT_INVALID")
        if self.truncated != (self.preview_row_count < self.total_row_count):
            raise ValueError("ANSWER_ARTIFACT_TRUNCATION_INVALID")
        outputs = {field.output_name for field in self.fields}
        if not self.row_identity_outputs and not (
            self.role in {"AGGREGATE", "SCALAR"} and not self.exact_grain
            or self.identity_semantics == "RESULT_SNAPSHOT_ORDINAL"
        ):
            raise ValueError("ANSWER_ARTIFACT_IDENTITY_REQUIRED")
        if self.identity_semantics == "RESULT_SNAPSHOT_ORDINAL" and (self.row_identity_outputs or any(row.identity or row.occurrence_ref is None for row in self.rows)):
            raise ValueError("ANSWER_ARTIFACT_OCCURRENCE_IDENTITY_REQUIRED")
        if not set(self.row_identity_outputs) <= outputs:
            raise ValueError("ANSWER_ARTIFACT_IDENTITY_FIELD_MISSING")
        if any(set(row.values) != outputs for row in self.rows):
            raise ValueError("ANSWER_ARTIFACT_ROW_FIELD_CLOSURE_INVALID")
        if any(
            tuple(name for name, _value in row.identity) != self.row_identity_outputs
            for row in self.rows
        ):
            raise ValueError("ANSWER_ARTIFACT_ROW_IDENTITY_INVALID")
        return self


class ArtifactDataQualityDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    relationship_contract_digest: str
    scanned_rows: int
    matched_rows: int
    unmatched_rows: int
    null_fk_rows: int
    orphan_rows: int
    duplicate_key_rows: int
    excluded_rows: int
    coverage_ratio: float
    applied_policy: str
    evidence_ref: str
    evidence_digest: str
    receipt_digest: str
    directional_scope: DirectionalQualityScope | StoredRowAssociationScope | None = None

    @model_serializer(mode="wrap")
    def preserve_v1_disclosure(self, handler):
        value = handler(self)
        if self.directional_scope is None:
            value.pop("directional_scope", None)
        return value


class ArtifactExecutionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    lane: Literal["attested", "exploratory"]
    classification: Literal["ATTESTED", "PROVISIONAL"]
    execution_receipt_ref: str
    execution_receipt_digest: str
    logical_plan_digest: str
    source_snapshot_digest: str
    result_digest: str
    attestation_state: Literal["PASS", "FAIL", "ABSENT"]
    attestation_ref: str | None
    attestation_digest: str | None

    @model_validator(mode="after")
    def validate_execution(self) -> "ArtifactExecutionEvidence":
        required = (
            self.execution_receipt_digest,
            self.logical_plan_digest,
            self.source_snapshot_digest,
            self.result_digest,
        )
        if not all(_is_digest(value) for value in required):
            raise ValueError("ANSWER_ARTIFACT_EXECUTION_DIGEST_INVALID")
        if self.classification == "ATTESTED" and self.attestation_state != "PASS":
            raise ValueError("ANSWER_ARTIFACT_ATTESTATION_REQUIRED")
        if self.attestation_state == "ABSENT" and (
            self.attestation_ref is not None or self.attestation_digest is not None
        ):
            raise ValueError("ANSWER_ARTIFACT_ATTESTATION_REF_FORBIDDEN")
        return self


class GovernedAnswerArtifact(BaseModel):
    """Immutable semantic answer; transport channel is deliberately absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-governed-answer-artifact/v1", "boi-governed-answer-artifact/v2", "boi-governed-answer-artifact/v3"] = (
        "boi-governed-answer-artifact/v1"
    )
    question_digest: str
    resolved_intent_digest: str
    answerability_state: str
    answerability_receipt_digest: str
    principal_digest: str
    purpose_digest: str
    active_release_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    profile_bundle_digest: str
    catalog_snapshot_digest: str
    schema_digest: str
    policy_digest: str
    result_shape: str
    result_shape_contract_digest: str | None
    root_object_ref: str
    exact_grain: tuple[str, ...]
    result_sets: tuple[ArtifactResultSet, ...] = Field(min_length=1)
    data_quality: tuple[ArtifactDataQualityDisclosure, ...]
    occurrence_associations: tuple[OccurrenceAssociation,...] = Field(default=(),exclude_if=lambda v:not v)
    evidence_refs: tuple[str, ...]
    execution: ArtifactExecutionEvidence
    resource_access_receipt_digest: str
    resource_freeze_receipt_digest: str
    meaning_context: AnswerMeaningContext | None = None
    raw_sql_exposed: Literal[False] = False
    model_repaired_sql: Literal[False] = False
    artifact_semantic_digest: str

    @model_serializer(mode='wrap')
    def preserve_historical_wire(self, handler):
        value = handler(self)
        if self.meaning_context is None:
            value.pop('meaning_context', None)
        return value

    def _authority_digest_values(self):
        return (self.question_digest, self.active_release_digest)

    def _review_and_resource_digest_values(self):
        return (self.answerability_receipt_digest,
                self.resource_access_receipt_digest, self.resource_freeze_receipt_digest)

    @model_validator(mode="after")
    def validate_artifact(self) -> "GovernedAnswerArtifact":
        digests = (
            self.resolved_intent_digest,
            self.principal_digest,
            self.purpose_digest,
            self.domain_profile_digest,
            self.mapping_profile_digest,
            self.query_profile_digest,
            self.profile_bundle_digest,
            self.catalog_snapshot_digest,
            self.schema_digest,
            self.policy_digest,
            self.artifact_semantic_digest,
        ) + self._authority_digest_values() + self._review_and_resource_digest_values()
        if not all(_is_digest(value) for value in digests):
            raise ValueError("ANSWER_ARTIFACT_DIGEST_INVALID")
        if any(item.paging for item in self.result_sets) and self.schema_name.endswith("/v1"):
            raise ValueError("ANSWER_ARTIFACT_PAGING_REVISION_REQUIRED")
        if (self.meaning_context is not None) != (self.schema_name not in {
                'boi-governed-answer-artifact/v1', 'boi-governed-answer-artifact/v2'}):
            raise ValueError('ANSWER_ARTIFACT_MEANING_REVISION_REQUIRED')
        if self.meaning_context is not None:
            if self.meaning_context.input_context_digest != self.profile_bundle_digest:
                raise ValueError('ANSWER_ARTIFACT_MEANING_CONTEXT_MISMATCH')
            if _digest(self.meaning_context.resolved_intent) != self.resolved_intent_digest:
                raise ValueError('ANSWER_ARTIFACT_MEANING_INTENT_MISMATCH')
            meaning_refs = set(self.meaning_context.root_definition_refs)
            required_refs = {self.root_object_ref, *self.exact_grain}
            required_refs.update(field.field_ref for result in self.result_sets for field in result.fields)
            if not required_refs <= meaning_refs:
                raise ValueError('ANSWER_ARTIFACT_MEANING_RESULT_COVERAGE_REQUIRED')
        if self.result_shape_contract_digest is not None and not _is_digest(
            self.result_shape_contract_digest
        ):
            raise ValueError("ANSWER_ARTIFACT_SHAPE_DIGEST_INVALID")
        if len({item.result_set_id for item in self.result_sets}) != len(
            self.result_sets
        ):
            raise ValueError("ANSWER_ARTIFACT_RESULT_SET_DUPLICATE")
        if not self.exact_grain and self.result_shape not in {"Aggregate", "ScalarAggregate"}:
            raise ValueError("ANSWER_ARTIFACT_EXACT_GRAIN_REQUIRED")
        if self.artifact_semantic_digest != _digest(_semantic_projection(self)):
            raise ValueError("ANSWER_ARTIFACT_SEMANTIC_DIGEST_MISMATCH")
        return self


def _quality_disclosures(
    receipts: Sequence[DataQualityReceipt],
) -> tuple[ArtifactDataQualityDisclosure, ...]:
    return tuple(
        ArtifactDataQualityDisclosure(
            receipt_id=item.receipt_id,
            relationship_contract_digest=item.relationship_contract_digest,
            scanned_rows=item.scanned_rows,
            matched_rows=item.matched_rows,
            unmatched_rows=item.unmatched_rows,
            null_fk_rows=item.null_fk_rows,
            orphan_rows=item.orphan_rows,
            duplicate_key_rows=item.duplicate_key_rows,
            excluded_rows=item.excluded_rows,
            coverage_ratio=item.coverage_ratio,
            applied_policy=item.applied_orphan_policy,
            evidence_ref=item.evidence_ref,
            evidence_digest=item.evidence_digest,
            receipt_digest=item.receipt_digest,
            directional_scope=item.directional_scope,
        )
        for item in receipts
    )


class GovernedAnswerArtifactBuilder:
    @staticmethod
    def _field_maps(context: SemanticPlanningContext):
        domains = {item.entry_id: item for item in context.bundle.domain_entries}
        mappings = {
            str(item.payload.get("mapping_id") or item.entry_id): item
            for item in context.bundle.mapping_entries
        }
        return domains, mappings

    @staticmethod
    def _artifact_field(
        *,
        logical_id: str,
        output_name: str,
        mapping_ref: str,
        context: SemanticPlanningContext,
        mapping_revision_digest: str,
        mapping_evidence: Sequence[str] = (),
        unit: str | None = None,
        source_logical_id: str | None = None,
        reducer: str | None = None,
    ) -> ArtifactField:
        domains, _mappings = GovernedAnswerArtifactBuilder._field_maps(context)
        domain = domains.get(logical_id)
        payload = domain.payload if domain is not None else {}
        source_domain = domains.get(source_logical_id) if source_logical_id else None
        type_payload = payload
        if not payload.get("value_type") and not payload.get("value_type_ref") and source_domain:
            type_payload = source_domain.payload
        value_type = domains.get(str(type_payload.get("value_type_ref") or ""))
        value_payload = (
            value_type.payload if value_type and value_type.payload.get("kind") == "ValueType" else {}
        )
        primitive = str(type_payload.get("value_type") or value_payload.get("primitive_type") or "")
        count = reducer in {"count_rows", "count", "count_distinct", "distinct_count"}
        if count:
            primitive = "integer"
        elif reducer in {"average", "ratio", "sum"} and primitive in {"integer", "number"}:
            primitive = "number"
        if primitive not in {"string", "integer", "number", "boolean", "date", "datetime", "duration"}:
            raise ValueError("ANSWER_ARTIFACT_VALUE_TYPE_UNRESOLVED")
        resolved_unit = None if count else (
            unit or payload.get("unit") or payload.get("unit_ref")
            or type_payload.get("unit") or type_payload.get("unit_ref")
            or value_payload.get("unit_ref")
        )
        evidence = tuple(dict.fromkeys(
            [*(domain.evidence_resources if domain is not None else ()),
             *(source_domain.evidence_resources if source_domain else ()),
             *(value_type.evidence_resources if value_type else ()), *mapping_evidence]
        ))
        return ArtifactField(
            field_ref=logical_id,
            output_name=output_name,
            # count_rows uses the mapped property only to anchor the table;
            # naming its output after that property's ID mislabels the count.
            label="기록 행 수" if reducer == "count_rows" else str(payload.get("name") or logical_id),
            value_type=primitive,
            unit=str(resolved_unit) if resolved_unit is not None else None,
            mapping_ref=mapping_ref,
            mapping_revision_digest=mapping_revision_digest,
            evidence_refs=evidence,
        )

    @staticmethod
    def _rows(
        rows: Sequence[dict[str, Any]],
        *,
        fields: Sequence[ArtifactField],
        identity_outputs: tuple[str, ...],
    ) -> tuple[ArtifactRow, ...]:
        outputs = tuple(item.output_name for item in fields)
        return tuple(
            ArtifactRow(
                identity=tuple((name, str(row[name])) for name in identity_outputs),
                values={name: row[name] for name in outputs},
            )
            for row in rows
        )

    @classmethod
    def build_single(
        cls,
        *,
        context: SemanticPlanningContext,
        binding: BindingResolutionOutcome,
        plan: RelationalAst,
        execution: QueryExecution,
        shape_contract: ResultShapeContract | None,
        quality_receipts: Sequence[DataQualityReceipt],
        answerability: QueryAnswerabilityReceipt,
        resource_access_receipt_digest: str,
        resource_freeze_receipt_digest: str,
    ) -> GovernedAnswerArtifact:
        by_logical = {item.logical_id: item for item in binding.field_bindings}
        fields: list[ArtifactField] = []
        logical_outputs: dict[str, str] = {}
        for projection in plan.projection_bindings:
            bound = by_logical[projection.logical_id]
            logical_outputs[projection.logical_id] = projection.output_alias
            fields.append(cls._artifact_field(
                logical_id=projection.logical_id,
                output_name=projection.output_alias,
                mapping_ref=bound.mapping_id,
                context=context,
                mapping_revision_digest=bound.mapping_revision_digest,
                mapping_evidence=bound.evidence_resources,
                unit=bound.unit,
            ))
        aggregations: list[ArtifactAggregation] = []
        semantic_dependencies = dict(binding.semantic_dependency_bindings)
        for aggregate in plan.aggregates:
            # Metrics and entity counts are semantic expressions.  The binder
            # records the physical property that actually supplies their
            # values, so preserve the semantic field_ref while grounding the
            # displayed value in that exact mapping.
            bound = by_logical.get(aggregate.logical_id) or by_logical.get(
                semantic_dependencies.get(aggregate.logical_id, "")
            )
            if bound is None:
                raise ValueError("ANSWER_ARTIFACT_AGGREGATE_BINDING_MISSING")
            logical_outputs[aggregate.logical_id] = aggregate.output_alias
            fields.append(cls._artifact_field(
                logical_id=aggregate.logical_id,
                output_name=aggregate.output_alias,
                mapping_ref=bound.mapping_id,
                context=context,
                mapping_revision_digest=bound.mapping_revision_digest,
                mapping_evidence=bound.evidence_resources,
                unit=bound.unit,
                source_logical_id=bound.logical_id,
                reducer=aggregate.operator,
            ))
            aggregations.append(ArtifactAggregation(
                field_ref=aggregate.logical_id,
                output_name=aggregate.output_alias,
                reducer=(
                    "count_distinct"
                    if aggregate.operator == "distinct_count"
                    else aggregate.operator
                ),
                unit=fields[-1].unit,
            ))
        identity_outputs = tuple(logical_outputs[item] for item in plan.group_by) if plan.aggregates else tuple(
            logical_outputs[item] for item in context.resolved_intent.candidate.grain
        )
        if not identity_outputs and not plan.aggregates:
            identity_outputs = (fields[0].output_name,)
        ordering = tuple(
            ArtifactOrdering(
                field_ref=item.logical_id,
                output_name=logical_outputs.get(
                    item.logical_id, f"hidden:{item.logical_id}"
                ),
                direction=item.direction,
            )
            for item in plan.ordering
        )
        latest = tuple(
            ArtifactOrdering(
                field_ref=item.logical_id,
                output_name=logical_outputs.get(
                    item.logical_id, f"hidden:{item.logical_id}"
                ),
                direction=item.direction,
            )
            for item in (plan.latest.ordering if plan.latest is not None else ())
        )
        shape = shape_contract.shape if shape_contract is not None else (
            "Aggregate" if plan.aggregates else "ObjectSet"
        )
        result_set = ArtifactResultSet(
            result_set_id="result:root",
            role="AGGREGATE" if plan.aggregates else "ROOT",
            shape=shape,
            object_ref=(shape_contract.root_object_ref if shape_contract is not None
                        else context.resolved_intent.candidate.entity_ids[0]),
            exact_grain=context.resolved_intent.candidate.grain,
            row_identity_outputs=identity_outputs,
            parent_link=None,
            fields=tuple(fields),
            rows=cls._rows(
                execution.result.rows,
                fields=fields,
                identity_outputs=identity_outputs,
            ),
            ordering=ordering,
            latest_ordering=latest,
            aggregations=tuple(aggregations),
            completeness_policy=(
                shape_contract.completeness_policy
                if shape_contract is not None
                else "PROVISIONAL_SNAPSHOT"
            ),
            coverage_semantics="SPARSE_ONLY",
            coverage_missing_parent_count=0,
            coverage_zero_filled_count=0,
            total_row_count=execution.result.row_count,
            preview_row_count=execution.result.row_count,
            truncated=False,
            protected_artifact_ref=None,
            result_digest=execution.result.result_digest,
        )
        attestation = execution.attestation
        evidence = ArtifactExecutionEvidence(
            execution_id=execution.execution_id,
            lane=execution.lane,
            classification=execution.result_status,
            execution_receipt_ref=f"query-execution-receipt:{execution.execution_id}",
            execution_receipt_digest=_digest(execution.receipt),
            logical_plan_digest=execution.receipt.logical_plan_digest,
            source_snapshot_digest=execution.receipt.source_snapshot,
            result_digest=execution.result.result_digest,
            attestation_state=attestation.status if attestation is not None else "ABSENT",
            attestation_ref=(
                f"query-attestation:{execution.execution_id}"
                if attestation is not None else None
            ),
            attestation_digest=_digest(attestation) if attestation is not None else None,
        )
        return cls._build(
            context=context,
            answerability=answerability,
            shape=shape,
            shape_contract=shape_contract,
            result_sets=(result_set,),
            quality_receipts=quality_receipts,
            execution=evidence,
            resource_access_receipt_digest=resource_access_receipt_digest,
            resource_freeze_receipt_digest=resource_freeze_receipt_digest,
        )

    @classmethod
    def build_multi(
        cls,
        *,
        context: SemanticPlanningContext,
        plan: MultiResultLogicalPlan,
        execution: MultiResultQueryExecution,
        shape_contract: ResultShapeContract,
        quality_receipts: Sequence[DataQualityReceipt],
        answerability: QueryAnswerabilityReceipt,
        resource_access_receipt_digest: str,
        resource_freeze_receipt_digest: str,
    ) -> GovernedAnswerArtifact:
        result_by_id = {item.result_set_id: item for item in execution.result.result_sets}
        result_sets = tuple(
            cls._multi_result_set(
                context=context,
                plan=item,
                result=result_by_id[item.result_set_id],
                protected_artifact_ref=execution.receipt.result_artifact_ref,
            )
            for item in plan.result_sets
        )
        associations=execution.result.occurrence_associations
        if associations:
            ids={a.root_result_set_id for a in associations}|{a.target_result_set_id for a in associations}
            result_sets=tuple(item.model_copy(update={
                "identity_semantics":"RESULT_SNAPSHOT_ORDINAL","row_identity_outputs":(),
                "rows":tuple(row.model_copy(update={"identity":(),
                    "occurrence_ref":(execution.result.run_id,item.result_set_id,index)})
                    for index,row in enumerate(item.rows))}) if item.result_set_id in ids else item
                for item in result_sets)
        evidence = ArtifactExecutionEvidence(
            execution_id=execution.execution_id,
            lane="exploratory",
            classification="PROVISIONAL",
            execution_receipt_ref=f"multi-result-execution-receipt:{execution.execution_id}",
            execution_receipt_digest=execution.receipt.receipt_digest,
            logical_plan_digest=execution.receipt.logical_plan_digest,
            source_snapshot_digest=execution.receipt.source_snapshot_digest,
            result_digest=execution.result.result_digest,
            attestation_state="ABSENT",
            attestation_ref=None,
            attestation_digest=None,
        )
        return cls._build(
            context=context,
            answerability=answerability,
            shape=shape_contract.shape,
            shape_contract=shape_contract,
            result_sets=result_sets,
            occurrence_associations=associations,
            quality_receipts=quality_receipts,
            execution=evidence,
            resource_access_receipt_digest=resource_access_receipt_digest,
            resource_freeze_receipt_digest=resource_freeze_receipt_digest,
        )

    @classmethod
    def _multi_result_set(
        cls,
        *,
        context: SemanticPlanningContext,
        plan: MultiResultSetPlan,
        result: MultiResultSetResult,
        protected_artifact_ref: str,
    ) -> ArtifactResultSet:
        _domains, mappings = cls._field_maps(context)
        fields: list[ArtifactField] = []
        for projection in plan.projections:
            mapping = mappings[projection.mapping_ref]
            logical_id = str(mapping.payload.get("domain_ref") or "")
            fields.append(cls._artifact_field(
                logical_id=logical_id,
                output_name=projection.output_name,
                mapping_ref=projection.mapping_ref,
                context=context,
                mapping_revision_digest=mapping.revision_digest,
                mapping_evidence=mapping.evidence_resources,
            ))
        aggregations: list[ArtifactAggregation] = []
        for aggregate in plan.aggregations:
            mapping = mappings[aggregate.mapping_ref]
            logical_id = str(mapping.payload.get("domain_ref") or "")
            field = cls._artifact_field(
                logical_id=logical_id,
                output_name=aggregate.output_name,
                mapping_ref=aggregate.mapping_ref,
                context=context,
                mapping_revision_digest=mapping.revision_digest,
                mapping_evidence=mapping.evidence_resources,
                reducer=aggregate.reducer,
            )
            fields.append(field)
            aggregations.append(ArtifactAggregation(
                field_ref=logical_id,
                output_name=aggregate.output_name,
                reducer=aggregate.reducer,
                unit=field.unit,
            ))
        directions = plan.ordering_directions or tuple("ASC" for _ in plan.ordering)
        ordering = tuple(
            ArtifactOrdering(
                field_ref=next(
                    item.field_ref for item in fields if item.output_name == output
                ),
                output_name=output,
                direction=direction,
            )
            for output, direction in zip(plan.ordering, directions)
        )
        latest = tuple(
            ArtifactOrdering(
                field_ref=next(
                    item.field_ref for item in fields if item.output_name == output
                ),
                output_name=output,
                direction=direction,
            )
            for output, direction in zip(
                plan.latest.ordering if plan.latest else (),
                plan.latest.ordering_directions if plan.latest else (),
            )
        )
        parent = plan.parent_link
        shape = (
            "ScalarAggregate" if plan.role == "SCALAR"
            else "Aggregate" if plan.role == "AGGREGATE"
            else "LinkedObjectSet" if plan.role == "RELATIONSHIP"
            else "NestedCollection" if parent is not None
            else "ObjectSet"
        )
        return ArtifactResultSet(
            result_set_id=plan.result_set_id,
            role=plan.role,
            shape=shape,
            object_ref=plan.object_ref,
            exact_grain=plan.exact_grain,
            row_identity_outputs=plan.exact_grain,
            parent_link=(
                ArtifactParentLink(
                    parent_result_set_id=parent.parent_result_set_id,
                    relationship_contract_id=parent.relationship_contract_id,
                    parent_key_outputs=parent.parent_key_outputs,
                    child_key_outputs=parent.child_key_outputs,
                )
                if parent is not None else None
            ),
            fields=tuple(fields),
            rows=cls._rows(
                result.rows, fields=fields, identity_outputs=plan.exact_grain
            ),
            ordering=ordering,
            latest_ordering=latest,
            aggregations=tuple(aggregations),
            completeness_policy=result.completeness_policy,
            latest_policy=result.latest_policy,
            latest_quality=result.latest_quality,
            temporal_predicate_quality=result.temporal_predicate_quality,
            coverage_semantics=result.coverage_semantics,
            coverage_missing_parent_count=result.coverage_missing_parent_count,
            coverage_zero_filled_count=result.coverage_zero_filled_count,
            total_row_count=result.row_count,
            preview_row_count=result.returned_row_count,
            truncated=result.truncated,
            protected_artifact_ref=(protected_artifact_ref if result.truncated else None),
            result_digest=result.result_digest,
            paging=result.paging,
        )

    @classmethod
    def _build(
        cls, *, answerability: QueryAnswerabilityReceipt, **kwargs,
    ) -> GovernedAnswerArtifact:
        values = cls._build_values(answerability_state=answerability.state,
            answerability_receipt_digest=answerability.receipt_digest, **kwargs)
        return GovernedAnswerArtifact.model_validate({**values,
            "artifact_semantic_digest": _digest(_semantic_projection(values))})

    @classmethod
    def _build_values(
        cls,
        *,
        context: SemanticPlanningContext,
        answerability_state: str,
        answerability_receipt_digest: str | None,
        shape: str,
        shape_contract: ResultShapeContract | None,
        result_sets: tuple[ArtifactResultSet, ...],
        quality_receipts: Sequence[DataQualityReceipt],
        execution: ArtifactExecutionEvidence,
        resource_access_receipt_digest: str | None,
        resource_freeze_receipt_digest: str | None,
        occurrence_associations: tuple[OccurrenceAssociation,...] = (),
    ) -> dict[str, Any]:
        quality = _quality_disclosures(quality_receipts)
        from .semantic_intent import SemanticIntentResolver
        candidate = context.resolved_intent.candidate
        roots = SemanticIntentResolver._referenced_ids(candidate)
        roots.update(field.field_ref for result in result_sets for field in result.fields)
        roots.update(item.object_ref for item in result_sets)
        if shape_contract is not None:
            roots.update(shape_contract.relationship_refs)
            roots.add(shape_contract.root_object_ref)
            roots.update(shape_contract.exact_grain)
        meaning = build_answer_meaning_context(entries=context.bundle.domain_entries,
            root_refs=tuple(roots), input_context_digest=context.semantic_bundle_digest,
            resolved_intent=candidate.model_dump(mode='json'),
            result_shape_contract=shape_contract.model_dump(mode='json') if shape_contract else None)
        evidence_refs = tuple(dict.fromkeys(
            [
                *(ref for item in result_sets for field in item.fields for ref in field.evidence_refs),
                *(ref for definition in meaning.definitions for ref in definition.evidence_refs),
                *(item.evidence_ref for item in quality),
                execution.execution_receipt_ref,
                *( (execution.attestation_ref,) if execution.attestation_ref else () ),
            ]
        ))
        values = {
            "schema_name": "boi-governed-answer-artifact/v3",
            **({"occurrence_associations":[a.model_dump(mode="json") for a in occurrence_associations]} if occurrence_associations else {}),
            "question_digest": context.question_digest,
            "resolved_intent_digest": context.resolved_intent.intent_digest,
            "answerability_state": answerability_state,
            "answerability_receipt_digest": answerability_receipt_digest,
            "principal_digest": _digest(context.principal_id),
            "purpose_digest": _digest(context.purpose),
            "active_release_digest": context.active_release_digest,
            "domain_profile_digest": context.domain_profile_digest,
            "mapping_profile_digest": context.mapping_profile_digest,
            "query_profile_digest": context.query_profile_digest,
            "profile_bundle_digest": context.semantic_bundle_digest,
            "catalog_snapshot_digest": context.catalog_snapshot_digest,
            "schema_digest": context.schema_digest,
            "policy_digest": context.planning_policy_digest,
            "result_shape": shape,
            "result_shape_contract_digest": (
                shape_contract.contract_digest if shape_contract is not None else None
            ),
            "root_object_ref": (
                shape_contract.root_object_ref
                if shape_contract is not None else candidate.entity_ids[0]
            ),
            "exact_grain": (
                shape_contract.exact_grain
                if shape_contract is not None else candidate.grain
            ),
            "result_sets": [item.model_dump(mode="json") for item in result_sets],
            "data_quality": [item.model_dump(mode="json") for item in quality],
            "evidence_refs": evidence_refs,
            "execution": execution.model_dump(mode="json"),
            "resource_access_receipt_digest": resource_access_receipt_digest,
            "resource_freeze_receipt_digest": resource_freeze_receipt_digest,
            "meaning_context": meaning.model_dump(mode='json'),
            "raw_sql_exposed": False,
            "model_repaired_sql": False,
        }
        return values


__all__ = [
    "ArtifactDataQualityDisclosure",
    "ArtifactExecutionEvidence",
    "ArtifactField",
    "ArtifactResultSet",
    "GovernedAnswerArtifact",
    "GovernedAnswerArtifactBuilder",
]
