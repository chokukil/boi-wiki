from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from lfx.custom import Component
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema import Data
from lfx.utils.secrets import unwrap_secret_value


class BoIModelAgent(Component):
    display_name = "실제 모델 Agent 예제"
    description = (
        "OpenAI-compatible 모델을 실제 호출하고 Wiki·Ontology·Task provenance를 "
        "손실 없이 다음 단계로 전달합니다."
    )
    icon = "brain"
    name = "BoIModelAgent"

    inputs = [
        DataInput(name="knowledge", display_name="Wiki 근거", required=True),
        MultilineInput(
            name="instructions",
            display_name="Agent 지시",
            value=(
                "제공된 근거만 사용해 사용자의 질문에 답하세요. 근거가 부족하면 부족한 점을 "
                "명시하고, source reference 식별자는 답변에서 임의로 바꾸지 마세요."
            ),
            advanced=True,
        ),
    ]
    outputs = [Output(name="agent_result", display_name="실제 모델 Agent 결과", method="run_agent")]

    async def _variable(self, name: str) -> str:
        try:
            value = await self.get_variables(name, "value")
        except (TypeError, ValueError):
            value = ""
        return str(unwrap_secret_value(value) or "").strip()

    async def _configuration(self) -> tuple[str, str, str]:
        base_url = (
            await self._variable("BOI_LLM_BASE_URL")
            or os.getenv("BOI_LLM_BASE_URL", "")
        ).strip()
        model = (
            await self._variable("BOI_AGENT_EXAMPLE_MODEL")
            or os.getenv("BOI_AGENT_EXAMPLE_MODEL", "")
            or os.getenv("BOI_LLM_MODEL", "")
            or "google/gemma-4-26b-a4b-qat"
        ).strip()
        api_key = (
            await self._variable("BOI_LLM_API_KEY")
            or os.getenv("BOI_LLM_API_KEY", "")
        ).strip()
        if not base_url:
            raise ValueError(
                "BOI_LLM_BASE_URL이 없습니다. Langflow Credential/Global Variable로 모델 연결을 준비하세요."
            )
        return base_url.rstrip("/"), model, api_key

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    async def run_agent(self) -> Data:
        payload: dict[str, Any] = dict(getattr(self.knowledge, "data", {}) or {})
        base_url, model, api_key = await self._configuration()
        question = str(payload.get("question") or "").strip()
        context = str(payload.get("context") or "").strip()
        source_references = [
            item for item in payload.get("source_references") or [] if isinstance(item, dict)
        ]
        ontology_relationships = [
            item
            for item in payload.get("ontology_relationships") or []
            if isinstance(item, dict)
        ]
        prompt_context = {
            "question": question,
            "business_context": payload.get("business_context") or "",
            "context_profile": payload.get("context_profile") or "knowledge_lookup",
            "task_context": (
                payload.get("task_context")
                if isinstance(payload.get("task_context"), dict)
                else {}
            ),
            "grounding_status": payload.get("grounding_status") or "no_accessible_evidence",
            "wiki_context": context,
            "source_references": source_references,
            "ontology_relationships": ontology_relationships,
        }
        headers = {"Content-Type": "application/json"}
        if api_key and api_key not in {"not-needed", "none"}:
            headers["Authorization"] = f"Bearer {api_key}"
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": str(self.instructions or "").strip()},
                {
                    "role": "user",
                    "content": json.dumps(prompt_context, ensure_ascii=False, default=str),
                },
            ],
            "temperature": 0.1,
        }
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                self._chat_completions_url(base_url),
                headers=headers,
                json=request_body,
            )
        response.raise_for_status()
        decoded = response.json()
        choices = decoded.get("choices") if isinstance(decoded, dict) else []
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else {}
        answer = str((message or {}).get("content") or "").strip()
        if not answer:
            raise ValueError("OpenAI-compatible model response did not include message.content")
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        provenance = (
            dict(payload.get("provenance"))
            if isinstance(payload.get("provenance"), dict)
            else {}
        )
        model_trace = {
            "provider": "openai-compatible",
            "model": str(decoded.get("model") or model),
            "response_id": str(decoded.get("id") or ""),
            "latency_ms": elapsed_ms,
            "usage": decoded.get("usage") if isinstance(decoded.get("usage"), dict) else {},
            "real_inference": True,
        }
        provenance["model_agent"] = model_trace
        return Data(
            data={
                "answer": answer,
                "question": question,
                "business_context": payload.get("business_context") or "",
                "save_mode": payload.get("save_mode") or "preview",
                "title": payload.get("title") or "Agent Playground 개인 초안",
                "trace_id": payload.get("trace_id") or "",
                "context_profile": payload.get("context_profile") or "knowledge_lookup",
                "task_context": (
                    payload.get("task_context")
                    if isinstance(payload.get("task_context"), dict)
                    else {}
                ),
                "source_references": source_references,
                "ontology_relationships": ontology_relationships,
                "grounding_status": payload.get("grounding_status") or "no_accessible_evidence",
                "permission_excluded_count": int(payload.get("permission_excluded_count") or 0),
                "provenance": provenance,
                "agent_slot": self.__class__.__name__,
                "model_trace": model_trace,
            }
        )
