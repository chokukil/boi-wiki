from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .capabilities import CapabilityRegistry
from .models import (
    GraphQueryDraft,
    PlanValidationReport,
    SemanticPlan,
    SemanticSubject,
    TypedCommand,
    ValidationIssue,
    WorkIntent,
    WorkOperation,
)


PLANNER_SCHEMA_REVISION = "semantic-plan/v3"


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


class PlanValidator:
    """Validate model-owned meaning without changing it or choosing a fallback."""

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

    def validate(
        self,
        plan: SemanticPlan,
        *,
        trusted_context_refs: set[str] | None = None,
        prior_topic_entities: list[str] | None = None,
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
            if (
                operation_contract is not None
                and operation_contract.presentations
                and plan.presentation not in operation_contract.presentations
            ):
                issues.append(
                    self._issue(
                        "operation.presentation_not_allowed",
                        "operation",
                        "The selected presentation is not declared for this semantic operation.",
                        details={
                            "operation": plan.operation.value,
                            "presentation": plan.presentation,
                            "allowed": list(operation_contract.presentations),
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
        prior_refs = {str(item).strip() for item in prior_topic_entities or [] if str(item).strip()}
        resolved_subject_refs = {
            item.entity_ref.strip()
            for item in plan.subjects
            if item.entity_ref.strip()
        }
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
            and prior_refs
            and inherited_refs != prior_refs
        ):
            issues.append(
                self._issue(
                    "topic.all_reference_incomplete",
                    "subjects",
                    "An all-subject continuation must retain every verified prior subject.",
                    details={"prior": sorted(prior_refs), "selected": sorted(inherited_refs)},
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
        if plan.topic_action == "new" and prior_refs and not resolved_subject_refs:
            issues.append(
                self._issue(
                    "topic.new_subject_not_resolved",
                    "subjects",
                    "A new topic in an existing session must resolve its distinct subject.",
                    details={"prior": sorted(prior_refs)},
                )
            )
        if plan.topic_action == "new" and inherited_refs:
            issues.append(
                self._issue(
                    "topic.new_reuses_prior_subject",
                    "topic_action",
                    "A new topic cannot reuse a verified prior subject as its resolved subject.",
                    details={"overlap": sorted(inherited_refs)},
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
        active_work_run: bool = False,
    ) -> CompiledSemanticPlan:
        report = self.validator.validate(
            plan,
            trusted_context_refs=trusted_context_refs,
            prior_topic_entities=prior_topic_entities,
            active_work_run=active_work_run,
        )
        if not report.valid:
            raise SemanticPlanningError("planner_invalid", "Semantic plan did not pass validation.", report=report)
        definition = self.registry.get(plan.capability_id)
        topic_mentions = [item.mention for item in plan.subjects]
        resolved_subject_refs = [item.entity_ref for item in plan.subjects if item.entity_ref]
        topic_entities = [item.entity_ref or item.mention for item in plan.subjects]
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
            referenceable_topic_entities=resolved_subject_refs,
            followup_reference_resolution=plan.reference_resolution,
            selected_prior_topic_entities=resolved_subject_refs if plan.topic_action == "continue" else [],
            followup_semantic_change=(
                "same_subject_question" if plan.topic_action == "continue" else "new_subject" if plan.topic_action == "new" else "ambiguous_reference"
            ),
            comparison_focal_entities=resolved_subject_refs if plan.operation == WorkOperation.compare else [],
            relationship_focal_entities=resolved_subject_refs if plan.operation == WorkOperation.connect else [],
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


def semantic_plan_schema(
    registry: CapabilityRegistry,
    *,
    trusted_context_refs: list[str] | None = None,
    prior_topic_entities: list[str] | None = None,
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
    for alternative in graph_schema.get("anyOf") or []:
        if alternative.get("type") == "object" and isinstance(alternative.get("properties"), dict):
            alternative["required"] = list(alternative["properties"])
            alternative["additionalProperties"] = False
            graph_properties = alternative["properties"]
            filter_contract = registry.graph_query_filter_contract
            if filter_contract.node_kinds:
                ((graph_properties.get("node_kinds") or {}).get("items") or {})["enum"] = list(
                    filter_contract.node_kinds
                )
            if filter_contract.relation_kinds:
                ((graph_properties.get("relation_kinds") or {}).get("items") or {})["enum"] = list(
                    filter_contract.relation_kinds
                )
    loop_schema = properties.get("loop_contract") or {}
    if isinstance(loop_schema.get("properties"), dict):
        loop_schema["required"] = list(loop_schema["properties"])
        loop_schema["additionalProperties"] = False
    properties.setdefault("capability_id", {})["enum"] = [item.capability_id for item in registry.all()]
    prior_refs = list(dict.fromkeys(str(item) for item in (prior_topic_entities or []) if str(item)))
    if not prior_refs:
        properties.setdefault("reference_resolution", {})["enum"] = ["none"]
    elif len(prior_refs) == 1:
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


def parse_semantic_plan(payload: dict[str, Any]) -> SemanticPlan:
    try:
        return SemanticPlan.model_validate(payload)
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
