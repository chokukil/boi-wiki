"""Hash-bound Workbench previews with separate approval and Release receipts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha256(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(item in "0123456789abcdef" for item in value[7:])
    )


class WorkbenchGateError(RuntimeError):
    pass


class WorkbenchStaleError(RuntimeError):
    pass


class MigrationWorkbenchShapeOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shape_contract_id: str
    shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    root_object_ref: str
    exact_grain: tuple[str, ...]
    relationship_refs: tuple[str, ...]
    collection_semantics: str | None
    aggregation_semantics: dict[str, object] | None
    fanout_semantics: str | None
    duplicate_policy: str
    completeness_policy: str
    readiness_status: Literal["READY", "BLOCKED"]
    reason_codes: tuple[str, ...]
    selected: bool
    contract_digest: str

    @field_validator("contract_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_SHAPE_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def valid_shape(self) -> "MigrationWorkbenchShapeOption":
        if not self.shape_contract_id.strip() or not self.root_object_ref.strip():
            raise ValueError("WORKBENCH_SHAPE_IDENTITY_REQUIRED")
        if not self.exact_grain:
            raise ValueError("WORKBENCH_EXACT_GRAIN_REQUIRED")
        if self.readiness_status == "READY" and self.reason_codes:
            raise ValueError("WORKBENCH_READY_SHAPE_HAS_REASONS")
        if self.readiness_status == "BLOCKED" and not self.reason_codes:
            raise ValueError("WORKBENCH_BLOCKED_SHAPE_REASON_REQUIRED")
        return self


class MigrationWorkbenchQualityImpact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_contract_id: str
    receipt_digest: str
    scanned_rows: int = Field(ge=0)
    matched_rows: int = Field(ge=0)
    unmatched_rows: int = Field(ge=0)
    null_fk_rows: int = Field(ge=0)
    orphan_rows: int = Field(ge=0)
    duplicate_key_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    fanout_min: int = Field(ge=0)
    fanout_p50: float = Field(ge=0)
    fanout_p95: float = Field(ge=0)
    fanout_max: int = Field(ge=0)
    applied_orphan_policy: Literal[
        "BLOCK", "INCLUDE_UNMATCHED", "EXCLUDE_WITH_DISCLOSURE", "QUARANTINE"
    ]
    evidence_digest: str

    @field_validator("receipt_digest", "evidence_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_QUALITY_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def valid_quality(self) -> "MigrationWorkbenchQualityImpact":
        if self.matched_rows + self.unmatched_rows != self.scanned_rows:
            raise ValueError("WORKBENCH_QUALITY_PARTITION_INVALID")
        if self.null_fk_rows + self.orphan_rows > self.unmatched_rows:
            raise ValueError("WORKBENCH_QUALITY_BREAKDOWN_INVALID")
        expected = self.matched_rows / self.scanned_rows if self.scanned_rows else 1.0
        if abs(self.coverage_ratio - expected) > 1e-12:
            raise ValueError("WORKBENCH_QUALITY_COVERAGE_INVALID")
        if not self.fanout_min <= self.fanout_p50 <= self.fanout_p95 <= self.fanout_max:
            raise ValueError("WORKBENCH_FANOUT_DISTRIBUTION_INVALID")
        return self


class MigrationWorkbenchCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    status: Literal["pass", "fail", "flag", "partial", "skip", "not_run"]
    required: bool
    evidence_digest: str | None
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def valid_check(self) -> "MigrationWorkbenchCheck":
        if not self.check_id.strip():
            raise ValueError("WORKBENCH_CHECK_ID_REQUIRED")
        if self.status == "pass":
            if self.evidence_digest is None or not _sha256(self.evidence_digest):
                raise ValueError("WORKBENCH_PASS_EVIDENCE_REQUIRED")
            if self.reason_codes:
                raise ValueError("WORKBENCH_PASS_REASON_FORBIDDEN")
        elif not self.reason_codes:
            raise ValueError("WORKBENCH_NONPASS_REASON_REQUIRED")
        return self


class MigrationWorkbenchConceptMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_ref: str
    action: Literal["reuse", "evidence", "extend", "new"]
    evidence_digest: str
    rationale: str
    duplicate_risk: bool

    @field_validator("evidence_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_MATCH_EVIDENCE_INVALID")
        return value

    @model_validator(mode="after")
    def valid_match(self) -> "MigrationWorkbenchConceptMatch":
        if not self.concept_ref.strip() or not self.rationale.strip():
            raise ValueError("WORKBENCH_MATCH_EXPLANATION_REQUIRED")
        if self.action == "new" and not self.duplicate_risk:
            raise ValueError("WORKBENCH_NEW_CONCEPT_DUPLICATE_RISK_REQUIRED")
        return self


class MigrationWorkbenchProfileChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    before: Any
    after: Any
    impact: str

    @model_validator(mode="after")
    def valid_change(self) -> "MigrationWorkbenchProfileChange":
        if not self.path.strip() or not self.impact.strip():
            raise ValueError("WORKBENCH_PROFILE_CHANGE_REQUIRED")
        return self


class MigrationWorkbenchProfileDiff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: Literal["domain", "data-mapping", "query"]
    before_digest: str | None
    after_digest: str
    changes: tuple[MigrationWorkbenchProfileChange, ...]

    @field_validator("before_digest", "after_digest")
    @classmethod
    def valid_digest(cls, value: str | None) -> str | None:
        if value is not None and not _sha256(value):
            raise ValueError("WORKBENCH_PROFILE_DIFF_DIGEST_INVALID")
        return value


class MigrationWorkbenchMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    logical_ref: str
    source_ref: str
    table_ref: str
    column_ref: str
    key_role: Literal["primary", "foreign", "attribute", "none"]
    data_type: str
    unit: str | None
    cardinality: Literal["one", "many", "unknown"]
    status: Literal["candidate", "verified", "blocked"]
    evidence_digest: str

    @field_validator("evidence_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_MAPPING_EVIDENCE_INVALID")
        return value

    @model_validator(mode="after")
    def valid_mapping(self) -> "MigrationWorkbenchMapping":
        required = (
            self.mapping_id,
            self.logical_ref,
            self.source_ref,
            self.table_ref,
            self.column_ref,
            self.data_type,
        )
        if any(not item.strip() for item in required):
            raise ValueError("WORKBENCH_MAPPING_IDENTITY_REQUIRED")
        return self


class MigrationWorkbenchGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_ref: str
    label: str
    kind: str


class MigrationWorkbenchGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: str
    relation: str
    target_ref: str
    evidence_digest: str

    @field_validator("evidence_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_GRAPH_EVIDENCE_INVALID")
        return value


class MigrationWorkbenchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    locator: str
    relation: str
    evidence_digest: str

    @field_validator("evidence_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_GROUNDING_EVIDENCE_INVALID")
        return value


class MigrationWorkbenchDryRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_plan_digest: str
    typed_parameters: dict[str, dict[str, Any]]
    protected_sql_ref: str
    result_digest: str
    execution_receipt_digest: str
    attestation_status: Literal["ATTESTED", "PROVISIONAL", "BLOCKED", "NOT_RUN"]
    attestation_receipt_digest: str

    @field_validator(
        "logical_plan_digest",
        "result_digest",
        "execution_receipt_digest",
        "attestation_receipt_digest",
    )
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("WORKBENCH_DRY_RUN_DIGEST_INVALID")
        return value

    @model_validator(mode="after")
    def protected_execution(self) -> "MigrationWorkbenchDryRun":
        if not self.protected_sql_ref.startswith("protected-sql:"):
            raise ValueError("WORKBENCH_PROTECTED_SQL_REF_REQUIRED")
        return self


class MigrationWorkbenchRepair(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason_code: str
    action: str
    candidate_only: Literal[True]


class MigrationWorkbenchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-ontology-migration-workbench-preview/v1"]
    job_id: str
    run_id: str
    candidate_digest: str
    plan_digest: str
    schema_digest: str
    profile_binding_digest: str
    qualification_receipt_id: str
    shape_options: tuple[MigrationWorkbenchShapeOption, ...]
    selected_shape_contract_digest: str
    quality_impacts: tuple[MigrationWorkbenchQualityImpact, ...]
    checks: tuple[MigrationWorkbenchCheck, ...]
    concept_matches: tuple[MigrationWorkbenchConceptMatch, ...] = ()
    profile_diffs: tuple[MigrationWorkbenchProfileDiff, ...] = ()
    mappings: tuple[MigrationWorkbenchMapping, ...] = ()
    graph_nodes: tuple[MigrationWorkbenchGraphNode, ...] = ()
    graph_edges: tuple[MigrationWorkbenchGraphEdge, ...] = ()
    evidence: tuple[MigrationWorkbenchEvidence, ...] = ()
    dry_run: MigrationWorkbenchDryRun | None = None
    repairs: tuple[MigrationWorkbenchRepair, ...] = ()
    gate: Literal["ready", "blocked"]
    blockers: tuple[str, ...]
    preview_digest: str


class MigrationApprovalReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-ontology-migration-approval/v1"]
    status: Literal["approved"]
    actor_id: str
    approved_revision: int
    candidate_digest: str
    preview_digest: str
    plan_digest: str
    schema_digest: str
    qualification_receipt_id: str
    release_created: Literal[False]
    active_pointer_transition: Literal[False]
    receipt_digest: str


class MigrationReleaseReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-ontology-migration-release/v1"]
    status: Literal["released"]
    actor_id: str
    released_revision: int
    candidate_digest: str
    preview_digest: str
    plan_digest: str
    schema_digest: str
    qualification_receipt_id: str
    approval_receipt_digest: str
    promotion_performed: Literal[False]
    active_pointer_transition: Literal[False]
    receipt_digest: str


class MigrationReleaseProposalReceipt(BaseModel):
    """Review proposal only; it never represents a ReleaseManifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-ontology-migration-release-proposal/v1"]
    status: Literal["release_proposed"]
    actor_id: str
    proposed_revision: int
    candidate_digest: str
    preview_digest: str
    plan_digest: str
    schema_digest: str
    qualification_receipt_id: str
    approval_receipt_digest: str
    release_manifest_created: Literal[False]
    promotion_performed: Literal[False]
    active_pointer_transition: Literal[False]
    receipt_digest: str


