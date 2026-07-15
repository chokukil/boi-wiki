from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from .models import HarnessCheck, HarnessResult, TaskMode, WorkContextPack, WorkIntent, WorkOperation


Validator = Callable[[dict[str, Any]], list[HarnessCheck]]


@dataclass(frozen=True)
class HarnessDefinition:
    harness_id: str
    version: str
    title: str
    phases: tuple[str, ...]
    operations: tuple[str, ...]
    validator_plugin: str
    validator: Validator
    document_ref: str
    required_context: tuple[str, ...]
    input_contract: str
    output_contract: str
    allowed_tools: tuple[str, ...]
    risk_policy: str
    test_contracts: tuple[str, ...]
    completion_policy: str
    fallback_policy: str
    status: str = "active"
    model_profiles: tuple[str, ...] = ("default",)
    fixture_revision: str = ""
    rollback_version: str = ""
    retryable: bool = False
    interruptible: bool = False
    evaluator_policy: dict[str, Any] = field(default_factory=dict)
    # A candidate may only change surfaces with an executable runtime applier.
    # Additional surfaces are opt-in per catalog definition when their applier
    # exists; storing an inert reviewed change would make release misleading.
    editable_surfaces: tuple[str, ...] = ("loop_budget",)
    immutable_boundaries: tuple[str, ...] = (
        "acl", "rbac", "risk_policy", "confirmation_policy", "autopilot_allowlist",
        "required_completion_evidence", "canonical_write_policy", "evaluator_thresholds",
    )

    def public_payload(self) -> dict[str, Any]:
        return {
            "harness_id": self.harness_id,
            "version": self.version,
            "title": self.title,
            "phases": list(self.phases),
            "operations": list(self.operations),
            "validator_plugin": self.validator_plugin,
            "document_ref": self.document_ref,
            "required_context": list(self.required_context),
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "allowed_tools": list(self.allowed_tools),
            "risk_policy": self.risk_policy,
            "test_contracts": list(self.test_contracts),
            "completion_policy": self.completion_policy,
            "fallback_policy": self.fallback_policy,
            "status": self.status,
            "model_profiles": list(self.model_profiles),
            "fixture_revision": self.fixture_revision,
            "rollback_version": self.rollback_version,
            "retryable": self.retryable,
            "interruptible": self.interruptible,
            "evaluator_policy": dict(self.evaluator_policy),
            "editable_surfaces": list(self.editable_surfaces),
            "immutable_boundaries": list(self.immutable_boundaries),
        }

    def binding(self, model_profile: str) -> dict[str, Any]:
        return {
            "harness_id": self.harness_id,
            "version": self.version,
            "status": self.status,
            "model_profile": model_profile or "default",
            "fixture_revision": self.fixture_revision,
            "rollback_version": self.rollback_version,
            "definition": self.public_payload(),
            "active_changes": {},
            "release_state": "catalog_version",
        }


def _check(check_id: str, label: str, passed: bool, message: str, *, warning: bool = False) -> HarnessCheck:
    return HarnessCheck(
        check_id=check_id,
        label=label,
        status="passed" if passed else "warning" if warning else "blocked",
        message="" if passed else message,
    )


def _context_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    context: WorkContextPack = payload["context"]
    intent: WorkIntent = payload["intent"]
    anchor_required = bool(
        intent.scope in {"current", "selected"}
        or intent.context_refs
        or intent.target_ref
        or context.task_ref
    )
    anchor_ready = bool(
        (context.page_anchor and context.page_anchor.resolved)
        or (context.goal_anchor and context.goal_anchor.resolved)
        or context.task_ref
        or (
            intent.target_ref
            and str(context.business_context.get("target_ref") or "") == intent.target_ref
        )
    )
    # A Task's completion/evidence design is the verified execution contract
    # needed to open the work loop. It is not completion evidence: the Task
    # runtime Harness and ExitCriteriaResult still require the resulting human
    # record or system binding before completion.
    execution_contract_ready = bool(
        context.task_ref
        and (context.completion_design or context.required_evidence)
    )
    evidence_ready = bool(context.evidence_refs) or execution_contract_ready
    no_evidence_can_be_reported = intent.operation in {
        WorkOperation.understand,
        WorkOperation.observe,
        WorkOperation.compare,
        WorkOperation.connect,
        WorkOperation.create,
        WorkOperation.refine,
    }
    return [
        _check(
            "context.anchor",
            "현재 업무 맥락",
            not anchor_required or anchor_ready,
            "현재 화면을 업무 맥락으로 확인하지 못했습니다.",
        ),
        _check(
            "context.evidence",
            "사용할 근거",
            evidence_ready or intent.operation in {WorkOperation.create, WorkOperation.capture},
            "답변이나 판단에 사용할 검증된 근거가 없습니다.",
            warning=no_evidence_can_be_reported,
        ),
        _check(
            "context.raw-isolation",
            "대용량 원본 격리",
            bool(context.context_manifest and not context.context_manifest.raw_content_in_prompt),
            "대용량 또는 원본 데이터가 Context 정책을 우회했습니다.",
        ),
    ]


