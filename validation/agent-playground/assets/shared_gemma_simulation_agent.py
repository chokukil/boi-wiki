"""Agent Hub validation asset for the BoI Universal Simulation MCP agent slot.

This standalone component is uploaded through the unmodified Agent Hub. It
uses only Langflow's public custom-component contract and an OpenAI-compatible
LM Studio endpoint supplied by runtime environment variables.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from langflow.custom import Component
from langflow.io import DataInput, Output, StrInput
from langflow.schema import Data


class SharedGemmaSimulationAgent(Component):
    component_contract = {
        "schema_version": "boi.agent-slot.v1",
        "inputs": ["agent_context"],
        "outputs": ["agent_result"],
    }
    display_name = "Shared Gemma Simulation Agent"
    description = (
        "Uses LM Studio Gemma to simulate a grounded business response while "
        "preserving Wiki sources, Ontology provenance, and Task Context."
    )
    icon = "Bot"
    name = "SharedGemmaSimulationAgent"

    inputs = [
        DataInput(
            name="agent_context",
            display_name="Agent Context",
            info="ACL-checked Wiki, Ontology, and optional SOP Task Context.",
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
    def _payload(value: Any) -> dict[str, Any]:
        if isinstance(value, Data):
            return dict(value.data or {})
        if isinstance(value, dict):
            return dict(value)
        return {}

    def build_agent_result(self) -> Data:
        payload = self._payload(self.agent_context)
        base_url = os.getenv("BOI_LLM_BASE_URL", "").rstrip("/")
        model = os.getenv("BOI_AGENT_EXAMPLE_MODEL", "")
        api_key = os.getenv("BOI_LLM_API_KEY", "not-needed")
        if not base_url or not model:
            raise ValueError("LM Studio runtime variables are not configured")

        prompt_context = {
            "question": payload.get("question") or "",
            "business_context": payload.get("business_context") or "",
            "task_context": payload.get("task_context") or {},
            "source_references": payload.get("source_references") or [],
            "ontology_relationships": payload.get("ontology_relationships") or [],
            "grounding_status": payload.get("grounding_status") or "",
            "missing_evidence": (
                (payload.get("task_context") or {}).get("missing_evidence") or []
            ),
        }
        started = time.perf_counter()
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a business simulation agent. Never claim "
                            "that a real system was called. Answer in Korean, "
                            "use only the supplied evidence, state limitations, "
                            "and provide next checks."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            prompt_context,
                            ensure_ascii=False,
                            default=str,
                        )[:60000],
                    },
                ],
            },
            timeout=180,
        )
        response.raise_for_status()
        body = response.json()
        answer = str(
            ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        ).strip()
        if not answer:
            raise ValueError("LM Studio returned an empty simulation")

        asset_id = str(self.component_asset_id or "").strip()
        executed = [
            str(value)
            for value in payload.get("executed_component_ids") or []
            if str(value)
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
            "model": model,
        }
        model_trace = {
            "provider": "openai-compatible",
            "model": str(body.get("model") or model),
            "response_id": str(body.get("id") or ""),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "usage": body.get("usage") or {},
            "real_inference": True,
        }
        return Data(
            data={
                **payload,
                "simulation_label": "SIMULATED",
                "answer": (
                    "# SIMULATED · 공유 Gemma Agent\n\n"
                    "> 실제 사내 시스템은 호출하지 않았습니다.\n\n"
                    f"{answer}"
                ),
                "model_trace": model_trace,
                "provenance": provenance,
                "component_asset_id": asset_id,
                "executed_component_ids": list(dict.fromkeys(executed)),
            }
        )
