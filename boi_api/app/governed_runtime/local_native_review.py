"""Nonexecutable review opinions admitted through the ordinary bundle workflow.

Recording positive, negative or unknown opinions grants no fact/use authority.
The supplied session remains unverified; source and reading fences are separate.
"""
from .native_definition_context import NativeDefinitionReview
from .native_observation import NativeObservation, _json
from .domain_asset_store import source_manifest_digest
from .semantic_binding_contract import semantic_digest

CONTRACT = 'boi/native-definition-review@1'
CAPABILITY = 'native_definition_review_opinion'


def parse_review_draft(draft):
    if draft.kind != 'pack':
        raise ValueError('LOCAL_NATIVE_REVIEW_PACK_REQUIRED')
    observation = NativeObservation.model_validate(_json(draft.content_json))
    request = observation.request
    review = NativeDefinitionReview.model_validate(_json(observation.value_json))
    if (request.review_contract_version != CONTRACT
            or semantic_digest(_json(request.output_schema_json))
            != semantic_digest(NativeDefinitionReview.model_json_schema())):
        raise ValueError('NATIVE_DEFINITION_REVIEW_CONTRACT_MISMATCH')
    if request.input_revisions != review.definition_revisions:
        raise ValueError('NATIVE_DEFINITION_REVIEW_INPUT_MISMATCH')
    if request.knowledge_reading_ref != draft.definition_reading_ref:
        raise ValueError('NATIVE_OBSERVATION_READING_MISMATCH')
    if source_manifest_digest(draft.sources) != request.source_manifest_digest:
        raise ValueError('NATIVE_OBSERVATION_SOURCE_MISMATCH')
    dependencies = {d.revision for d in draft.dependencies if d.required}
    if not set(request.input_revisions) <= dependencies:
        raise ValueError('NATIVE_OBSERVATION_INPUT_REVISION_NOT_READ_OR_DEPENDENT')
    return observation, review


def validate_review_reading(draft, context):
    observation, review = parse_review_draft(draft)
    if context is None or context.source_manifest_digest != observation.request.source_manifest_digest:
        raise ValueError('NATIVE_OBSERVATION_CONTEXT_BINDING_MISMATCH')
    assets = {a.revision:a for a in context.assets}
    if any(ref not in assets or assets[ref].kind != 'definition'
            or assets[ref].authority != 'candidate' for ref in review.definition_revisions):
        raise ValueError('NATIVE_DEFINITION_REVIEW_KIND_OR_SCOPE_MISMATCH')
    return observation, review