def _sop_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    artifact = payload.get("artifact") or {}
    if payload.get("phase") == "preflight" and not artifact:
        intent: WorkIntent = payload["intent"]
        return [
            _check("sop-preflight.goal", "업무 목적", bool(intent.goal.strip()), "SOP로 만들 업무 목적이 없습니다."),
            _check(
                "sop-preflight.mode",
                "사람과 AI의 수행 방식",
                payload.get("task_mode") in {TaskMode.manual, TaskMode.copilot, TaskMode.autopilot},
                "Task 수행 방식을 확인하지 못했습니다.",
            ),
        ]
    draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else artifact
    tasks = [item for item in draft.get("tasks") or [] if isinstance(item, dict)]
    task_contracts_ready = bool(tasks) and all(
        item.get("name")
        and item.get("purpose")
        and item.get("execution_mode") in {"manual", "copilot", "autopilot"}
        and (item.get("completion_design") or (item.get("exit_criteria") and item.get("required_evidence")))
        for item in tasks
    )
    autopilot_ready = all(
        item.get("execution_mode") != "autopilot"
        or (
            bool((item.get("completion_design") or {}).get("checks"))
            and all(
                check.get("confirmation") == "system"
                and isinstance(check.get("binding"), dict)
                and check["binding"].get("kind") not in {None, "", "none"}
                and check["binding"].get("ref")
                for check in (item.get("completion_design") or {}).get("checks") or []
            )
        )
        for item in tasks
    )
    return [
        _check("sop.goal", "업무 목적", bool(draft.get("goal") or draft.get("description")), "SOP의 업무 목적이 없습니다."),
        _check("sop.tasks", "Workflow와 Task", bool(tasks), "Workflow에 하나 이상의 Task가 필요합니다."),
        _check("sop.task-contracts", "Task 완료 항목과 근거", task_contracts_ready, "일부 Task의 수행 방식, 완료 항목 또는 확인 자료가 비어 있습니다."),
        _check(
            "sop.autopilot-bindings",
            "Autopilot 실행 연결",
            autopilot_ready,
            "자동 수행 Task에 시스템으로 확인 가능한 연결이 없습니다.",
            warning=payload.get("phase") not in {"test", "run"},
        ),
    ]


def _action_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    artifact = payload.get("artifact") or {}
    if payload.get("phase") == "preflight" and not artifact:
        intent: WorkIntent = payload["intent"]
        return [_check("action-preflight.goal", "Action 목적", bool(intent.goal.strip()), "Action이 도울 업무 목적이 없습니다.")]
    draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else artifact
    connector = draft.get("connector") or draft.get("connector_kind")
    return [
        _check("action.connector", "연결할 시스템", bool(connector), "Action connector가 정해지지 않았습니다."),
        _check("action.input", "필요한 입력", bool(draft.get("inputs") or draft.get("input_schema")), "Action 입력 계약이 없습니다."),
        _check("action.output", "남길 결과", bool(draft.get("output_contract") or draft.get("output_schema")), "Action 결과 계약이 없습니다."),
        _check("action.preview", "먼저 시험하기", draft.get("preview_only") is True or draft.get("dry_run_default") is True, "신규 Action은 preview 또는 dry-run이 기본이어야 합니다."),
        _check("action.risk", "위험도와 승인", bool(draft.get("risk") or draft.get("risk_level")), "Action 위험도가 정해지지 않았습니다."),
    ]


def _action_execution_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    context: WorkContextPack = payload["context"]
    intent: WorkIntent = payload["intent"]
    action_key = str(
        context.business_context.get("action_key")
        or (intent.target_ref.removeprefix("action:") if intent.target_ref.startswith("action:") else "")
    ).strip()
    return [
        _check("action-execution.target", "실행할 Action", bool(action_key), "실행할 Action을 확인하지 못했습니다."),
        _check(
            "action-execution.context",
            "업무 맥락과 근거",
            bool(context.evidence_refs or context.page_anchor or context.goal_anchor),
            "Action 실행의 업무 맥락이나 근거가 없습니다.",
        ),
        _check(
            "action-execution.raw-isolation",
            "원본과 비밀정보 격리",
            bool(context.context_manifest and not context.context_manifest.raw_content_in_prompt),
            "Action 입력이 Context 격리 정책을 우회했습니다.",
        ),
    ]


