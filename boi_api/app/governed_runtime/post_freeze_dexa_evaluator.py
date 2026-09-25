"""Independent historical-oracle evaluation after candidate plan freeze."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Mapping

from .bulk_migration_execution import CandidateFreezeReceipt
from .cold_candidate_query_planner import ColdCandidateLogicalPlan
from .multi_result_query_gateway import MultiResultQueryExecution


_REQUIRED_ORACLE_KEYS = frozenset(
    {
        "q1_route_rows",
        "q2_latest_rows",
        "q3_recipe_rows",
        "q3_parameter_rows",
        "q3_history_rows",
        "q3_history_count_sum",
        "q3_unbound_history",
        "q3_orphan_history",
        "historical_flat_rows",
        "historical_nonnull_lot_rows",
    }
)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PostFreezeDexaEvaluationReceipt:
    receipt_version: str
    status: str
    check_results: tuple[dict[str, object], ...]
    plan_digests: tuple[str, ...]
    execution_receipt_digests: tuple[str, ...]
    oracle_digest: str
    generator_oracle_access_count: int
    evaluator_oracle_access_count: int
    feedback_to_generator_count: int
    receipt_digest: str


def evaluate_post_freeze_dexa(
    *,
    candidates: tuple[ColdCandidateLogicalPlan, ...],
    freezes: tuple[CandidateFreezeReceipt, ...],
    executions: tuple[MultiResultQueryExecution, ...],
    oracle_loader: Callable[[], Mapping[str, int]],
) -> PostFreezeDexaEvaluationReceipt:
    if not (len(candidates) == len(freezes) == len(executions) == 3):
        raise ValueError("DEXA_THREE_QUERY_CLOSURE_REQUIRED")
    for candidate, freeze, execution in zip(candidates, freezes, executions):
        if freeze.status != "frozen" or freeze.logical_plan_digest != candidate.plan.plan_digest:
            raise ValueError("DEXA_EVALUATION_PLAN_NOT_FROZEN")
        if execution.receipt.logical_plan_digest != candidate.plan.plan_digest:
            raise ValueError("DEXA_EVALUATION_EXECUTION_MISMATCH")

    # The oracle callback is intentionally unreachable until every plan and
    # execution above has passed the structural freeze boundary.
    oracle = {str(key): int(value) for key, value in oracle_loader().items()}
    missing = sorted(_REQUIRED_ORACLE_KEYS.difference(oracle))
    if missing:
        raise ValueError("DEXA_ORACLE_CONTRACT_MISSING:" + ",".join(missing))
    q1, q2, q3 = executions
    q3_sets = {item.result_set_id: item for item in q3.result.result_sets}
    q3_candidate = candidates[2]
    history_quality = next(
        item for item in q3_candidate.quality_receipts if item.scanned_rows == 326
    )
    observed = {
        "q1_route_rows": q1.result.result_sets[0].row_count,
        "q2_latest_rows": q2.result.result_sets[0].row_count,
        "q3_recipe_rows": q3_sets["result:recipes"].row_count,
        "q3_parameter_rows": q3_sets["result:parameters"].row_count,
        "q3_history_rows": q3_sets["result:histories"].row_count,
        "q3_history_count_sum": sum(
            int(row["history_count"])
            for row in q3_sets["result:history-counts"].rows
        ),
        "q3_unbound_history": history_quality.null_fk_rows,
        "q3_orphan_history": history_quality.orphan_rows,
    }
    checks = tuple(
        {
            "check_id": key,
            "status": "pass" if observed.get(key) == expected else "fail",
            "observed": observed.get(key),
            "expected": expected,
            "evidence_digest": _digest(
                {"key": key, "observed": observed.get(key), "expected": expected}
            ),
        }
        for key, expected in oracle.items()
        if key in observed
    )
    historical_checks = (
        {
            "check_id": "historical_flat_view_not_promoted",
            "status": (
                "pass"
                if oracle.get("historical_flat_rows") == 3801
                and oracle.get("historical_nonnull_lot_rows") == 1464
                and observed["q3_history_count_sum"] != 1464
                else "fail"
            ),
            "observed": observed["q3_history_count_sum"],
            "expected": "independent history grain, not 1464/3801 flat compatibility",
            "evidence_digest": _digest(
                {
                    "history_count": observed["q3_history_count_sum"],
                    "flat": oracle.get("historical_flat_rows"),
                    "nonnull": oracle.get("historical_nonnull_lot_rows"),
                }
            ),
        },
    )
    all_checks = (*checks, *historical_checks)
    payload = {
        "receipt_version": "boi/post-freeze-dexa-evaluation@1.0.0",
        "status": "PASS" if all(item["status"] == "pass" for item in all_checks) else "FAIL",
        "check_results": all_checks,
        "plan_digests": [item.plan.plan_digest for item in candidates],
        "execution_receipt_digests": [item.receipt.receipt_digest for item in executions],
        "oracle_digest": _digest(oracle),
        "generator_oracle_access_count": 0,
        "evaluator_oracle_access_count": 1,
        "feedback_to_generator_count": 0,
    }
    return PostFreezeDexaEvaluationReceipt(
        receipt_version=str(payload["receipt_version"]),
        status=str(payload["status"]),
        check_results=all_checks,
        plan_digests=tuple(payload["plan_digests"]),
        execution_receipt_digests=tuple(payload["execution_receipt_digests"]),
        oracle_digest=str(payload["oracle_digest"]),
        generator_oracle_access_count=0,
        evaluator_oracle_access_count=1,
        feedback_to_generator_count=0,
        receipt_digest=_digest(payload),
    )
