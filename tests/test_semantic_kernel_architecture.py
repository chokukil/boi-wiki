from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from boi_api.app.v2.capabilities import CapabilityRegistry
from boi_api.app.v2.models import LoopContract, LoopKind, SemanticPlan, WorkIntent, WorkOperation
from boi_api.app.v2.semantic_kernel import PlanCompiler, PlanValidator, SemanticPlanningError
from boi_api.app.v2.work_learning import WorkLearningService
from scripts.evaluate_agent_v2_work_scenarios import expand_scenarios


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