def _business_event_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    artifact = payload.get("artifact") or {}
    if payload.get("phase") == "preflight" and not artifact:
        intent: WorkIntent = payload["intent"]
        return [_check("event-preflight.goal", "업무 시작 목적", bool(intent.goal.strip()), "업무 이벤트가 시작할 업무 목적이 없습니다.")]
    draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else artifact
    trigger_mode = str(draft.get("trigger_mode") or "").lower()
    condition_optional = trigger_mode in {"immediate", "direct", "manual", "schedule", "scheduled"}
    grouping_required = trigger_mode in {"repeated", "sustained", "aggregate", "state_change", "composite"}
    checks = [
        _check("event.source", "판단할 신호", bool(draft.get("source_kind")), "업무 이벤트가 볼 신호가 없습니다."),
        _check("event.trigger", "발생 방식", bool(trigger_mode), "업무 이벤트 발생 방식이 없습니다."),
        _check("event.target", "발생시킬 업무 이벤트", bool(draft.get("target_event_type")), "발생시킬 업무 이벤트가 없습니다."),
        _check(
            "event.conditions",
            "판단 조건",
            condition_optional or bool(draft.get("conditions")),
            "선택한 발생 방식에 필요한 판단 조건이 없습니다.",
        ),
        _check(
            "event.grouping",
            "같은 업무로 묶는 기준",
            not grouping_required or bool(draft.get("fingerprint_fields")),
            "반복·상태·복합 신호를 같은 업무로 묶을 기준이 없습니다.",
        ),
    ]
    if payload.get("phase") == "test":
        domain_test = artifact.get("domain_test") if isinstance(artifact.get("domain_test"), dict) else {}
        decision = domain_test.get("decision") if isinstance(domain_test.get("decision"), dict) else {}
        checks.append(
            _check(
                "event.sample-decision",
                "샘플 판단 결과",
                bool(
                    decision.get("dry_run") is True
                    and decision.get("decision")
                    in {"published", "suppressed", "aggregated", "pending_confirmation", "ignored"}
                ),
                "실제 Detector의 샘플 판단 결과가 없습니다.",
            )
        )
    return checks


def _skill_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    artifact = payload.get("artifact") or {}
    if payload.get("phase") == "preflight" and not artifact:
        intent: WorkIntent = payload["intent"]
        return [_check("skill-preflight.goal", "반복 업무 목적", bool(intent.goal.strip()), "Skill이 도울 반복 업무가 없습니다.")]
    draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else artifact
    tests = [item for item in draft.get("tests") or [] if isinstance(item, dict)]
    checks = [
        _check("skill.contract", "입력과 결과", bool(draft.get("input_schema")) and bool(draft.get("output_schema")), "Skill의 입력 또는 결과 계약이 없습니다."),
        _check("skill.permissions", "사용 권한", bool(draft.get("permissions")), "Skill 사용 권한이 정해지지 않았습니다."),
        _check("skill.tests", "시험 시나리오", bool(tests), "Skill을 확인할 시험 시나리오가 없습니다."),
    ]
    if payload.get("phase") == "test":
        test_result = artifact.get("test_result") if isinstance(artifact.get("test_result"), dict) else {}
        checks.append(
            _check(
                "skill.executable-test",
                "실제 시험 결과",
                test_result.get("status") == "passed",
                "현재 Skill revision의 실제 시험이 통과하지 않았습니다.",
            )
        )
    return checks


def _task_runtime_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    context: WorkContextPack = payload["context"]
    mode: TaskMode = payload.get("task_mode") or context.task_mode
    completion = context.completion_design
    checks = list(completion.checks) if completion else []
    evidence = list(completion.evidence) if completion else []
    human_ready = bool(checks) and any(item.confirmation == "human" for item in checks)
    system_ready = bool(checks) and all(
        item.confirmation == "system"
        and item.binding is not None
        and item.binding.kind != "none"
        and bool(item.binding.ref)
        for item in checks
    )
    completion_ready = system_ready if mode == TaskMode.autopilot else human_ready
    return [
        _check("task.completion", "완료된 모습", completion_ready, "수행 방식에 맞는 완료 확인 항목이 없습니다."),
        _check("task.evidence", "확인할 자료", bool(evidence or context.required_evidence), "Task 완료를 확인할 자료가 없습니다."),
        _check(
            "task.autopilot",
            "자동 확인 연결",
            mode != TaskMode.autopilot or system_ready,
            "자동 수행에는 시스템으로 확인 가능한 연결이 필요합니다. 연결을 보완하거나 Copilot으로 전환하세요.",
        ),
    ]


