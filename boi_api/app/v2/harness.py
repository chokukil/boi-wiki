from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import HarnessCheck, HarnessResult, TaskMode, WorkContextPack, WorkIntent, WorkOperation


Validator = Callable[[dict[str, Any]], list[HarnessCheck]]


@dataclass(frozen=True)
class HarnessDefinition:
    harness_id: str
    version: str
    title: str
    phases: tuple[str, ...]
    operations: tuple[str, ...]
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
    editable_surfaces: tuple[str, ...] = (
        "context_recipe", "retrieval_policy", "tool_order", "loop_budget",
        "planner_instruction", "presentation_policy", "fallback_order",
    )
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
    deictic = any(term in intent.goal.lower() for term in ("이 문서", "이 sop", "이 task", "현재 문서", "여기"))
    anchor_ready = bool(
        (context.page_anchor and context.page_anchor.resolved)
        or (context.goal_anchor and context.goal_anchor.resolved)
        or context.task_ref
    )
    evidence_ready = bool(context.evidence_refs)
    empty_result_is_valid = context.capability_id == "work.inbox"
    return [
        _check(
            "context.anchor",
            "현재 업무 맥락",
            not deictic or anchor_ready,
            "현재 화면을 업무 맥락으로 확인하지 못했습니다.",
        ),
        _check(
            "context.evidence",
            "사용할 근거",
            evidence_ready or empty_result_is_valid or intent.operation in {WorkOperation.create, WorkOperation.capture},
            "답변이나 판단에 사용할 검증된 근거가 없습니다.",
            warning=intent.operation in {WorkOperation.create, WorkOperation.refine},
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


class HarnessRegistry:
    def __init__(self) -> None:
        self._definitions = {
            item.harness_id: item
            for item in (
                HarnessDefinition(
                    harness_id="context.work",
                    version="1.1",
                    title="업무 맥락 Harness",
                    phases=("preflight", "post_verify"),
                    operations=tuple(item.value for item in WorkOperation),
                    validator=_context_checks,
                    document_ref="boi:public:boi-wiki-manual:agent:work-context-pack",
                    required_context=("goal", "context_manifest", "source_provenance"),
                    input_contract="WorkIntent + WorkContextPack",
                    output_contract="HarnessResult",
                    allowed_tools=("boi_search", "boi_get", "boi_context"),
                    risk_policy="read-only context selection; raw and secret content must stay outside prompts",
                    test_contracts=("deictic_anchor_resolves", "selected_sources_have_provenance", "raw_content_isolated"),
                    completion_policy="the request has a usable anchor or explicit Wiki scope and a provenance manifest",
                    fallback_policy="ask one focused context question or continue with an explicit no-evidence answer",
                ),
                HarnessDefinition(
                    harness_id="sop.authoring",
                    version="1.1",
                    title="SOP 작성 Harness",
                    phases=("preflight", "validate", "preview", "test", "post_verify"),
                    operations=("create", "refine", "connect", "validate", "test", "promote"),
                    validator=_sop_checks,
                    document_ref="boi:public:harness:sop-authoring-harness",
                    required_context=("business_goal", "task_mode", "evidence_policy"),
                    input_contract="SOP draft with Workflow and structured Task completion design",
                    output_contract="validated SOP registration draft",
                    allowed_tools=("boi_search", "boi_get", "sop_draft_create", "sop_draft_validate"),
                    risk_policy="draft-only until a named person confirms the existing SOP publication path",
                    test_contracts=("workflow_has_tasks", "tasks_have_completion_design", "autopilot_bindings_are_verifiable"),
                    completion_policy="all Tasks have purpose, mode, completion checks, evidence and valid automatic bindings where needed",
                    fallback_policy="save a private draft, mark missing connections, and offer Copilot instead of unsafe Autopilot",
                ),
                HarnessDefinition(
                    harness_id="action.authoring",
                    version="1.1",
                    title="Action 작성 Harness",
                    phases=("preflight", "validate", "preview", "test", "post_verify"),
                    operations=("create", "refine", "connect", "validate", "test", "run"),
                    validator=_action_checks,
                    document_ref="boi:public:harness:action-authoring-harness",
                    required_context=("business_goal", "connector", "input_output_contract"),
                    input_contract="Action registration draft",
                    output_contract="validated Action draft or dry-run result",
                    allowed_tools=("boi_search", "boi_get", "action_draft_create", "action_draft_validate"),
                    risk_policy="new Action stays preview-only; side effects require Action Gateway policy and confirmation",
                    test_contracts=("connector_configured", "input_output_schema_present", "dry_run_default", "risk_classified"),
                    completion_policy="connector, schemas, risk and preview behavior are validated",
                    fallback_policy="keep a Manual Action draft and report the missing connector or contract",
                ),
                HarnessDefinition(
                    harness_id="action.execution",
                    version="1.1",
                    title="Action 실행 Harness",
                    phases=("preflight", "validate", "post_verify"),
                    operations=("run",),
                    validator=_action_execution_checks,
                    document_ref="boi:public:harness:action-authoring-harness",
                    required_context=("action_target", "business_context", "evidence"),
                    input_contract="guarded Action invocation plan",
                    output_contract="Action Gateway result + LoopDelta(action_result)",
                    allowed_tools=("boi_plan", "boi_confirm", "action_gateway_invoke"),
                    risk_policy="dry-run first; medium/high risk or external side effects always require confirmation",
                    test_contracts=("target_resolved", "context_present", "secrets_isolated", "result_contract_valid"),
                    completion_policy="an Action Gateway result is recorded and the Task completion binding verifies it",
                    fallback_policy="stop execution, preserve the plan, and ask for a safer target or human handling",
                ),
                HarnessDefinition(
                    harness_id="business-event.definition",
                    version="1.1",
                    title="업무 이벤트 정의 Harness",
                    phases=("preflight", "validate", "preview", "test", "post_verify"),
                    operations=("create", "refine", "connect", "validate", "test", "run"),
                    validator=_business_event_checks,
                    document_ref="boi:public:boi-wiki-manual:use-cases:event-to-action-workflow-planning",
                    required_context=("business_goal", "source_signal", "occurrence_mode"),
                    input_contract="BusinessEventDefinition draft + sample signal",
                    output_contract="SignalDecision preview and inactive definition draft",
                    allowed_tools=("boi_search", "business_event_draft_create", "business_event_test"),
                    risk_policy="definitions remain inactive until sample test and explicit activation confirmation",
                    test_contracts=("source_configured", "trigger_valid", "conditions_valid", "dedupe_or_state_grouping_valid"),
                    completion_policy="sample decisions match the expected publish, ignore, suppress or pending result",
                    fallback_policy="keep the draft inactive and request the missing signal example or grouping key",
                ),
                HarnessDefinition(
                    harness_id="skill.authoring",
                    version="1.1",
                    title="Skill 작성 Harness",
                    phases=("preflight", "validate", "preview", "test", "post_verify"),
                    operations=("create", "refine", "validate", "test", "promote"),
                    validator=_skill_checks,
                    document_ref="boi:public:harness:skill-authoring-harness",
                    required_context=("repeated_work_goal", "source_refs"),
                    input_contract="Skill candidate with schemas, permissions and tests",
                    output_contract="private Skill candidate",
                    allowed_tools=("boi_search", "boi_get", "skill_candidate_create", "skill_test"),
                    risk_policy="Skill is a draft until tests pass; it cannot widen its own permissions",
                    test_contracts=("schemas_present", "permissions_bounded", "test_scenarios_present"),
                    completion_policy="the Skill contract and at least one representative test are valid",
                    fallback_policy="keep the repeated workflow Manual/Copilot and show the missing reusable contract",
                ),
                HarnessDefinition(
                    harness_id="task.runtime",
                    version="1.1",
                    title="Task 수행 Harness",
                    phases=("preflight", "validate", "post_verify"),
                    operations=("run", "observe", "complete"),
                    validator=_task_runtime_checks,
                    document_ref="boi:public:boi-wiki-manual:agent:task-loop",
                    required_context=("task", "task_mode", "completion_design", "evidence"),
                    input_contract="WorkContextPack + LoopDelta",
                    output_contract="verified CompletionRecord or explicit blocker",
                    allowed_tools=("boi_context", "boi_search", "boi_plan", "boi_confirm", "boi_job_status"),
                    risk_policy="Manual and Copilot need human confirmation; Autopilot needs allowlisted, verifiable system bindings",
                    test_contracts=("mode_specific_completion", "required_evidence_present", "no_progress_stops", "limits_enforced"),
                    completion_policy="structured completion checks and Evidence Ledger prove the Task is done",
                    fallback_policy="switch evidence, ask a person, move to Copilot, or stop with a named blocker",
                ),
                HarnessDefinition(
                    harness_id="learning.capture",
                    version="1.1",
                    title="지식 자산화 Harness",
                    phases=("capture", "promote"),
                    operations=("capture", "complete", "promote"),
                    validator=_learning_checks,
                    document_ref="boi:public:boi-wiki-manual:agent:personal-work-pattern-assets",
                    required_context=("source_work_run", "evidence_ledger", "novelty_check"),
                    input_contract="CompletionRecord or evidence-backed KnowledgeCandidate",
                    output_contract="private provisional candidate or promotion preview",
                    allowed_tools=("boi_search", "boi_get", "promotion_preview", "boi_confirm"),
                    risk_policy="raw chat is never knowledge; Team/Public writes require promotion validation and explicit confirmation",
                    test_contracts=("sources_present", "lesson_reusable", "duplicate_checked", "raw_transcript_excluded"),
                    completion_policy="the candidate has provenance, reuse value and a passed promotion preview when shared",
                    fallback_policy="keep or archive the private candidate and prefer augmenting an existing authoritative asset",
                ),
            )
        }

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
    ) -> HarnessResult:
        definition = self._definitions[harness_id]
        if phase not in definition.phases:
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
                version=definition.version,
                status="blocked",
                checks=checks,
                blockers=[checks[0].message],
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
            version=definition.version,
            status=status,
            checks=checks,
            blockers=blockers,
        )

    @staticmethod
    def harnesses_for(intent: WorkIntent, artifact_kind: str = "") -> list[str]:
        result = ["context.work"]
        kind = artifact_kind or intent.asset_kind.value
        authoring = intent.operation in {
            WorkOperation.create,
            WorkOperation.refine,
            WorkOperation.validate,
            WorkOperation.test,
        } or (intent.operation == WorkOperation.connect and intent.desired_outcome != "answer")
        if authoring and kind in {"sop", "workflow", "sop_draft", "sop.plan"}:
            result.append("sop.authoring")
        if authoring and kind in {"action", "action_draft", "action.plan"}:
            result.append("action.authoring")
        if authoring and kind in {"business_event", "business_event_definition_draft", "event", "business_event.plan"}:
            result.append("business-event.definition")
        if intent.operation == WorkOperation.run and intent.asset_kind.value == "business_event":
            result.append("business-event.definition")
        if authoring and kind in {"skill", "skill_draft", "skill.plan"}:
            result.append("skill.authoring")
        if intent.operation == WorkOperation.run and intent.asset_kind.value == "action":
            result.append("action.execution")
        elif (
            intent.operation in {WorkOperation.run, WorkOperation.complete}
            and intent.asset_kind.value in {"task", "workflow"}
        ) or (
            intent.operation == WorkOperation.observe
            and intent.asset_kind.value in {"task", "workflow"}
        ):
            result.append("task.runtime")
        if intent.operation in {WorkOperation.capture, WorkOperation.complete, WorkOperation.promote}:
            result.append("learning.capture")
        return list(dict.fromkeys(result))
