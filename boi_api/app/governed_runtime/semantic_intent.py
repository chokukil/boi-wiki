"""Closed-schema Pi intent synthesis and deterministic logical resolution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_serializer, model_validator, Field

from .filter_expression import FilterExpression,validate_filter_expression
from .cardinality_query_shape import ResultShapeContract
from .local_model_routing import (
    LocalModelPolicy,
    LocalModelRunIdentity,
    decide_pi_execution,
)
from .semantic_profile_loader import LoadedProfileEntry, SemanticContextBundle
from .semantic_profile_retrieval import RetrievalReceipt
from .token_routing_metrics import TokenRoutingMetrics
from .semantic_authority import SemanticAuthorityFields, semantic_authority_values, require_same_semantic_authority


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


ScalarValue = str | int | float | bool | None
FilterValue = ScalarValue | tuple[ScalarValue, ...]


class IntentFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_id: str
    operator: Literal[
        "eq", "neq", "ne", "gt", "gte", "lt", "lte", "in",
        "is_null", "not_null", "is_not_null",
        "=", "!=", "<>", ">", ">=", "<", "<=",
    ]
    value: FilterValue
    unit_ref: str | None = None
    scope: Literal[
        "COLLECTION_CONTENT",
        "COLLECTION",
        "ROOT_EXISTENCE",
        "ROOT_AND_COLLECTION",
        "ROOT_ABSENCE",
    ] | None = None


class IntentAggregation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: str
    target_id: str
    distinct: bool
    scope_object_id: str | None = None
    partition_by: tuple[str, ...] = ()
    group_by: tuple[str, ...] = ()

    @model_serializer(mode='wrap')
    def preserve_old_aggregation(self, handler):
        value=handler(self)
        if not self.group_by: value.pop('group_by',None)
        return value


class IntentOrdering(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_id: str
    direction: Literal["ASC", "DESC"]


class IntentTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    property_id: str
    start: str
    end: str
    timezone: str | None = None
    start_inclusive: bool | None = None
    end_inclusive: bool | None = None


class AmbiguityAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    logical_ids: tuple[str, ...]


class QualityDisclosureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_object_id: str = Field(min_length=1)
    relationship_id: str | None
    detail: Literal["SUMMARY", "ROWS"]
    measures: tuple[Literal["matched", "unmatched", "null_fk", "orphan", "duplicate_key", "excluded", "coverage"], ...] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def unique_measures(self):
        if len(set(self.measures)) != len(self.measures):
            raise ValueError("QUALITY_MEASURE_DUPLICATE")
        return self


class IntentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_ids: tuple[str, ...]
    property_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[IntentFilter, ...]
    filter_expression: FilterExpression | None = Field(default=None,exclude_if=lambda v:v is None,
        description='Boolean composition over zero-based entries in filters. Preserve the user condition grouping; absent means conjunction of all filters. Every filter must be referenced.')
    aggregations: tuple[IntentAggregation, ...]
    grain: tuple[str, ...]
    time_range: IntentTimeRange | None
    ordering: tuple[IntentOrdering, ...]
    limit: int
    unresolved_terms: tuple[str, ...]
    ambiguity_alternatives: tuple[AmbiguityAlternative, ...]
    intent_contract_version: Literal["typed-intent-v1", "quality-intent-v2", "scoped-aggregate-v3", "scoped-result-intent-v4"] = "typed-intent-v1"
    quality_requests: tuple[QualityDisclosureRequest, ...] = Field(default=(), max_length=4)
    rowset_object_ids: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def quality_revision_required(self):
        if self.filter_expression is not None:
            validate_filter_expression(self.filter_expression,len(self.filters))
        if self.intent_contract_version == 'scoped-result-intent-v4':
            if not self.rowset_object_ids:
                raise ValueError('ROWSET_MEMBERSHIP_REQUIRED')
            if (len(set(self.rowset_object_ids)) != len(self.rowset_object_ids)
                or not set(self.rowset_object_ids) <= set(self.entity_ids)):
                raise ValueError('ROWSET_MEMBERSHIP_INVALID')
        elif 'rowset_object_ids' in self.model_fields_set:
            raise ValueError('ROWSET_REVISION_REQUIRED')
        if self.quality_requests and self.intent_contract_version not in {"quality-intent-v2", "scoped-aggregate-v3", "scoped-result-intent-v4"}:
            raise ValueError("QUALITY_INTENT_REVISION_REQUIRED")
        if any(a.group_by for a in self.aggregations) and self.intent_contract_version not in {'scoped-aggregate-v3', 'scoped-result-intent-v4'}:
            raise ValueError('AGGREGATE_SCOPE_REVISION_REQUIRED')
        if (any(f.scope == 'ROOT_ABSENCE' for f in self.filters)
                and self.intent_contract_version != 'scoped-result-intent-v4'):
            raise ValueError('ROOT_ABSENCE_REVISION_REQUIRED')
        if any(a.group_by for a in self.aggregations if a.operator=='latest'):
            raise ValueError('LATEST_GROUP_BY_FORBIDDEN')
        if (self.intent_contract_version in {'scoped-aggregate-v3', 'scoped-result-intent-v4'}
            and any(a.operator=='latest' for a in self.aggregations)
            and any(a.operator!='latest' for a in self.aggregations)):
            raise ValueError('MIXED_LATEST_REDUCER_CONTRACT_REQUIRED')
        return self

    @model_serializer(mode="wrap")
    def preserve_v1_payload(self, handler):
        value = handler(self)
        if self.intent_contract_version != 'scoped-result-intent-v4':
            value.pop('rowset_object_ids', None)
        if self.intent_contract_version == "typed-intent-v1":
            value.pop("intent_contract_version", None)
            value.pop("quality_requests", None)
        return value


class IntentModelContextEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str
    kind: str
    revision_digest: str
    logical_payload: dict[str, Any]
    evidence_resources: tuple[str, ...]


class IntentModelInput(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    question_digest: str
    active_release_digest: str | None
    retrieval_receipt_digest: str
    logical_context: tuple[IntentModelContextEntry, ...]


class ReviewedFilterOwnership(BaseModel):
    """Versioned ownership boundary between question intent and source policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal['boi/reviewed-filter-ownership@1'] = (
        'boi/reviewed-filter-ownership@1'
    )
    intent_filter_source: Literal['explicit_question_only'] = 'explicit_question_only'
    explicit_question_filter_handling: Literal[
        'preserve_verbatim_even_if_source_qualifier_conflicts'
    ] = 'preserve_verbatim_even_if_source_qualifier_conflicts'
    source_qualifier_handling: Literal[
        'do_not_copy_into_intent;boi_applies_after_intent'
    ] = 'do_not_copy_into_intent;boi_applies_after_intent'


