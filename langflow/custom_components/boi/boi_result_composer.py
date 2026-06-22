from __future__ import annotations

import json
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MessageInput, Output
from lfx.schema.message import Message


class BoIResultComposer(Component):
    display_name = "BoI Result Composer"
    description = "Compose the final Langflow chat output from model analysis, policy validation, BoI write result, and action invocation result."
    icon = "square-check-big"
    name = "boi_result_composer"

    inputs = [
        MessageInput(name="analysis", display_name="Analysis Message", required=False),
        DataInput(name="simulation_agent", display_name="Simulation Agent Result", required=False),
        DataInput(name="validation", display_name="Policy Validation", required=False),
        DataInput(name="write_result", display_name="BoI Write Result", required=False),
        DataInput(name="action_result", display_name="Action Result", required=False),
    ]
    outputs = [Output(name="message", display_name="Result Message", method="compose")]

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if hasattr(value, "data"):
            return value.data or {}
        if isinstance(value, dict):
            return value
        return {"value": str(value)}

    def compose(self) -> Message:
        analysis_text = getattr(self.analysis, "text", "") if self.analysis else ""
        simulation_agent = self._as_dict(self.simulation_agent)
        validation = self._as_dict(self.validation)
        write_result = self._as_dict(self.write_result)
        action_result = self._as_dict(self.action_result)
        agent_markdown = ""
        if simulation_agent:
            simulation_result = simulation_agent.get("simulation_result")
            if isinstance(simulation_result, dict):
                agent_markdown = str(simulation_result.get("markdown") or "")
        summary = [
            "# Langflow BoI Execution Result",
            "",
            "## Universal Simulator Agent Result",
            agent_markdown or "No Universal Simulator Agent result returned.",
            "",
            "## Agent Trace",
            "```json",
            json.dumps(
                {
                    "agent": simulation_agent.get("agent"),
                    "agent_iterations": simulation_agent.get("agent_iterations"),
                    "tool_calls": simulation_agent.get("tool_calls"),
                    "coverage_report": simulation_agent.get("coverage_report"),
                    "evidence_packets": simulation_agent.get("evidence_packets"),
                    "limitations": simulation_agent.get("limitations"),
                },
                ensure_ascii=False,
                indent=2,
            )[:6000],
            "```",
            "",
            "## Analysis Draft",
            analysis_text or "No analysis text returned.",
            "",
            "## BoI Write Result",
            "```json",
            json.dumps(write_result, ensure_ascii=False, indent=2)[:4000],
            "```",
            "",
            "## Policy Validation",
            "```json",
            json.dumps(validation, ensure_ascii=False, indent=2)[:2000],
            "```",
            "",
            "## Action Result",
            "```json",
            json.dumps(action_result, ensure_ascii=False, indent=2)[:2000],
            "```",
        ]
        return Message(text="\n".join(summary))
