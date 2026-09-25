from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from .capabilities import CapabilityRegistry
from .models import (
    ExecutionPlan,
    GraphQueryDraft,
    OntologyProjectionBinding,
    PlanValidationReport,
    SemanticPlan,
    SemanticPlanV4,
    SemanticSubject,
    TypedCommand,
    ValidationIssue,
    WorkIntent,
    WorkOperation,
)


PLANNER_SCHEMA_REVISION = "semantic-plan/v4"


class SemanticPlanningError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        report: PlanValidationReport | None = None,
        clarification_question: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.report = report
        self.clarification_question = clarification_question


@dataclass(frozen=True)
class CompiledSemanticPlan:
    semantic_plan: SemanticPlan
    work_intent: WorkIntent
    capability_id: str


@dataclass(frozen=True)
class ParsedSemanticPlanV4:
    plan: SemanticPlanV4
    compatibility: dict[str, Any]


@dataclass(frozen=True)
class CompiledSemanticPlanV4:
    semantic_plan: SemanticPlanV4
    execution_plan: ExecutionPlan
    compatibility_plan: SemanticPlan
    work_intent: WorkIntent
    capability_id: str


class PlanValidator:
    """Validate model-owned meaning without changing it or choosing a fallback."""

    _REFERENCE_ONLY_SUBJECTS = {
        "그것",
        "그대상",
        "그항목",
        "그것들",
        "해당것",
        "이것",
        "저것",
        "it",
        "that",
        "this",
        "them",
    }

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    @staticmethod
    def _issue(
        code: str,
        field: str,
        message: str,
        *,
        repairable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            field=field,
            message=message,
            repairable=repairable,
            details=details or {},
        )

    @classmethod
    def _declares_distinct_subject(cls, value: str) -> bool:
        compact_value = "".join(str(value).casefold().split())
        return bool(compact_value and compact_value not in cls._REFERENCE_ONLY_SUBJECTS)

    def validate(
        self,
        plan: SemanticPlan,
        *,
        trusted_context_refs: set[str] | None = None,
        prior_topic_entities: list[str] | None = None,
        prior_focal_entities: list[str] | None = None,
        active_work_run: bool = False,
    ) -> PlanValidationReport:
        issues: list[ValidationIssue] = []
        try:
            definition = self.registry.get(plan.capability_id)
        except KeyError:
            definition = None
            issues.append(
                self._issue(
                    "capability.unknown",
                    "capability_id",
                    "The selected capability is not present in the pinned catalog.",
                )
            )

        if definition is not None:
            if plan.user_effect not in definition.user_effects:
                issues.append(
                    self._issue(
                        "capability.effect_not_allowed",
                        "user_effect",
                        "The selected user effect is not allowed by this capability contract.",
                        details={"allowed": list(definition.user_effects)},
                    )
                )
            if plan.operation not in definition.semantic_operations:
                issues.append(
                    self._issue(
                        "capability.operation_not_allowed",
                        "operation",
                        "The selected operation is not declared by this capability contract.",
                        details={"allowed": [item.value for item in definition.semantic_operations]},
                    )
                )
            operation_contract = definition.semantic_operation_contracts.get(plan.operation)
            if operation_contract is not None and operation_contract.requires_graph and not (
                plan.graph_query and plan.graph_query.enabled
            ):
                issues.append(
                    self._issue(
                        "operation.graph_required",
                        "graph_query",
                        "The selected operation contract requires an explicit graph traversal.",
                        details={"operation": plan.operation.value},
                    )
                )
            if (
                operation_contract is not None
                and operation_contract.presentations
                and plan.presentation not in operation_contract.presentations
            ):
                compatible_operations = [
                    candidate.value
                    for candidate, contract in definition.semantic_operation_contracts.items()
                    if plan.presentation in contract.presentations
                ]
                issues.append(
                    self._issue(
                        "operation.presentation_not_allowed",
                        "operation",
                        "The selected presentation is not declared for this semantic operation.",
                        details={
                            "operation": plan.operation.value,
                            "presentation": plan.presentation,
                            "allowed": list(operation_contract.presentations),
                            "compatible_operations": compatible_operations,
                        },
                    )
                )
            if plan.presentation not in definition.presentations:
                issues.append(
                    self._issue(
                        "capability.presentation_not_allowed",
                        "presentation",
                        "The selected presentation is not declared by this capability contract.",
                        details={"allowed": list(definition.presentations)},
                    )
                )
            if plan.work_view not in definition.work_views:
                issues.append(
                    self._issue(
                        "capability.work_view_not_allowed",
                        "work_view",
                        "The selected work view is not declared by this capability contract.",
                        details={"allowed": list(definition.work_views)},
                    )
                )
            perspective_values = list(plan.work_perspectives)
            perspective_set = set(perspective_values)
            expected_work_view = (
                "combined"
                if perspective_set == {"current", "responsibility"}
                else "current"
                if perspective_set == {"current"}
                else "responsibility"
                if perspective_set == {"responsibility"}
                else "none"
            )
            if len(perspective_values) != len(perspective_set):
                issues.append(
                    self._issue(
                        "work_view.duplicate_perspective",
                        "work_perspectives",
                        "Each requested workplace perspective may appear only once.",
                    )
                )
            if plan.work_view != expected_work_view:
                compatible_contracts = []
                for candidate in self.registry.all():
                    if expected_work_view not in candidate.work_views:
                        continue
                    if plan.user_effect not in candidate.user_effects:
                        continue
                    if plan.presentation not in candidate.presentations:
                        continue
                    if plan.evidence_scope not in candidate.evidence_scopes:
                        continue
                    candidate_operations = list(
                        candidate.work_view_operation_contracts.get(expected_work_view) or []
                    )
                    if not candidate_operations:
                        candidate_operations = list(candidate.semantic_operations)
                    compatible_operations = []
                    for candidate_operation in candidate_operations:
                        candidate_contract = candidate.semantic_operation_contracts.get(
                            candidate_operation
                        )
                        if (
                            candidate_contract is not None
                            and candidate_contract.presentations
                            and plan.presentation not in candidate_contract.presentations
                        ):
                            continue
                        if expected_work_view in {"responsibility", "combined"} and (
                            candidate_contract is None
                            or "responsibility" not in candidate_contract.graph_query_kinds
                        ):
                            continue
                        compatible_operations.append(candidate_operation.value)
                    if compatible_operations:
                        compatible_contracts.append(
                            {
                                "capability_id": candidate.capability_id,
                                "operations": compatible_operations,
                                "graph_query_kind": (
                                    "responsibility"
                                    if expected_work_view in {"responsibility", "combined"}
                                    else ""
                                ),
                            }
                        )
                issues.append(
                    self._issue(
                        "work_view.perspectives_mismatch",
                        "work_view",
                        "work_view must be the exact aggregate of the independently requested workplace perspectives.",
                        details={
                            "work_perspectives": perspective_values,
                            "allowed": [expected_work_view],
                            "compatible_contracts": compatible_contracts,
                        },
                    )
                )
            work_view_operations = definition.work_view_operation_contracts.get(plan.work_view) or []
            if work_view_operations and plan.operation not in work_view_operations:
                issues.append(
                    self._issue(
                        "work_view.operation_not_allowed",
                        "operation",
                        "The selected operation is not declared for this work view.",
                        details={
                            "work_view": plan.work_view,
                            "operation": plan.operation.value,
                            "allowed": [item.value for item in work_view_operations],
                        },
                    )
                )
            if plan.evidence_scope not in definition.evidence_scopes:
                issues.append(
                    self._issue(
                        "capability.evidence_scope_not_allowed",
                        "evidence_scope",
                        "The selected evidence scope is not declared by this capability contract.",
                        details={"allowed": list(definition.evidence_scopes)},
                    )
                )
            if plan.loop_contract.kind not in definition.allowed_loop_kinds:
                issues.append(
                    self._issue(
                        "loop.kind_not_allowed",
                        "loop_contract.kind",
                        "The selected loop kind is not declared by this capability contract.",
                        details={"allowed": [item.value for item in definition.allowed_loop_kinds]},
                    )
                )
            if plan.loop_contract.trigger not in definition.allowed_loop_triggers:
                issues.append(
                    self._issue(
                        "loop.trigger_not_allowed",
                        "loop_contract.trigger",
                        "The selected loop trigger is not declared by this capability contract.",
                        details={"allowed": [item.value for item in definition.allowed_loop_triggers]},
                    )
                )
            default_loop = definition.default_loop_contract
            if plan.loop_contract.kind.value == "turn":
                if plan.loop_contract.max_model_calls > default_loop.max_model_calls:
                    issues.append(
                        self._issue(
                            "loop.model_call_budget_exceeded",
                            "loop_contract.max_model_calls",
                            "A bounded turn cannot exceed the catalog model-call ceiling.",
                            details={"maximum": default_loop.max_model_calls},
                        )
                    )
                if default_loop.max_context_tokens > 0 and (
                    plan.loop_contract.max_context_tokens == 0
                    or plan.loop_contract.max_context_tokens > default_loop.max_context_tokens
                ):
                    issues.append(
                        self._issue(
                            "loop.context_budget_exceeded",
                            "loop_contract.max_context_tokens",
                            "A bounded turn cannot request an unbounded or larger context than the catalog contract.",
                            details={"maximum": default_loop.max_context_tokens},
                        )
                    )
            if plan.loop_contract.kind.value == "goal" and not plan.loop_contract.exit_criteria_refs:
                issues.append(
                    self._issue(
                        "loop.exit_criteria_required",
                        "loop_contract.exit_criteria_refs",
                        "A goal loop needs catalog-backed, verifiable exit criteria.",
                    )
                )
            if definition.subject_policy == "required" and not plan.subjects:
                issues.append(
                    self._issue(
                        "subject.required",
                        "subjects",
                        "This capability needs at least one explicit subject.",
                    )
                )
            if definition.subject_policy == "target_required" and not (
                plan.target_ref or any(item.entity_ref for item in plan.subjects)
            ):
                issues.append(
                    self._issue(
                        "subject.target_required",
                        "target_ref",
                        "This capability needs a resolved target before it can run.",
                    )
                )
            supported_subject_kinds = set(definition.subject_kinds) or {
                item.value for item in definition.supported_assets
            }
            unsupported_subjects = [
                {
                    "mention": item.mention,
                    "entity_ref": item.entity_ref,
                    "entity_kind": item.entity_kind,
                }
                for item in plan.subjects
                if item.entity_kind and item.entity_kind not in supported_subject_kinds
            ]
            if unsupported_subjects:
                issues.append(
                    self._issue(
                        "subject.kind_not_supported",
                        "subjects",
                        "The resolved subject kind is not declared by this capability contract.",
                        details={
                            "supported": sorted(supported_subject_kinds),
                            "subjects": unsupported_subjects[:20],
                        },
                    )
                )

        if plan.topic_action == "clarify" and not plan.clarification_question:
            issues.append(
                self._issue(
                    "topic.clarification_missing",
                    "clarification_question",
                    "An ambiguous plan must contain one focused clarification question.",
                )
            )
        if plan.topic_action != "clarify" and not plan.retrieval_query.strip():
            issues.append(
                self._issue(
                    "retrieval.query_required",
                    "retrieval_query",
                    "An executable semantic plan needs a standalone retrieval query.",
                )
            )
        prior_refs = {str(item).strip() for item in prior_topic_entities or [] if str(item).strip()}
        focal_refs = {
            str(item).strip()
            for item in (
                prior_focal_entities
                if prior_focal_entities is not None
                else prior_topic_entities or []
            )
            if str(item).strip()
        }
        resolved_subject_refs = {
            item.entity_ref.strip()
            for item in plan.subjects
            if item.entity_ref.strip()
        }
        if plan.topic_action == "clarify" and not prior_refs:
            issues.append(
                self._issue(
                    "topic.clarification_prior_state_missing",
                    "topic_action",
                    "A discourse-reference clarification requires verified prior topic state.",
                    details={"allowed": ["new"]},
                )
            )
        subject_ref_rows = [item.entity_ref.strip() for item in plan.subjects if item.entity_ref.strip()]
        duplicate_subject_refs = sorted(
            {item for item in subject_ref_rows if subject_ref_rows.count(item) > 1}
        )
        if duplicate_subject_refs:
            issues.append(
                self._issue(
                    "subject.duplicate_ref",
                    "subjects",
                    "Each resolved subject identity may appear only once in a semantic plan.",
                    details={"refs": duplicate_subject_refs},
                )
            )
        inherited_refs = prior_refs & resolved_subject_refs
        if plan.topic_action == "new" and plan.reference_resolution != "none":
            issues.append(
                self._issue(
                    "topic.new_reference_resolution",
                    "reference_resolution",
                    "A new topic must not claim to resolve a prior reference.",
                )
            )
        if plan.topic_action == "clarify" and plan.reference_resolution != "ambiguous":
            issues.append(
                self._issue(
                    "topic.clarification_resolution_mismatch",
                    "reference_resolution",
                    "A clarification must identify the prior reference as ambiguous.",
                )
            )
        if plan.topic_action == "continue" and plan.reference_resolution not in {"all", "specific"}:
            issues.append(
                self._issue(
                    "topic.continuation_resolution_missing",
                    "reference_resolution",
                    "A continued topic must state whether it selects all or one specific prior subject.",
                )
            )
        if plan.reference_resolution == "ambiguous" and plan.topic_action != "clarify":
            issues.append(
                self._issue(
                    "topic.ambiguous_reference_requires_clarification",
                    "topic_action",
                    "An ambiguous prior reference requires one clarification question.",
                )
            )
        if (
            plan.topic_action == "continue"
            and plan.reference_resolution == "specific"
            and prior_refs
            and len(inherited_refs) != 1
        ):
            issues.append(
                self._issue(
                    "topic.specific_reference_cardinality",
                    "subjects",
                    "A specific continuation must retain exactly one verified prior subject.",
                    details={"prior": sorted(prior_refs), "selected": sorted(inherited_refs)},
                )
            )
        if (
            plan.topic_action == "continue"
            and plan.reference_resolution == "all"
            and focal_refs
            and not focal_refs.issubset(inherited_refs)
        ):
            issues.append(
                self._issue(
                    "topic.all_reference_incomplete",
                    "subjects",
                    "An all-subject continuation must retain every verified prior subject.",
                    details={"prior": sorted(focal_refs), "selected": sorted(inherited_refs)},
                )
            )
        if plan.topic_action == "continue" and not prior_refs:
            issues.append(
                self._issue(
                    "topic.prior_state_missing",
                    "topic_action",
                    "The plan cannot continue a topic that has no verified prior entity state.",
                )
            )
        if plan.topic_action == "continue" and not resolved_subject_refs:
            issues.append(
                self._issue(
                    "topic.subject_not_resolved",
                    "subjects",
                    "A follow-up must resolve its inherited subject in the standalone plan.",
                )
            )
        has_declared_subject = bool(
            resolved_subject_refs
            or any(self._declares_distinct_subject(item.mention) for item in plan.subjects)
        )
        if plan.topic_action == "new" and prior_refs and not has_declared_subject:
            issues.append(
                self._issue(
                    "topic.new_subject_not_resolved",
                    "subjects",
                    "A new topic in an existing session must declare its distinct subject.",
                    details={"prior": sorted(prior_refs)},
                )
            )
        inherited_focal_refs = focal_refs & resolved_subject_refs
        if (
            plan.topic_action == "new"
            and inherited_focal_refs
            and resolved_subject_refs.issubset(focal_refs)
        ):
            issues.append(
                self._issue(
                    "topic.new_reuses_prior_subject",
                    "topic_action",
                    "A new topic cannot consist only of the verified prior focal subject set.",
                    details={"overlap": sorted(inherited_focal_refs)},
                )
            )
        if plan.topic_action == "continue" and prior_refs and resolved_subject_refs and not inherited_refs:
            issues.append(
                self._issue(
                    "topic.continuation_subject_mismatch",
                    "subjects",
                    "A continued topic must retain at least one verified prior subject.",
                    details={
                        "prior": sorted(prior_refs),
                        "selected": sorted(resolved_subject_refs),
                    },
                )
            )
        if plan.target_ref and resolved_subject_refs and plan.target_ref not in resolved_subject_refs:
            issues.append(
                self._issue(
                    "subject.target_mismatch",
                    "target_ref",
                    "The target ref must identify one of the plan's resolved subjects.",
                    details={
                        "target_ref": plan.target_ref,
                        "subject_refs": sorted(resolved_subject_refs),
                    },
                )
            )

        trusted_refs = trusted_context_refs if trusted_context_refs is not None else set()
        untrusted_refs = [item for item in plan.context_refs if item not in trusted_refs]
        if untrusted_refs:
            issues.append(
                self._issue(
                    "context.untrusted_ref",
                    "context_refs",
                    "The plan selected context refs that were not supplied to the planner.",
                    details={"refs": untrusted_refs[:20]},
                )
            )
        untrusted_subject_refs = [
            item.entity_ref
            for item in plan.subjects
            if item.entity_ref and item.entity_ref not in trusted_refs
        ]
        if plan.target_ref and plan.target_ref not in trusted_refs:
            untrusted_subject_refs.append(plan.target_ref)
        if untrusted_subject_refs:
            issues.append(
                self._issue(
                    "subject.untrusted_ref",
                    "subjects",
                    "Resolved subject refs must come from ACL-visible planner context.",
                    details={"refs": list(dict.fromkeys(untrusted_subject_refs))[:20]},
                )
            )

        graph = plan.graph_query
        if plan.presentation == "explorer" and not (graph and graph.enabled):
            issues.append(
                self._issue(
                    "graph.required_for_explorer",
                    "graph_query",
                    "Explorer presentation requires an explicit graph query plan.",
                )
            )
        if graph and graph.enabled:
            if not graph.focal_mentions:
                issues.append(
                    self._issue(
                        "graph.focal_subject_missing",
                        "graph_query.focal_mentions",
                        "A graph traversal needs at least one focal subject.",
                    )
                )
            if definition is not None and graph.query_kind not in definition.graph_query_kinds:
                issues.append(
                    self._issue(
                        "graph.query_not_allowed",
                        "graph_query.query_kind",
                        "The graph query kind is not declared by this capability contract.",
                        details={"allowed": list(definition.graph_query_kinds)},
                    )
                )
            if definition is not None and definition.semantic_operation_contracts:
                operation_contract = definition.semantic_operation_contracts.get(plan.operation)
                if (
                    operation_contract is not None
                    and graph.query_kind not in operation_contract.graph_query_kinds
                ):
                    issues.append(
                        self._issue(
                            "operation.graph_query_not_allowed",
                            "operation",
                            "The selected graph traversal is not declared for this semantic operation.",
                            details={
                                "operation": plan.operation.value,
                                "query_kind": graph.query_kind,
                                "allowed": list(operation_contract.graph_query_kinds),
                            },
                        )
                    )
            filter_contract = self.registry.graph_query_filter_contract
            unknown_node_kinds = sorted(set(graph.node_kinds) - set(filter_contract.node_kinds))
            if unknown_node_kinds:
                issues.append(
                    self._issue(
                        "graph.node_kind_unknown",
                        "graph_query.node_kinds",
                        "Graph node filters must come from the pinned ontology filter contract.",
                        details={"unknown": unknown_node_kinds, "allowed": filter_contract.node_kinds},
                    )
                )
            unknown_relation_kinds = sorted(set(graph.relation_kinds) - set(filter_contract.relation_kinds))
            if unknown_relation_kinds:
                issues.append(
                    self._issue(
                        "graph.relation_kind_unknown",
                        "graph_query.relation_kinds",
                        "Graph relation filters must come from the pinned ontology filter contract.",
                        details={"unknown": unknown_relation_kinds, "allowed": filter_contract.relation_kinds},
                    )
                )

        if plan.user_effect == "read" and plan.operation in {
            WorkOperation.create,
            WorkOperation.refine,
            WorkOperation.run,
            WorkOperation.complete,
            WorkOperation.capture,
            WorkOperation.promote,
        }:
            issues.append(
                self._issue(
                    "effect.operation_conflict",
                    "operation",
                    "A read-only request cannot compile to a changing operation.",
                )
            )
        if plan.user_effect == "execute" and plan.operation not in {
            WorkOperation.run,
            WorkOperation.test,
            WorkOperation.complete,
            WorkOperation.promote,
        }:
            issues.append(
                self._issue(
                    "effect.execute_operation_required",
                    "operation",
                    "An execute effect needs an execution operation.",
                )
            )

        continuation = plan.continuation
        record_has_content = any(
            value
            for value in continuation.work_record.model_dump(mode="python").values()
        )
        if continuation.continue_active_run:
            if not active_work_run:
                issues.append(
                    self._issue(
                        "continuation.active_run_missing",
                        "continuation.continue_active_run",
                        "A continuation requires an ACL-visible active WorkRun.",
                    )
                )
            if plan.topic_action != "continue":
                issues.append(
                    self._issue(
                        "continuation.topic_mismatch",
                        "topic_action",
                        "Continuing a WorkRun requires the verified prior topic to be continued.",
                    )
                )
            if plan.user_effect == "read":
                issues.append(
                    self._issue(
                        "continuation.read_effect_forbidden",
                        "user_effect",
                        "A read-only plan cannot append progress to a WorkRun.",
                    )
                )
            if continuation.delta_kind == "none":
                issues.append(
                    self._issue(
                        "continuation.delta_required",
                        "continuation.delta_kind",
                        "A WorkRun continuation must declare the progress delta kind.",
                    )
                )
            if continuation.user_confirmation and continuation.delta_kind != "human_input":
                issues.append(
                    self._issue(
                        "continuation.confirmation_mismatch",
                        "continuation.user_confirmation",
                        "Human confirmation is valid only for a human input delta.",
                    )
                )
        elif continuation.delta_kind != "none" or continuation.user_confirmation or record_has_content:
            issues.append(
                self._issue(
                    "continuation.inactive_payload",
                    "continuation",
                    "Continuation details cannot be supplied when no active WorkRun is continued.",
                )
            )

        return PlanValidationReport(
            valid=not any(item.severity == "error" for item in issues),
            issues=issues,
            catalog_revision=self.registry.version,
            planner_schema_revision=PLANNER_SCHEMA_REVISION,
        )


