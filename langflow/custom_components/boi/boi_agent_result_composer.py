from __future__ import annotations

import json

from lfx.custom import Component
from lfx.io import MessageInput, Output, StrInput
from lfx.schema.message import Message


class BoIAgentResultComposer(Component):
    display_name = "BoI Agent Result Composer"
    description = "Normalize native Agent output into the BoI Agent API response contract."
    icon = "bot-message-square"
    name = "boi_agent_result_composer"

    inputs = [
        MessageInput(name="agent_message", display_name="Agent Message", required=True),
        StrInput(name="result_title", display_name="Result Title", value="BoI Agent Response", required=False),
    ]
    outputs = [Output(name="message", display_name="Result Message", method="compose")]

    def compose(self) -> Message:
        text = getattr(self.agent_message, "text", "") if self.agent_message else ""
        stripped = str(text or "").strip()
        if stripped.startswith("```json"):
            stripped = stripped.removeprefix("```json").strip()
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and parsed.get("answer_markdown"):
                    return Message(text=json.dumps(parsed, ensure_ascii=False))
            except json.JSONDecodeError:
                pass
        payload = {
            "answer_markdown": stripped or "BoI Agent returned an empty answer.",
            "links": [],
            "citations": [],
            "suggested_questions": [],
            "context_summary": {"source": "langflow_boi_agent"},
        }
        return Message(text=json.dumps(payload, ensure_ascii=False))
