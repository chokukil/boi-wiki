from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CLASSIFICATION_POLICY_VERSION = "boi-classification-v1"
CLASSIFICATION_LEVELS = {"internal", "confidential", "restricted"}
HOTL_HIDDEN_STATUSES = {"hidden", "rolled_back", "blocked", "rejected", "archived"}


@dataclass
class AccessPolicyDecision:
    can_read: bool
    can_use_in_agent_context: bool
    can_cite: bool
    can_export: bool
    can_edit: bool
    can_promote: bool
    can_invoke_action: bool
    can_complete_handoff: bool
    visibility: str = ""
    classification: str = "internal"
    acl_policy: str = ""
    owner: str = ""
    team_id: str = ""
    redactions: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _relative_parts(path: str | Path, data_root: Path) -> tuple[str, ...]:
    try:
        return Path(path).relative_to(data_root).parts
    except Exception:
        return Path(path).parts


def _acl_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def doc_access_policy(
    doc: dict[str, Any],
    *,
    employee_id: str,
    teams: list[str],
    roles: list[str],
    data_root: Path,
    break_glass: bool = False,
) -> AccessPolicyDecision:
    metadata = doc.get("metadata") or {}
    path = Path(str(doc.get("path") or ""))
    parts = _relative_parts(path, data_root)
    visibility = str(metadata.get("visibility") or "")
    classification = str(metadata.get("classification") or "internal")
    if classification not in CLASSIFICATION_LEVELS:
        classification = "restricted"
    owner = str(metadata.get("owner") or "")
    team_id = str(metadata.get("team_id") or "")
    acl_policy = _acl_string(metadata.get("acl_policy"))
    reasons: list[str] = []
    redactions: list[str] = []

    hotl = metadata.get("hotl") if isinstance(metadata.get("hotl"), dict) else {}
    if str(hotl.get("status") or "") in HOTL_HIDDEN_STATUSES:
        reasons.append("document is hidden by HOTL status")
        return AccessPolicyDecision(False, False, False, False, False, False, False, False, visibility, classification, acl_policy, owner, team_id, redactions, reasons)

    is_admin = "boi.admin" in set(roles)
    can_read = False

    if visibility == "public":
        if acl_policy and acl_policy != "acl:public":
            reasons.append("public document acl_policy mismatch")
        can_read = not acl_policy or acl_policy == "acl:public"
    elif visibility == "team":
        path_team = parts[1] if len(parts) >= 2 and parts[0] == "team" else ""
        effective_team = team_id or path_team
        if path_team and team_id and path_team != team_id:
            reasons.append("team path and metadata.team_id mismatch")
        if acl_policy and effective_team and acl_policy != f"acl:team:{effective_team}":
            reasons.append("team acl_policy mismatch")
        can_read = bool(effective_team and effective_team in set(teams)) and not reasons
        team_id = effective_team
    elif visibility == "private":
        path_employee = parts[1] if len(parts) >= 2 and parts[0] == "private" else ""
        if not path_employee:
            reasons.append("private document is not stored under private/{employee_id}")
        if owner and owner != path_employee:
            reasons.append("private owner does not match path employee")
        if acl_policy and path_employee and acl_policy != f"acl:private:{path_employee}":
            reasons.append("private acl_policy mismatch")
        if path_employee == employee_id and not reasons:
            can_read = True
        elif break_glass and is_admin and path_employee and not reasons:
            can_read = True
            reasons.append("break-glass admin read")
        else:
            reasons.append("private document belongs to another employee")
    else:
        reasons.append("unknown visibility")

    if not can_read:
        return AccessPolicyDecision(False, False, False, False, False, False, False, False, visibility, classification, acl_policy, owner, team_id, redactions, reasons)

    can_use = True
    can_cite = True
    can_export = True
    can_action_payload = True
    if classification == "confidential":
        can_export = False
        can_action_payload = False
        redactions.append("external_export_payload")
    elif classification == "restricted":
        can_use = False
        can_cite = False
        can_export = False
        can_action_payload = False
        redactions.extend(["body", "memory", "external_export_payload"])

    role_set = set(roles)
    can_edit = "boi.editor" in role_set and can_read and classification != "restricted"
    can_promote = "boi.promoter" in role_set and can_read and classification not in {"restricted"}
    can_invoke_action = "boi.action_invoker" in role_set and can_read and can_action_payload
    can_complete_handoff = "boi.workflow_runner" in role_set and can_read

    return AccessPolicyDecision(
        can_read=can_read,
        can_use_in_agent_context=can_use,
        can_cite=can_cite,
        can_export=can_export,
        can_edit=can_edit,
        can_promote=can_promote,
        can_invoke_action=can_invoke_action,
        can_complete_handoff=can_complete_handoff,
        visibility=visibility,
        classification=classification,
        acl_policy=acl_policy,
        owner=owner,
        team_id=team_id,
        redactions=redactions,
        reasons=reasons,
    )
