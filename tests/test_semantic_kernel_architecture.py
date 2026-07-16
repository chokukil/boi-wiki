from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from boi_api.app.v2.capabilities import CapabilityRegistry
from boi_api.app.v2.models import (
    GraphQueryDraft,
    LoopContract,
    LoopKind,
    SemanticPlan,
    SemanticSubject,
    WorkIntent,
    WorkOperation,
)
from boi_api.app.v2.semantic_kernel import (
    PlanCompiler,
    PlanValidator,
    SemanticPlanningError,
    semantic_plan_schema,
)
from boi_api.app.v2.work_learning import WorkLearningService
from scripts.evaluate_agent_v2_work_scenarios import (
    evaluate_response,
    expand_scenarios,
    load_resume_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]


def test_semantic_kernel_architecture_guard() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_semantic_kernel_architecture.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_planner_schema_exposes_workrun_continuation_only_for_an_active_run() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")

    inactive = semantic_plan_schema(registry, active_work_run=False)
    active = semantic_plan_schema(registry, active_work_run=True)

    assert "continuation" not in inactive["properties"]
    assert "continuation" in active["properties"]


def test_catalog_only_capability_compiles_without_service_routing_change(tmp_path: Path) -> None:
    source_catalog = yaml.safe_load(
        (ROOT / "data/agent_catalog/capabilities-v2.yaml").read_text(encoding="utf-8")
    )
    template = next(
        item for item in source_catalog["capabilities"] if item["handler"] == "grounded_read"
    )
    capability = {
        **template,
        "capability_id": "test.unseen_asset",
        "title": "테스트용 미지 자산 읽기",
        "description": "catalog만으로 추가되는 읽기 자산",
        "examples": [],
        "starter_offers": [],
    }
    source_catalog["capabilities"] = [*source_catalog["capabilities"], capability]
    catalog_path = tmp_path / "capabilities-v2.yaml"
    catalog_path.write_text(yaml.safe_dump(source_catalog, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (tmp_path / "draft-contracts-v2.yaml").write_text(
        (ROOT / "data/agent_catalog/draft-contracts-v2.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    registry = CapabilityRegistry(catalog_path)
    compiled = PlanCompiler(registry).compile(
        SemanticPlan(
            resolved_goal="테스트 자산의 근거를 설명한다",
            retrieval_query="테스트 자산",
            capability_id="test.unseen_asset",
            user_effect="read",
            operation=WorkOperation.understand,
            presentation="prose",
            confidence=0.99,
        ),
        original_question="테스트 자산을 설명해줘",
        trusted_context_refs=set(),
    )

    assert compiled.capability_id == "test.unseen_asset"
    assert compiled.work_intent.operation == WorkOperation.understand
    assert registry.handler_supported(registry.get("test.unseen_asset"))


def test_plan_validator_rejects_without_mutating_or_falling_back() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    plan = SemanticPlan(
        resolved_goal="미등록 기능으로 문서를 만든다",
        retrieval_query="미등록 기능",
        capability_id="test.not_registered",
        user_effect="execute",
        operation=WorkOperation.run,
        presentation="artifact",
        confidence=0.91,
    )
    before = plan.model_dump(mode="json")

    report = PlanValidator(registry).validate(plan, trusted_context_refs=set())

    assert report.valid is False
    assert {item.code for item in report.issues} >= {"capability.unknown"}
    assert plan.model_dump(mode="json") == before
    try:
        PlanCompiler(registry).compile(
            plan,
            original_question="미등록 기능을 실행해줘",
            trusted_context_refs=set(),
        )
    except SemanticPlanningError as exc:
        assert exc.code == "planner_invalid"
    else:
        raise AssertionError("an unknown capability must not compile through a fallback")


def test_semantic_plan_preserves_large_trusted_context_sets() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    trusted_refs = {f"boi:public:reference:{index}" for index in range(40)}
    plan = SemanticPlan(
        resolved_goal="선택한 검토 지식 전체를 근거로 원칙을 설명한다",
        retrieval_query="검토 지식 원칙",
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.understand,
        context_refs=sorted(trusted_refs),
        confidence=0.99,
    )

    report = PlanValidator(registry).validate(plan, trusted_context_refs=trusted_refs)
    compiled = PlanCompiler(registry).compile(
        plan,
        original_question="검토 지식의 원칙을 설명해줘",
        trusted_context_refs=trusted_refs,
    )

    assert report.valid is True
    assert compiled.work_intent.context_refs == sorted(trusted_refs)


def test_loop_contract_is_catalog_driven_and_not_reclassified_by_runtime() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    read_definition = registry.get("knowledge.search")
    task_definition = registry.get("task.work")

    read_intent = WorkIntent(
        goal="업무 지식을 확인한다",
        operation=WorkOperation.run,
        loop_contract=read_definition.default_loop_contract,
    )
    task_intent = WorkIntent(
        goal="업무 결과를 기록한다",
        operation=WorkOperation.understand,
        loop_contract=task_definition.default_loop_contract,
    )

    assert WorkLearningService.resolve_loop_policy(read_intent).kind == LoopKind.turn
    assert WorkLearningService.resolve_loop_policy(task_intent).kind == LoopKind.goal


def test_plan_validator_rejects_loop_outside_capability_contract() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    plan = SemanticPlan(
        resolved_goal="검토된 지식을 설명한다",
        retrieval_query="검토된 지식",
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.understand,
        loop_contract=LoopContract(
            kind=LoopKind.goal,
            max_iterations=2,
            max_runs=1,
            exit_criteria_refs=["answer_grounded"],
        ),
        confidence=0.99,
    )

    report = PlanValidator(registry).validate(plan, trusted_context_refs=set())

    assert report.valid is False
    assert {item.code for item in report.issues} >= {"loop.kind_not_allowed"}


def test_plan_validator_uses_catalog_owned_graph_operation_contracts() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    graph = GraphQueryDraft(
        enabled=True,
        query_kind="workflow",
        focal_mentions=["업무 이벤트", "SOP"],
        presentation="mermaid",
    )
    invalid = SemanticPlan(
        resolved_goal="업무 이벤트와 SOP의 관계를 그림으로 본다",
        retrieval_query="업무 이벤트 SOP 관계",
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.understand,
        presentation="mermaid",
        graph_query=graph,
        confidence=0.95,
    )
    valid = invalid.model_copy(update={"operation": WorkOperation.connect})

    invalid_report = PlanValidator(registry).validate(invalid, trusted_context_refs=set())
    valid_report = PlanValidator(registry).validate(valid, trusted_context_refs=set())

    assert invalid_report.valid is False
    assert {item.code for item in invalid_report.issues} >= {
        "operation.graph_query_not_allowed",
        "operation.presentation_not_allowed",
    }
    assert valid_report.valid is True


def test_plan_validator_rejects_inconsistent_topic_and_target_identity() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    prior_ref = "boi:public:workflow:event-response"
    other_ref = "runtime:a2ui-capability-catalog"
    trusted = {prior_ref, other_ref}
    reused_as_new = SemanticPlan(
        resolved_goal="같은 관계를 다른 화면으로 본다",
        retrieval_query="업무 이벤트 관계",
        topic_action="new",
        subjects=[
            SemanticSubject(
                mention="업무 이벤트 관계",
                entity_ref=prior_ref,
                entity_kind="workflow",
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.connect,
        presentation="mermaid",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="workflow",
            focal_mentions=["업무 이벤트 관계"],
            presentation="mermaid",
        ),
        target_ref=other_ref,
        confidence=0.9,
    )

    report = PlanValidator(registry).validate(
        reused_as_new,
        trusted_context_refs=trusted,
        prior_topic_entities=[prior_ref],
    )

    assert report.valid is False
    assert {item.code for item in report.issues} >= {
        "topic.new_reuses_prior_subject",
        "subject.target_mismatch",
    }


def test_plan_validator_requires_resolved_identity_for_topic_transition() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    prior_ref = "boi:public:workflow:event-response"
    unresolved = SemanticSubject(
        mention="그 대상",
        entity_ref="",
        entity_kind="workflow",
        resolution="unresolved",
    )
    base = SemanticPlan(
        resolved_goal="선택한 대상의 시간 흐름을 본다",
        retrieval_query="선택한 대상 시간 흐름",
        subjects=[unresolved],
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.connect,
        presentation="timeline",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="timeline",
            focal_mentions=["그 대상"],
            presentation="timeline",
        ),
        confidence=0.9,
    )

    continued = PlanValidator(registry).validate(
        base.model_copy(update={"topic_action": "continue", "reference_resolution": "specific"}),
        trusted_context_refs={prior_ref},
        prior_topic_entities=[prior_ref],
    )
    changed = PlanValidator(registry).validate(
        base.model_copy(update={"topic_action": "new"}),
        trusted_context_refs={prior_ref},
        prior_topic_entities=[prior_ref],
    )

    assert {item.code for item in continued.issues} >= {"topic.subject_not_resolved"}
    assert {item.code for item in changed.issues} >= {"topic.new_subject_not_resolved"}


def test_plan_validator_requires_explicit_consistent_multi_subject_reference_resolution() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    refs = ["boi:public:concept:a2ui", "boi:public:concept:ontology"]
    subjects = [
        SemanticSubject(
            mention=ref.rsplit(":", 1)[-1],
            entity_ref=ref,
            entity_kind="concept",
            resolution="resolved",
        )
        for ref in refs
    ]
    base = SemanticPlan(
        resolved_goal="직전 두 주제의 실제 사용 범위를 확인한다",
        retrieval_query="A2UI Ontology 실제 사용 범위",
        topic_action="continue",
        subjects=subjects,
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.understand,
        presentation="prose",
    )

    missing = PlanValidator(registry).validate(
        base,
        trusted_context_refs=set(refs),
        prior_topic_entities=refs,
    )
    specific = PlanValidator(registry).validate(
        base.model_copy(update={"reference_resolution": "specific"}),
        trusted_context_refs=set(refs),
        prior_topic_entities=refs,
    )
    all_subjects = PlanValidator(registry).validate(
        base.model_copy(update={"reference_resolution": "all"}),
        trusted_context_refs=set(refs),
        prior_topic_entities=refs,
    )

    assert "topic.continuation_resolution_missing" in {item.code for item in missing.issues}
    assert "topic.specific_reference_cardinality" in {item.code for item in specific.issues}
    assert all_subjects.valid is True


def test_plan_validator_uses_catalog_owned_work_view_operation_contract() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    person_ref = "person:100001"
    plan = SemanticPlan(
        resolved_goal="공식 역할과 현재 업무를 구분한다",
        retrieval_query="공식 역할 현재 업무",
        subjects=[
            SemanticSubject(
                mention="현재 사용자",
                entity_ref=person_ref,
                entity_kind="person",
                resolution="resolved",
            )
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.observe,
        presentation="table",
        work_view="combined",
    )

    report = PlanValidator(registry).validate(plan, trusted_context_refs={person_ref})

    assert "work_view.operation_not_allowed" in {item.code for item in report.issues}


def test_plan_validator_rejects_duplicate_resolved_subjects() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    person_ref = "person:100001"
    plan = SemanticPlan(
        resolved_goal="현재 업무와 공식 역할 관계를 구분한다",
        retrieval_query="현재 업무 공식 역할 관계",
        subjects=[
            SemanticSubject(
                mention="현재 사용자",
                entity_ref=person_ref,
                entity_kind="person",
                resolution="resolved",
            ),
            SemanticSubject(
                mention="담당자",
                entity_ref=person_ref,
                entity_kind="person",
                resolution="resolved",
            ),
        ],
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.connect,
        presentation="table",
        graph_query=GraphQueryDraft(
            enabled=True,
            query_kind="responsibility",
            focal_mentions=[person_ref],
            presentation="table",
        ),
        confidence=0.9,
    )

    report = PlanValidator(registry).validate(
        plan,
        trusted_context_refs={person_ref},
    )

    assert {item.code for item in report.issues} >= {"subject.duplicate_ref"}


def test_clarification_is_model_authored_and_never_filled_by_service_fallback() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    plan = SemanticPlan(
        resolved_goal="대상이 모호한 관계 요청을 확인한다",
        retrieval_query="관계 요청 대상",
        topic_action="clarify",
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.understand,
        presentation="prose",
        confidence=0.71,
    )

    report = PlanValidator(registry).validate(plan, trusted_context_refs=set())

    assert report.valid is False
    assert {item.code for item in report.issues} >= {"topic.clarification_missing"}


def test_validation_documents_are_selected_by_the_plan_not_an_operation_rewrite() -> None:
    registry = CapabilityRegistry(ROOT / "data/agent_catalog/capabilities-v2.yaml")
    plan = SemanticPlan(
        resolved_goal="내부 acceptance 결과를 검증한다",
        retrieval_query="내부 acceptance 결과",
        capability_id="knowledge.search",
        user_effect="read",
        operation=WorkOperation.validate,
        evidence_scope="validation",
        presentation="prose",
        confidence=0.99,
    )

    report = PlanValidator(registry).validate(plan, trusted_context_refs=set())
    compiled = PlanCompiler(registry).compile(
        plan,
        original_question="acceptance 결과를 검증해줘",
        trusted_context_refs=set(),
    )

    assert report.valid is True
    assert compiled.work_intent.answer_source_scope == "validation"
    assert registry.get("knowledge.search").default_evidence_scope == "canonical"


def test_semantic_kernel_holdout_has_required_coverage() -> None:
    fixture = yaml.safe_load(
        (ROOT / "tests/fixtures/semantic_kernel_holdout.yaml").read_text(encoding="utf-8")
    )
    intent_groups = fixture.get("intent_groups") or []
    conversation_rows = fixture.get("scenarios") or []
    base = expand_scenarios(fixture, repetitions=1)
    repeated = expand_scenarios(fixture, repetitions=int(fixture.get("repetitions") or 0))

    assert len(intent_groups) == 12
    assert all(len(item.get("expressions") or []) == 5 for item in intent_groups)
    assert len([item for item in conversation_rows if item.get("turns")]) == 12
    assert len([item for item in conversation_rows if not item.get("turns")]) == 8
    assert len(base) == 80
    assert len(repeated) == 240
    assert all(item.get("require_semantic_plan") for item in repeated)


def test_semantic_holdout_checkpoint_resumes_only_a_compatible_prefix(tmp_path: Path) -> None:
    checkpoint = tmp_path / "holdout.json"
    checkpoint.write_text(
        """{
  "fixture_version": "semantic-kernel-holdout/v1",
  "base_url": "http://127.0.0.1:8769",
  "implementation_revision": "revision-1",
  "runner_revision": "runner-1",
  "fixture_checksum": "fixture-1",
  "total": 3,
  "results": [
    {"id": "scenario-1", "passed": true},
    {"id": "scenario-2", "passed": false}
  ]
}
""",
        encoding="utf-8",
    )

    restored = load_resume_checkpoint(
        checkpoint,
        fixture_version="semantic-kernel-holdout/v1",
        base_url="http://127.0.0.1:8769/",
        scenario_ids=["scenario-1", "scenario-2", "scenario-3"],
        implementation_revision="revision-1",
        runner_revision="runner-1",
        fixture_checksum="fixture-1",
    )

    assert [item["id"] for item in restored] == ["scenario-1", "scenario-2"]
    try:
        load_resume_checkpoint(
            checkpoint,
            fixture_version="semantic-kernel-holdout/v2",
            base_url="http://127.0.0.1:8769",
            scenario_ids=["scenario-1", "scenario-2", "scenario-3"],
            implementation_revision="revision-2",
            runner_revision="runner-1",
            fixture_checksum="fixture-1",
        )
    except ValueError as exc:
        assert "not compatible" in str(exc)
    else:
        raise AssertionError("an incompatible checkpoint must not be resumed")


def test_semantic_holdout_accepts_a_fail_closed_human_interrupt_without_an_execution_plan() -> None:
    evaluated = evaluate_response(
        {
            "id": "ambiguous-reference",
            "expected_capability": "knowledge.search",
            "expected_operation": "understand",
            "expected_user_effect": "read",
            "expected_topic_mode": "clarify",
            "expected_status": "needs_input",
            "require_semantic_plan": True,
            "require_internal_sources_only": True,
        },
        {
            "status": "needs_input",
            "capability_id": "semantic.planner",
            "stop_reason": "human_interrupt",
            "answer": {"markdown": "어느 항목을 말씀하시는지 하나를 선택해주세요."},
            "answerability": {"status": "insufficient"},
            "artifact_refs": [],
            "plan_ref": "",
            "semantic_plan_ref": "",
            "used_source_refs": [],
            "citations": [],
            "evidence_refs": [],
        },
    )

    assert evaluated["passed"] is True
    assert evaluated["checks"]["human_interrupt"] is True


def test_semantic_holdout_rejects_a_human_interrupt_that_created_a_mutation_plan() -> None:
    evaluated = evaluate_response(
        {
            "id": "unsafe-ambiguous-reference",
            "expected_capability": "knowledge.search",
            "expected_operation": "understand",
            "expected_user_effect": "read",
            "expected_status": "needs_input",
            "require_semantic_plan": True,
        },
        {
            "status": "needs_input",
            "capability_id": "semantic.planner",
            "stop_reason": "human_interrupt",
            "answer": {"markdown": "어느 항목을 말씀하시는지 하나를 선택해주세요."},
            "answerability": {"status": "insufficient"},
            "artifact_refs": [],
            "plan_ref": "plan-unsafe",
            "semantic_plan_ref": "",
            "used_source_refs": [],
            "citations": [],
            "evidence_refs": [],
        },
    )

    assert evaluated["passed"] is False
    assert evaluated["checks"]["human_interrupt"] is False
