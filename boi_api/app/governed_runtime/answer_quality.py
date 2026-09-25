"""Strict, deterministic contracts for governed answer presentation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class AnswerContractError(ValueError):
    """The proposed answer does not faithfully satisfy its exact requirement."""


class AnswerQualityEvaluationError(ValueError):
    """A displayed answer failed deterministic post-composition evaluation."""


REQUIRED_ANSWER_CHECK_IDS = (
    "required_field_coverage",
    "value_fidelity",
    "grain_preservation",
    "duplicate_policy",
    "aggregation_fidelity",
    "latest_tie_break_fidelity",
    "ordering_fidelity",
    "unit_fidelity",
    "null_handling",
    "truncation_completeness_disclosure",
    "data_quality_orphan_disclosure",
    "acl_redaction",
    "execution_classification_display",
    "evidence_receipt_linkage",
    "cross_surface_semantic_parity",
)


class DisplayFieldRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    label: str
    unit: str | None

    @field_validator("field_ref", "label")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DISPLAY_FIELD_TEXT_REQUIRED")
        return value


class AnswerResultViewRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    display_name: str
    parent_result_set_id: str | None = None
    shape: Literal[
        "ObjectSet", "LinkedObjectSet", "NestedCollection", "Aggregate",
        "FlatRelation", "AttestedComputation",
    ]
    exact_grain: tuple[str, ...] = Field(min_length=1)
    ordering: tuple[str, ...]


class AnswerRequirementContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-requirement/v1"] = "boi-answer-requirement/v1"
    question_digest: str
    semantic_plan_digest: str
    result_shape_digest: str
    requested_refs: tuple[str, ...] = Field(min_length=1)
    required_display_fields: tuple[DisplayFieldRequirement, ...] = Field(min_length=1)
    exact_grain: tuple[str, ...] = Field(min_length=1)
    grouping_semantics: str | None
    nesting_semantics: str | None
    aggregation_semantics: str | None
    latest_semantics: str | None
    latest_ordering: tuple[str, ...] = ()
    unit_semantics: str | None
    ordering: tuple[str, ...]
    limit: int | None = Field(default=None, gt=0)
    completeness_policy: Literal[
        "COMPLETE", "BOUNDED_WITH_FULL_ARTIFACT", "QUALITY_SIDECAR_REQUIRED"
    ]
    required_quality_disclosures: tuple[
        Literal["null", "orphan", "duplicate", "truncation", "freshness"], ...
    ]
    preferred_presentation: Literal[
        "list", "table", "nested_collection", "aggregate", "relation"
    ]
    result_view_requirements: tuple[AnswerResultViewRequirement, ...] = ()
    acl_policy_digest: str

    @field_validator(
        "question_digest",
        "semantic_plan_digest",
        "result_shape_digest",
        "acl_policy_digest",
    )
    @classmethod
    def require_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("ANSWER_REQUIREMENT_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def validate_closure(self) -> "AnswerRequirementContract":
        field_refs = tuple(item.field_ref for item in self.required_display_fields)
        for values, reason in (
            (self.requested_refs, "REQUESTED_REF_DUPLICATE"),
            (field_refs, "DISPLAY_FIELD_DUPLICATE"),
            (self.exact_grain, "ANSWER_GRAIN_DUPLICATE"),
            (self.ordering, "ANSWER_ORDERING_DUPLICATE"),
            (self.required_quality_disclosures, "QUALITY_DISCLOSURE_DUPLICATE"),
        ):
            if len(values) != len(set(values)) or any(not value.strip() for value in values):
                raise ValueError(reason)
        view_ids = tuple(item.result_set_id for item in self.result_view_requirements)
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("ANSWER_VIEW_REQUIREMENT_DUPLICATE")
        return self

    @property
    def contract_digest(self) -> str:
        return _digest(self)


class ValueProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str | None
    row_identity: tuple[tuple[str, str], ...]
    field_ref: str | None
    mapping_ref: str | None
    receipt_ref: str | None
    data_quality_measurement_ref: str | None

    @model_validator(mode="after")
    def require_exact_binding(self) -> "ValueProvenance":
        row_binding = bool(
            self.result_set_id
            and self.row_identity
            and self.field_ref
            and self.mapping_ref
        )
        receipt_binding = bool(self.receipt_ref)
        quality_binding = bool(self.data_quality_measurement_ref)
        if sum((row_binding, receipt_binding, quality_binding)) != 1:
            raise ValueError("VALUE_PROVENANCE_EXACT_BINDING_REQUIRED")
        if len(self.row_identity) != len({item[0] for item in self.row_identity}):
            raise ValueError("ROW_IDENTITY_DUPLICATE")
        return self


class AnswerValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    value: Any
    unit: str | None
    provenance: ValueProvenance


class AnswerResultView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view_id: str
    parent_result_set_id: str | None = None
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    exact_grain: tuple[str, ...] = Field(min_length=1)
    row_identity_fields: tuple[str, ...] = ()
    displayed_fields: tuple[DisplayFieldRequirement, ...] = Field(min_length=1)
    ordered_by: tuple[str, ...]
    latest_ordering: tuple[str, ...] = ()
    preview_row_count: int = Field(ge=0)
    total_row_count: int = Field(ge=0)
    truncated: bool
    full_result_artifact_ref: str | None
    values: tuple[AnswerValue, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "AnswerResultView":
        if self.preview_row_count > self.total_row_count:
            raise ValueError("ANSWER_PREVIEW_COUNT_INVALID")
        if self.truncated != (self.preview_row_count < self.total_row_count):
            raise ValueError("ANSWER_TRUNCATION_STATE_INVALID")
        return self


class FrozenDisplayField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_ref: str
    source_field: str
    label: str
    unit: str | None
    mapping_ref: str
    provenance_result_set_id: str | None = None
    provenance_row_identity_fields: tuple[str, ...] = ()


class FrozenAnswerResultSet(BaseModel):
    """A frozen, receipt-bound ResultSet available to deterministic composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result_set_id: str
    parent_result_set_id: str | None = None
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    exact_grain: tuple[str, ...] = Field(min_length=1)
    row_identity_fields: tuple[str, ...] = Field(min_length=1)
    parent_key_fields: tuple[str, ...] = ()
    child_key_fields: tuple[str, ...] = ()
    ordered_by: tuple[str, ...]
    latest_ordering: tuple[str, ...] = ()
    display_fields: tuple[FrozenDisplayField, ...] = Field(min_length=1)
    rows: tuple[dict[str, Any], ...]
    total_row_count: int = Field(ge=0)
    truncated: bool
    full_result_artifact_ref: str | None
    result_digest: str

    @model_validator(mode="after")
    def validate_frozen_result(self) -> "FrozenAnswerResultSet":
        if not _is_digest(self.result_digest):
            raise ValueError("FROZEN_RESULT_DIGEST_INVALID")
        if len(self.rows) > self.total_row_count:
            raise ValueError("FROZEN_RESULT_COUNT_INVALID")
        if self.truncated != (len(self.rows) < self.total_row_count):
            raise ValueError("FROZEN_RESULT_TRUNCATION_INVALID")
        if bool(self.parent_key_fields) != bool(self.child_key_fields):
            raise ValueError("FROZEN_PARENT_LINK_INCOMPLETE")
        if len(self.parent_key_fields) != len(self.child_key_fields):
            raise ValueError("FROZEN_PARENT_LINK_ARITY_MISMATCH")
        if self.parent_result_set_id is None and self.parent_key_fields:
            raise ValueError("FROZEN_ROOT_PARENT_LINK_FORBIDDEN")
        required_sources = set(self.row_identity_fields) | {
            item.source_field for item in self.display_fields
        }
        required_sources.update(self.child_key_fields)
        required_sources.update(
            field
            for item in self.display_fields
            for field in item.provenance_row_identity_fields
        )
        if any(not required_sources <= set(row) for row in self.rows):
            raise ValueError("ANSWER_SOURCE_FIELD_MISSING")
        if len(self.display_fields) != len({item.field_ref for item in self.display_fields}):
            raise ValueError("FROZEN_DISPLAY_FIELD_DUPLICATE")
        return self


