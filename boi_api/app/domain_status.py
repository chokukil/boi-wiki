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


def normalized_domain_status(value: Any) -> str:
    return str(value or "").strip().lower()


def action_has_terminal_outcome(value: Any) -> bool:
    return normalized_domain_status(value) in ACTION_TERMINAL_STATES


def action_has_successful_outcome(value: Any) -> bool:
    return normalized_domain_status(value) in ACTION_SUCCESS_STATES