def create_migration_workbench_preview(
    *,
    job_id: str,
    run_id: str,
    candidate_digest: str,
    plan_digest: str,
    schema_digest: str,
    profile_binding_digest: str,
    qualification_receipt_id: str,
    shape_options: tuple[MigrationWorkbenchShapeOption, ...],
    quality_impacts: tuple[MigrationWorkbenchQualityImpact, ...],
    checks: tuple[MigrationWorkbenchCheck, ...],
    concept_matches: tuple[MigrationWorkbenchConceptMatch, ...] = (),
    profile_diffs: tuple[MigrationWorkbenchProfileDiff, ...] = (),
    mappings: tuple[MigrationWorkbenchMapping, ...] = (),
    graph_nodes: tuple[MigrationWorkbenchGraphNode, ...] = (),
    graph_edges: tuple[MigrationWorkbenchGraphEdge, ...] = (),
    evidence: tuple[MigrationWorkbenchEvidence, ...] = (),
    dry_run: MigrationWorkbenchDryRun | None = None,
    repairs: tuple[MigrationWorkbenchRepair, ...] = (),
) -> MigrationWorkbenchPreview:
    for digest in (
        candidate_digest,
        plan_digest,
        schema_digest,
        profile_binding_digest,
    ):
        if not _sha256(digest):
            raise ValueError("WORKBENCH_PREVIEW_DIGEST_INVALID")
    if not job_id.strip() or not run_id.strip() or not qualification_receipt_id.strip():
        raise ValueError("WORKBENCH_PREVIEW_IDENTITY_REQUIRED")
    selected = tuple(item for item in shape_options if item.selected)
    if len(selected) != 1:
        raise ValueError("WORKBENCH_EXACTLY_ONE_SHAPE_REQUIRED")
    blockers: list[str] = []
    if selected[0].readiness_status != "READY":
        blockers.extend(selected[0].reason_codes)
    if any(item.required and item.status != "pass" for item in checks):
        blockers.append("REQUIRED_CHECK_NOT_PASS")
    values = {
        "schema_name": "boi-ontology-migration-workbench-preview/v1",
        "job_id": job_id,
        "run_id": run_id,
        "candidate_digest": candidate_digest,
        "plan_digest": plan_digest,
        "schema_digest": schema_digest,
        "profile_binding_digest": profile_binding_digest,
        "qualification_receipt_id": qualification_receipt_id,
        "shape_options": tuple(item.model_dump(mode="json") for item in shape_options),
        "selected_shape_contract_digest": selected[0].contract_digest,
        "quality_impacts": tuple(
            item.model_dump(mode="json") for item in quality_impacts
        ),
        "checks": tuple(item.model_dump(mode="json") for item in checks),
        "concept_matches": tuple(
            item.model_dump(mode="json") for item in concept_matches
        ),
        "profile_diffs": tuple(
            item.model_dump(mode="json") for item in profile_diffs
        ),
        "mappings": tuple(item.model_dump(mode="json") for item in mappings),
        "graph_nodes": tuple(
            item.model_dump(mode="json") for item in graph_nodes
        ),
        "graph_edges": tuple(
            item.model_dump(mode="json") for item in graph_edges
        ),
        "evidence": tuple(item.model_dump(mode="json") for item in evidence),
        "dry_run": dry_run.model_dump(mode="json") if dry_run is not None else None,
        "repairs": tuple(item.model_dump(mode="json") for item in repairs),
        "gate": "blocked" if blockers else "ready",
        "blockers": tuple(dict.fromkeys(blockers)),
    }
    return MigrationWorkbenchPreview(
        **{
            key: value
            for key, value in values.items()
            if key not in {
                "shape_options",
                "quality_impacts",
                "checks",
                "concept_matches",
                "profile_diffs",
                "mappings",
                "graph_nodes",
                "graph_edges",
                "evidence",
                "dry_run",
                "repairs",
            }
        },
        shape_options=shape_options,
        quality_impacts=quality_impacts,
        checks=checks,
        concept_matches=concept_matches,
        profile_diffs=profile_diffs,
        mappings=mappings,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        evidence=evidence,
        dry_run=dry_run,
        repairs=repairs,
        preview_digest=_digest(values),
    )