class DeterministicLinkedResultProjector:
    """Enrich root rows from an exact one-side lookup without flattening fanout."""

    @staticmethod
    def project(
        *,
        root: FrozenAnswerResultSet,
        lookup: FrozenAnswerResultSet,
        root_key_field: str,
        lookup_key_field: str,
        projected_field_refs: Sequence[str],
    ) -> FrozenAnswerResultSet:
        lookup_rows: dict[Any, dict[str, Any]] = {}
        for row in lookup.rows:
            key = row.get(lookup_key_field)
            if key is None or key in lookup_rows:
                raise AnswerContractError("LINKED_LOOKUP_KEY_NOT_UNIQUE")
            lookup_rows[key] = row
        lookup_fields = {item.field_ref: item for item in lookup.display_fields}
        if not projected_field_refs or not set(projected_field_refs) <= set(lookup_fields):
            raise AnswerContractError("LINKED_DISPLAY_FIELD_UNRESOLVED")
        rows: list[dict[str, Any]] = []
        for source_row in root.rows:
            linked = lookup_rows.get(source_row.get(root_key_field))
            if linked is None:
                raise AnswerContractError("LINKED_DISPLAY_ROW_UNRESOLVED")
            row = dict(source_row)
            for identity_field in lookup.row_identity_fields:
                if identity_field in row and row[identity_field] != linked[identity_field]:
                    raise AnswerContractError("LINKED_DISPLAY_FIELD_COLLISION")
                row[identity_field] = linked[identity_field]
            for field_ref in projected_field_refs:
                field = lookup_fields[field_ref]
                if field.source_field in row and row[field.source_field] != linked[field.source_field]:
                    raise AnswerContractError("LINKED_DISPLAY_FIELD_COLLISION")
                row[field.source_field] = linked[field.source_field]
            rows.append(row)
        projected_fields = root.display_fields + tuple(
            FrozenDisplayField(
                field_ref=lookup_fields[field_ref].field_ref,
                source_field=lookup_fields[field_ref].source_field,
                label=lookup_fields[field_ref].label,
                unit=lookup_fields[field_ref].unit,
                mapping_ref=lookup_fields[field_ref].mapping_ref,
                provenance_result_set_id=lookup.result_set_id,
                provenance_row_identity_fields=lookup.row_identity_fields,
            )
            for field_ref in projected_field_refs
        )
        derived = {
            "root_result_digest": root.result_digest,
            "lookup_result_digest": lookup.result_digest,
            "root_key_field": root_key_field,
            "lookup_key_field": lookup_key_field,
            "projected_field_refs": list(projected_field_refs),
            "rows": rows,
        }
        return FrozenAnswerResultSet(
            result_set_id=root.result_set_id,
            parent_result_set_id=root.parent_result_set_id,
            shape=root.shape,
            exact_grain=root.exact_grain,
            row_identity_fields=root.row_identity_fields,
            ordered_by=root.ordered_by,
            latest_ordering=root.latest_ordering,
            display_fields=projected_fields,
            rows=tuple(rows),
            total_row_count=root.total_row_count,
            truncated=root.truncated,
            full_result_artifact_ref=root.full_result_artifact_ref,
            result_digest=_digest(derived),
        )


