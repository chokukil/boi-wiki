"""Deterministic temporal SQL comparison under an explicit profile policy."""
from .latest_time_order import time_key
from datetime import datetime, timezone
import re

ALLOWED = frozenset({"ISO8601_UTC", "SOURCE_LOCAL_ISO8601", "ISO_DATE"})


def temporal_expression(quoted_identifier: str, policy: str) -> str:
    # Identifier quoting is owned by the dialect renderer; policy is an enum.
    if policy not in ALLOWED:
        raise ValueError("LATEST_TIME_ORDER_POLICY_INVALID")
    return f"boi_latest_time_key({quoted_identifier}, '{policy}')"


def temporal_parameter(value, policy: str):
    if policy not in ALLOWED:
        raise ValueError("LATEST_TIME_ORDER_POLICY_INVALID")
    # Explicit offset parameters denote an instant, unlike a source-local clock.
    # The source-value decoder remains strict about its declared storage format.
    normalized = time_key(value, policy)
    if normalized is None and policy == "ISO8601_UTC" and isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?[+-]\d{2}:\d{2}", value):
            try:
                parsed = datetime.fromisoformat(value)
                normalized = parsed.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds")
            except (ValueError, OverflowError):
                normalized = None
    if normalized is None:
        raise ValueError("LATEST_FILTER_TIME_FORMAT_POLICY_MISMATCH")
    return normalized


def policy_for_mapping(mapping, result_sets):
    found = set()
    encoding = getattr(mapping, "temporal_encoding", None)
    if encoding is not None:
        found.add(encoding.representation)
    for result_set in result_sets:
        if result_set.latest is None or result_set.latest.selection_policy is None:
            continue
        aliases = {p.output_name:p.column for p in result_set.projections}
        if (mapping.source_id, mapping.table, mapping.column) == (
            result_set.source_id, result_set.table, aliases[result_set.latest.ordering[0]]
        ):
            found.add(result_set.latest.selection_policy.time_ordering)
    if len(found) > 1:
        raise ValueError("LATEST_TIME_MAPPING_POLICY_CONFLICT")
    return next(iter(found)) if found else None


def selection_policies_for_mapping(mapping, result_sets):
    policies = []
    for result_set in result_sets:
        if result_set.latest is None or result_set.latest.selection_policy is None:
            continue
        aliases = {p.output_name:p.column for p in result_set.projections}
        if (mapping.source_id,mapping.table,mapping.column) == (
            result_set.source_id,result_set.table,aliases[result_set.latest.ordering[0]]):
            policy = result_set.latest.selection_policy
            if policy not in policies:
                policies.append(policy)
    return tuple(policies)
