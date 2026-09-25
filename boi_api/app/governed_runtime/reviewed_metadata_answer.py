"""Reviewed, provisional response using the common governed answer contracts.

Only the Application Service calls this after current source/review/mapping/ACL
checks and a protected Gateway result read. No candidate becomes a Release.
"""
from types import SimpleNamespace
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .answer_meaning_context import build_answer_meaning_context
from .governed_answer_artifact import (
    ArtifactExecutionEvidence, GovernedAnswerArtifact, GovernedAnswerArtifactBuilder,
    _quality_disclosures, _semantic_projection,
)
from .metadata_mapping_profile import parse_declared_metadata_mapping_inputs
from .multi_result_query_gateway import MultiResultLogicalPlan, ReviewedQueryAuthority
from .semantic_binding_contract import Digest, EvidenceUse, FrozenContract, Ref, SourceRecordRevision, semantic_digest
from .semantic_binding_validator import FieldEvidenceRecord
from .semantic_profile_loader import LoadedProfileEntry
from .reviewed_answer_presentation import (
    ReviewedAnswerPresentation,
    compose_reviewed_answer_presentation,
)


class AnswerSourceProvenance(FrozenContract):
    definition_ref: Ref
    candidate_digest: Digest
    source_record: SourceRecordRevision
    logical_definition_digest: Digest
    field_evidence: tuple[FieldEvidenceRecord, ...] = Field(min_length=1)
    logical_evidence_uses: tuple[EvidenceUse, ...] = Field(min_length=1)
    output_receipt_digest: Digest

    @model_validator(mode='after')
    def source_chain(self):
        record = self.source_record
        spans = {item.span_ref:item for item in self.field_evidence}
        if len(spans) != len(self.field_evidence):
            raise ValueError('REVIEWED_ANSWER_SOURCE_SPAN_DUPLICATE')
        if any(item.record_identity_digest != record.identity_digest
                or item.source_revision_digest != record.source_revision_digest
                or item.snapshot_digest != record.snapshot_digest for item in self.field_evidence):
            raise ValueError('REVIEWED_ANSWER_SOURCE_REVISION_MISMATCH')
        for use in self.logical_evidence_uses:
            if (spans.get(use.span_ref) != FieldEvidenceRecord.from_evidence_use(use)
                    or use.supports_contract_digest != self.logical_definition_digest):
                raise ValueError('REVIEWED_ANSWER_SOURCE_EVIDENCE_MISMATCH')
        return self


