"""Native query results in the existing governed answer model, without fake Release/review receipts."""
from typing import Literal
from pydantic import model_validator
from .governed_answer_artifact import (
    GovernedAnswerArtifact, GovernedAnswerArtifactBuilder, ArtifactExecutionEvidence, _semantic_projection,
)
from .multi_result_query_gateway import MultiResultQueryExecution, MultiResultExploratoryExecutionRequest, NativeQueryAuthority
from .semantic_binding_contract import Digest, Ref, semantic_digest
from .native_query_execution import read_native_query_result, prepare_native_query_request


class NativeGovernedAnswerArtifact(GovernedAnswerArtifact):
    schema_name: Literal['boi-governed-answer-artifact/v6'] = 'boi-governed-answer-artifact/v6'
    active_release_digest: None = None
    candidate_authority: NativeQueryAuthority
    planning_outcome_digest: Digest
    protected_artifact_ref: Ref
    protected_artifact_digest: Digest
    answerability_state: Literal['native_review_pending'] = 'native_review_pending'
    answerability_receipt_digest: None = None
    resource_access_receipt_digest: None = None
    resource_freeze_receipt_digest: None = None

    def _authority_digest_values(self):
        return (self.question_digest, self.planning_outcome_digest, self.protected_artifact_digest)

    def _review_and_resource_digest_values(self):
        # Current native authority is real; no bulk resource or semantic review
        # receipt exists. Literal-None fields prohibit manufacturing one here.
        return ()

    @model_validator(mode='after')
    def native_binding(self):
        authority = self.candidate_authority
        if (authority.planning_outcome_digest != self.planning_outcome_digest
            or semantic_digest(authority.principal) != self.principal_digest
            or semantic_digest(authority.purpose) != self.purpose_digest
            or authority.source_snapshot_digest != self.execution.source_snapshot_digest
            or self.protected_artifact_ref != 'protected:multi-result:'+self.protected_artifact_digest
            or self.execution.classification != 'PROVISIONAL'
            or self.execution.lane != 'exploratory'
            or self.execution.attestation_state != 'ABSENT'):
            raise ValueError('NATIVE_ANSWER_AUTHORITY_MISMATCH')
        return self


def validate_native_answer_execution(gateway, *, request, execution):
    """Validate supplied execution against the current-authorized immutable result."""
    request = MultiResultExploratoryExecutionRequest.model_validate(request)
    execution = MultiResultQueryExecution.model_validate(execution)
    receipt = execution.receipt
    artifact = read_native_query_result(gateway, request=request, artifact_ref=receipt.result_artifact_ref)
    plan = request.logical_plan
    expected = {'logical_plan_digest':plan.plan_digest,
        'validation_receipt_digest':request.validation_receipt.receipt_digest,
        'candidate_authority':plan.candidate_authority,
        'parameter_digest':semantic_digest(request.parameters),
        'source_snapshot_digest':artifact['source_snapshot_digest'],
        'result_artifact_digest':artifact['artifact_digest'], 'result_digest':artifact['result_digest']}
    if (receipt != execution.exploration_receipt
        or receipt.receipt_digest != semantic_digest(receipt.model_dump(mode='json',exclude={'receipt_digest'}))
        or any(getattr(receipt,k) != v for k,v in expected.items())
        or not (execution.execution_id == receipt.run_id == execution.result.run_id == artifact['run_id'])):
        raise ValueError('NATIVE_ANSWER_RECEIPT_MISMATCH')
    saved = {r['result_set_id']:r for r in artifact['result_sets']}
    planned = {r.result_set_id:r for r in plan.result_sets}
    results = execution.result.result_sets
    if (len(results) != len(saved) or {r.result_set_id for r in results} != set(saved)
        or set(saved) != set(planned)
        or execution.result.result_digest != artifact['result_digest']
        or execution.result.quality_sidecars != request.quality_receipts):
        raise ValueError('NATIVE_ANSWER_RESULT_MISMATCH')
    for result in results:
        row = result.model_dump(mode='json'); original = saved[result.result_set_id]; spec = planned[result.result_set_id]
        if (result.run_id != execution.execution_id or result.role != spec.role or result.object_ref != spec.object_ref
            or result.completeness_policy != spec.completeness_policy
            or result.parent_link != spec.parent_link
            or result.returned_row_count != len(result.rows)
            or result.truncated != (result.returned_row_count < result.row_count)
            or result.returned_row_count > len(original['rows'])
            or row['rows'] != original['rows'][:result.returned_row_count]
            or any(row.get(k) != original.get(k) for k in (
                'exact_grain','coverage_semantics','coverage_missing_parent_count','coverage_zero_filled_count',
                'row_count','result_digest','result_schema','result_schema_digest','paging','latest_quality',
                'latest_policy','temporal_predicate_quality'))):
            raise ValueError('NATIVE_ANSWER_RESULT_MISMATCH')
    return execution