def create_migration_approval_receipt(
    preview: MigrationWorkbenchPreview,
    *,
    actor_id: str,
    expected_revision: int,
    current_revision: int,
    expected_candidate_digest: str,
    expected_preview_digest: str,
    expected_plan_digest: str,
    expected_schema_digest: str,
    expected_qualification_receipt_id: str,
) -> MigrationApprovalReceipt:
    if expected_revision != current_revision:
        raise WorkbenchStaleError("REVISION_CAS_MISMATCH")
    exact = (
        (
            "CANDIDATE_DIGEST_MISMATCH",
            expected_candidate_digest,
            preview.candidate_digest,
        ),
        ("PREVIEW_DIGEST_MISMATCH", expected_preview_digest, preview.preview_digest),
        ("PLAN_DIGEST_MISMATCH", expected_plan_digest, preview.plan_digest),
        ("SCHEMA_DIGEST_MISMATCH", expected_schema_digest, preview.schema_digest),
        (
            "QUALIFICATION_RECEIPT_MISMATCH",
            expected_qualification_receipt_id,
            preview.qualification_receipt_id,
        ),
    )
    for code, expected, actual in exact:
        if expected != actual:
            raise WorkbenchStaleError(code)
    if preview.gate != "ready":
        raise WorkbenchGateError("WORKBENCH_PREVIEW_NOT_READY")
    if not actor_id.strip():
        raise ValueError("WORKBENCH_APPROVER_REQUIRED")
    values = {
        "schema_name": "boi-ontology-migration-approval/v1",
        "status": "approved",
        "actor_id": actor_id,
        "approved_revision": current_revision,
        "candidate_digest": preview.candidate_digest,
        "preview_digest": preview.preview_digest,
        "plan_digest": preview.plan_digest,
        "schema_digest": preview.schema_digest,
        "qualification_receipt_id": preview.qualification_receipt_id,
        "release_created": False,
        "active_pointer_transition": False,
    }
    return MigrationApprovalReceipt(**values, receipt_digest=_digest(values))


