from __future__ import annotations

from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema import Data


class BoIAgentSlot(Component):
    display_name = "Agent 바꿔 끼우기"
    description = "기준 Flow의 안정적인 입출력 계약입니다. 이 노드만 원하는 Agent로 교체할 수 있습니다."
    icon = "bot"
    name = "BoIAgentSlot"

    inputs = [
        DataInput(name="knowledge", display_name="Wiki 근거", required=True),
        MultilineInput(
            name="instructions",
            display_name="기본 지시",
            value="근거에 없는 사실을 만들지 말고 source references를 유지해 판단 근거를 정리합니다.",
            advanced=True,
        ),
    ]
    outputs = [Output(name="agent_result", display_name="Agent 결과", method="run_agent")]

    def run_agent(self) -> Data:
        payload: dict[str, Any] = dict(getattr(self.knowledge, "data", {}) or {})
        source_references = [
            item for item in payload.get("source_references") or [] if isinstance(item, dict)
        ]
        context = str(payload.get("context") or "").strip()
        answer = (
            f"{str(self.instructions or '').strip()}\n\n{context}".strip()
            if context
            else "현재 권한으로 확인 가능한 BoI Wiki 근거가 없습니다."
        )
        return Data(
            data={
                "answer": answer,
                "question": payload.get("question") or "",
                "business_context": payload.get("business_context") or "",
                "save_mode": payload.get("save_mode") or "preview",
                "title": payload.get("title") or "Agent Playground 개인 초안",
                "trace_id": payload.get("trace_id") or "",
                "context_profile": payload.get("context_profile") or "knowledge_lookup",
                "task_context": payload.get("task_context") if isinstance(payload.get("task_context"), dict) else {},
                "source_references": source_references,
                "ontology_relationships": [
                    item
                    for item in payload.get("ontology_relationships") or []
                    if isinstance(item, dict)
                ],
                "grounding_status": payload.get("grounding_status") or "no_accessible_evidence",
                "permission_excluded_count": int(payload.get("permission_excluded_count") or 0),
                "provenance": payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {},
                "agent_slot": self.__class__.__name__,
            }
        )