class PlanCompiler:
    """Compile a validated SemanticPlan without changing its semantic selections."""

    _effect_purpose = {
        "read": "explain",
        "draft": "design",
        "transform": "transform",
        "execute": "execute",
    }
    _effect_transition = {
        "read": "none",
        "draft": "draft",
        "transform": "transform",
        "execute": "execute",
    }

    def __init__(self, registry: CapabilityRegistry, validator: PlanValidator | None = None):
        self.registry = registry
        self.validator = validator or PlanValidator(registry)

    @staticmethod
    def _pipeline(plan: SemanticPlan, definition: Any) -> list[WorkOperation]:
        selected = list((definition.operation_pipelines or {}).get(plan.operation.value) or [])
        if selected:
            return list(dict.fromkeys(selected))
        declared = list(definition.operation_pipeline or [])
        if not declared:
            return [plan.operation]
        default = definition.default_operation
        values = [plan.operation if default is not None and item == default else item for item in declared]
        if plan.operation not in values:
            values.append(plan.operation)
        return list(dict.fromkeys(values))

    def compile(
        self,
        plan: SemanticPlan,
        *,
        original_question: str,
        trusted_context_refs: set[str] | None = None,
        prior_topic_entities: list[str] | None = None,
        prior_focal_entities: list[str] | None = None,
        active_work_run: bool = False,
    ) -> CompiledSemanticPlan:
        report = self.validator.validate(
            plan,
            trusted_context_refs=trusted_context_refs,
            prior_topic_entities=prior_topic_entities,
            prior_focal_entities=prior_focal_entities,
            active_work_run=active_work_run,
        )
        if not report.valid:
            raise SemanticPlanningError("planner_invalid", "Semantic plan did not pass validation.", report=report)
        definition = self.registry.get(plan.capability_id)
        topic_mentions = [item.mention for item in plan.subjects]
        resolved_subject_refs = [item.entity_ref for item in plan.subjects if item.entity_ref]
        topic_entities = [item.entity_ref or item.mention for item in plan.subjects]
        referenceable_topic_entities = list(
            dict.fromkeys(
                [
                    *resolved_subject_refs,
                    *([plan.target_ref] if plan.target_ref else []),
                ]
            )
        )
        if not topic_entities and plan.target_ref:
            # target_ref is an explicit, ACL-validated semantic identity even
            # when an optional-subject capability does not repeat it in
            # subjects. Preserve it for follow-up discourse instead of losing
            # the person, Task, or artifact that the plan actually targeted.
            topic_entities = [plan.target_ref]
        primary_subject = topic_mentions[0] if topic_mentions else ""
        intent = WorkIntent(
            goal=original_question,
            resolved_goal=plan.resolved_goal,
            retrieval_query=plan.retrieval_query,
            answer_intent=plan.answer_intent,
            answer_source_scope=plan.evidence_scope,
            topic_mode=plan.topic_action,
            topic_subject=primary_subject,
            topic_structure="single_focal" if len(topic_entities) <= 1 else "multiple_focal",
            primary_topic_entity=topic_entities[0] if len(topic_entities) == 1 else "",
            topic_entities=topic_entities,
            referenceable_topic_entities=referenceable_topic_entities,
            followup_reference_resolution=plan.reference_resolution,
            selected_prior_topic_entities=(
                referenceable_topic_entities if plan.topic_action == "continue" else []
            ),
            followup_semantic_change=(
                "same_subject_question" if plan.topic_action == "continue" else "new_subject" if plan.topic_action == "new" else "ambiguous_reference"
            ),
            comparison_focal_entities=(
                referenceable_topic_entities if plan.operation == WorkOperation.compare else []
            ),
            relationship_focal_entities=(
                referenceable_topic_entities if plan.operation == WorkOperation.connect else []
            ),
            asset_kind=definition.primary_asset,
            operation=plan.operation,
            operation_plan=self._pipeline(plan, definition),
            target_ref=plan.target_ref or (resolved_subject_refs[0] if resolved_subject_refs else ""),
            scope="selected" if plan.context_refs else "auto",
            desired_outcome=str(definition.output_schema.get("type") or "answer"),
            presentation_mode=plan.presentation,
            work_view=plan.work_view,
            graph_query_draft=plan.graph_query,
            context_refs=plan.context_refs,
            user_effect=plan.user_effect,
            result_purpose=self._effect_purpose[plan.user_effect],
            requested_transition=self._effect_transition[plan.user_effect],
            analysis_depth="deep" if definition.deep else "standard",
            requested_asset_kinds=list(definition.supported_assets),
            harness_ids=list(definition.harness_ids),
            artifact_actions=[],
            loop_contract=plan.loop_contract,
            risk=definition.risk,
            needs_clarification=plan.topic_action == "clarify",
            confidence=plan.confidence,
        )
        return CompiledSemanticPlan(semantic_plan=plan, work_intent=intent, capability_id=plan.capability_id)

    def compile_typed_command(
        self,
        command: TypedCommand,
        *,
        trusted_context_refs: set[str] | None = None,
    ) -> CompiledSemanticPlan:
        definition = self.registry.get(command.capability_id)
        subjects = [
            SemanticSubject(mention=ref, entity_ref=ref, resolution="resolved")
            for ref in command.subject_refs
        ]
        if not subjects and definition.subject_policy == "required":
            subjects = [SemanticSubject(mention=command.goal, resolution="unresolved")]
        plan = SemanticPlan(
            resolved_goal=command.goal,
            retrieval_query=command.goal,
            topic_action="new",
            subjects=subjects,
            capability_id=command.capability_id,
            user_effect=command.user_effect,
            operation=command.operation,
            evidence_scope=definition.default_evidence_scope,
            presentation=command.presentation,
            work_view=command.work_view,
            graph_query=command.graph_query,
            context_refs=command.subject_refs,
            target_ref=command.subject_refs[0] if command.subject_refs else "",
            loop_contract=definition.default_loop_contract,
            confidence=1.0,
        )
        return self.compile(
            plan,
            original_question=command.goal,
            trusted_context_refs=trusted_context_refs if trusted_context_refs is not None else set(command.subject_refs),
            prior_topic_entities=[],
        )

    @staticmethod
    def _work_view_from_perspectives(
        perspectives: list[str],
    ) -> str:
        values = set(perspectives)
        if values == {"current", "responsibility"}:
            return "combined"
        if values == {"current"}:
            return "current"
        if values == {"responsibility"}:
            return "responsibility"
        return "none"

    @staticmethod
    def _answer_intent_for_v4(plan: SemanticPlanV4, work_view: str) -> str:
        if work_view != "none" or plan.operation in {WorkOperation.observe, WorkOperation.complete}:
            return "work"
        if plan.operation == WorkOperation.compare:
            return "comparison"
        if plan.operation == WorkOperation.connect:
            return "relationship"
        if plan.operation in {WorkOperation.create, WorkOperation.refine, WorkOperation.run, WorkOperation.test}:
            return "procedure"
        return "fact"

    @staticmethod
    def _same_capability_continuation(
        plan: SemanticPlanV4,
        definition: Any,
        available_context: set[str] | None = None,
    ) -> bool:
        return bool(
            plan.topic_action == "continue"
            and f"capability:{definition.capability_id}" in (available_context or set())
        )

    @staticmethod
    def _v4_effective_operation(
        plan: SemanticPlanV4,
        definition: Any,
        available_context: set[str] | None = None,
    ) -> WorkOperation:
        """Resolve a catalog-declared operation fallback from typed context.

        This does not inspect the user's wording or choose a capability.  It
        only prevents an operation such as ``refine`` from targeting an
        artifact that does not exist, while keeping the original operation
        whenever its declared context is available.
        """

        available = available_context or set()
        operation = plan.operation
        if PlanCompiler._same_capability_continuation(
            plan,
            definition,
            available_context,
        ):
            operation = definition.semantic_compile.continuation_operation_aliases.get(
                operation,
                operation,
            )
        operation_contract = definition.semantic_operation_contracts.get(operation)
        if (
            operation_contract is not None
            and operation_contract.presentations
            and plan.presentation_intent not in operation_contract.presentations
        ):
            operation = definition.semantic_compile.presentation_operation_aliases.get(
                plan.presentation_intent,
                operation,
            )
        visited: set[WorkOperation] = set()
        while operation not in visited:
            visited.add(operation)
            contract = definition.semantic_operation_contracts.get(operation)
            if contract is None or set(contract.required_context).issubset(available):
                return operation
            fallback = contract.fallback_operation
            if fallback is None or fallback not in definition.semantic_operations:
                return operation
            operation = fallback
        return plan.operation

    @staticmethod
    def _v4_catalog_evidence_modes(
        plan: SemanticPlanV4,
        definition: Any,
        operation: WorkOperation,
        available_context: set[str] | None = None,
    ) -> list[str]:
        """Normalize model evidence vocabulary through typed Catalog data."""

        aliases = dict(
            definition.semantic_compile.evidence_mode_aliases_by_operation.get(
                operation,
                {},
            )
        )
        if PlanCompiler._same_capability_continuation(
            plan,
            definition,
            available_context,
        ):
            aliases.update(
                definition.semantic_compile.continuation_evidence_mode_aliases_by_operation.get(
                    operation,
                    {},
                )
            )
        return list(
            dict.fromkeys(
                aliases.get(mode, mode)
                for mode in plan.evidence_requirements.modes
                if mode
            )
        )

    @staticmethod
    def _v4_candidate_mismatches(
        plan: SemanticPlanV4,
        definition: Any,
        work_view: str,
        available_context: set[str] | None = None,
    ) -> set[str]:
        mismatches: set[str] = set()
        contract = definition.semantic_compile
        effective_operation = PlanCompiler._v4_effective_operation(
            plan,
            definition,
            available_context,
        )
        if plan.user_effect not in definition.user_effects:
            mismatches.add("user_effect")
        if effective_operation not in definition.semantic_operations:
            mismatches.add("operation")
        if plan.presentation_intent not in definition.presentations:
            mismatches.add("presentation_intent")
        if (
            plan.result_asset_kind is not None
            and plan.result_asset_kind not in definition.supported_assets
        ):
            mismatches.add("result_asset_kind")
        operation_contract = definition.semantic_operation_contracts.get(effective_operation)
        if (
            operation_contract is not None
            and operation_contract.presentations
            and plan.presentation_intent not in operation_contract.presentations
        ):
            mismatches.add("operation_presentation")
        requested_operation_contract = definition.semantic_operation_contracts.get(
            plan.operation
        )
        if (
            requested_operation_contract is not None
            and not set(requested_operation_contract.required_context).issubset(
                available_context or set()
            )
            and effective_operation == plan.operation
        ):
            mismatches.add("required_context")
        if work_view not in definition.work_views:
            mismatches.add("work_perspectives")
        if contract.mutation_intents and plan.mutation_intent not in contract.mutation_intents:
            mismatches.add("mutation_intent")
        if contract.loop_intents and plan.loop_intent not in contract.loop_intents:
            mismatches.add("loop_intent")
        if not set(contract.required_context).issubset(available_context or set()):
            mismatches.add("required_context")
        requested_perspectives = set(plan.work_perspectives)
        compile_perspectives = set(contract.work_perspectives)
        if requested_perspectives and not requested_perspectives.issubset(compile_perspectives):
            mismatches.add("work_perspectives")
        resolved_subjects = {
            item.entity_ref
            for item in plan.subjects
            if item.resolution == "resolved" and item.entity_ref
        }
        resolved_subject_kinds = {
            item.entity_kind
            for item in plan.subjects
            if item.entity_kind
            and item.resolution == "resolved"
            and item.entity_ref
        }
        # A planner may retain an unresolved generic label alongside an
        # already resolved subject (for example a Person plus "assigned
        # Task"). That label is useful for clarification and retrieval, but it
        # is not a verified ontology identity and must not veto the Catalog
        # contract selected by the resolved subject. When nothing resolved we
        # still use the declared kinds so an unresolved-only request can be
        # bounded by the Catalog and interrupted safely downstream.
        subject_kinds = resolved_subject_kinds or {
            item.entity_kind for item in plan.subjects if item.entity_kind
        }
        if definition.subject_policy == "required" and not plan.subjects:
            mismatches.add("subjects")
        if definition.subject_policy == "target_required" and not resolved_subjects:
            mismatches.add("subjects")
        if subject_kinds and not subject_kinds.issubset(set(definition.subject_kinds)):
            mismatches.add("subjects")
        evidence_modes = set(
            PlanCompiler._v4_catalog_evidence_modes(
                plan,
                definition,
                effective_operation,
                available_context,
            )
        )
        accepted_evidence_modes = {
            *contract.evidence_modes,
            *contract.evidence_modes_by_operation.get(effective_operation, []),
        }
        if PlanCompiler._same_capability_continuation(
            plan,
            definition,
            available_context,
        ):
            accepted_evidence_modes.update(contract.continuation_evidence_modes)
        if (
            evidence_modes
            and accepted_evidence_modes
            and not evidence_modes.intersection(accepted_evidence_modes)
        ):
            mismatches.add("evidence_requirements.modes")
        return mismatches

    @classmethod
    def _v4_candidate_matches(
        cls,
        plan: SemanticPlanV4,
        definition: Any,
        work_view: str,
        available_context: set[str] | None = None,
    ) -> bool:
        return not cls._v4_candidate_mismatches(
            plan,
            definition,
            work_view,
            available_context,
        )

    @staticmethod
    def _work_perspective_options(definition: Any) -> list[list[str]]:
        options = {
            "none": [],
            "current": ["current"],
            "responsibility": ["responsibility"],
            "combined": ["current", "responsibility"],
        }
        return [options[item] for item in definition.work_views if item in options]

    @classmethod
    def _v4_near_match_contracts(
        cls,
        plan: SemanticPlanV4,
        definitions: list[Any],
        work_view: str,
        available_context: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        ranked: list[tuple[int, int, int, int, int, str, Any, set[str]]] = []
        for definition in definitions:
            mismatches = cls._v4_candidate_mismatches(
                plan,
                definition,
                work_view,
                available_context,
            )
            score = cls._v4_candidate_score(
                plan,
                definition,
                available_context,
            )
            ranked.append(
                (
                    len(mismatches),
                    -score[0],
                    -score[1],
                    -score[2],
                    -score[3],
                    definition.capability_id,
                    definition,
                    mismatches,
                )
            )
        alternatives: list[dict[str, Any]] = []
        fingerprints: set[str] = set()
        for _, _, _, _, _, _, definition, mismatches in sorted(ranked):
            allowed: dict[str, Any] = {}
            contract = definition.semantic_compile
            if "user_effect" in mismatches:
                allowed["user_effect"] = list(definition.user_effects)
            if "operation" in mismatches:
                allowed["operation"] = [item.value for item in definition.semantic_operations]
            if "presentation_intent" in mismatches or "operation_presentation" in mismatches:
                operation_contract = definition.semantic_operation_contracts.get(plan.operation)
                allowed["presentation_intent"] = list(
                    operation_contract.presentations
                    if operation_contract and operation_contract.presentations
                    else definition.presentations
                )
            if "result_asset_kind" in mismatches:
                allowed["result_asset_kind"] = [
                    item.value for item in definition.supported_assets
                ]
            if "work_perspectives" in mismatches:
                allowed["work_perspectives"] = cls._work_perspective_options(definition)
            if "mutation_intent" in mismatches:
                allowed["mutation_intent"] = list(contract.mutation_intents)
            if "loop_intent" in mismatches:
                allowed["loop_intent"] = list(contract.loop_intents)
            if "subjects" in mismatches:
                allowed["subject_kinds"] = list(definition.subject_kinds)
            if "evidence_requirements.modes" in mismatches:
                allowed["evidence_requirements.modes"] = list(contract.evidence_modes)
            if "required_context" in mismatches:
                allowed["required_context"] = list(contract.required_context)
            alternative = {
                "mismatch_fields": sorted(mismatches),
                "allowed_meaning_values": allowed,
            }
            fingerprint = json.dumps(alternative, ensure_ascii=False, sort_keys=True)
            if fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            alternatives.append(alternative)
            if len(alternatives) >= 4:
                break
        return alternatives

    @staticmethod
    def _v4_candidate_score(
        plan: SemanticPlanV4,
        definition: Any,
        available_context: set[str] | None = None,
    ) -> tuple[int, int, int, int, str]:
        contract = definition.semantic_compile
        subject_kinds = {item.entity_kind for item in plan.subjects if item.entity_kind}
        preferred = set(contract.preferred_subject_kinds)
        effective_operation = PlanCompiler._v4_effective_operation(
            plan,
            definition,
            available_context,
        )
        evidence_modes = set(
            PlanCompiler._v4_catalog_evidence_modes(
                plan,
                definition,
                effective_operation,
                available_context,
            )
        )
        accepted_evidence_modes = {
            *contract.evidence_modes,
            *contract.evidence_modes_by_operation.get(effective_operation, []),
        }
        return (
            # For a draft/transform request, the requested result asset is the
            # output contract. Prefer the Catalog definition whose primary
            # asset is that exact result before a broader transform capability
            # that merely accepts the same source asset. Read requests keep
            # evidence mode as their strongest discriminator below.
            int(
                plan.user_effect in {"draft", "transform"}
                and plan.result_asset_kind is not None
                and plan.result_asset_kind == definition.primary_asset
            ),
            # Evidence mode is the strongest typed discriminator between a
            # generic knowledge answer and a domain read such as reviewed case
            # history. A broad result asset must not override that evidence
            # contract when the model emits both.
            len(evidence_modes & accepted_evidence_modes),
            # For read requests the subject/evidence domain is more specific
            # than a broad result container such as `knowledge`.  Otherwise a
            # generic knowledge capability can hide a typed case, work, or
            # ontology contract merely because the planner described the
            # reusable result as knowledge.
            len(subject_kinds & preferred),
            int(contract.priority),
            int(
                plan.result_asset_kind is not None
                and plan.result_asset_kind == definition.primary_asset
            ),
            # Reverse lexical order is not used as a semantic decision. It is a
            # stable final key only after all typed catalog dimensions tie.
            definition.capability_id,
        )

    def validate_v4(
        self,
        plan: SemanticPlanV4,
        *,
        trusted_context_refs: set[str] | None = None,
        prior_topic_entities: list[str] | None = None,
        prior_focal_entities: list[str] | None = None,
        active_work_run: bool = False,
    ) -> PlanValidationReport:
        issues: list[ValidationIssue] = []

        def issue(code: str, field: str, message: str, **details: Any) -> None:
            issues.append(
                ValidationIssue(
                    code=code,
                    field=field,
                    message=message,
                    details=details,
                )
            )

        if plan.topic_action == "clarify":
            if plan.reference_resolution != "ambiguous":
                issue(
                    "topic.clarification_resolution_mismatch",
                    "reference_resolution",
                    "A clarification must mark the prior reference ambiguous.",
                )
            if not plan.clarification_question.strip():
                issue(
                    "topic.clarification_missing",
                    "clarification_question",
                    "A clarification needs one focused question.",
                )
        elif not plan.retrieval_query.strip():
            issue(
                "retrieval.query_required",
                "retrieval_query",
                "An executable meaning plan needs a standalone retrieval query.",
            )
        if plan.evidence_requirements.as_of:
            try:
                datetime.fromisoformat(
                    plan.evidence_requirements.as_of.replace("Z", "+00:00")
                )
            except ValueError:
                issue(
                    "evidence.as_of_invalid",
                    "evidence_requirements.as_of",
                    "The evidence as_of value must be an ISO-8601 date or datetime.",
                )
        prior_refs = {str(item) for item in prior_topic_entities or [] if str(item)}
        focal_refs = {
            str(item)
            for item in (
                prior_focal_entities
                if prior_focal_entities is not None
                else prior_topic_entities or []
            )
            if str(item)
        }
        resolved_refs = {
            item.entity_ref for item in plan.subjects if item.entity_ref and item.resolution == "resolved"
        }
        inherited = prior_refs & resolved_refs
        if plan.topic_action == "new" and plan.reference_resolution != "none":
            issue(
                "topic.new_reference_resolution",
                "reference_resolution",
                "A new topic cannot resolve a prior reference.",
            )
        if plan.topic_action == "continue":
            if not prior_refs:
                issue(
                    "topic.prior_state_missing",
                    "topic_action",
                    "A continuation requires verified prior topic state.",
                )
            if plan.reference_resolution not in {"all", "specific"}:
                issue(
                    "topic.continuation_resolution_missing",
                    "reference_resolution",
                    "A continuation must select all or one specific prior subject.",
                )
            if not resolved_refs:
                issue(
                    "topic.subject_not_resolved",
                    "subjects",
                    "A continuation must retain a verified subject identity.",
                )
            if plan.reference_resolution == "specific" and prior_refs and len(inherited) != 1:
                issue(
                    "topic.specific_reference_cardinality",
                    "subjects",
                    "A specific continuation must retain exactly one prior identity.",
                    selected=sorted(inherited),
                )
            if plan.reference_resolution == "all" and focal_refs and not focal_refs.issubset(inherited):
                issue(
                    "topic.all_reference_incomplete",
                    "subjects",
                    "An all-subject continuation must retain every focal identity.",
                    selected=sorted(inherited),
                )
        trusted = trusted_context_refs if trusted_context_refs is not None else set()
        untrusted = sorted(ref for ref in resolved_refs if ref not in trusted)
        if untrusted:
            issue(
                "subject.untrusted_ref",
                "subjects",
                "Resolved identities must come from ACL-visible planner context.",
                refs=untrusted,
            )
        if len(plan.work_perspectives) != len(set(plan.work_perspectives)):
            issue(
                "work_perspectives.duplicate",
                "work_perspectives",
                "A workplace perspective may appear only once.",
            )
        expected_mutations = {
            "read": {"none"},
            "draft": {"private_draft"},
            "transform": {"transform_preview"},
            "execute": {"execute", "activate", "promote"},
        }
        if plan.mutation_intent not in expected_mutations[plan.user_effect]:
            issue(
                "effect.mutation_conflict",
                "mutation_intent",
                "Mutation intent must preserve the explicitly requested user effect.",
                actual=plan.mutation_intent,
                allowed=sorted(expected_mutations[plan.user_effect]),
            )
        if plan.user_effect == "read" and plan.operation in {
            WorkOperation.create,
            WorkOperation.refine,
            WorkOperation.run,
            WorkOperation.complete,
            WorkOperation.capture,
            WorkOperation.promote,
        }:
            issue(
                "effect.operation_conflict",
                "operation",
                "A read request cannot compile to a changing operation.",
            )
        continuation = plan.continuation_delta
        has_delta = continuation.continue_active_run or continuation.delta_kind != "none"
        if has_delta and not active_work_run:
            issue(
                "continuation.active_run_missing",
                "continuation_delta",
                "A WorkRun continuation requires an ACL-visible active run.",
            )
        return PlanValidationReport(
            valid=not issues,
            issues=issues,
            catalog_revision=self.registry.version,
            planner_schema_revision=PLANNER_SCHEMA_REVISION,
        )

    def compile_v4(
        self,
        parsed: ParsedSemanticPlanV4 | SemanticPlanV4,
        *,
        original_question: str,
        trusted_context_refs: set[str] | None = None,
        prior_topic_entities: list[str] | None = None,
        prior_focal_entities: list[str] | None = None,
        active_work_run: bool = False,
        available_context: set[str] | None = None,
    ) -> CompiledSemanticPlanV4:
        parsed_plan = (
            parsed
            if isinstance(parsed, ParsedSemanticPlanV4)
            else ParsedSemanticPlanV4(plan=parsed, compatibility={})
        )
        plan = parsed_plan.plan
        report = self.validate_v4(
            plan,
            trusted_context_refs=trusted_context_refs,
            prior_topic_entities=prior_topic_entities,
            prior_focal_entities=prior_focal_entities,
            active_work_run=active_work_run,
        )
        if not report.valid:
            raise SemanticPlanningError(
                "planner_invalid",
                "SemanticPlanV4 did not pass meaning validation.",
                report=report,
                clarification_question=plan.clarification_question,
            )
        work_view = self._work_view_from_perspectives(plan.work_perspectives)
        candidates = [
            definition
            for definition in self.registry.all()
            if self._v4_candidate_matches(
                plan,
                definition,
                work_view,
                available_context,
            )
        ]
        legacy_hint = str(parsed_plan.compatibility.get("capability_id") or "")
        definition = None
        if legacy_hint:
            try:
                hinted = self.registry.get(legacy_hint)
            except KeyError:
                hinted = None
            hinted_operation = (
                self._v4_effective_operation(plan, hinted, available_context)
                if hinted is not None
                else plan.operation
            )
            if (
                hinted is not None
                and plan.user_effect in hinted.user_effects
                and hinted_operation in hinted.semantic_operations
                and plan.presentation_intent in hinted.presentations
                and work_view in hinted.work_views
                and set(hinted.semantic_compile.required_context).issubset(
                    available_context or set()
                )
            ):
                # Persisted V3 and verified starter commands carry an explicit
                # compatibility capability. Preserve that boundary here and
                # let the legacy compiler report its detailed subject/evidence
                # contract violations. Only a real runtime-context precondition
                # may make the hinted handler ineligible before compilation.
                definition = hinted
        if definition is None:
            continuation_candidates = [
                item
                for item in candidates
                if self._same_capability_continuation(
                    plan,
                    item,
                    available_context,
                )
            ]
            if (
                plan.user_effect == "transform"
                and plan.result_asset_kind is not None
            ):
                # A transform's destination is a cross-asset contract. The
                # active artifact and origin capability remain inputs, but an
                # origin whose primary asset differs from the destination must
                # not pin compilation merely because it broadly accepts that
                # asset. If no destination-primary continuation exists, the
                # normal typed Catalog ranking selects the transform handler.
                continuation_candidates = [
                    item
                    for item in continuation_candidates
                    if item.primary_asset == plan.result_asset_kind
                ]
            elif plan.result_asset_kind is not None and any(
                item.primary_asset == plan.result_asset_kind for item in candidates
            ):
                continuation_candidates = [
                    item
                    for item in continuation_candidates
                    if item.primary_asset == plan.result_asset_kind
                ]
            if len(continuation_candidates) == 1:
                # A verified topic continuation keeps its originating Catalog
                # contract whenever that contract still accepts the complete
                # typed meaning. Cross-capability transforms remain possible
                # because an incompatible origin is absent from candidates.
                definition = continuation_candidates[0]
        if definition is None:
            ranked = sorted(
                candidates,
                key=lambda item: self._v4_candidate_score(
                    plan,
                    item,
                    available_context,
                ),
                reverse=True,
            )
            if not ranked:
                near_match_contracts = self._v4_near_match_contracts(
                    plan,
                    self.registry.all(),
                    work_view,
                    available_context,
                )
                raise SemanticPlanningError(
                    "catalog_no_match",
                    "No Capability Catalog entry matches the validated meaning contract.",
                    report=PlanValidationReport(
                        valid=False,
                        issues=[
                            ValidationIssue(
                                code="catalog.no_match",
                                field="semantic_plan",
                                message=(
                                    "No catalog compile contract accepts the complete typed meaning."
                                ),
                                details={
                                    "user_effect": plan.user_effect,
                                    "operation": plan.operation.value,
                                    "work_view": work_view,
                                    "presentation": plan.presentation_intent,
                                    "evidence_modes": list(plan.evidence_requirements.modes),
                                    "loop_intent": plan.loop_intent,
                                    "subjects": [
                                        item.model_dump(mode="json")
                                        for item in plan.subjects
                                    ],
                                    "compatible_meaning_contracts": near_match_contracts,
                                },
                            )
                        ],
                        catalog_revision=self.registry.version,
                        planner_schema_revision=PLANNER_SCHEMA_REVISION,
                    ),
                )
            definition = ranked[0]
            if (
                len(ranked) > 1
                and self._v4_candidate_score(
                    plan,
                    ranked[0],
                    available_context,
                )[:-1]
                == self._v4_candidate_score(
                    plan,
                    ranked[1],
                    available_context,
                )[:-1]
            ):
                raise SemanticPlanningError(
                    "catalog_ambiguous_match",
                    "The Capability Catalog has two equally specific compile contracts.",
                    report=PlanValidationReport(
                        valid=False,
                        issues=[
                            ValidationIssue(
                                code="catalog.ambiguous_match",
                                field="semantic_plan",
                                message="Two catalog compile contracts are equally specific.",
                                details={
                                    "capability_ids": [
                                        ranked[0].capability_id,
                                        ranked[1].capability_id,
                                    ]
                                },
                            )
                        ],
                        catalog_revision=self.registry.version,
                        planner_schema_revision=PLANNER_SCHEMA_REVISION,
                    ),
                )
        effective_operation = self._v4_effective_operation(
            plan,
            definition,
            available_context,
        )
        if effective_operation != plan.operation:
            plan = plan.model_copy(update={"operation": effective_operation})
        evidence_scope = next(
            (
                item
                for item in plan.evidence_requirements.scopes
                if item in definition.evidence_scopes
            ),
            definition.default_evidence_scope,
        )
        compile_contract = definition.semantic_compile
        # An empty model-owned requirement means "no stricter preference",
        # not "no Catalog may execute this plan". The selected typed Catalog
        # contract owns runtime evidence defaults, so materialize its ordered
        # default only after capability selection. Explicit, incompatible
        # modes are still rejected by candidate matching above.
        operation_evidence_modes = list(
            compile_contract.evidence_modes_by_operation.get(plan.operation, [])
        )
        normalized_plan_evidence_modes = self._v4_catalog_evidence_modes(
            plan,
            definition,
            plan.operation,
            available_context,
        )
        continuation_evidence_modes = (
            list(compile_contract.continuation_evidence_modes)
            if self._same_capability_continuation(
                plan,
                definition,
                available_context,
            )
            else []
        )
        effective_modes = list(
            dict.fromkeys(
                [
                    *normalized_plan_evidence_modes,
                    *operation_evidence_modes,
                    *continuation_evidence_modes,
                ]
            )
        ) or list(compile_contract.evidence_modes[:1])
        catalog_mode_scopes = [
            scope
            for mode in effective_modes
            for scope in compile_contract.evidence_scopes_by_mode.get(mode, [])
            if scope in definition.evidence_scopes
        ]
        catalog_operation_scopes = [
            scope
            for scope in compile_contract.evidence_scopes_by_operation.get(
                plan.operation,
                [],
            )
            if scope in definition.evidence_scopes
        ]
        effective_scopes = list(
            dict.fromkeys(
                [
                    *plan.evidence_requirements.scopes,
                    *catalog_mode_scopes,
                    *catalog_operation_scopes,
                ]
            )
        ) or [evidence_scope]
        catalog_authority_scopes = list(
            dict.fromkeys(
                compile_contract.evidence_authority_scope_by_mode[mode]
                for mode in effective_modes
                if mode in compile_contract.evidence_authority_scope_by_mode
            )
        )
        if len(catalog_authority_scopes) > 1:
            raise SemanticPlanningError(
                "catalog_evidence_authority_scope_conflict",
                "Selected evidence modes require conflicting authority scopes.",
            )
        effective_authority_scope = (
            catalog_authority_scopes[0]
            if catalog_authority_scopes
            else plan.evidence_requirements.authority_scope
        )
        if (
            effective_modes != list(plan.evidence_requirements.modes)
            or effective_scopes != list(plan.evidence_requirements.scopes)
            or effective_authority_scope
            != plan.evidence_requirements.authority_scope
        ):
            plan = plan.model_copy(
                update={
                    "evidence_requirements": plan.evidence_requirements.model_copy(
                        update={
                            "modes": effective_modes,
                            "scopes": effective_scopes,
                            "authority_scope": effective_authority_scope,
                        }
                    )
                }
            )
        evidence_authorities = list(
            dict.fromkeys(
                [
                    *compile_contract.evidence_authorities,
                    *(
                        authority
                        for mode in plan.evidence_requirements.modes
                        for authority in compile_contract.evidence_authorities_by_mode.get(
                            mode, []
                        )
                    ),
                ]
            )
        )
        evidence_statuses = list(
            dict.fromkeys(
                [
                    *compile_contract.evidence_statuses,
                    *(
                        status
                        for mode in plan.evidence_requirements.modes
                        for status in compile_contract.evidence_statuses_by_mode.get(
                            mode, []
                        )
                    ),
                ]
            )
        )
        operation_contract = definition.semantic_operation_contracts.get(plan.operation)
        # Work-view recipes own the boundary between operational assignment
        # and canonical responsibility.  A supplemental evidence mode (for
        # example execution evidence) must not replace that bounded recipe
        # with a generic neighbors traversal; it is compiled into typed
        # ProjectionRecipe bindings below.
        query_kind = (
            definition.semantic_compile.default_graph_query_by_work_view.get(work_view)
            or definition.semantic_compile.default_graph_query_by_presentation.get(
                plan.presentation_intent
            )
            or next(
                (
                    definition.semantic_compile.default_graph_query_by_evidence_mode[mode]
                    for mode in plan.evidence_requirements.modes
                    if mode
                    in definition.semantic_compile.default_graph_query_by_evidence_mode
                ),
                None,
            )
            or definition.semantic_compile.default_graph_query_by_operation.get(plan.operation)
        )
        projection_contracts: dict[tuple[str, str], dict[str, Any]] = {}
        for mode in effective_modes:
            projections_by_subject_kind = (
                compile_contract.ontology_projection_recipes_by_evidence_mode.get(
                    mode,
                    {},
                )
            )
            for subject in plan.subjects:
                subject_ref = str(subject.entity_ref or "").strip()
                subject_kind = str(subject.entity_kind or "").strip()
                if subject.resolution != "resolved" or not subject_ref or not subject_kind:
                    continue
                projection_policies = [
                    *projections_by_subject_kind.get(subject_kind, []),
                    *projections_by_subject_kind.get("*", []),
                ]
                for policy in projection_policies:
                    key = (policy.projection_id, subject_ref)
                    existing = projection_contracts.get(key)
                    policy_contract = {
                        "evidence_category": policy.evidence_category,
                        "required_for_answer": policy.required_for_answer,
                        "empty_message": policy.empty_message,
                        "section_ids": list(policy.section_ids),
                        "primary_graph_mode": policy.primary_graph_mode,
                        "graph_query_kind": str(
                            policy.graph_query_kind_by_operation.get(
                                plan.operation,
                                "",
                            )
                            or ""
                        ),
                    }
                    if existing is not None and any(
                        existing[field] != value
                        for field, value in policy_contract.items()
                    ):
                        raise SemanticPlanningError(
                            "catalog_projection_contract_conflict",
                            "A ProjectionRecipe has conflicting Catalog completion contracts.",
                        )
                    if existing is None:
                        existing = {**policy_contract, "evidence_modes": []}
                        projection_contracts[key] = existing
                    if mode not in existing["evidence_modes"]:
                        existing["evidence_modes"].append(mode)
        ontology_projection_bindings = [
            OntologyProjectionBinding(
                projection_id=projection_id,
                subject_ref=subject_ref,
                evidence_modes=contract["evidence_modes"],
                evidence_category=contract["evidence_category"],
                required_for_answer=contract["required_for_answer"],
                empty_message=contract["empty_message"],
                section_ids=contract["section_ids"],
                primary_graph_mode=contract["primary_graph_mode"],
            )
            for (projection_id, subject_ref), contract in projection_contracts.items()
        ]
        projection_graph_query_kinds = {
            str(contract.get("graph_query_kind") or "")
            for contract in projection_contracts.values()
            if str(contract.get("graph_query_kind") or "")
        }
        if work_view == "none" and projection_graph_query_kinds:
            if len(projection_graph_query_kinds) > 1:
                raise SemanticPlanningError(
                    "catalog_projection_graph_recipe_conflict",
                    "ProjectionRecipe bindings require conflicting graph recipes.",
                )
            query_kind = next(iter(projection_graph_query_kinds))
        graph_required = bool(
            operation_contract and operation_contract.requires_graph
        ) or plan.operation == WorkOperation.connect or plan.presentation_intent in {
            "mermaid", "explorer", "timeline"
        }
        graph_query = None
        if graph_required:
            if not query_kind:
                raise SemanticPlanningError(
                    "catalog_graph_recipe_missing",
                    "The selected catalog contract has no deterministic graph recipe.",
                )
            subject_kinds = {
                str(item.entity_kind or "").strip()
                for item in plan.subjects
                if str(item.entity_kind or "").strip()
            }
            graph_depth = max(
                [
                    2,
                    *[
                        int(depth)
                        for kind, depth in compile_contract.graph_depth_by_subject_kind.items()
                        if kind in subject_kinds
                    ],
                ]
            )
            graph_query = GraphQueryDraft(
                enabled=True,
                query_kind=query_kind,
                focal_mentions=[
                    item.entity_ref or item.mention
                    for item in plan.subjects
                ][:20],
                target_mentions=[],
                node_kinds=[],
                relation_kinds=[],
                direction="both",
                depth=max(1, min(graph_depth, 6)),
                presentation=(
                    plan.presentation_intent
                    if plan.presentation_intent in {"table", "timeline", "mermaid", "explorer"}
                    else "auto"
                ),
            )
        loop_contract = definition.default_loop_contract.model_copy(deep=True)
        if loop_contract.kind.value == "turn":
            loop_contract = loop_contract.model_copy(
                update={
                    "max_model_calls": min(2, loop_contract.max_model_calls),
                    "max_context_tokens": min(16_384, loop_contract.max_context_tokens or 16_384),
                    "max_elapsed_seconds": min(15, loop_contract.max_elapsed_seconds),
                }
            )
        execution_plan = ExecutionPlan(
            capability_id=definition.capability_id,
            operation_pipeline=self._pipeline(
                SemanticPlan(
                    resolved_goal=plan.resolved_goal,
                    retrieval_query=plan.retrieval_query,
                    capability_id=definition.capability_id,
                    user_effect=plan.user_effect,
                    operation=plan.operation,
                    evidence_scope=evidence_scope,
                    presentation=plan.presentation_intent,
                    work_perspectives=plan.work_perspectives,
                    work_view=work_view,
                    graph_query=graph_query,
                    loop_contract=loop_contract,
                ),
                definition,
            ),
            graph_query=graph_query,
            ontology_projection_bindings=ontology_projection_bindings,
            work_view=work_view,  # type: ignore[arg-type]
            evidence_scope=evidence_scope,  # type: ignore[arg-type]
            evidence_requirements=plan.evidence_requirements.model_copy(deep=True),
            evidence_authorities=evidence_authorities,
            evidence_statuses=evidence_statuses,
            presentation=plan.presentation_intent,
            harness_ids=list(definition.harness_ids),
            readiness_dependencies=list(definition.readiness),
            approval_required=bool(
                definition.risk.value != "low"
                or plan.mutation_intent in {"execute", "activate", "promote"}
            ),
            requested_loop_intent=plan.loop_intent,
            loop_contract=loop_contract,
            completion_criteria=list(definition.completion_criteria),
        )
        resolved_subjects = [
            item
            for item in plan.subjects
            if item.resolution == "resolved" and item.entity_ref
        ]
        # SemanticPlanV4 remains the complete meaning contract. The V3 object
        # below is only a compatibility adapter, so an unresolved descriptive
        # label must not be reinterpreted as a second verified target by the
        # legacy validator after the Catalog has already compiled the V4 plan.
        # If nothing resolved, retain the original subjects so the legacy
        # interrupt/clarification contract continues to apply.
        compatibility_subjects = resolved_subjects or plan.subjects
        resolved_refs = [item.entity_ref for item in resolved_subjects if item.entity_ref]
        compatibility_plan = SemanticPlan(
            resolved_goal=plan.resolved_goal,
            retrieval_query=plan.retrieval_query,
            topic_action=plan.topic_action,
            reference_resolution=plan.reference_resolution,
            subjects=compatibility_subjects,
            capability_id=definition.capability_id,
            user_effect=plan.user_effect,
            operation=plan.operation,
            evidence_scope=evidence_scope,
            presentation=plan.presentation_intent,
            work_perspectives=plan.work_perspectives,
            work_view=work_view,  # type: ignore[arg-type]
            graph_query=graph_query,
            context_refs=resolved_refs,
            target_ref=resolved_refs[0] if resolved_refs else "",
            answer_intent=self._answer_intent_for_v4(plan, work_view),  # type: ignore[arg-type]
            clarification_question=plan.clarification_question,
            continuation=plan.continuation_delta,
            loop_contract=loop_contract,
            confidence=plan.confidence,
        )
        legacy_compiled = self.compile(
            compatibility_plan,
            original_question=original_question,
            trusted_context_refs=trusted_context_refs,
            prior_topic_entities=prior_topic_entities,
            prior_focal_entities=prior_focal_entities,
            active_work_run=active_work_run,
        )
        work_intent = legacy_compiled.work_intent.model_copy(
            update={
                "evidence_requirements": plan.evidence_requirements.model_copy(deep=True),
                "evidence_authorities": evidence_authorities,
                "evidence_statuses": evidence_statuses,
                "ontology_projection_bindings": ontology_projection_bindings,
            }
        )
        return CompiledSemanticPlanV4(
            semantic_plan=plan,
            execution_plan=execution_plan,
            compatibility_plan=compatibility_plan,
            work_intent=work_intent,
            capability_id=definition.capability_id,
        )


def semantic_plan_schema(
    registry: CapabilityRegistry,
    *,
    trusted_context_refs: list[str] | None = None,
    prior_topic_entities: list[str] | None = None,
    prior_focal_entities: list[str] | None = None,
    requested_graph_node_kinds: list[str] | None = None,
    requested_graph_relation_kinds: list[str] | None = None,
    active_work_run: bool = False,
) -> dict[str, Any]:
    schema = copy.deepcopy(SemanticPlan.model_json_schema())
    definitions = schema.pop("$defs", {})

    def inline_refs(value: Any) -> Any:
        if isinstance(value, dict):
            ref = str(value.get("$ref") or "")
            if ref.startswith("#/$defs/"):
                key = ref.rsplit("/", 1)[-1]
                return inline_refs(copy.deepcopy(definitions[key]))
            return {key: inline_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline_refs(item) for item in value]
        return value

    schema = inline_refs(schema)

    properties = schema.get("properties") or {}
    if not active_work_run:
        # Conversation topic continuation and durable WorkRun continuation are
        # separate contracts. Do not expose execution-resume payloads when
        # there is no active run to resume.
        properties.pop("continuation", None)
    semantic_decisions = [
        "resolved_goal",
        "retrieval_query",
        "topic_action",
        "reference_resolution",
        "subjects",
        "capability_id",
        "user_effect",
        "operation",
        "evidence_scope",
        "presentation",
        "work_perspectives",
        "work_view",
        "graph_query",
        "context_refs",
        "target_ref",
        "answer_intent",
        "clarification_question",
        "loop_contract",
        "confidence",
    ]
    schema["required"] = semantic_decisions
    schema["additionalProperties"] = False

    # Require semantic choices while leaving optional runtime payload details
    # optional. In particular, a normal read turn must not be forced to invent
    # WorkRecord content merely to satisfy the planner transport schema.
    subject_schema = (properties.get("subjects") or {}).get("items") or {}
    subject_schema["required"] = ["mention", "entity_ref", "entity_kind", "resolution"]
    subject_schema["additionalProperties"] = False
    graph_schema = properties.get("graph_query") or {}
    graph_alternatives = graph_schema.get("anyOf") or []
    graph_object_schema: dict[str, Any] | None = None
    graph_null_schemas: list[dict[str, Any]] = []
    for alternative in graph_alternatives:
        if alternative.get("type") == "object" and isinstance(alternative.get("properties"), dict):
            graph_object_schema = alternative
            alternative["required"] = list(alternative["properties"])
            alternative["additionalProperties"] = False
            graph_properties = alternative["properties"]
            filter_contract = registry.graph_query_filter_contract
            if filter_contract.node_kinds:
                requested_nodes = list(
                    dict.fromkeys(
                        item
                        for item in (requested_graph_node_kinds or [])
                        if item in filter_contract.node_kinds
                    )
                )
                node_schema = graph_properties.get("node_kinds") or {}
                (node_schema.get("items") or {})["enum"] = (
                    requested_nodes or list(filter_contract.node_kinds)
                )
                node_schema["maxItems"] = len(requested_nodes)
            if filter_contract.relation_kinds:
                requested_relations = list(
                    dict.fromkeys(
                        item
                        for item in (requested_graph_relation_kinds or [])
                        if item in filter_contract.relation_kinds
                    )
                )
                relation_schema = graph_properties.get("relation_kinds") or {}
                (relation_schema.get("items") or {})["enum"] = (
                    requested_relations or list(filter_contract.relation_kinds)
                )
                relation_schema["maxItems"] = len(requested_relations)
        elif alternative.get("type") == "null":
            graph_null_schemas.append(alternative)
    if graph_object_schema is not None:
        graph_enabled_schema = copy.deepcopy(graph_object_schema)
        graph_disabled_schema = copy.deepcopy(graph_object_schema)
        graph_enabled_properties = graph_enabled_schema.get("properties") or {}
        graph_disabled_properties = graph_disabled_schema.get("properties") or {}
        graph_enabled_properties.setdefault("enabled", {})["const"] = True
        graph_disabled_properties.setdefault("enabled", {})["const"] = False
        graph_enabled_properties.setdefault("focal_mentions", {})["minItems"] = 1
        graph_schema["anyOf"] = [
            graph_enabled_schema,
            graph_disabled_schema,
            *graph_null_schemas,
        ]
    loop_schema = properties.get("loop_contract") or {}
    if isinstance(loop_schema.get("properties"), dict):
        loop_schema["required"] = list(loop_schema["properties"])
        loop_schema["additionalProperties"] = False
    properties.setdefault("capability_id", {})["enum"] = [item.capability_id for item in registry.all()]
    focal_refs = list(
        dict.fromkeys(
            str(item)
            for item in (
                prior_focal_entities
                if prior_focal_entities is not None
                else prior_topic_entities or []
            )
            if str(item)
        )
    )
    if not focal_refs:
        properties.setdefault("topic_action", {})["enum"] = ["new"]
        properties.setdefault("reference_resolution", {})["enum"] = ["none"]
    elif len(focal_refs) == 1:
        properties.setdefault("reference_resolution", {})["enum"] = ["none", "specific"]
    else:
        properties.setdefault("reference_resolution", {})["enum"] = [
            "none",
            "all",
            "specific",
            "ambiguous",
        ]
    subject_kinds = sorted(
        {
            kind
            for definition in registry.all()
            for kind in definition.subject_kinds
            if kind
        }
    )
    subject_properties = subject_schema.get("properties") or {}
    if subject_kinds:
        subject_properties.setdefault("entity_kind", {})["enum"] = ["", *subject_kinds]

    # The planner owns the subject mention, while internal identity remains an
    # ACL boundary. A ref can only be empty or one of the values supplied in
    # this request's visible context; downstream validation still uses the
    # complete SemanticPlan model and Capability Catalog.
    trusted_refs = list(dict.fromkeys(str(item) for item in (trusted_context_refs or []) if str(item)))
    subject_properties.setdefault("entity_ref", {})["enum"] = ["", *trusted_refs]
    properties.setdefault("target_ref", {})["enum"] = ["", *trusted_refs]
    if trusted_refs:
        ((properties.get("context_refs") or {}).get("items") or {})["enum"] = trusted_refs
    return schema


def semantic_plan_v4_schema(
    registry: CapabilityRegistry,
    *,
    trusted_context_refs: list[str] | None = None,
    prior_topic_entities: list[str] | None = None,
    prior_focal_entities: list[str] | None = None,
    active_work_run: bool = False,
) -> dict[str, Any]:
    """Production planner schema containing meaning fields only."""

    schema = copy.deepcopy(SemanticPlanV4.model_json_schema())
    definitions = schema.pop("$defs", {})

    def inline_refs(value: Any) -> Any:
        if isinstance(value, dict):
            ref = str(value.get("$ref") or "")
            if ref.startswith("#/$defs/"):
                inlined = inline_refs(
                    copy.deepcopy(definitions[ref.rsplit("/", 1)[-1]])
                )
                siblings = inline_refs(
                    {key: item for key, item in value.items() if key != "$ref"}
                )
                if isinstance(inlined, dict) and isinstance(siblings, dict):
                    return {**inlined, **siblings}
                return inlined
            return {key: inline_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline_refs(item) for item in value]
        return value

    schema = inline_refs(schema)
    properties = schema.get("properties") or {}
    if not active_work_run:
        properties.pop("continuation_delta", None)
    semantic_fields = [
        "resolved_goal",
        "retrieval_query",
        "topic_action",
        "reference_resolution",
        "subjects",
        "result_asset_kind",
        "user_effect",
        "operation",
        "work_perspectives",
        "presentation_intent",
        "evidence_requirements",
        "mutation_intent",
        "loop_intent",
        "clarification_question",
        "confidence",
    ]
    if active_work_run:
        semantic_fields.append("continuation_delta")
    schema["required"] = semantic_fields
    schema["additionalProperties"] = False
    subject_schema = (properties.get("subjects") or {}).get("items") or {}
    subject_schema["required"] = ["mention", "entity_ref", "entity_kind", "resolution"]
    subject_schema["additionalProperties"] = False
    subject_properties = subject_schema.get("properties") or {}
    trusted_refs = list(dict.fromkeys(str(item) for item in trusted_context_refs or [] if str(item)))
    subject_properties.setdefault("entity_ref", {})["enum"] = ["", *trusted_refs]
    subject_kinds = sorted(
        {
            kind
            for definition in registry.all()
            for kind in [*definition.subject_kinds, *definition.semantic_compile.preferred_subject_kinds]
            if kind
        }
    )
    subject_properties.setdefault("entity_kind", {})["enum"] = ["", *subject_kinds]
    focal_refs = list(
        dict.fromkeys(
            str(item)
            for item in (
                prior_focal_entities
                if prior_focal_entities is not None
                else prior_topic_entities or []
            )
            if str(item)
        )
    )
    if not focal_refs:
        properties.setdefault("topic_action", {})["enum"] = ["new"]
        properties.setdefault("reference_resolution", {})["enum"] = ["none"]
    elif len(focal_refs) == 1:
        properties.setdefault("reference_resolution", {})["enum"] = ["none", "specific"]
    else:
        properties.setdefault("reference_resolution", {})["enum"] = [
            "none", "all", "specific", "ambiguous"
        ]
    evidence_schema = properties.get("evidence_requirements") or {}
    if isinstance(evidence_schema.get("properties"), dict):
        evidence_schema["required"] = list(evidence_schema["properties"])
        evidence_schema["additionalProperties"] = False
    continuation_schema = properties.get("continuation_delta") or {}
    if isinstance(continuation_schema.get("properties"), dict):
        continuation_schema["required"] = list(continuation_schema["properties"])
        continuation_schema["additionalProperties"] = False
    return schema


def parse_semantic_plan_v4(payload: dict[str, Any]) -> ParsedSemanticPlanV4:
    """Parse V4 or adapt an explicit persisted/injected V3 wire payload."""

    raw = copy.deepcopy(payload)
    is_v4 = bool(
        str(raw.get("schema_revision") or "") == PLANNER_SCHEMA_REVISION
        or "presentation_intent" in raw
        or "evidence_requirements" in raw
    )
    compatibility: dict[str, Any] = {}
    if not is_v4:
        capability_id = str(raw.get("capability_id") or "")
        compatibility = {
            "source_schema_revision": str(raw.get("schema_revision") or "semantic-plan/v3"),
            "capability_id": capability_id,
            "work_view": str(raw.get("work_view") or "none"),
        }
        work_view = compatibility["work_view"]
        perspectives = raw.get("work_perspectives")
        expected_perspectives = {
            "current": ["current"],
            "responsibility": ["responsibility"],
            "combined": ["current", "responsibility"],
        }.get(work_view, [])
        if (
            not isinstance(perspectives, list)
            or set(str(item) for item in perspectives) != set(expected_perspectives)
        ):
            # V3 carried both a semantic perspective list and a derived
            # work_view, so persisted/scripted rows can contain an impossible
            # combination. The compatibility boundary normalizes that legacy
            # redundancy once; V4 itself owns only the semantic perspectives.
            perspectives = expected_perspectives
            compatibility["work_perspectives_reconciled"] = True
        scope = str(raw.get("evidence_scope") or "canonical")
        mode_by_capability = {
            "work.inbox": "current_work",
            "task.work": "execution_evidence",
            "cases.similar": "historical_cases",
            "knowledge.draft": "private_learning",
        }
        legacy_evidence_mode = mode_by_capability.get(capability_id)
        if not legacy_evidence_mode:
            # V3 had only a source scope and could not express the V4
            # evidence mode. Preserve that typed distinction at the one
            # compatibility boundary: operational facts are execution
            # evidence, while canonical/validation reads remain
            # authoritative knowledge. Without this conversion an
            # operational runtime catalog is broadened back to canonical by
            # the V4 Catalog and stale topic sources leak into follow-ups.
            legacy_evidence_mode = (
                "execution_evidence"
                if scope == "operational"
                else "authoritative_knowledge"
            )
        work_evidence_contract = {
            "current": {
                "scopes": ["operational"],
                "modes": ["current_work"],
            },
            "responsibility": {
                "scopes": ["canonical"],
                "modes": ["relationship_provenance"],
            },
            "combined": {
                "scopes": ["operational", "canonical"],
                "modes": ["current_work", "relationship_provenance"],
            },
        }.get(work_view)
        user_effect = str(raw.get("user_effect") or "read")
        operation = str(raw.get("operation") or "understand")
        mutation_intent = (
            "none"
            if user_effect == "read"
            else "private_draft"
            if user_effect == "draft"
            else "transform_preview"
            if user_effect == "transform"
            else "promote"
            if operation == "promote"
            else "execute"
        )
        loop_contract = raw.get("loop_contract") if isinstance(raw.get("loop_contract"), dict) else {}
        subjects = raw.get("subjects") if isinstance(raw.get("subjects"), list) else []
        legacy_graph = raw.get("graph_query") if isinstance(raw.get("graph_query"), dict) else {}
        if not subjects:
            target_ref = str(raw.get("target_ref") or "").strip()
            context_refs = [
                str(item).strip()
                for item in raw.get("context_refs") or []
                if str(item).strip()
            ]
            legacy_subject_refs = [target_ref] if target_ref else context_refs[:20]
            subjects = [
                {
                    "mention": subject_ref,
                    "entity_ref": subject_ref,
                    "entity_kind": "",
                    "resolution": "resolved",
                }
                for subject_ref in dict.fromkeys(legacy_subject_refs)
            ]
        if not subjects and bool(legacy_graph.get("enabled")):
            graph_mentions = list(
                dict.fromkeys(
                    str(item).strip()
                    for item in [
                        *(legacy_graph.get("focal_mentions") or []),
                        *(legacy_graph.get("target_mentions") or []),
                    ]
                    if str(item).strip()
                )
            )
            subjects = [
                {
                    "mention": mention,
                    "entity_ref": "",
                    "entity_kind": "",
                    "resolution": "unresolved",
                }
                for mention in graph_mentions[:20]
            ]
        raw = {
            "schema_revision": PLANNER_SCHEMA_REVISION,
            "resolved_goal": raw.get("resolved_goal") or "",
            "retrieval_query": raw.get("retrieval_query") or raw.get("resolved_goal") or "",
            "topic_action": raw.get("topic_action") or "new",
            "reference_resolution": raw.get("reference_resolution") or "none",
            "subjects": subjects,
            "user_effect": user_effect,
            "operation": operation,
            "work_perspectives": perspectives,
            "presentation_intent": raw.get("presentation") or "prose",
            "evidence_requirements": {
                "scopes": (
                    list(work_evidence_contract["scopes"])
                    if work_evidence_contract
                    else [scope]
                    if scope in {"canonical", "operational", "validation"}
                    else ["canonical"]
                ),
                "modes": (
                    list(work_evidence_contract["modes"])
                    if work_evidence_contract
                    else [legacy_evidence_mode]
                ),
                "require_citations": True,
                "require_freshness": True,
                "as_of": "",
            },
            "mutation_intent": mutation_intent,
            "loop_intent": str(loop_contract.get("kind") or "turn"),
            "clarification_question": raw.get("clarification_question") or "",
            "continuation_delta": raw.get("continuation") or {
                "continue_active_run": False,
                "delta_kind": "none",
                "user_confirmation": False,
                "work_record": {},
            },
            "confidence": raw.get("confidence") or 0.0,
        }
    raw_subjects = raw.get("subjects")
    if isinstance(raw_subjects, list):
        # A provider can mention one verified identity more than once and can
        # disagree only on redundant transport fields such as resolution or
        # kind.  Collapse exact non-empty refs before semantic validation so
        # this harmless duplication does not spend the one allowed repair
        # call.  This is identity normalization, not question interpretation:
        # unresolved subjects without a ref remain distinct and ordered.
        deduplicated_subjects: list[Any] = []
        subject_index_by_ref: dict[str, int] = {}
        deduplicated_refs: list[str] = []
        resolution_rank = {
            "unresolved": 0,
            "ambiguous": 1,
            "resolved": 2,
        }
        for item in raw_subjects:
            if not isinstance(item, dict):
                deduplicated_subjects.append(item)
                continue
            subject = copy.deepcopy(item)
            subject_ref = str(subject.get("entity_ref") or "").strip()
            subject["entity_ref"] = subject_ref
            if not subject_ref or subject_ref not in subject_index_by_ref:
                if subject_ref:
                    subject_index_by_ref[subject_ref] = len(deduplicated_subjects)
                deduplicated_subjects.append(subject)
                continue
            existing_index = subject_index_by_ref[subject_ref]
            existing = deduplicated_subjects[existing_index]
            if not isinstance(existing, dict):
                continue
            if not str(existing.get("mention") or "").strip():
                existing["mention"] = subject.get("mention") or subject_ref
            if not str(existing.get("entity_kind") or "").strip():
                existing["entity_kind"] = subject.get("entity_kind") or ""
            existing_resolution = str(existing.get("resolution") or "unresolved")
            subject_resolution = str(subject.get("resolution") or "unresolved")
            if resolution_rank.get(subject_resolution, -1) > resolution_rank.get(
                existing_resolution,
                -1,
            ):
                existing["resolution"] = subject_resolution
            deduplicated_refs.append(subject_ref)
        if deduplicated_refs:
            raw["subjects"] = deduplicated_subjects
            compatibility["deduplicated_subject_refs"] = list(
                dict.fromkeys(deduplicated_refs)
            )
    if (
        str(raw.get("topic_action") or "new") != "clarify"
        and not str(raw.get("retrieval_query") or "").strip()
        and str(raw.get("resolved_goal") or "").strip()
    ):
        raw["retrieval_query"] = str(raw["resolved_goal"]).strip()
    clarification = " ".join(
        str(raw.get("clarification_question") or "").split()
    ).strip()
    if str(raw.get("topic_action") or "new") != "clarify":
        # This field has no executable meaning outside a clarification turn.
        # Clearing it prevents an irrelevant model-authored paragraph from
        # invalidating an otherwise complete meaning contract.
        raw["clarification_question"] = ""
    elif len(clarification) > 240:
        # A clarification is a safe human interrupt. Bound its transport text
        # without changing subjects, effects, operations, or runtime choices.
        raw["clarification_question"] = clarification[:239].rstrip() + "…"
    else:
        raw["clarification_question"] = clarification
    raw.setdefault(
        "continuation_delta",
        {
            "continue_active_run": False,
            "delta_kind": "none",
            "user_confirmation": False,
            "work_record": {},
        },
    )
    try:
        return ParsedSemanticPlanV4(
            plan=SemanticPlanV4.model_validate(raw),
            compatibility=compatibility,
        )
    except ValidationError as exc:
        issues = [
            ValidationIssue(
                code="schema.invalid",
                field=".".join(str(item) for item in error.get("loc") or []),
                message=str(error.get("msg") or "Invalid SemanticPlanV4 field."),
            )
            for error in exc.errors()[:50]
        ]
        raise SemanticPlanningError(
            "planner_invalid",
            "Planner output did not match SemanticPlanV4.",
            report=PlanValidationReport(
                valid=False,
                issues=issues,
                planner_schema_revision=PLANNER_SCHEMA_REVISION,
            ),
        ) from exc


def parse_semantic_plan(payload: dict[str, Any]) -> SemanticPlan:
    normalized = copy.deepcopy(payload)
    if (
        str(normalized.get("topic_action") or "new") != "clarify"
        and not str(normalized.get("retrieval_query") or "").strip()
        and str(normalized.get("resolved_goal") or "").strip()
    ):
        normalized["retrieval_query"] = str(normalized["resolved_goal"]).strip()
    seen_subject_refs: set[str] = set()
    normalized_subjects: list[Any] = []
    for raw_subject in normalized.get("subjects") or []:
        if not isinstance(raw_subject, dict):
            normalized_subjects.append(raw_subject)
            continue
        subject = dict(raw_subject)
        entity_ref = str(subject.get("entity_ref") or "").strip()
        if entity_ref and entity_ref in seen_subject_refs:
            # One ACL-visible identity can support multiple user mentions. Keep
            # the additional mention as unresolved semantic context instead of
            # making the whole plan fail or pretending it is another entity.
            subject["entity_ref"] = ""
            subject["resolution"] = "unresolved"
        elif entity_ref:
            seen_subject_refs.add(entity_ref)
        normalized_subjects.append(subject)
    normalized["subjects"] = normalized_subjects
    try:
        return SemanticPlan.model_validate(normalized)
    except ValidationError as exc:
        issues = [
            ValidationIssue(
                code="schema.invalid",
                field=".".join(str(item) for item in error.get("loc") or []),
                message=str(error.get("msg") or "Invalid semantic plan field."),
            )
            for error in exc.errors()[:50]
        ]
        raise SemanticPlanningError(
            "planner_invalid",
            "Planner output did not match the SemanticPlan schema.",
            report=PlanValidationReport(valid=False, issues=issues),
        ) from exc