def build_native_query_answer(*, gateway, outcome, request, execution):
    """Assemble shared fields/meaning/evidence after current protected result read.

    This does not generate prose or certify answer sufficiency. Native semantic
    review remains pending and must be reported separately from execution.
    """
    from .profile_driven_query_runtime import ReviewedSemanticPlanOutcome
    outcome = ReviewedSemanticPlanOutcome.model_validate(outcome)
    request = MultiResultExploratoryExecutionRequest.model_validate(request)
    authority = request.logical_plan.candidate_authority
    if not isinstance(authority, NativeQueryAuthority):
        raise ValueError('NATIVE_RESULT_AUTHORITY_REQUIRED')
    expected = prepare_native_query_request(outcome, profile_revision=authority.profile_revision,
        source_snapshot_digest=authority.source_snapshot_digest,
        request_authorization_digest=authority.request_authorization_digest,idempotency_key=request.idempotency_key)
    if expected != request:
        raise ValueError('NATIVE_ANSWER_PLANNING_REQUEST_MISMATCH')
    execution = validate_native_answer_execution(gateway,request=request,execution=execution)
    receipt = execution.receipt
    results = {r.result_set_id:r for r in execution.result.result_sets}
    result_sets = tuple(GovernedAnswerArtifactBuilder._multi_result_set(context=outcome.planning_context,
        plan=p,result=results[p.result_set_id],protected_artifact_ref=receipt.result_artifact_ref)
        for p in request.logical_plan.result_sets)
    evidence = ArtifactExecutionEvidence(execution_id=execution.execution_id,lane='exploratory',classification='PROVISIONAL',
        execution_receipt_ref='multi-result-execution-receipt:'+execution.execution_id,
        execution_receipt_digest=receipt.receipt_digest,logical_plan_digest=receipt.logical_plan_digest,
        source_snapshot_digest=receipt.source_snapshot_digest,result_digest=receipt.result_digest,
        attestation_state='ABSENT',attestation_ref=None,attestation_digest=None)
    shape = outcome.shape_selection.solver_outcome.selected_shape
    values = GovernedAnswerArtifactBuilder._build_values(context=outcome.planning_context,
        answerability_state='native_review_pending',answerability_receipt_digest=None,
        shape=shape.shape,shape_contract=shape,result_sets=result_sets,quality_receipts=request.quality_receipts,
        execution=evidence,resource_access_receipt_digest=None,resource_freeze_receipt_digest=None)
    values.update(schema_name='boi-governed-answer-artifact/v6',candidate_authority=authority.model_dump(mode='json'),
        planning_outcome_digest=outcome.outcome_digest,protected_artifact_ref=receipt.result_artifact_ref,
        protected_artifact_digest=receipt.result_artifact_digest)
    return NativeGovernedAnswerArtifact.model_validate({**values,
        'artifact_semantic_digest':semantic_digest(_semantic_projection(values))})