def _learning_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    candidate = payload.get("candidate") or {}
    source_refs = [str(item) for item in candidate.get("source_refs") or [] if str(item).strip()]
    reusable = str(candidate.get("reusable_lesson") or candidate.get("summary") or "").strip()
    novelty = candidate.get("novelty") if isinstance(candidate.get("novelty"), dict) else {}
    return [
        _check("learning.sources", "확인 가능한 출처", bool(source_refs), "출처가 없는 내용은 지식 후보로 저장할 수 없습니다."),
        _check("learning.lesson", "다음에 재사용할 내용", len(reusable) >= 12, "다음 업무에 재사용할 내용이 충분하지 않습니다."),
        _check(
            "learning.duplicate",
            "기존 지식과 중복 확인",
            novelty.get("checked") is True,
            "기존 지식과의 중복 여부를 확인하지 않았습니다.",
        ),
        _check(
            "learning.raw-chat",
            "대화 원문 제외",
            candidate.get("raw_transcript_stored") is not True,
            "대화 또는 로그 원문 전체를 지식으로 저장할 수 없습니다.",
        ),
    ]


def _claim_grounding_checks(payload: dict[str, Any]) -> list[HarnessCheck]:
    context: WorkContextPack = payload["context"]
    artifact = payload.get("artifact") or {}
    claims = [item for item in artifact.get("claims") or [] if isinstance(item, dict)]
    if payload.get("phase") == "preflight":
        return [
            _check(
                "claim-grounding.provenance",
                "근거 출처",
                bool(context.context_manifest and not context.context_manifest.raw_content_in_prompt),
                "claim 검증에 사용할 source provenance가 준비되지 않았습니다.",
            )
        ]
    return [
        _check(
            "claim-grounding.binding",
            "claim과 chunk 연결",
            bool(claims)
            and all(item.get("source_refs") and item.get("supporting_chunk_ids") for item in claims),
            "직접 연결된 source와 chunk가 없는 factual claim이 있습니다.",
        )
    ]