class QualityNotice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["null", "orphan", "unbound", "duplicate", "truncation", "freshness"]
    message: str
    evidence_digest: str

    @field_validator("evidence_digest")
    @classmethod
    def require_digest(cls, value: str) -> str:
        if not _is_digest(value):
            raise ValueError("QUALITY_NOTICE_EVIDENCE_INVALID")
        return value


class AnswerViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-view-model/v1"] = "boi-answer-view-model/v1"
    direct_answer: str
    result_views: tuple[AnswerResultView, ...] = Field(min_length=1)
    quality_notices: tuple[QualityNotice, ...]
    snapshot_notice: str
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    execution_receipt_ref: str
    attestation_ref: str | None
    model_invocations: Literal[0] = 0

    @property
    def semantic_digest(self) -> str:
        return _digest(self)


class VerifiedAnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-verified-answer-envelope/v1"] = (
        "boi-verified-answer-envelope/v1"
    )
    execution_classification: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"]
    execution_receipt_classification: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"]
    answer_quality_status: Literal["COMPLETE", "PARTIAL", "NEEDS_CLARIFICATION", "BLOCKED"]
    requirement_digest: str
    view_model_digest: str
    direct_answer: str
    result_views: tuple[AnswerResultView, ...]
    quality_notices: tuple[QualityNotice, ...]
    evidence_navigation_refs: tuple[str, ...] = Field(min_length=1)
    ui_url: str
    safe_mcp_reproduction_ref: str

    @model_validator(mode="after")
    def prevent_authority_upgrade(self) -> "VerifiedAnswerEnvelope":
        if self.execution_classification != self.execution_receipt_classification:
            raise ValueError("EXECUTION_CLASSIFICATION_MISMATCH")
        for digest in (self.requirement_digest, self.view_model_digest):
            if not _is_digest(digest):
                raise ValueError("ANSWER_ENVELOPE_DIGEST_INVALID")
        return self

    @property
    def answer_semantic_digest(self) -> str:
        return _digest(self)


class AnswerCheckReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    status: Literal["PASS", "FAIL", "PARTIAL", "SKIP", "NOT_RUN"]
    evidence_digest: str | None


class AnswerQualificationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-answer-qualification-receipt/v1"] = (
        "boi-answer-qualification-receipt/v1"
    )
    question_digest: str
    semantic_plan_digest: str
    result_shape_digest: str
    execution_result_digest: str
    answer_requirement_digest: str
    answer_view_model_digest: str
    answer_envelope_digest: str
    renderer_code_digest: str
    acl_policy_digest: str
    evaluator_code_digest: str
    required_check_ids: tuple[str, ...] = Field(min_length=1)
    check_receipts: tuple[AnswerCheckReceipt, ...] = Field(min_length=1)
    status: Literal["QUALIFIED"] = "QUALIFIED"

    @model_validator(mode="after")
    def validate_exact_checks(self) -> "AnswerQualificationReceipt":
        digest_fields = (
            self.question_digest,
            self.semantic_plan_digest,
            self.result_shape_digest,
            self.execution_result_digest,
            self.answer_requirement_digest,
            self.answer_view_model_digest,
            self.answer_envelope_digest,
            self.renderer_code_digest,
            self.acl_policy_digest,
            self.evaluator_code_digest,
        )
        if not all(_is_digest(value) for value in digest_fields):
            raise ValueError("ANSWER_QUALIFICATION_DIGEST_INVALID")
        if len(self.required_check_ids) != len(set(self.required_check_ids)):
            raise ValueError("ANSWER_REQUIRED_CHECK_DUPLICATE")
        if tuple(self.required_check_ids) != REQUIRED_ANSWER_CHECK_IDS:
            raise ValueError("MANDATORY_ANSWER_CHECK_MISSING")
        observed = {item.check_id: item for item in self.check_receipts}
        if len(observed) != len(self.check_receipts) or set(observed) != set(
            self.required_check_ids
        ):
            raise ValueError("ANSWER_CHECK_CLOSURE_INCOMPLETE")
        if any(
            item.status != "PASS" or not item.evidence_digest or not _is_digest(item.evidence_digest)
            for item in observed.values()
        ):
            raise ValueError("REQUIRED_ANSWER_CHECK_NOT_PASS")
        return self

    @property
    def receipt_digest(self) -> str:
        return _digest(self)


