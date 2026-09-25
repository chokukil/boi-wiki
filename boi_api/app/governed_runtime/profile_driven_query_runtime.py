"""Canonical profile-driven natural-language query orchestration.

This module only composes the already-qualified generic semantic components.
It contains no domain vocabulary, registered computation matcher, family
router, query template, SQL generation by a model, or Release authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Annotated, Any, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ledger import GovernedRuntimeLedger, RecordKind
from .cardinality_profile_binding import (
    ProfileBoundShapeSelection,
    bind_cardinality_profile_contracts,
    solve_profile_bound_query_shape,
)
from .cardinality_query_shape import QueryShapeRequest
from .generic_result_shape_planner import (
    GenericLogicalResultShapePlan,
    GenericResultShapePlanner,
)
from .latest_selection_contract import LatestContractGap
from .local_model_routing import LocalModelPolicy, LocalModelRunIdentity
from .local_pi_intent_client import NinferIntentClient
from .local_embedding_client import LocalEmbeddingClient
from .semantic_authority import (
    SemanticAuthorityFields,
    require_active_semantic_authority,
    require_reviewed_semantic_authority,
    require_same_semantic_authority,
    semantic_authority_values,
)
from .query_gateway import QueryExecution, QueryGatewayService
from .query_answerability import (
    QueryAnswerabilityReceipt,
    classify_query_answerability,
)
from .multi_result_query_gateway import (
    AuthorizedPhysicalMapping,
    MultiResultExploratoryExecutionRequest,
    MultiResultLogicalPlan,
    MultiResultParameterSpec,
    MultiResultPlanAuthorityReceipt,
    MultiResultQueryExecution,
    MultiResultSetPlan,
    MultiResultSqliteGateway,
    capture_multi_result_sqlite_schema,
    create_multi_result_logical_plan,
    validate_multi_result_plan_authority,
)
from .physical_plan_binding import PhysicalPlanBinder, PhysicalPlanBinding
from .semantic_intent import PiIntentSynthesizer, SemanticIntentResolver, IntentSynthesisReceipt, SemanticQuestionInterpretation
from .query_clarification import QueryClarificationStore
from .identity_grain_equivalence import prove_identity_grain
from .semantic_plan_reuse import (
    GenericPlanPromotionCandidate,
    QualifiedSemanticPlanPreparation,
    QualifiedSemanticPlanStore,
)
from .semantic_profile_loader import (
    ActiveReleaseProfileLoader,
    ProfileCatalogSnapshot,
    ProfilePrincipal,
)
from .release_rebuild import KnowledgeObjectStore
from .semantic_profile_retrieval import HybridSemanticRetriever
from .semantic_query_execution import (
    SemanticExploratoryExecutionRequest,
    SemanticSqliteCompiler,
    capture_sqlite_planner_catalog,
)
from .semantic_query_planner import (
    CheckEvidenceStore,
    GenericBindingSolver,
    GenericRelationalPlanner,
    PlannerCatalogSnapshot,
    PlanningPolicy,
    SemanticPlanValidator,
    SemanticPlanningContext,
)
from .token_routing_metrics import TokenRoutingMetrics
from .governed_answer_delivery import GovernedQueryAnswerDeliveryContext
from .governed_answer_artifact import (
    GovernedAnswerArtifact,
    GovernedAnswerArtifactBuilder,
)
from .canonical_query_resources import (
    CanonicalEntrypointClosure,
    CanonicalQueryResourceBroker,
    QueryResourceManifest,
    audit_canonical_entrypoint_closure,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _reason_code(error: Exception) -> str:
    value = str(error).split(":", 1)[0].strip()
    return (
        value
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", value)
        else "GENERIC_QUERY_RUNTIME_FAILED"
    )


class QueryRootClarificationRequired(ValueError):
    def __init__(self, options: tuple[tuple[str, str], ...]):
        super().__init__("ROOT_OBJECT_AMBIGUOUS")
        self.options = options


class QueryShapeContractGap(ValueError):
    def __init__(self, request_digest: str):
        super().__init__("RESULT_GRAIN_NOT_APPROVED")
        self.dependency_ref = f"required-result-shape:{request_digest}"


class ModelIdentityProvider(Protocol):
    def __call__(self) -> LocalModelRunIdentity: ...


class ProfileDrivenQueryRuntimeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route: Literal[
        "exploratory_semantic",
        "clarification_required",
        "blocked",
        "not_applicable",
    ]
    registered_match: None = None
    parameters: dict[str, Any] = {}
    clarification_count: int = 0
    clarification: str = ""
    clarification_challenge: dict[str, Any] | None = None
    result_status: Literal["PROVISIONAL", "BLOCKED"]
    execution: QueryExecution | MultiResultQueryExecution | None = None
    plan_kind: Literal["single_result", "multi_result", "none"] = "none"
    plan_digest: str = ""
    catalog_snapshot_digest: str = ""
    plan_cache_status: Literal["HIT", "MISS", "NOT_APPLICABLE"] = "NOT_APPLICABLE"
    plan_cache_key: str = ""
    promotion_candidate: GenericPlanPromotionCandidate | None = None
    source_tables: tuple[str, ...] = ()
    join_path: tuple[str, ...] = ()
    intent_digest: str = ""
    grain: tuple[str, ...] = ()
    active_release_digest: str = ""
    profile_contract_binding_digest: str = ""
    shape_solver_outcome_digest: str = ""
    shape_selection_receipt_digest: str = ""
    relationship_contract_digests: tuple[str, ...] = ()
    quality_receipt_digests: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    codex_fallback_allowed: Literal[False] = False
    answerability: QueryAnswerabilityReceipt | None = None
    answer_delivery_context: GovernedQueryAnswerDeliveryContext | None = None
    governed_answer_artifact: GovernedAnswerArtifact | None = None
    resource_manifest_digest: str = ""
    entrypoint_closure_digest: str = ""
    resource_access_receipt_digest: str = ""
    resource_freeze_receipt_digest: str = ""
    resource_access_count: int = 0
    denied_oracle_access_count: int = 0


class CanonicalSingleResultPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_kind: Literal["single_result"] = "single_result"
    shape_selection: ProfileBoundShapeSelection
    preparation: QualifiedSemanticPlanPreparation


class CanonicalMultiResultPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_kind: Literal["multi_result"] = "multi_result"
    shape_selection: ProfileBoundShapeSelection
    logical_plan: MultiResultLogicalPlan
    validation_receipt: MultiResultPlanAuthorityReceipt
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    parameter_specs: tuple[MultiResultParameterSpec, ...]
    parameters: dict[str, Any]


CanonicalPreparedPlan = Annotated[
    CanonicalSingleResultPlan | CanonicalMultiResultPlan,
    Field(discriminator="plan_kind"),
]


class ReviewedSemanticPlanOutcome(SemanticAuthorityFields):
    """Common planner output over a reviewed definition scope; no execution grant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal['boi/reviewed-semantic-plan-outcome@1'] = (
        'boi/reviewed-semantic-plan-outcome@1'
    )
    active_release_digest: None = None
    status: Literal['READY', 'BLOCKED', 'CLARIFICATION_REQUIRED']
    reason_codes: tuple[str, ...]
    interpretation_receipt_digest: str
    planning_context: SemanticPlanningContext
    shape_selection: ProfileBoundShapeSelection | None
    semantic_plan: GenericLogicalResultShapePlan | None
    physical_binding: PhysicalPlanBinding | None
    parameters: dict[str, Any]
    execution_authority_granted: Literal[False] = False
    outcome_digest: str

    @model_validator(mode='after')
    def exact_receipt_chain(self):
        require_reviewed_semantic_authority(self)
        require_same_semantic_authority(self, self.planning_context)
        complete = (
            self.shape_selection is not None,
            self.semantic_plan is not None,
            self.physical_binding is not None,
        )
        if (self.status == 'READY') != all(complete):
            raise ValueError('REVIEWED_SEMANTIC_PLAN_COMPLETENESS_INVALID')
        if self.status == 'READY':
            if (self.shape_selection.reviewed_definition_authority
                    != self.reviewed_definition_authority):
                raise ValueError('REVIEWED_SEMANTIC_PLAN_AUTHORITY_MISMATCH')
            require_same_semantic_authority(self, self.semantic_plan)
            if (self.physical_binding.reviewed_definition_authority
                    != self.reviewed_definition_authority):
                raise ValueError('REVIEWED_SEMANTIC_PLAN_AUTHORITY_MISMATCH')
        expected = _digest(self.model_dump(mode='json', exclude={'outcome_digest'}))
        if self.outcome_digest != expected:
            raise ValueError('REVIEWED_SEMANTIC_PLAN_OUTCOME_DIGEST_INVALID')
        return self


