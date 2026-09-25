"""Reviewed question adapter to the shared durable frozen-inference store."""
import json
import re
import unicodedata

from .semantic_binding_contract import semantic_digest
from .semantic_inference_cache import (
    FrozenSemanticInferenceCache, QueryIntentInferenceRequest, InferenceAttemptContext, canonical,
)
from .semantic_intent import (
    IntentCandidate,
    IntentInferenceBlocked,
    REVIEWED_FILTER_OWNERSHIP,
)
from .semantic_qualifier import SemanticQualifier


def _operator(value):
    return {'ne': 'neq', 'is_not_null': 'not_null'}.get(value, value)


def _values(value):
    return tuple(value) if isinstance(value, tuple) else (value,)


def _predicate_signature(*, property_ref, operator, value, unit_ref):
    return semantic_digest({
        'property_ref': property_ref,
        'operator': _operator(operator),
        'values': _values(value),
        'unit_ref': unit_ref,
    })


def _question_contains_literal(question, value):
    text = unicodedata.normalize('NFKC', question).casefold()
    if isinstance(value, str):
        literal = unicodedata.normalize('NFKC', value).casefold().strip()
        if not literal:
            return False
        if re.fullmatch(r'[a-z0-9_]+', literal):
            return re.search(
                r'(?<![a-z0-9_])' + re.escape(literal) + r'(?![a-z0-9_])',
                text,
            ) is not None
        return literal in text
    if isinstance(value, bool):
        return json.dumps(value) in text
    if isinstance(value, (int, float)):
        literal = re.escape(str(value))
        return re.search(r'(?<![\d.])' + literal + r'(?![\d.])', text) is not None
    return False


def _filter_contains_value(item, value):
    return item.property_id and any(
        type(candidate_value) is type(value) and candidate_value == value
        for candidate_value in _values(item.value)
    )


def require_question_owned_filters(model_input, candidate):
    """Reject a source predicate copied into intent without its literal in the question.

    This proves only one narrow negative: a value-bearing reviewed source filter
    cannot masquerade as a user filter when none of its exact values occur in the
    question. Source applicability remains available to the later deterministic
    qualifier compiler.
    """
    if getattr(model_input, 'filter_ownership', None) != REVIEWED_FILTER_OWNERSHIP:
        raise IntentInferenceBlocked('REVIEWED_QUESTION_FILTER_OWNERSHIP_REQUIRED')
    source = set()
    source_predicates = []
    for entry in model_input.logical_context:
        raw = (entry.logical_payload.get('applicability') or {}).get('conditions') or ()
        for value in raw:
            try:
                qualifier = SemanticQualifier.model_validate(value)
            except ValueError:
                continue
            if qualifier.disposition != 'row_condition':
                continue
            for predicate in qualifier.predicates:
                if not predicate.values:
                    continue
                source.add(_predicate_signature(
                    property_ref=predicate.property_ref,
                    operator=predicate.operator,
                    value=predicate.values,
                    unit_ref=predicate.unit_ref,
                ))
                source_predicates.append(predicate)
    for item in candidate.filters:
        values = _values(item.value)
        signature = _predicate_signature(
            property_ref=item.property_id,
            operator=item.operator,
            value=values,
            unit_ref=item.unit_ref,
        )
        if signature in source and not all(
            _question_contains_literal(model_input.question, value)
            for value in values
        ):
            raise IntentInferenceBlocked(
                'REVIEWED_QUESTION_SOURCE_FILTER_OWNERSHIP_CONFLICT',
                candidate=candidate,
            )
    for predicate in source_predicates:
        for value in predicate.values:
            if (_question_contains_literal(model_input.question, value)
                    and not any(item.property_id == predicate.property_ref
                        and _filter_contains_value(item, value)
                        for item in candidate.filters)):
                raise IntentInferenceBlocked(
                    'REVIEWED_QUESTION_SOURCE_LITERAL_FILTER_UNBOUND',
                    candidate=candidate,
                )
    return candidate


class ReviewedQuestionInference:
    def __init__(self, *, store, scope, model, identity, policy, channel):
        self.cache=FrozenSemanticInferenceCache(store)
        self.scope=scope
        self.model=model
        self.identity=identity
        self.policy=policy
        self.channel=channel
        self.results=[]

    def __call__(self, model_input):
        scope=self.scope
        value=model_input.model_dump(mode='json')
        if len(canonical(value))>11264 or len(model_input.logical_context)>64:
            raise IntentInferenceBlocked('REVIEWED_QUESTION_INPUT_SCOPE_BUDGET_EXCEEDED')
        evidence=tuple(sorted({span['span_ref'] for c in scope.domain for span in c['field_evidence']}))
        closure=semantic_digest([entry.model_dump(mode='json') for entry in model_input.logical_context])
        request=QueryIntentInferenceRequest(principal_id=scope.run.principal,
            acl_policy_digest=scope.manifest['acl_policy_digest'],
            namespace=semantic_digest(sorted({c['source_record']['namespace'] for c in scope.domain})),
            source_profile_digest=scope.manifest['metadata_execution']['source_profile_digest'],
            semantic_input_digest=semantic_digest(value),definition_closure_digest=closure,
            output_contract_digest=semantic_digest(IntentCandidate.model_json_schema()),
            model_id=self.identity.model_id,model_digest=self.identity.model_digest,
            role_digest=self.identity.role_digest,prompt_digest=self.identity.prompt_digest,
            input_digest=semantic_digest(value),input_bytes=len(canonical(value)),
            atomic_unit_count=len(model_input.logical_context))
        attempt=InferenceAttemptContext(run_ref=scope.run.run_id,shard_ref=scope.shard.shard_id,
            unresolved_reason='REVIEWED_QUESTION_INTENT_REQUIRED',evidence_span_refs=evidence,
            evidence_closure_digest=semantic_digest([c['field_evidence'] for c in scope.domain]),channel=self.channel)
        frozen=self.cache.run_frozen(request=request,attempt=attempt,payload=value,identity=self.identity,
            policy=self.policy,invoke=lambda _:self.model(model_input),output_model=IntentCandidate)
        self.results.append(frozen)
        if frozen.output is None:
            raise IntentInferenceBlocked(frozen.reason_code or 'REVIEWED_QUESTION_INFERENCE_UNAVAILABLE')
        candidate = IntentCandidate.model_validate(frozen.output)
        require_question_owned_filters(model_input, candidate)
        return frozen.output