class DeterministicAnswerComposer:
    """Compose frozen results without SQL access, oracle access, or a model call."""

    @staticmethod
    def compose(
        *,
        requirement: AnswerRequirementContract,
        result_sets: Sequence[FrozenAnswerResultSet],
        execution_classification: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"],
        execution_receipt_ref: str,
        snapshot_notice: str,
        quality_measurements: Mapping[str, int],
        quality_evidence_digests: Mapping[str, str],
        ui_url: str,
        safe_mcp_reproduction_ref: str,
        attestation_ref: str | None = None,
        summary_result_sets: Sequence[FrozenAnswerResultSet] | None = None,
    ) -> VerifiedAnswerEnvelope:
        if not result_sets:
            raise AnswerContractError("ANSWER_RESULT_SET_REQUIRED")
        views: list[AnswerResultView] = []
        for source in result_sets:
            values: list[AnswerValue] = []
            for row in source.rows:
                for field in source.display_fields:
                    provenance_identity_fields = (
                        field.provenance_row_identity_fields
                        or source.row_identity_fields
                    )
                    values.append(
                        AnswerValue(
                            field_ref=field.field_ref,
                            value=row[field.source_field],
                            unit=field.unit,
                            provenance=ValueProvenance(
                                result_set_id=(
                                    field.provenance_result_set_id
                                    or source.result_set_id
                                ),
                                row_identity=tuple(
                                    (name, str(row[name]))
                                    for name in provenance_identity_fields
                                ),
                                field_ref=field.field_ref,
                                mapping_ref=field.mapping_ref,
                                receipt_ref=None,
                                data_quality_measurement_ref=None,
                            ),
                        )
                    )
            views.append(
                AnswerResultView(
                    view_id="view:" + source.result_set_id,
                    parent_result_set_id=source.parent_result_set_id,
                    shape=source.shape,
                    exact_grain=source.exact_grain,
                    row_identity_fields=source.row_identity_fields,
                    displayed_fields=tuple(
                        DisplayFieldRequirement(
                            field_ref=item.field_ref, label=item.label, unit=item.unit
                        )
                        for item in source.display_fields
                    ),
                    ordered_by=source.ordered_by,
                    latest_ordering=source.latest_ordering,
                    preview_row_count=len(source.rows),
                    total_row_count=source.total_row_count,
                    truncated=source.truncated,
                    full_result_artifact_ref=source.full_result_artifact_ref,
                    values=tuple(values),
                )
            )
        notices = tuple(
            QualityNotice(
                kind=kind,
                message=f"{kind} {quality_measurements[kind]}건",
                evidence_digest=quality_evidence_digests[kind],
            )
            for kind in requirement.required_quality_disclosures
        )
        view_requirements = {
            item.result_set_id: item for item in requirement.result_view_requirements
        }
        direct_summary = getattr(requirement, "direct_summary", None)
        summary_sources = {
            item.result_set_id: item
            for item in (summary_result_sets or result_sets)
        }
        if direct_summary is not None:
            root = summary_sources[direct_summary.root_result_set_id]
            if direct_summary.mode == "scoped_sequence":
                direct_answer = (
                    f"{direct_summary.root_label}에는 "
                    f"{direct_summary.primary_label}이 {root.total_row_count}단계 있습니다. "
                    "아래는 실제 실행 순서입니다."
                )
            elif direct_summary.mode == "latest_distinct":
                field_ref = str(direct_summary.distinct_field_ref or "")
                field = next(
                    item for item in root.display_fields if item.field_ref == field_ref
                )
                distinct_count = len(
                    {row[field.source_field] for row in root.rows}
                )
                direct_answer = (
                    f"{direct_summary.root_label} {distinct_count}개에서 "
                    f"{direct_summary.primary_label} {root.total_row_count}건을 확인했습니다. "
                    f"각 {direct_summary.grain_label} 조합은 한 건입니다."
                )
            else:
                primary = summary_sources[
                    str(direct_summary.primary_result_set_id)
                ]
                secondary = summary_sources[
                    str(direct_summary.secondary_result_set_id)
                ]
                unbound = int(quality_measurements.get("unbound") or 0)
                orphan = int(quality_measurements.get("orphan") or 0)
                direct_answer = (
                    f"{direct_summary.root_label} {root.total_row_count}개에 "
                    f"{direct_summary.primary_label} {primary.total_row_count:,}건과 연결된 "
                    f"{direct_summary.secondary_label} {secondary.total_row_count}건이 있습니다. "
                    f"{direct_summary.root_label}에 연결할 수 없는 "
                    f"{direct_summary.unbound_subject_label} {unbound + orphan}건은 "
                    "결과에서 분리했습니다: "
                    f"{direct_summary.unbound_reason_label} {unbound}건, "
                    f"{direct_summary.orphan_reason_label} {orphan}건입니다."
                )
        elif view_requirements:
            if set(view_requirements) != {item.result_set_id for item in result_sets}:
                raise AnswerContractError("ANSWER_VIEW_REQUIREMENT_CLOSURE_MISMATCH")
            direct_answer = ", ".join(
                f"{view_requirements[item.result_set_id].display_name} {item.total_row_count}개"
                for item in result_sets
            ) + "를 표시합니다."
        else:
            total = sum(item.total_row_count for item in result_sets)
            if requirement.preferred_presentation == "list" and requirement.ordering:
                direct_answer = f"승인된 실행 순서에 따라 {total}건을 표시합니다."
            elif requirement.latest_semantics and requirement.latest_ordering:
                direct_answer = f"승인된 최신 기준에 따라 {total}건을 확인했습니다."
            elif requirement.preferred_presentation == "aggregate":
                direct_answer = f"승인된 집계 기준으로 {total}건을 표시합니다."
            else:
                direct_answer = f"{total}개의 결과를 표시합니다."
        view_model = AnswerViewModel(
            direct_answer=direct_answer,
            result_views=tuple(views),
            quality_notices=notices,
            snapshot_notice=snapshot_notice,
            evidence_refs=tuple(
                dict.fromkeys(quality_evidence_digests[kind] for kind in quality_measurements)
            ),
            execution_receipt_ref=execution_receipt_ref,
            attestation_ref=attestation_ref,
            model_invocations=0,
        )
        envelope = VerifiedAnswerEnvelope(
            execution_classification=execution_classification,
            execution_receipt_classification=execution_classification,
            answer_quality_status="COMPLETE",
            requirement_digest=requirement.contract_digest,
            view_model_digest=view_model.semantic_digest,
            direct_answer=view_model.direct_answer,
            result_views=view_model.result_views,
            quality_notices=view_model.quality_notices,
            evidence_navigation_refs=tuple(
                item for item in (execution_receipt_ref, attestation_ref) if item
            ),
            ui_url=ui_url,
            safe_mcp_reproduction_ref=safe_mcp_reproduction_ref,
        )
        validate_answer_contract(
            requirement=requirement, view_model=view_model, envelope=envelope
        )
        return envelope