class ReviewedGovernedAnswerArtifact(GovernedAnswerArtifact):
    schema_name: Literal[
        'boi-governed-answer-artifact/v4', 'boi-governed-answer-artifact/v5'
    ] = 'boi-governed-answer-artifact/v5'
    question_digest: str | None = None
    active_release_digest: None = None
    input_kind: Literal['typed_logical_intent', 'natural_question'] = 'typed_logical_intent'
    candidate_authority: ReviewedQueryAuthority
    preparation_receipt_digest: Digest
    source_provenance: tuple[AnswerSourceProvenance, ...]
    source_subject_facets: tuple[dict, ...]
    qualifier_resolution: dict
    quality_audit_receipt: dict
    reviewed_answerability_receipt: dict
    presentation: ReviewedAnswerPresentation | None = None

    @model_serializer(mode='wrap')
    def preserve_reviewed_wire(self, handler):
        value = handler(self)
        if self.presentation is None:
            value.pop('presentation', None)
        return value

    def _authority_digest_values(self):
        return (self.preparation_receipt_digest,)

    @model_validator(mode='after')
    def reviewed_authority_binding(self):
        authority = self.candidate_authority
        natural = authority.contract_version == 'boi/reviewed-query-authority@2'
        if (authority.semantic_context_digest != self.profile_bundle_digest
                or authority.intent_digest != self.resolved_intent_digest
                or authority.mapping_input_digest != self.mapping_profile_digest
                or authority.freeze_receipt_digest != self.resource_freeze_receipt_digest
                or semantic_digest(authority.principal) != self.principal_digest
                or semantic_digest(authority.purpose) != self.purpose_digest
                or self.execution.classification != 'PROVISIONAL'
                or self.execution.lane != 'exploratory'):
            raise ValueError('REVIEWED_ANSWER_AUTHORITY_MISMATCH')
        if natural:
            if (self.input_kind != 'natural_question'
                    or self.question_digest != authority.question_digest
                    or self.policy_digest != authority.planning_policy_digest):
                raise ValueError('REVIEWED_NATURAL_ANSWER_AUTHORITY_MISMATCH')
        elif self.input_kind != 'typed_logical_intent' or self.question_digest is not None:
            raise ValueError('REVIEWED_TYPED_ANSWER_AUTHORITY_MISMATCH')
        receipt = self.reviewed_answerability_receipt
        if (receipt.get('receipt_digest') != self.answerability_receipt_digest
                or receipt.get('preparation_receipt_digest') != self.preparation_receipt_digest
                or receipt.get('execution_receipt_digest') != self.execution.execution_receipt_digest
                or receipt.get('state') != self.answerability_state
                or semantic_digest({k:v for k,v in receipt.items() if k != 'receipt_digest'}) != self.answerability_receipt_digest):
            raise ValueError('REVIEWED_ANSWER_EXECUTION_BINDING_MISMATCH')
        reviewed = {item.ref:item for item in self.meaning_context.definitions
            if item.revision_id.startswith('reviewed-definition:')}
        if (set(reviewed) != {item.definition_ref for item in self.source_provenance}
                or len({item.candidate_digest for item in self.source_provenance}) != len(self.source_provenance)
                or any(item.logical_definition_digest != reviewed[item.definition_ref].definition_digest
                    for item in self.source_provenance)):
            raise ValueError('REVIEWED_ANSWER_SOURCE_COVERAGE_MISMATCH')
        if self.schema_name == 'boi-governed-answer-artifact/v4':
            if self.presentation is not None:
                raise ValueError('REVIEWED_ANSWER_PRESENTATION_REVISION_REQUIRED')
            return self
        if self.presentation is None:
            raise ValueError('REVIEWED_ANSWER_PRESENTATION_REQUIRED')
        expected = compose_reviewed_answer_presentation(
            question_digest=self.question_digest,
            resolved_intent=self.meaning_context.resolved_intent,
            qualifier_resolution=self.qualifier_resolution,
            meaning_context=self.meaning_context,
            result_sets=self.result_sets,
            source_provenance=self.source_provenance,
            execution=self.execution,
        )
        if self.presentation != expected:
            raise ValueError('REVIEWED_ANSWER_PRESENTATION_BINDING_MISMATCH')
        return self


def _reviewed_entries(context):
    # Identical definitions may have several distinct source records. Preserve
    # every source separately; the logical entry has a content revision.
    entries = {item['entry_id']: LoadedProfileEntry.model_validate(item)
        for item in context['existing_definition_index']['items'] if item.get('category') == 'domain'}
    proposed = {}
    for candidate in context['domain_candidates']:
        definition = candidate['logical_definition']
        ref = definition['id']
        if ref in proposed and proposed[ref] != definition:
            raise ValueError('REVIEWED_ANSWER_DEFINITION_CONFLICT')
        proposed[ref] = definition
    for ref, definition in proposed.items():
        evidence = tuple(sorted({span['span_ref'] for candidate in context['domain_candidates']
            if candidate['logical_definition']['id'] == ref for span in candidate['field_evidence']}))
        revision = semantic_digest(definition)
        entries[ref] = LoadedProfileEntry(entry_id=ref, category='domain',
            revision_id='reviewed-definition:'+revision, revision_digest=revision,
            boi_id=ref, visibility='private', evidence_resources=evidence, payload=definition)
    return tuple(entries.values())


