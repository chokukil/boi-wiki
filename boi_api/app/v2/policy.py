from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from .models import CapabilityDefinition, OperationClass, Principal, RiskLevel, TaskMode
from .repository import KnowledgeRepository
from .store import AgentV2Store


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    mode: TaskMode
    confirmation_required: bool
    reason: str


class TaskPolicy:
    def __init__(self, repository: KnowledgeRepository, store: AgentV2Store | None = None):
        self.repository = repository
        self.store = store

    @staticmethod
    def _task_candidates(value: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if any(key in item for key in ("task_id", "stage_id", "execution_mode", "exit_criteria")):
                        candidates.append(item)
                    candidates.extend(TaskPolicy._task_candidates(item))
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"tasks", "stages", "workflow_stages", "steps", "workflow", "sop"}:
                    candidates.extend(TaskPolicy._task_candidates(item))
        return candidates

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        values = value if isinstance(value, (list, tuple, set)) else [value]
        return [str(item).strip() for item in values if str(item).strip()]

    @classmethod
    def _runtime_task_contract(
        cls,
        task: dict[str, Any],
        *,
        identifier: str,
        workflow_ref: str,
    ) -> dict[str, Any]:
        result = {**task, "task_id": identifier, "workflow_ref": workflow_ref}
        mode = str(result.get("execution_mode") or "copilot").lower()
        if mode not in {item.value for item in TaskMode}:
            mode = TaskMode.copilot.value
        result["execution_mode"] = mode
        result["name"] = str(result.get("name") or identifier or "Task")
        result["purpose"] = str(result.get("purpose") or result.get("goal") or f"{result['name']} 업무를 수행합니다.")
        result["required_evidence"] = cls._as_list(
            result.get("required_evidence") or result.get("evidence_requirements") or result.get("evidence_refs")
        )
        result["outputs"] = cls._as_list(result.get("outputs"))
        result["action_refs"] = list(
            dict.fromkeys(
                [
                    *cls._as_list(result.get("action_refs")),
                    *cls._as_list(result.get("automated_actions")),
                    *cls._as_list(result.get("manual_actions")),
                ]
            )
        )
        result["event_refs"] = list(
            dict.fromkeys(
                [
                    *cls._as_list(result.get("event_refs")),
                    *cls._as_list(result.get("event_types")),
                    *cls._as_list(result.get("entry_event")),
                    *cls._as_list(result.get("emits_event")),
                ]
            )
        )
        result["tat"] = str(result.get("tat") or result.get("tat_target") or "")

        exit_criteria = cls._as_list(result.get("exit_criteria") or result.get("completion_conditions"))
        if not exit_criteria:
            suffix = "결과와 담당자 판단이 기록되었어요" if mode != TaskMode.autopilot.value else "결과가 확인되었어요"
            exit_criteria = [f"{result['name']} {suffix}"]
        result["exit_criteria"] = exit_criteria

        if not isinstance(result.get("completion_design"), dict):
            confirmation = "system" if mode == TaskMode.autopilot.value else "human"
            system_ref = str(result.get("emits_event") or (result["outputs"][0] if result["outputs"] else ""))
            binding = {}
            if confirmation == "system" and system_ref:
                binding = {
                    "kind": "event" if system_ref in result["event_refs"] else "artifact",
                    "ref": system_ref,
                }
            result["completion_design"] = {
                "version": 1,
                "checks": [
                    {
                        "label": label,
                        "confirmation": confirmation,
                        "binding": binding,
                    }
                    for label in exit_criteria
                ],
                "evidence": [
                    {
                        "label": evidence_ref,
                        "ref": evidence_ref,
                        "provided_by": "system" if mode == TaskMode.autopilot.value else "human" if mode == TaskMode.manual.value else "agent",
                        "required": True,
                    }
                    for evidence_ref in result["required_evidence"]
                ],
            }
        return result

    def resolve_task(self, principal: Principal, task_ref: str) -> dict[str, Any]:
        if not task_ref:
            return {}
        if self.store:
            stored = self.store.get("task_modes", task_ref)
            if stored and (stored.get("employee_id") in {"", principal.employee_id} or principal.is_admin):
                return stored
        for record in self.repository.authoritative_records(principal, include_drafts=True):
            for task in self._task_candidates(record.metadata):
                identifier = str(task.get("task_id") or task.get("stage_id") or task.get("id") or "")
                if task_ref in {identifier, f"{record.record_id}:{identifier}"}:
                    return self._runtime_task_contract(
                        task,
                        identifier=identifier,
                        workflow_ref=str(
                            task.get("workflow_ref")
                            or record.metadata.get("workflow_definition_key")
                            or record.record_id
                        ),
                    )
        return {}

    def resolve_mode(self, principal: Principal, task_ref: str) -> TaskMode:
        task = self.resolve_task(principal, task_ref)
        try:
            return TaskMode(str(task.get("execution_mode") or "copilot").lower())
        except ValueError:
            return TaskMode.copilot

    def evaluate(
        self,
        definition: CapabilityDefinition,
        *,
        principal: Principal,
        task_ref: str,
        confirmed: bool = False,
        semantic_operation: str = "",
    ) -> PolicyDecision:
        mode = self.resolve_mode(principal, task_ref)
        if mode not in definition.task_modes:
            return PolicyDecision(False, mode, False, f"{mode.value} 모드에서 허용되지 않는 업무입니다.")
        if definition.operation == OperationClass.read:
            return PolicyDecision(True, mode, False, "조회 작업입니다.")
        if mode == TaskMode.manual:
            if (
                semantic_operation == "capture"
                and bool(definition.handler_config.get("direct_verified_capture"))
            ):
                return PolicyDecision(
                    True,
                    mode,
                    False,
                    "검증 완료 기록을 private provisional 지식으로만 보존합니다.",
                )
            return PolicyDecision(False, mode, False, "Manual Task에서는 초안이나 실행을 대신 만들지 않습니다.")
        if definition.operation == OperationClass.draft:
            return PolicyDecision(True, mode, False, "private draft만 생성합니다.")
        always_confirm = definition.risk in {RiskLevel.medium, RiskLevel.high}
        if mode == TaskMode.copilot or always_confirm:
            return PolicyDecision(confirmed, mode, not confirmed, "상태 변경 전에 확인이 필요합니다.")
        if definition.risk == RiskLevel.low and mode == TaskMode.autopilot:
            return PolicyDecision(True, mode, False, "허용된 저위험 Autopilot 작업입니다.")
        return PolicyDecision(False, mode, True, "실행 정책을 만족하지 않습니다.")

    @staticmethod
    def enforce(decision: PolicyDecision) -> None:
        if decision.allowed:
            return
        status_code = 409 if decision.confirmation_required else 403
        raise HTTPException(
            status_code=status_code,
            detail={
                "status": "confirmation_required" if decision.confirmation_required else "policy_denied",
                "task_mode": decision.mode.value,
                "message": decision.reason,
            },
        )
