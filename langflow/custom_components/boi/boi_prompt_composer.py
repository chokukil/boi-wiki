from __future__ import annotations

import json
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema.message import Message


class BoIPromptComposer(Component):
    display_name = "BoI Prompt Composer"
    description = "Compose a model-ready prompt from BoI harness rules, wiki context, normalized event context, and prior action results."
    icon = "braces"
    name = "boi_prompt_composer"

    inputs = [
        DataInput(name="harness", display_name="Harness", required=False),
        DataInput(name="documents", display_name="BoI Wiki Documents", required=False),
        DataInput(name="work_context", display_name="WorkContext", required=False),
        DataInput(name="prior_results", display_name="Prior Action Results", required=False),
        MultilineInput(
            name="instruction",
            display_name="Instruction",
            value=(
                "Write a Korean BoI workflow execution draft. Use linked SOP/action context, "
                "avoid PoC architecture boilerplate, and clearly mark manual handoff and approval needs."
            ),
        ),
    ]
    outputs = [Output(name="prompt", display_name="Prompt Message", method="compose")]

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if hasattr(value, "data"):
            return value.data or {}
        if isinstance(value, dict):
            return value
        return {"value": str(value)}

    def _doc_summaries(self, documents: dict[str, Any]) -> list[dict[str, str]]:
        items = documents.get("items") or []
        summaries = []
        for item in items[:5]:
            metadata = item.get("metadata") or {}
            summaries.append(
                {
                    "title": str(metadata.get("title") or item.get("uri") or ""),
                    "boi_id": str(metadata.get("boi_id") or ""),
                    "uri": str(item.get("uri") or ""),
                    "body_excerpt": str(item.get("body") or "")[:900],
                }
            )
        return summaries

    def compose(self) -> Message:
        harness = self._as_dict(self.harness)
        documents = self._as_dict(self.documents)
        work_context = self._as_dict(self.work_context)
        prior_results = self._as_dict(self.prior_results)
        prompt = {
            "instruction": self.instruction,
            "harness": harness,
            "work_context": work_context,
            "boi_wiki_context": self._doc_summaries(documents),
            "prior_action_results": prior_results,
            "output_contract": {
                "sections": [
                    "Current Finding",
                    "Evidence Used",
                    "Recommended Next Check",
                    "Manual Handoff",
                    "Risk/Approval Notes",
                ],
                "forbidden": [
                    "YAML frontmatter",
                    "Markdown code-fence wrapper around the whole answer",
                    "PoC architecture explanation",
                    "workflow platform marketing",
                    "Private BoI to Team BoI promotion boilerplate",
                ],
            },
        }
        return Message(text=json.dumps(prompt, ensure_ascii=False, indent=2))
