"""Convert an actual native planning outcome to the existing protected Gateway.

No SQL, source lookup, inference or authority resolver is supplied here. The
authorized host must bind and revalidate its actual source and current Wiki scope.
"""
from .profile_driven_query_runtime import ReviewedSemanticPlanOutcome
from .semantic_authority import NativeReviewedDefinitionAuthority
from .semantic_binding_contract import semantic_digest
from .multi_result_query_gateway import (
    NativeQueryAuthority, MultiResultExploratoryExecutionRequest, MultiResultParameterSpec,
    create_multi_result_logical_plan, validate_multi_result_plan_authority,
)


def read_native_query_result(gateway, *, request, artifact_ref):
    """Read an authorized saved result for this exact native request, without SQL.

    The Gateway's host resolver must still check current Wiki and source scope.
    Access to a saved result alone does not make it the result of this request.
    """
    request = MultiResultExploratoryExecutionRequest.model_validate(request)
    plan = request.logical_plan
    authority = plan.candidate_authority
    if not isinstance(authority, NativeQueryAuthority):
        raise ValueError('NATIVE_RESULT_AUTHORITY_REQUIRED')
    artifact = gateway.read_result_artifact(artifact_ref,
        principal=request.principal, purpose=request.purpose)
    expected = {
        'candidate_authority': authority.model_dump(mode='json'),
        'logical_plan_digest': plan.plan_digest,
        'parameter_digest': semantic_digest(request.parameters),
        'source_snapshot_digest': authority.source_snapshot_digest,
        'schema_digest': plan.schema_digest,
        'active_release_digest': None,
    }
    if (any(artifact.get(key) != value for key, value in expected.items())
        or tuple(artifact.get('quality_receipt_digests', ())) != plan.quality_receipt_digests):
        raise ValueError('NATIVE_RESULT_REQUEST_MISMATCH')
    return artifact


def prepare_native_query_request(outcome, *, profile_revision, source_snapshot_digest,
                                 request_authorization_digest, idempotency_key):
    outcome = ReviewedSemanticPlanOutcome.model_validate(outcome)
    authority = outcome.reviewed_definition_authority
    if (outcome.status != "READY" or not isinstance(authority, NativeReviewedDefinitionAuthority)
        or outcome.physical_binding is None or outcome.semantic_plan is None
        or outcome.shape_selection is None):
        raise ValueError("NATIVE_READY_PLAN_REQUIRED")
    context = outcome.planning_context
    bundle = context.bundle
    physical = outcome.physical_binding
    selection = outcome.shape_selection
    query_authority = NativeQueryAuthority(
        contract_version="boi/native-query-authority@1", principal=authority.principal,
        purpose=authority.purpose, definition_authority=authority,
        profile_revision=profile_revision, planning_outcome_digest=outcome.outcome_digest,
        source_snapshot_digest=source_snapshot_digest,
        parameter_digest=semantic_digest(outcome.parameters),
        request_authorization_digest=request_authorization_digest,
    )
    relationships = tuple(r.contract_id for r in selection.solver_outcome.bound_relationships)
    quality = selection.solver_outcome.quality_receipts
    plan = create_multi_result_logical_plan(
        shape_solver_outcome_digest=selection.solver_outcome.outcome_digest,
        profile_contract_binding_digest=selection.profile_contracts.binding_digest,
        active_release_digest=None, candidate_authority=query_authority,
        domain_profile_digest=bundle.domain_profile_digest,
        mapping_profile_digest=bundle.mapping_profile_digest,
        query_profile_digest=bundle.query_profile_digest, schema_digest=bundle.schema_digest,
        result_sets=physical.result_sets,
        parameter_specs=tuple(MultiResultParameterSpec.model_validate(s.model_dump(mode="json"))
                              for s in outcome.semantic_plan.parameter_specs),
        quality_receipt_digests=tuple(q.receipt_digest for q in quality),
    )
    validation = validate_multi_result_plan_authority(plan,
        physical_mappings=physical.physical_mappings, selected_relationship_ids=relationships)
    return MultiResultExploratoryExecutionRequest(
        lane="exploratory", logical_plan=plan, validation_receipt=validation,
        physical_mappings=physical.physical_mappings, selected_relationship_ids=relationships,
        quality_receipts=quality, parameters=outcome.parameters,
        principal=authority.principal, purpose=authority.purpose,
        idempotency_key=idempotency_key, inline_row_limit=min(context.policy.max_result_rows, 1000),
        timeout_seconds=context.policy.timeout_seconds,
    )
