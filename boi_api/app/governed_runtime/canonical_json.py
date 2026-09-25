"""Shared deterministic JSON and receipt-integrity contract.

`boi-canonical-json/v1` is UTF-8 JSON with sorted object keys, compact
separators, preserved non-ASCII text, and no non-finite numbers. Receipt digest
projections remove only the declared top-level digest field and explicitly
listed top-level exclusions.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


CONTRACT_ID = "boi-canonical-json/v1"


class CanonicalJsonError(ValueError):
    """Raised when a value or receipt violates the canonical contract."""


def _validate(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalJsonError(f"NON_FINITE_NUMBER:{path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalJsonError(f"NON_STRING_OBJECT_KEY:{path}")
            _validate(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate(child, path=f"{path}[{index}]")
        return
    raise CanonicalJsonError(f"UNSUPPORTED_JSON_TYPE:{path}:{type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON value according to `boi-canonical-json/v1`."""

    _validate(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def receipt_digest_projection(
    receipt: Mapping[str, Any],
    *,
    digest_field: str,
    excluded_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Return the exact top-level projection used as receipt digest input."""

    if not digest_field or "." in digest_field:
        raise CanonicalJsonError("INVALID_DIGEST_FIELD")
    excluded = set(excluded_fields)
    if any(not field or "." in field for field in excluded):
        raise CanonicalJsonError("INVALID_EXCLUDED_FIELD")
    return {
        key: value
        for key, value in receipt.items()
        if key != digest_field and key not in excluded
    }


def validate_qualification_time(qualified_at: str, *, observed_at: str) -> None:
    """Reject naive timestamps and qualification timestamps after observation."""

    try:
        qualified = datetime.fromisoformat(qualified_at)
        observed = datetime.fromisoformat(observed_at)
    except ValueError as error:
        raise CanonicalJsonError("QUALIFICATION_TIME_INVALID") from error
    if qualified.tzinfo is None or observed.tzinfo is None:
        raise CanonicalJsonError("QUALIFICATION_TIME_TIMEZONE_REQUIRED")
    if qualified > observed:
        raise CanonicalJsonError("QUALIFIED_AT_IN_FUTURE")


__all__ = [
    "CONTRACT_ID",
    "CanonicalJsonError",
    "canonical_digest",
    "canonical_json_bytes",
    "receipt_digest_projection",
    "validate_qualification_time",
]
