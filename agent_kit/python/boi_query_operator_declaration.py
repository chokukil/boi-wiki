"""Author an explicit query capability proposal; never grant runtime authority.

The returned payload must go through the existing source/definition review and
exact profile projection. This helper is not a missing-contract fallback in the
resolver and does not publish, execute, or alter an existing review.
"""
import copy
from boi_api.app.governed_runtime.cardinality_query_shape import ResultShapeContract


def declare_query_operators(entry, *, operators, maximum_rows):
    """Preserve the candidate and attach only the author-selected operators."""
    if not isinstance(entry, dict) or not isinstance(entry.get("query_spec_id"), str) or not entry["query_spec_id"].strip():
        raise ValueError("QUERY_SPEC_ID_REQUIRED")
    operators = tuple(operators)
    if (not operators or len(set(operators)) != len(operators)
            or not set(operators) <= {"project", "filter", "order", "limit", "count",
                "distinct_count", "average", "latest", "nested", "linked"}):
        raise ValueError("EXPLICIT_QUERY_OPERATORS_REQUIRED")
    if type(maximum_rows) is not int or not 1 <= maximum_rows <= 1000:
        raise ValueError("EXPLICIT_QUERY_LIMIT_REQUIRED")
    if entry.get("result_shape_contract") is not None:
        shape = ResultShapeContract.model_validate(entry["result_shape_contract"])
        if maximum_rows > shape.limit_policy.maximum_rows:
            raise ValueError("QUERY_LIMIT_EXCEEDS_RESULT_SHAPE")
    declaration = {"supported_operators": list(operators), "max_limit": maximum_rows}
    if "logical_plan" in entry and entry["logical_plan"] != declaration:
        raise ValueError("EXISTING_QUERY_DECLARATION_CONFLICT")
    return {**copy.deepcopy(entry), "logical_plan": declaration}