REVIEWED_FILTER_OWNERSHIP = ReviewedFilterOwnership()


class ReviewedIntentModelInput(IntentModelInput):
    """Tell Pi which contract owns source applicability in reviewed queries."""

    definition_projection_version: Literal[
        'boi/reviewed-definition-model-projection@1'
    ] = 'boi/reviewed-definition-model-projection@1'
    filter_ownership: ReviewedFilterOwnership = REVIEWED_FILTER_OWNERSHIP


class IntentContinuationModelInput(IntentModelInput):
    """Additive input revision; historical first-turn bytes stay unchanged."""
    clarification_context: dict[str, Any]


class ReviewedIntentContinuationModelInput(ReviewedIntentModelInput):
    clarification_context: dict[str, Any]


class NativeIntentSubmission(BaseModel):
    """A directly authored candidate bound to the exact presented input.

    This is submission evidence, never an inference execution or access grant.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal['boi/native-intent-submission@1'] = 'boi/native-intent-submission@1'
    input_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    candidate: IntentCandidate
    session_ref: str = Field(min_length=1)


class NativeIntentProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal['boi/native-intent-provenance@1'] = 'boi/native-intent-provenance@1'
    submission_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    submitted_principal: str = Field(min_length=1)
    session_ref: str = Field(min_length=1)
    execution_attested: Literal[False] = False
    session_identity_verified: Literal[False] = False
    semantic_truth_proven: Literal[False] = False


class IntentSynthesisReceipt(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "REJECTED"]
    reason_codes: tuple[str, ...]
    candidate: IntentCandidate | None
    question_digest: str
    retrieval_receipt_digest: str
    active_release_digest: str | None
    model_id: str
    model_digest: str
    role_digest: str
    prompt_digest: str
    input_digest: str
    output_digest: str
    codex_fallback_allowed: Literal[False] = False
    native_provenance: NativeIntentProvenance | None = Field(
        default=None, exclude_if=lambda value: value is None)
    receipt_digest: str

    @model_validator(mode='after')
    def native_origin_is_explicit(self):
        native = self.native_provenance is not None
        markers = (self.model_id == 'external-native',
                   self.model_digest == 'unavailable:external-native')
        if native != all(markers) or (not native and any(markers)):
            raise ValueError('NATIVE_INTENT_PROVENANCE_MISMATCH')
        if native:
            authority = self.reviewed_definition_authority
            if (authority is None or self.active_release_digest is not None
                    or authority.principal != self.native_provenance.submitted_principal):
                raise ValueError('NATIVE_INTENT_PROVENANCE_MISMATCH')
        return self


IntentModel = Callable[[IntentModelInput], dict[str, Any]]


class IntentModelOutputError(ValueError):
    """The local worker responded, but its closed-schema output was invalid."""


class IntentInferenceBlocked(ValueError):
    """A trusted controller withheld acceptance of an inference outcome.

    A schema-valid frozen candidate may remain attached for audit and response
    explanation.  The blocked synthesis status still prevents resolution,
    planning, and execution.
    """
    def __init__(self, reason_code, *, candidate: IntentCandidate | None = None):
        import re
        if not re.fullmatch(r'[A-Z][A-Z0-9_]+',reason_code):
            raise ValueError('INTENT_INFERENCE_REASON_INVALID')
        self.reason_code=reason_code
        self.candidate=candidate
        super().__init__(reason_code)


class PiIntentSynthesizer:
    _LOGICAL_KEYS = frozenset(
        {
            "id",
            "kind",
            "name",
            "aliases",
            "description",
            "term",
            "definition",
            "applicability",
            "exceptions",
            "quantity_kind",
            "authority_basis",
            "semantic_contract",
            "value_type",
            "value_type_ref",
            "unit",
            "unit_ref",
            "unit_semantics",
            "unit_conversions",
            "aggregation",
            "grain",
            "time_semantics",
            "inclusion",
            "exclusion",
            "depends_on",
            "identity_property_ref",
            "logical_grain",
            "versioning",
            "primitive_type",
            "logical_role",
            "owner_ref",
            "properties",
            "property_refs",
            "semantic_name",
            "left_optional",
            "right_optional",
            "relationship_identity_ref",
            "temporal_semantics",
            "priority",
            "conflict_policy",
            "effective_window",
            "expression",
            "left_endpoint_ref",
            "right_endpoint_ref",
            "left_property_ref",
            "right_property_ref",
            "left_property_refs",
            "right_property_refs",
            "cardinality",
            "optionality",
            "validity_window",
        }
    )

    def __init__(
        self,
        *,
        model: IntentModel,
        policy: LocalModelPolicy,
        metrics: TokenRoutingMetrics | None = None,
    ):
        self.model = model
        self.policy = policy
        self.metrics = metrics

    @staticmethod
    def _reviewed_definition_payload(entry: LoadedProfileEntry) -> dict[str, Any]:
        """Project one full reviewed definition without repeating equal facts.

        The reviewed bundle and its authority digest retain the original payload.
        Pi still receives every value, plus the exact definition revision and
        evidence resources.  Only identity already carried by the outer context
        entry and exactly equal facts represented elsewhere in the same payload
        are removed.  Empty conditions, exceptions, scope and null declarations
        stay explicit because absence would carry a different meaning.
        """
        payload = deepcopy(entry.payload)
        if payload.get('id') == entry.entry_id:
            payload.pop('id')
        if payload.get('kind') == str(entry.payload.get('kind') or entry.category):
            payload.pop('kind')
        semantic = payload.get('semantic_contract')
        if not isinstance(semantic, dict):
            return payload

        if ('definition' in payload and 'definition' in semantic
                and payload['definition'] == semantic['definition']):
            semantic.pop('definition', None)
        elif ('description' in payload and 'definition' in semantic
                and payload['description'] == semantic['definition']):
            payload.pop('description')
        if ('description' in payload and 'definition' in payload
                and payload['description'] == payload['definition']):
            payload.pop('description')
        for key in ('aliases', 'authority_basis', 'unit_ref', 'unit_semantics'):
            if key in payload and payload[key] == semantic.get(key):
                semantic.pop(key, None)
        outer_kind = str(entry.payload.get('kind') or entry.category)
        if semantic.get('kind') == outer_kind:
            semantic.pop('kind')
        return payload

    @classmethod
    def _context_entry(cls, entry: LoadedProfileEntry, *, evidence_complete: bool = False) -> IntentModelContextEntry:
        logical_payload = (
            cls._reviewed_definition_payload(entry)
            if evidence_complete
            else deepcopy({
                key: value
                for key, value in entry.payload.items()
                if key in cls._LOGICAL_KEYS
            })
        )
        return IntentModelContextEntry(
            entry_id=entry.entry_id,
            kind=str(entry.payload.get("kind") or entry.category),
            # Revision and evidence digests remain bound by the retrieval receipt,
            # semantic bundle, and active Release.  They are not query meaning and
            # needlessly consume the bounded untrusted-model context.
            revision_digest=entry.revision_digest if evidence_complete else "",
            logical_payload=logical_payload,
            # Retrieval and the final receipt retain evidence bindings.  The
            # untrusted intent model only needs logical meaning and identifiers.
            evidence_resources=entry.evidence_resources if evidence_complete else (),
        )

    @staticmethod
    def _receipt(
        *,
        status: str,
        reasons: tuple[str, ...],
        candidate: IntentCandidate | None,
        model_input: IntentModelInput,
        identity: LocalModelRunIdentity,
        output_digest: str,
    ) -> IntentSynthesisReceipt:
        values = {
            "status": status,
            "reason_codes": reasons,
            "candidate": candidate,
            "question_digest": model_input.question_digest,
            "retrieval_receipt_digest": model_input.retrieval_receipt_digest,
            **semantic_authority_values(model_input),
            "model_id": identity.model_id,
            "model_digest": identity.model_digest,
            "role_digest": identity.role_digest,
            "prompt_digest": identity.prompt_digest,
            "input_digest": _digest(model_input),
            "output_digest": output_digest,
            "codex_fallback_allowed": False,
        }
        digest_values = {
            **values,
            **({'reviewed_definition_authority':model_input.reviewed_definition_authority.model_dump(mode='json')}
                if model_input.reviewed_definition_authority is not None else {}),
            "candidate": candidate.model_dump(mode="json") if candidate else None,
        }
        return IntentSynthesisReceipt(**values, receipt_digest=_digest(digest_values))

    def synthesize(
        self,
        *,
        question: str,
        retrieval: RetrievalReceipt,
        bundle: SemanticContextBundle,
        identity: LocalModelRunIdentity,
        clarification_context: dict[str, Any] | None = None,
    ) -> IntentSynthesisReceipt:
        if retrieval.active_release_digest != bundle.active_release_digest:
            raise ValueError("RETRIEVAL_RELEASE_MISMATCH")
        require_same_semantic_authority(retrieval, bundle)
        if retrieval.semantic_bundle_digest != bundle.bundle_digest:
            raise ValueError("RETRIEVAL_BUNDLE_MISMATCH")
        entries = {entry.entry_id: entry for entry in bundle.domain_entries}
        reviewed = bundle.reviewed_definition_authority is not None
        model_type = (
            ReviewedIntentContinuationModelInput
            if reviewed and clarification_context is not None
            else ReviewedIntentModelInput
            if reviewed
            else IntentContinuationModelInput
            if clarification_context is not None
            else IntentModelInput
        )
        model_input = model_type(
            question=question,
            question_digest=_digest(question),
            **semantic_authority_values(bundle),
            retrieval_receipt_digest=retrieval.receipt_digest,
            logical_context=tuple(
                self._context_entry(entries[candidate.entry_id],
                    evidence_complete=bundle.reviewed_definition_authority is not None)
                for candidate in retrieval.candidates
                if candidate.entry_id in entries
            ),
            **({'clarification_context': clarification_context} if clarification_context is not None else {}),
        )
        input_bytes = len(model_input.model_dump_json().encode("utf-8"))
        decision = decide_pi_execution(identity, self.policy)
        if decision.status != "READY":
            if self.metrics is not None:
                self.metrics.record_withheld()
            return self._receipt(
                status="BLOCKED",
                reasons=decision.reason_codes,
                candidate=None,
                model_input=model_input,
                identity=identity,
                output_digest="",
            )
        try:
            raw_output = self.model(model_input)
        except IntentInferenceBlocked as error:
            if self.metrics is not None:
                self.metrics.record_withheld()
            return self._receipt(status='BLOCKED',reasons=(error.reason_code,),
                candidate=error.candidate, model_input=model_input,identity=identity,
                output_digest=_digest(error.candidate) if error.candidate is not None else '')
        except IntentModelOutputError:
            if self.metrics is not None:
                self.metrics.record_pi(input_bytes=input_bytes, status="REJECTED")
            return self._receipt(
                status="REJECTED",
                reasons=("INTENT_OUTPUT_SCHEMA_INVALID",),
                candidate=None,
                model_input=model_input,
                identity=identity,
                output_digest="",
            )
        except Exception:
            if self.metrics is not None:
                self.metrics.record_pi(input_bytes=input_bytes, status="BLOCKED")
            return self._receipt(
                status="BLOCKED",
                reasons=("LOCAL_MODEL_EXECUTION_FAILED",),
                candidate=None,
                model_input=model_input,
                identity=identity,
                output_digest="",
            )
        output_digest = _digest(raw_output)
        try:
            candidate = IntentCandidate.model_validate(raw_output)
        except ValidationError:
            if self.metrics is not None:
                self.metrics.record_pi(input_bytes=input_bytes, status="REJECTED")
            return self._receipt(
                status="REJECTED",
                reasons=("INTENT_OUTPUT_SCHEMA_INVALID",),
                candidate=None,
                model_input=model_input,
                identity=identity,
                output_digest=output_digest,
            )
        if self.metrics is not None:
            self.metrics.record_pi(input_bytes=input_bytes, status="READY")
        return self._receipt(
            status="READY",
            reasons=(),
            candidate=candidate,
            model_input=model_input,
            identity=identity,
            output_digest=output_digest,
        )


def prepare_intent_input(*, question, retrieval, bundle, clarification_context=None):
    """Read-only projection using the same definition projection as Pi.

    Callers must obtain the bundle/retrieval from the authorized existing reader.
    This helper grants no authorization and runs no model.
    """
    require_same_semantic_authority(retrieval, bundle)
    if retrieval.semantic_bundle_digest != bundle.bundle_digest:
        raise ValueError('RETRIEVAL_BUNDLE_MISMATCH')
    if retrieval.question_digest != _digest(question):
        raise ValueError('INTENT_QUESTION_RETRIEVAL_MISMATCH')
    entries = {entry.entry_id: entry for entry in bundle.domain_entries}
    reviewed = bundle.reviewed_definition_authority is not None
    model_type = (ReviewedIntentContinuationModelInput if reviewed and clarification_context is not None
        else ReviewedIntentModelInput if reviewed
        else IntentContinuationModelInput if clarification_context is not None else IntentModelInput)
    return model_type(question=question, question_digest=_digest(question),
        **semantic_authority_values(bundle), retrieval_receipt_digest=retrieval.receipt_digest,
        logical_context=tuple(PiIntentSynthesizer._context_entry(entries[c.entry_id],
            evidence_complete=reviewed) for c in retrieval.candidates if c.entry_id in entries),
        **({'clarification_context': clarification_context} if clarification_context is not None else {}))


def accept_native_intent(model_input, submission, *, principal):
    """Bind a native candidate; do not call a model or certify semantic correctness.

    The enclosing authorized service must supply principal and current input.
    The caller-supplied session label is deliberately not authenticated here.
    """
    submission = NativeIntentSubmission.model_validate(submission)
    if submission.input_digest != _digest(model_input):
        raise ValueError('NATIVE_INTENT_INPUT_MISMATCH')
    authority = model_input.reviewed_definition_authority
    if authority is None or model_input.active_release_digest is not None:
        raise ValueError('NATIVE_INTENT_REVIEWED_SCOPE_REQUIRED')
    if principal != authority.principal:
        raise ValueError('NATIVE_INTENT_PRINCIPAL_MISMATCH')
    provenance = NativeIntentProvenance(submission_digest=_digest(submission),
        submitted_principal=principal, session_ref=submission.session_ref)
    values = dict(status='READY', reason_codes=(), candidate=submission.candidate.model_dump(mode='json'),
        question_digest=model_input.question_digest,
        retrieval_receipt_digest=model_input.retrieval_receipt_digest,
        **semantic_authority_values(model_input), model_id='external-native',
        model_digest='unavailable:external-native',
        role_digest=_digest('boi/native-intent-submission@1'),
        prompt_digest=_digest(model_input), input_digest=_digest(model_input),
        output_digest=_digest(submission.candidate), codex_fallback_allowed=False,
        native_provenance=provenance.model_dump(mode='json'))
    return IntentSynthesisReceipt(**values, receipt_digest=_digest(values))


class ResolvedIntent(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: IntentCandidate
    intent_digest: str
    active_release_digest: str | None
    domain_profile_digest: str
    query_profile_digest: str


class SemanticResolutionReceipt(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["RESOLVED", "CLARIFICATION_REQUIRED", "BLOCKED"]
    reason_codes: tuple[str, ...]
    clarification_count: int
    resolved_intent: ResolvedIntent | None
    candidate_digest: str
    retrieval_receipt_digest: str
    active_release_digest: str | None
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    schema_digest: str
    capability_digest: str
    intent_synthesis_receipt_digest: str = ""
    intent_model_id: str = ""
    intent_model_digest: str = ""
    intent_role_digest: str = ""
    intent_prompt_digest: str = ""
    resolver_digest: str
    receipt_digest: str
    semantic_transformations: tuple[dict[str, Any], ...] = ()

    @model_serializer(mode='wrap')
    def preserve_historical_bytes(self, handler):
        value = handler(self)
        if not self.semantic_transformations:
            value.pop('semantic_transformations', None)
        return value


class SemanticQuestionInterpretation(SemanticAuthorityFields):
    """Receipt for question interpretation; never a query execution decision."""
    contract_version: Literal['boi/semantic-question-interpretation@1'] = 'boi/semantic-question-interpretation@1'
    active_release_digest: str | None
    status: Literal['RESOLVED','CLARIFICATION_REQUIRED','BLOCKED']
    reason_codes: tuple[str, ...]
    semantic_bundle_digest: str
    retrieval: RetrievalReceipt
    synthesis: IntentSynthesisReceipt | None
    resolution: SemanticResolutionReceipt | None
    execution_status: Literal['not_run'] = 'not_run'
    semantic_equivalence_decided: Literal[False] = False
    receipt_digest: str

    @model_validator(mode='after')
    def interpretation_chain(self):
        for receipt in (self.retrieval,self.synthesis,self.resolution):
            if receipt is not None:
                require_same_semantic_authority(self,receipt)
                if receipt.receipt_digest != _digest(receipt.model_dump(mode='json',exclude={'receipt_digest'})):
                    raise ValueError('QUESTION_INTERPRETATION_RECEIPT_INVALID')
        if self.retrieval.semantic_bundle_digest != self.semantic_bundle_digest:
            raise ValueError('QUESTION_INTERPRETATION_BUNDLE_MISMATCH')
        if self.synthesis is not None and self.synthesis.retrieval_receipt_digest != self.retrieval.receipt_digest:
            raise ValueError('QUESTION_INTERPRETATION_SYNTHESIS_MISMATCH')
        if self.resolution is not None:
            if (self.synthesis is None or self.resolution.intent_synthesis_receipt_digest != self.synthesis.receipt_digest
                    or self.resolution.status != self.status or self.resolution.reason_codes != self.reason_codes):
                raise ValueError('QUESTION_INTERPRETATION_RESOLUTION_MISMATCH')
        elif self.status != 'BLOCKED':
            raise ValueError('QUESTION_INTERPRETATION_RESOLUTION_REQUIRED')
        if self.receipt_digest != _digest(self.model_dump(mode='json',exclude={'receipt_digest'})):
            raise ValueError('QUESTION_INTERPRETATION_DIGEST_MISMATCH')
        return self


class SemanticIntentResolver:
    RESOLVER_ID = "boi.semantic-intent-resolver@0.5.0"

    @staticmethod
    def matching_result_shapes(
        bundle: SemanticContextBundle, entity_ids: tuple[str, ...] | list[str],
    ) -> tuple[ResultShapeContract, ...]:
        """Match only the exact active semantic endpoint closure, not a name."""
        domains = {entry.entry_id: entry for entry in bundle.domain_entries}
        requested = set(entity_ids)
        matching = []
        for entry in bundle.query_entries:
            raw = entry.payload.get("result_shape_contract")
            if raw is None:
                continue
            shape = ResultShapeContract.model_validate(raw)
            if not shape.relationship_refs or shape.root_object_ref not in requested:
                continue
            endpoints = {shape.root_object_ref}
            for ref in shape.relationship_refs:
                relation = domains.get(ref)
                if relation is None or relation.payload.get("kind") != "RelationType":
                    endpoints = set()
                    break
                endpoints.update((relation.payload.get("left_endpoint_ref"),
                                  relation.payload.get("right_endpoint_ref")))
            if endpoints == requested:
                matching.append(shape)
        return tuple(matching)

    @staticmethod
    def _independent_collection_grain(
        candidate: IntentCandidate, bundle: SemanticContextBundle,
        entity_ids: list[str],
    ) -> tuple[str, ...] | None:
        """Separate collection identities only under one exact approved shape.

        An identity list across independently returned ObjectSets is not a flat
        cross-product grain. Preserve every projected child/relationship identity;
        only the root grain is canonicalized. A competing flat shape, another root,
        an aggregate or a non-identity grain must never be silently rewritten.
        """
        if (len(entity_ids) < 2 or candidate.aggregations or candidate.metric_ids
                or candidate.unresolved_terms or candidate.ambiguity_alternatives
                or candidate.dimensions != candidate.grain):
            return None
        domains = {entry.entry_id: entry for entry in bundle.domain_entries}
        identities = {}
        for ref in entity_ids:
            entity = domains.get(ref)
            identity = entity.payload.get("identity_property_ref") if entity else None
            if not identity or entity.payload.get("kind") != "ObjectType":
                return None
            identities[ref] = identity
        if set(candidate.grain) != set(identities.values()):
            return None
        matching = SemanticIntentResolver.matching_result_shapes(bundle, entity_ids)
        if len(matching) != 1:
            return None
        shape = matching[0]
        if (shape.shape not in {"LinkedObjectSet", "NestedCollection"}
                or not shape.collection_semantics
                or shape.exact_grain != (identities[shape.root_object_ref],)):
            return None
        return shape.exact_grain

    @staticmethod
    def normalize_candidate(
        candidate: IntentCandidate,
        bundle: SemanticContextBundle,
    ) -> IntentCandidate:
        """Canonicalize representation-only redundancy from model output."""

        by_id = {entry.entry_id: entry for entry in bundle.domain_entries}
        if candidate.intent_contract_version == 'scoped-result-intent-v4':
            # v4 makes display membership explicit. Transport identity is added
            # by the planner; it is not a user-requested display field. Never
            # apply legacy grain/projection/reducer inference to this revision.
            return candidate
        property_refs = [
            *candidate.property_ids,
            *candidate.dimensions,
            *candidate.grain,
            *(item.property_id for item in candidate.filters),
            *(item.property_id for item in candidate.ordering),
        ]
        if candidate.time_range:
            property_refs.append(candidate.time_range.property_id)
        property_refs.extend(
            item.target_id
            for item in candidate.aggregations
            if (
                item.target_id in by_id
                and by_id[item.target_id].payload.get("kind") == "PropertyDefinition"
            )
        )
        for aggregation in candidate.aggregations:
            property_refs.extend(aggregation.partition_by)
            property_refs.extend(aggregation.group_by)
        entity_ids = list(dict.fromkeys(candidate.entity_ids))
        for property_id in property_refs:
            entry = by_id.get(property_id)
            owner_ref = entry.payload.get("owner_ref") if entry else None
            if isinstance(owner_ref, str) and owner_ref and owner_ref not in entity_ids:
                entity_ids.append(owner_ref)
        projection_like = not candidate.aggregations or all(
            item.operator == "latest" for item in candidate.aggregations
        )
        property_ids = list(dict.fromkeys(candidate.property_ids))
        if projection_like:
            # Object-backed projections always carry object identity even when the
            # model expresses it only by naming the ObjectType.  This is required
            # for exact collection identity and is derived solely from the active
            # Domain profile, not from a query oracle.
            for entity_id in entity_ids:
                entity = by_id.get(entity_id)
                identity_ref = (
                    entity.payload.get("identity_property_ref") if entity else None
                )
                if (
                    isinstance(identity_ref, str)
                    and identity_ref
                    and identity_ref not in property_ids
                ):
                    property_ids.append(identity_ref)
        dimensions = list(dict.fromkeys(candidate.dimensions))
        grain = list(dict.fromkeys(candidate.grain))
        collection_grain = SemanticIntentResolver._independent_collection_grain(
            candidate, bundle, entity_ids
        )
        if collection_grain is not None:
            grain = list(collection_grain)
            dimensions = list(collection_grain)
        if projection_like and not grain and len(entity_ids) == 1:
            root = by_id.get(entity_ids[0])
            identity_ref = root.payload.get("identity_property_ref") if root else None
            if isinstance(identity_ref, str) and identity_ref:
                grain.append(identity_ref)
                if identity_ref not in dimensions:
                    dimensions.append(identity_ref)
        normalized_filters: list[IntentFilter] = []
        for item in candidate.filters:
            operator = {
                'ne': 'neq', 'is_not_null': 'not_null',
                '=': 'eq', '!=': 'neq', '<>': 'neq',
                '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte',
            }.get(
                item.operator, item.operator
            )
            if operator != item.operator:
                item = item.model_copy(update={'operator': operator})
            if item.scope == "COLLECTION":
                item = item.model_copy(update={"scope": "COLLECTION_CONTENT"})
            property_entry = by_id.get(item.property_id)
            value_type_ref = (
                str(property_entry.payload.get("value_type_ref") or "")
                if property_entry
                else ""
            )
            value_type = by_id.get(value_type_ref)
            canonical_unit = (
                str(value_type.payload.get("unit_ref") or "")
                if value_type
                else ""
            )
            if item.unit_ref is None:
                normalized_filters.append(
                    item.model_copy(update={"unit_ref": canonical_unit or None})
                )
                continue
            if not canonical_unit:
                raise ValueError("FILTER_CANONICAL_UNIT_NOT_DECLARED")
            scale = Decimal("1")
            offset = Decimal("0")
            if item.unit_ref != canonical_unit:
                conversions = tuple(value_type.payload.get("unit_conversions") or ())
                conversion = next(
                    (
                        value
                        for value in conversions
                        if value.get("from_unit_ref") == item.unit_ref
                    ),
                    None,
                )
                if conversion is None:
                    raise ValueError("FILTER_UNIT_CONVERSION_NOT_DECLARED")
                try:
                    scale = Decimal(str(conversion["scale"]))
                    offset = Decimal(str(conversion.get("offset", "0")))
                except (InvalidOperation, KeyError) as error:
                    raise ValueError("FILTER_UNIT_CONVERSION_INVALID") from error

            def convert(value: ScalarValue) -> ScalarValue:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("FILTER_UNIT_VALUE_NOT_NUMERIC")
                converted = Decimal(str(value)) * scale + offset
                return float(converted)

            normalized_value: FilterValue = (
                tuple(convert(value) for value in item.value)
                if isinstance(item.value, tuple)
                else convert(item.value)
            )
            normalized_filters.append(
                item.model_copy(
                    update={"value": normalized_value, "unit_ref": canonical_unit}
                )
            )

        normalized_aggregations: list[IntentAggregation] = []
        for aggregation in candidate.aggregations:
            if aggregation.operator == 'avg':
                aggregation = aggregation.model_copy(update={'operator': 'average'})
            if (
                aggregation.operator == "distinct_count"
                and not candidate.dimensions
                and not candidate.grain
                and not candidate.property_ids
                and len(entity_ids) == 1
            ):
                target = by_id.get(aggregation.target_id)
                owner = str(target.payload.get("owner_ref") or "") if target else ""
                entity = by_id.get(owner)
                if (
                    target is not None
                    and target.payload.get("kind") == "PropertyDefinition"
                    and owner == entity_ids[0]
                    and entity is not None
                    and entity.payload.get("kind") == "ObjectType"
                    and entity.payload.get("identity_property_ref")
                    == aggregation.target_id
                ):
                    normalized_aggregations.append(
                        aggregation.model_copy(
                            update={
                                "operator": "count",
                                "target_id": owner,
                                "distinct": False,
                            }
                        )
                    )
                    continue
            if aggregation.operator != "latest":
                # A repeated GROUP BY grain is not an additional latest window.
                # Conflicting/undeclared partitions remain intact for rejection.
                if (
                    aggregation.partition_by
                    and aggregation.partition_by == candidate.dimensions == candidate.grain
                    and aggregation.scope_object_id is None
                    and not candidate.property_ids
                    and all(ref in by_id and by_id[ref].payload.get("kind") == "PropertyDefinition"
                            for ref in aggregation.partition_by)
                ):
                    aggregation = aggregation.model_copy(update={"partition_by": ()})
                normalized_aggregations.append(aggregation)
                continue
            target = by_id.get(aggregation.target_id)
            inferred_scope = aggregation.scope_object_id or (
                str(target.payload.get("owner_ref") or "") if target else ""
            )
            inferred_partition = aggregation.partition_by
            if not inferred_partition and inferred_scope and candidate.grain:
                grain_is_scope_local = all(
                    by_id.get(item) is not None
                    and by_id[item].payload.get("owner_ref") == inferred_scope
                    for item in candidate.grain
                )
                if grain_is_scope_local:
                    inferred_partition = candidate.grain
            normalized_aggregations.append(
                aggregation.model_copy(
                    update={
                        "scope_object_id": inferred_scope or None,
                        "partition_by": inferred_partition,
                    }
                )
            )
        normalized_time_range = candidate.time_range
        if normalized_time_range is not None and (
            normalized_time_range.timezone or ""
        ).casefold() in {"utc", "etc/utc", "z", "+00:00"}:
            def with_utc_offset(value: str) -> str:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return value
                return value + "Z" if parsed.utcoffset() is None else value

            normalized_time_range = normalized_time_range.model_copy(
                update={
                    "start": with_utc_offset(normalized_time_range.start),
                    "end": with_utc_offset(normalized_time_range.end),
                    "timezone": "UTC",
                }
            )
        normalized_alternatives = []
        for alternative in candidate.ambiguity_alternatives:
            object_ids = tuple(
                logical_id
                for logical_id in alternative.logical_ids
                if by_id.get(logical_id) is not None
                and by_id[logical_id].payload.get("kind") == "ObjectType"
            )
            normalized_alternatives.append(
                alternative.model_copy(
                    update={"logical_ids": object_ids or alternative.logical_ids}
                )
            )
        return candidate.model_copy(
            update={
                "entity_ids": tuple(entity_ids),
                "property_ids": tuple(property_ids),
                "metric_ids": tuple(dict.fromkeys(candidate.metric_ids)),
                "dimensions": tuple(dimensions),
                "grain": tuple(grain),
                "filters": tuple(normalized_filters),
                "aggregations": tuple(normalized_aggregations),
                "time_range": normalized_time_range,
                "ambiguity_alternatives": tuple(normalized_alternatives),
            }
        )

    @staticmethod
    def _referenced_ids(candidate: IntentCandidate) -> set[str]:
        ids = set(
            (
                *candidate.entity_ids,
                *(candidate.rowset_object_ids or ()),
                *candidate.property_ids,
                *candidate.metric_ids,
                *candidate.dimensions,
                *candidate.grain,
            )
        )
        ids.update(item.property_id for item in candidate.filters)
        ids.update(item.target_id for item in candidate.aggregations)
        ids.update(
            item.scope_object_id
            for item in candidate.aggregations
            if item.scope_object_id
        )
        for aggregation in candidate.aggregations:
            ids.update(aggregation.partition_by)
            ids.update(aggregation.group_by)
        ids.update(item.property_id for item in candidate.ordering)
        if candidate.time_range:
            ids.add(candidate.time_range.property_id)
        for alternative in candidate.ambiguity_alternatives:
            ids.update(alternative.logical_ids)
        for request in candidate.quality_requests:
            ids.add(request.subject_object_id)
            if request.relationship_id:
                ids.add(request.relationship_id)
        return ids

    @staticmethod
    def _operator_contract(bundle: SemanticContextBundle) -> tuple[set[str], int]:
        operators: set[str] = set()
        limits: list[int] = []
        for entry in bundle.query_entries:
            plan = entry.payload.get("logical_plan")
            if not isinstance(plan, dict):
                continue
            operators.update(
                str(value) for value in plan.get("supported_operators") or ()
            )
            if isinstance(plan.get("max_limit"), int):
                limits.append(int(plan["max_limit"]))
        return operators, min(limits) if limits else 0

    @staticmethod
    def _result(
        *,
        status: str,
        reasons: tuple[str, ...],
        candidate: IntentCandidate,
        retrieval: RetrievalReceipt,
        bundle: SemanticContextBundle,
        resolved: ResolvedIntent | None = None,
        synthesis: IntentSynthesisReceipt | None = None,
    ) -> SemanticResolutionReceipt:
        values = {
            "status": status,
            "reason_codes": reasons,
            "clarification_count": 1 if status == "CLARIFICATION_REQUIRED" else 0,
            "resolved_intent": resolved,
            "candidate_digest": _digest(candidate),
            "retrieval_receipt_digest": retrieval.receipt_digest,
            **semantic_authority_values(bundle),
            "principal_id": bundle.principal_id,
            "purpose": bundle.purpose,
            "acl_projection_digest": bundle.acl_projection_digest,
            "semantic_bundle_digest": bundle.bundle_digest,
            "domain_profile_digest": bundle.domain_profile_digest,
            "mapping_profile_digest": bundle.mapping_profile_digest,
            "query_profile_digest": bundle.query_profile_digest,
            "catalog_snapshot_digest": bundle.catalog_snapshot_digest,
            "schema_digest": bundle.schema_digest,
            "capability_digest": bundle.capability_digest,
            "intent_synthesis_receipt_digest": (
                synthesis.receipt_digest if synthesis else ""
            ),
            "intent_model_id": synthesis.model_id if synthesis else "",
            "intent_model_digest": synthesis.model_digest if synthesis else "",
            "intent_role_digest": synthesis.role_digest if synthesis else "",
            "intent_prompt_digest": synthesis.prompt_digest if synthesis else "",
            "resolver_digest": _digest(SemanticIntentResolver.RESOLVER_ID),
        }
        digest_values = {
            **values,
            **({'reviewed_definition_authority':bundle.reviewed_definition_authority.model_dump(mode='json')}
                if bundle.reviewed_definition_authority is not None else {}),
            "resolved_intent": resolved.model_dump(mode="json") if resolved else None,
        }
        return SemanticResolutionReceipt(
            **values, receipt_digest=_digest(digest_values)
        )

    def resolve(
        self,
        candidate: IntentCandidate,
        *,
        retrieval: RetrievalReceipt,
        bundle: SemanticContextBundle,
        synthesis: IntentSynthesisReceipt | None = None,
    ) -> SemanticResolutionReceipt:
        if retrieval.active_release_digest != bundle.active_release_digest:
            raise ValueError("RETRIEVAL_RELEASE_MISMATCH")
        require_same_semantic_authority(retrieval, bundle)
        if synthesis is not None:
            require_same_semantic_authority(synthesis, bundle)
            expected_synthesis_digest = _digest(
                synthesis.model_dump(mode="json", exclude={"receipt_digest"})
            )
            if synthesis.receipt_digest != expected_synthesis_digest:
                raise ValueError("INTENT_SYNTHESIS_RECEIPT_DIGEST_INVALID")
            if (
                synthesis.status != "READY"
                or synthesis.candidate is None
                or synthesis.candidate != candidate
                or synthesis.retrieval_receipt_digest != retrieval.receipt_digest
                or synthesis.active_release_digest != bundle.active_release_digest
            ):
                raise ValueError("INTENT_SYNTHESIS_RECEIPT_CHAIN_MISMATCH")
        try:
            candidate = self.normalize_candidate(candidate, bundle)
        except ValueError as error:
            reason = str(error)
            if reason not in {
                "FILTER_CANONICAL_UNIT_NOT_DECLARED",
                "FILTER_UNIT_CONVERSION_NOT_DECLARED",
                "FILTER_UNIT_CONVERSION_INVALID",
                "FILTER_UNIT_VALUE_NOT_NUMERIC",
            }:
                raise
            return self._result(
                status="BLOCKED",
                reasons=(reason,),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        if candidate.ambiguity_alternatives:
            return self._result(
                status="CLARIFICATION_REQUIRED",
                reasons=("OUTCOME_CHANGING_AMBIGUITY",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        if candidate.unresolved_terms:
            return self._result(
                status="BLOCKED",
                reasons=("INSUFFICIENT_CONTEXT",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        retrieved_ids = {item.entry_id for item in retrieval.candidates}
        referenced = self._referenced_ids(candidate)
        if referenced & set(bundle.unavailable_logical_ids):
            return self._result(
                status="BLOCKED",
                reasons=("UNBOUND_PROPERTY",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        if not referenced <= retrieved_ids:
            return self._result(
                status="BLOCKED",
                reasons=("UNKNOWN_OR_UNRETRIEVED_LOGICAL_ID",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        by_id = {entry.entry_id: entry for entry in bundle.domain_entries}
        expected_kinds = {
            **{entry_id: "ObjectType" for entry_id in candidate.entity_ids},
            **{entry_id: "ObjectType" for entry_id in (candidate.rowset_object_ids or ())},
            **{item.subject_object_id: "ObjectType" for item in candidate.quality_requests},
            **{item.relationship_id: "RelationType" for item in candidate.quality_requests if item.relationship_id},
            **{
                entry_id: "PropertyDefinition"
                for entry_id in (
                    *candidate.property_ids,
                    *candidate.dimensions,
                    *candidate.grain,
                    *(item.property_id for item in candidate.filters),
                    *(item.property_id for item in candidate.ordering),
                    *(
                        ()
                        if candidate.time_range is None
                        else (candidate.time_range.property_id,)
                    ),
                )
            },
            **{entry_id: "Metric" for entry_id in candidate.metric_ids},
            **{
                aggregation.scope_object_id: "ObjectType"
                for aggregation in candidate.aggregations
                if aggregation.scope_object_id
            },
        }
        expected_kinds.update(
            {
                property_id: "PropertyDefinition"
                for aggregation in candidate.aggregations
                for property_id in (*aggregation.partition_by, *aggregation.group_by)
            }
        )
        if any(
            by_id[entry_id].payload.get("kind") != kind
            for entry_id, kind in expected_kinds.items()
        ):
            return self._result(
                status="BLOCKED",
                reasons=("LOGICAL_KIND_MISMATCH",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        grain_owners = {
            str(by_id[item].payload.get("owner_ref") or "")
            for item in candidate.grain
        }
        if candidate.intent_contract_version == 'scoped-result-intent-v4':
            displayed_owners = {
                by_id[item].payload.get('owner_ref') for item in candidate.property_ids
            }
            if not displayed_owners <= set(candidate.rowset_object_ids or ()):
                return self._result(status='BLOCKED', reasons=('DISPLAY_ROWSET_MEMBERSHIP_MISMATCH',),
                    candidate=candidate, retrieval=retrieval, bundle=bundle, synthesis=synthesis)
            if not grain_owners <= set(candidate.rowset_object_ids or ()):
                return self._result(status='BLOCKED', reasons=('ROOT_ROWSET_MEMBERSHIP_REQUIRED',),
                    candidate=candidate, retrieval=retrieval, bundle=bundle, synthesis=synthesis)
        if any(
            item.scope is None
            and str(by_id[item.property_id].payload.get("owner_ref") or "")
            not in grain_owners
            for item in candidate.filters
        ):
            return self._result(
                status="CLARIFICATION_REQUIRED",
                reasons=("FILTER_SCOPE_AMBIGUOUS",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        supported, max_limit = self._operator_contract(bundle)
        required = {"limit"}
        if candidate.property_ids or candidate.dimensions:
            required.add("project")
        if candidate.filters or candidate.time_range:
            required.add("filter")
        if candidate.ordering:
            required.add("order")
        required.update(item.operator for item in candidate.aggregations)
        if not required <= supported:
            return self._result(
                status="BLOCKED",
                reasons=("UNSUPPORTED_OPERATOR",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        if candidate.limit < 1 or max_limit < 1 or candidate.limit > max_limit:
            return self._result(
                status="BLOCKED",
                reasons=("LIMIT_EXCEEDS_CONTRACT",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        latest_items = tuple(
            item for item in candidate.aggregations if item.operator == "latest"
        )
        if len(latest_items) > 1:
            return self._result(
                status="BLOCKED",
                reasons=("LATEST_SCOPE_AMBIGUOUS",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        if latest_items:
            latest = latest_items[0]
            target_owner = str(by_id[latest.target_id].payload.get("owner_ref") or "")
            if (
                not latest.scope_object_id
                or target_owner != latest.scope_object_id
                or not latest.partition_by
                or any(
                    by_id[item].payload.get("owner_ref") != latest.scope_object_id
                    for item in latest.partition_by
                )
            ):
                return self._result(
                    status="BLOCKED",
                    reasons=("LATEST_SCOPE_OR_PARTITION_INVALID",),
                    candidate=candidate,
                    retrieval=retrieval,
                    bundle=bundle,
                    synthesis=synthesis,
                )
        elif candidate.intent_contract_version in {'scoped-aggregate-v3', 'scoped-result-intent-v4'}:
            for item in candidate.aggregations:
                target=by_id[item.target_id].payload
                owner=item.target_id if target.get('kind')=='ObjectType' else target.get('owner_ref')
                if item.scope_object_id != owner:
                    return self._result(status='BLOCKED',reasons=('AGGREGATE_SCOPE_MISMATCH',),
                        candidate=candidate,retrieval=retrieval,bundle=bundle,synthesis=synthesis)
                if item.partition_by or item.group_by != candidate.dimensions or item.group_by != candidate.grain:
                    return self._result(status='BLOCKED',reasons=('AGGREGATE_GROUPING_MISMATCH',),
                        candidate=candidate,retrieval=retrieval,bundle=bundle,synthesis=synthesis)
        elif any(
            item.scope_object_id is not None or item.partition_by
            for item in candidate.aggregations
        ):
            return self._result(
                status="BLOCKED",
                reasons=("AGGREGATION_LATEST_FIELDS_FORBIDDEN",),
                candidate=candidate,
                retrieval=retrieval,
                bundle=bundle,
                synthesis=synthesis,
            )
        for aggregation in candidate.aggregations:
            target = by_id[aggregation.target_id]
            if target.payload.get("kind") == "Metric":
                required_metric_fields = {
                    "aggregation",
                    "grain",
                    "unit",
                    "time_semantics",
                    "inclusion",
                    "exclusion",
                }
                if target.payload.get(
                    "aggregation"
                ) != aggregation.operator or not required_metric_fields <= set(
                    target.payload
                ):
                    return self._result(
                        status="BLOCKED",
                        reasons=("METRIC_SEMANTICS_INCOMPLETE",),
                        candidate=candidate,
                        retrieval=retrieval,
                        bundle=bundle,
                        synthesis=synthesis,
                    )
            elif aggregation.operator == "average":
                value_type = target.payload.get("value_type")
                value_type_ref = target.payload.get("value_type_ref")
                if not value_type and isinstance(value_type_ref, str):
                    referenced = by_id.get(value_type_ref)
                    if referenced is not None:
                        value_type = referenced.payload.get("primitive_type")
                if value_type not in {"integer", "number", "float", "decimal"}:
                    return self._result(
                        status="BLOCKED",
                        reasons=("AGGREGATION_TYPE_INCOMPATIBLE",),
                        candidate=candidate,
                        retrieval=retrieval,
                        bundle=bundle,
                        synthesis=synthesis,
                    )
        resolved = ResolvedIntent(
            candidate=candidate,
            intent_digest=_digest(candidate),
            **semantic_authority_values(bundle),
            domain_profile_digest=bundle.domain_profile_digest,
            query_profile_digest=bundle.query_profile_digest,
        )
        return self._result(
            status="RESOLVED",
            reasons=(),
            candidate=candidate,
            retrieval=retrieval,
            bundle=bundle,
            resolved=resolved,
            synthesis=synthesis,
        )
