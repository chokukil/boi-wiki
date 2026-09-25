"""Fail-closed Data Lake artifact ACL rules shared by every projection."""

from __future__ import annotations

from typing import Any, Iterable


def artifact_acl_shape_valid(record: dict[str, Any]) -> bool:
    visibility = str(record.get("visibility") or "private")
    acl_policy = str(record.get("acl_policy") or "")
    if visibility == "public":
        return acl_policy == "acl:public"
    if visibility == "team":
        team_id = str(record.get("team_id") or "")
        return bool(team_id and acl_policy == f"acl:team:{team_id}")
    if visibility == "private":
        owner = str(record.get("owner_employee_id") or record.get("owner") or "")
        return bool(owner and acl_policy == f"acl:private:{owner}")
    return False


def artifact_visible_to_principal(
    record: dict[str, Any],
    employee_id: str,
    teams: Iterable[str],
    roles: Iterable[str],
) -> bool:
    """Return visibility without leaking malformed ACL records."""

    if not artifact_acl_shape_valid(record):
        return False
    role_set = set(roles)
    if "boi.admin" in role_set:
        return True
    visibility = str(record.get("visibility") or "private")
    if visibility == "public":
        return True
    if visibility == "team":
        return str(record.get("team_id") or "") in set(teams)
    owner = str(record.get("owner_employee_id") or record.get("owner") or "")
    return owner == employee_id
