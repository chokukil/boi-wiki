"""Deterministic six-state query answerability and candidate-only repair contract."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


AnswerabilityState = Literal[
    "EXECUTABLE_NOW",
    "CLARIFICATION_REQUIRED",
    "CONTRACT_GAP_REPAIRABLE",
    "POLICY_BLOCKED",
    "CAPABILITY_UNSUPPORTED",
    "DATA_UNAVAILABLE",
]


class ContractGapRepairCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["candidate_only"] = "candidate_only"
    missing_dependency_ids: tuple[str, ...]
    active_release_digest: str
    query_digest: str
    workbench_route: Literal["/ontology/migrations"] = "/ontology/migrations"
    approved: Literal[False] = False
    released: Literal[False] = False
    active: Literal[False] = False
    candidate_digest: str


class QueryAnswerabilityReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-query-answerability/v1"] = (
        "boi-query-answerability/v1"
    )
    state: AnswerabilityState
    executable: bool
    reason_codes: tuple[str, ...]
    missing_dependency_ids: tuple[str, ...]
    active_release_digest: str
    query_digest: str
    repair_candidate: ContractGapRepairCandidate | None
    receipt_digest: str


_CLARIFICATION_REASONS = frozenset({
    "ROOT_OBJECT_AMBIGUOUS",
    "OUTCOME_CHANGING_AMBIGUITY",
    "FILTER_SCOPE_AMBIGUOUS",
    "AMBIGUOUS_JOIN_PATH",
    "AMBIGUOUS_RELATIONSHIP_PATH",
    "AMBIGUOUS_RESULT_SHAPE",
})
_CONTRACT_GAP_REASONS = frozenset({
    "UNBOUND_PROPERTY",
    "QUERY_LOCAL_MAPPING_NOT_BOUND",
    "RELATIONSHIP_CONTRACT_NOT_FOUND",
    "RELATIONSHIP_PATH_NOT_DECLARED",
    "APPROVED_RESULT_SHAPE_NOT_FOUND",
    "RESULT_GRAIN_NOT_APPROVED",
    "DATA_QUALITY_RECEIPT_MISSING",
    "FILTER_CANONICAL_UNIT_NOT_DECLARED",
    "FILTER_UNIT_CONVERSION_NOT_DECLARED",
    "LATEST_BUSINESS_VERSION_CONTRACT_REQUIRED",
    "LATEST_SELECTION_CONTRACT_REQUIRED",
    "LATEST_RESULT_SHAPE_CONTRACT_REQUIRED",
    "LATEST_TIME_ORDERING_CONTRACT_REQUIRED",
})
_CAPABILITY_REASONS = frozenset({
    "UNSUPPORTED_OPERATOR",
    "AGGREGATION_OPERATOR_UNSUPPORTED",
    "COMPILER_CAPABILITY_UNSUPPORTED",
    "UNSUPPORTED_DIALECT",
    "LOCAL_MODEL_UNHEALTHY",
    "LOCAL_MODEL_EXECUTION_FAILED",
})
_DATA_REASONS = frozenset({
    "CATALOG_SNAPSHOT_NOT_CURRENT",
    "RELATIONSHIP_SCHEMA_SNAPSHOT_STALE",
    "SCHEMA_SNAPSHOT_STALE",
    "NO_AUTHORIZED_SEMANTIC_MATCH",
    "SOURCE_UNAVAILABLE",
})


def classify_query_answerability(
    *,
    executable: bool,
    reason_codes: tuple[str, ...],
    missing_dependency_ids: tuple[str, ...],
    active_release_digest: str,
    query_digest: str,
) -> QueryAnswerabilityReceipt:
    reasons = tuple(dict.fromkeys(reason_codes))
    missing = tuple(sorted(set(missing_dependency_ids)))
    if executable:
        if reasons or missing:
            raise ValueError("EXECUTABLE_ANSWERABILITY_CONFLICT")
        state: AnswerabilityState = "EXECUTABLE_NOW"
    elif set(reasons) & _CLARIFICATION_REASONS:
        state = "CLARIFICATION_REQUIRED"
    elif set(reasons) & _CONTRACT_GAP_REASONS:
        state = "CONTRACT_GAP_REPAIRABLE" if missing else "DATA_UNAVAILABLE"
    elif set(reasons) & _CAPABILITY_REASONS:
        state = "CAPABILITY_UNSUPPORTED"
    elif set(reasons) & _DATA_REASONS:
        state = "DATA_UNAVAILABLE"
    else:
        state = "POLICY_BLOCKED"
    if state == "CONTRACT_GAP_REPAIRABLE":
        if not missing:
            raise ValueError("REPAIRABLE_GAP_DEPENDENCY_REQUIRED")
        candidate_values = {
            "status": "candidate_only",
            "missing_dependency_ids": missing,
            "active_release_digest": active_release_digest,
            "query_digest": query_digest,
            "workbench_route": "/ontology/migrations",
            "approved": False,
            "released": False,
            "active": False,
        }
        repair_candidate = ContractGapRepairCandidate(
            **candidate_values,
            candidate_digest=_digest(candidate_values),
        )
    else:
        if missing:
            raise ValueError("NON_REPAIRABLE_DEPENDENCY_FORBIDDEN")
        repair_candidate = None
    values = {
        "schema_name": "boi-query-answerability/v1",
        "state": state,
        "executable": executable,
        "reason_codes": reasons,
        "missing_dependency_ids": missing,
        "active_release_digest": active_release_digest,
        "query_digest": query_digest,
        "repair_candidate": (
            repair_candidate.model_dump(mode="json") if repair_candidate else None
        ),
    }
    return QueryAnswerabilityReceipt(
        **values,
        receipt_digest=_digest(values),
    )


__all__ = [
    "AnswerabilityState",
    "ContractGapRepairCandidate",
    "QueryAnswerabilityReceipt",
    "classify_query_answerability",
]
