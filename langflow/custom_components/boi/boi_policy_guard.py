from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema import Data

REQUIRED = ["okf_version", "boi_profile_version", "type", "title", "description", "timestamp", "boi_id", "visibility", "classification", "owner", "acl_policy", "status"]
VALID_STATUSES = {"draft", "reviewed", "approved", "deprecated"}


class BoIPolicyGuard(Component):
    display_name = "BoI Policy & Validation Guard"
    description = "Validate minimal BoI metadata and promotion guardrails."
    icon = "badge-check"
    name = "boi_policy_guard"

    inputs = [
        DataInput(name="metadata", display_name="Metadata"),
        MultilineInput(name="body", display_name="BoI Body", required=False),
    ]
    outputs = [Output(name="validation", display_name="Validation Result", method="validate")]

    def validate(self) -> Data:
        meta: dict[str, Any] = self.metadata.data if hasattr(self.metadata, "data") else dict(self.metadata)
        errors = []
        warnings = []
        for f in REQUIRED:
            if not meta.get(f):
                errors.append(f"missing required metadata: {f}")
        if meta.get("visibility") not in {"private", "team", "public"}:
            errors.append("visibility must be private/team/public")
        if meta.get("status") not in VALID_STATUSES:
            errors.append("status must be draft/reviewed/approved/deprecated")
        if meta.get("visibility") in {"team", "public"}:
            if not meta.get("source_refs"):
                errors.append("team/public BoI requires source_refs")
            if not meta.get("review") and not meta.get("reviewer"):
                errors.append("team/public BoI requires reviewer")
            if meta.get("status") == "approved" and not (meta.get("review") or {}).get("reviewed_at"):
                errors.append("approved BoI requires review.reviewed_at")
        if "secret" in (self.body or "").lower():
            warnings.append("potential sensitive keyword detected")
        return Data(data={"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "metadata": meta, "body": self.body or ""})
