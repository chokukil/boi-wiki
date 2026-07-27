from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

from lfx.custom import Component
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema import Data
from lfx.utils.secrets import unwrap_secret_value


CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class BoIUniversalSimulationMCPAgent(Component):
    display_name = "3. 업무 시뮬레이션 Agent"
    description = (
        "Wiki·Ontology 업무 맥락만 사용해 실제 시스템을 호출하지 않는 시뮬레이션을 만들고 "
        "근거와 provenance를 다음 단계에 그대로 전달합니다."
    )
    icon = "route"
    name = "BoIUniversalSimulationMCPAgent"

    inputs = [
        DataInput(
            name="agent_context",
            display_name="Wiki·Ontology 업무 맥락",
            required=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="시뮬레이션 지시",
            value=(
                "제공된 업무 맥락과 근거 안에서만 처리 과정을 시뮬레이션하세요. "
                "실제 사내 시스템을 호출했다고 표현하지 말고, 근거가 부족하면 부족한 점을 "
                "명시하세요. source reference와 Ontology 식별자는 새로 만들거나 바꾸지 마세요."
            ),
            advanced=True,
        ),
    ]
    outputs = [
        Output(
            name="agent_result",
            display_name="근거가 보존된 시뮬레이션 결과",
            method="run_agent",
        )
    ]

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
        return (
            f"{base_url}/chat/completions"
            if base_url.endswith("/v1")
            else f"{base_url}/v1/chat/completions"
        )

    @staticmethod
    def _decode_model_result(value: str) -> dict[str, Any]:
        text = CODE_FENCE.sub("", str(value or "").strip()).strip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Gemma가 Universal Simulation JSON 계약을 반환하지 않았습니다."
            ) from exc
        if not isinstance(decoded, dict):
            raise ValueError("Gemma Universal Simulation 응답은 JSON object여야 합니다.")
        required = (
            "summary",
            "proposed_handling",
            "expected_result",
            "limitations",
            "next_steps",
        )
        missing = [name for name in required if not decoded.get(name)]
        if missing:
            raise ValueError(
                "Gemma Universal Simulation 응답에 필수 필드가 없습니다: "
                + ", ".join(missing)
            )
        return decoded

    @staticmethod
    def _as_lines(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if str(value or "").strip():
            return [str(value).strip()]
        return []

    @staticmethod
    def _coverage(
        payload: dict[str, Any],
        simulation: dict[str, Any],
        model_trace: dict[str, Any],
    ) -> dict[str, Any]:
        sources = [
            item
            for item in payload.get("source_references") or []
            if isinstance(item, dict)
        ]
        relations = [
            item
            for item in payload.get("ontology_relationships") or []
            if isinstance(item, dict)
        ]
        task_context = (
            payload.get("task_context")
            if isinstance(payload.get("task_context"), dict)
            else {}
        )
        profile = str(payload.get("context_profile") or "knowledge_lookup")
        checks = {
            "real_model_inference": bool(model_trace.get("real_inference")),
            "grounding_status": str(payload.get("grounding_status") or "")
            not in {"", "no_accessible_evidence"},
            "source_or_ontology_evidence": bool(sources or relations),
            "provenance": bool(payload.get("provenance")),
            "business_context": bool(
                str(payload.get("business_context") or "").strip()
                or task_context
            ),
            "simulation_contract": all(
                simulation.get(name)
                for name in ("summary", "proposed_handling", "expected_result")
            ),
            "limitations": bool(simulation.get("limitations")),
        }
        if profile in {"sop_task_execution", "task_execution"}:
            checks["resolved_task_context"] = bool(
                task_context.get("resolved_task_id")
                or task_context.get("task_ref")
            )
        required = list(checks)
        covered = [name for name, passed in checks.items() if passed]
        score = round(len(covered) / len(required), 2) if required else 0.0
        return {
            "profile": profile,
            "required": required,
            "covered": covered,
            "missing_context": [
                name for name, passed in checks.items() if not passed
            ],
            "coverage_score": score,
            "pass_threshold": 0.85,
            "passed": score >= 0.85,
        }

    @staticmethod
    def _markdown(
        simulation: dict[str, Any],
        coverage: dict[str, Any],
        source_references: list[dict[str, Any]],
        ontology_relationships: list[dict[str, Any]],
    ) -> str:
        lines = [
            "# SIMULATED · BoI Universal Simulation",
            "",
            "> 실제 사내 시스템을 호출하지 않은 근거 기반 미리보기입니다.",
            "",
            "## 처리 요약",
            str(simulation.get("summary") or ""),
            "",
            "## 시뮬레이션 처리",
        ]
        lines.extend(
            f"- {item}"
            for item in BoIUniversalSimulationMCPAgent._as_lines(
                simulation.get("proposed_handling")
            )
        )
        lines.extend(["", "## 예상 결과", str(simulation.get("expected_result") or "")])
        risks = BoIUniversalSimulationMCPAgent._as_lines(simulation.get("risks"))
        if risks:
            lines.extend(["", "## 위험·확인 사항", *[f"- {item}" for item in risks]])
        limitations = BoIUniversalSimulationMCPAgent._as_lines(
            simulation.get("limitations")
        )
        lines.extend(["", "## 부족한 근거와 제한", *[f"- {item}" for item in limitations]])
        next_steps = BoIUniversalSimulationMCPAgent._as_lines(
            simulation.get("next_steps")
        )
        lines.extend(["", "## 다음 단계", *[f"- {item}" for item in next_steps]])
        lines.extend(["", "## Wiki 근거"])
        lines.extend(
            f"- {item.get('title') or item.get('ref')} ({item.get('ref') or '-'})"
            for item in source_references[:8]
        )
        if not source_references:
            lines.append("- 현재 권한으로 확인된 문서 근거가 없습니다.")
        lines.extend(["", "## Ontology 관계"])
        lines.extend(
            (
                f"- {item.get('source_id')} — {item.get('relation')} → "
                f"{item.get('target_id')} (근거: {', '.join(item.get('source_refs') or [])})"
            )
            for item in ontology_relationships[:8]
        )
        if not ontology_relationships:
            lines.append("- 검증된 관계가 없어 문서 근거로 대체했습니다.")
        lines.extend(
            [
                "",
                "## Grounding coverage",
                (
                    f"- score={coverage.get('coverage_score')} / "
                    f"threshold={coverage.get('pass_threshold')}"
                ),
            ]
        )
        return "\n".join(lines).strip()

    async def run_agent(self) -> Data:
        payload = dict(getattr(self.agent_context, "data", {}) or {})
        base_url, model, api_key = await self._configuration()
        source_references = [
            item
            for item in payload.get("source_references") or []
            if isinstance(item, dict)
        ]
        ontology_relationships = [
            item
            for item in payload.get("ontology_relationships") or []
            if isinstance(item, dict)
        ]
        prompt_context = {
            "question": str(payload.get("question") or ""),
            "business_context": payload.get("business_context") or "",
            "context_profile": payload.get("context_profile")
            or "knowledge_lookup",
            "task_context": (
                payload.get("task_context")
                if isinstance(payload.get("task_context"), dict)
                else {}
            ),
            "grounding_status": payload.get("grounding_status")
            or "no_accessible_evidence",
            "wiki_context": payload.get("context") or "",
            "source_references": source_references,
            "ontology_relationships": ontology_relationships,
            "required_output": {
                "summary": "string",
                "proposed_handling": ["string"],
                "expected_result": "string",
                "risks": ["string"],
                "limitations": ["string"],
                "next_steps": ["string"],
            },
        }
        headers = {"Content-Type": "application/json"}
        if api_key and api_key not in {"not-needed", "none"}:
            headers["Authorization"] = f"Bearer {api_key}"
        request_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{str(self.instructions or '').strip()}\n\n"
                        "반드시 required_output과 같은 필드의 JSON object만 반환하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        prompt_context,
                        ensure_ascii=False,
                        default=str,
                    ),
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
        simulation = self._decode_model_result(str((message or {}).get("content") or ""))
        model_trace = {
            "provider": "openai-compatible",
            "model": str(decoded.get("model") or model),
            "response_id": str(decoded.get("id") or ""),
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "usage": (
                decoded.get("usage")
                if isinstance(decoded.get("usage"), dict)
                else {}
            ),
            "real_inference": True,
        }
        coverage = self._coverage(payload, simulation, model_trace)
        provenance = (
            dict(payload.get("provenance"))
            if isinstance(payload.get("provenance"), dict)
            else {}
        )
        provenance["model_agent"] = model_trace
        provenance["simulation_profile"] = "boi-universal-simulation-mcp-v1"
        answer = self._markdown(
            simulation,
            coverage,
            source_references,
            ontology_relationships,
        )
        return Data(
            data={
                "ok": True,
                "status": "simulated",
                "simulation": True,
                "simulation_label": "SIMULATED",
                "real_system_connected": False,
                "answer": answer,
                "simulation_result": simulation,
                "coverage_report": coverage,
                "limitations": self._as_lines(simulation.get("limitations")),
                "next_steps": self._as_lines(simulation.get("next_steps")),
                "question": payload.get("question") or "",
                "business_context": payload.get("business_context") or "",
                "save_mode": payload.get("save_mode") or "preview",
                "title": payload.get("title")
                or "Universal Simulation 개인 초안",
                "trace_id": payload.get("trace_id") or "",
                "context_profile": payload.get("context_profile")
                or "knowledge_lookup",
                "task_context": (
                    payload.get("task_context")
                    if isinstance(payload.get("task_context"), dict)
                    else {}
                ),
                "source_references": source_references,
                "ontology_relationships": ontology_relationships,
                "grounding_status": payload.get("grounding_status")
                or "no_accessible_evidence",
                "permission_excluded_count": int(
                    payload.get("permission_excluded_count") or 0
                ),
                "provenance": provenance,
                "agent_slot": self.__class__.__name__,
                "component_contract": "boi.agent-slot.v1",
                "executed_component_ids": [self.__class__.__name__],
                "model_trace": model_trace,
            }
        )