def create_migration_release_receipt(
    approval: MigrationApprovalReceipt,
    *,
    actor_id: str,
    expected_revision: int,
    current_revision: int,
    expected_approval_receipt_digest: str,
    expected_preview_digest: str,
) -> MigrationReleaseReceipt:
    if expected_revision != current_revision:
        raise WorkbenchStaleError("REVISION_CAS_MISMATCH")
    if expected_approval_receipt_digest != approval.receipt_digest:
        raise WorkbenchStaleError("APPROVAL_RECEIPT_MISMATCH")
    if expected_preview_digest != approval.preview_digest:
        raise WorkbenchStaleError("PREVIEW_DIGEST_MISMATCH")
    if not actor_id.strip():
        raise ValueError("WORKBENCH_RELEASE_APPROVER_REQUIRED")
    values = {
        "schema_name": "boi-ontology-migration-release/v1",
        "status": "released",
        "actor_id": actor_id,
        "released_revision": current_revision,
        "candidate_digest": approval.candidate_digest,
        "preview_digest": approval.preview_digest,
        "plan_digest": approval.plan_digest,
        "schema_digest": approval.schema_digest,
        "qualification_receipt_id": approval.qualification_receipt_id,
        "approval_receipt_digest": approval.receipt_digest,
        "promotion_performed": False,
        "active_pointer_transition": False,
    }
    return MigrationReleaseReceipt(**values, receipt_digest=_digest(values))


