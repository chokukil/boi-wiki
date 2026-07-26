"""Agent Hub cross-author adoption validation component.

This file is intentionally standalone so Agent Hub can deploy it through
Langflow's public custom-component API without a BoI or Langflow source patch.
"""

from __future__ import annotations

import json
from typing import Any

from langflow.custom import Component
from langflow.io import MultilineInput, Output
from langflow.schema import Data


class EvidencePrioritySelector(Component):
    display_name = "Evidence Priority Selector"
    description = (
        "Ranks document and ontology evidence while preserving provenance. "
        "It never reads credentials or changes Wiki data."
    )
    icon = "ListFilter"
    name = "EvidencePrioritySelector"

    inputs = [
        MultilineInput(
            name="evidence_json",
            display_name="Evidence JSON",
            info="JSON array of evidence objects.",
            required=True,
        ),
    ]
    outputs = [
        Output(
            name="ranked_evidence",
            display_name="Ranked Evidence",
            method="rank_evidence",
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

    def rank_evidence(self) -> Data:
        try:
            value = json.loads(self.evidence_json or "[]")
        except json.JSONDecodeError as exc:
            return Data(
                data={
                    "ranked_evidence": [],
                    "grounding_status": "invalid_evidence_json",
                    "error": str(exc),
                }
            )
        rows = [
            dict(item)
            for item in value
            if isinstance(item, dict)
        ] if isinstance(value, list) else []
        ranked = sorted(rows, key=self._score, reverse=True)
        return Data(
            data={
                "ranked_evidence": ranked,
                "grounding_status": (
                    "ranked_with_provenance"
                    if any(self._score(item)[0] for item in ranked)
                    else "ranked_without_provenance"
                ),
                "source_references": [
                    str(
                        item.get("source_ref")
                        or item.get("document_id")
                        or item.get("id")
                        or ""
                    )
                    for item in ranked
                    if (
                        item.get("source_ref")
                        or item.get("document_id")
                        or item.get("id")
                    )
                ],
            }
        )