class HarnessRegistry:
    _VALIDATORS: dict[str, Validator] = {
        "context_invariants": _context_checks,
        "sop_invariants": _sop_checks,
        "action_authoring_invariants": _action_checks,
        "action_execution_invariants": _action_execution_checks,
        "business_event_invariants": _business_event_checks,
        "skill_invariants": _skill_checks,
        "task_runtime_invariants": _task_runtime_checks,
        "learning_invariants": _learning_checks,
        "claim_grounding_invariants": _claim_grounding_checks,
    }

    def __init__(self, catalog_path: Path | None = None) -> None:
        self.catalog_path = catalog_path or (
            Path(__file__).resolve().parents[3] / "data" / "agent_catalog" / "harnesses-v2.yaml"
        )
        payload = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8")) or {}
        self.version = str(payload.get("version") or "2.0")
        definitions: dict[str, HarnessDefinition] = {}
        for raw in payload.get("harnesses") or []:
            harness_id = str(raw.get("harness_id") or "").strip()
            plugin_id = str(raw.get("validator_plugin") or "").strip()
            if not harness_id or harness_id in definitions:
                raise ValueError(f"invalid or duplicate harness_id: {harness_id}")
            validator = self._VALIDATORS.get(plugin_id)
            if validator is None:
                raise ValueError(f"unknown harness validator plugin: {plugin_id}")
            definitions[harness_id] = HarnessDefinition(
                harness_id=harness_id,
                version=str(raw.get("version") or "1.0"),
                title=str(raw.get("title") or harness_id),
                phases=tuple(str(item) for item in raw.get("phases") or []),
                operations=tuple(str(item) for item in raw.get("operations") or []),
                validator_plugin=plugin_id,
                validator=validator,
                document_ref=str(raw.get("document_ref") or ""),
                required_context=tuple(str(item) for item in raw.get("required_context") or []),
                input_contract=str(raw.get("input_contract") or ""),
                output_contract=str(raw.get("output_contract") or ""),
                allowed_tools=tuple(str(item) for item in raw.get("allowed_tools") or []),
                risk_policy=str(raw.get("risk_policy") or ""),
                test_contracts=tuple(str(item) for item in raw.get("test_contracts") or []),
                completion_policy=str(raw.get("completion_policy") or ""),
                fallback_policy=str(raw.get("fallback_policy") or ""),
                status=str(raw.get("status") or "active"),
                model_profiles=tuple(str(item) for item in raw.get("model_profiles") or ["default"]),
                fixture_revision=str(raw.get("fixture_revision") or ""),
                rollback_version=str(raw.get("rollback_version") or ""),
                retryable=bool(raw.get("retryable", False)),
                interruptible=bool(raw.get("interruptible", False)),
                evaluator_policy=dict(raw.get("evaluator_policy") or {}),
                editable_surfaces=tuple(str(item) for item in raw.get("editable_surfaces") or HarnessDefinition.__dataclass_fields__["editable_surfaces"].default),
                immutable_boundaries=tuple(str(item) for item in raw.get("immutable_boundaries") or HarnessDefinition.__dataclass_fields__["immutable_boundaries"].default),
            )
        self._definitions = definitions

    def definitions(self) -> list[dict[str, Any]]:
        return [item.public_payload() for item in self._definitions.values()]

    def bindings(self, harness_ids: list[str], model_profile: str) -> list[dict[str, Any]]:
        return [self._definitions[item].binding(model_profile) for item in harness_ids if item in self._definitions]

    def definition(self, harness_id: str) -> HarnessDefinition:
        return self._definitions[harness_id]

    def evaluate(
        self,
        harness_id: str,
        *,
        phase: str,
        intent: WorkIntent,
        context: WorkContextPack,
        artifact: dict[str, Any] | None = None,
        candidate: dict[str, Any] | None = None,
        task_mode: TaskMode = TaskMode.copilot,
        binding: dict[str, Any] | None = None,
    ) -> HarnessResult:
        definition = self._definitions[harness_id]
        snapshot = binding.get("definition") if isinstance(binding, dict) else {}
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        phases = tuple(str(item) for item in snapshot.get("phases") or definition.phases)
        version = str((binding or {}).get("version") or snapshot.get("version") or definition.version)
        retryable = bool(snapshot.get("retryable", definition.retryable))
        interruptible = bool(snapshot.get("interruptible", definition.interruptible))
        if phase not in phases:
            checks = [
                _check(
                    "harness.phase",
                    "검증 단계",
                    False,
                    f"{definition.title}은 {phase} 단계를 지원하지 않습니다.",
                )
            ]
            return HarnessResult(
                harness_id=definition.harness_id,
                version=version,
                status="blocked",
                checks=checks,
                blockers=[checks[0].message],
                definition_ref=f"{definition.harness_id}@{version}",
                phase=phase,
                evaluated_facts={"operation": intent.operation.value, "phase_supported": False},
                retryable=False,
                interruptible=interruptible,
            )
        checks = definition.validator(
            {
                "phase": phase,
                "intent": intent,
                "context": context,
                "artifact": artifact or {},
                "candidate": candidate or {},
                "task_mode": task_mode,
            }
        )
        blockers = [item.message for item in checks if item.status == "blocked" and item.message]
        status = "blocked" if blockers else "warning" if any(item.status == "warning" for item in checks) else "passed"
        return HarnessResult(
            harness_id=definition.harness_id,
            version=version,
            status=status,
            checks=checks,
            blockers=blockers,
            definition_ref=f"{definition.harness_id}@{version}",
            phase=phase,
            evaluated_facts={
                "operation": intent.operation.value,
                "task_mode": task_mode.value,
                "evidence_count": len(context.evidence_refs),
                "artifact_present": bool(artifact),
                "candidate_present": bool(candidate),
                "active_change_keys": sorted((binding or {}).get("active_changes") or {}),
            },
            retryable=retryable and status != "passed",
            interruptible=interruptible and status != "passed",
        )

    def harnesses_for(
        self,
        intent: WorkIntent,
        artifact_kind: str = "",
        *,
        phase: str = "",
    ) -> list[str]:
        requested = list(dict.fromkeys(intent.harness_ids or ["context.work"]))
        unknown = [item for item in requested if item not in self._definitions]
        if unknown:
            raise KeyError(f"unknown harness binding: {', '.join(unknown)}")
        operation = intent.operation.value
        return [
            harness_id
            for harness_id in requested
            if not self._definitions[harness_id].operations
            or operation in self._definitions[harness_id].operations
            if not phase or phase in self._definitions[harness_id].phases
        ]
