"""Deterministic attester for candidate-preview exploratory execution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .bulk_migration_execution import CandidateFreezeReceipt
from .cold_candidate_query_planner import ColdCandidateLogicalPlan
from .multi_result_query_gateway import (
    MultiResultPlanAuthorityReceipt,
    MultiResultQueryExecution,
)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class CandidateExecutionAttestation:
    attestation_version: str
    status: str
    result_classification: str
    candidate_plan_digest: str
    logical_plan_digest: str
    plan_authority_receipt_digest: str
    gateway_receipt_digest: str
    result_digest: str
    freeze_receipt_digest: str
    check_ids: tuple[str, ...]
    production_qualified: bool
    active_transition: bool
    attestation_digest: str


def attest_candidate_execution(
    *,
    candidate: ColdCandidateLogicalPlan,
    authority: MultiResultPlanAuthorityReceipt,
    execution: MultiResultQueryExecution,
    freeze_receipt: CandidateFreezeReceipt,
) -> CandidateExecutionAttestation:
    checks = {
        "authority_pass": authority.status == "PASS",
        "authority_plan_match": authority.plan_digest == candidate.plan.plan_digest,
        "gateway_plan_match": execution.receipt.logical_plan_digest
        == candidate.plan.plan_digest,
        "gateway_validation_match": execution.receipt.validation_receipt_digest
        == authority.receipt_digest,
        "result_digest_match": execution.receipt.result_digest
        == execution.result.result_digest,
        "provisional_lane": execution.lane == "exploratory"
        and execution.result_status == "PROVISIONAL",
        "protected_sql": execution.receipt.executed_sql is None,
        "candidate_authority": candidate.authority_scope == "candidate_preview"
        and candidate.production_qualified is False,
        "freeze_status": freeze_receipt.status == "frozen"
        and freeze_receipt.prefreeze_oracle_access_count == 0,
        "freeze_plan_match": freeze_receipt.logical_plan_digest
        == candidate.plan.plan_digest,
    }
    failed = tuple(key for key, passed in checks.items() if not passed)
    if failed:
        raise ValueError("CANDIDATE_ATTESTATION_FAILED:" + ",".join(failed))
    payload = {
        "attestation_version": "boi/candidate-execution-attestation@1.0.0",
        "status": "PASS",
        "result_classification": "PROVISIONAL",
        "candidate_plan_digest": candidate.candidate_plan_digest,
        "logical_plan_digest": candidate.plan.plan_digest,
        "plan_authority_receipt_digest": authority.receipt_digest,
        "gateway_receipt_digest": execution.receipt.receipt_digest,
        "result_digest": execution.result.result_digest,
        "freeze_receipt_digest": freeze_receipt.receipt_digest,
        "check_ids": list(checks),
        "production_qualified": False,
        "active_transition": False,
    }
    return CandidateExecutionAttestation(
        **{key: value for key, value in payload.items() if key != "check_ids"},
        check_ids=tuple(checks),
        attestation_digest=_digest(payload),
    )
