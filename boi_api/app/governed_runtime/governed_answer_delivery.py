"""Channel-neutral delivery from governed execution to one answer record."""

from __future__ import annotations

import hashlib
import hmac
import json
import base64
import csv
import io
import time
from collections.abc import Mapping, Sequence
from typing import Any, Callable, Literal, Protocol
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .answer_contract_v2 import AnswerRequirementContractV2
from .answer_quality import (
    DeterministicAnswerComposer,
    FrozenAnswerResultSet,
    FrozenDisplayField,
    VerifiedAnswerEnvelope,
    validate_answer_contract,
    AnswerViewModel,
)
from .multi_result_query_gateway import MultiResultQueryExecution, MultiResultSetResult
from .query_gateway import QueryExecution, QueryResult
from .governed_answer_artifact import GovernedAnswerArtifact


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


class AnswerDeliveryError(ValueError):
    """Execution or answer authority cannot be safely joined."""


class AnswerDeliveryStore(Protocol):
    def put(self, collection: str, key: str, value: dict) -> None: ...
    def get(self, collection: str, key: str): ...
    def list(self, collection: str, *, limit: int = 100): ...


class AnswerFieldBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    source_field: str
    mapping_ref: str

    @field_validator("field_ref", "source_field", "mapping_ref")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ANSWER_FIELD_BINDING_REQUIRED")
        return value


class AnswerResultBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    row_identity_fields: tuple[str, ...] = Field(min_length=1)
    parent_key_fields: tuple[str, ...] = ()
    child_key_fields: tuple[str, ...] = ()
    fields: tuple[AnswerFieldBinding, ...] = Field(min_length=1)
    source_ordering: tuple[str, ...]
    source_latest_ordering: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_binding(self) -> "AnswerResultBinding":
        refs = tuple(item.field_ref for item in self.fields)
        sources = tuple(item.source_field for item in self.fields)
        if len(refs) != len(set(refs)) or len(sources) != len(set(sources)):
            raise ValueError("ANSWER_FIELD_BINDING_DUPLICATE")
        if len(self.row_identity_fields) != len(set(self.row_identity_fields)):
            raise ValueError("ANSWER_ROW_IDENTITY_DUPLICATE")
        if bool(self.parent_key_fields) != bool(self.child_key_fields):
            raise ValueError("ANSWER_PARENT_LINK_BINDING_INCOMPLETE")
        if len(self.parent_key_fields) != len(self.child_key_fields):
            raise ValueError("ANSWER_PARENT_LINK_BINDING_ARITY_MISMATCH")
        return self


class GovernedQueryAnswerDeliveryContext(BaseModel):
    """Server-owned handoff from planning/execution to answer delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-query-answer-delivery-context/v1"] = (
        "boi-query-answer-delivery-context/v1"
    )
    requirement: AnswerRequirementContractV2
    result_bindings: tuple[AnswerResultBinding, ...] = Field(min_length=1)
    quality_measurements: dict[str, int]
    quality_evidence_digests: dict[str, str]
    renderer_code_digest: str
    evaluator_code_digest: str
    prepared_answer_ref_exposed: Literal[False] = False
    context_digest: str

    @classmethod
    def create(
        cls,
        *,
        requirement: AnswerRequirementContractV2,
        result_bindings: Sequence[AnswerResultBinding],
        quality_measurements: Mapping[str, int],
        quality_evidence_digests: Mapping[str, str],
        renderer_code_digest: str,
        evaluator_code_digest: str,
    ) -> "GovernedQueryAnswerDeliveryContext":
        base = {
            "schema_name": "boi-query-answer-delivery-context/v1",
            "requirement": requirement.model_dump(mode="json"),
            "result_bindings": [item.model_dump(mode="json") for item in result_bindings],
            "quality_measurements": dict(quality_measurements),
            "quality_evidence_digests": dict(quality_evidence_digests),
            "renderer_code_digest": renderer_code_digest,
            "evaluator_code_digest": evaluator_code_digest,
            "prepared_answer_ref_exposed": False,
        }
        return cls.model_validate({**base, "context_digest": _digest(base)})

    @model_validator(mode="after")
    def validate_context(self) -> "GovernedQueryAnswerDeliveryContext":
        if not _is_digest(self.renderer_code_digest) or not _is_digest(
            self.evaluator_code_digest
        ):
            raise ValueError("ANSWER_DELIVERY_CONTEXT_CODE_DIGEST_INVALID")
        required = set(self.requirement.required_quality_disclosures)
        if not required <= set(self.quality_measurements) or not required <= set(
            self.quality_evidence_digests
        ):
            raise ValueError("ANSWER_DELIVERY_CONTEXT_QUALITY_INCOMPLETE")
        if any(
            not _is_digest(self.quality_evidence_digests[item]) for item in required
        ):
            raise ValueError("ANSWER_DELIVERY_CONTEXT_QUALITY_DIGEST_INVALID")
        unsigned = self.model_dump(mode="json", exclude={"context_digest"})
        if self.context_digest != _digest(unsigned):
            raise ValueError("ANSWER_DELIVERY_CONTEXT_DIGEST_MISMATCH")
        return self


class AnswerDeliveryCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: Literal[
        "execution_receipt_binding",
        "result_set_closure",
        "answer_contract_validation",
        "owner_acl_binding",
        "model_authority_boundary",
    ]
    status: Literal["PASS"] = "PASS"
    evidence_digest: str

    @field_validator("evidence_digest")
    @classmethod
    def require_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_DELIVERY_CHECK_DIGEST_INVALID")
        return value


_DELIVERY_CHECKS = (
    "execution_receipt_binding",
    "result_set_closure",
    "answer_contract_validation",
    "owner_acl_binding",
    "model_authority_boundary",
)


class AnswerDeliveryPreparationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-delivery-preparation-receipt/v1"] = (
        "boi-answer-delivery-preparation-receipt/v1"
    )
    run_id: str
    execution_id: str
    execution_classification: Literal["ATTESTED", "PROVISIONAL"]
    execution_receipt_digest: str
    execution_result_digest: str
    requirement_digest: str
    answer_envelope_digest: str
    acl_projection_digest: str
    authorization_policy_digest: str
    renderer_code_digest: str
    evaluator_code_digest: str
    frozen_result_digests: tuple[str, ...] = Field(min_length=1)
    checks: tuple[AnswerDeliveryCheck, ...]
    surface_parity_qualified: Literal[False] = False
    model_invocations: Literal[0] = 0
    raw_sql_model_input: Literal[0] = 0
    raw_row_model_input: Literal[0] = 0
    golden_model_input: Literal[0] = 0
    authorizes_release: Literal[False] = False
    authorizes_activation: Literal[False] = False
    receipt_digest: str

    @model_validator(mode="after")
    def validate_receipt(self) -> "AnswerDeliveryPreparationReceipt":
        digests = (
            self.execution_receipt_digest,
            self.execution_result_digest,
            self.requirement_digest,
            self.answer_envelope_digest,
            self.acl_projection_digest,
            self.authorization_policy_digest,
            self.renderer_code_digest,
            self.evaluator_code_digest,
            *self.frozen_result_digests,
            self.receipt_digest,
        )
        if not all(_is_digest(value) for value in digests):
            raise ValueError("ANSWER_DELIVERY_RECEIPT_DIGEST_INVALID")
        if tuple(item.check_id for item in self.checks) != _DELIVERY_CHECKS:
            raise ValueError("ANSWER_DELIVERY_CHECK_CLOSURE_INVALID")
        unsigned = self.model_dump(mode="json", exclude={"receipt_digest"})
        if self.receipt_digest != _digest(unsigned):
            raise ValueError("ANSWER_DELIVERY_RECEIPT_DIGEST_MISMATCH")
        return self


class GovernedAnswerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-governed-answer-record/v2"] = (
        "boi-governed-answer-record/v2"
    )
    answer_id: str
    owner_principal: str
    purpose_digest: str
    run_id: str
    execution_id: str
    execution_classification: Literal["ATTESTED", "PROVISIONAL"]
    answer_semantic_digest: str
    envelope: VerifiedAnswerEnvelope
    delivery_receipt: AnswerDeliveryPreparationReceipt
    frozen_result_refs: tuple[str, ...] = Field(min_length=1)
    view_display_names: dict[str, str]
    preferred_presentation: Literal[
        "list", "table", "nested_collection", "aggregate", "relation"
    ]
    source_snapshot: str
    ui_url: str
    safe_mcp_reproduction_ref: str
    record_digest: str

    @model_validator(mode="after")
    def validate_record(self) -> "GovernedAnswerRecord":
        if self.answer_semantic_digest != self.envelope.answer_semantic_digest:
            raise ValueError("ANSWER_SEMANTIC_DIGEST_MISMATCH")
        if self.delivery_receipt.answer_envelope_digest != self.answer_semantic_digest:
            raise ValueError("ANSWER_DELIVERY_RECEIPT_BINDING_MISMATCH")
        if self.execution_classification != self.envelope.execution_classification:
            raise ValueError("ANSWER_EXECUTION_CLASSIFICATION_MISMATCH")
        unsigned = self.model_dump(mode="json", exclude={"record_digest"})
        if self.record_digest != _digest(unsigned):
            raise ValueError("ANSWER_RECORD_DIGEST_MISMATCH")
        return self


class GovernedAnswerArtifactRecord(BaseModel):
    """Canonical API/MCP/CLI record; it has no product query-UI contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-governed-answer-artifact-record/v1"] = (
        "boi-governed-answer-artifact-record/v1"
    )
    answer_id: str
    owner_principal: str
    purpose_digest: str
    execution_id: str
    execution_classification: Literal["ATTESTED", "PROVISIONAL"]
    answer_semantic_digest: str
    artifact: GovernedAnswerArtifact
    api_url: str
    safe_mcp_reproduction_ref: str
    record_digest: str

    @model_validator(mode="after")
    def validate_record(self) -> "GovernedAnswerArtifactRecord":
        if self.answer_semantic_digest != self.artifact.artifact_semantic_digest:
            raise ValueError("ANSWER_ARTIFACT_SEMANTIC_DIGEST_MISMATCH")
        if self.execution_id != self.artifact.execution.execution_id:
            raise ValueError("ANSWER_ARTIFACT_EXECUTION_ID_MISMATCH")
        if self.execution_classification != self.artifact.execution.classification:
            raise ValueError("ANSWER_ARTIFACT_EXECUTION_CLASSIFICATION_MISMATCH")
        unsigned = self.model_dump(mode="json", exclude={"record_digest"})
        if self.record_digest != _digest(unsigned):
            raise ValueError("ANSWER_ARTIFACT_RECORD_DIGEST_MISMATCH")
        return self


class AnswerExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view_id: str
    purpose: str
    format: Literal["csv", "json"] = "csv"
    parent_identity: dict[str, Any] | None = None

    @field_validator("view_id", "purpose")
    @classmethod
    def require_export_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ANSWER_EXPORT_FIELD_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_parent_identity(self) -> "AnswerExportRequest":
        if self.parent_identity is not None:
            if not self.parent_identity or any(
                not str(key).strip() or isinstance(value, (dict, list, tuple, set))
                for key, value in self.parent_identity.items()
            ):
                raise ValueError("ANSWER_PARENT_IDENTITY_INVALID")
        return self


class _ExecutionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    run_id: str
    classification: Literal["ATTESTED", "PROVISIONAL"]
    result_digest: str
    receipt_digest: str
    receipt_ref: str
    attestation_ref: str | None
    source_snapshot: str
    authorization_policy_digest: str
    result_sets: tuple[Any, ...]
    full_result_artifact_ref: str | None


class GovernedAnswerDeliveryService:
    """The sole execution-to-answer composition and persistence boundary."""

    def __init__(
        self,
        store: AnswerDeliveryStore,
        *,
        cursor_secret: bytes | None = None,
        protected_result_loader: Callable[[str, str, str], dict[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
        access_ttl_seconds: int = 3600,
    ):
        self.store = store
        self.cursor_secret = cursor_secret or b"boi-answer-component-test-only"
        self.protected_result_loader = protected_result_loader
        self.clock = clock or time.time
        self.access_ttl_seconds = access_ttl_seconds

    @staticmethod
    def _execution_projection(
        execution: QueryExecution | MultiResultQueryExecution,
    ) -> _ExecutionProjection:
        if execution.status != "SUCCEEDED" or execution.result_status == "BLOCKED":
            raise AnswerDeliveryError("ANSWER_EXECUTION_NOT_SUCCESSFUL")
        if isinstance(execution, QueryExecution):
            if execution.result_status == "ATTESTED":
                if (
                    execution.lane != "attested"
                    or execution.attestation is None
                    or execution.attestation.status != "PASS"
                ):
                    raise AnswerDeliveryError("ANSWER_ATTESTATION_NOT_PASSING")
                classification: Literal["ATTESTED", "PROVISIONAL"] = "ATTESTED"
            elif execution.result_status == "PROVISIONAL":
                classification = "PROVISIONAL"
            else:
                raise AnswerDeliveryError("ANSWER_EXECUTION_NOT_SUCCESSFUL")
            receipt_payload = execution.receipt.model_dump(mode="json")
            return _ExecutionProjection(
                execution_id=execution.execution_id,
                run_id=execution.execution_id,
                classification=classification,
                result_digest=execution.result.result_digest,
                receipt_digest=_digest(receipt_payload),
                receipt_ref=f"query-execution-receipt:{execution.execution_id}",
                attestation_ref=(
                    f"query-attestation:{execution.execution_id}"
                    if classification == "ATTESTED"
                    else None
                ),
                source_snapshot=execution.receipt.source_snapshot,
                authorization_policy_digest=execution.receipt.authorization_policy_digest,
                result_sets=(execution.result,),
                full_result_artifact_ref=None,
            )
        receipt = execution.receipt
        return _ExecutionProjection(
            execution_id=execution.execution_id,
            run_id=execution.result.run_id,
            classification="PROVISIONAL",
            result_digest=execution.result.result_digest,
            receipt_digest=receipt.receipt_digest,
            receipt_ref=f"multi-result-execution-receipt:{execution.execution_id}",
            attestation_ref=None,
            source_snapshot=receipt.source_snapshot_digest,
            authorization_policy_digest=receipt.authorization_policy_digest,
            result_sets=execution.result.result_sets,
            full_result_artifact_ref=receipt.result_artifact_ref,
        )

    def _freeze_results(
        self,
        *,
        projection: _ExecutionProjection,
        requirement: AnswerRequirementContractV2,
        bindings: Sequence[AnswerResultBinding],
        answer_id: str,
        principal: str,
        purpose: str,
    ) -> tuple[tuple[FrozenAnswerResultSet, ...], tuple[FrozenAnswerResultSet, ...]]:
        if len(bindings) != len(projection.result_sets):
            raise AnswerDeliveryError("ANSWER_RESULT_SET_CLOSURE_MISMATCH")
        if len({item.result_set_id for item in bindings}) != len(bindings):
            raise AnswerDeliveryError("ANSWER_RESULT_BINDING_DUPLICATE")
        if requirement.result_view_requirements:
            view_requirements = {
                item.result_set_id: item for item in requirement.result_view_requirements
            }
        elif len(bindings) == 1:
            view_requirements = {}
        else:
            raise AnswerDeliveryError("ANSWER_VIEW_REQUIREMENT_REQUIRED")
        display_requirements = {
            item.field_ref: item for item in requirement.required_display_fields
        }
        multi_sources = {
            item.result_set_id: item
            for item in projection.result_sets
            if isinstance(item, MultiResultSetResult)
        }
        protected_sets: dict[str, dict[str, Any]] = {}
        if any(
            isinstance(item, MultiResultSetResult) and item.truncated
            for item in projection.result_sets
        ):
            if (
                projection.full_result_artifact_ref is None
                or self.protected_result_loader is None
            ):
                raise AnswerDeliveryError("ANSWER_FULL_RESULT_LOADER_REQUIRED")
            artifact = self.protected_result_loader(
                projection.full_result_artifact_ref, principal, purpose
            )
            if artifact.get("result_digest") != projection.result_digest:
                raise AnswerDeliveryError("ANSWER_FULL_RESULT_DIGEST_MISMATCH")
            protected_sets = {
                str(item.get("result_set_id") or ""): item
                for item in artifact.get("result_sets") or []
            }
        frozen: list[FrozenAnswerResultSet] = []
        full_frozen: list[FrozenAnswerResultSet] = []
        for index, binding in enumerate(bindings):
            source = (
                multi_sources.get(binding.result_set_id)
                if multi_sources
                else projection.result_sets[index]
            )
            if source is None:
                raise AnswerDeliveryError("ANSWER_RESULT_SET_CLOSURE_MISMATCH")
            view = view_requirements.get(binding.result_set_id)
            expected_shape = view.shape if view else binding.shape
            expected_grain = view.exact_grain if view else requirement.exact_grain
            expected_ordering = view.ordering if view else requirement.ordering
            if binding.shape != expected_shape:
                raise AnswerDeliveryError("ANSWER_RESULT_SHAPE_BINDING_MISMATCH")
            by_ref = {item.field_ref: item for item in binding.fields}
            try:
                identity_sources = tuple(by_ref[item].source_field for item in expected_grain)
                ordering_sources = tuple(by_ref[item].source_field for item in expected_ordering)
                latest_sources = tuple(
                    f"{by_ref[item.rsplit(' ', 1)[0]].source_field} "
                    f"{item.rsplit(' ', 1)[1]}"
                    for item in requirement.latest_ordering
                )
            except KeyError as exc:
                raise AnswerDeliveryError("ANSWER_FIELD_BINDING_INCOMPLETE") from exc
            if identity_sources != binding.row_identity_fields:
                raise AnswerDeliveryError("ANSWER_ROW_IDENTITY_BINDING_MISMATCH")
            if ordering_sources != binding.source_ordering:
                raise AnswerDeliveryError("ANSWER_ORDERING_BINDING_MISMATCH")
            if latest_sources != binding.source_latest_ordering:
                raise AnswerDeliveryError("ANSWER_LATEST_ORDERING_BINDING_MISMATCH")
            displayed = tuple(
                FrozenDisplayField(
                    field_ref=item.field_ref,
                    source_field=item.source_field,
                    label=display_requirements[item.field_ref].label,
                    unit=display_requirements[item.field_ref].unit,
                    mapping_ref=item.mapping_ref,
                )
                for item in binding.fields
                if item.field_ref in display_requirements
            )
            if not displayed:
                raise AnswerDeliveryError("ANSWER_DISPLAY_BINDING_REQUIRED")
            if isinstance(source, QueryResult):
                rows = source.rows
                row_count = source.row_count
                result_digest = source.result_digest
                parent_result_set_id = None
            else:
                protected = protected_sets.get(source.result_set_id)
                if source.truncated:
                    if (
                        protected is None
                        or protected.get("result_digest") != source.result_digest
                        or int(protected.get("row_count") or -1) != source.row_count
                    ):
                        raise AnswerDeliveryError("ANSWER_FULL_RESULT_SET_MISMATCH")
                    rows = tuple(dict(item) for item in protected.get("rows") or [])
                    if len(rows) != source.row_count:
                        raise AnswerDeliveryError("ANSWER_FULL_RESULT_COUNT_MISMATCH")
                else:
                    rows = source.rows
                row_count = source.row_count
                result_digest = source.result_digest
                parent_result_set_id = (
                    source.parent_link.parent_result_set_id if source.parent_link else None
                )
            expected_parent = view.parent_result_set_id if view else None
            if parent_result_set_id != expected_parent:
                raise AnswerDeliveryError("ANSWER_PARENT_BINDING_MISMATCH")
            if isinstance(source, MultiResultSetResult) and source.parent_link:
                if binding.parent_key_fields and (
                    tuple(source.parent_link.parent_key_outputs)
                    != binding.parent_key_fields
                    or tuple(source.parent_link.child_key_outputs)
                    != binding.child_key_fields
                ):
                    raise AnswerDeliveryError("ANSWER_PARENT_KEY_BINDING_MISMATCH")
            elif binding.parent_key_fields or binding.child_key_fields:
                raise AnswerDeliveryError("ANSWER_PARENT_KEY_BINDING_FORBIDDEN")
            full_result = FrozenAnswerResultSet(
                    result_set_id=binding.result_set_id,
                    parent_result_set_id=parent_result_set_id,
                    shape=binding.shape,
                    exact_grain=expected_grain,
                    row_identity_fields=binding.row_identity_fields,
                    parent_key_fields=binding.parent_key_fields,
                    child_key_fields=binding.child_key_fields,
                    ordered_by=expected_ordering,
                    latest_ordering=requirement.latest_ordering,
                    display_fields=displayed,
                    rows=rows,
                    total_row_count=row_count,
                    truncated=False,
                    full_result_artifact_ref=None,
                    result_digest=result_digest,
                )
            full_frozen.append(full_result)
            preview_size = (
                requirement.pagination_policy.page_size
                if requirement.pagination_policy.full_access_required
                else None
            )
            preview_rows = rows[:preview_size] if preview_size is not None else rows
            presentation_truncated = len(preview_rows) < row_count
            if (
                isinstance(source, MultiResultSetResult)
                and source.truncated
                and not requirement.pagination_policy.full_access_required
            ):
                raise AnswerDeliveryError("ANSWER_PAGINATION_POLICY_REQUIRED")
            safe_rows_url = None
            if presentation_truncated:
                safe_rows_url = (
                    f"/api/v2/answers/{answer_id}/views/"
                    f"{quote('view:' + binding.result_set_id, safe='')}/rows"
                    f"?purpose={quote(purpose, safe='')}&page_size={preview_size}"
                )
            frozen.append(
                full_result.model_copy(
                    update={
                        "rows": preview_rows,
                        "truncated": presentation_truncated,
                        "full_result_artifact_ref": safe_rows_url,
                    }
                )
            )
        if view_requirements and set(view_requirements) != {
            item.result_set_id for item in frozen
        }:
            raise AnswerDeliveryError("ANSWER_RESULT_SET_CLOSURE_MISMATCH")
        if not set(display_requirements) <= {
            field.field_ref for item in frozen for field in item.display_fields
        }:
            raise AnswerDeliveryError("ANSWER_DISPLAY_BINDING_INCOMPLETE")
        return tuple(frozen), tuple(full_frozen)

    @staticmethod
    def _answer_id(
        principal: str, execution_id: str, requirement_digest: str
    ) -> str:
        return "answer_" + _digest(
            {
                "principal": principal,
                "execution_id": execution_id,
                "requirement_digest": requirement_digest,
            }
        )[7:39]

    def publish_from_execution(
        self,
        *,
        principal: str,
        purpose: str,
        idempotency_key: str,
        channel: Literal["ui", "mcp", "rest", "agent"],
        requirement: AnswerRequirementContractV2,
        execution: QueryExecution | MultiResultQueryExecution,
        result_bindings: Sequence[AnswerResultBinding],
        quality_measurements: Mapping[str, int],
        quality_evidence_digests: Mapping[str, str],
        renderer_code_digest: str,
        evaluator_code_digest: str,
        request_digest: str = "",
    ) -> GovernedAnswerRecord:
        if not principal.strip() or not purpose.strip() or not idempotency_key.strip():
            raise AnswerDeliveryError("ANSWER_DELIVERY_IDENTITY_REQUIRED")
        if not _is_digest(renderer_code_digest) or not _is_digest(evaluator_code_digest):
            raise AnswerDeliveryError("ANSWER_DELIVERY_CODE_DIGEST_INVALID")
        projection = self._execution_projection(execution)
        required_quality = set(requirement.required_quality_disclosures)
        if not required_quality <= set(quality_measurements) or not required_quality <= set(
            quality_evidence_digests
        ):
            raise AnswerDeliveryError("ANSWER_QUALITY_CLOSURE_INCOMPLETE")
        if any(
            not _is_digest(quality_evidence_digests[item]) for item in required_quality
        ):
            raise AnswerDeliveryError("ANSWER_QUALITY_EVIDENCE_INVALID")
        answer_id = self._answer_id(
            principal, projection.execution_id, requirement.contract_digest
        )
        frozen, full_frozen = self._freeze_results(
            projection=projection,
            requirement=requirement,
            bindings=result_bindings,
            answer_id=answer_id,
            principal=principal,
            purpose=purpose,
        )
        envelope = DeterministicAnswerComposer.compose(
            requirement=requirement,
            result_sets=frozen,
            execution_classification=projection.classification,
            execution_receipt_ref=projection.receipt_ref,
            snapshot_notice=projection.source_snapshot,
            quality_measurements=quality_measurements,
            quality_evidence_digests=quality_evidence_digests,
            ui_url=f"/ontology/answers/{answer_id}",
            safe_mcp_reproduction_ref=f"boi_get:{answer_id}",
            attestation_ref=projection.attestation_ref,
            summary_result_sets=full_frozen,
        )
        # Reconstruct the exact view-model inputs used by the composer so the
        # existing deterministic presentation validator remains authoritative.
        view_model = AnswerViewModel(
            direct_answer=envelope.direct_answer,
            result_views=envelope.result_views,
            quality_notices=envelope.quality_notices,
            snapshot_notice=projection.source_snapshot,
            evidence_refs=tuple(
                dict.fromkeys(
                    quality_evidence_digests[item]
                    for item in quality_measurements
                )
            ),
            execution_receipt_ref=projection.receipt_ref,
            attestation_ref=projection.attestation_ref,
            model_invocations=0,
        )
        validate_answer_contract(
            requirement=requirement, view_model=view_model, envelope=envelope
        )
        evidence_basis = {
            "execution_receipt_digest": projection.receipt_digest,
            "execution_result_digest": projection.result_digest,
            "requirement_digest": requirement.contract_digest,
            "answer_envelope_digest": envelope.answer_semantic_digest,
            "frozen_result_digests": [item.result_digest for item in frozen],
            "acl_projection_digest": requirement.acl_policy_digest,
            "authorization_policy_digest": projection.authorization_policy_digest,
        }
        checks = tuple(
            AnswerDeliveryCheck(
                check_id=check_id,
                evidence_digest=_digest({**evidence_basis, "check_id": check_id}),
            )
            for check_id in _DELIVERY_CHECKS
        )
        receipt_base = {
            "schema_name": "boi-answer-delivery-preparation-receipt/v1",
            "run_id": projection.run_id,
            "execution_id": projection.execution_id,
            "execution_classification": projection.classification,
            "execution_receipt_digest": projection.receipt_digest,
            "execution_result_digest": projection.result_digest,
            "requirement_digest": requirement.contract_digest,
            "answer_envelope_digest": envelope.answer_semantic_digest,
            "acl_projection_digest": requirement.acl_policy_digest,
            "authorization_policy_digest": projection.authorization_policy_digest,
            "renderer_code_digest": renderer_code_digest,
            "evaluator_code_digest": evaluator_code_digest,
            "frozen_result_digests": [item.result_digest for item in frozen],
            "checks": [item.model_dump(mode="json") for item in checks],
            "surface_parity_qualified": False,
            "model_invocations": 0,
            "raw_sql_model_input": 0,
            "raw_row_model_input": 0,
            "golden_model_input": 0,
            "authorizes_release": False,
            "authorizes_activation": False,
        }
        delivery_receipt = AnswerDeliveryPreparationReceipt.model_validate(
            {**receipt_base, "receipt_digest": _digest(receipt_base)}
        )
        purpose_digest = _digest(purpose)
        frozen_refs = tuple(
            f"answer-result:{answer_id}:{item.result_set_id}" for item in full_frozen
        )
        view_display_names = {
            "view:" + item.result_set_id: item.display_name
            for item in requirement.result_view_requirements
        }
        if not view_display_names and len(frozen) == 1:
            view_display_names["view:" + frozen[0].result_set_id] = "결과"
        record_base = {
            "schema_name": "boi-governed-answer-record/v2",
            "answer_id": answer_id,
            "owner_principal": principal,
            "purpose_digest": purpose_digest,
            "run_id": projection.run_id,
            "execution_id": projection.execution_id,
            "execution_classification": projection.classification,
            "answer_semantic_digest": envelope.answer_semantic_digest,
            "envelope": envelope.model_dump(mode="json"),
            "delivery_receipt": delivery_receipt.model_dump(mode="json"),
            "frozen_result_refs": frozen_refs,
            "view_display_names": view_display_names,
            "preferred_presentation": requirement.preferred_presentation,
            "source_snapshot": projection.source_snapshot,
            "ui_url": envelope.ui_url,
            "safe_mcp_reproduction_ref": envelope.safe_mcp_reproduction_ref,
        }
        record = GovernedAnswerRecord.model_validate(
            {**record_base, "record_digest": _digest(record_base)}
        )
        semantic_key = _digest(
            {
                "principal": principal,
                "execution_id": projection.execution_id,
                "requirement_digest": requirement.contract_digest,
            }
        )
        existing_semantic = self.store.get("governed_answer_semantic_v2", semantic_key)
        if existing_semantic:
            existing = self.get(
                principal=principal, answer_id=str(existing_semantic["answer_id"])
            )
            if existing.record_digest != record.record_digest:
                raise AnswerDeliveryError("ANSWER_SEMANTIC_CACHE_CONFLICT")
            record = existing
        else:
            for ref, result_set in zip(frozen_refs, full_frozen):
                self.store.put(
                    "governed_answer_frozen_results_v2",
                    ref,
                    {
                        "owner_principal": principal,
                        "purpose_digest": purpose_digest,
                        "answer_id": answer_id,
                        "result": result_set.model_dump(mode="json"),
                    },
                )
            self.store.put(
                "governed_answer_records_v2", answer_id, record.model_dump(mode="json")
            )
            self.store.put(
                "governed_answer_semantic_v2",
                semantic_key,
                {"answer_id": answer_id, "record_digest": record.record_digest},
            )
            access_base = {
                "answer_id": answer_id,
                "owner_principal": principal,
                "purpose": purpose,
                "purpose_digest": purpose_digest,
                "answer_semantic_digest": record.answer_semantic_digest,
                "acl_policy_digest": requirement.acl_policy_digest,
                "authorization_policy_digest": projection.authorization_policy_digest,
                "source_snapshot": projection.source_snapshot,
                "expires_at": int(self.clock()) + self.access_ttl_seconds,
                "revoked": False,
            }
            self.store.put(
                "governed_answer_access_v2",
                answer_id,
                {**access_base, "access_digest": _digest(access_base)},
            )
        idempotency_id = _digest(
            {"principal": principal, "idempotency_key": idempotency_key}
        )
        existing_idempotency = self.store.get(
            "governed_answer_idempotency_v2", idempotency_id
        )
        if existing_idempotency and existing_idempotency.get("record_digest") != record.record_digest:
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_CONFLICT")
        if (
            existing_idempotency
            and request_digest
            and str(existing_idempotency.get("request_digest") or "")
            != request_digest
        ):
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_REQUEST_CONFLICT")
        if not existing_idempotency:
            self.store.put(
                "governed_answer_idempotency_v2",
                idempotency_id,
                {
                    "answer_id": answer_id,
                    "record_digest": record.record_digest,
                    "request_digest": request_digest,
                },
            )
        self._record_invocation(record=record, channel=channel)
        return record

    def publish_artifact(
        self,
        *,
        principal: str,
        purpose: str,
        idempotency_key: str,
        channel: Literal["mcp", "rest", "cli", "agent"],
        artifact: GovernedAnswerArtifact,
        request_digest: str,
    ) -> GovernedAnswerArtifactRecord:
        """Persist one semantic artifact independent of invocation channel."""

        if (artifact.schema_name not in {'boi-governed-answer-artifact/v1',
                'boi-governed-answer-artifact/v2','boi-governed-answer-artifact/v3'}
                or not isinstance(artifact.active_release_digest,str)
                or not _is_digest(artifact.active_release_digest)):
            raise AnswerDeliveryError('ANSWER_ARTIFACT_ACTIVE_RELEASE_REQUIRED')
        if channel not in {"mcp", "rest", "cli", "agent"}:
            raise AnswerDeliveryError("ANSWER_INVOCATION_CHANNEL_INVALID")
        if not principal.strip() or not purpose.strip() or not idempotency_key.strip():
            raise AnswerDeliveryError("ANSWER_DELIVERY_IDENTITY_REQUIRED")
        runtime_principal = (
            principal if principal.startswith("employee:") else f"employee:{principal}"
        )
        if artifact.principal_digest != _digest(runtime_principal):
            raise AnswerDeliveryError("ANSWER_ARTIFACT_PRINCIPAL_MISMATCH")
        if artifact.purpose_digest != _digest(purpose):
            raise AnswerDeliveryError("ANSWER_ARTIFACT_PURPOSE_MISMATCH")
        if not _is_digest(request_digest):
            raise AnswerDeliveryError("ANSWER_REQUEST_DIGEST_INVALID")
        answer_id = "answer_" + _digest(
            {
                "principal": principal,
                "purpose_digest": artifact.purpose_digest,
                "answer_semantic_digest": artifact.artifact_semantic_digest,
                "execution_id": artifact.execution.execution_id,
            }
        )[7:39]
        base = {
            "schema_name": "boi-governed-answer-artifact-record/v1",
            "answer_id": answer_id,
            "owner_principal": principal,
            "purpose_digest": artifact.purpose_digest,
            "execution_id": artifact.execution.execution_id,
            "execution_classification": artifact.execution.classification,
            "answer_semantic_digest": artifact.artifact_semantic_digest,
            "artifact": artifact.model_dump(mode="json"),
            "api_url": f"/api/v2/answers/{answer_id}",
            "safe_mcp_reproduction_ref": f"boi_get:{answer_id}",
        }
        record = GovernedAnswerArtifactRecord.model_validate(
            {**base, "record_digest": _digest(base)}
        )
        existing = self.store.get("governed_answer_artifacts_v3", answer_id)
        if existing:
            stored = GovernedAnswerArtifactRecord.model_validate(existing)
            if stored.record_digest != record.record_digest:
                raise AnswerDeliveryError("ANSWER_ARTIFACT_RECORD_CONFLICT")
            record = stored
        else:
            self.store.put(
                "governed_answer_artifacts_v3",
                answer_id,
                record.model_dump(mode="json"),
            )
        idempotency_id = _digest(
            {"principal": principal, "idempotency_key": idempotency_key}
        )
        binding = {
            "answer_id": answer_id,
            "record_digest": record.record_digest,
            "request_digest": request_digest,
            "purpose_digest": record.purpose_digest,
        }
        existing_binding = self.store.get(
            "governed_answer_artifact_idempotency_v3", idempotency_id
        )
        if existing_binding:
            existing_binding = dict(existing_binding)
            existing_binding.pop("updated_at", None)
        if existing_binding and existing_binding != binding:
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_CONFLICT")
        if not existing_binding:
            self.store.put(
                "governed_answer_artifact_idempotency_v3",
                idempotency_id,
                binding,
            )
        self._record_artifact_invocation(record=record, channel=channel)
        return record

    def replay_artifact_idempotent(
        self,
        *,
        principal: str,
        purpose: str,
        idempotency_key: str,
        request_digest: str,
        channel: Literal["mcp", "rest", "cli", "agent"],
    ) -> GovernedAnswerArtifactRecord | None:
        if channel not in {"mcp", "rest", "cli", "agent"}:
            raise AnswerDeliveryError("ANSWER_INVOCATION_CHANNEL_INVALID")
        idempotency_id = _digest(
            {"principal": principal, "idempotency_key": idempotency_key}
        )
        binding = self.store.get(
            "governed_answer_artifact_idempotency_v3", idempotency_id
        )
        if not binding:
            return None
        if str(binding.get("request_digest") or "") != request_digest:
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_REQUEST_CONFLICT")
        record = self.get_artifact(
            principal=principal, answer_id=str(binding.get("answer_id") or "")
        )
        if record.record_digest != str(binding.get("record_digest") or ""):
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_RECORD_MISMATCH")
        if record.purpose_digest != _digest(purpose):
            raise AnswerDeliveryError("ANSWER_PURPOSE_MISMATCH")
        self._record_artifact_invocation(record=record, channel=channel)
        return record

    def get_artifact(
        self, *, principal: str, answer_id: str
    ) -> GovernedAnswerArtifactRecord:
        raw = self.store.get("governed_answer_artifacts_v3", answer_id)
        if not raw:
            raise AnswerDeliveryError("ANSWER_NOT_FOUND")
        payload = dict(raw)
        payload.pop("updated_at", None)
        record = GovernedAnswerArtifactRecord.model_validate(payload)
        if record.owner_principal != principal:
            raise AnswerDeliveryError("ANSWER_OWNER_FORBIDDEN")
        return record

    def _record_artifact_invocation(
        self,
        *,
        record: GovernedAnswerArtifactRecord,
        channel: Literal["mcp", "rest", "cli", "agent"],
    ) -> None:
        invocation = {
            "answer_id": record.answer_id,
            "owner_principal": record.owner_principal,
            "channel": channel,
            "answer_semantic_digest": record.answer_semantic_digest,
            "record_digest": record.record_digest,
        }
        sequence = len(
            [
                item
                for item in self.store.list(
                    "governed_answer_artifact_invocations_v3", limit=1_000_000
                )
                if item.get("answer_id") == record.answer_id
            ]
        )
        self.store.put(
            "governed_answer_artifact_invocations_v3",
            _digest({**invocation, "sequence": sequence}),
            invocation,
        )

    def replay_idempotent(
        self,
        *,
        principal: str,
        purpose: str,
        idempotency_key: str,
        request_digest: str,
        channel: Literal["ui", "mcp", "rest", "agent"],
    ) -> GovernedAnswerRecord | None:
        """Return an exact prior answer before re-executing its query.

        The request binding is deliberately stored beside the idempotency key,
        not inferred from a later execution receipt.  This makes a real
        UI/REST/MCP replay channel-neutral across process restarts while a key
        reused for different question/parameters/purpose fails closed.
        """

        idempotency_id = _digest(
            {"principal": principal, "idempotency_key": idempotency_key}
        )
        binding = self.store.get(
            "governed_answer_idempotency_v2", idempotency_id
        )
        if not binding:
            return None
        bound_request = str(binding.get("request_digest") or "")
        if not bound_request:
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_REQUEST_UNBOUND")
        if bound_request != request_digest:
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_REQUEST_CONFLICT")
        record = self.get(
            principal=principal, answer_id=str(binding.get("answer_id") or "")
        )
        if record.record_digest != str(binding.get("record_digest") or ""):
            raise AnswerDeliveryError("ANSWER_IDEMPOTENCY_RECORD_MISMATCH")
        if record.purpose_digest != _digest(purpose):
            raise AnswerDeliveryError("ANSWER_PURPOSE_MISMATCH")
        self._record_invocation(record=record, channel=channel)
        return record

    def _record_invocation(
        self,
        *,
        record: GovernedAnswerRecord,
        channel: Literal["ui", "mcp", "rest", "agent"],
    ) -> None:
        invocation = {
            "answer_id": record.answer_id,
            "owner_principal": record.owner_principal,
            "channel": channel,
            "answer_semantic_digest": record.answer_semantic_digest,
            "record_digest": record.record_digest,
        }
        sequence = len(
            [
                item
                for item in self.store.list(
                    "governed_answer_invocations_v2", limit=1_000_000
                )
                if item.get("answer_id") == record.answer_id
            ]
        )
        self.store.put(
            "governed_answer_invocations_v2",
            _digest({**invocation, "sequence": sequence}),
            invocation,
        )

    def get(self, *, principal: str, answer_id: str) -> GovernedAnswerRecord:
        raw = self.store.get("governed_answer_records_v2", answer_id)
        if not raw:
            raise AnswerDeliveryError("ANSWER_NOT_FOUND")
        payload = dict(raw)
        payload.pop("updated_at", None)
        record = GovernedAnswerRecord.model_validate(payload)
        if record.owner_principal != principal:
            raise AnswerDeliveryError("ANSWER_OWNER_FORBIDDEN")
        return record

    def _access_record(
        self, *, principal: str, purpose: str, answer_id: str
    ) -> dict[str, Any]:
        record = self.get(principal=principal, answer_id=answer_id)
        raw = self.store.get("governed_answer_access_v2", answer_id)
        if not raw:
            raise AnswerDeliveryError("ANSWER_ACCESS_RECORD_MISSING")
        access = dict(raw)
        access.pop("updated_at", None)
        embedded = str(access.pop("access_digest", ""))
        if embedded != _digest(access):
            raise AnswerDeliveryError("ANSWER_ACCESS_RECORD_TAMPERED")
        if (
            access.get("owner_principal") != principal
            or access.get("purpose") != purpose
            or access.get("purpose_digest") != _digest(purpose)
            or access.get("answer_semantic_digest") != record.answer_semantic_digest
            or access.get("acl_policy_digest")
            != record.delivery_receipt.acl_projection_digest
            or access.get("authorization_policy_digest")
            != record.delivery_receipt.authorization_policy_digest
            or access.get("source_snapshot") != record.source_snapshot
        ):
            raise AnswerDeliveryError("ANSWER_ACCESS_DENIED")
        if bool(access.get("revoked")):
            raise AnswerDeliveryError("ANSWER_ACCESS_REVOKED")
        if int(access.get("expires_at") or 0) <= int(self.clock()):
            raise AnswerDeliveryError("ANSWER_ACCESS_EXPIRED")
        return access

    def _cursor(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        signature = hmac.new(self.cursor_secret, raw, hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + signature

    def _decode_cursor(self, cursor: str) -> dict[str, Any]:
        try:
            encoded, signature = cursor.split(".", 1)
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            expected = hmac.new(self.cursor_secret, raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            payload = json.loads(raw)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AnswerDeliveryError("ANSWER_CURSOR_TAMPERED") from error
        if not isinstance(payload, dict):
            raise AnswerDeliveryError("ANSWER_CURSOR_TAMPERED")
        return payload

    def _full_result(
        self, *, principal: str, answer_id: str, view_id: str
    ) -> tuple[GovernedAnswerRecord, FrozenAnswerResultSet]:
        record = self.get(principal=principal, answer_id=answer_id)
        result_set_id = view_id.removeprefix("view:")
        ref = f"answer-result:{answer_id}:{result_set_id}"
        if ref not in record.frozen_result_refs:
            raise AnswerDeliveryError("ANSWER_VIEW_NOT_FOUND")
        raw = self.store.get("governed_answer_frozen_results_v2", ref)
        if not raw or raw.get("owner_principal") != principal:
            raise AnswerDeliveryError("ANSWER_VIEW_NOT_FOUND")
        payload = dict(raw.get("result") or {})
        return record, FrozenAnswerResultSet.model_validate(payload)

    @staticmethod
    def _rows_for_parent(
        result: FrozenAnswerResultSet,
        parent_identity: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], ...]:
        if parent_identity is None:
            return result.rows
        if not parent_identity or not set(parent_identity) <= set(
            result.row_identity_fields
        ):
            raise AnswerDeliveryError("ANSWER_PARENT_IDENTITY_INVALID")
        return tuple(
            row
            for row in result.rows
            if all(str(row.get(key)) == str(value) for key, value in parent_identity.items())
        )

    def rows_page(
        self,
        *,
        principal: str,
        purpose: str,
        answer_id: str,
        view_id: str,
        page_size: int,
        cursor: str | None = None,
        parent_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if page_size < 1 or page_size > 1000:
            raise AnswerDeliveryError("ANSWER_PAGE_SIZE_INVALID")
        access = self._access_record(
            principal=principal, purpose=purpose, answer_id=answer_id
        )
        record, result = self._full_result(
            principal=principal, answer_id=answer_id, view_id=view_id
        )
        selected_rows = self._rows_for_parent(result, parent_identity)
        parent_identity_digest = _digest(dict(parent_identity or {}))
        offset = 0
        if cursor:
            payload = self._decode_cursor(cursor)
            expected = {
                "answer_id": answer_id,
                "answer_semantic_digest": record.answer_semantic_digest,
                "result_digest": result.result_digest,
                "principal": principal,
                "purpose_digest": _digest(purpose),
                "acl_policy_digest": record.delivery_receipt.acl_projection_digest,
                "authorization_policy_digest": record.delivery_receipt.authorization_policy_digest,
                "source_snapshot": record.source_snapshot,
                "view_id": view_id,
                "parent_identity_digest": parent_identity_digest,
                "page_size": page_size,
                "expires_at": int(access["expires_at"]),
            }
            if any(payload.get(key) != value for key, value in expected.items()):
                raise AnswerDeliveryError("ANSWER_CURSOR_BINDING_MISMATCH")
            offset = int(payload.get("offset") or 0)
            if offset < 0:
                raise AnswerDeliveryError("ANSWER_CURSOR_OFFSET_INVALID")
        rows = selected_rows[offset : offset + page_size]
        columns = tuple(
            {"field_ref": item.field_ref, "label": item.label, "unit": item.unit}
            for item in result.display_fields
        )
        projected_rows = tuple(
            tuple(row[item.source_field] for item in result.display_fields)
            for row in rows
        )
        next_offset = offset + len(rows)
        next_cursor = None
        if next_offset < len(selected_rows):
            next_cursor = self._cursor(
                {
                    "answer_id": answer_id,
                    "answer_semantic_digest": record.answer_semantic_digest,
                    "result_digest": result.result_digest,
                    "principal": principal,
                    "purpose_digest": _digest(purpose),
                    "acl_policy_digest": record.delivery_receipt.acl_projection_digest,
                    "authorization_policy_digest": record.delivery_receipt.authorization_policy_digest,
                    "source_snapshot": record.source_snapshot,
                    "view_id": view_id,
                    "parent_identity_digest": parent_identity_digest,
                    "page_size": page_size,
                    "offset": next_offset,
                    "expires_at": int(access["expires_at"]),
                }
            )
        response = {
            "answer_id": answer_id,
            "view_id": view_id,
            "answer_semantic_digest": record.answer_semantic_digest,
            "result_digest": result.result_digest,
            "source_snapshot": record.source_snapshot,
            "parent_identity": dict(parent_identity or {}),
            "offset": offset,
            "page_size": page_size,
            "range_start": offset + 1 if projected_rows else 0,
            "range_end": offset + len(projected_rows),
            "returned_row_count": len(projected_rows),
            "total_row_count": len(selected_rows),
            "columns": columns,
            "rows": projected_rows,
            "next_cursor": next_cursor,
            "reran_database": False,
            "model_invocations": 0,
        }
        return {**response, "page_digest": _digest(response)}

    def create_export(
        self,
        *,
        principal: str,
        answer_id: str,
        request: AnswerExportRequest,
    ) -> dict[str, Any]:
        access = self._access_record(
            principal=principal, purpose=request.purpose, answer_id=answer_id
        )
        record, result = self._full_result(
            principal=principal, answer_id=answer_id, view_id=request.view_id
        )
        selected_rows = self._rows_for_parent(result, request.parent_identity)
        columns = [item.label for item in result.display_fields]
        rows = [
            [row[item.source_field] for item in result.display_fields]
            for row in selected_rows
        ]
        if request.format == "csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows)
            content = output.getvalue().encode("utf-8-sig")
            media_type = "text/csv; charset=utf-8"
        else:
            content = json.dumps(
                {"columns": columns, "rows": rows},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            media_type = "application/json"
        content_digest = "sha256:" + hashlib.sha256(content).hexdigest()
        export_identity = {
            "answer_id": answer_id,
            "answer_semantic_digest": record.answer_semantic_digest,
            "result_digest": result.result_digest,
            "principal": principal,
            "purpose_digest": _digest(request.purpose),
            "acl_policy_digest": record.delivery_receipt.acl_projection_digest,
            "authorization_policy_digest": record.delivery_receipt.authorization_policy_digest,
            "source_snapshot": record.source_snapshot,
            "view_id": request.view_id,
            "parent_identity_digest": _digest(dict(request.parent_identity or {})),
            "format": request.format,
            "content_digest": content_digest,
            "expires_at": int(access["expires_at"]),
        }
        export_id = "export_" + _digest(export_identity)[7:39]
        export = {
            **export_identity,
            "export_id": export_id,
            "owner_principal": principal,
            "purpose": request.purpose,
            "parent_identity": dict(request.parent_identity or {}),
            "row_count": len(rows),
            "media_type": media_type,
            "content_b64": base64.b64encode(content).decode("ascii"),
            "revoked": False,
        }
        export_digest = _digest(export)
        existing = self.store.get("governed_answer_exports_v2", export_id)
        if existing and existing.get("export_digest") != export_digest:
            raise AnswerDeliveryError("ANSWER_EXPORT_CONFLICT")
        if not existing:
            self.store.put(
                "governed_answer_exports_v2",
                export_id,
                {**export, "export_digest": export_digest},
            )
        return {
            "export_id": export_id,
            "answer_id": answer_id,
            "view_id": request.view_id,
            "format": request.format,
            "row_count": len(rows),
            "content_digest": content_digest,
            "export_digest": export_digest,
            "download_url": f"/api/v2/answers/{answer_id}/exports/{export_id}",
            "expires_at": int(access["expires_at"]),
        }

    def get_export(
        self,
        *,
        principal: str,
        purpose: str,
        answer_id: str,
        export_id: str,
    ) -> tuple[bytes, str, str]:
        self._access_record(
            principal=principal, purpose=purpose, answer_id=answer_id
        )
        raw = self.store.get("governed_answer_exports_v2", export_id)
        if not raw:
            raise AnswerDeliveryError("ANSWER_EXPORT_NOT_FOUND")
        export = dict(raw)
        export.pop("updated_at", None)
        embedded = str(export.pop("export_digest", ""))
        if embedded != _digest(export):
            raise AnswerDeliveryError("ANSWER_EXPORT_TAMPERED")
        if (
            export.get("answer_id") != answer_id
            or export.get("owner_principal") != principal
            or export.get("purpose") != purpose
            or bool(export.get("revoked"))
        ):
            raise AnswerDeliveryError("ANSWER_EXPORT_ACCESS_DENIED")
        content = base64.b64decode(str(export["content_b64"]), validate=True)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if digest != export.get("content_digest"):
            raise AnswerDeliveryError("ANSWER_EXPORT_CONTENT_TAMPERED")
        return content, str(export["media_type"]), digest

    def revoke_access(self, *, principal: str, answer_id: str) -> None:
        record = self.get(principal=principal, answer_id=answer_id)
        raw = self.store.get("governed_answer_access_v2", answer_id)
        if not raw:
            raise AnswerDeliveryError("ANSWER_ACCESS_RECORD_MISSING")
        access = dict(raw)
        access.pop("updated_at", None)
        access.pop("access_digest", None)
        if access.get("owner_principal") != record.owner_principal:
            raise AnswerDeliveryError("ANSWER_ACCESS_DENIED")
        access["revoked"] = True
        self.store.put(
            "governed_answer_access_v2",
            answer_id,
            {**access, "access_digest": _digest(access)},
        )

    def presentation(self, record: GovernedAnswerRecord) -> dict[str, Any]:
        views: dict[str, dict[str, Any]] = {}
        source_views = {item.view_id: item for item in record.envelope.result_views}
        full_results: dict[str, FrozenAnswerResultSet] = {}
        for view in record.envelope.result_views:
            _record, result = self._full_result(
                principal=record.owner_principal,
                answer_id=record.answer_id,
                view_id=view.view_id,
            )
            full_results[view.view_id] = result
        for view in record.envelope.result_views:
            width = len(view.displayed_fields)
            rows: list[dict[str, Any]] = []
            for start in range(0, len(view.values), width):
                values = view.values[start : start + width]
                identity = dict(values[0].provenance.row_identity) if values else {}
                rows.append(
                    {
                        "identity": identity,
                        "cells": [item.value for item in values],
                        "collections": {},
                    }
                )
            views[view.view_id] = {
                "view_id": view.view_id,
                "display_name": record.view_display_names.get(view.view_id, "결과"),
                "shape": view.shape,
                "parent_result_set_id": view.parent_result_set_id,
                "exact_grain": list(view.exact_grain),
                "row_identity_fields": list(view.row_identity_fields),
                "columns": [
                    {"label": item.label, "unit": item.unit}
                    for item in view.displayed_fields
                ],
                "rows": rows,
                "preview_row_count": view.preview_row_count,
                "total_row_count": view.total_row_count,
                "truncated": view.truncated,
                "rows_url": view.full_result_artifact_ref,
                "render_mode": (
                    "aggregate"
                    if view.shape == "Aggregate"
                    else "ordered_list"
                    if record.preferred_presentation == "list"
                    else "table"
                ),
            }
        roots: list[dict[str, Any]] = []
        for view_id, rendered in views.items():
            parent_result_id = rendered["parent_result_set_id"]
            if not parent_result_id:
                roots.append(rendered)
                continue
            parent_id = "view:" + parent_result_id
            parent = views.get(parent_id)
            child_source = source_views[view_id]
            parent_source = source_views.get(parent_id)
            full_child = full_results.get(view_id)
            if parent is None or parent_source is None:
                roots.append(rendered)
                continue
            explicit_parent_keys = full_child.parent_key_fields if full_child else ()
            explicit_child_keys = full_child.child_key_fields if full_child else ()
            if explicit_parent_keys and explicit_child_keys:
                parent_keys = explicit_parent_keys
                child_keys = explicit_child_keys
            else:
                shared = [
                    item
                    for item in parent_source.exact_grain
                    if item in child_source.exact_grain
                ]
                parent_map = dict(
                    zip(parent_source.exact_grain, parent_source.row_identity_fields)
                )
                child_map = dict(
                    zip(child_source.exact_grain, child_source.row_identity_fields)
                )
                if (
                    not shared
                    or not set(shared) <= set(parent_map)
                    or not set(shared) <= set(child_map)
                ):
                    roots.append(rendered)
                    continue
                parent_keys = tuple(parent_map[item] for item in shared)
                child_keys = tuple(child_map[item] for item in shared)
            grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
            if full_child is None:
                roots.append(rendered)
                continue
            for source_row in full_child.rows:
                key = tuple(str(source_row.get(item)) for item in child_keys)
                grouped.setdefault(key, []).append(
                    {
                        "identity": {
                            name: str(source_row.get(name))
                            for name in full_child.row_identity_fields
                        },
                        "cells": [
                            source_row.get(field.source_field)
                            for field in full_child.display_fields
                        ],
                    }
                )
            for parent_row in parent["rows"]:
                parent_identity = {
                    child: parent_row["identity"].get(parent)
                    for parent, child in zip(parent_keys, child_keys)
                }
                key = tuple(str(parent_identity[item]) for item in child_keys)
                child_rows = grouped.get(key, [])
                rows_url = rendered["rows_url"]
                if rows_url:
                    rows_url += "&" + urlencode(
                        {
                            "parent_identity": json.dumps(
                                parent_identity,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                        }
                    )
                parent_row["collections"][rendered["display_name"]] = {
                    "count": len(child_rows),
                    "columns": rendered["columns"],
                    "rows": child_rows[:20],
                    "rows_url": rows_url,
                    "truncated": len(child_rows) > 20,
                }
                parent["render_mode"] = "nested_collection"
        friendly_notices = {
            "null": "값이 비어 있는 데이터",
            "orphan": "연결 대상이 존재하지 않는 데이터",
            "unbound": "연결 기준을 확인할 수 없는 데이터",
            "duplicate": "중복 가능성이 있는 데이터",
            "truncation": "화면에 일부만 표시한 데이터",
            "freshness": "최신성 확인이 필요한 데이터",
        }
        return {
            "direct_answer": record.envelope.direct_answer,
            "classification": record.execution_classification,
            "source_snapshot": record.source_snapshot,
            "views": roots,
            "quality_notices": [
                {
                    **item.model_dump(mode="json"),
                    "message": f"{friendly_notices[item.kind]} {item.message.split(' ', 1)[-1]}",
                }
                for item in record.envelope.quality_notices
            ],
        }


__all__ = [
    "AnswerDeliveryError",
    "AnswerDeliveryPreparationReceipt",
    "AnswerExportRequest",
    "AnswerFieldBinding",
    "AnswerResultBinding",
    "GovernedAnswerDeliveryService",
    "GovernedAnswerRecord",
    "GovernedQueryAnswerDeliveryContext",
]
