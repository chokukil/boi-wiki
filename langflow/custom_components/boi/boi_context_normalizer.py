from __future__ import annotations

import json
import re
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

    def _embedded_simulation_agent(self, text: str) -> dict[str, Any]:
        marker = "BoI Simulation Agent retrieved context."
        if marker not in text:
            return {}
        start = text.find("{")
        end_marker = "\n\nOriginal Langflow request follows."
        end = text.find(end_marker)
        if start < 0 or end <= start:
            return {}
        try:
            return json.loads(text[start:end].strip())
        except Exception:
            return {}

    def build_context(self) -> Data:
        raw: dict[str, Any] = {}
        if self.event:
            raw = self.event.data if hasattr(self.event, "data") else dict(self.event)
        message_text = getattr(self.message, "text", "") if self.message else ""
        manual = self.manual_input or message_text or ""
        json_payload: dict[str, Any] = {}
        if manual.strip().startswith("{"):
            try:
                parsed = json.loads(manual)
                if isinstance(parsed, dict):
                    json_payload = parsed
            except Exception:
                json_payload = {}
        if not raw and isinstance(json_payload.get("event"), dict):
            raw = dict(json_payload["event"])
            if "payload" not in raw and isinstance(json_payload.get("payload"), dict):
                raw["payload"] = json_payload["payload"]
        elif not raw and json_payload.get("event_type"):
            raw = {
                "event_type": json_payload.get("event_type"),
                "trace_id": json_payload.get("trace_id") or "",
                "payload": json_payload.get("payload") if isinstance(json_payload.get("payload"), dict) else {},
            }
        simulation_agent = self._embedded_simulation_agent(manual)
        action_match = re.search(r"Action key:\s*([A-Za-z0-9_.-]+)", manual)
        trace_match = re.search(r"trace=([A-Za-z0-9_.-]+)", manual)
        event_match = re.search(r"Event:\s*([A-Za-z0-9_.-]+)", manual)
        sop_match = re.search(r"SOP:\s*([^\s\n]+)", manual)
        stage_match = re.search(r"Stage:\s*([^\n]+)", manual)
        if not raw and event_match:
            raw = {
                "event_type": event_match.group(1),
                "trace_id": trace_match.group(1) if trace_match else "",
                "payload": {},
            }
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
        owner = (
            json_payload.get("employee_id")
            or actor.get("employee_id")
            or actor.get("employee_id_hash")
            or "100001"
        )
        payload = raw.get("payload") or (json_payload.get("payload") if isinstance(json_payload.get("payload"), dict) else {}) or {}
        title = payload.get("title") or raw.get("title") or manual[:80] or event_type
        simulation_workflow = simulation_agent.get("workflow") or ((simulation_agent.get("context_pack") or {}).get("workflow") or {})
        return Data(data={
            "work_type": work_type,
            "requested_action": "create_private_boi",
            "action_key": json_payload.get("action_key") or (action_match.group(1) if action_match else ""),
            "event": raw,
            "event_type": event_type,
            "trace_id": raw.get("trace_id") or (trace_match.group(1) if trace_match else ""),
            "workflow_key": json_payload.get("workflow_key") or (simulation_workflow.get("workflow_key") if simulation_agent else ""),
            "sop_ref": json_payload.get("sop_ref") or (sop_match.group(1) if sop_match else "") or (simulation_workflow.get("sop_ref") if simulation_agent else ""),
            "sop_stage_id": json_payload.get("sop_stage_id") or (stage_match.group(1).strip() if stage_match else "") or (simulation_workflow.get("sop_stage_id") if simulation_agent else ""),
            "simulation_agent": simulation_agent,
            "prior_results": (simulation_agent.get("prior_results") or ((simulation_agent.get("context_pack") or {}).get("prior_results") or [])) if simulation_agent else [],
            "payload": payload,
            "employee_id": str(owner),
            "owner": owner,
            "title": title,
            "source_refs": raw.get("source_refs") or [],
            "manual_input": manual,
            "raw_json": json.dumps(raw, ensure_ascii=False),
        })
