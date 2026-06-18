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
        validation = self._as_dict(self.validation)
        write_result = self._as_dict(self.write_result)
        action_result = self._as_dict(self.action_result)
        summary = [
            "# Langflow BoI Execution Result",
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