class ProfileDrivenQueryRuntime:
    """Execute a generic profile-only cold path through the protected Gateway."""

    def __init__(
        self,
        *,
        profile_loader: ActiveReleaseProfileLoader,
        catalog: PlannerCatalogSnapshot,
        retriever: HybridSemanticRetriever,
        intent_synthesizer: PiIntentSynthesizer | None,
        model_identity_provider: ModelIdentityProvider | None,
        planning_policy: PlanningPolicy,
        gateway: QueryGatewayService,
        ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore,
        occurred_at: Callable[[], str] | None = None,
        plan_store: QualifiedSemanticPlanStore | None = None,
        token_metrics: TokenRoutingMetrics | None = None,
        auto_route_enabled: bool = False,
        retrieval_top_k: int = 8,
        max_expanded_entries: int = 64,
        resource_manifest: QueryResourceManifest | None = None,
        entrypoint_closure: CanonicalEntrypointClosure | None = None,
        grain_policy: str = 'strict-v1',
        reviewed_retrieval_policy: str = 'scope-inventory-v7',
    ) -> None:
        self.profile_loader = profile_loader
        self.reviewed_retriever=HybridSemanticRetriever(policy_version=reviewed_retrieval_policy,
            embedding_provider=retriever.embedding_provider,embedding_identity_digest=retriever.embedding_identity_digest)
        if grain_policy not in {'strict-v1','snapshot-identity-v1'}:
            raise ValueError('GRAIN_EQUIVALENCE_POLICY_UNSUPPORTED')
        self.grain_policy = grain_policy
        self.catalog = catalog
        self.retriever = retriever
        self.intent_synthesizer = intent_synthesizer
        self.model_identity_provider = model_identity_provider
        self.planning_policy = planning_policy
        self.gateway = gateway
        self.ledger = ledger
        self.evidence_store = evidence_store
        self.occurred_at = occurred_at or (
            lambda: datetime.now(timezone.utc).isoformat()
        )
        self.plan_store = plan_store
        synthesizer_metrics = self.intent_synthesizer.metrics if self.intent_synthesizer is not None else None
        if (
            token_metrics is not None
            and synthesizer_metrics is not None
            and token_metrics is not synthesizer_metrics
        ):
            raise ValueError("TOKEN_METRICS_COLLECTOR_MISMATCH")
        self.token_metrics = (
            token_metrics or synthesizer_metrics or TokenRoutingMetrics()
        )
        if self.intent_synthesizer is not None and self.intent_synthesizer.metrics is None:
            self.intent_synthesizer.metrics = self.token_metrics
        self.auto_route_enabled = auto_route_enabled
        self.retrieval_top_k = retrieval_top_k
        self.max_expanded_entries = max_expanded_entries
        self.resource_manifest = resource_manifest or QueryResourceManifest.canonical()
        self.entrypoint_closure = entrypoint_closure or audit_canonical_entrypoint_closure(
            Path(__file__).resolve(), package_root=Path(__file__).resolve().parent
        )
        if self.entrypoint_closure.status != "PASS":
            raise ValueError("CANONICAL_ENTRYPOINT_DEPENDENCY_CLOSURE_FAILED")

    def is_applicable(self, question: str) -> bool:
        # Implicit routing is an explicit deployment choice.  No keyword or
        # synonym classifier is permitted on this generic surface.
        return self.auto_route_enabled and bool(question.strip())

    def _blocked(
        self,
        *reasons: str,
        question: str = "",
        catalog_digest: str | None = None,
        intent_digest: str = "",
        grain: tuple[str, ...] = (),
        active_release_digest: str = "",
        missing_dependency_ids: tuple[str, ...] = (),
    ) -> ProfileDrivenQueryRuntimeOutcome:
        reason_codes = tuple(dict.fromkeys(reasons)) or ("GENERIC_QUERY_BLOCKED",)
        return ProfileDrivenQueryRuntimeOutcome(
            route="blocked",
            result_status="BLOCKED",
            catalog_snapshot_digest=catalog_digest or self.catalog.snapshot_digest,
            intent_digest=intent_digest,
            grain=grain,
            active_release_digest=active_release_digest,
            reason_codes=reason_codes,
            answerability=self._answerability(
                question,
                executable=False,
                reasons=reason_codes,
                missing_dependency_ids=missing_dependency_ids,
                active_release_digest=active_release_digest,
            ),
        )

    @staticmethod
    def _answerability(
        question: str,
        *,
        executable: bool,
        reasons: tuple[str, ...] = (),
        missing_dependency_ids: tuple[str, ...] = (),
        active_release_digest: str = "",
    ) -> QueryAnswerabilityReceipt:
        return classify_query_answerability(
            executable=executable,
            reason_codes=reasons,
            missing_dependency_ids=missing_dependency_ids,
            active_release_digest=active_release_digest,
            query_digest=_digest(question),
        )

    def _prepare(
        self,
        context: SemanticPlanningContext,
        *,
        occurred_at: str,
        allow_plan_store: bool = True,
    ) -> QualifiedSemanticPlanPreparation:
        if self.plan_store is not None and allow_plan_store:
            return self.plan_store.prepare(
                context,
                ledger=self.ledger,
                evidence_store=self.evidence_store,
                occurred_at=occurred_at,
            )
        binding = GenericBindingSolver().resolve(context)
        if binding.status != "READY":
            return QualifiedSemanticPlanPreparation(
                status=binding.status,
                reason_codes=binding.reason_codes,
                cache_status="NOT_APPLICABLE",
                binding_receipt=binding,
                plan=None,
                validation_receipt=None,
                plan_reuse_receipt=None,
            )
        planned = GenericRelationalPlanner().plan(context, binding=binding)
        if planned.status != "READY" or planned.plan is None:
            return QualifiedSemanticPlanPreparation(
                status=planned.status,
                reason_codes=planned.reason_codes,
                cache_status="NOT_APPLICABLE",
                binding_receipt=binding,
                plan=None,
                validation_receipt=None,
                plan_reuse_receipt=None,
            )
        validation = SemanticPlanValidator().validate(
            planned.plan,
            context=context,
            binding=binding,
            ledger=self.ledger,
            evidence_store=self.evidence_store,
            occurred_at=occurred_at,
        )
        return QualifiedSemanticPlanPreparation(
            status="READY" if validation.status == "PASS" else "BLOCKED",
            reason_codes=validation.reason_codes,
            cache_status="NOT_APPLICABLE",
            binding_receipt=binding,
            plan=planned.plan,
            validation_receipt=validation,
            plan_reuse_receipt=None,
        )

    @staticmethod
    def _cardinality_request(
        context: SemanticPlanningContext,
    ) -> QueryShapeRequest | None:
        contracts = bind_cardinality_profile_contracts(context.bundle)
        if not contracts.result_shapes:
            return None
        candidate = context.resolved_intent.candidate
        domains = {item.entry_id: item for item in context.bundle.domain_entries}
        grain_owners = tuple(dict.fromkeys(
            str(domains[item].payload.get("owner_ref") or "")
            for item in candidate.grain
            if item in domains and domains[item].payload.get("owner_ref")
        ))
        approved_root = None
        if len(grain_owners) > 1:
            matching = SemanticIntentResolver.matching_result_shapes(
                context.bundle, candidate.entity_ids
            )
            roots = {
                shape.root_object_ref for shape in matching
                if shape.exact_grain == candidate.grain
            }
            if not roots and not candidate.aggregations and candidate.dimensions == candidate.grain:
                identities = {
                    domains[ref].payload.get("identity_property_ref")
                    for ref in candidate.entity_ids if ref in domains
                }
                if None not in identities and set(candidate.grain) == identities:
                    # Alternative independent collection roots need a semantic
                    # choice. They do not authorize rewriting a flat grain.
                    alternatives = {
                        shape.root_object_ref for shape in matching
                        if shape.shape in {"NestedCollection", "LinkedObjectSet"}
                        and shape.collection_semantics
                    }
                    if len(alternatives) > 1:
                        roots = alternatives
            if len(roots) > 1:
                raise QueryRootClarificationRequired(tuple(
                    (ref, str(domains[ref].payload.get("name") or ref))
                    for ref in sorted(roots)
                ))
            if not roots:
                raise QueryShapeContractGap(_digest({
                    "candidate": candidate.model_dump(mode="json"),
                    "bundle_digest": context.bundle.bundle_digest,
                }))
            approved_root = next(iter(roots))
        root_object_ref = (
            approved_root or grain_owners[0]
            if grain_owners
            else candidate.entity_ids[0]
            if candidate.entity_ids
            else ""
        )
        if not root_object_ref:
            raise ValueError("ROOT_OBJECT_REQUIRED")
        target_object_refs = tuple(
            item for item in candidate.entity_ids if item != root_object_ref
        )
        if candidate.intent_contract_version == 'scoped-result-intent-v4':
            # Referencing an object does not request its rowset or an otherwise
            # unrelated path. Only execution dependencies select relationships.
            used_objects = list(candidate.rowset_object_ids or ())
            used_objects.extend(item.scope_object_id for item in candidate.aggregations if item.scope_object_id)
            used_objects.extend(domains[item.property_id].payload.get('owner_ref') for item in candidate.filters)
            if candidate.time_range:
                used_objects.append(domains[candidate.time_range.property_id].payload.get('owner_ref'))
            target_object_refs = tuple(dict.fromkeys(ref for ref in used_objects if ref and ref != root_object_ref))
        if candidate.intent_contract_version in {'scoped-aggregate-v3', 'scoped-result-intent-v4'}:
            target_object_refs = tuple(dict.fromkeys((*target_object_refs, *(
                item.scope_object_id for item in candidate.aggregations
                if item.operator != 'latest' and item.scope_object_id and item.scope_object_id != root_object_ref))))
        reducer = None
        if candidate.aggregations and not target_object_refs:
            aggregation = candidate.aggregations[0]
            if aggregation.operator != "latest":
                reducer = (
                    "count_distinct"
                    if (
                        aggregation.operator == "distinct_count"
                        or aggregation.operator == "count" and aggregation.distinct
                    )
                    else aggregation.operator
                )
        return QueryShapeRequest(
            root_object_ref=root_object_ref,
            relationship_refs=(),
            target_object_refs=target_object_refs,
            max_relationship_hops=context.policy.max_relationship_hops,
            requested_shape=("ScalarAggregate" if reducer is not None and not candidate.grain else None),
            exact_grain=candidate.grain,
            aggregation_reducer=reducer,
            prior_clarifications=0,
            active_schema_snapshot_digest=context.bundle.schema_digest,
        )

    @staticmethod
    def _authorized_multi_result_mappings(
        context: SemanticPlanningContext,
        *,
        result_sets: tuple[MultiResultSetPlan, ...],
    ) -> tuple[AuthorizedPhysicalMapping, ...]:
        required_refs = {
            item.mapping_ref
            for result_set in result_sets
            for item in (
                *result_set.projections,
                *result_set.aggregations,
                *result_set.filters,
            )
        }
        by_id = {item.entry_id: item for item in context.bundle.mapping_entries}
        mappings: list[AuthorizedPhysicalMapping] = []
        for mapping_ref in sorted(required_refs):
            entry = by_id.get(mapping_ref)
            if (
                entry is None
                or entry.availability != "bound"
                or entry.physical is None
            ):
                raise ValueError("MULTI_RESULT_MAPPING_NOT_BOUND")
            mappings.append(AuthorizedPhysicalMapping(
                mapping_ref=mapping_ref,
                source_id=entry.physical.source,
                table=entry.physical.table,
                column=entry.physical.column,
                revision_digest=entry.revision_digest,
                temporal_encoding=entry.payload.get("temporal_encoding"),
            ))
        return tuple(mappings)

    @staticmethod
    def _resolved_parameters(context: SemanticPlanningContext, semantic_plan=None) -> dict[str, Any]:
        parameters = {
            f"filter_{index}": item.value
            for index, item in enumerate(context.resolved_intent.candidate.filters)
            if item.operator not in {"is_null", "not_null"}
        }
        if context.resolved_intent.candidate.time_range is not None:
            parameters.update({
                "time_start": context.resolved_intent.candidate.time_range.start,
                "time_end": context.resolved_intent.candidate.time_range.end,
            })
        if semantic_plan is not None:
            source_values = semantic_plan.source_qualifier_parameters
            if set(source_values) & set(parameters):
                raise ValueError('RELATION_QUALIFIER_PARAMETER_COLLISION')
            parameters.update(source_values)
        return parameters

    def _prepare_cardinality_plan(
        self,
        context: SemanticPlanningContext,
        *,
        occurred_at: str,
    ) -> CanonicalPreparedPlan | ProfileBoundShapeSelection | None:
        request = self._cardinality_request(context)
        candidate = context.resolved_intent.candidate
        strict_latest = candidate.intent_contract_version == "scoped-result-intent-v4" and any(item.operator == "latest" for item in candidate.aggregations)
        if request is None:
            if strict_latest:
                raise LatestContractGap("LATEST_RESULT_SHAPE_CONTRACT_REQUIRED", candidate.aggregations[0].scope_object_id or "unknown")
            return None
        selection = solve_profile_bound_query_shape(
            request,
            bundle=context.bundle,
            projection_policy=context.policy.nested_projection_policy,
        )
        if selection.status != "READY":
            return selection
        if selection.projection_receipt is not None:
            self.ledger.append(RecordKind.CHECK,selection.projection_receipt,
                authority='mapping_validator',occurred_at=occurred_at)
        selected_shape = selection.solver_outcome.selected_shape
        if selected_shape is None:
            raise ValueError("SELECTED_RESULT_SHAPE_MISSING")
        if selected_shape.shape not in {"NestedCollection", "LinkedObjectSet"} and not strict_latest:
            return CanonicalSingleResultPlan(
                shape_selection=selection,
                preparation=self._prepare(
                    context,
                    occurred_at=occurred_at,
                    allow_plan_store=False,
                )
            )
        semantic_plan = GenericResultShapePlanner().plan(
            context,
            shape_selection=selection,
        )
        physical_binding = PhysicalPlanBinder().bind(
            semantic_plan,
            bundle=context.bundle,
        )
        result_sets = physical_binding.result_sets
        physical_mappings = physical_binding.physical_mappings
        parameter_specs = tuple(
            MultiResultParameterSpec(name=item.name, type=item.type)
            for item in semantic_plan.parameter_specs
        )
        parameters = self._resolved_parameters(context, semantic_plan)
        quality_receipts = selection.solver_outcome.quality_receipts
        logical_plan = create_multi_result_logical_plan(
            shape_solver_outcome_digest=selection.solver_outcome.outcome_digest,
            profile_contract_binding_digest=selection.profile_contracts.binding_digest,
            active_release_digest=context.bundle.active_release_digest,
            domain_profile_digest=context.bundle.domain_profile_digest,
            mapping_profile_digest=context.bundle.mapping_profile_digest,
            query_profile_digest=context.bundle.query_profile_digest,
            schema_digest=context.bundle.schema_digest,
            result_sets=result_sets,
            parameter_specs=parameter_specs,
            quality_receipt_digests=tuple(
                item.receipt_digest for item in quality_receipts
            ),
        )
        validation = validate_multi_result_plan_authority(
            logical_plan,
            physical_mappings=physical_mappings,
            selected_relationship_ids=tuple(
                item.contract_id
                for item in selection.solver_outcome.bound_relationships
            ),
        )
        if validation.status != "PASS":
            raise ValueError(
                validation.error_codes[0]
                if validation.error_codes
                else "MULTI_RESULT_PLAN_AUTHORITY_FAILED"
            )
        return CanonicalMultiResultPlan(
            shape_selection=selection,
            logical_plan=logical_plan,
            validation_receipt=validation,
            physical_mappings=physical_mappings,
            parameter_specs=parameter_specs,
            parameters=parameters,
        )

    @staticmethod
    def _reviewed_plan_outcome(*, status, reasons, interpretation, context,
            selection=None, semantic_plan=None, physical_binding=None,
            parameters=None):
        body = {
            'contract_version': 'boi/reviewed-semantic-plan-outcome@1',
            **semantic_authority_values(context),
            'status': status,
            'reason_codes': tuple(reasons),
            'interpretation_receipt_digest': interpretation.receipt_digest,
            'planning_context': context.model_dump(mode='json'),
            'shape_selection': (
                selection.model_dump(mode='json') if selection is not None else None
            ),
            'semantic_plan': (
                semantic_plan.model_dump(mode='json')
                if semantic_plan is not None else None
            ),
            'physical_binding': (
                physical_binding.model_dump(mode='json')
                if physical_binding is not None else None
            ),
            'parameters': parameters or {},
            'execution_authority_granted': False,
        }
        return ReviewedSemanticPlanOutcome.model_validate({
            **body, 'outcome_digest': _digest(body)
        })

    def plan_reviewed_interpretation(self, interpretation, *, bundle, catalog,
            validate_current_scope):
        """Run the common deterministic planner without granting Gateway access."""
        require_reviewed_semantic_authority(bundle)
        require_reviewed_semantic_authority(interpretation)
        require_same_semantic_authority(interpretation, bundle)
        if (interpretation.status != 'RESOLVED'
                or interpretation.resolution is None
                or interpretation.resolution.resolved_intent is None):
            raise ValueError('REVIEWED_QUESTION_RESOLUTION_REQUIRED')
        validate_current_scope(bundle)
        context = SemanticPlanningContext.create(
            retrieval=interpretation.retrieval,
            resolution=interpretation.resolution,
            bundle=bundle,
            catalog=catalog,
            policy=self.planning_policy,
            authority_lane='reviewed_definition',
        )
        try:
            if (
                context.policy.paging_policy is not None
                and not self.gateway.supports_snapshot_result_paging(
                    context.policy.paging_policy.policy_digest
                )
            ):
                outcome = self._reviewed_plan_outcome(
                    status='BLOCKED',
                    reasons=('REVIEWED_SNAPSHOT_PAGING_CAPABILITY_UNAVAILABLE',),
                    interpretation=interpretation,
                    context=context,
                )
            else:
                request = self._cardinality_request(context)
                if request is None:
                    outcome = self._reviewed_plan_outcome(
                        status='BLOCKED',
                        reasons=('REVIEWED_RESULT_SHAPE_CONTRACT_REQUIRED',),
                        interpretation=interpretation,
                        context=context,
                    )
                else:
                    selection = solve_profile_bound_query_shape(
                        request,
                        bundle=context.bundle,
                        projection_policy=context.policy.nested_projection_policy,
                    )
                    if selection.status != 'READY':
                        outcome = self._reviewed_plan_outcome(
                            status=selection.status,
                            reasons=selection.solver_outcome.reason_codes,
                            interpretation=interpretation,
                            context=context,
                            selection=selection,
                        )
                    else:
                        if selection.projection_receipt is not None:
                            self.ledger.append(
                                RecordKind.CHECK,
                                selection.projection_receipt,
                                authority='mapping_validator',
                                occurred_at=self.occurred_at(),
                            )
                        semantic_plan = GenericResultShapePlanner().plan(
                            context, shape_selection=selection
                        )
                        physical_binding = PhysicalPlanBinder().bind(
                            semantic_plan, bundle=context.bundle
                        )
                        outcome = self._reviewed_plan_outcome(
                            status='READY',
                            reasons=(),
                            interpretation=interpretation,
                            context=context,
                            selection=selection,
                            semantic_plan=semantic_plan,
                            physical_binding=physical_binding,
                            parameters=self._resolved_parameters(context, semantic_plan),
                        )
        except QueryRootClarificationRequired:
            outcome = self._reviewed_plan_outcome(
                status='CLARIFICATION_REQUIRED',
                reasons=('ROOT_OBJECT_AMBIGUOUS',),
                interpretation=interpretation,
                context=context,
            )
        except (ValueError, RuntimeError) as error:
            outcome = self._reviewed_plan_outcome(
                status='BLOCKED',
                reasons=(_reason_code(error),),
                interpretation=interpretation,
                context=context,
            )
        validate_current_scope(bundle)
        return outcome

    def prepare_native_reviewed_question(self, question, *, bundle,
            validate_current_scope, clarification_context=None):
        """Present the current authorized input without invoking an inference engine."""
        from .semantic_intent import prepare_intent_input
        require_reviewed_semantic_authority(bundle)
        if bundle.bundle_digest != _digest(bundle.model_dump(mode='json', exclude={'bundle_digest'})):
            raise ValueError('REVIEWED_QUESTION_BUNDLE_DIGEST_INVALID')
        validate_current_scope(bundle)
        retrieval = self.reviewed_retriever.retrieve(question, bundle=bundle,
            top_k=self.retrieval_top_k, max_expanded_entries=self.max_expanded_entries)
        value = prepare_intent_input(question=question, retrieval=retrieval, bundle=bundle,
            clarification_context=clarification_context)
        validate_current_scope(bundle)
        return retrieval, value

    def interpret_submitted_native_question(self, question, *, submission, principal,
            bundle, validate_current_scope, clarification_context=None):
        """Resolve a direct native submission through the existing logical resolver.

        No local model identity, callback replay, execution or access grant is made.
        The enclosing authorized service supplies principal and scope validation.
        """
        from .semantic_intent import accept_native_intent
        retrieval, value = self.prepare_native_reviewed_question(question, bundle=bundle,
            validate_current_scope=validate_current_scope, clarification_context=clarification_context)
        synthesis = accept_native_intent(value, submission, principal=principal)
        resolution = None
        if not retrieval.candidates:
            status, reasons = 'BLOCKED', ('NO_AUTHORIZED_SEMANTIC_MATCH',)
        else:
            resolution = SemanticIntentResolver().resolve(synthesis.candidate,
                retrieval=retrieval, bundle=bundle, synthesis=synthesis)
            status, reasons = resolution.status, resolution.reason_codes
        validate_current_scope(bundle)
        body = {'contract_version':'boi/semantic-question-interpretation@1',
            **semantic_authority_values(bundle), 'status':status, 'reason_codes':reasons,
            'semantic_bundle_digest':bundle.bundle_digest,
            'retrieval':retrieval.model_dump(mode='json'),
            'synthesis':synthesis.model_dump(mode='json'),
            'resolution':resolution.model_dump(mode='json') if resolution else None,
            'execution_status':'not_run', 'semantic_equivalence_decided':False}
        return SemanticQuestionInterpretation.model_validate({**body, 'receipt_digest':_digest(body)})

    def interpret_reviewed_question(self, question, *, bundle, validate_current_scope,
            identity=None, synthesizer=None, clarification_context=None):
        """Use the common interpreter in an explicit noncanonical review scope.

        The Application Service validates the current scope before inference and
        again before retaining results. Planning/execution require their own
        frozen contracts and Gateway permission; this method grants neither.
        """
        if ((synthesizer or self.intent_synthesizer) is None
                or (identity is None and self.model_identity_provider is None)):
            raise ValueError('INTERNAL_INTENT_MODEL_UNAVAILABLE')
        if bundle.reviewed_definition_authority is None or bundle.active_release_digest is not None:
            raise ValueError('REVIEWED_QUESTION_SCOPE_REQUIRED')
        if bundle.bundle_digest != _digest(bundle.model_dump(mode='json',exclude={'bundle_digest'})):
            raise ValueError('REVIEWED_QUESTION_BUNDLE_DIGEST_INVALID')
        validate_current_scope(bundle)
        retrieval=self.reviewed_retriever.retrieve(question,bundle=bundle,top_k=self.retrieval_top_k,
            max_expanded_entries=self.max_expanded_entries)
        synthesis=None;resolution=None
        if not retrieval.candidates:
            reasons=('NO_AUTHORIZED_SEMANTIC_MATCH',);status='BLOCKED'
        else:
            synthesis=(synthesizer or self.intent_synthesizer).synthesize(question=question,
                retrieval=retrieval,bundle=bundle,identity=identity or self.model_identity_provider(),
                clarification_context=clarification_context)
            if synthesis.status!='READY' or synthesis.candidate is None:
                reasons=synthesis.reason_codes;status='BLOCKED'
            else:
                resolution=SemanticIntentResolver().resolve(synthesis.candidate,
                    retrieval=retrieval,bundle=bundle,synthesis=synthesis)
                reasons=resolution.reason_codes;status=resolution.status
        validate_current_scope(bundle)
        body={'contract_version':'boi/semantic-question-interpretation@1',
            **semantic_authority_values(bundle),'status':status,'reason_codes':reasons,
            'semantic_bundle_digest':bundle.bundle_digest,'retrieval':retrieval.model_dump(mode='json'),
            'synthesis':synthesis.model_dump(mode='json') if synthesis else None,
            'resolution':resolution.model_dump(mode='json') if resolution else None,
            'execution_status':'not_run','semantic_equivalence_decided':False}
        body['reviewed_definition_authority']=bundle.reviewed_definition_authority.model_dump(mode='json')
        return SemanticQuestionInterpretation.model_validate({**body,'receipt_digest':_digest(body)})

    def handle(
        self,
        question: str,
        *,
        principal: str,
        purpose: str,
        parameters: dict[str, Any] | None = None,
        request_id: str = "",
        team_ids: tuple[str, ...] = (),
        clarification_response: Mapping[str, str] | None = None,
    ) -> ProfileDrivenQueryRuntimeOutcome:
        if not question.strip():
            reasons = ("QUESTION_REQUIRED",)
            return ProfileDrivenQueryRuntimeOutcome(
                route="not_applicable",
                result_status="BLOCKED",
                catalog_snapshot_digest=self.catalog.snapshot_digest,
                reason_codes=reasons,
                answerability=self._answerability(
                    question, executable=False, reasons=reasons
                ),
            )
        if self.intent_synthesizer is None or self.model_identity_provider is None:
            return self._blocked('INTERNAL_INTENT_MODEL_UNAVAILABLE', question=question)
        self.token_metrics.record_deterministic()
        if parameters:
            return self._blocked(
                "EXTERNAL_PARAMETER_OVERRIDE_FORBIDDEN", question=question
            )
        if not principal.strip() or not purpose or purpose != purpose.strip():
            return self._blocked(
                "QUERY_AUTHORIZATION_CONTEXT_INVALID", question=question
            )
        if self.catalog.freshness_status != "CURRENT":
            return self._blocked("CATALOG_SNAPSHOT_NOT_CURRENT", question=question)

        occurred_at = self.occurred_at()
        resource_manifest = self.resource_manifest
        if clarification_response is not None:
            resource_manifest = resource_manifest.with_clarification()
        if self.grain_policy == 'snapshot-identity-v1':
            resource_manifest = resource_manifest.with_identity_grain()
        broker = CanonicalQueryResourceBroker(
            ledger=self.ledger,
            run_id=request_id or "query:" + _digest({
                "question": question,
                "principal": principal,
                "purpose": purpose,
            }).removeprefix("sha256:"),
            occurred_at=occurred_at,
            manifest=resource_manifest,
            entrypoint_closure_digest=self.entrypoint_closure.closure_digest,
        )
        question_ref = broker.publish(
            kind="question", value=question, consumers=("retrieval", "pi")
        )
        catalog_ref = broker.publish(
            kind="catalog",
            value=self.catalog,
            consumers=("profile_loader", "planner"),
            digest=self.catalog.snapshot_digest,
        )

        try:
            broker_catalog = broker.read(stage="profile_loader", ref=catalog_ref)
            if not isinstance(broker_catalog, PlannerCatalogSnapshot):
                raise ValueError("BROKER_CATALOG_TYPE_INVALID")
            profile_catalog = ProfileCatalogSnapshot(
                snapshot_digest=broker_catalog.snapshot_digest,
                schema_digest=broker_catalog.schema_digest,
                capability_digest=broker_catalog.capability_digest,
                authorized_source_ids=tuple(
                    source.source_id for source in broker_catalog.sources
                ),
                captured_at=broker_catalog.captured_at,
            )
            bundle = self.profile_loader.load(
                principal=ProfilePrincipal(
                    principal_id=principal, team_ids=tuple(sorted(set(team_ids)))
                ),
                purpose=purpose,
                catalog_snapshot=profile_catalog,
            )
            require_active_semantic_authority(bundle)
            bundle_ref = broker.publish(
                kind="profile_bundle",
                value=bundle,
                consumers=("retrieval", "pi", "resolver", "planner"),
                digest=bundle.bundle_digest,
            )
            identity = self.model_identity_provider()
            clarification_store = QueryClarificationStore(self.ledger)
            clarification_binding = {
                'question': question, 'principal': principal, 'purpose': purpose,
                'context_digest': _digest({'bundle': bundle.bundle_digest,
                    'catalog': self.catalog.snapshot_digest, 'policy': _digest(self.planning_policy),
                    'model': identity.model_digest, 'role': identity.role_digest,
                    'prompt': identity.prompt_digest, 'retrieval': self.retriever.policy_version,
                    'grain_policy': self.grain_policy,
                    'entrypoint': self.entrypoint_closure.closure_digest}),
            }
            continuation = None
            continuation_ref = None
            if clarification_response is not None:
                if set(clarification_response) != {'challenge_ref', 'option_id'}:
                    raise ValueError('CLARIFICATION_RESPONSE_INVALID')
                continuation = clarification_store.accept(
                    challenge_ref=clarification_response['challenge_ref'],
                    option_id=clarification_response['option_id'], binding=clarification_binding,
                    occurred_at=occurred_at)
                continuation_ref = broker.publish(kind='clarification_reply', value=continuation,
                                                   consumers=('pi','resolver'))
            retrieval_question = broker.read(stage="retrieval", ref=question_ref)
            retrieval_bundle = broker.read(stage="retrieval", ref=bundle_ref)
            retrieval = self.retriever.retrieve(
                str(retrieval_question),
                bundle=retrieval_bundle,
                top_k=self.retrieval_top_k,
                max_expanded_entries=self.max_expanded_entries,
            )
            if not retrieval.candidates:
                return self._blocked("NO_AUTHORIZED_SEMANTIC_MATCH", question=question)
            retrieval_ref = broker.publish(
                kind="retrieval_receipt",
                value=retrieval,
                consumers=("pi", "resolver", "planner"),
                digest=retrieval.receipt_digest,
            )
            stored_synthesis = clarification_store.reserve_inference(
                continuation, occurred_at=occurred_at) if continuation is not None else None
            if stored_synthesis is not None:
                synthesis = IntentSynthesisReceipt.model_validate(stored_synthesis)
            else:
                synthesis = self.intent_synthesizer.synthesize(
                    question=str(broker.read(stage="pi", ref=question_ref)),
                    retrieval=broker.read(stage="pi", ref=retrieval_ref),
                    bundle=broker.read(stage="pi", ref=bundle_ref),
                    identity=identity,
                    clarification_context=(broker.read(stage='pi', ref=continuation_ref)
                                           if continuation_ref is not None else None),
                )
                if continuation is not None:
                    clarification_store.finish_inference(continuation,
                        synthesis.model_dump(mode='json'), occurred_at=occurred_at)
            if synthesis.status != "READY" or synthesis.candidate is None:
                return self._blocked(*synthesis.reason_codes, question=question)
            if continuation is not None:
                continuation = broker.read(stage='resolver', ref=continuation_ref)
                if synthesis.candidate.ambiguity_alternatives or synthesis.candidate.unresolved_terms:
                    return self._blocked('CLARIFICATION_UNRESOLVED_AFTER_REPLY', question=question)
                selected_ids = set(continuation['selected_alternative']['logical_ids'])
                if not selected_ids <= SemanticIntentResolver._referenced_ids(synthesis.candidate):
                    return self._blocked('CLARIFICATION_CHOICE_NOT_PRESERVED', question=question)
                chosen_scope = continuation['selected_alternative'].get('filter_scope')
                if chosen_scope and any(f.scope != chosen_scope for f in synthesis.candidate.filters
                                        if f.property_id in selected_ids):
                    return self._blocked('CLARIFICATION_CHOICE_NOT_PRESERVED', question=question)
                chosen_quality = continuation['selected_alternative'].get('quality_detail')
                if chosen_quality:
                    requests = [item for item in synthesis.candidate.quality_requests if item.subject_object_id in selected_ids]
                    if not requests or any(item.detail != chosen_quality for item in requests):
                        return self._blocked('CLARIFICATION_CHOICE_NOT_PRESERVED', question=question)
            synthesis_ref = broker.publish(
                kind="intent_synthesis",
                value=synthesis,
                consumers=("resolver",),
                digest=synthesis.receipt_digest,
            )
            resolution = SemanticIntentResolver().resolve(
                broker.read(stage="resolver", ref=synthesis_ref).candidate,
                retrieval=broker.read(stage="resolver", ref=retrieval_ref),
                bundle=broker.read(stage="resolver", ref=bundle_ref),
                synthesis=broker.read(stage="resolver", ref=synthesis_ref),
            )
            if resolution.status == "CLARIFICATION_REQUIRED":
                if continuation is not None:
                    return self._blocked('CLARIFICATION_UNRESOLVED_AFTER_REPLY', question=question)
                alternatives = [a.model_dump(mode='json') for a in synthesis.candidate.ambiguity_alternatives]
                if not alternatives and 'FILTER_SCOPE_AMBIGUOUS' in resolution.reason_codes:
                    logical_entries = {e.entry_id:e.payload for e in bundle.domain_entries}
                    grain_owners = {logical_entries[ref].get('owner_ref') for ref in synthesis.candidate.grain}
                    filter_ids = [f.property_id for f in synthesis.candidate.filters
                                  if f.scope is None and logical_entries[f.property_id].get('owner_ref') not in grain_owners]
                    alternatives = [
                        {'label':label, 'logical_ids':filter_ids, 'filter_scope':scope}
                        for scope,label in (
                            ('COLLECTION_CONTENT','상위 목록은 유지하고 하위 목록만 조건으로 필터'),
                            ('ROOT_EXISTENCE','조건에 맞는 하위 항목이 있는 상위만 선택하고 하위 목록은 유지'),
                            ('ROOT_AND_COLLECTION','상위 선택과 하위 목록 모두 조건으로 필터'))]
                labels = tuple(
                    item['label'].strip() for item in alternatives if item['label'].strip()
                )
                choices = " / ".join(labels[:4])
                clarification = (
                    f"어느 의미를 원하시는지 한 번만 확인해주세요: {choices}"
                    if choices
                    else "결과가 달라지는 의미가 둘 이상입니다. 원하는 기준을 한 번만 지정해주세요."
                )
                return ProfileDrivenQueryRuntimeOutcome(
                    route="clarification_required",
                    clarification_count=1,
                    clarification=clarification,
                    clarification_challenge=clarification_store.issue(
                        request_id=request_id, binding=clarification_binding,
                        alternatives=alternatives,
                        candidate_digest=resolution.candidate_digest, occurred_at=occurred_at),
                    result_status="BLOCKED",
                    catalog_snapshot_digest=self.catalog.snapshot_digest,
                    reason_codes=resolution.reason_codes,
                    answerability=self._answerability(
                        question,
                        executable=False,
                        reasons=resolution.reason_codes,
                        active_release_digest=bundle.active_release_digest,
                    ),
                )
            if resolution.status != "RESOLVED" or resolution.resolved_intent is None:
                referenced = SemanticIntentResolver._referenced_ids(
                    synthesis.candidate
                )
                missing_dependencies = tuple(
                    sorted(referenced & set(bundle.unavailable_logical_ids))
                )
                if (
                    "FILTER_UNIT_CONVERSION_NOT_DECLARED"
                    in resolution.reason_codes
                ):
                    missing_dependencies = tuple(
                        sorted(
                            f"unit-conversion:{item.property_id}:{item.unit_ref}"
                            for item in synthesis.candidate.filters
                            if item.unit_ref
                        )
                    )
                return self._blocked(
                    *resolution.reason_codes,
                    question=question,
                    active_release_digest=bundle.active_release_digest,
                    missing_dependency_ids=missing_dependencies,
                )
            resolution_ref = broker.publish(
                kind="intent_resolution",
                value=resolution,
                consumers=("planner",),
                digest=resolution.receipt_digest,
            )
            planning_bundle = broker.read(stage="planner", ref=bundle_ref)
            planning_catalog = broker.read(stage="planner", ref=catalog_ref)
            planning_retrieval = broker.read(stage="planner", ref=retrieval_ref)
            planning_resolution = broker.read(stage="planner", ref=resolution_ref)
            context = SemanticPlanningContext.create(
                retrieval=planning_retrieval,
                resolution=planning_resolution,
                bundle=planning_bundle,
                catalog=planning_catalog,
                policy=self.planning_policy,
            )
            if self.grain_policy == 'snapshot-identity-v1':
                context_ref = broker.publish(kind='semantic_context', value=context, consumers=('key_profiler',))
                revised_resolution, proof = prove_identity_grain(
                    context=broker.read(stage='key_profiler', ref=context_ref),
                    gateway=self.gateway, occurred_at=occurred_at)
                if proof is not None:
                    revised_ref = broker.publish(kind='intent_resolution', value=revised_resolution,
                        consumers=('planner',), digest=revised_resolution.receipt_digest)
                    resolution = revised_resolution
                    context = SemanticPlanningContext.create(retrieval=planning_retrieval,
                        resolution=broker.read(stage='planner', ref=revised_ref), bundle=planning_bundle,
                        catalog=planning_catalog, policy=self.planning_policy)
            cardinality_plan = self._prepare_cardinality_plan(
                context,
                occurred_at=occurred_at,
            )
            if isinstance(cardinality_plan, ProfileBoundShapeSelection):
                shape_outcome = cardinality_plan.solver_outcome
                if cardinality_plan.status == "CLARIFICATION_REQUIRED":
                    if continuation is not None:
                        return self._blocked('CLARIFICATION_UNRESOLVED_AFTER_REPLY', question=question)
                    return ProfileDrivenQueryRuntimeOutcome(
                        route="clarification_required",
                        clarification_count=1,
                        clarification=(
                            "결과 모양에 따라 의미가 달라집니다. 원하는 "
                            "collection, aggregate 또는 flat grain을 한 번만 지정해주세요."
                        ),
                        result_status="BLOCKED",
                        catalog_snapshot_digest=self.catalog.snapshot_digest,
                        intent_digest=resolution.resolved_intent.intent_digest,
                        grain=resolution.resolved_intent.candidate.grain,
                        active_release_digest=bundle.active_release_digest,
                        profile_contract_binding_digest=(
                            cardinality_plan.profile_contracts.binding_digest
                        ),
                        shape_solver_outcome_digest=shape_outcome.outcome_digest,
                        shape_selection_receipt_digest=cardinality_plan.receipt_digest,
                        reason_codes=shape_outcome.reason_codes,
                        answerability=self._answerability(
                            question,
                            executable=False,
                            reasons=shape_outcome.reason_codes,
                            active_release_digest=bundle.active_release_digest,
                        ),
                    )
                return self._blocked(
                    *shape_outcome.reason_codes,
                    question=question,
                    intent_digest=resolution.resolved_intent.intent_digest,
                    grain=resolution.resolved_intent.candidate.grain,
                    active_release_digest=bundle.active_release_digest,
                    missing_dependency_ids=(
                        (f"required-contract:{shape_outcome.request_digest}",)
                        if set(shape_outcome.reason_codes)
                        & {
                            "RELATIONSHIP_CONTRACT_NOT_FOUND",
                            "RELATIONSHIP_PATH_NOT_DECLARED",
                            "APPROVED_RESULT_SHAPE_NOT_FOUND",
                            "RESULT_GRAIN_NOT_APPROVED",
                            "DATA_QUALITY_RECEIPT_MISSING",
                        }
                        else ()
                    ),
                ).model_copy(update={
                    "active_release_digest": bundle.active_release_digest,
                    "profile_contract_binding_digest": (
                        cardinality_plan.profile_contracts.binding_digest
                    ),
                    "shape_solver_outcome_digest": shape_outcome.outcome_digest,
                    "shape_selection_receipt_digest": cardinality_plan.receipt_digest,
                    "relationship_contract_digests": tuple(
                        item.contract_digest for item in shape_outcome.bound_relationships
                    ),
                    "quality_receipt_digests": tuple(
                        item.receipt_digest for item in shape_outcome.quality_receipts
                    ),
                })
            if context.resolved_intent.candidate.quality_requests and not isinstance(cardinality_plan, CanonicalMultiResultPlan):
                raise ValueError("QUALITY_DISCLOSURE_RELATIONSHIP_CONTRACT_REQUIRED")
            if isinstance(cardinality_plan, CanonicalMultiResultPlan):
                selection = cardinality_plan.shape_selection
                shape_outcome = selection.solver_outcome
                if context.resolved_intent.candidate.quality_requests:
                    from .query_quality_disclosure import validate_quality_requests
                    try:
                        quality_proof = validate_quality_requests(candidate=context.resolved_intent.candidate,
                            relationships=shape_outcome.bound_relationships, quality_receipts=shape_outcome.quality_receipts,
                            schema_digest=context.schema_digest)
                    except ValueError as error:
                        if str(error) != 'QUALITY_RECORD_ACCESS_CONTRACT_REQUIRED' or continuation is not None:
                            raise
                        alternative = context.resolved_intent.candidate.model_copy(update={
                            'quality_requests': tuple(item.model_copy(update={'detail':'SUMMARY'})
                                                      for item in context.resolved_intent.candidate.quality_requests)})
                        availability = validate_quality_requests(candidate=alternative,
                            relationships=shape_outcome.bound_relationships, quality_receipts=shape_outcome.quality_receipts,
                            schema_digest=context.schema_digest)
                        self.ledger.append(RecordKind.CHECK, {
                            'record_type':'quality_disclosure_alternative_preflight',
                            'original_candidate_digest':resolution.candidate_digest,
                            'not_an_accepted_candidate':True, 'alternative_availability':availability,
                        }, authority='mapping_validator', occurred_at=occurred_at)
                        # Offer an explicit supported disclosure alternative,
                        # never rewrite requested ROWS into SUMMARY. Retaining
                        # ROWS after this one reply returns the precise gap.
                        subjects = sorted({item.subject_object_id for item in context.resolved_intent.candidate.quality_requests if item.detail == 'ROWS'})
                        alternatives = [
                            {'label':'품질 영향 건수·미연결 요약으로 진행', 'logical_ids':subjects, 'quality_detail':'SUMMARY'},
                            {'label':'개별 행이 필요함 — 별도 조회 계약 필요', 'logical_ids':subjects, 'quality_detail':'ROWS'},
                        ]
                        return ProfileDrivenQueryRuntimeOutcome(route='clarification_required', result_status='BLOCKED',
                            clarification_count=1,
                            clarification='현재 관계 계약은 품질 요약을 제공합니다. 미연결 건수 요약으로 진행할까요, 개별 행 조회가 필요한가요?',
                            clarification_challenge=clarification_store.issue(request_id=request_id,
                                binding=clarification_binding, alternatives=alternatives,
                                candidate_digest=resolution.candidate_digest, occurred_at=occurred_at),
                            reason_codes=('QUALITY_DISCLOSURE_SCOPE_CHOICE',), active_release_digest=bundle.active_release_digest)
                    self.ledger.append(RecordKind.CHECK, quality_proof, authority='mapping_validator', occurred_at=occurred_at)
                idempotency_key = "profile-multi-query:" + _digest({
                    "question_digest": context.question_digest,
                    "semantic_context_digest": context.context_digest,
                    "shape_selection_receipt_digest": selection.receipt_digest,
                    "logical_plan_digest": cardinality_plan.logical_plan.plan_digest,
                    "parameters": cardinality_plan.parameters,
                    "request_id": request_id,
                }).removeprefix("sha256:")
                multi_request = MultiResultExploratoryExecutionRequest(
                    lane="exploratory",
                    logical_plan=cardinality_plan.logical_plan,
                    validation_receipt=cardinality_plan.validation_receipt,
                    physical_mappings=cardinality_plan.physical_mappings,
                    selected_relationship_ids=tuple(
                        item.contract_id for item in shape_outcome.bound_relationships
                    ),
                    quality_receipts=shape_outcome.quality_receipts,
                    parameters=cardinality_plan.parameters,
                    principal=principal,
                    purpose=purpose,
                    idempotency_key=idempotency_key,
                    inline_row_limit=min(1000, self.planning_policy.max_result_rows),
                    timeout_seconds=self.planning_policy.timeout_seconds,
                )
                request_ref = broker.publish(
                    kind="execution_request",
                    value=multi_request,
                    consumers=("gateway",),
                )
                freeze = broker.freeze(
                    candidate_digest=resolution.candidate_digest,
                    intent_digest=resolution.resolved_intent.intent_digest,
                    logical_plan_digest=cardinality_plan.logical_plan.plan_digest,
                    profile_bundle_digest=bundle.bundle_digest,
                    catalog_snapshot_digest=self.catalog.snapshot_digest,
                )
                if freeze.status != "FROZEN":
                    return self._blocked(
                        "PREFREEZE_ORACLE_ACCESS_DETECTED",
                        question=question,
                        intent_digest=resolution.resolved_intent.intent_digest,
                        grain=shape_outcome.selected_shape.exact_grain,
                        active_release_digest=bundle.active_release_digest,
                    )
                gateway_request = broker.read(stage="gateway", ref=request_ref)
                if not isinstance(
                    gateway_request, MultiResultExploratoryExecutionRequest
                ):
                    raise ValueError("BROKER_EXECUTION_REQUEST_TYPE_INVALID")
                multi_execution = self.gateway.create(gateway_request)
                if not isinstance(multi_execution, MultiResultQueryExecution):
                    raise ValueError("MULTI_RESULT_GATEWAY_EXECUTION_TYPE_INVALID")
                source_tables = tuple(dict.fromkeys(
                    f"{item.source_id}::{item.table}"
                    for item in cardinality_plan.logical_plan.result_sets
                ))
                prefreeze_access = freeze.access_receipt_digest
                answerability = self._answerability(
                    question,
                    executable=True,
                    active_release_digest=bundle.active_release_digest,
                )
                governed_artifact = GovernedAnswerArtifactBuilder.build_multi(
                    context=context,
                    plan=cardinality_plan.logical_plan,
                    execution=multi_execution,
                    shape_contract=shape_outcome.selected_shape,
                    quality_receipts=shape_outcome.quality_receipts,
                    answerability=answerability,
                    resource_access_receipt_digest=prefreeze_access,
                    resource_freeze_receipt_digest=freeze.receipt_digest,
                )
                return ProfileDrivenQueryRuntimeOutcome(
                    route="exploratory_semantic",
                    parameters=cardinality_plan.parameters,
                    result_status="PROVISIONAL",
                    execution=multi_execution,
                    plan_kind="multi_result",
                    plan_digest=cardinality_plan.logical_plan.plan_digest,
                    catalog_snapshot_digest=self.catalog.snapshot_digest,
                    plan_cache_status="NOT_APPLICABLE",
                    source_tables=source_tables,
                    join_path=tuple(
                        item.contract_id for item in shape_outcome.bound_relationships
                    ),
                    intent_digest=resolution.resolved_intent.intent_digest,
                    grain=shape_outcome.selected_shape.exact_grain,
                    active_release_digest=bundle.active_release_digest,
                    profile_contract_binding_digest=(
                        selection.profile_contracts.binding_digest
                    ),
                    shape_solver_outcome_digest=shape_outcome.outcome_digest,
                    shape_selection_receipt_digest=selection.receipt_digest,
                    relationship_contract_digests=tuple(
                        item.contract_digest for item in shape_outcome.bound_relationships
                    ),
                    quality_receipt_digests=tuple(
                        item.receipt_digest for item in shape_outcome.quality_receipts
                    ),
                    answerability=answerability,
                    governed_answer_artifact=governed_artifact,
                    resource_manifest_digest=self.resource_manifest.manifest_digest,
                    entrypoint_closure_digest=self.entrypoint_closure.closure_digest,
                    resource_access_receipt_digest=prefreeze_access,
                    resource_freeze_receipt_digest=freeze.receipt_digest,
                    resource_access_count=len(freeze.observed_resource_digests),
                    denied_oracle_access_count=freeze.denied_oracle_access_count,
                )
            prepared = (
                cardinality_plan.preparation
                if isinstance(cardinality_plan, CanonicalSingleResultPlan)
                else self._prepare(context, occurred_at=occurred_at)
            )
            if prepared.cache_status == "HIT":
                self.token_metrics.record_cache_hit()
            intent = resolution.resolved_intent
            single_shape_selection = (
                cardinality_plan.shape_selection
                if isinstance(cardinality_plan, CanonicalSingleResultPlan)
                else None
            )
            if (
                prepared.status != "READY"
                or prepared.binding_receipt is None
                or prepared.plan is None
                or prepared.validation_receipt is None
            ):
                blocked = self._blocked(
                    *prepared.reason_codes,
                    question=question,
                    intent_digest=intent.intent_digest,
                    grain=intent.candidate.grain,
                    active_release_digest=bundle.active_release_digest,
                    missing_dependency_ids=tuple(
                        sorted(
                            {
                                *intent.candidate.property_ids,
                                *intent.candidate.dimensions,
                                *intent.candidate.grain,
                            }
                            - {
                                item.logical_id
                                for item in prepared.binding_receipt.field_bindings
                            }
                        )
                    )
                    if set(prepared.reason_codes)
                    & {"UNBOUND_PROPERTY", "QUERY_LOCAL_MAPPING_NOT_BOUND"}
                    else (),
                )
                if single_shape_selection is not None:
                    shape_outcome = single_shape_selection.solver_outcome
                    blocked = blocked.model_copy(update={
                        "active_release_digest": bundle.active_release_digest,
                        "profile_contract_binding_digest": (
                            single_shape_selection.profile_contracts.binding_digest
                        ),
                        "shape_solver_outcome_digest": shape_outcome.outcome_digest,
                        "shape_selection_receipt_digest": (
                            single_shape_selection.receipt_digest
                        ),
                        "relationship_contract_digests": tuple(
                            item.contract_digest
                            for item in shape_outcome.bound_relationships
                        ),
                        "quality_receipt_digests": tuple(
                            item.receipt_digest for item in shape_outcome.quality_receipts
                        ),
                    })
                return blocked
            compiled = SemanticSqliteCompiler().compile(
                prepared.plan,
                context=context,
                binding=prepared.binding_receipt,
            )
            idempotency_key = "profile-query:" + _digest(
                {
                    "question_digest": context.question_digest,
                    "semantic_context_digest": context.context_digest,
                    "parameters": compiled.parameter_bindings,
                    "request_id": request_id,
                }
            ).removeprefix("sha256:")
            request = SemanticExploratoryExecutionRequest(
                lane="exploratory",
                semantic_context=context,
                binding_receipt=prepared.binding_receipt,
                logical_plan=prepared.plan,
                validation_receipt=prepared.validation_receipt,
                logical_plan_ref=f"runtime-plan:{prepared.plan.plan_digest}",
                plan_reuse_receipt=prepared.plan_reuse_receipt,
                parameters=compiled.parameter_bindings,
                principal=principal,
                purpose=purpose,
                idempotency_key=idempotency_key,
                timeout_seconds=self.planning_policy.timeout_seconds,
                row_limit=self.planning_policy.max_result_rows,
            )
            request_ref = broker.publish(
                kind="execution_request",
                value=request,
                consumers=("gateway",),
            )
            freeze = broker.freeze(
                candidate_digest=resolution.candidate_digest,
                intent_digest=intent.intent_digest,
                logical_plan_digest=prepared.plan.plan_digest,
                profile_bundle_digest=bundle.bundle_digest,
                catalog_snapshot_digest=self.catalog.snapshot_digest,
            )
            if freeze.status != "FROZEN":
                return self._blocked(
                    "PREFREEZE_ORACLE_ACCESS_DETECTED",
                    question=question,
                    intent_digest=intent.intent_digest,
                    grain=intent.candidate.grain,
                    active_release_digest=bundle.active_release_digest,
                )
            gateway_request = broker.read(stage="gateway", ref=request_ref)
            if not isinstance(gateway_request, SemanticExploratoryExecutionRequest):
                raise ValueError("BROKER_EXECUTION_REQUEST_TYPE_INVALID")
            execution = self.gateway.create(gateway_request)
            if not isinstance(execution, QueryExecution):
                raise ValueError("SINGLE_RESULT_GATEWAY_EXECUTION_TYPE_INVALID")
            promotion = None
            exploration = execution.exploration_receipt
            if self.plan_store is not None and exploration is not None:
                candidate_ids = exploration.cold_path_trace.promotion_candidate_ids
                if candidate_ids:
                    promotion = next(
                        (
                            item
                            for item in self.plan_store.promotion_candidates(
                                ledger=self.ledger
                            )
                            if item.candidate_id == candidate_ids[0]
                        ),
                        None,
                    )
            answerability = self._answerability(
                question,
                executable=True,
                active_release_digest=bundle.active_release_digest,
            )
            single_shape = (
                single_shape_selection.solver_outcome.selected_shape
                if single_shape_selection is not None else None
            )
            single_quality = (
                single_shape_selection.solver_outcome.quality_receipts
                if single_shape_selection is not None else ()
            )
            governed_artifact = GovernedAnswerArtifactBuilder.build_single(
                context=context,
                binding=prepared.binding_receipt,
                plan=prepared.plan,
                execution=execution,
                shape_contract=single_shape,
                quality_receipts=single_quality,
                answerability=answerability,
                resource_access_receipt_digest=freeze.access_receipt_digest,
                resource_freeze_receipt_digest=freeze.receipt_digest,
            )
            return ProfileDrivenQueryRuntimeOutcome(
                route="exploratory_semantic",
                parameters=compiled.parameter_bindings,
                result_status="PROVISIONAL",
                execution=execution,
                plan_kind="single_result",
                plan_digest=prepared.plan.plan_digest,
                catalog_snapshot_digest=self.catalog.snapshot_digest,
                plan_cache_status=prepared.cache_status,
                plan_cache_key=(
                    self.plan_store.cache_key(
                        context, intent_digest=intent.intent_digest
                    )
                    if self.plan_store is not None
                    else ""
                ),
                promotion_candidate=promotion,
                source_tables=tuple(
                    f"{source_id}::{table}"
                    for source_id, table in prepared.binding_receipt.source_tables
                ),
                join_path=tuple(
                    item.relation_id
                    for item in prepared.binding_receipt.relationship_path
                ),
                intent_digest=intent.intent_digest,
                grain=intent.candidate.grain,
                active_release_digest=bundle.active_release_digest,
                profile_contract_binding_digest=(
                    single_shape_selection.profile_contracts.binding_digest
                    if single_shape_selection is not None
                    else ""
                ),
                shape_solver_outcome_digest=(
                    single_shape_selection.solver_outcome.outcome_digest
                    if single_shape_selection is not None
                    else ""
                ),
                shape_selection_receipt_digest=(
                    single_shape_selection.receipt_digest
                    if single_shape_selection is not None
                    else ""
                ),
                relationship_contract_digests=(
                    tuple(
                        item.contract_digest
                        for item in single_shape_selection.solver_outcome.bound_relationships
                    )
                    if single_shape_selection is not None
                    else ()
                ),
                quality_receipt_digests=(
                    tuple(
                        item.receipt_digest
                        for item in single_shape_selection.solver_outcome.quality_receipts
                    )
                    if single_shape_selection is not None
                    else ()
                ),
                answerability=answerability,
                governed_answer_artifact=governed_artifact,
                resource_manifest_digest=self.resource_manifest.manifest_digest,
                entrypoint_closure_digest=self.entrypoint_closure.closure_digest,
                resource_access_receipt_digest=freeze.access_receipt_digest,
                resource_freeze_receipt_digest=freeze.receipt_digest,
                resource_access_count=len(freeze.observed_resource_digests),
                denied_oracle_access_count=freeze.denied_oracle_access_count,
            )
        except QueryRootClarificationRequired as error:
            if continuation is not None:
                return self._blocked('CLARIFICATION_UNRESOLVED_AFTER_REPLY', question=question)
            return ProfileDrivenQueryRuntimeOutcome(
                route="clarification_required",
                clarification_count=1,
                clarification="결과의 기준 객체를 한 번만 선택해주세요: " + " / ".join(
                    label for _ref, label in error.options
                ),
                clarification_challenge=clarification_store.issue(
                    request_id=request_id, binding=clarification_binding,
                    alternatives=[{'label':label,'logical_ids':[ref]} for ref,label in error.options],
                    candidate_digest=resolution.candidate_digest, occurred_at=occurred_at),
                result_status="BLOCKED",
                catalog_snapshot_digest=self.catalog.snapshot_digest,
                active_release_digest=bundle.active_release_digest,
                reason_codes=("ROOT_OBJECT_AMBIGUOUS",),
                answerability=self._answerability(
                    question, executable=False, reasons=("ROOT_OBJECT_AMBIGUOUS",),
                    active_release_digest=bundle.active_release_digest,
                ),
            )
        except QueryShapeContractGap as error:
            return self._blocked(
                "RESULT_GRAIN_NOT_APPROVED", question=question,
                active_release_digest=bundle.active_release_digest,
                missing_dependency_ids=(error.dependency_ref,),
            )
        except LatestContractGap as error:
            return self._blocked(str(error), question=question,
                active_release_digest=bundle.active_release_digest,
                missing_dependency_ids=(error.dependency_ref,))
        except Exception as error:
            return self._blocked(_reason_code(error), question=question)


class ProfileDrivenRuntimeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProfileDrivenRuntimeAssembly:
    gateway: QueryGatewayService
    runtime: ProfileDrivenQueryRuntime
    catalog: PlannerCatalogSnapshot
    token_metrics: TokenRoutingMetrics
    configuration_digest: str


_REQUIRED_CONFIGURATION = (
    "BOI_PROFILE_QUERY_DATABASE",
    "BOI_PROFILE_QUERY_LEDGER_ROOT",
    "BOI_PROFILE_QUERY_OBJECT_ROOT",
    "BOI_PROFILE_QUERY_EVIDENCE_ROOT",
    "BOI_PROFILE_QUERY_RESULT_ARTIFACT_ROOT",
    "BOI_PROFILE_QUERY_SOURCE_ID",
    "BOI_PROFILE_QUERY_ALLOWED_TABLES",
    "BOI_PROFILE_QUERY_CATALOG_CAPTURED_AT",
    "BOI_PROFILE_QUERY_PI_BASE_URL",
    "BOI_PROFILE_QUERY_PI_MODEL_DIGEST",
    "BOI_PROFILE_QUERY_EMBEDDING_BASE_URL",
    "BOI_PROFILE_QUERY_EMBEDDING_MODEL_ID",
    "BOI_PROFILE_QUERY_EMBEDDING_MODEL_DIGEST",
    "BOI_PROFILE_QUERY_EMBEDDING_DIMENSIONS",
)
_CACHE_CONFIGURATION = (
    "BOI_PROFILE_QUERY_PLAN_CACHE_ROOT",
    "BOI_PROFILE_QUERY_QUALIFICATION_RECEIPT",
    "BOI_PROFILE_QUERY_QUALIFICATION_DIGEST",
)


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def build_profile_driven_runtime_from_environment(
    environ: Mapping[str, str],
) -> ProfileDrivenRuntimeAssembly | None:
    """Build the canonical runtime only from a complete explicit contract.

    An enabled but partial configuration raises and must leave both the Agent
    runtime and Gateway unavailable.  It never falls back to the historical
    registered/family implementation.
    """

    if not _enabled(environ.get("BOI_PROFILE_QUERY_ENABLED")):
        return None
    missing = tuple(
        key
        for key in _REQUIRED_CONFIGURATION
        if not str(environ.get(key) or "").strip()
    )
    if missing:
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_CONFIG_MISSING:" + ",".join(missing)
        )
    cache_values = tuple(
        bool(str(environ.get(key) or "").strip()) for key in _CACHE_CONFIGURATION
    )
    if any(cache_values) and not all(cache_values):
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_CACHE_CONFIG_INCOMPLETE"
        )

    database = Path(str(environ["BOI_PROFILE_QUERY_DATABASE"]).strip())
    if not database.is_file():
        raise ProfileDrivenRuntimeConfigurationError("PROFILE_QUERY_DATABASE_NOT_FOUND")
    allowed_tables = tuple(
        dict.fromkeys(
            value.strip()
            for value in str(environ["BOI_PROFILE_QUERY_ALLOWED_TABLES"]).split(",")
            if value.strip()
        )
    )
    if not allowed_tables:
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_ALLOWED_TABLES_REQUIRED"
        )
    captured_at = str(environ["BOI_PROFILE_QUERY_CATALOG_CAPTURED_AT"]).strip()
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_CAPTURED_AT_INVALID"
        ) from error

    model_id = str(
        environ.get("BOI_PROFILE_QUERY_PI_MODEL_ID") or "qwen3.8-27b"
    ).strip()
    model_digest = str(environ["BOI_PROFILE_QUERY_PI_MODEL_DIGEST"]).strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", model_digest):
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_PI_MODEL_DIGEST_INVALID"
        )
    embedding_model_digest = str(
        environ["BOI_PROFILE_QUERY_EMBEDDING_MODEL_DIGEST"]
    ).strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", embedding_model_digest):
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_EMBEDDING_MODEL_DIGEST_INVALID"
        )
    try:
        embedding_dimensions = int(
            str(environ["BOI_PROFILE_QUERY_EMBEDDING_DIMENSIONS"]).strip()
        )
    except ValueError as error:
        raise ProfileDrivenRuntimeConfigurationError(
            "PROFILE_QUERY_EMBEDDING_DIMENSIONS_INVALID"
        ) from error
    try:
        embedding_client = LocalEmbeddingClient(
            base_url=str(
                environ["BOI_PROFILE_QUERY_EMBEDDING_BASE_URL"]
            ).strip(),
            model_id=str(
                environ["BOI_PROFILE_QUERY_EMBEDDING_MODEL_ID"]
            ).strip(),
            model_digest=embedding_model_digest,
            dimensions=embedding_dimensions,
        )
    except ValueError as error:
        raise ProfileDrivenRuntimeConfigurationError(str(error)) from error
    catalog = capture_sqlite_planner_catalog(
        database,
        source_id=str(environ["BOI_PROFILE_QUERY_SOURCE_ID"]).strip(),
        allowed_tables=allowed_tables,
        captured_at=captured_at,
    )
    ledger = GovernedRuntimeLedger(
        Path(str(environ["BOI_PROFILE_QUERY_LEDGER_ROOT"]).strip())
    )
    evidence = CheckEvidenceStore(
        Path(str(environ["BOI_PROFILE_QUERY_EVIDENCE_ROOT"]).strip())
    )
    object_store = KnowledgeObjectStore(
        Path(str(environ["BOI_PROFILE_QUERY_OBJECT_ROOT"]).strip())
    )
    plan_store = None
    if all(cache_values):
        receipt_path = Path(
            str(environ["BOI_PROFILE_QUERY_QUALIFICATION_RECEIPT"]).strip()
        )
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProfileDrivenRuntimeConfigurationError(
                "PROFILE_QUERY_QUALIFICATION_RECEIPT_INVALID"
            ) from error
        plan_store = QualifiedSemanticPlanStore(
            Path(str(environ["BOI_PROFILE_QUERY_PLAN_CACHE_ROOT"]).strip()),
            qualification_receipt=receipt,
            expected_qualification_digest=str(
                environ["BOI_PROFILE_QUERY_QUALIFICATION_DIGEST"]
            ).strip(),
        )
    multi_result_schema = capture_multi_result_sqlite_schema(
        database,
        allowed_tables=allowed_tables,
    )
    # Explicit default-off, isolated candidate-preview capability revision. No
    # caller/model supplied paging policy and no production activation shortcut.
    from .snapshot_result_paging import SnapshotPagingPolicy, SnapshotResultPager
    paging_policy = None
    snapshot_pager = None
    paging_path = environ.get("BOI_PROFILE_QUERY_PAGING_POLICY_PATH")
    if paging_path:
        if environ.get("BOI_PROFILE_QUERY_PAGING_SCOPE") != "isolated_candidate_preview":
            raise ProfileDrivenRuntimeConfigurationError("PAGING_PREVIEW_SCOPE_REQUIRED")
        try:
            paging_policy = SnapshotPagingPolicy.model_validate_json(Path(str(paging_path)).read_bytes())
        except (OSError, ValueError) as error:
            raise ProfileDrivenRuntimeConfigurationError("PAGING_POLICY_INVALID") from error
        if paging_policy.policy_digest != environ.get("BOI_PROFILE_QUERY_PAGING_POLICY_DIGEST"):
            raise ProfileDrivenRuntimeConfigurationError("PAGING_POLICY_DIGEST_MISMATCH")
        page_loader = ActiveReleaseProfileLoader(ledger, object_store)
        page_catalog = ProfileCatalogSnapshot(snapshot_digest=catalog.snapshot_digest,
            schema_digest=catalog.schema_digest, capability_digest=catalog.capability_digest,
            authorized_source_ids=tuple(source.source_id for source in catalog.sources),
            captured_at=catalog.captured_at)

        def authorize_page(principal, purpose, binding):
            try:
                # No untrusted team list from cursors. This preview policy is
                # public/owner only; current authenticated group resolution is
                # required before enabling team-only paging in production.
                visible = page_loader.load(principal=ProfilePrincipal(principal_id=principal, team_ids=()),
                    purpose=purpose, catalog_snapshot=page_catalog)
                return all(getattr(visible, key) == binding[key] for key in (
                    "active_release_digest", "query_profile_digest", "domain_profile_digest", "mapping_profile_digest"))
            except Exception:
                return False

        snapshot_pager = SnapshotResultPager(
            Path(str(environ["BOI_PROFILE_QUERY_RESULT_ARTIFACT_ROOT"])) / "snapshot-pages",
            database, authorize=authorize_page,
            approved_policy_digests=(paging_policy.policy_digest,))
    from .protected_execution_repository import ProtectedExecutionRepository
    execution_repository = ProtectedExecutionRepository(
        Path(str(environ['BOI_PROFILE_QUERY_RESULT_ARTIFACT_ROOT']))/'executions', ledger)
    from .query_gateway import metadata_quality_grant_resolver_from_environment
    metadata_quality_grant_resolver=metadata_quality_grant_resolver_from_environment(environ)
    gateway = QueryGatewayService(
        None,
        semantic_path=database,
        semantic_ledger=ledger,
        semantic_evidence_store=evidence,
        semantic_plan_store=plan_store,
        metadata_quality_grant_resolver=metadata_quality_grant_resolver,
        multi_result_gateway=MultiResultSqliteGateway(
            database,
            schema=multi_result_schema,
            result_artifact_root=Path(
                str(environ["BOI_PROFILE_QUERY_RESULT_ARTIFACT_ROOT"]).strip()
            ),
            contract_schema_digest=catalog.schema_digest,
            snapshot_pager=snapshot_pager,
            execution_repository=execution_repository,
        ),
        schema_release_digest=catalog.schema_digest,
    )
    def record_symbol_transport(payload):
        from . import logical_symbol_codec
        ledger.append(RecordKind.RUN,
            {"record_type":"logical_symbol_transport_receipt", **payload,
             "codec_code_digest":"sha256:"+hashlib.sha256(Path(logical_symbol_codec.__file__).read_bytes()).hexdigest()},
            authority="executor", occurred_at=datetime.now(timezone.utc).isoformat())

    client = NinferIntentClient(
        base_url=str(environ["BOI_PROFILE_QUERY_PI_BASE_URL"]).strip(),
        model_id=model_id,
        model_digest=model_digest,
        input_encoding=str(environ.get("BOI_PROFILE_QUERY_PI_INPUT_ENCODING") or "full-v1"),
        inference_policy=str(environ.get("BOI_PROFILE_QUERY_PI_INFERENCE_POLICY") or "thinking-low-v1"),
        intent_contract=str(environ.get("BOI_PROFILE_QUERY_INTENT_CONTRACT") or "typed-intent-v1"),
        meaning_policy=str(environ.get("BOI_PROFILE_QUERY_MEANING_POLICY") or "legacy-v1"),
        transport_receipt_sink=record_symbol_transport,
    )
    token_metrics = TokenRoutingMetrics()
    nested_projection_policy=str(environ.get('BOI_PROFILE_QUERY_NESTED_PROJECTION_POLICY') or 'exact-v1')
    if nested_projection_policy != 'exact-v1' and environ.get('BOI_PROFILE_QUERY_NESTED_PROJECTION_SCOPE') != 'isolated_candidate_preview':
        raise ProfileDrivenRuntimeConfigurationError('NESTED_PROJECTION_PREVIEW_SCOPE_REQUIRED')
    policy = PlanningPolicy(
        policy_id=("boi.semantic-exploratory@0.2.0-candidate-paging" if paging_policy else "boi.semantic-exploratory@0.1.0"),
        allowed_relationship_authorities=("schema_defined", "steward_verified"),
        nested_projection_policy=nested_projection_policy,
        allowed_join_kinds=("inner", "left"),
        max_physical_sources=1,
        max_scan_tables=3,
        cross_database_allowed=False,
        max_estimated_rows=1_000_000,
        max_result_rows=1000,
        timeout_seconds=30,
        required_dialect="sqlite",
        paging_policy=paging_policy,
    )
    runtime = ProfileDrivenQueryRuntime(
        profile_loader=ActiveReleaseProfileLoader(ledger, object_store),
        catalog=catalog,
        retriever=HybridSemanticRetriever(
            embedding_provider=embedding_client,
            embedding_identity_digest=embedding_client.identity_digest,
            policy_version=str(environ.get("BOI_PROFILE_QUERY_RETRIEVAL_POLICY") or "dependency-v1"),
        ),
        intent_synthesizer=PiIntentSynthesizer(
            model=client,
            policy=LocalModelPolicy(model_id=f"ninfer-local/{model_id}"),
            metrics=token_metrics,
        ),
        model_identity_provider=client.probe_identity,
        planning_policy=policy,
        gateway=gateway,
        ledger=ledger,
        evidence_store=evidence,
        plan_store=plan_store,
        token_metrics=token_metrics,
        auto_route_enabled=_enabled(environ.get("BOI_PROFILE_QUERY_AUTO_ROUTE")),
        grain_policy=str(environ.get('BOI_PROFILE_QUERY_GRAIN_POLICY') or 'strict-v1'),
    )
    safe_configuration = {
        'grain_policy': runtime.grain_policy,
        "database_digest": "sha256:"
        + hashlib.sha256(database.read_bytes()).hexdigest(),
        "source_id": str(environ["BOI_PROFILE_QUERY_SOURCE_ID"]).strip(),
        "allowed_tables": allowed_tables,
        "catalog_snapshot_digest": catalog.snapshot_digest,
        "schema_digest": catalog.schema_digest,
        "capability_digest": catalog.capability_digest,
        "multi_result_physical_schema_digest": multi_result_schema.schema_digest,
        "model_id": f"ninfer-local/{model_id}",
        "model_digest": model_digest,
        "embedding_model_id": embedding_client.model_id,
        "embedding_model_digest": embedding_client.model_digest,
        "embedding_dimensions": embedding_client.dimensions,
        "embedding_identity_digest": embedding_client.identity_digest,
        "policy_digest": policy.policy_digest,
        "cache_enabled": plan_store is not None,
        "auto_route_enabled": runtime.auto_route_enabled,
        "retrieval_policy": runtime.retriever.policy_version,
        "pi_input_encoding": client.input_encoding,
        "pi_inference_policy": client.inference_policy,
        **({"pi_intent_contract": client.intent_contract} if client.intent_contract != "typed-intent-v1" else {}),
        **({"pi_meaning_policy": client.meaning_policy} if client.meaning_policy != "legacy-v1" else {}),
        **({'metadata_quality_grant_digest':_digest(metadata_quality_grant_resolver().model_dump(mode='json'))}
            if metadata_quality_grant_resolver else {}),
    }
    return ProfileDrivenRuntimeAssembly(
        gateway=gateway,
        runtime=runtime,
        catalog=catalog,
        token_metrics=token_metrics,
        configuration_digest=_digest(safe_configuration),
    )
