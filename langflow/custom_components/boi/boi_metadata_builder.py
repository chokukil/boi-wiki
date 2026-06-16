from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, MultilineInput, Output, StrInput
from lfx.schema import Data

KST = timezone(timedelta(hours=9))


class BoIMetadataBuilder(Component):
    display_name = "BoI Metadata Builder"
    description = "Build OKF/SK hynix BoI YAML-frontmatter metadata."
    icon = "file-cog"
    name = "boi_metadata_builder"

    inputs = [
        DataInput(name="work_context", display_name="WorkContext", required=False),
        StrInput(name="title", display_name="Title", required=False),
        StrInput(name="description", display_name="Description", value="BoI generated from Langflow", required=False),
        DropdownInput(name="boi_type", display_name="BoI Type", options=["boi/meeting", "boi/action", "boi/report", "boi/reference", "boi/sop-instance", "boi/analysis", "boi/runbook"], value="boi/reference"),
        DropdownInput(name="visibility", display_name="Visibility", options=["private", "team", "public"], value="private"),
        StrInput(name="owner", display_name="Owner Employee ID", value="100001"),
        StrInput(name="team_id", display_name="Team ID", value="aix-tf", required=False),
        StrInput(name="classification", display_name="Classification", value="internal"),
        MultilineInput(name="tags_json", display_name="Tags JSON", value='["AIX","BoIWiki","Langflow"]', required=False),
    ]
    outputs = [Output(name="metadata", display_name="Metadata", method="build_metadata")]

    def build_metadata(self) -> Data:
        ctx: dict[str, Any] = {}
        if self.work_context:
            ctx = self.work_context.data if hasattr(self.work_context, "data") else dict(self.work_context)
        event = ctx.get("event") or {}
        owner = ctx.get("owner") or self.owner
        title = self.title or ctx.get("title") or "Untitled BoI"
        boi_type = self.boi_type
        if ctx.get("work_type") in {"meeting", "action", "report", "analysis", "runbook"} and boi_type == "boi/reference":
            boi_type = f"boi/{ctx['work_type']}"
        elif ctx.get("work_type") == "sop-instance" and boi_type == "boi/reference":
            boi_type = "boi/sop-instance"
        try:
            tags = json.loads(self.tags_json) if self.tags_json else []
        except Exception:
            tags = ["AIX", "BoIWiki", "Langflow"]
        scope = self.visibility if self.visibility != "team" else f"team:{self.team_id}"
        boi_id = f"boi:{scope}:{owner}:{datetime.now(KST).strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:6]}"
        meta: dict[str, Any] = {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": boi_type,
            "title": title,
            "description": self.description,
            "tags": tags,
            "timestamp": datetime.now(KST).replace(microsecond=0).isoformat(),
            "boi_id": boi_id,
            "visibility": self.visibility,
            "classification": self.classification,
            "owner": owner,
            "author": {"type": "agent", "agent_id": "langflow-boi-metadata-builder-v0.1"},
            "acl_policy": f"acl:{self.visibility}:{owner if self.visibility == 'private' else (self.team_id if self.visibility == 'team' else 'public')}",
            "status": "draft",
        }
        if self.visibility == "team":
            meta["team_id"] = self.team_id
        if event:
            meta["source_event"] = {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "occurred_at": event.get("occurred_at"),
            }
            meta["source_refs"] = event.get("source_refs") or ctx.get("source_refs") or []
            if event.get("event_type"):
                meta["event_type"] = event.get("event_type")
        return Data(data=meta)
