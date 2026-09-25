from __future__ import annotations

from typing import Any


# Runtime status values are protocol invariants shared by Inbox, Task and Agent
# projections. They classify observed domain outcomes; they never infer intent.
ACTION_TERMINAL_STATES = frozenset(
    {
        "approved",
        "cancelled",
        "completed",
        "failed",
        "rejected",
        "resolved",
        "success",
        "succeeded",
    }
)
ACTION_SUCCESS_STATES = frozenset(
    {
        "approved",
        "completed",
        "resolved",
        "success",
        "succeeded",
    }
)
ACTION_OPEN_STATES = frozenset(
    {
        "awaiting_confirmation",
        "blocked",
        "manual_required",
        "needs_confirmation",
        "open",
        "pending",
        "pending_confirmation",
        "queued",
        "running",
    }
)

# Connector-specific success labels describe how a side effect was delivered,
# not whether the observed result satisfied the common runtime contract.  They
# may be projected as ``succeeded`` only when the persisted result explicitly
# records ``ok=true``.  Keeping this mapping beside the shared domain states
# prevents each reader (History, Ontology, Agent, MCP) from inventing a
# different interpretation of the same ActionRun.
ACTION_VERIFIED_CONNECTOR_SUCCESS_STATES = frozenset(
    {
        "event_published",
        "invoked",
        "langflow_invoked",
        "materialized",
    }
)


def normalized_domain_status(value: Any) -> str:
    return str(value or "").strip().lower()


def action_has_terminal_outcome(value: Any) -> bool:
    return normalized_domain_status(value) in ACTION_TERMINAL_STATES


def action_has_successful_outcome(value: Any) -> bool:
    return normalized_domain_status(value) in ACTION_SUCCESS_STATES


def normalized_action_outcome_status(value: Any, result: Any = None) -> str:
    """Project a persisted Action result into the common status vocabulary.

    Raw connector labels remain unchanged unless the same append-only record
    carries an explicit successful result.  Pending, failed, or result-less
    observations are therefore never promoted into completed case evidence.
    """

    status = normalized_domain_status(value)
    result_payload = result if isinstance(result, dict) else {}
    if (
        status in ACTION_VERIFIED_CONNECTOR_SUCCESS_STATES
        and result_payload.get("ok") is True
    ):
        return "succeeded"
    return status
