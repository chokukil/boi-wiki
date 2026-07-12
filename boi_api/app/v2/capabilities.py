from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from .models import (
    CapabilityDefinition,
    CapabilityState,
    OperationClass,
    Principal,
    TaskMode,
)


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_.-]+")


def tokens(value: str) -> set[str]:
    return {item.lower() for item in TOKEN_RE.findall(value or "") if len(item) > 1}


class CapabilityRegistry:
    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self.version = "2.0"
        self._definitions: dict[str, CapabilityDefinition] = {}
        self.reload()

    def reload(self) -> None:
        payload = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8")) or {}
        definitions = [CapabilityDefinition.model_validate(item) for item in payload.get("capabilities") or []]
        ids = [item.capability_id for item in definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability_id in v2 catalog")
        self.version = str(payload.get("version") or "2.0")
        self._definitions = {item.capability_id: item for item in definitions}

    def get(self, capability_id: str) -> CapabilityDefinition:
        try:
            return self._definitions[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc

    def all(self, *, external_only: bool = False) -> list[CapabilityDefinition]:
        values = list(self._definitions.values())
        if external_only:
            values = [item for item in values if item.external]
        return values

    def select(self, question: str, *, allowed: Iterable[str] | None = None) -> CapabilityDefinition:
        allowed_ids = set(allowed or self._definitions)
        query_tokens = tokens(question)
        scored: list[tuple[float, CapabilityDefinition]] = []
        for definition in self._definitions.values():
            if definition.capability_id not in allowed_ids:
                continue
            example_tokens = tokens(" ".join([definition.title, definition.description, *definition.examples]))
            overlap = len(query_tokens & example_tokens)
            phrase_bonus = sum(3 for example in definition.examples if example.lower() in question.lower())
            score = overlap + phrase_bonus
            if definition.capability_id == "knowledge.search":
                score += 0.1
            scored.append((score, definition))
        scored.sort(key=lambda item: (-item[0], item[1].capability_id))
        return scored[0][1] if scored else self.get("knowledge.search")

    @staticmethod
    def effective_mode(task_mode: str | TaskMode | None) -> TaskMode:
        try:
            return task_mode if isinstance(task_mode, TaskMode) else TaskMode(str(task_mode or "copilot"))
        except ValueError:
            return TaskMode.copilot

    def state_for(
        self,
        definition: CapabilityDefinition,
        *,
        principal: Principal,
        readiness: dict[str, bool],
        task_mode: str | TaskMode | None,
        supplied_input: dict[str, Any] | None = None,
    ) -> tuple[CapabilityState, list[str], str]:
        if not principal.is_admin and not any(role in principal.roles for role in definition.permissions):
            return CapabilityState.unavailable, [], "권한이 없습니다."
        mode = self.effective_mode(task_mode)
        if mode not in definition.task_modes:
            return CapabilityState.unavailable, [], f"{mode.value} 모드에서는 사용할 수 없습니다."
        missing_dependencies = [name for name in definition.readiness if not readiness.get(name, False)]
        if missing_dependencies:
            return CapabilityState.unavailable, [], "필요한 기능이 준비되지 않았습니다: " + ", ".join(missing_dependencies)
        required = [str(item) for item in (definition.input_schema.get("required") or [])]
        values = supplied_input or {}
        missing = [name for name in required if not str(values.get(name) or "").strip()]
        if missing:
            return CapabilityState.needs_input, missing, "실행에 필요한 내용을 입력해주세요."
        return CapabilityState.ready, [], "바로 사용할 수 있습니다."

    def public_payload(self, *, principal: Principal, readiness: dict[str, bool]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self.all(external_only=True):
            state, required, reason = self.state_for(
                item,
                principal=principal,
                readiness=readiness,
                task_mode=TaskMode.copilot,
                supplied_input={},
            )
            result.append(
                {
                    "capability_id": item.capability_id,
                    "version": item.version,
                    "title": item.title,
                    "description": item.description,
                    "operation": item.operation.value,
                    "risk": item.risk.value,
                    "state": state.value,
                    "required_inputs": required,
                    "state_reason": reason,
                    "renderer": item.renderer,
                    "deep": item.deep,
                }
            )
        return result

    def runnable_ids(self, *, principal: Principal, readiness: dict[str, bool]) -> list[str]:
        result: list[str] = []
        for item in self.all():
            state, _, _ = self.state_for(
                item,
                principal=principal,
                readiness=readiness,
                task_mode=TaskMode.copilot,
                supplied_input={"query": "x", "goal": "x"},
            )
            if state == CapabilityState.ready:
                result.append(item.capability_id)
        return result

    def operation_allowed(self, definition: CapabilityDefinition, mode: TaskMode) -> bool:
        if definition.operation == OperationClass.read:
            return True
        return mode in {TaskMode.copilot, TaskMode.autopilot}

    @staticmethod
    def handler_supported(definition: CapabilityDefinition) -> bool:
        """Return whether the turn service has an executable handler class.

        Mutating work is represented as a guarded plan and confirmed through the
        domain APIs. A catalog entry must not fall through to a runtime 501.
        """
        return definition.operation in {OperationClass.read, OperationClass.draft}
