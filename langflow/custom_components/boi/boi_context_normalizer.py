from __future__ import annotations

import json
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MessageInput, MultilineInput, Output
from lfx.schema import Data


class BoIContextNormalizer(Component):
    display_name = "BoI Context Normalizer"
    description = "Normalize Event Broker payload or manual text into a common BoI WorkContext."
    icon = "workflow"
    name = "boi_context_normalizer"

    inputs = [
        DataInput(name="event", display_name="Event Payload", required=False),
        MessageInput(name="message", display_name="Run Input Message", required=False),
        MultilineInput(name="manual_input", display_name="Manual Input", required=False),
    ]
    outputs = [Output(name="work_context", display_name="WorkContext", method="build_context")]

    def build_context(self) -> Data:
        raw: dict[str, Any] = {}
        if self.event:
            raw = self.event.data if hasattr(self.event, "data") else dict(self.event)
        message_text = getattr(self.message, "text", "") if self.message else ""
        manual = self.manual_input or message_text or ""
        event_type = raw.get("event_type") or "manual.input.v1"
        work_type = "reference"
        if event_type.startswith("meeting.closed"):
            work_type = "meeting"
        elif event_type.startswith("action.created"):
            work_type = "action"
        elif event_type.startswith("report.requested"):
            work_type = "report"
        elif event_type.startswith("equipment.alarm"):
            work_type = "sop-instance"
        elif event_type.startswith("trend.anomaly") or event_type.startswith("root_cause.analysis"):
            work_type = "analysis"
        elif event_type.startswith("maintenance.guide"):
            work_type = "runbook"
        elif event_type.startswith("corrective_action"):
            work_type = "action"
        actor = raw.get("actor") or {}
        owner = actor.get("employee_id") or actor.get("employee_id_hash") or "100001"
        payload = raw.get("payload") or {}
        title = payload.get("title") or raw.get("title") or manual[:80] or event_type
        return Data(data={
            "work_type": work_type,
            "requested_action": "create_private_boi",
            "event": raw,
            "event_type": event_type,
            "owner": owner,
            "title": title,
            "source_refs": raw.get("source_refs") or [],
            "manual_input": manual,
            "raw_json": json.dumps(raw, ensure_ascii=False),
        })