def build_reviewed_metadata_answer(*, prepared, execution, access_receipt_digest):
    """Build an answer from a verified preparation and actual Gateway execution."""
    context = prepared['semantic_context']
    plan = MultiResultLogicalPlan.model_validate(prepared['logical_plan'])
    authority = plan.candidate_authority
    natural = authority is not None and authority.contract_version == 'boi/reviewed-query-authority@2'
    context_matches = (
        prepared.get('semantic_bundle', {}).get('bundle_digest') == authority.semantic_context_digest
        if natural else semantic_digest(context) == authority.semantic_context_digest
    ) if authority is not None else False
    if (authority is None or plan.active_release_digest is not None
            or execution.receipt.candidate_authority != authority
            or execution.receipt.logical_plan_digest != plan.plan_digest
            or execution.receipt.result_digest != execution.result.result_digest
            or execution.receipt.receipt_digest != semantic_digest(execution.receipt.model_dump(mode='json',exclude={'receipt_digest'}))
            or not context_matches
            or prepared['receipt_digest'] != semantic_digest({k:v for k,v in prepared.items() if k != 'receipt_digest'})):
        raise ValueError('REVIEWED_ANSWER_PREPARATION_MISMATCH')
    if natural:
        definition_authority = prepared['semantic_bundle']['reviewed_definition_authority']
        planning = prepared['semantic_plan_outcome']
        freeze = prepared['input_freeze']
        if (semantic_digest(definition_authority) != authority.reviewed_definition_authority_digest
                or prepared['semantic_interpretation']['receipt_digest']
                    != authority.question_interpretation_receipt_digest
                or planning['planning_context']['context_digest']
                    != authority.semantic_planning_context_digest
                or planning['shape_selection']['receipt_digest']
                    != authority.shape_selection_receipt_digest
                or planning['semantic_plan']['plan_digest'] != authority.semantic_plan_digest
                or planning['physical_binding']['binding_digest'] != authority.physical_binding_digest
                or prepared['qualifier_application_receipt']['receipt_digest']
                    != authority.qualifier_application_receipt_digest
                or freeze['receipt_digest'] != authority.freeze_receipt_digest):
            raise ValueError('REVIEWED_NATURAL_ANSWER_PREPARATION_MISMATCH')
    entries = _reviewed_entries(context)
    inputs = parse_declared_metadata_mapping_inputs(context['declared_mapping_inputs'])
    mappings = tuple(LoadedProfileEntry(entry_id=p.physical.mapping_ref, category='mapping',
        revision_id='mapping:'+p.physical.revision_digest, revision_digest=p.physical.revision_digest,
        boi_id=p.physical.mapping_ref, visibility='private', evidence_resources=p.evidence_span_refs,
        payload={'mapping_id':p.physical.mapping_ref, 'domain_ref':p.logical_property_ref,
            **({'temporal_encoding':p.physical.temporal_encoding.model_dump(mode='json')}
                if p.physical.temporal_encoding is not None else {})})
        for p in inputs.properties)
    view = SimpleNamespace(bundle=SimpleNamespace(domain_entries=entries, mapping_entries=mappings))
    by_id = {item.result_set_id:item for item in execution.result.result_sets}
    results = tuple(GovernedAnswerArtifactBuilder._multi_result_set(context=view, plan=item,
        result=by_id[item.result_set_id], protected_artifact_ref=execution.receipt.result_artifact_ref)
        for item in plan.result_sets)
    intent = prepared['input_freeze']['intent']
    qualifier_resolution = (
        prepared['qualifier_resolution'] if natural else context['qualifier_resolution']
    )
    roots = {item['ref'] for item in qualifier_resolution['definition_revisions']}
    if natural:
        roots.update(intent.get('entity_ids', ()))
        roots.update(intent.get('property_ids', ()))
        roots.update(intent.get('metric_ids', ()))
        roots.update(intent.get('dimensions', ()))
        roots.update(intent.get('grain', ()))
        roots.update(item['property_id'] for item in intent.get('filters', ()))
        roots.update(item['target_id'] for item in intent.get('aggregations', ()))
        roots.update(item['scope_object_id'] for item in intent.get('aggregations', ())
                     if item.get('scope_object_id'))
        roots.update(item['property_id'] for item in intent.get('ordering', ()))
        if intent.get('time_range'):
            roots.add(intent['time_range']['property_id'])
    meaning = build_answer_meaning_context(entries=entries, root_refs=tuple(roots),
        input_context_digest=authority.semantic_context_digest, resolved_intent=intent)
    used = {item.ref for item in meaning.definitions}
    provenance = tuple(AnswerSourceProvenance.model_validate({key:candidate[key] for key in (
            'candidate_digest','source_record','logical_definition_digest','logical_evidence_uses',
            'field_evidence','output_receipt_digest')}
        | {'definition_ref':candidate['logical_definition']['id']}
        ) for candidate in context['domain_candidates'] if candidate['logical_definition']['id'] in used)
    receipt = execution.receipt
    answerability = dict(contract_version='boi/reviewed-answerability@1', state='EXECUTED_PROVISIONAL',
        preparation_receipt_digest=prepared['receipt_digest'], execution_receipt_digest=receipt.receipt_digest,
        meaning_completeness=meaning.completeness, semantic_equivalence_decided=False)
    answerability['receipt_digest'] = semantic_digest(answerability)
    evidence = ArtifactExecutionEvidence(execution_id=execution.execution_id, lane='exploratory',
        classification='PROVISIONAL', execution_receipt_ref='multi-result-execution-receipt:'+execution.execution_id,
        execution_receipt_digest=receipt.receipt_digest, logical_plan_digest=plan.plan_digest,
        source_snapshot_digest=receipt.source_snapshot_digest, result_digest=execution.result.result_digest,
        attestation_state='ABSENT', attestation_ref=None, attestation_digest=None)
    if natural:
        selected = prepared['semantic_plan_outcome']['shape_selection']['solver_outcome']['selected_shape']
        result_shape = selected['shape']
        result_shape_digest = semantic_digest(selected)
        root_object_ref = selected['root_object_ref']
        exact_grain = tuple(selected['exact_grain'])
        policy_digest = authority.planning_policy_digest
        quality = _quality_disclosures(execution.result.quality_sidecars)
    else:
        result_shape = 'ObjectSet'
        result_shape_digest = None
        root_object_ref = intent['root_object_ref']
        exact_grain = plan.result_sets[0].exact_grain
        policy_digest = inputs.policy_digest
        quality = ()
    presentation = compose_reviewed_answer_presentation(
        question_digest=authority.question_digest if natural else None,
        resolved_intent=intent,
        qualifier_resolution=qualifier_resolution,
        meaning_context=meaning,
        result_sets=results,
        source_provenance=provenance,
        execution=evidence,
    )
    values = dict(schema_name='boi-governed-answer-artifact/v5',
        question_digest=authority.question_digest if natural else None,
        active_release_digest=None,
        input_kind='natural_question' if natural else 'typed_logical_intent',
        candidate_authority=authority.model_dump(mode='json'),
        preparation_receipt_digest=prepared['receipt_digest'], resolved_intent_digest=authority.intent_digest,
        answerability_state=answerability['state'], answerability_receipt_digest=answerability['receipt_digest'],
        reviewed_answerability_receipt=answerability,
        principal_digest=semantic_digest(authority.principal), purpose_digest=semantic_digest(authority.purpose),
        domain_profile_digest=plan.domain_profile_digest, mapping_profile_digest=plan.mapping_profile_digest,
        query_profile_digest=plan.query_profile_digest, profile_bundle_digest=authority.semantic_context_digest,
        catalog_snapshot_digest=inputs.catalog_snapshot_digest, schema_digest=inputs.schema_snapshot_digest,
        policy_digest=policy_digest, result_shape=result_shape,
        result_shape_contract_digest=result_shape_digest,
        root_object_ref=root_object_ref, exact_grain=exact_grain,
        result_sets=[item.model_dump(mode='json') for item in results],
        data_quality=[item.model_dump(mode='json') for item in quality],
        evidence_refs=tuple(dict.fromkeys([*(ref for d in meaning.definitions for ref in d.evidence_refs),
            *(ref for result in results for f in result.fields for ref in f.evidence_refs), evidence.execution_receipt_ref])),
        execution=evidence.model_dump(mode='json'), resource_access_receipt_digest=access_receipt_digest,
        resource_freeze_receipt_digest=authority.freeze_receipt_digest, meaning_context=meaning.model_dump(mode='json'),
        source_provenance=[item.model_dump(mode='json') for item in provenance],
        source_subject_facets=context.get('source_subject_facets',()),
        qualifier_resolution=qualifier_resolution,
        quality_audit_receipt=context['quality_audit_receipt'],
        presentation=presentation.model_dump(mode='json'),
        raw_sql_exposed=False, model_repaired_sql=False)
    return ReviewedGovernedAnswerArtifact.model_validate({**values,
        'artifact_semantic_digest':semantic_digest(_semantic_projection(values))})