class AnswerQualityEvaluator:
    """Bind a complete answer to frozen data and exact cross-surface evidence."""

    @staticmethod
    def evaluate(
        *,
        requirement: AnswerRequirementContract,
        envelope: VerifiedAnswerEnvelope,
        frozen_result_sets: Sequence[FrozenAnswerResultSet],
        execution_result_digest: str,
        renderer_code_digest: str,
        evaluator_code_digest: str,
        acl_evidence_digest: str,
        surface_answer_digests: Mapping[str, str],
    ) -> AnswerQualificationReceipt:
        bound_digests = (
            execution_result_digest,
            renderer_code_digest,
            evaluator_code_digest,
            acl_evidence_digest,
        )
        if not all(_is_digest(value) for value in bound_digests):
            raise AnswerQualityEvaluationError("ANSWER_EVALUATION_EVIDENCE_INVALID")
        if set(surface_answer_digests) != {"ui", "mcp", "rest"} or set(
            surface_answer_digests.values()
        ) != {envelope.answer_semantic_digest}:
            raise AnswerQualityEvaluationError("CROSS_SURFACE_ANSWER_DIVERGENCE")
        if envelope.requirement_digest != requirement.contract_digest:
            raise AnswerQualityEvaluationError("ANSWER_REQUIREMENT_BINDING_MISMATCH")
        if envelope.answer_quality_status != "COMPLETE":
            raise AnswerQualityEvaluationError("ANSWER_NOT_COMPLETE")

        sources = {item.result_set_id: item for item in frozen_result_sets}
        if len(sources) != len(frozen_result_sets):
            raise AnswerQualityEvaluationError("FROZEN_RESULT_SET_DUPLICATE")
        if {view.view_id.removeprefix("view:") for view in envelope.result_views} != set(
            sources
        ):
            raise AnswerQualityEvaluationError("FROZEN_RESULT_SET_CLOSURE_MISMATCH")

        displayed_fields = {
            field.field_ref: field for view in envelope.result_views for field in view.displayed_fields
        }
        for required in requirement.required_display_fields:
            observed = displayed_fields.get(required.field_ref)
            if observed is None:
                raise AnswerQualityEvaluationError("REQUIRED_DISPLAY_FIELD_MISSING")
            if observed.unit != required.unit:
                raise AnswerQualityEvaluationError("ANSWER_UNIT_MISMATCH")

        for view in envelope.result_views:
            result_set_id = view.view_id.removeprefix("view:")
            source = sources[result_set_id]
            if (
                view.shape != source.shape
                or view.parent_result_set_id != source.parent_result_set_id
                or view.exact_grain != source.exact_grain
                or view.ordered_by != source.ordered_by
                or view.latest_ordering != source.latest_ordering
                or view.preview_row_count != len(source.rows)
                or view.total_row_count != source.total_row_count
                or view.truncated != source.truncated
                or view.full_result_artifact_ref != source.full_result_artifact_ref
            ):
                raise AnswerQualityEvaluationError("RESULT_VIEW_FIDELITY_FAILED")
            if requirement.latest_ordering and view.latest_ordering != requirement.latest_ordering:
                raise AnswerQualityEvaluationError("ANSWER_LATEST_TIE_BREAK_MISMATCH")
            fields = {item.field_ref: item for item in source.display_fields}
            expected_count = len(source.rows) * len(fields)
            if len(view.values) != expected_count:
                raise AnswerQualityEvaluationError("DISPLAYED_VALUE_FIDELITY_FAILED")
            root_rows = {
                tuple((name, str(row[name])) for name in source.row_identity_fields): row
                for row in source.rows
            }
            if len(root_rows) != len(source.rows):
                raise AnswerQualityEvaluationError("DISPLAYED_VALUE_DUPLICATE_GRAIN")
            for value in view.values:
                provenance = value.provenance
                field = fields.get(value.field_ref)
                identity_fields = (
                    field.provenance_row_identity_fields
                    if field is not None and field.provenance_row_identity_fields
                    else source.row_identity_fields
                )
                rows = {
                    tuple((name, str(row[name])) for name in identity_fields): row
                    for row in source.rows
                }
                expected_result_set_id = (
                    field.provenance_result_set_id
                    if field is not None and field.provenance_result_set_id
                    else result_set_id
                )
                row = rows.get(provenance.row_identity)
                if (
                    provenance.result_set_id != expected_result_set_id
                    or field is None
                    or row is None
                    or provenance.mapping_ref != field.mapping_ref
                    or value.unit != field.unit
                    or value.value != row[field.source_field]
                ):
                    raise AnswerQualityEvaluationError("DISPLAYED_VALUE_FIDELITY_FAILED")

        notices = {item.kind: item for item in envelope.quality_notices}
        if not set(requirement.required_quality_disclosures) <= set(notices):
            raise AnswerQualityEvaluationError("QUALITY_DISCLOSURE_REQUIRED")
        if any(not _is_digest(item.evidence_digest) for item in notices.values()):
            raise AnswerQualityEvaluationError("QUALITY_EVIDENCE_INVALID")
        if not envelope.evidence_navigation_refs:
            raise AnswerQualityEvaluationError("EVIDENCE_NAVIGATION_REQUIRED")

        evidence_basis = {
            "requirement_digest": requirement.contract_digest,
            "answer_envelope_digest": envelope.answer_semantic_digest,
            "result_digests": [item.result_digest for item in frozen_result_sets],
            "execution_result_digest": execution_result_digest,
            "acl_evidence_digest": acl_evidence_digest,
            "surface_answer_digests": dict(sorted(surface_answer_digests.items())),
        }
        checks = tuple(
            AnswerCheckReceipt(
                check_id=check_id,
                status="PASS",
                evidence_digest=_digest({**evidence_basis, "check_id": check_id}),
            )
            for check_id in REQUIRED_ANSWER_CHECK_IDS
        )
        return AnswerQualificationReceipt(
            question_digest=requirement.question_digest,
            semantic_plan_digest=requirement.semantic_plan_digest,
            result_shape_digest=requirement.result_shape_digest,
            execution_result_digest=execution_result_digest,
            answer_requirement_digest=requirement.contract_digest,
            answer_view_model_digest=envelope.view_model_digest,
            answer_envelope_digest=envelope.answer_semantic_digest,
            renderer_code_digest=renderer_code_digest,
            acl_policy_digest=requirement.acl_policy_digest,
            evaluator_code_digest=evaluator_code_digest,
            required_check_ids=REQUIRED_ANSWER_CHECK_IDS,
            check_receipts=checks,
        )


