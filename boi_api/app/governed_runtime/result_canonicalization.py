"""Canonicalize backend scalar results before hashing or delivery."""

from __future__ import annotations

import math
from typing import Any, Mapping


def _normalize_result_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NON_FINITE_RESULT_VALUE")
        normalized = float(format(value, ".15g"))
        return 0.0 if normalized == 0.0 else normalized
    if isinstance(value, Mapping):
        return {key: _normalize_result_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_normalize_result_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_result_value(item) for item in value]
    return value


def normalize_result_rows(
    rows: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Return rows with finite floats fixed to 15 significant digits."""

    return tuple(
        {key: _normalize_result_value(value) for key, value in row.items()}
        for row in rows
    )
