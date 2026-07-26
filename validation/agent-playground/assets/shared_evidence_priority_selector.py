"""Agent Hub cross-author adoption validation component.

This file is intentionally standalone so Agent Hub can deploy it through
Langflow's public custom-component API without a BoI or Langflow source patch.
"""

from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.io import DataInput, Output, StrInput
from langflow.schema import Data


class EvidencePrioritySelector(Component):
    component_contract = {
        "schema_version": "boi.agent-slot.v1",
        "inputs": ["agent_context"],
        "outputs": ["agent_result"],
    }
    display_name = "Evidence Priority Selector"
    description = (
        "Ranks document and ontology evidence while preserving provenance. "
        "It never reads credentials or changes Wiki data."
    )
    icon = "ListFilter"
    name = "EvidencePrioritySelector"

    inputs = [
        DataInput(
            name="agent_context",
            display_name="Agent Context",
            info="BoI Wiki source references, Ontology provenance, and Task Context.",
            required=True,
        ),
        StrInput(
            name="component_asset_id",
            display_name="Component Asset ID",
            value="",
            advanced=True,
        ),
    ]
    outputs = [
        Output(
            name="agent_result",
            display_name="Agent Result",
            method="build_agent_result",
        ),
    ]

    @staticmethod
    def _score(item: dict[str, Any]) -> tuple[int, float, str]:
        provenance = item.get("provenance")
        has_provenance = int(
            bool(provenance)
            or bool(item.get("source_ref"))
            or bool(item.get("source_refs"))
        )
        confidence = item.get("confidence")
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0
        identity = str(
            item.get("source_ref")
            or item.get("document_id")
            or item.get("id")
            or ""
        )
        return has_provenance, confidence_value, identity

    def build_agent_result(self) -> Data:
        source = self.agent_context
        payload = (
            dict(source.data)
            if isinstance(source, Data)
            else dict(source)
            if isinstance(source, dict)
            else {}
        )
        rows = [
            dict(item)
            for item in payload.get("source_references") or []
            if isinstance(item, dict)
        ]
        ranked = sorted(rows, key=self._score, reverse=True)
        asset_id = str(self.component_asset_id or "").strip()
        executed = [
            str(item)
            for item in payload.get("executed_component_ids") or []
            if str(item)
        ]
        if asset_id:
            executed.append(asset_id)
        provenance = (
            dict(payload.get("provenance"))
            if isinstance(payload.get("provenance"), dict)
            else {}
        )
        provenance["agent_component"] = {
            "contract": "boi.agent-slot.v1",
            "component_asset_id": asset_id,
            "source_reference_count": len(ranked),
        }
        return Data(
            data={
                **payload,
                "answer": str(
                    payload.get("answer")
                    or payload.get("context")
                    or "근거 우선순위를 반영했습니다."
                ),
                "source_references": [
                    item for item in ranked
                ],
                "provenance": provenance,
                "component_asset_id": asset_id,
                "executed_component_ids": list(dict.fromkeys(executed)),
            }
        )