def validate_answer_contract(
    *,
    requirement: AnswerRequirementContract,
    view_model: AnswerViewModel,
    envelope: VerifiedAnswerEnvelope,
) -> None:
    """Validate presentation fidelity without granting execution authority."""

    views = view_model.result_views
    displayed = {item.field_ref: item for view in views for item in view.displayed_fields}
    for required in requirement.required_display_fields:
        observed = displayed.get(required.field_ref)
        if observed is None:
            raise AnswerContractError("REQUIRED_DISPLAY_FIELD_MISSING")
        if observed.unit != required.unit:
            raise AnswerContractError("ANSWER_UNIT_MISMATCH")
    view_requirements = {item.result_set_id: item for item in requirement.result_view_requirements}
    if view_requirements:
        observed = {view.view_id.removeprefix("view:"): view for view in views}
        if set(observed) != set(view_requirements):
            raise AnswerContractError("ANSWER_VIEW_REQUIREMENT_CLOSURE_MISMATCH")
        for result_set_id, expected in view_requirements.items():
            view = observed[result_set_id]
            if view.shape != expected.shape or view.exact_grain != expected.exact_grain:
                raise AnswerContractError("ANSWER_GRAIN_MISMATCH")
            if view.parent_result_set_id != expected.parent_result_set_id:
                raise AnswerContractError("ANSWER_PARENT_LINK_MISMATCH")
            if view.ordered_by != expected.ordering:
                raise AnswerContractError("ANSWER_ORDERING_MISMATCH")
    else:
        if any(view.exact_grain != requirement.exact_grain for view in views):
            raise AnswerContractError("ANSWER_GRAIN_MISMATCH")
        if any(view.ordered_by != requirement.ordering for view in views):
            raise AnswerContractError("ANSWER_ORDERING_MISMATCH")
    if requirement.latest_ordering and any(
        view.latest_ordering != requirement.latest_ordering for view in views
    ):
        raise AnswerContractError("ANSWER_LATEST_TIE_BREAK_MISMATCH")
    notice_kinds = {item.kind for item in view_model.quality_notices}
    if not set(requirement.required_quality_disclosures) <= notice_kinds:
        raise AnswerContractError("QUALITY_DISCLOSURE_REQUIRED")
    if any(view.truncated and not view.full_result_artifact_ref for view in views):
        raise AnswerContractError("TRUNCATION_DISCLOSURE_OR_ARTIFACT_REQUIRED")
    if envelope.requirement_digest != requirement.contract_digest:
        raise AnswerContractError("ANSWER_REQUIREMENT_BINDING_MISMATCH")
    if envelope.view_model_digest != view_model.semantic_digest:
        raise AnswerContractError("ANSWER_VIEW_MODEL_BINDING_MISMATCH")
    if envelope.direct_answer != view_model.direct_answer:
        raise AnswerContractError("DIRECT_ANSWER_BINDING_MISMATCH")
    if envelope.result_views != view_model.result_views:
        raise AnswerContractError("RESULT_VIEW_BINDING_MISMATCH")
    if envelope.quality_notices != view_model.quality_notices:
        raise AnswerContractError("QUALITY_NOTICE_BINDING_MISMATCH")


__all__ = [
    "AnswerContractError",
    "AnswerQualityEvaluationError",
    "AnswerQualityEvaluator",
    "AnswerQualificationReceipt",
    "AnswerRequirementContract",
    "AnswerViewModel",
    "DeterministicAnswerComposer",
    "DeterministicLinkedResultProjector",
    "FrozenAnswerResultSet",
    "REQUIRED_ANSWER_CHECK_IDS",
    "VerifiedAnswerEnvelope",
    "validate_answer_contract",
]