def create_migration_release_proposal_receipt(
    approval: MigrationApprovalReceipt,
    *,
    actor_id: str,
    expected_revision: int,
    current_revision: int,
    expected_approval_receipt_digest: str,
    expected_preview_digest: str,
) -> MigrationReleaseProposalReceipt:
    if expected_revision != current_revision:
        raise WorkbenchStaleError("REVISION_CAS_MISMATCH")
    if expected_approval_receipt_digest != approval.receipt_digest:
        raise WorkbenchStaleError("APPROVAL_RECEIPT_MISMATCH")
    if expected_preview_digest != approval.preview_digest:
        raise WorkbenchStaleError("PREVIEW_DIGEST_MISMATCH")
    if not actor_id.strip():
        raise ValueError("WORKBENCH_RELEASE_PROPOSER_REQUIRED")
    values = {
        "schema_name": "boi-ontology-migration-release-proposal/v1",
        "status": "release_proposed",
        "actor_id": actor_id,
        "proposed_revision": current_revision,
        "candidate_digest": approval.candidate_digest,
        "preview_digest": approval.preview_digest,
        "plan_digest": approval.plan_digest,
        "schema_digest": approval.schema_digest,
        "qualification_receipt_id": approval.qualification_receipt_id,
        "approval_receipt_digest": approval.receipt_digest,
        "release_manifest_created": False,
        "promotion_performed": False,
        "active_pointer_transition": False,
    }
    return MigrationReleaseProposalReceipt(
        **values,
        receipt_digest=_digest(values),
    )


__all__ = [
    "MigrationApprovalReceipt",
    "MigrationReleaseReceipt",
    "MigrationReleaseProposalReceipt",
    "MigrationWorkbenchCheck",
    "MigrationWorkbenchConceptMatch",
    "MigrationWorkbenchDryRun",
    "MigrationWorkbenchEvidence",
    "MigrationWorkbenchGraphEdge",
    "MigrationWorkbenchGraphNode",
    "MigrationWorkbenchMapping",
    "MigrationWorkbenchPreview",
    "MigrationWorkbenchProfileChange",
    "MigrationWorkbenchProfileDiff",
    "MigrationWorkbenchQualityImpact",
    "MigrationWorkbenchRepair",
    "MigrationWorkbenchShapeOption",
    "WorkbenchGateError",
    "WorkbenchStaleError",
    "create_migration_approval_receipt",
    "create_migration_release_receipt",
    "create_migration_release_proposal_receipt",
    "create_migration_workbench_preview",
]
